"""MODstore 支付订单存储（JSON 文件落盘）。"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

_ORDERS_DIR_VAR = "MODSTORE_PAYMENT_ORDERS_DIR"

def _orders_dir() -> Path:
    d = Path(os.environ.get(_ORDERS_DIR_VAR, "") or (Path(__file__).resolve().parent / "payment_orders"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(out_trade_no: str) -> Path:
    return _orders_dir() / f"order_{out_trade_no}.json"


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def create(
    *,
    out_trade_no: str,
    subject: str,
    total_amount: str,
    user_id: int = 0,
    item_id: int = 0,
    plan_id: str = "",
    order_kind: str = "",
    qr_code: str | None = None,
    pay_type: str | None = None,
) -> dict[str, Any]:
    """创建订单记录。``order_kind``: ``plan`` | ``item`` | ``wallet``。"""
    p = _path(out_trade_no)
    if p.is_file():
        return {"ok": False, "message": f"订单 {out_trade_no} 已存在"}
    kind = order_kind or ("item" if item_id else "plan" if plan_id else "wallet")
    doc: dict[str, Any] = {
        "out_trade_no": out_trade_no,
        "subject": subject,
        "total_amount": total_amount,
        "user_id": user_id,
        "item_id": item_id,
        "plan_id": plan_id or "",
        "order_kind": kind,
        "status": "pending",
        "trade_no": None,
        "buyer_id": None,
        "paid_at": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "notify_count": 0,
        "fulfilled": False,
        "qr_code": qr_code,
        "pay_type": pay_type,
    }
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "order": doc}


def merge_fields(out_trade_no: str, **kwargs: Any) -> bool:
    """合并更新订单 JSON（用于写入二维码、支付类型、fulfilled 等）。"""
    doc = find(out_trade_no)
    if not doc:
        return False
    for k, v in kwargs.items():
        if v is not None:
            doc[k] = v
    doc["updated_at"] = _now_iso()
    p = _path(out_trade_no)
    try:
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except OSError:
        return False


def find(out_trade_no: str) -> Optional[dict[str, Any]]:
    p = _path(out_trade_no)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def update_status(
    *,
    out_trade_no: str,
    status: str,
    trade_no: Optional[str] = None,
    buyer_id: Optional[str] = None,
    paid_at: Optional[str] = None,
) -> bool:
    doc = find(out_trade_no)
    if not doc:
        return False
    doc["status"] = status
    doc["updated_at"] = _now_iso()
    if trade_no:
        doc["trade_no"] = trade_no
    if buyer_id:
        doc["buyer_id"] = buyer_id
    if paid_at:
        doc["paid_at"] = paid_at
    doc["notify_count"] = doc.get("notify_count", 0) + 1
    p = _path(out_trade_no)
    try:
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def list_orders(
    *,
    user_id: int = 0,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """按创建时间倒序列出订单。"""
    rows = []
    for p in _orders_dir().glob("order_*.json"):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            if user_id and doc.get("user_id") != user_id:
                continue
            if status and doc.get("status") != status:
                continue
            rows.append(doc)
        except Exception:
            continue

    rows.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    total = len(rows)
    return rows[offset : offset + limit], total
