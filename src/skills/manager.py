"""High-level manager for CATBot's modular skill framework."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseSkill
from .exceptions import SkillNotFoundError
from .executor import SkillExecutor
from .loader import SkillManifestLoader
from .models import SkillContext, SkillSpec, ToolExecutionResult, ToolSpec
from .package import SkillPackageExportResult, SkillPackageImportResult, SkillPackageManager
from .registry import SkillRegistry


class SkillManager:
    """Coordinate skill loading, registration, and execution."""

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        loader: Optional[SkillManifestLoader] = None,
        executor: Optional[SkillExecutor] = None,
    ) -> None:
        self.registry = registry or SkillRegistry()
        self.loader = loader or SkillManifestLoader()
        self.executor = executor or SkillExecutor(self.registry)
        self.packager = SkillPackageManager(self.loader)
        self._manifest_paths: Dict[str, Path] = {}

    @classmethod
    def from_manifest_directory(cls, directory: str | Path) -> "SkillManager":
        manager = cls()
        manager.load_manifests(directory)
        return manager

    def register_skill(self, skill: BaseSkill, replace: bool = False) -> SkillSpec:
        return self.registry.register_skill(skill, replace=replace)

    def load_manifests(self, directory: str | Path, replace: bool = False) -> List[SkillSpec]:
        loaded_specs: List[SkillSpec] = []
        for manifest, skill in self.loader.load_all_records_from_directory(directory):
            spec = self.register_skill(skill, replace=replace)
            if manifest.path is not None:
                self._manifest_paths[spec.name] = manifest.path
            loaded_specs.append(spec)
        return loaded_specs

    def list_skills(self) -> List[SkillSpec]:
        return self.registry.list_skill_specs()

    def list_tools(self) -> List[ToolSpec]:
        return self.registry.list_tool_specs()

    def openai_tools(self, qualified_names: bool = True) -> List[Dict[str, Any]]:
        return self.registry.list_openai_tools(qualified_names=qualified_names)

    def mcp_tools(self, qualified_names: bool = True) -> List[Dict[str, Any]]:
        return self.registry.list_mcp_tools(qualified_names=qualified_names)

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[SkillContext] = None,
        raise_errors: bool = False,
    ) -> ToolExecutionResult:
        return await self.executor.execute(
            tool_name=tool_name,
            arguments=arguments,
            context=context,
            raise_errors=raise_errors,
        )

    def manifest_path_for_skill(self, skill_name: str) -> Optional[Path]:
        return self._manifest_paths.get(skill_name)

    def export_skill_package(
        self,
        skill_name: str,
        output_path: str | Path,
        *,
        include_sources: bool = True,
        source_root: str | Path = ".",
        overwrite: bool = False,
    ) -> SkillPackageExportResult:
        manifest_path = self.manifest_path_for_skill(skill_name)
        if manifest_path is None:
            raise SkillNotFoundError(
                f"Skill '{skill_name}' is not associated with a loaded manifest."
            )
        return self.packager.export_manifest(
            manifest_path=manifest_path,
            output_path=output_path,
            include_sources=include_sources,
            source_root=source_root,
            overwrite=overwrite,
        )

    def import_skill_package(
        self,
        package_path: str | Path,
        manifest_dir: str | Path,
        *,
        source_root: str | Path = ".",
        load_skill: bool = True,
        replace: bool = False,
        overwrite: bool = False,
    ) -> Tuple[SkillPackageImportResult, Optional[SkillSpec]]:
        package_result = self.packager.import_package(
            package_path=package_path,
            manifest_dir=manifest_dir,
            source_root=source_root,
            overwrite=overwrite,
        )
        loaded_spec: Optional[SkillSpec] = None
        if load_skill:
            manifest = self.loader.parse_manifest_file(package_result.manifest_path)
            skill = self.loader.load_skill(manifest)
            if skill is not None:
                loaded_spec = self.register_skill(skill, replace=replace)
                if manifest.path is not None:
                    self._manifest_paths[loaded_spec.name] = manifest.path
        return package_result, loaded_spec
