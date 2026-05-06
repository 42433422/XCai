"""Sub-agent Task tool for AgentLoop.

Allows the LLM to fork a child AgentLoop with an isolated context window.
The child agent runs to completion and only its ``final_answer`` is injected
back into the parent's observation history, keeping the parent context lean.

Sub-agent types
---------------
``explore``  — read-only fast search tools (ripgrep, glob, read_file_v2, find_symbol)
``shell``    — sandbox ``run_command`` only
``general``  — full tool set (same as parent, minus todo management)

Background mode
---------------
When ``run_in_background=True`` the tool returns immediately with a task_id.
The parent can later poll with ``subagent_status(task_id)`` or simply wait —
the result is also available in the events stream.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..react.tools import Tool, ToolRegistry, ToolResult, tool


@dataclass
class SubagentTask:
    """Running or completed sub-agent task."""

    task_id: str
    description: str
    subagent_type: str
    status: str = "pending"        # "pending" | "running" | "done" | "error"
    final_answer: str = ""
    error: str = ""
    steps: int = 0


class SubagentManager:
    """Manages child AgentLoop instances for a parent run."""

    def __init__(
        self,
        *,
        parent_llm: Any,
        parent_tools: ToolRegistry | None = None,
        project_root: Path | None = None,
        max_steps: int = 15,
    ) -> None:
        self._llm = parent_llm
        self._parent_tools = parent_tools
        self._root = project_root
        self._max_steps = max_steps
        self._tasks: dict[str, SubagentTask] = {}
        self._results: dict[str, str] = {}   # task_id → final_answer

    def make_tools(self) -> list[Tool]:
        """Return ``[task, subagent_status]`` tools for registration in the parent bus."""
        manager = self

        @tool(
            "task",
            description=(
                "Launch a child agent to handle a sub-problem.  "
                "Types: 'explore' (read-only search), 'shell' (run commands), "
                "'general' (full tools).  "
                "Set run_in_background=true to return immediately with a task_id; "
                "otherwise blocks until the child agent finishes."
            ),
            arguments=[
                {"name": "description", "type": "string", "required": True,
                 "description": "what the sub-agent should do"},
                {"name": "subagent_type", "type": "string", "required": True,
                 "description": "explore | shell | general"},
                {"name": "prompt", "type": "string", "required": True,
                 "description": "the goal / question for the sub-agent"},
                {"name": "run_in_background", "type": "boolean", "required": False,
                 "description": "return task_id immediately instead of waiting (default false)"},
            ],
        )
        def task_tool(
            description: str,
            subagent_type: str,
            prompt: str,
            *,
            run_in_background: bool = False,
        ) -> ToolResult:
            return manager._launch(
                description=description,
                subagent_type=subagent_type,
                prompt=prompt,
                background=run_in_background,
            )

        @tool(
            "subagent_status",
            description="Poll the status / result of a background sub-agent task.",
        )
        def subagent_status(task_id: str) -> dict[str, Any]:
            t = manager._tasks.get(task_id)
            if t is None:
                return {"task_id": task_id, "status": "not_found"}
            return {
                "task_id": t.task_id,
                "status": t.status,
                "final_answer": t.final_answer,
                "error": t.error,
                "steps": t.steps,
            }

        return [task_tool, subagent_status]

    # ---------------------------------------------------------------- internals

    def _launch(
        self,
        *,
        description: str,
        subagent_type: str,
        prompt: str,
        background: bool,
    ) -> ToolResult:
        from .loop import AgentLoop

        task_id = uuid.uuid4().hex[:10]
        sa_task = SubagentTask(
            task_id=task_id,
            description=description,
            subagent_type=subagent_type,
            status="pending",
        )
        self._tasks[task_id] = sa_task

        tools = self._build_tools_for_type(subagent_type)
        child_loop = AgentLoop(
            self._llm,
            tools=tools,
            mode="agent",
            max_steps=self._max_steps,
            allow_parallel=(subagent_type == "explore"),
        )

        def _run() -> None:
            sa_task.status = "running"
            try:
                result = child_loop.run(prompt, run_id=task_id)
                sa_task.status = "done" if result.success else "error"
                sa_task.final_answer = result.final_answer
                sa_task.error = result.error
                sa_task.steps = result.steps
                self._results[task_id] = result.final_answer
            except Exception as exc:  # noqa: BLE001
                sa_task.status = "error"
                sa_task.error = str(exc)

        if background:
            thread = threading.Thread(target=_run, daemon=True, name=f"subagent-{task_id}")
            thread.start()
            return ToolResult(
                success=True,
                observation=f"[subagent started] task_id={task_id}; type={subagent_type}; poll with subagent_status(task_id='{task_id}')",
                output={"task_id": task_id, "status": "running"},
            )
        else:
            _run()
            if sa_task.status == "done":
                ans = sa_task.final_answer[:4_000]
                return ToolResult(
                    success=True,
                    observation=f"[subagent done] {description}\n\n{ans}",
                    output={"task_id": task_id, "final_answer": sa_task.final_answer, "steps": sa_task.steps},
                )
            return ToolResult(
                success=False,
                observation=f"[subagent error] {description}: {sa_task.error}",
                error=sa_task.error,
            )

    def _build_tools_for_type(self, subagent_type: str) -> ToolRegistry:
        """Return appropriate tool registry for the given subagent type."""
        reg = ToolRegistry()

        if subagent_type in ("explore", "general") and self._root:
            try:
                from ..react.builtins import make_fast_search_tools, make_filesystem_tools
                for t in make_fast_search_tools(self._root):
                    try:
                        reg.register(t)
                    except ValueError:
                        pass
                if subagent_type == "general":
                    for t in make_filesystem_tools(self._root):
                        if t.name not in ("read_file",):   # superseded by read_file_v2
                            try:
                                reg.register(t)
                            except ValueError:
                                pass
            except ImportError:
                pass

        if subagent_type in ("shell", "general") and self._root:
            try:
                from ..react.builtins import make_shell_tool, make_git_tools
                try:
                    reg.register(make_shell_tool(self._root))
                except ValueError:
                    pass
                for t in make_git_tools(self._root):
                    try:
                        reg.register(t)
                    except ValueError:
                        pass
            except ImportError:
                pass

        if subagent_type == "general" and self._parent_tools:
            # Copy remaining parent tools not already registered
            seen: set[int] = set()
            for t in self._parent_tools:
                if id(t) in seen:
                    continue
                seen.add(id(t))
                try:
                    reg.register(t)
                except ValueError:
                    pass

        return reg


__all__ = ["SubagentManager", "SubagentTask"]
