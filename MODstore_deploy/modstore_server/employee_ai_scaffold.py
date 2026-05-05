"""LLM 生成 employee_pack manifest + 最小 zip，经 import_zip 落入用户 Mod 库（与商店上架分离，需用户自行上传上架）。"""

from __future__ import annotations

import io
import json
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from modman.manifest_util import validate_manifest_dict
from modstore_server.employee_pack_blueprints_template import (
    render_employee_pack_blueprints_py,
    render_employee_pack_employee_py,
)
from modstore_server.employee_stub_template import safe_stub_module_name, stub_module_body
from modstore_server.mod_employee_impl_scaffold import sanitize_employee_stem
from modstore_server.xcagi_host_profile import (
    merge_workflow_employee_for_manifest,
    normalize_xcagi_host_profile,
)

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
- employee_config_v2: 可选对象。若用户要求联网、网页抓取、AI 模型排行统计，应包含：
  - perception: {"type":"web_rankings"}
  - cognition.agent.system_prompt: 要求基于网页片段输出模型、排名、来源、结论；**必须**在 system_prompt 末尾固定 Markdown 章节模板（## 用途 / ## 输入 / ## 输出 / ## 示例 / ## 异常与边界），让员工运行时输出可读 README 格式。
  - cognition.agent.model: {"provider":"deepseek","model_name":"deepseek-chat","max_tokens":4000}
  - actions.handlers: **必须如实声明**，合法值仅限 ["echo", "llm_md", "webhook"]（vibe_* 见下方扩展）。
    * "echo"   = 仅回显 payload，**不会调 LLM**；不要在只想让模型回话时写 echo
    * "llm_md" = 调 LLM 出 Markdown（默认走 cognition.agent.model 的 max_tokens/temperature）
    * "webhook"= 转发到 actions.webhook.url；声明 webhook 时必须在 actions.webhook 中给出 url
    禁止声明 ["echo"] 但实际期望模型回答；如需模型回答，请写 ["llm_md"]。
  - 若用户描述里出现「写代码 / 改代码 / 自动重构 / 自愈 / refactor / heal」等关键词，
    actions.handlers 可加入 vibe-coding 系列：
      vibe_edit  → 单轮多文件编辑：actions.vibe_edit = {"root":"<工作区子目录>", "brief":"...", "focus_paths":[...], "dry_run":false}
      vibe_heal  → 多轮自愈：actions.vibe_heal = {"root":"<工作区子目录>", "brief":"...", "max_rounds":3}
      vibe_code  → NL → 单技能：actions.vibe_code = {"brief":"...", "skill_id":"...", "run_input":{...}}
    root 必须落在用户工作区下，宿主会强制路径白名单；不要硬编码绝对路径。
- xcagi_host_profile: 可选对象，用于宿主副窗 / 内置轨道对齐（勿编造不存在的 id）：
  - panel_kind: "mod_http" | "builtin_track" | "placeholder"（默认 mod_http）
  - builtin_track_id: 仅当 panel_kind=builtin_track 时填写，允许值之一：
    label_print, shipment_mgmt, receipt_confirm, wechat_msg, wechat_phone, real_phone
  - workflow_employee_row: 可选对象，会合并进 manifest.workflow_employees[0]（如 phone_agent_base_path、workflow_placeholder 等）

示例：
{"id":"qq-watch-helper","name":"消息监控助手","version":"1.0.0","description":"协助整理与监控类需求","employee":{"id":"qq-watch","label":"监控助手","capabilities":["chat.summarize"]},"xcagi_host_profile":{"panel_kind":"mod_http"}}
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
    v2_in = data.get("employee_config_v2")
    if isinstance(v2_in, dict):
        manifest["employee_config_v2"] = _normalize_employee_config_v2_for_canvas(
            v2_in,
            pid=pid,
            name=name,
            description=desc,
            employee_id=eid,
            label=label,
            capabilities=caps,
        )
    else:
        manifest["employee_config_v2"] = _default_employee_config_v2(
            pid=pid,
            name=name,
            description=desc,
            employee_id=eid,
            label=label,
            capabilities=caps,
        )
    hp_raw = data.get("xcagi_host_profile")
    hp_norm, hp_errs = normalize_xcagi_host_profile(hp_raw)
    if hp_errs:
        return None, "xcagi_host_profile: " + "; ".join(hp_errs)
    if hp_norm:
        manifest["xcagi_host_profile"] = hp_norm
    wf_row = merge_workflow_employee_for_manifest(
        employee_id=eid,
        label=label,
        panel_summary=desc,
        host_profile=hp_norm,
    )
    manifest["workflow_employees"] = [wf_row]
    manifest["backend"] = {"entry": "blueprints", "init": "mod_init"}
    ve = validate_manifest_dict(manifest)
    if ve:
        return None, "manifest 校验: " + "; ".join(ve)
    return manifest, ""


def _normalize_employee_config_v2_for_canvas(
    v2: Dict[str, Any],
    *,
    pid: str,
    name: str,
    description: str,
    employee_id: str,
    label: str,
    capabilities: List[str],
) -> Dict[str, Any]:
    """Guarantee the employee canvas modules have concrete editable fields.

    The LLM may return a sparse ``employee_config_v2``.  The workbench canvas,
    however, edits fixed module slices (identity, cognition.agent,
    cognition.skills, collaboration.workflow).  Fill those slices at generation
    time so the generated package itself is complete instead of relying on
    frontend recovery heuristics.
    """
    out = dict(v2 or {})
    identity = dict(out.get("identity") if isinstance(out.get("identity"), dict) else {})
    identity.update(
        {
            "id": str(identity.get("id") or pid).strip() or pid,
            "version": str(identity.get("version") or "1.0.0").strip() or "1.0.0",
            "artifact": str(identity.get("artifact") or "employee_pack").strip() or "employee_pack",
            "name": str(identity.get("name") or name or label or employee_id).strip() or pid,
            "description": str(identity.get("description") or description).strip(),
        }
    )
    out["identity"] = identity

    cognition = dict(out.get("cognition") if isinstance(out.get("cognition"), dict) else {})
    agent = dict(cognition.get("agent") if isinstance(cognition.get("agent"), dict) else {})
    role = dict(agent.get("role") if isinstance(agent.get("role"), dict) else {})
    role.update(
        {
            "name": str(role.get("name") or label or name).strip() or pid,
            "persona": str(role.get("persona") or description or "专业、高效、亲切").strip(),
            "tone": str(role.get("tone") or "professional").strip() or "professional",
            "expertise": role.get("expertise") if isinstance(role.get("expertise"), list) else capabilities,
        }
    )
    model = dict(agent.get("model") if isinstance(agent.get("model"), dict) else {})
    model.update(
        {
            "provider": str(model.get("provider") or "deepseek").strip() or "deepseek",
            "model_name": str(model.get("model_name") or "deepseek-chat").strip() or "deepseek-chat",
            "temperature": model.get("temperature", 0.7),
            "max_tokens": model.get("max_tokens", 4000),
            "top_p": model.get("top_p", 0.9),
        }
    )
    agent.update(
        {
            "system_prompt": str(
                agent.get("system_prompt")
                or description
                or f"你是员工助手：{label or name}。请根据用户输入完成任务，并输出结构化结果。"
            ).strip(),
            "role": role,
            "behavior_rules": agent.get("behavior_rules") if isinstance(agent.get("behavior_rules"), list) else [],
            "few_shot_examples": agent.get("few_shot_examples") if isinstance(agent.get("few_shot_examples"), list) else [],
            "model": model,
        }
    )
    cognition["agent"] = agent
    if not isinstance(cognition.get("skills"), list):
        cognition["skills"] = [
            {"name": cap, "brief": cap}
            for cap in capabilities
        ]
    out["cognition"] = cognition

    collaboration = dict(out.get("collaboration") if isinstance(out.get("collaboration"), dict) else {})
    workflow = dict(collaboration.get("workflow") if isinstance(collaboration.get("workflow"), dict) else {})
    workflow.setdefault("workflow_id", 0)
    collaboration["workflow"] = workflow
    out["collaboration"] = collaboration
    out.setdefault("metadata", {"framework_version": "2.0.0", "created_by": "employee_ai_scaffold"})
    return out


def _default_employee_config_v2(
    *,
    pid: str,
    name: str,
    description: str,
    employee_id: str,
    label: str,
    capabilities: List[str],
) -> Dict[str, Any]:
    # Deprecated: 仅在 LLM 不可用/离线环境时作为静态关键词兜底使用。
    # 新流量请走 employee_ai_pipeline.stage_design_v2（完整 LLM 多维度设计），
    # 不要在 run_employee_ai_scaffold_async 以外的路径新增对本函数的调用。
    text = " ".join([pid, name, description, employee_id, label, " ".join(capabilities)]).lower()
    wants_rankings = any(k in text for k in ("排行", "rank", "leaderboard", "模型", "model", "上网", "联网"))
    perception: Dict[str, Any] = {"type": "web_rankings" if wants_rankings else "text"}
    prompt = (
        "你是 AI 模型排行榜统计员工。请基于输入中的网页抓取片段，整理主流 AI 模型的排名、模型名称、"
        "来源网站和简短结论；如果某来源抓取失败，要明确列出失败来源，不要编造未出现在片段中的排名。"
        if wants_rankings
        else f"你是员工助手：{label or name}。请根据用户输入完成任务，并输出结构化结果。"
    )
    return {
        "identity": {
            "id": pid,
            "version": "1.0.0",
            "artifact": "employee_pack",
            "name": name,
            "description": description,
        },
        "perception": perception,
        "memory": {"type": "session"},
        "cognition": {
            "agent": {
                "system_prompt": prompt,
                "role": {
                    "name": label or name,
                    "persona": description or "专业、高效、亲切",
                    "tone": "professional",
                    "expertise": capabilities,
                },
                "behavior_rules": [],
                "few_shot_examples": [],
                "model": {
                    "provider": "deepseek",
                    "model_name": "deepseek-chat",
                    "temperature": 0.2,
                    "max_tokens": 4000,
                    "top_p": 0.9,
                },
            },
            "skills": [{"name": cap, "brief": cap} for cap in capabilities],
        },
        "collaboration": {"workflow": {"workflow_id": 0}},
        # 默认走 llm_md：模板的 run 会真的调 LLM 出 Markdown，与 handlers 声明一致；
        # 如果只想回显 payload，请显式改写为 ["echo"]。
        "actions": {"handlers": ["llm_md"]},
        "metadata": {"framework_version": "2.0.0", "created_by": "employee_ai_scaffold"},
    }


def append_employee_stub_files_to_zip(zf: zipfile.ZipFile, pack_id: str, manifest: Dict[str, Any]) -> None:
    """写入 ``backend/employee_stubs`` 占位模块（与 workflow 脚手架一致，供安装包浏览 / XCAGI 对齐）。"""
    emp_id = str((manifest.get("employee") or {}).get("id") or manifest.get("id") or "employee").strip() or "employee"
    safe = safe_stub_module_name(emp_id)
    base = f"{pack_id}/backend/employee_stubs".replace("\\", "/")
    zf.writestr(f"{base}/__init__.py", '"""Packaged employee route stubs."""\n')
    zf.writestr(f"{base}/{safe}.py", stub_module_body(emp_id, safe))


def build_employee_pack_zip(pack_id: str, manifest: Dict[str, Any], *, include_runtime: bool = True) -> bytes:
    """manifest.zip：含 manifest.json；可选 ``backend/blueprints.py`` + ``backend/employees`` 运行时（与 FHD 挂载契约对齐）。"""
    body = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    buf = io.BytesIO()
    emp = manifest.get("employee") if isinstance(manifest.get("employee"), dict) else {}
    eid = str(emp.get("id") or pack_id).strip() or pack_id
    stem = sanitize_employee_stem(eid)
    label = str(emp.get("label") or eid).strip()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{pack_id}/manifest.json", body)
        if include_runtime:
            bp = render_employee_pack_blueprints_py(
                pack_id=pack_id, employee_id=eid, stem=stem, label=label
            )
            zf.writestr(f"{pack_id}/backend/blueprints.py", bp)
            emp_py = render_employee_pack_employee_py(employee_id=eid, stem=stem, label=label)
            zf.writestr(f"{pack_id}/backend/employees/{stem}.py", emp_py)
            zf.writestr(
                f"{pack_id}/backend/employees/__init__.py",
                '"""Generated employee implementations (employee_pack)."""\n',
            )
        else:
            append_employee_stub_files_to_zip(zf, pack_id, manifest)
    return buf.getvalue()
