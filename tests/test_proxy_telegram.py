"""
Unit and API tests for proxy server Telegram endpoints.
Covers: POST /v1/telegram/chat (success, validation, api key, secret), DELETE /v1/telegram/chat/{id}.
Uses mocks for external OpenAI and memory; no real API calls.
"""

import os
import base64
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _get_client():
    """Return TestClient for proxy_server app."""
    from src.servers.proxy_server import app
    return TestClient(app)


def _auth_headers():
    """Build Authorization header with a valid JWT so protected proxy routes can be exercised."""
    from src.servers.proxy_server import create_jwt, users_db
    users_db.setdefault("andyjm2k", {"created_at": "2026-01-01T00:00:00Z"})
    token = create_jwt({"sub": "andyjm2k"})
    return {"Authorization": f"Bearer {token}"}


def _mock_openai_response(reply_text: str = "Mocked reply"):
    """Build a mock response body for OpenAI-compatible chat."""
    return {
        "choices": [{"message": {"content": reply_text}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


@pytest.fixture(autouse=True)
def _isolate_telegram_secret(monkeypatch):
    """Keep Telegram endpoint tests independent of a locally configured .env secret."""
    from src.servers import proxy_server as ps

    monkeypatch.setattr(ps, "TELEGRAM_SECRET", None)


def test_skill_tool_alias_maps_markdown_to_slides_variants_to_googleworkspace_cli():
    from src.servers import proxy_server as ps

    expected = "googleworkspace_cli.slides_create_presentation_from_markdown"
    assert ps._resolve_skill_tool_qualified_name("google_slides.slides_create_presentation_from_markdown") == expected
    assert ps._resolve_skill_tool_qualified_name("slides_create_presentation_from_markdown") == expected
    assert ps._resolve_skill_tool_qualified_name("markdown_to_slides") == expected
    assert ps._resolve_skill_tool_qualified_name("markdownToSlides") == expected


def test_compose_system_prompt_with_context_includes_soul_prompt():
    from src.servers import proxy_server as ps

    with patch("src.servers.proxy_server._get_soul_prompt_text", return_value="Soul prompt"):
        prompt = ps._compose_system_prompt_with_context("Base prompt")

    assert prompt.startswith("Context: Today's date is ")
    assert "Soul prompt" in prompt
    assert prompt.endswith("Base prompt")
    assert prompt.index("Soul prompt") < prompt.index("Base prompt")


@pytest.mark.asyncio
async def test_handle_pdf_to_powerpoint_internal_supports_scratch_markdown():
    from src.servers import proxy_server as ps

    markdown_rel = f"presentations/test-markdown-{uuid.uuid4().hex}.md"
    pptx_rel = f"presentations/test-markdown-{uuid.uuid4().hex}.pptx"
    markdown_path = ps.SCRATCH_DIR / markdown_rel
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        "# Quarterly Update\n\n## Revenue\n- ARR grew 18%\n- Pipeline improved\n\n## Roadmap\n- Release v2 in Q3\n- Expand integrations\n",
        encoding="utf-8",
    )

    result = await ps._handle_pdf_to_powerpoint_internal(
        {
            "sourceUrl": markdown_rel,
            "sourceType": "markdown",
            "title": "Quarterly Update",
            "filename": pptx_rel,
        },
        conversation_id="tg-md-test",
        user_id="user-1",
    )
    assert result.get("success") is True, result
    data = result.get("data") or {}
    output_rel = data.get("file_path")
    assert output_rel == pptx_rel
    assert (ps.SCRATCH_DIR / output_rel).exists()


@pytest.mark.asyncio
async def test_handle_pdf_to_powerpoint_internal_supports_markdown_url():
    from src.servers import proxy_server as ps

    pptx_rel = f"presentations/test-url-{uuid.uuid4().hex}.pptx"
    fake_markdown = (
        "# URL Deck\n\n## Market\n- Demand is rising\n- Competition is fragmented\n\n"
        "## Plan\n- Launch pilot\n- Measure retention\n"
    ).encode("utf-8")

    with patch.object(ps, "_fetch_presentation_source_url", new=AsyncMock(return_value=("text/markdown", fake_markdown))):
        result = await ps._handle_pdf_to_powerpoint_internal(
            {
                "sourceUrl": "https://example.com/deck.md",
                "sourceType": "markdown",
                "title": "URL Deck",
                "filename": pptx_rel,
            },
            conversation_id="tg-url-test",
            user_id="user-1",
        )

    assert result.get("success") is True, result
    data = result.get("data") or {}
    assert data.get("file_path") == pptx_rel
    assert (ps.SCRATCH_DIR / pptx_rel).exists()


@pytest.mark.asyncio
async def test_handle_pdf_to_powerpoint_internal_uses_uploaded_attachment_when_source_missing():
    from src.servers import proxy_server as ps

    markdown_rel = f"attachments/telegram/test-attach/{uuid.uuid4().hex}.md"
    pptx_rel = f"presentations/test-attach-{uuid.uuid4().hex}.pptx"
    markdown_path = ps.SCRATCH_DIR / markdown_rel
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        "# Attachment Deck\n\n## Input\n- Came from upload\n- Stored in scratch\n\n## Output\n- Generate pptx\n- Send to user\n",
        encoding="utf-8",
    )

    result = await ps._handle_pdf_to_powerpoint_internal(
        {
            "title": "Attachment Deck",
            "filename": pptx_rel,
        },
        conversation_id="tg-attach-test",
        user_id="user-1",
        attachment_records=[{"relative_path": markdown_rel}],
    )

    assert result.get("success") is True, result
    data = result.get("data") or {}
    assert data.get("source_descriptor") == markdown_rel
    assert (ps.SCRATCH_DIR / pptx_rel).exists()


@pytest.mark.asyncio
async def test_handle_pdf_to_powerpoint_internal_supports_pdf_source():
    pytest.importorskip("reportlab.pdfgen.canvas")
    from reportlab.pdfgen import canvas
    from src.servers import proxy_server as ps

    pdf_rel = f"presentations/test-pdf-{uuid.uuid4().hex}.pdf"
    pptx_rel = f"presentations/test-pdf-{uuid.uuid4().hex}.pptx"
    pdf_path = ps.SCRATCH_DIR / pdf_rel
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(pdf_path))
    c.drawString(72, 720, "Quarterly performance improved across revenue, margin, and customer growth.")
    c.drawString(72, 700, "Priorities include partner rollout, hiring, and retention improvements.")
    c.save()

    result = await ps._handle_pdf_to_powerpoint_internal(
        {
            "sourceUrl": pdf_rel,
            "sourceType": "pdf",
            "title": "PDF Deck",
            "filename": pptx_rel,
        },
        conversation_id="tg-pdf-test",
        user_id="user-1",
    )

    assert result.get("success") is True, result
    data = result.get("data") or {}
    assert data.get("source_type") == "pdf"
    assert (ps.SCRATCH_DIR / pptx_rel).exists()


class TestTelegramChatEndpoint:
    """Tests for POST /v1/telegram/chat."""

    def test_telegram_chat_payload_includes_soul_prompt_before_base_prompt(self):
        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response("Hello from CATBot")

        def getenv(k, d=None):
            if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"):
                return "test-key"
            return os.environ.get(k, d) if d is not None else os.environ.get(k)

        with patch("src.servers.proxy_server.os.getenv", side_effect=getenv):
            with patch("src.servers.proxy_server._get_soul_prompt_text", return_value="Soul prompt line 1\nSoul prompt line 2"):
                with patch("src.servers.proxy_server._get_telegram_system_prompt_with_tools", return_value="Base prompt"):
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(return_value=mock_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"conversation_id": "soul-check", "user_id": "123", "message": "Hi"},
                            headers=_auth_headers(),
                        )

        assert resp.status_code == 200, resp.text
        payload = mock_client_instance.post.await_args.kwargs["json"]
        system_prompt = payload["messages"][0]["content"]
        assert "Soul prompt line 1\nSoul prompt line 2" in system_prompt
        assert "Base prompt" in system_prompt
        assert system_prompt.index("Soul prompt line 1") < system_prompt.index("Base prompt")

    def test_small_talk_does_not_create_status_session(self):
        """Low-intent greetings should not emit Telegram progress/status chatter."""
        client = _get_client()
        request_id = "small-talk-no-status"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response("Hello from CATBot")

        def getenv(k, d=None):
            if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"):
                return "test-key"
            return os.environ.get(k, d) if d is not None else os.environ.get(k)

        with patch("src.servers.proxy_server.os.getenv", side_effect=getenv):
            with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                mock_client_instance = MagicMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_aclient.return_value = mock_client_instance

                resp = client.post(
                    "/v1/telegram/chat",
                    json={"message": "Hey how are you?", "conversation_id": "small-talk-conv", "request_id": request_id},
                )
        assert resp.status_code == 200, resp.text
        status_resp = client.get(
            "/v1/status/latest",
            params={"conversation_id": "small-talk-conv", "request_id": request_id},
        )
        assert status_resp.status_code == 200
        assert status_resp.json() == {"found": False}

    def test_missing_message_returns_400(self):
        """POST with empty or missing message returns 400."""
        client = _get_client()
        resp = client.post(
            "/v1/telegram/chat",
            json={"message": ""},
        )
        assert resp.status_code == 400
        assert "message" in (resp.json().get("detail") or resp.text).lower()

    def test_valid_request_returns_200_and_reply(self):
        """POST with valid message and mocked OpenAI returns 200 and reply in body."""
        client = _get_client()
        request_id = "request-with-status"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response("Hello from CATBot")

        def getenv(k, d=None):
            if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"):
                return "test-key"
            return os.environ.get(k, d) if d is not None else os.environ.get(k)

        with patch("src.servers.proxy_server.os.getenv", side_effect=getenv):
            with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                mock_client_instance = MagicMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_aclient.return_value = mock_client_instance

                resp = client.post(
                    "/v1/telegram/chat",
                    json={"message": "Search for recent AI news", "conversation_id": "test-conv", "request_id": request_id},
                )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "Hello from CATBot"
        assert data.get("conversation_id") == "test-conv"
        status_resp = client.get(
            "/v1/status/latest",
            params={"conversation_id": "test-conv", "request_id": request_id},
        )
        assert status_resp.status_code == 200
        status_payload = status_resp.json()
        assert status_payload.get("found") is True
        assert status_payload.get("event", {}).get("channel") == "telegram"
        assert status_payload.get("event", {}).get("request_id") == request_id

    def test_attachment_only_request_saves_attachment_and_augments_prompt(self, monkeypatch):
        """Telegram chat should accept attachment-only payloads, save them to scratch, and pass a manifest to the model."""
        from src.servers import proxy_server as ps

        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response("Reviewed the attachment")
        scratch_root = os.path.join(os.path.dirname(__file__), "..", "scratch", f"telegram-attach-{int(time.time() * 1000)}")
        scratch_path = os.path.abspath(scratch_root)
        os.makedirs(scratch_path, exist_ok=True)
        monkeypatch.setattr(ps, "SCRATCH_DIR", ps.Path(scratch_path))
        attachment_b64 = base64.b64encode(b"hello attachment").decode("ascii")

        def getenv(k, d=None):
            if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"):
                return "test-key"
            return os.environ.get(k, d) if d is not None else os.environ.get(k)

        with patch("src.servers.proxy_server.os.getenv", side_effect=getenv):
            with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                mock_client_instance = MagicMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_aclient.return_value = mock_client_instance

                resp = client.post(
                    "/v1/telegram/chat",
                    json={
                        "conversation_id": "attach-only",
                        "user_id": "123",
                        "attachments": [
                            {
                                "filename": "brief.txt",
                                "mime_type": "text/plain",
                                "content_base64": attachment_b64,
                            }
                        ],
                    },
                )

        assert resp.status_code == 200, resp.text
        payload = mock_client_instance.post.await_args.kwargs["json"]
        user_message = payload["messages"][-1]["content"]
        assert user_message.startswith("Please review the attached file(s).")
        assert "Attached files saved in scratch:" in user_message
        assert "attachments/telegram/attach-only/" in user_message
        assert "filesystem.read_text" in user_message
        assert "Do not use pdfToPowerPoint unless the user explicitly asks to convert a PDF or Markdown document" in user_message
        saved_dir = os.path.join(scratch_path, "attachments", "telegram", "attach-only")
        try:
            saved_files = []
            for root, _, files in os.walk(saved_dir):
                for name in files:
                    if name.endswith(".txt"):
                        saved_files.append(os.path.join(root, name))
            assert len(saved_files) == 1
            with open(saved_files[0], "rb") as handle:
                assert handle.read() == b"hello attachment"
        finally:
            import shutil
            shutil.rmtree(scratch_path, ignore_errors=True)

    def test_image_attachment_is_forwarded_as_vision_input(self, monkeypatch):
        """Telegram image attachments should be included as image_url parts for vision-capable models."""
        from src.servers import proxy_server as ps

        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response("Reviewed the image")
        scratch_root = os.path.join(os.path.dirname(__file__), "..", "scratch", f"telegram-image-{int(time.time() * 1000)}")
        scratch_path = os.path.abspath(scratch_root)
        os.makedirs(scratch_path, exist_ok=True)
        monkeypatch.setattr(ps, "SCRATCH_DIR", ps.Path(scratch_path))
        image_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0k8AAAAASUVORK5CYII="
        )

        def getenv(k, d=None):
            if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"):
                return "test-key"
            return os.environ.get(k, d) if d is not None else os.environ.get(k)

        with patch("src.servers.proxy_server.os.getenv", side_effect=getenv):
            with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                mock_client_instance = MagicMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_aclient.return_value = mock_client_instance

                resp = client.post(
                    "/v1/telegram/chat",
                    json={
                        "conversation_id": "attach-image",
                        "user_id": "123",
                        "message": "What is in this image?",
                        "attachments": [
                            {
                                "filename": "pixel.png",
                                "mime_type": "image/png",
                                "content_base64": image_b64,
                            }
                        ],
                    },
                )

        try:
            assert resp.status_code == 200, resp.text
            payload = mock_client_instance.post.await_args.kwargs["json"]
            user_message = payload["messages"][-1]["content"]
            assert isinstance(user_message, list)
            assert user_message[0]["type"] == "text"
            image_parts = [part for part in user_message if part.get("type") == "image_url"]
            assert len(image_parts) == 1
            assert image_parts[0]["image_url"]["url"].startswith("data:image/png;base64,")
        finally:
            import shutil
            shutil.rmtree(scratch_path, ignore_errors=True)

    def test_invalid_attachment_base64_returns_400(self):
        """Telegram chat should reject malformed base64 attachments."""
        client = _get_client()
        resp = client.post(
            "/v1/telegram/chat",
            json={
                "conversation_id": "attach-invalid",
                "attachments": [
                    {
                        "filename": "brief.txt",
                        "mime_type": "text/plain",
                        "content_base64": "%%%not-base64%%%",
                    }
                ],
            },
        )
        assert resp.status_code == 400
        assert "base64" in resp.text.lower()

    def test_valid_request_handles_structured_content_reply(self):
        """POST should coerce list/dict content parts into plain text reply."""
        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "Hello from CATBot"},
                            {"type": "text", "text": "Second line"},
                        ]
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        def getenv(k, d=None):
            if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"):
                return "test-key"
            return os.environ.get(k, d) if d is not None else os.environ.get(k)

        with patch("src.servers.proxy_server.os.getenv", side_effect=getenv):
            with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                mock_client_instance = MagicMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_aclient.return_value = mock_client_instance

                resp = client.post(
                    "/v1/telegram/chat",
                    json={"message": "Hi", "conversation_id": "structured-conv"},
                )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "Hello from CATBot\nSecond line"
        assert data.get("conversation_id") == "structured-conv"

    def test_valid_request_strips_think_blocks_from_reply(self):
        """Assistant <think> blocks should be removed from Telegram-facing reply text."""
        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response(
            "<think>internal reasoning</think>\nHello from CATBot"
        )

        def getenv(k, d=None):
            if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"):
                return "test-key"
            return os.environ.get(k, d) if d is not None else os.environ.get(k)

        with patch("src.servers.proxy_server.os.getenv", side_effect=getenv):
            with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                mock_client_instance = MagicMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_aclient.return_value = mock_client_instance

                resp = client.post(
                    "/v1/telegram/chat",
                    json={"message": "Hi", "conversation_id": "think-strip-conv"},
                )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "Hello from CATBot"

    def test_minimax_tool_loop_preserves_reasoning_details_in_history(self):
        """Minimax tool follow-ups should keep reasoning metadata internally but strip it from the Telegram reply."""
        client = _get_client()
        first_response = MagicMock()
        first_response.status_code = 200
        first_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Searching now",
                        "reasoning_details": [{"type": "reasoning.text", "text": "internal plan"}],
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "webSearch",
                                    "arguments": "{\"query\": \"test query\"}",
                                },
                            }
                        ],
                    }
                }
            ]
        }
        second_response = MagicMock()
        second_response.status_code = 200
        second_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "<think>internal finish</think>\nFinal answer for Telegram"
                    }
                }
            ]
        }

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            with patch("src.servers.proxy_server.TELEGRAM_OPENAI_BASE_URL", "https://api.minimax.io/v1"):
                with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                    mock_search.return_value = {"results": [{"title": "Test", "snippet": "Snippet"}]}
                    with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                        m_getenv.side_effect = lambda k, d=None: (
                            "minimax-key"
                            if k in ("MINIMAX_API_KEY", "MCP_LLM_MINIMAX_API_KEY")
                            else os.environ.get(k, d)
                        )
                        with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                            mock_client_instance = MagicMock()
                            mock_client_instance.post = AsyncMock(side_effect=[first_response, second_response])
                            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                            mock_aclient.return_value = mock_client_instance

                            resp = client.post(
                                "/v1/telegram/chat",
                                json={"message": "Search for test", "conversation_id": "minimax-tool-loop"},
                            )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "Final answer for Telegram"

        first_payload = mock_client_instance.post.await_args_list[0].kwargs["json"]
        assert first_payload["extra_body"]["reasoning_split"] is True

        second_payload = mock_client_instance.post.await_args_list[1].kwargs["json"]
        assistant_turn = next(
            msg for msg in second_payload["messages"]
            if msg.get("role") == "assistant" and msg.get("tool_calls")
        )
        assert assistant_turn["reasoning_details"][0]["text"] == "internal plan"

    def test_memory_list_result_is_returned_without_llm_followup(self):
        """Memory listings are authoritative and must not be rewritten by a fallback model."""
        client = _get_client()
        first_response = MagicMock()
        first_response.status_code = 200
        first_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_memory_list",
                                "type": "function",
                                "function": {
                                    "name": "listMemories",
                                    "arguments": "{}",
                                },
                            }
                        ],
                    }
                }
            ]
        }
        hallucinated_followup = MagicMock()
        hallucinated_followup.status_code = 200
        hallucinated_followup.json.return_value = _mock_openai_response(
            "There are memories stored for Patrick."
        )
        mock_memory_manager = MagicMock()
        mock_memory_manager.list_memories.return_value = []

        def getenv(key, default=None):
            if key in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"):
                return "test-key"
            if key == "MEMORY_AUTO_EXTRACT":
                return "false"
            return os.environ.get(key, default)

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True), patch(
            "src.servers.proxy_server.MEMORY_AVAILABLE", True
        ), patch("src.servers.proxy_server.memory_manager", mock_memory_manager), patch(
            "src.servers.proxy_server.os.getenv", side_effect=getenv
        ), patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
            mock_client_instance = MagicMock()
            mock_client_instance.post = AsyncMock(
                side_effect=[first_response, hallucinated_followup]
            )
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_aclient.return_value = mock_client_instance

            resp = client.post(
                "/v1/telegram/chat",
                json={
                    "message": "List my memories",
                    "conversation_id": "memory-list-authoritative",
                    "user_id": "6644154165",
                },
            )

        assert resp.status_code == 200, resp.text
        assert resp.json().get("reply") == "Here's what I found:\n\nNo memories."
        assert mock_client_instance.post.await_count == 1
        mock_memory_manager.list_memories.assert_called_once()

    def test_telegram_system_prompt_appends_native_tool_json_rules(self):
        from src.servers import proxy_server as ps

        prompt = ps._get_telegram_system_prompt_with_tools("prompt-native-rules")

        assert "Native Telegram tools:" in prompt
        assert "Prefer structured tool calls using the provided tool schema and exact tool name." in prompt
        assert "Use XML tool markup only as a legacy fallback when structured tool calls are unavailable." in prompt
        assert "Parameters JSON schema:" in prompt
        assert "MUST ALWAYS respond in this EXACT format" not in prompt
        assert "Always use the XML-style format shown above" not in prompt
        assert '<tool>scrapeWebsite</tool>' not in prompt

    def test_telegram_system_prompt_prefers_filesystem_skills_over_legacy_file_tools(self):
        from src.servers import proxy_server as ps

        fake_skill_tools = [
            {"name": "filesystem.read_text", "description": "read", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "filesystem.write_text", "description": "write", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "filesystem.list_files", "description": "list", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "filesystem.search_files", "description": "search", "inputSchema": {"type": "object", "properties": {}}},
        ]

        with patch("src.servers.proxy_server._get_skill_tools_mcp_schema", return_value=fake_skill_tools):
            prompt = ps._get_telegram_system_prompt_with_tools("prompt-filesystem-preference")

        assert "prefer filesystem.read_text" in prompt
        assert "filesystem.write_text" in prompt
        assert "filesystem.list_files" in prompt
        assert "filesystem.search_files" in prompt
        assert "Filesystem skill tools are available in this conversation." in prompt

    def test_tool_capable_prompt_template_mentions_filesystem_skill_tools(self):
        from src.servers import proxy_server as ps

        prompt_template = ps.CATBOT_SYSTEM_PROMPT_WITH_TOOLS_FILE.read_text(encoding="utf-8")

        assert "filesystem.read_text" in prompt_template
        assert "filesystem.write_text" in prompt_template
        assert "filesystem.list_files" in prompt_template
        assert "filesystem.search_files" in prompt_template

    def test_telegram_system_prompt_prefers_native_create_slides_tool_over_raw_skill(self):
        from src.servers import proxy_server as ps

        fake_skill_tools = [
            {
                "name": "googleworkspace_cli.slides_create_presentation_from_markdown",
                "description": "create slides from markdown",
                "inputSchema": {"type": "object", "properties": {"markdown_path": {"type": "string"}}},
            }
        ]

        with patch("src.servers.proxy_server._get_skill_tools_mcp_schema", return_value=fake_skill_tools):
            prompt = ps._get_telegram_system_prompt_with_tools("prompt-slides-example")

        assert "createSlidesPresentation" in prompt
        assert "Do not call googleworkspace_cli.slides_create_presentation_from_markdown directly." in prompt
        assert 'Example: {"prompt":"Create investor slides for PermitFlow AI","title":"PermitFlow AI"}' in prompt
        assert "<tool>googleworkspace_cli.slides_create_presentation_from_markdown</tool>" not in prompt

    def test_telegram_chat_payload_includes_native_and_skill_tools(self):
        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response("Hello from CATBot")
        fake_skill_tools_openai = [
            {
                "type": "function",
                "function": {
                    "name": "filesystem.read_text",
                    "description": "read",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        fake_skill_tools_mcp = [
            {"name": "filesystem.read_text", "description": "read", "inputSchema": {"type": "object", "properties": {}}}
        ]

        def getenv(k, d=None):
            if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"):
                return "test-key"
            return os.environ.get(k, d) if d is not None else os.environ.get(k)

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            with patch("src.servers.proxy_server._get_skill_tools_openai_schema", return_value=fake_skill_tools_openai):
                with patch("src.servers.proxy_server._get_skill_tools_mcp_schema", return_value=fake_skill_tools_mcp):
                    with patch("src.servers.proxy_server.os.getenv", side_effect=getenv):
                        with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                            mock_client_instance = MagicMock()
                            mock_client_instance.post = AsyncMock(return_value=mock_response)
                            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                            mock_aclient.return_value = mock_client_instance

                            resp = client.post(
                                "/v1/telegram/chat",
                                json={"message": "Use tools", "conversation_id": "tool-payload-test"},
                            )

        assert resp.status_code == 200, resp.text
        payload = mock_client_instance.post.await_args_list[0].kwargs["json"]
        tool_names = {tool["function"]["name"] for tool in payload["tools"]}
        assert payload["tool_choice"] == "auto"
        assert "runBrowserAgent" in tool_names
        assert "createSlidesPresentation" in tool_names
        assert "pdfToPowerPoint" in tool_names
        assert "filesystem.read_text" in tool_names

    def test_telegram_combined_openai_tools_excludes_raw_slides_skill(self):
        from src.servers import proxy_server as ps

        fake_skill_tools_openai = [
            {
                "type": "function",
                "function": {
                    "name": "googleworkspace_cli.slides_create_presentation_from_markdown",
                    "description": "create slides from markdown",
                    "parameters": {"type": "object", "properties": {"markdown_path": {"type": "string"}}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "filesystem.read_text",
                    "description": "read",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

        with patch("src.servers.proxy_server._get_skill_tools_openai_schema", return_value=fake_skill_tools_openai):
            tools = ps._get_telegram_combined_openai_tools()

        tool_names = {tool["function"]["name"] for tool in tools}
        assert "createSlidesPresentation" in tool_names
        assert "filesystem.read_text" in tool_names
        assert "googleworkspace_cli.slides_create_presentation_from_markdown" not in tool_names

    def test_tool_followup_payload_keeps_unified_tool_schemas(self):
        client = _get_client()
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "webSearch",
                                    "arguments": '{"query": "test query"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": "Final answer"}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10},
        }
        fake_skill_tools_openai = [
            {
                "type": "function",
                "function": {
                    "name": "filesystem.read_text",
                    "description": "read",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        fake_skill_tools_mcp = [
            {"name": "filesystem.read_text", "description": "read", "inputSchema": {"type": "object", "properties": {}}}
        ]

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            with patch("src.servers.proxy_server._get_skill_tools_openai_schema", return_value=fake_skill_tools_openai):
                with patch("src.servers.proxy_server._get_skill_tools_mcp_schema", return_value=fake_skill_tools_mcp):
                    with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                        mock_search.return_value = {"results": [{"title": "Test", "snippet": "Snippet"}]}
                        with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                            m_getenv.side_effect = lambda k, d=None: (
                                "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                            )
                            with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                                mock_client_instance = MagicMock()
                                mock_client_instance.post = AsyncMock(side_effect=[mock_first, mock_second])
                                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                                mock_aclient.return_value = mock_client_instance

                                resp = client.post(
                                    "/v1/telegram/chat",
                                    json={"message": "Search for test", "conversation_id": "tool-followup-payload"},
                                )

        assert resp.status_code == 200, resp.text
        followup_payload = mock_client_instance.post.await_args_list[1].kwargs["json"]
        tool_names = {tool["function"]["name"] for tool in followup_payload["tools"]}
        assert followup_payload["tool_choice"] == "auto"
        assert "webSearch" in tool_names
        assert "pdfToPowerPoint" in tool_names
        assert "filesystem.read_text" in tool_names

    def test_no_api_key_returns_503(self):
        """POST when neither OPENAI_API_KEY nor MCP_LLM_OPENAI_API_KEY is set returns 503."""
        client = _get_client()
        with patch("src.servers.proxy_server.os.getenv") as m_getenv:
            missing_key_names = {
                "OPENAI_API_KEY",
                "MCP_LLM_OPENAI_API_KEY",
                "MINIMAX_API_KEY",
                "MCP_LLM_MINIMAX_API_KEY",
            }
            m_getenv.side_effect = (
                lambda k, d=None: None if k in missing_key_names else os.environ.get(k, d)
            )
            resp = client.post(
                "/v1/telegram/chat",
                json={"message": "Hi"},
            )
        assert resp.status_code == 503
        assert "OPENAI" in resp.text or "MCP_LLM" in resp.text


class TestTelegramClearEndpoint:
    """Tests for DELETE /v1/telegram/chat/{conversation_id}."""

    def test_clear_unknown_id_returns_200_cleared_false(self):
        """DELETE for unknown conversation_id returns 200 with cleared: false."""
        client = _get_client()
        resp = client.delete("/v1/telegram/chat/unknown-id-999")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("conversation_id") == "unknown-id-999"
        assert data.get("cleared") is False

    def test_clear_after_chat_returns_200_cleared_true(self):
        """After a chat with conversation_id, DELETE returns 200 with cleared: true."""
        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response("Hi")

        with patch("src.servers.proxy_server.os.getenv") as m_getenv:
            m_getenv.side_effect = lambda k, d=None: "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
            with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                mock_client_instance = MagicMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_aclient.return_value = mock_client_instance

                client.post(
                    "/v1/telegram/chat",
                    json={"message": "Hi", "conversation_id": "clear-me"},
                )
                resp = client.delete("/v1/telegram/chat/clear-me")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("cleared") is True


class TestTelegramSecret:
    """Tests for TELEGRAM_SECRET validation when set."""

    def test_unset_secret_rejects_non_loopback_request(self):
        """When TELEGRAM_SECRET is unset, non-loopback callers still need CATBot auth."""
        from fastapi import HTTPException
        from src.servers import proxy_server as ps

        request = MagicMock()
        request.headers = {}
        request.client.host = "203.0.113.10"

        with patch.object(ps, "TELEGRAM_SECRET", None):
            with pytest.raises(HTTPException) as exc_info:
                ps._validate_telegram_secret(request)

        assert exc_info.value.status_code == 401

    def test_when_secret_set_missing_header_returns_401(self):
        """When TELEGRAM_SECRET is set, request without secret returns 401."""
        client = _get_client()
        with patch("src.servers.proxy_server.TELEGRAM_SECRET", "my-secret"):
            resp = client.post(
                "/v1/telegram/chat",
                json={"message": "Hi"},
            )
        assert resp.status_code == 401
        assert "secret" in resp.text.lower() or "invalid" in resp.text.lower()

    def test_when_secret_set_correct_header_succeeds(self):
        """When TELEGRAM_SECRET is set, X-Telegram-Secret header allows request."""
        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response("OK")

        with patch("src.servers.proxy_server.TELEGRAM_SECRET", "my-secret"):
            with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                m_getenv.side_effect = lambda k, d=None: "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                    mock_client_instance = MagicMock()
                    mock_client_instance.post = AsyncMock(return_value=mock_response)
                    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                    mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                    mock_aclient.return_value = mock_client_instance

                    resp = client.post(
                        "/v1/telegram/chat",
                        json={"message": "Hi"},
                        headers={"X-Telegram-Secret": "my-secret"},
                    )
        assert resp.status_code == 200

    def test_delete_when_secret_set_requires_header(self):
        """DELETE when TELEGRAM_SECRET is set requires X-Telegram-Secret."""
        client = _get_client()
        with patch("src.servers.proxy_server.TELEGRAM_SECRET", "my-secret"):
            resp = client.delete("/v1/telegram/chat/some-id")
        assert resp.status_code == 401


class TestTelegramToolsLoop:
    """Tests for Telegram tool loop when TELEGRAM_TOOLS_ENABLED is True."""

    def test_format_telegram_tool_status_uses_human_friendly_copy(self):
        from src.servers import proxy_server as ps

        assert ps._format_telegram_tool_status("webSearch") == "On it. I'm looking for the best sources now."
        assert ps._format_telegram_tool_status("runDeepResearch") == "On it. I'm gathering sources and comparing them now."
        assert ps._format_telegram_tool_status("run_deep_research") == "On it. I'm gathering sources and comparing them now."
        assert ps._format_telegram_tool_status("createSlidesPresentation") == "On it. I'm building the presentation now."
        assert ps._format_telegram_tool_status("pdfToPowerPoint") == "On it. I'm converting the document into a PowerPoint now."
        assert ps._format_telegram_tool_status("health_check") == "On it. I'm checking the browser task status now."
        assert ps._format_telegram_tool_status("filesystem.write_text") == (
            "On it. I'm checking the workspace files now."
        )
        assert ps._format_telegram_tool_status("GitHubProjectManager.list_issues") == (
            "On it. I'm checking GitHub for that now."
        )
        assert ps._format_telegram_tool_status("googleworkspace_cli.gmail_list_unread") == (
            "On it. I'm checking your Google Workspace data now."
        )
        fallback = ps._format_telegram_tool_status("customTool\n<script>")
        assert fallback == "On it. I'm using customTool script for that now."

    def test_tool_loop_executes_native_tool_calls_and_returns_final_reply(self):
        """When LLM returns native message.tool_calls, proxy executes tools and returns final reply."""
        client = _get_client()
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "webSearch",
                                    "arguments": '{"query": "test query"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        final_response = "Here are the search results: [summary]."
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": final_response}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10},
        }
        mock_third = MagicMock()
        mock_third.status_code = 200
        mock_third.json.return_value = {
            "choices": [{"message": {"content": "All actions are now completed"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        post_calls = [mock_first, mock_second, mock_third]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_third

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {"results": [{"title": "Test", "snippet": "Snippet"}]}
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-native-test"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == final_response

    def test_tool_loop_with_think_wrapped_xml_still_executes_tool(self):
        """Tool XML in a response that also includes <think> blocks should still execute."""
        client = _get_client()
        tool_response = (
            "<think>I'll call search</think>\n"
            '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        )
        final_response = "<think>done</think>\nHere is the final result."

        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": final_response}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        mock_third = MagicMock()
        mock_third.status_code = 200
        mock_third.json.return_value = {
            "choices": [{"message": {"content": "All actions are now completed"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        post_calls = [mock_first, mock_second, mock_third]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_third

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {
                    "results": [{"title": "Test", "snippet": "Snippet", "url": "https://example.com"}]
                }
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "think-tool-loop"},
                        )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "Here is the final result."
        mock_search.assert_awaited_once()
        assert data.get("conversation_id") == "think-tool-loop"

    def test_tool_loop_executes_tool_and_returns_final_reply(self):
        """When LLM returns a tool call, proxy executes tool and sends result back; second LLM reply is returned."""
        client = _get_client()
        # First LLM response: tool call
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        # Second LLM response: natural language after seeing tool result
        final_response = "Here are the search results: [summary]."
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": final_response}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10},
        }
        mock_third = MagicMock()
        mock_third.status_code = 200
        mock_third.json.return_value = {
            "choices": [{"message": {"content": "All actions are now completed"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        post_calls = [mock_first, mock_second, mock_third]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_third

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {"results": [{"title": "Test", "snippet": "Snippet"}]}
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-test"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Final reply should be the second LLM response (natural language)
        assert data.get("reply") == final_response
        assert data.get("conversation_id") == "tools-test"

    def test_tool_loop_handles_structured_followup_content(self):
        """Tool-loop follow-up content parts should be normalized to text instead of failing response validation."""
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "Here are the search results."},
                            {"type": "text", "text": "Summary line 2."},
                        ]
                    }
                }
            ],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10},
        }
        mock_third = MagicMock()
        mock_third.status_code = 200
        mock_third.json.return_value = {
            "choices": [{"message": {"content": "All actions are now completed"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        post_calls = [mock_first, mock_second, mock_third]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_third

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {"results": [{"title": "Test", "snippet": "Snippet"}]}
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-structured-test"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "Here are the search results.\nSummary line 2."
        assert data.get("conversation_id") == "tools-structured-test"

    def test_tool_loop_keeps_mixed_final_reply_instead_of_error_fallback(self):
        """
        When follow-up text includes user-facing content plus incidental tool XML,
        the final reply should be delivered (with XML stripped), not replaced by
        the generic tool-error fallback.
        """
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        mixed_final = (
            "Here are the search results summary.\n"
            '<tool>webSearch</tool>\n<parameters>{"query":"next query"}</parameters>'
        )
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": mixed_final}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10},
        }
        mock_third = MagicMock()
        mock_third.status_code = 200
        mock_third.json.return_value = {
            "choices": [{"message": {"content": "All actions are now completed"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        post_calls = [mock_first, mock_second, mock_third]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_third

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {"results": [{"title": "Test", "snippet": "Snippet"}]}
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-mixed-final"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "Here are the search results summary."
        assert data.get("reply") != "I wasn't able to get that information just now. Please try again or rephrase your question."

    def test_tool_loop_executes_mixed_planning_reply_that_contains_next_tool(self):
        """
        If a chatty model wraps the next real tool call in planning prose, the loop
        should still execute the tool instead of treating the prose as the final answer.
        """
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        mixed_followup = (
            "I have the search results and will now scrape the URLs for more detail.\n"
            "<tool>scrapeWebsite</tool>\n"
            '<parameters>{"urls":["https://example.com/1","https://example.com/2"]}</parameters>'
        )
        final_response = "Here is the scraped summary."
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": mixed_followup}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 15},
        }
        mock_third = MagicMock()
        mock_third.status_code = 200
        mock_third.json.return_value = {
            "choices": [{"message": {"content": final_response}}],
            "usage": {"prompt_tokens": 25, "completion_tokens": 12},
        }
        mock_fourth = MagicMock()
        mock_fourth.status_code = 200
        mock_fourth.json.return_value = {
            "choices": [{"message": {"content": "All actions are now completed"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        post_calls = [mock_first, mock_second, mock_third, mock_fourth]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_fourth

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search, patch(
                "src.servers.proxy_server._do_proxy_fetch", new_callable=AsyncMock
            ) as mock_fetch:
                mock_search.return_value = {
                    "results": [
                        {"title": "Result 1", "snippet": "Snippet 1", "url": "https://example.com/1"},
                        {"title": "Result 2", "snippet": "Snippet 2", "url": "https://example.com/2"},
                    ]
                }
                mock_fetch.return_value = {
                    "success": True,
                    "url": "https://example.com/1",
                    "title": "Example",
                    "content": "Scraped content",
                }
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-mixed-planning-next-tool"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == final_response
        mock_search.assert_awaited_once()
        mock_fetch.assert_awaited_once()


class TestBrowserAgentProxy:
    @pytest.mark.asyncio
    async def test_do_browser_agent_maps_instruction_alias_to_task(self):
        from src.servers import proxy_server as ps

        health_response = MagicMock()
        health_response.status_code = 200

        post_response = MagicMock()
        post_response.status_code = 200
        post_response.headers = {"content-type": "application/json"}
        post_response.json.return_value = {"success": True, "message": "ok"}

        health_client = MagicMock()
        health_client.get = AsyncMock(return_value=health_response)
        health_client.__aenter__ = AsyncMock(return_value=health_client)
        health_client.__aexit__ = AsyncMock(return_value=None)

        post_client = MagicMock()
        post_client.post = AsyncMock(return_value=post_response)
        post_client.__aenter__ = AsyncMock(return_value=post_client)
        post_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.servers.proxy_server._get_mcp_browser_server_url", return_value="http://127.0.0.1:5001"), patch(
            "src.servers.proxy_server.MCP_BROWSER_SERVER_SHARED_SECRET",
            "bridge-secret",
        ), patch("src.servers.proxy_server.httpx.AsyncClient", side_effect=[health_client, post_client]):
            result = await ps._do_browser_agent({"instruction": "Open example.com"})

        assert result["success"] is True
        posted_json = post_client.post.await_args.kwargs["json"]
        assert posted_json["task"] == "Open example.com"
        assert post_client.post.await_args.kwargs["headers"] == {
            "Content-Type": "application/json",
            "X-Agent-Secret": "bridge-secret",
        }

    def test_tool_loop_does_not_infer_next_tool_from_planning_text(self):
        """
        The backend should not infer the next tool from planning text alone.
        It should stop on the last concrete tool result unless the model emits
        the next tool call explicitly.
        """
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        planning_reply = "I have the search results. Now I will use those URLs to scrape the content from each one."
        scrape_tool_response = (
            "<tool>scrapeWebsite</tool>\n"
            '<parameters>{"urls":["https://example.com/1","https://example.com/2"]}</parameters>'
        )
        final_response = "Here is the scraped summary."
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": planning_reply}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        mock_third = MagicMock()
        mock_third.status_code = 200
        mock_third.json.return_value = {
            "choices": [{"message": {"content": scrape_tool_response}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 15},
        }
        mock_fourth = MagicMock()
        mock_fourth.status_code = 200
        mock_fourth.json.return_value = {
            "choices": [{"message": {"content": final_response}}],
            "usage": {"prompt_tokens": 25, "completion_tokens": 12},
        }
        mock_fifth = MagicMock()
        mock_fifth.status_code = 200
        mock_fifth.json.return_value = {
            "choices": [{"message": {"content": "All actions are now completed"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        post_calls = [mock_first, mock_second, mock_third, mock_fourth, mock_fifth]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_fifth

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search, patch(
                "src.servers.proxy_server._do_proxy_fetch", new_callable=AsyncMock
            ) as mock_fetch:
                mock_search.return_value = {
                    "results": [
                        {"title": "Result 1", "snippet": "Snippet 1", "url": "https://example.com/1"},
                        {"title": "Result 2", "snippet": "Snippet 2", "url": "https://example.com/2"},
                    ]
                }
                mock_fetch.return_value = {
                    "success": True,
                    "url": "https://example.com/1",
                    "title": "Example",
                    "content": "Scraped content",
                }
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-followup-auto-continue"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply", "").startswith("Here's what I found:")
        assert "Search results:" in data.get("reply", "")
        mock_search.assert_awaited_once()
        mock_fetch.assert_not_awaited()

    def test_tool_loop_uses_last_tool_result_when_followup_is_only_planning(self):
        """
        If the follow-up model reply is only planning chatter, the backend should
        stop and return the last concrete tool result instead of continuing to self-prompt.
        """
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        planning_reply = "Thank you for the search results. I will now scrape the content from the URLs provided."
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": planning_reply}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        responses = [mock_first, mock_second]

        def next_response(*args, **kwargs):
            return responses.pop(0) if responses else mock_second

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search, patch(
                "src.servers.proxy_server._do_proxy_fetch", new_callable=AsyncMock
            ) as mock_fetch:
                mock_search.return_value = {
                    "results": [
                        {"title": "Result 1", "snippet": "Snippet 1", "url": "https://example.com/1"},
                        {"title": "Result 2", "snippet": "Snippet 2", "url": "https://example.com/2"},
                    ]
                }
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-no-self-check-fallback"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply", "").startswith("Here's what I found:")
        assert "Search results:" in data.get("reply", "")
        mock_search.assert_awaited_once()
        mock_fetch.assert_not_awaited()

    def test_tool_loop_followup_prompt_includes_direct_answer_rules_and_latest_tool_result(self):
        """
        The follow-up prompt should tell the model to return one tool call or a final answer,
        and it should include the latest tool result in the working message history.
        """
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "employee redundancy headlines"}</parameters>'
        final_response = "Here are the redundancy headlines."
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": final_response}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        responses = [mock_first, mock_second]
        captured_payloads = []

        def next_response(*args, **kwargs):
            captured_payloads.append(kwargs.get("json"))
            return responses.pop(0) if responses else mock_second

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {
                    "results": [
                        {"title": "Headline 1", "snippet": "Snippet 1", "url": "https://example.com/1"},
                        {"title": "Headline 2", "snippet": "Snippet 2", "url": "https://example.com/2"},
                    ]
                }
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={
                                "message": "Search the web for employee redundancy headlines",
                                "conversation_id": "tools-followup-controller-prompt",
                            },
                        )
        assert resp.status_code == 200, resp.text
        assert len(captured_payloads) >= 2
        followup_payload = captured_payloads[1]
        followup_messages = followup_payload.get("messages") or []
        followup_text = "\n".join(str(msg.get("content") or "") for msg in followup_messages if isinstance(msg, dict))
        assert "Return exactly one of these two outputs" in followup_text
        assert "Do not narrate plans, next steps, or intentions." in followup_text
        assert "If the latest tool result already answers the request, summarize it directly for the user." in followup_text
        assert "https://example.com/1" in followup_text
        assert "https://example.com/2" in followup_text

    def test_tool_loop_does_not_issue_extra_self_check_roundtrip(self):
        """
        Planning chatter after a tool result should not trigger an extra backend
        self-check request. The loop should stop after the normal follow-up turn.
        """
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "employee redundancy headlines"}</parameters>'
        planning_reply = "I found the search results and will gather the URLs I need next."
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": planning_reply}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        responses = [mock_first, mock_second]
        captured_payloads = []

        def next_response(*args, **kwargs):
            captured_payloads.append(kwargs.get("json"))
            return responses.pop(0) if responses else mock_second

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {
                    "results": [
                        {"title": "Headline 1", "snippet": "Snippet 1", "url": "https://example.com/1"},
                        {"title": "Headline 2", "snippet": "Snippet 2", "url": "https://example.com/2"},
                    ]
                }
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={
                                "message": "Search the web for employee redundancy headlines",
                                "conversation_id": "tools-no-self-check-extra-roundtrip",
                            },
                        )
        assert resp.status_code == 200, resp.text
        assert len(captured_payloads) == 2

    def test_tool_loop_replaces_planning_chatter_with_last_tool_result(self):
        """
        If follow-up reply is only planning chatter after a successful tool execution,
        return the last tool result instead of sending the chatter to the user.
        """
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        planning_reply = "Let me see what Gmail commands are available."
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": planning_reply}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        post_calls = [mock_first, mock_second]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_second

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {
                    "results": [{"title": "Test", "snippet": "Snippet", "url": "https://example.com"}]
                }
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-planning-fallback"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply", "").startswith("Here's what I found:")
        assert "Search results:" in data.get("reply", "")

    def test_tool_loop_replaces_planning_chatter_after_tool_error(self):
        """
        If follow-up reply is planning chatter after a failed tool call,
        return a user-safe error reply instead of the chatter.
        """
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        planning_reply = "Let me fix that - I need to adjust the parameters:"
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": planning_reply}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        post_calls = [mock_first, mock_second]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_second

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.side_effect = RuntimeError("Failed to fetch content: timeout")
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-planning-error-fallback"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "I wasn't able to get that information just now. Please try again or rephrase your question."

    def test_tool_loop_replaces_planning_chatter_when_iteration_cap_reached(self):
        """
        Planning chatter should still be replaced when the loop stops due TELEGRAM_TOOLS_MAX_ITERATIONS.
        """
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        planning_reply = "Let me fetch the next details for you:"
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": planning_reply}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        post_calls = [mock_first, mock_second]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_second

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True), patch(
            "src.servers.proxy_server.TELEGRAM_TOOLS_MAX_ITERATIONS", 1
        ):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {
                    "results": [{"title": "Test", "snippet": "Snippet", "url": "https://example.com"}]
                }
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-planning-cap"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply", "").startswith("Here's what I found:")
        assert "Search results:" in data.get("reply", "")

    def test_tool_loop_run_deep_research_rejects_overlap_for_same_conversation(self):
        """When a deep-research run is already active for a conversation, second adhoc run is rejected."""
        client = _get_client()
        tool_response = '<tool>runDeepResearch</tool>\n<parameters>{"researchTask": "test"}</parameters>'
        final_response = "A deep research request is already running for this chat."
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": final_response}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }
        mock_third = MagicMock()
        mock_third.status_code = 200
        mock_third.json.return_value = {
            "choices": [{"message": {"content": "All actions are now completed"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        post_calls = [mock_first, mock_second, mock_third]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_third

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")

            active = {
                "busy-conv": {
                    "request_id": "existing-request",
                    "started_at_ts": time.time(),
                    "started_at": "2026-03-09T09:21:00+00:00",
                }
            }
            with patch("src.servers.proxy_server.telegram_deep_research_active", active):
                with patch("src.servers.proxy_server._do_deep_research", new_callable=AsyncMock) as mock_research:
                    with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                        m_getenv.side_effect = lambda k, d=None: (
                            "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                        )
                        with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                            mock_client_instance = MagicMock()
                            mock_client_instance.post = AsyncMock(side_effect=next_response)
                            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                            mock_aclient.return_value = mock_client_instance

                            resp = client.post(
                                "/v1/telegram/chat",
                                json={"message": "run deep research", "conversation_id": "busy-conv"},
                            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == final_response
        mock_research.assert_not_awaited()


class TestIsTodoListQuery:
    """Tests for _is_todo_list_query (skip memory injection for todo-list requests)."""

    def test_todo_list_phrases_return_true(self):
        """Phrases asking for current todo list return True."""
        from src.servers.proxy_server import _is_todo_list_query
        assert _is_todo_list_query("What's on my todo list?") is True
        assert _is_todo_list_query("Show my tasks") is True
        assert _is_todo_list_query("list my tasks") is True
        assert _is_todo_list_query("my todo list") is True
        assert _is_todo_list_query("what are my tasks") is True
        assert _is_todo_list_query("what is due today?") is True
        assert _is_todo_list_query("show overdue tasks") is True

    def test_unrelated_queries_return_false(self):
        """Unrelated messages return False."""
        from src.servers.proxy_server import _is_todo_list_query
        assert _is_todo_list_query("What's the weather?") is False
        assert _is_todo_list_query("Search for AI news") is False
        assert _is_todo_list_query("") is False


class TestTelegramSkillPromptBlock:
    """Tests for dynamic Telegram skill-tool prompt rendering."""

    def test_skill_prompt_includes_gmail_examples_when_tools_available(self):
        from src.servers import proxy_server as ps

        fake_tools = [
            {
                "name": "googleworkspace_cli.gmail_list_unread",
                "description": "List unread messages.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "googleworkspace_cli.run_readonly_command",
                "description": "Generic fallback command.",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
        with patch("src.servers.proxy_server._get_skill_tools_mcp_schema", return_value=fake_tools):
            block = ps._build_telegram_skill_tools_prompt_block()

        assert "Gmail tool examples" in block
        assert "<tool>googleworkspace_cli.gmail_list_unread</tool>" in block
        assert "<tool>googleworkspace_cli.gmail_list_all</tool>" in block
        assert "<tool>googleworkspace_cli.gmail_get_message</tool>" in block
        assert "googleworkspace_cli.run_readonly_command" not in block


class TestResolveTodoUserForTelegram:
    """Tests for _resolve_todo_user_for_telegram (Telegram -> app username linking)."""

    def test_linked_user_id_returns_app_username(self):
        """When links file maps Telegram user_id to username, resolver returns username."""
        from src.servers import proxy_server as ps
        links_content = '{"6644154165": "andyjm2k"}'
        with patch.object(ps, "TELEGRAM_USER_LINKS_FILE") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = links_content
            out = ps._resolve_todo_user_for_telegram("6644154165", "6644154165")
        assert out == "andyjm2k"

    def test_no_link_returns_conversation_id(self):
        """When no mapping exists, resolver returns conversation_id (or user_id)."""
        from src.servers import proxy_server as ps
        with patch.object(ps, "TELEGRAM_USER_LINKS_FILE") as mock_path:
            mock_path.exists.return_value = False
            out = ps._resolve_todo_user_for_telegram("6644154165", "6644154165")
        assert out == "6644154165"

    def test_user_id_normalized_to_string(self):
        """user_id sent as number is normalized to string for lookup."""
        from src.servers import proxy_server as ps
        links_content = '{"6644154165": "andyjm2k"}'
        with patch.object(ps, "TELEGRAM_USER_LINKS_FILE") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = links_content
            # Simulate Pydantic/JSON giving int
            out = ps._resolve_todo_user_for_telegram("6644154165", 6644154165)
        assert out == "andyjm2k"


class TestTelegramTaskExecutionNotifications:
    """Tests for Telegram notification helpers used by task execution completion flow."""

    def test_resolve_telegram_chat_ids_for_todo_user_reverses_links(self):
        from src.servers import proxy_server as ps
        links_content = '{"6644154165": "andyjm2k", "-100123": "andyjm2k", "group_alpha": "andyjm2k"}'
        with patch.object(ps, "TELEGRAM_USER_LINKS_FILE") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = links_content
            out = ps._resolve_telegram_chat_ids_for_todo_user("andyjm2k")
        assert out == ["6644154165", "-100123"]

    def test_task_execution_register_telegram_target_adds_chat_id_once(self):
        from src.servers import proxy_server as ps
        user_key = "notify-user-1"
        ps.task_execution_state[user_key] = {"task_id": 1, "status": "executing", "telegram_chat_ids": ["111"]}
        try:
            ok1 = ps._task_execution_register_telegram_target(user_key, "222")
            ok2 = ps._task_execution_register_telegram_target(user_key, "222")
            assert ok1 is True
            assert ok2 is True
            state = ps._get_task_run_state(user_key, 1)
            assert state is not None
            assert state["telegram_chat_ids"] == ["111", "222"]
        finally:
            ps.task_execution_state.pop(user_key, None)

    @pytest.mark.asyncio
    async def test_run_task_loop_background_notifies_on_scheduled_completion(self):
        from src.servers import proxy_server as ps

        class _Executor:
            async def run_loop(self):
                return (ps.STATUS_AWAITING_CONFIRMATION, "Execution complete.")

        user_key = "notify-user-2"
        executor = _Executor()
        ps.task_execution_state[user_key] = {
            "task_id": 3,
            "status": ps.STATUS_EXECUTING,
            "executor": executor,
            "message": None,
            "task_description": "Scheduled task demo",
            "is_scheduled": True,
            "telegram_chat_ids": ["6644154165"],
        }
        try:
            with patch.object(ps, "_write_task_exec_response_to_scratch") as mock_write:
                with patch.object(ps, "_send_telegram_bot_message", new=AsyncMock(return_value=True)) as mock_send:
                    with patch.object(ps, "_todo_store") as mock_store:
                        mock_store.complete_task.return_value = {
                            "rescheduled": True,
                            "next_run_at": "2026-03-02T09:00:00+00:00",
                        }
                        await ps._run_task_loop_background(user_key, 3, executor)
            assert user_key not in ps.task_execution_state
            mock_store.complete_task.assert_called_once_with(user_key, 3)
            mock_write.assert_called_once()
            mock_send.assert_awaited_once()
        finally:
            ps.task_execution_state.pop(user_key, None)

    @pytest.mark.asyncio
    async def test_run_task_loop_background_records_learning_outcome(self):
        from src.servers import proxy_server as ps

        class _Executor:
            async def run_loop(self):
                return (ps.STATUS_AWAITING_CONFIRMATION, "I have finished the work for this task.")

            def get_run_diagnostics(self):
                return {
                    "iterations": 2,
                    "max_iterations": 20,
                    "elapsed_seconds": 1.5,
                    "tool_usage_counts": {"write_file": 1},
                    "tool_success_count": 1,
                    "tool_failure_count": 0,
                    "tool_error_messages": [],
                    "last_error": None,
                }

        user_key = "learning-user-1"
        executor = _Executor()
        ps.task_execution_state[user_key] = {
            "task_id": 2,
            "status": ps.STATUS_EXECUTING,
            "executor": executor,
            "message": None,
            "task_description": "Write summary file",
            "is_scheduled": False,
            "telegram_chat_ids": [],
        }
        mock_memory_manager = MagicMock()
        mock_memory_manager.record_task_outcome = AsyncMock(return_value={"outcome": "success"})
        try:
            with patch.object(ps, "MEMORY_AVAILABLE", True):
                with patch.object(ps, "memory_manager", mock_memory_manager):
                    with patch.object(ps, "_write_task_exec_response_to_scratch"):
                        with patch.object(ps, "_maybe_notify_telegram_task_completion", new=AsyncMock(return_value=None)):
                            await ps._run_task_loop_background(user_key, 2, executor)
            mock_memory_manager.record_task_outcome.assert_awaited_once()
            kwargs = mock_memory_manager.record_task_outcome.await_args.kwargs
            assert kwargs.get("task_description") == "Write summary file"
            assert kwargs.get("status") == ps.STATUS_AWAITING_CONFIRMATION
        finally:
            ps.task_execution_state.pop(user_key, None)

    @pytest.mark.asyncio
    async def test_run_task_loop_background_clears_unscheduled_terminal_state(self):
        from src.servers import proxy_server as ps

        class _Executor:
            async def run_loop(self):
                return (ps.STATUS_AWAITING_CONFIRMATION, "Finished run.")

        user_key = "terminal-clear-user"
        executor = _Executor()
        ps.task_execution_state[user_key] = {
            "task_id": 4,
            "status": ps.STATUS_EXECUTING,
            "executor": executor,
            "message": None,
            "task_description": "Terminal clear test",
            "is_scheduled": False,
            "telegram_chat_ids": [],
        }
        try:
            with patch.object(ps, "_write_task_exec_response_to_scratch"):
                with patch.object(ps, "_maybe_notify_telegram_task_completion", new=AsyncMock(return_value=None)):
                    await ps._run_task_loop_background(user_key, 4, executor)
            assert user_key not in ps.task_execution_state
        finally:
            ps.task_execution_state.pop(user_key, None)

    def test_task_execute_cancel_marks_state_cancelled_immediately(self):
        from src.servers import proxy_server as ps

        class _Executor:
            def __init__(self):
                self.cancelled = False

            def request_cancel(self):
                self.cancelled = True

        user_key = "cancel-now-user"
        executor = _Executor()
        ps.task_execution_state[user_key] = {
            "task_id": 9,
            "status": ps.STATUS_EXECUTING,
            "executor": executor,
            "message": None,
        }
        try:
            ok, msg, cancelled_task_id = ps._task_execute_cancel(user_key)
            assert ok is True
            assert "Cancellation requested" in msg
            assert cancelled_task_id == 9
            assert executor.cancelled is True
            state = ps._get_task_run_state(user_key, 9)
            assert state is not None
            assert state["status"] == ps.STATUS_CANCELLED
        finally:
            ps.task_execution_state.pop(user_key, None)

    def test_task_execution_status_clears_terminal_state(self):
        from src.servers import proxy_server as ps

        user_key = "status-clear-user"
        ps.task_execution_state[user_key] = {
            "task_id": 2,
            "status": ps.STATUS_CANCELLED,
            "message": "Cancellation requested.",
        }
        out = ps._task_execution_status(user_key)
        assert out is None
        assert user_key not in ps.task_execution_state

    def test_task_execution_status_lists_multiple_active_task_ids(self):
        from src.servers import proxy_server as ps

        user_key = "status-multi-user"
        ps.task_execution_state[user_key] = {
            "runs": {
                2: {"task_id": 2, "status": ps.STATUS_EXECUTING, "message": "Running task 2"},
                4: {"task_id": 4, "status": ps.STATUS_PAUSED_AWAITING_FEEDBACK, "message": "Need input"},
            }
        }
        try:
            out = ps._task_execution_status(user_key)
            assert out is not None
            assert out.get("status") == "multiple"
            assert out.get("task_ids") == [2, 4]
        finally:
            ps.task_execution_state.pop(user_key, None)

    def test_task_execute_cancel_requires_task_id_when_multiple_active(self):
        from src.servers import proxy_server as ps

        class _Executor:
            def request_cancel(self):
                return None

        user_key = "cancel-multi-user"
        ps.task_execution_state[user_key] = {
            "runs": {
                1: {"task_id": 1, "status": ps.STATUS_EXECUTING, "executor": _Executor()},
                2: {"task_id": 2, "status": ps.STATUS_EXECUTING, "executor": _Executor()},
            }
        }
        try:
            ok, msg, cancelled_task_id = ps._task_execute_cancel(user_key)
            assert ok is False
            assert cancelled_task_id is None
            assert "Multiple active tasks" in msg
        finally:
            ps.task_execution_state.pop(user_key, None)


class TestTelegramFileSendSecurity:
    """Tests for Telegram scratch-file sending preconditions."""

    @pytest.mark.asyncio
    async def test_send_telegram_file_internal_does_not_require_proxy_auth(self, monkeypatch):
        """send file helper should proceed without proxy auth checks and validate next requirements."""
        from src.servers import proxy_server as ps
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        out = await ps._send_telegram_file_internal(
            chat_id="123456",
            filename="report.txt",
        )
        assert out.get("success") is False
        assert "telegram_bot_token is not configured" in out.get("message", "").lower()


class TestPhilosopherFileTools:
    """Tests for file manipulation tools in philosopher mode (get_all_available_tools + execute_tool_for_philosopher)."""

    @pytest.mark.asyncio
    async def test_filesystem_skill_tools_included_in_tool_list(self):
        """get_all_available_tools should expose filesystem skill tools and omit retired native duplicates."""
        from src.servers import proxy_server as ps
        with patch.object(ps, "MCP_AVAILABLE", False):
            tools = await ps.get_all_available_tools()
        names = [t.get("name") for t in tools]
        assert "filesystem.read_text" in names
        assert "filesystem.write_text" in names
        assert "filesystem.list_files" in names
        assert "filesystem.search_files" in names
        assert "delete_file" in names
        assert "read_file" not in names
        assert "write_file" not in names
        assert "list_files" not in names
        assert "search_files" not in names

    @pytest.mark.asyncio
    async def test_html_client_native_tools_included_for_desktop_parity(self):
        """Desktop /v1/tools/openai should include the same native tool names as the HTML client."""
        from src.servers import proxy_server as ps

        with patch.object(ps, "MCP_AVAILABLE", False):
            tools = await ps.get_all_available_tools()
        names = {str(tool.get("name") or "") for tool in tools}

        assert set(ps._HTML_CLIENT_NATIVE_TOOL_NAMES).issubset(names)
        assert "resumeTodoExecution" in names
        assert "completeTodoTask" in names
        assert "health_check" in names

    @pytest.mark.asyncio
    async def test_html_resume_todo_execution_tool_uses_task_resume_helper(self):
        """The desktop-compatible resumeTodoExecution alias should execute, not only list."""
        from src.servers import proxy_server as ps

        with patch.object(
            ps,
            "_task_execute_resume",
            new=AsyncMock(return_value=("awaiting_confirmation", "Task resumed.", 42)),
        ) as mock_resume:
            result = await ps.execute_tool_for_philosopher(
                "resumeTodoExecution",
                {"userMessage": "continue with that", "taskId": 42, "user_id": "desktop_user"},
            )

        assert result == "Task resumed."
        mock_resume.assert_awaited_once_with("desktop_user", "continue with that", 42)

    @pytest.mark.asyncio
    async def test_html_complete_todo_task_tool_uses_completion_helper(self):
        """The desktop-compatible completeTodoTask alias should call the authenticated todo completion path."""
        from src.servers import proxy_server as ps

        with patch.object(
            ps,
            "_task_complete_for_tool",
            new=AsyncMock(return_value={"success": True, "message": "Task completion recorded.", "data": {}}),
        ) as mock_complete:
            result = await ps.execute_tool_for_philosopher(
                "completeTodoTask",
                {"taskId": 42, "user_id": "desktop_user"},
            )

        assert result == "Task completion recorded."
        mock_complete.assert_awaited_once_with("desktop_user", 42)

    @pytest.mark.asyncio
    async def test_filesystem_skill_tools_are_not_filtered(self):
        """Filesystem skill tools should remain visible now that native duplicates are retired."""
        from src.servers import proxy_server as ps

        raw_tools = [
            {"name": "filesystem.list_files", "description": "list"},
            {"name": "filesystem.read_text", "description": "read"},
            {"name": "filesystem.write_text", "description": "write"},
            {"name": "filesystem.search_files", "description": "search"},
            {"name": "core.ping", "description": "ping"},
        ]
        filtered = ps._filter_overlapping_file_skill_tools(raw_tools, openai_schema=False)
        names = [item.get("name") for item in filtered]
        assert "core.ping" in names
        assert "filesystem.list_files" in names
        assert "filesystem.read_text" in names
        assert "filesystem.write_text" in names
        assert "filesystem.search_files" in names

    @pytest.mark.asyncio
    async def test_execute_filesystem_list_files_returns_string(self):
        """execute_tool_for_philosopher filesystem.list_files returns a readable string."""
        from src.servers import proxy_server as ps
        result = await ps.execute_tool_for_philosopher("filesystem.list_files", {})
        assert isinstance(result, str)
        assert "scratch" in result.lower() or "empty" in result.lower() or "Files" in result

    @pytest.mark.asyncio
    async def test_execute_filesystem_list_files_truncates_when_limit_set(self, monkeypatch):
        """execute_tool_for_philosopher filesystem.list_files should cap rendered rows for large directories."""
        from src.servers import proxy_server as ps
        monkeypatch.setenv("LIST_FILES_TOOL_MAX_ENTRIES", "3")

        fake_result = {
            "success": True,
            "message": "OK",
            "data": {
                "items": [
                    {"name": "images", "relative_path": "images", "type": "directory", "size_bytes": None},
                    {"name": "a.txt", "relative_path": "a.txt", "type": "file", "size_bytes": 1},
                    {"name": "b.txt", "relative_path": "b.txt", "type": "file", "size_bytes": 2},
                    {"name": "c.txt", "relative_path": "c.txt", "type": "file", "size_bytes": 3},
                    {"name": "d.txt", "relative_path": "d.txt", "type": "file", "size_bytes": 4},
                ],
                "max_entries": 3,
            },
        }

        with patch.object(ps, "_execute_skill_framework_tool", new=AsyncMock(return_value=fake_result)):
            result = await ps.execute_tool_for_philosopher("filesystem.list_files", {})
        assert isinstance(result, str)
        assert "images/ [dir]" in result
        assert "a.txt (1 bytes)" in result
        assert "b.txt (2 bytes)" in result
        assert "... and 2 more files in this page." in result
        assert "Continue with offset=3" in result
        assert "c.txt (3 bytes)" not in result
        assert "d.txt (4 bytes)" not in result

    @pytest.mark.asyncio
    async def test_execute_filesystem_list_files_forwards_arguments(self):
        """execute_tool_for_philosopher filesystem.list_files forwards arguments into the skill executor."""
        from src.servers import proxy_server as ps

        fake_result = {
            "success": True,
            "message": "OK",
            "data": {
                "items": [{"name": "a.png", "relative_path": "images/a.png", "type": "file", "size_bytes": 10}],
            },
        }

        with patch.object(ps, "_execute_skill_framework_tool", new=AsyncMock(return_value=fake_result)) as mock_exec:
            result = await ps.execute_tool_for_philosopher(
                "filesystem.list_files",
                {"path": "images", "recursive": "true", "offset": 2, "max_entries": 5},
            )
        mock_exec.assert_awaited_once_with(
            tool_name="filesystem.list_files",
            arguments={"path": "images", "recursive": "true", "offset": 2, "max_entries": 5},
            conversation_id="",
            user_id="",
            metadata={"channel": "philosopher"},
        )
        assert isinstance(result, str)
        assert "images/a.png (10 bytes)" in result

    @pytest.mark.asyncio
    async def test_execute_filesystem_search_files_formats_matches(self):
        """execute_tool_for_philosopher filesystem.search_files should format skill matches cleanly."""
        from src.servers import proxy_server as ps

        fake_result = {
            "success": True,
            "message": "OK",
            "data": {
                "query": "alpha",
                "items": [
                    {
                        "relative_path": "docs/notes.txt",
                        "match_types": ["content"],
                        "line_number": 3,
                        "excerpt": "...alpha topic...",
                    }
                ],
                "offset": 2,
                "next_offset": 3,
                "has_more": True,
            },
        }

        with patch.object(ps, "_execute_skill_framework_tool", new=AsyncMock(return_value=fake_result)) as mock_exec:
            result = await ps.execute_tool_for_philosopher(
                "filesystem.search_files",
                {"query": "alpha", "path": "docs", "recursive": False, "offset": 2, "max_results": 5},
            )
        mock_exec.assert_awaited_once_with(
            tool_name="filesystem.search_files",
            arguments={"query": "alpha", "path": "docs", "recursive": False, "offset": 2, "max_results": 5},
            conversation_id="",
            user_id="",
            metadata={"channel": "philosopher"},
        )
        assert isinstance(result, str)
        assert "docs/notes.txt [content] line 3: ...alpha topic..." in result
        assert "filesystem.read_text" in result

    @pytest.mark.asyncio
    async def test_execute_skill_tool_prefers_descriptive_message_over_data_dump(self):
        """Non-filesystem skill tools should return their readable message without appending raw JSON."""
        from src.servers import proxy_server as ps

        fake_result = {
            "success": True,
            "message": "Created Google Slides deck 'PermitFlow AI' with 12 slide(s). Open: https://docs.google.com/presentation/d/pres_123/edit",
            "data": {
                "presentationId": "pres_123",
                "presentationUrl": "https://docs.google.com/presentation/d/pres_123/edit",
                "slides": [{"title": "Intro"}],
            },
        }

        with patch.object(ps, "_execute_skill_framework_tool", new=AsyncMock(return_value=fake_result)):
            result = await ps.execute_tool_for_philosopher(
                "googleworkspace_cli.slides_create_presentation_from_markdown",
                {"title": "PermitFlow AI"},
            )

        assert result == fake_result["message"]
        assert '"presentationId"' not in result

    @pytest.mark.asyncio
    async def test_execute_skill_tool_falls_back_to_data_for_placeholder_message(self):
        """Generic placeholder messages should still fall back to the returned skill data."""
        from src.servers import proxy_server as ps

        fake_result = {
            "success": True,
            "message": "OK",
            "data": {
                "presentationId": "pres_123",
                "presentationUrl": "https://docs.google.com/presentation/d/pres_123/edit",
            },
        }

        with patch.object(ps, "_execute_skill_framework_tool", new=AsyncMock(return_value=fake_result)):
            result = await ps.execute_tool_for_philosopher(
                "googleworkspace_cli.slides_create_presentation_from_markdown",
                {"title": "PermitFlow AI"},
            )

        assert '"presentationId": "pres_123"' in result
        assert '"presentationUrl": "https://docs.google.com/presentation/d/pres_123/edit"' in result

    @pytest.mark.asyncio
    async def test_run_workflow_tool_included_when_autogen_available(self):
        """When AUTOGEN_AVAILABLE is True, get_all_available_tools includes runWorkflow."""
        from src.servers import proxy_server as ps
        with patch.object(ps, "MCP_AVAILABLE", False):
            tools = await ps.get_all_available_tools()
        names = [t.get("name") for t in tools]
        if getattr(ps, "AUTOGEN_AVAILABLE", False):
            assert "runWorkflow" in names
        # If AutoGen not available, runWorkflow may be absent; test just ensures no crash

    @pytest.mark.asyncio
    async def test_execute_run_workflow_requires_content_prompt(self):
        """execute_tool_for_philosopher runWorkflow without contentPrompt returns error message."""
        from src.servers import proxy_server as ps
        result = await ps.execute_tool_for_philosopher("runWorkflow", {})
        assert isinstance(result, str)
        assert "contentPrompt" in result or "required" in result.lower()

    @pytest.mark.asyncio
    async def test_run_deep_research_tool_included_when_browser_use_configured(self):
        """When MCP_BROWSER_USE_HTTP_URL is set, get_all_available_tools includes run_deep_research."""
        from src.servers import proxy_server as ps
        with patch.object(ps, "MCP_AVAILABLE", False):
            with patch.object(ps, "MCP_BROWSER_USE_HTTP_URL", "http://127.0.0.1:8383/mcp"):
                tools = await ps.get_all_available_tools()
        names = [t.get("name") for t in tools]
        assert "run_deep_research" in names
        assert "health_check" in names

    @pytest.mark.asyncio
    async def test_execute_run_deep_research_requires_research_task(self):
        """execute_tool_for_philosopher run_deep_research without research_task returns error."""
        from src.servers import proxy_server as ps
        result = await ps.execute_tool_for_philosopher("run_deep_research", {})
        assert isinstance(result, str)
        assert "research_task" in result or "researchTask" in result or "required" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_health_check_returns_json_payload(self):
        """execute_tool_for_philosopher health_check should return parsed JSON text when backend succeeds."""
        from src.servers import proxy_server as ps
        fake = {
            "success": True,
            "message": "Browser-use status: healthy. Running tasks: 1. Uptime: 10.0s.",
            "result": {
                "status": "healthy",
                "running_tasks": 1,
                "tasks": [{"task_id": "abcd1234", "tool": "run_deep_research"}],
            },
        }
        with patch.object(ps, "_do_browser_health_check", new=AsyncMock(return_value=fake)):
            result = await ps.execute_tool_for_philosopher("health_check", {})
        assert isinstance(result, str)
        assert '"status": "healthy"' in result
        assert '"running_tasks": 1' in result


class TestProxyFetchUrls:
    """Tests for POST /v1/proxy/fetch with optional urls (scrape-with-retry)."""

    def test_fetch_with_urls_tries_until_success(self):
        """POST with urls list tries each URL until one succeeds."""
        from src.servers import proxy_server as ps
        client = _get_client()
        call_log = []

        async def mock_fetch(url, **kwargs):
            call_log.append(url)
            if "fail" in url:
                raise Exception("404 Not Found")
            return {"content": "Content from " + url}

        with patch.object(ps, "_do_proxy_fetch", new=AsyncMock(side_effect=mock_fetch)):
            resp = client.post(
                "/v1/proxy/fetch",
                json={"urls": ["https://fail.first/page", "https://ok.second/page"]},
                headers=_auth_headers(),
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("content") == "Content from https://ok.second/page"
        assert len(call_log) == 2

    def test_fetch_with_urls_retries_on_http_exception(self):
        """POST with urls retries on HTTPException failures from _do_proxy_fetch."""
        from src.servers import proxy_server as ps
        client = _get_client()

        async def mock_fetch(url, **kwargs):
            if "fail" in url:
                raise ps.HTTPException(status_code=500, detail="temporary failure")
            return {"content": "Content from " + url}

        with patch.object(ps, "_do_proxy_fetch", new=AsyncMock(side_effect=mock_fetch)):
            resp = client.post(
                "/v1/proxy/fetch",
                json={"urls": ["https://fail.first/page", "https://ok.second/page"]},
                headers=_auth_headers(),
            )
        assert resp.status_code == 200, resp.text
        assert resp.json().get("content") == "Content from https://ok.second/page"

    def test_fetch_with_single_url_unchanged(self):
        """POST with single url still works (backward compatible)."""
        from src.servers import proxy_server as ps
        client = _get_client()
        with patch.object(ps, "_do_proxy_fetch", new=AsyncMock(return_value={"content": "Hello"})):
            resp = client.post("/v1/proxy/fetch", json={"url": "https://example.com"}, headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.json().get("content") == "Hello"

    def test_fetch_forwards_dynamic_render_parameters(self):
        """POST /v1/proxy/fetch forwards JS-render parameters to _do_proxy_fetch."""
        from src.servers import proxy_server as ps
        client = _get_client()
        with patch.object(ps, "_do_proxy_fetch", new=AsyncMock(return_value={"content": "Hello"})) as mock_fetch:
            resp = client.post(
                "/v1/proxy/fetch",
                json={
                    "url": "https://example.com",
                    "crawl": False,
                    "max_pages": 1,
                    "max_depth": 0,
                    "render_js": True,
                    "render_engine": "playwright",
                    "wait_for_selector": ".status-table",
                    "js_wait_ms": 3500,
                },
                headers=_auth_headers(),
            )
        assert resp.status_code == 200, resp.text
        mock_fetch.assert_awaited_once_with(
            "https://example.com",
            crawl=False,
            max_pages=1,
            max_depth=0,
            render_js=True,
            render_engine="playwright",
            wait_for_selector=".status-table",
            js_wait_ms=3500,
        )

    def test_fetch_no_url_no_urls_returns_400(self):
        """POST without url or urls returns 400."""
        client = _get_client()
        resp = client.post("/v1/proxy/fetch", json={}, headers=_auth_headers())
        assert resp.status_code == 400

    def test_fetch_requires_auth(self):
        """POST /v1/proxy/fetch without auth or agent secret returns 401."""
        client = _get_client()
        resp = client.post("/v1/proxy/fetch", json={"url": "https://example.com"})
        assert resp.status_code == 401

    def test_fetch_accepts_agent_secret(self):
        """POST /v1/proxy/fetch accepts the internal AutoGen team secret."""
        from src.servers import proxy_server as ps
        client = _get_client()
        with patch.object(ps, "AUTOGEN_TEAM_SECRET", "agent-secret"), patch.object(
            ps, "_do_proxy_fetch", new=AsyncMock(return_value={"content": "Hello"})
        ):
            resp = client.post(
                "/v1/proxy/fetch",
                json={"url": "https://example.com"},
                headers={"X-Agent-Secret": "agent-secret"},
            )
        assert resp.status_code == 200, resp.text


class TestBrowserHealthProxy:
    """Tests for POST /v1/proxy/browser-health."""

    def test_browser_health_proxy_returns_backend_payload(self):
        """Proxy should return the normalized browser health payload from backend helper."""
        from src.servers import proxy_server as ps
        client = _get_client()
        fake = {
            "success": True,
            "message": "Browser-use status: healthy. Running tasks: 0. Uptime: 5.0s.",
            "result": {"status": "healthy", "running_tasks": 0, "tasks": []},
        }
        with patch.object(ps, "_do_browser_health_check", new=AsyncMock(return_value=fake)):
            resp = client.post("/v1/proxy/browser-health", json={}, headers=_auth_headers())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("success") is True
        assert data.get("result", {}).get("status") == "healthy"

    def test_browser_health_requires_auth(self):
        """POST /v1/proxy/browser-health without auth or agent secret returns 401."""
        client = _get_client()
        resp = client.post("/v1/proxy/browser-health", json={})
        assert resp.status_code == 401


class TestDeepResearchProxy:
    """Tests for deep-research proxy body normalization and forwarding."""

    def test_normalize_deep_research_body_maps_camel_case_aliases(self):
        from src.servers import proxy_server as ps

        out = ps._normalize_deep_research_body(
            {"researchTask": "Find competitor pricing", "maxParallelBrowsers": 4, "topic": "ignored"}
        )

        assert out["research_task"] == "Find competitor pricing"
        assert out["max_parallel_browsers"] == 4
        assert "researchTask" not in out
        assert "maxParallelBrowsers" not in out

    @pytest.mark.asyncio
    async def test_do_deep_research_forwards_snake_case_body(self):
        from src.servers import proxy_server as ps

        captured = {}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "message": "ok"}
        mock_response.headers = {"content-type": "application/json"}

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, url, json=None, headers=None):
                captured["url"] = url
                captured["json"] = json
                captured["headers"] = headers
                return mock_response

        with patch.object(ps, "_monitor_run_start", return_value="deep-research-test"), patch.object(
            ps, "_monitor_run_note"
        ), patch.object(ps, "_monitor_run_finish"), patch.object(
            ps, "_get_mcp_browser_server_url", return_value="http://127.0.0.1:5001"
        ), patch.object(ps, "MCP_BROWSER_SERVER_SHARED_SECRET", "bridge-secret"), patch.object(
            ps.httpx, "AsyncClient", return_value=_Client()
        ):
            result = await ps._do_deep_research(
                {"researchTask": "Find competitor pricing", "maxParallelBrowsers": 4}
            )

        assert result == {"success": True, "message": "ok"}
        assert captured["url"] == "http://127.0.0.1:5001/api/deep-research"
        assert captured["json"] == {
            "research_task": "Find competitor pricing",
            "max_parallel_browsers": 4,
        }
        assert captured["headers"] == {
            "Content-Type": "application/json",
            "X-Agent-Secret": "bridge-secret",
        }

    @pytest.mark.asyncio
    async def test_do_deep_research_promotes_report_to_message(self):
        from src.servers import proxy_server as ps

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "report": "Final research report"}
        mock_response.headers = {"content-type": "application/json"}

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, url, json=None, headers=None):
                return mock_response

        with patch.object(ps, "_monitor_run_start", return_value="deep-research-test"), patch.object(
            ps, "_monitor_run_note"
        ), patch.object(ps, "_monitor_run_finish"), patch.object(
            ps, "_get_mcp_browser_server_url", return_value="http://127.0.0.1:5001"
        ), patch.object(ps, "MCP_BROWSER_SERVER_SHARED_SECRET", "bridge-secret"), patch.object(
            ps.httpx, "AsyncClient", return_value=_Client()
        ):
            result = await ps._do_deep_research({"researchTask": "Find competitor pricing"})

        assert result["message"] == "Final research report"


class TestBrowserAgentProxy:
    """Tests for browser-agent proxy body normalization and response shaping."""

    @pytest.mark.asyncio
    async def test_do_browser_agent_promotes_result_to_message(self):
        from src.servers import proxy_server as ps

        captured = {}
        health_response = MagicMock()
        health_response.status_code = 200
        post_response = MagicMock()
        post_response.status_code = 200
        post_response.json.return_value = {"success": True, "result": "Explicit browser result"}
        post_response.headers = {"content-type": "application/json"}

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def get(self, url):
                captured["health_url"] = url
                return health_response

            async def post(self, url, json=None, headers=None):
                captured["url"] = url
                captured["json"] = json
                captured["headers"] = headers
                return post_response

        with patch.object(ps, "_monitor_run_start", return_value="browser-agent-test"), patch.object(
            ps, "_monitor_run_note"
        ), patch.object(ps, "_monitor_run_finish"), patch.object(
            ps, "_get_mcp_browser_server_url", return_value="http://127.0.0.1:5001"
        ), patch.object(ps, "MCP_BROWSER_SERVER_SHARED_SECRET", "bridge-secret"), patch.object(
            ps.httpx, "AsyncClient", return_value=_Client()
        ):
            result = await ps._do_browser_agent({"instruction": "Open the page and find the answer"})

        assert captured["url"] == "http://127.0.0.1:5001/api/browser-agent"
        assert captured["json"] == {"instruction": "Open the page and find the answer", "task": "Open the page and find the answer"}
        assert captured["headers"] == {
            "Content-Type": "application/json",
            "X-Agent-Secret": "bridge-secret",
        }
        assert result["message"] == "Explicit browser result"
