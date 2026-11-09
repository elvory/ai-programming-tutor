"""Bounded M1 orchestration; never calls AI, drafts or activity writers."""
from math import isfinite
from threading import BoundedSemaphore

from services.problem_service import get_problem

from .adapters.python_adapter import get_adapter, parse_result
from .config import ExecutionConfig
from .docker_runner import DockerRunner
from .exceptions import ExecutionBusy
from .schemas import ExecutionRequest, ExecutionResponse


class ExecutionRejected(Exception):
    """A safe request rejection, before any container is created."""

    def __init__(self, status_code, error_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


class ExecutionService:
    def __init__(self, config=None, runner=None):
        self._config_invalid = False
        try:
            self.config = config if config is not None else ExecutionConfig.from_env()
        except (TypeError, ValueError):
            # Optional execution settings must not disable the existing tutor.
            self.config = ExecutionConfig()
            self._config_invalid = True
        self.runner = runner if runner is not None else DockerRunner(self.config)
        self._slots = BoundedSemaphore(self.config.max_concurrent)
        self._cleanup_failed = False

    def capabilities(self):
        return {
            "enabled": self.config.enabled and not self._cleanup_failed,
            "engine_verified": False,
            "configuration_valid": not self._config_invalid,
            "languages": ["python"],
            "problem_ids": [1],
            "judging_scope": "public_examples",
            "official_accepted": False,
            "max_concurrent": self.config.max_concurrent,
            "note": "M1 仅支持 Python 两数之和公开示例；Engine 可用性在每次运行前检查。",
        }

    def run(self, request: ExecutionRequest):
        if self._config_invalid:
            raise ExecutionRejected(503, "EXECUTION_CONFIG_INVALID", "执行配置不正确，代码执行暂不可用。")
        if not self.config.enabled:
            raise ExecutionRejected(503, "EXECUTION_DISABLED", "代码执行尚未启用，请按 M1 文档配置后端。")
        if self._cleanup_failed:
            raise ExecutionRejected(503, "CLEANUP_UNCONFIRMED", "上次执行资源回收未确认，执行已暂停，请检查 Docker。")
        if len(request.code.encode("utf-8")) > self.config.code_limit:
            raise ExecutionRejected(413, "SOURCE_TOO_LARGE", "代码超过服务端大小限制。")
        problem = get_problem(request.problem_id)
        if problem is None:
            raise ExecutionRejected(404, "PROBLEM_NOT_FOUND", "未找到这道题。")
        if request.problem_id != 1 or problem.get("slug") != "two-sum":
            raise ExecutionRejected(422, "PROBLEM_NOT_SUPPORTED", "M1 暂时只支持 Python 两数之和公开示例，当前题目尚未适配。")
        adapter = get_adapter(request.problem_id, problem["slug"])
        if not self._slots.acquire(blocking=False):
            raise ExecutionRejected(429, "EXECUTION_BUSY", "当前已有代码执行，请稍后重试。")
        try:
            try:
                result = self.runner.run(request.code, adapter.case_input, str(request.request_id))
                cleanup = result.cleanup_confirmed is True
                if not cleanup:
                    self._cleanup_failed = True
                fields = {
                    "status": result.status,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "candidate": None,
                    "error_message": result.error_message,
                    "error_code": result.error_code,
                }
                if fields["status"] in {"SUCCESS", "RUNTIME_ERROR"} and cleanup:
                    fields.update(parse_result(result.stdout, result.stderr, result.exit_code))
                if not cleanup:
                    fields.update(status="SYSTEM_ERROR", error_message="执行资源回收未确认，执行已暂停。",
                                  error_code="CLEANUP_UNCONFIRMED")
                # Parser diagnostics originate in the untrusted container and
                # may add a message to stderr. Enforce the configured byte caps
                # again after parsing, including multi-byte Unicode text.
                for name, limit in (("stdout", self.config.stdout_limit), ("stderr", self.config.stderr_limit)):
                    fields[name] = fields[name].encode("utf-8", errors="replace")[:limit].decode("utf-8", errors="ignore")
                elapsed = result.execution_time_ms
                if elapsed is not None and (not isinstance(elapsed, (int, float)) or not isfinite(elapsed) or elapsed < 0):
                    elapsed = None
                return ExecutionResponse(
                    status=fields["status"], stdout=fields["stdout"], stderr=fields["stderr"],
                    exit_code=result.exit_code, execution_time_ms=elapsed,
                    problem_id=request.problem_id, request_id=str(request.request_id),
                    error_message=fields["error_message"], error_code=fields["error_code"],
                    cleanup_confirmed=cleanup, limits=result.limits,
                    judge=adapter.judge(fields["candidate"]) if fields["status"] == "SUCCESS" else adapter.not_run(),
                )
            except ExecutionBusy:
                raise ExecutionRejected(429, "EXECUTION_BUSY", "当前已有代码执行，请稍后重试。") from None
            except Exception:
                # No exception text, host paths or inherited environment crosses this boundary.
                self._cleanup_failed = True
                return ExecutionResponse(
                    status="SYSTEM_ERROR", stdout="", stderr="", exit_code=None, execution_time_ms=None,
                    problem_id=request.problem_id, request_id=str(request.request_id),
                    error_message="代码执行服务暂时无法完成请求，请检查 Docker 后重试。",
                    error_code="EXECUTION_SYSTEM_ERROR", cleanup_confirmed=False,
                    judge=adapter.not_run(),
                )
        finally:
            self._slots.release()
