"""工作流引擎：执行、沙盒追踪、拓扑校验。"""

from __future__ import annotations

import copy
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from modstore_server.models import (
    Workflow,
    WorkflowNode,
    WorkflowEdge,
    get_session_factory,
)
from modstore_server.eventing import new_event
from modstore_server.eventing.global_bus import neuro_bus
from modstore_server.workflow_variables import eval_condition, resolve_value

logger = logging.getLogger(__name__)


def _json_safe(value: Any, max_depth: int = 6, max_str: int = 8000) -> Any:
    """将上下文快照转为可 JSON 序列化的结构（沙盒报告用）。"""
    if max_depth <= 0:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > max_str:
            return value[: max_str - 1] + "…"
        return value
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= 80:
                out["__truncated__"] = True
                break
            sk = str(k)[:128]
            out[sk] = _json_safe(v, max_depth - 1, max_str)
        return out
    if isinstance(value, (list, tuple)):
        lim = 40
        return [_json_safe(v, max_depth - 1, max_str) for v in value[:lim]] + (
            [f"<{len(value) - lim} more>"] if len(value) > lim else []
        )
    return str(type(value).__name__) + ":<non-serializable>"


class WorkflowEngine:
    """工作流引擎：支持生产执行与沙盒（全链路追踪、Mock 员工）。"""

    def __init__(self):
        self.executors = {
            "start": self._execute_start_node,
            "end": self._execute_end_node,
            "employee": self._execute_employee_node,
            "condition": self._execute_condition_node,
            "openapi_operation": self._execute_openapi_operation_node,
            "knowledge_search": self._execute_knowledge_search_node,
            "webhook_trigger": self._execute_webhook_trigger_node,
            "cron_trigger": self._execute_cron_trigger_node,
            "variable_set": self._execute_variable_set_node,
        }

    def register_executor(self, node_type: str, executor):
        self.executors[node_type] = executor

    def execute_workflow(
        self,
        workflow_id: int,
        input_data: Dict[str, Any] = None,
        *,
        user_id: int = 0,
    ) -> Dict[str, Any]:
        """执行工作流（仅运行业务图，不写入 workflow_executions；由 API 层落库）。"""
        SessionFactory = get_session_factory()
        with SessionFactory() as session:
            workflow = session.query(Workflow).filter(Workflow.id == workflow_id).first()
            if not workflow:
                raise ValueError(f"工作流不存在: {workflow_id}")
            output, _steps, _warn = self._run_graph(
                session,
                workflow,
                input_data or {},
                mock_employees=False,
                collect_trace=False,
                user_id=user_id,
            )
            return output

    def run_sandbox(
        self,
        session: Session,
        workflow: Workflow,
        input_data: Dict[str, Any],
        *,
        mock_employees: bool = True,
        validate_only: bool = False,
        user_id: int = 0,
    ) -> Dict[str, Any]:
        """
        沙盒运行：不写入执行表。
        - validate_only：只做静态校验 + 拓扑可达性，不执行节点逻辑。
        - mock_employees：员工节点不调用真实执行器，返回可预测的桩数据。
        """
        errors = WorkflowValidator.validate_workflow(workflow, session)
        topo_warnings = _topology_warnings(session, workflow.id)
        if validate_only:
            return {
                "ok": len(errors) == 0,
                "validate_only": True,
                "errors": errors,
                "warnings": topo_warnings,
                "steps": [],
                "output": {},
            }
        if errors:
            return {
                "ok": False,
                "validate_only": False,
                "errors": errors,
                "warnings": topo_warnings,
                "steps": [],
                "output": {},
            }
        output, steps, run_warn = self._run_graph(
            session,
            workflow,
            input_data or {},
            mock_employees=mock_employees,
            collect_trace=True,
            user_id=user_id,
        )
        return {
            "ok": True,
            "validate_only": False,
            "errors": [],
            "warnings": topo_warnings + run_warn,
            "steps": steps,
            "output": _json_safe(output),
        }

    def _run_graph(
        self,
        session: Session,
        workflow: Workflow,
        input_data: Dict[str, Any],
        *,
        mock_employees: bool,
        collect_trace: bool,
        user_id: int = 0,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
        nodes = (
            session.query(WorkflowNode)
            .filter(WorkflowNode.workflow_id == workflow.id)
            .all()
        )
        edges = (
            session.query(WorkflowEdge)
            .filter(WorkflowEdge.workflow_id == workflow.id)
            .all()
        )
        node_map = {node.id: node for node in nodes}
        source_to_targets: Dict[int, List[WorkflowEdge]] = {}
        for edge in edges:
            source_to_targets.setdefault(edge.source_node_id, []).append(edge)
        for k in source_to_targets:
            source_to_targets[k].sort(key=lambda e: e.id)

        start_node = None
        for node in nodes:
            if node.node_type == "start":
                start_node = node
                break
        if not start_node:
            raise ValueError("工作流没有开始节点")

        current_node: Optional[WorkflowNode] = start_node
        current_data = copy.deepcopy(input_data) if input_data else {}
        steps: List[Dict[str, Any]] = []
        run_warnings: List[str] = []
        order = 0

        while current_node:
            t0 = time.perf_counter()
            data_before = _json_safe(current_data) if collect_trace else {}
            config = json.loads(current_node.config) if current_node.config else {}

            node_output = self._execute_node(
                current_node,
                current_data,
                config,
                mock_employee=mock_employees,
                user_id=user_id,
            )
            duration_ms = round((time.perf_counter() - t0) * 1000, 3)

            if collect_trace:
                order += 1
                steps.append(
                    {
                        "order": order,
                        "node_id": current_node.id,
                        "node_type": current_node.node_type,
                        "node_name": current_node.name,
                        "duration_ms": duration_ms,
                        "input_snapshot": data_before,
                        "output_delta": _json_safe(node_output),
                        "mock_employee": bool(
                            mock_employees and current_node.node_type == "employee"
                        ),
                        "edge_taken": None,
                    }
                )

            current_data.update(node_output)

            if current_node.node_type == "end":
                break

            next_edges = source_to_targets.get(current_node.id, [])
            if not next_edges:
                run_warnings.append(f"节点「{current_node.name}」无出边，流程提前结束")
                break

            next_node: Optional[WorkflowNode] = None
            edge_taken: Optional[Dict[str, Any]] = None
            ambiguous = [e for e in next_edges if not (e.condition or "").strip()]
            if len(ambiguous) > 1:
                run_warnings.append(
                    f"节点「{current_node.name}」存在多条无条件出边，已按边 id 最小优先（{ambiguous[0].id}）"
                )

            for edge in next_edges:
                cond_raw = (edge.condition or "").strip()
                if not cond_raw:
                    next_node = node_map.get(edge.target_node_id)
                    edge_taken = {
                        "edge_id": edge.id,
                        "condition": None,
                        "matched": True,
                    }
                    break
                matched = self._evaluate_condition(cond_raw, current_data)
                if collect_trace and steps:
                    steps[-1].setdefault("condition_branches", []).append(
                        {
                            "edge_id": edge.id,
                            "target_node_id": edge.target_node_id,
                            "condition": cond_raw,
                            "matched": matched,
                        }
                    )
                if matched:
                    next_node = node_map.get(edge.target_node_id)
                    edge_taken = {
                        "edge_id": edge.id,
                        "condition": cond_raw,
                        "matched": True,
                    }
                    break

            if collect_trace and steps:
                steps[-1]["edge_taken"] = edge_taken
            if next_node is None and next_edges:
                run_warnings.append(
                    f"节点「{current_node.name}」无有向边条件命中，流程停止"
                )
            current_node = next_node

        return current_data, steps, run_warnings

    def _execute_node(
        self,
        node: WorkflowNode,
        data: Dict[str, Any],
        config: Dict[str, Any],
        *,
        mock_employee: bool,
        user_id: int = 0,
    ) -> Dict[str, Any]:
        executor = self.executors.get(node.node_type)
        if not executor:
            raise ValueError(f"未知的节点类型: {node.node_type}")
        if node.node_type == "employee" and mock_employee:
            return self._execute_employee_node_mock(node, data, config)
        if node.node_type == "openapi_operation" and mock_employee:
            return self._execute_openapi_operation_mock(node, data, config)
        if node.node_type == "knowledge_search" and mock_employee:
            return self._execute_knowledge_search_mock(node, data, config)
        if node.node_type in ("employee", "openapi_operation", "knowledge_search"):
            return executor(node, data, config, user_id=user_id)
        return executor(node, data, config)

    def _execute_employee_node_mock(
        self, node: WorkflowNode, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        employee_id = config.get("employee_id", "")
        task = config.get("task", "")
        return {
            "employee_result": {
                "sandbox": True,
                "message": "沙盒 Mock：未调用真实员工执行器",
                "employee_id": employee_id,
                "task": task,
                "echo_keys": list(data.keys())[:24],
            },
            "employee_id": employee_id,
            "task": task,
            "execution_time": datetime.utcnow().isoformat(),
        }

    def _execute_openapi_operation_mock(
        self, node: WorkflowNode, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "openapi_result": {
                "sandbox": True,
                "message": "沙盒 Mock：未触发真实第三方 API 调用",
                "connector_id": config.get("connector_id"),
                "operation_id": config.get("operation_id"),
                "echo_keys": list(data.keys())[:24],
            },
            "connector_id": config.get("connector_id"),
            "operation_id": config.get("operation_id"),
            "execution_time": datetime.utcnow().isoformat(),
        }

    def _execute_knowledge_search_mock(
        self, node: WorkflowNode, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        out_var = str(config.get("output_var") or "knowledge")
        return {
            out_var: {
                "sandbox": True,
                "message": "沙盒 Mock：未真实查询向量库",
                "items": [],
                "count": 0,
            },
            "knowledge_search_collections": list(config.get("collection_ids") or []),
            "execution_time": datetime.utcnow().isoformat(),
        }

    def _execute_knowledge_search_node(
        self,
        node: WorkflowNode,
        data: Dict[str, Any],
        config: Dict[str, Any],
        *,
        user_id: int = 0,
    ) -> Dict[str, Any]:
        """``knowledge_search`` 节点：跨多个集合做 RAG 检索，写入 ``output_var``。

        Config:
            - collection_ids: list[int]    显式指定要查询的集合（可见性仍受权限校验）
            - query_template: str          支持 ``${var}`` 模板，从 ``data`` 取变量
            - query: str                   query_template 不存在时的默认文本
            - top_k: int                   返回数量
            - min_score: float             1 - distance 最低分阈值
            - employee_id: str             带上某 employee 上下文（包含其拥有的集合）
            - workflow_id: int             带上 workflow 上下文
            - output_var: str              结果写入 data 的键名（默认 'knowledge'）
        """
        logger.info("执行知识检索节点: %s", node.name)
        from modstore_server import rag_service

        ctx = {"nodes": data, "global": data, "result": data}
        raw_query = config.get("query_template") or config.get("query") or ""
        query_text = ""
        if isinstance(raw_query, str):
            try:
                query_text = str(resolve_value(raw_query, ctx) or "").strip()
            except Exception:  # noqa: BLE001
                query_text = raw_query.strip()
        else:
            query_text = str(resolve_value(raw_query, ctx) or "")

        top_k = int(config.get("top_k") or 6)
        min_score = float(config.get("min_score") or 0.0)
        out_var = str(config.get("output_var") or "knowledge")
        collection_ids_raw = config.get("collection_ids") or []
        if not isinstance(collection_ids_raw, list):
            collection_ids_raw = [collection_ids_raw]
        collection_ids = [int(x) for x in collection_ids_raw if x is not None]

        employee_id = str(config.get("employee_id") or "") or None
        workflow_id_cfg = config.get("workflow_id")
        try:
            workflow_id_int = int(workflow_id_cfg) if workflow_id_cfg is not None else None
        except Exception:  # noqa: BLE001
            workflow_id_int = None

        async def _run():
            return await rag_service.retrieve(
                user_id=int(user_id or 0),
                query=query_text,
                employee_id=employee_id,
                workflow_id=workflow_id_int,
                extra_collection_ids=collection_ids or None,
                top_k=top_k,
                min_score=min_score,
            )

        try:
            from modstore_server.employee_executor import _run_coro_sync

            chunks = _run_coro_sync(_run())
        except Exception as e:  # noqa: BLE001
            logger.warning("knowledge_search 节点执行失败: %s", e)
            return {
                out_var: {"items": [], "count": 0, "error": str(e)},
                "execution_time": datetime.utcnow().isoformat(),
            }

        items = [c.to_dict() for c in (chunks or [])]
        return {
            out_var: {"items": items, "count": len(items), "query": query_text},
            "execution_time": datetime.utcnow().isoformat(),
        }

    def _execute_start_node(
        self, node: WorkflowNode, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info("执行开始节点")
        return {}

    def _execute_end_node(
        self, node: WorkflowNode, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info("执行结束节点")
        return {}

    def _execute_employee_node(
        self, node: WorkflowNode, data: Dict[str, Any], config: Dict[str, Any], *, user_id: int = 0
    ) -> Dict[str, Any]:
        logger.info("执行员工节点: %s", node.name)
        employee_id = config.get("employee_id")
        task = config.get("task")
        if not employee_id or not task:
            raise ValueError("员工节点缺少必要的配置: employee_id 和 task")
        input_data = resolve_value(config.get("input_mapping") or data, {"nodes": data, "global": data, "result": data})
        timeout_seconds = int(config.get("timeout_seconds") or 30)
        retry_count = int(config.get("retry_count") or 0)
        output_mapping = config.get("output_mapping") or {}
        last_err = None
        try:
            from modstore_server.employee_executor import execute_employee_task
            result = None
            for _ in range(max(1, retry_count + 1)):
                with ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(execute_employee_task, employee_id, task, input_data, user_id)
                    try:
                        result = future.result(timeout=timeout_seconds)
                        break
                    except FutureTimeout as e:
                        last_err = e
                    except Exception as e:  # noqa: PERF203
                        last_err = e
            if result is None:
                raise RuntimeError(f"employee node failed: {last_err}")
            mapped = resolve_value(output_mapping, {"result": result, "nodes": data, "global": data})
            base = {
                "employee_result": result,
                "employee_id": employee_id,
                "task": task,
                "execution_time": datetime.utcnow().isoformat(),
            }
            if isinstance(mapped, dict):
                base.update(mapped)
            return base
        except Exception as e:
            logger.error("员工执行失败: %s", e)
            raise

    def _execute_openapi_operation_node(
        self,
        node: WorkflowNode,
        data: Dict[str, Any],
        config: Dict[str, Any],
        *,
        user_id: int = 0,
    ) -> Dict[str, Any]:
        logger.info("执行 OpenAPI operation 节点: %s", node.name)
        connector_id = config.get("connector_id")
        operation_id = config.get("operation_id")
        if not connector_id or not operation_id:
            raise ValueError("openapi_operation 节点缺少 connector_id 或 operation_id")
        try:
            connector_id_int = int(connector_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"connector_id 必须为整数: {connector_id!r}") from exc
        ctx = {"nodes": data, "global": data, "result": data}
        params = resolve_value(config.get("input_mapping") or {}, ctx) or {}
        body = resolve_value(config.get("body") or None, ctx) if config.get("body") is not None else None
        headers = resolve_value(config.get("headers") or {}, ctx) or {}
        timeout_seconds = max(1, min(60, int(config.get("timeout_seconds") or 30)))
        retry_count = max(0, min(5, int(config.get("retry_count") or 0)))
        output_mapping = config.get("output_mapping") or {}

        try:
            from modstore_server.openapi_connector_runtime import call_generated_operation
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"openapi connector runtime 不可用: {exc}") from exc

        last_result: Dict[str, Any] = {}
        last_err: Optional[str] = None
        for _ in range(retry_count + 1):
            last_result = call_generated_operation(
                connector_id=connector_id_int,
                user_id=int(user_id or 0),
                operation_id=str(operation_id),
                params=params if isinstance(params, dict) else {},
                body=body,
                headers=headers if isinstance(headers, dict) else {},
                timeout=float(timeout_seconds),
                source="workflow",
            )
            if last_result.get("ok"):
                last_err = None
                break
            last_err = str(last_result.get("error") or "")
        mapped = resolve_value(
            output_mapping, {"result": last_result, "nodes": data, "global": data}
        )
        base = {
            "openapi_result": last_result,
            "connector_id": connector_id_int,
            "operation_id": operation_id,
            "execution_time": datetime.utcnow().isoformat(),
        }
        if isinstance(mapped, dict):
            base.update(mapped)
        if last_err and not last_result.get("ok"):
            base["error"] = last_err
        return base

    def _execute_condition_node(
        self, node: WorkflowNode, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info("执行条件节点: %s", node.name)
        return {}

    def _execute_webhook_trigger_node(
        self, node: WorkflowNode, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """触发器节点：运行时由 HTTP/cron 调度；图内执行仅保证 payload 变量存在。"""
        logger.info("执行 Webhook 触发器节点（图内占位）: %s", node.name)
        payload_var = str(config.get("payload_var") or "webhook_payload").strip() or "webhook_payload"
        return {payload_var: data.get(payload_var, {})}

    def _execute_cron_trigger_node(
        self, node: WorkflowNode, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """定时触发器：调度由 workflow_scheduler 负责；图内执行为空增量。"""
        logger.info("执行 Cron 触发器节点（图内占位）: %s", node.name)
        return {}

    def _execute_variable_set_node(
        self, node: WorkflowNode, data: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """向上下文写入变量（支持 ``{{ var }}`` 模板）。"""
        logger.info("执行变量赋值节点: %s", node.name)
        name = str(config.get("name") or "").strip()
        if not name:
            raise ValueError("variable_set 节点缺少 name")
        ctx = {"nodes": data, "global": data, "result": data}
        resolved = resolve_value(config.get("value"), ctx)
        return {name: resolved}

    def _evaluate_condition(self, condition: str, data: Dict[str, Any]) -> bool:
        return eval_condition(condition, data)


def _topology_warnings(session: Session, workflow_id: int) -> List[str]:
    """可达性、孤立节点等（不改变执行语义，仅提示）。"""
    warnings: List[str] = []
    nodes = (
        session.query(WorkflowNode)
        .filter(WorkflowNode.workflow_id == workflow_id)
        .all()
    )
    edges = (
        session.query(WorkflowEdge)
        .filter(WorkflowEdge.workflow_id == workflow_id)
        .all()
    )
    if not nodes:
        return ["工作流没有任何节点"]
    node_ids = {n.id for n in nodes}
    start_ids = [n.id for n in nodes if n.node_type == "start"]
    end_ids = {n.id for n in nodes if n.node_type == "end"}
    if len(start_ids) != 1:
        return warnings
    adj: Dict[int, List[int]] = {nid: [] for nid in node_ids}
    for e in edges:
        if e.source_node_id in node_ids and e.target_node_id in node_ids:
            adj.setdefault(e.source_node_id, []).append(e.target_node_id)
    reachable: set[int] = set()
    stack = [start_ids[0]]
    while stack:
        u = stack.pop()
        if u in reachable:
            continue
        reachable.add(u)
        for v in adj.get(u, []):
            if v not in reachable:
                stack.append(v)
    unreached_end = end_ids - reachable
    if unreached_end:
        warnings.append("存在无法从开始节点到达的结束节点")
    for n in nodes:
        if n.id not in reachable and n.node_type != "start":
            warnings.append(f"孤立节点（从开始不可达）: {n.name} (id={n.id})")
            break
    return warnings


class WorkflowValidator:
    """工作流静态校验。"""

    @staticmethod
    def validate_workflow(workflow: Workflow, session: Session) -> List[str]:
        errors: List[str] = []
        nodes = (
            session.query(WorkflowNode)
            .filter(WorkflowNode.workflow_id == workflow.id)
            .all()
        )
        edges = (
            session.query(WorkflowEdge)
            .filter(WorkflowEdge.workflow_id == workflow.id)
            .all()
        )
        start_nodes = [node for node in nodes if node.node_type == "start"]
        if len(start_nodes) != 1:
            errors.append("工作流必须有且只有一个开始节点")
        end_nodes = [node for node in nodes if node.node_type == "end"]
        if len(end_nodes) == 0:
            errors.append("工作流至少需要一个结束节点")
        for node in nodes:
            if node.node_type == "employee":
                config = json.loads(node.config) if node.config else {}
                if "employee_id" not in config:
                    errors.append(f"员工节点 {node.name} 缺少 employee_id 配置")
                if "task" not in config:
                    errors.append(f"员工节点 {node.name} 缺少 task 配置")
            elif node.node_type == "openapi_operation":
                try:
                    config = json.loads(node.config) if node.config else {}
                except (TypeError, ValueError):
                    config = {}
                if not config.get("connector_id"):
                    errors.append(f"OpenAPI 节点 {node.name} 缺少 connector_id 配置")
                if not config.get("operation_id"):
                    errors.append(f"OpenAPI 节点 {node.name} 缺少 operation_id 配置")
            elif node.node_type == "knowledge_search":
                try:
                    config = json.loads(node.config) if node.config else {}
                except (TypeError, ValueError):
                    config = {}
                has_query = bool(
                    str(config.get("query") or "").strip()
                    or str(config.get("query_template") or "").strip()
                )
                if not has_query:
                    errors.append(f"知识检索节点 {node.name} 缺少 query 或 query_template 配置")
                cids = config.get("collection_ids")
                if cids is not None and not isinstance(cids, list):
                    errors.append(f"知识检索节点 {node.name} 的 collection_ids 必须是数组")
            elif node.node_type == "variable_set":
                try:
                    config = json.loads(node.config) if node.config else {}
                except (TypeError, ValueError):
                    config = {}
                if not str(config.get("name") or "").strip():
                    errors.append(f"变量赋值节点 {node.name} 缺少 name 配置")
            elif node.node_type == "cron_trigger":
                try:
                    config = json.loads(node.config) if node.config else {}
                except (TypeError, ValueError):
                    config = {}
                if not str(config.get("cron") or "").strip():
                    errors.append(f"定时触发器节点 {node.name} 缺少 cron 配置")
        node_ids = {node.id for node in nodes}
        for edge in edges:
            if edge.source_node_id not in node_ids:
                errors.append(f"边引用了不存在的源节点: {edge.source_node_id}")
            if edge.target_node_id not in node_ids:
                errors.append(f"边引用了不存在的目标节点: {edge.target_node_id}")
        return errors


workflow_engine = WorkflowEngine()


def execute_workflow(
    workflow_id: int, input_data: Dict[str, Any] = None, *, user_id: int = 0
) -> Dict[str, Any]:
    return workflow_engine.execute_workflow(workflow_id, input_data, user_id=user_id)


def validate_workflow(workflow_id: int) -> List[str]:
    SessionFactory = get_session_factory()
    with SessionFactory() as session:
        workflow = session.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            return [f"工作流不存在: {workflow_id}"]
        return WorkflowValidator.validate_workflow(workflow, session)


def run_workflow_sandbox(
    workflow_id: int,
    input_data: Dict[str, Any],
    *,
    mock_employees: bool = True,
    validate_only: bool = False,
    user_id: int = 0,
) -> Dict[str, Any]:
    SessionFactory = get_session_factory()
    with SessionFactory() as session:
        workflow = session.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            return {
                "ok": False,
                "errors": [f"工作流不存在: {workflow_id}"],
                "warnings": [],
                "steps": [],
                "output": {},
                "validate_only": validate_only,
            }
        result = workflow_engine.run_sandbox(
            session,
            workflow,
            input_data or {},
            mock_employees=mock_employees,
            validate_only=validate_only,
            user_id=user_id,
        )
        neuro_bus.publish(
            new_event(
                "workflow.sandbox_completed",
                producer="workflow",
                subject_id=str(workflow_id),
                payload={
                    "workflow_id": workflow_id,
                    "user_id": user_id,
                    "ok": bool(result.get("ok")),
                    "validate_only": validate_only,
                },
            )
        )
        return result
