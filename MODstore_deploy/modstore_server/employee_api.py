"""员工API模块，提供员工相关的API端点。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from modstore_server.api.deps import _get_current_user
from modstore_server.infrastructure.db import get_db
from modstore_server.models import CatalogItem, Entitlement, User, UserPlan
from modstore_server.services.employee import get_default_employee_client
from modstore_server.employee_executor import get_employee_status, list_employees as list_employees_exec

router = APIRouter(prefix="/api/employees", tags=["employees"])


def _user_may_execute_employee_pack(db: Session, user_id: int, pack_id: str) -> bool:
    """路径参数 ``employee_id`` 与 ``CatalogItem.pkg_id`` 一致（见 employee_runtime.load_employee_pack）。"""
    u = db.query(User).filter(User.id == user_id).first()
    if u and getattr(u, "is_admin", False):
        return True

    row = (
        db.query(CatalogItem)
        .filter(CatalogItem.pkg_id == pack_id.strip(), CatalogItem.artifact == "employee_pack")
        .first()
    )
    if not row:
        return False
    if row.author_id is not None and int(row.author_id) == int(user_id):
        return True

    ent = (
        db.query(Entitlement)
        .filter(
            Entitlement.user_id == user_id,
            Entitlement.catalog_id == row.id,
            Entitlement.is_active == True,
        )
        .first()
    )
    if ent:
        return True

    now = datetime.now(timezone.utc)
    plan = (
        db.query(UserPlan)
        .filter(UserPlan.user_id == user_id, UserPlan.is_active == True)
        .order_by(UserPlan.id.desc())
        .first()
    )
    if not plan:
        return False
    exp = plan.expires_at
    if exp is None:
        return True
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp > now


@router.get("/", summary="获取员工列表")
async def list_employees(
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """获取所有可用的AI员工"""
    try:
        employees = list_employees_exec()
        return employees
    except Exception as e:
        raise HTTPException(500, f"获取员工列表失败: {e}")


@router.get("/{employee_id}/status", summary="获取员工状态")
async def get_employee_status_endpoint(
    employee_id: str,
    user: User = Depends(_get_current_user),
):
    """获取员工的状态信息"""
    try:
        status = get_employee_status(employee_id)
        return status
    except Exception as e:
        raise HTTPException(500, f"获取员工状态失败: {e}")


@router.post("/{employee_id}/execute", summary="执行员工任务")
async def execute_employee_task_endpoint(
    employee_id: str,
    task: str,
    input_data: Optional[Dict] = None,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """执行员工任务"""
    if not _user_may_execute_employee_pack(db, user.id, employee_id):
        raise HTTPException(403, "您无权执行该员工，请先购买或订阅套餐")

    failure: str | None = None
    try:
        result = get_default_employee_client().execute_task(
            employee_id=employee_id,
            task=task,
            input_data=input_data or {},
            user_id=user.id,
        )
    except Exception as e:
        failure = str(e)
        result = None
    try:
        from modstore_server import webhook_dispatcher
        from modstore_server.eventing.contracts import EMPLOYEE_EXECUTION_COMPLETED

        webhook_dispatcher.publish_event(
            EMPLOYEE_EXECUTION_COMPLETED,
            aggregate_id=str(employee_id),
            data={
                "employee_id": employee_id,
                "user_id": int(user.id),
                "task": (task or "")[:256],
                "status": "failure" if failure else "success",
                "error": failure or "",
                "result_summary": (str(result)[:512] if isinstance(result, str) else "")
                if not isinstance(result, dict)
                else {
                    k: result.get(k)
                    for k in ("status", "ok", "duration_ms", "tokens_used")
                    if k in result
                },
            },
            source="modstore-employee-api",
        )
    except Exception:
        # 投递失败不阻塞业务回包
        pass

    if failure is not None:
        raise HTTPException(500, f"执行员工任务失败: {failure}")
    return result
