from __future__ import annotations

import io
import json
import logging
import os
import shutil
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    pass

from modman.manifest_util import (
    folder_name_must_match_id,
    read_manifest,
    save_manifest_validated,
    validate_manifest_dict,
    write_manifest,
)
from modman.repo_config import (
    RepoConfig,
    load_config,
    resolved_library,
    resolved_xcagi,
    resolved_xcagi_backend_url,
    save_config,
)
from modman.scaffold import create_mod
from modman.blueprint_scan import scan_fastapi_router_routes
from modman.fhd_shell_export import write_fhd_shell_mods_json
from modman.surface_bundle import load_bundled_extension_surface
from modman.store import (
    deploy_to_xcagi,
    import_zip,
    iter_mod_dirs,
    list_mod_relative_files,
    list_mods,
    project_root,
    pull_from_xcagi,
    remove_mod,
)
from modstore_server.authoring import slim_openapi_paths
from modstore_server.constants import DEFAULT_API_PORT, DEFAULT_XCAGI_BACKEND_URL
from modstore_server.file_safe import read_text_file, resolve_under_mod, write_text_file
from modstore_server.auth_service import decode_access_token, get_user_by_id
from modstore_server.models import User, add_user_mod, get_user_mod_ids, user_owns_mod, remove_user_mod
from fastapi import Depends, Header

_TAGS = [
    {"name": "health", "description": "服务探活"},
    {"name": "config", "description": "库路径、XCAGI 根目录、后端 URL、导出 FHD 壳层 /api/mods JSON"},
    {"name": "mods", "description": "Mod 列表、详情、manifest、文件读写、导入导出"},
    {"name": "sync", "description": "与 XCAGI/mods 推送与拉回"},
    {"name": "debug", "description": "沙箱目录、primary 批量标记、XCAGI 状态代理"},
    {"name": "authoring", "description": "扩展面文档、蓝图路由静态扫描、宿主 OpenAPI 合并"},
    {"name": "payment", "description": "支付、订单与会员计划"},
    {"name": "workflow", "description": "工作流编排与执行"},
    {"name": "webhooks", "description": "业务 Webhook 投递与重放"},
    {"name": "refunds", "description": "退款申请与审核"},
    {"name": "catalog", "description": "公开目录与市场检索"},
]

app = FastAPI(
    title="XC AGI",
    version="0.2.0",
    description=(
        "XCAGI Mod 本地库与调试辅助 API。"
        f"\n\n**交互式文档**：本页同源的 [`/docs`](./docs)（Swagger UI）、[`/redoc`](./redoc)。"
        f"\n**机器可读**：[`/openapi.json`](./openapi.json)。"
        f"\n\n默认假设 XCAGI HTTP 后端在 `{DEFAULT_XCAGI_BACKEND_URL}`（可在配置中覆盖）。"
        f"\n开发时 API 默认监听 `127.0.0.1:{DEFAULT_API_PORT}`。"
    ),
    openapi_tags=_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


from modstore_server.metrics import install_metrics, observe_payment_proxy


install_metrics(app)


# 把通知 / 审计日志 / 事件指标 等横切关注点接入领域事件总线。
# 业务路由仍可通过 ``webhook_dispatcher.publish_event`` /
# ``webhook_dispatcher.enqueue_event`` 触发事件，由订阅者负责副作用。
try:
    from modstore_server.eventing.subscribers import install_default_subscribers

    install_default_subscribers()
except Exception:  # 启动期失败必须降级，不能影响进程拉起
    logging.getLogger(__name__).exception(
        "domain event subscribers failed to install"
    )


def _request_id_from_headers(request: Request) -> str:
    raw = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
    if raw:
        cleaned = raw.strip()
        if cleaned:
            return cleaned[:128]
    return uuid.uuid4().hex


@app.middleware("http")
async def _request_id_middleware(request: Request, call_next):
    request_id = _request_id_from_headers(request)
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response

def _get_allowed_origins() -> list[str]:
    """从环境变量获取允许的跨域来源，默认包含本地开发地址。"""
    env = os.environ.get("CORS_ORIGINS", "").strip()
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]
    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:5175",
        "http://localhost:5175",
        "http://127.0.0.1:5176",
        "http://localhost:5176",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "https://xiu-ci.com",
        "https://www.xiu-ci.com",
    ]


def _get_cors_origin_regex() -> str | None:
    """可选：用正则匹配一批预览域名（如腾讯云 EdgeOne *.edgeone.cool）。"""
    raw = os.environ.get("CORS_ORIGIN_REGEX", "").strip()
    if raw:
        low = raw.lower()
        if low in ("0", "false", "none", "-"):
            return None
        return raw
    # 默认允许 EdgeOne 预览站（子域随实例变化，不宜写死在 allow_origins）
    return r"^https://[a-zA-Z0-9.-]+\.edgeone\.cool$"


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_origin_regex=_get_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载在线市场 API（认证、钱包、购买、个人商店）
from modstore_server.market_api import router as market_router

app.include_router(market_router)

# 挂载支付宝支付 API
from modstore_server.payment_api import router as payment_router

app.include_router(payment_router)

# 市场前端静态根目录（见文件末尾中间件：history 路由 + 真实 assets）
_MARKET_DIST = Path(__file__).resolve().parent.parent / "market" / "dist"


STATE_FILENAME = "_modstore_state.json"


def _cfg() -> RepoConfig:
    return load_config()


def _lib() -> Path:
    p = resolved_library(_cfg())
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path() -> Path:
    return _lib() / STATE_FILENAME


def _load_state() -> Dict[str, Any]:
    p = _state_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(updates: Dict[str, Any]) -> None:
    st = _load_state()
    st.update({k: v for k, v in updates.items() if v is not None})
    p = _state_path()
    p.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ConfigDTO(BaseModel):
    library_root: str = ""
    xcagi_root: str = ""
    xcagi_backend_url: str = ""


class HealthResponse(BaseModel):
    ok: bool = True


class CreateModDTO(BaseModel):
    mod_id: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=256)


class SyncDTO(BaseModel):
    mod_ids: Optional[List[str]] = None


class ManifestPutDTO(BaseModel):
    manifest: Dict[str, Any]


class ModFilePutDTO(BaseModel):
    path: str = Field(..., min_length=1)
    content: str = ""


class SandboxDTO(BaseModel):
    mod_id: str = Field(..., min_length=1)
    mode: str = Field(default="copy", pattern="^(copy|symlink)$")


class FocusPrimaryDTO(BaseModel):
    mod_id: str = Field(..., min_length=1)


class ExportFhdShellDTO(BaseModel):
    """空字符串表示写入默认路径 ``<FHD>/backend/shell/fhd_shell_mods.json``。"""

    output_path: str = ""


def _fhd_repo_root() -> Path:
    """MODstore 位于 ``<FHD>/MODstore`` 时的上级目录。"""
    return Path(__file__).resolve().parent.parent.parent


def _assert_path_inside_fhd_repo(fhd: Path, target: Path) -> None:
    fhd_r = fhd.resolve()
    tgt_r = target.resolve()
    if not tgt_r.is_relative_to(fhd_r):
        raise HTTPException(400, "output_path 必须位于 FHD 仓库根目录内")


def _mod_dir(mod_id: str) -> Path:
    if not mod_id or "/" in mod_id or "\\" in mod_id:
        raise HTTPException(400, "非法 mod id")
    d = _lib() / mod_id
    if not d.is_dir():
        raise HTTPException(404, f"Mod 不存在: {mod_id}")
    return d


def _get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[User]:
    """获取当前用户（可选，未登录返回 None）。"""
    raw = (authorization or "").strip()
    if not raw.startswith("Bearer "):
        return None
    token = raw[7:]
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = int(payload["sub"])
    return get_user_by_id(user_id)


def _require_user(authorization: Optional[str] = Header(None)) -> User:
    """强制要求登录，未登录抛出 401。"""
    raw = (authorization or "").strip()
    if not raw.startswith("Bearer "):
        raise HTTPException(401, "请先登录")
    token = raw[7:]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401, "登录凭证无效或已过期，请重新登录")
    user_id = int(payload["sub"])
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(401, "用户不存在")
    return user


def _assert_user_owns_mod(user: User, mod_id: str) -> None:
    """检查用户是否拥有指定 MOD，管理员可访问所有 MOD。"""
    if not user.is_admin and not user_owns_mod(user.id, mod_id):
        raise HTTPException(403, "您无权访问此 MOD")


@app.get("/api/health", tags=["health"], response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True)


@app.get("/api/auth/me", tags=["auth"])
def api_get_current_user(user: Optional[User] = Depends(_get_optional_user)):
    """获取当前用户信息，未登录返回 null。"""
    if user is None:
        return {"user": None}
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
        }
    }


@app.get("/api/config", tags=["config"])
def get_config():
    cfg = _cfg()
    lib = resolved_library(cfg)
    xc = resolved_xcagi(cfg)
    st = _load_state()
    return {
        "library_root": str(lib),
        "xcagi_root": str(xc) if xc else "",
        "library_exists": lib.is_dir(),
        "xcagi_ok": bool(xc and (xc / "mods").is_dir()),
        "saved_library_root": cfg.library_root,
        "saved_xcagi_root": cfg.xcagi_root,
        "saved_xcagi_backend_url": cfg.xcagi_backend_url,
        "xcagi_backend_url": resolved_xcagi_backend_url(cfg),
        "state": {
            "last_sandbox_mods_root": st.get("last_sandbox_mods_root") or "",
            "last_sandbox_mod_id": st.get("last_sandbox_mod_id") or "",
            "focus_mod_id": st.get("focus_mod_id") or "",
        },
    }


@app.post("/api/export/fhd-shell-mods", tags=["config"])
def api_export_fhd_shell_mods(body: ExportFhdShellDTO = Body(default_factory=ExportFhdShellDTO)):
    """
    将当前库导出为 FHD ``GET /api/mods`` 使用的 JSON 文件（与 ``modman export-fhd-shell`` 相同数据）。
    ``output_path`` 留空则写入 ``<FHD>/backend/shell/fhd_shell_mods.json``。
    """
    fhd = _fhd_repo_root()
    if not fhd.is_dir():
        raise HTTPException(500, "无法定位 FHD 仓库根目录（预期 MODstore 位于 FHD/MODstore）")
    raw = body.output_path or ""
    raw = raw.strip()
    if raw:
        target = Path(raw).expanduser().resolve()
    else:
        target = (fhd / "backend" / "shell" / "fhd_shell_mods.json").resolve()
    _assert_path_inside_fhd_repo(fhd, target)
    lib = _lib()
    n = write_fhd_shell_mods_json(lib, target)
    return {"ok": True, "path": str(target), "count": n}


@app.put("/api/config", tags=["config"])
def put_config(body: ConfigDTO):
    lr = (body.library_root or "").strip()
    xr = (body.xcagi_root or "").strip()
    url = (body.xcagi_backend_url or "").strip()
    cfg = RepoConfig(
        library_root=str(Path(lr).expanduser().resolve()) if lr else "",
        xcagi_root=str(Path(xr).expanduser().resolve()) if xr else "",
        xcagi_backend_url=url,
    )
    save_config(cfg)
    if cfg.library_root:
        Path(cfg.library_root).mkdir(parents=True, exist_ok=True)
    return get_config()


@app.get("/api/mods", tags=["mods"])
def api_list_mods(user: Optional[User] = Depends(_get_optional_user)):
    """列出 MOD：已登录用户只看自己的，管理员看所有。"""
    lib = _lib()
    if user is None:
        rows = []
    elif user.is_admin:
        rows = list_mods(lib)
    else:
        user_mod_ids = get_user_mod_ids(user.id)
        all_rows = list_mods(lib)
        rows = [r for r in all_rows if r.get("id") in user_mod_ids]
    return {"data": rows}


@app.get("/api/mods/{mod_id}", tags=["mods"])
def api_get_mod(mod_id: str, user: User = Depends(_require_user)):
    _assert_user_owns_mod(user, mod_id)
    d = _mod_dir(mod_id)
    data, err = read_manifest(d)
    if err or not data:
        raise HTTPException(400, err or "manifest 无效")
    ve = validate_manifest_dict(data)
    fn = folder_name_must_match_id(d, data)
    if fn:
        ve = list(ve) + [fn]
    files = list_mod_relative_files(d)
    return {
        "id": mod_id,
        "manifest": data,
        "validation_ok": len(ve) == 0,
        "warnings": ve,
        "files": files,
    }


@app.get("/api/authoring/extension-surface", tags=["authoring"])
def api_authoring_extension_surface(merge_host: bool = False):
    bundled = load_bundled_extension_surface()
    result: Dict[str, Any] = {
        "ok": True,
        "bundled": bundled,
        "host_openapi": None,
        "host_openapi_error": None,
    }
    if merge_host:
        cfg = _cfg()
        base = resolved_xcagi_backend_url(cfg).rstrip("/")
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


@app.get("/api/mods/{mod_id}/blueprint-routes", tags=["authoring"])
def api_mod_blueprint_routes(mod_id: str, user: User = Depends(_require_user)):
    """静态扫描 Mod ``backend/blueprints.py`` 内 FastAPI ``APIRouter`` 装饰的路由。"""
    _assert_user_owns_mod(user, mod_id)
    d = _mod_dir(mod_id)
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


@app.get("/api/mods/{mod_id}/authoring-summary", tags=["authoring"])
def api_mod_authoring_summary(mod_id: str, user: User = Depends(_require_user)):
    _assert_user_owns_mod(user, mod_id)
    d = _mod_dir(mod_id)
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
    return {
        "ok": True,
        "id": mod_id,
        "manifest_backend": data.get("backend") if isinstance(data.get("backend"), dict) else {},
        "manifest_frontend": data.get("frontend") if isinstance(data.get("frontend"), dict) else {},
        "validation_ok": len(ve) == 0,
        "warnings": ve,
        "blueprint_file": bp_file,
        "blueprint_routes": bp_routes,
    }


@app.put("/api/mods/{mod_id}/manifest", tags=["mods"])
def api_put_manifest(mod_id: str, body: ManifestPutDTO, user: User = Depends(_require_user)):
    _assert_user_owns_mod(user, mod_id)
    d = _mod_dir(mod_id)
    try:
        warnings = save_manifest_validated(d, body.manifest)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "warnings": warnings}


@app.get("/api/mods/{mod_id}/file", tags=["mods"])
def api_get_mod_file(mod_id: str, path: str, user: User = Depends(_require_user)):
    _assert_user_owns_mod(user, mod_id)
    d = _mod_dir(mod_id)
    try:
        p = resolve_under_mod(d, path)
        text = read_text_file(p)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return {"path": path.replace("\\", "/").lstrip("/"), "content": text}


@app.put("/api/mods/{mod_id}/file", tags=["mods"])
def api_put_mod_file(mod_id: str, body: ModFilePutDTO, user: User = Depends(_require_user)):
    _assert_user_owns_mod(user, mod_id)
    d = _mod_dir(mod_id)
    try:
        p = resolve_under_mod(d, body.path)
        write_text_file(p, body.content)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    manifest_warnings: List[str] = []
    if p.name == "manifest.json" and p.parent.resolve() == d.resolve():
        data, err = read_manifest(d)
        if data and not err:
            manifest_warnings = validate_manifest_dict(data)
            fn = folder_name_must_match_id(d, data)
            if fn:
                manifest_warnings = list(manifest_warnings) + [fn]
    return {"ok": True, "manifest_warnings": manifest_warnings}


@app.post("/api/mods/create", tags=["mods"])
def api_create_mod(body: CreateModDTO, user: User = Depends(_require_user)):
    mid = body.mod_id.strip().lower().replace(" ", "-")
    try:
        dest = create_mod(mid, body.display_name.strip(), _lib())
    except FileExistsError as e:
        raise HTTPException(409, str(e)) from e
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, str(e)) from e
    add_user_mod(user.id, mid)
    return {"ok": True, "path": str(dest), "id": mid}


@app.delete("/api/mods/{mod_id}", tags=["mods"])
def api_delete_mod(mod_id: str, user: User = Depends(_require_user)):
    _assert_user_owns_mod(user, mod_id)
    try:
        remove_mod(_lib(), mod_id)
    except FileNotFoundError:
        raise HTTPException(404, "不存在") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    remove_user_mod(user.id, mod_id)
    return {"ok": True}


@app.post("/api/mods/import", tags=["mods"])
async def api_import_mod(file: UploadFile = File(...), replace: bool = True, user: User = Depends(_require_user)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "请上传 .zip")
    raw = await file.read()
    if len(raw) > 80 * 1024 * 1024:
        raise HTTPException(400, "文件过大（>80MB）")
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(raw)
        tmp_path = Path(tmp.name)
    try:
        dest = import_zip(tmp_path, _lib(), replace=replace)
    except (ValueError, FileExistsError) as e:
        raise HTTPException(400, str(e)) from e
    finally:
        tmp_path.unlink(missing_ok=True)
    add_user_mod(user.id, dest.name)
    return {"ok": True, "id": dest.name, "path": str(dest)}


@app.get("/api/mods/{mod_id}/export", tags=["mods"])
def api_export_mod(mod_id: str, user: User = Depends(_require_user)):
    _assert_user_owns_mod(user, mod_id)
    d = _mod_dir(mod_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in d.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(d).as_posix())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{mod_id}.zip"'},
    )


@app.post("/api/sync/push", tags=["sync"])
def api_sync_push(body: SyncDTO, user: User = Depends(_require_user)):
    cfg = _cfg()
    xc = resolved_xcagi(cfg)
    if not xc:
        raise HTTPException(400, "未配置有效的 XCAGI 根目录（设置页）")
    if not user.is_admin and body.mod_ids:
        for mod_id in body.mod_ids:
            _assert_user_owns_mod(user, mod_id)
    lib = _lib()
    try:
        done = deploy_to_xcagi(body.mod_ids, lib, xc, replace=True)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "deployed": done}


@app.post("/api/sync/pull", tags=["sync"])
def api_sync_pull(body: SyncDTO, user: User = Depends(_require_user)):
    cfg = _cfg()
    xc = resolved_xcagi(cfg)
    if not xc:
        raise HTTPException(400, "未配置有效的 XCAGI 根目录")
    lib = _lib()
    try:
        done = pull_from_xcagi(body.mod_ids, lib, xc, replace=True)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e)) from e
    except FileExistsError as e:
        raise HTTPException(409, str(e)) from e
    return {"ok": True, "pulled": done}


@app.post("/api/debug/sandbox", tags=["debug"])
def api_debug_sandbox(body: SandboxDTO, user: User = Depends(_require_user)):
    _assert_user_owns_mod(user, body.mod_id)
    mod_id = body.mod_id.strip()
    _mod_dir(mod_id)
    lib = _lib()
    src = (lib / mod_id).resolve()
    root = project_root()
    sand = root / "debug_sandbox"
    sand.mkdir(parents=True, exist_ok=True)
    session = uuid.uuid4().hex[:12]
    mods_root = (sand / session / "mods").resolve()
    mods_root.mkdir(parents=True, exist_ok=True)
    dst = mods_root / mod_id
    if dst.exists():
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    try:
        if body.mode == "symlink":
            try:
                os.symlink(src, dst, target_is_directory=True)
            except OSError:
                shutil.copytree(src, dst)
        else:
            shutil.copytree(src, dst)
    except OSError as e:
        raise HTTPException(500, f"创建沙箱失败: {e}") from e
    path_str = str(mods_root)
    _save_state(
        {
            "last_sandbox_mods_root": path_str,
            "last_sandbox_mod_id": mod_id,
            "last_sandbox_session": session,
        }
    )
    return {
        "ok": True,
        "session": session,
        "mods_root": path_str,
        "mod_id": mod_id,
        "xcagi_mods_root_env": f"XCAGI_MODS_ROOT={path_str}",
        "hint": "重启 XCAGI 后端后，仅会从此目录加载 Mod。",
    }


@app.post("/api/debug/focus-primary", tags=["debug"])
def api_debug_focus_primary(body: FocusPrimaryDTO, user: User = Depends(_require_user)):
    _assert_user_owns_mod(user, body.mod_id)
    target = body.mod_id.strip()
    _mod_dir(target)
    lib = _lib()
    updated: List[str] = []
    for d in iter_mod_dirs(lib):
        data, err = read_manifest(d)
        if err or not data:
            continue
        mid = (data.get("id") or d.name).strip()
        data["primary"] = mid == target
        try:
            write_manifest(d, data)
            updated.append(mid)
        except OSError as e:
            raise HTTPException(500, f"写入失败 {d.name}: {e}") from e
    _save_state({"focus_mod_id": target})
    return {"ok": True, "primary_mod_id": target, "updated_manifests": updated}


@app.get("/api/fhd/db-tokens/status", tags=["debug"])
def api_fhd_db_tokens_status():
    """
    代理 FHD ``GET /api/fhd/db-tokens/status``：返回宿主进程是否已配置只读/写入 DB 令牌（无明文）。
    与「路径与同步」中的后端 URL 一致（可为 FHD http_app :8000）。
    """
    cfg = _cfg()
    base = resolved_xcagi_backend_url(cfg).rstrip("/")
    url = f"{base}/api/fhd/db-tokens/status"
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url)
    except httpx.RequestError as e:
        return {
            "ok": False,
            "error": str(e),
            "url": url,
            "data": None,
        }
    try:
        payload = r.json()
    except json.JSONDecodeError:
        payload = {"raw": r.text[:2000]}
    ok = 200 <= r.status_code < 300
    return {
        "ok": ok,
        "status_code": r.status_code,
        "url": url,
        "data": payload if ok else None,
        "error": None if ok else (r.text or str(payload))[:500],
    }


@app.get("/api/xcagi/loading-status", tags=["debug"])
def api_xcagi_loading_status():
    cfg = _cfg()
    base = resolved_xcagi_backend_url(cfg)
    url = f"{base}/api/mods/loading-status"
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url)
    except httpx.RequestError as e:
        return {
            "ok": False,
            "error": str(e),
            "url": url,
            "data": None,
        }
    try:
        payload = r.json()
    except json.JSONDecodeError:
        payload = {"raw": r.text[:2000]}
    ok = 200 <= r.status_code < 300
    return {
        "ok": ok,
        "status_code": r.status_code,
        "url": url,
        "data": payload,
    }


@app.get("/api/xcagi/installed-mods", tags=["sync"])
def api_xcagi_installed_mods():
    """
    扫描配置中的 XCAGI 根目录下 ``mods/``：与 ``push`` 部署目标一致，
    用于 MODstore 首页「当前接入」展示（磁盘上的扩展包，非实时进程内状态）。
    """
    cfg = _cfg()
    xc = resolved_xcagi(cfg)
    if not xc:
        return {
            "ok": False,
            "error": "未配置有效的 XCAGI 根目录（「路径与同步」或环境变量）",
            "mods_path": "",
            "mods": [],
            "primary_mod": None,
            "primary_mod_count": 0,
        }
    mods_dir = (xc / "mods").resolve()
    if not mods_dir.is_dir():
        return {
            "ok": True,
            "mods_path": str(mods_dir),
            "mods": [],
            "note": "XCAGI/mods 目录尚不存在",
            "primary_mod": None,
            "primary_mod_count": 0,
        }
    rows: List[Dict[str, Any]] = []
    for d in iter_mod_dirs(mods_dir):
        data, err = read_manifest(d)
        if err or not data:
            rows.append(
                {
                    "id": d.name,
                    "name": "",
                    "version": "",
                    "primary": False,
                    "ok": False,
                    "error": err or "manifest 无效",
                }
            )
            continue
        rows.append(
            {
                "id": str(data.get("id") or d.name).strip() or d.name,
                "name": str(data.get("name") or "").strip(),
                "version": str(data.get("version") or "").strip(),
                "primary": bool(data.get("primary")),
                "ok": True,
            }
        )
    rows.sort(key=lambda r: str(r.get("id") or ""))
    primary_rows = [r for r in rows if r.get("primary") and r.get("ok") is not False]
    primary_mod = primary_rows[0] if len(primary_rows) == 1 else None
    return {
        "ok": True,
        "mods_path": str(mods_dir),
        "mods": rows,
        "primary_mod": primary_mod,
        "primary_mod_count": len(primary_rows),
    }


from modstore_server.catalog_api import router as catalog_public_router

app.include_router(catalog_public_router)

# 其余功能 router：之前只挂了 market/payment/catalog，导致 /api/llm、/api/notifications、
# /api/knowledge、/api/realtime/ws 等前端常用接口全部 404。统一在此集中挂载，缺包则跳过。
def _include_optional(module_path: str) -> None:
    try:
        mod = __import__(module_path, fromlist=["router"])
    except Exception as exc:  # noqa: BLE001 — 启动期容忍可选 router 引入失败
        logging.getLogger(__name__).warning("skip router %s: %s", module_path, exc)
        return
    router = getattr(mod, "router", None)
    if router is None:
        return
    app.include_router(router)


for _m in (
    "modstore_server.llm_api",
    "modstore_server.notification_api",
    "modstore_server.knowledge_vector_api",
    "modstore_server.knowledge_v2_api",
    "modstore_server.realtime_ws",
    "modstore_server.workflow_api",
    "modstore_server.script_workflow_api",
    "modstore_server.runtime_allowlist_api",
    "modstore_server.workbench_api",
    "modstore_server.employee_api",
    "modstore_server.analytics_api",
    "modstore_server.refund_api",
    "modstore_server.ops_api",
    "modstore_server.webhook_api",
    "modstore_server.health_api",
    "modstore_server.openapi_connector_api",
    "modstore_server.developer_api",
    "modstore_server.webhook_subscription_api",
    "modstore_server.templates_api",
):
    _include_optional(_m)


def _maybe_mount_dev_docs() -> None:
    """把仓库的 docs/ 目录挂到 /dev-docs，让 /dev 门户能直接展示开发者手册。

    访问示例：``/dev-docs/developer/01-quickstart.md``、
    ``/dev-docs/contracts/openapi/modstore-server.json``。
    避免与 FastAPI 自带的 ``/docs`` (Swagger UI) 冲突，所以用 ``-md`` 后缀路径。
    """
    docs_root = Path(__file__).resolve().parent.parent / "docs"
    if not docs_root.is_dir():
        return
    app.mount("/dev-docs", StaticFiles(directory=str(docs_root)), name="dev-docs")


_maybe_mount_dev_docs()


def _maybe_mount_ui() -> None:
    root = Path(__file__).resolve().parent.parent
    dist = root / "web" / "dist"
    if not dist.is_dir():
        return
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="ui-assets")

    index_file = dist / "index.html"

    @app.get("/")
    def ui_root():
        if index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(404)

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if (
            full_path.startswith("api")
            or full_path.startswith("v1")
            or full_path.startswith("docs")
            or full_path.startswith("dev-docs")
            or full_path.startswith("redoc")
            or full_path.startswith("market")
            or full_path == "openapi.json"
        ):
            raise HTTPException(404)
        if index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(404)


_maybe_mount_ui()


def _gateway() -> "PaymentGatewayService":
    from modstore_server.application.payment_gateway import PaymentGatewayService

    return PaymentGatewayService()


def _payment_backend_is_java(request: Request) -> bool:
    return _gateway().should_proxy_to_java(request.url.path)


_HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
    }
)

_PROXY_RESPONSE_DROP_HEADERS = _HOP_BY_HOP_HEADERS | frozenset(
    {
        # httpx 自动解压上游 gzip/br/deflate 内容；若原样转发 content-encoding，
        # 浏览器会再次解压明文 JSON，表现为 fetch 直接失败（ERR_CONTENT_DECODING_FAILED）。
        "content-encoding",
    }
)


@app.middleware("http")
async def _payment_backend_proxy_middleware(request: Request, call_next):
    """PAYMENT_BACKEND=java 时，把 /api/payment、/api/wallet、/api/refunds 透传到 Java 支付服务。

    避免 Python SQLite 与 Java PostgreSQL 双源（订单/会员/钱包/退款一律以 Java 为准）。
    若中间件不在位，前端拿到的 my-plan / orders 都是 Python 本地空表，会员状态会"消失"。
    """
    gateway = _gateway()
    if not gateway.should_proxy_to_java(request.url.path):
        return await call_next(request)
    method = request.method
    target_url = f"{gateway.target_base_url()}{request.url.path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"
    fwd_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP_HEADERS
    }
    request_id = getattr(request.state, "request_id", "") or _request_id_from_headers(request)
    fwd_headers["X-Request-Id"] = request_id
    body_bytes = await request.body() if method not in ("GET", "HEAD") else b""
    started = time.perf_counter()
    try:
        timeout = httpx.Timeout(
            gateway.read_timeout_seconds,
            connect=gateway.connect_timeout_seconds,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            up = await client.request(
                method,
                target_url,
                content=body_bytes if body_bytes else None,
                headers=fwd_headers,
            )
    except httpx.HTTPError as exc:
        from modstore_server.application.payment_gateway import java_payment_unreachable_message

        observe_payment_proxy(method, request.url.path, 502, time.perf_counter() - started)
        return JSONResponse(
            {"ok": False, "message": java_payment_unreachable_message(exc)},
            headers={"X-Request-Id": request_id},
            status_code=502,
        )
    observe_payment_proxy(method, request.url.path, up.status_code, time.perf_counter() - started)
    out_headers = {
        k: v for k, v in up.headers.items() if k.lower() not in _PROXY_RESPONSE_DROP_HEADERS
    }
    out_headers["X-Request-Id"] = request_id
    return Response(
        content=up.content,
        status_code=up.status_code,
        headers=out_headers,
        media_type=up.headers.get("content-type"),
    )


@app.middleware("http")
async def _market_history_spa_middleware(request: Request, call_next):
    """
    在路由匹配之前处理 ``/market`` 和 ``/new`` 前缀：真实文件直接返回，否则回退 ``index.html``。
    避免其它宽泛路由或注册顺序导致 ``/market/register``、``/new/register`` 等返回 404。
    """
    if request.scope["type"] != "http":
        return await call_next(request)
    if request.method not in ("GET", "HEAD"):
        return await call_next(request)
    path = request.url.path

    for prefix in ("/market", "/new"):
        if path == prefix or path == prefix + "/" or path.startswith(prefix + "/"):
            idx = _MARKET_DIST / "index.html"
            if not _MARKET_DIST.is_dir() or not idx.is_file():
                return await call_next(request)

            dist_root = _MARKET_DIST.resolve()
            rel = path[len(prefix):].lstrip("/")
            if rel:
                if ".." in rel.split("/"):
                    return JSONResponse({"detail": "非法路径"}, status_code=400)
                candidate = (_MARKET_DIST / rel).resolve()
                try:
                    candidate.relative_to(dist_root)
                except ValueError:
                    return await call_next(request)
                if candidate.is_file():
                    return FileResponse(candidate)
            return FileResponse(idx)

    return await call_next(request)
