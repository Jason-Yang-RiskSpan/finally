"""Pydantic models for FastAPI request/response shapes.

Keep these aligned with PLAN.md §8. Frontend consumers and Playwright
tests treat the JSON shape returned here as the contract.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Watchlist ---------------------------------------------------------------


class WatchlistAddRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)


class WatchlistItem(BaseModel):
    ticker: str
    price: float | None = None
    previous_price: float | None = None
    session_open: float | None = None
    timestamp: float | None = None


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]


# --- Portfolio ---------------------------------------------------------------


class PositionDTO(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float | None
    market_value: float
    unrealized_pl: float
    unrealized_pl_percent: float


class PortfolioResponse(BaseModel):
    cash_balance: float
    positions: list[PositionDTO]
    market_value: float
    total_value: float
    total_cost_basis: float
    total_unrealized_pl: float
    total_unrealized_pl_percent: float


class TradeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)
    quantity: float = Field(..., gt=0)
    side: Literal["buy", "sell"]


class TradeExecutedResponse(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    executed_at: str
    cash_balance: float
    new_quantity: float
    new_avg_cost: float
    total_value: float


class SnapshotPoint(BaseModel):
    total_value: float
    recorded_at: str


class HistoryResponse(BaseModel):
    snapshots: list[SnapshotPoint]


# --- Chat (LLM stub) ---------------------------------------------------------


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ChatActionTrade(BaseModel):
    model_config = ConfigDict(extra="allow")

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float
    status: str  # "executed" | "rejected"
    price: float | None = None
    reason: str | None = None


class ChatActionWatchlist(BaseModel):
    model_config = ConfigDict(extra="allow")

    ticker: str
    action: Literal["add", "remove"]
    status: str  # "executed" | "rejected"
    reason: str | None = None


class ChatActions(BaseModel):
    trades: list[ChatActionTrade] = Field(default_factory=list)
    watchlist_changes: list[ChatActionWatchlist] = Field(default_factory=list)


class ChatResponse(BaseModel):
    message: str
    actions: ChatActions = Field(default_factory=ChatActions)


# --- Errors ------------------------------------------------------------------


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
