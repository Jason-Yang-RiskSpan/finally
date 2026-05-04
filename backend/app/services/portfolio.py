"""Portfolio valuation and trade orchestration.

Thin wrapper that sits between the route handlers and the db-engineer's
atomic helpers. Two responsibilities:

* :func:`valuate_portfolio` reads positions + cash, marks-to-market with
  the live :class:`PriceCache`, and produces the response shape served at
  ``GET /api/portfolio``.
* :func:`execute_trade_full` calls into ``db.execute_trade`` and writes a
  forced post-trade snapshot via ``db.record_snapshot``. This is the
  single entry point for both manual UI trades and LLM-issued trades.

The same functions are imported by the LLM engineer's chat handler.
"""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass

from app.market import PriceCache
from db import (
    execute_trade as db_execute_trade,
)
from db import (
    get_cash_balance,
    get_positions,
    get_user,
    record_snapshot,
)
from db.errors import DatabaseError, InsufficientFunds, InsufficientShares
from db.repository import TradeResult


@dataclass(frozen=True)
class PortfolioPosition:
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float | None
    market_value: float
    unrealized_pl: float
    unrealized_pl_percent: float


@dataclass(frozen=True)
class PortfolioSnapshot:
    cash_balance: float
    positions: list[PortfolioPosition]
    market_value: float  # market value of positions (excludes cash)
    total_value: float  # cash + market_value
    total_cost_basis: float
    total_unrealized_pl: float
    total_unrealized_pl_percent: float


def _position_value(
    qty: float, avg_cost: float, price: float | None
) -> tuple[float, float, float]:
    """Compute (market_value, unrealized_pl, unrealized_pl_percent)."""
    if price is None:
        return 0.0, 0.0, 0.0
    market_value = qty * price
    cost_basis = qty * avg_cost
    pl = market_value - cost_basis
    pct = (pl / cost_basis * 100.0) if cost_basis > 0 else 0.0
    return round(market_value, 4), round(pl, 4), round(pct, 4)


def valuate_portfolio(
    conn: sqlite3.Connection,
    cache: PriceCache,
    *,
    user_id: str = "default",
) -> PortfolioSnapshot:
    """Build a marked-to-market snapshot of the user's portfolio."""
    if get_user(conn, user_id) is None:
        # Ensures consistent error semantics — shouldn't happen given init_db
        # seeds the default user.
        return PortfolioSnapshot(
            cash_balance=0.0,
            positions=[],
            market_value=0.0,
            total_value=0.0,
            total_cost_basis=0.0,
            total_unrealized_pl=0.0,
            total_unrealized_pl_percent=0.0,
        )

    cash = get_cash_balance(conn, user_id)
    raw_positions = get_positions(conn, user_id)
    out: list[PortfolioPosition] = []
    market_value_total = 0.0
    cost_basis_total = 0.0

    for pos in raw_positions:
        price = cache.get_price(pos.ticker)
        market_value, pl, pct = _position_value(pos.quantity, pos.avg_cost, price)
        market_value_total += market_value
        cost_basis_total += pos.quantity * pos.avg_cost
        out.append(
            PortfolioPosition(
                ticker=pos.ticker,
                quantity=pos.quantity,
                avg_cost=pos.avg_cost,
                current_price=price,
                market_value=market_value,
                unrealized_pl=pl,
                unrealized_pl_percent=pct,
            )
        )

    total_value = cash + market_value_total
    total_pl = market_value_total - cost_basis_total
    total_pct = (total_pl / cost_basis_total * 100.0) if cost_basis_total > 0 else 0.0
    return PortfolioSnapshot(
        cash_balance=round(cash, 4),
        positions=out,
        market_value=round(market_value_total, 4),
        total_value=round(total_value, 4),
        total_cost_basis=round(cost_basis_total, 4),
        total_unrealized_pl=round(total_pl, 4),
        total_unrealized_pl_percent=round(total_pct, 4),
    )


@dataclass(frozen=True)
class ExecutedTrade:
    trade: TradeResult
    total_value: float


async def execute_trade_full(
    *,
    conn: sqlite3.Connection,
    db_lock: asyncio.Lock,
    cache: PriceCache,
    ticker: str,
    side: str,
    quantity: float,
    user_id: str = "default",
) -> ExecutedTrade:
    """Execute a market order at the live cache price.

    Wraps the db-engineer's atomic ``execute_trade`` helper, then writes
    a forced portfolio snapshot. ``db_lock`` serializes mutations on the
    shared sqlite connection so the BEGIN IMMEDIATE inside the helper
    cannot race with another coroutine on the same connection object.

    Raises:
        ValueError: missing live price (ticker isn't tracked) or invalid
            side / quantity (validated by db helper).
        InsufficientFunds / InsufficientShares: bubbled up from the db
            helper for caller-friendly translation.
    """
    side = side.lower()
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
    if quantity <= 0:
        raise ValueError("quantity must be > 0")

    price = cache.get_price(ticker)
    if price is None:
        raise ValueError(f"no live price available for {ticker!r}")

    async with db_lock:
        result = await asyncio.to_thread(
            db_execute_trade,
            conn,
            ticker=ticker,
            side=side,  # type: ignore[arg-type]
            quantity=quantity,
            price=price,
            user_id=user_id,
        )
        # Force a snapshot at the post-trade total value.
        snapshot = valuate_portfolio(conn, cache, user_id=user_id)
        await asyncio.to_thread(
            record_snapshot,
            conn,
            snapshot.total_value,
            user_id=user_id,
            force=True,
        )

    return ExecutedTrade(trade=result, total_value=snapshot.total_value)


__all__ = [
    "PortfolioPosition",
    "PortfolioSnapshot",
    "ExecutedTrade",
    "valuate_portfolio",
    "execute_trade_full",
    "DatabaseError",
    "InsufficientFunds",
    "InsufficientShares",
]
