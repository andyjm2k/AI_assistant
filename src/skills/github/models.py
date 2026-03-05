"""Data models for git and version operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


BumpLevel = Literal["major", "minor", "patch"]


@dataclass(frozen=True)
class GitStatus:
    branch: str
    ahead_by: int = 0
    behind_by: int = 0
    staged: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CommitResult:
    commit_hash: str
    branch: str
    message: str


@dataclass(frozen=True)
class VersionChange:
    previous: str
    current: str
    bump: BumpLevel


@dataclass(frozen=True)
class VersionedCommit:
    commit: CommitResult
    tag: str
    version: VersionChange

