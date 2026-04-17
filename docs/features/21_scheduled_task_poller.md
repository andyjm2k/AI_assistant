# Scheduled Task Poller

## Product Purpose
The scheduled task poller is the background service that turns scheduled todo metadata into actual execution. Without it, scheduled and recurring tasks would exist in storage but never trigger themselves.

## User-Facing Behavior
- Due tasks can start automatically without a user manually pressing execute.
- The poller scans authenticated users, not just the currently active web session.
- Repeating tasks can continue to execute on cadence because the poller keeps revisiting the due queue.
- Scheduled execution still flows through the normal task-execution engine, so status, scratch output, and confirmation logic remain consistent.

## How It Works
- `src/servers/scheduled_task_poller.py` loads user identities from `config/auth_users.json`.
- It generates service JWTs so it can call the proxy's authenticated todo endpoints on behalf of each user without bypassing the normal API layer.
- For each user, the poller requests `GET /v1/todo/due` and then calls `POST /v1/todo/execute` for each returned `task_id`.
- The poller uses `_url("/v1/todo/due")` and `_url("/v1/todo/execute")` helpers to build endpoint paths against the configured proxy base URL.
- Local deployment edge cases are handled in the poller as well, including localhost or `.local` targets with self-signed certificates.
- `scripts/start_all.py` launches the poller as part of the normal CATBot service bundle, and `scripts/restart_all.py` / `scripts/stop_all.py` include it in operational lifecycle commands.

## Expanded Flow Diagram
```mermaid
flowchart TD
    Timer[Poll interval or one-shot run] --> Users[Load auth users]
    Users --> JWT[Create service JWT per user]
    JWT --> Due[/v1/todo/due]
    Due --> Tasks{Any due tasks?}
    Tasks -->|No| Sleep[Wait for next poll]
    Tasks -->|Yes| Execute[/v1/todo/execute for each task_id]
    Execute --> Proxy[Normal task execution engine]
    Proxy --> Result[Execution state, scratch output, learning]
    Result --> Sleep
```

## Primary Code References
- `src/servers/scheduled_task_poller.py`
  Main service loop and per-user due-task scanning.
- `src/servers/scheduled_task_poller.py`
  Proxy endpoint construction via `_url("/v1/todo/due")` and `_url("/v1/todo/execute")`.
- `src/servers/scheduled_task_poller.py`
  Service-auth handling through short-lived JWT generation.
- `src/servers/proxy_server.py`
  Due-task and execution endpoints used by the poller.
- `scripts/start_all.py`
  Starts the poller in the normal CATBot runtime.
- `tests/test_scheduled_task_poller.py`
  Verifies due-task polling and execution-call behavior.

## Data and Dependencies
- Depends on the authenticated todo API, not direct file access to todo storage.
- Depends on the proxy being reachable at the configured base URL.
- Depends on valid auth-user configuration so the poller knows which users to scan.

## Constraints and Notes
- The poller does not implement its own execution logic. It delegates to the same execution endpoints used by manual task runs.
- Because the poller works through the proxy, API auth and scheduler behavior stay centralized.
- Scheduled executions are still subject to executor safety rules such as confirmation handling and bounded iterations.

## Related Docs
- [Todo System](18_todo_system.md)
- [Scheduling and Recurrence](19_scheduling_and_recurrence.md)
- [Task Execution Engine](20_task_execution_engine.md)
