"""从已入库 Mod + workflow_employees 条目生成 employee_pack manifest 与最小 zip。

manifest 会带上 ``employee_config_v2``，让运行时（``execute_employee_task``）
能走声明式 perception/cognition/actions，即使没有独立 Python 脚本也能响应。
若 Mod 目录里已有 ``backend/employees/<stem>.py``，会把该源码一起塞进 zip
``<pack_id>/source/employee.py`` 方便下载查看（不作为运行时入口）。
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modman.manifest_util import validate_manifest_dict
from modstore_server.employee_ai_scaffold import (
    _default_employee_config_v2,
    build_employee_pack_zip,
)
from modstore_server.employee_pack_blueprints_template import (
    render_employee_pack_blueprints_py,
    render_employee_pack_employee_py,
)
from modstore_server.employee_pack_standalone_template import (
    render_standalone_main_py,
    render_standalone_cli_py,
    render_standalone_runner_py,
    render_standalone_llm_adapter_py,
    render_standalone_handler_no_llm_py,
    render_standalone_handler_llm_md_py,
    render_standalone_readme_md,
)
from modstore_server.mod_employee_impl_scaffold import sanitize_employee_stem
from modstore_server.mod_ai_scaffold import normalize_mod_id


def _sanitize_employee_stem(emp_id: str) -> str:
    s = re.sub(r"[^a-z0-9_]", "_", (emp_id or "").strip().lower())
    if s and s[0].isdigit():
        s = "e_" + s
    return s or "emp"

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
    manifest["employee_config_v2"] = _default_employee_config_v2(
        pid=pack_id,
        name=name,
        description=desc,
        employee_id=emp_id,
        label=label,
        capabilities=caps,
    )
    from modstore_server.xcagi_host_profile import merge_workflow_employee_for_manifest

    manifest["workflow_employees"] = [
        merge_workflow_employee_for_manifest(
            employee_id=emp_id,
            label=label,
            panel_summary=desc,
            host_profile=None,
        )
    ]
    manifest["backend"] = {"entry": "blueprints", "init": "mod_init"}
    ve = validate_manifest_dict(manifest)
    if ve:
        return None, "manifest 校验: " + "; ".join(ve)
    return manifest, ""


def _read_employee_source(mod_dir: Optional[Path], emp_id: str) -> Optional[str]:
    if not mod_dir:
        return None
    try:
        stem = _sanitize_employee_stem(emp_id)
        p = mod_dir / "backend" / "employees" / f"{stem}.py"
        if p.is_file():
            return p.read_text(encoding="utf-8")
    except OSError:
        return None
    return None


def _build_employee_pack_zip_with_source(
    pack_id: str,
    manifest: Dict[str, Any],
    source_py: Optional[str],
) -> bytes:
    """manifest.json + 与 ``build_employee_pack_zip`` 一致的后端运行时；可选附 ``source/employee.py`` 副本。

    同时在 zip 顶层注入 ``__main__.py`` 与 ``<pack_id>/standalone/`` 目录，
    使产出的 .xcemp 文件既可被平台装载，也可作为 Python zipapp 独立执行：

        python xxx.xcemp info
        python xxx.xcemp validate
        python xxx.xcemp run [--input task.json] [--llm]

    平台运行时只通过 ``<pack_id>/manifest.json`` 与 ``backend/`` 加载，
    顶层 ``__main__.py`` 与 ``standalone/`` 不参与平台路径，零侵入。
    """
    buf = io.BytesIO()
    body = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    emp = manifest.get("employee") if isinstance(manifest.get("employee"), dict) else {}
    eid = str(emp.get("id") or pack_id).strip() or pack_id
    stem = sanitize_employee_stem(eid)
    label = str(emp.get("label") or eid).strip()
    bp = render_employee_pack_blueprints_py(pack_id=pack_id, employee_id=eid, stem=stem, label=label)
    emp_py = (
        source_py.strip() + "\n"
        if source_py and source_py.strip()
        else render_employee_pack_employee_py(employee_id=eid, stem=stem, label=label)
    )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # ── 平台原有文件（不变）─────────────────────────────────────────────
        zf.writestr(f"{pack_id}/manifest.json", body)
        zf.writestr(f"{pack_id}/backend/blueprints.py", bp)
        zf.writestr(f"{pack_id}/backend/employees/{stem}.py", emp_py)
        zf.writestr(
            f"{pack_id}/backend/employees/__init__.py",
            '"""Generated employee implementations (employee_pack)."""\n',
        )
        if source_py:
            zf.writestr(f"{pack_id}/source/employee.py", source_py)
            zf.writestr(
                f"{pack_id}/source/README.md",
                "# 员工源码\n\n本文件仅为查看参考。宿主通过 `backend/employees/<stem>.py` 执行。\n",
            )
        # ── zipapp 独立可执行入口（新增，对平台透明）──────────────────────
        zf.writestr("__main__.py", render_standalone_main_py(pack_id))
        zf.writestr(f"{pack_id}/standalone/__init__.py", "")
        zf.writestr(f"{pack_id}/standalone/cli.py", render_standalone_cli_py(pack_id, eid))
        zf.writestr(f"{pack_id}/standalone/runner.py", render_standalone_runner_py(pack_id))
        zf.writestr(f"{pack_id}/standalone/llm_adapter.py", render_standalone_llm_adapter_py())
        zf.writestr(f"{pack_id}/standalone/handlers/__init__.py", "")
        zf.writestr(f"{pack_id}/standalone/handlers/no_llm.py", render_standalone_handler_no_llm_py())
        zf.writestr(f"{pack_id}/standalone/handlers/llm_md.py", render_standalone_handler_llm_md_py())
        zf.writestr(
            f"{pack_id}/standalone/fixtures/example_input.json",
            '{"task": "validate"}\n',
        )
        zf.writestr(f"{pack_id}/standalone/requirements.txt", "")
        zf.writestr(f"{pack_id}/standalone/README.md", render_standalone_readme_md(pack_id, label))
    return buf.getvalue()


def build_employee_pack_zip_from_workflow(
    mod_id: str,
    mod_manifest: Dict[str, Any],
    wf_entry: Dict[str, Any],
    *,
    workflow_index: int = 0,
    mod_dir: Optional[Path] = None,
) -> Tuple[Optional[bytes], str, Optional[str]]:
    """返回 zip 字节、错误信息、选用的 pack_id。

    若传入 ``mod_dir``，会尝试读取 Mod 目录下的员工 Python 源码写入 zip 方便查看；
    运行时入口仍是 Mod 自己的 FastAPI 路由。
    """
    manifest, err = build_employee_pack_manifest_from_workflow(
        mod_id, mod_manifest, wf_entry, workflow_index=workflow_index
    )
    if err or not manifest:
        return None, err or "无法生成 manifest", None
    pid = str(manifest.get("id") or "").strip()
    emp_id = str((manifest.get("employee") or {}).get("id") or "").strip()
    src = _read_employee_source(mod_dir, emp_id) if mod_dir else None
    if src:
        raw = _build_employee_pack_zip_with_source(pid, manifest, src)
    else:
        raw = build_employee_pack_zip(pid, manifest)
    return raw, "", pid
