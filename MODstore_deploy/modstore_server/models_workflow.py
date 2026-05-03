from __future__ import annotations

from datetime import datetime

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
)

from .models_base import Base


class Workflow(Base):
    """工作流模型（节点图，**已弃用**：保留为只读迁移源数据）。

    新增字段：

    - ``migration_status``：``""|pending|migrating|migrated|failed`` ——
      迁移到脚本工作流的状态；空值代表还未启动迁移
    - ``migrated_to_id``：迁移成功后指向 :class:`ScriptWorkflow.id`
    """

    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    migration_status = Column(String(16), default="", index=True)
    migrated_to_id = Column(Integer, nullable=True, index=True)


class WorkflowNode(Base):
    """工作流节点模型"""

    __tablename__ = "workflow_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    node_type = Column(String(64), nullable=False)
    name = Column(String(256), nullable=False)
    config = Column(Text, default="{}")
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
    condition = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowSandboxRun(Base):
    """工作流沙盒运行记录，用于判断员工是否可绑定该工作流。"""

    __tablename__ = "workflow_sandbox_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ok = Column(Boolean, default=False, index=True)
    validate_only = Column(Boolean, default=False, index=True)
    mock_employees = Column(Boolean, default=True)
    graph_fingerprint = Column(String(64), default="", index=True)
    report_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class WorkflowExecution(Base):
    """工作流执行记录模型"""

    __tablename__ = "workflow_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(32), default="pending")
    input_data = Column(Text, default="{}")
    output_data = Column(Text, default="{}")
    error_message = Column(Text, default="")
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class WorkflowTrigger(Base):
    __tablename__ = "workflow_triggers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    trigger_type = Column(String(32), nullable=False, index=True)
    trigger_key = Column(String(128), default="", index=True)
    config_json = Column(Text, default="{}")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowVersion(Base):
    """工作流版本快照：用于发布/回滚。

    每次发布把工作流的 name/description + 节点/边 + 触发器序列化为
    ``graph_snapshot`` 字段（JSON）。回滚时仅依据 snapshot 重建图与元信息，
    不改动触发器（避免冷不丁停掉用户已经在用的 cron/webhook 入口）。

    每个 workflow 同时只有一个 ``is_current=True`` 行；
    ``version_no`` 在 (workflow_id) 维度自增。
    """

    __tablename__ = "workflow_versions"
    __table_args__ = (UniqueConstraint("workflow_id", "version_no", name="uq_workflow_version_no"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False)
    note = Column(Text, default="")
    graph_snapshot = Column(Text, nullable=False, default="{}")
    is_current = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScriptWorkflow(Base):
    """脚本即工作流：替代节点图模型的主体，存放完整 ``script.py`` + Brief。

    状态机（无人审）::

        draft  →  sandbox_testing  →  active
                       ↑                ↓
                  edit-with-ai      deprecated

    ``failed`` 是 agent loop 达到最大轮数仍未通过的终态。
    """

    __tablename__ = "script_workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    brief_json = Column(Text, default="{}")
    script_text = Column(Text, default="")
    schema_in_json = Column(Text, default="{}")
    status = Column(String(32), default="draft", index=True)
    agent_session_id = Column(String(64), default="", index=True)
    migrated_from_workflow_id = Column(Integer, nullable=True, index=True)
    last_manual_sandbox_run_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScriptWorkflowVersion(Base):
    """脚本工作流的版本快照：每次保存 / 通过 agent loop 都新建一行。"""

    __tablename__ = "script_workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version_no", name="uq_script_workflow_version_no"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("script_workflows.id"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False)
    script_text = Column(Text, default="")
    plan_md = Column(Text, default="")
    agent_log_json = Column(Text, default="{}")
    is_current = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScriptWorkflowRun(Base):
    """单次脚本运行记录。

    ``mode`` 区分 ``auto``（agent loop 自动跑）/ ``manual_sandbox``（用户人工
    沙箱试用）/ ``production``（触发器 / 生产 API 调起），便于审计与计费。
    """

    __tablename__ = "script_workflow_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("script_workflows.id"), nullable=False, index=True)
    version_id = Column(
        Integer, ForeignKey("script_workflow_versions.id"), nullable=True, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mode = Column(String(16), default="auto", index=True)
    status = Column(String(16), default="running", index=True)
    stdout = Column(Text, default="")
    stderr = Column(Text, default="")
    outputs_meta_json = Column(Text, default="[]")
    runtime_sdk_calls_json = Column(Text, default="[]")
    error_message = Column(Text, default="")
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
