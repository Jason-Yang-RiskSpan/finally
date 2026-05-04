"""Tests for prompt construction and portfolio-context formatting."""

from __future__ import annotations

from app.llm.prompt import SYSTEM_PROMPT, build_messages, format_portfolio_context


class TestFormatPortfolioContext:
    def test_empty_portfolio(self) -> None:
        text = format_portfolio_context(
            {"cash_balance": 10000.0, "total_value": 10000.0, "positions": [], "watchlist": []}
        )
        assert "$10,000.00" in text
        assert "100% cash" in text or "none" in text.lower()
        assert "empty" in text.lower()

    def test_with_positions_and_watchlist(self) -> None:
        ctx = {
            "cash_balance": 5000.0,
            "total_value": 6500.0,
            "positions": [
                {
                    "ticker": "AAPL",
                    "quantity": 10,
                    "avg_cost": 150.0,
                    "current_price": 191.42,
                    "unrealized_pnl": 414.20,
                    "unrealized_pnl_percent": 27.61,
                }
            ],
            "watchlist": [
                {"ticker": "MSFT", "price": 420.0, "change_percent": 1.23},
            ],
        }
        text = format_portfolio_context(ctx)
        assert "AAPL" in text
        assert "$150.00" in text
        assert "$191.42" in text
        assert "MSFT" in text
        assert "+1.23%" in text or "1.23%" in text

    def test_handles_missing_optional_fields(self) -> None:
        # Defensive: a partially populated context shouldn't crash
        text = format_portfolio_context({})
        assert text  # non-empty


class TestBuildMessages:
    def test_system_message_first_and_includes_persona(self) -> None:
        msgs = build_messages(
            {"cash_balance": 10000.0, "total_value": 10000.0, "positions": [], "watchlist": []},
            history=[],
            user_message="hello",
        )
        assert msgs[0]["role"] == "system"
        assert "FinAlly" in msgs[0]["content"]
        # The system prompt's full text should be present (anchor: persona line)
        assert SYSTEM_PROMPT.split("\n")[0] in msgs[0]["content"]

    def test_user_message_is_last(self) -> None:
        msgs = build_messages(
            {"cash_balance": 100.0, "total_value": 100.0, "positions": [], "watchlist": []},
            history=[
                {"role": "user", "content": "earlier"},
                {"role": "assistant", "content": "earlier reply"},
            ],
            user_message="now",
        )
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "now"

    def test_history_filters_invalid_roles(self) -> None:
        msgs = build_messages(
            {},
            history=[
                {"role": "user", "content": "ok"},
                {"role": "system", "content": "not allowed in history"},
                {"role": "assistant", "content": "ok2"},
                {"role": "user", "content": ""},  # empty content filtered
            ],
            user_message="x",
        )
        # 1 system + 2 valid history + 1 user = 4
        assert len(msgs) == 4
        assert msgs[0]["role"] == "system"
        assert msgs[1]["content"] == "ok"
        assert msgs[2]["content"] == "ok2"
