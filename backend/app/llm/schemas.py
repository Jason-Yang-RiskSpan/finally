"""Pydantic schemas for LLM structured outputs and chat I/O.

The LLM returns a single JSON object matching ``LLMResponse``. Trades and
watchlist changes are optional — when present, the chat handler auto-executes
each entry and records the outcome in the persisted ``actions`` JSON.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TradeRequest(BaseModel):
    """A trade the LLM wants to execute on the user's behalf."""

    ticker: str = Field(..., description="Ticker symbol, e.g. AAPL")
    side: Literal["buy", "sell"] = Field(..., description="Trade direction")
    quantity: float = Field(..., gt=0, description="Number of shares (fractional allowed)")


class WatchlistChange(BaseModel):
    """A watchlist mutation the LLM wants to perform."""

    ticker: str = Field(..., description="Ticker symbol, e.g. PYPL")
    action: Literal["add", "remove"] = Field(..., description="add or remove")


class LLMResponse(BaseModel):
    """Top-level structured response from the LLM.

    ``message`` is the conversational text shown to the user. ``trades`` and
    ``watchlist_changes`` are optional arrays the backend auto-executes.
    """

    message: str = Field(..., description="Conversational response shown to the user")
    trades: list[TradeRequest] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Persisted ``actions`` payload (PLAN.md §9 step 7)
# ---------------------------------------------------------------------------


class TradeAction(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float | None = None
    status: Literal["executed", "rejected"]
    reason: str | None = None


class WatchlistAction(BaseModel):
    ticker: str
    action: Literal["add", "remove"]
    status: Literal["executed", "rejected"]
    reason: str | None = None


class ActionsPayload(BaseModel):
    trades: list[TradeAction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistAction] = Field(default_factory=list)
