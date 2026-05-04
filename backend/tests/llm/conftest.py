"""Shared fixtures for LLM handler tests.

The injected dependencies are a simple in-memory fake that records every call
and lets each test program the responses for trade/watchlist primitives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pytest

from app.llm import ChatDependencies


@dataclass
class FakeDeps:
    """In-memory test double for ChatDependencies."""

    portfolio: dict[str, Any] = field(
        default_factory=lambda: {
            "cash_balance": 10000.0,
            "total_value": 10000.0,
            "positions": [],
            "watchlist": [
                {"ticker": "AAPL", "price": 191.42, "change_percent": 0.5},
            ],
        }
    )
    history: list[dict[str, Any]] = field(default_factory=list)
    trade_response: Callable[[str, str, str, float], dict[str, Any]] | None = None
    watchlist_add_response: Callable[[str, str], dict[str, Any]] | None = None
    watchlist_remove_response: Callable[[str, str], dict[str, Any]] | None = None

    # Recorded calls
    trade_calls: list[tuple[str, str, str, float]] = field(default_factory=list)
    watchlist_add_calls: list[tuple[str, str]] = field(default_factory=list)
    watchlist_remove_calls: list[tuple[str, str]] = field(default_factory=list)
    appended: list[tuple[str, str, str, dict[str, Any] | None]] = field(default_factory=list)

    # ChatDependencies protocol implementation ------------------------------

    def get_portfolio_context(self, user_id: str) -> dict[str, Any]:
        return dict(self.portfolio)

    def execute_trade(
        self, user_id: str, ticker: str, side: str, quantity: float
    ) -> dict[str, Any]:
        self.trade_calls.append((user_id, ticker, side, quantity))
        if self.trade_response is None:
            return {"status": "executed", "price": 100.0}
        return self.trade_response(user_id, ticker, side, quantity)

    def add_to_watchlist(self, user_id: str, ticker: str) -> dict[str, Any]:
        self.watchlist_add_calls.append((user_id, ticker))
        if self.watchlist_add_response is None:
            return {"status": "executed"}
        return self.watchlist_add_response(user_id, ticker)

    def remove_from_watchlist(self, user_id: str, ticker: str) -> dict[str, Any]:
        self.watchlist_remove_calls.append((user_id, ticker))
        if self.watchlist_remove_response is None:
            return {"status": "executed"}
        return self.watchlist_remove_response(user_id, ticker)

    def get_recent_messages(self, user_id: str, limit: int) -> list[dict[str, Any]]:
        # Return the last ``limit`` messages, mirroring the db-engineer's helper.
        # We only consider messages for this user_id.
        msgs = [m for m in self.history if m.get("user_id", user_id) == user_id]
        return msgs[-limit:]

    def append_message(
        self,
        user_id: str,
        role: str,
        content: str,
        actions: dict[str, Any] | None = None,
    ) -> None:
        self.appended.append((user_id, role, content, actions))
        self.history.append(
            {"user_id": user_id, "role": role, "content": content, "actions": actions}
        )


@pytest.fixture
def deps() -> ChatDependencies:
    return FakeDeps()
