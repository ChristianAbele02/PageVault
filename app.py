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

from flask import (
    Flask,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from config import (
    _FALLBACK_ADMIN_PASSWORD,
    _FALLBACK_SECRET_KEY,
    app_data_dir,
    resolve_config,
    resource_dir,
)
from pagevault_core import db as core_db
from pagevault_core import metadata as core_metadata
from pagevault_core import tls as core_tls
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
        banner = (
            "\n"
            "┌─────────────────────────────────────────────────────┐\n"
            "│  PageVault — Admin Password (this session only)     │\n"
            f"│  Password : {_pw:<41}│\n"
            "│                                                     │\n"
            "│  Set PAGEVAULT_ADMIN_PASSWORD in .env to persist.  │\n"
            "└─────────────────────────────────────────────────────┘\n"
        )
        try:
            print(banner, flush=True)
        except UnicodeEncodeError:
            # Redirected Windows consoles may use cp1252, which cannot encode
            # the box-drawing characters — never let the banner crash boot.
            print(f"\nPageVault admin password (this session only): {_pw}\n", flush=True)


# ── Application factory ───────────────────────────────────────────────────────
def create_app(config: dict | None = None) -> Flask:
    # Resolve templates/static through resource_dir() so they are found both from a
    # source checkout and when unpacked from a frozen (PyInstaller) bundle.
    resources = resource_dir()
    app = Flask(
        __name__,
        template_folder=str(resources / "templates"),
        static_folder=str(resources / "static"),
    )

    config_class = resolve_config(os.getenv("PAGEVAULT_ENV"))
    app.config.from_object(config_class)
    if config:
        app.config.update(config)

    _ensure_file_logging(app.config.get("LOG_FILE"))
    _check_security_config(app)

    # Register components
    _init_db_hook(app)
    app.register_blueprint(_api_bp())

    @app.get("/")
    def index():
        # mobile_qr controls the "Mobile" QR button. It is on for the networked
        # server (python app.py) and for the desktop app once its HTTPS LAN server
        # is up; it is off only when no phone-reachable URL exists.
        # is_mobile_app is set by the on-device Android build, which hides the
        # admin links and the phone-connect flow and enables native-app polish.
        return render_template(
            "index.html",
            mobile_qr=app.config.get("MOBILE_QR_ENABLED", True),
            is_mobile_app=app.config.get("PAGEVAULT_MOBILE_APP", False),
        )

    app.add_url_rule("/stats", "stats", lambda: render_template("stats.html"))
    app.add_url_rule("/reader", "reader", lambda: render_template("reader.html"))
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


def _fetch_dnb(isbn: str) -> dict | None:
    return core_metadata.fetch_dnb(isbn)


def _fetch_openlibrary_title_search(title: str, author: str | None = None) -> dict | None:
    return core_metadata.fetch_openlibrary_title_search(title, author)


def _fetch_googlebooks_title_author(title: str, author: str | None = None) -> dict | None:
    return core_metadata.fetch_googlebooks_title_author(title, author)


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
        fetch_dnb_fn=_fetch_dnb,
    )


def lookup_title_author(title: str, author: str | None = None) -> dict | None:
    """Metadata lookup for books without a real ISBN (Goodreads GR… ids)."""
    return core_metadata.lookup_title_author(
        title,
        author,
        fetch_openlibrary_title_fn=_fetch_openlibrary_title_search,
        fetch_googlebooks_title_fn=_fetch_googlebooks_title_author,
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
    # Explicit full-URL override, used by the desktop app to point the QR at its
    # separate HTTPS LAN server rather than the loopback URL the webview uses.
    explicit = (current_app.config.get("MOBILE_BASE_URL") or "").strip()
    if explicit:
        return explicit if explicit.endswith("/") else explicit + "/"

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
            "lookup_title_author": lambda title, author=None: lookup_title_author(title, author),
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


_HTTPS_OFF_VALUES = {"0", "false", "no", "off"}


def _https_enabled() -> bool:
    """HTTPS is on by default; PAGEVAULT_HTTPS=0/false/no/off opts out."""
    return (os.getenv("PAGEVAULT_HTTPS") or "auto").strip().lower() not in _HTTPS_OFF_VALUES


def _resolve_ssl_context(local_ip: str):
    """Return an ``ssl_context`` for ``app.run`` (cert/key tuple), or None for HTTP.

    Camera access in browsers requires a secure context, so HTTPS is what makes
    the mobile ISBN scanner work when a phone connects over the LAN IP.
    """
    if not _https_enabled():
        return None

    cert_dir = app_data_dir() / "certs"
    san_ips = ["127.0.0.1", "::1"]
    if local_ip not in san_ips:
        san_ips.append(local_ip)
    ssl_context = core_tls.ensure_self_signed_cert(cert_dir, ["localhost"], san_ips)
    if ssl_context is None:
        log.warning(
            "Falling back to HTTP — mobile camera scanning will not work. "
            "Install the optional dependency (pip install cryptography) or set "
            "PAGEVAULT_HTTPS=0 to silence this."
        )
    return ssl_context


def main() -> None:
    app = create_app()
    host = "0.0.0.0"
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
    local_ip = _detect_local_ip()

    ssl_context = _resolve_ssl_context(local_ip)
    scheme = "https" if ssl_context else "http"
    if ssl_context:
        # Served over TLS, so scope the session cookie to HTTPS. Left off when
        # falling back to HTTP (PAGEVAULT_HTTPS=0) or behind a TLS-terminating
        # proxy (gunicorn), where the cookie must still be sent over HTTP.
        app.config["SESSION_COOKIE_SECURE"] = True

    lines = [
        "\n📚  PageVault is running!",
        f"    Local  → {scheme}://localhost:{port}",
        f"    Phone  → {scheme}://{local_ip}:{port}  (same Wi-Fi)",
    ]
    if ssl_context:
        lines.append("    Note   → self-signed certificate; accept the one-time browser warning.")
    banner = "\n".join(lines) + "\n"
    try:
        print(banner, flush=True)
    except UnicodeEncodeError:
        # Redirected Windows consoles may use cp1252, which cannot encode the
        # book emoji — never let the startup banner crash boot (cf. issue #1).
        print(banner.encode("ascii", "ignore").decode("ascii"), flush=True)

    app.run(host=host, port=port, debug=debug, ssl_context=ssl_context)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
