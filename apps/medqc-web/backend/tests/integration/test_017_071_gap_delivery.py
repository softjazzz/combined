"""017/071合法时间缺口须通过正式Finalizer及隔离SQLite保存读取。"""
from copy import deepcopy
from datetime import datetime
import json

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

from app.services import custom_qc_workspace_service as workspace
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
    validate_luxian_0609_published_customer_display_facts,
)
from app.services.luxian_0609.continuity_result_mapping import (
    safe_continuity_customer_display_facts,
    validate_published_continuity_facts,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows, build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_course_quality_execution import execute_luxian_0609_native_course_quality_rules
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result, validated_customer_explanation,
)

COPY = "LX0609-12-01-02"
HANDOFF = "LX0609-10-01-01"
BODY = "患者持续咳嗽伴活动后气促，双肺呼吸音粗，可闻及湿性啰音，继续抗感染及化痰治疗，复查血常规和胸部影像。"


class NoModel:
    async def generate(self, *args, **kwargs):
        raise AssertionError("资料缺口及确定性对照不得调用模型")


async def _execute(rule, rows):
    def reader(**kwargs):
        source = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source, rows=rows.get(source, []), truncated=False, limit_rows=100,
        )
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-07-05T00:00:00+08:00", row_reader=reader,
    )
    common = dict(
        rule_ids=(rule,), decision_rule_ids=(rule,), llm_client=NoModel(),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    if rule == COPY:
        execution = await execute_luxian_0609_native_course_quality_rules(
            **common, institute_id="I", patient_id="P", visit_id="V", source_schema=None,
            wrapper_rules=[get_luxian_0609_rule(rule)], evidence_payload=None,
        )
    else:
        execution = await execute_luxian_0609_native_extended_document_rules(**common)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    result = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert execution.llm_call_count == 0
    return result


def _roundtrip(result, tmp_path):
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "native-result.sqlite").as_posix()
    engine = create_engine(url)
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    try:
        with Session(engine) as db:
            store.replace_for_job(
                db,
                job_row={"id": "J", "created_by": "reviewer", "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                })},
                items=[{**result, "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}],
                now=datetime(2026, 10, 7), projection_key="gap-test-key",
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="gap-test-key"),
            )
            db.commit()
        # 关闭写Session与引擎，再由新引擎、新Session经过正式读取校验。
        engine.dispose()
        engine = create_engine(url)
        with Session(engine) as db:
            loaded = store.load_selected(
                db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            )["items"][0]
        for key in ("status", "reason_code", "customer_display_facts", "missing_fields", "suggestion"):
            assert loaded.get(key) == result.get(key), key
        expected = envelope_item_from_rule_result(result, hmac_key="gap-test-key")
        assert loaded["evidence"] == expected["evidence"]
        for key in ("is_compliant", "criterion_results", "findings"):
            assert loaded.get(key) == expected.get(key), key
        api = workspace.project_customer_safe_result_item(loaded, hmac_key="gap-test-key")
        assert api.get("customer_display_facts") == result.get("customer_display_facts")
        return loaded
    finally:
        engine.dispose()


def _copy_rows(timed_count, include_missing):
    rows = [
        {"document_id": f"C{day}", "record_time": f"2026-07-0{day} 10:00:00", "record_content": BODY}
        for day in range(1, timed_count + 1)
    ]
    if include_missing:
        rows.append({"document_id": "MISSING", "record_content": BODY})
    return {"daily_course_record": rows}


@pytest.mark.asyncio
@pytest.mark.parametrize("timed_count", [0, 1])
async def test_017_missing_time_gap_roundtrips_without_comparison_facts(timed_count, tmp_path):
    result = await _execute(COPY, _copy_rows(timed_count, True))
    assert (result["status"], result["reason_code"]) == ("data_gap", "required_field_missing")
    assert not result.get("customer_display_facts")
    validated_customer_explanation(result, rule_id=COPY, status=result["status"])
    _roundtrip(result, tmp_path)


@pytest.mark.asyncio
@pytest.mark.parametrize("include_missing", [False, True])
async def test_017_proven_copy_survives_other_missing_time_record(include_missing, tmp_path):
    result = await _execute(COPY, _copy_rows(2, include_missing))
    assert result["status"] == "non_compliant"
    assert result["customer_display_facts"]["copy_similarity"] == 1
    _roundtrip(result, tmp_path)


@pytest.mark.parametrize("raw", [None, {}])
def test_017_legacy_gap_without_facts_keeps_none(raw):
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id=COPY, raw=raw, status="data_gap", reason_code="required_field_missing",
    ) is None


@pytest.mark.parametrize("status,reason,raw", [
    ("compliant", "requirement_satisfied", None),
    ("non_compliant", "threshold_exceeded", None),
    ("data_gap", "invented_reason", None),
    ("data_gap", "required_field_missing", {"copy_similarity": 1}),
    ("data_gap", "required_field_missing", {"source_document_refs": []}),
])
def test_017_gap_exception_rejects_wrong_state_reason_or_nonempty_partial_facts(status, reason, raw):
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=COPY, raw=raw, status=status, reason_code=reason,
        )


def _handoff_rows(count, missing_role=None, late=False):
    rows = {"inpat_nondrug_order": [], "handoff_record": [], "handover_record": []}
    for position in range(count):
        day = position * 2 + 2
        change = f"2026-07-0{day} 08:00:00"
        rows["inpat_nondrug_order"].append({
            "document_id": f"O{day}", "order_name": "经治医师变更",
            "order_time": change, "order_status": "新开",
        })
        rows["handoff_record"].append({
            "document_id": f"F{day}", "shift_time": change,
            "record_time": None if position == 0 and missing_role == "handoff" else f"2026-07-0{day} 07:50:00",
        })
        rows["handover_record"].append({
            "document_id": f"R{day}", "shift_time": change,
            "record_time": None if position == 0 and missing_role == "handover" else f"2026-07-0{day + 1} 08:00:0{1 if late else 0}",
        })
    return rows


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("missing_role", ["handoff", "handover"])
async def test_071_single_and_multiple_change_time_gap_roundtrip(count, missing_role, tmp_path):
    result = await _execute(HANDOFF, _handoff_rows(count, missing_role))
    assert (result["status"], result["reason_code"]) == ("data_gap", "authoritative_time_missing")
    facts = result["customer_display_facts"]
    assert facts["failure_kind"] == "physician_handoff_record_time_missing"
    assert facts["change_event_count"] == count
    assert facts[f"missing_{missing_role}_time_count"] == 1
    _roundtrip(result, tmp_path)


@pytest.mark.asyncio
@pytest.mark.parametrize("count,late", [(1, False), (2, False), (1, True)])
async def test_071_time_boundary_and_existing_multi_event_facts_roundtrip(count, late, tmp_path):
    result = await _execute(HANDOFF, _handoff_rows(count, late=late))
    assert result["status"] == ("non_compliant" if late else "compliant")
    _roundtrip(result, tmp_path)


def _missing_time_facts():
    return {
        "failure_kind": "physician_handoff_record_time_missing", "change_event_count": 1,
        "handoff_record_count": 1, "missing_handoff_time_count": 0,
        "handover_record_count": 1, "missing_handover_time_count": 1,
        "handover_threshold_hours": 24,
    }


@pytest.mark.parametrize("changes", [
    {"change_event_count": 0}, {"change_event_count": True},
    {"missing_handover_time_count": 2}, {"missing_handover_time_count": -1},
    {"handover_record_count": 0}, {"missing_handover_time_count": 0},
    {"missing_handoff_time_count": 2}, {"handover_threshold_hours": 48},
])
def test_071_missing_time_fact_count_contract_still_rejects_contradictions(changes):
    raw = {**_missing_time_facts(), **changes}
    assert safe_continuity_customer_display_facts(rule_id=HANDOFF, raw=raw) is None
    assert validate_published_continuity_facts(rule_id=HANDOFF, raw=raw) == (False, None)


def test_071_published_gap_rejects_forged_extra_fields_and_keeps_legacy_multi_event_shape():
    raw = _missing_time_facts()
    raw["change_event_count"] = 2
    assert validate_published_continuity_facts(rule_id=HANDOFF, raw=raw) == (True, raw)
    forged = deepcopy(raw)
    forged["source_document_refs"] = ["forged"]
    assert validate_published_continuity_facts(rule_id=HANDOFF, raw=forged) == (False, None)
