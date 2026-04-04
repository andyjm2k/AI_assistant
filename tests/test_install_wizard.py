"""Unit tests for scripts/install_wizard.py (configuration wizard)."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.install_wizard import (
    DEFAULT_PROJECT_ROOT,
    LLM_PROVIDERS,
    PROVIDER_API_KEY_VAR,
    STANDARD_PROVIDER_API_KEY_VAR,
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
    assert "minimax" in keys
    assert "google" in keys


def test_provider_api_key_var_mapping():
    """PROVIDER_API_KEY_VAR has correct env var names."""
    assert PROVIDER_API_KEY_VAR["openai"] == "MCP_LLM_OPENAI_API_KEY"
    assert PROVIDER_API_KEY_VAR["minimax"] == "MCP_LLM_MINIMAX_API_KEY"
    assert PROVIDER_API_KEY_VAR["google"] == "MCP_LLM_GOOGLE_API_KEY"
    assert PROVIDER_API_KEY_VAR["ollama"] is None
    assert STANDARD_PROVIDER_API_KEY_VAR["openai"] == "OPENAI_API_KEY"
    assert STANDARD_PROVIDER_API_KEY_VAR["google"] == "GOOGLE_API_KEY"


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
    scratch_root = DEFAULT_PROJECT_ROOT / "scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)
    env_path = scratch_root / f"test_wizard_{next(tempfile._get_candidate_names())}.env"
    try:
        with patch("builtins.input", side_effect=["1", "", "", "", "", "n", "n", "", "", "", "mylan.local"]):
            run_wizard(scratch_root, env_path)
        content = env_path.read_text(encoding="utf-8")
        assert "HTTPS_CERT_HOSTNAME=mylan.local" in content
    finally:
        env_path.unlink(missing_ok=True)


def test_run_wizard_uses_default_https_hostname_when_empty():
    """run_wizard uses default anton.local when HTTPS hostname prompt is empty."""
    scratch_root = DEFAULT_PROJECT_ROOT / "scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)
    env_path = scratch_root / f"test_wizard_{next(tempfile._get_candidate_names())}.env"
    try:
        with patch("builtins.input", side_effect=["1", "", "", "", "", "n", "n", "", "", "", ""]):
            run_wizard(scratch_root, env_path)
        content = env_path.read_text(encoding="utf-8")
        assert "HTTPS_CERT_HOSTNAME=anton.local" in content
    finally:
        env_path.unlink(missing_ok=True)


def test_run_wizard_sets_standard_google_aliases():
    """run_wizard mirrors Google provider settings into standard env names used by runtime modules."""
    scratch_root = DEFAULT_PROJECT_ROOT / "scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)
    env_path = scratch_root / f"test_wizard_{next(tempfile._get_candidate_names())}.env"
    try:
        with patch("builtins.input", side_effect=["4", "", "google-test-key", "", "", "n", "n", "", "", "", ""]):
            run_wizard(scratch_root, env_path)
        content = env_path.read_text(encoding="utf-8")
        assert "MCP_LLM_PROVIDER=google" in content
        assert "MCP_LLM_GOOGLE_API_KEY=google-test-key" in content
        assert "GOOGLE_API_KEY=google-test-key" in content
        assert "MCP_MODEL_PROVIDER=google" in content
        assert "MCP_MODEL_NAME=gemini-3-flash-preview" in content
    finally:
        env_path.unlink(missing_ok=True)


def test_run_wizard_provisions_browser_server_secret():
    """run_wizard provisions MCP_BROWSER_SERVER_SECRET when none exists."""
    scratch_root = DEFAULT_PROJECT_ROOT / "scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)
    env_path = scratch_root / f"test_wizard_{next(tempfile._get_candidate_names())}.env"
    try:
        with patch("scripts.install_wizard.secrets.token_urlsafe", return_value="browser-secret"), patch(
            "builtins.input",
            side_effect=["1", "", "", "", "", "n", "n", "", "", "", ""],
        ):
            run_wizard(scratch_root, env_path)
        content = env_path.read_text(encoding="utf-8")
        assert "MCP_BROWSER_SERVER_SECRET=browser-secret" in content
    finally:
        env_path.unlink(missing_ok=True)


def test_run_wizard_reuses_existing_autogen_secret_for_browser_server():
    """run_wizard reuses AUTOGEN_TEAM_SECRET for MCP_BROWSER_SERVER_SECRET when present."""
    scratch_root = DEFAULT_PROJECT_ROOT / "scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)
    env_path = scratch_root / f"test_wizard_{next(tempfile._get_candidate_names())}.env"
    try:
        env_path.write_text("AUTOGEN_TEAM_SECRET=team-secret\n", encoding="utf-8")
        with patch("builtins.input", side_effect=["1", "", "", "", "", "n", "n", "", "", "", ""]):
            run_wizard(scratch_root, env_path)
        content = env_path.read_text(encoding="utf-8")
        assert "AUTOGEN_TEAM_SECRET=team-secret" in content
        assert "MCP_BROWSER_SERVER_SECRET=team-secret" in content
    finally:
        env_path.unlink(missing_ok=True)
