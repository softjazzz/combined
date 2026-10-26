"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

import json
from typing import Any, Iterable

from sqlalchemy import select, tuple_
from sqlalchemy.exc import SQLAlchemyError

from ..database.connection import SessionLocal
from ..database.models.v36_reports import QCRecordReview
from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY

_IN_CHUNK = 500
_IDENTITY_KEYS = ("institute_id", "patient_id", "visit_id")


def _batch_job_table():
    from .custom_qc_workspace_service import _batch_jobs_table

    return _batch_jobs_table(readonly=True)


class RecordReviewConflict(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class RecordReviewUnavailable(RuntimeError):
    pass


def _require_session() -> None:
    if SessionLocal is None:
        raise RecordReviewUnavailable("数据库会话不可用")


def _chunks(values: Iterable[Any]) -> Iterable[list[Any]]:
    items = list(values)
    for start in range(0, len(items), _IN_CHUNK):
        yield items[start : start + _IN_CHUNK]


def _stage_from_decisions(decisions: list[Any], job_id: str, envelope_id: str) -> str:
    """decisions 须已按 created_at、id 倒序；只看其他结果对象上的最近一次决定。"""
    for row in decisions:
        if row.job_id == job_id and row.envelope_id == envelope_id:
            continue
        return "recheck" if row.decision == "doubtful" else "initial"
    return "initial"


def _derive_state(
    decisions: list[Any], job_id: str, envelope_id: str
) -> tuple[str, str, Any | None]:
    """单病例与批量共用的唯一状态推导：返回 (state, stage, 当前决定行或 None)。

    decisions 须为同三坐标 + rule_set_key 的全部决定，按 created_at、id 倒序。
    """
    current = next(
        (
            row
            for row in decisions
            if row.job_id == job_id and row.envelope_id == envelope_id
        ),
        None,
    )
    if current is not None:
        return current.decision, current.stage, current
    stage = _stage_from_decisions(decisions, job_id, envelope_id)
    return ("pending_recheck" if stage == "recheck" else "pending_review"), stage, None


def _review_scene(value: Any) -> str | None:
    """把任务/作业场景规范到工作台场景；未知值不猜测。"""
    normalized = str(value or "").strip().lower()
    return {
        "running": "running",
        "final": "final",
        "outpatient": "outpatient_emergency",
        "outpatient_emergency": "outpatient_emergency",
    }.get(normalized)


def _workspace_scene_from_job(row: Any, *, identity: tuple[str, str, str]) -> str:
    """单例与批量读取共用冻结场景判定，批量调用不重复查询任务。"""
    try:
        filters = json.loads(row["filters_json"] or "{}")
    except (TypeError, ValueError) as exc:
        raise RecordReviewConflict(
            "result_unavailable", "质控结果缺少可信场景"
        ) from exc
    if not isinstance(filters, dict):
        raise RecordReviewConflict("result_unavailable", "质控结果缺少可信场景")

    raw_snapshot = filters.get("record_scene_snapshot")
    if raw_snapshot is not None and not isinstance(raw_snapshot, list):
        raise RecordReviewConflict("result_unavailable", "质控结果场景快照格式无效")

    snapshot_scenes: set[str] = set()
    matched_snapshot = False
    for raw in raw_snapshot or []:
        if not isinstance(raw, dict):
            raise RecordReviewConflict("result_unavailable", "质控结果场景快照格式无效")
        snapshot_identity = tuple(
            str(raw.get(key) or "").strip() for key in _IDENTITY_KEYS
        )
        if snapshot_identity != identity:
            continue
        matched_snapshot = True
        scene = _review_scene(raw.get("resolved_scene") or raw.get("record_scene"))
        if scene is None:
            raise RecordReviewConflict("result_unavailable", "质控结果场景快照无效")
        snapshot_scenes.add(scene)
    if len(snapshot_scenes) > 1:
        raise RecordReviewConflict("result_unavailable", "质控结果场景快照冲突")
    if matched_snapshot:
        # 混合范围 job 的根 scene 只描述任务外壳；病例快照是单病例归属的权威 owner。
        return next(iter(snapshot_scenes))
    if raw_snapshot is not None:
        raise RecordReviewConflict("result_unavailable", "质控结果缺少当前病例场景快照")

    job_scene = _review_scene(row["scene"])
    scope_scene = _review_scene(row["scope"])
    if job_scene is not None and scope_scene is not None and job_scene != scope_scene:
        raise RecordReviewConflict("result_unavailable", "质控结果根场景冲突")
    scene = job_scene or scope_scene
    if scene is None:
        raise RecordReviewConflict("result_unavailable", "质控结果缺少可信场景")
    return scene


def _normalize_identity(
    institute_id: Any, patient_id: Any, visit_id: Any
) -> tuple[str, str, str] | None:
    parts = []
    for value in (institute_id, patient_id, visit_id):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 128:
            return None
        parts.append(value.strip())
    return parts[0], parts[1], parts[2]


def _batch_anchors(
    results: Iterable[Any],
) -> dict[tuple[str, str, str], tuple[str, str]]:
    """批量锚点校验：锚点不完整或规则集非 LX0609 的病例直接跳过。"""
    anchors: dict[tuple[str, str, str], tuple[str, str]] = {}
    for item in results:
        if (
            not isinstance(item, dict)
            or item.get("rule_set_key") != LUXIAN_0609_RULE_SET_KEY
        ):
            continue
        identity = _normalize_identity(
            item.get("institute_id"), item.get("patient_id"), item.get("visit_id")
        )
        job_id = str(item.get("job_id") or "").strip()
        envelope_id = str(item.get("envelope_id") or "").strip()
        if identity is None or not job_id or not envelope_id:
            continue
        anchors[identity] = (job_id, envelope_id)
    return anchors


def _batch_case_decisions(
    session: Any,
    anchors: dict[tuple[str, str, str], tuple[str, str]],
) -> dict[tuple[str, str, str], list[Any]]:
    """列表挂载与导出共用的唯一批量决定查询：按 visit_id 分块，倒序。"""
    decisions_by_case: dict[tuple[str, str, str], list[Any]] = {}
    for chunk in _chunks(sorted(anchors)):
        for row in session.execute(
            select(
                QCRecordReview.id,
                QCRecordReview.institute_id,
                QCRecordReview.patient_id,
                QCRecordReview.visit_id,
                QCRecordReview.job_id,
                QCRecordReview.envelope_id,
                QCRecordReview.stage,
                QCRecordReview.decision,
                QCRecordReview.reason,
                QCRecordReview.reviewer_id,
                QCRecordReview.created_at,
            )
            .where(
                tuple_(
                    QCRecordReview.institute_id,
                    QCRecordReview.patient_id,
                    QCRecordReview.visit_id,
                ).in_(chunk),
                QCRecordReview.rule_set_key == LUXIAN_0609_RULE_SET_KEY,
            )
            .order_by(QCRecordReview.created_at.desc(), QCRecordReview.id.desc()),
            execution_options=(
                {"schema_translate_map": {None: "qc"}}
                if session.get_bind().dialect.name == "postgresql"
                else {}
            ),
        ).all():
            case = (row.institute_id, row.patient_id, row.visit_id)
            if case in anchors:
                decisions_by_case.setdefault(case, []).append(row)
    return decisions_by_case


def batch_review_states(results: Iterable[Any]) -> dict[tuple[str, str, str], str]:
    """批量推导病例审核状态，供运行/终末列表挂载 review_state。

    入参每项含三坐标、job_id、envelope_id、rule_set_key；锚点不完整或规则集非 LX0609 的
    病例不出现在返回值中（调用方显示为未知）。决定按 visit_id 分块一次性读取，
    状态推导与单病例共用 _derive_state。数据库故障抛 RecordReviewUnavailable。
    """
    anchors = _batch_anchors(results)
    if not anchors:
        return {}
    _require_session()
    try:
        with SessionLocal() as session:
            decisions_by_case = _batch_case_decisions(session, anchors)
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("审核数据暂不可用") from exc
    return {
        identity: _derive_state(
            decisions_by_case.get(identity, []), job_id, envelope_id
        )[0]
        for identity, (job_id, envelope_id) in anchors.items()
    }


def batch_current_reviews(
    results: Iterable[Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """批量读取病例审核状态及“当前结果对象上的决定”，供服务端导出。

    与 batch_review_states 同一锚点校验、同一决定查询、同一 _derive_state 推导；
    额外返回当前决定的原因、审核人（显示名，缺失时为 None）与决定时间（库内无时区 UTC）。
    尚无决定的病例 decision/reason/reviewer_*/reviewed_at 均为 None。
    锚点不完整的病例不出现在返回值中；数据库故障抛 RecordReviewUnavailable。
    """
    from .case_operation_timeline_service import _display_names

    anchors = _batch_anchors(results)
    if not anchors:
        return {}
    _require_session()
    try:
        with SessionLocal() as session:
            decisions_by_case = _batch_case_decisions(session, anchors)
            derived = {
                identity: _derive_state(
                    decisions_by_case.get(identity, []), job_id, envelope_id
                )
                for identity, (job_id, envelope_id) in anchors.items()
            }
            reviewer_ids = {
                str(current.reviewer_id)
                for _, _, current in derived.values()
                if current is not None and current.reviewer_id
            }
            names = _display_names(session, reviewer_ids)
    except SQLAlchemyError as exc:
        raise RecordReviewUnavailable("审核数据暂不可用") from exc
    views: dict[tuple[str, str, str], dict[str, Any]] = {}
    for identity, (state, _stage, current) in derived.items():
        reviewer_id = (
            str(current.reviewer_id)
            if current is not None and current.reviewer_id
            else None
        )
        views[identity] = {
            "state": state,
            "decision": current.decision if current is not None else None,
            "reason": current.reason if current is not None else None,
            "reviewer_id": reviewer_id,
            "reviewer_name": names.get(reviewer_id) if reviewer_id else None,
            "reviewed_at": current.created_at if current is not None else None,
        }
    return views
