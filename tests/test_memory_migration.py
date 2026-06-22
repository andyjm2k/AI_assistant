import hashlib
import json
import math

import pytest

from src.memory.memory_manager import MemoryManager
from src.memory.migration import LegacyMemoryMigrator, backup_legacy_memory


class DeterministicEmbeddings:
    api_base = "https://embeddings.test/v1"
    model = "test-embedding-v1"

    async def get_embedding(self, text):
        digest = hashlib.sha256(str(text).encode("utf-8")).digest()
        vector = [float(value + 1) for value in digest[:8]]
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector]


@pytest.mark.asyncio
async def test_legacy_migration_is_backed_up_scoped_and_idempotent(tmp_path):
    legacy_path = tmp_path / "legacy"
    backup_root = tmp_path / "backups"
    legacy_path.mkdir()
    metadata = {
        "memories": [
            {
                "id": "owned-memory",
                "text": "User prefers concise answers.",
                "category": "preference",
                "user_key": "alice",
            },
            {
                "id": "unowned-memory",
                "text": "Unowned private fact.",
                "category": "profile_fact",
            },
            {
                "id": "derived-task-vector",
                "text": "A redundant task experience.",
                "category": "task_experience",
            },
        ]
    }
    events = [
        {
            "timestamp": "2026-01-02T03:04:05Z",
            "task_description": "Publish release notes",
            "status": "confirmed_complete",
            "summary": "Published successfully.",
            "tool_names": ["filesystem.write_text"],
            "metadata": {"user_key": "alice", "run_id": "legacy-run-1"},
        }
    ]
    metadata_path = legacy_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    events_path = legacy_path / "task_learning_events.jsonl"
    events_path.write_text(json.dumps(events[0]) + "\n", encoding="utf-8")

    backup = backup_legacy_memory(str(legacy_path), str(backup_root))
    assert backup["files"]["metadata.json"]["sha256"] == hashlib.sha256(
        metadata_path.read_bytes()
    ).hexdigest()
    assert backup["files"]["task_learning_events.jsonl"]["sha256"] == hashlib.sha256(
        events_path.read_bytes()
    ).hexdigest()

    manager = MemoryManager(
        storage_path=str(tmp_path / "database"),
        embeddings_client=DeterministicEmbeddings(),
    )
    migrator = LegacyMemoryMigrator(
        manager.repository,
        manager.personal_memory,
        manager.task_learning,
    )
    try:
        first = await migrator.migrate(str(legacy_path))
        second = await migrator.migrate(str(legacy_path))

        assert first["personal_imported"] == 1
        assert first["personal_quarantined"] == 1
        assert first["task_vectors_ignored"] == 1
        assert first["task_runs_imported"] == 1
        assert second["personal_imported"] == 0
        assert second["personal_unchanged"] == 1
        assert second["personal_quarantined"] == 0
        assert second["task_runs_updated"] == 1

        assert manager.count(namespace="alice") == 1
        assert len(manager.repository.list_task_runs("alice")) == 1
        assert manager.repository.metrics()["legacy_quarantined"] == 1
    finally:
        manager.close()
