"""SSE streaming endpoint tests.

We exercise the generator function directly. Going through TestClient
streaming is awkward because the generator never terminates on its own —
the disconnect signal would need to be staged via a mock. Driving
``_generate`` is cleaner and lets us assert payload semantics line by
line.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.market import PriceCache
from app.routes.stream import RETRY_MS, _build_payload, _generate
from app.services.session_prices import SessionOpenTracker


class FakeRequest:
    """Bare-minimum stand-in for a Starlette request."""

    def __init__(self) -> None:
        self._disconnected = False

    def disconnect(self) -> None:
        self._disconnected = True

    async def is_disconnected(self) -> bool:  # noqa: D401 - matches Starlette name
        return self._disconnected


def _parse_event_block(block: str) -> dict:
    """Parse a single SSE event block (lines split by \\n)."""
    parsed: dict[str, str] = {}
    for line in block.strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            parsed[key.strip()] = value.strip()
    return parsed


@pytest.fixture
def cache_with_aapl() -> PriceCache:
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    return cache


@pytest.fixture
def session_open_with_aapl() -> SessionOpenTracker:
    tracker = SessionOpenTracker()
    tracker.observe("AAPL", 190.0)
    return tracker


def test_build_payload_includes_session_open(cache_with_aapl, session_open_with_aapl):
    payload = _build_payload(cache_with_aapl, session_open_with_aapl)
    assert "AAPL" in payload
    assert payload["AAPL"]["session_open"] == 190.0
    assert payload["AAPL"]["price"] == 190.0
    # Schema fields from to_dict() are also present.
    assert "previous_price" in payload["AAPL"]
    assert "direction" in payload["AAPL"]


async def test_generator_emits_retry_then_initial_payload(cache_with_aapl, session_open_with_aapl):
    request = FakeRequest()
    gen = _generate(
        request,  # type: ignore[arg-type]
        cache_with_aapl,
        session_open_with_aapl,
        last_event_id=None,
        poll_interval=0.01,
    )
    # First yield: retry directive.
    first = await gen.__anext__()
    assert first.startswith(f"retry: {RETRY_MS}")

    # Second yield: initial snapshot at current cache version.
    second = await gen.__anext__()
    parsed = _parse_event_block(second)
    assert parsed["id"] == str(cache_with_aapl.version)
    body = json.loads(parsed["data"])
    assert "AAPL" in body

    # Disconnect and ensure the generator exits cleanly.
    request.disconnect()
    with pytest.raises(StopAsyncIteration):
        # poll once and then stop because is_disconnected returns True.
        await asyncio.wait_for(gen.__anext__(), timeout=1.0)


async def test_generator_emits_only_on_version_advance(cache_with_aapl, session_open_with_aapl):
    request = FakeRequest()
    gen = _generate(
        request,  # type: ignore[arg-type]
        cache_with_aapl,
        session_open_with_aapl,
        last_event_id=None,
        poll_interval=0.01,
    )
    await gen.__anext__()  # retry
    await gen.__anext__()  # initial snapshot

    # Without any cache update, the generator should not yield another
    # event in a small time window. Use a survivable timeout helper.
    pending = asyncio.ensure_future(gen.__anext__())
    done, _ = await asyncio.wait({pending}, timeout=0.05)
    assert pending not in done, "generator emitted without a cache update"

    # Now advance the cache; the pending task should resolve.
    cache_with_aapl.update("AAPL", 191.0)
    next_event = await asyncio.wait_for(pending, timeout=1.0)
    parsed = _parse_event_block(next_event)
    assert parsed["id"] == str(cache_with_aapl.version)
    body = json.loads(parsed["data"])
    assert body["AAPL"]["price"] == 191.0


async def test_generator_resume_skips_initial_when_id_current(
    cache_with_aapl, session_open_with_aapl
):
    """Last-Event-ID equal to current version → no immediate replay."""
    request = FakeRequest()
    last_id = str(cache_with_aapl.version)
    gen = _generate(
        request,  # type: ignore[arg-type]
        cache_with_aapl,
        session_open_with_aapl,
        last_event_id=last_id,
        poll_interval=0.01,
    )
    first = await gen.__anext__()
    assert first.startswith("retry:")
    # Should not get an immediate snapshot — version hasn't moved.
    pending = asyncio.ensure_future(gen.__anext__())
    done, _ = await asyncio.wait({pending}, timeout=0.05)
    assert pending not in done
    pending.cancel()
    try:
        await pending
    except (asyncio.CancelledError, StopAsyncIteration):
        pass


async def test_generator_resume_replays_when_id_stale(
    cache_with_aapl, session_open_with_aapl
):
    """Last-Event-ID below current version → immediate snapshot."""
    request = FakeRequest()
    cache_with_aapl.update("AAPL", 191.0)  # bump version
    last_id = "1"  # behind current
    gen = _generate(
        request,  # type: ignore[arg-type]
        cache_with_aapl,
        session_open_with_aapl,
        last_event_id=last_id,
        poll_interval=0.01,
    )
    await gen.__anext__()  # retry
    next_event = await gen.__anext__()
    parsed = _parse_event_block(next_event)
    assert int(parsed["id"]) == cache_with_aapl.version
    body = json.loads(parsed["data"])
    assert body["AAPL"]["price"] == 191.0


async def test_generator_handles_invalid_last_event_id(cache_with_aapl, session_open_with_aapl):
    request = FakeRequest()
    gen = _generate(
        request,  # type: ignore[arg-type]
        cache_with_aapl,
        session_open_with_aapl,
        last_event_id="not-an-int",
        poll_interval=0.01,
    )
    await gen.__anext__()  # retry
    # Should treat as fresh client and yield current snapshot.
    next_event = await gen.__anext__()
    assert "data:" in next_event
