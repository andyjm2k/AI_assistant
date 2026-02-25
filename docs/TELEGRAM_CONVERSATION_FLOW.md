# Telegram Conversation Flow and Handlers

This document describes the current Telegram conversation flow in CATBot, the key handlers involved, and the observed tool-call behavior. It also documents a requirement for periodic state updates for both Telegram and the HTML client.

Last updated: 2026-02-24

## Scope
- Telegram bot handlers and backend flow.
- Tool-call loop for Telegram, including fallback behavior.
- HTML (web) tool-call loop locations for parity discussion.
- Requirement: periodic state/progress messages every 1 minute.

## Telegram Handlers (Bot Layer)
Source: `src/integrations/telegram_bot.py`

Handlers registered in `main()`:
1. `/start` -> `start_command`
   - Authorization check via `is_authorized`.
   - Sends greeting and initializes message count.
2. `/help` -> `help_command`
   - Returns command list.
3. `/status` -> `status_command`
   - Calls backend `/health`, reports latency and message count.
4. `/clear` -> `clear_command`
   - Calls backend DELETE `/v1/telegram/chat/{conversation_id}`.
5. Text messages -> `handle_text`
   - Sends `ChatAction.TYPING`, forwards message to backend with `call_backend_chat`.
   - Returns final reply or generic error message on failure.

Key utilities:
- `call_backend_chat()` sends POST `/v1/telegram/chat` with `{ conversation_id, user_id, message }`.
- `clear_backend_history()` sends DELETE `/v1/telegram/chat/{conversation_id}`.
- `check_backend_health()` calls `/health`.

## Telegram Backend Flow (Proxy Server)
Source: `src/servers/proxy_server.py`

Entry point:
- `POST /v1/telegram/chat` -> `telegram_chat_endpoint()`

High-level flow:
1. Validate secret header if `TELEGRAM_SECRET` is configured.
2. Validate message and compute `conversation_id`.
3. Special case: if message requests proxy restart, schedule and return immediately.
4. Load model config and build system prompt (tools enabled or base).
5. Inject assistant context block and optional memory context.
6. Construct OpenAI-compatible payload and call the model endpoint.
7. Parse LLM reply and enter tool loop if tools are enabled.
8. Append assistant reply to `telegram_conversations` history.
9. Optional memory extraction (auto-extract).
10. Return `TelegramChatResponse`.

Key Telegram data structures:
- `telegram_conversations`: per-conversation chat history.
- `telegram_todo`, `telegram_memory_cache`: per-conversation stores used by Telegram tools.

## Telegram Tool Loop (Backend)
Source: `src/servers/proxy_server.py` + `src/servers/telegram_tools.py`

When `TELEGRAM_TOOLS_ENABLED=true`:
1. Parse tool call from the LLM response using `telegram_tools.parse_telegram_tool_response`.
2. Execute tool via `telegram_tools.execute_telegram_tool(...)` with a context that includes:
   - search/news/weather/autogen/codex/browser/deep-research handlers.
   - todo and memory cache stores.
   - internal file ops and drive upload helpers.
3. Add a "tool result" as a user message to `working_messages`.
4. Call the LLM again to produce a final user-facing response.
5. Repeat for up to `TELEGRAM_TOOLS_MAX_ITERATIONS`.

Fallback behaviors:
- If the follow-up LLM call fails, or returns no content, the tool result is used to build a reply.
- If the final reply still looks like a raw tool call, the last tool result is used instead.

Observed issue (as reported):
- When tools are executed (single or chained), the tool result is not reliably returned to the default LLM for a complete response cycle. This can result in the user seeing raw tool-call XML or incomplete output.
- The Telegram backend includes some fallback logic, but the chain can still fail when the follow-up call is empty or errors.

## HTML (Web) Tool Flow (For Parity)
Source: `js/app.js`

Primary paths:
- OpenAI/LMS tool calls:
  - `message.tool_calls` is handled in the main send flow.
  - `executeToolCall(...)` executes each tool.
  - A follow-up LLM call is made with tool results.
  - If the follow-up returns empty content, a fallback uses the last tool result.
- XML tool calls (Qwen-style):
  - `parseToolResponse(...)` detects tool call in assistant content.
  - Tool executes, then a follow-up call is made to get the final reply.

## Requirement: Periodic State Updates (Telegram + HTML)
Problem:
- Users do not see progress while long-running tools or multi-step tool chains run.
- When tool loops fail to return a final response, the user sees incomplete output.

Requirement:
- Emit a "state/progress" message every 60 seconds while work is ongoing.
- The state message must describe the current tool or processing step.
- The final response must always be a satisfactory answer or a summary of the completed task.

Recommended behavior:
1. Start a 60-second timer when a tool call starts or when LLM work begins.
2. Send a short status message on each tick until a final response is ready.
3. Stop the timer immediately once a final response is sent.
4. If a tool chain fails, send a summary of what succeeded and what failed.

Suggested status messages (examples):
- "Working: searching the web for sources."
- "Working: running browser agent to extract details."
- "Working: summarizing tool results."

Telegram delivery:
- Use `update.message.reply_text(...)` from the bot layer, or send via the proxy if tool loop is entirely server-side.

HTML delivery:
- Append a "state" message to the conversation stream in the UI, styled as a system/progress update.

## Where To Implement (Pointers)
Telegram:
- Bot layer: `src/integrations/telegram_bot.py` (if you want the bot to emit status messages).
- Backend layer: `src/servers/proxy_server.py` inside `telegram_chat_endpoint()` and tool loop (if you want to emit status from the proxy).

HTML:
- Tool execution path in `js/app.js` within the tool-call handling blocks.
- The state message can be injected into the existing chat history and UI rendering.
