"""现代申诉的只读 workspace 目标解析；不负责授权、计分或创建申诉。"""

from __future__ import annotations

from typing import Any, Callable

from . import record_review_service
from .record_review_service import (
    RecordReviewConflict,
    RecordReviewInvalid,
    RecordReviewNotFound,
    RecordReviewUnavailable,
)
from .scoring_service import project_customer_items

TARGET_CANONICAL_DEFECT = "canonical_defect"
TARGET_SCORE = "score"
TARGET_KINDS = frozenset({TARGET_CANONICAL_DEFECT, TARGET_SCORE})


class AppealWorkspaceTargetInvalid(ValueError):
    pass


class AppealWorkspaceTargetNotFound(LookupError):
    pass


class AppealWorkspaceTargetConflict(ValueError):
    pass


class AppealWorkspaceTargetUnavailable(RuntimeError):
    pass


def _project_items(raw_items: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        raise AppealWorkspaceTargetUnavailable("质控结果条目暂不可用")
    try:
        projected = project_customer_items(raw_items)
    except Exception as exc:  # noqa: BLE001 - 对外固定脱敏错误，不泄露结果正文
        raise AppealWorkspaceTargetUnavailable("质控结果条目暂不可用") from exc
    if not isinstance(projected, list) or any(not isinstance(item, dict) for item in projected):
        raise AppealWorkspaceTargetUnavailable("质控结果条目暂不可用")
    return projected


def _map_source_error(exc: Exception) -> Exception:
    if isinstance(exc, RecordReviewInvalid):
        return AppealWorkspaceTargetInvalid(str(exc))
    if isinstance(exc, RecordReviewNotFound):
        return AppealWorkspaceTargetNotFound("质控结果不存在")
    if isinstance(exc, RecordReviewConflict):
        return AppealWorkspaceTargetConflict(str(exc))
    if isinstance(exc, RecordReviewUnavailable):
        return AppealWorkspaceTargetUnavailable("质控结果来源暂不可用")
    return AppealWorkspaceTargetUnavailable("质控结果来源暂不可用")


def resolve_workspace_appeal_target(
    *, target_kind: str, institute_id: str, patient_id: str, visit_id: str,
    expected_job_id: str, expected_envelope_id: str, rule_id: str | None = None,
    workspace_factory: Callable[[], Any] | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """解析可信目标；不授予申诉权限，也不写库、不计算分数。

    返回的是调用时的候选事实，不能作为后续写入的持续有效凭据。即使传入
    ``session``，也只重验精确 Envelope，不阻止并发新结果成为 latest。
    """
    if target_kind not in TARGET_KINDS:
        raise AppealWorkspaceTargetInvalid("申诉目标类型无效")
    normalized_rule_id = str(rule_id or "").strip().upper()
    if target_kind == TARGET_CANONICAL_DEFECT and (
        not normalized_rule_id or len(normalized_rule_id) > 100
    ):
        raise AppealWorkspaceTargetInvalid("缺陷规则 ID 无效")
    if target_kind == TARGET_SCORE and rule_id is not None:
        raise AppealWorkspaceTargetInvalid("评分申诉不得指定缺陷规则")

    try:
        source = record_review_service.resolve_workspace_result_reference(
            institute_id=institute_id, patient_id=patient_id, visit_id=visit_id,
            expected_job_id=expected_job_id, expected_envelope_id=expected_envelope_id,
            workspace_factory=workspace_factory, session=session,
        )
    except Exception as exc:  # noqa: BLE001 - 统一映射为本模块稳定错误合同
        raise _map_source_error(exc) from exc

    customer_items = _project_items(source.get("items"))
    base = {
        "target_kind": target_kind,
        "target_id": source["envelope_id"] if target_kind == TARGET_SCORE else normalized_rule_id,
        "institute_id": source["institute_id"],
        "patient_id": source["patient_id"],
        "visit_id": source["visit_id"],
        "scene": source["scene"],
        "root_job_id": source["root_job_id"],
        "envelope_id": source["envelope_id"],
        "rule_set_key": source["rule_set_key"],
        "rule_set_version": source["rule_set_version"],
    }
    if target_kind == TARGET_SCORE:
        return {**base, "customer_items": customer_items}

    matches = [
        item for item in customer_items
        if str(item.get("rule_id") or "").strip().upper() == normalized_rule_id
    ]
    if not matches:
        raise AppealWorkspaceTargetNotFound("缺陷规则不在当前质控结果中")
    if len(matches) != 1:
        raise AppealWorkspaceTargetConflict("当前质控结果中的缺陷规则不唯一")
    if matches[0].get("is_confirmed_issue") is not True:
        raise AppealWorkspaceTargetConflict("当前规则不是已确认缺陷")
    return base


__all__ = [
    "AppealWorkspaceTargetConflict",
    "AppealWorkspaceTargetInvalid",
    "AppealWorkspaceTargetNotFound",
    "AppealWorkspaceTargetUnavailable",
    "resolve_workspace_appeal_target",
]
