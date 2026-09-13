"""20-user pilot load check against the local HTTPS test server; no production targets."""

import concurrent.futures
from datetime import timedelta
import json
import os
import secrets
import time
import httpx
from sqlalchemy import select, func
from sqlalchemy.engine import make_url

url = os.environ["TEST_DATABASE_URL"]
if not make_url(url).database.endswith("_test"):
    raise SystemExit("Only isolated _test databases are allowed.")
os.environ["DATABASE_URL"] = url
os.environ.setdefault("JWT_SECRET", "e2e-only-not-a-production-signing-secret-12345678")
from app.database import SessionLocal
from app.models import User, Project, Message, WebSession, Membership, now
from app.security import digest, csrf_value

with SessionLocal.begin() as db:
    owner = db.scalar(select(User).where(User.email == "client@example.com"))
    project = db.scalar(
        select(Project).where(
            Project.agency_id == owner.agency_id, Project.title == "Head of Product"
        )
    )
    recruiter = db.scalar(select(User).where(User.email == "recruiter@example.com"))
    count = db.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.project_id == project.id)
    )
    db.add_all(
        [
            Message(
                project_id=project.id,
                author_id=recruiter.id,
                body=f"Fictional load fixture {i}",
            )
            for i in range(max(0, 10000 - count))
        ]
    )
    sessions = []
    for i in range(20):
        email = f"load-{i}@example.com"
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(
                name=f"Load {i}",
                email=email,
                password_hash=owner.password_hash,
                role="client",
                agency_id=owner.agency_id,
                client_org_id=owner.client_org_id,
                email_verified=True,
            )
            db.add(user)
            db.flush()
            db.add(Membership(project_id=project.id, user_id=user.id))
        token = secrets.token_urlsafe(32)
        sessions.append(token)
        db.add(
            WebSession(
                token_hash=digest(token),
                user_id=user.id,
                expires_at=now() + timedelta(hours=1),
                idle_expires_at=now() + timedelta(hours=1),
                mfa_complete=True,
            )
        )
    pid = project.id


def work(token):
    reads = []
    writes = []
    with httpx.Client(
        base_url="https://localhost:8443",
        verify=False,
        timeout=15,
        headers={
            "Cookie": "searchroom_session=" + token,
            "Origin": "https://localhost:8443",
            "X-CSRF-Token": csrf_value(token),
        },
    ) as client:
        for i in range(15):
            start = time.perf_counter()
            response = client.get(f"/api/v1/projects/{pid}/messages")
            reads.append(time.perf_counter() - start)
            response.raise_for_status()
            assert len(response.json()["items"]) <= 50
            if i % 3 == 0:
                import uuid

                start = time.perf_counter()
                response = client.post(
                    f"/api/v1/projects/{pid}/messages",
                    json={"body": "Fictional concurrent load message"},
                    headers={"Idempotency-Key": str(uuid.uuid4())},
                )
                writes.append(time.perf_counter() - start)
                response.raise_for_status()
    return reads, writes


with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
    results = list(pool.map(work, sessions))
reads = sorted(x for r, _ in results for x in r)
writes = sorted(x for _, w in results for x in w)
report = {
    "users": 20,
    "fixture_messages": 10000,
    "reads": len(reads),
    "writes": len(writes),
    "read_p95_ms": round(reads[int(len(reads) * 0.95) - 1] * 1000, 1),
    "write_p95_ms": round(writes[int(len(writes) * 0.95) - 1] * 1000, 1),
}
print(json.dumps(report))
assert report["read_p95_ms"] < 500 and report["write_p95_ms"] < 1000, (
    "Pilot latency target missed; inspect the database and instance budget."
)
