"""Rebuild CATBot memory embeddings with the configured pinned model."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.memory.memory_manager import MemoryManager


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default=None)
    parser.add_argument("--storage-path", default="./memory_data")
    parser.add_argument("--backup-root", default="./backups")
    args = parser.parse_args()

    manager = MemoryManager(storage_path=args.storage_path)
    try:
        backup_root = Path(args.backup_root).resolve()
        backup_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = backup_root / f"memory-pre-reembed-{timestamp}.sqlite3"
        manager.repository.backup(backup_path)
        result = await manager.rebuild_embeddings(args.namespace)
    finally:
        manager.close()
    print(json.dumps({"backup": str(backup_path), **result}, indent=2))
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
