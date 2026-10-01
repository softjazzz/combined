"""整改分析只读现代 owner；七标签为显式待确认假设，不是新的领域状态。"""

import csv
import io
from collections import defaultdict

from sqlalchemy import select, tuple_

from ..database.connection import SessionLocal
from ..database.models.defect_rectification import DefectRectification as Task
from ..database.models.defect_rectification import DefectRectificationEvent as Event
from ..database.models.qc import QCAppeal
from .defect_rectification_service import RectificationError, _active_urge_ids, _person
from .defect_workflow_filter_service import SOURCE_KEYS, _load_jobs, source_key
from .record_quality_report_service import RecordQualityReportInvalid, _csv_cell
from .record_review_service import RecordReviewConflict, _workspace_scene_from_job

LABELS = {
    "clinical_appeal": "临床申诉",
    "appeal_rejected": "申诉驳回",
    "appeal_approved": "申诉通过",
    "urged_pending": "催办待整改",
    "self_rectified": "医生自行整改",
    "not_urged_pending": "未催办待整改",
    "urged_rectified": "催办已整改",
}
ASSUMPTIONS = [
    "七标签口径待确认；自动确认缺陷及已审核通过的人工缺陷按保存目标去重，申诉与整改独立，可跨标签重叠。",
    "仅匹配当前保存结果的冻结轮次；人工缺陷使用自身创建/run/job/envelope来源，旧轮次与来源不足单列。",
    "已整改仅指质控验收通过；医生提交仍为待验收，不计入已整改。",
    "催办/自行取医生本次提交前有效提醒；无有效催办且验收通过暂列医生自行整改，不表示未派发任务。",
    "未派发、缺少冻结来源或历史不足均单列，不推断未催办待整改。",
]
CASE_SOURCE_KEYS = (*SOURCE_KEYS[:4], *SOURCE_KEYS[6:])


def classify_rectification(task, events):
    """按 owner 版本序列定位本次提交；不按查询时提醒重分类已验收事实。"""
    if task is None:
        return [], "not_dispatched", None, []
    ordered = sorted(events, key=lambda event: event.version)
    if (
        not ordered
        or [event.version for event in ordered] != list(range(1, task.version + 1))
        or ordered[0].action != "assign"
        or ordered[-1].new_status != task.status
    ):
        return [], "history_unknown", None, []
    if task.status in {"pending", "rejected"}:
        active = sorted(_active_urge_ids(ordered))
        return (
            ["urged_pending" if active else "not_urged_pending"],
            task.status,
            None,
            active,
        )
    if task.status == "submitted":
        submissions = [
            event
            for event in ordered
            if event.action == "submit" and event.new_status == "submitted"
        ]
        if not submissions:
            return [], "history_unknown", None, []
        submission = submissions[-1]
        active = sorted(
            _active_urge_ids(
                [event for event in ordered if event.version < submission.version]
            )
        )
        return [], "pending_acceptance", submission.id, active
    if task.status != "approved":
        return [], "history_unknown", None, []
    approvals = [
        event
        for event in ordered
        if event.action == "approve" and event.new_status == "approved"
    ]
    if not approvals:
        return [], "history_unknown", None, []
    approval = approvals[-1]
    submissions = [
        event
        for event in ordered
        if event.action == "submit"
        and event.version < approval.version
        and event.new_status == "submitted"
    ]
    if not submissions:
        return [], "history_unknown", None, []
    submission = submissions[-1]
    active = sorted(
        _active_urge_ids(
            [event for event in ordered if event.version < submission.version]
        )
    )
    return (
        ["urged_rectified" if active else "self_rectified"],
        "approved",
        submission.id,
        active,
    )


def _manual_loader(session, identities, scene):
    from ..database.models.qc import QCDefect
    from .manual_defect_review_service import _manual_scope
    from .manual_quality_report_service import ManualQualityReportService, _source

    rows = []
    identities = sorted(identities)
    for start in range(0, len(identities), 100):
        defects = session.scalars(
            select(QCDefect).where(
                *_manual_scope(scene=scene),
                QCDefect.manual_review_status == "approved",
                tuple_(
                    QCDefect.institute_id, QCDefect.patient_id, QCDefect.visit_id
                ).in_(identities[start : start + 100]),
            )
        ).all()
        for offset in range(0, len(defects), 200):
            chunk = defects[offset : offset + 200]
            data = ManualQualityReportService()._batch(session, chunk)
            for defect in chunk:
                task, _, source = _source(
                    defect,
                    data["histories"].get(defect.id, []),
                    data["records"],
                    data["runs"],
                    data["jobs"],
                    data["envelopes"],
                )
                if not source or task["task_id"] not in data["tasks"]:
                    source = None
                rows.append(
                    {
                        "identity": (
                            defect.institute_id,
                            defect.patient_id,
                            defect.visit_id,
                        ),
                        "id": defect.id,
                        "review_status": defect.manual_review_status,
                        "rule_name": defect.rule_name,
                        "rule_code": defect.rule_code,
                        "source": dict(zip(SOURCE_KEYS, source)) if source else None,
                    }
                )
    return rows


def build_analysis(
    context,
    *,
    actor_id,
    sessions=SessionLocal,
    manual_loader=_manual_loader,
    jobs_loader=_load_jobs,
    person_loader=_person,
):
    """病例/owner/历史分块批读；只匹配三坐标+场景+本轮job/envelope+目标。"""
    with sessions() as session:
        actor = person_loader(session, actor_id)
        if not actor["roles"] & {"admin", "qc_manager"}:
            raise RectificationError("无整改分析访问权限", 403)
        if "admin" not in actor["roles"] and not actor["institute_id"]:
            raise RectificationError("账号缺少可信机构范围", 403)
        cases = {
            row.identity: row
            for row in context.rows
            if "admin" in actor["roles"] or row.identity[0] == actor["institute_id"]
        }
        targets = []
        for identity, row in cases.items():
            raw = context.saved_results.get(identity, {})
            for rule in (
                sorted(set(row.auto_defect_rule_ids))
                if context.scope["defect_source"] in {"all", "auto"}
                else []
            ):
                targets.append(
                    _target(
                        row,
                        context.scene,
                        raw,
                        "canonical_defect",
                        rule,
                        context.rule_meta.get(rule, {}).get("rule_name", rule),
                        bool(row.rule_statuses.get(rule))
                        and row.rule_statuses.get(rule) != "unknown",
                    )
                )
        if context.scope["defect_source"] in {"all", "manual"}:
            for item in manual_loader(session, list(cases), context.scene):
                identity = tuple(item.get("identity") or ())
                if (
                    identity in cases
                    and item.get("review_status") == "approved"
                    and item.get("id")
                ):
                    source = item.get("source") or {}
                    current = context.saved_results.get(identity, {})
                    verified = (
                        source_key(source)
                        and tuple(source.get(key) for key in SOURCE_KEYS[:3])
                        == identity
                    )
                    current_match = bool(
                        verified
                        and source.get("target_kind") == "task_manual_defect"
                        and source.get("target_id") == item["id"]
                        and source.get("scene") == context.scene
                        and source.get("root_job_id") == current.get("root_job_id")
                        and source.get("envelope_id") == current.get("envelope_id")
                    )
                    target = _target(
                        cases[identity],
                        source.get("scene") or context.scene,
                        source,
                        "task_manual_defect",
                        item["id"],
                        item.get("rule_name") or item.get("rule_code") or "人工缺陷",
                        current_match,
                    )
                    target["source_reason"] = (
                        None
                        if current_match
                        else "not_current_round"
                        if verified
                        else "manual_source_missing"
                    )
                    targets.append(target)
        jobs = jobs_loader(
            session, [{**target, "source": "auto"} for target in targets]
        )
        for target in targets:
            job = jobs.get(target["root_job_id"])
            try:
                target["source_known"] = bool(
                    target.pop("unique")
                    and job
                    and source_key(target)
                    and _workspace_scene_from_job(
                        job, identity=tuple(target[key] for key in SOURCE_KEYS[:3])
                    )
                    == context.scene
                )
            except RecordReviewConflict:
                target["source_known"] = False
        wanted = sorted(
            {
                tuple(target[key] for key in CASE_SOURCE_KEYS)
                for target in targets
                if target["source_known"]
            }
        )
        target_keys = {
            source_key(target) for target in targets if target["source_known"]
        }
        tasks, appeals = {}, defaultdict(list)
        for owner, result in ((Task, tasks), (QCAppeal, appeals)):
            columns = [getattr(owner, key) for key in CASE_SOURCE_KEYS]
            for start in range(0, max(1, len(wanted)), 100):
                for value in session.scalars(
                    select(owner).where(
                        tuple_(*columns).in_(wanted[start : start + 100])
                    )
                ):
                    key = source_key(
                        {name: getattr(value, name) for name in SOURCE_KEYS}
                    )
                    if key not in target_keys:
                        continue
                    if owner is Task:
                        if key in result:
                            raise RuntimeError("整改来源不唯一")
                        result[key] = value
                    else:
                        result[key].append(value)
        histories = defaultdict(list)
        task_ids = sorted(task.id for task in tasks.values())
        for start in range(0, max(1, len(task_ids)), 500):
            for event in session.scalars(
                select(Event).where(
                    Event.rectification_id.in_(task_ids[start : start + 500])
                )
            ):
                histories[event.rectification_id].append(event)
        rows = []
        for target in targets:
            key = source_key(target) if target["source_known"] else None
            task = tasks.get(key)
            events = histories.get(task.id, []) if task else []
            labels, state, submission_id, urge_ids = classify_rectification(
                task, events
            )
            if not target["source_known"]:
                state = "source_unknown"
            related_appeals = appeals.get(key, [])
            for appeal in related_appeals:
                label = {
                    "pending": "clinical_appeal",
                    "reviewing": "clinical_appeal",
                    "approved": "appeal_approved",
                    "rejected": "appeal_rejected",
                }.get(appeal.status)
                if label:
                    labels.append(label)
            rows.append(
                {
                    **target,
                    "labels": sorted(set(labels)),
                    "rectification_state": state,
                    "rectification_id": task.id if task else None,
                    "assignee_name": task.assignee_name if task else None,
                    "submission_event_id": submission_id,
                    "submission_urge_ids": urge_ids if submission_id else [],
                    "current_urge_ids": urge_ids if not submission_id else [],
                    "appeals": [
                        {"id": appeal.id, "status": appeal.status}
                        for appeal in related_appeals
                    ],
                    "events": [
                        {
                            "id": event.id,
                            "version": event.version,
                            "action": event.action,
                            "new_status": event.new_status,
                            "comment": event.comment,
                            "created_at": event.created_at,
                            "related_event_id": event.related_event_id,
                        }
                        for event in sorted(events, key=lambda value: value.version)
                    ],
                }
            )
        return {
            "scope": context.scope,
            "contract_status": "assumed_unconfirmed",
            "assumptions": ASSUMPTIONS,
            "labels": [
                {
                    "key": key,
                    "label": label,
                    "defect_total": sum(key in row["labels"] for row in rows),
                    "case_total": len(
                        {
                            tuple(row[name] for name in SOURCE_KEYS[:3])
                            for row in rows
                            if key in row["labels"]
                        }
                    ),
                }
                for key, label in LABELS.items()
            ],
            "state_counts": {
                state: sum(row["rectification_state"] == state for row in rows)
                for state in (
                    "not_dispatched",
                    "source_unknown",
                    "history_unknown",
                    "pending_acceptance",
                )
            },
            "rows": rows,
        }


def _target(row, scene, raw, kind, identifier, label, unique):
    return dict(zip(SOURCE_KEYS[:3], row.identity)) | {
        "scene": scene,
        "target_kind": kind,
        "target_id": identifier,
        "target_label": label,
        "root_job_id": str(raw.get("root_job_id") or ""),
        "envelope_id": str(raw.get("envelope_id") or ""),
        "unique": unique,
        "patient_name": row.patient_name,
        "department": row.department,
        "doctor": row.doctor,
    }


def filtered_rows(analysis, label=None):
    if (
        label is not None
        and label not in LABELS
        and label
        not in {
            "not_dispatched",
            "source_unknown",
            "history_unknown",
            "pending_acceptance",
        }
    ):
        raise RecordQualityReportInvalid("整改分析标签无效")
    return sorted(
        (
            row
            for row in analysis["rows"]
            if label is None
            or label in row["labels"]
            or row["rectification_state"] == label
        ),
        key=lambda row: tuple(str(row[key]) for key in SOURCE_KEYS),
    )


def page(analysis, *, label=None, page=1, page_size=20):
    if (
        isinstance(page, bool)
        or not isinstance(page, int)
        or page < 1
        or isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or not 1 <= page_size <= 100
    ):
        raise RecordQualityReportInvalid("整改分析分页无效")
    rows = filtered_rows(analysis, label)
    return {key: value for key, value in analysis.items() if key != "rows"} | {
        "total": len(rows),
        "page": page,
        "page_size": page_size,
        "filter_label": label,
        "items": rows[(page - 1) * page_size : page * page_size],
    }


def export_csv(analysis, *, label=None):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    fields = (
        *SOURCE_KEYS,
        "target_label",
        "patient_name",
        "department",
        "doctor",
        "rectification_state",
        "rectification_id",
        "submission_event_id",
        "submission_urge_ids",
        "current_urge_ids",
    )
    writer.writerow([*fields, "labels", "统计口径"])
    for row in filtered_rows(analysis, label):
        writer.writerow(
            [
                *[
                    _csv_cell(
                        "未知"
                        if row.get(key) is None
                        else ",".join(row[key])
                        if isinstance(row[key], list)
                        else row[key]
                    )
                    for key in fields
                ],
                "、".join(LABELS[key] for key in row["labels"]),
                "七标签待确认，可重叠；已整改仅验收通过，催办按提交时提醒",
            ]
        )
    return output.getvalue().encode("utf-8-sig")
