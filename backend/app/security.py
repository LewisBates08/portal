"""Opaque revocable sessions. No bearer token authentication is accepted."""

import hashlib
import hmac
import secrets
import threading
import time
from datetime import timedelta
from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from pwdlib import PasswordHash
from .config import get_settings
from .database import get_db
from .models import WebSession, RateBucket, User, AuditEvent, now

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("not-a-real-user-password")
_hash_slots = threading.BoundedSemaphore(2)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(value):
    if not _hash_slots.acquire(blocking=False):
        raise HTTPException(
            429, "Authentication busy. Try again shortly.", headers={"Retry-After": "5"}
        )
    try:
        return passwords.hash(value)
    finally:
        _hash_slots.release()


def verify_password(value, encoded):
    if not _hash_slots.acquire(blocking=False):
        raise HTTPException(
            429, "Authentication busy. Try again shortly.", headers={"Retry-After": "5"}
        )
    try:
        return passwords.verify(value, encoded)
    finally:
        _hash_slots.release()


def audit(db, user, action, resource=""):
    db.add(
        AuditEvent(
            agency_id=user.agency_id,
            actor_id=user.id,
            action=action,
            resource=str(resource),
        )
    )


def csrf_value(token):
    return hmac.new(
        get_settings().jwt_secret.encode(), token.encode(), hashlib.sha256
    ).hexdigest()


def session_row(request, db, required=True):
    token = request.cookies.get(get_settings().cookie_name, "")
    row = db.get(WebSession, digest(token)) if token else None
    if not row or row.expires_at <= now() or row.idle_expires_at <= now():
        if required:
            raise HTTPException(401, "Please sign in again.")
        return None
    return row


def issue_session(db, request, response, user=None, mfa_complete=False):
    old = request.cookies.get(get_settings().cookie_name)
    if old:
        db.execute(delete(WebSession).where(WebSession.token_hash == digest(old)))
    token = secrets.token_urlsafe(32)
    expiry = now() + (timedelta(days=7) if user else timedelta(minutes=15))
    row = WebSession(
        token_hash=digest(token),
        user_id=user.id if user else None,
        expires_at=expiry,
        idle_expires_at=min(
            expiry, now() + timedelta(minutes=get_settings().session_idle_minutes)
        ),
        mfa_complete=mfa_complete,
    )
    db.add(row)
    response.set_cookie(
        get_settings().cookie_name,
        token,
        max_age=604800 if user else 900,
        secure=get_settings().production,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return row


def require_csrf(request: Request, db: Session = Depends(get_db)):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.headers.get("origin") != get_settings().frontend_url.rstrip("/"):
        raise HTTPException(403, "Request origin is not allowed.")
    token = request.cookies.get(get_settings().cookie_name, "")
    session_row(request, db)
    if not token or not secrets.compare_digest(
        request.headers.get("x-csrf-token", ""), csrf_value(token)
    ):
        raise HTTPException(403, "Invalid CSRF token. Refresh and try again.")


def signed_in_user(request: Request, db: Session = Depends(get_db)):
    session = session_row(request, db)
    user = db.get(User, session.user_id) if session.user_id else None
    if not user or not user.active or not user.email_verified:
        raise HTTPException(401, "Please sign in again.")
    session.idle_expires_at = min(
        session.expires_at,
        now() + timedelta(minutes=get_settings().session_idle_minutes),
    )
    db.commit()
    return user


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(signed_in_user),
):
    if user.role == "admin" and (
        not user.mfa_enabled or not session_row(request, db).mfa_complete
    ):
        raise HTTPException(
            403, "Complete administrator authenticator setup or verification."
        )
    return user


def admin(user: User = Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Agency administrator access is required.")
    return user


def revoke_sessions(db, user_id):
    db.execute(delete(WebSession).where(WebSession.user_id == user_id))


def throttle(db, key, limit, seconds=60):
    """Shared atomic fixed windows; commit independently of the guarded action."""
    stamp = int(time.time()) // seconds
    hashed = hmac.new(
        get_settings().jwt_secret.encode(), f"{key}:{stamp}".encode(), hashlib.sha256
    ).hexdigest()
    statement = insert(RateBucket).values(
        key=hashed, count=1, expires_at=now() + timedelta(seconds=seconds * 2)
    )
    count = db.scalar(
        statement.on_conflict_do_update(
            index_elements=["key"], set_={"count": RateBucket.count + 1}
        ).returning(RateBucket.count)
    )
    db.commit()
    if count > limit:
        raise HTTPException(
            429,
            "Too many requests. Try again later.",
            headers={"Retry-After": str(seconds)},
        )


def auth_limit(request, db, email=""):
    throttle(
        db,
        "auth-ip:" + (request.client.host if request.client else "unknown"),
        get_settings().auth_rate_limit,
    )
    if email:
        throttle(db, "auth-account:" + email.lower(), 10, 600)
