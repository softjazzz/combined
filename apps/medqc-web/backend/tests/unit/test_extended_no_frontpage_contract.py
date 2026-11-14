"""新取材会话的原始文书与历史来源隔离，全部使用合成数据。"""
from copy import deepcopy

import pytest

from app.services.luxian_0609 import native_extended_document_execution as extended
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_material import build_material_document_refs
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows, SourceEvidenceUnavailable
from test_luxian_0609_tc02_performed_event_contract import CASES, PerformanceFake


def session(rule, rows, *, unavailable=(), truncated=()):
    def read(**kwargs):
        key = kwargs["source_key"]
        assert key != "mr" and not key.startswith("mr_"), key
        if key in unavailable:
            raise SourceEvidenceUnavailable("synthetic_missing_source")
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, ()),
                                         truncated=key in truncated, limit_rows=50)

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="synthetic-I", patient_id="synthetic-P", visit_id="synthetic-V",
        source_schema=None, created_at="2026-06-10T12:00:00+08:00", row_reader=read,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("extended_document",), selected_rule_ids=(rule,)),
    )


async def evaluate(rule, rows, *, client=None, unavailable=(), truncated=()):
    evidence = session(rule, rows, unavailable=unavailable, truncated=truncated)
    execution = await extended.execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=evidence.snapshot,
        evidence_materials=evidence.materials, llm_client=client,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule,), snapshot=evidence.snapshot,
        evidence_materials=evidence.materials,
    )[0]
    return execution, reduced, evidence


@pytest.mark.asyncio
async def test_070_dedicated_original_refs_do_not_require_unused_course_sources():
    rows = deepcopy(CASES[0]["rows"])
    execution, reduced, _ = await evaluate("LX0609-07-01-03", rows,
        client=PerformanceFake("performed"), unavailable=("daily_course_record", "senior_course_record"))
    assert reduced.final_state.value == "compliant"
    reference = build_material_document_refs("bloodtrans_record", rows["bloodtrans_record"])[0]
    assert reference in execution.decisions[0].fact_refs


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["unavailable", "truncated"])
async def test_070_real_source_gap_does_not_become_absent(kind):
    _, reduced, _ = await evaluate("LX0609-07-01-03", {"bloodtrans_record": ({"document_id": "B1"},)}, **{kind: ("bloodtrans_record",)})
    assert reduced.final_state.value == "data_gap"


@pytest.mark.asyncio
async def test_070_open_order_without_implementation_remains_unconfirmed():
    _, reduced, _ = await evaluate("LX0609-07-01-03", {
        "inpat_nondrug_order": ({"order_name": "输注红细胞", "order_status": "开立"},),
    })
    assert reduced.final_state.value == "data_gap"
    assert reduced.reason_code == "positive_assertion_not_explicit"


@pytest.mark.asyncio
async def test_075_empty_original_orders_ignore_contradicting_frontpage():
    _, reduced, _ = await evaluate("LX0609-10-03-01", {
        "mr_surgery": ({"surgery_code": "37.2200", "surgery_name": "冠状动脉造影术"},),
    })
    assert reduced.final_state.value == "not_applicable"


@pytest.mark.asyncio
async def test_075_original_order_failure_is_not_absence():
    _, reduced, _ = await evaluate("LX0609-10-03-01", {}, unavailable=("inpat_nondrug_order",))
    assert reduced.final_state.value == "data_gap"


@pytest.mark.asyncio
async def test_066_applicable_but_unbuildable_event_cannot_be_compliant(monkeypatch):
    rows = {"surgery_record": ({"document_id": "S1", "surgery_name": "合成手术",
        "record_content": "已完成合成手术", "surgery_begin_time": "2026-06-01 09:00:00+08:00",
        "surgery_end_time": "2026-06-01 10:00:00+08:00"},)}
    monkeypatch.setattr(extended, "_postoperative_surgery_events", lambda **_: ())
    _, reduced, _ = await evaluate("LX0609-04-05-03", rows)
    assert reduced.final_state.value == "data_gap"
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_043_typed_original_transfusion_events_survive_internal_projection():
    from app.services.luxian_0609 import native_transfusion_execution as native
    from transfusion_order_test_support import FrozenTransfusionProtocolClient

    rule = "LX0609-07-01-01"
    names = ("乙肝表面抗原", "乙肝表面抗体", "乙肝e抗原", "乙肝e抗体", "乙肝核心抗体",
             "丙肝抗体", "HIV抗体", "梅毒抗体", "ABO血型鉴定", "Rh血型鉴定", "不规则抗体筛查")
    rows = {"bloodtrans_record": ({"document_id": "B1", "record_time": "2026-06-02 14:00:00",
                "record_content": "悬浮红细胞2U输注完毕。"},),
            "labtest_item_report": tuple({"item_name": name, "result": "阴性", "report_datetime": "2026-06-02 10:00:00"}
                                         for name in names)}
    evidence = session(rule, rows)
    client = FrozenTransfusionProtocolClient(default_course_label="record", performance_state="performed")
    execution = await native.execute_luxian_0609_native_transfusion_rules(
        rule_ids=(rule,), wrapper_rules=[], evidence_payload=None,
        institute_id="synthetic-I", patient_id="synthetic-P", visit_id="synthetic-V", source_schema=None,
        llm_client=client, evidence_snapshot=evidence.snapshot, evidence_materials=evidence.materials,
        decision_rule_ids=(rule,),
    )
    [reduced] = bind_and_reduce_luxian_0609_rule_decisions(decisions=execution.decisions,
        expected_rule_ids=(rule,), snapshot=evidence.snapshot, evidence_materials=evidence.materials)
    assert reduced.final_state.value == "compliant"
    facts = dict(execution.customer_display_facts)[rule]
    assert facts["transfusion_time"] == "2026-06-02 14:00:00"
    assert len(facts["checked_items"]) == 11


@pytest.mark.asyncio
async def test_070_original_row_identity_tampering_fails_closed():
    from dataclasses import replace
    from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore

    rule = "LX0609-07-01-03"
    evidence = session(rule, deepcopy(CASES[0]["rows"]))
    with pytest.raises(ValueError, match="material rows do not match snapshot identity"):
        Luxian0609EvidenceMaterialStore.create(snapshot=evidence.snapshot,
            sources={**evidence.materials._sources, "bloodtrans_record": SnapshotSourceRows.create(
                source_key="bloodtrans_record", rows=({"document_id": "forged", "record_content": "伪造实施"},),
                truncated=False, limit_rows=50)})
    mismatched = replace(evidence.materials, snapshot_hash="a" * 64)
    with pytest.raises(ValueError):
        await extended.execute_luxian_0609_native_extended_document_rules(
            rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=evidence.snapshot,
            evidence_materials=mismatched, llm_client=PerformanceFake("performed"))


@pytest.mark.asyncio
async def test_discharge_course_current_sources_and_historical_frontpage_facts():
    from app.services.luxian_0609.extended_document import discharge_course_content as course
    from app.services.luxian_0609.discharge_result_mapping import validate_published_discharge_facts
    from test_luxian_0609_discharge_course_content import Client, TEXT

    evidence = session(course.RULE_ID, {"discharge_record": ({"document_id": "D1", "treatment_course": TEXT},)})
    outcome = await course.evaluate_discharge_course_content(snapshot=evidence.snapshot,
        materials=evidence.materials, llm_client=Client())
    assert outcome.state == "compliant"
    saved = deepcopy(dict(outcome.facts))
    # 旧发布协议可继续读取首页事实；它不参与新执行来源清单。
    saved.pop("review", None)
    saved["documents"].append({"document_index": 2, "source": "mr_bloodtrans",
        "document_ref": "a" * 64, "text_length": 5})
    assert validate_published_discharge_facts(rule_id=course.RULE_ID, raw=saved) == saved
    assert "mr_bloodtrans" not in course.SOURCES
