"""Run: python -m app.operations migrate|mail|cleanup|backup|check."""

import argparse
import logging
import os
import smtplib
import ssl
import subprocess
import tempfile
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path
from sqlalchemy import delete, select, text, func
from sqlalchemy.engine import make_url
from .database import SessionLocal, engine
from .models import (
    MailOutbox,
    EmailAction,
    WebSession,
    RateBucket,
    Submission,
    AuthSession,
    AuditEvent,
    now,
)
from .config import get_settings
from .mfa import decrypt


def migrate():
    from alembic import command
    from alembic.config import Config

    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(73201913)"))
        try:
            command.upgrade(
                Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head"
            )
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(73201913)"))


def mail():
    settings = get_settings()
    # Lock one row at a time; multiple job instances cannot claim the same mail.
    for _ in range(100):
        with SessionLocal.begin() as db:
            row = db.scalar(
                select(MailOutbox)
                .where(MailOutbox.next_attempt_at <= now(), MailOutbox.attempts < 8)
                .order_by(MailOutbox.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not row:
                return
            if row.created_at < now() - timedelta(days=7):
                db.delete(row)
                continue
            try:
                message = EmailMessage()
                message["From"], message["To"], message["Subject"] = (
                    settings.mail_from,
                    row.recipient,
                    "Searchroom account notification",
                )
                message["Message-ID"] = (
                    f"<searchroom-{row.id}@{settings.mail_from.split('@')[-1].rstrip('>')}>"
                )
                message.set_content(decrypt(row.content))
                with smtplib.SMTP(
                    settings.smtp_host, settings.smtp_port, timeout=10
                ) as smtp:
                    if settings.production or settings.smtp_user:
                        smtp.starttls(context=ssl.create_default_context())
                        smtp.login(settings.smtp_user, settings.smtp_password)
                    smtp.send_message(message)
                db.delete(row)
            except (OSError, smtplib.SMTPException):
                row.attempts += 1
                row.next_attempt_at = now() + timedelta(
                    minutes=min(60, 2**row.attempts)
                )
                logging.error(
                    "mail_delivery_failed outbox_id=%s attempts=%s",
                    row.id,
                    row.attempts,
                )


def cleanup():
    from .models import Invitation

    with SessionLocal.begin() as db:
        for model in (EmailAction, WebSession, RateBucket, AuthSession):
            db.execute(delete(model).where(model.expires_at < now()))
        db.execute(
            delete(Invitation).where(Invitation.expires_at < now() - timedelta(days=30))
        )
        db.execute(
            delete(MailOutbox).where(MailOutbox.created_at < now() - timedelta(days=7))
        )
        db.execute(
            delete(Submission).where(Submission.created_at < now() - timedelta(days=30))
        )
        db.execute(
            delete(AuditEvent).where(
                AuditEvent.created_at < now() - timedelta(days=180)
            )
        )


def backup():
    import boto3

    settings = get_settings()
    if not settings.backup_bucket or settings.backup_region != "eu-west-2":
        raise SystemExit("A private eu-west-2 backup bucket is required.")
    url = make_url(settings.database_url)
    env = {
        **os.environ,
        "PGHOST": url.host,
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username,
        "PGPASSWORD": url.password or "",
        "PGDATABASE": url.database,
    }
    for key in ("sslmode", "sslrootcert"):
        if key in url.query:
            env["PG" + key.upper()] = url.query[key]
    with tempfile.TemporaryDirectory() as folder:
        path = str(Path(folder) / "backup.dump")
        subprocess.run(
            ["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", path],
            env=env,
            check=True,
        )
        boto3.client("s3", region_name="eu-west-2").upload_file(
            path,
            settings.backup_bucket,
            f"postgres/{now():%Y/%m/%d/%H%M%S}.dump",
            ExtraArgs={
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": os.environ["BACKUP_KMS_KEY_ID"],
            },
        )
    print("Encrypted UK backup completed.")


def check():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        failed = db.scalar(
            select(func.count()).select_from(MailOutbox).where(MailOutbox.attempts >= 8)
        )
        if failed:
            raise SystemExit(
                f"{failed} account emails exhausted retries. Review mail delivery."
            )
    print("Database and mail queue healthy.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["migrate", "mail", "cleanup", "backup", "check", "mail-loop"],
    )
    command = parser.parse_args().command
    if command == "mail-loop":
        import time

        while True:
            mail()
            time.sleep(10)
    else:
        globals()[command]()
