"""High-level data-access functions consumed by route handlers.

Everything that mutates state goes through this module. In particular,
:func:`execute_trade` is the single entry point for both manual and
LLM-issued trades — its conditional cash UPDATE makes concurrent buys
race-safe.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Literal

from db.errors import InsufficientFunds, InsufficientShares
from db.schema import DEFAULT_USER_ID, SNAPSHOT_DELTA_THRESHOLD


Side = Literal["buy", "sell"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TradeResult:
    """Outcome of a successful trade.

    ``new_cash_balance`` and ``new_quantity`` are returned so callers can
    update UI / chat actions without re-querying. ``new_quantity == 0.0``
    means the position row was deleted (sell-to-zero).
    """

    trade_id: int
    ticker: str
    side: Side
    quantity: float
    price: float
    executed_at: str
    cost: float  # signed: positive for buy, negative for sell
    new_cash_balance: float
    new_quantity: float
    new_avg_cost: float


@dataclass(frozen=True)
class Position:
    ticker: str
    quantity: float
    avg_cost: float
    updated_at: str


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def get_user(conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT user_id, cash_balance, created_at FROM users_profile WHERE user_id = ?",
        (user_id,),
    )
    return cur.fetchone()


def get_cash_balance(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID
) -> float:
    cur = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE user_id = ?", (user_id,)
    )
    row = cur.fetchone()
    if row is None:
        raise KeyError(f"unknown user_id: {user_id!r}")
    return float(row["cash_balance"])


def get_positions(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID
) -> list[Position]:
    cur = conn.execute(
        "SELECT ticker, quantity, avg_cost, updated_at FROM positions "
        "WHERE user_id = ? ORDER BY ticker",
        (user_id,),
    )
    return [
        Position(
            ticker=r["ticker"],
            quantity=float(r["quantity"]),
            avg_cost=float(r["avg_cost"]),
            updated_at=r["updated_at"],
        )
        for r in cur.fetchall()
    ]


def get_position(
    conn: sqlite3.Connection, ticker: str, user_id: str = DEFAULT_USER_ID
) -> Position | None:
    cur = conn.execute(
        "SELECT ticker, quantity, avg_cost, updated_at FROM positions "
        "WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return Position(
        ticker=row["ticker"],
        quantity=float(row["quantity"]),
        avg_cost=float(row["avg_cost"]),
        updated_at=row["updated_at"],
    )


def get_watchlist(
    conn: sqlite3.Connection, user_id: str = DEFAULT_USER_ID
) -> list[str]:
    cur = conn.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at, id",
        (user_id,),
    )
    return [row["ticker"] for row in cur.fetchall()]


def add_watchlist_ticker(
    conn: sqlite3.Connection,
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
) -> bool:
    """Insert a ticker. Returns True if a new row was added, False if it
    already existed (UNIQUE conflict suppressed)."""
    now = _utcnow_iso()
    cur = conn.execute(
        "INSERT OR IGNORE INTO watchlist (user_id, ticker, added_at) "
        "VALUES (?, ?, ?)",
        (user_id, ticker, now),
    )
    return cur.rowcount > 0


def remove_watchlist_ticker(
    conn: sqlite3.Connection,
    ticker: str,
    user_id: str = DEFAULT_USER_ID,
) -> bool:
    """Remove a ticker. Returns True if a row was deleted."""
    cur = conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    )
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Trade execution
# ---------------------------------------------------------------------------


def execute_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    side: Side,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER_ID,
) -> TradeResult:
    """Execute a market order atomically.

    All state changes happen inside a single SQLite transaction:

    1. Conditional cash UPDATE (buys) or balance increment (sells)
    2. Position upsert / delete
    3. Append to ``trades`` table

    The conditional cash UPDATE pattern --

    .. code-block:: sql

        UPDATE users_profile
           SET cash_balance = cash_balance - :cost
         WHERE user_id = :user_id AND cash_balance >= :cost

    -- protects against concurrent buys overdrawing the account: if
    ``rowcount == 0`` we know another writer beat us to the cash.

    Raises :class:`InsufficientFunds` for buys without enough cash, and
    :class:`InsufficientShares` for sells exceeding the held quantity.
    """
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")
    if price <= 0:
        raise ValueError(f"price must be positive, got {price}")
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")

    cost = round(quantity * price, 10)  # signed below
    now = _utcnow_iso()

    # Use BEGIN IMMEDIATE so we acquire the write lock up-front; this
    # makes the conditional UPDATE behave under concurrency exactly the
    # way the spec describes.
    conn.execute("BEGIN IMMEDIATE")
    try:
        if side == "buy":
            cur = conn.execute(
                "UPDATE users_profile "
                "   SET cash_balance = cash_balance - ? "
                " WHERE user_id = ? AND cash_balance >= ?",
                (cost, user_id, cost),
            )
            if cur.rowcount == 0:
                # Could be unknown user OR insufficient funds — distinguish.
                bal_row = conn.execute(
                    "SELECT cash_balance FROM users_profile WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
                if bal_row is None:
                    raise KeyError(f"unknown user_id: {user_id!r}")
                raise InsufficientFunds(cost=cost, balance=float(bal_row["cash_balance"]))

            new_qty, new_avg = _apply_buy(conn, user_id, ticker, quantity, price, now)
            signed_cost = cost
        else:  # sell
            current = get_position(conn, ticker, user_id=user_id)
            if current is None or current.quantity < quantity:
                held = current.quantity if current else 0.0
                raise InsufficientShares(ticker=ticker, requested=quantity, held=held)

            cur = conn.execute(
                "UPDATE users_profile "
                "   SET cash_balance = cash_balance + ? "
                " WHERE user_id = ?",
                (cost, user_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"unknown user_id: {user_id!r}")

            new_qty, new_avg = _apply_sell(conn, user_id, ticker, quantity, current, now)
            signed_cost = -cost

        cur = conn.execute(
            "INSERT INTO trades "
            "    (user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, ticker, side, quantity, price, now),
        )
        trade_id = cur.lastrowid

        new_balance = float(
            conn.execute(
                "SELECT cash_balance FROM users_profile WHERE user_id = ?",
                (user_id,),
            ).fetchone()["cash_balance"]
        )

        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise

    return TradeResult(
        trade_id=int(trade_id) if trade_id is not None else 0,
        ticker=ticker,
        side=side,
        quantity=quantity,
        price=price,
        executed_at=now,
        cost=signed_cost,
        new_cash_balance=new_balance,
        new_quantity=new_qty,
        new_avg_cost=new_avg,
    )


def _apply_buy(
    conn: sqlite3.Connection,
    user_id: str,
    ticker: str,
    quantity: float,
    price: float,
    now: str,
) -> tuple[float, float]:
    """Upsert a position for a buy and return the new (quantity, avg_cost)."""
    existing = get_position(conn, ticker, user_id=user_id)
    if existing is None:
        new_qty = quantity
        new_avg = price
        conn.execute(
            "INSERT INTO positions "
            "   (user_id, ticker, quantity, avg_cost, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, ticker, new_qty, new_avg, now),
        )
    else:
        total_qty = existing.quantity + quantity
        # Weighted-average cost: total dollar basis / total shares.
        new_avg = (
            (existing.quantity * existing.avg_cost) + (quantity * price)
        ) / total_qty
        new_qty = total_qty
        conn.execute(
            "UPDATE positions "
            "   SET quantity = ?, avg_cost = ?, updated_at = ? "
            " WHERE user_id = ? AND ticker = ?",
            (new_qty, new_avg, now, user_id, ticker),
        )
    return new_qty, new_avg


def _apply_sell(
    conn: sqlite3.Connection,
    user_id: str,
    ticker: str,
    quantity: float,
    current: Position,
    now: str,
) -> tuple[float, float]:
    """Decrement a position for a sell. Sell-to-zero deletes the row."""
    new_qty = current.quantity - quantity
    # Treat near-zero floats as zero to avoid leaving 1e-15 residue.
    if new_qty <= 1e-9:
        conn.execute(
            "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
        return 0.0, 0.0
    # Avg cost is unchanged on a partial sell (it's the basis, not the value).
    conn.execute(
        "UPDATE positions "
        "   SET quantity = ?, updated_at = ? "
        " WHERE user_id = ? AND ticker = ?",
        (new_qty, now, user_id, ticker),
    )
    return new_qty, current.avg_cost


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


def record_snapshot(
    conn: sqlite3.Connection,
    total_value: float,
    *,
    user_id: str = DEFAULT_USER_ID,
    force: bool = False,
) -> bool:
    """Insert a portfolio snapshot, gated by the heartbeat policy.

    Behavior (PLAN.md §7 portfolio_snapshots):

    * Trade-driven snapshots pass ``force=True`` to always insert.
    * Heartbeat snapshots leave ``force=False``; the row is only inserted
      if ``total_value`` differs from the most recent snapshot by strictly
      more than :data:`SNAPSHOT_DELTA_THRESHOLD` (currently $0.01).

    Returns True if a row was written, False if suppressed.
    """
    if not force:
        cur = conn.execute(
            "SELECT total_value FROM portfolio_snapshots "
            " WHERE user_id = ? "
            " ORDER BY recorded_at DESC, id DESC LIMIT 1",
            (user_id,),
        )
        row = cur.fetchone()
        if row is not None:
            last = float(row["total_value"])
            if round(abs(total_value - last), 6) <= SNAPSHOT_DELTA_THRESHOLD:
                return False

    now = _utcnow_iso()
    conn.execute(
        "INSERT INTO portfolio_snapshots (user_id, total_value, recorded_at) "
        "VALUES (?, ?, ?)",
        (user_id, total_value, now),
    )
    return True


def get_snapshots(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> list[dict[str, Any]]:
    """Return snapshots ordered oldest→newest.

    ``since`` is an ISO 8601 string; only snapshots with
    ``recorded_at >= since`` are returned. Ordering by string works because
    ISO 8601 sorts lexicographically when timezone-normalized.
    """
    if since is None:
        cur = conn.execute(
            "SELECT id, total_value, recorded_at FROM portfolio_snapshots "
            " WHERE user_id = ? "
            " ORDER BY recorded_at, id",
            (user_id,),
        )
    else:
        cur = conn.execute(
            "SELECT id, total_value, recorded_at FROM portfolio_snapshots "
            " WHERE user_id = ? AND recorded_at >= ? "
            " ORDER BY recorded_at, id",
            (user_id, since),
        )
    return [
        {
            "id": int(r["id"]),
            "total_value": float(r["total_value"]),
            "recorded_at": r["recorded_at"],
        }
        for r in cur.fetchall()
    ]


# ---------------------------------------------------------------------------
# Chat messages
# ---------------------------------------------------------------------------


def add_chat_message(
    conn: sqlite3.Connection,
    *,
    role: Literal["user", "assistant"],
    content: str,
    actions: dict[str, Any] | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> int:
    """Append a chat message. Returns the new row id.

    ``actions`` is JSON-serialized; pass ``None`` for user messages.
    """
    if role not in ("user", "assistant"):
        raise ValueError(f"role must be 'user' or 'assistant', got {role!r}")
    if role == "user" and actions is not None:
        raise ValueError("actions must be None for user messages")

    now = _utcnow_iso()
    actions_json = json.dumps(actions) if actions is not None else None
    cur = conn.execute(
        "INSERT INTO chat_messages "
        "   (user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, role, content, actions_json, now),
    )
    return int(cur.lastrowid) if cur.lastrowid is not None else 0


def get_recent_chat_messages(
    conn: sqlite3.Connection,
    *,
    limit: int = 20,
    user_id: str = DEFAULT_USER_ID,
) -> list[dict[str, Any]]:
    """Return the most recent ``limit`` messages, ordered oldest→newest.

    The LLM engineer uses this for the last-20-message conversation
    context. The ordering is deliberately oldest-first so the result
    can be fed straight into the prompt.
    """
    if limit <= 0:
        return []
    cur = conn.execute(
        "SELECT id, role, content, actions, created_at "
        "  FROM chat_messages "
        " WHERE user_id = ? "
        " ORDER BY created_at DESC, id DESC "
        " LIMIT ?",
        (user_id, limit),
    )
    rows = cur.fetchall()
    rows = list(reversed(rows))  # oldest-first for prompt construction
    return [
        {
            "id": int(r["id"]),
            "role": r["role"],
            "content": r["content"],
            "actions": json.loads(r["actions"]) if r["actions"] else None,
            "created_at": r["created_at"],
        }
        for r in rows
    ]


__all__ = [
    "Position",
    "TradeResult",
    "Side",
    "get_user",
    "get_cash_balance",
    "get_positions",
    "get_position",
    "get_watchlist",
    "add_watchlist_ticker",
    "remove_watchlist_ticker",
    "execute_trade",
    "record_snapshot",
    "get_snapshots",
    "add_chat_message",
    "get_recent_chat_messages",
]


# Iterable is imported only for type-hint use elsewhere; keep the import
# stable to satisfy linters in environments where __all__ is consulted.
_ = Iterable
