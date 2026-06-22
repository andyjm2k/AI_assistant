#!/usr/bin/env python3
"""Install optional workflow backend dependencies selected in .env."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def _load_env_values(path: Path | None = None) -> dict[str, str]:
    path = ENV_FILE if path is None else path
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _ag2_available() -> tuple[bool, str]:
    try:
        import autogen  # type: ignore

        agentchat = getattr(autogen, "agentchat", None)
        required = ["AssistantAgent", "UserProxyAgent", "GroupChat", "GroupChatManager"]
        missing = [
            name
            for name in required
            if not (hasattr(autogen, name) or (agentchat is not None and hasattr(agentchat, name)))
        ]
        has_register = hasattr(autogen, "register_function") or (
            agentchat is not None and hasattr(agentchat, "register_function")
        )
        if missing or not has_register:
            detail = ", ".join(missing + ([] if has_register else ["register_function"]))
            return False, f"installed autogen package is missing AG2 APIs: {detail}"
        return True, "AG2 import OK"
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    values = _load_env_values()
    framework = (values.get("WORKFLOW_FRAMEWORK") or "autogen").strip().lower() or "autogen"
    if framework != "ag2":
        print(f"Workflow backend is {framework}; no optional AG2 install needed.")
        return 0

    available, message = _ag2_available()
    if available:
        print(message)
        return 0

    if str(os.getenv("CATBOT_SKIP_AG2_INSTALL") or "").strip().lower() in {"1", "true", "yes", "y", "on"}:
        print(f"AG2 install skipped by CATBOT_SKIP_AG2_INSTALL. Current status: {message}")
        return 1

    print(f"AG2 selected but not available: {message}")
    print('Installing optional workflow backend dependency: ag2[openai]')
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "ag2[openai]"],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        print('Failed to install ag2[openai]. Install it manually or set WORKFLOW_FRAMEWORK=autogen.')
        return result.returncode

    available, message = _ag2_available()
    if not available:
        print(f"AG2 installed but verification still failed: {message}")
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
