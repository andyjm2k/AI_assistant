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


def _module_name_to_path(module_name: str) -> Path:
    return Path(*module_name.split("."))


def _resolve_package_source_members(source_root: Path, package_source: str) -> List[Path]:
    package_source = package_source.strip()
    if not package_source:
        raise SkillPackageError("Package source entry cannot be empty.")

    base_path = _module_name_to_path(package_source)
    file_candidate = (source_root / base_path).with_suffix(".py")
    if file_candidate.exists() and file_candidate.is_file():
        return [file_candidate.relative_to(source_root)]

    dir_candidate = source_root / base_path
    if dir_candidate.exists() and dir_candidate.is_dir():
        members = sorted(
            path.relative_to(source_root)
            for path in dir_candidate.rglob("*.py")
            if path.is_file()
        )
        if members:
            return members
        raise SkillPackageError(
            f"Package source directory contains no Python files: {dir_candidate}"
        )

    raise SkillPackageError(
        f"Package source '{package_source}' did not resolve to a Python module or package under {source_root}."
    )


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
        source_rel_paths: List[Path] = [module_source_rel]
        for package_source in manifest.package_sources:
            source_rel_paths.extend(
                _resolve_package_source_members(source_root_path, package_source)
            )

        unique_source_rel_paths: List[Path] = []
        seen: set[str] = set()
        for rel_path in source_rel_paths:
            key = rel_path.as_posix()
            if key in seen:
                continue
            seen.add(key)
            unique_source_rel_paths.append(rel_path)

        source_members = [f"sources/{path.as_posix()}" for path in unique_source_rel_paths]
        source_files = [(source_root_path / path).resolve() for path in unique_source_rel_paths]

        if include_sources:
            for source_file in source_files:
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
            "source_members": source_members if include_sources else [],
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
                for source_member, source_file in zip(source_members, source_files):
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
