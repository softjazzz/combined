from __future__ import annotations

from copy import deepcopy

import pytest

from app.services.luxian_0609_result_schema import CANONICAL_RESULT_STATUSES


def _finalize(result: dict):
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_canonical_result,
    )

    return finalize_luxian_0609_canonical_result(result)


def test_finalizer_delegates_consultation_facts_to_the_family_projection() -> None:
    from app.services.luxian_0609.canonical_result_finalizer import (
        validate_luxian_0609_executor_customer_display_facts,
    )

    facts = validate_luxian_0609_executor_customer_display_facts(
        rule_id="LX0609-022",
        raw={
            "verification_kind": "consultation_opinion_quality_check",
            "episode_count": 1,
            "document_count": 1,
            "semantic_state": "clear",
            "checked_requirement": "给出针对当前病情的明确诊疗意见",
            "source_document_ids": ["CONSULT-1"],
            "episode_results": [
                {
                    "episode_index": 1,
                    "semantic_state": "clear",
                    "source_document_id": "CONSULT-1",
                    "record_time": "2026-07-20 01:00:00",
                    "document_title": "会诊记录单",
                }
            ],
        },
    )

    assert facts is not None
    assert "source_document_ids" not in facts
    assert "source_document_id" not in str(facts)


def test_finalizer_requires_public_fact_ref_evidence_for_migrated_surgery_rules() -> None:
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalizer_requires_public_fact_ref_evidence,
    )

    assert all(
        finalizer_requires_public_fact_ref_evidence(rule_id)
        for rule_id in ("LX0609-034", "LX0609-036", "LX0609-039", "LX0609-040")
    )
    assert all(
        not finalizer_requires_public_fact_ref_evidence(rule_id)
        for rule_id in ("LX0609-029", "LX0609-035", "LX0609-037", "LX0609-038")
    )


@pytest.mark.parametrize(
    ("rule_id", "raw"),
    (
        (
            "LX0609-030",
            {
                "verification_kind": "surgery_document_present",
                "target_document": "surgery_record",
                "performed_surgery_confirmed": True,
            },
        ),
        (
            "LX0609-032",
            {
                "failure_kind": "surgery_document_blank",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
        ),
    ),
)
def test_finalizer_delegates_surgery_presence_facts_without_claiming_public_evidence(
    rule_id: str, raw: dict[str, object]
) -> None:
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalizer_owns_executor_customer_display_facts,
        finalizer_requires_public_fact_ref_evidence,
        validate_luxian_0609_executor_customer_display_facts,
    )
    from app.services.luxian_0609.surgery_presence_result_mapping import (
        safe_surgery_presence_customer_display_facts,
    )

    assert finalizer_owns_executor_customer_display_facts(rule_id) is True
    assert finalizer_requires_public_fact_ref_evidence(rule_id) is False
    assert validate_luxian_0609_executor_customer_display_facts(
        rule_id=rule_id, raw=raw
    ) == safe_surgery_presence_customer_display_facts(rule_id=rule_id, raw=raw)


@pytest.mark.parametrize(
    ("rule_id", "raw_facts"),
    (
        (
            "LX0609-069",
            {
                "verification_kind": "consultation_timeliness_check",
                "threshold_hours": 24,
                "actual_interval_hours": [0.0],
                "request_times": ["2026-07-01"],
                "record_times": ["2026-07-01"],
                "event_results": [
                    {
                        "sequence": 1,
                        "request_time": "2026-07-01",
                        "completion_time": "2026-07-01",
                        "interval_seconds": 0,
                        "outcome": "within_threshold",
                    }
                ],
            },
        ),
        (
            "LX0609-071",
            {
                "verification_kind": "physician_handoff_timeliness_check",
                "change_time": "2026-07-01 08:00:00",
                "handoff_times": ["2026-07-01 07:50:00"],
                "handover_times": ["2026-07-01 14:00:00"],
                "handover_threshold_hours": 24,
            },
        ),
        (
            "LX0609-072",
            {
                "failure_kind": "transfer_records_missing",
                "transfer_order_count": 1,
                "transfer_in_count": 0,
                "transfer_out_count": 1,
            },
        ),
        (
            "LX0609-073",
            {
                "verification_kind": "transfer_record_presence_check",
                "transfer_order_time": "2026-07-01 08:00:00",
                "transfer_in_time": None,
                "transfer_out_time": "2026-07-01 10:00:00",
                "transfer_in_associated": False,
                "transfer_out_associated": True,
            },
        ),
        (
            "LX0609-074",
            {
                "verification_kind": "diagnosis_change_documentation_check",
                "diagnosis_change_count": 1,
                "reason_recorded": True,
                "basis_recorded": True,
            },
        ),
    ),
)
def test_finalizer_delegates_continuity_facts_to_the_family_mapping(
    rule_id: str,
    raw_facts: dict,
) -> None:
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalizer_owns_executor_customer_display_facts,
        finalizer_requires_public_fact_ref_evidence,
        validate_luxian_0609_executor_customer_display_facts,
    )
    from app.services.luxian_0609.continuity_result_mapping import (
        safe_continuity_customer_display_facts,
    )

    assert finalizer_owns_executor_customer_display_facts(rule_id) is True
    assert finalizer_requires_public_fact_ref_evidence(rule_id) is True
    assert validate_luxian_0609_executor_customer_display_facts(
        rule_id=rule_id,
        raw=raw_facts,
    ) == safe_continuity_customer_display_facts(rule_id=rule_id, raw=raw_facts)


@pytest.mark.parametrize(
    "rule_id",
    ("LX0609-069", "LX0609-071", "LX0609-072", "LX0609-073", "LX0609-074"),
)
def test_continuity_finalizer_converts_invalid_typed_facts_to_technical_error(
    rule_id: str,
) -> None:
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_executor_customer_display_facts,
        finalizer_rejects_invalid_public_executor_customer_display_facts,
    )

    assert finalizer_rejects_invalid_public_executor_customer_display_facts(rule_id)
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": rule_id,
            "status": "non_compliant",
            "reason_code": "requirement_violated",
            "findings": "不得保留的临床结论",
            "customer_evidence": [{"source_document_id": "PRIVATE-CONTINUITY"}],
        },
        raw_facts={"raw_private_text": "PRIVATE-CONTINUITY-FACT"},
    )

    assert handled is True
    assert (finalized["status"], finalized["reason_code"]) == (
        "technical_error",
        "model_invalid_output",
    )
    assert "customer_display_facts" not in finalized
    assert "customer_evidence" not in finalized


def test_finalizer_converts_invalid_executor_facts_to_isolated_technical_error() -> None:
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_executor_customer_display_facts,
    )

    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-022",
            "status": "non_compliant",
            "reason_code": "requirement_violated",
            "customer_display_facts": {"private": "must not survive"},
            "customer_evidence": [{"source_document_id": "PRIVATE-1"}],
            "criterion_results": [{"criterion_id": "semantic"}],
            "data_gap_details": {"reason_code": "unexpected_gap"},
            "findings": "临床结论不得残留",
            "evidence": "证据不得残留",
            "suggestion": "建议不得残留",
        },
        raw_facts={"PRIVATE_UNKNOWN": "PRIVATE-CONSULTATION-TEXT"},
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["result_status"] == "technical_error"
    assert finalized["reason_code"] == "model_invalid_output"
    assert finalized["is_compliant"] is None
    assert not {
        "customer_display_facts",
        "customer_evidence",
        "criterion_results",
        "data_gap_details",
        "findings",
        "evidence",
        "suggestion",
    } & set(finalized)


def test_finalizer_converts_invalid_basic_timeliness_facts_to_technical_error() -> None:
    """基础时限族与其他已迁出合同一致：无效执行器 facts 不得伪装成临床结论。"""

    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_executor_customer_display_facts,
        finalizer_rejects_invalid_public_executor_customer_display_facts,
    )

    assert finalizer_rejects_invalid_public_executor_customer_display_facts(
        "LX0609-005"
    ) is True
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-005",
            "status": "non_compliant",
            "reason_code": "requirement_violated",
            "findings": "不得残留的临床结论",
            "customer_evidence": [{"source_document_id": "PRIVATE-005"}],
        },
        raw_facts={"raw_private_text": "PRIVATE-BASIC-TIMELINESS"},
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["reason_code"] == "model_invalid_output"
    assert "customer_display_facts" not in finalized
    assert "customer_evidence" not in finalized
    assert "PRIVATE-BASIC-TIMELINESS" not in repr(finalized)


def test_finalizer_converts_conflicting_020_execution_counts_to_technical_error() -> None:
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_executor_customer_display_facts,
    )

    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-020",
            "status": "non_compliant",
            "reason_code": "requirement_violated",
            "data_gap_details": {"reason_code": "unexpected_gap"},
        },
        raw_facts={
            "verification_kind": "consultation_execution_relation_check",
            "completed_opinion_episode_count": 1,
            "recommendation_count": 2,
            "specific_execution_count": 0,
            "generic_execution_count": 0,
            "missing_execution_count": 0,
            "relation_state": "execution_missing",
            "source_document_ids": ["CONSULT-1"],
            "recommendation_results": [
                {
                    "episode_index": 1,
                    "recommendation_index": 1,
                    "action_type": "test",
                    "execution_state": "missing",
                },
                {
                    "episode_index": 1,
                    "recommendation_index": 2,
                    "action_type": "medication",
                    "execution_state": "missing",
                },
            ],
        },
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["reason_code"] == "model_invalid_output"
    assert "data_gap_details" not in finalized


def test_finalizer_preserves_existing_technical_reason_for_invalid_executor_facts() -> None:
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_executor_customer_display_facts,
    )

    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-020",
            "status": "technical_error",
            "reason_code": "snapshot_mismatch",
        },
        raw_facts={"PRIVATE_UNKNOWN": "PRIVATE-CONSULTATION-TEXT"},
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["reason_code"] == "snapshot_mismatch"


def test_exam_lab_finalizer_strips_internal_refs_from_valid_facts() -> None:
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_executor_customer_display_facts,
        finalizer_owns_executor_customer_display_facts,
    )

    assert finalizer_owns_executor_customer_display_facts("LX0609-012") is True
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-012",
            "status": "non_compliant",
            "reason_code": "requirement_violated",
        },
        raw_facts={
            "failure_kind": "exam_lab_requirement_not_documented",
            "subject": "ct_mri",
            "requirement": "positive_result_analysis_within_24h",
            "event_phase": "report",
            "checked_sources": ["exam_lab_report", "course_record"],
            "source_document_ids": ["REPORT-1"],
            "source_document_refs": [
                {"source_type": "exam_item_report", "source_document_id": "REPORT-1"}
            ],
        },
    )

    assert handled is True
    assert finalized["status"] == "non_compliant"
    assert finalized["customer_display_facts"] == {
        "failure_kind": "exam_lab_requirement_not_documented",
        "subject": "ct_mri",
        "requirement": "positive_result_analysis_within_24h",
        "event_phase": "report",
        "checked_sources": ["exam_lab_report", "course_record"],
    }


def test_exam_lab_finalizer_fails_closed_for_invalid_facts_only() -> None:
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_executor_customer_display_facts,
    )

    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-015",
            "status": "non_compliant",
            "reason_code": "requirement_violated",
            "findings": "不得保留",
        },
        raw_facts={
            "failure_kind": "exam_lab_requirement_not_documented",
            "subject": "culture_susceptibility",
            "requirement": "positive_result_analysis_within_24h",
            "event_phase": "report",
            "checked_sources": ["exam_lab_report", "course_record"],
            "unexpected_private_field": "不得透传",
        },
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["reason_code"] == "model_invalid_output"
    assert "findings" not in finalized


def test_discharge_finalizer_owns_facts_and_strips_private_document_refs() -> None:
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_executor_customer_display_facts,
        finalizer_owns_executor_customer_display_facts,
    )

    assert finalizer_owns_executor_customer_display_facts("LX0609-067") is True
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-067",
            "status": "compliant",
            "reason_code": "requirement_satisfied",
            "findings": "PRIVATE_FINDING",
        },
        raw_facts={
            "verification_kind": "predischarge_course_presence_check",
            "discharge_date": "2026-07-03",
            "checked_dates": ["2026-07-02", "2026-07-03"],
            "course_present": True,
            "source_document_refs": [
                {
                    "source_type": "daily_course_record",
                    "source_document_id": "PRIVATE-067",
                }
            ],
        },
    )

    assert handled is True
    assert (finalized["status"], finalized["reason_code"]) == (
        "compliant",
        "requirement_satisfied",
    )
    assert finalized["customer_display_facts"] == {
        "verification_kind": "predischarge_course_presence_check",
        "discharge_date": "2026-07-03",
        "checked_dates": ["2026-07-02", "2026-07-03"],
        "course_present": True,
    }


@pytest.mark.parametrize(
    ("rule_id", "raw_facts"),
    (
        ("LX0609-009", {"raw_private_text": "PRIVATE-009"}),
        ("LX0609-017", {
            "failure_kind": "copy_similarity_threshold_exceeded",
        }),
        ("LX0609-018", {"raw_private_text": "PRIVATE-018"}),
    ),
)
def test_course_quality_finalizer_rejects_invalid_typed_facts_as_technical_error(
    rule_id: str,
    raw_facts: dict,
) -> None:
    """非法查房病程 facts 仅可在 Typed Finalizer 边界降级为技术错误。"""

    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_executor_customer_display_facts,
    )

    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": rule_id,
            "status": "non_compliant",
            "reason_code": "requirement_violated",
            "findings": "不得保留",
            "customer_evidence": [{"source_document_id": "PRIVATE-DOCUMENT"}],
        },
        raw_facts=raw_facts,
    )

    assert handled is True
    assert (finalized["status"], finalized["reason_code"]) == (
        "technical_error",
        "model_invalid_output",
    )
    assert "customer_display_facts" not in finalized
    assert "customer_evidence" not in finalized
    assert "findings" not in finalized
    assert "PRIVATE" not in repr(finalized)


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"customer_display_facts": {"failure_kind": ""}},
        {"criterion_results": [{"status": "", "details": {}}]},
        {"customer_display_facts": {"failure_kind": "document_missing"}},
        {"customer_display_facts": {"requirement_met": False}},
        {"customer_display_facts": {"missing_count": 0}},
        {"criterion_results": [{"criterion_id": "presence", "status": "failed"}]},
        (
            {
                "evidence_items": [
                    {
                        "quote": "未见术前小结",
                        "source_document_id": "document-1",
                    }
                ]
            }
        ),
    ],
)
def test_finalizer_never_rewrites_the_executor_non_compliant_status(extra: dict):
    result = _finalize(
        {
            "rule_id": "LX0609-029",
            "status": "non_compliant",
            "result_status": "non_compliant",
            "reason_code": "requirement_violated",
            "is_compliant": False,
            **extra,
        }
    )

    assert result["status"] == "non_compliant"
    assert result["result_status"] == "non_compliant"
    assert result["is_compliant"] is False
    assert result["reason_code"] == "requirement_violated"


@pytest.mark.parametrize("status", CANONICAL_RESULT_STATUSES)
def test_finalizer_accepts_every_canonical_status_and_preserves_non_defect_reason(
    status: str,
):
    result = _finalize(
        {
            "rule_id": "LX0609-001",
            "status": status,
            "result_status": "stale-value",
            "reason_code": "original_reason",
            "is_compliant": "stale-value",
            "customer_display_facts": (
                {"failure_kind": "late"} if status == "non_compliant" else {}
            ),
        }
    )

    assert result["status"] == status
    assert result["result_status"] == status
    assert result["reason_code"] == "original_reason"
    assert result["is_compliant"] is (
        True
        if status == "compliant"
        else False
        if status == "non_compliant"
        else None
    )


def test_finalizer_rejects_missing_identity_and_unknown_status():
    with pytest.raises(ValueError, match="rule_id"):
        _finalize({"status": "compliant"})

    with pytest.raises(ValueError, match="status"):
        _finalize({"rule_id": "LX0609-001", "status": "future_status"})


def test_location_without_excerpt_does_not_change_the_executor_status():
    result = _finalize(
        {
            "rule_id": "LX0609-029",
            "status": "non_compliant",
            "reason_code": "requirement_violated",
            "customer_evidence": [
                {"source_document_id": "document-1", "source_type": "preoperative_summary"}
            ],
            "evidence_items": [{"source_document_id": "document-1", "quote": ""}],
        }
    )

    assert result["status"] == "non_compliant"
    assert result["reason_code"] == "requirement_violated"


def test_finalizer_is_idempotent_and_does_not_mutate_nested_input():
    source = {
        "rule_id": "LX0609-029",
        "status": "non_compliant",
        "result_status": "non_compliant",
        "reason_code": "requirement_violated",
        "is_compliant": False,
        "customer_display_facts": {},
        "criterion_results": [],
        "evidence_items": [{"quote": "", "metadata": {"rank": 1}}],
    }
    before = deepcopy(source)

    first = _finalize(source)
    second = _finalize(first)

    assert source == before
    assert first == second
    assert first is not source
    assert first["evidence_items"] is not source["evidence_items"]
    assert first["evidence_items"][0] is not source["evidence_items"][0]


def test_rule_040_does_not_replace_the_executor_decision_with_a_generic_result():
    result = _finalize(
        {
            "rule_id": "LX0609-040",
            "status": "non_compliant",
            "reason_code": "requirement_violated",
        }
    )

    assert result["status"] == "non_compliant"
    assert result["result_status"] == "non_compliant"
    assert result["reason_code"] == "requirement_violated"
    assert "findings" not in result
    assert "evidence" not in result


def test_data_gap_always_has_customer_readable_missing_data_contract():
    result = _finalize(
        {
            "rule_id": "LX0609-011",
            "status": "data_gap",
            "reason_code": "required_field_missing",
        }
    )

    assert result["status"] == "data_gap"
    assert result["reason_code"] == "required_field_missing"
    assert result["missing_sources"] == []
    assert result["missing_fields"] == ["完成判定所需的关键字段"]
    assert result["customer_message"] == (
        "已读取到相关资料，但缺少完成判定所需的关键字段，暂时无法完成本项质控。"
    )
    assert result["data_gap_details"] == {
        "reason_code": "required_field_missing",
        "reason_label": "关键字段缺失",
        "missing_sources": [],
        "missing_fields": ["完成判定所需的关键字段"],
        "customer_message": result["customer_message"],
    }


def test_rule_009_candidate_scope_gap_does_not_claim_missing_source() -> None:
    result = _finalize(
        {
            "rule_id": "LX0609-009",
            "status": "data_gap",
            "reason_code": "candidate_scope_incomplete",
        }
    )

    assert result["missing_sources"] == []
    assert result["missing_fields"] == []
    assert result["data_gap_details"]["reason_label"] == "自动核对范围超限"
    assert "现有资料无需补充" in result["customer_message"]
    assert "后续资料" not in result["customer_message"]

    other_rule = _finalize(
        {
            "rule_id": "LX0609-054",
            "status": "data_gap",
            "reason_code": "candidate_scope_incomplete",
        }
    )
    assert other_rule["missing_sources"] == ["完成本项质控所需资料"]
    assert other_rule["data_gap_details"]["reason_label"] == "现有资料不足"


def test_rule_048_names_the_missing_anesthesia_record_instead_of_generic_materials() -> None:
    result = _finalize(
        {
            "rule_id": "LX0609-048",
            "status": "data_gap",
            "reason_code": "transfusion_comparison_fields_unavailable",
            "customer_display_facts": {
                "failure_kind": "transfusion_comparison_material_missing",
                "missing_sources": ["anesthesia_record"],
            },
        }
    )

    assert result["missing_sources"] == ["麻醉记录单"]
    assert result["missing_fields"] == []
    assert result["data_gap_details"]["reason_label"] == "术中输血比对资料不完整"
    assert "麻醉记录单" in result["customer_message"]
    assert "完成本项质控所需资料" not in result["missing_sources"]


def test_rule_031_signature_association_gap_names_the_unavailable_signature_fields() -> None:
    result = _finalize(
        {
            "rule_id": "LX0609-031",
            "status": "data_gap",
            "reason_code": "association_failed",
        }
    )

    assert result["missing_sources"] == []
    assert result["missing_fields"] == ["主刀医师签名", "手术事件与手术记录的对应关系"]
    assert result["data_gap_details"]["reason_label"] == "手术签名信息暂无法核对"
    assert "主刀医师签名" in result["customer_message"]
    assert "提交人" not in result["customer_message"]


@pytest.mark.parametrize(
    ("rule_id", "order_count", "transfer_in_count", "transfer_out_count"),
    (
        ("LX0609-072", 3, 2, 1),
        ("LX0609-073", 2, 1, 0),
    ),
)
def test_transfer_event_association_gap_names_event_linkage_only(
    rule_id: str,
    order_count: int,
    transfer_in_count: int,
    transfer_out_count: int,
) -> None:
    result = _finalize(
        {
            "rule_id": rule_id,
            "status": "data_gap",
            "reason_code": "association_failed",
            "customer_display_facts": {
                "failure_kind": "transfer_event_association_gap",
                "transfer_order_count": order_count,
                "transfer_in_count": transfer_in_count,
                "transfer_out_count": transfer_out_count,
            },
        }
    )

    assert result["missing_sources"] == []
    assert result["missing_fields"] == [
        "转科医嘱与转入/转出记录的事件关联"
    ]
    assert result["data_gap_details"]["reason_label"] == "转科事件与文书关联信息不足"
    assert result["customer_message"] == (
        f"已识别{order_count}条转科相关医嘱、"
        f"{transfer_in_count}份转入/{transfer_out_count}份转出记录，"
        "缺少可将各文书与具体转科事件对应的关联信息，暂无法逐次核对。"
    )
    assert "文书缺失" not in result["customer_message"]
    assert "缺少时间" not in result["customer_message"]


def test_rule_028_required_field_gap_names_the_actual_prophylaxis_inputs() -> None:
    result = _finalize(
        {
            "rule_id": "LX0609-028",
            "status": "data_gap",
            "reason_code": "required_field_missing",
        }
    )

    assert result["missing_sources"] == []
    assert result["missing_fields"] == [
        "手术切口等级",
        "预防性用药属性",
        "抗菌药物实际给药时间",
        "抗菌药物实际停用时间",
    ]
    assert result["data_gap_details"]["reason_label"] == "预防性抗菌药物时长字段不完整"
    assert "实际停用时间" in result["customer_message"]
    assert "医嘱更新时间不能替代实际停用时间" in result["customer_message"]


@pytest.mark.parametrize(
    ("reason_code", "reason_label", "expected_phrase"),
    [
        ("source_unavailable", "数据源未接入", "尚未接入"),
        ("source_empty", "未读取到相关资料", "未读取到"),
        ("source_truncated", "输入资料不完整", "超过本次读取范围"),
        ("source_readiness_unproven", "数据同步状态未确认", "同步状态"),
        ("association_failed", "资料关联失败", "无法准确关联"),
        ("linkage_unresolved", "关联资料不足", "对应关系"),
        ("authoritative_time_missing", "权威时间缺失", "权威时间"),
        ("target_report_missing", "目标报告缺失", "对应的正式报告"),
        ("authoritative_report_time_missing", "报告时间缺失", "权威报告时间"),
        ("authoritative_time_conflict", "权威时间冲突", "存在冲突"),
        ("evaluation_window_not_mature", "评价窗口尚未结束", "尚未满"),
        ("applicability_source_gap", "适用性资料缺失", "是否适用"),
        ("unexpected_gap", "现有资料不足", "现有资料不足"),
    ],
)
def test_every_data_gap_reason_gets_a_controlled_customer_explanation(
    reason_code: str,
    reason_label: str,
    expected_phrase: str,
):
    result = _finalize(
        {
            "rule_id": "LX0609-054",
            "status": "data_gap",
            "reason_code": reason_code,
        }
    )

    assert result["data_gap_details"]["reason_label"] == reason_label
    assert expected_phrase in result["customer_message"]
    assert isinstance(result["missing_sources"], list)
    assert isinstance(result["missing_fields"], list)


def test_069_source_unavailable_is_labeled_as_institution_source_gap() -> None:
    result = _finalize(
        {
            "rule_id": "LX0609-069",
            "status": "data_gap",
            "reason_code": "source_unavailable",
        }
    )

    details = result["data_gap_details"]
    assert details["reason_label"] == "机构数据源未接入"
    assert details["missing_sources"] == ["会诊申请时间"]
    assert "当前机构" in details["customer_message"]


def test_data_gap_completion_preserves_more_precise_existing_details():
    result = _finalize(
        {
            "rule_id": "LX0609-052",
            "status": "data_gap",
            "reason_code": "required_field_missing",
            "missing_sources": ["检验结果明细"],
            "missing_fields": ["危急值标志"],
            "customer_message": "缺少检验结果明细中的危急值标志，暂时无法核对。",
            "data_gap_details": {"availability": "unavailable"},
        }
    )

    assert result["missing_sources"] == ["检验结果明细"]
    assert result["missing_fields"] == ["危急值标志"]
    assert result["customer_message"] == "缺少检验结果明细中的危急值标志，暂时无法核对。"
    assert result["data_gap_details"]["availability"] == "unavailable"
    assert result["data_gap_details"]["reason_label"] == "关键字段缺失"


def test_data_gap_completion_does_not_overwrite_rule_specific_detail_fields():
    existing_details = {
        "reason_code": "authoritative_time_missing",
        "reason_label": "病例评价时间待确认",
        "missing_sources": [],
        "missing_fields": ["有效出院时间"],
        "customer_message": "请确认本次住院的有效出院时间。",
    }
    result = _finalize(
        {
            "rule_id": "LX0609-012",
            "status": "data_gap",
            "reason_code": "authoritative_time_missing",
            "data_gap_details": existing_details,
        }
    )

    assert result["data_gap_details"] == existing_details
    assert result["missing_sources"] == existing_details["missing_sources"]
    assert result["missing_fields"] == existing_details["missing_fields"]
    assert result["customer_message"] == existing_details["customer_message"]


def test_data_gap_rejects_conflicting_top_level_and_detail_explanations():
    with pytest.raises(ValueError, match="conflicting data gap explanation field"):
        _finalize(
            {
                "rule_id": "LX0609-012",
                "status": "data_gap",
                "reason_code": "authoritative_time_missing",
                "customer_message": "顶层解释",
                "data_gap_details": {
                    "reason_code": "authoritative_time_missing",
                    "customer_message": "嵌套解释",
                },
            }
        )


def test_data_gap_uses_controlled_missing_source_from_customer_facts():
    result = _finalize(
        {
            "rule_id": "LX0609-052",
            "status": "data_gap",
            "reason_code": "required_field_missing",
            "customer_display_facts": {
                "failure_kind": "critical_value_result_detail_missing",
                "missing_source": "labtest_item_report",
            },
        }
    )

    assert result["missing_sources"] == ["检验结果明细"]
    assert result["missing_fields"] == ["完成判定所需的关键字段"]
