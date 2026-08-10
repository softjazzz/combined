from __future__ import annotations

from typing import Any

import pytest

from app.services.case_identity import CaseRef
from app.services.case_set_sync_service import CaseSetSyncService


def test_case_set_sync_only_continues_cases_with_visible_primary_record():
    visible = CaseRef("HOSPITAL-A", "PATIENT-A", "VISIT-1")
    missing = CaseRef("HOSPITAL-B", "PATIENT-B", "VISIT-1")
    fetched_case_refs: dict[str, tuple[CaseRef, ...]] = {}
    refreshed_rows: list[dict[str, Any]] = []

    def _fetch(**kwargs: Any) -> list[dict[str, Any]]:
        source_table = kwargs["source_table"]
        fetched_case_refs[source_table] = tuple(kwargs["case_refs"])
        if source_table == "mr":
            return [visible.as_dict()]
        return [visible.as_dict()]

    def _refresh(**kwargs: Any) -> dict[str, Any]:
        refreshed_rows.extend(kwargs["rows"])
        return {
            "scenes": {"running": {"failed": 0}, "final": {"failed": 0}},
            "domains": {"course": {"failed": 0}},
        }

    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {"name": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]},
            {
                "name": "daily_course_record",
                "key_fields": ["institute_id", "patient_id", "visit_id"],
            },
        ],
        row_fetcher=_fetch,
        row_upserter=lambda **kwargs: len(kwargs["records"]),
        bundle_refresher=_refresh,
        visit_index_ingester=lambda **_: {"processed": 1},
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
    )

    result = service.sync_case_set(
        case_refs=(visible, missing),
        table_names=("mr", "daily_course_record"),
        policy_version="case-set-sync-v1",
    )

    assert result.primary_visible is True
    assert result.visible_case_refs == (visible,)
    assert result.missing_primary_case_refs == (missing,)
    assert fetched_case_refs["mr"] == (visible, missing)
    assert fetched_case_refs["daily_course_record"] == (visible,)
    assert refreshed_rows == [visible.as_dict()]
    assert result.to_public_dict()["primary_visible"] is True
    assert result.to_public_dict()["visible_case_refs"] == [visible.as_dict()]
    assert result.to_public_dict()["missing_primary_case_refs"] == [missing.as_dict()]


def test_case_set_sync_does_not_refresh_bundles_after_hard_detail_failure():
    case_ref = CaseRef("HOSPITAL-A", "PATIENT-A", "VISIT-1")
    refresh_calls: list[dict[str, Any]] = []

    def _fetch(**kwargs: Any) -> list[dict[str, Any]]:
        if kwargs["source_table"] == "mr":
            return [case_ref.as_dict()]
        raise RuntimeError("detail read failed")

    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {"name": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]},
            {
                "name": "daily_course_record",
                "key_fields": ["institute_id", "patient_id", "visit_id"],
            },
        ],
        row_fetcher=_fetch,
        row_upserter=lambda **kwargs: len(kwargs["records"]),
        bundle_refresher=lambda **kwargs: refresh_calls.append(kwargs) or {},
        visit_index_ingester=lambda **_: {"processed": 1},
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
    )

    with pytest.raises(RuntimeError, match="detail read failed"):
        service.sync_case_set(
            case_refs=(case_ref,),
            table_names=("mr", "daily_course_record"),
            policy_version="case-set-sync-v1",
        )

    assert refresh_calls == []


def test_case_set_sync_refreshes_after_controlled_optional_table_missing():
    case_ref = CaseRef("HOSPITAL-A", "PATIENT-A", "VISIT-1")
    refresh_calls: list[dict[str, Any]] = []
    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {"name": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]}
        ],
        row_fetcher=lambda **_: [case_ref.as_dict()],
        row_upserter=lambda **kwargs: len(kwargs["records"]),
        bundle_refresher=lambda **kwargs: refresh_calls.append(kwargs)
        or {
            "scenes": {"running": {"failed": 0}, "final": {"failed": 0}},
            "domains": {},
        },
        visit_index_ingester=lambda **_: {"processed": 1},
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
    )

    result = service.sync_case_set(
        case_refs=(case_ref,),
        table_names=("mr", "optional_detail"),
        policy_version="case-set-sync-v1",
    )

    optional_result = next(
        item for item in result.synced_tables if item["table_name"] == "optional_detail"
    )
    assert optional_result["sync_status"] == "source_table_unavailable"
    assert optional_result["error_category"] == "source_config_missing"
    assert len(refresh_calls) == 1


@pytest.mark.parametrize(
    "refresh_stats",
    [
        {
            "scenes": {"running": {"failed": 1}, "final": {"failed": 0}},
            "domains": {},
        },
        {
            "scenes": {"running": {"failed": 0}, "final": {"failed": 0}},
            "domains": {"course": {"failed": 1}},
        },
    ],
)
def test_case_set_sync_fails_closed_when_any_bundle_refresh_fails(
    refresh_stats: dict[str, Any],
):
    case_ref = CaseRef("HOSPITAL-A", "PATIENT-A", "VISIT-1")
    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {"name": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]}
        ],
        row_fetcher=lambda **_: [case_ref.as_dict()],
        row_upserter=lambda **kwargs: len(kwargs["records"]),
        bundle_refresher=lambda **_: refresh_stats,
        visit_index_ingester=lambda **_: {"processed": 1},
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
    )

    with pytest.raises(RuntimeError, match="病例Bundle统一刷新失败"):
        service.sync_case_set(
            case_refs=(case_ref,),
            table_names=("mr",),
            policy_version="case-set-sync-v1",
        )


def test_case_set_sync_refreshes_all_bundles_once_after_detail_tables(monkeypatch):
    events: list[tuple[str, Any]] = []
    case_refs = (CaseRef("I-1", "P-1", "V-1"), CaseRef("I-2", "P-2", "V-1"))

    monkeypatch.setattr(
        "app.services.case_set_sync_service.get_remote_db_url",
        lambda: "postgresql://source",
    )
    monkeypatch.setattr(
        "app.services.case_set_sync_service.load_db_config",
        lambda: {"remote_schema": "cdm"},
    )

    def _fetch(**kwargs: Any) -> list[dict[str, Any]]:
        events.append(("fetch", kwargs["source_table"]))
        assert tuple(kwargs["case_refs"]) == case_refs
        return [case_ref.as_dict() for case_ref in case_refs]

    def _upsert(**kwargs: Any) -> int:
        events.append(("upsert", kwargs["table_name"]))
        return len(kwargs["records"])

    def _refresh(**kwargs: Any) -> dict[str, Any]:
        events.append(("refresh", tuple(tuple(row.values()) for row in kwargs["rows"])))
        assert kwargs["scenes"] == ("running", "final")
        return {
            "scenes": {"running": {"failed": 0}, "final": {"failed": 0}},
            "domains": {"course": {"failed": 0}},
        }

    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {"name": "daily_course_record", "key_fields": ["document_id"]},
            {"name": "mr", "key_fields": ["visit_id"]},
        ],
        row_fetcher=_fetch,
        row_upserter=_upsert,
        bundle_refresher=_refresh,
        visit_index_ingester=lambda **_: {"processed": 2},
    )
    result = service.sync_case_set(
        case_refs=case_refs,
        table_names=("daily_course_record", "mr"),
        policy_version="case-set-sync-v1",
    )

    assert result.primary_visible is True
    assert [item[1] for item in events if item[0] == "fetch"] == [
        "mr",
        "daily_course_record",
    ]
    assert events[-1][0] == "refresh"
    assert sum(1 for event, _ in events if event == "refresh") == 1
    assert result.total_rows_pulled == 4
    assert result.total_rows_upserted == 4


def test_case_set_sync_injects_configured_institute_at_public_boundary():
    fetched_case_refs: list[CaseRef] = []
    upserted_rows: list[dict[str, Any]] = []
    refreshed_rows: list[dict[str, Any]] = []

    def _fetch(**kwargs: Any) -> list[dict[str, Any]]:
        fetched_case_refs.extend(kwargs["case_refs"])
        return [{"patient_id": "P-1", "visit_id": "V-1"}]

    def _upsert(**kwargs: Any) -> int:
        upserted_rows.extend(kwargs["records"])
        return len(kwargs["records"])

    def _refresh(**kwargs: Any) -> dict[str, Any]:
        refreshed_rows.extend(kwargs["rows"])
        return {
            "scenes": {"running": {"failed": 0}, "final": {"failed": 0}},
            "domains": {},
        }

    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {"name": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]}
        ],
        row_fetcher=_fetch,
        row_upserter=_upsert,
        bundle_refresher=_refresh,
        visit_index_ingester=lambda **_: {"processed": 1},
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {
            "remote_schema": "public",
            "default_institute_id": "LOCAL-HOSPITAL",
        },
    )

    result = service.sync_case_set(
        case_refs=[{"patient_id": "P-1", "visit_id": "V-1"}],
        table_names=("mr",),
        policy_version="case-set-sync-v1",
    )

    expected = CaseRef("LOCAL-HOSPITAL", "P-1", "V-1")
    assert result.case_refs == (expected,)
    assert fetched_case_refs == [expected]
    assert upserted_rows == [expected.as_dict()]
    assert refreshed_rows == [expected.as_dict()]
    assert result.primary_visible is True


def test_case_set_sync_preserves_explicit_source_institute_id():
    captured_rows: list[dict[str, Any]] = []
    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {"name": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]}
        ],
        row_fetcher=lambda **_: [
            {"institute_id": "SOURCE-HOSPITAL", "patient_id": "P-1", "visit_id": "V-1"}
        ],
        row_upserter=lambda **kwargs: captured_rows.extend(kwargs["records"]) or 1,
        bundle_refresher=lambda **_: {
            "scenes": {"running": {"failed": 0}, "final": {"failed": 0}},
            "domains": {},
        },
        visit_index_ingester=lambda **_: {"processed": 1},
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {
            "remote_schema": "public",
            "default_institute_id": "LOCAL-HOSPITAL",
        },
    )

    result = service.sync_case_set(
        case_refs=[
            {"institute_id": "SOURCE-HOSPITAL", "patient_id": "P-1", "visit_id": "V-1"}
        ],
        table_names=("mr",),
        policy_version="case-set-sync-v1",
    )

    assert result.case_refs == (CaseRef("SOURCE-HOSPITAL", "P-1", "V-1"),)
    assert captured_rows[0]["institute_id"] == "SOURCE-HOSPITAL"


def test_case_set_sync_rejects_incomplete_identity_without_configured_institute():
    service = CaseSetSyncService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public", "default_institute_id": ""},
    )
    with pytest.raises(ValueError, match="三坐标"):
        service.sync_case_set(
            case_refs=[{"institute_id": "", "patient_id": "P", "visit_id": "V"}],
            table_names=("mr",),
            policy_version="case-set-sync-v1",
        )
