"""FinAlly database layer.

Owns SQLite schema, seed data, initialization, and atomic-transaction helpers
for trade execution and portfolio snapshots.

The runtime SQLite file lives at the path passed to ``init_db()`` (typically
``db/finally.db`` mounted as a Docker volume). Helpers in this package are the
sole writers to the database; route handlers in ``app/`` should import these
functions rather than executing SQL directly.

Public surface (consumed by the backend engineer)::

    from db import (
        init_db,
        connect,
        get_user,
        get_cash_balance,
        get_positions,
        get_position,
        execute_trade,
        record_snapshot,
        get_snapshots,
        add_chat_message,
        get_recent_chat_messages,
        InsufficientFunds,
        InsufficientShares,
        DEFAULT_USER_ID,
        DEFAULT_CASH_BALANCE,
        DEFAULT_WATCHLIST_TICKERS,
    )
"""

from db.errors import (
    DatabaseError,
    InsufficientFunds,
    InsufficientShares,
)
from db.schema import (
    DEFAULT_CASH_BALANCE,
    DEFAULT_USER_ID,
    DEFAULT_WATCHLIST_TICKERS,
    SNAPSHOT_DELTA_THRESHOLD,
)
from db.session import connect, init_db
from db.repository import (
    add_chat_message,
    add_watchlist_ticker,
    execute_trade,
    get_cash_balance,
    get_position,
    get_positions,
    get_recent_chat_messages,
    get_snapshots,
    get_user,
    get_watchlist,
    record_snapshot,
    remove_watchlist_ticker,
)

__all__ = [
    # session
    "init_db",
    "connect",
    # schema constants
    "DEFAULT_USER_ID",
    "DEFAULT_CASH_BALANCE",
    "DEFAULT_WATCHLIST_TICKERS",
    "SNAPSHOT_DELTA_THRESHOLD",
    # errors
    "DatabaseError",
    "InsufficientFunds",
    "InsufficientShares",
    # repository
    "get_user",
    "get_cash_balance",
    "get_positions",
    "get_position",
    "execute_trade",
    "record_snapshot",
    "get_snapshots",
    "get_watchlist",
    "add_watchlist_ticker",
    "remove_watchlist_ticker",
    "add_chat_message",
    "get_recent_chat_messages",
]
