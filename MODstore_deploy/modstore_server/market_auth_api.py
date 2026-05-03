"""XC AGI 在线市场 API：认证、注册、登录、公开联系表单。"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from modstore_server.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
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
from modstore_server import account_level_service
from modstore_server.java_me_profile import fetch_java_user_overlay
from modstore_server.models import (
    CatalogItem,
    LandingContactSubmission,
    User,
    VerificationCode,
    get_session_factory,
)
from modstore_server.market_shared import (
    _get_current_user,
    _public_contact_client_key,
    _public_contact_rate_allow,
    _require_admin,
)

router = APIRouter(tags=["market"])


class PublicContactDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    email: str = Field(..., min_length=4, max_length=256)
    phone: str = Field("", max_length=64)
    company: str = Field("", max_length=256)
    message: str = Field("", max_length=8000)
    source: str = Field("home", max_length=64)


@router.post("/public/contact", summary="落地页联系表单（匿名，入库）")
def api_public_contact_submit(body: PublicContactDTO, request: Request):
    from modstore_server.market_shared import _CONTACT_EMAIL_RE

    email = (body.email or "").strip()
    if not _CONTACT_EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    _public_contact_rate_allow(_public_contact_client_key(request))
    meta = {
        "user_agent": (request.headers.get("user-agent") or "")[:512],
        "referer": (request.headers.get("referer") or "")[:512],
    }
    row = LandingContactSubmission(
        name=(body.name or "").strip()[:128],
        email=email[:256],
        phone=(body.phone or "").strip()[:64],
        company=(body.company or "").strip()[:256],
        message=(body.message or "").strip()[:8000],
        source=(body.source or "home").strip()[:64] or "home",
        meta_json=json.dumps(meta, ensure_ascii=False),
    )
    sf = get_session_factory()
    with sf() as session:
        session.add(row)
        session.commit()
        new_id = row.id
    return {"ok": True, "id": new_id}


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
    username: str = Field(..., min_length=1, max_length=64)
    new_password: str = Field(..., min_length=6, max_length=128)


class ProfileUpdateDTO(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)


class PasswordChangeDTO(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)


def _normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _delete_unused_verification_code(email: str, code: str) -> None:
    sf = get_session_factory()
    with sf() as session:
        session.query(VerificationCode).filter(
            VerificationCode.email == email,
            VerificationCode.code == code,
            VerificationCode.used == False,
        ).delete(synchronize_session=False)
        session.commit()


def _background_send_verification_email(email: str, code: str, purpose: str) -> None:
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
    access_token = create_access_token(user.id, user.username, is_admin=bool(user.is_admin))
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
    access_token = create_access_token(user.id, user.username, is_admin=bool(user.is_admin))
    refresh_token = create_refresh_token(user.id, user.username)
    return {
        "ok": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.get("/auth/me")
def api_me(request: Request, user: User = Depends(_get_current_user)):
    exp = int(getattr(user, "experience", 0) or 0)
    level_profile = account_level_service.build_level_profile(exp).to_dict()
    phone_out = (getattr(user, "phone", None) or "") or ""
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    overlay = fetch_java_user_overlay(auth_header, expect_user_id=int(user.id))
    if overlay is not None:
        exp = int(overlay.experience)
        if isinstance(overlay.level_profile, dict) and overlay.level_profile:
            level_profile = overlay.level_profile
        else:
            level_profile = account_level_service.build_level_profile(exp).to_dict()
        if overlay.phone:
            phone_out = overlay.phone
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "phone": phone_out,
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

    access_token = create_access_token(user.id, user.username, is_admin=bool(user.is_admin))
    refresh_token = create_refresh_token(user.id, user.username)
    return {
        "ok": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.post("/auth/send-reset-password-code", status_code=202)
def api_send_reset_password_code(body: SendCodeDTO, background_tasks: BackgroundTasks):
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
    refresh_token = body.refresh_token
    if not refresh_token:
        raise HTTPException(400, "缺少刷新令牌")

    payload = decode_refresh_token(refresh_token)
    if not payload:
        raise HTTPException(401, "刷新令牌无效或已过期")

    user_id = int(payload["sub"])
    username = payload["username"]

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "用户不存在")

    new_access_token = create_access_token(user_id, username, is_admin=bool(user.is_admin))
    new_refresh_token = create_refresh_token(user_id, username)

    return {
        "ok": True,
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "user": {"id": user.id, "username": user.username, "email": user.email},
    }


@router.get("/admin/status")
def api_admin_status(user: User = Depends(_require_admin)):
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
