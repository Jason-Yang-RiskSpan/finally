"""LLM chat subsystem for FinAlly.

Public API:
    handle_chat_message  - End-to-end chat handler (the route delegates to this)
    set_dependencies     - Wire backend services at app startup
    ChatDependencies     - Protocol describing required injected services
    LLMResponse          - Pydantic model for the LLM's structured output
    ActionsPayload       - Pydantic model for the persisted ``actions`` JSON
    mock_response        - Deterministic mock used when LLM_MOCK=true
"""

from .handler import (
    HISTORY_LIMIT,
    ChatDependencies,
    actions_to_json,
    get_dependencies,
    handle_chat_message,
    set_dependencies,
)
from .mock import mock_response
from .schemas import (
    ActionsPayload,
    LLMResponse,
    TradeAction,
    TradeRequest,
    WatchlistAction,
    WatchlistChange,
)

__all__ = [
    "HISTORY_LIMIT",
    "ActionsPayload",
    "ChatDependencies",
    "LLMResponse",
    "TradeAction",
    "TradeRequest",
    "WatchlistAction",
    "WatchlistChange",
    "actions_to_json",
    "get_dependencies",
    "handle_chat_message",
    "mock_response",
    "set_dependencies",
]
