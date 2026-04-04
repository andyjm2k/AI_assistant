# CATBot Automated Install

Short deploy guide for bringing CATBot up on a new machine, especially a fresh Windows environment.

## Prerequisites

Install these before running the installer:

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | Used for CATBot and the main venv |
| Node.js | 16+ | Used for package install and optional Codex CLI install |
| Git | current | Used for the repo and the forked `mcp-browser-use` checkout |
| uv | current | Used by `mcp-browser-use` (`pip install uv`) |

Recommended:

- Chrome or Chromium for browser automation
- `espeak-ng` on `PATH` if you plan to enable embedded Kitten TTS

## Install

1. Clone the repo:

```bash
git clone https://github.com/andyjm2k/CATBot.git
cd CATBot
```

2. Run the installer from the project root:

- Windows: `.\install.ps1` or `install.bat`
- Linux/macOS: `chmod +x install.sh && ./install.sh`

The installer now does the full dependency path:

- checks Python / Node / Git / `uv`
- creates the main `venv`
- installs Python deps from `requirements.txt`
- installs Playwright browsers for the main venv
- installs Node deps with `npm ci` when `package-lock.json` is present
- installs Codex CLI if it is not already on `PATH`
- prepares the forked `mcp-browser-use` checkout with `uv sync --frozen` when `uv.lock` is present
- creates `.env` and required directories
- runs the interactive configuration wizard
- runs `scripts/verify_install.py`

Note:

- AutoGen Studio is not installed into the main CATBot `venv`. Current `autogenstudio` releases still conflict with CATBot's pinned `autogen-core 0.7.x` packages.
- If you want the Studio UI on port `8084`, install `autogenstudio` separately and either add it to `PATH` or set `AUTOGENSTUDIO_CMD` to the Studio executable before running `scripts/start_all.py`.

## Configuration

The installer wizard writes the core `.env` entries for you and now mirrors provider settings into the standard env names that older CATBot modules still read directly.
It also generates a real `JWT_SECRET`, configures a shared internal agent secret, keeps `AUTOGEN_REQUIRE_AUTH=true`, and leaves `AUTOGEN_ENABLE_CODE_EXECUTION=false` unless you opt in later.

Required for a basic install:

- `MCP_LLM_PROVIDER`
- `MCP_LLM_MODEL_NAME`
- the matching API key, or local Ollama config

Recommended for day-one usability:

- `BRAVE_API_KEY` for web search
- `HTTPS_CERT_HOSTNAME` for local HTTPS/cert generation

Recommended for a private deployment:

- keep `AUTOGEN_REQUIRE_AUTH=true` so `/v1/proxy/autogen` is not public
- leave `AUTOGEN_ENABLE_CODE_EXECUTION=false` unless you intentionally want the Docker execution tool
- treat `JWT_SECRET` and `CATBOT_AGENT_SECRET` as secrets and rotate existing JWTs if you replace `JWT_SECRET`

Optional sections in [.env.example](/C:/Users/pc/CATBot/.env.example) to review before first full test:

- Whisper/STT: `WHISPER_*`
- Telegram: `TELEGRAM_*`
- Google Drive uploads: `GOOGLE_DRIVE_*`
- GitHub skill: `GITHUB_*`
- Spotify skill: `SPOTIFY_*`
- image generation: `IMAGE_GENERATION_*`, `OPENROUTER_*`
- memory overrides: `MEMORY_*`, `EMBEDDINGS_*`, `MEMORY_EXTRACTOR_*`
- Codex tool: `CODEX_*`

## Forked browser-use

The project uses the CATBot-maintained fork in `mcp-browser-use/`.

Manual recovery commands if you want to re-run just that piece:

```bash
cd mcp-browser-use
uv sync --frozen
uv run playwright install
uv run mcp-server-browser-use --help
```

On Windows, use the project launcher for the HTTP server so UTF-8 and repo-local runtime paths are forced:

```bash
python scripts/start_mcp_browser_use_http_server.py
```

## Verification

Re-run post-install verification:

```bash
python scripts/verify_install.py
```

Check prerequisites only:

```bash
python scripts/check_prereqs.py
```

## Start

Windows:

```bash
start.bat
```

or:

```bash
venv\Scripts\python.exe scripts/start_all.py
```

Linux/macOS: start the same Python entrypoints documented in [README.md](/C:/Users/pc/CATBot/README.md) with your preferred process manager.

## Troubleshooting

- `uv not found`: install `uv` first, then rerun the installer
- `mcp-browser-use` verification fails: rerun `uv sync --frozen` and `uv run playwright install` inside `mcp-browser-use`
- embedded Kitten TTS warnings: install `espeak-ng`
- feature sanity warnings in `verify_install.py`: finish the matching `.env` section for that feature before testing it
