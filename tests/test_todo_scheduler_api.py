"""
Tests for scheduler-focused todo API behavior in src.servers.proxy_server.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def _client():
    from src.servers import proxy_server as ps

    client = TestClient(ps.app)
    return client, ps


def _auth_headers(client: TestClient) -> dict:
    username = "todo_scheduler_test_user"
    password = "todo_scheduler_test_password_123"
    signup = client.post("/v1/auth/signup", json={"username": username, "password": password})
    if signup.status_code == 200:
        token = signup.json()["access_token"]
    else:
        login = client.post("/v1/auth/login", json={"username": username, "password": password})
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _example_scheduler_meta():
    now = datetime.now(timezone.utc)
    return {
        "tasks": ["Task A", "Task B", "Task C"],
        "task_items": [
            {
                "id": "a",
                "description": "Task A",
                "next_run_at": None,
                "scheduled_for": None,
                "recurrence": None,
            },
            {
                "id": "b",
                "description": "Task B",
                "next_run_at": (now - timedelta(minutes=10)).isoformat(),
                "scheduled_for": (now - timedelta(hours=1)).isoformat(),
                "recurrence": None,
            },
            {
                "id": "c",
                "description": "Task C",
                "next_run_at": (now + timedelta(hours=3)).isoformat(),
                "scheduled_for": (now + timedelta(hours=3)).isoformat(),
                "recurrence": {"frequency": "daily", "interval": 1},
            },
        ],
        "updated_at": now.isoformat(),
    }


def test_build_todo_list_response_due_only_preserves_original_task_ids():
    from src.servers import proxy_server as ps

    due_only = ps._build_todo_list_response(_example_scheduler_meta(), due_only=True)
    assert due_only.tasks == ["Task B"]
    assert len(due_only.taskItems) == 1
    assert due_only.taskItems[0].taskId == 2
    assert due_only.taskItems[0].taskDescription == "Task B"


def test_todo_due_endpoint_returns_due_tasks_with_stable_ids():
    client, ps = _client()
    headers = _auth_headers(client)
    mock_store = MagicMock()
    mock_store.load_tasks_with_meta.return_value = _example_scheduler_meta()

    original_available = ps.TODO_STORE_AVAILABLE
    original_store = ps._todo_store
    ps.TODO_STORE_AVAILABLE = True
    ps._todo_store = mock_store
    try:
        response = client.get("/v1/todo/due", headers=headers)
    finally:
        ps.TODO_STORE_AVAILABLE = original_available
        ps._todo_store = original_store

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tasks"] == ["Task B"]
    assert len(body["taskItems"]) == 1
    assert body["taskItems"][0]["taskId"] == 2
    assert body["taskItems"][0]["isDue"] is True


def test_todo_complete_returns_scheduler_completion_metadata():
    client, ps = _client()
    headers = _auth_headers(client)
    now = datetime.now(timezone.utc)
    next_run = (now + timedelta(days=1)).isoformat()
    mock_store = MagicMock()
    mock_store.complete_task.return_value = {
        "rescheduled": True,
        "next_run_at": next_run,
        "tasks": ["Task B"],
        "task_items": [
            {
                "id": "b",
                "description": "Task B",
                "next_run_at": next_run,
                "scheduled_for": now.isoformat(),
                "recurrence": {"frequency": "daily", "interval": 1},
            }
        ],
        "updated_at": now.isoformat(),
    }

    original_available = ps.TODO_STORE_AVAILABLE
    original_store = ps._todo_store
    ps.TODO_STORE_AVAILABLE = True
    ps._todo_store = mock_store
    try:
        response = client.post("/v1/todo/2/complete", headers=headers)
    finally:
        ps.TODO_STORE_AVAILABLE = original_available
        ps._todo_store = original_store

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["completion"]["taskId"] == 2
    assert body["completion"]["rescheduled"] is True
    assert body["completion"]["nextRunAt"] == next_run
