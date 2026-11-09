"""Local-only execution capability and bounded request transport."""
import ipaddress
import secrets

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .schemas import ExecutionRequest, ExecutionResponse
from .service import ExecutionRejected


_HOSTS = {"127.0.0.1:8000", "localhost:8000", "127.0.0.1:5173", "localhost:5173", "[::1]:8000"}
_ORIGINS = {f"http://{host}" for host in _HOSTS}


def _local_request(scope):
    client = scope.get("client")
    try:
        if not client or not ipaddress.ip_address(client[0]).is_loopback:
            return False
    except ValueError:
        return False
    headers = {key.lower(): value for key, value in scope.get("headers", [])}
    host = headers.get(b"host", b"").decode("latin-1").lower()
    if host not in _HOSTS:
        return False
    origin = headers.get(b"origin")
    if origin is not None and origin.decode("latin-1") not in _ORIGINS:
        return False
    if headers.get(b"sec-fetch-site", b"").lower() == b"cross-site":
        return False
    return True


class ExecutionBoundaryMiddleware:
    """Gate only new endpoints; bound even chunked bodies before JSON parsing."""

    def __init__(self, app, service, token):
        self.app = app
        self.service = service
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/execution/"):
            await self.app(scope, receive, send)
            return

        async def reject(status, code, detail):
            response = JSONResponse(status_code=status, content={"detail": detail, "error_code": code},
                                    headers={"Cache-Control": "no-store"})
            await response(scope, receive, send)

        if not _local_request(scope):
            await reject(403, "LOCAL_ACCESS_REQUIRED", "代码执行仅允许本机可信页面访问。")
            return
        if scope["method"] == "POST":
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            supplied = headers.get(b"x-execution-token", b"")
            if not secrets.compare_digest(supplied, self.token.encode("ascii")):
                await reject(403, "EXECUTION_PERMISSION_REQUIRED", "请先获取本机执行会话，再发起代码运行。")
                return
            if headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower() != b"application/json":
                await reject(415, "JSON_REQUIRED", "执行请求必须使用 JSON。")
                return
            declared = headers.get(b"content-length")
            if declared is not None:
                try:
                    length = int(declared)
                except ValueError:
                    length = -1
                if length < 0:
                    await reject(400, "INVALID_CONTENT_LENGTH", "请求长度不正确。")
                    return
                if length > self.service.config.body_limit:
                    await reject(413, "REQUEST_TOO_LARGE", "执行请求超过服务端大小限制。")
                    return
            chunks = []
            received = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                received += len(chunk)
                if received > self.service.config.body_limit:
                    await reject(413, "REQUEST_TOO_LARGE", "执行请求超过服务端大小限制。")
                    return
                chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            body = b"".join(chunks)
            consumed = False

            async def bounded_receive():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            await self.app(scope, bounded_receive, send)
            return
        await self.app(scope, receive, send)


def install_execution(app, service):
    token = secrets.token_urlsafe(32)
    app.add_middleware(ExecutionBoundaryMiddleware, service=service, token=token)
    router = APIRouter(prefix="/api/execution")

    @router.get("/session")
    def session():
        return JSONResponse({"token": token, "capabilities": service.capabilities()},
                            headers={"Cache-Control": "no-store", "Vary": "Origin"})

    @router.post("/run", response_model=ExecutionResponse)
    def run(payload: ExecutionRequest):
        try:
            return service.run(payload)
        except ExecutionRejected as error:
            headers = {"Retry-After": "1"} if error.status_code == 429 else {}
            return JSONResponse(status_code=error.status_code,
                                content={"detail": error.message, "error_code": error.error_code}, headers=headers)

    app.include_router(router)
