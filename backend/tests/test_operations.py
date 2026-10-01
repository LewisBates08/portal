from contextlib import contextmanager
from sqlalchemy import select
from app import operations
from app.models import MailOutbox, now
from app.mail import queue_action
import pytest
from app.config import get_settings
from app.models import EmailAction


@pytest.mark.parametrize("path,payload", [
    ("/api/v1/auth/register", {
        "name": "Setup Test", "agency_name": "Setup Agency",
        "email": "setup@example.com", "password": "TemporaryTestPassword!",
    }),
    ("/api/v1/auth/forgot-password", {"email": "setup@example.com"}),
    ("/api/v1/auth/resend-verification", {"email": "setup@example.com"}),
])
def test_disabled_mail_returns_unavailable_without_queuing(client, db, monkeypatch, path, payload):
    monkeypatch.setattr(get_settings(), "mail_enabled", False)
    response = client.post(path, json=payload)
    assert response.status_code == 503
    assert "email is not configured" in response.json()["detail"]
    assert db.scalar(select(EmailAction.token_hash).where(EmailAction.email == "setup@example.com")) is None
    assert db.scalar(select(MailOutbox.id).where(MailOutbox.recipient == "setup@example.com")) is None


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
