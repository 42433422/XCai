"""FastAPI application factory.

Gateway note: payment proxy is wired in ``middleware_registry.register_all_middleware``
via ``_payment_backend_proxy_middleware`` wrapping ``payment_backend_proxy_middleware``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from fastapi import FastAPI

try:
    from dotenv import load_dotenv

    _deploy_root = Path(__file__).resolve().parents[2]
    load_dotenv(_deploy_root / ".env", override=False)
    # 本机覆盖（.gitignore）；不存在则忽略。后加载以便覆盖 .env 中同名键。
    _shared_secret_env = {
        key: os.environ.get(key)
        for key in ("MODSTORE_JWT_SECRET",)
        if os.environ.get(key)
    }
    load_dotenv(_deploy_root / ".env.local", override=True)
    # JWT 必须与 Java 支付服务一致；systemd/生产 .env 已有值时禁止 .env.local 覆盖。
    os.environ.update(_shared_secret_env)
except ImportError:
    pass

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

    try:
        from modstore_server.subscription_renewer import start_subscription_scheduler

        start_subscription_scheduler()
    except Exception:
        logger.exception("subscription auto-renew scheduler failed to start")

    from modstore_server.middleware_registry import register_all_middleware

    register_all_middleware(app)

    from modstore_server.api import csp_report, ui_mount

    app.include_router(csp_report.router)

    if cfg.profile != "llm-only":
        from modstore_server.market_api import router as market_router
        from modstore_server.payment_api import router as payment_router

        app.include_router(market_router)
        app.include_router(payment_router)

        # 联系表单、手机短信登录等补充认证路由（前缀 /api，路由中已带完整 path）
        try:
            from modstore_server.market_auth_api import router as market_auth_router
            app.include_router(market_auth_router, prefix="/api")
        except Exception:
            logger.exception("market_auth_api 加载失败，跳过")

        # 投诉、合规、material_category/license_scope 增强目录路由
        try:
            from modstore_server.market_catalog_api import router as market_catalog_router
            app.include_router(market_catalog_router, prefix="/api")
        except Exception:
            logger.exception("market_catalog_api 加载失败，跳过")

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
        "modstore_server.agent_butler_api",
        "modstore_server.notification_api",
        "modstore_server.knowledge_vector_api",
        "modstore_server.knowledge_v2_api",
        "modstore_server.realtime_ws",
        "modstore_server.workflow_api",
        "modstore_server.eskill_api",
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
        # 支付系统补全模块
        "modstore_server.author_earnings",
        "modstore_server.invoice_api",
        "modstore_server.reconciliation",
        "modstore_server.subscription_renewer",
    )
    if cfg.profile == "llm-only":
        from modstore_server.api import health as health_routes

        app.include_router(health_routes.router)
        _optional = ("modstore_server.llm_api", "modstore_server.health_api")

    for _m in _optional:
        _include_optional(app, _m)

    _maybe_mount_vibe_subapp(app)

    ui_mount.maybe_mount_dev_docs(app)
    ui_mount.maybe_mount_ui(app)

    return app


def _maybe_mount_vibe_subapp(app: FastAPI) -> None:
    """挂载 vibe-coding 自带的 Web UI / JSON API 到 ``/api/vibe``。

    默认关闭(避免在没装 vibe-coding 时报错)。设置 ``MODSTORE_ENABLE_VIBE_WEB=1``
    才挂载。挂载只是把 vibe-coding 暴露给前端 / IDE / LSP,实际业务流仍然走
    in-process import(:mod:`modstore_server.integrations.vibe_adapter`)。
    """
    if (os.environ.get("MODSTORE_ENABLE_VIBE_WEB") or "").strip() not in ("1", "true", "yes"):
        return
    try:
        from modstore_server.integrations.vibe_adapter import vibe_available
    except Exception:
        return
    if not vibe_available():
        logger.info("MODSTORE_ENABLE_VIBE_WEB=1 但 vibe-coding 未安装,跳过挂载")
        return
    try:
        from vibe_coding.agent.web import create_app as create_vibe_app
    except Exception:
        logger.exception("vibe_coding.agent.web 加载失败,跳过 /api/vibe 挂载")
        return
    try:
        sub = create_vibe_app()
        app.mount("/api/vibe", sub)
        logger.info("已挂载 vibe-coding sub-app 到 /api/vibe")
    except Exception:
        logger.exception("挂载 /api/vibe 失败")


__all__ = ["AppConfig", "create_app", "load_default_config"]
