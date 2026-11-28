"""供给未知只能阻断依赖缺失的结论；真实本地执行器，无模型。"""
import pytest
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session


def session(rule, rows, scope=True):
    def read(source_key, **kwargs):
        return SnapshotSourceRows.create(source_key=source_key, rows=rows.get(source_key, ()),
            truncated=False, limit_rows=100,
            material_scope={"can_judge_clinical_absence":False} if scope and source_key == "daily_course_record" else None)
    return build_luxian_0609_evidence_read_session(selected_rule_ids=(rule,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-01-10T08:00:00+08:00", evaluation_as_of_date="2026-01-10",
        row_reader=read, additional_source_keys=("inpat_registration", "admission_record", "daily_course_record", "senior_course_record"))


@pytest.mark.parametrize("within", [False, True])
def test_first_round_unknown_scope_preserves_positive_evidence(within):
    from test_luxian_0609_native_basic_timeliness import _reduce_typed_basic
    rule = "LX0609-02-01-01"
    rows = {"inpat_registration":[{"admission_datetime":"2026-01-01 08:00:00"}]}
    if within:
        rows["daily_course_record"] = [{"document_id":"A", "document_title":"主治医师查房记录", "record_time":"2026-01-02 08:00:00", "record_content":"主治医师查房，患者病情平稳。"}]
    _, reduced = _reduce_typed_basic(session(rule, rows), (rule,))
    assert reduced[0].final_state.value == ("compliant" if within else "data_gap")


def test_007_missing_interval_needs_supply_proof():
    from app.services.luxian_0609.course_quality.rule_007 import evaluate_rule_007_typed
    rule = "LX0609-02-01-03"
    value = session(rule, {"inpat_registration":[{"admission_datetime":"2026-01-01 08:00:00"}]})
    decision = evaluate_rule_007_typed(snapshot=value.snapshot, materials=value.materials)
    assert decision.qc_direction.value == "unknown"
    assert decision.evidence_state.value == "data_gap"


def test_handbook_supply_scope_keeps_reliable_rows():
    from app.services.luxian_0609.handbook_exam_lab import _read_source
    value = session("LX0609-02-01-01", {"daily_course_record":[{"document_id":"D", "record_content":"独立可靠合成事实"}]})
    rows = _read_source(value.snapshot, value.materials, "daily_course_record")
    assert len(rows.rows) == 1
    assert rows.complete is False


@pytest.mark.parametrize("rule,severity", [("LX0609-02-01-04","serious"),("LX0609-02-01-05","critical")])
def test_severity_missing_days_require_supply_proof(rule, severity):
    from app.services.luxian_0609.course_quality.rules_008_009 import _rule_008_009_decision
    from app.services.luxian_0609.source_evidence_reader import CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY
    rows = {CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY:[{"severity":severity,"prescribed_datetime":"2026-01-01 08:00:00"}],
            "inpat_registration":[{"admission_datetime":"2026-01-01 08:00:00"}]}
    value = session(rule, rows)
    decision = _rule_008_009_decision(rule_id=rule, snapshot=value.snapshot, materials=value.materials)
    assert decision.qc_direction.value == "unknown"
    assert decision.evidence_state.value == "data_gap"


def test_emergency_exception_absence_is_unknown_with_unproven_daily_supply():
    from app.services.luxian_0609.native_surgery_document_execution import _course_records_emergency_intervention
    value = session("LX0609-02-01-01", {})
    assert _course_records_emergency_intervention(value.materials) is None


def test_typed_chemotherapy_source_preserves_rows_and_supply_scope():
    from app.services.luxian_0609.native_tumor_pathology_execution import _load_typed_source
    value = session("LX0609-02-01-01", {"daily_course_record":[{"record_content":"独立可靠的合成正文"}]})
    source = _load_typed_source(source_key="daily_course_record", evidence_snapshot=value.snapshot, evidence_materials=value.materials)
    assert len(source.rows) == 1
    assert source.permits_absence is False


def test_posttransfusion_missing_evaluation_needs_scope_but_positive_remains():
    from app.services.luxian_0609.native_transfusion_execution import _programmatic_047_assessment
    docs = {"bloodtrans_record":[{"document_id":"T", "record_content":"2026-06-05 16:00:00输血结束。"}],
            "daily_course_record":[], "__evaluation_horizon_rows__":[{"horizon_datetime":"2026-06-10 12:00:00"}],
            "__material_scope__":{"daily_course_record":{"can_judge_clinical_absence":False}}}
    assert _programmatic_047_assessment(docs).status == "data_gap"
    docs["daily_course_record"] = [{"document_title":"输血后评价记录", "record_content":"输血后复查血红蛋白较前改善，未见输血不良反应。", "record_time":"2026-06-05 16:20:00"}]
    assert _programmatic_047_assessment(docs).status == "compliant"


def test_consultation_candidate_scope_keeps_positive_rows():
    from datetime import date
    from app.services.luxian_0609.native_consultation_episode_execution import _candidate_documents, _StayWindow
    value = session("LX0609-02-01-01", {"daily_course_record":[{"document_id":"D","record_time":"2026-01-02 08:00:00", "record_content":"按会诊意见执行。"}]})
    result = _candidate_documents(institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        evidence_materials=value.materials, evidence_snapshot=value.snapshot, stay_window=_StayWindow(date(2026,1,1),date(2026,1,10)))
    assert any(row.source_key == "daily_course_record" for row in result.candidates)
    assert "daily_course_record" in result.source_incomplete_keys
    assert "daily_course_record" not in result.source_complete_keys


def test_exam_typed_source_keeps_scope_separate_from_query_state():
    from app.services.luxian_0609.native_exam_lab_execution import _typed_source
    value = session("LX0609-02-01-01", {})
    result = _typed_source(source_key="daily_course_record", snapshot=value.snapshot, materials=value.materials)
    assert result.state == "empty"
    assert result.permits_absence is False


@pytest.mark.parametrize("present", [False, True])
def test_predischarge_scope_only_blocks_absence(present):
    from datetime import datetime
    from app.services.luxian_0609.extended_document.discharge_course import evaluate_predischarge_course_presence
    row = {"document_id":"D", "record_time":"2026-01-10 08:00:00", "record_content":"病情稳定，拟出院。"}
    result = evaluate_predischarge_course_presence(death_state="absent", death_error="", registration_error="", discharge_error="",
        discharge_time=datetime(2026,1,10,12), daily_error="", senior_error="", daily_rows=[row] if present else [], senior_rows=[],
        clinical_body_states={("daily_course_record",0):"present"}, daily_scope_complete=False)
    assert result.final_state == ("compliant" if present else "data_gap")


def test_handoff_cannot_infer_absence_from_partial_signatures():
    from app.services.luxian_0609.extended_document.physician_handoff import evaluate_physician_handoff
    result = evaluate_physician_handoff(physician_change_rows=[], physician_change_error="", nondrug_order_rows=[], nondrug_order_error="",
        daily_course_rows=[], daily_course_error="", handoff_rows=[], handoff_error="", handover_rows=[], handover_error="", daily_scope_complete=False)
    assert result.final_state == "data_gap"


def test_antimicrobial_missing_reason_requires_daily_scope():
    from datetime import datetime
    from types import SimpleNamespace
    from app.services.luxian_0609.extended_document.antimicrobial_family import _order_reason_rule_outcome
    event = SimpleNamespace(event_id="E", kind="start", antimicrobial="合成药物", time=datetime(2026,1,1), window_end=datetime(2026,1,2), orders=())
    result = _order_reason_rule_outcome(rule_id="LX0609-05-01-02", events=[event], time_missing_names=[], documents={}, per_event={},
        untimed=frozenset(), extraction=SimpleNamespace(state="ready", facts=[]), lab_master_rows=[], lab_item_rows=[], pathogen_sources_complete=True,
        evaluation_horizon=datetime(2026,1,10), horizon_error="", daily_scope_complete=False)
    assert result[0] == "data_gap"


@pytest.mark.parametrize("hours,expected", [(30,"data_gap"),(49,"non_compliant")])
def test_prophylaxis_scope_preserves_independent_duration_violation(hours, expected):
    from datetime import datetime, timedelta
    from test_luxian_0609_surgery_text_fact_contract import _event, SurgeryTextProjection, SurgeryTimeCandidate, SurgeryEventFact
    from app.services.luxian_0609.native_surgery_gate_execution import _surgery_text_outcome
    start = datetime(2026,1,1,8)
    projection = SurgeryTextProjection(context="synthetic", time_candidates={
        "T001":SurgeryTimeCandidate(start,"daily_course_record","text_datetime_candidate","S07-01"),
        "T002":SurgeryTimeCandidate(start+timedelta(hours=hours),"daily_course_record","text_datetime_candidate","S07-01")}, document_refs=frozenset({"S07-01"}))
    fact = SurgeryEventFact(**_event(evidence_refs=["S07-01"], antimicrobial_intent="prophylactic", start_time_ref="T001", start_time_role="actual_administration",
        end_time_ref="T002", end_time_role="actual_stop", interval_scope="prophylactic_segment", special_extension_reason="not_documented"))
    result = _surgery_text_outcome(rule_id="LX0609-05-01-01", facts=[fact], projection=projection, materials=session("LX0609-02-01-01",{}).materials)
    assert result.status == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["empty", "declared", "structured"])
async def test_diagnosis_change_missing_course_requires_supply_proof(kind):
    from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
    rule = "LX0609-12-02-01"
    rows = {}
    if kind == "declared":
        rows["admission_record_diagnosis"] = [{"document_id":"A", "diagnosis_type":"修正诊断", "diagnosis_name":"合成新诊断"}]
    elif kind == "structured":
        rows["diagnosis"] = [{"document_id":str(i), "diagnosis_datetime":f"2026-01-0{i} 08:00:00", "diagnosis_name":name, "diagnosis_type":"诊断", "diagnosis_no":"1"} for i,name in [(1,"合成旧诊断"),(2,"合成新诊断")]]
    value = session(rule, rows)
    result = await execute_luxian_0609_native_extended_document_rules(rule_ids=[rule], decision_rule_ids=[rule], evidence_snapshot=value.snapshot, evidence_materials=value.materials)
    assert result.decisions[0].evidence_state.value == "data_gap"
    assert result.decisions[0].qc_direction.value == "unknown"


@pytest.mark.parametrize("hours,expected", [(None,"data_gap"),(24,"compliant"),(80,"data_gap")])
def test_programmatic_round_scope_preserves_positive(hours, expected):
    from datetime import datetime, timedelta
    from app.services.luxian_0609_programmatic_rules import _evaluate_round
    docs = [] if hours is None else [{"title":"主治医师查房", "content":"主治医师查房", "authored_at":str(datetime(2026,1,1)+timedelta(hours=hours))}]
    result = _evaluate_round({"rule_id":"LX0609-02-01-01"}, {"admission_time":"2026-01-01 00:00:00", "documents":{"daily_course_record":docs}, "material_scope":{"daily_course_record":{"can_judge_clinical_absence":False}}}, role="attending", hours=48)
    assert result["status"] == expected


@pytest.mark.parametrize("meaning,other_valid,expected", [(None,False,"data_gap"),("cancelled",False,"data_gap"),("valid",False,"compliant"),(None,True,"compliant")])
def test_approved_status_is_required_for_real_first_round_positive(meaning,other_valid,expected):
    from copy import deepcopy
    from test_daily_material_projection import synthetic_manifest
    from test_luxian_0609_native_basic_timeliness import _reduce_typed_basic
    from app.services import daily_material_projection as projection
    value = synthetic_manifest()
    item = value["items"][0]
    # Fixed d7dc output permits selected/rule_usable despite UNCONFIRMED status semantics.
    item.update(source_status="Save",state="SUPPLEMENT_CONFIRMED",record_time="2026-01-02 08:00:00",title="主治医师查房记录",body="主治医师查房，患者病情平稳。",field_availability={"source_status":"UNCONFIRMED" if meaning is None else "SEMANTICS_APPROVED"})
    value["business_binding"] = {"policy":{"status_rules":[] if meaning is None else [["clinical","Save",meaning]]}}
    if other_valid:
        other = deepcopy(item)
        other.update(source_status="Approved",version_id="other",record_identity="other-record")
        value["business_binding"]["policy"]["status_rules"].append(["clinical","Approved","valid"])
        value["items"].append(other)
    rows = {"inpat_registration":[{"admission_datetime":"2026-01-01 08:00:00"}],"daily_course_record":projection.project_rows(value)}
    _, reduced = _reduce_typed_basic(session("LX0609-02-01-01",rows),("LX0609-02-01-01",))
    assert reduced[0].final_state.value == expected


@pytest.mark.parametrize("scope_complete,within,missing_time,expected", [
    (True, False, False, ("non_compliant", "course_record_interval_over_72h")),
    (False, False, False, ("data_gap", "course_time_source_unavailable")),
    (False, True, False, ("compliant", "course_record_interval_within_72h")),
    (False, False, True, ("data_gap", "authoritative_course_time_incomplete")),
])
@pytest.mark.parametrize("use_materials", [False, True])
def test_007_legacy_supply_scope_preserves_original_judgment(monkeypatch, scope_complete, within, missing_time, expected, use_materials):
    from types import SimpleNamespace
    from app.services.luxian_0609.course_quality import rule_007

    rows = [{"record_time": "2026-01-01 08:00:00", "record_content": "病情稳定"},
            {"record_time": "2026-01-03 08:00:00" if within else "2026-01-05 08:00:00", "record_content": "病情稳定"}]
    if missing_time:
        rows.append({"record_content": "病情稳定，继续观察"})
    def read(source_key, **kwargs):
        return rows if source_key == "daily_course_record" else []
    monkeypatch.setattr(rule_007.daily_material_projection, "permits_absence", lambda source_key: scope_complete)
    materials = SimpleNamespace(rows=read, permits_absence=lambda source_key: scope_complete) if use_materials else None
    result = rule_007.evaluate_rule_007_legacy(
        serious_state="absent", critical_state="absent", institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, unstable_order_reader=lambda **kwargs: False, source_row_reader=read,
        source_row_limit=lambda source_key: 100, evidence_materials=materials)
    assert (result.status, result.reason_code) == expected
