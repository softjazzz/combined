from types import SimpleNamespace

import pytest

from app.services import custom_qc_sample_pool_service as module
from app.services.case_identity import CaseRef


def _refresh_counts(visible_count=1):
    counts = {"processed": visible_count, "updated": visible_count, "failed": 0}
    return {
        "scenes": {name: dict(counts) for name in ("running", "final")},
        "domains": {
            name: dict(counts)
            for name in (
                "admission", "course", "surgery", "consult_discussion",
                "terminal", "index_coding_settlement",
            )
        },
    }


def _service(monkeypatch, *, refs=None, sync_result=None, sync_error=None):
    refs = refs or (CaseRef("H1", "P1", "V1"),)
    service = object.__new__(module.CustomQCSamplePoolService)
    events = []
    monkeypatch.setattr(service, "_list_sync_candidate_items", lambda **_: [{"id": "item-1"}])
    monkeypatch.setattr(
        service,
        "_resolve_remote_visit_keys",
        lambda **_: {
            "matched": len(refs), "ambiguous": 0, "unmatched": 0,
            "visit_keys": [(ref.patient_id, ref.visit_id) for ref in refs],
            "case_refs": refs,
            "case_scene_by_ref": {ref: "running" for ref in refs},
        },
    )
    monkeypatch.setattr(
        service, "resolve_sync_table_names",
        lambda **_: {"table_names": ["mr", "daily_course_record"], "group_ids": [], "missing_group_ids": []},
    )
    monkeypatch.setattr(module, "_load_previous_hospitalization_states", lambda items: {})
    monkeypatch.setattr(module, "_collect_current_hospitalization_states", lambda rows: {})
    monkeypatch.setattr(service, "get_pool", lambda **_: {"id": "pool-1"})
    monkeypatch.setattr(service, "match_pool_items", lambda **_: events.append("match") or {"pool": {"id": "pool-1"}})
    monkeypatch.setattr(
        service, "_mark_sync_items_bundle_pending",
        lambda **_: events.append("pending"),
    )
    monkeypatch.setattr(module, "new_bundle_staging_token", lambda: "task-record-sync-invalidated-v1:" + "a" * 32)
    monkeypatch.setattr(
        module, "invalidate_bundle_variants",
        lambda case_refs, **_: events.append(("invalidate", tuple(case_refs))),
    )
    monkeypatch.setattr(
        module, "publish_bundle_variants",
        lambda case_refs, **kwargs: events.append(("publish", tuple(case_refs), kwargs)),
    )

    def sync_case_set(**kwargs):
        events.append(("sync", kwargs))
        if sync_error:
            events.append("primary_committed")
            raise sync_error
        return sync_result

    monkeypatch.setattr(
        module, "CaseSetSyncService",
        lambda **_: SimpleNamespace(sync_case_set=sync_case_set),
    )
    return service, events


def _result(refs, *, refresh=None, statuses=None):
    return SimpleNamespace(
        visible_case_refs=refs,
        primary_visible=True,
        source_rows_by_table={"mr": tuple(ref.as_dict() for ref in refs)},
        synced_tables=tuple(
            {"table_name": name, "sync_status": status}
            for name, status in zip(("mr", "daily_course_record"), statuses or ("synced", "synced"))
        ),
        total_rows_pulled=2,
        total_rows_upserted=2,
        bundle_refresh=refresh or _refresh_counts(len(refs)),
    )


def test_old_ready_is_fenced_before_primary_commit_and_stays_pending_on_detail_error(monkeypatch):
    service, events = _service(monkeypatch, sync_error=RuntimeError("detail unavailable"))

    with pytest.raises(RuntimeError, match="detail unavailable"):
        service.sync_pool_records(pool_id="pool-1")

    assert events[0] == ("invalidate", (CaseRef("H1", "P1", "V1"),))
    assert events[1][0] == "sync"
    assert events[1][1]["policy_version"] == "sample_pool_incremental_sync"
    assert events[1][1]["bundle_policy_version"].endswith("a" * 32)
    assert events[2:] == ["primary_committed", "pending"]


def test_running_success_but_final_domain_failure_never_publishes(monkeypatch):
    ref = CaseRef("H1", "P1", "V1")
    refresh = _refresh_counts()
    refresh["domains"]["terminal"]["failed"] = 1
    service, events = _service(monkeypatch, sync_result=_result((ref,), refresh=refresh))

    with pytest.raises(RuntimeError, match="Bundle 刷新不完整"):
        service.sync_pool_records(pool_id="pool-1")

    assert events[-1] == "pending"
    assert not any(isinstance(event, tuple) and event[0] == "publish" for event in events)
    assert "match" not in events


def test_success_publishes_exact_visible_identity_before_match(monkeypatch):
    refs = (CaseRef("H1", "P1", "V1"), CaseRef("H2", "P1", "V1"))
    service, events = _service(monkeypatch, refs=refs, sync_result=_result(refs))

    response = service.sync_pool_records(pool_id="pool-1")

    assert response["sync_ready"] is True
    assert events[0] == ("invalidate", refs)
    assert events[2][0] == "publish"
    assert set(events[2][1]) == set(refs)
    assert events[2][2]["published_policy_version"] == "sample_pool_incremental_sync"
    assert events[3] == "match"


def test_source_table_missing_leaves_fence_and_pending(monkeypatch):
    ref = CaseRef("H1", "P1", "V1")
    service, events = _service(
        monkeypatch,
        sync_result=_result((ref,), statuses=("synced", "source_table_unavailable")),
    )

    response = service.sync_pool_records(pool_id="pool-1")

    assert response["sync_ready"] is False
    assert response["sync_block_reason"] == "details_incomplete"
    assert "pending" in events
    assert not any(isinstance(event, tuple) and event[0] == "publish" for event in events)


def test_visible_identity_outside_requested_scope_is_not_published(monkeypatch):
    requested = CaseRef("H1", "P1", "V1")
    foreign = CaseRef("H2", "P1", "V1")
    service, events = _service(monkeypatch, refs=(requested,), sync_result=_result((foreign,)))

    with pytest.raises(RuntimeError, match="源端资料集不完整"):
        service.sync_pool_records(pool_id="pool-1")

    assert events[-1] == "pending"
    assert not any(isinstance(event, tuple) and event[0] == "publish" for event in events)
