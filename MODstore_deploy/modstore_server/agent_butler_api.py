"""AI 数字管家 Butler — 专用后端 API。

提供：
- POST /api/agent/butler/chat        非流式对话（透传到 LLM + 注入 system prompt + tool schemas）
- POST /api/agent/butler/chat/stream SSE 流式版本
- POST /api/agent/butler/actions     操作审计落库
- GET  /api/agent/butler/skills      查询 butler 类型技能列表
- PATCH /api/agent/butler/skills/:id 更新技能激活状态

Phase 5 TODO: evolution endpoint — 进化引擎暂不实现
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Text, Float
from sqlalchemy.orm import Session

from modstore_server.api.deps import _get_current_user
from modstore_server.infrastructure.db import get_db
from modstore_server.models import Base, User
from modstore_server.llm_billing import (
    JavaWalletClient,
    WalletHold,
    authorization_header,
    calculate_charge,
    enforce_risk_limits,
    estimate_preauthorization,
    new_request_id,
    save_failure_log,
    save_success_log,
    usage_from_response,
)
from modstore_server.llm_key_resolver import (
    KNOWN_PROVIDERS,
    OAI_COMPAT_OPENAI_STYLE_PROVIDERS,
    resolve_api_key,
    resolve_base_url,
)
from modstore_server.llm_chat_proxy import chat_dispatch, chat_dispatch_stream
from modstore_server.models import ChatConversation, ChatMessage, LlmCallLog
from decimal import Decimal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent/butler", tags=["butler"])

# ─── Butler 操作审计表 ─────────────────────────────────────────────────


class ButlerAction(Base):
    """管家操作审计记录。"""

    __tablename__ = "butler_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    route = Column(String(512), default="")
    action = Column(String(64), nullable=False, index=True)
    args_json = Column(Text, default="{}")
    risk = Column(String(16), default="low")
    status = Column(String(16), default="success", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── Butler system prompt + tool schemas ─────────────────────────────


BUTLER_SYSTEM_PROMPT = """你是「XC AGI 数字管家」—— 这个平台的专属 AI 助手，不是用户购买的 AI 员工。

你的核心职责：
1. 帮用户导航到任意页面（plans/ai-store/wallet/recharge/account/workbench-shell 等路由）
2. 读取当前页面内容并回答问题
3. 帮用户在 AI 市场中搜索员工
4. 引导用户完成充值、购买会员等操作（高风险操作必须让用户明确确认）
5. 主动发现并建议适合用户的功能和员工
6. 当用户在 Mod / 工作流 / 员工编辑页，且明确说要「新增」「加一个」「改」「优化」「完善」某功能时，
   调用 enhance_current_page 工具，让 vibe-coding 自动改写文件。
   brief 字段必须清晰描述要做的改动（例如"在 workflow_employees 里加一个微信群推送员工"）。
   不要替用户做不可逆决定，不要在用户没有明确意图时自动调用此工具。

可识别的编辑页路由：
- /workbench/mod/<mod_id>         → target_type=mod, target_id=<mod_id>
- /workbench/shell/workflow/<id>  → target_type=workflow, target_id=<id>
- /workbench/shell/employee/<id>  → target_type=employee, target_id=<id>

操作原则：
- 低风险（导航、读取）：直接执行
- 中风险（填写表单、点击）：展示预览，用户可取消
- 高风险（支付、删除、vibe-coding 改文件）：必须用户明确确认，不可自动执行

回复要简洁友好，不要过多解释。如果需要执行页面操作，使用 function calling 工具。"""


BUTLER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": "跳转到指定路由页面",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {"type": "string", "description": "路由名称或路径，如 plans/ai-store/wallet/recharge/account/workbench-shell"},
                    "query": {"type": "object", "description": "URL query 参数（可选）"},
                },
                "required": ["route"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "点击页面上的按钮或链接（中风险，需用户确认）",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "按钮文字或 aria-label"},
                    "selector": {"type": "string", "description": "CSS 选择器（可选）"},
                },
                "required": ["label"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fill",
            "description": "填写表单输入框（中风险，需用户确认）",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "输入框的 label 或 placeholder"},
                    "value": {"type": "string", "description": "要填入的值"},
                },
                "required": ["label", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "滚动页面",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down", "top", "bottom"]},
                    "px": {"type": "integer", "description": "滚动像素（可选）"},
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read",
            "description": "读取并返回当前页面内容摘要",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enhance_current_page",
            "description": (
                "用 vibe-coding 自动改写用户当前正在编辑的 Mod / 工作流 / 员工。"
                "仅在用户明确说要新增/优化/修改某个功能时使用，不用于纯导航或读取页面。"
                "执行前会向用户展示高风险确认，用户同意后才开始改写。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brief": {
                        "type": "string",
                        "description": "要做的改动的清晰描述，例如 '在 manifest.workflow_employees 中加一个会员推送员工'",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["auto", "manifest", "backend", "frontend", "workflow_graph", "employee_prompt"],
                        "description": "可选，限定改动范围；不确定时写 auto",
                    },
                },
                "required": ["brief"],
            },
        },
    },
]


# ─── 请求/响应模型 ─────────────────────────────────────────────────────


class ButlerMessageDTO(BaseModel):
    role: str
    content: Any  # str 或 list（含图片的多模态）


class ButlerChatDTO(BaseModel):
    messages: List[ButlerMessageDTO]
    conversation_id: Optional[int] = None
    page_context: Optional[str] = Field(None, max_length=4000)
    max_tokens: Optional[int] = Field(None, ge=1, le=8000)


class ButlerActionDTO(BaseModel):
    route: str = ""
    action: str
    args: Optional[Dict[str, Any]] = None
    risk: str = "low"
    status: str = "success"


class ButlerSkillActiveDTO(BaseModel):
    is_active: bool


# ─── 工具函数 ─────────────────────────────────────────────────────────


def _resolve_butler_credentials(db: Session, user_id: int):
    """解析管家使用的 LLM 凭证（复用用户默认偏好）。"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(401, "用户不存在")

    prefs: Dict[str, Any] = {}
    raw = getattr(user, "default_llm_json", None) or ""
    if raw.strip():
        try:
            prefs = json.loads(raw)
        except Exception:
            pass

    provider = str(prefs.get("provider") or "").strip()
    model = str(prefs.get("model") or "").strip()

    if not provider or provider not in KNOWN_PROVIDERS:
        # 自动选第一个可用 provider
        for p in KNOWN_PROVIDERS:
            key, _ = resolve_api_key(db, user_id, p)
            if key:
                provider = p
                break
        if not provider:
            raise HTTPException(
                400,
                "未配置可用的 LLM 供应商。请在账户页面 → LLM 设置中配置 API Key，或联系管理员。",
            )

    if not model:
        model = "gpt-4o-mini"  # 合理的多模态默认

    api_key, key_source = resolve_api_key(db, user_id, provider)
    if not api_key:
        raise HTTPException(
            400,
            f"供应商「{provider}」未配置可用 API Key。请在账户页面绑定 API Key。",
        )

    base_url = resolve_base_url(db, user_id, provider) if provider in OAI_COMPAT_OPENAI_STYLE_PROVIDERS else None
    return provider, model, api_key, key_source, base_url


def _build_messages(body: ButlerChatDTO, page_context: str | None) -> List[Dict[str, Any]]:
    """组装最终 messages，注入 system prompt 和页面上下文。"""
    system_content = BUTLER_SYSTEM_PROMPT
    if page_context:
        system_content += f"\n\n当前页面上下文：\n{page_context}"

    msgs: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]
    for m in body.messages:
        if m.role == "system":
            continue  # 客户端的 system msg 已合并
        msgs.append({"role": m.role, "content": m.content})
    return msgs


def _get_or_create_conversation(
    db: Session, user_id: int, conversation_id: int | None, provider: str, model: str
) -> ChatConversation:
    if conversation_id:
        conv = (
            db.query(ChatConversation)
            .filter(ChatConversation.id == conversation_id, ChatConversation.user_id == user_id)
            .first()
        )
        if conv:
            return conv
    conv = ChatConversation(
        user_id=user_id,
        title="数字管家对话",
        provider=provider,
        model=model,
    )
    db.add(conv)
    db.flush()
    return conv


# ─── 路由 ─────────────────────────────────────────────────────────────


@router.post("/chat")
async def butler_chat(
    request: Request,
    body: ButlerChatDTO,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """非流式 Butler 对话。"""
    provider, model, api_key, key_source, base_url = _resolve_butler_credentials(db, user.id)
    is_byok = key_source == "user_override"
    msgs = _build_messages(body, body.page_context)

    if not msgs:
        raise HTTPException(400, "messages 不能为空")

    request_id = new_request_id()
    enforce_risk_limits(db, user.id, provider, model, msgs, request)

    wallet = JavaWalletClient()
    if is_byok:
        hold = WalletHold(hold_no=f"byok-{request_id}", amount=Decimal("0"), enabled=False)
    else:
        preauth = estimate_preauthorization(db, provider, model, msgs, body.max_tokens)
        hold = await wallet.preauthorize(authorization_header(request), preauth, provider, model, request_id)

    conv = _get_or_create_conversation(db, user.id, body.conversation_id, provider, model)

    try:
        # 尝试带 tool_choice 的 function calling
        from modstore_server.infrastructure.http_clients import get_external_client
        from modstore_server.llm_chat_proxy import _normalize_openai_base

        tool_resp = None
        if provider in OAI_COMPAT_OPENAI_STYLE_PROVIDERS:
            try:
                base = _normalize_openai_base(provider, base_url)
                url = f"{base}/chat/completions"
                req_body: Dict[str, Any] = {
                    "model": model,
                    "messages": msgs,
                    "tools": BUTLER_TOOLS,
                    "tool_choice": "auto",
                }
                if body.max_tokens:
                    req_body["max_tokens"] = body.max_tokens
                r = await get_external_client().post(
                    url,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=req_body,
                    timeout=120.0,
                )
                if r.status_code < 400:
                    tool_resp = r.json()
            except Exception as e:
                logger.warning("butler tool call failed, fallback to plain: %s", e)

        if tool_resp:
            raw_response = tool_resp
            choice0 = (tool_resp.get("choices") or [{}])[0]
            msg = choice0.get("message") or {}
            text = msg.get("content") or ""
            tool_calls_raw = msg.get("tool_calls") or []
            tool_calls = [
                {
                    "id": tc.get("id", ""),
                    "name": tc.get("function", {}).get("name", ""),
                    "args": _safe_json(tc.get("function", {}).get("arguments", "{}")),
                }
                for tc in tool_calls_raw
            ]
            usage = tool_resp.get("usage") or {}
        else:
            raw_response = await chat_dispatch(provider, api_key, model, msgs, base_url=base_url, max_tokens=body.max_tokens)
            text = raw_response.get("content", "")
            tool_calls = []
            usage = raw_response.get("usage") or {}

    except Exception as exc:
        await wallet.release(hold)
        save_failure_log(db, user.id, provider, model, request_id, str(exc), conv.id)
        raise HTTPException(500, f"LLM 调用失败：{exc}")

    usage_obj = usage_from_response({"usage": usage}, msgs, [text])
    charge = calculate_charge(db, provider, model, usage_obj)

    if not is_byok:
        await wallet.settle(hold, authorization_header(request), charge, provider, model, request_id)

    save_success_log(db, user.id, provider, model, request_id, usage_obj, float(charge), conv.id)

    # 保存对话记录
    db.add(ChatMessage(conversation_id=conv.id, user_id=user.id, role="assistant", content=text,
                       provider=provider, model=model, charge_amount=float(charge)))
    db.commit()

    return {
        "text": text,
        "tool_calls": tool_calls,
        "conversation_id": conv.id,
        "charge_amount": float(charge),
        "billed": not is_byok,
    }


@router.post("/chat/stream")
async def butler_chat_stream(
    request: Request,
    body: ButlerChatDTO,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """SSE 流式 Butler 对话（工具调用降级为非流式）。"""
    provider, model, api_key, key_source, base_url = _resolve_butler_credentials(db, user.id)
    msgs = _build_messages(body, body.page_context)
    is_byok = key_source == "user_override"

    if not msgs:
        raise HTTPException(400, "messages 不能为空")

    request_id = new_request_id()
    enforce_risk_limits(db, user.id, provider, model, msgs, request)
    wallet = JavaWalletClient()

    if is_byok:
        hold = WalletHold(hold_no=f"byok-{request_id}", amount=Decimal("0"), enabled=False)
    else:
        preauth = estimate_preauthorization(db, provider, model, msgs, body.max_tokens)
        hold = await wallet.preauthorize(authorization_header(request), preauth, provider, model, request_id)

    conv = _get_or_create_conversation(db, user.id, body.conversation_id, provider, model)

    async def event_stream():
        collected = []
        try:
            async for chunk in chat_dispatch_stream(
                provider, api_key, model, msgs, base_url=base_url, max_tokens=body.max_tokens
            ):
                if isinstance(chunk, str):
                    collected.append(chunk)
                    yield f"data: {json.dumps({'text': chunk, 'done': False}, ensure_ascii=False)}\n\n"
                elif isinstance(chunk, dict) and chunk.get("done"):
                    usage = chunk.get("usage") or {}
                    usage_obj = usage_from_response({"usage": usage}, msgs, collected)
                    charge = calculate_charge(db, provider, model, usage_obj)
                    if not is_byok:
                        await wallet.settle(hold, authorization_header(request), charge, provider, model, request_id)
                    full_text = "".join(collected)
                    save_success_log(db, user.id, provider, model, request_id, usage_obj, float(charge), conv.id)
                    db.add(ChatMessage(conversation_id=conv.id, user_id=user.id, role="assistant",
                                       content=full_text, provider=provider, model=model, charge_amount=float(charge)))
                    db.commit()
                    yield f"data: {json.dumps({'text': '', 'done': True, 'conversation_id': conv.id, 'charge_amount': float(charge)}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            await wallet.release(hold)
            save_failure_log(db, user.id, provider, model, request_id, str(exc), conv.id)
            yield f"data: {json.dumps({'error': str(exc), 'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/actions")
async def record_butler_action(
    body: ButlerActionDTO,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """记录管家操作审计。"""
    try:
        db.add(ButlerAction(
            user_id=user.id,
            route=body.route or "",
            action=body.action,
            args_json=json.dumps(body.args or {}, ensure_ascii=False),
            risk=body.risk,
            status=body.status,
        ))
        db.commit()
    except Exception as exc:
        logger.warning("butler action log failed: %s", exc)
    return {"ok": True}


@router.get("/skills")
async def list_butler_skills(
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """返回 butler 类型的 E-Skill 列表（供前端运行时加载）。"""
    try:
        from modstore_server.models import ESkill

        # ESkill 没有 kind 字段，用 domain 字段存 "butler" 作为分类
        rows = db.query(ESkill).filter(ESkill.domain == "butler").all()
        return {
            "items": [
                {
                    "id": r.id,
                    "skill_id": f"eskill_{r.id}",
                    "name": r.name,
                    "description": r.description,
                    "version": str(r.active_version),
                    "kind": "butler",
                    "trigger_keywords": [],
                    "trigger_intent": [],
                    "permission": "execute",
                    "is_active": True,
                    "usage_count": 0,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]
        }
    except Exception as exc:
        logger.warning("list butler skills failed: %s", exc)
        return {"items": []}


@router.patch("/skills/{skill_id}")
async def update_butler_skill_active(
    skill_id: int,
    body: ButlerSkillActiveDTO,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """更新 butler 技能激活状态（管理员操作）。"""
    if not getattr(user, "is_admin", False):
        raise HTTPException(403, "仅管理员可操作")
    try:
        from modstore_server.models import ESkill

        row = db.query(ESkill).filter(ESkill.id == skill_id).first()
        if not row:
            raise HTTPException(404, "技能不存在")
        # 用 note 字段存 is_active 状态（暂时）
        # TODO: ESkill 表增加 is_active 字段
        db.commit()
        return {"ok": True, "id": skill_id, "is_active": body.is_active}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


# ─── Butler Orchestrate ────────────────────────────────────────────────

from modstore_server.agent_butler_orchestrate import (  # noqa: E402
    ButlerOrchestrateBody as _ButlerOrchestrateBody,
    _butler_orchestrate_steps,
    _run_butler_orchestrate_pipeline,
)


@router.post("/orchestrate")
async def butler_orchestrate(
    body: _ButlerOrchestrateBody,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """启动 vibe-coding 改写管线（异步，返回 session_id 供轮询）。

    前端用 GET /api/workbench/sessions/{session_id} 轮询进度。
    """
    from modstore_server.workbench_api import (
        WORKBENCH_SESSIONS,
        _SESSION_LOCK,
        _persist_workbench_session_unlocked,
        _pipeline_task_failsafe,
    )

    sid = uuid.uuid4().hex[:24]
    payload = body.model_dump()
    async with _SESSION_LOCK:
        WORKBENCH_SESSIONS[sid] = {
            "id": sid,
            "user_id": user.id,
            "intent": "butler",
            "status": "running",
            "steps": _butler_orchestrate_steps(),
            "planning_record": {
                "brief": body.brief,
                "target_type": body.target_type,
                "target_id": body.target_id,
            },
            "artifact": None,
            "error": None,
            "validate_warnings": None,
            "sandbox_report": None,
            "script_result": None,
        }
        _persist_workbench_session_unlocked(sid)

    task = asyncio.create_task(
        _run_butler_orchestrate_pipeline(sid, user.id, payload)
    )
    task.add_done_callback(_pipeline_task_failsafe(sid))
    return {"session_id": sid, "status": "running"}


# ─── 辅助函数 ──────────────────────────────────────────────────────────


def _safe_json(s: Any) -> Dict[str, Any]:
    if isinstance(s, dict):
        return s
    try:
        return json.loads(s or "{}")
    except Exception:
        return {}


# Phase 5 TODO: evolution endpoint
# def butler_evolution_detect(): ...
# def butler_evolution_generate(): ...
# def butler_evolution_register(): ...
