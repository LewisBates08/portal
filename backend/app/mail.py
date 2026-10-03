"""Transactional email outbox; sensitive mail bodies are encrypted at rest."""

import secrets
from datetime import timedelta
from fastapi import HTTPException
from .config import get_settings
from .mfa import encrypt
from .models import EmailAction, MailOutbox, now
from .security import digest


def require_mail(email=None):
    if not get_settings().mail_enabled:
        raise HTTPException(
            503,
            "Account email is not configured yet. Please try again once setup is complete.",
        )
    allowed = get_settings().mail_allowed_recipients
    if email and allowed and email.lower() not in {
        value.strip().lower() for value in allowed.split(",")
    }:
        raise HTTPException(503, "Email is currently limited to approved test accounts.")


def queue_action(db, email, kind, payload, minutes):
    require_mail(email)
    token = secrets.token_urlsafe(32)
    db.add(
        EmailAction(
            token_hash=digest(token),
            email=email,
            kind=kind,
            payload=payload,
            expires_at=now() + timedelta(minutes=minutes),
        )
    )
    link = f"{get_settings().frontend_url}/account/{kind}#token={token}"
    db.add(
        MailOutbox(
            recipient=email,
            content=encrypt(
                f"Searchroom account action\n\nOpen this link to continue:\n{link}\n\nIt expires in {minutes} minutes. If you did not request this, ignore this email."
            ),
        )
    )


def queue_invitation(db, email, link):
    require_mail(email)
    db.add(
        MailOutbox(
            recipient=email,
            content=encrypt(
                f"You are invited to Searchroom.\n\n{link}\n\nThis link expires in seven days."
            ),
        )
    )
