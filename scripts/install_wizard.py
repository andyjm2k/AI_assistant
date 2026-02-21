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

# LLM providers we prompt for (key in .env, display name)
LLM_PROVIDERS = [
    ("ollama", "Ollama (local)"),
    ("openai", "OpenAI (GPT)"),
    ("google", "Google (Gemini)"),
    ("anthropic", "Anthropic (Claude)"),
    ("azure_openai", "Azure OpenAI"),
    ("deepseek", "DeepSeek"),
    ("mistral", "Mistral"),
    ("openrouter", "OpenRouter"),
    ("other", "Other (edit .env later)"),
]

# Default model names per provider (user can override)
DEFAULT_MODELS = {
    "ollama": "llama3.2",
    "openai": "gpt-4o-mini",
    "google": "gemini-2.0-flash-exp",
    "anthropic": "claude-3-5-sonnet-20241022",
    "azure_openai": "gpt-4o",
    "deepseek": "deepseek-chat",
    "mistral": "mistral-large-latest",
    "openrouter": "openai/gpt-4o-mini",
}

# Env var name for each provider's API key (None = no key needed, e.g. ollama)
PROVIDER_API_KEY_VAR = {
    "ollama": None,
    "openai": "MCP_LLM_OPENAI_API_KEY",
    "google": "MCP_LLM_GOOGLE_API_KEY",
    "anthropic": "MCP_LLM_ANTHROPIC_API_KEY",
    "azure_openai": "MCP_LLM_AZURE_OPENAI_API_KEY",
    "deepseek": "MCP_LLM_DEEPSEEK_API_KEY",
    "mistral": "MCP_LLM_MISTRAL_API_KEY",
    "openrouter": "MCP_LLM_OPENROUTER_API_KEY",
}


def _prompt(prompt: str, default: str = "", secret: bool = False) -> str:
    """Read one line from stdin; return stripped value or default."""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    if secret:
        try:
            import getpass
            value = getpass.getpass(prompt)
        except Exception:
            value = input(prompt)
    else:
        value = input(prompt)
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


def run_wizard(project_root: Path, env_path: Path) -> bool:
    """
    Run interactive prompts and write .env. Returns True if .env was written.
    """
    print("\n--- CATBot configuration wizard ---\n")
    print("Answer the questions below. Press Enter to accept [defaults]. You can edit .env later.\n")

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
    if provider == "ollama":
        endpoint = _prompt("3) Ollama endpoint (leave blank for localhost:11434)", "http://localhost:11434")
    else:
        endpoint = ""
        api_key = _prompt("3) API key for " + provider, "", secret=True)
        if not api_key:
            print("   (You can add it later in .env)")

    # 4. Brave Search (web search)
    brave = _prompt("4) Brave Search API key (optional; press Enter to skip)", "", secret=True)
    news = _prompt("5) News API key (optional; press Enter to skip)", "", secret=True)

    # 5. Telegram
    use_telegram = _prompt_yes_no("6) Enable Telegram bot?", False)
    telegram_token = ""
    telegram_admins = ""
    telegram_allow_all = "false"
    if use_telegram:
        telegram_token = _prompt("   Telegram bot token (from BotFather)", "", secret=True)
        if telegram_token:
            allow_all = _prompt_yes_no("   Allow all users (not just admin IDs)?", False)
            if allow_all:
                telegram_allow_all = "true"
            else:
                telegram_admins = _prompt("   Admin Telegram user ID(s), comma-separated", "")

    # 6. HTTPS certificate hostname (for LAN access; used by https_server and proxy_server)
    https_hostname = _prompt("7) HTTPS certificate hostname (for LAN access; used in cert generation and URLs)", "anton.local")
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
        content = _set_key_in_env_content(content, "MCP_LLM_OLLAMA_ENDPOINT", endpoint)
    if api_key:
        key_var = PROVIDER_API_KEY_VAR.get(provider)
        if key_var:
            content = _set_key_in_env_content(content, key_var, api_key)
    if brave:
        content = _set_key_in_env_content(content, "BRAVE_API_KEY", brave)
    if news:
        content = _set_key_in_env_content(content, "NEWS_API_KEY", news)
    if use_telegram and telegram_token:
        content = _set_key_in_env_content(content, "TELEGRAM_BOT_TOKEN", telegram_token)
        content = _set_key_in_env_content(content, "TELEGRAM_ALLOW_ALL", telegram_allow_all)
        if telegram_admins:
            content = _set_key_in_env_content(content, "TELEGRAM_ADMIN_IDS", telegram_admins)
    # Always write HTTPS hostname so https_server and proxy_server use it for cert discovery
    content = _set_key_in_env_content(content, "HTTPS_CERT_HOSTNAME", https_hostname)

    env_path.write_text(content, encoding="utf-8")
    print("\nWrote", str(env_path))
    print("   For HTTPS from other devices, run: mkcert", https_hostname, "localhost 127.0.0.1 <your-ip>")
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
