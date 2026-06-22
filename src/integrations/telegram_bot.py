#!/usr/bin/env python3
"""Telegram bot integration for CATBot with text and voice support.

Environment variables:
    TELEGRAM_BOT_TOKEN: Telegram bot token from @BotFather (required)
    TELEGRAM_ADMIN_IDS: Comma-separated Telegram user IDs allowed to chat
    TELEGRAM_ALLOW_ALL: Set to "true" to allow all users
    TELEGRAM_BACKEND_URL: CATBot backend base URL (default: http://localhost:8002)
    TELEGRAM_CHAT_ENDPOINT: Chat endpoint path or absolute URL (default: /v1/telegram/chat)
    TELEGRAM_TRANSCRIBE_ENDPOINT: Transcription endpoint path or absolute URL (default: /v1/audio/transcriptions)
    TELEGRAM_TRANSCRIBE_MODEL: Transcription model field sent to backend (default: whisper-1)
    TELEGRAM_VOICE_IN: Set to "false" to disable incoming voice transcription
    TELEGRAM_VOICE_OUT: Set to "true" to enable voice responses
    TELEGRAM_VOICE_NOTE_OPUS_BITRATE: Opus bitrate for Telegram voice notes (default: 32k)
    TELEGRAM_MAX_VOICE_SECONDS: Max accepted voice duration in seconds (default: 300)
    TELEGRAM_MAX_ATTACHMENT_BYTES: Max accepted document/photo size (default: FILE_OPS_MAX_SIZE_BYTES or 10485760)
    TELEGRAM_SEND_TRANSCRIPT: Set to "false" to suppress transcript echo message
    TELEGRAM_CHAT_TIMEOUT: Backend request timeout in seconds (default: 30)
    TELEGRAM_BOT_CHAT_TIMEOUT_HARD_CAP: Max allowed backend timeout in seconds (default: 10800)
    TELEGRAM_BACKEND_VERIFY_SSL: Set to "false" to skip SSL verification
    TELEGRAM_BOT_SYSTEM_PROMPT: Optional system prompt override passed to backend chat
    TELEGRAM_CHAT_MODEL: Optional model override passed to backend chat
    TELEGRAM_SECRET: Optional shared secret; sent as X-Telegram-Secret
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from dotenv import load_dotenv
from telegram import Audio, Document, Message, PhotoSize, Update, Voice
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
ALLOW_ALL_USERS = os.getenv("TELEGRAM_ALLOW_ALL", "false").lower() == "true"
BACKEND_BASE_URL = os.getenv("TELEGRAM_BACKEND_URL", os.getenv("BACKEND_URL", "http://localhost:8002"))
CHAT_ENDPOINT = os.getenv("TELEGRAM_CHAT_ENDPOINT", "/v1/telegram/chat")
TRANSCRIBE_ENDPOINT = os.getenv("TELEGRAM_TRANSCRIBE_ENDPOINT", "/v1/audio/transcriptions")
TRANSCRIBE_MODEL = os.getenv("TELEGRAM_TRANSCRIBE_MODEL", "whisper-1")
TTS_VOICE = os.getenv("TELEGRAM_TTS_VOICE", "alloy")
TTS_MODEL = os.getenv("TELEGRAM_TTS_MODEL", "tts-1")
TTS_RESPONSE_FORMAT = os.getenv("TELEGRAM_TTS_RESPONSE_FORMAT", "ogg")
VOICE_NOTE_OPUS_BITRATE = (os.getenv("TELEGRAM_VOICE_NOTE_OPUS_BITRATE", "32k") or "32k").strip() or "32k"
SYSTEM_PROMPT_OVERRIDE = os.getenv("TELEGRAM_BOT_SYSTEM_PROMPT")
MODEL_OVERRIDE = os.getenv("TELEGRAM_CHAT_MODEL")
TELEGRAM_SECRET = os.getenv("TELEGRAM_SECRET")
BACKEND_VERIFY_SSL = os.getenv("TELEGRAM_BACKEND_VERIFY_SSL", "true").lower() != "false"
SEND_TRANSCRIPT = os.getenv("TELEGRAM_SEND_TRANSCRIPT", "true").lower() != "false"
VOICE_IN_ENABLED = os.getenv("TELEGRAM_VOICE_IN", "true").lower() != "false"
VOICE_OUT_ENABLED = os.getenv("TELEGRAM_VOICE_OUT", "false").lower() == "true"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESTART_WORKER_SCRIPT = PROJECT_ROOT / "scripts" / "restart_all.py"
BACKUP_WORKER_SCRIPT = PROJECT_ROOT / "scripts" / "backup_all.py"


def _parse_admin_ids() -> set[int]:
    admin_ids: set[int] = set()
    raw = os.getenv("TELEGRAM_ADMIN_IDS", "")
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            admin_ids.add(int(item))
        except ValueError:
            logger.warning("Skipping invalid TELEGRAM_ADMIN_IDS entry: %r", item)
    return admin_ids


def _parse_chat_timeout() -> float:
    try:
        raw_timeout = float(os.getenv("TELEGRAM_CHAT_TIMEOUT", "30"))
    except ValueError:
        logger.warning("Invalid TELEGRAM_CHAT_TIMEOUT; using 30")
        return 30.0
    hard_cap_raw = os.getenv("TELEGRAM_BOT_CHAT_TIMEOUT_HARD_CAP", "10800")
    try:
        hard_cap = max(1.0, float(hard_cap_raw))
    except ValueError:
        hard_cap = 10800.0
    if raw_timeout > hard_cap:
        logger.warning(
            "TELEGRAM_CHAT_TIMEOUT=%s exceeds TELEGRAM_BOT_CHAT_TIMEOUT_HARD_CAP=%s; using cap.",
            raw_timeout,
            hard_cap,
        )
    return max(1.0, min(raw_timeout, hard_cap))


def _parse_max_voice_seconds() -> int:
    try:
        return max(1, int(os.getenv("TELEGRAM_MAX_VOICE_SECONDS", "300")))
    except ValueError:
        logger.warning("Invalid TELEGRAM_MAX_VOICE_SECONDS; using 300")
        return 300


def _parse_max_attachment_bytes() -> int:
    raw = os.getenv("TELEGRAM_MAX_ATTACHMENT_BYTES") or os.getenv("FILE_OPS_MAX_SIZE_BYTES") or "10485760"
    try:
        return max(1, int(raw))
    except ValueError:
        logger.warning("Invalid TELEGRAM_MAX_ATTACHMENT_BYTES/FILE_OPS_MAX_SIZE_BYTES; using 10485760")
        return 10485760


def _parse_status_update_interval() -> float:
    try:
        raw = float(os.getenv("TELEGRAM_STATUS_POLL_INTERVAL", "2"))
    except ValueError:
        logger.warning("Invalid TELEGRAM_STATUS_POLL_INTERVAL; using 2 seconds")
        return 2.0
    return max(0.2, raw)


ADMIN_IDS = _parse_admin_ids()
CHAT_TIMEOUT = _parse_chat_timeout()
MAX_VOICE_SECONDS = _parse_max_voice_seconds()
MAX_ATTACHMENT_BYTES = _parse_max_attachment_bytes()
STATUS_UPDATE_INTERVAL = _parse_status_update_interval()
TELEGRAM_TEXT_MESSAGE_LIMIT = 4000

# Track successful user message turns (text or voice transcript)
message_counts: Dict[int, int] = {}
_backend_http_client: Optional[httpx.AsyncClient] = None
_backend_http_client_lock = asyncio.Lock()
_background_tasks: set[asyncio.Task] = set()


def _build_backend_url(path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return f"{BACKEND_BASE_URL.rstrip('/')}{path_or_url}"


def _split_telegram_text_reply(text: str, max_chars: int = TELEGRAM_TEXT_MESSAGE_LIMIT) -> list[str]:
    normalized = str(text or "")
    if not normalized:
        return [""]
    if max_chars < 1:
        max_chars = TELEGRAM_TEXT_MESSAGE_LIMIT

    chunks: list[str] = []
    remaining = normalized
    while len(remaining) > max_chars:
        split_at = remaining.rfind("\n", 0, max_chars + 1)
        if split_at > 0:
            split_at += 1
        else:
            split_at = remaining.rfind(" ", 0, max_chars + 1)
            if split_at > 0:
                split_at += 1
        if split_at <= 0:
            split_at = max_chars
        chunk = remaining[:split_at]
        if not chunk:
            chunk = remaining[:max_chars]
            split_at = len(chunk)
        chunks.append(chunk)
        remaining = remaining[split_at:]
    if remaining:
        chunks.append(remaining)
    return chunks or [normalized]


async def _send_telegram_text_reply(message, text: str) -> None:
    chunks = _split_telegram_text_reply(text)
    for chunk in chunks:
        await message.reply_text(chunk)


def build_chat_url() -> str:
    """Backward-compatible helper used by tests and scripts."""
    return _build_backend_url(CHAT_ENDPOINT)


def _backend_headers() -> Dict[str, str]:
    if not TELEGRAM_SECRET:
        return {}
    return {"X-Telegram-Secret": TELEGRAM_SECRET}


async def _get_backend_http_client() -> httpx.AsyncClient:
    global _backend_http_client
    client = _backend_http_client
    if client is not None and not client.is_closed:
        return client
    async with _backend_http_client_lock:
        client = _backend_http_client
        if client is None or client.is_closed:
            _backend_http_client = httpx.AsyncClient(timeout=CHAT_TIMEOUT, verify=BACKEND_VERIFY_SSL)
        return _backend_http_client


async def _close_backend_http_client() -> None:
    global _backend_http_client
    async with _backend_http_client_lock:
        client = _backend_http_client
        _backend_http_client = None
    if client is not None and not client.is_closed:
        await client.aclose()


def _track_background_task(task: asyncio.Task) -> asyncio.Task:
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def _cancel_background_tasks() -> None:
    if not _background_tasks:
        return
    tasks = tuple(_background_tasks)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def is_authorized(user_id: int) -> bool:
    if ALLOW_ALL_USERS:
        return True
    if not ADMIN_IDS:
        logger.warning("No TELEGRAM_ADMIN_IDS configured and TELEGRAM_ALLOW_ALL is false")
        return False
    return user_id in ADMIN_IDS


def is_admin_user(user_id: int) -> bool:
    return bool(ADMIN_IDS and user_id in ADMIN_IDS)


async def _poll_status_updates(
    bot,
    chat_id: int,
    stop_event: asyncio.Event,
    conversation_id: str,
    request_id: str,
) -> None:
    last_seq = 0
    last_state_sent = ""
    url = _build_backend_url("/v1/status/latest")
    headers = _backend_headers()

    async def _fetch_once() -> tuple[int, str]:
        nonlocal last_seq, last_state_sent
        try:
            client = await _get_backend_http_client()
            resp = await client.get(
                url,
                params={"conversation_id": conversation_id, "request_id": request_id},
                headers=headers,
            )
            if resp.status_code != 200:
                return last_seq, last_state_sent
            payload = resp.json()
            if not payload.get("found"):
                return last_seq, last_state_sent
            event = payload.get("event") or {}
            seq = int(event.get("seq") or 0)
            state_text = (event.get("state") or "").strip()
            event_type = str(event.get("type") or "").strip().lower()
            if seq <= last_seq or not state_text:
                return last_seq, last_state_sent
            if state_text == last_state_sent:
                last_seq = seq
                return last_seq, last_state_sent
            last_seq = seq
            last_state_sent = state_text
            await bot.send_message(chat_id=chat_id, text=state_text)
        except Exception:
            logger.debug("Status polling failed for chat_id=%s", chat_id, exc_info=True)
        return last_seq, last_state_sent

    await _fetch_once()

    while True:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=STATUS_UPDATE_INTERVAL)
            break
        except asyncio.TimeoutError:
            await _fetch_once()


async def _stop_status_updates(stop_event: asyncio.Event, status_task: asyncio.Task) -> None:
    """Stop and await the status poller without leaking CancelledError."""
    stop_event.set()
    if not status_task.done():
        status_task.cancel()
    with suppress(asyncio.CancelledError, Exception):
        await status_task


async def call_backend_chat(
    user_id: int,
    message: str,
    request_id: Optional[str] = None,
    attachments: Optional[List[Dict[str, object]]] = None,
) -> str:
    payload = {
        "conversation_id": str(user_id),
        "user_id": str(user_id),
        "message": message,
    }
    if request_id:
        payload["request_id"] = request_id
    if SYSTEM_PROMPT_OVERRIDE:
        payload["system_prompt"] = SYSTEM_PROMPT_OVERRIDE
    if MODEL_OVERRIDE:
        payload["model"] = MODEL_OVERRIDE
    if attachments:
        payload["attachments"] = attachments

    url = _build_backend_url(CHAT_ENDPOINT)
    headers = _backend_headers()

    try:
        client = await _get_backend_http_client()
        response = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        raise RuntimeError("Failed to reach CATBot backend chat endpoint.") from exc

    if response.status_code != 200:
        logger.error("Chat backend error %s: %s", response.status_code, response.text)
        try:
            err = response.json()
            detail = err.get("detail") or err.get("message")
        except ValueError:
            detail = response.text
        raise RuntimeError(detail or "Backend returned an unexpected chat error.")

    data = response.json()
    reply = data.get("reply") or data.get("response") or data.get("text")
    if not reply:
        raise RuntimeError("Backend chat response did not include a reply.")

    message_counts[user_id] = message_counts.get(user_id, 0) + 1
    return str(reply)


def _extract_transcript(payload: dict) -> Optional[str]:
    for key in ("text", "transcript", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


async def call_backend_transcription(
    filename: str,
    mime_type: str,
    content: bytes,
) -> str:
    url = _build_backend_url(TRANSCRIBE_ENDPOINT)
    headers = _backend_headers()
    files = {"file": (filename, content, mime_type or "application/octet-stream")}
    data = {"model": TRANSCRIBE_MODEL}

    try:
        client = await _get_backend_http_client()
        response = await client.post(url, files=files, data=data, headers=headers)
    except httpx.RequestError as exc:
        raise RuntimeError("Failed to reach transcription endpoint.") from exc

    if response.status_code != 200:
        logger.error("Transcription backend error %s: %s", response.status_code, response.text)
        try:
            err = response.json()
            detail = err.get("detail") or err.get("message") or err.get("error")
        except ValueError:
            detail = response.text
        raise RuntimeError(detail or "Backend returned an unexpected transcription error.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Transcription endpoint returned non-JSON content.") from exc

    transcript = _extract_transcript(payload)
    if not transcript:
        raise RuntimeError("Transcription endpoint returned an empty transcript.")
    return transcript


def _guess_audio_filename(content_type: str) -> str:
    lowered = (content_type or "").lower()
    if "ogg" in lowered:
        return "reply.ogg"
    if "wav" in lowered:
        return "reply.wav"
    if "mpeg" in lowered or "mp3" in lowered:
        return "reply.mp3"
    return "reply.audio"


def _is_ogg_opus(content_type: str, audio_bytes: bytes) -> bool:
    lowered = (content_type or "").lower()
    if "opus" in lowered:
        return True
    if "ogg" not in lowered:
        return False
    header = audio_bytes[:128] if audio_bytes else b""
    return b"OpusHead" in header


def _convert_to_ogg_opus_sync(audio_bytes: bytes) -> bytes:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg is not available on PATH")
    if not audio_bytes:
        raise RuntimeError("No audio bytes to convert")

    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        "pipe:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "48000",
        "-c:a",
        "libopus",
        "-b:a",
        VOICE_NOTE_OPUS_BITRATE,
        "-vbr",
        "on",
        "-application",
        "voip",
        "-f",
        "ogg",
        "pipe:1",
    ]
    completed = subprocess.run(cmd, input=audio_bytes, capture_output=True, check=False)
    if completed.returncode != 0 or not completed.stdout:
        stderr = completed.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(stderr or "ffmpeg conversion failed")
    return completed.stdout


async def _ensure_telegram_voice_note_audio(
    audio_bytes: bytes,
    content_type: str,
) -> tuple[bytes, str, bool]:
    if _is_ogg_opus(content_type, audio_bytes):
        return audio_bytes, content_type, False
    try:
        converted = await asyncio.to_thread(_convert_to_ogg_opus_sync, audio_bytes)
    except Exception as exc:
        logger.warning("Could not convert TTS audio to OGG/Opus voice note: %s", exc)
        return audio_bytes, content_type, False
    return converted, "audio/ogg; codecs=opus", True


_BRACKET_CONTENT_PATTERN = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
_TTS_ALLOWED_PUNCTUATION = set(".,!?;:'\"-")
_TRANSIENT_REPLY_PATTERNS = [
    re.compile(r"^(?:on it|working on it|let me|i'll|i will|i am going to|now i will)\b", re.IGNORECASE),
    re.compile(r"\b(?:let me check|let me see|let me fetch|let me verify|i'll check|i will check|i'll use|i will use)\b", re.IGNORECASE),
    re.compile(r"\b(?:next step|after that|then i'll|then i will|now i'll|now i will)\b", re.IGNORECASE),
]


def _sanitize_tts_text(text: str) -> str:
    cleaned = text or ""

    # Remove content in parentheses and square brackets (supports nested by repeated passes).
    while True:
        updated = _BRACKET_CONTENT_PATTERN.sub(" ", cleaned)
        if updated == cleaned:
            break
        cleaned = updated

    # Keep only letters/digits, whitespace, and TTS-friendly punctuation.
    filtered_chars = [
        ch
        for ch in cleaned
        if ch.isalnum() or ch.isspace() or ch in _TTS_ALLOWED_PUNCTUATION
    ]
    normalized = "".join(filtered_chars)
    return re.sub(r"\s+", " ", normalized).strip()


def _looks_like_transient_reply(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    if not normalized:
        return False
    if "<tool>" in normalized.lower() or "<parameters>" in normalized.lower():
        return True
    if len(normalized) > 280:
        return False
    return any(pattern.search(normalized) for pattern in _TRANSIENT_REPLY_PATTERNS)


def _should_send_voice_reply(text: str) -> bool:
    """Only voice substantive user-facing replies, not transient planning/progress text."""
    normalized = str(text or "").strip()
    if not normalized:
        return False
    if _looks_like_transient_reply(normalized):
        return False
    return True


async def call_backend_tts(text: str) -> tuple[bytes, str]:
    url = _build_backend_url("/v1/proxy/tts/speech")
    headers = _backend_headers()
    sanitized_text = _sanitize_tts_text(text)
    if not sanitized_text:
        raise RuntimeError("TTS input was empty after sanitization.")

    payload = {
        "model": TTS_MODEL,
        "input": sanitized_text,
        "voice": TTS_VOICE,
        "response_format": TTS_RESPONSE_FORMAT,
    }

    try:
        client = await _get_backend_http_client()
        response = await client.post(
            url,
            params={"buffer": "true"},
            json=payload,
            headers=headers,
            timeout=CHAT_TIMEOUT,
        )
    except httpx.RequestError as exc:
        raise RuntimeError("Failed to reach TTS endpoint.") from exc

    if response.status_code != 200:
        logger.error("TTS backend error %s: %s", response.status_code, response.text)
        raise RuntimeError("Backend returned an unexpected TTS error.")

    content_type = response.headers.get("content-type", "audio/mpeg")
    return response.content, content_type


async def _send_voice_reply(message: Message, reply: str) -> None:
    try:
        await message.chat.send_action(action=ChatAction.RECORD_VOICE)
        audio_bytes, content_type = await call_backend_tts(reply)
        audio_bytes, content_type, was_converted = await _ensure_telegram_voice_note_audio(
            audio_bytes, content_type
        )
        filename = _guess_audio_filename(content_type)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename
        is_ogg_opus = _is_ogg_opus(content_type, audio_bytes)
        logger.info(
            "TTS reply audio bytes=%s content-type=%s ogg_opus=%s converted=%s",
            len(audio_bytes or b""),
            content_type,
            is_ogg_opus,
            was_converted,
        )
        if is_ogg_opus:
            await message.reply_voice(voice=audio_file, filename=filename)
        else:
            await message.reply_audio(audio=audio_file, filename=filename)
    except asyncio.CancelledError:
        logger.info("Cancelled pending Telegram voice reply task")
        raise
    except Exception as exc:
        logger.error("Voice reply failed: %s", exc, exc_info=True)


def _schedule_voice_reply(message: Message, reply: str) -> None:
    _track_background_task(asyncio.create_task(_send_voice_reply(message, reply)))


async def clear_backend_history(user_id: int) -> bool:
    delete_url = _build_backend_url(CHAT_ENDPOINT).rstrip("/") + f"/{user_id}"
    headers = _backend_headers()

    try:
        client = await _get_backend_http_client()
        response = await client.delete(delete_url, headers=headers)
    except httpx.RequestError as exc:
        raise RuntimeError("Unable to reach backend to clear conversation.") from exc

    if response.status_code not in (200, 204):
        logger.error("Failed to clear conversation (%s): %s", response.status_code, response.text)
        return False
    message_counts.pop(user_id, None)
    return True


async def check_backend_health() -> tuple[str, Optional[float]]:
    health_url = _build_backend_url("/health")
    headers = _backend_headers()
    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        client = await _get_backend_http_client()
        response = await client.get(health_url, headers=headers)
    except httpx.RequestError:
        logger.warning("Health check failed", exc_info=True)
        return "Offline", None

    latency = loop.time() - start
    if response.status_code == 200:
        return "Online", latency
    return f"HTTP {response.status_code}", latency


async def _authorize_or_reject(update: Update) -> Optional[int]:
    if not update.message or not update.effective_user:
        return None
    user_id = update.effective_user.id
    if is_authorized(user_id):
        return user_id
    await update.message.reply_text("You are not authorized to use this bot.")
    logger.warning("Unauthorized access attempt from user_id=%s", user_id)
    return None


async def _authorize_admin_or_reject(update: Update) -> Optional[int]:
    if not update.message or not update.effective_user:
        return None
    user_id = update.effective_user.id
    if is_admin_user(user_id):
        return user_id
    await update.message.reply_text("You are not authorized to use this admin command.")
    logger.warning("Unauthorized admin command attempt from user_id=%s", user_id)
    return None


async def _reply_with_backend_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    prompt_text: str,
    attachments: Optional[List[Dict[str, object]]] = None,
) -> None:
    if not update.message or not update.effective_chat:
        return

    await update.message.chat.send_action(action=ChatAction.TYPING)
    request_id = uuid.uuid4().hex
    stop_event = asyncio.Event()
    status_task = asyncio.create_task(
        _poll_status_updates(
            context.bot,
            update.effective_chat.id,
            stop_event,
            str(user_id),
            request_id,
        )
    )
    try:
        reply = await call_backend_chat(user_id, prompt_text, request_id=request_id, attachments=attachments)
    except RuntimeError as exc:
        logger.error("Backend chat failed: %s", exc)
        stop_event.set()
        await _stop_status_updates(stop_event, status_task)
        await _send_telegram_text_reply(
            update.message,
            "CATBot could not process that request right now. Please try again.",
        )
        return

    stop_event.set()
    await _stop_status_updates(stop_event, status_task)
    await _send_telegram_text_reply(update.message, reply)

    if VOICE_OUT_ENABLED and _should_send_voice_reply(reply):
        _schedule_voice_reply(update.message, reply)
    elif VOICE_OUT_ENABLED:
        logger.info("Skipping Telegram TTS for transient/planning reply: %r", reply[:200])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    user_id = await _authorize_or_reject(update)
    if user_id is None:
        return

    user_name = update.effective_user.first_name or update.effective_user.username or "there"
    message_counts.setdefault(user_id, 0)
    await update.message.reply_text(
        f"Hi {user_name}. I am CATBot.\n\n"
        "Send a text message, voice note, photo, or document and I will reply.\n"
        "Use /help to see available commands."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    admin_lines = ""
    if is_admin_user(update.effective_user.id):
        admin_lines = (
            "\n"
            "/restart - restart all CATBot services\n"
            f"/backup - create a ZIP backup in {PROJECT_ROOT / 'backups'}\n"
        )
    await update.message.reply_text(
        "*CATBot Telegram Commands*\n\n"
        "/start - initialize chat\n"
        "/help - show this message\n"
        "/status - backend status and usage\n"
        "/clear - clear conversation history\n"
        f"{admin_lines}\n"
        "You can send text, voice notes, audio files, photos, or documents.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user_id = await _authorize_or_reject(update)
    if user_id is None:
        return

    backend_status, latency = await check_backend_health()
    latency_ms = f"{latency * 1000:.0f} ms" if latency is not None else "n/a"
    message_total = message_counts.get(user_id, 0)

    await update.message.reply_text(
        "*CATBot Status*\n\n"
        f"Backend: {backend_status}\n"
        f"Latency: {latency_ms}\n"
        f"Your messages: {message_total}\n"
        f"User ID: `{user_id}`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user_id = await _authorize_or_reject(update)
    if user_id is None:
        return

    try:
        cleared = await clear_backend_history(user_id)
    except RuntimeError as exc:
        logger.error("Clear conversation failed: %s", exc)
        await update.message.reply_text("Could not clear conversation right now.")
        return

    if cleared:
        await update.message.reply_text("Conversation history cleared.")
    else:
        await update.message.reply_text("Backend did not confirm history clear. Try again shortly.")


def _spawn_worker_script(worker_script: Path, chat_id: int, requested_by: int) -> None:
    if not worker_script.exists():
        raise RuntimeError(f"Worker script not found: {worker_script}")

    # On Windows, launch through a short-lived PowerShell trampoline so the
    # worker is not a direct child of the telegram bot process.
    # This prevents stop_all.py (taskkill /T) from killing detached workers.
    if os.name == "nt":
        python_executable = str(Path(sys.executable).resolve())
        script_path = str(worker_script.resolve())

        def _ps_single_quote(value: str) -> str:
            return value.replace("'", "''")

        ps_script = (
            f"$python = '{_ps_single_quote(python_executable)}'; "
            f"$script = '{_ps_single_quote(script_path)}'; "
            f"$args = @($script, '--chat-id', '{chat_id}', '--requested-by', '{requested_by}'); "
            "Start-Process -FilePath $python -ArgumentList $args -WindowStyle Hidden"
        )

        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            creationflags=create_no_window,
        )
        return

    cmd = [
        sys.executable,
        str(worker_script),
        "--chat-id",
        str(chat_id),
        "--requested-by",
        str(requested_by),
    ]
    popen_kwargs = {
        "cwd": str(PROJECT_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        detached = getattr(subprocess, "DETACHED_PROCESS", 0)
        new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        popen_kwargs["creationflags"] = detached | new_group
    else:
        popen_kwargs["start_new_session"] = True

    subprocess.Popen(cmd, **popen_kwargs)


def _spawn_restart_worker(chat_id: int, requested_by: int) -> None:
    _spawn_worker_script(RESTART_WORKER_SCRIPT, chat_id=chat_id, requested_by=requested_by)


def _spawn_backup_worker(chat_id: int, requested_by: int) -> None:
    _spawn_worker_script(BACKUP_WORKER_SCRIPT, chat_id=chat_id, requested_by=requested_by)


async def restart_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    user_id = await _authorize_admin_or_reject(update)
    if user_id is None:
        return

    chat_id = update.effective_chat.id
    try:
        _spawn_restart_worker(chat_id=chat_id, requested_by=user_id)
    except Exception as exc:
        logger.error("Failed to launch restart worker: %s", exc, exc_info=True)
        await update.message.reply_text("Failed to start restart workflow. Check server logs.")
        return

    await update.message.reply_text(
        "Restart workflow started. I will post a follow-up message in this chat when services are back."
    )


async def backup_bot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    user_id = await _authorize_admin_or_reject(update)
    if user_id is None:
        return

    chat_id = update.effective_chat.id
    try:
        _spawn_backup_worker(chat_id=chat_id, requested_by=user_id)
    except Exception as exc:
        logger.error("Failed to launch backup worker: %s", exc, exc_info=True)
        await update.message.reply_text("Failed to start backup workflow. Check server logs.")
        return

    await update.message.reply_text(
        "Backup workflow started. I will post the archive path in this chat when it completes."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user_id = await _authorize_or_reject(update)
    if user_id is None:
        return

    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Please send a non-empty message.")
        return

    await _reply_with_backend_answer(update, context, user_id, text)


def _voice_file_info(voice: Optional[Voice], audio: Optional[Audio]) -> tuple[str, str, int]:
    if voice:
        filename = f"voice_{voice.file_unique_id}.ogg"
        mime_type = voice.mime_type or "audio/ogg"
        duration = int(voice.duration or 0)
        return filename, mime_type, duration
    if audio:
        filename = audio.file_name or f"audio_{audio.file_unique_id}.bin"
        mime_type = audio.mime_type or "audio/mpeg"
        duration = int(audio.duration or 0)
        return filename, mime_type, duration
    return "audio.bin", "application/octet-stream", 0


def _document_file_info(document: Optional[Document]) -> tuple[str, str]:
    if not document:
        return "attachment.bin", "application/octet-stream"
    filename = document.file_name or f"document_{document.file_unique_id}.bin"
    mime_type = document.mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return filename, mime_type


def _photo_file_info(photos: List[PhotoSize]) -> tuple[Optional[PhotoSize], str, str]:
    if not photos:
        return None, "photo.jpg", "image/jpeg"
    photo = photos[-1]
    filename = f"photo_{photo.file_unique_id}.jpg"
    return photo, filename, "image/jpeg"


def _telegram_file_size(value: object) -> Optional[int]:
    try:
        size = getattr(value, "file_size", None)
        if size is None:
            return None
        return max(0, int(size))
    except (TypeError, ValueError):
        return None


def _attachment_too_large(size_bytes: Optional[int]) -> bool:
    return size_bytes is not None and size_bytes > MAX_ATTACHMENT_BYTES


def _build_backend_attachment_payload(filename: str, mime_type: str, content: bytes) -> Dict[str, object]:
    return {
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": len(content),
        "content_base64": base64.b64encode(content).decode("ascii"),
    }


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user_id = await _authorize_or_reject(update)
    if user_id is None:
        return
    if not VOICE_IN_ENABLED:
        await update.message.reply_text("Voice transcription is disabled for this bot.")
        return

    voice = update.message.voice
    audio = update.message.audio
    if not voice and not audio:
        await update.message.reply_text("No voice or audio attachment was found.")
        return

    filename, mime_type, duration = _voice_file_info(voice, audio)
    if duration > MAX_VOICE_SECONDS:
        await update.message.reply_text(
            f"Voice message is too long ({duration}s). Max allowed is {MAX_VOICE_SECONDS}s."
        )
        return
    source_file = voice or audio
    if _attachment_too_large(_telegram_file_size(source_file)):
        await update.message.reply_text(
            f"Audio attachment is too large. Max allowed is {MAX_ATTACHMENT_BYTES} bytes."
        )
        return

    file_id = voice.file_id if voice else audio.file_id
    await update.message.chat.send_action(action=ChatAction.TYPING)

    try:
        tg_file = await context.bot.get_file(file_id)
        if _attachment_too_large(_telegram_file_size(tg_file)):
            await update.message.reply_text(
                f"Audio attachment is too large. Max allowed is {MAX_ATTACHMENT_BYTES} bytes."
            )
            return
        audio_data = await tg_file.download_as_bytearray()
        if len(audio_data) > MAX_ATTACHMENT_BYTES:
            await update.message.reply_text(
                f"Audio attachment is too large. Max allowed is {MAX_ATTACHMENT_BYTES} bytes."
            )
            return
        transcript = await call_backend_transcription(filename, mime_type, bytes(audio_data))
    except RuntimeError as exc:
        logger.error("Transcription failed: %s", exc)
        await update.message.reply_text("Could not transcribe that audio right now. Please try again.")
        return
    except Exception as exc:
        logger.error("Voice handling failed unexpectedly: %s", exc, exc_info=True)
        await update.message.reply_text("Failed to process the voice message.")
        return

    if SEND_TRANSCRIPT:
        await update.message.reply_text(f"Transcript:\n{transcript}")

    await _reply_with_backend_answer(update, context, user_id, transcript)


async def handle_attachment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    user_id = await _authorize_or_reject(update)
    if user_id is None:
        return

    document = update.message.document
    photos = list(update.message.photo or [])
    if not document and not photos:
        await update.message.reply_text("No supported attachment was found.")
        return

    await update.message.chat.send_action(action=ChatAction.TYPING)

    try:
        if document:
            filename, mime_type = _document_file_info(document)
            if _attachment_too_large(_telegram_file_size(document)):
                await update.message.reply_text(
                    f"Attachment is too large. Max allowed is {MAX_ATTACHMENT_BYTES} bytes."
                )
                return
            tg_file = await context.bot.get_file(document.file_id)
        else:
            photo, filename, mime_type = _photo_file_info(photos)
            if photo is None:
                await update.message.reply_text("No supported attachment was found.")
                return
            if _attachment_too_large(_telegram_file_size(photo)):
                await update.message.reply_text(
                    f"Attachment is too large. Max allowed is {MAX_ATTACHMENT_BYTES} bytes."
                )
                return
            tg_file = await context.bot.get_file(photo.file_id)

        if _attachment_too_large(_telegram_file_size(tg_file)):
            await update.message.reply_text(
                f"Attachment is too large. Max allowed is {MAX_ATTACHMENT_BYTES} bytes."
            )
            return
        attachment_bytes = bytes(await tg_file.download_as_bytearray())
        if len(attachment_bytes) > MAX_ATTACHMENT_BYTES:
            await update.message.reply_text(
                f"Attachment is too large. Max allowed is {MAX_ATTACHMENT_BYTES} bytes."
            )
            return
        prompt_text = (update.message.caption or "").strip() or "Please review the attached file."
        attachments = [_build_backend_attachment_payload(filename, mime_type, attachment_bytes)]
    except Exception as exc:
        logger.error("Attachment handling failed unexpectedly: %s", exc, exc_info=True)
        await update.message.reply_text("Failed to process that attachment.")
        return

    await _reply_with_backend_answer(
        update,
        context,
        user_id,
        prompt_text,
        attachments=attachments,
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram bot error: %s", context.error)


def validate_configuration() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is required")
    if not (ALLOW_ALL_USERS or ADMIN_IDS):
        raise RuntimeError(
            "No TELEGRAM_ADMIN_IDS configured. Set at least one admin ID or TELEGRAM_ALLOW_ALL=true."
        )


def main() -> None:
    try:
        validate_configuration()
    except RuntimeError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc

    async def _post_init(app: Application) -> None:
        logger.info("CATBot Telegram bot initialized")

    async def _post_shutdown(app: Application) -> None:
        await _cancel_background_tasks()
        await _close_backend_http_client()

    app: Application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .rate_limiter(AIORateLimiter())
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("restart", restart_bot_command))
    app.add_handler(CommandHandler("restart_bot", restart_bot_command))
    app.add_handler(CommandHandler("backup", backup_bot_command))
    app.add_handler(CommandHandler("backup_bot", backup_bot_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    if VOICE_IN_ENABLED:
        app.add_handler(MessageHandler((filters.VOICE | filters.AUDIO) & ~filters.COMMAND, handle_voice))
    else:
        logger.info("Incoming Telegram voice transcription is disabled")
    app.add_handler(
        MessageHandler(
            ((filters.Document.ALL | filters.PHOTO) & ~filters.VOICE & ~filters.AUDIO) & ~filters.COMMAND,
            handle_attachment,
        )
    )
    app.add_error_handler(error_handler)

    logger.info("Starting CATBot Telegram bot")
    if ALLOW_ALL_USERS:
        logger.info("Access mode: allow all users")
    else:
        logger.info("Access mode: admin-only, ids=%s", sorted(ADMIN_IDS))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
