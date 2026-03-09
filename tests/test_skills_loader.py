"""Tests for skills manifest loader parsing behavior."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from src.skills.loader import SkillManifestLoader


def _manifest_dir() -> Path:
    path = Path(f"skills_loader_test_{uuid.uuid4().hex}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_manifest_loader_parses_enabled_string_false() -> None:
    manifest_dir = _manifest_dir()
    try:
        manifest_path = manifest_dir / "demo.skill.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "name": "demo",
                    "module": "src.skills.builtin.core_skill:create_skill",
                    "enabled": "false",
                }
            ),
            encoding="utf-8",
        )

        loader = SkillManifestLoader()
        manifest = loader.parse_manifest_file(manifest_path)
        assert manifest.enabled is False
    finally:
        shutil.rmtree(manifest_dir, ignore_errors=True)


def test_manifest_loader_parses_enabled_string_true() -> None:
    manifest_dir = _manifest_dir()
    try:
        manifest_path = manifest_dir / "demo.skill.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "name": "demo",
                    "module": "src.skills.builtin.core_skill:create_skill",
                    "enabled": "true",
                }
            ),
            encoding="utf-8",
        )

        loader = SkillManifestLoader()
        manifest = loader.parse_manifest_file(manifest_path)
        assert manifest.enabled is True
    finally:
        shutil.rmtree(manifest_dir, ignore_errors=True)
