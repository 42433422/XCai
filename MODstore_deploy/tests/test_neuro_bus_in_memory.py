"""InMemoryNeuroBus：订阅顺序、通配符、幂等去重、单处理器异常不阻断其他处理器。"""

from __future__ import annotations

from modstore_server.eventing.bus import InMemoryNeuroBus
from modstore_server.eventing.events import new_event


def _evt(name: str, key: str = "k1", payload: dict | None = None):
    return new_event(
        name,
        producer="test",
        subject_id="sub",
        idempotency_key=key,
        payload=payload or {},
    )


def test_publish_invokes_handlers_in_subscribe_order() -> None:
    bus = InMemoryNeuroBus()
    out: list[str] = []
    bus.subscribe("order.paid", lambda _: out.append("first"))
    bus.subscribe("order.paid", lambda _: out.append("second"))
    bus.publish(_evt("order.paid", "id-1"))
    assert out == ["first", "second"]


def test_wildcard_star_subscriber() -> None:
    bus = InMemoryNeuroBus()
    stars: list[str] = []

    def star(_):
        stars.append("*")

    bus.subscribe("*", star)
    bus.publish(_evt("any.event", "id-4"))
    assert stars == ["*"]


def test_duplicate_idempotency_key_skips_handlers_second_time() -> None:
    bus = InMemoryNeuroBus()
    n = {"c": 0}

    def h(_):
        n["c"] += 1

    bus.subscribe("e", h)
    e = _evt("e", "same-key")
    bus.publish(e)
    bus.publish(e)
    assert n["c"] == 1


def test_handler_exception_does_not_stop_other_handlers() -> None:
    bus = InMemoryNeuroBus()
    out: list[str] = []

    def boom(_):
        raise RuntimeError("boom")

    def ok(_):
        out.append("ok")

    bus.subscribe("e2", boom)
    bus.subscribe("e2", ok)
    bus.publish(_evt("e2", "id-5"))
    assert out == ["ok"]
