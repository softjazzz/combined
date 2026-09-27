"""冻结资料离线复原；使用合成输入，不读取真实病历。"""
from copy import deepcopy

import pytest

from app.services.qc_diagnostics.contracts import DiagnosticPackageError
from app.services.qc_diagnostics.execution_inputs import freeze_execution_inputs
from app.services.qc_diagnostics.session_restore import restore_execution_session
from tests.unit.test_qc_diagnostic_execution_inputs import session_fixture


def fixture():
    session, _ = session_fixture()
    inputs = freeze_execution_inputs(
        session, selected_rule_ids=("LX0609-03-01-01", "LX0609-03-01-04"),
        evaluation_as_of_date="2026-07-05", evaluation_horizon_policy=None,
        horizon_unavailable_reason=None,
    )
    return session, inputs


def test_round_trip_preserves_facts_sources_and_failures_without_reading(monkeypatch):
    original, inputs = fixture()
    import app.services.luxian_0609.evidence_snapshot_provider as provider
    import app.services.luxian_0609.source_evidence_reader as reader
    import socket
    import sqlite3
    def forbidden(*args, **kwargs):
        pytest.fail("offline restoration must not query, connect or extract facts")
    monkeypatch.setattr(provider, "build_luxian_0609_evidence_read_session",
                        forbidden)
    monkeypatch.setattr(provider, "_surgery_order_facts", forbidden)
    monkeypatch.setattr(reader, "read_luxian_0609_snapshot_source_rows", forbidden)
    monkeypatch.setattr(reader, "read_luxian_0609_native_source_rows", forbidden)
    monkeypatch.setattr(reader, "read_luxian_0609_runtime_source_rows", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    restored = restore_execution_session(inputs, coordinates=("I", "P", "V"))
    assert restored.snapshot.to_safe_dict() == original.snapshot.to_safe_dict()
    assert [f.to_dict() for f in restored.snapshot.facts] == [f.to_dict() for f in original.snapshot.facts]
    sources = restored.materials.diagnostic_sources(snapshot=restored.snapshot)
    assert sources == original.materials.diagnostic_sources(snapshot=original.snapshot)
    assert sources["admission_record"].rows == ({"record_content": None}, {"record_content": ""}, {"record_content": ""})
    assert any(o.query_state.value == "error" for o in restored.snapshot.observations)
    assert sources["admission_record"].truncated
    assert "evaluation_context.horizon" in sources


@pytest.mark.parametrize("mutation", [
    "material", "missing_source", "extra_source", "visit", "snapshot_hash", "fact_id", "fact_value",
    "fact_ids", "document_refs", "record_count_bool", "extra_fact_field", "confidence_bool", "unknown_field",
    "source_ref", "missing_fact", "bad_coordinate", "fact_cycle", "duplicate_fact",
])
def test_mismatched_or_unresolved_inputs_fail_closed(mutation):
    _, data = fixture()
    coordinates = ("I", "P", "V")
    snap = data["snapshot"]
    if mutation == "material":
        data["sources"]["admission_record"]["rows"] = ({"record_content": "changed"},) * 3
    elif mutation == "missing_source":
        del data["sources"]["admission_record"]
    elif mutation == "extra_source":
        data["sources"]["unknown"] = {"rows": (), "truncated": False, "limit_rows": 1}
    elif mutation == "visit":
        coordinates = ("I", "P", "another")
    elif mutation in {"snapshot_hash", "source_ref"}:
        target = snap if mutation == "snapshot_hash" else snap["observations"][0]
        target["snapshot_hash" if mutation == "snapshot_hash" else "snapshot_ref"] = "0" * 64
    elif mutation == "fact_id":
        snap["facts"][0]["fact_id"] = "0" * 64
    elif mutation == "fact_value":
        snap["facts"][0]["normalized_value"] = "changed"
    elif mutation in {"fact_ids", "document_refs"}:
        snap[mutation].append("0" * 64)
    elif mutation == "record_count_bool":
        snap["observations"][0]["record_count"] = True
    elif mutation == "extra_fact_field":
        snap["facts"][0]["untrusted_field"] = "never execute"
    elif mutation == "confidence_bool":
        snap["facts"][0]["confidence"] = True
    elif mutation == "unknown_field":
        data["unapproved"] = "value"
    elif mutation == "missing_fact":
        snap["facts"].pop()
    elif mutation == "bad_coordinate":
        coordinates = ("I", "P", "")
    elif mutation == "duplicate_fact":
        snap["facts"].append(deepcopy(snap["facts"][0]))
    elif mutation == "fact_cycle":
        fact = snap["facts"][0]
        fact["extensions"] = {"test": {"derived_from_fact_ids": [fact["fact_id"]]}}
    with pytest.raises(DiagnosticPackageError, match="invalid_execution_session_archive"):
        restore_execution_session(data, coordinates=coordinates)


def test_custom_objects_are_rejected_before_serialization():
    class Unsafe:
        def __repr__(self):
            pytest.fail("custom code must never execute")
        __str__ = __repr__
    _, inputs = fixture()
    inputs["sources"]["admission_record"]["rows"] = ({"record_content": Unsafe()},)
    with pytest.raises(DiagnosticPackageError, match="invalid_execution_session_archive"):
        restore_execution_session(inputs, coordinates=("I", "P", "V"))


def test_derived_facts_are_restored_by_dependencies_not_hash_sort_order():
    from app.services.luxian_0609.evidence_snapshot import Luxian0609EvidenceSnapshot
    from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore, Luxian0609EvidenceReadSession
    from tests.unit.test_luxian_0609_fact_schema import _fact, _projection

    original, _ = fixture()
    snapshot = original.snapshot
    source = snapshot.observations[0]
    first = _fact(visit_ref=snapshot.visit_ref, source_key=source.source_key,
                  source_snapshot_hash=source.snapshot_ref.removeprefix("sha256:"))
    second = _fact(visit_ref=snapshot.visit_ref, source_key=source.source_key,
                   source_snapshot_hash=source.snapshot_ref.removeprefix("sha256:"),
                   extensions={"test": _projection(derived_from_fact_ids=[first.fact_id])},
                   known_upstream_fact_ids=[first.fact_id])
    rebuilt_snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="I", patient_id="P", visit_id="V", observations=snapshot.observations,
        facts=(second, first), document_refs=snapshot.document_refs, created_at=snapshot.created_at,
        snapshot_schema_version=snapshot.snapshot_schema_version,
        source_registry_version=snapshot.source_registry_version,
    )
    materials = Luxian0609EvidenceMaterialStore.create(
        snapshot=rebuilt_snapshot, sources=original.materials.diagnostic_sources(snapshot=snapshot),
    )
    data = freeze_execution_inputs(
        Luxian0609EvidenceReadSession(snapshot=rebuilt_snapshot, materials=materials),
        selected_rule_ids=("LX0609-03-01-01",), evaluation_as_of_date="2026-07-05",
        evaluation_horizon_policy=None, horizon_unavailable_reason=None,
    )
    restored = restore_execution_session(data, coordinates=("I", "P", "V"))
    assert [f.to_dict() for f in restored.snapshot.facts] == [f.to_dict() for f in rebuilt_snapshot.facts]
    # 即使一个格式正确的引用指向包中不存在的事实也不能继续。
    target = next(f for f in data["snapshot"]["facts"] if f["extensions"])
    target["extensions"]["test"]["derived_from_fact_ids"] = ["f" * 64]
    with pytest.raises(DiagnosticPackageError):
        restore_execution_session(data, coordinates=("I", "P", "V"))


def test_self_consistent_snapshot_still_cannot_omit_clinical_document_refs():
    from app.services.luxian_0609.evidence_snapshot import Luxian0609EvidenceSnapshot
    original, data = fixture()
    snapshot = original.snapshot
    forged = Luxian0609EvidenceSnapshot.create(
        institute_id="I", patient_id="P", visit_id="V", observations=snapshot.observations,
        facts=snapshot.facts, document_refs=(), created_at=snapshot.created_at,
        snapshot_schema_version=snapshot.snapshot_schema_version,
        source_registry_version=snapshot.source_registry_version,
    )
    data["snapshot"] = {**forged.to_safe_dict(), "facts": [f.to_dict() for f in forged.facts]}
    with pytest.raises(DiagnosticPackageError):
        restore_execution_session(data, coordinates=("I", "P", "V"))


def test_failure_never_formats_patient_data_or_underlying_exception():
    import traceback
    _, inputs = fixture()
    inputs["snapshot"]["observations"][0]["source_key"] = "PRIVATE_PATIENT_病人"
    with pytest.raises(DiagnosticPackageError) as caught:
        restore_execution_session(inputs, coordinates=("I", "P", "V"))
    assert "PRIVATE_PATIENT" not in str(caught.value)
    assert "PRIVATE_PATIENT" not in repr(caught.value)
    assert "PRIVATE_PATIENT" not in "".join(traceback.format_exception(caught.value))


def test_input_mutation_after_restore_cannot_change_materials():
    _, inputs = fixture()
    restored = restore_execution_session(inputs, coordinates=("I", "P", "V"))
    before = restored.snapshot.canonical_json()
    inputs["snapshot"]["facts"].clear()
    inputs["sources"]["admission_record"]["rows"] = ({"record_content": "changed"},)
    assert restored.snapshot.canonical_json() == before
    rows = restored.materials.diagnostic_sources(snapshot=restored.snapshot)["admission_record"].rows
    assert rows == ({"record_content": None}, {"record_content": ""}, {"record_content": ""})
