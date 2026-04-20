# MODstore 文档

- **定位（推荐主入口）**：扩展的制作、校验、与 `XCAGI/mods` 同步，以本目录 **独立 MODstore Web**（`MODstore/web` + `modstore_server`）为准；XCAGI 主前端 `/mod-store` 默认嵌入该站点，仅将「本机 .xcmod 简易目录」作为兼容入口。
- **API（自动生成）**：服务启动后访问 Swagger UI `/docs`、ReDoc `/redoc`、OpenAPI JSON `/openapi.json`。
- **制作向导（Web `/author`）**：展示内置 `extension_surface.json`（manifest/蓝图约定）；可合并宿主 `openapi.json` 中 `/api*` 路由摘要；各 Mod 详情「蓝图/API」页签静态扫描 `backend/blueprints.py`。
- **架构决策（ADR）**：[docs/adr/](adr/) 目录。
- **公网 Catalog（/v1）**：`modstore_server` 挂载 `GET/POST /v1/*`；数据目录由环境变量 `MODSTORE_CATALOG_DIR` 控制（默认 `modstore_server/catalog_data/`）；上传需 `Authorization: Bearer <MODSTORE_CATALOG_UPLOAD_TOKEN>`。CLI：`modman publish <zip> --catalog-url URL --token TOKEN`（需 `pip install httpx`）。
