"""Domain-specific exceptions raised by the data layer."""

from __future__ import annotations


class DatabaseError(Exception):
    """Base class for database-layer errors."""


class InsufficientFunds(DatabaseError):
    """Raised when a buy would overdraw the user's cash balance.

    Mirrors the contract of the conditional cash UPDATE: if ``rowcount == 0``
    the trade is rejected with this exception. The message includes the
    requested cost and current balance so callers (HTTP routes / LLM action
    reporters) can surface a useful reason.
    """

    def __init__(self, cost: float, balance: float) -> None:
        self.cost = cost
        self.balance = balance
        super().__init__(
            f"insufficient_cash: required {cost:.2f}, available {balance:.2f}"
        )


class InsufficientShares(DatabaseError):
    """Raised when a sell would drive a position negative.

    The position upsert never silently truncates a sell — the data layer
    rejects the transaction so the calling code can surface a clean error.
    """

    def __init__(self, ticker: str, requested: float, held: float) -> None:
        self.ticker = ticker
        self.requested = requested
        self.held = held
        super().__init__(
            f"insufficient_shares: ticker={ticker} requested={requested} held={held}"
        )
