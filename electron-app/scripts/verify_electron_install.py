#!/usr/bin/env python3
"""
Basic verification for the CATBot Electron desktop avatar workspace.
"""

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ELECTRON_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = ELECTRON_ROOT.parent


REQUIRED_FILES = [
    ELECTRON_ROOT / "package.json",
    ELECTRON_ROOT / "main" / "main.js",
    ELECTRON_ROOT / "main" / "preload.js",
    ELECTRON_ROOT / "renderer" / "avatar" / "avatar.html",
    ELECTRON_ROOT / "renderer" / "avatar" / "avatar.js",
    ELECTRON_ROOT / "renderer" / "avatar" / "vrm-quality.js",
    ELECTRON_ROOT / "renderer" / "control-panel" / "control-panel.html",
    ELECTRON_ROOT / "renderer" / "control-panel" / "control-panel.js",
    ELECTRON_ROOT / "config" / "default-desktop-config.json",
]


def main() -> int:
    missing = [str(path) for path in REQUIRED_FILES if not path.exists()]
    if missing:
        print("Missing required Electron files:")
        for item in missing:
            print(" -", item)
        return 1

    config_path = ELECTRON_ROOT / "config" / "default-desktop-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("mode") not in {"vrm", "live2d"}:
        print(f"Unsupported desktop avatar mode: {config.get('mode')}")
        return 1

    model_path = config.get("modelPath", "")
    if model_path:
        resolved_model = PROJECT_ROOT / model_path
        if not resolved_model.exists():
            print(f"Configured model path does not exist: {resolved_model}")
            return 1

    env_example = ELECTRON_ROOT / ".env.example"
    if not env_example.exists():
        print("electron-app/.env.example missing")
        return 1

    print("Electron desktop avatar workspace verification OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
