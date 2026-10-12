from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from tests.unit.test_luxian_0609_native_extended_document_execution import (
    _canonical_extended_result,
    _evaluate_selected,
    _session,
)


class _TextKeyedMedicationClient:
    """按出院医嘱正文返回人工标注的抽取结果；未标注正文直接报错。"""

    def __init__(self, labels):
        self.labels = dict(labels)
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append(prompt)
        payload = next(value for text, value in self.labels.items() if text in prompt)
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}, "_api_time": 0.1}


def _generic_instruction():
    # 未指明任何具体药物的笼统用药叮嘱。
    return {"schema_version": "lx0609_discharge_medications_v2", "state": "uncertain", "items": []}


def _drug_only(name):
    missing = {"state": "missing", "quote": None}
    return {"schema_version": "lx0609_discharge_medications_v2", "state": "medications_present", "items": [{
        "drug_name": {"state": "present", "quote": name}, "dose": missing, "route": missing,
        "medication_time": missing}]}


async def _evaluate_062(
    rows_by_source, *, llm_client=None, unavailable_sources=frozenset()
):
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-08-01-02",),
        rows_by_source,
        llm_client=llm_client,
        unavailable_sources=unavailable_sources,
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-08-01-02",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )
    return snapshot, materials, execution, reduced[0], canonical


def _document_refs(snapshot, materials):
    return {
        row["document_id"]: reference
        for reference, row in materials.document_rows(
            "discharge_record", snapshot=snapshot
        )
    }


@pytest.mark.asyncio
async def test_062_structured_medications_bind_only_the_first_selected_row() -> None:
    snapshot, materials, execution, reduced, canonical = await _evaluate_062({
        "discharge_record": (
            {"document_id": "ignored-062", "discharge_order": "继续服药"},
            {
                "document_id": "selected-062-structured",
                "discharge_medications": [{
                    "drug_name": "合成药甲",
                    "dose": "1片",
                    "route": "口服",
                    "duration": "7天",
                }],
            },
        ),
    }, llm_client=_TextKeyedMedicationClient({"继续服药": _generic_instruction()}))
    refs = _document_refs(snapshot, materials)
    material_order = [
        row["document_id"]
        for _reference, row in materials.document_rows(
            "discharge_record", snapshot=snapshot
        )
    ]

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"
    assert material_order != ["ignored-062", "selected-062-structured"]
    assert refs["selected-062-structured"] in execution.decisions[0].fact_refs
    assert refs["ignored-062"] not in execution.decisions[0].fact_refs
    assert canonical["customer_evidence"] == [{
        "source_type": "discharge_record",
        "source_document_id": "selected-062-structured",
    }]


@pytest.mark.asyncio
async def test_062_fixed_labels_bind_only_the_row_that_was_parsed() -> None:
    snapshot, materials, execution, reduced, canonical = await _evaluate_062({
        "discharge_record": (
            {
                "document_id": "unparsed-signal-062",
                "discharge_order": "出院后继续服药，定期复诊。",
            },
            {
                "document_id": "selected-labels-062",
                "discharge_order": (
                    "药品名称：合成药乙；用药剂量：1片；"
                    "给药途径：口服；用药时间：7天"
                ),
            },
        ),
    }, llm_client=_TextKeyedMedicationClient({"出院后继续服药，定期复诊。": _generic_instruction()}))
    refs = _document_refs(snapshot, materials)

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert refs["selected-labels-062"] in execution.decisions[0].fact_refs
    assert refs["unparsed-signal-062"] not in execution.decisions[0].fact_refs
    assert canonical["customer_evidence"][0]["source_document_id"] == (
        "selected-labels-062"
    )


@pytest.mark.asyncio
async def test_062_unparsed_medication_signals_bind_every_signal_row() -> None:
    snapshot, materials, execution, reduced, canonical = await _evaluate_062({
        "discharge_record": (
            {
                "document_id": "signal-a-062",
                "discharge_order": "出院后继续服用合成药甲。",
            },
            {
                "document_id": "non-medication-062",
                "discharge_order": "出院后清淡饮食。",
            },
            {
                "document_id": "signal-b-062",
                "discharge_order": "出院带药合成药乙，按医嘱执行。",
            },
        ),
    })
    refs = _document_refs(snapshot, materials)

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "required_field_missing"
    assert refs["signal-a-062"] in execution.decisions[0].fact_refs
    assert refs["non-medication-062"] not in execution.decisions[0].fact_refs
    assert refs["signal-b-062"] in execution.decisions[0].fact_refs
    assert {
        item["source_document_id"] for item in canonical["customer_evidence"]
    } == {"signal-a-062", "signal-b-062"}


@pytest.mark.asyncio
async def test_062_single_row_model_failure_binds_its_only_input_document() -> None:
    class InvalidClient:
        def __init__(self):
            self.calls = 0

        async def generate(self, _prompt, **_kwargs):
            self.calls += 1
            return {
                "choices": [{"message": {"content": "not-json"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            }

    client = InvalidClient()
    snapshot, materials, execution, reduced, canonical = await _evaluate_062(
        {
            "discharge_record": ({
                "document_id": "model-input-062",
                "discharge_order": "出院后继续服用合成药甲，按医嘱执行。",
            },),
        },
        llm_client=client,
    )
    only_ref = _document_refs(snapshot, materials)["model-input-062"]

    assert client.calls == 1
    assert reduced.final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced.reason_code == "model_invalid_output"
    assert only_ref in execution.decisions[0].fact_refs
    assert canonical["customer_evidence"] == [{
        "source_type": "discharge_record",
        "source_document_id": "model-input-062",
    }]


@pytest.mark.asyncio
@pytest.mark.parametrize("repeat_same_object", [False, True])
async def test_062_equal_or_repeated_rows_select_one_occurrence_without_guessing_id(
    repeat_same_object,
) -> None:
    row = {
        "document_id": "duplicate-document-062",
        "discharge_medications": [{
            "drug_name": "合成药甲",
            "dose": "1片",
            "route": "口服",
            "duration": "7天",
        }],
    }
    rows = (row, row) if repeat_same_object else (row, dict(row))
    snapshot, materials, execution, reduced, canonical = await _evaluate_062({
        "discharge_record": rows,
    })
    occurrence_refs = {
        reference
        for reference, _material_row in materials.document_rows(
            "discharge_record", snapshot=snapshot
        )
    }

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    # 2026-10-07 审计合同：所有出院记录中的带药均并入核对，内容相同的两份独立
    # 记录各绑定一次；同一对象重复出现时无法区分出现位置，仍不绑定。
    expected_bound_occurrences = 0 if repeat_same_object else 2
    assert len(occurrence_refs.intersection(execution.decisions[0].fact_refs)) == (
        expected_bound_occurrences
    )
    if repeat_same_object:
        assert "customer_evidence" not in canonical
    else:
        assert canonical["customer_evidence"] == [{
            "source_type": "discharge_record",
            "source_document_id": "duplicate-document-062",
        }]


@pytest.mark.asyncio
async def test_062_single_row_model_path_does_not_bind_mismatched_material_rows(
    monkeypatch,
) -> None:
    class InvalidClient:
        async def generate(self, _prompt, **_kwargs):
            return {
                "choices": [{"message": {"content": "not-json"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            }

    snapshot, materials = _session({
        "inpat_registration": ({"document_id": "other-material-062"},),
        "discharge_record": ({
            "document_id": "model-input-062",
            "discharge_order": "出院后继续服用合成药甲，按医嘱执行。",
        },),
    })
    original_document_rows = Luxian0609EvidenceMaterialStore.document_rows
    discharge_rows = original_document_rows(
        materials, "discharge_record", snapshot=snapshot
    )
    registration_rows = original_document_rows(
        materials, "inpat_registration", snapshot=snapshot
    )

    def mismatched_document_rows(self, source_key, *, snapshot):
        if source_key == "discharge_record":
            return discharge_rows + registration_rows
        return original_document_rows(self, source_key, snapshot=snapshot)

    monkeypatch.setattr(
        Luxian0609EvidenceMaterialStore,
        "document_rows",
        mismatched_document_rows,
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-08-01-02",),
        decision_rule_ids=("LX0609-08-01-02",),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        llm_client=InvalidClient(),
    )

    material_refs = {reference for reference, _row in discharge_rows + registration_rows}
    assert material_refs.isdisjoint(execution.decisions[0].fact_refs)


@pytest.mark.asyncio
async def test_062_explicit_non_medication_instruction_does_not_create_location() -> None:
    snapshot, materials, execution, reduced, canonical = await _evaluate_062({
        "discharge_record": ({
            "document_id": "non-medication-062",
            "discharge_order": "出院后注意休息，清淡饮食，定期复诊。",
        },),
    })
    only_ref = _document_refs(snapshot, materials)["non-medication-062"]

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"
    assert only_ref not in execution.decisions[0].fact_refs
    assert "customer_evidence" not in canonical


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("unavailable", "expected_state", "expected_reason"),
    [
        (False, CustomerFinalState.NOT_APPLICABLE, "trigger_absent_complete"),
        (True, CustomerFinalState.DATA_GAP, "source_unavailable"),
    ],
)
async def test_062_empty_or_unavailable_source_does_not_create_location(
    unavailable,
    expected_state,
    expected_reason,
) -> None:
    _snapshot, _materials, execution, reduced, canonical = await _evaluate_062(
        {},
        unavailable_sources=(frozenset({"discharge_record"}) if unavailable else frozenset()),
    )

    assert reduced.final_state is expected_state
    assert reduced.reason_code == expected_reason
    assert len(execution.decisions[0].fact_refs) == 1
    assert "customer_evidence" not in canonical


@pytest.mark.asyncio
async def test_062_specific_drug_in_other_free_text_is_still_checked() -> None:
    # 另一份记录点名具体药物却未写明细：不能被完整那份掩盖。
    _, _, execution, reduced, _ = await _evaluate_062({
        "discharge_record": (
            {"document_id": "free-062", "discharge_order": "出院后继续服用合成药甲。"},
            {"document_id": "complete-062", "discharge_order": (
                "药品名称：合成药乙；用药剂量：1片；给药途径：口服；用药时间：7天")},
        ),
    }, llm_client=_TextKeyedMedicationClient({"出院后继续服用合成药甲。": _drug_only("合成药甲")}))
    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert dict(execution.customer_display_facts)["LX0609-08-01-02"]["medication_count"] == 2
