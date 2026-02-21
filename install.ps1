# CATBot automated installer (Windows).
# Run from project root: .\install.ps1
# Prereqs: Python 3.11+, Node 16+, Git, uv (installer will check).

$ErrorActionPreference = 'Stop'
$ProjectRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location | Select-Object -ExpandProperty Path }
Set-Location $ProjectRoot

Write-Host ('CATBot installer - project root: ' + $ProjectRoot) -ForegroundColor Cyan

# 1. Prerequisites check
Write-Host ([Environment]::NewLine + '[1/9] Checking prerequisites...') -ForegroundColor Yellow
& py scripts/check_prereqs.py
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Prerequisites check failed. Install missing tools and run install.ps1 again.' -ForegroundColor Red
    exit 1
}

# 2. Git submodule (mcp-browser-use) – init and update so submodule is fully populated
Write-Host ([Environment]::NewLine + '[2/9] Initializing mcp-browser-use...') -ForegroundColor Yellow
$mcpDir = Join-Path $ProjectRoot 'mcp-browser-use'
$projectGitDir = Join-Path $ProjectRoot '.git'
if (Test-Path $projectGitDir) {
    & git submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) { Write-Host 'Note: git submodule update had issues (may be OK if no submodules).' -ForegroundColor Gray }
}
if (-not (Test-Path $mcpDir)) {
    Write-Host 'mcp-browser-use directory not found. Clone with --recurse-submodules or add as submodule; see README.' -ForegroundColor Red
    exit 1
}

# 3. Python venv and pip install
Write-Host ([Environment]::NewLine + '[3/9] Creating venv and installing Python dependencies...') -ForegroundColor Yellow
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

# 4. Playwright (main venv)
Write-Host ([Environment]::NewLine + '[4/9] Installing Playwright browsers...') -ForegroundColor Yellow
& $venvPython -m playwright install
if ($LASTEXITCODE -ne 0) { Write-Host 'Playwright install failed.' -ForegroundColor Red; exit 1 }

# 5. Node dependencies
Write-Host ([Environment]::NewLine + '[5/9] Installing Node.js dependencies...') -ForegroundColor Yellow
& npm install
if ($LASTEXITCODE -ne 0) { Write-Host 'npm install failed.' -ForegroundColor Red; exit 1 }

# 6. mcp-browser-use: uv sync and playwright
Write-Host ([Environment]::NewLine + '[6/9] Setting up mcp-browser-use (uv sync + playwright)...') -ForegroundColor Yellow
Push-Location $mcpDir
try {
    & uv sync
    if ($LASTEXITCODE -ne 0) { Write-Host 'uv sync failed in mcp-browser-use.' -ForegroundColor Red; exit 1 }
    & uv run playwright install
    if ($LASTEXITCODE -ne 0) { Write-Host 'uv run playwright install failed.' -ForegroundColor Red; exit 1 }
} finally {
    Pop-Location
}

# 7. .env and directories
Write-Host ([Environment]::NewLine + '[7/9] Creating .env and required directories...') -ForegroundColor Yellow
& $venvPython scripts/setup_env_and_dirs.py
if ($LASTEXITCODE -ne 0) { Write-Host 'setup_env_and_dirs failed.' -ForegroundColor Red; exit 1 }

# 8. Configuration wizard (interactive; collects API keys and writes .env)
Write-Host ([Environment]::NewLine + '[8/9] Configuration wizard (API keys, Telegram, etc.)...') -ForegroundColor Yellow
& $venvPython scripts/install_wizard.py
if ($LASTEXITCODE -ne 0) { Write-Host 'Wizard failed.' -ForegroundColor Red; exit 1 }

# 9. Verification
Write-Host ([Environment]::NewLine + '[9/9] Verifying installation...') -ForegroundColor Yellow
$env:CATBOT_VERIFY_PYTHON = $venvPython
& $venvPython scripts/verify_install.py
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Verification failed. Fix the above before starting CATBot.' -ForegroundColor Red
    exit 1
}

Write-Host ([Environment]::NewLine + 'CATBot install complete.') -ForegroundColor Green
Write-Host 'Next steps:' -ForegroundColor Cyan
Write-Host '  If you skipped the wizard or need to change settings: edit .env'
Write-Host '  Start CATBot: .\start.bat  or  .\venv\Scripts\python.exe scripts/start_all.py'
Write-Host ''
