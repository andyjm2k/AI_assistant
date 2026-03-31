"""Unit tests for scripts/verify_install.py (CATBot post-install verification)."""
import pytest
import shutil
import tempfile
from pathlib import Path
from scripts.verify_install import (
    PROJECT_ROOT,
    MCP_BROWSER_USE_DIR,
    check_core,
    check_autogen,
    check_mcp,
    check_playwright,
    check_runtime_optional_deps,
    check_llm_env_aliases,
    check_feature_env,
    check_mcp_server_cli,
)


def test_project_root_is_parent_of_scripts():
    """PROJECT_ROOT is the parent of the scripts directory."""
    assert PROJECT_ROOT.name != "scripts"
    assert (PROJECT_ROOT / "scripts").is_dir()
    assert (PROJECT_ROOT / "scripts" / "verify_install.py").exists()


def test_mcp_browser_use_path():
    """MCP_BROWSER_USE_DIR is mcp-browser-use under project root."""
    assert MCP_BROWSER_USE_DIR == PROJECT_ROOT / "mcp-browser-use"


def test_check_core_returns_tuple():
    """check_core returns (bool, str)."""
    ok, msg = check_core()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    # In test env we likely have core deps
    if ok:
        assert "OK" in msg or "Core" in msg


def test_check_autogen_returns_tuple():
    """check_autogen returns (bool, str)."""
    ok, msg = check_autogen()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)


def test_check_autogen_validates_required_assistant_agent_kwargs(monkeypatch):
    """check_autogen should verify the AssistantAgent API CATBot depends on."""
    from scripts import verify_install

    captured = {}

    def fake_run_python_check(description, code, python_exe=None):
        captured["description"] = description
        captured["code"] = code
        captured["python_exe"] = python_exe
        return True, "ok"

    monkeypatch.setattr(verify_install, "_run_python_check", fake_run_python_check)

    ok, msg = verify_install.check_autogen("C:/fake/python.exe")

    assert ok is True
    assert msg == "ok"
    assert captured["description"] == "AutoGen"
    assert captured["python_exe"] == "C:/fake/python.exe"
    assert "AssistantAgent" in captured["code"]
    assert "max_tool_iterations" in captured["code"]
    assert "reflect_on_tool_use" in captured["code"]
    assert "tool_call_summary_format" in captured["code"]


def test_check_mcp_returns_tuple():
    """check_mcp returns (bool, str)."""
    ok, msg = check_mcp()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)


def test_check_playwright_returns_tuple():
    """check_playwright returns (bool, str)."""
    ok, msg = check_playwright()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)


def test_check_runtime_optional_deps_returns_tuple():
    """check_runtime_optional_deps returns (bool, str)."""
    ok, msg = check_runtime_optional_deps()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)


def test_check_mcp_server_cli_returns_tuple():
    """check_mcp_server_cli returns (bool, str)."""
    ok, msg = check_mcp_server_cli()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    # If mcp-browser-use is missing, we get a clear message
    if not MCP_BROWSER_USE_DIR.is_dir() and not ok:
        assert "not found" in msg or "uv" in msg


def test_check_llm_env_aliases_warns_for_missing_standard_alias(monkeypatch):
    """check_llm_env_aliases warns when only MCP-prefixed provider keys are configured."""
    from scripts import verify_install

    root = Path.cwd() / f"verify-env-{next(tempfile._get_candidate_names())}"
    root.mkdir(parents=True, exist_ok=True)
    try:
        (root / ".env").write_text("MCP_LLM_PROVIDER=google\nMCP_LLM_GOOGLE_API_KEY=test-key\n", encoding="utf-8")
        monkeypatch.setattr(verify_install, "PROJECT_ROOT", root)
        ok, msg = verify_install.check_llm_env_aliases()
        assert ok is True
        assert "WARN:" in msg
        assert "GOOGLE_API_KEY" in msg
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_check_feature_env_warns_for_partial_spotify_config(monkeypatch):
    """check_feature_env warns when a feature block is only partially configured."""
    from scripts import verify_install

    root = Path.cwd() / f"verify-env-{next(tempfile._get_candidate_names())}"
    root.mkdir(parents=True, exist_ok=True)
    try:
        (root / ".env").write_text("SPOTIFY_CLIENT_ID=abc\n", encoding="utf-8")
        monkeypatch.setattr(verify_install, "PROJECT_ROOT", root)
        ok, msg = verify_install.check_feature_env()
        assert ok is True
        assert "WARN:" in msg
        assert "Spotify is partially configured" in msg
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_main_exits_zero_or_one(monkeypatch):
    """main() exits 0 when all checks pass, 1 when any fail."""
    from scripts import verify_install

    # Patched check functions must accept same signature as originals (python_exe optional)
    monkeypatch.setattr(verify_install, "check_core", lambda *a, **kw: (True, "ok"))
    monkeypatch.setattr(verify_install, "check_autogen", lambda *a, **kw: (True, "ok"))
    monkeypatch.setattr(verify_install, "check_mcp", lambda *a, **kw: (True, "ok"))
    monkeypatch.setattr(verify_install, "check_playwright", lambda *a, **kw: (True, "ok"))
    monkeypatch.setattr(verify_install, "check_runtime_optional_deps", lambda *a, **kw: (True, "ok"))
    monkeypatch.setattr(verify_install, "check_mcp_server_cli", lambda: (True, "ok"))
    monkeypatch.setattr(verify_install, "check_llm_env_aliases", lambda: (True, "ok"))
    monkeypatch.setattr(verify_install, "check_feature_env", lambda: (True, "ok"))
    assert verify_install.main() == 0

    monkeypatch.setattr(verify_install, "check_core", lambda *a, **kw: (False, "fail"))
    assert verify_install.main() == 1
