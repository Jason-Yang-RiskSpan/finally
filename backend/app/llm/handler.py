"""Chat handler: orchestrates context → LLM → auto-execution → persistence.

The backend-engineer registers ``/api/chat`` and delegates to
``handle_chat_message``. Trade and watchlist primitives, the chat-message repo,
and the portfolio context loader are *injected* via ``set_dependencies`` so the
LLM module owns no DB or business-logic code.

Wiring contract — see ``ChatDependencies`` below for the exact shape the
backend-engineer must satisfy.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .client import LLMCallError, call_llm
from .mock import mock_response
from .prompt import build_messages
from .schemas import (
    ActionsPayload,
    LLMResponse,
    TradeAction,
    TradeRequest,
    WatchlistAction,
    WatchlistChange,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------


class ChatDependencies(Protocol):
    """The set of backend services the handler needs.

    Each method is synchronous and returns a plain dict. Concrete
    implementations are owned by the backend-engineer (portfolio + watchlist
    services) and the db-engineer (chat_messages repo).
    """

    # Portfolio context: cash, positions (with current_price + P&L), watchlist
    # (with live prices), total_value.
    def get_portfolio_context(self, user_id: str) -> dict[str, Any]: ...

    # Atomic trade execution. Must return:
    #   {"status": "executed", "price": 191.42}  on success
    #   {"status": "rejected", "reason": "insufficient_cash"} on failure
    def execute_trade(
        self, user_id: str, ticker: str, side: str, quantity: float
    ) -> dict[str, Any]: ...

    # Validated watchlist mutation. Must return:
    #   {"status": "executed"}                 on success
    #   {"status": "rejected", "reason": "..."} on failure
    def add_to_watchlist(self, user_id: str, ticker: str) -> dict[str, Any]: ...
    def remove_from_watchlist(self, user_id: str, ticker: str) -> dict[str, Any]: ...

    # Chat-history repo (db-engineer).
    # ``get_recent`` returns chronological list of {"role", "content"} dicts.
    # ``append`` writes one message; ``actions`` is a JSON-serializable dict or None.
    def get_recent_messages(self, user_id: str, limit: int) -> list[dict[str, Any]]: ...
    def append_message(
        self,
        user_id: str,
        role: str,
        content: str,
        actions: dict[str, Any] | None = None,
    ) -> None: ...


@dataclass
class _DepsHolder:
    deps: ChatDependencies | None = None


_holder = _DepsHolder()


def set_dependencies(deps: ChatDependencies | None) -> None:
    """Wire the backend services. Called during FastAPI startup; pass
    ``None`` during shutdown so test fixtures can't leak a stale
    connection into a later test's request."""
    _holder.deps = deps


def get_dependencies() -> ChatDependencies:
    if _holder.deps is None:
        raise RuntimeError(
            "LLM handler dependencies not configured. Call llm.set_dependencies() "
            "during app startup."
        )
    return _holder.deps


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


HISTORY_LIMIT = 20


def handle_chat_message(
    user_id: str,
    content: str,
    deps: ChatDependencies | None = None,
    llm_caller: Callable[[list[dict[str, str]]], LLMResponse] | None = None,
) -> dict[str, Any]:
    """Process a single user chat turn end-to-end.

    Steps (PLAN.md §9):
      1. Persist the user's message.
      2. Load portfolio context + last 20 messages.
      3. Build prompt and call the LLM (or mock if ``LLM_MOCK=true``).
      4. Auto-execute trades and watchlist changes through injected services.
      5. Persist the assistant message with the ``actions`` payload.
      6. Return ``{"message": ..., "actions": {...}}``.

    Parameters
    ----------
    user_id, content
        Standard chat inputs.
    deps
        Injected for testing. Falls back to the module-level dependencies set
        via ``set_dependencies``.
    llm_caller
        Override the LLM call (tests stub this). Default: mock or real LiteLLM.
    """
    if deps is None:
        deps = get_dependencies()

    user_message = (content or "").strip()
    if not user_message:
        return {
            "message": "Please send a non-empty message.",
            "actions": ActionsPayload().model_dump(),
        }

    # 1. Persist user message immediately so it's recoverable even if a
    #    downstream call fails.
    deps.append_message(user_id, "user", user_message, actions=None)

    # 2. Load context + history (history already includes the user message we
    #    just wrote; we'll append the new turn ourselves to be explicit and
    #    avoid double-include).
    portfolio_context = deps.get_portfolio_context(user_id)
    history_all = deps.get_recent_messages(user_id, HISTORY_LIMIT)
    # Drop the just-appended user message if present at the tail to avoid
    # duplicating it when we add it as the final user turn in build_messages.
    history = _strip_trailing_user_echo(history_all, user_message)

    # 3. Call LLM (mock or real)
    response = _invoke_llm(portfolio_context, history, user_message, llm_caller)

    # 4. Auto-execute
    actions = _execute_actions(deps, user_id, response)

    # 5. Persist assistant message with actions
    deps.append_message(
        user_id,
        "assistant",
        response.message,
        actions=actions.model_dump(),
    )

    # 6. Return to caller
    return {
        "message": response.message,
        "actions": actions.model_dump(),
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _is_mock_mode() -> bool:
    return os.environ.get("LLM_MOCK", "").lower() == "true"


def _invoke_llm(
    portfolio_context: dict[str, Any],
    history: list[dict[str, Any]],
    user_message: str,
    llm_caller: Callable[[list[dict[str, str]]], LLMResponse] | None,
) -> LLMResponse:
    if llm_caller is not None:
        messages = build_messages(portfolio_context, history, user_message)
        return llm_caller(messages)

    if _is_mock_mode():
        logger.info("LLM_MOCK=true — using deterministic mock response")
        return mock_response(user_message)

    messages = build_messages(portfolio_context, history, user_message)
    try:
        return call_llm(messages)
    except LLMCallError as exc:
        logger.warning("LLM call error, returning fallback: %s", exc)
        return LLMResponse(
            message=(
                "I'm having trouble reaching my brain right now. "
                "Please try again in a moment."
            ),
        )


def _strip_trailing_user_echo(
    history: list[dict[str, Any]], user_message: str
) -> list[dict[str, Any]]:
    """If the last entry is the user message we just persisted, drop it."""
    if not history:
        return history
    last = history[-1]
    if last.get("role") == "user" and (last.get("content") or "").strip() == user_message:
        return history[:-1]
    return history


def _execute_actions(
    deps: ChatDependencies, user_id: str, response: LLMResponse
) -> ActionsPayload:
    """Run each trade and watchlist change through the backend's primitives.

    Each item lands in ``actions`` with ``status`` (``executed`` | ``rejected``)
    and an optional ``reason``. Backend errors are caught per-item so one bad
    request doesn't poison the rest.
    """
    actions = ActionsPayload()

    for trade in response.trades:
        actions.trades.append(_run_trade(deps, user_id, trade))

    for change in response.watchlist_changes:
        actions.watchlist_changes.append(_run_watchlist_change(deps, user_id, change))

    return actions


def _run_trade(
    deps: ChatDependencies, user_id: str, trade: TradeRequest
) -> TradeAction:
    ticker = trade.ticker.upper().strip()
    try:
        result = deps.execute_trade(user_id, ticker, trade.side, trade.quantity)
    except Exception as exc:  # defensive — backend should not raise
        logger.exception("Trade primitive raised: %s", exc)
        return TradeAction(
            ticker=ticker,
            side=trade.side,
            quantity=trade.quantity,
            status="rejected",
            reason=f"internal_error: {exc}",
        )

    status = result.get("status")
    if status == "executed":
        return TradeAction(
            ticker=ticker,
            side=trade.side,
            quantity=trade.quantity,
            price=result.get("price"),
            status="executed",
        )
    return TradeAction(
        ticker=ticker,
        side=trade.side,
        quantity=trade.quantity,
        status="rejected",
        reason=str(result.get("reason", "unknown")),
    )


def _run_watchlist_change(
    deps: ChatDependencies, user_id: str, change: WatchlistChange
) -> WatchlistAction:
    ticker = change.ticker.upper().strip()
    try:
        if change.action == "add":
            result = deps.add_to_watchlist(user_id, ticker)
        else:
            result = deps.remove_from_watchlist(user_id, ticker)
    except Exception as exc:
        logger.exception("Watchlist primitive raised: %s", exc)
        return WatchlistAction(
            ticker=ticker,
            action=change.action,
            status="rejected",
            reason=f"internal_error: {exc}",
        )

    status = result.get("status")
    if status == "executed":
        return WatchlistAction(ticker=ticker, action=change.action, status="executed")
    return WatchlistAction(
        ticker=ticker,
        action=change.action,
        status="rejected",
        reason=str(result.get("reason", "unknown")),
    )


# Convenience for the backend route: serialize actions back to JSON for storage.
def actions_to_json(actions: ActionsPayload) -> str:
    return json.dumps(actions.model_dump())


async def handle_chat(*, state: Any, message: str, user_id: str = "default") -> dict[str, Any]:
    """Async entry point for the FastAPI ``/api/chat`` route.

    Dependencies must already be wired via :func:`set_dependencies` during
    app startup. ``state`` is accepted for symmetry with the other routes
    but unused — the wired deps already close over the application state.
    Runs the sync handler in a worker thread so coroutine-based backend
    services (data source, db_lock) remain reachable through the deps
    adapter via ``asyncio.run_coroutine_threadsafe``.
    """
    return await asyncio.to_thread(handle_chat_message, user_id, message)
