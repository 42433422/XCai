"""单元测试 & 集成测试：employee_ai_pipeline 6 阶段流水线。

每个 stage 单测使用 StubLlmClient（预设回复 FIFO 队列）；
orchestrator 集成测试覆盖三条路径：
  1. 工作流 LLM 匹配（score >= threshold）
  2. 工作流兜底生成（score < threshold，调 generate_fallback）
  3. Stage 1 失败中止（返回 None）
"""

from __future__ import annotations

import json
import pytest

from modstore_server.script_agent.llm_client import StubLlmClient
from modstore_server.employee_ai_pipeline import (
    Intent,
    WorkflowChoice,
    EmployeeConfigV2,
    SuggestedSkill,
    PricingHint,
    stage_parse_intent,
    stage_resolve_workflow,
    stage_design_v2,
    stage_suggest_skills,
    stage_suggest_pricing,
    stage_assemble,
    refine_system_prompt,
    run_pipeline,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

INTENT_JSON = json.dumps({
    "id": "refund-assistant",
    "name": "退款客服助手",
    "role": "退款流程处理",
    "scenario": "用户提交退款申请后自动核查订单并输出处理意见",
    "industry": "电商",
    "complexity": "medium",
})

RANK_JSON_MATCH = json.dumps({"best_index": 0, "score": 0.82, "reason": "完全匹配退款场景"})
RANK_JSON_NO_MATCH = json.dumps({"best_index": -1, "score": 0.1, "reason": "无匹配"})

V2_JSON = json.dumps({
    "perception": {"type": "document"},
    "memory": {"type": "long_term", "knowledge_base": "退款政策知识库"},
    "cognition": {
        "agent": {
            "system_prompt": (
                "你是退款客服助手，专门负责处理用户退款申请。"
                "工作步骤：1. 核查订单有效性 2. 判断是否符合退款条件 3. 输出处理意见。"
                "禁止：不得承诺未经核实的退款金额；不得透露内部系统数据。"
                "输出格式：结构化 JSON，包含 decision/amount/reason 三个字段。"
            ),
            "model": {"provider": "deepseek", "model_name": "deepseek-chat", "temperature": 0.2},
        }
    },
    "actions": {"handlers": ["text_output", "notify"]},
})

SKILLS_JSON = json.dumps([
    {"name": "订单查询", "brief": "根据订单号查询状态与详情"},
    {"name": "退款计算", "brief": "按规则计算可退金额"},
])

PRICING_JSON = json.dumps({
    "tier": "standard",
    "cny": 29,
    "period": "month",
    "reasoning": "中等复杂度，含长期记忆与通知功能，标准档定价合理",
})

SAMPLE_INTENT = Intent(
    id="refund-assistant",
    name="退款客服助手",
    role="退款流程处理",
    scenario="用户提交退款申请后自动核查订单并输出处理意见",
    industry="电商",
    complexity="medium",
)

SAMPLE_WF_CHOICE = WorkflowChoice(workflow_id=42, workflow_name="退款工作流", match_score=0.82, generated=False)

SAMPLE_V2 = EmployeeConfigV2(
    perception={"type": "document"},
    memory={"type": "long_term", "knowledge_base": "退款政策知识库"},
    cognition={
        "agent": {
            "system_prompt": "你是退款客服助手，专门负责退款流程处理。" * 5,
            "model": {"provider": "deepseek", "model_name": "deepseek-chat"},
        }
    },
    actions={"handlers": ["text_output", "notify"]},
)

SAMPLE_SKILLS = [
    SuggestedSkill(name="订单查询", brief="查询订单状态"),
    SuggestedSkill(name="退款计算", brief="计算可退金额"),
]

SAMPLE_PRICING = PricingHint(tier="standard", cny=29.0, period="month", reasoning="标准档")


# ── stage unit tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stage_parse_intent_ok():
    llm = StubLlmClient([INTENT_JSON])
    intent, err = await stage_parse_intent("我要一个能处理退款的客服助手", llm)
    assert err == ""
    assert intent is not None
    assert intent.id == "refund-assistant"
    assert intent.name == "退款客服助手"
    assert intent.complexity == "medium"


@pytest.mark.asyncio
async def test_stage_parse_intent_bad_json():
    llm = StubLlmClient(["not-json!!"])
    intent, err = await stage_parse_intent("brief", llm)
    assert intent is None
    assert "JSON" in err


@pytest.mark.asyncio
async def test_stage_parse_intent_id_sanitized():
    bad_id_json = json.dumps({
        "id": "Hello World!!",
        "name": "测试",
        "role": "role",
        "scenario": "sc",
        "industry": "通用",
        "complexity": "low",
    })
    llm = StubLlmClient([bad_id_json])
    intent, err = await stage_parse_intent("brief", llm)
    assert err == ""
    assert intent is not None
    assert " " not in intent.id
    assert "!" not in intent.id


@pytest.mark.asyncio
async def test_stage_resolve_workflow_match():
    llm = StubLlmClient([RANK_JSON_MATCH])
    wfs = [{"id": 42, "name": "退款工作流", "description": "处理用户退款"}]
    choice, err = await stage_resolve_workflow(SAMPLE_INTENT, wfs, llm, score_threshold=0.55)
    assert err == ""
    assert choice is not None
    assert choice.workflow_id == 42
    assert choice.generated is False
    assert choice.match_score == pytest.approx(0.82)


@pytest.mark.asyncio
async def test_stage_resolve_workflow_no_match_with_fallback():
    llm = StubLlmClient([RANK_JSON_NO_MATCH])
    wfs = [{"id": 1, "name": "完全不相关流程", "description": ""}]
    fallback_called = []

    async def fake_fallback():
        fallback_called.append(True)
        return {"ok": True, "workflow_id": 99, "name": "生成的工作流"}

    choice, err = await stage_resolve_workflow(
        SAMPLE_INTENT, wfs, llm, generate_fallback=fake_fallback, score_threshold=0.55
    )
    assert err == ""
    assert choice is not None
    assert choice.workflow_id == 99
    assert choice.generated is True
    assert fallback_called


@pytest.mark.asyncio
async def test_stage_resolve_workflow_empty_list_no_fallback():
    llm = StubLlmClient([])
    choice, err = await stage_resolve_workflow(SAMPLE_INTENT, [], llm)
    assert err == ""
    assert choice is not None
    assert choice.workflow_id is None
    assert choice.generated is False


@pytest.mark.asyncio
async def test_stage_resolve_workflow_fallback_fails():
    llm = StubLlmClient([RANK_JSON_NO_MATCH])
    wfs = [{"id": 1, "name": "x", "description": ""}]

    async def fail_fallback():
        return {"ok": False, "error": "NL 生图失败"}

    choice, err = await stage_resolve_workflow(
        SAMPLE_INTENT, wfs, llm, generate_fallback=fail_fallback, score_threshold=0.55
    )
    assert choice is None
    assert "NL 生图失败" in err


@pytest.mark.asyncio
async def test_stage_design_v2_ok():
    llm = StubLlmClient([V2_JSON])
    v2, err = await stage_design_v2(SAMPLE_INTENT, SAMPLE_WF_CHOICE, llm)
    assert err == ""
    assert v2 is not None
    assert v2.perception["type"] == "document"
    assert v2.memory["type"] == "long_term"
    assert "system_prompt" in v2.cognition["agent"]
    assert "text_output" in v2.actions["handlers"]


@pytest.mark.asyncio
async def test_stage_design_v2_missing_prompt_gets_default():
    no_prompt = json.dumps({
        "perception": {"type": "text"},
        "memory": {"type": "session"},
        "cognition": {"agent": {"system_prompt": "", "model": {"provider": "deepseek", "model_name": "deepseek-chat"}}},
        "actions": {"handlers": ["echo"]},
    })
    llm = StubLlmClient([no_prompt])
    v2, err = await stage_design_v2(SAMPLE_INTENT, None, llm)
    assert err == ""
    assert v2 is not None
    assert v2.cognition["agent"]["system_prompt"]  # filled by default


@pytest.mark.asyncio
async def test_stage_suggest_skills_ok():
    llm = StubLlmClient([SKILLS_JSON])
    skills, err = await stage_suggest_skills(SAMPLE_INTENT, llm)
    assert err == ""
    assert len(skills) == 2
    assert skills[0].name == "订单查询"
    assert skills[0].unverified is True


@pytest.mark.asyncio
async def test_stage_suggest_skills_not_array():
    llm = StubLlmClient(['{"key": "value"}'])
    skills, err = await stage_suggest_skills(SAMPLE_INTENT, llm)
    assert skills == []
    assert "数组" in err


@pytest.mark.asyncio
async def test_stage_suggest_pricing_ok():
    llm = StubLlmClient([PRICING_JSON])
    pricing, err = await stage_suggest_pricing(SAMPLE_INTENT, SAMPLE_V2, SAMPLE_SKILLS, llm)
    assert err == ""
    assert pricing is not None
    assert pricing.tier == "standard"
    assert pricing.cny == pytest.approx(29.0)
    assert pricing.period == "month"


@pytest.mark.asyncio
async def test_stage_assemble_produces_valid_manifest():
    manifest, errs = stage_assemble(SAMPLE_INTENT, SAMPLE_WF_CHOICE, SAMPLE_V2, SAMPLE_SKILLS, SAMPLE_PRICING)
    assert manifest is not None, f"assemble returned None: {errs}"
    assert manifest["id"] == "refund-assistant"
    assert manifest["artifact"] == "employee_pack"
    v2 = manifest["employee_config_v2"]
    assert v2["perception"]["type"] == "document"
    meta = v2["metadata"]
    assert any(s["name"] == "订单查询" for s in meta["suggested_skills"])
    assert meta["suggested_pricing"]["tier"] == "standard"
    assert manifest["workflow_employees"][0].get("workflow_id") == 42


@pytest.mark.asyncio
async def test_stage_assemble_no_workflow():
    manifest, errs = stage_assemble(SAMPLE_INTENT, None, SAMPLE_V2, [], None)
    assert manifest is not None
    assert "workflow_employees" in manifest


@pytest.mark.asyncio
async def test_refine_system_prompt_ok():
    result_json = json.dumps({
        "improved_prompt": "你是专业退款客服AI助手，负责处理用户退款申请...",
        "diff_explanation": "增加了具体工作步骤和禁忌规则",
    })
    llm = StubLlmClient([result_json])
    result, err = await refine_system_prompt(
        current_prompt="你是客服助手",
        instruction="增加退款处理的具体步骤",
        role_context="退款场景",
        llm=llm,
    )
    assert err == ""
    assert result is not None
    assert result["improved_prompt"]
    assert result["diff_explanation"]


# ── orchestrator integration tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_workflow_match():
    """Path 1: eligible workflow found with high score."""
    llm = StubLlmClient([INTENT_JSON, RANK_JSON_MATCH, V2_JSON, SKILLS_JSON, PRICING_JSON])
    events: list = []

    async def on_event(ev):
        events.append(ev)

    manifest = await run_pipeline(
        "我要一个能处理退款的客服助手",
        llm=llm,
        on_event=on_event,
        eligible_workflows=[{"id": 42, "name": "退款工作流", "description": "处理退款"}],
    )
    assert manifest is not None
    assert manifest["id"] == "refund-assistant"

    stage_events = {e["stage"]: e["event"] for e in events if e.get("event") in ("stage_done", "stage_error")}
    assert stage_events.get("parse_intent") == "stage_done"
    assert stage_events.get("resolve_workflow") == "stage_done"
    assert stage_events.get("design_v2") == "stage_done"
    assert stage_events.get("assemble") == "stage_done"
    assert any(e["event"] == "pipeline_done" for e in events)


@pytest.mark.asyncio
async def test_pipeline_workflow_fallback_generation():
    """Path 2: no eligible workflows → fallback generator called."""
    llm = StubLlmClient([INTENT_JSON, V2_JSON, SKILLS_JSON, PRICING_JSON])
    fallback_called = []

    async def fake_fallback():
        fallback_called.append(True)
        return {"ok": True, "workflow_id": 99, "name": "AI 生成工作流"}

    events: list = []

    async def on_event(ev):
        events.append(ev)

    manifest = await run_pipeline(
        "我要一个能处理退款的客服助手",
        llm=llm,
        on_event=on_event,
        eligible_workflows=[],
        generate_workflow_fallback=fake_fallback,
    )
    assert manifest is not None
    assert fallback_called
    wf_done = next((e for e in events if e["stage"] == "resolve_workflow" and e["event"] == "stage_done"), None)
    assert wf_done is not None
    assert wf_done["data"]["generated"] is True
    assert wf_done["data"]["workflow_id"] == 99


@pytest.mark.asyncio
async def test_pipeline_stage1_failure_aborts():
    """Path 3: parse_intent returns bad JSON → pipeline returns None."""
    llm = StubLlmClient(["not-json"])
    events: list = []

    async def on_event(ev):
        events.append(ev)

    manifest = await run_pipeline(
        "brief",
        llm=llm,
        on_event=on_event,
        eligible_workflows=[],
    )
    assert manifest is None
    error_ev = next((e for e in events if e.get("event") == "stage_error"), None)
    assert error_ev is not None
    assert error_ev["stage"] == "parse_intent"
    assert error_ev["retryable"] is True


@pytest.mark.asyncio
async def test_pipeline_skills_error_non_fatal():
    """Skills stage error should not abort the pipeline."""
    llm = StubLlmClient([INTENT_JSON, RANK_JSON_MATCH, V2_JSON, "not-json-array", PRICING_JSON])
    events: list = []

    async def on_event(ev):
        events.append(ev)

    manifest = await run_pipeline(
        "brief",
        llm=llm,
        on_event=on_event,
        eligible_workflows=[{"id": 42, "name": "退款工作流", "description": ""}],
    )
    assert manifest is not None  # pipeline still completes
    skill_err = next((e for e in events if e["stage"] == "suggest_skills" and e["event"] == "stage_error"), None)
    assert skill_err is not None
    assert skill_err["retryable"] is False
