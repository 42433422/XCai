"""WebSocket 长连接：站内通知、后续可扩展其它推送。

路径 ``/api/realtime/ws`` 不落在 ``PROXY_PREFIXES``，始终由本 FastAPI 进程处理。
鉴权：查询参数 ``token``（与 HTTP Bearer 相同的 JWT access）。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from modstore_server.auth_service import decode_access_token, get_user_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


class _ConnectionManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sockets: dict[int, set[WebSocket]] = defaultdict(set)

    async def register(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._sockets[user_id].add(ws)

    async def unregister(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._sockets.get(user_id)
            if not conns:
                return
            conns.discard(ws)
            if not conns:
                del self._sockets[user_id]

    async def send_json_to_user(self, user_id: int, payload: dict[str, Any]) -> int:
        """推送给该用户所有已连接；返回成功送达的套接字数。"""
        data = json.dumps(payload, ensure_ascii=False)
        async with self._lock:
            conns = list(self._sockets.get(user_id, ()))
        n = 0
        for ws in conns:
            try:
                await ws.send_text(data)
                n += 1
            except Exception as e:
                logger.debug("WebSocket 发送失败 user_id=%s: %s", user_id, e)
        return n


_manager = _ConnectionManager()


def schedule_push_to_user(user_id: int, payload: dict[str, Any]) -> None:
    """在同步上下文中安全调度推送（如创建通知时）；无运行中的事件循环则忽略。"""
    if not user_id:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _go() -> None:
        try:
            await _manager.send_json_to_user(int(user_id), payload)
        except Exception as e:
            logger.debug("realtime 推送任务失败: %s", e)

    loop.create_task(_go())


@router.websocket("/ws")
async def websocket_channel(
    websocket: WebSocket,
    token: str = Query(""),
) -> None:
    await websocket.accept()
    raw = (token or "").strip()
    if not raw:
        await websocket.close(code=1008)
        return
    pl = decode_access_token(raw)
    if not pl:
        await websocket.close(code=1008)
        return
    try:
        user_id = int(pl.get("sub") or 0)
    except (TypeError, ValueError):
        user_id = 0
    if not user_id or not get_user_by_id(user_id):
        await websocket.close(code=1008)
        return

    await _manager.register(user_id, websocket)
    try:
        await websocket.send_text(
            json.dumps({"type": "ready", "user_id": user_id}, ensure_ascii=False)
        )
    except Exception:
        await _manager.unregister(user_id, websocket)
        return

    try:
        while True:
            try:
                msg = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            try:
                body = json.loads(msg)
            except json.JSONDecodeError:
                continue
            if body.get("type") == "ping":
                t = body.get("t")
                await websocket.send_json({"type": "pong", "t": t})
    finally:
        await _manager.unregister(user_id, websocket)
