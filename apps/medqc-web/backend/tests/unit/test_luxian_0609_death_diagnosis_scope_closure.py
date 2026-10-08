"""DD-F01：死亡诊断独立核对，未知终末状态不能伪造缺陷。"""

from datetime import datetime
import json

import pytest

from app.services.luxian_0609.discharge_result_mapping import (
    discharge_customer_fact_status_is_valid,
    safe_discharge_customer_display_facts,
    validate_published_discharge_facts,
)
from app.services.luxian_0609.source_registry import resolve_luxian_0609_decision_support_source_keys
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from test_luxian_0609_native_extended_document_execution import _evaluate_selected

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


class ForbiddenModel:
    async def generate(self, *args, **kwargs):
        raise AssertionError("063不得调用模型")


async def evaluate(rows, *, unavailable_sources=frozenset()):
    snapshot, materials, execution, reduced = await _evaluate_selected(
        (RULE,), rows, unavailable_sources=unavailable_sources, llm_client=ForbiddenModel(),
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": RULE}], execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    assert execution.llm_call_count == execution.total_tokens == 0
    assert len(canonical) == len(reduced) == 1
    assert canonical[0]["status"] == reduced[0].final_state.value
    return snapshot, materials, execution, reduced[0], canonical[0]


def test_063_single_rule_source_contract_reads_death_context():
    assert set(resolve_luxian_0609_decision_support_source_keys((RULE,))) == {
        "discharge_record", "mr_diagnosis", "inpat_registration", "death_record",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("written,status", [("合成诊断乙", "non_compliant"), ("合成诊断甲", "compliant")])
async def test_frozen_death_only_case_reaches_consistency_and_correct_customer_scope(written, status):
    snapshot, materials, execution, reduced, result = await evaluate(death_rows(written=written))
    assert result["status"] == status
    assert result["reason_code"] == ("requirement_violated" if status == "non_compliant" else "requirement_satisfied")
    facts = result["customer_display_facts"]
    assert facts["diagnosis_scope"] == "death"
    assert facts["authoritative_diagnoses"] == ["合成诊断甲"]
    assert facts["written_diagnoses"] == [written]
    assert "死亡诊断" in result["findings"]
    assert "权威出院诊断" not in result["findings"]
    assert "本次尚未形成出院记录" not in result["findings"]
    death_ref = materials.document_rows("death_record", snapshot=snapshot)[0][0]
    assert death_ref in execution.decisions[0].fact_refs
    assert not any(item.get("source_type") == "discharge_record"
                   for item in result.get("customer_evidence", []))


@pytest.mark.asyncio
@pytest.mark.parametrize("death_time,registration", [
    (None, []),
    ("2026-10-01 08:00:00", [{"patient_status": "死亡", "death_time": "2026-10-02 08:00:00"}]),
])
async def test_confirmed_death_content_does_not_require_unneeded_death_timestamp(death_time, registration):
    rows = death_rows(death_time=death_time)
    rows["inpat_registration"] = registration
    _, _, _, _, result = await evaluate(rows)
    assert result["status"] == "non_compliant"
    assert result["customer_display_facts"]["diagnosis_scope"] == "death"


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", ["discharge_record", "inpat_registration"])
async def test_readable_death_record_is_independent_of_unconsumed_sources(unavailable):
    _, _, _, _, result = await evaluate(death_rows(), unavailable_sources={unavailable})
    assert result["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_registration_confirmed_death_does_not_require_a_death_document_to_compare_diagnoses():
    rows = death_rows()
    rows.pop("death_record")
    rows["inpat_registration"] = [{"patient_status": "死亡"}]
    _, _, _, _, result = await evaluate(rows)
    assert result["status"] == "non_compliant"
    assert "死亡记录缺失" not in result["findings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["death", "discharge"])
async def test_terminal_scope_does_not_mix_diagnosis_types_or_opposite_document_refs(scope):
    rows = death_rows(written="合成诊断甲")
    rows["discharge_record"] = [{"document_id": "SYN-DISCH", "record_time": "2026-10-02 10:00:00"}]
    rows["mr_diagnosis"].append(diagnosis("出院侧冲突甲", scope="出院诊断", document="SYN-MR-DISCH"))
    rows["discharge_record_diagnosis"].append(diagnosis("出院侧冲突乙", scope="出院诊断", document="SYN-DISCH"))
    if scope == "discharge":
        rows["death_record"] = []
        rows["inpat_registration"] = [{"patient_status": "正常出院"}]
    snapshot, materials, execution, _, result = await evaluate(rows)
    assert result["status"] == ("compliant" if scope == "death" else "data_gap")
    if scope == "discharge":
        assert result["customer_display_facts"]["authoritative_gap"] == "scope_conflict"
        assert "diagnosis_scope" not in result["customer_display_facts"]
        return
    facts = result["customer_display_facts"]
    assert facts["diagnosis_scope"] == scope
    assert facts["authoritative_diagnoses"] == (["合成诊断甲"] if scope == "death" else ["出院侧冲突甲"])
    for source in ("mr_diagnosis", "discharge_record_diagnosis"):
        for ref, row in materials.document_rows(source, snapshot=snapshot):
            if row["diagnosis_type"] != ("死亡诊断" if scope == "death" else "出院诊断"):
                assert ref not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["mr_diagnosis", "discharge_record_diagnosis"])
async def test_unreadable_required_diagnosis_source_is_gap_and_does_not_fallback(source):
    rows = death_rows()
    rows["diagnosis"] = [diagnosis("合成诊断乙")]
    _, _, _, reduced, result = await evaluate(rows, unavailable_sources={source})
    assert result["status"] == "data_gap"
    assert reduced.reason_code == "source_unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize("rows,status", [
    ({}, "data_gap"),
    ({"inpat_registration": [{"patient_status": ""}]}, "data_gap"),
    ({"inpat_registration": [{"patient_status": "在院"}]}, "not_applicable"),
    ({"inpat_registration": [{"patient_status": "正常出院"}]}, "not_applicable"),
])
async def test_unknown_or_alive_scope_never_infers_missing_death_diagnosis(rows, status):
    _, _, _, _, result = await evaluate(rows)
    assert result["status"] == status
    assert "死亡诊断错填" not in result["findings"]
    assert "未记录死亡诊断" not in result["findings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["authority_missing", "written_missing", "name_missing", "same_names_without_order", "mismatch_without_order", "order_mismatch"])
async def test_death_diagnosis_missing_and_order_contract_keeps_confirmed_content_defects(change):
    rows = death_rows(written="合成诊断甲")
    expected = "data_gap"
    if change == "authority_missing":
        rows["mr_diagnosis"] = []
    elif change == "written_missing":
        rows["discharge_record_diagnosis"] = []
    elif change == "name_missing":
        rows["discharge_record_diagnosis"][0]["diagnosis_name"] = ""
    else:
        rows["mr_diagnosis"].append(diagnosis("合成诊断乙", sequence=2, document="SYN-MR"))
        rows["discharge_record_diagnosis"].append(diagnosis("合成诊断乙", sequence=2))
        if change == "order_mismatch":
            expected = "non_compliant"
            rows["discharge_record_diagnosis"][0]["diagnosis_no"] = 2
            rows["discharge_record_diagnosis"][1]["diagnosis_no"] = 1
        else:
            for row in rows["discharge_record_diagnosis"]:
                row.pop("diagnosis_no")
            if change == "mismatch_without_order":
                rows["discharge_record_diagnosis"][0]["diagnosis_name"] = "合成诊断丙"
                expected = "non_compliant"
    _, _, _, _, result = await evaluate(rows)
    assert result["status"] == expected
    assert result["customer_display_facts"]["diagnosis_scope"] == "death"
    if expected == "data_gap":
        assert "死亡诊断" in result["findings"]


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


@pytest.mark.asyncio
@pytest.mark.parametrize("written", ["合成诊断甲", "合成诊断乙", ""])
async def test_death_scope_survives_isolated_sqlite_new_engine_and_customer_projection(written, tmp_path):
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace_module
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

    _, _, _, _, result = await evaluate(death_rows(written=written))
    item = {**result, "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "dd-f01-death-scope.sqlite").as_posix()
    engine = create_engine(url)
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    try:
        with Session(engine) as write_db:
            store.replace_for_job(write_db, job_row={"id": "J", "created_by": "reviewer",
                "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})},
                items=[item], now=datetime(2026, 10, 8, 12),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"), projection_key="test-key")
            write_db.commit()
        engine.dispose()
        engine = create_engine(url)
        with Session(engine) as read_db:
            loaded = store.load_selected(read_db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")
            saved = loaded["items"][0]
            assert saved["customer_display_facts"]["diagnosis_scope"] == "death"
            for key in ("status", "reason_code", "customer_display_facts", "findings", "suggestion"):
                assert saved.get(key) == item.get(key)
            api = workspace_module.project_customer_safe_result_item(saved, hmac_key="test-key")
            assert api["customer_display_facts"] == saved["customer_display_facts"]
            assert api["evidence"] == saved["evidence"]
            assert "event_key" not in json.dumps(api, ensure_ascii=False)
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_real_death_document_coordinates_are_projected_without_invented_discharge_parent():
    rows = death_rows()
    rows["death_record"][0].update(record_time="2026-10-01 09:00:00", record_content="患者死亡，死亡诊断已填写。")
    snapshot, materials, execution, _, result = await evaluate(rows)
    assert result["status"] == "non_compliant"
    mr_ref = materials.document_rows("mr_diagnosis", snapshot=snapshot)[0][0]
    source_ref = next(ob.snapshot_ref.removeprefix("sha256:") for ob in snapshot.observations if ob.source_key == "mr_diagnosis")
    assert mr_ref not in execution.decisions[0].fact_refs
    assert source_ref in execution.decisions[0].fact_refs
    assert any(item.get("source_document_id") == "SYN-DEATH" and item.get("source_type") == "death_record"
               for item in result["customer_evidence"])
    assert not any(item.get("source_type") == "discharge_record" for item in result["customer_evidence"])


# 独立审计冻结8项：ba15b3e8...，原DD-S01及旧死亡fixture预期不覆盖。
TYPED_DEATH_SCOPE_CASES = [('DD-TD-001', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [], 'inpat_registration': []}, 'compliant'), ('DD-TD-002', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断乙', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [], 'inpat_registration': []}, 'non_compliant'), ('DD-TD-003', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [], 'inpat_registration': [{'patient_status': '在院'}]}, 'data_gap'), ('DD-TD-004', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [], 'inpat_registration': [{'patient_status': '存活', 'discharge_status': '存活'}]}, 'data_gap'), ('DD-TD-005', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}, {'diagnosis_type': '出院诊断', 'diagnosis_no': 2, 'diagnosis_name': '合成诊断乙'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [], 'inpat_registration': []}, 'data_gap'), ('DD-TD-006', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [{'document_id': 'SYN-DEATH-A', 'death_time': '2026-10-01 08:00:00'}, {'document_id': 'SYN-DEATH-B', 'death_time': '2026-10-01 09:00:00'}], 'discharge_record': [], 'inpat_registration': [{'patient_status': '死亡', 'death_datetime': '2026-10-01 08:00:00'}]}, 'compliant'), ('DD-TD-007', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断乙', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [{'document_id': 'SYN-DEATH-A', 'death_time': '2026-10-01 08:00:00'}, {'document_id': 'SYN-DEATH-B', 'death_time': '2026-10-01 09:00:00'}], 'discharge_record': [], 'inpat_registration': [{'patient_status': '死亡', 'death_datetime': '2026-10-01 08:00:00'}]}, 'non_compliant'), ('DD-TD-008', {'mr_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲'}], 'discharge_record_diagnosis': [{'diagnosis_type': '死亡诊断', 'diagnosis_no': 1, 'diagnosis_name': '合成诊断甲', 'document_id': 'SYN-DEATH-WRITTEN'}], 'death_record': [], 'discharge_record': [{'record_time': '2026-10-01 10:00:00'}], 'inpat_registration': []}, 'compliant')]


@pytest.mark.asyncio
@pytest.mark.parametrize("case_id,rows,status", TYPED_DEATH_SCOPE_CASES, ids=[case[0] for case in TYPED_DEATH_SCOPE_CASES])
async def test_independent_typed_death_scope_freeze(case_id, rows, status):
    _, _, _, _, result = await evaluate(rows)
    assert result["status"] == status, case_id
    if status in {"compliant", "non_compliant"}:
        assert result["customer_display_facts"]["diagnosis_scope"] == "death"


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


@pytest.mark.asyncio
async def test_normal_discharge_authority_does_not_consume_extra_written_death_diagnoses():
    rows = {"inpat_registration": [{"patient_status": "正常出院"}],
            "discharge_record": [{"document_id": "SYN-DISCH", "record_time": "2026-10-02 10:00:00"}],
            "mr_diagnosis": [diagnosis("合成诊断甲", scope="出院诊断", document="SYN-MR")],
            "discharge_record_diagnosis": [diagnosis("合成诊断乙", scope="出院诊断", document="SYN-DISCH"),
                                          diagnosis("死亡侧无关诊断", document="SYN-DEATH")]}
    snapshot, materials, execution, _, result = await evaluate(rows)
    assert result["status"] == "non_compliant"
    assert result["customer_display_facts"].get("diagnosis_scope", "discharge") == "discharge"
    assert result["customer_display_facts"]["written_diagnoses"] == ["合成诊断乙"]
    other_ref = next(ref for ref, row in materials.document_rows("discharge_record_diagnosis", snapshot=snapshot)
                     if row["diagnosis_type"] == "死亡诊断")
    assert other_ref not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", [{"death_record"}, {"inpat_registration"}, {"death_record", "inpat_registration"}])
async def test_optional_death_context_unavailable_does_not_block_normal_discharge(unavailable):
    rows = {"discharge_record": [{"document_id": "SYN-DISCH", "record_time": "2026-10-02 10:00:00"}],
            "mr_diagnosis": [diagnosis("合成诊断甲", scope="出院诊断", document="SYN-MR")],
            "discharge_record_diagnosis": [diagnosis("合成诊断甲", scope="出院诊断", document="SYN-DISCH")]}
    _, _, _, _, result = await evaluate(rows, unavailable_sources=unavailable)
    assert result["status"] == "compliant"
    assert result["customer_display_facts"].get("diagnosis_scope", "discharge") == "discharge"
