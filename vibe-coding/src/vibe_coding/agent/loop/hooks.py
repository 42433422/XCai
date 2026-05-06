"""Hook system for AgentLoop.

Hooks are Python callables registered for specific event points in the loop.
They run synchronously (or as coroutines via ``asyncio.run_until_complete``).

Hook points
-----------
``pre_tool_call``    — called before each tool execution
``post_tool_call``   — called after each tool execution with result
``pre_apply_patch``  — called before any patch/edit write (subset of post_tool)
``post_run_done``    — called when the loop reaches final_answer or error

Built-in production hook
------------------------
``ruff_prettier_hook`` — runs ``ruff --fix`` + ``prettier --write`` on changed
Python/JS/TS/Vue files after every successful write-tool call.

Configuration
-------------
Read from ``vibe_coding.hooks.json`` in the store_dir root (optional):

    {
        "hooks": [
            {"event": "post_tool_call", "builtin": "ruff_prettier"}
        ]
    }
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


# ---------------------------------------------------------------- types

HookFn = Callable[..., None]


@dataclass
class HookRegistration:
    event: str
    fn: HookFn
    name: str = ""


class HookRegistry:
    """Collect and fire hooks by event name."""

    def __init__(self) -> None:
        self._hooks: list[HookRegistration] = []

    def register(self, event: str, fn: HookFn, *, name: str = "") -> None:
        self._hooks.append(HookRegistration(event=event, fn=fn, name=name or fn.__name__))

    def fire(self, event: str, **kwargs: Any) -> None:
        for reg in self._hooks:
            if reg.event == event:
                try:
                    reg.fn(**kwargs)
                except Exception:  # noqa: BLE001
                    pass   # hooks must never break the loop

    @classmethod
    def from_config(cls, config_path: Path) -> "HookRegistry":
        reg = cls()
        if not config_path.is_file():
            return reg
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return reg
        for hook_def in data.get("hooks") or []:
            builtin = hook_def.get("builtin", "")
            event = hook_def.get("event", "post_tool_call")
            if builtin == "ruff_prettier":
                reg.register(event, ruff_prettier_hook, name="ruff_prettier")
        return reg


# ---------------------------------------------------------------- built-ins


def ruff_prettier_hook(
    *,
    tool_name: str = "",
    args: dict[str, Any] | None = None,
    result: Any = None,
    project_root: Path | None = None,
    **_: Any,
) -> None:
    """Run ruff --fix + prettier on files changed by the tool."""
    args = args or {}
    changed: list[str] = []
    if tool_name in ("write_file", "apply_edit"):
        p = args.get("path", "")
        if p:
            changed.append(p)
    elif tool_name == "apply_project_patch":
        try:
            files = (result.output or {}).get("files") or []
            changed.extend(files if isinstance(files, list) else [])
        except (AttributeError, TypeError):
            pass

    if not changed or not project_root:
        return

    py_files = [f for f in changed if f.endswith(".py")]
    js_files = [f for f in changed if any(f.endswith(ext) for ext in (".js", ".ts", ".jsx", ".tsx", ".vue"))]

    root = Path(project_root)

    if py_files and shutil.which("ruff"):
        try:
            subprocess.run(
                ["ruff", "check", "--fix", "--quiet"] + py_files,
                cwd=str(root),
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass

    if js_files and shutil.which("prettier"):
        try:
            subprocess.run(
                ["prettier", "--write"] + js_files,
                cwd=str(root),
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass


__all__ = ["HookRegistry", "HookRegistration", "ruff_prettier_hook"]
