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
    phone = Column(String(32), unique=True, nullable=True, index=True)
    password_hash = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    default_llm_json = Column(Text, default="")
    experience = Column(Integer, default=0, nullable=False)


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
    artifact = Column(String(32), default="mod", index=True)
    industry = Column(String(64), default="通用")
    stored_filename = Column(String(256), default="")
    sha256 = Column(String(64), default="")
    is_public = Column(Boolean, default=True)
    security_level = Column(String(32), default="personal")
    industry_code = Column(String(16), default="")
    industry_secondary = Column(String(64), default="")
    description_embedding = Column(Text, default="")
    # M3 模板市场扩展（artifact='workflow_template' 时使用）
    template_category = Column(String(32), default="", index=True)
    template_difficulty = Column(String(16), default="")
    install_count = Column(Integer, default=0)
    graph_snapshot = Column(Text, default="")
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


class OpenApiConnector(Base):
    """第三方 OpenAPI 连接器：解析后的服务清单，对应一份 OpenAPI 3.x 文档。

    生成产物（受控 Python client）落到 ``data/generated_connectors/{id}/{version}/``。
    """

    __tablename__ = "openapi_connectors"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_openapi_connector_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    base_url = Column(String(512), default="")
    spec_hash = Column(String(64), default="", index=True)
    spec_version = Column(String(32), default="")
    title = Column(String(256), default="")
    status = Column(String(32), default="ready", index=True)  # ready | error | disabled
    generated_version = Column(Integer, default=0)
    operation_count = Column(Integer, default=0)
    last_error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OpenApiOperation(Base):
    """从 OpenAPI 文档解析出来的可调用 operation。"""

    __tablename__ = "openapi_operations"
    __table_args__ = (
        UniqueConstraint("connector_id", "operation_id", name="uq_openapi_operation_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    connector_id = Column(
        Integer, ForeignKey("openapi_connectors.id"), nullable=False, index=True
    )
    operation_id = Column(String(128), nullable=False)
    method = Column(String(16), nullable=False)
    path = Column(String(512), nullable=False)
    summary = Column(String(512), default="")
    tags = Column(Text, default="[]")
    request_schema = Column(Text, default="{}")
    response_schema = Column(Text, default="{}")
    generated_symbol = Column(String(128), default="")
    enabled = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OpenApiCredential(Base):
    """连接器鉴权配置：复用 Fernet 主密钥，加密各类 token / api_key / basic / oauth。

    auth_type ∈ {none, api_key, bearer, basic, oauth2_client_credentials}
    config_encrypted 是 JSON 序列化后的密文（不存任何明文敏感字段）。
    """

    __tablename__ = "openapi_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "connector_id", name="uq_openapi_credential_owner"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    connector_id = Column(
        Integer, ForeignKey("openapi_connectors.id"), nullable=False, index=True
    )
    auth_type = Column(String(32), nullable=False, default="none")
    config_encrypted = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OpenApiCallLog(Base):
    """连接器调用记录：用于审计和问题定位，敏感 header / 大响应体均已脱敏/截断。"""

    __tablename__ = "openapi_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    connector_id = Column(
        Integer, ForeignKey("openapi_connectors.id"), nullable=False, index=True
    )
    operation_id = Column(String(128), nullable=False, index=True)
    method = Column(String(16), default="")
    path = Column(String(512), default="")
    status_code = Column(Integer, nullable=True)
    duration_ms = Column(Float, default=0.0)
    request_summary = Column(Text, default="")
    response_summary = Column(Text, default="")
    error = Column(Text, default="")
    source = Column(String(32), default="manual", index=True)  # manual | workflow | employee
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


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


class WebhookSubscription(Base):
    """开发者级 Webhook 出站订阅。

    每个用户可创建多条订阅，按事件名匹配（``["*"]`` 表示订阅所有事件）。
    ``secret_encrypted`` 用 Fernet（``llm_crypto``）加密保存，签名时解出
    用于 HMAC-SHA256 计算（行为对齐 ``webhook_dispatcher._signature``）。
    """

    __tablename__ = "webhook_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False, default="")
    description = Column(Text, default="")
    target_url = Column(String(1024), nullable=False)
    secret_encrypted = Column(Text, nullable=False, default="")
    enabled_events_json = Column(Text, default='["*"]')
    is_active = Column(Boolean, default=True, index=True)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_delivery_at = Column(DateTime, nullable=True)
    last_delivery_status = Column(String(32), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebhookDelivery(Base):
    """单次 Webhook 投递记录，用于审计和手动重试。

    与 ``webhook_dispatcher`` 落盘到磁盘的 ``webhook_events/*.json`` 区别：
    后者是默认全局 URL 投递的"事件存档"，仅按 event_id 一份；
    这里按 (subscription, attempt) 维度记录，便于开发者面板浏览。
    """

    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(
        Integer, ForeignKey("webhook_subscriptions.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_id = Column(String(128), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    target_url = Column(String(1024), nullable=False, default="")
    status = Column(String(16), nullable=False, default="pending", index=True)  # pending/success/failed
    status_code = Column(Integer, nullable=True)
    attempts = Column(Integer, default=0)
    request_body = Column(Text, default="")
    response_body = Column(Text, default="")
    error_message = Column(Text, default="")
    duration_ms = Column(Float, default=0.0)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)


class DeveloperToken(Base):
    """开发者 Personal Access Token (PAT)。

    明文形如 ``pat_<32 字符随机字符串>``，**仅在创建时返回一次**；
    DB 仅保存 sha256 反向哈希用于校验。``token_prefix`` 是头 8 位 (含 ``pat_``)，
    用于 UI 上做 "pat_abcdef…" 这种部分掩码展示。

    ``scopes_json`` 是 JSON 字符串数组，例如 ``["workflow:read", "workflow:execute"]``。
    当前 PR-C 暂不强制路由级 scope 校验，由 PR-D / 后续逐步落地，
    避免一次改动击穿太多现有接口。
    """

    __tablename__ = "developer_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_developer_token_hash"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False, default="")
    token_prefix = Column(String(16), nullable=False, default="")
    token_hash = Column(String(128), nullable=False, index=True)
    scopes_json = Column(Text, default="[]")
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowVersion(Base):
    """工作流版本快照：用于发布/回滚。

    每次发布把工作流的 name/description + 节点/边 + 触发器序列化为
    ``graph_snapshot`` 字段（JSON）。回滚时仅依据 snapshot 重建图与元信息，
    不改动触发器（避免冷不丁停掉用户已经在用的 cron/webhook 入口）。

    每个 workflow 同时只有一个 ``is_current=True`` 行；
    ``version_no`` 在 (workflow_id) 维度自增。
    """

    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version_no", name="uq_workflow_version_no"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False)
    note = Column(Text, default="")
    graph_snapshot = Column(Text, nullable=False, default="{}")
    is_current = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


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


class AccountExperienceLedger(Base):
    """账号经验流水：以 (source_type, source_order_id) 唯一标识，保证支付回调/查询补发/退款重试不重复加减。"""

    __tablename__ = "account_experience_ledger"
    __table_args__ = (
        UniqueConstraint("source_type", "source_order_id", name="uq_account_xp_source"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source_type = Column(String(32), nullable=False, index=True)
    source_order_id = Column(String(64), nullable=False)
    amount = Column(Float, nullable=False)
    xp_delta = Column(Integer, nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class AiModelPrice(Base):
    __tablename__ = "ai_model_prices"
    __table_args__ = (UniqueConstraint("provider", "model", name="uq_ai_model_price"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(256), nullable=False, index=True)
    label = Column(String(256), default="")
    input_price_per_1k = Column(Float, default=0.0)
    output_price_per_1k = Column(Float, default=0.0)
    min_charge = Column(Float, default=0.01)
    enabled = Column(Boolean, default=True, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(256), default="")
    provider = Column(String(64), default="", index=True)
    model = Column(String(256), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    content = Column(Text, default="")
    provider = Column(String(64), default="")
    model = Column(String(256), default="")
    usage_json = Column(Text, default="{}")
    charge_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class LlmCallLog(Base):
    __tablename__ = "llm_call_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=True, index=True)
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(256), nullable=False)
    status = Column(String(32), default="success", index=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated = Column(Boolean, default=False)
    charge_amount = Column(Float, default=0.0)
    hold_no = Column(String(64), default="")
    upstream_status = Column(Integer, nullable=True)
    error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeCollection(Base):
    """知识库集合元数据：每条对应一个物理 Chroma 集合 ``kb_<id>``。

    owner_kind / owner_id 决定归属（user|employee|workflow|org），允许 grant 给别的实体共享。
    """

    __tablename__ = "knowledge_collections"
    __table_args__ = (
        UniqueConstraint("owner_kind", "owner_id", "name", name="uq_kb_owner_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_kind = Column(String(16), nullable=False, index=True)
    owner_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, default="")
    visibility = Column(String(16), default="private", index=True)
    embedding_model = Column(String(64), default="")
    embedding_dim = Column(Integer, default=1536)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeMembership(Base):
    """共享授权：把某个集合 grant 给另一个 owner（user/employee/workflow/org）。"""

    __tablename__ = "knowledge_memberships"
    __table_args__ = (
        UniqueConstraint(
            "collection_id",
            "grantee_kind",
            "grantee_id",
            name="uq_kb_membership_unique",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(
        Integer, ForeignKey("knowledge_collections.id"), nullable=False, index=True
    )
    grantee_kind = Column(String(16), nullable=False)
    grantee_id = Column(String(64), nullable=False, index=True)
    permission = Column(String(8), default="read")
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeDocument(Base):
    """集合内的文档元数据（chunk 已写入 Chroma 物理集合）。"""

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("collection_id", "doc_id", name="uq_kb_doc_unique"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(
        Integer, ForeignKey("knowledge_collections.id"), nullable=False, index=True
    )
    doc_id = Column(String(64), nullable=False, index=True)
    filename = Column(String(256), default="")
    size_bytes = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    ip = Column(String(64), default="", index=True)
    event_type = Column(String(64), nullable=False, index=True)
    provider = Column(String(64), default="")
    model = Column(String(256), default="")
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class OutboxEvent(Base):
    """事务型事件 outbox。

    业务事务内同库写入这张表 + 业务表，再由独立 dispatcher 拉取并通过
    NeuroBus / Webhook 投递。``status`` 流转：``pending`` → ``dispatched`` /
    ``failed``，失败带 ``last_error`` 与 ``attempts`` 供重试与告警。
    """

    __tablename__ = "event_outbox"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_event_outbox_event_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(128), nullable=False, index=True)
    event_name = Column(String(64), nullable=False, index=True)
    event_version = Column(Integer, default=1, nullable=False)
    aggregate_id = Column(String(128), default="", index=True)
    idempotency_key = Column(String(192), default="", index=True)
    producer = Column(String(64), default="modstore-python")
    payload_json = Column(Text, default="{}")
    status = Column(String(16), default="pending", index=True)
    attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    dispatched_at = Column(DateTime, nullable=True)


def default_db_path() -> Path:
    raw = (os.environ.get("MODSTORE_DB_PATH") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent / "modstore.db"


def database_url(db_path: Optional[Path] = None) -> str:
    raw = (os.environ.get("DATABASE_URL") or "").strip()
    if raw:
        if raw.startswith("postgres://"):
            return "postgresql://" + raw[len("postgres://") :]
        return raw
    p = db_path or default_db_path()
    return f"sqlite:///{p}"


_engine = None
_SessionFactory = None


def get_engine(db_path: Optional[Path] = None):
    global _engine
    if _engine is None:
        url = database_url(db_path)
        if url.startswith("sqlite:///"):
            p = Path(url.replace("sqlite:///", "", 1))
            p.parent.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(url, echo=False)
        else:
            _engine = create_engine(
                url,
                echo=False,
                pool_pre_ping=True,
                pool_size=int(os.environ.get("MODSTORE_DB_POOL_SIZE", "10")),
                max_overflow=int(os.environ.get("MODSTORE_DB_MAX_OVERFLOW", "20")),
            )
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
    if engine.dialect.name != "sqlite":
        init_default_plan_templates()
        return
    try:
        _sqlite_add_column_if_missing(engine, "catalog_items", "industry", "TEXT DEFAULT '通用'")
    except Exception:
        pass
    try:
        _sqlite_add_column_if_missing(engine, "users", "default_llm_json", "TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        _sqlite_add_column_if_missing(engine, "users", "phone", "TEXT")
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
    try:
        _sqlite_add_column_if_missing(engine, "catalog_items", "template_category", "TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        _sqlite_add_column_if_missing(engine, "catalog_items", "template_difficulty", "TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        _sqlite_add_column_if_missing(engine, "catalog_items", "install_count", "INTEGER DEFAULT 0 NOT NULL")
    except Exception:
        pass
    try:
        _sqlite_add_column_if_missing(engine, "catalog_items", "graph_snapshot", "TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        _sqlite_add_column_if_missing(engine, "users", "experience", "INTEGER DEFAULT 0 NOT NULL")
    except Exception:
        pass
    init_default_plan_templates()


def init_default_plan_templates() -> None:
    """
    会员体系（与历史 plan_id 保留兼容）：
      - VIP   = plan_basic       入门档
      - VIP+  = plan_pro         进阶档
      - svip  = plan_enterprise  企业级会员入口（展示文案只描述本档）
      - SVIP2..8 = plan_svip2..plan_svip8 进阶 S 级，购买前需已拥有任一 SVIP 档
    旧 plan_id 不变，避免 user_plans / payment_orders 历史数据失效。
    """
    defaults = [
        {
            "id": "plan_basic",
            "name": "VIP",
            "description": "入门会员，解锁基础 AI 调用与平台能力",
            "price": 9.90,
            "features_json": '["基础 AI 对话","基础模型额度","可购买更多余额","会员身份标识"]',
            "quotas_json": '{"employee_count":1,"llm_calls":5000,"storage_mb":512}',
        },
        {
            "id": "plan_pro",
            "name": "VIP+",
            "description": "进阶会员，更高额度 + BYOK + 用量明细",
            "price": 29.90,
            "features_json": '["更高 AI 调用额度","BYOK 自有密钥","优先模型接入","用量明细","高级功能优先体验"]',
            "quotas_json": '{"employee_count":3,"llm_calls":30000,"storage_mb":2048}',
        },
        {
            "id": "plan_enterprise",
            "name": "svip",
            "description": "企业级会员（svip），含大额度企业 AI 调用、团队/部署与优先支持",
            "price": 99.90,
            "features_json": '["企业级 AI 调用额度","团队/企业支持","专属部署支持","优先技术支持"]',
            "quotas_json": '{"employee_count":999999,"llm_calls":300000,"storage_mb":10240}',
        },
        {
            "id": "plan_svip2",
            "name": "SVIP2",
            "description": "SVIP 进阶档（需已是 SVIP 用户）",
            "price": 199.00,
            "features_json": '["svip 全部权益","双倍 AI 调用额度","专属客服群组","新功能内测资格"]',
            "quotas_json": '{"employee_count":999999,"llm_calls":600000,"storage_mb":20480}',
        },
        {
            "id": "plan_svip3",
            "name": "SVIP3",
            "description": "SVIP 进阶档（需已是 SVIP 用户）",
            "price": 299.00,
            "features_json": '["SVIP2 全部权益","三倍 AI 调用额度","定制工作流模板"]',
            "quotas_json": '{"employee_count":999999,"llm_calls":900000,"storage_mb":30720}',
        },
        {
            "id": "plan_svip4",
            "name": "SVIP4",
            "description": "SVIP 进阶档（需已是 SVIP 用户）",
            "price": 499.00,
            "features_json": '["SVIP3 全部权益","五倍 AI 调用额度","专家咨询时长 2h/月"]',
            "quotas_json": '{"employee_count":999999,"llm_calls":1500000,"storage_mb":51200}',
        },
        {
            "id": "plan_svip5",
            "name": "SVIP5",
            "description": "SVIP 进阶档（需已是 SVIP 用户）",
            "price": 999.00,
            "features_json": '["SVIP4 全部权益","十倍 AI 调用额度","专家咨询时长 5h/月"]',
            "quotas_json": '{"employee_count":999999,"llm_calls":3000000,"storage_mb":102400}',
        },
        {
            "id": "plan_svip6",
            "name": "SVIP6",
            "description": "SVIP 进阶档（需已是 SVIP 用户）",
            "price": 1999.00,
            "features_json": '["SVIP5 全部权益","二十倍 AI 调用额度","驻场技术对接 1d/月"]',
            "quotas_json": '{"employee_count":999999,"llm_calls":6000000,"storage_mb":204800}',
        },
        {
            "id": "plan_svip7",
            "name": "SVIP7",
            "description": "SVIP 进阶档（需已是 SVIP 用户）",
            "price": 2999.00,
            "features_json": '["SVIP6 全部权益","三十倍 AI 调用额度","驻场技术对接 2d/月","品牌联合露出"]',
            "quotas_json": '{"employee_count":999999,"llm_calls":9000000,"storage_mb":307200}',
        },
        {
            "id": "plan_svip8",
            "name": "SVIP8",
            "description": "SVIP 顶级档（需已是 SVIP 用户）",
            "price": 4999.00,
            "features_json": '["SVIP7 全部权益","无限 AI 调用额度","驻场技术对接 5d/月","战略合作通道"]',
            "quotas_json": '{"employee_count":999999,"llm_calls":99999999,"storage_mb":1048576}',
        },
    ]
    sf = get_session_factory()
    with sf() as session:
        for row in defaults:
            exists = session.query(PlanTemplate).filter(PlanTemplate.id == row["id"]).first()
            if exists:
                exists.name = row["name"]
                exists.description = row["description"]
                exists.features_json = row["features_json"]
                exists.quotas_json = row["quotas_json"]
                exists.price = row["price"]
                exists.is_active = True
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
