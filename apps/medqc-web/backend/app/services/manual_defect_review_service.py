"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

import json
from typing import Any, Iterable

from sqlalchemy import select, tuple_
from sqlalchemy.exc import SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.v36_reports import QCDefect

MANUAL_DEFECT_SCENES = frozenset({"all", "running", "final", "outpatient_emergency"})


class ManualDefectReviewInvalid(ValueError):
    """请求参数不符合合同。"""


class ManualDefectReviewUnavailable(RuntimeError):
    """数据库不可用或写入失败；对外只给脱敏提示。"""


def _manual_scope(*, scene: str = "all") -> tuple[Any, ...]:
    """人工缺陷唯一谓词；具体场景只匹配冻结值，历史 NULL 仅属于 all。"""
    if not isinstance(scene, str) or scene not in MANUAL_DEFECT_SCENES:
        raise ManualDefectReviewInvalid("场景无效")
    predicates = (
        QCDefect.origin == "manual",
        QCDefect.source_key == "task_assigned_qc",
        QCDefect.identity_version == 1,
    )
    if scene == "all":
        return predicates
    return (*predicates, QCDefect.scene == scene)


def _require_session_factory() -> Any:
    if SessionLocal is None:
        raise ManualDefectReviewUnavailable("数据库会话不可用")
    return SessionLocal


def _task_identity(rows: list[Any], created_by: str | None) -> dict[str, Any]:
    """从唯一一条 manual_create 历史中取任务坐标；历史缺失或不一致时返回空值。"""
    empty = {"task_id": None, "task_record_id": None, "run_number": None}
    if len(rows) != 1 or rows[0].actor_id != created_by:
        return empty
    try:
        details = json.loads(rows[0].details)
    except (TypeError, ValueError):
        return empty
    if not isinstance(details, dict):
        return empty
    task_id = details.get("task_id")
    task_record_id = details.get("task_record_id")
    run_number = details.get("run_number")
    if (
        not isinstance(task_id, str)
        or not task_id.strip()
        or not isinstance(task_record_id, str)
        or not task_record_id.strip()
        or type(run_number) is not int
        or run_number <= 0
    ):
        return empty
    return {
        "task_id": task_id,
        "task_record_id": task_record_id,
        "run_number": run_number,
    }


def _case_identity(
    institute_id: Any, patient_id: Any, visit_id: Any
) -> tuple[str, str, str]:
    values = (institute_id, patient_id, visit_id)
    if any(
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > 128
        for value in values
    ):
        raise ManualDefectReviewInvalid("病例三坐标无效")
    return (str(institute_id), str(patient_id), str(visit_id))


_CASE_BATCH_CHUNK = 200


def list_manual_defects_for_cases(
    identities: Iterable[tuple[str, str, str]],
    *,
    scene: str = "all",
) -> list[dict[str, Any]]:
    """按三坐标集合批量只读人工缺陷字段，供报表与工作台缺陷列表复用。

    与审核列表同一谓词；在 SQL 中按完整三坐标分块过滤。
    仅返回缺陷结果列表所需字段，不返回证据与整改建议。数据库故障抛
    ManualDefectReviewUnavailable。
    """
    wanted = {_case_identity(i, p, v) for i, p, v in identities}
    if not wanted:
        return []
    factory = _require_session_factory()
    ordered = sorted(wanted)
    rows: list[dict[str, Any]] = []
    try:
        with factory() as session:
            for start in range(0, len(ordered), _CASE_BATCH_CHUNK):
                chunk = ordered[start : start + _CASE_BATCH_CHUNK]
                for row in session.execute(
                    select(
                        QCDefect.institute_id,
                        QCDefect.patient_id,
                        QCDefect.visit_id,
                        QCDefect.id,
                        QCDefect.rule_code,
                        QCDefect.rule_name,
                        QCDefect.description,
                        QCDefect.severity,
                        QCDefect.location,
                        QCDefect.manual_review_status,
                        QCDefect.created_at,
                    ).where(
                        *_manual_scope(scene=scene),
                        tuple_(
                            QCDefect.institute_id,
                            QCDefect.patient_id,
                            QCDefect.visit_id,
                        ).in_(chunk),
                    )
                ).all():
                    identity = (
                        str(row.institute_id),
                        str(row.patient_id),
                        str(row.visit_id),
                    )
                    if identity in wanted:
                        rows.append(
                            {
                                "identity": identity,
                                "id": str(row.id),
                                "rule_code": str(row.rule_code or "").strip().upper(),
                                "rule_name": str(row.rule_name or "").strip(),
                                "description": str(row.description or "").strip(),
                                "severity": str(row.severity or "").strip(),
                                "location": str(row.location or "").strip(),
                                "review_status": row.manual_review_status,
                                "created_at": row.created_at,
                            }
                        )
    except SQLAlchemyError as exc:
        raise ManualDefectReviewUnavailable("人工缺陷读取失败") from exc
    return rows
