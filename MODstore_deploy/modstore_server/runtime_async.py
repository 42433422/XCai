"""Run asyncio coroutines from sync contexts (thread-pool fallback when loop is running)."""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, TypeVar

T = TypeVar("T")


def run_coro_sync(coro: Any) -> Any:
    """Execute ``coro`` synchronously; safe when called from worker threads."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    result: Dict[str, Any] = {}
    error: Dict[str, Exception] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except Exception as e:  # noqa: PERF203
            error["err"] = e

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join()
    if "err" in error:
        raise error["err"]
    return result.get("value")


__all__ = ["run_coro_sync"]
