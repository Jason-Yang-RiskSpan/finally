"""Schema DDL and seed constants.

The full SQL schema for FinAlly lives here as a single string. ``init_db()``
in ``db.session`` executes this against a fresh database; on subsequent runs
the ``IF NOT EXISTS`` guards make the script idempotent.

Schema decisions (see PLAN.md §7 + §13):

* All tables use ``INTEGER PRIMARY KEY AUTOINCREMENT`` for ``id``.
* Every domain table carries a ``user_id TEXT DEFAULT 'default'`` column so
  multi-user is a future configuration change rather than a migration.
* ``UNIQUE(user_id, ticker)`` is enforced on ``watchlist`` and ``positions``.
* ``chat_messages.actions`` is JSON serialized as TEXT (NULL for user
  messages).
* All ``*_at`` columns are timezone-aware ISO 8601 strings.
"""

from __future__ import annotations

# --- Seed constants -------------------------------------------------------

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0

# Initial watchlist matches PLAN.md §7 default seed data.
DEFAULT_WATCHLIST_TICKERS: tuple[str, ...] = (
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
)

# Snapshot heartbeat threshold (PLAN.md §7 portfolio_snapshots): a heartbeat
# write only occurs when the new total_value differs from the last recorded
# value by strictly more than this delta. Trade-driven snapshots ignore this.
SNAPSHOT_DELTA_THRESHOLD = 0.01


# --- DDL ------------------------------------------------------------------

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users_profile (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT    NOT NULL UNIQUE DEFAULT 'default',
    cash_balance  REAL    NOT NULL DEFAULT 10000.0,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   TEXT    NOT NULL DEFAULT 'default',
    ticker    TEXT    NOT NULL,
    added_at  TEXT    NOT NULL,
    UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS positions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL DEFAULT 'default',
    ticker      TEXT    NOT NULL,
    quantity    REAL    NOT NULL,
    avg_cost    REAL    NOT NULL,
    updated_at  TEXT    NOT NULL,
    UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT    NOT NULL DEFAULT 'default',
    ticker       TEXT    NOT NULL,
    side         TEXT    NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity     REAL    NOT NULL,
    price        REAL    NOT NULL,
    executed_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT    NOT NULL DEFAULT 'default',
    total_value  REAL    NOT NULL,
    recorded_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL DEFAULT 'default',
    role        TEXT    NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT    NOT NULL,
    actions     TEXT,
    created_at  TEXT    NOT NULL
);

-- Indexes for the most common access patterns.
-- (chat_messages: LLM engineer reads the most recent N rows by user.)
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created
    ON chat_messages (user_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_trades_user_executed
    ON trades (user_id, executed_at DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_user_recorded
    ON portfolio_snapshots (user_id, recorded_at);
"""
