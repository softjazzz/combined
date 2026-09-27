"""金样参考：读取侧版本化前（提交 7faa55e80）worklist_service._load_luxian_0609_analytics_events 原实现。

逐字冻结，仅去掉类缩进变为以 ``self`` 为首参的模块函数；依赖复制自 worklist_service 命名空间，
``__package__`` 设为原包以解析方法体内的相对导入。
仅供等价性金样测试对比使用，禁止修改或在业务代码中引用。
"""
# ruff: noqa

from __future__ import annotations

from app.services.workstation import worklist_service as _worklist_module

globals().update(
    {key: value for key, value in vars(_worklist_module).items() if not key.startswith("__")}
)
# 原方法体内有相对导入（``from ..custom_qc_workspace_service import ...``），按原包解析。
__package__ = _worklist_module.__package__


def _load_luxian_0609_analytics_events(
    self,
    session: Session,
    *,
    records_by_identity: Mapping[tuple[str, str, str], Mapping[str, Any]],
    completed_from: Optional[datetime],
    completed_to: Optional[datetime],
    job_id: Optional[str],
) -> tuple[list[Dict[str, Any]], int]:
    """读取当前版本已完成根任务的 Canonical 事件，缺失只进入数据健康。"""

    from ..custom_qc_workspace_service import CustomQCWorkspaceService
    from ..qc_workspace.canonical_result_store import (
        CANONICAL_RESULT_DELIVERY_MODE as _CANONICAL_RESULT_DELIVERY_MODE,
        _CUSTOMER_STATUSES,
        RECORD_RESULT_ENVELOPE_SCHEMA as _RECORD_RESULT_ENVELOPE_SCHEMA,
    )

    workspace_service = CustomQCWorkspaceService()
    jobs_query = select(
        workspace_service._batch_job_table.c.id,
        workspace_service._batch_job_table.c.finished_at,
        workspace_service._batch_job_table.c.filters_json,
        workspace_service._batch_job_table.c.record_ids_json,
    ).where(
        and_(
            workspace_service._batch_job_table.c.status == "completed",
            or_(
                workspace_service._batch_job_table.c.parent_job_id.is_(None),
                workspace_service._batch_job_table.c.parent_job_id == "",
            ),
        )
    )
    if job_id:
        jobs_query = jobs_query.where(workspace_service._batch_job_table.c.id == job_id)
    jobs: Dict[str, Dict[str, Any]] = {}
    legacy_candidates: Dict[str, Dict[str, Any]] = {}
    for raw_row in session.execute(jobs_query).mappings().all():
        row = dict(raw_row)
        current_job_id = _safe_text(row.get("id")).strip()
        finished_at = _to_datetime(row.get("finished_at"))
        filters = _json_loads_if_needed(row.get("filters_json"))
        source = filters if isinstance(filters, Mapping) else {}
        if (
            not current_job_id
            or finished_at is None
            or (completed_from is not None and finished_at < completed_from)
            or (completed_to is not None and finished_at > completed_to)
        ):
            continue
        record_ids = _json_loads_if_needed(row.get("record_ids_json"))
        job = {
            "finished_at": row.get("finished_at"),
            "record_ids": {
                _safe_text(value).strip()
                for value in record_ids
                if _safe_text(value).strip()
            }
            if isinstance(record_ids, list)
            else set(),
        }
        filter_rule_set_key = _safe_text(source.get("rule_set_key")).strip()
        filter_rule_set_version = _safe_text(source.get("rule_set_version")).strip()
        if (
            filter_rule_set_key == LUXIAN_0609_RULE_SET_KEY
            and filter_rule_set_version == LUXIAN_0609_RULE_SET_VERSION
        ):
            jobs[current_job_id] = job
        elif not filter_rule_set_key and not filter_rule_set_version:
            # 保留历史 summary 回退，但延迟且按任务 ID 精确读取，禁止把每个大
            # summary 拉到统计请求里再反序列化。
            legacy_candidates[current_job_id] = job
    if legacy_candidates:
        legacy_rows = session.execute(
            select(
                workspace_service._batch_job_table.c.id,
                workspace_service._batch_job_table.c.summary_json,
            ).where(workspace_service._batch_job_table.c.id.in_(list(legacy_candidates)))
        ).mappings().all()
        for raw_row in legacy_rows:
            row = dict(raw_row)
            current_job_id = _safe_text(row.get("id")).strip()
            summary = _json_loads_if_needed(row.get("summary_json"))
            if not isinstance(summary, Mapping):
                continue
            if (
                _safe_text(summary.get("rule_set_key")).strip() == LUXIAN_0609_RULE_SET_KEY
                and _safe_text(summary.get("rule_set_version")).strip() == LUXIAN_0609_RULE_SET_VERSION
            ):
                jobs[current_job_id] = legacy_candidates[current_job_id]
    if not jobs:
        return [], 0

    envelope_rows = session.execute(
        select(
            workspace_service._record_result_envelope_table.c.root_job_id,
            workspace_service._record_result_envelope_table.c.institute_id,
            workspace_service._record_result_envelope_table.c.patient_id,
            workspace_service._record_result_envelope_table.c.visit_id,
            workspace_service._record_result_envelope_table.c.envelope_json,
        ).where(
            and_(
                workspace_service._record_result_envelope_table.c.root_job_id.in_(list(jobs)),
                workspace_service._record_result_envelope_table.c.rule_set_key == LUXIAN_0609_RULE_SET_KEY,
                workspace_service._record_result_envelope_table.c.rule_set_version == LUXIAN_0609_RULE_SET_VERSION,
            )
        )
    ).mappings().all()
    rows_by_event: Dict[tuple[str, str, str, str], list[Dict[str, Any]]] = {}
    for raw_row in envelope_rows:
        row = dict(raw_row)
        root_job_id = _safe_text(row.get("root_job_id")).strip()
        identity = tuple(_safe_text(row.get(key)).strip() for key in ("institute_id", "patient_id", "visit_id"))
        if root_job_id not in jobs or not all(identity):
            continue
        rows_by_event.setdefault((root_job_id, *identity), []).append(row)

    events: list[Dict[str, Any]] = []
    invalid_total = 0
    for root_job_id, job in jobs.items():
        record_ids = job["record_ids"]
        matching_identities = [
            identity for identity in records_by_identity if identity[2] in record_ids
        ]
        unresolved_visit_ids = record_ids - {identity[2] for identity in matching_identities}
        invalid_total += len(unresolved_visit_ids)
        for identity in matching_identities:
            candidates = rows_by_event.get((root_job_id, *identity), [])
            if len(candidates) != 1:
                invalid_total += 1
                continue
            envelope = _json_loads_if_needed(candidates[0].get("envelope_json"))
            items = envelope.get("items") if isinstance(envelope, Mapping) else None
            if (
                not isinstance(envelope, Mapping)
                or envelope.get("schema_version") != _RECORD_RESULT_ENVELOPE_SCHEMA
                or envelope.get("delivery_mode") != _CANONICAL_RESULT_DELIVERY_MODE
                or not isinstance(items, list)
            ):
                invalid_total += 1
                continue
            rule_ids: set[str] = set()
            valid_items: list[Dict[str, Any]] = []
            valid = True
            for item in items:
                if not isinstance(item, Mapping):
                    valid = False
                    break
                rule_id = _safe_text(item.get("rule_id") or item.get("rule_code")).strip().upper()
                status = _safe_text(item.get("status")).strip()
                if not rule_id or rule_id in rule_ids or status not in _CUSTOMER_STATUSES:
                    valid = False
                    break
                rule_ids.add(rule_id)
                valid_items.append({"rule_id": rule_id, "status": status})
            if not valid:
                invalid_total += 1
                continue
            record = records_by_identity[identity]
            events.append(
                {
                    "root_job_id": root_job_id,
                    "identity": identity,
                    "department": _safe_text(record.get("department"), "未分科室").strip() or "未分科室",
                    "attending_physician": _safe_text(record.get("attending_physician")).strip(),
                    "finished_at": job["finished_at"],
                    "items": valid_items,
                }
            )
    return events, invalid_total
