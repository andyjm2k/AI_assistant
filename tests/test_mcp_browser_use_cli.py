"""Regression tests for mcp-browser-use CLI state-dir resolution."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = PROJECT_ROOT / "mcp-browser-use" / "src" / "mcp_server_browser_use" / "cli.py"


def _load_cli_module(monkeypatch, runtime_dir: Path):
    package_name = "mcp_server_browser_use"
    cli_module_name = f"{package_name}.cli_test"
    config_module_name = f"{package_name}.config"
    skills_module_name = f"{package_name}.skills"

    monkeypatch.setenv("CATBOT_BROWSER_USE_RUNTIME_DIR", str(runtime_dir))

    package = types.ModuleType(package_name)
    package.__path__ = [str(CLI_PATH.parent)]
    sys.modules[package_name] = package

    config_module = types.ModuleType(config_module_name)
    config_module.APP_NAME = "mcp-server-browser-use"
    config_module.CONFIG_FILE = runtime_dir / "config.json"
    config_module.get_default_results_dir = lambda: runtime_dir / "results"
    config_module.load_config_file = lambda: {}
    config_module.save_config_file = lambda config: None
    config_module.settings = types.SimpleNamespace()
    sys.modules[config_module_name] = config_module

    skills_module = types.ModuleType(skills_module_name)
    skills_module.SkillStore = object
    sys.modules[skills_module_name] = skills_module

    spec = importlib.util.spec_from_file_location(cli_module_name, CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[cli_module_name] = module
    spec.loader.exec_module(module)
    return module


def test_cli_prefers_catbot_runtime_dir_for_state_files(monkeypatch):
    """CLI should keep daemon state/log files inside the repo runtime dir when configured."""
    runtime_dir = PROJECT_ROOT / "scratch" / "test-browser-state-runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    expected_state_dir = runtime_dir / "mcp-server-browser-use"

    module = _load_cli_module(monkeypatch, runtime_dir)

    assert module.get_state_dir() == expected_state_dir
    assert module.LOG_FILE == expected_state_dir / "server.log"
    assert module.SERVER_INFO_FILE == expected_state_dir / "server.json"
