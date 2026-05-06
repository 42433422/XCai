"""ToolBus — parallel-safe tool dispatcher for AgentLoop.

Key improvements over the bare ``ToolRegistry.call``:

1. **read_only tags** — every registered tool is tagged ``read_only=True/False``.
   Multiple read-only calls in the same LLM turn are dispatched with
   ``asyncio.gather`` (or ``concurrent.futures.ThreadPoolExecutor`` for sync
   tool funcs), then results are collated in order.

2. **Write barrier** — if any tool in a batch is write-capable, the whole
   batch is executed sequentially (write tools are never parallelised).

3. **Mode filtering** — in ``plan`` mode the bus silently converts write-tool
   invocations into errors so the loop stays read-only without changing
   individual tool implementations.

4. **Transparent wrapping** — tools already in a ``ToolRegistry`` can be
   promoted to the bus in one call; ``register_from_registry`` copies every
   tool and infers ``read_only`` from a set of known read-only tool names.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ..react.tools import Tool, ToolRegistry, ToolResult


# ---------------------------------------------------------------- well-known read-only names

_READ_ONLY_NAMES: frozenset[str] = frozenset({
    # filesystem reads
    "read_file", "read_file_v2", "list_dir", "stat_path",
    # search
    "grep", "find_files", "glob_files", "ripgrep_search",
    # git (read)
    "git_status", "git_diff", "git_log",
    # project index
    "index_project", "find_symbol",
    # web fetch (read)
    "http_fetch",
    # introspection
    "todo_list",
})


# ---------------------------------------------------------------- bus entry

@dataclass
class BusEntry:
    tool: Tool
    read_only: bool = False


# ---------------------------------------------------------------- ToolBus

_WRITE_TOOL_NAMES: frozenset[str] = frozenset({
    "write_file", "apply_edit", "apply_project_patch",
})


class ToolBus:
    """Wraps ``ToolRegistry`` with parallel execution + plan-mode safety."""

    def __init__(
        self,
        *,
        mode: str = "agent",          # "agent" | "plan"
        executor: concurrent.futures.Executor | None = None,
        post_edit_hook: Callable[[list[str], Any], dict[str, Any] | None] | None = None,
        project_root: Any | None = None,
    ) -> None:
        self._entries: dict[str, BusEntry] = {}
        self.mode = mode
        self._executor = executor or concurrent.futures.ThreadPoolExecutor(
            max_workers=8, thread_name_prefix="vibe-toolbus"
        )
        # Called after each write tool: (paths_changed, root) → lint_result_dict | None
        self._post_edit_hook = post_edit_hook
        self.project_root = project_root

    # ---------------------------------------------------------------- registration

    def register(self, tool: Tool, *, read_only: bool | None = None) -> None:
        if read_only is None:
            read_only = tool.name in _READ_ONLY_NAMES
        entry = BusEntry(tool=tool, read_only=read_only)
        self._entries[tool.name] = entry
        for alias in tool.aliases:
            if alias and alias not in self._entries:
                self._entries[alias] = entry

    def register_from_registry(self, registry: ToolRegistry) -> None:
        seen: set[int] = set()
        for t in registry:
            if id(t) in seen:
                continue
            seen.add(id(t))
            self.register(t)

    def names(self) -> list[str]:
        seen: set[int] = set()
        out: list[str] = []
        for entry in self._entries.values():
            if id(entry.tool) in seen:
                continue
            seen.add(id(entry.tool))
            out.append(entry.tool.name)
        return out

    def to_prompt_schema(self) -> str:
        """Render schema for JSON-mode prompting."""
        seen: set[int] = set()
        lines: list[str] = []
        for entry in self._entries.values():
            t = entry.tool
            if id(t) in seen:
                continue
            seen.add(id(t))
            lines.append(f"### `{t.name}`")
            if t.description:
                lines.append(t.description.strip())
            if t.arguments:
                arg_lines = []
                for a in t.arguments:
                    req = "**required**" if a.get("required", True) else "optional"
                    arg_lines.append(
                        f"- `{a['name']}` ({a.get('type', 'string')}, {req}): "
                        f"{a.get('description', '')}"
                    )
                lines.append("\n".join(arg_lines))
            lines.append("")
        return "\n".join(lines).rstrip()

    def to_registry(self) -> ToolRegistry:
        """Return a plain ``ToolRegistry`` from current entries (for FC schema)."""
        reg = ToolRegistry()
        seen: set[int] = set()
        for entry in self._entries.values():
            if id(entry.tool) in seen:
                continue
            seen.add(id(entry.tool))
            try:
                reg.register(entry.tool)
            except ValueError:
                pass
        return reg

    # ---------------------------------------------------------------- execution

    async def call_many(
        self,
        calls: list[tuple[str, dict[str, Any]]],
        *,
        step_index: int = 0,
        on_start: Callable[[str, dict[str, Any]], None] | None = None,
        on_end: Callable[[str, ToolResult, float], None] | None = None,
    ) -> list[ToolResult]:
        """Execute a batch of (tool_name, args) pairs.

        Read-only calls in the batch are executed concurrently.
        Any write call causes the entire batch to execute sequentially
        from that point on.
        """
        if not calls:
            return []

        # Plan mode: block writes
        if self.mode == "plan":
            calls = self._filter_plan_mode(calls)

        # Classify batch
        all_read_only = all(
            self._entries.get(name, BusEntry(tool=_NOOP_TOOL)).read_only
            for name, _ in calls
        )

        if all_read_only and len(calls) > 1:
            return await self._call_parallel(calls, on_start=on_start, on_end=on_end)
        return await self._call_sequential(calls, on_start=on_start, on_end=on_end)

    async def call_one(
        self,
        name: str,
        args: dict[str, Any],
        *,
        on_start: Callable[[str, dict[str, Any]], None] | None = None,
        on_end: Callable[[str, ToolResult, float], None] | None = None,
    ) -> ToolResult:
        results = await self.call_many([(name, args)], on_start=on_start, on_end=on_end)
        return results[0] if results else ToolResult(success=False, observation="no result")

    # ---------------------------------------------------------------- internals

    def _filter_plan_mode(
        self, calls: list[tuple[str, dict[str, Any]]]
    ) -> list[tuple[str, dict[str, Any]]]:
        filtered = []
        for name, args in calls:
            entry = self._entries.get(name)
            if entry is None or not entry.read_only:
                # Replace with a stub that returns a plan-mode error
                filtered.append((_PLAN_BLOCK_PREFIX + name, args))
            else:
                filtered.append((name, args))
        return filtered

    async def _call_parallel(
        self,
        calls: list[tuple[str, dict[str, Any]]],
        *,
        on_start: Callable | None,
        on_end: Callable | None,
    ) -> list[ToolResult]:
        loop = asyncio.get_event_loop()

        async def _one(name: str, args: dict[str, Any]) -> ToolResult:
            if on_start:
                on_start(name, args)
            t0 = time.perf_counter()
            entry = self._entries.get(name)
            if entry is None:
                res = ToolResult(
                    success=False,
                    observation=f"[error] tool {name!r} not registered",
                    error=f"ToolNotFoundError: {name}",
                )
            else:
                res = await loop.run_in_executor(
                    self._executor, lambda e=entry, a=args: e.tool.run(**a)
                )
            elapsed = round((time.perf_counter() - t0) * 1000, 3)
            if on_end:
                on_end(name, res, elapsed)
            return res

        tasks = [_one(name, args) for name, args in calls]
        return list(await asyncio.gather(*tasks))

    async def _call_sequential(
        self,
        calls: list[tuple[str, dict[str, Any]]],
        *,
        on_start: Callable | None,
        on_end: Callable | None,
    ) -> list[ToolResult]:
        loop = asyncio.get_event_loop()
        results: list[ToolResult] = []
        for name, args in calls:
            if name.startswith(_PLAN_BLOCK_PREFIX):
                real_name = name[len(_PLAN_BLOCK_PREFIX):]
                results.append(ToolResult(
                    success=False,
                    observation=f"[plan mode] tool '{real_name}' is a write operation and is blocked in plan mode",
                    error="plan_mode_write_blocked",
                ))
                continue
            if on_start:
                on_start(name, args)
            t0 = time.perf_counter()
            entry = self._entries.get(name)
            if entry is None:
                res = ToolResult(
                    success=False,
                    observation=f"[error] tool {name!r} not registered. Available: {', '.join(self.names())}",
                    error=f"ToolNotFoundError: {name}",
                )
            else:
                res = await loop.run_in_executor(
                    self._executor, lambda e=entry, a=args: e.tool.run(**a)
                )
            elapsed = round((time.perf_counter() - t0) * 1000, 3)
            if on_end:
                on_end(name, res, elapsed)
            results.append(res)

            # Post-edit lints for write tools
            if name in _WRITE_TOOL_NAMES and res.success and self._post_edit_hook and self.project_root:
                changed_paths = _extract_changed_paths(name, args, res)
                try:
                    lint_result = self._post_edit_hook(changed_paths, self.project_root)
                    if lint_result:
                        from .lints import format_lint_observation
                        lint_obs = format_lint_observation(lint_result)
                        # Append lint observation to the tool result so it reaches the context
                        results[-1] = ToolResult(
                            success=res.success,
                            observation=res.observation + "\n\n" + lint_obs,
                            output=res.output,
                            error=res.error,
                        )
                except Exception:  # noqa: BLE001
                    pass
        return results


# ---------------------------------------------------------------- helpers

_PLAN_BLOCK_PREFIX = "__plan_block__"


def _extract_changed_paths(tool_name: str, args: dict[str, Any], res: ToolResult) -> list[str]:
    """Best-effort extraction of changed file paths from a write-tool call."""
    if tool_name in ("write_file", "apply_edit"):
        p = args.get("path", "")
        return [p] if p else []
    if tool_name == "apply_project_patch":
        try:
            files = (res.output or {}).get("files") or []
            return list(files) if isinstance(files, list) else []
        except (AttributeError, TypeError):
            return []
    return []


@Tool.from_func if hasattr(Tool, "from_func") else lambda f: f  # type: ignore[attr-defined]
def _noop_tool_func(**_: Any) -> str:
    return "(noop)"


# Minimal no-op tool used as fallback when a name is unregistered
_NOOP_TOOL = Tool(
    name="__noop__",
    description="no-op placeholder",
    func=lambda **_: ToolResult(success=False, observation="noop"),
)


__all__ = ["BusEntry", "ToolBus", "_READ_ONLY_NAMES"]
