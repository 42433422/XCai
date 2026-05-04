"""RateLimiterMiddleware 挂载与豁免路径行为。"""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytest.importorskip("starlette")


def test_rate_limiter_exempt_paths_skip_limit(monkeypatch):
    """豁免路径（如 ``/metrics``）在极低 limit 下仍可重复命中。"""
    monkeypatch.setenv("MODSTORE_RATE_LIMIT", "1")
    monkeypatch.setenv("MODSTORE_RATE_WINDOW", "60")
    monkeypatch.delenv("MODSTORE_REDIS_URL", raising=False)

    from modstore_server.api.rate_limiter import RateLimiterMiddleware

    app = FastAPI()

    @app.get("/metrics")
    def metrics():
        return "ok"

    app.add_middleware(RateLimiterMiddleware)
    c = TestClient(app)
    for _ in range(10):
        assert c.get("/metrics").status_code == 200


def test_rate_limiter_returns_429_when_exceeded(monkeypatch):
    monkeypatch.setenv("MODSTORE_RATE_LIMIT", "2")
    monkeypatch.setenv("MODSTORE_RATE_WINDOW", "60")
    monkeypatch.delenv("MODSTORE_REDIS_URL", raising=False)

    from modstore_server.api.rate_limiter import RateLimiterMiddleware

    app = FastAPI()

    @app.get("/hit")
    def hit():
        return {"n": 1}

    app.add_middleware(RateLimiterMiddleware)
    c = TestClient(app)
    assert c.get("/hit").status_code == 200
    assert c.get("/hit").status_code == 200
    r = c.get("/hit")
    assert r.status_code == 429
    assert r.json().get("detail") == "Too many requests"
    assert "Retry-After" in r.headers
