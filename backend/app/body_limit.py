"""ASGI request-body limiting that preserves the downstream receive stream."""

from starlette.datastructures import Headers
from starlette.responses import JSONResponse


MAX_REQUEST_BODY = 1024 * 1024
MAX_CV_UPLOAD_BODY = 6 * 1024 * 1024
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class RequestBodyLimitMiddleware:
    def __init__(self, app, max_bytes: int = MAX_REQUEST_BODY):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return

        limit = (
            MAX_CV_UPLOAD_BODY
            if scope.get("path", "").endswith("/candidates/extract")
            else self.max_bytes
        )
        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > limit:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                # Let the server/framework handle malformed transport metadata.
                pass

        consumed = 0
        messages = []
        while True:
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > limit:
                    await self._reject(scope, receive, send)
                    return
            messages.append(message)
            if message["type"] == "http.disconnect" or not message.get(
                "more_body", False
            ):
                break

        async def replay_receive():
            if messages:
                return messages.pop(0)
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(scope, receive, send):
        response = JSONResponse(
            status_code=413, content={"detail": "Request is too large."}
        )
        await response(scope, receive, send)
