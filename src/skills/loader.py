"""Manifest-based loading for CATBot skills."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseSkill
from .exceptions import SkillValidationError


@dataclass(frozen=True)
class SkillManifest:
    """Representation of a skill manifest file."""

    name: str
    module: str
    description: str = ""
    enabled: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)
    package_sources: List[str] = field(default_factory=list)
    path: Optional[Path] = None


def _load_python_target(path: str) -> Any:
    module_name, sep, attr = path.partition(":")
    if not module_name or not sep or not attr:
        raise SkillValidationError(
            "Manifest 'module' must be in format 'package.module:attribute'."
        )
    module = importlib.import_module(module_name)
    try:
        return getattr(module, attr)
    except AttributeError as exc:
        raise SkillValidationError(
            f"Unable to resolve '{attr}' from module '{module_name}'."
        ) from exc


class SkillManifestLoader:
    """Load skills from JSON manifests."""

    @staticmethod
    def _parse_enabled_flag(raw_enabled: Any, manifest_path: Path) -> bool:
        if isinstance(raw_enabled, bool):
            return raw_enabled
        if isinstance(raw_enabled, (int, float)):
            return bool(raw_enabled)
        if isinstance(raw_enabled, str):
            normalized = raw_enabled.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off", ""}:
                return False
        raise SkillValidationError(
            f"Manifest '{manifest_path}' field 'enabled' must be a boolean-like value."
        )

    def parse_manifest_file(self, path: str | Path) -> SkillManifest:
        manifest_path = Path(path)
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SkillValidationError(
                f"Invalid JSON in manifest '{manifest_path}': {exc}"
            ) from exc

        name = str(data.get("name", "")).strip()
        module = str(data.get("module", "")).strip()
        if not name:
            raise SkillValidationError(
                f"Manifest '{manifest_path}' missing required field: name"
            )
        if not module:
            raise SkillValidationError(
                f"Manifest '{manifest_path}' missing required field: module"
            )
        settings = data.get("settings", {})
        if settings is None:
            settings = {}
        if not isinstance(settings, dict):
            raise SkillValidationError(
                f"Manifest '{manifest_path}' field 'settings' must be an object."
            )
        package_sources_raw = data.get("package_sources", [])
        if package_sources_raw is None:
            package_sources_raw = []
        if not isinstance(package_sources_raw, list):
            raise SkillValidationError(
                f"Manifest '{manifest_path}' field 'package_sources' must be an array when provided."
            )
        package_sources: List[str] = []
        for raw in package_sources_raw:
            value = str(raw).strip()
            if not value:
                raise SkillValidationError(
                    f"Manifest '{manifest_path}' contains an empty package_sources entry."
                )
            package_sources.append(value)

        return SkillManifest(
            name=name,
            module=module,
            description=str(data.get("description", "")).strip(),
            enabled=self._parse_enabled_flag(data.get("enabled", True), manifest_path),
            settings=settings,
            package_sources=package_sources,
            path=manifest_path,
        )

    def load_skill(self, manifest: SkillManifest) -> Optional[BaseSkill]:
        if not manifest.enabled:
            return None

        target = _load_python_target(manifest.module)
        settings = dict(manifest.settings or {})

        if isinstance(target, BaseSkill):
            skill = target
        elif isinstance(target, type) and issubclass(target, BaseSkill):
            skill = target(**settings)
        elif callable(target):
            skill = target(**settings)
        else:
            raise SkillValidationError(
                f"Manifest target '{manifest.module}' did not resolve to a skill."
            )

        if not isinstance(skill, BaseSkill):
            raise SkillValidationError(
                f"Factory '{manifest.module}' must return BaseSkill instance."
            )

        if skill.name != manifest.name:
            raise SkillValidationError(
                f"Manifest name '{manifest.name}' does not match skill name '{skill.name}'."
            )
        return skill

    def discover_manifest_paths(self, directory: str | Path) -> List[Path]:
        base = Path(directory)
        if not base.exists():
            return []
        return sorted(base.glob("*.skill.json"))

    def load_all_from_directory(self, directory: str | Path) -> List[BaseSkill]:
        return [record[1] for record in self.load_all_records_from_directory(directory)]

    def load_all_records_from_directory(
        self, directory: str | Path
    ) -> List[Tuple[SkillManifest, BaseSkill]]:
        records: List[Tuple[SkillManifest, BaseSkill]] = []
        for manifest_path in self.discover_manifest_paths(directory):
            manifest = self.parse_manifest_file(manifest_path)
            skill = self.load_skill(manifest)
            if skill is not None:
                records.append((manifest, skill))
        return records
