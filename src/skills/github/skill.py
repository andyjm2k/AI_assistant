"""Built-in GitHub project management skill."""

from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path
from typing import Any, Dict, Sequence

from src.skills.base import BaseSkill, BaseTool
from src.skills.exceptions import SkillValidationError
from src.skills.models import SkillContext

from .service import GitHubIntegrationService

_ALLOWED_BUMPS = {"major", "minor", "patch"}


def _require_non_empty_string(arguments: Dict[str, Any], key: str) -> str:
    value = str(arguments.get(key, "")).strip()
    if not value:
        raise SkillValidationError(f"'{key}' is required.")
    return value


def _optional_string(arguments: Dict[str, Any], key: str) -> str | None:
    raw = arguments.get(key)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _validate_bump(value: Any, *, default: str = "patch") -> str:
    bump = str(value or default).strip().lower()
    if bump not in _ALLOWED_BUMPS:
        raise SkillValidationError(
            f"Invalid bump level '{value}'. Expected one of: major, minor, patch."
        )
    return bump


def _validate_pr_state(value: Any, *, default: str = "open") -> str:
    state = str(value or default).strip().lower()
    if state not in {"open", "closed", "all"}:
        raise SkillValidationError(
            f"Invalid pull request state '{value}'. Expected one of: open, closed, all."
        )
    return state


def _coerce_int(
    value: Any,
    *,
    default: int,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    if value is None:
        resolved = default
    elif isinstance(value, bool):
        resolved = int(value)
    elif isinstance(value, int):
        resolved = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            resolved = default
        else:
            try:
                resolved = int(raw)
            except ValueError as exc:
                raise SkillValidationError(f"Invalid integer value: {value}") from exc
    else:
        raise SkillValidationError(f"Invalid integer value: {value}")

    if min_value is not None and resolved < min_value:
        raise SkillValidationError(f"Integer value must be >= {min_value}: {resolved}")
    if max_value is not None and resolved > max_value:
        raise SkillValidationError(f"Integer value must be <= {max_value}: {resolved}")
    return resolved


def _to_jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


def _load_integration_service_class() -> type:
    return GitHubIntegrationService


def _create_service(arguments: Dict[str, Any]) -> tuple[Any, Path]:
    workspace_value = _optional_string(arguments, "workspace")
    workspace = Path(workspace_value or ".").resolve()
    service_class = _load_integration_service_class()
    factory = getattr(service_class, "from_env", None)
    if not callable(factory):
        raise SkillValidationError(
            "GitHubIntegrationService.from_env is required for skill integration."
        )
    try:
        service = factory(workspace=workspace)
    except TypeError:
        service = factory(workspace)
    return service, workspace


async def _invoke_service_method(
    service: Any,
    method_name: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    method = getattr(service, method_name, None)
    if not callable(method):
        raise SkillValidationError(
            f"GitHub integration service does not implement '{method_name}'."
        )
    result = await asyncio.to_thread(method, *args, **kwargs)
    return _to_jsonable(result)


class InitializeRepositoryTool(BaseTool):
    name = "initialize_repository"
    description = "Initialize a workspace as a git repository with identity and optional remote."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "remote_url": {"type": "string", "description": "Optional remote URL to set on the configured remote."},
        },
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        remote_url = _optional_string(arguments, "remote_url")
        if remote_url:
            result = await _invoke_service_method(
                service,
                "initialize_repository",
                remote_url=remote_url,
            )
        else:
            result = await _invoke_service_method(service, "initialize_repository")
        return {"workspace": str(workspace), "result": result}


class StatusTool(BaseTool):
    name = "status"
    description = "Return git branch/state details and current semantic version."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
        },
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        status = await _invoke_service_method(service, "status")
        return {"workspace": str(workspace), "status": status}


class FetchTool(BaseTool):
    name = "fetch"
    description = "Fetch branch and reference updates from a remote."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "remote_name": {"type": "string", "description": "Git remote name. Defaults to configured remote."},
        },
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        remote_name = _optional_string(arguments, "remote_name")
        result = await _invoke_service_method(service, "fetch", remote_name=remote_name)
        return {"workspace": str(workspace), "fetch": result}


class PullTool(BaseTool):
    name = "pull"
    description = "Pull remote branch changes into the current local branch."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "remote_name": {"type": "string", "description": "Git remote name. Defaults to configured remote."},
            "branch": {"type": "string", "description": "Optional branch name to pull."},
            "rebase": {"type": "boolean", "default": False, "description": "Use rebase strategy when true."},
        },
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        remote_name = _optional_string(arguments, "remote_name")
        branch = _optional_string(arguments, "branch")
        rebase = _coerce_bool(arguments.get("rebase"), default=False)
        result = await _invoke_service_method(
            service,
            "pull",
            remote_name=remote_name,
            branch=branch,
            rebase=rebase,
        )
        return {"workspace": str(workspace), "pull": result}


class PushTool(BaseTool):
    name = "push"
    description = "Push current or specified branch and optional tags to remote."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "remote_name": {"type": "string", "description": "Git remote name. Defaults to configured remote."},
            "branch": {"type": "string", "description": "Optional branch name to push."},
            "set_upstream": {"type": "boolean", "default": False, "description": "Set upstream tracking when true."},
            "tags": {"type": "boolean", "default": False, "description": "Push tags when true."},
        },
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        remote_name = _optional_string(arguments, "remote_name")
        branch = _optional_string(arguments, "branch")
        set_upstream = _coerce_bool(arguments.get("set_upstream"), default=False)
        tags = _coerce_bool(arguments.get("tags"), default=False)
        result = await _invoke_service_method(
            service,
            "push",
            remote_name=remote_name,
            branch=branch,
            set_upstream=set_upstream,
            tags=tags,
        )
        return {"workspace": str(workspace), "push": result}


class SyncTool(BaseTool):
    name = "sync"
    description = "Synchronize local branch with remote by pulling then pushing."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "remote_name": {"type": "string", "description": "Git remote name. Defaults to configured remote."},
            "branch": {"type": "string", "description": "Optional branch name to sync."},
            "rebase": {"type": "boolean", "default": False, "description": "Use rebase for pull when true."},
            "set_upstream": {"type": "boolean", "default": False, "description": "Set upstream tracking on push when true."},
            "tags": {"type": "boolean", "default": False, "description": "Push tags during sync when true."},
        },
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        remote_name = _optional_string(arguments, "remote_name")
        branch = _optional_string(arguments, "branch")
        rebase = _coerce_bool(arguments.get("rebase"), default=False)
        set_upstream = _coerce_bool(arguments.get("set_upstream"), default=False)
        tags = _coerce_bool(arguments.get("tags"), default=False)
        result = await _invoke_service_method(
            service,
            "sync",
            remote_name=remote_name,
            branch=branch,
            rebase=rebase,
            set_upstream=set_upstream,
            tags=tags,
        )
        return {"workspace": str(workspace), "sync": result}


class CreateBranchTool(BaseTool):
    name = "create_branch"
    description = "Create and checkout a new branch, optionally push and set upstream."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "branch": {"type": "string", "description": "New branch name."},
            "from_ref": {"type": "string", "description": "Optional source ref to branch from."},
            "push": {"type": "boolean", "default": False, "description": "Push new branch when true."},
            "set_upstream": {"type": "boolean", "default": True, "description": "Set upstream tracking when push is true."},
            "remote_name": {"type": "string", "description": "Git remote name for push operation."},
        },
        "required": ["branch"],
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        branch = _require_non_empty_string(arguments, "branch")
        from_ref = _optional_string(arguments, "from_ref")
        push = _coerce_bool(arguments.get("push"), default=False)
        set_upstream = _coerce_bool(arguments.get("set_upstream"), default=True)
        remote_name = _optional_string(arguments, "remote_name")
        result = await _invoke_service_method(
            service,
            "create_branch",
            branch,
            from_ref=from_ref,
            push=push,
            set_upstream=set_upstream,
            remote_name=remote_name,
        )
        return {"workspace": str(workspace), "branch": result}


class CheckoutBranchTool(BaseTool):
    name = "checkout_branch"
    description = "Checkout an existing local branch."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "branch": {"type": "string", "description": "Branch name to checkout."},
        },
        "required": ["branch"],
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        branch = _require_non_empty_string(arguments, "branch")
        result = await _invoke_service_method(service, "checkout_branch", branch)
        return {"workspace": str(workspace), "checkout": result}


class BumpVersionTool(BaseTool):
    name = "bump_version"
    description = "Bump semantic version in VERSION file by major/minor/patch without creating a commit."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "bump": {
                "type": "string",
                "enum": ["major", "minor", "patch"],
                "default": "patch",
                "description": "Semantic version bump level.",
            },
        },
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        bump = _validate_bump(arguments.get("bump"), default="patch")
        result = await _invoke_service_method(service, "bump_version", bump)
        return {"workspace": str(workspace), "version": result}


class CommitVersionedChangeTool(BaseTool):
    name = "commit_versioned_change"
    description = "Bump version, create commit, create tag, and optionally push commit/tags."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "message": {"type": "string", "description": "Commit message prefix."},
            "bump": {
                "type": "string",
                "enum": ["major", "minor", "patch"],
                "default": "patch",
                "description": "Semantic version bump level.",
            },
            "tag_prefix": {"type": "string", "default": "v", "description": "Tag prefix used for release tags."},
            "push": {"type": "boolean", "default": False, "description": "When true, push commit and tags."},
        },
        "required": ["message"],
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        message = _require_non_empty_string(arguments, "message")
        bump = _validate_bump(arguments.get("bump"), default="patch")
        tag_prefix = _optional_string(arguments, "tag_prefix") or "v"
        push = _coerce_bool(arguments.get("push"), default=False)
        result = await _invoke_service_method(
            service,
            "commit_versioned_change",
            message,
            bump=bump,
            tag_prefix=tag_prefix,
            push=push,
        )
        return {"workspace": str(workspace), "commit": result}


class CreatePullRequestTool(BaseTool):
    name = "create_pull_request"
    description = "Create a pull request using configured GitHub credentials."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "title": {"type": "string", "description": "Pull request title."},
            "head": {"type": "string", "description": "Head branch name to merge from."},
            "base": {"type": "string", "description": "Base branch name. Defaults to configured default branch."},
            "body": {"type": "string", "default": "", "description": "Pull request body text."},
        },
        "required": ["title", "head"],
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        title = _require_non_empty_string(arguments, "title")
        head = _require_non_empty_string(arguments, "head")
        base = _optional_string(arguments, "base")
        body = _optional_string(arguments, "body") or ""
        result = await _invoke_service_method(
            service,
            "create_pull_request",
            title,
            head,
            body=body,
            base=base,
        )
        return {"workspace": str(workspace), "pull_request": result}


class ListPullRequestsTool(BaseTool):
    name = "list_pull_requests"
    description = "List pull requests in the configured GitHub repository."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open", "description": "Pull request state filter."},
            "sort": {"type": "string", "default": "created", "description": "Sort field passed to GitHub API."},
            "direction": {"type": "string", "default": "desc", "description": "Sort direction passed to GitHub API."},
            "per_page": {"type": "integer", "minimum": 1, "maximum": 100, "default": 30, "description": "Items per page."},
            "page": {"type": "integer", "minimum": 1, "default": 1, "description": "Result page number."},
        },
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        state = _validate_pr_state(arguments.get("state"), default="open")
        sort = _optional_string(arguments, "sort") or "created"
        direction = _optional_string(arguments, "direction") or "desc"
        per_page = _coerce_int(arguments.get("per_page"), default=30, min_value=1, max_value=100)
        page = _coerce_int(arguments.get("page"), default=1, min_value=1)
        result = await _invoke_service_method(
            service,
            "list_pull_requests",
            state=state,
            sort=sort,
            direction=direction,
            per_page=per_page,
            page=page,
        )
        return {"workspace": str(workspace), "pull_requests": result}


class RepositoryInfoTool(BaseTool):
    name = "repository_info"
    description = "Return configured repository metadata and optional GitHub API rate-limit summary."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "include_rate_limit": {"type": "boolean", "default": False, "description": "Include API rate-limit core usage details."},
        },
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        include_rate_limit = _coerce_bool(arguments.get("include_rate_limit"), default=False)
        result = await _invoke_service_method(
            service,
            "repository_info",
            include_rate_limit=include_rate_limit,
        )
        return {"workspace": str(workspace), "repository": result}


class PublishReleaseTool(BaseTool):
    name = "publish_release"
    description = "Create a versioned commit and publish a GitHub release."
    input_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string", "description": "Repository path. Defaults to current working directory."},
            "title": {"type": "string", "description": "Release title. Defaults to generated version tag."},
            "notes": {"type": "string", "default": "", "description": "Release notes body."},
            "bump": {
                "type": "string",
                "enum": ["major", "minor", "patch"],
                "default": "patch",
                "description": "Semantic version bump level.",
            },
            "prerelease": {"type": "boolean", "default": False, "description": "Create as prerelease when true."},
            "push": {"type": "boolean", "default": True, "description": "Push commit/tags before release creation."},
        },
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        del context
        service, workspace = _create_service(arguments)
        title = _optional_string(arguments, "title")
        notes = _optional_string(arguments, "notes") or ""
        bump = _validate_bump(arguments.get("bump"), default="patch")
        prerelease = _coerce_bool(arguments.get("prerelease"), default=False)
        push = _coerce_bool(arguments.get("push"), default=True)
        result = await _invoke_service_method(
            service,
            "publish_release",
            title=title,
            notes=notes,
            bump=bump,
            prerelease=prerelease,
            push=push,
        )
        return {"workspace": str(workspace), "release": result}


class GitHubProjectManagerSkill(BaseSkill):
    name = "GitHubProjectManager"
    description = "Project lifecycle automation for git workflows, semantic versioning, pull requests, and releases."
    version = "1.2.0"
    tags = ["git", "github", "release", "versioning", "devops"]

    def create_tools(self) -> Sequence[BaseTool]:
        return [
            InitializeRepositoryTool(),
            StatusTool(),
            FetchTool(),
            PullTool(),
            PushTool(),
            SyncTool(),
            CreateBranchTool(),
            CheckoutBranchTool(),
            BumpVersionTool(),
            CommitVersionedChangeTool(),
            CreatePullRequestTool(),
            ListPullRequestsTool(),
            RepositoryInfoTool(),
            PublishReleaseTool(),
        ]


def create_skill() -> BaseSkill:
    return GitHubProjectManagerSkill()
