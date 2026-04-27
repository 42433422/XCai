"""配额检查与消耗工具。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException

from modstore_server.eventing import new_event
from modstore_server.eventing.global_bus import neuro_bus
from modstore_server.models import Quota


def _month_reset() -> datetime:
    now = datetime.utcnow()
    return now + timedelta(days=30)


def get_quota(session, user_id: int, quota_type: str) -> Optional[Quota]:
    row = (
        session.query(Quota)
        .filter(Quota.user_id == user_id, Quota.quota_type == quota_type)
        .first()
    )
    if row and row.reset_at and row.reset_at <= datetime.utcnow():
        row.used = 0
        row.reset_at = _month_reset()
        session.add(row)
        session.commit()
    return row


def require_quota(session, user_id: int, quota_type: str, amount: int = 1) -> Quota:
    row = get_quota(session, user_id, quota_type)
    if not row:
        raise HTTPException(403, f"缺少配额: {quota_type}")
    if row.total >= 0 and row.used + amount > row.total:
        raise HTTPException(403, f"配额不足: {quota_type}")
    return row


def consume_quota(session, user_id: int, quota_type: str, amount: int = 1) -> Quota:
    row = require_quota(session, user_id, quota_type, amount)
    row.used += amount
    if not row.reset_at:
        row.reset_at = _month_reset()
    session.add(row)
    session.commit()
    if quota_type.startswith("llm") or quota_type in {"tokens", "llm_tokens"}:
        neuro_bus.publish(
            new_event(
                "llm.quota_consumed",
                producer="quota",
                subject_id=str(user_id),
                payload={"user_id": user_id, "quota_type": quota_type, "amount": amount, "used": row.used, "total": row.total},
            )
        )
    return row
