"""受领质控员针对已核实任务病历创建人工缺陷。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError

from ..database.connection import SessionLocal
from ..database.models.qc import QCDefect, QCDefectHistory, QCTask, QCTaskQCRun, QCTaskRecord
from .task_qc_run_service import (
    TaskQCRunConflict,
    TaskQCRunForbidden,
    TaskQCRunNotFound,
    get_task_qc_run_record_result,
)


class TaskManualDefectNotFound(LookupError):
    pass


class TaskManualDefectForbidden(PermissionError):
    pass


class TaskManualDefectConflict(ValueError):
    pass


class TaskManualDefectUnavailable(RuntimeError):
    pass


def _validate_actor(actor_id: str) -> None:
    if not isinstance(actor_id, str) or not actor_id.strip() or len(actor_id) > 36:
        raise TaskManualDefectForbidden("当前用户缺少有效身份")
    if SessionLocal is None:
        raise TaskManualDefectUnavailable("数据库会话不可用")


def _validate_text(value: str | None, name: str, maximum: int, *, required: bool) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value.strip()) or len(value) > maximum:
        raise TaskManualDefectConflict(f"{name}无效")
    return value.strip() or None


def _context(session: Any, task_id: str, task_record_id: str, actor_id: str, *, lock: bool) -> tuple[Any, Any]:
    task_query = select(QCTask.__table__).where(QCTask.id == task_id)
    task = session.execute(task_query.with_for_update() if lock else task_query).mappings().first()
    if task is None:
        raise TaskManualDefectNotFound("任务不存在")
    record_query = select(QCTaskRecord.__table__).where(
        QCTaskRecord.id == task_record_id, QCTaskRecord.task_id == task_id,
    )
    record = session.execute(record_query.with_for_update() if lock else record_query).mappings().first()
    if record is None:
        raise TaskManualDefectNotFound("任务病历不存在")
    if record["assignee_id"] != actor_id:
        raise TaskManualDefectForbidden("当前用户未受领该病历")
    identity = tuple(record.get(key) for key in ("institute_id", "patient_id", "visit_id"))
    if (
        any(not isinstance(part, str) or not part.strip() or len(part) > 100 for part in identity)
        or record["record_id"] != record["id"]
    ):
        raise TaskManualDefectConflict("任务病历缺少完整三坐标")
    return task, record


def _verified_result(
    *, task_id: str, task_record_id: str, actor_id: str,
    run_number: int, workspace_factory: Callable[[], Any],
) -> str:
    try:
        result = get_task_qc_run_record_result(
            task_id=task_id, task_record_id=task_record_id,
            actor_id=actor_id, run_number=run_number,
            workspace_factory=workspace_factory, run_scope="assigned",
        )
    except TaskQCRunNotFound as exc:
        raise TaskManualDefectNotFound(str(exc)) from exc
    except TaskQCRunForbidden as exc:
        raise TaskManualDefectForbidden(str(exc)) from exc
    except TaskQCRunConflict as exc:
        raise TaskManualDefectConflict(str(exc)) from exc
    except RuntimeError as exc:
        raise TaskManualDefectUnavailable("质控结果暂不可用") from exc
    if (
        not isinstance(result, dict)
        or result.get("result_state") != "available"
        or result.get("task_id") != task_id
        or result.get("task_record_id") != task_record_id
        or type(result.get("run_number")) is not int
        or result["run_number"] != run_number
        or not isinstance(result.get("items"), list)
        or not result["items"]
    ):
        raise TaskManualDefectConflict("本次质控结果尚不可用于人工缺陷")
    job_id = result.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        raise TaskManualDefectConflict("任务病历质控结果缺少运行身份")
    return job_id


def _history_details(session: Any, defect_id: str, actor_id: str) -> dict[str, Any] | None:
    histories = session.execute(
        select(QCDefectHistory.details, QCDefectHistory.actor_id).where(
            QCDefectHistory.defect_id == defect_id,
            QCDefectHistory.action == "manual_create",
        ).order_by(QCDefectHistory.created_at, QCDefectHistory.id).limit(2)
    ).all()
    if len(histories) != 1 or histories[0].actor_id != actor_id:
        return None
    try:
        details = json.loads(histories[0].details)
    except (TypeError, ValueError):
        return None
    return details if isinstance(details, dict) else None


def _response(defect: Any, *, task_id: str, task_record_id: str, run_number: int) -> dict[str, Any]:
    return {
        "id": defect.id,
        "task_id": task_id,
        "task_record_id": task_record_id,
        "run_number": run_number,
        "rule_name": defect.rule_name,
        "description": defect.description,
        "severity": defect.severity,
        "suggestion": defect.suggestion,
        "evidence": defect.evidence,
        "manual_review_status": defect.manual_review_status,
        "created_at": defect.created_at,
    }


def _replay(
    session: Any, *, defect: QCDefect, record: Any, task_id: str,
    task_record_id: str, actor_id: str, run_number: int,
    rule_name: str, description: str, severity: str,
    suggestion: str | None, evidence: str | None,
) -> dict[str, Any]:
    details = _history_details(session, defect.id, actor_id)
    run = session.get(QCTaskQCRun, (task_id, run_number))
    if (
        details is None or details.get("task_id") != task_id
        or details.get("task_record_id") != task_record_id
        or details.get("run_number") != run_number
        or run is None or run.run_scope != "assigned"
        or run.triggered_by != actor_id or run.job_id != details.get("job_id")
        or defect.record_id != task_record_id
        or defect.origin != "manual"
        or defect.source_key != "task_assigned_qc"
        or defect.manual_created_by != actor_id
        or defect.identity_version != 1
        or any(getattr(defect, key) != record[key]
               for key in ("institute_id", "patient_id", "visit_id"))
        or any(getattr(defect, key) != value for key, value in (
            ("rule_name", rule_name), ("description", description),
            ("severity", severity), ("suggestion", suggestion), ("evidence", evidence),
        ))
    ):
        raise TaskManualDefectConflict("人工缺陷请求 ID 已被其他内容使用")
    return {**_response(defect, task_id=task_id, task_record_id=task_record_id,
                        run_number=run_number), "idempotent": True}


def create_task_manual_defect(
    *, task_id: str, task_record_id: str, actor_id: str, defect_id: str,
    run_number: int, rule_name: str, description: str, severity: str,
    suggestion: str | None = None, evidence: str | None = None,
    workspace_factory: Callable[[], Any],
) -> dict[str, Any]:
    """先核实受领运行结果，再原子保存人工缺陷与创建历史。"""
    _validate_actor(actor_id)
    try:
        canonical_id = str(UUID(defect_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise TaskManualDefectConflict("人工缺陷请求 ID 无效") from exc
    if canonical_id != defect_id or type(run_number) is not int or run_number <= 0:
        raise TaskManualDefectConflict("人工缺陷请求 ID 或运行序号无效")
    rule_name = _validate_text(rule_name, "规则名称", 200, required=True)
    description = _validate_text(description, "缺陷描述", 4000, required=True)
    suggestion = _validate_text(suggestion, "整改建议", 2000, required=False)
    evidence = _validate_text(evidence, "证据", 2000, required=False)
    if severity not in {"info", "warning", "error", "critical"}:
        raise TaskManualDefectConflict("缺陷级别无效")

    with SessionLocal() as session:
        _, record = _context(session, task_id, task_record_id, actor_id, lock=False)
        existing = session.get(QCDefect, defect_id)
        if existing is not None:
            return _replay(
                session, defect=existing, record=record, task_id=task_id,
                task_record_id=task_record_id, actor_id=actor_id,
                run_number=run_number, rule_name=rule_name,
                description=description, severity=severity,
                suggestion=suggestion, evidence=evidence,
            )

    job_id = _verified_result(
        task_id=task_id, task_record_id=task_record_id,
        actor_id=actor_id, run_number=run_number, workspace_factory=workspace_factory,
    )
    try:
        return _insert_verified_defect(
            task_id=task_id, task_record_id=task_record_id,
            actor_id=actor_id, defect_id=defect_id, run_number=run_number,
            rule_name=rule_name, description=description, severity=severity,
            suggestion=suggestion, evidence=evidence, job_id=job_id,
        )
    except IntegrityError:
        # 并发请求可能已抢先写入同一客户端请求 ID，回滚后重新核对。
        with SessionLocal() as session:
            _, record = _context(session, task_id, task_record_id, actor_id, lock=False)
            existing = session.get(QCDefect, defect_id)
            if existing is None:
                raise TaskManualDefectUnavailable("人工缺陷保存失败，请稍后重试")
            return _replay(
                session, defect=existing, record=record, task_id=task_id,
                task_record_id=task_record_id, actor_id=actor_id,
                run_number=run_number, rule_name=rule_name,
                description=description, severity=severity,
                suggestion=suggestion, evidence=evidence,
            )


def _insert_verified_defect(
    *, task_id: str, task_record_id: str, actor_id: str, defect_id: str,
    run_number: int, rule_name: str, description: str, severity: str,
    suggestion: str | None, evidence: str | None, job_id: str,
) -> dict[str, Any]:
    with SessionLocal() as session:
        with session.begin():
            task, record = _context(session, task_id, task_record_id, actor_id, lock=True)
            existing = session.get(QCDefect, defect_id)
            if existing is not None:
                return _replay(
                    session, defect=existing, record=record, task_id=task_id,
                    task_record_id=task_record_id, actor_id=actor_id,
                    run_number=run_number, rule_name=rule_name,
                    description=description, severity=severity,
                    suggestion=suggestion, evidence=evidence,
                )
            if task["status"] != "in_progress" or record["status"] != "in_progress":
                raise TaskManualDefectConflict("任务或病历当前状态不允许添加人工缺陷")
            run = session.execute(
                select(QCTaskQCRun.__table__).where(
                    QCTaskQCRun.task_id == task_id,
                    QCTaskQCRun.run_number == run_number,
                ).with_for_update()
            ).mappings().first()
            if run is None:
                raise TaskManualDefectNotFound("任务运行不存在")
            if run["run_scope"] != "assigned" or run["triggered_by"] != actor_id:
                raise TaskManualDefectForbidden("仅受领运行人可添加人工缺陷")
            if run["job_id"] != job_id:
                raise TaskManualDefectConflict("任务运行身份已变化")
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            defect = QCDefect(
                id=defect_id, record_id=task_record_id, identity_version=1,
                source_key="task_assigned_qc",
                institute_id=record["institute_id"], patient_id=record["patient_id"],
                visit_id=record["visit_id"],
                rule_name=rule_name, description=description, severity=severity,
                suggestion=suggestion, evidence=evidence, category="manual",
                status="pending", origin="manual", manual_review_status="pending",
                manual_created_by=actor_id, deduct_score=0.0,
                created_at=now, updated_at=now,
            )
            session.add(defect)
            session.add(QCDefectHistory(
                id=str(uuid4()), defect_id=defect_id, action="manual_create",
                actor_id=actor_id,
                details=json.dumps({
                    "task_id": task_id, "task_record_id": task_record_id,
                    "run_number": run_number, "job_id": job_id,
                }, ensure_ascii=False, sort_keys=True),
                created_at=now,
            ))
            session.flush()
            response = _response(defect, task_id=task_id,
                                 task_record_id=task_record_id, run_number=run_number)
    return {**response, "idempotent": False}


def list_task_manual_defects(
    *, task_id: str, task_record_id: str, actor_id: str,
    limit: int = 50, offset: int = 0,
) -> dict[str, Any]:
    """仅读取受领任务病历三坐标下的人工缺陷。"""
    _validate_actor(actor_id)
    if type(limit) is not int or limit < 1 or limit > 50 or type(offset) is not int or offset < 0:
        raise TaskManualDefectConflict("分页参数无效")
    with SessionLocal() as session:
        _, record = _context(session, task_id, task_record_id, actor_id, lock=False)
        predicates = (
            QCDefect.record_id == task_record_id,
            QCDefect.identity_version == 1,
            QCDefect.source_key == "task_assigned_qc",
            QCDefect.institute_id == record["institute_id"],
            QCDefect.patient_id == record["patient_id"],
            QCDefect.visit_id == record["visit_id"],
            QCDefect.origin == "manual",
            QCDefect.manual_created_by == actor_id,
            exists().where(
                QCDefectHistory.defect_id == QCDefect.id,
                QCDefectHistory.action == "manual_create",
            ),
        )
        total = session.execute(
            select(func.count(QCDefect.id)).where(*predicates)
        ).scalar_one()
        defects = session.execute(
            select(QCDefect).where(*predicates)
            .order_by(QCDefect.created_at.desc(), QCDefect.id.desc())
            .offset(offset).limit(limit)
        ).scalars().all()
        if not defects:
            return {"items": [], "total": total, "limit": limit, "offset": offset}

        histories = session.execute(
            select(QCDefectHistory).where(
                QCDefectHistory.defect_id.in_([defect.id for defect in defects]),
                QCDefectHistory.action == "manual_create",
            )
        ).scalars().all()
        by_defect: dict[str, list[QCDefectHistory]] = {}
        for history in histories:
            by_defect.setdefault(history.defect_id, []).append(history)
        run_numbers: set[int] = set()
        validated: list[tuple[QCDefect, int, str]] = []
        for defect in defects:
            rows = by_defect.get(defect.id, [])
            if len(rows) != 1 or rows[0].actor_id != actor_id:
                raise TaskManualDefectUnavailable("人工缺陷创建历史不完整")
            try:
                details = json.loads(rows[0].details)
            except (TypeError, ValueError) as exc:
                raise TaskManualDefectUnavailable("人工缺陷创建历史不完整") from exc
            if (
                not isinstance(details, dict)
                or details.get("task_id") != task_id
                or details.get("task_record_id") != task_record_id
                or type(details.get("run_number")) is not int
                or details["run_number"] <= 0
                or not isinstance(details.get("job_id"), str)
                or not details["job_id"].strip()
            ):
                raise TaskManualDefectUnavailable("人工缺陷创建历史与任务身份不一致")
            run_numbers.add(details["run_number"])
            validated.append((defect, details["run_number"], details["job_id"]))
        runs = session.execute(
            select(QCTaskQCRun).where(
                QCTaskQCRun.task_id == task_id,
                QCTaskQCRun.run_number.in_(run_numbers),
            )
        ).scalars().all()
        by_number = {run.run_number: run for run in runs}
        items = []
        for defect, run_number, job_id in validated:
            run = by_number.get(run_number)
            if (
                run is None or run.run_scope != "assigned"
                or run.triggered_by != actor_id or run.job_id != job_id
            ):
                raise TaskManualDefectUnavailable("人工缺陷创建运行与当前任务不一致")
            items.append(_response(defect, task_id=task_id,
                                   task_record_id=task_record_id,
                                   run_number=run_number))
        return {"items": items, "total": total, "limit": limit, "offset": offset}
