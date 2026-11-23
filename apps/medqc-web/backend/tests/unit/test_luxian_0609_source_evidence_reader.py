from contextlib import contextmanager
from dataclasses import dataclass

import pytest

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


def test_admission_diagnosis_source_preserves_main_diagnosis_flag() -> None:
    assert (
        "diagnosis_main"
        in source_evidence_reader._NATIVE_SOURCE_FIELDS["admission_record_diagnosis"]
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


class _SourceRowsConnection:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params):
        self.calls.append((str(statement), dict(params)))
        return _Rows(self.rows)


def test_snapshot_reader_projects_real_mr_surgery_primary_identity(monkeypatch) -> None:
    """029 只能依赖实际投影到 EvidenceSnapshot 的 mr_surgery 主键去重。"""

    connection = _SourceRowsConnection(
        [
            {
                "surgery_id": "mr-surgery-1",
                "surgical_level": "二级",
                "surgery_begin_datetime": "2026-01-01 08:00:00",
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
        lambda _schema, _table: [
            "institute_id",
            "patient_id",
            "visit_id",
            "surgery_id",
            "surgical_level",
            "surgery_begin_datetime",
        ],
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key="mr_surgery",
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
    )

    assert result.rows[0]["surgery_id"] == "mr-surgery-1"
    sql, _params = connection.calls[0]
    assert '"surgery_id"' in sql


def test_063_snapshot_reader_projects_mr_diagnosis_identity_order_and_type(
    monkeypatch,
) -> None:
    source_row = {
        "diagnosis_id": "DX-1",
        "document_id": "DOC-1",
        "diagnosis_no": "visit||2",
        "diagnosis_type": "出院诊断",
        "diagnosis_name": "社区获得性肺炎",
    }
    connection = _SourceRowsConnection([source_row])
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
        lambda _schema, _table: [
            "institute_id",
            "patient_id",
            "visit_id",
            *source_row,
        ],
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key="mr_diagnosis",
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
    )

    assert result.rows == (source_row,)
    sql, _params = connection.calls[0]
    assert 'FROM "cdm"."mr_diagnosis"' in sql
    for field in source_row:
        assert f'"{field}"' in sql


def test_063_discharge_diagnosis_snapshot_projection_keeps_type_field() -> None:
    assert "diagnosis_type" in source_evidence_reader._NATIVE_SOURCE_FIELDS[
        "discharge_record_diagnosis"
    ]
    assert "diagnosis_type" in source_evidence_reader._SNAPSHOT_SOURCE_FIELDS[
        "discharge_record_diagnosis"
    ]
    assert "mr_diagnosis" in source_evidence_reader._SNAPSHOT_SOURCE_FIELDS


def test_snapshot_reader_projects_drug_order_planned_start_time(monkeypatch) -> None:
    signature_fields = {
        "repeat_indicator": "临时",
        "drug_specification": "100ml:0.5g",
        "dose_form": "注射剂",
        "medication_duration": "1",
        "last_modified_datetime": "2026-08-19 08:01:00+08",
    }
    connection = _SourceRowsConnection([{
        "order_id": "O-1",
        "generic_name": "美罗培南",
        "prescribed_datetime": "2026-08-19 08:00:00+08",
        "planned_start_datetime": "2026-08-19 10:00:00+08",
        **signature_fields,
    }])
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
        lambda _schema, _table: [
            "institute_id",
            "patient_id",
            "visit_id",
            "order_id",
            "generic_name",
            "prescribed_datetime",
            "planned_start_datetime",
            *signature_fields,
        ],
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key="inpat_drug_order",
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
    )

    assert result.rows[0]["planned_start_datetime"] == "2026-08-19 10:00:00+08"
    assert {field: result.rows[0][field] for field in signature_fields} == signature_fields
    sql, _params = connection.calls[0]
    assert '"planned_start_datetime"' in sql
    assert all(f'"{field}"' in sql for field in signature_fields)


@pytest.mark.parametrize(
    ("source_key", "business_fields", "row"),
    (
        (
            "consultation_record",
            ("request_time", "consultation_time", "record_time"),
            {
                "request_time": "2026-08-19 08:00:00+08",
                "consultation_time": "2026-08-19 10:00:00+08",
                "record_time": "2026-08-19 10:05:00+08",
            },
        ),
        (
            "handoff_record",
            ("shift_time", "handoff_doctor", "record_time"),
            {
                "shift_time": "2026-08-19 11:00:00+08",
                "handoff_doctor": "张医生",
                "record_time": "2026-08-19 11:05:00+08",
            },
        ),
        (
            "handover_record",
            ("shift_time", "handover_doctor", "record_time"),
            {
                "shift_time": "2026-08-19 11:00:00+08",
                "handover_doctor": "李医生",
                "record_time": "2026-08-19 11:05:00+08",
            },
        ),
    ),
)
def test_snapshot_reader_projects_customer_consultation_and_handoff_facts(
    monkeypatch, source_key, business_fields, row
) -> None:
    """069/071 读取缝必须投影已同步的权威时间和交接医生。"""

    source_row = {"document_id": "DOC-1", **row}
    connection = _SourceRowsConnection([source_row])
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
        lambda _schema, _table: [
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            *business_fields,
        ],
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key=source_key,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
    )

    assert result.rows == (source_row,)
    sql, _params = connection.calls[0]
    for field in business_fields:
        assert f'"{field}"' in sql


class _SeverityConnection:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params):
        sql = str(statement)
        self.calls.append((sql, dict(params)))
        rows = self.rows
        if "NOT LIKE :cancelled_name" in sql:
            rows = [
                row
                for row in rows
                if not any(
                    marker in str(row.get("order_name") or "")
                    for marker in ("取消", "撤销", "作废")
                )
            ]
        return _Rows(rows[: params["limit_rows"]])


class _DischargeFallbackConnection:
    def __init__(self, registration_rows=None, discharge_rows=None):
        self.calls: list[tuple[str, dict]] = []
        self.registration_rows = registration_rows or []
        self.discharge_rows = (
            [{"discharge_date": "2026-07-15", "discharge_time": "2026-07-15 16:20:31"}]
            if discharge_rows is None else discharge_rows
        )

    def execute(self, statement, params):
        sql = str(statement)
        self.calls.append((sql, dict(params)))
        if '"inpat_registration"' in sql:
            return _Rows(list(self.registration_rows))
        if '"discharge_record"' in sql:
            return _Rows(list(self.discharge_rows)[:params["limit_rows"]])
        raise AssertionError(f"unexpected source query: {sql}")


def test_discharge_horizon_reader_uses_original_document_when_registration_has_no_row(
    monkeypatch,
) -> None:
    connection = _DischargeFallbackConnection()
    result = _read_horizon_with(monkeypatch, connection)

    assert result.rows[0]["discharge_datetime"] == "2026-07-15 16:20:31"
    assert result.rows[0]["time_source"] == "discharge_record.discharge_time"
    assert result.rows[0]["row_ref"] == source_evidence_reader.digest_source_evidence((
        source_evidence_reader.CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
        "discharge_record", connection.discharge_rows[0],
    ))
    assert result.truncated is False
    assert len(connection.calls) == 2
    assert '"inpat_registration"' in connection.calls[0][0]
    assert '"discharge_record"' in connection.calls[1][0]
    for sql, params in connection.calls:
        for key, value in (("institute_id", "safe-institute"), ("patient_id", "safe-patient"), ("visit_id", "safe-visit")):
            assert f'"{key}" = :{key}' in sql
            assert params[key] == value and value not in sql
        assert params["limit_rows"] == 2
        assert '"mr"' not in sql


def _read_horizon_with(monkeypatch, connection):
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly, "engine", _Engine(connection)
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm"
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, table: {
            "inpat_registration": ["institute_id", "patient_id", "visit_id", "discharge_datetime"],
            "discharge_record": ["institute_id", "patient_id", "visit_id", "discharge_date", "discharge_time"],
        }.get(table, []),
    )
    return source_evidence_reader.read_luxian_0609_discharge_horizon_rows(
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
    )


@pytest.mark.parametrize("blank", [None, "", "  "])
def test_discharge_horizon_reader_uses_original_document_when_registration_time_is_blank(
    monkeypatch, blank
) -> None:
    # 登记有行但时间为空时，采用原始出院文书，不能静默落回评价日。
    connection = _DischargeFallbackConnection([{"discharge_datetime": blank}])
    result = _read_horizon_with(monkeypatch, connection)
    assert result.rows[0]["discharge_datetime"] == "2026-07-15 16:20:31"
    assert result.rows[0]["time_source"] == "discharge_record.discharge_time"
    assert not any('"mr"' in sql for sql, _ in connection.calls)


def test_discharge_horizon_reader_prefers_registration_time_when_present(monkeypatch) -> None:
    connection = _DischargeFallbackConnection([{"discharge_datetime": "2026-07-14 10:00:00"}])
    result = _read_horizon_with(monkeypatch, connection)
    assert result.rows[0]["discharge_datetime"] == "2026-07-14 10:00:00"
    assert result.rows[0]["time_source"] == "inpat_registration.discharge_datetime"
    assert len(connection.calls) == 1
    assert not any('"mr"' in sql for sql, _ in connection.calls)


@pytest.mark.parametrize("document_count", [0, 2])
def test_discharge_horizon_reader_keeps_empty_or_ambiguous_original_source_without_homepage(
    monkeypatch, document_count,
) -> None:
    row = {"discharge_date": "2026-07-15", "discharge_time": "2026-07-15 16:20:31"}
    connection = _DischargeFallbackConnection(discharge_rows=[dict(row) for _ in range(document_count)])
    result = _read_horizon_with(monkeypatch, connection)
    assert len(result.rows) == min(document_count, 1)
    assert result.truncated is (document_count > 1)
    assert result.limit_rows == 1
    assert not any('"mr"' in sql for sql, _ in connection.calls)


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
    assert params["limit_rows"] == 301  # 检查检验医嘱读取上限 300（多读 1 行判截断）
    assert params["institute_id"] == "safe-institute"
    assert "safe-institute" not in sql


def test_rescue_order_reader_filters_before_limit_and_preserves_audited_status(
    monkeypatch,
) -> None:
    class _RescueOrderConnection(_SourceRowsConnection):
        def execute(self, statement, params):
            sql = str(statement)
            bound = dict(params)
            self.calls.append((sql, bound))
            accepted_names = {
                bound["small_rescue"],
                bound["medium_rescue"],
                bound["small_rescue_free_ascii"],
                bound["small_rescue_free_full"],
            }
            cancelled_statuses = {
                bound["cancelled_status"],
                bound["revoked_status"],
                bound["voided_status"],
            }
            filtered = [
                row
                for row in self.rows
                if row.get("order_name") in accepted_names
                and (
                    row.get("order_status") is None
                    or row.get("order_status") not in cancelled_statuses
                )
            ]
            return _Rows(filtered[: bound["limit_rows"]])

    connection = _RescueOrderConnection(
        [
            {
                "order_id": f"OTHER-{index:03d}",
                "order_name": "常规护理",
                "order_status": "执行中",
            }
            for index in range(120)
        ]
        + [
            {
                "order_id": f"CANCELLED-{index:03d}",
                "order_name": "小抢救",
                "order_status": "取消",
            }
            for index in range(60)
        ]
        + [
            {"order_id": "ACTIVE", "order_name": "小抢救", "order_status": "执行中"},
            {"order_id": "STOPPED", "order_name": "中抢救", "order_status": "已停止"},
            {"order_id": "UNKNOWN", "order_name": "小抢救", "order_status": "待确认"},
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
        lambda _schema, _table: [
            "institute_id",
            "patient_id",
            "visit_id",
            "order_id",
            "order_name",
            "order_status",
        ],
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key=source_evidence_reader.CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
    )

    assert list(result.rows) == [
        {"order_id": "ACTIVE", "status_state": "effective"},
        {"order_id": "STOPPED", "status_state": "effective"},
        {"order_id": "UNKNOWN", "status_state": "unresolved"},
    ]
    assert result.truncated is False
    sql, params = connection.calls[0]
    assert 'FROM "cdm"."inpat_nondrug_order"' in sql
    assert '"order_name" IN' in sql
    assert '"order_status" IS NULL OR "order_status" NOT IN' in sql
    assert params["cancelled_status"] == "取消"
    assert params["revoked_status"] == "撤销"
    assert params["voided_status"] == "作废"
    assert params["limit_rows"] == 51


def test_severity_order_reader_keeps_stop_event_for_interval_cutoff(monkeypatch) -> None:
    connection = _SeverityConnection(
        [
            {
                "order_id": "START-1",
                "order_name": "病重通知",
                "order_status": "执行中",
                "prescribed_datetime": "2026-01-01 08:00:00",
            },
            {
                "order_id": "STOP-1",
                "order_name": "停止病重",
                "order_status": "停止",
                "prescribed_datetime": "2026-01-02 08:00:00",
            },
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
        lambda _schema, _table: [
            "institute_id",
            "patient_id",
            "visit_id",
            "order_id",
            "order_name",
            "order_status",
            "prescribed_datetime",
        ],
    )

    result = source_evidence_reader.read_luxian_0609_severity_order_rows(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None
    )

    assert [(row["severity"], row["event_kind"]) for row in result.rows] == [
        ("serious", "start"),
        ("serious", "end"),
    ]
    assert "NOT LIKE :cancelled_name" in connection.calls[0][0]


def test_severity_order_reader_preserves_same_row_lifecycle_times(monkeypatch) -> None:
    connection = _SeverityConnection(
        [
            {
                "order_id": "CRITICAL-STOPPED",
                "order_name": "病危",
                "order_status": "停止",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "planned_start_datetime": "2026-01-01 09:00:00",
                "planned_end_datetime": "2026-01-02 10:00:00",
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
        lambda _schema, _table: [
            "institute_id",
            "patient_id",
            "visit_id",
            "order_id",
            "order_name",
            "order_status",
            "prescribed_datetime",
            "planned_start_datetime",
            "planned_end_datetime",
        ],
    )

    result = source_evidence_reader.read_luxian_0609_severity_order_rows(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None
    )

    assert len(result.rows) == 1
    row = result.rows[0]
    assert row["severity"] == "critical"
    assert row["event_kind"] == "start"
    assert row["lifecycle_state"] == "stopped"
    assert row["planned_start_datetime"] == "2026-01-01 09:00:00"
    assert row["planned_end_datetime"] == "2026-01-02 10:00:00"
    sql = connection.calls[0][0]
    assert '"planned_start_datetime"' in sql
    assert '"planned_end_datetime"' in sql


def test_severity_order_reader_filters_cancelled_rows_before_limit(monkeypatch) -> None:
    """取消历史不能占满受控上限而掩盖后续有效病危医嘱。"""

    connection = _SeverityConnection(
        [
            {
                "order_id": f"CANCEL-{index:03d}",
                "order_name": "取消病重通知",
                "order_status": "取消",
                "prescribed_datetime": f"2026-01-01 08:{index % 60:02d}:00",
            }
            for index in range(51)
        ]
        + [
            {
                "order_id": "ACTIVE-CRITICAL",
                "order_name": "病危通知",
                "order_status": "执行中",
                "prescribed_datetime": "2026-01-02 08:00:00",
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
        lambda _schema, _table: [
            "institute_id",
            "patient_id",
            "visit_id",
            "order_id",
            "order_name",
            "order_status",
            "prescribed_datetime",
        ],
    )

    result = source_evidence_reader.read_luxian_0609_severity_order_rows(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None
    )

    assert [(row["severity"], row["event_kind"]) for row in result.rows] == [
        ("critical", "start")
    ]
    assert result.truncated is False
    sql, params = connection.calls[0]
    assert "NOT LIKE :cancelled_name" in sql
    assert params["cancelled_name"] == "%取消%"


@pytest.mark.parametrize("snapshot", (False, True))
@pytest.mark.parametrize("new_columns", (False, True))
def test_discharge_reader_keeps_new_evidence_fields_without_changing_document_clocks(
    monkeypatch, snapshot, new_columns,
):
    import json
    import re
    from datetime import datetime, timezone
    from app.services.luxian_0609.extended_document.discharge_documentation import (
        _discharge_record_completion_time,
    )
    from app.services.luxian_0609.native_extended_document_execution import _row_text

    signed = datetime(2026, 10, 1, 0, tzinfo=timezone.utc)
    payload = json.dumps({"cheifphy_sign_time": signed.isoformat(), "private_extra": "JSON_ONLY_MARKER", "items": list(range(5000))})
    row = {"document_id":"D", "record_time":None, "submit_datetime":None,
           "record_content":"合成出院正文。", "chief_physician_sign_datetime":signed, "v2_schema":payload}
    fields = ("chief_physician_sign_datetime", "v2_schema")
    columns = ["institute_id", "patient_id", "visit_id", "document_id", "record_content", "record_time", "submit_datetime"]
    if new_columns:
        columns.extend(fields)

    class ProjectedConnection(_SourceRowsConnection):
        def execute(self, statement, params):
            self.calls.append((str(statement), dict(params)))
            selected = re.findall(r'"([a-z0-9_]+)"', str(statement).split(" FROM ")[0])
            return _Rows([{name: row.get(name) for name in selected}])

    connection = ProjectedConnection([row])
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _Engine(connection))
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_get_table_columns", lambda *_: columns)
    kwargs = dict(source_key="discharge_record", institute_id="I", patient_id="P", visit_id="V", source_schema="cdm")
    if snapshot:
        output = source_evidence_reader.read_luxian_0609_snapshot_source_rows(**kwargs).rows[0]
    else:
        output = source_evidence_reader.read_luxian_0609_native_source_rows(**kwargs)[0]
    selected_sql = connection.calls[0][0].split(" FROM ")[0]
    if new_columns:
        assert output[fields[0]] == signed
        assert output[fields[1]] == payload
        assert all(f'"{field}"' in selected_sql for field in fields)
    else:
        assert all(field not in output and f'"{field}"' not in selected_sql for field in fields)
    assert source_evidence_reader.authoritative_document_time_value(output) is None
    assert _discharge_record_completion_time(output) is None
    assert "JSON_ONLY_MARKER" not in _row_text(output)
    assert _row_text(output) == row["record_content"]
    assert row["record_time"] is None and row["submit_datetime"] is None


def test_discharge_signature_and_json_are_in_both_whitelists_but_not_time_fallbacks():
    fields = {"chief_physician_sign_datetime", "v2_schema"}
    assert fields <= set(source_evidence_reader._NATIVE_SOURCE_FIELDS["discharge_record"])
    assert fields <= set(source_evidence_reader._SNAPSHOT_SOURCE_FIELDS["discharge_record"])
    assert not fields.intersection(source_evidence_reader.AUTHORITATIVE_DOCUMENT_TIME_FIELDS)


def _sqlite_nondrug_order_engine(rows: list[dict], monkeypatch):
    from sqlalchemy import create_engine, text

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE inpat_nondrug_order (
                    institute_id TEXT,
                    patient_id TEXT,
                    visit_id TEXT,
                    order_id TEXT,
                    order_name TEXT,
                    order_status TEXT,
                    prescribed_datetime TEXT,
                    planned_start_datetime TEXT,
                    planned_end_datetime TEXT
                )
                """
            )
        )
        for index, row in enumerate(rows):
            conn.execute(
                text(
                    """
                    INSERT INTO inpat_nondrug_order (
                        institute_id, patient_id, visit_id, order_id, order_name,
                        order_status, prescribed_datetime, planned_start_datetime,
                        planned_end_datetime
                    ) VALUES (
                        :institute_id, :patient_id, :visit_id, :order_id, :order_name,
                        :order_status, :prescribed_datetime, :planned_start_datetime,
                        :planned_end_datetime
                    )
                    """
                ),
                {
                    "institute_id": row.get("institute_id", "I"),
                    "patient_id": row.get("patient_id", "P"),
                    "visit_id": row.get("visit_id", "V"),
                    "order_id": row.get("order_id", f"O-{index}"),
                    "order_name": row.get("order_name"),
                    "order_status": row.get("order_status"),
                    "prescribed_datetime": row.get("prescribed_datetime"),
                    "planned_start_datetime": row.get("planned_start_datetime"),
                    "planned_end_datetime": row.get("planned_end_datetime"),
                },
            )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly, "_source_engine", lambda _schema: engine
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "main"
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_qualified_table",
        lambda _schema, table: f'"{table}"',
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _table: [
            "institute_id",
            "patient_id",
            "visit_id",
            "order_id",
            "order_name",
            "order_status",
            "prescribed_datetime",
            "planned_start_datetime",
            "planned_end_datetime",
        ],
    )
    return engine


@pytest.mark.parametrize(
    ("order_name", "order_status"),
    [
        ("病危", "取消"),
        ("病重", "撤销"),
        ("病危通知", "作废"),
        ("病重", "已取消"),
        ("病危", "已撤销"),
        ("病重通知", "已作废"),
        ("病危", "未执行"),
        ("病重", " 取消 "),
        ("取消病危", "执行中"),
        ("撤销病重", "新开"),
        ("作废病危", "停止"),
    ],
)
def test_unstable_order_ignores_void_and_never_effective_orders(
    monkeypatch, order_name: str, order_status: str
) -> None:
    _sqlite_nondrug_order_engine(
        [{"order_name": order_name, "order_status": order_status}], monkeypatch
    )

    present = source_evidence_reader.has_luxian_0609_current_visit_unstable_order(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None
    )

    assert present is False


@pytest.mark.parametrize(
    "order_status",
    ["新开", "执行中", "执行", "核实", "停止", "已停止", " 停止 "],
)
def test_unstable_order_detects_effective_and_stopped_after_effective_orders(
    monkeypatch, order_status: str
) -> None:
    _sqlite_nondrug_order_engine(
        [
            {"order_name": "病重", "order_status": "取消"},
            {"order_name": "病危", "order_status": order_status},
        ],
        monkeypatch,
    )

    present = source_evidence_reader.has_luxian_0609_current_visit_unstable_order(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None
    )

    assert present is True


@pytest.mark.parametrize("order_status", [None, "", "   ", "待确认"])
def test_unstable_order_raises_unavailable_when_only_unresolved_status_exists(
    monkeypatch, order_status
) -> None:
    _sqlite_nondrug_order_engine(
        [{"order_name": "病危", "order_status": order_status}], monkeypatch
    )

    with pytest.raises(source_evidence_reader.SourceEvidenceUnavailable):
        source_evidence_reader.has_luxian_0609_current_visit_unstable_order(
            institute_id="I", patient_id="P", visit_id="V", source_schema=None
        )


def test_unstable_order_returns_true_when_effective_order_coexists_with_unresolved(
    monkeypatch,
) -> None:
    _sqlite_nondrug_order_engine(
        [
            {"order_name": "病重", "order_status": None},
            {"order_name": "病危", "order_status": "停止"},
        ],
        monkeypatch,
    )

    assert (
        source_evidence_reader.has_luxian_0609_current_visit_unstable_order(
            institute_id="I", patient_id="P", visit_id="V", source_schema=None
        )
        is True
    )


def test_unstable_order_without_status_column_still_filters_cancelled_names(
    monkeypatch,
) -> None:
    _sqlite_nondrug_order_engine(
        [{"order_name": "取消病危", "order_status": "取消"}], monkeypatch
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _table: ["institute_id", "patient_id", "visit_id", "order_name"],
    )

    assert (
        source_evidence_reader.has_luxian_0609_current_visit_unstable_order(
            institute_id="I", patient_id="P", visit_id="V", source_schema=None
        )
        is False
    )


def test_severity_order_reader_filters_excluded_statuses_before_limit_and_keeps_null_unresolved(
    monkeypatch,
) -> None:
    """大量取消/作废/未执行病危行不得占满 LIMIT 50 截断有效行，同时 NULL 状态仍保留为 unresolved。"""

    rows = [
        {
            "order_id": f"CANCEL-{index:03d}",
            "order_name": "病危",
            "order_status": ("取消", "已取消", "未执行")[index % 3],
            "prescribed_datetime": f"2026-01-01 08:{index % 60:02d}:00",
        }
        for index in range(55)
    ] + [
        {
            "order_id": "STOPPED-CRITICAL",
            "order_name": "病危",
            "order_status": "已停止",
            "prescribed_datetime": "2026-01-02 08:00:00",
            "planned_start_datetime": "2026-01-02 08:00:00",
            "planned_end_datetime": "2026-01-03 08:00:00",
        },
        {
            "order_id": "NULL-SERIOUS",
            "order_name": "病重",
            "order_status": None,
            "prescribed_datetime": "2026-01-02 09:00:00",
        },
    ]
    _sqlite_nondrug_order_engine(rows, monkeypatch)

    result = source_evidence_reader.read_luxian_0609_severity_order_rows(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None
    )

    assert result.truncated is False
    assert [
        (row["severity"], row["status_state"], row["lifecycle_state"])
        for row in result.rows
    ] == [
        ("critical", "effective", "stopped"),
        ("serious", "unresolved", ""),
    ]
