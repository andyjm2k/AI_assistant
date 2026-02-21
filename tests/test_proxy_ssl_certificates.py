"""
Unit tests for proxy_server SSL certificate discovery (find_mkcert_certificates, get_ssl_certificates).
Verifies HTTPS_CERT_HOSTNAME from .env is used for cert discovery and default paths.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_find_mkcert_certificates_uses_hostname_glob(monkeypatch):
    """find_mkcert_certificates finds certs matching hostname glob in certs/ dir."""
    import src.servers.proxy_server as proxy_server

    tmp_path = Path(tempfile.mkdtemp(prefix="test_ssl_", dir=str(PROJECT_ROOT)))
    try:
        certs_dir = tmp_path / "certs"
        certs_dir.mkdir()
        hostname = "testproxy.local"
        (certs_dir / f"{hostname}+2.pem").write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
        (certs_dir / f"{hostname}+2-key.pem").write_text("-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n")

        monkeypatch.setattr(proxy_server, "_PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(proxy_server, "_SSL_CERT_HOSTNAME", hostname)
        monkeypatch.setattr(proxy_server, "_SSL_CERT_HOSTNAME_GLOB", hostname)

        cert_file, key_file = proxy_server.find_mkcert_certificates()
        assert cert_file is not None
        assert key_file is not None
        assert hostname in cert_file
        assert "certs" in cert_file
    finally:
        try:
            (tmp_path / "certs" / f"{hostname}+2.pem").unlink(missing_ok=True)
            (tmp_path / "certs" / f"{hostname}+2-key.pem").unlink(missing_ok=True)
            (tmp_path / "certs").rmdir()
            tmp_path.rmdir()
        except Exception:
            pass


def test_get_ssl_certificates_fallback_uses_hostname(monkeypatch):
    """get_ssl_certificates fallback default cert names use configured hostname."""
    import src.servers.proxy_server as proxy_server

    tmp_path = Path(tempfile.mkdtemp(prefix="test_ssl_", dir=str(PROJECT_ROOT)))
    try:
        certs_dir = tmp_path / "certs"
        certs_dir.mkdir()
        hostname = "fallback.local"
        (certs_dir / f"{hostname}+2.pem").write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
        (certs_dir / f"{hostname}+2-key.pem").write_text("-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n")

        monkeypatch.setattr(proxy_server, "_PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(proxy_server, "_SSL_CERT_HOSTNAME", hostname)
        monkeypatch.setattr(proxy_server, "_SSL_CERT_HOSTNAME_GLOB", hostname)

        cert_file, key_file = proxy_server.get_ssl_certificates()
        assert cert_file is not None
        assert key_file is not None
        assert hostname in cert_file
    finally:
        try:
            (tmp_path / "certs" / f"{hostname}+2.pem").unlink(missing_ok=True)
            (tmp_path / "certs" / f"{hostname}+2-key.pem").unlink(missing_ok=True)
            (tmp_path / "certs").rmdir()
            tmp_path.rmdir()
        except Exception:
            pass


def test_proxy_ssl_cert_hostname_default():
    """When HTTPS_CERT_HOSTNAME is unset, proxy_server uses default anton.local."""
    env = {k: v for k, v in os.environ.items() if k != "HTTPS_CERT_HOSTNAME"}
    env["PYTHONIOENCODING"] = "utf-8"  # Avoid UnicodeEncodeError on Windows for proxy_server print
    code = (
        "import os, sys; sys.path.insert(0, %r); os.environ.pop('HTTPS_CERT_HOSTNAME', None); "
        "import src.servers.proxy_server as m; "
        "assert m._SSL_CERT_HOSTNAME == 'anton.local'; assert m._SSL_CERT_HOSTNAME_GLOB == 'anton.local'"
    ) % (str(PROJECT_ROOT),)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")
