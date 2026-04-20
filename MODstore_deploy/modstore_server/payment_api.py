"""XC AGI 支付宝支付路由：下单、回调、查询、套餐、诊断。"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from modstore_server import alipay_service
from modstore_server import payment_orders
from modstore_server.auth_service import decode_access_token, get_user_by_id
from modstore_server.models import CatalogItem, Purchase, Transaction, User, Wallet, get_session_factory, init_db
from modstore_server.market_api import _get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payment", tags=["payment"])

init_db()

# ── 套餐定义（可扩展为 DB 读取） ────────────────────────────

DEFAULT_PLANS: list[dict[str, Any]] = [
    {
        "id": "plan_basic",
        "name": "基础版 MOD",
        "description": "包含基础数据处理和1个 AI 员工",
        "price": 9.90,
        "features": ["基础数据库", "字段管理", "1个 AI 员工"],
    },
    {
        "id": "plan_pro",
        "name": "专业版 MOD",
        "description": "完整工作流能力 + 3个 AI 员工",
        "price": 29.90,
        "features": ["高级数据库", "流程规则", "自动化处理", "3个 AI 员工", "报表导出"],
    },
    {
        "id": "plan_enterprise",
        "name": "企业版 MOD",
        "description": "不限 AI 员工 + 专属部署支持",
        "price": 99.90,
        "features": ["全部功能", "不限 AI 员工", "专属部署", "优先技术支持", "自定义域名"],
    },
]

# ── DTOs ────────────────────────────────────────────────────


class CheckoutDTO(BaseModel):
    """下单请求。"""

    plan_id: str = ""
    item_id: int = 0
    total_amount: float = 0
    subject: str = ""


# ── 获取当前用户（可选） ─────────────────────────────────────


def _get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[User]:
    raw = (authorization or "").strip()
    if not raw.startswith("Bearer "):
        return None
    token = raw[7:]
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = int(payload["sub"])
    return get_user_by_id(user_id)


# ── 套餐列表 ─────────────────────────────────────────────────


@router.get("/plans")
def api_payment_plans():
    """获取可用套餐列表。"""
    return {
        "plans": DEFAULT_PLANS,
    }


# ── 下单（Checkout） ─────────────────────────────────────────


@router.post("/checkout")
async def api_payment_checkout(
    body: CheckoutDTO,
    request: Request,
    user: Optional[User] = Depends(_get_optional_user),
):
    """
    创建支付宝订单。
    支持三种模式：
      - plan_id: 购买预设套餐
      - item_id: 购买市场中的 MOD/AI 员工
      - 直接指定 total_amount + subject（充值模式）
    返回: {"ok", "order_id", "type": "page"|"wap"|"precreate", "redirect_url"|"qr_code"}
    """
    user_id = user.id if user else 0

    # 1. 确定金额和标题
    subject = body.subject or "XC AGI 订单"
    total_amount = body.total_amount

    if body.plan_id:
        plan = next((p for p in DEFAULT_PLANS if p["id"] == body.plan_id), None)
        if not plan:
            raise HTTPException(404, f"套餐 {body.plan_id} 不存在")
        total_amount = plan["price"]
        subject = plan["name"]

    elif body.item_id:
        sf = get_session_factory()
        with sf() as session:
            item = session.query(CatalogItem).filter(CatalogItem.id == body.item_id).first()
            if not item:
                raise HTTPException(404, "商品不存在")
            if item.price <= 0:
                return {"ok": True, "message": "免费商品，无需支付"}
            total_amount = item.price
            subject = item.name

    if not total_amount or total_amount <= 0:
        raise HTTPException(400, "金额必须大于 0")

    # 2. 检查支付宝是否就绪
    if not alipay_service.alipay_ui_ready():
        raise HTTPException(503, "支付宝支付未配置，请联系管理员")

    # 3. 创建订单记录
    out_trade_no = f"MOD{int(time.time())}{user_id:06d}"
    order_result = payment_orders.create(
        out_trade_no=out_trade_no,
        subject=subject,
        total_amount=str(total_amount),
        user_id=user_id,
        item_id=body.item_id,
    )
    if not order_result["ok"]:
        raise HTTPException(500, f"创建订单失败: {order_result.get('message')}")

    # 4. 调用支付宝下单（自动根据 UA 选择 page/wap/precreate）
    ua = request.headers.get("user-agent", "")
    pay_result = alipay_service.create_pay_order(
        out_trade_no=out_trade_no,
        subject=subject,
        total_amount=f"{total_amount:.2f}",
        user_agent=ua,
        notify_url=os.environ.get("ALIPAY_NOTIFY_URL"),
    )

    if not pay_result["ok"]:
        # 更新订单为失败状态
        payment_orders.update_status(out_trade_no=out_trade_no, status="failed")
        raise HTTPException(502, f"支付下单失败: {pay_result.get('message')}")

    return {
        "ok": True,
        "order_id": out_trade_no,
        "type": pay_result["type"],
        "redirect_url": pay_result.get("redirect_url"),
        "qr_code": pay_result.get("qr_code"),
        "subject": subject,
        "total_amount": total_amount,
    }


# ── 支付宝异步通知回调 ────────────────────────────────────────


@router.post("/notify/alipay")
async def api_payment_notify_alipay(request: Request):
    """
    支付宝异步通知。
    验签 → 更新订单 → 发放权益。
    """
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

    # 金额校验
    if order.get("total_amount") != total_amount:
        logger.warning("金额不匹配: 期望 %s, 实际 %s", order.get("total_amount"), total_amount)
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

    # 发放权益
    user_id = order.get("user_id", 0)
    item_id = order.get("item_id", 0)

    if item_id:
        # 购买商品：创建 Purchase 记录 + 充值到钱包
        sf = get_session_factory()
        with sf() as session:
            wallet = session.query(Wallet).filter(Wallet.user_id == user_id).first()
            if not wallet:
                wallet = Wallet(user_id=user_id, balance=0.0)
                session.add(wallet)
            wallet.balance += float(total_amount)
            wallet.updated_at = datetime.now(timezone.utc)
            txn = Transaction(
                user_id=user_id,
                amount=float(total_amount),
                txn_type="alipay_recharge",
                status="completed",
                description=f"支付宝充值 (订单 {out_trade_no})",
            )
            session.add(txn)
            session.commit()

    logger.info("订单支付成功并已发放权益: %s, 用户 %d, 金额 %s", out_trade_no, user_id, total_amount)
    return "success"


# ── 订单查询 ──────────────────────────────────────────────────


@router.get("/query/{out_trade_no}")
def api_payment_query(out_trade_no: str):
    """查询本地订单状态，同时调用支付宝接口确认。"""
    order = payment_orders.find(out_trade_no)
    if not order:
        raise HTTPException(404, "订单不存在")

    # 如果本地状态为 pending，尝试调用支付宝确认
    if order.get("status") == "pending":
        try:
            alipay_result = alipay_service.query_order(out_trade_no=out_trade_no)
            if alipay_result.get("ok"):
                raw = alipay_result.get("raw", {})
                trade_status = raw.get("trade_status", "")
                if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
                    # 同步本地状态
                    payment_orders.update_status(
                        out_trade_no=out_trade_no,
                        status="paid",
                        trade_no=raw.get("trade_no"),
                        buyer_id=raw.get("buyer_id"),
                        paid_at=datetime.now(timezone.utc).isoformat(),
                    )
                    order["status"] = "paid"
        except Exception:
            pass

    return order


@router.get("/orders")
def api_payment_list_orders(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(_get_current_user),
):
    """列出当前用户的支付订单。"""
    rows, total = payment_orders.list_orders(
        user_id=user.id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"orders": rows, "total": total}


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
