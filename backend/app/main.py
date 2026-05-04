"""FastAPI entry point.

Composes the long-lived application state, registers routes, and starts
the snapshot heartbeat. Static frontend assets are served at the catch-all
mount when present (the static directory is populated by the Docker build
stage; in local dev it's typically absent and Next.js handles the UI).
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.market import PriceCache, create_market_data_source
from app.routes import chat as chat_routes
from app.routes import health as health_routes
from app.routes import portfolio as portfolio_routes
from app.routes import stream as stream_routes
from app.routes import watchlist as watchlist_routes
from app.services.heartbeat import run_heartbeat_loop
from app.services.session_prices import SessionOpenTracker, sync_from_cache
from app.services.watchlist import reconcile_tracked_tickers
from app.state import AppState
from db import DEFAULT_WATCHLIST_TICKERS, init_db

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "db/finally.db"
STATIC_DIR_NAME = "static"


def _resolve_db_path() -> str:
    """Pick the SQLite path. Honors ``FINALLY_DB_PATH`` env var."""
    return os.environ.get("FINALLY_DB_PATH", DEFAULT_DB_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Boot/shutdown the app's long-lived resources."""
    db_path = _resolve_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = init_db(db_path)
    cache = PriceCache()
    data_source = create_market_data_source(cache)
    session_open = SessionOpenTracker()

    state = AppState(
        db=conn,
        price_cache=cache,
        data_source=data_source,
        session_open=session_open,
    )
    app.state.appstate = state  # type: ignore[attr-defined]

    # Bootstrap the data source with the union of watchlist + held-position
    # tickers. We rely on the seed data populating the watchlist on first
    # boot; subsequent boots reuse whatever is on disk.
    from db import get_positions, get_watchlist

    initial_tickers = list(dict.fromkeys(
        list(get_watchlist(conn)) or list(DEFAULT_WATCHLIST_TICKERS)
    ))
    held = [p.ticker for p in get_positions(conn)]
    for t in held:
        if t not in initial_tickers:
            initial_tickers.append(t)

    await data_source.start(initial_tickers)
    sync_from_cache(session_open, cache)

    # In case any DB-known ticker isn't yet registered (e.g., the data
    # source was unable to seed it during start()), reconcile now.
    await reconcile_tracked_tickers(
        conn=conn,
        db_lock=state.db_lock,
        data_source=data_source,
        cache=cache,
        session_open=session_open,
    )

    # Background snapshot heartbeat.
    state.heartbeat_task = asyncio.create_task(
        run_heartbeat_loop(conn, cache, state.db_lock),
        name="snapshot-heartbeat",
    )

    # Wire LLM chat dependencies to the live AppState. The handler runs in
    # a worker thread; the adapter dispatches async calls back to this loop.
    from app.llm import handler as llm_handler
    from app.services.llm_deps import AppStateChatDeps

    llm_handler.set_dependencies(
        AppStateChatDeps(state, asyncio.get_running_loop())
    )

    try:
        yield
    finally:
        llm_handler.set_dependencies(None)
        if state.heartbeat_task is not None:
            state.heartbeat_task.cancel()
            try:
                await state.heartbeat_task
            except (asyncio.CancelledError, Exception):
                pass
        try:
            await data_source.stop()
        except Exception:  # pragma: no cover - shutdown best-effort
            logger.exception("Data source shutdown raised")
        conn.close()


def _mount_static(app: FastAPI) -> None:
    """Mount the Next.js static export at ``/`` if it has been built.

    Skipped silently when the directory is missing (typical in dev / tests).
    """
    candidates = [
        Path(__file__).resolve().parent.parent / STATIC_DIR_NAME,
        Path.cwd() / STATIC_DIR_NAME,
    ]
    for candidate in candidates:
        if candidate.is_dir():
            app.mount("/", StaticFiles(directory=str(candidate), html=True), name="static")
            logger.info("Mounted static frontend from %s", candidate)
            return


def create_app() -> FastAPI:
    """Build a FastAPI instance. Used by both production and tests."""
    app = FastAPI(
        title="FinAlly",
        description="AI-powered trading workstation — backend API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health_routes.router)
    app.include_router(portfolio_routes.router)
    app.include_router(watchlist_routes.router)
    app.include_router(stream_routes.router)
    app.include_router(chat_routes.router)
    _mount_static(app)
    return app


app = create_app()
