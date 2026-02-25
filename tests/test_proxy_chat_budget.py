"""
Unit tests for proxy chat budget helpers.
"""

from src.servers import proxy_server


def test_normalize_chat_endpoint_appends_path():
    base = "http://localhost:1234/v1"
    assert proxy_server._normalize_chat_endpoint(base) == "http://localhost:1234/v1/chat/completions"
    already = "http://localhost:1234/v1/chat/completions"
    assert proxy_server._normalize_chat_endpoint(already) == already


def test_get_max_tokens_from_payload():
    assert proxy_server._get_max_tokens_from_payload({"max_tokens": 100}) == 100
    assert proxy_server._get_max_tokens_from_payload({"max_tokens": "200"}) == 200
    assert proxy_server._get_max_tokens_from_payload({"max_tokens": None}) == 0
    assert proxy_server._get_max_tokens_from_payload({"max_tokens": "bad"}) == 0
