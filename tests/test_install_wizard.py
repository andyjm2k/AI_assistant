"""Unit tests for scripts/install_wizard.py (configuration wizard)."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.install_wizard import (
    DEFAULT_PROJECT_ROOT,
    LLM_PROVIDERS,
    PROVIDER_API_KEY_VAR,
    _set_key_in_env_content,
    run_wizard,
)


def test_project_root_is_parent_of_scripts():
    """DEFAULT_PROJECT_ROOT is parent of scripts directory."""
    assert DEFAULT_PROJECT_ROOT.name != "scripts"
    assert (DEFAULT_PROJECT_ROOT / "scripts" / "install_wizard.py").exists()


def test_llm_providers_include_ollama_and_openai():
    """LLM_PROVIDERS includes common providers."""
    keys = [p[0] for p in LLM_PROVIDERS]
    assert "ollama" in keys
    assert "openai" in keys
    assert "google" in keys


def test_provider_api_key_var_mapping():
    """PROVIDER_API_KEY_VAR has correct env var names."""
    assert PROVIDER_API_KEY_VAR["openai"] == "MCP_LLM_OPENAI_API_KEY"
    assert PROVIDER_API_KEY_VAR["google"] == "MCP_LLM_GOOGLE_API_KEY"
    assert PROVIDER_API_KEY_VAR["ollama"] is None


def test_set_key_in_env_content_replaces_existing():
    """_set_key_in_env_content replaces existing KEY=value line."""
    content = "MCP_LLM_PROVIDER=ollama\nMCP_LLM_MODEL_NAME=old\n"
    result = _set_key_in_env_content(content, "MCP_LLM_PROVIDER", "openai")
    assert "MCP_LLM_PROVIDER=openai\n" in result
    assert "MCP_LLM_PROVIDER=ollama" not in result


def test_set_key_in_env_content_appends_if_missing():
    """_set_key_in_env_content appends KEY=value if key not present."""
    content = "FOO=bar\n"
    result = _set_key_in_env_content(content, "NEW_KEY", "new_value")
    assert "NEW_KEY=new_value\n" in result
    assert "FOO=bar" in result


def test_set_key_in_env_content_skips_empty_value():
    """_set_key_in_env_content does not set when value is empty."""
    content = "MCP_LLM_PROVIDER=ollama\n"
    result = _set_key_in_env_content(content, "MCP_LLM_PROVIDER", "")
    assert result == content


def test_set_key_in_env_content_preserves_comments():
    """_set_key_in_env_content preserves comment lines."""
    content = "# comment\nMCP_LLM_PROVIDER=ollama\n"
    result = _set_key_in_env_content(content, "MCP_LLM_PROVIDER", "google")
    assert "# comment\n" in result
    assert "MCP_LLM_PROVIDER=google\n" in result


def test_wizard_skip_wizard_exits_zero():
    """main() with --skip-wizard exits 0."""
    import scripts.install_wizard as wiz
    # Run with --skip-wizard; need to patch sys.argv
    import sys
    old = sys.argv
    try:
        sys.argv = ["install_wizard.py", "--skip-wizard"]
        assert wiz.main() == 0
    finally:
        sys.argv = old


def test_run_wizard_writes_https_cert_hostname():
    """run_wizard writes HTTPS_CERT_HOSTNAME to .env with prompted or default value."""
    tmp_path = Path(tempfile.mkdtemp(prefix="test_wizard_", dir=str(Path(__file__).resolve().parent.parent)))
    try:
        env_path = tmp_path / ".env"
        # Mock input: 1=ollama, default model, blank endpoint, blank brave, blank news, n=no telegram, custom hostname
        with patch("builtins.input", side_effect=["1", "", "", "", "", "n", "mylan.local"]):
            run_wizard(Path(tmp_path), env_path)
        content = env_path.read_text(encoding="utf-8")
        assert "HTTPS_CERT_HOSTNAME=mylan.local" in content
    finally:
        try:
            tmp_path.joinpath(".env").unlink(missing_ok=True)
            tmp_path.rmdir()
        except Exception:
            pass


def test_run_wizard_uses_default_https_hostname_when_empty():
    """run_wizard uses default anton.local when HTTPS hostname prompt is empty."""
    tmp_path = Path(tempfile.mkdtemp(prefix="test_wizard_", dir=str(Path(__file__).resolve().parent.parent)))
    try:
        env_path = tmp_path / ".env"
        with patch("builtins.input", side_effect=["1", "", "", "", "", "n", ""]):
            run_wizard(Path(tmp_path), env_path)
        content = env_path.read_text(encoding="utf-8")
        assert "HTTPS_CERT_HOSTNAME=anton.local" in content
    finally:
        try:
            tmp_path.joinpath(".env").unlink(missing_ok=True)
            tmp_path.rmdir()
        except Exception:
            pass
