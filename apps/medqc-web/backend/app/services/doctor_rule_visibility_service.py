"""医生端规则结果可见性，只消费已冻结的规则版本 entry 配置。"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .rule_set_version_service import get_version_detail
from .scoring_service import ScoringScopeContextUnavailable, item_applies_to_department


class DoctorRuleVisibilityUnavailable(RuntimeError):
    """规则版本或适用配置不可可信读取。"""


def _text(value: Any) -> str:
    return str(value or "").strip()


def visible_rule_ids(
    *, rule_set_key: str, rule_set_version: str, institute_id: str, department_name: str,
) -> frozenset[str]:
    """按版本冻结配置精确计算医生可见规则；旧版本未配置时不会放行。"""

    if not all(_text(value) for value in (
        rule_set_key, rule_set_version, institute_id, department_name,
    )):
        raise DoctorRuleVisibilityUnavailable("医生端规则适用上下文不完整")
    try:
        detail = get_version_detail(rule_set_key, rule_set_version)
    except Exception as exc:  # noqa: BLE001 - 消费方统一失败关闭
        raise DoctorRuleVisibilityUnavailable("规则版本暂不可用") from exc
    visible: set[str] = set()
    for entry in detail.get("entries") or []:
        if not isinstance(entry, Mapping) or entry.get("state") != "active":
            continue
        if entry.get("doctor_visible") is not True:
            continue
        try:
            applies = item_applies_to_department(
                entry, institute_id=institute_id, department_name=department_name,
            )
        except ScoringScopeContextUnavailable:
            applies = False
        if applies:
            visible.add(_text(entry.get("rule_id")).upper())
    return frozenset(rule_id for rule_id in visible if rule_id)


def project_doctor_visible_items(
    items: Sequence[Mapping[str, Any]], *, rule_set_key: str, rule_set_version: str,
    institute_id: str, department_name: str,
) -> list[dict[str, Any]]:
    allowed = visible_rule_ids(
        rule_set_key=rule_set_key, rule_set_version=rule_set_version,
        institute_id=institute_id, department_name=department_name,
    )
    return [
        dict(item) for item in items
        if item.get("can_show_to_doctor") is True
        and _text(item.get("rule_id") or item.get("rule_code")).upper() in allowed
    ]
