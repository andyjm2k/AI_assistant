"""Startup behavior tests for src.servers.proxy_server."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_startup_event_schedules_background_autogen_warmup(monkeypatch):
    from src.servers import proxy_server as ps

    scheduled = {}

    class DummyTask:
        def done(self):
            return False

    async def fake_warmup():
        return None

    def fake_create_task(coro):
        scheduled["coro"] = coro
        return DummyTask()

    monkeypatch.setattr(ps, "_get_shared_chat_http_client", AsyncMock())
    monkeypatch.setattr(ps, "_warm_autogen_team_after_startup", fake_warmup)
    monkeypatch.setattr(ps.asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(ps, "_autogen_team_warmup_task", None)

    await ps.startup_event()

    assert scheduled["coro"].cr_code.co_name == fake_warmup.__code__.co_name
    scheduled["coro"].close()
