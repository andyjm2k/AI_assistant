#!/usr/bin/env python3
"""Telegram bot integration for the CATBot AI assistant.

This bot connects Telegram users to the CATBot backend by forwarding
messages to the FastAPI proxy server. The proxy server then resolves
requests using OpenAI (or any compatible model endpoint configured on
the server).

Environment variables:
    TELEGRAM_BOT_TOKEN: Telegram bot token obtained from @BotFather (required)
    TELEGRAM_ADMIN_IDS: Comma separated list of Telegram user IDs that are allowed to chat
    TELEGRAM_ALLOW_ALL: Set to "true" to allow all Telegram users (optional)
    TELEGRAM_BACKEND_URL: Base URL of the CATBot proxy server (default: http://localhost:8002)
    TELEGRAM_CHAT_ENDPOINT: Relative or absolute URL to the chat endpoint (default: /v1/telegram/chat)
    TELEGRAM_CHAT_TIMEOUT: Timeout for chat requests to backend in seconds (default: 30)
    TELEGRAM_BACKEND_VERIFY_SSL: Set to "false" to skip SSL verification for backend (e.g. self-signed cert)
    TELEGRAM_BOT_SYSTEM_PROMPT: Optional system prompt override passed to backend
    TELEGRAM_CHAT_MODEL: Optional model override passed to backend

The bot implements the following commands:
    /start  - greet the user and register the conversation
    /help   - display available commands
    /status - report backend status and message counts
    /clear  - clear the conversation history on the backend

Text messages are proxied to the backend chat endpoint which maintains
conversation history and calls the LLM provider.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, Optional

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def _parse_admin_ids() -> set:
    """Parse TELEGRAM_ADMIN_IDS defensively; skip non-numeric values and log warnings."""
    admin_ids: set = set()
    raw = os.getenv("TELEGRAM_ADMIN_IDS", "")
    for part in raw.split(","):
        s = part.strip()
        if not s:
            continue
        try:
            admin_ids.add(int(s))
        except ValueError:
            logger.warning("Skipping invalid TELEGRAM_ADMIN_IDS entry (not numeric): %r", s)
    return admin_ids


ADMIN_IDS = _parse_admin_ids()
ALLOW_ALL_USERS = os.getenv("TELEGRAM_ALLOW_ALL", "false").lower() == "true"
BACKEND_BASE_URL = os.getenv("TELEGRAM_BACKEND_URL", os.getenv("BACKEND_URL", "http://localhost:8002"))
CHAT_ENDPOINT = os.getenv("TELEGRAM_CHAT_ENDPOINT", "/v1/telegram/chat")


def _parse_chat_timeout() -> float:
    """Parse TELEGRAM_CHAT_TIMEOUT with default 30 on invalid value."""
    try:
        return float(os.getenv("TELEGRAM_CHAT_TIMEOUT", "30"))
    except ValueError:
        logger.warning("Invalid TELEGRAM_CHAT_TIMEOUT; using default 30")
        return 30.0


CHAT_TIMEOUT = _parse_chat_timeout()
SYSTEM_PROMPT_OVERRIDE = os.getenv("TELEGRAM_BOT_SYSTEM_PROMPT")
MODEL_OVERRIDE = os.getenv("TELEGRAM_CHAT_MODEL")
# Optional shared secret for bot-to-proxy auth when proxy is reachable beyond localhost
TELEGRAM_SECRET = os.getenv("TELEGRAM_SECRET")
# Set to "false" to disable SSL verification for backend requests (e.g. self-signed cert at https://anton.local:8002)
BACKEND_VERIFY_SSL = os.getenv("TELEGRAM_BACKEND_VERIFY_SSL", "true").lower() != "false"

# Track message counts for /status reporting
message_counts: Dict[int, int] = {}


def _backend_headers() -> Dict[str, str]:
    """Return optional auth headers for backend requests when TELEGRAM_SECRET is set."""
    if not TELEGRAM_SECRET:
        return {}
    return {"X-Telegram-Secret": TELEGRAM_SECRET}


def is_authorized(user_id: int) -> bool:
    """Return True if the user is allowed to interact with the bot."""

    if ALLOW_ALL_USERS:
        return True

    if not ADMIN_IDS:
        logger.warning(
            "No TELEGRAM_ADMIN_IDS configured. Set TELEGRAM_ALLOW_ALL=true to explicitly opt-in to public access."
        )
        return False

    return user_id in ADMIN_IDS


def build_chat_url() -> str:
    """Resolve the chat endpoint from environment configuration."""

    if CHAT_ENDPOINT.startswith("http://") or CHAT_ENDPOINT.startswith("https://"):
        return CHAT_ENDPOINT
    return f"{BACKEND_BASE_URL.rstrip('/')}{CHAT_ENDPOINT}"


async def call_backend_chat(user_id: int, message: str) -> str:
    """Send the user message to the backend and return the assistant reply."""

    payload = {
        "conversation_id": str(user_id),
        "user_id": str(user_id),
        "message": message,
    }

    if SYSTEM_PROMPT_OVERRIDE:
        payload["system_prompt"] = SYSTEM_PROMPT_OVERRIDE
    if MODEL_OVERRIDE:
        payload["model"] = MODEL_OVERRIDE

    url = build_chat_url()
    logger.debug("Sending chat payload to %s", url)
    headers = _backend_headers()

    try:
        async with httpx.AsyncClient(timeout=CHAT_TIMEOUT, verify=BACKEND_VERIFY_SSL) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        logger.error("Backend request error: %s", exc)
        raise RuntimeError("Failed to reach CATBot backend. Please check the server logs.") from exc

    if response.status_code != 200:
        logger.error("Backend returned %s: %s", response.status_code, response.text)
        try:
            error_payload = response.json()
            message_text = error_payload.get("detail") or error_payload.get("message")
        except ValueError:
            message_text = response.text
        raise RuntimeError(message_text or "CATBot backend returned an unexpected error.")

    data = response.json()
    reply = data.get("reply") or data.get("response") or data.get("text")
    if not reply:
        raise RuntimeError("CATBot backend did not return a response message.")

    # Update message counts for status command
    message_counts[user_id] = message_counts.get(user_id, 0) + 1

    return reply


async def clear_backend_history(user_id: int) -> bool:
    """Request the backend to clear conversation history for a user."""

    url = build_chat_url()
    delete_url = url.rstrip("/") + f"/{user_id}"
    headers = _backend_headers()

    try:
        async with httpx.AsyncClient(timeout=CHAT_TIMEOUT, verify=BACKEND_VERIFY_SSL) as client:
            response = await client.delete(delete_url, headers=headers)
    except httpx.RequestError as exc:
        logger.error("Failed clearing backend conversation: %s", exc)
        raise RuntimeError("Unable to reach CATBot backend to clear the conversation.") from exc

    if response.status_code not in (200, 204):
        logger.error("Backend clear failed (%s): %s", response.status_code, response.text)
        return False

    message_counts.pop(user_id, None)
    return True


async def check_backend_health() -> tuple[str, Optional[float]]:
    """Return backend health status string and latency in seconds."""

    health_url = f"{BACKEND_BASE_URL.rstrip('/')}/health"
    headers = _backend_headers()
    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        async with httpx.AsyncClient(timeout=CHAT_TIMEOUT, verify=BACKEND_VERIFY_SSL) as client:
            response = await client.get(health_url, headers=headers)
    except httpx.RequestError:
        logger.warning("CATBot backend health check failed", exc_info=True)
        return "❌ Offline", None

    latency = loop.time() - start
    if response.status_code == 200:
        return "✅ Online", latency

    return f"⚠️ {response.status_code}", latency


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""

    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or update.effective_user.username or "there"

    if not is_authorized(user_id):
        await update.message.reply_text(
            "⚠️ This bot is currently restricted. Please contact the administrator to request access."
        )
        logger.warning("Unauthorized /start attempt from user %s", user_id)
        return

    message_counts.setdefault(user_id, 0)

    greeting = (
        f"👋 Hi {user_name}! I'm CATBot, your AI assistant.\n\n"
        "Send me a message and I'll reply using the full CATBot stack.\n"
        "Use /help to see everything I can do."
    )
    await update.message.reply_text(greeting)
    logger.info("Authorized user %s started the bot", user_id)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""

    if not update.message:
        return

    help_text = (
        "📚 *CATBot Telegram Bot Commands*\n\n"
        "*/start* – initialize the chat\n"
        "*/help* – display this help message\n"
        "*/status* – check backend connectivity and usage\n"
        "*/clear* – reset our conversation history\n\n"
        "Simply send any text message to talk with CATBot."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""

    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("⚠️ You are not authorized to use this bot.")
        return

    backend_status, latency = await check_backend_health()
    message_total = message_counts.get(user_id, 0)
    latency_ms = f"{latency * 1000:.0f} ms" if latency is not None else "n/a"

    status_text = (
        "🤖 *CATBot Telegram Bot Status*\n\n"
        f"Backend: {backend_status}\n"
        f"Latency: {latency_ms}\n"
        f"Your messages: {message_total}\n"
        f"User ID: `{user_id}`\n\n"
        "📋 *Todo sync with web app:* To see the same todo list in Telegram and the browser, "
        "add a mapping in `config/telegram_user_links.json` on the server: "
        f'`\"{user_id}\": \"your_web_username\"`. See config/TELEGRAM_TODO_LINK.md for details.'
    )
    await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear command to reset conversation history."""

    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("⚠️ You are not authorized to use this bot.")
        return

    cleared = await clear_backend_history(user_id)
    if cleared:
        await update.message.reply_text("✅ Conversation history cleared. Let's start fresh!")
    else:
        await update.message.reply_text(
            "⚠️ I couldn't reset our history automatically. Please try again in a moment."
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forward text messages to the backend chat endpoint."""

    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text("⚠️ You are not authorized to use this bot.")
        logger.warning("Unauthorized message from %s", user_id)
        return

    text = update.message.text or ""
    if not text.strip():
        await update.message.reply_text("Please send a non-empty message.")
        return

    await update.message.chat.send_action(action=ChatAction.TYPING)

    try:
        reply = await call_backend_chat(user_id, text)
    except RuntimeError as exc:
        await update.message.reply_text(
            "😔 Sorry, something went wrong talking to CATBot. Please try again later."
        )
        logger.error("Error while chatting with backend: %s", exc)
        return

    await update.message.reply_text(reply)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log unexpected errors from the Telegram application."""

    logger.exception("Telegram bot error: %s", context.error)


def validate_configuration() -> None:
    """Ensure required environment variables are available."""

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required")

    if not (ALLOW_ALL_USERS or ADMIN_IDS):
        raise RuntimeError(
            "No TELEGRAM_ADMIN_IDS configured. Either specify at least one user ID or set TELEGRAM_ALLOW_ALL=true."
        )


def main() -> None:
    """Start the Telegram bot application."""

    try:
        validate_configuration()
    except RuntimeError as exc:
        logger.error(str(exc))
        raise SystemExit(1) from exc

    async def _post_init(app: Application) -> None:
        """Log when the application has finished initializing (post_init must be async)."""
        logger.info("CATBot Telegram bot started")

    application: Application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .rate_limiter(AIORateLimiter())
        .post_init(_post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(error_handler)

    logger.info("🤖 Starting CATBot Telegram bot...")
    if not ALLOW_ALL_USERS:
        logger.info("Authorized user IDs: %s", sorted(ADMIN_IDS))
    else:
        logger.info("Bot is configured for public access")

    print("\n✅ Bot is running! Press Ctrl+C to stop.")
    print("📱 Open Telegram and message your bot to begin.\n")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
