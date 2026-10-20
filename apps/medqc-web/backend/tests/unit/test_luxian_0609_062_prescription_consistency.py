"""062 出院记录与正式出院处方药物集合一致性；全部资料为匿名合成输入。"""

import json
from datetime import datetime

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import project_customer_safe_result_item
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.extended_document.discharge_medication_extraction import SCHEMA_VERSION
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore,
    envelope_item_from_rule_result,
)
from tests.unit.test_luxian_0609_native_extended_document_execution import (
    _canonical_extended_result,
    _session,
)


RULE = "LX0609-08-01-02"


def _medication(name: str) -> dict:
    return {"drug_name": name, "dose": "每次1片", "route": "口服", "duration": "每日1次"}


def _prescription_rows(*names: str) -> dict:
    return {
        "inpat_prescription": ({
            "prescription_id": "rx-discharge",
            "order_type": "出院带药",
            "order_status": "完成",
        },),
        "inpat_prescription_item": tuple({
            "prescription_id": "rx-discharge",
            "prescription_item_id": f"item-{index}",
            "generic_name": name,
            "drug_apply_method": "口服",
        } for index, name in enumerate(names, start=1)),
    }


async def _evaluate(rows: dict, *, llm_client=None, unavailable_sources=frozenset()) -> tuple[object, dict]:
    snapshot, materials = _session(rows, unavailable_sources=unavailable_sources)
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(RULE,), decision_rule_ids=(RULE,), evidence_snapshot=snapshot,
        evidence_materials=materials, llm_client=llm_client,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(RULE,), snapshot=snapshot,
        evidence_materials=materials,
    )
    final = _canonical_extended_result(
        rule_id=RULE, snapshot=snapshot, materials=materials,
        result=result, reduced=reduced,
    )
    return result, final


@pytest.mark.asyncio
async def test_extra_formal_discharge_prescription_drug_is_reported_by_name():
    documented = tuple(f"合成药{index}" for index in range(1, 6))
    missing = "合成药6"
    rows = {
        "discharge_record": ({"document_id": "d1", "discharge_medications": [
            _medication(name) for name in documented
        ]},),
        **_prescription_rows(*documented, missing),
    }

    result, final = await _evaluate(rows)

    assert final["status"] == "non_compliant"
    assert result.llm_call_count == 0
    assert final["customer_display_facts"] == {
        "verification_kind": "discharge_medication_completeness_check",
        "medication_count": 5,
        "prescription_medication_count": 6,
        "required_fields": ["drug_name", "dose", "route", "duration"],
        "missing_fields": ["drug_name"],
        "missing_drug_names": [missing],
    }
    assert missing in final["findings"]


@pytest.mark.asyncio
async def test_safe_generic_suffix_and_source_brand_match_without_false_omission():
    rows = {
        "discharge_record": ({"document_id": "d1", "discharge_medications": [
            _medication("合成药甲"), _medication("品牌乙"),
        ]},),
        "inpat_prescription": ({
            "prescription_id": "rx-discharge", "order_type": "出院带药", "order_status": "完成",
        },),
        "inpat_prescription_item": (
            {"prescription_id": "rx-discharge", "prescription_item_id": "i1",
             "generic_name": "合成药甲片", "drug_apply_method": "口服"},
            {"prescription_id": "rx-discharge", "prescription_item_id": "i2",
             "generic_name": "通用药乙胶囊", "brand_name": "品牌乙胶囊", "drug_apply_method": "口服"},
        ),
    }

    _result, final = await _evaluate(rows)

    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["missing_drug_names"] == []
    assert final["customer_display_facts"]["prescription_medication_count"] == 2


@pytest.mark.asyncio
async def test_exact_two_character_drug_name_matches_without_suffix_expansion():
    rows = {
        "discharge_record": ({"document_id": "d1", "discharge_medications": [_medication("叶酸")]},),
        **_prescription_rows("叶酸"),
    }

    _result, final = await _evaluate(rows)

    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["prescription_medication_count"] == 1
    assert final["customer_display_facts"]["missing_drug_names"] == []


@pytest.mark.asyncio
async def test_duplicate_formal_rows_for_same_drug_are_one_medication_set_member():
    rows = {
        "discharge_record": ({"document_id": "d1", "discharge_medications": [_medication("合成药甲")]},),
        "inpat_prescription": (
            {"prescription_id": "rx1", "order_type": "出院带药", "order_status": "完成"},
            {"prescription_id": "rx2", "order_type": "出院带药", "order_status": "完成"},
        ),
        "inpat_prescription_item": (
            {"prescription_id": "rx1", "prescription_item_id": "i1", "generic_name": "合成药甲",
             "drug_apply_method": "口服"},
            {"prescription_id": "rx2", "prescription_item_id": "i2", "generic_name": "合成药甲",
             "drug_apply_method": "口服"},
        ),
    }

    _result, final = await _evaluate(rows)

    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["prescription_medication_count"] == 1
    assert final["customer_display_facts"]["missing_drug_names"] == []


@pytest.mark.asyncio
async def test_materially_different_drug_identity_is_not_force_matched():
    rows = {
        "discharge_record": ({"document_id": "d1", "discharge_medications": [
            _medication("合成拉唑"),
        ]},),
        **_prescription_rows("异构合成拉唑镁肠溶胶囊"),
    }

    _result, final = await _evaluate(rows)

    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["missing_drug_names"] == ["异构合成拉唑镁肠溶胶囊"]


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", ["inpatient", "canceled", "deleted_header", "deleted_item", "orphan"])
async def test_ineligible_or_orphan_prescription_item_does_not_create_an_omission(variant):
    rows = {
        "discharge_record": ({"document_id": "d1", "discharge_medications": [
            _medication("合成药甲"),
        ]},),
        **_prescription_rows("合成药甲", "不应纳入药乙"),
    }
    header = rows["inpat_prescription"][0]
    items = list(rows["inpat_prescription_item"])
    if variant == "inpatient":
        header["order_type"] = "普通医嘱"
    elif variant == "canceled":
        header["order_status"] = "撤销"
    elif variant == "deleted_header":
        header["is_deleted"] = "1"
    elif variant == "deleted_item":
        items[1]["is_deleted"] = "true"
    else:
        items[1]["prescription_id"] = "other-visit-prescription"
    rows["inpat_prescription_item"] = tuple(items)

    _result, final = await _evaluate(rows)

    if variant in {"inpatient", "canceled", "deleted_header"}:
        assert final["status"] == "compliant"
        assert final["customer_display_facts"]["prescription_medication_count"] == 0
    else:
        assert final["status"] == "compliant"
        assert final["customer_display_facts"]["prescription_medication_count"] == 1
    assert final["customer_display_facts"]["missing_drug_names"] == []


@pytest.mark.asyncio
async def test_explicit_refusal_is_not_turned_into_an_omission_by_prescription_only_evidence():
    class Client:
        async def generate(self, prompt, **kwargs):
            return {"choices": [{"message": {"content": json.dumps({
                "schema_version": SCHEMA_VERSION, "state": "no_medications", "items": [],
            }, ensure_ascii=False)}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

    rows = {
        "discharge_record": ({"document_id": "d1", "discharge_order": "明确拒绝出院带药。"},),
        **_prescription_rows("合成药甲"),
    }

    result, final = await _evaluate(rows, llm_client=Client())

    assert final["status"] == "not_applicable"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_unnamed_formal_prescription_item_is_data_gap_not_fabricated_omission():
    rows = {
        "discharge_record": ({"document_id": "d1", "discharge_medications": [
            _medication("合成药甲"),
        ]},),
        "inpat_prescription": ({
            "prescription_id": "rx-discharge", "order_type": "出院带药", "order_status": "完成",
        },),
        "inpat_prescription_item": ({
            "prescription_id": "rx-discharge", "prescription_item_id": "i1",
            "generic_name": "", "brand_name": "", "drug_apply_method": "口服",
        },),
    }

    _result, final = await _evaluate(rows)

    assert final["status"] == "data_gap"
    assert final["customer_display_facts"] == {
        "verification_kind": "discharge_medication_prescription_identity_gap",
        "gap_reason": "identity_missing",
        "affected_prescription_item_count": 1,
    }
    assert "漏写" not in final["findings"]


@pytest.mark.asyncio
async def test_more_than_twenty_unique_formal_drugs_is_bounded_data_gap():
    names = tuple(f"合成药{index:02d}" for index in range(1, 22))
    rows = {
        "discharge_record": ({"document_id": "d1", "discharge_medications": [_medication(names[0])]},),
        **_prescription_rows(*names),
    }

    _result, final = await _evaluate(rows)

    assert final["status"] == "data_gap"
    assert final["customer_display_facts"] == {
        "verification_kind": "discharge_medication_prescription_identity_gap",
        "gap_reason": "too_many_items",
        "affected_prescription_item_count": 21,
    }


@pytest.mark.asyncio
async def test_confirmed_document_field_gap_wins_without_claiming_unknown_prescription_is_empty():
    incomplete = _medication("合成药甲")
    incomplete["dose"] = "每次1mg"
    incomplete["route"] = ""
    rows = {
        "discharge_record": ({"document_id": "d1", "discharge_medications": [incomplete]},),
        "inpat_prescription": ({
            "prescription_id": "rx-discharge", "order_type": "出院带药", "order_status": "完成",
        },),
        "inpat_prescription_item": ({
            "prescription_id": "rx-discharge", "prescription_item_id": "i1",
            "generic_name": "", "brand_name": "", "drug_apply_method": "口服",
        },),
    }

    _result, final = await _evaluate(rows)

    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"] == {
        "verification_kind": "discharge_medication_completeness_check",
        "medication_count": 1,
        "required_fields": ["drug_name", "dose", "route", "duration"],
        "missing_fields": ["route"],
    }


@pytest.mark.asyncio
async def test_item_source_is_only_required_when_an_eligible_formal_header_exists():
    document = {"discharge_record": ({
        "document_id": "d1", "discharge_medications": [_medication("合成药甲")],
    },)}
    _result, without_header = await _evaluate(
        document, unavailable_sources=frozenset({"inpat_prescription_item"}),
    )
    assert without_header["status"] == "compliant"

    _result, with_header = await _evaluate(
        {
            **document,
            "inpat_prescription": ({
                "prescription_id": "rx-discharge", "order_type": "出院带药", "order_status": "完成",
            },),
        },
        unavailable_sources=frozenset({"inpat_prescription_item"}),
    )
    assert with_header["status"] == "data_gap"
    assert with_header["customer_display_facts"] == {
        "verification_kind": "discharge_medication_prescription_identity_gap",
        "gap_reason": "source_unavailable",
        "affected_prescription_item_count": 0,
    }


def test_prescription_consistency_facts_survive_sqlite_roundtrip():
    facts = {
        "verification_kind": "discharge_medication_completeness_check",
        "medication_count": 5,
        "prescription_medication_count": 6,
        "required_fields": ["drug_name", "dose", "route", "duration"],
        "missing_fields": ["drug_name"],
        "missing_drug_names": ["合成药6"],
    }
    item = {
        "record_id": "visit-1", "visit_id": "visit-1",
        "institute_id": "inst-1", "patient_id": "patient-1",
        "schema_version": "lx0609-customer-result-v2", "rule_id": RULE,
        "status": "non_compliant", "result_status": "non_compliant",
        "display_status": "non_compliant", "is_compliant": False,
        "reason_code": "requirement_violated", "customer_display_facts": facts,
        "conclusion": "出院带药与正式处方不一致。",
    }
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    try:
        with Session(engine) as session:
            store.replace_for_job(
                session,
                job_row={
                    "id": "job-062", "created_by": "reviewer-a",
                    "filters_json": json.dumps({
                        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                    }),
                },
                items=[item], now=datetime(2026, 10, 20, 10, 0, 0),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="unit-test-key"),
                projection_key="unit-test-key",
            )
            session.commit()
            loaded = store.load_selected(
                session, root_job_id="job-062", institute_id="inst-1", patient_id="patient-1",
                visit_id="visit-1", rule_set_key="luxian_0609_qc_v1",
                rule_set_version="2026-06-09",
            )
            assert loaded["items"][0]["customer_display_facts"] == facts
            assert project_customer_safe_result_item(
                loaded["items"][0], hmac_key="unit-test-key",
            )["customer_display_facts"] == facts
    finally:
        engine.dispose()
