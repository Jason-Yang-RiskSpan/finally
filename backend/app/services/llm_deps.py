"""Adapter wiring ``app.llm.handler.ChatDependencies`` to backend services.

The LLM module declares a synchronous Protocol (``ChatDependencies``) but
the backend's portfolio/watchlist primitives are async (they take
``db_lock`` and call into the async data source). This adapter bridges
the two by scheduling async work back onto the main event loop via
``asyncio.run_coroutine_threadsafe`` — the LLM handler runs inside
``asyncio.to_thread``, so blocking on the future is safe and preserves
the db_lock serialization guarantees that manual UI trades depend on.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.portfolio import (
    InsufficientFunds,
    InsufficientShares,
    execute_trade_full,
    valuate_portfolio,
)
from app.services.validation import InvalidTickerSyntax, UnknownTicker
from app.services.watchlist import (
    add_to_watchlist as add_to_watchlist_async,
)
from app.services.watchlist import (
    list_watchlist_with_prices,
    remove_from_watchlist,
)
from app.state import AppState
from db import add_chat_message, get_recent_chat_messages

logger = logging.getLogger(__name__)


class AppStateChatDeps:
    """Implements ``ChatDependencies`` against a live ``AppState``."""

    def __init__(self, state: AppState, loop: asyncio.AbstractEventLoop) -> None:
        self._state = state
        self._loop = loop

    def _run(self, coro: Any) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def get_portfolio_context(self, user_id: str) -> dict[str, Any]:
        snapshot = valuate_portfolio(
            self._state.db, self._state.price_cache, user_id=user_id
        )
        watchlist = list_watchlist_with_prices(
            self._state.db,
            self._state.price_cache,
            self._state.session_open,
            user_id=user_id,
        )
        positions_out = []
        for p in snapshot.positions:
            positions_out.append(
                {
                    "ticker": p.ticker,
                    "quantity": p.quantity,
                    "avg_cost": p.avg_cost,
                    "current_price": p.current_price,
                    "market_value": p.market_value,
                    "unrealized_pnl": p.unrealized_pl,
                    "unrealized_pnl_percent": p.unrealized_pl_percent,
                }
            )
        watchlist_out = []
        for w in watchlist:
            change_pct = None
            if w.price is not None and w.session_open:
                change_pct = (w.price - w.session_open) / w.session_open * 100.0
            watchlist_out.append(
                {
                    "ticker": w.ticker,
                    "price": w.price,
                    "session_open": w.session_open,
                    "change_percent": change_pct,
                }
            )
        return {
            "cash_balance": snapshot.cash_balance,
            "total_value": snapshot.total_value,
            "unrealized_pnl": snapshot.total_unrealized_pl,
            "unrealized_pnl_percent": snapshot.total_unrealized_pl_percent,
            "positions": positions_out,
            "watchlist": watchlist_out,
        }

    def execute_trade(
        self, user_id: str, ticker: str, side: str, quantity: float
    ) -> dict[str, Any]:
        try:
            result = self._run(
                execute_trade_full(
                    conn=self._state.db,
                    db_lock=self._state.db_lock,
                    cache=self._state.price_cache,
                    ticker=ticker,
                    side=side,
                    quantity=quantity,
                    user_id=user_id,
                )
            )
            return {"status": "executed", "price": result.trade.price}
        except InsufficientFunds:
            return {"status": "rejected", "reason": "insufficient_cash"}
        except InsufficientShares:
            return {"status": "rejected", "reason": "insufficient_shares"}
        except ValueError as exc:
            return {"status": "rejected", "reason": str(exc)}

    def add_to_watchlist(self, user_id: str, ticker: str) -> dict[str, Any]:
        try:
            self._run(
                add_to_watchlist_async(
                    conn=self._state.db,
                    db_lock=self._state.db_lock,
                    data_source=self._state.data_source,
                    cache=self._state.price_cache,
                    session_open=self._state.session_open,
                    ticker=ticker,
                    user_id=user_id,
                )
            )
            return {"status": "executed"}
        except InvalidTickerSyntax:
            return {"status": "rejected", "reason": "invalid_syntax"}
        except UnknownTicker:
            return {"status": "rejected", "reason": "unknown_ticker"}

    def remove_from_watchlist(self, user_id: str, ticker: str) -> dict[str, Any]:
        try:
            removed = self._run(
                remove_from_watchlist(
                    conn=self._state.db,
                    db_lock=self._state.db_lock,
                    data_source=self._state.data_source,
                    cache=self._state.price_cache,
                    ticker=ticker,
                    user_id=user_id,
                )
            )
            if removed:
                return {"status": "executed"}
            return {"status": "rejected", "reason": "not_on_watchlist"}
        except InvalidTickerSyntax:
            return {"status": "rejected", "reason": "invalid_syntax"}

    def get_recent_messages(self, user_id: str, limit: int) -> list[dict[str, Any]]:
        rows = get_recent_chat_messages(self._state.db, limit=limit, user_id=user_id)
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def append_message(
        self,
        user_id: str,
        role: str,
        content: str,
        actions: dict[str, Any] | None = None,
    ) -> None:
        add_chat_message(
            self._state.db,
            role=role,
            content=content,
            actions=actions,
            user_id=user_id,
        )


__all__ = ["AppStateChatDeps"]
