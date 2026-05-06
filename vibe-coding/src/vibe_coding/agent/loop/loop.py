"""AgentLoop v2 — the central autonomous-agent kernel.

Plan mode
---------
Set ``mode="plan"`` to get a read-only, exploratory pass.  The bus blocks
write tools; the LLM must call ``present_plan(title, summary, plan_md)`` to
finish.  The ``plan_proposed`` event carries the full plan for the caller to
display / confirm before switching to ``mode="agent"`` for execution.

Sub-agents
----------
Pass ``subagent_manager=...`` (or set ``project_root`` to enable auto-creation)
to get the ``task`` + ``subagent_status`` tools in the registry.  Sub-agents
run with an isolated context; only ``final_answer`` returns to the parent.


Replaces :class:`vibe_coding.agent.react.ReActAgent` as the primary loop.
The old class is kept as a thin shim that delegates here.

Usage (async streaming)
-----------------------
    loop = AgentLoop(
        llm=my_llm,
        tools=builtin_tools(root="."),
        mode="agent",
    )
    async for event in loop.arun("把所有 print() 换成 logger.info()"):
        print(event.to_dict())

Usage (sync, for backward compat)
----------------------------------
    result = loop.run("...")
    print(result.final_answer)
"""

from __future__ import annotations

import asyncio
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable

from ...nl.llm import LLMClient
from ..react.tools import Tool, ToolRegistry, ToolResult, tool
from .context_manager import ContextManager
from .events import AgentEvent, EventType
from .function_calling import FunctionCallingAdapter, LLMTurn, ToolCallRequest
from .todos import SYSTEM_RULE, TodoStore
from .tool_bus import ToolBus


# ---------------------------------------------------------------- result type

@dataclass(slots=True)
class AgentLoopResult:
    """Outcome of a completed ``AgentLoop.run`` call."""

    success: bool
    goal: str
    final_answer: str = ""
    steps: int = 0
    total_ms: float = 0.0
    error: str = ""
    todos: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "goal": self.goal,
            "final_answer": self.final_answer,
            "steps": self.steps,
            "total_ms": self.total_ms,
            "error": self.error,
            "todos": list(self.todos),
        }


# ---------------------------------------------------------------- run options

@dataclass
class RunOptions:
    """Optional parameters for ``AgentLoop.run / arun``."""

    context: str = ""
    run_id: str = ""
    on_event: Callable[[AgentEvent], None] | None = None
    # Called after every parallel-tool-batch with list of (name, result)
    on_tools_done: Callable[[list[tuple[str, ToolResult]]], None] | None = None


# ---------------------------------------------------------------- system prompt helpers

_BASE_SYSTEM = textwrap.dedent("""\
    你是一个**自主规划的工具调用 Agent**，运行模式：{mode}。

    {todo_rule}
    {tools_addendum}

    规则：
    1. 工具响应（## Observation N）给出结果后，再思考下一步。
    2. 可用工具见上文 ## Tools；不要调用未列出的工具。
    3. 遇到只读工具（read_file、grep 等）时，可在 JSON 数组中一次请求多个以加速。
    4. 对写操作（apply_edit、write_file、run_command 等）一次只请求一个。
    5. 完成目标时输出 final_answer，不再调用工具。
    6. 最多 {max_steps} 步；在你确信完成目标时尽早输出 final_answer。
""")


class AgentLoop:
    """Claude Code-parity autonomous agent loop.

    Parameters
    ----------
    llm:
        Any ``LLMClient`` (or provider with optional ``chat_with_tools``).
    tools:
        Either a ``ToolRegistry``, a ``ToolBus``, or a list of ``Tool`` objects.
    mode:
        ``"agent"`` (default) — full tool access.
        ``"plan"`` — write tools blocked; terminates via ``present_plan``.
    max_steps:
        Hard cap on LLM round-trips per ``run`` call.
    allow_parallel:
        Permit the LLM to batch read-only tools in one turn (default True).
    store_dir:
        Optional path for todo persistence.
    """

    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry | ToolBus | list[Tool] | None = None,
        *,
        mode: str = "agent",
        max_steps: int = 30,
        allow_parallel: bool = True,
        store_dir: Any | None = None,
        system_addendum: str = "",
        context_mgr: ContextManager | None = None,
        project_root: Any | None = None,
        enable_subagents: bool = False,
        enable_plan_mode_tool: bool = True,
    ) -> None:
        self.llm = llm
        self.mode = mode
        self.max_steps = max(1, int(max_steps))
        self.allow_parallel = allow_parallel
        self.system_addendum = system_addendum
        self._store_dir = store_dir
        self._project_root = project_root
        self._enable_subagents = enable_subagents
        self._enable_plan_mode_tool = enable_plan_mode_tool

        # ---- build ToolBus
        from pathlib import Path as _Path
        _root = _Path(str(project_root)).resolve() if project_root else None
        self.bus = ToolBus(
            mode=mode,
            project_root=_root,
        )
        if tools is None:
            pass
        elif isinstance(tools, ToolBus):
            self.bus = tools
            self.bus.mode = mode
        elif isinstance(tools, ToolRegistry):
            self.bus.register_from_registry(tools)
        elif isinstance(tools, list):
            for t in tools:
                self.bus.register(t)
        else:
            raise TypeError(f"tools must be ToolRegistry, ToolBus, or list[Tool], got {type(tools)}")

        # ---- function-calling adapter
        self._fc = FunctionCallingAdapter(
            llm,
            self.bus.to_registry(),
            allow_parallel=allow_parallel,
        )

        # ---- context manager
        self._ctx = context_mgr or ContextManager(llm=llm)

        # ---- plan-mode termination event (set when present_plan is called)
        self._plan_proposed: dict[str, Any] | None = None

    # ---------------------------------------------------------------- public

    def run(
        self,
        goal: str,
        *,
        context: str = "",
        run_id: str = "",
        on_event: Callable[[AgentEvent], None] | None = None,
    ) -> AgentLoopResult:
        """Synchronous wrapper around ``arun``."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        opts = RunOptions(context=context, run_id=run_id, on_event=on_event)
        return loop.run_until_complete(self._collect(goal, opts))

    async def arun(
        self,
        goal: str,
        *,
        context: str = "",
        run_id: str = "",
        on_event: Callable[[AgentEvent], None] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Async generator; yields ``AgentEvent`` objects."""
        opts = RunOptions(context=context, run_id=run_id, on_event=on_event)
        async for event in self._run_loop(goal, opts):
            yield event

    # ---------------------------------------------------------------- internals

    async def _collect(self, goal: str, opts: RunOptions) -> AgentLoopResult:
        """Collect all events from the async generator into a result."""
        events: list[dict[str, Any]] = []
        result = AgentLoopResult(success=False, goal=goal)
        t0 = time.perf_counter()
        async for ev in self._run_loop(goal, opts):
            events.append(ev.to_dict())
            if ev.type == EventType.FINAL_ANSWER:
                result.success = True
                result.final_answer = ev.payload.get("answer", "")
                result.steps = ev.payload.get("steps", 0)
            elif ev.type == EventType.ERROR:
                result.error = ev.payload.get("reason", "")
            elif ev.type == EventType.TODO_UPDATE:
                result.todos = list(ev.payload.get("todos") or [])
        result.total_ms = round((time.perf_counter() - t0) * 1000, 3)
        result.events = events
        return result

    async def _run_loop(
        self,
        goal: str,
        opts: RunOptions,
    ) -> AsyncIterator[AgentEvent]:
        run_id = opts.run_id or uuid.uuid4().hex[:12]
        from pathlib import Path as _Path
        persist_dir = _Path(str(self._store_dir)) / "todos" if self._store_dir else None

        # ---- todo store
        todo_store = TodoStore(run_id=run_id, persist_dir=persist_dir)
        try:
            self.bus.register(todo_store.make_tool())
        except ValueError:
            pass
        try:
            self.bus.register(todo_store.make_list_tool())
        except ValueError:
            pass

        # ---- plan-mode present_plan tool
        self._plan_proposed = None
        if self._enable_plan_mode_tool:
            loop_self = self

            @tool(
                "present_plan",
                description=(
                    "Finish the planning phase.  Call this when you have a complete plan "
                    "ready for user review.  In agent mode this just records the plan; "
                    "in plan mode it terminates the loop."
                ),
                arguments=[
                    {"name": "title", "type": "string", "required": True,
                     "description": "short plan title"},
                    {"name": "summary", "type": "string", "required": True,
                     "description": "1-3 sentence overview"},
                    {"name": "plan_md", "type": "string", "required": True,
                     "description": "full markdown plan"},
                ],
            )
            def present_plan_tool(title: str, summary: str, plan_md: str) -> ToolResult:
                loop_self._plan_proposed = {
                    "title": title,
                    "summary": summary,
                    "plan_md": plan_md,
                }
                return ToolResult(
                    success=True,
                    observation=f"[plan recorded] {title}: {summary[:120]}",
                    output=loop_self._plan_proposed,
                )

            try:
                self.bus.register(present_plan_tool, read_only=True)
            except ValueError:
                pass

        # ---- subagent tools
        if self._enable_subagents:
            from .subagents import SubagentManager
            _root = _Path(str(self._project_root)).resolve() if self._project_root else None
            sa_mgr = SubagentManager(
                parent_llm=self.llm,
                parent_tools=self.bus.to_registry(),
                project_root=_root,
                max_steps=max(10, self.max_steps // 2),
            )
            for sa_tool in sa_mgr.make_tools():
                try:
                    self.bus.register(sa_tool)
                except ValueError:
                    pass

        # Rebuild FC adapter with all tools now registered
        self._fc = FunctionCallingAdapter(
            self.llm, self.bus.to_registry(), allow_parallel=self.allow_parallel
        )

        # hook: fire todo_update events
        def _on_todo_change(store: TodoStore) -> None:
            ev = AgentEvent.todo_update(store.todos, run_id=run_id)
            ev.run_id = run_id
            _emit(ev)

        todo_store._on_change = _on_todo_change

        # ---- event queue for sync callbacks
        pending_events: list[AgentEvent] = []

        def _emit(ev: AgentEvent) -> None:
            ev.run_id = run_id
            pending_events.append(ev)
            if opts.on_event:
                try:
                    opts.on_event(ev)
                except Exception:  # noqa: BLE001
                    pass

        self._ctx.clear()

        system = self._build_system(todo_store)
        t_start = time.perf_counter()

        for step_idx in range(1, self.max_steps + 1):
            # flush pending events from callbacks
            for ev in pending_events:
                yield ev
            pending_events.clear()

            user_prompt = self._ctx.build_user_prompt(
                goal,
                opts.context,
                todo_summary=todo_store.summary(),
            )
            # Rebuild system with current todo context
            system = self._build_system(todo_store)

            turn: LLMTurn = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda s=system, u=user_prompt: self._fc.call(s, u, max_steps=self.max_steps),
            )

            if turn.parse_error:
                _emit(AgentEvent(
                    type=EventType.STEP,
                    payload={"step": step_idx, "thought": "", "error": turn.parse_error},
                    step_index=step_idx,
                ))
                self._ctx.add_observation(step_idx, f"[parse_error] {turn.parse_error}")
                for _pev in pending_events:
                    yield _pev
                pending_events.clear()
                continue

            _emit(AgentEvent(
                type=EventType.STEP,
                payload={
                    "step": step_idx,
                    "thought": turn.thought[:500],
                    "tool_calls": [{"tool": tc.tool, "args": tc.args} for tc in turn.tool_calls],
                    "has_final": bool(turn.final_answer),
                },
                step_index=step_idx,
            ))

            # ---- final answer
            if turn.final_answer:
                total_ms = round((time.perf_counter() - t_start) * 1000, 3)
                ev = AgentEvent.final_answer(turn.final_answer, steps=step_idx, total_ms=total_ms)
                ev.run_id = run_id
                _emit(ev)
                for ev2 in pending_events:
                    yield ev2
                return

            # ---- tool calls
            if not turn.tool_calls:
                # LLM returned neither tools nor final_answer — treat as no-op
                self._ctx.add_observation(step_idx, "(no action)")
                for _pev in pending_events:
                    yield _pev
                pending_events.clear()
                continue

            # Emit parallel start event if multiple calls
            if len(turn.tool_calls) > 1:
                _emit(AgentEvent(
                    type=EventType.TOOL_CALLS_PARALLEL,
                    payload={"calls": [{"tool": tc.tool, "args": tc.args} for tc in turn.tool_calls]},
                    step_index=step_idx,
                ))

            # Flush before executing tools (emit start events)
            for ev in pending_events:
                yield ev
            pending_events.clear()

            # --- dispatch tools
            batch: list[tuple[str, dict[str, Any]]] = [
                (tc.tool, tc.args) for tc in turn.tool_calls
            ]
            start_events: list[AgentEvent] = []
            end_events: list[AgentEvent] = []
            name_order: list[str] = []

            def on_start(name: str, args: dict[str, Any], _si: int = step_idx) -> None:
                ev = AgentEvent.tool_call_start(name, args, step_index=_si)
                ev.run_id = run_id
                start_events.append(ev)

            def on_end(name: str, res: ToolResult, dur: float, _si: int = step_idx) -> None:
                ev = AgentEvent.tool_call_end(
                    name,
                    success=res.success,
                    observation=res.observation,
                    output=res.output,
                    error=res.error,
                    duration_ms=dur,
                    step_index=_si,
                )
                ev.run_id = run_id
                end_events.append(ev)
                name_order.append(name)

            results = await self.bus.call_many(
                batch,
                step_index=step_idx,
                on_start=on_start,
                on_end=on_end,
            )

            # Yield start → end in order
            for _sev in start_events:
                yield _sev
            for _eev in end_events:
                yield _eev

            # Track file reads for dedup
            for tc, res in zip(turn.tool_calls, results):
                if tc.tool in ("read_file", "read_file_v2"):
                    path = tc.args.get("path", "")
                    if path and res.success and isinstance(res.output, str):
                        known = self._ctx.note_file_read(path, res.output)
                        if known:
                            res = ToolResult(
                                success=res.success,
                                observation=f"[file already read this session — using memory]\n{res.observation[:400]}",
                                output=res.output,
                                error=res.error,
                            )

            # Aggregate observations
            if len(results) == 1:
                self._ctx.add_observation(step_idx, results[0].observation)
            else:
                agg = "\n\n".join(
                    f"[{tc.tool}] {r.observation}"
                    for tc, r in zip(turn.tool_calls, results)
                )
                self._ctx.add_observation(step_idx, agg)

            # notify caller
            if opts.on_tools_done:
                pairs = [(tc.tool, r) for tc, r in zip(turn.tool_calls, results)]
                try:
                    opts.on_tools_done(pairs)
                except Exception:  # noqa: BLE001
                    pass

            # ---- check if plan_proposed was set by this round's tool calls (plan mode)
            if self._plan_proposed is not None and self.mode == "plan":
                plan_ev = AgentEvent(
                    type=EventType.PLAN_PROPOSED,
                    payload=dict(self._plan_proposed),
                    step_index=step_idx,
                )
                plan_ev.run_id = run_id
                _emit(plan_ev)
                for _pev in pending_events:
                    yield _pev
                return

        # max_steps exhausted
        total_ms = round((time.perf_counter() - t_start) * 1000, 3)
        ev = AgentEvent.error(
            f"max_steps={self.max_steps} reached without a final answer",
            step_index=self.max_steps,
        )
        ev.run_id = run_id
        yield ev

    # ---------------------------------------------------------------- helpers

    def _build_system(self, todo_store: TodoStore | None = None) -> str:
        todo_rule = SYSTEM_RULE if self.mode == "agent" else ""
        tools_addendum = self._fc.build_system_addendum() if hasattr(self, "_fc") else ""
        base = _BASE_SYSTEM.format(
            mode=self.mode,
            todo_rule=todo_rule.strip(),
            tools_addendum=tools_addendum.strip(),
            max_steps=self.max_steps,
        ).strip()
        if self.system_addendum:
            base += "\n\n## Extra instructions\n\n" + self.system_addendum.strip()
        return base

    # ---------------------------------------------------------------- class helpers

    @classmethod
    def from_registry(
        cls,
        llm: LLMClient,
        registry: ToolRegistry,
        **kwargs: Any,
    ) -> "AgentLoop":
        return cls(llm, tools=registry, **kwargs)


__all__ = ["AgentLoop", "AgentLoopResult", "RunOptions"]
