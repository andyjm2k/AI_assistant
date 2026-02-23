# CATBot — Automated install and deploy

Short guide for deploying CATBot on a new machine using the automated installer.

## Prerequisites

Install these before running the installer (the installer will check and report what is missing):

| Tool | Version | Notes |
|------|---------|--------|
| **Python** | 3.11+ | [python.org](https://www.python.org/downloads/) |
| **Node.js** | 16+ | [nodejs.org](https://nodejs.org/) |
| **Git** | — | For clone and submodule; [git-scm.com](https://git-scm.com/) |
| **uv** | — | For mcp-browser-use; `pip install uv` or [astral-sh/uv](https://github.com/astral-sh/uv) |
| **Codex CLI** | — | Optional but recommended for `runCodexCli` tool; installed by the automated scripts (uses npm) |

Optional: Chrome/Chromium for browser automation.

## One-line install

1. **Clone** the repository (if you have not already):
   ```bash
   git clone https://github.com/andyjm2k/CATBot.git
   cd CATBot
   ```

2. **Run the installer** from the project root:
   - **Windows:** `.\install.ps1` or `install.bat`
   - **Linux/macOS:** `chmod +x install.sh` (once), then `./install.sh`

3. **Configure:** The installer runs an interactive **configuration wizard** that asks for your LLM provider, model, API keys (OpenAI/Google/etc.), optional Brave/News keys, and optional Telegram bot. Your answers are written to `.env` so you usually don’t need to edit it by hand. If you skip the wizard (e.g. non-interactive install) or need to change something later, edit `.env` (see below).

4. **Start:** On Windows run `start.bat` or `python scripts/start_all.py`. On Linux/macOS start the services as documented in the README (e.g. run the same Python modules in separate terminals or use your preferred process manager).

## Post-install: API keys

In `.env` set at least:

- **LLM:** e.g. `MCP_LLM_PROVIDER` and `MCP_LLM_MODEL_NAME`, plus the matching API key (`MCP_LLM_OPENAI_API_KEY`, `MCP_LLM_GOOGLE_API_KEY`, etc.) or use Ollama locally.
- **Web search:** `BRAVE_API_KEY` (or the app will fall back to DuckDuckGo).
- **Optional:** `NEWS_API_KEY`, `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ADMIN_IDS` for Telegram.

See `config/mcp_config.env.example` and the README Configuration section for the full list.

## Optional: Whisper (speech-to-text)

The default STT endpoint is `http://localhost:8001/v1/audio/transcriptions`. To use your own Whisper-compatible server:

1. Run or deploy a Whisper API server (e.g. [whisper-api-server](https://github.com/ahmetoner/whisper-api-server) in a sibling directory).
2. In `.env` set `WHISPER_ENDPOINT` to your server URL.

The Windows `start_all.py` script can start a sibling `whisper-api-server` if present; otherwise start it separately.

## Optional: Telegram bot

1. Create a bot with [BotFather](https://core.telegram.org/bots#botfather) and get the token.
2. In `.env` set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ADMIN_IDS` (or `TELEGRAM_ALLOW_ALL=true`).
3. Start the stack; the Telegram bot is started by `start_all.py` on Windows.

## Optional: Codex CLI tool

The installer attempts to install the Codex CLI automatically (via npm) if it is not already on your PATH. To configure:

1. Ensure `codex` is available on PATH (or set `CODEX_CLI_PATH` in `.env`).
2. Optional: tune `CODEX_SANDBOX_MODE`, `CODEX_APPROVAL_POLICY`, and `CODEX_TIMEOUT_SECONDS` in `.env`.
3. The `runCodexCli` tool is available in both web and Telegram when tools are enabled. It runs in the CATBot project root and writes a summary file to `scratch/`.

## Verification

To re-run the post-install checks without reinstalling:

```bash
# From project root with venv activated (Windows: venv\Scripts\activate)
python scripts/verify_install.py
```

To only check prerequisites:

```bash
python scripts/check_prereqs.py
```

## Troubleshooting

- **"Python 3.11+ required"** — Install Python 3.11 or newer and ensure `python` or `py` is on your PATH.
- **"uv not found"** — Install uv: `pip install uv` or use the official install script for your OS.
- **"mcp-browser-use directory not found"** — Clone or add the mcp-browser-use repo into the project as `mcp-browser-use/` (see README).
- **Verify step fails** — Ensure the venv is activated and you ran the full installer (pip install, playwright, uv sync in mcp-browser-use).

For more help see the main [README](README.md) and [Troubleshooting](README.md#troubleshooting) section.
