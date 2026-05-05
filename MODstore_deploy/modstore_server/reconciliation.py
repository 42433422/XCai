"""平台对账系统 API。

对账报告按时间段汇总以下维度：
  - total_orders / total_gmv：已支付订单数与成交金额
  - platform_revenue：平台抽成收益（来自 AuthorEarning.gross - net 汇总）
  - author_payable：作者应付分润（AuthorEarning.net 汇总）
  - refunds_count / refunds_amount：退款单数与金额
  - wallet_top_ups：钱包充值金额（Transaction txn_type in wallet/alipay_wallet/alipay_recharge）
  - alipay_income：全部支付宝入账（paid orders 总金额）

报告以 ReconciliationReport 快照形式持久化，状态 draft → confirmed。

API 端点（均需管理员权限）：
  POST /api/admin/reconciliation/generate    — 生成指定时段对账报告
  GET  /api/admin/reconciliation             — 列出历史报告
  GET  /api/admin/reconciliation/{id}        — 查看单份报告详情
  POST /api/admin/reconciliation/{id}/confirm — 管理员确认报告
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from modstore_server.api.auth_deps import require_user
from modstore_server.models import (
    AuthorEarning,
    ReconciliationReport,
    Transaction,
    User,
    get_session_factory,
)
from modstore_server import payment_orders as _po

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reconciliation"])


# ---------------------------------------------------------------- DTOs


class GenerateDTO(BaseModel):
    period_start: str  # ISO 8601 datetime
    period_end: str    # ISO 8601 datetime


# ---------------------------------------------------------------- 内部工具


def _parse_dt(s: str) -> datetime:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError as exc:
        raise HTTPException(400, f"日期格式错误（期望 ISO 8601）：{s}") from exc


def _report_row(r: ReconciliationReport) -> dict:
    return {
        "id": r.id,
        "period_start": r.period_start.isoformat() if r.period_start else None,
        "period_end": r.period_end.isoformat() if r.period_end else None,
        "total_orders": r.total_orders,
        "total_gmv": r.total_gmv,
        "platform_revenue": r.platform_revenue,
        "author_payable": r.author_payable,
        "refunds_count": r.refunds_count,
        "refunds_amount": r.refunds_amount,
        "wallet_top_ups": r.wallet_top_ups,
        "alipay_income": r.alipay_income,
        "status": r.status,
        "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None,
    }


def _generate_report(
    session,
    period_start: datetime,
    period_end: datetime,
) -> ReconciliationReport:
    """按时间段从 payment_orders + Transaction + AuthorEarning 汇总数据。"""

    # --- 从 payment_orders（JSON 文件）加载已支付订单 ---
    all_orders, _ = _po.list_orders(status="paid", limit=100_000)
    paid_in_range = []
    refunded_in_range = []
    for o in all_orders:
        raw_ts = o.get("paid_at") or o.get("created_at") or ""
        try:
            ts = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            continue
        if period_start <= ts < period_end:
            paid_in_range.append(o)
        if o.get("refunded"):
            refund_ts_raw = o.get("refunded_at") or o.get("updated_at") or ""
            try:
                refund_ts = datetime.fromisoformat(
                    str(refund_ts_raw).replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except Exception:
                refund_ts = ts
            if period_start <= refund_ts < period_end:
                refunded_in_range.append(o)

    total_orders = len(paid_in_range)
    total_gmv = sum(float(o.get("total_amount") or 0) for o in paid_in_range)
    refunds_count = len(refunded_in_range)
    refunds_amount = sum(float(o.get("total_amount") or 0) for o in refunded_in_range)

    # --- 从 Transaction 表汇总钱包充值 ---
    wallet_top_up_types = {"alipay_wallet", "alipay_recharge", "wallet"}
    wallet_txns = (
        session.query(Transaction)
        .filter(
            Transaction.txn_type.in_(wallet_top_up_types),
            Transaction.created_at >= period_start,
            Transaction.created_at < period_end,
            Transaction.status == "completed",
        )
        .all()
    )
    wallet_top_ups = sum(float(t.amount or 0) for t in wallet_txns if (t.amount or 0) > 0)

    # --- 从 AuthorEarning 汇总分润 ---
    earnings = (
        session.query(AuthorEarning)
        .filter(
            AuthorEarning.created_at >= period_start,
            AuthorEarning.created_at < period_end,
        )
        .all()
    )
    author_payable = sum(float(e.net or 0) for e in earnings)
    platform_revenue = sum(
        float(e.gross or 0) - float(e.net or 0) for e in earnings
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    report = ReconciliationReport(
        period_start=period_start,
        period_end=period_end,
        total_orders=total_orders,
        total_gmv=round(total_gmv, 2),
        platform_revenue=round(platform_revenue, 2),
        author_payable=round(author_payable, 2),
        refunds_count=refunds_count,
        refunds_amount=round(refunds_amount, 2),
        wallet_top_ups=round(wallet_top_ups, 2),
        alipay_income=round(total_gmv, 2),
        status="draft",
        generated_at=now,
    )
    session.add(report)
    session.flush()
    return report


# ---------------------------------------------------------------- API 端点


@router.post("/api/admin/reconciliation/generate")
def api_generate_report(
    body: GenerateDTO,
    user: User = Depends(require_user),
):
    """管理员按时段生成对账报告快照（幂等：不校验重复，允许重新生成）。"""
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    period_start = _parse_dt(body.period_start)
    period_end = _parse_dt(body.period_end)
    if period_end <= period_start:
        raise HTTPException(400, "period_end 必须晚于 period_start")

    sf = get_session_factory()
    with sf() as session:
        report = _generate_report(session, period_start, period_end)
        session.commit()
        session.refresh(report)
        return {"ok": True, "report": _report_row(report)}


@router.get("/api/admin/reconciliation")
def api_list_reports(
    status: Optional[str] = Query(None, description="draft/confirmed"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user: User = Depends(require_user),
):
    """管理员列出历史对账报告（按生成时间倒序）。"""
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    sf = get_session_factory()
    with sf() as session:
        q = session.query(ReconciliationReport)
        if status:
            q = q.filter(ReconciliationReport.status == status)
        total = q.count()
        rows = (
            q.order_by(ReconciliationReport.generated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "ok": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_report_row(r) for r in rows],
        }


@router.get("/api/admin/reconciliation/{report_id}")
def api_get_report(
    report_id: int,
    export_csv: bool = Query(False, description="是否导出订单明细 CSV"),
    user: User = Depends(require_user),
):
    """管理员查看单份报告详情，可选导出订单级 CSV。"""
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    sf = get_session_factory()
    with sf() as session:
        report = session.query(ReconciliationReport).filter(ReconciliationReport.id == report_id).first()
        if not report:
            raise HTTPException(404, "对账报告不存在")

        if not export_csv:
            return {"ok": True, "report": _report_row(report)}

        # 导出订单级 CSV
        period_start = report.period_start
        period_end = report.period_end
        all_orders, _ = _po.list_orders(status="paid", limit=100_000)
        rows_in_range = []
        for o in all_orders:
            raw_ts = o.get("paid_at") or o.get("created_at") or ""
            try:
                ts = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                continue
            if period_start <= ts < period_end:
                rows_in_range.append(o)

        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["out_trade_no", "user_id", "total_amount", "kind", "status", "paid_at", "refunded"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for o in rows_in_range:
            writer.writerow({
                "out_trade_no": o.get("out_trade_no", ""),
                "user_id": o.get("user_id", ""),
                "total_amount": o.get("total_amount", ""),
                "kind": o.get("kind", ""),
                "status": o.get("status", ""),
                "paid_at": o.get("paid_at") or o.get("created_at", ""),
                "refunded": o.get("refunded", False),
            })
        buf.seek(0)
        filename = (
            f"reconciliation_{report_id}_"
            f"{period_start.strftime('%Y%m%d')}_{period_end.strftime('%Y%m%d')}.csv"
        )
        return StreamingResponse(
            iter([buf.read()]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


@router.post("/api/admin/reconciliation/{report_id}/confirm")
def api_confirm_report(
    report_id: int,
    user: User = Depends(require_user),
):
    """管理员确认对账报告（draft → confirmed）。"""
    if not user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sf = get_session_factory()
    with sf() as session:
        report = session.query(ReconciliationReport).filter(ReconciliationReport.id == report_id).first()
        if not report:
            raise HTTPException(404, "对账报告不存在")
        if report.status != "draft":
            raise HTTPException(400, f"报告当前状态为 {report.status}，无法重复确认")
        report.status = "confirmed"
        report.confirmed_at = now
        session.commit()
        return {"ok": True, "report_id": report_id, "status": "confirmed"}


__all__ = ["router"]
