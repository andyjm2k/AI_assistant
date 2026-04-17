# Task Execution Engine

## Product Purpose
The task execution engine is one of CATBot's main agent features. Instead of only storing todos, CATBot can run a bounded LLM-plus-tools loop against a specific task, pause for human input when needed, and stop in an auditable state rather than pretending the work is done.

## User-Facing Behavior
- A todo task can be executed explicitly through the API or via Telegram tool flows.
- Active runs expose status, can be resumed after a pause, and can be soft-cancelled.
- The engine never silently marks work complete just because the model says it is done; the normal end state is `awaiting_confirmation`.
- Scheduled executions can auto-complete into the todo system once the run reaches a confirmation-ready state.

## How It Works
- `src/features/task_execution.py` implements `TodoTaskExecutor`, which owns the bounded task loop.
- The executor builds a task-focused system prompt instructing the model to use tools, ask for user input when blocked, and explicitly say the work is finished when it reaches a completion state.
- `run_loop()` repeatedly calls the model, executes any returned tool calls, and keeps state until one of four things happens: pause, awaiting confirmation, cancellation, or max-iteration exhaustion.
- `_check_pause_or_done(content)` scans assistant text for `DONE_PHRASES` and `PAUSE_PHRASES`, mapping those phrases into `STATUS_AWAITING_CONFIRMATION` or `STATUS_PAUSED_AWAITING_FEEDBACK`.
- `request_cancel()` sets a soft-cancel flag, which `run_loop()` checks at iteration boundaries to exit cleanly.
- `src/servers/proxy_server.py` manages active executors per user/task, exposes the runtime API, and integrates execution with monitoring, scratch-file capture, Telegram notifications, and task-learning memory.
- The main execution API surface is:
- `POST /v1/todo/execute`
- `POST /v1/todo/execute/resume`
- `POST /v1/todo/execute/cancel`
- `GET /v1/todo/execute/status`
- `POST /v1/todo/{task_id}/complete`
- `_task_execute_resume(...)` restores a paused execution with new user input, while `_task_execute_cancel(...)` issues a soft cancellation against the active executor.
- `_write_task_exec_response_to_scratch(...)` persists human-readable output snapshots so task runs leave an artifact even when the user is not watching the live chat.
- When a run ends, the proxy records task-learning outcomes and, for scheduled tasks, can call `_auto_complete_scheduled_execution(...)` to reschedule or remove the todo item automatically.

## Expanded Flow Diagram
```mermaid
flowchart TD
    Start[/v1/todo/execute/] --> State[Create active executor state]
    State --> Prompt[Build task-focused prompt]
    Prompt --> Loop[TodoTaskExecutor.run_loop]
    Loop --> Model[Call LLM]
    Model --> ToolCheck{Tool calls returned?}
    ToolCheck -->|Yes| ToolExec[Execute tools]
    ToolExec --> Loop
    ToolCheck -->|No| StatusCheck[_check_pause_or_done]

    StatusCheck -->|Pause phrase| Paused[paused_awaiting_feedback]
    StatusCheck -->|Done phrase| Awaiting[awaiting_confirmation]
    StatusCheck -->|Neither| Iterate[Next iteration]
    Iterate --> Loop

    Paused --> Resume[/v1/todo/execute/resume/]
    Resume --> Loop

    Awaiting --> Confirm[/v1/todo/{task_id}/complete/]
    Awaiting --> Scratch[_write_task_exec_response_to_scratch]
    Awaiting --> Learning[record_task_outcome]

    Cancel[/v1/todo/execute/cancel/] --> SoftCancel[request_cancel]
    SoftCancel --> Cancelled[Cancelled state]
```

## Primary Code References
- `src/features/task_execution.py`
  Core executor class: `TodoTaskExecutor`.
- `src/features/task_execution.py`
  Terminal-state constants: `STATUS_PAUSED_AWAITING_FEEDBACK` and `STATUS_AWAITING_CONFIRMATION`.
- `src/features/task_execution.py`
  Phrase controls: `PAUSE_PHRASES`, `DONE_PHRASES`, and `_check_pause_or_done(content)`.
- `src/features/task_execution.py`
  Main loop and cancel hook: `run_loop()` and `request_cancel()`.
- `src/servers/proxy_server.py`
  Execution endpoints: `/v1/todo/execute`, `/v1/todo/execute/resume`, `/v1/todo/execute/cancel`, `/v1/todo/execute/status`, and `/v1/todo/{task_id}/complete`.
- `src/servers/proxy_server.py`
  Runtime helpers: `_task_execute_resume(...)`, `_task_execute_cancel(...)`, `_write_task_exec_response_to_scratch(...)`, and `_auto_complete_scheduled_execution(...)`.
- `src/servers/proxy_server.py`
  Completion integration: task-learning recording and optional Telegram notification for scheduled runs.
- `tests/test_task_execution.py`
  Executor behavior tests for completion, pause, and cancel handling.
- `tests/test_task_exec_scratch.py`
  Scratch-output persistence tests.

## Data and Dependencies
- Depends on the todo system for task lookup, confirmation, and rescheduling.
- Depends on the tool registry and model client for the actual work loop.
- Active execution state is held in proxy memory, while scratch artifacts and task-learning events are written to persistent storage.

## Constraints and Notes
- This is a bounded loop, not an unbounded autonomous agent. Iteration limits are part of the design.
- Human confirmation is a core safety feature, not a fallback. It prevents the model from unilaterally closing work.
- Scheduled tasks behave slightly differently because the proxy can auto-complete them after the executor reaches a confirmation-ready state.

## Related Docs
- [Todo System](18_todo_system.md)
- [Scheduling and Recurrence](19_scheduling_and_recurrence.md)
- [Task-Learning Memory](16_task_learning_memory.md)
