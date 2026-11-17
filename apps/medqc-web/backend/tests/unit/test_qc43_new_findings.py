"""Claude待复现项：仅以可证明的原始事件和来源标签构造反例。"""
from datetime import datetime
from app.services.luxian_0609.malignancy_fact import build_stage_malignancy_sources
from app.services.luxian_0609 import native_surgery_gate_execution as surgery
from test_luxian_0609_native_surgery_gate_execution import _typed_003_session
from app.services.luxian_0609.course_quality.rule_018 import _lx018_primary_diagnosis_resolution


def test_other_confirmed_operation_cannot_be_hidden_by_one_timely_record():
    session = _typed_003_session(
        surgery_document_id="s1", surgery_begin_time=datetime(2026, 1, 1, 1),
        surgery_time=datetime(2026, 1, 1, 8), record_time=datetime(2026, 1, 1, 9),
        original_anesthesia_rows=tuple({"document_id": f"a{day}", "record_content":
            f"本次手术已完成。手术开始时间：2026-01-0{day} 01:00:00+08:00 手术结束时间：2026-01-0{day} 08:00:00+08:00"}
            for day in (1, 2)), evaluation_as_of_date="2026-01-05",
    )
    decision = surgery._typed_003_decision(snapshot=session.snapshot, materials=session.materials)
    assert decision.qc_direction.value != "satisfied"
    assert decision.reason_code == "association_failed"


def test_explicit_homepage_diagnosis_does_not_override_original_discharge_document():
    original = {"diagnosis_name": "肺炎", "document_id": "original-discharge"}
    sources = build_stage_malignancy_sources(
        visit_stage="discharged", admission_state="empty", admission_rows=(),
        diagnosis_state="available", diagnosis_rows=({"diagnosis_source": "病案首页", "diagnosis_name": "肺癌"},),
        discharge_diagnosis_state="available", discharge_diagnosis_rows=(original,),
        pathology_state="empty", pathology_rows=(),
    )
    assert sources[0].source_key == "discharge_record_diagnosis"
    assert sources[0].rows == (original,)


def test_homepage_admission_diagnosis_does_not_override_original_document():
    result = _lx018_primary_diagnosis_resolution({
        "diagnosis": [{"diagnosis_type": "入院诊断", "diagnosis_source": "首页", "diagnosis_no": 1, "diagnosis_name": "肺癌"}],
        "admission_record_diagnosis": [{"diagnosis_type": "入院诊断", "diagnosis_no": 1, "diagnosis_name": "肺炎"}],
    })
    assert result == ("available", "肺炎")


def test_execution_metadata_matches_actual_model_use():
    from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
    contracts = {c.rule_id: c for c in load_luxian_0609_rule_contracts()}
    for rule, count in (("LX0609-05-01-06", 1), ("LX0609-08-01-02", 2), ("LX0609-08-02-02", 1)):
        assert contracts[rule].decision_authority == "program_then_optional_llm"
        assert contracts[rule].max_llm_calls_per_rule == count
    assert contracts["LX0609-12-01-02"].decision_authority == "program_only"
