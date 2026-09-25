"""门急诊候选仅以三坐标代表病例，不以文书或旧记录 ID 代表病例。"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core import supabase_client
from app.services import task_sampling_service
from app.services.task_sampling_service import TaskSamplingService


_COUNT_DEFAULT = object()


class Query:
    def __init__(self, rows, error=None, *, count_override=_COUNT_DEFAULT, page_cap=None, count_sequence=None):
        self.rows = rows
        self.error = error
        self.columns = None
        self.limit_calls = []
        self.range_calls = []
        self.order_columns = []
        self.count_arg = None
        self.count_override = count_override
        self.page_cap = page_cap
        self.count_sequence = count_sequence
        self.execute_count = 0

    def select(self, columns, count=None):
        self.columns = columns
        self.count_arg = count
        self.order_columns = []
        return self

    def order(self, column):
        self.order_columns.append(column)
        return self

    def range(self, start, end):
        self.range_calls.append((start, end))
        return self

    def limit(self, value):
        self.limit_calls.append(value)
        return self

    def execute(self):
        if self.error:
            raise self.error
        rows = sorted(self.rows, key=lambda row: tuple(row[column] for column in self.order_columns))
        start, end = self.range_calls[-1]
        page = rows[start:end + 1]
        if self.page_cap is not None:
            page = page[:self.page_cap]
        count = len(rows) if self.count_override is _COUNT_DEFAULT else self.count_override
        if self.count_sequence is not None:
            count = self.count_sequence[min(self.execute_count, len(self.count_sequence) - 1)]
        self.execute_count += 1
        return SimpleNamespace(data=page, count=count)


class Database:
    def __init__(self, rows, error=None, **query_options):
        self.query = Query(rows, error, **query_options)
        self.tables = []

    def table(self, name):
        self.tables.append(name)
        return self.query


def wire(monkeypatch, rows, error=None, **query_options):
    database = Database(rows, error, **query_options)
    monkeypatch.setattr(supabase_client, "get_supabase", lambda: database)

    async def execute(query):
        return query.execute()

    monkeypatch.setattr(supabase_client, "async_execute", execute)
    return database


def doc(institute="H1", patient="P1", visit="V1", when="2026-09-22T09:00:00+08:00", dept="内科"):
    return {
        "institute_id": institute,
        "patient_id": patient,
        "visit_id": visit,
        "document_id": f"doc-{visit}",
        "visit_datetime": when,
        "dept_name": dept,
    }


@pytest.mark.asyncio
async def test_multiple_documents_share_one_case_but_same_visit_id_other_owner_does_not(monkeypatch):
    rows = [
        {**doc(), "document_id": "D1"},
        {**doc(), "document_id": "D2"},
        doc("H2", "P1", "V1"),
        doc("H1", "P2", "V1"),
    ]
    database = wire(monkeypatch, rows)

    result = await TaskSamplingService()._get_outpatient_candidates({})

    assert len(result) == 3
    assert {(row["institute_id"], row["patient_id"], row["visit_id"]) for row in result} == {
        ("H1", "P1", "V1"), ("H2", "P1", "V1"), ("H1", "P2", "V1")
    }
    assert "id" not in result[0]
    assert "document_id" not in result[0]
    assert result[0]["department"] == "内科"
    assert database.tables == ["cdm.outpat_record"]
    assert database.query.count_arg == "exact"
    assert database.query.range_calls == [(0, 499)]


@pytest.mark.asyncio
async def test_date_and_department_boundaries_are_inclusive(monkeypatch):
    wire(monkeypatch, [
        doc(visit="V1", when="2026-09-01T00:00:00+08:00"),
        doc(visit="V2", when=datetime(2026, 9, 30, 15, 59, tzinfo=timezone.utc)),
        doc(visit="V3", when="2026-10-01T00:00:00+08:00"),
        doc(visit="V4", dept="外科"),
        doc(visit="V5", when="2026-09-30T16:00:00Z"),
    ])

    result = await TaskSamplingService()._get_outpatient_candidates({
        "date_range": {"start": "2026-09-01", "end": "2026-09-30"},
        "department_filter": ["内科"],
    })

    assert [row["visit_id"] for row in result] == ["V1", "V2"]


@pytest.mark.asyncio
async def test_utc_timestamp_is_filtered_by_hospital_calendar_day(monkeypatch):
    wire(monkeypatch, [
        doc(visit="V1", when="2026-08-31T16:00:00Z"),
        doc(visit="V2", when=datetime(2026, 8, 31, 15, 59, tzinfo=timezone.utc)),
        doc(visit="V3", when="2026-09-01T16:00:00Z"),
    ])
    result = await TaskSamplingService()._get_outpatient_candidates({
        "date_range": {"start": "2026-09-01", "end": "2026-09-01"},
    })
    assert [row["visit_id"] for row in result] == ["V1"]


@pytest.mark.asyncio
async def test_explicit_refs_must_all_exist_within_filtered_outpatient_scope(monkeypatch):
    wire(monkeypatch, [doc(), doc(visit="V2", dept="外科")])
    requested = [doc() | {"visit_id": "V1"}, doc() | {"visit_id": "V2"}]

    with pytest.raises(ValueError, match="筛选范围"):
        await TaskSamplingService()._get_outpatient_candidates({
            "record_refs": requested,
            "department_filter": ["内科"],
        })

    result = await TaskSamplingService()._get_outpatient_candidates({
        "record_refs": [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
    })
    assert len(result) == 1
    assert result[0]["visit_id"] == "V1"


@pytest.mark.asyncio
@pytest.mark.parametrize("task", [
    {"date_range": {"start": "2026-02-30"}},
    {"date_range": {"start": datetime(2026, 9, 1, tzinfo=timezone.utc)}},
    {"date_range": {"start": "2026-10-01", "end": "2026-09-01"}},
    {"record_refs": [{"institute_id": "H1", "patient_id": "P1"}]},
    {"record_refs": [{"institute_id": "H1", "patient_id": "", "visit_id": "V1"}]},
])
async def test_invalid_scope_is_rejected_before_query(monkeypatch, task):
    database = wire(monkeypatch, [])
    with pytest.raises(ValueError):
        await TaskSamplingService()._get_outpatient_candidates(task)
    assert database.tables == []


@pytest.mark.asyncio
async def test_empty_source_is_valid_but_missing_explicit_case_is_not(monkeypatch):
    wire(monkeypatch, [])
    service = TaskSamplingService()
    assert await service._get_outpatient_candidates({}) == []
    with pytest.raises(ValueError, match="不存在"):
        await service._get_outpatient_candidates({
            "record_refs": [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
        })


@pytest.mark.asyncio
async def test_database_failure_is_not_an_empty_pool_or_logged_with_patient_detail(monkeypatch, caplog):
    wire(monkeypatch, [], RuntimeError("patient P-PRIVATE source failed"))
    with caplog.at_level("WARNING", logger="app.services.task_sampling_service"):
        with pytest.raises(RuntimeError, match="候选病历数据源不可用"):
            await TaskSamplingService()._get_outpatient_candidates({})
    assert "P-PRIVATE" not in caplog.text


@pytest.mark.asyncio
async def test_query_does_not_truncate_after_ten_thousand_documents(monkeypatch):
    rows = [doc(visit=f"V{i}") for i in range(10001)]
    database = wire(monkeypatch, rows)
    result = await TaskSamplingService()._get_outpatient_candidates({})
    assert len(result) == 10001
    assert database.query.limit_calls == []
    assert len(database.query.range_calls) == 21
    assert database.query.range_calls[0] == (0, 499)
    assert database.query.range_calls[-1] == (10000, 10499)


@pytest.mark.asyncio
async def test_short_server_pages_continue_until_exact_count(monkeypatch):
    database = wire(monkeypatch, [doc(visit=f"V{i}") for i in range(7)], page_cap=3)
    result = await TaskSamplingService()._get_outpatient_candidates({})
    assert len(result) == 7
    assert database.query.range_calls == [(0, 499), (3, 502), (6, 505)]


@pytest.mark.asyncio
@pytest.mark.parametrize("options", [
    {"count_override": None},
    {"count_sequence": [7, 8]},
    {"page_cap": 0},
])
async def test_missing_or_drifting_total_cannot_publish_partial_candidates(monkeypatch, options):
    if "page_cap" not in options:
        options = {**options, "page_cap": 3}
    database = wire(monkeypatch, [doc(visit=f"V{i}") for i in range(7)], **options)
    with pytest.raises(RuntimeError, match="候选病历数据源不可用"):
        await TaskSamplingService()._get_outpatient_candidates({})
    assert database.query.execute_count <= 2


@pytest.mark.asyncio
async def test_document_limit_fails_instead_of_returning_partial_candidates(monkeypatch):
    monkeypatch.setattr(task_sampling_service, "_OUTPATIENT_MAX_DOCUMENTS", 6)
    database = wire(monkeypatch, [doc(visit=f"V{i}") for i in range(7)], page_cap=3)
    with pytest.raises(RuntimeError, match="候选病历数据源不可用"):
        await TaskSamplingService()._get_outpatient_candidates({})
    assert database.query.execute_count == 1


@pytest.mark.asyncio
async def test_repeated_document_primary_key_fails_closed(monkeypatch):
    wire(monkeypatch, [doc(), doc()])
    with pytest.raises(RuntimeError, match="候选病历数据源不可用"):
        await TaskSamplingService()._get_outpatient_candidates({})
