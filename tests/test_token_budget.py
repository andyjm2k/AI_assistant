"""
Unit tests for token budget helpers.
"""

import os

import pytest

from src.utils import token_budget


def test_estimate_tokens_from_text_uses_chars_per_token(monkeypatch):
    monkeypatch.setenv("TOKEN_ESTIMATE_CHARS_PER_TOKEN", "4")
    assert token_budget.estimate_tokens_from_text("1234") == 1
    assert token_budget.estimate_tokens_from_text("12345") == 2


def test_estimate_tokens_from_messages_adds_overhead(monkeypatch):
    monkeypatch.setenv("TOKEN_ESTIMATE_CHARS_PER_TOKEN", "4")
    messages = [
        {"role": "system", "content": "abcd"},
        {"role": "user", "content": "efgh"},
    ]
    est = token_budget.estimate_tokens_from_messages(messages)
    assert est >= 2  # base tokens
    assert est > 2   # overhead included


def test_is_context_limit_error_matches_messages():
    assert token_budget.is_context_limit_error(400, "context length exceeded")
    assert token_budget.is_context_limit_error(413, "too many tokens")
    assert not token_budget.is_context_limit_error(500, "context length exceeded")
    assert not token_budget.is_context_limit_error(400, "internal error")
