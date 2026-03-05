from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from src.skills.github.errors import VersionError
from src.skills.github.version_manager import VersionManager


def _make_local_temp_dir() -> Path:
    base = Path("scratch") / "_github_skill_version_manager_tests"
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"case_{uuid.uuid4().hex}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def test_ensure_exists_creates_default_version_file() -> None:
    tmp_dir = _make_local_temp_dir()
    try:
        manager = VersionManager(tmp_dir)
        version = manager.ensure_exists()
        assert version == "0.1.0"
        assert (tmp_dir / "VERSION").read_text(encoding="utf-8").strip() == "0.1.0"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_bump_patch_minor_major() -> None:
    tmp_dir = _make_local_temp_dir()
    try:
        manager = VersionManager(tmp_dir)
        manager.set_version("1.2.3")

        patch = manager.bump("patch")
        assert patch.previous == "1.2.3"
        assert patch.current == "1.2.4"

        minor = manager.bump("minor")
        assert minor.previous == "1.2.4"
        assert minor.current == "1.3.0"

        major = manager.bump("major")
        assert major.previous == "1.3.0"
        assert major.current == "2.0.0"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_invalid_version_raises() -> None:
    tmp_dir = _make_local_temp_dir()
    try:
        manager = VersionManager(tmp_dir)
        with pytest.raises(VersionError):
            manager.set_version("one.two.three")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
