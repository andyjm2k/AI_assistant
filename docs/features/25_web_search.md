# Web Search

## Product Purpose
Web search is CATBot's discovery layer for current web information. It is often the first step before scraping, deep research, or synthesizing an answer about something outside the local codebase or memory store.

## User-Facing Behavior
- CATBot can return structured web search results for a query.
- When Brave Search is configured, CATBot prefers it; otherwise it can fall back to DuckDuckGo-style behavior.
- Search is available to the web app, Telegram tools, and multi-agent workflows.
- Search results can feed directly into later fetch, scrape, and browser steps.

## How It Works
- `src/servers/proxy_server.py` exposes `/v1/proxy/search`.
- The proxy checks whether Brave Search credentials are available and uses the Brave path when possible.
- If Brave is unavailable or not configured, CATBot falls back to an alternative search path instead of disabling search entirely.
- Search is also represented in the internal tool registry through tool names such as `webSearch`, so agentic flows can call it as a first-class capability.
- AutoGen team configs and Telegram tools both rely on the same backend search behavior rather than implementing separate providers.

## Expanded Flow Diagram
```mermaid
flowchart TD
    Query[Search query] --> Proxy[/v1/proxy/search]
    Proxy --> BraveCheck{Brave configured?}
    BraveCheck -->|Yes| Brave[Brave Search request]
    BraveCheck -->|No| Fallback[Fallback search provider]
    Brave --> Results[Structured search results]
    Fallback --> Results
    Results --> Consumer[Web UI, Telegram, AutoGen, fetch/scrape pipeline]
```

## Primary Code References
- `src/servers/proxy_server.py`
  Search route: `/v1/proxy/search`.
- `src/servers/proxy_server.py`
  Internal tool registry entries for search-oriented actions.
- `src/servers/telegram_tools.py`
  Telegram `webSearch` tool path via `do_search`.
- `src/autogen/team_builder.py`
  Research-capable roles that include web search in their tool budgets.
- `scripts/install_wizard.py`
  Setup path for Brave Search configuration.

## Data and Dependencies
- Primary provider is Brave Search when configured.
- Fallback behavior reduces hard dependency on a single provider.
- Search output becomes input for fetch, scrape, deep research, or human-facing summaries.

## Constraints and Notes
- Search only discovers candidate sources; it does not guarantee that the final answer reflects page content unless a later retrieval step follows.
- Provider availability, rate limits, and current-web freshness are external dependencies.
- This feature is most valuable when composed with fetch, browser, or research features rather than used in isolation.

## Related Docs
- [Deep Research](23_deep_research.md)
- [Web Fetch and Scraping](24_web_fetch_and_scraping.md)
- [News Lookup](26_news_lookup.md)
