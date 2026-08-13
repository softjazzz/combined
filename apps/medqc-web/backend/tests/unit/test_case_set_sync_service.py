from __future__ import annotations

from typing import Any

import pytest

from app.services.case_identity import CaseRef
from app.services.case_set_sync_service import CaseSetSyncService


def test_running_case_without_mr_no_is_visible_from_inpat_registration():
    case_ref = CaseRef("H1", "P1", "V1")
    fetched_case_refs: dict[str, tuple[CaseRef, ...]] = {}

    def _fetch(**kwargs: Any) -> list[dict[str, Any]]:
        source_table = kwargs["source_table"]
        fetched_case_refs[source_table] = tuple(kwargs["case_refs"])
        if source_table == "mr":
            return []
        if source_table == "inpat_registration":
            return [{**case_ref.as_dict(), "mr_no": "", "discharge_datetime": None}]
        return [case_ref.as_dict()]

    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {"name": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]},
            {
                "name": "inpat_registration",
                "key_fields": ["institute_id", "patient_id", "visit_id"],
            },
            {
                "name": "daily_course_record",
                "key_fields": ["institute_id", "patient_id", "visit_id"],
            },
        ],
        row_fetcher=_fetch,
        row_upserter=lambda **kwargs: len(kwargs["records"]),
        bundle_refresher=lambda **_: {"scenes": {}, "domains": {}},
        visit_index_ingester=lambda **_: {"processed": 1},
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
    )

    result = service.sync_case_set(
        case_refs=(case_ref,),
        table_names=("mr", "inpat_registration", "daily_course_record"),
        policy_version="case-set-sync-v1",
        sync_scene="running",
    )

    assert result.visible_case_refs == (case_ref,)
    assert result.missing_primary_case_refs == ()
    assert fetched_case_refs["daily_course_record"] == (case_ref,)


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
        sync_scene="running",
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
            sync_scene="running",
        )

    assert refresh_calls == []


def test_case_set_sync_does_not_refresh_after_controlled_detail_table_missing():
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
        sync_scene="running",
    )

    optional_result = next(
        item for item in result.synced_tables if item["table_name"] == "optional_detail"
    )
    assert optional_result["sync_status"] == "source_table_unavailable"
    assert optional_result["error_category"] == "source_config_missing"
    assert refresh_calls == []
    assert result.bundle_refresh == {}


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
            sync_scene="running",
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
        sync_scene="running",
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
        sync_scene="running",
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
        sync_scene="running",
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
            sync_scene="running",
        )


@pytest.mark.parametrize(
    ("sync_scene", "allow_frontpage_only"),
    [
        ("running", False),
        ("final", False),
        ("frontpage", True),
        ("coding", True),
        ("settlement", False),
        ("both", True),
    ],
)
def test_case_set_sync_passes_controlled_scene_to_visit_index(
    sync_scene: str,
    allow_frontpage_only: bool,
):
    case_ref = CaseRef("H1", "P1", "V1")
    ingest_calls: list[dict[str, Any]] = []
    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {"name": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]}
        ],
        row_fetcher=lambda **_: [case_ref.as_dict()],
        row_upserter=lambda **kwargs: len(kwargs["records"]),
        bundle_refresher=lambda **_: {
            "scenes": {"running": {"failed": 0}, "final": {"failed": 0}},
            "domains": {},
        },
        visit_index_ingester=lambda **kwargs: ingest_calls.append(kwargs) or {},
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
    )

    service.sync_case_set(
        case_refs=(case_ref,),
        table_names=("mr",),
        policy_version="case-set-sync-v1",
        sync_scene=sync_scene.upper(),
    )

    assert len(ingest_calls) == 1
    assert ingest_calls[0]["sync_scene"] == sync_scene
    assert ingest_calls[0]["allow_frontpage_only"] is allow_frontpage_only


def test_case_set_sync_groups_mixed_case_scenes_without_guessing():
    running_ref = CaseRef("H1", "P1", "SAME-VISIT")
    final_ref = CaseRef("H2", "P2", "SAME-VISIT")
    ingest_calls: list[dict[str, Any]] = []
    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {"name": "mr", "key_fields": ["institute_id", "patient_id", "visit_id"]}
        ],
        row_fetcher=lambda **_: [running_ref.as_dict(), final_ref.as_dict()],
        row_upserter=lambda **kwargs: len(kwargs["records"]),
        bundle_refresher=lambda **_: {
            "scenes": {"running": {"failed": 0}, "final": {"failed": 0}},
            "domains": {},
        },
        visit_index_ingester=lambda **kwargs: ingest_calls.append(kwargs) or {},
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
    )

    service.sync_case_set(
        case_refs=(running_ref, final_ref),
        table_names=("mr",),
        policy_version="case-set-sync-v1",
        sync_scene="both",
        case_scene_by_ref={running_ref: "running", final_ref: "final"},
    )

    assert [call["sync_scene"] for call in ingest_calls] == ["running", "final"]
    assert ingest_calls[0]["rows"] == [running_ref.as_dict()]
    assert ingest_calls[1]["rows"] == [final_ref.as_dict()]


def test_case_set_sync_rejects_incomplete_case_scene_mapping():
    case_refs = (CaseRef("H1", "P1", "V1"), CaseRef("H2", "P2", "V2"))
    service = CaseSetSyncService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
    )

    with pytest.raises(ValueError, match="病例场景映射不完整"):
        service.sync_case_set(
            case_refs=case_refs,
            table_names=("mr",),
            policy_version="case-set-sync-v1",
            sync_scene="both",
            case_scene_by_ref={case_refs[0]: "running"},
        )


def test_case_set_sync_rejects_unknown_scene():
    service = CaseSetSyncService(
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
    )

    with pytest.raises(ValueError, match="同步场景无效"):
        service.sync_case_set(
            case_refs=(CaseRef("H1", "P1", "V1"),),
            table_names=("mr",),
            policy_version="case-set-sync-v1",
            sync_scene="guessed-scene",
        )


def test_full_visit_reload_replaces_exact_case_snapshot_even_when_source_is_empty():
    case_ref = CaseRef("H1", "P1", "V1")
    upsert_calls: list[dict[str, Any]] = []
    refresh_calls: list[dict[str, Any]] = []

    def _fetch(**kwargs: Any) -> list[dict[str, Any]]:
        if kwargs["source_table"] == "mr":
            return [case_ref.as_dict()]
        return []

    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {
                "name": "mr",
                "key_fields": ["institute_id", "patient_id", "visit_id"],
                "incremental_strategy": "full_visit_reload",
            },
            {
                "name": "daily_course_record",
                "key_fields": [
                    "institute_id",
                    "patient_id",
                    "visit_id",
                    "document_id",
                ],
                "incremental_strategy": "full_visit_reload",
            },
        ],
        row_fetcher=_fetch,
        row_upserter=lambda **kwargs: upsert_calls.append(kwargs) or len(
            kwargs["records"]
        ),
        bundle_refresher=lambda **kwargs: refresh_calls.append(kwargs)
        or {"scenes": {}, "domains": {}},
        visit_index_ingester=lambda **_: {"processed": 1},
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
    )

    result = service.sync_case_set(
        case_refs=(case_ref,),
        table_names=("mr", "daily_course_record"),
        policy_version="case-set-sync-v1",
        sync_scene="final",
    )

    detail_call = next(
        call for call in upsert_calls if call["table_name"] == "daily_course_record"
    )
    assert detail_call["records"] == []
    assert detail_call["replace_case_refs"] == (case_ref,)
    assert result.bundle_refresh
    assert len(refresh_calls) == 1


def test_incremental_table_does_not_replace_existing_case_snapshot():
    case_ref = CaseRef("H1", "P1", "V1")
    upsert_calls: list[dict[str, Any]] = []
    service = CaseSetSyncService(
        table_catalog_loader=lambda: [
            {
                "name": "mr",
                "key_fields": ["institute_id", "patient_id", "visit_id"],
                "incremental_strategy": "updated_at",
            }
        ],
        row_fetcher=lambda **_: [case_ref.as_dict()],
        row_upserter=lambda **kwargs: upsert_calls.append(kwargs) or 1,
        bundle_refresher=lambda **_: {"scenes": {}, "domains": {}},
        visit_index_ingester=lambda **_: {"processed": 1},
        remote_url_loader=lambda: "postgresql://source",
        db_config_loader=lambda: {"remote_schema": "public"},
    )

    service.sync_case_set(
        case_refs=(case_ref,),
        table_names=("mr",),
        policy_version="case-set-sync-v1",
        sync_scene="final",
    )

    assert "replace_case_refs" not in upsert_calls[0]
