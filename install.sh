#!/usr/bin/env bash
# CATBot automated installer (Linux/macOS).
# Run from project root: ./install.sh
# Prereqs: Python 3.11+, Node 16+, Git, uv (installer will check).

set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "CATBot installer — project root: $PROJECT_ROOT"

# 1. Prerequisites check
echo ""
echo "[1/10] Checking prerequisites..."
python3 scripts/check_prereqs.py 2>/dev/null || python scripts/check_prereqs.py
if [ $? -ne 0 ]; then
  echo "Prerequisites check failed. Install missing tools and run install.sh again." >&2
  exit 1
fi

# 2. Git submodule (mcp-browser-use)
echo ""
echo "[2/10] Initializing mcp-browser-use..."
MCP_DIR="$PROJECT_ROOT/mcp-browser-use"
if [ -d "$MCP_DIR" ]; then
  if [ -d "$MCP_DIR/.git" ]; then
    git submodule update --init --recursive || true
  fi
else
  echo "mcp-browser-use directory not found. Clone it or add as submodule; see README." >&2
  exit 1
fi

# 3. Python venv and pip install
echo ""
echo "[3/10] Creating venv and installing Python dependencies..."
VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"
VENV_PIP="$PROJECT_ROOT/venv/bin/pip"
if [ ! -x "$VENV_PYTHON" ]; then
  python3 -m venv venv 2>/dev/null || python -m venv venv
fi
"$VENV_PYTHON" -m pip install --upgrade pip -q
"$VENV_PIP" install -r requirements.txt
if [ $? -ne 0 ]; then
  echo "pip install failed." >&2
  exit 1
fi

# 4. Playwright (main venv)
echo ""
echo "[4/10] Installing Playwright browsers..."
"$VENV_PYTHON" -m playwright install
if [ $? -ne 0 ]; then
  echo "Playwright install failed." >&2
  exit 1
fi

# 5. Node dependencies
echo ""
echo "[5/10] Installing Node.js dependencies..."
npm install
if [ $? -ne 0 ]; then
  echo "npm install failed." >&2
  exit 1
fi

# 6. Codex CLI (optional)
echo ""
echo "[6/10] Installing Codex CLI (optional)..."
if ! command -v codex >/dev/null 2>&1; then
  echo "Codex CLI not found; installing via npm..."
  npm install -g @openai/codex || echo "Codex CLI install failed (optional). You can install it later and set CODEX_CLI_PATH."
else
  echo "Codex CLI already installed."
fi

# 7. mcp-browser-use: uv sync and playwright
echo ""
echo "[7/10] Setting up mcp-browser-use (uv sync + playwright)..."
(cd "$MCP_DIR" && uv sync && uv run playwright install)
if [ $? -ne 0 ]; then
  echo "mcp-browser-use setup failed." >&2
  exit 1
fi

# 8. .env and directories
echo ""
echo "[8/10] Creating .env and required directories..."
"$VENV_PYTHON" scripts/setup_env_and_dirs.py
if [ $? -ne 0 ]; then
  echo "setup_env_and_dirs failed." >&2
  exit 1
fi

# 9. Configuration wizard (interactive; collects API keys and writes .env)
echo ""
echo "[9/10] Configuration wizard (API keys, Telegram, etc.)..."
"$VENV_PYTHON" scripts/install_wizard.py
if [ $? -ne 0 ]; then
  echo "Wizard failed." >&2
  exit 1
fi

# 10. Verification
echo ""
echo "[10/10] Verifying installation..."
export CATBOT_VERIFY_PYTHON="$VENV_PYTHON"
"$VENV_PYTHON" scripts/verify_install.py
if [ $? -ne 0 ]; then
  echo "Verification failed. Fix the above before starting CATBot." >&2
  exit 1
fi

echo ""
echo "CATBot install complete."
echo "Next steps:"
echo "  If you skipped the wizard or need to change settings: edit .env"
echo "  Activate venv: source venv/bin/activate"
echo "  Start services (see README for running each component or use your process manager)."
echo ""
