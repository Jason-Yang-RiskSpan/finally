"""Tests for the chat handler: auto-execution wiring, persistence, history window."""

from __future__ import annotations

import os
from unittest.mock import patch

from app.llm import (
    HISTORY_LIMIT,
    LLMResponse,
    TradeRequest,
    WatchlistChange,
    handle_chat_message,
)


def _stub(response: LLMResponse):
    """Helper: produce an llm_caller callable that always returns ``response``."""
    return lambda _messages: response


class TestAutoExecutionWiring:
    def test_two_trades_and_one_watchlist_invokes_each_primitive_once(self, deps):  # type: ignore[no-untyped-def]
        response = LLMResponse(
            message="Executing your trades.",
            trades=[
                TradeRequest(ticker="AAPL", side="buy", quantity=5),
                TradeRequest(ticker="MSFT", side="sell", quantity=2),
            ],
            watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
        )
        # Make execute_trade return distinct prices so we can verify wiring
        deps.trade_response = lambda u, t, s, q: {"status": "executed", "price": 100.0 + q}

        result = handle_chat_message("default", "do it", deps=deps, llm_caller=_stub(response))

        # Each primitive called exactly once with correct args
        assert deps.trade_calls == [
            ("default", "AAPL", "buy", 5),
            ("default", "MSFT", "sell", 2),
        ]
        assert deps.watchlist_add_calls == [("default", "PYPL")]
        assert deps.watchlist_remove_calls == []

        # Returned actions reflect status + price
        assert len(result["actions"]["trades"]) == 2
        assert result["actions"]["trades"][0]["status"] == "executed"
        assert result["actions"]["trades"][0]["price"] == 105.0
        assert result["actions"]["trades"][1]["price"] == 102.0
        assert len(result["actions"]["watchlist_changes"]) == 1
        assert result["actions"]["watchlist_changes"][0]["status"] == "executed"

    def test_watchlist_remove_routed_to_remove_primitive(self, deps):  # type: ignore[no-untyped-def]
        response = LLMResponse(
            message="Removing.",
            watchlist_changes=[WatchlistChange(ticker="META", action="remove")],
        )
        handle_chat_message("default", "drop meta", deps=deps, llm_caller=_stub(response))
        assert deps.watchlist_remove_calls == [("default", "META")]
        assert deps.watchlist_add_calls == []

    def test_ticker_normalized_to_uppercase(self, deps):  # type: ignore[no-untyped-def]
        response = LLMResponse(
            message="ok",
            trades=[TradeRequest(ticker="aapl", side="buy", quantity=1)],
            watchlist_changes=[WatchlistChange(ticker="pypl", action="add")],
        )
        handle_chat_message("default", "x", deps=deps, llm_caller=_stub(response))
        assert deps.trade_calls[0][1] == "AAPL"
        assert deps.watchlist_add_calls[0][1] == "PYPL"


class TestRejectionWiring:
    def test_insufficient_cash_lands_in_actions(self, deps):  # type: ignore[no-untyped-def]
        response = LLMResponse(
            message="Trying.",
            trades=[TradeRequest(ticker="AAPL", side="buy", quantity=1_000_000)],
        )
        deps.trade_response = lambda *_: {
            "status": "rejected",
            "reason": "insufficient_cash",
        }

        result = handle_chat_message(
            "default", "buy a million", deps=deps, llm_caller=_stub(response)
        )

        assert len(result["actions"]["trades"]) == 1
        t = result["actions"]["trades"][0]
        assert t["status"] == "rejected"
        assert t["reason"] == "insufficient_cash"
        assert t["ticker"] == "AAPL"
        assert t["quantity"] == 1_000_000

    def test_unknown_ticker_lands_in_actions(self, deps):  # type: ignore[no-untyped-def]
        response = LLMResponse(
            message="Trying.",
            watchlist_changes=[WatchlistChange(ticker="ZZZZZ", action="add")],
        )
        deps.watchlist_add_response = lambda *_: {
            "status": "rejected",
            "reason": "unknown_ticker",
        }

        result = handle_chat_message(
            "default", "watch zzzzz", deps=deps, llm_caller=_stub(response)
        )

        assert len(result["actions"]["watchlist_changes"]) == 1
        w = result["actions"]["watchlist_changes"][0]
        assert w["status"] == "rejected"
        assert w["reason"] == "unknown_ticker"
        assert w["ticker"] == "ZZZZZ"

    def test_backend_exception_caught_per_item(self, deps):  # type: ignore[no-untyped-def]
        # Defensive: a backend that raises shouldn't crash the handler
        response = LLMResponse(
            message="ok",
            trades=[TradeRequest(ticker="AAPL", side="buy", quantity=1)],
        )

        def boom(*_):
            raise RuntimeError("db gone")

        deps.trade_response = boom
        result = handle_chat_message("default", "x", deps=deps, llm_caller=_stub(response))
        t = result["actions"]["trades"][0]
        assert t["status"] == "rejected"
        assert "internal_error" in t["reason"]


class TestHistoryWindowing:
    def test_only_last_20_messages_passed_to_llm(self, deps):  # type: ignore[no-untyped-def]
        # Seed 30 messages of history
        for i in range(30):
            deps.history.append(
                {
                    "user_id": "default",
                    "role": "user" if i % 2 == 0 else "assistant",
                    "content": f"msg-{i}",
                }
            )

        captured: dict = {}

        def capture(messages):
            captured["msgs"] = messages
            return LLMResponse(message="ok")

        handle_chat_message("default", "new turn", deps=deps, llm_caller=capture)

        msgs = captured["msgs"]
        # 1 system + at most HISTORY_LIMIT history + 1 new user
        # (history is fetched AFTER appending the user message; we strip the
        # tail echo, so at most HISTORY_LIMIT - 1 historical messages remain
        # plus the explicit final user message).
        assert msgs[0]["role"] == "system"
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "new turn"

        history_in_prompt = msgs[1:-1]
        assert len(history_in_prompt) <= HISTORY_LIMIT
        # And only the most-recent slice — earliest seeded msgs must be gone
        contents = {m["content"] for m in history_in_prompt}
        assert "msg-0" not in contents
        assert "msg-1" not in contents


class TestPersistence:
    def test_user_and_assistant_messages_both_written(self, deps):  # type: ignore[no-untyped-def]
        response = LLMResponse(
            message="Got it.",
            trades=[TradeRequest(ticker="AAPL", side="buy", quantity=1)],
        )
        deps.trade_response = lambda *_: {"status": "executed", "price": 191.42}

        handle_chat_message("default", "buy 1 AAPL", deps=deps, llm_caller=_stub(response))

        roles = [a[1] for a in deps.appended]
        assert roles == ["user", "assistant"]
        # User message has no actions
        assert deps.appended[0][2] == "buy 1 AAPL"
        assert deps.appended[0][3] is None
        # Assistant message stored with actions matching execution outcome
        assert deps.appended[1][2] == "Got it."
        actions = deps.appended[1][3]
        assert actions is not None
        assert len(actions["trades"]) == 1
        assert actions["trades"][0]["status"] == "executed"
        assert actions["trades"][0]["price"] == 191.42

    def test_assistant_actions_match_mixed_outcomes(self, deps):  # type: ignore[no-untyped-def]
        response = LLMResponse(
            message="Mixed bag.",
            trades=[
                TradeRequest(ticker="AAPL", side="buy", quantity=1),
                TradeRequest(ticker="TSLA", side="buy", quantity=999_999),
            ],
            watchlist_changes=[
                WatchlistChange(ticker="PYPL", action="add"),
                WatchlistChange(ticker="ZZZZZ", action="add"),
            ],
        )

        def trade_resp(u, t, s, q):
            if t == "TSLA":
                return {"status": "rejected", "reason": "insufficient_cash"}
            return {"status": "executed", "price": 191.42}

        def add_resp(u, t):
            if t == "ZZZZZ":
                return {"status": "rejected", "reason": "unknown_ticker"}
            return {"status": "executed"}

        deps.trade_response = trade_resp
        deps.watchlist_add_response = add_resp

        handle_chat_message("default", "do it all", deps=deps, llm_caller=_stub(response))

        assistant_actions = deps.appended[1][3]
        assert assistant_actions is not None
        statuses_t = [t["status"] for t in assistant_actions["trades"]]
        assert statuses_t == ["executed", "rejected"]
        statuses_w = [w["status"] for w in assistant_actions["watchlist_changes"]]
        assert statuses_w == ["executed", "rejected"]
        assert assistant_actions["trades"][1]["reason"] == "insufficient_cash"
        assert assistant_actions["watchlist_changes"][1]["reason"] == "unknown_ticker"


class TestEmptyMessage:
    def test_empty_string_short_circuits(self, deps):  # type: ignore[no-untyped-def]
        result = handle_chat_message("default", "   ", deps=deps, llm_caller=_stub(LLMResponse(message="x")))
        assert "non-empty" in result["message"].lower()
        # No persistence, no LLM call
        assert deps.appended == []
        assert deps.trade_calls == []


class TestMockModeFullPipeline:
    """End-to-end: each canned mock scenario produces correct ``actions``."""

    def test_executed_trade_pipeline(self, deps):  # type: ignore[no-untyped-def]
        with patch.dict(os.environ, {"LLM_MOCK": "true"}):
            r = handle_chat_message("default", "buy 5 AAPL", deps=deps)
        assert r["actions"]["trades"][0]["status"] == "executed"
        assert r["actions"]["trades"][0]["ticker"] == "AAPL"

    def test_rejected_trade_pipeline(self, deps):  # type: ignore[no-untyped-def]
        deps.trade_response = lambda *_: {
            "status": "rejected",
            "reason": "insufficient_cash",
        }
        with patch.dict(os.environ, {"LLM_MOCK": "true"}):
            r = handle_chat_message("default", "buy 1000000 AAPL", deps=deps)
        assert r["actions"]["trades"][0]["status"] == "rejected"
        assert r["actions"]["trades"][0]["reason"] == "insufficient_cash"

    def test_watchlist_add_pipeline(self, deps):  # type: ignore[no-untyped-def]
        with patch.dict(os.environ, {"LLM_MOCK": "true"}):
            r = handle_chat_message("default", "watch PYPL", deps=deps)
        assert r["actions"]["watchlist_changes"][0]["status"] == "executed"
        assert r["actions"]["watchlist_changes"][0]["ticker"] == "PYPL"

    def test_unknown_ticker_pipeline(self, deps):  # type: ignore[no-untyped-def]
        deps.watchlist_add_response = lambda *_: {
            "status": "rejected",
            "reason": "unknown_ticker",
        }
        with patch.dict(os.environ, {"LLM_MOCK": "true"}):
            r = handle_chat_message("default", "watch ZZZZZ", deps=deps)
        assert r["actions"]["watchlist_changes"][0]["status"] == "rejected"
        assert r["actions"]["watchlist_changes"][0]["reason"] == "unknown_ticker"
