"""Audit, back up, and migrate CATBot legacy memory into SQLite."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.memory.memory_manager import MemoryManager
from src.memory.migration import LegacyMemoryMigrator, audit_legacy_memory, backup_legacy_memory


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--storage-path", default="./memory_data")
    parser.add_argument("--backup-root", default="./backups")
    parser.add_argument("--legacy-owner", default=None)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--skip-backup", action="store_true")
    args = parser.parse_args()

    audit = audit_legacy_memory(args.storage_path)
    output = {"audit": audit}
    if args.audit_only:
        print(json.dumps(output, indent=2))
        return 0
    if not args.skip_backup:
        output["backup"] = backup_legacy_memory(args.storage_path, args.backup_root)

    manager = MemoryManager(storage_path=args.storage_path)
    try:
        migrator = LegacyMemoryMigrator(
            manager.repository,
            manager.personal_memory,
            manager.task_learning,
        )
        output["migration"] = await migrator.migrate(
            args.storage_path,
            legacy_owner=args.legacy_owner,
        )
    finally:
        manager.repository.close()
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
