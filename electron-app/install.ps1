# CATBot Electron desktop avatar installer (Windows)

$ErrorActionPreference = 'Stop'
$ElectronRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location | Select-Object -ExpandProperty Path }
$ProjectRoot = Split-Path $ElectronRoot -Parent
Set-Location $ElectronRoot

Write-Host ('CATBot Desktop Avatar installer - electron root: ' + $ElectronRoot) -ForegroundColor Cyan

Write-Host ([Environment]::NewLine + '[1/6] Checking prerequisites...') -ForegroundColor Yellow
& py ..\scripts\check_prereqs.py
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Prerequisites check failed. Install missing tools and run electron-app\install.ps1 again.' -ForegroundColor Red
    exit 1
}

Write-Host ([Environment]::NewLine + '[2/6] Installing Electron dependencies...') -ForegroundColor Yellow
if (Test-Path (Join-Path $ElectronRoot 'package-lock.json')) {
    & npm ci
} else {
    & npm install
}
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Electron dependency install failed.' -ForegroundColor Red
    exit 1
}

Write-Host ([Environment]::NewLine + '[3/6] Preparing Electron config files...') -ForegroundColor Yellow
& py scripts\setup_electron_env.py
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Electron config bootstrap failed.' -ForegroundColor Red
    exit 1
}

Write-Host ([Environment]::NewLine + '[4/6] Running Electron configuration wizard...') -ForegroundColor Yellow
& py scripts\install_electron_wizard.py
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Electron wizard failed.' -ForegroundColor Red
    exit 1
}

Write-Host ([Environment]::NewLine + '[5/6] Verifying Electron workspace...') -ForegroundColor Yellow
& py scripts\verify_electron_install.py
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Electron verification failed.' -ForegroundColor Red
    exit 1
}

Write-Host ([Environment]::NewLine + '[6/6] Optional Windows installer build...') -ForegroundColor Yellow
$buildInstaller = Read-Host 'Build the NSIS installer now? [y/N]'
if ($buildInstaller -match '^(y|yes)$') {
    & npm run dist:win
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Installer build failed.' -ForegroundColor Red
        exit 1
    }
}

Write-Host ([Environment]::NewLine + 'CATBot Desktop Avatar install complete.') -ForegroundColor Green
Write-Host 'Next steps:' -ForegroundColor Cyan
Write-Host '  Launch the desktop app: npm start'
Write-Host '  Re-run the desktop wizard: py scripts\install_electron_wizard.py'
Write-Host '  Build the installer later: npm run dist:win'
Write-Host '  The existing CATBot HTML client remains unchanged and separate.'
