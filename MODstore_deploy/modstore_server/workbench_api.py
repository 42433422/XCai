"""工作台 AI 编排：内存会话 + 磁盘持久化（多 worker 可读）+ 异步执行 + GET 轮询。"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from io import BytesIO
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
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
    import_mod_suite_repository,
    mod_compileall_warnings,
    patch_workflow_graph_employee_nodes,
    register_mod_employee_packs_async,
    run_mod_suite_mod_sandbox,
    run_mod_suite_workflow_sandboxes,
    run_employee_ai_scaffold_async,
    run_mod_ai_scaffold_async,
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
from modstore_server.workbench_script_runner import run_script_job
from modstore_server.workbench_research import build_research_context
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
        if (employee_target or "").strip().lower() == "pack_plus_workflow":
            base.extend(
                [
                    {"id": "workflow", "label": "生成 Skill 组（画布）", "status": "pending", "message": None},
                    {"id": "workflow_sandbox", "label": "工作流沙箱测试", "status": "pending", "message": None},
                    {"id": "mod_sandbox", "label": "包体与 Python 校验", "status": "pending", "message": None},
                    {"id": "host_check", "label": "宿主连通性检查", "status": "pending", "message": None},
                ]
            )
        else:
            base.extend(
                [
                    {"id": "workflow", "label": "Skill 组（画布）", "status": "pending", "message": None},
                    {"id": "workflow_sandbox", "label": "工作流沙箱测试", "status": "pending", "message": None},
                    {"id": "mod_sandbox", "label": "包体与 Python 校验", "status": "pending", "message": None},
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
    message: Optional[str] = None,
) -> None:
    async with _SESSION_LOCK:
        _hydrate_workbench_session_unlocked(sid)
        sess = WORKBENCH_SESSIONS.get(sid)
        if not sess:
            return
        for s in sess["steps"]:
            if s["id"] == step_id:
                s["status"] = status
                if message is not None:
                    s["message"] = message
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
                        sess["status"] = "done"
                        sess["validate_warnings"] = warns
                        sess["artifact"] = {
                            "mod_id": res["id"],
                            "workflow_results": [],
                            "blueprint": None,
                            "validation_summary": {"ok": not warns, "python_warnings": warns},
                        }
                        _persist_workbench_session_unlocked(sid)
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
                write_mod_suite_blueprint(
                    mod_dir,
                    blueprint,
                    workflow_results,
                    industry_card=industry_card,
                    ui_shell=ui_shell,
                    api_summary=api_summary,
                    workflow_sandbox=workflow_sandbox,
                    employee_readiness=employee_readiness,
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
                        sess["status"] = "done"
                        sess["validate_warnings"] = (
                            api_summary["warnings"] + validation_summary["workflow_warnings"]
                        )
                        sess["sandbox_report"] = {"workflow": workflow_sandbox, "mod": mod_sandbox}
                        sess["artifact"] = {
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
                        }
                        _persist_workbench_session_unlocked(sid)
            except Exception as e:  # noqa: BLE001
                _LOG.exception("workbench mod full suite failed session=%s", sid)
                await _abort_mod_pipeline("complete", str(e)[:2000])
                return

            return

        if intent == "employee":
            et = str(payload.get("employee_target") or "pack_only").strip().lower()
            wf_name = (payload.get("employee_workflow_name") or "").strip() or None
            fhd_base = (payload.get("fhd_base_url") or "").strip() or None

            await _set_step(sid, "generate", "running")
            res = await run_employee_ai_scaffold_async(
                db,
                user,
                brief=brief,
                replace=replace,
                provider=prov,
                model=mdl,
            )
            if not res.get("ok"):
                await _fail_session(sid, "generate", res.get("error") or "生成失败")
                return
            await _set_step(sid, "generate", "done")

            await _set_step(sid, "validate", "running")
            async with _SESSION_LOCK:
                sess = WORKBENCH_SESSIONS.get(sid)
                if sess:
                    sess["validate_warnings"] = []
                    _persist_workbench_session_unlocked(sid)
            await _set_step(sid, "validate", "done", "manifest 已在导入时校验")

            pack_dir = Path(str(res.get("path") or ""))
            wf_attach: Dict[str, Any] = {}
            await _set_step(sid, "workflow", "running")
            if et == "pack_plus_workflow":
                wf_attach = await attach_nl_workflow_to_employee_pack_dir(
                    db,
                    user,
                    pack_dir=pack_dir,
                    brief=brief,
                    workflow_name=wf_name,
                    provider=prov,
                    model=mdl,
                )
                wmsg = (
                    f"已创建工作流 id={wf_attach.get('workflow_id')}；NL 生图"
                    f"{'成功' if (wf_attach.get('nl') or {}).get('ok') else '有提示'}"
                )
                await _set_step(sid, "workflow", "done", wmsg[:480])
            else:
                await _set_step(
                    sid,
                    "workflow",
                    "done",
                    "已跳过：当前为「仅员工包」模式；若需画布请选 pack_plus_workflow 并重新编排",
                )

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
            else:
                mod_checks.append({"id": "manifest", "ok": False, "message": f"包目录无效: {pack_dir}"})
            emp_mod_sandbox = {
                "ok": all(c.get("ok") for c in mod_checks) if mod_checks else False,
                "checks": mod_checks,
                "note": "员工包轻量校验（含 backend/blueprints 运行时）",
            }
            mod_sb_msg = "包体轻量校验通过" if emp_mod_sandbox["ok"] else "包体校验有提示，见会话 artifact.mod_sandbox"
            await _set_step(sid, "mod_sandbox", "done", mod_sb_msg[:480])

            host_probe: Dict[str, Any] = {"skipped": True}
            await _set_step(sid, "host_check", "running", "探测宿主 /api/mods/")
            if fhd_base:
                try:
                    import httpx  # type: ignore

                    base = fhd_base.rstrip("/")
                    host_warnings: List[str] = []
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        r = await client.get(f"{base}/api/mods/")
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

            await _set_step(sid, "complete", "done")
            async with _SESSION_LOCK:
                sess = WORKBENCH_SESSIONS.get(sid)
                if sess:
                    sess["status"] = "done"
                    emp = (res.get("manifest") or {}).get("employee") or {}
                    sess["sandbox_report"] = {"workflow": workflow_sandbox, "mod": emp_mod_sandbox}
                    sess["artifact"] = {
                        "pack_id": res["id"],
                        "employee_id": res["id"],
                        "manifest_employee_id": emp.get("id") or res["id"],
                        "name": (res.get("manifest") or {}).get("name"),
                        "description": (res.get("manifest") or {}).get("description"),
                        "package": res.get("package") or {},
                        "workflow_sandbox": workflow_sandbox,
                        "mod_sandbox": emp_mod_sandbox,
                        "employee_target": et,
                        "workflow_attachment": wf_attach,
                        "host_probe": host_probe,
                        "validation_summary": {
                            "ok": bool(emp_mod_sandbox.get("ok")),
                            "mod_sandbox": emp_mod_sandbox,
                            "workflow_skipped": not bool(wid),
                        },
                    }
                    _persist_workbench_session_unlocked(sid)
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

            await _set_step(sid, "complete", "done")
            async with _SESSION_LOCK:
                sess = WORKBENCH_SESSIONS.get(sid)
                if sess:
                    sess["status"] = "done"
                    sess["artifact"] = _enrich_artifact_skill_aliases(
                        {
                            "workflow_id": wid,
                            "workflow_name": name,
                            **nl_meta,
                        },
                    )
                    _persist_workbench_session_unlocked(sid)
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
    asyncio.create_task(_run_pipeline(sid, user.id, payload))
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
    asyncio.create_task(_run_pipeline(sid, user.id, payload))
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
