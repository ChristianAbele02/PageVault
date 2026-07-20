"""PageVault — Android entry point.

Runs the existing Flask application on a loopback port inside the Android app
process (embedded CPython via Chaquopy). The Kotlin ``MainActivity`` calls
:func:`start` once, then loads ``http://127.0.0.1:<port>/`` in a WebView.

The heavy lifting lives in the shared ``app``/``pagevault_core`` modules, which
are copied into the build unchanged. This module only wires the Android runtime
to them: it points the writable data directory and the read-only resource
directory at paths supplied by Kotlin, disables TLS (loopback is already a secure
context, so the camera works without a certificate), and starts a WSGI server.
"""

from __future__ import annotations

import logging
import os
import secrets
import socket
import threading
import time

log = logging.getLogger("pagevault.android")

# waitress is a pure-Python, production-grade WSGI server. Traffic here is a
# single local WebView, so a small thread pool is plenty.
_SERVER_THREADS = 4
_STARTUP_TIMEOUT_S = 20.0
_SECRET_KEY_FILE = "secret_key"
_PORT_FILE = "server_port"

# Module-level state so a re-entrant call (e.g. Activity recreation) reuses the
# already-running server rather than starting a second one.
_lock = threading.Lock()
_running_port = 0


def _free_loopback_port() -> int:
    """Return an OS-assigned free TCP port bound to loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _port_is_available(port: int) -> bool:
    """True if ``port`` can currently be bound on loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _choose_stable_port(data_dir: str) -> int:
    """Return a loopback port, preferring the one used on the previous launch.

    The WebView origin is ``http://127.0.0.1:<port>``. Keeping the port stable
    keeps that origin stable, so origin-scoped browser storage (the saved theme
    and language, the offline caches) survives across app restarts. A fresh port
    is only chosen when no port was saved yet or the saved one is taken.
    """
    path = os.path.join(data_dir, _PORT_FILE)
    try:
        with open(path, encoding="utf-8") as handle:
            saved = int(handle.read().strip())
        if 1024 <= saved <= 65535 and _port_is_available(saved):
            return saved
    except (OSError, ValueError):
        pass

    port = _free_loopback_port()
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(str(port))
    except OSError as exc:
        log.warning("Could not persist the server port (%s); it may change next launch.", exc)
    return port


def _wait_until_reachable(port: int, timeout: float) -> bool:
    """Poll the loopback port until it accepts a connection or ``timeout`` passes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def _load_or_create_secret_key(data_dir: str) -> str:
    """Return a stable Flask secret key, creating and persisting one on first run.

    A stable key keeps any signed session cookies valid across app restarts.
    """
    path = os.path.join(data_dir, _SECRET_KEY_FILE)
    try:
        with open(path, encoding="utf-8") as handle:
            existing = handle.read().strip()
        if existing:
            return existing
    except OSError:
        pass
    key = secrets.token_hex(32)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(key)
    except OSError as exc:
        # Never fail startup over the key file; fall back to an in-memory key.
        log.warning("Could not persist secret key (%s); using a session-only key.", exc)
    return key


def start(data_dir: str, resource_dir: str) -> int:
    """Start the Flask server on loopback and return the port it is listening on.

    Args:
        data_dir: Writable directory for the SQLite database, book files and logs
            (typically ``<filesDir>/data``).
        resource_dir: Directory holding the extracted ``templates`` and ``static``
            folders (typically ``<filesDir>/web``).

    Returns:
        The loopback TCP port the server is listening on. Repeated calls return the
        same port without starting a second server.
    """
    global _running_port
    with _lock:
        if _running_port:
            return _running_port

        os.makedirs(data_dir, exist_ok=True)

        # These must be set before importing config/app: config reads them while
        # its configuration classes are constructed at import time.
        os.environ["PAGEVAULT_DATA_DIR"] = data_dir
        os.environ["PAGEVAULT_RESOURCE_DIR"] = resource_dir
        os.environ["PAGEVAULT_HTTPS"] = "0"

        from app import create_app  # imported here so the env above is in effect

        app = create_app(
            {
                "SECRET_KEY": _load_or_create_secret_key(data_dir),
                # The phone is the device, so the "connect a phone" QR button and
                # the admin console are hidden in the on-device build.
                "MOBILE_QR_ENABLED": False,
                "PAGEVAULT_MOBILE_APP": True,
            }
        )

        port = _choose_stable_port(data_dir)

        def _serve() -> None:
            from waitress import serve

            serve(app, host="127.0.0.1", port=port, threads=_SERVER_THREADS)

        threading.Thread(target=_serve, name="pagevault-server", daemon=True).start()

        if not _wait_until_reachable(port, _STARTUP_TIMEOUT_S):
            raise RuntimeError(f"PageVault server did not start within {_STARTUP_TIMEOUT_S:.0f}s")

        _running_port = port
        log.info("PageVault server ready on 127.0.0.1:%d", port)
        return port
