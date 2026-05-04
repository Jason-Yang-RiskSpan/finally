"""Tests for the LiteLLM/Cerebras call site.

We stub ``litellm.completion`` since these tests must run offline.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.llm import LLMResponse
from app.llm.client import EXTRA_BODY, MODEL, call_llm


def _fake_completion(content: str) -> MagicMock:
    """Build a fake response object that matches LiteLLM's shape."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class TestCallLLM:
    def test_calls_completion_with_cerebras_pattern(self) -> None:
        content = json.dumps({"message": "ok", "trades": [], "watchlist_changes": []})
        with patch("litellm.completion") as fake:
            fake.return_value = _fake_completion(content)
            messages = [{"role": "user", "content": "hi"}]
            out = call_llm(messages)

        # Verify the canonical Cerebras pattern from the skill is used:
        kwargs = fake.call_args.kwargs
        assert kwargs["model"] == MODEL == "openrouter/openai/gpt-oss-120b"
        assert kwargs["messages"] == messages
        assert kwargs["extra_body"] == EXTRA_BODY
        assert kwargs["extra_body"]["provider"]["order"] == ["cerebras"]
        assert kwargs["reasoning_effort"] == "low"
        assert kwargs["response_format"] is LLMResponse

        # Verify parsed result
        assert isinstance(out, LLMResponse)
        assert out.message == "ok"

    def test_malformed_response_returns_fallback(self) -> None:
        with patch("litellm.completion") as fake:
            fake.return_value = _fake_completion("not json {{{")
            out = call_llm([{"role": "user", "content": "hi"}])
        # Fallback never auto-executes anything
        assert isinstance(out, LLMResponse)
        assert out.trades == []
        assert out.watchlist_changes == []
