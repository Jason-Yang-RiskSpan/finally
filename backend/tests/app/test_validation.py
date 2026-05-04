"""Ticker-validation tests covering syntactic + data-source probe paths."""

from __future__ import annotations

import pytest

from app.services.validation import (
    InvalidTickerSyntax,
    UnknownTicker,
    check_syntax,
    register_ticker,
)


@pytest.mark.parametrize("good", ["A", "AA", "MSFT", "GOOGL", "TSLA"])
def test_check_syntax_accepts_valid(good: str):
    assert check_syntax(good) == good


def test_check_syntax_normalizes_case_and_whitespace():
    assert check_syntax(" aapl ") == "AAPL"


@pytest.mark.parametrize(
    "bad",
    ["", "TOOLONG", "12", "AAPL.", "AA AA", "AA-PL", "$$$"],
)
def test_check_syntax_rejects_invalid(bad: str):
    with pytest.raises(InvalidTickerSyntax):
        check_syntax(bad)


async def test_register_ticker_success(stub_source, cache, session_open):
    stub_source.default_price = 250.0
    validated = await register_ticker(
        "PYPL",
        data_source=stub_source,
        cache=cache,
        session_open=session_open,
    )
    assert validated.ticker == "PYPL"
    assert validated.price == 250.0
    assert validated.session_open == 250.0
    assert "PYPL" in stub_source.get_tickers()


async def test_register_ticker_unknown_rejected(stub_source, cache, session_open):
    # default_price=None means stub doesn't seed the cache → looks unknown.
    stub_source.default_price = None
    with pytest.raises(UnknownTicker):
        await register_ticker(
            "ZZZZZ",
            data_source=stub_source,
            cache=cache,
            session_open=session_open,
            probe_timeout=0.05,
            poll_interval=0.01,
        )
    # Failed registration cleaned up.
    assert "ZZZZZ" not in stub_source.get_tickers()


async def test_register_ticker_normalizes_bad_syntax_first(stub_source, cache, session_open):
    with pytest.raises(InvalidTickerSyntax):
        await register_ticker(
            "1234567",
            data_source=stub_source,
            cache=cache,
            session_open=session_open,
        )


async def test_register_ticker_returns_existing_open(stub_source, cache, session_open):
    """If the ticker is already in the cache, we get an immediate response."""
    cache.update("AAPL", 190.0)
    session_open.observe("AAPL", 190.0)
    validated = await register_ticker(
        "AAPL",
        data_source=stub_source,
        cache=cache,
        session_open=session_open,
    )
    # No re-add needed; session_open held.
    assert validated.session_open == 190.0
