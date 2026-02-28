#!/usr/bin/env python3
"""
Python FastAPI replacement for the Node.js proxy server.
Provides the same functionality but in Python for better integration with the MCP ecosystem.
"""

import asyncio
import collections
import json
import html
import os
import re
import sys
import time
import base64
import hmac
import hashlib
import secrets
import glob
import socket
import struct
from typing import Dict, List, Optional, Any, Set, Tuple
from pathlib import Path
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import urljoin, urlparse, urlunparse
from dataclasses import dataclass
from contextlib import suppress

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, ConfigDict, Field
import uvicorn

from src.utils.token_budget import (
    estimate_tokens_from_messages,
    format_messages_for_summary,
    get_max_token_limit,
    is_context_limit_error,
)
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BeautifulSoup = None
    BS4_AVAILABLE = False

# Import dotenv to load .env file
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("[WARN] python-dotenv not available. Install with: pip install python-dotenv")

# Import file operations libraries
try:
    from docx import Document  # python-docx for Word documents
    import openpyxl  # openpyxl for Excel files
    from openpyxl.styles import Font, Alignment  # For Excel formatting
    import PyPDF2  # PyPDF2 for PDF reading
    from PIL import Image  # Pillow for image operations
    FILE_OPS_AVAILABLE = True
    print("[OK] File operations libraries loaded successfully")
except ImportError as e:
    print(f"[WARN] File operations libraries not available: {e}")
    FILE_OPS_AVAILABLE = False

# Import AutoGen components for team-based chat
try:
    from autogen_agentchat.teams import SelectorGroupChat
    from autogen_core import Component, FunctionCall, ComponentLoader
    AUTOGEN_AVAILABLE = True
    print("[OK] AutoGen imports successful")
except ImportError as e:
    print(f"[WARN] AutoGen not available: {e}")
    AUTOGEN_AVAILABLE = False
    SelectorGroupChat = None
    Component = None
    ComponentLoader = None

# Optional: code execution tool and Docker executor for actor workbench (requires autogen-ext[docker])
AUTOGEN_CODE_EXEC_AVAILABLE = False
PythonCodeExecutionTool = None
DockerCommandLineCodeExecutor = None
if AUTOGEN_AVAILABLE:
    try:
        from autogen_ext.tools.code_execution import PythonCodeExecutionTool as _PythonCodeExecutionTool
        from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor as _DockerCommandLineCodeExecutor
        PythonCodeExecutionTool = _PythonCodeExecutionTool
        DockerCommandLineCodeExecutor = _DockerCommandLineCodeExecutor
        AUTOGEN_CODE_EXEC_AVAILABLE = True
        print("[OK] AutoGen code execution (Docker) available")
    except ImportError as e:
        print(f"[WARN] AutoGen code execution not available (install autogen-ext[docker]): {e}")

# Import MCP SDK (with error handling)
try:
    from mcp import ClientSession, stdio_client, StdioServerParameters
    MCP_AVAILABLE = True
except ImportError as e:
    print(f"MCP import error: {e}")
    MCP_AVAILABLE = False
    ClientSession = None
    stdio_client = None
    StdioServerParameters = None

# Browser-use HTTP server URL (must run: uv run mcp-server-browser-use server)
MCP_BROWSER_USE_HTTP_URL = os.environ.get("MCP_BROWSER_USE_HTTP_URL", "http://127.0.0.1:8383/mcp").strip()
BROWSER_USE_HTTP_UNAVAILABLE_MSG = (
    "Browser-use HTTP server not available. Start it with: uv run mcp-server-browser-use server (in mcp-browser-use directory)."
)
OPEN_METEO_FORECAST_BASE_URL = os.environ.get("OPEN_METEO_FORECAST_BASE_URL", "https://api.open-meteo.com/v1/forecast").strip().rstrip("/")
OPEN_METEO_GEOCODING_BASE_URL = os.environ.get("OPEN_METEO_GEOCODING_BASE_URL", "https://geocoding-api.open-meteo.com/v1/search").strip().rstrip("/")
_open_meteo_timeout_value = os.environ.get("OPEN_METEO_TIMEOUT_SECONDS", os.environ.get("BOM_API_TIMEOUT_SECONDS", "12"))
try:
    OPEN_METEO_TIMEOUT_SECONDS = float(_open_meteo_timeout_value)
except ValueError:
    OPEN_METEO_TIMEOUT_SECONDS = 12.0
_open_meteo_trust_env_value = os.environ.get("OPEN_METEO_TRUST_ENV", os.environ.get("BOM_API_TRUST_ENV", ""))
OPEN_METEO_TRUST_ENV = str(_open_meteo_trust_env_value).strip().lower() in {"1", "true", "yes", "y", "on"}
OPEN_METEO_USER_AGENT = (
    os.environ.get("OPEN_METEO_USER_AGENT")
    or os.environ.get("BOM_API_USER_AGENT")
    or "CATBot/1.0 (+open-meteo-weather-tool)"
).strip() or "CATBot/1.0"
OPEN_METEO_ALLOWED_HOST_SUFFIX = "open-meteo.com"

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "")
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_str(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None

PROXY_RELOAD = _env_bool("PROXY_RELOAD", default=False)
PROXY_RESTART_ENABLED = _env_bool("PROXY_RESTART_ENABLED", default=True)
try:
    PROXY_RESTART_DELAY_SECONDS = max(0.2, float(os.environ.get("PROXY_RESTART_DELAY_SECONDS", "1.0")))
except ValueError:
    PROXY_RESTART_DELAY_SECONDS = 1.0

_proxy_restart_scheduled = False
PROXY_START_TIME = time.time()

# Embedded Kitten TTS settings (disabled by default; set EMBEDDED_KITTEN_TTS_ENABLED=true)
EMBEDDED_KITTEN_TTS_ENABLED = _env_bool("EMBEDDED_KITTEN_TTS_ENABLED", default=False)
EMBEDDED_KITTEN_MODEL = os.environ.get("EMBEDDED_KITTEN_MODEL", "KittenML/kitten-tts-nano-0.2").strip()
EMBEDDED_KITTEN_DEFAULT_VOICE = os.environ.get("EMBEDDED_KITTEN_DEFAULT_VOICE", "expr-voice-2-f").strip() or "expr-voice-2-f"
EMBEDDED_KITTEN_VOICES = [
    v.strip() for v in os.environ.get(
        "EMBEDDED_KITTEN_VOICES",
        "expr-voice-2-f,expr-voice-3-f,expr-voice-4-m,expr-voice-5-m,expr-voice-2-m,expr-voice-5-f",
    ).split(",") if v.strip()
]
try:
    EMBEDDED_KITTEN_SAMPLE_RATE = max(8000, int(os.environ.get("EMBEDDED_KITTEN_SAMPLE_RATE", "24000")))
except ValueError:
    EMBEDDED_KITTEN_SAMPLE_RATE = 24000
try:
    EMBEDDED_KITTEN_STREAM_CHUNK_BYTES = max(512, int(os.environ.get("EMBEDDED_KITTEN_STREAM_CHUNK_BYTES", "8192")))
except ValueError:
    EMBEDDED_KITTEN_STREAM_CHUNK_BYTES = 8192
try:
    EMBEDDED_KITTEN_MAX_INPUT_CHARS = max(120, int(os.environ.get("EMBEDDED_KITTEN_MAX_INPUT_CHARS", "320")))
except ValueError:
    EMBEDDED_KITTEN_MAX_INPUT_CHARS = 320
try:
    EMBEDDED_KITTEN_CHUNK_SILENCE_MS = max(0, int(os.environ.get("EMBEDDED_KITTEN_CHUNK_SILENCE_MS", "120")))
except ValueError:
    EMBEDDED_KITTEN_CHUNK_SILENCE_MS = 120
try:
    TTS_PROXY_TIMEOUT_SECONDS = max(30.0, float(os.environ.get("TTS_PROXY_TIMEOUT_SECONDS", "120")))
except ValueError:
    TTS_PROXY_TIMEOUT_SECONDS = 120.0

_embedded_kitten_model_instance = None
_embedded_kitten_model_lock = asyncio.Lock()
_embedded_kitten_model_repo_id: Optional[str] = None
_embedded_kitten_voice_aliases: Dict[str, str] = {}

EMBEDDED_KITTEN_COMPAT_VOICE_ALIASES: Dict[str, str] = {
    # OpenAI-style names
    "alloy": "expr-voice-5-m",
    "echo": "expr-voice-2-m",
    "fable": "expr-voice-3-f",
    "onyx": "expr-voice-4-m",
    "nova": "expr-voice-5-f",
    "shimmer": "expr-voice-2-f",
    # Kitten mini aliases and project-specific names seen in configs
    "bella": "expr-voice-2-f",
    "jasper": "expr-voice-2-m",
    "luna": "expr-voice-3-f",
    "bruno": "expr-voice-3-m",
    "rosie": "expr-voice-4-f",
    "hugo": "expr-voice-4-m",
    "kiki": "expr-voice-5-f",
    "leo": "expr-voice-5-m",
    "empress": "expr-voice-4-f",
}


# Import memory system (with error handling)
MEMORY_AVAILABLE = False
MemoryManager = None
memory_import_error = None

try:
    # Check for required dependencies first
    try:
        import numpy
    except ImportError:
        raise ImportError("numpy is required for the memory system. Install with: pip install numpy")
    
    from src.memory import MemoryManager
    MEMORY_AVAILABLE = True
    print("[OK] Memory system imports successful")
except ImportError as e:
    memory_import_error = str(e)
    print(f"[WARN] Memory system not available: {e}")
    if "numpy" in str(e).lower():
        print("   Install numpy with: pip install numpy")
    MEMORY_AVAILABLE = False
    MemoryManager = None
except Exception as e:
    memory_import_error = str(e)
    print(f"[WARN] Memory system not available (unexpected error): {e}")
    MEMORY_AVAILABLE = False
    MemoryManager = None

# Import philosopher mode
try:
    from src.features.philosopher_mode import PhilosopherMode
    PHILOSOPHER_MODE_AVAILABLE = True
    print("[OK] Philosopher mode imports successful")
except ImportError as e:
    print(f"[WARN] Philosopher mode not available: {e}")
    PHILOSOPHER_MODE_AVAILABLE = False
    PhilosopherMode = None
except Exception as e:
    print(f"[WARN] Philosopher mode not available (unexpected error): {e}")
    PHILOSOPHER_MODE_AVAILABLE = False
    PhilosopherMode = None

# Optional embedded Kitten TTS (OpenAI-compatible /v1/audio/speech + /v1/audio/voices)
try:
    from kittentts import KittenTTS as EmbeddedKittenTTS
    EMBEDDED_KITTEN_IMPORT_AVAILABLE = True
except Exception as e:
    EmbeddedKittenTTS = None
    EMBEDDED_KITTEN_IMPORT_AVAILABLE = False
    print(f"[WARN] Embedded Kitten TTS import not available: {e}")

try:
    from huggingface_hub import hf_hub_download as _hf_hub_download
    from kittentts.onnx_model import KittenTTS_1_Onnx as _EmbeddedKittenOnnxModel
    EMBEDDED_KITTEN_FALLBACK_LOADER_AVAILABLE = True
except Exception as e:
    _hf_hub_download = None
    _EmbeddedKittenOnnxModel = None
    EMBEDDED_KITTEN_FALLBACK_LOADER_AVAILABLE = False
    print(f"[WARN] Embedded Kitten fallback loader unavailable: {e}")

# Telegram tool parsing and execution (for Telegram tools parity with web client)
try:
    from src.servers import telegram_tools as _telegram_tools
    TELEGRAM_TOOLS_MODULE_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Telegram tools module not available: {e}")

# Persistent todo store (per-user file storage)
try:
    from src.servers import todo_store as _todo_store
    TODO_STORE_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Todo store not available: {e}")
    _todo_store = None
    TODO_STORE_AVAILABLE = False

# Load environment variables from .env file in project root
if DOTENV_AVAILABLE:
    # Load from project root (two levels up from src/servers/)
    env_path = Path(__file__).resolve().parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment variables from {env_path}")
    else:
        print(f"âš ï¸  No .env file found. Using system environment variables.")
        print(f"   Looked in: {env_path}")
else:
    print("âš ï¸  python-dotenv not available. Using system environment variables only.")

# Primary hostname for SSL cert discovery (same as https_server; configurable via HTTPS_CERT_HOSTNAME in .env)
_SSL_CERT_HOSTNAME = (os.environ.get("HTTPS_CERT_HOSTNAME") or "anton.local").strip()
# Sanitize for glob to avoid matching unintended files
_SSL_CERT_HOSTNAME_GLOB = _SSL_CERT_HOSTNAME.replace("*", "").replace("?", "") or "anton.local"

# Pydantic models for request/response validation
# Note: 'command' is intentionally not accepted from clients; only server-side presets are used.
class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")  # Reject any extra fields (e.g. 'command') in request body

    id: Optional[str] = None
    name: Optional[str] = None
    preset_id: Optional[str] = None  # Required for add/update; must be in MCP_PRESETS
    apiKey: Optional[str] = None
    model: Optional[str] = None
    url: Optional[str] = None
    wsUrl: Optional[str] = None
    status: Optional[str] = None
    enabled: Optional[bool] = None
    action: Optional[str] = None

class ToolCallRequest(BaseModel):
    toolName: str
    parameters: Optional[Dict[str, Any]] = None

# Pydantic models for file operations
class ReadFileRequest(BaseModel):
    filename: str  # Name of the file to read

class WriteFileRequest(BaseModel):
    filename: str  # Name of the file to write
    content: str  # Content to write to the file
    format: Optional[str] = "txt"  # File format (txt, md, docx, xlsx, pdf)

class FileResponse(BaseModel):
    success: bool  # Whether the operation was successful
    message: str  # Human-readable message
    data: Optional[Dict[str, Any]] = None  # Optional data payload

class AuthSignupRequest(BaseModel):
    username: str
    password: str


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str


class AuthUserResponse(BaseModel):
    username: str
    created_at: str


# Todo REST API request/response models (all endpoints require auth)
class TodoRecurrenceRequest(BaseModel):
    frequency: str
    interval: int = Field(default=1, ge=1, le=10000)


class TodoAddRequest(BaseModel):
    taskDescription: str
    scheduledFor: Optional[str] = None
    recurrence: Optional[TodoRecurrenceRequest] = None


class TodoUpdateRequest(BaseModel):
    taskDescription: Optional[str] = None
    scheduledFor: Optional[str] = None
    recurrence: Optional[TodoRecurrenceRequest] = None
    clearSchedule: bool = False
    clearRecurrence: bool = False


class TodoTaskItemResponse(BaseModel):
    taskId: int
    taskDescription: str
    scheduledFor: Optional[str] = None
    nextRunAt: Optional[str] = None
    recurrence: Optional[Dict[str, Any]] = None
    lastCompletedAt: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    isDue: bool = False


class TodoCompletionMetaResponse(BaseModel):
    taskId: int
    rescheduled: bool = False
    nextRunAt: Optional[str] = None


class TodoListResponse(BaseModel):
    tasks: List[str]
    taskItems: List[TodoTaskItemResponse] = []
    updated_at: Optional[str] = None
    completion: Optional[TodoCompletionMetaResponse] = None


class TodoExecuteRequest(BaseModel):
    taskId: int
    promptOverride: Optional[str] = None


class TodoResumeRequest(BaseModel):
    userMessage: str


class CodexExecRequest(BaseModel):
    prompt: str


class TodoExecuteResponse(BaseModel):
    status: str
    message: str
    taskId: Optional[int] = None


class TelegramChatMessage(BaseModel):
    role: str
    content: str


class TelegramChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    history: Optional[List[TelegramChatMessage]] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None


class TelegramChatResponse(BaseModel):
    reply: str
    conversation_id: str
    usage: Optional[Dict[str, Any]] = None


class EmbeddedTtsSpeechRequest(BaseModel):
    model: Optional[str] = None
    voice: Optional[str] = None
    input: str
    response_format: Optional[str] = "wav"
    stream: Optional[bool] = False
    sample_rate: Optional[int] = None
    channels: Optional[int] = 1
    speed: Optional[float] = None


class StatusStartRequest(BaseModel):
    conversation_id: str
    request_id: str
    channel: Optional[str] = "web"
    state: Optional[str] = None


class StatusUpdateRequest(BaseModel):
    conversation_id: str
    request_id: str
    state: str
    phase: Optional[str] = None


class StatusFinishRequest(BaseModel):
    conversation_id: str
    request_id: str
    final_state: Optional[str] = None
    phase: Optional[str] = None

# Pydantic models for memory operations
class MemoryStoreRequest(BaseModel):
    text: str
    category: Optional[str] = None
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class MemorySearchRequest(BaseModel):
    query: str
    limit: Optional[int] = None
    similarity_threshold: Optional[float] = None
    category: Optional[str] = None

class MemoryExtractRequest(BaseModel):
    messages: List[Dict[str, str]]
    max_memories: Optional[int] = 3

class MemoryResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

# Pydantic models for philosopher mode
class PhilosopherStartRequest(BaseModel):
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None

class PhilosopherStopRequest(BaseModel):
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None

class PhilosopherContemplateRequest(BaseModel):
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    question: Optional[str] = None  # Optional: if not provided, generate one

class PhilosopherResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# Pydantic models for companion config API (CATBot tool settings saved as named companions)
class CompanionCreateRequest(BaseModel):
    """Request body for creating a new companion."""
    name: str
    settings: Dict[str, Any]  # Full tool settings snapshot (serializable)


class CompanionResponse(BaseModel):
    """Single companion record (id, name, optional full settings)."""
    id: str
    name: str
    settings: Optional[Dict[str, Any]] = None  # Omitted in list view, included in GET by id


class ProxyFetchRequest(BaseModel):
    """Request body for POST /v1/proxy/fetch (avoids URL length limits on iOS Safari)."""
    url: Optional[str] = None
    urls: Optional[List[str]] = None  # Optional list: try each until one succeeds (scrape-with-retry)
    crawl: bool = True
    max_pages: int = 3
    max_depth: int = 1


# Project root (two levels up from src/servers/proxy_server.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Global state (similar to the Node.js version)
mcp_clients = {}
mcp_servers = {}
SERVERS_FILE = _PROJECT_ROOT / "config" / "mcp_servers.json"

# Server-side allowlist: only these presets may be used for MCP server execution.
# Never execute user-supplied command strings; resolve command/args only from here.
MCP_PRESETS = {
    "browser-use": {"type": "inprocess"},  # No subprocess; handled in-process in call_tool/list_tools
    # Future: "stdio": {"type": "stdio", "command": sys.executable, "allowed_args": [["-m", "mcp_server_browser_use"], ...]},
}
TEAM_CONFIG_FILE = _PROJECT_ROOT / "config" / "team-config.json"
# Optional: same system prompt / rules as web UI; when present, used for Telegram (overrides TELEGRAM_SYSTEM_PROMPT env)
CATBOT_SYSTEM_PROMPT_FILE = _PROJECT_ROOT / "config" / "catbot_system_prompt.txt"
SCRATCH_DIR = _PROJECT_ROOT / "scratch"
# Companion configs stored as one JSON file per companion (server filesystem only)
COMPANIONS_DIR = _PROJECT_ROOT / "config" / "companions"

# Allowed file extensions for scratch file operations (path traversal mitigation)
READ_ALLOWED_EXTENSIONS = {".txt", ".md", ".docx", ".xlsx", ".xls", ".pdf", ".png", ".jpg", ".jpeg", ".py", ".js", ".html"}
WRITE_ALLOWED_EXTENSIONS = {".txt", ".md", ".docx", ".xlsx", ".xls", ".pdf", ".py", ".js", ".html"}
# Allowed extensions for Google Drive upload (scratch workspace only; path exfiltration mitigation)
DRIVE_UPLOAD_EXTENSIONS = {".txt", ".md", ".docx", ".xlsx", ".xls", ".pdf", ".png", ".jpg", ".jpeg"}
# Max file size for read/write in bytes (10MB default), configurable via env
FILE_OPS_MAX_SIZE_BYTES = int(os.getenv("FILE_OPS_MAX_SIZE", "10485760"))

# Telegram chat session storage (simple in-memory cache)
telegram_conversations: Dict[str, List[Dict[str, str]]] = {}
# Per-conversation todo list and memory cache for Telegram tools (same semantics as web client)
telegram_todo: Dict[str, List[str]] = {}
telegram_memory_cache: Dict[str, List[str]] = {}

# Optional: tool-capable system prompt for Telegram when TELEGRAM_TOOLS_ENABLED=true
CATBOT_SYSTEM_PROMPT_WITH_TOOLS_FILE = _PROJECT_ROOT / "config" / "catbot_system_prompt_with_tools.txt"
TELEGRAM_TOOLS_ENABLED = os.getenv("TELEGRAM_TOOLS_ENABLED", "false").lower() == "true"
TELEGRAM_TOOLS_MAX_ITERATIONS = max(1, min(10, int(os.getenv("TELEGRAM_TOOLS_MAX_ITERATIONS", "5"))))
# Automatic memory injection quality controls (Telegram/web auto-context paths)
MEMORY_AUTO_SEARCH_MIN_SIMILARITY = max(
    0.0, min(1.0, float(os.getenv("MEMORY_AUTO_SEARCH_MIN_SIMILARITY", "0.72")))
)
MEMORY_AUTO_SEARCH_CANDIDATE_THRESHOLD = max(
    0.0, min(1.0, float(os.getenv("MEMORY_AUTO_SEARCH_CANDIDATE_THRESHOLD", "0.55")))
)
MEMORY_AUTO_SEARCH_LIMIT = max(1, min(10, int(os.getenv("MEMORY_AUTO_SEARCH_LIMIT", "3"))))
MEMORY_AUTO_SEARCH_SCORE_WINDOW = max(
    0.0, min(1.0, float(os.getenv("MEMORY_AUTO_SEARCH_SCORE_WINDOW", "0.12")))
)
# Optional: map Telegram user_id or conversation_id to app username for shared todo list
TELEGRAM_USER_LINKS_FILE = _PROJECT_ROOT / "config" / "telegram_user_links.json"
_TELEGRAM_CHAT_ID_RE = re.compile(r"^-?\d+$")

# ============================================================================
# STATUS EVENTS (persistent progress updates)
# ============================================================================

STATUS_UPDATE_INTERVAL_SECONDS = max(5, int(os.environ.get("STATUS_UPDATE_INTERVAL_SECONDS", "60")))
STATUS_DATA_DIR = _PROJECT_ROOT / "status_data"
STATUS_EVENTS_FILE = STATUS_DATA_DIR / "status_events.jsonl"


@dataclass
class StatusSession:
    conversation_id: str
    request_id: str
    channel: str
    state: str
    phase: str
    seq: int = 0
    started_at: float = 0.0
    heartbeat_task: Optional[asyncio.Task] = None
    done: bool = False


status_sessions: Dict[Tuple[str, str], StatusSession] = {}
status_latest_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
status_write_lock = asyncio.Lock()


def _ensure_status_storage() -> None:
    STATUS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STATUS_EVENTS_FILE.exists():
        STATUS_EVENTS_FILE.write_text("", encoding="utf-8")


def _tail_text_file(path: Path, max_lines: int = 200, max_bytes: int = 262144) -> str:
    """Return the last max_lines from a text file, reading up to max_bytes from the end."""
    if not path.exists():
        return ""
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            read_size = min(size, max_bytes)
            f.seek(-read_size, os.SEEK_END)
            data = f.read(read_size)
        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        return "\n".join(lines[-max_lines:])
    except Exception as exc:
        print(f"[WARN] Failed to tail file {path}: {exc}")
        return ""


def _get_recent_status_events(limit: int = 50) -> List[Dict[str, Any]]:
    """Read recent status events from the JSONL store."""
    text = _tail_text_file(STATUS_EVENTS_FILE, max_lines=limit * 2)
    events: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events[-limit:]


def _load_status_index() -> None:
    status_latest_index.clear()
    if not STATUS_EVENTS_FILE.exists():
        return
    try:
        with STATUS_EVENTS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                conv = event.get("conversation_id")
                req = event.get("request_id")
                if not conv or not req:
                    continue
                status_latest_index[(conv, req)] = event
    except Exception as exc:
        print(f"[WARN] Failed to load status index: {exc}")


def _init_status_store() -> None:
    _ensure_status_storage()
    _load_status_index()


# Initialize status storage on module load
_init_status_store()


async def _record_status_event(event: Dict[str, Any]) -> None:
    async with status_write_lock:
        try:
            with STATUS_EVENTS_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
            conv = event.get("conversation_id")
            req = event.get("request_id")
            if conv and req:
                status_latest_index[(conv, req)] = event
        except Exception as exc:
            print(f"[WARN] Failed to write status event: {exc}")


async def _emit_status_event(
    session: StatusSession,
    state: Optional[str] = None,
    phase: Optional[str] = None,
    done: bool = False,
    event_type: str = "heartbeat",
) -> Dict[str, Any]:
    if state is not None:
        session.state = state
    if phase is not None:
        session.phase = phase
    session.seq += 1
    now = datetime.now(timezone.utc)
    event = {
        "ts": now.timestamp(),
        "iso": now.isoformat(),
        "conversation_id": session.conversation_id,
        "request_id": session.request_id,
        "channel": session.channel,
        "seq": session.seq,
        "state": session.state,
        "phase": session.phase,
        "done": done,
        "type": event_type,
    }
    await _record_status_event(event)
    return event


async def _status_heartbeat(session: StatusSession) -> None:
    while not session.done:
        await asyncio.sleep(STATUS_UPDATE_INTERVAL_SECONDS)
        if session.done:
            break
        await _emit_status_event(session, event_type="heartbeat")


async def _start_status_session(
    conversation_id: str,
    request_id: str,
    channel: str,
    initial_state: str,
    phase: str = "start",
) -> StatusSession:
    key = (conversation_id, request_id)
    existing = status_sessions.get(key)
    if existing and existing.heartbeat_task:
        existing.done = True
        with suppress(Exception):
            existing.heartbeat_task.cancel()
    session = StatusSession(
        conversation_id=conversation_id,
        request_id=request_id,
        channel=channel,
        state=initial_state,
        phase=phase,
        seq=0,
        started_at=time.time(),
        heartbeat_task=None,
        done=False,
    )
    status_sessions[key] = session
    await _emit_status_event(session, event_type="start")
    session.heartbeat_task = asyncio.create_task(_status_heartbeat(session))
    return session


async def _update_status_session(
    conversation_id: str,
    request_id: str,
    state: str,
    phase: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    key = (conversation_id, request_id)
    session = status_sessions.get(key)
    if not session:
        return None
    return await _emit_status_event(session, state=state, phase=phase, event_type="update")


async def _finish_status_session(
    conversation_id: str,
    request_id: str,
    final_state: Optional[str] = None,
    phase: str = "done",
) -> Optional[Dict[str, Any]]:
    key = (conversation_id, request_id)
    session = status_sessions.get(key)
    if not session:
        return None
    if final_state:
        session.state = final_state
    session.done = True
    event = await _emit_status_event(session, phase=phase, done=True, event_type="finish")
    if session.heartbeat_task:
        with suppress(Exception):
            session.heartbeat_task.cancel()
    status_sessions.pop(key, None)
    return event


def _get_latest_status_event(
    conversation_id: str,
    request_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if request_id:
        event = status_latest_index.get((conversation_id, request_id))
        if event:
            return event
    # Fallback: scan file for latest event for conversation
    if not STATUS_EVENTS_FILE.exists():
        return None
    latest = None
    try:
        with STATUS_EVENTS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("conversation_id") != conversation_id:
                    continue
                if request_id and event.get("request_id") != request_id:
                    continue
                latest = event
    except Exception as exc:
        print(f"[WARN] Failed reading status events: {exc}")
    return latest


def _get_status_events_since(
    conversation_id: str,
    request_id: str,
    since_seq: int,
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if not STATUS_EVENTS_FILE.exists():
        return events
    try:
        with STATUS_EVENTS_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("conversation_id") != conversation_id:
                    continue
                if event.get("request_id") != request_id:
                    continue
                seq = event.get("seq") or 0
                if seq > since_seq:
                    events.append(event)
    except Exception as exc:
        print(f"[WARN] Failed reading status events: {exc}")
    return events


def _load_telegram_user_links() -> Dict[str, str]:
    """Load Telegram user-link mappings from config/telegram_user_links.json."""
    mapping: Dict[str, str] = {}
    if not TELEGRAM_USER_LINKS_FILE.exists():
        return mapping
    try:
        raw = TELEGRAM_USER_LINKS_FILE.read_text(encoding="utf-8")
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            return mapping
        for key, value in loaded.items():
            key_text = str(key or "").strip()
            value_text = str(value or "").strip()
            if key_text and value_text:
                mapping[key_text] = value_text
    except (json.JSONDecodeError, OSError):
        return {}
    return mapping


def _resolve_todo_user_for_telegram(conversation_id: str, user_id: Optional[str]) -> str:
    """
    Resolve the todo user key for Telegram: if telegram_user_links.json maps this conversation
    or user to an app username, return that; else return conversation_id (or user_id) for persistent per-chat todo.
    """
    mapping = _load_telegram_user_links()
    # Normalize to string (API may send user_id as number)
    uid = str(user_id or "").strip()
    cid = str(conversation_id or "").strip() or "default"
    if uid and uid in mapping:
        return str(mapping[uid]).strip() or cid
    if cid in mapping:
        return str(mapping[cid]).strip() or cid
    return cid


def _resolve_telegram_chat_ids_for_todo_user(user_key: str) -> List[str]:
    """
    Resolve Telegram chat IDs that should receive task-execution notifications for a todo user key.

    Supports:
    - direct numeric user_key values (Telegram chat/user IDs)
    - reverse lookup in telegram_user_links.json where value == user_key
    """
    key = str(user_key or "").strip()
    if not key:
        return []
    chat_ids: List[str] = []
    if _TELEGRAM_CHAT_ID_RE.match(key):
        chat_ids.append(key)
    mapping = _load_telegram_user_links()
    for tg_id, mapped_user in mapping.items():
        if mapped_user != key:
            continue
        tg_id_text = str(tg_id or "").strip()
        if tg_id_text and _TELEGRAM_CHAT_ID_RE.match(tg_id_text):
            chat_ids.append(tg_id_text)
    return list(dict.fromkeys(chat_ids))


def _task_execution_register_telegram_target(user_key: str, chat_id: Optional[Any]) -> bool:
    """Attach a Telegram chat ID to an in-flight task execution so completion can notify the user."""
    state = task_execution_state.get(user_key)
    if not state:
        return False
    chat_id_text = str(chat_id or "").strip()
    if not chat_id_text or not _TELEGRAM_CHAT_ID_RE.match(chat_id_text):
        return False
    existing = state.get("telegram_chat_ids")
    if not isinstance(existing, list):
        existing = []
        state["telegram_chat_ids"] = existing
    if chat_id_text not in existing:
        existing.append(chat_id_text)
    return True


def _build_task_execution_telegram_message(
    *,
    task_id: Optional[int],
    task_description: str,
    status: str,
    result_message: str,
) -> str:
    now_utc = datetime.now(timezone.utc).isoformat()
    body = (result_message or "").strip()
    if len(body) > 1800:
        body = body[:1800].rstrip() + "\n...[truncated]"
    lines = [
        "Scheduled task execution completed.",
        f"Task ID: {task_id if task_id is not None else 'unknown'}",
        f"Task: {task_description or '(no description)'}",
        f"Status: {status or 'unknown'}",
        f"Completed at (UTC): {now_utc}",
    ]
    if body:
        lines.append("")
        lines.append("Result:")
        lines.append(body)
    return "\n".join(lines)


async def _send_telegram_bot_message(chat_id: str, text: str) -> bool:
    """Send a direct Telegram message via Bot API. Returns True when sent successfully."""
    token = str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id_text = str(chat_id or "").strip()
    message_text = (text or "").strip()
    if not token or not chat_id_text or not message_text:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id_text, "text": message_text}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload)
        if response.status_code != 200:
            print(f"[WARN] Telegram sendMessage failed ({response.status_code}) for chat_id={chat_id_text}", flush=True)
            return False
        data = response.json()
        ok = bool(data.get("ok"))
        if not ok:
            print(f"[WARN] Telegram sendMessage returned ok=false for chat_id={chat_id_text}", flush=True)
        return ok
    except Exception as exc:
        print(f"[WARN] Telegram sendMessage error for chat_id={chat_id_text}: {exc}", flush=True)
        return False


async def _maybe_notify_telegram_task_completion(
    user_key: str,
    state: Dict[str, Any],
    status: str,
    message: str,
) -> None:
    """
    Send Telegram notification when a scheduled task execution reaches completion state.
    No-op when task is not scheduled or no resolvable Telegram chat IDs are available.
    """
    if status != STATUS_AWAITING_CONFIRMATION:
        return
    if not bool(state.get("is_scheduled")):
        return
    chat_ids = state.get("telegram_chat_ids")
    if not isinstance(chat_ids, list) or not chat_ids:
        return
    text = _build_task_execution_telegram_message(
        task_id=state.get("task_id"),
        task_description=str(state.get("task_description") or ""),
        status=status,
        result_message=message or "",
    )
    for chat_id in chat_ids:
        await _send_telegram_bot_message(str(chat_id), text)

# Philosopher mode state storage (per conversation)
philosopher_mode_active: Dict[str, bool] = {}
philosopher_mode_instances: Dict[str, Any] = {}

# Task execution: max iterations per run (configurable via .env)
TASK_EXECUTION_MAX_ITERATIONS = max(1, min(200, int(os.getenv("TASK_EXECUTION_MAX_ITERATIONS", "200"))))
# Per-user execution state: user_key -> { "task_id", "status", "executor" } (executor held for resume)
task_execution_state: Dict[str, Dict[str, Any]] = {}

# Task execution module (bounded LLM+tools loop for todo tasks)
try:
    from src.features.task_execution import TodoTaskExecutor
    from src.features.task_execution import (
        STATUS_EXECUTING,
        STATUS_PAUSED_AWAITING_FEEDBACK,
        STATUS_AWAITING_CONFIRMATION,
        STATUS_CANCELLED,
    )
    TASK_EXECUTION_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Task execution not available: {e}")
    TodoTaskExecutor = None
    TASK_EXECUTION_AVAILABLE = False
    STATUS_EXECUTING = "executing"
    STATUS_PAUSED_AWAITING_FEEDBACK = "paused_awaiting_feedback"
    STATUS_AWAITING_CONFIRMATION = "awaiting_confirmation"
    STATUS_CANCELLED = "cancelled"

# Assistant context: current date, timezone, and knowledge-gap awareness (prepended to all chat system prompts)
def _get_assistant_context_block() -> str:
    """Returns context block with server date, timezone, and knowledge-awareness instructions."""
    now = datetime.now().astimezone()
    date_str = now.strftime("%A, %d %B %Y")  # e.g. Thursday, 13 February 2025
    tz_str = now.strftime("%Z (UTC%z)")
    return (
        f"Context: Today's date is {date_str}. You are running in timezone {tz_str}. "
        "Use this when interpreting dates, times, and relative references (e.g. 'today', 'this week') unless the user specifies otherwise.\n"
        "Knowledge awareness: Your training has a cutoff. Acknowledge your knowledge gap; do not assume the current year or recent events. "
        "When the user provides current facts, corrections, or information that differs from your training "
        '(e.g., "it\'s 2025 now", "that API changed"), accept them as authoritative and do not contradict them.\n\n'
    )


def _normalize_chat_endpoint(endpoint: str) -> str:
    if not endpoint:
        return ""
    if endpoint.endswith("/chat/completions"):
        return endpoint
    return endpoint.rstrip("/") + "/chat/completions"


def _estimate_total_tokens(messages: List[Dict[str, Any]], max_tokens: int) -> int:
    return estimate_tokens_from_messages(messages) + max_tokens


def _get_max_tokens_from_payload(payload: Dict[str, Any]) -> int:
    raw = payload.get("max_tokens")
    try:
        if raw is None:
            return 0
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


async def _call_chat_completion(
    endpoint: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: float = 120.0,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        return await client.post(endpoint, json=payload, headers=headers)


async def _summarize_messages_for_budget_proxy(
    messages: List[Dict[str, Any]],
    endpoint: str,
    headers: Dict[str, str],
    model_name: str,
    max_tokens: int,
    large_model: Optional[str] = None,
    large_endpoint: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not messages:
        return messages

    system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
    remainder = messages[1:] if system_msg else messages[:]
    if len(remainder) <= 4:
        return messages

    keep_tail_options = [8, 6, 4, 2]
    for keep_tail in keep_tail_options:
        if len(remainder) <= keep_tail:
            continue
        head = remainder[:-keep_tail]
        tail = remainder[-keep_tail:]
        summary_source_text = format_messages_for_summary(head, max_chars=40000)
        if not summary_source_text.strip():
            break

        summary_prompt = (
            "Summarize the prior conversation so the assistant can continue accurately. "
            "Include key requirements, decisions, file paths, commands, tool outputs, errors, "
            "and remaining TODOs. Keep it concise and structured."
        )
        summary_messages = [
            {"role": "system", "content": "You are a summarization assistant. Summarize accurately and concisely."},
            {"role": "user", "content": f"{summary_prompt}\n\nConversation:\n{summary_source_text}"},
        ]

        summary_model = large_model or model_name
        summary_endpoint = _normalize_chat_endpoint(large_endpoint or endpoint)
        summary_payload = {
            "model": summary_model,
            "messages": summary_messages,
            "temperature": 0.2,
            "max_tokens": 800,
        }
        try:
            summary_response = await _call_chat_completion(summary_endpoint, headers, summary_payload, timeout_seconds=120.0)
            if summary_response.status_code == 200:
                data = summary_response.json()
                summary_text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
            else:
                summary_text = ""
        except Exception:
            summary_text = ""

        if not summary_text:
            summary_text = summary_source_text[-2000:] if summary_source_text else ""

        new_messages: List[Dict[str, Any]] = []
        if system_msg:
            new_messages.append(system_msg)
        new_messages.append({"role": "system", "content": f"Summary of previous context:\n{summary_text}"})
        new_messages.extend(tail)

        if _estimate_total_tokens(new_messages, max_tokens) <= get_max_token_limit():
            return new_messages

    return messages


# Telegram/OpenAI configuration
def _parse_telegram_history_limit() -> int:
    """Parse TELEGRAM_HISTORY_LIMIT with default 12 on invalid value."""
    try:
        return max(1, int(os.getenv("TELEGRAM_HISTORY_LIMIT", "12")))
    except ValueError:
        return 12


def _parse_telegram_chat_timeout() -> float:
    """Parse TELEGRAM_CHAT_TIMEOUT with default 30 on invalid value."""
    try:
        return max(1.0, float(os.getenv("TELEGRAM_CHAT_TIMEOUT", "30")))
    except ValueError:
        return 30.0


TELEGRAM_DEFAULT_MODEL = os.getenv("TELEGRAM_MODEL") or os.getenv("OPENAI_MODEL") or os.getenv("MCP_LLM_MODEL_NAME", "gpt-4o-mini")
TELEGRAM_SYSTEM_PROMPT_ENV = os.getenv(
    "TELEGRAM_SYSTEM_PROMPT",
    "You are CATBot, a helpful AI assistant that responds concisely for Telegram users.",
)


def _get_telegram_system_prompt_base() -> str:
    """Return the base system prompt for Telegram: config file if present, else TELEGRAM_SYSTEM_PROMPT env."""
    if CATBOT_SYSTEM_PROMPT_FILE.exists():
        try:
            content = CATBOT_SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
            if content:
                return content
        except Exception as e:
            print(f"Warning: Could not read {CATBOT_SYSTEM_PROMPT_FILE}: {e}")
    return TELEGRAM_SYSTEM_PROMPT_ENV


def _get_telegram_system_prompt_with_tools(conversation_id: str, todo_user_key: Optional[str] = None) -> str:
    """Return the tool-capable system prompt for Telegram, with current todo and memory cache for this conversation."""
    content = ""
    if CATBOT_SYSTEM_PROMPT_WITH_TOOLS_FILE.exists():
        try:
            content = CATBOT_SYSTEM_PROMPT_WITH_TOOLS_FILE.read_text(encoding="utf-8").strip()
        except Exception as e:
            print(f"Warning: Could not read {CATBOT_SYSTEM_PROMPT_WITH_TOOLS_FILE}: {e}")
    if not content:
        content = _get_telegram_system_prompt_base()
    # Use persistent todo store when available and todo_user_key provided; else in-memory fallback
    if todo_user_key and TODO_STORE_AVAILABLE and _todo_store:
        todo_list = _todo_store.load_tasks(todo_user_key)
    else:
        todo_list = telegram_todo.get(conversation_id, [])
    mem_cache = telegram_memory_cache.get(conversation_id, [])
    todo_block = "\n".join([f"{i + 1}. {t}" for i, t in enumerate(todo_list)]) if todo_list else "(empty)"
    mem_block = "\n".join([f"{i + 1}. {m}" for i, m in enumerate(mem_cache)]) if mem_cache else "(empty)"
    content = content.replace("{{MEMORY_CACHE}}", mem_block).replace("{{TODO_LIST}}", todo_block)
    return content


TELEGRAM_HISTORY_LIMIT = _parse_telegram_history_limit()
TELEGRAM_CHAT_TIMEOUT = _parse_telegram_chat_timeout()
TELEGRAM_OPENAI_BASE_URL = (
    os.getenv("TELEGRAM_OPENAI_BASE_URL")
    or os.getenv("OPENAI_API_BASE")
    or os.getenv("MCP_LLM_OPENAI_ENDPOINT")
    or "https://api.openai.com/v1"
)
TELEGRAM_OPENAI_CHAT_PATH = os.getenv("TELEGRAM_OPENAI_CHAT_PATH", "/chat/completions")
OPENAI_ORG_ID = os.getenv("OPENAI_ORG_ID") or os.getenv("OPENAI_ORGANIZATION")
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID")
# Optional shared secret for bot-to-proxy auth; when set, requests must include X-Telegram-Secret or Authorization: Bearer <secret>
TELEGRAM_SECRET = os.getenv("TELEGRAM_SECRET")

# Large payload model fallback (optional)
LARGE_PAYLOAD_MODEL = (os.getenv("LARGE_PAYLOAD_MODEL") or "").strip() or None
LARGE_PAYLOAD_ENDPOINT = (os.getenv("LARGE_PAYLOAD_ENDPOINT") or "").strip() or None

# Codex CLI configuration
CODEX_ENABLED = os.getenv("CODEX_ENABLED", "true").lower() == "true"
CODEX_CLI_PATH = (os.getenv("CODEX_CLI_PATH") or "codex").strip() or "codex"
CODEX_SANDBOX_MODE = (os.getenv("CODEX_SANDBOX_MODE") or "workspace-write").strip() or "workspace-write"
CODEX_APPROVAL_POLICY = (os.getenv("CODEX_APPROVAL_POLICY") or "never").strip() or "never"
CODEX_ENABLE_SEARCH = os.getenv("CODEX_ENABLE_SEARCH", "true").lower() == "true"
CODEX_TIMEOUT_SECONDS = int(os.getenv("CODEX_TIMEOUT_SECONDS", "1800"))
CODEX_JSON_EVENTS = os.getenv("CODEX_JSON_EVENTS", "true").lower() == "true"
CODEX_OUTPUT_LAST_MESSAGE = os.getenv("CODEX_OUTPUT_LAST_MESSAGE", "true").lower() == "true"

# Auth configuration
AUTH_USERS_FILE = _PROJECT_ROOT / "config" / "auth_users.json"
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = int(os.getenv("JWT_EXPIRATION_SECONDS", "3600"))

# Simple in-memory user storage with JSON persistence
users_db: Dict[str, Dict[str, str]] = {}


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def hash_password(password: str, salt: str) -> str:
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return _base64url_encode(hashed)


def create_password_record(password: str) -> Dict[str, str]:
    salt = secrets.token_hex(16)
    return {
        "salt": salt,
        "password_hash": hash_password(password, salt),
    }


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    candidate_hash = hash_password(password, salt)
    return hmac.compare_digest(candidate_hash, expected_hash)


def save_users_db() -> None:
    AUTH_USERS_FILE.write_text(json.dumps(users_db, indent=2), encoding="utf-8")


def load_users_db() -> None:
    global users_db
    if not AUTH_USERS_FILE.exists():
        users_db = {}
        return

    try:
        users_db = json.loads(AUTH_USERS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"âš ï¸ Failed to load users database: {e}")
        users_db = {}


def create_jwt(payload: Dict[str, Any], expires_in: int = JWT_EXPIRATION_SECONDS) -> str:
    now = datetime.now(timezone.utc)
    body = payload.copy()
    body["iat"] = int(now.timestamp())
    body["exp"] = int((now + timedelta(seconds=expires_in)).timestamp())

    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    header_b64 = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _base64url_encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_and_validate_jwt(token: str) -> Dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token format") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_sig = _base64url_decode(signature_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    try:
        payload = json.loads(_base64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token payload") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise HTTPException(status_code=401, detail="Token missing expiration")
    if datetime.now(timezone.utc).timestamp() > exp:
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


def get_current_user_from_headers(authorization: Optional[str], x_auth_token: Optional[str]) -> Dict[str, Any]:
    auth_value = authorization
    if not auth_value and x_auth_token:
        auth_value = f"Bearer {x_auth_token}"

    if not auth_value:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Strip whitespace and handle potential formatting issues
    auth_value = auth_value.strip()
    
    try:
        scheme, token = auth_value.split(" ", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Authorization header") from exc

    # Strip token whitespace as well
    token = token.strip()
    
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization scheme must be Bearer")

    # Debug logging for token issues
    if not token or len(token.split(".")) != 3:
        print(f"🔒 Token format issue - token length: {len(token) if token else 0}, parts: {len(token.split('.')) if token else 0}")
        print(f"   Token preview: {token[:50] if token else 'None'}...")
        raise HTTPException(status_code=401, detail="Invalid token format")

    payload = decode_and_validate_jwt(token)
    username = payload.get("sub")
    if not username or username not in users_db:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    return {"username": username, **users_db[username]}


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    x_auth_token: Optional[str] = Header(default=None, alias="X-Auth-Token"),
) -> Dict[str, Any]:
    return get_current_user_from_headers(authorization, x_auth_token)


def security_log(action: str, user: str, server_id: Optional[str], detail: str) -> None:
    """Log MCP config/connect actions for audit; do not log secrets."""
    ts = datetime.now(timezone.utc).isoformat()
    sid = server_id or ""
    print(f"[SEC] {ts} action={action} user={user} server_id={sid} detail={detail}", flush=True)


# Helper utilities for Telegram integration
def build_openai_url(path: str) -> str:
    """Return absolute URL for OpenAI-compatible endpoints."""

    if path.startswith("http://") or path.startswith("https://"):
        return path

    base = TELEGRAM_OPENAI_BASE_URL.rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def trim_telegram_history(history: List[Dict[str, str]]) -> None:
    """Trim stored history to the configured limit (in-place)."""

    max_messages = max(TELEGRAM_HISTORY_LIMIT, 1) * 2
    if len(history) > max_messages:
        del history[: len(history) - max_messages]


def _validate_telegram_secret(request: Request) -> None:
    """If TELEGRAM_SECRET is set, require X-Telegram-Secret or Authorization Bearer to match; else raise 401."""
    if not TELEGRAM_SECRET:
        return
    secret_header = request.headers.get("X-Telegram-Secret")
    auth_header = request.headers.get("Authorization")
    token = None
    if secret_header is not None and secret_header.strip() == TELEGRAM_SECRET:
        token = TELEGRAM_SECRET
    if auth_header and auth_header.strip().startswith("Bearer "):
        token = auth_header.strip()[7:].strip()
    if token != TELEGRAM_SECRET:
        raise HTTPException(status_code=401, detail="Telegram secret required or invalid")


# Create scratch and companions directories if they don't exist
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
COMPANIONS_DIR.mkdir(parents=True, exist_ok=True)
load_users_db()

# Global AutoGen team instance
autogen_team = None

# Global memory manager instance
memory_manager = None

# Initialize memory manager if available
if MEMORY_AVAILABLE:
    try:
        memory_enabled = os.getenv("MEMORY_ENABLED", "true").lower() == "true"
        if memory_enabled:
            memory_manager = MemoryManager()
            print(f"✅ Memory system initialized with {memory_manager.count()} existing memories")
        else:
            print("âš ï¸  Memory system disabled via MEMORY_ENABLED=false")
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"âš ï¸  Failed to initialize memory system: {e}")
        print(f"   Full traceback:\n{error_trace}")
        memory_manager = None

# MCP Client Manager class to handle transport lifecycle
class MCPClientManager:
    """Manages MCP client and transport lifecycle."""

    def __init__(self, server_config: Dict[str, Any]):
        self.server_config = server_config
        self.client = None
        self.transport = None
        self.read = None
        self.write = None

    async def connect(self):
        """Connect to MCP server using server-side allowlisted preset only; never execute user-supplied command."""
        if not MCP_AVAILABLE:
            raise Exception("MCP SDK not available")

        preset_id = self.server_config.get("preset_id")
        if not preset_id or preset_id not in MCP_PRESETS:
            raise ValueError(
                "Server has no valid preset_id. Reconfigure the server with a preset (e.g. preset_id: 'browser-use')."
            )
        preset = MCP_PRESETS[preset_id]
        if preset.get("type") == "inprocess":
            # browser-use: connect is handled in connect_server without calling this code path
            raise ValueError(
                f"Preset '{preset_id}' is inprocess; connect is handled separately. Do not call MCPClientManager.connect for this preset."
            )
        if preset.get("type") != "stdio":
            raise ValueError(
                f"Preset '{preset_id}' has no executable command. Reconfigure the server with a valid stdio preset."
            )

        # Resolve command and args only from allowlist; never use server_config['command']
        command = preset.get("command")
        allowed_args = preset.get("allowed_args", [])
        if not command or not allowed_args:
            raise ValueError(f"Preset '{preset_id}' has no command/args defined in MCP_PRESETS.")
        # Use first allowed_args entry for this preset (e.g. ["-m", "mcp_server_browser_use"])
        args = list(allowed_args[0]) if isinstance(allowed_args[0], (list, tuple)) else []

        try:
            print(f"🔧 Creating MCP client with command: {command} and args: {args}")

            # Prepare environment variables from server config (apiKey, model only)
            env = os.environ.copy()
            if self.server_config.get("apiKey"):
                model = self.server_config.get("model", "").lower()
                if "gemini" in model:
                    env["GOOGLE_API_KEY"] = self.server_config["apiKey"]
                    env["MCP_MODEL_PROVIDER"] = "google"
                elif "claude" in model:
                    env["ANTHROPIC_API_KEY"] = self.server_config["apiKey"]
                    env["MCP_MODEL_PROVIDER"] = "anthropic"
                else:
                    env["OPENAI_API_KEY"] = self.server_config["apiKey"]
                    env["MCP_MODEL_PROVIDER"] = "openai"
            if self.server_config.get("model"):
                env["MCP_MODEL_NAME"] = self.server_config["model"]
            env.setdefault("BROWSER_USE_HEADLESS", "true")
            env.setdefault("BROWSER_USE_DISABLE_SECURITY", "false")

            print(f"ðŸ” Environment variables for MCP server: {list(env.keys())}")

            server_params = StdioServerParameters(command=command, args=args, env=env)

            try:
                transport_cm = stdio_client(server_params)
                async with transport_cm as (self.read, self.write):
                    self.client = ClientSession(self.read, self.write)
                    await self.client.initialize()
                    print("✅ MCP client setup complete")
                    return self.client
            except Exception as e:
                print(f"Failed to create stdio client: {e}")
                raise

        except Exception as e:
            print(f"MCP connection error: {e}")
            raise Exception(f"Failed to connect to MCP server: {str(e)}")

    async def disconnect(self):
        """Disconnect from MCP server."""
        if self.client:
            await self.client.close()
        if self.transport:
            # The transport context manager will handle cleanup
            pass

# FastAPI app
app = FastAPI(title="CATBot Proxy Server", version="2.0.0")

# Startup event to verify app initialization
@app.on_event("startup")
async def startup_event():
    """Log that the application has started successfully."""
    import sys
    print("🚀 FastAPI application startup event fired", flush=True)
    sys.stdout.flush()
    print(f"🚀 App routes registered: {len(app.routes)} routes", flush=True)
    sys.stdout.flush()
    # List all registered routes
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            print(f"   Route: {list(route.methods)} {route.path}", flush=True)
            sys.stdout.flush()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop AutoGen code executors (e.g. Docker containers) on app shutdown."""
    global autogen_team
    if autogen_team is not None:
        await _stop_code_executors(autogen_team)
        autogen_team = None

# Request logging middleware to debug CORS issues
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming requests for debugging."""
    async def dispatch(self, request: Request, call_next):
        import sys
        # Safely log the incoming request with error handling
        try:
            method = getattr(request, 'method', 'UNKNOWN')
            path = getattr(request.url, 'path', 'unknown') if hasattr(request, 'url') else 'unknown'
            query = getattr(request.url, 'query', '') if hasattr(request, 'url') and hasattr(request.url, 'query') else ''
            origin = request.headers.get('origin', 'none') if hasattr(request, 'headers') else 'none'
            print(f"ðŸŒ [{method}] {path}?{query}", flush=True)
            sys.stdout.flush()
            print(f"   Origin: {origin}", flush=True)
            sys.stdout.flush()
            if hasattr(request, 'headers'):
                print(f"   Headers: {dict(request.headers)}", flush=True)
                sys.stdout.flush()
        except Exception as log_error:
            # If logging fails, continue anyway - don't break the request
            print(f"âš ï¸ Error logging request: {log_error}", flush=True)
            sys.stdout.flush()
            import traceback
            print(traceback.format_exc(), flush=True)
            sys.stdout.flush()
        
        try:
            # Process the request
            response = await call_next(request)
            # Log successful response
            try:
                method = getattr(request, 'method', 'UNKNOWN')
                path = getattr(request.url, 'path', 'unknown') if hasattr(request, 'url') else 'unknown'
                status = getattr(response, 'status_code', 'unknown')
                print(f"✅ [{method}] {path} -> {status}", flush=True)
                sys.stdout.flush()
            except Exception as log_err:
                print(f"âš ï¸ Error logging response: {log_err}", flush=True)
                sys.stdout.flush()
            return response
        except Exception as e:
            # Log the exception
            try:
                method = getattr(request, 'method', 'UNKNOWN')
                path = getattr(request.url, 'path', 'unknown') if hasattr(request, 'url') else 'unknown'
                print(f"âŒ [{method}] {path} -> Exception: {e}", flush=True)
                sys.stdout.flush()
                import traceback
                print(traceback.format_exc(), flush=True)
                sys.stdout.flush()
            except Exception:
                print("âŒ Error in exception logging", flush=True)
                sys.stdout.flush()
            # Re-raise the exception so it can be handled by exception handlers
            raise

# Add request logging middleware first (before CORS)
app.add_middleware(RequestLoggingMiddleware)

# Add CORS middleware
# Allow specific origins for development and production
# Note: Using allow_credentials=False allows more flexible origin matching
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development (be more permissive to debug)
    allow_credentials=False,  # Set to False to allow more flexible CORS handling
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*", "Authorization", "X-Auth-Token", "Content-Type", "Accept"],  # Explicitly allow Authorization header
    expose_headers=["*"],
)


@app.middleware("http")
async def require_auth_for_v1_routes(request: Request, call_next):
    path = request.url.path

    if request.method == "OPTIONS":
        return await call_next(request)

    # Exempt certain routes from authentication (public endpoints)
    exempt_paths = {
        "/v1/auth/signup",
        "/v1/auth/login",
        "/v1/tools/log",  # Tool invocation log sink for HTML UI tool calls
        "/v1/audio/transcriptions",  # Whisper endpoint - public for audio transcription
        "/v1/audio/speech",  # Embedded OpenAI-compatible TTS speech endpoint
        "/v1/audio/voices",  # Embedded OpenAI-compatible TTS voices endpoint
        "/v1/proxy/chat/completions",  # Chat completions proxy - public to avoid mixed content
        "/v1/proxy/models",  # Models list proxy - public to avoid mixed content
        "/v1/proxy/autogen",  # AutoGen workflow proxy - public to avoid mixed content
        "/v1/proxy/browser-agent",  # Browser automation proxy - public to avoid mixed content
        "/v1/proxy/deep-research",  # Deep research proxy - public to avoid mixed content
        "/v1/proxy/tts/voices",  # TTS voices endpoint - public
        "/v1/proxy/tts/speech",  # TTS speech endpoint - public
        "/v1/proxy/search",  # Search proxy - public
        "/v1/proxy/news",  # News proxy - public
        "/v1/proxy/fetch",  # Web fetch proxy - public
        "/v1/status/start",
        "/v1/status/update",
        "/v1/status/finish",
        "/v1/status/latest",
        "/v1/status/events",
    }
    # Telegram bot endpoints are unauthenticated (bot uses TELEGRAM_SECRET when set)
    require_auth = (
        path.startswith("/v1/")
        and path not in exempt_paths
        and not path.startswith("/v1/telegram/chat")
    )
    if require_auth:
        try:
            # Get authorization header - FastAPI headers are case-insensitive, but check both for robustness
            # Use get() with case-insensitive lookup
            auth_header = None
            x_auth_token = None
            
            # Try to get authorization header (case-insensitive)
            for key, value in request.headers.items():
                if key.lower() == "authorization":
                    auth_header = value
                    break
                elif key.lower() == "x-auth-token":
                    x_auth_token = value
                    break
            
            # Fallback to direct get if not found in loop
            if not auth_header:
                auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
            if not x_auth_token:
                x_auth_token = request.headers.get("x-auth-token") or request.headers.get("X-Auth-Token")
            
            # Debug logging for auth issues
            if not auth_header and not x_auth_token:
                print(f"🔒 Auth check failed for {path}: No authorization header found")
                print(f"   Available headers: {list(request.headers.keys())}")
            elif auth_header:
                # Log token preview for debugging (first 50 chars)
                token_preview = auth_header[:50] + "..." if len(auth_header) > 50 else auth_header
                print(f"🔒 Auth check for {path}: Found auth header (length: {len(auth_header)}, preview: {token_preview})")
            
            get_current_user_from_headers(
                auth_header,
                x_auth_token,
            )
        except HTTPException as exc:
            print(f"🔒 Auth check failed for {path}: {exc.detail}")
            # Log the actual header value for debugging (truncated)
            auth_debug = request.headers.get("authorization") or request.headers.get("Authorization") or "None"
            if auth_debug != "None":
                print(f"   Auth header value (first 100 chars): {auth_debug[:100]}")
            # Include CORS headers in error response
            cors_headers = build_cors_headers(request)
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=cors_headers
            )

    return await call_next(request)

def build_cors_headers(request: Request) -> Dict[str, str]:
    """Build CORS headers for the request origin. Supports both localhost and remote access."""
    try:
        # Safely get origin from request headers, with fallback
        if hasattr(request, 'headers'):
            origin = request.headers.get("origin")
            # If no origin header (e.g., same-origin request), allow all origins for network access
            if not origin:
                origin = "*"
        else:
            origin = "*"
    except Exception:
        # If we can't access headers, allow all origins for network access
        origin = "*"
    
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
        "Access-Control-Allow-Headers": "*",
    }

# Global exception handler to ensure CORS headers are always included
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions and ensure CORS headers are included."""
    # Safely build CORS headers - if this fails, use minimal headers
    try:
        cors_headers = build_cors_headers(request)
    except Exception as header_error:
        print(f"âš ï¸ Error building CORS headers in HTTPException handler: {header_error}")
        # Use minimal safe headers if build_cors_headers fails
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
        }
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=cors_headers,
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors and ensure CORS headers are included."""
    # Safely build CORS headers - if this fails, use minimal headers
    try:
        cors_headers = build_cors_headers(request)
    except Exception as header_error:
        print(f"âš ï¸ Error building CORS headers in ValidationException handler: {header_error}")
        # Use minimal safe headers if build_cors_headers fails
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
        }
    
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
        headers=cors_headers,
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions and ensure CORS headers are included."""
    import sys
    import traceback
    error_trace = traceback.format_exc()
    print(f"âŒ Unhandled exception in general_exception_handler: {exc}", flush=True)
    sys.stdout.flush()
    print(error_trace, flush=True)
    sys.stdout.flush()
    
    # Safely build CORS headers - if this fails, use minimal headers
    try:
        cors_headers = build_cors_headers(request)
    except Exception as header_error:
        print(f"âš ï¸ Error building CORS headers: {header_error}", flush=True)
        sys.stdout.flush()
        import traceback
        print(traceback.format_exc(), flush=True)
        sys.stdout.flush()
        # Use minimal safe headers if build_cors_headers fails
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "*",
        }
    
    try:
        response = JSONResponse(
            status_code=500,
            content={"detail": f"Internal server error: {str(exc)}"},
            headers=cors_headers,
        )
        print(f"✅ Created error response with status 500", flush=True)
        sys.stdout.flush()
        return response
    except Exception as response_error:
        print(f"âŒ Error creating error response: {response_error}", flush=True)
        sys.stdout.flush()
        import traceback
        print(traceback.format_exc(), flush=True)
        sys.stdout.flush()
        # Last resort - return a simple response
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=f"Internal server error: {str(exc)}",
            status_code=500,
            headers=cors_headers,
        )

# Helper function to clean HTML text (similar to Node.js version)
def clean_text(text: str) -> str:
    """Clean HTML text by removing tags and decoding entities."""
    if not text:
        return ""

    # Remove HTML tags
    text = re.sub(r'</?[^>]+(>|$)', '', text)

    # Decode HTML entities
    html_entities = {
        '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#039;': "'",
        '&rsquo;': "'", '&lsquo;': "'", '&rdquo;': '"', '&ldquo;': '"',
        '&ndash;': '-', '&mdash;': '—'
    }

    for entity, replacement in html_entities.items():
        text = text.replace(entity, replacement)

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# Helper function to parse dates (similar to Node.js version)
def parse_date(date_str: Optional[str]) -> Optional[float]:
    """Parse date string to timestamp."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).timestamp()
    except (ValueError, AttributeError):
        return None

# Load servers from disk; migrate legacy 'command' to preset_id and never retain command
def load_servers():
    """Load MCP servers from JSON file. Migrate legacy config: set preset_id from name, drop command."""
    global mcp_servers
    try:
        if SERVERS_FILE.exists():
            with open(SERVERS_FILE, "r", encoding="utf-8") as f:
                servers = json.load(f)
            result = {}
            for server in servers:
                sid = server.get("id")
                if not sid:
                    continue
                # Migrate: infer preset_id from name when missing (browser-use detection)
                if not server.get("preset_id"):
                    name = (server.get("name") or "").lower()
                    if "mcp-browser-use" in name or "browser-use" in name or ("browser" in name and "use" in name):
                        server["preset_id"] = "browser-use"
                # Never retain command in memory
                server.pop("command", None)
                result[sid] = server
            mcp_servers = result
            print(f"Loaded {len(mcp_servers)} MCP servers from disk")
    except Exception as e:
        print(f"No existing servers file found, starting with empty state: {e}")

# Save servers to disk; never persist 'command'
def save_servers():
    """Save MCP servers to disk. Only persist safe keys; never write command."""
    global mcp_servers
    try:
        servers = []
        for s in mcp_servers.values():
            safe = {k: s[k] for k in MCP_SERVER_SAFE_KEYS if k in s}
            servers.append(safe)
        with open(SERVERS_FILE, "w", encoding="utf-8") as f:
            json.dump(servers, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(servers)} MCP servers to disk")
    except Exception as e:
        print(f"Error saving servers to disk: {e}")

# Load AutoGen team from config
def load_autogen_team():
    """Load AutoGen team from team-config.json."""
    global autogen_team
    
    if not AUTOGEN_AVAILABLE:
        print("âš ï¸  AutoGen not available, skipping team load")
        return None
    
    try:
        if not TEAM_CONFIG_FILE.exists():
            print(f"âš ï¸  Team config file not found: {TEAM_CONFIG_FILE}")
            return None
            
        print(f"📂 Loading AutoGen team from {TEAM_CONFIG_FILE}...")
        
        with open(TEAM_CONFIG_FILE, 'r', encoding='utf-8') as f:
            team_config = json.load(f)
        
        # Load the team from the configuration using ComponentLoader
        loader = ComponentLoader()
        team = loader.load_component(team_config)

        # Inject PythonCodeExecutionTool (Docker) into first participant's workbench if available
        if AUTOGEN_CODE_EXEC_AVAILABLE and PythonCodeExecutionTool and DockerCommandLineCodeExecutor:
            coding_dir = _PROJECT_ROOT / "coding"
            try:
                coding_dir.mkdir(exist_ok=True)
            except OSError:
                pass
            work_dir = str(coding_dir)
            executor = DockerCommandLineCodeExecutor(
                work_dir=work_dir,
                image="python:3.12-slim",
                timeout=120,
            )
            code_tool = PythonCodeExecutionTool(executor)
            participants = getattr(team, "participants", None) or getattr(team, "_participants", [])
            if participants:
                agent = participants[0]
                wb = getattr(agent, "workbench", getattr(agent, "_workbench", None))
                if wb is not None:
                    wb_list = wb if isinstance(wb, list) else [wb]
                    for wb_item in wb_list:
                        tools = getattr(wb_item, "tools", getattr(wb_item, "_tools", None))
                        if tools is not None and isinstance(tools, list):
                            tools.insert(0, code_tool)
                            print("✅ Injected PythonCodeExecutionTool (Docker) into assistant_agent workbench")
                            break

        print(f"✅ AutoGen team loaded successfully: {team_config.get('label', 'Unknown')}")
        return team
        
    except Exception as e:
        import traceback
        print(f"âŒ Error loading AutoGen team: {e}")
        print(traceback.format_exc())
        return None


async def _start_code_executors(team: Any) -> None:
    """Start any code executors (Docker/local) attached to team participants or their tools."""
    if not AUTOGEN_AVAILABLE or team is None:
        return
    participants = getattr(team, "participants", None) or getattr(team, "_participants", [])
    for agent in participants or []:
        # CodeExecutorAgent has _code_executor
        executor = getattr(agent, "_code_executor", None)
        if executor is not None and hasattr(executor, "start"):
            try:
                await executor.start()
            except Exception as e:
                print(f"âš ï¸ Code executor start warning: {e}")
        # AssistantAgent workbench tools may have .executor (e.g. PythonCodeExecutionTool)
        wb = getattr(agent, "workbench", getattr(agent, "_workbench", None))
        if wb is not None:
            wb_list = wb if isinstance(wb, list) else [wb]
            for wb_item in wb_list:
                tools = getattr(wb_item, "tools", getattr(wb_item, "_tools", None))
                if tools is not None:
                    for t in tools:
                        ex = getattr(t, "executor", None) or getattr(t, "_executor", None)
                        if ex is not None and hasattr(ex, "start"):
                            try:
                                await ex.start()
                            except Exception as e:
                                print(f"âš ï¸ Tool executor start warning: {e}")


async def _stop_code_executors(team: Any) -> None:
    """Stop any code executors attached to team participants or their tools."""
    if not AUTOGEN_AVAILABLE or team is None:
        return
    participants = getattr(team, "participants", None) or getattr(team, "_participants", [])
    for agent in participants or []:
        executor = getattr(agent, "_code_executor", None)
        if executor is not None and hasattr(executor, "stop"):
            try:
                await executor.stop()
            except Exception as e:
                print(f"âš ï¸ Code executor stop warning: {e}")
        wb = getattr(agent, "workbench", getattr(agent, "_workbench", None))
        if wb is not None:
            wb_list = wb if isinstance(wb, list) else [wb]
            for wb_item in wb_list:
                tools = getattr(wb_item, "tools", getattr(wb_item, "_tools", None))
                if tools is not None:
                    for t in tools:
                        ex = getattr(t, "executor", None) or getattr(t, "_executor", None)
                        if ex is not None and hasattr(ex, "stop"):
                            try:
                                await ex.stop()
                            except Exception as e:
                                print(f"âš ï¸ Tool executor stop warning: {e}")


# Load servers on startup (with error handling to prevent startup failures)
try:
    load_servers()
    print(f"✅ Loaded {len(mcp_servers)} MCP servers from disk")
except Exception as e:
    import traceback
    print(f"âš ï¸ Warning: Could not load servers on startup: {e}")
    print(traceback.format_exc())
    # Continue anyway - server should still work without pre-loaded servers

# Load AutoGen team on startup (with error handling to prevent startup failures)
try:
    autogen_team = load_autogen_team()
    if autogen_team is not None:
        print("✅ AutoGen team loaded successfully on startup")
except Exception as e:
    import traceback
    print(f"âš ï¸ Warning: Could not load AutoGen team on startup: {e}")
    print(traceback.format_exc())
    # Continue anyway - server should still work without AutoGen team
    autogen_team = None

# Web proxy endpoint for fetching content (GET for backward compat, POST for iOS Safari / long URLs)
def _is_dns_or_network_error(exc: BaseException) -> bool:
    """True if the exception is DNS (getaddrinfo) or network unreachable."""
    if isinstance(exc, socket.gaierror):
        return True
    # Windows: OSError can have winerror 11002 (WSAHOST_NOT_FOUND)
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 11002:
        return True
    # Check wrapped cause (e.g. httpx wraps socket errors)
    cause = getattr(exc, "__cause__", None)
    if cause and _is_dns_or_network_error(cause):
        return True
    errstr = str(exc).lower()
    if "getaddrinfo failed" in errstr or "name or service not known" in errstr or "nodename nor servname" in errstr or "errno 11002" in errstr:
        return True
    return False


async def _do_proxy_fetch(
    url: str,
    crawl: bool = True,
    max_pages: int = 3,
    max_depth: int = 1,
) -> Dict[str, Any]:
    """Shared fetch logic: fetch URL(s), extract readable content, and optionally crawl."""
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="URL parameter is required")
    return await _fetch_and_extract_content(
        url=url,
        crawl=bool(crawl),
        max_pages=max_pages,
        max_depth=max_depth,
    )


def _normalize_url(raw_url: str) -> str:
    url = (raw_url or "").strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _is_same_domain(base_url: str, candidate_url: str) -> bool:
    try:
        base_host = (urlparse(base_url).hostname or "").lower()
        cand_host = (urlparse(candidate_url).hostname or "").lower()
        return bool(base_host) and base_host == cand_host
    except Exception:
        return False


def _extract_links_from_html(raw_html: str, base_url: str) -> List[str]:
    if not raw_html:
        return []
    links: List[str] = []
    seen: Set[str] = set()
    for match in re.finditer(r"""<a\s+[^>]*href=["']([^"']+)["']""", raw_html, re.IGNORECASE):
        href = (match.group(1) or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        # Normalize by dropping fragments only.
        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))
        if normalized in seen:
            continue
        seen.add(normalized)
        links.append(normalized)
    return links


def _extract_text_bs4(raw_html: str) -> Tuple[str, str]:
    soup = BeautifulSoup(raw_html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "canvas", "iframe", "form"]):
        tag.decompose()

    main = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find("body")
        or soup
    )

    for tag in main.find_all(["nav", "header", "footer", "aside"]):
        tag.decompose()

    title = (soup.title.get_text(" ", strip=True) if soup.title else "").strip()
    text = main.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return title, text


def _extract_text_fallback(raw_html: str) -> Tuple[str, str]:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    title = html.unescape(re.sub(r"<[^>]+>", " ", title_match.group(1))).strip() if title_match else ""

    cleaned = re.sub(r"<!--.*?-->", " ", raw_html, flags=re.DOTALL)
    cleaned = re.sub(r"<(script|style|noscript|svg|canvas|iframe|form)\b[^>]*>.*?</\1>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)

    # Prefer content-heavy semantic containers before full body fallback.
    for pattern in [
        r"<article\b[^>]*>(.*?)</article>",
        r"<main\b[^>]*>(.*?)</main>",
        r"<body\b[^>]*>(.*?)</body>",
    ]:
        m = re.search(pattern, cleaned, flags=re.IGNORECASE | re.DOTALL)
        if m:
            cleaned = m.group(1)
            break

    cleaned = re.sub(r"<(nav|header|footer|aside)\b[^>]*>.*?</\1>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    text = html.unescape(cleaned)
    text = re.sub(r"\s+", " ", text).strip()
    return title, text


def _extract_readable_content(raw_html: str) -> Tuple[str, str]:
    if BS4_AVAILABLE and BeautifulSoup is not None:
        try:
            return _extract_text_bs4(raw_html)
        except Exception:
            pass
    return _extract_text_fallback(raw_html)


async def _fetch_and_extract_content(
    url: str,
    crawl: bool = True,
    max_pages: int = 3,
    max_depth: int = 1,
) -> Dict[str, Any]:
    normalized_start = _normalize_url(url)
    max_pages = max(1, min(int(max_pages or 1), 10))
    max_depth = max(0, min(int(max_depth or 0), 2))

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

    queue = collections.deque([(normalized_start, 0)])
    visited: Set[str] = set()
    pages: List[Dict[str, Any]] = []
    last_raw_html = ""
    last_error: Optional[BaseException] = None

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            while queue and len(pages) < max_pages:
                current_url, depth = queue.popleft()
                if current_url in visited:
                    continue
                visited.add(current_url)

                try:
                    response = await client.get(current_url, headers=headers)
                    response.raise_for_status()
                    raw_html = response.text
                    final_url = str(response.url)
                    content_type = (response.headers.get("content-type") or "").lower()

                    if "text/html" not in content_type and "<html" not in raw_html[:3000].lower():
                        # Non-HTML content is still captured as plain text.
                        extracted_title = ""
                        extracted_text = raw_html.strip()
                    else:
                        extracted_title, extracted_text = _extract_readable_content(raw_html)

                    if extracted_text:
                        pages.append(
                            {
                                "url": final_url,
                                "title": extracted_title,
                                "content": extracted_text,
                            }
                        )
                        last_raw_html = raw_html

                    if crawl and depth < max_depth and len(pages) < max_pages:
                        for link in _extract_links_from_html(raw_html, final_url):
                            if link in visited:
                                continue
                            if not _is_same_domain(normalized_start, link):
                                continue
                            queue.append((link, depth + 1))
                except Exception as page_error:
                    last_error = page_error
                    continue
    except Exception as e:
        if _is_dns_or_network_error(e):
            raise HTTPException(
                status_code=502,
                detail=(
                    "The proxy server could not resolve the website's hostname (DNS lookup failed). "
                    "This usually means the machine running the proxy has no internet or restricted DNS. "
                    "Ensure the proxy runs on a machine with working internet and DNS (e.g. try pinging the host from that machine)."
                ),
            )
        raise HTTPException(status_code=500, detail=f"Failed to fetch content: {str(e)}")

    if not pages:
        if last_error and _is_dns_or_network_error(last_error):
            raise HTTPException(
                status_code=502,
                detail=(
                    "The proxy server could not resolve the website's hostname (DNS lookup failed). "
                    "This usually means the machine running the proxy has no internet or restricted DNS. "
                    "Ensure the proxy runs on a machine with working internet and DNS (e.g. try pinging the host from that machine)."
                ),
            )
        if last_error:
            raise HTTPException(status_code=500, detail=f"Failed to fetch content: {str(last_error)}")
        raise HTTPException(status_code=500, detail="Failed to fetch content: no pages returned")

    combined_parts: List[str] = []
    for i, page in enumerate(pages, start=1):
        page_title = (page.get("title") or "").strip()
        title_line = f"Title: {page_title}\n" if page_title else ""
        combined_parts.append(f"[Page {i}] {page.get('url')}\n{title_line}{page.get('content', '')}")
    combined_content = "\n\n".join(combined_parts).strip()

    return {
        "url": pages[0].get("url", normalized_start),
        "content": combined_content,
        "title": pages[0].get("title", ""),
        "pages": pages,
        "crawled": bool(crawl),
        "page_count": len(pages),
        "raw_html": last_raw_html,
    }


@app.get("/v1/proxy/fetch")
async def proxy_fetch_get(
    url: str,
    request: Request,
    crawl: bool = True,
    max_pages: int = 3,
    max_depth: int = 1,
):
    """Fetch web content via GET (query param). Use POST for long URLs (e.g. iOS Safari)."""
    try:
        result = await _do_proxy_fetch(url, crawl=crawl, max_pages=max_pages, max_depth=max_depth)
        cors = build_cors_headers(request)
        return JSONResponse(content=result, headers=cors)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Proxy fetch error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch content: {str(e)}")


@app.post("/v1/proxy/fetch")
async def proxy_fetch_post(body: ProxyFetchRequest, request: Request):
    """Fetch web content via POST body. Use url (single) or urls (list); if urls, try each until one succeeds."""
    # Build list: prefer urls if non-empty, else single url
    to_try: List[str] = []
    if body.urls:
        to_try = [u.strip() for u in body.urls if u and isinstance(u, str) and u.strip()]
    if not to_try and body.url:
        to_try = [body.url.strip()]
    if not to_try:
        raise HTTPException(status_code=400, detail="Either 'url' or 'urls' is required")
    last_error: Optional[Exception] = None
    for one_url in to_try:
        try:
            result = await _do_proxy_fetch(
                one_url,
                crawl=body.crawl,
                max_pages=body.max_pages,
                max_depth=body.max_depth,
            )
            cors = build_cors_headers(request)
            return JSONResponse(content=result, headers=cors)
        except HTTPException:
            raise
        except Exception as e:
            last_error = e
            print(f"Proxy fetch failed for {one_url[:60]}...: {e}")
            continue
    if last_error:
        raise HTTPException(status_code=500, detail=f"Failed to fetch content: {str(last_error)}")
    raise HTTPException(status_code=400, detail="No URLs to try")

# Shared search logic for route and Telegram tool runner
async def _do_proxy_search(query: str) -> Dict[str, Any]:
    """Search the web using Brave Search API or DuckDuckGo fallback. Raises HTTPException on failure."""
    if not query:
        raise HTTPException(status_code=400, detail="Search query is required")
    brave_api_key = os.getenv('BRAVE_API_KEY')
    if not brave_api_key:
        print("âš ï¸  BRAVE_API_KEY not configured. Falling back to DuckDuckGo.")
    else:
        try:
            print(f"ðŸ” Using Brave Search API for query: {query[:50]}...")
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    'https://api.search.brave.com/res/v1/web/search',
                    headers={
                        'Accept': 'application/json',
                        'Accept-Encoding': 'gzip',
                        'X-Subscription-Token': brave_api_key
                    },
                    params={
                        'q': query,
                        'count': 10,
                        'search_lang': 'en',
                        'safesearch': 'moderate',
                        'freshness': 'past_month'
                    }
                )

            if response.status_code == 200:
                data = response.json()
                if data.get('web', {}).get('results'):
                    results = []
                    for result in data['web']['results']:
                        date_str = result.get('age') or result.get('published')
                        parsed_date = parse_date(date_str) if date_str else None
                        results.append({
                            'url': result['url'],
                            'title': clean_text(result.get('title', '')),
                            'snippet': clean_text(result.get('description', '')),
                            'date': parsed_date
                        })
                    results = [r for r in results if r['title'] and r['snippet']]
                    results.sort(key=lambda x: parse_date(x.get('date')) or 0, reverse=True)
                    print(f"✅ Brave Search returned {len(results)} results")
                    return {"results": results[:5], "source": "brave"}
                else:
                    print(f"âš ï¸  Brave Search returned no results in response")
            elif response.status_code == 401:
                print(f"âŒ Brave Search API authentication failed (401). Check your BRAVE_API_KEY.")
                raise HTTPException(
                    status_code=500,
                    detail="Brave Search API authentication failed. Please check your BRAVE_API_KEY configuration."
                )
            elif response.status_code == 429:
                print(f"âš ï¸  Brave Search API rate limit exceeded (429). Falling back to DuckDuckGo.")
            else:
                print(f"âš ï¸  Brave Search API returned status {response.status_code}. Falling back to DuckDuckGo.")
                try:
                    error_data = response.json()
                    print(f"   Error details: {error_data}")
                except Exception:
                    print(f"   Error text: {response.text[:200]}")

        except httpx.RequestError as e:
            error_msg = str(e) if str(e) else f"Network error: {type(e).__name__}"
            print(f"âŒ Brave Search network error: {error_msg}")
            print("   Falling back to DuckDuckGo...")
        except httpx.HTTPStatusError as e:
            print(f"âŒ Brave Search HTTP error: {e.response.status_code if e.response else 'Unknown'}")
            print("   Falling back to DuckDuckGo...")
        except HTTPException:
            raise
        except Exception as e:
            error_msg = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
            print(f"âŒ Brave Search failed: {error_msg}")
            print("   Falling back to DuckDuckGo...")
            import traceback
            print(traceback.format_exc())

    print("🦆 Falling back to DuckDuckGo search...")
    try:
        search_url = f"https://html.duckduckgo.com/html/?q={query}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                search_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Referer': 'https://duckduckgo.com/'
                },
                follow_redirects=True
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"DuckDuckGo search returned HTTP {response.status_code}. The search service may be temporarily unavailable."
                )
        results = []
        html = response.text
        patterns = [
            r'<div class="links_main links_deep result__body">.*?<a class="result__a" href="([^"]+)".*?>(.*?)</a>.*?<a class="result__snippet".*?>(.*?)</a>',
            r'<div class="result__body">.*?<a class="result__url" href="([^"]+)".*?>(.*?)</a>.*?<div class="result__snippet">(.*?)</div>',
            r'<div class="result__body">.*?<a class="result__a" href="([^"]+)".*?>(.*?)</a>.*?<div class="result__snippet">(.*?)</div>',
            r'<a[^>]*class="[^"]*result[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<div[^>]*class="[^"]*snippet[^"]*"[^>]*>(.*?)</div>',
            r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*result__a[^"]*"[^>]*>(.*?)</a>.*?<span[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</span>'
        ]
        for pattern in patterns:
            matches = re.finditer(pattern, html, re.DOTALL)
            for match in matches:
                if len(results) >= 5:
                    break
                try:
                    url, title, snippet = match.groups()
                    url = url.replace('&amp;', '&')
                    title = clean_text(title)
                    snippet = clean_text(snippet)
                    if url and 'duckduckgo.com' not in url and title and snippet:
                        results.append({'url': url, 'title': title, 'snippet': snippet})
                except (ValueError, IndexError):
                    continue
            if len(results) >= 5:
                break
        if len(results) == 0:
            print(f"âš ï¸  DuckDuckGo search: No results found with regex patterns. HTML preview: {html[:1000]}")
            return {"results": [], "source": "duckduckgo", "message": "No results found. DuckDuckGo HTML structure may have changed."}
        print(f"✅ DuckDuckGo returned {len(results)} results")
        return {"results": results, "source": "duckduckgo"}
    except httpx.RequestError as e:
        error_msg = str(e) if str(e) else f"Network error: {type(e).__name__}"
        print(f"Search error (network): {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to perform search: Network error - {error_msg}")
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}" if e.response else str(e)
        print(f"Search error (HTTP): {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to perform search: {error_msg}")
    except Exception as e:
        error_msg = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
        print(f"Search error: {error_msg}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to perform search: {error_msg}")


@app.get("/v1/proxy/search")
async def proxy_search(query: str):
    """Search the web using Brave Search API or DuckDuckGo fallback."""
    return await _do_proxy_search(query)


# Shared news logic for route and Telegram tool runner
async def _do_proxy_news(query: str) -> Dict[str, Any]:
    """Fetch news articles for query. Raises HTTPException on failure."""
    if not query:
        raise HTTPException(status_code=400, detail="Search query is required")
    news_api_key = os.getenv('NEWS_API_KEY')
    if not news_api_key:
        raise HTTPException(
            status_code=503,
            detail="NEWS_API_KEY is not configured. Please set it in your .env file."
        )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                'https://newsapi.org/v2/everything',
                headers={'Accept': 'application/json'},
                params={
                    'q': query,
                    'apiKey': news_api_key,
                    'sortBy': 'publishedAt',
                    'language': 'en',
                    'pageSize': 100
                }
            )
        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])
            if not articles:
                return {"success": False, "message": f"No articles found for \"{query}\"", "articles": []}
            formatted_articles = []
            for article in articles:
                formatted_articles.append({
                    'title': clean_text(article.get('title', '')),
                    'url': article.get('url', ''),
                    'description': clean_text(article.get('description', '')),
                    'publishedAt': article.get('publishedAt', ''),
                    'source': article.get('source', {}).get('name', 'Unknown')
                })
            return {
                "success": True,
                "message": f"Found {len(formatted_articles)} articles",
                "articles": formatted_articles,
                "totalResults": data.get('totalResults', len(formatted_articles))
            }
        error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
        error_message = error_data.get('message', f"News API returned status {response.status_code}")
        print(f"News API error: {error_message}")
        raise HTTPException(status_code=response.status_code, detail=f"News API error: {error_message}")
    except httpx.HTTPStatusError as e:
        print(f"News API HTTP error: {e}")
        raise HTTPException(status_code=e.response.status_code, detail=f"News API request failed: {str(e)}")
    except Exception as e:
        print(f"News API error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch news: {str(e)}")


@app.get("/v1/proxy/news")
async def proxy_news_search(query: str):
    """Search news articles using News API."""
    return await _do_proxy_news(query)


def _sanitize_weather_location(location: str) -> str:
    if location is None:
        return ""
    if not isinstance(location, str):
        location = str(location)
    return re.sub(r"\s+", " ", location.strip())


def _normalize_weather_detail(detail: Optional[str]) -> str:
    """Normalize weather detail/request type to supported values."""
    value = (detail or "summary")
    if not isinstance(value, str):
        value = str(value)
    key = value.strip().lower()
    aliases = {
        "overview": "summary",
        "all": "summary",
        "rain": "forecast",
        "wind": "current",
        "alerts": "summary",
    }
    return aliases.get(key, key if key in {"summary", "current", "forecast"} else "summary")


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _open_meteo_weather_code_to_text(code: Any) -> str:
    code_int: Optional[int]
    try:
        code_int = int(float(code))
    except (TypeError, ValueError):
        code_int = None
    mapping = {
        0: "clear sky",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "fog",
        48: "depositing rime fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "dense drizzle",
        56: "light freezing drizzle",
        57: "dense freezing drizzle",
        61: "slight rain",
        63: "moderate rain",
        65: "heavy rain",
        66: "light freezing rain",
        67: "heavy freezing rain",
        71: "slight snow fall",
        73: "moderate snow fall",
        75: "heavy snow fall",
        77: "snow grains",
        80: "slight rain showers",
        81: "moderate rain showers",
        82: "violent rain showers",
        85: "slight snow showers",
        86: "heavy snow showers",
        95: "thunderstorm",
        96: "thunderstorm with slight hail",
        99: "thunderstorm with heavy hail",
    }
    if code_int is None:
        return "unknown"
    return mapping.get(code_int, f"weather code {code_int}")


def _extract_memory_location(memories: List[Dict[str, Any]]) -> Optional[str]:
    if not memories:
        return None
    patterns = [
        r"(?:i(?:\s|'| a)?m|i live|i am based|my location is|i'm in)\s+(?:in\s+)?([A-Za-z\s,'-]{2,80})",
        r"\b([A-Za-z\s'-]{2,60},\s*(?:nsw|vic|qld|sa|wa|tas|nt|act))\b",
        r"\b(\d{4})\b",
    ]
    for m in memories:
        txt = (m.get("text") or "").strip()
        if not txt:
            continue
        for pat in patterns:
            mo = re.search(pat, txt, re.IGNORECASE)
            if mo:
                return _sanitize_weather_location(mo.group(1).strip(" .,"))
    return None


async def _resolve_weather_location(location: Optional[str], user_id: Optional[str], memory_manager: Any) -> Tuple[str, str]:
    requested = _sanitize_weather_location(location or "")
    if requested:
        return requested, "request"
    if memory_manager is not None and user_id:
        try:
            memories = await memory_manager.search_memories(
                query=f"{user_id} location city suburb postcode", limit=8, similarity_threshold=0.3
            )
            inferred = _extract_memory_location(memories)
            if inferred:
                return inferred, "memory"
        except Exception as e:
            print(f"[WEATHER] Memory lookup failed: {e}")
    raise HTTPException(status_code=400, detail="Location is required. Please provide a city/suburb/postcode.")


async def _do_proxy_weather(location: Optional[str], detail: str = "summary", user_id: Optional[str] = None, memory_manager: Any = None) -> Dict[str, Any]:
    resolved_location, source = await _resolve_weather_location(location, user_id, memory_manager)
    detail = _normalize_weather_detail(detail)
    parsed_geocoding_base = urlparse(OPEN_METEO_GEOCODING_BASE_URL)
    if not parsed_geocoding_base.scheme.startswith("http"):
        raise HTTPException(status_code=500, detail="Invalid OPEN_METEO_GEOCODING_BASE_URL configuration")
    if not parsed_geocoding_base.hostname or not parsed_geocoding_base.hostname.endswith(OPEN_METEO_ALLOWED_HOST_SUFFIX):
        raise HTTPException(status_code=500, detail="OPEN_METEO_GEOCODING_BASE_URL host is not allowlisted")
    parsed_forecast_base = urlparse(OPEN_METEO_FORECAST_BASE_URL)
    if not parsed_forecast_base.scheme.startswith("http"):
        raise HTTPException(status_code=500, detail="Invalid OPEN_METEO_FORECAST_BASE_URL configuration")
    if not parsed_forecast_base.hostname or not parsed_forecast_base.hostname.endswith(OPEN_METEO_ALLOWED_HOST_SUFFIX):
        raise HTTPException(status_code=500, detail="OPEN_METEO_FORECAST_BASE_URL host is not allowlisted")

    weather_headers = {"Accept": "application/json", "User-Agent": OPEN_METEO_USER_AGENT}
    try:
        async with httpx.AsyncClient(timeout=OPEN_METEO_TIMEOUT_SECONDS, trust_env=OPEN_METEO_TRUST_ENV, follow_redirects=True) as client:
            loc_resp = await client.get(
                OPEN_METEO_GEOCODING_BASE_URL,
                params={"name": resolved_location, "count": 10, "language": "en", "format": "json"},
                headers=weather_headers,
            )
            loc_resp.raise_for_status()
            try:
                loc_json = loc_resp.json()
            except ValueError as e:
                raise HTTPException(status_code=502, detail=f"Invalid Open-Meteo geocoding payload: {str(e)}")
            loc_items = loc_json.get("results") if isinstance(loc_json, dict) else []
            if not isinstance(loc_items, list) or not loc_items:
                raise HTTPException(status_code=404, detail=f"No Open-Meteo location found for '{resolved_location}'.")
            requested_lc = resolved_location.lower()
            loc = next(
                (
                    item for item in loc_items
                    if isinstance(item, dict) and str(item.get("name") or "").strip().lower() == requested_lc
                ),
                None,
            )
            if not loc:
                loc = next(
                    (
                        item for item in loc_items
                        if isinstance(item, dict) and str(item.get("name") or "").strip().lower().startswith(requested_lc)
                ),
                None,
            )
            if not loc:
                loc = next(
                    (
                        item for item in loc_items
                        if isinstance(item, dict) and requested_lc in " ".join(
                            str(item.get(part) or "").strip().lower()
                            for part in ("name", "admin1", "country", "country_code")
                        )
                    ),
                    None,
                )
            if not loc:
                loc = loc_items[0] if isinstance(loc_items[0], dict) else {}

            latitude = _safe_float(loc.get("latitude"))
            longitude = _safe_float(loc.get("longitude"))
            if latitude is None or longitude is None:
                raise HTTPException(status_code=502, detail="Open-Meteo geocoding response missing coordinates")

            forecast_resp = await client.get(
                OPEN_METEO_FORECAST_BASE_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "forecast_days": 7,
                    "timezone": "auto",
                },
                headers=weather_headers,
            )
            forecast_resp.raise_for_status()
            try:
                forecast_json = forecast_resp.json()
            except ValueError as e:
                raise HTTPException(status_code=502, detail=f"Invalid Open-Meteo weather payload: {str(e)}")
    except HTTPException:
        raise
    except httpx.ConnectError as e:
        hint = ""
        if not OPEN_METEO_TRUST_ENV:
            hint = " If you require an outbound proxy, set OPEN_METEO_TRUST_ENV=true and configure HTTP(S)_PROXY."
        raise HTTPException(status_code=502, detail=f"Could not connect to Open-Meteo service: {str(e)}.{hint}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timed out contacting Open-Meteo weather service")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Open-Meteo weather service returned status {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve weather data: {str(e)}")

    current_data = (forecast_json or {}).get("current") if isinstance(forecast_json, dict) else {}
    if not isinstance(current_data, dict):
        current_data = {}
    daily_data = (forecast_json or {}).get("daily") if isinstance(forecast_json, dict) else {}
    if not isinstance(daily_data, dict):
        daily_data = {}

    daily_dates = daily_data.get("time") if isinstance(daily_data.get("time"), list) else []
    daily_mins = daily_data.get("temperature_2m_min") if isinstance(daily_data.get("temperature_2m_min"), list) else []
    daily_maxs = daily_data.get("temperature_2m_max") if isinstance(daily_data.get("temperature_2m_max"), list) else []
    daily_rain = daily_data.get("precipitation_probability_max") if isinstance(daily_data.get("precipitation_probability_max"), list) else []
    daily_codes = daily_data.get("weather_code") if isinstance(daily_data.get("weather_code"), list) else []

    def _daily_value(values: Any, index: int) -> Any:
        if isinstance(values, list) and index < len(values):
            return values[index]
        return None

    current = {
        "temperature_c": _safe_float(current_data.get("temperature_2m")),
        "feels_like_c": _safe_float(current_data.get("apparent_temperature")),
        "humidity_pct": _safe_float(current_data.get("relative_humidity_2m")),
        "wind_kph": _safe_float(current_data.get("wind_speed_10m")),
        "condition": _open_meteo_weather_code_to_text(current_data.get("weather_code")),
        "observation_time": current_data.get("time") or "",
    }

    forecast = []
    for idx, day_date in enumerate(daily_dates[:7]):
        day_code = _daily_value(daily_codes, idx)
        forecast.append({
            "date": day_date,
            "min_c": _safe_float(_daily_value(daily_mins, idx)),
            "max_c": _safe_float(_daily_value(daily_maxs, idx)),
            "rain_chance_pct": _safe_float(_daily_value(daily_rain, idx)),
            "condition": _open_meteo_weather_code_to_text(day_code),
        })

    loc_name = loc.get("name") or resolved_location
    current_temp = current.get("temperature_c")
    current_temp_text = f"{current_temp}C" if current_temp is not None else "N/A"
    summary = (
        f"Weather for {loc_name}: {current_temp_text}, {current.get('condition', 'unknown')}"
        f". Forecast entries: {len(forecast)}."
    )

    payload = {
        "success": True,
        "summary": summary,
        "resolved_location": loc_name,
        "location_source": source,
        "current": current,
        "forecast": forecast,
        "detail": detail,
        "source": "open-meteo.com",
    }

    if detail == "current":
        payload["forecast"] = []
    elif detail == "forecast":
        payload["current"] = {}
    return payload


@app.get("/v1/proxy/weather")
async def proxy_weather(
    location: Optional[str] = None,
    detail: str = "summary",
    requestType: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Fetch parsed weather information from Open-Meteo. Auth required."""
    user_id = current_user.get("username") if isinstance(current_user, dict) else None
    final_detail = _normalize_weather_detail(requestType or detail)
    return await _do_proxy_weather(location=location, detail=final_detail, user_id=user_id, memory_manager=memory_manager if MEMORY_AVAILABLE else None)


# Shared AutoGen logic for route and Telegram tool runner
async def _do_autogen(input_text: str) -> Dict[str, Any]:
    """Run AutoGen team with input_text. Returns dict with output/response/messages. Raises HTTPException on failure."""
    global autogen_team
    if not input_text:
        raise HTTPException(status_code=400, detail="Input parameter is required")
    if not AUTOGEN_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="AutoGen not available. Please install: pip install autogen-agentchat autogen-ext"
        )
    if autogen_team is None:
        print("🔄 Loading AutoGen team for the first time...")
        autogen_team = load_autogen_team()
        if autogen_team is None:
            raise HTTPException(
                status_code=503,
                detail="AutoGen team not loaded. Check team-config.json exists and is valid."
            )
    try:
        config_mtime = TEAM_CONFIG_FILE.stat().st_mtime
        if not hasattr(autogen_team, '_config_mtime') or autogen_team._config_mtime != config_mtime:
            print("🔄 Team config file changed, reloading AutoGen team...")
            await _stop_code_executors(autogen_team)
            new_team = load_autogen_team()
            if new_team is not None:
                autogen_team = new_team
                autogen_team._config_mtime = config_mtime
                if hasattr(autogen_team, '_executors_started'):
                    delattr(autogen_team, '_executors_started')
    except Exception as e:
        print(f"âš ï¸  Error checking team config modification time: {e}")
    if not getattr(autogen_team, '_executors_started', False):
        await _start_code_executors(autogen_team)
        try:
            autogen_team._executors_started = True
        except Exception:
            pass
    try:
        print(f"🚀 Running AutoGen team with input: {input_text[:100]}...")
        result = await autogen_team.run(task=input_text)
        messages = []
        if hasattr(result, 'messages'):
            messages = [
                {
                    "source": msg.source if hasattr(msg, 'source') else 'unknown',
                    "content": msg.content if hasattr(msg, 'content') else str(msg)
                }
                for msg in result.messages
            ]
        conversation_summary = "=== AutoGen Team Workflow ===\n\n"
        if messages:
            for i, msg in enumerate(messages, 1):
                conversation_summary += f"[{i}] {msg.get('source', 'unknown')}:\n{msg.get('content', '')}\n\n"
            conversation_summary += "=== End of Workflow ===\n\n"
            conversation_summary += "Please review the above conversation and provide a concise summary of the final result."
        else:
            conversation_summary += "No messages returned from AutoGen team."
        print(f"✅ AutoGen team completed with {len(messages)} messages")
        try:
            _write_autogen_conversation_to_scratch(input_text, messages, conversation_summary)
        except Exception as e:
            print(f"[AUTOGEN] Failed to write conversation to scratch: {e}", flush=True)
        return {
            "output": conversation_summary,
            "response": conversation_summary,
            "messages": messages,
            "message_count": len(messages)
        }
    except Exception as e:
        import traceback
        print(f"âŒ AutoGen team execution error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"AutoGen team execution failed: {str(e)}")


def _write_autogen_conversation_to_scratch(
    input_text: str,
    messages: List[Dict[str, str]],
    conversation_summary: str,
) -> str:
    """Write AutoGen conversation to scratch and return filename."""
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    timestamp_file = now.strftime("%Y-%m-%d_%H-%M-%S")
    timestamp_human = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    suffix = secrets.token_hex(4)
    filename = f"autogen_run_{timestamp_file}_{suffix}.txt"
    filepath = SCRATCH_DIR / filename
    lines = [
        "AutoGen team conversation log",
        f"Date-time: {timestamp_human}",
        "",
        "Input:",
        input_text or "(empty)",
        "",
        "--- Messages ---",
    ]
    if messages:
        for i, msg in enumerate(messages, 1):
            source = msg.get("source", "unknown")
            content = msg.get("content", "")
            lines.append(f"[{i}] {source}:")
            lines.append(content if content else "(empty)")
            lines.append("")
    else:
        lines.append("(No messages returned from AutoGen team)")
        lines.append("")
    lines.extend(
        [
            "--- Conversation Summary ---",
            "",
            conversation_summary or "(empty)",
        ]
    )
    filepath.write_text("\n".join(lines), encoding="utf-8")
    print(f"[AUTOGEN] Wrote conversation to {filepath}", flush=True)
    return filename


def _write_codex_summary_to_scratch(
    prompt: str,
    command: List[str],
    exit_code: Optional[int],
    stdout: str,
    stderr: str,
    duration_ms: int,
    timed_out: bool,
    events_file: Optional[str] = None,
    last_message_file: Optional[str] = None,
) -> str:
    """Write Codex execution summary to scratch and return filename."""
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    timestamp_file = now.strftime("%Y-%m-%d_%H-%M-%S")
    timestamp_human = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    suffix = secrets.token_hex(4)
    filename = f"codex_run_{timestamp_file}_{suffix}.txt"
    filepath = SCRATCH_DIR / filename
    lines = [
        "Codex CLI execution summary",
        f"Date-time: {timestamp_human}",
        f"Duration (ms): {duration_ms}",
        f"Timed out: {timed_out}",
        f"Exit code: {exit_code if exit_code is not None else 'N/A'}",
        f"Events file: {events_file or 'N/A'}",
        f"Last message file: {last_message_file or 'N/A'}",
        "",
        "Command:",
        " ".join(command),
        "",
        "Prompt:",
        prompt or "(empty)",
        "",
        "--- STDOUT ---",
        stdout or "(empty)",
        "",
        "--- STDERR ---",
        stderr or "(empty)",
    ]
    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filename


def _write_codex_error_to_scratch(
    prompt: str,
    command: List[str],
    error_message: str,
) -> str:
    """Write Codex execution error to scratch and return filename."""
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    timestamp_file = now.strftime("%Y-%m-%d_%H-%M-%S")
    timestamp_human = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    suffix = secrets.token_hex(4)
    filename = f"codex_run_error_{timestamp_file}_{suffix}.txt"
    filepath = SCRATCH_DIR / filename
    lines = [
        "Codex CLI execution error",
        f"Date-time: {timestamp_human}",
        "",
        "Command:",
        " ".join(command) if command else "(none)",
        "",
        "Prompt:",
        prompt or "(empty)",
        "",
        "Error:",
        error_message or "(empty)",
    ]
    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filename


async def _run_codex_cli(prompt: str) -> Dict[str, Any]:
    if not CODEX_ENABLED:
        raise HTTPException(status_code=503, detail="Codex CLI tool is disabled.")
    prompt = (prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required.")
    timeout = CODEX_TIMEOUT_SECONDS
    if timeout <= 0:
        raise HTTPException(status_code=500, detail="CODEX_TIMEOUT_SECONDS must be a positive integer.")
    timeout = min(max(timeout, 60), 7200)

    sandbox_mode = CODEX_SANDBOX_MODE if CODEX_SANDBOX_MODE in ("read-only", "workspace-write") else "workspace-write"
    approval_policy = CODEX_APPROVAL_POLICY if CODEX_APPROVAL_POLICY in ("untrusted", "on-request", "on-failure", "never") else "never"

    cmd: List[str] = [CODEX_CLI_PATH]
    if CODEX_ENABLE_SEARCH:
        # --search is a top-level codex flag and must appear before the subcommand.
        cmd.append("--search")
    cmd.extend([
        "exec",
        "--sandbox",
        sandbox_mode,
        "-C",
        str(_PROJECT_ROOT),
    ])
    if approval_policy == "never":
        # codex exec no longer accepts -a; --full-auto is the supported non-interactive mode
        cmd.append("--full-auto")
    events_file = None
    last_message_file = None
    if CODEX_JSON_EVENTS:
        cmd.append("--json")
    if CODEX_OUTPUT_LAST_MESSAGE:
        SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now().astimezone()
        timestamp_file = now.strftime("%Y-%m-%d_%H-%M-%S")
        suffix = secrets.token_hex(4)
        last_message_file = f"codex_last_message_{timestamp_file}_{suffix}.txt"
        cmd.extend(["-o", str(SCRATCH_DIR / last_message_file)])
    cmd.append(prompt)

    start = time.time()
    stdout_text = ""
    stderr_text = ""
    exit_code: Optional[int] = None
    timed_out = False
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(_PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out_bytes, err_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            timed_out = True
            proc.kill()
            out_bytes, err_bytes = await proc.communicate()
        stdout_text = (out_bytes or b"").decode("utf-8", errors="replace")
        stderr_text = (err_bytes or b"").decode("utf-8", errors="replace")
        exit_code = proc.returncode
    except FileNotFoundError:
        error_file = _write_codex_error_to_scratch(prompt, cmd, "Codex CLI not found. Ensure it is installed and on PATH.")
        raise HTTPException(status_code=500, detail=f"Codex CLI not found. See {error_file} in scratch for details.")
    except Exception as e:
        error_file = _write_codex_error_to_scratch(prompt, cmd, f"Failed to execute Codex CLI: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to execute Codex CLI. See {error_file} in scratch for details.")
    finally:
        duration_ms = int((time.time() - start) * 1000)

    if CODEX_JSON_EVENTS:
        SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now().astimezone()
        timestamp_file = now.strftime("%Y-%m-%d_%H-%M-%S")
        suffix = secrets.token_hex(4)
        events_file = f"codex_events_{timestamp_file}_{suffix}.jsonl"
        (SCRATCH_DIR / events_file).write_text(stdout_text or "", encoding="utf-8")

    summary_file = _write_codex_summary_to_scratch(
        prompt=prompt,
        command=cmd,
        exit_code=exit_code,
        stdout=stdout_text,
        stderr=stderr_text,
        duration_ms=duration_ms,
        timed_out=timed_out,
        events_file=events_file,
        last_message_file=last_message_file,
    )
    return {
        "success": exit_code == 0 and not timed_out,
        "summaryFile": summary_file,
        "eventsFile": events_file,
        "lastMessageFile": last_message_file,
        "exitCode": exit_code,
        "timedOut": timed_out,
        "durationMs": duration_ms,
        "stdout": stdout_text,
        "stderr": stderr_text,
    }


# AutoGen team chat endpoint (integrated directly)
@app.post("/v1/proxy/autogen")
async def autogen_chat(request: Request):
    """Run AutoGen team conversation directly (no separate service needed)."""
    try:
        body = await request.json()
        input_text = body.get('input')
        if not input_text:
            raise HTTPException(status_code=400, detail="Input parameter is required")
        print(f"🤖 AutoGen team request: {input_text[:100]}...")
        return await _do_autogen(input_text)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"âŒ AutoGen endpoint error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to process AutoGen request: {str(e)}")


@app.post("/v1/proxy/codex")
async def proxy_codex_exec(
    request: CodexExecRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Run Codex CLI non-interactively in sandboxed mode. Auth required."""
    _ = current_user  # keep for auth enforcement
    return await _run_codex_cli(request.prompt)


@app.post("/v1/proxy/restart")
async def proxy_restart_server(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Schedule a proxy process restart. Auth required."""
    username = current_user.get("username", "unknown")
    return await _request_proxy_restart(trigger="web_api", requested_by=f"user:{username}")

# Allowed keys when persisting MCP server config (never persist 'command')
MCP_SERVER_SAFE_KEYS = {"id", "name", "preset_id", "apiKey", "model", "url", "wsUrl", "status", "enabled"}


# MCP server management endpoints (all require authentication)
@app.post("/v1/mcp/servers")
async def manage_servers(
    server_config: ServerConfig,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Manage MCP servers (create, update, clear). Never persist or execute client-supplied command."""
    # Log without secrets
    safe_dict = {k: v for k, v in server_config.model_dump().items() if k != "apiKey"}
    print(f"Received server config: {safe_dict}")

    global mcp_clients, mcp_servers

    try:
        # Handle clear action
        if server_config.action == "clear":
            for server_id, client in list(mcp_clients.items()):
                try:
                    await client.close()
                except Exception as e:
                    print(f"Error closing client {server_id}: {e}")
            mcp_servers.clear()
            mcp_clients.clear()
            print("Cleared all MCP servers and clients")
            save_servers()
            security_log("mcp_clear", current_user.get("username", ""), None, "all servers cleared")
            return {"message": "All MCP servers cleared successfully"}

        # Validate required fields
        if not server_config.id or not server_config.name:
            raise HTTPException(status_code=400, detail="Missing required fields: id, name")

        # Resolve preset_id: require or infer from name (browser-use)
        preset_id = server_config.preset_id
        if not preset_id and server_config.name and "mcp-browser-use" in server_config.name.lower():
            preset_id = "browser-use"
        if not preset_id:
            raise HTTPException(
                status_code=400,
                detail="Missing preset_id. Provide preset_id (e.g. 'browser-use') or use a name that implies it.",
            )
        if preset_id not in MCP_PRESETS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid preset_id '{preset_id}'. Allowed: {list(MCP_PRESETS.keys())}",
            )

        # Build stored server dict from allowed fields only; never store 'command'
        raw = server_config.model_dump()
        stored = {k: raw[k] for k in MCP_SERVER_SAFE_KEYS if k in raw and raw[k] is not None}
        stored["status"] = "disconnected"
        # Preserve connection status when updating
        existing_server = mcp_servers.get(server_config.id)
        if existing_server:
            stored["status"] = existing_server.get("status", "disconnected")
        stored["preset_id"] = preset_id

        if existing_server:
            mcp_servers[server_config.id] = {**existing_server, **stored}
            print(f"Updated MCP server: {server_config.name} ({server_config.id})")
            security_log("mcp_update", current_user.get("username", ""), server_config.id, f"preset_id={preset_id}")
        else:
            mcp_servers[server_config.id] = stored
            print(f"Added MCP server: {server_config.name} ({server_config.id})")
            security_log("mcp_add", current_user.get("username", ""), server_config.id, f"preset_id={preset_id}")

        save_servers()
        return {"message": "Server saved successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving MCP server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save MCP server: {str(e)}")

@app.get("/v1/mcp/servers")
async def get_servers(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get all MCP servers."""
    try:
        servers = list(mcp_servers.values())
        return {"servers": servers}
    except Exception as e:
        print(f"Error getting MCP servers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get MCP servers: {str(e)}")

def setup_browser_llm():
    """Set up the language model for browser automation."""
    model_provider = os.getenv("MCP_MODEL_PROVIDER", "google").lower()
    model_name = os.getenv("MCP_MODEL_NAME", "gemini-flash-latest")
    temperature = float(os.getenv("MCP_TEMPERATURE", "0.1"))

    if model_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY")
        )
    elif model_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    elif model_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("GOOGLE_API_KEY")
        )
    else:
        # Default to Google/Gemini
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            api_key=os.getenv("GOOGLE_API_KEY", "dummy-key")
        )

async def create_mcp_client(server_config: Dict[str, Any]):
    """Create MCP client connection (similar to Node.js version)."""
    manager = MCPClientManager(server_config)
    client = await manager.connect()
    return client

@app.post("/v1/mcp/servers/{server_id}/connect")
async def connect_server(
    server_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Connect to an MCP server. Uses only server-side presets; never executes user-supplied command."""
    try:
        print(f"Attempting to connect to server: {server_id}")

        server = mcp_servers.get(server_id)
        if not server:
            print(f"Server not found: {server_id}")
            raise HTTPException(status_code=404, detail="Server not found")

        print(f"Found server: {server.get('name')} ({server_id})")

        # Inprocess preset (e.g. browser-use): no subprocess, mark connected
        preset_id = server.get("preset_id") or (
            "browser-use" if _is_browser_use_server(server) else None
        )
        if preset_id == "browser-use" or _is_browser_use_server(server):
            server["preset_id"] = preset_id or "browser-use"
            server["status"] = "connected"
            mcp_servers[server_id] = server
            print(f"Successfully connected to MCP Browser Use server: {server.get('name')}")
            security_log("mcp_connect", current_user.get("username", ""), server_id, "preset_id=browser-use")
            return {"message": "Server connected successfully"}

        if server_id in mcp_clients:
            print(f"Server already connected: {server_id}")
            raise HTTPException(status_code=409, detail="Server is already connected")

        if not preset_id or preset_id not in MCP_PRESETS:
            raise HTTPException(
                status_code=400,
                detail="Server has no valid preset_id. Reconfigure the server with a preset (e.g. preset_id: 'browser-use').",
            )
        if MCP_PRESETS[preset_id].get("type") != "stdio":
            raise HTTPException(
                status_code=400,
                detail=f"Preset '{preset_id}' does not support stdio connect. Use a stdio preset or browser-use.",
            )

        if not MCP_AVAILABLE:
            raise HTTPException(status_code=503, detail="MCP SDK not available")

        print(f"Creating MCP client for server: {server.get('name')}")
        client = await create_mcp_client(server)
        mcp_clients[server_id] = client

        server["status"] = "connected"
        mcp_servers[server_id] = server

        print(f"Successfully connected to MCP server: {server.get('name')}")
        security_log("mcp_connect", current_user.get("username", ""), server_id, f"preset_id={preset_id}")
        return {"message": "Server connected successfully"}

    except HTTPException:
        raise
    except ValueError as e:
        print(f"Error connecting to MCP server: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error connecting to MCP server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to MCP server: {str(e)}")

@app.post("/v1/mcp/servers/{server_id}/disconnect")
async def disconnect_server(
    server_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Disconnect from an MCP server."""
    try:
        global mcp_clients, mcp_servers

        # Check if this is the MCP Browser Use server
        server = mcp_servers.get(server_id)
        if server and _is_browser_use_server(server):
            # Just mark as disconnected since we don't have a real connection
            server["status"] = "disconnected"
            mcp_servers[server_id] = server
            security_log("mcp_disconnect", current_user.get("username", ""), server_id, "browser-use")
            return {"message": "Server disconnected successfully"}

        if not MCP_AVAILABLE:
            raise HTTPException(status_code=503, detail="MCP SDK not available")

        client = mcp_clients.get(server_id)
        if not client:
            raise HTTPException(status_code=404, detail="Server is not connected")

        # Create a temporary manager to handle disconnect
        if server:
            manager = MCPClientManager(server)
            await manager.disconnect()

        del mcp_clients[server_id]

        server = mcp_servers.get(server_id)
        if server:
            server["status"] = "disconnected"
            mcp_servers[server_id] = server

        security_log("mcp_disconnect", current_user.get("username", ""), server_id, "stdio")
        return {"message": "Server disconnected successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error disconnecting MCP server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disconnect MCP server: {str(e)}")


async def _browser_use_http_list_tools() -> Dict[str, Any]:
    """List tools from the browser-use HTTP MCP server. Raises on connection failure."""
    from fastmcp import Client

    async with Client(MCP_BROWSER_USE_HTTP_URL) as client:
        tools = await client.list_tools()
    # Convert to the shape expected by the proxy API (name, description, inputSchema)
    tools_list = []
    for t in tools:
        entry = {
            "name": getattr(t, "name", "unknown"),
            "description": getattr(t, "description", None) or "",
            "inputSchema": getattr(t, "inputSchema", None) or {"type": "object", "properties": {}},
        }
        tools_list.append(entry)
    return {"tools": tools_list}


async def _browser_use_http_call_tool(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Call a tool on the browser-use HTTP MCP server. Returns result with content list; raises on connection failure."""
    from fastmcp import Client

    _log_tool_invocation("browser_use_http", tool_name, parameters)

    # Map proxy parameter names to server names (e.g. instruction -> task for run_browser_agent)
    args = dict(parameters)
    if tool_name == "run_browser_agent" and "instruction" in args and "task" not in args:
        args["task"] = args.pop("instruction")

    async with Client(MCP_BROWSER_USE_HTTP_URL) as client:
        result = await client.call_tool(tool_name, args)

    # Build content list from result.content (list of items with .text or str)
    content = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None) or str(item)
        content.append({"type": "text", "text": text})
    if getattr(result, "is_error", False) and not content:
        content.append({"type": "text", "text": "Tool returned an error."})
    return {"content": content}


def _is_browser_use_server(server: Optional[Dict[str, Any]]) -> bool:
    """Return True if server is the browser-use preset (by preset_id or name). Used for routing tools and philosopher detection."""
    if not server:
        return False
    name = (server.get("name") or "").lower()
    preset_id = (server.get("preset_id") or "").lower()
    return (
        preset_id == "browser-use"
        or "mcp-browser-use" in name
        or "browser-use" in name
        or ("browser" in name and "use" in name)
    )


def _log_tool_invocation(source: str, tool_name: str, parameters: Optional[Dict[str, Any]] = None) -> None:
    """Unified console logging for all tool invocation entry points."""
    try:
        payload = parameters if isinstance(parameters, dict) else {}
        args_text = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        args_text = str(parameters)
    print(f"[TOOL][{source}] name={tool_name} args={args_text}", flush=True)


@app.post("/v1/tools/log")
async def log_tool_invocation(request: Request):
    """Record a tool invocation from clients that execute tool routing locally (e.g. HTML UI)."""
    body: Dict[str, Any] = {}
    try:
        parsed = await request.json()
        if isinstance(parsed, dict):
            body = parsed
    except Exception:
        body = {}

    tool_name = str(body.get("name") or "").strip()
    if not tool_name:
        raise HTTPException(status_code=400, detail="name is required")

    source = str(body.get("source") or "client")
    arguments = body.get("arguments")
    _log_tool_invocation(source, tool_name, arguments if isinstance(arguments, dict) else {})
    return {"success": True}


# Browser automation tool endpoint (browser-use via HTTP; other servers via MCP client)
@app.post("/v1/mcp/servers/{server_id}/tools/call")
async def call_tool(server_id: str, request: ToolCallRequest):
    """Call a tool on an MCP server. Browser-use preset uses HTTP client; others use connected MCP client."""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP SDK not available")

    try:
        print(f"🔧 [TOOLS/CALL] Server: {server_id}")

        server = mcp_servers.get(server_id)
        tool_name = request.toolName
        parameters = request.parameters or {}
        _log_tool_invocation(f"mcp_call:{server_id}", tool_name, parameters)
        print(f"ðŸ” [TOOLS/CALL] Tool name: {tool_name}")
        print(f"ðŸ” [TOOLS/CALL] Parameters: {parameters}")

        # Browser-use preset: use HTTP client (no mcp_clients entry)
        if server and _is_browser_use_server(server):
            try:
                result = await _browser_use_http_call_tool(tool_name, parameters)
                return {"result": result}
            except Exception as e:
                print(f"âŒ [TOOLS/CALL] Browser-use HTTP error: {e}")
                raise HTTPException(
                    status_code=503,
                    detail=BROWSER_USE_HTTP_UNAVAILABLE_MSG + " " + str(e),
                )

        client = mcp_clients.get(server_id)
        if not client:
            print(f"âŒ [TOOLS/CALL] Server {server_id} not found or not connected")
            raise HTTPException(status_code=404, detail="Server is not connected")

        if not tool_name:
            print("âŒ [TOOLS/CALL] toolName is required but missing")
            raise HTTPException(status_code=400, detail="toolName is required")

        result = await client.request(
            method="tools/call",
            params={"name": tool_name, "arguments": parameters},
        )
        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 [TOOLS/CALL] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to call tool on MCP server: {str(e)}")

@app.post("/v1/mcp/servers/{server_id}/tools/list")
async def list_tools(server_id: str):
    """List tools available on an MCP server. Browser-use preset uses HTTP client."""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP SDK not available")

    try:
        print(f"ðŸ” [TOOLS/LIST] Server: {server_id}")

        server = mcp_servers.get(server_id)
        # Browser-use preset: list tools from HTTP server
        if server and _is_browser_use_server(server):
            try:
                result = await _browser_use_http_list_tools()
                return {"result": result}
            except Exception as e:
                print(f"âŒ [TOOLS/LIST] Browser-use HTTP error: {e}")
                raise HTTPException(
                    status_code=503,
                    detail=BROWSER_USE_HTTP_UNAVAILABLE_MSG + " " + str(e),
                )

        global mcp_clients
        client = mcp_clients.get(server_id)
        if not client:
            print(f"âŒ [TOOLS/LIST] Server {server_id} not found or not connected")
            raise HTTPException(status_code=404, detail="Server is not connected")

        result = await client.request(
            method="tools/list",
            params={},
        )

        print(f"📨 [TOOLS/LIST] Raw response from MCP server: {result}")

        # Validate response structure
        if not result:
            print("âŒ [TOOLS/LIST] No result returned from MCP server")
        elif 'tools' not in result:
            print(f"âŒ [TOOLS/LIST] Missing 'tools' field in response: {list(result.keys())}")
        elif not isinstance(result['tools'], list):
            print(f"âŒ [TOOLS/LIST] 'tools' field is not an array: {type(result['tools'])}")
        else:
            print(f"✅ [TOOLS/LIST] Found {len(result['tools'])} tools in response")
            for i, tool in enumerate(result['tools']):
                print(f"  Tool {i}: {tool.get('name', 'unnamed')}")
                if 'name' not in tool:
                    print(f"    âŒ Missing name for tool {i}")
                if 'description' not in tool:
                    print(f"    âš ï¸  Missing description for tool {i}")
                if 'inputSchema' not in tool:
                    print(f"    âš ï¸  Missing inputSchema for tool {i}")
                else:
                    schema = tool['inputSchema']
                    print(f"    ✅ inputSchema type: {schema.get('type')}")
                    if 'properties' in schema:
                        print(f"    ✅ Has {len(schema['properties'])} properties")
                    else:
                        print("    âš ï¸  No properties in inputSchema")

        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 [TOOLS/LIST] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tools on MCP server: {str(e)}")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "CATBot Proxy Server", "version": "2.0.0"}

@app.post("/v1/auth/signup", response_model=AuthTokenResponse)
async def auth_signup(request: AuthSignupRequest):
    """Create a new user account and return a signed JWT."""
    username = request.username.strip().lower()
    password = request.password

    if len(username) < 3:
        raise HTTPException(status_code=400, detail="username must be at least 3 characters")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="password must be at least 8 characters")
    if username in users_db:
        raise HTTPException(status_code=409, detail="username already exists")

    password_record = create_password_record(password)
    users_db[username] = {
        **password_record,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_users_db()

    token = create_jwt({"sub": username})
    return AuthTokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRATION_SECONDS,
        username=username,
    )


@app.post("/v1/auth/login", response_model=AuthTokenResponse)
async def auth_login(request: AuthLoginRequest):
    """Authenticate a user and return a signed JWT."""
    username = request.username.strip().lower()
    user = users_db.get(username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(request.password, user["salt"], user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_jwt({"sub": username})
    return AuthTokenResponse(
        access_token=token,
        expires_in=JWT_EXPIRATION_SECONDS,
        username=username,
    )


@app.get("/v1/auth/me", response_model=AuthUserResponse)
async def auth_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return the profile of the authenticated user based on JWT bearer token."""
    return AuthUserResponse(
        username=current_user["username"],
        created_at=current_user["created_at"],
    )


# ============================================================================
# TODO REST API (all endpoints require authentication)
# ============================================================================

def _todo_recurrence_to_dict(recurrence: Optional[TodoRecurrenceRequest]) -> Optional[Dict[str, Any]]:
    if not recurrence:
        return None
    return {
        "frequency": str(recurrence.frequency).strip().lower(),
        "interval": int(recurrence.interval),
    }


def _parse_todo_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_todo_list_response(
    meta: Dict[str, Any],
    due_only: bool = False,
    completion: Optional[Dict[str, Any]] = None,
) -> TodoListResponse:
    now = datetime.now(timezone.utc)
    raw_items = meta.get("task_items") if isinstance(meta, dict) else []
    if not isinstance(raw_items, list):
        raw_items = []

    task_items: List[TodoTaskItemResponse] = []
    tasks: List[str] = []
    for task_index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            continue
        description = str(item.get("description") or "").strip()
        if not description:
            continue
        next_run = _parse_todo_datetime(item.get("next_run_at"))
        is_due = bool(next_run and next_run <= now)
        if due_only and not is_due:
            continue
        tasks.append(description)
        task_items.append(
            TodoTaskItemResponse(
                taskId=task_index,
                taskDescription=description,
                scheduledFor=item.get("scheduled_for"),
                nextRunAt=item.get("next_run_at"),
                recurrence=item.get("recurrence"),
                lastCompletedAt=item.get("last_completed_at"),
                createdAt=item.get("created_at"),
                updatedAt=item.get("updated_at"),
                isDue=is_due,
            )
        )

    # Backward compatibility with old store schema that only had "tasks": ["..."].
    if not task_items and not due_only:
        raw_legacy_tasks = meta.get("tasks") if isinstance(meta, dict) else []
        if isinstance(raw_legacy_tasks, list):
            tasks = [str(t) for t in raw_legacy_tasks]
            task_items = [
                TodoTaskItemResponse(taskId=i + 1, taskDescription=desc)
                for i, desc in enumerate(tasks)
            ]

    completion_payload: Optional[TodoCompletionMetaResponse] = None
    if isinstance(completion, dict):
        try:
            completion_payload = TodoCompletionMetaResponse(
                taskId=int(completion.get("taskId")),
                rescheduled=bool(completion.get("rescheduled", False)),
                nextRunAt=completion.get("nextRunAt"),
            )
        except (TypeError, ValueError):
            completion_payload = None

    return TodoListResponse(
        tasks=tasks,
        taskItems=task_items,
        updated_at=meta.get("updated_at"),
        completion=completion_payload,
    )


@app.get("/v1/todo", response_model=TodoListResponse)
async def todo_list(
    due_only: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return the authenticated user's todo list. Requires JWT."""
    if not TODO_STORE_AVAILABLE or not _todo_store:
        raise HTTPException(status_code=503, detail="Todo store is not available.")
    user_key = current_user["username"]
    meta = _todo_store.load_tasks_with_meta(user_key)
    return _build_todo_list_response(meta, due_only=due_only)


@app.get("/v1/todo/due", response_model=TodoListResponse)
async def todo_due_list(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return due scheduled tasks (next_run_at <= now) for the authenticated user."""
    if not TODO_STORE_AVAILABLE or not _todo_store:
        raise HTTPException(status_code=503, detail="Todo store is not available.")
    user_key = current_user["username"]
    meta = _todo_store.load_tasks_with_meta(user_key)
    return _build_todo_list_response(meta, due_only=True)


@app.post("/v1/todo", response_model=TodoListResponse)
async def todo_add(
    request: TodoAddRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Add a task to the authenticated user's todo list. Requires JWT."""
    if not TODO_STORE_AVAILABLE or not _todo_store:
        raise HTTPException(status_code=503, detail="Todo store is not available.")
    user_key = current_user["username"]
    desc = (request.taskDescription or "").strip()
    if not desc:
        raise HTTPException(status_code=400, detail="taskDescription is required.")
    recurrence = _todo_recurrence_to_dict(request.recurrence)
    try:
        _todo_store.add_task(
            user_key,
            desc,
            scheduled_for=request.scheduledFor,
            recurrence=recurrence,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = _todo_store.load_tasks_with_meta(user_key)
    return _build_todo_list_response(meta)


@app.patch("/v1/todo/{task_id}", response_model=TodoListResponse)
async def todo_update(
    task_id: int,
    request: TodoUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Update a task by 1-based index. Requires JWT."""
    if not TODO_STORE_AVAILABLE or not _todo_store:
        raise HTTPException(status_code=503, detail="Todo store is not available.")
    user_key = current_user["username"]
    desc = request.taskDescription
    if desc is not None:
        desc = desc.strip()
        if not desc:
            raise HTTPException(status_code=400, detail="taskDescription is required.")
    if (
        desc is None
        and request.scheduledFor is None
        and request.recurrence is None
        and not request.clearSchedule
        and not request.clearRecurrence
    ):
        raise HTTPException(status_code=400, detail="No update fields provided.")
    try:
        _todo_store.update_task(
            user_key,
            task_id,
            desc,
            scheduled_for=request.scheduledFor,
            recurrence=_todo_recurrence_to_dict(request.recurrence),
            clear_schedule=bool(request.clearSchedule),
            clear_recurrence=bool(request.clearRecurrence),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = _todo_store.load_tasks_with_meta(user_key)
    return _build_todo_list_response(meta)


@app.delete("/v1/todo/{task_id}", response_model=TodoListResponse)
async def todo_delete(
    task_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a task by 1-based index. Requires JWT."""
    if not TODO_STORE_AVAILABLE or not _todo_store:
        raise HTTPException(status_code=503, detail="Todo store is not available.")
    user_key = current_user["username"]
    try:
        _todo_store.delete_task(user_key, task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = _todo_store.load_tasks_with_meta(user_key)
    return _build_todo_list_response(meta)


@app.delete("/v1/todo", response_model=TodoListResponse)
async def todo_clear(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Clear all tasks for the authenticated user. Requires JWT."""
    if not TODO_STORE_AVAILABLE or not _todo_store:
        raise HTTPException(status_code=503, detail="Todo store is not available.")
    user_key = current_user["username"]
    _todo_store.clear_tasks(user_key)
    return TodoListResponse(tasks=[], taskItems=[], updated_at=None)


# ============================================================================
# TASK EXECUTION (internal helpers + REST; all REST require authentication)
# ============================================================================

def _write_task_exec_response_to_scratch(
    user_key: str, task_id: Optional[int], status: str, message: str
) -> None:
    """
    Write the task execution agent response to a timestamped text file in scratch.
    Called whenever a run ends (completed, paused, awaiting confirmation, or cancelled).
    Includes a clear SUMMARY and "What you can do" so the file conclusively shows outcome and next steps.
    """
    try:
        SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now().astimezone()
        timestamp_file = now.strftime("%Y-%m-%d_%H-%M-%S")
        timestamp_human = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        safe_user = re.sub(r"[^\w\-]", "_", (user_key or "unknown")[:64])
        task_suffix = f"_task{task_id}" if task_id is not None else ""
        filename = f"task_exec_{timestamp_file}_{safe_user}{task_suffix}.txt"
        filepath = SCRATCH_DIR / filename
        # Human-readable summary so the file conclusively shows whether task is done, paused, or cancelled
        if status == STATUS_AWAITING_CONFIRMATION:
            summary = "Task run finished. Awaiting your confirmation to mark the task complete."
            what_to_do = "Confirm completion (e.g. 'mark task complete' or use todo complete), or ask for status."
        elif status == STATUS_PAUSED_AWAITING_FEEDBACK:
            summary = "Paused for your feedback or input."
            what_to_do = "Send your input to resume (e.g. via chat or execute/resume)."
        elif status == STATUS_CANCELLED:
            summary = "Execution was cancelled."
            what_to_do = "You can start a new execution for a task if needed."
        else:
            summary = f"Status: {status}"
            what_to_do = "Check status or resume/cancel as appropriate."
        lines = [
            "Task execution response",
            "SUMMARY: " + summary,
            "",
            f"Date-time: {timestamp_human}",
            f"Status: {status}",
            f"Task ID: {task_id}" if task_id is not None else "Task ID: (none)",
            "",
            "What you can do: " + what_to_do,
            "",
            "--- Agent response ---",
            "",
            message or "(No response text)",
        ]
        filepath.write_text("\n".join(lines), encoding="utf-8")
        print(f"[TASK_EXEC] Wrote response to {filepath}", flush=True)
    except Exception as e:
        print(f"[TASK_EXEC] Failed to write response to scratch: {e}", flush=True)


async def _run_task_loop_background(user_key: str, executor: Any) -> None:
    """
    Run executor.run_loop() in background; update or clear task_execution_state in finally
    so we never leave state stuck as 'executing' on exception or cancel.
    """
    status = STATUS_AWAITING_CONFIRMATION
    message = "Execution stopped unexpectedly."
    try:
        status, message = await executor.run_loop()
    except Exception as e:
        status = STATUS_AWAITING_CONFIRMATION
        message = str(e)
        print(f"[TASK_EXEC] run_loop error for user {user_key}: {e}", flush=True)
    finally:
        # Only update if this user's state is still 'executing' (we own it)
        state = task_execution_state.get(user_key)
        if state and state.get("status") == STATUS_EXECUTING:
            state["status"] = status
            state["message"] = message or ""
            # Always capture agent response to scratch with timestamp (paused, awaiting, cancelled, done)
            _write_task_exec_response_to_scratch(user_key, state.get("task_id"), status, message or "")
            await _maybe_notify_telegram_task_completion(user_key, state, status, message or "")
            # Clear state on cancel so user can start a new execution
            if status == STATUS_CANCELLED:
                task_execution_state.pop(user_key, None)


async def _task_execute_start(user_key: str, task_id: int, prompt_override: Optional[str]) -> tuple:
    """Start task execution for user_key. Runs loop in background; returns immediately with status 'executing'."""
    if not TASK_EXECUTION_AVAILABLE or not TodoTaskExecutor:
        raise HTTPException(status_code=503, detail="Task execution is not available.")
    if not TODO_STORE_AVAILABLE or not _todo_store:
        raise HTTPException(status_code=503, detail="Todo store is not available.")
    if user_key in task_execution_state:
        raise HTTPException(status_code=409, detail="An execution is already active. Complete or cancel it first.")
    tasks = _todo_store.load_tasks(user_key)
    if task_id < 1 or task_id > len(tasks):
        raise HTTPException(status_code=400, detail="Invalid task ID.")
    task_description = tasks[task_id - 1]
    task_is_scheduled = False
    try:
        meta = _todo_store.load_tasks_with_meta(user_key)
        task_items = meta.get("task_items") if isinstance(meta, dict) else None
        if isinstance(task_items, list) and task_id >= 1 and task_id <= len(task_items):
            task_item = task_items[task_id - 1]
            if isinstance(task_item, dict):
                item_desc = str(task_item.get("description") or "").strip()
                if item_desc:
                    task_description = item_desc
                task_is_scheduled = bool(
                    task_item.get("scheduled_for")
                    or task_item.get("next_run_at")
                    or task_item.get("recurrence")
                )
    except Exception:
        # Keep execution available even if metadata parsing fails.
        task_is_scheduled = False
    telegram_chat_ids = _resolve_telegram_chat_ids_for_todo_user(user_key)
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("MCP_LLM_OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured.")
    executor = TodoTaskExecutor(
        api_key=api_key,
        task_id=task_id,
        task_description=task_description,
        prompt_override=prompt_override,
        max_iterations=TASK_EXECUTION_MAX_ITERATIONS,
        tool_executor=execute_tool_for_philosopher,
        get_tools_func=get_all_available_tools,
    )
    # Set state to 'executing' before starting so cancel/status work and we never leave state stuck
    task_execution_state[user_key] = {
        "task_id": task_id,
        "status": STATUS_EXECUTING,
        "executor": executor,
        "message": None,
        "task_description": task_description,
        "is_scheduled": task_is_scheduled,
        "telegram_chat_ids": telegram_chat_ids,
    }
    asyncio.create_task(_run_task_loop_background(user_key, executor))
    return (STATUS_EXECUTING, "Task execution started. Ask me for status or to cancel.")


async def _task_execute_resume(user_key: str, user_message: str) -> tuple:
    """Resume paused execution. Returns (status, message)."""
    if not TASK_EXECUTION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Task execution is not available.")
    state = task_execution_state.get(user_key)
    if not state or state.get("status") != STATUS_PAUSED_AWAITING_FEEDBACK:
        raise HTTPException(status_code=400, detail="No paused execution to resume.")
    executor = state.get("executor")
    if not executor:
        task_execution_state.pop(user_key, None)
        raise HTTPException(status_code=400, detail="Execution state lost. Start a new execution.")
    executor.add_user_message(user_message or "")
    try:
        status, message = await executor.run_loop()
        state["status"] = status
        state["message"] = message or ""
        # Capture agent response to scratch (paused or awaiting confirmation after resume)
        _write_task_exec_response_to_scratch(user_key, state.get("task_id"), status, message or "")
        await _maybe_notify_telegram_task_completion(user_key, state, status, message or "")
        return (status, message or "Resumed.")
    except Exception as e:
        state["status"] = STATUS_AWAITING_CONFIRMATION
        state["message"] = str(e)
        _write_task_exec_response_to_scratch(user_key, state.get("task_id"), STATUS_AWAITING_CONFIRMATION, str(e))
        return (STATUS_AWAITING_CONFIRMATION, str(e))


@app.post("/v1/todo/execute", response_model=TodoExecuteResponse)
async def todo_execute(
    request: TodoExecuteRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Start task execution for the given todo task. Requires JWT. One active execution per user."""
    user_key = current_user["username"]
    status, message = await _task_execute_start(user_key, request.taskId, request.promptOverride)
    return TodoExecuteResponse(status=status, message=message, taskId=request.taskId)


@app.post("/v1/todo/execute/resume", response_model=TodoExecuteResponse)
async def todo_execute_resume(
    resume_request: TodoResumeRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Resume a paused task execution with user feedback. Requires JWT."""
    user_key = current_user["username"]
    state = task_execution_state.get(user_key)
    status, message = await _task_execute_resume(user_key, resume_request.userMessage or "")
    return TodoExecuteResponse(status=status, message=message, taskId=state.get("task_id") if state else None)


@app.post("/v1/todo/{task_id}/complete", response_model=TodoListResponse)
async def todo_task_complete(
    task_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Human verification: complete a task. Repeating tasks are rescheduled; one-time tasks are removed."""
    if not TODO_STORE_AVAILABLE or not _todo_store:
        raise HTTPException(status_code=503, detail="Todo store is not available.")
    user_key = current_user["username"]
    task_execution_state.pop(user_key, None)
    try:
        result = _todo_store.complete_task(user_key, task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = {
        "tasks": result.get("tasks", []),
        "task_items": result.get("task_items", []),
        "updated_at": result.get("updated_at"),
    }
    completion = {
        "taskId": task_id,
        "rescheduled": bool(result.get("rescheduled", False)),
        "nextRunAt": result.get("next_run_at"),
    }
    return _build_todo_list_response(meta, completion=completion)


def _task_execute_cancel(user_key: str) -> tuple:
    """Request cancel for current execution (soft cancel). Returns (ok, message)."""
    state = task_execution_state.get(user_key)
    if not state:
        return (False, "No active execution to cancel.")
    executor = state.get("executor")
    if executor and hasattr(executor, "request_cancel"):
        executor.request_cancel()
        return (True, "Cancellation requested. The task will stop after the current step.")
    task_execution_state.pop(user_key, None)
    return (False, "No active execution to cancel.")


def _task_execution_status(user_key: str) -> Optional[Dict[str, Any]]:
    """Return current execution state for user_key, or None if none."""
    state = task_execution_state.get(user_key)
    if not state:
        return None
    return {"status": state.get("status"), "task_id": state.get("task_id"), "message": state.get("message")}


@app.post("/v1/todo/execute/cancel", response_model=TodoExecuteResponse)
async def todo_execute_cancel(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Cancel current task execution; task remains in list. Requires JWT."""
    user_key = current_user["username"]
    ok, msg = _task_execute_cancel(user_key)
    task_id = task_execution_state.get(user_key, {}).get("task_id") if ok else None
    return TodoExecuteResponse(status=STATUS_CANCELLED, message=msg, taskId=task_id)


def _is_todo_list_query(message_text: str) -> bool:
    """
    Return True if the message is clearly asking for the current todo/task list.
    Used to skip memory injection so the model uses manageTodoList tool instead of answering from memory.
    """
    if not message_text or len(message_text) > 500:
        return False
    lower = message_text.lower().strip()
    # Phrases that indicate user wants current list (use tool), not memory-based answer
    phrases = (
        "what's on my todo",
        "whats on my todo",
        "what is on my todo",
        "show my todo",
        "list my todo",
        "my todo list",
        "show my tasks",
        "list my tasks",
        "what are my tasks",
        "what's on my list",
        "whats on my list",
        "my tasks",
        "my todos",
        "what is due",
        "what's due",
        "whats due",
        "show due tasks",
        "list due tasks",
        "show overdue tasks",
        "list overdue tasks",
    )
    return any(p in lower for p in phrases)


def _is_memory_context_question(message_text: str) -> bool:
    """
    Return True when a message is likely asking for opinions/knowledge where memory context helps.
    Action/tool requests should return False to avoid noisy memory injection.
    """
    if not message_text:
        return False

    lower = message_text.lower().strip()
    if len(lower) > 800:
        return False

    action_patterns = (
        r"(search|find|look\s+up|get|fetch|retrieve)\s+(for|information\s+about|details\s+about)",
        r"how\s+much\s+(does|do|is|are|cost)",
        r"what'?s\s+the\s+(weather|price|cost|temperature|time)",
        r"(show|display|list|give\s+me)\s+(information|data|details|results)",
        r"(navigate|go\s+to|visit|open|browse)",
        r"(read|write|save|load|upload|download)\s+(the\s+)?(file|document|data)",
        r"(create|make|build|generate|produce)\s+(a|an|the)",
        r"(run|execute|perform|do)\s+(a|an|the)",
    )
    if any(re.search(p, lower, re.IGNORECASE) for p in action_patterns):
        return False

    opinion_patterns = (
        r"what\s+(do\s+you\s+)?think\s+(about|of)",
        r"what'?s\s+(your\s+)?(opinion|view|perspective|take|thoughts?)\s+(on|about|of|regarding)",
        r"what\s+(do\s+you\s+)?know\s+(about|of)",
        r"how\s+do\s+you\s+(feel|see|view|perceive)\s+(about|on|regarding)",
        r"tell\s+me\s+(what\s+you\s+)?(think|know|believe|feel)\s+(about|of|on)",
        r"share\s+(your\s+)?(thoughts?|views?|opinions?|perspective)",
        r"what\s+(do\s+you\s+)?(believe|understand|consider)\s+(about|of|regarding)",
    )
    if any(re.search(p, lower, re.IGNORECASE) for p in opinion_patterns):
        return True

    return bool(re.search(r"^what\s+(do\s+you|'?s\s+your)", lower, re.IGNORECASE))


def _extract_memory_search_query(message_text: str) -> str:
    """Extract likely topic phrase for memory search; falls back to full message."""
    if not message_text:
        return ""
    match = re.search(
        r"(?:think|opinion|view|know|thoughts?|beliefs?|feel|see|perceive|understand|consider|"
        r"insights?|reflections?|contemplations?)\s+(?:about|of|on|regarding)\s+(.+?)(?:\?|$)",
        message_text,
        re.IGNORECASE,
    )
    topic = (match.group(1).strip() if match and match.group(1) else message_text.strip())
    return topic[:500]


def _filter_high_relevance_memories(memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Keep only high-confidence memory matches:
    - top hit must pass minimum similarity
    - keep matches in a score window close to top score
    - cap final count
    """
    if not memories:
        return []

    sorted_memories = sorted(memories, key=lambda m: float(m.get("similarity", 0.0)), reverse=True)
    top_score = float(sorted_memories[0].get("similarity", 0.0))
    if top_score < MEMORY_AUTO_SEARCH_MIN_SIMILARITY:
        return []

    floor = max(MEMORY_AUTO_SEARCH_MIN_SIMILARITY, top_score - MEMORY_AUTO_SEARCH_SCORE_WINDOW)
    filtered = [m for m in sorted_memories if float(m.get("similarity", 0.0)) >= floor]
    return filtered[:MEMORY_AUTO_SEARCH_LIMIT]


def _message_requests_proxy_restart(message_text: str) -> bool:
    """
    Return True for explicit restart command-style phrases.
    This keeps restart deterministic for chat without relying on LLM tool selection.
    """
    if not message_text:
        return False
    normalized = re.sub(r"\s+", " ", message_text.strip().lower())
    normalized = normalized.rstrip(" .!?,;:")
    explicit_commands = {
        "/restartproxy",
        "/restart_proxy",
        "restart proxy",
        "restart proxy server",
        "restart the proxy",
        "restart the proxy server",
    }
    return normalized in explicit_commands


async def _restart_proxy_after_delay(trigger: str, requested_by: str) -> None:
    """Restart this proxy process after a short delay so current HTTP response can complete."""
    global _proxy_restart_scheduled
    await asyncio.sleep(PROXY_RESTART_DELAY_SECONDS)
    print(
        f"[RESTART] Restarting proxy server now (trigger={trigger}, requested_by={requested_by})",
        flush=True,
    )
    # Restart using the canonical module entrypoint so startup behavior remains consistent.
    try:
        os.execv(sys.executable, [sys.executable, "-m", "src.servers.proxy_server"])
    except Exception as exc:
        _proxy_restart_scheduled = False
        print(f"[RESTART] Failed to restart proxy server: {exc}", flush=True)


async def _request_proxy_restart(trigger: str, requested_by: str) -> Dict[str, Any]:
    """Schedule a process restart once; subsequent requests before restart are acknowledged idempotently."""
    global _proxy_restart_scheduled
    if not PROXY_RESTART_ENABLED:
        return {
            "success": False,
            "scheduled": False,
            "message": "Proxy restart is disabled by server configuration.",
        }
    if _proxy_restart_scheduled:
        return {
            "success": True,
            "scheduled": True,
            "alreadyScheduled": True,
            "message": "Proxy restart is already scheduled and will start shortly.",
        }
    _proxy_restart_scheduled = True
    asyncio.create_task(_restart_proxy_after_delay(trigger=trigger, requested_by=requested_by))
    return {
        "success": True,
        "scheduled": True,
        "message": "Proxy restart scheduled. Reconnect in a few seconds to load updated tools.",
    }


@app.post("/v1/telegram/chat", response_model=TelegramChatResponse)
async def telegram_chat_endpoint(raw_request: Request, request: TelegramChatRequest):
    """Process a Telegram chat message via OpenAI-compatible API."""
    _validate_telegram_secret(raw_request)

    message_text = (request.message or "").strip()
    if not message_text:
        raise HTTPException(status_code=400, detail="message is required")

    conversation_id = request.conversation_id or request.user_id or "default"
    request_id = request.request_id or f"telegram-{conversation_id}-{int(time.time() * 1000)}"

    await _start_status_session(
        conversation_id=conversation_id,
        request_id=request_id,
        channel="telegram",
        initial_state="Working: contacting model",
        phase="llm_request",
    )

    # Explicit command path for reliable Telegram-triggered proxy restarts (no LLM/tool-call required).
    if _message_requests_proxy_restart(message_text):
        restart_result = await _request_proxy_restart(
            trigger="telegram_command",
            requested_by=f"telegram:{request.user_id or conversation_id}",
        )
        reply_text = restart_result.get("message", "Proxy restart requested.")
        await _finish_status_session(
            conversation_id=conversation_id,
            request_id=request_id,
            final_state="Done: proxy restart scheduled",
            phase="done",
        )
        history = telegram_conversations.setdefault(conversation_id, [])
        history.append({"role": "user", "content": message_text})
        history.append({"role": "assistant", "content": reply_text})
        trim_telegram_history(history)
        return TelegramChatResponse(reply=reply_text, conversation_id=conversation_id, usage=None)

    # Prefer OPENAI_API_KEY; fall back to MCP_LLM_OPENAI_API_KEY for single .env setups
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("MCP_LLM_OPENAI_API_KEY")
    if not api_key:
        await _finish_status_session(
            conversation_id=conversation_id,
            request_id=request_id,
            final_state="Failed: server missing API key",
            phase="error",
        )
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY or MCP_LLM_OPENAI_API_KEY is not configured on the server",
        )

    todo_user_key = _resolve_todo_user_for_telegram(conversation_id, request.user_id)
    history = telegram_conversations.setdefault(conversation_id, [])

    if request.history is not None:
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.history
            if msg.content
        ]
        telegram_conversations[conversation_id] = history
        trim_telegram_history(history)

    history.append({"role": "user", "content": message_text})
    trim_telegram_history(history)

    system_prompt = request.system_prompt
    if system_prompt is None:
        if TELEGRAM_TOOLS_ENABLED:
            system_prompt = _get_telegram_system_prompt_with_tools(conversation_id, todo_user_key=todo_user_key)
        else:
            system_prompt = _get_telegram_system_prompt_base()

    # Prepend assistant context (timezone + knowledge awareness)
    system_prompt = _get_assistant_context_block() + system_prompt

    # Retrieve relevant memories only for opinion/knowledge-style prompts.
    memory_context = ""
    if (
        MEMORY_AVAILABLE
        and memory_manager
        and not _is_todo_list_query(message_text)
        and _is_memory_context_question(message_text)
    ):
        try:
            search_query = _extract_memory_search_query(message_text)
            candidate_memories = await memory_manager.search_memories(
                query=search_query,
                limit=max(5, MEMORY_AUTO_SEARCH_LIMIT * 2),
                similarity_threshold=MEMORY_AUTO_SEARCH_CANDIDATE_THRESHOLD,
            )

            relevant_memories = _filter_high_relevance_memories(candidate_memories)
            if relevant_memories:
                print(
                    f"Memory context: kept {len(relevant_memories)}/{len(candidate_memories)} "
                    f"for query '{search_query[:50]}...'"
                )
                memory_context = "\n\nRelevant context from previous conversations:\n"
                for i, mem in enumerate(relevant_memories, 1):
                    memory_context += f"{i}. {mem.get('text', '')}\n"
                memory_context += "\nUse this context to provide more personalized and relevant responses."
            else:
                print(f"Memory context: no high-relevance matches for query '{search_query[:50]}...'")
        except Exception as e:
            print(f"Warning: Failed to retrieve memories: {e}")
            import traceback
            print(traceback.format_exc())

    # Add memory context to system prompt
    if memory_context:
        system_prompt = system_prompt + memory_context

    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history)

    model_name = request.model or TELEGRAM_DEFAULT_MODEL
    if not model_name:
        raise HTTPException(status_code=400, detail="No model configured for Telegram chat")

    payload: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
    }

    if request.temperature is not None:
        payload["temperature"] = request.temperature

    if request.max_output_tokens is not None:
        payload["max_tokens"] = request.max_output_tokens

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if OPENAI_ORG_ID:
        headers["OpenAI-Organization"] = OPENAI_ORG_ID

    if OPENAI_PROJECT_ID:
        headers["OpenAI-Project"] = OPENAI_PROJECT_ID

    url = build_openai_url(TELEGRAM_OPENAI_CHAT_PATH)
    url = _normalize_chat_endpoint(url)

    max_tokens = _get_max_tokens_from_payload(payload)
    summarized = False
    if isinstance(payload.get("messages"), list):
        estimated = _estimate_total_tokens(payload["messages"], max_tokens)
        if estimated > get_max_token_limit():
            payload["messages"] = await _summarize_messages_for_budget_proxy(
                payload["messages"],
                endpoint=url,
                headers=headers,
                model_name=model_name,
                max_tokens=max_tokens,
                large_model=LARGE_PAYLOAD_MODEL,
                large_endpoint=LARGE_PAYLOAD_ENDPOINT,
            )
            summarized = True

    try:
        response = await _call_chat_completion(url, headers, payload, timeout_seconds=TELEGRAM_CHAT_TIMEOUT)
    except httpx.RequestError as exc:
        print(f"Telegram chat request error: {exc}")
        await _finish_status_session(
            conversation_id=conversation_id,
            request_id=request_id,
            final_state="Failed: could not contact model service",
            phase="error",
        )
        raise HTTPException(status_code=502, detail="Failed to contact language model service") from exc

    if response.status_code != 200:
        print(f"Telegram chat API error {response.status_code}: {response.text}")
        detail = response.text
        try:
            error_json = response.json()
            detail = (
                error_json.get("error", {}).get("message")
                or error_json.get("message")
                or detail
            )
        except ValueError:
            pass
        if is_context_limit_error(response.status_code, detail):
            if not summarized and isinstance(payload.get("messages"), list):
                payload["messages"] = await _summarize_messages_for_budget_proxy(
                    payload["messages"],
                    endpoint=url,
                    headers=headers,
                    model_name=model_name,
                    max_tokens=max_tokens,
                    large_model=LARGE_PAYLOAD_MODEL,
                    large_endpoint=LARGE_PAYLOAD_ENDPOINT,
                )
                summarized = True
                response = await _call_chat_completion(url, headers, payload, timeout_seconds=TELEGRAM_CHAT_TIMEOUT)
            if response.status_code != 200 and LARGE_PAYLOAD_MODEL:
                payload["model"] = LARGE_PAYLOAD_MODEL
                large_url = _normalize_chat_endpoint(LARGE_PAYLOAD_ENDPOINT or url)
                response = await _call_chat_completion(large_url, headers, payload, timeout_seconds=TELEGRAM_CHAT_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
            else:
                await _finish_status_session(
                    conversation_id=conversation_id,
                    request_id=request_id,
                    final_state="Failed: model returned error",
                    phase="error",
                )
                raise HTTPException(status_code=response.status_code, detail=detail)
        else:
            await _finish_status_session(
                conversation_id=conversation_id,
                request_id=request_id,
                final_state="Failed: model returned error",
                phase="error",
            )
            raise HTTPException(status_code=response.status_code, detail=detail)

    data = response.json()
    reply = None
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        reply = message.get("content")

    if not reply:
        reply = "I couldn't generate a response right now. Please try again shortly."

    # Tool loop: when tools enabled, parse for tool calls and execute up to TELEGRAM_TOOLS_MAX_ITERATIONS
    # Track last tool result so we can show it to the user if the LLM never returns a final text reply
    last_tool_result_message: Optional[str] = None
    last_tool_success: Optional[bool] = None
    # Friendly message when tool failed or returned an error (avoid showing raw 404/500 to user)
    _telegram_tool_error_reply = "I wasn't able to get that information just now. Please try again or rephrase your question."
    if TELEGRAM_TOOLS_ENABLED and _telegram_tools is not None:
        working_messages: List[Dict[str, str]] = []
        if system_prompt:
            working_messages.append({"role": "system", "content": system_prompt})
        working_messages.extend(history)
        iterations = 0
        while iterations < TELEGRAM_TOOLS_MAX_ITERATIONS:
            parsed = _telegram_tools.parse_telegram_tool_response(reply)
            if not parsed:
                break
            tool_name = parsed.get("name")
            if tool_name:
                await _update_status_session(
                    conversation_id=conversation_id,
                    request_id=request_id,
                    state=f"Working: executing tool {tool_name}",
                    phase=f"tool:{tool_name}",
                )
            args_str = parsed.get("arguments", "{}")
            try:
                tool_args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except (TypeError, json.JSONDecodeError):
                tool_args = {}
            if not isinstance(tool_args, dict):
                tool_args = {}
            # Build context for tool execution
            tool_ctx = {
                "conversation_id": conversation_id,
                "user_id": request.user_id,
                "todo_user_key": todo_user_key,
                "task_execute_start": _task_execute_start,
                "task_execute_resume": _task_execute_resume,
                "task_execute_cancel": _task_execute_cancel,
                "task_execution_status": _task_execution_status,
                "task_execution_register_telegram_target": _task_execution_register_telegram_target,
                "todo_store": telegram_todo,
                "memory_cache_store": telegram_memory_cache,
                "do_search": _do_proxy_search,
                "do_fetch": _do_proxy_fetch,
                "do_news": _do_proxy_news,
                "do_weather": _do_proxy_weather,
                "do_autogen": _do_autogen,
                "do_codex": _run_codex_cli,
                "do_restart_proxy": lambda reason=None: _request_proxy_restart(
                    trigger=f"telegram_tool:{(reason or '').strip() or 'requested'}",
                    requested_by=f"telegram:{request.user_id or conversation_id}",
                ),
                "do_browser_agent": _do_browser_agent,
                "do_deep_research": _do_deep_research,
                "read_file_internal": _read_file_internal,
                "write_file_internal": _write_file_internal,
                "list_files_internal": _list_files_internal,
                "upload_drive_internal": _upload_drive_internal,
                "memory_manager": memory_manager if MEMORY_AVAILABLE else None,
            }
            try:
                tool_result = await _telegram_tools.execute_telegram_tool(tool_name, tool_args, tool_ctx)
            except Exception as e:
                tool_result = {"success": False, "message": str(e)}
            result_message = tool_result.get("message", str(tool_result))
            last_tool_result_message = result_message
            last_tool_success = tool_result.get("success", True)
            working_messages.append({"role": "assistant", "content": reply})
            working_messages.append({"role": "user", "content": f"Tool result: {result_message}"})
            payload_tool = {"model": model_name, "messages": working_messages}
            if request.temperature is not None:
                payload_tool["temperature"] = request.temperature
            if request.max_output_tokens is not None:
                payload_tool["max_tokens"] = request.max_output_tokens
            max_tokens_tool = _get_max_tokens_from_payload(payload_tool)
            summarized_tool = False
            if isinstance(payload_tool.get("messages"), list):
                estimated_tool = _estimate_total_tokens(payload_tool["messages"], max_tokens_tool)
                if estimated_tool > get_max_token_limit():
                    payload_tool["messages"] = await _summarize_messages_for_budget_proxy(
                        payload_tool["messages"],
                        endpoint=url,
                        headers=headers,
                        model_name=payload_tool.get("model", ""),
                        max_tokens=max_tokens_tool,
                        large_model=LARGE_PAYLOAD_MODEL,
                        large_endpoint=LARGE_PAYLOAD_ENDPOINT,
                    )
                    summarized_tool = True
            await _update_status_session(
                conversation_id=conversation_id,
                request_id=request_id,
                state="Working: requesting final response",
                phase="llm_followup",
            )
            try:
                response_tool = await _call_chat_completion(url, headers, payload_tool, timeout_seconds=TELEGRAM_CHAT_TIMEOUT)
            except httpx.RequestError as exc:
                print(f"Telegram tool-loop request error: {exc}")
                break
            if response_tool.status_code != 200:
                print(f"Telegram tool follow-up returned status {response_tool.status_code}, using tool result as reply")
                if is_context_limit_error(response_tool.status_code, response_tool.text or ""):
                    if not summarized_tool and isinstance(payload_tool.get("messages"), list):
                        payload_tool["messages"] = await _summarize_messages_for_budget_proxy(
                            payload_tool["messages"],
                            endpoint=url,
                            headers=headers,
                            model_name=payload_tool.get("model", ""),
                            max_tokens=max_tokens_tool,
                            large_model=LARGE_PAYLOAD_MODEL,
                            large_endpoint=LARGE_PAYLOAD_ENDPOINT,
                        )
                        summarized_tool = True
                        response_tool = await _call_chat_completion(url, headers, payload_tool, timeout_seconds=TELEGRAM_CHAT_TIMEOUT)
                    if response_tool.status_code != 200 and LARGE_PAYLOAD_MODEL:
                        payload_tool["model"] = LARGE_PAYLOAD_MODEL
                        large_url = _normalize_chat_endpoint(LARGE_PAYLOAD_ENDPOINT or url)
                        response_tool = await _call_chat_completion(large_url, headers, payload_tool, timeout_seconds=TELEGRAM_CHAT_TIMEOUT)
                if response_tool.status_code != 200:
                    reply = _telegram_tool_error_reply if (not last_tool_success or _telegram_tools.tool_result_looks_like_error(result_message)) else f"Here's what I found:\n\n{result_message}"
                    break
            data_tool = response_tool.json()
            choices_tool = data_tool.get("choices") or []
            if not choices_tool:
                print("Telegram tool follow-up returned no choices, using tool result as reply")
                reply = _telegram_tool_error_reply if (not last_tool_success or _telegram_tools.tool_result_looks_like_error(result_message)) else f"Here's what I found:\n\n{result_message}"
                break
            new_content = (choices_tool[0].get("message") or {}).get("content")
            # If follow-up has no content (e.g. GLM 5 returns empty), use tool result so user never sees raw XML
            if new_content is None or (isinstance(new_content, str) and not new_content.strip()):
                print("Telegram tool follow-up returned empty content, using tool result as reply")
                reply = _telegram_tool_error_reply if (not last_tool_success or _telegram_tools.tool_result_looks_like_error(result_message)) else f"Here's what I found:\n\n{result_message}"
            else:
                reply = new_content
            iterations += 1

    # Never send raw tool-call XML to the user: if reply still looks like a tool call, show last tool result instead
    if _telegram_tools is not None and _telegram_tools.reply_looks_like_tool_call(reply):
        if last_tool_result_message is not None:
            print("Telegram: reply was raw tool call, using last tool result for user")
            if not last_tool_success or _telegram_tools.tool_result_looks_like_error(last_tool_result_message):
                reply = _telegram_tool_error_reply
            else:
                reply = f"Here's what I found:\n\n{last_tool_result_message}"
        else:
            reply = "I used a tool but couldn't format the result. Please try again."

    history.append({"role": "assistant", "content": reply})
    trim_telegram_history(history)

    # Extract and store memories if memory system is available and auto-extract is enabled
    if MEMORY_AVAILABLE and memory_manager:
        auto_extract = os.getenv("MEMORY_AUTO_EXTRACT", "true").lower() == "true"
        if auto_extract:
            try:
                # Extract memories from the conversation (last few messages)
                # Include both user message and assistant response
                recent_messages = history[-4:] if len(history) >= 4 else history
                await memory_manager.extract_memories_from_conversation(
                    messages=recent_messages,
                    max_memories=3,
                )
            except Exception as e:
                print(f"Warning: Failed to extract memories: {e}")

    usage = data.get("usage") if isinstance(data, dict) else None

    await _finish_status_session(
        conversation_id=conversation_id,
        request_id=request_id,
        final_state="Done: response delivered",
        phase="done",
    )

    return TelegramChatResponse(
        reply=reply,
        conversation_id=conversation_id,
        usage=usage,
    )


@app.delete("/v1/telegram/chat/{conversation_id}")
async def telegram_clear_conversation(request: Request, conversation_id: str):
    """Clear cached Telegram conversation history for a user."""
    _validate_telegram_secret(request)

    removed = telegram_conversations.pop(conversation_id, None) is not None
    return {"conversation_id": conversation_id, "cleared": removed}

# ============================================================================
# STATUS EVENTS ENDPOINTS
# ============================================================================

@app.post("/v1/status/start")
async def status_start(request: StatusStartRequest):
    """Start a status session for progress updates."""
    state = (request.state or "Working: processing your request...").strip()
    await _start_status_session(
        conversation_id=request.conversation_id,
        request_id=request.request_id,
        channel=request.channel or "web",
        initial_state=state,
        phase="start",
    )
    return {"ok": True}


@app.post("/v1/status/update")
async def status_update(request: StatusUpdateRequest):
    """Update the current status state for a session."""
    event = await _update_status_session(
        conversation_id=request.conversation_id,
        request_id=request.request_id,
        state=request.state,
        phase=request.phase,
    )
    return {"ok": True, "event": event}


@app.post("/v1/status/finish")
async def status_finish(request: StatusFinishRequest):
    """Finish a status session and stop heartbeat updates."""
    event = await _finish_status_session(
        conversation_id=request.conversation_id,
        request_id=request.request_id,
        final_state=request.final_state,
        phase=request.phase or "done",
    )
    return {"ok": True, "event": event}


@app.get("/v1/status/latest")
async def status_latest(conversation_id: str, request_id: Optional[str] = None):
    """Get the latest status event for a conversation (optionally by request_id)."""
    event = _get_latest_status_event(conversation_id, request_id=request_id)
    if not event:
        return {"found": False}
    key = (event.get("conversation_id"), event.get("request_id"))
    active = key in status_sessions
    return {"found": True, "active": active, "event": event}


@app.get("/v1/status/events")
async def status_events(conversation_id: str, request_id: str, since_seq: int = 0):
    """Get status events since a sequence number for a given request."""
    events = _get_status_events_since(conversation_id, request_id, since_seq)
    latest = status_latest_index.get((conversation_id, request_id))
    latest_seq = latest.get("seq") if latest else since_seq
    active = (conversation_id, request_id) in status_sessions
    return {"events": events, "latest_seq": latest_seq, "active": active}

# ============================================================================
# MEMORY SYSTEM ENDPOINTS
# ============================================================================

@app.post("/v1/memory/store", response_model=MemoryResponse)
async def store_memory(request: MemoryStoreRequest):
    """Store a memory explicitly."""
    if not MEMORY_AVAILABLE or not memory_manager:
        error_detail = "Memory system is not available."
        if not MEMORY_AVAILABLE:
            error_detail += f" Import failed: {memory_import_error}. Check /v1/memory/status for details."
        elif not memory_manager:
            error_detail += " Memory manager initialization failed. Check server logs and /v1/memory/status endpoint."
        raise HTTPException(
            status_code=503,
            detail=error_detail
        )
    
    try:
        # Store the memory
        memory_id = await memory_manager.store_memory(
            text=request.text,
            category=request.category,
            source=request.source or "explicit",
            metadata=request.metadata,
        )
        
        return MemoryResponse(
            success=True,
            message=f"Memory stored successfully",
            data={"memory_id": memory_id}
        )
    except Exception as e:
        print(f"Error storing memory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {str(e)}")

@app.post("/v1/memory/search", response_model=MemoryResponse)
async def search_memories(request: MemorySearchRequest):
    """Search memories by query."""
    if not MEMORY_AVAILABLE or not memory_manager:
        raise HTTPException(
            status_code=503,
            detail="Memory system is not available. Check MEMORY_ENABLED setting."
        )
    
    try:
        # Search for relevant memories
        results = await memory_manager.search_memories(
            query=request.query,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            category=request.category,
        )
        
        return MemoryResponse(
            success=True,
            message=f"Found {len(results)} relevant memories",
            data={"memories": results, "count": len(results)}
        )
    except Exception as e:
        print(f"Error searching memories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search memories: {str(e)}")

@app.get("/v1/memory/list", response_model=MemoryResponse)
async def list_memories(limit: Optional[int] = None):
    """List recent memories."""
    if not MEMORY_AVAILABLE or not memory_manager:
        raise HTTPException(
            status_code=503,
            detail="Memory system is not available. Check MEMORY_ENABLED setting."
        )
    
    try:
        # List memories
        memories = memory_manager.list_memories(limit=limit)
        
        return MemoryResponse(
            success=True,
            message=f"Retrieved {len(memories)} memories",
            data={"memories": memories, "count": len(memories), "total": memory_manager.count()}
        )
    except Exception as e:
        print(f"Error listing memories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list memories: {str(e)}")

@app.get("/v1/memory/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: str):
    """Get a specific memory by ID."""
    if not MEMORY_AVAILABLE or not memory_manager:
        raise HTTPException(
            status_code=503,
            detail="Memory system is not available. Check MEMORY_ENABLED setting."
        )
    
    try:
        # Get memory by ID
        memory = memory_manager.get_memory(memory_id)
        
        if not memory:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        
        return MemoryResponse(
            success=True,
            message="Memory retrieved successfully",
            data={"memory": memory}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting memory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get memory: {str(e)}")

@app.post("/v1/memory/extract", response_model=MemoryResponse)
async def extract_memories(request: MemoryExtractRequest):
    """Extract and store memories from a conversation."""
    if not MEMORY_AVAILABLE or not memory_manager:
        error_detail = "Memory system is not available."
        if not MEMORY_AVAILABLE:
            error_detail += f" Import failed: {memory_import_error}. Check /v1/memory/status for details."
        elif not memory_manager:
            error_detail += " Memory manager initialization failed. Check server logs and /v1/memory/status endpoint."
        raise HTTPException(
            status_code=503,
            detail=error_detail
        )
    
    try:
        # Check if auto-extract is enabled
        auto_extract = os.getenv("MEMORY_AUTO_EXTRACT", "true").lower() == "true"
        if not auto_extract:
            return MemoryResponse(
                success=False,
                message="Automatic memory extraction is disabled via MEMORY_AUTO_EXTRACT=false",
                data={"extracted": 0}
            )
        
        # Extract memories from conversation
        max_memories = request.max_memories or 1
        memory_ids = await memory_manager.extract_memories_from_conversation(
            messages=request.messages,
            max_memories=max_memories,
        )
        
        return MemoryResponse(
            success=True,
            message=f"Extracted and stored {len(memory_ids)} memories",
            data={"extracted": len(memory_ids), "memory_ids": memory_ids}
        )
    except Exception as e:
        print(f"Error extracting memories: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to extract memories: {str(e)}")

@app.get("/v1/memory/status")
async def memory_status():
    """Get the status of the memory system."""
    status = {
        "available": MEMORY_AVAILABLE,
        "enabled": os.getenv("MEMORY_ENABLED", "true").lower() == "true",
        "initialized": memory_manager is not None,
        "memory_count": memory_manager.count() if memory_manager else 0,
    }
    if not MEMORY_AVAILABLE:
        status["error"] = f"Memory module not available (import failed: {memory_import_error})"
        if memory_import_error and "numpy" in memory_import_error.lower():
            status["fix"] = "Install numpy with: pip install numpy"
    elif not status["enabled"]:
        status["error"] = "Memory system disabled via MEMORY_ENABLED=false"
    elif not status["initialized"]:
        status["error"] = "Memory manager failed to initialize (check server logs)"
    return status

@app.delete("/v1/memory/{memory_id}", response_model=MemoryResponse)
async def delete_memory(memory_id: str):
    """Delete a memory by ID."""
    if not MEMORY_AVAILABLE or not memory_manager:
        error_detail = "Memory system is not available."
        if not MEMORY_AVAILABLE:
            error_detail += " Memory module import failed."
        elif not memory_manager:
            error_detail += " Memory manager initialization failed. Check server logs and /v1/memory/status endpoint."
        raise HTTPException(
            status_code=503,
            detail=error_detail
        )
    
    try:
        # Delete memory
        deleted = memory_manager.delete_memory(memory_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")
        
        return MemoryResponse(
            success=True,
            message=f"Memory {memory_id} deleted successfully",
            data={"memory_id": memory_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting memory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {str(e)}")

# ============================================================================
# END MEMORY SYSTEM ENDPOINTS
# ============================================================================

# ============================================================================
# PHILOSOPHER MODE HELPER FUNCTIONS
# ============================================================================

async def get_all_available_tools() -> List[Dict]:
    """Get all available tools from all connected MCP servers and built-in proxy tools."""
    print(f"[PHILOSOPHER] get_all_available_tools called - MCP_AVAILABLE: {MCP_AVAILABLE}")
    
    all_tools = []
    
    # Add built-in proxy tools (web search, web scraper, news API)
    # These are always available if the server is running
    
    # 1. Web Search Tool
    all_tools.append({
        "name": "web_search",
        "description": "Search the web using Brave Search API (with DuckDuckGo fallback). Returns top search results with URLs, titles, and snippets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to execute (e.g., 'latest AI developments 2024')",
                }
            },
            "required": ["query"]
        },
        "server_id": "proxy_server"
    })
    print("[PHILOSOPHER] Added web_search tool")
    
    # 2. Web Scraper/Fetcher Tool
    all_tools.append({
        "name": "web_scraper",
        "description": "Fetch and scrape readable content from a web URL. Can optionally crawl a few same-domain pages and return extracted text content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch and scrape (must include http:// or https://)",
                },
                "crawl": {
                    "type": "boolean",
                    "description": "Whether to crawl linked pages on the same domain",
                    "default": True,
                },
                "max_pages": {
                    "type": "integer",
                    "description": "Maximum pages to scrape including the start page",
                    "default": 3,
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum link depth from the start page",
                    "default": 1,
                },
            },
            "required": ["url"]
        },
        "server_id": "proxy_server"
    })
    print("[PHILOSOPHER] Added web_scraper tool")
    
    # 3. News API Tool (only if API key is configured)
    news_api_key = os.getenv('NEWS_API_KEY')
    if news_api_key:
        all_tools.append({
            "name": "news_search",
            "description": "Search for recent news articles using News API. Returns articles with titles, URLs, descriptions, and publication dates.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for news articles (e.g., 'artificial intelligence')",
                    }
                },
                "required": ["query"]
            },
            "server_id": "proxy_server"
        })
        print("[PHILOSOPHER] Added news_search tool")
    else:
        print("[PHILOSOPHER] NEWS_API_KEY not configured, skipping news_search tool")

    all_tools.append({
        "name": "weather_info",
        "description": "Get weather information from Open-Meteo (api.open-meteo.com). Supports explicit location or memory-based location fallback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City/suburb/postcode (optional if available in memory)"},
                "detail": {"type": "string", "description": "summary, current, or forecast", "default": "summary"}
            }
        },
        "server_id": "proxy_server"
    })
    print("[PHILOSOPHER] Added weather_info tool")
    
    # 4. File manipulation tools (scratch directory only; when file ops available)
    if FILE_OPS_AVAILABLE:
        all_tools.append({
            "name": "read_file",
            "description": "Read a file from the scratch workspace. Supported: .txt, .md, .docx, .xlsx, .xls, .pdf, .png, .jpg, .jpeg, .py, .js, .html. Use filename only (e.g. notes.txt), no path traversal.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file to read (e.g. notes.txt)",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Optional max characters to return (default 12000).",
                    },
                },
                "required": ["filename"]
            },
            "server_id": "proxy_server"
        })
        all_tools.append({
            "name": "write_file",
            "description": "Write or overwrite a file in the scratch workspace. Supported: .txt, .md, .docx, .xlsx, .xls, .pdf, .py, .js, .html. Use filename with extension or filename plus format.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file (e.g. report.txt or report with format)",
                    },
                    "content": {
                        "type": "string",
                        "description": "Text content to write",
                    },
                    "format": {
                        "type": "string",
                        "description": "Format if filename has no extension (default: txt)",
                        "default": "txt"
                    }
                },
                "required": ["filename", "content"]
            },
            "server_id": "proxy_server"
        })
        all_tools.append({
            "name": "list_files",
            "description": "List all files in the scratch workspace with name, size, and modified time.",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
            "server_id": "proxy_server"
        })
        all_tools.append({
            "name": "delete_file",
            "description": "Delete a file from the scratch workspace. Use filename only (e.g. notes.txt).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name of the file to delete",
                    }
                },
                "required": ["filename"]
            },
            "server_id": "proxy_server"
        })
        print("[PHILOSOPHER] Added read_file, write_file, list_files, delete_file tools")
    else:
        print("[PHILOSOPHER] File ops not available, skipping file manipulation tools")
    
    # 5. runWorkflow (AutoGen team - code generation and automation)
    if AUTOGEN_AVAILABLE:
        all_tools.append({
            "name": "runWorkflow",
            "description": "Execute workflows for code generation and automation tasks using an AutoGen team. Use for tasks like building apps, generating code, or multi-step automation.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "contentPrompt": {
                        "type": "string",
                        "description": "The task to execute (e.g. 'build a javascript todo app', 'write a Python script that parses CSV')",
                    }
                },
                "required": ["contentPrompt"]
            },
            "server_id": "proxy_server"
        })
        print("[PHILOSOPHER] Added runWorkflow tool")
    else:
        print("[PHILOSOPHER] AutoGen not available, skipping runWorkflow tool")

    # 5b. runCodexCli (Codex CLI for CATBot code changes and tooling)
    if CODEX_ENABLED:
        all_tools.append({
            "name": "runCodexCli",
            "description": "Run Codex CLI in non-interactive mode to make CATBot code changes or add new capabilities. Always provide a clear prompt describing the change. Output is written to a scratch summary file.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Task instructions for Codex (e.g. 'Add a new /v1/proxy/codex tool in the proxy server and update docs')",
                    },
                },
                "required": ["prompt"]
            },
            "server_id": "proxy_server"
        })
        print("[PHILOSOPHER] Added runCodexCli tool")
    else:
        print("[PHILOSOPHER] Codex CLI disabled, skipping runCodexCli tool")
    
    # 6. run_browser_agent (standalone browser-use HTTP server; not tied to mcp_servers)
    # Browser-use runs as a separate HTTP server (MCP_BROWSER_USE_HTTP_URL); add tool when URL is configured
    run_browser_agent_tool = {
        "name": "run_browser_agent",
        "description": "Control a web browser using natural language commands. Executes browser automation tasks and returns results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "instruction": {
                    "type": "string",
                    "description": "Natural language instruction for browser automation (e.g., 'Navigate to Google and search for cats')",
                },
                "max_steps": {
                    "type": "integer",
                    "description": "Maximum number of steps the agent should take",
                    "default": 10
                },
                "use_vision": {
                    "type": "boolean",
                    "description": "Whether to use vision for understanding page content",
                    "default": True
                }
            },
            "required": ["instruction"]
        },
        "server_id": "proxy_server"
    }
    if MCP_BROWSER_USE_HTTP_URL:
        all_tools.append(run_browser_agent_tool)
        print(f"[PHILOSOPHER] Added run_browser_agent (standalone browser-use HTTP at {MCP_BROWSER_USE_HTTP_URL})")
        # Deep research (same browser-use ecosystem; proxy forwards to MCP browser server on port 5001)
        all_tools.append({
            "name": "run_deep_research",
            "description": "Performs comprehensive multi-step web research on a topic using multiple browser agents. Gathers information from many sources and returns a detailed research report with citations and findings. Use for in-depth research or comprehensive analysis requests.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "research_task": {
                        "type": "string",
                        "description": "The research topic or question to investigate (e.g. 'What are the latest developments in quantum computing?', 'Compare the best electric vehicles available in 2024')",
                    },
                    "researchTask": {
                        "type": "string",
                        "description": "Same as research_task; the research topic or question.",
                    },
                    "max_parallel_browsers": {
                        "type": "integer",
                        "description": "Optional: maximum number of parallel browser instances (default 3, max 5)",
                        "default": 3,
                    },
                    "maxParallelBrowsers": {
                        "type": "integer",
                        "description": "Optional: same as max_parallel_browsers",
                    },
                },
                "required": [],
            },
            "server_id": "proxy_server"
        })
        print("[PHILOSOPHER] Added run_deep_research (deep research agent)")
    else:
        print("[PHILOSOPHER] MCP_BROWSER_USE_HTTP_URL not set, skipping run_browser_agent")
    
    # Add MCP tools if MCP is available
    if MCP_AVAILABLE:
        # Debug: Check what servers are available
        print(f"[PHILOSOPHER] Checking MCP tools - mcp_clients: {len(mcp_clients)} clients, mcp_servers: {len(mcp_servers)} servers")
        print(f"[PHILOSOPHER] Connected client IDs: {list(mcp_clients.keys())}")
        print(f"[PHILOSOPHER] Server IDs in mcp_servers: {list(mcp_servers.keys())}")
        
        # Optional: also add run_browser_agent from mcp_servers if user added browser-use as a server and connected it,
        # and we did not already add it from MCP_BROWSER_USE_HTTP_URL (avoid duplicate)
        if not MCP_BROWSER_USE_HTTP_URL:
            for server_id, server in mcp_servers.items():
                server_status = server.get("status", "disconnected")
                if server_status == "connected" and _is_browser_use_server(server):
                    print(f"[PHILOSOPHER] Found connected browser-use server in mcp_servers: {server_id}")
                    all_tools.append({
                        **run_browser_agent_tool,
                        "server_id": server_id,
                    })
                    break  # only one browser-use
        
        # Get tools from each connected MCP client (non-browser-use servers)
        for server_id, client in mcp_clients.items():
            try:
                print(f"[PHILOSOPHER] Processing MCP server: {server_id}")
                # Check if this is the browser-use server (shouldn't be, but check anyway)
                server = mcp_servers.get(server_id)
                print(f"[PHILOSOPHER] Server config for {server_id}: {server}")
                
                if server and _is_browser_use_server(server):
                    # Skip - browser-use is added from MCP_BROWSER_USE_HTTP_URL or from mcp_servers above
                    print(f"[PHILOSOPHER] Skipping browser-use server {server_id} (already handled)")
                    continue
                else:
                    # Get tools from MCP server
                    print(f"[PHILOSOPHER] Requesting tools/list from MCP server {server_id}")
                    result = await client.request(method="tools/list", params={})
                    print(f"[PHILOSOPHER] tools/list response from {server_id}: {result}")
                    if result and "tools" in result:
                        print(f"[PHILOSOPHER] Found {len(result['tools'])} tools from server {server_id}")
                        for tool in result["tools"]:
                            tool["server_id"] = server_id
                            all_tools.append(tool)
                    else:
                        print(f"[PHILOSOPHER] No tools in response from server {server_id}")
            except Exception as e:
                print(f"[PHILOSOPHER] Error getting tools from server {server_id}: {e}")
                import traceback
                print(traceback.format_exc())
                continue
    else:
        print("[PHILOSOPHER] MCP not available, skipping MCP tools")
    
    print(f"[PHILOSOPHER] Total tools collected: {len(all_tools)}")
    return all_tools

async def execute_tool_for_philosopher(tool_name: str, parameters: Dict) -> str:
    """Execute a tool for philosopher mode. Returns result as string."""
    _log_tool_invocation("philosopher", tool_name, parameters)
    
    # Handle built-in proxy server tools
    if tool_name == "web_search":
        try:
            query = parameters.get("query", "")
            if not query:
                return "Error: 'query' parameter is required for web_search"
            
            # Call the proxy search endpoint
            result = await proxy_search(query)
            
            # Format results as readable text
            if result and "results" in result:
                results = result["results"]
                if not results:
                    return f"No search results found for query: {query}"
                
                formatted_results = []
                for i, item in enumerate(results, 1):
                    formatted_results.append(
                        f"{i}. {item.get('title', 'No title')}\n"
                        f"   URL: {item.get('url', 'No URL')}\n"
                        f"   {item.get('snippet', 'No description')}"
                    )
                
                return f"Search results for '{query}':\n\n" + "\n\n".join(formatted_results)
            else:
                return f"Search returned no results for query: {query}"
        except HTTPException as e:
            return f"Error executing web_search: {e.detail}"
        except Exception as e:
            return f"Error executing web_search: {str(e)}"
    
    elif tool_name == "web_scraper":
        try:
            url = parameters.get("url", "")
            if not url:
                return "Error: 'url' parameter is required for web_scraper"

            crawl = bool(parameters.get("crawl", True))
            max_pages = int(parameters.get("max_pages", 3) or 3)
            max_depth = int(parameters.get("max_depth", 1) or 1)

            # Call the proxy fetch endpoint with extraction + optional crawl
            result = await _do_proxy_fetch(url, crawl=crawl, max_pages=max_pages, max_depth=max_depth)

            if result and "content" in result:
                content = result["content"] or ""
                page_count = result.get("page_count", 1)
                # Truncate if too long (keep first 10000 characters)
                if len(content) > 10000:
                    return (
                        f"Scraped content from {url} (pages: {page_count}, truncated):\n\n"
                        f"{content[:10000]}...\n\n[Content truncated to 10000 characters]"
                    )
                return f"Scraped content from {url} (pages: {page_count}):\n\n{content}"
            else:
                return f"No content retrieved from URL: {url}"
        except HTTPException as e:
            return f"Error executing web_scraper: {e.detail}"
        except Exception as e:
            return f"Error executing web_scraper: {str(e)}"
    
    elif tool_name == "news_search":
        try:
            query = parameters.get("query", "")
            if not query:
                return "Error: 'query' parameter is required for news_search"
            
            # Call the proxy news search endpoint
            result = await proxy_news_search(query)
            
            # Format results as readable text
            if result and "articles" in result:
                articles = result["articles"]
                if not articles:
                    return f"No news articles found for query: {query}"
                
                formatted_articles = []
                for i, article in enumerate(articles[:10], 1):  # Limit to top 10
                    formatted_articles.append(
                        f"{i}. {article.get('title', 'No title')}\n"
                        f"   Source: {article.get('source', 'Unknown')}\n"
                        f"   Published: {article.get('publishedAt', 'Unknown date')}\n"
                        f"   URL: {article.get('url', 'No URL')}\n"
                        f"   {article.get('description', 'No description')}"
                    )
                
                total = result.get("totalResults", len(articles))
                return f"News articles for '{query}' (showing {len(formatted_articles)} of {total}):\n\n" + "\n\n".join(formatted_articles)
            else:
                return f"News search returned no articles for query: {query}"
        except HTTPException as e:
            return f"Error executing news_search: {e.detail}"
        except Exception as e:
            return f"Error executing news_search: {str(e)}"
    
    elif tool_name == "weather_info":
        try:
            result = await _do_proxy_weather(
                location=parameters.get("location"),
                detail=parameters.get("detail", "summary"),
                user_id=parameters.get("user_id"),
                memory_manager=memory_manager if MEMORY_AVAILABLE else None,
            )
            return json.dumps(result, ensure_ascii=False)
        except HTTPException as e:
            return f"Error executing weather_info: {e.detail}"
        except Exception as e:
            return f"Error executing weather_info: {str(e)}"

    # Handle file manipulation tools (scratch workspace)
    elif tool_name == "read_file":
        try:
            filename = parameters.get("filename", "").strip()
            if not filename:
                return "Error: 'filename' is required for read_file"
            result = await _read_file_internal(filename)
            if not result.get("success"):
                return result.get("message", "Read failed")
            data = result.get("data", {})
            content = data.get("content", "")
            content = content if isinstance(content, str) else str(content)
            req_max_chars = parameters.get("max_chars")
            if isinstance(req_max_chars, str) and req_max_chars.isdigit():
                req_max_chars = int(req_max_chars)
            if isinstance(req_max_chars, (int, float)):
                max_chars = int(req_max_chars)
            else:
                max_chars = int(os.getenv("READ_FILE_MAX_CHARS", "12000") or 12000)
            max_chars = max(2000, max_chars)
            if content and len(content) > max_chars:
                head = max_chars // 2
                tail = max_chars - head
                removed = len(content) - max_chars
                return (
                    f"{content[:head]}\n\n"
                    f"...[truncated {removed} chars]...\n\n"
                    f"{content[-tail:]}"
                )
            return content if content else "(empty file)"
        except Exception as e:
            return f"Error executing read_file: {str(e)}"
    
    elif tool_name == "write_file":
        try:
            filename = parameters.get("filename", "").strip()
            content = parameters.get("content", "")
            content = content if isinstance(content, str) else str(content)
            fmt = (parameters.get("format") or "txt").strip() or "txt"
            if not filename:
                return "Error: 'filename' is required for write_file"
            result = await _write_file_internal(filename, content, format=fmt)
            if not result.get("success"):
                return result.get("message", "Write failed")
            return result.get("message", "File written.")
        except Exception as e:
            return f"Error executing write_file: {str(e)}"
    
    elif tool_name == "list_files":
        try:
            result = await _list_files_internal()
            if not result.get("success"):
                return result.get("message", "List failed")
            files = result.get("files", [])
            if not files:
                return f"Scratch workspace is empty. (Directory: {result.get('scratch_dir', 'scratch')})"
            return _format_list_files_for_tool_output(files, include_sizes=True)
        except Exception as e:
            return f"Error executing list_files: {str(e)}"
    
    elif tool_name == "delete_file":
        try:
            filename = parameters.get("filename", "").strip()
            if not filename:
                return "Error: 'filename' is required for delete_file"
            result = await _delete_file_internal(filename)
            if not result.get("success"):
                return result.get("message", "Delete failed")
            return result.get("message", "File deleted.")
        except Exception as e:
            return f"Error executing delete_file: {str(e)}"
    
    elif tool_name == "runWorkflow":
        try:
            content_prompt = (parameters.get("contentPrompt") or parameters.get("content_prompt") or "").strip()
            if not content_prompt:
                return "Error: 'contentPrompt' is required for runWorkflow"
            if not AUTOGEN_AVAILABLE:
                return "Error: Workflow (AutoGen) is not available."
            result = await _do_autogen(content_prompt)
            msg = result.get("output") or result.get("response") or str(result)
            return msg
        except HTTPException as e:
            return f"Error executing runWorkflow: {e.detail}"
        except Exception as e:
            return f"Error executing runWorkflow: {str(e)}"

    elif tool_name == "runCodexCli":
        try:
            codex_prompt = (parameters.get("prompt") or "").strip()
            if not codex_prompt:
                return "Error: 'prompt' is required for runCodexCli"
            result = await _run_codex_cli(codex_prompt)
            summary_file = result.get("summaryFile")
            exit_code = result.get("exitCode")
            timed_out = result.get("timedOut")
            return (
                f"Codex CLI finished (exit_code={exit_code}, timed_out={timed_out}). "
                f"Summary file: {summary_file}"
            )
        except HTTPException as e:
            return f"Error executing runCodexCli: {e.detail}"
        except Exception as e:
            return f"Error executing runCodexCli: {str(e)}"
    
    # Handle run_browser_agent (standalone browser-use HTTP server; no mcp_servers entry required)
    elif tool_name == "run_browser_agent":
        if not MCP_BROWSER_USE_HTTP_URL:
            return "Error: Browser-use is not configured (MCP_BROWSER_USE_HTTP_URL not set)."
        try:
            instruction = (parameters.get("instruction") or parameters.get("task") or "").strip()
            if not instruction:
                return "Error: 'instruction' is required for run_browser_agent"
            result = await _browser_use_http_call_tool("run_browser_agent", parameters)
            content = result.get("content", [])
            if isinstance(content, list):
                texts = [item.get("text", str(item)) for item in content if isinstance(item, dict)]
                return "\n".join(texts) if texts else "Browser agent completed (no output)."
            return str(content)
        except Exception as e:
            return f"Error executing run_browser_agent: {BROWSER_USE_HTTP_UNAVAILABLE_MSG} {str(e)}"
    
    # Handle run_deep_research (proxies to MCP browser server /api/deep-research on port 5001)
    elif tool_name == "run_deep_research":
        research_task = (parameters.get("research_task") or parameters.get("researchTask") or "").strip()
        if not research_task:
            return "Error: 'research_task' or 'researchTask' is required for run_deep_research."
        max_parallel = parameters.get("max_parallel_browsers") or parameters.get("maxParallelBrowsers")
        if max_parallel is not None:
            try:
                max_parallel = min(5, max(1, int(max_parallel)))
            except (TypeError, ValueError):
                max_parallel = 3
        body = {"research_task": research_task}
        if max_parallel is not None:
            body["max_parallel_browsers"] = max_parallel
        try:
            result = await _do_deep_research(body)
            # Flask returns { success, result, error }; proxy returns response.json()
            report = result.get("result") or result.get("message") or result.get("output")
            if report:
                return str(report)
            if not result.get("success", True) and result.get("error"):
                return f"Deep research failed: {result.get('error')}"
            return str(result)
        except HTTPException as e:
            return f"Error executing run_deep_research: {e.detail}"
        except Exception as e:
            return f"Error executing run_deep_research: {str(e)}"
    
    # Handle MCP tools
    elif MCP_AVAILABLE:
        # Find which server has this tool
        all_tools = await get_all_available_tools()
        server_id = None
        
        for tool in all_tools:
            if tool.get("name") == tool_name:
                server_id = tool.get("server_id")
                break
        
        if not server_id:
            return f"Error: Tool '{tool_name}' not found on any connected server"
        
        # Execute the tool using the existing call_tool logic
        try:
            request = ToolCallRequest(toolName=tool_name, parameters=parameters)
            result = await call_tool(server_id, request)
            
            # Extract result content
            if result and "result" in result:
                result_data = result["result"]
                if "content" in result_data:
                    content = result_data["content"]
                    if isinstance(content, list):
                        # Extract text from content array
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                        return "\n".join(text_parts)
                    return str(content)
                return str(result_data)
            
            return str(result)
        except Exception as e:
            return f"Error executing tool {tool_name}: {str(e)}"
    else:
        return f"Error: Tool '{tool_name}' is not a built-in tool and MCP is not available"

# ============================================================================
# PHILOSOPHER MODE ENDPOINTS
# ============================================================================

@app.post("/v1/philosopher/start", response_model=PhilosopherResponse)
async def philosopher_start(request: PhilosopherStartRequest):
    """Enable philosopher mode for a conversation."""
    if not PHILOSOPHER_MODE_AVAILABLE or not PhilosopherMode:
        raise HTTPException(
            status_code=503,
            detail="Philosopher mode is not available. Check server logs for details."
        )
    
    # Check if philosopher mode is enabled
    philosopher_enabled = os.getenv("PHILOSOPHER_MODE_ENABLED", "true").lower() == "true"
    if not philosopher_enabled:
        raise HTTPException(
            status_code=503,
            detail="Philosopher mode is disabled via PHILOSOPHER_MODE_ENABLED=false"
        )
    
    # Get conversation ID
    conversation_id = request.conversation_id or request.user_id or "default"
    
    # Check if already active
    if philosopher_mode_active.get(conversation_id, False):
        return PhilosopherResponse(
            success=True,
            message="Philosopher mode is already active for this conversation",
            data={"conversation_id": conversation_id, "active": True}
        )
    
    try:
        # Get API configuration
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured")
        
        api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        # Use OPENAI_MODEL directly (not TELEGRAM_DEFAULT_MODEL) since philosopher mode is not Telegram-specific
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # Create philosopher mode instance with tool support
        philosopher = PhilosopherMode(
            api_key=api_key,
            api_base=api_base,
            model=model,
            memory_manager=memory_manager if MEMORY_AVAILABLE else None,
            max_cycles=int(os.getenv("PHILOSOPHER_MAX_CYCLES", "10")),
            similarity_threshold=float(os.getenv("PHILOSOPHER_SIMILARITY_THRESHOLD", "0.3")),
            memory_limit=int(os.getenv("PHILOSOPHER_MEMORY_LIMIT", "10")),
            conversation_history_limit=int(os.getenv("PHILOSOPHER_CONVERSATION_HISTORY_LIMIT", "3")),
            tool_executor=execute_tool_for_philosopher,
            get_tools_func=get_all_available_tools,
            diversification_threshold=int(os.getenv("PHILOSOPHER_DIVERSIFICATION_THRESHOLD", "7")),
        )
        
        # Store instance and activate mode
        philosopher_mode_instances[conversation_id] = philosopher
        philosopher_mode_active[conversation_id] = True
        
        return PhilosopherResponse(
            success=True,
            message="Philosopher mode activated",
            data={"conversation_id": conversation_id, "active": True}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error starting philosopher mode: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to start philosopher mode: {str(e)}")

@app.post("/v1/philosopher/stop", response_model=PhilosopherResponse)
async def philosopher_stop(request: PhilosopherStopRequest):
    """Disable philosopher mode for a conversation."""
    # Get conversation ID
    conversation_id = request.conversation_id or request.user_id or "default"
    
    # Check if active
    if not philosopher_mode_active.get(conversation_id, False):
        return PhilosopherResponse(
            success=True,
            message="Philosopher mode is not active for this conversation",
            data={"conversation_id": conversation_id, "active": False}
        )
    
    try:
        # Deactivate mode
        philosopher_mode_active[conversation_id] = False
        # Remove instance (optional - could keep for reuse)
        philosopher_mode_instances.pop(conversation_id, None)
        
        return PhilosopherResponse(
            success=True,
            message="Philosopher mode deactivated",
            data={"conversation_id": conversation_id, "active": False}
        )
    except Exception as e:
        print(f"Error stopping philosopher mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop philosopher mode: {str(e)}")

@app.get("/v1/philosopher/status")
async def philosopher_status(conversation_id: Optional[str] = None, user_id: Optional[str] = None):
    """Check if philosopher mode is active for a conversation."""
    # Get conversation ID
    conv_id = conversation_id or user_id or "default"
    
    is_active = philosopher_mode_active.get(conv_id, False)
    
    return {
        "active": is_active,
        "conversation_id": conv_id,
        "available": PHILOSOPHER_MODE_AVAILABLE,
        "enabled": os.getenv("PHILOSOPHER_MODE_ENABLED", "true").lower() == "true"
    }

@app.post("/v1/philosopher/contemplate", response_model=PhilosopherResponse)
async def philosopher_contemplate(request: PhilosopherContemplateRequest):
    """Execute a single contemplation cycle."""
    if not PHILOSOPHER_MODE_AVAILABLE or not PhilosopherMode:
        raise HTTPException(
            status_code=503,
            detail="Philosopher mode is not available. Check server logs for details."
        )
    
    # Get conversation ID
    conversation_id = request.conversation_id or request.user_id or "default"
    
    # Check if mode is active
    if not philosopher_mode_active.get(conversation_id, False):
        raise HTTPException(
            status_code=400,
            detail="Philosopher mode is not active for this conversation. Start it first with /v1/philosopher/start"
        )
    
    # Get philosopher instance
    philosopher = philosopher_mode_instances.get(conversation_id)
    if not philosopher:
        raise HTTPException(
            status_code=500,
            detail="Philosopher mode instance not found. Try restarting philosopher mode."
        )
    
    try:
        # Generate question if not provided
        if request.question:
            question = request.question
        else:
            question = await philosopher.generate_contemplation_question()
            if not question:
                raise HTTPException(status_code=500, detail="Failed to generate contemplation question")
        
        # Execute contemplation
        result = await philosopher.contemplate_question(question)
        
        # Store contemplation in memory
        memory_id = await philosopher.store_contemplation(
            question=result["question"],
            conclusion=result["conclusion"],
            cycle_count=result["cycle_count"]
        )
        
        return PhilosopherResponse(
            success=True,
            message="Contemplation completed",
            data={
                "question": result["question"],
                "conclusion": result["conclusion"],
                "contemplation_steps": result["contemplation_steps"],
                "cycle_count": result["cycle_count"],
                "memory_id": memory_id,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during contemplation: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to contemplate: {str(e)}")

# ============================================================================
# END PHILOSOPHER MODE ENDPOINTS
# ============================================================================

# Simple test endpoint to verify requests are reaching the server
@app.get("/test")
async def test_endpoint():
    """Simple test endpoint that should always work."""
    import sys
    print("🧪 TEST endpoint called", flush=True)
    sys.stdout.flush()
    return {"message": "test successful", "timestamp": time.time()}

# Monitoring dashboard (standalone)
@app.get("/monitor")
async def monitor_dashboard():
    """Serve the monitoring dashboard HTML."""
    dashboard_file = _PROJECT_ROOT / "docs" / "monitoring_dashboard.html"
    if not dashboard_file.exists():
        return HTMLResponse(content="<h1>Monitoring dashboard not found.</h1>", status_code=404)
    return HTMLResponse(content=dashboard_file.read_text(encoding="utf-8"), status_code=200)


@app.get("/monitor/summary")
async def monitor_summary():
    """Return high-level system status summary."""
    uptime_seconds = max(0.0, time.time() - PROXY_START_TIME)
    openai_key_present = bool(os.getenv("OPENAI_API_KEY") or os.getenv("MCP_LLM_OPENAI_API_KEY"))
    return {
        "time": time.time(),
        "uptime_seconds": uptime_seconds,
        "memory_available": MEMORY_AVAILABLE,
        "telegram_tools_enabled": TELEGRAM_TOOLS_ENABLED,
        "status_sessions_active": len(status_sessions),
        "openai_api_key_configured": openai_key_present,
        "status_events_file": str(STATUS_EVENTS_FILE),
    }


@app.get("/monitor/status")
async def monitor_status(limit: int = 50):
    """Return recent status events for dashboard display."""
    limit = max(1, min(200, limit))
    return {"events": _get_recent_status_events(limit)}


@app.get("/monitor/logs")
async def monitor_logs(limit: int = 200):
    """Return the last N lines from the proxy log file if configured."""
    limit = max(1, min(1000, limit))
    log_path_env = os.getenv("PROXY_LOG_FILE") or ""
    log_path = Path(log_path_env) if log_path_env else None
    if not log_path or not log_path.exists():
        return {"available": False, "lines": []}
    text = _tail_text_file(log_path, max_lines=limit)
    lines = text.splitlines()
    return {"available": True, "lines": lines[-limit:]}

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Add explicit logging to debug
    import sys
    print("ðŸ¥ Health check endpoint called", flush=True)
    sys.stdout.flush()
    try:
        result = {"status": "healthy", "timestamp": time.time()}
        print(f"ðŸ¥ Health check returning: {result}", flush=True)
        sys.stdout.flush()
        return result
    except Exception as e:
        import traceback
        print(f"âŒ Health check error: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        sys.stdout.flush()
        raise


@app.get("/v1/client-config")
async def client_config():
    """Expose safe client defaults from .env (no secrets)."""
    tts_model = _env_str("TTS_MODEL") or _env_str("TELEGRAM_TTS_MODEL")
    tts_voice = _env_str("TTS_VOICE") or _env_str("TELEGRAM_TTS_VOICE")
    return {
        "ttsEndpoint": _env_str("TTS_ENDPOINT"),
        "ttsModel": tts_model,
        "ttsVoice": tts_voice,
    }

# Models list proxy endpoint to handle CORS and mixed content
@app.get("/v1/proxy/models")
async def proxy_models(request: Request, endpoint: Optional[str] = None):
    """
    Proxy models list requests to handle CORS and avoid mixed content issues.
    Routes requests to the OpenAI-compatible API endpoint specified in the request.
    """
    try:
        # Get the endpoint from query parameter or use default
        if not endpoint:
            endpoint = request.query_params.get('endpoint', '')
        
        # If still no endpoint, use default from environment or localhost
        if not endpoint:
            endpoint = os.getenv('OPENAI_API_BASE', 'http://localhost:1234/v1/models')
        else:
            # Ensure the endpoint includes the full path if not already present
            if not endpoint.endswith('/models'):
                endpoint = endpoint.rstrip('/') + '/models'
        
        # Get Authorization header from the request
        auth_header = request.headers.get('Authorization', '')
        
        # Build headers for the forwarded request
        headers = {}
        if auth_header:
            headers['Authorization'] = auth_header
        
        # Add organization/project headers if present in original request
        org_header = request.headers.get('OpenAI-Organization')
        if org_header:
            headers['OpenAI-Organization'] = org_header
        
        project_header = request.headers.get('OpenAI-Project')
        if project_header:
            headers['OpenAI-Project'] = project_header
        
        print(f"📋 Proxying models list request to: {endpoint}")
        
        # Forward the request to the LLM service
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                endpoint,
                headers=headers
            )
        
        print(f"✅ Models list response status: {response.status_code}")
        
        # Check if the response is successful
        if response.status_code != 200:
            print(f"âŒ LLM service returned error: {response.status_code}")
            print(f"   Response text: {response.text[:500]}")
            return JSONResponse(
                content=response.json() if response.headers.get('content-type', '').startswith('application/json') else {"error": response.text},
                status_code=response.status_code
            )
        
        # Return the JSON response
        try:
            response_data = response.json()
            return JSONResponse(content=response_data, status_code=200)
        except Exception as json_error:
            print(f"âŒ Failed to parse JSON response: {json_error}")
            return JSONResponse(
                content={"error": "Invalid JSON response from LLM service"},
                status_code=500
            )
    
    except httpx.ConnectError as e:
        print(f"âŒ Connection error: Could not connect to LLM service")
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to LLM service. Please check the endpoint configuration."
        )
    except Exception as e:
        print(f"âŒ Models list proxy error: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to proxy models list request: {str(e)}")

# Shared browser-agent logic for route and Telegram tool runner
async def _do_browser_agent(body: Dict[str, Any]) -> Dict[str, Any]:
    """Forward browser-agent request to MCP browser server. Returns response dict or raises HTTPException."""
    mcp_browser_url = os.getenv('MCP_BROWSER_SERVER_URL', None)
    if not mcp_browser_url:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            mcp_browser_url = f"http://{local_ip}:5001"
            print(f"   Detected local IP: {local_ip}, using {mcp_browser_url}")
        except Exception:
            mcp_browser_url = "http://127.0.0.1:5001"
            print(f"   Using default: {mcp_browser_url}")
    else:
        print(f"   Using configured MCP_BROWSER_SERVER_URL: {mcp_browser_url}")
    endpoint = f"{mcp_browser_url.rstrip('/')}/api/browser-agent"
    print(f"ðŸŒ Proxying browser-agent request to: {endpoint}")
    health_endpoint = f"{mcp_browser_url.rstrip('/')}/api/health"
    health_check_passed = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as health_client:
            health_response = await health_client.get(health_endpoint)
            if health_response.status_code == 200:
                health_check_passed = True
    except Exception as health_err:
        print(f"   âš ï¸  MCP browser server health check failed: {health_err}")
        if not mcp_browser_url.startswith("http://127.0.0.1"):
            mcp_browser_url = "http://127.0.0.1:5001"
            endpoint = f"{mcp_browser_url.rstrip('/')}/api/browser-agent"
            try:
                async with httpx.AsyncClient(timeout=5.0) as hc:
                    hr = await hc.get(f"{mcp_browser_url.rstrip('/')}/api/health")
                    if hr.status_code == 200:
                        health_check_passed = True
            except Exception:
                pass
    if not health_check_passed:
        print(f"   âš ï¸  Warning: Health check failed, but continuing with request")
    timeout = httpx.Timeout(connect=10.0, read=10800.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.post(endpoint, json=body, headers={'Content-Type': 'application/json'})
        except httpx.ConnectError as conn_err:
            print(f"âŒ Connection error to MCP browser server: {conn_err}")
            raise HTTPException(
                status_code=503,
                detail="Could not connect to MCP browser server. Please ensure it's running on port 5001."
            )
        except httpx.ReadTimeout:
            raise HTTPException(
                status_code=504,
                detail="Browser automation task timed out. Please try again or check the MCP browser server logs."
            )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Browser automation task timed out. Please try again or check the MCP browser server logs."
            )
    print(f"✅ Browser-agent response status: {response.status_code}")
    if response.status_code != 200:
        error_content = response.json() if response.headers.get('content-type', '').startswith('application/json') else {"error": response.text}
        print(f"   Error response: {error_content}")
        raise HTTPException(status_code=response.status_code, detail=error_content.get("error", str(error_content)))
    return response.json()


@app.post("/v1/proxy/browser-agent")
async def proxy_browser_agent(request: Request):
    """Proxy browser automation requests to the MCP browser server."""
    body = await request.json()
    result = await _do_browser_agent(body)
    return JSONResponse(content=result, status_code=200)


# Shared deep-research logic for route and Telegram tool runner
async def _do_deep_research(body: Dict[str, Any]) -> Dict[str, Any]:
    """Forward deep-research request to MCP browser server. Returns response dict or raises HTTPException."""
    mcp_browser_url = os.getenv('MCP_BROWSER_SERVER_URL', None)
    if not mcp_browser_url:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            mcp_browser_url = f"http://{local_ip}:5001"
            print(f"   Detected local IP: {local_ip}, using {mcp_browser_url}")
        except Exception:
            mcp_browser_url = "http://127.0.0.1:5001"
            print(f"   Using default: {mcp_browser_url}")
    else:
        print(f"   Using configured MCP_BROWSER_SERVER_URL: {mcp_browser_url}")
    endpoint = f"{mcp_browser_url.rstrip('/')}/api/deep-research"
    print(f"🔬 Proxying deep-research request to: {endpoint}")
    timeout = httpx.Timeout(connect=10.0, read=10800.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(endpoint, json=body, headers={'Content-Type': 'application/json'})
        except httpx.ConnectError as conn_err:
            print(f"âŒ Connection error to MCP browser server: {conn_err}")
            raise HTTPException(
                status_code=503,
                detail="Could not connect to MCP browser server. Please ensure it's running on port 5001."
            )
        except httpx.ReadTimeout as timeout_err:
            print(f"âŒ Read timeout from MCP browser server: {timeout_err}")
            raise HTTPException(
                status_code=504,
                detail="Deep research task timed out. Please try again or check the MCP browser server logs."
            )
    print(f"✅ Deep-research response status: {response.status_code}")
    if response.status_code != 200:
        error_content = response.json() if response.headers.get('content-type', '').startswith('application/json') else {"error": response.text}
        raise HTTPException(status_code=response.status_code, detail=error_content.get("error", str(error_content)))
    return response.json()


@app.post("/v1/proxy/deep-research")
async def proxy_deep_research(request: Request):
    """Proxy deep research requests to the MCP browser server."""
    try:
        body = await request.json()
        result = await _do_deep_research(body)
        return JSONResponse(content=result, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        print(f"âŒ Deep-research proxy error: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to proxy deep-research request: {str(e)}")

# Chat completions proxy endpoint to handle CORS and mixed content
@app.post("/v1/proxy/chat/completions")
async def proxy_chat_completions(request: Request):
    """
    Proxy chat completions requests to handle CORS and avoid mixed content issues.
    Routes requests to the OpenAI-compatible API endpoint specified in the request.
    """
    try:
        # Get the request body
        body = await request.json()
        
        # Get the endpoint from query parameter or request body, or use default
        endpoint = request.query_params.get('endpoint', '')
        if not endpoint:
            # Try to get from body (some clients might send it)
            endpoint = body.get('_endpoint', '')
        
        # If still no endpoint, use default from environment or localhost
        if not endpoint:
            endpoint = os.getenv('OPENAI_API_BASE', 'http://localhost:1234/v1/chat/completions')
        endpoint = _normalize_chat_endpoint(endpoint)
        
        # Remove internal endpoint parameter from body before forwarding
        body_clean = {k: v for k, v in body.items() if k != '_endpoint'}
        
        # Get Authorization header from the request
        auth_header = request.headers.get('Authorization', '')
        
        # Build headers for the forwarded request
        headers = {
            'Content-Type': 'application/json'
        }
        if auth_header:
            headers['Authorization'] = auth_header
        
        # Add organization/project headers if present in original request
        org_header = request.headers.get('OpenAI-Organization')
        if org_header:
            headers['OpenAI-Organization'] = org_header
        
        project_header = request.headers.get('OpenAI-Project')
        if project_header:
            headers['OpenAI-Project'] = project_header
        
        print(f"💬 Proxying chat completions request to: {endpoint}")
        print(f"   Model: {body_clean.get('model', 'unknown')}")
        
        max_tokens = _get_max_tokens_from_payload(body_clean)
        summarized = False
        if isinstance(body_clean.get("messages"), list):
            estimated = _estimate_total_tokens(body_clean["messages"], max_tokens)
            if estimated > get_max_token_limit():
                body_clean["messages"] = await _summarize_messages_for_budget_proxy(
                    body_clean["messages"],
                    endpoint=endpoint,
                    headers=headers,
                    model_name=body_clean.get("model", ""),
                    max_tokens=max_tokens,
                    large_model=LARGE_PAYLOAD_MODEL,
                    large_endpoint=LARGE_PAYLOAD_ENDPOINT,
                )
                summarized = True

        response = await _call_chat_completion(endpoint, headers, body_clean, timeout_seconds=120.0)
        
        print(f"✅ Chat completions response status: {response.status_code}")
        
        # Check if the response is successful
        if response.status_code != 200:
            print(f"âŒ LLM service returned error: {response.status_code}")
            print(f"   Response text: {response.text[:500]}")
            error_text = response.text or ""
            if is_context_limit_error(response.status_code, error_text):
                # Retry with summarization if we haven't yet.
                if not summarized and isinstance(body_clean.get("messages"), list):
                    body_clean["messages"] = await _summarize_messages_for_budget_proxy(
                        body_clean["messages"],
                        endpoint=endpoint,
                        headers=headers,
                        model_name=body_clean.get("model", ""),
                        max_tokens=max_tokens,
                        large_model=LARGE_PAYLOAD_MODEL,
                        large_endpoint=LARGE_PAYLOAD_ENDPOINT,
                    )
                    summarized = True
                    response = await _call_chat_completion(endpoint, headers, body_clean, timeout_seconds=120.0)
                # Retry with large payload model if configured
                if response.status_code != 200 and LARGE_PAYLOAD_MODEL:
                    body_clean["model"] = LARGE_PAYLOAD_MODEL
                    large_endpoint = _normalize_chat_endpoint(LARGE_PAYLOAD_ENDPOINT or endpoint)
                    response = await _call_chat_completion(large_endpoint, headers, body_clean, timeout_seconds=120.0)
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        return JSONResponse(content=response_data, status_code=200)
                    except Exception as json_error:
                        print(f"âŒ Failed to parse JSON response after retry: {json_error}")
                        return JSONResponse(content={"error": "Invalid JSON response from LLM service"}, status_code=500)
            return JSONResponse(
                content=response.json() if response.headers.get('content-type', '').startswith('application/json') else {"error": response.text},
                status_code=response.status_code
            )
        
        # Return the JSON response
        try:
            response_data = response.json()
            return JSONResponse(content=response_data, status_code=200)
        except Exception as json_error:
            print(f"âŒ Failed to parse JSON response: {json_error}")
            return JSONResponse(
                content={"error": "Invalid JSON response from LLM service"},
                status_code=500
            )
    
    except httpx.ConnectError as e:
        print(f"âŒ Connection error: Could not connect to LLM service")
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to LLM service. Please check the endpoint configuration."
        )
    except Exception as e:
        print(f"âŒ Chat completions proxy error: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to proxy chat completions request: {str(e)}")

# OPTIONS handler for Whisper endpoint to handle CORS preflight
@app.options("/v1/audio/transcriptions")
async def proxy_whisper_options(request: Request):
    """Handle CORS preflight requests for Whisper endpoint."""
    return JSONResponse(
        content={},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
    )

# Whisper proxy endpoint to handle CORS; compatible with OpenAI whisper-1 (passes key when needed)
@app.post("/v1/audio/transcriptions")
async def proxy_whisper(request: Request):
    """Proxy Whisper transcription requests to handle CORS. Client Authorization is for proxy auth only; upstream uses WHISPER_API_KEY."""
    try:
        # Get the form data from the request
        form_data = await request.form()
        
        # Get the Whisper endpoint (defaulting to localhost:8001)
        whisper_endpoint = os.getenv('WHISPER_ENDPOINT', 'http://localhost:8001/v1/audio/transcriptions')
        
        print(f"ðŸ“ Proxying Whisper request to: {whisper_endpoint}")
        
        # Outgoing auth to Whisper/OpenAI uses only WHISPER_API_KEY (client Authorization is for proxy auth, not forwarded)
        forward_headers = {}
        whisper_api_key = os.getenv("WHISPER_API_KEY")
        if whisper_api_key:
            forward_headers["Authorization"] = f"Bearer {whisper_api_key}"
        
        # Prepare the files and data for forwarding
        files = {}
        data = {}
        
        for key, value in form_data.items():
            if hasattr(value, 'read'):  # This is a file
                # Read the file content
                file_content = await value.read()
                files[key] = (value.filename, file_content, value.content_type)
                print(f"  📎 File: {value.filename} ({len(file_content)} bytes)")
            else:  # This is a regular form field
                data[key] = value
                print(f"  📄 Field: {key} = {value}")
        
        # Forward the request to the Whisper service (server key only; client auth stays between client and proxy)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                whisper_endpoint,
                files=files,
                data=data,
                headers=forward_headers
            )
        
        print(f"✅ Whisper response status: {response.status_code}")
        print(f"📄 Response content type: {response.headers.get('content-type', 'unknown')}")
        
        # Check if the response is successful
        if response.status_code != 200:
            print(f"âŒ Whisper service returned error: {response.status_code}")
            print(f"   Response text: {response.text}")
            return JSONResponse(
                content={"error": f"Whisper service error: {response.text}"},
                status_code=response.status_code
            )
        
        # Try to parse the JSON response
        try:
            response_data = response.json()
            print(f"✅ Parsed JSON response: {response_data}")
            return JSONResponse(content=response_data, status_code=200)
        except Exception as json_error:
            print(f"âŒ Failed to parse JSON response: {json_error}")
            print(f"   Raw response text: {response.text[:200]}")
            # Return the raw text if JSON parsing fails
            return JSONResponse(
                content={"text": response.text},
                status_code=200
            )
    
    except httpx.ConnectError as e:
        print(f"âŒ Connection error: Could not connect to Whisper service at {whisper_endpoint}")
        print(f"   Make sure the Whisper service is running on port 8001")
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to Whisper service. Make sure it's running on port 8001."
        )
    except Exception as e:
        print(f"âŒ Whisper proxy error: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to proxy Whisper request: {str(e)}")

def _build_wav_header(sample_rate: int, channels: int, bits_per_sample: int, pcm_bytes_len: int) -> bytes:
    channels = max(1, int(channels))
    sample_rate = max(8000, int(sample_rate))
    bits_per_sample = max(8, int(bits_per_sample))
    block_align = channels * (bits_per_sample // 8)
    byte_rate = sample_rate * block_align
    return (
        b"RIFF"
        + struct.pack("<I", 36 + pcm_bytes_len)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", 16)
        + struct.pack("<H", 1)
        + struct.pack("<H", channels)
        + struct.pack("<I", sample_rate)
        + struct.pack("<I", byte_rate)
        + struct.pack("<H", block_align)
        + struct.pack("<H", bits_per_sample)
        + b"data"
        + struct.pack("<I", pcm_bytes_len)
    )


def _float_audio_to_pcm16_bytes(audio: Any) -> bytes:
    try:
        import numpy as np  # type: ignore

        arr = np.asarray(audio, dtype=np.float32).reshape(-1)
        arr = np.clip(arr, -1.0, 1.0)
        return (arr * 32767.0).astype(np.int16).tobytes()
    except Exception:
        pass

    out = bytearray()
    try:
        for value in (audio or []):
            f = float(value)
            if f > 1.0:
                f = 1.0
            elif f < -1.0:
                f = -1.0
            out.extend(struct.pack("<h", int(f * 32767.0)))
    except Exception as exc:
        raise RuntimeError(f"Could not convert generated audio to PCM16: {exc}") from exc
    return bytes(out)


def _normalize_embedded_kitten_repo_id(model_name: Optional[str]) -> str:
    raw = (model_name or EMBEDDED_KITTEN_MODEL or "").strip()
    if not raw:
        raw = "KittenML/kitten-tts-nano-0.2"
    if "/" not in raw:
        return f"KittenML/{raw}"
    return raw


def _get_embedded_kitten_available_voices(model: Any) -> List[str]:
    available = getattr(model, "available_voices", None)
    if not available:
        return []
    if isinstance(available, (list, tuple, set)):
        return [str(v).strip() for v in available if str(v).strip()]
    return []


def _fetch_embedded_kitten_config(repo_id: str) -> Dict[str, Any]:
    if _hf_hub_download is None:
        return {}
    try:
        config_path = _hf_hub_download(repo_id=repo_id, filename="config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _extract_embedded_kitten_voice_aliases(config: Dict[str, Any]) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    raw_aliases = config.get("voice_aliases")
    if isinstance(raw_aliases, dict):
        for alias, target in raw_aliases.items():
            alias_key = str(alias).strip().lower()
            target_value = str(target).strip()
            if alias_key and target_value:
                aliases[alias_key] = target_value
    return aliases


def _coerce_embedded_kitten_style_embeddings(model: Any) -> bool:
    """Normalize legacy voice embeddings to match ONNX style tensor shape."""
    session = getattr(model, "session", None)
    voices_obj = getattr(model, "voices", None)
    if session is None or voices_obj is None:
        return False

    try:
        style_input = next((inp for inp in session.get_inputs() if inp.name == "style"), None)
    except Exception:
        return False
    if style_input is None:
        return False

    shape = list(getattr(style_input, "shape", []) or [])
    expected_batch = shape[0] if len(shape) >= 1 else None
    expected_width = shape[1] if len(shape) >= 2 else None

    keys: List[str] = []
    if isinstance(voices_obj, dict):
        keys = [str(k) for k in voices_obj.keys()]
    elif hasattr(voices_obj, "files"):
        keys = [str(k) for k in getattr(voices_obj, "files", [])]
    if not keys:
        return False

    patched: Dict[str, Any] = {}
    changed = False
    for key in keys:
        try:
            style_embedding = voices_obj[key]
        except Exception:
            continue

        embedding_shape = tuple(getattr(style_embedding, "shape", ()) or ())
        normalized = style_embedding

        if expected_batch == 1:
            if len(embedding_shape) == 1:
                if expected_width is None or embedding_shape[0] == expected_width:
                    try:
                        normalized = style_embedding.reshape((1, embedding_shape[0]))
                        changed = True
                    except Exception:
                        normalized = style_embedding
            elif len(embedding_shape) >= 2 and embedding_shape[0] != 1:
                if expected_width is None or embedding_shape[-1] == expected_width:
                    normalized = style_embedding[:1]
                    changed = True

        patched[key] = normalized

    if not changed:
        return False

    model.voices = patched
    if hasattr(model, "available_voices"):
        available = [k for k in keys if k in patched]
        if available:
            model.available_voices = available
    print("Normalized embedded KittenTTS voice embeddings for ONNX style input compatibility")
    return True


def _load_embedded_kitten_model_sync(repo_id: str) -> Tuple[Any, Dict[str, str]]:
    if not EMBEDDED_KITTEN_IMPORT_AVAILABLE or EmbeddedKittenTTS is None:
        raise RuntimeError("Embedded Kitten TTS import unavailable.")

    config = _fetch_embedded_kitten_config(repo_id)
    alias_map = _extract_embedded_kitten_voice_aliases(config)

    try:
        model = EmbeddedKittenTTS(repo_id)
        _coerce_embedded_kitten_style_embeddings(model)
        return model, alias_map
    except ValueError as exc:
        if "Unsupported model type" not in str(exc):
            raise
        if not EMBEDDED_KITTEN_FALLBACK_LOADER_AVAILABLE or _hf_hub_download is None or _EmbeddedKittenOnnxModel is None:
            raise RuntimeError(
                f"Model {repo_id} is unsupported by installed kittentts and fallback loader is unavailable."
            ) from exc

        config = config or _fetch_embedded_kitten_config(repo_id)
        model_type = str(config.get("type", "")).strip().upper()
        model_file = str(config.get("model_file", "")).strip()
        voices_file = str(config.get("voices", "")).strip()
        if model_type not in {"ONNX1", "ONNX2"} or not model_file or not voices_file:
            raise RuntimeError(
                f"Model {repo_id} uses unsupported type '{model_type or 'unknown'}'."
            ) from exc

        model_path = _hf_hub_download(repo_id=repo_id, filename=model_file)
        voices_path = _hf_hub_download(repo_id=repo_id, filename=voices_file)
        alias_map = alias_map or _extract_embedded_kitten_voice_aliases(config)
        model = _EmbeddedKittenOnnxModel(model_path=model_path, voices_path=voices_path)
        _coerce_embedded_kitten_style_embeddings(model)
        return model, alias_map


def _resolve_embedded_kitten_voice(
    requested_voice: str,
    available_voices: List[str],
    alias_map: Dict[str, str],
) -> str:
    requested = (requested_voice or "").strip()
    if not requested:
        return available_voices[0] if available_voices else EMBEDDED_KITTEN_DEFAULT_VOICE

    available_lookup = {voice.lower(): voice for voice in available_voices}
    if requested in available_voices:
        return requested
    if requested.lower() in available_lookup:
        return available_lookup[requested.lower()]

    alias_target = alias_map.get(requested.lower()) or EMBEDDED_KITTEN_COMPAT_VOICE_ALIASES.get(requested.lower())
    if alias_target:
        mapped = available_lookup.get(alias_target.lower())
        if mapped:
            return mapped
        if alias_target in available_voices:
            return alias_target

    if available_voices:
        available_preview = ", ".join(available_voices)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported voice '{requested}'. Available voices: {available_preview}",
        )
    return requested


async def _get_embedded_kitten_model(model_name: Optional[str] = None) -> Tuple[Any, Dict[str, str]]:
    global _embedded_kitten_model_instance, _embedded_kitten_model_repo_id, _embedded_kitten_voice_aliases

    if not EMBEDDED_KITTEN_TTS_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Embedded Kitten TTS is disabled. Set EMBEDDED_KITTEN_TTS_ENABLED=true.",
        )

    if not EMBEDDED_KITTEN_IMPORT_AVAILABLE or EmbeddedKittenTTS is None:
        raise HTTPException(
            status_code=503,
            detail="Embedded Kitten TTS is unavailable. Install kitten-tts support dependencies.",
        )

    target_repo_id = _normalize_embedded_kitten_repo_id(model_name)

    async with _embedded_kitten_model_lock:
        if _embedded_kitten_model_instance is None or _embedded_kitten_model_repo_id != target_repo_id:
            try:
                print(f"Loading embedded KittenTTS model: {target_repo_id}")
                model, alias_map = await asyncio.to_thread(_load_embedded_kitten_model_sync, target_repo_id)
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Failed to load embedded Kitten TTS model '{target_repo_id}': {exc}",
                ) from exc

            _embedded_kitten_model_instance = model
            _embedded_kitten_model_repo_id = target_repo_id
            _embedded_kitten_voice_aliases = alias_map
            print("Embedded KittenTTS model loaded")

    return _embedded_kitten_model_instance, _embedded_kitten_voice_aliases


def _split_embedded_kitten_text_chunks(raw_text: str, max_chars: int) -> List[str]:
    collapsed = re.sub(r"\s+", " ", (raw_text or "").strip())
    if not collapsed:
        return []
    if len(collapsed) <= max_chars:
        return [collapsed]

    chunks: List[str] = []
    current = ""

    def append_piece(piece: str) -> None:
        nonlocal current
        piece = piece.strip()
        if not piece:
            return
        if not current:
            current = piece
            return
        candidate = f"{current} {piece}"
        if len(candidate) <= max_chars:
            current = candidate
            return
        chunks.append(current)
        current = piece

    segments = re.split(r"(?<=[.!?])\s+", collapsed)
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        if len(segment) <= max_chars:
            append_piece(segment)
            continue

        words = segment.split(" ")
        word_buffer = ""
        for word in words:
            word = word.strip()
            if not word:
                continue
            candidate = f"{word_buffer} {word}".strip() if word_buffer else word
            if len(candidate) <= max_chars:
                word_buffer = candidate
                continue
            if word_buffer:
                append_piece(word_buffer)
                word_buffer = ""

            if len(word) <= max_chars:
                word_buffer = word
                continue

            for i in range(0, len(word), max_chars):
                token = word[i:i + max_chars].strip()
                if token:
                    append_piece(token)

        if word_buffer:
            append_piece(word_buffer)

    if current:
        chunks.append(current)
    return [chunk for chunk in chunks if chunk]


def _build_embedded_kitten_pcm16_silence_bytes(target_sample_rate: int, milliseconds: int) -> bytes:
    if milliseconds <= 0:
        return b""
    frame_count = max(0, int((target_sample_rate * milliseconds) / 1000))
    if frame_count <= 0:
        return b""
    return b"\x00\x00" * frame_count


async def _iter_embedded_kitten_pcm_chunks(
    text: str,
    voice: str,
    model_name: Optional[str] = None,
    speed: Optional[float] = None,
    sample_rate: Optional[int] = None,
):
    model, alias_map = await _get_embedded_kitten_model(model_name=model_name)
    resolved_voice = _resolve_embedded_kitten_voice(
        requested_voice=voice,
        available_voices=_get_embedded_kitten_available_voices(model),
        alias_map=alias_map,
    )

    chunks = _split_embedded_kitten_text_chunks(text, EMBEDDED_KITTEN_MAX_INPUT_CHARS)
    if not chunks:
        raise HTTPException(status_code=400, detail="Input text is required.")
    if len(chunks) > 1:
        print(
            f"[TTS] Chunking embedded Kitten request into {len(chunks)} segments "
            f"(max {EMBEDDED_KITTEN_MAX_INPUT_CHARS} chars each)"
        )

    target_sample_rate = max(8000, int(sample_rate or EMBEDDED_KITTEN_SAMPLE_RATE))
    inter_chunk_silence = _build_embedded_kitten_pcm16_silence_bytes(
        target_sample_rate, EMBEDDED_KITTEN_CHUNK_SILENCE_MS
    )
    speed_supported = speed is not None

    for index, chunk in enumerate(chunks):
        kwargs: Dict[str, Any] = {"voice": resolved_voice}
        if speed_supported and speed is not None:
            kwargs["speed"] = speed

        try:
            generated = await asyncio.to_thread(model.generate, chunk, **kwargs)
        except TypeError:
            if "speed" in kwargs:
                speed_supported = False
                kwargs.pop("speed", None)
                generated = await asyncio.to_thread(model.generate, chunk, **kwargs)
            else:
                raise
        except ValueError as exc:
            detail = (
                f"Embedded Kitten TTS rejected request on chunk {index + 1}/{len(chunks)}: {exc}"
                if len(chunks) > 1
                else f"Embedded Kitten TTS rejected request: {exc}"
            )
            raise HTTPException(status_code=400, detail=detail) from exc

        chunk_pcm = _float_audio_to_pcm16_bytes(generated)
        if not chunk_pcm:
            raise RuntimeError(f"Embedded Kitten TTS generated empty audio for chunk {index + 1}/{len(chunks)}.")
        yield chunk_pcm
        if inter_chunk_silence and index < len(chunks) - 1:
            yield inter_chunk_silence


async def _generate_embedded_kitten_pcm(
    text: str,
    voice: str,
    model_name: Optional[str] = None,
    speed: Optional[float] = None,
    sample_rate: Optional[int] = None,
) -> bytes:
    pcm_parts: List[bytes] = []
    async for piece in _iter_embedded_kitten_pcm_chunks(
        text=text,
        voice=voice,
        model_name=model_name,
        speed=speed,
        sample_rate=sample_rate,
    ):
        pcm_parts.append(piece)
    pcm_bytes = b"".join(pcm_parts)
    if not pcm_bytes:
        raise RuntimeError("Embedded Kitten TTS generated empty audio.")
    return pcm_bytes

@app.get("/v1/audio/voices")
async def embedded_audio_voices():
    """OpenAI-compatible voices endpoint served directly by proxy_server (embedded KittenTTS)."""
    if not EMBEDDED_KITTEN_TTS_ENABLED:
        raise HTTPException(status_code=404, detail="Embedded Kitten TTS endpoint is disabled.")
    voices = EMBEDDED_KITTEN_VOICES or [EMBEDDED_KITTEN_DEFAULT_VOICE]
    return JSONResponse(
        content={
            "object": "list",
            "data": [
                {"id": voice_id, "object": "voice", "name": voice_id}
                for voice_id in voices
            ],
        },
        status_code=200,
    )


@app.post("/v1/audio/speech")
async def embedded_audio_speech(payload: EmbeddedTtsSpeechRequest):
    """OpenAI-compatible TTS speech endpoint served directly by proxy_server (embedded KittenTTS)."""
    if not EMBEDDED_KITTEN_TTS_ENABLED:
        raise HTTPException(status_code=404, detail="Embedded Kitten TTS endpoint is disabled.")

    text = (payload.input or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Input text is required.")

    requested_model = (payload.model or EMBEDDED_KITTEN_MODEL or "").strip() or EMBEDDED_KITTEN_MODEL
    requested_voice = (payload.voice or EMBEDDED_KITTEN_DEFAULT_VOICE or "").strip() or EMBEDDED_KITTEN_DEFAULT_VOICE
    sample_rate = max(8000, int(payload.sample_rate or EMBEDDED_KITTEN_SAMPLE_RATE))
    channels = max(1, int(payload.channels or 1))
    response_format = (payload.response_format or "wav").strip().lower()
    stream_mode = bool(payload.stream)

    headers = {
        "X-Audio-Sample-Rate": str(sample_rate),
        "X-Audio-Channels": str(channels),
        "Cache-Control": "no-store",
    }

    if response_format in {"pcm", "l16", "s16le"}:
        media_type = "audio/pcm"
        if stream_mode:
            async def pcm_stream():
                async for generated_chunk in _iter_embedded_kitten_pcm_chunks(
                    text=text,
                    voice=requested_voice,
                    model_name=requested_model,
                    speed=payload.speed,
                    sample_rate=sample_rate,
                ):
                    for i in range(0, len(generated_chunk), EMBEDDED_KITTEN_STREAM_CHUNK_BYTES):
                        yield generated_chunk[i:i + EMBEDDED_KITTEN_STREAM_CHUNK_BYTES]
                        await asyncio.sleep(0)

            return StreamingResponse(pcm_stream(), media_type=media_type, headers=headers)
        pcm_bytes = await _generate_embedded_kitten_pcm(
            text=text,
            voice=requested_voice,
            model_name=requested_model,
            speed=payload.speed,
            sample_rate=sample_rate,
        )
        return Response(content=pcm_bytes, media_type=media_type, headers=headers, status_code=200)

    pcm_bytes = await _generate_embedded_kitten_pcm(
        text=text,
        voice=requested_voice,
        model_name=requested_model,
        speed=payload.speed,
        sample_rate=sample_rate,
    )
    wav_bytes = _build_wav_header(sample_rate=sample_rate, channels=channels, bits_per_sample=16, pcm_bytes_len=len(pcm_bytes)) + pcm_bytes
    if stream_mode:
        async def wav_stream():
            yield wav_bytes[:44]
            await asyncio.sleep(0)
            payload_bytes = wav_bytes[44:]
            for i in range(0, len(payload_bytes), EMBEDDED_KITTEN_STREAM_CHUNK_BYTES):
                yield payload_bytes[i:i + EMBEDDED_KITTEN_STREAM_CHUNK_BYTES]
                await asyncio.sleep(0)

        return StreamingResponse(wav_stream(), media_type="audio/wav", headers=headers)
    return Response(content=wav_bytes, media_type="audio/wav", headers=headers, status_code=200)

# TTS voices proxy endpoint to handle CORS
def _should_skip_tts_tls_verify(base_url: str) -> bool:
    """Return True for local HTTPS TTS endpoints where self-signed certs are common."""
    try:
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https":
            return False
        if host in {"localhost", "127.0.0.1", "::1"}:
            return True
        return host.endswith(".local")
    except Exception:
        return False


@app.get("/v1/proxy/tts/voices")
async def proxy_tts_voices(endpoint: str):
    """Proxy TTS voices requests to handle CORS. Tries /voices first, then /v1/audio/voices."""
    if not endpoint:
        raise HTTPException(status_code=400, detail="Endpoint parameter is required")
    
    try:
        # Normalize the endpoint URL (remove trailing slash)
        base_endpoint = endpoint.rstrip('/')
        
        # Extract base URL (origin: protocol + host + port) to avoid path duplication
        try:
            # Parse the endpoint URL to extract the origin (protocol + host + port)
            if not base_endpoint.startswith('http://') and not base_endpoint.startswith('https://'):
                # If no protocol, assume http://
                base_endpoint = f"http://{base_endpoint}"
            
            parsed_url = urlparse(base_endpoint)
            # Reconstruct base URL with scheme, hostname, and port (if present)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        except Exception as e:
            # Fallback to simple string replacement if URL parsing fails
            # Extract origin manually using regex
            match = re.match(r'^(https?://[^/]+)', base_endpoint)
            if match:
                base_url = match.group(1)
            else:
                # Last resort: remove /v1 and any path
                base_url = base_endpoint.split('/')[0] if '/' in base_endpoint else base_endpoint
                if not base_url.startswith('http'):
                    base_url = f"http://{base_url}"
        
        skip_tls_verify = _should_skip_tts_tls_verify(base_url)
        if skip_tls_verify:
            print(f"[WARN] TTS voices proxy: TLS verification disabled for local endpoint: {base_url}")

        # Try /voices first (Chatterbox style)
        voices_url_primary = f"{base_url}/voices"
        print(f"🎤 Trying primary TTS voices endpoint: {voices_url_primary}")
        
        response = None
        response_data = None
        
        async with httpx.AsyncClient(timeout=10.0, verify=(not skip_tls_verify)) as client:
            try:
                # Try the primary endpoint first
                response = await client.get(
                    voices_url_primary,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                )
                
                print(f"✅ Primary TTS voices response status: {response.status_code}")
                
                # If primary endpoint succeeds, use it
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        print(f"✅ Parsed TTS voices JSON response from primary endpoint")
                        return JSONResponse(content=response_data, status_code=200)
                    except Exception as json_error:
                        print(f"âŒ Failed to parse JSON response: {json_error}")
                        print(f"   Raw response text: {response.text[:200]}")
                        # Return the raw text if JSON parsing fails
                        return JSONResponse(
                            content={"text": response.text},
                            status_code=200
                        )
            except (httpx.ConnectError, httpx.HTTPStatusError) as e:
                # Primary endpoint failed, try fallback
                print(f"âš ï¸ Primary endpoint failed: {e}")
                response = None
            
            # If primary failed, try /v1/audio/voices (OpenAI-compatible style)
            if not response or response.status_code != 200:
                voices_url_fallback = f"{base_url}/v1/audio/voices"
                print(f"🎤 Trying fallback TTS voices endpoint: {voices_url_fallback}")
                
                try:
                    response = await client.get(
                        voices_url_fallback,
                        headers={
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        }
                    )
                    
                    print(f"✅ Fallback TTS voices response status: {response.status_code}")
                    
                    # Check if the fallback response is successful
                    if response.status_code == 200:
                        try:
                            response_data = response.json()
                            print(f"✅ Parsed TTS voices JSON response from fallback endpoint")
                            return JSONResponse(content=response_data, status_code=200)
                        except Exception as json_error:
                            print(f"âŒ Failed to parse JSON response: {json_error}")
                            print(f"   Raw response text: {response.text[:200]}")
                            # Return the raw text if JSON parsing fails
                            return JSONResponse(
                                content={"text": response.text},
                                status_code=200
                            )
                    else:
                        # Fallback also failed
                        print(f"âŒ Fallback TTS service returned error: {response.status_code}")
                        print(f"   Response text: {response.text[:200]}")
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"TTS service error: {response.text[:200]}"
                        )
                except httpx.ConnectError as e:
                    print(f"âŒ Connection error: Could not connect to TTS service at {voices_url_fallback}")
                    raise HTTPException(
                        status_code=503,
                        detail=f"Could not connect to TTS service. Tried {voices_url_primary} and {voices_url_fallback}"
                    )
                except httpx.HTTPStatusError as e:
                    print(f"âŒ HTTP error from fallback TTS service: {e.response.status_code}")
                    raise HTTPException(
                        status_code=e.response.status_code,
                        detail=f"TTS service returned error: {str(e)}"
                    )
        
        # If we get here, both attempts failed
        if response and response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"TTS service error: {response.text[:200]}"
            )
        else:
            raise HTTPException(
                status_code=503,
                detail=f"Could not connect to TTS service. Tried {voices_url_primary} and {base_url}/v1/audio/voices"
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except httpx.ConnectError as e:
        print(f"âŒ Connection error: Could not connect to TTS service at {endpoint}")
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to TTS service at {endpoint}"
        )
    except httpx.HTTPStatusError as e:
        print(f"âŒ HTTP error from TTS service: {e.response.status_code}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"TTS service returned error: {str(e)}"
        )
    except Exception as e:
        print(f"âŒ TTS voices proxy error: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to proxy TTS voices request: {str(e)}")

# TTS speech proxy endpoint to handle CORS and streaming
@app.post("/v1/proxy/tts/speech")
async def proxy_tts_speech(request: Request, endpoint: Optional[str] = None):
    """Proxy TTS speech requests to handle CORS. Supports streaming responses."""
    try:
        buffer_response = request.query_params.get("buffer", "").lower() in {"1", "true", "yes", "on"}
        # Get endpoint from query parameter or try to extract from request
        if not endpoint:
            # Try to get from query params
            endpoint = request.query_params.get('endpoint', '')
        
        # If still no endpoint, try to get from TTS_ENDPOINT env var or use default
        if not endpoint:
            tts_endpoint = os.getenv('TTS_ENDPOINT', 'http://localhost:4123/v1')
            endpoint = tts_endpoint.rstrip('/')
        
        # Normalize the endpoint URL (remove trailing slash)
        base_endpoint = endpoint.rstrip('/')
        
        # Extract base URL (origin: protocol + host + port) to avoid path duplication
        try:
            # Parse the endpoint URL to extract the origin (protocol + host + port)
            if not base_endpoint.startswith('http://') and not base_endpoint.startswith('https://'):
                # If no protocol, assume http://
                base_endpoint = f"http://{base_endpoint}"
            
            parsed_url = urlparse(base_endpoint)
            # Reconstruct base URL with scheme, hostname, and port (if present)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        except Exception as e:
            # Fallback to simple string replacement if URL parsing fails
            # Extract origin manually using regex
            match = re.match(r'^(https?://[^/]+)', base_endpoint)
            if match:
                base_url = match.group(1)
            else:
                # Last resort: remove /v1 and any path
                base_url = base_endpoint.split('/')[0] if '/' in base_endpoint else base_endpoint
                if not base_url.startswith('http'):
                    base_url = f"http://{base_url}"
        
        # Construct the speech endpoint URL
        speech_url = f"{base_url}/v1/audio/speech"
        
        print(f"🎤 Proxying TTS speech request to: {speech_url}")
        
        # Get the request body
        try:
            request_body = await request.json()
        except Exception:
            request_body = {}
        
        # Get headers from the original request
        # Forward Accept header to support both SSE (Chatterbox) and binary audio (VibeVoice/OpenAI-compatible)
        # If client requests SSE, forward it; otherwise let TTS service decide (defaults to binary audio)
        accept_header = request.headers.get('Accept', '')
        forward_headers = {
            'Content-Type': 'application/json',
        }
        
        # Forward Accept header if present (allows Chatterbox to return SSE, VibeVoice will ignore and return binary)
        if accept_header:
            forward_headers['Accept'] = accept_header
        
        # Forward Authorization header if present
        auth_header = request.headers.get('Authorization')
        if auth_header:
            forward_headers['Authorization'] = auth_header

        skip_tls_verify = _should_skip_tts_tls_verify(base_url)
        if skip_tls_verify:
            print(f"[WARN] TTS speech proxy: TLS verification disabled for local endpoint: {base_url}")

        if buffer_response:
            async with httpx.AsyncClient(timeout=TTS_PROXY_TIMEOUT_SECONDS, verify=(not skip_tls_verify)) as client:
                response = await client.post(
                    speech_url,
                    json=request_body,
                    headers=forward_headers,
                )
            content_type = response.headers.get('content-type', 'audio/mpeg')
            # Safari/iOS can fail to decode blobs labeled as audio/mp3; normalize to audio/mpeg.
            if isinstance(content_type, str) and content_type.lower().startswith('audio/mp3'):
                content_type = 'audio/mpeg'
            if response.status_code != 200:
                print(f"âŒ TTS service returned error (buffered): {response.status_code}")
                return Response(
                    content=response.content,
                    media_type=content_type,
                    status_code=response.status_code,
                )
            return Response(
                content=response.content,
                media_type=content_type,
                status_code=200,
            )
        
        # Open upstream stream first so we can forward the *actual* content-type.
        # This avoids mislabeling MP3 as SSE, which breaks browser playback/parsing.
        client = httpx.AsyncClient(timeout=TTS_PROXY_TIMEOUT_SECONDS, verify=(not skip_tls_verify))
        try:
            upstream_response = await client.send(
                client.build_request(
                    "POST",
                    speech_url,
                    json=request_body,
                    headers=forward_headers,
                ),
                stream=True,
            )
        except Exception:
            await client.aclose()
            raise

        print(f"✅ TTS speech response status: {upstream_response.status_code}")
        print(f"📤 TTS request body: {json.dumps(request_body, indent=2)[:500]}")
        print(f"📤 TTS request headers: {forward_headers}")
        upstream_content_type = upstream_response.headers.get("content-type", "audio/mpeg")
        # Normalize non-standard MP3 MIME type for better iOS Safari compatibility.
        if isinstance(upstream_content_type, str) and upstream_content_type.lower().startswith("audio/mp3"):
            upstream_content_type = "audio/mpeg"
        print(f"📦 TTS response content-type: {upstream_content_type}")

        if upstream_response.status_code != 200:
            error_body = await upstream_response.aread()
            print(f"âŒ TTS service returned error: {upstream_response.status_code}")
            print(f"   Response text: {error_body[:200]}")
            await upstream_response.aclose()
            await client.aclose()
            return Response(
                content=error_body,
                status_code=upstream_response.status_code,
                headers={"Content-Type": upstream_content_type},
            )

        async def stream_upstream():
            try:
                async for chunk in upstream_response.aiter_bytes():
                    if chunk:
                        yield chunk
            finally:
                await upstream_response.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_upstream(),
            status_code=200,
            headers={"Content-Type": upstream_content_type},
        )
    
    except Exception as e:
        print(f"âŒ TTS speech proxy error: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to proxy TTS speech request: {str(e)}")

# ============================================================================
# FILE OPERATIONS ENDPOINTS
# ============================================================================

def resolve_scratch_path(filename: str, allowed_extensions: Optional[Set[str]] = None) -> Path:
    """
    Resolve a user-supplied filename to a path under SCRATCH_DIR.
    Rejects absolute paths, traversal (..), and disallowed extensions.
    Returns the canonical path for safe I/O. Raises HTTPException 400 on invalid input.
    """
    # Reject empty or whitespace-only filename
    if not filename or not filename.strip():
        raise HTTPException(status_code=400, detail="Invalid filename")
    # Reject absolute paths (Unix / or Windows drive/root)
    if os.path.isabs(filename) or filename.startswith("/") or filename.startswith("\\"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    # Reject path traversal components
    parts = Path(filename).parts
    if ".." in parts:
        raise HTTPException(status_code=400, detail="Invalid filename")
    # Build candidate path and resolve to canonical form
    candidate = SCRATCH_DIR / filename
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail="Invalid filename") from e
    # Enforce containment under SCRATCH_DIR (Python 3.9+ relative_to)
    root = SCRATCH_DIR.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    # Optional: enforce extension allowlist
    if allowed_extensions is not None:
        suffix = resolved.suffix.lower()
        if suffix not in allowed_extensions:
            raise HTTPException(status_code=400, detail="Invalid filename")
    return resolved


def read_text_file(filepath: Path) -> str:
    """Read a plain text file and return its content"""
    try:
        # Read the file with UTF-8 encoding
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # Fallback to latin-1 if UTF-8 fails
        with open(filepath, 'r', encoding='latin-1') as f:
            return f.read()

def read_docx_file(filepath: Path) -> str:
    """Read a Word document and return its text content"""
    # Load the document using python-docx
    doc = Document(filepath)
    # Extract text from all paragraphs
    paragraphs = [para.text for para in doc.paragraphs]
    # Join paragraphs with newlines
    return '\n'.join(paragraphs)

def read_xlsx_file(filepath: Path) -> str:
    """Read an Excel file and return its content as formatted text"""
    # Load the workbook
    wb = openpyxl.load_workbook(filepath, data_only=True)
    result = []
    
    # Process each sheet in the workbook
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        result.append(f"=== Sheet: {sheet_name} ===\n")
        
        # Process each row in the sheet
        for row in sheet.iter_rows(values_only=True):
            # Filter out None values and convert to strings
            row_data = [str(cell) if cell is not None else '' for cell in row]
            # Join cells with tabs for better formatting
            result.append('\t'.join(row_data))
        
        result.append('\n')  # Add blank line between sheets
    
    # Join all lines with newlines
    return '\n'.join(result)

def read_pdf_file(filepath: Path) -> str:
    """Read a PDF file and return its text content"""
    result = []
    # Open the PDF file in binary mode
    with open(filepath, 'rb') as f:
        # Create a PDF reader object
        pdf_reader = PyPDF2.PdfReader(f)
        # Extract text from each page
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            result.append(f"=== Page {page_num + 1} ===\n{text}\n")
    
    # Join all pages with newlines
    return '\n'.join(result)

def read_png_file(filepath: Path) -> Dict[str, Any]:
    """Read a PNG image and return metadata and base64-encoded data"""
    # Open the image using PIL
    img = Image.open(filepath)
    
    # Get image metadata
    metadata = {
        'width': img.width,
        'height': img.height,
        'format': img.format,
        'mode': img.mode
    }
    
    # Convert image to base64 for transmission
    buffered = BytesIO()
    img.save(buffered, format=img.format)
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    return {
        'metadata': metadata,
        'data': img_base64,
        'description': f"Image: {img.width}x{img.height} pixels, format: {img.format}"
    }

def write_text_file(filepath: Path, content: str) -> None:
    """Write content to a plain text file"""
    # Write the content with UTF-8 encoding
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def write_docx_file(filepath: Path, content: str) -> None:
    """Write content to a Word document"""
    # Create a new document
    doc = Document()
    
    # Split content into paragraphs and add each to the document
    for paragraph in content.split('\n'):
        doc.add_paragraph(paragraph)
    
    # Save the document
    doc.save(filepath)

def write_xlsx_file(filepath: Path, content: str) -> None:
    """Write content to an Excel file"""
    # Create a new workbook
    wb = openpyxl.Workbook()
    # Get the active sheet
    ws = wb.active
    ws.title = "Sheet1"
    
    # Split content into rows
    rows = content.split('\n')
    
    # Write each row to the Excel file
    for row_idx, row_content in enumerate(rows, start=1):
        # Split row by tabs or commas
        if '\t' in row_content:
            cells = row_content.split('\t')
        else:
            cells = row_content.split(',')
        
        # Write each cell
        for col_idx, cell_content in enumerate(cells, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=cell_content.strip())
            
            # Apply formatting to the first row (header)
            if row_idx == 1:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center')
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Save the workbook
    wb.save(filepath)

def write_pdf_file(filepath: Path, content: str) -> None:
    """Write content to a PDF file using reportlab"""
    try:
        # Import reportlab for PDF creation
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas as pdf_canvas
        from reportlab.lib.units import inch
        
        # Create a canvas for PDF generation
        c = pdf_canvas.Canvas(str(filepath), pagesize=letter)
        width, height = letter
        
        # Set up text formatting
        text_object = c.beginText(1 * inch, height - 1 * inch)
        text_object.setFont("Helvetica", 12)
        
        # Split content into lines and add to PDF
        lines = content.split('\n')
        for line in lines:
            # Handle long lines by wrapping
            if len(line) > 80:
                words = line.split(' ')
                current_line = ''
                for word in words:
                    if len(current_line + word) < 80:
                        current_line += word + ' '
                    else:
                        text_object.textLine(current_line)
                        current_line = word + ' '
                if current_line:
                    text_object.textLine(current_line)
            else:
                text_object.textLine(line)
            
            # Add new page if needed (simple check)
            if text_object.getY() < 1 * inch:
                c.drawText(text_object)
                c.showPage()
                text_object = c.beginText(1 * inch, height - 1 * inch)
                text_object.setFont("Helvetica", 12)
        
        # Draw the text and save the PDF
        c.drawText(text_object)
        c.save()
        
    except ImportError:
        # If reportlab is not available, raise an error
        raise HTTPException(
            status_code=500,
            detail="PDF writing requires reportlab library. Install with: pip install reportlab"
        )


# Internal file ops for Telegram tool runner (no auth; same security as routes)
async def _read_file_internal(filename: str) -> Dict[str, Any]:
    """Read file from scratch dir. Returns dict with success, message, data (content/type). Used by Telegram tools only."""
    if not FILE_OPS_AVAILABLE:
        return {"success": False, "message": "File operations not available."}
    try:
        filepath = resolve_scratch_path(filename, READ_ALLOWED_EXTENSIONS)
        if not filepath.exists():
            return {"success": False, "message": f"File not found: {filename}"}
        if filepath.stat().st_size > FILE_OPS_MAX_SIZE_BYTES:
            return {"success": False, "message": "File too large"}
        ext = filepath.suffix.lower()
        if ext in ['.txt', '.md']:
            content = read_text_file(filepath)
            return {"success": True, "message": f"Read {filename}", "data": {"content": content, "type": "text"}}
        if ext == '.docx':
            content = read_docx_file(filepath)
            return {"success": True, "message": f"Read {filename}", "data": {"content": content, "type": "text"}}
        if ext in ['.xlsx', '.xls']:
            content = read_xlsx_file(filepath)
            return {"success": True, "message": f"Read {filename}", "data": {"content": content, "type": "text"}}
        if ext == '.pdf':
            content = read_pdf_file(filepath)
            return {"success": True, "message": f"Read {filename}", "data": {"content": content, "type": "text"}}
        if ext in ['.png', '.jpg', '.jpeg']:
            image_data = read_png_file(filepath)
            return {"success": True, "message": f"Read {filename}", "data": {"content": image_data.get("description", ""), "type": "image", "image_data": image_data}}
        return {"success": False, "message": f"Unsupported file type: {ext}"}
    except HTTPException as e:
        return {"success": False, "message": e.detail or "Invalid filename"}
    except Exception as e:
        return {"success": False, "message": str(e)}


async def _write_file_internal(filename: str, content: str, format: str = "txt") -> Dict[str, Any]:
    """Write file to scratch dir. Returns dict with success, message. Used by Telegram tools only."""
    if not FILE_OPS_AVAILABLE:
        return {"success": False, "message": "File operations not available."}
    try:
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > FILE_OPS_MAX_SIZE_BYTES:
            return {"success": False, "message": "Content too large"}
        logical_name = filename.strip()
        if not Path(logical_name).suffix:
            logical_name = f"{logical_name}.{format.lower()}"
        filepath = resolve_scratch_path(logical_name, WRITE_ALLOWED_EXTENSIONS)
        ext = filepath.suffix.lower()
        if ext in ['.txt', '.md']:
            write_text_file(filepath, content)
        elif ext == '.docx':
            write_docx_file(filepath, content)
        elif ext in ['.xlsx', '.xls']:
            write_xlsx_file(filepath, content)
        elif ext == '.pdf':
            write_pdf_file(filepath, content)
        else:
            return {"success": False, "message": f"Unsupported file type for writing: {ext}"}
        return {"success": True, "message": f"Wrote {filepath.name}", "data": {"filepath": str(filepath), "size": filepath.stat().st_size}}
    except HTTPException as e:
        return {"success": False, "message": e.detail or "Invalid filename"}
    except Exception as e:
        return {"success": False, "message": str(e)}


async def _list_files_internal() -> Dict[str, Any]:
    """List files in scratch dir. Returns dict with success, files. Used by Telegram tools only."""
    try:
        files = []
        for file in SCRATCH_DIR.iterdir():
            if file.is_file():
                files.append({
                    'name': file.name,
                    'size': file.stat().st_size,
                    'modified': file.stat().st_mtime,
                    'extension': file.suffix
                })
        files.sort(key=lambda x: x['modified'], reverse=True)
        return {"success": True, "files": files, "count": len(files), "scratch_dir": str(SCRATCH_DIR)}
    except Exception as e:
        return {"success": False, "message": str(e), "files": []}


def _get_list_files_tool_max_entries() -> int:
    """Return max entries rendered in list-files tool replies."""
    raw = (os.getenv("LIST_FILES_TOOL_MAX_ENTRIES", "60") or "60").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 60
    return max(1, parsed)


def _format_list_files_for_tool_output(files: List[Dict[str, Any]], include_sizes: bool = False) -> str:
    """Format scratch files for LLM-facing tool output with a bounded number of rows."""
    if not files:
        return "Scratch workspace is empty."
    limit = _get_list_files_tool_max_entries()
    shown = files[:limit]
    if include_sizes:
        lines = [f"{f.get('name', '?')} ({f.get('size', 0)} bytes)" for f in shown]
    else:
        lines = [f.get("name", "?") for f in shown]
    remaining = max(0, len(files) - len(shown))
    header = "Files in scratch workspace:"
    if remaining > 0:
        header += f" (showing {len(shown)} of {len(files)})"
        lines.append(f"... and {remaining} more files.")
    return header + "\n" + "\n".join(lines)


async def _delete_file_internal(filename: str) -> Dict[str, Any]:
    """Delete file from scratch dir. Returns dict with success, message. Used by philosopher and other server-side callers."""
    if not FILE_OPS_AVAILABLE:
        return {"success": False, "message": "File operations not available."}
    try:
        filepath = resolve_scratch_path(filename, READ_ALLOWED_EXTENSIONS)
        if not filepath.exists():
            return {"success": False, "message": f"File not found: {filename}"}
        filepath.unlink()
        return {"success": True, "message": f"Deleted {filename}"}
    except HTTPException as e:
        return {"success": False, "message": e.detail or "Invalid filename"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/v1/files/read", response_model=FileResponse)
async def read_file(
    request: ReadFileRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Read a file from the scratch directory
    Supports: txt, md, docx, xlsx, pdf, png
    """
    if not FILE_OPS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="File operations not available. Install: pip install python-docx openpyxl PyPDF2 reportlab Pillow"
        )
    # Resolve path with containment and extension checks (blocks path traversal)
    filepath = resolve_scratch_path(request.filename, READ_ALLOWED_EXTENSIONS)
    try:
        # Check if file exists
        if not filepath.exists():
            return FileResponse(
                success=False,
                message=f"File not found: {request.filename}"
            )
        # Enforce max file size before reading
        if filepath.stat().st_size > FILE_OPS_MAX_SIZE_BYTES:
            return FileResponse(
                success=False,
                message="File too large"
            )
        # Determine file extension
        file_ext = filepath.suffix.lower()
        # Read file based on extension
        if file_ext in ['.txt', '.md']:
            content = read_text_file(filepath)
            return FileResponse(
                success=True,
                message=f"Successfully read {request.filename}",
                data={'content': content, 'type': 'text'}
            )
        
        elif file_ext == '.docx':
            content = read_docx_file(filepath)
            return FileResponse(
                success=True,
                message=f"Successfully read {request.filename}",
                data={'content': content, 'type': 'text'}
            )
        
        elif file_ext in ['.xlsx', '.xls']:
            content = read_xlsx_file(filepath)
            return FileResponse(
                success=True,
                message=f"Successfully read {request.filename}",
                data={'content': content, 'type': 'text'}
            )
        
        elif file_ext == '.pdf':
            content = read_pdf_file(filepath)
            return FileResponse(
                success=True,
                message=f"Successfully read {request.filename}",
                data={'content': content, 'type': 'text'}
            )
        
        elif file_ext in ['.png', '.jpg', '.jpeg']:
            image_data = read_png_file(filepath)
            return FileResponse(
                success=True,
                message=f"Successfully read {request.filename}",
                data={'content': image_data['description'], 'type': 'image', 'image_data': image_data}
            )
        
        else:
            # Unsupported file type
            return FileResponse(
                success=False,
                message=f"Unsupported file type: {file_ext}. Supported types: txt, md, docx, xlsx, pdf, png"
            )
    
    except Exception as e:
        # Handle any errors during file reading
        return FileResponse(
            success=False,
            message=f"Error reading file: {str(e)}"
        )

@app.post("/v1/files/write", response_model=FileResponse)
async def write_file(
    request: WriteFileRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Write content to a file in the scratch directory
    Supports: txt, md, docx, xlsx, pdf
    """
    if not FILE_OPS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="File operations not available. Install: pip install python-docx openpyxl PyPDF2 reportlab Pillow"
        )
    # Enforce max content size before processing
    content_bytes = request.content.encode("utf-8")
    if len(content_bytes) > FILE_OPS_MAX_SIZE_BYTES:
        return FileResponse(success=False, message="Content too large")
    # Build logical filename with extension from format if missing
    logical_name = request.filename.strip()
    if not Path(logical_name).suffix:
        logical_name = f"{logical_name}.{request.format.lower()}"
    # Resolve path with containment and extension checks (blocks path traversal)
    filepath = resolve_scratch_path(logical_name, WRITE_ALLOWED_EXTENSIONS)
    file_ext = filepath.suffix.lower()
    try:
        # Write file based on extension
        if file_ext in ['.txt', '.md']:
            write_text_file(filepath, request.content)
        
        elif file_ext == '.docx':
            write_docx_file(filepath, request.content)
        
        elif file_ext in ['.xlsx', '.xls']:
            write_xlsx_file(filepath, request.content)
        
        elif file_ext == '.pdf':
            write_pdf_file(filepath, request.content)
        
        else:
            # Unsupported file type
            return FileResponse(
                success=False,
                message=f"Unsupported file type for writing: {file_ext}. Supported types: txt, md, docx, xlsx, pdf"
            )
        
        # Return success response
        return FileResponse(
            success=True,
            message=f"Successfully wrote {filepath.name}",
            data={'filepath': str(filepath), 'size': filepath.stat().st_size}
        )
    
    except Exception as e:
        # Handle any errors during file writing
        return FileResponse(
            success=False,
            message=f"Error writing file: {str(e)}"
        )

@app.get("/v1/files/list")
async def list_files(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List all files in the scratch directory"""
    try:
        # Get all files in scratch directory
        files = []
        for file in SCRATCH_DIR.iterdir():
            if file.is_file():
                files.append({
                    'name': file.name,
                    'size': file.stat().st_size,
                    'modified': file.stat().st_mtime,
                    'extension': file.suffix
                })
        
        # Sort files by modification time (newest first)
        files.sort(key=lambda x: x['modified'], reverse=True)
        
        return {
            'success': True,
            'count': len(files),
            'files': files,
            'scratch_dir': str(SCRATCH_DIR)
        }
    
    except Exception as e:
        # Handle any errors during directory listing
        return {
            'success': False,
            'message': f"Error listing files: {str(e)}"
        }

@app.delete("/v1/files/delete/{filename}")
async def delete_file(
    filename: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a file from the scratch directory"""
    # Resolve path with containment and extension checks (blocks path traversal)
    filepath = resolve_scratch_path(filename, READ_ALLOWED_EXTENSIONS)
    try:
        # Check if file exists
        if not filepath.exists():
            return FileResponse(
                success=False,
                message=f"File not found: {filename}"
            )
        
        # Delete the file
        filepath.unlink()
        
        return FileResponse(
            success=True,
            message=f"Successfully deleted {filename}"
        )
    
    except Exception as e:
        # Handle any errors during file deletion
        return FileResponse(
            success=False,
            message=f"Error deleting file: {str(e)}"
        )


# ============================================================================
# COMPANIONS API (CATBot tool settings saved as static config files)
# ============================================================================

# Safe filename: only alphanumeric, hyphen, underscore (no path traversal, .json only)
_COMPANION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def resolve_companion_path(companion_id: str) -> Path:
    """
    Resolve a companion id to a path under COMPANIONS_DIR.
    Only allows safe ids (alphanumeric, hyphen, underscore); enforces .json.
    Raises HTTPException 400 on invalid input.
    """
    if not companion_id or not companion_id.strip():
        raise HTTPException(status_code=400, detail="Invalid companion id")
    if not _COMPANION_ID_RE.match(companion_id):
        raise HTTPException(status_code=400, detail="Invalid companion id: only letters, numbers, hyphen, underscore allowed")
    # Build path: COMPANIONS_DIR / {id}.json
    candidate = COMPANIONS_DIR / f"{companion_id}.json"
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail="Invalid companion id") from e
    # Enforce containment under COMPANIONS_DIR
    root = COMPANIONS_DIR.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid companion id")
    if resolved.suffix.lower() != ".json":
        raise HTTPException(status_code=400, detail="Invalid companion id")
    return resolved


@app.get("/v1/companions", response_model=List[CompanionResponse])
async def list_companions(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List all saved companions (id and name only for list view)."""
    try:
        result = []
        for path in COMPANIONS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                cid = data.get("id") or path.stem
                name = data.get("name") or path.stem
                result.append(CompanionResponse(id=cid, name=name, settings=None))
            except (json.JSONDecodeError, OSError):
                continue
        result.sort(key=lambda c: c.name.lower())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/companions/{companion_id}", response_model=CompanionResponse)
async def get_companion(
    companion_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Get one companion by id (full record including settings)."""
    filepath = resolve_companion_path(companion_id)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Companion not found")
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return CompanionResponse(
            id=data.get("id", companion_id),
            name=data.get("name", companion_id),
            settings=data.get("settings"),
        )
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/companions", response_model=CompanionResponse)
async def create_companion(
    request: CompanionCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create a new companion; server generates id (UUID), writes config/companions/{id}.json."""
    import uuid
    name = (request.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Companion name is required")
    # Generate a URL-safe id (use uuid4 hex for simplicity and uniqueness)
    cid = uuid.uuid4().hex
    filepath = resolve_companion_path(cid)
    record = {"id": cid, "name": name, "settings": request.settings or {}}
    try:
        filepath.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return CompanionResponse(id=cid, name=name, settings=record["settings"])
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/companions/{companion_id}")
async def delete_companion(
    companion_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Delete a companion by id."""
    filepath = resolve_companion_path(companion_id)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Companion not found")
    try:
        filepath.unlink()
        return {"success": True, "message": f"Companion {companion_id} deleted"}
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# END COMPANIONS API
# ============================================================================

# ============================================================================
# MODEL AVATAR SCAN (discover *.model3.json and *.vrm under model_avatar/)
# ============================================================================

def scan_model_avatar_dir() -> Dict[str, Any]:
    """
    Recursively scan model_avatar directory for Live2D (.model3.json) and VRM (.vrm) files.
    Returns paths relative to project root with ./ prefix and forward slashes for UI consistency.
    """
    model_avatar_dir = _PROJECT_ROOT / "model_avatar"
    result = {"live2d": [], "vrm": []}
    if not model_avatar_dir.is_dir():
        result["message"] = "model_avatar directory not found"
        return result
    try:
        # Collect Live2D model paths (one per file, any depth)
        for p in model_avatar_dir.rglob("*.model3.json"):
            if p.is_file():
                rel = p.relative_to(_PROJECT_ROOT)
                path_str = "./" + str(rel).replace("\\", "/")
                result["live2d"].append(path_str)
        result["live2d"].sort()
        # Collect VRM model paths (one per file, any depth)
        for p in model_avatar_dir.rglob("*.vrm"):
            if p.is_file():
                rel = p.relative_to(_PROJECT_ROOT)
                path_str = "./" + str(rel).replace("\\", "/")
                result["vrm"].append(path_str)
        result["vrm"].sort()
    except Exception as e:
        result["message"] = str(e)
    return result


@app.get("/v1/model-avatar/scan")
async def model_avatar_scan(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return lists of discovered Live2D and VRM model paths under model_avatar/ for tools settings."""
    return scan_model_avatar_dir()


# ============================================================================
# GOOGLE DRIVE UPLOAD ENDPOINT
# ============================================================================

# Internal drive upload for Telegram tool runner (no auth; same path/credential checks)
async def _upload_drive_internal(file_path: str, file_name: Optional[str] = None) -> Dict[str, Any]:
    """Upload a file from scratch dir to Google Drive. Returns dict with success, message, fileId, etc. Used by Telegram tools only."""
    try:
        if not file_path or not str(file_path).strip():
            return {"success": False, "message": "filePath is required"}
        file_path_obj = resolve_scratch_path(str(file_path).strip(), DRIVE_UPLOAD_EXTENSIONS)
        if not file_path_obj.exists():
            return {"success": False, "message": f"File not found: {file_path}"}
        folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        if not folder_id:
            return {"success": False, "message": "GOOGLE_DRIVE_FOLDER_ID is not set"}
        project_id = os.getenv('GOOGLE_DRIVE_PROJECT_ID')
        private_key_id = os.getenv('GOOGLE_DRIVE_PRIVATE_KEY_ID')
        private_key = os.getenv('GOOGLE_DRIVE_PRIVATE_KEY')
        client_email = os.getenv('GOOGLE_DRIVE_CLIENT_EMAIL')
        if not all([project_id, private_key_id, private_key, client_email]):
            missing = [k for k, v in {
                'GOOGLE_DRIVE_PROJECT_ID': project_id,
                'GOOGLE_DRIVE_PRIVATE_KEY_ID': private_key_id,
                'GOOGLE_DRIVE_PRIVATE_KEY': private_key,
                'GOOGLE_DRIVE_CLIENT_EMAIL': client_email
            }.items() if not v]
            return {"success": False, "message": f"Missing Google Drive credentials: {', '.join(missing)}"}
        private_key_formatted = private_key.replace('\\n', '\n')
        credentials_dict = {
            "type": "service_account",
            "project_id": project_id,
            "private_key_id": private_key_id,
            "private_key": private_key_formatted,
            "client_email": client_email,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
        }
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError:
            return {"success": False, "message": "Google Drive API libraries not available. Install: pip install google-auth google-api-python-client"}
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        drive_service = build('drive', 'v3', credentials=credentials)
        upload_file_name = file_name if file_name else file_path_obj.name
        file_metadata = {'name': upload_file_name, 'parents': [folder_id]}
        media = MediaFileUpload(str(file_path_obj), resumable=True)
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()
        return {
            'success': True,
            'fileId': file.get('id'),
            'fileName': file.get('name'),
            'webViewLink': file.get('webViewLink'),
            'message': f"File successfully uploaded to Google Drive with ID: {file.get('id')}"
        }
    except HTTPException as e:
        return {"success": False, "message": e.detail or "Upload failed"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/v1/proxy/upload-to-drive")
async def upload_to_drive(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Upload a file from the scratch directory to Google Drive using service account credentials from .env file.
    filePath must be a filename relative to the scratch directory (e.g. report.docx). Path traversal and absolute paths are rejected.
    """
    folder_id = None
    file_path_obj = None
    try:
        form_data = await request.form()
        file_path = form_data.get('filePath')
        if not file_path or not str(file_path).strip():
            raise HTTPException(status_code=400, detail="filePath is required")
        file_path_obj = resolve_scratch_path(str(file_path).strip(), DRIVE_UPLOAD_EXTENSIONS)
        if not file_path_obj.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        file_name = form_data.get('fileName')
        folder_id = form_data.get('folderId') or os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        if not folder_id:
            raise HTTPException(status_code=400, detail="folderId is required (provide in request or set GOOGLE_DRIVE_FOLDER_ID in .env)")
        
        # Read Google Drive credentials from environment variables (loaded from .env file)
        project_id = os.getenv('GOOGLE_DRIVE_PROJECT_ID')
        private_key_id = os.getenv('GOOGLE_DRIVE_PRIVATE_KEY_ID')
        private_key = os.getenv('GOOGLE_DRIVE_PRIVATE_KEY')
        client_email = os.getenv('GOOGLE_DRIVE_CLIENT_EMAIL')
        
        # Validate that all required credentials are present
        if not all([project_id, private_key_id, private_key, client_email]):
            missing = [k for k, v in {
                'GOOGLE_DRIVE_PROJECT_ID': project_id,
                'GOOGLE_DRIVE_PRIVATE_KEY_ID': private_key_id,
                'GOOGLE_DRIVE_PRIVATE_KEY': private_key,
                'GOOGLE_DRIVE_CLIENT_EMAIL': client_email
            }.items() if not v]
            raise HTTPException(
                status_code=500,
                detail=f"Missing Google Drive credentials in .env file: {', '.join(missing)}"
            )
        
        # Construct credentials object from environment variables
        # Replace \\n with actual newlines in private key
        private_key_formatted = private_key.replace('\\n', '\n')
        
        credentials_dict = {
            "type": "service_account",
            "project_id": project_id,
            "private_key_id": private_key_id,
            "private_key": private_key_formatted,
            "client_email": client_email,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
        }
        
        # Try to import Google Drive API libraries
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            GOOGLE_DRIVE_AVAILABLE = True
        except ImportError:
            GOOGLE_DRIVE_AVAILABLE = False
            raise HTTPException(
                status_code=503,
                detail="Google Drive API libraries not available. Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
            )
        
        # Authenticate with Google Drive using service account credentials
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=['https://www.googleapis.com/auth/drive.file']
        )
        
        # Build the Drive service
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # Determine file name to use
        upload_file_name = file_name if file_name else file_path_obj.name
        
        # Prepare file metadata
        file_metadata = {
            'name': upload_file_name,
            'parents': [folder_id] if folder_id else []
        }
        
        # Upload file to Google Drive
        media = MediaFileUpload(
            str(file_path_obj),
            resumable=True
        )
        
        # Perform the upload
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()
        
        # Audit log: user, filename, folder_id, success, file_id
        user_sub = current_user.get("sub") or "unknown"
        print(f"[AUDIT] upload-to-drive user={user_sub} filename={file_path_obj.name} folder_id={folder_id} success=true file_id={file.get('id')}")
        # Return success response with file ID
        return {
            'success': True,
            'fileId': file.get('id'),
            'fileName': file.get('name'),
            'webViewLink': file.get('webViewLink'),
            'message': f"File successfully uploaded to Google Drive with ID: {file.get('id')}"
        }
        
    except HTTPException as exc:
        # Audit log on auth/path/not-found/credential errors
        user_sub = current_user.get("sub") if current_user else "unknown"
        filename_log = file_path_obj.name if file_path_obj else "n/a"
        print(f"[AUDIT] upload-to-drive user={user_sub} filename={filename_log} folder_id={folder_id or 'n/a'} success=false status={exc.status_code} detail={exc.detail}")
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Audit log on unexpected errors
        user_sub = current_user.get("sub") if current_user else "unknown"
        print(f"[AUDIT] upload-to-drive user={user_sub} folder_id={folder_id or 'n/a'} success=false error={str(e)}")
        # Handle any other errors
        print(f"âŒ Google Drive upload error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file to Google Drive: {str(e)}"
        )

# ============================================================================
# END GOOGLE DRIVE UPLOAD ENDPOINT
# ============================================================================

# ============================================================================
# SSL CERTIFICATE UTILITIES
# ============================================================================

def get_local_ip() -> Optional[str]:
    """
    Get the local IP address of this machine.
    Returns the IP address or None if unable to determine.
    """
    try:
        # Connect to a remote address to determine local IP (doesn't actually send data)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

def find_mkcert_certificates() -> Tuple[Optional[str], Optional[str]]:
    """
    Find mkcert-generated certificates in project root or certs/ directory.
    Returns a tuple of (cert_file, key_file) or (None, None) if not found.
    mkcert creates files like: <hostname>+2.pem, <hostname>+2-key.pem, etc.
    Hostname comes from HTTPS_CERT_HOSTNAME in .env.
    """
    # Search in certs/ first, then project root (glob uses sanitized hostname)
    search_dirs = [_PROJECT_ROOT / "certs", _PROJECT_ROOT]
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        cert_files = list(search_dir.glob(f"{_SSL_CERT_HOSTNAME_GLOB}*.pem"))
        # Filter out key files and find matching pairs
        cert_key_pairs = []
        for cert_path in cert_files:
            if "-key" in cert_path.name:
                continue
            key_path = cert_path.parent / (cert_path.stem + "-key.pem")
            if key_path.exists():
                cert_key_pairs.append((str(cert_path), str(key_path), cert_path.stat().st_mtime))
        if cert_key_pairs:
            cert_key_pairs.sort(key=lambda x: x[2], reverse=True)
            return cert_key_pairs[0][0], cert_key_pairs[0][1]
    return None, None

def get_ssl_certificates() -> Tuple[Optional[str], Optional[str]]:
    """
    Get SSL certificate files for HTTPS server.
    First tries to find mkcert certificates in certs/ or project root.
    Returns a tuple of (cert_file, key_file) or (None, None) if not found.
    """
    # Try to find mkcert certificates first
    cert_file, key_file = find_mkcert_certificates()
    if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
        print(f"[SSL] Found mkcert certificate: {cert_file}")
        return cert_file, key_file
    
    # Fall back to default certificate file names in certs/ or project root (hostname from .env)
    for base in [_PROJECT_ROOT / "certs", _PROJECT_ROOT]:
        default_cert = base / f"{_SSL_CERT_HOSTNAME}+2.pem"
        default_key = base / f"{_SSL_CERT_HOSTNAME}+2-key.pem"
        if default_cert.exists() and default_key.exists():
            print(f"[SSL] Using default certificate: {default_cert}")
            return str(default_cert), str(default_key)
    
    # Return None if no certificates found
    print("[SSL] No SSL certificates found. Server will run without HTTPS.")
    return None, None

# ============================================================================
# END SSL CERTIFICATE UTILITIES
# ============================================================================

if __name__ == "__main__":
    # Start the server
    print("[START] Starting CATBot Proxy Server with File Operations...")
    print(f"[INFO] Scratch directory: {SCRATCH_DIR}")
    
    # Get SSL certificates for HTTPS
    cert_file, key_file = get_ssl_certificates()
    
    # Configure uvicorn with SSL if certificates are available
    if cert_file and key_file:
        print(f"[SSL] Starting HTTPS server on port 8002")
        print(f"[SSL] Certificate: {cert_file}")
        print(f"[SSL] Key: {key_file}")
        uvicorn.run(
            "src.servers.proxy_server:app",
            host="0.0.0.0",
            port=8002,
            reload=PROXY_RELOAD,
            log_level="info",
            ssl_keyfile=key_file,
            ssl_certfile=cert_file
        )
    else:
        print("[WARN] Starting HTTP server (no SSL certificates found)")
        print("[INFO] To enable HTTPS, ensure mkcert certificate files are in certs/ directory")
        uvicorn.run(
            "src.servers.proxy_server:app",
            host="0.0.0.0",
            port=8002,
            reload=PROXY_RELOAD,
            log_level="info"
        )
