"""工作台 AI 编排：内存会话 + 磁盘持久化（多 worker 可读）+ 异步执行 + GET 轮询。"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import uuid
from io import BytesIO
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from modstore_server.api.deps import _get_current_user
from modstore_server.models import (
    CatalogItem,
    get_session_factory,
    ScriptWorkflow,
    ScriptWorkflowRun,
    ScriptWorkflowVersion,
    User,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
)
from modstore_server.mod_scaffold_runner import (
    analyze_mod_employee_readiness,
    attach_nl_workflow_to_employee_pack_dir,
    create_mod_suite_workflows_async,
    generate_mod_suite_blueprint_async,
    generate_workflow_for_intent,
    import_mod_suite_repository,
    employee_pack_consistency_warnings,
    materialize_employee_pack_if_missing,
    mod_compileall_warnings,
    modstore_library_path,
    patch_workflow_graph_employee_nodes,
    register_mod_employee_packs_async,
    run_mod_suite_mod_sandbox,
    run_mod_suite_workflow_sandboxes,
    run_employee_ai_scaffold_async,
    run_mod_ai_scaffold_async,
    resolve_llm_provider_model_auto,
    write_mod_suite_blueprint,
    write_mod_suite_industry_card,
    write_mod_suite_ui_shell,
)
from modstore_server.mod_employee_impl_scaffold import (
    _fallback_employee_py,
    generate_mod_employee_impls_async,
    sanitize_employee_stem,
)
from modstore_server.workflow_engine import run_workflow_sandbox
from modstore_server.workflow_nl_graph import apply_nl_workflow_graph
from modstore_server.workflow_sandbox_state import record_workflow_sandbox_run
from modstore_server.workbench_script_runner import run_script_agent_job, run_script_job
from modstore_server.workbench_research import build_research_context
from modstore_server.llm_chat_proxy import chat_dispatch
from modstore_server.llm_key_resolver import resolve_api_key, resolve_base_url
from modstore_server.employee_ai_scaffold import (
    build_employee_pack_zip,
    normalize_editor_manifest_for_registry,
)
from modman.manifest_util import read_manifest

try:
    import edge_tts as _edge_tts

    _EDGE_TTS = _edge_tts
except ImportError:  # pragma: no cover - 可选依赖
    _EDGE_TTS = None

router = APIRouter(prefix="/api/workbench", tags=["workbench"])

_LOG = logging.getLogger(__name__)

_MAX_EMPLOYEES_FOR_LLM = 10

WORKBENCH_SESSIONS: Dict[str, Dict[str, Any]] = {}
_SESSION_LOCK = asyncio.Lock()

# 画布编排 intent：`workflow` 已规范为 `skill`（Skill 组）
CANVAS_SKILL_INTENT = "skill"


def _canonical_workbench_intent(intent: Optional[str]) -> str:
    s = (intent or "").strip().lower()
    if s == "workflow":
        return CANVAS_SKILL_INTENT
    return s


def _enrich_artifact_skill_aliases(artifact: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not artifact or not isinstance(artifact, dict):
        return artifact
    out = dict(artifact)
    wid = out.get("workflow_id")
    if wid is not None:
        out.setdefault("skill_group_id", wid)
    wn = out.get("workflow_name")
    if wn is not None:
        out.setdefault("skill_group_name", wn)
    return out


def _workbench_session_store_dir() -> Path:
    d = Path(__file__).resolve().parent / "data" / "workbench_sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _workbench_session_file(sid: str) -> Path:
    # create_workbench_session 使用 hex[:24]，禁止路径穿越
    s = str(sid or "").strip().lower()
    if len(s) < 16 or len(s) > 32 or any(c not in "0123456789abcdef" for c in s):
        raise ValueError("invalid session id")
    return _workbench_session_store_dir() / f"{s}.json"


def _persist_workbench_session_unlocked(sid: str) -> None:
    """多 worker / 多进程时内存 dict 不共享，落盘以便 GET 轮询命中任意进程可读。"""
    sess = WORKBENCH_SESSIONS.get(sid)
    if not sess:
        return
    try:
        path = _workbench_session_file(sid)
    except ValueError:
        return
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(sess, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def _load_workbench_session_unlocked(sid: str) -> Optional[Dict[str, Any]]:
    try:
        path = _workbench_session_file(sid)
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _hydrate_workbench_session_unlocked(sid: str) -> None:
    if sid in WORKBENCH_SESSIONS:
        return
    loaded = _load_workbench_session_unlocked(sid)
    if loaded and str(loaded.get("id") or "") == str(sid):
        if loaded.get("intent") == "workflow":
            loaded["intent"] = CANVAS_SKILL_INTENT
        WORKBENCH_SESSIONS[sid] = loaded


async def _persist_workbench_session(sid: str) -> None:
    async with _SESSION_LOCK:
        _persist_workbench_session_unlocked(sid)


class EmployeeAiDraftBody(BaseModel):
    brief: str = Field(..., min_length=3, max_length=8000)
    provider: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=128)
    suggested_id: Optional[str] = Field(None, max_length=64)


class EmployeeAiRefinePromptBody(BaseModel):
    current_prompt: str = Field(..., min_length=1, max_length=16000)
    instruction: str = Field(..., min_length=3, max_length=2000)
    role_context: str = Field("", max_length=500)
    provider: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=128)


class WorkbenchResearchBody(BaseModel):
    brief: str = Field(..., min_length=3, max_length=4000)
    intent: Literal["workflow", "mod", "employee", "skill"] = "skill"
    max_repos: int = Field(3, ge=1, le=5)
    max_web: int = Field(6, ge=1, le=12, description="Tavily 网页摘要条数上限")
    max_chars: int = Field(8000, ge=2000, le=20000)

    @field_validator("intent", mode="before")
    @classmethod
    def _research_intent_alias(cls, v: object) -> object:
        if isinstance(v, str) and v.strip().lower() == "workflow":
            return "skill"
        return v


class WorkbenchSessionCreateBody(BaseModel):
    intent: Literal["mod", "employee", "workflow", "skill"]
    brief: str = Field(..., min_length=3, max_length=30000)
    workflow_name: Optional[str] = Field(None, max_length=256)
    skill_group_name: Optional[str] = Field(
        None,
        max_length=256,
        description="画布 Skill 组名称；若填且未填 workflow_name，则写入 workflow_name",
    )
    plan_notes: Optional[str] = Field("", max_length=4000)
    suggested_mod_id: Optional[str] = Field(None, max_length=64)
    replace: bool = True
    provider: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=128)
    generate_workflow_graph: bool = Field(
        True,
        description="为画布 intent（skill，旧称 workflow）时是否用 LLM 生成节点与边（false 则仅创建空 Skill 组容器）",
    )
    generate_full_suite: bool = Field(
        True,
        description="为 mod intent 时是否生成 Mod + 员工 + 工作流绑定的一体化套件",
    )
    generate_frontend: bool = Field(
        True,
        description="为 mod intent 时是否生成定制 Vue 前端页面；false 时仅保留最小前端占位",
    )
    planning_messages: List[Dict[str, Any]] = Field(default_factory=list)
    execution_checklist: List[str] = Field(default_factory=list)
    source_documents: List[Dict[str, Any]] = Field(default_factory=list)
    execution_mode: Literal["workflow", "script"] = "workflow"
    employee_target: Literal["pack_only", "pack_plus_workflow"] = Field(
        "pack_only",
        description="做员工：pack_only 仅生成包体；pack_plus_workflow 额外创建画布工作流并写回 manifest",
    )
    employee_workflow_name: Optional[str] = Field(
        None,
        max_length=256,
        description="pack_plus_workflow 时画布工作流名称（可选）",
    )
    fhd_base_url: Optional[str] = Field(
        None,
        max_length=512,
        description="可选 FHD 宿主根 URL，用于编排末尾 GET /api/mods/ 连通性探测",
    )
    embed_script_workflow: bool = Field(
        False,
        description="做员工：在生成员工包之前先走脚本生成/沙箱 pipeline，落库 ScriptWorkflow 并把 workflow_id 写入 employee_config_v2.collaboration.script_workflows",
    )

    @field_validator("intent", mode="before")
    @classmethod
    def _session_intent_alias(cls, v: object) -> object:
        if isinstance(v, str) and v.strip().lower() == "workflow":
            return CANVAS_SKILL_INTENT
        return v

    @model_validator(mode="before")
    @classmethod
    def _skill_group_name_merge(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        wn = (data.get("workflow_name") or "").strip()
        sg = (data.get("skill_group_name") or "").strip()
        if not wn and sg:
            data["workflow_name"] = sg
        return data


def _default_steps(
    intent: str,
    execution_mode: str = "workflow",
    *,
    employee_target: str = "pack_only",
) -> List[Dict[str, Any]]:
    intent = _canonical_workbench_intent(intent)
    if execution_mode == "script":
        return [
            {"id": "spec", "label": "理解任务", "status": "pending", "message": None},
            {"id": "generate", "label": "生成处理脚本", "status": "pending", "message": None},
            {"id": "validate", "label": "安全检查", "status": "pending", "message": None},
            {"id": "run", "label": "运行并生成文件", "status": "pending", "message": None},
            {"id": "complete", "label": "完成", "status": "pending", "message": None},
        ]
    if intent == "mod":
        return [
            {"id": "spec", "label": "理解需求", "status": "pending", "message": None},
            {"id": "manifest", "label": "生成蓝图与 JSON", "status": "pending", "message": None},
            {"id": "repo", "label": "新建 Mod 仓库", "status": "pending", "message": None},
            {"id": "industry", "label": "生成行业卡片", "status": "pending", "message": None},
            {"id": "employees", "label": "创建员工骨架", "status": "pending", "message": None},
            {"id": "employee_impls", "label": "生成员工脚本", "status": "pending", "message": None},
            {
                "id": "workflows",
                "label": "生成员工 Skill 组（画布编排）",
                "status": "pending",
                "message": None,
            },
            {"id": "register_packs", "label": "登记员工包并修复图", "status": "pending", "message": None},
            {"id": "api", "label": "生成/绑定 API 节点", "status": "pending", "message": None},
            {"id": "workflow_sandbox", "label": "工作流沙箱测试", "status": "pending", "message": None},
            {"id": "mod_sandbox", "label": "Mod 沙箱测试", "status": "pending", "message": None},
            {"id": "complete", "label": "完成", "status": "pending", "message": None},
        ]
    base = [
        {"id": "spec", "label": "理解需求", "status": "pending", "message": None},
        {"id": "generate", "label": "生成产物", "status": "pending", "message": None},
        {"id": "validate", "label": "服务端校验", "status": "pending", "message": None},
    ]
    if intent == "employee":
        base.insert(1, {"id": "employee_plan", "label": "规划一站式员工", "status": "pending", "message": None})
        base.extend(
            [
                {"id": "script_workflow", "label": "生成配套小程序", "status": "pending", "message": None},
                {"id": "embed_script", "label": "绑定到员工", "status": "pending", "message": None},
            ]
        )
        if (employee_target or "").strip().lower() == "pack_plus_workflow":
            base.extend(
                [
                    {"id": "workflow", "label": "生成自动化流程", "status": "pending", "message": None},
                    {"id": "workflow_sandbox", "label": "流程沙箱测试", "status": "pending", "message": None},
                    {"id": "mod_sandbox", "label": "包体与 Python 校验", "status": "pending", "message": None},
                    {"id": "standalone_smoke", "label": "独立可执行自检", "status": "pending", "message": None},
                    {"id": "host_check", "label": "宿主连通性检查", "status": "pending", "message": None},
                ]
            )
        else:
            base.extend(
                [
                    {"id": "workflow", "label": "生成自动化流程", "status": "pending", "message": None},
                    {"id": "workflow_sandbox", "label": "流程沙箱测试", "status": "pending", "message": None},
                    {"id": "mod_sandbox", "label": "包体与 Python 校验", "status": "pending", "message": None},
                    {"id": "standalone_smoke", "label": "独立可执行自检", "status": "pending", "message": None},
                    {"id": "host_check", "label": "宿主连通性检查", "status": "pending", "message": None},
                ]
            )
    base.append({"id": "complete", "label": "完成", "status": "pending", "message": None})
    if intent == CANVAS_SKILL_INTENT:
        base[1]["label"] = "创建 Skill 组"
    return base


async def _set_step(
    sid: str,
    step_id: str,
    status: str,
    message: Optional[Union[str, dict]] = None,
) -> None:
    """Update a workbench step.

    ``message`` may now be either a plain string (legacy) or a structured
    dict with keys: ``summary``, ``round``, ``current_tool``, ``todos``,
    ``slow_hint``.  The Vue frontend uses ``summary`` as the fallback text
    when it encounters a dict.
    """
    async with _SESSION_LOCK:
        _hydrate_workbench_session_unlocked(sid)
        sess = WORKBENCH_SESSIONS.get(sid)
        if not sess:
            return
        for s in sess["steps"]:
            if s["id"] == step_id:
                prev_status = s.get("status")
                s["status"] = status
                if message is not None:
                    s["message"] = message
                if status == "running" and prev_status != "running":
                    s["started_at"] = datetime.utcnow().isoformat() + "Z"
                elif status in ("done", "error"):
                    s.pop("started_at", None)
                break
        _persist_workbench_session_unlocked(sid)


async def _fail_session(sid: str, step_id: str, err: str) -> None:
    async with _SESSION_LOCK:
        _hydrate_workbench_session_unlocked(sid)
        sess = WORKBENCH_SESSIONS.get(sid)
        if not sess:
            return
        sess["status"] = "error"
        sess["error"] = err
        updated = False
        for s in sess["steps"]:
            if s["id"] == step_id and s["status"] == "running":
                s["status"] = "error"
                s["message"] = err
                updated = True
                break
        if not updated:
            for s in sess["steps"]:
                if s["id"] == step_id:
                    s["status"] = "error"
                    s["message"] = err
                    break
        _persist_workbench_session_unlocked(sid)


async def _finalize_session_done(sid: str, artifact: Dict[str, Any]) -> None:
    """Atomically write artifact + status=done.

    Guards against the case where a pipeline branch returns early without
    explicitly completing every step: any step still in pending/running is
    force-promoted to done so the frontend never sees status=done alongside
    non-terminal steps (which would cause premature navigation).
    """
    async with _SESSION_LOCK:
        _hydrate_workbench_session_unlocked(sid)
        sess = WORKBENCH_SESSIONS.get(sid)
        if not sess:
            return
        for s in sess.get("steps") or []:
            if s.get("status") not in ("done", "error"):
                _LOG.warning(
                    "workbench session=%s step=%s was still in state=%s at finalize; forcing done",
                    sid,
                    s.get("id"),
                    s.get("status"),
                )
                s["status"] = "done"
                if not s.get("message"):
                    s["message"] = "管线收尾时补全"
                s.pop("started_at", None)
        sess["status"] = "done"
        sess["artifact"] = artifact
        _persist_workbench_session_unlocked(sid)


def _check_vibe_coding_capability(
    pack_dir: Path,
    wf_attach: "Dict[str, Any]",
) -> "List[Dict[str, Any]]":
    """Inspect pack_dir + workflow attachment for vibe-coding completeness.

    Returns a list of check-result dicts (id, ok, message) that are appended to
    the mod_sandbox checks list.  All checks are informational (non-blocking)
    so a missing capability surfaces as a warning rather than a hard failure.
    """
    import re as _re
    results: List[Dict[str, Any]] = []

    # 1. Does the workflow attachment claim any vibe_code / vibe_workflow ESkills?
    nl_data = wf_attach.get("nl") if isinstance(wf_attach, dict) else None
    skill_blueprints = []
    if isinstance(nl_data, dict):
        skill_blueprints = nl_data.get("skill_blueprints") or []
    vibe_logic_count = sum(
        1 for bp in skill_blueprints
        if isinstance(bp, dict) and str(bp.get("static_logic", {}).get("type") or "").startswith("vibe")
    )
    has_vibe_nodes = bool(wf_attach) and (
        int(wf_attach.get("eskill_count") or 0) > 0 or vibe_logic_count > 0
    )
    results.append({
        "id": "vibe_logic_present",
        "ok": True,  # informational — always pass; surface count for observability
        "message": (
            f"Skill 组含 {vibe_logic_count} 个 vibe 类 logic / {int(wf_attach.get('eskill_count') or 0)} 个 ESkill"
            if isinstance(wf_attach, dict) and wf_attach
            else "未创建画布工作流，vibe-coding 能力检查已跳过"
        ),
    })

    # 2. Do the generated employee Python files have a meaningful SYSTEM_PROMPT?
    emp_dir = pack_dir / "backend" / "employees"
    if emp_dir.is_dir():
        hollow_files: List[str] = []
        missing_prompt_files: List[str] = []
        hollow_patterns = [
            r'SYSTEM_PROMPT\s*=\s*["\'].*请根据用户输入完成任务.*["\']',
            # Exactly empty string: "" or '' — use negative lookahead to avoid matching """
            r'SYSTEM_PROMPT\s*=\s*["\']["\'](?!["\'])',
        ]
        for py_file in sorted(emp_dir.glob("*.py")):
            if py_file.name.startswith("__"):
                continue
            try:
                src = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "SYSTEM_PROMPT" not in src:
                missing_prompt_files.append(py_file.name)
            elif any(_re.search(pat, src) for pat in hollow_patterns):
                hollow_files.append(py_file.name)

        if hollow_files:
            results.append({
                "id": "vibe_system_prompt_quality",
                "ok": False,
                "message": (
                    f"以下员工文件的 SYSTEM_PROMPT 为空洞占位，缺少角色/任务/输出格式说明："
                    f" {', '.join(hollow_files[:5])}"
                ),
            })
        elif missing_prompt_files:
            results.append({
                "id": "vibe_system_prompt_quality",
                "ok": False,
                "message": (
                    f"以下员工文件未定义 SYSTEM_PROMPT 常量（员工只能调 LLM 但无明确指导）："
                    f" {', '.join(missing_prompt_files[:5])}"
                ),
            })
        else:
            results.append({
                "id": "vibe_system_prompt_quality",
                "ok": True,
                "message": "员工文件均定义了 SYSTEM_PROMPT 常量",
            })

        # 3. Does the employee code implement real step-by-step logic (怎么做)?
        #    Heuristic: a file that calls call_llm but never extracts data from
        #    payload / project_analysis before the call is a "thin impl".
        #    We look for explicit reads from payload/pa/project_analysis variables,
        #    directory scan ops, or file system calls.  Reads from the LLM result
        #    (e.g. result.get('content')) don't count because they happen AFTER
        #    the call and don't represent pre-processing logic.
        thin_impl_files: List[str] = []
        for py_file in sorted(emp_dir.glob("*.py")):
            if py_file.name.startswith("__"):
                continue
            try:
                src = py_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Skip very short or empty stubs
            if len(src.strip()) < 200:
                continue
            has_payload_steps = bool(
                # Reads from payload or project_analysis-named variables
                _re.search(
                    r'(?:payload|project_analysis|pa|manifests|tech_stack|scripts|config|data)\s*'
                    r'\.\s*(?:get|items|values|keys)\s*\(',
                    src,
                )
                or _re.search(r'payload\s*\[', src)
                or _re.search(r'for\s+\w+\s+in\s+', src)
                or _re.search(r'os\.|glob\.|pathlib\.', src)
            )
            if not has_payload_steps and "call_llm" in src:
                thin_impl_files.append(py_file.name)

        if thin_impl_files:
            results.append({
                "id": "vibe_how_to_do_logic",
                "ok": False,
                "message": (
                    f"以下员工文件调用了 call_llm 但缺乏数据提取/目录扫描等前置步骤，"
                    f"建议补充「怎么做」逻辑： {', '.join(thin_impl_files[:5])}"
                ),
            })
        else:
            results.append({
                "id": "vibe_how_to_do_logic",
                "ok": True,
                "message": "员工文件包含数据处理步骤（怎么做逻辑检查通过）",
            })
    else:
        results.append({
            "id": "vibe_system_prompt_quality",
            "ok": True,
            "message": "无 backend/employees 目录，跳过员工代码检查",
        })
        results.append({
            "id": "vibe_how_to_do_logic",
            "ok": True,
            "message": "无 backend/employees 目录，跳过怎么做检查",
        })

    return results


def _refresh_employee_pack_catalog_zip(db: Session, user: User, pack_dir: Path) -> Dict[str, Any]:
    """Rebuild stored .xcemp after in-place manifest edits.

    ``run_employee_ai_scaffold_async`` first imports/saves the package, then the
    employee pipeline may mutate ``library/<pack>/manifest.json`` (for example
    writing workflow_id into employee_config_v2).  The catalog runtime reads the
    stored .xcemp, not the library folder, so rebuild and re-register that file.
    """
    from modstore_server.catalog_store import append_package, package_manifest_alignment_errors

    raw = _load_registry_aligned_employee_manifest(pack_dir, pack_dir.name)
    pack_id = str(raw.get("id") or pack_dir.name).strip() or pack_dir.name
    raw_zip = build_employee_pack_zip(pack_id, raw)
    with tempfile.NamedTemporaryFile(suffix=".xcemp", delete=False) as tmp:
        tmp.write(raw_zip)
        tmp_path = Path(tmp.name)
    try:
        rec = {
            "id": pack_id,
            "name": str(raw.get("name") or pack_id),
            "version": str(raw.get("version") or "1.0.0"),
            "description": str(raw.get("description") or ""),
            "artifact": "employee_pack",
            "industry": str(raw.get("industry") or "通用"),
            "release_channel": "stable",
            "commerce": raw.get("commerce") or {"mode": "free", "price": 0},
            "license": {"type": "personal", "verify_url": None},
        }
        align_errs = package_manifest_alignment_errors(rec, tmp_path)
        if align_errs:
            raise ValueError("员工包 metadata 与包内 manifest 不一致: " + "; ".join(align_errs))
        saved = append_package(rec, tmp_path)
        row = db.query(CatalogItem).filter(CatalogItem.pkg_id == pack_id).first()
        if not row:
            row = CatalogItem(pkg_id=pack_id, author_id=user.id)
            db.add(row)
        row.version = saved.get("version") or rec["version"]
        row.name = saved.get("name") or rec["name"]
        row.description = saved.get("description") or rec["description"]
        row.price = 0.0
        row.artifact = "employee_pack"
        row.industry = saved.get("industry") or rec["industry"]
        row.stored_filename = saved.get("stored_filename") or ""
        row.sha256 = saved.get("sha256") or ""
        db.commit()
        return saved
    finally:
        tmp_path.unlink(missing_ok=True)


def _load_registry_aligned_employee_manifest(pack_dir: Path, pack_id: str) -> Dict[str, Any]:
    mf = pack_dir / "manifest.json"
    raw = json.loads(mf.read_text(encoding="utf-8"))
    aligned, errs = normalize_editor_manifest_for_registry(raw, pack_id)
    if errs:
        from modman.artifact_constants import normalize_artifact

        if normalize_artifact(aligned) != "employee_pack":
            raise ValueError("manifest 规范化失败: " + "; ".join(errs))
    return aligned


def _employee_pack_workflow_reference_report(
    db: Session,
    user: User,
    manifest: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate workflow/script_workflow ID references against the current DB.

    Employee packs currently package manifest/runtime files only; workflow and
    ScriptWorkflow definitions are not migrated inside the .xcemp.  A manifest
    that references IDs not present in the target DB will install successfully
    but fail at runtime, so export/save records an explicit report.
    """
    workflow_ids: List[int] = []
    script_workflow_ids: List[int] = []

    rows = manifest.get("workflow_employees")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                wid = int(row.get("workflow_id") or row.get("workflowId") or 0)
            except (TypeError, ValueError):
                wid = 0
            if wid > 0 and wid not in workflow_ids:
                workflow_ids.append(wid)

    v2 = manifest.get("employee_config_v2") if isinstance(manifest.get("employee_config_v2"), dict) else {}
    collab = v2.get("collaboration") if isinstance(v2.get("collaboration"), dict) else {}
    wf = collab.get("workflow") if isinstance(collab.get("workflow"), dict) else {}
    try:
        wid = int(wf.get("workflow_id") or wf.get("workflowId") or 0)
    except (TypeError, ValueError):
        wid = 0
    if wid > 0 and wid not in workflow_ids:
        workflow_ids.append(wid)

    scripts = collab.get("script_workflows")
    if isinstance(scripts, list):
        for item in scripts:
            if not isinstance(item, dict):
                continue
            try:
                sid = int(item.get("script_workflow_id") or item.get("workflow_id") or 0)
            except (TypeError, ValueError):
                sid = 0
            if sid > 0 and sid not in script_workflow_ids:
                script_workflow_ids.append(sid)
    swa = manifest.get("script_workflow_attachment")
    if isinstance(swa, dict):
        try:
            sid = int(swa.get("script_workflow_id") or swa.get("workflow_id") or 0)
        except (TypeError, ValueError):
            sid = 0
        if sid > 0 and sid not in script_workflow_ids:
            script_workflow_ids.append(sid)

    workflow_found: List[int] = []
    for wid in workflow_ids:
        row = db.query(Workflow).filter(Workflow.id == wid, Workflow.user_id == user.id).first()
        if row:
            workflow_found.append(wid)
    script_found: List[int] = []
    for sid in script_workflow_ids:
        row = db.query(ScriptWorkflow).filter(ScriptWorkflow.id == sid, ScriptWorkflow.user_id == user.id).first()
        if row:
            script_found.append(sid)

    missing_workflows = [wid for wid in workflow_ids if wid not in workflow_found]
    missing_scripts = [sid for sid in script_workflow_ids if sid not in script_found]
    warnings: List[str] = []
    if missing_workflows:
        warnings.append(f"workflow_id 不存在或不属于当前用户: {missing_workflows}")
    if missing_scripts:
        warnings.append(f"script_workflow_id 不存在或不属于当前用户: {missing_scripts}")
    if workflow_ids or script_workflow_ids:
        warnings.append("employee_pack 不会内嵌 workflow/script_workflow 定义；跨环境上线前必须在目标库重建或重新绑定。")

    return {
        "packaging": "manifest_runtime_only",
        "workflow_ids": workflow_ids,
        "script_workflow_ids": script_workflow_ids,
        "missing_workflow_ids": missing_workflows,
        "missing_script_workflow_ids": missing_scripts,
        "ok": not missing_workflows and not missing_scripts,
        "warnings": warnings,
    }


def _write_workflow_reference_report(
    db: Session,
    user: User,
    manifest: Dict[str, Any],
) -> List[str]:
    report = _employee_pack_workflow_reference_report(db, user, manifest)
    v2 = manifest.get("employee_config_v2") if isinstance(manifest.get("employee_config_v2"), dict) else {}
    meta = v2.get("metadata") if isinstance(v2.get("metadata"), dict) else {}
    meta["workflow_reference_report"] = report
    meta["workflow_runtime_check"] = "employee_pack 不内嵌 workflow/script_workflow；上线前须确认目标库存在这些 ID 或重新绑定。"
    v2["metadata"] = meta
    manifest["employee_config_v2"] = v2
    return list(report.get("warnings") or [])


def _cleanup_mod_pipeline_resources(db: Session, resources: List[Dict[str, Any]]) -> None:
    """做 Mod 全流程失败时尽量撤销已创建目录与数据库记录（尽力而为）。"""
    import shutil

    for res in reversed(resources):
        try:
            if res["type"] == "mod_dir":
                p = Path(res["path"])
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
            elif res["type"] == "workflow_ids":
                for wid in res.get("ids") or []:
                    try:
                        wid_int = int(wid)
                    except (TypeError, ValueError):
                        continue
                    db.query(WorkflowEdge).filter(WorkflowEdge.workflow_id == wid_int).delete(
                        synchronize_session=False
                    )
                    db.query(WorkflowNode).filter(WorkflowNode.workflow_id == wid_int).delete(
                        synchronize_session=False
                    )
                    wf = db.query(Workflow).filter(Workflow.id == wid_int).first()
                    if wf:
                        db.delete(wf)
                db.commit()
            elif res["type"] == "catalog_by_pkg":
                pkg_id = str(res.get("pkg_id") or "").strip()
                if pkg_id:
                    db.query(CatalogItem).filter(CatalogItem.pkg_id == pkg_id).delete(
                        synchronize_session=False
                    )
                    db.commit()
        except Exception:
            _LOG.exception("cleanup pipeline resource failed res=%s", res)


def _script_workflow_brief(payload: Dict[str, Any], files: List[Dict[str, Any]]) -> Dict[str, Any]:
    brief = (payload.get("brief") or "").strip()
    filenames = [str((f or {}).get("filename") or "upload.bin") for f in files or []]
    return {
        "goal": brief,
        "inputs": [
            {"filename": name, "description": "工作台上传样本文件"}
            for name in filenames
        ],
        "outputs": "生成处理后的结果文件到 outputs/，用于下载和沙箱复核",
        "acceptance": "脚本运行成功，outputs/ 至少生成一个结果文件",
        "fallback": "",
        "trigger_type": "manual",
        "references": {"source": "workbench-script-session"},
    }


def _embed_script_workflow_in_employee_pack(
    pack_dir: Path,
    *,
    script_workflow: Dict[str, Any],
    brief: str,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Write ScriptWorkflow linkage into an employee pack manifest in-place.

    When *db* is supplied the function also embeds a portable
    ``script_workflow_bundles`` entry so the pack is self-contained and can be
    installed into a different environment without losing the script definition.
    """
    mf = pack_dir / "manifest.json"
    raw = json.loads(mf.read_text(encoding="utf-8"))
    v2 = raw.get("employee_config_v2") if isinstance(raw.get("employee_config_v2"), dict) else {}
    collab = v2.get("collaboration") if isinstance(v2.get("collaboration"), dict) else {}
    entries = collab.get("script_workflows")
    if not isinstance(entries, list):
        entries = []
    sid = script_workflow.get("id")
    sid_int = int(sid) if sid is not None else 0
    entry = {
        "script_workflow_id": sid_int,
        "workflow_id": sid_int,
        "name": str(script_workflow.get("name") or "员工脚本工作流"),
        "trigger_type": "manual",
        "role": "primary_program",
        "description": (brief or "").strip()[:1000],
    }
    deduped: List[Any] = []
    for x in entries:
        if not isinstance(x, dict):
            deduped.append(x)
            continue
        try:
            existing_id = int(x.get("script_workflow_id") or x.get("workflow_id") or 0)
        except (TypeError, ValueError):
            existing_id = 0
        if existing_id != sid_int:
            deduped.append(x)
    entries = deduped
    entries.insert(0, entry)
    collab = {**collab, "script_workflows": entries}
    v2["collaboration"] = collab
    raw["employee_config_v2"] = v2
    raw["script_workflow_attachment"] = {
        "script_workflow_id": sid_int,
        "name": entry["name"],
        "trigger_type": entry["trigger_type"],
    }
    if db is not None and sid_int > 0:
        try:
            from modstore_server.employee_pack_workflow_bundle import embed_workflow_bundles_in_manifest
            embed_workflow_bundles_in_manifest(db, raw)
        except Exception as _e:  # noqa: BLE001
            _LOG.warning("embed script workflow bundle failed sid=%d: %s", sid_int, _e)
    mf.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return raw["script_workflow_attachment"]


def _strip_json_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        import re

        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _fallback_employee_orchestration_plan(brief: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    checklist = payload.get("execution_checklist")
    checklist_text = "\n".join(f"- {x}" for x in checklist if isinstance(x, str)) if isinstance(checklist, list) else ""
    source_docs = payload.get("source_documents")
    doc_hint = ""
    if isinstance(source_docs, list) and source_docs:
        names = [str((x or {}).get("name") or "").strip() for x in source_docs if isinstance(x, dict)]
        doc_hint = "参考资料：" + "、".join([n for n in names if n][:8])
    merged = "\n".join(x for x in [brief, checklist_text, doc_hint] if x).strip()
    short = (brief or "员工助手").strip().splitlines()[0][:40] or "员工助手"
    return {
        "employee_name": short,
        "employee_brief": merged or brief,
        "script_workflow_name": f"{short} 脚本工作流",
        "script_brief": (
            f"{merged or brief}\n\n请生成配套 Python 脚本：读取 inputs/ 中的文档或数据文件，"
            "递归整理可读文本，输出 Markdown 摘要/处理结果到 outputs/；没有输入文件时输出示例说明。"
        ),
        "script_runtime_notes": "只能读 inputs/、写 outputs/；允许 os.walk 遍历 inputs；禁止联网和越界文件访问。",
        "workflow_name": str(payload.get("employee_workflow_name") or short).strip() or short,
        "workflow_brief": (
            f"{merged or brief}\n\n请把该员工拆成可执行 Skill 组：接收输入、读取/归纳、生成结果、人工复核。"
        ),
        "acceptance": [
            "员工包可安装并能解释自己的职责",
            "脚本工作流可空跑并生成 outputs/ 结果文件",
            "Skill 组体现输入、处理、输出、复核的顺序",
        ],
    }


async def _build_employee_orchestration_plan(
    db: Session,
    user_id: int,
    *,
    payload: Dict[str, Any],
    provider: Optional[str],
    model: Optional[str],
) -> Dict[str, Any]:
    brief = (payload.get("brief") or "").strip()
    fallback = _fallback_employee_orchestration_plan(brief, payload)
    if not provider or not model:
        return fallback
    key, _src = resolve_api_key(db, user_id, provider)
    if not key:
        return fallback
    checklist = payload.get("execution_checklist")
    messages = payload.get("planning_messages")
    docs = payload.get("source_documents")
    planning_context = {
        "brief": brief,
        "execution_checklist": checklist if isinstance(checklist, list) else [],
        "planning_messages": messages if isinstance(messages, list) else [],
        "source_documents": docs if isinstance(docs, list) else [],
    }
    sys_prompt = (
        "你是 XCAGI「做员工」一站式编排规划器。只输出 JSON 对象，不要 markdown。\n"
        "你要把同一个用户需求拆成三份互相一致的 brief：\n"
        "1 employee_brief：给员工包生成器，描述角色、边界、输出格式。\n"
        "2 script_brief：给 Python 脚本工作流生成器，描述如何读取 inputs/、写 outputs/，没有输入也能空跑生成说明文件。\n"
        "3 workflow_brief：给画布 Skill 组生成器，描述多步自动化流程。\n"
        "字段必须包含：employee_name, employee_brief, script_workflow_name, script_brief, script_runtime_notes, workflow_name, workflow_brief, acceptance。\n"
        "script_brief 必须明确：只能读 inputs/、只能写 outputs/；如需遍历文件，用 os.walk('inputs')；输出 Markdown 或 JSON 结果文件。\n"
        "不要让脚本读取真实磁盘绝对路径，不要要求联网。"
    )
    try:
        res = await chat_dispatch(
            provider,
            api_key=key,
            base_url=resolve_base_url(db, user_id, provider),
            model=model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": json.dumps(planning_context, ensure_ascii=False)[:12000]},
            ],
            max_tokens=1800,
        )
    except Exception:
        _LOG.exception("employee orchestration plan LLM failed")
        return fallback
    if not res.get("ok"):
        return fallback
    try:
        data = json.loads(_strip_json_fence(str(res.get("content") or "")))
    except json.JSONDecodeError:
        return fallback
    if not isinstance(data, dict):
        return fallback
    out = {**fallback}
    for k in (
        "employee_name",
        "employee_brief",
        "script_workflow_name",
        "script_brief",
        "script_runtime_notes",
        "workflow_name",
        "workflow_brief",
    ):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = v.strip()
    acc = data.get("acceptance")
    if isinstance(acc, list):
        out["acceptance"] = [str(x).strip() for x in acc if str(x).strip()][:8]
    return out


def _planning_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    """把前端需求规划材料固定进服务端会话，方便审计与重新生成。"""
    messages = payload.get("planning_messages")
    checklist = payload.get("execution_checklist")
    docs = payload.get("source_documents")
    return {
        "brief": (payload.get("brief") or "").strip(),
        "plan_notes": (payload.get("plan_notes") or "").strip(),
        "messages": messages if isinstance(messages, list) else [],
        "execution_checklist": checklist if isinstance(checklist, list) else [],
        "source_documents": docs if isinstance(docs, list) else [],
        "created_at": datetime.utcnow().isoformat() + "Z",
    }


def _commit_script_workflow_from_result(
    db: Session,
    *,
    user_id: int,
    session_id: str,
    payload: Dict[str, Any],
    files: List[Dict[str, Any]],
    result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """把工作台的一次性脚本结果保存为可继续沙箱调试的脚本工作流。"""
    code = str(result.get("script") or "").strip()
    if not result.get("ok") or not code:
        return None
    raw_name = str(payload.get("workflow_name") or "").strip()
    if not raw_name:
        raw_name = (str(payload.get("brief") or "").strip()[:40] or "Excel 文件处理")
    name = raw_name if raw_name.endswith("脚本工作流") else f"{raw_name} 脚本工作流"
    brief_json = _script_workflow_brief(payload, files)
    wf = ScriptWorkflow(
        user_id=user_id,
        name=name[:256],
        brief_json=json.dumps(brief_json, ensure_ascii=False),
        script_text=code,
        schema_in_json=json.dumps({}, ensure_ascii=False),
        status="sandbox_testing",
        agent_session_id=session_id,
    )
    db.add(wf)
    db.flush()
    version = ScriptWorkflowVersion(
        workflow_id=wf.id,
        version_no=1,
        script_text=code,
        plan_md="由工作台附件生成的初始脚本工作流。",
        agent_log_json=json.dumps(
            {"source": "workbench", "session_id": session_id},
            ensure_ascii=False,
        ),
        is_current=True,
    )
    db.add(version)
    db.flush()
    run = ScriptWorkflowRun(
        workflow_id=wf.id,
        version_id=version.id,
        user_id=user_id,
        mode="auto",
        status="success",
        stdout=str(result.get("stdout") or ""),
        stderr=str(result.get("stderr") or ""),
        outputs_meta_json=json.dumps(result.get("outputs") or [], ensure_ascii=False),
        runtime_sdk_calls_json=json.dumps(result.get("sdk_calls") or [], ensure_ascii=False),
        error_message="",
        completed_at=datetime.utcnow(),
    )
    db.add(run)
    wf.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(wf)
    return {"id": wf.id, "name": wf.name}


def _pipeline_task_failsafe(sid: str) -> Any:
    """Return a done-callback for asyncio tasks created from _run_pipeline.

    If the task raises an unhandled exception (any branch that forgot try/except),
    this callback marks the session as error and sets the first running step to error,
    preventing the zombie-session where status stays 'running' forever.
    """

    def _cb(task: "asyncio.Task[None]") -> None:  # type: ignore[type-arg]
        try:
            exc = task.exception()
        except (asyncio.CancelledError, Exception):
            exc = None
        if exc is None:
            return
        _LOG.exception(
            "workbench pipeline task failed unhandled session=%s err=%s",
            sid,
            exc,
            exc_info=exc,
        )
        err_msg = f"[内部错误] {type(exc).__name__}: {exc!s}"[:2000]
        # Synchronous fast-path: update in-memory dict without acquiring the async lock
        # (we are in a sync callback fired from the event loop).
        sess = WORKBENCH_SESSIONS.get(sid)
        if not sess:
            return
        if sess.get("status") == "running":
            sess["status"] = "error"
            sess["error"] = err_msg
        for s in sess.get("steps") or []:
            if s.get("status") == "running":
                s["status"] = "error"
                s["message"] = err_msg[:480]
                s.pop("started_at", None)
                break
        try:
            _persist_workbench_session_unlocked(sid)
        except Exception:  # noqa: BLE001
            pass

    return _cb


async def _run_pipeline(sid: str, user_id: int, payload: Dict[str, Any]) -> None:
    intent = _canonical_workbench_intent(str(payload.get("intent") or ""))
    payload["intent"] = intent
    execution_mode = str(payload.get("execution_mode") or "workflow")
    brief = (payload.get("brief") or "").strip()
    prov = (payload.get("provider") or "").strip() or None
    mdl = (payload.get("model") or "").strip() or None
    replace = bool(payload.get("replace", True))
    gen_wf_graph = bool(payload.get("generate_workflow_graph", True))
    generate_frontend = bool(payload.get("generate_frontend", True))

    sf = get_session_factory()
    with sf() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await _fail_session(sid, "spec", "用户不存在")
            return

        await _set_step(sid, "spec", "running")
        await _set_step(sid, "spec", "done")

        if execution_mode == "script":
            await _set_step(sid, "generate", "running", "正在生成处理脚本")
            await _set_step(sid, "validate", "pending")
            files = payload.get("_files") or []
            try:
                result = await run_script_job(
                    db=db,
                    user_id=user_id,
                    session_id=sid,
                    brief=brief,
                    files=files,
                    provider=prov,
                    model=mdl,
                )
            except Exception as e:  # noqa: BLE001
                msg = str(e)[:800]
                await _set_step(sid, "generate", "error", msg)
                await _fail_session(sid, "generate", msg)
                return
            await _set_step(sid, "generate", "done", "脚本已生成")
            if result.get("errors"):
                await _set_step(sid, "validate", "error", "；".join(result.get("errors") or []))
                await _fail_session(sid, "validate", "；".join(result.get("errors") or []))
                async with _SESSION_LOCK:
                    sess = WORKBENCH_SESSIONS.get(sid)
                    if sess:
                        sess["script_result"] = result
                        sess["artifact"] = {"execution_mode": "script", "outputs": []}
                        _persist_workbench_session_unlocked(sid)
                return
            await _set_step(sid, "validate", "done", "安全检查通过")
            await _set_step(sid, "run", "running", "正在执行脚本")
            script_wf: Optional[Dict[str, Any]] = None
            if not result.get("ok"):
                await _set_step(sid, "run", "error", (result.get("stderr") or "脚本执行失败")[:300])
                await _fail_session(sid, "run", (result.get("stderr") or "脚本执行失败")[:1000])
            else:
                try:
                    script_wf = _commit_script_workflow_from_result(
                        db,
                        user_id=user_id,
                        session_id=sid,
                        payload=payload,
                        files=files,
                        result=result,
                    )
                except Exception as e:  # noqa: BLE001
                    msg = f"保存脚本工作流失败: {e}"
                    await _set_step(sid, "run", "error", msg[:300])
                    await _fail_session(sid, "run", msg[:1000])
                    async with _SESSION_LOCK:
                        sess = WORKBENCH_SESSIONS.get(sid)
                        if sess:
                            sess["script_result"] = result
                            sess["artifact"] = {"execution_mode": "script", "outputs": []}
                            _persist_workbench_session_unlocked(sid)
                    return
                await _set_step(sid, "run", "done", f"生成 {len(result.get('outputs') or [])} 个文件")
                await _set_step(sid, "complete", "done")
            async with _SESSION_LOCK:
                sess = WORKBENCH_SESSIONS.get(sid)
                if sess:
                    sess["script_result"] = result
                    sess["status"] = "done" if result.get("ok") else "error"
                    sess["artifact"] = {
                        "execution_mode": "script",
                        "script_workflow_id": script_wf.get("id") if script_wf else None,
                        "script_workflow_name": script_wf.get("name") if script_wf else None,
                        "outputs": [
                            {
                                "filename": o.get("filename"),
                                "size": o.get("size"),
                                "download_url": f"/api/workbench/sessions/{sid}/files/{o.get('filename')}",
                            }
                            for o in (result.get("outputs") or [])
                        ],
                    }
                    if not result.get("ok"):
                        sess["error"] = (result.get("stderr") or "脚本执行失败")[:1000]
                    _persist_workbench_session_unlocked(sid)
            return

        if intent == "mod":
            if not bool(payload.get("generate_full_suite", True)):
                await _set_step(sid, "manifest", "running", "正在生成最小 manifest")
                res = await run_mod_ai_scaffold_async(
                    db,
                    user,
                    brief=brief,
                    suggested_id=payload.get("suggested_mod_id"),
                    replace=replace,
                    provider=prov,
                    model=mdl,
                )
                if not res.get("ok"):
                    await _fail_session(sid, "manifest", res.get("error") or "生成失败")
                    return
                await _set_step(sid, "manifest", "done", "manifest 已生成")
                await _set_step(sid, "repo", "done", f"Mod 仓库：{res.get('id')}")
                for skipped in ("industry", "employees", "workflows", "api", "workflow_sandbox"):
                    await _set_step(sid, skipped, "done", "最小 Mod 模式跳过")
                await _set_step(sid, "mod_sandbox", "running", "正在做轻量 Mod 校验")
                mod_dir = Path(res["path"])
                warns = mod_compileall_warnings(mod_dir)
                await _set_step(sid, "mod_sandbox", "done", "；".join(warns) if warns else "轻量校验通过")
                await _set_step(sid, "complete", "done")
                async with _SESSION_LOCK:
                    sess = WORKBENCH_SESSIONS.get(sid)
                    if sess:
                        sess["validate_warnings"] = warns
                        _persist_workbench_session_unlocked(sid)
                await _finalize_session_done(
                    sid,
                    {
                        "mod_id": res["id"],
                        "workflow_results": [],
                        "blueprint": None,
                        "validation_summary": {"ok": not warns, "python_warnings": warns},
                    },
                )
                return

            await _set_step(sid, "manifest", "running", "正在生成结构化 Mod 蓝图 JSON")
            gen = await generate_mod_suite_blueprint_async(
                db,
                user,
                brief=brief,
                suggested_id=payload.get("suggested_mod_id"),
                provider=prov,
                model=mdl,
            )
            if not gen.get("ok"):
                await _fail_session(sid, "manifest", gen.get("error") or "蓝图生成失败")
                return
            parsed = gen["parsed"]
            manifest = parsed["manifest"]
            employees = parsed.get("employees") or []
            blueprint = parsed.get("blueprint") or {}
            repair_note = "；已自动修复 JSON" if gen.get("repair_used") else ""
            await _set_step(
                sid,
                "manifest",
                "done",
                f"manifest.id={manifest.get('id')}，员工 {len(employees)} 名{repair_note}",
            )

            _pipeline_resources: List[Dict[str, Any]] = []

            async def _abort_mod_pipeline(step_id: str, err: str) -> None:
                _cleanup_mod_pipeline_resources(db, _pipeline_resources)
                await _fail_session(sid, step_id, err)

            try:
                await _set_step(sid, "repo", "running", "正在新建或覆盖 Mod 仓库")
                imported = import_mod_suite_repository(
                    db,
                    user,
                    parsed=parsed,
                    replace=replace,
                    generate_frontend=generate_frontend,
                )
                if not imported.get("ok"):
                    await _fail_session(sid, "repo", imported.get("error") or "Mod 仓库创建失败")
                    return
                # import 可能补全 parsed.blueprint.frontend_app，与本地 blueprint 变量再对齐
                blueprint = parsed.get("blueprint") or blueprint
                mod_dir = Path(imported["path"])
                _pipeline_resources.append({"type": "mod_dir", "path": str(mod_dir)})
                repo_done = f"已写入 {imported.get('id')}"
                if generate_frontend:
                    repo_done += (
                        "；含 Vue 定制页（frontend/routes.js、frontend/views/HomeView.vue）"
                        + ("，frontend_app 由模型省略已自动补齐" if imported.get("had_frontend_fallback") else "")
                    )
                await _set_step(sid, "repo", "done", repo_done)

                await _set_step(sid, "industry", "running", "正在写入行业卡片")
                try:
                    industry_card = write_mod_suite_industry_card(mod_dir, blueprint)
                    ui_shell = write_mod_suite_ui_shell(mod_dir, blueprint)
                except Exception as e:  # noqa: BLE001
                    await _abort_mod_pipeline("industry", f"行业/UI 配置生成失败: {e}")
                    return
                await _set_step(
                    sid,
                    "industry",
                    "done",
                    f"{industry_card.get('name') or '通用'}；侧栏 {len(ui_shell.get('sidebar_menu') or [])} 项",
                )

                await _set_step(sid, "employees", "running", f"正在创建 {len(employees)} 名员工骨架")
                await _set_step(sid, "employees", "done", f"已写入 workflow_employees：{len(employees)} 名")

                employees_for_llm = employees[:_MAX_EMPLOYEES_FOR_LLM]
                if len(employees) > _MAX_EMPLOYEES_FOR_LLM:
                    await _set_step(
                        sid,
                        "employee_impls",
                        "running",
                        f"员工数 {len(employees)} 超过 LLM 上限 {_MAX_EMPLOYEES_FOR_LLM}，"
                        f"仅前 {_MAX_EMPLOYEES_FOR_LLM} 名请求模型；其余写入兜底实现…",
                    )
                    emp_dir = mod_dir / "backend" / "employees"
                    emp_dir.mkdir(parents=True, exist_ok=True)
                    for emp in employees[_MAX_EMPLOYEES_FOR_LLM:]:
                        if not isinstance(emp, dict):
                            continue
                        eid = str(emp.get("id") or "").strip()
                        if not eid:
                            continue
                        stem = sanitize_employee_stem(eid)
                        label = str(emp.get("label") or emp.get("panel_title") or eid).strip()
                        panel_summary = str(emp.get("panel_summary") or "").strip()
                        fb = _fallback_employee_py(eid, label, panel_summary)
                        (emp_dir / f"{stem}.py").write_text(fb, encoding="utf-8")

                # 新步骤：为每员工生成真实 Python 实现（backend/employees/<stem>.py）
                await _set_step(sid, "employee_impls", "running", "开始为每员工生成可执行脚本…")

                async def _emp_impl_step_msg(text: str) -> None:
                    await _set_step(sid, "employee_impls", "running", text)

                try:
                    impl_result = await generate_mod_employee_impls_async(
                        db,
                        user,
                        mod_dir=mod_dir,
                        employees=employees_for_llm,
                        mod_id=str(manifest.get("id") or mod_dir.name),
                        mod_name=str(manifest.get("name") or manifest.get("id") or mod_dir.name),
                        mod_brief=brief,
                        industry_card=industry_card,
                        provider=gen.get("provider"),
                        model=gen.get("model"),
                        status_hook=_emp_impl_step_msg,
                    )
                except Exception as exc:  # noqa: BLE001
                    _LOG.exception("workbench mod employee_impls failed session=%s", sid)
                    await _abort_mod_pipeline(
                        "employee_impls",
                        f"生成员工脚本异常（可查看服务端日志）: {exc!s}"[:1000],
                    )
                    return
                impl_errs = impl_result.get("errors") or []
                impl_done_msg = (
                    f"已生成 {len(impl_result.get('generated') or [])} 份员工脚本"
                    + (f"，{len(impl_errs)} 份走兜底实现" if impl_errs else "")
                )
                await _set_step(sid, "employee_impls", "done", impl_done_msg)

                await _set_step(
                    sid,
                    "workflows",
                    "running",
                    "开始生成员工 Skill 组（画布节点与连线；ESkill 口径下单节点即 Skill）…",
                )

                async def _workflows_step_msg(text: str) -> None:
                    await _set_step(sid, "workflows", "running", text)

                wf = await create_mod_suite_workflows_async(
                    db,
                    user,
                    mod_dir=mod_dir,
                    employees=employees,
                    brief=brief,
                    provider=gen.get("provider"),
                    model=gen.get("model"),
                    step_message_hook=_workflows_step_msg,
                )
                workflow_results = wf.get("workflow_results") or []
                wf_ids = [
                    x.get("workflow_id")
                    for x in workflow_results
                    if isinstance(x, dict) and x.get("workflow_id") is not None
                ]
                _pipeline_resources.append({"type": "workflow_ids", "ids": wf_ids})
                failed_workflows = [
                    x for x in workflow_results if isinstance(x, dict) and not x.get("ok", True)
                ]
                await _set_step(
                    sid,
                    "workflows",
                    "done",
                    f"已生成 {len(workflow_results)} 条工作流，失败 {len(failed_workflows)} 条",
                )

                # 新步骤：自动修复画布 employee 节点 id 对齐 + 五维审核登记 Catalog
                await _set_step(sid, "register_packs", "running", "修复画布员工节点对齐…")
                graph_patch_result = patch_workflow_graph_employee_nodes(
                    db, user, mod_dir=mod_dir, workflow_results=workflow_results
                )

                async def _register_step_msg(text: str) -> None:
                    await _set_step(sid, "register_packs", "running", text)

                register_result = await register_mod_employee_packs_async(
                    db,
                    user,
                    mod_dir=mod_dir,
                    workflow_results=workflow_results,
                    status_hook=_register_step_msg,
                    industry=str((industry_card or {}).get("name") or "通用"),
                )
                _pipeline_resources.append(
                    {
                        "type": "catalog_by_pkg",
                        "pkg_id": str(imported.get("id") or manifest.get("id") or mod_dir.name),
                    }
                )
                reg_errs = register_result.get("errors") or []
                patches = graph_patch_result.get("patches") or []
                patch_updates = sum(1 for p in patches if p.get("action") in ("update", "insert"))
                reg_done_msg = (
                    f"画布修复 {patch_updates} 处；已登记 {len(register_result.get('registered') or [])} 个员工包"
                    + (f"，{len(reg_errs)} 个失败" if reg_errs else "")
                )
                await _set_step(sid, "register_packs", "done", reg_done_msg)

                await _set_step(sid, "api", "running", "正在汇总 OpenAPI 节点")
                api_summary = {
                    "nodes": wf.get("api_nodes") or [],
                    "warnings": wf.get("api_warnings") or [],
                }
                api_msg = (
                    f"发现 {len(api_summary['nodes'])} 个 API 节点"
                    + (f"，{len(api_summary['warnings'])} 个待配置" if api_summary["warnings"] else "")
                )
                await _set_step(sid, "api", "done", api_msg)

                await _set_step(sid, "workflow_sandbox", "running", "正在 mock 执行员工工作流")
                workflow_sandbox = run_mod_suite_workflow_sandboxes(db, user, workflow_results)
                await _set_step(
                    sid,
                    "workflow_sandbox",
                    "done",
                    "结构沙盒（Mock 员工）通过"
                    if workflow_sandbox.get("ok")
                    else "结构沙盒存在警告，请进入画布检查",
                )

                employee_readiness = analyze_mod_employee_readiness(db, user, mod_dir)
                blueprint["employee_impl_result"] = impl_result
                blueprint["graph_patch_result"] = graph_patch_result
                blueprint["pack_register_result"] = register_result
                vibe_heal_report = impl_result.get("vibe_heal") if isinstance(impl_result, dict) else None
                write_mod_suite_blueprint(
                    mod_dir,
                    blueprint,
                    workflow_results,
                    industry_card=industry_card,
                    ui_shell=ui_shell,
                    api_summary=api_summary,
                    workflow_sandbox=workflow_sandbox,
                    employee_readiness=employee_readiness,
                    vibe_heal=vibe_heal_report if isinstance(vibe_heal_report, dict) else None,
                )

                await _set_step(sid, "mod_sandbox", "running", "正在校验 Mod manifest、蓝图与路由骨架")
                mod_sandbox = run_mod_suite_mod_sandbox(mod_dir, workflow_results)
                validation_summary = {
                    "mod_sandbox": mod_sandbox,
                    "api_warnings": api_summary["warnings"],
                    "workflow_warnings": [
                        str(item.get("error") or item.get("graph", {}).get("error") or "")
                        for item in workflow_results
                        if isinstance(item, dict) and not item.get("ok", True)
                    ],
                    "repair_suggestions": [],
                    "employee_readiness": employee_readiness,
                    "ok": bool(mod_sandbox.get("ok"))
                    and not failed_workflows
                    and bool(employee_readiness.get("ok")),
                }
                await _set_step(
                    sid,
                    "mod_sandbox",
                    "done",
                    "Mod 沙箱通过；员工真实执行仍需登记与非 Mock 验证"
                    if mod_sandbox.get("ok") and employee_readiness.get("ok")
                    else "Mod 沙箱或员工可用性存在缺口，已写入报告",
                )

                await _set_step(sid, "complete", "done")
                async with _SESSION_LOCK:
                    sess = WORKBENCH_SESSIONS.get(sid)
                    if sess:
                        sess["validate_warnings"] = (
                            api_summary["warnings"] + validation_summary["workflow_warnings"]
                        )
                        sess["sandbox_report"] = {"workflow": workflow_sandbox, "mod": mod_sandbox}
                        _persist_workbench_session_unlocked(sid)
                await _finalize_session_done(
                    sid,
                    {
                        "mod_id": imported["id"],
                        "workflow_results": workflow_results,
                        "blueprint": blueprint,
                        "industry_card": industry_card,
                        "ui_shell": ui_shell,
                        "api_summary": api_summary,
                        "workflow_sandbox": workflow_sandbox,
                        "employee_readiness": employee_readiness,
                        "mod_sandbox": mod_sandbox,
                        "validation_summary": validation_summary,
                        "employee_impls": impl_result,
                        "graph_patch": graph_patch_result,
                        "pack_register": register_result,
                    },
                )
            except Exception as e:  # noqa: BLE001
                _LOG.exception("workbench mod full suite failed session=%s", sid)
                await _abort_mod_pipeline("complete", str(e)[:2000])
                return

            return

        if intent == "employee":
            et = str(payload.get("employee_target") or "pack_only").strip().lower()
            embed_script_workflow = bool(payload.get("embed_script_workflow", True))
            wf_name = (payload.get("employee_workflow_name") or "").strip() or None
            fhd_base = (payload.get("fhd_base_url") or "").strip() or None
            _emp_current_step = "employee_plan"
            try:
                await _set_step(sid, "employee_plan", "running", "正在拆分员工、脚本工作流与 Skill 组职责")
                employee_plan = await _build_employee_orchestration_plan(
                    db,
                    user_id,
                    payload=payload,
                    provider=prov,
                    model=mdl,
                )
                await _set_step(
                    sid,
                    "employee_plan",
                    "done",
                    f"已规划：{employee_plan.get('employee_name') or '员工'} / 脚本 / Skill 组",
                )

                employee_brief = str(employee_plan.get("employee_brief") or brief).strip() or brief
                script_brief = str(employee_plan.get("script_brief") or brief).strip() or brief
                script_hint = str(employee_plan.get("script_runtime_notes") or "").strip()
                workflow_brief = str(employee_plan.get("workflow_brief") or brief).strip() or brief
                planned_workflow_name = str(employee_plan.get("workflow_name") or "").strip() or None
                planned_script_name = str(employee_plan.get("script_workflow_name") or "").strip() or None

                _emp_current_step = "generate"
                await _set_step(sid, "generate", "running")
                res = await run_employee_ai_scaffold_async(
                    db,
                    user,
                    brief=employee_brief,
                    replace=replace,
                    provider=prov,
                    model=mdl,
                )
                if not res.get("ok"):
                    await _fail_session(sid, "generate", res.get("error") or "生成失败")
                    return
                await _set_step(sid, "generate", "done")

                _emp_current_step = "validate"
                await _set_step(sid, "validate", "running")
                async with _SESSION_LOCK:
                    sess = WORKBENCH_SESSIONS.get(sid)
                    if sess:
                        sess["validate_warnings"] = []
                        _persist_workbench_session_unlocked(sid)
                await _set_step(sid, "validate", "done", "manifest 已在导入时校验")

                pack_dir = Path(str(res.get("path") or ""))
                script_wf: Optional[Dict[str, Any]] = None
                script_attachment: Dict[str, Any] = {}
                script_result: Dict[str, Any] = {}
                _emp_current_step = "script_workflow"
                if embed_script_workflow:
                    await _set_step(sid, "script_workflow", "running", "正在生成员工配套小程序")

                    async def _script_progress(msg: str) -> None:
                        await _set_step(sid, "script_workflow", "running", msg)

                    script_result = await run_script_agent_job(
                        db=db,
                        user_id=user_id,
                        session_id=f"{sid}-employee-script",
                        brief=script_brief,
                        files=[],
                        provider=prov,
                        model=mdl,
                        system_hint=script_hint,
                        status_hook=_script_progress,
                    )
                    if script_result.get("errors"):
                        msg = "；".join(script_result.get("errors") or [])[:1500]
                        await _set_step(sid, "script_workflow", "error", msg)
                        await _fail_session(sid, "script_workflow", msg)
                        return
                    if not script_result.get("ok"):
                        msg = str(script_result.get("stderr") or "脚本工作流沙箱未通过")[:1000]
                        await _set_step(sid, "script_workflow", "error", msg)
                        await _fail_session(sid, "script_workflow", msg)
                        return
                    script_wf = _commit_script_workflow_from_result(
                        db,
                        user_id=user_id,
                        session_id=sid,
                        payload={
                            **payload,
                            "brief": script_brief,
                            "workflow_name": planned_script_name or wf_name or res.get("id") or "员工配套",
                        },
                        files=[],
                        result=script_result,
                    )
                    if not script_wf:
                        msg = "脚本已运行但未能保存为 ScriptWorkflow"
                        await _set_step(sid, "script_workflow", "error", msg)
                        await _fail_session(sid, "script_workflow", msg)
                        return
                    await _set_step(
                        sid,
                        "script_workflow",
                        "done",
                        f"已生成脚本工作流 id={script_wf.get('id')}",
                    )
                else:
                    await _set_step(sid, "script_workflow", "done", "已跳过：未开启配套小程序")

                wf_attach: Dict[str, Any] = {}
                saved_package: Dict[str, Any] = res.get("package") or {}
                _emp_current_step = "embed_script"
                if embed_script_workflow and script_wf:
                    await _set_step(sid, "embed_script", "running", "正在把配套小程序绑定到员工能力")
                    script_attachment = _embed_script_workflow_in_employee_pack(
                        pack_dir,
                        script_workflow=script_wf,
                        brief=script_brief,
                        db=db,
                    )
                    saved_package = _refresh_employee_pack_catalog_zip(db, user, pack_dir)
                    await _set_step(
                        sid,
                        "embed_script",
                        "done",
                        f"已写入脚本工作流 id={script_attachment.get('script_workflow_id')}",
                    )
                else:
                    await _set_step(sid, "embed_script", "done", "已跳过：未绑定配套小程序")
                _emp_current_step = "workflow"
                await _set_step(sid, "workflow", "running", "正在创建自动化流程…")

                async def _emp_wf_msg(text: str) -> None:
                    await _set_step(sid, "workflow", "running", text)

                if et == "pack_plus_workflow":
                    wf_attach = await attach_nl_workflow_to_employee_pack_dir(
                        db,
                        user,
                        pack_dir=pack_dir,
                        brief=workflow_brief,
                        workflow_name=wf_name or planned_workflow_name,
                        provider=prov,
                        model=mdl,
                        status_hook=_emp_wf_msg,
                    )
                    # attach_nl_workflow_to_employee_pack_dir mutates library/<pack>/manifest.json.
                    # Persist those new employee_config_v2/workflow fields back into the stored
                    # .xcemp so /api/employees/{id}/manifest and runtime execution see them.
                    saved_package = _refresh_employee_pack_catalog_zip(db, user, pack_dir)
                    _eskill_n = int(wf_attach.get("eskill_count") or 0)
                    _nl_ok = (wf_attach.get("nl") or {}).get("ok")
                    if _eskill_n:
                        wmsg = (
                            f"已创建工作流 id={wf_attach.get('workflow_id')}；"
                            f"注入 {_eskill_n} 个真脚本 Skill，NL 编排{'成功' if _nl_ok else '有提示'}"
                        )
                    else:
                        wmsg = (
                            f"已创建工作流 id={wf_attach.get('workflow_id')}；NL 生图"
                            f"{'成功' if _nl_ok else '有提示'}"
                        )
                    await _set_step(sid, "workflow", "done", wmsg[:480])
                else:
                    await _set_step(
                        sid,
                        "workflow",
                        "done",
                        "已跳过：当前为「仅员工包」模式；若需画布请选 pack_plus_workflow 并重新编排",
                    )

                _emp_current_step = "workflow_sandbox"
                await _set_step(sid, "workflow_sandbox", "running", "工作流 Mock 沙箱")
                workflow_sandbox: Dict[str, Any]
                wid = wf_attach.get("workflow_id") if isinstance(wf_attach, dict) else None
                if et == "pack_plus_workflow" and wid:
                    report = run_workflow_sandbox(
                        int(wid),
                        {},
                        mock_employees=True,
                        validate_only=True,
                        user_id=user.id,
                    )
                    record_workflow_sandbox_run(
                        db,
                        workflow_id=int(wid),
                        user_id=user.id,
                        report=report,
                        validate_only=True,
                        mock_employees=True,
                    )
                    workflow_sandbox = {
                        "ok": bool(report.get("ok")),
                        "skipped": False,
                        "workflow_id": int(wid),
                        "reports": [report],
                    }
                    await _set_step(
                        sid,
                        "workflow_sandbox",
                        "done",
                        "结构沙盒（validate_only）完成" if report.get("ok") else "沙箱有提示，请进画布查看",
                    )
                else:
                    wf_skip_msg = (
                        "已跳过 Mock：未创建画布工作流或模式为仅员工包。"
                        "完整双沙箱见「做 Mod」或 pack_plus_workflow 模式。"
                    )
                    workflow_sandbox = {"ok": True, "skipped": True, "reason": wf_skip_msg, "reports": []}
                    await _set_step(sid, "workflow_sandbox", "done", wf_skip_msg[:520])

                _emp_current_step = "mod_sandbox"
                await _set_step(sid, "mod_sandbox", "running", "正在校验包体（manifest / Python）")
                mod_checks: List[Dict[str, Any]] = []
                if pack_dir.is_dir():
                    _mf, mf_err = read_manifest(pack_dir)
                    mod_checks.append(
                        {"id": "manifest", "ok": mf_err is None, "message": mf_err or "manifest 可读取"},
                    )
                    py_warns = mod_compileall_warnings(pack_dir)
                    mod_checks.append(
                        {
                            "id": "python_compile",
                            "ok": not py_warns,
                            "message": "；".join(py_warns) if py_warns else "未发现需编译的 Python 或检查通过",
                        },
                    )
                    # 员工包一致性静态校验：max_tokens / handlers / try-call_llm / 返回 schema
                    cons_warns = employee_pack_consistency_warnings(pack_dir)
                    mod_checks.append(
                        {
                            "id": "employee_pack_consistency",
                            "ok": not cons_warns,
                            "message": "；".join(cons_warns)[:1200] if cons_warns else "manifest ↔ employees 一致性检查通过",
                        },
                    )

                    # ── vibe-coding 实质性检查 ─────────────────────────────────────
                    # 当画布 Skill 组里包含 vibe_code/vibe_workflow logic 时，
                    # 验证员工包是否具备"怎么做"能力：
                    #   1. vibe_logic_present   – 是否声明了 vibe_code/vibe_workflow
                    #   2. system_prompt_quality – SYSTEM_PROMPT 不为空洞占位
                    #   3. how_to_do_logic       – employees/*.py 含真实业务步骤标志
                    vibe_checks = _check_vibe_coding_capability(pack_dir, wf_attach)
                    mod_checks.extend(vibe_checks)
                else:
                    mod_checks.append({"id": "manifest", "ok": False, "message": f"包目录无效: {pack_dir}"})

                emp_mod_sandbox = {
                    "ok": all(c.get("ok") for c in mod_checks) if mod_checks else False,
                    "checks": mod_checks,
                    "note": "员工包轻量校验（含 backend/blueprints 运行时与 vibe-coding 能力检查）",
                }
                _all_pass = emp_mod_sandbox["ok"]
                _vibe_gaps = [c for c in mod_checks if not c.get("ok") and "vibe" in c.get("id", "")]
                if _all_pass:
                    mod_sb_msg = "包体轻量校验通过"
                elif _vibe_gaps:
                    mod_sb_msg = "基础校验通过，vibe-coding 能力存在缺口：" + "；".join(
                        c.get("message", "") for c in _vibe_gaps
                    )
                else:
                    mod_sb_msg = "包体校验有提示，见会话 artifact.mod_sandbox"
                await _set_step(sid, "mod_sandbox", "done", mod_sb_msg[:480])

                # ── standalone_smoke：验证 .xcemp 可作为 zipapp 独立运行 ────────
                _emp_current_step = "standalone_smoke"
                await _set_step(sid, "standalone_smoke", "running", "正在生成独立包并验证 python xxx.xcemp validate …")
                _standalone_smoke_ok = False
                _standalone_smoke_msg = "跳过（未能获取包字节）"
                try:
                    import asyncio as _asyncio
                    import sys as _sys
                    import tempfile as _tempfile
                    from modstore_server.employee_pack_export import _build_employee_pack_zip_with_source
                    from modstore_server.employee_ai_scaffold import build_employee_pack_zip

                    # 取当前会话中已保存的 manifest；若没有则仅标记 skip
                    _sess_now = WORKBENCH_SESSIONS.get(sid)
                    _sm_manifest = (
                        (_sess_now.get("artifact") or {}).get("manifest")
                        if isinstance(_sess_now, dict)
                        else None
                    )
                    if _sm_manifest and isinstance(_sm_manifest, dict):
                        _sm_pid = str(_sm_manifest.get("id") or "employee-pack").strip() or "employee-pack"
                        _sm_zip_bytes = _build_employee_pack_zip_with_source(_sm_pid, _sm_manifest, None)
                        with _tempfile.NamedTemporaryFile(
                            suffix=".xcemp", delete=False
                        ) as _tf:
                            _tf.write(_sm_zip_bytes)
                            _tmp_xcemp = _tf.name
                        try:
                            _proc = await _asyncio.wait_for(
                                _asyncio.create_subprocess_exec(
                                    _sys.executable, _tmp_xcemp, "validate",
                                    stdout=_asyncio.subprocess.PIPE,
                                    stderr=_asyncio.subprocess.PIPE,
                                ),
                                timeout=20,
                            )
                            _stdout, _stderr = await _asyncio.wait_for(
                                _proc.communicate(), timeout=20
                            )
                            if _proc.returncode == 0:
                                _standalone_smoke_ok = True
                                _standalone_smoke_msg = f"独立运行 OK — python {_sm_pid}.xcemp validate 通过"
                            else:
                                _out_text = (_stderr or _stdout or b"").decode("utf-8", errors="replace")[:300]
                                _standalone_smoke_msg = f"validate 退出码 {_proc.returncode}（降级为 warning）: {_out_text}"
                        except Exception as _se:
                            _standalone_smoke_msg = f"子进程异常（降级为 warning）: {_se}"
                        finally:
                            try:
                                import os as _os
                                _os.unlink(_tmp_xcemp)
                            except Exception:
                                pass
                    else:
                        _standalone_smoke_msg = "manifest 尚未生成，独立自检跳过"
                        _standalone_smoke_ok = True  # 非阻断性
                except Exception as _smoke_exc:
                    _standalone_smoke_msg = f"独立自检异常（降级为 warning）: {_smoke_exc}"
                # standalone_smoke 失败不阻断流程，仅作 warning
                await _set_step(sid, "standalone_smoke", "done", _standalone_smoke_msg[:480])

                _emp_current_step = "host_check"
                host_probe: Dict[str, Any] = {"skipped": True}
                await _set_step(sid, "host_check", "running", "探测宿主 /api/mods/")
                if fhd_base:
                    try:
                        from modstore_server.infrastructure.http_clients import get_external_client

                        base = fhd_base.rstrip("/")
                        host_warnings: List[str] = []
                        client = get_external_client()
                        r = await client.get(f"{base}/api/mods/", timeout=10.0)
                        host_probe = {
                            "skipped": False,
                            "ok": r.status_code < 500,
                            "status_code": r.status_code,
                            "url": f"{base}/api/mods/",
                        }
                        try:
                            lr = await client.get(f"{base}/api/mods/llm-status")
                            if lr.status_code == 200:
                                try:
                                    lj = lr.json()
                                    if isinstance(lj, dict) and lj.get("api_key_configured") is False:
                                        host_warnings.append(
                                            "宿主返回 llm-status：未配置 LLM API Key，员工运行时可能无法调用模型"
                                        )
                                except Exception:
                                    host_warnings.append("llm-status 返回非 JSON，跳过密钥探测")
                            elif lr.status_code == 404:
                                host_warnings.append(
                                    "宿主未提供 /api/mods/llm-status（可选），无法在编排阶段探测 LLM 密钥"
                                )
                        except Exception:
                            host_warnings.append("无法请求宿主 /api/mods/llm-status（可选端点）")

                        try:
                            vr = await client.get(f"{base}/api/version")
                            if vr.status_code == 200:
                                try:
                                    vj = vr.json()
                                    if isinstance(vj, dict) and vj.get("min_mod_sdk_version"):
                                        host_probe["host_min_mod_sdk_version"] = str(
                                            vj.get("min_mod_sdk_version") or ""
                                        )
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        msg = (
                            f"HTTP {r.status_code}"
                            if host_probe.get("ok")
                            else f"HTTP {r.status_code}（异常）"
                        )
                        if host_warnings:
                            msg += "；" + "；".join(host_warnings[:3])[:400]
                            host_probe["warnings"] = host_warnings
                        await _set_step(sid, "host_check", "done", msg[:480])
                    except Exception as e:  # noqa: BLE001
                        host_probe = {"skipped": False, "ok": False, "error": str(e)[:300]}
                        await _set_step(sid, "host_check", "done", f"探测失败: {e!s}"[:300])
                else:
                    await _set_step(sid, "host_check", "done", "未配置 fhd_base_url，已跳过")

                _emp_current_step = "complete"
                await _set_step(sid, "complete", "done")
                async with _SESSION_LOCK:
                    sess = WORKBENCH_SESSIONS.get(sid)
                    if sess:
                        sess["sandbox_report"] = {"workflow": workflow_sandbox, "mod": emp_mod_sandbox}
                        _persist_workbench_session_unlocked(sid)
                emp = (res.get("manifest") or {}).get("employee") or {}
                await _finalize_session_done(
                    sid,
                    {
                        "pack_id": res["id"],
                        "employee_id": res["id"],
                        "manifest_employee_id": emp.get("id") or res["id"],
                        "name": (res.get("manifest") or {}).get("name"),
                        "description": (res.get("manifest") or {}).get("description"),
                        "workflow_id": wid,
                        "package": saved_package,
                        "workflow_sandbox": workflow_sandbox,
                        "mod_sandbox": emp_mod_sandbox,
                        "employee_target": et,
                        "employee_orchestration_plan": employee_plan,
                        "workflow_attachment": wf_attach,
                        "script_workflow": script_wf,
                        "script_workflow_attachment": script_attachment,
                        "host_probe": host_probe,
                        "validation_summary": {
                            "ok": bool(emp_mod_sandbox.get("ok")),
                            "mod_sandbox": emp_mod_sandbox,
                            "workflow_skipped": not bool(wid),
                        },
                    },
                )
            except Exception as e:  # noqa: BLE001
                _LOG.exception("workbench employee pipeline failed session=%s step=%s", sid, _emp_current_step)
                await _fail_session(sid, _emp_current_step, str(e)[:2000])
            return

        if intent == CANVAS_SKILL_INTENT:
            name = (payload.get("workflow_name") or "").strip()
            if not name:
                await _fail_session(sid, "generate", "请填写 Skill 组名称")
                return
            plan = (payload.get("plan_notes") or "").strip()
            full_desc = brief
            if plan:
                full_desc = f"{brief}\n\n—— 框架与排期 ——\n{plan}"
            _skill_current_step = "generate"
            try:
                await _set_step(sid, "generate", "running")
                wf = Workflow(
                    user_id=user.id,
                    name=name,
                    description=full_desc,
                    is_active=True,
                    kind="skill_group",
                )
                db.add(wf)
                db.commit()
                db.refresh(wf)
                wid = wf.id

                nl_meta: Dict[str, Any] = {
                    "generate_workflow_graph": gen_wf_graph,
                    "nodes_created": 0,
                    "edges_created": 0,
                    "sandbox_ok": True,
                    "validation_errors": [],
                    "llm_warnings": [],
                }
                if gen_wf_graph:

                    async def _workflow_graph_msg(text: str) -> None:
                        await _set_step(sid, "generate", "running", text)

                    nl = await apply_nl_workflow_graph(
                        db,
                        user,
                        workflow_id=wid,
                        brief=full_desc,
                        provider=prov,
                        model=mdl,
                        status_hook=_workflow_graph_msg,
                    )
                    if not nl.get("ok"):
                        try:
                            db.query(WorkflowEdge).filter(WorkflowEdge.workflow_id == wid).delete(
                                synchronize_session=False
                            )
                            db.query(WorkflowNode).filter(WorkflowNode.workflow_id == wid).delete(
                                synchronize_session=False
                            )
                            db.query(Workflow).filter(Workflow.id == wid).delete(
                                synchronize_session=False
                            )
                            db.commit()
                        except Exception:
                            db.rollback()
                        await _fail_session(
                            sid, "generate", nl.get("error") or "工作流图生成失败"
                        )
                        async with _SESSION_LOCK:
                            sess = WORKBENCH_SESSIONS.get(sid)
                            if sess:
                                sess["artifact"] = None
                                _persist_workbench_session_unlocked(sid)
                        return
                    nl_meta.update(
                        {
                            "nodes_created": int(nl.get("nodes_created") or 0),
                            "edges_created": int(nl.get("edges_created") or 0),
                            "sandbox_ok": bool(nl.get("sandbox_ok")),
                            "validation_errors": nl.get("validation_errors") or [],
                            "llm_warnings": nl.get("llm_warnings") or [],
                        }
                    )

                await _set_step(sid, "generate", "done")

                _skill_current_step = "validate"
                await _set_step(sid, "validate", "running")
                node_count = (
                    db.query(WorkflowNode).filter(WorkflowNode.workflow_id == wid).count()
                )
                if node_count == 0:
                    detail = "新建工作流暂无节点，进入画布后再添加节点并运行沙盒校验"
                    async with _SESSION_LOCK:
                        sess = WORKBENCH_SESSIONS.get(sid)
                        if sess:
                            sess["sandbox_report"] = None
                            sess["validate_warnings"] = []
                            _persist_workbench_session_unlocked(sid)
                    await _set_step(sid, "validate", "done", detail)
                else:
                    report = run_workflow_sandbox(
                        wid,
                        {},
                        mock_employees=True,
                        validate_only=True,
                        user_id=user.id,
                    )
                    record_workflow_sandbox_run(
                        db,
                        workflow_id=wid,
                        user_id=user.id,
                        report=report,
                        validate_only=True,
                        mock_employees=True,
                    )
                    errs = report.get("errors") or []
                    warns = report.get("warnings") or []
                    detail = None
                    if errs:
                        detail = "校验提示（可进画布修改）：" + "；".join(
                            str(e) for e in errs[:8]
                        )
                    elif warns:
                        detail = "提示：" + "；".join(str(w) for w in warns[:6])
                    async with _SESSION_LOCK:
                        sess = WORKBENCH_SESSIONS.get(sid)
                        if sess:
                            sess["sandbox_report"] = report
                            sess["validate_warnings"] = warns
                            _persist_workbench_session_unlocked(sid)
                    if not errs:
                        run_report = run_workflow_sandbox(
                            wid,
                            {},
                            mock_employees=True,
                            validate_only=False,
                            user_id=user.id,
                        )
                        record_workflow_sandbox_run(
                            db,
                            workflow_id=wid,
                            user_id=user.id,
                            report=run_report,
                            validate_only=False,
                            mock_employees=True,
                        )
                        nl_meta["sandbox_ok"] = bool(run_report.get("ok"))
                    # MVP：保留已生成图，不因 validate_only 错误而整体失败
                    await _set_step(sid, "validate", "done", detail)

                _skill_current_step = "complete"
                await _set_step(sid, "complete", "done")
                await _finalize_session_done(
                    sid,
                    _enrich_artifact_skill_aliases(
                        {
                            "workflow_id": wid,
                            "workflow_name": name,
                            **nl_meta,
                        },
                    ),
                )
            except Exception as e:  # noqa: BLE001
                _LOG.exception("workbench skill pipeline failed session=%s step=%s", sid, _skill_current_step)
                await _fail_session(sid, _skill_current_step, str(e)[:2000])
            return

        await _fail_session(sid, "spec", f"未知 intent: {intent}")


@router.post("/research-context", summary="联网检索摘要 + GitHub 公开资料（供需求规划）")
async def workbench_research_context(
    body: WorkbenchResearchBody,
    user: User = Depends(_get_current_user),
):
    """
    使用 Tavily 做通用网页检索（摘要仅用 API 返回字段，不抓取任意第三方 URL），
    并从结果与用户 brief 中解析 github.com 仓库，仅通过 api.github.com 拉取公开元数据与 README，
    拼成有上限的 context_pack。
    """
    out = await build_research_context(
        brief=body.brief,
        intent=body.intent,
        max_repos=body.max_repos,
        max_chars=body.max_chars,
        max_web=body.max_web,
        user_id=user.id,
    )
    if out.get("ok") is False and out.get("error") == "rate_limited":
        raise HTTPException(429, out.get("warnings", ["请求过于频繁"])[0])
    return out


@router.post("/sessions", summary="启动工作台 AI 编排（异步）")
async def create_workbench_session(
    body: WorkbenchSessionCreateBody,
    user: User = Depends(_get_current_user),
):
    sid = uuid.uuid4().hex[:24]
    payload = body.model_dump()
    async with _SESSION_LOCK:
        WORKBENCH_SESSIONS[sid] = {
            "id": sid,
            "user_id": user.id,
            "intent": body.intent,
            "status": "running",
            "steps": _default_steps(
                body.intent,
                body.execution_mode,
                employee_target=str(getattr(body, "employee_target", None) or "pack_only"),
            ),
            "planning_record": _planning_record(payload),
            "artifact": None,
            "error": None,
            "validate_warnings": None,
            "sandbox_report": None,
            "script_result": None,
        }
        _persist_workbench_session_unlocked(sid)
    _task = asyncio.create_task(_run_pipeline(sid, user.id, payload))
    _task.add_done_callback(_pipeline_task_failsafe(sid))
    return {"session_id": sid, "status": "running"}


@router.post("/script-sessions", summary="启动 AI + Python 文件处理任务")
async def create_workbench_script_session(
    metadata: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    user: User = Depends(_get_current_user),
):
    try:
        meta = json.loads(metadata or "{}")
    except json.JSONDecodeError as e:
        raise HTTPException(400, "metadata 必须是 JSON") from e
    brief = str(meta.get("brief") or "").strip()
    if len(brief) < 3:
        raise HTTPException(400, "brief 不能为空")
    raw_files: List[Dict[str, Any]] = []
    for f in files or []:
        content = await f.read()
        if len(content) > 30 * 1024 * 1024:
            raise HTTPException(400, f"文件过大: {f.filename}")
        raw_files.append({"filename": f.filename or "upload.bin", "content": content})
    if not raw_files:
        raise HTTPException(400, "请上传至少一个文件")

    sid = uuid.uuid4().hex[:24]
    payload = {
        "intent": CANVAS_SKILL_INTENT,
        "execution_mode": "script",
        "brief": brief,
        "workflow_name": meta.get("workflow_name"),
        "provider": meta.get("provider"),
        "model": meta.get("model"),
        "_files": raw_files,
    }
    async with _SESSION_LOCK:
        WORKBENCH_SESSIONS[sid] = {
            "id": sid,
            "user_id": user.id,
            "intent": CANVAS_SKILL_INTENT,
            "status": "running",
            "steps": _default_steps(CANVAS_SKILL_INTENT, "script"),
            "planning_record": _planning_record(payload),
            "artifact": None,
            "error": None,
            "validate_warnings": None,
            "sandbox_report": None,
            "script_result": None,
        }
        _persist_workbench_session_unlocked(sid)
    _script_task = asyncio.create_task(_run_pipeline(sid, user.id, payload))
    _script_task.add_done_callback(_pipeline_task_failsafe(sid))
    return {"session_id": sid, "status": "running"}


@router.get("/sessions/{session_id}", summary="查询编排会话（轮询）")
async def get_workbench_session(
    session_id: str,
    user: User = Depends(_get_current_user),
):
    async with _SESSION_LOCK:
        _hydrate_workbench_session_unlocked(session_id)
        sess = WORKBENCH_SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在或已过期")
    if sess.get("user_id") != user.id:
        raise HTTPException(403, "无权访问此会话")
    return {
        "id": sess["id"],
        "intent": _canonical_workbench_intent(str(sess.get("intent") or "")),
        "status": sess["status"],
        "steps": sess["steps"],
        "artifact": _enrich_artifact_skill_aliases(
            dict(sess["artifact"]) if isinstance(sess.get("artifact"), dict) else None
        ),
        "planning_record": sess.get("planning_record"),
        "error": sess.get("error"),
        "validate_warnings": sess.get("validate_warnings"),
        "script_result": {
            "ok": (sess.get("script_result") or {}).get("ok"),
            "stdout": (sess.get("script_result") or {}).get("stdout", ""),
            "stderr": (sess.get("script_result") or {}).get("stderr", ""),
            "outputs": [
                {
                    "filename": o.get("filename"),
                    "size": o.get("size"),
                    "download_url": f"/api/workbench/sessions/{session_id}/files/{o.get('filename')}",
                }
                for o in ((sess.get("script_result") or {}).get("outputs") or [])
            ],
        }
        if sess.get("script_result")
        else None,
    }


@router.get("/sessions/{session_id}/files/{filename}", summary="下载脚本执行结果文件")
async def download_workbench_session_file(
    session_id: str,
    filename: str,
    user: User = Depends(_get_current_user),
):
    async with _SESSION_LOCK:
        _hydrate_workbench_session_unlocked(session_id)
        sess = WORKBENCH_SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在或已过期")
    if sess.get("user_id") != user.id:
        raise HTTPException(403, "无权访问此会话")
    result = sess.get("script_result") or {}
    for o in result.get("outputs") or []:
        if o.get("filename") == filename:
            path = Path(str(o.get("path") or ""))
            if path.is_file():
                return FileResponse(path, filename=filename)
    raise HTTPException(404, "文件不存在")


class WorkbenchEdgeTtsBody(BaseModel):
    """与 Edge 浏览器「大声朗读」相同的在线神经语音（经 edge-tts 访问微软语音服务）。"""

    text: str = Field(..., min_length=1, max_length=5000)
    voice: str = Field("zh-CN-XiaoxiaoNeural", max_length=120)
    rate: float = Field(1.0, ge=0.6, le=1.6, description="相对语速，约映射到 Edge 的 rate 百分比")


class WorkbenchVibeCodeSkillBody(BaseModel):
    """工作台「AI 代码技能」: NL → vibe-coding CodeSkill → 试跑 → 可选发布。"""

    brief: str = Field(..., min_length=3, max_length=8000)
    run_input: Dict[str, Any] = Field(default_factory=dict)
    skill_id: Optional[str] = Field(None, max_length=128)
    mode: Literal["brief_first", "direct"] = "brief_first"
    dry_run: bool = Field(False, description="为 True 时只生成代码 + 试跑,不上架")
    provider: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=128)
    project_root: Optional[str] = Field(
        None,
        max_length=4096,
        description=(
            "可选：项目根目录（必须在用户工作区内）。"
            "非空时会先做目录扫描/技术栈分析并注入 brief，"
            "并把 project_analysis 自动加入 run_input，"
            "用于文档生成器/项目分析类 Skill。"
        ),
    )
    publish: Optional[Dict[str, Any]] = Field(
        None,
        description="非空时在试跑通过后调 SkillPublisher 上架到本 MODstore",
    )


@router.post("/vibe-code-skill", summary="vibe-coding NL → CodeSkill 全闭环")
async def workbench_vibe_code_skill(
    body: WorkbenchVibeCodeSkillBody,
    user: User = Depends(_get_current_user),
):
    """vibe-coding 端到端 API:生成代码、试跑、可选直接上架本 MODstore。

    本接口同步返回(单次代码生成大约 5-30 秒,取决于 LLM 速度);
    长时间任务请用「脚本工作流」。
    """
    from modstore_server.mod_scaffold_runner import resolve_llm_provider_model_auto

    sf = get_session_factory()
    with sf() as db:
        prov, mdl, err = await resolve_llm_provider_model_auto(
            db, user, body.provider, body.model
        )
        if err:
            raise HTTPException(400, err)

    def _do() -> Dict[str, Any]:
        try:
            from modstore_server.integrations.vibe_adapter import (
                VibeIntegrationError,
                VibePathError,
                ensure_within_workspace,
                get_vibe_coder,
            )
        except ImportError as exc:
            return {"ok": False, "error": f"未启用 vibe-coding 集成: {exc}"}

        # Validate project_root against the user workspace boundary.
        resolved_project_root: Optional[str] = None
        if body.project_root and body.project_root.strip():
            try:
                resolved_project_root = str(
                    ensure_within_workspace(body.project_root.strip(), user_id=int(user.id or 0))
                )
            except VibePathError as exc:
                return {"ok": False, "error": f"project_root 路径无效: {exc}"}
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"project_root 校验失败: {exc}"}

        sf2 = get_session_factory()
        with sf2() as session:
            try:
                coder = get_vibe_coder(
                    session=session,
                    user_id=int(user.id or 0),
                    provider=prov,
                    model=mdl,
                )
            except VibeIntegrationError as exc:
                return {"ok": False, "error": str(exc)}

            try:
                skill = coder.code(
                    body.brief.strip(),
                    mode=body.mode,
                    skill_id=(body.skill_id or None),
                    project_root=resolved_project_root,
                )
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"vibe-coding 生成失败: {exc}"}

            # Pre-compute project analysis and inject as run_input["project_analysis"]
            # so the generated Skill can process it without hitting the filesystem.
            run_input_final = dict(body.run_input or {})
            if resolved_project_root and "project_analysis" not in run_input_final:
                try:
                    from vibe_coding.code_factory import analyze_project  # type: ignore[import-not-found]
                    import json as _json
                    analysis = analyze_project(resolved_project_root)
                    run_input_final["project_analysis"] = _json.loads(
                        _json.dumps({
                            "root_name": analysis.root_name,
                            "manifests": analysis.manifests,
                            "top_level": analysis.top_level,
                            "languages": analysis.languages,
                            "tech_stack": analysis.tech_stack,
                            "entry_points": analysis.entry_points,
                            "config_files": analysis.config_files,
                            "readme_snippet": analysis.readme_snippet,
                            "git_info": analysis.git_info,
                        }, ensure_ascii=False)
                    )
                except Exception:  # noqa: BLE001
                    pass  # analysis is optional; proceed without it

            sid = getattr(skill, "skill_id", "") or ""
            run_dict: Optional[Dict[str, Any]] = None
            try:
                run_obj = coder.run(sid, run_input_final)
                run_dict = (
                    run_obj.to_dict()
                    if hasattr(run_obj, "to_dict") and callable(run_obj.to_dict)
                    else {"output": getattr(run_obj, "output", None)}
                )
            except Exception as exc:  # noqa: BLE001
                run_dict = {"ok": False, "error": f"试跑失败: {exc}"}

            skill_dict: Dict[str, Any]
            if hasattr(skill, "to_dict") and callable(skill.to_dict):
                skill_dict = dict(skill.to_dict())
            else:
                skill_dict = {
                    "skill_id": sid,
                    "code": getattr(skill, "code", "") or "",
                }

            publish_dict: Optional[Dict[str, Any]] = None
            if body.publish and not body.dry_run:
                publish_dict = _publish_vibe_skill_via_local_modstore(
                    coder, sid, body.publish, user_id=int(user.id or 0)
                )

            return {
                "ok": True,
                "provider": prov,
                "model": mdl,
                "skill": skill_dict,
                "run": run_dict,
                "publish": publish_dict,
                "project_root_used": resolved_project_root,
            }

    out = await asyncio.to_thread(_do)
    return out


def _publish_vibe_skill_via_local_modstore(
    coder: Any,
    skill_id: str,
    publish_cfg: Dict[str, Any],
    *,
    user_id: int,
) -> Dict[str, Any]:
    """直接调本 MODstore 的 catalog 上传接口,不用 HTTP 自调来回。

    用 vibe-coding 的 ``SkillPackager`` 打包(它知道 .xcmod 内部结构),
    再走 :func:`catalog_store.append_package` + ``CatalogItem`` 写库。
    """
    try:
        from vibe_coding.agent.marketplace import (  # type: ignore[import-not-found]
            PublishOptions,
            SkillPackager,
        )
    except ImportError as exc:
        return {"ok": False, "error": f"vibe-coding marketplace 未安装: {exc}"}

    pkg_id = str(publish_cfg.get("pkg_id") or "").strip()
    if not pkg_id:
        return {"ok": False, "error": "publish.pkg_id 必填"}
    artifact_kind = str(publish_cfg.get("artifact") or "mod").strip() or "mod"
    if artifact_kind not in ("mod", "employee_pack"):
        return {"ok": False, "error": f"不支持的 artifact: {artifact_kind}"}

    try:
        skill = coder.code_store.get_code_skill(skill_id)
    except KeyError:
        return {"ok": False, "error": f"skill_id 不存在: {skill_id}"}

    options = PublishOptions(
        pkg_id=pkg_id,
        version=str(publish_cfg.get("version") or "1.0.0"),
        name=str(publish_cfg.get("name") or pkg_id),
        description=str(publish_cfg.get("description") or ""),
        price=float(publish_cfg.get("price") or 0.0),
        artifact=artifact_kind,
        industry=str(publish_cfg.get("industry") or "通用"),
        author=f"user-{user_id}",
    )
    try:
        packager = SkillPackager()
        artifact = packager.package_skill(skill, options=options)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"打包失败: {exc}"}

    try:
        from modstore_server.catalog_store import append_package
        from modstore_server.models import CatalogItem

        rec = {
            "id": pkg_id,
            "name": options.name,
            "version": options.version,
            "description": options.description,
            "artifact": artifact_kind,
            "industry": options.industry,
            "release_channel": "stable",
            "commerce": {"mode": "free" if options.price <= 0 else "paid", "price": options.price},
            "license": {"type": "personal", "verify_url": None},
        }
        sf3 = get_session_factory()
        with sf3() as session:
            saved = append_package(rec, Path(artifact.archive_path))
            row = session.query(CatalogItem).filter(CatalogItem.pkg_id == pkg_id).first()
            if not row:
                row = CatalogItem(pkg_id=pkg_id, author_id=user_id)
                session.add(row)
            row.version = saved.get("version") or rec["version"]
            row.name = saved.get("name") or rec["name"]
            row.description = saved.get("description") or rec["description"]
            row.price = float(options.price)
            row.artifact = artifact_kind
            row.industry = saved.get("industry") or rec["industry"]
            row.stored_filename = saved.get("stored_filename") or ""
            row.sha256 = saved.get("sha256") or ""
            session.commit()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"上架到本地 MODstore 失败: {exc}",
            "artifact": getattr(artifact, "to_dict", lambda: {})(),
        }
    return {
        "ok": True,
        "pkg_id": pkg_id,
        "version": options.version,
        "artifact": getattr(artifact, "to_dict", lambda: {})(),
    }


@router.post("/tts/edge", summary="微软在线神经 TTS（edge-tts，返回 MP3）")
async def workbench_edge_tts(
    body: WorkbenchEdgeTtsBody,
    _user: User = Depends(_get_current_user),
):
    if _EDGE_TTS is None:
        raise HTTPException(
            503,
            "服务端未安装 edge-tts。请在部署环境执行: pip install 'modstore[web]' 或 pip install edge-tts",
        )
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "text 不能为空")
    voice = (body.voice or "zh-CN-XiaoxiaoNeural").strip()
    pct = int(round((float(body.rate) - 1.0) * 80))
    pct = max(-50, min(80, pct))
    rate_str = f"{pct:+d}%"
    try:
        communicate = _EDGE_TTS.Communicate(text, voice=voice, rate=rate_str)
        buf = BytesIO()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                buf.write(chunk["data"])
        audio = buf.getvalue()
        if not audio:
            raise HTTPException(502, "TTS 未返回音频数据")
        return Response(content=audio, media_type="audio/mpeg")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"TTS 合成失败: {exc}") from exc


# ── AI Employee Draft Pipeline (SSE) ─────────────────────────────────────────

@router.post("/employee-ai/draft", summary="6 阶段 AI 员工生成（SSE 流式）")
async def employee_ai_draft(
    body: EmployeeAiDraftBody,
    user: User = Depends(_get_current_user),
):
    """SSE 事件序列：stage_start / stage_progress / stage_done / stage_error / pipeline_done。

    ``pipeline_done`` 携带完整 manifest；客户端可在收到后离线编辑，再调 ``/api/mods/ai-scaffold``
    或 ``import_zip`` 落库上架（保持与现有 employee 工作台链路兼容）。
    """
    from modstore_server.employee_ai_pipeline import run_pipeline
    from modstore_server.script_agent.llm_client import RealLlmClient
    from modstore_server.llm_key_resolver import resolve_api_key, resolve_base_url, OAI_COMPAT_OPENAI_STYLE_PROVIDERS

    sf = get_session_factory()

    async def _stream():
        events: List[Dict[str, Any]] = []

        async def on_event(ev: Dict[str, Any]) -> None:
            events.append(ev)
            line = f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            yield line.encode()

        with sf() as db:
            prov, mdl, err = await resolve_llm_provider_model_auto(db, user, body.provider, body.model)
            if err:
                err_ev = {"event": "pipeline_error", "stage": "init", "error": err}
                yield f"data: {json.dumps(err_ev, ensure_ascii=False)}\n\n".encode()
                return

            api_key, _ = resolve_api_key(db, user.id, prov)
            if not api_key:
                err_ev = {"event": "pipeline_error", "stage": "init", "error": "该供应商未配置可用 API Key"}
                yield f"data: {json.dumps(err_ev, ensure_ascii=False)}\n\n".encode()
                return
            base_url = (
                resolve_base_url(db, user.id, prov)
                if prov in OAI_COMPAT_OPENAI_STYLE_PROVIDERS
                else None
            )
            llm = RealLlmClient(prov, api_key=api_key, model=mdl, base_url=base_url)

            # Fetch eligible workflows for stage 2 ranking
            from modstore_server.models import Workflow as WorkflowModel
            wf_rows = (
                db.query(WorkflowModel)
                .filter(WorkflowModel.user_id == user.id, WorkflowModel.is_active == True)  # noqa: E712
                .order_by(WorkflowModel.updated_at.desc())
                .limit(20)
                .all()
            )
            eligible_wfs = [
                {
                    "id": w.id,
                    "name": w.name or "",
                    "description": w.description or "",
                    "sandbox_passed": bool(getattr(w, "sandbox_passed_for_current_graph", False)),
                }
                for w in wf_rows
            ]

            async def _gen_wf_fallback() -> Dict[str, Any]:
                # Re-open a fresh session for the workflow creation call
                with sf() as db2:
                    return await generate_workflow_for_intent(
                        db2,
                        user,
                        role=body.brief[:40],
                        scenario=body.brief[:120],
                        workflow_name=f"AI 员工工作流 - {(body.suggested_id or body.brief[:16]).strip()}",
                        provider=prov,
                        model=mdl,
                    )

            # Yield events through the generator
            collected: List[Dict[str, Any]] = []

            async def on_event_gen(ev: Dict[str, Any]) -> None:
                collected.append(ev)

            # We need to bridge the async generator pattern with run_pipeline's callback
            # Use a queue to bridge
            import asyncio as _asyncio
            q: asyncio.Queue = _asyncio.Queue()

            async def _on_ev(ev: Dict[str, Any]) -> None:
                await q.put(ev)

            async def _run_and_sentinel() -> None:
                try:
                    await run_pipeline(
                        body.brief,
                        llm=llm,
                        on_event=_on_ev,
                        eligible_workflows=eligible_wfs,
                        generate_workflow_fallback=_gen_wf_fallback,
                    )
                finally:
                    await q.put(None)  # sentinel

            task = _asyncio.create_task(_run_and_sentinel())
            while True:
                ev = await q.get()
                if ev is None:
                    break
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode()
            await task

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/employee-ai/refine-prompt", summary="LLM 优化 system prompt")
async def employee_ai_refine_prompt(
    body: EmployeeAiRefinePromptBody,
    user: User = Depends(_get_current_user),
):
    """用 LLM 重写 employee system prompt，返回优化后文本与一句话 diff 说明。"""
    from modstore_server.employee_ai_pipeline import refine_system_prompt
    from modstore_server.script_agent.llm_client import RealLlmClient
    from modstore_server.llm_key_resolver import resolve_api_key, resolve_base_url, OAI_COMPAT_OPENAI_STYLE_PROVIDERS

    sf = get_session_factory()
    with sf() as db:
        prov, mdl, err = await resolve_llm_provider_model_auto(db, user, body.provider, body.model)
        if err:
            raise HTTPException(400, err)
        api_key, _ = resolve_api_key(db, user.id, prov)
        if not api_key:
            raise HTTPException(400, "该供应商未配置可用 API Key")
        base_url = (
            resolve_base_url(db, user.id, prov)
            if prov in OAI_COMPAT_OPENAI_STYLE_PROVIDERS
            else None
        )

    llm = RealLlmClient(prov, api_key=api_key, model=mdl, base_url=base_url)
    result, err = await refine_system_prompt(
        current_prompt=body.current_prompt,
        instruction=body.instruction,
        role_context=body.role_context,
        llm=llm,
    )
    if err or result is None:
        raise HTTPException(502, f"Prompt 优化失败: {err or '未知错误'}")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 员工上架：基准测试 + 五维审核 + 上架到目录
# ─────────────────────────────────────────────────────────────────────────────


class EmployeeBenchRequest(BaseModel):
    employee_id: str = Field(..., description="员工包 ID（同 pack_id）")
    provider: Optional[str] = Field(None)
    model: Optional[str] = Field(None)
    per_dimension_ids: Optional[Dict[str, str]] = Field(
        None,
        description=(
            "五维专属评分员工包映射 {维度键: employee_id}；"
            "有效键：manifest_compliance / declaration_completeness / "
            "api_testability_static / security_and_size / metadata_quality。"
            "合并优先级：环境变量 MODSTORE_AUDIT_DIM_* → LLM 自动从评审池挑选 → 本字段。"
            "未填满的维度可用服务端评审池（MODSTORE_BENCH_REVIEWER_POOL / *_FROM_CATALOG）自动补位。"
        ),
    )


class EmployeePublishRequest(BaseModel):
    employee_id: str = Field(..., description="员工包 ID（同 pack_id）")
    price: float = Field(0.0)
    industry: str = Field("通用", max_length=64)
    release_channel: str = Field("stable", max_length=32)


@router.post("/employee-bench-test", summary="员工上架前基准测试（LLM 生成任务 + 执行 + 五维审核）")
async def employee_bench_test(
    body: EmployeeBenchRequest,
    user: User = Depends(_get_current_user),
):
    """
    1. LLM 生成 1-5 级（每级 3 条）共 15 项测试任务
    2. 逐条执行并记录 ok / cost_tokens / duration_ms
    3. 量化打分 + 五维审核
    4. 返回完整报告，前端据此决定是否允许上架
    """
    from modstore_server.employee_bench import generate_bench_tasks, run_and_score_bench

    employee_id = (body.employee_id or "").strip()
    if not employee_id:
        raise HTTPException(400, "employee_id 不能为空")

    materialize_employee_pack_if_missing(employee_id)

    # 从本地库读 manifest 获取 brief + panel_summary
    pack_dir = modstore_library_path() / employee_id
    brief = ""
    panel_summary = ""
    mf_path = pack_dir / "manifest.json"
    if mf_path.is_file():
        try:
            mf = json.loads(mf_path.read_text(encoding="utf-8"))
            brief = (
                str(mf.get("description") or "")
                or str(mf.get("identity", {}).get("description") or "")
            )[:800]
            rows = mf.get("workflow_employees") or []
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                panel_summary = str(rows[0].get("panel_summary") or "").strip()[:400]
        except Exception:  # noqa: BLE001
            pass

    sf = get_session_factory()
    with sf() as db:
        from modstore_server.services.llm import resolve_platform_bench_llm
        prov, mdl = resolve_platform_bench_llm()
        if not prov or not mdl:
            raise HTTPException(
                503,
                "基准测试需要平台 LLM 密钥（服务端环境变量），当前未配置。"
                "请联系运维设置 MODSTORE_EMPLOYEE_BENCH_PROVIDER + MODSTORE_EMPLOYEE_BENCH_MODEL "
                "及对应供应商的 API Key 环境变量。",
            )

        try:
            task_list = await generate_bench_tasks(
                brief or employee_id,
                panel_summary,
                db=db,
                user_id=user.id,
                provider=prov,
                model=mdl,
                use_platform_dispatch=True,
                strict=True,
            )
        except RuntimeError as exc:
            raise HTTPException(502, f"基准任务生成失败（LLM 调用）：{exc}") from exc

        report = await run_and_score_bench(
            employee_id,
            task_list,
            db=db,
            user=user,
            bench_llm_override=(prov, mdl),
            per_dimension_ids=body.per_dimension_ids,
        )

    return {"ok": True, "employee_id": employee_id, **report}


@router.post("/employee-publish", summary="员工包上架到商店目录")
async def employee_publish(
    body: EmployeePublishRequest,
    user: User = Depends(_get_current_user),
):
    """
    将本地库中的员工包重建 zip 并写入商店目录（catalog_store + catalog_items）。
    调用方应先通过 /employee-bench-test 且 passed=true，再调此接口。
    """
    from modstore_server.catalog_store import append_package, package_manifest_alignment_errors
    from modstore_server.catalog_sync import upsert_catalog_item_from_xc_package_dict
    from modstore_server.models import CatalogItem

    employee_id = (body.employee_id or "").strip()
    if not employee_id:
        raise HTTPException(400, "employee_id 不能为空")

    materialize_employee_pack_if_missing(employee_id)

    pack_dir = modstore_library_path() / employee_id
    mf_path = pack_dir / "manifest.json"
    if not mf_path.is_file():
        raise HTTPException(404, f"员工包不存在: {employee_id}")

    try:
        raw_mf = _load_registry_aligned_employee_manifest(pack_dir, employee_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"manifest.json 读取失败: {exc}") from exc

    # 重建 zip
    try:
        pkg_id = str(raw_mf.get("id") or employee_id).strip() or employee_id
        zip_bytes = build_employee_pack_zip(pkg_id, raw_mf)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"员工包打包失败: {exc}") from exc

    version = str(raw_mf.get("version") or "1.0.0").strip()
    rec = {
        "id": pkg_id,
        "name": str(raw_mf.get("name") or pkg_id),
        "version": version,
        "description": str(raw_mf.get("description") or ""),
        "artifact": "employee_pack",
        "industry": body.industry or str(raw_mf.get("industry") or "通用"),
        "release_channel": body.release_channel or "stable",
        "commerce": {"mode": "free" if body.price <= 0 else "paid", "price": body.price},
        "license": {"type": "personal", "verify_url": None},
    }

    import tempfile as _tmpmod

    with _tmpmod.NamedTemporaryFile(suffix=".xcemp", delete=False) as tmp:
        tmp.write(zip_bytes)
        tmp_path = Path(tmp.name)

    try:
        align_errs = package_manifest_alignment_errors(rec, tmp_path)
        if align_errs:
            raise HTTPException(400, "员工包 metadata 与包内 manifest 不一致: " + "; ".join(align_errs))
        saved = append_package(rec, tmp_path)
    except Exception as exc:  # noqa: BLE001
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(500, f"写入 catalog_store 失败: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    sf = get_session_factory()
    with sf() as db:
        try:
            upsert_catalog_item_from_xc_package_dict(db, saved, author_id=user.id)
            # 同步写 CatalogItem（与现有流程一致）
            row = db.query(CatalogItem).filter(CatalogItem.pkg_id == pkg_id).first()
            if not row:
                row = CatalogItem(pkg_id=pkg_id, author_id=user.id)
                db.add(row)
            row.version = saved.get("version") or version
            row.name = saved.get("name") or rec["name"]
            row.description = saved.get("description") or rec["description"]
            row.price = float(body.price)
            row.artifact = "employee_pack"
            row.industry = saved.get("industry") or rec["industry"]
            row.stored_filename = saved.get("stored_filename") or ""
            row.sha256 = saved.get("sha256") or ""
            db.commit()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            raise HTTPException(500, f"写入数据库失败: {exc}") from exc

    return {
        "ok": True,
        "pkg_id": pkg_id,
        "version": saved.get("version") or version,
        "stored_filename": saved.get("stored_filename") or "",
        "name": saved.get("name") or rec["name"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 员工同步测试：bench → 发布到 catalog → 推送到宿主 fhd-sandbox-runtime
# ─────────────────────────────────────────────────────────────────────────────


class EmployeeSyncTestRequest(BaseModel):
    employee_id: str = Field(..., description="员工包 ID（同 pack_id）")
    fhd_base_url: Optional[str] = Field(None, description="宿主 fhd-sandbox-runtime 的 base URL，如 http://localhost:9999")
    provider: Optional[str] = Field(None)
    model: Optional[str] = Field(None)
    price: float = Field(0.0)
    industry: str = Field("通用", max_length=64)
    per_dimension_ids: Optional[Dict[str, str]] = Field(
        None,
        description=(
            "五维专属评分员工包映射 {维度键: employee_id}；"
            "与环境变量、自动评审池补位规则同 employee-bench-test。"
        ),
    )


@router.post("/employee-sync-test", summary="员工同步测试：bench→发布→推送到宿主安装")
async def employee_sync_test(
    body: EmployeeSyncTestRequest,
    user: User = Depends(_get_current_user),
):
    """
    一键同步流程：
    1. LLM 生成 1-5 级测试任务并执行 + 五维审核
    2. 通过后发布到 MODstore catalog（/v1/packages）
    3. 调用宿主 fhd-sandbox-runtime 的 /api/mod-store/install 安装此员工包
       → 员工出现在宿主「一键托管」面板、「员工工作流管理」页等位置
    """
    import httpx

    from modstore_server.employee_bench import generate_bench_tasks, run_and_score_bench
    from modstore_server.catalog_store import append_package, package_manifest_alignment_errors
    from modstore_server.catalog_sync import upsert_catalog_item_from_xc_package_dict
    from modstore_server.models import CatalogItem

    employee_id = (body.employee_id or "").strip()
    if not employee_id:
        raise HTTPException(400, "employee_id 不能为空")

    materialize_employee_pack_if_missing(employee_id)

    # ── Step 1: 读取员工信息 ──────────────────────────────────────────────────
    pack_dir = modstore_library_path() / employee_id
    mf_path = pack_dir / "manifest.json"
    if not mf_path.is_file():
        raise HTTPException(404, f"员工包不存在: {employee_id}")

    try:
        raw_mf = _load_registry_aligned_employee_manifest(pack_dir, employee_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"manifest.json 读取失败: {exc}") from exc

    brief = str(raw_mf.get("description") or "").strip()[:800]
    rows = raw_mf.get("workflow_employees") or []
    panel_summary = ""
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        panel_summary = str(rows[0].get("panel_summary") or "").strip()[:400]

    # ── Step 2: bench test using platform model ───────────────────────────────
    from modstore_server.services.llm import resolve_platform_bench_llm
    prov, mdl = resolve_platform_bench_llm()
    if not prov or not mdl:
        raise HTTPException(
            503,
            "同步测试需要平台 LLM 密钥（服务端环境变量），当前未配置。"
            "请联系运维设置 MODSTORE_EMPLOYEE_BENCH_PROVIDER + MODSTORE_EMPLOYEE_BENCH_MODEL "
            "及对应供应商的 API Key 环境变量。",
        )

    sf = get_session_factory()
    with sf() as db:
        try:
            task_list = await generate_bench_tasks(
                brief or employee_id,
                panel_summary,
                db=db,
                user_id=user.id,
                provider=prov,
                model=mdl,
                use_platform_dispatch=True,
                strict=True,
            )
        except RuntimeError as exc:
            raise HTTPException(502, f"基准任务生成失败（LLM 调用）：{exc}") from exc

        report = await run_and_score_bench(
            employee_id,
            task_list,
            db=db,
            user=user,
            bench_llm_override=(prov, mdl),
            per_dimension_ids=body.per_dimension_ids,
        )

    if not report.get("passed"):
        return {
            "ok": False,
            "stage": "bench_test",
            "reason": f"基准测试未通过（得分 {report.get('overall_score', 0):.1f}，需 ≥ 60）",
            "bench": report,
        }

    # ── Step 3: 发布到 MODstore catalog ─────────────────────────────────────
    pkg_id = str(raw_mf.get("id") or employee_id).strip() or employee_id
    version = str(raw_mf.get("version") or "1.0.0").strip()

    try:
        zip_bytes = build_employee_pack_zip(pkg_id, raw_mf)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"员工包打包失败: {exc}") from exc

    rec = {
        "id": pkg_id,
        "name": str(raw_mf.get("name") or pkg_id),
        "version": version,
        "description": str(raw_mf.get("description") or ""),
        "artifact": "employee_pack",
        "industry": body.industry or str(raw_mf.get("industry") or "通用"),
        "release_channel": "stable",
        "commerce": {"mode": "free", "price": 0.0},
        "license": {"type": "personal", "verify_url": None},
    }

    import tempfile as _tmpmod

    with _tmpmod.NamedTemporaryFile(suffix=".xcemp", delete=False) as tmp:
        tmp.write(zip_bytes)
        tmp_path_str = tmp.name

    try:
        align_errs = package_manifest_alignment_errors(rec, Path(tmp_path_str))
        if align_errs:
            raise HTTPException(400, "员工包 metadata 与包内 manifest 不一致: " + "; ".join(align_errs))
        saved = append_package(rec, Path(tmp_path_str))
    except Exception as exc:  # noqa: BLE001
        Path(tmp_path_str).unlink(missing_ok=True)
        raise HTTPException(500, f"写入 catalog_store 失败: {exc}") from exc
    finally:
        Path(tmp_path_str).unlink(missing_ok=True)

    sf2 = get_session_factory()
    with sf2() as db2:
        try:
            upsert_catalog_item_from_xc_package_dict(db2, saved, author_id=user.id)
            row = db2.query(CatalogItem).filter(CatalogItem.pkg_id == pkg_id).first()
            if not row:
                row = CatalogItem(pkg_id=pkg_id, author_id=user.id)
                db2.add(row)
            row.version = saved.get("version") or version
            row.name = saved.get("name") or rec["name"]
            row.description = saved.get("description") or rec["description"]
            row.price = 0.0
            row.artifact = "employee_pack"
            row.industry = saved.get("industry") or rec["industry"]
            row.stored_filename = saved.get("stored_filename") or ""
            row.sha256 = saved.get("sha256") or ""
            db2.commit()
        except Exception as exc:  # noqa: BLE001
            db2.rollback()
            raise HTTPException(500, f"写入数据库失败: {exc}") from exc

    # ── Step 4: 推送到宿主 fhd-sandbox-runtime ───────────────────────────────
    fhd_base = (body.fhd_base_url or "").strip().rstrip("/")
    fhd_result: Dict[str, Any] = {"skipped": True, "reason": "未提供 fhd_base_url"}

    if fhd_base:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{fhd_base}/api/mod-store/install",
                    json={"pkg_id": pkg_id, "version": saved.get("version") or version, "activate": True},
                )
            if r.status_code < 400:
                fhd_result = {"ok": True, "status": r.status_code, "data": r.json()}
            else:
                fhd_result = {"ok": False, "status": r.status_code, "error": r.text[:400]}
        except Exception as exc:  # noqa: BLE001
            fhd_result = {"ok": False, "error": str(exc)[:400]}

    return {
        "ok": True,
        "stage": "synced",
        "pkg_id": pkg_id,
        "version": saved.get("version") or version,
        "bench": report,
        "catalog": {"ok": True, "stored_filename": saved.get("stored_filename") or ""},
        "fhd_install": fhd_result,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 员工编辑器保存 / 导出：接受前端当前 manifest，持久化或直接返回完整 .xcemp zip
# ─────────────────────────────────────────────────────────────────────────────


class EmployeeSaveBody(BaseModel):
    manifest: Dict[str, Any] = Field(..., description="员工完整 manifest（employee_config_v2 结构）")
    employee_id: Optional[str] = Field(None, max_length=128, description="已有员工ID；为空时从 manifest.identity.id 读取")
    provider: Optional[str] = Field(None, max_length=64, description="注册 vibe-coding Skill 用的 LLM 供应商（为空则尝试用户默认）")
    model: Optional[str] = Field(None, max_length=128, description="注册 vibe-coding Skill 用的 LLM 模型")
    register_skills: bool = Field(True, description="是否同时注册 vibe-coding ESkill（需要 LLM；失败不影响保存）")


@router.post("/employee-save", summary="保存/持久化编辑器当前 manifest 到服务器库并注册 ESkill")
async def employee_save(
    body: EmployeeSaveBody,
    user: User = Depends(_get_current_user),
):
    """把前端编辑器的当前 manifest 保存到 library/<pack_id>，解压运行时文件，
    并通过 vibe-coding 将 cognition.skills 注册为真实可执行 ESkill。

    register_skills=true（默认）时会调用 LLM 为每个 skill 生成 Python 代码并在数据库创建 ESkill 记录。
    返回保存的 pack_id、已注册 ESkill 数量和下载元信息。
    """
    import re as _re
    import tempfile as _tmp
    import zipfile as _zipfile
    from modstore_server.employee_ai_scaffold import build_employee_pack_zip
    from modstore_server.catalog_store import append_package
    from modstore_server.catalog_sync import upsert_catalog_item_from_xc_package_dict

    mf = body.manifest
    if not isinstance(mf, dict):
        raise HTTPException(400, "manifest 必须是 JSON 对象")

    # Resolve pack_id: body > manifest.identity.id > manifest.id
    raw_id = (
        (body.employee_id or "").strip()
        or str((mf.get("identity") or {}).get("id") or "").strip()
        or str(mf.get("id") or "").strip()
    )
    if not raw_id:
        raise HTTPException(400, "manifest 中缺少 identity.id 或顶层 id 字段")
    pack_id = _re.sub(r"[^a-z0-9._-]", "-", raw_id.lower()).strip("-")[:48]
    if not pack_id:
        raise HTTPException(400, f"无法从 employee_id/manifest.id 生成合法 pack_id: {raw_id!r}")

    mf["id"] = mf.get("id") or pack_id

    # ── 0. 画布形态 → 登记形态规范化 ─────────────────────────────────────
    mf, registry_errs = normalize_editor_manifest_for_registry(mf, pack_id)
    if registry_errs:
        _LOG.info("employee_save: manifest 校验警告 pack=%s: %s", pack_id, registry_errs)
    ref_warnings: List[str] = []
    sf_ref = get_session_factory()
    with sf_ref() as db_ref:
        try:
            from modstore_server.employee_pack_workflow_bundle import embed_workflow_bundles_in_manifest
            embed_workflow_bundles_in_manifest(db_ref, mf)
        except Exception as _bundle_exc:  # noqa: BLE001
            _LOG.warning("employee_save: embed bundles failed pack=%s: %s", pack_id, _bundle_exc)
            ref_warnings = _write_workflow_reference_report(db_ref, user, mf)
    # 仅当规范化后 artifact 仍不是 employee_pack 时才视为致命错误
    from modman.artifact_constants import normalize_artifact
    if normalize_artifact(mf) != "employee_pack":
        raise HTTPException(
            400,
            f"manifest 规范化后 artifact 仍无效；校验详情: {'; '.join(registry_errs)}"
        )

    # ── 1. Build full zip (includes blueprints.py + employee.py) ──────────────
    try:
        zip_bytes = build_employee_pack_zip(pack_id, mf)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"员工包打包失败: {exc}") from exc

    # ── 2. Extract to library so .py files land on disk ───────────────────────
    lib = modstore_library_path()
    pack_dir = lib / pack_id
    try:
        with _tmp.NamedTemporaryFile(suffix=".xcemp", delete=False) as tmp:
            tmp.write(zip_bytes)
            tmp_zip_path = Path(tmp.name)
        # Extract everything inside the zip's sub-directory into pack_dir.
        pack_dir.mkdir(parents=True, exist_ok=True)
        with _zipfile.ZipFile(tmp_zip_path, "r") as zf:
            for member in zf.namelist():
                # member looks like "pack_id/backend/employees/emp.py"
                parts = member.split("/", 1)
                if len(parts) == 2 and parts[1]:
                    dest = pack_dir / parts[1].replace("/", Path.sep if hasattr(Path, "sep") else "/")  # type: ignore[attr-defined]
                    dest = pack_dir / Path(parts[1])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not member.endswith("/"):
                        dest.write_bytes(zf.read(member))
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("employee_save: zip 解压失败 pack=%s: %s", pack_id, exc)
    finally:
        try:
            tmp_zip_path.unlink(missing_ok=True)
        except Exception:
            pass

    # ── 2b. Rehydrate bundled workflow/script-workflow definitions ─────────────
    try:
        from modstore_server.mod_scaffold_runner import rehydrate_employee_pack_bundles
        sf_rh = get_session_factory()
        with sf_rh() as db_rh:
            rehydrate_employee_pack_bundles(pack_id, db=db_rh, user=user)
            # Reload manifest in case IDs were rewritten
            mf_path_rh = pack_dir / "manifest.json"
            if mf_path_rh.is_file():
                mf = json.loads(mf_path_rh.read_text(encoding="utf-8"))
    except Exception as _rh_exc:  # noqa: BLE001
        _LOG.warning("employee_save: rehydrate bundles failed pack=%s: %s", pack_id, _rh_exc)

    # ── 3. Register vibe-coding ESkill for each cognition.skill ──────────────
    eskill_result: Dict[str, Any] = {"registered": 0, "skipped": False, "error": ""}
    if body.register_skills:
        try:
            from modstore_server.employee_skill_register import register_employee_pack_as_eskills
            from modstore_server.mod_scaffold_runner import resolve_llm_provider_model_auto

            sf_reg = get_session_factory()
            with sf_reg() as db_reg:
                prov, mdl, perr = await resolve_llm_provider_model_auto(
                    db_reg, user, body.provider, body.model
                )
            if perr:
                eskill_result["skipped"] = True
                eskill_result["error"] = f"LLM 解析失败（跳过 Skill 注册）: {perr}"
            else:
                brief = str(
                    mf.get("description")
                    or (mf.get("identity") or {}).get("description")
                    or mf.get("name")
                    or pack_id
                )
                panel_summary = ""
                wf_rows = mf.get("workflow_employees") or []
                if isinstance(wf_rows, list) and wf_rows and isinstance(wf_rows[0], dict):
                    panel_summary = str(wf_rows[0].get("panel_summary") or "")

                sf_sk = get_session_factory()
                with sf_sk() as db_sk:
                    specs = await register_employee_pack_as_eskills(
                        db_sk,
                        user,
                        pack_dir=pack_dir,
                        brief=brief,
                        panel_summary=panel_summary,
                        provider=prov,
                        model=mdl,
                    )
                eskill_result["registered"] = len(specs)
                # Write eskill IDs back into manifest's cognition.skills
                if specs:
                    v2 = mf.get("employee_config_v2") if isinstance(mf.get("employee_config_v2"), dict) else {}
                    cog = v2.get("cognition") if isinstance(v2.get("cognition"), dict) else {}
                    existing_skills = cog.get("skills") if isinstance(cog.get("skills"), list) else []
                    # Merge: update existing entries with eskill_id where name matches
                    name_to_spec = {s["name"]: s for s in specs}
                    updated = []
                    for sk in existing_skills:
                        sk_dict = dict(sk) if isinstance(sk, dict) else {}
                        matched = name_to_spec.get(sk_dict.get("name") or "")
                        if matched:
                            sk_dict["eskill_id"] = matched["eskill_id"]
                            sk_dict["vibe_skill_id"] = matched.get("vibe_skill_id") or ""
                        updated.append(sk_dict)
                    # Append any new ones not already in the list
                    existing_names = {s.get("name") or "" for s in updated}
                    for spec in specs:
                        if spec["name"] not in existing_names:
                            updated.append({
                                "name": spec["name"],
                                "brief": spec.get("output_var") or spec["name"],
                                "eskill_id": spec["eskill_id"],
                                "vibe_skill_id": spec.get("vibe_skill_id") or "",
                            })
                    cog["skills"] = updated
                    v2["cognition"] = cog
                    mf["employee_config_v2"] = v2
                    # Persist updated manifest
                    mf_path = pack_dir / "manifest.json"
                    mf_path.write_text(json.dumps(mf, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("employee_save: Skill 注册异常（保存继续）pack=%s: %s", pack_id, exc)
            eskill_result["skipped"] = True
            eskill_result["error"] = str(exc)[:400]

    # ── 4. Rebuild catalog zip with (possibly updated) manifest ──────────────
    try:
        zip_bytes = build_employee_pack_zip(pack_id, mf)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"员工包打包失败: {exc}") from exc

    version = str(mf.get("version") or (mf.get("identity") or {}).get("version") or "1.0.0").strip()
    name = str(mf.get("name") or (mf.get("identity") or {}).get("name") or pack_id).strip()
    rec = {
        "id": pack_id,
        "name": name,
        "version": version,
        "description": str(mf.get("description") or (mf.get("identity") or {}).get("description") or ""),
        "artifact": "employee_pack",
        "industry": str(mf.get("industry") or (mf.get("commerce") or {}).get("industry") or "通用"),
        "release_channel": "stable",
        "commerce": mf.get("commerce") or {"mode": "free", "price": 0},
        "license": {"type": "personal", "verify_url": None},
    }
    with _tmp.NamedTemporaryFile(suffix=".xcemp", delete=False) as tmp:
        tmp.write(zip_bytes)
        tmp_path = Path(tmp.name)
    try:
        align_errs = package_manifest_alignment_errors(rec, tmp_path)
        if align_errs:
            raise HTTPException(400, "员工包 metadata 与包内 manifest 不一致: " + "; ".join(align_errs))
        saved = append_package(rec, tmp_path)
    except Exception as exc:  # noqa: BLE001
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(500, f"写入 catalog_store 失败: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    sf = get_session_factory()
    with sf() as db:
        try:
            upsert_catalog_item_from_xc_package_dict(db, saved, author_id=user.id)
            row = db.query(CatalogItem).filter(CatalogItem.pkg_id == pack_id).first()
            if not row:
                row = CatalogItem(pkg_id=pack_id, author_id=user.id)
                db.add(row)
            row.version = saved.get("version") or version
            row.name = saved.get("name") or name
            row.description = saved.get("description") or rec["description"]
            row.price = 0.0
            row.artifact = "employee_pack"
            row.industry = saved.get("industry") or rec["industry"]
            row.stored_filename = saved.get("stored_filename") or ""
            row.sha256 = saved.get("sha256") or ""
            db.commit()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            raise HTTPException(500, f"写入数据库失败: {exc}") from exc

    return {
        "ok": True,
        "pack_id": pack_id,
        "version": version,
        "name": name,
        "stored_filename": saved.get("stored_filename") or "",
        "eskill_registered": eskill_result["registered"],
        "eskill_skipped": eskill_result["skipped"],
        "eskill_error": eskill_result["error"],
        "manifest": mf,  # Return updated manifest (with eskill_id written back)
        "manifest_warnings": (registry_errs if registry_errs else []) + ref_warnings,
    }


class EmployeeExportBody(BaseModel):
    manifest: Dict[str, Any] = Field(..., description="员工完整 manifest")
    employee_id: Optional[str] = Field(None, max_length=128)


@router.post("/employee-export", summary="根据当前 manifest 生成完整 .xcemp 并下载（不落盘）")
async def employee_export(
    body: EmployeeExportBody,
    user: User = Depends(_get_current_user),
):
    """接收前端当前 manifest，用后端模板生成完整 .xcemp（含 blueprints.py + employee.py），直接返回 zip 流。
    不写入数据库，仅供本地查看/调试用。
    """
    import re as _re

    mf = body.manifest
    if not isinstance(mf, dict):
        raise HTTPException(400, "manifest 必须是 JSON 对象")

    raw_id = (
        (body.employee_id or "").strip()
        or str((mf.get("identity") or {}).get("id") or "").strip()
        or str(mf.get("id") or "").strip()
    )
    if not raw_id:
        raise HTTPException(400, "manifest 中缺少 identity.id 或顶层 id 字段")
    pack_id = _re.sub(r"[^a-z0-9._-]", "-", raw_id.lower()).strip("-")[:48] or "employee"
    mf["id"] = mf.get("id") or pack_id

    # 画布形态 → 登记形态规范化（补顶层 artifact/name/version、employee、employee_config_v2）
    mf, registry_errs = normalize_editor_manifest_for_registry(mf, pack_id)
    if registry_errs:
        _LOG.info("employee_export: manifest 校验警告 pack=%s: %s", pack_id, registry_errs)
    ref_warnings: List[str] = []
    sf_ref = get_session_factory()
    with sf_ref() as db_ref:
        try:
            from modstore_server.employee_pack_workflow_bundle import embed_workflow_bundles_in_manifest
            embed_workflow_bundles_in_manifest(db_ref, mf)
        except Exception as _bundle_exc:  # noqa: BLE001
            _LOG.warning("employee_export: embed bundles failed pack=%s: %s", pack_id, _bundle_exc)
            ref_warnings = _write_workflow_reference_report(db_ref, user, mf)

    try:
        zip_bytes = build_employee_pack_zip(pack_id, mf)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"员工包打包失败: {exc}") from exc

    # 使用整包 Response 而非 StreamingResponse(BytesIO)：部分反向代理在 HTTP/2 下对「流 + Content-Length」
    # 处理不当会触发浏览器 net::ERR_HTTP2_PROTOCOL_ERROR；zip 已完全在内存中，无需分块流式。
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{pack_id}.xcemp"',
            # 把校验警告通过响应头带回，便于前端或调试工具快速查看
            "X-Manifest-Warnings": "; ".join((registry_errs + ref_warnings)[:5]) if (registry_errs or ref_warnings) else "",
        },
    )
