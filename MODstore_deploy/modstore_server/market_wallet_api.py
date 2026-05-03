"""XC AGI 在线市场 API：钱包、余额、充值、交易记录。"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from modstore_server.models import (
    Transaction,
    User,
    Wallet,
    get_session_factory,
)
from modstore_server.market_shared import _get_current_user

router = APIRouter(tags=["market"])


class RechargeDTO(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = ""
    recharge_token: str = ""


class AdminSelfCreditDTO(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = ""


@router.get("/wallet/balance")
def api_wallet_balance(user: User = Depends(_get_current_user)):
    sf = get_session_factory()
    with sf() as session:
        wallet = session.query(Wallet).filter(Wallet.user_id == user.id).first()
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=0.0)
            session.add(wallet)
            session.commit()
        return {
            "balance": wallet.balance,
            "updated_at": wallet.updated_at.isoformat() if wallet.updated_at else "",
        }


@router.post("/wallet/recharge")
def api_wallet_recharge(
    body: RechargeDTO,
    request: Request,
    user: User = Depends(_get_current_user),
):
    if not user.is_admin:
        raise HTTPException(403, "仅管理员可使用 Token 直充接口，且只能为当前登录账号加款")
    admin_token = (os.environ.get("MODSTORE_ADMIN_RECHARGE_TOKEN") or "").strip()
    if not admin_token:
        raise HTTPException(503, "未配置 MODSTORE_ADMIN_RECHARGE_TOKEN，无法直充")
    client_token = (request.headers.get("X-Modstore-Recharge-Token") or "").strip() or (
        body.recharge_token or ""
    ).strip()
    if client_token != admin_token:
        raise HTTPException(403, "无效的充值授权")

    sf = get_session_factory()
    with sf() as session:
        wallet = session.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().first()
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=0.0)
            session.add(wallet)
            session.flush()
        wallet.balance += body.amount
        wallet.updated_at = datetime.now(timezone.utc)
        txn = Transaction(
            user_id=user.id,
            amount=body.amount,
            txn_type="recharge",
            status="completed",
            description=body.description or "管理员充值",
        )
        session.add(txn)
        session.commit()
        return {"ok": True, "new_balance": wallet.balance}


def _admin_self_credit_cap() -> float:
    raw = (os.environ.get("MODSTORE_ADMIN_SELF_CREDIT_CAP") or "").strip()
    if not raw:
        return 100_000.0
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 100_000.0


@router.post("/wallet/admin-self-credit")
def api_wallet_admin_self_credit(body: AdminSelfCreditDTO, user: User = Depends(_get_current_user)):
    if not user.is_admin:
        raise HTTPException(403, "仅管理员可为本人钱包加款")
    cap = _admin_self_credit_cap()
    if body.amount > cap:
        raise HTTPException(400, f"单次加款不能超过 {cap:g} 元")

    sf = get_session_factory()
    with sf() as session:
        wallet = session.query(Wallet).filter(Wallet.user_id == user.id).with_for_update().first()
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=0.0)
            session.add(wallet)
            session.flush()
        wallet.balance += body.amount
        wallet.updated_at = datetime.now(timezone.utc)
        txn = Transaction(
            user_id=user.id,
            amount=body.amount,
            txn_type="admin_self_credit",
            status="completed",
            description=(body.description or "").strip() or "管理员本人加款",
        )
        session.add(txn)
        session.commit()
        return {"ok": True, "new_balance": wallet.balance, "balance": wallet.balance}


@router.get("/wallet/transactions")
def api_wallet_transactions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(_get_current_user),
):
    sf = get_session_factory()
    with sf() as session:
        total = session.query(Transaction).filter(Transaction.user_id == user.id).count()
        rows = (
            session.query(Transaction)
            .filter(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "transactions": [
                {
                    "id": r.id,
                    "amount": r.amount,
                    "type": r.txn_type,
                    "status": r.status,
                    "description": r.description,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ],
            "total": total,
        }
