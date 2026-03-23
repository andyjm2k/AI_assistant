"""Built-in Spotify Web API player skill."""

from __future__ import annotations

import base64
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from urllib.parse import urlencode, urlparse, urlunparse

import httpx

from src.skills.base import BaseSkill, BaseTool
from src.skills.exceptions import SkillValidationError
from src.skills.models import SkillContext

DEFAULT_SPOTIFY_API_BASE = "https://api.spotify.com/v1"
DEFAULT_SPOTIFY_ACCOUNTS_BASE = "https://accounts.spotify.com"
DEFAULT_SPOTIFY_AUTH_BASE = "https://accounts.spotify.com/api"
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_TIMEOUT_SECONDS = 60.0
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50
_SPOTIFY_ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")
_TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS = 30
_TOKEN_VALIDATION_QUERY = "spotify"
_PLAYBACK_AUTH_SCOPES = ("user-modify-playback-state", "user-read-playback-state")


def _coerce_timeout_seconds(value: Any, *, default: float = DEFAULT_TIMEOUT_SECONDS) -> float:
    """Coerce a timeout value into Spotify-safe bounds."""

    try:
        parsed = float(default if value is None else value)
    except (TypeError, ValueError):
        parsed = default
    return max(5.0, min(parsed, MAX_TIMEOUT_SECONDS))


def _coerce_search_limit(value: Any) -> int:
    """Coerce the Spotify search result limit."""

    if value is None:
        return DEFAULT_SEARCH_LIMIT
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SkillValidationError("'limit' must be an integer.") from exc
    if parsed < 1 or parsed > MAX_SEARCH_LIMIT:
        raise SkillValidationError(f"'limit' must be between 1 and {MAX_SEARCH_LIMIT}.")
    return parsed


def _coerce_non_negative_int(value: Any, *, key: str) -> Optional[int]:
    """Coerce an optional integer that must not be negative."""

    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SkillValidationError(f"'{key}' must be an integer.") from exc
    if parsed < 0:
        raise SkillValidationError(f"'{key}' must be >= 0.")
    return parsed


def _resolve_client_id() -> str:
    """Resolve the Spotify application client ID from environment variables."""

    client_id = str(os.getenv("SPOTIFY_CLIENT_ID") or "").strip()
    if not client_id:
        raise SkillValidationError("SPOTIFY_CLIENT_ID is not configured.")
    return client_id


def _resolve_client_secret() -> str:
    """Resolve the Spotify application client secret from environment variables."""

    client_secret = str(os.getenv("SPOTIFY_CLIENT_SECRET") or "").strip()
    if not client_secret:
        raise SkillValidationError("SPOTIFY_CLIENT_SECRET is not configured.")
    return client_secret


def _resolve_redirect_uri() -> str:
    """Resolve the Spotify OAuth redirect URI used for re-authorization links."""

    redirect_uri = str(os.getenv("SPOTIFY_REDIRECT_URI") or "").strip()
    if not redirect_uri:
        raise SkillValidationError(
            "SPOTIFY_REDIRECT_URI is not configured. Set it to one of your Spotify app's "
            "registered redirect URIs so spotify_player can generate a re-authorization URL."
        )
    return redirect_uri


def _build_local_authorize_url() -> str:
    """Build CATBot's local Spotify authorization bootstrap URL from the callback origin."""

    redirect_uri = _resolve_redirect_uri()
    parsed = urlparse(redirect_uri)
    if not parsed.scheme or not parsed.netloc:
        raise SkillValidationError("SPOTIFY_REDIRECT_URI must be an absolute URL.")
    return urlunparse((parsed.scheme, parsed.netloc, "/spotify/authorize", "", "", ""))


def _normalize_spotify_id(value: Any, *, expected_type: str) -> str:
    """Accept a raw Spotify ID, URI, or open.spotify.com URL and return the object ID."""

    raw = str(value or "").strip()
    if not raw:
        raise SkillValidationError(f"'{expected_type}_id' is required.")
    if _SPOTIFY_ID_RE.fullmatch(raw):
        return raw

    if raw.startswith("spotify:"):
        parts = raw.split(":")
        if len(parts) >= 3 and parts[1].strip().lower() == expected_type:
            candidate = parts[2].strip()
            if _SPOTIFY_ID_RE.fullmatch(candidate):
                return candidate
        raise SkillValidationError(
            f"Expected a Spotify {expected_type} URI in the form 'spotify:{expected_type}:<id>'."
        )

    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc.lower().endswith("spotify.com"):
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0].strip().lower() == expected_type:
            candidate = path_parts[1].strip()
            if _SPOTIFY_ID_RE.fullmatch(candidate):
                return candidate

    raise SkillValidationError(
        f"'{expected_type}_id' must be a Spotify ID, URI, or open.spotify.com {expected_type} URL."
    )


def _extract_spotify_error_message(response: httpx.Response) -> str:
    """Extract a concise Spotify API error message from a response."""

    try:
        payload = response.json()
    except Exception:
        return response.text[:500]

    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message") or error.get("error_description")
        if message:
            return str(message)
        status = error.get("status")
        if status:
            return f"Spotify API error {status}."
    if isinstance(error, str):
        return error
    if isinstance(payload.get("error_description"), str):
        return str(payload["error_description"])
    return str(payload)[:500]


def _normalize_track_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a Spotify track payload into the CATBot skill response shape."""

    artists = item.get("artists") if isinstance(item.get("artists"), list) else []
    album = item.get("album") if isinstance(item.get("album"), dict) else {}
    external_urls = item.get("external_urls") if isinstance(item.get("external_urls"), dict) else {}
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "uri": item.get("uri"),
        "artists": [
            {
                "id": artist.get("id"),
                "name": artist.get("name"),
                "uri": artist.get("uri"),
            }
            for artist in artists
            if isinstance(artist, dict)
        ],
        "artist_names": [artist.get("name") for artist in artists if isinstance(artist, dict) and artist.get("name")],
        "album": {
            "id": album.get("id"),
            "name": album.get("name"),
            "release_date": album.get("release_date"),
            "uri": album.get("uri"),
        },
        "duration_ms": item.get("duration_ms"),
        "explicit": bool(item.get("explicit")),
        "popularity": item.get("popularity"),
        "preview_url": item.get("preview_url"),
        "external_url": external_urls.get("spotify"),
        "is_playable": item.get("is_playable"),
    }


def _normalize_device_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a Spotify player device payload into the CATBot skill response shape."""

    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "type": item.get("type"),
        "is_active": bool(item.get("is_active")),
        "is_private_session": bool(item.get("is_private_session")),
        "is_restricted": bool(item.get("is_restricted")),
        "supports_volume": item.get("supports_volume"),
        "volume_percent": item.get("volume_percent"),
    }


class SpotifyApiClient:
    """Small async client wrapper for Spotify Web API auth and playback calls."""

    def __init__(self) -> None:
        self.api_base = DEFAULT_SPOTIFY_API_BASE.rstrip("/")
        self.accounts_base = DEFAULT_SPOTIFY_ACCOUNTS_BASE.rstrip("/")
        self.auth_base = DEFAULT_SPOTIFY_AUTH_BASE.rstrip("/")
        self._app_token: Optional[str] = None
        self._app_token_expires_at: float = 0.0
        self._user_token: Optional[str] = None
        self._user_token_expires_at: float = 0.0

    def _build_reauthorization_url(self) -> str:
        """Build a Spotify authorization URL for replacing an invalid refresh token."""

        try:
            return _build_local_authorize_url()
        except SkillValidationError:
            query = urlencode(
                {
                    "client_id": _resolve_client_id(),
                    "response_type": "code",
                    "redirect_uri": _resolve_redirect_uri(),
                    "scope": " ".join(_PLAYBACK_AUTH_SCOPES),
                    "show_dialog": "true",
                }
            )
            return f"{self.accounts_base}/authorize?{query}"

    def _build_reauthorization_message(self, *, reason: Optional[str] = None) -> str:
        """Create a clear re-authorization error for invalid or missing playback auth."""

        message = "Spotify playback authorization has expired or is invalid."
        if reason:
            message = f"{message} Spotify said: {reason}."
        authorize_url = self._build_reauthorization_url()
        return (
            f"{message} Re-authorize the Spotify app using this "
            f"one-time URL: {authorize_url}"
        )

    async def _request_token(self, form_data: Dict[str, Any], *, timeout_seconds: float) -> Dict[str, Any]:
        """Request a Spotify access token using the configured app credentials."""

        client_id = _resolve_client_id()
        client_secret = _resolve_client_secret()
        basic_token = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {basic_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                f"{self.auth_base}/token",
                headers=headers,
                data=form_data,
            )
        if response.status_code != 200:
            message = _extract_spotify_error_message(response)
            is_refresh_request = str(form_data.get("grant_type") or "").strip().lower() == "refresh_token"
            if is_refresh_request:
                try:
                    payload = response.json()
                except Exception:
                    payload = None
                error_code = ""
                if isinstance(payload, dict):
                    error_code = str(payload.get("error") or "").strip().lower()
                if error_code == "invalid_grant":
                    raise SkillValidationError(self._build_reauthorization_message(reason=message))
            raise RuntimeError(f"Spotify token request failed ({response.status_code}): {message}")
        payload = response.json()
        if not isinstance(payload, dict) or not str(payload.get("access_token") or "").strip():
            raise RuntimeError("Spotify token response did not contain an access token.")
        return payload

    async def get_app_access_token(self, *, timeout_seconds: float) -> str:
        """Get a cached app access token for non-user Spotify API requests."""

        if self._app_token and time.time() < self._app_token_expires_at - _TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS:
            return self._app_token
        payload = await self._request_token(
            {"grant_type": "client_credentials"},
            timeout_seconds=timeout_seconds,
        )
        self._app_token = str(payload.get("access_token") or "").strip()
        expires_in = int(payload.get("expires_in") or 3600)
        self._app_token_expires_at = time.time() + max(expires_in, 60)
        return self._app_token

    async def _validate_access_token(self, access_token: str, *, timeout_seconds: float) -> bool:
        """Check whether a Spotify access token is still valid before playback."""

        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "q": _TOKEN_VALIDATION_QUERY,
            "type": "track",
            "limit": 1,
        }
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(
                f"{self.api_base}/search",
                headers=headers,
                params=params,
            )
        if response.status_code == 200:
            return True
        if response.status_code == 401:
            return False
        message = _extract_spotify_error_message(response)
        raise RuntimeError(f"Spotify token validation failed ({response.status_code}): {message}")

    async def _refresh_playback_access_token(self, *, timeout_seconds: float) -> str:
        """Refresh the playback token using the configured Spotify refresh token."""

        refresh_token = str(os.getenv("SPOTIFY_REFRESH_TOKEN") or "").strip()
        if not refresh_token:
            raise SkillValidationError(
                "Spotify playback requires SPOTIFY_REFRESH_TOKEN with the "
                "'user-modify-playback-state' scope."
            )

        payload = await self._request_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout_seconds=timeout_seconds,
        )
        self._user_token = str(payload.get("access_token") or "").strip()
        expires_in = int(payload.get("expires_in") or 3600)
        self._user_token_expires_at = time.time() + max(expires_in, 60)
        return self._user_token

    async def get_playback_access_token(self, *, timeout_seconds: float) -> str:
        """Get a playback-capable user token for Spotify player control endpoints."""

        refresh_token = str(os.getenv("SPOTIFY_REFRESH_TOKEN") or "").strip()
        if self._user_token:
            if time.time() < self._user_token_expires_at - _TOKEN_EXPIRY_SAFETY_MARGIN_SECONDS:
                is_valid = await self._validate_access_token(self._user_token, timeout_seconds=timeout_seconds)
                if is_valid:
                    return self._user_token
            self._user_token = None
            self._user_token_expires_at = 0.0

        access_token = str(os.getenv("SPOTIFY_ACCESS_TOKEN") or "").strip()
        if access_token:
            is_valid = await self._validate_access_token(access_token, timeout_seconds=timeout_seconds)
            if is_valid:
                return access_token
            if refresh_token:
                return await self._refresh_playback_access_token(timeout_seconds=timeout_seconds)
            raise SkillValidationError(self._build_reauthorization_message(reason="access token expired"))

        if refresh_token:
            return await self._refresh_playback_access_token(timeout_seconds=timeout_seconds)

        raise SkillValidationError(
            "Spotify playback requires SPOTIFY_ACCESS_TOKEN or SPOTIFY_REFRESH_TOKEN. "
            "For silent renewal and re-authorization support, configure SPOTIFY_REFRESH_TOKEN "
            "and SPOTIFY_REDIRECT_URI with the 'user-modify-playback-state' scope."
        )

    async def _send_playback_request(
        self,
        *,
        access_token: str,
        payload: Dict[str, Any],
        device_id: Optional[str],
        timeout_seconds: float,
    ) -> httpx.Response:
        """Issue the Spotify playback request with the provided bearer token."""

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        params: Dict[str, Any] = {}
        if device_id:
            params["device_id"] = device_id

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            return await client.put(
                f"{self.api_base}/me/player/play",
                headers=headers,
                params=params or None,
                json=payload,
            )

    async def search_tracks(
        self,
        *,
        query: str,
        limit: int,
        market: Optional[str],
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        """Search Spotify tracks using application credentials."""

        access_token = await self.get_app_access_token(timeout_seconds=timeout_seconds)
        params: Dict[str, Any] = {
            "q": query,
            "type": "track",
            "limit": limit,
        }
        if market:
            params["market"] = market

        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(
                f"{self.api_base}/search",
                headers=headers,
                params=params,
            )
        if response.status_code != 200:
            message = _extract_spotify_error_message(response)
            raise RuntimeError(f"Spotify search failed ({response.status_code}): {message}")

        payload = response.json()
        tracks_payload = payload.get("tracks") if isinstance(payload, dict) else {}
        if not isinstance(tracks_payload, dict):
            tracks_payload = {}
        items = tracks_payload.get("items") if isinstance(tracks_payload.get("items"), list) else []
        return {
            "query": query,
            "limit": limit,
            "market": market,
            "returned_count": len(items),
            "total": tracks_payload.get("total"),
            "tracks": [
                _normalize_track_item(item)
                for item in items
                if isinstance(item, dict)
            ],
        }

    async def get_available_devices(self, *, timeout_seconds: float) -> Dict[str, Any]:
        """Retrieve available Spotify Connect player devices for the current user."""

        access_token = await self.get_playback_access_token(timeout_seconds=timeout_seconds)
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(
                f"{self.api_base}/me/player/devices",
                headers=headers,
            )
        if response.status_code == 401 and str(os.getenv("SPOTIFY_REFRESH_TOKEN") or "").strip():
            access_token = await self._refresh_playback_access_token(timeout_seconds=timeout_seconds)
            headers = {"Authorization": f"Bearer {access_token}"}
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.get(
                    f"{self.api_base}/me/player/devices",
                    headers=headers,
                )
        if response.status_code != 200:
            message = _extract_spotify_error_message(response)
            raise RuntimeError(f"Spotify device lookup failed ({response.status_code}): {message}")

        payload = response.json()
        devices = payload.get("devices") if isinstance(payload, dict) and isinstance(payload.get("devices"), list) else []
        normalized_devices = [
            _normalize_device_item(item)
            for item in devices
            if isinstance(item, dict)
        ]
        return {
            "returned_count": len(normalized_devices),
            "devices": normalized_devices,
            "device_ids": [device.get("id") for device in normalized_devices if device.get("id")],
        }

    async def start_playback(
        self,
        *,
        payload: Dict[str, Any],
        device_id: Optional[str],
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        """Start Spotify playback using a user token."""

        access_token = await self.get_playback_access_token(timeout_seconds=timeout_seconds)
        response = await self._send_playback_request(
            access_token=access_token,
            payload=payload,
            device_id=device_id,
            timeout_seconds=timeout_seconds,
        )
        if response.status_code == 401 and str(os.getenv("SPOTIFY_REFRESH_TOKEN") or "").strip():
            access_token = await self._refresh_playback_access_token(timeout_seconds=timeout_seconds)
            response = await self._send_playback_request(
                access_token=access_token,
                payload=payload,
                device_id=device_id,
                timeout_seconds=timeout_seconds,
            )
        if response.status_code not in {200, 202, 204}:
            message = _extract_spotify_error_message(response)
            raise RuntimeError(f"Spotify playback request failed ({response.status_code}): {message}")
        return {
            "started": True,
            "status_code": response.status_code,
            "device_id": device_id,
        }


class SearchTracksTool(BaseTool):
    """Search for tracks through the Spotify Web API."""

    name = "search_tracks"
    description = "Search Spotify tracks by query using Spotify Web API application auth."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Track search query text.",
            },
            "limit": {
                "type": "integer",
                "default": DEFAULT_SEARCH_LIMIT,
                "minimum": 1,
                "maximum": MAX_SEARCH_LIMIT,
                "description": "Maximum number of tracks to return.",
            },
            "market": {
                "type": "string",
                "description": "Optional ISO 3166-1 alpha-2 market code such as AU or US.",
            },
            "timeout_seconds": {
                "type": "number",
                "default": DEFAULT_TIMEOUT_SECONDS,
                "minimum": 5,
                "maximum": MAX_TIMEOUT_SECONDS,
                "description": "HTTP timeout in seconds.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, client: SpotifyApiClient) -> None:
        self.client = client

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise SkillValidationError("'query' is required.")
        limit = _coerce_search_limit(arguments.get("limit"))
        market = str(arguments.get("market") or "").strip().upper() or None
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))
        return await self.client.search_tracks(
            query=query,
            limit=limit,
            market=market,
            timeout_seconds=timeout_seconds,
        )


class PlayTrackTool(BaseTool):
    """Start playback for a single Spotify track."""

    name = "play_track"
    description = "Start Spotify playback for a specific track ID, URI, or URL."
    input_schema = {
        "type": "object",
        "properties": {
            "track_id": {
                "type": "string",
                "description": "Spotify track ID, spotify:track URI, or open.spotify.com track URL.",
            },
            "device_id": {
                "type": "string",
                "description": "Optional Spotify Connect device ID. Falls back to SPOTIFY_DEVICE_ID.",
            },
            "position_ms": {
                "type": "integer",
                "minimum": 0,
                "description": "Optional start position in milliseconds.",
            },
            "timeout_seconds": {
                "type": "number",
                "default": DEFAULT_TIMEOUT_SECONDS,
                "minimum": 5,
                "maximum": MAX_TIMEOUT_SECONDS,
                "description": "HTTP timeout in seconds.",
            },
        },
        "required": ["track_id"],
        "additionalProperties": False,
    }

    def __init__(self, client: SpotifyApiClient) -> None:
        self.client = client

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        track_id = _normalize_spotify_id(arguments.get("track_id"), expected_type="track")
        position_ms = _coerce_non_negative_int(arguments.get("position_ms"), key="position_ms")
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))
        device_id = str(arguments.get("device_id") or os.getenv("SPOTIFY_DEVICE_ID") or "").strip() or None

        payload: Dict[str, Any] = {"uris": [f"spotify:track:{track_id}"]}
        if position_ms is not None:
            payload["position_ms"] = position_ms

        response = await self.client.start_playback(
            payload=payload,
            device_id=device_id,
            timeout_seconds=timeout_seconds,
        )
        response.update(
            {
                "track_id": track_id,
                "track_uri": f"spotify:track:{track_id}",
            }
        )
        return response


class GetAvailableDevicesTool(BaseTool):
    """List Spotify Connect devices available to the current user."""

    name = "get_available_devices"
    description = "Retrieve Spotify player devices and their device IDs for the current user."
    input_schema = {
        "type": "object",
        "properties": {
            "timeout_seconds": {
                "type": "number",
                "default": DEFAULT_TIMEOUT_SECONDS,
                "minimum": 5,
                "maximum": MAX_TIMEOUT_SECONDS,
                "description": "HTTP timeout in seconds.",
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, client: SpotifyApiClient) -> None:
        self.client = client

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))
        return await self.client.get_available_devices(timeout_seconds=timeout_seconds)


class PlayPlaylistTool(BaseTool):
    """Start playback for a Spotify playlist."""

    name = "play_playlist"
    description = "Start Spotify playback for a specific playlist ID, URI, or URL."
    input_schema = {
        "type": "object",
        "properties": {
            "playlist_id": {
                "type": "string",
                "description": "Spotify playlist ID, spotify:playlist URI, or open.spotify.com playlist URL.",
            },
            "device_id": {
                "type": "string",
                "description": "Optional Spotify Connect device ID. Falls back to SPOTIFY_DEVICE_ID.",
            },
            "offset_position": {
                "type": "integer",
                "minimum": 0,
                "description": "Optional zero-based starting track offset within the playlist.",
            },
            "position_ms": {
                "type": "integer",
                "minimum": 0,
                "description": "Optional start position in milliseconds inside the selected track.",
            },
            "timeout_seconds": {
                "type": "number",
                "default": DEFAULT_TIMEOUT_SECONDS,
                "minimum": 5,
                "maximum": MAX_TIMEOUT_SECONDS,
                "description": "HTTP timeout in seconds.",
            },
        },
        "required": ["playlist_id"],
        "additionalProperties": False,
    }

    def __init__(self, client: SpotifyApiClient) -> None:
        self.client = client

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        playlist_id = _normalize_spotify_id(arguments.get("playlist_id"), expected_type="playlist")
        offset_position = _coerce_non_negative_int(arguments.get("offset_position"), key="offset_position")
        position_ms = _coerce_non_negative_int(arguments.get("position_ms"), key="position_ms")
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))
        device_id = str(arguments.get("device_id") or os.getenv("SPOTIFY_DEVICE_ID") or "").strip() or None

        payload: Dict[str, Any] = {"context_uri": f"spotify:playlist:{playlist_id}"}
        if offset_position is not None:
            payload["offset"] = {"position": offset_position}
        if position_ms is not None:
            payload["position_ms"] = position_ms

        response = await self.client.start_playback(
            payload=payload,
            device_id=device_id,
            timeout_seconds=timeout_seconds,
        )
        response.update(
            {
                "playlist_id": playlist_id,
                "playlist_uri": f"spotify:playlist:{playlist_id}",
                "offset_position": offset_position,
            }
        )
        return response


class SpotifyPlayerSkill(BaseSkill):
    """Spotify Web API skill for track search and playback control."""

    name = "spotify_player"
    description = (
        "Spotify Web API tools for track search, player device discovery, and playback control. "
        "Search uses app credentials. Player tools validate the current token, refresh silently when possible, "
        "and require Spotify user authorization."
    )
    version = "1.2.0"
    tags = ["spotify", "music", "playback"]

    def __init__(self, root_dir: str = "./scratch") -> None:
        super().__init__()
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.client = SpotifyApiClient()

    def create_tools(self) -> Sequence[BaseTool]:
        return [
            SearchTracksTool(client=self.client),
            GetAvailableDevicesTool(client=self.client),
            PlayTrackTool(client=self.client),
            PlayPlaylistTool(client=self.client),
        ]


def create_skill(root_dir: str = "./scratch") -> BaseSkill:
    """Create the built-in Spotify player skill."""

    return SpotifyPlayerSkill(root_dir=root_dir)
