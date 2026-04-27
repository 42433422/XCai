"""Employee application boundary."""

from __future__ import annotations

from typing import Any

from modstore_server.employee_executor import execute_employee_task, get_employee_status, list_employees


class EmployeeApplicationService:
    def list_available(self) -> list[dict[str, Any]]:
        return list_employees()

    def status(self, employee_id: str) -> dict[str, Any]:
        return get_employee_status(employee_id)

    def execute(self, employee_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return execute_employee_task(employee_id, payload)
