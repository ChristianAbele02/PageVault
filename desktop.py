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

from app import create_app
from config import app_data_dir

log = logging.getLogger("pagevault.desktop")

# ── Constants (no buried magic numbers) ─────────────────────────────────────────
WINDOW_TITLE = "PageVault"
WINDOW_SIZE = (1180, 820)
WINDOW_MIN_SIZE = (900, 600)

HOST = "127.0.0.1"
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

    app = create_app(
        {
            "SECRET_KEY": secret_key,
            "ADMIN_PASSWORD": admin_password,
            # Loopback-only server: hide the "Mobile" QR button, which a phone
            # could not reach anyway.
            "DESKTOP_MODE": True,
        }
    )

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
