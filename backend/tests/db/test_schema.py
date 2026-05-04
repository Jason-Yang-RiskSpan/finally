"""Tests for schema initialization and seeding."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from db import (
    DEFAULT_CASH_BALANCE,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST_TICKERS,
    get_cash_balance,
    get_user,
    get_watchlist,
    init_db,
)


class TestSchemaInit:
    """Schema creation + idempotency."""

    def test_creates_all_tables(self, conn: sqlite3.Connection):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = {row["name"] for row in cur.fetchall()}
        # Ignore SQLite-internal tables (e.g., sqlite_sequence created by AUTOINCREMENT).
        names = {n for n in names if not n.startswith("sqlite_")}
        assert names == {
            "users_profile",
            "watchlist",
            "positions",
            "trades",
            "portfolio_snapshots",
            "chat_messages",
        }

    def test_seeds_default_user(self, conn: sqlite3.Connection):
        user = get_user(conn)
        assert user is not None
        assert user["user_id"] == DEFAULT_USER_ID
        assert float(user["cash_balance"]) == DEFAULT_CASH_BALANCE

    def test_seeds_default_watchlist(self, conn: sqlite3.Connection):
        tickers = get_watchlist(conn)
        assert set(tickers) == set(DEFAULT_WATCHLIST_TICKERS)
        assert len(tickers) == 10

    def test_seeds_initial_snapshot(self, conn: sqlite3.Connection):
        cur = conn.execute(
            "SELECT total_value FROM portfolio_snapshots WHERE user_id = ?",
            (DEFAULT_USER_ID,),
        )
        rows = cur.fetchall()
        assert len(rows) == 1
        assert float(rows[0]["total_value"]) == DEFAULT_CASH_BALANCE

    def test_idempotent_reinit(self, db_path: Path):
        # First init seeds.
        c1 = init_db(db_path)
        c1.close()
        # Second init must not duplicate seed data.
        c2 = init_db(db_path)
        try:
            (n_users,) = c2.execute("SELECT COUNT(*) FROM users_profile").fetchone()
            (n_watch,) = c2.execute("SELECT COUNT(*) FROM watchlist").fetchone()
            (n_snap,) = c2.execute(
                "SELECT COUNT(*) FROM portfolio_snapshots"
            ).fetchone()
            assert n_users == 1
            assert n_watch == len(DEFAULT_WATCHLIST_TICKERS)
            assert n_snap == 1
        finally:
            c2.close()

    def test_users_profile_unique_user_id(self, conn: sqlite3.Connection):
        # Inserting a second row with the same user_id must fail.
        try:
            conn.execute(
                "INSERT INTO users_profile (user_id, cash_balance, created_at) "
                "VALUES (?, ?, ?)",
                (DEFAULT_USER_ID, 0.0, "2026-01-01T00:00:00+00:00"),
            )
            raised = False
        except sqlite3.IntegrityError:
            raised = True
        assert raised

    def test_watchlist_unique_user_ticker(self, conn: sqlite3.Connection):
        try:
            conn.execute(
                "INSERT INTO watchlist (user_id, ticker, added_at) VALUES (?, ?, ?)",
                (DEFAULT_USER_ID, "AAPL", "2026-01-01T00:00:00+00:00"),
            )
            raised = False
        except sqlite3.IntegrityError:
            raised = True
        assert raised

    def test_trades_side_check_constraint(self, conn: sqlite3.Connection):
        try:
            conn.execute(
                "INSERT INTO trades "
                " (user_id, ticker, side, quantity, price, executed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (DEFAULT_USER_ID, "AAPL", "hold", 1.0, 100.0, "2026-01-01T00:00:00+00:00"),
            )
            raised = False
        except sqlite3.IntegrityError:
            raised = True
        assert raised

    def test_get_cash_balance_unknown_user(self, conn: sqlite3.Connection):
        import pytest as _pytest

        with _pytest.raises(KeyError):
            get_cash_balance(conn, user_id="nope")
