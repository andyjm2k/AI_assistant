"""Bootstrap helpers for initializing CATBot skills."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .manager import SkillManager


def create_default_skill_manager(
    manifest_dir: Optional[str | Path] = None,
) -> SkillManager:
    """Create a manager preloaded with manifests from src/skills/manifests."""
    manager = SkillManager()
    target = Path(manifest_dir) if manifest_dir else Path(__file__).parent / "manifests"
    manager.load_manifests(target)
    return manager

