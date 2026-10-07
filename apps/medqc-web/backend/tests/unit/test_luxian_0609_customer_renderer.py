from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.customer_renderer import (
    CUSTOMER_RESULT_KEYS,
    compliant_customer_finding,
    customer_finding_from_controlled_facts,
    data_gap_customer_message,
    render_luxian_0609_customer_result,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    CriterionResult,
    CriterionStatus,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import (
    CustomerFinalState,
    reduce_luxian_0609_rule_decision,
)
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts


SNAPSHOT_HASH = "a" * 64
FACT_REF = "b" * 64


@pytest.mark.parametrize(
    ("rule_id", "reason_code", "missing_sources", "expected"),
    [
        (
            "LX0609-05-01-02",
            "required_field_missing",
            [],
            "已读取到相关资料，但缺少完成判定所需的关键字段，暂时无法完成本项质控。",
        ),
        (
            "LX0609-05-01-02",
            "source_unavailable",
            [],
            "本项质控所需的数据源尚未接入或本次未读取到，暂时无法完成判定。",
        ),
        (
            "LX0609-05-01-02",
            "source_empty",
            [],
            "本次未读取到完成本项质控所需的相关资料，暂时无法完成判定。",
        ),
        (
            "LX0609-05-01-02",
            "source_truncated",
            [],
            "相关资料数量超过本次读取范围，当前资料不完整，暂时无法完成本项质控。",
        ),
        (
            "LX0609-05-01-02",
            "source_readiness_unproven",
            [],
            "本项质控所需资料的同步状态尚未确认，暂时无法判断资料是否完整。",
        ),
        (
            "LX0609-05-01-02",
            "association_failed",
            [],
            "已读取到相关资料，但暂时无法准确关联对应事件与文书，无法完成本项质控。",
        ),
        (
            "LX0609-05-01-02",
            "linkage_unresolved",
            [],
            "现有资料不足以确认事件与文书的对应关系，暂时无法完成本项质控。",
        ),
        (
            "LX0609-05-01-02",
            "authoritative_time_missing",
            [],
            "缺少用于计算质控时限的权威时间，暂时无法完成本项质控。",
        ),
        (
            "LX0609-05-01-02",
            "target_report_missing",
            [],
            "已读取到目标检查检验医嘱，但未读取到对应的正式报告，暂时无法核对24小时要求。",
        ),
        (
            "LX0609-05-01-02",
            "authoritative_report_time_missing",
            [],
            "已读取到目标检查检验事件，但缺少权威报告时间，暂时无法核对24小时要求。",
        ),
        (
            "LX0609-05-01-02",
            "authoritative_time_conflict",
            [],
            "报告时间与本次住院的评价截止时间存在冲突，暂时无法完成本项质控。",
        ),
        (
            "LX0609-05-01-02",
            "evaluation_window_not_mature",
            [],
            "截至本次评价日期尚未满规则要求的观察时限，本次暂不判定缺陷。",
        ),
        (
            "LX0609-05-01-02",
            "applicability_source_gap",
            [],
            "缺少判断本质控点是否适用的关键资料，暂时无法继续判定。",
        ),
        (
            "LX0609-04-02-07",
            "source_unavailable",
            [],
            "当前机构会诊接口未提供会诊申请时间，无法核对会诊记录是否在申请发出后24小时内完成。",
        ),
        (
            "LX0609-02-01-05",
            "candidate_scope_incomplete",
            [],
            "本次病情变化候选超出单次自动核对的安全容量，暂未形成确定结论；现有资料无需补充，请重新执行本项质控，如仍出现请联系系统管理员。",
        ),
        (
            "LX0609-05-01-01",
            "required_field_missing",
            [],
            "已读取手术及用药资料，但尚缺切口等级、预防性用药属性或抗菌药物实际给药/停用时间中的至少一项；医嘱更新时间不能替代实际停用时间。",
        ),
        (
            "LX0609-04-02-05",
            "association_failed",
            [],
            "已读取手术主表和手术记录，但尚未取得可与每次手术对应的主刀医师签名，暂时无法完成签名资格核对。",
        ),
        (
            "LX0609-07-04-01",
            "transfusion_comparison_fields_unavailable",
            [],
            "已确认存在术中输血，但三份文书的比对资料不完整，暂时无法完成一致性核对。",
        ),
        (
            "LX0609-07-04-01",
            "transfusion_comparison_fields_unavailable",
            ["麻醉记录单"],
            "已确认存在术中输血，但缺少麻醉记录单，暂时无法完成手术记录、麻醉记录单和术后首次病程记录的一致性核对。",
        ),
        (
            "LX0609-05-01-02",
            "unexpected_gap",
            [],
            "现有资料不足，暂时无法完成本项质控；请补充或同步相关资料后重新评估。",
        ),
    ],
)
def test_data_gap_customer_message_freezes_finalizer_default_copy(
    rule_id: str,
    reason_code: str,
    missing_sources: list[str],
    expected: str,
) -> None:
    assert (
        data_gap_customer_message(
            rule_id=rule_id,
            reason_code=reason_code,
            missing_sources=missing_sources,
        )
        == expected
    )


def test_050_customer_finding_explains_local_diagnosis_scope_uncertainty() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-03-02-01",
        facts={
            "verification_kind": "uncertain_diagnosis_scope_unverified",
            "admission_time": "2026-06-01 08:00:00",
            "uncertain_record_times": ["2026-06-09 09:00:00"],
            "discussion_count": 0,
            "raw_text": "PRIVATE_MEDICAL_BODY",
        },
    )

    assert finding == (
        "入院时间为 2026-06-01 08:00:00；入院满 7 天后的病程于 "
        "2026-06-09 09:00:00 出现局部原因待查或性质待定表述。"
        "现有资料无法确认这是否表示本次住院整体诊断仍不明确，"
        "不能据此认定缺少疑难病例讨论，请人工核对整体诊断状态。"
    )
    assert "PRIVATE_MEDICAL_BODY" not in finding


def test_050_scope_uncertainty_renders_without_reclassifying_the_reason() -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-03-02-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.CONFLICT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="diagnosis_scope_uncertain",
            fact_refs=(FACT_REF,),
            evaluator_version="extended-document-v2",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "uncertain"
    assert result["reason_code"] == "diagnosis_scope_uncertain"
    assert result["is_compliant"] is None


def test_054_order_without_confirmed_action_uses_neutral_not_applicable_copy() -> None:
    """普通抗菌药医嘱不再触发054时，文案不得误称“没有医嘱”。"""

    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-05-01-02",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="trigger_absent_complete",
            fact_refs=(FACT_REF,),
            evaluator_version="extended-document-v2",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "not_applicable"
    assert result["reason_code"] == "trigger_absent_complete"
    assert result["findings"] == "本次未发现需要核对理由的抗菌药物使用或调整动作"
    assert "未发现抗菌药物医嘱" not in result["findings"]


def test_058_customer_finding_distinguishes_expert_support_after_special_use() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-05-01-06",
        facts={
            "verification_kind": "special_antimicrobial_expert_support_check",
            "special_antimicrobials": ["美罗培南"],
            "expert_support_present": True,
            "first_antimicrobial_time": "2026-06-01 10:00:00",
            "expert_support_time": "2026-06-01 11:00:00",
            "support_before_use": False,
            "unmatched_special_antimicrobials": ["美罗培南"],
            "association_ambiguous": False,
        },
    )

    assert finding == (
        "已确认特殊级抗菌药物 美罗培南 的计划开始/启用时间为 "
        "2026-06-01 10:00:00，但专家支持记录时间 2026-06-01 11:00:00 "
        "晚于该时间，不满足计划启用前支持要求。"
    )


def test_058_customer_finding_confirms_expert_support_before_or_at_special_use() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-05-01-06",
        facts={
            "verification_kind": "special_antimicrobial_expert_support_check",
            "special_antimicrobials": ["美罗培南"],
            "expert_support_present": True,
            "first_antimicrobial_time": "2026-06-01 10:00:00",
            "expert_support_time": "2026-06-01 10:00:00",
            "support_before_use": True,
            "unmatched_special_antimicrobials": [],
            "association_ambiguous": False,
        },
    )

    assert finding == (
        "已确认特殊级抗菌药物 美罗培南 计划开始/启用时间为 "
        "2026-06-01 10:00:00，并在该时间前或同刻找到专家支持记录（2026-06-01 10:00:00）。"
    )


def test_058_customer_finding_does_not_call_partial_support_late() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-05-01-06",
        facts={
            "verification_kind": "special_antimicrobial_expert_support_check",
            "special_antimicrobials": ["美罗培南", "万古霉素"],
            "expert_support_present": True,
            "first_antimicrobial_time": "2026-06-01 10:00:00",
            "expert_support_time": "2026-06-01 09:00:00",
            "support_before_use": False,
            "unmatched_special_antimicrobials": ["万古霉素"],
            "association_ambiguous": False,
        },
    )

    assert finding == "已核对特殊级抗菌药物 美罗培南、万古霉素；其中 万古霉素 未找到可关联的计划启用前专家支持记录。"


def test_054_customer_finding_identifies_the_unmatched_antimicrobial() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-05-01-02",
        facts={
            "verification_kind": "antimicrobial_reason_documentation_check",
            "antimicrobials": ["美罗培南", "万古霉素"],
            "reason_documented": False,
            "unmatched_antimicrobials": ["万古霉素"],
            "association_ambiguous": False,
        },
    )

    assert finding == "已核对抗菌药物 美罗培南、万古霉素；其中 万古霉素 未找到明确的使用或调整动作及理由。"


@pytest.mark.parametrize(
    ("rule_id", "facts", "expected"),
    (
        ("LX0609-05-01-02", {
            "verification_kind": "antimicrobial_reason_documentation_check",
            "antimicrobials": ["美罗培南", "万古霉素"],
            "association_ambiguous": True,
        }, "已核对抗菌药物 美罗培南、万古霉素；现有病程未明确关联到具体药物使用或调整事件，暂无法逐项核对理由。"),
        ("LX0609-05-01-03", {
            "verification_kind": "antimicrobial_effect_evaluation_check",
            "antimicrobials": ["美罗培南", "万古霉素"],
            "association_ambiguous": True,
        }, "已核对抗菌药物 美罗培南、万古霉素；现有效果评价未明确关联到具体药物计划开始/启用事件，暂无法逐项核对 48～72 小时评价。"),
        ("LX0609-05-01-06", {
            "verification_kind": "special_antimicrobial_expert_support_check",
            "special_antimicrobials": ["美罗培南", "万古霉素"],
            "association_ambiguous": True,
        }, "已核对特殊级抗菌药物 美罗培南、万古霉素；现有专家支持记录未明确关联到具体药物计划开始/启用事件，暂无法逐项核对计划启用前支持。"),
    ),
)
def test_antimicrobial_customer_finding_explains_ambiguous_association(
    rule_id: str, facts: dict[str, object], expected: str
) -> None:
    assert customer_finding_from_controlled_facts(rule_id=rule_id, facts=facts) == expected


def test_069_customer_finding_identifies_each_consultation_and_the_late_one() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-04-02-07",
        facts={
            "verification_kind": "consultation_timeliness_check",
            "threshold_hours": 24,
            "actual_interval_hours": [2.0, 27.0],
            "request_times": ["2026-08-20 08:00:00+08:00", "2026-08-20 09:00:00+08:00"],
            "record_times": ["2026-08-20 10:00:00+08:00", "2026-08-21 12:00:00+08:00"],
            "event_results": [
                {
                    "sequence": 1,
                    "request_time": "2026-08-20 08:00:00+08:00",
                    "completion_time": "2026-08-20 10:00:00+08:00",
                    "interval_seconds": 7200,
                    "outcome": "within_threshold",
                },
                {
                    "sequence": 2,
                    "request_time": "2026-08-20 09:00:00+08:00",
                    "completion_time": "2026-08-21 12:00:00+08:00",
                    "interval_seconds": 97200,
                    "outcome": "threshold_exceeded",
                },
            ],
        },
    )

    assert "第1次会诊" in finding
    assert "第2次会诊" in finding
    assert "超过24小时" in finding


def test_001_blank_or_placeholder_admission_record_renders_specific_customer_copy() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-01-01-01",
        facts={
            "failure_kind": "timeliness_requirement_not_met",
            "target_document": "admission_record",
            "source_label": "入院记录",
            "timeliness_state": "missing",
            "threshold_hours": 24,
            "document_content_state": "blank_or_placeholder",
        },
    )

    assert finding == "已检到入院记录，但未发现可核验的有效文书内容。"


def test_010_association_facts_render_exact_customer_counts() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-06-01-02",
        facts={
            "failure_kind": "exam_order_exam_association_failed",
            "subject": "ct_mri",
            "checked_sources": [
                "exam_lab_order",
                "exam_master",
                "exam_lab_report",
                "course_record",
            ],
            "requirement": "order_course_report_consistency",
            "requirement_met": False,
            "order_count": 6,
            "exam_master_count": 1,
            "uniquely_linked_order_count": 1,
            "unmatched_or_ambiguous_order_count": 5,
            "association_issue_kind": "order_without_exam_master",
        },
    )

    assert finding == (
        "已核对6条CT/MRI医嘱与1条检查主记录，其中5条医嘱未找到唯一对应检查主记录，"
        "暂无法确认属于同一次诊疗事件。"
    )


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        (
            {
                "failure_kind": "course_record_interval_over_72h",
                "interval_start_source": "inpat_registration",
                "interval_end_source": "daily_course_record",
                "interval_start_time": "2026-08-14 08:00:00",
                "interval_end_time": "2026-08-17 10:02:00",
                "interval_seconds": 266520,
                "overdue_seconds": 7320,
                "threshold_hours": 72,
            },
            "权威入院时间（2026-08-14 08:00:00）至首次查房（2026-08-17 10:02:00）间隔"
            "74小时2分，超过72小时要求2小时2分。",
        ),
        (
            {
                "failure_kind": "course_record_interval_over_72h",
                "interval_start_source": "senior_course_record",
                "interval_end_source": "evaluation_context.horizon",
                "interval_start_time": "2026-08-14 09:30:00",
                "interval_end_date": "2026-08-18",
                "interval_end_precision": "date",
                "threshold_hours": 72,
            },
            "最后一次查房（2026-08-14 09:30:00）至评价截止日期（2026-08-18）"
            "已确认超过72小时要求。",
        ),
        (
            {
                "failure_kind": "course_record_interval_over_72h",
                "interval_start_source": "senior_course_record",
                "interval_end_source": "evaluation_context.horizon",
                "interval_start_time": "2026-08-14 09:30:00",
                "interval_end_time": "2026-08-17 10:00:00",
                "interval_seconds": 261000,
                "overdue_seconds": 1800,
                "threshold_hours": 72,
            },
            "最后一次查房（2026-08-14 09:30:00）至评价截止时间（2026-08-17 10:00:00）间隔"
            "72小时30分，超过72小时要求30分。",
        ),
        (
            {
                "failure_kind": "course_record_interval_over_72h",
                "interval_start_source": "inpat_registration",
                "interval_end_source": "evaluation_context.horizon",
                "interval_start_time": "2026-08-14 08:00:00",
                "interval_end_date": "2026-08-18",
                "interval_end_precision": "date",
                "threshold_hours": 72,
            },
            "权威入院时间（2026-08-14 08:00:00）至评价截止日期（2026-08-18）"
            "已确认超过72小时要求；期间未见有效查房。",
        ),
    ],
)
def test_007_boundary_overdue_renders_controlled_boundary_copy(facts, expected) -> None:
    assert customer_finding_from_controlled_facts(rule_id="LX0609-02-01-03", facts=facts) == expected


def test_007_zero_rounds_exact_boundaries_render_without_fabricating_round_number() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-02-01-03",
        facts={
            "failure_kind": "course_record_interval_over_72h",
            "interval_start_source": "inpat_registration",
            "interval_end_source": "evaluation_context.horizon",
            "interval_start_time": "2026-08-14 08:00:00",
            "interval_end_time": "2026-08-17 10:00:00",
            "interval_seconds": 266400,
            "overdue_seconds": 7200,
            "threshold_hours": 72,
        },
    )

    assert finding == (
        "权威入院时间（2026-08-14 08:00:00）至评价截止时间（2026-08-17 10:00:00）间隔"
        "74小时，超过72小时要求2小时；期间未见有效查房。"
    )
    assert "第0次" not in finding
    assert "第1次" not in finding


@pytest.mark.parametrize(
    ("failure_kind", "expected"),
    (
        ("exam_order_reason_missing", "检查前病程未记录检查原因"),
        ("exam_course_without_order", "未找到对应检查医嘱"),
        ("exam_order_course_missing", "未找到对应病程记录"),
        ("exam_report_missing", "未找到对应检查报告"),
    ),
)
def test_010_other_deterministic_failures_render_specific_customer_copy(
    failure_kind: str,
    expected: str,
) -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-06-01-02",
        facts={"failure_kind": failure_kind},
    )

    assert expected in finding


def test_034_missing_anesthesia_consent_renders_specific_customer_copy() -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-11-02-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="required_document_missing",
            fact_refs=(FACT_REF,),
            evaluator_version="customer-copy-audit-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"] == "已实施麻醉，但未找到对应的麻醉知情同意书"
    assert "专用麻醉知情同意书" in result["evidence"]
    assert "麻醉风险告知" in result["suggestion"]


def test_068_compliant_message_covers_regular_and_automatic_discharge_paths() -> None:
    finding = compliant_customer_finding(
        rule_id="LX0609-08-02-02",
        criterion_results=(),
    )

    assert "上级医师同意出院意见" in finding
    assert "自动出院" in finding
    assert "书面签署" in finding


def test_024_compliant_message_does_not_claim_dissection_when_reason_was_documented() -> None:
    finding = compliant_customer_finding(
        rule_id="LX0609-04-02-03",
        criterion_results=(),
    )

    assert finding == "已核对目标恶性肿瘤手术记录，淋巴结处理情况或未处理原因已有记录。"


def test_017_semantic_template_pass_explains_high_similarity_without_threshold_claim() -> None:
    facts = {
        "failure_kind": "copy_semantic_review_passed",
        "copy_similarity": 0.7223,
        "copy_similarity_threshold": 0.7,
        "copy_document_sources": ["daily_course_record", "senior_course_record"],
        "copy_document_record_times": [
            "2026-06-01 09:00:00",
            "2026-06-02 10:30:00",
        ],
    }

    finding = compliant_customer_finding(
        rule_id="LX0609-12-01-02",
        safe_customer_display_facts=facts,
    )

    assert "超过候选阈值 70%" in finding
    assert "经语义复核确认属于模板或必要重复" in finding
    assert "未认定为实质复制" in finding
    assert "相似度达到或超过 70% 的重复记录" not in finding
    assert customer_finding_from_controlled_facts(
        rule_id="LX0609-12-01-02", facts=facts
    ) == finding


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        (
            {
                "failure_kind": "physician_handoff_association_failed",
                "change_event_count": 2,
                "handoff_record_count": 1,
                "handover_record_count": 1,
            },
            "检测到 2 次经治医师变更，已找到交班记录 1 份、接班记录 1 份",
        ),
        (
            {
                "failure_kind": "physician_change_time_missing",
                "change_event_count": 2,
                "missing_change_time_count": 1,
                "handoff_record_count": 1,
                "handover_record_count": 1,
            },
            "其中 1 次缺少权威变更时间",
        ),
    ],
)
def test_071_data_gap_facts_explain_existing_records_without_claiming_absence(
    facts,
    expected,
) -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-10-01-01",
        facts=facts,
    )

    assert expected in finding
    assert "未读取到" not in finding


def test_071_single_change_association_gap_does_not_claim_multiple_changes() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-10-01-01",
        facts={
            "failure_kind": "physician_handoff_association_failed",
            "change_event_count": 1,
            "handoff_record_count": 1,
            "handover_record_count": 1,
        },
    )

    assert "检测到 1 次经治医师变更" in finding
    assert "多次经治医师变更" not in finding


@pytest.mark.parametrize(
    ("reason_code", "expected_finding", "expected_evidence"),
    [
        (
            "association_failed",
            "检测到经治医师变更事件",
            "并非未读取到资料",
        ),
        (
            "authoritative_time_missing",
            "缺少权威时间",
            "至少一次变更缺少可用于计算的权威时间",
        ),
    ],
)
def test_071_reason_specific_data_gap_copy_is_factual(
    reason_code,
    expected_finding,
    expected_evidence,
) -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-10-01-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            fact_refs=(FACT_REF,),
            evaluator_version="native-extended-document-v1",
        )
    )

    rendered = render_luxian_0609_customer_result(decision=decision)

    assert expected_finding in rendered["findings"]
    assert expected_evidence in rendered["evidence"]
    assert "当前未读取到经治医师变更事件" not in rendered["evidence"]


def test_069_source_unavailable_copy_identifies_institution_source_gap() -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-04-02-07",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="source_unavailable",
            fact_refs=(FACT_REF,),
            evaluator_version="native-extended-document-v1",
        )
    )

    rendered = render_luxian_0609_customer_result(decision=decision)

    assert rendered["findings"] == "当前机构会诊申请时间数据源未接入"
    assert "会诊记录已读取" in rendered["evidence"]
    assert "资料关联失败" not in str(rendered)


@pytest.mark.parametrize("reason_code", ["association_failed", "authoritative_time_missing"])
def test_071_reason_copy_does_not_claim_that_handoff_records_exist(
    reason_code,
) -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-10-01-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            fact_refs=(FACT_REF,),
            evaluator_version="native-extended-document-v1",
        )
    )

    rendered = render_luxian_0609_customer_result(decision=decision)

    assert "已读取经治医师变更事件及交班、接班记录" not in rendered["evidence"]
    assert "已读取经治医师变更事件及交接班数据来源" in rendered["evidence"]


def test_074_association_gap_uses_diagnosis_specific_copy_not_missing_reason_copy() -> None:
    facts = {
        "failure_kind": "diagnosis_change_association_failed",
        "diagnosis_record_count": 3,
        "diagnosis_change_count": 2,
        "association_issue": "multiple_changes_unresolved",
    }
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-12-02-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="association_failed",
            fact_refs=(FACT_REF,),
            evaluator_version="native-extended-document-v1",
        )
    )

    rendered = render_luxian_0609_customer_result(
        decision=decision,
        safe_customer_display_facts=facts,
    )

    assert customer_finding_from_controlled_facts(
        rule_id="LX0609-12-02-01",
        facts=facts,
    ) == "已读取 3 条诊断记录，识别到 2 次诊断修改；多次修改无法与对应病程逐次唯一关联。"
    assert "已读取诊断记录" in rendered["evidence"]
    assert "诊断类别/序号缺失、重复或同刻冲突" in rendered["evidence"]
    assert "缺少诊断修正时间、对应修改理由或诊断依据" not in rendered["evidence"]


def test_074_untimed_reason_and_basis_copy_does_not_claim_missing_documentation() -> None:
    facts = {
        "failure_kind": "diagnosis_change_documentation_time_missing",
        "diagnosis_change_count": 1,
        "untimed_document_count": 1,
        "issue": "candidate_document_time_missing",
    }
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-12-02-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_missing",
            fact_refs=(FACT_REF,),
            evaluator_version="native-extended-document-v1",
        )
    )

    rendered = render_luxian_0609_customer_result(
        decision=decision,
        safe_customer_display_facts=facts,
    )

    assert customer_finding_from_controlled_facts(
        rule_id="LX0609-12-02-01",
        facts=facts,
    ) == "已读取 1 份含修改理由和诊断依据的病程，但缺少权威记录时间，无法确认是否在诊断修改后完成。"
    assert "已读取含修改理由和诊断依据的病程" in rendered["evidence"]
    assert "缺少权威记录时间" in rendered["evidence"]
    assert "缺少诊断修正时间、对应修改理由或诊断依据" not in rendered["evidence"]


def test_046_component_gap_uses_actual_transfused_component_copy_only_for_course_record() -> None:
    assert customer_finding_from_controlled_facts(
        rule_id="LX0609-07-02-02",
        facts={
            "failure_kind": "transfusion_course_record_incomplete",
            "record_count": 3,
            "incomplete_record_count": 2,
            "missing_fields": ["component"],
            "missing_field_record_counts": {"component": 2},
        },
    ) == (
        "共核对 3 份输血病程记录，其中 2 份存在缺项："
        "2 份未明确记录实际输注血液成分。"
    )
    assert customer_finding_from_controlled_facts(
        rule_id="LX0609-11-03-02",
        facts={
            "failure_kind": "transfusion_consent_incomplete",
            "missing_fields": ["component"],
        },
    ) == "输血知情同意书缺少：拟输血成分。"


@pytest.mark.parametrize(
    ("rule_id", "facts", "expected_finding"),
    [
        (
            "LX0609-04-01-01",
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "presurg_summary",
                "surgery_trigger_kind": "performed_surgery",
                "performed_surgery_confirmed": True,
            },
            "已确认本次实施手术，但未找到对应的术前小结。",
        ),
        (
            "LX0609-04-04-03",
            {
                "failure_kind": "anesthesia_record_missing",
                "performed_anesthesia_confirmed": True,
                "checked_sources": ["anesthesia_record"],
            },
            "已确认本次实施非局部麻醉，但未找到麻醉记录单。",
        ),
    ],
)
def test_customer_finding_uses_existing_controlled_facts_instead_of_generic_copy(
    rule_id: str,
    facts: dict[str, object],
    expected_finding: str,
) -> None:
    assert customer_finding_from_controlled_facts(
        rule_id=rule_id,
        facts=facts,
    ) == expected_finding


@pytest.mark.parametrize(
    ("rule_id", "expected_suggestion"),
    [
        (
            "LX0609-06-01-05",
            "请在检查报告出具后24小时内的病程中，记录阳性结果的临床意义、处置措施及后续计划。",
        ),
        (
            "LX0609-06-03-04",
            "请在培养报告出具后24小时内的病程中，记录阳性菌结果的临床意义、抗感染调整及后续计划。",
        ),
        (
            "LX0609-12-01-02",
            "请逐组核对结果列出的高相似病程，删除机械复制内容，并补充当日病情变化、检查结果和诊疗调整。",
        ),
        (
            "LX0609-04-02-04",
            "请在手术记录中补全结果列出的植入物名称、种类、规格/型号、材质及数量等缺项。",
        ),
        (
            "LX0609-04-01-01",
            "请为本次已实施手术补充术前小结，并记录术前诊断、手术指征、拟施手术及注意事项。",
        ),
        (
            "LX0609-04-04-03",
            "请补充本次麻醉记录单，并核对麻醉方式、用药、生命体征及术中事件记录。",
        ),
        (
            "LX0609-04-01-03",
            "请补充本次四级手术的术前多学科讨论记录，并记录参会科室、讨论意见及手术方案。",
        ),
        (
            "LX0609-05-01-06",
            "请补充使用特殊级抗菌药物前的专家查房或会诊意见，并记录用药依据。",
        ),
        (
            "LX0609-04-05-01",
            "请按每台手术分别补齐术后次日起连续3天的病程记录，并记录术者查房情况。",
        ),
        (
            "LX0609-12-02-01",
            "请对每次诊断修正或补充记录修改理由及诊断依据。",
        ),
    ],
)
def test_non_compliant_result_gives_rule_specific_action_instead_of_generic_advice(
    rule_id: str,
    expected_suggestion: str,
) -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="requirement_violated",
            fact_refs=(FACT_REF,),
            evaluator_version="native-rule-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert expected_suggestion in result["suggestion"]
    assert result["suggestion"] != "请按质控要求核对并完善相关记录。"


def _defect_decision(rule_id: str) -> RuleDecision:
    return reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="requirement_violated",
            fact_refs=(FACT_REF,),
            evaluator_version="native-rule-v1",
        )
    )


def test_withheld_consultation_rules_no_longer_deliver_rule_specific_template() -> None:
    """022 因会诊记录单来源缺失暂停，不再交付会诊记录单书写模板。"""

    withheld = render_luxian_0609_customer_result(
        decision=_defect_decision("LX0609-03-01-03")
    )

    assert "修改对象：会诊记录单" not in withheld["suggestion"]
    assert "病情判断—具体措施" not in withheld["suggestion"]
    assert withheld["suggestion"] == "请按质控要求核对并完善相关记录。"


def test_surviving_consultation_rule_keeps_structured_action() -> None:
    """023 保留为会诊族唯一可执行规则，模板中写明会诊意见来自正文语义提取。"""

    result = render_luxian_0609_customer_result(
        decision=_defect_decision("LX0609-03-01-04")
    )

    assert result["status"] == "non_compliant"
    assert "会诊意见按会诊执行记录正文语义提取" in result["findings"]
    assert "会诊意见按会诊执行记录正文语义提取" in result["evidence"]
    assert "照抄" not in result["findings"]
    assert "照抄" not in result["evidence"]
    assert "照抄" not in result["suggestion"]
    for section in ("修改对象：", "需要补充：", "推荐写法：", "注意事项："):
        assert section in result["suggestion"]
    assert "请在会诊意见执行记录中补充具体执行措施" in result["suggestion"]


DEFINED_RULE_IDS = tuple(
    contract.rule_id
    for contract in load_luxian_0609_rule_contracts()
    if contract.phase_status != "pending_definition"
)
CUSTOMER_EXECUTABLE_RULE_IDS = DEFINED_RULE_IDS


@pytest.mark.parametrize("rule_id", CUSTOMER_EXECUTABLE_RULE_IDS)
def test_every_customer_executable_rule_has_specific_action_instead_of_generic_advice(
    rule_id: str,
) -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="requirement_violated",
            fact_refs=(FACT_REF,),
            evaluator_version="customer-copy-audit-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "non_compliant", rule_id
    assert result["reason_code"] == "requirement_violated", rule_id
    assert result["suggestion"] != "请按质控要求核对并完善相关记录。", rule_id
    assert len(result["suggestion"]) >= 12, rule_id


NOT_APPLICABLE_CASES = (
    ("LX0609-09-01-01", "trigger_absent_complete"),
    ("LX0609-02-01-02", "evaluation_window_not_mature"),
    ("LX0609-02-01-03", "evaluation_window_not_mature"),
    ("LX0609-04-02-01", "performed_event_absent"),
    ("LX0609-02-01-03", "eligibility_not_met"),
    ("LX0609-02-01-04", "trigger_absent_complete"),
    ("LX0609-02-01-05", "trigger_absent_complete"),
    ("LX0609-06-01-02", "trigger_absent_complete"),
    ("LX0609-06-01-04", "trigger_absent_complete"),
    ("LX0609-06-01-05", "trigger_absent_complete"),
    ("LX0609-06-02-03", "trigger_absent_complete"),
    ("LX0609-06-03-03", "trigger_absent_complete"),
    ("LX0609-06-03-04", "trigger_absent_complete"),
    ("LX0609-06-02-02", "trigger_absent_complete"),
    ("LX0609-03-01-01", "trigger_absent_complete"),
    ("LX0609-03-01-02", "trigger_absent_complete"),
    ("LX0609-03-01-03", "trigger_absent_complete"),
    ("LX0609-04-02-04", "performed_event_absent"),
    ("LX0609-08-01-04", "trigger_absent_complete"),
    ("LX0609-04-01-01", "performed_event_absent"),
    ("LX0609-04-02-02", "performed_event_absent"),
    ("LX0609-04-02-02", "trigger_absent_complete"),
    ("LX0609-04-02-05", "performed_event_absent"),
    ("LX0609-04-03-01", "performed_event_absent"),
    ("LX0609-04-03-01", "trigger_absent_complete"),
    ("LX0609-11-01-01", "performed_event_absent"),
    ("LX0609-11-02-01", "performed_event_absent"),
    ("LX0609-11-02-02", "performed_event_absent"),
    ("LX0609-04-04-01", "performed_event_absent"),
    ("LX0609-04-04-01", "eligibility_not_met"),
    ("LX0609-04-04-02", "eligibility_not_met"),
    ("LX0609-04-04-02", "performed_event_absent"),
    ("LX0609-04-04-03", "performed_event_absent"),
    ("LX0609-04-04-03", "eligibility_not_met"),
    ("LX0609-04-01-02", "performed_event_absent"),
    ("LX0609-04-01-02", "eligibility_not_met"),
    ("LX0609-04-01-03", "performed_event_absent"),
    ("LX0609-04-01-03", "trigger_absent_complete"),
    ("LX0609-11-03-02", "eligibility_not_met"),
) + (
    ("LX0609-11-03-01", "trigger_absent_complete"),
    ("LX0609-11-03-02", "trigger_absent_complete"),
    ("LX0609-07-01-01", "trigger_absent_complete"),
    ("LX0609-07-01-02", "trigger_absent_complete"),
    ("LX0609-07-02-01", "trigger_absent_complete"),
    ("LX0609-07-02-02", "trigger_absent_complete"),
    ("LX0609-07-03-01", "trigger_absent_complete"),
    ("LX0609-07-04-01", "trigger_absent_complete"),
    ("LX0609-09-02-01", "trigger_absent_complete"),
    ("LX0609-05-01-06", "trigger_absent_complete"),
    ("LX0609-04-02-06", "trigger_absent_complete"),
    ("LX0609-08-01-03", "trigger_absent_complete"),
    ("LX0609-07-01-03", "trigger_absent_complete"),
    ("LX0609-10-02-01", "trigger_absent_complete"),
    ("LX0609-10-02-02", "trigger_absent_complete"),
)


@pytest.mark.parametrize(
    ("reason_code", "expected_finding", "expected_evidence", "expected_suggestion"),
    [
        (
            "rescue_record_missing_after_trigger",
            "已发现有效抢救医嘱，但未读取到对应抢救记录",
            "抢救事件已被有效医嘱触发",
            "先核对抢救记录是否已完整同步",
        ),
        (
            "rescue_end_time_missing",
            "抢救记录缺少抢救结束时间",
            "无法计算抢救结束至记录完成的间隔",
            "补充本次抢救的权威结束时间",
        ),
        (
            "document_completion_time_missing",
            "抢救记录缺少权威完成时间",
            "无法计算抢救结束至记录完成的间隔",
            "补充抢救记录的权威完成时间",
        ),
    ],
)
def test_004_data_gap_reasons_have_specific_customer_messages(
    reason_code: str,
    expected_finding: str,
    expected_evidence: str,
    expected_suggestion: str,
) -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-09-01-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            fact_refs=(FACT_REF,),
            evaluator_version="rescue-timeliness-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "data_gap"
    assert expected_finding in result["findings"]
    assert expected_evidence in result["evidence"]
    assert expected_suggestion in result["suggestion"]


@pytest.mark.parametrize(
    ("rule_id", "reason_code", "expected_finding"),
    [
        ("LX0609-09-01-01", "trigger_absent_complete", "未发现有效抢救事件"),
        ("LX0609-02-01-02", "evaluation_window_not_mature", "入院尚未满72小时"),
        ("LX0609-02-01-03", "evaluation_window_not_mature", "病情稳定观察时段尚未满3天"),
        ("LX0609-06-01-02", "trigger_absent_complete", "未发现已实施的CT或MRI检查"),
        ("LX0609-06-01-04", "trigger_absent_complete", "未发现已实施的CT或MRI检查"),
        ("LX0609-06-01-05", "trigger_absent_complete", "未发现已实施并出具报告的CT或MRI检查"),
    ],
)
def test_not_applicable_reasons_have_specific_customer_messages(
    rule_id: str,
    reason_code: str,
    expected_finding: str,
) -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            fact_refs=(FACT_REF,),
            evaluator_version="basic-timeliness-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "not_applicable"
    assert expected_finding in result["findings"]


def test_022_mixed_opinions_name_each_problematic_episode() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-03-01-03",
        facts={
            "verification_kind": "consultation_opinion_quality_check",
            "episode_count": 4,
            "document_count": 4,
            "semantic_state": "mixed",
            "checked_requirement": "给出针对当前病情的明确诊疗意见",
            "source_document_ids": [
                "CONSULT-1",
                "CONSULT-2",
                "CONSULT-3",
                "CONSULT-4",
            ],
            "episode_results": [
                {
                    "episode_index": 1,
                    "semantic_state": "clear",
                    "source_document_id": "CONSULT-1",
                    "record_time": "2026-07-20 09:00:00",
                    "document_title": "会诊记录单",
                },
                {
                    "episode_index": 2,
                    "semantic_state": "vague",
                    "source_document_id": "CONSULT-2",
                    "record_time": "2026-07-21 10:30:00",
                    "document_title": "会诊记录单",
                },
                {
                    "episode_index": 3,
                    "semantic_state": "clear",
                    "source_document_id": "CONSULT-3",
                    "record_time": "2026-07-22 11:00:00",
                    "document_title": "会诊记录单",
                },
                {
                    "episode_index": 4,
                    "semantic_state": "missing",
                    "source_document_id": "CONSULT-4",
                    "record_time": "2026-07-23 14:15:00",
                    "document_title": "会诊记录单",
                },
            ],
        },
    )

    assert finding == (
        "共核对4次会诊意见；需完善2次："
        "2026-07-21 10:30:00《会诊记录单》（第2次）意见不明确；"
        "2026-07-23 14:15:00《会诊记录单》（第4次）未记录明确会诊意见。"
        "其余2次意见明确。"
    )


@pytest.mark.parametrize(
    ("rule_id", "facts", "expected"),
    [
        (
            "LX0609-02-01-05",
            {
                "failure_kind": "critical_daily_record_coverage_satisfied",
                "required_dates": ["2026-06-01", "2026-06-02"],
                "covered_dates": ["2026-06-01", "2026-06-02"],
            },
            "病危观察期 2026-06-01 至 2026-06-02，共 2 天；每日病程 2/2 天，记录完整。本阶段仅核对病危期间每日病程。",
        ),
        (
            "LX0609-06-01-05",
            {
                "failure_kind": "exam_lab_requirement_not_documented",
                "report_time": "2026-06-02 14:00:00",
                "response_record_count": 1,
                "response_record_time": "2026-06-02 18:00:00",
                "interval_hours": 4.0,
            },
            "CT/MRI 报告于 2026-06-02 14:00:00 出具。已核对首次病程记录及后续病程记录，找到 1 份报告后相关病程，最早相关病程时间 2026-06-02 18:00:00，间隔 4 小时，但病程未记录阳性结果的临床意义判断或相应处置。",
        ),
        (
            "LX0609-03-01-01",
            {"execution_record_state": "未发现执行记录"},
            "已找到会诊意见，但未发现对应的请会诊执行记录。",
        ),
        (
            "LX0609-03-01-02",
            {"consultation_assessment": "不符合要求"},
            "已核对会诊申请目的，其中未说明具体临床问题、会诊理由或明确目的。",
        ),
        (
            "LX0609-03-01-02",
            {
                "verification_kind": "consultation_application_quality_check",
                "episode_count": 4,
                "document_count": 4,
                "semantic_state": "mixed",
                "checked_requirement": "说明具体临床问题、会诊理由或明确会诊目的",
                "source_document_ids": ["opaque-1", "opaque-2"],
            },
            "共核对4次会诊申请，其中部分申请未说明具体临床问题、会诊理由或明确目的。",
        ),
        (
            "LX0609-03-01-03",
            {
                "verification_kind": "consultation_opinion_quality_check",
                "episode_count": 3,
                "document_count": 3,
                "semantic_state": "vague",
                "checked_requirement": "给出针对当前病情的明确诊疗意见",
                "source_document_ids": ["opaque-1"],
            },
            "共核对3次会诊意见，均未给出针对当前病情的明确诊疗意见。",
        ),
        (
            "LX0609-05-02-01",
            {
                "verification_kind": "chemotherapy_order_course_comparison",
                "order_count": 1,
                "field_results": {
                    "drug_name": "matched",
                    "dose": "mismatched",
                    "route": "matched",
                    "time": "matched",
                },
            },
            "已核对 1 条化疗医嘱及对应病程，剂量记录不一致。",
        ),
        (
            "LX0609-04-01-03",
            {
                "performed_surgery_confirmed": True,
                "procedure_kind": "surgery",
                "effective_surgery_level": "四级",
                "surgery_level_source": "hospital_performance",
                "mdt_discussion_state": "missing",
                "procedure_code": "01.2400X013",
                "procedure_name": "硬脑膜外血肿清除术",
            },
            "已确认实施四级手术 硬脑膜外血肿清除术（01.2400X013）（等级来源：院内绩效分配），未找到术前多学科讨论记录。",
        ),
        (
            "LX0609-11-03-02",
            {
                "failure_kind": "transfusion_consent_incomplete",
                "missing_fields": ["patient_or_agent_signature", "signed_time"],
            },
            "输血知情同意书缺少：患者或代理人签名、精确到分钟的签署时间。",
        ),
        (
            "LX0609-07-01-01",
            {
                "failure_kind": "pretransfusion_items_incomplete",
                "missing_items": ["hiv", "syphilis", "alt"],
            },
            "输血前九项缺少：艾滋病病毒抗体、梅毒筛查、谷丙转氨酶。",
        ),
        (
            "LX0609-07-01-02",
            {
                "verification_kind": "pretransfusion_assessment_complete",
                "missing_fields": [],
            },
            "输血申请单已记录申请理由及输血前客观指标，且在实际输血前完成。",
        ),
        (
            "LX0609-07-01-02",
            {
                "failure_kind": "pretransfusion_assessment_time_conflict",
                "application_time": "2026-08-20 15:00:00",
                "transfusion_time": "2026-08-20 14:00:00",
                "elapsed_minutes": 60,
            },
            "输血申请时间 2026-08-20 15:00:00 晚于实际输血时间 2026-08-20 14:00:00 60 分钟，时间顺序存在冲突。",
        ),
        (
            "LX0609-07-01-02",
            {
                "failure_kind": "pretransfusion_assessment_missing",
                "missing_fields": ["indication", "laboratory_indicator"],
            },
            "已确认实施输血，但未找到可核对的输血前评估记录。",
        ),
        (
            "LX0609-07-02-02",
            {
                "verification_kind": "transfusion_course_record_complete",
                "missing_fields": [],
            },
            "输血病程已记录指征、起止时间、血液成分、输注量、过程观察及反应处理。",
        ),
        (
            "LX0609-07-03-01",
            {
                "verification_kind": "posttransfusion_evaluation_complete",
                "transfusion_end_time": "2026-06-05 16:00:00",
                "evaluation_time": "2026-06-06 08:00:00",
                "elapsed_hours": 16.0,
            },
            "已在输血结束后 24 小时内完成效果评价，间隔 16 小时（结束时间 2026-06-05 16:00:00；评价时间 2026-06-06 08:00:00）。",
        ),
        (
            "LX0609-05-01-03",
            {
                "verification_kind": "antimicrobial_effect_evaluation_check",
                "antimicrobials": ["美罗培南", "万古霉素"],
                "window_hours": [48, 72],
                "evaluation_intervals": [],
                "unmatched_antimicrobials": ["万古霉素"],
                "association_ambiguous": False,
            },
            "已核对抗菌药物 美罗培南、万古霉素；其中 万古霉素 未找到计划开始/启用后 48～72 小时内的效果评价记录。",
        ),
        (
            "LX0609-08-01-01",
            {
                "verification_kind": "discharge_record_timeliness_check",
                "record_time": "2026-06-09 09:00:00",
                "discharge_time": "2026-06-09 10:00:00",
                "actual_interval_hours": -1.0,
            },
            "出院记录时间早于权威出院时间 1小时（记录时间 2026-06-09 09:00:00；出院时间 2026-06-09 10:00:00），时间顺序存在冲突，暂无法判断是否在出院后 24 小时内完成。",
        ),
        (
            "LX0609-04-05-03",
            {
                "verification_kind": "postoperative_first_course_presence_check",
                "performed_surgery_count": 7,
                "postoperative_first_course_count": 2,
            },
            "已确认实施手术 7 台，找到术后首次病程记录 2 份；尚不能逐台关联，暂无法确认每台手术均有对应记录。",
        ),
        (
            "LX0609-07-04-01",
            {
                "failure_kind": "transfusion_comparison_fields_missing",
                "missing_fields_by_source": {
                    "surgery_record": ["doses"],
                    "postsurg_firstcourse_record": ["components", "doses"],
                },
            },
            "手术记录缺少输注量；术后首次病程记录缺少血液成分、输注量，无法完成三方一致性核对。",
        ),
    ],
)
def test_transfusion_controlled_facts_render_customer_readable_finding(
    rule_id, facts, expected
):
    assert customer_finding_from_controlled_facts(rule_id=rule_id, facts=facts) == expected


def test_061_boundary_overdue_duration_does_not_round_to_threshold() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-08-01-01",
        facts={
            "verification_kind": "discharge_record_timeliness_check",
            "discharge_time": "2026-06-09 10:00:00",
            "record_time": "2026-06-10 10:00:01",
            "threshold_hours": 24,
            "actual_interval_hours": 24.0,
        },
    )

    assert finding == (
        "出院时间 2026-06-09 10:00:00，出院记录时间 2026-06-10 10:00:01，"
        "实际间隔 24小时0分1秒（超时1秒），规定时限 24 小时。"
    )


def test_061_one_second_negative_interval_renders_a_time_conflict() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-08-01-01",
        facts={
            "verification_kind": "discharge_record_timeliness_check",
            "discharge_time": "2026-06-09 10:00:00",
            "record_time": "2026-06-09 09:59:59",
            "threshold_hours": 24,
            "actual_interval_hours": -1 / 3600,
        },
    )

    assert finding == (
        "出院记录时间早于权威出院时间 1秒"
        "（记录时间 2026-06-09 09:59:59；出院时间 2026-06-09 10:00:00），"
        "时间顺序存在冲突，暂无法判断是否在出院后 24 小时内完成。"
    )


def test_061_missing_record_time_does_not_render_none_values() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-08-01-01",
        facts={
            "failure_kind": "discharge_record_timeliness_check",
            "discharge_time": "2026-07-13 15:15:00",
            "record_time": None,
            "threshold_hours": 24,
            "actual_interval_hours": None,
        },
    )

    assert finding == (
        "已取得权威出院时间 2026-07-13 15:15:00，但未取得出院记录完成时间，"
        "暂无法判断是否在出院后 24 小时内完成。"
    )
    assert "None" not in finding


def test_061_conflicting_authoritative_discharge_times_are_explicit() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-08-01-01",
        facts={
            "verification_kind": "discharge_record_timeliness_check",
            "discharge_time": None,
            "record_time": None,
            "threshold_hours": 24,
            "actual_interval_hours": None,
            "conflicting_discharge_times": [
                "2026-07-01 12:00:00",
                "2026-07-02 12:00:00",
            ],
        },
    )

    assert finding == (
        "发现多条权威出院时间：2026-07-01 12:00:00、2026-07-02 12:00:00；"
        "时间依据相互冲突，暂无法判断出院记录是否在出院后 24 小时内完成，请核对住院登记时间。"
    )


def test_058_missing_drug_start_time_does_not_claim_expert_support_absent() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-05-01-06",
        facts={
            "failure_kind": "special_antimicrobial_expert_support_check",
            "special_antimicrobials": ["美罗培南"],
            "expert_support_present": False,
            "first_antimicrobial_time": None,
            "expert_support_time": None,
            "support_before_use": False,
            "unmatched_special_antimicrobials": [],
            "association_ambiguous": False,
        },
    )

    assert finding == (
        "已识别特殊级抗菌药物 美罗培南 计划，但缺少计划开始/启用时间，"
        "暂无法判断专家支持记录是否在用药前完成。"
    )
    assert "未找到专家" not in finding


def test_020_customer_finding_lists_missing_recommendations_by_episode_and_action_type():
    facts = {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 3,
        "recommendation_count": 4,
        "specific_execution_count": 3,
        "generic_execution_count": 0,
        "missing_execution_count": 1,
        "relation_state": "execution_missing",
        "recommendation_results": [
            {
                "episode_index": 1,
                "recommendation_index": 1,
                "action_type": "medication",
                "execution_state": "specific",
            },
            {
                "episode_index": 2,
                "recommendation_index": 2,
                "action_type": "test",
                "execution_state": "missing",
            },
            {
                "episode_index": 3,
                "recommendation_index": 3,
                "action_type": "monitoring",
                "execution_state": "specific",
            },
            {
                "episode_index": 3,
                "recommendation_index": 4,
                "action_type": "procedure",
                "execution_state": "specific",
            },
        ],
        "source_document_ids": ["CONSULT-2"],
    }

    assert customer_finding_from_controlled_facts(
        rule_id="LX0609-03-01-01", facts=facts
    ) == (
        "共核对3次已完成会诊的4条建议：3条已找到明确执行记录，"
        "1条未找到对应执行记录。未闭环：第2次会诊的检查类建议。"
    )


def test_020_customer_finding_does_not_hide_generic_or_unknown_recommendations():
    facts = {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 2,
        "recommendation_count": 3,
        "specific_execution_count": 0,
        "generic_execution_count": 1,
        "missing_execution_count": 1,
        "relation_state": "execution_missing",
        "recommendation_results": [
            {
                "episode_index": 1,
                "recommendation_index": 1,
                "action_type": "medication",
                "execution_state": "generic",
            },
            {
                "episode_index": 2,
                "recommendation_index": 2,
                "action_type": "test",
                "execution_state": "missing",
            },
            {
                "episode_index": 2,
                "recommendation_index": 3,
                "action_type": "monitoring",
                "execution_state": "unknown",
            },
        ],
        "source_document_ids": ["CONSULT-2"],
    }

    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-03-01-01", facts=facts
    )

    assert "1条找到笼统执行痕迹" in finding
    assert "1条暂无法判断" in finding


def test_021_customer_finding_identifies_the_specific_vague_consultation_application():
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-03-01-02",
        facts={
            "verification_kind": "consultation_application_quality_check",
            "episode_count": 2,
            "document_count": 2,
            "semantic_state": "mixed",
            "checked_requirement": "说明具体临床问题、会诊理由或明确会诊目的",
            "episode_results": [
                {
                    "episode_index": 1,
                    "semantic_state": "clear",
                    "record_time": "2026-07-20 01:00:00",
                    "document_title": "会诊申请单",
                },
                {
                    "episode_index": 2,
                    "semantic_state": "vague",
                    "record_time": "2026-07-20 02:00:00",
                    "document_title": "会诊申请单",
                },
            ],
        },
    )

    assert finding == (
        "共核对2次会诊申请；需完善1次："
        "2026-07-20 02:00:00《会诊申请单》（第2次）目的不明确。其余1次申请目的明确。"
    )


def test_controlled_finding_does_not_render_untrusted_matrix_values():
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-07-04-01",
        facts={
            "failure_kind": "transfusion_records_inconsistent",
            "differing_fields": ["components"],
            "comparison_matrix": {
                "surgery_record": {"components": ["PRIVATE_CHART_BODY"], "doses": []},
            },
        },
    )

    assert finding == "手术记录、麻醉记录和术后首次病程记录中的血液成分不一致。"
    assert "PRIVATE_CHART_BODY" not in finding


@pytest.mark.parametrize("rule_id", ["LX0609-06-04-01", "LX0609-06-04-02"])
def test_critical_value_missing_result_detail_renders_exact_gap(rule_id):
    finding = customer_finding_from_controlled_facts(
        rule_id=rule_id,
        facts={
            "failure_kind": "critical_value_result_detail_missing",
            "lab_report_count": 43,
            "missing_source": "labtest_item_report",
        },
    )

    assert finding == (
        "已读取到检验报告 43 条，但检验结果明细未同步，"
        "无法取得 PL/PH 危急值标志及报告时间。"
    )


def test_anesthesia_visit_incomplete_facts_render_exact_customer_gaps():
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-04-04-02",
        facts={
            "failure_kind": "anesthesia_visit_incomplete",
            "missing_fields_by_visit": {
                "preanesthesia_visit": ["airway_assessment", "risk_discussion"],
                "postanesthesia_visit": [
                    "respiratory_status",
                    "complication_assessment",
                ],
            },
        },
    )

    assert finding == (
        "麻醉术前访视缺少气道评估、麻醉风险告知；"
        "麻醉术后访视缺少呼吸情况、麻醉并发症评估。"
    )


def test_anesthesia_visit_complete_facts_render_compliance_reason():
    assert customer_finding_from_controlled_facts(
        rule_id="LX0609-04-04-02",
        facts={
            "verification_kind": "anesthesia_visits_complete",
            "performed_anesthesia_confirmed": True,
            "checked_sources": [
                "preane_surveil_record",
                "postane_surveil_record",
            ],
            "checked_fields_by_visit": {
                "preanesthesia_visit": [
                    "asa_level",
                    "airway_assessment",
                    "fasting_status",
                    "anesthesia_history",
                    "risk_discussion",
                    "anesthetist_signature",
                    "record_time",
                ],
                "postanesthesia_visit": [
                    "consciousness_status",
                    "respiratory_status",
                    "circulatory_status",
                    "complication_assessment",
                    "anesthetist_signature",
                    "record_time",
                ],
            },
        },
    ) == (
        "麻醉术前访视已核对：ASA分级、气道评估、禁食禁饮情况、既往麻醉史、"
        "麻醉风险告知、麻醉医师签名、记录时间；麻醉术后访视已核对：意识状态、"
        "呼吸情况、循环情况、麻醉并发症评估、麻醉医师签名、记录时间。"
    )


def _reduced(final_state: CustomerFinalState):
    dimensions = {
        CustomerFinalState.COMPLIANT: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        ),
        CustomerFinalState.NON_COMPLIANT: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "requirement_violated",
        ),
        CustomerFinalState.NOT_APPLICABLE: (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "trigger_absent_complete",
        ),
        CustomerFinalState.DATA_GAP: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "source_unavailable",
        ),
        CustomerFinalState.TECHNICAL_ERROR: (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            "source_query_error",
        ),
        CustomerFinalState.EVALUATION_UNKNOWN: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "evidence_conflict",
        ),
    }
    applicability, evidence, direction, reason = dimensions[final_state]
    return reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-01-01-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=applicability,
            evidence_state=evidence,
            qc_direction=direction,
            reason_code=reason,
            fact_refs=(FACT_REF,),
            evaluator_version="basic-timeliness-v1",
            confidence=0.9,
        )
    )


@pytest.mark.parametrize(
    ("final_state", "customer_status", "is_compliant"),
    [
        (CustomerFinalState.COMPLIANT, "compliant", True),
        (CustomerFinalState.NON_COMPLIANT, "non_compliant", False),
        (CustomerFinalState.NOT_APPLICABLE, "not_applicable", True),
        (CustomerFinalState.DATA_GAP, "data_gap", None),
        (CustomerFinalState.TECHNICAL_ERROR, "technical_error", None),
        (CustomerFinalState.EVALUATION_UNKNOWN, "uncertain", None),
    ],
)
def test_renderer_maps_only_reducer_state_to_customer_status(
    final_state,
    customer_status,
    is_compliant,
):
    result = render_luxian_0609_customer_result(
        decision=_reduced(final_state),
    )

    assert result["status"] == result["result_status"] == customer_status
    assert result["is_compliant"] is is_compliant
    assert result["reason_code"] == _reduced(final_state).reason_code
    assert set(result) == CUSTOMER_RESULT_KEYS
    assert result["evidence_items"] == []
    assert result["criterion_results"] == []
    assert "metadata" not in result
    assert "audit" not in result
    assert "diagnostic_trace" not in result


@pytest.mark.parametrize(
    ("reason_code", "expected_finding"),
    [
        ("source_unavailable", "当前缺少入院时间或入院记录时间，暂时无法完成核对"),
        ("source_empty", "当前缺少入院时间或入院记录时间，暂时无法完成核对"),
        ("source_truncated", "当前缺少入院时间或入院记录时间，暂时无法完成核对"),
        ("source_readiness_unproven", "相关资料是否完整尚待确认"),
        ("required_field_missing", "当前缺少入院时间或入院记录时间，暂时无法完成核对"),
        ("authoritative_time_missing", "当前缺少入院时间或入院记录时间，暂时无法完成核对"),
        ("association_failed", "当前缺少入院时间或入院记录时间，暂时无法完成核对"),
        ("linkage_unresolved", "暂未找到可相互核对的对应记录"),
        ("applicability_source_gap", "暂无法确认本质控点是否适用"),
    ],
)
def test_renderer_explains_data_gap_as_system_evidence_condition(
    reason_code,
    expected_finding,
):
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-01-01-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            fact_refs=(FACT_REF,),
            evaluator_version="basic-timeliness-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"] == expected_finding
    assert "请补充或同步所需数据" not in result["suggestion"]


def test_006_required_field_gap_names_the_unverifiable_physician_title():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-02-01-02",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="required_field_missing",
            fact_refs=(FACT_REF,),
            evaluator_version="basic-timeliness-authoritative-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "data_gap"
    assert "查房医师职称" in result["findings"]
    assert "查房医师职称" in result["evidence"]


def test_029_missing_surgery_time_explains_confirmed_trigger_and_linkage_gap():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-04-01-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_missing",
            fact_refs=(FACT_REF,),
            evaluator_version="surgery-document-native-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"] == (
        "已确认本次存在已实施手术，但缺少手术实施时间，"
        "暂无法将术前小结与同一次手术准确关联"
    )


def test_029_association_gap_explains_confirmed_surgery_and_summary():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-04-01-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="association_failed",
            fact_refs=(FACT_REF,),
            evaluator_version="surgery-document-native-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"] == (
        "已确认本次存在已实施手术且已读取术前小结，但现有资料无法确认术前小结"
        "对应哪一台手术，暂无法逐台完成核对"
    )

    assert "缺少可用于单台手术关联的实施时间" not in result["evidence"]
    assert "术前小结与具体手术的单台对应关系未能确定" in result["evidence"]
    assert "完整可读取的文书、权威时间及必要关联字段" not in result["suggestion"]
    assert "术前小结与具体手术的单台关联信息" in result["suggestion"]


@pytest.mark.parametrize(
    ("rule_id", "expected_required", "expected_recommendation"),
    (
        (
            "LX0609-05-01-02",
            "每条抗菌药物医嘱对应的使用或调整动作、理由及关联时间",
            "逐条核对抗菌药物医嘱与病程",
        ),
        (
            "LX0609-05-01-03",
            "每条抗菌药物的计划开始/启用时间及对应的48至72小时效果评价",
            "核对每条抗菌药物的计划开始/启用时间",
        ),
        (
            "LX0609-05-01-06",
            "特殊级抗菌药物计划开始/启用时间与专家查房或会诊支持记录的关联",
            "核对特殊级抗菌药物计划开始/启用时间",
        ),
        (
            "LX0609-08-01-01",
            "权威出院时间与出院记录完成时间",
            "核对住院登记中的权威出院时间",
        ),
        (
            "LX0609-04-02-07",
            "每次会诊申请与对应会诊记录的业务关联、申请时间及完成时间",
            "逐次核对会诊申请与会诊记录",
        ),
    ),
)
def test_priority_data_gap_rules_explain_event_or_time_gap(
    rule_id: str,
    expected_required: str,
    expected_recommendation: str,
) -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=(
                "association_failed"
                if rule_id in {"LX0609-05-01-02", "LX0609-04-02-07"}
                else "authoritative_time_missing"
            ),
            fact_refs=(FACT_REF,),
            evaluator_version="customer-gap-copy-v1",
        )
    )

    suggestion = render_luxian_0609_customer_result(decision=decision)["suggestion"]

    assert f"需要补充：{expected_required}" in suggestion
    assert expected_recommendation in suggestion
    assert "完整可读取的文书、权威时间及必要关联字段" not in suggestion


def test_rule_009_candidate_scope_gap_has_rule_and_reason_specific_message() -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-02-01-05",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="candidate_scope_incomplete",
            fact_refs=(FACT_REF,),
            evaluator_version="course-severity-semantic-v2",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"] == "病情变化候选超过单次安全核对范围，暂未形成确定结论"
    assert "病历资料缺失" in result["evidence"]
    assert "无需补充病历资料" in result["suggestion"]

    other_rule = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-05-01-02",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="candidate_scope_incomplete",
            fact_refs=(FACT_REF,),
            evaluator_version="native-antimicrobial-v1",
        )
    )
    other_result = render_luxian_0609_customer_result(decision=other_rule)
    assert "抗菌药物" in other_result["findings"]
    assert "病情变化候选" not in other_result["findings"]


def test_rule_specific_gap_keeps_controlled_customer_reason_and_rule_context():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-11-01-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="source_unavailable",
            fact_refs=(FACT_REF,),
            evaluator_version="native-surgery-document-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"].startswith("当前系统尚未接入核对所需的资料；")
    assert "手术知情同意书" in result["findings"]
    assert "已确认实施手术" in result["evidence"]


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        (
            {
                "failure_kind": "surgery_consent_document_missing",
                "consent_state": "missing",
                "performed_surgery_confirmed": True,
            },
            "已确认实施手术，未检索到手术知情同意书。",
        ),
        (
            {
                "failure_kind": "surgery_consent_body_missing",
                "consent_state": "blank",
                "performed_surgery_confirmed": True,
            },
            "已确认实施手术，但手术知情同意书正文为空。",
        ),
        (
            {
                "failure_kind": "surgery_consent_signature_missing",
                "consent_state": "signature_missing",
                "performed_surgery_confirmed": True,
                "missing_signature_roles": ["surgeon"],
            },
            "已确认实施手术，但手术知情同意书缺少术者签名。",
        ),
    ],
)
def test_lx0609_033_controlled_consent_facts_have_distinct_customer_explanations(
    facts, expected
):
    assert customer_finding_from_controlled_facts(
        rule_id="LX0609-11-01-01",
        facts=facts,
    ) == expected


def test_lx0609_012_non_explicit_positive_has_customer_readable_gap_explanation():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-06-01-05",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="positive_assertion_not_explicit",
            fact_refs=(FACT_REF,),
            evaluator_version="exam-lab-ruledecision-shadow-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "data_gap"
    assert result["reason_code"] == "positive_assertion_not_explicit"
    assert result["findings"] == "检查报告未明确写明阳性，暂无法启动阳性结果分析核对"
    assert "未明确标注“阳性”" in result["evidence"]


@pytest.mark.parametrize(
    ("rule_id", "reason_code", "expected_finding", "expected_suggestion"),
    (
        (
            "LX0609-06-01-04",
            "target_report_missing",
            "未读取到对应检查报告",
            "同步或核对对应的 CT/MRI 正式报告",
        ),
        (
            "LX0609-06-01-04",
            "authoritative_report_time_missing",
            "CT/MRI 报告缺少权威报告时间",
            "核对 CT/MRI 报告时间",
        ),
        (
            "LX0609-06-01-05",
            "association_failed",
            "CT/MRI 阳性结果与病程记录暂时无法唯一关联",
            "核对检查医嘱、报告和病程记录的业务关联标识",
        ),
        (
            "LX0609-06-03-03",
            "source_truncated",
            "细菌培养相关病程资料读取不完整",
            "完整同步细菌培养报告及报告后病程记录",
        ),
        (
            "LX0609-06-03-04",
            "required_field_missing",
            "阳性菌结果缺少可核对的结果或分析字段",
            "核对培养结果、阳性标志和分析病程",
        ),
    ),
)
def test_exam_lab_data_gap_explains_the_specific_missing_information(
    rule_id: str,
    reason_code: str,
    expected_finding: str,
    expected_suggestion: str,
) -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            fact_refs=(FACT_REF,),
            evaluator_version="exam-lab-ruledecision-shadow-v2",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "data_gap"
    assert result["reason_code"] == reason_code
    assert expected_finding in result["findings"]
    assert expected_suggestion in result["suggestion"]


def test_lx0609_025_renders_each_surgery_missing_fields_without_barcode() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-04-02-04",
        facts={
            "failure_kind": "implant_information_incomplete",
            "missing_fields": ["implant_material", "implant_quantity"],
            "implant_event_details": [
                {
                    "event_position": 1,
                    "missing_fields": ["implant_material"],
                    "implant_names": ["人工硬脑膜"],
                },
                {
                    "event_position": 2,
                    "missing_fields": ["implant_quantity"],
                    "implant_names": ["钛网"],
                },
            ],
            "source_label": "手术记录",
            "source_document_type": "surgery_record",
        },
    )

    assert finding == (
        "已确认实际使用永久性植入物；"
        "第1台手术（人工硬脑膜）手术记录缺少：材质；"
        "第2台手术（钛网）手术记录缺少：植入物数量。"
    )
    assert "条码" not in finding


def test_lx0609_025_complete_contract_lists_only_five_frozen_fields() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-04-02-04",
        facts={
            "verification_kind": "implant_information_complete",
            "performed_surgery_confirmed": True,
            "checked_fields": [
                "implant_name",
                "implant_type",
                "implant_specification",
                "implant_material",
                "implant_quantity",
            ],
            "identified_implants": ["人工硬脑膜"],
            "source_label": "手术记录",
            "source_document_type": "surgery_record",
        },
    )

    assert "名称、植入物种类、规格/型号、材质、植入物数量均有记录" in finding
    assert "条码" not in finding


@pytest.mark.parametrize(
    ("reason_code", "expected_evidence"),
    [
        ("authoritative_time_missing", "缺少本次住院的评价截止日期或有效出院时间"),
        ("authoritative_time_conflict", "存在先后冲突"),
    ],
)
@pytest.mark.parametrize(
    "rule_id",
    ("LX0609-06-01-04", "LX0609-06-01-05", "LX0609-06-03-03", "LX0609-06-03-04"),
)
def test_exam_lab_window_gap_has_customer_readable_specific_explanation(
    rule_id,
    reason_code,
    expected_evidence,
):
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            fact_refs=(FACT_REF,),
            evaluator_version="exam-lab-ruledecision-shadow-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "data_gap"
    assert result["reason_code"] == reason_code
    assert expected_evidence in result["evidence"]


@pytest.mark.parametrize(
    "rule_id",
    ("LX0609-06-01-04", "LX0609-06-01-05", "LX0609-06-03-03", "LX0609-06-03-04"),
)
def test_exam_lab_window_not_mature_is_customer_not_applicable(rule_id):
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="evaluation_window_not_mature",
            fact_refs=(FACT_REF,),
            evaluator_version="exam-lab-ruledecision-shadow-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "not_applicable"
    assert result["reason_code"] == "evaluation_window_not_mature"
    assert "24 小时评价窗口尚未结束" in result["findings"]
    assert "无需提前补写" in result["suggestion"]


WINDOW_NOT_MATURE_COPY = "报告后 24 小时评价窗口尚未届满，暂不判定"
NEGATIVE_NOT_APPLICABLE_COPY = "按报告结果判定为未检出需分析的阳性结果，本项不适用"
NEUTRAL_NOT_APPLICABLE_COPY = "未确认本次检查为需分析的目标事件，本项不适用"


def _multi_event_analysis_facts(*, second_event_positive_state):
    """构造仅第二事件阳性标签不同的多事件 012 客户事实。

    其余字段逐字段相同，用于锁定"文案差异只来自真实原因"。
    """

    second_event = {
        "event_position": 2,
        "event_status": "not_applicable",
        "report_time": "2026-04-04 12:00:00",
        "response_record_count": 0,
    }
    if second_event_positive_state is not None:
        second_event["positive_state"] = second_event_positive_state
    return {
        "verification_kind": "exam_lab_requirement_checked",
        "subject": "ct_mri",
        "requirement": "positive_result_analysis_within_24h",
        "event_phase": "report",
        "checked_sources": ["exam_lab_report", "course_record"],
        "threshold_hours": 24,
        "event_count": 2,
        "event_position": 2,
        "reviewed_record_scope": "首次病程记录及后续病程记录",
        "event_results": [
            {
                "event_position": 1,
                "event_status": "compliant",
                "report_time": "2026-04-01 12:00:00",
                "positive_state": "positive",
                "response_record_count": 1,
                "response_record_time": "2026-04-01 16:24:00",
                "interval_hours": 4.4,
                "requirement_met": True,
            },
            second_event,
        ],
    }


def test_012_multi_event_window_not_mature_and_negative_copies_are_distinct() -> None:
    window_facts = _multi_event_analysis_facts(second_event_positive_state="positive")
    negative_facts = _multi_event_analysis_facts(second_event_positive_state="negative")
    window_frozen = json.loads(json.dumps(window_facts))
    negative_frozen = json.loads(json.dumps(negative_facts))

    window_finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-06-01-05", facts=window_facts
    )
    negative_finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-06-01-05", facts=negative_facts
    )

    # 窗口未成熟：必须写明评价窗口尚未届满，不得断言报告未明确阳性。
    assert WINDOW_NOT_MATURE_COPY in window_finding
    assert NEGATIVE_NOT_APPLICABLE_COPY not in window_finding
    assert "报告未明确阳性" not in window_finding
    # 明确阴性：只能表述为系统判定，不得当成临床事实断言。
    assert NEGATIVE_NOT_APPLICABLE_COPY in negative_finding
    assert WINDOW_NOT_MATURE_COPY not in negative_finding
    assert "报告未明确阳性" not in negative_finding
    # 两种真实原因的文案必须互不相同。
    assert window_finding != negative_finding
    # 渲染只读事实：不得改写任何客户展示事实。
    assert window_facts == window_frozen
    assert negative_facts == negative_frozen
    # 差异只来自 not_applicable 事件的 positive_state。
    assert window_facts["event_results"][1].pop("positive_state") == "positive"
    assert negative_facts["event_results"][1].pop("positive_state") == "negative"
    assert window_facts == negative_facts


@pytest.mark.parametrize("positive_state", ["unknown", "not_relevant", None])
def test_012_multi_event_unconfirmed_positive_state_uses_neutral_copy(
    positive_state,
) -> None:
    facts = _multi_event_analysis_facts(second_event_positive_state=positive_state)

    finding = customer_finding_from_controlled_facts(rule_id="LX0609-06-01-05", facts=facts)

    assert NEUTRAL_NOT_APPLICABLE_COPY in finding
    assert WINDOW_NOT_MATURE_COPY not in finding
    assert NEGATIVE_NOT_APPLICABLE_COPY not in finding


@pytest.mark.parametrize("rule_id", ["LX0609-06-01-04", "LX0609-06-03-03"])
def test_record_rule_multi_event_not_applicable_copy_is_unchanged(rule_id) -> None:
    facts = _multi_event_analysis_facts(second_event_positive_state="not_relevant")

    finding = customer_finding_from_controlled_facts(rule_id=rule_id, facts=facts)

    assert "本次事件不适用" in finding
    assert WINDOW_NOT_MATURE_COPY not in finding
    assert NEGATIVE_NOT_APPLICABLE_COPY not in finding
    assert NEUTRAL_NOT_APPLICABLE_COPY not in finding


@pytest.mark.parametrize(
    ("rule_id", "expected_finding", "expected_evidence"),
    [
        (
            "LX0609-06-02-03",
            "暂无法核对病理结果是否记入手术记录或病程",
            "病理最终诊断",
        ),
        (
            "LX0609-06-02-02",
            "暂无法核对病理取材记录",
            "病理申请或报告来源",
        ),
        (
            "LX0609-03-01-01",
            "暂无法核对会诊意见是否具有对应执行记录",
            "后续病程执行记录",
        ),
        (
            "LX0609-03-01-02",
            "暂无法核对会诊申请目的是否明确",
            "具体临床问题、会诊理由",
        ),
        (
            "LX0609-03-01-03",
            "暂无法核对会诊意见是否明确",
            "明确诊疗意见",
        ),
        (
            "LX0609-05-02-01",
            "暂无法核对化疗记录与医嘱是否一致",
            "药名、剂量、用法、时间",
        ),
        (
            "LX0609-08-01-04",
            "暂无法核对恶性肿瘤出院治疗计划",
            "恶性肿瘤诊断依据",
        ),
        (
            "LX0609-11-03-02",
            "暂无法完整核对输血知情同意书",
            "患者或代理人签名",
        ),
        (
            "LX0609-07-01-01",
            "暂无法完整核对输血前九项检查",
            "乙肝五项",
        ),
        (
            "LX0609-07-02-02",
            "暂无法完整核对输血病程记录",
            "输血原因、起止时间",
        ),
        (
            "LX0609-07-03-01",
            "暂无法核对输血后24小时评价",
            "输血结束时间",
        ),
    ],
)
def test_task3_data_gap_names_the_customer_visible_missing_material(
    rule_id,
    expected_finding,
    expected_evidence,
):
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="required_field_missing",
            fact_refs=(FACT_REF,),
            evaluator_version="native-task3-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"].startswith("当前")
    assert "；" in result["findings"]
    assert result["findings"].endswith(expected_finding)
    assert expected_evidence in result["evidence"]


def test_rule_identity_and_name_come_only_from_the_trusted_catalog():
    trusted = get_luxian_0609_rule("LX0609-01-01-01")
    result = render_luxian_0609_customer_result(
        decision=_reduced(CustomerFinalState.COMPLIANT),
    )

    assert trusted is not None
    assert result["rule_id"] == result["rule_code"] == "LX0609-01-01-01"
    assert result["rule_name"] == trusted["name"]
    assert result["rule_version"] == trusted["rule_version"]


@pytest.mark.parametrize(
    ("rule_id", "expected_finding"),
    [
        ("LX0609-01-01-01", "已确认入院记录在入院后 24 小时内完成。"),
        ("LX0609-02-01-05", "已核对病危期间的查房记录，未发现应记录日期缺失。"),
        ("LX0609-04-03-01", "已确认本次手术具备手术安全核查表。"),
        ("LX0609-07-01-01", "已核对输血前常规检查，所需项目完整。"),
        ("LX0609-07-04-01", "已核对术中输血相关记录，未发现文书间内容不一致。"),
    ],
)
def test_compliant_result_explains_why_it_is_compliant(rule_id, expected_finding):
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.SATISFIED,
            reason_code="requirement_satisfied",
            fact_refs=(FACT_REF,),
            evaluator_version="native-rule-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "compliant"
    assert result["findings"] == expected_finding
    assert result["findings"] != "符合质控要求"


def test_lx037_parent_visit_missing_has_noncontradictory_customer_explanation():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-04-04-02",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="eligibility_not_met",
            fact_refs=(FACT_REF,),
            evaluator_version="native-surgery-document-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "not_applicable"
    assert "已确认实施麻醉" in result["findings"]
    assert "LX0609-04-04-01" in result["evidence"]


def test_lx039_emergency_rescue_exception_uses_eligibility_customer_copy():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-04-01-02",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="eligibility_not_met",
            fact_refs=(FACT_REF,),
            evaluator_version="native-surgery-document-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "not_applicable"
    assert "急诊抢救手术" in result["findings"]
    assert "未实施手术" not in result["findings"]


def test_lx018_compliant_result_uses_controlled_criterion_values():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-01-01-02",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.SATISFIED,
            reason_code="requirement_satisfied",
            fact_refs=(FACT_REF,),
            evaluator_version="native-course-quality-v1",
            criterion_results=(
                CriterionResult(
                    criterion_id="chief_complaint_length",
                    status=CriterionStatus.PASSED,
                    reason_code="requirement_satisfied",
                    fact_refs=(FACT_REF,),
                    actual_value=8,
                    expected_value=20,
                    operator="lte",
                    unit="character",
                ),
                CriterionResult(
                    criterion_id="diagnostic_direction",
                    status=CriterionStatus.PASSED,
                    reason_code="requirement_satisfied",
                    fact_refs=(FACT_REF,),
                    actual_value="supported",
                    rationale_code="supported",
                    dimensions=("symptom_pattern",),
                    medical_analysis=(
                        "主诉中的反复胸痛及持续时间，为入院第一诊断"
                        "不稳定型心绞痛提供了症状和病程依据。"
                    ),
                ),
            ),
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"] == (
        "主诉共 8 字，符合不超过 20 字要求；"
        "第一诊断可导出：主诉中的反复胸痛及持续时间，为入院第一诊断"
        "不稳定型心绞痛提供了症状和病程依据。"
    )


def test_lx018_non_compliant_result_names_failed_diagnostic_direction():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-01-01-02",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="requirement_violated",
            fact_refs=(FACT_REF,),
            evaluator_version="native-course-quality-v1",
            criterion_results=(
                CriterionResult(
                    criterion_id="chief_complaint_length",
                    status=CriterionStatus.PASSED,
                    reason_code="requirement_satisfied",
                    fact_refs=(FACT_REF,),
                    actual_value=18,
                    expected_value=20,
                    operator="lte",
                    unit="character",
                ),
                CriterionResult(
                    criterion_id="diagnostic_direction",
                    status=CriterionStatus.FAILED,
                    reason_code="complaint_primary_diagnosis_mismatch",
                    fact_refs=(FACT_REF,),
                    actual_value="mismatch",
                    rationale_code="diagnosis_mismatch",
                    dimensions=("anatomic_site",),
                ),
            ),
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"] == (
        "主诉共 18 字，符合不超过 20 字要求；"
        "主诉与入院第一诊断的方向不一致，不能据此导出第一诊断。"
    )


def test_lx018_customer_finding_preserves_full_medical_analysis():
    analysis = "主诉提供的症状和病程线索需要结合第一诊断判断。" * 20
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-01-01-02",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="requirement_violated",
            fact_refs=(FACT_REF,),
            evaluator_version="native-course-quality-v1",
            criterion_results=(
                CriterionResult(
                    criterion_id="chief_complaint_length",
                    status=CriterionStatus.PASSED,
                    reason_code="requirement_satisfied",
                    fact_refs=(FACT_REF,),
                    actual_value=8,
                    expected_value=20,
                    operator="lte",
                    unit="character",
                ),
                CriterionResult(
                    criterion_id="diagnostic_direction",
                    status=CriterionStatus.FAILED,
                    reason_code="complaint_primary_diagnosis_mismatch",
                    fact_refs=(FACT_REF,),
                    actual_value="mismatch",
                    rationale_code="diagnosis_mismatch",
                    dimensions=("symptom_pattern",),
                    medical_analysis=analysis,
                ),
            ),
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert analysis in result["findings"]
    assert "…" not in result["findings"]


def test_data_gap_uses_unknown_criterion_label_to_name_missing_data():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-01-01-02",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="required_field_missing",
            fact_refs=(FACT_REF,),
            evaluator_version="native-course-quality-v1",
            criterion_results=(
                CriterionResult(
                    criterion_id="chief_complaint_length",
                    status=CriterionStatus.PASSED,
                    reason_code="requirement_satisfied",
                    fact_refs=(FACT_REF,),
                    actual_value=8,
                    expected_value=20,
                    operator="lte",
                    unit="character",
                ),
                CriterionResult(
                    criterion_id="diagnostic_direction",
                    status=CriterionStatus.UNKNOWN,
                    reason_code="required_field_missing",
                    fact_refs=(FACT_REF,),
                ),
            ),
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"] == "当前缺少第一诊断指向，暂时无法完成核对"
    assert "已读取到相关记录" in result["evidence"]
    assert "第一诊断指向" in result["evidence"]


@pytest.mark.parametrize("rule_id", DEFINED_RULE_IDS)
def test_each_defined_rule_data_gap_names_customer_visible_missing_material(rule_id):
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="required_field_missing",
            fact_refs=(FACT_REF,),
            evaluator_version="native-gap-acceptance-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "data_gap"
    assert result["findings"] not in {
        "当前记录缺少完成核对所需的关键信息",
        "当前资料不足，暂时无法完成核对",
    }
    assert result["evidence"] != "已读取到相关记录，但其中缺少本项判断所需的字段。"


@pytest.mark.parametrize(
    ("rule_id", "expected_material"),
    (
        ("LX0609-06-01-02", "CT/MRI"),
        ("LX0609-12-01-02", "病程记录"),
        ("LX0609-03-01-04", "会诊意见"),
    ),
)
def test_data_gap_for_event_rules_names_the_missing_customer_material(
    rule_id, expected_material
):
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="required_field_missing",
            fact_refs=(FACT_REF,),
            evaluator_version="native-gap-acceptance-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert expected_material in result["findings"]
    assert expected_material in result["evidence"]
    assert expected_material in result["suggestion"]


@pytest.mark.parametrize(("rule_id", "reason_code"), NOT_APPLICABLE_CASES)
def test_each_gated_rule_not_applicable_names_the_excluding_fact(
    rule_id, reason_code
):
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            fact_refs=(FACT_REF,),
            evaluator_version="native-not-applicable-acceptance-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "not_applicable"
    assert result["findings"] != "本次就诊不适用该质控点"
    assert result["evidence"] != "完整适用性证据未触发本质控点。"


def test_renderer_has_no_free_text_or_wrapper_mapping_input_seam():
    decision = _reduced(CustomerFinalState.NON_COMPLIANT)
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=decision,
            presentation={"findings": "PRIVATE_CHART_BODY_MARKER_7F4A"},
        )
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=decision,
            wrapper_rule={"name": "患者姓名：张三"},
        )
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=decision,
            executor_key="coord-secret-007",
        )


@pytest.mark.parametrize(
    "marker",
    [
        "PRIVATE_CHART_BODY_MARKER_7F4A",
        "VISIT-20260716-ABCXYZ",
        "ghp_secret_credential",
        "AKIAIOSFODNN7EXAMPLE",
        "header.payload.signature",
        "postgresql://user:pass@host/db",
        "DROP TABLE patient_records",
        "WITH recent AS (SELECT 1) SELECT 1",
        "SC‐087",
        "S C - 087",
        "SC_087",
        "LXE：31",
        "密码=secret-marker",
        "exception_message=private failure",
    ],
)
def test_no_arbitrary_string_input_can_enter_customer_dto(marker):
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=_reduced(CustomerFinalState.DATA_GAP),
            presentation={"findings": marker},
        )
    result = render_luxian_0609_customer_result(
        decision=_reduced(CustomerFinalState.DATA_GAP)
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert marker not in repr(result)
    assert marker not in serialized


def test_renderer_accepts_only_reducer_owned_decision():
    raw = RuleDecision(
        rule_id="LX0609-01-01-01",
        snapshot_hash=SNAPSHOT_HASH,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_satisfied",
        fact_refs=(FACT_REF,),
        evaluator_version="basic-timeliness-v1",
    )
    with pytest.raises(TypeError, match="ReducedRuleDecision"):
        render_luxian_0609_customer_result(decision=raw)


def test_safe_trace_is_separate_and_sink_failure_cannot_change_customer_result():
    traces = []
    decision = _reduced(CustomerFinalState.COMPLIANT)
    result = render_luxian_0609_customer_result(
        decision=decision,
        trace_sink=traces.append,
    )

    assert len(traces) == 1
    assert set(traces[0]) == {
        "event",
        "rule_id",
        "snapshot_hash",
        "decision_fingerprint",
        "reason_code",
        "fact_refs",
        "evaluator_version",
        "executor_key",
        "final_state",
    }
    assert {
        "snapshot_hash",
        "decision_fingerprint",
        "fact_refs",
        "evaluator_version",
        "executor_key",
        "final_state",
    }.isdisjoint(result)
    assert result["reason_code"] == decision.reason_code

    def explode(_payload):
        raise RuntimeError("trace sink failure Bearer secret 13800138000")

    repeated = render_luxian_0609_customer_result(
        decision=decision,
        trace_sink=explode,
    )
    assert repeated == result


def test_transfer_customer_facts_render_each_document_association_separately() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-10-02-02",
        facts={
            "verification_kind": "transfer_record_presence_check",
            "transfer_order_time": "2026-07-01 08:00:00",
            "transfer_in_time": "2026-07-01 09:00:00",
            "transfer_out_time": None,
            "transfer_in_associated": True,
            "transfer_out_associated": None,
        },
    )

    assert "转入记录已关联（2026-07-01 09:00:00）" in finding
    assert "转出记录暂无法唯一关联" in finding


def test_transfer_timeliness_uses_a_readable_gap_when_interval_is_unavailable() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-10-02-01",
        facts={
            "verification_kind": "transfer_record_timeliness_check",
            "transfer_order_time": "2026-07-01 08:00:00",
            "transfer_in_time": None,
            "transfer_out_time": "2026-07-01 10:00:00",
            "threshold_hours": 24,
            "transfer_in_interval_hours": None,
            "transfer_out_interval_hours": 2.0,
        },
    )

    assert "转入记录时间未能关联到本次转科，间隔无法计算" in finding
    assert "转出记录时间2026-07-01 10:00:00，间隔 2.0 小时" in finding
    assert "None 小时" not in finding


def test_transfer_multi_event_gap_renders_counts_without_claiming_documents_missing() -> None:
    facts = {
        "failure_kind": "transfer_event_association_gap",
        "transfer_order_count": 3,
        "transfer_in_count": 2,
        "transfer_out_count": 1,
    }
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-10-02-01",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="association_failed",
            fact_refs=(FACT_REF,),
            evaluator_version="transfer-documentation-v1",
            confidence=1.0,
        )
    )

    rendered = render_luxian_0609_customer_result(
        decision=decision,
        safe_customer_display_facts=facts,
    )

    expected = (
        "已识别3条转科相关医嘱、2份转入/1份转出记录，"
        "缺少可将各文书与具体转科事件对应的关联信息，暂无法逐次核对。"
    )
    assert customer_finding_from_controlled_facts(
        rule_id="LX0609-10-02-01", facts=facts
    ) == expected
    assert rendered["findings"] == expected
    assert "文书缺失" not in rendered["findings"]
    assert "缺少时间" not in rendered["findings"]


def test_transfer_multi_event_gap_does_not_invent_zero_count_record_evidence() -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-10-02-02",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="association_failed",
            fact_refs=(FACT_REF,),
            evaluator_version="transfer-documentation-v1",
            confidence=1.0,
        )
    )

    rendered = render_luxian_0609_customer_result(
        decision=decision,
        safe_customer_display_facts={
            "failure_kind": "transfer_event_association_gap",
            "transfer_order_count": 2,
            "transfer_in_count": 1,
            "transfer_out_count": 0,
        },
    )

    assert "1份转入/0份转出记录" in rendered["findings"]
    assert rendered["evidence"] == (
        "已定位本次纳入核对的转科资料，当前缺口为逐次事件对应关系。"
    )
    assert "候选转出记录" not in rendered["evidence"]


def test_preop_content_association_gap_does_not_claim_body_missing():
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id="LX0609-04-01-04", snapshot_hash=SNAPSHOT_HASH,
        applicability=ApplicabilityState.APPLICABLE, evidence_state=EvidenceState.DATA_GAP,
        qc_direction=QcDirection.UNKNOWN, reason_code="association_failed", fact_refs=(FACT_REF,),
        evaluator_version="native-preop-content-v1"))
    result = render_luxian_0609_customer_result(decision=decision)
    assert result["status"] == "data_gap"
    assert "已读取术前小结" in result["findings"]
    assert "具体手术" in result["findings"]
    assert "缺少术前小结正文" not in result["findings"]


@pytest.mark.parametrize("missing", [["planned_anesthesia"], ["precautions", "surgeon_preop_visit"]])
def test_preop_summary_explains_only_confirmed_missing_items(missing):
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id="LX0609-04-01-04", snapshot_hash=SNAPSHOT_HASH,
        applicability=ApplicabilityState.APPLICABLE, evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.DEFECT, reason_code="requirement_violated",
        fact_refs=(FACT_REF,), evaluator_version="preop-content-v1"))
    facts = {"verification_kind": "preop_content_incomplete", "missing_fields": missing,
             "documents": [{"missing_fields": ["brief_condition"]}]}
    result = render_luxian_0609_customer_result(decision=decision, safe_customer_display_facts=facts)
    assert result["status"] == "non_compliant"
    assert "确认缺少" in result["findings"]
    assert "简要病情" not in result["findings"]
    assert "同一份" not in result["suggestion"]
    if missing == ["planned_anesthesia"]:
        assert "拟施麻醉方式" in result["findings"]
        assert "拟施麻醉方式" in result["suggestion"]
        assert "术者术前查看" not in result["suggestion"]


def test_preop_summary_without_missing_facts_does_not_invent_items():
    from app.services.luxian_0609.customer_renderer import preop_summary_customer_message
    message = preop_summary_customer_message(rule_id="LX0609-04-01-04", status="non_compliant", facts={})
    assert "未提供可核验的具体缺项" in message[0]
    assert "先确认" in message[2]
    assert preop_summary_customer_message(rule_id="LX0609-04-01-04", status="data_gap", facts={}) is None
