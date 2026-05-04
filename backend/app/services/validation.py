"""Ticker validation shared by manual and LLM-driven adds.

Per PLAN.md §6 the validation has two stages:

1. Syntactic check ``^[A-Z]{1,5}$`` — reject obvious garbage (HTTP 400).
2. Data-source probe — register the ticker with the active data source
   and confirm a price is produced. Failures surface as HTTP 404 with
   a clear ``unknown_ticker`` reason.

This module is the single path used by both the watchlist API and the
future LLM ``watchlist_changes`` action handler. The LLM cannot bypass
validation; it goes through the same function.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from app.market import MarketDataSource, PriceCache
from app.services.session_prices import SessionOpenTracker

TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}$")


class TickerValidationError(Exception):
    """Base class for validation failures."""

    code: str = "invalid_ticker"
    http_status: int = 400


class InvalidTickerSyntax(TickerValidationError):
    code = "invalid_syntax"
    http_status = 400


class UnknownTicker(TickerValidationError):
    code = "unknown_ticker"
    http_status = 404


@dataclass(frozen=True)
class ValidatedTicker:
    """Outcome of a successful validation."""

    ticker: str
    price: float
    session_open: float


def normalize(ticker: str) -> str:
    """Uppercase and strip whitespace."""
    return ticker.strip().upper()


def check_syntax(ticker: str) -> str:
    """Validate the ticker syntactically. Returns the normalized ticker.

    Raises :class:`InvalidTickerSyntax` when the input does not match
    ``^[A-Z]{1,5}$`` after normalization.
    """
    normalized = normalize(ticker)
    if not TICKER_PATTERN.match(normalized):
        raise InvalidTickerSyntax(
            f"ticker {ticker!r} must match ^[A-Z]{{1,5}}$"
        )
    return normalized


async def register_ticker(
    ticker: str,
    *,
    data_source: MarketDataSource,
    cache: PriceCache,
    session_open: SessionOpenTracker,
    probe_timeout: float = 5.0,
    poll_interval: float = 0.05,
) -> ValidatedTicker:
    """Validate and register a ticker.

    Performs the syntactic check, then asks the data source to start
    producing prices. We wait up to ``probe_timeout`` seconds for a
    cached price to appear; if none arrives the ticker is rejected and
    the data source is asked to drop it.

    Returns a :class:`ValidatedTicker` carrying the normalized symbol,
    the latest price, and the captured session-open value.
    """
    normalized = check_syntax(ticker)

    # Already tracked? Return whatever we know.
    cached = cache.get(normalized)
    if cached is not None:
        open_price = session_open.observe(normalized, cached.price)
        return ValidatedTicker(
            ticker=normalized, price=cached.price, session_open=open_price
        )

    await data_source.add_ticker(normalized)

    deadline_iters = max(1, int(probe_timeout / poll_interval))
    for _ in range(deadline_iters):
        cached = cache.get(normalized)
        if cached is not None:
            open_price = session_open.observe(normalized, cached.price)
            return ValidatedTicker(
                ticker=normalized, price=cached.price, session_open=open_price
            )
        await asyncio.sleep(poll_interval)

    # No price ever appeared — the data source rejected it (real Massive
    # API, unknown symbol) or the symbol genuinely has no quote. Roll
    # back the registration so we don't keep polling for a dead ticker.
    try:
        await data_source.remove_ticker(normalized)
    except Exception:  # pragma: no cover - defensive cleanup
        pass
    raise UnknownTicker(
        f"data source produced no price for {normalized!r}"
    )
