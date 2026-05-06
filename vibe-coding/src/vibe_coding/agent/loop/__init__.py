"""AgentLoop v2 — Claude Code-parity autonomous agent kernel.

Drop-in replacement for :class:`vibe_coding.agent.react.ReActAgent` that adds:

- Parallel read-only tool execution (``asyncio.gather`` when safe)
- Native function-calling for OpenAI / Claude / Qwen with JSON-mode fallback
- ``TodoStore`` task management with ``todo_write`` tool
- Plan mode (read-only + ``present_plan`` gate) vs agent mode
- Task sub-agents (explore / shell / general) with isolated context
- ``ContextManager`` (auto-summarise long observations, file-fingerprint dedup)
- Streaming ``AsyncIterator[AgentEvent]`` interface plus sync ``run()`` wrapper
- Background runs + cancel / resume (P2 extension)

Public surface
--------------
    from vibe_coding.agent.loop import AgentLoop, AgentEvent, ToolBus
    from vibe_coding.agent.loop.todos import TodoStore
    from vibe_coding.agent.loop.context_manager import ContextManager
"""

from __future__ import annotations

from .events import AgentEvent, EventType
from .function_calling import FunctionCallingAdapter, ToolCallRequest
from .loop import AgentLoop, AgentLoopResult, RunOptions
from .tool_bus import ToolBus

__all__ = [
    "AgentEvent",
    "AgentLoop",
    "AgentLoopResult",
    "EventType",
    "FunctionCallingAdapter",
    "RunOptions",
    "ToolBus",
    "ToolCallRequest",
]
