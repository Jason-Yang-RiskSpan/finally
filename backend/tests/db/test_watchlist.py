"""Tests for watchlist helpers."""

from __future__ import annotations

import sqlite3

from db import (
    DEFAULT_WATCHLIST_TICKERS,
    add_watchlist_ticker,
    get_watchlist,
    remove_watchlist_ticker,
)


class TestWatchlist:
    def test_add_returns_true_on_new(self, conn: sqlite3.Connection):
        assert add_watchlist_ticker(conn, "PYPL") is True
        assert "PYPL" in get_watchlist(conn)

    def test_add_returns_false_on_duplicate(self, conn: sqlite3.Connection):
        # AAPL is in the default seeded set.
        assert "AAPL" in DEFAULT_WATCHLIST_TICKERS
        assert add_watchlist_ticker(conn, "AAPL") is False
        # Watchlist length unchanged.
        assert len(get_watchlist(conn)) == len(DEFAULT_WATCHLIST_TICKERS)

    def test_remove_returns_true_when_present(self, conn: sqlite3.Connection):
        assert remove_watchlist_ticker(conn, "AAPL") is True
        assert "AAPL" not in get_watchlist(conn)

    def test_remove_returns_false_when_absent(self, conn: sqlite3.Connection):
        assert remove_watchlist_ticker(conn, "PYPL") is False
