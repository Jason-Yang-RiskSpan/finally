"""Trade execution + valuation tests at the service layer."""

from __future__ import annotations

import pytest

from app.services.portfolio import (
    InsufficientFunds,
    InsufficientShares,
    execute_trade_full,
    valuate_portfolio,
)
from db import get_position, get_snapshots


async def test_buy_decreases_cash_and_creates_position(app_state):
    app_state.price_cache.update("AAPL", 100.0)
    executed = await execute_trade_full(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        cache=app_state.price_cache,
        ticker="AAPL",
        side="buy",
        quantity=5,
    )
    assert executed.trade.side == "buy"
    assert executed.trade.new_cash_balance == pytest.approx(10000 - 500)
    pos = get_position(app_state.db, "AAPL")
    assert pos is not None
    assert pos.quantity == 5
    assert pos.avg_cost == pytest.approx(100.0)


async def test_buy_records_post_trade_snapshot(app_state):
    app_state.price_cache.update("AAPL", 100.0)
    snapshots_before = get_snapshots(app_state.db)
    await execute_trade_full(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        cache=app_state.price_cache,
        ticker="AAPL",
        side="buy",
        quantity=5,
    )
    snapshots_after = get_snapshots(app_state.db)
    assert len(snapshots_after) == len(snapshots_before) + 1


async def test_buy_insufficient_cash_rejected(app_state):
    app_state.price_cache.update("AAPL", 100.0)
    with pytest.raises(InsufficientFunds):
        await execute_trade_full(
            conn=app_state.db,
            db_lock=app_state.db_lock,
            cache=app_state.price_cache,
            ticker="AAPL",
            side="buy",
            quantity=200,  # 200 * 100 = $20k > $10k
        )


async def test_sell_more_than_held_rejected(app_state):
    app_state.price_cache.update("AAPL", 100.0)
    with pytest.raises(InsufficientShares):
        await execute_trade_full(
            conn=app_state.db,
            db_lock=app_state.db_lock,
            cache=app_state.price_cache,
            ticker="AAPL",
            side="sell",
            quantity=1,
        )


async def test_sell_to_zero_deletes_position(app_state):
    app_state.price_cache.update("AAPL", 100.0)
    await execute_trade_full(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        cache=app_state.price_cache,
        ticker="AAPL",
        side="buy",
        quantity=3,
    )
    await execute_trade_full(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        cache=app_state.price_cache,
        ticker="AAPL",
        side="sell",
        quantity=3,
    )
    assert get_position(app_state.db, "AAPL") is None


async def test_partial_sell_keeps_avg_cost(app_state):
    app_state.price_cache.update("AAPL", 100.0)
    await execute_trade_full(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        cache=app_state.price_cache,
        ticker="AAPL",
        side="buy",
        quantity=10,
    )
    # Move the price; partial sell shouldn't alter avg_cost.
    app_state.price_cache.update("AAPL", 150.0)
    await execute_trade_full(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        cache=app_state.price_cache,
        ticker="AAPL",
        side="sell",
        quantity=4,
    )
    pos = get_position(app_state.db, "AAPL")
    assert pos is not None
    assert pos.quantity == pytest.approx(6)
    assert pos.avg_cost == pytest.approx(100.0)


async def test_buy_without_live_price_raises(app_state):
    with pytest.raises(ValueError):
        await execute_trade_full(
            conn=app_state.db,
            db_lock=app_state.db_lock,
            cache=app_state.price_cache,
            ticker="AAPL",
            side="buy",
            quantity=1,
        )


async def test_valuate_marks_to_market(app_state):
    app_state.price_cache.update("AAPL", 100.0)
    await execute_trade_full(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        cache=app_state.price_cache,
        ticker="AAPL",
        side="buy",
        quantity=5,
    )
    app_state.price_cache.update("AAPL", 120.0)
    snapshot = valuate_portfolio(app_state.db, app_state.price_cache)
    assert snapshot.cash_balance == pytest.approx(9500.0)
    assert snapshot.market_value == pytest.approx(600.0)
    assert snapshot.total_value == pytest.approx(10100.0)
    assert snapshot.total_unrealized_pl == pytest.approx(100.0)
