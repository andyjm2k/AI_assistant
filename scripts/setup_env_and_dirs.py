#!/usr/bin/env python3
"""
Create default directories and .env from template with project-root path substitution.
Run from project root or pass --project-root. Does not overwrite existing .env.
"""
import argparse
import os
import re
import shutil
import sys
from pathlib import Path

# Default project root = parent of scripts directory
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_ROOT = SCRIPT_DIR.parent

# Example prefix in .env.example to replace with actual project root (Windows)
# Update this if the example file uses a different canonical path
EXAMPLE_PREFIX_WIN = "C:\\Users\\andyj\\AI_assistant"
EXAMPLE_PREFIX_POSIX = "/home/user/AI_assistant"

# Env vars that contain paths we substitute with project root
PATH_ENV_VARS = frozenset({
    "MCP_RESEARCH_TOOL_SAVE_DIR",
    "MCP_AGENT_TOOL_SAVE_RECORDING_PATH",
    "MCP_AGENT_TOOL_HISTORY_PATH",
    "MCP_PATHS_DOWNLOADS",
    "MCP_SERVER_LOG_FILE",
    "MCP_BROWSER_TRACE_PATH",
})

# Directories to create under project root (align with proxy and .env)
REQUIRED_DIRS = ["scratch", "todo_data", "research", "memory_data"]
# Alternative name used in config/mcp_config.env.example
RESEARCH_OUTPUT_DIR = "research_output"


def _normalize_path_for_env(p: Path, on_windows: bool) -> str:
    """Return path string suitable for .env (backslashes on Windows)."""
    s = str(p.resolve())
    if on_windows:
        s = s.replace("/", "\\")
    return s


def _substitute_path_in_line(line: str, project_root: Path, on_windows: bool) -> str:
    """If line is KEY=VALUE and KEY is a path var, substitute value with project_root."""
    if "=" not in line or line.strip().startswith("#"):
        return line
    key, _, value = line.partition("=")
    key = key.strip()
    value = value.strip()
    if key not in PATH_ENV_VARS or not value:
        return line
    # Replace known example prefix with actual project root
    new_prefix = _normalize_path_for_env(project_root, on_windows)
    for old in (EXAMPLE_PREFIX_WIN, EXAMPLE_PREFIX_POSIX, project_root.as_posix(), str(project_root)):
        if value.startswith(old):
            suffix = value[len(old):].lstrip("\\/")
            new_value = new_prefix + (os.sep if on_windows else "/") + suffix.replace("/", os.sep)
            return f"{key}={new_value}\n"
    # If value is relative (./something), resolve to project root
    if value.startswith("./") or value.startswith(".\\"):
        rel = value.lstrip(".\\/")
        new_value = _normalize_path_for_env(project_root / rel, on_windows)
        return f"{key}={new_value}\n"
    return line


def create_dirs(project_root: Path) -> list[str]:
    """Create required directories; return list of created dir names."""
    created = []
    for name in REQUIRED_DIRS:
        d = project_root / name
        if not d.is_dir():
            d.mkdir(parents=True, exist_ok=True)
            created.append(name)
    # Also create research_output if used by config
    ro = project_root / RESEARCH_OUTPUT_DIR
    if not ro.is_dir():
        ro.mkdir(parents=True, exist_ok=True)
        created.append(RESEARCH_OUTPUT_DIR)
    return created


def setup_env(project_root: Path, env_path: Path, template_path: Path, force: bool) -> tuple[bool, str]:
    """
    Copy template to .env if missing (or force), with path substitution.
    Return (created_or_updated, message).
    """
    if env_path.exists() and not force:
        return False, "Existing .env left unchanged (use --force to overwrite)"
    if not template_path.exists():
        return False, f"Template not found: {template_path}"
    on_windows = os.name == "nt"
    content = template_path.read_text(encoding="utf-8", errors="replace")
    lines = []
    for line in content.splitlines(keepends=True) if "\n" in content else [content]:
        lines.append(_substitute_path_in_line(line, project_root, on_windows))
    env_path.write_text("".join(lines), encoding="utf-8")
    return True, "Created .env from template with project-root paths"


def main() -> int:
    """Create dirs and optionally .env; print summary."""
    parser = argparse.ArgumentParser(description="Create CATBot dirs and .env from template")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=DEFAULT_PROJECT_ROOT,
        help="Project root directory (default: parent of scripts/)",
    )
    parser.add_argument(
        "--no-env",
        action="store_true",
        help="Only create directories; do not create or update .env",
    )
    parser.add_argument(
        "--force-env",
        action="store_true",
        help="Overwrite existing .env with template (default: skip if .env exists)",
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    if not root.is_dir():
        print(f"Error: project root is not a directory: {root}", file=sys.stderr)
        return 1

    # Prefer .env.example at root, else config/mcp_config.env.example
    env_example = root / ".env.example"
    if not env_example.exists():
        env_example = root / "config" / "mcp_config.env.example"
    env_file = root / ".env"

    created_dirs = create_dirs(root)
    if created_dirs:
        print("Created directories:", ", ".join(created_dirs))
    else:
        print("Required directories already exist.")

    if not args.no_env:
        created, msg = setup_env(root, env_file, env_example, force=args.force_env)
        print(msg)
        if created:
            print("Edit .env with your API keys (OPENAI, BRAVE, TELEGRAM, etc.) before starting CATBot.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
