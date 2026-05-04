"""Session-open price tracker.

PLAN.md §6 asks the SSE payload to include a per-ticker ``session_open``
price -- the first price observed in the cache after backend startup.
Daily change % on the frontend is computed against this value.

The :class:`SessionOpenTracker` is a thin in-memory dict guarded by a
threading lock. We capture an open price the first time we see a ticker
after startup; later rounds of polling do not overwrite it.
"""

from __future__ import annotations

from threading import Lock

from app.market import PriceCache


class SessionOpenTracker:
    """Records the session-open price for each ticker.

    Captured the first time the price cache reports a value. Stays
    fixed for the rest of the process lifetime, even if the ticker is
    removed from the watchlist and later re-added.
    """

    def __init__(self) -> None:
        self._open: dict[str, float] = {}
        self._lock = Lock()

    def observe(self, ticker: str, price: float) -> float:
        """Record ``price`` as the open if we haven't seen ``ticker``.

        Returns the current open price for the ticker (whether newly
        captured or previously recorded).
        """
        with self._lock:
            if ticker not in self._open:
                self._open[ticker] = price
            return self._open[ticker]

    def get(self, ticker: str) -> float | None:
        with self._lock:
            return self._open.get(ticker)

    def all(self) -> dict[str, float]:
        with self._lock:
            return dict(self._open)

    def reset(self, ticker: str | None = None) -> None:
        """Clear tracked opens (one ticker, or everything if ``None``)."""
        with self._lock:
            if ticker is None:
                self._open.clear()
            else:
                self._open.pop(ticker, None)


def sync_from_cache(tracker: SessionOpenTracker, cache: PriceCache) -> None:
    """Populate the tracker from any tickers already in the cache.

    Called after data-source startup to capture open prices for the
    initial seed batch.
    """
    for ticker, update in cache.get_all().items():
        tracker.observe(ticker, update.price)
