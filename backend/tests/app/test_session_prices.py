"""Tests for the session-open price tracker."""

from __future__ import annotations

from app.market import PriceCache
from app.services.session_prices import SessionOpenTracker, sync_from_cache


def test_observe_captures_first_price():
    tracker = SessionOpenTracker()
    assert tracker.observe("AAPL", 190.0) == 190.0
    # Subsequent observations don't overwrite.
    assert tracker.observe("AAPL", 195.0) == 190.0
    assert tracker.get("AAPL") == 190.0


def test_get_unknown_ticker_returns_none():
    tracker = SessionOpenTracker()
    assert tracker.get("ZZZZ") is None


def test_reset_one_ticker():
    tracker = SessionOpenTracker()
    tracker.observe("AAPL", 190.0)
    tracker.observe("MSFT", 420.0)
    tracker.reset("AAPL")
    assert tracker.get("AAPL") is None
    assert tracker.get("MSFT") == 420.0


def test_reset_all():
    tracker = SessionOpenTracker()
    tracker.observe("AAPL", 1.0)
    tracker.reset()
    assert tracker.all() == {}


def test_sync_from_cache():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.update("MSFT", 420.0)
    tracker = SessionOpenTracker()
    sync_from_cache(tracker, cache)
    assert tracker.get("AAPL") == 190.0
    assert tracker.get("MSFT") == 420.0
