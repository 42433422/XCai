"""``repairer`` —— 失败时把"原脚本 + 错误信息 + 验收期望"打包让 LLM 改。

入参 ``last_failure`` 通常包含以下字段之一或多个：
- ``static_errors``: list[str]      —— 静态检查失败
- ``stderr``: str                   —— 子进程 stderr
- ``returncode``: int
- ``timed_out``: bool
- ``verdict_reason``: str           —— observer 判定不通过原因
- ``verdict_suggestions``: list[str]
"""

from __future__ import annotations

from typing import Any, Dict, List

from modstore_server.script_agent.brief import Brief, ContextBundle, PlanResult
from modstore_server.script_agent.llm_client import LlmClient, extract_code_block


REPAIR_SYSTEM_PROMPT = """\
你是 Python 编程代理的"修复官"。给定上一轮的 ``script.py`` 与失败信息，请输出修复后的 **完整** ``script.py``。
约束（与首轮生成相同）：
- 必须 ``if __name__ == "__main__":`` 入口；至少 ``print`` 一行进度
- 仅允许 import：stdlib（除 subprocess/ctypes/multiprocessing）+ 审核 allowlist + ``modstore_runtime``
- 严禁 ``eval/exec/compile/__import__``、``os.system``、``subprocess.*``
- 优先修最可能让验收通过的那个根因；不要做无关重构

只输出代码（可包在 ```python``` 块里），不要解释。"""


def _format_failure(failure: Dict[str, Any]) -> str:
    lines: List[str] = []
    if failure.get("static_errors"):
        lines.append("静态检查失败：")
        for e in failure["static_errors"]:
            lines.append(f"  - {e}")
    if failure.get("timed_out"):
        lines.append("脚本运行超时")
    rc = failure.get("returncode")
    if rc is not None and rc != 0:
        lines.append(f"返回码：{rc}")
    if failure.get("stderr"):
        lines.append("stderr 末段：")
        lines.append(str(failure["stderr"])[-1500:])
    if failure.get("stdout"):
        lines.append("stdout 末段：")
        lines.append(str(failure["stdout"])[-800:])
    if failure.get("verdict_reason"):
        lines.append(f"验收不通过原因：{failure['verdict_reason']}")
    if failure.get("verdict_suggestions"):
        lines.append("验收建议：")
        for s in failure["verdict_suggestions"]:
            lines.append(f"  - {s}")
    return "\n".join(lines) or "(无具体错误信息)"


async def repair_code(
    brief: Brief,
    plan: PlanResult,
    ctx: ContextBundle,
    last_code: str,
    last_failure: Dict[str, Any],
    *,
    llm: LlmClient,
    max_tokens: int = 4096,
) -> str:
    sys_msg = REPAIR_SYSTEM_PROMPT
    appendix = ctx.as_system_prompt_appendix()
    if appendix:
        sys_msg += "\n\n# 上下文\n" + appendix

    user_msg = (
        "# 用户需求\n" + brief.as_markdown()
        + "\n\n# 计划\n" + plan.plan_md
        + "\n\n# 上一轮 script.py\n```python\n" + last_code + "\n```\n"
        + "\n\n# 失败信息\n" + _format_failure(last_failure)
    )
    raw = await llm.chat(
        [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=max_tokens,
    )
    return extract_code_block(raw, lang="python")
