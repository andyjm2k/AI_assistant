"""Startup behavior tests for src.servers.proxy_server."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


def test_proxy_log_tee_stream_replaces_unencodable_console_text():
    from src.servers import proxy_server as ps

    class Cp1252LikeStream:
        encoding = "cp1252"
        errors = "strict"

        def __init__(self):
            self.writes = []

        def write(self, text):
            text.encode(self.encoding, errors=self.errors)
            self.writes.append(text)
            return len(text)

        def flush(self):
            return None

    class LogHandle:
        def __init__(self):
            self.writes = []

        def write(self, text):
            self.writes.append(text)
            return len(text)

        def flush(self):
            return None

    stream = Cp1252LikeStream()
    log_handle = LogHandle()
    tee = ps._ProxyLogTeeStream(stream, log_handle)

    written = tee.write("✅ startup ok")

    assert written == len("? startup ok")
    assert stream.writes == ["? startup ok"]
    assert log_handle.writes == ["✅ startup ok"]


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
    monkeypatch.setattr(ps, "_should_warm_autogen_on_startup", lambda: True)
    monkeypatch.setattr(ps, "_warm_autogen_team_after_startup", fake_warmup)
    monkeypatch.setattr(ps.asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(ps, "_autogen_team_warmup_task", None)

    await ps.startup_event()

    assert scheduled["coro"].cr_code.co_name == fake_warmup.__code__.co_name
    scheduled["coro"].close()


@pytest.mark.asyncio
async def test_startup_event_skips_autogen_warmup_when_backend_not_autogen(monkeypatch):
    from src.servers import proxy_server as ps

    def fail_create_task(_coro):
        raise AssertionError("AutoGen warmup should not be scheduled")

    monkeypatch.setattr(ps, "_get_shared_chat_http_client", AsyncMock())
    monkeypatch.setattr(ps, "_should_warm_autogen_on_startup", lambda: False)
    monkeypatch.setattr(ps.asyncio, "create_task", fail_create_task)
    monkeypatch.setattr(ps, "_autogen_team_warmup_task", None)

    await ps.startup_event()

    assert ps._autogen_team_warmup_task is None
