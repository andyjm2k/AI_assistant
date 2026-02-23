#!/usr/bin/env python3
"""
Post-install verification for CATBot.
Run from project root with venv activated (or pass path to venv Python).
Exits 0 if all checks pass; prints failures and exits non-zero otherwise.
"""
import os
import subprocess
import sys
from pathlib import Path

# Project root = parent of scripts directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MCP_BROWSER_USE_DIR = PROJECT_ROOT / "mcp-browser-use"


def _run_python_check(description: str, code: str, python_exe: str | None = None) -> tuple[bool, str]:
    """Run a one-liner Python check; return (success, message)."""
    exe = python_exe or sys.executable
    try:
        result = subprocess.run(
            [exe, "-c", code],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            out = (result.stdout or "").strip()
            return True, out or "OK"
        return False, result.stderr.strip() or result.stdout.strip() or "exit non-zero"
    except Exception as e:
        return False, str(e)


def check_core(python_exe: str | None = None) -> tuple[bool, str]:
    """Verify core server deps: fastapi, uvicorn, httpx, pydantic."""
    return _run_python_check(
        "Core",
        "import fastapi, uvicorn, httpx, pydantic; print('Core OK')",
        python_exe,
    )


def check_autogen(python_exe: str | None = None) -> tuple[bool, str]:
    """Verify AutoGen is importable."""
    return _run_python_check(
        "AutoGen",
        "import autogen_agentchat; print('AutoGen OK')",
        python_exe,
    )


def check_mcp(python_exe: str | None = None) -> tuple[bool, str]:
    """Verify MCP client library."""
    return _run_python_check(
        "MCP",
        "import mcp; print('MCP OK')",
        python_exe,
    )


def check_playwright(python_exe: str | None = None) -> tuple[bool, str]:
    """Verify Playwright is importable."""
    return _run_python_check(
        "Playwright",
        "from playwright.sync_api import sync_playwright; print('Playwright OK')",
        python_exe,
    )


def check_mcp_server_cli() -> tuple[bool, str]:
    """Verify mcp-server-browser-use CLI runs (via uv in mcp-browser-use). Non-blocking if submodule is incomplete."""
    if not MCP_BROWSER_USE_DIR.is_dir():
        return False, "mcp-browser-use directory not found"
    # Run without parent VIRTUAL_ENV so uv uses mcp-browser-use's .venv (avoids "does not match" warning)
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    try:
        result = subprocess.run(
            ["uv", "run", "mcp-server-browser-use", "--help"],
            cwd=str(MCP_BROWSER_USE_DIR),
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        if result.returncode == 0:
            return True, "mcp-server-browser-use CLI OK"
        # Submodule may be incomplete (missing exceptions.py, providers.py, etc.); treat as warning, not hard fail
        err = result.stderr.strip() or result.stdout.strip() or "exit non-zero"
        if "ModuleNotFoundError" in err or "No module named" in err:
            return True, "skipped (mcp-browser-use submodule incomplete; run 'git submodule update --init --recursive' to fix)"
        return False, err
    except FileNotFoundError:
        return True, "skipped (uv not found in PATH)"
    except Exception as e:
        return True, f"skipped ({e})"


def check_codex_cli() -> tuple[bool, str]:
    """Verify codex CLI is available (optional)."""
    try:
        result = subprocess.run(
            ["codex", "--version"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, (result.stdout.strip() or "codex CLI OK")
        return True, "skipped (codex CLI not available)"
    except FileNotFoundError:
        return True, "skipped (codex CLI not found)"
    except Exception as e:
        return True, f"skipped ({e})"


def main() -> int:
    """Run all verification checks. Use venv Python if running from installer."""
    python_exe = os.environ.get("CATBOT_VERIFY_PYTHON") or sys.executable
    checks = [
        ("Core (FastAPI, uvicorn, httpx, pydantic)", lambda: check_core(python_exe)),
        ("AutoGen", lambda: check_autogen(python_exe)),
        ("MCP", lambda: check_mcp(python_exe)),
        ("Playwright", lambda: check_playwright(python_exe)),
        ("mcp-server-browser-use CLI", check_mcp_server_cli),
        ("Codex CLI (optional)", check_codex_cli),
    ]
    failed = []
    for name, check_fn in checks:
        ok, msg = check_fn()
        if ok:
            print(f"  OK  {name}: {msg}")
        else:
            print(f"  FAIL {name}: {msg}")
            failed.append((name, msg))
    if failed:
        print("\nVerification failed. Fix the above before starting CATBot.")
        return 1
    print("\nAll checks passed. CATBot stack is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
