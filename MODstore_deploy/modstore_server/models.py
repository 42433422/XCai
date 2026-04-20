"""XC AGI 在线市场数据库模型（SQLite + SQLAlchemy）。"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

class Base(DeclarativeBase):
    pass


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(128), nullable=False, index=True)
    code = Column(String(8), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=True)
    password_hash = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    txn_type = Column(String(32), nullable=False)
    status = Column(String(16), default="completed")
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pkg_id = Column(String(128), unique=True, nullable=False, index=True)
    version = Column(String(32), nullable=False)
    name = Column(String(256), nullable=False)
    description = Column(Text, default="")
    price = Column(Float, default=0.0)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    artifact = Column(String(32), default="mod")
    stored_filename = Column(String(256), default="")
    sha256 = Column(String(64), default="")
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    catalog_id = Column(Integer, ForeignKey("catalog_items.id"), nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserMod(Base):
    """用户与本地 MOD 的关联表。"""

    __tablename__ = "user_mods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mod_id = Column(String(128), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def default_db_path() -> Path:
    raw = (os.environ.get("MODSTORE_DB_PATH") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent / "modstore.db"


_engine = None
_SessionFactory = None


def get_engine(db_path: Optional[Path] = None):
    global _engine
    if _engine is None:
        p = db_path or default_db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{p}", echo=False)
    return _engine


def get_session_factory(db_path: Optional[Path] = None):
    global _SessionFactory
    if _SessionFactory is None:
        engine = get_engine(db_path)
        _SessionFactory = sessionmaker(bind=engine)
    return _SessionFactory


def init_db(db_path: Optional[Path] = None):
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)


def add_user_mod(user_id: int, mod_id: str) -> UserMod:
    """添加用户与 MOD 的关联。"""
    sf = get_session_factory()
    with sf() as session:
        existing = session.query(UserMod).filter(
            UserMod.user_id == user_id, UserMod.mod_id == mod_id
        ).first()
        if existing:
            return existing
        user_mod = UserMod(user_id=user_id, mod_id=mod_id)
        session.add(user_mod)
        session.commit()
        session.refresh(user_mod)
        return user_mod


def remove_user_mod(user_id: int, mod_id: str) -> bool:
    """删除用户与 MOD 的关联。"""
    sf = get_session_factory()
    with sf() as session:
        user_mod = session.query(UserMod).filter(
            UserMod.user_id == user_id, UserMod.mod_id == mod_id
        ).first()
        if user_mod:
            session.delete(user_mod)
            session.commit()
            return True
        return False


def get_user_mod_ids(user_id: int) -> list[str]:
    """获取用户拥有的所有 MOD ID 列表。"""
    sf = get_session_factory()
    with sf() as session:
        rows = session.query(UserMod.mod_id).filter(UserMod.user_id == user_id).all()
        return [r[0] for r in rows]


def user_owns_mod(user_id: int, mod_id: str) -> bool:
    """检查用户是否拥有指定 MOD。"""
    sf = get_session_factory()
    with sf() as session:
        return session.query(UserMod).filter(
            UserMod.user_id == user_id, UserMod.mod_id == mod_id
        ).first() is not None
