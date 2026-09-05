"""020–023 会诊执行器客户事实的安全投影合同。

本模块只把执行器已经判定的会诊 facts 校验并投影为客户可见字段；它不解释状态、
不选择业务证据，也不产生 ``customer_evidence``。实际文书定位仍由 RuleDecision
的 ``fact_refs`` 经公共证据投影完成。逐建议的既有安全引用形状由公共引用投影
组件生成，避免会诊族自行处理业务文书 ID。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from .customer_evidence_enrichment import project_selected_grouped_document_refs


_CONSULTATION_RULE_IDS = frozenset(
    {"LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"}
)
_RECOMMENDATION_EVIDENCE_SOURCE_TYPES = frozenset(
    {
        "consultation_record",
        "daily_course_record",
        "senior_course_record",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "exam_master",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "surgery_record",
    }
)


def is_consultation_customer_rule(rule_id: str) -> bool:
    """返回本投影合同唯一负责的正式会诊质量规则。"""

    return str(rule_id or "").strip().upper() in _CONSULTATION_RULE_IDS


def _valid_record_time(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    time_format = (
        "%Y-%m-%d %H:%M:%S"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value)
        else "%Y-%m-%d"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
        else ""
    )
    if not time_format:
        return False
    try:
        parsed = datetime.strptime(value, time_format)
    except ValueError:
        return False
    return parsed.strftime(time_format) == value


def _safe_semantic_facts(*, rule_id: str, raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if rule_id not in {"LX0609-021", "LX0609-022"}:
        return None
    expected_kind = (
        "consultation_application_quality_check"
        if rule_id == "LX0609-021"
        else "consultation_opinion_quality_check"
    )
    expected_requirement = (
        "说明具体临床问题、会诊理由或明确会诊目的"
        if rule_id == "LX0609-021"
        else "给出针对当前病情的明确诊疗意见"
    )
    expected_keys = {
        "verification_kind",
        "episode_count",
        "document_count",
        "semantic_state",
        "checked_requirement",
        "source_document_ids",
    }
    has_public_shape = "source_document_ids" not in raw
    if has_public_shape:
        expected_keys.remove("source_document_ids")
    has_episode_results = "episode_results" in raw
    if has_episode_results:
        expected_keys.add("episode_results")
    if (
        set(raw) != expected_keys
        or raw.get("verification_kind") != expected_kind
        or raw.get("checked_requirement") != expected_requirement
        or raw.get("semantic_state")
        not in {"clear", "vague", "missing", "absent", "unknown", "mixed"}
        or type(raw.get("episode_count")) is not int
        or not 0 <= raw["episode_count"] <= 100
        or type(raw.get("document_count")) is not int
        or not 0 <= raw["document_count"] <= 100
    ):
        return None
    facts: dict[str, Any] = {
        "verification_kind": expected_kind,
        "episode_count": raw["episode_count"],
        "document_count": raw["document_count"],
        "semantic_state": raw["semantic_state"],
        "checked_requirement": expected_requirement,
    }
    if not has_episode_results:
        return facts
    episode_results = raw.get("episode_results")
    if (
        not isinstance(episode_results, list)
        or len(episode_results) != raw["episode_count"]
        or len(episode_results) > 100
    ):
        return None
    episode_states: list[str] = []
    safe_episode_results: list[dict[str, Any]] = []
    for expected_index, item in enumerate(episode_results, start=1):
        base_keys = {"episode_index", "semantic_state"}
        if not has_public_shape:
            base_keys.add("source_document_id")
        locator_keys = {"record_time", "document_title"}
        if not isinstance(item, Mapping) or set(item) not in {
            frozenset(base_keys),
            frozenset(base_keys | locator_keys),
        }:
            return None
        state = item.get("semantic_state")
        if (
            item.get("episode_index") != expected_index
            or state not in {"clear", "vague", "missing", "unknown"}
        ):
            return None
        if locator_keys.issubset(item):
            expected_title = "会诊申请单" if rule_id == "LX0609-021" else "会诊记录单"
            if item.get("document_title") != expected_title or not _valid_record_time(
                item.get("record_time")
            ):
                return None
        episode_states.append(state)
        safe_episode_results.append(
            {
                "episode_index": expected_index,
                "semantic_state": state,
                **(
                    {
                        "record_time": item["record_time"],
                        "document_title": item["document_title"],
                    }
                    if locator_keys.issubset(item)
                    else {}
                ),
            }
        )
    state_set = set(episode_states)
    derived_state = "absent" if not state_set else next(iter(state_set)) if len(state_set) == 1 else "mixed"
    if derived_state != raw["semantic_state"]:
        return None
    facts["episode_results"] = safe_episode_results
    return facts


def _safe_execution_facts(*, rule_id: str, raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if rule_id not in {"LX0609-020", "LX0609-023"}:
        return None
    expected_kind = (
        "consultation_execution_quality_check"
        if rule_id == "LX0609-023"
        else "consultation_execution_relation_check"
    )
    allowed_relation_states = (
        {
            "specific_execution",
            "generic_or_copied_execution",
            "execution_record_absent",
            "source_incomplete",
            "association_unresolved",
            "source_error",
        }
        if rule_id == "LX0609-023"
        else {
            "all_linked",
            "execution_missing",
            "not_triggered",
            "source_incomplete",
            "association_unresolved",
            "source_error",
        }
    )
    expected_keys = {
        "verification_kind",
        "completed_opinion_episode_count",
        "recommendation_count",
        "specific_execution_count",
        "generic_execution_count",
        "missing_execution_count",
        "relation_state",
        "source_document_ids",
    }
    has_public_shape = "source_document_ids" not in raw
    if has_public_shape:
        expected_keys.remove("source_document_ids")
    if rule_id == "LX0609-020" and "recommendation_results" in raw:
        expected_keys.add("recommendation_results")
    allowed_internal_keys = {"source_document_refs", "recommendation_evidence"}
    count_keys = (
        "completed_opinion_episode_count",
        "recommendation_count",
        "specific_execution_count",
        "generic_execution_count",
        "missing_execution_count",
    )
    if (
        set(raw) - allowed_internal_keys != expected_keys
        or raw.get("verification_kind") != expected_kind
        or raw.get("relation_state") not in allowed_relation_states
        or any(type(raw.get(key)) is not int or not 0 <= raw[key] <= 100 for key in count_keys)
    ):
        return None
    if not has_public_shape:
        source_document_ids = raw.get("source_document_ids")
        if (
            not isinstance(source_document_ids, list)
            or any(
                not isinstance(value, str)
                or not value.strip()
                for value in source_document_ids
            )
        ):
            return None
    source_document_refs = raw.get("source_document_refs")
    if source_document_refs is not None:
        if not isinstance(source_document_refs, list) or len(source_document_refs) > 8:
            return None
        for reference in source_document_refs:
            if (
                not isinstance(reference, Mapping)
                or set(reference) != {"source_type", "source_document_id"}
                or reference.get("source_type") not in _RECOMMENDATION_EVIDENCE_SOURCE_TYPES
                or not isinstance(reference.get("source_document_id"), str)
                or not reference["source_document_id"].strip()
            ):
                return None
    recommendation_results: list[dict[str, Any]] | None = None
    if rule_id == "LX0609-020" and "recommendation_results" in raw:
        raw_results = raw.get("recommendation_results")
        if (
            not isinstance(raw_results, list)
            or len(raw_results) != raw["recommendation_count"]
            or len(raw_results) > 96
        ):
            return None
        recommendation_results = []
        for index, item in enumerate(raw_results, start=1):
            if (
                not isinstance(item, Mapping)
                or set(item)
                != {"episode_index", "recommendation_index", "action_type", "execution_state"}
                or type(item.get("episode_index")) is not int
                or not 1 <= item["episode_index"] <= raw["completed_opinion_episode_count"]
                or type(item.get("recommendation_index")) is not int
                or item["recommendation_index"] != index
                or item.get("action_type")
                not in {"medication", "test", "procedure", "transfer", "monitoring", "other"}
                or item.get("execution_state") not in {"specific", "generic", "missing", "unknown"}
            ):
                return None
            recommendation_results.append(dict(item))
        count_values = {
            state: sum(item["execution_state"] == state for item in recommendation_results)
            for state in ("specific", "generic", "missing")
        }
        if any(
            raw[f"{state}_execution_count"] != count_values[state]
            for state in ("specific", "generic", "missing")
        ):
            return None
    safe_facts: dict[str, Any] = {
        "verification_kind": expected_kind,
        "completed_opinion_episode_count": raw["completed_opinion_episode_count"],
        "recommendation_count": raw["recommendation_count"],
        "specific_execution_count": raw["specific_execution_count"],
        "generic_execution_count": raw["generic_execution_count"],
        "missing_execution_count": raw["missing_execution_count"],
        "relation_state": raw["relation_state"],
    }
    if recommendation_results is not None:
        safe_facts["recommendation_results"] = recommendation_results
    raw_recommendation_evidence = raw.get("recommendation_evidence")
    if raw_recommendation_evidence is not None:
        if (
            not isinstance(raw_recommendation_evidence, list)
            or len(raw_recommendation_evidence) != raw["recommendation_count"]
            or len(raw_recommendation_evidence) > 96
        ):
            return None
        safe_recommendation_evidence: list[dict[str, Any]] = []
        seen_indexes: set[tuple[int, int]] = set()
        for expected_index, item in enumerate(raw_recommendation_evidence, start=1):
            if not isinstance(item, Mapping):
                return None
            item_is_public = (
                "opinion_evidence" in item or "execution_evidence" in item
            )
            if item_is_public:
                expected_item_keys = {
                    "episode_index",
                    "recommendation_index",
                    "execution_state",
                    "opinion_evidence",
                    "execution_evidence",
                }
                opinion_key, execution_key = "opinion_evidence", "execution_evidence"
            else:
                expected_item_keys = {
                    "episode_index",
                    "recommendation_index",
                    "execution_state",
                    "opinion_refs",
                    "execution_refs",
                }
                opinion_key, execution_key = "opinion_refs", "execution_refs"
            episode_index = item.get("episode_index")
            recommendation_index = item.get("recommendation_index")
            if (
                set(item) != expected_item_keys
                or type(episode_index) is not int
                or not 1 <= episode_index <= raw["completed_opinion_episode_count"]
                or type(recommendation_index) is not int
                or recommendation_index != expected_index
                or item.get("execution_state") not in {"specific", "generic", "missing", "unknown"}
                or (recommendation_results is not None
                    and item["execution_state"]
                    != recommendation_results[expected_index - 1]["execution_state"])
                or (episode_index, recommendation_index) in seen_indexes
            ):
                return None
            opinion_evidence = project_selected_grouped_document_refs(
                raw_refs=item.get(opinion_key),
                public=item_is_public,
                allowed_source_types=_RECOMMENDATION_EVIDENCE_SOURCE_TYPES,
            )
            execution_evidence = project_selected_grouped_document_refs(
                raw_refs=item.get(execution_key),
                public=item_is_public,
                allowed_source_types=_RECOMMENDATION_EVIDENCE_SOURCE_TYPES,
            )
            if opinion_evidence is None or execution_evidence is None:
                return None
            seen_indexes.add((episode_index, recommendation_index))
            safe_recommendation_evidence.append(
                {
                    "episode_index": episode_index,
                    "recommendation_index": recommendation_index,
                    "execution_state": item["execution_state"],
                    "opinion_evidence": opinion_evidence,
                    "execution_evidence": execution_evidence,
                }
            )
        if any(
            raw[f"{state}_execution_count"]
            != sum(
                item["execution_state"] == state
                for item in safe_recommendation_evidence
            )
            for state in ("specific", "generic", "missing")
        ):
            return None
        safe_facts["recommendation_evidence"] = safe_recommendation_evidence
    return safe_facts


def _safe_legacy_023_facts(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if (
        raw.get("failure_kind") != "consultation_execution_too_generic"
        or raw.get("observed_expression") != "仅笼统记录已按会诊意见执行"
        or raw.get("missing_details") != ["具体执行措施", "执行结果或后续安排"]
    ):
        return None
    return {
        "failure_kind": "consultation_execution_too_generic",
        "observed_expression": "仅笼统记录已按会诊意见执行",
        "missing_details": ["具体执行措施", "执行结果或后续安排"],
    }


def _safe_legacy_assessment_facts(
    *, rule_id: str, raw: Mapping[str, Any]
) -> dict[str, Any] | None:
    if (
        rule_id not in {"LX0609-020", "LX0609-021", "LX0609-022"}
        or raw.get("consultation_assessment") not in {"明确", "不符合要求"}
    ):
        return None
    expected_keys = {"source_document_ids", "consultation_assessment"}
    if rule_id == "LX0609-020":
        expected_keys.update({"execution_record_state", "execution_candidate_count"})
    safe_keys = expected_keys - {"source_document_ids"}
    raw_keys = set(raw)
    if raw_keys != expected_keys and raw_keys != safe_keys:
        return None
    facts: dict[str, Any] = {"consultation_assessment": raw["consultation_assessment"]}
    if rule_id == "LX0609-020":
        if (
            raw.get("execution_record_state") not in {"已发现明确执行记录", "未发现执行记录"}
            or type(raw.get("execution_candidate_count")) is not int
            or not 0 <= raw["execution_candidate_count"] <= 100
        ):
            return None
        facts.update(
            {
                "execution_record_state": raw["execution_record_state"],
                "execution_candidate_count": raw["execution_candidate_count"],
            }
        )
    return facts


def safe_consultation_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """验证并剥离 020–023 原生 facts 中的内部文书标识。

    返回 ``None`` 表示执行器输出的 facts 不符合合同；调用方必须在执行器侧把该规则
    收敛为既有 ``technical_error``，而不是由聚合器改写临床结论。
    """

    normalized_rule_id = str(rule_id or "").strip().upper()
    if not is_consultation_customer_rule(normalized_rule_id) or not isinstance(raw, Mapping):
        return None
    return (
        _safe_semantic_facts(rule_id=normalized_rule_id, raw=raw)
        or _safe_execution_facts(rule_id=normalized_rule_id, raw=raw)
        or (
            _safe_legacy_023_facts(raw)
            if normalized_rule_id == "LX0609-023"
            else None
        )
        or _safe_legacy_assessment_facts(rule_id=normalized_rule_id, raw=raw)
    )
