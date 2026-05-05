"""6 阶段 AI 员工流水线：NL → 完整 employee_pack manifest。

每个阶段独立 LLM 调用 + 严格 JSON 校验；通过 on_event 回调推送 SSE 事件，
供 /api/workbench/employee-ai/draft 端点实时流式输出。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from modstore_server.employee_ai_scaffold import _strip_json_fence
from modstore_server.script_agent.llm_client import LlmClient

# ── system prompts ────────────────────────────────────────────────────────────

_SYS_PARSE_INTENT = """你是 AI 员工意图解析器。用户用自然语言描述想要的 AI 员工。
你只输出一个 JSON 对象（不含 markdown 围栏），字段：
- id: 字符串，小写英文/数字/连字符，2-32 字符
- name: 简短中文显示名（不超过 12 字）
- role: 角色核心职能（不超过 20 字）
- scenario: 使用场景（不超过 80 字）
- industry: 行业分类（如"电商""金融""教育""通用"等）
- complexity: "low"/"medium"/"high"

示例：{"id":"refund-assistant","name":"退款客服助手","role":"退款流程处理","scenario":"用户提交退款申请后自动核查订单并输出处理意见","industry":"电商","complexity":"medium"}"""

_SYS_RANK_WORKFLOW = """你是 AI 工作流选型助手。给你员工意图描述和候选工作流列表，只输出一个 JSON 对象：
- best_index: 最匹配工作流的 index（从 0 开始），若均不匹配输出 -1
- score: 匹配度 0.0-1.0
- reason: 一句话理由（不超过 40 字）

当 score < 0.5 时，best_index 必须为 -1。"""

_SYS_DESIGN_V2 = """你是 XCAGI employee_config_v2 设计师。根据员工意图，只输出一个 JSON 对象，字段：
- perception: 对象，含 type（"text"|"document"|"event"|"web_rankings"|"multimodal"）
- memory: 对象，含 type（"session"|"long_term"|"none"）；需长期记忆时加 knowledge_base 字符串
- cognition: 对象，含 agent.system_prompt（至少 120 字专业 prompt）及 agent.model（provider/model_name）
- actions: 对象，含 handlers 数组（合法值：echo/text_output/notify/webhook/vibe_edit/vibe_heal/vibe_code）

system_prompt 要求：明确身份、能力范围、工作步骤、输出格式、禁忌事项，不少于 120 字，面向 AI 执行。
model 建议：provider 默认 "deepseek"，model_name 默认 "deepseek-chat"，temperature 0.2。"""

_SYS_SUGGEST_SKILLS = """你是 AI 技能推荐助手。根据员工角色和场景推荐合适的技能，只输出 JSON 数组（不含对象包裹），每项含：
- name: 技能名（不超过 16 字）
- brief: 技能简介（不超过 50 字）

推荐 2-5 个，按重要性排序。
示例：[{"name":"订单查询","brief":"根据订单号查询订单状态与详情"}]"""

_SYS_SUGGEST_PRICING = """你是 AI 定价顾问。根据员工复杂度、功能丰富度、行业特性建议定价，只输出一个 JSON 对象：
- tier: "free"/"basic"/"standard"/"pro"/"enterprise"
- cny: 月费（人民币），免费则 0
- period: "month"（月付）/ "year"（年付）/ "once"（买断）
- reasoning: 不超过 60 字的定价理由

定价参考区间：free=0，basic≤9，standard≤29，pro≤99，enterprise≥99"""

_SYS_REFINE_PROMPT = """你是专业 system prompt 优化助手。用户提供当前 system prompt 和优化指令，你须：
1. 输出优化后的 system prompt（与原文同语言，去掉废话/模糊表述，增强具体性和专业度）
2. 用一句话解释主要改动

只输出一个 JSON 对象：
- improved_prompt: 完整的优化后 system prompt（字符串）
- diff_explanation: 改动说明（不超过 80 字）"""


# ── dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class Intent:
    id: str
    name: str
    role: str
    scenario: str
    industry: str
    complexity: str  # "low" | "medium" | "high"


@dataclass
class WorkflowChoice:
    workflow_id: Optional[int]
    workflow_name: str
    match_score: float
    generated: bool
    sandbox_passed: bool = False


@dataclass
class EmployeeConfigV2:
    perception: Dict[str, Any]
    memory: Dict[str, Any]
    cognition: Dict[str, Any]
    actions: Dict[str, Any]


@dataclass
class SuggestedSkill:
    name: str
    brief: str
    unverified: bool = True


@dataclass
class PricingHint:
    tier: str
    cny: float
    period: str
    reasoning: str


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _parse_json(text: str) -> Tuple[Optional[Any], str]:
    raw = _strip_json_fence(text)
    try:
        return json.loads(raw), ""
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败: {e}"


# ── stage 1: parse intent ─────────────────────────────────────────────────────

async def stage_parse_intent(brief: str, llm: LlmClient) -> Tuple[Optional[Intent], str]:
    content = await llm.chat(
        [{"role": "system", "content": _SYS_PARSE_INTENT}, {"role": "user", "content": brief}],
        max_tokens=512,
    )
    data, err = _parse_json(content)
    if err:
        return None, err
    if not isinstance(data, dict):
        return None, "LLM 须返回 JSON 对象"
    raw_id = re.sub(r"[^a-z0-9\-_]", "-", str(data.get("id") or "").lower().strip()).strip("-")
    safe_id = raw_id[:32] or "my-employee"
    return Intent(
        id=safe_id,
        name=str(data.get("name") or safe_id)[:24],
        role=str(data.get("role") or "")[:40],
        scenario=str(data.get("scenario") or "")[:120],
        industry=str(data.get("industry") or "通用")[:20],
        complexity=str(data.get("complexity") or "medium").lower(),
    ), ""


# ── stage 2: resolve workflow ─────────────────────────────────────────────────

async def stage_resolve_workflow(
    intent: Intent,
    eligible_workflows: List[Dict[str, Any]],
    llm: LlmClient,
    *,
    generate_fallback: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None,
    score_threshold: float = 0.55,
    on_progress: Optional[Callable[[str], Awaitable[None]]] = None,
) -> Tuple[Optional[WorkflowChoice], str]:
    """LLM-rank eligible workflows; fall back to generation if score is below threshold."""
    if not eligible_workflows:
        if generate_fallback is None:
            return WorkflowChoice(workflow_id=None, workflow_name="", match_score=0.0, generated=False), ""
        if on_progress:
            await on_progress("未找到已通过沙箱的工作流，正在为您生成新工作流…")
        res = await generate_fallback()
        if not res.get("ok"):
            return None, f"工作流兜底生成失败: {res.get('error') or '未知错误'}"
        return WorkflowChoice(
            workflow_id=int(res["workflow_id"]),
            workflow_name=str(res.get("name") or ""),
            match_score=0.0,
            generated=True,
        ), ""

    cands = [
        {
            "index": i,
            "name": w.get("name", ""),
            "description": str(w.get("description", ""))[:120],
        }
        for i, w in enumerate(eligible_workflows)
    ]
    msg = (
        f"员工意图：{intent.role}（{intent.scenario}）\n"
        f"候选工作流：{json.dumps(cands, ensure_ascii=False)}"
    )
    content = await llm.chat(
        [{"role": "system", "content": _SYS_RANK_WORKFLOW}, {"role": "user", "content": msg}],
        max_tokens=256,
    )
    data, err = _parse_json(content)
    if err:
        return None, err

    best_idx = int(data.get("best_index", -1))
    score = float(data.get("score", 0.0))

    if 0 <= best_idx < len(eligible_workflows) and score >= score_threshold:
        wf = eligible_workflows[best_idx]
        return WorkflowChoice(
            workflow_id=int(wf["id"]),
            workflow_name=str(wf.get("name", "")),
            match_score=score,
            generated=False,
            sandbox_passed=bool(wf.get("sandbox_passed", False)),
        ), ""

    # Score below threshold → try to generate
    if generate_fallback is None:
        return WorkflowChoice(workflow_id=None, workflow_name="", match_score=score, generated=False), ""
    if on_progress:
        await on_progress(f"现有工作流匹配度（{score:.0%}）不足，正在生成专属工作流…")
    res = await generate_fallback()
    if not res.get("ok"):
        return None, f"工作流兜底生成失败: {res.get('error') or '未知错误'}"
    return WorkflowChoice(
        workflow_id=int(res["workflow_id"]),
        workflow_name=str(res.get("name") or ""),
        match_score=0.0,
        generated=True,
    ), ""


# ── stage 3: design employee_config_v2 ───────────────────────────────────────

async def stage_design_v2(
    intent: Intent,
    workflow_choice: Optional[WorkflowChoice],
    llm: LlmClient,
) -> Tuple[Optional[EmployeeConfigV2], str]:
    ctx_parts = [
        f"角色：{intent.role}",
        f"场景：{intent.scenario}",
        f"行业：{intent.industry}",
        f"复杂度：{intent.complexity}",
    ]
    if workflow_choice and workflow_choice.workflow_id:
        ctx_parts.append(f"已绑定工作流：{workflow_choice.workflow_name}")
    content = await llm.chat(
        [{"role": "system", "content": _SYS_DESIGN_V2}, {"role": "user", "content": "\n".join(ctx_parts)}],
        max_tokens=2048,
    )
    data, err = _parse_json(content)
    if err:
        return None, err
    if not isinstance(data, dict):
        return None, "LLM 须返回 JSON 对象"

    default_prompt = (
        f"你是{intent.name}，负责{intent.role}。"
        f"场景：{intent.scenario}。请根据用户输入完成任务并输出结构化结果。"
    )
    cog_raw = data.get("cognition") or {}
    if not isinstance(cog_raw, dict):
        cog_raw = {}
    agent_raw = cog_raw.get("agent") or {}
    if not isinstance(agent_raw, dict):
        agent_raw = {}
    if not agent_raw.get("system_prompt"):
        agent_raw["system_prompt"] = default_prompt
    if not agent_raw.get("model"):
        agent_raw["model"] = {"provider": "deepseek", "model_name": "deepseek-chat", "temperature": 0.2, "max_tokens": 4000}
    cog_raw["agent"] = agent_raw

    return EmployeeConfigV2(
        perception=data.get("perception") or {"type": "text"},
        memory=data.get("memory") or {"type": "session"},
        cognition=cog_raw,
        actions=data.get("actions") or {"handlers": ["echo"]},
    ), ""


# ── stage 4: suggest skills ───────────────────────────────────────────────────

async def stage_suggest_skills(
    intent: Intent, llm: LlmClient
) -> Tuple[List[SuggestedSkill], str]:
    ctx = f"角色：{intent.role}\n场景：{intent.scenario}\n行业：{intent.industry}"
    content = await llm.chat(
        [{"role": "system", "content": _SYS_SUGGEST_SKILLS}, {"role": "user", "content": ctx}],
        max_tokens=512,
    )
    data, err = _parse_json(content)
    if err:
        return [], err
    if not isinstance(data, list):
        return [], "须返回 JSON 数组"
    skills: List[SuggestedSkill] = []
    for item in data[:8]:
        if isinstance(item, dict) and item.get("name"):
            skills.append(
                SuggestedSkill(
                    name=str(item["name"])[:32],
                    brief=str(item.get("brief") or "")[:80],
                )
            )
    return skills, ""


# ── stage 5: suggest pricing ──────────────────────────────────────────────────

async def stage_suggest_pricing(
    intent: Intent,
    v2: EmployeeConfigV2,
    skills: List[SuggestedSkill],
    llm: LlmClient,
) -> Tuple[Optional[PricingHint], str]:
    handlers = list(v2.actions.get("handlers") or [])
    ctx = (
        f"角色：{intent.role}\n行业：{intent.industry}\n复杂度：{intent.complexity}\n"
        f"技能数：{len(skills)}\n已启用功能：{', '.join(handlers)}"
    )
    content = await llm.chat(
        [{"role": "system", "content": _SYS_SUGGEST_PRICING}, {"role": "user", "content": ctx}],
        max_tokens=256,
    )
    data, err = _parse_json(content)
    if err:
        return None, err
    if not isinstance(data, dict):
        return None, "须返回 JSON 对象"
    return PricingHint(
        tier=str(data.get("tier") or "free"),
        cny=float(data.get("cny") or 0),
        period=str(data.get("period") or "month"),
        reasoning=str(data.get("reasoning") or "")[:120],
    ), ""


# ── stage 6: assemble manifest ────────────────────────────────────────────────

def stage_assemble(
    intent: Intent,
    workflow_choice: Optional[WorkflowChoice],
    v2: EmployeeConfigV2,
    skills: List[SuggestedSkill],
    pricing: Optional[PricingHint],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    from modman.manifest_util import validate_manifest_dict
    from modstore_server.xcagi_host_profile import (
        merge_workflow_employee_for_manifest,
        normalize_xcagi_host_profile,
    )

    eid = re.sub(r"[^a-z0-9_]", "_", intent.id).strip("_") or "employee"
    hp_norm, _ = normalize_xcagi_host_profile({"panel_kind": "mod_http"})
    wf_row = merge_workflow_employee_for_manifest(
        employee_id=eid,
        label=intent.name,
        panel_summary=intent.scenario,
        host_profile=hp_norm,
    )
    if workflow_choice and workflow_choice.workflow_id:
        wf_row["workflow_id"] = workflow_choice.workflow_id

    metadata: Dict[str, Any] = {
        "framework_version": "2.0.0",
        "created_by": "employee_ai_pipeline",
    }
    if skills:
        metadata["suggested_skills"] = [asdict(s) for s in skills]
    if pricing:
        metadata["suggested_pricing"] = asdict(pricing)
    # Flag if the chosen workflow hasn't passed sandbox testing yet.
    # The frontend shows a warning so the user can run sandbox before publishing.
    if workflow_choice and workflow_choice.workflow_id and not workflow_choice.sandbox_passed:
        metadata["workflow_needs_sandbox"] = True

    v2_dict = asdict(v2)
    v2_dict.setdefault("identity", {
        "id": intent.id,
        "version": "1.0.0",
        "artifact": "employee_pack",
        "name": intent.name,
        "description": intent.scenario,
    })
    v2_dict["metadata"] = metadata

    manifest: Dict[str, Any] = {
        "id": intent.id,
        "name": intent.name,
        "version": "1.0.0",
        "author": "",
        "description": intent.scenario,
        "artifact": "employee_pack",
        "scope": "global",
        "industry": intent.industry,
        "dependencies": {"xcagi": ">=1.0.0"},
        "employee": {
            "id": eid,
            "label": intent.name,
            "capabilities": [],
        },
        "employee_config_v2": v2_dict,
        "xcagi_host_profile": hp_norm or {"panel_kind": "mod_http"},
        "workflow_employees": [wf_row],
        "backend": {"entry": "blueprints", "init": "mod_init"},
    }

    # Write pricing into the top-level commerce block so catalog upload forms
    # can read it directly via manifest.commerce.price without extra fallback logic.
    if pricing and (pricing.cny > 0 or pricing.tier != "free"):
        manifest["commerce"] = {
            "price": pricing.cny,
            "currency": "CNY",
            "tier": pricing.tier,
            "period": pricing.period,
        }

    errs = validate_manifest_dict(manifest)
    return manifest, errs


# ── refine prompt helper ──────────────────────────────────────────────────────

async def refine_system_prompt(
    current_prompt: str,
    instruction: str,
    role_context: str,
    llm: LlmClient,
) -> Tuple[Optional[Dict[str, str]], str]:
    """LLM-improve a system prompt and explain the changes."""
    ctx = (
        f"角色背景：{role_context}\n\n"
        f"当前 system prompt：\n{current_prompt}\n\n"
        f"优化指令：{instruction}"
    )
    content = await llm.chat(
        [{"role": "system", "content": _SYS_REFINE_PROMPT}, {"role": "user", "content": ctx}],
        max_tokens=2048,
    )
    data, err = _parse_json(content)
    if err:
        return None, err
    if not isinstance(data, dict):
        return None, "须返回 JSON 对象"
    improved = str(data.get("improved_prompt") or "").strip()
    if not improved:
        return None, "LLM 未返回优化后的 prompt"
    return {
        "improved_prompt": improved,
        "diff_explanation": str(data.get("diff_explanation") or "")[:160],
    }, ""


# ── orchestrator ──────────────────────────────────────────────────────────────

async def run_pipeline(
    brief: str,
    *,
    llm: LlmClient,
    on_event: Callable[[Dict[str, Any]], Awaitable[None]],
    eligible_workflows: Optional[List[Dict[str, Any]]] = None,
    generate_workflow_fallback: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None,
) -> Optional[Dict[str, Any]]:
    """Run the 6-stage pipeline pushing SSE events via on_event.

    Returns the assembled manifest dict on success, None on fatal failure.
    Stages 4 (skills) and 5 (pricing) are non-fatal: errors produce empty/null
    results but do not abort the pipeline.
    """

    async def _emit(event: str, stage: str, **kw: Any) -> None:
        await on_event({"event": event, "stage": stage, **kw})

    # ── S1 parse intent ───────────────────────────────────────────────────────
    await _emit("stage_start", "parse_intent")
    intent, err = await stage_parse_intent(brief, llm)
    if err or intent is None:
        await _emit("stage_error", "parse_intent", error=err or "意图解析失败", retryable=True)
        return None
    await _emit("stage_done", "parse_intent", data=asdict(intent))

    # ── S2 resolve workflow ───────────────────────────────────────────────────
    await _emit("stage_start", "resolve_workflow")

    async def _on_wf_progress(msg: str) -> None:
        await _emit("stage_progress", "resolve_workflow", message=msg)

    wf_choice, err = await stage_resolve_workflow(
        intent,
        eligible_workflows or [],
        llm,
        generate_fallback=generate_workflow_fallback,
        on_progress=_on_wf_progress,
    )
    if err:
        await _emit("stage_error", "resolve_workflow", error=err, retryable=True)
        return None
    await _emit("stage_done", "resolve_workflow", data=asdict(wf_choice) if wf_choice else None)

    # ── S3 design config v2 ───────────────────────────────────────────────────
    await _emit("stage_start", "design_v2")
    v2, err = await stage_design_v2(intent, wf_choice, llm)
    if err or v2 is None:
        await _emit("stage_error", "design_v2", error=err or "配置设计失败", retryable=True)
        return None
    await _emit("stage_done", "design_v2", data=asdict(v2))

    # ── S4 suggest skills (non-fatal) ─────────────────────────────────────────
    await _emit("stage_start", "suggest_skills")
    skills, err = await stage_suggest_skills(intent, llm)
    if err:
        await _emit("stage_error", "suggest_skills", error=err, retryable=False)
        skills = []
    await _emit("stage_done", "suggest_skills", data=[asdict(s) for s in skills])

    # ── S5 suggest pricing (non-fatal) ────────────────────────────────────────
    await _emit("stage_start", "suggest_pricing")
    pricing, err = await stage_suggest_pricing(intent, v2, skills, llm)
    if err:
        await _emit("stage_error", "suggest_pricing", error=err, retryable=False)
        pricing = None
    await _emit("stage_done", "suggest_pricing", data=asdict(pricing) if pricing else None)

    # ── S6 assemble manifest ──────────────────────────────────────────────────
    await _emit("stage_start", "assemble")
    manifest, errs = stage_assemble(intent, wf_choice, v2, skills, pricing)
    if manifest is None:
        await _emit("stage_error", "assemble", error="; ".join(errs) if errs else "装配失败", retryable=False)
        return None
    if errs:
        await _emit("stage_done", "assemble", data=manifest, warnings=errs)
    else:
        await _emit("stage_done", "assemble", data=manifest)

    await _emit("pipeline_done", "pipeline", manifest=manifest)
    return manifest
