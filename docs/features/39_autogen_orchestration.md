# Workflow Orchestration (AutoGen / AG2)

## Product Purpose
Workflow orchestration gives CATBot a multi-agent planning and execution mode. Instead of using one assistant persona for everything, CATBot can run a virtual product company where specialized roles collaborate through a managed team chat. AutoGen remains the default backend, and AG2 can be selected with `WORKFLOW_FRAMEWORK=ag2`.

## User-Facing Behavior
- Users can trigger a multi-agent workflow through the proxy.
- The team is organized around explicit roles such as CEO, PM, marketer, architect, engineer, QA, and user proxy.
- Workflow runs can emit progress notes, write scratch logs, and return a normalized response shape across AutoGen and AG2.
- Some roles can use tools such as search, browser automation, deep research, and Codex to support their part of the workflow.

## How It Works
- `src/autogen/team_builder.py` defines the role prompts, helper tools, selector behavior, and exported team construction logic.
- `src/workflows/config.py` parses `WORKFLOW_FRAMEWORK`.
- `src/workflows/ag2_runner.py` lazy-loads AG2, builds the equivalent role team, registers shared role tools, and normalizes AG2 chat history.
- `config/team-config.json` stores the serialized team configuration used for runtime loading and Studio/export workflows.
- `src/servers/proxy_server.py` loads and warms the AutoGen team on startup, with both Python-builder and JSON fallback logic.
- `_do_workflow(...)` selects the configured backend. `_do_autogen(...)` remains the AutoGen compatibility path, and `_do_ag2_workflow(...)` handles AG2 runs.
- `scripts/start_all.py` and `scripts/restart_all.py` preflight the selected workflow backend, so `WORKFLOW_FRAMEWORK=ag2` is checked before service launch or restart stop/start.
- The generic route surface is `/v1/proxy/workflow`; `/v1/proxy/autogen` remains an AutoGen-only compatibility route.
- Workflow runs are represented in monitoring and status systems so the user can inspect ongoing multi-agent activity.

## Expanded Flow Diagram
```mermaid
flowchart TD
    UserTask[Workflow request] --> Proxy[/v1/proxy/workflow]
    Proxy --> Select{WORKFLOW_FRAMEWORK}
    Select --> AutoGen[AutoGen SelectorGroupChat]
    Select --> AG2[AG2 GroupChat]
    AutoGen --> Team[Virtual company roles]
    AG2 --> Team
    Team --> CEO[CEO]
    Team --> PM[Product Manager]
    Team --> Architect[Architect]
    Team --> Engineer[Lead Engineer]
    Team --> QA[QA Officer]
    Team --> Others[Other role agents]
    Others --> Tools[Search, browser, research, Codex, etc.]
    Tools --> Team
    Team --> Transcript[Conversation messages]
    Transcript --> Scratch[Write AutoGen scratch log]
    Scratch --> Response[Return normalized workflow output]
```

## Primary Code References
- `src/autogen/team_builder.py`
  Team definitions, tool budgets, role prompts, and export helpers.
- `config/team-config.json`
  Serialized team configuration.
- `src/servers/proxy_server.py`
  Team loading/warmup logic and runtime loader.
- `src/servers/proxy_server.py`
  Shared execution paths: `_do_workflow(...)`, `_do_autogen(...)`, and `_do_ag2_workflow(...)`.
- `src/servers/proxy_server.py`
  Routes: `/v1/proxy/workflow` and `/v1/proxy/autogen`.
- `src/workflows/ag2_runner.py`
  Optional AG2 backend implementation.
- `scripts/install_optional_workflow_backend.py`
  Installs `ag2[openai]` when AG2 is selected in `.env`.
- `scripts/start_all.py` and `scripts/restart_all.py`
  Startup and restart checks for the selected workflow backend.
- `scripts/export_autogen_team_config.py`
  Export workflow for the team configuration.
- `tests/test_autogen_team.py`
  Team-builder and runtime-loader coverage.
- `tests/test_ag2_runner.py`
  Mocked AG2 construction, tool registration, and history normalization coverage.

## Data and Dependencies
- AutoGen depends on the pinned AutoGen 0.7.x packages in `requirements.txt`.
- AG2 is optional and installed by `scripts/install_optional_workflow_backend.py` when `WORKFLOW_FRAMEWORK=ag2`.
- Start and restart scripts verify the selected backend with `scripts.verify_install.check_workflow_backend` before launching or cycling services.
- Scratch logging and monitor integration provide persistence and visibility for team runs.
- Tool-equipped roles depend on the same configured downstream integrations used elsewhere in CATBot.

## Constraints and Notes
- Multi-agent backends are more operationally complex than single-agent chat and have explicit compatibility handling for provider quirks.
- The proxy is designed to continue working even when a selected workflow backend is unavailable, returning a clear configuration or dependency error.
- Multi-agent collaboration quality depends on both the team definition and the stability of the underlying model provider.

## Related Docs
- [Web Search](25_web_search.md)
- [Browser Automation](22_browser_automation.md)
- [Codex CLI Integration](40_codex_cli_integration.md)
