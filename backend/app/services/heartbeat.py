"""Background snapshot heartbeat.

PLAN.md §7 portfolio_snapshots: in addition to per-trade snapshots, the
backend writes a snapshot every 30 seconds *only if* the user's total
portfolio value has changed by strictly more than ``$0.01`` since the
last recorded snapshot. This keeps the time-series compact when the tab
is idle but still produces points whenever prices actually move.

The heartbeat is a single asyncio task driven by the lifespan in
``app/main.py``.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3

from app.market import PriceCache
from app.services.portfolio import valuate_portfolio
from db import record_snapshot

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 30.0


async def heartbeat_once(
    conn: sqlite3.Connection,
    cache: PriceCache,
    db_lock: asyncio.Lock,
    *,
    user_id: str = "default",
) -> bool:
    """Run a single heartbeat tick. Returns True if a snapshot was written."""
    async with db_lock:
        snapshot = await asyncio.to_thread(
            valuate_portfolio, conn, cache, user_id=user_id
        )
        wrote = await asyncio.to_thread(
            record_snapshot,
            conn,
            snapshot.total_value,
            user_id=user_id,
            force=False,
        )
    return wrote


async def run_heartbeat_loop(
    conn: sqlite3.Connection,
    cache: PriceCache,
    db_lock: asyncio.Lock,
    *,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    user_id: str = "default",
) -> None:
    """Loop forever, sleeping ``interval_seconds`` between ticks.

    Cancellation is the normal stop signal (lifespan shutdown).
    """
    logger.info("Snapshot heartbeat starting (interval=%.1fs)", interval_seconds)
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                wrote = await heartbeat_once(conn, cache, db_lock, user_id=user_id)
                if wrote:
                    logger.debug("Heartbeat snapshot recorded")
            except Exception:
                logger.exception("Heartbeat tick failed (continuing)")
    except asyncio.CancelledError:
        logger.info("Snapshot heartbeat cancelled")
        raise
