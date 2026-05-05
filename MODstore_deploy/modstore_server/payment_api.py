"""XC AGI 支付宝支付路由：下单、回调、查询、套餐、诊断。

⚠️ 兼容层：当 ``PAYMENT_BACKEND=java`` 时（生产推荐），FastAPI 中间件会将
``/api/payment/**`` 整段透传到 Java 支付服务（见 ``app._payment_backend_proxy_middleware``），
本文件中的实现仅作为本地开发或灰度回滚用 fallback。任何对账/履约的真实入口请改写
``java_payment_service``，并通过 ``payment_contract`` + ``test_payment_contract`` 维护契约。

新增端点应优先：
1. 在 ``payment_contract.PAYMENT_ENDPOINTS`` 注册；
2. 在 Java 控制器实现；
3. 仅在 fallback 必要时在本文件实现。
"""

from __future__ import annotations

import logging
import os
import time
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from modstore_server import alipay_service
from modstore_server.application.payment_gateway import PaymentGatewayService, java_payment_unreachable_message
from modstore_server import payment_orders
from modstore_server import cache
from modstore_server import webhook_dispatcher
from modstore_server import account_level_service
from modstore_server.eventing.contracts import PAYMENT_PAID, WALLET_BALANCE_CHANGED
from modstore_server.models import (
    CatalogItem,
    Entitlement,
    EmployeeExecutionMetric,
    PlanTemplate,
    Purchase,
    Quota,
    Transaction,
    User,
    UserPlan,
    Wallet,
    get_session_factory,
    init_db,
)
from modstore_server.api.deps import _get_current_user
from modstore_server.payment_common import (
    REPLAY_WINDOW,
    check_replay_attack,
    generate_signature,
    processed_requests,
    verify_signature,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payment", tags=["payment"])

# 支付宝回调 / 查询结果与本地订单金额比对容差（元）
_AMOUNT_TOLERANCE = 0.01

init_db()
# Plan 模板可能在 init_db() 中被升级（VIP/VIP+/svip 改名 + SVIP2~8 新增），
# 立刻清掉 /plans 的缓存，避免老旧 5 分钟缓存遮蔽新数据。
try:
    cache.delete("modstore:plans:active")
except Exception:
    pass


def _parse_money(value: Any) -> Optional[float]:
    """将订单或回调中的金额字段解析为 float；无法解析则返回 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _amounts_match(order_amount: Any, paid_amount: Any, *, tol: float = _AMOUNT_TOLERANCE) -> bool:
    """比较本地订单金额与支付宝返回金额是否在容差内。"""
    a = _parse_money(order_amount)
    b = _parse_money(paid_amount)
    if a is None or b is None:
        return False
    return abs(a - b) <= tol

def _plan_rows(session) -> list[PlanTemplate]:
    rows = list(session.query(PlanTemplate).filter(PlanTemplate.is_active == True).all())
    rows.sort(
        key=lambda p: (
            MEMBERSHIP_TIER_ORDER.get(p.id, 9999),
            p.id or "",
        )
    )
    return rows


# 任一 SVIP 档（含入门 svip）算作"已是 SVIP 用户"，可购买 SVIP2~SVIP8
SVIP_TIER_PLAN_IDS: frozenset[str] = frozenset(
    {"plan_enterprise", "plan_svip2", "plan_svip3", "plan_svip4", "plan_svip5", "plan_svip6", "plan_svip7", "plan_svip8"}
)
# 需要"先成为 SVIP"才能购买的进阶档
SVIP_LOCKED_PLAN_IDS: frozenset[str] = frozenset(
    {"plan_svip2", "plan_svip3", "plan_svip4", "plan_svip5", "plan_svip6", "plan_svip7", "plan_svip8"}
)

# 与前端 PaymentPlansView MEMBERSHIP_TIER_ORDER 一致：值越大档越高
MEMBERSHIP_TIER_ORDER: dict[str, int] = {
    "plan_basic": 0,
    "plan_pro": 1,
    "plan_enterprise": 2,
    "plan_svip2": 3,
    "plan_svip3": 4,
    "plan_svip4": 5,
    "plan_svip5": 6,
    "plan_svip6": 7,
    "plan_svip7": 8,
    "plan_svip8": 9,
}


def _plan_required_predecessor(plan_id: str | None) -> str | None:
    """SVIP2~SVIP8 必须先持有 svip 入门档（plan_enterprise），其余套餐无前置依赖。"""
    pid = (plan_id or "").strip()
    return "plan_enterprise" if pid in SVIP_LOCKED_PLAN_IDS else None


def _user_max_membership_tier_order(session, user_id: int) -> int:
    """用户当前所有 active UserPlan 中、已知套餐 ID 里最高的档位序。无 known 行则 -1。"""
    if not user_id:
        return -1
    rows = (
        session.query(UserPlan.plan_id)
        .filter(UserPlan.user_id == user_id, UserPlan.is_active == True)
        .all()
    )
    m = -1
    for (pid,) in rows:
        s = (pid or "").strip()
        r = MEMBERSHIP_TIER_ORDER.get(s, -1)
        if r > m:
            m = r
    return m


def _user_owns_svip_tier(session, user_id: int) -> bool:
    """判断用户当前是否拥有任一 SVIP 档（含 svip 入门档）。

    使用 ``UserPlan`` 的 active 行做判断：购买 svip 后即解锁 SVIP2~8 购买资格；
    后续升档到 SVIP2-8，``UserPlan`` 的 active plan_id 也属于 SVIP_TIER_PLAN_IDS，
    依然满足条件。
    """
    if not user_id:
        return False
    rows = (
        session.query(UserPlan.plan_id)
        .filter(UserPlan.user_id == user_id, UserPlan.is_active == True)
        .all()
    )
    return any((pid or "") in SVIP_TIER_PLAN_IDS for (pid,) in rows)


def _plan_as_dict(row: PlanTemplate) -> dict[str, Any]:
    try:
        features = __import__("json").loads(row.features_json or "[]")
    except Exception:
        features = []
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description or "",
        "price": float(row.price or 0),
        "features": features if isinstance(features, list) else [],
        # FE 用此字段判断是否需要"购买 svip 后解锁"
        "requires_plan": _plan_required_predecessor(row.id),
    }


def _plan_quotas(row: PlanTemplate) -> dict[str, int]:
    try:
        q = __import__("json").loads(row.quotas_json or "{}")
    except Exception:
        q = {}
    if not isinstance(q, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in q.items():
        try:
            out[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out


def _membership_meta(plan_id: str | None) -> dict[str, Any]:
    pid = (plan_id or "").strip()
    meta = {
        "plan_basic": ("vip", "VIP", True, False),
        "plan_pro": ("vip_plus", "VIP+", True, True),
        "plan_enterprise": ("svip1", "svip", True, True),
        "plan_svip2": ("svip2", "SVIP2", True, True),
        "plan_svip3": ("svip3", "SVIP3", True, True),
        "plan_svip4": ("svip4", "SVIP4", True, True),
        "plan_svip5": ("svip5", "SVIP5", True, True),
        "plan_svip6": ("svip6", "SVIP6", True, True),
        "plan_svip7": ("svip7", "SVIP7", True, True),
        "plan_svip8": ("svip8", "SVIP8", True, True),
    }.get(pid, ("free", "普通用户", False, False))
    return {"tier": meta[0], "label": meta[1], "is_member": meta[2], "can_byok": meta[3]}

# ── DTOs ────────────────────────────────────────────────────


class SignCheckoutBody(BaseModel):
    """服务端签名请求体（不含 request_id / timestamp / signature）。"""

    plan_id: str = ""
    item_id: int = 0
    total_amount: float = 0
    subject: str = ""
    wallet_recharge: bool = False


class CheckoutDTO(BaseModel):
    """下单请求。"""

    plan_id: str = ""
    item_id: int = 0
    total_amount: float = 0
    subject: str = ""
    wallet_recharge: bool = False
    pay_channel: str = Field(default="alipay", description="alipay 或 wechat，不参与签名字段")
    request_id: str = Field(..., description="请求唯一标识")
    timestamp: int = Field(..., description="请求时间戳")
    signature: str = Field(..., description="请求签名")


def _amount_sign_str(x: Any) -> str:
    """与前端 ``amountSignStr`` 一致：整数不带小数，小数最多 6 位并去尾 0。"""
    try:
        xf = float(x or 0)
    except (TypeError, ValueError):
        return "0"
    if xf == int(xf):
        return str(int(xf))
    s = f"{xf:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"


def canonical_checkout_sign_data(body: CheckoutDTO) -> dict[str, str]:
    """下单签名的七字段 canonical 形态（键排序后与前端相同）。"""
    return {
        "item_id": str(int(body.item_id or 0)),
        "plan_id": (body.plan_id or "").strip(),
        "request_id": str(body.request_id),
        "subject": (body.subject or "").strip(),
        "timestamp": str(int(body.timestamp)),
        "total_amount": _amount_sign_str(body.total_amount),
        "wallet_recharge": "true" if body.wallet_recharge else "false",
    }


def _resolve_checkout_fields(
    session,
    body: SignCheckoutBody,
    user_id: int | None = None,
) -> tuple[str, float, int, str, str, bool]:
    """
    解析下单业务字段（与 ``/checkout`` 逻辑一致）。
    返回 ``(subject, total_amount, item_id, plan_id, order_kind, wallet_recharge)``。

    ``user_id`` 可选；若提供，则会对 SVIP2~SVIP8 套餐做"必须已是 SVIP"前置检查。
    """
    subject = (body.subject or "").strip() or "XC AGI 订单"
    total_amount = float(body.total_amount or 0)
    plan_id = ""
    item_id = 0
    order_kind = ""
    wallet_recharge = bool(body.wallet_recharge)

    if wallet_recharge:
        if not total_amount or total_amount <= 0:
            raise HTTPException(400, "请填写大于 0 的充值金额")
        subject = (body.subject or "").strip() or "XC AGI 钱包充值"
        order_kind = "wallet"
    elif body.plan_id:
        plan_row = session.query(PlanTemplate).filter(
            PlanTemplate.id == body.plan_id, PlanTemplate.is_active == True
        ).first()
        if not plan_row:
            raise HTTPException(404, f"套餐 {body.plan_id} 不存在")
        # SVIP2~SVIP8 必须先成为 SVIP（持有 plan_enterprise / SVIP2-8 之一的 active UserPlan）
        if (body.plan_id or "").strip() in SVIP_LOCKED_PLAN_IDS:
            if not user_id or not _user_owns_svip_tier(session, int(user_id)):
                raise HTTPException(403, "需要先购买 svip 档后才能购买 SVIP2~SVIP8")
        pid = (body.plan_id or "").strip()
        t_new = MEMBERSHIP_TIER_ORDER.get(pid, -1)
        if user_id and t_new >= 0:
            t_cur = _user_max_membership_tier_order(session, int(user_id))
            if t_cur >= 0 and t_new < t_cur:
                raise HTTPException(400, "已拥有更高等级会员，不能购买此低档套餐")
        plan = _plan_as_dict(plan_row)
        total_amount = float(plan["price"])
        subject = str(plan["name"])
        plan_id = body.plan_id.strip()
        order_kind = "plan"
        wallet_recharge = False
    elif body.item_id:
        item = session.query(CatalogItem).filter(CatalogItem.id == body.item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        if item.price <= 0:
            raise HTTPException(400, "免费商品，无需支付")
        total_amount = float(item.price)
        subject = str(item.name)
        item_id = int(body.item_id)
        order_kind = "item"
        wallet_recharge = False
        if user_id:
            dup = (
                session.query(Purchase)
                .filter(Purchase.user_id == int(user_id), Purchase.catalog_id == int(body.item_id))
                .first()
            )
            if dup:
                raise HTTPException(400, "您已购买过该商品，无需重复支付")
    else:
        raise HTTPException(400, "请使用 wallet_recharge、plan_id 或 item_id 之一下单")

    if total_amount <= 0:
        raise HTTPException(400, "金额必须大于 0")

    return subject, total_amount, item_id, plan_id, order_kind, wallet_recharge


def _checkout_return_url(request: Request, out_trade_no: str) -> str | None:
    """收银台回跳地址（page/wap pay 的 return_url / quit_url）。"""
    origin = (os.environ.get("MODSTORE_PUBLIC_ORIGIN") or "").strip().rstrip("/")
    if not origin:
        origin = str(request.base_url).rstrip("/")
    prefix = (os.environ.get("MODSTORE_MARKET_PREFIX") or "/market").strip()
    if prefix and not prefix.startswith("/"):
        prefix = "/" + prefix
    prefix = prefix.rstrip("/")
    path = f"{prefix}/checkout/{out_trade_no}" if prefix else f"/checkout/{out_trade_no}"
    return f"{origin}{path}"


def _fulfill_paid_order(out_trade_no: str) -> None:
    """支付成功后幂等入账（钱包 / 套餐 / 市场商品）。

    Phase A：``PAYMENT_BACKEND=java`` 时 Java 拥有履约权（通过事件 + DB 事务），
    本函数直接返回。Python 侧履约逻辑已移除，待 Java 稳定 6 个月后（Phase C）
    删除本函数及其调用点。
    """
    if not payment_orders.is_local_source_of_truth():
        logger.warning(
            "PAYMENT_BACKEND=java; skipping Python _fulfill_paid_order for %s (Java owns fulfillment)",
            out_trade_no,
        )
        return
    # Phase C（Java 稳定后）: 删除以下 Python 履约路径及整个函数
    logger.error(
        "_fulfill_paid_order called in Python mode for %s — "
        "this path is deprecated; set PAYMENT_BACKEND=java to route via Java.",
        out_trade_no,
    )


# ── 套餐列表 ─────────────────────────────────────────────────


@router.get("/plans")
def api_payment_plans():
    """获取可用套餐列表。"""
    cached = cache.get_json("modstore:plans:active")
    if cached is not None:
        return cached
    sf = get_session_factory()
    with sf() as session:
        result = {"plans": [_plan_as_dict(p) for p in _plan_rows(session)]}
        cache.set_json("modstore:plans:active", result, 300)
        return result


@router.get("/my-plan")
def api_my_plan(user: User = Depends(_get_current_user)):
    sf = get_session_factory()
    with sf() as session:
        row = (
            session.query(UserPlan)
            .filter(UserPlan.user_id == user.id, UserPlan.is_active == True)
            .order_by(UserPlan.id.desc())
            .first()
        )
        if not row:
            return {"plan": None, "quotas": [], "membership": _membership_meta(None)}
        plan = session.query(PlanTemplate).filter(PlanTemplate.id == row.plan_id).first()
        membership = _membership_meta(row.plan_id)
        quotas = session.query(Quota).filter(Quota.user_id == user.id).all()
        return {
            "plan": {
                "id": row.plan_id,
                "name": plan.name if plan else row.plan_id,
                "started_at": row.started_at.isoformat() if row.started_at else "",
                "expires_at": row.expires_at.isoformat() if row.expires_at else "",
                **membership,
            },
            "membership": membership,
            "quotas": [
                {
                    "quota_type": q.quota_type,
                    "total": q.total,
                    "used": q.used,
                    "remaining": max((q.total or 0) - (q.used or 0), 0),
                    "reset_at": q.reset_at.isoformat() if q.reset_at else "",
                }
                for q in quotas
            ],
        }


# ── 下单（Checkout） ─────────────────────────────────────────


@router.post("/sign-checkout")
def api_sign_checkout(body: SignCheckoutBody, user: User = Depends(_get_current_user)):
    """
    服务端生成支付下单签名（``PAYMENT_SECRET_KEY`` 仅在后端使用）。
    前端应使用返回的 ``request_id`` / ``timestamp`` / ``signature`` 及解析后的金额字段调用 ``POST /checkout``。
    """
    sf = get_session_factory()
    with sf() as session:
        subject, total_amount, item_id, plan_id, _order_kind, wallet_recharge = _resolve_checkout_fields(
            session, body, user_id=user.id
        )
    request_id = str(uuid.uuid4())
    timestamp = int(time.time())
    dto = CheckoutDTO(
        plan_id=plan_id,
        item_id=item_id,
        total_amount=total_amount,
        subject=subject,
        wallet_recharge=wallet_recharge,
        request_id=request_id,
        timestamp=timestamp,
        signature="-",
    )
    secret_key = os.environ.get("PAYMENT_SECRET_KEY", "") or "default_secret_key"
    data_to_sign = canonical_checkout_sign_data(dto)
    sig = generate_signature(data_to_sign, secret_key)
    return {
        "request_id": request_id,
        "timestamp": timestamp,
        "signature": sig,
        "subject": subject,
        "total_amount": total_amount,
        "item_id": item_id,
        "plan_id": plan_id,
        "wallet_recharge": wallet_recharge,
    }


async def _forward_checkout_to_java(request: Request, body: CheckoutDTO) -> Response | None:
    """PAYMENT_BACKEND=java 时由中间件转发；若请求仍落到本路由，则直连 Java，避免误用 Python 侧支付宝配置。"""
    gw = PaymentGatewayService()
    if gw.backend != "java":
        return None
    url = f"{gw.java_url.rstrip('/')}/api/payment/checkout"
    payload = body.model_dump(exclude_none=True)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    auth = request.headers.get("authorization")
    if auth:
        headers["Authorization"] = auth
    ua = request.headers.get("user-agent")
    if ua:
        headers["User-Agent"] = ua
    from modstore_server.infrastructure.http_clients import get_java_client

    try:
        client = get_java_client()
        r = await client.post(url, json=payload, headers=headers, timeout=30.0, follow_redirects=False)
    except httpx.HTTPError as e:
        raise HTTPException(502, java_payment_unreachable_message(e)) from e
    hop = {
        k: v
        for k, v in r.headers.items()
        if k.lower() not in {"content-length", "transfer-encoding", "connection", "content-encoding"}
    }
    return Response(content=r.content, status_code=r.status_code, headers=dict(hop))


@router.post("/checkout")
async def api_payment_checkout(
    body: CheckoutDTO,
    request: Request,
    user: User = Depends(_get_current_user),
):
    """
    创建支付宝订单（需登录）。
    模式：
      - ``wallet_recharge=true`` + ``total_amount``：钱包充值
      - ``plan_id``：购买预设套餐
      - ``item_id``：购买市场中的 MOD
    返回: ``type`` 为 ``page`` / ``wap`` / ``precreate``，对应跳转 URL 或扫码内容。
    """
    try:
        # 防重放攻击检查
        if check_replay_attack(body.request_id, body.timestamp):
            raise HTTPException(400, "请求已过期或重复")

        secret_key = os.environ.get("PAYMENT_SECRET_KEY", "") or "default_secret_key"

        sf = get_session_factory()
        with sf() as session:
            subject, total_amount, item_id, plan_id, order_kind, wallet_recharge = _resolve_checkout_fields(
                session,
                SignCheckoutBody(
                    plan_id=body.plan_id,
                    item_id=body.item_id,
                    total_amount=body.total_amount,
                    subject=body.subject,
                    wallet_recharge=body.wallet_recharge,
                ),
                user_id=user.id,
            )

        dto_verify = CheckoutDTO(
            plan_id=plan_id,
            item_id=item_id,
            total_amount=total_amount,
            subject=subject,
            wallet_recharge=wallet_recharge,
            pay_channel=(body.pay_channel or "alipay").strip() or "alipay",
            request_id=body.request_id,
            timestamp=body.timestamp,
            signature=body.signature,
        )
        data_to_sign = canonical_checkout_sign_data(dto_verify)
        if not verify_signature(data_to_sign, secret_key, body.signature):
            raise HTTPException(400, "签名验证失败")

        java_response = await _forward_checkout_to_java(request, dto_verify)
        if java_response is not None:
            return java_response

        # Phase A: Python Alipay 下单路径已进入弃用状态。
        # 生产环境应设置 PAYMENT_BACKEND=java；中间件会在到达此处前完成代理。
        # 若到达此处说明 PAYMENT_BACKEND != java，仅允许本地开发。
        if not payment_orders.is_local_source_of_truth():
            raise HTTPException(
                503,
                "支付路由配置错误：PAYMENT_BACKEND=java 时请求应由中间件代理到 Java，"
                "未预期到达 Python checkout 路径。请检查中间件配置。",
            )

        user_id = user.id

        if not alipay_service.alipay_ui_ready():
            detail = alipay_service.alipay_not_ready_reason()
            raise HTTPException(
                503,
                (
                    "支付宝支付未配置，请联系管理员。"
                    f" 缺失项：{detail}"
                    "（管理员登录后可请求 GET /api/payment/diagnostics 查看明细）"
                ),
            )

        out_trade_no = f"MOD{int(time.time())}{user_id:06d}"
        order_result = payment_orders.create(
            out_trade_no=out_trade_no,
            subject=subject,
            total_amount=f"{total_amount:.2f}",
            user_id=user_id,
            item_id=item_id,
            plan_id=plan_id,
            order_kind=order_kind,
        )
        if not order_result["ok"]:
            raise HTTPException(500, f"创建订单失败: {order_result.get('message')}")

        ua = request.headers.get("user-agent", "")
        return_url = _checkout_return_url(request, out_trade_no)
        notify_url = (os.environ.get("ALIPAY_NOTIFY_URL") or "").strip() or alipay_service.notify_url_default()
        pay_result = alipay_service.create_pay_order(
            out_trade_no=out_trade_no,
            subject=subject,
            total_amount=f"{total_amount:.2f}",
            user_agent=ua,
            return_url=return_url,
            quit_url=return_url,
            notify_url=notify_url,
        )

        if not pay_result["ok"]:
            payment_orders.update_status(out_trade_no=out_trade_no, status="failed")
            raise HTTPException(502, f"支付下单失败: {pay_result.get('message')}")

        extras: dict[str, Any] = {"pay_type": pay_result.get("type")}
        if pay_result.get("qr_code"):
            extras["qr_code"] = pay_result["qr_code"]
        payment_orders.merge_fields(out_trade_no, **extras)

        return {
            "ok": True,
            "order_id": out_trade_no,
            "type": pay_result["type"],
            "redirect_url": pay_result.get("redirect_url"),
            "qr_code": pay_result.get("qr_code"),
            "subject": subject,
            "total_amount": total_amount,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("支付下单异常: %s", e)
        raise HTTPException(500, "系统内部错误，请稍后重试")


# ── 支付宝异步通知回调 ────────────────────────────────────────


@router.post("/notify/alipay")
async def api_payment_notify_alipay(request: Request):
    """
    支付宝异步通知。
    验签 → 更新订单 → 发放权益。
    """
    try:
        form_data = await request.form()
        data = dict(form_data)

        signature = data.pop("sign", "")
        if not signature:
            logger.warning("支付宝通知缺少签名")
            return "fail"

        # 验签
        if not alipay_service.verify_notify(data, signature):
            logger.warning("支付宝通知验签失败")
            return "fail"

        out_trade_no = data.get("out_trade_no", "")
        trade_status = data.get("trade_status", "")
        trade_no = data.get("trade_no", "")
        total_amount = data.get("total_amount", "")
        buyer_id = data.get("buyer_id", "")

        if not out_trade_no:
            logger.warning("支付宝通知缺少 out_trade_no")
            return "fail"

        # 只处理支付成功的通知
        if trade_status not in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            return "success"

        # 查询本地订单
        order = payment_orders.find(out_trade_no)
        if not order:
            logger.warning("本地订单不存在: %s", out_trade_no)
            return "fail"

        if order.get("status") == "paid":
            logger.info("订单已处理，跳过: %s", out_trade_no)
            return "success"

        # 金额校验（规范化 + 容差，避免 str/float 与格式差异）
        if not _amounts_match(order.get("total_amount"), total_amount):
            logger.warning(
                "金额不匹配: 期望 %s, 实际 %s",
                order.get("total_amount"),
                total_amount,
            )
            return "fail"

        # 更新订单状态
        paid_at = datetime.now(timezone.utc).isoformat()
        payment_orders.update_status(
            out_trade_no=out_trade_no,
            status="paid",
            trade_no=trade_no,
            buyer_id=buyer_id,
            paid_at=paid_at,
        )

        _fulfill_paid_order(out_trade_no)
        logger.info("订单支付成功并已发放权益: %s, 金额 %s", out_trade_no, total_amount)
        return "success"
    except Exception as e:
        logger.error("处理支付宝通知异常: %s", e)
        return "fail"


# ── 订单查询 ──────────────────────────────────────────────────


@router.get("/query/{out_trade_no}")
def api_payment_query(out_trade_no: str, user: User = Depends(_get_current_user)):
    """查询本地订单状态，同时调用支付宝接口确认。登录用户只能查询自己的订单；管理员可查任意订单。"""
    try:
        order = payment_orders.find(out_trade_no)
        if not order:
            raise HTTPException(404, "订单不存在")
        if not user.is_admin and str(order.get("user_id", "")) != str(user.id):
            raise HTTPException(403, "无权查看该订单")

        # 如果本地状态为 pending，尝试调用支付宝确认
        if order.get("status") == "pending":
            try:
                alipay_result = alipay_service.query_order(out_trade_no=out_trade_no)
                if alipay_result.get("ok"):
                    raw = alipay_result.get("raw", {})
                    trade_status = raw.get("trade_status", "")
                    if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
                        remote_amt = raw.get("total_amount")
                        if not _amounts_match(order.get("total_amount"), remote_amt):
                            logger.warning(
                                "查询同步金额不匹配: order=%s 本地=%s 支付宝=%s",
                                out_trade_no,
                                order.get("total_amount"),
                                remote_amt,
                            )
                        else:
                            payment_orders.update_status(
                                out_trade_no=out_trade_no,
                                status="paid",
                                trade_no=raw.get("trade_no"),
                                buyer_id=raw.get("buyer_id"),
                                paid_at=datetime.now(timezone.utc).isoformat(),
                            )
                            _fulfill_paid_order(out_trade_no)
                            order = payment_orders.find(out_trade_no) or order
            except Exception as e:
                logger.error("查询支付宝订单状态异常: %s", e)
                # 继续返回本地订单状态，不影响查询

        if order.get("status") == "paid" and not order.get("fulfilled"):
            try:
                _fulfill_paid_order(out_trade_no)
                order = payment_orders.find(out_trade_no) or order
            except Exception as e:
                logger.error("发放权益异常: %s", e)
                # 继续返回订单状态

        return order
    except HTTPException:
        raise
    except Exception as e:
        logger.error("查询订单异常: %s", e)
        raise HTTPException(500, "系统内部错误，请稍后重试")


@router.get("/orders")
def api_payment_list_orders(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(_get_current_user),
):
    """列出当前用户的支付订单。"""
    try:
        rows, total = payment_orders.list_orders(
            user_id=user.id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return {"orders": rows, "total": total}
    except Exception as e:
        logger.error("查询订单列表异常: %s", e)
        raise HTTPException(500, "系统内部错误，请稍后重试")


@router.post("/orders/dismiss-non-active")
def api_payment_dismiss_non_active_orders(user: User = Depends(_get_current_user)):
    """将当前用户所有「非活跃」（closed / expired / refunded）订单标记为已读/隐藏。
    前端 paymentDismissNonActiveOrders 消费此接口。
    """
    try:
        rows, _ = payment_orders.list_orders(user_id=user.id, status=None, limit=500, offset=0)
        dismissed = 0
        for o in rows:
            if (o.get("status") or "").lower() in ("closed", "expired", "refunded", "cancelled"):
                ono = o.get("out_trade_no") or o.get("order_no") or ""
                if ono:
                    payment_orders.merge_fields(ono, dismissed=True)
                    dismissed += 1
        return {"ok": True, "dismissed": dismissed}
    except Exception as e:
        logger.error("dismiss-non-active 异常: %s", e)
        raise HTTPException(500, "系统内部错误")


@router.post("/cancel/{order_no}")
def api_payment_cancel_order(order_no: str, user: User = Depends(_get_current_user)):
    """取消待支付订单。"""
    ono = (order_no or "").strip()
    order = payment_orders.find(ono)
    if not order or int(order.get("user_id") or 0) != user.id:
        raise HTTPException(404, "订单不存在")
    if (order.get("status") or "").strip().lower() != "pending":
        raise HTTPException(400, f"订单状态为 {order.get('status')}，无法取消")
    payment_orders.merge_fields(ono, status="closed")
    return {"ok": True}


# ── 诊断 ─────────────────────────────────────────────────────


@router.get("/diagnostics")
def api_payment_diagnostics(user: User = Depends(_get_current_user)):
    """支付配置诊断（管理员用）。"""
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return alipay_service.diagnostics_snapshot()


# ── 已购权益 ─────────────────────────────────────────────────


@router.get("/entitlements")
def api_payment_entitlements(user: User = Depends(_get_current_user)):
    """获取用户已购买的 MOD/AI 员工列表。"""
    sf = get_session_factory()
    with sf() as session:
        purchases = (
            session.query(Purchase)
            .filter(Purchase.user_id == user.id)
            .order_by(Purchase.created_at.desc())
            .all()
        )
        items = []
        for p in purchases:
            item = session.query(CatalogItem).filter(CatalogItem.id == p.catalog_id).first()
            if item:
                items.append({
                    "purchase_id": p.id,
                    "catalog_id": item.id,
                    "pkg_id": item.pkg_id,
                    "version": item.version,
                    "name": item.name,
                    "price_paid": p.amount,
                    "purchased_at": p.created_at.isoformat() if p.created_at else "",
                })
        return {"items": items, "total": len(items)}


@router.get("/usage-metrics")
def api_usage_metrics(user: User = Depends(_get_current_user)):
    sf = get_session_factory()
    with sf() as session:
        rows = (
            session.query(EmployeeExecutionMetric)
            .filter(EmployeeExecutionMetric.user_id.in_([0, user.id]))
            .order_by(EmployeeExecutionMetric.id.desc())
            .limit(200)
            .all()
        )
        total = len(rows)
        ok = len([r for r in rows if r.status == "success"])
        token_sum = sum(int(r.llm_tokens or 0) for r in rows)
        duration = sum(float(r.duration_ms or 0) for r in rows)
        return {
            "total_calls": total,
            "success_rate": (ok / total * 100.0) if total else 0,
            "total_tokens": token_sum,
            "avg_duration_ms": (duration / total) if total else 0.0,
            "rows": [
                {
                    "employee_id": r.employee_id,
                    "task": r.task,
                    "status": r.status,
                    "duration_ms": r.duration_ms,
                    "llm_tokens": r.llm_tokens,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows[:30]
            ],
        }


class RefundDTO(BaseModel):
    out_trade_no: str
    reason: str = "用户申请退款"
    refund_reason: Optional[str] = Field(
        None,
        description="结构化退款原因（用于风控/对账归档）。空时取 reason 兜底。",
        max_length=256,
    )


@router.post("/refund")
def api_payment_refund(body: RefundDTO, user: User = Depends(_get_current_user)):
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    order = payment_orders.find(body.out_trade_no)
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.get("status") != "paid":
        raise HTTPException(400, "仅支持已支付订单退款")
    if order.get("refunded"):
        raise HTTPException(400, "订单已退款")
    sf = get_session_factory()
    with sf() as session:
        user_id = int(order.get("user_id") or 0)
        amount = float(order.get("total_amount") or 0)
        wallet = (
            session.query(Wallet)
            .filter(Wallet.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not wallet:
            wallet = Wallet(user_id=user_id, balance=0.0)
            session.add(wallet)
            session.flush()
        # 按订单类型决定是否调整钱包余额：
        #   wallet  — 充值退款，需从余额扣回（余额必须充足，否则拒绝）
        #   plan    — 套餐退款，同步收回已发放的 LLM 余额（向下取 0，不允许负数）
        #   item    — 市场商品通过支付宝退款，钱包余额无需变动
        kind = (order.get("kind") or "").strip()
        if kind == "wallet":
            current = float(wallet.balance or 0)
            if current < amount:
                raise HTTPException(
                    400,
                    f"钱包余额（{current:.2f}）不足以退款（{amount:.2f}），请先检查账户",
                )
            wallet.balance = current - amount
        elif kind == "plan":
            wallet.balance = max(0.0, float(wallet.balance or 0) - amount)
        # else: item/其他 — 支付宝渠道退款，不动钱包余额
        session.add(
            Transaction(
                user_id=user_id,
                amount=-amount,
                txn_type="refund",
                status="completed",
                description=f"退款 {body.out_trade_no}: {body.reason}",
            )
        )
        session.query(Entitlement).filter(
            Entitlement.source_order_id == body.out_trade_no, Entitlement.is_active == True
        ).update({"is_active": False})
        try:
            xp_revoked = account_level_service.revoke_order_xp(
                session,
                user_id=user_id,
                out_trade_no=body.out_trade_no,
                description=f"管理员退款扣回经验 ({body.out_trade_no})",
            )
            if xp_revoked:
                logger.info(
                    "账号经验 -%s user=%s order=%s",
                    xp_revoked,
                    user_id,
                    body.out_trade_no,
                )
        except Exception:
            logger.exception("管理员退款扣回经验失败: %s", body.out_trade_no)
        payment_orders.merge_fields(body.out_trade_no, refunded=True, refund_reason=body.reason)
        session.commit()
    return {"ok": True}
