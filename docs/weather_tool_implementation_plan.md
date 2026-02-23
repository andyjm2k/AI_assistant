# Weather Tool Implementation Plan (BOM API)

## Goal
Add a new `weatherInfo` tool in the proxy server that works for both:
- HTML/web chat tool-calling flow.
- Telegram tool-calling flow.

The tool must query `bom.gov.au` weather endpoints using either:
1. a location explicitly requested by the user, or
2. the user’s saved location from memory when no location is provided.

The tool should return structured/parsed weather data so the LLM can answer either:
- specific weather questions (temperature, rain chance, wind, alerts), or
- a general weather summary.

## Scope and Architecture

### Backend (`src/servers/proxy_server.py`)
1. **Add shared weather service function**
   - Introduce `_do_proxy_weather(...)` near existing shared helpers (`_do_proxy_search`, `_do_proxy_news`).
   - Responsibilities:
     - Validate tool arguments.
     - Resolve location (explicit > memory fallback > error).
     - Query BOM endpoints with timeout + retries.
     - Parse BOM response into normalized fields.
     - Return compact structured payload designed for LLM consumption.

2. **Add secure API route for weather**
   - Add authenticated route:
     - `GET /v1/proxy/weather?location=...&detail=...`
     - optional `units` or `includeForecast` params.
   - Reuse existing auth/security middleware behavior used by other proxy APIs.
   - Ensure route returns actionable 4xx/5xx errors (missing location, BOM unavailable, parse failure).

3. **Add weather tool handling for philosopher/tool executor path**
   - In built-in tool registry used by philosopher mode, add `weather_info` mapping to shared weather function.
   - Ensure consistent response shape with other built-in tools.

### Telegram tool bridge (`src/servers/telegram_tools.py`)
1. Add `weatherInfo` tool case in `execute_telegram_tool(...)`.
2. Use shared callback from context (`do_weather`) to avoid logic duplication.
3. Validate arguments and return friendly message on missing location when no saved memory exists.
4. Keep response format consistent with existing tool responses (`success`, `message`, `data`).

### Telegram chat endpoint wiring (`src/servers/proxy_server.py`)
1. Pass `do_weather` into Telegram tool execution context (same pattern as `do_search`, `do_news`, etc.).
2. Add weather tool instructions to Telegram tool-capable system prompt file generation path (if currently in file/string constants).

### Web tool schema (`js/app.js`)
1. Add new OpenAI-style tool definition for `weatherInfo` in the `tools` array.
2. Suggested arguments schema:
   - `location` (string, optional)
   - `requestType` (enum: `summary`, `current`, `forecast`, `rain`, `wind`, `alerts`)
   - `dayOffset` (integer, optional)
3. Add execution branch in `executeToolCall(...)` to call proxy weather endpoint.
4. Keep UX behavior aligned with existing tools (status message + fallback error text).

## BOM Integration Strategy
1. **Location normalization**
   - Normalize suburb/city/state/postcode input.
   - Optionally support coordinate input if memory has lat/lon.
2. **Endpoint selection**
   - Use BOM API endpoint(s) that provide current observations + forecast.
   - Keep endpoint base configurable via `.env` (`BOM_API_BASE_URL`) for testability.
3. **Parser output contract**
   - Return a predictable shape, e.g.:
     - `resolved_location`
     - `current` (`temperature_c`, `feels_like_c`, `humidity_pct`, `wind_kph`, `condition`, `observation_time`)
     - `forecast` (list by day)
     - `alerts` (list)
     - `source` metadata
4. **LLM-oriented response**
   - Include a concise `summary` string + detailed structured `data`.
   - Enables both direct display and follow-up question answering.

## Memory Fallback Strategy
1. Try explicit `location` argument first.
2. If absent, attempt to resolve via memory manager:
   - Search user profile memory for saved/home/current location facts.
   - Use deterministic extraction priority to reduce ambiguity.
3. If still unresolved, return a clear tool error asking user for location.

## Security Requirements
1. Route remains behind existing auth requirement like other secure proxy routes.
2. Prevent SSRF/open redirect:
   - BOM host allowlist validation.
   - No user-provided raw URL fetches.
3. Apply request timeout and bounded payload parsing.
4. Sanitize error bodies from upstream before returning to client.
5. Add security logging events similar to existing secure API patterns.

## Test Plan

### Unit tests
1. `tests/test_telegram_tools.py`
   - `weatherInfo` success with explicit location.
   - `weatherInfo` success with memory fallback.
   - missing location + no memory returns friendly error.
2. New parser-focused tests (e.g. `tests/test_weather_parser.py`)
   - BOM payload → normalized schema.
   - missing fields handled gracefully.

### API tests
1. `tests/test_proxy_telegram.py`
   - Telegram weather tool loop integration.
2. Add/extend proxy tests (e.g. `tests/test_proxy_weather.py`)
   - auth required for `/v1/proxy/weather`.
   - 200 success with mocked BOM response.
   - upstream timeout/5xx mapped correctly.
   - allowlist rejection for invalid host config.

### Deterministic mocking
- Use `httpx` mocking/monkeypatch fixtures (same local testing style as existing suite).
- Never call live BOM in CI tests.

## Documentation Updates
1. **README.md**
   - Add weather tool capability to highlights/tool list.
   - Document environment variables:
     - `BOM_API_BASE_URL` (default BOM endpoint)
     - `BOM_API_TIMEOUT_SECONDS` (default timeout)
2. Add this implementation plan document under `docs/`.
3. If Telegram tool docs exist, add `weatherInfo` examples.

## Auto-installer / Setup Impact
1. **Dependencies**
   - No new third-party dependency required if using existing `httpx`.
2. **Env templates**
   - Add `BOM_API_BASE_URL` and `BOM_API_TIMEOUT_SECONDS` to `.env.example`.
3. **Install wizard**
   - Ensure generated `.env` preserves defaults for BOM weather settings.
4. **Verify scripts**
   - Optional: extend `scripts/verify_install.py` to check weather env vars are present (non-blocking defaults).

## Delivery Sequence
1. Implement shared weather service + secure route.
2. Wire tool definitions for web and Telegram.
3. Add parser + memory fallback.
4. Add tests (unit + integration + security).
5. Update docs and installer/env templates.
6. Run full relevant test subset and ship.
