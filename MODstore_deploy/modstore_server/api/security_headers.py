from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.responses import Response


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"x-frame-options", b"DENY"))
                headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                headers.append(
                    (
                        b"content-security-policy",
                        b"default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                        b"style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; "
                        b"font-src 'self' data:; connect-src 'self' ws: wss: https:",
                    )
                )
                scheme = scope.get("scheme", "http")
                if scheme == "https":
                    headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
