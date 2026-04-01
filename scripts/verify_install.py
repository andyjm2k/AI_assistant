#!/usr/bin/env python3
"""
Post-install verification for CATBot.
Run from project root with venv activated (or pass path to venv Python).
Exits 0 if all checks pass; prints failures and exits non-zero otherwise.
"""
import os
import subprocess
import sys
from pathlib import Path

# Project root = parent of scripts directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.runtime_env import build_script_env, resolve_project_root

PROJECT_ROOT = resolve_project_root()
MCP_BROWSER_USE_DIR = PROJECT_ROOT / "mcp-browser-use"
MCP_BROWSER_USE_RUNTIME_DIR = MCP_BROWSER_USE_DIR / ".runtime"
MCP_BROWSER_USE_TEMP_DIR = MCP_BROWSER_USE_RUNTIME_DIR / "tmp"
MCP_BROWSER_USE_UV_CACHE_DIR = MCP_BROWSER_USE_RUNTIME_DIR / "uv-cache"
MCP_BROWSER_USE_DOWNLOADS_DIR = MCP_BROWSER_USE_RUNTIME_DIR / "browser-use-downloads"


def _run_python_check(description: str, code: str, python_exe: str | None = None) -> tuple[bool, str]:
    """Run a one-liner Python check; return (success, message)."""
    exe = python_exe or sys.executable
    try:
        result = subprocess.run(
            [exe, "-c", code],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        if result.returncode == 0:
            out = (result.stdout or "").strip()
            return True, out or "OK"
        return False, result.stderr.strip() or result.stdout.strip() or "exit non-zero"
    except Exception as e:
        return False, str(e)


def check_core(python_exe: str | None = None) -> tuple[bool, str]:
    """Verify core server deps: fastapi, uvicorn, httpx, pydantic."""
    return _run_python_check(
        "Core",
        "import fastapi, uvicorn, httpx, pydantic; print('Core OK')",
        python_exe,
    )


def check_autogen(python_exe: str | None = None) -> tuple[bool, str]:
    """Verify AutoGen imports and CATBot's required AssistantAgent API are present."""
    return _run_python_check(
        "AutoGen",
        (
            "import importlib.metadata as m; "
            "import inspect; "
            "import autogen_agentchat; "
            "from autogen_agentchat.agents import AssistantAgent; "
            "from autogen_core.model_context import BufferedChatCompletionContext; "
            "BufferedChatCompletionContext(buffer_size=1); "
            "sig = inspect.signature(AssistantAgent.__init__); "
            "required = ('max_tool_iterations', 'reflect_on_tool_use', 'tool_call_summary_format'); "
            "missing = [name for name in required if name not in sig.parameters]; "
            "versions = ', '.join(f\"{pkg}={m.version(pkg)}\" for pkg in ('autogen-agentchat', 'autogen-core', 'autogen-ext')); "
            "missing and (_ for _ in ()).throw(SystemExit('Incompatible AutoGen install: AssistantAgent.__init__ missing ' + ', '.join(missing) + '; ' + versions)); "
            "print('AutoGen OK (' + versions + ')')"
        ),
        python_exe,
    )


def check_mcp(python_exe: str | None = None) -> tuple[bool, str]:
    """Verify MCP client library."""
    return _run_python_check(
        "MCP",
        "import mcp; print('MCP OK')",
        python_exe,
    )


def check_playwright(python_exe: str | None = None) -> tuple[bool, str]:
    """Verify Playwright is importable."""
    return _run_python_check(
        "Playwright",
        "from playwright.sync_api import sync_playwright; print('Playwright OK')",
        python_exe,
    )


def check_kitten_tts(python_exe: str | None = None) -> tuple[bool, str]:
    """Verify embedded Kitten TTS runtime imports."""
    return _run_python_check(
        "KittenTTS",
        "import kittentts, onnxruntime, misaki, phonemizer; print('KittenTTS OK')",
        python_exe,
    )


def check_runtime_optional_deps(python_exe: str | None = None) -> tuple[bool, str]:
    """Verify direct runtime imports that are easy to miss from requirements.txt."""
    return _run_python_check(
        "Runtime integrations",
        (
            "import bs4, google.oauth2.service_account, googleapiclient.discovery, "
            "huggingface_hub, multipart; print('Runtime integrations OK')"
        ),
        python_exe,
    )


def _build_browser_use_env() -> dict[str, str]:
    """Prepare a child-process environment that matches the Windows-safe launcher settings."""
    env = build_script_env(PROJECT_ROOT, include_venv=False)
    env.pop("VIRTUAL_ENV", None)

    MCP_BROWSER_USE_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    MCP_BROWSER_USE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    MCP_BROWSER_USE_UV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MCP_BROWSER_USE_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["UV_CACHE_DIR"] = str(MCP_BROWSER_USE_UV_CACHE_DIR)
    env["TEMP"] = str(MCP_BROWSER_USE_TEMP_DIR)
    env["TMP"] = str(MCP_BROWSER_USE_TEMP_DIR)
    env["TMPDIR"] = str(MCP_BROWSER_USE_TEMP_DIR)
    env["MCP_BROWSER_DOWNLOADS_DIR"] = str(MCP_BROWSER_USE_DOWNLOADS_DIR)
    env["CATBOT_BROWSER_USE_RUNTIME_DIR"] = str(MCP_BROWSER_USE_RUNTIME_DIR)
    env["CATBOT_BROWSER_USE_STATE_DIR"] = str(MCP_BROWSER_USE_RUNTIME_DIR / "mcp-server-browser-use")
    return env


def _load_env_values() -> dict[str, str]:
    """Parse the project .env file into a simple key/value mapping."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def _is_truthy(value: str | None) -> bool:
    """Interpret common truthy string values."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _command_available(command: list[str]) -> bool:
    """Return True when a command can be executed successfully."""
    try:
        result = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False
    

def check_llm_env_aliases() -> tuple[bool, str]:
    """Warn when only MCP-prefixed provider vars are set but standard aliases are missing."""
    values = _load_env_values()
    if not values:
        return True, "skipped (.env not found)"

    provider = values.get("MCP_LLM_PROVIDER", "").strip().lower()
    alias_map = {
        "openai": ("MCP_LLM_OPENAI_API_KEY", "OPENAI_API_KEY"),
        "minimax": ("MCP_LLM_MINIMAX_API_KEY", "MINIMAX_API_KEY"),
        "google": ("MCP_LLM_GOOGLE_API_KEY", "GOOGLE_API_KEY"),
        "anthropic": ("MCP_LLM_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
        "azure_openai": ("MCP_LLM_AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_KEY"),
        "deepseek": ("MCP_LLM_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"),
        "openrouter": ("MCP_LLM_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"),
    }
    warnings: list[str] = []

    pair = alias_map.get(provider)
    if pair:
        mcp_key, standard_key = pair
        if values.get(mcp_key) and not values.get(standard_key):
            warnings.append(f"{standard_key} is empty while {mcp_key} is set")

    if provider in {"ollama", "openai", "minimax", "deepseek", "openrouter"}:
        if values.get("MCP_LLM_MODEL_NAME") and not values.get("OPENAI_MODEL"):
            warnings.append("OPENAI_MODEL is empty; OpenAI-compatible helpers will fall back to defaults")
        if values.get("MCP_LLM_BASE_URL") and not values.get("OPENAI_API_BASE"):
            warnings.append("OPENAI_API_BASE is empty; memory/task helpers may not target the same endpoint")

    if warnings:
        return True, "WARN: " + "; ".join(warnings)
    return True, "LLM env aliases OK"


def check_feature_env() -> tuple[bool, str]:
    """Warn about common partial feature configuration in .env."""
    values = _load_env_values()
    if not values:
        return True, "skipped (.env not found)"

    warnings: list[str] = []

    if values.get("TELEGRAM_BOT_TOKEN") and not _is_truthy(values.get("TELEGRAM_ALLOW_ALL")) and not values.get("TELEGRAM_ADMIN_IDS"):
        warnings.append("TELEGRAM_BOT_TOKEN is set but TELEGRAM_ADMIN_IDS/TELEGRAM_ALLOW_ALL is not configured")

    spotify_fields = ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REDIRECT_URI")
    if any(values.get(field) for field in spotify_fields):
        missing = [field for field in spotify_fields if not values.get(field)]
        if missing:
            warnings.append("Spotify is partially configured; missing " + ", ".join(missing))

    google_drive_fields = (
        "GOOGLE_DRIVE_PROJECT_ID",
        "GOOGLE_DRIVE_PRIVATE_KEY_ID",
        "GOOGLE_DRIVE_PRIVATE_KEY",
        "GOOGLE_DRIVE_CLIENT_EMAIL",
    )
    if any(values.get(field) for field in google_drive_fields + ("GOOGLE_DRIVE_FOLDER_ID",)):
        missing = [field for field in google_drive_fields if not values.get(field)]
        if missing:
            warnings.append("Google Drive upload is partially configured; missing " + ", ".join(missing))

    if _is_truthy(values.get("EMBEDDED_KITTEN_TTS_ENABLED")) and not _command_available(["espeak-ng", "--version"]):
        warnings.append("EMBEDDED_KITTEN_TTS_ENABLED=true but espeak-ng is not available on PATH")

    jwt_secret = values.get("JWT_SECRET", "").strip()
    if not jwt_secret or jwt_secret == "change-this-secret-in-production":
        warnings.append("JWT_SECRET is still using the default value")

    if warnings:
        return True, "WARN: " + "; ".join(warnings)
    return True, "Feature env sanity OK"


def check_mcp_server_cli() -> tuple[bool, str]:
    """Verify mcp-server-browser-use CLI runs (via uv in mcp-browser-use). Non-blocking if checkout is incomplete."""
    if not MCP_BROWSER_USE_DIR.is_dir():
        return False, "mcp-browser-use directory not found"
    env = _build_browser_use_env()
    commands = [["uv", "run", "mcp-server-browser-use", "--help"]]
    fallback_python = MCP_BROWSER_USE_DIR / ".venv" / "Scripts" / "python.exe"
    if fallback_python.exists():
        commands.append([str(fallback_python), "-m", "mcp_server_browser_use.cli", "--help"])
    try:
        err = "exit non-zero"
        for command in commands:
            result = subprocess.run(
                command,
                cwd=str(MCP_BROWSER_USE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                env=env,
            )
            if result.returncode == 0:
                return True, "mcp-server-browser-use CLI OK"
            err = result.stderr.strip() or result.stdout.strip() or "exit non-zero"
        if "ModuleNotFoundError" in err or "No module named" in err:
            return True, (
                "skipped (mcp-browser-use checkout incomplete; update the local checkout or "
                "clone https://github.com/andyjm2k/mcp-browser-use.git into mcp-browser-use/)"
            )
        return False, err
    except FileNotFoundError:
        return True, "skipped (uv not found in PATH)"
    except Exception as e:
        return True, f"skipped ({e})"


def check_codex_cli() -> tuple[bool, str]:
    """Verify codex CLI is available (optional)."""
    try:
        result = subprocess.run(
            ["codex", "--version"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            return True, (result.stdout.strip() or "codex CLI OK")
        return True, "skipped (codex CLI not available)"
    except FileNotFoundError:
        return True, "skipped (codex CLI not found)"
    except Exception as e:
        return True, f"skipped ({e})"


def check_telegram_security_env() -> tuple[bool, str]:
    """Best-effort security sanity check for Telegram tools configuration."""
    values = _load_env_values()
    if not values:
        return True, "skipped (.env not found)"

    tools_enabled = _is_truthy(values.get("TELEGRAM_TOOLS_ENABLED"))
    has_secret = bool(values.get("TELEGRAM_SECRET", "").strip())
    if tools_enabled and not has_secret:
        return True, "WARN: TELEGRAM_TOOLS_ENABLED=true but TELEGRAM_SECRET is empty (recommended for authenticated Telegram file attachments)."
    return True, "Telegram security env OK"


def main() -> int:
    """Run all verification checks. Use venv Python if running from installer."""
    python_exe = os.environ.get("CATBOT_VERIFY_PYTHON") or sys.executable
    checks = [
        ("Core (FastAPI, uvicorn, httpx, pydantic)", lambda: check_core(python_exe)),
        ("AutoGen", lambda: check_autogen(python_exe)),
        ("MCP", lambda: check_mcp(python_exe)),
        ("Playwright", lambda: check_playwright(python_exe)),
        ("KittenTTS runtime", lambda: check_kitten_tts(python_exe)),
        ("Runtime integrations", lambda: check_runtime_optional_deps(python_exe)),
        ("mcp-server-browser-use CLI", check_mcp_server_cli),
        ("Codex CLI (optional)", check_codex_cli),
        ("LLM env aliases (optional)", check_llm_env_aliases),
        ("Feature env sanity (optional)", check_feature_env),
        ("Telegram security env (optional)", check_telegram_security_env),
    ]
    failed = []
    for name, check_fn in checks:
        ok, msg = check_fn()
        if ok:
            print(f"  OK  {name}: {msg}")
        else:
            print(f"  FAIL {name}: {msg}")
            failed.append((name, msg))
    if failed:
        print("\nVerification failed. Fix the above before starting CATBot.")
        return 1
    print("\nAll checks passed. CATBot stack is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
