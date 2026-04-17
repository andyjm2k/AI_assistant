# News Lookup

## Product Purpose
News lookup gives CATBot a direct path for topical article discovery. It is a specialized retrieval feature for recent news coverage, separate from general web search and useful when the user wants article-oriented results rather than broad web pages.

## User-Facing Behavior
- Users can ask for news about a topic and receive article results with titles, links, descriptions, and dates.
- Web flows can save news results to a file for later use.
- Telegram tool flows can fetch news and write the results to CSV in the scratch workspace.
- News search is also available as a tool to higher-level agent workflows when the API key is configured.

## How It Works
- `src/servers/proxy_server.py` exposes `GET /v1/proxy/news`.
- The backend helper around the route checks `NEWS_API_KEY`, calls the News API provider, and normalizes the returned articles into a structured result.
- `js/app.js` implements `handleNews({ searchTerm, filename })`, which requests news results and can write them into a file-oriented output flow for the user.
- Telegram uses the `fetchNews` tool path in `src/servers/telegram_tools.py`, which calls the shared `do_news` callback and writes CSV output through the backend file writer.
- The proxy tool registry only exposes the news-search tool when `NEWS_API_KEY` is available, which keeps unavailable integrations from surfacing as broken tools.

## Expanded Flow Diagram
```mermaid
flowchart TD
    Topic[News topic query] --> Proxy[/v1/proxy/news]
    Proxy --> KeyCheck{NEWS_API_KEY configured?}
    KeyCheck -->|No| Error[Return configuration error]
    KeyCheck -->|Yes| NewsAPI[News API request]
    NewsAPI --> Articles[Structured article list]
    Articles --> Web[Web response]
    Articles --> TelegramCSV[Telegram fetchNews writes CSV]
    Articles --> Tool[News-search tool result]
```

## Primary Code References
- `src/servers/proxy_server.py`
  News helper and route: `GET /v1/proxy/news`.
- `src/servers/proxy_server.py`
  Tool registration for news-search capability when `NEWS_API_KEY` is present.
- `js/app.js`
  News client path: `handleNews({ searchTerm, filename })`.
- `src/servers/telegram_tools.py`
  Telegram `fetchNews` behavior and CSV writing path.
- `tests/test_telegram_tools.py`
  Coverage for news file-writing behavior in Telegram flows.

## Data and Dependencies
- Depends on `NEWS_API_KEY` and the upstream news provider.
- File-saving flows depend on the scratch workspace writer.
- News output is typically used for reading, summarization, or downstream analysis rather than as a final presentation artifact by itself.

## Constraints and Notes
- This feature is provider-dependent and unavailable until `NEWS_API_KEY` is configured.
- News lookup is topical retrieval, not semantic summarization; downstream prompting or tools still determine how article results are used.
- Because it is news-specific, it complements rather than replaces the general web-search feature.

## Related Docs
- [Web Search](25_web_search.md)
- [File Workspace](28_file_workspace.md)
- [Tool-Enabled Telegram](38_tool_enabled_telegram.md)
