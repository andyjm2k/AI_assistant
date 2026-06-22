from unittest.mock import AsyncMock
import secrets

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_do_workflow_defaults_to_autogen(monkeypatch):
    from src.servers import proxy_server as ps

    fake_autogen = AsyncMock(return_value={"output": "ok", "response": "ok"})

    monkeypatch.setenv("WORKFLOW_FRAMEWORK", "autogen")
    monkeypatch.setattr(ps, "_do_autogen", fake_autogen)

    result = await ps._do_workflow("draft report")

    assert result["framework"] == "autogen"
    assert result["output"] == "ok"
    fake_autogen.assert_awaited_once_with("draft report")


@pytest.mark.asyncio
async def test_do_workflow_rejects_invalid_framework(monkeypatch):
    from src.servers import proxy_server as ps

    monkeypatch.setenv("WORKFLOW_FRAMEWORK", "invalid")

    with pytest.raises(HTTPException) as exc:
        await ps._do_workflow("draft report")

    assert exc.value.status_code == 400
    assert "WORKFLOW_FRAMEWORK must be one of" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_do_workflow_ag2_missing_dependency_has_clear_error(monkeypatch):
    from src.servers import proxy_server as ps

    class MissingAg2Runner:
        def available(self):
            return type(
                "Availability",
                (),
                {
                    "available": False,
                    "message": "AG2 backend not available. Install AG2 with OpenAI support.",
                },
            )()

        async def stop(self):
            return None

    monkeypatch.setenv("WORKFLOW_FRAMEWORK", "ag2")
    scratch_dir = ps._PROJECT_ROOT / "scratch" / f"workflow-proxy-{secrets.token_hex(4)}"
    scratch_dir.mkdir(parents=True, exist_ok=False)
    monkeypatch.setattr(ps, "SCRATCH_DIR", scratch_dir)
    monkeypatch.setattr(ps, "Ag2WorkflowRunner", lambda: MissingAg2Runner())

    try:
        with pytest.raises(HTTPException) as exc:
            await ps._do_workflow("draft report")

        assert exc.value.status_code == 503
        assert "AG2 backend not available" in str(exc.value.detail)

        logs = list(scratch_dir.glob("workflow_ag2_run_*.txt"))
        assert logs
        assert "AG2 backend not available" in logs[0].read_text(encoding="utf-8")
    finally:
        for child in scratch_dir.iterdir():
            child.unlink(missing_ok=True)
        scratch_dir.rmdir()
