"""File-backed event outbox for the first event-driven rollout."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .events import DomainEvent


class FileEventOutbox:
    def __init__(self, path: Path | None = None):
        raw = (os.environ.get("MODSTORE_EVENT_OUTBOX_PATH") or "").strip()
        self.path = path or (Path(raw).expanduser() if raw else Path(__file__).resolve().parents[1] / "data" / "event_outbox.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: DomainEvent) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False, default=str) + "\n")
