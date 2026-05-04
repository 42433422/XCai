from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_EXEMPT_PATHS = {"/health", "/metrics", "/docs", "/openapi.json", "/redoc"}
_DEFAULT_LIMIT = 60
_DEFAULT_WINDOW = 60


class _InMemoryBucket:
    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        cutoff = now - window
        self._windows[key] = [t for t in self._windows[key] if t > cutoff]
        if len(self._windows[key]) >= limit:
            return False
        self._windows[key].append(now)
        return True

    def retry_after(self, key: str, window: int) -> int:
        now = time.time()
        entries = self._windows.get(key, [])
        if not entries:
            return 1
        oldest = min(entries)
        return max(1, int(oldest + window - now))


class _RedisBucket:
    def __init__(self, redis_url: str):
        import redis

        self._client = redis.from_url(redis_url, decode_responses=True)

    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        pipe = self._client.pipeline()
        member = f"{key}:{now}"
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.expire(key, window)
        results = pipe.execute()
        count = int(results[2])
        return count <= limit

    def retry_after(self, key: str, window: int) -> int:
        now = time.time()
        entries = self._client.zrange(key, 0, 0, withscores=True)
        if not entries:
            return 1
        oldest = entries[0][1]
        return max(1, int(oldest + window - now))


class RateLimiterMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._limit = int(os.environ.get("MODSTORE_RATE_LIMIT", str(_DEFAULT_LIMIT)))
        self._window = int(os.environ.get("MODSTORE_RATE_WINDOW", str(_DEFAULT_WINDOW)))
        self._bucket = self._init_bucket()

    def _init_bucket(self):
        redis_url = os.environ.get("MODSTORE_REDIS_URL", "").strip()
        if redis_url:
            try:
                bucket = _RedisBucket(redis_url)
                bucket._client.ping()
                return bucket
            except Exception:
                logger.warning("Redis unavailable, falling back to in-memory rate limiter")
        return _InMemoryBucket()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive, send)
        path = request.url.path

        for exempt in _EXEMPT_PATHS:
            if path == exempt or path.startswith(exempt + "/"):
                await self.app(scope, receive, send)
                return

        client_ip = request.client.host if request.client else "unknown"
        user_hint = (request.headers.get("x-modstore-user") or request.headers.get("x-user-id") or "")[:64]
        route = f"{request.method}:{path}"[:220]
        key = f"rate:{client_ip}:{user_hint}:{route}"

        if not self._bucket.is_allowed(key, self._limit, self._window):
            retry_after = self._bucket.retry_after(key, self._window)
            response = JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
