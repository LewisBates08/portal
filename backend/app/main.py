import json
import logging
import time
import uuid
from pathlib import Path
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, TimeoutError
from . import admin, auth, projects
from .config import get_settings
from .database import get_db
from .security import require_csrf

settings = get_settings()
app = FastAPI(
    title="Searchroom API",
    version="0.2.0",
    docs_url=None if settings.production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.production else "/openapi.json",
)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts.split(",")
)
for router in (auth.router, admin.router, projects.router):
    app.include_router(router, prefix="/api/v1", dependencies=[Depends(require_csrf)])


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "This record conflicts with another change. Refresh and try again."
        },
    )


@app.exception_handler(OperationalError)
@app.exception_handler(TimeoutError)
async def unavailable(request, exc):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "The database is temporarily unavailable. Please retry shortly."
        },
        headers={"Retry-After": "5"},
    )


@app.middleware("http")
async def headers(request: Request, call_next):
    started = time.monotonic()
    request_id = str(uuid.uuid4())
    # Buffer at most 1 MiB, including chunked requests. Never log the body.
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        length = 0
        chunks = []
        async for chunk in request.stream():
            length += len(chunk)
            if length > 1048576:
                return JSONResponse(
                    status_code=413, content={"detail": "Request is too large."}
                )
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
            "X-Request-ID": request_id,
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cache-Control": "public, max-age=31536000, immutable"
            if request.url.path.startswith("/assets/") and response.status_code == 200
            else "no-store",
        }
    )
    if settings.production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
    route = request.scope.get("route")
    logging.getLogger("searchroom").warning(
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        )
    )
    return response


@app.get("/api/v1/health")
@app.get("/api/v1/health/live")
def live():
    return {"status": "ok"}


@app.get("/api/v1/health/ready")
def ready(db=Depends(get_db)):
    revision = db.scalar(text("SELECT version_num FROM alembic_version"))
    if revision != "readiness_20260913":
        raise HTTPException(503, "Database migration is required.")
    return {"status": "ready"}


if settings.static_dir:
    root = Path(settings.static_dir).resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "API route not found.")
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            raise HTTPException(404)
        if target.is_file():
            return FileResponse(target)
        if path.startswith("assets/") or "." in path.rsplit("/", 1)[-1]:
            raise HTTPException(404)
        return FileResponse(root / "index.html")
