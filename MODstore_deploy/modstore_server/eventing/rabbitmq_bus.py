"""RabbitMQ-oriented :class:`~modstore_server.eventing.bus.NeuroBus` 实现占位。

完整 aio-pika 发布/订阅应在独立 worker 中运行，以避免在 FastAPI 同步路径中阻塞事件循环。
本类 **继承** :class:`~modstore_server.eventing.bus.InMemoryNeuroBus`，保证与现有单测及
in-process subscribers 行为一致；当 ``MODSTORE_RABBITMQ_URL`` 配置可用时，可在此处扩展
``publish`` 将消息投递到 broker。
"""

from __future__ import annotations

import logging
import os

from modstore_server.eventing.bus import InMemoryNeuroBus
from modstore_server.eventing.events import DomainEvent

logger = logging.getLogger(__name__)


class RabbitMqNeuroBus(InMemoryNeuroBus):
    """内存 handlers + 可选 AMQP（当前默认仅打日志，避免引入异步复杂度）。"""

    def __init__(self) -> None:
        super().__init__()
        self._amqp_url = (os.environ.get("MODSTORE_RABBITMQ_URL") or "").strip()

    def publish(self, event: DomainEvent) -> None:
        super().publish(event)
        if self._amqp_url:
            logger.debug(
                "rabbitmq fan-out placeholder for event=%s (configure worker to consume)",
                event.event_name,
            )


__all__ = ["RabbitMqNeuroBus"]
