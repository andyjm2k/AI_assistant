import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


def _client():
    from src.servers.proxy_server import app
    return TestClient(app)


def _install_monitor_test_user(monkeypatch, username="monitor-user", password="password123"):
    from src.servers import proxy_server as ps

    monkeypatch.setattr(
        ps,
        "users_db",
        {
            username: {
                **ps.create_password_record(password),
                "created_at": "2026-06-05T00:00:00+00:00",
            }
        },
    )
    monkeypatch.setattr(ps, "save_users_db", lambda: None)
    return username, password


def test_monitor_summary_exposes_agent_run_counts():
    from src.servers import proxy_server as ps

    ps.monitor_recent_runs["autogen"].clear()
    ps.monitor_recent_runs["browser_use"].clear()
    ps.monitor_recent_runs["philosopher"].clear()
    ps.monitor_recent_runs["task_execution"].clear()
    ps.monitor_active_runs.clear()

    ps._monitor_run_start("autogen", "team-run", input_text="write a script")
    ps._monitor_run_start("browser_use", "browser-agent", input_text="open example.com")
    ps._monitor_run_start("philosopher", "contemplate", input_text="What is meaning?")
    ps._monitor_run_start("task_execution", "task-run", input_text="Write the report")

    client = _client()
    response = client.get("/monitor/summary")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["autogen_active_runs"] == 1
    assert data["browser_use_active_runs"] == 1
    assert data["philosopher_active_runs"] == 1
    assert data["task_execution_active_runs"] == 1


def test_monitor_access_accepts_catbot_auth_cookie_for_remote_request(monkeypatch):
    from src.servers import proxy_server as ps

    username, _ = _install_monitor_test_user(monkeypatch)
    token = ps.create_jwt({"sub": username})
    request = MagicMock()
    request.headers = {}
    request.cookies = {ps.AUTH_COOKIE_NAME: token}
    request.client.host = "203.0.113.10"

    ps._require_internal_or_local_access(request, "monitoring")


def test_monitor_summary_accepts_auth_cookie_for_remote_client(monkeypatch):
    from src.servers import proxy_server as ps

    username, _ = _install_monitor_test_user(monkeypatch)
    token = ps.create_jwt({"sub": username})
    with TestClient(
        ps.app,
        client=("203.0.113.10", 50000),
        cookies={ps.AUTH_COOKIE_NAME: token},
    ) as client:
        response = client.get("/monitor/summary")

    assert response.status_code == 200, response.text
    assert "uptime_seconds" in response.json()


def test_monitoring_alias_accepts_auth_cookie_for_remote_client(monkeypatch):
    from src.servers import proxy_server as ps

    username, _ = _install_monitor_test_user(monkeypatch)
    token = ps.create_jwt({"sub": username})
    with TestClient(
        ps.app,
        client=("203.0.113.10", 50000),
        cookies={ps.AUTH_COOKIE_NAME: token},
    ) as client:
        response = client.get("/monitoring")

    assert response.status_code == 200, response.text
    assert "CATBot Monitoring Dashboard" in response.text


def test_monitoring_alias_prompts_login_for_remote_client_without_auth():
    from src.servers import proxy_server as ps

    with TestClient(ps.app, client=("203.0.113.10", 50000)) as client:
        response = client.get("/monitoring")

    assert response.status_code == 401
    assert "text/html" in response.headers["content-type"]
    assert "CATBot Monitoring Login" in response.text
    assert "Authentication is required to access monitoring." in response.text
    assert 'fetch("/v1/auth/login"' in response.text


def test_monitor_detail_login_prompt_preserves_requested_target_for_remote_client():
    from src.servers import proxy_server as ps

    with TestClient(ps.app, client=("203.0.113.10", 50000)) as client:
        response = client.get("/monitoring/detail?view=browser")

    assert response.status_code == 401
    assert "CATBot Monitoring Login" in response.text
    assert "Destination: /monitoring/detail?view=browser" in response.text
    assert 'const NEXT_PATH = "/monitoring/detail?view=browser";' in response.text


def test_login_then_monitoring_alias_uses_auth_cookie(monkeypatch):
    from src.servers import proxy_server as ps

    username, password = _install_monitor_test_user(monkeypatch)
    with TestClient(ps.app, client=("203.0.113.10", 50000)) as client:
        login_response = client.post("/v1/auth/login", json={"username": username, "password": password})
        dashboard_response = client.get("/monitoring")

    assert login_response.status_code == 200, login_response.text
    assert dashboard_response.status_code == 200, dashboard_response.text
    assert "CATBot Monitoring Dashboard" in dashboard_response.text


def test_auth_me_accepts_auth_cookie_without_header(monkeypatch):
    from src.servers import proxy_server as ps

    username, _ = _install_monitor_test_user(monkeypatch)
    token = ps.create_jwt({"sub": username})
    with TestClient(ps.app, cookies={ps.AUTH_COOKIE_NAME: token}) as client:
        response = client.get("/v1/auth/me")

    assert response.status_code == 200, response.text
    assert response.json()["username"] == username


def test_monitor_data_returns_programmatic_snapshot():
    client = _client()
    response = client.get("/monitoring/data?status_limit=2&log_limit=2&include_workflows=false")

    assert response.status_code == 200, response.text
    data = response.json()
    assert "summary" in data
    assert "system_stats" in data
    assert "app_info" in data
    assert "status_events" in data
    assert "logs" in data
    assert "cpu" in data["system_stats"]
    assert "memory" in data["system_stats"]


def test_telegram_native_tools_register_monitoring_snapshot():
    from src.servers import proxy_server as ps

    tools = ps._get_telegram_native_tools_mcp_schema()
    names = {item["name"] for item in tools}

    assert "getMonitoringSnapshot" in names


def test_monitor_access_rejects_remote_request_without_catbot_auth():
    from src.servers import proxy_server as ps

    request = MagicMock()
    request.headers = {}
    request.cookies = {}
    request.client.host = "203.0.113.10"

    with pytest.raises(HTTPException) as exc_info:
        ps._require_internal_or_local_access(request, "monitoring")
    assert exc_info.value.status_code == 401


def test_monitor_data_still_returns_json_401_for_remote_client_without_auth():
    from src.servers import proxy_server as ps

    with TestClient(ps.app, client=("203.0.113.10", 50000)) as client:
        response = client.get("/monitoring/data")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"] == "Authentication is required to access monitoring."


def test_auth_login_sets_monitor_cookie(monkeypatch):
    from src.servers import proxy_server as ps

    username, password = _install_monitor_test_user(monkeypatch)
    client = _client()
    response = client.post("/v1/auth/login", json={"username": username, "password": password})

    assert response.status_code == 200, response.text
    assert response.cookies.get(ps.AUTH_COOKIE_NAME)


def test_auth_me_refreshes_monitor_cookie_from_existing_header_token(monkeypatch):
    from src.servers import proxy_server as ps

    username, _ = _install_monitor_test_user(monkeypatch)
    token = ps.create_jwt({"sub": username})
    client = _client()
    response = client.get("/v1/auth/me", headers={"X-Auth-Token": token})

    assert response.status_code == 200, response.text
    assert response.cookies.get(ps.AUTH_COOKIE_NAME) == token


def test_monitor_workflows_returns_recent_autogen_and_browser_use_activity():
    from src.servers import proxy_server as ps

    ps.monitor_recent_runs["autogen"].clear()
    ps.monitor_recent_runs["browser_use"].clear()
    ps.monitor_recent_runs["philosopher"].clear()
    ps.monitor_recent_runs["task_execution"].clear()
    ps.monitor_active_runs.clear()
    ps.monitor_browser_health_snapshot.update(
        {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "ok": True,
            "message": "Browser-use status: healthy. Running tasks: 1. Uptime: 10.0s.",
            "result": {"status": "healthy", "running_tasks": 1},
        }
    )

    autogen_run_id = ps._monitor_run_start("autogen", "team-run", input_text="draft report")
    ps._monitor_run_note(autogen_run_id, "Running AutoGen team.")
    ps._monitor_run_finish(autogen_run_id, status="completed", summary="Completed with 3 messages.")

    browser_run_id = ps._monitor_run_start("browser_use", "deep-research", input_text="research topic")
    ps._monitor_run_note(browser_run_id, "Proxying deep-research request.")
    ps._monitor_run_finish(browser_run_id, status="completed", summary="Research finished.")

    philosopher_run_id = ps._monitor_run_start("philosopher", "contemplate", input_text="What matters most?")
    ps._monitor_run_update(
        philosopher_run_id,
        summary="Running contemplation step 2 of 10.",
        metadata={
            "workflow_name": "What matters most?",
            "current_step": 2,
            "total_steps": 10,
            "phase": "contemplation",
            "conversation_id": "conv-1",
        },
    )
    ps._monitor_run_note(philosopher_run_id, "Running contemplation step 2 of 10.")
    ps._monitor_run_finish(
        philosopher_run_id,
        status="completed",
        summary="Completed philosopher workflow in 2 step(s).",
        metadata={"current_step": 2, "total_steps": 10},
    )

    task_run_id = ps._monitor_run_start("task_execution", "task-run", input_text="Draft the report")
    ps._monitor_run_update(
        task_run_id,
        summary="Task 7 step 3/20. Writing report draft.",
        metadata={
            "workflow_name": "Draft the report",
            "task_id": 7,
            "current_step": 3,
            "total_steps": 20,
            "phase": "executing",
            "user_key": "alice",
        },
    )
    ps._monitor_run_note(task_run_id, "Running task step 3 of 20.")
    ps._monitor_run_finish(
        task_run_id,
        status="paused_awaiting_feedback",
        summary="Task 7 step 3/20. Need user feedback before continuing.",
        metadata={"current_step": 3, "total_steps": 20, "task_id": 7},
    )

    client = _client()
    response = client.get("/monitor/workflows")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["autogen"]["recent"][0]["summary"] == "Completed with 3 messages."
    assert data["browser_use"]["recent"][0]["summary"] == "Research finished."
    assert data["browser_use"]["health"]["result"]["running_tasks"] == 1
    assert data["philosopher"]["recent"][0]["summary"] == "Completed philosopher workflow in 2 step(s)."
    assert data["philosopher"]["recent"][0]["metadata"]["workflow_name"] == "What matters most?"
    assert data["philosopher"]["recent"][0]["metadata"]["current_step"] == 2
    assert data["philosopher"]["recent"][0]["metadata"]["total_steps"] == 10
    assert data["task_execution"]["recent"][0]["summary"] == "Task 7 step 3/20. Need user feedback before continuing."
    assert data["task_execution"]["recent"][0]["metadata"]["task_id"] == 7
    assert data["task_execution"]["recent"][0]["metadata"]["current_step"] == 3
    assert data["task_execution"]["recent"][0]["metadata"]["total_steps"] == 20


def test_monitor_workflows_refreshes_stale_browser_health_snapshot(monkeypatch):
    from src.servers import proxy_server as ps

    stale_checked_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    ps.monitor_browser_health_snapshot.update(
        {
            "checked_at": stale_checked_at,
            "ok": False,
            "message": "Browser-use HTTP server not available.",
            "result": None,
        }
    )

    async def fake_health_check(_body):
        ps.monitor_browser_health_snapshot.update(
            {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "ok": True,
                "message": "Browser-use status: healthy. Running tasks: 0. Uptime: 12.0s.",
                "result": {"status": "healthy", "running_tasks": 0, "uptime_seconds": 12.0},
            }
        )
        return {
            "success": True,
            "message": ps.monitor_browser_health_snapshot["message"],
            "result": ps.monitor_browser_health_snapshot["result"],
        }

    monkeypatch.setattr(ps, "_do_browser_health_check", fake_health_check)

    client = _client()
    response = client.get("/monitor/workflows")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["browser_use"]["health"]["ok"] is True
    assert data["browser_use"]["health"]["result"]["status"] == "healthy"
    assert data["browser_use"]["health"]["result"]["running_tasks"] == 0


def test_monitor_dashboard_html_links_tiles_to_detail_route():
    from src.servers import proxy_server as ps

    html = (ps._PROJECT_ROOT / "docs" / "monitoring_dashboard.html").read_text(encoding="utf-8")

    assert 'href="/monitor/detail?view=autogen"' in html
    assert 'href="/monitor/detail?view=browser"' in html
    assert 'data-drill-panel' in html
    assert 'id="detail-breadcrumb"' in html
    assert 'Back to overview' in html
    assert 'if (detailLayout) detailLayout.hidden = !DETAIL_MODE;' in html
    assert 'const AUTH_TOKEN_STORAGE_KEY = "jwtAuthToken";' in html
    assert 'headers.set("X-Auth-Token", token);' in html
    assert 'credentials: "same-origin"' in html
    assert "Proxy Uptime" not in html


def test_monitor_detail_route_serves_dashboard_shell():
    client = _client()
    response = client.get("/monitor/detail?view=autogen")

    assert response.status_code == 200, response.text
    assert 'id="detail-breadcrumb"' in response.text


def test_monitor_browser_use_logs_tails_configured_file():
    from src.servers import proxy_server as ps

    log_file = ps._PROJECT_ROOT / "scratch" / f"browser-use-monitor-{secrets.token_hex(4)}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
    ps.BROWSER_USE_LOG_FILE = str(log_file)

    client = _client()
    response = client.get("/monitor/logs/browser-use?limit=2")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["available"] is True
    assert data["lines"] == ["line 2", "line 3"]
    assert data["path"] == str(log_file)
    log_file.unlink(missing_ok=True)


def test_monitor_logs_tails_proxy_log_file(monkeypatch):
    from src.servers import proxy_server as ps

    log_file = ps._PROJECT_ROOT / "scratch" / f"proxy-monitor-{secrets.token_hex(4)}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("proxy 1\nproxy 2\nproxy 3\n", encoding="utf-8")
    monkeypatch.setattr(ps, "PROXY_LOG_FILE", log_file)

    client = _client()
    response = client.get("/monitor/logs?limit=2")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["available"] is True
    assert data["lines"] == ["proxy 2", "proxy 3"]
    assert data["path"] == str(log_file)
    log_file.unlink(missing_ok=True)


def test_autogen_scratch_log_is_created_early_and_rewritten(monkeypatch):
    from src.servers import proxy_server as ps

    scratch_dir = ps._PROJECT_ROOT / "scratch" / f"autogen-monitor-{secrets.token_hex(4)}"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ps, "SCRATCH_DIR", scratch_dir)

    filename = ps._write_autogen_conversation_to_scratch(
        "draft report",
        [],
        "AutoGen run created.",
        status="running",
        progress_notes=["Loading AutoGen team."],
    )
    log_path = scratch_dir / filename
    initial_text = log_path.read_text(encoding="utf-8")

    updated_filename = ps._write_autogen_conversation_to_scratch(
        "draft report",
        [{"source": "planner", "content": "Finished the draft."}],
        "Completed successfully.",
        filename=filename,
        status="completed",
        progress_notes=["Loading AutoGen team.", "Running AutoGen team."],
    )
    final_text = log_path.read_text(encoding="utf-8")

    assert updated_filename == filename
    assert "Status: running" in initial_text
    assert "Loading AutoGen team." in initial_text
    assert "Status: completed" in final_text
    assert "Running AutoGen team." in final_text
    assert "[1] planner:" in final_text
    assert "Finished the draft." in final_text

    log_path.unlink(missing_ok=True)
    scratch_dir.rmdir()


def test_monitor_workflow_log_returns_full_autogen_conversation(monkeypatch):
    from src.servers import proxy_server as ps

    ps.monitor_recent_runs["autogen"].clear()
    ps.monitor_active_runs.clear()

    scratch_dir = ps._PROJECT_ROOT / "scratch" / f"autogen-monitor-{secrets.token_hex(4)}"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ps, "SCRATCH_DIR", scratch_dir)

    run_id = ps._monitor_run_start("autogen", "team-run", input_text="draft report")
    filename = ps._write_autogen_conversation_to_scratch(
        "draft report",
        [
            {"source": "ceo_agent", "content": "Please draft the report."},
            {"source": "writer_agent", "content": "Draft completed and ready for review."},
        ],
        "Completed successfully.",
        status="completed",
        progress_notes=["Loading AutoGen team.", "Running AutoGen team."],
    )
    ps._monitor_run_update(
        run_id,
        log_file=filename,
        log_excerpt=ps._read_monitor_log_excerpt(scratch_dir / filename),
    )
    ps._monitor_run_finish(
        run_id,
        status="completed",
        summary="Completed with 2 messages.",
        log_file=filename,
        log_excerpt=ps._read_monitor_log_excerpt(scratch_dir / filename),
    )

    client = _client()
    response = client.get(f"/monitor/workflows/log/{run_id}")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["available"] is True
    assert data["log_file"] == filename
    assert "[1] ceo_agent:" in data["content"]
    assert "Draft completed and ready for review." in data["content"]
    assert data["truncated"] is False

    log_path = scratch_dir / filename
    log_path.unlink(missing_ok=True)
    scratch_dir.rmdir()


@pytest.mark.asyncio
async def test_do_autogen_returns_full_transcript_in_response(monkeypatch):
    from src.servers import proxy_server as ps

    class DummyTeam:
        _executors_started = True
        _config_mtime = 1

        async def reset(self):
            return None

        async def run(self, task):
            assert task == "draft report"
            return SimpleNamespace(
                messages=[
                    SimpleNamespace(source="ceo_agent", content="Please draft the report."),
                    SimpleNamespace(source="writer_agent", content="Draft completed and ready for review."),
                ]
            )

    ps.monitor_recent_runs["autogen"].clear()
    ps.monitor_active_runs.clear()

    scratch_dir = ps._PROJECT_ROOT / "scratch" / f"autogen-monitor-{secrets.token_hex(4)}"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ps, "SCRATCH_DIR", scratch_dir)
    monkeypatch.setattr(ps, "AUTOGEN_AVAILABLE", True)
    monkeypatch.setattr(ps, "_autogen_team_definition_mtime", lambda: 1)
    monkeypatch.setattr(ps, "_start_code_executors", AsyncMock())
    monkeypatch.setattr(ps, "_stop_code_executors", AsyncMock())
    monkeypatch.setattr(ps, "autogen_team", DummyTeam())

    result = await ps._do_autogen("draft report")

    assert result["message_count"] == 2
    assert result["log_file"].startswith("autogen_run_")
    assert "Completed with 2 messages." in result["response"]
    assert result["log_content"] != result["response"]
    assert "[1] ceo_agent:" in result["log_content"]
    assert "Draft completed and ready for review." in result["log_content"]
    assert "Please review the above conversation" not in result["log_content"]

    log_path = scratch_dir / result["log_file"]
    log_path.unlink(missing_ok=True)
    scratch_dir.rmdir()
