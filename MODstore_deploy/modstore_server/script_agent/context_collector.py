"""``context_collector`` —— 把 Brief + 知识库 + SDK 文档拼成生成上下文。

设计要点：

- 不依赖 LLM；纯组装。失败的子步（如知识库不可用）静默降级。
- ``sdk_doc`` 是固定字符串（修改 SDK 时一并更新这里）。
- ``kb_chunks_md`` 仅当 ``brief.references.kb_collection_ids`` 提供时才查。
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from modstore_server.script_agent.brief import Brief, ContextBundle
from modstore_server.script_agent.package_allowlist import allowed_packages


SDK_DOC = """\
from modstore_runtime import ai, kb_search, employee_run, http_get, log, inputs, outputs

# 1) ai(prompt, *, text="", schema=None, model=None, max_tokens=1024) -> str|dict
#    非确定性兜底：从一段文本里"提取/分类/总结"。schema 给 dict 时尝试解析为对象。
#
# 2) kb_search(query, *, top_k=6) -> list[{collection_id, collection_name, score, text, metadata}]
#    跨当前用户可见的知识库做向量检索。
#
# 3) employee_run(employee_id, task="", payload=None) -> dict
#    以当前用户身份调平台员工。
#
# 4) http_get(url, *, params=None, headers=None, timeout=30) -> {status, text, headers}
#    走父进程的受控 HTTP GET（域名白名单）。
#
# 5) log.info(msg, **fields)  log.warning(...)  log.error(...)
#    结构化日志写 stderr，observer 可解析。
#
# 6) inputs / outputs：
#    inputs.path("a.xlsx")            -> Path("inputs/a.xlsx")
#    inputs.list()                    -> ["a.xlsx", "b.csv"]
#    outputs.write_text(name, text)   -> Path
#    outputs.write_bytes(name, data)  -> Path
#    outputs.write_json(name, data)   -> Path
#
# 强制约束：
#   - 只能读 inputs/、写 outputs/；超出走 SDK
#   - 禁止 import subprocess/ctypes/multiprocessing
#   - 禁止 eval/exec/compile/__import__
#   - 第三方包必须在 allowlist 内
"""


def _summarize_inputs(brief: Brief) -> str:
    if not brief.inputs:
        return "(无上传文件)"
    parts = []
    for f in brief.inputs:
        suffix = ""
        if f.description:
            suffix = f" — {f.description}"
        parts.append(f"- {f.filename}{suffix}")
    return "\n".join(parts)


async def _collect_kb_chunks(
    *,
    user_id: int,
    queries: Sequence[str],
    collection_ids: Optional[Sequence[int]] = None,
    top_k_per_query: int = 3,
) -> str:
    """对每条 query 检索知识库，拼成 markdown 列表。失败返回空串。"""
    try:
        from modstore_server.rag_service import retrieve
    except Exception:  # noqa: BLE001
        return ""
    rows: List[str] = []
    for q in queries:
        if not q.strip():
            continue
        try:
            chunks = await retrieve(
                user_id=user_id,
                query=q,
                top_k=top_k_per_query,
                extra_collection_ids=collection_ids,
            )
        except Exception:  # noqa: BLE001
            continue
        for c in chunks:
            text = str(getattr(c, "text", "") or "").strip()
            if not text:
                continue
            name = str(getattr(c, "collection_name", "") or "")
            rows.append(f"- ({name}) {text[:600]}")
    return "\n".join(rows)


async def collect_context(
    brief: Brief,
    *,
    user_id: int,
    extra_kb_queries: Iterable[str] = (),
) -> ContextBundle:
    """同步拼装 + 异步检索知识库，返回喂给 planner / code_writer 的 bundle。"""
    kb_md = ""
    refs = brief.references or {}
    coll_ids = refs.get("kb_collection_ids") or refs.get("kb_collections")
    if coll_ids:
        try:
            ids: List[int] = []
            for x in coll_ids:
                try:
                    ids.append(int(x))
                except Exception:  # noqa: BLE001
                    continue
            queries = list(extra_kb_queries) or [brief.goal[:200]]
            kb_md = await _collect_kb_chunks(
                user_id=user_id,
                queries=queries,
                collection_ids=ids,
            )
        except Exception:  # noqa: BLE001
            kb_md = ""

    return ContextBundle(
        brief_md=brief.as_markdown(),
        inputs_summary=_summarize_inputs(brief),
        kb_chunks_md=kb_md,
        sdk_doc=SDK_DOC,
        allowlist_packages=sorted(allowed_packages()),
    )
