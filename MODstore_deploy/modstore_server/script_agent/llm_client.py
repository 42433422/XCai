"""LLM 调用的薄抽象，方便单元测试用 ``StubLlmClient`` 替换。

主代码只用 :class:`LlmClient` 协议（``Protocol``），具体实例
:class:`RealLlmClient` 内部走 :func:`modstore_server.llm_chat_proxy.chat_dispatch`。
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
    ) -> None:
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int = 1024,
    ) -> str:
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
