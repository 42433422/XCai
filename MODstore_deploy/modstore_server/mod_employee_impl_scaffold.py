"""为「做 Mod」生成的每名 workflow_employee 生成可执行 Python 实现。

产物写到 ``backend/employees/<safe_id>.py``，由 ``render_suite_blueprints_py``
通过 FHD 宿主 ``app.mod_sdk.mods_bus.import_mod_backend_py`` 加载并调度。

对每名员工单独调 LLM 一次；生成后立刻 ``py_compile``，不通过则一次修复重试。
不依赖外部凭证；允许模块内使用 ``ctx["call_llm"]`` / ``ctx["http_get"]`` 等由
host 注入的最小运行时（见 ``render_suite_blueprints_py`` 里的 build_run_context）。
"""

from __future__ import annotations

import ast
import asyncio
import json
import py_compile
import re
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from modstore_server.llm_chat_proxy import chat_dispatch
from modstore_server.llm_key_resolver import (
    OAI_COMPAT_OPENAI_STYLE_PROVIDERS,
    resolve_api_key,
    resolve_base_url,
)
from modstore_server.models import User


_SAFE_ID_RE = re.compile(r"[^a-z0-9_]")

_MAX_CONCURRENT_LLM = 3
_MAX_REPAIR_ATTEMPTS = 2

_FORBIDDEN_IMPORTS = frozenset({
    "os",
    "subprocess",
    "shutil",
    "sys",
    "pathlib",
    "socket",
    "ctypes",
    "multiprocessing",
    "threading",
    "signal",
    "resource",
    "fcntl",
    "mmap",
})
_FORBIDDEN_ATTRS = frozenset({
    "system",
    "popen",
    "exec",
    "eval",
    "compile",
    "__import__",
    "open",
})
_ALLOWED_MOD_SDK_PREFIX = "app.mod_sdk."


def sanitize_employee_stem(emp_id: str) -> str:
    """与 ``workflow_employee_scaffold._sanitize_py_module`` 同规则，便于沙箱共存。"""
    s = _SAFE_ID_RE.sub("_", (emp_id or "").strip().lower())
    if s and s[0].isdigit():
        s = "e_" + s
    return s or "emp"


SYSTEM_PROMPT_EMPLOYEE_IMPL = """你是 XCAGI 工作台 Mod 员工实现代码生成器。用户给你一个员工的业务画像，请你直接输出**一个完整的 Python 文件**（UTF-8，顶层不用 Markdown 代码围栏、不加解释），这个文件会被放到 ``backend/employees/<safe_id>.py`` 里，由宿主 FastAPI 通过 ``import_mod_backend_py`` 按独立模块加载。

必须严格遵守：
1. 文件顶部允许 ``from __future__ import annotations``、标准库 import（``asyncio / json / logging / re / time / datetime / typing``）、以及 ``import httpx`` 或 ``import requests``（可选，仅当实现需要发起 HTTP 时）。
2. **FHD 宿主 import 边界**：除上述标准库与 ``httpx``/``requests`` 外，若需调用宿主业务、AI 或 Mod 间能力，**仅允许** ``from app.mod_sdk.<子模块> import ...``（例如 ``app.mod_sdk.comms`` 的 ``get_mod_comms``、``app.mod_sdk.services`` 的 ``get_products_service`` 等已导出符号）。禁止 ``from app.routes``、``from app.application``、``from app.services``、``from modstore_server`` 等绕过契约层的导入。需要 LLM 时**优先**使用 ``await ctx["call_llm"](...)``（外层 ``blueprints`` 已优先桥接到宿主 ``app.mod_sdk.mod_employee_llm``）。
3. 禁止出现：相对 import（``from . import ...``）、``import *``、访问文件系统外部路径、硬编码 API key/密码/手机号/身份证。
4. 必须实现：
   ``async def run(payload: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:``
   - ``payload``：调用方通过 ``POST /api/mod/{mod_id}/employees/{emp_id}/run`` 传入的 JSON。
   - ``ctx``：host 注入的能力 dict，至少含：
     * ``ctx["mod_id"]``（str）
     * ``ctx["employee_id"]``（str）
     * ``ctx["logger"]``（logging.Logger）
     * ``ctx["call_llm"]``（async callable）：``await ctx["call_llm"](messages, *, max_tokens=1024, temperature=0.2, response_format=None)``，返回 ``{"ok": bool, "content": str, "error": str}``。
     * ``ctx["http_get"]``（async callable）：``await ctx["http_get"](url, *, headers=None, timeout=30)``，返回 ``{"ok": bool, "status": int, "text": str, "error": str}``。
     * ``ctx["http_post"]``（async callable）：同上，多一个 ``json_body``/``data`` 参数。
     * ``ctx.get("secrets")`` 可能为 ``None``；若需要凭证必须从 ``secrets`` 读取而不是硬编码。
   - 返回 JSON 可序列化 dict；建议键：``summary``（一句话人话结果）、``items``（数组明细）、``warnings``（字符串数组）。异常应 ``raise``，由外层 blueprints 统一兜底。

5. 可以定义若干辅助函数（同文件内）；也可以定义 ``SYSTEM_PROMPT`` 常量给 ``call_llm`` 用。
6. 若业务需要多步（抓网页 → 抽取 → LLM 总结 → 合成答复），在 ``run`` 里顺序执行；不要自己起线程、也不要启动新 event loop。
7. 不要写 Flask/FastAPI 路由；你只是一个被外层 router 调用的纯函数。
8. 代码风格：类型标注完整；最多 ~200 行；注释用简体中文，说明实现思路与外部依赖。
9. 输出内容必须能通过 ``py_compile`` 校验；整个回复就是该 .py 的源代码本体。
"""


SYSTEM_PROMPT_EMPLOYEE_IMPL_REPAIR = """你是 Python 语法修复器。用户将给你一段被 ``py_compile`` 拒绝的源代码与错误信息。请只输出**修复后的完整 Python 文件**（UTF-8，不要 Markdown 围栏、不要解释）。保留原有 ``async def run(payload, ctx)`` 签名与业务逻辑，仅修正语法与引号/缩进问题。"""


def _employee_brief_lines(
    emp: Dict[str, Any],
    *,
    mod_id: str,
    mod_name: str,
    mod_brief: str,
    industry_card: Optional[Dict[str, Any]] = None,
) -> List[str]:
    eid = str(emp.get("id") or "").strip()
    label = str(emp.get("label") or emp.get("panel_title") or eid).strip()
    panel_title = str(emp.get("panel_title") or "").strip()
    panel_summary = str(emp.get("panel_summary") or "").strip()
    capabilities = emp.get("capabilities") if isinstance(emp.get("capabilities"), list) else []
    data_sources = emp.get("data_sources") if isinstance(emp.get("data_sources"), list) else []
    outputs = emp.get("outputs") if isinstance(emp.get("outputs"), list) else []
    wf = emp.get("workflow") if isinstance(emp.get("workflow"), dict) else {}
    wf_desc = str(wf.get("description") or "").strip()
    lines = [
        f"Mod id: {mod_id}",
        f"Mod 名称: {mod_name}",
        f"Mod 一句话: {mod_brief[:400]}",
    ]
    if industry_card:
        ind = str(industry_card.get("name") or industry_card.get("id") or "").strip()
        scen = str(industry_card.get("scenario") or "").strip()
        if ind:
            lines.append(f"行业/场景: {ind}; 说明: {scen[:240]}")
    lines.extend(
        [
            "",
            f"员工 id: {eid}",
            f"员工显示名: {label}",
            f"面板标题: {panel_title}",
            f"职责摘要: {panel_summary[:800]}",
        ]
    )
    if capabilities:
        lines.append(f"能力标识: {', '.join(str(x) for x in capabilities[:12])}")
    if data_sources:
        lines.append(f"数据源: {', '.join(str(x) for x in data_sources[:12])}")
    if outputs:
        lines.append(f"预期输出: {', '.join(str(x) for x in outputs[:12])}")
    if wf_desc:
        lines.append(f"所属工作流说明: {wf_desc[:800]}")
    lines.append("")
    lines.append(
        "请你基于以上画像实现 async def run(payload, ctx)。若画像信息不足以写出真实业务逻辑，"
        "请让 run 走「调用 ctx['call_llm'] 生成一段针对 payload 的结构化建议，并把模型输出作为 data」的兜底实现，"
        "但仍要按画像里的 panel_summary 调整 SYSTEM_PROMPT。"
    )
    return lines


def _security_check(src: str) -> Optional[str]:
    """AST 级安全审查。返回 None 表示通过；否则返回违规描述。"""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return f"语法错误: {e}"

    violations: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_mod = alias.name.split(".")[0]
                if root_mod in _FORBIDDEN_IMPORTS:
                    violations.append(f"禁止 import {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_mod = node.module.split(".")[0]
                if root_mod in _FORBIDDEN_IMPORTS:
                    violations.append(f"禁止 from {node.module} import ...")
                if root_mod == "app" and not node.module.startswith(_ALLOWED_MOD_SDK_PREFIX):
                    violations.append(
                        f"仅允许 from app.mod_sdk.<子模块> import ...，禁止 from {node.module}"
                    )

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr
                if attr_name in _FORBIDDEN_ATTRS:
                    violations.append(f"禁止调用 .{attr_name}()")

            if isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "compile", "__import__"):
                    violations.append(f"禁止调用 {node.func.id}()")

    if violations:
        return "安全审查未通过: " + "; ".join(violations[:8])
    return None


def _behavior_check(src: str) -> Optional[str]:
    """行为校验：检查 run 函数是否存在且签名基本正确。"""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return f"语法错误: {e}"

    has_run = False
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run":
            has_run = True
            arg_names = [a.arg for a in node.args.args]
            if "payload" not in arg_names or "ctx" not in arg_names:
                return "run() 签名必须为 async def run(payload, ctx)"
            break

    if not has_run:
        return "缺少 async def run(payload, ctx) 函数定义"

    return None


def _compile_check(src: str) -> Optional[str]:
    """返回 None 表示通过；否则返回编译错误字符串。"""
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8"
        ) as fp:
            fp.write(src)
            tmp = Path(fp.name)
        try:
            py_compile.compile(str(tmp), doraise=True)
        finally:
            tmp.unlink(missing_ok=True)
        return None
    except py_compile.PyCompileError as e:
        return str(e.msg or e)
    except OSError as e:
        return str(e)


def _strip_code_fence(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:python|py)?\s*\n?", "", s, flags=re.I)
        s = re.sub(r"\n?```\s*$", "", s)
    return s.strip() + "\n"


async def _generate_one_employee_py(
    *,
    prov: str,
    api_key: str,
    base_url: Optional[str],
    model: str,
    emp: Dict[str, Any],
    mod_id: str,
    mod_name: str,
    mod_brief: str,
    industry_card: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    user_msg = "\n".join(
        _employee_brief_lines(
            emp,
            mod_id=mod_id,
            mod_name=mod_name,
            mod_brief=mod_brief,
            industry_card=industry_card,
        )
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_EMPLOYEE_IMPL},
        {"role": "user", "content": user_msg},
    ]
    res = await chat_dispatch(
        prov,
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=messages,
        max_tokens=3072,
    )
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error") or "upstream error"}
    raw_orig = _strip_code_fence(str(res.get("content") or ""))
    current_source = raw_orig

    last_err: Optional[str] = None
    for attempt in range(_MAX_REPAIR_ATTEMPTS):
        err = _compile_check(current_source)
        if not err:
            sec_err = _security_check(current_source)
            if sec_err:
                return {"ok": False, "error": sec_err, "raw": raw_orig}
            beh_err = _behavior_check(current_source)
            if beh_err:
                return {"ok": False, "error": beh_err, "raw": raw_orig}
            return {
                "ok": True,
                "source": current_source,
                "repair_used": attempt > 0,
            }

        last_err = err
        repair_messages = [
            {"role": "system", "content": SYSTEM_PROMPT_EMPLOYEE_IMPL_REPAIR},
            {
                "role": "user",
                "content": (
                    f"py_compile 报错：\n{err}\n\n原始代码（保持业务逻辑，仅修语法）：\n{current_source[:8000]}"
                ),
            },
        ]
        res2 = await chat_dispatch(
            prov,
            api_key=api_key,
            base_url=base_url,
            model=model,
            messages=repair_messages,
            max_tokens=3072,
        )
        if not res2.get("ok"):
            return {
                "ok": False,
                "error": f"repair upstream: {res2.get('error') or 'error'}",
                "raw": raw_orig,
                "compile_error": err,
            }
        current_source = _strip_code_fence(str(res2.get("content") or ""))

    return {
        "ok": False,
        "error": f"经过 {_MAX_REPAIR_ATTEMPTS} 次修复仍无法通过编译",
        "raw": raw_orig,
        "compile_error": last_err,
    }


def _fallback_employee_py(emp_id: str, label: str, panel_summary: str) -> str:
    """模型失败或信息极少时的最小可编译实现：调用 ctx.call_llm 做兜底应答。"""
    safe_label = json.dumps(label or emp_id, ensure_ascii=False)
    safe_summary = json.dumps(
        (panel_summary or "根据 payload 完成员工任务并返回结构化结果。")[:600],
        ensure_ascii=False,
    )
    body = f'''"""自动生成的员工实现（兜底版）：{emp_id}。

画像信息不足或 LLM 生成失败时使用，行为为「把 payload 与员工画像拼给 ctx.call_llm，
把模型文本作为 summary 返回」。部署后请在「Mod 制作页」里替换为真实业务逻辑。
"""

from __future__ import annotations

import json
from typing import Any, Dict


EMPLOYEE_LABEL = {safe_label}
SYSTEM_PROMPT = {safe_summary}


async def run(payload: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    logger = ctx.get("logger")
    if logger:
        logger.info("[employee:{emp_id}] invoked payload=%s", str(payload)[:200])
    call_llm = ctx.get("call_llm")
    if not callable(call_llm):
        return {{
            "summary": "ctx.call_llm 未注入；请在宿主 build_run_context 中挂载 LLM 调度。",
            "items": [],
            "warnings": ["call_llm_missing"],
            "echo": payload,
        }}
    user_msg = json.dumps(payload or {{}}, ensure_ascii=False)[:4000]
    res = await call_llm(
        [
            {{"role": "system", "content": SYSTEM_PROMPT}},
            {{"role": "user", "content": user_msg}},
        ],
        max_tokens=1024,
        temperature=0.2,
    )
    if not res.get("ok"):
        return {{
            "summary": f"员工 {{EMPLOYEE_LABEL}} 调用 LLM 失败：" + str(res.get("error") or "")[:300],
            "items": [],
            "warnings": ["call_llm_failed"],
        }}
    return {{
        "summary": str(res.get("content") or "").strip()[:2000],
        "items": [],
        "warnings": [],
    }}
'''
    return body


async def generate_mod_employee_impls_async(
    db: Session,
    user: User,
    *,
    mod_dir: Path,
    employees: List[Dict[str, Any]],
    mod_id: str,
    mod_name: str,
    mod_brief: str,
    industry_card: Optional[Dict[str, Any]] = None,
    provider: Optional[str],
    model: Optional[str],
    status_hook: Optional[Callable[[str], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """
    为 employees 中每名员工生成 ``backend/employees/<stem>.py``。
    生成失败（LLM 不可用或重试仍编译失败）时写入「兜底版」源码，以保证编排能继续跑，
    并把失败项写入返回值 ``errors`` 供前端展示。
    """
    out_dir = mod_dir / "backend" / "employees"
    out_dir.mkdir(parents=True, exist_ok=True)
    init_py = out_dir / "__init__.py"
    if not init_py.is_file():
        init_py.write_text(
            '"""Generated employee implementations (loaded via import_mod_backend_py)."""\n',
            encoding="utf-8",
        )

    prov = (provider or "").strip()
    mdl = (model or "").strip()
    api_key = ""
    base = None
    if prov:
        api_key, _ = resolve_api_key(db, user.id, prov)
        if prov in OAI_COMPAT_OPENAI_STYLE_PROVIDERS:
            base = resolve_base_url(db, user.id, prov)

    valid_employees = [e for e in employees if isinstance(e, dict) and str(e.get("id") or "").strip()]
    total = len(valid_employees)
    sem = asyncio.Semaphore(_MAX_CONCURRENT_LLM)
    progress_lock = asyncio.Lock()
    done_cnt = 0

    async def _gen_one(idx: int, emp: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal done_cnt
        eid = str(emp.get("id") or "").strip()
        stem = sanitize_employee_stem(eid)
        target = out_dir / f"{stem}.py"
        label = str(emp.get("label") or emp.get("panel_title") or eid).strip()
        panel_summary = str(emp.get("panel_summary") or "").strip()

        used_fallback = False
        gen_err = ""
        source = ""

        if prov and mdl and api_key:
            async with sem:
                gen = await _generate_one_employee_py(
                    prov=prov,
                    api_key=api_key,
                    base_url=base,
                    model=mdl,
                    emp=emp,
                    mod_id=mod_id,
                    mod_name=mod_name,
                    mod_brief=mod_brief,
                    industry_card=industry_card,
                )
            if gen.get("ok"):
                source = str(gen.get("source") or "").strip() + "\n"
            else:
                gen_err = str(gen.get("error") or "")
        else:
            gen_err = "LLM provider/model/api_key 不可用，写入兜底实现"

        if not source:
            source = _fallback_employee_py(eid, label, panel_summary)
            used_fallback = True

        target.write_text(source, encoding="utf-8")
        entry = {
            "employee_id": eid,
            "stem": stem,
            "path": f"backend/employees/{stem}.py",
            "fallback": used_fallback,
        }
        if used_fallback and gen_err:
            entry["note"] = gen_err[:400]

        async with progress_lock:
            done_cnt += 1
            if status_hook:
                await status_hook(f"已完成 {done_cnt}/{max(total, 1)} 名员工实现生成（并发上限 {_MAX_CONCURRENT_LLM}）…")

        return entry

    results = await asyncio.gather(*[_gen_one(i, e) for i, e in enumerate(valid_employees)])

    generated = list(results)
    errors = [e for e in generated if e.get("fallback") and e.get("note")]

    return {
        "ok": not errors,
        "generated": generated,
        "errors": errors,
    }
