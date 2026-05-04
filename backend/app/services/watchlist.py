"""Watchlist mutations + tracked-ticker reconciliation.

The set of tickers the data source must keep live = watchlist tickers ∪
tickers held as positions (PLAN.md §6 Tracked Tickers). These helpers are
the single path for both manual and (future) LLM-issued mutations:

* :func:`add_to_watchlist` validates + registers + persists.
* :func:`remove_from_watchlist` removes from DB and from the data source
  *only if* no position is still held in the ticker.

The LLM engineer imports the same functions for ``watchlist_changes``.
"""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass

from app.market import MarketDataSource, PriceCache
from app.services.session_prices import SessionOpenTracker
from app.services.validation import (
    UnknownTicker,
    ValidatedTicker,
    check_syntax,
    register_ticker,
)
from db import (
    add_watchlist_ticker,
    get_position,
    get_watchlist,
    remove_watchlist_ticker,
)


@dataclass(frozen=True)
class WatchlistEntry:
    """A watchlist row enriched with the latest price snapshot."""

    ticker: str
    price: float | None
    previous_price: float | None
    session_open: float | None
    timestamp: float | None


def list_watchlist_with_prices(
    conn: sqlite3.Connection,
    cache: PriceCache,
    session_open: SessionOpenTracker,
    *,
    user_id: str = "default",
) -> list[WatchlistEntry]:
    """Return the persisted watchlist with live price data folded in."""
    out: list[WatchlistEntry] = []
    for ticker in get_watchlist(conn, user_id):
        update = cache.get(ticker)
        out.append(
            WatchlistEntry(
                ticker=ticker,
                price=update.price if update else None,
                previous_price=update.previous_price if update else None,
                session_open=session_open.get(ticker),
                timestamp=update.timestamp if update else None,
            )
        )
    return out


async def add_to_watchlist(
    *,
    conn: sqlite3.Connection,
    db_lock: asyncio.Lock,
    data_source: MarketDataSource,
    cache: PriceCache,
    session_open: SessionOpenTracker,
    ticker: str,
    user_id: str = "default",
) -> ValidatedTicker:
    """Validate + register + persist a watchlist add.

    Same path used by manual UI adds and LLM-issued ``watchlist_changes``.
    Raises validation errors (:class:`InvalidTickerSyntax`,
    :class:`UnknownTicker`) without writing to the DB.
    """
    validated = await register_ticker(
        ticker,
        data_source=data_source,
        cache=cache,
        session_open=session_open,
    )
    async with db_lock:
        await asyncio.to_thread(
            add_watchlist_ticker, conn, validated.ticker, user_id
        )
    return validated


async def remove_from_watchlist(
    *,
    conn: sqlite3.Connection,
    db_lock: asyncio.Lock,
    data_source: MarketDataSource,
    cache: PriceCache,
    ticker: str,
    user_id: str = "default",
) -> bool:
    """Remove a ticker from the watchlist.

    Tracked-ticker rule: the data source keeps producing prices for any
    ticker the user still has a position in, so we only ``remove_ticker``
    from the data source if no position references it.

    Returns True if a row was deleted from the watchlist table.
    """
    normalized = check_syntax(ticker)

    async with db_lock:
        deleted = await asyncio.to_thread(
            remove_watchlist_ticker, conn, normalized, user_id
        )
        held = await asyncio.to_thread(get_position, conn, normalized, user_id)

    if deleted and held is None:
        # No position depends on this ticker — drop it from the data source.
        try:
            await data_source.remove_ticker(normalized)
        except Exception:
            # Don't bubble — the watchlist was successfully updated.
            pass
    return deleted


async def reconcile_tracked_tickers(
    *,
    conn: sqlite3.Connection,
    db_lock: asyncio.Lock,
    data_source: MarketDataSource,
    cache: PriceCache,
    session_open: SessionOpenTracker,
    user_id: str = "default",
) -> set[str]:
    """Ensure the data source tracks watchlist ∪ held-position tickers.

    Called once at startup after the data source has been started. Adds
    any DB-known ticker the source doesn't already have, capturing
    session-open as soon as a price appears. Returns the final set of
    tracked tickers.
    """
    async with db_lock:
        watchlist = await asyncio.to_thread(get_watchlist, conn, user_id)
        from db import get_positions

        positions = await asyncio.to_thread(get_positions, conn, user_id)
    desired = {check_syntax(t) for t in watchlist}
    desired.update({check_syntax(p.ticker) for p in positions})

    current = set(data_source.get_tickers())
    for ticker in desired - current:
        try:
            await register_ticker(
                ticker,
                data_source=data_source,
                cache=cache,
                session_open=session_open,
            )
        except UnknownTicker:
            # A previously-valid ticker now rejected by the live data
            # source — log and drop. We don't delete the DB row because
            # holdings audit history matters.
            continue

    # Capture session-open for any ticker already in the cache (fast path
    # for the simulator which seeds prices synchronously).
    for ticker in cache.get_all():
        session_open.observe(ticker, cache.get_price(ticker) or 0.0)
    return desired


__all__ = [
    "WatchlistEntry",
    "list_watchlist_with_prices",
    "add_to_watchlist",
    "remove_from_watchlist",
    "reconcile_tracked_tickers",
]
