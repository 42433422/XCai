"""员工包运行时加载与 V2 解析。"""

from __future__ import annotations

import json
import zipfile
from typing import Any, Dict

from modstore_server.catalog_store import files_dir
from modstore_server.employee_config_v2_adapter import (
    needs_executor_translation,
    translate_v2_to_executor_config,
)
from modstore_server.models import CatalogItem


def load_employee_pack(session, pack_id: str) -> Dict[str, Any]:
    row = (
        session.query(CatalogItem)
        .filter(CatalogItem.pkg_id == pack_id, CatalogItem.artifact == "employee_pack")
        .first()
    )
    if not row:
        raise ValueError(f"员工包不存在: {pack_id}")
    manifest: Dict[str, Any] = {"id": row.pkg_id, "name": row.name, "version": row.version}
    fn = (row.stored_filename or "").strip()
    if fn:
        path = files_dir() / fn
        if path.is_file() and path.suffix.lower() in (".xcemp", ".zip", ".xcmod"):
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    names = {n.replace("\\", "/") for n in zf.namelist()}
                    preferred = f"{pack_id}/manifest.json"
                    inner = preferred if preferred in names else ""
                    if not inner:
                        candidates = sorted(n for n in names if n.endswith("/manifest.json"))
                        inner = candidates[0] if candidates else ""
                    if inner:
                        manifest = json.loads(zf.read(inner).decode("utf-8"))
            except (OSError, zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError):
                pass
    return {
        "pack_id": row.pkg_id,
        "name": row.name,
        "version": row.version,
        "stored_filename": row.stored_filename,
        "manifest": manifest,
    }


def parse_employee_config_v2(manifest: Dict[str, Any]) -> Dict[str, Any]:
    v2 = manifest.get("employee_config_v2") if isinstance(manifest, dict) else None
    if isinstance(v2, dict):
        if needs_executor_translation(v2):
            return translate_v2_to_executor_config(v2)
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
