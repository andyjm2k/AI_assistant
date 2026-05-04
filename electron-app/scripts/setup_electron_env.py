#!/usr/bin/env python3
"""
Create Electron desktop companion config folders and .env from template.
"""

import argparse
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ELECTRON_ROOT = SCRIPT_DIR.parent
CONFIG_DIR = ELECTRON_ROOT / "config"


def ensure_layout() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def setup_env(force: bool = False) -> bool:
    template = ELECTRON_ROOT / ".env.example"
    env_file = ELECTRON_ROOT / ".env"
    if env_file.exists() and not force:
        return False
    env_file.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare CATBot Electron desktop config")
    parser.add_argument("--force-env", action="store_true", help="Overwrite existing electron-app/.env")
    args = parser.parse_args()

    ensure_layout()
    created = setup_env(force=args.force_env)
    print("Electron config layout ready.")
    if created:
        print("Created electron-app/.env from template.")
    else:
        print("Existing electron-app/.env left unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
