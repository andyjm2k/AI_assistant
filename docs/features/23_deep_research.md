# Deep Research

## Product Purpose
Deep research is CATBot's multi-step browsing and synthesis workflow. It goes beyond a single search or fetch request by coordinating multiple browser-assisted passes and returning a more complete research report.

## User-Facing Behavior
- Users can submit a research task and receive a synthesized report rather than a single page scrape.
- The feature can control parallel browser capacity through request parameters.
- Telegram can invoke the same research path when tool-enabled mode is active.
- Research output can also be saved into a configured research directory through the browser bridge layer.

## How It Works
- `src/servers/proxy_server.py` exposes `/v1/proxy/deep-research` as the product-facing route.
- The proxy normalizes incoming request bodies with `_normalize_deep_research_body(...)`, mapping aliases such as `researchTask` into the canonical `research_task`.
- `_do_deep_research(...)` forwards the normalized request to the browser bridge at `/api/deep-research`, tracks monitor state, and promotes returned report text into the response message when appropriate.
- `src/servers/mcp_browser_server.py` implements `/api/deep-research`, validates required parameters, and then calls the underlying browser-use client with the configured research task and concurrency options.
- The bridge can save outputs into `MCP_RESEARCH_SAVE_DIRECTORY`, which turns research into a persisted artifact rather than only a transient response.
- Telegram integrates through `src/servers/telegram_tools.py`, where `runDeepResearch` delegates to the shared `do_deep_research` callable provided in the execution context.

## Expanded Flow Diagram
```mermaid
flowchart TD
    UserTask[Research task] --> Proxy[/v1/proxy/deep-research]
    Proxy --> Normalize[_normalize_deep_research_body]
    Normalize --> Monitor[Start monitor run]
    Monitor --> Bridge[/api/deep-research]
    Bridge --> Validate{research_task present?}
    Validate -->|No| Error[Return validation error]
    Validate -->|Yes| BrowserUse[run_deep_research via browser-use client]
    BrowserUse --> Parallel[Parallel browser/search passes]
    Parallel --> Synthesis[Collected evidence and report]
    Synthesis --> Save[Optional save to research directory]
    Save --> ProxyResult[Promote report to response]
```

## Primary Code References
- `src/servers/proxy_server.py`
  Product route: `/v1/proxy/deep-research`.
- `src/servers/proxy_server.py`
  Helpers: `_normalize_deep_research_body(...)` and `_do_deep_research(...)`.
- `src/servers/mcp_browser_server.py`
  Bridge route: `/api/deep-research`.
- `src/servers/mcp_browser_server.py`
  Browser-use call path inside `deep_research_endpoint()`.
- `src/servers/telegram_tools.py`
  `runDeepResearch` tool dispatch.
- `tests/test_proxy_telegram.py`
  Deep-research proxy normalization and forwarding tests.
- `tests/test_telegram_tools.py`
  Telegram-side deep-research tool behavior tests.

## Data and Dependencies
- Depends on the browser automation stack being available.
- Optional research artifact persistence depends on `MCP_RESEARCH_SAVE_DIRECTORY`.
- Output often becomes an input to later summarization, comparison, or workflow steps.

## Constraints and Notes
- Deep research is guarded against overlapping runs in some conversation paths because it is resource-intensive.
- It is a browser-backed workflow, so failures can come from either CATBot code or the underlying browsing runtime.
- The feature returns a synthesized report, but the quality still depends on the research prompt and the sites reached during the run.

## Related Docs
- [Browser Automation](22_browser_automation.md)
- [Web Fetch and Scraping](24_web_fetch_and_scraping.md)
- [Tool-Enabled Telegram](38_tool_enabled_telegram.md)
