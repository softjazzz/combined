"""人工质控报表：已确认创建日期窗口、当前审核/整改状态统计口径。"""

import csv
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select, tuple_

from ..database.connection import SessionLocal
from ..database.models.qc import (
    QCDefect,
    QCDefectHistory,
    QCTaskRecord,
    QCTaskQCRun,
    QCTask,
    SysUser,
)
from ..database.models.defect_rectification import DefectRectification
from .defect_rectification_service import _person, RectificationError
from .manual_defect_review_service import _manual_scope, _task_identity
from .appeal_manual_target_service import _history_details, _identity, _scene, _text
from .qc_workspace.canonical_result_store import (
    RECORD_RESULT_ENVELOPE_SCHEMA,
    CANONICAL_RESULT_DELIVERY_MODE,
)
from .user_scope_owner import user_owner_options
from .performance_ranking_service import HOSPITAL_TIMEZONE, RankingWindow

MAX_ROWS = 10000
REVIEW = ("pending", "approved", "rejected", "unknown")
RECTIFICATION = (
    "pending",
    "submitted",
    "approved",
    "rejected",
    "unassigned",
    "unknown",
)
ASSUMPTION = "已确认统计口径：按医院上海自然日的人工缺陷创建日期计录入数；审核与整改为各自当前状态，同缺陷多次操作只计一条；支持机构、科室、录入人、任务及场景筛选；科室取来源已核验的已保存任务病例抽样科室，来源不完整或错配时相关信息为未知。"


def _json(value):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _source(defect, histories, records, runs, jobs, envelopes):
    """批量读出的冻结链，只读验证；绝不回退当前 run 或逐例解析。"""
    task = _task_identity(histories, defect.manual_created_by)
    if not task["task_id"]:
        return task, None, None
    details = _history_details(histories[0]) or {}
    identity = _identity(
        {
            key: getattr(defect, key)
            for key in ("institute_id", "patient_id", "visit_id")
        }
    )
    scene = _scene(defect.scene)
    job_id = _text(details.get("job_id"), maximum=36)
    record = records.get(task["task_record_id"])
    run = runs.get((task["task_id"], task["run_number"]))
    if (
        identity is None
        or scene is None
        or job_id is None
        or details.get("scene") != scene
        or defect.record_id != task["task_record_id"]
        or record is None
        or record["task_id"] != task["task_id"]
        or record["record_id"] != task["task_record_id"]
        or _identity(record) != identity
        or run is None
        or run["job_id"] != job_id
        or run["run_scope"] != "assigned"
        or run["triggered_by"] != defect.manual_created_by
    ):
        return {"task_id": None, "task_record_id": None, "run_number": None}, None, None
    department = _text(record.get("department"), maximum=100)
    job = jobs.get(job_id)
    filters = _json(job.get("filters_json")) if job else None
    if not isinstance(filters, dict):
        return task, department, None
    refs = filters.get("record_refs")
    identities = (
        [_identity(item) if isinstance(item, dict) else None for item in refs]
        if isinstance(refs, list)
        else []
    )
    rule_key = _text(filters.get("rule_set_key"), maximum=96)
    rule_version = _text(filters.get("rule_set_version"), maximum=96)
    if (
        job["created_by"] != defect.manual_created_by
        or filters.get("task_id") != task["task_id"]
        or str(filters.get("task_run_number") or "") != str(task["run_number"])
        or _scene(filters.get("query_scope")) != scene
        or not rule_key
        or not rule_version
        or not identities
        or any(value is None for value in identities)
        or len(set(identities)) != len(identities)
        or identity not in identities
    ):
        return task, department, None
    matches = envelopes.get((job_id, *identity, rule_key, rule_version), [])
    if len(matches) != 1:
        return task, department, None
    envelope = matches[0]
    payload = _json(envelope["envelope_json"])
    if (
        not _text(envelope["id"], maximum=36)
        or envelope["record_id"] != identity[2]
        or envelope["created_by"] != defect.manual_created_by
        or not isinstance(payload, dict)
        or payload.get("schema_version") != RECORD_RESULT_ENVELOPE_SCHEMA
        or payload.get("delivery_mode") != CANONICAL_RESULT_DELIVERY_MODE
        or not isinstance(payload.get("items"), list)
        or not payload["items"]
        or type(envelope["result_count"]) is not int
        or len(payload["items"]) != envelope["result_count"]
    ):
        return task, department, None
    return (
        task,
        department,
        (*identity, scene, "task_manual_defect", defect.id, job_id, envelope["id"]),
    )


class ManualQualityReportService:
    def __init__(self, sessions=None, person_loader=None, tables=None):
        self.sessions = sessions or SessionLocal
        self.person = person_loader or _person
        self.tables = tables

    def report(
        self,
        actor_id,
        *,
        start_date,
        end_date,
        institute_id=None,
        department=None,
        creator_id=None,
        task_id=None,
        scene="all",
        page=1,
        page_size=20,
    ):
        if start_date > end_date or (end_date - start_date).days > 365:
            raise RectificationError("创建日期窗口须为正序且不超过366天")
        if (
            type(page) is not int
            or page < 1
            or type(page_size) is not int
            or not 1 <= page_size <= 100
        ):
            raise RectificationError("分页参数无效")
        if department and not institute_id:
            raise RectificationError("科室筛选须同时指定机构")
        as_of = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        window = RankingWindow(
            period="custom",
            label="自定义创建日期",
            local_start=datetime.combine(start_date, time.min, HOSPITAL_TIMEZONE),
            local_end=datetime.combine(
                end_date + timedelta(days=1), time.min, HOSPITAL_TIMEZONE
            ),
        )
        with self.sessions() as session:
            actor = self.person(session, actor_id)
            roles = actor["roles"]
            if not roles & {"admin", "qc_manager", "qc_staff"}:
                raise RectificationError("仅质控人员可读取人工质控报表", 403)
            if "admin" not in roles:
                if not actor["institute_id"] or (
                    institute_id and institute_id != actor["institute_id"]
                ):
                    raise RectificationError("无权读取该机构报表", 403)
                institute_id = actor["institute_id"]
            self_only = "admin" not in roles and "qc_manager" not in roles
            if self_only and creator_id and creator_id != actor_id:
                raise RectificationError("仅可读取本人录入的人工缺陷", 403)
            if self_only:
                creator_id = actor_id
            predicates = [
                *_manual_scope(scene=scene),
                QCDefect.created_at >= window.utc_start,
                QCDefect.created_at < window.utc_end,
            ]
            if institute_id:
                predicates.append(QCDefect.institute_id == institute_id)
            if self_only:
                predicates.append(QCDefect.manual_created_by == actor_id)
            defects = session.scalars(
                select(QCDefect)
                .where(*predicates)
                .order_by(QCDefect.created_at.desc(), QCDefect.id)
                .limit(MAX_ROWS + 1)
            ).all()
            if len(defects) > MAX_ROWS:
                raise RectificationError("统计范围超过10000条，请缩小日期或机构范围")
            data = self._batch(session, defects)
            rows = []
            for defect in defects:
                task, frozen_department, source = _source(
                    defect,
                    data["histories"].get(defect.id, []),
                    data["records"],
                    data["runs"],
                    data["jobs"],
                    data["envelopes"],
                )
                if not source or task["task_id"] not in data["tasks"]:
                    source = None
                    frozen_department = None
                    task = {"task_id": None, "task_record_id": None, "run_number": None}
                matches = data["rectifications"].get(defect.id, [])
                matched = [
                    row
                    for row in matches
                    if source
                    and tuple(
                        getattr(row, key)
                        for key in (
                            "institute_id",
                            "patient_id",
                            "visit_id",
                            "scene",
                            "target_kind",
                            "target_id",
                            "root_job_id",
                            "envelope_id",
                        )
                    )
                    == source
                ]
                status = "unknown"
                if source:
                    status = (
                        "unassigned"
                        if not matches
                        else matched[0].status
                        if len(matched) == 1 and len(matches) == 1
                        else "unknown"
                    )
                if status not in RECTIFICATION:
                    status = "unknown"
                rows.append(
                    {
                        "id": defect.id,
                        "institute_id": defect.institute_id,
                        "patient_id": defect.patient_id,
                        "visit_id": defect.visit_id,
                        "scene": defect.scene,
                        "creator_id": defect.manual_created_by,
                        "creator_name": data["people"].get(defect.manual_created_by)
                        or defect.manual_created_by
                        or "未知录入人",
                        "department": frozen_department,
                        **task,
                        "task_name": data["tasks"].get(task["task_id"])
                        if task["task_id"]
                        else None,
                        "rule_name": defect.rule_name,
                        "created_at": defect.created_at.replace(tzinfo=timezone.utc)
                        .astimezone(HOSPITAL_TIMEZONE)
                        .isoformat(),
                        "review_status": defect.manual_review_status
                        if defect.manual_review_status in REVIEW
                        else "unknown",
                        "rectification_status": status,
                        "source_verified": source is not None,
                    }
                )
            options = {
                "institutes": sorted(
                    {row["institute_id"] for row in rows if row["institute_id"]}
                ),
                "departments": [
                    {"institute_id": key[0], "department": key[1]}
                    for key in sorted(
                        {
                            (row["institute_id"], row["department"])
                            for row in rows
                            if row["institute_id"] and row["department"]
                        }
                    )
                ],
                "creators": [
                    {"id": key, "name": data["people"].get(key) or key}
                    for key in sorted(
                        {row["creator_id"] for row in rows if row["creator_id"]}
                    )
                ],
                "tasks": [
                    {"id": key, "name": data["tasks"].get(key) or key}
                    for key in sorted(
                        {row["task_id"] for row in rows if row["task_id"]}
                    )
                ],
            }
            rows = [
                row
                for row in rows
                if (not department or row["department"] == department)
                and (not creator_id or row["creator_id"] == creator_id)
                and (not task_id or row["task_id"] == task_id)
            ]
            review = Counter(row["review_status"] for row in rows)
            rectification = Counter(row["rectification_status"] for row in rows)
            return {
                "assumption": ASSUMPTION,
                "as_of": as_of,
                "timezone": "Asia/Shanghai",
                "filters": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "institute_id": institute_id,
                    "department": department,
                    "creator_id": creator_id,
                    "task_id": task_id,
                    "scene": scene,
                },
                "summary": {
                    "entered": len(rows),
                    "review": {key: review[key] for key in REVIEW},
                    "rectification": {key: rectification[key] for key in RECTIFICATION},
                },
                "filter_options": options,
                "items": rows[(page - 1) * page_size : page * page_size],
                "total": len(rows),
                "page": page,
                "page_size": page_size,
                "_export_rows": rows,
            }

    def _batch(self, session, defects):
        from .custom_qc_workspace_service import (
            _batch_jobs_table,
            _record_result_envelopes_table,
        )

        histories = defaultdict(list)
        ids = [row.id for row in defects]
        if not ids:
            return {
                "histories": histories,
                "records": {},
                "runs": {},
                "jobs": {},
                "envelopes": {},
                "rectifications": {},
                "people": {},
                "tasks": {},
            }
        for row in session.scalars(
            select(QCDefectHistory).where(
                QCDefectHistory.defect_id.in_(ids),
                QCDefectHistory.action == "manual_create",
            )
        ):
            histories[row.defect_id].append(row)
        details = [
            _history_details(row) or {}
            for values in histories.values()
            for row in values
        ]
        task_ids = [
            value["task_id"]
            for value in details
            if isinstance(value.get("task_id"), str)
        ]
        record_ids = [
            value["task_record_id"]
            for value in details
            if isinstance(value.get("task_record_id"), str)
        ]
        job_ids = [
            value["job_id"] for value in details if isinstance(value.get("job_id"), str)
        ]
        run_refs = [
            (value["task_id"], value["run_number"])
            for value in details
            if isinstance(value.get("task_id"), str)
            and type(value.get("run_number")) is int
        ]
        records = {
            row["id"]: row
            for row in session.execute(
                select(QCTaskRecord.__table__).where(QCTaskRecord.id.in_(record_ids))
            ).mappings()
        }
        runs = {
            (row["task_id"], row["run_number"]): row
            for row in session.execute(
                select(QCTaskQCRun.__table__).where(
                    tuple_(QCTaskQCRun.task_id, QCTaskQCRun.run_number).in_(run_refs)
                )
            ).mappings()
        }
        job_table, envelope_table = self.tables or (
            _batch_jobs_table(),
            _record_result_envelopes_table(),
        )
        jobs = {
            row["id"]: row
            for row in session.execute(
                select(job_table).where(job_table.c.id.in_(job_ids))
            ).mappings()
        }
        envelopes = defaultdict(list)
        case_refs = {
            (
                value.get("job_id"),
                defect.institute_id,
                defect.patient_id,
                defect.visit_id,
            )
            for defect in defects
            for history in histories.get(defect.id, [])
            for value in [_history_details(history) or {}]
            if isinstance(value.get("job_id"), str)
        }
        for row in session.execute(
            select(envelope_table).where(
                tuple_(
                    envelope_table.c.root_job_id,
                    envelope_table.c.institute_id,
                    envelope_table.c.patient_id,
                    envelope_table.c.visit_id,
                ).in_(case_refs)
            )
        ).mappings():
            envelopes[
                tuple(
                    row[key]
                    for key in (
                        "root_job_id",
                        "institute_id",
                        "patient_id",
                        "visit_id",
                        "rule_set_key",
                        "rule_set_version",
                    )
                )
            ].append(row)
        rectifications = defaultdict(list)
        for row in session.scalars(
            select(DefectRectification).where(
                DefectRectification.target_kind == "task_manual_defect",
                DefectRectification.target_id.in_(ids),
            )
        ):
            rectifications[row.target_id].append(row)
        people = {
            row.id: row.display_name
            for row in session.scalars(
                select(SysUser).where(
                    SysUser.id.in_([row.manual_created_by for row in defects])
                ),
                execution_options=user_owner_options(session),
            )
        }
        tasks = {
            row.id: row.task_name
            for row in session.scalars(select(QCTask).where(QCTask.id.in_(task_ids)))
        }
        return {
            "histories": histories,
            "records": records,
            "runs": runs,
            "jobs": jobs,
            "envelopes": envelopes,
            "rectifications": rectifications,
            "people": people,
            "tasks": tasks,
        }


def csv_export(rows, as_of=None):
    fields = (
        "id",
        "institute_id",
        "patient_id",
        "visit_id",
        "department",
        "creator_id",
        "creator_name",
        "task_id",
        "task_record_id",
        "run_number",
        "scene",
        "rule_name",
        "created_at",
        "review_status",
        "rectification_status",
        "source_verified",
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow((*fields, "as_of", "统计口径（已确认）"))
    for row in rows:
        values = []
        for key in fields:
            text = str(row.get(key) if row.get(key) is not None else "未知")
            values.append(
                "'" + text
                if text.lstrip().startswith(("=", "+", "-", "@"))
                or text.startswith(("\t", "\r", "\n"))
                else text
            )
        writer.writerow((*values, as_of or "未知读取时间", ASSUMPTION))
    return "\ufeff" + output.getvalue()
