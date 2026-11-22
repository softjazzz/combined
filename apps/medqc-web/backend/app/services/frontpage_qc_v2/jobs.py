"""首页质控 V2：后台批量任务。

确定性规则、不调用模型。逐份读取 CDM 首页（只读）→ 执行规则 → 写入结果表。
单份失败不阻塞其余病历，任务结束后汇总失败列表；支持取消。
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .adapter import build_frontpage_doc
from .engine import evaluate_frontpage
from .loader import FrontpageRef, load_frontpage_raw
from .store import FrontpageQcStore

logger = logging.getLogger(__name__)

MAX_RECORDS_PER_RUN = 500
PROGRESS_EVERY = 10
_FAILED_SAMPLE_LIMIT = 50

RecordMeta = Dict[FrontpageRef, Dict[str, str]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_frontpage_qc_job(
    run_id: str,
    *,
    store: FrontpageQcStore,
    cdm_session_factory: Callable[[], Any],
    record_meta: Optional[RecordMeta] = None,
    cdm_schema: Any = ...,
) -> Dict[str, Any]:
    """执行一个已创建的任务。record_meta 按三坐标提供科室、出院日期等展示字段。"""
    run = store.get_run(run_id)
    if run["status"] != "queued":
        return run
    if run.get("cancel_requested"):
        return store.request_cancel(run_id)
    if not store.claim_run(run_id):
        return store.get_run(run_id)
    refs = store.run_refs(run_id)
    meta = record_meta or {}

    processed = success = failed = issue_records = gap_records = 0
    failed_records: List[Dict[str, str]] = []
    cancelled = False
    try:
        with cdm_session_factory() as cdm_session:
            for index, ref in enumerate(refs):
                if store.is_cancel_requested(run_id):
                    cancelled = True
                    break
                try:
                    kwargs = {} if cdm_schema is ... else {"schema": cdm_schema}
                    raw = load_frontpage_raw(cdm_session, ref, **kwargs)
                    if raw is None:
                        raise LookupError("未找到病案首页")
                    outcome = evaluate_frontpage(build_frontpage_doc(raw))
                    info = meta.get(ref, {})
                    store.save_outcome(
                        run_id=run_id,
                        outcome=outcome,
                        department=info.get("department") or raw.mr.get("discharge_dept_name") or "",
                        discharge_date=info.get("discharge_date") or str(raw.mr.get("discharge_datetime") or "")[:10],
                    )
                    success += 1
                    issue_records += 1 if outcome.fail_count else 0
                    gap_records += 1 if outcome.data_gap_count else 0
                except Exception as exc:  # noqa: BLE001 - 单份失败记录后继续
                    failed += 1
                    rollback = getattr(cdm_session, "rollback", None)
                    if callable(rollback):
                        rollback()
                    if len(failed_records) < _FAILED_SAMPLE_LIMIT:
                        failed_records.append({**ref.__dict__, "error": type(exc).__name__, "message": str(exc)[:120]})
                    logger.warning("首页质控单份失败 run=%s error=%s", run_id, type(exc).__name__)
                processed += 1
                if processed % PROGRESS_EVERY == 0:
                    store.update_run(
                        run_id,
                        processed_records=processed,
                        success_count=success,
                        failed_count=failed,
                        issue_records=issue_records,
                        data_gap_records=gap_records,
                    )
        if not cancelled and store.is_cancel_requested(run_id):
            cancelled = True
    except Exception as exc:  # noqa: BLE001 - 整体失败要落库，前端才能停止轮询
        logger.exception("首页质控任务失败 run=%s", run_id)
        store.update_run(
            run_id,
            status="failed",
            processed_records=processed,
            success_count=success,
            failed_count=failed,
            issue_records=issue_records,
            data_gap_records=gap_records,
            failed_records=failed_records,
            error_message=f"任务执行失败：{type(exc).__name__}",
            finished_at=_now(),
        )
        return store.get_run(run_id)

    if cancelled:
        status = "cancelled"
    elif failed and not success:
        status = "failed"
    elif failed:
        status = "completed_with_errors"
    else:
        status = "completed"
    store.update_run(
        run_id,
        status=status,
        processed_records=processed,
        success_count=success,
        failed_count=failed,
        issue_records=issue_records,
        data_gap_records=gap_records,
        failed_records=failed_records,
        error_message=None if status != "failed" else "全部病历质控失败",
        finished_at=_now(),
    )
    return store.get_run(run_id)


def refs_from_records(records: List[Dict[str, Any]]) -> List[FrontpageRef]:
    seen = set()
    refs: List[FrontpageRef] = []
    for record in records:
        ref = FrontpageRef.from_record(record)
        if not all((ref.institute_id, ref.patient_id, ref.visit_id)) or ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
    return refs
