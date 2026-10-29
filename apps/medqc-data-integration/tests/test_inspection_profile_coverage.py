from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from medqc_ingest.catalog import CandidateInterface, DateSemantics
from medqc_ingest.coverage import CoverageStatus, build_coverage_contracts
from medqc_ingest.domain import (
    INTERFACE_REGISTRY,
    WEB_MR_SOURCE_COLUMNS,
    IngestError,
    resolve_interface,
)
from medqc_ingest.inspection import InspectionService, plan_inspection_calls
from medqc_ingest.profiling import ProfileService, ProfileSnapshotRow


def _metadata(semantics: DateSemantics, arguments: int) -> CandidateInterface:
    return CandidateInterface("web.test", arguments, semantics, "registered")


def test_three_day_and_range_planning_and_unknown_fail_closed() -> None:
    start, end = date(2026, 10, 26), date(2026, 10, 28)
    daily = plan_inspection_calls(_metadata(DateSemantics.SINGLE_DAY, 1), start, end)
    assert [call.arguments for call in daily] == [
        ("2026-10-26",),
        ("2026-10-27",),
        ("2026-10-28",),
    ]
    ranged = plan_inspection_calls(
        _metadata(DateSemantics.RANGE_INCLUSIVE, 2), start, end
    )
    assert ranged[0].arguments == ("2026-10-26", "2026-10-28")
    with pytest.raises(IngestError) as exc_info:
        plan_inspection_calls(_metadata(DateSemantics.UNKNOWN, 1), start, end)
    assert exc_info.value.location == "unverified_date_semantics"


class InspectCursor:
    columns = WEB_MR_SOURCE_COLUMNS
    source_types = tuple("str" for _ in WEB_MR_SOURCE_COLUMNS)

    def __init__(self, row: tuple[str, ...]) -> None:
        self.rows = [row]

    def fetchmany(self, size: int) -> list[tuple[str, ...]]:
        rows, self.rows = self.rows[:size], self.rows[size:]
        return rows

    def close(self) -> None:
        pass


class InspectSource:
    def __init__(self, row: tuple[str, ...], fail: bool) -> None:
        self.row = row
        self.fail = fail

    def open(self) -> None:
        if self.fail:
            raise IngestError("source_connect_error", "fake_connect")

    def query(self, spec: Any, arguments: Any) -> InspectCursor:
        return InspectCursor(self.row)

    def close(self) -> None:
        pass


class InspectRepository:
    def __init__(self) -> None:
        self.runs: list[tuple[Any, ...]] = []
        self.snapshots: list[Any] = []

    def connect_control(self) -> None:
        pass

    def acquire_lock(self, scope: str) -> bool:
        return True

    def release_lock(self, scope: str) -> None:
        pass

    def start_inspection(self, start: date, end: date) -> int:
        return 7

    def record_inspection_run(self, *args: Any) -> None:
        self.runs.append(args)

    def begin_snapshot(self) -> None:
        pass

    def write_inspection_schema(self, *args: Any) -> None:
        pass

    def write_snapshot(self, *args: Any) -> None:
        self.snapshots.extend(args[-1])

    def commit_snapshot(self) -> None:
        pass

    def rollback_snapshot(self) -> None:
        pass

    def finish_inspection(self, batch_id: int, status: str) -> None:
        self.finished = status

    def close(self) -> None:
        pass


def _mr_row() -> tuple[str, ...]:
    values = dict.fromkeys(WEB_MR_SOURCE_COLUMNS, "x")
    values.update(institute_id="I", patient_id="P", visit_id="V")
    return tuple(values[column] for column in WEB_MR_SOURCE_COLUMNS)


def test_inspection_isolates_call_failure_and_blocks_candidates() -> None:
    attempt = 0

    def factory() -> InspectSource:
        nonlocal attempt
        attempt += 1
        return InspectSource(_mr_row(), fail=attempt == 2)

    repository = InspectRepository()
    candidates = {
        "web.mr": CandidateInterface(
            "web.mr", 1, DateSemantics.SINGLE_DAY, "registered"
        ),
        "web.pending": CandidateInterface(
            "web.pending", 1, DateSemantics.SINGLE_DAY, "candidate"
        ),
    }
    result = InspectionService(factory, repository, 10).run_all(
        INTERFACE_REGISTRY,
        candidates,
        date(2026, 10, 26),
        date(2026, 10, 28),
    )
    assert (result.succeeded, result.failed, result.blocked) == (2, 1, 1)
    assert len(repository.snapshots) == 2
    assert repository.finished == "completed_with_failures"


class ProfileCursor:
    def __init__(self, rows: list[ProfileSnapshotRow]) -> None:
        self.rows = rows

    def fetchmany(self, size: int) -> list[ProfileSnapshotRow]:
        rows, self.rows = self.rows[:size], self.rows[size:]
        return rows

    def close(self) -> None:
        pass


class ProfileRepository:
    def __init__(self, rows: list[ProfileSnapshotRow]) -> None:
        self.rows = rows
        self.columns: list[Any] = []
        self.relations: list[Any] = []

    def load_inspection_schemas(self, batch_id: int) -> dict[str, tuple[Any, Any]]:
        return {"web.mr": (("institute_id", "patient_id", "visit_id"), ("str",) * 3)}

    def open_profile_rows(self, batch_id: int) -> ProfileCursor:
        return ProfileCursor(list(self.rows))

    def replace_profiles(self, batch_id: int, columns: Any, relations: Any) -> None:
        self.columns = list(columns)
        self.relations = list(relations)

    def close(self) -> None:
        pass


def test_profile_counts_missing_duplicate_and_relation_without_values() -> None:
    rows = [
        ProfileSnapshotRow(
            "web.mr",
            {"institute_id": "I", "patient_id": "P", "visit_id": "V"},
            "k",
            "c",
            True,
        ),
        ProfileSnapshotRow(
            "web.mr",
            {"institute_id": "I", "patient_id": "P", "visit_id": "V"},
            "k",
            "c",
            True,
        ),
        ProfileSnapshotRow(
            "web.mr",
            {"institute_id": "I", "patient_id": None, "visit_id": "X"},
            None,
            None,
            False,
        ),
    ]
    repository = ProfileRepository(rows)
    result = ProfileService(repository, 2).run(7, {"web.mr": resolve_interface("web.mr")})
    assert result.rows_profiled == 3
    key_relation = next(
        row for row in repository.relations if row["relation_name"] == "candidate_key"
    )
    assert key_relation["missing_rows"] == 1
    assert key_relation["duplicate_rows"] == 1
    serialized = repr((repository.columns, repository.relations))
    assert "patient-value" not in serialized


def test_coverage_has_53_requirements_and_name_match_stays_blocked() -> None:
    contracts = build_coverage_contracts()
    assert len(contracts) == 53
    assert {status.value for status in CoverageStatus} == {
        "direct",
        "derived",
        "partial",
        "missing",
        "blocked",
    }
    assert sum(row.status is CoverageStatus.DIRECT for row in contracts) == 7
    diagnosis = next(row for row in contracts if row.source_type == "diagnosis")
    assert diagnosis.status is CoverageStatus.BLOCKED
    assert diagnosis.evidence == "name_match_only_not_field_verified"
