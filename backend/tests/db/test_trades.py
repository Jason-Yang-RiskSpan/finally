"""Tests for atomic trade execution."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from db import (
    DEFAULT_CASH_BALANCE,
    InsufficientFunds,
    InsufficientShares,
    connect,
    execute_trade,
    get_cash_balance,
    get_position,
    init_db,
)


class TestBuy:
    def test_buy_creates_position(self, conn: sqlite3.Connection):
        result = execute_trade(
            conn, ticker="AAPL", side="buy", quantity=10.0, price=190.0
        )
        assert result.new_quantity == 10.0
        assert result.new_avg_cost == pytest.approx(190.0)
        assert result.new_cash_balance == pytest.approx(DEFAULT_CASH_BALANCE - 1900.0)

        pos = get_position(conn, "AAPL")
        assert pos is not None
        assert pos.quantity == 10.0
        assert pos.avg_cost == pytest.approx(190.0)

    def test_buy_appends_trade_row(self, conn: sqlite3.Connection):
        result = execute_trade(
            conn, ticker="AAPL", side="buy", quantity=2.0, price=100.0
        )
        row = conn.execute(
            "SELECT * FROM trades WHERE id = ?", (result.trade_id,)
        ).fetchone()
        assert row["side"] == "buy"
        assert float(row["quantity"]) == 2.0
        assert float(row["price"]) == 100.0

    def test_buy_updates_avg_cost(self, conn: sqlite3.Connection):
        execute_trade(conn, ticker="AAPL", side="buy", quantity=10.0, price=100.0)
        execute_trade(conn, ticker="AAPL", side="buy", quantity=10.0, price=200.0)
        pos = get_position(conn, "AAPL")
        assert pos is not None
        assert pos.quantity == 20.0
        # weighted avg: (10*100 + 10*200) / 20 = 150
        assert pos.avg_cost == pytest.approx(150.0)

    def test_buy_insufficient_cash(self, conn: sqlite3.Connection):
        with pytest.raises(InsufficientFunds) as exc:
            execute_trade(
                conn, ticker="AAPL", side="buy", quantity=1000.0, price=100.0
            )
        # Balance unchanged; no position created; no trade row.
        assert get_cash_balance(conn) == pytest.approx(DEFAULT_CASH_BALANCE)
        assert get_position(conn, "AAPL") is None
        assert exc.value.cost == pytest.approx(100000.0)
        (n_trades,) = conn.execute("SELECT COUNT(*) FROM trades").fetchone()
        assert n_trades == 0

    def test_buy_rejects_non_positive(self, conn: sqlite3.Connection):
        with pytest.raises(ValueError):
            execute_trade(conn, ticker="AAPL", side="buy", quantity=0, price=100.0)
        with pytest.raises(ValueError):
            execute_trade(conn, ticker="AAPL", side="buy", quantity=1, price=0.0)


class TestSell:
    def test_sell_partial(self, conn: sqlite3.Connection):
        execute_trade(conn, ticker="AAPL", side="buy", quantity=10.0, price=100.0)
        result = execute_trade(
            conn, ticker="AAPL", side="sell", quantity=4.0, price=150.0
        )
        # Partial sell leaves avg_cost untouched (it's the basis).
        assert result.new_quantity == pytest.approx(6.0)
        assert result.new_avg_cost == pytest.approx(100.0)
        # Cash: 10000 - 1000 + 600 = 9600
        assert result.new_cash_balance == pytest.approx(9600.0)
        pos = get_position(conn, "AAPL")
        assert pos is not None
        assert pos.quantity == pytest.approx(6.0)
        assert pos.avg_cost == pytest.approx(100.0)

    def test_sell_to_zero_deletes_position(self, conn: sqlite3.Connection):
        execute_trade(conn, ticker="AAPL", side="buy", quantity=5.0, price=100.0)
        result = execute_trade(
            conn, ticker="AAPL", side="sell", quantity=5.0, price=120.0
        )
        assert result.new_quantity == 0.0
        assert result.new_avg_cost == 0.0
        # Position row deleted; trades preserve history.
        assert get_position(conn, "AAPL") is None
        (n_trades,) = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE ticker = 'AAPL'"
        ).fetchone()
        assert n_trades == 2

    def test_sell_no_position(self, conn: sqlite3.Connection):
        with pytest.raises(InsufficientShares) as exc:
            execute_trade(
                conn, ticker="AAPL", side="sell", quantity=1.0, price=100.0
            )
        assert exc.value.held == 0.0
        assert get_cash_balance(conn) == pytest.approx(DEFAULT_CASH_BALANCE)

    def test_sell_more_than_held(self, conn: sqlite3.Connection):
        execute_trade(conn, ticker="AAPL", side="buy", quantity=2.0, price=100.0)
        with pytest.raises(InsufficientShares):
            execute_trade(
                conn, ticker="AAPL", side="sell", quantity=3.0, price=110.0
            )
        # State unchanged.
        pos = get_position(conn, "AAPL")
        assert pos is not None
        assert pos.quantity == pytest.approx(2.0)
        assert get_cash_balance(conn) == pytest.approx(DEFAULT_CASH_BALANCE - 200.0)


class TestRace:
    """Concurrent buys must never overdraw cash."""

    def test_concurrent_buys_cannot_overdraw(self, db_path: Path):
        # Seed once, then have many threads attempt to buy more than the
        # remaining balance can cover. Exactly one should succeed.
        init_db(db_path).close()

        # Set the user up with $1,000 to make the math easy.
        c0 = connect(db_path)
        try:
            c0.execute(
                "UPDATE users_profile SET cash_balance = 1000.0 WHERE user_id = 'default'"
            )
        finally:
            c0.close()

        n_threads = 8
        successes: list[bool] = []
        failures: list[bool] = []
        lock = threading.Lock()

        def buy_once():
            conn = connect(db_path)
            try:
                # Each thread tries to buy $900 worth — at most one can succeed
                # given the $1,000 starting balance.
                execute_trade(
                    conn, ticker="AAPL", side="buy", quantity=9.0, price=100.0
                )
                with lock:
                    successes.append(True)
            except InsufficientFunds:
                with lock:
                    failures.append(True)
            finally:
                conn.close()

        threads = [threading.Thread(target=buy_once) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(successes) == 1
        assert len(failures) == n_threads - 1

        c1 = connect(db_path)
        try:
            bal = float(
                c1.execute(
                    "SELECT cash_balance FROM users_profile WHERE user_id = 'default'"
                ).fetchone()["cash_balance"]
            )
        finally:
            c1.close()

        assert bal == pytest.approx(100.0)  # 1000 - 900
