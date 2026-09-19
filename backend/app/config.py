from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def public_hostname(hostname: str) -> bool:
    import ipaddress
    import re

    try:
        ipaddress.ip_address(hostname)
        return False
    except ValueError:
        pass
    if hostname != hostname.lower() or len(hostname) > 253 or "." not in hostname:
        return False
    reserved = (
        "localhost",
        ".localhost",
        ".local",
        ".internal",
        ".test",
        ".invalid",
        ".example",
    )
    if hostname.endswith(reserved) or any(
        part in hostname
        for part in (
            "example.com",
            "example.org",
            "example.net",
            "your-domain",
            "yourcompany",
            "replace",
            "placeholder",
        )
    ):
        return False
    return all(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in hostname.split(".")
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", hide_input_in_errors=True
    )
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = Field(repr=False)
    # Legacy name is accepted for local setups; this key signs CSRF tokens, not JWTs.
    jwt_secret: str = Field(min_length=32, repr=False)
    encryption_key: str = Field(default="", repr=False)
    frontend_url: str = "http://localhost:5173"
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    auth_rate_limit: int = Field(default=30, ge=1)
    session_idle_minutes: int = Field(default=30, ge=1)
    pool_size: int = Field(default=5, ge=1, le=20)
    static_dir: str = ""
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = Field(default="", repr=False)
    mail_from: str = "Searchroom <no-reply@localhost>"
    max_users: int = 100
    max_projects: int = 100
    max_candidates: int = 1000
    daily_writes: int = 10000
    backup_bucket: str = ""
    backup_region: str = "eu-west-2"

    @property
    def production(self):
        return self.environment == "production"

    @property
    def cookie_name(self):
        return "__Host-searchroom_session" if self.production else "searchroom_session"

    @model_validator(mode="after")
    def production_safe(self):
        if self.production:
            from sqlalchemy.engine import make_url
            from cryptography.fernet import Fernet

            url = make_url(self.database_url)
            if url.query.get("sslmode") != "verify-full" or not url.query.get(
                "sslrootcert"
            ):
                raise ValueError(
                    "Production database requires verify-full TLS and sslrootcert."
                )
            if (
                not url.password
                or url.password in ("portal", "password")
                or url.username in ("portal", "postgres", "doadmin")
            ):
                raise ValueError(
                    "Use a dedicated, restricted production database role."
                )
            origin = urlsplit(self.frontend_url)
            hostname = origin.hostname or ""
            if (
                origin.scheme != "https"
                or origin.netloc != hostname
                or origin.path not in ("", "/")
                or origin.query
                or origin.fragment
                or not public_hostname(hostname)
            ):
                raise ValueError(
                    "Production FRONTEND_URL must be a real HTTPS origin without a path or custom port."
                )
            self.frontend_url = f"https://{hostname}"
            hosts = [host.strip() for host in self.trusted_hosts.split(",")]
            if hosts != [hostname]:
                raise ValueError(
                    "Production TRUSTED_HOSTS must contain only the FRONTEND_URL hostname."
                )
            self.trusted_hosts = hostname
            if any(
                s in self.jwt_secret.lower()
                for s in (
                    "change",
                    "example",
                    "test",
                    "development",
                    "replace",
                    "generate",
                    "placeholder",
                )
            ):
                raise ValueError("Replace the placeholder signing secret.")
            Fernet(self.encryption_key.encode())
            if (
                not self.smtp_user
                or not self.smtp_password
                or self.smtp_host != "email-smtp.eu-west-2.amazonaws.com"
            ):
                raise ValueError("Configure authenticated Amazon SES SMTP in London.")
            if any(
                marker in value.lower()
                for value in (
                    self.smtp_user,
                    self.smtp_password,
                    self.mail_from,
                    url.password,
                )
                for marker in ("replace", "your-domain", "placeholder")
            ):
                raise ValueError("Replace all credential and sender placeholders.")
            if not self.static_dir or "@localhost" in self.mail_from:
                raise ValueError("Set static_dir and a verified sender.")
        return self


@lru_cache
def get_settings():
    return Settings()
