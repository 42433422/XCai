from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

from .models_base import Base


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pkg_id = Column(String(128), unique=True, nullable=False, index=True)
    version = Column(String(32), nullable=False)
    name = Column(String(256), nullable=False)
    description = Column(Text, default="")
    price = Column(Numeric(12, 2), default=0)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    artifact = Column(String(32), default="mod", index=True)
    industry = Column(String(64), default="通用")
    stored_filename = Column(String(256), default="")
    sha256 = Column(String(64), default="")
    is_public = Column(Boolean, default=True)
    security_level = Column(String(32), default="personal")
    industry_code = Column(String(16), default="")
    industry_secondary = Column(String(64), default="")
    description_embedding = Column(Text, default="")
    template_category = Column(String(32), default="", index=True)
    template_difficulty = Column(String(16), default="")
    install_count = Column(Integer, default=0)
    graph_snapshot = Column(Text, default="")
    material_category = Column(String(64), default="", index=True)
    license_scope = Column(String(32), default="personal", index=True)
    origin_type = Column(String(32), default="original", index=True)
    ip_risk_level = Column(String(16), default="low", index=True)
    compliance_status = Column(String(32), default="approved", index=True)
    rank_score = Column(Float, default=100.0, index=True)
    delist_reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class UserMod(Base):
    """用户与本地 MOD 的关联表。"""

    __tablename__ = "user_mods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mod_id = Column(String(128), nullable=False, index=True)
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


class CatalogComplaint(Base):
    __tablename__ = "catalog_complaints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    catalog_id = Column(Integer, ForeignKey("catalog_items.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    complaint_type = Column(String(32), default="other", index=True)
    reason = Column(Text, default="")
    evidence_json = Column(Text, default="{}")
    status = Column(String(24), default="pending", index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    admin_note = Column(Text, default="")
    resolution = Column(String(32), default="", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "catalog_id", name="uq_favorite_user_catalog"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    catalog_id = Column(Integer, ForeignKey("catalog_items.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AiModelPrice(Base):
    __tablename__ = "ai_model_prices"
    __table_args__ = (UniqueConstraint("provider", "model", name="uq_ai_model_price"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(256), nullable=False, index=True)
    label = Column(String(256), default="")
    input_price_per_1k = Column(Numeric(12, 6), default=0)
    output_price_per_1k = Column(Numeric(12, 6), default=0)
    min_charge = Column(Numeric(12, 2), default=0.01)
    enabled = Column(Boolean, default=True, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LlmModelCapability(Base):
    """L1 探针 / L3 人审状态；与目录中的 (provider, model) 对齐。"""

    __tablename__ = "llm_model_capabilities"
    __table_args__ = (UniqueConstraint("provider", "model", name="uq_llm_model_cap"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(256), nullable=False, index=True)
    l1_status = Column(String(32), default="pending", index=True)
    l1_score = Column(Float, nullable=True)
    l1_at = Column(DateTime, nullable=True)
    l1_flags_json = Column(Text, default="{}")
    l1_error = Column(Text, default="")
    effective_category = Column(String(32), default="")
    taxonomy_source = Column(String(32), default="heuristic")
    l3_status = Column(String(32), default="none", index=True)
    l3_notes = Column(Text, default="")
    l3_reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    l3_at = Column(DateTime, nullable=True)
    cs_ticket_id = Column(
        Integer, ForeignKey("customer_service_tickets.id"), nullable=True, index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
