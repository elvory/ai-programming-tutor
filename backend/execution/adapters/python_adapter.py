"""M1: one public Two Sum example, independently checked outside the container.

The bootstrap is transported as a fixed argument to the container interpreter.
It never runs on the host. The result envelope is an untrusted candidate channel,
not authentication of a verdict, runtime, or memory measurement.
"""
import copy
import json
import math


RESULT_PREFIX = "\x1eAI_TUTOR_RESULT_V1:"

BOOTSTRAP = r'''
import json
import os
import resource
import sys
from typing import List, Optional

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
_write = os.write
_dumps = json.dumps
_compile = compile
_exec = exec
_prefix = "\x1eAI_TUTOR_RESULT_V1:"

def emit(kind, **fields):
    payload = _dumps(dict(kind=kind, **fields), ensure_ascii=True, allow_nan=False)
    _write(1, ("\n" + _prefix + payload + "\n").encode("utf-8"))

payload = json.loads(sys.stdin.buffer.read(524289))
try:
    compiled = _compile(payload["code"], "solution.py", "exec")
except (SyntaxError, ValueError, OverflowError) as error:
    emit("compile_error", message=str(error))
    sys.exit(1)

try:
    scope = {"__name__": "__submission__", "List": List, "Optional": Optional}
    _exec(compiled, scope)
    data = payload["input"]
    value = scope["Solution"]().twoSum(data["nums"], data["target"])
    emit("return", value=value)
except BaseException as error:
    emit("runtime_error", message=type(error).__name__ + ": " + str(error))
    sys.exit(1)
'''


def _invalid_constant(_value):
    raise ValueError("non-finite JSON")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _bounded_value(value):
    pending = [(value, 0)]
    count = 0
    while pending:
        current, depth = pending.pop()
        count += 1
        if depth > 16 or count > 8192:
            return False
        if isinstance(current, float) and not math.isfinite(current):
            return False
        if isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)
        elif isinstance(current, dict):
            pending.extend((child, depth + 1) for child in current.values())
    return True


def parse_result(stdout, stderr, exit_code):
    """Validate a bounded, untrusted transport, never trust a reported verdict."""
    lines = stdout.split("\n")
    envelopes = [line for line in lines if line.startswith(RESULT_PREFIX)]
    visible = "\n".join(line for line in lines if not line.startswith(RESULT_PREFIX))
    result = {"status": "RUNTIME_ERROR", "stdout": visible, "stderr": stderr,
              "candidate": None, "error_message": "程序未返回有效的函数执行结果。",
              "error_code": "INVALID_RESULT_PROTOCOL"}
    if len(envelopes) != 1:
        return result
    try:
        envelope = json.loads(envelopes[0][len(RESULT_PREFIX):], parse_constant=_invalid_constant,
                              object_pairs_hook=_unique_object)
    except (ValueError, TypeError, RecursionError):
        return result
    if not isinstance(envelope, dict) or not _bounded_value(envelope):
        return result
    kind = envelope.get("kind")
    if kind == "return" and exit_code == 0 and set(envelope) == {"kind", "value"}:
        result.update(status="SUCCESS", candidate=envelope["value"],
                      error_message=None, error_code=None)
    elif kind in ("compile_error", "runtime_error") and exit_code != 0:
        result.update(status="COMPILE_ERROR" if kind == "compile_error" else "RUNTIME_ERROR",
                      error_message="Python 语法检查失败。" if kind == "compile_error" else "Python 程序运行失败。",
                      error_code="PYTHON_SYNTAX_ERROR" if kind == "compile_error" else "PYTHON_RUNTIME_ERROR")
        # This text is student-controlled and already stream-size bounded.
        message = envelope.get("message")
        if isinstance(message, str):
            result["stderr"] = (stderr + "\n" + message).strip()[:65536]
    return result


class TwoSumAdapter:
    """The existing catalog's single public example, not a hidden judge suite."""
    problem_id = 1
    slug = "two-sum"
    suite_version = "two-sum-public-example-v1"
    _input = {"nums": [4, 1, 6], "target": 7}
    _expected = [1, 2]

    @property
    def case_input(self):
        return copy.deepcopy(self._input)

    def not_run(self):
        return self._report(None, False, "not_run", "not_run", executed=0)

    def judge(self, candidate):
        error = None
        if not isinstance(candidate, list) or len(candidate) != 2:
            error = "invalid_index_count"
        elif any(type(index) is not int for index in candidate):
            error = "invalid_index_type"
        elif any(index < 0 or index >= len(self._input["nums"]) for index in candidate):
            error = "index_out_of_range"
        elif candidate[0] == candidate[1]:
            error = "reused_index"
        elif sum(self._input["nums"][index] for index in candidate) != self._input["target"]:
            error = "wrong_sum"
        passed = error is None
        return self._report(candidate, passed, "passed" if passed else "failed", error, executed=1)

    def _report(self, actual, passed, status, error, *, executed):
        return {"scope": "public_examples", "suite_version": self.suite_version,
                "passed": int(passed), "total": 1, "executed": executed,
                "all_passed": passed, "official_accepted": False,
                "cases": [{"case_id": "example-1", "input": self.case_input,
                           "expected": self._expected[:], "actual": actual,
                           "passed": passed, "status": status, "error_type": error}]}


def get_adapter(problem_id, slug="two-sum"):
    if type(problem_id) is not int or problem_id != 1 or slug != "two-sum":
        raise ValueError("M1 暂仅支持 Python 两数之和的公开示例运行，当前题目尚未适配。")
    return TwoSumAdapter()
