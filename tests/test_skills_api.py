"""Integration tests for skills routes mounted on proxy_server."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


def _client():
    from src.servers import proxy_server as ps

    return TestClient(ps.app)


def _auth_headers(client: TestClient) -> dict:
    username = "skills_api_test_user"
    password = "skills_api_test_password_123"
    signup = client.post("/v1/auth/signup", json={"username": username, "password": password})
    if signup.status_code == 200:
        token = signup.json()["access_token"]
    else:
        login = client.post("/v1/auth/login", json={"username": username, "password": password})
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_skills_routes_require_authentication() -> None:
    client = _client()
    response = client.get("/v1/skills")
    assert response.status_code == 401


def test_skills_list_and_execute_with_auth() -> None:
    client = _client()
    headers = _auth_headers(client)

    list_response = client.get("/v1/skills", headers=headers)
    assert list_response.status_code == 200, list_response.text
    names = [item["name"] for item in list_response.json()["skills"]]
    assert "core" in names
    assert "filesystem" in names

    execute_response = client.post(
        "/v1/skills/tools/execute",
        headers=headers,
        json={"tool_name": "core.ping", "arguments": {}, "context": {}},
    )
    assert execute_response.status_code == 200, execute_response.text
    payload = execute_response.json()
    assert payload["success"] is True
    assert payload["tool_name"] == "core.ping"
    assert payload["data"]["pong"] is True


def test_skills_openai_tools_hide_overlapping_filesystem_tools_by_default() -> None:
    client = _client()
    headers = _auth_headers(client)

    default_resp = client.get("/v1/skills/tools/openai?qualified_names=true", headers=headers)
    assert default_resp.status_code == 200, default_resp.text
    default_tools = default_resp.json().get("tools", [])
    default_names = {
        str(tool.get("function", {}).get("name", ""))
        for tool in default_tools
        if isinstance(tool, dict)
    }
    assert "filesystem.list_files" not in default_names
    assert "filesystem.read_text" not in default_names
    assert "filesystem.write_text" not in default_names
    assert "filesystem.search_files" not in default_names

    include_resp = client.get(
        "/v1/skills/tools/openai?qualified_names=true&include_overlapping_file_tools=true",
        headers=headers,
    )
    assert include_resp.status_code == 200, include_resp.text
    include_tools = include_resp.json().get("tools", [])
    include_names = {
        str(tool.get("function", {}).get("name", ""))
        for tool in include_tools
        if isinstance(tool, dict)
    }
    assert "filesystem.list_files" in include_names
    assert "filesystem.read_text" in include_names
    assert "filesystem.write_text" in include_names
    assert "filesystem.search_files" in include_names


def test_skills_package_export_and_import_endpoints() -> None:
    temp_base = _create_workspace_temp_dir()
    client = _client()
    headers = _auth_headers(client)
    package_path = temp_base / "core-api.catbotskill"

    try:
        export_response = client.post(
            "/v1/skills/packages/export",
            headers=headers,
            json={
                "skill_name": "core",
                "output_path": str(package_path),
                "include_sources": True,
                "source_root": ".",
                "overwrite": True,
            },
        )
        assert export_response.status_code == 200, export_response.text
        export_payload = export_response.json()
        assert export_payload["success"] is True
        assert Path(export_payload["package_path"]).exists()

        import_response = client.post(
            "/v1/skills/packages/import",
            headers=headers,
            json={
                "package_path": str(package_path),
                "manifest_dir": str(temp_base / "imported-manifests"),
                "source_root": str(temp_base / "imported-source-root"),
                "load_skill": True,
                "replace": True,
                "overwrite": True,
            },
        )
        assert import_response.status_code == 200, import_response.text
        import_payload = import_response.json()
        assert import_payload["success"] is True
        assert Path(import_payload["manifest_path"]).exists()
        assert import_payload["loaded_skill"] is not None
        assert import_payload["loaded_skill"]["name"] == "core"
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


def _create_workspace_temp_dir() -> Path:
    base = Path("scratch") / f"skills-api-test-{uuid.uuid4().hex}"
    base.mkdir(parents=True, exist_ok=True)
    return base
