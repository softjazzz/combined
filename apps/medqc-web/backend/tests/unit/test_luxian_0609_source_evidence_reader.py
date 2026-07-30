from contextlib import contextmanager
from dataclasses import dataclass

from app.services.luxian_0609 import source_evidence_reader


def test_2496813_structured_course_fields_are_in_source_projection() -> None:
    assert (
        "history_of_present_illness"
        in source_evidence_reader._NATIVE_SOURCE_FIELDS["admission_record"]
    )
    assert (
        "case_characteristic"
        in source_evidence_reader._NATIVE_SOURCE_FIELDS["first_course_record"]
    )


@dataclass
class _Rows:
    rows: list[dict]

    def mappings(self):
        return self

    def all(self):
        return self.rows


class _FilteringConnection:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params):
        sql = str(statement)
        bound = dict(params)
        self.calls.append((sql, bound))
        target_rows = [
            row
            for row in self.rows
            if any(
                token in str(row.get("order_name") or "").upper()
                for token in ("CT", "MRI", "培养", "药敏")
            )
        ]
        return _Rows(target_rows[: bound["limit_rows"]])


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection


class _DischargeFallbackConnection:
    def __init__(self):
        self.calls: list[str] = []

    def execute(self, statement, params):
        sql = str(statement)
        self.calls.append(sql)
        if '"inpat_registration"' in sql:
            return _Rows([])
        if '"mr"' in sql:
            return _Rows([{"discharge_datetime": "2026-07-15 16:20:31"}])
        raise AssertionError(f"unexpected source query: {sql}")


def test_discharge_horizon_reader_falls_back_to_mr_when_registration_has_no_row(
    monkeypatch,
) -> None:
    connection = _DischargeFallbackConnection()
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly, "engine", _Engine(connection)
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, table: (
            ["institute_id", "patient_id", "visit_id", "discharge_datetime"]
            if table in {"inpat_registration", "mr"}
            else []
        ),
    )

    result = source_evidence_reader.read_luxian_0609_discharge_horizon_rows(
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
    )

    assert result.rows[0]["discharge_datetime"] == "2026-07-15 16:20:31"
    assert result.truncated is False
    assert any('"inpat_registration"' in sql for sql in connection.calls)
    assert any('"mr"' in sql for sql in connection.calls)


def test_exam_lab_order_reader_filters_before_limit_so_unrelated_orders_cannot_hide_target(
    monkeypatch,
) -> None:
    """100 条以上无关医嘱不能把当前住院的目标 CT 医嘱挤出受控快照。"""

    connection = _FilteringConnection(
        [
            {
                "order_id": f"OTHER-{index:03d}",
                "order_name": "常规护理",
                "order_status": "新开",
                "prescribed_datetime": f"2026-07-07 08:{index % 60:02d}:00",
            }
            for index in range(120)
        ]
        + [
            {
                "order_id": "TARGET-CT",
                "order_name": "头颅CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-07 14:31:00",
            }
        ]
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly, "engine", _Engine(connection)
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, table: (
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "order_id",
                "order_name",
                "order_status",
                "prescribed_datetime",
            ]
            if table == "inpat_nondrug_order"
            else []
        ),
    )

    result = source_evidence_reader.read_luxian_0609_exam_lab_order_rows(
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
    )

    assert [row["order_id"] for row in result.rows] == ["TARGET-CT"]
    assert result.truncated is False
    sql, params = connection.calls[0]
    assert 'FROM "cdm"."inpat_nondrug_order"' in sql
    assert "UPPER(\"order_name\") LIKE :ct_name" in sql
    assert "\"order_name\" LIKE :magnetic_name" in sql
    assert "\"order_name\" LIKE :nmr_name" in sql
    assert params["limit_rows"] == 51
    assert params["institute_id"] == "safe-institute"
    assert "safe-institute" not in sql
