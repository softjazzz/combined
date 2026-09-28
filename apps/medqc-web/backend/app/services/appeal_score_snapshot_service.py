"""评分申诉的只读引用与重算快照；不创建申诉、不授予权限。"""

from __future__ import annotations

from typing import Any, Callable

from .appeal_workspace_target_service import (
    AppealWorkspaceTargetConflict,
    AppealWorkspaceTargetInvalid,
    AppealWorkspaceTargetNotFound,
    AppealWorkspaceTargetUnavailable,
    resolve_workspace_appeal_target,
)
from .scoring_service import score_result
from .scoring_standard_service import (
    ScoringStandardConflict,
    ScoringStandardInvalid,
    ScoringStandardNotFound,
    ScoringStandardUnavailable,
    get_exact_default_standard_in_session,
)


class AppealScoreSnapshotInvalid(ValueError):
    pass


class AppealScoreSnapshotNotFound(LookupError):
    pass


class AppealScoreSnapshotConflict(ValueError):
    pass


class AppealScoreSnapshotUnavailable(RuntimeError):
    pass


_STANDARD_SCENE = {
    "running": "running",
    "final": "final",
    "outpatient_emergency": "outpatient",
}


def _map_error(exc: Exception) -> Exception:
    if isinstance(exc, (AppealWorkspaceTargetInvalid, ScoringStandardInvalid)):
        return AppealScoreSnapshotInvalid(str(exc))
    if isinstance(exc, (AppealWorkspaceTargetNotFound, ScoringStandardNotFound)):
        return AppealScoreSnapshotNotFound("评分申诉引用不存在")
    if isinstance(exc, (AppealWorkspaceTargetConflict, ScoringStandardConflict)):
        return AppealScoreSnapshotConflict("评分申诉引用已变化，请刷新后重试")
    if isinstance(exc, (AppealWorkspaceTargetUnavailable, ScoringStandardUnavailable)):
        return AppealScoreSnapshotUnavailable("评分申诉快照暂不可用")
    return AppealScoreSnapshotUnavailable("评分申诉快照暂不可用")


def build_appeal_score_snapshot(
    *, session: Any, institute_id: str, patient_id: str, visit_id: str,
    expected_job_id: str, expected_envelope_id: str,
    expected_standard_id: str, expected_standard_version_seq: int,
    expected_standard_updated_at: Any,
    workspace_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """用可信结果引用和精确默认标准重算评分；调用方拥有 session/事务。

    workspace resolver 仍通过自持会话选择当前 latest DTO，再用调用方 session 回读
    精确 Envelope；因此本函数不承诺持续锁住 latest，也不等于原子创建申诉。
    """
    if session is None:
        raise AppealScoreSnapshotInvalid("评分申诉快照需要调用方数据库会话")
    try:
        target = resolve_workspace_appeal_target(
            target_kind="score",
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            expected_job_id=expected_job_id,
            expected_envelope_id=expected_envelope_id,
            workspace_factory=workspace_factory,
            session=session,
        )
        scene = _STANDARD_SCENE.get(target.get("scene"))
        if scene is None:
            raise AppealScoreSnapshotConflict("质控结果场景不可评分")
        standard = get_exact_default_standard_in_session(
            session,
            scene=scene,
            expected_standard_id=expected_standard_id,
            expected_version_seq=expected_standard_version_seq,
            expected_updated_at=expected_standard_updated_at,
            for_update=True,
        )
        if target.get("rule_set_key") != standard.get("rule_set_key"):
            raise AppealScoreSnapshotConflict("质控结果与评分标准的规则集不一致")
        scored = score_result(target.get("customer_items") or [], standard)
    except (AppealScoreSnapshotInvalid, AppealScoreSnapshotNotFound,
            AppealScoreSnapshotConflict, AppealScoreSnapshotUnavailable):
        raise
    except Exception as exc:
        raise _map_error(exc) from exc

    result_ref = {
        key: target[key]
        for key in (
            "envelope_id", "root_job_id", "institute_id", "patient_id", "visit_id",
            "rule_set_key", "rule_set_version",
        )
    }
    standard_ref = {
        "standard_id": standard["id"],
        "version_seq": standard["version_seq"],
        "updated_at": standard["updated_at"],
    }
    return {
        "result_ref": result_ref,
        "standard_ref": standard_ref,
        "score_snapshot": {
            **scored,
            "standard_version_seq": standard["version_seq"],
        },
    }


__all__ = [
    "AppealScoreSnapshotConflict",
    "AppealScoreSnapshotInvalid",
    "AppealScoreSnapshotNotFound",
    "AppealScoreSnapshotUnavailable",
    "build_appeal_score_snapshot",
]
