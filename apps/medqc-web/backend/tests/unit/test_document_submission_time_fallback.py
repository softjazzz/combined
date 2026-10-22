"""文书时间各入口统一回退提交时间，保持业务事件时间独立。"""
from datetime import datetime

import pytest

from app.services.luxian_0609 import native_consultation_execution as consultation
from app.services.luxian_0609 import native_preop_content_execution as preop
from app.services.luxian_0609 import pretransfusion_assessment as transfusion
from app.services.luxian_0609 import runtime_shadow_input_provider as provider
from app.services.luxian_0609 import source_evidence_reader as reader
from app.services.luxian_0609 import native_surgery_gate_execution as surgery
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows, build_luxian_0609_evidence_read_session,
)


@pytest.mark.parametrize("field", reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS)
def test_preop_clock_and_consultation_projection_keep_all_document_time_aliases(field):
    row = {"document_id": "doc", "record_time": " ", field: "2026-01-01 08:00:00",
           "record_content": "会诊意见：完善检查。"}
    assert preop._document_record_time(row) == datetime(2026, 1, 1, 8)
    assert "2026-01-01 08:00:00" in consultation._project_row("daily_course_record", row, 1)


@pytest.mark.parametrize("field", ["submit_time", "submit_datetime"])
def test_transfusion_course_window_uses_submission_only_if_record_missing(field):
    row = {"document_id": "doc", field: "2026-01-02 08:00:00", "record_content": "血红蛋白低，拟输血。"}
    documents = {"daily_course_record": [row]}
    content, refs = transfusion._pretransfusion_course_text(documents, datetime(2026, 1, 2, 9))
    assert "血红蛋白低" in content
    assert refs == (("daily_course_record", "doc"),)
    row["record_time"] = "2026-01-03 08:00:00"
    assert transfusion._pretransfusion_course_text(documents, datetime(2026, 1, 2, 9)) == ("", ())


@pytest.mark.parametrize("source", ["presurg_summary", "surgery_safecheck_record"])
def test_snapshot_does_not_strip_document_time_aliases(source):
    assert set(reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS) <= set(reader._SNAPSHOT_SOURCE_FIELDS[source])


@pytest.mark.parametrize("value", ["2026-01-01T00:00:00+00:00", datetime.fromisoformat("2026-01-01T00:00:00+00:00")])
def test_shadow_document_clock_accepts_submission_formats_and_converts_hospital_timezone(value):
    assert provider._parse_presurg_record_time(value) == datetime(2026, 1, 1, 8)


def test_shadow_hash_tracks_effective_document_time():
    a = {"record_content": "完整术前小结内容", "submit_time": "2026-01-01 08:00:00"}
    b = {**a, "submit_time": "2026-01-01 09:00:00"}
    assert provider._target_qualification_material_hash("presurg_summary", a) != provider._target_qualification_material_hash("presurg_summary", b)
    assert provider._target_qualification_material_hash("presurg_summary", a) == provider._target_qualification_material_hash("presurg_summary", {**a, "record_time": a["submit_time"]})


@pytest.mark.parametrize("clock", [preop._document_record_time, lambda r: provider._parse_presurg_record_time(reader.authoritative_document_time_value(r))])
def test_document_fallback_does_not_use_sync_time_or_incomplete_date(clock):
    assert clock({"update_time": "2026-01-01 08:00:00"}) is None
    assert clock({"submit_time": "2026-01-01"}) is None
    assert clock({"record_time": "2026-01-01 07:00:00", "submit_time": "2026-01-01 09:00:00"}) == datetime(2026, 1, 1, 7)


@pytest.mark.parametrize("field", ["submit_time", "submit_datetime"])
@pytest.mark.parametrize("hours,expected_reason", [(1, "requirement_within_threshold"), (25, "threshold_exceeded")])
def test_surgery_record_24_hour_decision_reads_submission_without_replacing_surgery_end(field, hours, expected_reason):
    from datetime import timedelta
    end = datetime(2026, 1, 1, 9)
    def source_rows(**kwargs):
        rows = [{"document_id": "surgery-doc", "record_time": None,
                 "surgery_begin_time": datetime(2026, 1, 1, 8),
                 "surgery_end_time": end, field: end + timedelta(hours=hours)}] if kwargs["source_key"] == "surgery_record" else []
        return SnapshotSourceRows.create(source_key=kwargs["source_key"], rows=rows, truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-02-01",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-07-16T12:00:00+08:00", row_reader=source_rows,
    )
    decision = surgery._typed_003_decision(snapshot=session.snapshot, materials=session.materials, customer_display_facts=[])
    assert decision.reason_code == expected_reason


@pytest.mark.parametrize("field", reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS)
def test_compatibility_fact_and_programmatic_inputs_keep_document_clocks(field):
    from app.services import luxian_0609_fact_extraction as facts
    from app.services import luxian_0609_programmatic_rules as rules
    row = {field: "2026-01-01 08:00:00", "display_time": "2026-01-02 09:00:00"}
    assert facts._document_time(row) == row[field]
    assert rules._document_time(row) == datetime(2026, 1, 1, 8)


@pytest.mark.parametrize("field", reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS)
def test_surgery_model_projection_uses_effective_clock_with_actual_field_role(field):
    from app.services.luxian_0609.surgery_text_fact_contract import build_surgery_text_projection
    row = {"document_id": "doc", "record_content": "术中情况完整记录。", field: "2026-01-01 08:00:00"}
    projection = build_surgery_text_projection(rows_by_source={"surgery_record": [row]})
    assert any(candidate.field_role == field for candidate in projection.time_candidates.values())
    if field in ("submit_time", "submit_datetime"):
        row["record_time"] = "2026-01-01 07:00:00"
        projection = build_surgery_text_projection(rows_by_source={"surgery_record": [row]})
        assert all(candidate.field_role != field for candidate in projection.time_candidates.values())


@pytest.mark.parametrize("field", reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS)
def test_anesthesia_visit_completeness_accepts_each_document_clock_alias(monkeypatch, field):
    from app.services.luxian_0609 import native_surgery_document_execution as visits
    monkeypatch.setattr(visits, "_anesthesia_visit_rows", lambda _materials, source: ({field: "2026-01-01 08:00:00"},))
    _state, missing = visits._anesthesia_visit_completeness(None)
    assert all("record_time" not in fields for fields in missing.values())


def test_runtime_preop_reader_selects_submission_columns(monkeypatch):
    from contextlib import contextmanager
    class Connection:
        def execute(self, statement, _params):
            sql = str(statement).split(" FROM ")[0]
            for field in reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS:
                assert f'"{field}"' in sql
            return self
        def mappings(self): return self
        def all(self): return [{"record_time": None, "submit_time": "2026-01-01 08:00:00", "record_content": "术前小结"}]
    class Engine:
        @contextmanager
        def connect(self): yield Connection()
    monkeypatch.setattr(reader.bundle_assembly, "engine", Engine())
    monkeypatch.setattr(reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(reader.bundle_assembly, "_get_table_columns", lambda *_: (
        "institute_id", "patient_id", "visit_id", "record_content", *reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS))
    rows = reader.read_luxian_0609_runtime_source_rows(
        source_key="presurg_summary", institute_id="I", patient_id="P", visit_id="V", source_schema="cdm")
    assert reader.authoritative_document_time_value(rows[0]) == "2026-01-01 08:00:00"
