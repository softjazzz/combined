from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping

from ..constants.doc_types import DOC_TYPE_MAP


SCHEMA_VERSION = "visual-condition-v1"
MAX_GROUPS = 10
MAX_CONDITIONS_PER_GROUP = 20

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_GROUP_OPERATORS = frozenset({"all", "any"})
_FIELD_OPERATORS = {
    "string": frozenset({"eq", "ne", "in", "not_in", "exists", "not_exists"}),
    "datetime": frozenset({"exists", "not_exists"}),
}
_TIME_OPERATORS = frozenset({"lt", "lte", "gt", "gte"})
_TIME_UNITS = frozenset({"minutes", "hours", "days"})

# 仅开放 programmatic_timeline 已有稳定 owner 的文书表。扩目录必须同时补 FactBuilder 证明。
_DOCUMENT_TABLES = (
    "admission_record",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "consultation_record",
    "rescue_record",
    "presurg_discussion",
    "presurg_summary",
    "surgery_record",
    "anesthesia_record",
    "postsurg_firstcourse_record",
    "discharge_record",
)
_RECORD_FACTS = {
    "record.department": {"label": "当前病例科室", "value_type": "string"},
    "record.admission_datetime": {"label": "入院时间", "value_type": "datetime"},
    "record.discharge_datetime": {"label": "出院时间", "value_type": "datetime"},
}


class VisualConditionInvalid(ValueError):
    pass


def _operator_options(value_type: str) -> list[dict[str, Any]]:
    labels = {
        "eq": "等于",
        "ne": "不等于",
        "in": "属于",
        "not_in": "不属于",
        "exists": "存在",
        "not_exists": "不存在",
    }
    return [
        {
            "value": operator,
            "label": labels[operator],
            "value_required": operator not in {"exists", "not_exists"},
        }
        for operator in sorted(_FIELD_OPERATORS[value_type])
    ]


def document_types() -> list[dict[str, str]]:
    return [{"value": key, "label": DOC_TYPE_MAP[key]} for key in _DOCUMENT_TABLES]


def _time_fact_options() -> list[dict[str, str]]:
    options = [
        {"value": key, "label": value["label"]}
        for key, value in _RECORD_FACTS.items()
        if value["value_type"] == "datetime"
    ]
    for source_table in _DOCUMENT_TABLES:
        label = DOC_TYPE_MAP[source_table]
        options.extend(
            (
                {"value": f"document.{source_table}.earliest_authored_at", "label": f"最早{label}记录时间"},
                {"value": f"document.{source_table}.latest_authored_at", "label": f"最晚{label}记录时间"},
            )
        )
    return options


def visual_condition_options() -> dict[str, Any]:
    time_fields = _time_fact_options()
    time_values = [item["value"] for item in time_fields]
    return {
        "schema_version": SCHEMA_VERSION,
        "fields": [
            {
                "key": key,
                "label": value["label"],
                "value_type": value["value_type"],
                "kind": "record",
                "operators": _operator_options(value["value_type"]),
            }
            for key, value in _RECORD_FACTS.items()
        ],
        "document_types": document_types(),
        "group_operators": ["all", "any"],
        "timeliness": {
            "start_fields": deepcopy(time_fields),
            "end_fields": deepcopy(time_fields),
            "allowed_pairs": [
                {"start_fact": start, "end_fact": end}
                for start in time_values
                for end in time_values
                if start != end
            ],
            "operators": [
                {"value": value, "label": {"lt": "小于", "lte": "小于等于", "gt": "大于", "gte": "大于等于"}[value]}
                for value in ("lt", "lte", "gt", "gte")
            ],
            "units": [
                {"value": value, "label": {"minutes": "分钟", "hours": "小时", "days": "天"}[value]}
                for value in ("minutes", "hours", "days")
            ],
        },
        "limits": {
            "max_groups": MAX_GROUPS,
            "max_conditions_per_group": MAX_CONDITIONS_PER_GROUP,
        },
        "result_semantics": {
            "true": "non_compliant",
            "false": "compliant",
            "unknown": "data_gap",
        },
    }


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise VisualConditionInvalid(f"{field} 必须是对象")
    return dict(value)


def _exact_keys(value: Mapping[str, Any], *, allowed: set[str], field: str) -> None:
    extras = set(value) - allowed
    if extras:
        raise VisualConditionInvalid(f"{field} 包含不支持字段: {', '.join(sorted(extras))}")


def _condition_id(value: Any, field: str) -> str:
    normalized = str(value or "").strip()
    if not _ID_PATTERN.fullmatch(normalized):
        raise VisualConditionInvalid(f"{field} 仅允许1-64位字母、数字、下划线或连字符")
    return normalized


def _normalize_field_condition(raw: dict[str, Any], field: str) -> dict[str, Any]:
    _exact_keys(raw, allowed={"id", "kind", "fact_key", "operator", "value"}, field=field)
    fact_key = str(raw.get("fact_key") or "").strip()
    fact = _RECORD_FACTS.get(fact_key)
    if not fact:
        raise VisualConditionInvalid(f"{field}.fact_key 不在可信字段目录")
    operator = str(raw.get("operator") or "").strip()
    if operator not in _FIELD_OPERATORS[fact["value_type"]]:
        raise VisualConditionInvalid(f"{field}.operator 与字段类型不匹配")
    result = {
        "id": _condition_id(raw.get("id"), f"{field}.id"),
        "kind": "field",
        "fact_key": fact_key,
        "operator": operator,
    }
    if operator in {"exists", "not_exists"}:
        if "value" in raw:
            raise VisualConditionInvalid(f"{field}.value 不适用于存在性操作")
    else:
        value = raw.get("value")
        if operator in {"in", "not_in"}:
            if not isinstance(value, list) or not value or len(value) > 50:
                raise VisualConditionInvalid(f"{field}.value 必须是1-50项数组")
            if any(not isinstance(item, str) for item in value):
                raise VisualConditionInvalid(f"{field}.value 每项必须是字符串")
            normalized = [item.strip() for item in value]
            if any(not item or len(item) > 200 for item in normalized):
                raise VisualConditionInvalid(f"{field}.value 包含空值或超长值")
            result["value"] = normalized
        else:
            if not isinstance(value, str):
                raise VisualConditionInvalid(f"{field}.value 必须是字符串")
            normalized = value.strip()
            if not normalized or len(normalized) > 200:
                raise VisualConditionInvalid(f"{field}.value 必须是1-200字符")
            result["value"] = normalized
    return result


def _normalize_document_presence(raw: dict[str, Any], field: str) -> dict[str, Any]:
    _exact_keys(raw, allowed={"id", "kind", "document_type", "operator"}, field=field)
    document_type = str(raw.get("document_type") or "").strip()
    if document_type not in _DOCUMENT_TABLES:
        raise VisualConditionInvalid(f"{field}.document_type 不在可信文书目录")
    operator = str(raw.get("operator") or "").strip()
    if operator not in {"exists", "not_exists"}:
        raise VisualConditionInvalid(f"{field}.operator 仅支持 exists/not_exists")
    return {
        "id": _condition_id(raw.get("id"), f"{field}.id"),
        "kind": "document_presence",
        "document_type": document_type,
        "operator": operator,
    }


def _normalize_timeliness(raw: dict[str, Any], field: str) -> dict[str, Any]:
    _exact_keys(
        raw,
        allowed={"id", "kind", "start_fact", "end_fact", "operator", "threshold"},
        field=field,
    )
    allowed_facts = {item["value"] for item in _time_fact_options()}
    start_fact = str(raw.get("start_fact") or "").strip()
    end_fact = str(raw.get("end_fact") or "").strip()
    if start_fact not in allowed_facts or end_fact not in allowed_facts:
        raise VisualConditionInvalid(f"{field} 使用了目录外时间事实")
    if start_fact == end_fact:
        raise VisualConditionInvalid(f"{field} 起止事实不能相同")
    operator = str(raw.get("operator") or "").strip()
    if operator not in _TIME_OPERATORS:
        raise VisualConditionInvalid(f"{field}.operator 不支持")
    threshold = _mapping(raw.get("threshold"), f"{field}.threshold")
    _exact_keys(threshold, allowed={"value", "unit"}, field=f"{field}.threshold")
    value = threshold.get("value")
    unit = str(threshold.get("unit") or "").strip()
    if type(value) is not int or not 1 <= value <= 525600:
        raise VisualConditionInvalid(f"{field}.threshold.value 必须是1-525600的整数")
    if unit not in _TIME_UNITS:
        raise VisualConditionInvalid(f"{field}.threshold.unit 不支持")
    return {
        "id": _condition_id(raw.get("id"), f"{field}.id"),
        "kind": "timeliness",
        "start_fact": start_fact,
        "end_fact": end_fact,
        "operator": operator,
        "threshold": {"value": value, "unit": unit},
    }


def normalize_visual_condition(value: Any) -> dict[str, Any]:
    raw = _mapping(value, "visual_condition")
    _exact_keys(raw, allowed={"schema_version", "root_operator", "groups"}, field="visual_condition")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise VisualConditionInvalid("visual_condition.schema_version 不支持")
    root_operator = str(raw.get("root_operator") or "").strip()
    if root_operator not in _GROUP_OPERATORS:
        raise VisualConditionInvalid("visual_condition.root_operator 仅支持 all/any")
    raw_groups = raw.get("groups")
    if not isinstance(raw_groups, list) or not 1 <= len(raw_groups) <= MAX_GROUPS:
        raise VisualConditionInvalid(f"visual_condition.groups 必须是1-{MAX_GROUPS}组")
    groups: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for group_index, raw_group in enumerate(raw_groups):
        field = f"visual_condition.groups[{group_index}]"
        group = _mapping(raw_group, field)
        _exact_keys(group, allowed={"id", "operator", "conditions"}, field=field)
        group_id = _condition_id(group.get("id"), f"{field}.id")
        operator = str(group.get("operator") or "").strip()
        if operator not in _GROUP_OPERATORS:
            raise VisualConditionInvalid(f"{field}.operator 仅支持 all/any")
        conditions = group.get("conditions")
        if not isinstance(conditions, list) or not 1 <= len(conditions) <= MAX_CONDITIONS_PER_GROUP:
            raise VisualConditionInvalid(f"{field}.conditions 必须是1-{MAX_CONDITIONS_PER_GROUP}项")
        normalized_conditions = []
        if group_id in seen_ids:
            raise VisualConditionInvalid("组和条件 id 必须唯一")
        seen_ids.add(group_id)
        for condition_index, raw_condition in enumerate(conditions):
            condition_field = f"{field}.conditions[{condition_index}]"
            condition = _mapping(raw_condition, condition_field)
            kind = str(condition.get("kind") or "").strip()
            if kind == "field":
                normalized = _normalize_field_condition(condition, condition_field)
            elif kind == "document_presence":
                normalized = _normalize_document_presence(condition, condition_field)
            elif kind == "timeliness":
                normalized = _normalize_timeliness(condition, condition_field)
            else:
                raise VisualConditionInvalid(f"{condition_field}.kind 不支持")
            if normalized["id"] in seen_ids:
                raise VisualConditionInvalid("组和条件 id 必须唯一")
            seen_ids.add(normalized["id"])
            normalized_conditions.append(normalized)
        groups.append({"id": group_id, "operator": operator, "conditions": normalized_conditions})
    return {
        "schema_version": SCHEMA_VERSION,
        "root_operator": root_operator,
        "groups": groups,
    }


def visual_condition_from_check_logic(check_logic: Any) -> dict[str, Any] | None:
    if not isinstance(check_logic, Mapping):
        return None
    value = check_logic.get("visual_condition")
    if value is None:
        return None
    return normalize_visual_condition(value)
