"""Transactional email outbox; sensitive mail bodies are encrypted at rest."""

import secrets
from datetime import timedelta
from .config import get_settings
from .mfa import encrypt
from .models import EmailAction, MailOutbox, now
from .security import digest


def queue_action(db, email, kind, payload, minutes):
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
    db.add(
        MailOutbox(
            recipient=email,
            content=encrypt(
                f"You are invited to Searchroom.\n\n{link}\n\nThis link expires in seven days."
            ),
        )
    )
