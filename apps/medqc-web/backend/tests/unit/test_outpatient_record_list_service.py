from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

import pytest

from app.services import outpatient_record_list_service as service


@dataclass
class _Result:
    data: list[dict[str, Any]]
    count: int


class _Query:
    def __init__(self, database: "_Database") -> None:
        self.database = database
        self.start = 0
        self.end = len(database.rows) - 1

    def select(self, _columns: str, *, count: str):
        assert count == "exact"
        return self

    def order(self, column: str, *, desc: bool):
        assert column == "id" and desc is False
        return self

    def range(self, start: int, end: int):
        self.start, self.end = start, end
        return self

    def execute(self) -> _Result:
        if self.database.failed:
            raise RuntimeError("synthetic source failure")
        rows = sorted(self.database.rows, key=lambda row: str(row.get("id") or ""))
        self.database.reads.append((self.start, self.end))
        return _Result(
            data=[dict(row) for row in rows[self.start:self.end + 1]],
            count=self.database.reported_count if self.database.reported_count is not None else len(rows),
        )


class _Database:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        failed: bool = False,
        reported_count: int | None = None,
    ) -> None:
        self.rows = rows
        self.failed = failed
        self.reported_count = reported_count
        self.reads: list[tuple[int, int]] = []

    def table(self, table_name: str) -> _Query:
        assert table_name == "medical_records"
        return _Query(self)


async def _execute(query: _Query) -> _Result:
    return query.execute()


@pytest.mark.asyncio
async def test_complete_source_paging_finds_match_after_old_5000_cutoff():
    rows = [
        {"id": f"a-{index:05d}", "record_type": "inpatient", "patient_name": "非门急诊"}
        for index in range(5_001)
    ]
    rows.append({
        "id": "z-match", "record_type": "outpatient", "record_id": "OP-1",
        "patient_name": "命中患者", "visit_date": "2026-09-28",
    })
    database = _Database(rows)

    result = await service.query_records(
        source=database,
        table_name="medical_records",
        filters=service.build_filter(keyword="命中", sort_field="visit_date", sort_order="desc"),
        page=1,
        page_size=20,
        execute=_execute,
    )

    assert result.total == 1
    assert result.items[0]["record_id"] == "OP-1"
    assert len(database.reads) == 6


def test_filter_sort_keeps_unknown_null_and_date_filter_excludes_unknown_date():
    rows = [
        {"id": "2", "record_type": "emergency", "record_id": "E-2", "visit_date": ""},
        {
            "id": "1", "record_type": "outpatient", "record_id": "O-1",
            "visit_date": "2026-09-20", "score": "91.5", "defect_count": "2",
        },
    ]

    without_date = service.filter_and_sort(rows, service.build_filter(sort_field="score"))
    assert without_date[0]["record_id"] == "O-1"
    assert without_date[1]["score"] is None
    assert without_date[1]["defect_count"] is None

    start_only = service.filter_and_sort(rows, service.build_filter(start_date="2026-09-01"))
    end_only = service.filter_and_sort(rows, service.build_filter(end_date="2026-09-30"))
    assert [row["record_id"] for row in start_only] == ["O-1"]
    assert [row["record_id"] for row in end_only] == ["O-1"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start_date": "2026/09/01"}, "开始日期格式无效"),
        ({"start_date": "2026-09-02", "end_date": "2026-09-01"}, "开始日期不能晚于"),
        ({"sort_field": "created_at"}, "不支持的排序字段"),
        ({"sort_order": "sideways"}, "排序方向仅支持"),
    ],
)
def test_filter_validation_fails_before_source_access(kwargs, message):
    with pytest.raises(service.OutpatientRecordInvalid, match=message):
        service.build_filter(**kwargs)


@pytest.mark.asyncio
async def test_export_is_bom_csv_formula_safe_and_preserves_unknown_as_empty():
    database = _Database([{
        "id": "out-1", "record_type": "emergency", "record_id": "=E-1",
        "patient_name": "  +公式患者", "visit_date": "2026-09-28",
        "department": "急诊科", "status": "passed", "score": 99,
        "defect_count": 0, "scoring_standard": "legacy-standard",
    }])

    result = await service.export_records(
        source=database,
        table_name="medical_records",
        filters=service.build_filter(),
        execute=_execute,
    )

    assert result.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(result.content.decode("utf-8-sig"))))
    assert rows == [{
        "病历号": "'=E-1", "姓名": "'  +公式患者", "就诊类型": "emergency",
        "科室": "急诊科", "医生": "", "日期": "2026-09-28", "状态": "",
        "分数": "", "缺陷数": "", "评分标准": "",
    }]


@pytest.mark.parametrize(
    ("raw", "score", "defect_count"),
    [
        ({"score": True, "defect_count": False}, None, None),
        ({"score": "nan", "defect_count": 1.5}, None, None),
        ({"score": float("inf"), "defect_count": "1.5"}, None, None),
        ({"score": "88.5", "defect_count": 2.0}, 88.5, 2),
    ],
)
def test_numeric_normalization_rejects_non_finite_bool_and_fractional_count(
    raw, score, defect_count,
):
    row = service.normalize_record({
        "id": "record-1", "record_type": "outpatient", **raw,
    })
    assert row["score"] == score
    assert row["defect_count"] == defect_count


@pytest.mark.asyncio
async def test_export_rejects_more_than_10000_matches_without_truncation():
    database = _Database([
        {"id": f"out-{index:05d}", "record_type": "outpatient", "record_id": f"O-{index}"}
        for index in range(service.MAX_EXPORT_ROWS + 1)
    ])

    with pytest.raises(service.OutpatientRecordExportTooLarge) as caught:
        await service.export_records(
            source=database,
            table_name="medical_records",
            filters=service.build_filter(),
            execute=_execute,
        )
    assert caught.value.count == service.MAX_EXPORT_ROWS + 1


@pytest.mark.asyncio
async def test_source_duplicate_ids_and_incomplete_pages_fail_closed():
    duplicate = _Database([
        {"id": "same", "record_type": "outpatient"},
        {"id": "same", "record_type": "emergency"},
    ])
    with pytest.raises(service.OutpatientRecordSourceUnavailable):
        await service.load_source_rows(
            source=duplicate, table_name="medical_records", execute=_execute,
        )

    incomplete = _Database([], reported_count=1)
    with pytest.raises(service.OutpatientRecordSourceUnavailable):
        await service.load_source_rows(
            source=incomplete, table_name="medical_records", execute=_execute,
        )
