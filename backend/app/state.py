"""Application state container.

Holds the long-lived singletons that route handlers and background tasks
need: the SQLite connection, the price cache, the data source, the
session-open tracker, and the snapshot policy. Stored on
``app.state.appstate`` and reachable via ``request.app.state.appstate``.
"""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

from app.market import MarketDataSource, PriceCache
from app.services.session_prices import SessionOpenTracker


@dataclass
class AppState:
    """Long-lived dependencies wired up by the FastAPI lifespan."""

    db: sqlite3.Connection
    price_cache: PriceCache
    data_source: MarketDataSource
    session_open: SessionOpenTracker
    db_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    heartbeat_task: Optional[asyncio.Task] = None
