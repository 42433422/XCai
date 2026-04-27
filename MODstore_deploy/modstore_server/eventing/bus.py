"""NeuroBus interface and in-memory implementation."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable

from .events import DomainEvent

logger = logging.getLogger(__name__)

EventHandler = Callable[[DomainEvent], None]


class NeuroBus:
    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        raise NotImplementedError

    def publish(self, event: DomainEvent) -> None:
        raise NotImplementedError


class InMemoryNeuroBus(NeuroBus):
    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._seen: set[str] = set()

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)

    def publish(self, event: DomainEvent) -> None:
        if event.idempotency_key in self._seen:
            logger.debug("skip duplicate event: %s", event.idempotency_key)
            return
        self._seen.add(event.idempotency_key)
        for handler in [*self._handlers.get(event.event_name, []), *self._handlers.get("*", [])]:
            try:
                handler(event)
            except Exception:
                logger.exception("event handler failed: %s", event.event_name)
