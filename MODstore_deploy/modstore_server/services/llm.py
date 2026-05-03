"""LLM chat service port.

Future state: replaced by an HTTP client to a dedicated LLM service. Today the
default implementation simply forwards to ``llm_chat_proxy.chat_dispatch`` so
existing behaviour is preserved.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
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

    async def chat_stream(self, request: LlmChatRequest) -> AsyncIterator[dict[str, Any]]:
        """Stream tokens / usage events; default falls back to non-streaming :meth:`chat`."""

        res = await self.chat(request)
        if res.ok and res.content:
            yield {"type": "delta", "delta": res.content}
        if res.usage:
            yield {"type": "usage", "usage": res.usage}
        if not res.ok:
            yield {"type": "error", "error": res.error or "upstream error"}


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

    async def chat_stream(self, request: LlmChatRequest) -> AsyncIterator[dict[str, Any]]:
        from modstore_server.llm_chat_proxy import chat_dispatch_stream

        async for ev in chat_dispatch_stream(
            request.provider,
            api_key=request.api_key,
            base_url=request.base_url,
            model=request.model,
            messages=list(request.messages),
            max_tokens=request.max_tokens,
        ):
            yield ev


async def chat_dispatch_via_session(
    session: Any,
    user_id: int,
    provider: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    max_tokens: Optional[int] = None,
) -> dict[str, Any]:
    """Resolve BYOK / platform keys via ``llm_key_resolver`` then call ``chat_dispatch``.

    Keeps ``employee_executor`` / ``workflow_nl_graph`` off direct ``llm_*`` imports.
    """

    from modstore_server.llm_chat_proxy import chat_dispatch
    from modstore_server.llm_key_resolver import (
        OAI_COMPAT_OPENAI_STYLE_PROVIDERS,
        resolve_api_key,
        resolve_base_url,
    )

    api_key, _source = resolve_api_key(session, user_id, provider)
    if not api_key:
        return {"ok": False, "error": f"missing api key for provider: {provider}"}
    base_url = None
    if provider in OAI_COMPAT_OPENAI_STYLE_PROVIDERS:
        base_url = resolve_base_url(session, user_id, provider)
    return await chat_dispatch(
        provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )


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
    "chat_dispatch_via_session",
    "get_default_llm_client",
    "set_default_llm_client",
]
