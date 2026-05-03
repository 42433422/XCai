"""Process-local NeuroBus instance (memory | rabbitmq) + optional shadow dual-write."""

from __future__ import annotations

import logging
import os

from modstore_server.eventing.bus import InMemoryNeuroBus, NeuroBus
from modstore_server.eventing.events import DomainEvent

from .outbox import FileEventOutbox

logger = logging.getLogger(__name__)


def _build_primary_bus() -> NeuroBus:
    raw = (os.environ.get("MODSTORE_BUS") or "memory").strip().lower()
    if raw in ("rabbitmq", "rmq", "amqp"):
        try:
            from modstore_server.eventing.rabbitmq_bus import RabbitMqNeuroBus

            return RabbitMqNeuroBus()
        except Exception:  # noqa: BLE001
            logger.exception("MODSTORE_BUS=%s but rabbitmq bus init failed; using memory", raw)
    return InMemoryNeuroBus()


class _ShadowNeuroBus(NeuroBus):
    """Writes to primary then best-effort secondary (for greyscale cutover)."""

    def __init__(self, primary: NeuroBus, secondary: NeuroBus) -> None:
        self._primary = primary
        self._secondary = secondary

    def subscribe(self, event_name: str, handler) -> None:
        self._primary.subscribe(event_name, handler)
        try:
            self._secondary.subscribe(event_name, handler)
        except Exception:  # noqa: BLE001
            logger.debug("shadow subscribe failed on secondary", exc_info=True)

    def publish(self, event: DomainEvent) -> None:
        self._primary.publish(event)
        try:
            self._secondary.publish(event)
        except Exception:  # noqa: BLE001
            logger.warning("shadow publish failed on secondary bus", exc_info=True)


def _build_bus() -> NeuroBus:
    primary = _build_primary_bus()
    shadow = (os.environ.get("MODSTORE_BUS_SHADOW") or "").strip().lower()
    if not shadow or shadow in ("0", "false", "no", "off"):
        return primary
    try:
        from modstore_server.eventing.rabbitmq_bus import RabbitMqNeuroBus

        secondary = RabbitMqNeuroBus()
    except Exception:  # noqa: BLE001
        secondary = InMemoryNeuroBus()
    return _ShadowNeuroBus(primary, secondary)


neuro_bus: NeuroBus = _build_bus()
event_outbox = FileEventOutbox()
neuro_bus.subscribe("*", event_outbox.append)
