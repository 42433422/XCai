"""Execute a :class:`VibeWorkflowGraph` (code-layer only).

The standalone engine runs every node through :class:`CodeSkillRuntime` —
which already provides per-node self-healing (sandbox + LLM patch + solidify).
We do not include the config-layer (``ESkillRuntime``) or ``ESkillNodeWrapper``
plumbing that exists upstream; those belong to the eskill prototype. If you
need them, use the upstream ``eskill.vibe_coding`` package instead.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ._internals import TriggerPolicy
from .runtime import CodeSkillRuntime
from .workflow_models import VibeWorkflowGraph, VibeWorkflowNode


@dataclass(slots=True)
class NodeRunOutcome:
    node_id: str
    layer: str | None
    skill_id: str
    stage: str
    output: dict[str, Any]
    duration_ms: float
    error: str = ""
    patch: dict[str, Any] | None = None


@dataclass(slots=True)
class WorkflowRunResult:
    workflow_id: str
    success: bool
    context: dict[str, Any] = field(default_factory=dict)
    outcomes: list[NodeRunOutcome] = field(default_factory=list)
    error: str = ""
    duration_ms: float = 0.0

    def output_for(self, node_id: str) -> dict[str, Any] | None:
        for o in self.outcomes:
            if o.node_id == node_id:
                return o.output
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "success": self.success,
            "context": dict(self.context),
            "outcomes": [
                {
                    "node_id": o.node_id,
                    "layer": o.layer,
                    "skill_id": o.skill_id,
                    "stage": o.stage,
                    "output": dict(o.output),
                    "duration_ms": o.duration_ms,
                    "error": o.error,
                    "patch": o.patch,
                }
                for o in self.outcomes
            ],
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class VibeWorkflowEngine:
    """Run a :class:`VibeWorkflowGraph` produced by :class:`NLWorkflowFactory`."""

    def __init__(self, *, code_runtime: CodeSkillRuntime):
        if code_runtime is None:
            raise ValueError("code_runtime is required")
        self.code_runtime = code_runtime

    def run(self, graph: VibeWorkflowGraph, input_data: dict[str, Any]) -> WorkflowRunResult:
        issues = graph.validate()
        if issues:
            return WorkflowRunResult(
                workflow_id=graph.workflow_id,
                success=False,
                error=f"graph validation failed: {issues}",
            )

        t0 = time.perf_counter()
        context: dict[str, Any] = dict(input_data or {})
        outcomes: list[NodeRunOutcome] = []
        try:
            order = graph.topological_order()
        except ValueError as exc:
            return WorkflowRunResult(
                workflow_id=graph.workflow_id, success=False, error=str(exc)
            )

        for node in order:
            if node.node_type in ("start", "end"):
                continue
            outcome = self._execute_node(node, context)
            outcomes.append(outcome)
            if outcome.error:
                return WorkflowRunResult(
                    workflow_id=graph.workflow_id,
                    success=False,
                    context=context,
                    outcomes=outcomes,
                    error=f"node {node.node_id!r} failed: {outcome.error}",
                    duration_ms=round((time.perf_counter() - t0) * 1000, 3),
                )
            output_var = str(node.config.get("output_var") or node.node_id)
            context[output_var] = outcome.output

        return WorkflowRunResult(
            workflow_id=graph.workflow_id,
            success=True,
            context=context,
            outcomes=outcomes,
            duration_ms=round((time.perf_counter() - t0) * 1000, 3),
        )

    def _execute_node(self, node: VibeWorkflowNode, context: dict[str, Any]) -> NodeRunOutcome:
        if node.layer != "code":
            return NodeRunOutcome(
                node_id=node.node_id,
                layer=node.layer,
                skill_id="",
                stage="invalid",
                output={},
                duration_ms=0.0,
                error=(
                    f"unsupported node layer {node.layer!r} — standalone vibe_coding "
                    "supports layer='code' only"
                ),
            )
        skill_id = node.code_skill_ref or ""
        if not skill_id:
            return NodeRunOutcome(
                node_id=node.node_id,
                layer="code",
                skill_id="",
                stage="missing_skill",
                output={},
                duration_ms=0.0,
                error="code_skill_ref is empty",
            )
        input_data = self._build_input(node, context)
        t0 = time.perf_counter()
        try:
            cr = self.code_runtime.run(
                skill_id,
                input_data,
                force_dynamic=bool(node.config.get("force_dynamic", False)),
                solidify=bool(node.config.get("solidify", True)),
                trigger_policy=_to_trigger_policy(node.config.get("trigger_policy")),
                quality_gate=node.config.get("quality_gate") or None,
            )
        except Exception as exc:  # noqa: BLE001
            return NodeRunOutcome(
                node_id=node.node_id,
                layer="code",
                skill_id=skill_id,
                stage="exception",
                output={},
                duration_ms=round((time.perf_counter() - t0) * 1000, 3),
                error=str(exc),
            )
        return NodeRunOutcome(
            node_id=node.node_id,
            layer="code",
            skill_id=skill_id,
            stage=cr.stage,
            output=dict(cr.output_data) if cr.output_data else {},
            duration_ms=round((time.perf_counter() - t0) * 1000, 3),
            error=cr.error or "",
            patch=cr.patch.to_dict() if cr.patch else None,
        )

    def _build_input(self, node: VibeWorkflowNode, context: dict[str, Any]) -> dict[str, Any]:
        input_mapping = node.config.get("input_mapping")
        if isinstance(input_mapping, dict) and input_mapping:
            return {str(k): _resolve_ref(ref, context) for k, ref in input_mapping.items()}
        return dict(context)


def _resolve_ref(ref: Any, context: dict[str, Any]) -> Any:
    """Same dotted-path resolver as the upstream engine."""
    if not isinstance(ref, str):
        return ref
    if "." not in ref:
        return context[ref] if ref in context else ref
    parts = ref.split(".")
    head = parts[0]
    if head not in context:
        return ref
    cursor: Any = context[head]
    for part in parts[1:]:
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        else:
            return ref
    return cursor


def _to_trigger_policy(raw: Any) -> TriggerPolicy | None:
    if raw is None:
        return None
    if isinstance(raw, TriggerPolicy):
        return raw
    if isinstance(raw, dict):
        return TriggerPolicy.from_dict(raw)
    return None
