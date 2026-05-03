"""从自然语言生成工作流节点/边（LLM），落库后可选沙箱校验。"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from modstore_server.services.employee import get_default_employee_client
from modstore_server.services.llm import chat_dispatch_via_session
from modstore_server.models import User, Workflow, WorkflowEdge, WorkflowNode
from modstore_server.workflow_engine import run_workflow_sandbox

_MAX_NODES = 20
_ALLOWED_TYPES = frozenset(
    {
        "start",
        "end",
        "employee",
        "condition",
        "openapi_operation",
        "knowledge_search",
        "webhook_trigger",
        "cron_trigger",
        "variable_set",
    }
)


def _strip_json_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    raw = _strip_json_fence(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 尝试从文本中抠出第一个 { ... } 块
        i = raw.find("{")
        j = raw.rfind("}")
        if i < 0 or j <= i:
            return None
        try:
            data = json.loads(raw[i : j + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


SYSTEM_PROMPT = """你是 XCAGI 工作流图生成器。用户用自然语言描述业务流程，你输出**仅一个 JSON 对象**（不要 markdown 围栏、不要解释）。

JSON 结构：
{
  "nodes": [
    {
      "temp_id": "字符串，在 nodes 内唯一",
      "node_type": "start" | "end" | "employee" | "condition"
        | "openapi_operation" | "knowledge_search"
        | "webhook_trigger" | "cron_trigger" | "variable_set",
      "name": "节点显示名",
      "config": { },
      "position_x": 0,
      "position_y": 0
    }
  ],
  "edges": [
    {
      "source_temp_id": "…",
      "target_temp_id": "…",
      "condition": "可选，Python 表达式字符串；无条件则空字符串"
    }
  ]
}

规则：
1. 必须有且仅有 **一个** node_type 为 start 的节点，config 为 {}。
2. 必须有且仅有 **一个** node_type 为 end 的节点，config 为 {}。
3. 节点总数不超过 20。
4. employee 节点的 config 必须包含：
   - "employee_id": 字符串，**优先**从下方「可用员工目录」中选 id；若无合适项可填目录中第一条或合理占位并在 name 中说明。
   - "task": 字符串，对员工的具体任务说明（一句即可）。
5. condition 节点可在 config 中包含 "expression": 字符串（展示用）；出边分支仍用 edges[].condition。
6. openapi_operation：config 含 "connector_id"(整数)、"operation_id"(字符串)、"params"(对象，可为空)、可选 "output_var"(默认 api_result)。
7. knowledge_search：config 含 "query"(字符串，可用 {{ var }})、可选 "kb_id"、可选 "top_k"(整数)、可选 "output_var"(默认 kb_chunks)、可选 "collection_ids"(整数数组)。
8. webhook_trigger：config 可选 "secret"、可选 "payload_var"(默认 webhook_payload)。须从 start 经边可达（通常 start -> … -> webhook 或 webhook 接在 start 后）。
9. cron_trigger：config 含 "cron"(cron 表达式字符串)、可选 "timezone"(如 Asia/Shanghai)。
10. variable_set：config 含 "name"(变量名)、"value"(字符串，可用 {{ var }} 模板)。
11. edges 构成从 start 经若干节点到 end 的**有向可达**路径；避免悬空节点。
12. position_x / position_y 为横向/纵向布局坐标，建议每层间隔 220（x）与 120（y）。

只输出 JSON，不要其它文字。"""


def _catalog_lines(max_items: int = 40) -> str:
    try:
        rows = get_default_employee_client().list_employees() or []
    except Exception:
        rows = []
    lines: List[str] = []
    for r in rows[:max_items]:
        if not isinstance(r, dict):
            continue
        eid = str(r.get("id") or "").strip()
        name = str(r.get("name") or "").strip()
        if eid:
            lines.append(f"- id={eid!r} name={name!r}")
    if not lines:
        return "（当前目录无已上架员工包；employee 节点可填占位 employee_id，用户稍后在画布修改。）"
    return "可用员工目录（employee_id 须与下列 id 一致）：\n" + "\n".join(lines)


def _normalize_node(
    raw: Dict[str, Any], warnings: List[str]
) -> Optional[Dict[str, Any]]:
    tid = str(raw.get("temp_id") or "").strip()
    nt = str(raw.get("node_type") or "").strip().lower()
    name = str(raw.get("name") or "").strip() or nt
    if not tid or nt not in _ALLOWED_TYPES:
        warnings.append(f"跳过非法节点: temp_id={tid!r} type={nt!r}")
        return None
    cfg = raw.get("config")
    if not isinstance(cfg, dict):
        cfg = {}
    if nt == "employee":
        eid = str(cfg.get("employee_id") or "").strip()
        task = str(cfg.get("task") or "").strip()
        if not eid:
            warnings.append(f"员工节点 {name!r} 缺少 employee_id，已用占位 placeholder")
            eid = "placeholder"
            cfg = {**cfg, "employee_id": eid}
        if not task:
            task = "根据工作流上下文完成用户描述中的任务"
            cfg = {**cfg, "task": task}
            warnings.append(f"员工节点 {name!r} 已补全默认 task")
    elif nt == "condition":
        expr = str(cfg.get("expression") or "").strip()
        cfg = {"expression": expr} if expr else {}
    elif nt == "openapi_operation":
        try:
            cid = int(cfg.get("connector_id") or 0)
        except (TypeError, ValueError):
            cid = 0
        oid = str(cfg.get("operation_id") or "").strip()
        params = cfg.get("params")
        if not isinstance(params, dict):
            params = {}
        im = cfg.get("input_mapping")
        if isinstance(im, dict) and im:
            params = im
        out_var = str(cfg.get("output_var") or "api_result").strip() or "api_result"
        cfg = {
            "connector_id": cid,
            "operation_id": oid,
            "params": params,
            "input_mapping": params,
            "output_var": out_var,
        }
        if not cid:
            warnings.append(f"OpenAPI 节点 {name!r} 缺少有效 connector_id，已写 0，请在画布中修改")
        if not oid:
            warnings.append(f"OpenAPI 节点 {name!r} 缺少 operation_id，请在画布中补全")
    elif nt == "knowledge_search":
        query = str(cfg.get("query") or cfg.get("query_template") or "").strip()
        kb_id = str(cfg.get("kb_id") or "").strip()
        if not query and kb_id:
            query = f"知识库 {kb_id} 检索"
            warnings.append(f"知识检索节点 {name!r} 已根据 kb_id 生成占位 query")
        if not query:
            query = "根据上下文检索知识库"
            warnings.append(f"知识检索节点 {name!r} 已补全默认 query")
        try:
            top_k = int(cfg.get("top_k") or 5)
        except (TypeError, ValueError):
            top_k = 5
        output_var = str(cfg.get("output_var") or "kb_chunks").strip() or "kb_chunks"
        cids = cfg.get("collection_ids")
        if not isinstance(cids, list):
            cids = []
        cfg = {
            "query": query,
            "top_k": max(1, min(50, top_k)),
            "output_var": output_var,
            "collection_ids": cids,
        }
        if kb_id:
            cfg["kb_id"] = kb_id
    elif nt == "webhook_trigger":
        secret = str(cfg.get("secret") or "").strip()
        payload_var = str(cfg.get("payload_var") or "webhook_payload").strip() or "webhook_payload"
        cfg = {"secret": secret, "payload_var": payload_var}
    elif nt == "cron_trigger":
        cron = str(cfg.get("cron") or "0 * * * *").strip() or "0 * * * *"
        tz = str(cfg.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai"
        cfg = {"cron": cron, "timezone": tz}
    elif nt == "variable_set":
        vname = str(cfg.get("name") or "").strip()
        value = cfg.get("value", "")
        if value is not None and not isinstance(value, (dict, list)):
            value = str(value)
        if not vname:
            warnings.append(f"变量赋值节点 {name!r} 缺少 name，已用占位 _var")
            vname = "_var"
        cfg = {"name": vname, "value": value}
    elif nt in ("start", "end"):
        cfg = {}
    else:
        cfg = {}
    try:
        px = float(raw.get("position_x", 0))
        py = float(raw.get("position_y", 0))
    except (TypeError, ValueError):
        px, py = 0.0, 0.0
    return {
        "temp_id": tid,
        "node_type": nt,
        "name": name[:256],
        "config": cfg,
        "position_x": px,
        "position_y": py,
    }


async def apply_nl_workflow_graph(
    db: Session,
    user: User,
    *,
    workflow_id: int,
    brief: str,
    provider: Optional[str],
    model: Optional[str],
) -> Dict[str, Any]:
    """
    为已存在且属于当前用户的工作流生成节点与边。
    成功: ok=True, nodes_created, edges_created, sandbox_ok, validation_errors, llm_warnings
    失败: ok=False, error=...
    """
    wf = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id, Workflow.user_id == user.id)
        .first()
    )
    if not wf:
        return {"ok": False, "error": "工作流不存在或无权访问"}

    from modstore_server.mod_scaffold_runner import resolve_llm_provider_model

    prov, mdl, err = resolve_llm_provider_model(db, user, provider, model)
    if err:
        return {"ok": False, "error": err}
    user_msg = (
        f"工作流名称: {wf.name}\n\n"
        f"工作流说明与需求:\n{brief.strip()}\n\n"
        f"{_catalog_lines()}\n\n"
        "请生成 nodes 与 edges JSON。"
    )
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    result = await chat_dispatch_via_session(
        db,
        user.id,
        prov,
        mdl,
        msgs,
        max_tokens=4096,
    )
    if not result.get("ok"):
        e = str(result.get("error") or "LLM 调用失败")
        if "missing api key" in e.lower():
            e = "该供应商未配置可用 API Key（平台或 BYOK）"
        return {"ok": False, "error": e}

    data = _extract_json_object(str(result.get("content") or ""))
    if not data:
        return {"ok": False, "error": "模型返回无法解析为 JSON 对象"}

    raw_nodes = data.get("nodes")
    raw_edges = data.get("edges")
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        return {"ok": False, "error": "JSON 须包含 nodes 与 edges 数组"}

    warnings: List[str] = []
    nodes_in: List[Dict[str, Any]] = []
    seen_tid: set[str] = set()
    for i, rn in enumerate(raw_nodes):
        if not isinstance(rn, dict):
            continue
        if len(nodes_in) >= _MAX_NODES:
            warnings.append(f"节点超过 {_MAX_NODES} 个，已截断")
            break
        nn = _normalize_node(rn, warnings)
        if not nn:
            continue
        if nn["temp_id"] in seen_tid:
            warnings.append(f"重复 temp_id {nn['temp_id']!r}，已跳过后续")
            continue
        seen_tid.add(nn["temp_id"])
        nodes_in.append(nn)

    starts = [n for n in nodes_in if n["node_type"] == "start"]
    ends = [n for n in nodes_in if n["node_type"] == "end"]
    if len(starts) != 1 or len(ends) != 1:
        return {
            "ok": False,
            "error": f"图中须有且仅有一个 start 与一个 end（当前 start={len(starts)} end={len(ends)}）",
        }

    temp_to_row: Dict[str, Dict[str, Any]] = {n["temp_id"]: n for n in nodes_in}
    edges_in: List[Dict[str, Any]] = []
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, dict):
            continue
        s = str(raw_edge.get("source_temp_id") or "").strip()
        t = str(raw_edge.get("target_temp_id") or "").strip()
        cond = str(raw_edge.get("condition") or "")
        if not s or not t or s not in temp_to_row or t not in temp_to_row:
            warnings.append(f"跳过无效边: {s!r} -> {t!r}")
            continue
        edges_in.append({"source_temp_id": s, "target_temp_id": t, "condition": cond})

    if not edges_in:
        return {"ok": False, "error": "未生成任何有效边"}

    # 落库：先插节点
    id_map: Dict[str, int] = {}
    try:
        for n in nodes_in:
            row = WorkflowNode(
                workflow_id=workflow_id,
                node_type=n["node_type"],
                name=n["name"],
                config=json.dumps(n["config"], ensure_ascii=False),
                position_x=n["position_x"],
                position_y=n["position_y"],
            )
            db.add(row)
            db.flush()
            id_map[n["temp_id"]] = row.id

        for e in edges_in:
            sid = id_map.get(e["source_temp_id"])
            tid = id_map.get(e["target_temp_id"])
            if not sid or not tid:
                continue
            db.add(
                WorkflowEdge(
                    workflow_id=workflow_id,
                    source_node_id=sid,
                    target_node_id=tid,
                    condition=e["condition"] or "",
                )
            )
        db.commit()
    except Exception as ex:
        db.rollback()
        return {"ok": False, "error": f"写入节点/边失败: {ex}"}

    report = run_workflow_sandbox(
        workflow_id,
        {},
        mock_employees=True,
        validate_only=True,
    )
    errs = [str(x) for x in (report.get("errors") or [])]
    val_ok = bool(report.get("ok"))
    return {
        "ok": True,
        "nodes_created": len(nodes_in),
        "edges_created": len(edges_in),
        "sandbox_ok": val_ok,
        "validation_errors": errs,
        "llm_warnings": warnings,
    }
