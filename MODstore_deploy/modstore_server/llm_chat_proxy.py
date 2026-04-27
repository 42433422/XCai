"""统一聊天代理：OpenAI 兼容 / Anthropic / Google Gemini。"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from modstore_server.llm_key_resolver import (
    OAI_COMPAT_OPENAI_STYLE_PROVIDERS,
    openai_compat_default_root,
)


def _normalize_openai_base(provider: str, base_url: Optional[str]) -> str:
    b = (base_url or openai_compat_default_root(provider)).rstrip("/")
    if not (b.endswith("/v1") or b.endswith("/v2") or b.endswith("/v3") or b.endswith("/v4")):
        b = b + "/v1"
    return b


async def chat_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    *,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/chat/completions"
    body: Dict[str, Any] = {"model": model, "messages": messages}
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        text = r.text
        if r.status_code >= 400:
            return {"ok": False, "status": r.status_code, "error": text[:2000]}
        data = r.json()
    choice0 = (data.get("choices") or [{}])[0]
    msg = choice0.get("message") or {}
    content = msg.get("content") or ""
    return {"ok": True, "content": content, "usage": data.get("usage") or {}, "raw": data}


async def stream_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    *,
    max_tokens: Optional[int] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Stream OpenAI-compatible chat completions as normalized events.

    Yields:
      {"type": "delta", "delta": "..."}
      {"type": "usage", "usage": {...}} when upstream provides stream_options.include_usage
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        ) as r:
            if r.status_code >= 400:
                text = await r.aread()
                yield {"type": "error", "status": r.status_code, "error": text.decode("utf-8", errors="ignore")[:2000]}
                return
            async for line in r.aiter_lines():
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                if raw == "[DONE]":
                    break
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if data.get("usage"):
                    yield {"type": "usage", "usage": data.get("usage") or {}}
                choice0 = (data.get("choices") or [{}])[0] or {}
                delta = choice0.get("delta") or {}
                content = delta.get("content")
                if content:
                    yield {"type": "delta", "delta": str(content)}


def _oai_to_anthropic(messages: List[Dict[str, str]]) -> tuple[str, List[Dict[str, Any]]]:
    system_parts: List[str] = []
    out: List[Dict[str, Any]] = []
    for m in messages:
        role = (m.get("role") or "user").strip()
        content = (m.get("content") or "").strip()
        if role == "system":
            system_parts.append(content)
            continue
        if role not in ("user", "assistant"):
            role = "user"
        out.append({"role": role, "content": content})
    system = "\n\n".join(system_parts) if system_parts else ""
    return system, out


async def chat_anthropic(
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    *,
    max_tokens: int = 1024,
) -> Dict[str, Any]:
    system, msgs = _oai_to_anthropic(messages)
    url = "https://api.anthropic.com/v1/messages"
    body: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": msgs,
    }
    if system:
        body["system"] = system
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
        )
        text = r.text
        if r.status_code >= 400:
            return {"ok": False, "status": r.status_code, "error": text[:2000]}
        data = r.json()
    blocks = data.get("content") or []
    parts: List[str] = []
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "text":
            parts.append(str(b.get("text") or ""))
    return {"ok": True, "content": "\n".join(parts), "usage": data.get("usage") or {}, "raw": data}


def _oai_to_gemini(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    contents: List[Dict[str, Any]] = []
    system_chunks: List[str] = []
    for m in messages:
        role = (m.get("role") or "user").strip()
        content = (m.get("content") or "").strip()
        if role == "system":
            system_chunks.append(content)
            continue
        g_role = "user" if role == "user" else "model"
        text = content
        if system_chunks and g_role == "user" and not contents:
            text = "\n\n".join(system_chunks) + "\n\n" + text
            system_chunks = []
        contents.append({"role": g_role, "parts": [{"text": text}]})
    return contents


async def chat_google(
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
) -> Dict[str, Any]:
    contents = _oai_to_gemini(messages)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            url,
            params={"key": api_key},
            json={"contents": contents},
        )
        text = r.text
        if r.status_code >= 400:
            return {"ok": False, "status": r.status_code, "error": text[:2000]}
        data = r.json()
    cands = data.get("candidates") or []
    if not cands:
        return {"ok": False, "error": "no candidates", "raw": data}
    parts = (((cands[0] or {}).get("content") or {}).get("parts")) or []
    texts = [str(p.get("text") or "") for p in parts if isinstance(p, dict)]
    usage = data.get("usageMetadata") or data.get("usage") or {}
    return {"ok": True, "content": "\n".join(texts), "usage": usage, "raw": data}


async def chat_dispatch(
    provider: str,
    *,
    api_key: str,
    base_url: Optional[str],
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    if provider in OAI_COMPAT_OPENAI_STYLE_PROVIDERS:
        b = _normalize_openai_base(provider, base_url)
        return await chat_openai_compatible(b, api_key, model, messages, max_tokens=max_tokens)
    if provider == "anthropic":
        return await chat_anthropic(api_key, model, messages, max_tokens=max_tokens or 1024)
    if provider == "google":
        return await chat_google(api_key, model, messages)
    return {"ok": False, "error": f"unsupported provider: {provider}"}


async def chat_dispatch_stream(
    provider: str,
    *,
    api_key: str,
    base_url: Optional[str],
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: Optional[int] = None,
) -> AsyncIterator[Dict[str, Any]]:
    if provider in OAI_COMPAT_OPENAI_STYLE_PROVIDERS:
        b = _normalize_openai_base(provider, base_url)
        async for ev in stream_openai_compatible(b, api_key, model, messages, max_tokens=max_tokens):
            yield ev
        return
    # Anthropic / Google 后续可接各自原生 stream；当前保持兼容，回退成一次性结果。
    result = await chat_dispatch(
        provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )
    if not result.get("ok"):
        yield {"type": "error", "error": result.get("error") or "upstream error"}
        return
    content = str(result.get("content") or "")
    if content:
        yield {"type": "delta", "delta": content}
    if result.get("usage"):
        yield {"type": "usage", "usage": result.get("usage") or {}}


async def image_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    *,
    size: str = "1024x1024",
    n: int = 1,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/images/generations"
    body: Dict[str, Any] = {
        "model": model or "gpt-image-1",
        "prompt": prompt,
        "size": size,
        "n": max(1, min(int(n or 1), 4)),
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        text = r.text
        if r.status_code >= 400:
            return {"ok": False, "status": r.status_code, "error": text[:2000]}
        data = r.json()
    images: List[str] = []
    for item in data.get("data") or []:
        if not isinstance(item, dict):
            continue
        if item.get("url"):
            images.append(str(item["url"]))
        elif item.get("b64_json"):
            images.append(f"data:image/png;base64,{item['b64_json']}")
    return {"ok": True, "images": images, "raw": data}


async def image_dispatch(
    provider: str,
    *,
    api_key: str,
    base_url: Optional[str],
    model: str,
    prompt: str,
    size: str = "1024x1024",
    n: int = 1,
) -> Dict[str, Any]:
    if provider not in OAI_COMPAT_OPENAI_STYLE_PROVIDERS:
        return {"ok": False, "error": f"provider {provider} does not expose OpenAI-compatible images API"}
    b = _normalize_openai_base(provider, base_url)
    return await image_openai_compatible(b, api_key, model or "gpt-image-1", prompt, size=size, n=n)
