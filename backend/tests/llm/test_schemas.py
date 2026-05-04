"""Tests for the LLM structured-output schemas + parser."""

from __future__ import annotations

import json

from app.llm import LLMResponse
from app.llm.client import parse_response


class TestParseResponse:
    def test_valid_full_response(self) -> None:
        raw = json.dumps(
            {
                "message": "Buying 5 AAPL.",
                "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}],
                "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
            }
        )
        out = parse_response(raw)
        assert isinstance(out, LLMResponse)
        assert out.message == "Buying 5 AAPL."
        assert len(out.trades) == 1
        assert out.trades[0].ticker == "AAPL"
        assert out.trades[0].side == "buy"
        assert out.trades[0].quantity == 5
        assert len(out.watchlist_changes) == 1
        assert out.watchlist_changes[0].action == "add"

    def test_missing_optional_fields(self) -> None:
        # Only ``message`` is required; trades/watchlist_changes default to []
        raw = json.dumps({"message": "Just chatting."})
        out = parse_response(raw)
        assert out.message == "Just chatting."
        assert out.trades == []
        assert out.watchlist_changes == []

    def test_empty_arrays(self) -> None:
        raw = json.dumps({"message": "Hi", "trades": [], "watchlist_changes": []})
        out = parse_response(raw)
        assert out.trades == []
        assert out.watchlist_changes == []

    def test_dict_input_also_accepted(self) -> None:
        out = parse_response({"message": "ok"})
        assert out.message == "ok"

    def test_malformed_json_returns_fallback(self) -> None:
        # Not JSON at all
        out = parse_response("not json at all {{{")
        assert isinstance(out, LLMResponse)
        # Fallback message must be non-empty and contain no actions
        assert out.message
        assert out.trades == []
        assert out.watchlist_changes == []

    def test_empty_string_returns_fallback(self) -> None:
        out = parse_response("")
        assert isinstance(out, LLMResponse)
        assert out.message
        assert out.trades == []

    def test_missing_message_field_returns_fallback(self) -> None:
        # ``message`` is required — schema validation should fail and we fall
        # back to the safe default.
        raw = json.dumps({"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}]})
        out = parse_response(raw)
        assert isinstance(out, LLMResponse)
        # The safe fallback never auto-executes anything
        assert out.trades == []

    def test_invalid_side_rejected_via_fallback_path(self) -> None:
        raw = json.dumps(
            {
                "message": "ok",
                "trades": [{"ticker": "AAPL", "side": "yolo", "quantity": 1}],
            }
        )
        out = parse_response(raw)
        # Best-effort path can't construct a TradeRequest with side="yolo";
        # we should land in the fallback which yields no trades.
        assert isinstance(out, LLMResponse)
        assert out.trades == []
