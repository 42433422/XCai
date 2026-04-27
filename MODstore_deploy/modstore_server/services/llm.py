"""LLM chat service port.

Future state: replaced by an HTTP client to a dedicated LLM service. Today the
default implementation simply forwards to ``llm_chat_proxy.chat_dispatch`` so
existing behaviour is preserved.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class LlmChatRequest:
    provider: str
    model: str
    messages: List[Dict[str, str]]
    api_key: str = ""
    base_url: Optional[str] = None
    max_tokens: Optional[int] = None
    user_id: Optional[int] = None
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LlmChatResponse:
    ok: bool
    content: str = ""
    usage: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    status: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "LlmChatResponse":
        return cls(
            ok=bool(payload.get("ok")),
            content=str(payload.get("content") or ""),
            usage=dict(payload.get("usage") or {}),
            error=str(payload.get("error") or ""),
            status=payload.get("status"),
            raw=dict(payload.get("raw") or {}),
        )


class LlmChatClient(ABC):
    @abstractmethod
    async def chat(self, request: LlmChatRequest) -> LlmChatResponse:
        ...


class InProcessLlmChatClient(LlmChatClient):
    """Default port wired to the existing ``llm_chat_proxy``."""

    async def chat(self, request: LlmChatRequest) -> LlmChatResponse:
        from modstore_server.llm_chat_proxy import chat_dispatch

        result = await chat_dispatch(
            request.provider,
            api_key=request.api_key,
            base_url=request.base_url,
            model=request.model,
            messages=list(request.messages),
            max_tokens=request.max_tokens,
        )
        return LlmChatResponse.from_dict(result)


_LOCK = Lock()
_default: LlmChatClient | None = None


def get_default_llm_client() -> LlmChatClient:
    global _default
    with _LOCK:
        if _default is None:
            _default = InProcessLlmChatClient()
        return _default


def set_default_llm_client(client: Optional[LlmChatClient]) -> None:
    global _default
    with _LOCK:
        _default = client


__all__ = [
    "InProcessLlmChatClient",
    "LlmChatClient",
    "LlmChatRequest",
    "LlmChatResponse",
    "get_default_llm_client",
    "set_default_llm_client",
]
