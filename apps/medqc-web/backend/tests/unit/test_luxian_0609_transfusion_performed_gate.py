from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows, build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable

RULES = ("LX0609-07-01-01", "LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02", "LX0609-07-03-01")
CANCELLED = "患者原计划输血，经再次评估后取消，本次住院未实施输血。"
PERFORMED = "患者开始输注去白悬浮红细胞2U，输注过程平稳，无输血反应。"


def _execute(contents=(), *, structured=False, failed=False):
    def reader(**kwargs):
        source = kwargs["source_key"]
        if failed and source == "mr_bloodtrans":
            raise SourceEvidenceUnavailable()
        rows = []
        if source == "bloodtrans_record":
            rows = [{"document_id": f"R{i}", "record_content": text, "record_time": "2026-07-16 16:20:00"} for i, text in enumerate(contents)]
        elif source == "mr_bloodtrans" and structured:
            rows = [{"document_id": "S1", "transfution_datetime": datetime(2026, 7, 16, 12)}]
        elif source == "blood_application":
            rows = [{"application_id": "A1", "hemoglobin": "114", "transfuse_variety": "红细胞", "transfuse_volume": "2", "transfuse_volume_unit": "U"}]
        return SnapshotSourceRows.create(source_key=source, rows=rows, truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=RULES, institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-07-17T12:00:00+08:00", row_reader=reader,
    )
    result = asyncio.run(transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=RULES, wrapper_rules=[{"rule_id": rule} for rule in RULES], evidence_payload={},
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=None,
        evidence_materials=session.materials, evidence_snapshot=session.snapshot, decision_rule_ids=RULES,
    ))
    return {item.rule_id: reduce_luxian_0609_rule_decision(item).final_state.value for item in result.decisions}


@pytest.mark.parametrize("text", [CANCELLED, "原计划给予红细胞输注治疗，现已取消输血。", "本次住院未进行输血，继续观察复查血常规。"])
def test_explicit_nonperformance_cannot_trigger_confirmed_defect(text):
    assert set(_execute([text]).values()) == {"data_gap"}


def test_application_only_is_not_applicable():
    assert set(_execute().values()) == {"not_applicable"}


@pytest.mark.parametrize("contents", [[PERFORMED], [CANCELLED, PERFORMED]])
def test_actual_transfusion_and_no_reaction_are_preserved(contents):
    assert _execute(contents)["LX0609-07-02-01"] == "compliant"


def test_structured_performance_is_not_erased_by_cancelled_text():
    assert _execute([CANCELLED], structured=True)["LX0609-07-02-02"] == "non_compliant"


def test_failed_source_is_not_absence():
    assert set(_execute(failed=True).values()) == {"data_gap"}


def test_unknown_short_text_is_not_absence():
    assert set(_execute(["输血记录：待完善"]).values()) == {"data_gap"}


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
    assert _execute(["未输血前已完成相关检查。" + PERFORMED])["LX0609-07-02-01"] == "compliant"


@pytest.mark.parametrize("reaction", ["没有输血反应", "未发生输血反应", "没有输血不良反应", "未见输血反应", "无输血反应"])
def test_negative_reaction_does_not_negate_actual_transfusion(reaction):
    content = "本次输注红细胞2U，输注过程平稳，" + reaction + "。"
    assert _execute([content])["LX0609-07-02-02"] == "non_compliant"
