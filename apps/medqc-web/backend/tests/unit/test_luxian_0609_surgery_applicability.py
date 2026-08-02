from __future__ import annotations

from datetime import datetime

from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)
from app.services.luxian_0609.surgery_applicability import (
    resolve_surgery_applicability,
)


CREATED_AT = "2026-08-02T20:00:00+08:00"


def _session(rows_by_source=None, *, failing_source="", unavailable_source=""):
    rows_by_source = rows_by_source or {}

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == failing_source:
            raise SourceEvidenceQueryError()
        if source_key == unavailable_source:
            raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=tuple(rows_by_source.get(source_key, ())),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-029",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )


def test_no_surgery_is_not_applicable_only_after_complete_empty_sources():
    session = _session()

    result = resolve_surgery_applicability(
        snapshot=session.snapshot, materials=session.materials
    )

    assert result.state == "not_applicable"
    assert result.reason_code == "performed_event_absent"
    assert result.procedure_kind == "none"


def test_non_surgical_operation_does_not_trigger_surgery_rules():
    session = _session(
        {
            "mr_surgery": (
                {
                    "surgery_code": "00.5901",
                    "surgery_name": "冠脉瞬时无波形比值检查[iFR检查]",
                    "surgery_begin_datetime": datetime(2026, 8, 1, 9, 0),
                    "surgical_level": "四级",
                },
            )
        }
    )

    result = resolve_surgery_applicability(
        snapshot=session.snapshot, materials=session.materials
    )

    assert result.state == "not_applicable"
    assert result.procedure_kind == "non_surgical_operation"


def test_performed_level_four_surgery_uses_approved_catalog_level_and_source():
    session = _session(
        {
            "mr_surgery": (
                {
                    "surgery_code": "01.2400X013",
                    "surgery_name": "硬脑膜外血肿清除术",
                    "surgery_begin_datetime": datetime(2026, 8, 1, 9, 0),
                },
            )
        }
    )

    result = resolve_surgery_applicability(
        snapshot=session.snapshot, materials=session.materials
    )

    assert result.is_performed_surgery
    assert result.effective_level == "四级"
    assert result.level_source == "hospital_performance"


def test_source_unavailable_is_data_gap_instead_of_not_applicable():
    session = _session(unavailable_source="surgery_record")

    result = resolve_surgery_applicability(
        snapshot=session.snapshot, materials=session.materials
    )

    assert result.state == "data_gap"
    assert result.reason_code == "source_unavailable"


def test_source_query_error_stays_technical_error():
    session = _session(failing_source="surgery_record")

    result = resolve_surgery_applicability(
        snapshot=session.snapshot, materials=session.materials
    )

    assert result.state == "technical_error"
    assert result.reason_code == "source_query_error"
