# Task-Learning Memory

## Purpose

Task learning records execution evidence without contaminating personal memory.

## Data Model

`task_runs` contains one row per namespace and executor run ID. Status updates
modify that row, while another user may safely use the same external run ID.

`task_lessons` contains aggregated procedural guidance:

- Task fingerprint
- Recommendation and preconditions
- Evidence count
- Success and failure counts
- Confidence
- Source run IDs
- Common tool names
- Optional versioned embedding

## Outcome Semantics

- `awaiting_confirmation` is pending, not success.
- `confirmed_complete`, `completed`, or `success` is confirmed success.
- Explicit failure states are confirmed failures.
- Paused runs remain unconfirmed.
- A late pending update cannot downgrade a confirmed terminal run.

Lessons are created or updated only from confirmed evidence. Repeated runs update the same lesson key rather than adding task vectors.

## Retrieval

Task execution calls `build_task_execution_guidance(..., namespace=user_key)`. The service searches only `task_lessons` for that user and includes confidence, evidence count, and source run IDs.

Normal conversation retrieval never queries task tables.

## API

- `GET /v1/memory/learning/events`
- `POST /v1/memory/learning/context`
- `GET /v1/memory/learning/lessons`
- `DELETE /v1/memory/learning/lessons/{lesson_id}`

All routes are authenticated and namespace-scoped.

## Migration

Legacy JSONL task events are imported idempotently as task runs. Legacy `task_experience` and `task_learning` vectors are derived artifacts and are not imported.
