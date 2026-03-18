"""FastAPI routes for CATBot skill management."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .bootstrap import create_default_skill_manager
from .exceptions import SkillFrameworkError, SkillNotFoundError, ToolNotFoundError
from .manager import SkillManager
from .models import SkillContext, SkillSpec, ToolExecutionResult, ToolSpec


class SkillSpecPayload(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0.0"
    tags: List[str] = Field(default_factory=list)
    tool_names: List[str] = Field(default_factory=list)


class ToolSpecPayload(BaseModel):
    skill_name: str
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    qualified_name: str


class SkillContextPayload(BaseModel):
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    scratch_dir: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LoadManifestsRequest(BaseModel):
    directory: Optional[str] = None
    replace: bool = False


class ExecuteToolRequest(BaseModel):
    tool_name: str = Field(..., min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)
    context: SkillContextPayload = Field(default_factory=SkillContextPayload)
    raise_errors: bool = False


class ExportSkillPackageRequest(BaseModel):
    skill_name: str = Field(..., min_length=1)
    output_path: str = Field(..., min_length=1)
    include_sources: bool = True
    source_root: str = "."
    overwrite: bool = False


class ExportSkillPackageResponse(BaseModel):
    success: bool
    package_path: str
    manifest_path: str
    included_members: List[str] = Field(default_factory=list)


class ImportSkillPackageRequest(BaseModel):
    package_path: str = Field(..., min_length=1)
    manifest_dir: Optional[str] = None
    source_root: str = "."
    load_skill: bool = True
    replace: bool = False
    overwrite: bool = False


class ImportSkillPackageResponse(BaseModel):
    success: bool
    package_path: str
    manifest_path: str
    extracted_sources: List[str] = Field(default_factory=list)
    loaded_skill: Optional[SkillSpecPayload] = None


class SkillsResponse(BaseModel):
    skills: List[SkillSpecPayload]


class ToolsResponse(BaseModel):
    tools: List[ToolSpecPayload]


class OpenAIToolsResponse(BaseModel):
    tools: List[Dict[str, Any]]


class MCPToolsResponse(BaseModel):
    tools: List[Dict[str, Any]]


class LoadManifestsResponse(BaseModel):
    directory: str
    loaded: List[SkillSpecPayload]


class UnregisterSkillResponse(BaseModel):
    success: bool
    message: str
    skill_name: str


class ExecuteToolResponse(BaseModel):
    success: bool
    message: str = ""
    data: Any = None
    error_code: Optional[str] = None
    tool_name: Optional[str] = None


def _to_skill_payload(spec: SkillSpec) -> SkillSpecPayload:
    return SkillSpecPayload(
        name=spec.name,
        description=spec.description,
        version=spec.version,
        tags=list(spec.tags),
        tool_names=list(spec.tool_names),
    )


def _to_tool_payload(spec: ToolSpec) -> ToolSpecPayload:
    return ToolSpecPayload(
        skill_name=spec.skill_name,
        name=spec.name,
        description=spec.description,
        input_schema=dict(spec.input_schema),
        tags=list(spec.tags),
        qualified_name=spec.qualified_name,
    )


def _to_skill_context(payload: SkillContextPayload) -> SkillContext:
    scratch_dir = Path(payload.scratch_dir) if payload.scratch_dir else None
    return SkillContext(
        conversation_id=payload.conversation_id,
        user_id=payload.user_id,
        scratch_dir=scratch_dir,
        metadata=dict(payload.metadata),
    )


def _filter_overlapping_file_tools(
    tools: List[Dict[str, Any]],
    *,
    openai_schema: bool,
    include_overlapping_file_tools: bool,
) -> List[Dict[str, Any]]:
    return [tool for tool in tools if isinstance(tool, dict)]


def _raise_framework_http_error(exc: SkillFrameworkError) -> None:
    status_code = 404 if isinstance(exc, (SkillNotFoundError, ToolNotFoundError)) else 400
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


def create_skill_router(
    manager: SkillManager,
    auth_dependency: Optional[Callable[..., Any]] = None,
) -> APIRouter:
    dependencies = [Depends(auth_dependency)] if auth_dependency else None
    router = APIRouter(prefix="/v1/skills", tags=["skills"], dependencies=dependencies)

    @router.get("", response_model=SkillsResponse)
    async def list_skills() -> SkillsResponse:
        return SkillsResponse(skills=[_to_skill_payload(spec) for spec in manager.list_skills()])

    @router.get("/tools", response_model=ToolsResponse)
    async def list_tools() -> ToolsResponse:
        return ToolsResponse(tools=[_to_tool_payload(spec) for spec in manager.list_tools()])

    @router.get("/tools/openai", response_model=OpenAIToolsResponse)
    async def list_openai_tools(
        qualified_names: bool = True,
        include_overlapping_file_tools: bool = False,
    ) -> OpenAIToolsResponse:
        tools = manager.openai_tools(qualified_names=qualified_names)
        filtered = _filter_overlapping_file_tools(
            tools,
            openai_schema=True,
            include_overlapping_file_tools=include_overlapping_file_tools,
        )
        return OpenAIToolsResponse(tools=filtered)

    @router.get("/tools/mcp", response_model=MCPToolsResponse)
    async def list_mcp_tools(
        qualified_names: bool = True,
        include_overlapping_file_tools: bool = False,
    ) -> MCPToolsResponse:
        tools = manager.mcp_tools(qualified_names=qualified_names)
        filtered = _filter_overlapping_file_tools(
            tools,
            openai_schema=False,
            include_overlapping_file_tools=include_overlapping_file_tools,
        )
        return MCPToolsResponse(tools=filtered)

    @router.post("/manifests/load", response_model=LoadManifestsResponse)
    async def load_manifests(request: LoadManifestsRequest) -> LoadManifestsResponse:
        target = Path(request.directory) if request.directory else Path(__file__).parent / "manifests"
        if not target.exists() or not target.is_dir():
            raise HTTPException(
                status_code=404,
                detail=f"Manifest directory '{target}' not found.",
            )
        try:
            loaded = manager.load_manifests(target, replace=request.replace)
        except SkillFrameworkError as exc:
            _raise_framework_http_error(exc)
        return LoadManifestsResponse(
            directory=str(target),
            loaded=[_to_skill_payload(spec) for spec in loaded],
        )

    @router.post("/tools/execute", response_model=ExecuteToolResponse)
    async def execute_tool(request: ExecuteToolRequest) -> ExecuteToolResponse:
        context = _to_skill_context(request.context)
        try:
            result = await manager.execute_tool(
                tool_name=request.tool_name,
                arguments=request.arguments,
                context=context,
                raise_errors=request.raise_errors,
            )
        except SkillFrameworkError as exc:
            _raise_framework_http_error(exc)

        return ExecuteToolResponse(**_result_to_payload(result))

    @router.post("/packages/export", response_model=ExportSkillPackageResponse)
    async def export_package(request: ExportSkillPackageRequest) -> ExportSkillPackageResponse:
        try:
            export_result = manager.export_skill_package(
                skill_name=request.skill_name,
                output_path=request.output_path,
                include_sources=request.include_sources,
                source_root=request.source_root,
                overwrite=request.overwrite,
            )
        except SkillFrameworkError as exc:
            _raise_framework_http_error(exc)
        return ExportSkillPackageResponse(
            success=True,
            package_path=str(export_result.package_path),
            manifest_path=str(export_result.manifest_path),
            included_members=list(export_result.included_members),
        )

    @router.post("/packages/import", response_model=ImportSkillPackageResponse)
    async def import_package(request: ImportSkillPackageRequest) -> ImportSkillPackageResponse:
        target_manifest_dir = (
            Path(request.manifest_dir)
            if request.manifest_dir
            else Path(__file__).parent / "manifests"
        )
        try:
            package_result, loaded_spec = manager.import_skill_package(
                package_path=request.package_path,
                manifest_dir=target_manifest_dir,
                source_root=request.source_root,
                load_skill=request.load_skill,
                replace=request.replace,
                overwrite=request.overwrite,
            )
        except SkillFrameworkError as exc:
            _raise_framework_http_error(exc)

        payload_skill = _to_skill_payload(loaded_spec) if loaded_spec else None
        return ImportSkillPackageResponse(
            success=True,
            package_path=str(package_result.package_path),
            manifest_path=str(package_result.manifest_path),
            extracted_sources=[str(path) for path in package_result.extracted_sources],
            loaded_skill=payload_skill,
        )

    @router.delete("/{skill_name}", response_model=UnregisterSkillResponse)
    async def unregister_skill(skill_name: str) -> UnregisterSkillResponse:
        try:
            manager.registry.unregister_skill(skill_name)
        except SkillFrameworkError as exc:
            _raise_framework_http_error(exc)
        return UnregisterSkillResponse(
            success=True,
            message=f"Skill '{skill_name}' unregistered.",
            skill_name=skill_name,
        )

    return router


def _result_to_payload(result: ToolExecutionResult) -> Dict[str, Any]:
    payload = result.to_dict()
    payload.setdefault("error_code", result.error_code)
    payload.setdefault("tool_name", result.tool_name)
    return payload


def create_skill_server_app(
    manager: Optional[SkillManager] = None,
    manifest_dir: Optional[str | Path] = None,
    auth_dependency: Optional[Callable[..., Any]] = None,
) -> FastAPI:
    resolved_manager = manager or create_default_skill_manager(manifest_dir=manifest_dir)
    app = FastAPI(title="CATBot Skill Server", version="1.0.0")
    app.include_router(
        create_skill_router(resolved_manager, auth_dependency=auth_dependency)
    )

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    return app


app = create_skill_server_app()
