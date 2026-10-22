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
    {"LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03", "LX0609-03-01-04"}
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
        # 023 手术/转科类建议的住院期间执行证据（用户口径 2026-10-22）。
        "transfer_out_record",
        "transfer_in_record",
        "postsurg_firstcourse_record",
    }
)


def is_consultation_customer_rule(rule_id: str) -> bool:
    """返回本投影合同唯一负责的正式会诊质量规则。"""

    return str(rule_id or "").strip().upper() in _CONSULTATION_RULE_IDS


# 023 未纳入医嘱执行核对的原因（2026-10-20 用户口径）。
_023_EXCLUSION_REASONS = frozenset({
    "execution_condition_not_defined",
    "non_order_recommendation",
    "home_medication",
    "condition_not_met",
    "declined_in_record",
})


def _valid_window_start(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None and _valid_record_time(value)


def _valid_missing_measures(value: Any) -> bool:
    return (
        type(value) is list
        and 1 <= len(value) <= 8
        and all(type(item) is str and item.strip() and len(item) <= 40 for item in value)
    )


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
    if rule_id not in {"LX0609-03-01-02", "LX0609-03-01-03"}:
        return None
    expected_kind = (
        "consultation_application_quality_check"
        if rule_id == "LX0609-03-01-02"
        else "consultation_opinion_quality_check"
    )
    expected_requirement = (
        "说明具体临床问题、会诊理由或明确会诊目的"
        if rule_id == "LX0609-03-01-02"
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
            expected_title = "会诊申请单" if rule_id == "LX0609-03-01-02" else "会诊记录单"
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
    if rule_id not in {"LX0609-03-01-01", "LX0609-03-01-04"}:
        return None
    expected_kind = (
        "consultation_execution_quality_check"
        if rule_id == "LX0609-03-01-04"
        else "consultation_execution_relation_check"
    )
    allowed_relation_states = (
        {
            "specific_execution",
            "execution_missing_or_generic",
            "not_triggered",
            # 兼容历史已保存结果；新执行器不再产出以下两个旧状态。
            "generic_or_copied_execution",
            "execution_record_absent",
            "source_incomplete",
            "association_unresolved",
            "source_error",
        }
        if rule_id == "LX0609-03-01-04"
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
    if rule_id == "LX0609-03-01-01" and "recommendation_results" in raw:
        expected_keys.add("recommendation_results")
    allowed_internal_keys = {
        "source_document_refs",
        "recommendation_evidence",
        "excluded_recommendations",
    }
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
    if rule_id == "LX0609-03-01-01" and "recommendation_results" in raw:
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
            recommendation_text = item.get("recommendation_text")
            if recommendation_text is not None:
                expected_item_keys.add("recommendation_text")
            opinion_time = item.get("opinion_time")
            missing_measures = item.get("missing_measures")
            window_start_date = item.get("window_start_date")
            declined_measures = item.get("declined_measures")
            if rule_id == "LX0609-03-01-04":
                if opinion_time is not None:
                    expected_item_keys.add("opinion_time")
                if missing_measures is not None:
                    expected_item_keys.add("missing_measures")
                if window_start_date is not None:
                    expected_item_keys.add("window_start_date")
                if declined_measures is not None:
                    expected_item_keys.add("declined_measures")
            if (
                (opinion_time is not None and not _valid_record_time(opinion_time))
                or (missing_measures is not None and not _valid_missing_measures(missing_measures))
                or (window_start_date is not None and not _valid_window_start(window_start_date))
                or (declined_measures is not None and not _valid_missing_measures(declined_measures))
            ):
                return None
            episode_index = item.get("episode_index")
            recommendation_index = item.get("recommendation_index")
            if (
                set(item) != expected_item_keys
                or type(episode_index) is not int
                or not 1 <= episode_index <= raw["completed_opinion_episode_count"]
                or type(recommendation_index) is not int
                or recommendation_index != expected_index
                or item.get("execution_state") not in {"specific", "generic", "missing", "unknown"}
                or (
                    recommendation_text is not None
                    and (
                        not isinstance(recommendation_text, str)
                        or not recommendation_text.strip()
                        or len(recommendation_text) > 320
                    )
                )
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
            safe_item = {
                "episode_index": episode_index,
                "recommendation_index": recommendation_index,
                "execution_state": item["execution_state"],
                "opinion_evidence": opinion_evidence,
                "execution_evidence": execution_evidence,
            }
            if recommendation_text is not None:
                safe_item["recommendation_text"] = recommendation_text.strip()
            if opinion_time is not None:
                safe_item["opinion_time"] = opinion_time
            if missing_measures is not None:
                safe_item["missing_measures"] = [value.strip() for value in missing_measures]
            if window_start_date is not None:
                safe_item["window_start_date"] = window_start_date
            if declined_measures is not None:
                safe_item["declined_measures"] = [value.strip() for value in declined_measures]
            safe_recommendation_evidence.append(safe_item)
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
    raw_excluded_recommendations = raw.get("excluded_recommendations")
    if raw_excluded_recommendations is not None:
        if (
            rule_id != "LX0609-03-01-04"
            or not isinstance(raw_excluded_recommendations, list)
            or len(raw_excluded_recommendations) > 96
        ):
            return None
        safe_excluded_recommendations: list[dict[str, Any]] = []
        for item in raw_excluded_recommendations:
            if (
                not isinstance(item, Mapping)
                or set(item)
                != {"episode_index", "recommendation_text", "exclusion_reason"}
                or type(item.get("episode_index")) is not int
                or not 1 <= item["episode_index"] <= raw["completed_opinion_episode_count"]
                or not isinstance(item.get("recommendation_text"), str)
                or not item["recommendation_text"].strip()
                or len(item["recommendation_text"]) > 320
                or item.get("exclusion_reason") not in _023_EXCLUSION_REASONS
            ):
                return None
            safe_excluded_recommendations.append(
                {
                    "episode_index": item["episode_index"],
                    "recommendation_text": item["recommendation_text"].strip(),
                    "exclusion_reason": item["exclusion_reason"],
                }
            )
        safe_facts["excluded_recommendations"] = safe_excluded_recommendations
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
        rule_id not in {"LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03"}
        or raw.get("consultation_assessment") not in {"明确", "不符合要求"}
    ):
        return None
    expected_keys = {"source_document_ids", "consultation_assessment"}
    if rule_id == "LX0609-03-01-01":
        expected_keys.update({"execution_record_state", "execution_candidate_count"})
    safe_keys = expected_keys - {"source_document_ids"}
    raw_keys = set(raw)
    if raw_keys != expected_keys and raw_keys != safe_keys:
        return None
    facts: dict[str, Any] = {"consultation_assessment": raw["consultation_assessment"]}
    if rule_id == "LX0609-03-01-01":
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
            if normalized_rule_id == "LX0609-03-01-04"
            else None
        )
        or _safe_legacy_assessment_facts(rule_id=normalized_rule_id, raw=raw)
    )


def _published_semantic_facts(rule_id: str, raw: dict[str, Any]) -> bool:
    if rule_id not in {"LX0609-03-01-02", "LX0609-03-01-03"}:
        return False
    expected_kind = ("consultation_application_quality_check" if rule_id == "LX0609-03-01-02"
                     else "consultation_opinion_quality_check")
    requirement = ("说明具体临床问题、会诊理由或明确会诊目的" if rule_id == "LX0609-03-01-02"
                   else "给出针对当前病情的明确诊疗意见")
    base = {"verification_kind", "episode_count", "document_count", "semantic_state", "checked_requirement"}
    if (set(raw) not in (base, base | {"episode_results"})
            or raw["verification_kind"] != expected_kind or raw["checked_requirement"] != requirement
            or type(raw["semantic_state"]) is not str
            or raw["semantic_state"] not in {"clear", "vague", "missing", "absent", "unknown", "mixed"}
            or type(raw["episode_count"]) is not int or not 0 <= raw["episode_count"] <= 100
            or type(raw["document_count"]) is not int or not 0 <= raw["document_count"] <= 100):
        return False
    if "episode_results" not in raw:
        return True  # 早期发布形态没有逐次明细。
    results = raw["episode_results"]
    if type(results) is not list or len(results) != raw["episode_count"]:
        return False
    states: list[str] = []
    title = "会诊申请单" if rule_id == "LX0609-03-01-02" else "会诊记录单"
    for index, item in enumerate(results, start=1):
        base_item = {"episode_index", "semantic_state"}
        locator = {"record_time", "document_title"}
        if (type(item) is not dict or set(item) not in (base_item, base_item | locator)
                or type(item["episode_index"]) is not int or item["episode_index"] != index
                or type(item["semantic_state"]) is not str
                or item["semantic_state"] not in {"clear", "vague", "missing", "unknown"}):
            return False
        if locator <= set(item) and (item["document_title"] != title or not _valid_record_time(item["record_time"])):
            return False
        states.append(item["semantic_state"])
    state_set = set(states)
    derived = "absent" if not state_set else next(iter(state_set)) if len(state_set) == 1 else "mixed"
    return raw["semantic_state"] == derived


def _published_recommendation_results(raw: dict[str, Any]) -> bool:
    results = raw["recommendation_results"]
    if type(results) is not list or len(results) != raw["recommendation_count"] or len(results) > 96:
        return False
    expected = {"episode_index", "recommendation_index", "action_type", "execution_state"}
    for index, item in enumerate(results, start=1):
        if (type(item) is not dict or set(item) != expected
                or type(item["episode_index"]) is not int
                or not 1 <= item["episode_index"] <= raw["completed_opinion_episode_count"]
                or type(item["recommendation_index"]) is not int or item["recommendation_index"] != index
                or type(item["action_type"]) is not str
                or item["action_type"] not in {"medication", "test", "procedure", "transfer", "monitoring", "other"}
                or type(item["execution_state"]) is not str
                or item["execution_state"] not in {"specific", "generic", "missing", "unknown"}):
            return False
    return all(raw[f"{state}_execution_count"] == sum(item["execution_state"] == state for item in results)
               for state in ("specific", "generic", "missing"))


def _published_recommendation_evidence(raw: dict[str, Any]) -> bool:
    evidence = raw["recommendation_evidence"]
    if type(evidence) is not list or len(evidence) != raw["recommendation_count"] or len(evidence) > 96:
        return False
    expected = {"episode_index", "recommendation_index", "execution_state", "opinion_evidence", "execution_evidence"}
    optional = {"recommendation_text"}
    if raw["verification_kind"] == "consultation_execution_quality_check":
        optional |= {"opinion_time", "missing_measures", "window_start_date", "declined_measures"}
    for index, item in enumerate(evidence, start=1):
        if (type(item) is not dict or not expected <= set(item) <= expected | optional
                or ("opinion_time" in item and not _valid_record_time(item["opinion_time"]))
                or ("missing_measures" in item and not _valid_missing_measures(item["missing_measures"]))
                or ("window_start_date" in item and not _valid_window_start(item["window_start_date"]))
                or ("declined_measures" in item and not _valid_missing_measures(item["declined_measures"]))
                or type(item["episode_index"]) is not int
                or not 1 <= item["episode_index"] <= raw["completed_opinion_episode_count"]
                or type(item["recommendation_index"]) is not int or item["recommendation_index"] != index
                or type(item["execution_state"]) is not str
                or item["execution_state"] not in {"specific", "generic", "missing", "unknown"}
                or ("recommendation_text" in item and (
                    type(item["recommendation_text"]) is not str
                    or not item["recommendation_text"].strip()
                    or len(item["recommendation_text"]) > 320
                ))):
            return False
        if ("recommendation_results" in raw
                and item["execution_state"] != raw["recommendation_results"][index - 1]["execution_state"]):
            return False
        for key in ("opinion_evidence", "execution_evidence"):
            projected = project_selected_grouped_document_refs(
                raw_refs=item[key], public=True,
                allowed_source_types=_RECOMMENDATION_EVIDENCE_SOURCE_TYPES,
            )
            if projected is None or projected != item[key]:
                return False
    return all(raw[f"{state}_execution_count"] == sum(item["execution_state"] == state for item in evidence)
               for state in ("specific", "generic", "missing"))


def _published_excluded_recommendations(raw: dict[str, Any]) -> bool:
    excluded = raw["excluded_recommendations"]
    return (
        type(excluded) is list
        and len(excluded) <= 96
        and all(
            type(item) is dict
            and set(item)
            == {"episode_index", "recommendation_text", "exclusion_reason"}
            and type(item["episode_index"]) is int
            and 1 <= item["episode_index"] <= raw["completed_opinion_episode_count"]
            and type(item["recommendation_text"]) is str
            and bool(item["recommendation_text"].strip())
            and len(item["recommendation_text"]) <= 320
            and item["exclusion_reason"] in _023_EXCLUSION_REASONS
            for item in excluded
        )
    )


def _published_execution_facts(rule_id: str, raw: dict[str, Any]) -> bool:
    if rule_id not in {"LX0609-03-01-01", "LX0609-03-01-04"}:
        return False
    is_023 = rule_id == "LX0609-03-01-04"
    base = {"verification_kind", "completed_opinion_episode_count", "recommendation_count",
            "specific_execution_count", "generic_execution_count", "missing_execution_count", "relation_state"}
    optional = (
        {"recommendation_evidence", "excluded_recommendations"}
        if is_023
        else {"recommendation_evidence", "recommendation_results"}
    )
    kind = "consultation_execution_quality_check" if is_023 else "consultation_execution_relation_check"
    states = ({"specific_execution", "execution_missing_or_generic", "not_triggered",
               "generic_or_copied_execution", "execution_record_absent", "source_incomplete",
               "association_unresolved", "source_error"} if is_023 else
              {"all_linked", "execution_missing", "not_triggered", "source_incomplete",
               "association_unresolved", "source_error"})
    if (not base <= set(raw) <= base | optional or raw["verification_kind"] != kind
            or type(raw["relation_state"]) is not str or raw["relation_state"] not in states
            or any(type(raw[key]) is not int or not 0 <= raw[key] <= 100 for key in (
                "completed_opinion_episode_count", "recommendation_count", "specific_execution_count",
                "generic_execution_count", "missing_execution_count"))):
        return False
    return (("recommendation_results" not in raw or _published_recommendation_results(raw))
            and ("recommendation_evidence" not in raw or _published_recommendation_evidence(raw))
            and ("excluded_recommendations" not in raw
                 or _published_excluded_recommendations(raw)))


def validate_published_consultation_facts(*, rule_id: str, raw: Any) -> dict[str, Any] | None:
    """仅验已发布公开 JSON，合法事实逐值返回，不重跑内部事实投影。"""
    normalized = str(rule_id or "").strip().upper()
    if not is_consultation_customer_rule(normalized) or type(raw) is not dict or any(type(key) is not str for key in raw):
        return None
    if _published_semantic_facts(normalized, raw) or _published_execution_facts(normalized, raw):
        return dict(raw)
    if normalized == "LX0609-03-01-04":
        if (set(raw) == {"failure_kind", "observed_expression", "missing_details"}
                and raw["failure_kind"] == "consultation_execution_too_generic"
                and raw["observed_expression"] == "仅笼统记录已按会诊意见执行"
                and type(raw["missing_details"]) is list
                and raw["missing_details"] == ["具体执行措施", "执行结果或后续安排"]):
            return dict(raw)
    if normalized in {"LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03"}:
        expected = ({"consultation_assessment", "execution_record_state", "execution_candidate_count"}
                    if normalized == "LX0609-03-01-01" else {"consultation_assessment"})
        if set(raw) == expected and type(raw["consultation_assessment"]) is str and raw["consultation_assessment"] in {"明确", "不符合要求"}:
            if normalized != "LX0609-03-01-01" or (
                type(raw["execution_record_state"]) is str
                and raw["execution_record_state"] in {"已发现明确执行记录", "未发现执行记录"}
                and type(raw["execution_candidate_count"]) is int
                and 0 <= raw["execution_candidate_count"] <= 100
            ):
                return dict(raw)
    return None
