"""Real concurrent transactions in a disposable PostgreSQL schema."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import secrets
import threading
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
from app.database import Base, get_db
from app.main import app
from app.models import (
    Agency,
    ClientOrg,
    User,
    Project,
    Membership,
    Invitation,
    WebSession,
    Message,
    ReadMarker,
    now,
)
from app.security import digest, csrf_value, throttle
from conftest import TEST_URL


@pytest.fixture
def parallel_world(engine, password_hash):
    schema = "race_" + secrets.token_hex(6)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    isolated = create_engine(
        TEST_URL,
        connect_args={"options": f"-c search_path={schema} -c lock_timeout=5000"},
        pool_size=5,
        max_overflow=0,
    )
    Base.metadata.create_all(isolated)
    with Session(isolated, expire_on_commit=False) as db:
        agency = Agency(name="Race", retention_days=90)
        db.add(agency)
        db.flush()
        org = ClientOrg(name="Client", agency_id=agency.id)
        db.add(org)
        db.flush()
        staff = User(
            name="Admin",
            email="race-admin@example.com",
            role="admin",
            agency_id=agency.id,
            password_hash=password_hash,
            email_verified=True,
            mfa_enabled=True,
        )
        user = User(
            name="Client",
            email="race-client@example.com",
            role="client",
            agency_id=agency.id,
            client_org_id=org.id,
            password_hash=password_hash,
            email_verified=True,
        )
        db.add_all([staff, user])
        db.flush()
        project = Project(title="Race", agency_id=agency.id, client_org_id=org.id)
        db.add(project)
        db.flush()
        db.add(Membership(project_id=project.id, user_id=user.id))
        tokens = {}
        for name, person in [("admin", staff), ("client", user)]:
            token = secrets.token_urlsafe(32)
            tokens[name] = {
                "Cookie": "searchroom_session=" + token,
                "X-CSRF-Token": csrf_value(token),
                "Origin": "http://localhost:5173",
            }
            db.add(
                WebSession(
                    token_hash=digest(token),
                    user_id=person.id,
                    expires_at=now() + timedelta(days=1),
                    idle_expires_at=now() + timedelta(hours=1),
                    mfa_complete=True,
                )
            )
        invite_token = secrets.token_urlsafe(32)
        invite = Invitation(
            token_hash=digest(invite_token),
            agency_id=agency.id,
            client_org_id=org.id,
            project_id=project.id,
            email=user.email,
            role="client",
            expires_at=now() + timedelta(days=7),
        )
        db.add(invite)
        db.commit()
        ids = {"project": project.id, "client": user.id, "invite": invite_token}
    previous = dict(app.dependency_overrides)

    def session():
        with Session(isolated, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_db] = session
    yield isolated, tokens, ids
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    isolated.dispose()
    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))


def concurrent(*jobs):
    barrier = threading.Barrier(len(jobs))

    def run(job):
        barrier.wait()
        with TestClient(app) as client:
            return job(client)

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(run, jobs))


def test_accept_racing_removal_cannot_restore_access(parallel_world):
    engine, headers, ids = parallel_world
    results = concurrent(
        lambda c: c.post(
            "/api/v1/auth/accept-invitation",
            headers=headers["client"],
            json={"token": ids["invite"]},
        ),
        lambda c: c.delete(
            f"/api/v1/projects/{ids['project']}/members/{ids['client']}",
            headers=headers["admin"],
        ),
    )
    assert results[0].status_code in (200, 400), results[0].text
    assert results[1].status_code == 204, results[1].text
    with Session(engine) as db:
        assert db.get(Membership, (ids["project"], ids["client"])) is None


def test_concurrent_submission_key_creates_one_message(parallel_world):
    engine, h, ids = parallel_world
    headers = {**h["client"], "Idempotency-Key": str(uuid.uuid4())}

    def send(c):
        return c.post(
            f"/api/v1/projects/{ids['project']}/messages",
            headers=headers,
            json={"body": "Once"},
        )

    responses = concurrent(send, send)
    assert [r.status_code for r in responses] == [201, 201], [r.text for r in responses]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    with Session(engine) as db:
        assert len(list(db.scalars(select(Message)))) == 1


def test_two_editors_cannot_overwrite_same_version(parallel_world):
    engine, h, ids = parallel_world

    def edit(c):
        return c.put(
            f"/api/v1/projects/{ids['project']}",
            headers=h["admin"],
            json={"title": "Edited", "version": 1},
        )

    results = concurrent(edit, edit)
    assert sorted(r.status_code for r in results) == [200, 409], [
        r.text for r in results
    ]


def test_rate_limit_is_shared_across_connections(parallel_world):
    engine, _, _ = parallel_world

    def attempt(_):
        from fastapi import HTTPException

        with Session(engine) as db:
            try:
                throttle(db, "shared-limit", 1)
                return 200
            except HTTPException as e:
                return e.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [200, 429]


def test_concurrent_first_read_markers_are_monotonic(parallel_world):
    engine, h, ids = parallel_world
    with Session(engine) as db:
        rows = [
            Message(
                project_id=ids["project"], author_id=ids["client"], body="Read test"
            )
            for _ in range(2)
        ]
        db.add_all(rows)
        db.flush()
        values = [r.id for r in rows]
        for session in db.scalars(
            select(WebSession).where(WebSession.user_id == ids["client"])
        ):
            session.delivered = {str(ids["project"]): max(values)}
        db.commit()
    results = concurrent(
        *[
            lambda c, n=n: c.put(
                f"/api/v1/projects/{ids['project']}/messages/read",
                headers=h["client"],
                json={"last_message_id": n},
            )
            for n in values
        ]
    )
    assert [r.status_code for r in results] == [204, 204], [r.text for r in results]
    with Session(engine) as db:
        assert db.get(
            ReadMarker, (ids["project"], ids["client"])
        ).last_message_id == max(values)
