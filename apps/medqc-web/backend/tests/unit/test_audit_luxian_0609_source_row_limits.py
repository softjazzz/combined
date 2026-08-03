import json

import pytest

from scripts.audit_luxian_0609_source_row_limits import (
    AuditContractError,
    VisitCoordinate,
    build_safe_report_payload,
    count_source_rows_in_batches,
    coordinate_set_hash,
    freeze_coordinate_rows,
    merge_audit_coordinates,
    resolve_focus_coordinate,
    run_in_read_only_snapshot,
    select_unique_pool,
    summarize_source_counts,
)


class _MappingRows:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> "_MappingRows":
        return self

    def all(self) -> list[dict[str, object]]:
        return self._rows


class _CountingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def execute(self, statement: object, params: dict[str, object]) -> _MappingRows:
        sql = str(statement)
        self.calls.append((sql, dict(params)))
        rows = []
        indexes = sorted(
            int(key[1:]) for key in params if key.startswith("i") and key[1:].isdigit()
        )
        for index in indexes:
            rows.append(
                {
                    "institute_id": params[f"i{index}"],
                    "patient_id": params[f"p{index}"],
                    "visit_id": params[f"v{index}"],
                    "row_count": index % 3,
                }
            )
        return _MappingRows(rows)


class _Context:
    def __init__(self, value: object, events: list[str], label: str) -> None:
        self.value = value
        self.events = events
        self.label = label

    def __enter__(self) -> object:
        self.events.append(f"enter:{self.label}")
        return self.value

    def __exit__(self, *_args: object) -> None:
        self.events.append(f"exit:{self.label}")


class _ReadOnlyConnection:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def execution_options(self, **options: object) -> "_ReadOnlyConnection":
        self.events.append(f"isolation:{options['isolation_level']}")
        return self

    def __enter__(self) -> "_ReadOnlyConnection":
        self.events.append("enter:connection")
        return self

    def __exit__(self, *_args: object) -> None:
        self.events.append("exit:connection")

    def begin(self) -> _Context:
        return _Context(self, self.events, "transaction")

    def exec_driver_sql(self, sql: str) -> None:
        self.events.append(f"driver:{sql}")


class _ReadOnlyEngine:
    def __init__(self, events: list[str]) -> None:
        self.connection = _ReadOnlyConnection(events)

    def connect(self) -> _ReadOnlyConnection:
        return self.connection


def test_summary_includes_zero_row_visits_and_limit_hits() -> None:
    summary = summarize_source_counts(
        counts_by_visit={
            "visit-1": 0,
            "visit-2": 1,
            "visit-3": 2,
            "visit-4": 100,
            "visit-5": 101,
        },
        all_visit_refs=("visit-1", "visit-2", "visit-3", "visit-4", "visit-5"),
        current_limit=100,
    )

    assert summary["sample_visit_count"] == 5
    assert summary["nonempty_visit_count"] == 4
    assert summary["p50"] == 2
    assert summary["p95"] == 101
    assert summary["p99"] == 101
    assert summary["max"] == 101
    assert summary["at_limit_count"] == 1
    assert summary["above_limit_count"] == 1


def test_safe_report_redacts_coordinates_and_hash_is_order_independent() -> None:
    coordinates = (
        VisitCoordinate("hospital-secret", "patient-secret-a", "visit-secret-a"),
        VisitCoordinate("hospital-secret", "patient-secret-b", "visit-secret-b"),
    )

    report = build_safe_report_payload(
        audit_started_at="2026-08-03T12:00:00Z",
        git_commit="abc123",
        pool_id="pool-0426",
        pool_name="0426",
        frozen_coordinates=coordinates,
        excluded_missing_coordinates=1,
        focus_coordinate_missing=0,
        focus_coordinate_ambiguous=0,
        focus_results={
            "focus_case_a": {"row_count": 3, "truncated": False},
            "focus_case_b": {"row_count": 0, "truncated": False},
        },
        source_summaries=(
            {"source_key": "daily_course_record", "max": 3},
        ),
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["coordinate_set_hash"] == coordinate_set_hash(tuple(reversed(coordinates)))
    assert coordinate_set_hash(coordinates) != coordinate_set_hash(
        (
            coordinates[0],
            VisitCoordinate("hospital-secret", "patient-secret-b", "visit-changed"),
        )
    )
    assert report["frozen_coordinate_count"] == 2
    assert report["focus_results"]["focus_case_a"]["row_count"] == 3
    assert "hospital-secret" not in serialized
    assert "patient-secret" not in serialized
    assert "visit-secret" not in serialized


def test_pool_name_must_match_exactly_one_row() -> None:
    matched = select_unique_pool(
        ({"id": "pool-1", "name": "0426"},),
        pool_id=None,
        pool_name="0426",
    )
    assert matched == {"id": "pool-1", "name": "0426"}

    with pytest.raises(AuditContractError, match="pool_not_found"):
        select_unique_pool((), pool_id=None, pool_name="0426")
    with pytest.raises(AuditContractError, match="pool_name_ambiguous"):
        select_unique_pool(
            (
                {"id": "pool-1", "name": "0426"},
                {"id": "pool-2", "name": "0426"},
            ),
            pool_id=None,
            pool_name="0426",
        )


def test_focus_coordinate_never_selects_first_ambiguous_visit() -> None:
    frozen, excluded = freeze_coordinate_rows(
        (
            {
                "matched_institute_id": "i1",
                "matched_patient_id": "p1",
                "matched_visit_id": "focus-1",
            },
            {
                "matched_institute_id": "",
                "matched_patient_id": "missing",
                "matched_visit_id": "focus-2",
            },
        )
    )
    assert excluded == 1
    assert resolve_focus_coordinate(
        visit_id="focus-1", frozen_coordinates=frozen, fallback_coordinates=()
    ) == (frozen[0], "pool")

    with pytest.raises(AuditContractError, match="focus_coordinate_missing"):
        resolve_focus_coordinate(
            visit_id="missing", frozen_coordinates=frozen, fallback_coordinates=()
        )
    with pytest.raises(AuditContractError, match="focus_coordinate_ambiguous"):
        resolve_focus_coordinate(
            visit_id="ambiguous",
            frozen_coordinates=frozen,
            fallback_coordinates=(
                VisitCoordinate("i1", "p1", "ambiguous"),
                VisitCoordinate("i2", "p2", "ambiguous"),
            ),
        )


def test_physical_source_counts_use_three_coordinate_batches() -> None:
    connection = _CountingConnection()
    coordinates = tuple(
        VisitCoordinate("hospital", f"patient-{index}", f"visit-{index}")
        for index in range(401)
    )

    counts = count_source_rows_in_batches(
        connection,
        schema="cdm",
        source_key="daily_course_record",
        coordinates=coordinates,
        batch_size=200,
        allowed_source_keys={"daily_course_record"},
    )

    assert len(connection.calls) == 3
    assert len(counts) == 401
    assert all("WITH visit_keys" in sql for sql, _ in connection.calls)
    assert all("patient-" not in sql and "visit-" not in sql for sql, _ in connection.calls)
    assert all(len(params) <= 600 for _, params in connection.calls)


def test_audit_uses_one_repeatable_read_read_only_snapshot() -> None:
    events: list[str] = []

    result = run_in_read_only_snapshot(
        _ReadOnlyEngine(events),
        lambda _connection: events.append("audit") or "done",
    )

    assert result == "done"
    assert events == [
        "isolation:REPEATABLE READ",
        "enter:connection",
        "enter:transaction",
        "driver:SET TRANSACTION READ ONLY",
        "audit",
        "exit:transaction",
        "exit:connection",
    ]


def test_focus_coordinates_are_added_to_frozen_audit_set_without_duplicates() -> None:
    pool_coordinate = VisitCoordinate("i1", "p1", "v1")
    extra_focus = VisitCoordinate("i2", "p2", "v2")

    merged = merge_audit_coordinates(
        (pool_coordinate,),
        {"focus_case_a": pool_coordinate, "focus_case_b": extra_focus},
    )

    assert merged == (pool_coordinate, extra_focus)
