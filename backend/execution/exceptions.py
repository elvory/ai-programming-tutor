"""Sanitized execution control failures; never contain Docker stderr."""


class ExecutionFailure(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class ExecutionBusy(ExecutionFailure):
    def __init__(self):
        super().__init__("EXECUTION_BUSY", "执行服务正在处理其他请求，请稍后重试。")


class DockerControlError(ExecutionFailure):
    def __init__(self, code="DOCKER_UNAVAILABLE", message="Docker 执行服务暂不可用，请检查 Docker Desktop。"):
        super().__init__(code, message)
