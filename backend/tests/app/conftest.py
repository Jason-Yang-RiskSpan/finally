"""Shared fixtures for backend app tests.

Built around a hand-assembled :class:`AppState` so each test owns a
fresh SQLite file, an empty :class:`PriceCache`, and a stub data source
that doesn't spawn background tasks. This keeps the unit tests fast and
hermetic. The end-to-end ``TestClient`` fixture exercises the real
lifespan with the simulator.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.market import MarketDataSource, PriceCache
from app.services.session_prices import SessionOpenTracker
from app.state import AppState
from db import init_db


class StubDataSource(MarketDataSource):
    """Minimal MarketDataSource for tests.

    Tracks ticker membership and lets tests push prices into the cache
    directly. ``probe_price`` is the price returned for new tickers
    when they are added (None means ticker is rejected).
    """

    def __init__(self, cache: PriceCache, default_price: float | None = 100.0) -> None:
        self._cache = cache
        self._tickers: list[str] = []
        self.default_price = default_price
        self.rejected: set[str] = set()

    async def start(self, tickers: list[str]) -> None:
        self._tickers = list(tickers)
        for t in tickers:
            if self.default_price is not None:
                self._cache.update(t, self.default_price)

    async def stop(self) -> None:
        pass

    async def add_ticker(self, ticker: str) -> None:
        if ticker in self.rejected:
            return
        if ticker not in self._tickers:
            self._tickers.append(ticker)
        if self.default_price is not None:
            self._cache.update(ticker, self.default_price)

    async def remove_ticker(self, ticker: str) -> None:
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "finally.db"


@pytest.fixture
def db_conn(db_path: Path):
    conn = init_db(db_path)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def cache() -> PriceCache:
    return PriceCache()


@pytest.fixture
def session_open() -> SessionOpenTracker:
    return SessionOpenTracker()


@pytest.fixture
def stub_source(cache: PriceCache) -> StubDataSource:
    return StubDataSource(cache)


@pytest.fixture
def app_state(db_conn, cache, stub_source, session_open) -> AppState:
    state = AppState(
        db=db_conn,
        price_cache=cache,
        data_source=stub_source,
        session_open=session_open,
        db_lock=asyncio.Lock(),
    )
    return state
