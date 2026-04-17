# Scheduling and Recurrence

## Product Purpose
Scheduling turns CATBot's todo list into a time-based workflow system. Tasks can be set for a future moment, repeated on a defined cadence, and surfaced automatically when they become due.

## User-Facing Behavior
- Tasks can be created with `scheduledFor` timestamps and optional recurrence settings.
- Supported recurrence frequencies are hourly, daily, weekly, monthly, and yearly.
- Due-only task views show tasks whose `nextRunAt` has passed.
- Completing a recurring task reschedules it instead of removing it.

## How It Works
- `src/servers/todo_store.py` normalizes recurrence payloads with `_normalize_recurrence(...)` and validates frequency and interval bounds.
- `_next_occurrence(...)` computes the next recurrence anchor, and `_advance_after(...)` advances repeated tasks until the next valid run after the current time.
- `_build_task_item(...)` populates schedule-related fields such as `scheduled_for`, `recurrence`, `next_run_at`, and `last_completed_at`.
- `complete_task(...)` handles recurrence-aware completion. For repeating tasks, it computes the next scheduled occurrence, updates `next_run_at`, and returns `rescheduled=True`; for one-time tasks, it removes the completed item.
- `list_due_task_items(...)` filters the stored tasks to only scheduled items whose `next_run_at` is at or before the reference time.
- In the proxy, request models expose recurrence through `TodoRecurrenceRequest`, and `_todo_recurrence_to_dict(...)` converts validated request objects into store-ready dictionaries.
- `GET /v1/todo/due` and `GET /v1/todo?due_only=true` both surface the due-task view that later drives the scheduled task poller.

## Expanded Flow Diagram
```mermaid
flowchart TD
    Create[Create or update task] --> Normalize[_normalize_recurrence and schedule normalization]
    Normalize --> Item[_build_task_item]
    Item --> Persist[Persist to todo store]

    Persist --> DueQuery[list_due_task_items]
    DueQuery --> DueView[/v1/todo/due]
    DueView --> Poller[Scheduled task poller]

    Complete[User or auto completion] --> CompleteFn[complete_task]
    CompleteFn --> Repeat{Has recurrence?}
    Repeat -->|No| Remove[Remove task]
    Repeat -->|Yes| Next[_next_occurrence and _advance_after]
    Next --> Reschedule[Update next_run_at and last_completed_at]
```

## Primary Code References
- `src/servers/todo_store.py`
  Recurrence validation: `_normalize_recurrence(...)`.
- `src/servers/todo_store.py`
  Recurrence math: `_next_occurrence(...)` and `_advance_after(...)`.
- `src/servers/todo_store.py`
  Stored task construction: `_build_task_item(...)`.
- `src/servers/todo_store.py`
  Completion and due filtering: `complete_task(...)` and `list_due_task_items(...)`.
- `src/servers/proxy_server.py`
  Scheduler-aware request model: `TodoRecurrenceRequest`.
- `src/servers/proxy_server.py`
  Conversion and response helpers: `_todo_recurrence_to_dict(...)` and `_build_todo_list_response(...)`.
- `tests/test_todo_scheduler_api.py`
  API-level scheduler behavior tests.
- `tests/test_scheduled_task_poller.py`
  End-to-end due-task polling expectations.

## Data and Dependencies
- Schedule timestamps are normalized and stored in the todo data layer.
- Recurring tasks depend on consistent UTC-aware comparisons so due filtering and rescheduling stay deterministic.
- The scheduled poller depends on this metadata to decide which tasks to execute automatically.

## Constraints and Notes
- Unsupported recurrence patterns are intentionally rejected rather than loosely interpreted.
- Recurrence handling is cadence-based, not a full calendar rules engine.
- Because scheduled tasks can auto-complete and reschedule, schedule state interacts directly with task execution status and notification flows.

## Related Docs
- [Todo System](18_todo_system.md)
- [Task Execution Engine](20_task_execution_engine.md)
- [Scheduled Task Poller](21_scheduled_task_poller.md)
