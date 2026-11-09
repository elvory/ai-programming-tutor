"""Server-owned execution budgets. Never reads dotenv or model credentials."""
from dataclasses import dataclass
import math
import os
import re


@dataclass(frozen=True)
class ExecutionConfig:
    enabled: bool = False
    image: str = "python:3.12-slim"
    memory_mb: int = 128
    cpu: float = 0.5
    pids: int = 64
    timeout_seconds: float = 3.0
    prepare_timeout_seconds: float = 15.0
    stdout_limit: int = 65536
    stderr_limit: int = 65536
    code_limit: int = 65536
    body_limit: int = 524288
    max_concurrent: int = 1
    tmpfs_mb: int = 16

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError("Execution enabled flag must be boolean")
        if not isinstance(self.image, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@-]{0,254}", self.image):
            raise ValueError("Invalid server-owned execution image")
        for name, lower, upper in (("memory_mb", 32, 1024), ("pids", 8, 256),
                                   ("stdout_limit", 128, 1048576), ("stderr_limit", 128, 1048576),
                                   ("code_limit", 128, 262144), ("body_limit", 1024, 2097152),
                                   ("tmpfs_mb", 1, 64)):
            value = getattr(self, name)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError("Invalid execution budget: " + name)
        for name, lower, upper in (("cpu", 0.1, 2.0), ("timeout_seconds", 0.05, 30),
                                   ("prepare_timeout_seconds", 1, 60)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError("Invalid execution budget: " + name)
        # M1 is deliberately serial, including between multiple local API workers.
        if type(self.max_concurrent) is not int or self.max_concurrent != 1:
            raise ValueError("M1 supports exactly one concurrent execution")

    @classmethod
    def from_env(cls, environ=None):
        environ = os.environ if environ is None else environ
        values = {}
        flag = environ.get("AI_TUTOR_EXECUTION_ENABLED", "0")
        if flag not in ("0", "1"):
            raise ValueError("AI_TUTOR_EXECUTION_ENABLED must be 0 or 1")
        values["enabled"] = flag == "1"
        for name in ("image", "memory_mb", "cpu", "pids", "timeout_seconds", "prepare_timeout_seconds",
                     "stdout_limit", "stderr_limit", "code_limit", "body_limit", "max_concurrent", "tmpfs_mb"):
            raw = environ.get("AI_TUTOR_EXECUTION_" + name.upper())
            if raw is not None:
                converter = str if name == "image" else float if name in ("cpu", "timeout_seconds", "prepare_timeout_seconds") else int
                try:
                    values[name] = converter(raw)
                except (ValueError, TypeError):
                    raise ValueError("Invalid execution setting: " + name) from None
        return cls(**values)
