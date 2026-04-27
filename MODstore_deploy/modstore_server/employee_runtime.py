"""员工包运行时加载与 V2 解析。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from modstore_server.catalog_store import files_dir
from modstore_server.models import CatalogItem


def load_employee_pack(session, pack_id: str) -> Dict[str, Any]:
    row = (
        session.query(CatalogItem)
        .filter(CatalogItem.pkg_id == pack_id, CatalogItem.artifact == "employee_pack")
        .first()
    )
    if not row:
        raise ValueError(f"员工包不存在: {pack_id}")
    return {
        "pack_id": row.pkg_id,
        "name": row.name,
        "version": row.version,
        "stored_filename": row.stored_filename,
        "manifest": {"id": row.pkg_id, "name": row.name, "version": row.version},
    }


def parse_employee_config_v2(manifest: Dict[str, Any]) -> Dict[str, Any]:
    v2 = manifest.get("employee_config_v2") if isinstance(manifest, dict) else None
    if isinstance(v2, dict):
        return v2
    employee: Any = manifest.get("employee") if isinstance(manifest, dict) else {}
    if not isinstance(employee, dict):
        employee = {}
    label = employee.get("label") if isinstance(employee, dict) else None
    return {
        "perception": {"type": "text"},
        "memory": {"type": "session"},
        "cognition": {
            "system_prompt": f"你是员工助手：{label or (manifest.get('name') if isinstance(manifest, dict) else None) or 'assistant'}",
            "reasoning_mode": "default",
        },
        "actions": {"handlers": ["echo"]},
    }


def build_employee_context(employee_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "employee_id": employee_id,
        "input_data": input_data or {},
    }
