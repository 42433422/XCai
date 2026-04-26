"""向量数据库：用于 MOD/员工包的语义检索与智能推荐。"""

from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

_lock = threading.Lock()


def _vector_db_dir() -> Path:
    raw = (os.environ.get("MODSTORE_VECTOR_DB_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent / "vector_data"


_client = None


def _build_embedding_text(text: str) -> str:
    """将文本转为用于嵌入的纯文本格式。"""
    return (text or "").strip().replace("\n", " ").replace("\r", " ")


def get_vector_client():
    """懒加载向量数据库客户端（chromadb 持久化模式）。"""
    global _client
    if _client is not None:
        return _client

    import chromadb

    db_dir = _vector_db_dir()
    db_dir.mkdir(parents=True, exist_ok=True)

    settings = chromadb.Settings(
        anonymized_telemetry=False,
        is_persistent=True,
        persist_directory=str(db_dir),
    )
    _client = chromadb.Client(settings)
    return _client


def _collection():
    """获取或创建 catalog 向量集合。"""
    client = get_vector_client()
    try:
        col = client.get_collection(name="catalog_embeddings")
    except Exception:
        col = client.create_collection(
            name="catalog_embeddings",
            metadata={"hnsw:space": "cosine"},
        )
    return col


def insert_embedding(
    item_id: str,
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """插入或更新单条嵌入向量。

    Args:
        item_id: 商品唯一标识（如 pkg_id:version）
        text: 用于生成向量的文本（名称+描述）
        metadata: 附加元数据

    Returns:
        插入的 ID
    """
    embedding_text = _build_embedding_text(text)
    if not embedding_text:
        return ""

    doc_id = str(item_id).strip()
    hashed_id = hashlib.sha256(doc_id.encode()).hexdigest()[:16]

    with _lock:
        col = _collection()
        col.upsert(
            ids=[hashed_id],
            documents=[embedding_text],
            metadatas=[metadata or {}],
        )
    return hashed_id


def query_similar(
    text: str,
    limit: int = 10,
    filter_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """语义相似度查询。

    Args:
        text: 查询文本
        limit: 返回数量上限
        filter_meta: 可选的元数据过滤条件

    Returns:
        匹配结果列表，每项包含 id, document, metadata, distance
    """
    query_text = _build_embedding_text(text)
    if not query_text:
        return []

    where_filter = None
    if filter_meta:
        where_filter = {
            "$and": [
                {k: {"$eq": v}}
                for k, v in filter_meta.items()
                if v is not None
            ]
        }

    with _lock:
        col = _collection()
        results = col.query(
            query_texts=[query_text],
            n_results=min(limit, 100),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

    items = []
    if results and results.get("ids"):
        ids = results["ids"][0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [{}])[0]
        dists = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            items.append({
                "id": ids[i],
                "document": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
                "distance": dists[i] if i < len(dists) else 1.0,
            })

    return items


def delete_embedding(item_id: str) -> bool:
    """删除指定嵌入向量。"""
    doc_id = str(item_id).strip()
    hashed_id = hashlib.sha256(doc_id.encode()).hexdigest()[:16]

    with _lock:
        col = _collection()
        col.delete(ids=[hashed_id])
    return True


def count_embeddings() -> int:
    """返回集合中的向量总数。"""
    with _lock:
        col = _collection()
        return col.count()
