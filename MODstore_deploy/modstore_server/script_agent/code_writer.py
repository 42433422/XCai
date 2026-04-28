"""``code_writer`` —— 让 LLM 按 plan.md 写出完整 ``script.py``。

强约束 prompt 让产物更可能一次过静检：
- 必须 ``if __name__ == "__main__":`` 入口
- 只能用 stdlib + allowlist 第三方包 + ``modstore_runtime``
- 写产物到 ``outputs/``，读输入从 ``inputs/``
- 至少 print 一行进度
"""

from __future__ import annotations

from typing import Optional

from modstore_server.script_agent.brief import Brief, ContextBundle, PlanResult
from modstore_server.script_agent.llm_client import LlmClient, extract_code_block


CODE_SYSTEM_PROMPT = """\
你是 Python 编程代理的"实现官"。请按 plan.md 写出 **完整可运行** 的 ``script.py``。
硬约束：
- 必须有 ``if __name__ == "__main__":`` 入口；逻辑写在函数里调用之
- 仅允许 import: Python 标准库（除 subprocess/ctypes/multiprocessing 外）+ 已审核三方包 + ``modstore_runtime``
- 调 LLM/知识库/员工：``from modstore_runtime import ai, kb_search, employee_run``
- 调 HTTP：``from modstore_runtime import http_get``
- 读输入：``from pathlib import Path; Path('inputs/...').read_*()`` 或 ``inputs.path('...')``
- 写输出：``Path('outputs/...').write_*()`` 或 ``outputs.write_*()``；至少产出一个文件到 ``outputs/``
- 至少 ``print`` 一行总结性进度（最终状态、关键统计），便于观察通过
- 严禁 ``eval / exec / compile / __import__``；严禁 ``os.system / subprocess.*``

只输出代码，可包在 ```python``` 块里，不要解释。"""


async def write_code(
    brief: Brief,
    plan: PlanResult,
    ctx: ContextBundle,
    *,
    llm: LlmClient,
    max_tokens: int = 4096,
    extra_instruction: Optional[str] = None,
) -> str:
    sys_msg = CODE_SYSTEM_PROMPT
    appendix = ctx.as_system_prompt_appendix()
    if appendix:
        sys_msg += "\n\n# 上下文\n" + appendix

    user_msg = (
        "# 用户需求\n"
        + ctx.brief_md
        + "\n\n# 计划\n"
        + plan.plan_md
    )
    if extra_instruction and extra_instruction.strip():
        user_msg += "\n\n# 额外指令\n" + extra_instruction.strip()

    raw = await llm.chat(
        [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=max_tokens,
    )
    code = extract_code_block(raw, lang="python")
    return code
