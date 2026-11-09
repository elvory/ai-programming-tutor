"""M1 public contracts; execution success is separate from example correctness."""
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


ExecutionStatus = Literal[
    "SUCCESS", "RUNTIME_ERROR", "TIME_LIMIT_EXCEEDED", "OUTPUT_LIMIT_EXCEEDED",
    "MEMORY_LIMIT_EXCEEDED", "COMPILE_ERROR", "SYSTEM_ERROR",
]


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: int = Field(gt=0, strict=True)
    language: Literal["python"]
    code: str = Field(strict=True, min_length=1, max_length=65536)
    request_id: UUID = Field(default_factory=uuid4)

    @field_validator("code")
    @classmethod
    def valid_source(cls, value):
        try:
            size = len(value.encode("utf-8"))
        except UnicodeEncodeError:
            raise ValueError("代码必须是有效的 UTF-8 文本。") from None
        if not value.strip() or "\x00" in value or size > 65536:
            raise ValueError("代码为空、包含空字符或超过 64 KiB。")
        return value


class ExecutionResponse(BaseModel):
    status: ExecutionStatus
    stdout: str
    stderr: str
    exit_code: Optional[int]
    execution_time_ms: Optional[float]
    language: Literal["python"] = "python"
    problem_id: int
    request_id: str
    error_message: Optional[str]
    error_code: Optional[str]
    cleanup_confirmed: bool
    limits: dict[str, Any] = Field(default_factory=dict)
    judge: dict[str, Any]
