"""任务人工缺陷的现代申诉目标只读解析。

解析只证明缺陷来自哪一次已冻结的质控结果，不授予任何用户申诉权限，也不判断
人工缺陷处于何种审核状态时可以申诉。
"""

from __future__ import annotations

import json
from contextlib import nullcontext
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..database.connection import SessionLocal
from ..database.models.qc import QCDefect, QCDefectHistory, QCTaskQCRun, QCTaskRecord
from .qc_workspace.canonical_result_store import CanonicalResultStore


class AppealManualTargetNotFound(LookupError):
    """指定人工缺陷不存在。"""


class AppealManualTargetConflict(ValueError):
    """人工缺陷的冻结来源链不完整或互相冲突。"""


class AppealManualTargetUnavailable(RuntimeError):
    """人工缺陷来源暂时无法读取。"""


_SCENES = frozenset({"running", "final", "outpatient_emergency"})
_IDENTITY_KEYS = ("institute_id", "patient_id", "visit_id")


def _envelope_table() -> Any:
    """延迟读取 Envelope 表，便于 SQLite 测试替换无 schema 的同构表。"""
    from .custom_qc_workspace_service import _record_result_envelopes_table

    return _record_result_envelopes_table()


def _text(value: Any, *, maximum: int = 128) -> str | None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        return None
    return value if len(value) <= maximum else None


def _scene(value: Any) -> str | None:
    if value == "outpatient":
        return "outpatient_emergency"
    return value if value in _SCENES else None


def _history_details(row: Any) -> dict[str, Any] | None:
    try:
        value = json.loads(row.details)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _identity(mapping: Any) -> tuple[str, str, str] | None:
    parts = tuple(_text(mapping.get(key)) for key in _IDENTITY_KEYS)
    if any(part is None for part in parts):
        return None
    return parts  # type: ignore[return-value]


def _job_source(
    session: Session, *, workspace_factory: Callable[[], Any], job_id: str, actor_id: str,
    task_id: str, run_number: int, identity: tuple[str, str, str], scene: str,
    lock: bool,
) -> tuple[str, str]:
    try:
        workspace = workspace_factory()
        table = workspace._batch_job_table
        statement = select(table).where(
            table.c.id == job_id,
            table.c.created_by == actor_id,
        )
        job = session.execute(
            statement.with_for_update(read=True) if lock else statement
        ).mappings().first()
    except Exception as exc:
        raise AppealManualTargetUnavailable("质控运行来源暂不可用") from exc
    if job is None:
        raise AppealManualTargetConflict("人工缺陷对应的质控运行不存在")
    try:
        filters = json.loads(job.get("filters_json"))
    except (TypeError, ValueError):
        filters = None
    if not isinstance(filters, dict):
        raise AppealManualTargetConflict("人工缺陷对应的质控运行缺少冻结配置")
    rule_set_key = _text(filters.get("rule_set_key"), maximum=96)
    rule_set_version = _text(filters.get("rule_set_version"), maximum=96)
    refs = filters.get("record_refs")
    identities = [_identity(item) for item in refs] if isinstance(refs, list) else []
    if (
        _text(job.get("id"), maximum=36) != job_id
        or _text(job.get("created_by"), maximum=64) != actor_id
        or _text(filters.get("task_id"), maximum=36) != task_id
        or str(filters.get("task_run_number") or "") != str(run_number)
        or rule_set_key is None
        or rule_set_version is None
        or _scene(filters.get("query_scope")) != scene
        or not identities
        or any(item is None for item in identities)
        or len(set(identities)) != len(identities)
        or identity not in identities
    ):
        raise AppealManualTargetConflict("人工缺陷与历史质控运行不一致")
    return rule_set_key, rule_set_version


def _resolve(
    session: Session, *, defect_id: str, workspace_factory: Callable[[], Any], lock: bool,
) -> dict[str, Any]:
    defect_query = select(QCDefect).where(QCDefect.id == defect_id)
    defect = session.execute(
        defect_query.with_for_update(read=True) if lock else defect_query
    ).scalar_one_or_none()
    if defect is None:
        raise AppealManualTargetNotFound("人工缺陷不存在")

    identity = _identity({key: getattr(defect, key) for key in _IDENTITY_KEYS})
    actor_id = _text(defect.manual_created_by, maximum=64)
    frozen_scene = _scene(defect.scene)
    if (
        defect.identity_version != 1
        or defect.source_key != "task_assigned_qc"
        or defect.origin != "manual"
        or identity is None
        or actor_id is None
        or frozen_scene is None
    ):
        raise AppealManualTargetConflict("缺陷不是来源完整的任务人工缺陷")

    history_query = (
        select(QCDefectHistory).where(
            QCDefectHistory.defect_id == defect_id,
            QCDefectHistory.action == "manual_create",
        ).order_by(QCDefectHistory.created_at, QCDefectHistory.id).limit(2)
    )
    histories = session.execute(
        history_query.with_for_update(read=True) if lock else history_query
    ).scalars().all()
    if len(histories) != 1 or histories[0].actor_id != actor_id:
        raise AppealManualTargetConflict("人工缺陷创建历史不唯一")
    details = _history_details(histories[0])
    if details is None:
        raise AppealManualTargetConflict("人工缺陷创建历史无效")

    task_id = _text(details.get("task_id"), maximum=36)
    task_record_id = _text(details.get("task_record_id"), maximum=36)
    job_id = _text(details.get("job_id"), maximum=36)
    run_number = details.get("run_number")
    if (
        task_id is None
        or task_record_id is None
        or job_id is None
        or type(run_number) is not int
        or run_number <= 0
        or details.get("scene") != frozen_scene
        or defect.record_id != task_record_id
    ):
        raise AppealManualTargetConflict("人工缺陷创建历史与缺陷不一致")

    record_query = select(QCTaskRecord.__table__).where(
            QCTaskRecord.id == task_record_id,
            QCTaskRecord.task_id == task_id,
    )
    record = session.execute(
        record_query.with_for_update(read=True) if lock else record_query
    ).mappings().first()
    run_query = select(QCTaskQCRun.__table__).where(
            QCTaskQCRun.task_id == task_id,
            QCTaskQCRun.run_number == run_number,
    )
    run = session.execute(
        run_query.with_for_update(read=True) if lock else run_query
    ).mappings().first()
    if (
        record is None
        or record.get("record_id") != task_record_id
        or _identity(record) != identity
        or run is None
        or run.get("run_scope") != "assigned"
        or run.get("triggered_by") != actor_id
        or run.get("job_id") != job_id
    ):
        raise AppealManualTargetConflict("人工缺陷的任务运行锚点不一致")

    rule_set_key, rule_set_version = _job_source(
        session, workspace_factory=workspace_factory, job_id=job_id, actor_id=actor_id,
        task_id=task_id, run_number=run_number, identity=identity, scene=frozen_scene,
        lock=lock,
    )
    envelope = _envelope_table()
    envelope_query = select(envelope).where(
            envelope.c.root_job_id == job_id,
            envelope.c.institute_id == identity[0],
            envelope.c.patient_id == identity[1],
            envelope.c.visit_id == identity[2],
            envelope.c.rule_set_key == rule_set_key,
            envelope.c.rule_set_version == rule_set_version,
    ).limit(2)
    rows = session.execute(
        envelope_query.with_for_update(read=True) if lock else envelope_query
    ).mappings().all()
    if len(rows) != 1:
        raise AppealManualTargetConflict("人工缺陷对应的结果信封缺失或不唯一")
    row = rows[0]
    locked_envelope_id = _text(row.get("id"), maximum=36)
    if "envelope_id" in details and (
        _text(details.get("envelope_id"), maximum=36) is None
        or details["envelope_id"] != locked_envelope_id
    ):
        raise AppealManualTargetConflict("人工缺陷创建时的结果信封已变化")
    envelope_payload, parsed_envelope_id = CanonicalResultStore(
        envelope
    ).load_selected_with_id(
        session,
        root_job_id=job_id,
        institute_id=identity[0],
        patient_id=identity[1],
        visit_id=identity[2],
        rule_set_key=rule_set_key,
        rule_set_version=rule_set_version,
    )
    if (
        locked_envelope_id is None
        or parsed_envelope_id != locked_envelope_id
        or _text(row.get("root_job_id"), maximum=36) != job_id
        or _text(row.get("created_by"), maximum=64) != actor_id
        or not isinstance(envelope_payload, dict)
        or not isinstance(envelope_payload.get("items"), list)
        or not envelope_payload["items"]
        or type(row.get("result_count")) is not int
        or row["result_count"] != len(envelope_payload["items"])
    ):
        raise AppealManualTargetConflict("人工缺陷对应的结果信封无效")

    return {
        "target_kind": "task_manual_defect",
        "target_id": defect_id,
        "institute_id": identity[0],
        "patient_id": identity[1],
        "visit_id": identity[2],
        "scene": frozen_scene,
        "root_job_id": job_id,
        "envelope_id": locked_envelope_id,
        "rule_set_key": rule_set_key,
        "rule_set_version": rule_set_version,
    }


def resolve_task_manual_defect_target(
    *, defect_id: str, workspace_factory: Callable[[], Any],
    session: Session | None = None, lock: bool = False,
) -> dict[str, Any]:
    """解析人工缺陷的冻结来源；调用方传 session 时可在自己的事务内重验。"""
    if _text(defect_id, maximum=36) is None:
        raise AppealManualTargetConflict("人工缺陷 ID 无效")
    if lock and session is None:
        raise AppealManualTargetConflict("锁定解析必须使用调用方事务")
    if session is None and SessionLocal is None:
        raise AppealManualTargetUnavailable("数据库会话不可用")

    try:
        manager = nullcontext(session) if session is not None else SessionLocal()
        with manager as active_session:
            return _resolve(
                active_session, defect_id=defect_id,
                workspace_factory=workspace_factory, lock=lock,
            )
    except (AppealManualTargetNotFound, AppealManualTargetConflict, AppealManualTargetUnavailable):
        raise
    except SQLAlchemyError as exc:
        raise AppealManualTargetUnavailable("人工缺陷来源暂不可用") from exc
    except Exception as exc:
        raise AppealManualTargetUnavailable("人工缺陷来源暂不可用") from exc


__all__ = [
    "AppealManualTargetConflict",
    "AppealManualTargetNotFound",
    "AppealManualTargetUnavailable",
    "resolve_task_manual_defect_target",
]
