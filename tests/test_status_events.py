"""
Unit tests for persistent status events endpoints.
"""

import uuid
from pathlib import Path

from fastapi.testclient import TestClient


def _make_status_tmp() -> Path:
    base = Path("scratch") / "status_tests"
    base.mkdir(parents=True, exist_ok=True)
    path = base / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _setup_status_store(tmp_dir: Path):
    from src.servers import proxy_server as ps
    ps.STATUS_DATA_DIR = tmp_dir
    ps.STATUS_EVENTS_FILE = tmp_dir / "status_events.jsonl"
    ps.status_sessions.clear()
    ps.status_latest_index.clear()
    ps._init_status_store()
    return ps


def test_status_events_flow():
    tmp_dir = _make_status_tmp()
    ps = _setup_status_store(tmp_dir)
    client = TestClient(ps.app)

    start_payload = {
        "conversation_id": "conv-1",
        "request_id": "req-1",
        "channel": "web",
        "state": "Working: start",
    }
    resp = client.post("/v1/status/start", json=start_payload)
    assert resp.status_code == 200

    update_payload = {
        "conversation_id": "conv-1",
        "request_id": "req-1",
        "state": "Working: step",
    }
    resp = client.post("/v1/status/update", json=update_payload)
    assert resp.status_code == 200

    events_resp = client.get("/v1/status/events", params={
        "conversation_id": "conv-1",
        "request_id": "req-1",
        "since_seq": 0,
    })
    assert events_resp.status_code == 200
    events_data = events_resp.json()
    assert len(events_data.get("events", [])) >= 2

    latest_resp = client.get("/v1/status/latest", params={
        "conversation_id": "conv-1",
        "request_id": "req-1",
    })
    assert latest_resp.status_code == 200
    latest_data = latest_resp.json()
    assert latest_data.get("found") is True
    assert latest_data.get("event", {}).get("state") == "Working: step"

    finish_payload = {
        "conversation_id": "conv-1",
        "request_id": "req-1",
        "final_state": "Done",
    }
    resp = client.post("/v1/status/finish", json=finish_payload)
    assert resp.status_code == 200


def test_status_events_persist_across_restart():
    tmp_dir = _make_status_tmp()
    ps = _setup_status_store(tmp_dir)
    client = TestClient(ps.app)

    client.post("/v1/status/start", json={
        "conversation_id": "conv-2",
        "request_id": "req-2",
        "state": "Working: start",
    })
    client.post("/v1/status/update", json={
        "conversation_id": "conv-2",
        "request_id": "req-2",
        "state": "Working: step",
    })

    # Simulate restart: clear in-memory and reload index from file
    ps.status_sessions.clear()
    ps.status_latest_index.clear()
    ps._load_status_index()

    latest_resp = client.get("/v1/status/latest", params={
        "conversation_id": "conv-2",
        "request_id": "req-2",
    })
    assert latest_resp.status_code == 200
    latest_data = latest_resp.json()
    assert latest_data.get("found") is True
    assert latest_data.get("event", {}).get("state") == "Working: step"
