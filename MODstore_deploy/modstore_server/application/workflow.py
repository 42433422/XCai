"""Workflow application boundary."""

from __future__ import annotations

from typing import Any

from modstore_server.workflow_engine import run_workflow_sandbox


class WorkflowApplicationService:
    def run_sandbox(self, workflow_id: int, input_data: dict[str, Any], *, mock_employees: bool = True, validate_only: bool = False) -> dict[str, Any]:
        return run_workflow_sandbox(
            workflow_id=workflow_id,
            input_data=input_data,
            mock_employees=mock_employees,
            validate_only=validate_only,
        )
