# Browser Automation

## Product Purpose
Browser automation lets CATBot operate on real websites rather than only on API-backed tools or plain text. It is the bridge between natural-language instructions and interactive browser work such as navigation, clicking, filling forms, and extracting page state.

## User-Facing Behavior
- Web and Telegram users can trigger browser-agent workflows through CATBot.
- Browser tasks run through the product-facing proxy route instead of exposing the browser-use runtime directly.
- Automation health and active runs can be observed through the monitoring layer.
- The browser stack is also reused by higher-level features such as deep research.

## How It Works
- `scripts/start_mcp_browser_use_http_server.py` launches the `mcp-server-browser-use` HTTP runtime and prepares its local runtime directories.
- `src/servers/mcp_browser_server.py` is the guarded bridge process in front of the browser-use runtime. It exposes protected endpoints such as `/api/browser-agent` and checks the shared secret before forwarding work.
- `src/mcp/mcp_browser_client.py` provides the client-side integration layer used by the bridge or proxy to talk to the browser-use runtime.
- `src/servers/proxy_server.py` exposes the product-facing `/v1/proxy/browser-agent` route so the rest of CATBot can treat browser automation like a first-class internal capability.
- Browser automation is also surfaced as a tool in the proxy tool registry, which makes it available to Telegram, philosopher mode, and orchestration flows when configured.

## Expanded Flow Diagram
```mermaid
flowchart LR
    User[Web UI or Telegram] --> Proxy[/v1/proxy/browser-agent]
    Proxy --> GuardedBridge[mcp_browser_server]
    GuardedBridge --> Secret{Shared secret valid?}
    Secret -->|No| Reject[Reject request]
    Secret -->|Yes| BrowserClient[mcp_browser_client]
    BrowserClient --> BrowserUse[mcp-server-browser-use HTTP runtime]
    BrowserUse --> Session[Playwright-backed browser session]
    Session --> Result[Structured automation result]
    Result --> Proxy
```

## Primary Code References
- `scripts/start_mcp_browser_use_http_server.py`
  Launches and configures the browser-use HTTP runtime.
- `src/servers/mcp_browser_server.py`
  Protected bridge layer and route definitions such as `/api/browser-agent`.
- `src/mcp/mcp_browser_client.py`
  Client used to talk to the browser-use server.
- `src/servers/proxy_server.py`
  Product route: `/v1/proxy/browser-agent`.
- `tests/test_mcp_browser_server.py`
  Validates the bridge behavior and protected routing assumptions.
- `docs/BROWSER_USE_INSTALL_GUIDE.md`
  Installation and runtime expectations for the browser-use stack.

## Data and Dependencies
- Depends on the `mcp-browser-use` checkout, Playwright/browser runtime pieces, and the launched HTTP server.
- Depends on the bridge shared secret to avoid exposing expensive browser endpoints broadly.
- Output can feed into downstream reasoning, research, or task-execution flows.

## Constraints and Notes
- Browser automation is multi-process in this codebase: launcher, bridge, proxy, and browser-use runtime each have a distinct role.
- Failures in the browser-use runtime degrade both direct browser-agent use and deep research.
- Because automation acts on live websites, reliability depends on page behavior, selectors, and remote site changes.

## Related Docs
- [Deep Research](23_deep_research.md)
- [Web Fetch and Scraping](24_web_fetch_and_scraping.md)
- [Monitoring Dashboard](43_monitoring_dashboard.md)
