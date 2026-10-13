from datetime import date, datetime
import pytest
from app.services.etl_sync import _apply_sync_column_aliases
from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.source_evidence_reader import (
    _SNAPSHOT_SOURCE_FIELDS,
    SnapshotSourceRows,
    _normalize_snapshot_source_row,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_basic_timeliness import (
    execute_luxian_0609_native_basic_timeliness,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)


@pytest.mark.parametrize(
    "field,stamp,expected",
    [
        ("last_modified_time", "2026-10-03 08:00:00", "data_gap"),
        ("last_modified_datetime", "2026-10-03 08:00:00", "data_gap"),
        ("record_time", "2026-10-01 16:00:00", "compliant"),
        ("record_datetime", "2026-10-01 16:00:01", "non_compliant"),
        ("submit_time", "2026-10-01 09:00:00", "compliant"),
        ("submit_datetime", "2026-10-03 08:00:00", "non_compliant"),
        ("physician_sign_time", "2026-10-01 09:00:00", "compliant"),
    ],
)
def test_first_course_completion_source_through_formal_chain(field, stamp, expected):
    row = {
        "document_id": "SYN-D",
        "record_content": "合成首程：病情稳定，已记录诊疗经过。",
        field: stamp,
    }
    mapped = _apply_sync_column_aliases(
        table_name="first_course_record",
        record=row,
        existing_columns=set(row) | {"record_datetime"},
    )
    rows = {
        "inpat_registration": [{"admission_datetime": "2026-10-01 08:00:00"}],
        "first_course_record": [mapped],
    }

    def read(**kw):
        key = kw["source_key"]
        projected = [
            _normalize_snapshot_source_row(
                key,
                {
                    f: v
                    for f, v in r.items()
                    if f in _SNAPSHOT_SOURCE_FIELDS.get(key, ())
                },
            )
            for r in rows.get(key, [])
        ]
        return SnapshotSourceRows.create(
            source_key=key, rows=projected, truncated=False, limit_rows=50
        )

    rules = ("LX0609-01-02-01",)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=rules,
        institute_id="SYN-I",
        patient_id="SYN-P",
        visit_id="SYN-V",
        source_schema=None,
        created_at="2026-10-07T12:00:00+08:00",
        evaluation_as_of_date="2026-10-07",
        row_reader=read,
    )
    output = execute_luxian_0609_native_basic_timeliness(
        rule_ids=rules,
        decision_rule_ids=rules,
        evidence_payload=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    result = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=output.decisions,
        expected_rule_ids=rules,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert result[0].final_state.value == expected


@pytest.mark.parametrize(
    "stamp,expected",
    [
        ("2026-10-06 16:30:00+00:00", 1),
        ("2026-10-06T16:30:00Z", 1),
        ("2026-10-07 00:30:00+08:00", 1),
        ("2026-10-07 00:30:00", 1),
        ("2026-10-06 21:30:00+05:00", 1),
        ("2026-10-07 18:30:00+00:00", 0),
        ("2026-10-06 15:59:59+00:00", 0),
        ("2026-10-07 15:59:59+00:00", 1),
        ("2026-10-07", 1),
    ],
)
def test_consultation_candidates_hospital_day(monkeypatch, stamp, expected):
    rows = {
        "exam_master": [
            {
                "exam_id": "SYN",
                "exam_time": stamp,
                "exam_name": "CT",
                "report_result": "synthetic finding",
            }
        ]
    }
    monkeypatch.setattr(
        episode, "_read_rows", lambda **kw: rows.get(kw["source_key"], [])
    )
    result = episode._candidate_documents(
        institute_id="SYN-I",
        patient_id="SYN-P",
        visit_id="SYN-V",
        source_schema=None,
        evidence_materials=None,
        evidence_snapshot=None,
        stay_window=episode._StayWindow(date(2026, 10, 7), date(2026, 10, 7)),
    )
    assert len(result.candidates) == expected
    assert "exam_master" in result.source_complete_keys


@pytest.mark.parametrize(
    "stamp,precise",
    [
        ("2026-10-07", False),
        ("2026/10/07", False),
        ("2026/10/07 00:30:00", True),
        ("2026-10-06T16:30:00Z", True),
    ],
)
def test_consultation_precision_preserved(stamp, precise):
    parsed = episode._parse_observed_time(stamp)
    assert parsed.precise is precise
    assert parsed.day == date(2026, 10, 7)


def test_consultation_offset_preserves_event_order():
    opinion = episode._parse_observed_time("2026-10-07 00:00:00+08:00")
    execution = episode._parse_observed_time("2026-10-06 16:30:00+00:00")
    assert opinion.value < execution.value
    assert execution.value == datetime(2026, 10, 7, 0, 30)
