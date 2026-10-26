"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

SOURCE_KEYS = (
    "job_id",
    "envelope_id",
    "institute_id",
    "patient_id",
    "visit_id",
    "rule_set_key",
    "rule_set_version",
    "scene",
)


class DefectSnapshotInvalid(ValueError):
    """缺陷快照或其冻结来源不完整。"""


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def validate_snapshot(
    snapshot: Any, *, source: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """校验完整快照，失败抛错；返回原始字典，不补历史或修改事实。"""
    if (
        not isinstance(snapshot, dict)
        or type(snapshot.get("schema_version")) is not int
    ):
        raise DefectSnapshotInvalid("缺陷快照格式无效")
    frozen = snapshot.get("source")
    if (
        snapshot["schema_version"] != 1
        or snapshot.get("complete") is not True
        or not isinstance(frozen, dict)
        or any(not _text(frozen.get(k)) for k in SOURCE_KEYS)
        or frozen["scene"] not in {"running", "final", "outpatient_emergency"}
    ):
        raise DefectSnapshotInvalid("缺陷快照来源无效")
    if source is not None and any(source.get(k) != frozen[k] for k in SOURCE_KEYS):
        raise DefectSnapshotInvalid("缺陷快照与审核来源不一致")
    try:
        if not isinstance(snapshot.get("captured_at"), str):
            raise ValueError()
        captured = datetime.fromisoformat(
            snapshot["captured_at"].replace("Z", "+00:00")
        )
        if captured.tzinfo is None:
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise DefectSnapshotInvalid("缺陷快照时间无效") from exc
    if source is not None and source.get("created_at") is not None:
        expected = source["created_at"]
        if not isinstance(expected, datetime):
            raise DefectSnapshotInvalid("审核事件时间无效")
        expected_utc = (
            expected.astimezone(timezone.utc).replace(tzinfo=None)
            if expected.tzinfo
            else expected
        )
        if captured.astimezone(timezone.utc).replace(tzinfo=None) != expected_utc:
            raise DefectSnapshotInvalid("缺陷快照时间与审核事件不一致")
    for kind, keys in (
        ("auto", ("defect_id", "rule_id")),
        (
            "manual",
            ("defect_id", "created_by", "creation_history_id", "approval_history_id"),
        ),
    ):
        group = snapshot.get(kind)
        if (
            not isinstance(group, dict)
            or type(group.get("count")) is not int
            or not isinstance(group.get("items"), list)
            or group["count"] != len(group["items"])
        ):
            raise DefectSnapshotInvalid("缺陷快照数量无效")
        ids = set()
        for item in group["items"]:
            if not isinstance(item, dict) or any(not _text(item.get(k)) for k in keys):
                raise DefectSnapshotInvalid("缺陷快照条目无效")
            if item["defect_id"] in ids or (
                kind == "auto" and item["defect_id"] != item["rule_id"]
            ):
                raise DefectSnapshotInvalid("缺陷快照条目身份冲突")
            ids.add(item["defect_id"])
    return snapshot
