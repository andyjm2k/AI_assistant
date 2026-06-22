# Automatic Memory-Aware Conversation

## Product Purpose

CATBot retrieves relevant durable memory before a response so Electron and
Telegram can personalize answers without relying on the model to call a memory
tool.

## User-Facing Behavior

- Normal conversations can use remembered preferences, profile facts, and
  relevant prior interactions.
- Retrieval is scoped to the authenticated user.
- Task execution records do not enter normal conversation context.
- Philosopher mode uses its own scoped retrieval path.
- Retrieval failures do not block the main conversation.

## How It Works

The Electron client calls `POST /v1/memory/context` with the current prompt,
conversation ID, item limit, and token budget. The server:

1. Derives the namespace from the authenticated username.
2. Filters active, unexpired conversation-memory kinds before ranking.
3. Combines lexical and compatible semantic scores.
4. Deduplicates and diversifies the results.
5. Escapes memory text and returns a bounded `<memory_evidence>` block that
   explicitly labels the content as untrusted data.

Telegram calls the same `MemoryManager.build_context()` policy with its
server-owned user key. Neither channel implements its own memory classifier,
ranking thresholds, or prompt formatter.

## Flow

```mermaid
flowchart TD
    Prompt[User prompt] --> Endpoint[/v1/memory/context]
    Endpoint --> Auth[Authenticated namespace]
    Auth --> Retrieve[Shared hybrid retrieval]
    Retrieve --> Safe[Safe bounded evidence block]
    Safe --> Inject[Append to system prompt]
    Inject --> Model[Generate response]
```

## Primary Code References

- `js/app.js`: `fetchConversationMemoryContext(prompt)` and request assembly.
- `src/servers/memory_api.py`: authenticated context endpoint.
- `src/memory/retrieval_service.py`: candidate filtering and hybrid ranking.
- `src/memory/context_builder.py`: prompt-safe context construction.
- `src/servers/proxy_server.py`: Telegram conversation integration.

## Constraints

- Memory evidence can be stale or malicious and must never be treated as
  instructions.
- The server owns namespace selection; client-supplied user identifiers are not
  trusted.
- Context is bounded by both result count and token estimate.
- Explicit memory tools remain available for user-directed inspection and
  management.

## Related Docs

- [Prompt and Persona Layering](12_prompt_and_persona_layering.md)
- [Long-Term Memory System](14_long_term_memory_system.md)
- [Memory Quality Controls](15_memory_quality_controls.md)
