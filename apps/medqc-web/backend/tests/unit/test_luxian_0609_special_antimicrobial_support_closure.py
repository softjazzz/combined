"""TP-D04：具名其他药专家支持不得绑定到目标药；只用合成正式交付链。"""
from __future__ import annotations

import pytest

from special_antimicrobial_test_support import FrozenSpecialApprovalClient

from app.services.luxian_0609 import native_extended_document_execution as native
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys

RULE = "LX0609-05-01-06"
# 在执行前独立冻结；首例逐字段继承既有 expert_other_drug，不按执行器结果生成预期。
# 会诊只使用真实投影 document_id/record_time/record_content；不补造 related_order_id。
CASES = [{'id': 'expert_other_drug',
  'rows': {'inpat_drug_order': [{'document_id': 'synthetic-order',
                                 'order_id': 'synthetic-O1',
                                 'generic_name': '美罗培南',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 08:00:00',
                                 'prescribed_datetime': '2026-04-01 08:00:00'}],
           'consultation_record': [{'document_id': 'synthetic-note',
                                    'record_time': '2026-04-01 07:00:00',
                                    'record_content': '专家会诊，建议万古霉素抗感染。'}],
           'evaluation_context.horizon': [{'horizon_date': '2026-04-08',
                                           'basis': 'evaluation_as_of'}]},
  'oracle': {'status': 'non_compliant',
             'reason_code': 'required_document_missing',
             'support_before_use': False,
             'unmatched_special_antimicrobials': ['美罗培南'],
             'association_ambiguous': False,
             'evidence_document_ids': ['synthetic-order'],
             'forbidden_findings': ['晚于该时间', '时间前或同刻找到专家支持记录']},
  'rationale': '其他药物专家支持不能证明本药已获支持'},
 {'id': 'same_drug_before',
  'rows': {'inpat_drug_order': [{'document_id': 'synthetic-order',
                                 'order_id': 'synthetic-O1',
                                 'generic_name': '美罗培南',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 08:00:00',
                                 'prescribed_datetime': '2026-04-01 08:00:00'}],
           'consultation_record': [{'document_id': 'synthetic-note',
                                    'record_time': '2026-04-01 07:00:00',
                                    'record_content': '专家会诊，建议美罗培南抗感染。'}],
           'evaluation_context.horizon': [{'horizon_date': '2026-04-08',
                                           'basis': 'evaluation_as_of'}]},
  'oracle': {'status': 'compliant',
             'reason_code': 'requirement_satisfied',
             'support_before_use': True,
             'unmatched_special_antimicrobials': [],
             'association_ambiguous': False,
             'evidence_document_ids': ['synthetic-order', 'synthetic-note'],
             'forbidden_findings': []},
  'rationale': '沿用已冻结同药启用前/同刻/晚于启用/缺时间合同。'},
 {'id': 'same_drug_same_instant',
  'rows': {'inpat_drug_order': [{'document_id': 'synthetic-order',
                                 'order_id': 'synthetic-O1',
                                 'generic_name': '美罗培南',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 08:00:00',
                                 'prescribed_datetime': '2026-04-01 08:00:00'}],
           'consultation_record': [{'document_id': 'synthetic-note',
                                    'record_time': '2026-04-01 08:00:00',
                                    'record_content': '专家会诊，建议美罗培南抗感染。'}],
           'evaluation_context.horizon': [{'horizon_date': '2026-04-08',
                                           'basis': 'evaluation_as_of'}]},
  'oracle': {'status': 'compliant',
             'reason_code': 'requirement_satisfied',
             'support_before_use': True,
             'unmatched_special_antimicrobials': [],
             'association_ambiguous': False,
             'evidence_document_ids': ['synthetic-order', 'synthetic-note'],
             'forbidden_findings': []},
  'rationale': '沿用已冻结同药启用前/同刻/晚于启用/缺时间合同。'},
 {'id': 'same_drug_late',
  'rows': {'inpat_drug_order': [{'document_id': 'synthetic-order',
                                 'order_id': 'synthetic-O1',
                                 'generic_name': '美罗培南',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 08:00:00',
                                 'prescribed_datetime': '2026-04-01 08:00:00'}],
           # 用户口径（2026-10-17）：启用后 24 小时内补办算合规；“晚于启用”用例取 25 小时后。
           'consultation_record': [{'document_id': 'synthetic-note',
                                    'record_time': '2026-04-02 09:00:00',
                                    'record_content': '专家会诊，建议美罗培南抗感染。'}],
           'evaluation_context.horizon': [{'horizon_date': '2026-04-08',
                                           'basis': 'evaluation_as_of'}]},
  'oracle': {'status': 'non_compliant',
             'reason_code': 'requirement_violated',
             'support_before_use': False,
             'unmatched_special_antimicrobials': ['美罗培南'],
             'association_ambiguous': False,
             'evidence_document_ids': ['synthetic-order', 'synthetic-note'],
             'forbidden_findings': []},
  'rationale': '沿用已冻结同药启用前/同刻/晚于启用/缺时间合同。'},
 {'id': 'same_drug_missing_time',
  'rows': {'inpat_drug_order': [{'document_id': 'synthetic-order',
                                 'order_id': 'synthetic-O1',
                                 'generic_name': '美罗培南',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 08:00:00',
                                 'prescribed_datetime': '2026-04-01 08:00:00'}],
           'consultation_record': [{'document_id': 'synthetic-note',
                                    'record_time': '',
                                    'record_content': '专家会诊，建议美罗培南抗感染。'}],
           'evaluation_context.horizon': [{'horizon_date': '2026-04-08',
                                           'basis': 'evaluation_as_of'}]},
  'oracle': {'status': 'data_gap',
             'reason_code': 'authoritative_time_missing',
             'support_before_use': False,
             'unmatched_special_antimicrobials': ['美罗培南'],
             'association_ambiguous': False,
             'evidence_document_ids': ['synthetic-order', 'synthetic-note'],
             'forbidden_findings': []},
  'rationale': '沿用已冻结同药启用前/同刻/晚于启用/缺时间合同。'},
 {'id': 'anonymous_single_event',
  'rows': {'inpat_drug_order': [{'document_id': 'synthetic-order',
                                 'order_id': 'synthetic-O1',
                                 'generic_name': '美罗培南',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 08:00:00',
                                 'prescribed_datetime': '2026-04-01 08:00:00'}],
           'consultation_record': [{'document_id': 'synthetic-note',
                                    'record_time': '2026-04-01 07:00:00',
                                    'record_content': '感染专家会诊同意特殊级抗菌药物方案。'}],
           'evaluation_context.horizon': [{'horizon_date': '2026-04-08',
                                           'basis': 'evaluation_as_of'}]},
  'oracle': {'status': 'compliant',
             'reason_code': 'requirement_satisfied',
             'support_before_use': True,
             'unmatched_special_antimicrobials': [],
             'association_ambiguous': False,
             'evidence_document_ids': ['synthetic-order', 'synthetic-note'],
             'forbidden_findings': []},
  'rationale': '现有单事件匿名支持合同保护，不另立业务政策。'},
 {'id': 'multiple_named_each_supported',
  'rows': {'inpat_drug_order': [{'document_id': 'synthetic-order',
                                 'order_id': 'synthetic-O1',
                                 'generic_name': '美罗培南',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 08:00:00',
                                 'prescribed_datetime': '2026-04-01 08:00:00'},
                                {'document_id': 'synthetic-order-V',
                                 'order_id': 'synthetic-O2',
                                 'generic_name': '万古霉素',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 09:00:00',
                                 'prescribed_datetime': '2026-04-01 09:00:00'}],
           'consultation_record': [{'document_id': 'synthetic-note-M',
                                    'record_time': '2026-04-01 07:00:00',
                                    'record_content': '专家会诊，建议美罗培南抗感染。'},
                                   {'document_id': 'synthetic-note-V',
                                    'record_time': '2026-04-01 08:30:00',
                                    'record_content': '专家会诊，建议万古霉素抗感染。'}],
           'evaluation_context.horizon': [{'horizon_date': '2026-04-08',
                                           'basis': 'evaluation_as_of'}]},
  'oracle': {'status': 'compliant',
             'reason_code': 'requirement_satisfied',
             'support_before_use': True,
             'unmatched_special_antimicrobials': [],
             'association_ambiguous': False,
             'evidence_document_ids': ['synthetic-order',
                                       'synthetic-order-V',
                                       'synthetic-note-M',
                                       'synthetic-note-V'],
             'forbidden_findings': []},
  'rationale': '两个明确不同药事件各有本药启用前支持，不相互借支持。'},
 {'id': 'multiple_only_meropenem_supported',
  'rows': {'inpat_drug_order': [{'document_id': 'synthetic-order',
                                 'order_id': 'synthetic-O1',
                                 'generic_name': '美罗培南',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 08:00:00',
                                 'prescribed_datetime': '2026-04-01 08:00:00'},
                                {'document_id': 'synthetic-order-V',
                                 'order_id': 'synthetic-O2',
                                 'generic_name': '万古霉素',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 09:00:00',
                                 'prescribed_datetime': '2026-04-01 09:00:00'}],
           'consultation_record': [{'document_id': 'synthetic-note-M',
                                    'record_time': '2026-04-01 07:00:00',
                                    'record_content': '专家会诊，建议美罗培南抗感染。'}],
           'evaluation_context.horizon': [{'horizon_date': '2026-04-08',
                                           'basis': 'evaluation_as_of'}]},
  'oracle': {'status': 'non_compliant',
             'reason_code': 'required_document_missing',
             'support_before_use': False,
             'unmatched_special_antimicrobials': ['万古霉素'],
             'association_ambiguous': False,
             'evidence_document_ids': ['synthetic-order', 'synthetic-order-V', 'synthetic-note-M'],
             'forbidden_findings': []},
  'rationale': '美罗培南支持不能覆盖另一万古霉素事件。'},
 {'id': 'anonymous_multiple_events',
  'rows': {'inpat_drug_order': [{'document_id': 'synthetic-order',
                                 'order_id': 'synthetic-O1',
                                 'generic_name': '美罗培南',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 08:00:00',
                                 'prescribed_datetime': '2026-04-01 08:00:00'},
                                {'document_id': 'synthetic-order-V',
                                 'order_id': 'synthetic-O2',
                                 'generic_name': '万古霉素',
                                 'drug_apply_method': '静脉滴注',
                                 'order_status': '已执行',
                                 'planned_start_datetime': '2026-04-01 09:00:00',
                                 'prescribed_datetime': '2026-04-01 09:00:00'}],
           'consultation_record': [{'document_id': 'synthetic-note',
                                    'record_time': '2026-04-01 07:00:00',
                                    'record_content': '感染专家会诊同意特殊级抗菌药物方案。'}],
           'evaluation_context.horizon': [{'horizon_date': '2026-04-08',
                                           'basis': 'evaluation_as_of'}]},
  'oracle': {'status': 'data_gap',
             'reason_code': 'association_failed',
             'support_before_use': False,
             'unmatched_special_antimicrobials': [],
             'association_ambiguous': True,
             'evidence_document_ids': ['synthetic-order', 'synthetic-order-V'],
             'forbidden_findings': []},
  'rationale': '现有多事件匿名支持归属不明合同保护，不能猜测覆盖全部。'}]


async def _run(rows):
    def read(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE,), institute_id="synthetic-I", patient_id="synthetic-P",
        visit_id="synthetic-V", source_schema=None, created_at="2026-10-08T10:00:00+08:00",
        row_reader=read,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("extended_document",), selected_rule_ids=(RULE,),
        ),
    )
    execution = await native.execute_luxian_0609_native_extended_document_rules(
        rule_ids=(RULE,), decision_rule_ids=(RULE,), llm_client=FrozenSpecialApprovalClient(),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(RULE,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(execution.customer_display_facts)[RULE],
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    # 用户口径（2026-10-21）：058 改为医嘱驱动，专家是否同意由模型抽取，受控桩每例至多一次调用。
    assert execution.llm_call_count in {0, 1}
    assert execution.total_tokens == execution.llm_call_count * 15
    assert execution.results == ()
    assert len(execution.decisions) == 1
    return execution, reduced, final


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True], ids=["original", "reversed"])
@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
async def test_expert_support_is_bound_to_the_correct_special_drug_through_finalizer(case, reverse):
    rows = {key: tuple(reversed(value)) if reverse else tuple(value) for key, value in case["rows"].items()}
    execution, reduced, final = await _run(rows)
    oracle = case["oracle"]
    assert execution.decisions[0].reason_code == reduced.reason_code == oracle["reason_code"]
    assert reduced.final_state.value == final["status"] == oracle["status"]
    raw_facts = dict(execution.customer_display_facts)[RULE]
    facts = final["customer_display_facts"]
    assert facts == raw_facts
    assert facts["verification_kind"] == "special_antimicrobial_expert_support_check"
    assert set(facts["special_antimicrobials"]) == {row["generic_name"] for row in rows["inpat_drug_order"]}
    for key in ("support_before_use", "association_ambiguous"):
        assert facts[key] is oracle[key]
    assert set(facts["unmatched_special_antimicrobials"]) == set(oracle["unmatched_special_antimicrobials"])
    expected_sources = {
        (source, row["document_id"])
        for source in ("inpat_drug_order", "consultation_record")
        for row in rows[source]
        if row["document_id"] in oracle["evidence_document_ids"]
    }
    assert {(ref["source_type"], ref["source_document_id"]) for ref in final["customer_evidence"]} == expected_sources
    for forbidden in oracle["forbidden_findings"]:
        assert forbidden not in final["findings"]
    if oracle["status"] != "compliant":
        assert "继续保持" not in final["suggestion"]
    if oracle["unmatched_special_antimicrobials"]:
        assert all(name in final["findings"] for name in oracle["unmatched_special_antimicrobials"])
