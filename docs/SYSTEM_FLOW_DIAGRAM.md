# CATBot System Flow

Last updated: 2026-06-15

## Browser Conversation

```mermaid
flowchart TD
    Input[User prompt] --> ContextRequest[POST /v1/memory/context]
    ContextRequest --> Auth[Authenticate request]
    Auth --> Namespace[Derive namespace from authenticated username]
    Namespace --> Retrieve[Prefilter kinds and run hybrid retrieval]
    Retrieve --> SafeContext[Escape and bound untrusted memory evidence]
    SafeContext --> Prompt[Assemble system prompt and conversation history]
    Prompt --> Chat[POST /v1/chat/completions]
    Chat --> Tools{Tool calls?}
    Tools -->|Yes| Execute[Execute authorized tools]
    Execute --> Chat
    Tools -->|No| Display[Display and speak response]
    Display --> Extract[POST /v1/memory/extract with stable source IDs]
```

The browser does not classify memory questions, rank memories, or format raw
records for prompt injection. It asks the server for a ready-to-use context
block. Philosopher mode skips this normal browser context request because it
uses its own namespace-scoped retrieval path.

## Telegram Conversation

```mermaid
flowchart TD
    Message[Telegram message] --> Identity[Resolve authenticated Telegram user key]
    Identity --> Context[MemoryManager.build_context]
    Context --> Model[Run chat completion with tools]
    Model --> ToolLoop{Tool calls?}
    ToolLoop -->|Yes| Tool[Execute Telegram tool with server-owned user key]
    Tool --> Model
    ToolLoop -->|No| Reply[Send response]
    Reply --> Extract[Run idempotent memory extraction]
```

Telegram and Electron use the same retrieval, kind filtering, ranking, and
context safety policy. User-controlled request fields cannot override the
server-owned memory namespace.

## Memory Context

```mermaid
flowchart TD
    Query[Query plus purpose] --> Scope[Mandatory namespace]
    Scope --> Filter[Filter active, unexpired, allowed kinds]
    Filter --> Lexical[FTS lexical candidates]
    Filter --> Semantic[Compatible embedding candidates]
    Lexical --> Rank[Combine scores and quality signals]
    Semantic --> Rank
    Rank --> Diversify[Deduplicate and diversify]
    Diversify --> Bound[Apply item and token budgets]
    Bound --> Escape[HTML-escape evidence]
    Escape --> Block[Return memory_evidence block marked untrusted]
```

Conversation retrieval accepts personal and episodic kinds only. Task runs are
stored separately and cannot occupy conversation retrieval candidate slots.

## Memory Extraction

```mermaid
flowchart TD
    Messages[Recent conversation messages] --> Claim[Claim unique extraction run]
    Claim --> Extractor[Request schema-constrained candidates]
    Extractor --> Validate[Validate kind, confidence, and user evidence quote]
    Validate --> Normalize[Normalize and hash content]
    Normalize --> Supersede[Supersede prior keyed profile value]
    Supersede --> Store[Transactionally store record]
    Store --> Embed[Store versioned embedding or pending failure state]
    Embed --> Complete[Mark extraction run complete]
```

Stable conversation and message IDs make extraction replay-safe. Extracted
claims must include evidence that appears in a user message.

## Task Learning

```mermaid
flowchart TD
    Run[Task execution run] --> Pending[Store one row by run ID]
    Pending --> Confirm{Confirmed outcome?}
    Confirm -->|No| Wait[Keep pending without a lesson]
    Confirm -->|Yes| Aggregate[Aggregate evidence by task fingerprint]
    Aggregate --> Lesson[Upsert one procedural lesson]
    Lesson --> Guidance[Retrieve task guidance separately]
```

`awaiting_confirmation` is not success. A final lesson is derived only from a
confirmed terminal outcome, and late pending updates cannot downgrade it.

## Storage and Security Boundaries

- `src/servers/memory_api.py` authenticates every memory route.
- `src/memory/sqlite_repository.py` owns SQLite transactions, WAL mode, schema,
  namespace constraints, FTS, embeddings, task runs, and task lessons.
- `src/memory/retrieval_service.py` owns candidate selection and ranking.
- `src/memory/context_builder.py` owns prompt-safe evidence formatting.
- `src/memory/extraction_service.py` owns extraction claims and validation.
- `src/memory/task_learning_service.py` owns confirmed run learning.
- `src/memory/memory_manager.py` is a compatibility facade, not a storage layer.

Short-lived tool notes use `manageWorkingContext`. The legacy
`manageMemoryCache` tool name and `{{MEMORY_CACHE}}` placeholder remain aliases
only for compatibility; neither writes durable long-term memory.
