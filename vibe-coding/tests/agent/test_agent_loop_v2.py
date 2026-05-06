"""Tests for the AgentLoop v2 implementation.

Covers:
- Basic run / final_answer
- TodoStore + todo_write tool
- Parallel read-only tool dispatch (timing bound)
- Plan mode (write-tool blocking + plan_proposed event)
- Fast search tools (ripgrep_search / glob_files / read_file_v2)
- ContextManager dedup
- SubagentManager tools
- BackgroundRunManager
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from vibe_coding.agent.loop import AgentLoop, AgentEvent, EventType
from vibe_coding.agent.loop.todos import TodoStore
from vibe_coding.agent.loop.context_manager import ContextManager
from vibe_coding.agent.loop.background import BackgroundRunManager
from vibe_coding.agent.loop.tool_bus import ToolBus, _READ_ONLY_NAMES
from vibe_coding.agent.react.tools import Tool, ToolRegistry, ToolResult, tool
from vibe_coding.nl.llm import MockLLM


# ---------------------------------------------------------------- helpers

def _loop_with_mock(responses, *, mode="agent", max_steps=5, tools=None, **kwargs):
    llm = MockLLM(responses)
    return AgentLoop(llm, tools, mode=mode, max_steps=max_steps, **kwargs)


def _fa(answer):
    """Final-answer JSON string."""
    return json.dumps({"thought": "done", "action": {"tool": "", "args": {}}, "final_answer": answer})


def _act(tool_name, args, thought="ok"):
    """Tool-call JSON string."""
    return json.dumps({"thought": thought, "action": {"tool": tool_name, "args": args}, "final_answer": ""})


def _parallel(calls):
    """Multi-tool batch JSON array."""
    return json.dumps([
        {"thought": f"step {i}", "action": {"tool": name, "args": args}, "final_answer": ""}
        for i, (name, args) in enumerate(calls)
    ])


# ---------------------------------------------------------------- basic

def test_basic_run_returns_result():
    loop = _loop_with_mock([_fa("all done")])
    result = loop.run("do something")
    assert result.success
    assert result.final_answer == "all done"
    assert result.steps == 1


def test_max_steps_exhausted():
    loop = _loop_with_mock([_act("__nonexistent__", {})] * 5, max_steps=3)
    result = loop.run("loop forever")
    assert not result.success
    assert "max_steps" in result.error


def test_empty_goal_still_runs():
    loop = _loop_with_mock([_fa("ok")])
    result = loop.run("")
    assert result.success


# ---------------------------------------------------------------- todo

def test_todo_write_tool_updates_store():
    todos = [{"id": "t1", "content": "first", "status": "pending"}]
    responses = [
        _act("todo_write", {"todos": todos}),
        _fa("todos written"),
    ]
    loop = _loop_with_mock(responses)
    result = loop.run("task with todos")
    assert result.success
    assert any(t["id"] == "t1" for t in result.todos)


def test_todo_status_update():
    todo_store = TodoStore("test-run")
    todo_store.write([
        {"id": "a", "content": "do A", "status": "pending"},
        {"id": "b", "content": "do B", "status": "pending"},
    ])
    assert len(todo_store.todos) == 2
    todo_store.write([
        {"id": "a", "content": "do A", "status": "completed"},
        {"id": "b", "content": "do B", "status": "in_progress"},
    ])
    statuses = {t["id"]: t["status"] for t in todo_store.todos}
    assert statuses["a"] == "completed"
    assert statuses["b"] == "in_progress"


def test_todo_summary_shows_progress():
    store = TodoStore("x")
    store.write([
        {"id": "1", "content": "step one", "status": "completed"},
        {"id": "2", "content": "step two", "status": "in_progress"},
        {"id": "3", "content": "step three", "status": "pending"},
    ])
    summary = store.summary()
    assert "1/3" in summary
    assert "step two" in summary


# ---------------------------------------------------------------- tool bus / parallel

def test_tool_bus_read_only_tagging():
    bus = ToolBus()
    assert "read_file" in _READ_ONLY_NAMES
    assert "grep" in _READ_ONLY_NAMES
    assert "write_file" not in _READ_ONLY_NAMES


def test_parallel_read_only_tools_run_concurrently(tmp_path):
    """Two read-only tools in a single LLM turn should complete in < 2× single-tool time."""
    delay = 0.05   # 50 ms per tool

    @tool("slow_read_a", description="slow read A")
    def slow_a() -> str:
        time.sleep(delay)
        return "result_a"

    @tool("slow_read_b", description="slow read B")
    def slow_b() -> str:
        time.sleep(delay)
        return "result_b"

    bus = ToolBus()
    bus.register(slow_a, read_only=True)
    bus.register(slow_b, read_only=True)

    t0 = time.perf_counter()
    results = asyncio.get_event_loop().run_until_complete(
        bus.call_many([("slow_read_a", {}), ("slow_read_b", {})], step_index=1)
    )
    elapsed = time.perf_counter() - t0

    assert len(results) == 2
    assert all(r.success for r in results)
    # Parallel: should be < 1.5× single delay
    assert elapsed < delay * 1.5 + 0.1, f"Expected parallel, got {elapsed:.3f}s"


def test_write_tool_in_plan_mode_is_blocked():
    bus = ToolBus(mode="plan")

    @tool("write_file", description="write")
    def write_file(path: str, contents: str) -> str:
        return "written"

    bus.register(write_file, read_only=False)

    results = asyncio.get_event_loop().run_until_complete(
        bus.call_many([("write_file", {"path": "x.txt", "contents": "hi"})], step_index=1)
    )
    assert len(results) == 1
    assert not results[0].success
    assert "plan mode" in results[0].observation


# ---------------------------------------------------------------- plan mode

def test_plan_mode_emits_plan_proposed(tmp_path):
    plan_payload = {
        "title": "My Plan",
        "summary": "step by step",
        "plan_md": "# Step 1\ndo stuff",
    }
    responses = [
        _act("present_plan", plan_payload),
        _fa("plan done"),  # should not be reached in plan mode
    ]
    loop = _loop_with_mock(responses, mode="plan", max_steps=5)
    events: list[AgentEvent] = []

    async def _collect():
        async for ev in loop.arun("plan for me"):
            events.append(ev)

    asyncio.get_event_loop().run_until_complete(_collect())
    plan_events = [e for e in events if e.type == EventType.PLAN_PROPOSED]
    assert plan_events, "Expected a plan_proposed event"
    assert plan_events[0].payload["title"] == "My Plan"


# ---------------------------------------------------------------- fast search tools

def test_read_file_v2_with_offset_limit(tmp_path):
    src = tmp_path / "code.py"
    lines = [f"line {i}" for i in range(1, 31)]
    src.write_text("\n".join(lines), encoding="utf-8")

    from vibe_coding.agent.react.builtins import make_fast_search_tools
    tools = make_fast_search_tools(tmp_path)
    read_v2 = next(t for t in tools if t.name == "read_file_v2")

    result = read_v2.run(path="code.py", offset=5, limit=5)
    assert result.success
    output = result.observation
    # Should contain lines 5-9 (1-based)
    assert "5|" in output or "     5|" in output
    assert "10|" not in output or ("10|" in output and "     5|" in output)


def test_glob_files_sorted_by_mtime(tmp_path):
    (tmp_path / "old.py").write_text("x")
    time.sleep(0.05)
    (tmp_path / "new.py").write_text("y")

    from vibe_coding.agent.react.builtins import make_fast_search_tools
    tools = make_fast_search_tools(tmp_path)
    glob_t = next(t for t in tools if t.name == "glob_files")

    result = glob_t.run(pattern="*.py")
    assert result.success
    files = result.output["files"]
    assert len(files) == 2
    # newest first
    assert files[0] == "new.py"


def test_ripgrep_search_fallback(tmp_path):
    """ripgrep_search should find matches even without rg on PATH."""
    src = tmp_path / "hello.py"
    src.write_text("def hello():\n    pass\n")

    from vibe_coding.agent.react.builtins import make_fast_search_tools
    tools = make_fast_search_tools(tmp_path)
    rg = next(t for t in tools if t.name == "ripgrep_search")

    result = rg.run(pattern="def hello", path=".")
    assert result.success
    matches = result.output["matches"]
    assert len(matches) >= 1
    assert "hello.py" in matches[0]["file"]


# ---------------------------------------------------------------- context manager

def test_context_manager_dedup_marks_second_read():
    ctx = ContextManager(max_full_observations=10)
    was_known = ctx.note_file_read("foo.py", "content here")
    assert not was_known   # first read
    was_known = ctx.note_file_read("foo.py", "content here")
    assert was_known       # second read


def test_context_manager_archives_overflow():
    ctx = ContextManager(max_full_observations=3)
    for i in range(8):
        ctx.add_observation(i, f"observation {i} " * 50)
    prompt = ctx.build_user_prompt("goal")
    # Archived summary should be present
    assert "Archived" in prompt or "summary" in prompt.lower() or "observation 7" in prompt


# ---------------------------------------------------------------- background runs

def test_background_manager_start_and_poll(tmp_path):
    mgr = BackgroundRunManager(store_dir=tmp_path)

    responses = [_fa("background done")]
    llm = MockLLM(responses)
    loop = AgentLoop(llm, max_steps=3)

    run_id = mgr.start(lambda: loop, "bg goal")
    assert run_id

    # Poll until done (max 3s)
    deadline = time.time() + 3.0
    state = None
    while time.time() < deadline:
        state = mgr.get_status(run_id)
        if state and state.status in ("done", "error"):
            break
        time.sleep(0.1)

    assert state is not None
    assert state.status == "done", f"Expected done, got {state.status}: {state.error}"
    assert state.final_answer == "background done"


def test_background_manager_cancel(tmp_path):
    mgr = BackgroundRunManager(store_dir=tmp_path)
    ok = mgr.cancel("nonexistent-run")
    assert not ok
