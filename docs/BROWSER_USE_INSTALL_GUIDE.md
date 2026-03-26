# MCP Browser-Use Install Guide

Current install notes for CATBot's forked `mcp-browser-use` checkout.

## What this repo expects

CATBot uses the fork in:

- [mcp-browser-use](/C:/Users/pc/CATBot/mcp-browser-use)

The main installer now prepares it automatically, but these are the manual steps and recovery commands.

## Prerequisites

- Python 3.11+
- `uv`
- Chrome / Chromium
- Playwright browser install support

Windows note:

- Start the HTTP server through [scripts/start_mcp_browser_use_http_server.py](/C:/Users/pc/CATBot/scripts/start_mcp_browser_use_http_server.py) when possible. That launcher forces UTF-8 and keeps runtime/cache paths inside the repo, which avoids the Windows permission and encoding failures seen with direct `uv run ... server`.

## Install the fork

From the CATBot project root:

```bash
cd mcp-browser-use
uv sync --frozen
uv run playwright install
uv run mcp-server-browser-use --help
```

If `uv.lock` is missing in a future branch, use:

```bash
uv sync
```

## Start the HTTP MCP server

Recommended from the CATBot project root:

```bash
python scripts/start_mcp_browser_use_http_server.py
```

Direct fallback from inside `mcp-browser-use`:

```bash
uv run mcp-server-browser-use server
```

Default CATBot connection target:

```env
MCP_BROWSER_USE_HTTP_URL=http://127.0.0.1:8383/mcp
```

## Required `.env` pieces

Core settings live in [.env.example](/C:/Users/pc/CATBot/.env.example).

For browser-use to match the rest of CATBot, configure:

```env
MCP_LLM_PROVIDER=...
MCP_LLM_MODEL_NAME=...
MCP_LLM_BASE_URL=...      # only when needed for the provider
MCP_BROWSER_HEADLESS=false
MCP_AGENT_MAX_STEPS=20
MCP_AGENT_USE_VISION=true
MCP_RESEARCH_SAVE_DIRECTORY=./scratch
```

Also set the matching provider key:

```env
# examples
MCP_LLM_OPENAI_API_KEY=
MCP_LLM_GOOGLE_API_KEY=
MCP_LLM_ANTHROPIC_API_KEY=
MCP_LLM_OPENROUTER_API_KEY=
```

The install wizard now also mirrors provider settings into the standard env aliases used by older CATBot modules, such as `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_BASE`, and `OPENAI_MODEL` where applicable.

## Validation

Run the CATBot verifier from the project root:

```bash
python scripts/verify_install.py
```

That now checks:

- core Python runtime imports
- `mcp-server-browser-use` CLI availability
- direct optional runtime imports used by CATBot (`bs4`, Google Drive libs, `huggingface_hub`, multipart)
- `.env` sanity for mirrored provider aliases and partially configured features

## Fresh Windows checklist

Use this sequence for a start-to-finish test on a fresh Windows machine:

1. Run `.\install.ps1`
2. Complete the wizard
3. Confirm `python scripts/verify_install.py` passes
4. Start `start.bat`
5. Check browser-use health by confirming the launcher window for `start_mcp_browser_use_http_server.py` starts cleanly

If browser-use still fails on Windows:

```bash
cd mcp-browser-use
uv sync --frozen
uv run mcp-server-browser-use --help
cd ..
python scripts/start_mcp_browser_use_http_server.py
```
