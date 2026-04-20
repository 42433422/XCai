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
    decode_access_token,
    get_user_by_id,
    register_user,
)
from modstore_server.email_service import (
    assert_email_outbound_configured,
    find_user_by_email,
    generate_verification_code,
    send_verification_email,
)
from modstore_server.models import (
    CatalogItem,
    Purchase,
    Transaction,
    User,
    VerificationCode,
    Wallet,
    get_session_factory,
    init_db,
)

router = APIRouter(prefix="/api", tags=["market"])

# ── Auth helpers ──────────────────────────────────────────────


def _get_current_user(authorization: Optional[str] = Header(None)) -> User:
    raw = (authorization or "").strip()
    if not raw.startswith("Bearer "):
        raise HTTPException(401, "缺少认证凭证")
    token = raw[7:]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401, "凭证无效或已过期")
    user_id = int(payload["sub"])
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "用户不存在")
    return user


def _require_admin(user: User = Depends(_get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return user


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
    token = create_access_token(user.id, user.username)
    return {
        "ok": True,
        "token": token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.post("/auth/login")
def api_login(body: LoginDTO):
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    token = create_access_token(user.id, user.username)
    return {
        "ok": True,
        "token": token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.get("/auth/me")
def api_me(user: User = Depends(_get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat() if user.created_at else "",
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

    token = create_access_token(user.id, user.username)
    return {
        "ok": True,
        "token": token,
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
        wallet = session.query(Wallet).filter(Wallet.user_id == user.id).first()
        if not wallet:
            wallet = Wallet(user_id=user.id, balance=0.0)
            session.add(wallet)
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
    """公开：返回市场中出现的行业、类型（artifact）取值，供商店页筛选。"""
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
        return {"industries": industries, "artifacts": artifacts}


@router.get("/market/catalog")
def api_market_catalog(
    q: Optional[str] = Query(None),
    artifact: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
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
        if user:
            purchased = (
                session.query(Purchase)
                .filter(Purchase.user_id == user.id, Purchase.catalog_id == item.id)
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
            "created_at": item.created_at.isoformat() if item.created_at else "",
        }


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

        wallet = session.query(Wallet).filter(Wallet.user_id == user.id).first()
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
        from fastapi.responses import FileResponse

        path = files_dir() / item.stored_filename
        if not path.is_file():
            raise HTTPException(404, "文件缺失")
        return FileResponse(path, filename=item.pkg_id + ".zip", media_type="application/zip")


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


def _compute_sha256(file_path: Path) -> str:
    """计算文件 SHA256。"""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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
