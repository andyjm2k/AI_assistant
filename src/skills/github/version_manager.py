"""Semantic version management utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .errors import VersionError
from .models import BumpLevel, VersionChange

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$"
)


@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: str | None = None
    build: str | None = None

    def bump(self, level: BumpLevel) -> "SemVer":
        if level == "major":
            return SemVer(self.major + 1, 0, 0)
        if level == "minor":
            return SemVer(self.major, self.minor + 1, 0)
        if level == "patch":
            return SemVer(self.major, self.minor, self.patch + 1)
        raise VersionError(f"Unsupported bump level: {level}")

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base += f"-{self.prerelease}"
        if self.build:
            base += f"+{self.build}"
        return base


class VersionManager:
    """Reads and updates a semantic VERSION file."""

    def __init__(self, repo_path: Path, version_file: str = "VERSION") -> None:
        self.repo_path = Path(repo_path).resolve()
        self.version_path = self.repo_path / version_file

    def ensure_exists(self, default: str = "0.1.0") -> str:
        if self.version_path.exists():
            return self.current_version()
        self.set_version(default)
        return default

    def current_version(self) -> str:
        if not self.version_path.exists():
            raise VersionError(f"Version file does not exist: {self.version_path}")
        raw = self.version_path.read_text(encoding="utf-8").strip()
        self.parse(raw)
        return raw

    def parse(self, version: str) -> SemVer:
        match = SEMVER_RE.match(version.strip())
        if not match:
            raise VersionError(f"Invalid semantic version: {version}")
        major, minor, patch, prerelease, build = match.groups()
        return SemVer(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease,
            build=build,
        )

    def set_version(self, version: str) -> str:
        parsed = self.parse(version)
        self.version_path.parent.mkdir(parents=True, exist_ok=True)
        self.version_path.write_text(f"{parsed}\n", encoding="utf-8")
        return str(parsed)

    def bump(self, level: BumpLevel) -> VersionChange:
        previous = self.ensure_exists()
        updated = str(self.parse(previous).bump(level))
        self.set_version(updated)
        return VersionChange(previous=previous, current=updated, bump=level)

