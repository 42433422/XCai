"""LLM 生成可导入 Mod 脚手架（manifest + skeleton 文件），经 import_zip 落库。"""

from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from modman.manifest_util import validate_manifest_dict
from modman.scaffold import template_dir

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def normalize_mod_id(s: str) -> Optional[str]:
    x = str(s or "").strip().lower()
    if not x or not _ID_RE.match(x):
        return None
    return x

SYSTEM_PROMPT = """你是 XCAGI Mod 清单生成器。用户会用自然语言描述想要的扩展 Mod。
你必须只输出一个 JSON 对象（不要 markdown 围栏、不要解释文字），字段如下：
- id: 字符串，小写英文/数字/点/下划线/连字符，以字母或数字开头，建议 2–48 字符
- name: 简短中文或英文显示名
- version: 语义化版本，默认 "1.0.0"
- description: 一句话介绍
- workflow_employees: 可选数组；每项为对象，含 id、label、panel_title、panel_summary（均可选但 id 与 label 至少其一非空）

示例：
{"id":"demo-helper","name":"演示助手","version":"1.0.0","description":"示例 Mod","workflow_employees":[{"id":"helper-1","label":"助手","panel_title":"助手","panel_summary":"占位说明"}]}
"""


def _strip_json_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def parse_llm_manifest_json(content: str) -> Tuple[Optional[Dict[str, Any]], str]:
    raw = _strip_json_fence(content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"模型返回非合法 JSON: {e}"
    if not isinstance(data, dict):
        return None, "JSON 根须为对象"
    mid = str(data.get("id") or "").strip().lower()
    if not mid or not _ID_RE.match(mid):
        return None, "id 无效：须匹配小写字母/数字/._- 且不以连字符开头"
    name = str(data.get("name") or mid).strip() or mid
    ver = str(data.get("version") or "1.0.0").strip() or "1.0.0"
    desc = str(data.get("description") or "").strip()
    wf_in = data.get("workflow_employees")
    wf_out: List[Dict[str, Any]] = []
    if isinstance(wf_in, list):
        for i, item in enumerate(wf_in):
            if not isinstance(item, dict):
                continue
            eid = str(item.get("id") or "").strip()
            label = str(item.get("label") or "").strip()
            pt = str(item.get("panel_title") or "").strip()
            ps = str(item.get("panel_summary") or "").strip()
            if not eid and not label and not pt:
                continue
            wf_out.append(
                {
                    "id": eid or f"{mid}-wf-{i + 1}",
                    "label": label or pt or eid,
                    "panel_title": pt or label or eid,
                    "panel_summary": ps or desc[:240],
                }
            )
    manifest: Dict[str, Any] = {
        "id": mid,
        "name": name,
        "version": ver,
        "author": "",
        "description": desc,
        "primary": False,
        "dependencies": {"xcagi": ">=1.0.0"},
        "backend": {"entry": "blueprints", "init": "mod_init"},
        "frontend": {
            "routes": "frontend/routes",
            "menu": [
                {
                    "id": f"{mid}-home",
                    "label": name,
                    "icon": "fa-cube",
                    "path": f"/{mid}",
                }
            ],
        },
        "hooks": {},
        "comms": {"exports": []},
    }
    if wf_out:
        manifest["workflow_employees"] = wf_out
    ve = validate_manifest_dict(manifest)
    if ve:
        return None, "manifest 校验: " + "; ".join(ve)
    return manifest, ""


def _sub_template(text: str, mod_id: str, mod_name: str) -> str:
    return text.replace("__MOD_ID__", mod_id).replace("__MOD_NAME__", mod_name)


def build_scaffold_zip(mod_id: str, mod_name: str, manifest: Dict[str, Any]) -> bytes:
    td = template_dir()
    files: Dict[str, str] = {
        "manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    }
    for rel in (
        "backend/__init__.py",
        "backend/blueprints.py",
        "frontend/routes.js",
        "frontend/views/HomeView.vue",
    ):
        p = td / rel
        if not p.is_file():
            raise FileNotFoundError(f"缺少模板: {p}")
        files[rel] = _sub_template(p.read_text(encoding="utf-8"), mod_id, mod_name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc, body in files.items():
            zf.writestr(f"{mod_id}/{arc}", body)
    return buf.getvalue()
