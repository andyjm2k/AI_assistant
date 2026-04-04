# CATBot automated installer (Windows).
# Run from project root: .\install.ps1
# Prereqs: Python 3.11+, Node 16+, Git, uv (installer will check).

$ErrorActionPreference = 'Stop'
$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location | Select-Object -ExpandProperty Path }
Set-Location $ProjectRoot

Write-Host ('CATBot installer - project root: ' + $ProjectRoot) -ForegroundColor Cyan

# 1. Prerequisites check
Write-Host ([Environment]::NewLine + '[1/10] Checking prerequisites...') -ForegroundColor Yellow
& py scripts/check_prereqs.py
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Prerequisites check failed. Install missing tools and run install.ps1 again.' -ForegroundColor Red
    exit 1
}

# 2. mcp-browser-use: initialize existing checkout if present, else clone CATBot fork
Write-Host ([Environment]::NewLine + '[2/10] Initializing mcp-browser-use...') -ForegroundColor Yellow
$mcpDir = Join-Path $ProjectRoot 'mcp-browser-use'
$mcpRepoUrl = 'https://github.com/andyjm2k/mcp-browser-use.git'
$projectGitDir = Join-Path $ProjectRoot '.git'
if (Test-Path $projectGitDir) {
    & git submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) { Write-Host 'Note: git submodule update had issues (may be OK if no submodules).' -ForegroundColor Gray }
}
# Require full mcp-browser-use tree (pyproject.toml + key source); incomplete/broken copies get replaced by fresh clone
$mcpPyproject = Join-Path $mcpDir 'pyproject.toml'
$mcpExceptions = Join-Path $mcpDir 'src/mcp_server_browser_use/exceptions.py'
$mcpHasContent = (Test-Path $mcpDir) -and (Test-Path $mcpPyproject) -and (Test-Path $mcpExceptions)
if (-not $mcpHasContent) {
    if (Test-Path $mcpDir) {
        Write-Host 'mcp-browser-use exists but is incomplete; cloning fresh copy...' -ForegroundColor Yellow
        Remove-Item -Recurse -Force $mcpDir
    }
    Write-Host ('Cloning ' + $mcpRepoUrl + ' into mcp-browser-use...') -ForegroundColor Cyan
    & git clone --depth 1 $mcpRepoUrl $mcpDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Failed to clone mcp-browser-use. Check network and Git, then run install again.' -ForegroundColor Red
        exit 1
    }
}
if (-not (Test-Path $mcpDir)) {
    Write-Host 'mcp-browser-use directory not found after init/clone. See README.' -ForegroundColor Red
    exit 1
}

# 3. Python venv and pip install
Write-Host ([Environment]::NewLine + '[3/10] Creating venv and installing Python dependencies...') -ForegroundColor Yellow
$venvPath = Join-Path $ProjectRoot 'venv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'
$venvPip = Join-Path $venvPath 'Scripts\pip.exe'

if (-not (Test-Path $venvPython)) {
    & py -m venv venv
    if ($LASTEXITCODE -ne 0) { Write-Host 'Failed to create venv.' -ForegroundColor Red; exit 1 }
}
& $venvPython -m pip install --upgrade pip -q
& $venvPip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host 'pip install failed.' -ForegroundColor Red; exit 1 }

# Ensure embedded Kitten TTS package is present (fallback if direct URL in requirements was blocked)
$kittenImport = & $venvPython -c "import kittentts; print('ok')" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing embedded Kitten TTS package (fallback)...' -ForegroundColor Yellow
    & $venvPip install "https://github.com/KittenML/KittenTTS/releases/download/0.1/kittentts-0.1.0-py3-none-any.whl"
    if ($LASTEXITCODE -ne 0) { Write-Host 'Kitten TTS install failed.' -ForegroundColor Red; exit 1 }
}

# Fail early if pip resolved an AutoGen API that CATBot does not support.
$autogenCompatCheck = @'
import importlib.metadata as m
import inspect
from autogen_agentchat.agents import AssistantAgent
from autogen_core.model_context import BufferedChatCompletionContext

BufferedChatCompletionContext(buffer_size=1)
sig = inspect.signature(AssistantAgent.__init__)
required = ("max_tool_iterations", "reflect_on_tool_use", "tool_call_summary_format")
missing = [name for name in required if name not in sig.parameters]
versions = ", ".join(
    f"{pkg}={m.version(pkg)}"
    for pkg in ("autogen-agentchat", "autogen-core", "autogen-ext")
)
if missing:
    raise SystemExit(
        "Incompatible AutoGen install: AssistantAgent.__init__ missing "
        + ", ".join(missing)
        + ". Installed versions: "
        + versions
    )
print("AutoGen compatibility OK (" + versions + ")")
'@
Write-Host 'Validating AutoGen package compatibility...' -ForegroundColor Yellow
$autogenCompatCheck | & $venvPython -
if ($LASTEXITCODE -ne 0) {
    Write-Host 'AutoGen compatibility check failed. Re-run install after recreating the venv or updating requirements.' -ForegroundColor Red
    exit 1
}

# 4. Playwright (main venv)
Write-Host ([Environment]::NewLine + '[4/10] Installing Playwright browsers...') -ForegroundColor Yellow
& $venvPython -m playwright install
if ($LASTEXITCODE -ne 0) { Write-Host 'Playwright install failed.' -ForegroundColor Red; exit 1 }

# 5. Node dependencies
Write-Host ([Environment]::NewLine + '[5/10] Installing Node.js dependencies...') -ForegroundColor Yellow
if (Test-Path (Join-Path $ProjectRoot 'package-lock.json')) {
    & npm ci
} else {
    & npm install
}
if ($LASTEXITCODE -ne 0) { Write-Host 'Node dependency install failed.' -ForegroundColor Red; exit 1 }

# 6. Codex CLI (optional)
Write-Host ([Environment]::NewLine + '[6/10] Installing Codex CLI (optional)...') -ForegroundColor Yellow
$codexCmd = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codexCmd) {
    Write-Host 'Codex CLI not found; installing via npm...' -ForegroundColor Cyan
    & npm install -g @openai/codex
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Codex CLI install failed (optional). You can install it later and set CODEX_CLI_PATH.' -ForegroundColor Yellow
    }
} else {
    Write-Host 'Codex CLI already installed.' -ForegroundColor Green
}

# 7. mcp-browser-use: uv sync and playwright
Write-Host ([Environment]::NewLine + '[7/10] Setting up mcp-browser-use (uv sync + playwright)...') -ForegroundColor Yellow
Push-Location $mcpDir
try {
    $uvSyncArgs = @('sync')
    if (Test-Path (Join-Path $mcpDir 'uv.lock')) {
        $uvSyncArgs += '--frozen'
    }
    & uv @uvSyncArgs
    if ($LASTEXITCODE -ne 0) { Write-Host 'uv sync failed in mcp-browser-use.' -ForegroundColor Red; exit 1 }
    & uv run playwright install
    if ($LASTEXITCODE -ne 0) { Write-Host 'uv run playwright install failed.' -ForegroundColor Red; exit 1 }
} finally {
    Pop-Location
}

# 8. .env and directories
Write-Host ([Environment]::NewLine + '[8/10] Creating .env and required directories...') -ForegroundColor Yellow
& $venvPython scripts/setup_env_and_dirs.py
if ($LASTEXITCODE -ne 0) { Write-Host 'setup_env_and_dirs failed.' -ForegroundColor Red; exit 1 }

# 9. Configuration wizard (interactive; collects API keys and writes .env)
Write-Host ([Environment]::NewLine + '[9/10] Configuration wizard (API keys, Telegram, etc.)...') -ForegroundColor Yellow
& $venvPython scripts/install_wizard.py
if ($LASTEXITCODE -ne 0) { Write-Host 'Wizard failed.' -ForegroundColor Red; exit 1 }

# 10. Verification
Write-Host ([Environment]::NewLine + '[10/10] Verifying installation...') -ForegroundColor Yellow
$env:CATBOT_VERIFY_PYTHON = $venvPython
& $venvPython scripts/verify_install.py
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Verification failed. Fix the above before starting CATBot.' -ForegroundColor Red
    exit 1
}

Write-Host ([Environment]::NewLine + 'CATBot install complete.') -ForegroundColor Green
Write-Host 'Next steps:' -ForegroundColor Cyan
Write-Host '  If you skipped the wizard or need to change settings: edit .env'
Write-Host '  AutoGen workflow requests now require auth by default (`AUTOGEN_REQUIRE_AUTH=true`).'
Write-Host '  Docker-backed AutoGen code execution stays off until you explicitly set AUTOGEN_ENABLE_CODE_EXECUTION=true.'
Write-Host '  If using Telegram tools/file attachments, set TELEGRAM_SECRET on both bot and proxy.'
Write-Host '  Telegram listFiles now supports path/recursive; sendTelegramFile accepts subdirectory paths under scratch/.'
Write-Host '  Built-in image_generation skill is available (see docs/SKILL_FRAMEWORK.md).'
Write-Host '  Review optional .env sections for Whisper, Spotify, Google Drive, GitHub, and memory overrides.'
Write-Host '  If you plan to use embedded Kitten TTS, install eSpeak NG and ensure espeak-ng is on PATH.'
Write-Host '  Start CATBot: .\start.bat  or  .\venv\Scripts\python.exe scripts/start_all.py'
Write-Host ''
