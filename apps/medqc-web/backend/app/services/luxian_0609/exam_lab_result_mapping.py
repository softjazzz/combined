"""检查检验规则的结果映射与可展示事实投影。"""

from __future__ import annotations

from .ct_order_course_consistency import (
    RULE_ID as CT_CONSISTENCY_RULE,
    validate_ct_display_facts,
    ct_display_status_matches,
)

from dataclasses import dataclass
import re
from typing import Any, Collection, Mapping, Sequence

from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .exam_lab_course_time import (
    assess_fact_responses,
    has_time_sources,
    scan_unplaced_time_state,
)
from .exam_lab_fact_extraction import (
    ExamLabEventFact,
    ExamLabTextProjection,
    event_for_fact,
    event_result_carried_by_course,
    events_for_family,
)
from .handbook_exam_lab import REPORT_RULES as HANDBOOK_REPORT_RULES, safe_handbook_display_facts

# 报告后病程时间的受控说明：仅有提交时间 / 记录时间与报告时间冲突。
_RESPONSE_TIME_STATES = frozenset({"submit_only", "record_time_conflict"})


@dataclass(frozen=True)
class ExamLabOutcome:
    rule_id: str
    status: str
    reason_code: str
    fact_refs: tuple[str, ...] = ()


EXAM_LAB_CUSTOMER_RULE_IDS = frozenset(
    {
        CT_CONSISTENCY_RULE,
        "LX0609-06-01-02",
        "LX0609-06-01-03",
        "LX0609-06-01-04",
        "LX0609-06-01-05",
        "LX0609-06-03-02",
        "LX0609-06-03-03",
        "LX0609-06-03-04",
    }
)


def is_exam_lab_customer_rule(rule_id: str) -> bool:
    """返回由检查检验规则族拥有客户展示事实合同的规则。"""

    return str(rule_id or "").strip().upper() in EXAM_LAB_CUSTOMER_RULE_IDS


def _controlled_trigger_orders(value: Any) -> list[dict[str, str]] | None:
    if not isinstance(value, list) or not value or len(value) > 8:
        return None
    orders: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) not in (
            {"order_name"},
            {"order_name", "order_time"},
        ):
            return None
        order_name = item.get("order_name")
        order_time = item.get("order_time")
        if (
            not isinstance(order_name, str)
            or not order_name.strip()
            or len(order_name) > 200
            or "\n" in order_name
            or (
                order_time is not None
                and (
                    not isinstance(order_time, str)
                    or not order_time.strip()
                    or len(order_time) > 40
                    or "\n" in order_time
                )
            )
        ):
            return None
        order = {"order_name": order_name.strip()}
        if order_time is not None:
            order["order_time"] = order_time.strip()
        orders.append(order)
    return orders


_CONFLICT_TIMES_KEY = "result_conflict_record_times"


def _safe_conflict_times(value: Any) -> list[str] | None:
    """06-01-04 检查结果与病程一致性提示：只允许最多 8 个固定格式的病程记录时间。"""

    if (
        not isinstance(value, list)
        or not 1 <= len(value) <= 8
        or any(
            not isinstance(item, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", item)
            for item in value
        )
    ):
        return None
    return list(value)


_ANALYSIS_GAP_KEY = "analysis_gap_notes"
ANALYSIS_GAP_KINDS = frozenset({"listing_only", "conclusion_without_basis", "plan_without_basis"})

_REPORT_RESULT_TEXTS_KEY = "report_result_texts"


def _safe_report_result_texts(value: Any) -> list[str] | None:
    """06-01-05 客户可见的 CT/MRI 报告结果：仅允许短文本列表。"""

    if not isinstance(value, list) or not 1 <= len(value) <= 8:
        return None
    texts: list[str] = []
    total_chars = 0
    for item in value:
        if not isinstance(item, str):
            return None
        text = _clean(item)
        if not text or len(text) > 500 or text != item:
            return None
        total_chars += len(text)
        if total_chars > 2000:
            return None
        texts.append(text)
    return texts


def _safe_analysis_gap_notes(value: Any) -> list[dict[str, str]] | None:
    """06-01-05 修改建议：最多 8 条，只含固定格式的病程记录时间与受控不足类别。"""

    if not isinstance(value, list) or not 1 <= len(value) <= 8:
        return None
    notes = []
    for item in value:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"record_time", "gap"}
            or not isinstance(item["record_time"], str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", item["record_time"])
            or item["gap"] not in ANALYSIS_GAP_KINDS
        ):
            return None
        notes.append({"record_time": item["record_time"], "gap": item["gap"]})
    return notes


def safe_exam_lab_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """验证并剥离检查检验客户事实中的内部文书标识。

    这是 010/011/012/014/015 的唯一事实合同所有者。逐行文书证据由
    RuleDecision ``fact_refs`` 经公共投影生成，故本函数只返回客户可见字段。
    """

    normalized_rule_id = str(rule_id or "").strip().upper()
    if normalized_rule_id == CT_CONSISTENCY_RULE:
        return validate_ct_display_facts(raw)
    if normalized_rule_id not in EXAM_LAB_CUSTOMER_RULE_IDS or not isinstance(raw, Mapping):
        return None

    if normalized_rule_id in HANDBOOK_REPORT_RULES:
        return safe_handbook_display_facts(normalized_rule_id, raw)

    if (
        normalized_rule_id == "LX0609-06-01-02"
        and raw.get("requirement") == "order_course_report_consistency"
    ):
        allowed_public_keys = {
            "failure_kind",
            "verification_kind",
            "subject",
            "checked_sources",
            "requirement",
            "requirement_met",
            "order_count",
            "exam_master_count",
            "uniquely_linked_order_count",
            "unmatched_or_ambiguous_order_count",
            "association_issue_kind",
            "trigger_orders",
        }
        allowed_internal_keys = {"source_document_ids", "source_document_refs"}
        if not set(raw).issubset(allowed_public_keys | allowed_internal_keys):
            return None
        failure_kind = raw.get("failure_kind")
        verification_kind = raw.get("verification_kind")
        allowed_failure_kinds = {
            "exam_order_reason_missing",
            "exam_course_without_order",
            "exam_order_course_missing",
            "exam_report_missing",
            "exam_order_exam_association_failed",
            "exam_order_contract_data_gap",
        }
        if (
            (failure_kind is None) == (verification_kind is None)
            or (failure_kind is not None and failure_kind not in allowed_failure_kinds)
            or (
                verification_kind is not None
                and verification_kind != "exam_order_course_report_consistent"
            )
            or raw.get("subject") != "ct_mri"
            or raw.get("checked_sources")
            != ["exam_lab_order", "exam_master", "exam_lab_report", "course_record"]
            or type(raw.get("requirement_met")) is not bool
            or bool(raw.get("requirement_met")) != (verification_kind is not None)
        ):
            return None
        source_document_ids = raw.get("source_document_ids")
        if source_document_ids is not None and (
            not isinstance(source_document_ids, list)
            or any(not isinstance(item, str) for item in source_document_ids)
        ):
            return None
        source_document_refs = raw.get("source_document_refs")
        if source_document_refs is not None:
            if not isinstance(source_document_refs, list) or len(source_document_refs) > 8:
                return None
            for item in source_document_refs:
                if (
                    not isinstance(item, Mapping)
                    or set(item) != {"source_type", "source_document_id"}
                    or item.get("source_type") not in {"exam_master", "exam_item_report"}
                    or not isinstance(item.get("source_document_id"), str)
                ):
                    return None
        raw_trigger_orders = raw.get("trigger_orders")
        trigger_orders = (
            _controlled_trigger_orders(raw_trigger_orders)
            if raw_trigger_orders is not None
            else None
        )
        if raw_trigger_orders is not None and trigger_orders is None:
            return None
        facts: dict[str, Any] = {
            "failure_kind" if failure_kind is not None else "verification_kind": (
                failure_kind or verification_kind
            ),
            "subject": "ct_mri",
            "checked_sources": [
                "exam_lab_order",
                "exam_master",
                "exam_lab_report",
                "course_record",
            ],
            "requirement": "order_course_report_consistency",
            "requirement_met": bool(raw.get("requirement_met")),
        }
        if trigger_orders is not None:
            facts["trigger_orders"] = trigger_orders
        association_keys = (
            "order_count",
            "exam_master_count",
            "uniquely_linked_order_count",
            "unmatched_or_ambiguous_order_count",
        )
        is_association_failure = failure_kind == "exam_order_exam_association_failed"
        if not is_association_failure and any(key in raw for key in association_keys):
            return None
        if not is_association_failure and "association_issue_kind" in raw:
            return None
        if is_association_failure:
            counts = {key: raw.get(key) for key in association_keys}
            if any(type(value) is not int or value < 0 for value in counts.values()):
                return None
            order_count = counts["order_count"]
            master_count = counts["exam_master_count"]
            uniquely_linked = counts["uniquely_linked_order_count"]
            unmatched = counts["unmatched_or_ambiguous_order_count"]
            # 合并检查的一条主记录可显式覆盖多条医嘱，唯一关联医嘱数可以超过
            # 主记录数；只要求不超过医嘱数。
            if (
                uniquely_linked > order_count
                or unmatched != order_count - uniquely_linked
            ):
                return None
            issue_kind = raw.get("association_issue_kind")
            if issue_kind not in {
                "invalid_business_key",
                "exam_master_without_order",
                "ambiguous_exam_master_linkage",
                "order_without_exam_master",
                "mixed_association_failure",
                "association_cardinality_mismatch",
            }:
                return None
            facts.update(counts)
            facts["association_issue_kind"] = issue_kind
        return facts

    if raw.get("failure_kind") == "exam_lab_target_report_missing":
        expected_subject = (
            "ct_mri"
            if normalized_rule_id in {"LX0609-06-01-04", "LX0609-06-01-05"}
            else "culture_susceptibility"
        )
        trigger_orders = _controlled_trigger_orders(raw.get("trigger_orders"))
        if (
            set(raw)
            != {"failure_kind", "subject", "checked_sources", "trigger_orders"}
            or raw.get("subject") != expected_subject
            or raw.get("checked_sources") != ["exam_lab_order", "exam_lab_report"]
            or trigger_orders is None
        ):
            return None
        return {
            "failure_kind": "exam_lab_target_report_missing",
            "subject": expected_subject,
            "checked_sources": ["exam_lab_order", "exam_lab_report"],
            "trigger_orders": trigger_orders,
        }

    requirements = {
        "LX0609-06-01-02": "reason_before_order",
        "LX0609-06-01-04": "result_recording_within_24h",
        "LX0609-06-01-05": "positive_result_analysis_within_24h",
        "LX0609-06-03-03": "result_recording_within_24h",
        "LX0609-06-03-04": "positive_result_analysis_within_24h",
    }
    expected_subject = (
        "ct_mri"
        if normalized_rule_id in {"LX0609-06-01-02", "LX0609-06-01-04", "LX0609-06-01-05"}
        else "culture_susceptibility"
    )
    expected_phase = "order" if normalized_rule_id == "LX0609-06-01-02" else "report"
    expected_sources = (
        ["exam_lab_order", "course_record"]
        if normalized_rule_id == "LX0609-06-01-02"
        else ["exam_lab_report", "course_record"]
    )
    allowed_event_keys = {
        "failure_kind",
        "verification_kind",
        "subject",
        "requirement",
        "event_phase",
        "checked_sources",
        "applicable",
        "requirement_met",
        "positive_state",
        "report_time",
        "response_record_time",
        "threshold_hours",
        "response_record_count",
        "interval_hours",
        "response_time_state",
        "reviewed_record_scope",
        "event_count",
        "event_position",
        "event_results",
        "source_document_ids",
        "source_document_refs",
    }
    if normalized_rule_id == "LX0609-06-01-04":
        allowed_event_keys.add(_CONFLICT_TIMES_KEY)
    if normalized_rule_id == "LX0609-06-01-05":
        allowed_event_keys.add(_ANALYSIS_GAP_KEY)
        allowed_event_keys.add(_REPORT_RESULT_TEXTS_KEY)
    if not set(raw).issubset(allowed_event_keys):
        return None
    source_document_ids = raw.get("source_document_ids")
    if source_document_ids is not None and (
        not isinstance(source_document_ids, list)
        or len(source_document_ids) > 8
        or any(
            not isinstance(item, str)
            or not item.strip()
            or len(item) > 256
            or "\n" in item
            or "\r" in item
            for item in source_document_ids
        )
    ):
        return None
    source_document_refs = raw.get("source_document_refs")
    if source_document_refs is not None:
        if not isinstance(source_document_refs, list) or len(source_document_refs) > 8:
            return None
        allowed_source_types = {
            "exam_master",
            "exam_item_report",
            "labtest_master",
            "labtest_item_report",
            "first_course_record",
            "daily_course_record",
            "senior_course_record",
            "rescue_record",
        }
        for item in source_document_refs:
            if (
                not isinstance(item, Mapping)
                or set(item) != {"source_type", "source_document_id"}
                or item.get("source_type") not in allowed_source_types
                or not isinstance(item.get("source_document_id"), str)
                or not item["source_document_id"].strip()
                or len(item["source_document_id"]) > 256
                or "\n" in item["source_document_id"]
                or "\r" in item["source_document_id"]
            ):
                return None
    failure_kind = raw.get("failure_kind")
    verification_kind = raw.get("verification_kind")
    if (
        (
            failure_kind != "exam_lab_requirement_not_documented"
            and verification_kind
            not in {"exam_lab_requirement_checked", "exam_lab_event_review_incomplete"}
        )
        or (failure_kind is not None and verification_kind is not None)
        or raw.get("subject") != expected_subject
        or raw.get("requirement") != requirements[normalized_rule_id]
        or raw.get("event_phase") != expected_phase
        or raw.get("checked_sources") != expected_sources
    ):
        return None
    facts = {
        "failure_kind" if failure_kind is not None else "verification_kind": (
            "exam_lab_requirement_not_documented"
            if failure_kind is not None
            else verification_kind
        ),
        "subject": expected_subject,
        "requirement": requirements[normalized_rule_id],
        "event_phase": expected_phase,
        "checked_sources": list(expected_sources),
    }
    for key in ("applicable", "requirement_met"):
        value = raw.get(key)
        if value is not None:
            if not isinstance(value, bool):
                return None
            facts[key] = value
    positive_state = raw.get("positive_state")
    if positive_state is not None:
        if positive_state not in {"positive", "negative", "not_relevant", "unknown"}:
            return None
        if (
            positive_state == "unknown"
            and verification_kind != "exam_lab_event_review_incomplete"
        ):
            return None
        facts["positive_state"] = positive_state
    for key in ("report_time", "response_record_time"):
        value = raw.get(key)
        if value is not None:
            if not isinstance(value, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value
            ):
                return None
            facts[key] = value
    threshold_hours = raw.get("threshold_hours")
    if threshold_hours is not None:
        if threshold_hours != 24:
            return None
        facts["threshold_hours"] = 24
    response_count = raw.get("response_record_count")
    if response_count is not None:
        if not isinstance(response_count, int) or response_count < 0:
            return None
        facts["response_record_count"] = response_count
    interval_hours = raw.get("interval_hours")
    if interval_hours is not None:
        if not isinstance(interval_hours, (int, float)) or interval_hours < 0:
            return None
        facts["interval_hours"] = round(float(interval_hours), 2)
    response_time_state = raw.get("response_time_state")
    if response_time_state is not None:
        if response_time_state not in _RESPONSE_TIME_STATES:
            return None
        facts["response_time_state"] = response_time_state
    reviewed_record_scope = raw.get("reviewed_record_scope")
    if reviewed_record_scope is not None:
        if reviewed_record_scope != "首次病程记录及后续病程记录":
            return None
        facts["reviewed_record_scope"] = reviewed_record_scope
    if _CONFLICT_TIMES_KEY in raw:
        conflict_times = _safe_conflict_times(raw[_CONFLICT_TIMES_KEY])
        if conflict_times is None:
            return None
        facts[_CONFLICT_TIMES_KEY] = conflict_times
    if _ANALYSIS_GAP_KEY in raw:
        gap_notes = _safe_analysis_gap_notes(raw[_ANALYSIS_GAP_KEY])
        if gap_notes is None:
            return None
        facts[_ANALYSIS_GAP_KEY] = gap_notes
    if _REPORT_RESULT_TEXTS_KEY in raw:
        report_result_texts = _safe_report_result_texts(raw[_REPORT_RESULT_TEXTS_KEY])
        if report_result_texts is None or positive_state != "positive":
            return None
        facts[_REPORT_RESULT_TEXTS_KEY] = report_result_texts
    event_count = raw.get("event_count")
    event_position = raw.get("event_position")
    if event_count is not None or event_position is not None:
        if (
            type(event_count) is not int
            or type(event_position) is not int
            or not 1 <= event_position <= event_count <= 32
        ):
            return None
        facts["event_count"] = event_count
        facts["event_position"] = event_position
    raw_event_results = raw.get("event_results")
    if raw_event_results is not None:
        if (
            not isinstance(raw_event_results, list)
            or event_count is None
            or len(raw_event_results) != event_count
        ):
            return None
        allowed_event_keys = {
            "event_position",
            "event_status",
            "report_time",
            "positive_state",
            "response_record_count",
            "response_record_time",
            "interval_hours",
            "response_time_state",
            "applicable",
            "requirement_met",
        }
        if normalized_rule_id == "LX0609-06-01-04":
            allowed_event_keys.add(_CONFLICT_TIMES_KEY)
        if normalized_rule_id == "LX0609-06-01-05":
            allowed_event_keys.add(_ANALYSIS_GAP_KEY)
            allowed_event_keys.add(_REPORT_RESULT_TEXTS_KEY)
        safe_event_results: list[dict[str, Any]] = []
        # 顺序合同（2026-09-12 收口）：事实的**语义**由 event_position 决定，物理顺序
        # 不是合同的一部分。此前用 enumerate 下标与 event_position 做相等比对，会把
        # 「位置集合完整、但模型返回乱序」判成合同失败，继而在 finalizer 被升级为
        # technical_error（实测 C04 的 r2/r3；生产端已在执行器内改为升序投影）。
        # 这里改为按 event_position 建键：**仍然严格要求位置集合恰为 1..event_count
        # 且不重不漏**，值校验（允许键、event_status 枚举、时间格式、计数非负等）
        # 一条都没有放宽，只是不再要求物理顺序。
        by_position: dict[int, Mapping[str, Any]] = {}
        for item in raw_event_results:
            if not isinstance(item, Mapping) or set(item) - allowed_event_keys:
                return None
            item_position = item.get("event_position")
            if (
                type(item_position) is not int
                or not 1 <= item_position <= event_count
                or item_position in by_position
            ):
                return None
            by_position[item_position] = item
        if set(by_position) != set(range(1, event_count + 1)):
            return None
        for expected_position in range(1, event_count + 1):
            item = by_position[expected_position]
            if item.get("event_status") not in {
                "compliant",
                "non_compliant",
                "not_applicable",
                "data_gap",
                "evaluation_unknown",
            }:
                return None
            safe_item: dict[str, Any] = {
                "event_position": expected_position,
                "event_status": item["event_status"],
            }
            for key in ("report_time", "response_record_time"):
                value = item.get(key)
                if value is not None:
                    if not isinstance(value, str) or not re.fullmatch(
                        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value
                    ):
                        return None
                    safe_item[key] = value
            event_positive_state = item.get("positive_state")
            if event_positive_state is not None:
                if event_positive_state not in {
                    "positive", "negative", "not_relevant", "unknown"
                }:
                    return None
                if (
                    event_positive_state == "unknown"
                    and item["event_status"] not in {"data_gap", "evaluation_unknown"}
                ):
                    return None
                safe_item["positive_state"] = event_positive_state
            event_response_count = item.get("response_record_count")
            if event_response_count is not None:
                if type(event_response_count) is not int or event_response_count < 0:
                    return None
                safe_item["response_record_count"] = event_response_count
            event_interval = item.get("interval_hours")
            if event_interval is not None:
                if (
                    isinstance(event_interval, bool)
                    or not isinstance(event_interval, (int, float))
                    or event_interval < 0
                ):
                    return None
                safe_item["interval_hours"] = round(float(event_interval), 2)
            item_time_state = item.get("response_time_state")
            if item_time_state is not None:
                if item_time_state not in _RESPONSE_TIME_STATES:
                    return None
                safe_item["response_time_state"] = item_time_state
            for key in ("applicable", "requirement_met"):
                value = item.get(key)
                if value is not None:
                    if not isinstance(value, bool):
                        return None
                    safe_item[key] = value
            if _CONFLICT_TIMES_KEY in item:
                conflict_times = _safe_conflict_times(item[_CONFLICT_TIMES_KEY])
                if conflict_times is None:
                    return None
                safe_item[_CONFLICT_TIMES_KEY] = conflict_times
            if _ANALYSIS_GAP_KEY in item:
                gap_notes = _safe_analysis_gap_notes(item[_ANALYSIS_GAP_KEY])
                if gap_notes is None:
                    return None
                safe_item[_ANALYSIS_GAP_KEY] = gap_notes
            if _REPORT_RESULT_TEXTS_KEY in item:
                report_result_texts = _safe_report_result_texts(item[_REPORT_RESULT_TEXTS_KEY])
                if report_result_texts is None or event_positive_state != "positive":
                    return None
                safe_item[_REPORT_RESULT_TEXTS_KEY] = report_result_texts
            safe_event_results.append(safe_item)
        if (
            verification_kind == "exam_lab_event_review_incomplete"
            and not any(
                item["event_status"] in {"data_gap", "evaluation_unknown"}
                for item in safe_event_results
            )
        ):
            return None
        facts["event_results"] = safe_event_results
    return facts


def exam_lab_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """校验 2026 手册新增报告完整性事实与已裁决状态一致。"""

    normalized_rule_id = str(rule_id or "").strip().upper()
    if normalized_rule_id == CT_CONSISTENCY_RULE:
        return ct_display_status_matches(status, safe_facts)
    if normalized_rule_id not in HANDBOOK_REPORT_RULES:
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    items = safe_facts.get("event_results")
    if not isinstance(items, list):
        return False
    event_statuses = [item.get("event_status") for item in items if isinstance(item, Mapping)]
    if len(event_statuses) != len(items):
        return False
    complete = safe_facts.get("review_scope_complete") is True
    expected = (
        "non_compliant" if "non_compliant" in event_statuses
        else "data_gap" if not complete or "data_gap" in event_statuses
        else "compliant" if "compliant" in event_statuses
        else "not_applicable"
    )
    return str(status or "").strip().lower() == expected


def build_exam_lab_rule_decision(
    *,
    outcome: ExamLabOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
    allowed_source_keys: Collection[str],
    evaluator_version: str,
) -> RuleDecision:
    """将受控结果映射为 RuleDecision；来源白名单必须由调用方显式提供。"""

    selected_document_refs = tuple(dict.fromkeys(outcome.fact_refs))
    # 事件级判定必须原样消费 executor 实际选中的逐行文书引用；Binding 会在
    # 单规则边界验证其确属当前 Snapshot 的允许来源。空引用就是没有实际逐行
    # 判定材料，不能退回为 observation 引用并诱导后续层猜测具体文书。
    refs = selected_document_refs
    if outcome.status == "compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        )
    elif outcome.status == "non_compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "requirement_violated",
        )
    elif outcome.status == "not_applicable":
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "evaluation_window_not_mature"
            if outcome.reason_code == "evaluation_window_not_mature"
            else "eligibility_not_met"
            if outcome.reason_code == "admission_window_exempt"
            else "trigger_absent_complete",
        )
    elif outcome.status == "data_gap":
        normalized_gap_reasons = {
            # 执行器内部保留事件级缺口；RuleDecision 只交付统一合同已批准的
            # 受控原因码，但不能把不同缺口全部压成 required_field_missing。
            "target_report_missing": "target_report_missing",
            "authoritative_report_time_missing": "authoritative_report_time_missing",
            "multiple_event_or_time_conflict": "association_failed",
            "course_projection_incomplete": "source_truncated",
            # 仅有提交时间（无记录时间）的病程不能证明 24 小时内/外：沿用
            # 已批准的“文书完成时间缺失”原因码，不新增公共原因。
            "course_record_time_unproven": "document_completion_time_missing",
        }
        preserved_gap_reasons = {
            "target_report_missing",
            "authoritative_time_missing",
            "authoritative_report_time_missing",
            "authoritative_time_conflict",
            "evaluation_window_not_mature",
            "positive_assertion_not_explicit",
            # 010 已明确要求以业务键唯一关联医嘱、检查和报告。关联不唯一时
            # 必须将真实原因原样交付，不能压缩成笼统字段缺失。
            "association_failed",
            "document_completion_time_missing",
        }
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            normalized_gap_reasons.get(
                outcome.reason_code,
                outcome.reason_code
                if outcome.reason_code in preserved_gap_reasons
                else "source_unavailable"
                if "unavailable" in outcome.reason_code
                else "required_field_missing",
            ),
        )
    elif outcome.status == "evaluation_unknown":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "semantic_output_unknown",
        )
    elif outcome.status == "technical_error":
        reason_code = (
            "source_query_error"
            if outcome.reason_code == "source_query_error"
            else "model_invalid_output"
            if outcome.reason_code == "exam_lab_llm_invalid_output"
            else "model_transport_error"
            if outcome.reason_code == "exam_lab_llm_failure"
            else "executor_exception"
        )
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            reason_code,
        )
    else:
        raise ValueError("unsupported exam lab outcome")
    applicability, evidence_state, qc_direction, reason_code = dimensions
    if (
        not refs
        and outcome.status == "not_applicable"
        and reason_code == "trigger_absent_complete"
    ):
        # 没有触发事件时，允许来源快照仅用于证明相关完整资料已被核对。
        # 这不是事件文书的回退：公共投影会将 trigger_absent_complete 映射为
        # 空客户证据，后续层也不得据此反查或猜测具体文书。
        allowed_keys = set(allowed_source_keys)
        refs = tuple(
            dict.fromkeys(
                observation.snapshot_ref.removeprefix("sha256:")
                for observation in snapshot.observations
                if observation.source_key in allowed_keys
            )
        )
    return RuleDecision(
        rule_id=outcome.rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version=evaluator_version,
        confidence=None,
    )


def build_default_display_facts(
    *,
    rule_id: str,
    status: str,
    reason_code: str,
    source_document_ids: Sequence[str] = (),
) -> Mapping[str, Any] | None:
    """仅为可确定的不合规输出可展示的检查/检验事实，不携带正文或模型输出。"""

    if status != "non_compliant":
        return None
    if reason_code not in {"exam_order_reason_missing", "exam_lab_text_fact"}:
        return None

    def with_document_ids(facts: dict[str, Any]) -> dict[str, Any]:
        # document_id 仅在来源行显式提供时才写入内部事实。后续聚合器须将其
        # 转为 HMAC evidence_ref；这里绝不根据 order_id、行号或正文猜测文书。
        ids = tuple(
            dict.fromkeys(
                value
                for raw in source_document_ids
                if (value := _clean(raw))
            )
        )
        if ids:
            facts["source_document_ids"] = list(ids)
        return facts

    if rule_id == "LX0609-06-01-02":
        return with_document_ids({
            "failure_kind": "exam_lab_requirement_not_documented",
            "subject": "ct_mri",
            "requirement": "reason_before_order",
            "event_phase": "order",
            "checked_sources": ["exam_lab_order", "course_record"],
        })
    if rule_id in {"LX0609-06-01-04", "LX0609-06-03-03"}:
        return with_document_ids({
            "failure_kind": "exam_lab_requirement_not_documented",
            "subject": "ct_mri" if rule_id == "LX0609-06-01-04" else "culture_susceptibility",
            "requirement": "result_recording_within_24h",
            "event_phase": "report",
            "checked_sources": ["exam_lab_report", "course_record"],
        })
    if rule_id in {"LX0609-06-01-05", "LX0609-06-03-04"}:
        return with_document_ids({
            "failure_kind": "exam_lab_requirement_not_documented",
            "subject": "ct_mri" if rule_id == "LX0609-06-01-05" else "culture_susceptibility",
            "requirement": "positive_result_analysis_within_24h",
            "event_phase": "report",
            "checked_sources": ["exam_lab_report", "course_record"],
        })
    return None


def build_text_outcome_display_facts(
    *,
    rule_id: str,
    status: str,
    fact: ExamLabEventFact,
    projection: ExamLabTextProjection,
    event_results: Sequence[Mapping[str, Any]] = (),
    event_source_document_refs: Sequence[Mapping[str, str]] = (),
    include_data_gap: bool = False,
) -> Mapping[str, Any] | None:
    """输出报告事件、响应病程和24小时计算事实；仅公开报告结果，不公开病程正文。"""

    if (
        rule_id not in {"LX0609-06-01-04", "LX0609-06-01-05", "LX0609-06-03-03", "LX0609-06-03-04"}
        or (
            status not in {"compliant", "non_compliant", "not_applicable"}
            and not (
                include_data_gap
                and status in {"data_gap", "evaluation_unknown"}
            )
        )
    ):
        return None
    is_exam_rule = rule_id in {"LX0609-06-01-04", "LX0609-06-01-05"}
    event = event_for_fact(projection, fact)
    if event is None:
        return None
    subject = "ct_mri" if is_exam_rule else "culture_susceptibility"
    analysis_rule = rule_id in {"LX0609-06-01-05", "LX0609-06-03-04"}
    requirement = (
        "positive_result_analysis_within_24h"
        if analysis_rule
        else "result_recording_within_24h"
    )
    time_state: str | None = None
    if has_time_sources(projection):
        assessed = assess_fact_responses(
            projection=projection,
            event=event,
            refs=fact.course_doc_refs,
            carries_result=event_result_carried_by_course,
        )
        after_report = tuple(
            item
            for item in assessed
            if item.kind in {"in_window", "late", "submit_unconfirmed"}
        )
        # 提交时间不是记录时间：只有记录时间才可作为“最早相关病程”时间和间隔。
        response_times = sorted(
            item.effective
            for item in after_report
            if item.basis == "record" and item.effective is not None
        )
        response_count = len(after_report)
        if any(item.kind == "conflict" for item in assessed):
            time_state = "record_time_conflict"
        elif any(item.basis == "submit" for item in after_report):
            time_state = "submit_only"
        elif status == "data_gap":
            time_state = scan_unplaced_time_state(projection=projection, event=event)
        if status == "non_compliant":
            time_state = None
    else:
        response_times = sorted(
            value
            for ref in fact.course_doc_refs
            if (value := projection.course_times.get(ref)) is not None
            and event.report_time is not None
            and value >= event.report_time
        )
        response_count = len(response_times)
    first_response = response_times[0] if response_times else None
    facts: dict[str, Any] = {
        ("failure_kind" if status == "non_compliant" else "verification_kind"): (
            "exam_lab_requirement_not_documented"
            if status == "non_compliant"
            else "exam_lab_event_review_incomplete"
            if status in {"data_gap", "evaluation_unknown"}
            else "exam_lab_requirement_checked"
        ),
        "subject": subject,
        "requirement": requirement,
        "event_phase": "report",
        "checked_sources": ["exam_lab_report", "course_record"],
        "positive_state": fact.positive_state,
        "threshold_hours": 24,
        "response_record_count": response_count,
        "event_count": len(events_for_family(
            projection, "exam" if is_exam_rule else "culture"
        )),
        "event_position": fact.event_position,
    }
    if rule_id == "LX0609-06-01-05" and fact.positive_state == "positive":
        report_result_texts: list[str] = []
        total_chars = 0
        for raw_text in event.report_result_texts:
            text = _clean(raw_text)
            if not text or text in report_result_texts:
                continue
            remaining = 2000 - total_chars
            if remaining <= 0 or len(report_result_texts) >= 8:
                break
            text = text[: min(500, remaining)].strip()
            if text:
                report_result_texts.append(text)
                total_chars += len(text)
        if report_result_texts:
            facts[_REPORT_RESULT_TEXTS_KEY] = report_result_texts
    if status != "data_gap":
        facts["applicable"] = status != "not_applicable"
    # 对报告后病程规则，向客户明确“查找范围”，而不是把内部 source key
    # 直接交给界面。该字段描述的是已核对范围，不是命中的关键证据。
    facts["reviewed_record_scope"] = "首次病程记录及后续病程记录"
    if status in {"compliant", "non_compliant"}:
        facts["requirement_met"] = status == "compliant"
    if time_state is not None:
        facts["response_time_state"] = time_state
    if event.report_time is not None:
        facts["report_time"] = event.report_time.strftime("%Y-%m-%d %H:%M:%S")
    if first_response is not None and event.report_time is not None:
        facts["response_record_time"] = first_response.strftime("%Y-%m-%d %H:%M:%S")
        facts["interval_hours"] = round(
            (first_response - event.report_time).total_seconds() / 3600,
            2,
        )
    source_document_refs = projection.source_document_refs or {}
    evidence_refs = tuple(fact.evidence_refs)
    # 015 的病程证据必须经过同一培养事件绑定。若模型引用全部被
    # 过滤，不能把当前投影中的其他培养文书（如导管尖端培养）整体
    # 回填到客户证据，否则会制造跨事件的“关键证据”。
    if (
        status == "non_compliant"
        and not fact.course_doc_refs
        and rule_id != "LX0609-06-03-04"
    ):
        evidence_refs = tuple((*evidence_refs, *projection.course_times.keys()))
    located_documents = [
        {"source_type": source_type, "source_document_id": source_document_id}
        for ref in dict.fromkeys(evidence_refs)
        if (located := source_document_refs.get(ref)) is not None
        for source_type, source_document_id in (located,)
    ]
    all_located_documents = [*located_documents, *event_source_document_refs]
    if all_located_documents:
        facts["source_document_refs"] = list(
            {
                (str(item["source_type"]), str(item["source_document_id"])): {
                    "source_type": str(item["source_type"]),
                    "source_document_id": str(item["source_document_id"]),
                }
                for item in all_located_documents
                if isinstance(item, Mapping)
                and item.get("source_type")
                and item.get("source_document_id")
            }.values()
        )[:8]
    if event_results:
        facts["event_results"] = [dict(item) for item in event_results]
    return facts


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


__all__ = [
    "EXAM_LAB_CUSTOMER_RULE_IDS",
    "exam_lab_customer_fact_status_is_valid",
    "ExamLabOutcome",
    "build_default_display_facts",
    "build_exam_lab_rule_decision",
    "build_text_outcome_display_facts",
    "is_exam_lab_customer_rule",
    "safe_exam_lab_customer_display_facts",
]
