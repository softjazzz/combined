from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.customer_renderer import (
    CUSTOMER_RESULT_KEYS,
    compliant_customer_finding,
    customer_finding_from_controlled_facts,
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


def test_010_association_facts_render_exact_customer_counts() -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-010",
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
        rule_id="LX0609-010",
        facts={"failure_kind": failure_kind},
    )

    assert expected in finding


def test_068_compliant_message_covers_regular_and_automatic_discharge_paths() -> None:
    finding = compliant_customer_finding(
        rule_id="LX0609-068",
        criterion_results=(),
    )

    assert "上级医师同意出院意见" in finding
    assert "自动出院" in finding
    assert "书面签署" in finding


def test_046_component_gap_uses_actual_transfused_component_copy_only_for_course_record() -> None:
    assert customer_finding_from_controlled_facts(
        rule_id="LX0609-046",
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
        rule_id="LX0609-042",
        facts={
            "failure_kind": "transfusion_consent_incomplete",
            "missing_fields": ["component"],
        },
    ) == "输血知情同意书缺少：拟输血成分。"


@pytest.mark.parametrize(
    ("rule_id", "facts", "expected_finding"),
    [
        (
            "LX0609-029",
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "presurg_summary",
                "performed_surgery_confirmed": True,
            },
            "已确认本次实施手术，但未找到对应的术前小结。",
        ),
        (
            "LX0609-038",
            {
                "failure_kind": "anesthesia_record_missing",
                "performed_anesthesia_confirmed": True,
                "checked_sources": ["anesthesia_record"],
            },
            "已确认本次实施非局部麻醉，但未找到麻醉记录单。",
        ),
        (
            "LX0609-059",
            {
                "failure_kind": "antimicrobial_course_documentation_missing",
                "antimicrobials": ["青霉素", "哌拉西林", "头孢他啶"],
                "course_documented": False,
            },
            "已核对抗菌药物青霉素、哌拉西林、头孢他啶，未找到对应的用药病程记录。",
        ),
        (
            "LX0609-075",
            {
                "failure_kind": "invasive_procedure_course_record_missing",
                "ordered_procedures": ["中心静脉置管", "气管插管", "支气管镜"],
                "course_documented": False,
            },
            "已识别有创操作医嘱：中心静脉置管、气管插管、支气管镜；"
            "未找到对应的有创操作病程记录。",
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
            "LX0609-012",
            "请在检查报告出具后24小时内的病程中，记录阳性结果的临床意义、处置措施及后续计划。",
        ),
        (
            "LX0609-015",
            "请在培养报告出具后24小时内的病程中，记录阳性菌结果的临床意义、抗感染调整及后续计划。",
        ),
        (
            "LX0609-017",
            "请逐组核对结果列出的高相似病程，删除机械复制内容，并补充当日病情变化、检查结果和诊疗调整。",
        ),
        (
            "LX0609-025",
            "请在手术记录中补全结果列出的植入物名称、种类、规格/型号、材质、条码及数量等缺项。",
        ),
        (
            "LX0609-029",
            "请为本次已实施手术补充术前小结，并记录术前诊断、手术指征、拟施手术及注意事项。",
        ),
        (
            "LX0609-038",
            "请补充本次麻醉记录单，并核对麻醉方式、用药、生命体征及术中事件记录。",
        ),
        (
            "LX0609-040",
            "请补充本次四级手术的术前多学科讨论记录，并记录参会科室、讨论意见及手术方案。",
        ),
        (
            "LX0609-058",
            "请补充使用特殊级抗菌药物前的专家查房或会诊意见，并记录用药依据。",
        ),
        (
            "LX0609-059",
            "请在病程中补充上述抗菌药物的使用原因、方案调整及疗效观察。",
        ),
        (
            "LX0609-064",
            "请按每台手术分别补齐术后次日起连续3天的病程记录，并记录术者查房情况。",
        ),
        (
            "LX0609-074",
            "请对每次诊断修正或补充记录修改理由及诊断依据。",
        ),
        (
            "LX0609-075",
            "请分别补充上述有创操作的适应证、操作时间、过程、结果及并发症观察。",
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

    assert result["suggestion"] == expected_suggestion
    assert result["suggestion"] != "请按质控要求核对并完善相关记录。"


DEFINED_RULE_IDS = tuple(
    contract.rule_id
    for contract in load_luxian_0609_rule_contracts()
    if contract.phase_status != "pending_definition"
)
CUSTOMER_EXECUTABLE_RULE_IDS = tuple(
    contract.rule_id
    for contract in load_luxian_0609_rule_contracts()
    if contract.rule_id != "LX0609-049"
)


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

    assert result["suggestion"] != "请按质控要求核对并完善相关记录。", rule_id
    assert len(result["suggestion"]) >= 12, rule_id


NOT_APPLICABLE_CASES = (
    ("LX0609-003", "performed_event_absent"),
    ("LX0609-007", "eligibility_not_met"),
    ("LX0609-008", "trigger_absent_complete"),
    ("LX0609-009", "trigger_absent_complete"),
    ("LX0609-011", "trigger_absent_complete"),
    ("LX0609-012", "trigger_absent_complete"),
    ("LX0609-013", "trigger_absent_complete"),
    ("LX0609-014", "trigger_absent_complete"),
    ("LX0609-015", "trigger_absent_complete"),
    ("LX0609-019", "trigger_absent_complete"),
    ("LX0609-020", "trigger_absent_complete"),
    ("LX0609-021", "trigger_absent_complete"),
    ("LX0609-022", "trigger_absent_complete"),
    ("LX0609-025", "performed_event_absent"),
    ("LX0609-027", "trigger_absent_complete"),
    ("LX0609-029", "performed_event_absent"),
    ("LX0609-030", "performed_event_absent"),
    ("LX0609-030", "trigger_absent_complete"),
    ("LX0609-031", "performed_event_absent"),
    ("LX0609-032", "performed_event_absent"),
    ("LX0609-032", "trigger_absent_complete"),
    ("LX0609-033", "performed_event_absent"),
    ("LX0609-034", "performed_event_absent"),
    ("LX0609-035", "performed_event_absent"),
    ("LX0609-036", "performed_event_absent"),
    ("LX0609-037", "eligibility_not_met"),
    ("LX0609-037", "performed_event_absent"),
    ("LX0609-038", "performed_event_absent"),
    ("LX0609-039", "performed_event_absent"),
    ("LX0609-040", "performed_event_absent"),
    ("LX0609-040", "trigger_absent_complete"),
    ("LX0609-042", "eligibility_not_met"),
) + tuple(
    (f"LX0609-{index:03d}", "trigger_absent_complete")
    for index in range(41, 49)
) + (
    ("LX0609-051", "trigger_absent_complete"),
    ("LX0609-058", "trigger_absent_complete"),
    ("LX0609-060", "trigger_absent_complete"),
    ("LX0609-063", "trigger_absent_complete"),
    ("LX0609-070", "trigger_absent_complete"),
    ("LX0609-072", "trigger_absent_complete"),
    ("LX0609-073", "trigger_absent_complete"),
)


@pytest.mark.parametrize(
    ("rule_id", "facts", "expected"),
    [
        (
            "LX0609-009",
            {
                "failure_kind": "critical_daily_record_coverage_satisfied",
                "required_dates": ["2026-06-01", "2026-06-02"],
                "covered_dates": ["2026-06-01", "2026-06-02"],
            },
            "病危观察期 2026-06-01 至 2026-06-02，共 2 天；每日病程 2/2 天，记录完整。本阶段仅核对病危期间每日病程。",
        ),
        (
            "LX0609-012",
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
            "LX0609-020",
            {"execution_record_state": "未发现执行记录"},
            "已找到会诊意见，但未发现对应的请会诊执行记录。",
        ),
        (
            "LX0609-021",
            {"consultation_assessment": "不符合要求"},
            "已核对会诊申请目的，其中未说明具体临床问题、会诊理由或明确目的。",
        ),
        (
            "LX0609-026",
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
            "LX0609-040",
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
            "LX0609-042",
            {
                "failure_kind": "transfusion_consent_incomplete",
                "missing_fields": ["patient_or_agent_signature", "signed_time"],
            },
            "输血知情同意书缺少：患者或代理人签名、精确到分钟的签署时间。",
        ),
        (
            "LX0609-043",
            {
                "failure_kind": "pretransfusion_items_incomplete",
                "missing_items": ["hiv", "syphilis", "alt"],
            },
            "输血前九项缺少：艾滋病病毒抗体、梅毒筛查、谷丙转氨酶。",
        ),
        (
            "LX0609-044",
            {
                "verification_kind": "pretransfusion_assessment_complete",
                "missing_fields": [],
            },
            "输血前评估已记录输血指征、相关检验，以及输血风险、既往输血情况或患者当前情况。",
        ),
        (
            "LX0609-044",
            {
                "failure_kind": "pretransfusion_assessment_missing",
                "missing_fields": ["indication", "laboratory_indicator"],
            },
            "已确认实施输血，但未找到可核对的输血前评估记录。",
        ),
        (
            "LX0609-046",
            {
                "verification_kind": "transfusion_course_record_complete",
                "missing_fields": [],
            },
            "输血病程已记录指征、起止时间、血液成分、输注量、过程观察及反应处理。",
        ),
        (
            "LX0609-047",
            {
                "verification_kind": "posttransfusion_evaluation_complete",
                "transfusion_end_time": "2026-06-05 16:00:00",
                "evaluation_time": "2026-06-06 08:00:00",
                "elapsed_hours": 16.0,
            },
            "已在输血结束后 24 小时内完成效果评价，间隔 16 小时（结束时间 2026-06-05 16:00:00；评价时间 2026-06-06 08:00:00）。",
        ),
        (
            "LX0609-055",
            {
                "verification_kind": "antimicrobial_effect_evaluation_check",
                "antimicrobials": ["美罗培南", "万古霉素"],
                "evaluation_intervals": [],
            },
            "已核对抗菌药物 美罗培南、万古霉素，未找到首次用药后 48～72 小时内的效果评价记录。",
        ),
        (
            "LX0609-061",
            {
                "verification_kind": "discharge_record_timeliness_check",
                "record_time": "2026-06-09 09:00:00",
                "discharge_time": "2026-06-09 10:00:00",
                "actual_interval_hours": -1.0,
            },
            "出院记录于出院前 1 小时完成（记录时间 2026-06-09 09:00:00；出院时间 2026-06-09 10:00:00），符合出院后 24 小时内完成要求。",
        ),
        (
            "LX0609-066",
            {
                "verification_kind": "postoperative_first_course_presence_check",
                "performed_surgery_count": 7,
                "postoperative_first_course_count": 2,
            },
            "已确认实施手术 7 台，找到术后首次病程记录 2 份；尚不能逐台关联，暂无法确认每台手术均有对应记录。",
        ),
        (
            "LX0609-048",
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
        rule_id="LX0609-061",
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
        rule_id="LX0609-020", facts=facts
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
        rule_id="LX0609-020", facts=facts
    )

    assert "1条找到笼统执行痕迹" in finding
    assert "1条暂无法判断" in finding


def test_controlled_finding_does_not_render_untrusted_matrix_values():
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-048",
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


@pytest.mark.parametrize("rule_id", ["LX0609-052", "LX0609-053"])
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
        rule_id="LX0609-037",
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
        rule_id="LX0609-037",
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
            rule_id="LX0609-001",
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
            rule_id="LX0609-001",
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


def test_rule_009_candidate_scope_gap_has_rule_and_reason_specific_message() -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-009",
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
            rule_id="LX0609-054",
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
            rule_id="LX0609-033",
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
        rule_id="LX0609-033",
        facts=facts,
    ) == expected


def test_lx0609_012_non_explicit_positive_has_customer_readable_gap_explanation():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-012",
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
    ("reason_code", "expected_evidence"),
    [
        ("authoritative_time_missing", "缺少本次住院的评价截止日期或有效出院时间"),
        ("authoritative_time_conflict", "存在先后冲突"),
        ("evaluation_window_not_mature", "尚未满 24 小时"),
    ],
)
@pytest.mark.parametrize(
    "rule_id",
    ("LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"),
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
    ("rule_id", "expected_finding", "expected_evidence"),
    [
        (
            "LX0609-013",
            "暂无法核对病理结果是否记入手术记录或病程",
            "病理最终诊断",
        ),
        (
            "LX0609-019",
            "暂无法核对病理取材记录",
            "病理申请或报告来源",
        ),
        (
            "LX0609-020",
            "暂无法核对会诊意见是否具有对应执行记录",
            "后续病程执行记录",
        ),
        (
            "LX0609-021",
            "暂无法核对会诊申请目的是否明确",
            "具体临床问题、会诊理由",
        ),
        (
            "LX0609-022",
            "暂无法核对会诊意见是否明确",
            "明确诊疗意见",
        ),
        (
            "LX0609-026",
            "暂无法核对化疗记录与医嘱是否一致",
            "药名、剂量、用法、时间",
        ),
        (
            "LX0609-027",
            "暂无法核对恶性肿瘤出院治疗计划",
            "恶性肿瘤诊断依据",
        ),
        (
            "LX0609-042",
            "暂无法完整核对输血知情同意书",
            "患者或代理人签名",
        ),
        (
            "LX0609-043",
            "暂无法完整核对输血前九项检查",
            "乙肝五项",
        ),
        (
            "LX0609-046",
            "暂无法完整核对输血病程记录",
            "输血原因、起止时间",
        ),
        (
            "LX0609-047",
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
    trusted = get_luxian_0609_rule("LX0609-001")
    result = render_luxian_0609_customer_result(
        decision=_reduced(CustomerFinalState.COMPLIANT),
    )

    assert trusted is not None
    assert result["rule_id"] == result["rule_code"] == "LX0609-001"
    assert result["rule_name"] == trusted["name"]
    assert result["rule_version"] == trusted["rule_version"]


@pytest.mark.parametrize(
    ("rule_id", "expected_finding"),
    [
        ("LX0609-001", "已确认入院记录在入院后 24 小时内完成。"),
        ("LX0609-009", "已核对病危期间的查房记录，未发现应记录日期缺失。"),
        ("LX0609-032", "已确认本次手术具备手术安全核查表。"),
        ("LX0609-043", "已核对输血前常规检查，所需项目完整。"),
        ("LX0609-048", "已核对术中输血相关记录，未发现文书间内容不一致。"),
        ("LX0609-049", "已核对输血医嘱与收费记录，未发现不一致。"),
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
            rule_id="LX0609-037",
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
    assert "LX0609-036" in result["evidence"]


def test_lx018_compliant_result_uses_controlled_criterion_values():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-018",
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
            rule_id="LX0609-018",
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


def test_data_gap_uses_unknown_criterion_label_to_name_missing_data():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-018",
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
        ("LX0609-010", "CT/MRI"),
        ("LX0609-017", "病程记录"),
        ("LX0609-023", "会诊意见"),
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
        rule_id="LX0609-001",
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
