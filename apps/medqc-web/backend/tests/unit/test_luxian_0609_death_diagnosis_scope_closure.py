"""063 暂停当前比较；死亡诊断历史事实仍须严格验证，冻结输入不重写。"""

import pytest

from app.services.luxian_0609.discharge_result_mapping import (
    discharge_customer_fact_status_is_valid, safe_discharge_customer_display_facts,
    validate_published_discharge_facts,
)
from app.services.luxian_0609.source_registry import resolve_luxian_0609_decision_support_source_keys
from app.services.luxian_0609.native_extended_document_execution import _discharge_or_death_diagnosis_rows, _death_context
from test_luxian_0609_063_running_scope import pending_execution

RULE = "LX0609-08-01-03"

def diagnosis(name, *, scope="死亡诊断", sequence=1, document="SYN-DEATH"):
    return {"document_id": document, "diagnosis_type": scope,
            "diagnosis_no": sequence, "diagnosis_name": name}


def death_rows(*, written="合成诊断乙", authority="合成诊断甲", death_time="2026-10-01 08:00:00"):
    # DD-S01冻结原反例：不添加正常出院记录，不改变冲突名称或顺序。
    return {"death_record": [{"document_id": "SYN-DEATH", "death_time": death_time}],
            "mr_diagnosis": [{"diagnosis_type": "死亡诊断", "diagnosis_no": 1,
                              "diagnosis_name": authority}],
            "discharge_record_diagnosis": [diagnosis(written)]}


@pytest.fixture(autouse=True)
def sqlite_and_no_network(monkeypatch):
    import httpx
    import socket
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def blocked(*args, **kwargs):
        raise AssertionError("DD-F01合成测试禁止PG、网络和真实模型")

    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite"

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    event.listen(Engine, "before_cursor_execute", sqlite_only)
    yield
    event.remove(Engine, "before_cursor_execute", sqlite_only)


@pytest.mark.parametrize("scope", [None, "", "unknown", 1, [], {}])
def test_public_scope_requires_strict_supported_enum(scope):
    raw = {"verification_kind": "discharge_diagnosis_consistency_check",
           "authoritative_diagnoses": ["合成诊断甲"], "written_diagnoses": ["合成诊断甲"],
           "diagnoses_consistent": True, "order_comparable": True, "diagnosis_scope": scope}
    assert safe_discharge_customer_display_facts(rule_id=RULE, raw=raw) is None
    assert validate_published_discharge_facts(rule_id=RULE, raw=raw) is None


@pytest.mark.parametrize("scope", [None, "death", "discharge"])
def test_old_facts_default_scope_and_new_facts_preserve_strict_status(scope):
    raw = {"verification_kind": "discharge_diagnosis_consistency_check",
           "authoritative_diagnoses": ["合成诊断甲"], "written_diagnoses": ["合成诊断乙"],
           "diagnoses_consistent": False, "order_comparable": True}
    if scope is not None:
        raw["diagnosis_scope"] = scope
    safe = safe_discharge_customer_display_facts(rule_id=RULE, raw=raw)
    assert safe == raw
    assert validate_published_discharge_facts(rule_id=RULE, raw=safe) == safe
    assert discharge_customer_fact_status_is_valid(rule_id=RULE, status="non_compliant", safe_facts=safe)
    assert not discharge_customer_fact_status_is_valid(rule_id=RULE, status="compliant", safe_facts=safe)
    assert not discharge_customer_fact_status_is_valid(rule_id=RULE, status="", safe_facts=safe)


TYPED_DEATH_SCOPE_CASES = [('DD-TD-001', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [], 'inpat_registration': []}, 'compliant'), ('DD-TD-002', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断乙', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [], 'inpat_registration': []}, 'non_compliant'), ('DD-TD-003', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [], 'inpat_registration': [{'patient_status': '在院'}]}, 'data_gap'), ('DD-TD-004', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [], 'inpat_registration': [{'patient_status': '存活', 'discharge_status': '存活'}]}, 'data_gap'), ('DD-TD-005', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}, {'diagnosis_type': '出院诊断', 'diagnosis_no': 2, 'diagnosis_name': '合成诊断乙'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [], 'inpat_registration': []}, 'data_gap'), ('DD-TD-006', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [{'document_id': 'SYN-DEATH-A', 'death_time': '2026-10-01 08:00:00'}, {'document_id': 'SYN-DEATH-B', 'death_time': '2026-10-01 09:00:00'}], 'discharge_record': [], 'inpat_registration': [{'patient_status': '死亡', 'death_datetime': '2026-10-01 08:00:00'}]}, 'compliant'), ('DD-TD-007', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断乙', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [{'document_id': 'SYN-DEATH-A', 'death_time': '2026-10-01 08:00:00'}, {'document_id': 'SYN-DEATH-B', 'death_time': '2026-10-01 09:00:00'}], 'discharge_record': [], 'inpat_registration': [{'patient_status': '死亡', 'death_datetime': '2026-10-01 08:00:00'}]}, 'non_compliant'), ('DD-TD-008', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [{'record_time': '2026-10-01 10:00:00'}], 'inpat_registration': []}, 'compliant')]


@pytest.mark.parametrize("gap", ["scope_conflict", "scope_unknown"])
@pytest.mark.parametrize("change", ["written_field", "chosen_scope", "second_gap", "unknown_gap", "extra_payload"])
def test_scope_gap_fields_and_payload_cannot_forge_a_chosen_scope(gap, change):
    raw = {"verification_kind": "discharge_diagnosis_data_gap", "authoritative_gap": gap, "written_gap": None}
    if change == "written_field":
        raw["authoritative_gap"], raw["written_gap"] = None, gap
    elif change == "chosen_scope":
        raw["diagnosis_scope"] = "death"
    elif change == "second_gap":
        raw["written_gap"] = "diagnoses_missing"
    elif change == "unknown_gap":
        raw["authoritative_gap"] = "invented_scope"
    else:
        raw["internal_source_payload"] = {"patient_name": "合成姓名"}
    assert safe_discharge_customer_display_facts(rule_id=RULE, raw=raw) is None
    assert validate_published_discharge_facts(rule_id=RULE, raw=raw) is None


@pytest.mark.parametrize("gap", ["scope_conflict", "scope_unknown"])
@pytest.mark.parametrize("status", ["", "unknown", "technical_error", "uncertain", "not_executed", "compliant", "non_compliant", "not_applicable"])
def test_scope_gap_cannot_be_published_as_a_determined_or_unknown_status(gap, status):
    from app.services.luxian_0609.canonical_result_finalizer import validate_luxian_0609_published_customer_display_facts

    raw = {"verification_kind": "discharge_diagnosis_data_gap", "authoritative_gap": gap, "written_gap": None}
    assert not discharge_customer_fact_status_is_valid(rule_id=RULE, status=status, safe_facts=raw)
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=RULE, raw=raw, status=status, reason_code="required_field_missing")


def test_063_current_source_contract_has_no_homepage_dependency():
    assert set(resolve_luxian_0609_decision_support_source_keys((RULE,))) == {
        "discharge_record", "inpat_registration", "death_record", "evaluation_context.horizon",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("written", ["合成诊断甲", "合成诊断乙", ""])
@pytest.mark.parametrize("unavailable", [frozenset(), {"mr_diagnosis"}, {"discharge_record_diagnosis"}, {"death_record", "inpat_registration"}])
async def test_current_death_content_cannot_enable_pending_comparison(written, unavailable):
    await pending_execution(death_rows(written=written), unavailable_sources=unavailable)


@pytest.mark.parametrize("scope", ["death", "discharge"])
def test_historical_diagnosis_selection_does_not_mix_terminal_types(scope):
    rows = [diagnosis("死亡侧"), diagnosis("出院侧", scope="出院诊断"), diagnosis("入院侧", scope="入院诊断")]
    assert _discharge_or_death_diagnosis_rows(rows, diagnosis_scope=scope) == (rows[0 if scope == "death" else 1],)


def test_historical_death_context_does_not_invent_terminal_state():
    assert _death_context(registration_rows=[], death_rows=[], discharge_rows=[]) == ("unknown", None)
    assert _death_context(registration_rows=[], death_rows=[{"document_id": "DEATH"}], discharge_rows=[]) == ("present", None)
    assert _death_context(registration_rows=[{"patient_status": "正常出院"}], death_rows=[], discharge_rows=[]) == ("absent", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("case_id,rows,status", TYPED_DEATH_SCOPE_CASES, ids=[case[0] for case in TYPED_DEATH_SCOPE_CASES])
async def test_frozen_historical_death_inputs_now_return_pending_without_rewriting_fixture(case_id, rows, status):
    # 原独立审计的病例、诊断名称和历史结论原样保留；当前候选不再重算它们。
    assert status in {"compliant", "non_compliant", "data_gap"}, case_id
    await pending_execution(rows)


@pytest.mark.parametrize("written,status,reason", [
    ("合成诊断甲", "compliant", "requirement_satisfied"),
    ("合成诊断乙", "non_compliant", "requirement_violated"),
    ("", "data_gap", "required_field_missing"),
])
def test_historical_death_scope_new_engine_roundtrip_preserves_frozen_result(written, status, reason, tmp_path):
    """冻结历史结论经独立引擎读回及客户投影，不经暂停算法重算。"""
    from datetime import datetime
    import json
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

    facts = (
        {"verification_kind": "discharge_diagnosis_data_gap", "diagnosis_scope": "death",
         "authoritative_gap": None, "written_gap": "diagnoses_missing"}
        if status == "data_gap" else
        {"verification_kind": "discharge_diagnosis_consistency_check", "diagnosis_scope": "death",
         "authoritative_diagnoses": ["合成诊断甲"], "written_diagnoses": [written],
         "diagnoses_consistent": status == "compliant", "order_comparable": True}
    )
    assert validate_published_discharge_facts(rule_id=RULE, raw=facts) == facts
    assert discharge_customer_fact_status_is_valid(rule_id=RULE, status=status, safe_facts=facts)
    historical = {"rule_id": RULE, "rule_code": RULE, "rule_version": "2026-06-09",
                  "status": status, "result_status": status, "display_status": status,
                  "reason_code": reason, "is_compliant": None if status == "data_gap" else status == "compliant",
                  "customer_display_facts": facts, "conclusion": "死亡诊断历史核对结果。",
                  "suggestion": "保留原始死亡诊断和核对结论。",
                  "evidence": [{"source_type": "death_record", "source_document_id": "SYN-DEATH"}]}
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "historical-death-diagnosis.sqlite").as_posix()
    engine = create_engine(url)
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    projection_key = "synthetic-historical-death-key"
    try:
        with Session(engine) as write_db:
            store.replace_for_job(write_db,
                job_row={"id": "J", "created_by": "synthetic-reviewer", "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})},
                items=[{**historical, "record_id": "V", "visit_id": "V", "patient_id": "P", "institute_id": "I"}],
                now=datetime(2026, 10, 8, 12),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key=projection_key),
                projection_key=projection_key)
            write_db.commit()
        engine.dispose()
        engine = create_engine(url)
        with Session(engine) as read_db:
            saved = store.load_selected(read_db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")["items"][0]
            for key in ("status", "reason_code", "rule_version", "customer_display_facts", "conclusion", "suggestion"):
                assert saved[key] == historical[key]
            assert saved["customer_display_facts"]["diagnosis_scope"] == "death"
            assert saved["record_ref"].startswith("rec_")
            assert saved["evidence"][0]["source_ref"].startswith("src_")
            assert "source_document_id" not in saved["evidence"][0]
            api = workspace.project_customer_safe_result_item(saved, hmac_key=projection_key)
            assert api["customer_display_facts"] == facts
            assert api["evidence"] == saved["evidence"]
            assert "event_key" not in json.dumps(api, ensure_ascii=False)
            assert validate_published_discharge_facts(rule_id=RULE, raw=api["customer_display_facts"]) == facts
    finally:
        engine.dispose()
