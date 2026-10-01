"""Keep the application origin strict while accepting Railway readiness probes."""

from starlette.datastructures import Headers
from starlette.middleware.trustedhost import TrustedHostMiddleware


class SearchroomTrustedHostMiddleware(TrustedHostMiddleware):
    def __init__(self, app, *, railway=False, **kwargs):
        super().__init__(app, **kwargs)
        self.railway = railway

    async def __call__(self, scope, receive, send):
        if (
            self.railway
            and scope["type"] == "http"
            and scope["method"] == "GET"
            and scope["path"] == "/api/v1/health/ready"
            and Headers(scope=scope).get("host") == "healthcheck.railway.app"
        ):
            # Run the actual database readiness handler; do not synthesize success.
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)
