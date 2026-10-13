from __future__ import annotations

import pytest

from app.services.luxian_0609.customer_remediation import (
    ACTIVE_FORMAL_RULE_IDS,
    PENDING_RULE_IDS,
    build_customer_remediation_suggestion,
)
from app.services.luxian_0609.customer_renderer import (
    render_luxian_0609_customer_result,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import (
    reduce_luxian_0609_rule_decision,
)
from app.services.luxian_0609.customer_renderer import _RULE_NON_COMPLIANT_MESSAGES
from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master


# 2026 手册新增、由 customer_renderer 专门渲染不合规建议的规则（2026-10-12）。
HANDBOOK_RENDERED_RULE_IDS = frozenset({
    "LX0609-04-01-04",
    "LX0609-04-01-05",
    "LX0609-06-01-01",
    "LX0609-06-01-03",
    "LX0609-06-02-01",
    "LX0609-06-03-02",
    "LX0609-09-01-02",
})
SNAPSHOT_HASH = "a" * 64
FACT_REF = "b" * 64


def test_every_active_non_compliant_rule_has_structured_action() -> None:
    # 正式范围以规则总表为准：active 与 pending 必须无交集且完整覆盖 86 条（2026-10-12），
    # 避免硬编码数量掩盖规则丢失或分区遗漏。
    master_rule_ids = tuple(entry.rule_id for entry in load_luxian_0609_rule_master())
    assert len(master_rule_ids) == 86
    assert len(master_rule_ids) == len(set(master_rule_ids))
    assert set(ACTIVE_FORMAL_RULE_IDS).isdisjoint(PENDING_RULE_IDS)
    assert set(ACTIVE_FORMAL_RULE_IDS) | set(PENDING_RULE_IDS) == set(master_rule_ids)
    assert len(ACTIVE_FORMAL_RULE_IDS) + len(PENDING_RULE_IDS) == 86

    for rule_id in ACTIVE_FORMAL_RULE_IDS:
        suggestion = build_customer_remediation_suggestion(
            rule_id=rule_id,
            status="non_compliant",
            reason_code="requirement_violated",
        )

        if rule_id in HANDBOOK_RENDERED_RULE_IDS:
            # 2026 手册新增规则由客户渲染层按裁决事实给出专门建议，不走四段式模板。
            assert not suggestion, rule_id
            assert _RULE_NON_COMPLIANT_MESSAGES[rule_id][2], rule_id
            continue
        assert suggestion, rule_id
        for section in ("修改对象：", "需要补充：", "推荐写法：", "注意事项："):
            assert section in suggestion, (rule_id, suggestion)
        assert suggestion != "请按质控要求核对并完善相关记录。"


@pytest.mark.parametrize("rule_id", ACTIVE_FORMAL_RULE_IDS)
@pytest.mark.parametrize(
    ("status", "expected"),
    (
        ("data_gap", "确认资料同步完整并补齐关联信息后重新评估"),
        ("evaluation_unknown", "人工核对相关文书与结构化资料"),
        ("technical_error", "本质控点的质控执行链"),
    ),
)
def test_every_active_non_terminal_result_has_safe_action_semantics(
    rule_id: str,
    status: str,
    expected: str,
) -> None:
    suggestion = build_customer_remediation_suggestion(
        rule_id=rule_id,
        status=status,
        reason_code="controlled_test_reason",
    )

    if status == "data_gap" and rule_id in {"LX0609-04-01-01", "LX0609-05-01-02", "LX0609-05-01-03", "LX0609-05-01-06", "LX0609-08-01-01", "LX0609-04-02-07"}:
        assert "重新评估" in suggestion, (rule_id, status, suggestion)
    else:
        assert expected in suggestion, (rule_id, status, suggestion)
    for section in ("修改对象：", "需要补充：", "推荐写法：", "注意事项："):
        assert section in suggestion, (rule_id, status, suggestion)
    if status == "technical_error":
        assert "技术异常不代表病历存在缺陷" in suggestion
        assert "不应要求医务人员据此补写临床记录" in suggestion


@pytest.mark.parametrize("rule_id", PENDING_RULE_IDS)
def test_pending_or_not_executed_rule_has_no_deterministic_remediation(
    rule_id: str,
) -> None:
    assert (
        build_customer_remediation_suggestion(
            rule_id=rule_id,
            status="not_executed",
            reason_code="not_executed",
        )
        == ""
    )
    assert (
        build_customer_remediation_suggestion(
            rule_id=rule_id,
            status="non_compliant",
            reason_code="requirement_violated",
        )
        == ""
    )


@pytest.mark.parametrize("status", ("compliant", "not_applicable", "not_executed"))
def test_non_problem_states_do_not_generate_remediation(status: str) -> None:
    assert (
        build_customer_remediation_suggestion(
            rule_id="LX0609-03-01-03",
            status=status,
        )
        == ""
    )


@pytest.mark.parametrize(
    ("status", "reason_code", "expected"),
    (
        ("data_gap", "required_field_missing", "资料同步完整"),
        ("evaluation_unknown", "semantic_uncertain", "人工核对相关文书与结构化资料"),
        ("technical_error", "execution_failed", "排查数据读取、规则执行或结果保存异常"),
    ),
)
def test_non_terminal_states_have_action_semantics(
    status: str,
    reason_code: str,
    expected: str,
) -> None:
    suggestion = build_customer_remediation_suggestion(
        rule_id="LX0609-03-01-04",
        status=status,
        reason_code=reason_code,
    )

    assert suggestion
    assert expected in suggestion
    assert "修改对象：" in suggestion
    assert "注意事项：" in suggestion


def test_controlled_episode_facts_identify_the_consultations_to_revise() -> None:
    """022 暂停后不再交付逐条会诊定位模板；受控事实仍由执行器产出。"""

    suggestion = build_customer_remediation_suggestion(
        rule_id="LX0609-03-01-03",
        status="non_compliant",
        reason_code="requirement_violated",
        facts={
            "episode_count": 4,
            "episode_results": [
                {"episode_index": 1, "semantic_state": "clear"},
                {
                    "episode_index": 2,
                    "semantic_state": "vague",
                    "record_time": "2026-07-21 10:30:00",
                    "document_title": "会诊记录单",
                },
                {"episode_index": 3, "semantic_state": "clear"},
                {
                    "episode_index": 4,
                    "semantic_state": "missing",
                    "record_time": "2026-07-23 14:15:00",
                    "document_title": "会诊记录单",
                },
            ],
        },
    )

    assert suggestion == ""


def test_non_compliant_consultation_advice_does_not_mix_data_gap_instructions() -> None:
    suggestion = build_customer_remediation_suggestion(
        rule_id="LX0609-03-01-04",
        status="non_compliant",
        reason_code="requirement_violated",
    )

    assert "修改对象：会诊意见执行记录" in suggestion
    assert "请依据本次实际诊疗事实补充" in suggestion
    assert "不要编造未核实事实" in suggestion
    assert "资料不足时应标记待核实" not in suggestion
    assert "不得直接写成已完成" not in suggestion


def test_030_order_only_advice_requires_execution_check_before_record_remediation() -> None:
    suggestion = build_customer_remediation_suggestion(
        rule_id="LX0609-04-02-02",
        status="non_compliant",
        reason_code="required_document_missing",
        facts={
            "failure_kind": "surgery_document_missing",
            "target_document": "surgery_record",
            "surgery_trigger_kind": "surgery_order",
            "surgery_order_confirmed": True,
        },
    )

    assert "请先核对该手术医嘱是否实际执行" in suggestion
    assert "如已实施，请补充对应手术记录" in suggestion
    assert "不得补写未发生的手术" in suggestion
    assert "每台已实施手术" not in suggestion


def test_030_order_only_renderer_does_not_claim_surgery_was_performed() -> None:
    facts = {
        "failure_kind": "surgery_document_missing",
        "target_document": "surgery_record",
        "surgery_trigger_kind": "surgery_order",
        "surgery_order_confirmed": True,
    }
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-04-02-02",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="required_document_missing",
            fact_refs=(FACT_REF,),
            evaluator_version="native-surgery-presence-v1",
        )
    )

    result = render_luxian_0609_customer_result(
        decision=decision,
        safe_customer_display_facts=facts,
    )

    assert result["findings"] == "已开立手术医嘱，但未找到对应手术记录"
    assert "当前仅确认手术医嘱触发" in result["evidence"]
    assert "请先核对该手术医嘱是否实际执行" in result["suggestion"]
    assert "每台已实施手术" not in result["suggestion"]


def test_controlled_missing_fields_are_named_without_echoing_raw_content() -> None:
    suggestion = build_customer_remediation_suggestion(
        rule_id="LX0609-08-01-02",
        status="non_compliant",
        reason_code="requirement_violated",
        facts={"missing_fields": ["dose", "route"]},
    )

    assert "剂量、给药途径" in suggestion
    assert "drug_name" not in suggestion
    assert "原始病历" not in suggestion


@pytest.mark.parametrize("rule_id", ("LX0609-03-01-03", "LX0609-04-02-06", "LX0609-08-01-02"))
def test_unrelated_fact_strings_never_enter_the_remediation(rule_id: str) -> None:
    private_marker = "PRIVATE_PATIENT_ABC_13800138000"
    facts = {
        "death_time": private_marker,
        "diagnosis": private_marker,
        "drug_names": [private_marker],
        "raw_text": private_marker,
        "source_document_id": private_marker,
        "episode_results": [
            {"episode_index": 1, "semantic_state": "vague"},
        ],
        "missing_fields": ["dose", "route"],
    }

    suggestion = build_customer_remediation_suggestion(
        rule_id=rule_id,
        status="non_compliant",
        reason_code="requirement_violated",
        facts=facts,
    )

    assert private_marker not in suggestion
    assert "13800138000" not in suggestion


@pytest.mark.parametrize(
    ("evidence_state", "applicability", "reason_code"),
    (
        (EvidenceState.DATA_GAP, ApplicabilityState.APPLICABLE, "required_field_missing"),
        (EvidenceState.CONFLICT, ApplicabilityState.APPLICABLE, "evidence_conflict"),
        (EvidenceState.TECHNICAL_ERROR, ApplicabilityState.APPLICABLE, "executor_exception"),
    ),
)
def test_renderer_structures_non_terminal_state_actions(
    evidence_state: EvidenceState,
    applicability: ApplicabilityState,
    reason_code: str,
) -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-03-01-04",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=applicability,
            evidence_state=evidence_state,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            fact_refs=(FACT_REF,),
            evaluator_version="native-consultation-v1",
        )
    )

    suggestion = render_luxian_0609_customer_result(decision=decision)["suggestion"]

    assert "修改对象：" in suggestion
    assert "需要补充：" in suggestion
    assert "推荐写法：" in suggestion
    assert "注意事项：" in suggestion
