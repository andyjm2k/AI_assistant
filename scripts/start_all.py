"""
Start all CATBot services in separate command windows.
Run from project root. Uses dynamic paths based on script location.
"""
import subprocess
from pathlib import Path

# Project root = parent of scripts directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
# Fallback if venv312 does not exist (e.g. on Linux or different venv name)
if not VENV_PYTHON.exists():
    VENV_PYTHON = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = "python"  # Use system Python

# Commands to run (each in a new cmd window; cd to project root first)
commands = [
    f'start cmd /k "cd /d {PROJECT_ROOT} && {VENV_PYTHON} -m src.servers.https_server"',
    f'start cmd /k "cd /d {PROJECT_ROOT} && {VENV_PYTHON} -m src.servers.proxy_server"',
    f'start cmd /k "cd /d {PROJECT_ROOT} && %venv% && autogenstudio serve --team config/team-config.json --host 0.0.0.0 --port 8084"',
    f'start cmd /k "cd /d {PROJECT_ROOT} && {VENV_PYTHON} scripts/start_mcp_browser_use_http_server.py"',
    f'start cmd /k "cd /d {PROJECT_ROOT} && {VENV_PYTHON} scripts/start_mcp_browser_server.py"',
    f'start cmd /k "cd /d {PROJECT_ROOT} && {VENV_PYTHON} -m src.integrations.telegram_bot"',
]

# Start all processes in separate command windows
for cmd in commands:
    subprocess.Popen(cmd, shell=True, cwd=str(PROJECT_ROOT))

print("All processes have been started.")
