"""正式 provider 合成输入的统一脱敏与引用闭环，无 DB/模型。"""
from datetime import datetime

import pytest

from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.qc_diagnostics.execution_inputs import freeze_execution_inputs
from app.services.qc_diagnostics.sanitization import PayloadSanitizer
from app.services.qc_diagnostics.session_redaction import sanitize_execution_inputs
from app.services.qc_diagnostics.session_restore import restore_execution_session
from app.services.qc_diagnostics.contracts import DiagnosticPackageError


COORDINATES = ("hospital-test", "patient-test", "visit-test")
RULES = ("LX0609-012", "LX0609-020", "LX0609-029", "LX0609-076")
FIELDS = frozenset({"institute_id", "patient_id", "visit_id", "patient_name", "content",
    "document_id", "record_content", "admission_datetime", "discharge_datetime", "present", "row_ref",
    "horizon_date", "horizon_datetime", "basis", "surgery_order", "complete", "performed", "emergency_rescue"})


def fixture(*, controlled=True):
    def reader(**kwargs):
        key = kwargs["source_key"]
        rows = {
            "admission_record": [{"document_id": "case-doc-1", "record_content": "合成患者甲 于2026-07-01入院"}] * 2,
            "inpat_registration": [{"admission_datetime": "2026-07-01 08:00:00"}],
            "inpat_registration.discharge_horizon": [{"discharge_datetime": "2026-07-03 08:00:00"}],
            "inpat_nondrug_order.unstable_order": [{"present": True}] if controlled else [],
        }.get(key, [])
        return SnapshotSourceRows.create(source_key=key, rows=rows, truncated=False, limit_rows=10)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=RULES, institute_id=COORDINATES[0], patient_id=COORDINATES[1], visit_id=COORDINATES[2],
        source_schema=None, created_at="2026-07-05T00:00:00+08:00", evaluation_as_of_date="2026-07-05",
        additional_source_keys=("admission_record",), row_reader=reader,
    )
    inputs = freeze_execution_inputs(session, selected_rule_ids=RULES, evaluation_as_of_date="2026-07-05",
                                    evaluation_horizon_policy=None, horizon_unavailable_reason=None)
    return session, inputs


def sanitizer(fields=FIELDS):
    return PayloadSanitizer(identities=[], allowed_fields=fields, date_shift_days=7)


@pytest.mark.parametrize("controlled", [True, False])
def test_single_identity_pass_rebuilds_provider_session_and_all_references(controlled, monkeypatch):
    import socket
    import sqlite3
    original, inputs = fixture(controlled=controlled)
    def forbidden(*a, **kw):
        pytest.fail("must not access database or network")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    engine = sanitizer()
    # 姓名仅在附带字段出现；必须先统一发现再转换材料正文，不能分批漏脱敏。
    result = sanitize_execution_inputs(inputs, coordinates=COORDINATES, sanitizer=engine,
        related_values={"patient_name": "合成患者甲", "content": "合成患者甲 于2026-07-03出院"})
    restored = restore_execution_session(result.inputs, coordinates=result.coordinates)
    assert result.coordinates != COORDINATES
    assert "合成患者甲" not in repr(result.inputs)
    alias = result.related_values["patient_name"]
    rows = result.inputs["sources"]["admission_record"]["rows"]
    assert len(rows) == 2 and rows[0] == rows[1]
    assert alias in rows[0]["record_content"] and alias in result.related_values["content"]
    assert "2026-07-08" in rows[0]["record_content"]
    assert "2026-07-10" in result.related_values["content"]
    assert result.inputs["evaluation_as_of_date"] == "2026-07-12"
    assert result.inputs["selected_rule_ids"] == RULES
    old_horizon_ref = inputs["sources"]["evaluation_context.horizon"]["rows"][0]["row_ref"]
    new_horizon_ref = result.inputs["sources"]["evaluation_context.horizon"]["rows"][0]["row_ref"]
    assert new_horizon_ref != old_horizon_ref
    assert result.remap_reference(old_horizon_ref) == new_horizon_ref
    assert old_horizon_ref not in repr(result.inputs)
    assert engine.report()["automatic_export_allowed"] is False
    assert engine.report()["temporal_equivalent"] is True
    for old in original.snapshot.facts:
        new = next(f for f in restored.snapshot.facts if f.fact_id == result.remap_reference(old.fact_id))
        assert new.assertion == old.assertion and new.event_status == old.event_status
        assert new.source_snapshot_hash == result.remap_reference(old.source_snapshot_hash)
        if old.fact_type != "evaluation_horizon":
            assert new.normalized_value == old.normalized_value
    for old in original.snapshot.observations:
        new = next(o for o in restored.snapshot.observations if o.source_key == old.source_key)
        assert new.query_state == old.query_state and new.record_count == old.record_count
        assert new.snapshot_ref == result.remap_reference(old.snapshot_ref)
    mapped = {result.remap_reference(ref) for ref in original.snapshot.document_refs}
    assert mapped == set(restored.snapshot.document_refs)
    assert result.remap_reference(original.snapshot.visit_ref) == restored.snapshot.visit_ref
    assert result.remap_reference(original.snapshot.snapshot_hash) == restored.snapshot.snapshot_hash
    assert "合成患者甲" not in repr(result) and "hospital-test" not in repr(result)


def test_unapproved_related_fields_fail_before_any_export():
    _, inputs = fixture()
    with pytest.raises(DiagnosticPackageError):
        sanitize_execution_inputs(inputs, coordinates=COORDINATES, sanitizer=sanitizer(),
                                  related_values={"authorization": "Bearer never-export"})


def test_unresolved_reference_is_not_silently_kept():
    _, inputs = fixture()
    result = sanitize_execution_inputs(inputs, coordinates=COORDINATES, sanitizer=sanitizer(),
                                      related_values={"patient_name": "合成患者甲"})
    with pytest.raises(DiagnosticPackageError):
        result.remap_reference("f" * 64)


def test_dates_retain_interval_and_source_ownership():
    _, inputs = fixture()
    result = sanitize_execution_inputs(inputs, coordinates=COORDINATES, sanitizer=sanitizer())
    old = inputs["sources"]
    new = result.inputs["sources"]
    def interval(sources):
        start = sources["inpat_registration"]["rows"][0]["admission_datetime"]
        end = sources["inpat_registration.discharge_horizon"]["rows"][0]["discharge_datetime"]
        return datetime.fromisoformat(end) - datetime.fromisoformat(start)
    assert interval(old) == interval(new)


def test_business_enum_overlap_cannot_silently_change_fact():
    _, inputs = fixture()
    with pytest.raises(DiagnosticPackageError, match="redaction_changed_business_fact"):
        sanitize_execution_inputs(inputs, coordinates=COORDINATES, sanitizer=sanitizer(),
                                  related_values={"patient_name": "discharge_date"})


def test_hash_like_row_identity_is_shared_without_reinterpreting_digits():
    from app.services.qc_diagnostics.material_redaction import sanitize_material_sources
    raw_ref = "20260701" + "13800138000" + "a" * 45
    source = SnapshotSourceRows.create(source_key="admission_record",
        rows=({"row_ref": raw_ref, "record_content": "参考 " + raw_ref},), truncated=False, limit_rows=1)
    result = sanitize_material_sources({"admission_record": source}, sanitizer=sanitizer(),
                                      related_values={"content": "参考 " + raw_ref})
    row = result.sources["admission_record"].rows[0]
    assert len(row["row_ref"]) == 64 and set(row["row_ref"]) <= set("abcdef")
    assert row["row_ref"] in row["record_content"] and row["row_ref"] in result.related_values["content"]
    assert raw_ref not in repr(result.related_values)


@pytest.mark.parametrize("kind", ["fact", "document", "visit", "snapshot", "source", "escaped_json"])
def test_related_old_execution_references_require_explicit_projection(kind):
    import json
    original, inputs = fixture()
    snapshot = original.snapshot
    reference = {"fact": snapshot.facts[0].fact_id, "document": snapshot.document_refs[0],
                 "visit": snapshot.visit_ref, "snapshot": snapshot.snapshot_hash,
                 "source": snapshot.observations[0].snapshot_ref,
                 "escaped_json": snapshot.facts[0].fact_id}[kind]
    text = json.dumps({"content": reference}) if kind == "escaped_json" else reference
    if kind == "escaped_json":
        # 验证嵌入 JSON 的转义形式不能绕过普通字符串预检。
        text = text.replace(reference[0], "\\u" + format(ord(reference[0]), "04x"))
    with pytest.raises(DiagnosticPackageError, match="related_execution_references_require_projection"):
        sanitize_execution_inputs(inputs, coordinates=COORDINATES, sanitizer=sanitizer(),
                                  related_values={"content": [text]})
