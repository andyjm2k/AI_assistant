#!/usr/bin/env python3
"""
Interactive terminal wizard to collect CATBot configuration and write .env.
Run from project root (or pass --project-root). Gathers LLM provider, API keys,
Brave/News, and optional Telegram so you rarely need to edit .env manually.
"""
import os
import re
import sys
from pathlib import Path

# Project root = parent of scripts directory
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_ROOT = SCRIPT_DIR.parent
# Ensure project root is on path so "from scripts.xxx" works when run as scripts/install_wizard.py
if str(DEFAULT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_PROJECT_ROOT))

# LLM providers we prompt for (key in .env, display name) (key in .env, display name)
LLM_PROVIDERS = [
    ("ollama", "Ollama (local)"),
    ("openai", "OpenAI (GPT)"),
    ("minimax", "Minimax (OpenAI-compatible)"),
    ("google", "Google (Gemini)"),
    ("anthropic", "Anthropic (Claude)"),
    ("azure_openai", "Azure OpenAI"),
    ("deepseek", "DeepSeek"),
    ("openrouter", "OpenRouter"),
    ("other", "Other (edit .env later)"),
]

# Default model names per provider (user can override)
DEFAULT_MODELS = {
    "ollama": "llama3.2",
    "openai": "gpt-4o-mini",
    "minimax": "MiniMax-M2.5",
    "google": "gemini-3-flash-preview",
    "anthropic": "claude-3-5-sonnet-20241022",
    "azure_openai": "gpt-4o",
    "deepseek": "deepseek-chat",
    "openrouter": "openai/gpt-4o-mini",
}

# Env var name for each provider's API key (None = no key needed, e.g. ollama)
PROVIDER_API_KEY_VAR = {
    "ollama": None,
    "openai": "MCP_LLM_OPENAI_API_KEY",
    "minimax": "MCP_LLM_MINIMAX_API_KEY",
    "google": "MCP_LLM_GOOGLE_API_KEY",
    "anthropic": "MCP_LLM_ANTHROPIC_API_KEY",
    "azure_openai": "MCP_LLM_AZURE_OPENAI_API_KEY",
    "deepseek": "MCP_LLM_DEEPSEEK_API_KEY",
    "openrouter": "MCP_LLM_OPENROUTER_API_KEY",
}

STANDARD_PROVIDER_API_KEY_VAR = {
    "ollama": None,
    "openai": "OPENAI_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "google": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "azure_openai": "AZURE_OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

OPENAI_COMPATIBLE_ALIAS_PROVIDERS = frozenset({
    "ollama",
    "openai",
    "minimax",
    "deepseek",
    "openrouter",
})

DEFAULT_OPENAI_COMPATIBLE_BASE_URLS = {
    "ollama": "http://localhost:11434/v1",
    "openai": "https://api.openai.com/v1",
    "minimax": "https://api.minimax.io/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


def _prompt(prompt: str, default: str = "", secret: bool = False) -> str:
    """Read one line from stdin; return stripped value or default. Flushes stdout so prompts and input are visible when run from batch/PowerShell."""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    # Flush so the prompt appears before we read (fixes buffering when run from install.bat / PowerShell)
    sys.stdout.flush()
    sys.stderr.flush()
    if secret:
        # On Windows, getpass can fail to capture when run from PowerShell/batch; use input() so we always capture
        if os.name == "nt":
            value = input(prompt)
        else:
            try:
                import getpass
                value = getpass.getpass(prompt)
            except Exception:
                value = input(prompt)
    else:
        value = input(prompt)
    sys.stdout.flush()
    value = value.strip()
    return value if value else default


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    """Ask yes/no; return True for yes, False for no."""
    d = "Y/n" if default else "y/N"
    raw = _prompt(f"{prompt} ({d})", "y" if default else "n").lower()
    if not raw:
        return default
    return raw in ("y", "yes", "1", "true")


def _set_key_in_env_content(content: str, key: str, value: str) -> str:
    """Replace or add KEY=value in .env-style content. Preserves comments."""
    if not value and value is not None:
        return content
    line_match = re.compile(r"^(\s*)" + re.escape(key) + r"\s*=[^\n]*", re.MULTILINE)
    new_line = f"{key}={value}\n"
    if line_match.search(content):
        return line_match.sub(new_line, content, count=1)
    # Append before the first "# ===" or at end
    if "# ===" in content:
        insert_pos = content.find("# ===")
        return content[:insert_pos] + new_line + content[insert_pos:]
    return content.rstrip() + "\n" + new_line


def _has_key_in_env_content(content: str, key: str) -> bool:
    """Return True if KEY= exists in .env-style content."""
    return bool(re.search(r"^\s*" + re.escape(key) + r"\s*=", content, flags=re.MULTILINE))


def _set_key_if_missing(content: str, key: str, value: str) -> str:
    """Set KEY=value only if key is not present."""
    if _has_key_in_env_content(content, key):
        return content
    return _set_key_in_env_content(content, key, value)


def _load_template_with_path_substitution(project_root: Path) -> str:
    """Load .env.example or config/mcp_config.env.example and substitute project root in paths."""
    from scripts.setup_env_and_dirs import (
        EXAMPLE_PREFIX_WIN,
        EXAMPLE_PREFIX_POSIX,
        PATH_ENV_VARS,
        _normalize_path_for_env,
    )
    env_example = project_root / ".env.example"
    if not env_example.exists():
        env_example = project_root / "config" / "mcp_config.env.example"
    if not env_example.exists():
        return ""
    content = env_example.read_text(encoding="utf-8", errors="replace")
    on_windows = os.name == "nt"
    new_prefix = _normalize_path_for_env(project_root, on_windows)
    lines = []
    for line in content.splitlines(keepends=True) if "\n" in content else [content]:
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key in PATH_ENV_VARS and value:
                for old in (EXAMPLE_PREFIX_WIN, EXAMPLE_PREFIX_POSIX):
                    if value.startswith(old):
                        suffix = value[len(old):].lstrip("\\/")
                        value = new_prefix + (os.sep if on_windows else "/") + suffix.replace("/", os.sep)
                        line = f"{key}={value}\n"
                        break
        lines.append(line)
    return "".join(lines)


def _normalize_base_url(value: str) -> str:
    """Normalize a base URL by trimming whitespace and trailing slashes."""
    return value.strip().rstrip("/")


def _derive_openai_compatible_base_url(provider: str, endpoint: str) -> str:
    """Return an OpenAI-compatible base URL for modules that still read OPENAI_* vars."""
    normalized_endpoint = _normalize_base_url(endpoint)
    if not normalized_endpoint:
        normalized_endpoint = DEFAULT_OPENAI_COMPATIBLE_BASE_URLS.get(provider, "")
    if not normalized_endpoint:
        return ""
    if provider == "ollama" and not normalized_endpoint.endswith("/v1"):
        return normalized_endpoint + "/v1"
    return normalized_endpoint


def run_wizard(project_root: Path, env_path: Path) -> bool:
    """
    Run interactive prompts and write .env. Returns True if .env was written.
    """
    print("\n--- CATBot configuration wizard ---\n")
    print("Answer the questions below. Press Enter to accept [defaults]. You can edit .env later.\n")
    if os.name == "nt":
        print("(On Windows, API keys will be visible as you type so they are captured correctly.)\n")

    # 1. LLM provider
    print("1) LLM provider (for chat and tools):")
    for i, (key, label) in enumerate(LLM_PROVIDERS, 1):
        print(f"   {i}. {label}")
    choice = _prompt("Number or name", "1")
    provider = "ollama"
    for i, (key, label) in enumerate(LLM_PROVIDERS, 1):
        if choice == str(i) or choice.lower() == key:
            provider = key
            break
    if provider == "other":
        provider = _prompt("Provider key for .env (e.g. openai, google)", "openai")

    # 2. Model name
    default_model = DEFAULT_MODELS.get(provider, "gpt-4o-mini")
    model = _prompt("2) Model name", default_model)

    # 3. API key for chosen provider (skip for ollama unless they want to set base URL)
    api_key = ""
    azure_api_version = ""
    if provider == "ollama":
        endpoint = _prompt("3) Ollama base URL (leave blank for localhost:11434)", "http://localhost:11434")
    elif provider == "minimax":
        endpoint = _prompt("3) Minimax base URL", "https://api.minimax.io/v1")
        api_key = _prompt("4) API key for minimax", "", secret=True)
        if not api_key:
            print("   (You can add it later in .env)")
    elif provider == "openrouter":
        endpoint = _prompt("3) OpenRouter base URL", "https://openrouter.ai/api/v1")
        api_key = _prompt("4) API key for openrouter", "", secret=True)
        if not api_key:
            print("   (You can add it later in .env)")
    elif provider == "azure_openai":
        endpoint = _prompt("3) Azure OpenAI endpoint", "https://your-resource.openai.azure.com")
        azure_api_version = _prompt("4) Azure OpenAI API version", "2024-02-01")
        api_key = _prompt("5) API key for azure_openai", "", secret=True)
        if not api_key:
            print("   (You can add it later in .env)")
    elif provider == "deepseek":
        endpoint = _prompt("3) DeepSeek base URL", "https://api.deepseek.com/v1")
        api_key = _prompt("4) API key for deepseek", "", secret=True)
        if not api_key:
            print("   (You can add it later in .env)")
    elif provider == "openai":
        endpoint = _prompt("3) OpenAI base URL", "https://api.openai.com/v1")
        api_key = _prompt("4) API key for openai", "", secret=True)
        if not api_key:
            print("   (You can add it later in .env)")
    else:
        endpoint = ""
        api_key = _prompt("3) API key for " + provider, "", secret=True)
        if not api_key:
            print("   (You can add it later in .env)")

    # 4. Brave Search (web search)
    brave = _prompt("5) Brave Search API key (optional; press Enter to skip)", "", secret=True)
    news = _prompt("6) News API key (optional; press Enter to skip)", "", secret=True)

    # 5. Codex CLI tool
    use_codex = _prompt_yes_no("7) Enable Codex CLI tool?", True)
    codex_path = ""
    codex_search = True
    codex_timeout = "1800"
    if use_codex:
        codex_path = _prompt("   Codex CLI path (default: codex)", "codex")
        codex_search = _prompt_yes_no("   Enable Codex web search?", True)
        codex_timeout = _prompt("   Codex timeout seconds", "1800")

    # 6. Telegram
    use_telegram = _prompt_yes_no("8) Enable Telegram bot?", False)
    telegram_token = ""
    telegram_admins = ""
    telegram_allow_all = "false"
    telegram_tools_enabled = "false"
    telegram_secret = ""
    if use_telegram:
        telegram_token = _prompt("   Telegram bot token (from BotFather)", "", secret=True)
        if telegram_token:
            allow_all = _prompt_yes_no("   Allow all users (not just admin IDs)?", False)
            if allow_all:
                telegram_allow_all = "true"
            else:
                telegram_admins = _prompt("   Admin Telegram user ID(s), comma-separated", "")
            enable_tools = _prompt_yes_no("   Enable Telegram tools on proxy?", False)
            telegram_tools_enabled = "true" if enable_tools else "false"
            if enable_tools:
                print("   Telegram file attachments (sendTelegramFile) require authenticated proxy requests.")
                print("   listFiles supports path/recursive for scratch sub-directory listings.")
            set_secret = _prompt_yes_no(
                "   Set TELEGRAM_SECRET for bot-to-proxy authentication (recommended)?",
                True,
            )
            if set_secret:
                telegram_secret = _prompt("   TELEGRAM_SECRET value (same on bot and proxy)", "", secret=True)

    # 7. Web UI TTS defaults (optional)
    tts_endpoint = _prompt("9) Default TTS endpoint for web UI (optional; press Enter to skip)", "")
    tts_model = _prompt("10) Default TTS model for web UI (optional; used as UI fallback on voice-fetch failure)", "")
    tts_voice = _prompt("11) Default TTS voice for web UI (optional; used as UI fallback on voice-fetch failure)", "")

    # 8. HTTPS certificate hostname (for LAN access; used by https_server and proxy_server)
    https_hostname = _prompt("12) HTTPS certificate hostname (for LAN access; used in cert generation and URLs)", "anton.local")
    if not https_hostname.strip():
        https_hostname = "anton.local"
    else:
        https_hostname = https_hostname.strip()

    # Use existing .env or template with path substitution
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8", errors="replace")
    else:
        content = _load_template_with_path_substitution(project_root)
        if not content:
            content = "# CATBot .env (generated by wizard)\n\n"

    # Apply wizard values
    content = _set_key_in_env_content(content, "MCP_LLM_PROVIDER", provider)
    content = _set_key_in_env_content(content, "MCP_LLM_MODEL_NAME", model)
    if endpoint:
        content = _set_key_in_env_content(content, "MCP_LLM_BASE_URL", endpoint)
    if api_key:
        key_var = PROVIDER_API_KEY_VAR.get(provider)
        if key_var:
            content = _set_key_in_env_content(content, key_var, api_key)
        standard_key_var = STANDARD_PROVIDER_API_KEY_VAR.get(provider)
        if standard_key_var:
            content = _set_key_in_env_content(content, standard_key_var, api_key)
    content = _set_key_in_env_content(content, "MCP_MODEL_PROVIDER", provider)
    content = _set_key_in_env_content(content, "MCP_MODEL_NAME", model)
    if endpoint:
        content = _set_key_in_env_content(content, "MCP_MODEL_BASE_URL", endpoint)
    if provider == "azure_openai":
        if endpoint:
            content = _set_key_in_env_content(content, "MCP_LLM_AZURE_ENDPOINT", endpoint)
        content = _set_key_in_env_content(content, "MCP_LLM_AZURE_API_VERSION", azure_api_version or "2024-02-01")
    openai_compat_base_url = _derive_openai_compatible_base_url(provider, endpoint)
    if provider in OPENAI_COMPATIBLE_ALIAS_PROVIDERS:
        content = _set_key_in_env_content(content, "OPENAI_MODEL", model)
        if openai_compat_base_url:
            content = _set_key_in_env_content(content, "OPENAI_API_BASE", openai_compat_base_url)
        if api_key:
            content = _set_key_in_env_content(content, "OPENAI_API_KEY", api_key)
    if provider == "openrouter":
        content = _set_key_in_env_content(
            content,
            "OPENROUTER_API_BASE",
            openai_compat_base_url or "https://openrouter.ai/api/v1",
        )
    if brave:
        content = _set_key_in_env_content(content, "BRAVE_API_KEY", brave)
    if news:
        content = _set_key_in_env_content(content, "NEWS_API_KEY", news)
    content = _set_key_in_env_content(content, "CODEX_ENABLED", "true" if use_codex else "false")
    if use_codex:
        content = _set_key_in_env_content(content, "CODEX_CLI_PATH", codex_path or "codex")
        content = _set_key_in_env_content(content, "CODEX_ENABLE_SEARCH", "true" if codex_search else "false")
        content = _set_key_in_env_content(content, "CODEX_TIMEOUT_SECONDS", codex_timeout or "1800")
        content = _set_key_in_env_content(content, "CODEX_SANDBOX_MODE", "workspace-write")
        content = _set_key_in_env_content(content, "CODEX_APPROVAL_POLICY", "never")
        content = _set_key_in_env_content(content, "CODEX_DISABLE_ALT_SCREEN", "true")
    # Weather tool defaults (BOM): no API key required; keep configurable base URL/timeout in .env
    content = _set_key_in_env_content(content, "BOM_API_BASE_URL", "https://api.weather.bom.gov.au/v1")
    content = _set_key_in_env_content(content, "BOM_API_TIMEOUT_SECONDS", "12")
    # Context window controls (defaults)
    content = _set_key_in_env_content(content, "MAX_TOKEN_LIMIT", "256000")
    content = _set_key_in_env_content(content, "TOKEN_ESTIMATE_CHARS_PER_TOKEN", "4")
    # Large payload fallback (disabled by default)
    content = _set_key_in_env_content(content, "LARGE_PAYLOAD_MODEL", "")
    content = _set_key_in_env_content(content, "LARGE_PAYLOAD_ENDPOINT", "")
    if use_telegram and telegram_token:
        content = _set_key_in_env_content(content, "TELEGRAM_BOT_TOKEN", telegram_token)
        content = _set_key_in_env_content(content, "TELEGRAM_ALLOW_ALL", telegram_allow_all)
        if telegram_admins:
            content = _set_key_in_env_content(content, "TELEGRAM_ADMIN_IDS", telegram_admins)
        content = _set_key_in_env_content(content, "TELEGRAM_TOOLS_ENABLED", telegram_tools_enabled)
        if telegram_secret:
            content = _set_key_in_env_content(content, "TELEGRAM_SECRET", telegram_secret)
    if tts_endpoint:
        content = _set_key_in_env_content(content, "TTS_ENDPOINT", tts_endpoint)
    if tts_model:
        content = _set_key_in_env_content(content, "TTS_MODEL", tts_model)
    if tts_voice:
        content = _set_key_in_env_content(content, "TTS_VOICE", tts_voice)
    # Embedded/local TTS latency defaults (set only if missing to avoid overwriting custom tuning)
    content = _set_key_if_missing(content, "EMBEDDED_KITTEN_SAMPLE_RATE", "24000")
    content = _set_key_if_missing(content, "EMBEDDED_KITTEN_STREAM_CHUNK_BYTES", "4096")
    content = _set_key_if_missing(content, "EMBEDDED_KITTEN_MAX_INPUT_CHARS", "220")
    content = _set_key_if_missing(content, "EMBEDDED_KITTEN_CHUNK_SILENCE_MS", "80")
    content = _set_key_if_missing(content, "TTS_PROXY_TIMEOUT_SECONDS", "180")
    # Always write HTTPS hostname so https_server and proxy_server use it for cert discovery
    content = _set_key_in_env_content(content, "HTTPS_CERT_HOSTNAME", https_hostname)

    env_path.write_text(content, encoding="utf-8")
    print("\nWrote", str(env_path))
    print("   For HTTPS from other devices, run: mkcert", https_hostname, "localhost 127.0.0.1 <your-ip>")
    print("   Review optional .env sections if you plan to use Whisper, Spotify, Google Drive, GitHub, image generation, or memory overrides.")
    return True


def main() -> int:
    """Entry point: ensure dirs and .env template, then run wizard."""
    import argparse
    from scripts.setup_env_and_dirs import create_dirs, setup_env

    parser = argparse.ArgumentParser(description="CATBot configuration wizard (interactive .env setup)")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT, help="Project root")
    parser.add_argument("--skip-wizard", action="store_true", help="Only create dirs and template .env; do not prompt")
    args = parser.parse_args()
    root = args.project_root.resolve()
    env_file = root / ".env"
    template = root / ".env.example"
    if not template.exists():
        template = root / "config" / "mcp_config.env.example"

    if not root.is_dir():
        print(f"Error: project root is not a directory: {root}", file=sys.stderr)
        return 1

    create_dirs(root)
    if not env_file.exists() and template.exists():
        created, _ = setup_env(root, env_file, template, force=False)
        if created:
            print("Created .env from template. Running wizard to fill in your values.\n")

    if args.skip_wizard:
        print("Skipping wizard (--skip-wizard). Edit .env manually.")
        return 0

    # Only run wizard if stdin looks interactive (TTY)
    if not sys.stdin.isatty():
        print("Not a terminal; skipping interactive wizard. Edit .env manually or run: python scripts/install_wizard.py")
        return 0

    run_wizard(root, env_file)
    print("\nDone. Start CATBot with start.bat or: python scripts/start_all.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
