"""Smoke test for the full application lifespan.

Boots ``app.main.create_app`` with the simulator (no MASSIVE_API_KEY) and
verifies the basic route surface responds. The heartbeat task is given
no time to fire — interval is 30s — so it stays inert during the test.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def configured_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "smoke.db"))
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    yield


def test_full_app_boots_and_responds(configured_env):
    """End-to-end smoke: lifespan, simulator, routes."""
    from app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200

        r = client.get("/api/portfolio")
        assert r.status_code == 200
        body = r.json()
        assert body["cash_balance"] == 10000.0

        r = client.get("/api/watchlist")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 10
        # Simulator seeds the cache synchronously on start(), so prices
        # should be present immediately.
        assert all(item["price"] is not None for item in items)
