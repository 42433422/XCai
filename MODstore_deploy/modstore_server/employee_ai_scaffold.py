"""LLM 生成 employee_pack manifest + 最小 zip，经 import_zip 落入用户 Mod 库（与商店上架分离，需用户自行上传上架）。"""

from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from modman.manifest_util import validate_manifest_dict

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

SYSTEM_PROMPT_EMPLOYEE = """你是 XCAGI 全局员工包（employee_pack）清单生成器。用户用自然语言描述想要的 AI 员工能力。
你必须只输出一个 JSON 对象（不要 markdown 围栏、不要解释文字），字段如下：
- id: 字符串，小写英文/数字/点/下划线/连字符，以字母或数字开头，表示包 id（安装目录名），建议 2–48 字符
- name: 简短中文或英文显示名
- version: 语义化版本，默认 "1.0.0"
- description: 一句话介绍
- employee: 对象，必填，含：
  - id: 字符串，员工逻辑 id（可与包 id 不同）
  - label: 显示标签
  - capabilities: 字符串数组，能力标识，可为空数组

示例：
{"id":"qq-watch-helper","name":"消息监控助手","version":"1.0.0","description":"协助整理与监控类需求","employee":{"id":"qq-watch","label":"监控助手","capabilities":["chat.summarize"]}}
"""


def _strip_json_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def parse_employee_pack_llm_json(content: str) -> Tuple[Optional[Dict[str, Any]], str]:
    raw = _strip_json_fence(content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"模型返回非合法 JSON: {e}"
    if not isinstance(data, dict):
        return None, "JSON 根须为对象"
    pid = str(data.get("id") or "").strip().lower()
    if not pid or not _ID_RE.match(pid):
        return None, "id 无效：须匹配小写字母/数字/._- 且不以连字符开头"
    name = str(data.get("name") or pid).strip() or pid
    ver = str(data.get("version") or "1.0.0").strip() or "1.0.0"
    desc = str(data.get("description") or "").strip()
    emp_in = data.get("employee")
    if not isinstance(emp_in, dict):
        return None, "须包含 employee 对象"
    eid = str(emp_in.get("id") or "").strip() or pid
    label = str(emp_in.get("label") or name).strip() or name
    caps_in = emp_in.get("capabilities")
    caps: List[str] = []
    if isinstance(caps_in, list):
        for x in caps_in:
            if isinstance(x, str) and x.strip():
                caps.append(x.strip())
    manifest: Dict[str, Any] = {
        "id": pid,
        "name": name,
        "version": ver,
        "author": "",
        "description": desc,
        "artifact": "employee_pack",
        "scope": "global",
        "dependencies": {"xcagi": ">=1.0.0"},
        "employee": {
            "id": eid,
            "label": label,
            "capabilities": caps,
        },
    }
    ve = validate_manifest_dict(manifest)
    if ve:
        return None, "manifest 校验: " + "; ".join(ve)
    return manifest, ""


def build_employee_pack_zip(pack_id: str, manifest: Dict[str, Any]) -> bytes:
    """单文件 manifest.zip，顶层为 pack_id/manifest.json。"""
    body = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{pack_id}/manifest.json", body)
    return buf.getvalue()
