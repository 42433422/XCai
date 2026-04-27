"""Auth application service."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from modstore_server.auth_service import (
    PAT_PREFIX,
    decode_access_token,
    get_user_by_id,
    resolve_user_from_pat,
)
from modstore_server.models import User


class AuthApplicationService:
    """Application boundary for token based user lookup.

    支持两种凭证：
    - JWT access token：``Authorization: Bearer eyJ...``（用于 web 端会话）
    - Personal Access Token：``Authorization: Bearer pat_xxx``（用于第三方 / SDK）

    任意一种通过即视为该用户身份；两套体系各自维护过期/吊销。
    """

    def current_user_from_authorization(self, authorization: Optional[str]) -> User:
        raw = (authorization or "").strip()
        if not raw.startswith("Bearer "):
            raise HTTPException(401, "缺少认证凭证")
        token = raw[7:].strip()

        if token.startswith(PAT_PREFIX):
            user = resolve_user_from_pat(token)
            if not user:
                raise HTTPException(401, "API Token 无效、已吊销或已过期")
            return user

        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(401, "凭证无效或已过期")
        try:
            user_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(401, "凭证无效或已过期") from exc
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(401, "用户不存在")
        return user
