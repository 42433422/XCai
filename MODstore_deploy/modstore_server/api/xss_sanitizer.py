from __future__ import annotations

import json
import re
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import Response


_SCRIPT_RE = re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL)


def _sanitize_value(value):
    if isinstance(value, str):
        # 仅剥离 ``<script>`` 片段；勿对 JSON 字符串做 ``html.escape``，否则会破坏 OpenAPI/YAML 等合法载荷。
        return _SCRIPT_RE.sub("", value)
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    return value


class XSSSanitizerMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive, send)
        content_type = request.headers.get("content-type", "")

        if "application/json" not in content_type:
            await self.app(scope, receive, send)
            return

        if request.method.upper() not in ("POST", "PUT", "PATCH", "DELETE"):
            await self.app(scope, receive, send)
            return

        body = await request.body()
        if not body:
            await self.app(scope, receive, send)
            return

        try:
            parsed = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            await self.app(scope, receive, send)
            return

        sanitized = _sanitize_value(parsed)

        new_body = json.dumps(sanitized, ensure_ascii=False).encode("utf-8")

        async def receive_sanitized():
            return {"type": "http.request", "body": new_body}

        await self.app(scope, receive_sanitized, send)
