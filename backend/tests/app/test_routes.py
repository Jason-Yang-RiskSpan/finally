"""Route-level tests using FastAPI's TestClient.

We build a small FastAPI instance pointed at the test ``AppState`` so the
tests are deterministic and don't spawn background tasks.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import asyncio

from app.llm import handler as llm_handler
from app.routes import chat as chat_routes
from app.routes import health as health_routes
from app.routes import portfolio as portfolio_routes
from app.routes import stream as stream_routes
from app.routes import watchlist as watchlist_routes
from app.services.llm_deps import AppStateChatDeps
from app.state import AppState


def _make_app(state: AppState) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.appstate = state
        llm_handler.set_dependencies(
            AppStateChatDeps(state, asyncio.get_running_loop())
        )
        try:
            yield
        finally:
            llm_handler.set_dependencies(None)

    app = FastAPI(lifespan=lifespan)
    app.include_router(health_routes.router)
    app.include_router(portfolio_routes.router)
    app.include_router(watchlist_routes.router)
    app.include_router(stream_routes.router)
    app.include_router(chat_routes.router)
    return app


@pytest.fixture
def client(app_state) -> TestClient:
    app = _make_app(app_state)
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_get_portfolio_empty(client: TestClient):
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert body["cash_balance"] == 10000.0
    assert body["positions"] == []
    assert body["total_value"] == 10000.0


def test_get_watchlist_seeded(client: TestClient, app_state):
    r = client.get("/api/watchlist")
    assert r.status_code == 200
    items = r.json()["items"]
    tickers = [item["ticker"] for item in items]
    assert "AAPL" in tickers
    assert len(tickers) == 10


def test_post_watchlist_add_invalid_syntax(client: TestClient):
    r = client.post("/api/watchlist", json={"ticker": "bad ticker"})
    assert r.status_code == 400


def test_post_watchlist_add_unknown(client: TestClient, app_state):
    app_state.data_source.default_price = None
    r = client.post("/api/watchlist", json={"ticker": "ZZZZZ"})
    assert r.status_code == 404


def test_post_watchlist_add_success(client: TestClient, app_state):
    r = client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert r.status_code == 201
    item = r.json()
    assert item["ticker"] == "PYPL"
    assert item["session_open"] is not None


def test_delete_watchlist_existing(client: TestClient, app_state):
    # Add then delete.
    r = client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert r.status_code == 201
    r = client.delete("/api/watchlist/PYPL")
    assert r.status_code == 204


def test_delete_watchlist_missing(client: TestClient):
    r = client.delete("/api/watchlist/NEVER")
    assert r.status_code == 404


def test_delete_watchlist_invalid_syntax(client: TestClient):
    r = client.delete("/api/watchlist/12345!@")
    assert r.status_code == 400


def test_post_trade_buy_succeeds(client: TestClient, app_state):
    app_state.price_cache.update("AAPL", 100.0)
    r = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 5, "side": "buy"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["side"] == "buy"
    assert body["cash_balance"] == pytest.approx(10000 - 500)
    assert body["new_quantity"] == 5


def test_post_trade_insufficient_cash(client: TestClient, app_state):
    app_state.price_cache.update("AAPL", 100.0)
    r = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 200, "side": "buy"},
    )
    assert r.status_code == 400
    assert "insufficient_cash" in r.json()["detail"]


def test_post_trade_no_live_price(client: TestClient):
    r = client.post(
        "/api/portfolio/trade",
        json={"ticker": "ZZZZ", "quantity": 1, "side": "buy"},
    )
    assert r.status_code == 404


def test_post_trade_invalid_quantity(client: TestClient, app_state):
    app_state.price_cache.update("AAPL", 100.0)
    r = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 0, "side": "buy"},
    )
    # Pydantic rejects quantity <= 0 as 422.
    assert r.status_code == 422


def test_post_trade_sell_more_than_held(client: TestClient, app_state):
    app_state.price_cache.update("AAPL", 100.0)
    r = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 1, "side": "sell"},
    )
    assert r.status_code == 400


def test_get_history(client: TestClient):
    r = client.get("/api/portfolio/history")
    assert r.status_code == 200
    snapshots = r.json()["snapshots"]
    # Seed inserts a t=0 snapshot.
    assert len(snapshots) >= 1
    assert snapshots[0]["total_value"] == 10000.0


def test_get_history_with_since_filter(client: TestClient, app_state):
    # `since` in the future returns nothing.
    r = client.get("/api/portfolio/history?since=2999-01-01T00:00:00+00:00")
    assert r.status_code == 200
    assert r.json()["snapshots"] == []


def test_chat_returns_mock_response(client: TestClient, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    r = client.post("/api/chat", json={"message": "hello"})
    assert r.status_code == 200
    body = r.json()
    assert "message" in body and isinstance(body["message"], str)
    assert "actions" in body
    assert "trades" in body["actions"]
    assert "watchlist_changes" in body["actions"]


def test_chat_executes_mock_buy_trade(client: TestClient, app_state, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    # The mock trades AAPL — make sure it's priced so execute_trade can fill.
    app_state.price_cache.update("AAPL", 190.0)
    r = client.post("/api/chat", json={"message": "buy 5 aapl"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["actions"]["trades"]) == 1
    trade = body["actions"]["trades"][0]
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["status"] == "executed"
