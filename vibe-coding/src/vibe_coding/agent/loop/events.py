"""Structured event schema for AgentLoop's streaming output.

Every ``AgentEvent`` is JSON-serialisable and can be forwarded to:
- SSE handlers (workbench, web cockpit)
- CLI rich.live panels
- Test assertions

Event types
-----------
``step``              — LLM Thought + tool selection (one per loop iteration)
``tool_call_start``   — a specific tool is about to be invoked
``tool_call_end``     — tool finished; carries observation text
``tool_calls_parallel`` — multiple read-only tools started concurrently
``todo_update``       — TodoStore state changed (driven by ``todo_write`` tool)
``plan_proposed``     — plan mode finished; carries plan markdown + todos
``subagent_start``    — a child AgentLoop was launched
``subagent_end``      — child loop finished; final_answer injected into parent
``lints``             — post-edit lint results from ruff/eslint/mypy
``context_summary``   — ContextManager summarised a long observation
``final_answer``      — loop completed successfully
``error``             — loop terminated with an error
``cancelled``         — loop was cancelled by the caller
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    STEP = "step"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    TOOL_CALLS_PARALLEL = "tool_calls_parallel"
    TODO_UPDATE = "todo_update"
    PLAN_PROPOSED = "plan_proposed"
    SUBAGENT_START = "subagent_start"
    SUBAGENT_END = "subagent_end"
    LINTS = "lints"
    CONTEXT_SUMMARY = "context_summary"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class AgentEvent:
    """One event emitted by :class:`AgentLoop`.

    ``type`` identifies the kind; ``payload`` carries type-specific data.
    ``ts`` is a float Unix timestamp set at construction time.
    ``run_id`` is filled in by the loop before yielding.
    """

    type: EventType | str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    run_id: str = ""
    step_index: int = 0

    # ---------------------------------------------------------------- helpers

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type if isinstance(self.type, str) else self.type.value,
            "payload": dict(self.payload),
            "ts": self.ts,
            "run_id": self.run_id,
            "step_index": self.step_index,
        }

    # Convenience constructors -------------------------------------------

    @classmethod
    def tool_call_start(
        cls,
        tool: str,
        args: dict[str, Any],
        *,
        step_index: int = 0,
        parallel_batch: int | None = None,
    ) -> "AgentEvent":
        p: dict[str, Any] = {"tool": tool, "args": args}
        if parallel_batch is not None:
            p["parallel_batch"] = parallel_batch
        return cls(type=EventType.TOOL_CALL_START, payload=p, step_index=step_index)

    @classmethod
    def tool_call_end(
        cls,
        tool: str,
        *,
        success: bool,
        observation: str,
        output: Any = None,
        error: str = "",
        duration_ms: float = 0.0,
        step_index: int = 0,
    ) -> "AgentEvent":
        return cls(
            type=EventType.TOOL_CALL_END,
            payload={
                "tool": tool,
                "success": success,
                "observation": observation[:6_000],
                "output": output,
                "error": error,
                "duration_ms": duration_ms,
            },
            step_index=step_index,
        )

    @classmethod
    def todo_update(
        cls,
        todos: list[dict[str, Any]],
        *,
        run_id: str = "",
        step_index: int = 0,
    ) -> "AgentEvent":
        return cls(
            type=EventType.TODO_UPDATE,
            payload={"todos": list(todos)},
            run_id=run_id,
            step_index=step_index,
        )

    @classmethod
    def final_answer(
        cls,
        answer: str,
        *,
        steps: int = 0,
        total_ms: float = 0.0,
        step_index: int = 0,
    ) -> "AgentEvent":
        return cls(
            type=EventType.FINAL_ANSWER,
            payload={"answer": answer, "steps": steps, "total_ms": total_ms},
            step_index=step_index,
        )

    @classmethod
    def error(
        cls,
        reason: str,
        *,
        step_index: int = 0,
    ) -> "AgentEvent":
        return cls(
            type=EventType.ERROR,
            payload={"reason": reason},
            step_index=step_index,
        )


__all__ = ["AgentEvent", "EventType"]
