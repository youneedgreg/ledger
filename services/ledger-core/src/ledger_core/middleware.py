import re
import time
import uuid

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "request-id"
# The gateway sets this header. Anything else is replaced, so that untrusted
# input can't end up in the logs.
_VALID_REQUEST_ID = re.compile(r"^req_[A-Za-z0-9-]{1,64}$")

log = structlog.get_logger()


def _request_id(scope: Scope) -> str:
    candidate = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
    if _VALID_REQUEST_ID.fullmatch(candidate):
        return candidate
    return f"req_{uuid.uuid4()}"


class RequestContextMiddleware:
    """Gives each request an ID, echoes it in the response, and logs the outcome."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope)
        status_code = 500
        started = time.perf_counter()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            try:
                await self.app(scope, receive, send_with_request_id)
            finally:
                log.info(
                    "request completed",
                    method=scope["method"],
                    path=scope["path"],
                    status=status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                )
