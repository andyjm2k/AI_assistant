#!/usr/bin/env python3
"""
Check that required prerequisites are installed for CATBot deployment.
Exits with 0 if all checks pass, non-zero and prints missing items otherwise.
Run from project root or any directory; does not require venv.
"""
import re
import subprocess
import sys
from pathlib import Path


def _run_cmd(cmd: list[str], capture: bool = True) -> tuple[bool, str]:
    """Run a command; return (success, stdout_or_stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=10,
        )
        out = (result.stdout or result.stderr or "").strip()
        return result.returncode == 0, out
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""


def check_python() -> tuple[bool, str]:
    """Require Python >= 3.11. Return (ok, message)."""
    # Prefer py launcher on Windows for 3.11+
    for cmd in ([sys.executable, "--version"], ["py", "-3.11", "--version"], ["python3", "--version"], ["python", "--version"]):
        ok, out = _run_cmd(cmd)
        if not ok:
            continue
        match = re.search(r"(\d+)\.(\d+)", out)
        if match:
            major, minor = int(match.group(1)), int(match.group(2))
            if major > 3 or (major == 3 and minor >= 11):
                return True, f"Python {major}.{minor} found"
        break
    return False, "Python 3.11+ required. Get it from https://www.python.org/downloads/"


def check_node() -> tuple[bool, str]:
    """Require Node.js >= 16. Return (ok, message)."""
    ok, out = _run_cmd(["node", "-v"])
    if not ok:
        return False, "Node.js required (v16+). Get it from https://nodejs.org/"
    match = re.search(r"v(\d+)", out)
    if match and int(match.group(1)) >= 16:
        return True, f"Node.js {out.strip()} found"
    return False, "Node.js v16+ required. Get it from https://nodejs.org/"


def check_git() -> tuple[bool, str]:
    """Require Git. Return (ok, message)."""
    ok, out = _run_cmd(["git", "--version"])
    if ok:
        return True, out.split("\n")[0] if out else "Git found"
    return False, "Git required for clone/submodule. Get it from https://git-scm.com/"


def check_uv() -> tuple[bool, str]:
    """Require uv (for mcp-browser-use). Return (ok, message)."""
    ok, out = _run_cmd(["uv", "--version"])
    if ok:
        return True, out.split("\n")[0] if out else "uv found"
    return False, "uv required for mcp-browser-use. Install: pip install uv, or https://github.com/astral-sh/uv"


def main() -> int:
    """Run all prerequisite checks; print results and exit 0 iff all pass."""
    checks = [
        ("Python 3.11+", check_python),
        ("Node.js 16+", check_node),
        ("Git", check_git),
        ("uv", check_uv),
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
        print("\nFix the missing prerequisites above, then run the installer again.")
        return 1
    print("\nAll prerequisites satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
