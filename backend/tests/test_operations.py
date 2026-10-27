from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy import select
from app import operations
from app.models import (
    AuditEvent,
    AuthSession,
    EmailAction,
    Invitation,
    MailOutbox,
    RateBucket,
    Submission,
    WebSession,
    now,
)
from app.mail import queue_action
import pytest
import json
from urllib.error import HTTPError
from app.config import get_settings


@pytest.mark.parametrize(
    "path,payload",
    [
        (
            "/api/v1/auth/register",
            {
                "name": "Setup Test",
                "agency_name": "Setup Agency",
                "email": "setup@example.com",
                "password": "TemporaryTestPassword!",
            },
        ),
        ("/api/v1/auth/forgot-password", {"email": "setup@example.com"}),
        ("/api/v1/auth/resend-verification", {"email": "setup@example.com"}),
    ],
)
def test_disabled_mail_returns_unavailable_without_queuing(
    client, db, monkeypatch, path, payload
):
    monkeypatch.setattr(get_settings(), "mail_enabled", False)
    response = client.post(path, json=payload)
    assert response.status_code == 503
    assert "email is not configured" in response.json()["detail"]
    assert (
        db.scalar(
            select(EmailAction.token_hash).where(
                EmailAction.email == "setup@example.com"
            )
        )
        is None
    )
    assert (
        db.scalar(
            select(MailOutbox.id).where(MailOutbox.recipient == "setup@example.com")
        )
        is None
    )


def test_disabled_mail_worker_does_not_send(monkeypatch):
    monkeypatch.setattr(get_settings(), "mail_enabled", False)

    def unexpected(*args, **kwargs):
        raise AssertionError("Disabled worker must not connect to SMTP")

    monkeypatch.setattr(operations.smtplib, "SMTP", unexpected)
    operations.mail()


def test_outbox_retry_and_delete_after_acceptance(db, monkeypatch):
    queue_action(db, "delivery@example.com", "verify", {}, 1440)
    db.commit()

    class Factory:
        @staticmethod
        @contextmanager
        def begin():
            yield db
            db.commit()

    monkeypatch.setattr(operations, "SessionLocal", Factory)

    def fail(*args, **kwargs):
        raise OSError("simulated SMTP outage")

    monkeypatch.setattr(operations.smtplib, "SMTP", fail)
    operations.mail()
    row = db.scalar(
        select(MailOutbox).where(MailOutbox.recipient == "delivery@example.com")
    )
    assert row.attempts == 1 and row.next_attempt_at > now()
    row.next_attempt_at = now()
    db.commit()

    class SMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def send_message(self, message):
            assert "Searchroom account action" in message.get_content()
            assert message["To"] == "delivery@example.com"

    monkeypatch.setattr(operations.smtplib, "SMTP", SMTP)
    operations.mail()
    assert (
        db.scalar(
            select(MailOutbox).where(MailOutbox.recipient == "delivery@example.com")
        )
        is None
    )


def test_relay_outage_preserves_outbox_until_acceptance(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mail_transport", "relay")
    monkeypatch.setattr(
        settings, "mail_relay_url", "https://test.lambda-url.eu-west-2.on.aws/"
    )
    monkeypatch.setattr(settings, "mail_relay_token", "test-token-" * 8)
    queue_action(db, "delivery@example.com", "verify", {}, 1440)
    db.commit()

    class Factory:
        @staticmethod
        @contextmanager
        def begin():
            yield db
            db.commit()

    monkeypatch.setattr(operations, "SessionLocal", Factory)
    accepted = False

    class Opener:
        @contextmanager
        def open(self, request, timeout):
            assert (
                request.get_header("Authorization")
                == "Bearer " + settings.mail_relay_token
            )
            assert json.loads(request.data)["recipient"] == "delivery@example.com"
            assert timeout == 20
            if not accepted:
                raise HTTPError(request.full_url, 503, "unavailable", {}, None)
            yield type("Response", (), {"status": 202})()

    monkeypatch.setattr(operations, "build_opener", lambda *args: Opener())
    operations.mail()
    row = db.scalar(
        select(MailOutbox).where(MailOutbox.recipient == "delivery@example.com")
    )
    assert row.attempts == 1
    row.next_attempt_at = now()
    db.commit()
    accepted = True
    operations.mail()
    assert (
        db.scalar(
            select(MailOutbox.id).where(MailOutbox.recipient == "delivery@example.com")
        )
        is None
    )


def test_relay_does_not_follow_redirects():
    assert (
        operations.NoMailRedirects().redirect_request(
            None, None, 302, "", {}, "https://evil.invalid"
        )
        is None
    )


def test_pilot_recipient_restriction_does_not_queue(client, db, monkeypatch):
    monkeypatch.setattr(
        get_settings(), "mail_allowed_recipients", "approved@example.com"
    )
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Pilot",
            "agency_name": "Pilot",
            "email": "other@example.com",
            "password": "TemporaryTestPassword!",
        },
    )
    assert response.status_code == 503
    assert (
        db.scalar(
            select(MailOutbox.id).where(MailOutbox.recipient == "other@example.com")
        )
        is None
    )


def test_cleanup_respects_expiry_and_retention_boundaries(db, world, monkeypatch):
    fixed = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
    user_id = world["recruiter"].id
    project_id = world["project"].id
    for offset in (-1, 0, 1):
        db.add_all(
            [
                EmailAction(
                    token_hash=f"email-{offset}",
                    email=f"email-{offset}@example.com",
                    kind="verify",
                    payload={},
                    expires_at=fixed + timedelta(seconds=offset),
                ),
                WebSession(
                    token_hash=f"web-{offset}",
                    user_id=user_id,
                    expires_at=fixed + timedelta(seconds=offset),
                    idle_expires_at=fixed + timedelta(hours=1),
                    mfa_complete=True,
                ),
                RateBucket(
                    key=f"rate-{offset}",
                    count=1,
                    expires_at=fixed + timedelta(seconds=offset),
                ),
                AuthSession(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    refresh_hash=f"refresh-{offset}",
                    expires_at=fixed + timedelta(seconds=offset),
                ),
                Invitation(
                    token_hash=f"invite-{offset}",
                    agency_id=world["agency"].id,
                    project_id=project_id,
                    email=f"invite-{offset}@example.com",
                    role="recruiter",
                    expires_at=fixed - timedelta(days=30) + timedelta(seconds=offset),
                ),
                MailOutbox(
                    recipient=f"mail-{offset}@example.com",
                    content="placeholder",
                    created_at=fixed - timedelta(days=7) + timedelta(seconds=offset),
                    next_attempt_at=fixed,
                ),
                Submission(
                    key=f"submission-{offset}",
                    user_id=user_id,
                    project_id=project_id,
                    fingerprint="f" * 64,
                    result={},
                    created_at=fixed - timedelta(days=30) + timedelta(seconds=offset),
                ),
                AuditEvent(
                    agency_id=world["agency"].id,
                    actor_id=user_id,
                    action="boundary",
                    resource=str(offset),
                    created_at=fixed - timedelta(days=180) + timedelta(seconds=offset),
                ),
            ]
        )
    db.commit()

    class TestSessions:
        @staticmethod
        @contextmanager
        def begin():
            yield db

    monkeypatch.setattr(operations, "SessionLocal", TestSessions)
    monkeypatch.setattr(operations, "now", lambda: fixed)
    operations.cleanup()
    db.flush()

    assert db.get(EmailAction, "email--1") is None
    assert db.get(WebSession, "web--1") is None
    assert db.get(RateBucket, "rate--1") is None
    assert (
        db.scalar(select(AuthSession).where(AuthSession.refresh_hash == "refresh--1"))
        is None
    )
    assert (
        db.scalar(select(Invitation).where(Invitation.token_hash == "invite--1"))
        is None
    )
    assert (
        db.scalar(
            select(MailOutbox).where(MailOutbox.recipient == "mail--1@example.com")
        )
        is None
    )
    assert db.get(Submission, "submission--1") is None
    assert db.scalar(select(AuditEvent).where(AuditEvent.resource == "-1")) is None

    for offset in (0, 1):
        assert db.get(EmailAction, f"email-{offset}") is not None
        assert db.get(WebSession, f"web-{offset}") is not None
        assert db.get(RateBucket, f"rate-{offset}") is not None
        assert (
            db.scalar(
                select(AuthSession).where(
                    AuthSession.refresh_hash == f"refresh-{offset}"
                )
            )
            is not None
        )
        assert (
            db.scalar(
                select(Invitation).where(Invitation.token_hash == f"invite-{offset}")
            )
            is not None
        )
        assert (
            db.scalar(
                select(MailOutbox).where(
                    MailOutbox.recipient == f"mail-{offset}@example.com"
                )
            )
            is not None
        )
        assert db.get(Submission, f"submission-{offset}") is not None
        assert (
            db.scalar(select(AuditEvent).where(AuditEvent.resource == str(offset)))
            is not None
        )
