from __future__ import annotations

from typing import Any, Iterable

from ..luxian_0609_evidence_formatter import format_luxian_0609_evidence
from ..luxian_0609_llm_gate import evaluate_luxian_0609_trigger_gates_with_llm
from ..luxian_0609_programmatic_rules import evaluate_luxian_0609_programmatic_rules
from ..luxian_0609_result_aggregator import aggregate_luxian_0609_results, summarize_luxian_0609_results
from ..luxian_0609_result_review_service import review_luxian_0609_batch_job
from ..luxian_0609_result_schema import apply_luxian_0609_result_schema
from ..luxian_0609_rule_catalog import (
    LUXIAN_0609_RULE_SET_KEY,
    LUXIAN_0609_RULE_SET_NAME,
    filter_luxian_0609_rules_by_documents,
    get_luxian_0609_rule,
    load_luxian_0609_rules,
)
from ..luxian_0609_trigger_gate import (
    Luxian0609GateDecision,
    evaluate_luxian_0609_trigger_gates,
    filter_executable_rules_by_gate,
)


RULE_FAMILY_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "basic_timeliness",
        "name": "基础时限",
        "rule_ids": ("LX0609-001", "LX0609-002", "LX0609-004", "LX0609-005", "LX0609-006"),
    },
    {
        "key": "course_quality",
        "name": "查房病程",
        "rule_ids": (
            "LX0609-007",
            "LX0609-008",
            "LX0609-009",
            "LX0609-016",
            "LX0609-017",
            "LX0609-018",
            "LX0609-077",
        ),
    },
    {
        "key": "exam_lab",
        "name": "检查检验",
        "rule_ids": ("LX0609-010", "LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"),
    },
    {
        "key": "consultation_quality",
        "name": "会诊质量",
        "rule_ids": ("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"),
    },
    {
        "key": "surgery_anesthesia",
        "name": "手术麻醉",
        "rule_ids": (
            "LX0609-003",
            "LX0609-024",
            "LX0609-025",
            "LX0609-028",
            "LX0609-029",
            "LX0609-030",
            "LX0609-031",
            "LX0609-032",
            "LX0609-033",
            "LX0609-034",
            "LX0609-035",
            "LX0609-036",
            "LX0609-037",
            "LX0609-038",
            "LX0609-039",
            "LX0609-040",
        ),
    },
    {
        "key": "transfusion",
        "name": "输血",
        "rule_ids": (
            "LX0609-041",
            "LX0609-042",
            "LX0609-043",
            "LX0609-044",
            "LX0609-045",
            "LX0609-046",
            "LX0609-047",
            "LX0609-048",
            "LX0609-049",
        ),
    },
    {
        "key": "tumor_pathology",
        "name": "肿瘤病理",
        "rule_ids": ("LX0609-013", "LX0609-019", "LX0609-026", "LX0609-027"),
    },
    {
        "key": "extended_document",
        "name": "死亡出院与连续医疗记录",
        "rule_ids": (
            "LX0609-050",
            "LX0609-051",
            "LX0609-052",
            "LX0609-053",
            "LX0609-054",
            "LX0609-055",
            "LX0609-056",
            "LX0609-057",
            "LX0609-058",
            "LX0609-059",
            "LX0609-060",
            "LX0609-061",
            "LX0609-062",
            "LX0609-063",
            "LX0609-064",
            "LX0609-065",
            "LX0609-066",
            "LX0609-067",
            "LX0609-068",
            "LX0609-069",
            "LX0609-070",
            "LX0609-071",
            "LX0609-072",
            "LX0609-073",
            "LX0609-074",
            "LX0609-075",
            "LX0609-076",
        ),
    },
)


def is_luxian_0609_rule_set(rule_set_key: str | None) -> bool:
    return str(rule_set_key or "").strip() == LUXIAN_0609_RULE_SET_KEY


def normalize_customer_rule_ids(rule_ids: Iterable[str] | None) -> list[str]:
    return sorted(
        {
            str(rule_id or "").strip().upper()
            for rule_id in list(rule_ids or [])
            if str(rule_id or "").strip()
        }
    )


def customer_rule_count() -> int:
    return len(load_luxian_0609_rules())


def _wrappers_by_id() -> dict[str, dict[str, Any]]:
    return {
        str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper(): wrapper
        for wrapper in load_luxian_0609_rules()
    }


def resolve_execution_rule_ids(customer_rule_ids: Iterable[str] | None) -> tuple[list[str], list[str]]:
    """Map customer-facing LX0609 ids to executable SC/LX/CL rule ids."""

    normalized_customer_ids = normalize_customer_rule_ids(customer_rule_ids)
    if not normalized_customer_ids:
        return [], []
    wrappers_by_id = _wrappers_by_id()
    invalid_rule_ids = [rule_id for rule_id in normalized_customer_ids if rule_id not in wrappers_by_id]
    execution_rule_ids: list[str] = []
    for customer_rule_id in normalized_customer_ids:
        wrapper = wrappers_by_id.get(customer_rule_id) or {}
        mapped_rule_ids = [
            rule_id
            for rule_id in (
                str(item or "").strip().upper()
                for item in list(wrapper.get("mapped_rule_ids") or [])
            )
            if rule_id
        ]
        if not mapped_rule_ids:
            primary_rule_id = str(wrapper.get("primary_execution_rule_id") or "").strip()
            mapped_rule_ids = normalize_customer_rule_ids([primary_rule_id])
        for mapped_rule_id in mapped_rule_ids:
            if mapped_rule_id and mapped_rule_id not in execution_rule_ids:
                execution_rule_ids.append(mapped_rule_id)
    return execution_rule_ids, invalid_rule_ids


def resolve_execution_scope(
    customer_rule_ids: Iterable[str] | None,
    *,
    allowed_rule_ids: set[str],
) -> tuple[list[str], list[str], list[str]]:
    """校验并保留客户规则 ID，执行层再统一完成 Native/兼容分区。

    ``allowed_rule_ids`` 与入参均是客户侧 LX0609 ID。这里若提前展开为旧
    SC/LX 执行 ID，再用客户 ID 白名单过滤，会把显式勾选的规则全部误判为
    gate-only，绕过 Native 主链。
    """

    normalized_customer_ids = normalize_customer_rule_ids(customer_rule_ids)
    wrappers_by_id = _wrappers_by_id()
    execution_rule_ids: list[str] = []
    invalid_rule_ids: list[str] = []
    for customer_rule_id in normalized_customer_ids:
        if customer_rule_id not in wrappers_by_id or (
            allowed_rule_ids and customer_rule_id not in allowed_rule_ids
        ):
            invalid_rule_ids.append(customer_rule_id)
            continue
        execution_rule_ids.append(customer_rule_id)
    return execution_rule_ids, normalize_customer_rule_ids(invalid_rule_ids), []


def build_family_scopes(customer_rule_ids: Iterable[str] | None) -> list[dict[str, Any]]:
    selected_rule_ids = normalize_customer_rule_ids(customer_rule_ids)
    if not selected_rule_ids:
        return []
    selected = set(selected_rule_ids)
    covered: set[str] = set()
    scopes: list[dict[str, Any]] = []
    for family in RULE_FAMILY_DEFINITIONS:
        family_rule_ids = [
            rule_id
            for rule_id in normalize_customer_rule_ids(list(family.get("rule_ids") or []))
            if rule_id in selected
        ]
        if not family_rule_ids:
            continue
        covered.update(family_rule_ids)
        scopes.append(
            {
                "key": str(family["key"]),
                "name": str(family["name"]),
                "rule_ids": family_rule_ids,
            }
        )
    orphan_rule_ids = [rule_id for rule_id in selected_rule_ids if rule_id not in covered]
    if orphan_rule_ids:
        scopes.append({"key": "other", "name": "其他质控点", "rule_ids": orphan_rule_ids})
    return scopes
