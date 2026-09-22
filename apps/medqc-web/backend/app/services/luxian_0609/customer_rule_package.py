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
        "rule_ids": ("LX0609-01-01-01", "LX0609-01-02-01", "LX0609-09-01-01", "LX0609-02-01-01", "LX0609-02-01-02", "LX0609-09-01-02"),
    },
    {
        "key": "course_quality",
        "name": "查房病程",
        "rule_ids": (
            "LX0609-02-01-03",
            "LX0609-02-01-04",
            "LX0609-02-01-05",
            "LX0609-12-01-01",
            "LX0609-12-01-02",
            "LX0609-01-01-02",
            "LX0609-01-02-02",
        ),
    },
    {
        "key": "exam_lab",
        "name": "检查检验",
        "rule_ids": (
            "LX0609-06-01-02", "LX0609-06-01-04", "LX0609-06-01-05",
            "LX0609-06-03-03", "LX0609-06-03-04",
            "LX0609-06-01-01", "LX0609-06-03-01",
            "LX0609-06-01-03", "LX0609-06-03-02",
        ),
    },
    {
        "key": "consultation_quality",
        "name": "会诊质量",
        "rule_ids": ("LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03", "LX0609-03-01-04"),
    },
    {
        "key": "surgery_anesthesia",
        "name": "手术麻醉",
        "rule_ids": (
            "LX0609-04-02-01",
            "LX0609-04-02-03",
            "LX0609-04-02-04",
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
            "LX0609-04-01-04",
            "LX0609-04-01-05",
        ),
    },
    {
        "key": "transfusion",
        "name": "输血",
        "rule_ids": (
            "LX0609-11-03-01",
            "LX0609-11-03-02",
            "LX0609-07-01-01",
            "LX0609-07-01-02",
            "LX0609-07-02-01",
            "LX0609-07-02-02",
            "LX0609-07-03-01",
            "LX0609-07-04-01",
            "LX0609-07-04-02",
        ),
    },
    {
        "key": "tumor_pathology",
        "name": "肿瘤病理",
        "rule_ids": ("LX0609-06-02-03", "LX0609-06-02-02", "LX0609-05-02-01", "LX0609-08-01-04", "LX0609-06-02-01"),
    },
    {
        "key": "extended_document",
        "name": "死亡出院与连续医疗记录",
        "rule_ids": (
            "LX0609-03-02-01",
            "LX0609-09-02-01",
            "LX0609-06-04-01",
            "LX0609-06-04-02",
            "LX0609-05-01-02",
            "LX0609-05-01-03",
            "LX0609-05-01-04",
            "LX0609-05-01-05",
            "LX0609-05-01-06",
            "LX0609-05-03-01",
            "LX0609-04-02-06",
            "LX0609-08-01-01",
            "LX0609-08-01-02",
            "LX0609-08-01-03",
            "LX0609-04-05-01",
            "LX0609-04-05-02",
            "LX0609-04-05-03",
            "LX0609-08-02-01",
            "LX0609-08-02-02",
            "LX0609-04-02-07",
            "LX0609-07-01-03",
            "LX0609-10-01-01",
            "LX0609-10-02-01",
            "LX0609-10-02-02",
            "LX0609-12-02-01",
            "LX0609-10-03-01",
            "LX0609-04-02-08",
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
