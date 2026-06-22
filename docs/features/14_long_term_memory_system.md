# Long-Term Memory System

## Purpose

CATBot stores durable user information in a namespace-scoped SQLite database. Electron, Telegram, weather, philosopher mode, and task execution use the same backend services and cannot select another user's namespace.

## Memory Types

- Working context: temporary per-conversation notes exposed as `manageWorkingContext`; never stored as long-term memory.
- Personal memory: profile facts, preferences, habits, needs, and relationships.
- Episodic memory: bounded interaction summaries when they have future value.
- Philosopher memory: conclusions stored under `philosopher_contemplation`.
- Task learning: task runs and aggregated lessons in separate tables and retrieval paths.

Raw task runs never enter normal conversation retrieval.

## Architecture

```text
Authenticated user
  -> memory_api namespace
  -> MemoryManager facade
     -> PersonalMemoryService
     -> ExtractionService
     -> RetrievalService
     -> MemoryContextBuilder
     -> TaskLearningService
  -> SQLiteMemoryRepository
     -> memory.sqlite3 (schema v3, WAL, transactions, FTS5, vector blobs)
```

Primary modules:

- `src/memory/models.py`
- `src/memory/sqlite_repository.py`
- `src/memory/embedding_provider.py`
- `src/memory/personal_memory_service.py`
- `src/memory/extraction_service.py`
- `src/memory/retrieval_service.py`
- `src/memory/context_builder.py`
- `src/memory/task_learning_service.py`
- `src/memory/memory_manager.py`
- `src/servers/memory_api.py`

## Retrieval

Retrieval applies namespace, kind, active status, and expiry filters before ranking. It combines FTS5 lexical candidates with compatible embedding candidates. Embedding provider, model, dimension, and version are stored with every vector.

`POST /v1/memory/context` is the shared Electron and Telegram context endpoint. It returns a bounded evidence block that explicitly treats stored content as untrusted data.

## API Security

All `/v1/memory/*` routes resolve namespace from `get_current_user`. Namespace is not accepted from request bodies. Cross-user get and delete return not found. Extraction idempotency keys and task run IDs are composite identities scoped by namespace.

Metadata and extraction payloads are bounded, and `MEMORY_DATABASE_NAME` must
be a plain filename so configuration cannot escape `MEMORY_STORAGE_PATH`.

Available routes include:

- `POST /v1/memory/store`
- `POST /v1/memory/search`
- `POST /v1/memory/context`
- `POST /v1/memory/extract`
- `GET /v1/memory/list`
- `GET /v1/memory/{id}`
- `DELETE /v1/memory/{id}`
- `GET /v1/memory/export`
- `POST /v1/memory/clear`
- Task run and lesson routes under `/v1/memory/learning/*`

## Operations

See [Memory Operations](../memory_operations.md) for backup, migration, export, clear, and embedding rebuild commands.
