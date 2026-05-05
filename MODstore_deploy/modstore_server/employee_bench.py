"""员工上架前的基准测试：LLM 生成 1-5 级任务 → 执行 → 量化打分 → 五维审核。

公开接口
--------
generate_bench_tasks(brief, panel_summary, db, user_id, provider, model)
    -> List[{level, tasks:[{id, task_desc}]}]

run_and_score_bench(employee_id, task_list, db, user, provider, model)
    -> {tasks_result, level_scores, overall_score, audit, passed}
"""

from __future__ import annotations

import json
import logging
import re
import time
import zipfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from modstore_server.models import User

logger = logging.getLogger(__name__)

# ── 权重：越低难度级别权重越高 ──────────────────────────────────────────
_LEVEL_WEIGHTS = {1: 3.0, 2: 2.5, 3: 2.0, 4: 1.5, 5: 1.0}

# ── 效率因子基准（tokens，超过则 efficiency < 1）─────────────────────────
_EFFICIENT_TOKEN_THRESHOLD = 500

# ── 通过标准 ─────────────────────────────────────────────────────────────
_PASS_OVERALL_SCORE = 60.0
_PASS_AUDIT_SCORE = True  # audit.summary.pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 生成测试任务
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_TASK_GEN_SYSTEM = """\
你是一位严格的 AI 员工考官。根据员工功能描述，为该员工设计一套分级测试任务（共 5 级，每级 3 个任务）。

任务难度递增：
- 1 级：极简验证，单步操作，无歧义输入
- 2 级：基础功能，正常业务场景
- 3 级：中等复杂度，含边界条件
- 4 级：多步骤、需要判断的场景
- 5 级：压力/异常/综合场景

输出**仅**一个合法 JSON 数组（无注释、无 markdown 围栏）：
[
  {
    "level": 1,
    "tasks": [
      {"id": "1-1", "task_desc": "具体任务指令，30字以内"},
      {"id": "1-2", "task_desc": "..."},
      {"id": "1-3", "task_desc": "..."}
    ]
  },
  ... (level 2 to 5)
]
"""


def _strip_fence(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I | re.S)
        s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def _parse_task_list(content: str) -> List[Dict[str, Any]]:
    raw = _strip_fence(content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        i, j = raw.find("["), raw.rfind("]")
        if i < 0 or j <= i:
            return []
        try:
            data = json.loads(raw[i : j + 1])
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        lv = int(item.get("level") or 0)
        if lv < 1 or lv > 5:
            continue
        tasks = [
            {"id": str(t.get("id") or f"{lv}-{i+1}"), "task_desc": str(t.get("task_desc") or "").strip()[:120]}
            for i, t in enumerate((item.get("tasks") or [])[:3])
            if isinstance(t, dict) and str(t.get("task_desc") or "").strip()
        ]
        if tasks:
            out.append({"level": lv, "tasks": tasks})
    return out


def _fallback_tasks(brief: str) -> List[Dict[str, Any]]:
    """LLM 失败时生成最小占位任务集。"""
    short = (brief or "执行默认任务")[:40]
    return [
        {
            "level": lv,
            "tasks": [
                {"id": f"{lv}-{t}", "task_desc": f"[Lv{lv}] {short}（测试 {t}）"}
                for t in range(1, 4)
            ],
        }
        for lv in range(1, 6)
    ]


async def generate_bench_tasks(
    brief: str,
    panel_summary: str,
    *,
    db: Session,
    user_id: int,
    provider: Optional[str],
    model: Optional[str],
) -> List[Dict[str, Any]]:
    """调 LLM 一次生成 1-5 级共 15 条测试任务。

    失败时退化为占位任务列表（保证后续流程不中断）。
    """
    from modstore_server.services.llm import chat_dispatch_via_session

    if not provider or not model:
        logger.warning("generate_bench_tasks: 无 provider/model，使用占位任务")
        return _fallback_tasks(brief)

    user_msg = (
        f"员工功能描述（brief）：\n{(brief or '').strip()}\n\n"
        f"功能摘要（panel_summary）：\n{(panel_summary or '（无）').strip()}"
    )
    try:
        result = await chat_dispatch_via_session(
            db,
            user_id,
            provider,
            model,
            [
                {"role": "system", "content": _TASK_GEN_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=2000,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("generate_bench_tasks LLM call failed: %s", exc)
        return _fallback_tasks(brief)

    if not result.get("ok"):
        logger.warning("generate_bench_tasks LLM error: %s", result.get("error"))
        return _fallback_tasks(brief)

    tasks = _parse_task_list(str(result.get("content") or ""))
    if not tasks:
        logger.warning("generate_bench_tasks: 解析失败，使用占位任务")
        return _fallback_tasks(brief)

    # 补齐缺失的 level
    seen = {t["level"] for t in tasks}
    for lv in range(1, 6):
        if lv not in seen:
            tasks.append({"level": lv, "tasks": [{"id": f"{lv}-1", "task_desc": f"[Lv{lv}] {brief[:40]}（补位）"}]})
    tasks.sort(key=lambda x: x["level"])
    return tasks


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 执行 + 量化打分
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _efficiency_factor(cost_tokens: int) -> float:
    """token 消耗越少效率因子越高（最大 1.0）。"""
    if cost_tokens <= 0:
        return 1.0
    factor = _EFFICIENT_TOKEN_THRESHOLD / max(cost_tokens, _EFFICIENT_TOKEN_THRESHOLD)
    return min(1.0, factor)


def _run_single_task(
    employee_id: str,
    task_desc: str,
    user_id: int,
) -> Dict[str, Any]:
    """同步执行单条任务，记录 ok / cost_tokens / duration_ms。"""
    from modstore_server.services.employee import get_default_employee_client

    client = get_default_employee_client()
    t0 = time.perf_counter()
    try:
        res = client.execute_task(
            employee_id=employee_id,
            task=task_desc,
            input_data={},
            user_id=user_id,
        )
        ok = bool(res.get("ok", True)) if isinstance(res, dict) else bool(res)
        cost_tokens = int(res.get("cost_tokens") or res.get("tokens_used") or 0) if isinstance(res, dict) else 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("bench task failed employee=%s task=%r: %s", employee_id, task_desc[:40], exc)
        ok = False
        cost_tokens = 0
        res = {"error": str(exc)}
    duration_ms = (time.perf_counter() - t0) * 1000
    return {
        "ok": ok,
        "cost_tokens": cost_tokens,
        "duration_ms": round(duration_ms, 1),
        "raw": res if isinstance(res, dict) else {},
    }


def _score_level(level_results: List[Dict[str, Any]]) -> float:
    """对某一级的多条任务结果计算平均得分（0-100）。"""
    if not level_results:
        return 0.0
    scores = [
        100.0 * (1.0 if r["ok"] else 0.0) * _efficiency_factor(r["cost_tokens"])
        for r in level_results
    ]
    return sum(scores) / len(scores)


def _weighted_overall(level_scores: Dict[int, float]) -> float:
    total_w = sum(_LEVEL_WEIGHTS[lv] for lv in range(1, 6))
    weighted = sum(_LEVEL_WEIGHTS.get(lv, 1.0) * level_scores.get(lv, 0.0) for lv in range(1, 6))
    return weighted / total_w if total_w else 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 五维审核
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def _run_five_dim_audit(employee_id: str) -> Dict[str, Any]:
    """从 library 目录重建员工包 zip，再调五维审核。"""
    from modstore_server.mod_scaffold_runner import modstore_library_path
    from modstore_server.package_sandbox_audit import run_package_audit_async
    from modstore_server.employee_ai_scaffold import build_employee_pack_zip

    pack_dir = modstore_library_path() / employee_id
    mf_path = pack_dir / "manifest.json"
    if not mf_path.is_file():
        return {
            "ok": False,
            "error": f"员工包目录不存在: {employee_id}",
            "dimensions": {},
            "summary": {"average": 0, "pass": False},
        }
    try:
        manifest = json.loads(mf_path.read_text(encoding="utf-8"))
        zip_bytes = build_employee_pack_zip(employee_id, manifest)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"构建员工包失败: {exc}",
            "dimensions": {},
            "summary": {"average": 0, "pass": False},
        }

    try:
        audit = await run_package_audit_async(zip_bytes, {"artifact": "employee_pack"})
    except Exception as exc:  # noqa: BLE001
        logger.warning("five-dim audit failed: %s", exc)
        audit = {
            "ok": False,
            "error": str(exc),
            "dimensions": {},
            "summary": {"average": 0, "pass": False},
        }
    return audit


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 公开入口
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def run_and_score_bench(
    employee_id: str,
    task_list: List[Dict[str, Any]],
    *,
    db: Session,
    user: User,
) -> Dict[str, Any]:
    """执行全部测试任务、量化打分、五维审核，返回综合报告。

    返回结构：
    {
        tasks_result: [{level, task_id, task_desc, ok, cost_tokens, duration_ms, score}],
        level_scores: {1: float, ..., 5: float},
        overall_score: float,
        audit: {...},          # run_package_audit_async 完整返回
        passed: bool,
    }
    """
    import asyncio

    tasks_result: List[Dict[str, Any]] = []
    level_results: Dict[int, List[Dict[str, Any]]] = {lv: [] for lv in range(1, 6)}

    for level_group in task_list:
        lv = int(level_group.get("level") or 0)
        if lv < 1 or lv > 5:
            continue
        for task in level_group.get("tasks") or []:
            task_id = str(task.get("id") or f"{lv}-?")
            task_desc = str(task.get("task_desc") or "").strip()
            if not task_desc:
                continue
            # 在线程中运行同步员工调用，不阻塞事件循环
            run_result = await asyncio.to_thread(
                _run_single_task, employee_id, task_desc, user.id
            )
            eff = _efficiency_factor(run_result["cost_tokens"])
            task_score = 100.0 * (1.0 if run_result["ok"] else 0.0) * eff
            entry = {
                "level": lv,
                "task_id": task_id,
                "task_desc": task_desc,
                "ok": run_result["ok"],
                "cost_tokens": run_result["cost_tokens"],
                "duration_ms": run_result["duration_ms"],
                "score": round(task_score, 1),
            }
            tasks_result.append(entry)
            level_results[lv].append(run_result)

    level_scores: Dict[int, float] = {
        lv: round(_score_level(results), 1)
        for lv, results in level_results.items()
    }
    overall_score = round(_weighted_overall(level_scores), 1)

    # 五维审核
    audit = await _run_five_dim_audit(employee_id)
    audit_passed = bool(audit.get("summary", {}).get("pass", False))

    passed = overall_score >= _PASS_OVERALL_SCORE and audit_passed

    return {
        "tasks_result": tasks_result,
        "level_scores": level_scores,
        "overall_score": overall_score,
        "audit": audit,
        "passed": passed,
    }
