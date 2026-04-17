# Automatic Memory-Aware Conversation

## Product Purpose
CATBot can proactively search memory before answering certain kinds of questions. Instead of waiting for the model to choose a memory tool call, the web client detects opinion- and knowledge-style prompts and injects relevant memory context into the request automatically.

## User-Facing Behavior
- When the user asks a reflective or knowledge-oriented question, CATBot can answer with remembered preferences, prior discussions, and stored context.
- Action-oriented prompts skip this automatic memory search so operational requests do not get cluttered with irrelevant conversational memory.
- Philosopher mode suppresses the normal auto-search path because it manages its own reflective memory context.
- The memory search happens before the main reply and is intended to be invisible unless it materially changes the answer quality.

## How It Works
- `js/app.js` implements `isOpinionOrKnowledgeQuestion(prompt)`, which uses pattern matching to distinguish reflective or informational prompts from action requests.
- If the prompt qualifies, `autoSearchMemoriesForQuestion(prompt)` calls the backend memory search path and requests a small, relevant set of memories using tuned thresholds.
- During main message preparation, the frontend checks whether philosopher mode is active. If it is not, memory context from `autoSearchMemoriesForQuestion()` is appended to `effectiveSystemPrompt`.
- The injected block explicitly tells the model that the appended snippets are relevant context from previous conversations and should be used to personalize the answer.
- On the backend, `src/servers/proxy_server.py` exposes `/v1/memory/search`, and Telegram has a similar but separate memory-aware flow using `_extract_memory_search_query()` and Telegram-specific thresholds when tool-enabled conversation is running there.
- The underlying memory results come from `MemoryManager.search_memories()` and then inherit any filtering rules defined for conversational context.

## Expanded Flow Diagram
```mermaid
flowchart TD
    Prompt[User prompt] --> Detect[isOpinionOrKnowledgeQuestion]
    Detect -->|Action request| Direct[Skip auto memory search]
    Detect -->|Opinion or knowledge| Search[autoSearchMemoriesForQuestion]
    Search --> Proxy[/v1/memory/search]
    Proxy --> Manager[MemoryManager.search_memories]
    Manager --> Vector[Vector store similarity search]
    Vector --> Results[Ranked memory snippets]
    Results --> Filter[Conversation-context filtering]
    Filter --> Inject[Append memory context to effectiveSystemPrompt]
    Direct --> Request[Main chat request]
    Inject --> Request
    Request --> Model[Final model response]
```

## Primary Code References
- `js/app.js`
  Key detection logic: `isOpinionOrKnowledgeQuestion(prompt)`.
- `js/app.js`
  Key retrieval logic: `autoSearchMemoriesForQuestion(prompt)`.
- `js/app.js`
  Request assembly path where `memoryContext` is appended to `effectiveSystemPrompt` before the main send.
- `src/servers/proxy_server.py`
  Memory query helper: `_extract_memory_search_query(message_text)` for Telegram-side topic extraction.
- `src/servers/proxy_server.py`
  Memory route: `@app.post("/v1/memory/search")`.
- `src/memory/memory_manager.py`
  Retrieval path: `search_memories(...)` and `filter_memories_for_conversation_context(...)`.
- `docs/SYSTEM_FLOW_DIAGRAM.md`
  Cross-system explanation of the opinion/action branching and auto-search behavior.

## Data and Dependencies
- Depends on the long-term memory system being initialized and embeddings being available.
- Uses the current prompt text itself as the basis for retrieval, sometimes after extracting a more focused search phrase.
- The injected context is ephemeral per request; it is not itself a permanent prompt rewrite.

## Constraints and Notes
- This feature is intentionally selective. If every prompt triggered memory retrieval, the assistant would overfit to stale or irrelevant context.
- Browser and Telegram flows are similar in intent but not identical in implementation detail.
- The quality of this feature depends on both retrieval accuracy and the memory-quality filters that keep noisy operational state out of the conversational context set.

## Related Docs
- [Prompt and Persona Layering](12_prompt_and_persona_layering.md)
- [Long-Term Memory System](14_long_term_memory_system.md)
- [Memory Quality Controls](15_memory_quality_controls.md)
