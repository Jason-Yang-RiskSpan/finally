"""Portfolio routes: read state, execute trades, fetch snapshots."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas import (
    HistoryResponse,
    PortfolioResponse,
    PositionDTO,
    SnapshotPoint,
    TradeExecutedResponse,
    TradeRequest,
)
from app.services.portfolio import (
    InsufficientFunds,
    InsufficientShares,
    execute_trade_full,
    valuate_portfolio,
)
from app.services.validation import (
    InvalidTickerSyntax,
    check_syntax,
)
from app.state import AppState
from db import get_snapshots

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _state(request: Request) -> AppState:
    state: AppState = request.app.state.appstate  # type: ignore[attr-defined]
    return state


def _to_response(snapshot) -> PortfolioResponse:
    return PortfolioResponse(
        cash_balance=snapshot.cash_balance,
        positions=[
            PositionDTO(
                ticker=p.ticker,
                quantity=p.quantity,
                avg_cost=p.avg_cost,
                current_price=p.current_price,
                market_value=p.market_value,
                unrealized_pl=p.unrealized_pl,
                unrealized_pl_percent=p.unrealized_pl_percent,
            )
            for p in snapshot.positions
        ],
        market_value=snapshot.market_value,
        total_value=snapshot.total_value,
        total_cost_basis=snapshot.total_cost_basis,
        total_unrealized_pl=snapshot.total_unrealized_pl,
        total_unrealized_pl_percent=snapshot.total_unrealized_pl_percent,
    )


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(request: Request) -> PortfolioResponse:
    state = _state(request)
    async with state.db_lock:
        snapshot = await asyncio.to_thread(
            valuate_portfolio, state.db, state.price_cache
        )
    return _to_response(snapshot)


@router.post("/trade", response_model=TradeExecutedResponse)
async def post_trade(req: TradeRequest, request: Request) -> TradeExecutedResponse:
    state = _state(request)
    try:
        ticker = check_syntax(req.ticker)
    except InvalidTickerSyntax as e:
        raise HTTPException(status_code=400, detail=str(e))

    if state.price_cache.get_price(ticker) is None:
        # Buys without a known price are rejected — the ticker has not
        # been registered. The frontend should add to the watchlist first.
        raise HTTPException(
            status_code=404,
            detail=f"no live price for {ticker!r}; add to watchlist first",
        )

    try:
        executed = await execute_trade_full(
            conn=state.db,
            db_lock=state.db_lock,
            cache=state.price_cache,
            ticker=ticker,
            side=req.side,
            quantity=req.quantity,
        )
    except InsufficientFunds as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientShares as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return TradeExecutedResponse(
        ticker=executed.trade.ticker,
        side=executed.trade.side,
        quantity=executed.trade.quantity,
        price=executed.trade.price,
        executed_at=executed.trade.executed_at,
        cash_balance=executed.trade.new_cash_balance,
        new_quantity=executed.trade.new_quantity,
        new_avg_cost=executed.trade.new_avg_cost,
        total_value=executed.total_value,
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    request: Request,
    since: str | None = Query(default=None),
) -> HistoryResponse:
    state = _state(request)
    async with state.db_lock:
        rows = await asyncio.to_thread(
            get_snapshots, state.db, since=since
        )
    return HistoryResponse(
        snapshots=[
            SnapshotPoint(
                total_value=row["total_value"],
                recorded_at=row["recorded_at"],
            )
            for row in rows
        ]
    )
