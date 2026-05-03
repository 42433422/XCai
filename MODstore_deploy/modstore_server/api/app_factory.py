"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:
    pass

from modstore_server.api.middleware import (
    market_history_spa_middleware,
    payment_backend_proxy_middleware,
    request_id_middleware,
)
from modstore_server.constants import DEFAULT_API_PORT, DEFAULT_XCAGI_BACKEND_URL

logger = logging.getLogger(__name__)

_OPENAPI_TAGS = [
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
    {"name": "catalog-mod-sync", "description": "公网机器令牌：库与 XCAGI/mods 推送/拉回（/v1/mod-sync）"},
]


@dataclass(frozen=True)
class AppConfig:
    """Process-level app wiring flags."""

    profile: str = "full"  # full | llm-only


def load_default_config() -> AppConfig:
    raw = (os.environ.get("MODSTORE_APP_PROFILE") or "").strip().lower()
    if raw in ("llm-only", "llm_only"):
        return AppConfig(profile="llm-only")
    return AppConfig(profile="full")


def _get_allowed_origins() -> list[str]:
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
    raw = os.environ.get("CORS_ORIGIN_REGEX", "").strip()
    if raw:
        low = raw.lower()
        if low in ("0", "false", "none", "-"):
            return None
        return raw
    return r"^https://[a-zA-Z0-9.-]+\.edgeone\.cool$"


def _include_optional(app: FastAPI, module_path: str) -> None:
    try:
        mod = __import__(module_path, fromlist=["router"])
    except ImportError as exc:
        logger.info("skip optional router %s: %s", module_path, exc)
        return
    except Exception:
        logger.exception("FATAL: router %s failed to load", module_path)
        raise
    router = getattr(mod, "router", None)
    if router is None:
        return
    app.include_router(router)


def _maybe_mount_dev_docs(app: FastAPI) -> None:
    docs_root = Path(__file__).resolve().parents[2] / "docs"
    if not docs_root.is_dir():
        return
    app.mount("/dev-docs", StaticFiles(directory=str(docs_root)), name="dev-docs")


def _maybe_mount_ui(app: FastAPI) -> None:
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    root = Path(__file__).resolve().parents[2]
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


def create_app(config: AppConfig | None = None) -> FastAPI:
    cfg = config or load_default_config()
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
        openapi_tags=_OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    from modstore_server.metrics import install_metrics

    install_metrics(app)

    try:
        from modstore_server.eventing.subscribers import install_default_subscribers

        install_default_subscribers()
    except Exception:
        logger.exception("domain event subscribers failed to install")

    try:
        from modstore_server.eventing.db_outbox import start_default_worker

        start_default_worker()
    except Exception:
        logger.exception("outbox dispatcher worker failed to start")

    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next):
        return await request_id_middleware(request, call_next)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_allowed_origins(),
        allow_origin_regex=_get_cors_origin_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if cfg.profile != "llm-only":
        from modstore_server.market_api import router as market_router
        from modstore_server.payment_api import router as payment_router

        app.include_router(market_router)
        app.include_router(payment_router)

        from modstore_server.api import admin_events, authoring, catalog, config as config_routes, debug, health, sync

        app.include_router(health.router)
        app.include_router(admin_events.router)
        app.include_router(config_routes.router)
        app.include_router(catalog.router)
        app.include_router(authoring.router)
        app.include_router(sync.router)
        app.include_router(debug.router)

        from modstore_server.catalog_api import router as catalog_public_router
        from modstore_server.mod_sync_catalog_api import router as mod_sync_catalog_router

        app.include_router(catalog_public_router)
        app.include_router(mod_sync_catalog_router)

    _optional = (
        "modstore_server.llm_api",
        "modstore_server.notification_api",
        "modstore_server.knowledge_vector_api",
        "modstore_server.knowledge_v2_api",
        "modstore_server.realtime_ws",
        "modstore_server.workflow_api",
        "modstore_server.script_workflow_api",
        "modstore_server.runtime_allowlist_api",
        "modstore_server.email_admin_api",
        "modstore_server.workbench_api",
        "modstore_server.employee_api",
        "modstore_server.analytics_api",
        "modstore_server.refund_api",
        "modstore_server.ops_api",
        "modstore_server.webhook_api",
        "modstore_server.health_api",
        "modstore_server.openapi_connector_api",
        "modstore_server.customer_service_api",
        "modstore_server.developer_api",
        "modstore_server.developer_key_export_api",
        "modstore_server.webhook_subscription_api",
        "modstore_server.templates_api",
        "modstore_server.sandbox_api",
    )
    if cfg.profile == "llm-only":
        from modstore_server.api import health as health_routes

        app.include_router(health_routes.router)
        _optional = ("modstore_server.llm_api", "modstore_server.health_api")

    for _m in _optional:
        _include_optional(app, _m)

    _maybe_mount_dev_docs(app)
    _maybe_mount_ui(app)

    @app.middleware("http")
    async def _payment_backend_proxy_middleware(request: Request, call_next):
        return await payment_backend_proxy_middleware(request, call_next)

    @app.middleware("http")
    async def _market_history_spa_middleware(request: Request, call_next):
        return await market_history_spa_middleware(request, call_next)

    return app


__all__ = ["AppConfig", "create_app", "load_default_config"]
