"""Tests for .catbotskill package export/import APIs."""

from __future__ import annotations

import shutil
import uuid
import zipfile
from pathlib import Path

from src.skills import SkillManager


def test_export_creates_catbotskill_archive() -> None:
    temp_base = _create_workspace_temp_dir()
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    output = temp_base / "core-package.catbotskill"

    try:
        result = manager.export_skill_package(
            "core",
            output,
            include_sources=True,
            source_root=".",
        )

        assert result.package_path.exists()
        with zipfile.ZipFile(result.package_path, "r") as archive:
            names = set(archive.namelist())

        assert "package.json" in names
        assert "manifests/core.skill.json" in names
        assert "sources/src/skills/builtin/core_skill.py" in names
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


def test_import_extracts_manifest_and_source_files() -> None:
    temp_base = _create_workspace_temp_dir()
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    output = temp_base / "testkit-package.catbotskill"
    try:
        manager.export_skill_package(
            "testkit",
            output,
            include_sources=True,
            source_root=".",
        )

        importer = SkillManager()
        manifest_dir = temp_base / "manifests"
        source_root = temp_base / "source-root"
        package_result, loaded_spec = importer.import_skill_package(
            package_path=output,
            manifest_dir=manifest_dir,
            source_root=source_root,
            load_skill=False,
        )

        assert loaded_spec is None
        assert package_result.manifest_path.exists()
        assert (manifest_dir / "testkit.skill.json").exists()
        assert (source_root / "src" / "skills" / "builtin" / "test_skill.py").exists()
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


def test_import_with_load_skill_registers_skill() -> None:
    temp_base = _create_workspace_temp_dir()
    source_manager = SkillManager.from_manifest_directory("src/skills/manifests")
    package_file = temp_base / "core.catbotskill"
    try:
        source_manager.export_skill_package(
            "core",
            package_file,
            include_sources=False,
            source_root=".",
        )

        target_manager = SkillManager()
        package_result, loaded_spec = target_manager.import_skill_package(
            package_path=package_file,
            manifest_dir=temp_base / "imported-manifests",
            source_root=temp_base / "imported-source-root",
            load_skill=True,
        )

        assert package_result.manifest_path.exists()
        assert loaded_spec is not None
        assert loaded_spec.name == "core"
        assert any(spec.name == "core" for spec in target_manager.list_skills())
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


def _create_workspace_temp_dir() -> Path:
    base = Path("scratch") / f"skills-package-test-{uuid.uuid4().hex}"
    base.mkdir(parents=True, exist_ok=True)
    return base
