"""
PageVault — Personal Book Catalog
Flask application factory and REST API.

Usage:
    python app.py                  # development
    flask run --host=0.0.0.0       # production-ish
    gunicorn -w 2 "app:create_app()"
"""

from __future__ import annotations

import logging
import os
import socket
import sqlite3
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from config import _FALLBACK_ADMIN_PASSWORD, _FALLBACK_SECRET_KEY, resolve_config
from pagevault_core import db as core_db
from pagevault_core import metadata as core_metadata
from pagevault_core import utils as core_utils

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def _ensure_file_logging(log_file: str | None) -> None:
    if not log_file:
        return
    root_logger = logging.getLogger()
    if any(isinstance(handler, logging.FileHandler) for handler in root_logger.handlers):
        return
    try:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        # RotatingFileHandler: 10 MB per file, keep 5 backups (issue #18)
        file_handler = RotatingFileHandler(
            log_file,
            encoding="utf-8",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
    except OSError as exc:
        # Avoid crashing app boot in restricted runtimes (e.g., read-only /app in containers).
        log.warning("File logging disabled (%s): %s", log_file, exc)
        return

    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(file_handler)


def _check_security_config(app: Flask) -> None:
    """Warn about insecure / default configuration values at startup (issue #1, #2)."""
    if app.config.get("TESTING"):
        return  # suppress warnings and banner during test runs

    if app.config.get("SECRET_KEY") == _FALLBACK_SECRET_KEY:
        log.warning(
            "SECRET_KEY not set — a random key is used this session. "
            "Sessions will be invalidated on every restart. "
            "Set SECRET_KEY in your environment for stable, persistent sessions."
        )

    if app.config.get("ADMIN_PASSWORD") == _FALLBACK_ADMIN_PASSWORD:
        _pw = app.config["ADMIN_PASSWORD"]
        log.warning(
            "PAGEVAULT_ADMIN_PASSWORD not set — temporary admin password for this session: %s  "
            "Set PAGEVAULT_ADMIN_PASSWORD in your environment to make it permanent.",
            _pw,
        )
        print(
            "\n"
            "┌─────────────────────────────────────────────────────┐\n"
            "│  PageVault — Admin Password (this session only)     │\n"
            f"│  Password : {_pw:<41}│\n"
            "│                                                     │\n"
            "│  Set PAGEVAULT_ADMIN_PASSWORD in .env to persist.  │\n"
            "└─────────────────────────────────────────────────────┘\n",
            flush=True,
        )


# ── Application factory ───────────────────────────────────────────────────────
def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    config_class = resolve_config(os.getenv("PAGEVAULT_ENV"))
    app.config.from_object(config_class)
    if config:
        app.config.update(config)

    _ensure_file_logging(app.config.get("LOG_FILE"))
    _check_security_config(app)

    # Register components
    _init_db_hook(app)
    app.register_blueprint(_api_bp())
    app.add_url_rule("/", "index", lambda: render_template("index.html"))
    app.add_url_rule("/stats", "stats", lambda: render_template("stats.html"))
    app.add_url_rule("/admin/login", "admin_login", lambda: render_template("admin_login.html"))

    @app.get("/admin")
    def admin_dashboard():
        if session.get("role") != "admin":
            return redirect(url_for("admin_login"))
        return render_template("admin.html")

    @app.get("/api/mobile/connect")
    def mobile_connect_info():
        return jsonify({"url": _mobile_base_url()})

    core_db.bootstrap_database(app)

    return app


# ── Database helpers ──────────────────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    return core_db.get_db()


def _init_db_hook(app: Flask) -> None:
    core_db.init_db_hook(app)


def _ensure_schema(db: sqlite3.Connection) -> None:
    core_db.ensure_schema(db)


# ── ISBN metadata helpers ─────────────────────────────────────────────────────
def _fetch_openlibrary(isbn: str) -> dict | None:
    return core_metadata.fetch_openlibrary(isbn)


def _fetch_googlebooks(isbn: str) -> dict | None:
    return core_metadata.fetch_googlebooks(isbn)


def _fetch_crossref(isbn: str) -> dict | None:
    return core_metadata.fetch_crossref(isbn)


def _fetch_openlibrary_search(isbn: str) -> dict | None:
    return core_metadata.fetch_openlibrary_search(isbn)


def _fetch_openlibrary_covers(isbn: str) -> dict | None:
    return core_metadata.fetch_openlibrary_covers(isbn)


def _merge_lookup_data(primary: dict | None, fallback: dict | None) -> dict | None:
    return core_metadata.merge_lookup_data(primary, fallback)


def lookup_isbn(isbn: str) -> dict | None:
    return core_metadata.lookup_isbn(
        isbn,
        fetch_openlibrary_fn=_fetch_openlibrary,
        fetch_googlebooks_fn=_fetch_googlebooks,
        fetch_crossref_fn=_fetch_crossref,
        fetch_openlibrary_search_fn=_fetch_openlibrary_search,
        fetch_openlibrary_covers_fn=_fetch_openlibrary_covers,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────
def _now() -> str:
    return core_utils.now_utc_iso()


def _err(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


def _validate_status(value: str | None) -> bool:
    return core_utils.validate_status(value)


def _validate_logo_url(value: str | None) -> bool:
    return core_utils.validate_logo_url(value)


def _normalize_tags(value) -> list[str]:
    return core_utils.normalize_tags(value)


def _int_list(values) -> list[int]:
    return core_utils.int_list(values)


def _normalize_isbn(value: str | None) -> str:
    return core_utils.normalize_isbn(value)


def _split_multi_value(value: str | None) -> list[str]:
    return core_utils.split_multi_value(value)


def _status_from_goodreads(value: str | None) -> str:
    return core_utils.status_from_goodreads(value)


def _detect_local_ip() -> str:
    """Best-effort local IP detection for same-network mobile access."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            detected = sock.getsockname()[0]
            if detected:
                return str(detected)
    except OSError:
        pass

    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


def _mobile_base_url() -> str:
    override_host = (os.getenv("PAGEVAULT_MOBILE_HOST") or "").strip()
    host_header = request.host or ""
    host = host_header.split(":", 1)[0].strip().lower()

    if override_host:
        public_host = override_host
    elif host in {"", "localhost", "127.0.0.1", "::1"}:
        public_host = _detect_local_ip()
    else:
        public_host = host_header

    if ":" not in public_host and ":" in host_header:
        _, port = host_header.rsplit(":", 1)
        if port.isdigit() and port not in {"80", "443"}:
            public_host = f"{public_host}:{port}"

    return f"{request.scheme}://{public_host}/"


# ── API Blueprint ─────────────────────────────────────────────────────────────
def _api_bp():
    """Create API blueprint using modular core infrastructure."""
    from pagevault_core import api as core_api

    return core_api.create_api_blueprint(
        deps={
            "get_db": get_db,
            "lookup_isbn": lambda isbn: lookup_isbn(isbn),
            "merge_lookup_data": _merge_lookup_data,
            "now": _now,
            "err": _err,
            "validate_status": _validate_status,
            "validate_logo_url": _validate_logo_url,
            "normalize_tags": _normalize_tags,
            "int_list": _int_list,
            "normalize_isbn": _normalize_isbn,
            "split_multi_value": _split_multi_value,
            "status_from_goodreads": _status_from_goodreads,
            "log": log,
        }
    )


def main() -> None:
    app = create_app()
    host = "0.0.0.0"
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except OSError:  # specific exception instead of bare except (issue #6)
        local_ip = "127.0.0.1"

    print("\n📚  PageVault is running!")
    print(f"    Local  → http://localhost:{port}")
    print(f"    Phone  → http://{local_ip}:{port}  (same Wi-Fi)\n")
    app.run(host=host, port=port, debug=debug)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
