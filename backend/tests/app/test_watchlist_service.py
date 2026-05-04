"""Tests for watchlist add/remove and the tracked-tickers reconcile helper."""

from __future__ import annotations

import pytest

from app.services.validation import InvalidTickerSyntax, UnknownTicker
from app.services.watchlist import (
    add_to_watchlist,
    list_watchlist_with_prices,
    reconcile_tracked_tickers,
    remove_from_watchlist,
)
from db import get_watchlist


async def test_add_to_watchlist_persists_and_registers(app_state):
    validated = await add_to_watchlist(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        data_source=app_state.data_source,
        cache=app_state.price_cache,
        session_open=app_state.session_open,
        ticker="pypl",
    )
    assert validated.ticker == "PYPL"
    assert "PYPL" in get_watchlist(app_state.db)
    assert "PYPL" in app_state.data_source.get_tickers()


async def test_add_to_watchlist_invalid_syntax(app_state):
    with pytest.raises(InvalidTickerSyntax):
        await add_to_watchlist(
            conn=app_state.db,
            db_lock=app_state.db_lock,
            data_source=app_state.data_source,
            cache=app_state.price_cache,
            session_open=app_state.session_open,
            ticker="bad ticker!",
        )


async def test_add_to_watchlist_unknown(app_state):
    app_state.data_source.default_price = None
    with pytest.raises(UnknownTicker):
        await add_to_watchlist(
            conn=app_state.db,
            db_lock=app_state.db_lock,
            data_source=app_state.data_source,
            cache=app_state.price_cache,
            session_open=app_state.session_open,
            ticker="ZZZZZ",
        )
    assert "ZZZZZ" not in get_watchlist(app_state.db)


async def test_remove_from_watchlist_drops_data_source_when_no_position(app_state):
    await add_to_watchlist(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        data_source=app_state.data_source,
        cache=app_state.price_cache,
        session_open=app_state.session_open,
        ticker="PYPL",
    )
    assert await remove_from_watchlist(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        data_source=app_state.data_source,
        cache=app_state.price_cache,
        ticker="PYPL",
    )
    assert "PYPL" not in app_state.data_source.get_tickers()


async def test_remove_from_watchlist_keeps_tracked_ticker_with_position(app_state):
    """If a position exists, the ticker stays tracked even after removal."""
    from app.services.portfolio import execute_trade_full

    await add_to_watchlist(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        data_source=app_state.data_source,
        cache=app_state.price_cache,
        session_open=app_state.session_open,
        ticker="PYPL",
    )
    # Buy a share.
    await execute_trade_full(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        cache=app_state.price_cache,
        ticker="PYPL",
        side="buy",
        quantity=1,
    )
    deleted = await remove_from_watchlist(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        data_source=app_state.data_source,
        cache=app_state.price_cache,
        ticker="PYPL",
    )
    assert deleted
    # Watchlist row gone, but the data source still tracks the ticker
    # because a position references it.
    assert "PYPL" not in get_watchlist(app_state.db)
    assert "PYPL" in app_state.data_source.get_tickers()


async def test_reconcile_tracked_tickers_picks_up_db_state(app_state):
    """Watchlist entries already in the DB get registered with the source."""
    # Seed data already populates watchlist; reconcile should add them.
    desired = await reconcile_tracked_tickers(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        data_source=app_state.data_source,
        cache=app_state.price_cache,
        session_open=app_state.session_open,
    )
    assert "AAPL" in desired
    assert "AAPL" in app_state.data_source.get_tickers()


async def test_list_watchlist_with_prices_folds_in_session_open(app_state):
    app_state.price_cache.update("AAPL", 200.0)
    app_state.session_open.observe("AAPL", 200.0)
    entries = list_watchlist_with_prices(
        app_state.db, app_state.price_cache, app_state.session_open
    )
    aapl = next(e for e in entries if e.ticker == "AAPL")
    assert aapl.price == 200.0
    assert aapl.session_open == 200.0
