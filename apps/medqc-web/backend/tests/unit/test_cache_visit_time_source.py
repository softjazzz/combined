"""当前登记时间与历史首页投影合同；数据均虚构，不连接医院或模型。"""

from contextlib import contextmanager
from datetime import date, datetime

import pytest

from app.services.luxian_0609 import source_evidence_reader as reader
from app.services.luxian_0609.basic_timeliness_facts import (
    AdmissionAnchorState, extract_admission_anchor,
)
from app.services.luxian_0609.cache_visit_time_source import project_mr_visit_times
from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_registry import resolve_luxian_0609_physical_source_entry

KEYS = ("institute_id", "patient_id", "visit_id")
TIMES = {"admission_datetime": "2026-10-26 08:30:00", "discharge_datetime": "2026-10-28 15:00:00"}


class Rows:
    def __init__(self, values):
        self.values = values

    def mappings(self):
        return self

    def all(self):
        return self.values


class Connection:
    def __init__(self, registration, mr, fail_registration=False):
        self.registration, self.mr = registration, mr
        self.fail_registration = fail_registration
        self.calls = []

    def execute(self, statement, params):
        sql = str(statement)
        self.calls.append((sql, dict(params)))
        if '"inpat_registration"' in sql:
            if self.fail_registration:
                raise RuntimeError("fictional database error")
            return Rows(self.registration)
        if '"mr"' in sql:
            return Rows(self.mr)
        return Rows([])

    @contextmanager
    def connect(self):
        yield self


def install(monkeypatch, registration=(), mr=None, has_registration=True, fail_registration=False):
    connection = Connection(list(registration), [dict(TIMES)] if mr is None else mr,
                            fail_registration)
    monkeypatch.setattr(reader.bundle_assembly, "engine", connection)
    monkeypatch.setattr(reader, "_case_source_schema", lambda **_: "cdm")
    monkeypatch.setattr(reader.bundle_assembly, "_get_table_columns", lambda _, table: (
        [*KEYS, *TIMES] if table == "mr" or table == "inpat_registration" and has_registration
        else []
    ))
    return connection


def read():
    return reader.read_luxian_0609_snapshot_source_rows(
        source_key="inpat_registration", institute_id="fictional-I", patient_id="fictional-P",
        visit_id="fictional-V", source_schema="cdm",
    )


@pytest.mark.parametrize("has_registration", [True, False])
def test_empty_or_absent_registration_never_falls_back_to_homepage(monkeypatch, has_registration):
    connection = install(monkeypatch, has_registration=has_registration)
    if has_registration:
        result = read()
        assert result.source_key == "inpat_registration" and not result.truncated
        assert result.rows == ()
    else:
        with pytest.raises(reader.SourceEvidenceUnavailable):
            read()
    assert not any('"mr"' in sql for sql, _ in connection.calls)


def test_existing_registration_is_preserved_without_mr_merge(monkeypatch):
    original = {"admission_datetime": "2026-10-25 12:00:00", "patient_status": "original"}
    connection = install(monkeypatch, registration=[original])
    result = read()
    assert dict(result.rows[0]) == original
    assert not any('"mr"' in sql for sql, _ in connection.calls)
    assert len(connection.calls) == 1
    sql, params = connection.calls[0]
    for key in KEYS:
        assert f'"{key}" = :{key}' in sql
    assert {key: params[key] for key in KEYS} == dict(
        zip(KEYS, ("fictional-I", "fictional-P", "fictional-V"))
    )
    assert params["limit_rows"] == result.limit_rows + 1
    assert "fictional" not in sql


def test_primary_query_error_is_not_hidden_by_fallback(monkeypatch):
    connection = install(monkeypatch, fail_registration=True)
    with pytest.raises(reader.SourceEvidenceQueryError):
        read()
    assert not any('"mr"' in sql for sql, _ in connection.calls)


@pytest.mark.parametrize("values", [[], [dict(TIMES), dict(TIMES)]])
def test_homepage_cardinality_does_not_change_empty_registration(monkeypatch, values):
    connection = install(monkeypatch, mr=values)
    assert read().rows == ()
    assert not any('"mr"' in sql for sql, _ in connection.calls)


@pytest.mark.parametrize("admission", ["2026-10-26", date(2026, 10, 26), "1840-12-31 00:00:00", None])
def test_date_only_placeholder_or_missing_admission_is_not_an_exact_time(admission):
    assert project_mr_visit_times([{**TIMES, "admission_datetime": admission}]) is None


def test_offset_is_converted_without_assuming_utc_for_naive_time():
    assert project_mr_visit_times([{"admission_datetime": "2026-10-26T00:30:00Z"}]) == {
        "admission_datetime": datetime(2026, 10, 26, 8, 30)
    }
    assert project_mr_visit_times([{"admission_datetime": TIMES["admission_datetime"]}]) == {
        "admission_datetime": datetime(2026, 10, 26, 8, 30)
    }


def test_null_discharge_does_not_generate_inpatient_or_death_status():
    result = project_mr_visit_times([{**TIMES, "discharge_datetime": None}])
    assert result == {"admission_datetime": datetime(2026, 10, 26, 8, 30)}


@pytest.mark.parametrize("discharge", ["1840-12-31 00:00:00", "2026-10-25 08:00:00"])
def test_invalid_or_reversed_discharge_is_rejected(discharge):
    assert project_mr_visit_times([{**TIMES, "discharge_datetime": discharge}]) is None


def test_formal_rule_anchor_and_session_receive_registration_time(monkeypatch):
    install(monkeypatch, registration=[dict(TIMES)])
    material = read()
    anchor = extract_admission_anchor(
        registration_rows=material.rows, admission_rows=(), discharge_rows=(),
        allow_date_fallback=False,
    )
    assert anchor.state is AdmissionAnchorState.EXACT
    assert anchor.anchor_time == datetime(2026, 10, 26, 8, 30)

    def row_reader(**kwargs):
        if kwargs["source_key"] == "inpat_registration":
            return reader.read_luxian_0609_snapshot_source_rows(**kwargs)
        return reader.SnapshotSourceRows.create(
            source_key=kwargs["source_key"], rows=(), truncated=False, limit_rows=200,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-01-01-01",), institute_id="fictional-I",
        patient_id="fictional-P", visit_id="fictional-V", source_schema="cdm",
        created_at="2026-10-29T12:00:00+08:00", evaluation_as_of_date="2026-10-29",
        row_reader=row_reader,
    )
    entry = resolve_luxian_0609_physical_source_entry("inpat_registration")
    assert entry.query_version == "snapshot-provider-inpat_registration-v3"
    assert entry.physical_source_keys == ("inpat_registration",)
    assert session.materials.rows("inpat_registration")[0]["admission_datetime"] == (
        TIMES["admission_datetime"]
    )
    observation = next(o for o in session.snapshot.observations
                       if o.source_key == "inpat_registration")
    assert observation.query_state.value == "available"
    assert observation.query_version == entry.query_version


@pytest.mark.parametrize("completion,expected", [
    ("2026-10-27 08:30:00", "compliant"),
    ("2026-10-27 08:30:01", "non_compliant"),
])
def test_registration_time_drives_formal_admission_rule_without_model(monkeypatch, completion, expected):
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.native_basic_timeliness import (
        execute_luxian_0609_native_basic_timeliness,
    )

    install(monkeypatch, registration=[dict(TIMES)])

    def row_reader(**kwargs):
        key = kwargs["source_key"]
        if key == "inpat_registration":
            return reader.read_luxian_0609_snapshot_source_rows(**kwargs)
        rows = [{"document_id": "fictional-A", "record_datetime": completion,
                 "record_content": "虚构测试文书"}] if key == "admission_record" else []
        return reader.SnapshotSourceRows.create(
            source_key=key, rows=rows, truncated=False, limit_rows=50,
        )

    rule = "LX0609-01-01-01"
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="fictional-I", patient_id="fictional-P",
        visit_id="fictional-V", source_schema="cdm", created_at="2026-10-29T12:00:00+08:00",
        evaluation_as_of_date="2026-10-29", row_reader=row_reader,
    )
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_payload=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    decisions = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert decisions[0].final_state.value == expected
    assert getattr(execution, "llm_call_count", 0) == 0
