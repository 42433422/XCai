"""XC ``packages.json``（Catalog API ``/v1``）与 SQLite ``catalog_items``（市场）的关系与同步。

**市场展示与购买**以 ``catalog_items`` 为准（``market_api``）。**XC 包仓库**使用
``catalog_store`` 的 ``packages.json`` 与 ``catalog_data/files/``。

管理员可调用 ``POST /api/admin/catalog/sync-from-xc-packages``，将 JSON 中存在而
数据库中不存在的 ``(pkg_id, version)`` 插入 ``catalog_items``；若 XC 目录中存在
对应二进制文件则复制到 ``market_files/``。已有记录不会被覆盖或删除。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

from modstore_server.catalog_store import files_dir as xc_catalog_files_dir, load_store
from modstore_server.models import CatalogItem


def market_catalog_files_dir() -> Path:
    d = Path(__file__).resolve().parent / "market_files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _commerce_price(commerce: Any) -> float:
    if not isinstance(commerce, dict):
        return 0.0
    mode = str(commerce.get("mode") or "free").strip().lower()
    if mode == "free":
        return 0.0
    try:
        return float(commerce.get("price") or commerce.get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def sync_packages_json_to_catalog_items(session, *, admin_user_id: int) -> Dict[str, Any]:
    """将 ``catalog_store`` 中缺失的包插入 ``catalog_items``。"""
    inserted = 0
    skipped = 0
    errors: List[str] = []
    xc_dir = xc_catalog_files_dir()
    mdir = market_catalog_files_dir()

    for r in load_store().get("packages") or []:
        if not isinstance(r, dict):
            continue
        pkg_id = str(r.get("id") or "").strip()
        version = str(r.get("version") or "").strip()
        if not pkg_id or not version:
            continue
        exists = (
            session.query(CatalogItem)
            .filter(CatalogItem.pkg_id == pkg_id, CatalogItem.version == version)
            .first()
        )
        if exists:
            skipped += 1
            continue

        name = (str(r.get("name") or pkg_id).strip() or pkg_id)[:256]
        description = str(r.get("description") or "")[:8000]
        artifact = str(r.get("artifact") or "mod").strip() or "mod"
        industry = str(r.get("industry") or "通用").strip() or "通用"
        price = _commerce_price(r.get("commerce"))
        stored = str(r.get("stored_filename") or "").strip()
        sha256 = str(r.get("sha256") or "").strip()

        dest_name = stored
        if stored:
            src = xc_dir / stored
            if src.is_file():
                suffix = src.suffix.lower() or ".zip"
                dest_name = f"{pkg_id}-{version}{suffix}"
                try:
                    shutil.copy2(src, mdir / dest_name)
                except OSError as e:
                    errors.append(f"{pkg_id}@{version}: copy failed {e}")
                    dest_name = ""
                    sha256 = ""

        item = CatalogItem(
            pkg_id=pkg_id,
            version=version,
            name=name,
            description=description,
            price=float(price),
            author_id=admin_user_id,
            artifact=artifact,
            industry=industry,
            stored_filename=dest_name or "",
            sha256=sha256,
            is_public=True,
        )
        session.add(item)
        inserted += 1

    return {"inserted": inserted, "skipped_existing": skipped, "errors": errors}
