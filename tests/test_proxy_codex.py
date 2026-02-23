from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def _client():
    from src.servers.proxy_server import app
    return TestClient(app)


def _auth_headers():
    from src.servers.proxy_server import create_jwt, users_db
    users_db.setdefault("codex-user", {"created_at": "2026-01-01T00:00:00Z"})
    token = create_jwt({"sub": "codex-user"})
    return {"Authorization": f"Bearer {token}"}


def test_codex_requires_auth():
    client = _client()
    response = client.post("/v1/proxy/codex", json={"prompt": "test"})
    assert response.status_code in (401, 403)


def test_codex_endpoint_returns_summary_file():
    client = _client()
    fake_result = {
        "success": True,
        "summaryFile": "codex_run_2026-01-01_00-00-00_abcd1234.txt",
        "exitCode": 0,
        "timedOut": False,
        "durationMs": 1234,
        "stdout": "ok",
        "stderr": "",
    }
    with patch("src.servers.proxy_server._run_codex_cli", new=AsyncMock(return_value=fake_result)):
        response = client.post("/v1/proxy/codex", json={"prompt": "test"}, headers=_auth_headers())
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("summaryFile") == fake_result["summaryFile"]
    assert data.get("success") is True


def test_codex_summary_writer_creates_file():
    from src.servers import proxy_server

    original = proxy_server.SCRATCH_DIR
    scratch_test_dir = original / "test_codex_summary"
    scratch_test_dir.mkdir(parents=True, exist_ok=True)
    try:
        proxy_server.SCRATCH_DIR = scratch_test_dir
        filename = proxy_server._write_codex_summary_to_scratch(
            prompt="hello",
            command=["codex", "exec"],
            exit_code=0,
            stdout="stdout",
            stderr="stderr",
            duration_ms=100,
            timed_out=False,
        )
        path = scratch_test_dir / filename
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Codex CLI execution summary" in content
        assert "hello" in content
    finally:
        proxy_server.SCRATCH_DIR = original
