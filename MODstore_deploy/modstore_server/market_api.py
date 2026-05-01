"""XC AGI 在线市场 API：认证、钱包、购买、个人商店。"""

from __future__ import annotations

import os
import hashlib
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from modstore_server.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_user_by_id,
    hash_password,
    register_user,
    verify_password,
)
from modstore_server.email_service import (
    assert_email_outbound_configured,
    find_user_by_email,
    generate_verification_code,
    send_verification_email,
)
from modstore_server import account_level_service, catalog_sync
from modstore_server.api.deps import get_current_user, require_admin
from modstore_server.models import (
    CatalogItem,
    Entitlement,
    Favorite,
    Purchase,
    Review,
    Transaction,
    User,
    VerificationCode,
    Wallet,
    get_session_factory,
    init_db,
)

router = APIRouter(prefix="/api", tags=["market"])

# ── Auth helpers (legacy aliases) ───────────────────────────────
# 共享认证依赖来自 ``api/deps``，这里仅保留模块级别的别名以避免大批量
# Depends 重写。``test_neuro_ddd_boundaries`` 锁定本文件不再 *自己* 实现
# auth helper，详见 ``application/auth.py``。
_get_current_user = get_current_user
_require_admin = require_admin


# ── DTOs ─────────────────────────────────────────────────────


class RegisterDTO(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6)
    email: str = Field(..., min_length=5, max_length=128, description="必填，用于接收验证码")
    verification_code: str = Field(..., min_length=4, max_length=16, description="邮箱验证码")


class LoginDTO(BaseModel):
    username: str
    password: str


class SendCodeDTO(BaseModel):
    email: str


class LoginWithCodeDTO(BaseModel):
    email: str
    code: str


class RefreshTokenDTO(BaseModel):
    refresh_token: str


class ResetPasswordDTO(BaseModel):
    email: str
    code: str = Field(..., min_length=4, max_length=16)
    new_password: str = Field(..., min_length=6, max_length=128)


class AdminResetUserPasswordDTO(BaseModel):
    """线下运维：凭 MODSTORE_ADMIN_RECHARGE_TOKEN 重置指定用户密码（无邮件场景）。"""

    username: str = Field(..., min_length=1, max_length=64)
    new_password: str = Field(..., min_length=6, max_length=128)


class RechargeDTO(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = ""
    recharge_token: str = ""


class BuyDTO(BaseModel):
    pass


class UploadCatalogDTO(BaseModel):
    pkg_id: str = Field(..., min_length=1, max_length=128)
    version: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    price: float = Field(..., ge=0)
    artifact: str = "mod"


def _normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _delete_unused_verification_code(email: str, code: str) -> None:
    """发信失败时删除未使用的一条验证码，避免用户拿到无效码。"""
    sf = get_session_factory()
    with sf() as session:
        session.query(VerificationCode).filter(
            VerificationCode.email == email,
            VerificationCode.code == code,
            VerificationCode.used == False,
        ).delete(synchronize_session=False)
        session.commit()


def _background_send_verification_email(email: str, code: str, purpose: str) -> None:
    import logging

    try:
        send_verification_email(email, code, purpose)
    except Exception:
        logging.exception(
            "Background verification email failed email=%s purpose=%s",
            email,
            purpose,
        )
        try:
            _delete_unused_verification_code(email, code)
        except Exception:
            logging.exception("Failed to remove verification code after email failure")


def _verify_and_consume_verification_code(email: str, code: str) -> None:
    """校验并作废一条未过期的邮箱验证码（email 须已小写归一化）。"""
    code = (code or "").strip()
    if not code:
        raise HTTPException(400, "请填写验证码")
    sf = get_session_factory()
    with sf() as session:
        vc = (
            session.query(VerificationCode)
            .filter(
                VerificationCode.email == email,
                VerificationCode.code == code,
                VerificationCode.used == False,
                VerificationCode.expires_at > datetime.utcnow(),
            )
            .order_by(VerificationCode.created_at.desc())
            .first()
        )
        if not vc:
            raise HTTPException(401, "验证码无效或已过期")
        vc.used = True
        session.commit()


# ── Auth endpoints ───────────────────────────────────────────


@router.post("/auth/register")
def api_register(body: RegisterDTO):
    email_norm = _normalize_email(body.email)
    if not email_norm or "@" not in email_norm:
        raise HTTPException(400, "请填写有效邮箱")
    vcode = (body.verification_code or "").strip()
    if not vcode:
        raise HTTPException(400, "请填写邮箱验证码，并先通过「获取验证码」收取邮件")
    _verify_and_consume_verification_code(email_norm, vcode)
    try:
        user = register_user(body.username, body.password, email_norm)
    except ValueError as e:
        raise HTTPException(409, str(e))
    access_token = create_access_token(user.id, user.username)
    refresh_token = create_refresh_token(user.id, user.username)
    return {
        "ok": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.post("/auth/login")
def api_login(body: LoginDTO):
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    access_token = create_access_token(user.id, user.username)
    refresh_token = create_refresh_token(user.id, user.username)
    return {
        "ok": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.get("/auth/me")
def api_me(user: User = Depends(_get_current_user)):
    # 经验值与等级档由前端导航栏 / 设置页直接消费；缺失会导致用户停在 Lv.1
    exp = int(getattr(user, "experience", 0) or 0)
    level_profile = account_level_service.build_level_profile(exp).to_dict()
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "experience": exp,
        "level_profile": level_profile,
    }


@router.post("/auth/send-code", status_code=202)
def api_send_code(body: SendCodeDTO, background_tasks: BackgroundTasks):
    email_norm = _normalize_email(body.email)
    if not email_norm:
        raise HTTPException(400, "请填写邮箱")

    user = find_user_by_email(email_norm)
    if not user:
        raise HTTPException(404, "该邮箱未注册")

    try:
        assert_email_outbound_configured()
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    code = generate_verification_code()
    sf = get_session_factory()
    with sf() as session:
        vc = VerificationCode(
            email=email_norm,
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        session.add(vc)
        session.commit()

    background_tasks.add_task(_background_send_verification_email, email_norm, code, "login")

    return {
        "ok": True,
        "message": "验证码已受理，邮件正在发送（约数秒内送达），5 分钟内有效",
        "queued": True,
    }


@router.post("/auth/send-register-code", status_code=202)
def api_send_register_code(body: SendCodeDTO, background_tasks: BackgroundTasks):
    """向未注册邮箱发送注册验证码：先 202 落库，再异步 SMTP。"""
    email_norm = _normalize_email(body.email)
    if not email_norm:
        raise HTTPException(400, "请填写邮箱")

    if find_user_by_email(email_norm):
        raise HTTPException(409, "该邮箱已注册")

    try:
        assert_email_outbound_configured()
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    code = generate_verification_code()
    sf = get_session_factory()
    with sf() as session:
        vc = VerificationCode(
            email=email_norm,
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        session.add(vc)
        session.commit()

    background_tasks.add_task(_background_send_verification_email, email_norm, code, "register")

    return {
        "ok": True,
        "message": "验证码已受理，邮件正在发送（约数秒内送达），5 分钟内有效",
        "queued": True,
    }


@router.post("/auth/login-with-code")
def api_login_with_code(body: LoginWithCodeDTO):
    email_norm = _normalize_email(body.email)
    if not email_norm:
        raise HTTPException(400, "请填写邮箱")

    user = find_user_by_email(email_norm)
    if not user:
        raise HTTPException(404, "该邮箱未注册")

    sf = get_session_factory()
    with sf() as session:
        vc = (
            session.query(VerificationCode)
            .filter(
                VerificationCode.email == email_norm,
                VerificationCode.code == (body.code or "").strip(),
                VerificationCode.used == False,
                VerificationCode.expires_at > datetime.utcnow(),
            )
            .order_by(VerificationCode.created_at.desc())
            .first()
        )
        if not vc:
            raise HTTPException(401, "验证码无效或已过期")

        vc.used = True
        session.commit()

    access_token = create_access_token(user.id, user.username)
    refresh_token = create_refresh_token(user.id, user.username)
    return {
        "ok": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.post("/auth/send-reset-password-code", status_code=202)
def api_send_reset_password_code(body: SendCodeDTO, background_tasks: BackgroundTasks):
    """忘记密码：向已注册邮箱发送验证码（未注册邮箱返回相同提示，不泄露是否存在）。"""
    email_norm = _normalize_email(body.email)
    if not email_norm:
        raise HTTPException(400, "请填写邮箱")
    user = find_user_by_email(email_norm)
    if not user:
        return {
            "ok": True,
            "message": "如果该邮箱已注册，将收到验证码邮件",
            "queued": True,
        }
    try:
        assert_email_outbound_configured()
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    code = generate_verification_code()
    sf = get_session_factory()
    with sf() as session:
        vc = VerificationCode(
            email=email_norm,
            code=code,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        session.add(vc)
        session.commit()

    background_tasks.add_task(_background_send_verification_email, email_norm, code, "reset")

    return {
        "ok": True,
        "message": "如果该邮箱已注册，将收到验证码邮件",
        "queued": True,
    }


@router.post("/auth/reset-password")
def api_reset_password(body: ResetPasswordDTO):
    email_norm = _normalize_email(body.email)
    if not email_norm:
        raise HTTPException(400, "请填写邮箱")
    _verify_and_consume_verification_code(email_norm, body.code)
    u = find_user_by_email(email_norm)
    if not u:
        raise HTTPException(404, "用户不存在")
    sf = get_session_factory()
    with sf() as session:
        row = session.query(User).filter(User.id == u.id).first()
        if not row:
            raise HTTPException(404, "用户不存在")
        row.password_hash = hash_password(body.new_password)
        session.commit()
    return {"ok": True}


class ProfileUpdateDTO(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)


class PasswordChangeDTO(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)


@router.put("/auth/profile")
def api_update_profile(body: ProfileUpdateDTO, user: User = Depends(_get_current_user)):
    un = (body.username or "").strip()
    sf = get_session_factory()
    with sf() as session:
        taken = session.query(User).filter(User.username == un, User.id != user.id).first()
        if taken:
            raise HTTPException(409, "用户名已被占用")
        row = session.query(User).filter(User.id == user.id).first()
        if not row:
            raise HTTPException(404, "用户不存在")
        row.username = un
        session.commit()
    return {"ok": True, "username": un}


@router.post("/auth/change-password")
def api_change_password(body: PasswordChangeDTO, user: User = Depends(_get_current_user)):
    sf = get_session_factory()
    with sf() as session:
        row = session.query(User).filter(User.id == user.id).first()
        if not row:
            raise HTTPException(404, "用户不存在")
        if not verify_password(body.current_password, row.password_hash):
            raise HTTPException(400, "当前密码不正确")
        row.password_hash = hash_password(body.new_password)
        session.commit()
    return {"ok": True}


@router.post("/admin/reset-user-password")
def api_admin_reset_user_password(
    body: AdminResetUserPasswordDTO,
    request: Request,
):
    """凭 ``MODSTORE_ADMIN_RECHARGE_TOKEN`` 重置用户密码；请求头 ``X-Modstore-Recharge-Token`` 与钱包直充一致。"""
    admin_token = (os.environ.get("MODSTORE_ADMIN_RECHARGE_TOKEN") or "").strip()
    if not admin_token:
        raise HTTPException(503, "未配置 MODSTORE_ADMIN_RECHARGE_TOKEN，无法执行管理员密码重置")
    client_token = (request.headers.get("X-Modstore-Recharge-Token") or "").strip()
    if client_token != admin_token:
        raise HTTPException(403, "无效的管理员授权")

    un = (body.username or "").strip()
    if not un:
        raise HTTPException(400, "请填写用户名")

    sf = get_session_factory()
    with sf() as session:
        row = session.query(User).filter(User.username == un).first()
        if not row:
            raise HTTPException(404, "用户不存在")
        row.password_hash = hash_password(body.new_password)
        session.commit()
    return {"ok": True}


@router.post("/auth/refresh")
def api_refresh_token(body: RefreshTokenDTO):
    """使用刷新令牌获取新的访问令牌"""
    refresh_token = body.refresh_token
    if not refresh_token:
        raise HTTPException(400, "缺少刷新令牌")
    
    payload = decode_refresh_token(refresh_token)
    if not payload:
        raise HTTPException(401, "刷新令牌无效或已过期")
    
    user_id = int(payload["sub"])
    username = payload["username"]
    
    # 验证用户是否存在
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "用户不存在")
    
    # 生成新的访问令牌和刷新令牌
    new_access_token = create_access_token(user_id, username)
    new_refresh_token = create_refresh_token(user_id, username)
    
    return {
        "ok": True,
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.get("/admin/status")
def api_admin_status(user: User = Depends(_require_admin)):
    """管理员状态检查。"""
    sf = get_session_factory()
    with sf() as session:
        total_items = session.query(CatalogItem).count()
        total_users = session.query(User).count()
        return {
            "ok": True,
            "is_admin": True,
            "total_catalog_items": total_items,
            "total_users": total_users,
        }


# ── Wallet endpoints ─────────────────────────────────────────


@router.get("/wallet/balance")
def api_wallet_balance(user: User = Depends(_get_current_user)):
    sf = get_session_factory()
    with sf() as session:
        wallet = session.query(Wallet).filter(Wallet.user_id == user.id).first()
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=0.0)
            session.add(wallet)
            session.commit()
        return {"balance": wallet.balance, "updated_at": wallet.updated_at.isoformat() if wallet.updated_at else ""}


@router.post("/wallet/recharge")
def api_wallet_recharge(
    body: RechargeDTO,
    request: Request,
    user: User = Depends(_get_current_user),
):
    """管理员线下直充（需密钥）。用户日常充值请使用「支付宝」在钱包页发起。"""
    admin_token = (os.environ.get("MODSTORE_ADMIN_RECHARGE_TOKEN") or "").strip()
    if not admin_token:
        raise HTTPException(503, "未配置 MODSTORE_ADMIN_RECHARGE_TOKEN，无法直充")
    client_token = (
        (request.headers.get("X-Modstore-Recharge-Token") or "").strip()
        or (body.recharge_token or "").strip()
    )
    if client_token != admin_token:
        raise HTTPException(403, "无效的充值授权")

    sf = get_session_factory()
    with sf() as session:
        wallet = (
            session.query(Wallet)
            .filter(Wallet.user_id == user.id)
            .with_for_update()
            .first()
        )
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


# ── Market catalog ───────────────────────────────────────────


@router.get("/market/facets")
def api_market_facets():
    """公开：返回市场中出现的行业、类型（artifact）、保密级取值，供商店页筛选。"""
    sf = get_session_factory()
    with sf() as session:
        pub = CatalogItem.is_public == True
        industries = sorted(
            {
                t[0]
                for t in session.query(CatalogItem.industry).filter(pub).distinct().all()
                if t[0]
            },
        )
        artifacts = sorted(
            {
                t[0]
                for t in session.query(CatalogItem.artifact).filter(pub).distinct().all()
                if t[0]
            },
        )
        security_levels = sorted(
            {
                t[0]
                for t in session.query(CatalogItem.security_level).filter(pub).distinct().all()
                if t[0]
            },
        )
        return {"industries": industries, "artifacts": artifacts, "security_levels": security_levels}


@router.get("/market/catalog")
def api_market_catalog(
    q: Optional[str] = Query(None),
    artifact: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    security_level: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: Optional[User] = Depends(lambda authorization=None: _get_current_user(authorization) if authorization else None),
):
    sf = get_session_factory()
    with sf() as session:
        query = session.query(CatalogItem).filter(CatalogItem.is_public == True)
        if q:
            ql = q.lower()
            query = query.filter(
                (CatalogItem.name.ilike(f"%{ql}%"))
                | (CatalogItem.pkg_id.ilike(f"%{ql}%"))
                | (CatalogItem.description.ilike(f"%{ql}%"))
            )
        if artifact:
            query = query.filter(CatalogItem.artifact == artifact)
        if industry:
            query = query.filter(CatalogItem.industry == industry)
        if security_level:
            query = query.filter(CatalogItem.security_level == security_level)
        total = query.count()
        rows = query.order_by(CatalogItem.created_at.desc()).offset(offset).limit(limit).all()

        purchased_ids = set()
        if user:
            purchased_rows = session.query(Purchase.catalog_id).filter(Purchase.user_id == user.id).all()
            purchased_ids = {r[0] for r in purchased_rows}

        return {
            "items": [
                {
                    "id": r.id,
                    "pkg_id": r.pkg_id,
                    "version": r.version,
                    "name": r.name,
                    "description": r.description,
                    "price": r.price,
                    "artifact": r.artifact,
                    "industry": getattr(r, "industry", None) or "通用",
                    "security_level": getattr(r, "security_level", None) or "personal",
                    "author_id": r.author_id,
                    "purchased": r.id in purchased_ids,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ],
            "total": total,
        }


@router.get("/market/catalog/{item_id}")
def api_market_catalog_detail(
    item_id: int,
    user: Optional[User] = Depends(lambda authorization=None: _get_current_user(authorization) if authorization else None),
):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        purchased = False
        favorited = False
        user_has_review = False
        if user:
            purchased = (
                session.query(Purchase)
                .filter(Purchase.user_id == user.id, Purchase.catalog_id == item.id)
                .first()
                is not None
            )
            favorited = (
                session.query(Favorite)
                .filter(Favorite.user_id == user.id, Favorite.catalog_id == item.id)
                .first()
                is not None
            )
            user_has_review = (
                session.query(Review)
                .filter(Review.user_id == user.id, Review.catalog_id == item.id)
                .first()
                is not None
            )
        return {
            "id": item.id,
            "pkg_id": item.pkg_id,
            "version": item.version,
            "name": item.name,
            "description": item.description,
            "price": item.price,
            "artifact": item.artifact,
            "industry": getattr(item, "industry", None) or "通用",
            "author_id": item.author_id,
            "purchased": purchased,
            "favorited": favorited,
            "user_has_review": user_has_review,
            "created_at": item.created_at.isoformat() if item.created_at else "",
        }


class ReviewSubmitDTO(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    content: str = Field(default="", max_length=4000)


@router.post("/market/catalog/{item_id}/review")
def api_submit_review(
    item_id: int,
    body: ReviewSubmitDTO,
    user: User = Depends(_get_current_user),
):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        ent = (
            session.query(Entitlement)
            .filter(
                Entitlement.user_id == user.id,
                Entitlement.catalog_id == item_id,
                Entitlement.is_active == True,
            )
            .first()
        )
        purchase = (
            session.query(Purchase).filter(Purchase.user_id == user.id, Purchase.catalog_id == item_id).first()
        )
        if not ent and not purchase:
            raise HTTPException(403, "购买后方可评价")
        exists = session.query(Review).filter(Review.user_id == user.id, Review.catalog_id == item_id).first()
        if exists:
            raise HTTPException(400, "已评价过")
        session.add(
            Review(
                user_id=user.id,
                catalog_id=item_id,
                rating=int(body.rating),
                content=(body.content or "").strip(),
            )
        )
        session.commit()
    return {"ok": True}


@router.get("/market/catalog/{item_id}/reviews")
def api_catalog_reviews(item_id: int):
    sf = get_session_factory()
    with sf() as session:
        rows = (
            session.query(Review, User)
            .join(User, Review.user_id == User.id)
            .filter(Review.catalog_id == item_id)
            .order_by(Review.created_at.desc())
            .limit(50)
            .all()
        )
        revs = [
            {
                "id": r.id,
                "user_name": u.username,
                "rating": r.rating,
                "content": r.content or "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r, u in rows
        ]
        avg = sum(x[0].rating for x in rows) / len(rows) if rows else 0.0
        return {"reviews": revs, "average_rating": round(avg, 2), "total": len(revs)}


@router.post("/market/catalog/{item_id}/favorite")
def api_toggle_favorite(item_id: int, user: User = Depends(_get_current_user)):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        existing = session.query(Favorite).filter(Favorite.user_id == user.id, Favorite.catalog_id == item_id).first()
        if existing:
            session.delete(existing)
            session.commit()
            return {"ok": True, "favorited": False}
        session.add(Favorite(user_id=user.id, catalog_id=item_id))
        session.commit()
        return {"ok": True, "favorited": True}


# ── Purchase ─────────────────────────────────────────────────


@router.post("/market/catalog/{item_id}/buy")
def api_buy_item(item_id: int, user: User = Depends(_get_current_user)):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        if item.price <= 0:
            existing = (
                session.query(Purchase)
                .filter(Purchase.user_id == user.id, Purchase.catalog_id == item.id)
                .first()
            )
            if existing:
                return {"ok": True, "message": "已拥有"}
            purchase = Purchase(user_id=user.id, catalog_id=item.id, amount=0)
            session.add(purchase)
            session.commit()
            return {"ok": True, "message": "免费领取成功"}

        existing = (
            session.query(Purchase)
            .filter(Purchase.user_id == user.id, Purchase.catalog_id == item.id)
            .first()
        )
        if existing:
            return {"ok": True, "message": "已拥有"}

        wallet = (
            session.query(Wallet)
            .filter(Wallet.user_id == user.id)
            .with_for_update()
            .first()
        )
        if not wallet:
            session.add(Wallet(user_id=user.id, balance=0.0))
            session.flush()
            wallet = (
                session.query(Wallet)
                .filter(Wallet.user_id == user.id)
                .with_for_update()
                .first()
            )
        if not wallet or wallet.balance < item.price:
            raise HTTPException(402, f"余额不足，需要 ¥{item.price}，当前 ¥{wallet.balance if wallet else 0}")

        wallet.balance -= item.price
        wallet.updated_at = datetime.now(timezone.utc)
        purchase = Purchase(user_id=user.id, catalog_id=item.id, amount=item.price)
        txn = Transaction(
            user_id=user.id,
            amount=-item.price,
            txn_type="purchase",
            status="completed",
            description=f"购买 {item.name} ({item.pkg_id})",
        )
        session.add(purchase)
        session.add(txn)
        session.commit()
        return {"ok": True, "message": "购买成功", "new_balance": wallet.balance}


@router.get("/market/catalog/{item_id}/download")
def api_download_item(item_id: int, user: User = Depends(_get_current_user)):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")
        if item.price > 0:
            purchased = (
                session.query(Purchase)
                .filter(Purchase.user_id == user.id, Purchase.catalog_id == item.id)
                .first()
            )
            if not purchased:
                raise HTTPException(403, "未购买此商品，请先购买后下载")
        if not item.stored_filename:
            raise HTTPException(404, "该商品无文件可下载")
        from modstore_server.catalog_store import files_dir
        from fastapi.responses import StreamingResponse

        path = files_dir() / item.stored_filename
        if not path.is_file():
            raise HTTPException(404, "文件缺失")
        
        # 流式下载大文件
        def generate():
            with open(path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk
        
        return StreamingResponse(
            generate(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={item.pkg_id}.zip",
                "Content-Length": str(path.stat().st_size)
            }
        )


# ── My store ─────────────────────────────────────────────────


@router.get("/my-store")
def api_my_store(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(_get_current_user),
):
    sf = get_session_factory()
    with sf() as session:
        total = session.query(Purchase).filter(Purchase.user_id == user.id).count()
        rows = (
            session.query(Purchase)
            .filter(Purchase.user_id == user.id)
            .order_by(Purchase.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        items = []
        for p in rows:
            item = session.query(CatalogItem).filter(CatalogItem.id == p.catalog_id).first()
            if item:
                items.append(
                    {
                        "purchase_id": p.id,
                        "catalog_id": item.id,
                        "pkg_id": item.pkg_id,
                        "version": item.version,
                        "name": item.name,
                        "artifact": item.artifact or "mod",
                        "price_paid": p.amount,
                        "purchased_at": p.created_at.isoformat() if p.created_at else "",
                    }
                )
        return {"items": items, "total": total}


# ── Admin: upload catalog item with file ─────────────────────


def _catalog_files_dir() -> Path:
    """市场文件存储目录。"""
    d = Path(__file__).resolve().parent / "market_files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _upload_chunks_dir() -> Path:
    """分块上传临时目录。"""
    d = Path(__file__).resolve().parent / "upload_chunks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _compute_sha256(file_path: Path) -> str:
    """计算文件 SHA256。"""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class UploadSession(BaseModel):
    """上传会话信息"""
    session_id: str
    file_name: str
    total_size: int
    chunk_size: int
    total_chunks: int


class UploadChunk(BaseModel):
    """文件块信息"""
    session_id: str
    chunk_index: int
    chunk_data: bytes


class CompleteUpload(BaseModel):
    """完成上传请求"""
    session_id: str
    pkg_id: str
    version: str
    name: str
    description: str = ""
    price: float = 0.0
    artifact: str = "mod"
    industry: str = "通用"


@router.post("/admin/catalog", summary="管理员上传 MOD 到市场（支持文件上传）")
async def api_admin_upload_catalog(
    pkg_id: str = Form(..., min_length=1, max_length=128),
    version: str = Form(..., min_length=1, max_length=32),
    name: str = Form(..., min_length=1, max_length=256),
    description: str = Form(""),
    price: float = Form(0, ge=0),
    artifact: str = Form("mod"),
    industry: str = Form("通用"),
    file: UploadFile = File(None),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        existing = session.query(CatalogItem).filter(
            CatalogItem.pkg_id == pkg_id, CatalogItem.version == version
        ).first()
        if existing:
            raise HTTPException(409, f"pkg_id '{pkg_id}' + version '{version}' 已存在")

        stored_filename = ""
        sha256 = ""

        if file and file.filename:
            suffix = Path(file.filename).suffix.lower()
            if suffix not in {".zip", ".xcmod", ".xcemp"}:
                raise HTTPException(400, "仅支持 .zip / .xcmod / .xcemp 格式")

            dest_dir = _catalog_files_dir()
            dest_name = f"{pkg_id}-{version}{suffix}"
            dest_path = dest_dir / dest_name

            content = await file.read()
            if len(content) > 100 * 1024 * 1024:
                raise HTTPException(400, "文件过大（>100MB）")

            dest_path.write_bytes(content)
            stored_filename = dest_name
            sha256 = _compute_sha256(dest_path)

        ind = (industry or "").strip() or "通用"
        item = CatalogItem(
            pkg_id=pkg_id,
            version=version,
            name=name,
            description=description,
            price=price,
            author_id=user.id,
            artifact=artifact,
            industry=ind,
            stored_filename=stored_filename,
            sha256=sha256,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return {
            "ok": True,
            "id": item.id,
            "pkg_id": item.pkg_id,
            "stored_filename": item.stored_filename,
        }


@router.post("/admin/catalog/sync-from-xc-packages", summary="从 XC catalog_store 同步缺失条目到市场库")
def api_admin_sync_xc_catalog_packages(user: User = Depends(_require_admin)):
    """将 ``packages.json`` 中尚未出现在 ``catalog_items`` 的包插入数据库（可选复制文件）。"""
    sf = get_session_factory()
    with sf() as session:
        out = catalog_sync.sync_packages_json_to_catalog_items(session, admin_user_id=user.id)
        session.commit()
    return {"ok": True, **out}


@router.get("/admin/catalog")
def api_admin_list_catalog(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        total = session.query(CatalogItem).count()
        rows = session.query(CatalogItem).order_by(CatalogItem.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "items": [
                {
                    "id": r.id,
                    "pkg_id": r.pkg_id,
                    "version": r.version,
                    "name": r.name,
                    "description": r.description,
                    "price": r.price,
                    "artifact": r.artifact,
                    "industry": getattr(r, "industry", None) or "通用",
                    "stored_filename": r.stored_filename,
                    "sha256": r.sha256,
                    "is_public": r.is_public,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ],
            "total": total,
        }


@router.post("/admin/upload/initiate", summary="初始化分块上传")
def api_initiate_upload(
    file_name: str = Form(...),
    total_size: int = Form(...),
    chunk_size: int = Form(...),
    user: User = Depends(_require_admin),
):
    """初始化分块上传会话"""
    import uuid
    session_id = str(uuid.uuid4())
    total_chunks = (total_size + chunk_size - 1) // chunk_size
    
    # 创建上传会话目录
    session_dir = _upload_chunks_dir() / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # 存储会话信息
    session_info = {
        "session_id": session_id,
        "file_name": file_name,
        "total_size": total_size,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "created_at": datetime.utcnow().isoformat()
    }
    
    with open(session_dir / "session.json", "w", encoding="utf-8") as f:
        json.dump(session_info, f)
    
    return {
        "ok": True,
        "session_id": session_id,
        "total_chunks": total_chunks
    }


@router.post("/admin/upload/chunk", summary="上传文件块")
async def api_upload_chunk(
    session_id: str = Form(...),
    chunk_index: int = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(_require_admin),
):
    """上传单个文件块"""
    session_dir = _upload_chunks_dir() / session_id
    if not session_dir.exists():
        raise HTTPException(404, "上传会话不存在")
    
    # 读取会话信息
    with open(session_dir / "session.json", "r", encoding="utf-8") as f:
        session_info = json.load(f)
    
    if chunk_index >= session_info["total_chunks"]:
        raise HTTPException(400, "无效的块索引")
    
    # 保存文件块
    chunk_path = session_dir / f"chunk_{chunk_index}"
    content = await file.read()
    
    with open(chunk_path, "wb") as f:
        f.write(content)
    
    return {"ok": True, "chunk_index": chunk_index}


@router.post("/admin/upload/complete", summary="完成分块上传")
def api_complete_upload(
    session_id: str = Form(...),
    pkg_id: str = Form(...),
    version: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    price: float = Form(0.0),
    artifact: str = Form("mod"),
    industry: str = Form("通用"),
    user: User = Depends(_require_admin),
):
    """完成分块上传并合并文件"""
    session_dir = _upload_chunks_dir() / session_id
    if not session_dir.exists():
        raise HTTPException(404, "上传会话不存在")
    
    # 读取会话信息
    with open(session_dir / "session.json", "r", encoding="utf-8") as f:
        session_info = json.load(f)
    
    # 检查所有块是否上传完成
    missing_chunks = []
    for i in range(session_info["total_chunks"]):
        chunk_path = session_dir / f"chunk_{i}"
        if not chunk_path.exists():
            missing_chunks.append(i)
    
    if missing_chunks:
        raise HTTPException(400, f"缺少文件块: {missing_chunks}")
    
    # 合并文件
    suffix = Path(session_info["file_name"]).suffix.lower()
    if suffix not in {".zip", ".xcmod", ".xcemp"}:
        raise HTTPException(400, "仅支持 .zip / .xcmod / .xcemp 格式")
    
    dest_dir = _catalog_files_dir()
    dest_name = f"{pkg_id}-{version}{suffix}"
    dest_path = dest_dir / dest_name
    
    # 合并所有块
    with open(dest_path, "wb") as out_file:
        for i in range(session_info["total_chunks"]):
            chunk_path = session_dir / f"chunk_{i}"
            with open(chunk_path, "rb") as in_file:
                out_file.write(in_file.read())
    
    # 计算文件哈希
    sha256 = _compute_sha256(dest_path)
    
    # 清理临时文件
    import shutil
    shutil.rmtree(session_dir)
    
    # 保存到数据库
    sf = get_session_factory()
    with sf() as session:
        existing = session.query(CatalogItem).filter(
            CatalogItem.pkg_id == pkg_id, CatalogItem.version == version
        ).first()
        if existing:
            raise HTTPException(409, f"pkg_id '{pkg_id}' + version '{version}' 已存在")
        
        ind = (industry or "").strip() or "通用"
        item = CatalogItem(
            pkg_id=pkg_id,
            version=version,
            name=name,
            description=description,
            price=price,
            author_id=user.id,
            artifact=artifact,
            industry=ind,
            stored_filename=dest_name,
            sha256=sha256,
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        
        return {
            "ok": True,
            "id": item.id,
            "pkg_id": item.pkg_id,
            "stored_filename": item.stored_filename,
            "file_size": session_info["total_size"]
        }


@router.delete("/admin/catalog/{item_id}")
def api_admin_delete_catalog(item_id: int, user: User = Depends(_require_admin)):
    sf = get_session_factory()
    with sf() as session:
        item = session.query(CatalogItem).filter(CatalogItem.id == item_id).first()
        if not item:
            raise HTTPException(404, "商品不存在")

        if item.stored_filename:
            file_path = _catalog_files_dir() / item.stored_filename
            if file_path.is_file():
                file_path.unlink()

        session.delete(item)
        session.commit()
        return {"ok": True, "deleted_id": item_id}


@router.get("/admin/users")
def api_admin_list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        total = session.query(User).count()
        rows = session.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "users": [
                {
                    "id": r.id,
                    "username": r.username,
                    "email": r.email,
                    "is_admin": r.is_admin,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ],
            "total": total,
        }


@router.put("/admin/users/{user_id}/admin")
def api_admin_set_admin_status(
    user_id: int,
    is_admin: bool = Query(...),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        target = session.query(User).filter(User.id == user_id).first()
        if not target:
            raise HTTPException(404, "用户不存在")
        target.is_admin = is_admin
        session.commit()
        return {"ok": True, "user_id": user_id, "is_admin": is_admin}


@router.get("/admin/wallets")
def api_admin_list_wallets(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        total = session.query(Wallet).count()
        rows = session.query(Wallet).order_by(Wallet.id).offset(offset).limit(limit).all()
        return {
            "items": [
                {
                    "id": w.id,
                    "user_id": w.user_id,
                    "balance": w.balance,
                    "updated_at": w.updated_at.isoformat() if w.updated_at else "",
                }
                for w in rows
            ],
            "total": total,
        }


@router.get("/admin/transactions")
def api_admin_list_transactions(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(_require_admin),
):
    sf = get_session_factory()
    with sf() as session:
        total = session.query(Transaction).count()
        rows = (
            session.query(Transaction)
            .order_by(Transaction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "items": [
                {
                    "id": t.id,
                    "user_id": t.user_id,
                    "amount": t.amount,
                    "txn_type": t.txn_type,
                    "status": t.status,
                    "description": t.description,
                    "created_at": t.created_at.isoformat() if t.created_at else "",
                }
                for t in rows
            ],
            "total": total,
        }


# ── Init on import ──────────────────────────────────────────

init_db()
