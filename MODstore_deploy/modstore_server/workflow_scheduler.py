"""工作流 cron 触发：从 DB 加载 APScheduler 任务。"""

from __future__ import annotations

import json
import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from modstore_server import payment_orders
from modstore_server.models import WorkflowTrigger, get_session_factory
from modstore_server.workflow_engine import execute_workflow

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None

_JOB_PREFIX = "wf_trigger_"


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.start()
    _load_triggers()

    def _close_stale_orders() -> None:
        try:
            n = payment_orders.close_pending_older_than(minutes=30)
            if n:
                logger.info("closed %d expired pending payment orders", n)
        except Exception:
            logger.exception("close expired payment orders failed")

    _scheduler.add_job(
        _close_stale_orders,
        IntervalTrigger(minutes=5),
        id="payment_orders_expire",
        replace_existing=True,
    )
    logger.info("workflow scheduler started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("workflow scheduler stopped")


def _job_id(trigger_id: int) -> str:
    return f"{_JOB_PREFIX}{trigger_id}"


def _load_triggers() -> None:
    if _scheduler is None:
        return
    sf = get_session_factory()
    with sf() as session:
        rows = (
            session.query(WorkflowTrigger)
            .filter(
                WorkflowTrigger.trigger_type == "cron",
                WorkflowTrigger.is_active.is_(True),
            )
            .all()
        )
    for t in rows:
        _register_cron_trigger(t.id, t.workflow_id, t.user_id, t.config_json or "{}")


def _register_cron_trigger(trigger_id: int, workflow_id: int, user_id: int, config_json: str) -> None:
    global _scheduler
    if _scheduler is None:
        return
    try:
        config = json.loads(config_json or "{}")
    except json.JSONDecodeError:
        config = {}
    cron_expr = str(config.get("cron") or config.get("schedule") or "0 0 * * *").strip()

    wf_id = workflow_id
    uid = user_id

    def job_wrapper() -> None:
        try:
            sf = get_session_factory()
            with sf() as qdb:
                from modstore_server.quota_middleware import require_quota

                require_quota(qdb, uid, "llm_calls", 1)
            execute_workflow(wf_id, {}, user_id=uid)
            with sf() as qdb2:
                from modstore_server.quota_middleware import consume_quota

                consume_quota(qdb2, uid, "llm_calls", 1)
        except Exception as e:
            logger.exception("cron workflow failed workflow_id=%s: %s", wf_id, e)

    jid = _job_id(trigger_id)
    try:
        _scheduler.remove_job(jid)
    except Exception:
        pass
    try:
        _scheduler.add_job(
            job_wrapper,
            CronTrigger.from_crontab(cron_expr),
            id=jid,
            replace_existing=True,
        )
        logger.info("registered cron trigger id=%s workflow=%s expr=%s", trigger_id, wf_id, cron_expr)
    except Exception as e:
        logger.warning("invalid cron for trigger id=%s: %s", trigger_id, e)


def unregister_cron_trigger(trigger_id: int) -> None:
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.remove_job(_job_id(trigger_id))
    except Exception:
        pass


def refresh_cron_trigger(trigger_id: int) -> None:
    sf = get_session_factory()
    with sf() as session:
        t = session.query(WorkflowTrigger).filter(WorkflowTrigger.id == trigger_id).first()
    if not t or not t.is_active or (t.trigger_type or "").lower() != "cron":
        unregister_cron_trigger(trigger_id)
        return
    _register_cron_trigger(t.id, t.workflow_id, t.user_id, t.config_json or "{}")


def reload_all_cron_triggers() -> None:
    global _scheduler
    if _scheduler is None:
        return
    for job in list(_scheduler.get_jobs()):
        jid = job.id or ""
        if jid.startswith(_JOB_PREFIX):
            try:
                _scheduler.remove_job(jid)
            except Exception:
                pass
    _load_triggers()
