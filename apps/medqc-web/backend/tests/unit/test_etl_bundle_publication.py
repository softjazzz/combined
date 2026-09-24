from __future__ import annotations

from datetime import date

import pytest

from app.services import etl_sync
from app.services.bundles import publication
from app.services.case_identity import CaseRef
from app.services.case_scope_service import HospitalizationScopeResult
from app.services.case_set_sync_service import CaseSetSyncResult


_REF = CaseRef("H1", "P1", "V1")
_STAGING = f"{publication.INVALIDATED_POLICY_VERSION}:{'a' * 32}"


def _refresh_counts(count: int = 1) -> dict:
    return {
        "scenes": {
            name: {"processed": count, "updated": count, "failed": 0}
            for name in ("running", "final")
        },
        "domains": {
            name: {"processed": count, "updated": count, "failed": 0}
            for name in (
                "admission", "course", "surgery", "consult_discussion",
                "terminal", "index_coding_settlement",
            )
        },
    }


def _result(*, unavailable_detail: bool = False, unavailable_primary: bool = False,
            refresh: dict | None = None):
    tables = [
        {"table_name": "mr", "rows_pulled": 1, "rows_upserted": 1,
         "sync_status": "source_table_unavailable" if unavailable_primary else "synced"},
        {
            "table_name": "daily_course_record",
            "rows_pulled": 0,
            "rows_upserted": 0,
            "sync_status": "source_table_unavailable" if unavailable_detail else "synced",
        },
    ]
    return CaseSetSyncResult(
        case_refs=(_REF,),
        primary_visible=True,
        visible_case_refs=(_REF,),
        missing_primary_case_refs=(),
        synced_tables=tuple(tables),
        source_rows_by_table={},
        total_rows_pulled=1,
        total_rows_upserted=1,
        bundle_refresh=_refresh_counts() if refresh is None else refresh,
    )


def _install(monkeypatch, events: list, sync_action):
    class ScopeService:
        def resolve_hospitalization_scope(self, **_kwargs):
            return HospitalizationScopeResult(
                case_refs=(_REF,),
                selected=({**_REF.as_dict(), "hospitalization_status": "active"},),
                all_selected=(),
                sources_used=("inpat_registration",),
                source_status="ready",
                warnings=(),
            )

    class SyncService:
        def sync_case_set(self, **kwargs):
            events.append(("sync", kwargs))
            return sync_action(kwargs)

    monkeypatch.setattr(etl_sync, "engine", None)
    monkeypatch.setattr(etl_sync, "_upsert_sync_job_state", lambda _state: None)
    monkeypatch.setattr(etl_sync, "get_remote_db_url", lambda: "postgresql://source")
    monkeypatch.setattr(etl_sync, "_resolve_sync_mode", lambda: "table")
    monkeypatch.setattr(
        etl_sync,
        "_resolve_target_tables",
        lambda _tables: (
            [
                {"name": "mr", "source_table": "mr"},
                {"name": "admission_record", "source_table": "admission_record"},
                {"name": "daily_course_record", "source_table": "daily_course_record"},
            ],
            [],
        ),
    )
    monkeypatch.setattr(etl_sync, "validate_pg_sync_plan", lambda **_kwargs: {"executable": True})
    monkeypatch.setattr(etl_sync, "load_sync_policy", lambda: {})
    monkeypatch.setattr(etl_sync, "_current_hospital_date", lambda: date(2026, 9, 24))
    monkeypatch.setattr(etl_sync, "_create_case_scope_service", ScopeService)
    monkeypatch.setattr(etl_sync, "_create_case_set_sync_service", SyncService)
    monkeypatch.setattr(etl_sync, "_mark_primary_records_sync_completed", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(publication, "new_bundle_staging_token", lambda: _STAGING)
    monkeypatch.setattr(
        publication,
        "invalidate_bundle_variants",
        lambda refs, **kwargs: events.append(("invalidate", tuple(refs), kwargs)),
    )
    monkeypatch.setattr(
        publication,
        "publish_bundle_variants",
        lambda refs, **kwargs: events.append(("publish", tuple(refs), kwargs)),
    )


def test_etl_fences_before_first_table_and_publishes_original_policy(monkeypatch):
    events = []

    def sync_action(kwargs):
        events.append(("first_cdm_write",))
        return _result()

    _install(monkeypatch, events, sync_action)
    result = etl_sync.run_sync(scene="running", policy_version="hospital-policy-v7")

    assert result["success"] is True
    assert [event[0] for event in events] == [
        "invalidate", "sync", "first_cdm_write", "publish",
    ]
    assert events[0][1] == (_REF,)
    assert events[1][1]["policy_version"] == "hospital-policy-v7"
    assert events[1][1]["bundle_policy_version"] == _STAGING
    assert events[-1][2]["staging_token"] == _STAGING
    assert events[-1][2]["published_policy_version"] == "hospital-policy-v7"


@pytest.mark.parametrize("failure_stage", ["second_table", "bundle_refresh"])
def test_etl_keeps_marker_when_sync_or_refresh_fails(monkeypatch, failure_stage):
    events = []

    def sync_action(_kwargs):
        events.append(("first_cdm_write",))
        raise RuntimeError(failure_stage)

    _install(monkeypatch, events, sync_action)
    result = etl_sync.run_sync(scene="running", policy_version="v7")

    assert result["success"] is False
    assert result["status"] == "failed"
    assert [event[0] for event in events] == ["invalidate", "sync", "first_cdm_write"]


def test_etl_fences_new_case_without_prior_bundle_then_fails_on_unavailable_detail(monkeypatch):
    events = []
    _install(monkeypatch, events, lambda _kwargs: _result(unavailable_detail=True, refresh={}))

    result = etl_sync.run_sync(scene="running", policy_version="v7")

    assert result["success"] is False
    assert result["status"] == "partial"
    assert result["bundle_refresh"] == {}
    assert [event[0] for event in events] == ["invalidate", "sync"]


def test_etl_does_not_publish_when_primary_source_is_missing_but_other_anchor_is_visible(monkeypatch):
    events = []
    _install(monkeypatch, events, lambda _kwargs: _result(unavailable_primary=True))

    result = etl_sync.run_sync(scene="running", policy_version="v7")

    assert result["success"] is False
    assert result["status"] == "partial"
    assert [event[0] for event in events] == ["invalidate", "sync"]


def test_etl_keeps_marker_when_publication_fails(monkeypatch):
    events = []
    _install(monkeypatch, events, lambda _kwargs: _result())

    def fail_publish(_refs, **_kwargs):
        events.append(("publish_attempt",))
        raise RuntimeError("publish rollback")

    monkeypatch.setattr(publication, "publish_bundle_variants", fail_publish)
    result = etl_sync.run_sync(scene="running", policy_version="v7")

    assert result["success"] is False
    assert result["status"] == "failed"
    assert [event[0] for event in events] == ["invalidate", "sync", "publish_attempt"]
