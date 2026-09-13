from contextlib import contextmanager
from sqlalchemy import select
from app import operations
from app.models import MailOutbox, now
from app.mail import queue_action


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
