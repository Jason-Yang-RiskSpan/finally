"""Watchlist routes: list, add, remove."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.schemas import (
    WatchlistAddRequest,
    WatchlistItem,
    WatchlistResponse,
)
from app.services.validation import (
    InvalidTickerSyntax,
    UnknownTicker,
    check_syntax,
)
from app.services.watchlist import (
    add_to_watchlist,
    list_watchlist_with_prices,
    remove_from_watchlist,
)
from app.state import AppState

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def _state(request: Request) -> AppState:
    state: AppState = request.app.state.appstate  # type: ignore[attr-defined]
    return state


@router.get("", response_model=WatchlistResponse)
async def list_watchlist(request: Request) -> WatchlistResponse:
    state = _state(request)
    async with state.db_lock:
        entries = list_watchlist_with_prices(
            state.db, state.price_cache, state.session_open
        )
    return WatchlistResponse(
        items=[
            WatchlistItem(
                ticker=e.ticker,
                price=e.price,
                previous_price=e.previous_price,
                session_open=e.session_open,
                timestamp=e.timestamp,
            )
            for e in entries
        ]
    )


@router.post("", response_model=WatchlistItem, status_code=201)
async def add_ticker(req: WatchlistAddRequest, request: Request) -> WatchlistItem:
    state = _state(request)
    try:
        validated = await add_to_watchlist(
            conn=state.db,
            db_lock=state.db_lock,
            data_source=state.data_source,
            cache=state.price_cache,
            session_open=state.session_open,
            ticker=req.ticker,
        )
    except InvalidTickerSyntax as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UnknownTicker as e:
        raise HTTPException(status_code=404, detail=str(e))

    update = state.price_cache.get(validated.ticker)
    return WatchlistItem(
        ticker=validated.ticker,
        price=validated.price,
        previous_price=update.previous_price if update else None,
        session_open=validated.session_open,
        timestamp=update.timestamp if update else None,
    )


@router.delete("/{ticker}", status_code=204)
async def delete_ticker(ticker: str, request: Request):
    state = _state(request)
    try:
        check_syntax(ticker)
    except InvalidTickerSyntax as e:
        raise HTTPException(status_code=400, detail=str(e))
    deleted = await remove_from_watchlist(
        conn=state.db,
        db_lock=state.db_lock,
        data_source=state.data_source,
        cache=state.price_cache,
        ticker=ticker,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail=f"ticker not on watchlist: {ticker}")
    # 204 No Content
