#!/usr/bin/env python3
"""
Start the mcp-server-browser-use HTTP server with this project's .env so that
the background MCP server uses the same LLM provider/model as the Flask HTTP bridge.

On Windows this launcher also keeps uv cache, temp files, and browser-use downloads
inside the repo to avoid permission issues with shared cache paths and ``\\tmp``.
Run from project root. Press Ctrl+C to stop the server.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Project root = parent of scripts directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MCP_BROWSER_USE_DIR = PROJECT_ROOT / "mcp-browser-use"
RUNTIME_DIR = MCP_BROWSER_USE_DIR / ".runtime"
TEMP_DIR = RUNTIME_DIR / "tmp"
UV_CACHE_DIR = RUNTIME_DIR / "uv-cache"
BROWSER_DOWNLOADS_DIR = RUNTIME_DIR / "browser-use-downloads"


def load_project_env(project_root: Path) -> None:
    """Load project .env so MCP_LLM_* matches the Flask server / proxy."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded env from: {env_file}")


def build_server_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Prepare a child-process environment with repo-local runtime paths."""
    env = dict(base_env or os.environ)

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    UV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    BROWSER_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # Force UTF-8 so browser-use "extract" and other code don't hit cp1252.
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    # Keep uv and browser-use off shared/system paths that are denied in this environment.
    env["UV_CACHE_DIR"] = str(UV_CACHE_DIR)
    env["TEMP"] = str(TEMP_DIR)
    env["TMP"] = str(TEMP_DIR)
    env["TMPDIR"] = str(TEMP_DIR)
    env["MCP_BROWSER_DOWNLOADS_DIR"] = str(BROWSER_DOWNLOADS_DIR)
    env["CATBOT_BROWSER_USE_RUNTIME_DIR"] = str(RUNTIME_DIR)

    # uv gets confused by the parent CATBot venv; force it to use mcp-browser-use's environment.
    env.pop("VIRTUAL_ENV", None)
    return env


def uv_command() -> list[str]:
    """Preferred startup path using uv."""
    return ["uv", "run", "mcp-server-browser-use", "server"]


def python_fallback_command() -> list[str]:
    """Fallback startup path using the bundled mcp-browser-use virtualenv directly."""
    venv_python = MCP_BROWSER_USE_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return [str(venv_python), "-m", "mcp_server_browser_use.cli", "server"]
    return [sys.executable, "-m", "mcp_server_browser_use.cli", "server"]


def run_command(command: list[str], env: dict[str, str]) -> int:
    """Run a command in the mcp-browser-use directory and return its exit code."""
    try:
        result = subprocess.run(command, cwd=str(MCP_BROWSER_USE_DIR), env=env, check=False)
        return int(result.returncode)
    except FileNotFoundError:
        return 127


def start_server() -> int:
    """Start the browser-use HTTP server, falling back when uv hits Windows permission issues."""
    if not MCP_BROWSER_USE_DIR.is_dir():
        print(f"Error: mcp-browser-use directory not found: {MCP_BROWSER_USE_DIR}")
        return 1

    load_project_env(PROJECT_ROOT)

    provider = os.environ.get("MCP_LLM_PROVIDER", "google")
    model = os.environ.get("MCP_LLM_MODEL_NAME", "")
    print(f"Starting MCP server with LLM: provider={provider}, model={model or '(default)'}")
    print("URL: http://127.0.0.1:8383/mcp")
    print(f"Using repo-local runtime dir: {RUNTIME_DIR}")
    print("Press Ctrl+C to stop.\n")

    env = build_server_env()
    print("Using UTF-8 plus repo-local uv/temp/download paths to avoid Windows permission issues.")

    uv_exit = run_command(uv_command(), env)
    if uv_exit == 0:
        return 0

    print("\nuv startup failed; retrying with the bundled mcp-browser-use virtualenv.")
    python_exit = run_command(python_fallback_command(), env)
    if python_exit == 0:
        return 0

    print("\nError: both uv and direct Python startup failed.")
    return python_exit or uv_exit or 1


if __name__ == "__main__":
    try:
        sys.exit(start_server())
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(130)
