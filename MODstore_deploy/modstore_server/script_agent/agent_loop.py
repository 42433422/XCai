"""``agent_loop`` —— 把 6 个阶段串起来，按事件流方式抛给上层（SSE 用）。

事件 type 与 ``brief.AgentEvent`` 文档保持一致；上层（``script_workflow_api`` /
SSE handler）按需消费即可。每轮 trace（plan / code / check_errors /
sandbox result / verdict）也聚合为 ``trace`` 字段返回给调用方持久化到
``ScriptWorkflowVersion.agent_log_json``。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

from modstore_server.script_agent.brief import (
    AgentEvent,
    Brief,
    ContextBundle,
    PlanResult,
    Verdict,
)
from modstore_server.script_agent.code_writer import write_code
from modstore_server.script_agent.context_collector import collect_context
from modstore_server.script_agent.llm_client import LlmClient
from modstore_server.script_agent.observer import judge
from modstore_server.script_agent.planner import make_plan
from modstore_server.script_agent.repairer import repair_code
from modstore_server.script_agent.sandbox_runner import SandboxResult, run_in_sandbox
from modstore_server.script_agent.static_checker import validate_script


DEFAULT_MAX_ITERATIONS = 4


@dataclass
class AgentLoopOutcome:
    """``agent_loop`` 完成后的最终态汇总，便于落库。"""

    ok: bool
    iterations: int
    final_code: str = ""
    plan_md: str = ""
    last_result: Optional[SandboxResult] = None
    last_verdict: Optional[Verdict] = None
    trace: List[Dict[str, Any]] = field(default_factory=list)
    error: str = ""


SandboxRunner = Callable[..., Awaitable[SandboxResult]]


async def run_agent_loop(
    brief: Brief,
    *,
    llm: LlmClient,
    user_id: int,
    session_id: str,
    files: Optional[List[Dict[str, Any]]] = None,
    sandbox_runner: SandboxRunner = run_in_sandbox,
    sandbox_kwargs: Optional[Dict[str, Any]] = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> AsyncIterator[AgentEvent]:
    """主循环。``yield`` 出 :class:`AgentEvent` 流；最后一帧 ``type='done'`` 或 ``'error'``。

    调用者通常用::

        async for ev in run_agent_loop(...):
            await sse_send(ev)
            if ev.type in ("done", "error"):
                outcome = ev.payload["outcome"]
    """
    files = files or []
    sandbox_kwargs = dict(sandbox_kwargs or {})
    trace: List[Dict[str, Any]] = []

    ctx = await collect_context(brief, user_id=user_id)
    yield AgentEvent("context", 0, {
        "brief_md": ctx.brief_md,
        "inputs_summary": ctx.inputs_summary,
        "kb_chunks_md": ctx.kb_chunks_md,
        "allowlist_packages": ctx.allowlist_packages,
    })
    trace.append({"phase": "context", "iteration": 0})

    try:
        plan = await make_plan(brief, ctx, llm=llm)
    except Exception as e:  # noqa: BLE001
        outcome = AgentLoopOutcome(ok=False, iterations=0, error=f"planner: {e}", trace=trace)
        yield AgentEvent("error", 0, {"reason": f"planner failed: {e}", "outcome": _outcome_dict(outcome)})
        return
    yield AgentEvent("plan", 0, {"plan_md": plan.plan_md})
    trace.append({"phase": "plan", "iteration": 0, "plan_md": plan.plan_md})

    last_code: Optional[str] = None
    last_failure: Dict[str, Any] = {}
    final_outcome = AgentLoopOutcome(ok=False, iterations=0, plan_md=plan.plan_md, trace=trace)

    for i in range(max_iterations):
        final_outcome.iterations = i + 1
        # === code / repair ===
        try:
            if last_code is None:
                code = await write_code(brief, plan, ctx, llm=llm)
                phase_label = "code"
            else:
                code = await repair_code(brief, plan, ctx, last_code, last_failure, llm=llm)
                phase_label = "repair"
        except Exception as e:  # noqa: BLE001
            yield AgentEvent("error", i, {"reason": f"{phase_label} failed: {e}"})
            final_outcome.error = f"{phase_label}: {e}"
            yield AgentEvent("error", i, {"outcome": _outcome_dict(final_outcome)})
            return
        if not code:
            final_outcome.error = "LLM 返回空代码"
            yield AgentEvent("error", i, {"reason": final_outcome.error, "outcome": _outcome_dict(final_outcome)})
            return
        yield AgentEvent(phase_label, i, {"code": code})
        trace.append({"phase": phase_label, "iteration": i, "code_excerpt": code[:1000]})

        # === static check ===
        static_errors = validate_script(code)
        yield AgentEvent("check", i, {"ok": not static_errors, "errors": static_errors})
        trace.append({"phase": "check", "iteration": i, "errors": static_errors})
        if static_errors:
            last_code = code
            last_failure = {"static_errors": static_errors}
            continue

        # === run ===
        try:
            result = await sandbox_runner(
                user_id=user_id,
                session_id=f"{session_id}_iter{i}",
                script_text=code,
                files=files,
                **sandbox_kwargs,
            )
        except Exception as e:  # noqa: BLE001
            final_outcome.error = f"sandbox: {e}"
            yield AgentEvent("error", i, {"reason": final_outcome.error, "outcome": _outcome_dict(final_outcome)})
            return
        yield AgentEvent("run", i, {
            "ok": result.ok,
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
            "outputs": result.outputs,
            "timed_out": result.timed_out,
            "sdk_calls": result.sdk_calls,
        })
        trace.append({
            "phase": "run", "iteration": i,
            "returncode": result.returncode,
            "outputs": result.outputs,
            "timed_out": result.timed_out,
        })
        final_outcome.last_result = result

        # === observe ===
        try:
            verdict = await judge(brief, plan, result, llm=llm)
        except Exception as e:  # noqa: BLE001
            verdict = Verdict(ok=False, reason=f"observer 调用失败: {e}")
        yield AgentEvent("observe", i, {
            "ok": verdict.ok, "reason": verdict.reason, "suggestions": verdict.suggestions,
        })
        trace.append({"phase": "observe", "iteration": i, "verdict": {
            "ok": verdict.ok, "reason": verdict.reason, "suggestions": verdict.suggestions,
        }})
        final_outcome.last_verdict = verdict

        if verdict.ok and result.ok:
            final_outcome.ok = True
            final_outcome.final_code = code
            yield AgentEvent("done", i, {
                "code": code, "outputs": result.outputs,
                "outcome": _outcome_dict(final_outcome),
            })
            return

        last_code = code
        last_failure = {
            "stderr": result.stderr,
            "stdout": result.stdout,
            "returncode": result.returncode,
            "timed_out": result.timed_out,
            "verdict_reason": verdict.reason,
            "verdict_suggestions": verdict.suggestions,
        }

    final_outcome.error = "已达最大迭代轮数仍未通过验收"
    final_outcome.final_code = last_code or ""
    yield AgentEvent("error", max_iterations - 1, {
        "reason": final_outcome.error, "outcome": _outcome_dict(final_outcome),
    })


def _outcome_dict(o: AgentLoopOutcome) -> Dict[str, Any]:
    """把 outcome 序列化成可 JSON 化的 dict（SandboxResult/Verdict 拍平）。"""
    last_result = None
    if o.last_result is not None:
        last_result = {
            "ok": o.last_result.ok,
            "returncode": o.last_result.returncode,
            "stdout_tail": o.last_result.stdout[-2000:],
            "stderr_tail": o.last_result.stderr[-2000:],
            "outputs": o.last_result.outputs,
            "errors": o.last_result.errors,
            "timed_out": o.last_result.timed_out,
            "sdk_calls": o.last_result.sdk_calls,
            "work_dir": o.last_result.work_dir,
        }
    last_verdict = None
    if o.last_verdict is not None:
        last_verdict = {
            "ok": o.last_verdict.ok,
            "reason": o.last_verdict.reason,
            "suggestions": o.last_verdict.suggestions,
        }
    return {
        "ok": o.ok,
        "iterations": o.iterations,
        "final_code": o.final_code,
        "plan_md": o.plan_md,
        "last_result": last_result,
        "last_verdict": last_verdict,
        "trace": o.trace,
        "error": o.error,
    }


# ---------------------------------------------------------------------------
# vibe-coding 接入:用 NLCodeSkillFactory 生成代码 + script_agent 沙箱跑
# ---------------------------------------------------------------------------


async def run_vibe_agent_loop(
    brief: Brief,
    *,
    user_id: int,
    session_id: str,
    provider: str,
    model: str,
    files: Optional[List[Dict[str, Any]]] = None,
    sandbox_runner: SandboxRunner = run_in_sandbox,
    sandbox_kwargs: Optional[Dict[str, Any]] = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> AsyncIterator[AgentEvent]:
    """vibe-coding 驱动版的 agent loop。

    与 :func:`run_agent_loop` 行为对齐(同样的 :class:`AgentEvent` 流、SSE 兼容);
    内部:

    1. 用 ``vibe_coding.NLCodeSkillFactory`` 一次生成 brief→code(brief_first 自带
       内部沙盒校验,失败会抛 :class:`VibeCodingError`)。
    2. 把生成的代码丢给 MODstore 的 :func:`run_in_sandbox` 跑用户上传的样本文件,
       因为 vibe-coding 的内部沙盒不知道 ``ctx['files']`` 这套约定。
    3. 如果运行失败,把 stderr / observer verdict 反馈给 vibe-coding 的
       ``code_factory.repair`` 走多轮修复。
    4. PatchLedger / CodeStore 自动保留补丁链,可在工作台沙箱报告里回看。

    任何 vibe-coding 缺失/构造失败都会立刻 ``yield`` 一帧 ``error`` 并退出,
    上层 SSE 消费者按通用错误处理即可。
    """
    files = files or []
    sandbox_kwargs = dict(sandbox_kwargs or {})
    trace: List[Dict[str, Any]] = []

    try:
        from modstore_server.integrations.vibe_adapter import (
            VibeIntegrationError,
            get_vibe_coder,
        )
    except ImportError as exc:
        outcome = AgentLoopOutcome(
            ok=False, iterations=0, error=f"integrations 未导入: {exc}", trace=trace
        )
        yield AgentEvent(
            "error", 0, {"reason": str(outcome.error), "outcome": _outcome_dict(outcome)}
        )
        return

    ctx = await collect_context(brief, user_id=user_id)
    yield AgentEvent("context", 0, {
        "brief_md": ctx.brief_md,
        "inputs_summary": ctx.inputs_summary,
        "kb_chunks_md": ctx.kb_chunks_md,
        "allowlist_packages": ctx.allowlist_packages,
    })
    trace.append({"phase": "context", "iteration": 0, "engine": "vibe"})

    from modstore_server.models import get_session_factory

    sf = get_session_factory()
    coder = None
    try:
        with sf() as session:
            coder = get_vibe_coder(
                session=session, user_id=int(user_id or 0), provider=provider, model=model
            )
    except VibeIntegrationError as exc:
        outcome = AgentLoopOutcome(ok=False, iterations=0, error=str(exc), trace=trace)
        yield AgentEvent(
            "error", 0, {"reason": str(exc), "outcome": _outcome_dict(outcome)}
        )
        return
    except Exception as exc:  # noqa: BLE001
        outcome = AgentLoopOutcome(
            ok=False, iterations=0, error=f"vibe coder 构造失败: {exc}", trace=trace
        )
        yield AgentEvent(
            "error", 0, {"reason": str(outcome.error), "outcome": _outcome_dict(outcome)}
        )
        return

    yield AgentEvent("plan", 0, {"plan_md": ctx.brief_md or brief.goal or ""})
    trace.append({"phase": "plan", "iteration": 0, "engine": "vibe"})

    last_skill = None
    last_failure: Dict[str, Any] = {}
    final_outcome = AgentLoopOutcome(
        ok=False, iterations=0, plan_md=ctx.brief_md or brief.goal or "", trace=trace
    )

    brief_text = (ctx.brief_md or brief.goal or "").strip()
    skill_id_hint: Optional[str] = f"script_{session_id}" if session_id else None

    for i in range(max_iterations):
        final_outcome.iterations = i + 1
        try:
            if last_skill is None:
                skill = await asyncio.to_thread(
                    coder.code, brief_text, mode="brief_first", skill_id=skill_id_hint
                )
                phase_label = "code"
            else:
                # vibe-coding 的 code_factory.repair(skill_id, failure) 针对失败诊断回滚 +
                # 重新生成。这里把 sandbox stderr 与 verdict 反馈给它。
                failure_blob = {
                    "stderr": last_failure.get("stderr") or "",
                    "stdout": last_failure.get("stdout") or "",
                    "verdict_reason": last_failure.get("verdict_reason") or "",
                    "verdict_suggestions": last_failure.get("verdict_suggestions") or [],
                }
                skill = await asyncio.to_thread(
                    coder.code_factory.repair, skill_id_hint or last_skill.skill_id, failure_blob
                )
                phase_label = "repair"
        except Exception as exc:  # noqa: BLE001
            yield AgentEvent("error", i, {"reason": f"vibe {phase_label} failed: {exc}"})
            final_outcome.error = f"vibe {phase_label}: {exc}"
            yield AgentEvent("error", i, {"outcome": _outcome_dict(final_outcome)})
            return

        code = (getattr(skill, "code", "") or "").strip()
        if not code:
            final_outcome.error = "vibe-coding 返回空代码"
            yield AgentEvent("error", i, {
                "reason": final_outcome.error, "outcome": _outcome_dict(final_outcome)
            })
            return
        last_skill = skill
        skill_id_hint = getattr(skill, "skill_id", None) or skill_id_hint
        yield AgentEvent(phase_label, i, {"code": code, "skill_id": skill_id_hint})
        trace.append({
            "phase": phase_label, "iteration": i, "engine": "vibe",
            "skill_id": skill_id_hint, "code_excerpt": code[:1000],
        })

        # static check 仍走 MODstore 的 validate_script(更贴 MODstore allowlist)
        static_errors = validate_script(code)
        yield AgentEvent("check", i, {"ok": not static_errors, "errors": static_errors})
        trace.append({"phase": "check", "iteration": i, "engine": "vibe", "errors": static_errors})
        if static_errors:
            last_failure = {
                "stderr": "\n".join(static_errors),
                "stdout": "",
                "verdict_reason": "static_check_failed",
                "verdict_suggestions": [],
            }
            continue

        try:
            result = await sandbox_runner(
                user_id=user_id,
                session_id=f"{session_id}_iter{i}_vibe",
                script_text=code,
                files=files,
                **sandbox_kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            final_outcome.error = f"sandbox: {exc}"
            yield AgentEvent("error", i, {
                "reason": final_outcome.error, "outcome": _outcome_dict(final_outcome)
            })
            return
        yield AgentEvent("run", i, {
            "ok": result.ok,
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
            "outputs": result.outputs,
            "timed_out": result.timed_out,
            "sdk_calls": result.sdk_calls,
        })
        trace.append({
            "phase": "run", "iteration": i, "engine": "vibe",
            "returncode": result.returncode, "outputs": result.outputs,
            "timed_out": result.timed_out,
        })
        final_outcome.last_result = result

        from modstore_server.script_agent.brief import PlanResult as _PlanResult

        plan_obj = _PlanResult(plan_md=ctx.brief_md or brief.goal or "")
        try:
            from modstore_server.script_agent.llm_client import RealLlmClient

            with sf() as judge_session:
                judge_llm = RealLlmClient.from_user_session(
                    judge_session, int(user_id or 0), provider, model
                )
                verdict = await judge(brief, plan_obj, result, llm=judge_llm)
        except Exception as exc:  # noqa: BLE001
            verdict = Verdict(ok=False, reason=f"observer 调用失败: {exc}")
        yield AgentEvent("observe", i, {
            "ok": verdict.ok, "reason": verdict.reason, "suggestions": verdict.suggestions,
        })
        trace.append({"phase": "observe", "iteration": i, "engine": "vibe", "verdict": {
            "ok": verdict.ok, "reason": verdict.reason, "suggestions": verdict.suggestions,
        }})
        final_outcome.last_verdict = verdict

        if verdict.ok and result.ok:
            final_outcome.ok = True
            final_outcome.final_code = code
            yield AgentEvent("done", i, {
                "code": code, "outputs": result.outputs,
                "skill_id": skill_id_hint,
                "outcome": _outcome_dict(final_outcome),
            })
            return

        last_failure = {
            "stderr": result.stderr, "stdout": result.stdout,
            "returncode": result.returncode, "timed_out": result.timed_out,
            "verdict_reason": verdict.reason, "verdict_suggestions": verdict.suggestions,
        }

    final_outcome.error = "vibe agent 已达最大迭代轮数仍未通过验收"
    final_outcome.final_code = (getattr(last_skill, "code", "") or "") if last_skill else ""
    yield AgentEvent("error", max_iterations - 1, {
        "reason": final_outcome.error, "outcome": _outcome_dict(final_outcome),
    })
