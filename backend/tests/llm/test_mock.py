"""Tests for mock-mode determinism — covers the four canned scenarios that the
integration-tester depends on.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from app.llm import handle_chat_message, mock_response


class TestMockResponseScenarios:
    def test_executed_trade(self) -> None:
        r = mock_response("Please buy 5 AAPL")
        assert "AAPL" in r.message
        assert len(r.trades) == 1
        assert r.trades[0].ticker == "AAPL"
        assert r.trades[0].side == "buy"
        assert r.trades[0].quantity == 5

    def test_rejected_trade_insufficient_cash(self) -> None:
        r = mock_response("buy 1000000 AAPL")
        assert len(r.trades) == 1
        assert r.trades[0].quantity == 1_000_000
        # Watchlist changes must be empty
        assert r.watchlist_changes == []

    def test_watchlist_add_executed(self) -> None:
        r = mock_response("watch PYPL please")
        assert len(r.watchlist_changes) == 1
        assert r.watchlist_changes[0].ticker == "PYPL"
        assert r.watchlist_changes[0].action == "add"
        assert r.trades == []

    def test_watchlist_add_unknown_ticker(self) -> None:
        r = mock_response("watch ZZZZZ for me")
        assert len(r.watchlist_changes) == 1
        assert r.watchlist_changes[0].ticker == "ZZZZZ"
        assert r.watchlist_changes[0].action == "add"
        assert r.trades == []

    def test_default_fallback(self) -> None:
        r = mock_response("hello there")
        assert r.message
        assert r.trades == []
        assert r.watchlist_changes == []

    def test_determinism_same_input_same_output(self) -> None:
        # Critical for E2E tests: identical input must yield identical output
        for prompt in (
            "buy 5 AAPL",
            "watch PYPL",
            "watch ZZZZZ",
            "buy 1000000 AAPL",
            "tell me about my portfolio",
        ):
            a = mock_response(prompt)
            b = mock_response(prompt)
            assert a.model_dump() == b.model_dump()


class TestMockModeWiredThroughHandler:
    """When LLM_MOCK=true, the real LiteLLM call must not happen."""

    def test_handler_uses_mock_when_env_var_set(self, deps) -> None:  # type: ignore[no-untyped-def]
        with patch.dict(os.environ, {"LLM_MOCK": "true"}):
            with patch("app.llm.client.call_llm") as fake_real:
                result = handle_chat_message("default", "buy 5 AAPL", deps=deps)
        # call_llm must NEVER be invoked in mock mode
        fake_real.assert_not_called()
        assert "AAPL" in result["message"]
        # Trade should have been auto-executed
        assert len(result["actions"]["trades"]) == 1
        assert result["actions"]["trades"][0]["status"] == "executed"

    def test_handler_calls_real_when_mock_disabled(self, deps) -> None:  # type: ignore[no-untyped-def]
        from app.llm.schemas import LLMResponse

        with patch.dict(os.environ, {"LLM_MOCK": "false"}):
            stub = lambda _msgs: LLMResponse(message="hi")  # noqa: E731
            result = handle_chat_message("default", "hello", deps=deps, llm_caller=stub)
        assert result["message"] == "hi"
