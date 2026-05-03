"""Authoring / blueprint / employee pack routes."""

from __future__ import annotations

import io
import json
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from modman.blueprint_scan import scan_fastapi_router_routes
from modman.manifest_util import (
    folder_name_must_match_id,
    read_manifest,
    save_manifest_validated,
    validate_manifest_dict,
)
from modman.surface_bundle import load_bundled_extension_surface

from modstore_server.api.auth_deps import assert_user_owns_mod, require_user
from modstore_server.api.dto import (
    FrontendRegenerateDTO,
    ModAiScaffoldDTO,
    WorkflowEmployeeCatalogDTO,
)
from modstore_server.application.catalog import CatalogShellService, get_default_catalog_application_service
from modstore_server.authoring import slim_openapi_paths
from modstore_server.employee_pack_export import build_employee_pack_zip_from_workflow
from modstore_server.infrastructure import library_paths
from modstore_server.mod_snapshots import capture_manifest_snapshot
from modstore_server.application.employee import get_default_employee_application_service
from modstore_server.models import User, get_session_factory
from modstore_server.package_sandbox_audit import run_package_audit_async
from modstore_server.workflow_employee_scaffold import (
    WorkflowEmployeeScaffoldDTO,
    run_workflow_employee_scaffold,
    scaffold_auto_merge_default,
)

router = APIRouter(tags=["authoring"])


@router.get("/api/authoring/extension-surface")
def api_authoring_extension_surface(merge_host: bool = False):
    bundled = load_bundled_extension_surface()
    result: Dict[str, Any] = {
        "ok": True,
        "bundled": bundled,
        "host_openapi": None,
        "host_openapi_error": None,
    }
    if merge_host:
        cfg = library_paths.cfg()
        base = library_paths.resolved_xcagi_backend_url(cfg).rstrip("/")
        url = f"{base}/openapi.json"
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(url)
            if r.status_code >= 400:
                result["host_openapi_error"] = f"HTTP {r.status_code} from {url}"
            else:
                spec = r.json()
                routes = slim_openapi_paths(spec if isinstance(spec, dict) else {})
                result["host_openapi"] = {
                    "base_url": base,
                    "openapi_url": url,
                    "route_count": len(routes),
                    "routes": routes,
                }
        except httpx.RequestError as e:
            result["host_openapi_error"] = f"{type(e).__name__}: {e} ({url})"
        except json.JSONDecodeError as e:
            result["host_openapi_error"] = f"openapi.json 非 JSON: {e}"
    return result


@router.get("/api/mods/{mod_id}/blueprint-routes")
def api_mod_blueprint_routes(mod_id: str, user: User = Depends(require_user)):
    assert_user_owns_mod(user, mod_id)
    try:
        d = library_paths.mod_dir(mod_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    for rel in ("backend/blueprints.py", "blueprints.py"):
        p = d / rel
        if p.is_file():
            routes = scan_fastapi_router_routes(p)
            return {"ok": True, "file": rel, "routes": routes}
    return {
        "ok": True,
        "file": None,
        "routes": [],
        "hint": "未找到 backend/blueprints.py 或根目录 blueprints.py（FastAPI 路由扫描）",
    }


@router.get("/api/mods/{mod_id}/authoring-summary")
def api_mod_authoring_summary(mod_id: str, user: User = Depends(require_user)):
    assert_user_owns_mod(user, mod_id)
    try:
        d = library_paths.mod_dir(mod_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    data, err = read_manifest(d)
    if err or not data:
        raise HTTPException(400, err or "manifest 无效")
    ve = validate_manifest_dict(data)
    fn = folder_name_must_match_id(d, data)
    if fn:
        ve = list(ve) + [fn]
    bp_file: str | None = None
    bp_routes: List[Dict[str, Any]] = []
    for rel in ("backend/blueprints.py", "blueprints.py"):
        p = d / rel
        if p.is_file():
            bp_file = rel
            bp_routes = scan_fastapi_router_routes(p)
            break
    from modstore_server.mod_scaffold_runner import analyze_mod_employee_readiness

    sf = get_session_factory()
    with sf() as db:
        employee_readiness = analyze_mod_employee_readiness(db, user, d)
    return {
        "ok": True,
        "id": mod_id,
        "manifest_backend": data.get("backend") if isinstance(data.get("backend"), dict) else {},
        "manifest_frontend": data.get("frontend") if isinstance(data.get("frontend"), dict) else {},
        "validation_ok": len(ve) == 0,
        "warnings": ve,
        "blueprint_file": bp_file,
        "blueprint_routes": bp_routes,
        "employee_readiness": employee_readiness,
    }


@router.post("/api/mods/{mod_id}/workflow-employees/scaffold")
def api_mod_workflow_employee_scaffold(
    mod_id: str, body: WorkflowEmployeeScaffoldDTO, user: User = Depends(require_user)
):
    assert_user_owns_mod(user, mod_id)
    try:
        d = library_paths.mod_dir(mod_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    try:
        return run_workflow_employee_scaffold(
            d, body, allow_blueprint_merge=scaffold_auto_merge_default()
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/api/mods/{mod_id}/export-employee-pack")
def api_export_workflow_employee_pack(
    mod_id: str,
    workflow_index: int = 0,
    user: User = Depends(require_user),
):
    assert_user_owns_mod(user, mod_id)
    try:
        d = library_paths.mod_dir(mod_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    data, err = read_manifest(d)
    if err or not data:
        raise HTTPException(400, err or "manifest 无效")
    rows = data.get("workflow_employees")
    if not isinstance(rows, list) or workflow_index < 0 or workflow_index >= len(rows):
        raise HTTPException(400, "workflow_index 越界或 workflow_employees 非数组")
    raw, build_err, pack_id = build_employee_pack_zip_from_workflow(
        mod_id,
        data,
        rows[workflow_index] if isinstance(rows[workflow_index], dict) else {},
        workflow_index=workflow_index,
        mod_dir=d,
    )
    if build_err or not raw or not pack_id:
        raise HTTPException(400, build_err or "生成员工包失败")
    return StreamingResponse(
        io.BytesIO(raw),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{pack_id}.xcemp"'},
    )


@router.post("/api/mods/{mod_id}/register-workflow-employee-catalog")
async def api_register_workflow_employee_catalog(
    mod_id: str,
    body: WorkflowEmployeeCatalogDTO,
    user: User = Depends(require_user),
):
    assert_user_owns_mod(user, mod_id)
    try:
        d = library_paths.mod_dir(mod_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    data, err = read_manifest(d)
    if err or not data:
        raise HTTPException(400, err or "manifest 无效")
    rows = data.get("workflow_employees")
    idx = int(body.workflow_index)
    if not isinstance(rows, list) or idx < 0 or idx >= len(rows):
        raise HTTPException(400, "workflow_index 越界或 workflow_employees 非数组")
    entry = rows[idx] if isinstance(rows[idx], dict) else {}
    raw, build_err, pack_id = build_employee_pack_zip_from_workflow(
        mod_id,
        data,
        entry,
        workflow_index=idx,
        mod_dir=d,
    )
    if build_err or not raw or not pack_id:
        raise HTTPException(400, build_err or "生成员工包失败")

    audit = await run_package_audit_async(raw, {"artifact": "employee_pack"})
    if not audit.get("ok"):
        raise HTTPException(400, str(audit.get("error") or "包审核失败"))
    summary = audit.get("summary") if isinstance(audit.get("summary"), dict) else {}
    if summary and summary.get("pass") is False:
        raise HTTPException(400, "五维审核未通过，禁止登记")

    manifest_zip, manifest_err, _pid = build_employee_pack_zip_from_workflow(
        mod_id,
        data,
        entry,
        workflow_index=idx,
        mod_dir=d,
    )
    if manifest_err or not manifest_zip:
        raise HTTPException(400, manifest_err or "生成员工包失败")
    from modstore_server.employee_pack_export import build_employee_pack_manifest_from_workflow

    manifest, manifest_build_err = build_employee_pack_manifest_from_workflow(
        mod_id,
        data,
        entry,
        workflow_index=idx,
    )
    if manifest_build_err or not manifest:
        raise HTTPException(400, manifest_build_err or "生成员工包 manifest 失败")

    rec: Dict[str, Any] = {
        "id": pack_id,
        "name": str(manifest.get("name") or pack_id),
        "version": str(manifest.get("version") or "1.0.0"),
        "description": str(manifest.get("description") or ""),
        "artifact": "employee_pack",
        "industry": body.industry.strip() or "通用",
        "release_channel": body.release_channel,
        "commerce": {"mode": "free" if body.price <= 0 else "paid", "price": body.price},
        "license": {"type": "personal" if body.price <= 0 else "commercial", "verify_url": None},
        "probe_mod_id": mod_id,
    }
    with tempfile.NamedTemporaryFile(suffix=".xcemp", delete=False) as tmp:
        tmp.write(manifest_zip)
        tmp_path = Path(tmp.name)
    try:
        from modstore_server.mod_scaffold_runner import analyze_mod_employee_readiness

        sf = get_session_factory()
        with sf() as db:
            saved = get_default_catalog_application_service().register_employee_pack(
                db,
                author_id=user.id,
                mod_id=mod_id,
                pack_id=pack_id,
                package_record=rec,
                package_file=tmp_path,
                price=float(body.price or 0),
            )
            get_default_employee_application_service().register_pack(
                author_id=user.id,
                mod_id=mod_id,
                pack_id=pack_id,
                version=str(saved.get("version") or rec["version"]),
            )
            db.commit()
            readiness = analyze_mod_employee_readiness(db, user, d)
    finally:
        tmp_path.unlink(missing_ok=True)

    return {"ok": True, "package": saved, "audit": audit, "employee_readiness": readiness}


@router.post("/api/mods/{mod_id}/patch-workflow-employee-nodes")
def api_patch_workflow_employee_nodes(mod_id: str, user: User = Depends(require_user)):
    assert_user_owns_mod(user, mod_id)
    try:
        d = library_paths.mod_dir(mod_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    from modstore_server.mod_scaffold_runner import (
        analyze_mod_employee_readiness,
        patch_workflow_graph_employee_nodes,
    )

    sf = get_session_factory()
    with sf() as db:
        out = patch_workflow_graph_employee_nodes(db, user, mod_dir=d, workflow_results=[])
        readiness = analyze_mod_employee_readiness(db, user, d)
    return {"ok": bool(out.get("ok")), "graph_patch": out, "employee_readiness": readiness}


@router.post("/api/mods/{mod_id}/frontend/regenerate")
def api_mod_frontend_regenerate(
    mod_id: str,
    body: FrontendRegenerateDTO,
    user: User = Depends(require_user),
):
    assert_user_owns_mod(user, mod_id)
    try:
        mod_dir = library_paths.mod_dir(mod_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    manifest, err = read_manifest(mod_dir)
    if not manifest or err:
        raise HTTPException(400, err or "无法读取 manifest")
    try:
        snap = capture_manifest_snapshot(mod_dir, f"重新生成前端前 {time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception:  # noqa: BLE001
        snap = None
    spec = CatalogShellService.frontend_spec_for_existing_mod(mod_dir, manifest, body.brief)
    mod_name = str(manifest.get("name") or mod_id)
    frontend = manifest.get("frontend") if isinstance(manifest.get("frontend"), dict) else {}
    menu = frontend.get("menu") if isinstance(frontend.get("menu"), list) and frontend.get("menu") else [
        {"id": f"{mod_id}-home", "label": mod_name, "icon": "fa-cube", "path": spec["entry_path"]}
    ]
    frontend.update(
        {
            "routes": frontend.get("routes") or "frontend/routes",
            "menu": menu,
            "pro_entry_path": spec["entry_path"],
            "app": "config/frontend_spec.json",
        }
    )
    manifest["frontend"] = frontend
    config = manifest.get("config") if isinstance(manifest.get("config"), dict) else {}
    config["frontend_spec"] = "config/frontend_spec.json"
    manifest["config"] = config
    warnings = save_manifest_validated(mod_dir, manifest)
    from modstore_server.mod_scaffold_runner import render_frontend_routes_js, render_generated_home_vue

    (mod_dir / "config").mkdir(parents=True, exist_ok=True)
    (mod_dir / "frontend" / "views").mkdir(parents=True, exist_ok=True)
    (mod_dir / "config" / "frontend_spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (mod_dir / "frontend" / "routes.js").write_text(
        render_frontend_routes_js(mod_id, mod_name, spec["entry_path"]), encoding="utf-8"
    )
    (mod_dir / "frontend" / "views" / "HomeView.vue").write_text(
        render_generated_home_vue(mod_id, mod_name, spec), encoding="utf-8"
    )
    return {
        "ok": True,
        "frontend_spec": spec,
        "entry_path": spec["entry_path"],
        "snapshot": snap,
        "manifest_warnings": warnings,
        "files": ["config/frontend_spec.json", "frontend/routes.js", "frontend/views/HomeView.vue"],
    }


@router.post("/api/mods/ai-scaffold")
async def api_mod_ai_scaffold(body: ModAiScaffoldDTO, user: User = Depends(require_user)):
    from modstore_server.mod_scaffold_runner import run_mod_suite_ai_scaffold_async

    sf = get_session_factory()
    with sf() as db:
        res = await run_mod_suite_ai_scaffold_async(
            db,
            user,
            brief=body.brief,
            suggested_id=body.suggested_id,
            replace=body.replace,
            provider=body.provider,
            model=body.model,
        )
    if not res.get("ok"):
        raise HTTPException(400, res.get("error") or "AI 生成 Mod 失败")
    return res
