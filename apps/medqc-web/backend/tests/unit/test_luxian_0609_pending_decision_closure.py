"""LX0609 剩余限制与产品口径收口（用户口径 2026-11-08）。

只用合成材料、固定应答；关键场景经 Provider/Native/Binding/Finalizer 并以内存 SQLite 保存读回。
"""

import asyncio
from datetime import datetime

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from tests.unit.test_luxian_0609_cross_event_identity import (
    DONE_TEXT,
    _ScriptedInvasiveModel,
    _course,
    _session as _cross_session,
    _surgery_master,
    _surgery_presence_final,
    _surgery_record,
    _two_day_rows,
)
from tests.unit.test_luxian_0609_death_record_timeliness import saved_roundtrip


@pytest.fixture(autouse=True)
def isolated_freeze(monkeypatch, tmp_path):
    for key in (
        "LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR", "LUXIAN_0609_OPINION_FREEZE_DIR",
        "LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR", "LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR",
    ):
        monkeypatch.setenv(key, str(tmp_path))


def _saved(final):
    loaded = saved_roundtrip(final)
    assert (loaded["status"], loaded["reason_code"]) == (final["status"], final["reason_code"])
    assert loaded.get("customer_display_facts") == final.get("customer_display_facts")
    return loaded


# ---------- 1. 10-03-01：书写日期不是实施日期 ----------
async def _075_final(rows, plan):
    from app.services.luxian_0609.native_extended_document_execution import (
        execute_luxian_0609_native_extended_document_rules,
    )

    rule = "LX0609-10-03-01"
    session = _cross_session(rule, rows, "extended_document", final=True)
    native = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, llm_client=_ScriptedInvasiveModel(plan),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(native.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )


FIRST = f"2026年6月1日{DONE_TEXT}"


@pytest.mark.asyncio
@pytest.mark.parametrize("second_text,expected", [
    (f"{DONE_TEXT}，过程顺利。", "data_gap"),
    (f"补记操作经过：{DONE_TEXT}，过程顺利。", "data_gap"),
    (f"今日再次{DONE_TEXT}，过程顺利。", "compliant"),
], ids=["no_date_written_same_day", "supplement_without_date", "today_wording"])
async def test_075_write_date_alone_does_not_prove_overlapping_occurrence(second_text, expected):
    rows = _two_day_rows(_course("D1", 1, 15, FIRST + "。"), _course("D2", 2, 15, second_text))
    final = await _075_final(rows, {
        "2026-06-01": (lambda r: r["time"].startswith("2026-06-01"), FIRST),
        "2026-06-02": (lambda r: r["time"].startswith("2026-06-02"), DONE_TEXT),
    })
    assert _saved(final)["status"] == expected


# ---------- 2. 04-02-02：记录须能唯一关联到台次 ----------
def _two_surgeries(*records):
    return _surgery_presence_final({
        "mr_surgery": [_surgery_master(2, 8), _surgery_master(2, 20, surgeon="乙")],
        "surgery_record": list(records),
    })


def test_030_record_spanning_both_surgeries_proves_neither():
    spanning = {**_surgery_record(2, 8), "document_id": "SPAN",
                "surgery_begin_time": "2026-06-02 08:30:00+08:00",
                "surgery_end_time": "2026-06-02 21:00:00+08:00"}
    final = _two_surgeries(_surgery_record(2, 8), spanning)
    assert (_saved(final)["status"], final["reason_code"]) == ("data_gap", "association_failed")


def test_030_small_time_difference_with_overlapping_span_is_associated():
    early = {**_surgery_record(2, 8), "surgery_begin_time": "2026-06-02 07:55:00+08:00"}
    final = _two_surgeries(early, _surgery_record(2, 20))
    assert final["reason_code"] != "association_failed"
    assert _saved(final)["status"] == "compliant"


# ---------- 3. 08-01-03：死亡记录多版本 ----------
async def _death_result(death_records, diagnoses):
    from tests.unit.test_luxian_0609_death_diagnosis_scope_closure import evaluate

    rows = {
        "death_record": death_records,
        "mr_diagnosis": [{"diagnosis_type": "死亡诊断", "diagnosis_no": 1, "diagnosis_name": "合成诊断甲"}],
        "discharge_record_diagnosis": diagnoses,
    }
    *_ignored, result = await evaluate(rows)
    return result


def _death(doc, record_time):
    return {"document_id": doc, "death_time": "2026-10-01 08:00:00", "record_time": record_time}


def _dx(doc, name):
    return {"document_id": doc, "diagnosis_type": "死亡诊断", "diagnosis_no": 1, "diagnosis_name": name}


@pytest.mark.asyncio
@pytest.mark.parametrize("old,new,expected", [
    ("合成诊断乙", "合成诊断甲", "compliant"),
    ("合成诊断甲", "合成诊断乙", "non_compliant"),
], ids=["latest_matches", "latest_differs"])
async def test_063_death_uses_latest_death_record(old, new, expected):
    result = await _death_result(
        [_death("DEATH-1", "2026-10-01 09:00:00"), _death("DEATH-2", "2026-10-01 12:00:00")],
        [_dx("DEATH-1", old), _dx("DEATH-2", new)],
    )
    assert result["status"] == expected
    assert result["customer_display_facts"]["written_diagnoses"] == [new]


@pytest.mark.asyncio
async def test_063_death_same_time_conflicting_versions_is_gap():
    result = await _death_result(
        [_death("DEATH-1", "2026-10-01 09:00:00"), _death("DEATH-2", "2026-10-01 09:00:00")],
        [_dx("DEATH-1", "合成诊断甲"), _dx("DEATH-2", "合成诊断乙")],
    )
    assert result["status"] == "data_gap"
    assert result["customer_display_facts"]["written_gap"] == "version_conflict"


@pytest.mark.asyncio
async def test_063_death_latest_without_diagnoses_does_not_borrow_older():
    result = await _death_result(
        [_death("DEATH-1", "2026-10-01 09:00:00"), _death("DEATH-2", "2026-10-01 12:00:00")],
        [_dx("DEATH-1", "合成诊断甲")],
    )
    assert result["status"] == "data_gap"
    assert result["customer_display_facts"]["written_gap"] == "diagnoses_missing"


# ---------- 6. 04-01-01：未来手术计划不立即报缺术前小结 ----------
SURGERY = "腹腔镜下阑尾切除术"


def _029_final(rows, *, day):
    from app.services.luxian_0609.native_surgery_document_execution import (
        execute_luxian_0609_native_surgery_document_rules,
    )

    rule = "LX0609-04-01-01"
    frozen = {"institute_id": "I", "patient_id": "P", "visit_id": "V", "record_scene": "running",
              "evaluation_horizon": day, "evaluation_basis": "task_frozen_date", "resolution_status": "resolved"}

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=tuple(rows.get(key, ())),
                                         truncated=False, limit_rows=500)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at=day + "T12:00:00+08:00", row_reader=reader,
        evaluation_as_of_date=day, evaluation_horizon_policy="frozen_task_date",
        evaluation_horizon_snapshot=frozen,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("surgery_document",), selected_rule_ids=(rule,)
        ),
    )
    native = asyncio.run(execute_luxian_0609_native_surgery_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), wrapper_rules=[{"rule_id": rule}],
        evidence_payload={}, llm_client=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    ))
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    return finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(native.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )


def _order(day, status="新开"):
    return {"order_id": f"O{day}", "order_type": "手术", "order_name": SURGERY, "order_status": status,
            "planned_start_datetime": f"2026-06-{day:02d} 08:00:00"}


def test_029_future_planned_surgery_is_not_yet_due():
    final = _029_final({"inpat_nondrug_order": [_order(12)]}, day="2026-06-10")
    assert (_saved(final)["status"], final["reason_code"]) == ("not_applicable", "evaluation_window_not_mature")


@pytest.mark.parametrize("status", ["新开", "停止"])
def test_029_past_plan_without_performance_evidence_is_unresolved(status):
    final = _029_final({"inpat_nondrug_order": [_order(5, status)]}, day="2026-06-10")
    assert (_saved(final)["status"], final["reason_code"]) == ("data_gap", "source_readiness_unproven")
    assert "手术实施情况" in final["findings"]


def test_029_performed_surgery_without_summary_is_still_defect():
    record = {"document_id": "R1", "surgery_name": SURGERY, "surgeon": "甲", "surgeon_sign": "甲",
              "surgery_begin_time": "2026-06-02 08:00:00+08:00",
              "surgery_end_time": "2026-06-02 10:00:00+08:00", "record_time": "2026-06-02 11:00:00",
              "surgery_process": "手术经过：顺利。", "record_content": "手术经过：顺利。"}
    final = _029_final({"surgery_record": [record], "inpat_nondrug_order": [_order(12)]}, day="2026-06-10")
    assert _saved(final)["status"] == "non_compliant"
