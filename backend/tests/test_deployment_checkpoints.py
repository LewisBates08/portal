"""Regression tests for fail-closed production configuration and safe errors."""

import secrets
from contextlib import contextmanager
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.config import Settings, get_settings
from app.main import app
from app.models import User
from test_concurrency import parallel_world  # noqa: F401


def valid_settings(**overrides):
    values = dict(
        environment="production",
        database_url="postgresql+psycopg://app_owner:"
        + secrets.token_urlsafe(24)
        + "@db.internal:25060/searchroom?sslmode=verify-full&sslrootcert=/tmp/ca.pem",
        jwt_secret=secrets.token_hex(32),
        encryption_key=Fernet.generate_key().decode(),
        frontend_url="https://portal.radiumsearch.com",
        trusted_hosts="portal.radiumsearch.com",
        smtp_host="email-smtp.eu-west-2.amazonaws.com",
        smtp_user=secrets.token_hex(12),
        smtp_password=secrets.token_hex(24),
        mail_from="Searchroom <accounts@radiumsearch.com>",
        static_dir="/app/static",
    )
    return Settings(_env_file=None, **(values | overrides))


@pytest.mark.parametrize(
    "origin",
    [
        "http://portal.radiumsearch.com",
        "https://127.0.0.1",
        "https://localhost",
        "https://portal.radiumsearch.com@evil.invalid",
        "https://portal.radiumsearch.com/path",
        "https://portal.radiumsearch.com?x=1",
        "https://portal.radiumsearch.com:8443",
        "https://portal.your-domain.co.uk",
        "https://portal.example.com",
    ],
)
def test_bad_production_origins_rejected(origin):
    with pytest.raises(ValidationError):
        valid_settings(frontend_url=origin)


@pytest.mark.parametrize(
    "hosts",
    [
        "*",
        "portal.radiumsearch.com,localhost",
        "127.0.0.1",
        "evil.invalid",
        "*.radiumsearch.com",
        "",
    ],
)
def test_hosts_must_match_the_production_origin(hosts):
    with pytest.raises(ValidationError):
        valid_settings(trusted_hosts=hosts)


def test_production_config_and_repr_hide_secrets():
    settings = valid_settings()
    assert settings.cookie_name == "__Host-searchroom_session"
    for value in (
        settings.jwt_secret,
        settings.encryption_key,
        settings.smtp_password,
        settings.database_url,
    ):
        assert value not in repr(settings)
    with pytest.raises(ValidationError) as failure:
        valid_settings(jwt_secret="private-secret-too-short")
    assert "private-secret-too-short" not in str(failure.value)


def test_validation_does_not_echo_credentials(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "invalid", "password": "private-input-marker" * 20},
    )
    assert response.status_code == 422
    assert "private-input-marker" not in response.text
    assert all(
        "input" not in error and "ctx" not in error
        for error in response.json()["detail"]
    )


def test_cross_origin_requests_are_not_granted_cors(client):
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://attacker.invalid",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers
    assert (
        client.get("/api/v1/health", headers={"Host": "attacker.invalid"}).status_code
        == 400
    )


def test_production_500_is_generic_and_has_no_traceback(client, monkeypatch, caplog):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")

    async def fail():
        raise RuntimeError("private-exception-marker")

    app.add_api_route("/_checkpoint-failure", fail)
    try:
        response = client.get("/_checkpoint-failure")
        assert response.status_code == 500
        assert "private-exception-marker" not in response.text
        assert "Traceback" not in response.text
        assert "private-exception-marker" not in caplog.text
        assert response.json()["request_id"] == response.headers["x-request-id"]
        assert response.headers["cache-control"] == "no-store"
        assert app.debug is False
    finally:
        app.router.routes[:] = [
            r
            for r in app.router.routes
            if getattr(r, "path", None) != "/_checkpoint-failure"
        ]


def test_production_refuses_legacy_demo_accounts(parallel_world, monkeypatch):  # noqa: F811
    import app.main as main

    engine, _, ids = parallel_world

    @contextmanager
    def session():
        with Session(engine) as db:
            yield db

    monkeypatch.setattr(main, "SessionLocal", session)
    monkeypatch.setattr(get_settings(), "environment", "production")
    with Session(engine) as db:
        user = db.get(User, ids["client"])
        user.email = "client@example.com"
        db.commit()
    with pytest.raises(RuntimeError, match="legacy demo"):
        with TestClient(app):
            pass


def test_production_bootstrap_rejects_reload():
    import os
    from pathlib import Path
    import subprocess
    import sys

    bootstrap = Path(__file__).resolve().parents[1] / "bootstrap.py"
    result = subprocess.run(
        [sys.executable, str(bootstrap), "uvicorn", "app.main:app", "--reload"],
        env={**os.environ, "ENVIRONMENT": "production"},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "reload is disabled in production" in result.stderr
