from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse
import uuid

from fastapi.testclient import TestClient


def _client():
    from src.servers import proxy_server as ps

    return TestClient(ps.app)


def test_spotify_authorize_redirects_to_accounts_with_expected_query(monkeypatch) -> None:
    from src.servers import proxy_server as ps

    ps.spotify_oauth_pending_states.clear()
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "https://catbot.local:8002/spotify/callback")

    client = _client()
    response = client.get("/spotify/authorize", follow_redirects=False)

    assert response.status_code == 307, response.text
    location = response.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.spotify.com"
    assert parsed.path == "/authorize"
    assert query["client_id"] == ["spotify-client-id"]
    assert query["response_type"] == ["code"]
    assert query["redirect_uri"] == ["https://catbot.local:8002/spotify/callback"]
    assert query["scope"] == ["user-modify-playback-state user-read-playback-state"]
    assert query["show_dialog"] == ["true"]
    state = query["state"][0]
    assert state in ps.spotify_oauth_pending_states


def test_spotify_callback_persists_refresh_and_access_tokens(monkeypatch) -> None:
    from src.servers import proxy_server as ps

    temp_dir = Path("scratch") / f"spotify-oauth-test-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    env_file = temp_dir / ".env"

    try:
        env_file.write_text(
            "SPOTIFY_CLIENT_ID=spotify-client-id\n"
            "SPOTIFY_CLIENT_SECRET=spotify-client-secret\n"
            "SPOTIFY_REDIRECT_URI=https://catbot.local:8002/spotify/callback\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(ps, "ENV_FILE", env_file)
        monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
        monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify-client-secret")
        monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "https://catbot.local:8002/spotify/callback")

        ps.spotify_oauth_pending_states.clear()
        ps.spotify_oauth_pending_states["state-123"] = time.time()

        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "access_token": "spotify-access-token",
            "refresh_token": "spotify-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        client = _client()
        with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=token_response)
            mock_client_cls.return_value = mock_client

            response = client.get("/spotify/callback?code=spotify-code&state=state-123")

        assert response.status_code == 200, response.text
        assert "Spotify authorization complete" in response.text
        assert 'SPOTIFY_REFRESH_TOKEN' in response.text
        assert os.environ["SPOTIFY_ACCESS_TOKEN"] == "spotify-access-token"
        assert os.environ["SPOTIFY_REFRESH_TOKEN"] == "spotify-refresh-token"

        persisted = env_file.read_text(encoding="utf-8")
        assert "SPOTIFY_ACCESS_TOKEN=spotify-access-token" in persisted
        assert "SPOTIFY_REFRESH_TOKEN=spotify-refresh-token" in persisted

        post_call = mock_client.post.call_args
        assert post_call is not None
        assert post_call.args[0] == "https://accounts.spotify.com/api/token"
        assert post_call.kwargs["data"] == {
            "grant_type": "authorization_code",
            "code": "spotify-code",
            "redirect_uri": "https://catbot.local:8002/spotify/callback",
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_spotify_callback_rejects_invalid_state(monkeypatch) -> None:
    from src.servers import proxy_server as ps

    ps.spotify_oauth_pending_states.clear()
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "spotify-client-secret")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "https://catbot.local:8002/spotify/callback")

    client = _client()
    response = client.get("/spotify/callback?code=spotify-code&state=missing-state")

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Invalid or expired Spotify OAuth state."


def test_spotify_authorize_rejects_localhost_redirect_uri(monkeypatch) -> None:
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "spotify-client-id")
    monkeypatch.setenv("SPOTIFY_REDIRECT_URI", "https://localhost:8002/spotify/callback")

    client = _client()
    response = client.get("/spotify/authorize", follow_redirects=False)

    assert response.status_code == 500, response.text
    assert "cannot use localhost" in response.json()["detail"]
