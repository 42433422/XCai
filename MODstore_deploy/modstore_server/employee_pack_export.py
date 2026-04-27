"""从已入库 Mod + workflow_employees 条目生成 employee_pack manifest 与最小 zip。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from modman.manifest_util import validate_manifest_dict
from modstore_server.employee_ai_scaffold import build_employee_pack_zip
from modstore_server.mod_ai_scaffold import normalize_mod_id

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _slug_id(raw: str, fallback: str) -> str:
    x = (raw or "").strip().lower()
    x = re.sub(r"[^a-z0-9._-]+", "-", x)
    x = re.sub(r"-{2,}", "-", x).strip("-")
    if not x:
        x = fallback
    if x and not x[0].isalnum():
        x = "x" + x
    if not _ID_RE.match(x):
        x = fallback
    return x[:48]


def build_employee_pack_manifest_from_workflow(
    mod_id: str,
    mod_manifest: Dict[str, Any],
    wf_entry: Dict[str, Any],
    *,
    workflow_index: int = 0,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    用 Mod 的 manifest 与单条 workflow_employee 构造可校验的 employee_pack manifest。
    pack id 优先 {mod_id}-{wf_id}，避免与库内其他包 id 冲突。
    """
    mid = normalize_mod_id(mod_id)
    if not mid:
        return None, "Mod id 无效"

    wf = wf_entry if isinstance(wf_entry, dict) else {}
    wf_raw_id = str(wf.get("id") or "").strip()
    wf_slug = normalize_mod_id(wf_raw_id) or _slug_id(wf_raw_id, f"emp{workflow_index}")
    pack_id = f"{mid}-{wf_slug}" if wf_slug != mid else mid
    if len(pack_id) > 48:
        pack_id = pack_id[:48]
    if not _ID_RE.match(pack_id):
        pack_id = mid

    name_src = str(wf.get("label") or wf.get("panel_title") or mod_manifest.get("name") or pack_id).strip()
    name = name_src[:200] or pack_id
    ver = str(mod_manifest.get("version") or "1.0.0").strip() or "1.0.0"
    desc = str(
        wf.get("panel_summary")
        or wf.get("description")
        or mod_manifest.get("description")
        or ""
    ).strip()[:4000]

    emp_id = normalize_mod_id(str(wf.get("id") or "").strip()) or wf_slug
    label = str(wf.get("label") or name).strip() or emp_id
    caps_in = wf.get("capabilities")
    caps: List[str] = []
    if isinstance(caps_in, list):
        for x in caps_in:
            if isinstance(x, str) and x.strip():
                caps.append(x.strip()[:128])

    manifest: Dict[str, Any] = {
        "id": pack_id,
        "name": name,
        "version": ver,
        "author": str(mod_manifest.get("author") or "").strip(),
        "description": desc,
        "artifact": "employee_pack",
        "scope": "global",
        "dependencies": (
            mod_manifest["dependencies"]
            if isinstance(mod_manifest.get("dependencies"), dict)
            else {"xcagi": ">=1.0.0"}
        ),
        "employee": {
            "id": emp_id,
            "label": label[:200],
            "capabilities": caps,
        },
    }
    ve = validate_manifest_dict(manifest)
    if ve:
        return None, "manifest 校验: " + "; ".join(ve)
    return manifest, ""


def build_employee_pack_zip_from_workflow(
    mod_id: str,
    mod_manifest: Dict[str, Any],
    wf_entry: Dict[str, Any],
    *,
    workflow_index: int = 0,
) -> Tuple[Optional[bytes], str, Optional[str]]:
    """返回 zip 字节、错误信息、选用的 pack_id。"""
    manifest, err = build_employee_pack_manifest_from_workflow(
        mod_id, mod_manifest, wf_entry, workflow_index=workflow_index
    )
    if err or not manifest:
        return None, err or "无法生成 manifest", None
    pid = str(manifest.get("id") or "").strip()
    raw = build_employee_pack_zip(pid, manifest)
    return raw, "", pid
