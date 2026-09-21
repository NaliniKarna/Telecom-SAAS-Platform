"""Request-context middleware: assigns a request id and binds it for logging.

Implemented as a raw ASGI middleware, NOT starlette.middleware.base.
BaseHTTPMiddleware. This is a deliberate fix, not a style choice:

BaseHTTPMiddleware wraps the downstream app in an anyio task group and
re-raises exceptions through `call_next()` in a way that is well documented
to be incompatible with FastAPI's registered exception handlers. Even when
`app.exception_handler(Exception)` successfully converts a crash into a
normal JSONResponse, that response can still fail to propagate back through
BaseHTTPMiddleware as a real response — it comes back out as a raised
exception instead. CORSMiddleware (which sits outside this middleware) never
gets a chance to attach Access-Control-* headers to whatever the outermost
error handler ends up sending, so the browser reports "blocked by CORS
policy" for what is actually an unrelated server-side crash.

This is NOT specific to any one route or bug — reproduced with a completely
unrelated, deliberately planted crash, confirming every endpoint in the API
was exposed to this failure mode for any unhandled exception. The fix
mirrors Starlette's own guidance: avoid BaseHTTPMiddleware when reliable
exception propagation matters; use a raw ASGI middleware instead.
"""
import uuid
from contextvars import ContextVar

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        rid = headers.get(b"x-request-id", b"").decode() or str(uuid.uuid4())

        # Request.state wraps scope["state"] directly (Starlette's State
        # class is a thin attribute-access wrapper over this same dict), so
        # setting it here is exactly equivalent to `request.state.request_id
        # = rid` downstream, without needing a Request object at all.
        scope.setdefault("state", {})
        scope["state"]["request_id"] = rid
        token = request_id_ctx.set(rid)

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", rid.encode()),
                ]
            await send(message)

        try:
            # Added on every response path, including ones that end in an
            # unhandled exception being converted to a 500 by the outer
            # error middleware — strictly better than the previous
            # BaseHTTPMiddleware version, which only added this header on
            # the success path.
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_ctx.reset(token)