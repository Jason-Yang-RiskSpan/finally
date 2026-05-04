"""Deterministic mock-mode LLM responses.

Activated when ``LLM_MOCK=true``. The integration-tester's Playwright suite
asserts on these exact strings/shapes, so they MUST stay stable.

Coverage (per PLAN.md §9 LLM Mock Mode):
    1. executed trade           — "buy 5 aapl"
    2. rejected trade            — "buy 1000000 aapl"  (insufficient cash)
    3. watchlist add (executed)  — "watch pypl"
    4. unknown ticker (rejected) — "watch zzzzz"

A default fallback handles anything else — a chatty no-op acknowledgement.
"""

from __future__ import annotations

from .schemas import LLMResponse, TradeRequest, WatchlistChange


def mock_response(user_message: str) -> LLMResponse:
    """Return a deterministic ``LLMResponse`` for the given user message.

    The match is case-insensitive and substring-based to make tests robust to
    light prompt variation. The tester can rely on these triggers.
    """
    msg = (user_message or "").strip().lower()

    # Scenario 4: unknown ticker — "watch zzzzz" must come before scenario 3
    if "zzzzz" in msg:
        return LLMResponse(
            message="Adding ZZZZZ to your watchlist for you.",
            watchlist_changes=[WatchlistChange(ticker="ZZZZZ", action="add")],
        )

    # Scenario 3: watchlist add (executed)
    if "watch" in msg and "pypl" in msg:
        return LLMResponse(
            message="Adding PYPL to your watchlist.",
            watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
        )

    # Scenario 2: rejected trade (insufficient cash) — large quantity
    if "1000000" in msg or "million" in msg:
        return LLMResponse(
            message="Buying 1,000,000 shares of AAPL.",
            trades=[TradeRequest(ticker="AAPL", side="buy", quantity=1_000_000)],
        )

    # Scenario 1: executed trade
    if "buy" in msg and "aapl" in msg:
        return LLMResponse(
            message="Buying 5 shares of AAPL.",
            trades=[TradeRequest(ticker="AAPL", side="buy", quantity=5)],
        )

    # Default fallback — no trades, no watchlist changes
    return LLMResponse(
        message=(
            "I'm running in mock mode. Try: 'buy 5 AAPL', 'buy 1000000 AAPL', "
            "'watch PYPL', or 'watch ZZZZZ'."
        ),
    )
