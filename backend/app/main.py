import json
import logging
import time
import uuid
from functools import lru_cache
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy import text, select
from .database import SessionLocal
from .models import User
from sqlalchemy.exc import IntegrityError, OperationalError, TimeoutError
from . import admin, auth, projects
from .config import get_settings
from .database import get_db
from .security import require_csrf
from .hosts import SearchroomTrustedHostMiddleware
from .body_limit import RequestBodyLimitMiddleware

settings = get_settings()
if settings.production:
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("searchroom").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app):
    if settings.production:
        ensure_production_database()
    yield


def ensure_production_database():
    # Legacy fixture credentials must never reach a production release.
    with SessionLocal() as db:
        if db.scalar(
            select(User.id).where(User.email.in_(LEGACY_DEMO_EMAILS)).limit(1)
        ):
            raise RuntimeError(
                "Production startup refused: remove legacy demo accounts from the target database."
            )


LEGACY_DEMO_EMAILS = (
    "admin@example.com",
    "recruiter@example.com",
    "client@example.com",
)


app = FastAPI(
    title="Searchroom API",
    debug=False,
    lifespan=lifespan,
    version="0.2.0",
    docs_url=None if settings.production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.production else "/openapi.json",
)
app.add_middleware(
    SearchroomTrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts.split(","),
    railway=bool(settings.railway_service_id),
)
app.add_middleware(RequestBodyLimitMiddleware)
# Same-origin frontend/API: intentionally no CORS middleware or cross-origin grants.
# Cookie writes additionally require the exact configured HTTPS Origin and CSRF token.
for router in (auth.router, admin.router, projects.router):
    app.include_router(router, prefix="/api/v1", dependencies=[Depends(require_csrf)])


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    log_failure(request, exc, "unexpected_integrity_error")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected database error occurred."},
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


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # FastAPI's default errors echo invalid inputs, which can include passwords.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
                for error in exc.errors()
            ]
        },
    )


@app.middleware("http")
async def headers(request: Request, call_next):
    started = time.monotonic()
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception as exc:
        if not settings.production:
            raise
        # Do not log exceptions/SQL parameters or return framework tracebacks.
        log_failure(request, exc, "unexpected_application_error")
        response = JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected error occurred. Contact support with the request ID.",
                "request_id": request_id,
            },
        )
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
    logging.getLogger("searchroom").info(
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


def log_failure(request: Request, exc: Exception | None, category: str) -> None:
    if not settings.production:
        return
    route = request.scope.get("route")
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    event = {
        "event": "request_failed",
        "request_id": getattr(request.state, "request_id", "unknown"),
        "route": getattr(route, "path", "unmatched"),
        "exception_class": type(exc).__name__ if exc else "Exception",
        "category": category,
    }
    if isinstance(sqlstate, str) and len(sqlstate) == 5:
        event["sqlstate"] = sqlstate
    logging.getLogger("searchroom").error(json.dumps(event))


@app.get("/api/v1/health")
@app.get("/api/v1/health/live")
def live():
    return {"status": "ok"}


@app.get("/api/v1/health/ready")
def ready(db=Depends(get_db)):
    try:
        database_heads = frozenset(
            db.scalars(text("SELECT version_num FROM alembic_version")).all()
        )
        repository_heads = repository_migration_heads()
    except Exception:
        raise HTTPException(503, "Service is not ready.") from None
    if not database_heads or database_heads != repository_heads:
        raise HTTPException(503, "Service is not ready.")
    return {"status": "ready"}


@lru_cache(maxsize=1)
def repository_migration_heads() -> frozenset[str]:
    """Read repository heads once; database state is checked on every request."""
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    return frozenset(ScriptDirectory.from_config(config).get_heads())


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
