"""Snapshot-heartbeat policy tests."""

from __future__ import annotations

from app.services.heartbeat import heartbeat_once
from app.services.portfolio import execute_trade_full
from db import get_snapshots


async def test_heartbeat_no_change_skips(app_state):
    """No price change between trades → heartbeat should not write."""
    before = get_snapshots(app_state.db)
    wrote = await heartbeat_once(app_state.db, app_state.price_cache, app_state.db_lock)
    assert wrote is False
    after = get_snapshots(app_state.db)
    assert len(after) == len(before)


async def test_heartbeat_writes_when_value_moves(app_state):
    app_state.price_cache.update("AAPL", 100.0)
    await execute_trade_full(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        cache=app_state.price_cache,
        ticker="AAPL",
        side="buy",
        quantity=5,
    )
    # Position bought; a forced post-trade snapshot already exists.
    # Move the price by more than $0.01 worth at the position level.
    app_state.price_cache.update("AAPL", 110.0)  # +$50 portfolio value
    wrote = await heartbeat_once(app_state.db, app_state.price_cache, app_state.db_lock)
    assert wrote is True


async def test_heartbeat_threshold_under_one_cent_skips(app_state):
    """A delta strictly <= $0.01 should not write."""
    app_state.price_cache.update("AAPL", 100.0)
    await execute_trade_full(
        conn=app_state.db,
        db_lock=app_state.db_lock,
        cache=app_state.price_cache,
        ticker="AAPL",
        side="buy",
        quantity=1,
    )
    # 1 share: $0.005 price wiggle == $0.005 portfolio delta -> below 0.01.
    app_state.price_cache.update("AAPL", 100.005)
    wrote = await heartbeat_once(app_state.db, app_state.price_cache, app_state.db_lock)
    assert wrote is False
