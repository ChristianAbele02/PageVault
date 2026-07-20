"""
PageVault — Desktop launcher.

Runs the Flask application on a local waitress WSGI server and presents it in a
native OS window via pywebview, turning the web app into a self-contained desktop
program. Designed to run both from source and from a frozen (PyInstaller) build.

Usage:
    python desktop.py              # open the native window
    python desktop.py --no-window  # run the local server only and print its URL
    python desktop.py --port 8000  # bind the server to a fixed port
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import secrets
import socket
import threading
import time
from pathlib import Path

from flask import Flask

from app import _detect_local_ip, create_app
from config import app_data_dir
from pagevault_core import tls as core_tls

log = logging.getLogger("pagevault.desktop")

# ── Constants (no buried magic numbers) ─────────────────────────────────────────
WINDOW_TITLE = "PageVault"
WINDOW_SIZE = (1180, 820)
WINDOW_MIN_SIZE = (900, 600)

HOST = "127.0.0.1"
# The webview talks to the loopback server; the phone-facing HTTPS server binds
# all interfaces so a device on the same Wi-Fi can reach the LAN IP.
MOBILE_HTTPS_HOST = "0.0.0.0"
# Loopback-only port used purely as a single-instance lock (not for serving).
SINGLE_INSTANCE_PORT = 49219
SERVER_START_TIMEOUT_S = 15.0
SERVER_THREADS = 8

SECRET_KEY_FILE = "secret_key"
ADMIN_PASSWORD_FILE = "admin_password.txt"


# ── Persistent per-user secrets ─────────────────────────────────────────────────
def _write_private(path: Path, content: str) -> None:
    """Write text and best-effort restrict permissions to the owner."""
    path.write_text(content, encoding="utf-8")
    # POSIX permission bits are advisory at best on Windows; never fail on this.
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def _load_or_create_secret_key(data_dir: Path) -> str:
    """Return a stable Flask SECRET_KEY, generating and persisting one on first run.

    A stable key keeps login sessions valid across restarts, unlike the per-process
    random fallback used by the web/server configuration.
    """
    path = data_dir / SECRET_KEY_FILE
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass
    key = secrets.token_hex(32)
    _write_private(path, key)
    return key


def _load_or_create_admin_password(data_dir: Path) -> tuple[str, bool]:
    """Return the admin password, generating and persisting one on first run.

    Returns:
        A ``(password, created)`` tuple, where ``created`` is True only when a new
        password was generated during this call.
    """
    path = data_dir / ADMIN_PASSWORD_FILE
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing, False
    except OSError:
        pass
    password = secrets.token_urlsafe(14)
    _write_private(path, password + "\n")
    return password, True


# ── Single-instance guard ───────────────────────────────────────────────────────
def _acquire_single_instance_lock() -> socket.socket | None:
    """Bind a loopback lock port to ensure only one instance runs.

    Returns:
        The bound socket (keep it alive for the process lifetime) or None when
        another instance already holds the lock.
    """
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Deliberately no SO_REUSEADDR so a second instance fails to bind.
        lock.bind((HOST, SINGLE_INSTANCE_PORT))
        lock.listen(1)
    except OSError:
        lock.close()
        return None
    return lock


# ── Local server ────────────────────────────────────────────────────────────────
def _free_port(host: str = HOST) -> int:
    """Return an OS-assigned free TCP port on ``host``."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def _serve(app: Flask, host: str, port: int) -> None:
    """Serve ``app`` with waitress (blocking; intended to run on a daemon thread)."""
    from waitress import serve

    serve(app, host=host, port=port, threads=SERVER_THREADS)


def _serve_https(app: Flask, host: str, port: int, ssl_context: tuple[str, str]) -> None:
    """Serve ``app`` over HTTPS with Werkzeug (blocking; runs on a daemon thread).

    Waitress has no TLS support, so the phone-facing endpoint uses Werkzeug's
    threaded server. Traffic is light (a phone scanning the occasional barcode).
    """
    from werkzeug.serving import make_server

    make_server(host, port, app, threaded=True, ssl_context=ssl_context).serve_forever()


def _enable_mobile_access(app: Flask, data_dir: Path) -> str | None:
    """Start an HTTPS server on the LAN so a phone can use its camera scanner.

    Browsers expose the camera only on a secure origin, so the phone needs HTTPS
    rather than the loopback HTTP the desktop window uses. Returns the public
    ``https://<lan-ip>:<port>/`` URL, or None when a certificate cannot be created
    (for example if the optional ``cryptography`` dependency is unavailable).
    """
    lan_ip = _detect_local_ip()
    san_ips = ["127.0.0.1", "::1"]
    if lan_ip not in san_ips:
        san_ips.append(lan_ip)
    ssl_context = core_tls.ensure_self_signed_cert(data_dir / "certs", ["localhost"], san_ips)
    if ssl_context is None:
        log.warning("Mobile scanning unavailable: could not create a local certificate.")
        return None

    https_port = _free_port(MOBILE_HTTPS_HOST)
    threading.Thread(
        target=_serve_https,
        args=(app, MOBILE_HTTPS_HOST, https_port, ssl_context),
        name="pagevault-https",
        daemon=True,
    ).start()
    return f"https://{lan_ip}:{https_port}/"


def _wait_for_server(host: str, port: int, timeout: float) -> bool:
    """Poll until the server accepts a TCP connection or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _open_window(url: str) -> None:
    """Open the native webview window at ``url`` (blocks until the window closes)."""
    import webview

    webview.create_window(
        WINDOW_TITLE,
        url=url,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=WINDOW_MIN_SIZE,
    )
    webview.start()


# ── Entry point ─────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pagevault-desktop",
        description="Run PageVault as a native desktop application.",
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="Run the local server without opening a window (prints the URL).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind the local server to a specific port (default: an auto-selected free port).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # waitress is chatty at INFO; keep its banner quiet.
    logging.getLogger("waitress").setLevel(logging.WARNING)

    lock = _acquire_single_instance_lock()
    if lock is None:
        log.info("PageVault is already running.")
        return 0

    data_dir = app_data_dir()
    secret_key = _load_or_create_secret_key(data_dir)
    admin_password, created = _load_or_create_admin_password(data_dir)
    if created:
        log.info("Generated a new admin password (stored at %s).", data_dir / ADMIN_PASSWORD_FILE)

    app = create_app({"SECRET_KEY": secret_key, "ADMIN_PASSWORD": admin_password})

    host = HOST
    port = args.port or _free_port(host)

    server_thread = threading.Thread(
        target=_serve,
        args=(app, host, port),
        name="pagevault-server",
        daemon=True,
    )
    server_thread.start()

    if not _wait_for_server(host, port, SERVER_START_TIMEOUT_S):
        log.error("Server did not become reachable within %.0f s.", SERVER_START_TIMEOUT_S)
        return 1

    # Phone-facing HTTPS server so the camera scanner works from the same Wi-Fi.
    # The "Mobile" QR button is shown only when this succeeds.
    mobile_url = _enable_mobile_access(app, data_dir)
    app.config["MOBILE_QR_ENABLED"] = mobile_url is not None
    if mobile_url:
        app.config["MOBILE_BASE_URL"] = mobile_url
        log.info(
            "Mobile scanning available at %s (accept the certificate prompt on your phone).",
            mobile_url,
        )

    url = f"http://{host}:{port}/"

    if args.no_window:
        log.info("PageVault server running at %s (press Ctrl+C to stop).", url)
        try:
            server_thread.join()
        except KeyboardInterrupt:
            log.info("Shutting down.")
        return 0

    log.info("Opening PageVault window (%s).", url)
    _open_window(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
