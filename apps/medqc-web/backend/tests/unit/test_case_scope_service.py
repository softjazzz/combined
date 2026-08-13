from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from app.services.case_scope_service import CaseScopeService
from app.services.case_identity import CaseRef


class _SourceCursor:
    def __init__(
        self,
        *,
        table_columns: dict[str, set[str]],
        source_rows: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._table_columns = table_columns
        self._source_rows = source_rows or {}
        self._rows: list[dict[str, Any]] = []
        self.queries: list[tuple[str, Any]] = []

    def execute(self, query: str, params: Any = None) -> None:
        self.queries.append((query, params))
        if "information_schema.columns" in query:
            self._rows = [
                {"table_name": table_name, "column_name": column_name}
                for table_name, columns in self._table_columns.items()
                for column_name in columns
            ]
            return
        for table_name, rows in self._source_rows.items():
            if f"FROM public.{table_name}" in query:
                self._rows = [dict(row) for row in rows]
                if "%s::text AS institute_id" in query:
                    for row in self._rows:
                        row.setdefault("institute_id", params[0])
                return
        raise AssertionError(f"非预期源库查询: {query}")

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def close(self) -> None:
        return None


class _SourceConnection:
    def __init__(self, cursor: _SourceCursor) -> None:
        self._cursor = cursor

    def cursor(self, **_kwargs: Any) -> _SourceCursor:
        return self._cursor

    def close(self) -> None:
        return None


def test_active_scope_requires_reliable_inpat_registration_source():
    cursor = _SourceCursor(
        table_columns={
            "admission_record": {
                "institute_id",
                "patient_id",
                "visit_id",
                "admission_datetime",
                "discharge_datetime",
            },
            "mr": {
                "institute_id",
                "patient_id",
                "visit_id",
                "admission_datetime",
                "discharge_datetime",
            },
        }
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    with pytest.raises(ValueError, match="请同步住院登记"):
        service.resolve_hospitalization_scope(
            scope_mode="active",
            as_of_date=date(2026, 7, 31),
            discharge_start_date=None,
            discharge_end_date=None,
            departments=(),
        )


def test_combined_scope_returns_active_and_period_discharge_case_refs():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {
                "admission_datetime",
                "discharge_datetime",
                "current_dept_name",
            },
            "discharge_record": identity_columns
            | {"discharge_datetime", "discharge_dept_name"},
        },
        source_rows={
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "ACTIVE-OLD",
                    "admission_time": "2026-06-01 08:00:00",
                    "discharge_time": None,
                    "current_department": "重症医学科（ICU）",
                }
            ],
            "discharge_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P2",
                    "visit_id": "DISCHARGED-TODAY",
                    "admission_time": None,
                    "discharge_time": "2026-07-31 10:00:00",
                    "discharge_department": "神经外科",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P3",
                    "visit_id": "DISCHARGED-BEFORE",
                    "admission_time": None,
                    "discharge_time": "2026-07-30 10:00:00",
                    "discharge_department": "内科",
                },
            ],
        },
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    result = service.resolve_hospitalization_scope(
        scope_mode="active_and_discharged",
        as_of_date=date(2026, 7, 31),
        discharge_start_date=date(2026, 7, 31),
        discharge_end_date=date(2026, 7, 31),
        departments=(),
    )

    assert result.case_refs == (
        CaseRef("H1", "P1", "ACTIVE-OLD"),
        CaseRef("H1", "P2", "DISCHARGED-TODAY"),
    )
    assert [row["hospitalization_status"] for row in result.selected] == [
        "active",
        "discharged",
    ]
    assert result.selected[0]["authoritative_time"].isoformat() == (
        "2026-06-01T08:00:00"
    )
    assert result.selected[1]["authoritative_time"].isoformat() == (
        "2026-07-31T10:00:00"
    )
    assert result.selected[0]["source_table"] == "inpat_registration"
    assert result.selected[1]["source_table"] == "discharge_record"
    assert result.sources_used == ("inpat_registration", "discharge_record")
    assert result.source_status == "ready"


def test_combined_scope_normalizes_offset_aware_source_times_to_hospital_time():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {
                "admission_datetime",
                "discharge_datetime",
                "current_dept_name",
            },
            "discharge_record": identity_columns
            | {"discharge_datetime", "discharge_dept_name"},
        },
        source_rows={
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "ACTIVE-AWARE",
                    "admission_time": datetime(
                        2026,
                        5,
                        2,
                        8,
                        tzinfo=timezone(timedelta(hours=8)),
                    ),
                    "discharge_time": None,
                    "current_department": "外一科",
                }
            ],
            "discharge_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P2",
                    "visit_id": "DISCHARGED-AWARE",
                    "admission_time": None,
                    "discharge_time": "2026-05-05T10:30:00+08:00",
                    "discharge_department": "中医科",
                }
            ],
        },
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    result = service.resolve_hospitalization_scope(
        scope_mode="active_and_discharged",
        as_of_date=date(2026, 5, 9),
        admission_start_date=date(2026, 5, 1),
        discharge_start_date=date(2026, 5, 1),
        discharge_end_date=date(2026, 5, 9),
        departments=("外一科", "中医科"),
    )

    assert result.case_refs == (
        CaseRef("H1", "P1", "ACTIVE-AWARE"),
        CaseRef("H1", "P2", "DISCHARGED-AWARE"),
    )
    assert [row["authoritative_time"].isoformat() for row in result.selected] == [
        "2026-05-02T08:00:00",
        "2026-05-05T10:30:00",
    ]


def test_active_scope_filters_by_admission_start_date():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {
                "admission_datetime",
                "discharge_datetime",
                "current_dept_name",
            },
        },
        source_rows={
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P-OLD",
                    "visit_id": "V-OLD",
                    "admission_time": "2026-06-30 08:00:00",
                    "discharge_time": None,
                    "current_department": "重症医学科（ICU）",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P-IN-RANGE",
                    "visit_id": "V-IN-RANGE",
                    "admission_time": "2026-07-01 00:00:00",
                    "discharge_time": None,
                    "current_department": "重症医学科（ICU）",
                },
            ]
        },
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    result = service.resolve_hospitalization_scope(
        scope_mode="active",
        as_of_date=date(2026, 7, 31),
        admission_start_date=date(2026, 7, 1),
        discharge_start_date=None,
        discharge_end_date=None,
        departments=(),
    )

    assert result.case_refs == (CaseRef("H1", "P-IN-RANGE", "V-IN-RANGE"),)


def test_active_scope_deduplicates_full_coordinates_and_filters_effective_department():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    first = {
        "institute_id": "H1",
        "patient_id": "P1",
        "visit_id": "SAME-VISIT",
        "admission_time": "2026-06-01 08:00:00",
        "discharge_time": None,
        "admission_department": "急诊科",
        "current_department": "重症医学科（ICU）",
    }
    second = {
        "institute_id": "H2",
        "patient_id": "P2",
        "visit_id": "SAME-VISIT",
        "admission_time": "2026-06-02 08:00:00",
        "discharge_time": None,
        "admission_department": "内科",
        "current_department": "心内科",
    }
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {"admission_datetime", "discharge_datetime"}
        },
        source_rows={"inpat_registration": [first, dict(first), second]},
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    result = service.resolve_hospitalization_scope(
        scope_mode="active",
        as_of_date=date(2026, 7, 31),
        discharge_start_date=None,
        discharge_end_date=None,
        departments=("重症医学科（ICU）",),
    )

    assert result.case_refs == (CaseRef("H1", "P1", "SAME-VISIT"),)
    assert len(result.all_selected) == 2
    assert result.selected[0]["department"] == "重症医学科（ICU）"
    assert result.selected[0]["department_basis"] == "current_department"


def test_discharged_scope_merges_sources_and_preserves_authoritative_priority():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "discharge_record": identity_columns | {"discharge_datetime"},
            "mr": identity_columns | {"discharge_datetime"},
            "inpat_registration": identity_columns | {"discharge_datetime"},
            "admission_record": identity_columns | {"discharge_datetime"},
        },
        source_rows={
            "discharge_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "discharge_time": "2026-08-10 09:00:00",
                }
            ],
            "mr": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "discharge_time": "2026-08-10 11:00:00",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P-MR-ONLY",
                    "visit_id": "V-MR-ONLY",
                    "discharge_time": "2026-08-10 10:00:00",
                }
            ],
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P-AUGUST",
                    "visit_id": "V-AUGUST",
                    "discharge_time": "2026-08-10 12:00:00",
                }
            ],
            "admission_record": [],
        },
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    result = service.resolve_hospitalization_scope(
        scope_mode="discharged",
        as_of_date=date(2026, 8, 13),
        discharge_start_date=date(2026, 8, 7),
        discharge_end_date=date(2026, 8, 13),
        departments=(),
    )

    assert result.case_refs == (
        CaseRef("H1", "P1", "V1"),
        CaseRef("H1", "P-MR-ONLY", "V-MR-ONLY"),
        CaseRef("H1", "P-AUGUST", "V-AUGUST"),
    )
    assert result.selected[0]["source_table"] == "discharge_record"
    assert result.selected[0]["authoritative_time"] == datetime(2026, 8, 10, 9, 0)
    assert result.sources_used == (
        "discharge_record",
        "mr",
        "inpat_registration",
        "admission_record",
    )
    assert result.source_status == "ready"
    source_queries = [
        query
        for query, _params in cursor.queries
        if "information_schema.columns" not in query
    ]
    assert len(source_queries) == 4
    assert "FROM public.discharge_record" in source_queries[0]
    assert "FROM public.mr" in source_queries[1]
    assert "FROM public.inpat_registration" in source_queries[2]
    assert "FROM public.admission_record" in source_queries[3]


def test_discharged_scope_accepts_31_day_window_and_rejects_32_days():
    cursor = _SourceCursor(
        table_columns={
            "discharge_record": {
                "institute_id",
                "patient_id",
                "visit_id",
                "discharge_datetime",
            }
        },
        source_rows={
            "discharge_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "discharge_time": "2026-07-31 09:00:00",
                }
            ]
        },
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    accepted = service.resolve_hospitalization_scope(
        scope_mode="discharged",
        as_of_date=date(2026, 7, 31),
        discharge_start_date=date(2026, 7, 1),
        discharge_end_date=date(2026, 7, 31),
        departments=(),
    )
    assert accepted.case_refs == (CaseRef("H1", "P1", "V1"),)

    with pytest.raises(ValueError, match="最多 31 天"):
        service.resolve_hospitalization_scope(
            scope_mode="discharged",
            as_of_date=date(2026, 8, 1),
            discharge_start_date=date(2026, 7, 1),
            discharge_end_date=date(2026, 8, 1),
            departments=(),
        )


def test_single_institution_source_injects_configured_identity_at_source_boundary():
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": {
                "patient_id",
                "visit_id",
                "admission_datetime",
                "discharge_datetime",
            }
        },
        source_rows={
            "inpat_registration": [
                {
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "admission_time": "2026-07-01 08:00:00",
                    "discharge_time": None,
                }
            ]
        },
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {
            "remote_schema": "public",
            "default_institute_id": "LOCAL-HOSPITAL",
        },
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    result = service.resolve_hospitalization_scope(
        scope_mode="active",
        as_of_date=date(2026, 7, 31),
        discharge_start_date=None,
        discharge_end_date=None,
        departments=(),
    )

    assert result.case_refs == (CaseRef("LOCAL-HOSPITAL", "P1", "V1"),)
    source_query, params = next(
        (query, params)
        for query, params in cursor.queries
        if "FROM public.inpat_registration" in query
    )
    assert "%s::text AS institute_id" in source_query
    assert params[0] == "LOCAL-HOSPITAL"


def test_single_institution_source_without_configured_identity_fails_closed():
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": {
                "patient_id",
                "visit_id",
                "admission_datetime",
                "discharge_datetime",
            }
        }
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    with pytest.raises(ValueError, match="default_institute_id"):
        service.resolve_hospitalization_scope(
            scope_mode="active",
            as_of_date=date(2026, 7, 31),
            discharge_start_date=None,
            discharge_end_date=None,
            departments=(),
        )


def test_discharged_scope_reports_degraded_fallback_when_discharge_record_unavailable():
    cursor = _SourceCursor(
        table_columns={
            "mr": {
                "institute_id",
                "patient_id",
                "visit_id",
                "discharge_datetime",
            },
            "inpat_registration": {
                "institute_id",
                "patient_id",
                "visit_id",
                "discharge_datetime",
            },
        },
        source_rows={
            "mr": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "discharge_time": "2026-07-31 09:00:00",
                }
            ],
            "inpat_registration": [],
        },
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    result = service.resolve_hospitalization_scope(
        scope_mode="discharged",
        as_of_date=date(2026, 7, 31),
        discharge_start_date=date(2026, 7, 31),
        discharge_end_date=date(2026, 7, 31),
        departments=(),
    )

    assert result.sources_used == ("mr", "inpat_registration")
    assert result.source_status == "degraded"
    assert result.warnings == (
        "源库未提供可用出院记录表，已使用病案首页或住院记录识别期间出院患者。",
    )


def test_scope_backfills_missing_patient_name_without_changing_case_identity():
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": {
                "institute_id",
                "patient_id",
                "visit_id",
                "admission_datetime",
                "discharge_datetime",
            },
            "patient_information": {
                "institute_id",
                "patient_id",
                "name",
            },
        },
        source_rows={
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "patient_name": "",
                    "admission_time": "2026-07-01 08:00:00",
                    "discharge_time": None,
                }
            ],
            "patient_information": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "patient_name": "在院患者",
                }
            ],
        },
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    result = service.resolve_hospitalization_scope(
        scope_mode="active",
        as_of_date=date(2026, 7, 31),
        discharge_start_date=None,
        discharge_end_date=None,
        departments=(),
    )

    assert result.case_refs == (CaseRef("H1", "P1", "V1"),)
    assert result.selected[0]["patient_name"] == "在院患者"
