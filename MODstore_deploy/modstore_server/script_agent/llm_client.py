"""LLM 调用的薄抽象，方便单元测试用 ``StubLlmClient`` 替换。

主代码只用 :class:`LlmClient` 协议（``Protocol``），具体实例
:class:`RealLlmClient` 内部走 :func:`modstore_server.llm_chat_proxy.chat_dispatch`。

vibe-coding 接入后,``RealLlmClient.from_user_session`` 是新的推荐入口:
- 走 :func:`services.llm.chat_dispatch_via_session`,统一 BYOK / 平台 Key 解析与 quota 消耗。
- 与 :class:`modstore_server.integrations.vibe_adapter.ChatDispatchLLMClient`
  共用同一上游,避免脚本工作流和 vibe-coding 出现两套不一致的 LLM 解析。
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional, Protocol


class LlmClient(Protocol):
    async def chat(
        self, messages: List[Dict[str, str]], *, max_tokens: int = 1024
    ) -> str: ...


class RealLlmClient:
    """绑定到具体 provider/model/key 的真实 LLM 客户端。"""

    def __init__(
        self,
        provider: str,
        *,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        session: Any = None,
        user_id: int = 0,
        use_session_dispatch: bool = False,
    ) -> None:
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._session = session
        self._user_id = int(user_id or 0)
        self._use_session_dispatch = bool(use_session_dispatch)

    @classmethod
    def from_user_session(
        cls,
        session: Any,
        user_id: int,
        provider: str,
        model: str,
    ) -> "RealLlmClient":
        """走 ``llm_key_resolver`` 解析 BYOK,使用 session 路径调用。

        与 :class:`modstore_server.integrations.vibe_adapter.ChatDispatchLLMClient`
        是一对的两面:同一份解析规则、同一份 quota 消耗。
        """
        try:
            from modstore_server.llm_key_resolver import (
                OAI_COMPAT_OPENAI_STYLE_PROVIDERS,
                resolve_api_key,
                resolve_base_url,
            )

            api_key, _ = resolve_api_key(session, user_id, provider)
            base_url = (
                resolve_base_url(session, user_id, provider)
                if provider in OAI_COMPAT_OPENAI_STYLE_PROVIDERS
                else None
            )
        except Exception:  # pragma: no cover - resolver 缺失时降级
            api_key = ""
            base_url = None
        return cls(
            provider,
            api_key=api_key or "",
            model=model,
            base_url=base_url,
            session=session,
            user_id=int(user_id or 0),
            use_session_dispatch=True,
        )

    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int = 1024,
    ) -> str:
        if self._use_session_dispatch and self._session is not None:
            from modstore_server.services.llm import chat_dispatch_via_session

            res = await chat_dispatch_via_session(
                self._session,
                self._user_id,
                self.provider,
                self.model,
                messages,
                max_tokens=max_tokens,
            )
        else:
            from modstore_server.llm_chat_proxy import chat_dispatch

            res = await chat_dispatch(
                self.provider,
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
            )
        if not res.get("ok"):
            raise RuntimeError(
                f"LLM 调用失败: {res.get('error') or res.get('status') or ''}"
            )
        return str(res.get("content") or "")


class StubLlmClient:
    """单测专用：按 FIFO 顺序返回预设回复。每次 ``chat`` 取队首。"""

    def __init__(self, responses: List[str]) -> None:
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int = 1024,
    ) -> str:
        await asyncio.sleep(0)  # 模拟 await
        self.calls.append({"messages": list(messages), "max_tokens": max_tokens})
        if not self._responses:
            raise AssertionError("StubLlmClient: 预设回复已耗尽")
        return self._responses.pop(0)


def extract_code_block(text: str, *, lang: str = "python") -> str:
    """从 LLM 回答里抽 ```lang … ``` 代码段；若无包裹则返回原文 strip。"""
    if not text:
        return ""
    m = re.search(rf"```(?:{lang})?\s*([\s\S]*?)```", text, re.I)
    if m:
        return m.group(1).strip()
    return text.strip()
