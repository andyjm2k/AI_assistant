import hashlib
import math

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from src.memory.memory_manager import MemoryManager
from src.servers.memory_api import create_memory_router


class DeterministicEmbeddings:
    api_base = "https://embeddings.test/v1"
    model = "test-embedding-v1"

    async def get_embedding(self, text):
        digest = hashlib.sha256(str(text).encode("utf-8")).digest()
        vector = [float(value + 1) for value in digest[:8]]
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector]


def test_memory_api_enforces_authenticated_namespace(tmp_path):
    manager = MemoryManager(
        storage_path=str(tmp_path),
        embeddings_client=DeterministicEmbeddings(),
    )

    def current_user(x_test_user: str = Header(default="")):
        if not x_test_user:
            raise HTTPException(status_code=401)
        return {"username": x_test_user}

    app = FastAPI()
    app.include_router(
        create_memory_router(
            manager_provider=lambda: manager,
            auth_dependency=current_user,
        )
    )
    client = TestClient(app)
    try:
        created = client.post(
            "/v1/memory/store",
            headers={"X-Test-User": "alice"},
            json={"text": "Alice lives in Hobart.", "kind": "profile_fact"},
        )
        assert created.status_code == 200
        memory_id = created.json()["data"]["memory_id"]
        bob_created = client.post(
            "/v1/memory/store",
            headers={"X-Test-User": "bob"},
            json={"text": "Bob lives in Perth.", "kind": "profile_fact"},
        )
        assert bob_created.status_code == 200
        bob_memory_id = bob_created.json()["data"]["memory_id"]

        bob_list = client.get("/v1/memory/list", headers={"X-Test-User": "bob"})
        assert bob_list.status_code == 200
        assert [item["id"] for item in bob_list.json()["data"]["memories"]] == [bob_memory_id]

        bob_search = client.post(
            "/v1/memory/search",
            headers={"X-Test-User": "bob"},
            json={"query": "Alice lives in Hobart", "similarity_threshold": -1},
        )
        assert bob_search.status_code == 200
        assert all(
            item["id"] != memory_id
            for item in bob_search.json()["data"]["memories"]
        )

        bob_export = client.get("/v1/memory/export", headers={"X-Test-User": "bob"})
        assert bob_export.status_code == 200
        assert bob_export.json()["data"]["namespace"] == "bob"
        assert [item["id"] for item in bob_export.json()["data"]["memories"]] == [
            bob_memory_id
        ]

        bob_get = client.get(
            f"/v1/memory/{memory_id}",
            headers={"X-Test-User": "bob"},
        )
        assert bob_get.status_code == 404
        bob_delete = client.delete(
            f"/v1/memory/{memory_id}",
            headers={"X-Test-User": "bob"},
        )
        assert bob_delete.status_code == 404

        alice_get = client.get(
            f"/v1/memory/{memory_id}",
            headers={"X-Test-User": "alice"},
        )
        assert alice_get.status_code == 200

        invalid_kind = client.post(
            "/v1/memory/store",
            headers={"X-Test-User": "alice"},
            json={"text": "Invalid category", "kind": "task_experience"},
        )
        assert invalid_kind.status_code == 400

        oversized_metadata = client.post(
            "/v1/memory/store",
            headers={"X-Test-User": "alice"},
            json={
                "text": "Bounded metadata",
                "kind": "profile_fact",
                "metadata": {"payload": "x" * 33000},
            },
        )
        assert oversized_metadata.status_code == 400

        non_text_extraction = client.post(
            "/v1/memory/extract",
            headers={"X-Test-User": "alice"},
            json={"messages": [{"role": "user", "content": {"text": "nested"}}]},
        )
        assert non_text_extraction.status_code == 400

        bob_clear = client.post(
            "/v1/memory/clear",
            headers={"X-Test-User": "bob"},
            json={"confirm": True},
        )
        assert bob_clear.status_code == 200
        assert manager.get_memory(memory_id, namespace="alice") is not None
        assert manager.get_memory(bob_memory_id, namespace="bob") is None

        unauthenticated = client.get("/v1/memory/status")
        assert unauthenticated.status_code == 401
    finally:
        client.close()
        manager.repository.close()
