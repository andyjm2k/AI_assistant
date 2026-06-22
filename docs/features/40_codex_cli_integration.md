# Codex CLI Integration

## Product Purpose
Codex CLI integration gives CATBot a path into real coding execution. It allows the platform to hand off code-oriented tasks to a non-interactive Codex process rather than stopping at planning or suggestion text.

## User-Facing Behavior
- Users and other CATBot workflows can trigger a Codex run through the proxy.
- Codex runs produce scratch artifacts such as summaries, last-message captures, and event logs.
- AutoGen can route engineering tasks into an isolated Codex workspace instead of pointing Codex at the live repo.
- Telegram tool-enabled mode can also invoke Codex through the same backend pathway.

## How It Works
- `src/servers/proxy_server.py` exposes `POST /v1/proxy/codex`.
- `_run_codex_cli(prompt, isolated_workspace=False)` builds the Codex CLI command, runs it non-interactively, captures stdout/stderr, and returns a structured result.
- `_prepare_autogen_codex_workspace()` creates an isolated workspace under `scratch/autogen` for AutoGen-triggered Codex runs, preventing those flows from working directly in the live CATBot repo.
- `_write_codex_summary_to_scratch(...)` and `_write_codex_error_to_scratch(...)` persist human-readable run artifacts so each Codex invocation leaves a traceable output.
- The proxy injects `do_codex` into Telegram tool execution context, and the AutoGen team config includes a `codex_cli_task` helper for the lead engineer role.
- Access to the route is guarded so either a user JWT or the AutoGen team secret is required.

## Expanded Flow Diagram
```mermaid
flowchart TD
    Prompt[Codex task prompt] --> Route[/v1/proxy/codex]
    Route --> Auth{User JWT or AutoGen secret?}
    Auth -->|No| Reject[Reject request]
    Auth -->|Yes| Workspace{Isolated workspace requested?}
    Workspace -->|Yes| Prepare[_prepare_autogen_codex_workspace]
    Workspace -->|No| Live[Use current workspace]
    Prepare --> Exec[_run_codex_cli]
    Live --> Exec
    Exec --> Codex[Codex CLI process]
    Codex --> Capture[Capture stdout, stderr, events]
    Capture --> Scratch[Write summary/error artifacts]
    Scratch --> Result[Structured response]
```

## Primary Code References
- `src/servers/proxy_server.py`
  Route: `POST /v1/proxy/codex`.
- `src/servers/proxy_server.py`
  Main runner: `_run_codex_cli(...)`.
- `src/servers/proxy_server.py`
  Isolated-workspace helper: `_prepare_autogen_codex_workspace()`.
- `src/servers/proxy_server.py`
  Scratch writers: `_write_codex_summary_to_scratch(...)` and `_write_codex_error_to_scratch(...)`.
- `src/servers/proxy_server.py`
  Telegram and AutoGen context injection for Codex usage.
- `config/team-config.json`
  `codex_cli_task` helper used by AutoGen's lead engineer role.
- `tests/test_proxy_codex.py`
  Route, workspace, and scratch-output coverage.
- `tests/test_telegram_tools.py`
  Telegram-side Codex tool coverage.

## Data and Dependencies
- Depends on the external Codex CLI being installed and reachable at `CODEX_CLI_PATH`.
- Scratch output stores summaries, error reports, and event logs for each run.
- AutoGen isolation depends on the scratch/autogen workspace model.

## Constraints and Notes
- This is non-interactive Codex execution, not a fully embedded agent IDE.
- The isolated AutoGen workspace is an explicit safety and containment mechanism.
- Codex CLI integration is complementary to the GitHub skill and AutoGen orchestration: it handles code work, while those features handle workflow structure and repo lifecycle.

## Related Docs
- [GitHub Project Management Skill](35_github_project_management_skill.md)
- [Workflow Orchestration](39_autogen_orchestration.md)
- [Security Controls](45_security_controls.md)
