# AutoGen Orchestration

## Product Purpose
AutoGen orchestration gives CATBot a multi-agent planning and execution mode. Instead of using one assistant persona for everything, CATBot can run a virtual product company where specialized roles collaborate through a managed team chat.

## User-Facing Behavior
- Users can trigger a multi-agent workflow through the proxy.
- The team is organized around explicit roles such as CEO, PM, marketer, architect, engineer, QA, and user proxy.
- AutoGen runs can emit progress notes, write scratch logs, and retry around known provider quirks.
- Some roles can use tools such as search, browser automation, deep research, and Codex to support their part of the workflow.

## How It Works
- `src/autogen/team_builder.py` defines the role prompts, helper tools, selector behavior, and exported team construction logic.
- `config/team-config.json` stores the serialized team configuration used for runtime loading and Studio/export workflows.
- `src/servers/proxy_server.py` loads and warms the AutoGen team on startup, with both Python-builder and JSON fallback logic.
- `_do_autogen(...)` is the shared execution path used by the route and Telegram tool runner. It loads or reloads the team when needed, starts executors, tracks progress notes, handles provider-specific failure cases, and writes conversation logs to scratch.
- The main route surface is `/v1/proxy/autogen`.
- AutoGen runs are also represented in monitoring and status systems so the user can inspect ongoing multi-agent activity.

## Expanded Flow Diagram
```mermaid
flowchart TD
    UserTask[Workflow request] --> Proxy[/v1/proxy/autogen]
    Proxy --> Load[Load or reload AutoGen team]
    Load --> Team[SelectorGroupChat virtual company]
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
    Scratch --> Response[Return workflow output]
```

## Primary Code References
- `src/autogen/team_builder.py`
  Team definitions, tool budgets, role prompts, and export helpers.
- `config/team-config.json`
  Serialized team configuration.
- `src/servers/proxy_server.py`
  Team loading/warmup logic and runtime loader.
- `src/servers/proxy_server.py`
  Shared execution path: `_do_autogen(...)`.
- `src/servers/proxy_server.py`
  Route: `/v1/proxy/autogen`.
- `scripts/export_autogen_team_config.py`
  Export workflow for the team configuration.
- `tests/test_autogen_team.py`
  Team-builder and runtime-loader coverage.

## Data and Dependencies
- Depends on AutoGen packages and a compatible chat-model backend for multi-agent execution.
- Scratch logging and monitor integration provide persistence and visibility for team runs.
- Tool-equipped roles depend on the same configured downstream integrations used elsewhere in CATBot.

## Constraints and Notes
- AutoGen is more operationally complex than single-agent chat and has explicit compatibility handling for some providers.
- The proxy is designed to continue working even when AutoGen is unavailable, which shows that this is an optional but significant product layer.
- Multi-agent collaboration quality depends on both the team definition and the stability of the underlying model provider.

## Related Docs
- [Web Search](25_web_search.md)
- [Browser Automation](22_browser_automation.md)
- [Codex CLI Integration](40_codex_cli_integration.md)
