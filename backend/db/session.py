"""Connection helpers and one-shot startup initialization.

``init_db(path)`` is the entry point the FastAPI application calls during
startup. It is idempotent: if the SQLite file already exists with the schema
present, it leaves data untouched. If tables are missing it creates them, and
if the user/watchlist/snapshot tables are empty it seeds the defaults
described in PLAN.md §7.

``connect(path)`` returns a configured ``sqlite3.Connection`` with row
factory and pragmas the rest of the layer expects (foreign keys enabled,
WAL journal mode for concurrency, ISO 8601 string timestamps).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from db.schema import (
    DEFAULT_CASH_BALANCE,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST_TICKERS,
    SCHEMA_SQL,
)


def _utcnow_iso() -> str:
    """Timezone-aware ISO-8601 timestamp with microseconds."""
    return datetime.now(timezone.utc).isoformat()


def connect(path: str | os.PathLike[str]) -> sqlite3.Connection:
    """Open a connection with the pragmas / row factory we want everywhere.

    The caller is responsible for closing the connection (or using it as a
    context manager). ``check_same_thread=False`` is enabled so that an async
    web framework can hand the connection across the threadpool — locking is
    handled by SQLite itself.
    """
    conn = sqlite3.connect(
        str(path),
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
        isolation_level=None,  # we manage BEGIN/COMMIT explicitly when needed
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL is fine for our single-writer workload and keeps reads non-blocking.
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        # In-memory databases reject WAL; fall back to default journaling.
        pass
    conn.execute("PRAGMA synchronous = NORMAL")
    # Wait up to 5s for the write lock when contended; without this,
    # concurrent BEGIN IMMEDIATE calls raise "database is locked" instead
    # of serializing.
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(path: str | os.PathLike[str]) -> sqlite3.Connection:
    """Create the schema and seed defaults if the DB is fresh.

    Idempotent: re-running against a populated database is a no-op.

    Returns an open connection so the caller can hold onto it for the
    lifetime of the process if desired.
    """
    db_path = Path(path)
    if db_path.parent and str(db_path.parent) not in ("", "."):
        db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect(db_path)
    conn.executescript(SCHEMA_SQL)
    _seed_if_empty(conn)
    return conn


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    """Insert default seed data if the database has not yet been seeded.

    This is split into independent checks per table so a partial seed
    (e.g., user inserted but watchlist failed) self-heals on next startup.
    """
    now = _utcnow_iso()

    # users_profile: ensure the default user exists.
    cur = conn.execute(
        "SELECT 1 FROM users_profile WHERE user_id = ?", (DEFAULT_USER_ID,)
    )
    if cur.fetchone() is None:
        conn.execute(
            "INSERT INTO users_profile (user_id, cash_balance, created_at) "
            "VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now),
        )

    # watchlist: only seed if the table is empty for this user.
    cur = conn.execute(
        "SELECT COUNT(*) FROM watchlist WHERE user_id = ?", (DEFAULT_USER_ID,)
    )
    (watchlist_count,) = cur.fetchone()
    if watchlist_count == 0:
        _seed_watchlist(conn, DEFAULT_WATCHLIST_TICKERS, now)

    # portfolio_snapshots: only seed t=0 if there are no snapshots yet.
    cur = conn.execute(
        "SELECT COUNT(*) FROM portfolio_snapshots WHERE user_id = ?",
        (DEFAULT_USER_ID,),
    )
    (snap_count,) = cur.fetchone()
    if snap_count == 0:
        conn.execute(
            "INSERT INTO portfolio_snapshots (user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now),
        )


def _seed_watchlist(
    conn: sqlite3.Connection, tickers: Iterable[str], now: str
) -> None:
    rows = [(DEFAULT_USER_ID, t, now) for t in tickers]
    conn.executemany(
        "INSERT OR IGNORE INTO watchlist (user_id, ticker, added_at) "
        "VALUES (?, ?, ?)",
        rows,
    )
