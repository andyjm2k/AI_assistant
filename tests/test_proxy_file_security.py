"""
Unit and API tests for proxy server file security (path traversal and auth).
Tests resolve_scratch_path and file endpoints reject traversal/absolute paths.
Includes upload-to-drive: auth required, path restricted to scratch, audit behavior.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Project root for scratch path (conftest adds project root to path)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Import after path is set
from src.servers.proxy_server import (
    app,
    create_jwt,
    READ_ALLOWED_EXTENSIONS,
    resolve_scratch_path,
    SCRATCH_DIR,
    WRITE_ALLOWED_EXTENSIONS,
)


def _auth_headers():
    """Build Authorization header with a valid JWT so middleware allows the request."""
    token = create_jwt({"sub": "andyjm2k"})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Unit tests for resolve_scratch_path
# ---------------------------------------------------------------------------

class TestResolveScratchPath:
    """Unit tests for resolve_scratch_path path validation and containment."""

    def test_valid_relative_filename_returns_path_under_scratch(self):
        """Valid relative filename like doc.txt returns path under SCRATCH_DIR."""
        result = resolve_scratch_path("doc.txt", READ_ALLOWED_EXTENSIONS)
        assert result is not None
        assert result.suffix.lower() == ".txt"
        root = SCRATCH_DIR.resolve()
        result.resolve().relative_to(root)  # must not raise
        assert result.name == "doc.txt"

    def test_traversal_raises_400(self):
        """Path with .. raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_scratch_path("../outside.txt", READ_ALLOWED_EXTENSIONS)
        assert exc_info.value.status_code == 400
        assert "Invalid filename" in (exc_info.value.detail or "")

    def test_traversal_deep_raises_400(self):
        """Path with multiple .. raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_scratch_path("../../../.env", READ_ALLOWED_EXTENSIONS)
        assert exc_info.value.status_code == 400

    def test_absolute_path_unix_raises_400(self):
        """Unix absolute path raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_scratch_path("/etc/passwd", READ_ALLOWED_EXTENSIONS)
        assert exc_info.value.status_code == 400

    def test_absolute_path_windows_raises_400(self):
        """Windows-style path starting with backslash raises 400."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_scratch_path("\\windows\\path\\file.txt", READ_ALLOWED_EXTENSIONS)
        assert exc_info.value.status_code == 400

    def test_empty_filename_raises_400(self):
        """Empty filename raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_scratch_path("", READ_ALLOWED_EXTENSIONS)
        assert exc_info.value.status_code == 400

    def test_whitespace_only_filename_raises_400(self):
        """Whitespace-only filename raises HTTPException 400."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_scratch_path("   ", READ_ALLOWED_EXTENSIONS)
        assert exc_info.value.status_code == 400

    def test_dot_only_raises_400(self):
        """Filename '.' raises 400 (treated as invalid)."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_scratch_path(".", READ_ALLOWED_EXTENSIONS)
        assert exc_info.value.status_code == 400

    def test_disallowed_extension_raises_400(self):
        """Filename with disallowed extension (e.g. .env) raises 400."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_scratch_path("secret.env", READ_ALLOWED_EXTENSIONS)
        assert exc_info.value.status_code == 400

    def test_allowed_extension_succeeds(self):
        """Filename with allowed extension returns resolved path."""
        result = resolve_scratch_path("report.docx", READ_ALLOWED_EXTENSIONS)
        assert result.suffix.lower() == ".docx"
        SCRATCH_DIR.resolve()
        result.resolve().relative_to(SCRATCH_DIR.resolve())

    def test_scratch_py_js_html_read_allowed(self):
        """Scratch directory allows .py, .js, .html for read (file management tools)."""
        for name, ext in [("script.py", ".py"), ("app.js", ".js"), ("page.html", ".html")]:
            result = resolve_scratch_path(name, READ_ALLOWED_EXTENSIONS)
            assert result.suffix.lower() == ext
            result.resolve().relative_to(SCRATCH_DIR.resolve())

    def test_scratch_py_js_html_write_allowed(self):
        """Scratch directory allows .py, .js, .html for write (file management tools)."""
        for name, ext in [("script.py", ".py"), ("app.js", ".js"), ("page.html", ".html")]:
            result = resolve_scratch_path(name, WRITE_ALLOWED_EXTENSIONS)
            assert result.suffix.lower() == ext
            result.resolve().relative_to(SCRATCH_DIR.resolve())

    def test_resolve_without_extension_allowlist_allows_any_extension(self):
        """When allowed_extensions is None, any extension is accepted (containment still enforced)."""
        # Still reject traversal
        with pytest.raises(HTTPException):
            resolve_scratch_path("../other.txt", None)
        # Accept a path that would be invalid for read (e.g. .py) when allowlist is None
        result = resolve_scratch_path("script.py", None)
        assert result.suffix.lower() == ".py"
        result.resolve().relative_to(SCRATCH_DIR.resolve())


# ---------------------------------------------------------------------------
# API tests (traversal and valid request)
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_auth():
    """TestClient; requests must include Authorization header with valid JWT (middleware runs first)."""
    with TestClient(app) as c:
        yield c


class TestFileApiSecurity:
    """API tests: file endpoints return 400 for path traversal and accept valid paths."""

    def test_read_traversal_returns_400(self, client_with_auth):
        """POST /v1/files/read with traversal filename returns 400."""
        response = client_with_auth.post(
            "/v1/files/read",
            json={"filename": "../../../.env"},
            headers=_auth_headers(),
        )
        assert response.status_code == 400

    def test_write_traversal_returns_400(self, client_with_auth):
        """POST /v1/files/write with traversal filename returns 400."""
        response = client_with_auth.post(
            "/v1/files/write",
            json={"filename": "../../../etc/malicious.txt", "content": "x", "format": "txt"},
            headers=_auth_headers(),
        )
        assert response.status_code == 400

    def test_delete_traversal_returns_400(self, client_with_auth):
        """DELETE /v1/files/delete with traversal path returns 400."""
        # Percent-encode ".." so the path is not normalized; filename param becomes ".."
        response = client_with_auth.request(
            "DELETE",
            "/v1/files/delete/%2e%2e",
            headers=_auth_headers(),
        )
        assert response.status_code == 400

    def test_read_valid_filename_not_found_returns_404_or_failure(self, client_with_auth):
        """POST /v1/files/read with valid filename but missing file returns success=False (no 400)."""
        response = client_with_auth.post(
            "/v1/files/read",
            json={"filename": "nonexistent_12345.txt"},
            headers=_auth_headers(),
        )
        # Path is valid so we get 200 with success=False, not 400
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is False
        assert "not found" in data.get("message", "").lower() or "file" in data.get("message", "").lower()

    def test_read_valid_filename_existing_file_succeeds(self, client_with_auth):
        """POST /v1/files/read with valid filename and existing file in scratch returns success."""
        # Create scratch dir and a test file if needed (project root / scratch)
        scratch = PROJECT_ROOT / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        test_file = scratch / "security_test_read_me.txt"
        test_file.write_text("hello", encoding="utf-8")
        try:
            response = client_with_auth.post(
                "/v1/files/read",
                json={"filename": "security_test_read_me.txt"},
                headers=_auth_headers(),
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True
            assert data.get("data", {}).get("content") == "hello"
        finally:
            if test_file.exists():
                test_file.unlink()


# ---------------------------------------------------------------------------
# Upload-to-Drive security and behavior tests
# ---------------------------------------------------------------------------

class TestUploadToDriveSecurity:
    """API tests: upload-to-drive requires auth and rejects invalid paths."""

    def test_upload_to_drive_without_auth_returns_401(self, client_with_auth):
        """POST /v1/proxy/upload-to-drive without Authorization returns 401."""
        response = client_with_auth.post(
            "/v1/proxy/upload-to-drive",
            data={"filePath": "any.txt", "folderId": "fake"},
            headers={},
        )
        assert response.status_code == 401

    def test_upload_to_drive_traversal_returns_400(self, client_with_auth):
        """POST /v1/proxy/upload-to-drive with traversal filePath returns 400."""
        response = client_with_auth.post(
            "/v1/proxy/upload-to-drive",
            data={"filePath": "../../../.env", "folderId": "fake"},
            headers=_auth_headers(),
        )
        assert response.status_code == 400

    def test_upload_to_drive_absolute_unix_returns_400(self, client_with_auth):
        """POST /v1/proxy/upload-to-drive with absolute Unix path returns 400."""
        response = client_with_auth.post(
            "/v1/proxy/upload-to-drive",
            data={"filePath": "/etc/passwd", "folderId": "fake"},
            headers=_auth_headers(),
        )
        assert response.status_code == 400

    def test_upload_to_drive_absolute_windows_returns_400(self, client_with_auth):
        """POST /v1/proxy/upload-to-drive with Windows-style absolute path returns 400."""
        response = client_with_auth.post(
            "/v1/proxy/upload-to-drive",
            data={"filePath": "\\\\windows\\path\\file.txt", "folderId": "fake"},
            headers=_auth_headers(),
        )
        assert response.status_code == 400

    def test_upload_to_drive_disallowed_extension_returns_400(self, client_with_auth):
        """POST /v1/proxy/upload-to-drive with disallowed extension (.env) returns 400."""
        # .env is not in DRIVE_UPLOAD_EXTENSIONS
        response = client_with_auth.post(
            "/v1/proxy/upload-to-drive",
            data={"filePath": "secret.env", "folderId": "fake"},
            headers=_auth_headers(),
        )
        assert response.status_code == 400

    def test_upload_to_drive_valid_scratch_file_succeeds_with_mocked_drive(self, client_with_auth, monkeypatch):
        """POST /v1/proxy/upload-to-drive with valid scratch filename returns 200 and fileId when Drive is mocked."""
        # Skip if Google API client is not installed (patch would import it)
        pytest.importorskip("googleapiclient.discovery")
        # Ensure scratch dir exists and create a test file
        SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        test_file = SCRATCH_DIR / "security_test_drive_upload.txt"
        test_file.write_text("content", encoding="utf-8")
        # Set minimal env so handler passes credential check (private_key must contain \n for parsing)
        monkeypatch.setenv("GOOGLE_DRIVE_PROJECT_ID", "test-project")
        monkeypatch.setenv("GOOGLE_DRIVE_PRIVATE_KEY_ID", "test-key-id")
        monkeypatch.setenv("GOOGLE_DRIVE_PRIVATE_KEY", "-----BEGIN KEY-----\nline\n-----END KEY-----")
        monkeypatch.setenv("GOOGLE_DRIVE_CLIENT_EMAIL", "test@project.iam.gserviceaccount.com")
        monkeypatch.setenv("GOOGLE_DRIVE_FOLDER_ID", "fake-folder-id")
        # Mock Drive API: build() returns a mock whose files().create().execute() returns success payload
        mock_execute = MagicMock(return_value={"id": "drive-file-123", "name": "security_test_drive_upload.txt", "webViewLink": "https://drive.google.com/file/d/123"})
        mock_create = MagicMock(return_value=MagicMock(execute=mock_execute))
        mock_files = MagicMock(return_value=MagicMock(create=mock_create))
        mock_drive = MagicMock(files=mock_files)
        try:
            with patch("googleapiclient.discovery.build", return_value=mock_drive):
                response = client_with_auth.post(
                    "/v1/proxy/upload-to-drive",
                    data={"filePath": "security_test_drive_upload.txt", "folderId": "fake-folder-id"},
                    headers=_auth_headers(),
                )
            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True
            assert data.get("fileId") == "drive-file-123"
        finally:
            if test_file.exists():
                test_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
