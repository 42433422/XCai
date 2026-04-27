"""XC AGI 用户认证服务：注册、登录、JWT，以及 Personal Access Token (PAT) 工具。"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
import jwt
from sqlalchemy import func

from modstore_server.models import DeveloperToken, User, Wallet, get_session_factory

_JWT_SECRET = os.environ.get("MODSTORE_JWT_SECRET", "modstore-dev-secret-change-in-prod")
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_HOURS = 72
_JWT_REFRESH_EXPIRE_DAYS = int(os.environ.get("MODSTORE_JWT_REFRESH_EXPIRE_DAYS", "30"))


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
    # 兼容历史 token（无 type 字段）：默认按 access 处理；显式标 refresh 的不走这里。
    token_type = payload.get("type")
    if token_type and token_type != "access":
        return None
    return payload


def create_refresh_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=_JWT_REFRESH_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def decode_refresh_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
    if payload.get("type") != "refresh":
        return None
    return payload


def register_user(username: str, password: str, email: str = "") -> User:
    email_clean = (email or "").strip().lower() or ""
    sf = get_session_factory()
    with sf() as session:
        existing = session.query(User).filter(User.username == username).first()
        if existing:
            raise ValueError("用户名已存在")
        if email_clean:
            taken = session.query(User).filter(func.lower(User.email) == email_clean).first()
            if taken:
                raise ValueError("该邮箱已被注册")
        user = User(
            username=username,
            email=email_clean if email_clean else None,
            password_hash=hash_password(password),
        )
        session.add(user)
        session.flush()
        wallet = Wallet(user_id=user.id, balance=0.0)
        session.add(wallet)
        session.commit()
        session.refresh(user)
        return user


def authenticate_user(username: str, password: str) -> Optional[User]:
    sf = get_session_factory()
    with sf() as session:
        user = session.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user


def get_user_by_id(user_id: int) -> Optional[User]:
    sf = get_session_factory()
    with sf() as session:
        return session.query(User).filter(User.id == user_id).first()


# ----- Personal Access Token (PAT) -----------------------------------------

PAT_PREFIX = "pat_"
_PAT_BODY_LEN = 32  # base32hex 字符数；安全度 ≈ 160 bit


def hash_pat(raw_token: str) -> str:
    """sha256 反向哈希 (hex)，DB 端唯一索引。"""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_pat() -> Tuple[str, str, str]:
    """生成一个 PAT，返回 (raw_token, prefix, sha256_hex)。

    raw_token 仅一次性返回给客户端，prefix 用于 UI 掩码展示 (例：``pat_AbCdEf12``)。
    """
    body = secrets.token_urlsafe(_PAT_BODY_LEN)[:_PAT_BODY_LEN]
    raw = f"{PAT_PREFIX}{body}"
    prefix = raw[: len(PAT_PREFIX) + 8]
    return raw, prefix, hash_pat(raw)


def resolve_user_from_pat(raw_token: str) -> Optional[User]:
    """按 PAT 反查用户；非 ``pat_`` 前缀直接返回 None。

    命中后异步更新 ``last_used_at``。已吊销 / 已过期的 token 视为无效。
    """
    raw = (raw_token or "").strip()
    if not raw.startswith(PAT_PREFIX):
        return None
    digest = hash_pat(raw)

    sf = get_session_factory()
    with sf() as session:
        row = (
            session.query(DeveloperToken)
            .filter(
                DeveloperToken.token_hash == digest,
                DeveloperToken.revoked_at.is_(None),
            )
            .first()
        )
        if not row:
            return None
        if row.expires_at and row.expires_at < datetime.utcnow():
            return None
        user = session.query(User).filter(User.id == row.user_id).first()
        if not user:
            return None
        # 写一次 last_used_at（容忍并发竞态：单字段 UPDATE 安全）
        try:
            row.last_used_at = datetime.utcnow()
            session.commit()
        except Exception:
            session.rollback()
        return user
