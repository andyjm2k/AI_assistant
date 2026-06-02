# CATBot — Central Agentic Tools Bot
<p align="center">
<img src="CATBot_logo.png" alt="CATBot Logo" width="200" height="200" align="center">
</p>
<p align="center">
  <strong>Your comprehensive AI assistant with browser automation, speech, and 3D avatars</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="MIT License"></a>
  <a href="https://github.com/microsoft/autogen"><img src="https://img.shields.io/badge/AutoGen-Microsoft-blue?style=for-the-badge" alt="AutoGen"></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-Protocol-green?style=for-the-badge" alt="MCP"></a>
</p>

**CATBot** is a _comprehensive AI assistant system_ you run on your own devices. It features browser automation, speech-to-text, text-to-speech, multi-agent collaboration, and 3D avatar integration with VRM/Live2D support. The system provides a unified interface for interacting with AI models through multiple channels and capabilities.

If you want a personal, feature-rich assistant that combines conversational AI, browser automation, and immersive 3D avatars, this is it.

[Installation Guide](#installation-guide) · [Automated install](#automated-install) · [Configuration](#configuration) · [Usage](#usage) · [Troubleshooting](#troubleshooting)

## Quick Start

Runtime: **Node.js ≥16** and **Python ≥3.11**.

```bash
# Clone the repository
git clone https://github.com/andyjm2k/CATBot.git
cd CATBot

# Install Node.js dependencies
npm ci

# Create Python virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install Python dependencies (single source: requirements.txt)
pip install -r requirements.txt

# Install Playwright browsers
playwright install

# Clone the CATBot MCP Browser-Use fork
git clone https://github.com/andyjm2k/mcp-browser-use.git mcp-browser-use

# Set up MCP Browser-Use
cd mcp-browser-use
pip install uv
uv sync --frozen
uv run playwright install
cd ..

# Configure environment variables
cp .env.example .env
# Edit .env with your provider/API settings and any optional feature sections you need

# Start all services (run from project root)
python scripts/start_all.py
```

Full setup guide: [Installation Guide](#installation-guide). For one-command setup on a new machine, see [Automated install](#automated-install).

## Automated install

On a **new machine** you can run the automated installer instead of following the Quick Start steps manually.

**Prerequisites (install these first if missing):** Python 3.11+, Node.js 16+, Git, and [uv](https://github.com/astral-sh/uv) (e.g. `pip install uv`).  
For embedded Kitten TTS, install `espeak-ng` on the host and ensure `espeak-ng` is on `PATH`.

- **Windows:** From project root run:
  ```powershell
  .\install.ps1
  ```
  or double-click `install.bat`. The installer now uses `npm ci` when the lockfile is present, prepares the forked `mcp-browser-use` checkout with `uv sync --frozen` when `uv.lock` exists, runs a configuration wizard, and then verifies the install. The wizard writes both the MCP-prefixed provider vars and the standard provider aliases still used by older CATBot modules. Then start with `start.bat` or `python scripts/start_all.py`.
- **Linux/macOS:** From project root run:
  ```bash
  ./install.sh
  ```
  Then edit `.env` and start services (see [INSTALL.md](INSTALL.md)).

See [INSTALL.md](INSTALL.md) for the current deploy flow and [docs/BROWSER_USE_INSTALL_GUIDE.md](docs/BROWSER_USE_INSTALL_GUIDE.md) for the forked browser-use setup.

## Highlights

- **[Multi-Agent Collaboration](https://github.com/microsoft/autogen)** — Microsoft AutoGen integration for team-based AI interactions
- **[Browser Automation](https://github.com/browser-use/browser-use)** — Autonomous browser agent powered by browser-use and Playwright
- **[Speech Capabilities](https://openai.com/)** — Speech-to-text (Whisper) and text-to-speech (OpenAI-compatible) integration
- **[3D Avatar Support](https://vroid.com/studio)** — VRM and Live2D avatar integration with emotive animations
- **[Model Context Protocol](https://modelcontextprotocol.io/)** — MCP integration for extensible tooling
- **[Skill Framework](docs/SKILL_FRAMEWORK.md)** — Manifest-driven skills, including a working `image_generation.generate_image` example (OpenRouter Seedream 4.5)
- **[File Operations](proxy_server.py)** — Read/write support for txt, docx, xlsx, pdf, and images
- **[Web Search](proxy_server.py)** — Brave Search API with DuckDuckGo fallback
- **[Weather Information (Open-Meteo)](src/servers/proxy_server.py)** — Secure weather tool for web + Telegram using api.open-meteo.com data
- **[Codex CLI Tool](src/servers/proxy_server.py)** — Non-interactive Codex CLI runner for CATBot code changes and new tool capabilities
- **[Telegram Integration](telegram_bot.py)** — Bot interface for Telegram messaging
- **[Memory System](memory/)** — Vector-based memory storage and retrieval for conversation context

## Prerequisites

### System Requirements

- **Node.js** (v16 or higher) — [Download](https://nodejs.org/)
- **Python** (v3.11 or higher) — [Download](https://www.python.org/downloads/)
- **Chrome/Chromium Browser** — Required for browser automation

### API Keys and Endpoints

1. **OpenAI-Compatible LLM Endpoint**
   - For text generation and chat functionality
   - Environment variable: `OPENAI_API_KEY` or `OPENAI_API_BASE`

2. **OpenAI-Compatible TTS (Text-to-Speech) Endpoint**
   - For converting text to speech
   - Environment variable: `OPENAI_API_KEY` (shared with LLM) or separate TTS endpoint

3. **OpenAI-Compatible Whisper Endpoint (STT)**
   - For converting speech to text
   - Default: `http://localhost:8001/v1/audio/transcriptions`
   - Environment variable: `WHISPER_ENDPOINT`

4. **Brave Search API Key** (Required for web search)
   - Get your key: https://brave.com/search/api/
   - Environment variable: `BRAVE_API_KEY`
   - Note: Falls back to DuckDuckGo if not configured

5. **News API Key** (Optional)
   - Get your key: https://newsapi.org/
   - Can be configured in the application settings UI

6. **Open-Meteo Weather API Access** (No key required)
   - Forecast data source: https://api.open-meteo.com/v1/forecast
   - Geocoding data source: https://geocoding-api.open-meteo.com/v1/search
   - Environment variable: `OPEN_METEO_FORECAST_BASE_URL` (optional override)
   - Environment variable: `OPEN_METEO_GEOCODING_BASE_URL` (optional override)
   - Environment variable: `OPEN_METEO_TIMEOUT_SECONDS` (optional request timeout)
   - Environment variable: `OPEN_METEO_TRUST_ENV` (`false` by default; set `true` only when you intentionally need HTTP(S)_PROXY)

7. **Telegram Bot Token** (Optional)
   - Create a bot: https://core.telegram.org/bots#botfather
   - Environment variable: `TELEGRAM_BOT_TOKEN`

## Installation Guide

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd AI_assistant
```

### Step 2: Install Node.js Dependencies

```bash
npm install
```

### Step 3: Install Python Dependencies

#### Option A: Using pip (Recommended)

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install all Python dependencies from requirements.txt
pip install -r requirements.txt

# Note: requirements include KittenTTS from a GitHub wheel URL.
# If embedded TTS is enabled, ensure espeak-ng is installed on the host.

# Install Playwright browsers
playwright install
```

#### Option B: Using UV (For the `mcp-browser-use` checkout)

```bash
# Install UV package manager
pip install uv
# OR
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Navigate to mcp-browser-use directory
cd mcp-browser-use

# Sync dependencies using uv
uv sync

# Install Playwright browsers for uv environment
uv run playwright install

# Return to project root
cd ..
```

#### Getting mcp-browser-use working in a new deployment (Windows, venv + pip)

For a clean install of the MCP browser-use server in a new deployment (e.g. fresh clone or new machine), use a dedicated virtual environment and editable install:

```batch
deactivate
cd C:\Users\pc\AI_assistant\mcp-browser-use
rmdir /s /q .venv
py -m venv .venv
.venv\Scripts\activate
py -m pip install -U pip
pip install -e .
```

Replace `C:\Users\pc\AI_assistant\mcp-browser-use` with your actual path to the `mcp-browser-use` directory. Then install Playwright browsers: `playwright install` (or `py -m playwright install`). Return to the project root when done.

**Resources:**
- [UV Package Manager](https://github.com/astral-sh/uv)
- [CATBot MCP Browser-Use Fork](https://github.com/andyjm2k/mcp-browser-use)

### Step 4: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Copy example configuration
cp .env.example .env
# Windows:
copy .env.example .env
```

Edit `.env` with your configuration:

```env
# OpenAI-Compatible LLM Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# TTS Configuration (OpenAI-Compatible)
# Use endpoint base URL (proxy app appends /v1/audio/speech internally)
TTS_ENDPOINT=https://api.openai.com
TTS_MODEL=tts-1
TTS_VOICE=alloy

# Optional: Embedded Kitten / Pocket TTS served by proxy_server itself
# EMBEDDED_KITTEN_TTS_ENABLED=true
# EMBEDDED_KITTEN_MODEL=KittenML/kitten-tts-nano-0.2
# EMBEDDED_KITTEN_DEFAULT_VOICE=expr-voice-2-f
# EMBEDDED_KITTEN_SAMPLE_RATE=24000
# EMBEDDED_KITTEN_STREAM_CHUNK_BYTES=4096
# EMBEDDED_KITTEN_MAX_INPUT_CHARS=220
# EMBEDDED_KITTEN_CHUNK_SILENCE_MS=80
# EMBEDDED_POCKET_TTS_ENABLED=true
# EMBEDDED_POCKET_MODEL=pocket-tts-realtime
# EMBEDDED_POCKET_DEFAULT_VOICE=alba
# EMBEDDED_POCKET_VOICES=alba,marius,javert,jean,fantine,cosette,eponine,azelma
# EMBEDDED_POCKET_STREAM_CHUNK_BYTES=4096
# TTS_PROXY_TIMEOUT_SECONDS=180
# Then set TTS endpoint to this proxy:
# TTS_ENDPOINT=http://localhost:8002
# Use TTS_MODEL=kitten-tts-mini-0.8 for Kitten or TTS_MODEL=pocket-tts-realtime for Pocket.

# STT Configuration (Whisper-Compatible)
WHISPER_ENDPOINT=http://localhost:8001/v1/audio/transcriptions

# Brave Search API
BRAVE_API_KEY=your_brave_api_key_here

# News API
NEWS_API_KEY=your_news_api_key_here

# Telegram Bot (Optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_ADMIN_IDS=123456789,987654321
TELEGRAM_ALLOW_ALL=false

# MCP Browser-Use Configuration
MCP_LLM_PROVIDER=google
MCP_LLM_MODEL_NAME=gemini-2.0-flash-exp
GOOGLE_API_KEY=your_google_api_key_here
MCP_BROWSER_HEADLESS=true
MCP_RESEARCH_TOOL_SAVE_DIR=./research_output

# AutoGen Configuration
AUTOGEN_CONFIG_PATH=./config/team-config.json
```

### Step 5: Set Up Avatar Models

#### VRM Models (VRoid)

1. Download or create VRM models from VRoid Studio
2. Place `.vrm` files in `model_avatar/<model_name>/` directories

**Resources:**
- [VRoid Studio](https://vroid.com/studio)
- [VRM Specification](https://github.com/vrm-c/vrm-specification)

#### VMA Animation Files

1. Download or create VMA (VRM Animation) files
2. Place `.vrma` files alongside VRM models

**Resources:**
- [VRM Animation](https://github.com/vrm-c/vrm-specification/tree/master/specification/VRMC_vrm_animation-1.0)

#### Live2D Models (Alternative)

1. Download Live2D Cubism models
2. Place model files in appropriate directories

**Resources:**
- [Live2D Cubism](https://www.live2d.com/)
- [Live2D SDK](https://www.live2d.com/sdk/)

### Step 6: Create Required Directories

```bash
# Create scratch directory for file operations
mkdir scratch

# Create research output directory
mkdir research_output

# Create directories for optional features
mkdir -p recordings      # If using browser recording
mkdir -p agent_history   # If saving agent history
mkdir -p traces          # If using Playwright tracing
```

### Step 7: Verify Installation

```bash
# Test Node.js dependencies
node -e "console.log('Node.js OK')"
npm list --depth=0

# Test Python dependencies
python -c "import fastapi; print('FastAPI OK')"
python -c "import autogen_agentchat; print('AutoGen OK')"
python -c "import mcp; print('MCP OK')"
python -c "import browser_use; print('Browser-Use OK')"

# Test Playwright
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"

# Test MCP Browser-Use server
cd mcp-browser-use
uv run mcp-server-browser-use --help
cd ..
```

## Configuration

### Environment Variables

Key environment variables (see `.env.example` for complete list):

#### LLM Configuration
- `OPENAI_API_KEY`: OpenAI API key
- `OPENAI_API_BASE`: OpenAI-compatible endpoint base URL
- `OPENAI_MODEL`: Model name to use
- `GOOGLE_API_KEY`: Google AI API key (for Gemini)
- `ANTHROPIC_API_KEY`: Anthropic API key (for Claude)

#### MCP Browser-Use Configuration
- `MCP_LLM_PROVIDER`: LLM provider (openai, google, anthropic, azure_openai, deepseek, mistral, ollama, openrouter, alibaba, moonshot, unbound_ai)
- `MCP_LLM_MODEL_NAME`: Specific model name (e.g., gemini-2.0-flash-exp, gpt-4o-mini)
- `MCP_BROWSER_HEADLESS`: Run browser in headless mode (true/false)
- `MCP_RESEARCH_TOOL_SAVE_DIR`: Directory for research outputs (required)

#### Service Endpoints
- `WHISPER_ENDPOINT`: Whisper STT service endpoint
- `TTS_ENDPOINT`: TTS service endpoint base URL
- `TTS_MODEL`: Default TTS model for the web UI (optional; also used as fallback if TTS voice list fetch fails)
- `TTS_VOICE`: Default TTS voice for the web UI (optional; also used as fallback if TTS voice list fetch fails)
- `EMBEDDED_KITTEN_TTS_ENABLED`: Enable embedded `/v1/audio/speech` + `/v1/audio/voices` in proxy_server
- `EMBEDDED_KITTEN_MODEL`: Embedded Kitten model id
- `EMBEDDED_KITTEN_DEFAULT_VOICE`: Default embedded Kitten voice id
- `EMBEDDED_KITTEN_VOICES`: Comma-separated embedded voice ids exposed to UI
- `EMBEDDED_KITTEN_SAMPLE_RATE`: Embedded output sample rate (default 24000)
- `EMBEDDED_KITTEN_STREAM_CHUNK_BYTES`: Embedded stream chunk size in bytes
- `EMBEDDED_KITTEN_MAX_INPUT_CHARS`: Max text chars per generation chunk for embedded Kitten streaming
- `EMBEDDED_KITTEN_CHUNK_SILENCE_MS`: Silence inserted between generated chunks (milliseconds)
- `EMBEDDED_POCKET_TTS_ENABLED`: Enable embedded Kyutai Pocket TTS on the same `/v1/audio/speech` + `/v1/audio/voices` endpoints
- `EMBEDDED_POCKET_MODEL`: Logical Pocket model selector exposed to clients (`pocket-tts-realtime` by default)
- `EMBEDDED_POCKET_DEFAULT_VOICE`: Default embedded Pocket voice id
- `EMBEDDED_POCKET_VOICES`: Comma-separated Pocket voice ids exposed to UI/Telegram
- `EMBEDDED_POCKET_STREAM_CHUNK_BYTES`: Embedded Pocket PCM/WAV stream chunk size in bytes
- `TTS_PROXY_TIMEOUT_SECONDS`: Proxy timeout for forwarded TTS requests (seconds)
- `BRAVE_API_KEY`: Brave Search API key
- `NEWS_API_KEY`: News API key
 
#### Context Window Controls
- `MAX_TOKEN_LIMIT`: Max total tokens (input + output) per LLM request. The proxy preflights, summarizes, and retries when exceeded.
- `TOKEN_ESTIMATE_CHARS_PER_TOKEN`: Heuristic for token estimation when no tokenizer is available (default 4).
- `LIST_FILES_TOOL_MAX_ENTRIES`: Max number of rows returned by LLM-facing file-list tools (`filesystem.list_files`, plus Telegram `listFiles`, default 60). Supports optional `path` and `recursive` arguments for subdirectory listing.
 
#### Large Payload Fallback
- `LARGE_PAYLOAD_MODEL`: Optional model to retry with when context window exhaustion occurs.
- `LARGE_PAYLOAD_ENDPOINT`: Optional endpoint for the large payload model (OpenAI-compatible).

#### Codex CLI Tool (optional)
- `CODEX_ENABLED`: Enable the Codex CLI tool endpoint (default true)
- `CODEX_CLI_PATH`: Path to the `codex` executable (default `codex` on PATH)
- `CODEX_SANDBOX_MODE`: Sandbox policy (`read-only`, `workspace-write`, `danger-full-access`)
- `CODEX_APPROVAL_POLICY`: Approval policy (`untrusted`, `on-request`, `on-failure`, `never`)
- `CODEX_ENABLE_SEARCH`: Enable Codex built-in web search (default true)
- `CODEX_TIMEOUT_SECONDS`: Default timeout in seconds (default 1800)

#### Telegram Bot Configuration

**Required (bot process):**
- `TELEGRAM_BOT_TOKEN`: Telegram bot token from BotFather (required for the bot)
- `TELEGRAM_ADMIN_IDS`: Comma-separated list of allowed Telegram user IDs (numeric only), or use `TELEGRAM_ALLOW_ALL=true` to allow all users

**Required (proxy process, for chat):**
- `OPENAI_API_KEY` or `MCP_LLM_OPENAI_API_KEY`: One of these must be set on the proxy so Telegram chat can call the LLM (same keys as web UI)

**Optional (bot):**
- `TELEGRAM_ALLOW_ALL`: Set to `"true"` to allow all users (default: false)
- `TELEGRAM_BACKEND_URL`: Base URL of the CATBot proxy server (default: http://localhost:8002)
- `TELEGRAM_CHAT_ENDPOINT`: Chat endpoint path (default: /v1/telegram/chat)
- `TELEGRAM_CHAT_MODEL`: Model override for Telegram (default from OPENAI_MODEL or gpt-4o-mini)
- `TELEGRAM_BACKEND_VERIFY_SSL`: Set to `"false"` to skip SSL verification for backend (e.g. self-signed certs)
- `TELEGRAM_VOICE_NOTE_OPUS_BITRATE`: Opus bitrate for Telegram voice-note conversion (default: `32k`)
- If `TELEGRAM_VOICE_OUT=true`, the bot attempts to transcode TTS output to Telegram-friendly `OGG/Opus` voice notes using `ffmpeg` when needed.

**Proxy auth:**
- `TELEGRAM_SECRET`: Shared secret for bot-to-proxy auth. Set the same value on both bot and proxy when the proxy is reachable beyond loopback.
- `TELEGRAM_MAX_ATTACHMENT_BYTES`: Bot-side document/photo size cap before downloads (default: `FILE_OPS_MAX_SIZE_BYTES` or `10485760`).
- `TELEGRAM_SYSTEM_PROMPT`: System prompt override; overridden by `config/catbot_system_prompt.txt` when that file exists
- `TELEGRAM_HISTORY_LIMIT`, `TELEGRAM_CHAT_TIMEOUT`: Conversation tuning (defaults 12, 30)
- `TELEGRAM_CHAT_TIMEOUT_HARD_CAP`, `TELEGRAM_TOOL_FOLLOWUP_TIMEOUT`, `TELEGRAM_BOT_CHAT_TIMEOUT_HARD_CAP`: Timeout safety limits to prevent hangs while still allowing long-running tools (defaults 120, 45, 10800)
- `TELEGRAM_OPENAI_BASE_URL`, `TELEGRAM_OPENAI_CHAT_PATH`: Override LLM endpoint (e.g. Azure/Groq)

**Telegram tools (optional, proxy only):**
- `TELEGRAM_TOOLS_ENABLED`: Set to `"true"` to enable tools in Telegram (search, files, todo, memory, workflows, etc.). When enabled, the proxy uses `config/catbot_system_prompt_with_tools.txt` and runs a tool loop.
- `TELEGRAM_TOOLS_MAX_ITERATIONS`: Max tool-loop iterations per message (default: 5)
- `LIST_FILES_TOOL_MAX_ENTRIES`: Caps `listFiles` output rows sent back to the model (default: 60) so large scratch directories do not bloat chat context.
- When tools are enabled, the following are used by specific tools if set (same as web UI): `BRAVE_API_KEY` (webSearch; else DuckDuckGo), `NEWS_API_KEY` (fetchNews), `GOOGLE_DRIVE_*` (uploadToGoogleDrive), memory/vector-store settings for store/search/list/delete memories. File tools use the proxy scratch directory; runWorkflow uses AutoGen/team-config.
- `listFiles` accepts optional `path` (subdirectory under `scratch/`) and `recursive` (default `false`) for scoped listings.
- Security note: `sendTelegramFile` only sends files from the proxy `scratch/` directory and still enforces path + size checks. Subdirectory paths like `images/generated/file.png` are supported.

**Todo list (persistent, per user):** The todo list is stored in backend file storage (`todo_data/` by default, or `TODO_DATA_PATH`) per authenticated user. The web UI requires sign-in to load/save todo; tools (manageTodoList, executeTodoTask) call the proxy REST API. Telegram uses the same backend; optional **Telegram account linking** via `config/telegram_user_links.json` (mapping Telegram user ID or conversation ID to app username) lets the same todo list be shared between browser and Telegram. Without linking, Telegram uses a persistent per-chat list keyed by conversation ID.

**Task Execution:** Users can say "execute task N" or "execute task N. &lt;prompt&gt;" to run a bounded LLM+tools loop on a todo item. The task is **never** auto-removed; a human must confirm completion (human-in-the-loop). Execution can pause for feedback. Configure `TASK_EXECUTION_MAX_ITERATIONS` (default 20) in `.env`. Available from both the HTML page and Telegram when tools are enabled.

**System prompt / rules:** To use the same system context and rules as the web UI, put your prompt in `config/catbot_system_prompt.txt`. The proxy uses this file for Telegram when it exists (overrides `TELEGRAM_SYSTEM_PROMPT` env). A default file is included. See "Telegram tools" below for available tools and limitations when `TELEGRAM_TOOLS_ENABLED=true`.

See `config/telegram_env_example.txt` for the full list and examples.

### Team Configuration (AutoGen)

The AutoGen team source of truth is now [`src/autogen/team_builder.py`](src/autogen/team_builder.py). The proxy loads that Python-defined team directly at runtime.

`config/team-config.json` is still kept for tools such as AutoGen Studio, but it is a generated export, not the primary definition. Refresh it with:

```bash
python scripts/export_autogen_team_config.py
```

`scripts/start_all.py` runs that export automatically before launching AutoGen Studio.

Security defaults:

- The install wizard generates a real `JWT_SECRET`. If you replace it later, rotate any previously issued JWTs.
- Public signup is disabled after first-user bootstrap unless `AUTH_ALLOW_PUBLIC_SIGNUP=true` or `AUTH_SIGNUP_INVITE_CODE` is configured.
- CORS allows local/private origins by default. Set `CATBOT_CORS_ALLOWED_ORIGINS` for deployed clients instead of `CATBOT_CORS_ALLOW_ALL=true`.
- Server-side fetch/proxy requests block private and loopback targets unless the endpoint is explicitly trusted or `CATBOT_OUTBOUND_ALLOW_PRIVATE=true`.
- `AUTOGEN_REQUIRE_AUTH=true` keeps `POST /v1/proxy/autogen` behind authentication by default.
- Browser users should call it with their normal JWT. Internal AutoGen/browser-bridge callers can use `CATBOT_AGENT_SECRET` (or the legacy `AUTOGEN_TEAM_SECRET`) via `X-Agent-Secret`.
- `AUTOGEN_ENABLE_CODE_EXECUTION=false` leaves the Docker-backed Python execution tool disabled even when the optional AutoGen Docker extras are installed.
- If you enable code execution later, ensure Docker is installed and running. The proxy server manages that executor lifecycle (start before first run, stop on reload or app shutdown).

**Resources:**
- [AutoGen Documentation](https://microsoft.github.io/autogen/)
- [AutoGen Studio](https://github.com/microsoft/autogen-studio)

## Usage

### Starting the Services

#### Option 1: Start All Services (Windows)

```bash
python scripts/start_all.py
```

This will start (each in a separate command window):
- HTTP server (port 8000)
- Whisper API server (port 8001)
- Proxy server (port 8002)
- AutoGen Studio (port 8084)
- MCP Browser-Use HTTP server (port 8383; run `uv run mcp-server-browser-use server` in mcp-browser-use directory)
- MCP Browser HTTP server (port 5001; localhost-only by default; internal Flask bridge to browser-use via `MCP_BROWSER_USE_HTTP_URL`, default http://127.0.0.1:8383/mcp)
- **Telegram bot** (polling; requires `python-telegram-bot` and `TELEGRAM_BOT_TOKEN` in `.env`)

#### Option 1b: Stop All Services (Windows)

```bash
python scripts/stop_all.py
```

#### Option 2: Start Services Individually

```bash
# Start HTTP server
python -m http.server 8000

# Start proxy server
python -m src.servers.proxy_server

# Export the current Python-defined team for Studio
python scripts/export_autogen_team_config.py

# Start AutoGen Studio (optional)
# The main CATBot venv intentionally does not install autogenstudio because current
# releases conflict with CATBot's pinned autogen-core 0.7.x stack.
# If you installed Studio separately, either put `autogenstudio` on PATH or set
# `AUTOGENSTUDIO_CMD` to its executable path before using scripts/start_all.py.
autogenstudio serve --team config/team-config.json --port 8084

# Start MCP Browser-Use HTTP server (required; stdio is deprecated).
# To use the same LLM provider/model as the Flask server, run the wrapper so it loads this project's .env:
python scripts/start_mcp_browser_use_http_server.py
# Or without wrapper (uses mcp-browser-use config/defaults): cd mcp-browser-use && uv run mcp-server-browser-use server

# Start MCP Browser HTTP server (Flask bridge for frontend)
python scripts/start_mcp_browser_server.py
```

### Accessing the Application

#### Local Access (localhost)

1. **Web Interface**: Open `index-dev.html` in your browser (served on port 8000)
2. **AutoGen Studio (optional)**: Navigate to `http://localhost:8084` if you installed Studio separately
3. **Proxy Server API**: `http://localhost:8002` (FastAPI with comprehensive endpoints)
4. **MCP Browser HTTP Server**: `http://localhost:5001` (internal Flask bridge; browser/deep-research routes require `X-Agent-Secret` and are normally accessed through the proxy)

#### Remote Network Access

The web server, proxy, and optional Studio can accept connections from devices on your local network. The MCP Browser HTTP bridge on port `5001` now binds to loopback by default and is intended as an internal proxy hop, not a public/LAN API.

To access from a remote device:

1. **Find your server's IP address:**
   - **Windows**: Run `ipconfig` in Command Prompt and look for "IPv4 Address" under your active network adapter
   - **Linux/Mac**: Run `ifconfig` or `ip addr` and look for your network interface IP
   - Example: `192.168.1.100`

2. **Access services from remote devices:**
   - **Web Interface**: `http://<server-ip>:8000` (e.g., `http://192.168.1.100:8000`)
   - **AutoGen Studio**: `http://<server-ip>:8084`
   - **Proxy Server API**: `http://<server-ip>:8002`

3. **Frontend auto-detection:**
   - The web interface automatically detects if it's being accessed remotely and adjusts API endpoints accordingly
   - You can also manually specify the server IP using a URL parameter: `http://<server-ip>:8000?server=<server-ip>`

4. **Firewall configuration:**
   - Ensure your firewall allows incoming connections on ports: 8000, 8002, and 8084
   - **Windows Firewall**: Add inbound rules for these ports
   - **Linux**: Use `ufw` or `iptables` to allow the ports

**Security Note**: If you intentionally expose the MCP Browser HTTP bridge, set a strong `MCP_BROWSER_SERVER_SECRET`, keep a strict `MCP_BROWSER_SERVER_ALLOWED_ORIGINS` allowlist, and override its host binding explicitly instead of relying on the default localhost-only mode.

### API Endpoints

#### Proxy Server Endpoints (Port 8002)

**Web Operations:**
- `GET /v1/proxy/fetch` - Fetch web content from a URL (query param)
- `POST /v1/proxy/fetch` - Fetch web content; body: `{"url": "..."}` or `{"urls": ["...", "..."]}`. Optional dynamic-page args: `render_js` (bool), `render_engine` (`auto|playwright|selenium`), `wait_for_selector` (CSS selector), `js_wait_ms` (extra wait). When `urls` is provided, the server tries each URL in order until one succeeds (scrape-with-retry), e.g. after a web search.
  - Note: JS rendering requires either Playwright (`playwright install chromium`) or Selenium with a working ChromeDriver.
- `GET /v1/proxy/search` - Perform web search (Brave Search or DuckDuckGo fallback)
- `GET /v1/proxy/weather` - Weather info (Open-Meteo: current, forecast, summary; supports memory fallback)

**AI & Chat:**
- `POST /v1/proxy/autogen` - AutoGen team-based chat endpoint (auth required by default; accepts JWT or internal agent secret)
- `POST /v1/proxy/codex` - Codex CLI non-interactive runner (auth required; writes summary to scratch)
- `POST /v1/proxy/restart` - Restart proxy server process to reload tool/code changes (auth required)
- `POST /v1/telegram/chat` - Telegram bot chat endpoint
- `DELETE /v1/telegram/chat/{conversation_id}` - Clear Telegram conversation history

**Speech & Audio:**
- `POST /v1/audio/transcriptions` - Whisper STT proxy endpoint
- `GET /v1/audio/voices` - Embedded OpenAI-compatible TTS voices (Kitten or Pocket, selected by `model`)
- `POST /v1/audio/speech` - Embedded OpenAI-compatible TTS speech (Kitten or Pocket; PCM/WAV + stream)
- `GET /v1/proxy/tts/voices` - Get available TTS voices
- `POST /v1/proxy/tts/speech` - Generate TTS speech (supports streaming)
- `GET /v1/client-config` - Expose non-secret UI defaults (e.g., TTS endpoint/model/voice)

**MCP Server Management:**
- `POST /v1/mcp/servers` - Add or update MCP server configuration
- `GET /v1/mcp/servers` - List all configured MCP servers
- `POST /v1/mcp/servers/{server_id}/connect` - Connect to an MCP server
- `POST /v1/mcp/servers/{server_id}/disconnect` - Disconnect from an MCP server
- `POST /v1/mcp/servers/{server_id}/tools/call` - Call an MCP tool
- `POST /v1/mcp/servers/{server_id}/tools/list` - List available MCP tools

**File Operations:**
- `POST /v1/files/read` - Read files (supports: txt, docx, xlsx, pdf, png, jpg)
- `POST /v1/files/write` - Write files (supports: txt, docx, xlsx, pdf)
- `GET /v1/files/list` - List files in scratch directory (optional query params: `path`, `recursive`)
- `DELETE /v1/files/delete/{filename}` - Delete a file from scratch directory

**Todo list (all require authentication: `Authorization: Bearer <JWT>`):**
- `GET /v1/todo` - List current user's tasks (`?due_only=true` optional)
- `GET /v1/todo/due` - List only due scheduled tasks (`nextRunAt <= now`)
- `POST /v1/todo` - Add task (body supports `taskDescription`, optional `scheduledFor`, optional `recurrence`)
- `PATCH /v1/todo/{task_id}` - Update task (body supports `taskDescription`, `scheduledFor`, `recurrence`, `clearSchedule`, `clearRecurrence`)
- `DELETE /v1/todo/{task_id}` - Delete task
- `DELETE /v1/todo` - Clear all tasks

**Task Execution (all require authentication):**
- `POST /v1/todo/execute` - Start execution for a task (body: `{"taskId": 1, "promptOverride": "optional"}`)
- `POST /v1/todo/execute/resume` - Resume paused execution (body: `{"userMessage": "...", "taskId": 1}`; `taskId` optional unless multiple paused tasks exist)
- `POST /v1/todo/{task_id}/complete` - Human verification: mark task complete (one-time tasks removed, repeating tasks rescheduled)
- `POST /v1/todo/execute/cancel` - Cancel an active execution (optional query: `?taskId=1`; required when multiple tasks are active)
- `GET /v1/todo/execute/status` - Execution status summary (`active`, `activeTaskIds`, `runs`, optional `task` when `?taskId=...` is provided)
- `taskId` values are stable per task and are never reused for future tasks in that user list.

**Utility:**
- `GET /health` - Health check endpoint
- `GET /test` - Simple test endpoint

#### MCP Browser HTTP Server Endpoints (Port 5001)

- `POST /api/browser-agent` - Execute browser automation task (`X-Agent-Secret` or `Authorization: Bearer <shared-secret>` required)
- `POST /api/deep-research` - Execute deep research task (`X-Agent-Secret` or `Authorization: Bearer <shared-secret>` required)
- `GET /api/health` - Check server health, MCP availability, and whether bridge auth is configured
- `POST /api/disconnect` - Disconnect MCP client

### Using Browser Automation

```bash
# Preferred: via proxy routes / tools
curl -X POST http://localhost:8002/v1/proxy/browser-agent \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <jwt>" \
  -d '{"task": "Go to example.com and get the page title"}'

# Direct bridge access for local/internal callers only
curl -X POST http://localhost:5001/api/browser-agent \
  -H "Content-Type: application/json" \
  -H "X-Agent-Secret: <MCP_BROWSER_SERVER_SECRET>" \
  -d '{"task": "Go to example.com and get the page title"}'

# Via Proxy Server MCP endpoints
curl -X POST http://localhost:8002/v1/mcp/servers/browser-use/tools/call \
  -H "Content-Type: application/json" \
  -d '{"toolName": "run_browser_agent", "parameters": {"task": "Your task here"}}'
```

### Using File Operations

```bash
# Read a file
curl -X POST http://localhost:8002/v1/files/read \
  -H "Content-Type: application/json" \
  -d '{"filename": "document.docx"}'

# Write a file
curl -X POST http://localhost:8002/v1/files/write \
  -H "Content-Type: application/json" \
  -d '{"filename": "output.docx", "content": "Your content here", "format": "docx"}'

# List top-level files
curl http://localhost:8002/v1/files/list

# List files in a subdirectory
curl "http://localhost:8002/v1/files/list?path=images"

# List files recursively under a subdirectory
curl "http://localhost:8002/v1/files/list?path=images&recursive=true"

# Delete a file
curl -X DELETE http://localhost:8002/v1/files/delete/document.docx
```

Supported file formats:
- **Read**: txt, docx, xlsx, pdf, png, jpg, jpeg
- **Write**: txt, docx, xlsx, pdf

### Using Telegram Bot

Telegram users talk to the CATBot assistant via a polling bot. The bot forwards messages to the CATBot proxy server, which keeps per-user conversation history and calls the same OpenAI-compatible LLM used elsewhere (configurable via `OPENAI_API_KEY` or `MCP_LLM_OPENAI_API_KEY`). Memory and assistant context (timezone, knowledge cutoff) apply to Telegram chats as well. To use the same system prompt and rules as the web UI, place your prompt in `config/catbot_system_prompt.txt`; the proxy uses it for Telegram when the file exists.

**Setup:**
1. Create a bot with [@BotFather](https://core.telegram.org/bots#botfather)
2. Set `TELEGRAM_BOT_TOKEN` in your `.env` file
3. Configure `TELEGRAM_ADMIN_IDS` or set `TELEGRAM_ALLOW_ALL=true`
4. Set `TELEGRAM_SECRET` on both bot and proxy when the proxy is reachable beyond loopback.
5. Ensure the proxy server is running (e.g. port 8002). For Telegram-only use, only the proxy and the bot need to run.
6. Start the bot: run `python scripts/start_all.py` (the Telegram bot is started automatically), or start it only with `python -m src.integrations.telegram_bot` from the project root. Install the dependency first: `pip install -r requirements.txt` or `pip install "python-telegram-bot[rate-limiter]"`.

**Bot Commands:**
- `/start` - Greet the user and register the conversation
- `/help` - Display available commands
- `/status` - Report backend status and message counts
- `/clear` - Clear the conversation history on the backend

**Telegram tools (optional):**  
Set `TELEGRAM_TOOLS_ENABLED=true` in the proxy environment to enable the same tool set as the web client. When enabled, the model can use tools (e.g. web search, read/write files in scratch, todo list, memory cache, workflows, news, calculate, store/search memories). The proxy parses `<tool>...</tool><parameters>...</parameters>` from the model reply, executes the tool server-side, and sends the result back to the model for a natural-language reply.

- **Available in Telegram:** manageTodoList, executeTodoTask (run task with tools; human confirms completion), manageMemoryCache, navigateToUrl (returns link text), openChatToUser, calculate, runWorkflow (AutoGen), runCodexCli (Codex CLI for CATBot code changes), restartProxyServer (restart proxy to load new/updated tools), scrapeWebsite, webSearch, fetchNews, readFile, writeFile, listFiles, sendTelegramFile (attach file from `scratch/` into current Telegram chat), storeMemory, searchMemories, listMemories, deleteMemory, runBrowserAgent, runDeepResearch, uploadToGoogleDrive, llmQuery (or web-only message). Todo list is persistent and stored per user (or per Telegram chat if not linked). **scrapeWebsite** accepts a single `url` or an optional `urls` array; when `urls` is provided (e.g. from a prior webSearch), the backend tries each URL in order until one succeeds (scrape-with-retry). For JavaScript-heavy sites, pass `render_js=true` and optional `render_engine`, `wait_for_selector`, `js_wait_ms`. The same behaviour is supported in the web (HTML) client.
- **Available in web and Telegram:** PDF to PowerPoint (`pdfToPowerPoint`) accepts PDF or Markdown sources from uploads, scratch-relative paths, and URLs, then produces a `.pptx` presentation.
- **Config:** `config/catbot_system_prompt_with_tools.txt` (included) defines the tool list and format; placeholders `{{MEMORY_CACHE}}` and `{{TODO_LIST}}` are filled per conversation. Max tool-loop iterations per message: `TELEGRAM_TOOLS_MAX_ITERATIONS` (default 5).

## Project Structure

```
AI_assistant/
├── src/                   # Application source code
│   ├── servers/          # HTTP/API servers (proxy, https, mcp_browser)
│   ├── mcp/               # MCP client (mcp_browser_client)
│   ├── integrations/      # Telegram bot
│   ├── features/          # Philosopher mode
│   └── memory/            # Memory system (embeddings, vector store)
├── scripts/               # Entry points and run scripts
│   ├── start_all.py       # Start all services (Windows)
│   ├── stop_all.py        # Stop all services (Windows)
│   └── ...
├── tests/                 # Test files
├── config/                # Configuration files
│   ├── team-config.json   # AutoGen team configuration
│   ├── mcp_servers.json   # MCP server configurations
│   └── mcp_config.env.example
├── docs/                  # Documentation
├── assets/                # Static assets (favicons, images)
├── certs/                 # TLS certificates
├── libs/                  # Third-party libraries (ogg-opus-decoder)
├── mcp-browser-use/       # MCP Browser-Use checkout from the CATBot fork
├── memory_data/           # Runtime memory data
├── scratch/               # File operations workspace
├── research_output/       # Research tool outputs
├── package.json           # Node.js dependencies
├── index.html             # Web interface
└── README.md              # This file
```

## Dependencies

### NPM Packages

| Package | Version | Purpose |
|---------|---------|----------|
| `@langchain/mcp-adapters` | ^0.6.0 | LangChain integration with Model Context Protocol |
| `@modelcontextprotocol/sdk` | ^1.0.0 | Model Context Protocol SDK for Node.js |
| `axios` | ^1.6.2 | HTTP client for API requests |
| `cors` | ^2.8.5 | Cross-Origin Resource Sharing middleware |
| `express` | ^4.18.2 | Web server framework |
| `ogg-opus-decoder` | ^1.7.3 | Audio decoder for Opus codec |

### Python Packages

Key packages include (see [Installation Guide](#step-3-install-python-dependencies) and `requirements.txt` for the full list):

| Package | Purpose |
|---------|---------|
| `fastapi`, `uvicorn` | Proxy server and API |
| `httpx` | HTTP client (proxy, Telegram bot backend requests) |
| `python-telegram-bot[rate-limiter]` | Telegram bot integration (polling) |
| `python-dotenv` | Load `.env` configuration |
| `flask`, `flask-cors` | MCP browser HTTP server |
| `kittentts` | Embedded OpenAI-compatible TTS (`/v1/audio/speech`, `/v1/audio/voices`) |
| `pocket-tts` | Embedded Kyutai Pocket TTS realtime backend (`/v1/audio/speech`, `/v1/audio/voices`) |
| `python-docx`, `openpyxl`, `PyPDF2`, `Pillow`, `reportlab` | File operations |

Install all Python dependencies with: `pip install -r requirements.txt`

## Additional Resources

### Official Documentation

- **[Microsoft AutoGen](https://microsoft.github.io/autogen/)** — Multi-agent collaboration framework
  - GitHub: https://github.com/microsoft/autogen
  - AutoGen Studio: https://github.com/microsoft/autogen-studio

- **[Browser-Use](https://docs.browser-use.com/)** — Autonomous browser automation
  - GitHub: https://github.com/browser-use/browser-use

- **[MCP Browser-Use Server](https://github.com/andyjm2k/mcp-browser-use)** — CATBot-maintained MCP integration for browser-use

- **[Model Context Protocol (MCP)](https://modelcontextprotocol.io/)** — Protocol for AI tool integration
  - Python SDK: https://github.com/modelcontextprotocol/python-sdk
  - Node.js SDK: https://github.com/modelcontextprotocol/typescript-sdk

- **[UV Package Manager](https://github.com/astral-sh/uv)** — Fast Python package manager
  - Documentation: https://docs.astral.sh/uv/

- **[Playwright](https://playwright.dev/python/)** — Browser automation framework
  - GitHub: https://github.com/microsoft/playwright

- **[FastAPI](https://fastapi.tiangolo.com/)** — Modern web framework
  - GitHub: https://github.com/tiangolo/fastapi

### Avatar Resources

- **[VRoid Studio](https://vroid.com/studio)** — Create 3D avatars
- **[VRM Specification](https://github.com/vrm-c/vrm-specification)** — VRM format documentation
- **[VRM Animation](https://github.com/vrm-c/vrm-specification/tree/master/specification/VRMC_vrm_animation-1.0)** — Animation format
- **[Live2D Cubism](https://www.live2d.com/)** — 2D avatar platform

### API Services

- **[OpenAI API](https://platform.openai.com/docs)** — LLM and TTS services
- **[Brave Search API](https://brave.com/search/api/)** — Web search
- **[News API](https://newsapi.org/)** — News aggregation
- **[Telegram Bot API](https://core.telegram.org/bots/api)** — Telegram integration

## Troubleshooting

### Common Issues

1. **UV Command Not Found**
   ```bash
   pip install uv
   # Or use official installer (see Installation Guide)
   ```

2. **Playwright Browsers Not Found**
   ```bash
   playwright install
   # Or for uv environment:
   cd mcp-browser-use
   uv run playwright install
   ```

3. **MCP Server Won't Start**
   ```bash
   cd mcp-browser-use
   uv sync
   uv run mcp-server-browser-use --help
   ```

4. **Missing API Keys**
   - Ensure all required API keys are set in `.env` file
   - Verify environment variables are loaded correctly
   - Check `config/mcp_config.env.example` for all available configuration options

5. **Port Already in Use**
   - Change port numbers in configuration files
   - Or stop the process using the port
   - Use `python scripts/stop_all.py` to stop all services on Windows

6. **File Operations Not Working**
   - Ensure file operation libraries are installed: `pip install python-docx openpyxl PyPDF2 reportlab Pillow`
   - Check that files are in the `scratch/` directory
   - Verify file format is supported (txt, docx, xlsx, pdf, png, jpg)

7. **Telegram Bot Not Responding**
   - See "Telegram Bot Configuration" above and `config/telegram_env_example.txt` for required vs optional variables.
   - Verify `TELEGRAM_BOT_TOKEN` is set correctly
   - Check that `TELEGRAM_ADMIN_IDS` is configured (numeric IDs only) or `TELEGRAM_ALLOW_ALL=true`
   - Ensure the proxy server is running on port 8002
   - Set `OPENAI_API_KEY` or `MCP_LLM_OPENAI_API_KEY` on the proxy so Telegram chat can call the LLM
   - If using `TELEGRAM_SECRET`, set the same value on both the bot and the proxy
   - For **Telegram tools**: set `TELEGRAM_TOOLS_ENABLED=true` on the proxy; ensure `config/catbot_system_prompt_with_tools.txt` exists. Tools need the same backend config as the web UI (e.g. `BRAVE_API_KEY`, `NEWS_API_KEY`).
- For Telegram file attachments (`sendTelegramFile`), ensure the file exists in `scratch/` (top-level or subdirectory path) and is within size limits.
   - Check bot logs for connection errors

8. **runCodexCli Not Triggering or Failing (Telegram or Web UI)**
   - Verify the tool-capable prompt is in use. For Telegram, `TELEGRAM_TOOLS_ENABLED=true` and do not override `system_prompt` with a non-tool prompt.
   - Ensure `CODEX_ENABLED=true` on the proxy.
   - Confirm the `codex` binary is installed and available on PATH (or set `CODEX_CLI_PATH`).
   - Web UI only: confirm you are authenticated (JWT); `/v1/proxy/codex` requires auth.
   - If the model returns tool calls inside fenced code blocks (```), Telegram will ignore them.
   - Check proxy logs for `Codex CLI not found` or `Codex CLI tool is disabled`.

9. **AutoGen Workflow Returns 401**
   - Confirm you are signed in before calling `/v1/proxy/autogen` from the web UI.
   - For internal callers, set `CATBOT_AGENT_SECRET` (or `AUTOGEN_TEAM_SECRET`) and send it as `X-Agent-Secret`.
   - Leave `AUTOGEN_REQUIRE_AUTH=true` unless you intentionally want a public endpoint.
   - Leave `AUTOGEN_ENABLE_CODE_EXECUTION=false` unless you intentionally want Docker-backed execution inside the AutoGen team.

10. **MCP Browser Server Connection Issues**
   - Verify MCP Browser-Use server is running
   - Check environment variables in `.env` file, especially `MCP_BROWSER_SERVER_SECRET`
   - Ensure `MCP_RESEARCH_TOOL_SAVE_DIR` directory exists
   - Review `start_mcp_browser_server.py` output for configuration errors

10. **CORS Errors in Browser**
   - Proxy server includes CORS middleware - ensure it's running
   - Browser UI requests should go to port `8002` via the proxy, not directly to port `5001`
   - Direct browser access to port `5001` requires `MCP_BROWSER_SERVER_ALLOWED_ORIGINS` to include the calling origin
   - Verify browser console for specific CORS error messages

11. **Todo list not syncing / Task execution not starting**
   - **Todo:** Ensure you are signed in (JWT). Todo is stored per user in `todo_data/` (or `TODO_DATA_PATH`). For Telegram, use `config/telegram_user_links.json` to link your Telegram user ID to your app username so the same list appears in the web UI—see **config/TELEGRAM_TODO_LINK.md** for step-by-step instructions (get your Telegram ID with `/status` in the bot).
   - **Task execution:** All todo/execution endpoints require authentication (Bearer token). Multiple task executions can run in parallel per user (one run per task ID). Use `taskId` for resume/cancel/status targeting when more than one run exists. Set `TASK_EXECUTION_MAX_ITERATIONS` in `.env` if you need a higher iteration limit (default 200).

### Getting Help

- Check the installation guide: `INSTALL_GUIDE.md`
- Review MCP Browser-Use README: `mcp-browser-use/README.md`
- Enable debug logging: Set `MCP_SERVER_LOGGING_LEVEL=DEBUG` in `.env`
- Check proxy server logs for API endpoint errors
- Review test files in `tests/` for usage examples

### Testing the Installation

Run tests from project root:

```bash
# Full local regression run for Codex and maintainers
python scripts/run_full_regression.py

# List available regression suites
python scripts/run_full_regression.py --list

# Run all Python tests directly
python -m pytest tests/ -v

# Test file operations
python -m pytest tests/test_file_operations.py -v

# Test MCP client (HTTP; requires mcp-server-browser-use server running)
python -m pytest tests/test_mcp_client.py -v

# Test server endpoints
python -m pytest tests/test_server.py -v
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Third-Party Licenses

This project includes third-party software components. For complete attribution
and license information, please see the [NOTICE](NOTICE) file.

**Summary of third-party licenses:**
- **MCP Browser-Use**: MIT License (see `mcp-browser-use/LICENSE`)
- **AutoGen**: MIT License (see [Microsoft AutoGen repository](https://github.com/microsoft/autogen))
- **Browser-Use**: MIT License (see [browser-use repository](https://github.com/browser-use/browser-use))
- **ogg-opus-decoder**: MIT License (see `libs/ogg-opus-decoder/LICENSE`)

All third-party components use permissive open source licenses (MIT) that are
compatible with each other and allow for commercial use.

## Contributing

Contributions are welcome! Please ensure:
- Code follows project style guidelines
- Tests are included for new features
- Documentation is updated
- Dependencies are properly listed

---

**Last Updated**: 2024  
**Project Version**: 1.0.0
