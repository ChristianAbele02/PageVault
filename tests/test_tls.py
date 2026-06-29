"""Tests for self-signed certificate generation and the HTTPS toggle."""

from __future__ import annotations

from pathlib import Path

import pytest

import app as app_module
from pagevault_core import tls

pytest.importorskip("cryptography")
from cryptography import x509  # noqa: E402 — imported after the availability guard


def _load(cert_path: str) -> x509.Certificate:
    return x509.load_pem_x509_certificate(Path(cert_path).read_bytes())


def _san_ips(cert: x509.Certificate) -> set[str]:
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}


class TestCertGeneration:
    def test_generates_cert_and_key_with_expected_san(self, tmp_path):
        result = tls.ensure_self_signed_cert(tmp_path, ["localhost"], ["127.0.0.1", "192.168.1.50"])
        assert result is not None
        cert_path, key_path = result
        assert Path(cert_path).exists()
        assert Path(key_path).exists()

        cert = _load(cert_path)
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        assert "localhost" in san.get_values_for_type(x509.DNSName)
        assert {"127.0.0.1", "192.168.1.50"} <= _san_ips(cert)

    def test_invalid_ip_is_skipped_not_fatal(self, tmp_path):
        result = tls.ensure_self_signed_cert(tmp_path, ["localhost"], ["127.0.0.1", "not-an-ip"])
        assert result is not None
        assert _san_ips(_load(result[0])) == {"127.0.0.1"}

    def test_reuses_existing_cert(self, tmp_path):
        first = tls.ensure_self_signed_cert(tmp_path, ["localhost"], ["127.0.0.1"])
        assert first is not None
        serial = _load(first[0]).serial_number

        second = tls.ensure_self_signed_cert(tmp_path, ["localhost"], ["127.0.0.1"])
        assert second == first
        # Same certificate on disk: not silently regenerated each launch.
        assert _load(second[0]).serial_number == serial

    def test_regenerates_when_lan_ip_changes(self, tmp_path):
        first = tls.ensure_self_signed_cert(tmp_path, ["localhost"], ["127.0.0.1"])
        assert first is not None
        old_serial = _load(first[0]).serial_number

        # A new LAN IP not covered by the stored cert forces regeneration (DHCP).
        second = tls.ensure_self_signed_cert(tmp_path, ["localhost"], ["127.0.0.1", "10.0.0.5"])
        assert second is not None
        new_cert = _load(second[0])
        assert new_cert.serial_number != old_serial
        assert "10.0.0.5" in _san_ips(new_cert)


class TestHttpsToggle:
    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("PAGEVAULT_HTTPS", raising=False)
        assert app_module._https_enabled() is True

    def test_auto_is_enabled(self, monkeypatch):
        monkeypatch.setenv("PAGEVAULT_HTTPS", "auto")
        assert app_module._https_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "OFF", " Off "])
    def test_off_values_disable(self, monkeypatch, value):
        monkeypatch.setenv("PAGEVAULT_HTTPS", value)
        assert app_module._https_enabled() is False

    def test_disabled_yields_no_ssl_context(self, monkeypatch):
        monkeypatch.setenv("PAGEVAULT_HTTPS", "0")
        assert app_module._resolve_ssl_context("192.168.1.50") is None
