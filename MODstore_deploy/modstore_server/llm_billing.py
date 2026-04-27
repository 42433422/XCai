"""LLM metering, wallet settlement and lightweight risk controls."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, Optional

import httpx
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from modstore_server.application.payment_gateway import PaymentGatewayService
from modstore_server.models import (
    AiModelPrice,
    ChatConversation,
    ChatMessage,
    LlmCallLog,
    RiskEvent,
)


DEFAULT_INPUT_PRICE_PER_1K = Decimal(os.environ.get("COSER_DEFAULT_INPUT_PRICE_PER_1K", "0.006"))
DEFAULT_OUTPUT_PRICE_PER_1K = Decimal(os.environ.get("COSER_DEFAULT_OUTPUT_PRICE_PER_1K", "0.018"))
DEFAULT_MIN_CHARGE = Decimal(os.environ.get("COSER_DEFAULT_MIN_CHARGE", "0.02"))
DEFAULT_PREAUTH_CHARGE = Decimal(os.environ.get("COSER_DEFAULT_PREAUTH_CHARGE", "0.05"))
DEFAULT_SERVICE_FEE_MULTIPLIER = Decimal(os.environ.get("COSER_SERVICE_FEE_MULTIPLIER", "1.5"))

_WINDOWS: dict[str, list[float]] = {}


@dataclass
class UsageMeter:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated: bool = False


@dataclass
class WalletHold:
    hold_no: str
    amount: Decimal
    enabled: bool


def money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def money_str(value: Decimal | float | int | str) -> str:
    return format(money(value), "f")


def estimate_tokens_from_text(text: str) -> int:
    # 粗略估算：中英文混合场景按 4 字符约 1 token，保底 1。
    return max(1, int(len(text or "") / 4) + 1)


def usage_from_response(raw_usage: Dict[str, Any] | None, messages: Iterable[Dict[str, str]], content: str) -> UsageMeter:
    usage = raw_usage or {}
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or usage.get("promptTokenCount") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or usage.get("candidatesTokenCount") or 0)
    total = int(usage.get("total_tokens") or usage.get("totalTokenCount") or 0)
    if prompt or completion or total:
        if not total:
            total = prompt + completion
        return UsageMeter(prompt, completion, total, estimated=False)
    prompt = sum(estimate_tokens_from_text(m.get("content") or "") for m in messages)
    completion = estimate_tokens_from_text(content)
    return UsageMeter(prompt, completion, prompt + completion, estimated=True)


def model_price(session: Session, provider: str, model: str) -> tuple[Decimal, Decimal, Decimal]:
    row = (
        session.query(AiModelPrice)
        .filter(AiModelPrice.provider == provider, AiModelPrice.model == model, AiModelPrice.enabled == True)
        .first()
    )
    if not row:
        return DEFAULT_INPUT_PRICE_PER_1K, DEFAULT_OUTPUT_PRICE_PER_1K, DEFAULT_MIN_CHARGE
    return (
        Decimal(str(row.input_price_per_1k or 0)),
        Decimal(str(row.output_price_per_1k or 0)),
        Decimal(str(row.min_charge or DEFAULT_MIN_CHARGE)),
    )


def calculate_charge(session: Session, provider: str, model: str, usage: UsageMeter) -> Decimal:
    in_price, out_price, min_charge = model_price(session, provider, model)
    base_amount = (Decimal(usage.prompt_tokens) / Decimal(1000) * in_price) + (
        Decimal(usage.completion_tokens) / Decimal(1000) * out_price
    )
    amount = base_amount * DEFAULT_SERVICE_FEE_MULTIPLIER
    return money(max(amount, min_charge))


def estimate_preauthorization(session: Session, provider: str, model: str, messages: Iterable[Dict[str, str]], max_tokens: int | None) -> Decimal:
    prompt_tokens = sum(estimate_tokens_from_text(m.get("content") or "") for m in messages)
    completion_tokens = max_tokens or int(os.environ.get("COSER_DEFAULT_PREAUTH_COMPLETION_TOKENS", "1024"))
    estimated = UsageMeter(prompt_tokens, completion_tokens, prompt_tokens + completion_tokens, estimated=True)
    return money(max(calculate_charge(session, provider, model, estimated), DEFAULT_PREAUTH_CHARGE))


def _client_ip(request: Request | None) -> str:
    if not request:
        return ""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else ""


def _limit_key(name: str, ident: str, window_seconds: int, limit: int) -> None:
    if limit <= 0:
        return
    now = time.monotonic()
    key = f"{name}:{ident}"
    rows = [t for t in _WINDOWS.get(key, []) if now - t < window_seconds]
    if len(rows) >= limit:
        raise HTTPException(429, "请求过于频繁，请稍后再试")
    rows.append(now)
    _WINDOWS[key] = rows


def enforce_risk_limits(session: Session, user_id: int, provider: str, model: str, messages: Iterable[Dict[str, str]], request: Request | None) -> None:
    ip = _client_ip(request)
    try:
        _limit_key("llm_user_minute", str(user_id), 60, int(os.environ.get("COSER_USER_LLM_RPM", "20")))
        if ip:
            _limit_key("llm_ip_minute", ip, 60, int(os.environ.get("COSER_IP_LLM_RPM", "60")))
        _limit_key("llm_provider_minute", provider, 60, int(os.environ.get("COSER_PROVIDER_LLM_RPM", "300")))
    except HTTPException:
        session.add(RiskEvent(user_id=user_id, ip=ip, event_type="rate_limited", provider=provider, model=model, detail="LLM rate limit"))
        session.commit()
        raise

    blocked_words = [x.strip() for x in os.environ.get("COSER_BLOCKED_WORDS", "").split(",") if x.strip()]
    if blocked_words:
        joined = "\n".join(m.get("content") or "" for m in messages)
        hit = next((w for w in blocked_words if w and w in joined), "")
        if hit:
            session.add(RiskEvent(user_id=user_id, ip=ip, event_type="content_blocked", provider=provider, model=model, detail=hit))
            session.commit()
            raise HTTPException(400, "内容未通过安全检查")


class JavaWalletClient:
    def __init__(self):
        self.gateway = PaymentGatewayService()

    @property
    def enabled(self) -> bool:
        return self.gateway.backend == "java"

    async def preauthorize(self, authorization: str, amount: Decimal, provider: str, model: str, request_id: str) -> WalletHold:
        if not self.enabled:
            return WalletHold(hold_no=f"debug-{request_id}", amount=money(amount), enabled=False)
        data = await self._post(
            "/api/wallet/ai/preauthorize",
            authorization,
            {
                "amount": money_str(amount),
                "provider": provider,
                "model": model,
                "request_id": request_id,
                "idempotency_key": f"{request_id}:preauth",
            },
        )
        hold = data.get("hold") or {}
        return WalletHold(hold_no=str(hold.get("hold_no") or ""), amount=money(hold.get("amount") or amount), enabled=True)

    async def settle(self, authorization: str, hold: WalletHold, actual_amount: Decimal, request_id: str) -> None:
        if not hold.enabled:
            return
        await self._post(
            "/api/wallet/ai/settle",
            authorization,
            {
                "hold_no": hold.hold_no,
                "actual_amount": money_str(actual_amount),
                "idempotency_key": f"{request_id}:settle",
            },
        )

    async def release(self, authorization: str, hold: WalletHold, reason: str, request_id: str) -> None:
        if not hold.enabled:
            return
        await self._post(
            "/api/wallet/ai/release",
            authorization,
            {
                "hold_no": hold.hold_no,
                "reason": reason,
                "idempotency_key": f"{request_id}:release",
            },
        )

    async def _post(self, path: str, authorization: str, body: Dict[str, Any]) -> Dict[str, Any]:
        if not authorization:
            raise HTTPException(401, "缺少登录令牌，无法完成钱包扣费")
        url = f"{self.gateway.target_base_url()}{path}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers={"Authorization": authorization, "Content-Type": "application/json"}, json=body)
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.text[:500])
        data = resp.json()
        if data.get("ok") is False:
            msg = str(data.get("message") or "钱包扣费失败")
            if "余额不足" in msg:
                raise HTTPException(402, msg)
            raise HTTPException(503, msg)
        return data


def authorization_header(request: Request | None) -> str:
    return request.headers.get("authorization", "") if request else ""


def new_request_id() -> str:
    return "llm_" + uuid.uuid4().hex


def save_success_log(
    session: Session,
    *,
    user_id: int,
    provider: str,
    model: str,
    messages: list[Dict[str, str]],
    content: str,
    usage: UsageMeter,
    charge: Decimal,
    hold_no: str,
    conversation_id: int | None = None,
) -> int:
    conversation = None
    if conversation_id:
        conversation = session.query(ChatConversation).filter(
            ChatConversation.id == conversation_id, ChatConversation.user_id == user_id
        ).first()
    if not conversation:
        title = next((m.get("content", "").strip() for m in messages if m.get("role") == "user"), "")[:80] or "新对话"
        conversation = ChatConversation(user_id=user_id, title=title, provider=provider, model=model)
        session.add(conversation)
        session.flush()

    for m in messages:
        if m.get("role") in {"user", "assistant", "system"}:
            session.add(ChatMessage(conversation_id=conversation.id, user_id=user_id, role=m.get("role") or "user", content=m.get("content") or "", provider=provider, model=model))
    session.add(
        ChatMessage(
            conversation_id=conversation.id,
            user_id=user_id,
            role="assistant",
            content=content,
            provider=provider,
            model=model,
            usage_json=json.dumps(usage.__dict__, ensure_ascii=False),
            charge_amount=float(charge),
        )
    )
    session.add(
        LlmCallLog(
            user_id=user_id,
            conversation_id=conversation.id,
            provider=provider,
            model=model,
            status="success",
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            estimated=usage.estimated,
            charge_amount=float(charge),
            hold_no=hold_no,
        )
    )
    session.commit()
    return int(conversation.id)


def save_failure_log(session: Session, *, user_id: int, provider: str, model: str, error: str, hold_no: str = "") -> None:
    session.add(
        LlmCallLog(
            user_id=user_id,
            provider=provider,
            model=model,
            status="failed",
            error=error[:2000],
            hold_no=hold_no,
        )
    )
    session.commit()
