"""Background run manager for AgentLoop.

Provides ``run_async`` (start + get run_id), ``get_status``, ``cancel``,
and ``resume`` for long-running agent loops that shouldn't block the caller.

Persistence
-----------
Run state is written to ``store_dir/agent/runs/<run_id>.json`` so the loop
can survive process restarts (resume starts fresh but with preserved todo
state and archived context summary).

Thread model
------------
Each background run gets its own ``asyncio.Task`` in a dedicated background
event-loop thread.  The main thread (or FastAPI handler) polls via
``get_status`` which reads the persisted state file.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class RunState:
    """Persisted state for a background run."""

    run_id: str
    goal: str
    status: str = "pending"        # pending | running | done | error | cancelled
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    final_answer: str = ""
    error: str = ""
    steps: int = 0
    todos: list[dict[str, Any]] = field(default_factory=list)
    events_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BackgroundRunManager:
    """Manages background AgentLoop runs."""

    def __init__(self, store_dir: Path | None = None) -> None:
        self._store_dir = store_dir
        self._runs: dict[str, RunState] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- public

    def start(
        self,
        loop_factory: Callable[[], Any],
        goal: str,
        *,
        run_id: str | None = None,
        on_event: Callable[[Any], None] | None = None,
    ) -> str:
        """Start a background run and return its run_id."""
        run_id = run_id or uuid.uuid4().hex[:12]
        state = RunState(run_id=run_id, goal=goal, status="pending")
        cancel_ev = threading.Event()
        with self._lock:
            self._runs[run_id] = state
            self._cancel_events[run_id] = cancel_ev
        self._persist(state)

        def _thread() -> None:
            state.status = "running"
            state.updated_at = time.time()
            self._persist(state)
            try:
                agent_loop = loop_factory()
                result = agent_loop.run(
                    goal,
                    run_id=run_id,
                    on_event=on_event,
                )
                if cancel_ev.is_set():
                    state.status = "cancelled"
                elif result.success:
                    state.status = "done"
                    state.final_answer = result.final_answer
                    state.steps = result.steps
                    state.todos = result.todos
                else:
                    state.status = "error"
                    state.error = result.error
                    state.todos = result.todos
            except Exception as exc:  # noqa: BLE001
                state.status = "error"
                state.error = str(exc)
            state.updated_at = time.time()
            self._persist(state)

        t = threading.Thread(target=_thread, daemon=True, name=f"vibe-run-{run_id}")
        t.start()
        return run_id

    def get_status(self, run_id: str) -> RunState | None:
        with self._lock:
            state = self._runs.get(run_id)
        if state is None:
            state = self._load(run_id)
        return state

    def cancel(self, run_id: str) -> bool:
        ev = self._cancel_events.get(run_id)
        if ev is None:
            return False
        ev.set()
        state = self.get_status(run_id)
        if state:
            state.status = "cancelled"
            state.updated_at = time.time()
            self._persist(state)
        return True

    def list_runs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            states = list(self._runs.values())
        states.sort(key=lambda s: s.created_at, reverse=True)
        return [s.to_dict() for s in states[:limit]]

    # ---------------------------------------------------------------- persist

    def _persist(self, state: RunState) -> None:
        if not self._store_dir:
            return
        try:
            runs_dir = self._store_dir / "agent" / "runs"
            runs_dir.mkdir(parents=True, exist_ok=True)
            path = runs_dir / f"{state.run_id}.json"
            path.write_text(
                json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _load(self, run_id: str) -> RunState | None:
        if not self._store_dir:
            return None
        path = self._store_dir / "agent" / "runs" / f"{run_id}.json"
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            state = RunState(
                run_id=str(data.get("run_id") or run_id),
                goal=str(data.get("goal") or ""),
                status=str(data.get("status") or "unknown"),
                created_at=float(data.get("created_at") or 0),
                updated_at=float(data.get("updated_at") or 0),
                final_answer=str(data.get("final_answer") or ""),
                error=str(data.get("error") or ""),
                steps=int(data.get("steps") or 0),
                todos=list(data.get("todos") or []),
                events_count=int(data.get("events_count") or 0),
            )
            with self._lock:
                self._runs[run_id] = state
            return state
        except (OSError, ValueError):
            return None


# Module-level singleton (lazy-init)
_default_manager: BackgroundRunManager | None = None


def get_default_manager(store_dir: Path | None = None) -> BackgroundRunManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = BackgroundRunManager(store_dir=store_dir)
    return _default_manager


__all__ = ["BackgroundRunManager", "RunState", "get_default_manager"]
