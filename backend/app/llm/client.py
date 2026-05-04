"""LiteLLM → OpenRouter → Cerebras call site.

Follows the canonical pattern from the ``cerebras-inference`` skill:
    MODEL = "openrouter/openai/gpt-oss-120b"
    EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

We use Structured Outputs by passing ``response_format=LLMResponse`` and
validating the returned JSON via ``LLMResponse.model_validate_json``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .schemas import LLMResponse

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}


class LLMCallError(RuntimeError):
    """Raised when the LLM call or parse fails fatally."""


def call_llm(messages: list[dict[str, str]]) -> LLMResponse:
    """Call the LLM via LiteLLM with structured outputs and return an LLMResponse.

    On parse failure (malformed JSON, missing required fields), we fall back to
    a conservative ``LLMResponse`` containing only a ``message`` and no actions
    so the user always gets a graceful reply.
    """
    # Lazy import so unit tests can stub ``litellm`` without it being installed
    # in every environment, and so the module is importable for offline tooling.
    from litellm import completion  # type: ignore[import-not-found]

    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=LLMResponse,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
        )
    except Exception as exc:  # pragma: no cover - network/API failure path
        logger.exception("LLM call failed: %s", exc)
        raise LLMCallError(f"LLM call failed: {exc}") from exc

    raw = _extract_content(response)
    return parse_response(raw)


def parse_response(raw: str | dict[str, Any]) -> LLMResponse:
    """Parse a raw LLM response (JSON string or dict) into an LLMResponse.

    Graceful failure: malformed JSON or schema mismatch returns a minimal
    LLMResponse with an apologetic message and no actions, instead of raising.
    """
    if isinstance(raw, dict):
        try:
            return LLMResponse.model_validate(raw)
        except Exception as exc:
            logger.warning("LLM response (dict) failed validation: %s", exc)
            return _fallback_response(str(raw))

    if not isinstance(raw, str) or not raw.strip():
        logger.warning("LLM returned empty content")
        return _fallback_response("")

    try:
        return LLMResponse.model_validate_json(raw)
    except Exception as exc:
        logger.warning("LLM response failed JSON validation: %s", exc)
        # Try a best-effort parse: maybe it's valid JSON but missing optional
        # fields, or fields under different casing.
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "message" in data:
                return LLMResponse(
                    message=str(data.get("message", "")),
                    trades=data.get("trades") or [],
                    watchlist_changes=data.get("watchlist_changes") or [],
                )
        except Exception:
            pass
        return _fallback_response(raw)


def _extract_content(response: Any) -> str:
    """Pull the JSON string out of a LiteLLM ``completion`` response."""
    try:
        return response.choices[0].message.content  # type: ignore[no-any-return]
    except (AttributeError, IndexError, KeyError) as exc:  # pragma: no cover
        raise LLMCallError(f"Malformed LiteLLM response: {exc}") from exc


def _fallback_response(raw: str) -> LLMResponse:
    """Conservative response when the LLM output can't be parsed."""
    preview = raw[:120] if raw else "(empty)"
    logger.info("Using fallback LLM response. raw preview: %s", preview)
    return LLMResponse(
        message=(
            "I had trouble formatting my response. Could you rephrase your request?"
        ),
    )
