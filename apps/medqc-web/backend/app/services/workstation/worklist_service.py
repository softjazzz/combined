"""Workstation V4 worklist and snapshot aggregation service."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Optional

from sqlalchemy import MetaData, Table, and_, desc, func, or_, select
from sqlalchemy.orm import Session

from ...database.connection import SessionLocal, engine
from ..luxian_0609_result_schema import RULE_SET_VERSION as LUXIAN_0609_RULE_SET_VERSION
from ..luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from .workflow_queue_state_service import default_workflow_queue_state_service


WORKFLOW_LABELS = {
    "frontpage": "首页质控",
    "coding": "编码质控",
    "settlement": "结算清单质控",
}

HOME_WORKFLOWS = ("frontpage", "coding", "settlement")

WORKFLOW_TO_QUEUE_WORKFLOW = {
    "frontpage": "frontpage_qc",
    "coding": "coding_qc",
    "settlement": "settlement_qc",
}

WORKFLOW_TO_LAUNCH = {
    "frontpage": {"launch_action": "qc_frontpage", "launch_stage": "frontpage_qc"},
    "coding": {"launch_action": "qc_coding", "launch_stage": "coding_qc"},
    "settlement": {"launch_action": "qc_settlement", "launch_stage": "settlement_qc"},
}

QUEUE_STATUS_FALLBACK = {
    "frontpage": "pending",
    "coding": "pending",
    "settlement": "pending",
}

QUEUE_STATUS_LABELS = {
    "frontpage": {
        "pending": "待首页质控",
        "running": "质控中",
        "succeeded": "质控完成",
        "failed": "质控失败",
        "unknown": "状态未知",
    },
    "coding": {
        "pending": "待编码质控",
        "running": "质控中",
        "succeeded": "质控完成",
        "failed": "质控失败",
        "unknown": "状态未知",
    },
    "settlement": {
        "pending": "待结算清单质控",
        "running": "质控中",
        "succeeded": "质控完成",
        "failed": "质控失败",
        "unknown": "状态未知",
    },
}

NOTIFICATION_TYPES = {
    "frontpage": "frontpage_qc",
    "coding": "coding_qc",
    "settlement": "settlement_qc",
}

BATCH_SUMMARY_SUFFIX = "_batch_summary"

SEVERITY_RANK = {
    "critical": 4,
    "error": 3,
    "warning": 2,
    "medium": 2,
    "info": 1,
    "low": 1,
}

TASK_STATUS_RANK = {
    "overdue": 0,
    "in_progress": 1,
    "pending": 2,
}

QUEUE_STATUS_SORT_RANK = {
    "running": 0,
    "failed": 1,
    "pending": 2,
    "succeeded": 3,
    "unknown": 4,
}

DEFAULT_SORT_FIELD = "discharge_date"
ALLOWED_SORT_FIELDS = {
    "patient_name",
    "department",
    "admission_date",
    "discharge_date",
    "latest_qc_time",
    "latest_qc_score",
    "active_defect_count",
    "notification_updated_at",
}


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _to_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _json_loads_if_needed(value: Any) -> Any:
    if isinstance(value, (dict, list)) or value is None:
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            return json.loads(text)
        except Exception:
            return value
    return value


def _serialize_scalar(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _serialize_scalar(_json_loads_if_needed(value)) for key, value in row.items()}


def _datetime_sort_number(value: Any) -> float:
    dt = _to_datetime(value)
    if dt is None:
        return 0.0
    try:
        return dt.timestamp()
    except (OverflowError, OSError, ValueError):
        return 0.0


@lru_cache(maxsize=32)
def _table_candidates(table_name: str, schemas: tuple[str, ...]) -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; workstation aggregation unavailable")

    metadata = MetaData()
    last_error: Exception | None = None
    for schema in schemas:
        try:
            return Table(table_name, metadata, schema=schema, autoload_with=engine)
        except Exception as exc:  # pragma: no cover - fallback path
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Unable to load table {table_name}")


def _table(table_name: str, *schemas: str) -> Table:
    return _table_candidates(table_name, tuple(schemas))


class WorklistIdentityAmbiguousError(ValueError):
    """同一就诊号对应多个病历身份，单键关联无法安全归属。"""


class WorkstationAggregationService:
    def __init__(self, session_factory: Any | None = None) -> None:
        self._session_factory = session_factory or SessionLocal
        if self._session_factory is None:
            raise RuntimeError("DATABASE_URL is not configured; workstation aggregation unavailable")

    def get_frontpage_worklist(
        self,
        *,
        department: Optional[str] = None,
        keyword: Optional[str] = None,
        queue_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        recipient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._get_worklist(
            workflow_type="frontpage",
            department=department,
            keyword=keyword,
            queue_status=queue_status,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            recipient_id=recipient_id,
        )

    def get_coding_worklist(
        self,
        *,
        department: Optional[str] = None,
        keyword: Optional[str] = None,
        queue_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        recipient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._get_worklist(
            workflow_type="coding",
            department=department,
            keyword=keyword,
            queue_status=queue_status,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            recipient_id=recipient_id,
        )

    def get_settlement_worklist(
        self,
        *,
        department: Optional[str] = None,
        keyword: Optional[str] = None,
        queue_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        recipient_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._get_worklist(
            workflow_type="settlement",
            department=department,
            keyword=keyword,
            queue_status=queue_status,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            recipient_id=recipient_id,
        )

    def get_frontpage_snapshot(self, visit_id: str, *, recipient_id: Optional[str] = None) -> Dict[str, Any]:
        return self._get_snapshot("frontpage", visit_id, recipient_id=recipient_id)

    def get_coding_snapshot(self, visit_id: str, *, recipient_id: Optional[str] = None) -> Dict[str, Any]:
        return self._get_snapshot("coding", visit_id, recipient_id=recipient_id)

    def get_settlement_snapshot(self, visit_id: str, *, recipient_id: Optional[str] = None) -> Dict[str, Any]:
        return self._get_snapshot("settlement", visit_id, recipient_id=recipient_id)

    def get_home(
        self,
        *,
        target_date: Optional[str] = None,
        department: Optional[str] = None,
        severity: Optional[str] = None,
        workflow_type: Optional[str] = None,
        keyword: Optional[str] = None,
        recipient_id: Optional[str] = None,
        hotspot_limit: int = 50,
        todo_limit: int = 12,
    ) -> Dict[str, Any]:
        session: Session = self._session_factory()
        try:
            date_value = self._parse_target_date(target_date)
            hotspots = self._build_home_hotspots(
                session,
                target_date=date_value,
                department=department,
                severity=severity,
                workflow_type=workflow_type,
                keyword=keyword,
                recipient_id=recipient_id,
                limit=hotspot_limit,
            )
            todo_items = self._build_home_todos(
                session,
                department=department,
                workflow_type=workflow_type,
                keyword=keyword,
                recipient_id=recipient_id,
                limit=todo_limit,
            )
            batch_summaries = self._load_batch_summary_notifications(
                session,
                target_date=date_value,
                recipient_id=recipient_id,
            )
            clinical_qc = self._build_luxian_0609_home_projection(
                session,
                department=department,
                keyword=keyword,
                priority_limit=hotspot_limit,
            )
            return {
                "date": date_value.strftime("%Y-%m-%d"),
                # 旧首页的前台/编码/结算统计仍保持兼容，不能混入全病历质控主口径。
                "kpis": self._build_home_kpis(hotspots, todo_items, batch_summaries),
                "hotspots": hotspots,
                "my_todo_summary": self._build_todo_summary(todo_items),
                "my_todo_items": todo_items,
                "batch_summaries": batch_summaries,
                # 首页科室筛选必须与全病历质控使用同一资料范围；保留旧字段名和
                # string[] 契约，不能再从兼容工作流的热点/待办反推科室。
                "department_options": clinical_qc["department_options"],
                "team_summary": self._build_team_summary(hotspots, todo_items),
                "scope": clinical_qc["scope"],
                "clinical_qc": clinical_qc,
            }
        finally:
            session.close()

    def get_luxian_0609_home(
        self,
        *,
        department: Optional[str] = None,
        keyword: Optional[str] = None,
        priority_limit: int = 20,
    ) -> Dict[str, Any]:
        """返回当前全病历质控首页所需的最小 Canonical 汇总。

        该入口不读取旧热点、待办或通知聚合。它们仍由 ``get_home`` 为兼容页面提供，
        但不能让当前质控首页为未展示的数据承担查询耗时。
        """

        session: Session = self._session_factory()
        try:
            clinical_qc = self._build_luxian_0609_home_projection(
                session,
                department=department,
                keyword=keyword,
                priority_limit=priority_limit,
            )
            return {
                "department_options": clinical_qc["department_options"],
                "scope": clinical_qc["scope"],
                "clinical_qc": clinical_qc,
            }
        finally:
            session.close()

    def get_luxian_0609_analytics(
        self,
        *,
        completed_from: Optional[datetime] = None,
        completed_to: Optional[datetime] = None,
        department: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """按已完成根任务的 Canonical Envelope 汇总泸县质控统计。

        统计事件的身份是 ``root_job_id + 三坐标``；病历数只按三坐标去重。
        该入口不读取 legacy items、Bundle 或结果文案，也不返回任何病历正文。
        """

        if completed_from and completed_to and completed_from > completed_to:
            raise ValueError("completed_from 不能晚于 completed_to")
        normalized_job_id = _safe_text(job_id).strip() or None
        session: Session = self._session_factory()
        try:
            records = self._load_luxian_home_records(session, department=None, keyword=None)
            records_by_identity = {
                (
                    _safe_text(record.get("institute_id")).strip(),
                    _safe_text(record.get("patient_id")).strip(),
                    _safe_text(record.get("visit_id")).strip(),
                ): record
                for record in records
                if all(
                    _safe_text(record.get(key)).strip()
                    for key in ("institute_id", "patient_id", "visit_id")
                )
            }
            if department:
                records_by_identity = {
                    identity: record
                    for identity, record in records_by_identity.items()
                    if _safe_text(record.get("department")).strip() == department
                }
            events, invalid_total = self._load_luxian_0609_analytics_events(
                session,
                records_by_identity=records_by_identity,
                completed_from=completed_from,
                completed_to=completed_to,
                job_id=normalized_job_id,
            )
        finally:
            session.close()

        status_order = (
            "non_compliant",
            "data_gap",
            "uncertain",
            "compliant",
            "not_applicable",
            "not_executed",
        )
        status_counts = {status: 0 for status in status_order}
        rule_counts: Dict[str, Dict[str, int]] = {}
        department_records: Dict[str, set[tuple[str, str, str]]] = {}
        department_non_compliant: Dict[str, set[tuple[str, str, str]]] = {}
        department_data_gap: Dict[str, set[tuple[str, str, str]]] = {}
        department_uncertain: Dict[str, set[tuple[str, str, str]]] = {}
        physician_records: Dict[str, set[tuple[str, str, str]]] = {}
        physician_non_compliant: Dict[str, set[tuple[str, str, str]]] = {}
        physician_data_gap: Dict[str, set[tuple[str, str, str]]] = {}
        physician_uncertain: Dict[str, set[tuple[str, str, str]]] = {}
        records_with_non_compliant: set[tuple[str, str, str]] = set()
        records_with_data_gap: set[tuple[str, str, str]] = set()
        event_identities: set[tuple[str, str, str, str]] = set()
        record_identities: set[tuple[str, str, str]] = set()
        time_buckets: Dict[str, int] = {}

        from ..luxian_0609_rule_master import load_luxian_0609_rule_master
        from ..sample_validation_rule_sets import (
            get_luxian_0609_customer_delivery_rule_ids,
        )

        rule_entries = tuple(load_luxian_0609_rule_master())
        all_rule_ids = {entry.rule_id for entry in rule_entries}
        customer_delivery_rule_ids = frozenset(
            get_luxian_0609_customer_delivery_rule_ids()
        )
        rule_names = {entry.rule_id: entry.title for entry in rule_entries}
        for event in events:
            identity = event["identity"]
            root_job_id = _safe_text(event.get("root_job_id")).strip()
            if not root_job_id or not isinstance(identity, tuple) or len(identity) != 3:
                invalid_total += 1
                continue
            event_key = (root_job_id, *identity)
            if event_key in event_identities:
                invalid_total += 1
                continue
            department_name = _safe_text(event.get("department"), "未分科室").strip() or "未分科室"
            event_statuses = set()
            validated_items: list[tuple[str, str]] = []
            valid_event = True
            delivered_rule_ids: set[str] = set()
            for item in event.get("items", []):
                if not isinstance(item, Mapping):
                    valid_event = False
                    break
                rule_id = _safe_text(item.get("rule_id") or item.get("rule_code")).strip().upper()
                status = _safe_text(item.get("status")).strip()
                if (
                    not rule_id
                    or rule_id not in all_rule_ids
                    or status not in status_counts
                ):
                    valid_event = False
                    break
                # 033/034/035/041/042 are explicitly outside customer delivery;
                # they must not inflate customer analytics, while unknown IDs
                # remain fail-closed above.
                if rule_id not in customer_delivery_rule_ids:
                    continue
                if rule_id in delivered_rule_ids:
                    valid_event = False
                    break
                delivered_rule_ids.add(rule_id)
                validated_items.append((rule_id, status))
            if not valid_event:
                invalid_total += 1
                continue
            event_identities.add(event_key)
            record_identities.add(identity)
            department_records.setdefault(department_name, set()).add(identity)
            physician_name = _safe_text(event.get("attending_physician")).strip() or "未登记主治医师"
            physician_records.setdefault(physician_name, set()).add(identity)
            for rule_id, status in validated_items:
                status_counts[status] += 1
                event_statuses.add(status)
                bucket = rule_counts.setdefault(
                    rule_id,
                    {
                        "non_compliant_count": 0,
                        "data_gap_count": 0,
                        "uncertain_count": 0,
                        "evaluated_count": 0,
                    },
                )
                bucket["evaluated_count"] += 1
                if status in {"non_compliant", "data_gap", "uncertain"}:
                    bucket[f"{status}_count"] += 1
            if "non_compliant" in event_statuses:
                records_with_non_compliant.add(identity)
                department_non_compliant.setdefault(department_name, set()).add(identity)
                physician_non_compliant.setdefault(physician_name, set()).add(identity)
            if "data_gap" in event_statuses:
                records_with_data_gap.add(identity)
                department_data_gap.setdefault(department_name, set()).add(identity)
                physician_data_gap.setdefault(physician_name, set()).add(identity)
            if "uncertain" in event_statuses:
                department_uncertain.setdefault(department_name, set()).add(identity)
                physician_uncertain.setdefault(physician_name, set()).add(identity)

            completed_at = _to_datetime(event.get("finished_at"))
            if completed_at is not None:
                bucket = completed_at.date().isoformat()
                time_buckets[bucket] = time_buckets.get(bucket, 0) + 1

        department_distribution = [
            {
                "department": name,
                "distinct_record_total": len(identities),
                "non_compliant_record_total": len(department_non_compliant.get(name, set())),
                "data_gap_record_total": len(department_data_gap.get(name, set())),
                "uncertain_record_total": len(department_uncertain.get(name, set())),
                "canonical_invalid_or_missing_total": 0,
            }
            for name, identities in department_records.items()
        ]
        department_distribution.sort(
            key=lambda item: (
                -item["non_compliant_record_total"],
                -item["data_gap_record_total"],
                item["department"],
            )
        )
        physician_distribution = [
            {
                "physician": name,
                "distinct_record_total": len(identities),
                "non_compliant_record_total": len(physician_non_compliant.get(name, set())),
                "data_gap_record_total": len(physician_data_gap.get(name, set())),
                "uncertain_record_total": len(physician_uncertain.get(name, set())),
            }
            for name, identities in physician_records.items()
        ]
        physician_distribution.sort(
            key=lambda item: (
                -item["non_compliant_record_total"],
                -item["data_gap_record_total"],
                -item["uncertain_record_total"],
                item["physician"],
            )
        )
        rule_distribution = [
            {
                "rule_id": rule_id,
                "rule_name": rule_names.get(rule_id, rule_id),
                **counts,
            }
            for rule_id, counts in rule_counts.items()
        ]
        rule_distribution.sort(
            key=lambda item: (
                -item["non_compliant_count"],
                -item["data_gap_count"],
                -item["uncertain_count"],
                item["rule_id"],
            )
        )
        time_series = (
            [
                {"bucket": bucket, "completed_event_total": count}
                for bucket, count in sorted(time_buckets.items())
            ]
            if len(time_buckets) >= 2
            else None
        )
        return {
            "scope": {
                "time_basis": "qc_completed_at",
                "completed_from": completed_from.isoformat() if completed_from else None,
                "completed_to": completed_to.isoformat() if completed_to else None,
                "department": department or None,
                "job_id": normalized_job_id,
                "scene": "final",
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                "hospital_scope": "all",
                "generated_at": datetime.now().astimezone().isoformat(),
            },
            "kpis": {
                "distinct_record_total": len(record_identities),
                "completed_event_total": len(event_identities),
                "records_with_non_compliant": len(records_with_non_compliant),
                "records_with_data_gap": len(records_with_data_gap),
                "canonical_invalid_or_missing_total": invalid_total,
            },
            "status_distribution": [
                {"status": status, "count": status_counts[status]}
                for status in status_order
            ],
            "department_distribution": department_distribution,
            "physician_distribution": physician_distribution,
            "rule_distribution": rule_distribution[:10],
            "completion_time_series": time_series,
            "data_health": {
                "canonical_invalid_or_missing_total": invalid_total,
            },
        }

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

    def _build_luxian_0609_home_projection(
        self,
        session: Session,
        *,
        department: Optional[str],
        keyword: Optional[str],
        priority_limit: int,
    ) -> Dict[str, Any]:
        """按病历池相同三坐标范围聚合全病历 Canonical 质控摘要。

        首页只消费 Task 2A 的完成态 Canonical 摘要；运行态和资料同步状态没有
        三坐标权威来源时保持 unknown，不能从旧工作流、文案或文书数量回填。
        """

        records = self._load_luxian_home_records(
            session,
            department=department,
            keyword=keyword,
        )
        record_refs = [
            {
                "institute_id": _safe_text(record.get("institute_id")).strip(),
                "patient_id": _safe_text(record.get("patient_id")).strip(),
                "visit_id": _safe_text(record.get("visit_id")).strip(),
            }
            for record in records
        ]
        summaries = self._load_luxian_0609_summaries(record_refs)

        canonical_status_counts: Dict[str, int] = {}
        technical_error_total = 0
        qc_completed_total = 0
        qc_pending_total = 0
        high_risk_review_total = 0
        last_successful_qc_at: Optional[str] = None
        priority_items: List[Dict[str, Any]] = []
        department_distribution: Dict[str, Dict[str, int]] = {}
        physician_distribution: Dict[str, Dict[str, int]] = {}

        for record in records:
            identity = (
                _safe_text(record.get("institute_id")).strip(),
                _safe_text(record.get("patient_id")).strip(),
                _safe_text(record.get("visit_id")).strip(),
            )
            summary = summaries.get(identity) or {"status": "not_run"}
            summary_status = _safe_text(summary.get("status"), "not_run").strip()
            department_name = _safe_text(record.get("department"), "未分科室").strip() or "未分科室"
            department_bucket = department_distribution.setdefault(
                department_name,
                {
                    "records_total": 0,
                    "completed_record_total": 0,
                    "high_risk_review_total": 0,
                    "data_gap_record_total": 0,
                    "uncertain_record_total": 0,
                    "defect_total": 0,
                },
            )
            department_bucket["records_total"] += 1
            physician_name = (
                _safe_text(record.get("attending_physician")).strip()
                or "未登记主治医师"
            )
            physician_bucket = physician_distribution.setdefault(
                physician_name,
                {
                    "records_total": 0,
                    "completed_record_total": 0,
                    "high_risk_review_total": 0,
                    "data_gap_record_total": 0,
                    "uncertain_record_total": 0,
                    "defect_total": 0,
                },
            )
            physician_bucket["records_total"] += 1

            if summary_status == "technical_error":
                technical_error_total += 1
                continue
            if summary_status != "ready":
                qc_pending_total += 1
                continue

            qc_completed_total += 1
            department_bucket["completed_record_total"] += 1
            physician_bucket["completed_record_total"] += 1
            raw_counts = summary.get("status_counts")
            status_counts = raw_counts if isinstance(raw_counts, dict) else {}
            normalized_counts: Dict[str, int] = {}
            for raw_status, raw_count in status_counts.items():
                try:
                    count = int(raw_count)
                except (TypeError, ValueError):
                    continue
                status = _safe_text(raw_status).strip()
                if count > 0 and status:
                    normalized_counts[status] = count
                    canonical_status_counts[status] = canonical_status_counts.get(status, 0) + count

            completed_at = _safe_text(summary.get("completed_at")).strip() or None
            if completed_at and (
                last_successful_qc_at is None
                or _datetime_sort_number(completed_at) > _datetime_sort_number(last_successful_qc_at)
            ):
                last_successful_qc_at = completed_at

            non_compliant_count = normalized_counts.get("non_compliant", 0)
            data_gap_count = normalized_counts.get("data_gap", 0)
            uncertain_count = normalized_counts.get("uncertain", 0)
            department_bucket["defect_total"] += non_compliant_count
            physician_bucket["defect_total"] += non_compliant_count
            if non_compliant_count:
                high_risk_review_total += 1
                department_bucket["high_risk_review_total"] += 1
                physician_bucket["high_risk_review_total"] += 1
            if data_gap_count:
                department_bucket["data_gap_record_total"] += 1
                physician_bucket["data_gap_record_total"] += 1
            if uncertain_count:
                department_bucket["uncertain_record_total"] += 1
                physician_bucket["uncertain_record_total"] += 1

            if non_compliant_count:
                priority_kind = "non_compliant"
                priority_rank = 0
            elif data_gap_count:
                priority_kind = "data_gap"
                priority_rank = 1
            elif uncertain_count:
                priority_kind = "uncertain"
                priority_rank = 2
            else:
                continue

            priority_items.append(
                {
                    "record_key": self._luxian_home_record_key(identity),
                    "institute_id": identity[0],
                    "patient_id": identity[1],
                    "visit_id": identity[2],
                    "patient_name": _safe_text(record.get("patient_name")),
                    "department": department_name,
                    "priority_kind": priority_kind,
                    "status_counts": normalized_counts,
                    "completed_at": completed_at,
                    "_priority_rank": priority_rank,
                }
            )

        priority_items.sort(
            key=lambda item: (
                int(item.get("_priority_rank", 9)),
                -int(dict(item.get("status_counts") or {}).get("non_compliant", 0)),
                -int(dict(item.get("status_counts") or {}).get("data_gap", 0)),
                -_datetime_sort_number(item.get("completed_at")),
                _safe_text(item.get("record_key")),
            )
        )
        for item in priority_items:
            item.pop("_priority_rank", None)

        generated_at = datetime.now().astimezone().isoformat()
        return {
            "scope": {
                "hospital_scope": "all",
                "department": department or None,
                "scene": "final",
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                "generated_at": generated_at,
            },
            "kpis": {
                "records_total": len(records),
                "qc_pending_total": qc_pending_total,
                "qc_completed_total": qc_completed_total,
                "high_risk_review_total": high_risk_review_total,
            },
            "data_health": {
                "source_sync_status": "unknown",
                "source_error_total": 0,
                "technical_error_total": technical_error_total,
                "running_task_total": None,
                "running_task_state": "unknown",
                "last_successful_qc_at": last_successful_qc_at,
            },
            "canonical_status_counts": dict(sorted(canonical_status_counts.items())),
            "priority_items": priority_items[: max(1, priority_limit)],
            "department_options": sorted(department_distribution),
            "department_distribution": [
                {
                    "department": name,
                    **counts,
                    "average_defect_count": round(
                        counts["defect_total"] / counts["completed_record_total"],
                        2,
                    )
                    if counts["completed_record_total"]
                    else 0,
                }
                for name, counts in sorted(
                    department_distribution.items(),
                    key=lambda item: (-item[1]["high_risk_review_total"], -item[1]["records_total"], item[0]),
                )
            ],
            "physician_distribution": [
                {
                    "physician": name,
                    **counts,
                    "average_defect_count": round(
                        counts["defect_total"] / counts["completed_record_total"],
                        2,
                    )
                    if counts["completed_record_total"]
                    else 0,
                }
                for name, counts in sorted(
                    physician_distribution.items(),
                    key=lambda item: (
                        -item[1]["high_risk_review_total"],
                        -item[1]["records_total"],
                        item[0],
                    ),
                )
            ],
            "rule_family_distribution": [],
            "trend": None,
            "comparison": None,
        }

    @staticmethod
    def _luxian_home_record_key(identity: tuple[str, str, str]) -> str:
        return json.dumps(list(identity), ensure_ascii=False, separators=(",", ":"))

    def _load_luxian_home_records(
        self,
        session: Session,
        *,
        department: Optional[str],
        keyword: Optional[str],
    ) -> List[Dict[str, str]]:
        """复用病历池的筛选器，仅读取三坐标齐全的真实 CDM 病历。"""

        from ..medical_records.query_service import (
            MedicalRecordFrontpage,
            _apply_workstation_filters,
            _workstation_department_expr,
            _workstation_discharge_join_condition,
            _workstation_discharge_summary_subquery,
        )

        discharge_summary = _workstation_discharge_summary_subquery(session)
        query = session.query(MedicalRecordFrontpage)
        if discharge_summary is not None:
            query = query.outerjoin(
                discharge_summary,
                _workstation_discharge_join_condition(discharge_summary),
            )
        query = _apply_workstation_filters(
            query,
            dept=department,
            doctor=None,
            keyword=keyword,
            start_date=None,
            end_date=None,
            date_field="visit",
            # 首页当前范围始终包含全院在院与出院病历；公共筛选器的住院状态
            # 参数必须显式传入，避免新增筛选合同后首页运行时漏参。
            hospital_status="all",
            sync_scope="all",
            include_department=True,
            include_doctor=False,
            discharge_summary=discharge_summary,
        )
        rows = query.with_entities(
            MedicalRecordFrontpage.institute_id,
            MedicalRecordFrontpage.patient_id,
            MedicalRecordFrontpage.visit_id,
            MedicalRecordFrontpage.name.label("patient_name"),
            MedicalRecordFrontpage.attending_physician_sign.label("attending_physician"),
            _workstation_department_expr(discharge_summary).label("department"),
        ).all()
        records_by_identity: Dict[tuple[str, str, str], Dict[str, str]] = {}
        for row in rows:
            identity = (
                _safe_text(row.institute_id).strip(),
                _safe_text(row.patient_id).strip(),
                _safe_text(row.visit_id).strip(),
            )
            if not all(identity):
                continue
            records_by_identity.setdefault(
                identity,
                {
                    "institute_id": identity[0],
                    "patient_id": identity[1],
                    "visit_id": identity[2],
                    "patient_name": _safe_text(row.patient_name).strip(),
                    "attending_physician": _safe_text(row.attending_physician).strip(),
                    "department": _safe_text(row.department).strip() or "未分科室",
                },
            )
        return list(records_by_identity.values())

    def _load_luxian_0609_summaries(
        self,
        record_refs: List[Dict[str, str]],
    ) -> Dict[tuple[str, str, str], Dict[str, Any]]:
        """只复用 Task 2A 的已完成 Canonical 批量摘要入口。"""

        from ..custom_qc_workspace_service import CustomQCWorkspaceService

        return CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
            record_refs=record_refs,
            session_factory=self._session_factory,
        )

    def get_home_hotspots(
        self,
        *,
        target_date: Optional[str] = None,
        department: Optional[str] = None,
        severity: Optional[str] = None,
        workflow_type: Optional[str] = None,
        keyword: Optional[str] = None,
        recipient_id: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        session: Session = self._session_factory()
        try:
            date_value = self._parse_target_date(target_date)
            items = self._build_home_hotspots(
                session,
                target_date=date_value,
                department=department,
                severity=severity,
                workflow_type=workflow_type,
                keyword=keyword,
                recipient_id=recipient_id,
                limit=limit,
            )
            return {
                "date": date_value.strftime("%Y-%m-%d"),
                "items": items,
                "total": len(items),
            }
        finally:
            session.close()

    def get_home_todos(
        self,
        *,
        department: Optional[str] = None,
        workflow_type: Optional[str] = None,
        keyword: Optional[str] = None,
        recipient_id: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        session: Session = self._session_factory()
        try:
            items = self._build_home_todos(
                session,
                department=department,
                workflow_type=workflow_type,
                keyword=keyword,
                recipient_id=recipient_id,
                limit=limit,
            )
            return {
                "summary": self._build_todo_summary(items),
                "items": items,
                "total": len(items),
            }
        finally:
            session.close()

    def _get_worklist(
        self,
        workflow_type: str,
        *,
        department: Optional[str],
        keyword: Optional[str],
        queue_status: Optional[str],
        page: int,
        page_size: int,
        sort_by: Optional[str],
        sort_order: Optional[str],
        recipient_id: Optional[str],
    ) -> Dict[str, Any]:
        session: Session = self._session_factory()
        try:
            items = self._build_worklist_items(
                session,
                workflow_type=workflow_type,
                department=department,
                keyword=keyword,
                recipient_id=recipient_id,
            )
            if not items:
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "departments": [{"name": "全部科室", "total": 0, "warningCount": 0}],
                }

            if queue_status:
                items = [
                    item
                    for item in items
                    if self._queue_status_matches_filter(
                        workflow_type,
                        _safe_text(item.get("queue_status"), "pending"),
                        queue_status,
                    )
                ]
            sorted_items = self._sort_items(items, sort_by=sort_by, sort_order=sort_order)
            total = len(sorted_items)
            paged_items = sorted_items[(page - 1) * page_size : page * page_size]

            return {
                "items": [self._strip_internal_fields(item) for item in paged_items],
                "total": total,
                "page": page,
                "page_size": page_size,
                "departments": self._build_departments(items),
            }
        finally:
            session.close()

    def _get_snapshot(self, workflow_type: str, visit_id: str, *, recipient_id: Optional[str]) -> Dict[str, Any]:
        session: Session = self._session_factory()
        try:
            base_rows = self._load_base_rows(session, workflow_type=workflow_type, department=None, keyword=None, visit_id=visit_id)
            if workflow_type == "settlement" and base_rows:
                identity_rows = self._load_base_rows(
                    session, workflow_type="frontpage", department=None, keyword=None, visit_id=visit_id
                )
            else:
                identity_rows = base_rows
            identities = {
                (row["institute_id"], row["patient_id"], row["visit_id"])
                for row in identity_rows
            }
            if len(identities) > 1:
                raise WorklistIdentityAmbiguousError(f"就诊号 {visit_id} 对应多个病历身份，需核实三坐标")
            if not base_rows:
                return {
                    "visit_id": visit_id,
                    "workflow_type": workflow_type,
                    "workflow_label": WORKFLOW_LABELS[workflow_type],
                    "identity_status": "unverified",
                    "queue_status": "unknown",
                    "queue_status_source": "identity_unverified",
                    "latest_qc_result": None,
                    "active_defects": [],
                    "latest_notification": None,
                    "recent_results": [],
                }

            base = base_rows[0]
            return {
                "visit_id": visit_id,
                "patient_id": base["patient_id"],
                "institute_id": base["institute_id"],
                "patient_name": base["patient_name"],
                "patient_age": base.get("patient_age"),
                "patient_sex": base.get("patient_sex"),
                "patient_gender": base.get("patient_sex"),
                "department": base["department"],
                "workflow_type": workflow_type,
                "workflow_label": WORKFLOW_LABELS[workflow_type],
                "identity_status": "unverified",
                "queue_status": "unknown",
                "queue_status_source": "identity_unverified",
                "latest_qc_result": None,
                "active_defects": [],
                "latest_notification": None,
                "recent_results": [],
            }
        finally:
            session.close()

    def _build_worklist_items(
        self,
        session: Session,
        *,
        workflow_type: str,
        department: Optional[str] = None,
        keyword: Optional[str] = None,
        recipient_id: Optional[str] = None,
        visit_ids: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        base_rows = self._load_base_rows(
            session,
            workflow_type=workflow_type,
            department=department,
            keyword=keyword,
            visit_ids=visit_ids,
        )
        if not base_rows:
            return []

        identity_rows = base_rows
        if department or keyword or workflow_type == "settlement":
            identity_rows = self._load_base_rows(
                session,
                workflow_type="frontpage",
                department=None,
                keyword=None,
                visit_ids={row["visit_id"] for row in base_rows},
            )
        identities_by_visit: Dict[str, set[tuple[str, str, str]]] = {}
        for row in identity_rows:
            visit_id = _safe_text(row["visit_id"])
            identities_by_visit.setdefault(visit_id, set()).add(
                (_safe_text(row["institute_id"]), _safe_text(row["patient_id"]), visit_id)
            )
        ambiguous_visit_ids = {
            visit_id for visit_id, identities in identities_by_visit.items() if len(identities) > 1
        }
        items: List[Dict[str, Any]] = []
        for row in base_rows:
            visit_id = row["visit_id"]
            identity_ambiguous = visit_id in ambiguous_visit_ids
            status_source = "identity_ambiguous" if identity_ambiguous else "identity_unverified"

            launch = WORKFLOW_TO_LAUNCH.get(workflow_type, {})
            items.append(
                {
                    "visit_id": visit_id,
                    "record_id": f"{workflow_type}::{visit_id}",
                    "patient_id": row["patient_id"],
                    "institute_id": row["institute_id"],
                    "patient_name": row["patient_name"],
                    "patient_age": row.get("patient_age"),
                    "patient_sex": row.get("patient_sex"),
                    "patient_gender": row.get("patient_sex"),
                    "department": row["department"],
                    "admission_date": row.get("admission_date"),
                    "discharge_date": row.get("discharge_date"),
                    "workflow_type": workflow_type,
                    "identity_status": "ambiguous" if identity_ambiguous else "unverified",
                    "queue_status": "unknown",
                    "queue_status_source": status_source,
                    "latest_qc_result_id": None,
                    "latest_qc_score": None,
                    "latest_qc_grade": None,
                    "latest_qc_time": None,
                    "active_defect_count": 0,
                    "top_severity": "info",
                    "risk_reason": "身份待核实" if identity_ambiguous else "历史质控归属未核实",
                    "notification_status": "none",
                    "notification_updated_at": None,
                    "latest_notification_id": None,
                    "queue_updated_at": None,
                    "launch_action": None if identity_ambiguous else launch.get("launch_action"),
                    "launch_stage": None if identity_ambiguous else launch.get("launch_stage"),
                }
            )
        return items

    def _parse_target_date(self, target_date: Optional[str]) -> datetime:
        if target_date:
            try:
                return datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError("date 格式必须为 YYYY-MM-DD") from exc
        return datetime.now()

    def _build_home_hotspots(
        self,
        session: Session,
        *,
        target_date: datetime,
        department: Optional[str],
        severity: Optional[str],
        workflow_type: Optional[str],
        keyword: Optional[str],
        recipient_id: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        rows = self._load_notifications_for_date(
            session,
            target_date=target_date,
            recipient_id=recipient_id,
        )
        grouped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            notif_type = _safe_text(row.get("type")).lower()
            if notif_type.endswith(BATCH_SUMMARY_SUFFIX):
                continue
            workflow_context = self._infer_workflow_context(notif_type, _safe_text(row.get("record_id")))
            current_workflow = workflow_context.get("workflow_type")
            visit_id = workflow_context.get("visit_id")
            if not current_workflow or not visit_id:
                continue
            if workflow_type and current_workflow != workflow_type:
                continue
            item_department = "未分科室"
            if department and item_department != department:
                continue
            item_severity = _safe_text(row.get("severity") or row.get("level"), "info").lower()
            if severity and severity != "all" and item_severity != severity:
                continue

            key = f"{current_workflow}|{item_severity}|{item_department}"
            current = grouped.get(key)
            created_at = _safe_text(row.get("created_at"))
            if current is None:
                current = {
                    "id": key,
                    "record_id": "",
                    "visit_id": "",
                    "patient_id": "",
                    "patient_name": "",
                    "department": "未分科室",
                    "workflow_type": current_workflow,
                    "severity": item_severity,
                    "title": "历史通知归属待核实",
                    "summary": "仅显示匿名汇总，暂不可按病历处理",
                    "occurrence_count": 0,
                    "unread_count": 0,
                    "active_defect_count": 0,
                    "latest_qc_score": None,
                    "latest_qc_grade": None,
                    "queue_status": "unknown",
                    "queue_status_source": "identity_unverified",
                    "identity_status": "unverified",
                    "latest_created_at": created_at,
                    "latest_notification_id": None,
                    "launch_action": None,
                    "launch_stage": None,
                }
                grouped[key] = current
            current["occurrence_count"] += 1
            if not bool(row.get("is_read")):
                current["unread_count"] += 1
            current_time = _to_datetime(current.get("latest_created_at"))
            next_time = _to_datetime(created_at)
            if next_time and (current_time is None or next_time > current_time):
                current["latest_created_at"] = created_at
        result: List[Dict[str, Any]] = []
        for item in grouped.values():
            result.append(item)

        result.sort(
            key=lambda item: (
                int(item.get("unread_count") or 0),
                SEVERITY_RANK.get(_safe_text(item.get("severity"), "info").lower(), 1),
                int(item.get("occurrence_count") or 0),
                _datetime_sort_number(item.get("latest_created_at")),
            ),
            reverse=True,
        )
        return result[: max(1, limit)]

    def _build_home_todos(
        self,
        session: Session,
        *,
        department: Optional[str],
        workflow_type: Optional[str],
        keyword: Optional[str],
        recipient_id: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        workflows = [workflow_type] if workflow_type in HOME_WORKFLOWS else list(HOME_WORKFLOWS)
        base_items: List[Dict[str, Any]] = []
        for name in workflows:
            base_items.extend(
                self._build_worklist_items(
                    session,
                    workflow_type=name,
                    department=department,
                    keyword=keyword,
                    recipient_id=recipient_id,
                )
            )

        todo_items: List[Dict[str, Any]] = []
        for item in base_items:
            queue_status = _safe_text(item.get("queue_status"), "pending")
            has_unread = _safe_text(item.get("notification_status")) == "unread"
            has_defects = int(item.get("active_defect_count") or 0) > 0
            needs_identity_review = _safe_text(item.get("identity_status")) in {"ambiguous", "unverified"}
            is_queue_attention = queue_status in {"failed", "running"}
            is_pending_entry = (
                queue_status == "pending"
                and (
                    has_unread
                    or has_defects
                    or not item.get("latest_qc_result_id")
                )
            )
            has_attention = (
                is_queue_attention
                or is_pending_entry
                or has_defects
                or has_unread
                or needs_identity_review
            )
            if not has_attention:
                continue
            task_status = self._resolve_todo_task_status(item)
            due_at = (
                item.get("notification_updated_at")
                or item.get("queue_updated_at")
                or item.get("latest_qc_time")
                or item.get("discharge_date")
            )
            workflow_name = _safe_text(item.get("workflow_type"))
            todo_items.append(
                {
                    "id": f"todo::{workflow_name}::{item.get('institute_id')}::{item.get('patient_id')}::{item.get('visit_id')}",
                    "todo_type": workflow_name,
                    "record_id": item.get("record_id"),
                    "visit_id": item.get("visit_id"),
                    "patient_id": item.get("patient_id"),
                    "institute_id": item.get("institute_id"),
                    "patient_name": item.get("patient_name"),
                    "patient_age": item.get("patient_age"),
                    "patient_sex": item.get("patient_sex"),
                    "patient_gender": item.get("patient_gender"),
                    "department": item.get("department"),
                    "workflow_type": workflow_name,
                    "identity_status": item.get("identity_status"),
                    "task_status": task_status,
                    "priority": self._resolve_todo_priority(item),
                    "due_at": due_at,
                    "active_defect_count": int(item.get("active_defect_count") or 0),
                    "summary": item.get("risk_reason") or f"待处理{WORKFLOW_LABELS.get(workflow_name, '任务')}",
                    "notification_status": item.get("notification_status"),
                    "queue_status": item.get("queue_status"),
                    "queue_status_source": item.get("queue_status_source"),
                    "latest_qc_score": item.get("latest_qc_score"),
                    "latest_qc_grade": item.get("latest_qc_grade"),
                    "launch_action": item.get("launch_action"),
                    "launch_stage": item.get("launch_stage"),
                }
            )

        deduped_todos: Dict[str, Dict[str, Any]] = {}
        for item in todo_items:
            dedupe_key = item["id"]
            current = deduped_todos.get(dedupe_key)
            if current is None or self._should_replace_todo_item(item, current):
                deduped_todos[dedupe_key] = item

        final_todos = list(deduped_todos.values())
        final_todos.sort(
            key=lambda item: (
                TASK_STATUS_RANK.get(_safe_text(item.get("task_status"), "pending"), 9),
                self._todo_priority_rank(_safe_text(item.get("priority"), "normal")),
                -_datetime_sort_number(item.get("due_at")),
                -int(item.get("active_defect_count") or 0),
            )
        )
        return final_todos[: max(1, limit)]

    def _build_home_kpis(
        self,
        hotspots: List[Dict[str, Any]],
        todo_items: List[Dict[str, Any]],
        batch_summaries: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        return {
            "hotspot_total": len(hotspots),
            "high_risk_total": sum(
                1 for item in hotspots if SEVERITY_RANK.get(_safe_text(item.get("severity"), "info").lower(), 1) >= 3
            ),
            "my_pending_total": sum(1 for item in todo_items if _safe_text(item.get("task_status")) == "pending"),
            "my_in_progress_total": sum(1 for item in todo_items if _safe_text(item.get("task_status")) == "in_progress"),
            "my_overdue_total": sum(1 for item in todo_items if _safe_text(item.get("task_status")) == "overdue"),
            "batch_summary_total": len(batch_summaries),
        }

    def _build_todo_summary(self, todo_items: List[Dict[str, Any]]) -> Dict[str, int]:
        return {
            "pending_total": sum(1 for item in todo_items if _safe_text(item.get("task_status")) == "pending"),
            "in_progress_total": sum(1 for item in todo_items if _safe_text(item.get("task_status")) == "in_progress"),
            "overdue_total": sum(1 for item in todo_items if _safe_text(item.get("task_status")) == "overdue"),
            "high_priority_total": sum(
                1 for item in todo_items if _safe_text(item.get("priority")) in {"critical", "high"}
            ),
        }

    def _build_home_departments(
        self,
        hotspots: List[Dict[str, Any]],
        todo_items: List[Dict[str, Any]],
    ) -> List[str]:
        departments = {
            _safe_text(item.get("department")).strip()
            for item in [*hotspots, *todo_items]
            if _safe_text(item.get("department")).strip()
        }
        return sorted(departments)

    def _build_team_summary(
        self,
        hotspots: List[Dict[str, Any]],
        todo_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        department_risk: Dict[str, int] = {}
        workflow_status: Dict[str, Dict[str, int]] = {}
        for item in hotspots:
            department = _safe_text(item.get("department"), "未分科室")
            department_risk[department] = department_risk.get(department, 0) + 1
        for item in todo_items:
            workflow_name = _safe_text(item.get("workflow_type"), "unknown")
            task_status = _safe_text(item.get("task_status"), "pending")
            bucket = workflow_status.setdefault(workflow_name, {})
            bucket[task_status] = bucket.get(task_status, 0) + 1
        return {
            "department_risk_distribution": [
                {"department": key, "count": value}
                for key, value in sorted(department_risk.items(), key=lambda pair: (-pair[1], pair[0]))
            ],
            "workflow_status_distribution": [
                {"workflow_type": key, **value}
                for key, value in sorted(workflow_status.items(), key=lambda pair: pair[0])
            ],
        }

    def _resolve_todo_task_status(self, item: Dict[str, Any]) -> str:
        queue_status = _safe_text(item.get("queue_status"), "pending")
        if queue_status == "failed":
            return "overdue"
        if queue_status == "running":
            return "in_progress"
        due_at = item.get("notification_updated_at") or item.get("queue_updated_at")
        if due_at and self._is_overdue(due_at):
            return "overdue"
        return "pending"

    def _resolve_todo_priority(self, item: Dict[str, Any]) -> str:
        queue_status = _safe_text(item.get("queue_status"), "pending")
        if queue_status == "failed":
            return "critical"
        top_severity = _safe_text(item.get("top_severity"), "info").lower()
        if SEVERITY_RANK.get(top_severity, 1) >= 3:
            return "high"
        if queue_status == "running":
            return "medium"
        return "normal"

    def _todo_priority_rank(self, priority: str) -> int:
        mapping = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "normal": 3,
        }
        return mapping.get(priority, 4)

    def _should_replace_todo_item(self, candidate: Dict[str, Any], current: Dict[str, Any]) -> bool:
        candidate_status = TASK_STATUS_RANK.get(_safe_text(candidate.get("task_status"), "pending"), 9)
        current_status = TASK_STATUS_RANK.get(_safe_text(current.get("task_status"), "pending"), 9)
        if candidate_status != current_status:
            return candidate_status < current_status

        candidate_priority = self._todo_priority_rank(_safe_text(candidate.get("priority"), "normal"))
        current_priority = self._todo_priority_rank(_safe_text(current.get("priority"), "normal"))
        if candidate_priority != current_priority:
            return candidate_priority < current_priority

        candidate_unread = 1 if _safe_text(candidate.get("notification_status")) == "unread" else 0
        current_unread = 1 if _safe_text(current.get("notification_status")) == "unread" else 0
        if candidate_unread != current_unread:
            return candidate_unread > current_unread

        return _datetime_sort_number(candidate.get("due_at")) > _datetime_sort_number(current.get("due_at"))

    def _is_overdue(self, value: Any) -> bool:
        dt = _to_datetime(value)
        if dt is None:
            return False
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt <= datetime.now() - timedelta(days=1)

    def _load_notifications_for_date(
        self,
        session: Session,
        *,
        target_date: datetime,
        recipient_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        notifications = _table("notifications", "qc", "public")
        start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(days=1)
        stmt = (
            select(notifications)
            .where(
                and_(
                    notifications.c.created_at >= start_dt,
                    notifications.c.created_at < end_dt,
                )
            )
            .order_by(desc(notifications.c.created_at))
        )
        if recipient_id:
            stmt = stmt.where(notifications.c.recipient_id == recipient_id)
        rows = session.execute(stmt).mappings().all()
        return [_serialize_row(dict(row)) for row in rows]

    def _load_batch_summary_notifications(
        self,
        session: Session,
        *,
        target_date: datetime,
        recipient_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        rows = self._load_notifications_for_date(
            session,
            target_date=target_date,
            recipient_id=recipient_id,
        )
        result: List[Dict[str, Any]] = []
        for row in rows:
            notif_type = _safe_text(row.get("type")).lower()
            if not notif_type.endswith(BATCH_SUMMARY_SUFFIX):
                continue
            workflow_context = self._infer_workflow_context(notif_type, _safe_text(row.get("record_id")))
            result.append(
                {
                    "id": _safe_text(row.get("id")),
                    "title": _safe_text(row.get("title")),
                    "content": _safe_text(row.get("content") or row.get("message")),
                    "created_at": _safe_text(row.get("created_at")),
                    "is_read": bool(row.get("is_read")),
                    "type": notif_type,
                    "workflow_type": workflow_context.get("workflow_type") or "general",
                }
            )
        return result

    def _infer_workflow_context(self, notification_type: str, record_id: str) -> Dict[str, str]:
        normalized_type = _safe_text(notification_type).lower()
        normalized_record_id = _safe_text(record_id)
        if normalized_record_id.startswith("frontpage::"):
            visit_id = self._visit_id_from_record_id(normalized_record_id)
            return {"workflow_type": "frontpage", "visit_id": visit_id, **WORKFLOW_TO_LAUNCH["frontpage"]}
        if normalized_record_id.startswith("coding::"):
            visit_id = self._visit_id_from_record_id(normalized_record_id)
            return {"workflow_type": "coding", "visit_id": visit_id, **WORKFLOW_TO_LAUNCH["coding"]}
        if normalized_record_id.startswith("settlement::"):
            visit_id = self._visit_id_from_record_id(normalized_record_id)
            return {"workflow_type": "settlement", "visit_id": visit_id, **WORKFLOW_TO_LAUNCH["settlement"]}
        if "coding" in normalized_type:
            return {"workflow_type": "coding", "visit_id": self._visit_id_from_record_id(normalized_record_id), **WORKFLOW_TO_LAUNCH["coding"]}
        if "settlement" in normalized_type or "cost" in normalized_type:
            return {"workflow_type": "settlement", "visit_id": self._visit_id_from_record_id(normalized_record_id), **WORKFLOW_TO_LAUNCH["settlement"]}
        if "frontpage" in normalized_type:
            return {"workflow_type": "frontpage", "visit_id": self._visit_id_from_record_id(normalized_record_id), **WORKFLOW_TO_LAUNCH["frontpage"]}
        return {"workflow_type": "", "visit_id": "", "launch_action": "", "launch_stage": ""}

    def _extract_department_from_notification(self, item: Dict[str, Any]) -> str:
        for key in ("department", "dept_name", "department_name"):
            value = _safe_text(item.get(key)).strip()
            if value:
                return value
        metadata = _json_loads_if_needed(item.get("metadata"))
        if isinstance(metadata, dict):
            for key in ("department", "dept_name", "department_name"):
                value = _safe_text(metadata.get(key)).strip()
                if value:
                    return value
        payload = _json_loads_if_needed(item.get("payload"))
        if isinstance(payload, dict):
            for key in ("department", "dept_name", "department_name"):
                value = _safe_text(payload.get(key)).strip()
                if value:
                    return value
        return "未分科室"

    def _load_base_rows(
        self,
        session: Session,
        *,
        workflow_type: str,
        department: Optional[str],
        keyword: Optional[str],
        visit_id: Optional[str] = None,
        visit_ids: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        mr = _table("mr", "cdm", "public")
        columns = [
            mr.c.institute_id.label("institute_id"),
            mr.c.patient_id.label("patient_id"),
            mr.c.visit_id.label("visit_id"),
            mr.c.name.label("patient_name"),
            func.coalesce(mr.c.age, mr.c.age_year, mr.c.age_month).label("patient_age"),
            mr.c.sex.label("patient_sex"),
            func.coalesce(mr.c.discharge_dept_name, mr.c.admission_dept_name, "").label("department"),
            mr.c.admission_datetime.label("admission_date"),
            mr.c.discharge_datetime.label("discharge_date"),
            mr.c.mr_no.label("mr_no"),
            mr.c.inpat_no.label("inpat_no"),
        ]
        stmt = select(*columns)

        if workflow_type == "settlement":
            settlement = _table("medical_insurance_settlement", "cdm", "public")
            stmt = stmt.add_columns(
                settlement.c.medinsur_serial_no.label("medinsur_serial_no"),
                settlement.c.settlement_status.label("settlement_status"),
            ).select_from(
                mr.join(
                    settlement,
                    and_(
                        mr.c.institute_id == settlement.c.institute_id,
                        mr.c.patient_id == settlement.c.patient_id,
                        mr.c.visit_id == settlement.c.visit_id,
                    ),
                )
            )

        if department:
            stmt = stmt.where(
                func.coalesce(mr.c.discharge_dept_name, mr.c.admission_dept_name, "") == department
            )
        if keyword:
            like_value = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    mr.c.name.ilike(like_value),
                    mr.c.mr_no.ilike(like_value),
                    mr.c.inpat_no.ilike(like_value),
                    mr.c.visit_id.ilike(like_value),
                )
            )
        if visit_id:
            stmt = stmt.where(mr.c.visit_id == visit_id)
        if visit_ids:
            normalized_visit_ids = [str(value).strip() for value in visit_ids if str(value).strip()]
            if normalized_visit_ids:
                stmt = stmt.where(mr.c.visit_id.in_(normalized_visit_ids))

        stmt = stmt.order_by(desc(mr.c.discharge_datetime), desc(mr.c.admission_datetime))
        rows = session.execute(stmt).mappings().all()

        deduped: Dict[tuple[str, str, str], Dict[str, Any]] = {}
        for row in rows:
            data = _serialize_row(dict(row))
            identity = tuple(_safe_text(data[key]) for key in ("institute_id", "patient_id", "visit_id"))
            deduped.setdefault(identity, data)
        return list(deduped.values())

    def _load_latest_results(self, session: Session, workflow_type: str, visit_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        qc_results = _table("qc_results", "qc", "public")
        record_ids = [f"{workflow_type}::{visit_id}" for visit_id in visit_ids]
        if not record_ids:
            return {}
        stmt = (
            select(qc_results)
            .where(qc_results.c.record_id.in_(record_ids))
            .order_by(desc(qc_results.c.analysis_date), desc(qc_results.c.created_at))
        )
        rows = session.execute(stmt).mappings().all()
        latest: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            data = _serialize_row(dict(row))
            visit_id = _safe_text(data.get("visit_id")) or self._visit_id_from_record_id(_safe_text(data.get("record_id")))
            if visit_id and visit_id not in latest:
                latest[visit_id] = data
        return latest

    def _load_result_history(
        self,
        session: Session,
        workflow_type: str,
        visit_id: str,
        *,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        qc_results = _table("qc_results", "qc", "public")
        record_id = f"{workflow_type}::{visit_id}"
        stmt = (
            select(qc_results)
            .where(qc_results.c.record_id == record_id)
            .order_by(desc(qc_results.c.analysis_date), desc(qc_results.c.created_at))
            .limit(limit)
        )
        rows = session.execute(stmt).mappings().all()
        return [_serialize_row(dict(row)) for row in rows]

    def _load_active_defects(
        self,
        session: Session,
        workflow_type: str,
        visit_ids: Iterable[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        defects = _table("qc_defects", "qc", "public")
        record_ids = [f"{workflow_type}::{visit_id}" for visit_id in visit_ids]
        if not record_ids:
            return {}
        stmt = (
            select(defects)
            .where(
                and_(
                    defects.c.record_id.in_(record_ids),
                    defects.c.status != "completed",
                )
            )
            .order_by(desc(defects.c.updated_at), desc(defects.c.created_at))
        )
        rows = session.execute(stmt).mappings().all()
        result: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            data = _serialize_row(dict(row))
            visit_id = self._visit_id_from_record_id(_safe_text(data.get("record_id")))
            if not visit_id:
                continue
            result.setdefault(visit_id, []).append(data)

        for visit_id, items in result.items():
            items.sort(key=self._defect_sort_key)
        return result

    def _load_latest_notifications(
        self,
        session: Session,
        workflow_type: str,
        visit_ids: Iterable[str],
        *,
        recipient_id: Optional[str],
    ) -> Dict[str, Dict[str, Any]]:
        notifications = _table("notifications", "qc", "public")
        record_ids = [f"{workflow_type}::{visit_id}" for visit_id in visit_ids]
        if not record_ids:
            return {}
        stmt = (
            select(notifications)
            .where(
                and_(
                    notifications.c.record_id.in_(record_ids),
                    notifications.c.type == NOTIFICATION_TYPES[workflow_type],
                )
            )
            .order_by(desc(notifications.c.created_at))
        )
        if recipient_id:
            stmt = stmt.where(notifications.c.recipient_id == recipient_id)
        rows = session.execute(stmt).mappings().all()
        latest: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            data = _serialize_row(dict(row))
            visit_id = self._visit_id_from_record_id(_safe_text(data.get("record_id")))
            if visit_id and visit_id not in latest:
                latest[visit_id] = data
        return latest

    def _load_queue_state_map(self, *, workflow_type: str, visit_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        queue_workflow = WORKFLOW_TO_QUEUE_WORKFLOW.get(workflow_type)
        if not queue_workflow:
            return {}
        visit_list = [str(v).strip() for v in visit_ids if str(v).strip()]
        if not visit_list:
            return {}

        states = default_workflow_queue_state_service.get_state_map(
            workflow_type=queue_workflow,
            visit_ids=visit_list,
        )
        if states:
            return states

        try:
            default_workflow_queue_state_service.backfill_from_existing_data(
                workflow_type=queue_workflow,
                visit_ids=visit_list,
            )
            return default_workflow_queue_state_service.get_state_map(
                workflow_type=queue_workflow,
                visit_ids=visit_list,
            )
        except Exception:
            return states

    def _resolve_queue_state(
        self,
        *,
        workflow_type: str,
        queue_state: Optional[Dict[str, Any]],
    ) -> tuple[str, str, Optional[str]]:
        fallback = QUEUE_STATUS_FALLBACK.get(workflow_type, "pending")
        if not queue_state:
            return fallback, "backfill", None

        status = _safe_text(queue_state.get("queue_status"), fallback).strip().lower() or fallback
        source = _safe_text(queue_state.get("queue_status_source"), "backfill").strip().lower() or "backfill"
        if status not in QUEUE_STATUS_SORT_RANK:
            status = "unknown"
        if source not in {"backfill", "runtime"}:
            source = "backfill"
        updated_at = queue_state.get("updated_at")
        updated_text = updated_at.isoformat() if isinstance(updated_at, datetime) else _safe_text(updated_at) or None
        return status, source, updated_text

    def _queue_status_matches_filter(self, workflow_type: str, status_code: str, raw_filter: str) -> bool:
        expected = _safe_text(raw_filter).strip()
        if not expected:
            return True
        if expected == status_code:
            return True
        label = QUEUE_STATUS_LABELS.get(workflow_type, {}).get(status_code, "")
        return expected == label

    def _build_risk_reason(self, defects: List[Dict[str, Any]]) -> str:
        if not defects:
            return ""
        top = sorted(defects, key=self._defect_sort_key)[:3]
        first = top[0]
        rule_name = _safe_text(first.get("rule_name")).strip()
        description = _safe_text(first.get("description")).strip()
        lead = f"{rule_name}: {description}".strip(": ").strip()
        if len(top) == 1:
            return lead
        return f"{lead} 等 {len(top)} 条问题"

    def _top_severity(self, defects: List[Dict[str, Any]]) -> str:
        if not defects:
            return "info"
        ordered = sorted(defects, key=self._defect_sort_key)
        return _safe_text(ordered[0].get("severity"), "info")

    def _defect_sort_key(self, defect: Dict[str, Any]) -> tuple[int, float]:
        severity = _safe_text(defect.get("severity"), "info").lower()
        updated_sort = _datetime_sort_number(defect.get("updated_at")) or _datetime_sort_number(defect.get("created_at"))
        return (-SEVERITY_RANK.get(severity, 1), -updated_sort)

    def _sort_items(
        self,
        items: List[Dict[str, Any]],
        *,
        sort_by: Optional[str],
        sort_order: Optional[str],
    ) -> List[Dict[str, Any]]:
        # Default queue order applies only when caller did not explicitly pass sort params.
        if sort_by is None and sort_order is None:
            def default_sort_key(item: Dict[str, Any]) -> tuple[int, float]:
                status = _safe_text(item.get("queue_status"), "unknown")
                rank = QUEUE_STATUS_SORT_RANK.get(status, 5)
                updated_sort = _datetime_sort_number(item.get("queue_updated_at"))
                return rank, -updated_sort

            return sorted(items, key=default_sort_key)

        field = sort_by if sort_by in ALLOWED_SORT_FIELDS else DEFAULT_SORT_FIELD
        reverse = str(sort_order).lower() != "asc"

        def sort_key(item: Dict[str, Any]) -> Any:
            value = item.get(field)
            if field in {"admission_date", "discharge_date", "latest_qc_time", "notification_updated_at"}:
                return _datetime_sort_number(value)
            if field == "active_defect_count":
                return int(item.get(field) or 0)
            if field == "latest_qc_score":
                raw = item.get(field)
                return float(raw or 0)
            return _safe_text(value).lower()

        return sorted(items, key=sort_key, reverse=reverse)

    def _build_departments(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        dept_map: Dict[str, Dict[str, Any]] = {}
        warning_total = 0
        for item in items:
            name = _safe_text(item.get("department"), "未分科室") or "未分科室"
            bucket = dept_map.setdefault(name, {"name": name, "total": 0, "warningCount": 0})
            bucket["total"] += 1
            if int(item.get("active_defect_count") or 0) > 0:
                bucket["warningCount"] += 1
                warning_total += 1
        ordered = sorted(dept_map.values(), key=lambda item: (-int(item["total"]), item["name"]))
        return [{"name": "全部科室", "total": len(items), "warningCount": warning_total}, *ordered]

    def _visit_id_from_record_id(self, record_id: str) -> str:
        if "::" not in record_id:
            return ""
        return record_id.split("::", 1)[1]

    def _strip_internal_fields(self, item: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(item)
        payload.pop("queue_updated_at", None)
        return payload


default_workstation_aggregation_service = WorkstationAggregationService()
