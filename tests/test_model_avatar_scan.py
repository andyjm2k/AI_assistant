"""
Unit tests for model_avatar scan: scan_model_avatar_dir() and GET /v1/model-avatar/scan.
Uses a temporary directory so the real model_avatar tree is not touched.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _auth_headers():
    """Build Authorization header with a valid JWT for protected proxy routes."""
    from src.servers.proxy_server import create_jwt
    token = create_jwt({"sub": "andyjm2k"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def temp_model_avatar(tmp_path):
    """
    Create a temporary model_avatar tree with *.model3.json and *.vrm files in subdirs.
    Returns the temp project root (tmp_path) so model_avatar lives at tmp_path / "model_avatar".
    """
    avatar = tmp_path / "model_avatar"
    avatar.mkdir(exist_ok=True)
    # One Live2D at top level
    (avatar / "Top.model3.json").write_text("{}")
    # Subdir with Live2D and VRM
    sub1 = avatar / "SubA"
    sub1.mkdir(exist_ok=True)
    (sub1 / "A.model3.json").write_text("{}")
    (sub1 / "A.vrm").write_bytes(b"vrm")
    # Nested subdir
    sub2 = avatar / "SubB" / "Nested"
    sub2.mkdir(parents=True, exist_ok=True)
    (sub2 / "Nested.vrm").write_bytes(b"vrm")
    (sub2 / "Nested.model3.json").write_text("{}")
    return tmp_path


class TestScanModelAvatarDir:
    """Unit tests for scan_model_avatar_dir() with a temporary directory."""

    def test_returns_live2d_and_vrm_lists_with_dot_slash_prefix(self, temp_model_avatar):
        """Discovered paths use ./ prefix and forward slashes."""
        with patch("src.servers.proxy_server._PROJECT_ROOT", temp_model_avatar):
            from src.servers.proxy_server import scan_model_avatar_dir
            result = scan_model_avatar_dir()
        assert "live2d" in result
        assert "vrm" in result
        assert isinstance(result["live2d"], list)
        assert isinstance(result["vrm"], list)
        for path in result["live2d"]:
            assert path.startswith("./"), f"Live2D path should start with ./: {path}"
            assert path.endswith(".model3.json"), f"Live2D path should end with .model3.json: {path}"
            assert "\\" not in path, f"Path should use forward slashes: {path}"
        for path in result["vrm"]:
            assert path.startswith("./"), f"VRM path should start with ./: {path}"
            assert path.endswith(".vrm"), f"VRM path should end with .vrm: {path}"
            assert "\\" not in path, f"Path should use forward slashes: {path}"

    def test_finds_all_model_files_in_subdirs(self, temp_model_avatar):
        """All *.model3.json and *.vrm under model_avatar are listed."""
        with patch("src.servers.proxy_server._PROJECT_ROOT", temp_model_avatar):
            from src.servers.proxy_server import scan_model_avatar_dir
            result = scan_model_avatar_dir()
        live2d = set(result["live2d"])
        vrm = set(result["vrm"])
        assert "./model_avatar/Top.model3.json" in live2d
        assert "./model_avatar/SubA/A.model3.json" in live2d
        assert "./model_avatar/SubB/Nested/Nested.model3.json" in live2d
        assert len(live2d) == 3
        assert "./model_avatar/SubA/A.vrm" in vrm
        assert "./model_avatar/SubB/Nested/Nested.vrm" in vrm
        assert len(vrm) == 2

    def test_missing_model_avatar_dir_returns_empty_lists_and_message(self, tmp_path):
        """When model_avatar does not exist, returns empty lists and a message."""
        with patch("src.servers.proxy_server._PROJECT_ROOT", tmp_path):
            from src.servers.proxy_server import scan_model_avatar_dir
            result = scan_model_avatar_dir()
        assert result["live2d"] == []
        assert result["vrm"] == []
        assert "message" in result
        assert "not found" in result["message"].lower()


class TestModelAvatarScanEndpoint:
    """API tests for GET /v1/model-avatar/scan (auth and response shape)."""

    def test_scan_endpoint_returns_200_and_lists_with_auth(self, temp_model_avatar):
        """GET /v1/model-avatar/scan with valid auth returns live2d and vrm arrays."""
        with patch("src.servers.proxy_server._PROJECT_ROOT", temp_model_avatar):
            from src.servers.proxy_server import app
            with TestClient(app) as client:
                res = client.get("/v1/model-avatar/scan", headers=_auth_headers())
        assert res.status_code == 200
        data = res.json()
        assert "live2d" in data
        assert "vrm" in data
        assert len(data["live2d"]) == 3
        assert len(data["vrm"]) == 2

    def test_scan_endpoint_requires_auth(self, temp_model_avatar):
        """GET /v1/model-avatar/scan without auth returns 401."""
        with patch("src.servers.proxy_server._PROJECT_ROOT", temp_model_avatar):
            from src.servers.proxy_server import app
            with TestClient(app) as client:
                res = client.get("/v1/model-avatar/scan")
        assert res.status_code == 401
