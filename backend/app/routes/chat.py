"""Chat route stub.

The LLM engineer will land ``app/llm/handler.py`` exposing
``async def handle_chat(state: AppState, message: str) -> dict``. Until
then this route returns ``503 Service Unavailable`` so callers know the
endpoint exists but isn't wired yet. Once the module is present the
import succeeds and the route delegates to it transparently.
"""

from __future__ import annotations

from importlib import import_module

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ChatActions, ChatMessageRequest, ChatResponse
from app.state import AppState

router = APIRouter(prefix="/api", tags=["chat"])


def _load_handler():
    """Resolve ``app.llm.handler.handle_chat`` lazily."""
    try:
        module = import_module("app.llm.handler")
    except ModuleNotFoundError:
        return None
    return getattr(module, "handle_chat", None)


@router.post("/chat", response_model=ChatResponse)
async def post_chat(req: ChatMessageRequest, request: Request) -> ChatResponse:
    handler = _load_handler()
    if handler is None:
        raise HTTPException(
            status_code=503,
            detail="chat handler not yet implemented (app.llm.handler.handle_chat missing)",
        )
    state: AppState = request.app.state.appstate  # type: ignore[attr-defined]
    result = await handler(state=state, message=req.message)
    if isinstance(result, ChatResponse):
        return result
    if isinstance(result, dict):
        return ChatResponse(
            message=result.get("message", ""),
            actions=ChatActions(**result.get("actions", {})),
        )
    raise HTTPException(status_code=500, detail="invalid chat handler response shape")
