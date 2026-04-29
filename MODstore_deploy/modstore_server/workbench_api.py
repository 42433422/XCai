"""工作台 AI 编排：内存会话 + 异步执行 + GET 轮询状态。"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from modstore_server.api.deps import _get_current_user
from modstore_server.models import (
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
    mod_compileall_warnings,
    run_employee_ai_scaffold_async,
    run_mod_ai_scaffold_async,
)
from modstore_server.workflow_engine import run_workflow_sandbox
from modstore_server.workflow_nl_graph import apply_nl_workflow_graph
from modstore_server.workflow_sandbox_state import record_workflow_sandbox_run
from modstore_server.workbench_script_runner import run_script_job
from modstore_server.workbench_research import build_research_context

router = APIRouter(prefix="/api/workbench", tags=["workbench"])

WORKBENCH_SESSIONS: Dict[str, Dict[str, Any]] = {}
_SESSION_LOCK = asyncio.Lock()


class WorkbenchResearchBody(BaseModel):
    brief: str = Field(..., min_length=3, max_length=4000)
    intent: Literal["workflow", "mod", "employee"] = "workflow"
    max_repos: int = Field(3, ge=1, le=5)
    max_web: int = Field(6, ge=1, le=12, description="Tavily 网页摘要条数上限")
    max_chars: int = Field(8000, ge=2000, le=20000)


class WorkbenchSessionCreateBody(BaseModel):
    intent: Literal["mod", "employee", "workflow"]
    brief: str = Field(..., min_length=3, max_length=8000)
    workflow_name: Optional[str] = Field(None, max_length=256)
    plan_notes: Optional[str] = Field("", max_length=4000)
    suggested_mod_id: Optional[str] = Field(None, max_length=64)
    replace: bool = True
    provider: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=128)
    generate_workflow_graph: bool = Field(
        True,
        description="为 workflow intent 时是否用 LLM 生成节点与边（false 则仅创建空工作流）",
    )
    execution_mode: Literal["workflow", "script"] = "workflow"


def _default_steps(intent: str, execution_mode: str = "workflow") -> List[Dict[str, Any]]:
    if execution_mode == "script":
        return [
            {"id": "spec", "label": "理解任务", "status": "pending", "message": None},
            {"id": "generate", "label": "生成处理脚本", "status": "pending", "message": None},
            {"id": "validate", "label": "安全检查", "status": "pending", "message": None},
            {"id": "run", "label": "运行并生成文件", "status": "pending", "message": None},
            {"id": "complete", "label": "完成", "status": "pending", "message": None},
        ]
    base = [
        {"id": "spec", "label": "理解需求", "status": "pending", "message": None},
        {"id": "generate", "label": "生成产物", "status": "pending", "message": None},
        {"id": "validate", "label": "服务端校验", "status": "pending", "message": None},
        {"id": "complete", "label": "完成", "status": "pending", "message": None},
    ]
    if intent == "workflow":
        base[1]["label"] = "创建工作流"
    return base


async def _set_step(
    sid: str,
    step_id: str,
    status: str,
    message: Optional[str] = None,
) -> None:
    async with _SESSION_LOCK:
        sess = WORKBENCH_SESSIONS.get(sid)
        if not sess:
            return
        for s in sess["steps"]:
            if s["id"] == step_id:
                s["status"] = status
                if message is not None:
                    s["message"] = message
                break


async def _fail_session(sid: str, step_id: str, err: str) -> None:
    async with _SESSION_LOCK:
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
    intent = payload["intent"]
    execution_mode = str(payload.get("execution_mode") or "workflow")
    brief = (payload.get("brief") or "").strip()
    prov = (payload.get("provider") or "").strip() or None
    mdl = (payload.get("model") or "").strip() or None
    replace = bool(payload.get("replace", True))
    gen_wf_graph = bool(payload.get("generate_workflow_graph", True))

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
            return

        if intent == "mod":
            await _set_step(sid, "generate", "running")
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
                await _fail_session(sid, "generate", res.get("error") or "生成失败")
                return
            await _set_step(sid, "generate", "done")

            await _set_step(sid, "validate", "running")
            mod_dir = Path(res["path"])
            warns = mod_compileall_warnings(mod_dir)
            msg = "；".join(warns) if warns else None
            async with _SESSION_LOCK:
                sess = WORKBENCH_SESSIONS.get(sid)
                if sess:
                    sess["validate_warnings"] = warns
            await _set_step(sid, "validate", "done", msg)

            await _set_step(sid, "complete", "done")
            async with _SESSION_LOCK:
                sess = WORKBENCH_SESSIONS.get(sid)
                if sess:
                    sess["status"] = "done"
                    sess["artifact"] = {"mod_id": res["id"]}
            return

        if intent == "employee":
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
            await _set_step(sid, "validate", "done", "manifest 已在导入时校验")

            await _set_step(sid, "complete", "done")
            async with _SESSION_LOCK:
                sess = WORKBENCH_SESSIONS.get(sid)
                if sess:
                    sess["status"] = "done"
                    emp = (res.get("manifest") or {}).get("employee") or {}
                    sess["artifact"] = {
                        "pack_id": res["id"],
                        "employee_id": emp.get("id") or res["id"],
                        "name": (res.get("manifest") or {}).get("name"),
                        "description": (res.get("manifest") or {}).get("description"),
                    }
            return

        if intent == "workflow":
            name = (payload.get("workflow_name") or "").strip()
            if not name:
                await _fail_session(sid, "generate", "请填写工作流名称")
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
                nl = await apply_nl_workflow_graph(
                    db,
                    user,
                    workflow_id=wid,
                    brief=full_desc,
                    provider=prov,
                    model=mdl,
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
                    sess["artifact"] = {
                        "workflow_id": wid,
                        "workflow_name": name,
                        **nl_meta,
                    }
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
            "steps": _default_steps(body.intent, body.execution_mode),
            "artifact": None,
            "error": None,
            "validate_warnings": None,
            "sandbox_report": None,
            "script_result": None,
        }
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
        "intent": "workflow",
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
            "intent": "workflow",
            "status": "running",
            "steps": _default_steps("workflow", "script"),
            "artifact": None,
            "error": None,
            "validate_warnings": None,
            "sandbox_report": None,
            "script_result": None,
        }
    asyncio.create_task(_run_pipeline(sid, user.id, payload))
    return {"session_id": sid, "status": "running"}


@router.get("/sessions/{session_id}", summary="查询编排会话（轮询）")
async def get_workbench_session(
    session_id: str,
    user: User = Depends(_get_current_user),
):
    async with _SESSION_LOCK:
        sess = WORKBENCH_SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在或已过期")
    if sess.get("user_id") != user.id:
        raise HTTPException(403, "无权访问此会话")
    return {
        "id": sess["id"],
        "intent": sess["intent"],
        "status": sess["status"],
        "steps": sess["steps"],
        "artifact": sess.get("artifact"),
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
