from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from transfusion_order_test_support import (
    OPEN_TRANSFUSION_ORDER, FrozenTransfusionProtocolClient,
)

from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows, build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable

RULES = ("LX0609-07-01-01", "LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02", "LX0609-07-03-01")
CANCELLED = "患者原计划输血，经再次评估后取消，本次住院未实施输血。"
PERFORMED = "患者开始输注去白悬浮红细胞2U，输注过程平稳，无输血反应。"


ORDER_RULES = ("LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02")
LEGACY_PERFORMED_RULES = ("LX0609-07-01-01", "LX0609-07-03-01")


def _execute(contents=(), *, structured=False, failed=False, orders=False, course_kind="unknown"):
    # 标签由各病例显式冻结；不使用关键字从正文计算模型判定。
    client = FrozenTransfusionProtocolClient(course_labels={text: ("not_record" if text == CANCELLED else course_kind) for text in contents})
    def reader(**kwargs):
        source = kwargs["source_key"]
        if failed and source == "mr_bloodtrans":
            raise SourceEvidenceUnavailable()
        rows = []
        if source == "bloodtrans_record":
            rows = [{"document_id": f"R{i}", "record_content": text, "record_time": "2026-07-16 16:20:00"} for i, text in enumerate(contents)]
        elif source == "mr_bloodtrans" and structured:
            rows = [{"document_id": "S1", "transfution_datetime": datetime(2026, 7, 16, 12)}]
        elif source == "inpat_nondrug_order" and orders:
            rows = [dict(OPEN_TRANSFUSION_ORDER)]
        elif source == "blood_application":
            rows = [{"application_id": "A1", "hemoglobin": "114", "transfuse_variety": "红细胞", "transfuse_volume": "2", "transfuse_volume_unit": "U"}]
        return SnapshotSourceRows.create(source_key=source, rows=rows, truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=RULES, institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-07-17T12:00:00+08:00", row_reader=reader,
    )
    result = asyncio.run(transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=RULES, wrapper_rules=[{"rule_id": rule} for rule in RULES], evidence_payload={},
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_materials=session.materials, evidence_snapshot=session.snapshot, decision_rule_ids=RULES,
    ))
    return {item.rule_id: reduce_luxian_0609_rule_decision(item).final_state.value for item in result.decisions}


@pytest.mark.parametrize("text", [CANCELLED, "原计划给予红细胞输注治疗，现已取消输血。", "本次住院未进行输血，继续观察复查血常规。"])
def test_explicit_nonperformance_cannot_trigger_confirmed_defect(text):
    result = _execute([text])
    assert {result[rule] for rule in ORDER_RULES} == {"not_applicable"}
    assert {result[rule] for rule in LEGACY_PERFORMED_RULES} == {"data_gap"}
    with_order = _execute([text], orders=True, course_kind="not_record")
    assert with_order["LX0609-07-02-01"] == "non_compliant"
    assert with_order["LX0609-07-02-02"] == "data_gap"
    assert {with_order[rule] for rule in LEGACY_PERFORMED_RULES} == {"data_gap"}


def test_application_only_is_not_applicable():
    assert set(_execute().values()) == {"not_applicable"}


@pytest.mark.parametrize("contents", [[PERFORMED], [CANCELLED, PERFORMED]])
def test_actual_transfusion_and_no_reaction_are_preserved(contents):
    assert _execute(contents, orders=True, course_kind="record")["LX0609-07-02-01"] == "compliant"
    assert {_execute(contents)[rule] for rule in ORDER_RULES} == {"not_applicable"}


def test_structured_performance_is_not_erased_by_cancelled_text():
    result = _execute([CANCELLED], structured=True)
    assert {result[rule] for rule in ORDER_RULES} == {"not_applicable"}
    # v2：结构化实际执行不再代替有效专用记录；045缺记录，046资料缺口。
    result = _execute([CANCELLED], structured=True, orders=True, course_kind="not_record")
    assert result["LX0609-07-02-01"] == "non_compliant"
    assert result["LX0609-07-02-02"] == "data_gap"


def test_failed_source_is_not_absence():
    result = _execute(failed=True)
    assert {result[rule] for rule in ORDER_RULES} == {"not_applicable"}
    assert {result[rule] for rule in LEGACY_PERFORMED_RULES} == {"data_gap"}


def test_unknown_short_text_is_not_absence():
    result = _execute(["输血记录：待完善"])
    assert {result[rule] for rule in ORDER_RULES} == {"not_applicable"}
    assert {result[rule] for rule in LEGACY_PERFORMED_RULES} == {"data_gap"}


@pytest.mark.parametrize("content, expected", [(CANCELLED, "data_gap"), (PERFORMED, "present")])
def test_documents_shortcut_checks_nonperformance(monkeypatch, content, expected):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", lambda **kwargs: [
        {"record_content": content}
    ] if kwargs["source_key"] == "bloodtrans_record" else [])
    state = transfusion._performed_source_state(
        documents={"bloodtrans_record": [{"content": content}]}, institute_id="I", patient_id="P",
        visit_id="V", source_schema=None,
    )
    assert state == expected


def test_pretransfusion_context_does_not_negate_completed_transfusion():
    assert _execute(["未输血前已完成相关检查。" + PERFORMED], orders=True, course_kind="record")["LX0609-07-02-01"] == "compliant"


@pytest.mark.parametrize("reaction", ["没有输血反应", "未发生输血反应", "没有输血不良反应", "未见输血反应", "无输血反应"])
def test_negative_reaction_does_not_negate_actual_transfusion(reaction):
    content = "本次输注红细胞2U，输注过程平稳，" + reaction + "。"
    assert _execute([content], orders=True, course_kind="record")["LX0609-07-02-02"] == "non_compliant"
