"""Process-local NeuroBus instance."""

from __future__ import annotations

from .bus import InMemoryNeuroBus
from .outbox import FileEventOutbox

neuro_bus = InMemoryNeuroBus()
event_outbox = FileEventOutbox()
neuro_bus.subscribe("*", event_outbox.append)
