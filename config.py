from __future__ import annotations

import os
import secrets
from pathlib import Path

# Module-level random fallbacks — generated once per process start.
# These are used only when the corresponding env var is not set.
# Both values change on every restart, which is intentional for security.
_FALLBACK_SECRET_KEY = secrets.token_hex(32)
_FALLBACK_ADMIN_PASSWORD = secrets.token_urlsafe(14)


class BaseConfig:
    DATABASE = os.getenv("PAGEVAULT_DB") or str(Path(__file__).parent / "pagevault.db")

    # If SECRET_KEY is not set, a random key is generated per-process restart.
    # Sessions will be invalidated on every restart.  Set SECRET_KEY in env for
    # stable sessions in any networked or persistent deployment.
    SECRET_KEY: str = os.getenv("SECRET_KEY") or _FALLBACK_SECRET_KEY

    JSON_SORT_KEYS = False

    # Admin authentication.  If PAGEVAULT_ADMIN_PASSWORD is not set, a random
    # one-time password is generated and logged at startup (see app.py).
    # Always set this env var before any networked deployment.
    ADMIN_PASSWORD: str = os.getenv("PAGEVAULT_ADMIN_PASSWORD") or _FALLBACK_ADMIN_PASSWORD

    LOG_FILE = os.getenv("PAGEVAULT_LOG_FILE") or str(Path(__file__).parent / "pagevault.log")

    # Cookie security — SameSite=Lax mitigates CSRF for same-origin SPA requests.
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # Set to True when serving over HTTPS


class DevConfig(BaseConfig):
    DEBUG = True


class TestConfig(BaseConfig):
    TESTING = True
    # Use a fixed key in tests so sessions are stable across requests.
    SECRET_KEY = "test-secret-key-do-not-use-in-production"
    ADMIN_PASSWORD = "test-admin-password"


class ProdConfig(BaseConfig):
    DEBUG = False
    # In production HTTPS deployments, enable secure cookies.
    # SESSION_COOKIE_SECURE = True


def resolve_config(config_name: str | None):
    mapping = {
        "development": DevConfig,
        "dev": DevConfig,
        "testing": TestConfig,
        "test": TestConfig,
        "production": ProdConfig,
        "prod": ProdConfig,
    }
    return mapping.get((config_name or "").strip().lower(), BaseConfig)
