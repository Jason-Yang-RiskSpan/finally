"""SSE streaming endpoint for live price updates.

Per PLAN.md §6:

* Emits a single event whenever the price-cache version advances.
  No fixed-cadence polling on the wire — the cadence is driven by the
  data source (~500ms simulator, ~15s Massive free tier).
* Sends a ``retry: 3000`` directive at connection start so the browser
  uses a sane backoff if the network drops.
* Honors ``Last-Event-ID``: a client resuming with an event id less than
  the current cache version receives an immediate snapshot. The id is
  the cache version counter as an integer string.
* Each price record carries: ticker, price, previous_price, timestamp,
  change, change_percent, direction, and session_open.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Optional

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from app.market import PriceCache
from app.services.session_prices import SessionOpenTracker
from app.state import AppState

logger = logging.getLogger(__name__)

RETRY_MS = 3000
DEFAULT_POLL_INTERVAL = 0.1  # 100ms — only loops, doesn't emit on every tick


router = APIRouter(prefix="/api/stream", tags=["streaming"])


def _build_payload(
    cache: PriceCache, session_open: SessionOpenTracker
) -> dict[str, dict[str, float | str]]:
    payload: dict[str, dict[str, float | str]] = {}
    for ticker, update in cache.get_all().items():
        # Make sure session-open is captured (in case the data source
        # populated the cache before the tracker was wired up).
        open_price = session_open.observe(ticker, update.price)
        record = update.to_dict()
        record["session_open"] = open_price
        payload[ticker] = record
    return payload


async def _generate(
    request: Request,
    cache: PriceCache,
    session_open: SessionOpenTracker,
    last_event_id: Optional[str],
    poll_interval: float,
) -> AsyncGenerator[str, None]:
    yield f"retry: {RETRY_MS}\n\n"

    # Resume / cold-start logic.
    try:
        last_seen = int(last_event_id) if last_event_id else -1
    except ValueError:
        last_seen = -1

    current = cache.version
    if current > last_seen:
        payload = _build_payload(cache, session_open)
        if payload:
            yield f"id: {current}\ndata: {json.dumps(payload)}\n\n"
            last_seen = current

    try:
        while True:
            if await request.is_disconnected():
                logger.debug("SSE client disconnected")
                return
            current = cache.version
            if current != last_seen:
                payload = _build_payload(cache, session_open)
                if payload:
                    yield f"id: {current}\ndata: {json.dumps(payload)}\n\n"
                last_seen = current
            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:  # pragma: no cover - normal shutdown path
        logger.debug("SSE generator cancelled")
        raise


@router.get("/prices")
async def stream_prices(
    request: Request,
    last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    state: AppState = request.app.state.appstate  # type: ignore[attr-defined]
    return StreamingResponse(
        _generate(
            request,
            state.price_cache,
            state.session_open,
            last_event_id,
            DEFAULT_POLL_INTERVAL,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
