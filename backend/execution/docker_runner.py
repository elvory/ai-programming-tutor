"""Bounded Docker CLI controller. Submitted Python only runs in a container.

M1 targets Docker Desktop's local Linux context. All control commands are fixed
argv lists, with bounded pipes, deadlines and a minimal host environment.
"""
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import time
from uuid import uuid4

from .config import ExecutionConfig
from .exceptions import DockerControlError, ExecutionBusy


HOST_ENV_KEYS = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
                 "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA")
NAME_PATTERN = re.compile(r"ai-tutor-m1-[0-9a-f]{32}\Z")


def start_watchdog(*args):
    # Lazy import keeps mock-only tests independent of the helper process.
    from .watchdog import start_watchdog as start
    return start(*args)


@dataclass
class SandboxResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    execution_time_ms: float | None = None
    error_message: str | None = None
    error_code: str | None = None
    candidate: object = None
    cleanup_confirmed: bool = True
    limits: dict = field(default_factory=dict)


class _ExecutionLock:
    """One local execution across API processes, with a crash recovery journal."""
    def __init__(self, directory):
        self.uncertain_until = None
        directory = Path(directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink() or not directory.is_dir():
            raise DockerControlError("UNSAFE_LOCK_DIRECTORY", "执行锁目录不可用。")
        if os.name != "nt" and (directory.stat().st_uid != os.getuid() or stat.S_IMODE(directory.stat().st_mode) & 0o077):
            raise DockerControlError("UNSAFE_LOCK_DIRECTORY", "执行锁目录权限不安全。")
        path = directory / "execution.lock"
        if path.is_symlink():
            raise DockerControlError("UNSAFE_LOCK_DIRECTORY", "执行锁文件不可用。")
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        self.file = os.fdopen(os.open(path, flags, 0o600), "r+b", buffering=0)
        try:
            if self.file.seek(0, os.SEEK_END) == 0:
                self.file.write(b"\0")
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise ExecutionBusy() from None

    def read(self):
        self.file.seek(1)
        raw = self.file.read(1025)
        if len(raw) > 1024:
            raise DockerControlError("INVALID_RECOVERY_JOURNAL", "执行恢复信息需要人工检查。")
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or not NAME_PATTERN.fullmatch(data.get("name", "")):
                raise ValueError()
            until = data.get("uncertain_until")
            if until is not None and (type(until) not in (float, int) or not math.isfinite(until)):
                raise ValueError()
            self.uncertain_until = until
            return data["name"]
        except (ValueError, TypeError, KeyError):
            raise DockerControlError("INVALID_RECOVERY_JOURNAL", "执行恢复信息需要人工检查。") from None

    def write(self, name=None, uncertain_until=None):
        self.file.seek(1)
        self.file.write(json.dumps({"name": name, "uncertain_until": uncertain_until}).encode() if name else b"")
        self.file.truncate()
        os.fsync(self.file.fileno())

    def close(self):
        if self.file.closed:
            return
        self.file.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.file, fcntl.LOCK_UN)
        self.file.close()


def _collect(process, timeout, stdout_limit, stderr_limit, payload=None):
    """Read each pipe incrementally and retain at most its byte budget."""
    stdout, stderr = bytearray(), bytearray()
    exceeded = threading.Event()
    failed = threading.Event()

    def pump(stream, destination, limit):
        try:
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    return
                room = max(0, limit - len(destination))
                destination.extend(chunk[:room])
                if len(chunk) > room:
                    exceeded.set()
                    return
        except (OSError, ValueError):
            failed.set()

    def write_input():
        try:
            if payload is not None:
                process.stdin.write(payload)
                process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            # A program may exit without reading stdin. Inspect its actual state.
            pass
        finally:
            try:
                process.stdin.close()
            except (OSError, ValueError):
                pass

    threads = [threading.Thread(target=pump, args=(process.stdout, stdout, stdout_limit), daemon=True),
               threading.Thread(target=pump, args=(process.stderr, stderr, stderr_limit), daemon=True)]
    if payload is not None:
        threads.append(threading.Thread(target=write_input, daemon=True))
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + timeout
    reason = None
    try:
        while process.poll() is None:
            if exceeded.is_set():
                reason = "output"
                break
            if failed.is_set():
                reason = "communication"
                break
            if time.monotonic() >= deadline:
                reason = "timeout"
                break
            exceeded.wait(min(0.02, max(0, deadline - time.monotonic())))
        if reason:
            process.kill()  # Stops the CLI; container termination is separate.
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            reason = "communication"
        for thread in threads:
            thread.join(timeout=1)
        if any(thread.is_alive() for thread in threads):
            reason = reason or "communication"
        if exceeded.is_set():
            reason = "output"
        elif failed.is_set() and not reason:
            reason = "communication"
        return bytes(stdout), bytes(stderr), process.returncode, reason
    finally:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass


class DockerRunner:
    def __init__(self, config=None, *, docker_path=None, lock_directory=None):
        self.config = config or ExecutionConfig.from_env()
        self.docker_path = docker_path or shutil.which("docker")
        self.lock_directory = lock_directory or Path(tempfile.gettempdir()) / "ai-tutor-execution-m1"
        self.environment = {key: value for key, value in os.environ.items() if key.upper() in HOST_ENV_KEYS}
        self._cleanup_failed = False
        self._retained_lock = None
        self._run_lock = threading.Lock()

    def _spawn(self, args, *, input_pipe=False):
        if not self.docker_path:
            raise DockerControlError("DOCKER_NOT_INSTALLED", "未找到 Docker CLI，请安装并启动 Docker Desktop。")
        return subprocess.Popen([self.docker_path, "--context", "desktop-linux", *args],
            stdin=subprocess.PIPE if input_pipe else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
            env=self.environment, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)

    def _control(self, args, *, timeout=None, check=True):
        try:
            process = self._spawn(args)
            out, err, exit_code, reason = _collect(process, timeout or self.config.prepare_timeout_seconds, 32768, 32768)
        except (OSError, subprocess.SubprocessError):
            raise DockerControlError() from None
        if reason or (check and exit_code != 0):
            raise DockerControlError()
        return exit_code, out, err

    def _preflight(self):
        _, data, _ = self._control(["info", "--format", '{"os":"{{.OSType}}","security":{{json .SecurityOptions}}}'])
        try:
            info = json.loads(data)
            if info["os"] != "linux" or not any("seccomp" in option and "unconfined" not in option for option in info["security"]):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise DockerControlError("UNSAFE_DOCKER_ENGINE", "需要启用默认 seccomp 的 Linux Docker Engine。") from None
        _, data, _ = self._control(["image", "inspect", "--format", "{{.Id}}", self.config.image], check=False)
        image_id = data.decode("ascii", errors="ignore").strip()
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise DockerControlError("IMAGE_UNAVAILABLE", "Python 执行镜像不可用，请由负责人预先准备镜像。")
        return image_id

    def availability(self):
        if not self.config.enabled:
            return {"available": False, "reason": "EXECUTION_DISABLED"}
        if self._cleanup_failed:
            return {"available": False, "reason": "CLEANUP_UNCONFIRMED"}
        try:
            self._preflight()
        except DockerControlError as error:
            return {"available": False, "reason": error.code}
        return {"available": True, "reason": None}

    def _remove(self, name):
        try:
            # No broad prune or label-only deletion. This is our pre-recorded name.
            self._control(["rm", "--force", "--volumes", name], timeout=5, check=False)
            _, remaining, _ = self._control(["container", "ls", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"], timeout=5)
            return not remaining.strip()
        except DockerControlError:
            return False

    def run(self, code, case_input, request_id):
        config = self.config
        if self._cleanup_failed:
            return SandboxResult("SYSTEM_ERROR", error_code="CLEANUP_UNCONFIRMED", error_message="前次执行资源尚未确认清理，执行服务已关闭。", cleanup_confirmed=False)
        if not config.enabled:
            return SandboxResult("SYSTEM_ERROR", error_code="EXECUTION_DISABLED", error_message="代码执行尚未启用。")
        if not self._run_lock.acquire(blocking=False):
            raise ExecutionBusy()
        lock = None
        name = None
        guard = None
        create_pending = False
        result = SandboxResult("SYSTEM_ERROR", error_code="EXECUTION_FAILED", error_message="代码执行服务未能完成，请稍后重试。")
        try:
            lock = _ExecutionLock(self.lock_directory)
            old_name = lock.read()
            if old_name:
                if lock.uncertain_until is not None and time.time() < lock.uncertain_until:
                    raise DockerControlError("CLEANUP_UNCONFIRMED", "中断创建的容器仍在回收观察期，请稍后重启执行服务。")
                if not self._remove(old_name):
                    raise DockerControlError("CLEANUP_UNCONFIRMED", "上次中断的执行资源尚未回收。")
                lock.write()
            image_id = self._preflight()
            from .adapters.python_adapter import BOOTSTRAP
            payload = json.dumps({"code": code, "input": case_input}, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(code.encode("utf-8")) > config.code_limit or len(payload) > config.body_limit:
                raise DockerControlError("INPUT_TOO_LARGE", "代码或输入超过执行上限。")
            name = "ai-tutor-m1-" + uuid4().hex
            guard_deadline = time.time() + config.prepare_timeout_seconds + config.timeout_seconds + 20
            # Persist before create: an interrupted CLI can lose the response
            # while the daemon is still completing the operation.
            lock.write(name, uncertain_until=guard_deadline)
            guard = start_watchdog(name, guard_deadline,
                                   self.docker_path, self.environment)
            args = ["create", "--interactive", "--pull=never", "--name", name,
                    "--label", "ai-tutor.execution=m1", "--network=none", "--read-only",
                    "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=65534:65534",
                    "--memory=" + str(config.memory_mb) + "m", "--memory-swap=" + str(config.memory_mb) + "m",
                    "--cpus=" + str(config.cpu), "--pids-limit=" + str(config.pids),
                    "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=" + str(config.tmpfs_mb) + "m,mode=1777",
                    "--workdir", "/tmp", "--log-driver=none", "--ulimit", "nofile=128:128",
                    "--ulimit", "fsize=16777216:16777216", "--init",
                    image_id, "python", "-I", "-B", "-u", "-c", BOOTSTRAP]
            create_pending = True
            self._control(args)
            create_pending = False
            lock.write(name)
            started = time.monotonic()
            process = self._spawn(["start", "--attach", "--interactive", name], input_pipe=True)
            out, err, _, reason = _collect(process, config.timeout_seconds, config.stdout_limit, config.stderr_limit, payload)
            elapsed = round((time.monotonic() - started) * 1000, 3)
            if reason in ("timeout", "output"):
                self._control(["kill", name], timeout=5, check=False)
            _, state_data, _ = self._control(["inspect", "--type", "container", "--format", "{{json .State}}", name], timeout=5)
            state = json.loads(state_data)
            limits = {"memory_mb": config.memory_mb, "cpu": config.cpu, "pids": config.pids,
                      "timeout_seconds": config.timeout_seconds, "stdout_bytes": config.stdout_limit,
                      "stderr_bytes": config.stderr_limit}
            if state.get("Running") or not state.get("StartedAt") or state["StartedAt"].startswith("0001-"):
                raise DockerControlError("START_FAILED", "执行容器未能正常启动。")
            status = ("OUTPUT_LIMIT_EXCEEDED" if reason == "output" else "TIME_LIMIT_EXCEEDED" if reason == "timeout"
                      else "SYSTEM_ERROR" if reason else "MEMORY_LIMIT_EXCEEDED" if state.get("OOMKilled")
                      else "SUCCESS" if state.get("ExitCode") == 0 else "RUNTIME_ERROR")
            message = {"TIME_LIMIT_EXCEEDED": "代码运行超过墙钟时间上限。", "OUTPUT_LIMIT_EXCEEDED": "标准输出或错误输出超过上限。",
                       "MEMORY_LIMIT_EXCEEDED": "容器因超过内存上限被终止。", "SYSTEM_ERROR": "执行通信失败。"}.get(status)
            # Byte slicing may end inside a multibyte character; ignore only that
            # incomplete tail so decoded output cannot exceed the byte budget.
            result = SandboxResult(status, out.decode("utf-8", errors="ignore"), err.decode("utf-8", errors="ignore"),
                                   state.get("ExitCode"), elapsed, message, status if status != "SUCCESS" else None, limits=limits)
            if status == "SYSTEM_ERROR":
                result.stdout = result.stderr = ""
        except ExecutionBusy:
            raise
        except DockerControlError as error:
            if error.code == "CLEANUP_UNCONFIRMED":
                self._cleanup_failed = True
            result = SandboxResult("SYSTEM_ERROR", error_code=error.code, error_message=error.message,
                                   cleanup_confirmed=not self._cleanup_failed)
        except Exception:
            # Do not return Docker stderr, command args, paths or Python tracebacks.
            result = SandboxResult("SYSTEM_ERROR", error_code="EXECUTION_FAILED", error_message="执行服务发生系统异常，请稍后重试。")
        finally:
            if name:
                clean = self._remove(name)
                if clean and not create_pending:
                    lock.write()
                    if guard:
                        guard.stop()
                else:
                    # A missing container immediately after an uncertain create
                    # does not prove the daemon cannot finish creating it later.
                    # Keep its guard, journal and cross-process lock alive.
                    result = SandboxResult("SYSTEM_ERROR", error_code="CLEANUP_UNCONFIRMED", error_message="执行资源尚未确认清理，执行服务已关闭。", cleanup_confirmed=False)
                    self._cleanup_failed = True
            if lock:
                if self._cleanup_failed:
                    self._retained_lock = lock
                else:
                    lock.close()
            self._run_lock.release()
        return result
