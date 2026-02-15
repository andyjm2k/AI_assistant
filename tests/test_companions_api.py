"""
Unit and API tests for proxy server Companions API.
Tests GET/POST/DELETE /v1/companions and resolve_companion_path security.
Uses a temporary directory for COMPANIONS_DIR so real config is not modified.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _auth_headers():
    """Build Authorization header with a valid JWT (sub must exist in users_db, same as test_proxy_file_security)."""
    from src.servers.proxy_server import create_jwt
    token = create_jwt({"sub": "andyjm2k"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def companions_dir(tmp_path):
    """Use a temporary directory as COMPANIONS_DIR for the duration of the test."""
    (tmp_path / "companions").mkdir(exist_ok=True)
    with patch("src.servers.proxy_server.COMPANIONS_DIR", tmp_path / "companions"):
        yield tmp_path / "companions"


@pytest.fixture
def client_with_companions(companions_dir):
    """TestClient with COMPANIONS_DIR patched to a temp dir."""
    with TestClient(__import__("src.servers.proxy_server", fromlist=["app"]).app) as c:
        yield c


# ---------------------------------------------------------------------------
# Unit tests for resolve_companion_path
# ---------------------------------------------------------------------------

class TestResolveCompanionPath:
    """Unit tests for resolve_companion_path id validation."""

    @pytest.fixture(autouse=True)
    def patch_companions_dir(self, tmp_path):
        comp_dir = tmp_path / "companions"
        comp_dir.mkdir(exist_ok=True)
        with patch("src.servers.proxy_server.COMPANIONS_DIR", comp_dir):
            yield comp_dir

    def test_valid_id_returns_path(self):
        """Valid alphanumeric id returns path under COMPANIONS_DIR with .json."""
        from src.servers.proxy_server import resolve_companion_path, COMPANIONS_DIR
        result = resolve_companion_path("abc123")
        assert result == COMPANIONS_DIR / "abc123.json"
        assert result.suffix.lower() == ".json"

    def test_id_with_hyphen_and_underscore_succeeds(self):
        """Id with hyphen and underscore is allowed."""
        from src.servers.proxy_server import resolve_companion_path, COMPANIONS_DIR
        result = resolve_companion_path("my-companion_1")
        assert result == COMPANIONS_DIR / "my-companion_1.json"

    def test_empty_id_raises_400(self):
        """Empty id raises HTTPException 400."""
        from src.servers.proxy_server import resolve_companion_path
        with pytest.raises(HTTPException) as exc_info:
            resolve_companion_path("")
        assert exc_info.value.status_code == 400

    def test_invalid_chars_raise_400(self):
        """Id with dots or path chars raises 400."""
        from src.servers.proxy_server import resolve_companion_path
        with pytest.raises(HTTPException) as exc_info:
            resolve_companion_path("bad.id")
        assert exc_info.value.status_code == 400
        with pytest.raises(HTTPException) as exc_info:
            resolve_companion_path("../other")
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# API tests for /v1/companions
# ---------------------------------------------------------------------------

class TestCompanionsApi:
    """API tests: list, create, get, delete companions with auth."""

    def test_list_companions_requires_auth(self, client_with_companions):
        """GET /v1/companions without auth returns 401."""
        resp = client_with_companions.get("/v1/companions")
        assert resp.status_code == 401

    def test_list_companions_returns_array(self, client_with_companions):
        """GET /v1/companions with auth returns 200 and JSON array."""
        resp = client_with_companions.get("/v1/companions", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_create_companion_requires_auth(self, client_with_companions):
        """POST /v1/companions without auth returns 401."""
        resp = client_with_companions.post(
            "/v1/companions",
            json={"name": "Test", "settings": {}},
        )
        assert resp.status_code == 401

    def test_create_companion_succeeds_and_file_exists(self, client_with_companions, companions_dir):
        """POST /v1/companions with auth creates JSON file and returns id and name."""
        resp = client_with_companions.post(
            "/v1/companions",
            json={"name": "My Companion", "settings": {"userName": "User", "assistantName": "EVA"}},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["name"] == "My Companion"
        cid = data["id"]
        path = companions_dir / f"{cid}.json"
        assert path.exists()
        content = json.loads(path.read_text(encoding="utf-8"))
        assert content["name"] == "My Companion"
        assert content["settings"]["userName"] == "User"

    def test_create_companion_empty_name_returns_400(self, client_with_companions):
        """POST /v1/companions with empty name returns 400."""
        resp = client_with_companions.post(
            "/v1/companions",
            json={"name": "   ", "settings": {}},
            headers=_auth_headers(),
        )
        assert resp.status_code == 400

    def test_get_companion_returns_settings(self, client_with_companions, companions_dir):
        """GET /v1/companions/{id} returns full record with settings."""
        # Create one first
        create_resp = client_with_companions.post(
            "/v1/companions",
            json={"name": "GetTest", "settings": {"systemPrompt": "Hello"}},
            headers=_auth_headers(),
        )
        assert create_resp.status_code == 200
        cid = create_resp.json()["id"]
        get_resp = client_with_companions.get(
            f"/v1/companions/{cid}",
            headers=_auth_headers(),
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == cid
        assert data["name"] == "GetTest"
        assert data.get("settings", {}).get("systemPrompt") == "Hello"

    def test_get_companion_not_found_returns_404(self, client_with_companions):
        """GET /v1/companions/{id} for missing id returns 404."""
        resp = client_with_companions.get(
            "/v1/companions/nonexistentid123",
            headers=_auth_headers(),
        )
        assert resp.status_code == 404

    def test_delete_companion_succeeds(self, client_with_companions, companions_dir):
        """DELETE /v1/companions/{id} removes file and returns success."""
        create_resp = client_with_companions.post(
            "/v1/companions",
            json={"name": "ToDelete", "settings": {}},
            headers=_auth_headers(),
        )
        assert create_resp.status_code == 200
        cid = create_resp.json()["id"]
        path = companions_dir / f"{cid}.json"
        assert path.exists()
        del_resp = client_with_companions.delete(
            f"/v1/companions/{cid}",
            headers=_auth_headers(),
        )
        assert del_resp.status_code == 200
        assert not path.exists()

    def test_delete_companion_not_found_returns_404(self, client_with_companions):
        """DELETE /v1/companions/{id} for missing id returns 404."""
        resp = client_with_companions.delete(
            "/v1/companions/nonexistentid123",
            headers=_auth_headers(),
        )
        assert resp.status_code == 404
