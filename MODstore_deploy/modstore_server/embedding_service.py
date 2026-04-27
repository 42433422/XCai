"""OpenAI-compatible embedding client for knowledge-base vectors."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import httpx


class EmbeddingConfigError(RuntimeError):
    pass


def embedding_config_snapshot() -> Dict[str, Any]:
    api_key = (os.environ.get("MODSTORE_EMBEDDING_API_KEY") or "").strip()
    base_url = (os.environ.get("MODSTORE_EMBEDDING_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "").strip()
    model = (os.environ.get("MODSTORE_EMBEDDING_MODEL") or "text-embedding-3-small").strip()
    dim = int((os.environ.get("MODSTORE_EMBEDDING_DIM") or "1536").strip() or "1536")
    return {
        "configured": bool(api_key),
        "base_url": base_url or "https://api.openai.com/v1",
        "model": model,
        "dim": dim,
    }


def _embeddings_url(base_url: str) -> str:
    b = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
    return b if b.endswith("/embeddings") else f"{b}/embeddings"


async def embed_texts(texts: List[str]) -> List[List[float]]:
    cfg = embedding_config_snapshot()
    api_key = (os.environ.get("MODSTORE_EMBEDDING_API_KEY") or "").strip()
    if not api_key:
        raise EmbeddingConfigError("未配置 MODSTORE_EMBEDDING_API_KEY，无法构建向量库")

    clean = [(t or "").strip() for t in texts]
    if not clean:
        return []
    body = {"model": cfg["model"], "input": clean}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(_embeddings_url(str(cfg["base_url"])), json=body, headers=headers)
        res.raise_for_status()
        data = res.json()

    rows = data.get("data")
    if not isinstance(rows, list):
        raise EmbeddingConfigError("Embedding API 响应缺少 data")
    rows = sorted(rows, key=lambda x: int(x.get("index", 0)) if isinstance(x, dict) else 0)
    vectors: List[List[float]] = []
    for item in rows:
        emb = item.get("embedding") if isinstance(item, dict) else None
        if not isinstance(emb, list):
            raise EmbeddingConfigError("Embedding API 响应缺少 embedding")
        if len(emb) != int(cfg["dim"]):
            raise EmbeddingConfigError(f"Embedding 维度 {len(emb)} 与配置 {cfg['dim']} 不一致")
        vectors.append([float(x) for x in emb])
    return vectors
