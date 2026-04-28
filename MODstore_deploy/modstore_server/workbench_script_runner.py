"""Workbench "做脚本" 入口的薄壳：兼容旧 API，内部走新 ``script_agent`` 沙箱。

历史接口保留：
- 模块级 ``SCRIPT_ROOT``（被 ``test_workbench_script_runner.py`` 通过
  monkeypatch 替换为 ``tmp_path``）
- :func:`validate_script` —— 现在 delegate 到
  :mod:`modstore_server.script_agent.static_checker`
- :func:`_fallback_script` —— 内置 Excel 汇总兜底
- :func:`run_script_job` —— ``await`` 即跑通："生成 → 静检 → 沙箱执行"

Phase 2 起 ``script_agent.agent_loop`` 会承担多轮迭代修复，
本模块仅保留单轮"生成+执行"路径以服务 Workbench"快速跑一个脚本"场景。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from modstore_server.llm_chat_proxy import chat_dispatch
from modstore_server.llm_key_resolver import resolve_api_key, resolve_base_url
from modstore_server.script_agent import sandbox_runner as _sandbox
from modstore_server.script_agent.static_checker import validate_script as _validate


SCRIPT_ROOT = _sandbox.SCRIPT_ROOT


def _fallback_script() -> str:
    """LLM 不可用时的兜底脚本：把 inputs 下的 xlsx 汇总到 outputs/处理结果.xlsx。

    依赖 ``openpyxl``（已在默认 allowlist），不调 ``modstore_runtime`` SDK，
    保证即使没有 LLM key 也能产出可下载结果。
    """
    return r'''
from pathlib import Path
from openpyxl import Workbook, load_workbook

input_dir = Path("inputs")
output_dir = Path("outputs")
output_dir.mkdir(exist_ok=True)

out = Workbook()
summary = out.active
summary.title = "处理说明"
summary.append(["说明", "已读取上传文件，生成汇总预览。请在工作台中补充更具体规则后可再次执行。"])
summary.append(["输入文件数", len(list(input_dir.iterdir()))])

for file in input_dir.iterdir():
    if file.suffix.lower() != ".xlsx":
        continue
    wb = load_workbook(file, data_only=False)
    for ws in wb.worksheets:
        title = (file.stem + "_" + ws.title)[:31]
        sheet = out.create_sheet(title)
        for r_idx, row in enumerate(ws.iter_rows(values_only=False), start=1):
            if r_idx > 80:
                break
            for c_idx, cell in enumerate(row, start=1):
                if c_idx > 40:
                    break
                sheet.cell(r_idx, c_idx).value = cell.value

out.save(output_dir / "处理结果.xlsx")
print("已生成 outputs/处理结果.xlsx")
'''


def _extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*([\s\S]*?)```", text or "", re.I)
    return (m.group(1) if m else text or "").strip()


def validate_script(code: str) -> List[str]:
    """兼容旧签名：仅返回错误列表。底层用 ``static_checker``。"""
    return _validate(code)


async def _generate_script(
    *,
    db: Optional[Session],
    user_id: int,
    brief: str,
    input_files: List[Path],
    provider: Optional[str],
    model: Optional[str],
) -> str:
    if db is None or not provider or not model:
        return _fallback_script()
    key, _src = resolve_api_key(db, user_id, provider)
    if not key:
        return _fallback_script()
    base = resolve_base_url(db, user_id, provider)
    files_text = "\n".join(f"- {p.name}" for p in input_files)
    sys_prompt = (
        "你是 Python 数据处理脚本生成器。只输出 Python 代码（可包在 ```python 块里），不要解释。\n"
        "脚本运行目录包含 inputs/ 与 outputs/。只能读 inputs/，只能写 outputs/。\n"
        "可使用 Python 标准库与已审核的第三方库（openpyxl）。禁止调用 subprocess、ctypes、网络 socket、删除目录、eval/exec。\n"
        "如需调 LLM/知识库/员工，使用 `from modstore_runtime import ai, kb_search, employee_run`。\n"
        "脚本必须至少生成一个结果文件到 outputs/，并 print 一行进度。"
    )
    user_prompt = f"任务:\n{brief}\n\n输入文件:\n{files_text}\n\n请输出 script.py 完整内容。"
    res = await chat_dispatch(
        provider,
        api_key=key,
        base_url=base,
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=4096,
    )
    if not res.get("ok"):
        return _fallback_script()
    code = _extract_code(str(res.get("content") or ""))
    return code or _fallback_script()


async def run_script_job(
    *,
    db: Optional[Session],
    user_id: int,
    session_id: str,
    brief: str,
    files: List[Dict[str, Any]],
    provider: Optional[str],
    model: Optional[str],
) -> Dict[str, Any]:
    """一次性 "生成→校验→沙箱执行"，向后兼容 ``workbench_api`` 调用。"""
    fake_input_files = [Path(str((f or {}).get("filename") or "input.bin")) for f in files or []]
    code = await _generate_script(
        db=db,
        user_id=user_id,
        brief=brief,
        input_files=fake_input_files,
        provider=provider,
        model=model,
    )

    errors = validate_script(code)
    if errors:
        return {
            "ok": False,
            "work_dir": "",
            "script": code,
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "outputs": [],
            "errors": errors,
        }

    api_key: Optional[str] = None
    base_url: Optional[str] = None
    if db is not None and provider:
        try:
            api_key, _src = resolve_api_key(db, user_id, provider)
            base_url = resolve_base_url(db, user_id, provider)
        except Exception:  # noqa: BLE001 — key 解析失败时只是失去 ai() 能力
            api_key, base_url = None, None

    result = await _sandbox.run_in_sandbox(
        user_id=user_id,
        session_id=session_id,
        script_text=code,
        files=files or [],
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        script_root=SCRIPT_ROOT,
    )
    return {
        "ok": bool(result.ok and result.outputs),
        "work_dir": result.work_dir,
        "script": code,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
        "returncode": result.returncode,
        "outputs": result.outputs,
        "errors": result.errors,
        "sdk_calls": result.sdk_calls,
    }
