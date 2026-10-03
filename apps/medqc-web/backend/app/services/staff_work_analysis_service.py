"""质控员工作分析：同一事件集合驱动汇总、人员下钻和导出。"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.defect_rectification import DefectRectification, DefectRectificationEvent
from ..database.models.qc import (
    QCAppeal,
    QCAppealReview,
    QCDefect,
    QCDefectHistory,
    QCRecordReview,
    QCTask,
    QCTaskRecord,
)
from .case_operation_timeline_service import _display_names
from .manual_defect_review_service import (
    _manual_scope,
    _task_identity as _manual_task_identity,
)
from .medical_records.query_service import load_scoring_departments
from .performance_ranking_service import (
    HOSPITAL_TIMEZONE,
    SCENE_ALL,
    PerformanceRankingInvalid,
    RankingWindow,
    compute_window,
)
from .record_review_defect_snapshot_service import (
    SOURCE_KEYS as _SNAPSHOT_SOURCE_FIELDS,
    DefectSnapshotInvalid,
    validate_snapshot,
)

COUNT_FIELDS = (
    "record_review_count", "reviewed_case_count", "rechecked_case_count", "initial_count", "recheck_count",
    "manual_defect_created_count", "manual_review_approved_count",
    "manual_review_rejected_count", "appeal_approved_count", "appeal_rejected_count",
    "urged_defect_count", "confirmed_defect_count",
)
APPEAL_COUNT_FIELDS = ("appeal_approved_count", "appeal_rejected_count")
DETAIL_METRICS = frozenset(COUNT_FIELDS)
MAX_EXPORT_ROWS = 5_000
MAX_DETAIL_PAGE_SIZE = 100
FILTER_NOT_ATTRIBUTABLE = "filter_not_attributable"
DEPARTMENT_SOURCE_UNAVAILABLE = "department_source_unavailable"
TASK_SOURCE_UNAVAILABLE = "task_source_unavailable"
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")
_COVERAGE_FIELDS = (
    "initial_review_count", "covered_initial_review_count",
    "missing_initial_review_count", "known_defect_count",
)


class StaffWorkAnalysisInvalid(ValueError):
    """请求参数无效。"""


class StaffWorkAnalysisUnavailable(RuntimeError):
    """统计来源不可用或事件归属不可信。"""


class StaffWorkAnalysisTooLarge(RuntimeError):
    def __init__(self, matched_at_least: int) -> None:
        super().__init__(f"匹配质控员超过 {MAX_EXPORT_ROWS} 人，请缩小筛选范围")
        self.matched_at_least = matched_at_least
        self.limit = MAX_EXPORT_ROWS


@dataclass(frozen=True)
class AnalysisScope:
    period: str
    scene: str
    institute_id: str | None
    department: str | None
    task_id: str | None
    start_date: date | None
    end_date: date | None
    as_of: datetime
    window: RankingWindow

    @property
    def appeals_attributable(self) -> bool:
        # 运行/终末按申诉创建时冻结的 scene 归属；历史无 scene 的申诉只进入全场景。
        # 科室/机构/任务筛选下申诉事件仍无可信归属，保持未知。
        return (
            self.institute_id is None
            and self.department is None
            and self.task_id is None
        )

    def filters(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "scene": self.scene,
            "institute_id": self.institute_id,
            "department": self.department,
            "task_id": self.task_id,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "as_of": self.as_of.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        }


@dataclass(frozen=True)
class AnalysisEvents:
    events: list[dict[str, Any]]
    department_options: list[dict[str, str]]
    task_options: list[dict[str, str | None]]
    filter_options_unavailable_reason: str | None
    context_unavailable_count: int
    urge_unavailable_reason: str | None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise StaffWorkAnalysisInvalid("筛选参数无效")
    return value.strip() or None


def _parse_as_of(value: str | datetime | None, now: datetime | None) -> datetime:
    if value is None:
        parsed = now or datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise StaffWorkAnalysisInvalid("as_of 必须是带时区的 ISO 时间") from exc
    else:
        raise StaffWorkAnalysisInvalid("as_of 必须是带时区的 ISO 时间")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StaffWorkAnalysisInvalid("as_of 必须包含时区")
    return parsed


def _parse_date(value: str | None, field: str) -> date | None:
    text = _optional_text(value)
    if text is None:
        return None
    if len(text) != 10:
        raise StaffWorkAnalysisInvalid(f"{field} 必须为 YYYY-MM-DD")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise StaffWorkAnalysisInvalid(f"{field} 不是有效日期") from exc


def _scope(
    *, period: str, scene: str = SCENE_ALL, institute_id: str | None = None,
    department: str | None = None, task_id: str | None = None,
    start_date: str | None = None, end_date: str | None = None,
    as_of: str | datetime | None = None, now: datetime | None = None,
) -> AnalysisScope:
    if scene not in {SCENE_ALL, "running", "final"}:
        raise StaffWorkAnalysisInvalid("scene 无效")
    institute = _optional_text(institute_id)
    department_name = _optional_text(department)
    if (institute is None) != (department_name is None):
        raise StaffWorkAnalysisInvalid("institute_id 与 department 必须同时提供")
    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")
    if (start is None) != (end is None):
        raise StaffWorkAnalysisInvalid("start_date 与 end_date 必须同时提供")
    if start and end and start > end:
        raise StaffWorkAnalysisInvalid("start_date 不能晚于 end_date")
    anchor = _parse_as_of(as_of, now)
    try:
        period_window = compute_window(period, anchor)
        if start is not None and end is not None:
            local_start = datetime.combine(start, time.min, HOSPITAL_TIMEZONE)
            local_end = datetime.combine(end + timedelta(days=1), time.min, HOSPITAL_TIMEZONE)
            window = RankingWindow(
                "custom", "自定义", local_start,
                min(local_end, anchor.astimezone(HOSPITAL_TIMEZONE)),
            )
        else:
            window = period_window
        _ = window.utc_start
        _ = window.utc_end
    except (PerformanceRankingInvalid, OverflowError, ValueError) as exc:
        raise StaffWorkAnalysisInvalid(str(exc) or "时间范围无效") from exc
    return AnalysisScope(
        period=period, scene=scene, institute_id=institute, department=department_name,
        task_id=_optional_text(task_id), start_date=start, end_date=end,
        as_of=anchor, window=window,
    )


def _task_identity(histories: list[Any], defect: Any) -> tuple[str, str] | None:
    identity = _manual_task_identity(histories, defect.manual_created_by)
    task_id = identity["task_id"]
    task_record_id = identity["task_record_id"]
    if task_id is None or task_record_id is None:
        return None
    return task_id.strip(), task_record_id.strip()


def _event(
    *, event_id: str, event_type: str, occurred_at: datetime, user_id: str,
    institute_id: str | None = None, patient_id: str | None = None,
    visit_id: str | None = None, task_id: str | None = None,
    stage: str | None = None, decision: str | None = None,
    defect_id: str | None = None, appeal_id: str | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id, "event_type": event_type, "occurred_at": occurred_at,
        "user_id": user_id, "institute_id": institute_id, "patient_id": patient_id,
        "visit_id": visit_id, "task_id": task_id, "department": None,
        "stage": stage, "decision": decision, "defect_id": defect_id,
        "appeal_id": appeal_id,
    }


def _appeal_execution_options(session: Any) -> dict[str, Any]:
    """申诉与申诉审核的权威表在 qc；PostgreSQL 下不经 search_path 命中 public 同名旧表。"""
    if session.get_bind().dialect.name == "postgresql":
        return {"schema_translate_map": {None: "qc"}}
    return {}


def _load_base_events(session: Any, scope: AnalysisScope) -> tuple[list[dict[str, Any]], bool]:
    window = scope.window
    review_predicates = [
        QCRecordReview.created_at >= window.utc_start,
        QCRecordReview.created_at < window.utc_end,
    ]
    if scope.scene != SCENE_ALL:
        review_predicates.append(QCRecordReview.scene == scope.scene)
    reviews = session.execute(select(QCRecordReview).where(*review_predicates)).scalars().all()
    events = []
    confirmed_keys = set()
    for row in sorted(reviews, key=lambda item: (item.created_at, item.id)):
        event = _event(
            event_id=row.id, event_type="record_review", occurred_at=row.created_at,
            user_id=str(row.reviewer_id), institute_id=str(row.institute_id),
            patient_id=str(row.patient_id), visit_id=str(row.visit_id),
            task_id=str(row.task_id) if row.task_id else None,
            stage=row.stage, decision=row.decision,
        )
        if row.stage == "initial":
            try:
                snapshot = validate_snapshot(
                    getattr(row, "defect_snapshot", None),
                    source={**{field: getattr(row, field) for field in _SNAPSHOT_SOURCE_FIELDS},
                            "created_at": row.created_at},
                )
            except DefectSnapshotInvalid:
                snapshot = None
            event["defect_snapshot_complete"] = snapshot is not None
            if snapshot is not None:
                # 缺陷只搬运初审冻结结果；不读取当前 Envelope 或人工缺陷状态补齐历史。
                source = snapshot["source"]
                for kind in ("auto", "manual"):
                    for item in snapshot[kind]["items"]:
                        key = (str(row.reviewer_id), *(source[field] for field in _SNAPSHOT_SOURCE_FIELDS),
                               kind, item["defect_id"])
                        if key in confirmed_keys:
                            continue
                        confirmed_keys.add(key)
                        confirmed = _event(
                            event_id=f"{row.id}:{kind}:{item['defect_id']}",
                            event_type="initial_defect_confirmed", occurred_at=row.created_at,
                            user_id=str(row.reviewer_id),
                            institute_id=source["institute_id"], patient_id=source["patient_id"],
                            visit_id=source["visit_id"], task_id=event["task_id"],
                            stage="initial", decision=row.decision, defect_id=item["defect_id"],
                        )
                        confirmed.update(source=kind, rule_id=item.get("rule_id"),
                                         job_id=source["job_id"], envelope_id=source["envelope_id"],
                                         rule_set_key=source["rule_set_key"],
                                         rule_set_version=source["rule_set_version"],
                                         scene=source["scene"])
                        events.append(confirmed)
        events.append(event)

    event_histories = session.execute(select(QCDefectHistory).where(
        QCDefectHistory.action.in_((
            "manual_create", "manual_review_approved", "manual_review_rejected",
        )),
        QCDefectHistory.created_at >= window.utc_start,
        QCDefectHistory.created_at < window.utc_end,
    )).scalars().all()
    event_defect_ids = {row.defect_id for row in event_histories}
    defects = []
    if event_defect_ids:
        defects = session.execute(select(QCDefect).where(
            QCDefect.id.in_(event_defect_ids), *_manual_scope(scene=scope.scene),
        )).scalars().all()

    histories_by_defect: dict[str, list[Any]] = {}
    if defects:
        defect_ids = [row.id for row in defects]
        create_histories = session.execute(select(QCDefectHistory).where(
            QCDefectHistory.defect_id.in_(defect_ids),
            QCDefectHistory.action == "manual_create",
        )).scalars().all()
        relevant_ids = set(defect_ids)
        histories = [
            row for row in event_histories
            if row.defect_id in relevant_ids and row.action != "manual_create"
        ] + list(create_histories)
        for history in histories:
            histories_by_defect.setdefault(history.defect_id, []).append(history)

    parsed_task: dict[str, tuple[str, str] | None] = {}
    record_ids: set[str] = set()
    for defect in defects:
        create_rows = [
            row for row in histories_by_defect.get(defect.id, []) if row.action == "manual_create"
        ]
        if not create_rows:
            continue
        if any(row.actor_id != defect.manual_created_by for row in create_rows):
            raise StaffWorkAnalysisUnavailable("人工缺陷创建事件归属不一致")
        parsed_task[defect.id] = _task_identity(create_rows, defect)
        if parsed_task[defect.id]:
            record_ids.add(parsed_task[defect.id][1])

    records = {}
    task_source_unavailable = False
    if record_ids:
        try:
            with session.begin_nested():
                records = {
                    row.id: row for row in session.execute(
                        select(QCTaskRecord).where(QCTaskRecord.id.in_(record_ids))
                    ).scalars().all()
                }
        except SQLAlchemyError as exc:
            if scope.task_id is not None:
                raise StaffWorkAnalysisUnavailable("任务归属读取失败") from exc
            records = {}
            task_source_unavailable = True

    for defect in defects:
        identity = (
            str(defect.institute_id or ""), str(defect.patient_id or ""),
            str(defect.visit_id or ""),
        )
        task_id: str | None = None
        task_context = parsed_task.get(defect.id)
        if task_context:
            candidate_task, record_id = task_context
            record = records.get(record_id)
            if (
                record is not None and record.task_id == candidate_task
                and defect.record_id == record_id
                and identity == (
                    str(record.institute_id or ""), str(record.patient_id or ""),
                    str(record.visit_id or ""),
                )
            ):
                task_id = candidate_task

        create_rows = [
            row for row in histories_by_defect.get(defect.id, []) if row.action == "manual_create"
        ]
        if create_rows and defect.manual_created_by is not None:
            created = min(create_rows, key=lambda row: row.created_at)
            if window.utc_start <= created.created_at < window.utc_end:
                events.append(_event(
                    event_id=created.id, event_type="manual_defect_created",
                    occurred_at=created.created_at, user_id=str(defect.manual_created_by),
                    institute_id=identity[0] or None, patient_id=identity[1] or None,
                    visit_id=identity[2] or None, task_id=task_id, defect_id=defect.id,
                ))
        for history in histories_by_defect.get(defect.id, []):
            if history.action not in {"manual_review_approved", "manual_review_rejected"}:
                continue
            if not history.actor_id:
                raise StaffWorkAnalysisUnavailable("人工缺陷审核事件缺少审核人")
            events.append(_event(
                event_id=history.id, event_type=history.action,
                occurred_at=history.created_at, user_id=str(history.actor_id),
                institute_id=identity[0] or None, patient_id=identity[1] or None,
                visit_id=identity[2] or None, task_id=task_id, defect_id=defect.id,
            ))

    if scope.appeals_attributable:
        start = window.utc_start.replace(tzinfo=timezone.utc)
        end = window.utc_end.replace(tzinfo=timezone.utc)
        statement = select(QCAppealReview).where(
            QCAppealReview.action.in_(("approve", "reject")),
            QCAppealReview.created_at >= start,
            QCAppealReview.created_at < end,
        )
        if scope.scene != SCENE_ALL:
            # 只统计审核事件关联的、已冻结为该场景的申诉；历史 NULL 不计入具体场景。
            statement = statement.join(
                QCAppeal, QCAppeal.id == QCAppealReview.appeal_id,
            ).where(QCAppeal.scene == scope.scene)
        appeals = session.execute(
            statement, execution_options=_appeal_execution_options(session),
        ).scalars().all()
        for row in appeals:
            if not row.reviewer_id:
                raise StaffWorkAnalysisUnavailable("申诉审核事件缺少审核人")
            events.append(_event(
                event_id=row.id,
                event_type="appeal_approved" if row.action == "approve" else "appeal_rejected",
                occurred_at=row.created_at, user_id=str(row.reviewer_id), appeal_id=row.appeal_id,
            ))
    return events, task_source_unavailable


def _load_events(
    session: Any,
    scope: AnalysisScope,
    department_loader: Callable[..., dict[tuple[str, str, str], str]],
) -> AnalysisEvents:
    events, task_source_unavailable = _load_base_events(session, scope)
    urge_unavailable_reason = None
    # 催办只取整改 owner 的缺陷事件，病例级沟通不冒充缺陷催办。
    if scope.task_id is not None:
        urge_unavailable_reason = FILTER_NOT_ATTRIBUTABLE
    else:
        try:
            with session.begin_nested():
                statement = select(DefectRectificationEvent, DefectRectification).join(
                    DefectRectification,
                    DefectRectification.id == DefectRectificationEvent.rectification_id,
                ).where(
                    DefectRectificationEvent.action == "urge",
                    DefectRectificationEvent.created_at >= scope.window.utc_start,
                    DefectRectificationEvent.created_at < scope.window.utc_end,
                )
                if scope.scene != SCENE_ALL:
                    statement = statement.where(DefectRectification.scene == scope.scene)
                urges = session.execute(statement).all()
            seen_urges = set()
            for entry, source in sorted(urges, key=lambda pair: (pair[0].created_at, pair[0].id)):
                source_key = (
                    source.institute_id, source.patient_id, source.visit_id, source.scene,
                    source.target_kind, source.target_id, source.root_job_id, source.envelope_id,
                )
                if not entry.actor_id or not all(source_key):
                    raise StaffWorkAnalysisUnavailable("缺陷催办事件归属不完整")
                key = (entry.actor_id, *source_key)
                if key in seen_urges:
                    continue
                seen_urges.add(key)
                event = _event(
                    event_id=entry.id, event_type="defect_urged", occurred_at=entry.created_at,
                    user_id=entry.actor_id, institute_id=source.institute_id,
                    patient_id=source.patient_id, visit_id=source.visit_id,
                    defect_id=source.target_id,
                )
                event.update(scene=source.scene, target_kind=source.target_kind,
                             root_job_id=source.root_job_id, envelope_id=source.envelope_id,
                             department=source.department)
                events.append(event)
        except SQLAlchemyError:
            urge_unavailable_reason = "source_unavailable"
    identities = {
        (event["institute_id"], event["patient_id"], event["visit_id"])
        for event in events
        if event["institute_id"] and event["patient_id"] and event["visit_id"]
    }
    department_error = None
    try:
        with session.begin_nested():
            departments = department_loader(identities, session=session)
    except Exception as exc:
        if scope.department is not None:
            raise StaffWorkAnalysisUnavailable("当前病例科室读取失败") from exc
        departments = {}
        department_error = DEPARTMENT_SOURCE_UNAVAILABLE

    department_options = sorted(
        {(identity[0], name) for identity, name in departments.items() if identity[0] and name}
        | {(event["institute_id"], event["department"]) for event in events
           if event["event_type"] == "defect_urged" and event["department"]},
        key=lambda item: (item[0], item[1]),
    )
    for event in events:
        identity = (event["institute_id"], event["patient_id"], event["visit_id"])
        if event["event_type"] != "defect_urged":
            event["department"] = departments.get(identity)

    context_unavailable_count = 0
    if scope.task_id is not None:
        filtered = []
        for event in events:
            if event["task_id"] == scope.task_id:
                filtered.append(event)
            elif (event["task_id"] is None and not event["event_type"].startswith("appeal_")
                  and event["event_type"] != "initial_defect_confirmed"):
                context_unavailable_count += 1
        events = filtered
    if scope.department is not None:
        filtered = []
        for event in events:
            if event["institute_id"] == scope.institute_id and event["department"] == scope.department:
                filtered.append(event)
            elif (event["department"] is None and not event["event_type"].startswith("appeal_")
                  and event["event_type"] != "initial_defect_confirmed"):
                context_unavailable_count += 1
        events = filtered

    task_ids = sorted({event["task_id"] for event in events if event["task_id"]})
    task_names = {}
    if task_ids:
        try:
            with session.begin_nested():
                task_names = {
                    row.id: row.task_name for row in session.execute(
                        select(QCTask).where(QCTask.id.in_(task_ids))
                    ).scalars().all()
                }
        except SQLAlchemyError:
            task_names = {}
            task_source_unavailable = True
    return AnalysisEvents(
        events=events,
        department_options=[
            {"institute_id": institute, "department_name": name}
            for institute, name in department_options
        ],
        task_options=[
            {"task_id": value, "task_name": task_names.get(value)} for value in task_ids
        ],
        filter_options_unavailable_reason=(
            department_error or (TASK_SOURCE_UNAVAILABLE if task_source_unavailable else None)
        ),
        context_unavailable_count=context_unavailable_count,
        urge_unavailable_reason=urge_unavailable_reason,
    )


def _aggregate(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    staff: dict[str, dict[str, Any]] = {}
    personal_cases: dict[str, set[tuple[str, str, str]]] = {}
    rechecked_cases: dict[str, set[tuple[str, str, str]]] = {}
    global_cases: set[tuple[str, str, str]] = set()
    field_by_type = {
        "manual_defect_created": "manual_defect_created_count",
        "manual_review_approved": "manual_review_approved_count",
        "manual_review_rejected": "manual_review_rejected_count",
        "appeal_approved": "appeal_approved_count",
        "appeal_rejected": "appeal_rejected_count",
        "defect_urged": "urged_defect_count",
        "initial_defect_confirmed": "confirmed_defect_count",
    }
    for event in events:
        user_id = event["user_id"]
        row = staff.setdefault(
            user_id, {"user_id": user_id, "name": None, **dict.fromkeys(COUNT_FIELDS, 0),
                      "defect_snapshot_coverage": dict.fromkeys(_COVERAGE_FIELDS, 0)},
        )
        if event["event_type"] == "record_review":
            row["record_review_count"] += 1
            row["initial_count" if event["stage"] == "initial" else "recheck_count"] += 1
            if event["stage"] == "initial":
                coverage = row["defect_snapshot_coverage"]
                coverage["initial_review_count"] += 1
                field = ("covered_initial_review_count" if event.get("defect_snapshot_complete")
                         else "missing_initial_review_count")
                coverage[field] += 1
            identity = (event["institute_id"], event["patient_id"], event["visit_id"])
            personal_cases.setdefault(user_id, set()).add(identity)
            if event["stage"] == "recheck":
                rechecked_cases.setdefault(user_id, set()).add(identity)
            global_cases.add(identity)
        else:
            row[field_by_type[event["event_type"]]] += 1
            if event["event_type"] == "initial_defect_confirmed":
                row["defect_snapshot_coverage"]["known_defect_count"] += 1
    for user_id, cases in personal_cases.items():
        staff[user_id]["reviewed_case_count"] = len(cases)
        staff[user_id]["rechecked_case_count"] = len(rechecked_cases.get(user_id, set()))
    for row in staff.values():
        if row["defect_snapshot_coverage"]["missing_initial_review_count"]:
            row["confirmed_defect_count"] = None
    return list(staff.values()), len(global_cases)


def _summary(
    staff: list[dict[str, Any]], global_case_count: int, *, appeals_attributable: bool,
) -> dict[str, Any]:
    known_fields = COUNT_FIELDS if appeals_attributable else tuple(
        field for field in COUNT_FIELDS if field not in APPEAL_COUNT_FIELDS
    )
    totals = {
        field: None if any(row[field] is None for row in staff) else sum(row[field] for row in staff)
        for field in known_fields
    }
    if not appeals_attributable:
        totals.update(dict.fromkeys(APPEAL_COUNT_FIELDS))
    totals["reviewed_case_count"] = global_case_count
    active_reviewers = sum(row["record_review_count"] > 0 for row in staff)
    active_staff = len(staff)
    return {
        "active_staff_count": active_staff,
        "record_reviewer_count": active_reviewers,
        **totals,
        **{
            average: round(sum(row[field] for row in staff) / active_staff, 2) if active_staff else None
            for average, field in (
                ("avg_reviewed_cases_per_active_staff", "reviewed_case_count"),
                ("avg_rechecked_cases_per_active_staff", "rechecked_case_count"),
                ("avg_manual_defects_per_active_staff", "manual_defect_created_count"),
                ("avg_rejected_defects_per_active_staff", "manual_review_rejected_count"),
            )
        },
        "avg_record_reviews_per_active_staff": (
            round(totals["record_review_count"] / active_staff, 2) if active_staff else None
        ),
        "avg_reviewed_cases_per_reviewer": (
            round(sum(row["reviewed_case_count"] for row in staff) / active_reviewers, 2)
            if active_reviewers else None
        ),
    }


def _ordered_staff(
    session: Any, rows: list[dict[str, Any]], *, appeals_attributable: bool,
    rank_metric: str = "record_review_count",
) -> list[dict[str, Any]]:
    names = _display_names(session, {row["user_id"] for row in rows})
    ordered = sorted(rows, key=lambda row: (
        row[rank_metric] is None, -(row[rank_metric] or 0), row["user_id"],
    ))
    prior_count: int | None = None
    rank = 0
    for index, row in enumerate(ordered, start=1):
        row["name"] = names.get(row["user_id"])
        if not appeals_attributable:
            for field in APPEAL_COUNT_FIELDS:
                row[field] = None
        if row[rank_metric] != prior_count:
            rank = index
            prior_count = row[rank_metric]
        row["rank"] = rank
    return ordered


def _unavailable_metrics(scope: AnalysisScope) -> dict[str, str]:
    if scope.appeals_attributable:
        return {}
    return dict.fromkeys(APPEAL_COUNT_FIELDS, FILTER_NOT_ATTRIBUTABLE)


def _read(
    scope: AnalysisScope,
    *,
    department_loader: Callable[..., dict[tuple[str, str, str], str]] = load_scoring_departments,
) -> tuple[Any, AnalysisEvents]:
    if SessionLocal is None:
        raise StaffWorkAnalysisUnavailable("数据库会话不可用")
    session = SessionLocal()
    try:
        return session, _load_events(session, scope, department_loader)
    except StaffWorkAnalysisUnavailable:
        session.close()
        raise
    except SQLAlchemyError as exc:
        session.close()
        raise StaffWorkAnalysisUnavailable("质控员工作分析读取失败") from exc


def get_staff_work_analysis(
    *, period: str, scene: str = SCENE_ALL, institute_id: str | None = None,
    department: str | None = None, task_id: str | None = None,
    start_date: str | None = None, end_date: str | None = None,
    as_of: str | datetime | None = None, now: datetime | None = None,
    department_loader: Callable[..., dict[tuple[str, str, str], str]] = load_scoring_departments,
    rank_metric: str = "record_review_count",
) -> dict[str, Any]:
    if rank_metric not in DETAIL_METRICS:
        raise StaffWorkAnalysisInvalid("rank_metric 无效")
    scope = _scope(
        period=period, scene=scene, institute_id=institute_id, department=department,
        task_id=task_id, start_date=start_date, end_date=end_date, as_of=as_of, now=now,
    )
    session, loaded = _read(scope, department_loader=department_loader)
    try:
        rows, global_case_count = _aggregate(loaded.events)
        ordered = _ordered_staff(
            session, rows, appeals_attributable=scope.appeals_attributable,
            rank_metric=rank_metric,
        )
        summary = _summary(ordered, global_case_count, appeals_attributable=scope.appeals_attributable)
        unavailable_metrics = _unavailable_metrics(scope)
        coverage = {
            field: sum(row["defect_snapshot_coverage"][field] for row in ordered)
            for field in _COVERAGE_FIELDS
        }
        summary["defect_snapshot_coverage"] = coverage
        if coverage["missing_initial_review_count"]:
            unavailable_metrics["confirmed_defect_count"] = "snapshot_incomplete"
        if loaded.urge_unavailable_reason:
            unavailable_metrics["urged_defect_count"] = loaded.urge_unavailable_reason
            summary["urged_defect_count"] = None
            for row in ordered:
                row["urged_defect_count"] = None
        if rank_metric in unavailable_metrics:
            for row in ordered:
                row["rank"] = None
    finally:
        session.close()
    return {
        "period": scope.period,
        "period_label": scope.window.label,
        "range": {
            "start": scope.window.local_start.isoformat(),
            "end": scope.window.local_end.isoformat(),
        },
        "scene": scope.scene,
        "rank_metric": rank_metric,
        "filters": scope.filters(),
        "filter_options": {
            "departments": loaded.department_options,
            "tasks": loaded.task_options,
        },
        "filter_options_unavailable_reason": loaded.filter_options_unavailable_reason,
        "context_unavailable_count": loaded.context_unavailable_count,
        "summary": summary,
        "defect_snapshot_coverage": coverage,
        "staff": ordered,
        "unavailable_reason": None,
        "unavailable_metrics": unavailable_metrics,
    }


def get_staff_work_details(
    *, user_id: str, metric: str, page: int = 1, page_size: int = 20, **filters: Any,
) -> dict[str, Any]:
    user = _optional_text(user_id)
    if user is None:
        raise StaffWorkAnalysisInvalid("user_id 无效")
    if metric not in DETAIL_METRICS:
        raise StaffWorkAnalysisInvalid("metric 无效")
    if (
        type(page) is not int or page < 1
        or type(page_size) is not int or not 1 <= page_size <= MAX_DETAIL_PAGE_SIZE
    ):
        raise StaffWorkAnalysisInvalid("分页参数无效")
    scope = _scope(**filters)
    if metric in APPEAL_COUNT_FIELDS and not scope.appeals_attributable:
        return {
            "filters": scope.filters(), "metric": metric, "user_id": user,
            "items": None, "total": None, "page": page, "page_size": page_size,
            "unavailable_reason": _unavailable_metrics(scope)[metric],
        }
    session, loaded = _read(scope)
    session.close()
    if metric == "urged_defect_count" and loaded.urge_unavailable_reason:
        return {
            "filters": scope.filters(), "metric": metric, "user_id": user,
            "items": None, "total": None, "page": page, "page_size": page_size,
            "unavailable_reason": loaded.urge_unavailable_reason,
        }
    events = [event for event in loaded.events if event["user_id"] == user]
    coverage = None
    if metric == "confirmed_defect_count":
        rows, _ = _aggregate(events)
        coverage = rows[0]["defect_snapshot_coverage"] if rows else dict.fromkeys(_COVERAGE_FIELDS, 0)
    if metric == "record_review_count":
        selected = [event for event in events if event["event_type"] == "record_review"]
    elif metric in {"reviewed_case_count", "rechecked_case_count"}:
        selected = []
        seen = set()
        for event in sorted(events, key=lambda item: (item["occurred_at"], item["event_id"]), reverse=True):
            if event["event_type"] != "record_review":
                continue
            if metric == "rechecked_case_count" and event["stage"] != "recheck":
                continue
            identity = (event["institute_id"], event["patient_id"], event["visit_id"])
            if identity not in seen:
                seen.add(identity)
                selected.append(event)
    elif metric in {"initial_count", "recheck_count"}:
        stage = "initial" if metric == "initial_count" else "recheck"
        selected = [
            event for event in events
            if event["event_type"] == "record_review" and event["stage"] == stage
        ]
    else:
        type_by_metric = {
            "manual_defect_created_count": "manual_defect_created",
            "manual_review_approved_count": "manual_review_approved",
            "manual_review_rejected_count": "manual_review_rejected",
            "appeal_approved_count": "appeal_approved",
            "appeal_rejected_count": "appeal_rejected",
            "urged_defect_count": "defect_urged",
            "confirmed_defect_count": "initial_defect_confirmed",
        }
        selected = [event for event in events if event["event_type"] == type_by_metric[metric]]
    selected.sort(key=lambda item: (item["occurred_at"], item["event_id"]), reverse=True)
    total = len(selected)
    offset = (page - 1) * page_size
    items = [
        {key: value for key, value in event.items() if key not in {"user_id", "defect_snapshot_complete"}}
        for event in selected[offset:offset + page_size]
    ]
    snapshot_incomplete = coverage is not None and coverage["missing_initial_review_count"] > 0
    return {
        "filters": scope.filters(), "metric": metric, "user_id": user,
        "items": items, "total": None if snapshot_incomplete else total,
        "page": page, "page_size": page_size,
        "unavailable_reason": "snapshot_incomplete" if snapshot_incomplete else None,
        **({"known_total": total, "total_complete": not snapshot_incomplete,
            "defect_snapshot_coverage": coverage} if coverage is not None else {}),
    }


_EXPORT_HEADERS = (
    ("rank", "排名"), ("user_id", "人员ID"), ("name", "姓名"),
    ("record_review_count", "审核决定数"), ("reviewed_case_count", "审核病历数"),
    ("rechecked_case_count", "复审病历数"),
    ("initial_count", "初审数"), ("recheck_count", "复审数"),
    ("manual_defect_created_count", "人工缺陷录入数"),
    ("manual_review_approved_count", "人工缺陷审核通过数"),
    ("manual_review_rejected_count", "人工缺陷审核驳回数"),
    ("appeal_approved_count", "申诉通过数"), ("appeal_rejected_count", "申诉驳回数"),
    ("urged_defect_count", "催办缺陷数"),
    ("confirmed_defect_count", "初审确认质控缺陷数"),
    ("initial_review_count", "缺陷统计初审数"),
    ("covered_initial_review_count", "完整缺陷记录初审数"),
    ("missing_initial_review_count", "缺少完整缺陷记录初审数"),
    ("known_defect_count", "已知初审确认缺陷数"),
)


def _csv_safe(value: Any) -> Any:
    if value is None:
        return "未知"
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    return f"'{text}" if text.lstrip().startswith(_FORMULA_PREFIXES) else text


def export_staff_work_csv(**filters: Any) -> tuple[bytes, int]:
    report = get_staff_work_analysis(**filters)
    rows = report["staff"]
    if len(rows) > MAX_EXPORT_ROWS:
        raise StaffWorkAnalysisTooLarge(len(rows))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=[label for _, label in _EXPORT_HEADERS])
    writer.writeheader()
    for row in rows:
        values = {**row, **row["defect_snapshot_coverage"]}
        writer.writerow({label: _csv_safe(values.get(key)) for key, label in _EXPORT_HEADERS})
    return output.getvalue().encode("utf-8-sig"), len(rows)
