from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

APP_NAME = "PageVault"

# Module-level random fallbacks — generated once per process start.
# These are used only when the corresponding env var is not set.
# Both values change on every restart, which is intentional for security.
_FALLBACK_SECRET_KEY = secrets.token_hex(32)
_FALLBACK_ADMIN_PASSWORD = secrets.token_urlsafe(14)


def _is_frozen() -> bool:
    """True when running from a PyInstaller (or similar) frozen build."""
    return bool(getattr(sys, "frozen", False))


def _platform_data_root() -> Path:
    """Per-user, writable data root for the current OS."""
    if sys.platform == "win32":
        base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
        return Path(base) if base else Path.home() / "AppData" / "Local"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    xdg = os.getenv("XDG_DATA_HOME")
    return Path(xdg) if xdg else Path.home() / ".local" / "share"


def app_data_dir() -> Path:
    """Return the directory holding PageVault's writable state (DB, book files, logs).

    Resolution order:
        1. ``PAGEVAULT_DATA_DIR`` if set, for explicit control.
        2. A per-user OS data directory when running as a frozen executable, since
           the executable may live in a read-only location (e.g. Program Files) and
           one-file builds extract to a temp directory that is wiped on exit.
        3. The project directory for source checkouts and development.

    The resolved directory is created if it does not already exist.

    Returns:
        The writable data directory as a :class:`~pathlib.Path`.
    """
    override = os.getenv("PAGEVAULT_DATA_DIR")
    if override:
        path = Path(override)
    elif _is_frozen():
        path = _platform_data_root() / APP_NAME
    else:
        path = Path(__file__).resolve().parent
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_dir() -> Path:
    """Return the base directory for bundled read-only resources (templates, static).

    Under a frozen build these are unpacked beside the interpreter at
    ``sys._MEIPASS``; from source they sit next to this module.

    Returns:
        The resource base directory as a :class:`~pathlib.Path`.
    """
    if _is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return Path(__file__).resolve().parent


def _default_db_path() -> str:
    return os.getenv("PAGEVAULT_DB") or str(app_data_dir() / "pagevault.db")


def _default_book_files_dir(db_path: str) -> str:
    return os.getenv("PAGEVAULT_BOOK_FILES_DIR") or str(Path(db_path).parent / "book_files")


def _default_log_file() -> str:
    return os.getenv("PAGEVAULT_LOG_FILE") or str(app_data_dir() / "pagevault.log")


class BaseConfig:
    DATABASE = _default_db_path()
    # Book files live next to the database so a custom PAGEVAULT_DB keeps them together.
    BOOK_FILES_DIR: str = _default_book_files_dir(DATABASE)
    MAX_CONTENT_LENGTH: int = 150 * 1024 * 1024  # 150 MB upload limit

    # If SECRET_KEY is not set, a random key is generated per-process restart.
    # Sessions will be invalidated on every restart.  Set SECRET_KEY in env for
    # stable sessions in any networked or persistent deployment.
    SECRET_KEY: str = os.getenv("SECRET_KEY") or _FALLBACK_SECRET_KEY

    JSON_SORT_KEYS = False

    # Admin authentication.  If PAGEVAULT_ADMIN_PASSWORD is not set, a random
    # one-time password is generated and logged at startup (see app.py).
    # Always set this env var before any networked deployment.
    ADMIN_PASSWORD: str = os.getenv("PAGEVAULT_ADMIN_PASSWORD") or _FALLBACK_ADMIN_PASSWORD

    LOG_FILE = _default_log_file()

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
