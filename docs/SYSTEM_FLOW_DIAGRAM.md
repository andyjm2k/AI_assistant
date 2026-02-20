# CATBot System Flow: Prompt to Response (Updated)

## Overview
This document diagrams the complete flow from user prompt through to system response, including all intermediate steps, tool calls, memory operations, and the new automatic memory search feature for opinion/knowledge questions.

**Last Updated**: Includes automatic memory search for opinion/knowledge questions (when not in Philosopher mode)

---

## Main Flow: Frontend Chat Interface (Updated)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          1. USER INPUT (Frontend)                           │
│                         index-dev.html (Browser)                            │
│  • User types prompt in input field                                          │
│  • Clipboard content may be attached (images/text)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   2. QUESTION TYPE DETECTION (NEW)                          │
│  • Check if NOT in Philosopher mode (philosopherModeActive === false)      │
│  • Analyze prompt with isOpinionOrKnowledgeQuestion():                     │
│    - Opinion/Knowledge patterns:                                            │
│      * "what do you think about X?"                                         │
│      * "what's your opinion on Y?"                                          │
│      * "what do you know about Z?"                                          │
│      * "what are your thoughts on..."                                       │
│    - Action patterns (skip memory search):                                  │
│      * "search for information on X"                                       │
│      * "how much does Y cost?"                                              │
│      * "what's the weather in Z?"                                           │
│      * "read file", "calculate", "navigate", etc.                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
        ┌───────────────────────┐      ┌──────────────────────────────┐
        │  OPINION/KNOWLEDGE    │      │      ACTION QUESTION         │
        │      QUESTION         │      │   (Skip Memory Search)       │
        └───────────────────────┘      └──────────────────────────────┘
                    │                               │
                    ▼                               │
┌─────────────────────────────────────────────────────────────────────────────┐
│                   3. AUTOMATIC MEMORY SEARCH (NEW)                          │
│  • Extract topic from question (e.g., "X" from "what do you think about X?")│
│  • Call autoSearchMemoriesForQuestion(promptText):                         │
│    - POST /v1/memory/search to proxy server                                 │
│    - Query: extracted topic or full prompt                                   │
│    - Limit: 5 memories                                                       │
│    - Similarity threshold: 0.5                                               │
│  • If memories found:                                                        │
│    - Format memory context string                                            │
│    - Return memory context                                                   │
│  • If no memories or error:                                                 │
│    - Return null (fail silently, don't block)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   4. MESSAGE PREPARATION (Updated)                          │
│  • Build system prompt:                                                      │
│    - Start with base system prompt                                          │
│    - If memory context exists:                                               │
│      * Append: "\n\nRelevant context from previous conversations:\n"         │
│      * Append: memory context (formatted memories)                          │
│      * Append: "\n\nUse this context to provide more personalized..."       │
│  • Build messages array:                                                    │
│    - [system (with memory context if applicable), ...history, user_message]  │
│  • Add clipboard content if present (images/text)                          │
│  • Include tools definitions (searchMemories, runBrowserAgent, etc.)        │
│  • Set model, temperature, max_tokens, tool_choice                          │
│  • Add user message to chatHistory                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   5. API REQUEST (Frontend → LLM)                           │
│  POST /v1/chat/completions                                                  │
│  {                                                                          │
│    model: "model-name",                                                     │
│    messages: [                                                              │
│      { role: "system", content: "...with memory context if applicable..." },│
│      ...history,                                                            │
│      { role: "user", content: promptText }                                 │
│    ],                                                                       │
│    tools: [...],                                                            │
│    tool_choice: "auto",                                                     │
│    temperature: 0.7,                                                        │
│    max_tokens: 4096                                                          │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   6. LLM PROCESSING (Language Model)                        │
│  • Processes messages with context (including memory context if provided)   │
│  • Decides: direct response OR tool calls                                   │
│  • Returns response with choices[0].message                                 │
│  • Note: For opinion/knowledge questions, LLM now has memory context        │
│    available in system prompt, so it can reference previous conversations    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
        ┌───────────────────────┐      ┌──────────────────────────────┐
        │  7a. DIRECT RESPONSE  │      │  7b. TOOL CALLS DETECTED     │
        │  (No tool_calls)      │      │  (message.tool_calls exists) │
        └───────────────────────┘      └──────────────────────────────┘
                    │                               │
                    │                               ▼
                    │              ┌────────────────────────────────────┐
                    │              │  8. TOOL EXECUTION LOOP            │
                    │              │  For each tool_call:                │
                    │              │  • Parse tool name & arguments      │
                    │              │  • Route to handler:                │
                    │              │    - searchMemories → proxy API     │
                    │              │    - runBrowserAgent → proxy API    │
                    │              │    - readFile/writeFile → proxy API │
                    │              │    - calculate → local JS           │
                    │              │    - manageTodoList → local JS     │
                    │              │  • Execute tool                    │
                    │              │  • Format result                    │
                    │              │  • Add to messages as 'tool' role   │
                    │              └────────────────────────────────────┘
                    │                               │
                    │                               ▼
                    │              ┌────────────────────────────────────┐
                    │              │  9. FOLLOW-UP LLM REQUEST         │
                    │              │  • Add assistant tool_calls msg    │
                    │              │  • Add all tool results            │
                    │              │  • Send to LLM again               │
                    │              │  • Get final response               │
                    │              └────────────────────────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   10. RESPONSE PROCESSING (Frontend)                       │
│  • Strip `<think>` tags if present                                           │
│  • Add assistant message to chatHistory                                     │
│  • Display in responseOutput                                                │
│  • Update messageHistory UI                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   11. POST-RESPONSE ACTIONS (Frontend)                     │
│  • Extract memories (async, non-blocking):                                 │
│    - Get last 4 messages from chatHistory                                   │
│    - POST /v1/memory/extract to proxy server                                │
│    - Backend extracts & stores high-confidence memories                    │
│  • Text-to-Speech: textToSpeech(finalContent)                              │
│  • VRM Animation: Detect emotion keywords, trigger poses                    │
│  • Clear clipboard if used                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Question Type Detection Flow (Detailed)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    QUESTION TYPE DETECTION                                  │
│                    isOpinionOrKnowledgeQuestion(prompt)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   1. CHECK ACTION PATTERNS (Priority)                       │
│  Patterns that indicate action-oriented questions:                          │
│  • "search for information on X"                                           │
│  • "how much does Y cost?"                                                  │
│  • "what's the weather in Z?"                                              │
│  • "read file", "calculate", "navigate", "create", etc.                   │
│  → If match: return FALSE (skip memory search)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   2. CHECK OPINION/KNOWLEDGE PATTERNS                      │
│  Patterns that indicate opinion/knowledge questions:                       │
│  • "what do you think about X?"                                            │
│  • "what's your opinion on Y?"                                              │
│  • "what do you know about Z?"                                             │
│  • "what are your thoughts on..."                                          │
│  • "how do you feel about..."                                              │
│  • "tell me what you think about..."                                       │
│  • "share your thoughts on..."                                              │
│  → If match: return TRUE (perform memory search)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   3. DEFAULT FALLBACK                                       │
│  • If starts with "what do you" or "what's your":                           │
│    → return TRUE (treat as opinion/knowledge)                                │
│  • Otherwise:                                                                │
│    → return FALSE (treat as action-oriented)                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Automatic Memory Search Flow (Detailed)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AUTO MEMORY SEARCH                                       │
│                    autoSearchMemoriesForQuestion(prompt)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   1. CHECK PHILOSOPHER MODE                                │
│  • If philosopherModeActive === true:                                        │
│    → return null (skip auto-search)                                        │
│  • If philosopherModeActive === false:                                      │
│    → continue to next step                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   2. CHECK QUESTION TYPE                                    │
│  • Call isOpinionOrKnowledgeQuestion(prompt)                               │
│  • If returns FALSE (action question):                                      │
│    → return null (skip auto-search)                                        │
│  • If returns TRUE (opinion/knowledge question):                            │
│    → continue to next step                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   3. EXTRACT TOPIC                                          │
│  • Try to extract main topic from question:                                │
│    - Pattern: /(think|opinion|view|know|...)\s+(about|of|on|regarding)\s+ │
│      (.+?)(?:\?|$)/i                                                        │
│    - Example: "what do you think about AI?" → "AI"                          │
│  • If extraction fails: use full prompt as search query                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   4. SEARCH MEMORIES                                        │
│  • Call handleSearchMemories({ query, limit: 5 })                           │
│  • POST /v1/memory/search to proxy server                                   │
│  • Parameters:                                                               │
│    - query: extracted topic or full prompt                                   │
│    - limit: 5                                                                │
│    - similarity_threshold: 0.5                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   5. PROCESS RESULTS                                        │
│  • If memories found:                                                        │
│    - Format: "Found X relevant memories:\n1. memory1\n2. memory2..."        │
│    - Return formatted memory context string                                 │
│  • If no memories found:                                                    │
│    - Return null                                                             │
│  • If error occurs:                                                          │
│    - Log warning to console                                                  │
│    - Return null (fail silently, don't block request)                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Alternative Flow: Telegram Bot Path

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TELEGRAM BOT FLOW (Backend)                              │
│                         proxy_server.py                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   1. RECEIVE MESSAGE                                        │
│  POST /v1/telegram/chat                                                     │
│  • Extract message_text                                                     │
│  • Get/initialize conversation history                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   2. MEMORY RETRIEVAL (Before Response)                     │
│  • Search relevant memories:                                                │
│    memory_manager.search_memories(query, limit=5, threshold=0.3)           │
│  • Build memory_context string                                              │
│  • Append to system_prompt                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   3. LLM REQUEST                                            │
│  • Build messages: [system+memory, ...history, user]                        │
│  • POST to OpenAI API (or compatible)                                       │
│  • Get response                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   4. MEMORY EXTRACTION (After Response)                     │
│  • If MEMORY_AUTO_EXTRACT=true:                                             │
│    - Get recent_messages (last 4)                                            │
│    - Call memory_manager.extract_memories_from_conversation()               │
│    - MemoryExtractor uses LLM to identify important info                    │
│    - Store only high-confidence memories                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   5. RETURN RESPONSE                                        │
│  • Add assistant reply to history                                           │
│  • Return TelegramChatResponse                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Memory System Flow (Detailed)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MEMORY EXTRACTION PROCESS                                 │
│                    memory/memory_extractor.py                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   1. FORMAT CONVERSATION                                    │
│  • Convert messages to readable text format                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   2. LLM EXTRACTION REQUEST                                 │
│  • Build extraction prompt focusing on:                                      │
│    - User preferences, habits, facts                                         │
│    - User needs, relationships                                              │
│  • Call LLM with extraction prompt                                          │
│  • Request JSON format: [{text, category, confidence}]                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   3. FILTER & STORE                                         │
│  • Parse LLM response (JSON array)                                          │
│  • Filter: Only keep confidence="high"                                      │
│  • For each memory:                                                         │
│    - Generate embedding (embeddings_client)                                 │
│    - Store in vector_store (numpy array)                                    │
│    - Save metadata (JSON)                                                   │
│  • Return memory_ids                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Tool Execution Examples

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TOOL ROUTING (Frontend)                                   │
│                    executeToolCall() function                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│ LOCAL TOOLS   │         │ PROXY API     │         │ PROXY API     │
│ (Frontend JS) │         │ (Backend)     │         │ (Backend)     │
├───────────────┤         ├───────────────┤         ├───────────────┤
│ • calculate   │         │ • searchMemories│       │ • runBrowserAgent│
│ • manageTodoList│       │ • storeMemory  │       │ • runDeepResearch│
│ • webSearch   │         │ • readFile     │       │ • scrapeWebsite │
│ • navigateToUrl│        │ • writeFile    │       │ • fetchNews     │
│               │         │ • listFiles    │       │                │
└───────────────┘         └───────────────┘         └───────────────┘
        │                           │                           │
        │                           │                           │
        └───────────────────────────┴───────────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │  Format Tool Result  │
                        │  Add to messages as   │
                        │  'tool' role          │
                        └───────────────────────┘
```

---

## Key Components Summary

### 1. Frontend (`index-dev.html`)
- **UI Input Handling**: Captures user prompts, clipboard content, images
- **Question Type Detection**: `isOpinionOrKnowledgeQuestion()` - Detects opinion/knowledge vs action questions
- **Automatic Memory Search**: `autoSearchMemoriesForQuestion()` - Searches memories for opinion/knowledge questions (when not in philosopher mode)
- **Message History Management**: Maintains conversation context
- **Tool Call Execution**: Routes and executes various tools
- **Response Display & TTS**: Shows responses and converts to speech
- **Memory Extraction Trigger**: Automatically extracts memories after responses

### 2. Backend (`proxy_server.py`)
- **Telegram Chat Endpoint**: `/v1/telegram/chat` for Telegram bot integration
- **Memory Management Endpoints**: Store, search, extract memories
- **MCP Server Integration**: Connects to Model Context Protocol servers
- **File Operations**: Read/write/list files in scratch directory
- **Browser Automation Proxy**: Routes browser agent and deep research requests

### 3. Memory System (`memory/`)
- **MemoryManager**: Orchestrates all memory operations
- **MemoryExtractor**: Uses LLM to extract important information from conversations
- **VectorStore**: Stores embeddings and metadata using numpy arrays
- **EmbeddingsClient**: Generates embeddings for semantic search

### 4. LLM Service
- **OpenAI-Compatible API**: Works with LM Studio, OpenAI, or other compatible services
- **Message Processing**: Handles conversation context and tool definitions
- **Response Generation**: Returns either direct responses or tool calls

---

## Key Configuration Settings

### Memory System
- **Auto-extraction**: Controlled by `MEMORY_AUTO_EXTRACT` environment variable (default: `true`)
- **Confidence Filter**: Only stores memories with `confidence="high"` (changed from `["high", "medium"]`)
- **Max Memories**: Default is `1` per extraction (changed from `3`)
- **Similarity Threshold**: `0.5` for automatic memory search, `0.3` for Telegram flow

### Automatic Memory Search (New Feature)
- **Trigger Condition**: Only for opinion/knowledge questions when NOT in Philosopher mode
- **Search Limit**: 5 memories per search
- **Similarity Threshold**: 0.5
- **Topic Extraction**: Automatically extracts topic from question for better search accuracy
- **Failure Handling**: Fails silently, doesn't block conversation flow

### Tool Execution
- **Tool Choice**: `"auto"` - LLM decides when to use tools
- **Max Tokens**: `4096` for responses
- **Temperature**: `0.7` for main responses, `0.3` for memory extraction
- **scrapeWebsite (scrape-with-retry)**: Both the Telegram and web (HTML) tool paths support an optional `urls` array. When multiple URLs are provided (e.g. from a prior webSearch), the backend or proxy tries each URL in order until one succeeds, so a single 404 or fetch failure does not block the flow. Single `url` continues to work as before.

### Philosopher Mode
- **Memory Search**: Disabled when `philosopherModeActive === true`
- **Auto-search**: Only runs when `philosopherModeActive === false`

---

## Example Flows

### Example 1: Opinion Question (With Memory Search)
```
User: "What do you think about artificial intelligence?"
  ↓
[Question Type Detection]
  → Detected as opinion/knowledge question
  ↓
[Automatic Memory Search]
  → Extracted topic: "artificial intelligence"
  → Searched memories: Found 3 relevant memories
  → Memory context added to system prompt
  ↓
[LLM Request]
  → System prompt includes: "Relevant context from previous conversations:
     1. We discussed AI ethics and bias (similarity: 85.2%)
     2. You mentioned concerns about AI job displacement (similarity: 72.1%)
     3. We talked about AI in healthcare applications (similarity: 68.5%)"
  ↓
[LLM Response]
  → Response references previous conversations
  → Provides personalized answer based on memory context
```

### Example 2: Action Question (No Memory Search)
```
User: "Search for information on quantum computing"
  ↓
[Question Type Detection]
  → Detected as action question (contains "search for")
  ↓
[Skip Memory Search]
  → No automatic memory search performed
  ↓
[LLM Request]
  → Standard system prompt (no memory context)
  ↓
[LLM Response with Tool Call]
  → Calls webSearch tool directly
  → Returns search results
```

### Example 3: Philosopher Mode (No Auto-Search)
```
User: "What do you think about consciousness?"
  ↓
[Check Philosopher Mode]
  → philosopherModeActive === true
  ↓
[Skip Auto-Search]
  → No automatic memory search (philosopher mode active)
  ↓
[LLM Request]
  → Standard system prompt (no memory context)
  → Philosopher mode handles contemplation internally
```

---

## File Locations

- **Frontend**: `index-dev.html`
  - Lines 5890-5943: `isOpinionOrKnowledgeQuestion()` function
  - Lines 5945-5979: `autoSearchMemoriesForQuestion()` function
  - Lines 7171-7179: Automatic memory search integration in message preparation
  - Lines 7000-7500: Main chat flow
  - Lines 5600-5800: Tool execution handlers

- **Backend**: `proxy_server.py`
  - Lines 1420-1575: Telegram chat endpoint
  - Lines 1696-1736: Memory extraction endpoint

- **Memory System**: 
  - `memory/memory_manager.py` (lines 197-235 for extraction)
  - `memory/memory_extractor.py` (lines 64-141 for LLM-based extraction)
  - `memory/vector_store.py` (embedding storage)
  - `memory/embeddings_client.py` (embedding generation)

---

## Notes

1. **Automatic Memory Search**: The new feature automatically searches memories for opinion/knowledge questions before sending to the LLM, providing context from previous conversations.

2. **Question Type Detection**: Uses pattern matching to distinguish between opinion/knowledge questions and action-oriented questions. Action patterns take priority.

3. **Philosopher Mode Override**: When Philosopher mode is active, automatic memory search is disabled to allow the philosopher mode to handle contemplation independently.

4. **Tool Call Loop**: The system supports multiple rounds of tool calls. After each tool execution, the LLM can make another decision to call more tools or provide a final response.

5. **Memory Extraction**: Happens asynchronously after the response is displayed, so it doesn't block the user experience.

6. **Error Handling**: Tool execution errors and memory search errors are caught and handled gracefully, allowing the conversation to continue.

7. **Conversation History**: Both frontend and Telegram backend maintain separate conversation histories per user/conversation ID.

8. **VRM Integration**: The frontend includes emotion detection and triggers 3D avatar animations based on response content.

---

## Flow Comparison: Before vs After Update

### Before Update:
- Memory search was only available as a tool that the LLM could choose to call
- No automatic memory context injection
- LLM had to explicitly decide to search memories

### After Update:
- Automatic memory search for opinion/knowledge questions
- Memory context automatically injected into system prompt
- LLM receives relevant memories without needing to call the tool
- Action questions skip memory search and go directly to tool execution
- Philosopher mode preserves original behavior (no auto-search)

