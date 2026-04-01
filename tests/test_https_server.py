"""
Unit tests for src/servers/https_server.py.
Verifies HTTPS_CERT_HOSTNAME from .env is used for cert names and hostname list.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_https_cert_hostname_default_without_env():
    """When HTTPS_CERT_HOSTNAME is unset, module uses default anton.local for cert filenames."""
    # Run in subprocess so we get a fresh import with no env set and no .env loading.
    root = str(PROJECT_ROOT)
    code = (
        "import sys, os, types; sys.path.insert(0, %r); os.environ.pop('HTTPS_CERT_HOSTNAME', None); "
        "dotenv = types.ModuleType('dotenv'); dotenv.load_dotenv = lambda *a, **k: None; sys.modules['dotenv'] = dotenv; "
        "import src.servers.https_server as m; "
        "assert m.CERT_FILE == 'anton.local+2.pem'; assert m.KEY_FILE == 'anton.local+2-key.pem'; "
        "assert m._CERT_HOSTNAME == 'anton.local'"
    ) % (root,)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env={k: v for k, v in os.environ.items() if k != "HTTPS_CERT_HOSTNAME"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")


def test_https_cert_hostname_from_env():
    """When HTTPS_CERT_HOSTNAME is set in env, module uses it for cert filenames and hostname."""
    root = str(PROJECT_ROOT)
    code = (
        "import sys, os; sys.path.insert(0, %r); os.environ['HTTPS_CERT_HOSTNAME']='mytest.local'; "
        "import src.servers.https_server as m; "
        "assert m.CERT_FILE == 'mytest.local+2.pem'; assert m.KEY_FILE == 'mytest.local+2-key.pem'; "
        "assert m._CERT_HOSTNAME == 'mytest.local'"
    ) % (root,)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env={**os.environ, "HTTPS_CERT_HOSTNAME": "mytest.local"},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")


def test_https_cert_hostname_stripped():
    """HTTPS_CERT_HOSTNAME value is stripped of surrounding whitespace."""
    root = str(PROJECT_ROOT)
    code = (
        "import sys, os; sys.path.insert(0, %r); os.environ['HTTPS_CERT_HOSTNAME']='  myhost.local  '; "
        "import src.servers.https_server as m; "
        "assert m._CERT_HOSTNAME == 'myhost.local'; assert m.CERT_FILE == 'myhost.local+2.pem'"
    ) % (root,)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env={**os.environ, "HTTPS_CERT_HOSTNAME": "  myhost.local  "},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (result.stdout or "") + (result.stderr or "")


def test_check_mkcert_certificates_uses_hostname_glob():
    """check_mkcert_certificates uses _CERT_HOSTNAME_GLOB for glob pattern (no wildcard injection)."""
    # Import after we know default; glob var should be sanitized (no * or ?)
    import src.servers.https_server as m
    assert "*" not in m._CERT_HOSTNAME_GLOB, "Glob part should not contain *"
    assert "?" not in m._CERT_HOSTNAME_GLOB, "Glob part should not contain ?"


def test_configure_console_output_prefers_utf8(monkeypatch):
    """HTTPS startup should reconfigure console streams to UTF-8 when possible."""
    import src.servers.https_server as m

    calls = []

    class FakeStream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(m.sys, "stdout", FakeStream())
    monkeypatch.setattr(m.sys, "stderr", FakeStream())

    m._configure_console_output()

    assert calls == [
        {"encoding": "utf-8", "errors": "replace"},
        {"encoding": "utf-8", "errors": "replace"},
    ]
