"""Explicit auth configuration; no import-time secrets or legacy defaults."""

from dataclasses import dataclass
import os
from urllib.parse import urlsplit


@dataclass(frozen=True)
class AuthConfig:
    secret: str
    origins: tuple[str, ...]
    secure_cookie: bool
    access_seconds: int = 300
    refresh_seconds: int = 604800
    issuer: str = "snooker-hybrid"
    audience: str = "snooker-frontend"

    @property
    def cookie_name(self) -> str:
        return "__Host-snooker_refresh" if self.secure_cookie else "snooker_refresh"


def allowed_origins() -> tuple[str, ...]:
    configured = os.environ.get("AUTH_ALLOWED_ORIGINS", "")
    if not configured and os.environ.get("APP_ENV") == "development":
        configured = "http://localhost:5173,http://127.0.0.1:5173"
    return tuple(
        item.strip().rstrip("/") for item in configured.split(",") if item.strip()
    )


def get_auth_config() -> AuthConfig:
    secret = os.environ.get("AUTH_SECRET_KEY", "")
    if len(secret) < 48 or len(set(secret)) < 8:
        raise RuntimeError(
            "AUTH_SECRET_KEY must be securely generated (at least 48 characters)"
        )
    origins = allowed_origins()
    development = os.environ.get("APP_ENV") == "development"
    if not origins or any(
        urlsplit(origin).scheme not in ("https", "http")
        or not urlsplit(origin).hostname
        or urlsplit(origin).username is not None
        or urlsplit(origin).path
        or urlsplit(origin).query
        or urlsplit(origin).fragment
        for origin in origins
    ):
        raise RuntimeError("AUTH_ALLOWED_ORIGINS must list explicit trusted origins")
    secure = os.environ.get("AUTH_COOKIE_SECURE", "true").lower() != "false"
    if not development and (
        not secure or any(not origin.startswith("https://") for origin in origins)
    ):
        raise RuntimeError(
            "Production authentication requires HTTPS origins and Secure cookies"
        )
    return AuthConfig(secret=secret, origins=origins, secure_cookie=secure)
