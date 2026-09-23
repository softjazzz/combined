from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from app.services.case_scope_service import CaseScopeService, _parse_datetime
from app.services.case_identity import CaseRef


class _SourceCursor:
    def __init__(
        self,
        *,
        table_columns: dict[str, set[str]],
        source_rows: dict[str, list[dict[str, Any]]] | None = None,
        table_column_types: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self._table_columns = table_columns
        self._source_rows = source_rows or {}
        self._table_column_types = table_column_types or {}
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
            for row in self._rows:
                row["data_type"] = self._table_column_types.get(
                    row["table_name"], {}
                ).get(row["column_name"], "")
            return
        for table_name in self._table_columns:
            rows = self._source_rows.get(table_name, [])
            if f"FROM public.{table_name} AS source_row" in query or (
                table_name == "patient_information"
                and f"FROM public.{table_name}" in query
            ):
                selected_rows = [dict(row) for row in rows]
                excluded_tables = re.findall(
                    r"FROM public\.(\w+) AS discharged_\d+", query
                )
                if excluded_tables:
                    as_of_dates = [
                        date.fromisoformat(value)
                        for value in params
                        if isinstance(value, str)
                        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                    ]
                    assert as_of_dates
                    as_of_end = datetime.combine(
                        max(as_of_dates) + timedelta(days=1), datetime.min.time()
                    )
                    default_institute_id = next(
                        (
                            value
                            for value in params
                            if isinstance(value, str)
                            and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                        ),
                        "",
                    )

                    def has_discharge_fact(candidate: dict[str, Any]) -> bool:
                        candidate_institute = str(
                            candidate.get("institute_id") or default_institute_id
                        )
                        for source_name in excluded_tables:
                            for fact in self._source_rows.get(source_name, []):
                                raw_text_time = fact.get("discharge_time")
                                text_type = self._table_column_types.get(source_name, {}).get(
                                    "discharge_time"
                                ) == "text"
                                discharge_time = _parse_datetime(
                                    raw_text_time
                                    or fact.get("discharge_datetime")
                                    or fact.get("discharge_date")
                                )
                                local_text_format = re.fullmatch(
                                    r"[1-9][0-9]{3}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
                                    r"([ T]([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?)?",
                                    str(raw_text_time),
                                )
                                if raw_text_time and text_type and not local_text_format:
                                    discharge_time = datetime.min
                                elif raw_text_time and discharge_time is None:
                                    discharge_time = datetime.min
                                if discharge_time is None or discharge_time >= as_of_end:
                                    continue
                                if (
                                    str(fact.get("institute_id") or default_institute_id),
                                    str(fact.get("patient_id") or ""),
                                    str(fact.get("visit_id") or ""),
                                ) == (
                                    candidate_institute,
                                    str(candidate.get("patient_id") or ""),
                                    str(candidate.get("visit_id") or ""),
                                ):
                                    return True
                        return False

                    selected_rows = [
                        row
                        for row in selected_rows
                        if not has_discharge_fact(row)
                    ]
                    if ") AND source_row.institute_id::text = %s::text" in query:
                        selected_rows = [
                            row for row in selected_rows
                            if row.get("institute_id") == default_institute_id
                        ]
                self._rows = selected_rows
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


def test_active_scope_falls_back_to_recent_admission_minus_discharge_facts():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {"admission_time", "discharge_time"},
            "admission_record": identity_columns
            | {"admission_time", "dept_name"},
            "mr": identity_columns | {"discharge_time"},
            "discharge_record": identity_columns | {"discharge_time"},
        },
        source_rows={
            "inpat_registration": [],
            "admission_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P-ACTIVE",
                    "visit_id": "V-ACTIVE",
                    "admission_time": "2026-07-20 08:00:00",
                    "current_department": "呼吸与危重症医学科",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P-DISCHARGED",
                    "visit_id": "V-DISCHARGED",
                    "admission_time": "2026-07-21 08:00:00",
                    "current_department": "儿科",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P-DISCHARGED-RECORD",
                    "visit_id": "V-DISCHARGED-RECORD",
                    "admission_time": "2026-07-22 08:00:00",
                    "current_department": "呼吸与危重症医学科",
                },
            ],
            "mr": [
                {
                    "institute_id": "H1",
                    "patient_id": "P-DISCHARGED",
                    "visit_id": "V-DISCHARGED",
                    "discharge_time": "2026-07-25 10:00:00",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P-ACTIVE",
                    "visit_id": "V-ACTIVE",
                    "discharge_time": "2026-08-01 00:00:00",
                },
            ],
            "discharge_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P-DISCHARGED-RECORD",
                    "visit_id": "V-DISCHARGED-RECORD",
                    "discharge_time": "2026-07-31 10:00:00",
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
        departments=("呼吸与危重症医学科",),
    )

    assert result.case_refs == (CaseRef("H1", "P-ACTIVE", "V-ACTIVE"),)
    assert result.selected[0]["source_table"] == "admission_record"
    assert result.selected[0]["department"] == "呼吸与危重症医学科"
    assert result.sources_used == ("admission_record", "mr", "discharge_record")
    assert result.source_status == "degraded"
    assert result.warnings == (
        "住院登记没有可用在院时间，已按最近180天入院记录排除已出院病例。",
    )
    admission_queries = [
        (query, params)
        for query, params in cursor.queries
        if "FROM public.admission_record" in query
    ]
    assert admission_queries
    assert "admission_time >= %s::date" in admission_queries[0][0]
    assert admission_queries[0][0].count("NOT EXISTS") == 2
    assert "FROM public.mr AS discharged_0" in admission_queries[0][0]
    assert "FROM public.discharge_record AS discharged_1" in admission_queries[0][0]
    assert "2026-02-01" in admission_queries[0][1]


def test_active_scope_fallback_requires_authoritative_discharge_facts():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {"admission_time", "discharge_time"},
            "admission_record": identity_columns | {"admission_time"},
        },
        source_rows={"inpat_registration": []},
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    with pytest.raises(ValueError, match="权威出院事实"):
        service.resolve_hospitalization_scope(
            scope_mode="active",
            as_of_date=date(2026, 7, 31),
            discharge_start_date=None,
            discharge_end_date=None,
            departments=(),
        )


def test_registration_active_excludes_only_matching_discharge_facts_by_as_of():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {"admission_datetime", "discharge_datetime"},
            "mr": identity_columns | {"discharge_datetime"},
            "discharge_record": identity_columns | {"discharge_datetime"},
        },
        source_rows={
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": patient_id,
                    "visit_id": "SAME-VISIT",
                    "admission_time": "2026-07-01 08:00:00",
                    "discharge_time": None,
                }
                for patient_id in ("P-MR", "P-RECORD", "P-FUTURE", "P-OTHER")
            ]
            + [
                {
                    "institute_id": "H2",
                    "patient_id": "P-OTHER",
                    "visit_id": "SAME-VISIT",
                    "admission_time": "2026-07-01 08:00:00",
                    "discharge_time": None,
                }
            ],
            "mr": [
                {
                    "institute_id": "H1",
                    "patient_id": "P-MR",
                    "visit_id": "SAME-VISIT",
                    "discharge_time": "2026-07-31 10:00:00",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P-FUTURE",
                    "visit_id": "SAME-VISIT",
                    "discharge_time": "2026-08-01 00:00:00",
                },
            ],
            "discharge_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P-RECORD",
                    "visit_id": "SAME-VISIT",
                    "discharge_time": "2026-07-30 09:00:00",
                },
                {
                    "institute_id": "H2",
                    "patient_id": "P-OTHER",
                    "visit_id": "SAME-VISIT",
                    "discharge_time": "2026-07-30 09:00:00",
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
        scope_mode="active",
        as_of_date=date(2026, 7, 31),
        discharge_start_date=None,
        discharge_end_date=None,
        departments=(),
    )

    assert result.case_refs == (
        CaseRef("H1", "P-FUTURE", "SAME-VISIT"),
        CaseRef("H1", "P-OTHER", "SAME-VISIT"),
    )
    assert result.sources_used == ("inpat_registration", "mr", "discharge_record")
    assert result.source_status == "ready"
    query, params = next(
        (query, params)
        for query, params in cursor.queries
        if "FROM public.inpat_registration AS source_row" in query
    )
    assert query.count("NOT EXISTS") == 2
    assert query.count("< (%s::date + INTERVAL '1 day')") == 3
    assert params == ["2026-07-31"] * 4


def test_registration_active_requires_discharge_fact_source():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {"admission_datetime", "discharge_datetime"},
        },
        source_rows={"inpat_registration": []},
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    with pytest.raises(ValueError, match="权威出院事实"):
        service.resolve_hospitalization_scope(
            scope_mode="active",
            as_of_date=date(2026, 7, 31),
            discharge_start_date=None,
            discharge_end_date=None,
            departments=(),
        )


def test_registration_active_with_one_discharge_source_is_degraded():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {"admission_datetime", "discharge_datetime"},
            "mr": identity_columns | {"discharge_datetime"},
        },
        source_rows={
            "inpat_registration": [
                {
                    "institute_id": "H1",
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
    assert result.sources_used == ("inpat_registration", "mr")
    assert result.source_status == "degraded"
    assert "仅有部分权威出院反证来源" in result.warnings[0]


def test_registration_active_exclusion_uses_hospital_day_for_timestamptz():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {"admission_datetime", "discharge_datetime"},
            "mr": identity_columns | {"discharge_datetime"},
            "discharge_record": identity_columns | {"discharge_datetime"},
        },
        table_column_types={
            "mr": {"discharge_datetime": "timestamp with time zone"},
        },
        source_rows={
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": patient_id,
                    "visit_id": "V1",
                    "admission_time": "2026-07-01 08:00:00",
                    "discharge_time": None,
                }
                for patient_id in ("P-LOCAL-JULY", "P-LOCAL-AUGUST")
            ],
            "mr": [
                {
                    "institute_id": "H1",
                    "patient_id": "P-LOCAL-JULY",
                    "visit_id": "V1",
                    "discharge_time": "2026-07-31T15:30:00+00:00",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P-LOCAL-AUGUST",
                    "visit_id": "V1",
                    "discharge_time": "2026-07-31T16:30:00+00:00",
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
        scope_mode="active",
        as_of_date=date(2026, 7, 31),
        discharge_start_date=None,
        discharge_end_date=None,
        departments=(),
    )

    assert result.case_refs == (CaseRef("H1", "P-LOCAL-AUGUST", "V1"),)
    query = next(
        query
        for query, _params in cursor.queries
        if "FROM public.inpat_registration AS source_row" in query
    )
    assert "discharged_0.discharge_datetime AT TIME ZONE 'Asia/Shanghai'" in query


def test_registration_active_uses_text_time_and_typed_date_discharge_facts():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {"admission_datetime", "discharge_datetime"},
            "mr": identity_columns | {"discharge_datetime"},
            "discharge_record": identity_columns | {"discharge_time", "discharge_date"},
        },
        table_column_types={
            "discharge_record": {"discharge_time": "text", "discharge_date": "date"},
        },
        source_rows={
            "inpat_registration": [
                {
                    "institute_id": "H1", "patient_id": patient_id,
                    "visit_id": "V1", "admission_time": "2026-07-01 08:00:00",
                    "discharge_time": None,
                }
                for patient_id in ("P-TEXT", "P-DATE", "P-FUTURE", "P-BAD", "P-OFFSET", "P-OTHER")
            ],
            "discharge_record": [
                {"institute_id": "H1", "patient_id": "P-TEXT", "visit_id": "V1",
                 "discharge_time": "2026-07-30 10:00:00", "discharge_date": None},
                {"institute_id": "H1", "patient_id": "P-DATE", "visit_id": "V1",
                 "discharge_time": None, "discharge_date": date(2026, 7, 30)},
                {"institute_id": "H1", "patient_id": "P-FUTURE", "visit_id": "V1",
                 "discharge_time": "2026-08-01 10:00:00", "discharge_date": None},
                {"institute_id": "H1", "patient_id": "P-BAD", "visit_id": "V1",
                 "discharge_time": "unknown", "discharge_date": None},
                {"institute_id": "H1", "patient_id": "P-OFFSET", "visit_id": "V1",
                 "discharge_time": "2026-08-01T00:30:00+00:00", "discharge_date": None},
            ],
        },
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    result = service.resolve_hospitalization_scope(
        scope_mode="active", as_of_date=date(2026, 7, 31),
        discharge_start_date=None, discharge_end_date=None, departments=(),
    )

    assert result.case_refs == (
        CaseRef("H1", "P-FUTURE", "V1"),
        CaseRef("H1", "P-OTHER", "V1"),
    )
    query, params = next(
        (query, params) for query, params in cursor.queries
        if "FROM public.inpat_registration AS source_row" in query
    )
    assert "btrim(discharged_1.discharge_time)" in query
    assert "[ T]([01][0-9]|2[0-3])" in query
    assert "?)?$'" in query
    assert "discharged_1.discharge_date <= %s::date" in query
    assert params == ["2026-07-31"] * 5


def test_registration_does_not_assert_other_institutions_active_without_scoped_discharge_facts():
    identity_columns = {"patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {"institute_id", "admission_datetime", "discharge_datetime"},
            "mr": identity_columns | {"discharge_datetime"},
            "discharge_record": identity_columns | {"discharge_date"},
        },
        source_rows={
            "inpat_registration": [
                {"institute_id": "H1", "patient_id": "P-ACTIVE", "visit_id": "V1",
                 "admission_time": "2026-07-01 08:00:00", "discharge_time": None},
                {"institute_id": "H1", "patient_id": "P-DISCH", "visit_id": "V1",
                 "admission_time": "2026-07-01 08:00:00", "discharge_time": None},
                {"institute_id": "H2", "patient_id": "P-UNKNOWN", "visit_id": "V1",
                 "admission_time": "2026-07-01 08:00:00", "discharge_time": None},
            ],
            "mr": [
                {"patient_id": "P-DISCH", "visit_id": "V1",
                 "discharge_time": "2026-07-30 12:00:00"},
            ],
        },
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {
            "remote_schema": "public", "default_institute_id": "H1",
        },
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    result = service.resolve_hospitalization_scope(
        scope_mode="active", as_of_date=date(2026, 7, 31),
        discharge_start_date=None, discharge_end_date=None, departments=(),
    )

    assert result.case_refs == (CaseRef("H1", "P-ACTIVE", "V1"),)
    assert result.source_status == "degraded"
    assert any("缺少机构号" in warning for warning in result.warnings)
    query, params = next(
        (query, params) for query, params in cursor.queries
        if "FROM public.inpat_registration AS source_row" in query
    )
    assert ") AND source_row.institute_id::text = %s::text" in query
    assert params[-1] == "H1"


@pytest.mark.parametrize("has_fallback", [False, True])
def test_registration_with_text_time_cannot_be_active_primary_source(has_fallback):
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    table_columns = {
        "inpat_registration": identity_columns
        | {"admission_datetime", "discharge_time"},
        "mr": identity_columns | {"discharge_datetime"},
        "discharge_record": identity_columns | {"discharge_date"},
    }
    table_column_types = {
        "inpat_registration": {
            "admission_datetime": "timestamp without time zone",
            "discharge_time": "text",
        },
    }
    source_rows = {
        "inpat_registration": [
            {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1",
             "admission_time": "2026-07-01 08:00:00", "discharge_time": None},
        ],
    }
    if has_fallback:
        table_columns["admission_record"] = identity_columns | {"admission_datetime"}
        table_column_types["admission_record"] = {
            "admission_datetime": "timestamp without time zone",
        }
        source_rows["admission_record"] = [
            {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1",
             "admission_time": "2026-07-01 08:00:00"},
        ]
    cursor = _SourceCursor(
        table_columns=table_columns,
        table_column_types=table_column_types,
        source_rows=source_rows,
    )
    service = CaseScopeService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
        connection_factory=lambda *_args, **_kwargs: _SourceConnection(cursor),
    )

    if not has_fallback:
        with pytest.raises(ValueError, match="当前在院患者数据"):
            service.resolve_hospitalization_scope(
                scope_mode="active", as_of_date=date(2026, 7, 31),
                discharge_start_date=None, discharge_end_date=None, departments=(),
            )
        return

    result = service.resolve_hospitalization_scope(
        scope_mode="active", as_of_date=date(2026, 7, 31),
        discharge_start_date=None, discharge_end_date=None, departments=(),
    )
    assert result.case_refs == (CaseRef("H1", "P1", "V1"),)
    assert result.source_status == "degraded"
    assert result.sources_used == ("admission_record", "mr", "discharge_record")
    assert all(
        "FROM public.inpat_registration AS source_row" not in query
        for query, _params in cursor.queries
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
            "mr": identity_columns | {"discharge_datetime"},
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
    assert result.sources_used == ("inpat_registration", "mr", "discharge_record")
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
            "mr": identity_columns | {"discharge_datetime"},
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
            "mr": identity_columns | {"discharge_datetime"},
            "discharge_record": identity_columns | {"discharge_datetime"},
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
            | {"admission_datetime", "discharge_datetime"},
            "mr": identity_columns | {"discharge_datetime"},
            "discharge_record": identity_columns | {"discharge_datetime"},
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


def test_combined_scope_prefers_period_discharge_over_stale_active_candidate():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {"admission_datetime", "discharge_datetime", "current_dept_name"},
            "discharge_record": identity_columns
            | {"discharge_datetime", "discharge_dept_name"},
            "mr": identity_columns | {"discharge_datetime"},
        },
        source_rows={
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "admission_time": "2026-08-01 08:00:00",
                    "discharge_time": None,
                    "current_department": "重症医学科",
                }
            ],
            "discharge_record": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "discharge_time": "2026-08-10 09:00:00",
                    "discharge_department": "神经外科",
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
        as_of_date=date(2026, 8, 13),
        discharge_start_date=date(2026, 8, 7),
        discharge_end_date=date(2026, 8, 13),
        departments=(),
    )

    assert result.case_refs == (CaseRef("H1", "P1", "V1"),)
    assert result.selected[0]["hospitalization_status"] == "discharged"
    assert result.selected[0]["source_table"] == "discharge_record"
    assert result.selected[0]["department"] == "神经外科"


def test_department_filter_uses_lower_priority_source_only_to_fill_missing_department():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "discharge_record": identity_columns | {"discharge_datetime"},
            "mr": identity_columns | {"discharge_datetime", "discharge_dept_name"},
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
                    "discharge_time": "2026-08-10 09:00:00",
                    "discharge_department": "神经外科",
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
        scope_mode="discharged",
        as_of_date=date(2026, 8, 13),
        discharge_start_date=date(2026, 8, 7),
        discharge_end_date=date(2026, 8, 13),
        departments=("神经外科",),
    )

    assert result.case_refs == (CaseRef("H1", "P1", "V1"),)
    assert result.selected[0]["source_table"] == "discharge_record"
    assert result.selected[0]["department"] == "神经外科"


def test_timestamptz_discharge_filter_uses_hospital_calendar_day_in_source_sql():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns | {"discharge_datetime"},
        },
        table_column_types={
            "inpat_registration": {"discharge_datetime": "timestamp with time zone"},
        },
        source_rows={
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "discharge_time": "2026-08-07T00:15:00+08:00",
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
        scope_mode="discharged",
        as_of_date=date(2026, 8, 13),
        discharge_start_date=date(2026, 8, 7),
        discharge_end_date=date(2026, 8, 13),
        departments=(),
    )

    assert result.case_refs == (CaseRef("H1", "P1", "V1"),)
    source_query = next(
        query for query, _params in cursor.queries if "FROM public.inpat_registration" in query
    )
    assert "discharge_datetime AT TIME ZONE 'Asia/Shanghai'" in source_query


def test_timestamptz_active_filter_uses_hospital_calendar_boundaries_in_source_sql():
    identity_columns = {"institute_id", "patient_id", "visit_id"}
    cursor = _SourceCursor(
        table_columns={
            "inpat_registration": identity_columns
            | {"admission_datetime", "discharge_datetime"},
            "mr": identity_columns | {"discharge_datetime"},
            "discharge_record": identity_columns | {"discharge_datetime"},
        },
        table_column_types={
            "inpat_registration": {
                "admission_datetime": "timestamp with time zone",
                "discharge_datetime": "timestamp with time zone",
            },
        },
        source_rows={
            "inpat_registration": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "admission_time": "2026-08-07T00:15:00+08:00",
                    "discharge_time": None,
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
        as_of_date=date(2026, 8, 13),
        admission_start_date=date(2026, 8, 7),
        discharge_start_date=None,
        discharge_end_date=None,
        departments=(),
    )

    assert result.case_refs == (CaseRef("H1", "P1", "V1"),)
    source_query = next(
        query for query, _params in cursor.queries if "FROM public.inpat_registration" in query
    )
    assert "admission_datetime AT TIME ZONE 'Asia/Shanghai'" in source_query
    assert "discharge_datetime AT TIME ZONE 'Asia/Shanghai'" in source_query


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
            },
            "mr": {"patient_id", "visit_id", "discharge_datetime"},
            "discharge_record": {"patient_id", "visit_id", "discharge_datetime"},
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
            },
            "mr": {"patient_id", "visit_id", "discharge_datetime"},
            "discharge_record": {"patient_id", "visit_id", "discharge_datetime"},
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
            "mr": {"institute_id", "patient_id", "visit_id", "discharge_datetime"},
            "discharge_record": {
                "institute_id", "patient_id", "visit_id", "discharge_datetime"
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
