"""TodoStore — Claude Code-style task management for AgentLoop.

The store holds an ordered list of todos for the current run.  The LLM
controls the list through the ``todo_write`` built-in tool; the store
fires ``AgentEvent.todo_update`` events whenever state changes so frontends
can display live progress.

Todo schema
-----------
Every todo is a plain dict:
    {
        "id":      str,   # unique within the run
        "content": str,   # one-sentence description
        "status":  str,   # "pending" | "in_progress" | "completed" | "cancelled"
    }

System-prompt rule injected by AgentLoop
-----------------------------------------
    For tasks with 3+ distinct steps, call todo_write FIRST to create your
    plan, then mark each item in_progress as you start it and completed when
    done.  Never have more than one in_progress at a time.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from ..react.tools import Tool, ToolResult, tool


VALID_STATUSES = frozenset({"pending", "in_progress", "completed", "cancelled"})

_SYSTEM_RULE = """\
## Task management

When the task has 3 or more distinct steps, use `todo_write` to record your
plan BEFORE taking any action.  Rules:
1. Only one todo may have status "in_progress" at a time.
2. Mark an item "completed" before starting the next one.
3. Use "cancelled" for items you decide to skip.
4. Calling `todo_write` with a full list REPLACES the current list — pass all
   existing items you want to keep.
"""


class TodoStore:
    """In-memory todo list with optional JSON persistence."""

    def __init__(
        self,
        run_id: str = "",
        *,
        persist_dir: Path | None = None,
        on_change: Callable[["TodoStore"], None] | None = None,
    ) -> None:
        self.run_id = run_id
        self._todos: list[dict[str, Any]] = []
        self._persist_dir = persist_dir
        self._on_change = on_change

    # ---------------------------------------------------------------- public

    @property
    def todos(self) -> list[dict[str, Any]]:
        return list(self._todos)

    def write(self, todos: list[dict[str, Any]]) -> None:
        """Replace the todo list.  Called by the ``todo_write`` tool."""
        validated: list[dict[str, Any]] = []
        for item in todos:
            if not isinstance(item, dict):
                continue
            tid = str(item.get("id") or "").strip()
            content = str(item.get("content") or "").strip()
            status = str(item.get("status") or "pending")
            if status not in VALID_STATUSES:
                status = "pending"
            if not tid or not content:
                continue
            validated.append({"id": tid, "content": content, "status": status})
        self._todos = validated
        self._persist()
        if self._on_change:
            self._on_change(self)

    def summary(self) -> str:
        """Human-readable one-liner for system prompt injection."""
        if not self._todos:
            return ""
        done = sum(1 for t in self._todos if t["status"] == "completed")
        total = len(self._todos)
        active = next(
            (t["content"][:60] for t in self._todos if t["status"] == "in_progress"),
            None,
        )
        parts = [f"Todos: {done}/{total} completed"]
        if active:
            parts.append(f"Currently: {active}")
        return " | ".join(parts)

    def make_tool(self) -> Tool:
        """Return the ``todo_write`` tool bound to this store."""
        store = self

        @tool(
            "todo_write",
            description=(
                "Create or update the task todo list for this run. "
                "Pass the FULL list of todos (merges by id). "
                "Status must be one of: pending, in_progress, completed, cancelled."
            ),
        )
        def todo_write(todos: list) -> ToolResult:
            if not isinstance(todos, list):
                return ToolResult(
                    success=False,
                    observation="todo_write: 'todos' must be a list",
                    error="invalid type",
                )
            store.write(todos)
            summary = store.summary()
            return ToolResult(
                success=True,
                observation=f"todos updated: {summary}",
                output={"todos": store.todos},
            )

        return todo_write

    def make_list_tool(self) -> Tool:
        """Return the read-only ``todo_list`` tool."""
        store = self

        @tool("todo_list", description="Return the current todo list.")
        def todo_list() -> list:
            return list(store.todos)

        return todo_list

    # ---------------------------------------------------------------- persist

    def _persist(self) -> None:
        if not self._persist_dir or not self.run_id:
            return
        try:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            path = self._persist_dir / f"{self.run_id}.json"
            payload = {
                "run_id": self.run_id,
                "ts": time.time(),
                "todos": self._todos,
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    @classmethod
    def load(cls, run_id: str, persist_dir: Path) -> "TodoStore":
        store = cls(run_id, persist_dir=persist_dir)
        path = persist_dir / f"{run_id}.json"
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                todos = payload.get("todos") or []
                if isinstance(todos, list):
                    store._todos = todos
            except (OSError, ValueError):
                pass
        return store


SYSTEM_RULE = _SYSTEM_RULE

__all__ = ["TodoStore", "SYSTEM_RULE", "VALID_STATUSES"]
