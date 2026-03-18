import shutil
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
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


def test_codex_endpoint_accepts_autogen_team_secret(monkeypatch):
    from src.servers import proxy_server

    monkeypatch.setattr(proxy_server, "AUTOGEN_TEAM_SECRET", "team-secret")
    client = TestClient(proxy_server.app)
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
        response = client.post("/v1/proxy/codex", json={"prompt": "test"}, headers={"X-Agent-Secret": "team-secret"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("summaryFile") == fake_result["summaryFile"]
    assert data.get("success") is True


def test_codex_endpoint_user_auth_uses_project_root_workspace():
    client = _client()
    fake_result = {
        "success": True,
        "summaryFile": "codex_run_2026-01-01_00-00-00_abcd1234.txt",
        "exitCode": 0,
        "timedOut": False,
        "durationMs": 1234,
        "stdout": "ok",
        "stderr": "",
        "workspaceDir": "C:/Users/pc/CATBot",
        "workspaceMode": "project_root",
    }
    mock_run = AsyncMock(return_value=fake_result)
    with patch("src.servers.proxy_server._run_codex_cli", new=mock_run):
        response = client.post("/v1/proxy/codex", json={"prompt": "test"}, headers=_auth_headers())
    assert response.status_code == 200, response.text
    assert mock_run.await_args.args == ("test",)
    assert mock_run.await_args.kwargs.get("isolated_workspace") is False


def test_codex_endpoint_autogen_secret_uses_isolated_workspace(monkeypatch):
    from src.servers import proxy_server

    monkeypatch.setattr(proxy_server, "AUTOGEN_TEAM_SECRET", "team-secret")
    client = TestClient(proxy_server.app)
    fake_result = {
        "success": True,
        "summaryFile": "codex_run_2026-01-01_00-00-00_abcd1234.txt",
        "exitCode": 0,
        "timedOut": False,
        "durationMs": 1234,
        "stdout": "ok",
        "stderr": "",
        "workspaceDir": "C:/Users/pc/CATBot/scratch/autogen/codex_run",
        "workspaceMode": "scratch_autogen_empty",
    }
    mock_run = AsyncMock(return_value=fake_result)
    with patch("src.servers.proxy_server._run_codex_cli", new=mock_run):
        response = client.post("/v1/proxy/codex", json={"prompt": "test"}, headers={"X-Agent-Secret": "team-secret"})
    assert response.status_code == 200, response.text
    assert mock_run.await_args.args == ("test",)
    assert mock_run.await_args.kwargs.get("isolated_workspace") is True


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
            workspace_dir="C:/Users/pc/CATBot/scratch/autogen/codex_run_example",
            workspace_mode="scratch_autogen_empty",
        )
        path = scratch_test_dir / filename
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Codex CLI execution summary" in content
        assert "hello" in content
        assert "Workspace mode: scratch_autogen_empty" in content
        assert "Workspace dir: C:/Users/pc/CATBot/scratch/autogen/codex_run_example" in content
    finally:
        proxy_server.SCRATCH_DIR = original


@pytest.mark.asyncio
async def test_run_codex_cli_uses_isolated_autogen_workspace(monkeypatch):
    from src.servers import proxy_server

    test_root = Path("scratch") / f"test_codex_isolated_{uuid.uuid4().hex}"
    project_root = test_root / "project"
    scratch_dir = project_root / "scratch"
    try:
        (project_root / "src").mkdir(parents=True, exist_ok=True)
        (project_root / "src" / "sample.py").write_text("print('hello')\n", encoding="utf-8")
        (project_root / ".git").mkdir(parents=True, exist_ok=True)
        (project_root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
        scratch_dir.mkdir(parents=True, exist_ok=True)
        (scratch_dir / "should_not_copy.txt").write_text("skip", encoding="utf-8")

        monkeypatch.setattr(proxy_server, "_PROJECT_ROOT", project_root)
        monkeypatch.setattr(proxy_server, "SCRATCH_DIR", scratch_dir)
        monkeypatch.setattr(proxy_server, "CODEX_ENABLED", True)
        monkeypatch.setattr(proxy_server, "CODEX_CLI_PATH", "codex")
        monkeypatch.setattr(proxy_server, "CODEX_SANDBOX_MODE", "workspace-write")
        monkeypatch.setattr(proxy_server, "CODEX_APPROVAL_POLICY", "never")
        monkeypatch.setattr(proxy_server, "CODEX_ENABLE_SEARCH", False)
        monkeypatch.setattr(proxy_server, "CODEX_TIMEOUT_SECONDS", 60)
        monkeypatch.setattr(proxy_server, "CODEX_JSON_EVENTS", False)
        monkeypatch.setattr(proxy_server, "CODEX_OUTPUT_LAST_MESSAGE", False)

        captured: dict[str, object] = {}

        class DummyProc:
            returncode = 0

            async def communicate(self):
                return (b"ok", b"")

            def kill(self):
                self.returncode = -9

        async def fake_subprocess_exec(*cmd, cwd=None, stdout=None, stderr=None):
            captured["cmd"] = list(cmd)
            captured["cwd"] = cwd
            return DummyProc()

        monkeypatch.setattr(proxy_server.asyncio, "create_subprocess_exec", fake_subprocess_exec)

        result = await proxy_server._run_codex_cli("make a change", isolated_workspace=True)

        workspace_dir = Path(str(result["workspaceDir"]))
        assert result["workspaceMode"] == "scratch_autogen_empty"
        assert workspace_dir.parent == scratch_dir / "autogen"
        assert workspace_dir.exists()
        assert captured["cwd"] == str(workspace_dir)
        command = captured["cmd"]
        assert isinstance(command, list)
        assert "-C" in command
        assert command[command.index("-C") + 1] == str(workspace_dir)
        assert not (workspace_dir / "src").exists()
        assert not (workspace_dir / "scratch").exists()
        assert not (workspace_dir / ".git").exists()
        readme = workspace_dir / "AUTOGEN_WORKSPACE_README.txt"
        assert readme.exists()
        assert "empty isolated directory" in readme.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(test_root, ignore_errors=True)
