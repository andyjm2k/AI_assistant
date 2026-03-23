"""MCP server for browser-use."""

from __future__ import annotations

import os
from pathlib import Path


def _runtime_downloads_root() -> Path:
    configured = os.environ.get("MCP_BROWSER_DOWNLOADS_DIR")
    if configured:
        return Path(configured).expanduser()

    runtime_dir = os.environ.get("CATBOT_BROWSER_USE_RUNTIME_DIR")
    if runtime_dir:
        return Path(runtime_dir).expanduser() / "browser-use-downloads"

    return Path.cwd() / ".runtime" / "browser-use-downloads"


def _patch_browser_use_tmp_downloads() -> None:
    """Redirect browser-use's hardcoded /tmp download dir on Windows."""
    if os.name != "nt":
        return

    try:
        from browser_use.browser import profile as profile_module
    except Exception:
        return

    validator = getattr(profile_module.BrowserProfile, "set_default_downloads_path", None)
    if validator is None:
        return

    original_path = validator.__globals__.get("Path", Path)
    if getattr(original_path, "__name__", "") == "_catbot_patched_path":
        return

    def _catbot_patched_path(value: str | os.PathLike[str]) -> Path:
        text = os.fspath(value)
        if text.startswith("/tmp/browser-use-downloads-"):
            unique_id = text.rsplit("-", 1)[-1]
            return _runtime_downloads_root() / unique_id
        return Path(text)

    validator.__globals__["Path"] = _catbot_patched_path


_patch_browser_use_tmp_downloads()

from .config import settings
from .exceptions import BrowserError, LLMProviderError, MCPBrowserUseError
from .providers import get_llm
from .server import main, serve

__all__ = [
    "BrowserError",
    "LLMProviderError",
    "MCPBrowserUseError",
    "get_llm",
    "main",
    "serve",
    "settings",
]
