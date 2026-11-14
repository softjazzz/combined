"""合成冻结材料：备选来源缺口不得抵消已独立证明的手术缺陷。"""

from dataclasses import replace
from datetime import datetime

import pytest

from app.services import case_material_snapshot as material
from app.services.luxian_0609 import native_surgery_gate_execution as surgery
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from test_luxian_0609_native_surgery_gate_execution import _typed_003_session


def _auto_state():
    return {"automatic_material": {"protocol": "cdm-auto-v1", "sources": {
        key: {"status": "available" if key == "surgery_record" else "empty_unconfirmed",
              "can_judge_clinical_absence": False}
        for key in ("surgery_record", "mr_surgery", "anesthesia_record", "surgery_application", "inpat_nondrug_order")
    }}}


def _reduce(session, decision):
    return bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,), expected_rule_ids=(decision.rule_id,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]


def test_independent_late_surgery_stays_defect_with_empty_alternatives():
    with material.activate(_auto_state()):
        session = _typed_003_session(
            surgery_document_id="SYNTHETIC-S1", surgery_begin_time="2026-01-01 08:00:00+08:00",
            surgery_time="2026-01-01 10:00:00+08", record_time="2026-01-02 11:00:00",
        )
        facts = []
        decision = surgery._typed_003_decision(
            snapshot=session.snapshot, materials=session.materials, customer_display_facts=facts,
        )
        assert decision.reason_code == "threshold_exceeded"
        assert facts[0][1]["elapsed_hours"] == 25.0
        reduced = _reduce(session, decision)
        assert (reduced.final_state.value, reduced.reason_code) == ("non_compliant", "threshold_exceeded")
        from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
        result = finalize_luxian_0609_reduced_customer_result(
            decision=reduced, raw_customer_display_facts=facts[0][1],
            evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        )
        assert result["status"] == "non_compliant"
        assert result["reason_code"] == "threshold_exceeded"


@pytest.mark.parametrize("mode", ["truncated", "empty", "error"])
def test_positive_scope_never_bypasses_bad_surgery_material(mode):
    with material.activate(_auto_state()):
        session = _typed_003_session(
            surgery_document_id="SYNTHETIC-S1", surgery_time="2026-01-01 10:00:00+08",
            record_time="2026-01-02 11:00:00", source_mode=mode,
        )
        decision = surgery._typed_003_decision(snapshot=session.snapshot, materials=session.materials)
        assert not decision.positive_document_refs
        assert _reduce(session, decision).final_state.value in {"data_gap", "technical_error"}


@pytest.mark.parametrize("tamper", ["hash", "ref"])
def test_positive_surgery_still_requires_original_snapshot_binding(tamper):
    with material.activate(_auto_state()):
        session = _typed_003_session(
            surgery_document_id="SYNTHETIC-S1", surgery_time="2026-01-01 10:00:00+08",
            record_time="2026-01-02 11:00:00",
        )
        decision = surgery._typed_003_decision(snapshot=session.snapshot, materials=session.materials)
        decision = replace(decision, **(
            {"snapshot_hash": "f" * 64} if tamper == "hash" else
            {"positive_document_refs": ("f" * 64,), "fact_refs": ("f" * 64,)}
        ))
        reduced = _reduce(session, decision)
        assert (reduced.final_state.value, reduced.reason_code) == ("technical_error", "snapshot_mismatch")


def test_independent_signature_defect_stays_defect_with_missing_master():
    with material.activate(_auto_state()):
        def reader(**kwargs):
            key = kwargs["source_key"]
            rows = ({"document_id": "SYNTHETIC-S1", "surgery_name": "合成手术",
                     "surgery_end_time": "2026-01-01 10:00:00+08", "surgeon": "术者甲",
                     "surgeon_sign": "医师乙", "record_content": "合成正文"},) if key == "surgery_record" else ()
            return SnapshotSourceRows.create(source_key=key, rows=rows, truncated=False, limit_rows=50)
        session = build_luxian_0609_evidence_read_session(
            selected_rule_ids=("LX0609-04-02-05",), institute_id="I", patient_id="P", visit_id="V",
            source_schema=None, created_at="2026-01-03T12:00:00+08:00", row_reader=reader,
        )
        decision = surgery._typed_conservative_surgery_gate_decision(
            rule_id="LX0609-04-02-05", snapshot=session.snapshot, materials=session.materials,
        )
        assert decision.qc_direction.value == "defect"
        assert _reduce(session, decision).final_state.value == "non_compliant"


@pytest.mark.parametrize("fallback", ["anesthesia_record"])
def test_late_fallback_preserves_both_actual_evidence_sources(fallback):
    state = _auto_state()
    state["automatic_material"]["sources"][fallback]["status"] = "available"
    with material.activate(state):
        session = _typed_003_session(
            surgery_document_id="SYNTHETIC-S1", surgery_begin_time="2026-01-01 08:00:00+08",
            record_time=datetime(2026, 1, 2, 11),
            **({"mr_surgery_time": datetime(2026, 1, 1, 10)} if fallback == "mr_surgery" else {
                "anesthesia_surgery_begin_time": "2026-01-01 08:00:00+08:00",
                "anesthesia_surgery_end_time": "2026-01-01 10:00:00+08:00",
            }),
        )
        facts = []
        decision = surgery._typed_003_decision(
            snapshot=session.snapshot, materials=session.materials, customer_display_facts=facts,
        )
        expected_refs = {
            ref for key in ("surgery_record", fallback)
            for ref, _row in session.materials.document_rows(key, snapshot=session.snapshot)
        }
        assert len(expected_refs) == 2
        assert set(decision.fact_refs) == set(decision.positive_document_refs) == expected_refs
        reduced = _reduce(session, decision)
        assert (reduced.final_state.value, reduced.reason_code) == ("non_compliant", "threshold_exceeded")
        from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
        result = finalize_luxian_0609_reduced_customer_result(
            decision=reduced, raw_customer_display_facts=facts[0][1],
            evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        )
        assert {row["source_type"] for row in result["customer_evidence"]} == {"surgery_record", fallback}


@pytest.mark.parametrize("record_time", ["2026-01-01 11:00:00", "2026-01-02 11:00:00"])
def test_003_requires_only_real_sources_without_frontpage_observation(record_time):
    session = _typed_003_session(
        surgery_document_id="SYNTHETIC-S1", surgery_time="2026-01-01 10:00:00+08",
        record_time=record_time,
    )
    decision = surgery._typed_003_decision(snapshot=session.snapshot, materials=session.materials)
    assert decision.reason_code == ("threshold_exceeded" if "02 11" in record_time else "requirement_within_threshold")


def test_signature_selection_ignores_conflicting_frontpage():
    record = {"surgeon": "术者甲", "surgeon_sign": "术者甲", "record_content": "合成记录"}
    master = {"surgeon": "术者甲", "surgeon_sign": "错误签名"}
    actual = surgery._resolve_surgery_signature_selection(surgery_master_rows=(master,), surgery_record_rows=(record,))
    assert actual == surgery._resolve_surgery_signature_selection(surgery_master_rows=(), surgery_record_rows=(record,))
