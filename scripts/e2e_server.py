"""HTTPS smoke-test server; refuses any database not explicitly ending in _test."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
url = os.environ.get("TEST_DATABASE_URL", "")
if not make_url(url).database.endswith("_test"):
    raise SystemExit("TEST_DATABASE_URL must name an isolated _test database.")
os.environ.update(
    DATABASE_URL=url,
    ENVIRONMENT="test",
    FRONTEND_URL="https://localhost:8443",
    STATIC_DIR=str(root / "frontend/dist"),
    AUTH_RATE_LIMIT="10000",
)
import secrets

os.environ.setdefault("JWT_SECRET", secrets.token_urlsafe(48))
sys.path.insert(0, str(root / "backend"))
from app.operations import migrate

migrate()
from browser_fixture import seed_browser_fixture

seed_browser_fixture(os.environ["E2E_PASSWORD"])
from app.database import SessionLocal
from app.models import User
from app.security import hash_password
from sqlalchemy import select

with SessionLocal.begin() as db:
    for user in db.scalars(
        select(User).where(
            User.email.in_(
                ["admin@example.com", "recruiter@example.com", "client@example.com"]
            )
        )
    ):
        user.active = True
        user.email_verified = True
        user.password_hash = hash_password(os.environ["E2E_PASSWORD"])
    admin = db.scalar(select(User).where(User.email == "admin@example.com"))
    admin.mfa_enabled = False
    admin.mfa_secret = None
    admin.mfa_last_step = 0
    admin.recovery_hashes = []
if "--prepare-only" in sys.argv:
    print("Browser fixtures prepared; start the runtime container separately.")
    raise SystemExit(0)

with tempfile.TemporaryDirectory() as folder:
    key, cert = str(Path(folder) / "key.pem"), str(Path(folder) / "cert.pem")
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            key,
            "-out",
            cert,
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8443,
        ssl_keyfile=key,
        ssl_certfile=cert,
        access_log=False,
    )
