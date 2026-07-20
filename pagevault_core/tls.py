"""Self-signed TLS certificate generation for local HTTPS.

Browsers only expose the camera API (``navigator.mediaDevices.getUserMedia``)
in a *secure context*: an HTTPS origin, or ``localhost``. When a phone connects
to PageVault over the LAN IP (``http://192.168.x.x:5000``) the page loads but
the ISBN scanner cannot open the camera, because that origin is plain HTTP.

Serving the app over HTTPS fixes this. We generate a persistent self-signed
certificate whose SubjectAltName covers the local hostnames and IP addresses,
so the same certificate is reused across restarts and a phone only has to accept
the security warning once. The certificate is regenerated automatically when it
is missing, close to expiry, or no longer covers the current LAN IP (which can
change under DHCP).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import ipaddress
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

CERT_FILENAME = "pagevault-cert.pem"
KEY_FILENAME = "pagevault-key.pem"

# 825 days is the maximum validity modern browsers accept for a leaf certificate.
_VALIDITY_DAYS = 825
# Regenerate once the certificate is within this many days of expiry.
_RENEW_BEFORE_DAYS = 30
_RSA_KEY_SIZE = 2048


def _parse_ips(raw_ips: list[str]) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    parsed: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for value in raw_ips:
        try:
            parsed.append(ipaddress.ip_address(value))
        except ValueError:
            log.debug("Skipping invalid IP for certificate SAN: %s", value)
    return parsed


def _cert_covers(cert_path: Path, desired_ips: list) -> bool:
    """Return True if the certificate is unexpired and lists every desired IP."""
    from cryptography import x509

    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    except (ValueError, OSError) as exc:
        log.debug("Existing certificate unreadable, will regenerate: %s", exc)
        return False

    now = dt.datetime.now(dt.timezone.utc)
    if cert.not_valid_after_utc <= now + dt.timedelta(days=_RENEW_BEFORE_DAYS):
        return False

    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        cert_ips = set(san.get_values_for_type(x509.IPAddress))
    except x509.ExtensionNotFound:
        return False

    return all(ip in cert_ips for ip in desired_ips)


def ensure_self_signed_cert(
    cert_dir: str | os.PathLike[str],
    san_hosts: list[str],
    san_ips: list[str],
) -> tuple[str, str] | None:
    """Ensure a usable self-signed certificate exists, generating one if needed.

    Args:
        cert_dir: Directory in which the certificate and key are stored.
        san_hosts: DNS names to embed in the SubjectAltName (e.g. ``localhost``).
        san_ips: IP addresses to embed in the SubjectAltName (e.g. the LAN IP).

    Returns:
        A ``(cert_path, key_path)`` tuple suitable for ``ssl_context`` in
        ``app.run``, or ``None`` if the ``cryptography`` library is unavailable.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        log.warning(
            "HTTPS requested but the 'cryptography' package is not installed. "
            "Install it (pip install cryptography) to enable mobile camera scanning."
        )
        return None

    cert_dir = Path(cert_dir)
    cert_path = cert_dir / CERT_FILENAME
    key_path = cert_dir / KEY_FILENAME
    desired_ips = _parse_ips(san_ips)

    if cert_path.exists() and key_path.exists() and _cert_covers(cert_path, desired_ips):
        return (str(cert_path), str(key_path))

    key = rsa.generate_private_key(public_exponent=65537, key_size=_RSA_KEY_SIZE)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PageVault Local")])
    san_entries: list[x509.GeneralName] = [x509.DNSName(host) for host in san_hosts]
    san_entries += [x509.IPAddress(ip) for ip in desired_ips]

    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=_VALIDITY_DAYS))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    cert_dir.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    # Best-effort on platforms/filesystems that ignore POSIX permissions.
    with contextlib.suppress(OSError):
        os.chmod(key_path, 0o600)

    log.info("Generated self-signed certificate for local HTTPS at %s", cert_path)
    return (str(cert_path), str(key_path))
