from datetime import timedelta
from urllib.parse import urlsplit, parse_qs
import re
import pytest
import pyotp
from sqlalchemy import select
from app.models import User, MailOutbox, EmailAction, WebSession, now
from app.mfa import decrypt
from app.security import digest

API = "/api/v1/auth"


def mail_token(db):
    row = db.scalar(select(MailOutbox).order_by(MailOutbox.id.desc()).limit(1))
    return re.search(r"#token=([^\s]+)", decrypt(row.content)).group(1)


def csrf(client):
    client.headers["X-CSRF-Token"] = client.get(API + "/csrf").json()["csrf_token"]


def test_registration_email_mfa_and_logout(client, db):
    payload = {
        "email": "new@example.com",
        "name": "New",
        "agency_name": "New Agency",
        "password": "StrongPassword!",
    }
    response = client.post(API + "/register", json=payload)
    assert response.status_code == 202 and "access_token" not in response.json()
    assert db.scalar(select(User).where(User.email == payload["email"])) is None
    token = mail_token(db)
    assert client.post(API + "/verify-email", json={"token": token}).status_code == 204
    assert client.post(API + "/verify-email", json={"token": token}).status_code == 400
    login = client.post(
        API + "/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200 and login.json()["mfa_required"]
    assert (
        "HttpOnly" in login.headers["set-cookie"]
        and "SameSite=lax" in login.headers["set-cookie"]
    )
    assert client.get("/api/v1/projects").status_code == 403
    csrf(client)
    secret = client.post(API + "/mfa/setup").json()["secret"]
    verified = client.post(API + "/mfa/verify", json={"code": pyotp.TOTP(secret).now()})
    assert verified.status_code == 200, verified.text
    assert len(verified.json()["recovery_codes"]) == 10
    assert client.get("/api/v1/projects").status_code == 200
    csrf(client)
    assert client.post(API + "/logout").status_code == 204
    assert client.get(API + "/me").status_code == 401


def test_csrf_origin_bearer_and_body_limits(client, world, auth):
    h = auth("client")
    assert (
        client.post(
            "/api/v1/projects/1/messages",
            headers={**h, "Origin": "https://evil.example"},
            json={"body": "Bad"},
        ).status_code
        == 403
    )
    assert (
        client.post(API + "/logout", headers={**h, "X-CSRF-Token": "bad"}).status_code
        == 403
    )
    assert (
        client.get(
            API + "/me", headers={"Cookie": "", "Authorization": "Bearer obsolete"}
        ).status_code
        == 401
    )
    assert (
        client.post(API + "/refresh", json={"refresh_token": "obsolete"}).status_code
        == 404
    )
    assert client.post(API + "/login", content="x" * 1048577).status_code == 413


def test_password_reset_revokes_sessions_single_use_and_generic(
    client, world, auth, db
):
    h = auth("client")
    assert (
        client.post(
            API + "/forgot-password", json={"email": "fixture-client@example.com"}
        ).json()
        == client.post(
            API + "/forgot-password", json={"email": "unknown@example.com"}
        ).json()
    )
    token = mail_token(db)
    assert (
        client.post(
            API + "/reset-password",
            json={"token": token, "password": "ReplacementPassword!"},
        ).status_code
        == 204
    )
    assert client.get(API + "/me", headers=h).status_code == 401
    assert (
        client.post(
            API + "/reset-password",
            json={"token": token, "password": "ReplacementPassword!"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            API + "/login",
            json={
                "email": "fixture-client@example.com",
                "password": "PasswordForTests!",
            },
        ).status_code
        == 401
    )
    assert (
        client.post(
            API + "/login",
            json={
                "email": "fixture-client@example.com",
                "password": "ReplacementPassword!",
            },
        ).status_code
        == 200
    )


def test_invitation_verified_before_membership_and_revocation(client, world, auth, db):
    h = auth("admin")
    pid = world["project"].id
    result = client.post(
        "/api/v1/invitations",
        headers=h,
        json={"email": "invited@example.com", "role": "client", "project_id": pid},
    )
    assert result.status_code == 201, result.text
    invite = parse_qs(urlsplit(result.json()["url"]).fragment)["token"][0]
    assert (
        client.post(
            API + "/accept-invitation",
            json={"token": invite, "name": "Invited", "password": "InvitedPassword!"},
        ).status_code
        == 200
    )
    assert db.scalar(select(User).where(User.email == "invited@example.com")) is None
    verification = mail_token(db)
    assert (
        client.post(API + "/verify-email", json={"token": verification}).status_code
        == 204
    )
    assert (
        client.post(API + "/accept-invitation", json={"token": invite}).status_code
        == 400
    )
    login = client.post(
        API + "/login",
        json={"email": "invited@example.com", "password": "InvitedPassword!"},
    )
    assert login.status_code == 200
    assert client.get(f"/api/v1/projects/{pid}").status_code == 200
    assert client.get(f"/api/v1/projects/{world['second'].id}").status_code == 404


def test_expired_verification_and_idle_absolute_expiry(client, db, world, auth):
    client.post(
        API + "/register",
        json={
            "name": "Expired",
            "agency_name": "Agency",
            "email": "expired@example.com",
            "password": "PasswordForTests!",
        },
    )
    token = mail_token(db)
    action = db.get(EmailAction, digest(token))
    action.expires_at = now() - timedelta(seconds=1)
    db.commit()
    assert client.post(API + "/verify-email", json={"token": token}).status_code == 400
    h = auth("client")
    raw = h["Cookie"].split("=", 1)[1]
    row = db.get(WebSession, digest(raw))
    absolute = row.expires_at
    assert client.get(API + "/me", headers=h).status_code == 200
    db.refresh(row)
    assert row.expires_at == absolute
    row.idle_expires_at = now() - timedelta(seconds=1)
    db.commit()
    assert client.get(API + "/me", headers=h).status_code == 401


def test_existing_account_invite_matching_and_removed_pending_access(
    client, world, auth
):
    h = auth("admin")
    pid = world["second"].id
    response = client.post(
        "/api/v1/invitations",
        headers=h,
        json={
            "email": "fixture-client@example.com",
            "role": "client",
            "project_id": pid,
        },
    )
    token = parse_qs(urlsplit(response.json()["url"]).fragment)["token"][0]
    assert (
        client.post(
            API + "/accept-invitation", headers=auth("colleague"), json={"token": token}
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/v1/projects/{pid}/members/{world['client'].id}", headers=h
        ).status_code
        == 204
    )
    assert (
        client.post(
            API + "/accept-invitation", headers=auth("client"), json={"token": token}
        ).status_code
        == 400
    )


def test_production_cookie_flags_and_security_headers(client, db, world, monkeypatch):
    from app.config import get_settings
    from app.main import app
    from fastapi.testclient import TestClient

    import app.main as main

    # Database launch gating is covered separately against an isolated schema.
    monkeypatch.setattr(main, "ensure_production_database", lambda: None)
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "frontend_url", "https://localhost")
    with TestClient(app, base_url="https://localhost") as browser:
        token = browser.get(API + "/csrf").json()["csrf_token"]
        result = browser.post(
            API + "/login",
            headers={"Origin": "https://localhost", "X-CSRF-Token": token},
            json={
                "email": "fixture-client@example.com",
                "password": "PasswordForTests!",
            },
        )
        assert result.status_code == 200, result.text
        cookie = result.headers["set-cookie"]
        assert (
            "__Host-searchroom_session=" in cookie
            and "Secure" in cookie
            and "HttpOnly" in cookie
            and "Domain=" not in cookie
        )
        assert result.headers["strict-transport-security"] == "max-age=31536000"
        assert "frame-ancestors 'none'" in result.headers["content-security-policy"]
        assert "localhost" not in result.headers["content-security-policy"]
        assert browser.get(API + "/me").status_code == 200


def test_production_config_rejects_development_settings():
    from app.config import Settings
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            database_url="postgresql+psycopg://portal:portal@localhost/portal",
            jwt_secret="a" * 64,
        )


def test_mfa_replay_and_single_use_recovery(client, world, auth, db):
    h = auth("admin")
    user = world["admin"]
    user.mfa_enabled = False
    db.commit()
    secret = client.post(API + "/mfa/setup", headers=h).json()["secret"]
    result = client.post(
        API + "/mfa/verify", headers=h, json={"code": pyotp.TOTP(secret).now()}
    )
    assert result.status_code == 200, result.text
    csrf(client)
    assert (
        client.post(
            API + "/mfa/verify", json={"code": pyotp.TOTP(secret).now()}
        ).status_code
        == 401
    )
    code = result.json()["recovery_codes"][0]
    assert client.post(API + "/mfa/verify", json={"code": code}).status_code == 200
    csrf(client)
    assert client.post(API + "/mfa/verify", json={"code": code}).status_code == 401
