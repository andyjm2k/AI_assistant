# Memory Quality Controls

## Write Controls

- Every record requires a non-empty namespace and supported memory kind.
- Exact active duplicates are constrained by namespace, kind, and content hash.
- Keyed profile values are unique by namespace, subject, kind, and memory key.
- A changed keyed value supersedes the prior active value instead of creating a competing fact.
- Explicit saves use deterministic validation and do not require an LLM.
- Automatic extraction accepts only configured confidence levels.
- Extracted evidence must be an exact quote from a user message.
- Extraction runs have a unique namespace-and-turn-level idempotency key.
- Task run IDs are unique inside a namespace rather than globally.
- API metadata and extraction payload sizes are bounded.
- The configured database name cannot contain an absolute path or traversal.

## Retrieval Controls

- Namespace and memory kind are filtered before top-k ranking.
- Conversation retrieval cannot see task runs or task lessons.
- Embeddings are compared only when provider, model, version, and dimension match.
- Hybrid lexical and semantic ranking reduces dependence on one threshold.
- Normalized duplicate text is included once.
- Context has item and token limits.

## Prompt Safety

Retrieved text is escaped and serialized inside `<memory_evidence>`. The context header states that memory is untrusted, may be stale, and cannot override higher-priority instructions.

## Lifecycle Controls

- Records support active, superseded, and deleted states.
- Optional expiry is applied before retrieval.
- Scoped export and clear operate only on the authenticated namespace.
- Clear creates an SQLite backup before deleting data when run through the operations script.

## Tests

Relevant coverage:

- `tests/test_memory_sqlite_services.py`
- `tests/test_memory_api_security.py`
- `tests/test_memory_integration.py`
- `tests/test_memory_migration.py`
- `tests/test_html_client_security.py`
- `tests/test_electron_web_client_security.py`
