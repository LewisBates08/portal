"""Integration tests use a dedicated PostgreSQL database and rolled-back transactions."""

import os
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

TEST_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_URL:
    raise RuntimeError(
        "Set TEST_DATABASE_URL to a separate PostgreSQL database ending in _test."
    )
url = make_url(TEST_URL)
if (
    url.get_backend_name() != "postgresql"
    or not url.database
    or not url.database.endswith("_test")
):
    raise RuntimeError(
        "Tests require a separate PostgreSQL database whose name ends in _test."
    )
os.environ["DATABASE_URL"] = TEST_URL
os.environ["JWT_SECRET"] = "integration-tests-only-secret-at-least-32-characters"
os.environ["AUTH_RATE_LIMIT"] = "10000"
os.environ["ENVIRONMENT"] = "test"
from app.database import get_db
from app.main import app
from app.models import Agency, ClientOrg, Membership, Project, User
from app.security import passwords, csrf_value, digest
from app.models import WebSession, now
from datetime import timedelta
import secrets
import uuid


@pytest.fixture(scope="session")
def engine():
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")
    engine = create_engine(TEST_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as session:
            yield session
        transaction.rollback()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db

    class PortalClient(TestClient):
        def request(self, method, url, **kwargs):
            headers = dict(kwargs.pop("headers", {}) or {})
            headers.setdefault("Origin", "http://localhost:5173")
            headers.setdefault("Idempotency-Key", str(uuid.uuid4()))
            return super().request(method, url, headers=headers, **kwargs)

    with PortalClient(app) as client:
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        client.headers["X-CSRF-Token"] = csrf
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def password_hash():
    return passwords.hash("PasswordForTests!")


@pytest.fixture
def world(db, password_hash):
    agency = Agency(name="Agency A", retention_days=180)
    other = Agency(name="Agency B", retention_days=180)
    db.add_all([agency, other])
    db.flush()
    org = ClientOrg(name="Client A", agency_id=agency.id)
    other_org = ClientOrg(name="Client B", agency_id=other.id)
    db.add_all([org, other_org])
    db.flush()
    roles = {}
    for name, role, a, c in [
        ("admin", "admin", agency, None),
        ("recruiter", "recruiter", agency, None),
        ("client", "client", agency, org),
        ("colleague", "client", agency, org),
        ("outsider", "admin", other, None),
    ]:
        u = User(
            name=name,
            email=f"fixture-{name}@example.com",
            role=role,
            agency_id=a.id,
            client_org_id=c.id if c else None,
            password_hash=password_hash,
            email_verified=True,
            mfa_enabled=role == "admin",
        )
        db.add(u)
        db.flush()
        roles[name] = u
    p = Project(title="Search A", agency_id=agency.id, client_org_id=org.id)
    p2 = Project(
        title="Other search, same agency", agency_id=agency.id, client_org_id=org.id
    )
    foreign = Project(
        title="Foreign search", agency_id=other.id, client_org_id=other_org.id
    )
    db.add_all([p, p2, foreign])
    db.flush()
    db.add_all(
        [
            Membership(project_id=p.id, user_id=roles["recruiter"].id),
            Membership(project_id=p.id, user_id=roles["client"].id),
        ]
    )
    db.commit()
    return dict(
        **roles,
        agency=agency,
        org=org,
        other_org=other_org,
        project=p,
        second=p2,
        foreign=foreign,
    )


@pytest.fixture
def auth(db, world):
    # Resource tests use independent browser sessions; authentication has its own tests.
    def login(role):
        token = secrets.token_urlsafe(32)
        db.add(
            WebSession(
                token_hash=digest(token),
                user_id=world[role].id,
                expires_at=now() + timedelta(days=7),
                idle_expires_at=now() + timedelta(minutes=30),
                mfa_complete=True,
            )
        )
        db.commit()
        return {
            "Cookie": "searchroom_session=" + token,
            "X-CSRF-Token": csrf_value(token),
        }

    return login
