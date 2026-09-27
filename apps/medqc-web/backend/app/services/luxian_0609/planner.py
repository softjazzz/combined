"""LX0609-04-01-01、LX0609-04-02-02、LX0609-04-03-01 的纯前置 shadow scope/source planner。

本模块只声明后续程序化切片所需的规则、事实与来源，不读取 Manifest/Fact bundle，
不判断来源状态、适用性或质控结果，也不连接现有执行链。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from itertools import islice
import json
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping


SUPPORTED_RULE_IDS = ("LX0609-04-01-01", "LX0609-04-02-02", "LX0609-04-03-01")
_NORMALIZABLE_RULE_ID_ORDER = (
    "LX0609-01-01-01",
    "LX0609-01-02-01",
    "LX0609-04-02-01",
    "LX0609-09-01-01",
    "LX0609-02-01-01",
    "LX0609-02-01-02",
    "LX0609-02-01-03",
    "LX0609-02-01-04",
    "LX0609-02-01-05",
    "LX0609-06-01-02",
    "LX0609-06-01-04",
    "LX0609-06-01-05",
    "LX0609-06-02-03",
    "LX0609-06-03-03",
    "LX0609-06-03-04",
    "LX0609-12-01-01",
    "LX0609-12-01-02",
    "LX0609-01-01-02",
    "LX0609-06-02-02",
    "LX0609-03-01-01",
    "LX0609-03-01-02",
    "LX0609-03-01-03",
    "LX0609-03-01-04",
    "LX0609-04-02-03",
    "LX0609-04-02-04",
    "LX0609-05-02-01",
    "LX0609-08-01-04",
    "LX0609-05-01-01",
    "LX0609-04-01-01",
    "LX0609-04-02-02",
    "LX0609-04-02-05",
    "LX0609-04-03-01",
    "LX0609-11-01-01",
    "LX0609-11-02-01",
    "LX0609-11-02-02",
    "LX0609-04-04-01",
    "LX0609-04-04-02",
    "LX0609-04-04-03",
    "LX0609-04-01-02",
    "LX0609-04-01-03",
    "LX0609-11-03-01",
    "LX0609-11-03-02",
    "LX0609-07-01-01",
    "LX0609-07-01-02",
    "LX0609-07-02-01",
    "LX0609-07-02-02",
    "LX0609-07-03-01",
    "LX0609-07-04-01",
    "LX0609-07-04-02",
)
_NORMALIZABLE_RULE_IDS = frozenset(_NORMALIZABLE_RULE_ID_ORDER)
MAX_SCOPE_RULE_IDS = 256
MAX_RECORD_VISITS = 512
MAX_RULES_PER_VISIT = 256
MAX_TOTAL_RECORD_RULES = 8_192
MAX_PLAN_EXCLUSIONS = 1_024

_RULE_ID_PATTERN = re.compile(r"^LX0609-[0-9]{2}-[0-9]{2}-[0-9]{2}$")
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_CREDENTIAL_PATTERN = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|api[_ -]?key\s*[:=]|password\s*[:=])"
)
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(?:patient[_ -]?name|id[_ -]?card|phone|mobile|address|full[_ -]?text|"
    r"prompt|response|trace|quote|error[_ -]?stack|sql)"
)
_FORBIDDEN_STATUS_PATTERN = re.compile(
    r"(?i)(?:not[_ -]?applicable|data[_ -]?gap|non[_ -]?compliant|"
    r"ai[_ -]?suggested(?:[_ -]?(?:compliant|non[_ -]?compliant))?|"
    r"technical[_ -]?error|evaluation[_ -]?unknown|suppressed|(?<!non[_ -])compliant)"
)

_ALLOWED_EXCLUSION_REASONS = frozenset(
    {
        "record_excluded",
        "scoped_not_selected",
        "selected_not_scoped",
        "unsupported_slice_rule",
    }
)
_ALLOWED_RECORD_SCOPE_STATES = frozenset(
    {"empty_record_map", "current_visit_present", "current_visit_absent"}
)


_TRIGGER_REQUIREMENT_SPECS = MappingProxyType(
    {
        "current_visit_surgery_order_confirmed": MappingProxyType(
            {
                "allowed_source_keys": ("inpat_nondrug_order",),
                "trigger_scope": "current_visit",
                "current_visit_relevance": "relevant",
                "assertion": "affirmed",
                "allowed_event_statuses": ("ordered", "performed"),
            }
        ),
        "current_visit_surgery_confirmed": MappingProxyType(
            {
                "allowed_source_keys": ("surgery_application", "surgery_record", "mr_surgery"),
                "trigger_scope": "current_visit",
                "current_visit_relevance": "relevant",
                "assertion": "affirmed",
                "allowed_event_statuses": ("performed",),
            }
        ),
    }
)


@dataclass(frozen=True)
class TriggerRequirement:
    fact_type: str
    allowed_source_keys: tuple[str, ...]
    trigger_scope: str
    current_visit_relevance: str
    assertion: str
    allowed_event_statuses: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.fact_type, str):
            raise TypeError("trigger requirement fact_type must be str")
        if type(self.allowed_source_keys) is not tuple or type(
            self.allowed_event_statuses
        ) is not tuple:
            raise TypeError("trigger requirement collections must be tuple")
        expected = _TRIGGER_REQUIREMENT_SPECS.get(self.fact_type)
        actual = {
            "allowed_source_keys": self.allowed_source_keys,
            "trigger_scope": self.trigger_scope,
            "current_visit_relevance": self.current_visit_relevance,
            "assertion": self.assertion,
            "allowed_event_statuses": self.allowed_event_statuses,
        }
        if expected is None or actual != expected:
            raise ValueError("trigger requirement mismatch")

    @classmethod
    def for_fact_type(cls, fact_type: str) -> "TriggerRequirement":
        if not isinstance(fact_type, str):
            raise TypeError("trigger requirement fact_type must be str")
        expected = _TRIGGER_REQUIREMENT_SPECS.get(fact_type)
        if expected is None:
            raise ValueError("trigger requirement mismatch")
        return cls(fact_type=fact_type, **expected)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_event_statuses": list(self.allowed_event_statuses),
            "allowed_source_keys": list(self.allowed_source_keys),
            "assertion": self.assertion,
            "current_visit_relevance": self.current_visit_relevance,
            "fact_type": self.fact_type,
            "trigger_scope": self.trigger_scope,
        }


_ORDER_TRIGGER_REQUIREMENT = TriggerRequirement.for_fact_type(
    "current_visit_surgery_order_confirmed"
)
_PERFORMED_TRIGGER_REQUIREMENT = TriggerRequirement.for_fact_type(
    "current_visit_surgery_confirmed"
)


_RULE_METADATA = MappingProxyType({
    "LX0609-04-01-01": MappingProxyType({
        "family": "surgery_anesthesia",
        "execution_kind": "programmatic_zero_llm",
        "trigger_requirements": (
            _ORDER_TRIGGER_REQUIREMENT,
            _PERFORMED_TRIGGER_REQUIREMENT,
        ),
        "trigger_alternative_policy": "any",
        "target_source_key": "presurg_summary",
        "source_requirement_version": "lx0609-surgery-source-v3",
        "parent_rule_ids": (),
        "dependency_reason_codes": (),
        "independent_target_source": True,
    }),
    "LX0609-04-02-02": MappingProxyType({
        "family": "surgery_anesthesia",
        "execution_kind": "programmatic_zero_llm",
        "trigger_requirements": (
            _ORDER_TRIGGER_REQUIREMENT,
            _PERFORMED_TRIGGER_REQUIREMENT,
        ),
        "trigger_alternative_policy": "any",
        "target_source_key": "surgery_record",
        "source_requirement_version": "lx0609-surgery-source-v3",
        "parent_rule_ids": (),
        "dependency_reason_codes": (),
        "independent_target_source": True,
    }),
    "LX0609-04-03-01": MappingProxyType({
        "family": "surgery_anesthesia",
        "execution_kind": "programmatic_zero_llm",
        "trigger_requirements": (_PERFORMED_TRIGGER_REQUIREMENT,),
        "trigger_alternative_policy": "any",
        "target_source_key": "surgery_safecheck_record",
        "source_requirement_version": "lx0609-surgery-source-v3",
        "parent_rule_ids": ("LX0609-04-02-02",),
        "dependency_reason_codes": ("informational_parent_only",),
        "independent_target_source": True,
    }),
})


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _validate_code(field_name: str, value: Any, *, max_length: int = 128) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    if (
        not value
        or value != value.strip()
        or len(value) > max_length
        or not _CODE_PATTERN.fullmatch(value)
        or _ID_CARD_PATTERN.search(value)
        or _PHONE_PATTERN.search(value)
        or _CREDENTIAL_PATTERN.search(value)
        or _SENSITIVE_KEY_PATTERN.search(value)
    ):
        raise ValueError(f"invalid {field_name}")
    return value


def _validate_created_at(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("created_at must be explicit ISO-8601 text")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("created_at must be valid ISO-8601 text") from None
    return value


def _normalize_rule_id(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("rule_id must be str")
    normalized = value.strip().upper()
    if (
        not _RULE_ID_PATTERN.fullmatch(normalized)
        or normalized not in _NORMALIZABLE_RULE_IDS
    ):
        raise ValueError("invalid rule_id")
    return normalized


def _materialize_rule_ids(
    values: Iterable[str],
    *,
    field_name: str,
    limit: int = MAX_SCOPE_RULE_IDS,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be an iterable of rule ids")
    try:
        iterator = iter(values)
    except TypeError:
        raise TypeError(f"{field_name} must be an iterable of rule ids") from None
    raw_values = tuple(islice(iterator, limit + 1))
    if len(raw_values) > limit:
        raise ValueError(f"too many {field_name}")
    normalized = {_normalize_rule_id(value) for value in raw_values}
    return tuple(
        rule_id for rule_id in _NORMALIZABLE_RULE_ID_ORDER if rule_id in normalized
    )


def _materialize_record_rule_map(
    value: Mapping[str, list[str] | tuple[str, ...]],
) -> tuple[dict[str, tuple[str, ...]], int]:
    if type(value) is not dict:
        raise TypeError("record_rule_map must be a concrete dict")
    if len(value) > MAX_RECORD_VISITS:
        raise ValueError("too many record_rule_map visits")
    normalized: dict[str, tuple[str, ...]] = {}
    total = 0
    for raw_visit_ref, raw_rule_ids in value.items():
        visit_ref = _validate_code("record_rule_map visit_ref", raw_visit_ref)
        if type(raw_rule_ids) not in (list, tuple):
            raise TypeError("record_rule_map values must be concrete list or tuple")
        if len(raw_rule_ids) > MAX_RULES_PER_VISIT:
            raise ValueError("too many record_rule_map rules for visit")
        total += len(raw_rule_ids)
        if total > MAX_TOTAL_RECORD_RULES:
            raise ValueError("too many total record_rule_map rules")
        normalized[visit_ref] = _materialize_rule_ids(
            raw_rule_ids,
            field_name="record_rule_map rules",
            limit=MAX_RULES_PER_VISIT,
        )
    return normalized, total


def _assert_no_forbidden_status_tokens(value: Any) -> None:
    if isinstance(value, str):
        if _FORBIDDEN_STATUS_PATTERN.search(value):
            raise ValueError("planner metadata contains forbidden status token")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_forbidden_status_tokens(key)
            _assert_no_forbidden_status_tokens(item)
        return
    if isinstance(value, (tuple, list)):
        for item in value:
            _assert_no_forbidden_status_tokens(item)


@dataclass(frozen=True)
class PlannedRule:
    rule_id: str
    family: str
    execution_kind: str
    trigger_requirements: tuple[TriggerRequirement, ...]
    trigger_alternative_policy: str
    target_source_key: str
    source_requirement_version: str
    parent_rule_ids: tuple[str, ...]
    dependency_reason_codes: tuple[str, ...]
    independent_target_source: bool

    def __post_init__(self) -> None:
        rule_id = _normalize_rule_id(self.rule_id)
        expected = _RULE_METADATA.get(rule_id)
        if expected is None:
            raise ValueError("unsupported planned rule")
        collection_fields = (
            "trigger_requirements",
            "parent_rule_ids",
            "dependency_reason_codes",
        )
        if any(type(getattr(self, name)) is not tuple for name in collection_fields):
            raise TypeError("planned rule collections must be tuple")
        actual = {
            "family": self.family,
            "execution_kind": self.execution_kind,
            "trigger_requirements": tuple(self.trigger_requirements),
            "trigger_alternative_policy": self.trigger_alternative_policy,
            "target_source_key": self.target_source_key,
            "source_requirement_version": self.source_requirement_version,
            "parent_rule_ids": tuple(self.parent_rule_ids),
            "dependency_reason_codes": tuple(self.dependency_reason_codes),
            "independent_target_source": self.independent_target_source,
        }
        if actual != expected:
            raise ValueError("planned rule metadata mismatch")
        if not self.trigger_requirements or not all(
            isinstance(item, TriggerRequirement) for item in self.trigger_requirements
        ):
            raise TypeError("trigger_requirements must contain TriggerRequirement values")
        _assert_no_forbidden_status_tokens(actual)
        object.__setattr__(self, "rule_id", rule_id)
        for field_name in collection_fields:
            object.__setattr__(self, field_name, tuple(actual[field_name]))

    @classmethod
    def for_rule_id(cls, rule_id: str) -> "PlannedRule":
        normalized = _normalize_rule_id(rule_id)
        metadata = _RULE_METADATA.get(normalized)
        if metadata is None:
            raise ValueError("unsupported planned rule")
        return cls(rule_id=normalized, **metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dependency_reason_codes": list(self.dependency_reason_codes),
            "execution_kind": self.execution_kind,
            "family": self.family,
            "independent_target_source": self.independent_target_source,
            "parent_rule_ids": list(self.parent_rule_ids),
            "required_source_keys": list(self.required_source_keys),
            "required_trigger_fact_types": list(self.required_trigger_fact_types),
            "rule_id": self.rule_id,
            "source_requirement_version": self.source_requirement_version,
            "target_source_key": self.target_source_key,
            "trigger_alternative_policy": self.trigger_alternative_policy,
            "trigger_requirements": [
                requirement.to_dict() for requirement in self.trigger_requirements
            ],
            "trigger_source_keys": list(self.trigger_source_keys),
        }

    @property
    def required_trigger_fact_types(self) -> tuple[str, ...]:
        return tuple(requirement.fact_type for requirement in self.trigger_requirements)

    @property
    def trigger_source_keys(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    source_key
                    for requirement in self.trigger_requirements
                    for source_key in requirement.allowed_source_keys
                }
            )
        )

    @property
    def required_source_keys(self) -> tuple[str, ...]:
        return tuple(sorted({*self.trigger_source_keys, self.target_source_key}))


@dataclass(frozen=True)
class PlanningExclusion:
    rule_id: str
    reason_code: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", _normalize_rule_id(self.rule_id))
        if self.reason_code not in _ALLOWED_EXCLUSION_REASONS:
            raise ValueError("invalid planning exclusion reason")
        _assert_no_forbidden_status_tokens(self.reason_code)

    def to_dict(self) -> dict[str, str]:
        return {"reason_code": self.reason_code, "rule_id": self.rule_id}


def _expected_exclusions(
    *,
    selected: tuple[str, ...],
    scoped: tuple[str, ...],
    record_rule_ids: tuple[str, ...],
) -> tuple[PlanningExclusion, ...]:
    selected_set = set(selected)
    scoped_set = set(scoped)
    record_set = set(record_rule_ids)
    supported = set(SUPPORTED_RULE_IDS)
    exclusions: set[tuple[str, str]] = set()
    for rule_id in selected_set - scoped_set:
        exclusions.add((rule_id, "selected_not_scoped"))
    for rule_id in scoped_set - selected_set:
        exclusions.add((rule_id, "scoped_not_selected"))
    for rule_id in (selected_set & scoped_set & supported) - record_set:
        exclusions.add((rule_id, "record_excluded"))
    for rule_id in (selected_set | scoped_set | record_set) - supported:
        exclusions.add((rule_id, "unsupported_slice_rule"))
    if len(exclusions) > MAX_PLAN_EXCLUSIONS:
        raise ValueError("too many planning exclusions")
    return tuple(
        PlanningExclusion(rule_id=rule_id, reason_code=reason)
        for rule_id, reason in sorted(
            exclusions,
            key=lambda item: (
                _NORMALIZABLE_RULE_ID_ORDER.index(item[0]),
                item[1],
            ),
        )
    )


@dataclass(frozen=True)
class ShadowRulePlan:
    planner_schema_version: str
    rule_plan_version: str
    visit_ref: str
    selected_rule_ids: tuple[str, ...]
    scoped_customer_rule_ids: tuple[str, ...]
    record_scope_state: str
    record_rule_ids: tuple[str, ...]
    planned_rules: tuple[PlannedRule, ...]
    exclusions: tuple[PlanningExclusion, ...]
    created_at: str

    def __post_init__(self) -> None:
        planner_schema_version = _validate_code(
            "planner_schema_version", self.planner_schema_version, max_length=64
        )
        rule_plan_version = _validate_code(
            "rule_plan_version", self.rule_plan_version, max_length=64
        )
        visit_ref = _validate_code("visit_ref", self.visit_ref)
        selected = _materialize_rule_ids(
            self.selected_rule_ids, field_name="selected_rule_ids"
        )
        scoped = _materialize_rule_ids(
            self.scoped_customer_rule_ids,
            field_name="scoped_customer_rule_ids",
        )
        record_rules = _materialize_rule_ids(
            self.record_rule_ids, field_name="record_rule_ids"
        )
        if self.record_scope_state not in _ALLOWED_RECORD_SCOPE_STATES:
            raise ValueError("invalid record_scope_state")
        if type(self.planned_rules) not in (tuple, list):
            raise TypeError("planned_rules must be a concrete tuple or list")
        if len(self.planned_rules) > len(SUPPORTED_RULE_IDS):
            raise ValueError("too many planned rules")
        planned = tuple(self.planned_rules)
        if len(planned) > len(SUPPORTED_RULE_IDS) or not all(
            isinstance(item, PlannedRule) for item in planned
        ):
            raise TypeError("planned_rules must contain bounded PlannedRule values")
        expected_rule_ids = tuple(
            rule_id
            for rule_id in SUPPORTED_RULE_IDS
            if rule_id in set(selected) & set(scoped) & set(record_rules)
        )
        if tuple(item.rule_id for item in planned) != expected_rule_ids:
            raise ValueError("planned_rules do not match effective scope")
        if type(self.exclusions) not in (tuple, list):
            raise TypeError("exclusions must be a concrete tuple or list")
        if len(self.exclusions) > MAX_PLAN_EXCLUSIONS:
            raise ValueError("too many planning exclusions")
        exclusions = tuple(self.exclusions)
        if len(exclusions) > MAX_PLAN_EXCLUSIONS or not all(
            isinstance(item, PlanningExclusion) for item in exclusions
        ):
            raise TypeError("exclusions must contain bounded PlanningExclusion values")
        expected_exclusions = _expected_exclusions(
            selected=selected,
            scoped=scoped,
            record_rule_ids=record_rules,
        )
        if exclusions != expected_exclusions:
            raise ValueError("planning exclusions do not match scope")
        if (
            self.record_scope_state in {"empty_record_map", "current_visit_absent"}
            and record_rules
        ):
            raise ValueError("record_scope_state cannot carry record rules")
        object.__setattr__(self, "planner_schema_version", planner_schema_version)
        object.__setattr__(self, "rule_plan_version", rule_plan_version)
        object.__setattr__(self, "visit_ref", visit_ref)
        object.__setattr__(self, "selected_rule_ids", selected)
        object.__setattr__(self, "scoped_customer_rule_ids", scoped)
        object.__setattr__(self, "record_rule_ids", record_rules)
        object.__setattr__(self, "planned_rules", planned)
        object.__setattr__(self, "exclusions", exclusions)
        object.__setattr__(self, "created_at", _validate_created_at(self.created_at))
        _assert_no_forbidden_status_tokens(self.to_dict())

    @property
    def planned_rule_count(self) -> int:
        return len(self.planned_rules)

    def summary_dict(self) -> dict[str, Any]:
        return {
            "expected_llm_call_count": 0,
            "planned_rule_count": self.planned_rule_count,
            "zero_llm_expected": True,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "exclusions": [item.to_dict() for item in self.exclusions],
            "planned_rules": [item.to_dict() for item in self.planned_rules],
            "planner_schema_version": self.planner_schema_version,
            "record_rule_ids": list(self.record_rule_ids),
            "record_scope_state": self.record_scope_state,
            "rule_plan_version": self.rule_plan_version,
            "scoped_customer_rule_ids": list(self.scoped_customer_rule_ids),
            "selected_rule_ids": list(self.selected_rule_ids),
            "summary": self.summary_dict(),
            "visit_ref": self.visit_ref,
        }

    def identity_dict(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("created_at")
        return value

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    def fingerprint(self) -> str:
        return hashlib.sha256(
            _canonical_json(self.identity_dict()).encode("utf-8")
        ).hexdigest()


def build_luxian_0609_shadow_plan(
    *,
    visit_ref: str,
    selected_rule_ids: Iterable[str],
    scoped_customer_rule_ids: Iterable[str],
    record_rule_map: Mapping[str, list[str] | tuple[str, ...]],
    planner_schema_version: str,
    rule_plan_version: str,
    created_at: str,
) -> ShadowRulePlan:
    """按显式 selected/scoped/current-visit record scope 构造稳定 shadow plan。"""

    normalized_visit_ref = _validate_code("visit_ref", visit_ref)
    selected = _materialize_rule_ids(
        selected_rule_ids, field_name="selected_rule_ids"
    )
    scoped = _materialize_rule_ids(
        scoped_customer_rule_ids,
        field_name="scoped_customer_rule_ids",
    )
    normalized_map, _ = _materialize_record_rule_map(record_rule_map)
    if not normalized_map:
        record_scope_state = "empty_record_map"
        record_rules: tuple[str, ...] = ()
    elif normalized_visit_ref not in normalized_map:
        record_scope_state = "current_visit_absent"
        record_rules = ()
    else:
        record_scope_state = "current_visit_present"
        record_rules = normalized_map[normalized_visit_ref]
    effective = set(selected) & set(scoped) & set(record_rules)
    planned = tuple(
        PlannedRule.for_rule_id(rule_id)
        for rule_id in SUPPORTED_RULE_IDS
        if rule_id in effective
    )
    exclusions = _expected_exclusions(
        selected=selected,
        scoped=scoped,
        record_rule_ids=record_rules,
    )
    return ShadowRulePlan(
        planner_schema_version=planner_schema_version,
        rule_plan_version=rule_plan_version,
        visit_ref=normalized_visit_ref,
        selected_rule_ids=selected,
        scoped_customer_rule_ids=scoped,
        record_scope_state=record_scope_state,
        record_rule_ids=record_rules,
        planned_rules=planned,
        exclusions=exclusions,
        created_at=created_at,
    )
