"""029 医嘱触发只交付阳性医嘱，不将同源无关材料混入客户证据。"""
import pytest

from app.services.case_material_snapshot import activate
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
from app.services.luxian_0609.evidence_snapshot import Luxian0609EvidenceSnapshot
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.fact_schema import FactV2
from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceQueryError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("procedure_names", "surgery_code", "surgery_read", "order_read", "summary_available", "expected_state", "expected_reason"),
    [
        (("纤维支气管镜下肺活检", "内镜下胃息肉切除术"), None, "complete", "complete", False, "not_applicable", "eligibility_not_met"),
        (("内镜下胃息肉切除术",), "43.4105", "complete", "complete", True, "not_applicable", "eligibility_not_met"),
        (("内镜下胃息肉切除术",), "01.2400X013", "complete", "complete", False, "data_gap", None),
        (("内镜下胃息肉切除术",), None, "unknown", "complete", False, "data_gap", "source_readiness_unproven"),
        (("内镜下胃息肉切除术",), None, "complete", "unknown", False, "data_gap", "source_readiness_unproven"),
        (("内镜下胃息肉切除术",), None, "complete", "surgery", True, "data_gap", "source_readiness_unproven"),
        (("内镜下胃息肉切除术",), None, "complete", "error", False, "technical_error", "source_query_error"),
        (("内镜下胃息肉切除术", "腹腔镜下胆囊切除术"), None, "complete", "complete", False, "data_gap", None),
        ((), None, "unknown", "unknown", False, "data_gap", "source_readiness_unproven"),
        (("内镜下胃息肉切除术",), None, "truncated", "complete", False, "data_gap", None),
        ((), None, "error", "complete", False, "technical_error", "source_query_error"),
    ],
)
async def test_029_endoscopic_exception_requires_complete_event_coverage(
    procedure_names, surgery_code, surgery_read, order_read, summary_available, expected_state, expected_reason,
):
    rule_id = "LX0609-04-01-01"
    procedures = tuple(
        {
            "document_id": f"procedure-{i}",
            "surgery_name": name,
            "surgery_code": surgery_code,
            "surgery_begin_time": f"2026-06-01 {hour}:00:00+08:00",
            "surgery_end_time": f"2026-06-01 {hour}:30:00+08:00",
        }
        for i, (hour, name) in enumerate(zip(("08", "11"), procedure_names))
    )
    summary = ({"document_id": "summary-1", "record_content": "术前小结正文完整。"},) if summary_available else ()
    orders = (
        ({"order_id": "another-surgery", "order_type": "手术", "order_status": "新开", "order_name": "腹腔镜下胆囊切除术"},)
        if order_read == "surgery" else ()
    )
    rows = {"surgery_record": procedures, "presurg_summary": summary, "inpat_nondrug_order": orders}
    covered_sources = {
        source
        for source, covered in (
            ("surgery_record", surgery_read == "complete"),
            ("inpat_nondrug_order", order_read in {"complete", "surgery"}),
        )
        if covered
    }
    scopes = {
        source: {
            "protocol": "cdm-auto-v1",
            "status": "available" if source_rows else "empty" if source in covered_sources else "empty_unconfirmed",
            "coverage": "complete" if source in covered_sources else "unknown",
            "can_judge_clinical_absence": source in covered_sources,
        }
        for source, source_rows in rows.items()
    }

    def reader(*, source_key, **_kwargs):
        if (
            (source_key == "surgery_record" and surgery_read == "error")
            or (source_key == "inpat_nondrug_order" and order_read == "error")
        ):
            raise SourceEvidenceQueryError()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows.get(source_key, ()),
            truncated=source_key == "surgery_record" and surgery_read == "truncated",
            limit_rows=100,
            material_scope=scopes.get(source_key),
        )

    with activate({"automatic_material": {"sources": scopes}}):
        session = build_luxian_0609_evidence_read_session(
            selected_rule_ids=(rule_id,), institute_id="I", patient_id="P", visit_id="V",
            source_schema=None, created_at="2026-06-08T00:00:00+08:00", row_reader=reader,
        )
        result = await execute_luxian_0609_native_surgery_document_rules(
            rule_ids=(rule_id,), wrapper_rules=[], evidence_payload=None, llm_client=None,
            evidence_snapshot=session.snapshot, evidence_materials=session.materials,
            decision_rule_ids=(rule_id,),
        )
        decision, = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=result.decisions, expected_rule_ids=(rule_id,),
            snapshot=session.snapshot, evidence_materials=session.materials,
        )
        assert decision.final_state.value == expected_state
        if expected_reason is not None:
            assert decision.reason_code == expected_reason

        if expected_state == "not_applicable":
            surgery_refs = {
                ref for ref, _ in session.materials.document_rows("surgery_record", snapshot=session.snapshot)
            }
            order_source_ref = next(
                observation.snapshot_ref.removeprefix("sha256:")
                for observation in session.snapshot.observations
                if observation.source_key == "inpat_nondrug_order"
            )
            expected_refs = surgery_refs | {order_source_ref}
            assert set(decision.fact_refs) == expected_refs
            canonical = finalize_luxian_0609_reduced_customer_result(
                decision=decision, raw_customer_display_facts=None,
                evidence_snapshot=session.snapshot, evidence_materials=session.materials,
            )
            assert canonical["status"] == "not_applicable"
            receipt = canonical["applicability_receipt"]
            assert set(receipt["fact_refs"]) == expected_refs
            assert {check["source_key"] for check in receipt["source_checks"] if check["depended_on"]} == {
                "surgery_record", "inpat_nondrug_order",
            }


@pytest.mark.asyncio
async def test_029_endoscopic_record_cannot_exempt_independently_confirmed_surgery():
    rule_id = "LX0609-04-01-01"
    row = {
        "document_id": "endoscopy",
        "surgery_name": "内镜下胃息肉切除术",
        "surgery_code": "43.4105",
        "surgery_begin_time": "2026-06-01 08:00:00+08:00",
        "surgery_end_time": "2026-06-01 08:30:00+08:00",
    }

    def reader(*, source_key, **_kwargs):
        return SnapshotSourceRows.create(
            source_key=source_key, rows=(row,) if source_key == "surgery_record" else (),
            truncated=False, limit_rows=100,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-06-08T00:00:00+08:00", row_reader=reader,
    )
    original = session.snapshot
    fact_fields = next(fact for fact in original.facts if fact.fact_type == "current_visit_surgery_confirmed").to_dict()
    del fact_fields["fact_id"]
    fact_fields["source_document_id"] = "separate-verified-operation"
    confirmed_surgery = FactV2.create(**fact_fields, redaction_terms=(), known_upstream_fact_ids=())
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="I", patient_id="P", visit_id="V", snapshot_schema_version=original.snapshot_schema_version,
        source_registry_version=original.source_registry_version, observations=original.observations,
        facts=(*original.facts, confirmed_surgery), document_refs=original.document_refs, created_at=original.created_at,
    )
    materials = Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot, sources=session.materials.diagnostic_sources(snapshot=original),
    )
    result = await execute_luxian_0609_native_surgery_document_rules(
        rule_ids=(rule_id,), wrapper_rules=[], evidence_payload=None, llm_client=None,
        evidence_snapshot=snapshot, evidence_materials=materials, decision_rule_ids=(rule_id,),
    )
    decision, = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule_id,), snapshot=snapshot, evidence_materials=materials,
    )
    assert decision.final_state.value == "data_gap"
    assert decision.reason_code == "source_readiness_unproven"
    assert confirmed_surgery.fact_id in decision.fact_refs


@pytest.mark.asyncio
@pytest.mark.parametrize("unrelated_count", [1, 179])
@pytest.mark.parametrize("has_summary", [False, True])
async def test_029_excludes_unrelated_orders_from_decision_and_customer_evidence(
    unrelated_count, has_summary,
):
    """超过引用上限的无关医嘱不能中断交付；少量无关医嘱也不得污染证据。"""
    orders = (
        # 用户已将气管插管排除为治疗性操作；阳性证据隔离须使用真正的手术。
        {"order_id": "operation||1", "order_type": "手术", "order_status": "新开", "order_name": "腹腔镜下阑尾切除术"},
        *(
            {"order_id": f"unrelated||{index}", "order_type": "护理", "order_status": "新开", "order_name": "常规护理"}
            for index in range(unrelated_count)
        ),
    )
    summary = (
        ({"document_id": "summary||1", "record_content": "术前小结正文完整。"},)
        if has_summary else ()
    )

    def reader(**kwargs):
        source = kwargs["source_key"]
        rows = {"inpat_nondrug_order": orders, "presurg_summary": summary}.get(source, ())
        return SnapshotSourceRows.create(
            source_key=source, rows=rows, truncated=False, limit_rows=1000,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-01-01",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-09-08T00:00:00+08:00", row_reader=reader,
    )
    result = await execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",), wrapper_rules=[], evidence_payload=None,
        llm_client=None, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    # 用户口径（2026-11-08）：仅医嘱触发、实施情况未知时缺小结保留未决。
    expected_state = "compliant" if has_summary else "data_gap"
    expected_reason = "requirement_satisfied" if has_summary else "source_readiness_unproven"
    assert reduced[0].final_state.value == expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == result.total_tokens == 0

    adopted_refs = set(result.decisions[0].fact_refs)
    for ref, row in session.materials.document_rows("inpat_nondrug_order", snapshot=session.snapshot):
        assert (ref in adopted_refs) == (row["order_id"] == "operation||1")
    for ref, _ in session.materials.document_rows("presurg_summary", snapshot=session.snapshot):
        assert ref in adopted_refs
    canonical = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0], raw_customer_display_facts=dict(result.customer_display_facts).get("LX0609-04-01-01"),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    expected_coordinates = {("inpat_nondrug_order", "operation||1")}
    if has_summary:
        expected_coordinates.add(("presurg_summary", "summary||1"))
    assert {
        (item["source_type"], item["source_document_id"])
        for item in canonical["customer_evidence"]
    } == expected_coordinates
    assert canonical["status"] == expected_state
    assert canonical["reason_code"] == expected_reason
