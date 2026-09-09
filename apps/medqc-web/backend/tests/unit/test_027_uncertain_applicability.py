"""027 恶性性质不确定属于适用性未知，不是治疗计划缺字段。"""

import json

import pytest

from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.malignancy_fact import MalignancyFactResolver, MalignancySource, build_stage_malignancy_sources
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result


class OfflineClient:
    def __init__(self, state="uncertain"):
        self.state = state
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        payload = {"schema_version": "lx0609_malignancy_v1", "results": [
            {"ref": "D01", "state": "explicit_nonmalignant"},
            {"ref": "D02", "state": self.state},
        ]}
        return {"choices": [{"message": {"content": json.dumps(payload)}}], "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}}


@pytest.mark.parametrize("source", ["admission_record_diagnosis", "diagnosis", "discharge_record_diagnosis"])
@pytest.mark.asyncio
async def test_uncertain_resolution_retains_exact_source_row_without_prompt_coordinates(source):
    rows = ({"document_id": "private-normal", "diagnosis_name": "合成普通诊断"}, {"document_id": "private-uncertain", "diagnosis_name": "合成性质待定诊断"})
    sources = build_stage_malignancy_sources(
        visit_stage="inpatient" if source == "admission_record_diagnosis" else "discharged",
        admission_state="available", admission_rows=rows if source == "admission_record_diagnosis" else (),
        diagnosis_state="available" if source == "diagnosis" else "empty", diagnosis_rows=rows if source == "diagnosis" else (),
        discharge_diagnosis_state="available", discharge_diagnosis_rows=rows if source == "discharge_record_diagnosis" else (),
        pathology_state="empty", pathology_rows=(),
    )
    client = OfflineClient()
    resolver = MalignancyFactResolver(client)
    resolution = await resolver.resolve(sources)
    assert resolution.uncertain_rows == ((source, rows[1]),)
    assert resolution.uncertain_rows[0][1] is rows[1]
    assert await resolver.resolve(sources) is resolution
    assert resolver.claim_usage().llm_call_count == 1
    assert resolver.claim_usage().llm_call_count == 0
    assert len(client.prompts) == 1
    assert "private-" not in client.prompts[0]
    assert "source_key" not in client.prompts[0]


@pytest.mark.parametrize("source", ["diagnosis", "discharge_record_diagnosis"])
@pytest.mark.parametrize("prewarmed", [False, True])
@pytest.mark.asyncio
async def test_027_uncertainty_survives_binding_and_finalizer(source, prewarmed):
    rows = [{"document_id": "normal", "diagnosis_name": "合成普通诊断"}, {"document_id": "uncertain", "diagnosis_name": "合成性质待定诊断"}]
    def reader(**kwargs):
        key = kwargs["source_key"]
        material = rows if key == source else [{"document_id": "discharge", "record_content": "出院后复诊。"}] if key == "discharge_record" else []
        return SnapshotSourceRows.create(source_key=key, rows=material, truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-027",), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-01-09T09:00:00+08:00", row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("tumor_pathology",), selected_rule_ids=("LX0609-027",)),
    )
    client = OfflineClient()
    resolver = MalignancyFactResolver(client)
    if prewarmed:
        # 模拟同请求内先由其他规则消费共享恶性事实，并已经认领模型用量。
        await resolver.resolve((MalignancySource(source, "available", session.materials.rows(source)),))
        assert resolver.claim_usage().llm_call_count == 1
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-027",), wrapper_rules=[{"rule_id": "LX0609-027", "custom_prompt": "{medical_text}"}], evidence_payload=None,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=("LX0609-027",),
        malignancy_resolver=resolver,
    )
    assert result.decisions[0].applicability.value == "unknown"
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=result.decisions, expected_rule_ids=("LX0609-027",), snapshot=session.snapshot, evidence_materials=session.materials)[0]
    final = finalize_luxian_0609_reduced_customer_result(decision=reduced, raw_customer_display_facts=dict(result.customer_display_facts).get("LX0609-027"), evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    assert reduced.final_state.value == "evaluation_unknown"
    assert final["status"] == "uncertain"
    assert final["reason_code"] == "semantic_low_confidence"
    assert final["customer_display_facts"] == {"verification_kind": "malignant_diagnosis_applicability_uncertain", "malignancy_state": "unknown", "uncertain_diagnosis_count": 1}
    assert [item["source_document_id"] for item in final["customer_evidence"]] == ["uncertain"]
    assert not final.get("missing_fields")
    assert "恶性性质" in final["findings"]
    assert "缺少" not in final["findings"]
    assert len(client.prompts) == 1
    assert result.llm_call_count == (0 if prewarmed else 1)


@pytest.mark.parametrize("count", [True, 0, -1, "1"])
def test_uncertainty_display_rejects_invalid_count(count):
    from app.services.luxian_0609.tumor_pathology_result_mapping import safe_tumor_pathology_customer_display_facts
    assert safe_tumor_pathology_customer_display_facts(rule_id="LX0609-027", raw={
        "verification_kind": "malignant_diagnosis_applicability_uncertain",
        "malignancy_state": "unknown", "uncertain_diagnosis_count": count,
    }) is None


@pytest.mark.parametrize("parent_count", [0, 1, 2, 3])
@pytest.mark.asyncio
async def test_027_shared_parent_id_locates_only_verified_parent_document(parent_count, monkeypatch):
    if parent_count == 3:
        from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
        original = Luxian0609EvidenceMaterialStore.document_rows
        def reject_parent(self, source_key, *, snapshot):
            if source_key == "discharge_record":
                raise ValueError("parent snapshot mismatch")
            return original(self, source_key, snapshot=snapshot)
        monkeypatch.setattr(Luxian0609EvidenceMaterialStore, "document_rows", reject_parent)
    diagnosis_rows = [
        {"document_id": "parent", "diagnosis_id": "diagnosis-1", "diagnosis_name": "合成普通诊断"},
        {"document_id": "parent", "diagnosis_id": "diagnosis-2", "diagnosis_name": "合成性质待定诊断"},
    ]
    def reader(**kwargs):
        source = kwargs["source_key"]
        rows = diagnosis_rows if source == "discharge_record_diagnosis" else [
            {"document_id": "parent" if parent_count else "other", "record_content": "合成出院记录"}
            for _ in range(1 if parent_count == 3 else max(1, parent_count))
        ] if source == "discharge_record" else []
        return SnapshotSourceRows.create(source_key=source, rows=rows, truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-027",), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-01-09T09:00:00+08:00", row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("tumor_pathology",), selected_rule_ids=("LX0609-027",)),
    )
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-027",), wrapper_rules=[{"rule_id": "LX0609-027", "custom_prompt": "{medical_text}"}], evidence_payload=None,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=OfflineClient(),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=("LX0609-027",),
    )
    selected_rows = [row for ref, row in session.materials.document_rows("discharge_record_diagnosis", snapshot=session.snapshot) if ref in result.decisions[0].fact_refs]
    assert len(selected_rows) == 1 and selected_rows[0]["diagnosis_id"] == "diagnosis-2"
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=result.decisions, expected_rule_ids=("LX0609-027",), snapshot=session.snapshot, evidence_materials=session.materials)[0]
    final = finalize_luxian_0609_reduced_customer_result(decision=reduced, raw_customer_display_facts=dict(result.customer_display_facts)["LX0609-027"], evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    assert final["status"] == "uncertain"
    evidence = final.get("customer_evidence", [])
    if parent_count == 1:
        assert len(evidence) == 1
        assert evidence[0]["source_type"] == "discharge_record"
        assert evidence[0]["source_document_id"] == "parent"
    else:
        assert evidence == []
