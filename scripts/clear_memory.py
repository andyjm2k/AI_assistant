"""Back up and clear a single CATBot memory namespace."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.memory.memory_manager import MemoryManager


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--storage-path", default="./memory_data")
    parser.add_argument("--backup-root", default="./backups")
    parser.add_argument("--keep-task-data", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("--confirm is required")

    manager = MemoryManager(storage_path=args.storage_path)
    try:
        backup_dir = Path(args.backup_root).resolve()
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = backup_dir / f"memory-{args.namespace}-{timestamp}.sqlite3"
        manager.repository.backup(backup_path)
        deleted = manager.clear_namespace(
            args.namespace,
            include_task_data=not args.keep_task_data,
        )
    finally:
        manager.repository.close()
    print(json.dumps({"backup": str(backup_path), "deleted": deleted}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
