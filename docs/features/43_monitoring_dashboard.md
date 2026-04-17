# Monitoring Dashboard

## Product Purpose
The monitoring dashboard makes CATBot operable as a multi-service system. It provides a browser-accessible view into runtime health, workflow activity, logs, and recent execution state across the assistant's major subsystems.

## User-Facing Behavior
- Users can open `/monitor` and inspect browser automation, AutoGen, philosopher mode, task execution, memory readiness, and other runtime signals.
- Detail views and summary routes expose more specific monitoring perspectives.
- Long-running workflows can be tracked without tailing raw server logs.
- The dashboard is focused on operational visibility rather than end-user chat interaction.

## How It Works
- `docs/monitoring_dashboard.html` defines the dashboard UI and the client-side logic for rendering chip cards, detail panes, lanes, meters, and recent-run stacks.
- `src/servers/proxy_server.py` serves routes such as `/monitor`, `/monitor/detail`, `/monitor/status`, `/monitor/summary`, and workflow/log-related endpoints.
- The proxy maintains recent and active run metadata for key systems such as AutoGen, browser-use, philosopher mode, and task execution.
- Persistent status-event endpoints such as `/v1/status/start`, `/v1/status/update`, `/v1/status/finish`, `/v1/status/latest`, and `/v1/status/events` feed the broader visibility model used by both Telegram progress reporting and dashboard views.
- Browser-use log capture and proxy log capture are integrated into the monitor pages so dashboard users can inspect runtime behavior without leaving the CATBot UI.

## Expanded Flow Diagram
```mermaid
flowchart TD
    Workflows[AutoGen, browser, philosopher, task execution] --> MonitorState[In-memory monitor state]
    StatusEvents[Persistent status events JSONL] --> MonitorState
    Logs[Proxy logs and browser logs] --> MonitorState
    MonitorState --> Routes[/monitor summary/detail/workflows/log routes]
    Routes --> Dashboard[monitoring_dashboard.html]
    Dashboard --> User[Operator view]
```

## Primary Code References
- `docs/monitoring_dashboard.html`
  Dashboard UI and client-side data rendering logic.
- `src/servers/proxy_server.py`
  Monitor-serving routes such as `/monitor`, `/monitor/detail`, `/monitor/status`, and related summary/log views.
- `src/servers/proxy_server.py`
  Status-event routes: `/v1/status/start`, `/v1/status/update`, `/v1/status/finish`, `/v1/status/latest`, and `/v1/status/events`.
- `tests/test_monitor_dashboard.py`
  Dashboard route coverage.
- `tests/test_status_events.py`
  Persistent status-event coverage across restarts.

## Data and Dependencies
- Depends on in-memory monitor state plus persistent status-event storage.
- Browser log visibility depends on the browser-use logging path being configured.
- Dashboard usefulness increases with the number of enabled CATBot subsystems because it is meant to summarize cross-system activity.

## Constraints and Notes
- This is an operator-facing feature, not a substitute for raw logs or external observability tooling.
- The dashboard depends on backend services emitting enough structured progress information to be meaningful.
- Because CATBot has many optional subsystems, the dashboard is also responsible for making partial availability visible rather than hiding it.

## Related Docs
- [Scheduled Task Poller](21_scheduled_task_poller.md)
- [AutoGen Orchestration](39_autogen_orchestration.md)
- [Telegram Bot Interface](37_telegram_bot_interface.md)
