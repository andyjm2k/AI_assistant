"""Git command wrapper for source control operations."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Sequence

from .errors import GitCommandError
from .models import CommitResult, GitStatus

REF_RE = re.compile(r"^[A-Za-z0-9._/\-]+$")


def _validate_ref_name(value: str, label: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise GitCommandError(f"{label} cannot be empty")
    if not REF_RE.match(trimmed):
        raise GitCommandError(f"Invalid {label}: {value}")
    if ".." in trimmed or "@{" in trimmed or trimmed.endswith(".lock"):
        raise GitCommandError(f"Unsafe {label}: {value}")
    if trimmed.startswith("/") or trimmed.endswith("/") or trimmed.startswith("."):
        raise GitCommandError(f"Unsafe {label}: {value}")
    return trimmed


class GitService:
    """Small, typed interface over git CLI."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = Path(repo_path).resolve()

    def _run(self, args: Sequence[str], check: bool = True) -> str:
        cmd = ["git", *args]
        result = subprocess.run(
            cmd,
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if check and result.returncode != 0:
            message = stderr or stdout or "Unknown git error"
            raise GitCommandError(f"git {' '.join(args)} failed: {message}")
        return stdout

    def is_repository(self) -> bool:
        output = self._run(["rev-parse", "--is-inside-work-tree"], check=False)
        return output == "true"

    def init(self, default_branch: str = "main") -> None:
        self._run(["init", "-b", _validate_ref_name(default_branch, "default branch")])

    def set_identity(self, name: str, email: str) -> None:
        self._run(["config", "user.name", name])
        self._run(["config", "user.email", email])

    def remote_add_or_set(self, remote_name: str, remote_url: str) -> None:
        remote = _validate_ref_name(remote_name, "remote name")
        existing = self._run(["remote"], check=False).splitlines()
        if remote in existing:
            self._run(["remote", "set-url", remote, remote_url])
        else:
            self._run(["remote", "add", remote, remote_url])

    def current_branch(self) -> str:
        return self._run(["rev-parse", "--abbrev-ref", "HEAD"])

    def status(self) -> GitStatus:
        lines = self._run(["status", "--porcelain", "--branch"]).splitlines()
        if not lines:
            return GitStatus(branch=self.current_branch())

        branch = "HEAD"
        ahead = 0
        behind = 0
        staged: list[str] = []
        changed: list[str] = []
        untracked: list[str] = []

        head_line = lines[0]
        if head_line.startswith("## "):
            branch_part = head_line[3:]
            branch = branch_part.split("...")[0]
            ahead_match = re.search(r"ahead (\d+)", branch_part)
            behind_match = re.search(r"behind (\d+)", branch_part)
            if ahead_match:
                ahead = int(ahead_match.group(1))
            if behind_match:
                behind = int(behind_match.group(1))

        for raw in lines[1:]:
            if len(raw) < 4:
                continue
            x, y = raw[0], raw[1]
            path = raw[3:]
            if raw.startswith("??"):
                untracked.append(path)
                continue
            if x != " ":
                staged.append(path)
            if y != " ":
                changed.append(path)

        return GitStatus(
            branch=branch,
            ahead_by=ahead,
            behind_by=behind,
            staged=staged,
            changed=changed,
            untracked=untracked,
        )

    def checkout(self, branch: str, create: bool = False, from_ref: str | None = None) -> None:
        branch_name = _validate_ref_name(branch, "branch name")
        if create:
            if from_ref:
                self._run(["checkout", "-b", branch_name, _validate_ref_name(from_ref, "source ref")])
            else:
                self._run(["checkout", "-b", branch_name])
            return
        self._run(["checkout", branch_name])

    def add(self, paths: Sequence[str] | None = None) -> None:
        if not paths:
            self._run(["add", "-A"])
            return
        self._run(["add", *paths])

    def commit(self, message: str, allow_empty: bool = False) -> CommitResult:
        args = ["commit", "-m", message]
        if allow_empty:
            args.append("--allow-empty")
        self._run(args)
        commit_hash = self._run(["rev-parse", "HEAD"])
        return CommitResult(commit_hash=commit_hash, branch=self.current_branch(), message=message)

    def fetch(self, remote_name: str = "origin") -> None:
        self._run(["fetch", _validate_ref_name(remote_name, "remote name")])

    def pull(self, remote_name: str = "origin", branch: str | None = None, rebase: bool = False) -> None:
        remote = _validate_ref_name(remote_name, "remote name")
        args = ["pull", remote]
        if branch:
            args.append(_validate_ref_name(branch, "branch name"))
        if rebase:
            args.append("--rebase")
        self._run(args)

    def push(
        self,
        remote_name: str = "origin",
        branch: str | None = None,
        set_upstream: bool = False,
        tags: bool = False,
    ) -> None:
        remote = _validate_ref_name(remote_name, "remote name")
        args = ["push", remote]
        if set_upstream:
            args.append("-u")
        if branch:
            args.append(_validate_ref_name(branch, "branch name"))
        if tags:
            args.append("--tags")
        self._run(args)

    def diff_name_only(self, base_ref: str, head_ref: str) -> list[str]:
        base = _validate_ref_name(base_ref, "base ref")
        head = _validate_ref_name(head_ref, "head ref")
        output = self._run(["diff", "--name-only", f"{base}...{head}"])
        return [line.strip() for line in output.splitlines() if line.strip()]

    def tag(self, name: str, message: str | None = None, annotated: bool = True, force: bool = False) -> None:
        tag_name = _validate_ref_name(name, "tag name")
        args = ["tag"]
        if force:
            args.append("-f")
        if annotated:
            args.extend(["-a", tag_name])
            args.extend(["-m", message or tag_name])
        else:
            args.append(tag_name)
        self._run(args)
