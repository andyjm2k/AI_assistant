"""Import/export support for CATBot .catbotskill packages."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional

from .exceptions import SkillPackageError
from .loader import SkillManifestLoader


def _ensure_safe_member_name(member_name: str) -> PurePosixPath:
    path = PurePosixPath(member_name)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise SkillPackageError(f"Unsafe archive member path: {member_name}")
    return path


def _module_to_source_path(module_target: str) -> Path:
    module_name, sep, _attribute = module_target.partition(":")
    if not module_name or not sep:
        raise SkillPackageError(
            "Manifest module must be in format 'package.module:attribute'."
        )
    return Path(*module_name.split(".")).with_suffix(".py")


@dataclass(frozen=True)
class SkillPackageExportResult:
    package_path: Path
    manifest_path: Path
    included_members: List[str]


@dataclass(frozen=True)
class SkillPackageImportResult:
    package_path: Path
    manifest_path: Path
    extracted_sources: List[Path]


class SkillPackageManager:
    """Create and extract .catbotskill archives."""

    def __init__(self, loader: Optional[SkillManifestLoader] = None) -> None:
        self.loader = loader or SkillManifestLoader()

    def export_manifest(
        self,
        manifest_path: str | Path,
        output_path: str | Path,
        *,
        include_sources: bool = True,
        source_root: str | Path = ".",
        overwrite: bool = False,
    ) -> SkillPackageExportResult:
        source_root_path = Path(source_root).resolve()
        manifest_file = Path(manifest_path).resolve()
        if not manifest_file.exists() or not manifest_file.is_file():
            raise SkillPackageError(f"Manifest not found: {manifest_file}")

        manifest = self.loader.parse_manifest_file(manifest_file)

        package_file = Path(output_path)
        if package_file.suffix.lower() != ".catbotskill":
            package_file = package_file.with_suffix(".catbotskill")
        package_file = package_file.resolve()

        if package_file.exists() and not overwrite:
            raise SkillPackageError(f"Package file already exists: {package_file}")
        package_file.parent.mkdir(parents=True, exist_ok=True)

        members: List[str] = []
        manifest_member = f"manifests/{manifest_file.name}"
        module_source_rel = _module_to_source_path(manifest.module)
        source_member = f"sources/{module_source_rel.as_posix()}"
        source_file = (source_root_path / module_source_rel).resolve()

        if include_sources:
            if not source_file.exists() or not source_file.is_file():
                raise SkillPackageError(
                    f"Source file for module '{manifest.module}' not found: {source_file}"
                )

        metadata: Dict[str, Any] = {
            "format": "catbotskill.v1",
            "name": manifest.name,
            "description": manifest.description,
            "module": manifest.module,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "manifest_member": manifest_member,
            "includes_sources": include_sources,
            "source_members": [source_member] if include_sources else [],
        }

        with zipfile.ZipFile(package_file, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "package.json",
                json.dumps(metadata, indent=2, ensure_ascii=True),
            )
            members.append("package.json")

            archive.writestr(manifest_member, manifest_file.read_text(encoding="utf-8"))
            members.append(manifest_member)

            if include_sources:
                archive.writestr(source_member, source_file.read_text(encoding="utf-8"))
                members.append(source_member)

        return SkillPackageExportResult(
            package_path=package_file,
            manifest_path=manifest_file,
            included_members=members,
        )

    def import_package(
        self,
        package_path: str | Path,
        manifest_dir: str | Path,
        *,
        source_root: str | Path = ".",
        overwrite: bool = False,
    ) -> SkillPackageImportResult:
        package_file = Path(package_path).resolve()
        if not package_file.exists() or not package_file.is_file():
            raise SkillPackageError(f"Package not found: {package_file}")

        manifest_dir_path = Path(manifest_dir).resolve()
        manifest_dir_path.mkdir(parents=True, exist_ok=True)
        source_root_path = Path(source_root).resolve()
        source_root_path.mkdir(parents=True, exist_ok=True)

        extracted_sources: List[Path] = []
        with zipfile.ZipFile(package_file, mode="r") as archive:
            names = archive.namelist()
            if "package.json" not in names:
                raise SkillPackageError("Invalid .catbotskill archive: missing package.json")

            manifest_members = [
                name for name in names if name.startswith("manifests/") and name.endswith(".skill.json")
            ]
            if len(manifest_members) != 1:
                raise SkillPackageError(
                    "Invalid .catbotskill archive: expected exactly one manifest under manifests/."
                )

            manifest_member = manifest_members[0]
            _ensure_safe_member_name(manifest_member)
            manifest_name = Path(manifest_member).name
            output_manifest = manifest_dir_path / manifest_name
            if output_manifest.exists() and not overwrite:
                raise SkillPackageError(f"Manifest already exists: {output_manifest}")
            output_manifest.write_text(archive.read(manifest_member).decode("utf-8"), encoding="utf-8")

            for member_name in names:
                if not member_name.startswith("sources/"):
                    continue
                member_path = _ensure_safe_member_name(member_name)
                relative_source = member_path.relative_to("sources")
                target = (source_root_path / relative_source).resolve()
                try:
                    target.relative_to(source_root_path)
                except ValueError as exc:
                    raise SkillPackageError(
                        f"Unsafe source extraction target for '{member_name}'."
                    ) from exc

                if target.exists() and not overwrite:
                    raise SkillPackageError(f"Source file already exists: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(archive.read(member_name).decode("utf-8"), encoding="utf-8")
                extracted_sources.append(target)

        self.loader.parse_manifest_file(output_manifest)
        return SkillPackageImportResult(
            package_path=package_file,
            manifest_path=output_manifest,
            extracted_sources=extracted_sources,
        )
