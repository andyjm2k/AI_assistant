"""
Unit and API tests for proxy server file security (path traversal and auth).
Tests resolve_scratch_path and file endpoints reject traversal/absolute paths.
Includes upload-to-drive: auth required, path restricted to scratch, audit behavior.
"""

import os
import sys
import shutil
import uuid
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

    def test_csv_extension_allowed_for_read_and_write(self):
        """Scratch directory allows .csv for read/write so fetchNews exports work in Telegram."""
        read_result = resolve_scratch_path("news.csv", READ_ALLOWED_EXTENSIONS)
        write_result = resolve_scratch_path("news.csv", WRITE_ALLOWED_EXTENSIONS)
        assert read_result.suffix.lower() == ".csv"
        assert write_result.suffix.lower() == ".csv"
        read_result.resolve().relative_to(SCRATCH_DIR.resolve())
        write_result.resolve().relative_to(SCRATCH_DIR.resolve())

    def test_resolve_without_extension_allowlist_allows_any_extension(self):
        """When allowed_extensions is None, any extension is accepted (containment still enforced)."""
        # Still reject traversal
        with pytest.raises(HTTPException):
            resolve_scratch_path("../other.txt", None)
        # Accept a path that would be invalid for read (e.g. .py) when allowlist is None
        result = resolve_scratch_path("script.py", None)
        assert result.suffix.lower() == ".py"
        result.resolve().relative_to(SCRATCH_DIR.resolve())

    def test_scratch_prefixed_paths_resolve_inside_workspace(self):
        """Paths prefixed with scratch/ or scratch\\ resolve correctly under SCRATCH_DIR."""
        unix_style = resolve_scratch_path("scratch/images/sample.png", READ_ALLOWED_EXTENSIONS)
        windows_style = resolve_scratch_path(r"scratch\images\sample.png", READ_ALLOWED_EXTENSIONS)
        assert unix_style.resolve().relative_to(SCRATCH_DIR.resolve()) == Path("images") / "sample.png"
        assert windows_style.resolve().relative_to(SCRATCH_DIR.resolve()) == Path("images") / "sample.png"


class TestListFilesInternal:
    """Unit tests for internal scratch listing robustness and recursion."""

    @pytest.mark.asyncio
    async def test_recursive_listing_includes_subdirectory_files(self, monkeypatch):
        """_list_files_internal(recursive=True) should include nested file names."""
        from src.servers import proxy_server as ps

        scratch = PROJECT_ROOT / "scratch" / f"proxy-list-test-{uuid.uuid4().hex}"
        try:
            (scratch / "images" / "2026").mkdir(parents=True, exist_ok=True)
            (scratch / "root.txt").write_text("root", encoding="utf-8")
            (scratch / "images" / "a.png").write_text("a", encoding="utf-8")
            (scratch / "images" / "2026" / "b.png").write_text("b", encoding="utf-8")

            monkeypatch.setattr(ps, "SCRATCH_DIR", scratch)

            non_recursive = await ps._list_files_internal(path="", recursive=False)
            assert non_recursive.get("success") is True
            non_recursive_names = {item.get("name") for item in non_recursive.get("files", [])}
            assert "root.txt" in non_recursive_names
            assert "images" in non_recursive_names
            assert "images/a.png" not in non_recursive_names

            recursive = await ps._list_files_internal(path="", recursive=True)
            assert recursive.get("success") is True
            recursive_names = {item.get("name") for item in recursive.get("files", [])}
            assert "root.txt" in recursive_names
            assert "images/a.png" in recursive_names
            assert "images/2026/b.png" in recursive_names
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_listing_skips_entries_with_stat_errors(self, monkeypatch):
        """_list_files_internal should continue when one entry cannot be stat'ed."""
        from src.servers import proxy_server as ps

        scratch = PROJECT_ROOT / "scratch" / f"proxy-list-test-{uuid.uuid4().hex}"
        try:
            scratch.mkdir(parents=True, exist_ok=True)
            (scratch / "good.txt").write_text("ok", encoding="utf-8")
            (scratch / "bad.txt").write_text("nope", encoding="utf-8")

            monkeypatch.setattr(ps, "SCRATCH_DIR", scratch)

            original_stat = Path.stat

            def _patched_stat(path_obj, *args, **kwargs):
                if path_obj.name == "bad.txt":
                    raise PermissionError("denied")
                return original_stat(path_obj, *args, **kwargs)

            monkeypatch.setattr(Path, "stat", _patched_stat)

            out = await ps._list_files_internal(path="", recursive=False)
            assert out.get("success") is True
            names = {item.get("name") for item in out.get("files", [])}
            assert "good.txt" in names
            assert "bad.txt" not in names
            assert int(out.get("skipped_count", 0) or 0) >= 1
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_listing_accepts_scratch_prefixed_paths(self, monkeypatch):
        """_list_files_internal should accept path values like scratch/images and scratch\\images."""
        from src.servers import proxy_server as ps

        scratch = PROJECT_ROOT / "scratch" / f"proxy-list-test-{uuid.uuid4().hex}"
        try:
            (scratch / "images").mkdir(parents=True, exist_ok=True)
            (scratch / "images" / "a.png").write_text("a", encoding="utf-8")

            monkeypatch.setattr(ps, "SCRATCH_DIR", scratch)

            unix_style = await ps._list_files_internal(path="scratch/images", recursive=False)
            windows_style = await ps._list_files_internal(path=r"scratch\images", recursive=False)

            assert unix_style.get("success") is True
            assert windows_style.get("success") is True

            unix_names = {item.get("name") for item in unix_style.get("files", [])}
            windows_names = {item.get("name") for item in windows_style.get("files", [])}
            assert "images/a.png" in unix_names
            assert "images/a.png" in windows_names
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_listing_uses_stable_order_and_supports_pagination(self, monkeypatch):
        """_list_files_internal should sort by relative path and support deterministic paging."""
        from src.servers import proxy_server as ps

        scratch = PROJECT_ROOT / "scratch" / f"proxy-list-test-{uuid.uuid4().hex}"
        try:
            (scratch / "folder").mkdir(parents=True, exist_ok=True)
            (scratch / "b.txt").write_text("b", encoding="utf-8")
            (scratch / "a.txt").write_text("a", encoding="utf-8")

            monkeypatch.setattr(ps, "SCRATCH_DIR", scratch)

            out = await ps._list_files_internal(path="", recursive=False, offset=1, max_entries=2)
            assert out.get("success") is True
            assert out.get("total_count") == 3
            assert out.get("returned_count") == 2
            assert out.get("has_more") is False
            assert out.get("offset") == 1
            assert [item.get("name") for item in out.get("files", [])] == ["a.txt", "b.txt"]
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_search_files_internal_finds_content_matches(self, monkeypatch):
        """_search_files_internal should search file names and text content."""
        from src.servers import proxy_server as ps

        scratch = PROJECT_ROOT / "scratch" / f"proxy-search-test-{uuid.uuid4().hex}"
        try:
            (scratch / "docs").mkdir(parents=True, exist_ok=True)
            (scratch / "docs" / "notes.txt").write_text("alpha roadmap\nbeta\n", encoding="utf-8")
            (scratch / "docs" / "other.txt").write_text("gamma\n", encoding="utf-8")
            monkeypatch.setattr(ps, "SCRATCH_DIR", scratch)

            out = await ps._search_files_internal("alpha", path="docs", recursive=True, max_results=10)
            assert out.get("success") is True
            assert out.get("total_matches") == 1
            match = out.get("matches", [])[0]
            assert match.get("relative_path") == "docs/notes.txt"
            assert match.get("line_number") == 1
            assert "alpha" in match.get("excerpt", "").lower()
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


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

    def test_read_api_supports_line_ranges(self, client_with_auth):
        """POST /v1/files/read should support partial reads with line numbers."""
        scratch = PROJECT_ROOT / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        test_file = scratch / "security_test_partial.txt"
        test_file.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")
        try:
            response = client_with_auth.post(
                "/v1/files/read",
                json={
                    "path": "security_test_partial.txt",
                    "start_line": 2,
                    "end_line": 3,
                    "include_line_numbers": True,
                },
                headers=_auth_headers(),
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True
            assert data.get("data", {}).get("content") == "2: two\n3: three"
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_write_and_read_csv_file_succeeds(self, client_with_auth):
        """POST /v1/files/write and /v1/files/read should support CSV scratch files."""
        scratch = PROJECT_ROOT / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        test_file = scratch / "security_test_news.csv"
        csv_content = 'Title,URL\n"One","https://example.com/one"'
        try:
            write_response = client_with_auth.post(
                "/v1/files/write",
                json={"filename": "security_test_news.csv", "content": csv_content, "format": "csv"},
                headers=_auth_headers(),
            )
            assert write_response.status_code == 200
            write_data = write_response.json()
            assert write_data.get("success") is True
            assert test_file.exists()

            read_response = client_with_auth.post(
                "/v1/files/read",
                json={"filename": "security_test_news.csv"},
                headers=_auth_headers(),
            )
            assert read_response.status_code == 200
            read_data = read_response.json()
            assert read_data.get("success") is True
            assert read_data.get("data", {}).get("content") == csv_content
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_list_files_api_accepts_scratch_prefixed_paths(self, client_with_auth, monkeypatch):
        """GET /v1/files/list should accept scratch/ and scratch\\ path prefixes."""
        from src.servers import proxy_server as ps

        scratch = PROJECT_ROOT / "scratch" / f"proxy-list-api-{uuid.uuid4().hex}"
        try:
            (scratch / "images").mkdir(parents=True, exist_ok=True)
            (scratch / "images" / "a.png").write_text("a", encoding="utf-8")
            monkeypatch.setattr(ps, "SCRATCH_DIR", scratch)

            unix_response = client_with_auth.get(
                "/v1/files/list",
                params={"path": "scratch/images"},
                headers=_auth_headers(),
            )
            windows_response = client_with_auth.get(
                "/v1/files/list",
                params={"path": r"scratch\images"},
                headers=_auth_headers(),
            )

            assert unix_response.status_code == 200
            assert windows_response.status_code == 200
            unix_data = unix_response.json()
            windows_data = windows_response.json()
            assert unix_data.get("success") is True
            assert windows_data.get("success") is True
            assert {item.get("name") for item in unix_data.get("files", [])} == {"images/a.png"}
            assert {item.get("name") for item in windows_data.get("files", [])} == {"images/a.png"}
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_list_files_api_recursive_mode_includes_nested_files(self, client_with_auth, monkeypatch):
        """GET /v1/files/list should honor recursive=true for nested directories."""
        from src.servers import proxy_server as ps

        scratch = PROJECT_ROOT / "scratch" / f"proxy-list-api-{uuid.uuid4().hex}"
        try:
            (scratch / "images" / "2026").mkdir(parents=True, exist_ok=True)
            (scratch / "images" / "a.png").write_text("a", encoding="utf-8")
            (scratch / "images" / "2026" / "b.png").write_text("b", encoding="utf-8")
            monkeypatch.setattr(ps, "SCRATCH_DIR", scratch)

            non_recursive_response = client_with_auth.get(
                "/v1/files/list",
                params={"path": "images"},
                headers=_auth_headers(),
            )
            recursive_response = client_with_auth.get(
                "/v1/files/list",
                params={"path": "images", "recursive": "true"},
                headers=_auth_headers(),
            )

            assert non_recursive_response.status_code == 200
            assert recursive_response.status_code == 200
            non_recursive_data = non_recursive_response.json()
            recursive_data = recursive_response.json()
            assert non_recursive_data.get("success") is True
            assert recursive_data.get("success") is True

            non_recursive_names = {item.get("name") for item in non_recursive_data.get("files", [])}
            recursive_names = {item.get("name") for item in recursive_data.get("files", [])}
            assert "images/a.png" in non_recursive_names
            assert "images/2026" in non_recursive_names
            assert "images/2026/b.png" not in non_recursive_names
            assert "images/2026/b.png" in recursive_names
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_list_files_api_supports_offset_and_max_entries(self, client_with_auth, monkeypatch):
        """GET /v1/files/list should expose deterministic pagination metadata."""
        from src.servers import proxy_server as ps

        scratch = PROJECT_ROOT / "scratch" / f"proxy-list-api-{uuid.uuid4().hex}"
        try:
            scratch.mkdir(parents=True, exist_ok=True)
            (scratch / "c.txt").write_text("c", encoding="utf-8")
            (scratch / "a.txt").write_text("a", encoding="utf-8")
            (scratch / "b.txt").write_text("b", encoding="utf-8")
            monkeypatch.setattr(ps, "SCRATCH_DIR", scratch)

            response = client_with_auth.get(
                "/v1/files/list",
                params={"offset": "1", "max_entries": "1"},
                headers=_auth_headers(),
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True
            assert data.get("total_count") == 3
            assert data.get("returned_count") == 1
            assert data.get("has_more") is True
            assert data.get("next_offset") == 2
            assert [item.get("name") for item in data.get("files", [])] == ["b.txt"]
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_search_files_api_returns_matches(self, client_with_auth, monkeypatch):
        """GET /v1/files/search should return matching files and snippets."""
        from src.servers import proxy_server as ps

        scratch = PROJECT_ROOT / "scratch" / f"proxy-search-api-{uuid.uuid4().hex}"
        try:
            (scratch / "docs").mkdir(parents=True, exist_ok=True)
            (scratch / "docs" / "notes.txt").write_text("alpha roadmap\n", encoding="utf-8")
            monkeypatch.setattr(ps, "SCRATCH_DIR", scratch)

            response = client_with_auth.get(
                "/v1/files/search",
                params={"query": "alpha", "path": "docs"},
                headers=_auth_headers(),
            )

            assert response.status_code == 200
            data = response.json()
            assert data.get("success") is True
            assert data.get("total_matches") == 1
            assert data.get("matches", [])[0].get("relative_path") == "docs/notes.txt"
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


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
