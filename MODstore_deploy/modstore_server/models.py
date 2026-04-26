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
    UniqueConstraint,
    JSON,
    create_engine,
    text,
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
    default_llm_json = Column(Text, default="")


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
    industry = Column(String(64), default="通用")
    stored_filename = Column(String(256), default="")
    sha256 = Column(String(64), default="")
    is_public = Column(Boolean, default=True)
    security_level = Column(String(32), default="personal")
    industry_code = Column(String(16), default="")
    industry_secondary = Column(String(64), default="")
    description_embedding = Column(Text, default="")
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


class Workflow(Base):
    """工作流模型"""

    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowNode(Base):
    """工作流节点模型"""

    __tablename__ = "workflow_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    node_type = Column(String(64), nullable=False)  # start, end, employee, condition, etc.
    name = Column(String(256), nullable=False)
    config = Column(Text, default="{}")  # JSON configuration
    position_x = Column(Float, default=0.0)
    position_y = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowEdge(Base):
    """工作流边模型"""

    __tablename__ = "workflow_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    source_node_id = Column(Integer, ForeignKey("workflow_nodes.id"), nullable=False)
    target_node_id = Column(Integer, ForeignKey("workflow_nodes.id"), nullable=False)
    condition = Column(Text, default="")  # Optional condition for the edge
    created_at = Column(DateTime, default=datetime.utcnow)


class UserLlmCredential(Base):
    """用户 BYOK：各 provider 的 API Key（Fernet 密文）与可选 base_url。"""

    __tablename__ = "user_llm_credentials"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_llm_provider"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False)
    api_key_encrypted = Column(Text, nullable=False, default="")
    base_url_encrypted = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowExecution(Base):
    """工作流执行记录模型"""

    __tablename__ = "workflow_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(32), default="pending")  # pending, running, completed, failed
    input_data = Column(Text, default="{}")  # JSON input data
    output_data = Column(Text, default="{}")  # JSON output data
    error_message = Column(Text, default="")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class PlanTemplate(Base):
    __tablename__ = "plan_templates"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    price = Column(Float, default=0.0)
    features_json = Column(Text, default="[]")
    quotas_json = Column(Text, default="{}")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserPlan(Base):
    __tablename__ = "user_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(String(64), ForeignKey("plan_templates.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Quota(Base):
    __tablename__ = "quotas"
    __table_args__ = (UniqueConstraint("user_id", "quota_type", name="uq_user_quota_type"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quota_type = Column(String(64), nullable=False, index=True)
    total = Column(Integer, default=0)
    used = Column(Integer, default=0)
    reset_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Entitlement(Base):
    __tablename__ = "entitlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    catalog_id = Column(Integer, ForeignKey("catalog_items.id"), nullable=True, index=True)
    entitlement_type = Column(String(32), nullable=False, index=True)  # plan/employee/mod
    source_order_id = Column(String(64), default="", index=True)
    metadata_json = Column(Text, default="{}")
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)


class EmployeeExecutionMetric(Base):
    __tablename__ = "employee_execution_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    employee_id = Column(String(128), nullable=False, index=True)
    task = Column(String(128), default="")
    status = Column(String(32), default="success")
    duration_ms = Column(Float, default=0.0)
    llm_tokens = Column(Integer, default=0)
    error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowTrigger(Base):
    __tablename__ = "workflow_triggers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    trigger_type = Column(String(32), nullable=False, index=True)  # cron/webhook/event
    trigger_key = Column(String(128), default="", index=True)
    config_json = Column(Text, default="{}")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kind = Column("type", String(32), nullable=False)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    data_json = Column(Text, default="{}")
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "catalog_id", name="uq_review_user_catalog"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    catalog_id = Column(Integer, ForeignKey("catalog_items.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "catalog_id", name="uq_favorite_user_catalog"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    catalog_id = Column(Integer, ForeignKey("catalog_items.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    order_no = Column(String(64), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(16), default="pending", index=True)
    admin_note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


def _sqlite_add_column_if_missing(engine, table: str, column: str, ddl_type: str) -> None:
    """SQLite 表结构演进：缺列时 ALTER ADD（幂等）。"""
    with engine.begin() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        if any(row[1] == column for row in rows):
            return
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))


def init_db(db_path: Optional[Path] = None):
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    try:
        _sqlite_add_column_if_missing(engine, "catalog_items", "industry", "TEXT DEFAULT '通用'")
    except Exception:
        pass
    try:
        _sqlite_add_column_if_missing(engine, "users", "default_llm_json", "TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        _sqlite_add_column_if_missing(engine, "catalog_items", "security_level", "TEXT DEFAULT 'personal'")
    except Exception:
        pass
    try:
        _sqlite_add_column_if_missing(engine, "catalog_items", "industry_code", "TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        _sqlite_add_column_if_missing(engine, "catalog_items", "industry_secondary", "TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        _sqlite_add_column_if_missing(engine, "catalog_items", "description_embedding", "TEXT DEFAULT ''")
    except Exception:
        pass
    init_default_plan_templates()


def init_default_plan_templates() -> None:
    defaults = [
        {
            "id": "plan_basic",
            "name": "基础版 MOD",
            "description": "包含基础数据处理和1个 AI 员工",
            "price": 9.90,
            "features_json": '["基础数据库","字段管理","1个 AI 员工"]',
            "quotas_json": '{"employee_count":1,"llm_calls":5000,"storage_mb":512}',
        },
        {
            "id": "plan_pro",
            "name": "专业版 MOD",
            "description": "完整工作流能力 + 3个 AI 员工",
            "price": 29.90,
            "features_json": '["高级数据库","流程规则","自动化处理","3个 AI 员工","报表导出"]',
            "quotas_json": '{"employee_count":3,"llm_calls":30000,"storage_mb":2048}',
        },
        {
            "id": "plan_enterprise",
            "name": "企业版 MOD",
            "description": "不限 AI 员工 + 专属部署支持",
            "price": 99.90,
            "features_json": '["全部功能","不限 AI 员工","专属部署","优先技术支持","自定义域名"]',
            "quotas_json": '{"employee_count":999999,"llm_calls":300000,"storage_mb":10240}',
        },
    ]
    sf = get_session_factory()
    with sf() as session:
        for row in defaults:
            exists = session.query(PlanTemplate).filter(PlanTemplate.id == row["id"]).first()
            if exists:
                continue
            session.add(PlanTemplate(**row))
        session.commit()


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
