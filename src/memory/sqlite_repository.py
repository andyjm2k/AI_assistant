"""Transactional SQLite repository for CATBot memory."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np

from .models import (
    EmbeddingRecord,
    MemoryRecord,
    RetrievalCandidate,
    TaskLessonRecord,
    TaskRunRecord,
    normalize_namespace,
    utc_now,
)


SCHEMA_VERSION = 3


class SQLiteMemoryRepository:
    """SQLite source of truth with FTS and vector blobs."""

    def __init__(self, storage_path: str = "./memory_data", database_name: Optional[str] = None):
        import os

        database_name = (
            database_name
            or os.getenv("MEMORY_DATABASE_NAME")
            or "memory.sqlite3"
        ).strip()
        database_file = Path(database_name)
        if (
            not database_name
            or database_file.is_absolute()
            or database_file.name != database_name
            or database_name in {".", ".."}
        ):
            raise ValueError("Memory database name must be a plain filename")
        root = Path(storage_path).resolve()
        root.mkdir(parents=True, exist_ok=True)
        self.database_path = root / database_file
        self._lock = RLock()
        self._connection = sqlite3.connect(
            str(self.database_path),
            check_same_thread=False,
            isolation_level=None,
            timeout=30.0,
        )
        self._connection.row_factory = sqlite3.Row
        self._fts_available = False
        self._configure()
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _configure(self) -> None:
        with self._lock:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA busy_timeout=30000")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self._connection
            except Exception:
                self._connection.execute("ROLLBACK")
                raise
            else:
                self._connection.execute("COMMIT")

    def _migrate(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL CHECK(length(trim(namespace)) > 0),
            kind TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT 'user',
            memory_key TEXT,
            text TEXT NOT NULL CHECK(length(trim(text)) > 0),
            normalized_text TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.8,
            importance REAL NOT NULL DEFAULT 0.5,
            source TEXT NOT NULL,
            source_ref TEXT,
            conversation_id TEXT,
            turn_id TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            valid_from TEXT,
            valid_to TEXT,
            expires_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_accessed_at TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            embedding_status TEXT NOT NULL DEFAULT 'pending',
            embedding_error TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_memories_namespace_kind_status
            ON memories(namespace, kind, status, updated_at DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_active_key
            ON memories(namespace, subject, kind, memory_key)
            WHERE status = 'active' AND memory_key IS NOT NULL AND memory_key <> '';
        CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_active_hash
            ON memories(namespace, kind, content_hash)
            WHERE status = 'active';

        CREATE TABLE IF NOT EXISTS memory_embeddings (
            memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            embedding_version TEXT NOT NULL,
            vector BLOB NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memory_embedding_identity
            ON memory_embeddings(provider, model, embedding_version, dimension);

        CREATE TABLE IF NOT EXISTS memory_extraction_runs (
            idempotency_key TEXT NOT NULL,
            namespace TEXT NOT NULL CHECK(length(trim(namespace)) > 0),
            conversation_id TEXT,
            user_message_id TEXT,
            assistant_message_id TEXT,
            extractor_model TEXT NOT NULL,
            extractor_version TEXT NOT NULL,
            status TEXT NOT NULL,
            candidate_count INTEGER NOT NULL DEFAULT 0,
            accepted_count INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(namespace, idempotency_key)
        );

        CREATE TABLE IF NOT EXISTS task_runs (
            run_id TEXT NOT NULL,
            namespace TEXT NOT NULL CHECK(length(trim(namespace)) > 0),
            task_id TEXT,
            task_fingerprint TEXT NOT NULL,
            task_description TEXT NOT NULL,
            status TEXT NOT NULL,
            confirmed_outcome TEXT,
            summary TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '',
            tool_usage_json TEXT NOT NULL DEFAULT '[]',
            source_phase TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            started_at TEXT,
            finished_at TEXT,
            recorded_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(namespace, run_id)
        );
        CREATE INDEX IF NOT EXISTS idx_task_runs_namespace_fingerprint
            ON task_runs(namespace, task_fingerprint, recorded_at DESC);

        CREATE TABLE IF NOT EXISTS task_lessons (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL CHECK(length(trim(namespace)) > 0),
            task_fingerprint TEXT NOT NULL,
            lesson_key TEXT NOT NULL,
            text TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            preconditions TEXT NOT NULL DEFAULT '',
            evidence_count INTEGER NOT NULL,
            success_count INTEGER NOT NULL,
            failure_count INTEGER NOT NULL,
            confidence REAL NOT NULL,
            source_run_ids_json TEXT NOT NULL DEFAULT '[]',
            tool_names_json TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            embedding_provider TEXT,
            embedding_model TEXT,
            embedding_dimension INTEGER,
            embedding_version TEXT,
            embedding_vector BLOB,
            UNIQUE(namespace, task_fingerprint, lesson_key)
        );
        CREATE INDEX IF NOT EXISTS idx_task_lessons_namespace_status
            ON task_lessons(namespace, status, updated_at DESC);

        CREATE TABLE IF NOT EXISTS memory_metrics (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS legacy_memory_quarantine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            legacy_id TEXT,
            reason TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_legacy_quarantine_identity
            ON legacy_memory_quarantine(source_type, coalesce(legacy_id, ''), reason);
        """
        with self._lock:
            self._connection.executescript(schema)
        self._migrate_namespace_scoped_identities()
        with self._lock:
            self._connection.execute(
                "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
        self._configure_fts()

    def _primary_key_columns(self, table: str) -> List[str]:
        with self._lock:
            rows = self._connection.execute(f"PRAGMA table_info({table})").fetchall()
        return [
            str(row["name"])
            for row in sorted((row for row in rows if int(row["pk"]) > 0), key=lambda row: row["pk"])
        ]

    def _migrate_namespace_scoped_identities(self) -> None:
        extraction_pk = self._primary_key_columns("memory_extraction_runs")
        task_run_pk = self._primary_key_columns("task_runs")
        if extraction_pk == ["namespace", "idempotency_key"] and task_run_pk == [
            "namespace",
            "run_id",
        ]:
            return

        with self._transaction() as conn:
            if extraction_pk != ["namespace", "idempotency_key"]:
                conn.execute("DROP TABLE IF EXISTS memory_extraction_runs_v3")
                conn.execute(
                    """
                    CREATE TABLE memory_extraction_runs_v3 (
                        idempotency_key TEXT NOT NULL,
                        namespace TEXT NOT NULL CHECK(length(trim(namespace)) > 0),
                        conversation_id TEXT,
                        user_message_id TEXT,
                        assistant_message_id TEXT,
                        extractor_model TEXT NOT NULL,
                        extractor_version TEXT NOT NULL,
                        status TEXT NOT NULL,
                        candidate_count INTEGER NOT NULL DEFAULT 0,
                        accepted_count INTEGER NOT NULL DEFAULT 0,
                        error TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(namespace, idempotency_key)
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO memory_extraction_runs_v3
                    SELECT idempotency_key, namespace, conversation_id, user_message_id,
                           assistant_message_id, extractor_model, extractor_version,
                           status, candidate_count, accepted_count, error, created_at, updated_at
                    FROM memory_extraction_runs
                    """
                )
                conn.execute("DROP TABLE memory_extraction_runs")
                conn.execute(
                    "ALTER TABLE memory_extraction_runs_v3 RENAME TO memory_extraction_runs"
                )

            if task_run_pk != ["namespace", "run_id"]:
                conn.execute("DROP TABLE IF EXISTS task_runs_v3")
                conn.execute(
                    """
                    CREATE TABLE task_runs_v3 (
                        run_id TEXT NOT NULL,
                        namespace TEXT NOT NULL CHECK(length(trim(namespace)) > 0),
                        task_id TEXT,
                        task_fingerprint TEXT NOT NULL,
                        task_description TEXT NOT NULL,
                        status TEXT NOT NULL,
                        confirmed_outcome TEXT,
                        summary TEXT NOT NULL DEFAULT '',
                        error TEXT NOT NULL DEFAULT '',
                        tool_usage_json TEXT NOT NULL DEFAULT '[]',
                        source_phase TEXT NOT NULL DEFAULT '',
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        started_at TEXT,
                        finished_at TEXT,
                        recorded_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(namespace, run_id)
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO task_runs_v3
                    SELECT run_id, namespace, task_id, task_fingerprint, task_description,
                           status, confirmed_outcome, summary, error, tool_usage_json,
                           source_phase, metadata_json, started_at, finished_at,
                           recorded_at, updated_at
                    FROM task_runs
                    """
                )
                conn.execute("DROP TABLE task_runs")
                conn.execute("ALTER TABLE task_runs_v3 RENAME TO task_runs")
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_task_runs_namespace_fingerprint
                    ON task_runs(namespace, task_fingerprint, recorded_at DESC)
                    """
                )

    def _configure_fts(self) -> None:
        try:
            with self._lock:
                self._connection.executescript(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                        memory_id UNINDEXED,
                        namespace UNINDEXED,
                        kind UNINDEXED,
                        text,
                        subject,
                        memory_key
                    );

                    CREATE TRIGGER IF NOT EXISTS memory_fts_insert
                    AFTER INSERT ON memories
                    WHEN NEW.status = 'active'
                    BEGIN
                        INSERT INTO memory_fts(memory_id, namespace, kind, text, subject, memory_key)
                        VALUES(NEW.id, NEW.namespace, NEW.kind, NEW.text, NEW.subject, coalesce(NEW.memory_key, ''));
                    END;

                    CREATE TRIGGER IF NOT EXISTS memory_fts_delete
                    AFTER DELETE ON memories
                    BEGIN
                        DELETE FROM memory_fts WHERE memory_id = OLD.id;
                    END;

                    CREATE TRIGGER IF NOT EXISTS memory_fts_update
                    AFTER UPDATE ON memories
                    BEGIN
                        DELETE FROM memory_fts WHERE memory_id = OLD.id;
                        INSERT INTO memory_fts(memory_id, namespace, kind, text, subject, memory_key)
                        SELECT NEW.id, NEW.namespace, NEW.kind, NEW.text, NEW.subject, coalesce(NEW.memory_key, '')
                        WHERE NEW.status = 'active';
                    END;
                    """
                )
                self._connection.execute("DELETE FROM memory_fts")
                self._connection.execute(
                    """
                    INSERT INTO memory_fts(memory_id, namespace, kind, text, subject, memory_key)
                    SELECT id, namespace, kind, text, subject, coalesce(memory_key, '')
                    FROM memories WHERE status = 'active'
                    """
                )
            self._fts_available = True
        except sqlite3.OperationalError:
            self._fts_available = False

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _parse_json(value: Optional[str], default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default

    @staticmethod
    def _vector_blob(vector: Sequence[float]) -> bytes:
        array = np.asarray(vector, dtype=np.float32)
        if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
            raise ValueError("Embedding vector must be a non-empty finite one-dimensional array")
        return array.tobytes()

    @staticmethod
    def _blob_vector(blob: Optional[bytes], dimension: Optional[int]) -> Optional[List[float]]:
        if not blob or not dimension:
            return None
        array = np.frombuffer(blob, dtype=np.float32)
        if array.size != int(dimension):
            return None
        return array.astype(np.float32, copy=True).tolist()

    @staticmethod
    def _memory_from_row(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"],
            namespace=row["namespace"],
            kind=row["kind"],
            subject=row["subject"],
            memory_key=row["memory_key"],
            text=row["text"],
            normalized_text=row["normalized_text"],
            content_hash=row["content_hash"],
            confidence=float(row["confidence"]),
            importance=float(row["importance"]),
            source=row["source"],
            source_ref=row["source_ref"],
            conversation_id=row["conversation_id"],
            turn_id=row["turn_id"],
            status=row["status"],
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_accessed_at=row["last_accessed_at"],
            version=int(row["version"]),
            embedding_status=row["embedding_status"],
            embedding_error=row["embedding_error"],
            metadata=SQLiteMemoryRepository._parse_json(row["metadata_json"], {}),
        )

    @staticmethod
    def _task_run_from_row(row: sqlite3.Row) -> TaskRunRecord:
        return TaskRunRecord(
            run_id=row["run_id"],
            namespace=row["namespace"],
            task_id=row["task_id"],
            task_fingerprint=row["task_fingerprint"],
            task_description=row["task_description"],
            status=row["status"],
            confirmed_outcome=row["confirmed_outcome"],
            summary=row["summary"],
            error=row["error"],
            tool_usage=SQLiteMemoryRepository._parse_json(row["tool_usage_json"], []),
            source_phase=row["source_phase"],
            metadata=SQLiteMemoryRepository._parse_json(row["metadata_json"], {}),
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            recorded_at=row["recorded_at"],
        )

    @staticmethod
    def _task_lesson_from_row(row: sqlite3.Row) -> TaskLessonRecord:
        embedding = None
        vector = SQLiteMemoryRepository._blob_vector(
            row["embedding_vector"],
            row["embedding_dimension"],
        )
        if vector is not None:
            embedding = EmbeddingRecord(
                provider=row["embedding_provider"] or "unknown",
                model=row["embedding_model"] or "unknown",
                dimension=int(row["embedding_dimension"]),
                embedding_version=row["embedding_version"] or "v1",
                vector=vector,
                created_at=row["updated_at"],
            )
        return TaskLessonRecord(
            id=row["id"],
            namespace=row["namespace"],
            task_fingerprint=row["task_fingerprint"],
            lesson_key=row["lesson_key"],
            text=row["text"],
            recommendation=row["recommendation"],
            preconditions=row["preconditions"],
            evidence_count=int(row["evidence_count"]),
            success_count=int(row["success_count"]),
            failure_count=int(row["failure_count"]),
            confidence=float(row["confidence"]),
            source_run_ids=SQLiteMemoryRepository._parse_json(row["source_run_ids_json"], []),
            tool_names=SQLiteMemoryRepository._parse_json(row["tool_names_json"], []),
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            embedding=embedding,
        )

    def _insert_memory(
        self,
        conn: sqlite3.Connection,
        memory: MemoryRecord,
        embedding: Optional[EmbeddingRecord],
    ) -> None:
        conn.execute(
            """
            INSERT INTO memories(
                id, namespace, kind, subject, memory_key, text, normalized_text, content_hash,
                confidence, importance, source, source_ref, conversation_id, turn_id, status,
                valid_from, valid_to, expires_at, created_at, updated_at, last_accessed_at,
                version, embedding_status, embedding_error, metadata_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                memory.id,
                memory.namespace,
                memory.kind,
                memory.subject,
                memory.memory_key,
                memory.text,
                memory.normalized_text,
                memory.content_hash,
                memory.confidence,
                memory.importance,
                memory.source,
                memory.source_ref,
                memory.conversation_id,
                memory.turn_id,
                memory.status,
                memory.valid_from,
                memory.valid_to,
                memory.expires_at,
                memory.created_at,
                memory.updated_at,
                memory.last_accessed_at,
                memory.version,
                "ready" if embedding else memory.embedding_status,
                memory.embedding_error,
                self._json(memory.metadata),
            ),
        )
        if embedding:
            self._insert_embedding(conn, memory.id, embedding)

    def _insert_embedding(
        self,
        conn: sqlite3.Connection,
        memory_id: str,
        embedding: EmbeddingRecord,
    ) -> None:
        if int(embedding.dimension) != len(embedding.vector):
            raise ValueError("Embedding dimension does not match vector length")
        conn.execute(
            """
            INSERT INTO memory_embeddings(
                memory_id, provider, model, dimension, embedding_version, vector, created_at
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(memory_id) DO UPDATE SET
                provider=excluded.provider,
                model=excluded.model,
                dimension=excluded.dimension,
                embedding_version=excluded.embedding_version,
                vector=excluded.vector,
                created_at=excluded.created_at
            """,
            (
                memory_id,
                embedding.provider,
                embedding.model,
                embedding.dimension,
                embedding.embedding_version,
                self._vector_blob(embedding.vector),
                embedding.created_at,
            ),
        )
        conn.execute(
            "UPDATE memories SET embedding_status='ready', embedding_error=NULL, updated_at=? WHERE id=?",
            (utc_now(), memory_id),
        )

    def upsert_memory(
        self,
        memory: MemoryRecord,
        embedding: Optional[EmbeddingRecord] = None,
    ) -> Tuple[MemoryRecord, str]:
        memory.namespace = normalize_namespace(memory.namespace)
        now = utc_now()
        with self._transaction() as conn:
            existing = None
            if memory.memory_key:
                existing = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE namespace=? AND subject=? AND kind=? AND memory_key=? AND status='active'
                    LIMIT 1
                    """,
                    (memory.namespace, memory.subject, memory.kind, memory.memory_key),
                ).fetchone()
            if existing is None:
                existing = conn.execute(
                    """
                    SELECT * FROM memories
                    WHERE namespace=? AND kind=? AND content_hash=? AND status='active'
                    LIMIT 1
                    """,
                    (memory.namespace, memory.kind, memory.content_hash),
                ).fetchone()

            if existing is not None:
                current = self._memory_from_row(existing)
                if current.normalized_text == memory.normalized_text:
                    conn.execute(
                        """
                        UPDATE memories SET
                            confidence=max(confidence, ?),
                            importance=max(importance, ?),
                            updated_at=?,
                            metadata_json=?
                        WHERE id=?
                        """,
                        (
                            memory.confidence,
                            memory.importance,
                            now,
                            self._json({**current.metadata, **memory.metadata}),
                            current.id,
                        ),
                    )
                    if embedding:
                        self._insert_embedding(conn, current.id, embedding)
                    row = conn.execute("SELECT * FROM memories WHERE id=?", (current.id,)).fetchone()
                    self._increment_metric_in_transaction(conn, "memory_unchanged")
                    return self._memory_from_row(row), "unchanged"

                conn.execute(
                    """
                    UPDATE memories
                    SET status='superseded', valid_to=?, updated_at=?
                    WHERE id=?
                    """,
                    (now, now, current.id),
                )
                memory.version = current.version + 1
                memory.valid_from = memory.valid_from or now
                memory.updated_at = now
                self._insert_memory(conn, memory, embedding)
                self._increment_metric_in_transaction(conn, "memory_superseded")
                self._increment_metric_in_transaction(conn, "memory_created")
                return memory, "updated"

            self._insert_memory(conn, memory, embedding)
            self._increment_metric_in_transaction(conn, "memory_created")
            return memory, "created"

    def set_memory_embedding(self, memory_id: str, embedding: EmbeddingRecord) -> None:
        with self._transaction() as conn:
            row = conn.execute("SELECT id FROM memories WHERE id=?", (memory_id,)).fetchone()
            if row is None:
                raise KeyError(f"Memory not found: {memory_id}")
            self._insert_embedding(conn, memory_id, embedding)

    def mark_embedding_failed(self, memory_id: str, error: str) -> None:
        message = str(error or "embedding generation failed")[:1000]
        with self._transaction() as conn:
            conn.execute(
                """
                UPDATE memories
                SET embedding_status='failed', embedding_error=?, updated_at=?
                WHERE id=?
                """,
                (message, utc_now(), memory_id),
            )
            self._increment_metric_in_transaction(conn, "embedding_failures")

    def get_memory(self, namespace: str, memory_id: str) -> Optional[MemoryRecord]:
        namespace = normalize_namespace(namespace)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM memories WHERE namespace=? AND id=? AND status <> 'deleted'",
                (namespace, memory_id),
            ).fetchone()
        return self._memory_from_row(row) if row else None

    def list_memories(
        self,
        namespace: str,
        kinds: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
        status: str = "active",
    ) -> List[MemoryRecord]:
        namespace = normalize_namespace(namespace)
        params: List[Any] = [namespace, status]
        where = ["namespace=?", "status=?"]
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            where.append(f"kind IN ({placeholders})")
            params.extend(kinds)
        sql = f"SELECT * FROM memories WHERE {' AND '.join(where)} ORDER BY updated_at DESC"
        if limit is not None:
            safe_limit = max(0, int(limit))
            if safe_limit == 0:
                return []
            sql += " LIMIT ?"
            params.append(safe_limit)
        with self._lock:
            rows = self._connection.execute(sql, params).fetchall()
        return [self._memory_from_row(row) for row in rows]

    def count_memories(self, namespace: str, kinds: Optional[Sequence[str]] = None) -> int:
        namespace = normalize_namespace(namespace)
        params: List[Any] = [namespace]
        where = ["namespace=?", "status='active'"]
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            where.append(f"kind IN ({placeholders})")
            params.extend(kinds)
        with self._lock:
            row = self._connection.execute(
                f"SELECT count(*) AS count FROM memories WHERE {' AND '.join(where)}",
                params,
            ).fetchone()
        return int(row["count"]) if row else 0

    def delete_memory(self, namespace: str, memory_id: str) -> bool:
        namespace = normalize_namespace(namespace)
        now = utc_now()
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE memories
                SET status='deleted', valid_to=?, updated_at=?
                WHERE namespace=? AND id=? AND status <> 'deleted'
                """,
                (now, now, namespace, memory_id),
            )
            if cursor.rowcount:
                self._increment_metric_in_transaction(conn, "memory_deleted")
            return bool(cursor.rowcount)

    def semantic_candidates(
        self,
        namespace: str,
        kinds: Sequence[str],
    ) -> List[RetrievalCandidate]:
        namespace = normalize_namespace(namespace)
        if not kinds:
            return []
        placeholders = ",".join("?" for _ in kinds)
        now = utc_now()
        params: List[Any] = [namespace, *kinds, now]
        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT m.*, e.provider, e.model, e.dimension, e.embedding_version, e.vector
                FROM memories m
                JOIN memory_embeddings e ON e.memory_id=m.id
                WHERE m.namespace=? AND m.kind IN ({placeholders})
                  AND m.status='active'
                  AND (m.expires_at IS NULL OR m.expires_at > ?)
                """,
                params,
            ).fetchall()
        candidates: List[RetrievalCandidate] = []
        for row in rows:
            vector = self._blob_vector(row["vector"], row["dimension"])
            if vector is not None:
                candidates.append(
                    RetrievalCandidate(
                        memory=self._memory_from_row(row),
                        embedding=vector,
                        embedding_provider=row["provider"],
                        embedding_model=row["model"],
                        embedding_version=row["embedding_version"],
                    )
                )
        return candidates

    @staticmethod
    def _fts_query(query: str) -> str:
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_'/-]{1,63}", str(query or ""))
        unique = list(dict.fromkeys(token.lower() for token in tokens))[:20]
        return " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in unique)

    def lexical_candidates(
        self,
        namespace: str,
        query: str,
        kinds: Sequence[str],
        limit: int,
    ) -> List[RetrievalCandidate]:
        namespace = normalize_namespace(namespace)
        safe_limit = max(0, min(200, int(limit)))
        if not kinds or safe_limit == 0:
            return []
        placeholders = ",".join("?" for _ in kinds)
        rows: List[sqlite3.Row] = []
        fts_query = self._fts_query(query)
        if self._fts_available and fts_query:
            params: List[Any] = [namespace, *kinds, fts_query, safe_limit]
            with self._lock:
                rows = self._connection.execute(
                    f"""
                    SELECT m.*, bm25(memory_fts) AS lexical_rank
                    FROM memory_fts
                    JOIN memories m ON m.id=memory_fts.memory_id
                    WHERE m.namespace=? AND m.kind IN ({placeholders})
                      AND m.status='active' AND memory_fts MATCH ?
                    ORDER BY lexical_rank ASC
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
        if not rows:
            tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_'/-]{1,63}", str(query or ""))[:8]
            if not tokens:
                return []
            like_parts = " OR ".join("lower(text) LIKE ?" for _ in tokens)
            params = [namespace, *kinds, *[f"%{token.lower()}%" for token in tokens], safe_limit]
            with self._lock:
                rows = self._connection.execute(
                    f"""
                    SELECT *, 0.0 AS lexical_rank FROM memories
                    WHERE namespace=? AND kind IN ({placeholders}) AND status='active'
                      AND ({like_parts})
                    ORDER BY updated_at DESC LIMIT ?
                    """,
                    params,
                ).fetchall()
        output: List[RetrievalCandidate] = []
        for index, row in enumerate(rows):
            output.append(
                RetrievalCandidate(
                    memory=self._memory_from_row(row),
                    lexical_score=1.0 / (1.0 + index),
                )
            )
        return output

    def claim_extraction(
        self,
        idempotency_key: str,
        namespace: str,
        conversation_id: Optional[str],
        user_message_id: Optional[str],
        assistant_message_id: Optional[str],
        extractor_model: str,
        extractor_version: str,
    ) -> bool:
        namespace = normalize_namespace(namespace)
        now = utc_now()
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO memory_extraction_runs(
                    idempotency_key, namespace, conversation_id, user_message_id,
                    assistant_message_id, extractor_model, extractor_version,
                    status, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,'running',?,?)
                """,
                (
                    idempotency_key,
                    namespace,
                    conversation_id,
                    user_message_id,
                    assistant_message_id,
                    extractor_model,
                    extractor_version,
                    now,
                    now,
                ),
            )
            if cursor.rowcount:
                self._increment_metric_in_transaction(conn, "extraction_claimed")
            else:
                self._increment_metric_in_transaction(conn, "extraction_duplicate")
            return bool(cursor.rowcount)

    def finish_extraction(
        self,
        idempotency_key: str,
        status: str,
        candidate_count: int,
        accepted_count: int,
        error: Optional[str] = None,
        *,
        namespace: str,
    ) -> None:
        namespace = normalize_namespace(namespace)
        with self._transaction() as conn:
            conn.execute(
                """
                UPDATE memory_extraction_runs
                SET status=?, candidate_count=?, accepted_count=?, error=?, updated_at=?
                WHERE namespace=? AND idempotency_key=?
                """,
                (
                    status,
                    max(0, int(candidate_count)),
                    max(0, int(accepted_count)),
                    str(error)[:1000] if error else None,
                    utc_now(),
                    namespace,
                    idempotency_key,
                ),
            )
            self._increment_metric_in_transaction(conn, f"extraction_{status}")

    def upsert_task_run(self, run: TaskRunRecord) -> Tuple[TaskRunRecord, bool]:
        run.namespace = normalize_namespace(run.namespace)
        now = utc_now()
        with self._transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM task_runs WHERE run_id=? AND namespace=?",
                (run.run_id, run.namespace),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO task_runs(
                        run_id, namespace, task_id, task_fingerprint, task_description,
                        status, confirmed_outcome, summary, error, tool_usage_json,
                        source_phase, metadata_json, started_at, finished_at,
                        recorded_at, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        run.run_id,
                        run.namespace,
                        run.task_id,
                        run.task_fingerprint,
                        run.task_description,
                        run.status,
                        run.confirmed_outcome,
                        run.summary,
                        run.error,
                        self._json(run.tool_usage),
                        run.source_phase,
                        self._json(run.metadata),
                        run.started_at,
                        run.finished_at,
                        run.recorded_at,
                        now,
                    ),
                )
                self._increment_metric_in_transaction(conn, "task_run_created")
                return run, True

            current = self._task_run_from_row(existing)
            outcome = run.confirmed_outcome or current.confirmed_outcome
            status = (
                current.status
                if current.confirmed_outcome and not run.confirmed_outcome
                else run.status
            )
            finished_at = run.finished_at or current.finished_at
            conn.execute(
                """
                UPDATE task_runs SET
                    task_id=?, task_fingerprint=?, task_description=?, status=?,
                    confirmed_outcome=?, summary=?, error=?, tool_usage_json=?,
                    source_phase=?, metadata_json=?, started_at=?, finished_at=?, updated_at=?
                WHERE run_id=? AND namespace=?
                """,
                (
                    run.task_id or current.task_id,
                    run.task_fingerprint,
                    run.task_description,
                    status,
                    outcome,
                    run.summary or current.summary,
                    run.error or current.error,
                    self._json(run.tool_usage or current.tool_usage),
                    run.source_phase or current.source_phase,
                    self._json({**current.metadata, **run.metadata}),
                    run.started_at or current.started_at,
                    finished_at,
                    now,
                    run.run_id,
                    run.namespace,
                ),
            )
            self._increment_metric_in_transaction(conn, "task_run_updated")
            row = conn.execute(
                "SELECT * FROM task_runs WHERE run_id=? AND namespace=?",
                (run.run_id, run.namespace),
            ).fetchone()
            return self._task_run_from_row(row), False

    def list_task_runs(
        self,
        namespace: str,
        limit: int = 50,
        outcome: Optional[str] = None,
    ) -> List[TaskRunRecord]:
        namespace = normalize_namespace(namespace)
        safe_limit = max(0, min(100000, int(limit)))
        if safe_limit == 0:
            return []
        params: List[Any] = [namespace]
        where = ["namespace=?"]
        if outcome:
            where.append("confirmed_outcome=?")
            params.append(outcome)
        params.append(safe_limit)
        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT * FROM task_runs
                WHERE {' AND '.join(where)}
                ORDER BY recorded_at DESC LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._task_run_from_row(row) for row in rows]

    def upsert_task_lesson(self, lesson: TaskLessonRecord) -> TaskLessonRecord:
        lesson.namespace = normalize_namespace(lesson.namespace)
        embedding = lesson.embedding
        blob = self._vector_blob(embedding.vector) if embedding else None
        dimension = embedding.dimension if embedding else None
        if embedding and dimension != len(embedding.vector):
            raise ValueError("Task lesson embedding dimension mismatch")
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO task_lessons(
                    id, namespace, task_fingerprint, lesson_key, text, recommendation,
                    preconditions, evidence_count, success_count, failure_count,
                    confidence, source_run_ids_json, tool_names_json, status,
                    created_at, updated_at, embedding_provider, embedding_model,
                    embedding_dimension, embedding_version, embedding_vector
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(namespace, task_fingerprint, lesson_key) DO UPDATE SET
                    text=excluded.text,
                    recommendation=excluded.recommendation,
                    preconditions=excluded.preconditions,
                    evidence_count=excluded.evidence_count,
                    success_count=excluded.success_count,
                    failure_count=excluded.failure_count,
                    confidence=excluded.confidence,
                    source_run_ids_json=excluded.source_run_ids_json,
                    tool_names_json=excluded.tool_names_json,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    embedding_provider=excluded.embedding_provider,
                    embedding_model=excluded.embedding_model,
                    embedding_dimension=excluded.embedding_dimension,
                    embedding_version=excluded.embedding_version,
                    embedding_vector=excluded.embedding_vector
                """,
                (
                    lesson.id,
                    lesson.namespace,
                    lesson.task_fingerprint,
                    lesson.lesson_key,
                    lesson.text,
                    lesson.recommendation,
                    lesson.preconditions,
                    lesson.evidence_count,
                    lesson.success_count,
                    lesson.failure_count,
                    lesson.confidence,
                    self._json(lesson.source_run_ids),
                    self._json(lesson.tool_names),
                    lesson.status,
                    lesson.created_at,
                    lesson.updated_at,
                    embedding.provider if embedding else None,
                    embedding.model if embedding else None,
                    dimension,
                    embedding.embedding_version if embedding else None,
                    blob,
                ),
            )
            self._increment_metric_in_transaction(conn, "task_lesson_upserted")
            row = conn.execute(
                """
                SELECT * FROM task_lessons
                WHERE namespace=? AND task_fingerprint=? AND lesson_key=?
                """,
                (lesson.namespace, lesson.task_fingerprint, lesson.lesson_key),
            ).fetchone()
        return self._task_lesson_from_row(row)

    def list_task_lessons(
        self,
        namespace: str,
        task_fingerprint: Optional[str] = None,
        limit: int = 50,
    ) -> List[TaskLessonRecord]:
        namespace = normalize_namespace(namespace)
        safe_limit = max(0, min(100000, int(limit)))
        if safe_limit == 0:
            return []
        params: List[Any] = [namespace]
        where = ["namespace=?", "status='active'"]
        if task_fingerprint:
            where.append("task_fingerprint=?")
            params.append(task_fingerprint)
        params.append(safe_limit)
        with self._lock:
            rows = self._connection.execute(
                f"""
                SELECT * FROM task_lessons
                WHERE {' AND '.join(where)}
                ORDER BY confidence DESC, evidence_count DESC, updated_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._task_lesson_from_row(row) for row in rows]

    def delete_task_lesson(self, namespace: str, lesson_id: str) -> bool:
        namespace = normalize_namespace(namespace)
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE task_lessons SET status='deleted', updated_at=?
                WHERE namespace=? AND id=? AND status <> 'deleted'
                """,
                (utc_now(), namespace, lesson_id),
            )
            return bool(cursor.rowcount)

    def _increment_metric_in_transaction(
        self,
        conn: sqlite3.Connection,
        name: str,
        amount: int = 1,
    ) -> None:
        conn.execute(
            """
            INSERT INTO memory_metrics(name, value, updated_at) VALUES(?,?,?)
            ON CONFLICT(name) DO UPDATE SET
                value=value + excluded.value,
                updated_at=excluded.updated_at
            """,
            (name, int(amount), utc_now()),
        )

    def increment_metric(self, name: str, amount: int = 1) -> None:
        with self._transaction() as conn:
            self._increment_metric_in_transaction(conn, name, amount)

    def metrics(self) -> Dict[str, int]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT name, value FROM memory_metrics ORDER BY name"
            ).fetchall()
        return {str(row["name"]): int(row["value"]) for row in rows}

    def list_namespaces(self) -> List[str]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT namespace FROM memories
                UNION SELECT namespace FROM task_runs
                UNION SELECT namespace FROM task_lessons
                ORDER BY namespace
                """
            ).fetchall()
        return [str(row["namespace"]) for row in rows if str(row["namespace"] or "").strip()]

    def backup(self, destination: Path) -> Path:
        destination = Path(destination).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            target = sqlite3.connect(str(destination))
            try:
                self._connection.backup(target)
            finally:
                target.close()
        return destination

    def export_namespace(self, namespace: str) -> Dict[str, Any]:
        namespace = normalize_namespace(namespace)
        memories = [record.to_dict() for record in self.list_memories(namespace, status="active")]
        task_runs = [record.to_dict() for record in self.list_task_runs(namespace, limit=100000)]
        task_lessons = [
            record.to_dict() for record in self.list_task_lessons(namespace, limit=100000)
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "namespace": namespace,
            "exported_at": utc_now(),
            "memories": memories,
            "task_runs": task_runs,
            "task_lessons": task_lessons,
        }

    def clear_namespace(self, namespace: str, include_task_data: bool = True) -> Dict[str, int]:
        namespace = normalize_namespace(namespace)
        with self._transaction() as conn:
            memory_count = conn.execute(
                "SELECT count(*) AS count FROM memories WHERE namespace=?",
                (namespace,),
            ).fetchone()["count"]
            extraction_count = conn.execute(
                "SELECT count(*) AS count FROM memory_extraction_runs WHERE namespace=?",
                (namespace,),
            ).fetchone()["count"]
            task_run_count = 0
            task_lesson_count = 0
            conn.execute("DELETE FROM memories WHERE namespace=?", (namespace,))
            conn.execute("DELETE FROM memory_extraction_runs WHERE namespace=?", (namespace,))
            if include_task_data:
                task_run_count = conn.execute(
                    "SELECT count(*) AS count FROM task_runs WHERE namespace=?",
                    (namespace,),
                ).fetchone()["count"]
                task_lesson_count = conn.execute(
                    "SELECT count(*) AS count FROM task_lessons WHERE namespace=?",
                    (namespace,),
                ).fetchone()["count"]
                conn.execute("DELETE FROM task_runs WHERE namespace=?", (namespace,))
                conn.execute("DELETE FROM task_lessons WHERE namespace=?", (namespace,))
            self._increment_metric_in_transaction(conn, "namespace_cleared")
        return {
            "memories": int(memory_count),
            "extraction_runs": int(extraction_count),
            "task_runs": int(task_run_count),
            "task_lessons": int(task_lesson_count),
        }

    def quarantine_legacy(
        self,
        source_type: str,
        legacy_id: Optional[str],
        reason: str,
        payload: Dict[str, Any],
    ) -> bool:
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO legacy_memory_quarantine(
                    source_type, legacy_id, reason, payload_json, created_at
                ) VALUES(?,?,?,?,?)
                """,
                (
                    str(source_type or "unknown"),
                    str(legacy_id) if legacy_id else None,
                    str(reason or "unspecified"),
                    self._json(payload),
                    utc_now(),
                ),
            )
            if cursor.rowcount:
                self._increment_metric_in_transaction(conn, "legacy_quarantined")
            return bool(cursor.rowcount)
