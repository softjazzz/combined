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


def test_snapshot_reader_projects_drug_order_planned_start_time(monkeypatch) -> None:
    connection = _SourceRowsConnection([{
        "order_id": "O-1",
        "generic_name": "美罗培南",
        "prescribed_datetime": "2026-08-19 08:00:00+08",
        "planned_start_datetime": "2026-08-19 10:00:00+08",
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
    sql, _params = connection.calls[0]
    assert '"planned_start_datetime"' in sql


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
