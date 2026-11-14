from __future__ import annotations

import pytest

from app.services.case_identity import CaseRef
from app.services.qc_workspace.failed_rule_retry import (
    build_failed_rule_auto_retry_plan,
    build_failed_rule_retry_scope,
    merge_failed_rule_retry_results,
)


def _row(rule_id: str, *, status: str | None = None) -> dict:
    row = {
        "institute_id": "hospital-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "record_key": CaseRef("hospital-1", "patient-1", "visit-1").as_key(),
        "rule_id": rule_id,
    }
    if status:
        row["status"] = status
    return row


def test_scope_uses_only_failed_record_rule_pairs() -> None:
    job = {
        "status": "failed",
        "job_kind": "leaf",
        "summary": {"execution_status": "partial_failed"},
        "items": [_row("LX0609-06-01-04", status="compliant")],
        "failed_records": [
            _row("LX0609-06-01-05"),
            {
                "visit_id": "visit-2",
                "rule_id": "LX0609-04-01-03",
            },
        ],
        "filters": {
            "rule_ids": ["LX0609-06-01-04", "LX0609-06-01-05", "LX0609-04-01-03"],
            "record_refs": [
                {
                    "institute_id": "hospital-1",
                    "patient_id": "patient-1",
                    "visit_id": "visit-1",
                },
                {
                    "institute_id": "hospital-1",
                    "patient_id": "patient-2",
                    "visit_id": "visit-2",
                },
            ],
        },
    }

    result = build_failed_rule_retry_scope(job)

    assert result is not None
    scope, normalized_failures = result
    assert scope["rule_ids"] == ["LX0609-06-01-05", "LX0609-04-01-03"]
    assert scope["pending_count"] == 2
    assert scope["record_rule_map"] == {
        '["hospital-1","patient-1","visit-1"]': ["LX0609-06-01-05"],
        '["hospital-1","patient-2","visit-2"]': ["LX0609-04-01-03"],
    }
    assert normalized_failures[1]["patient_id"] == "patient-2"


def test_scope_rejects_ambiguous_legacy_visit_identity() -> None:
    job = {
        "status": "failed",
        "summary": {"execution_status": "partial_failed"},
        "items": [_row("LX0609-06-01-04", status="compliant")],
        "failed_records": [{"visit_id": "visit-1", "rule_id": "LX0609-06-01-05"}],
        "filters": {
            "record_refs": [
                {"institute_id": "hospital-1", "patient_id": "patient-1", "visit_id": "visit-1"},
                {"institute_id": "hospital-2", "patient_id": "patient-2", "visit_id": "visit-1"},
            ]
        },
    }

    with pytest.raises(ValueError, match="无法唯一定位"):
        build_failed_rule_retry_scope(job)


def test_scope_supports_all_model_results_failed() -> None:
    job = {
        "status": "failed",
        "summary": {"execution_status": "failed"},
        "items": [],
        "failed_records": [_row("LX0609-06-01-05")],
        "filters": {
            "record_refs": [
                {
                    "institute_id": "hospital-1",
                    "patient_id": "patient-1",
                    "visit_id": "visit-1",
                }
            ]
        },
    }

    result = build_failed_rule_retry_scope(job)

    assert result is not None
    scope, _ = result
    assert scope["pending_count"] == 1
    assert scope["rule_ids"] == ["LX0609-06-01-05"]


def test_merge_replaces_only_pending_failure_and_preserves_valid_result() -> None:
    valid = _row("LX0609-06-01-04", status="compliant")
    pending = _row("LX0609-06-01-05")
    recovered = _row("LX0609-06-01-05", status="non_compliant")

    items, failures = merge_failed_rule_retry_results(
        base_items=[valid],
        base_failures=[pending],
        retry_items=[recovered],
        retry_failures=[],
    )

    assert items == [valid, recovered]
    assert failures == []


def test_merge_rejects_out_of_scope_result() -> None:
    with pytest.raises(ValueError, match="范围外"):
        merge_failed_rule_retry_results(
            base_items=[_row("LX0609-06-01-04", status="compliant")],
            base_failures=[_row("LX0609-06-01-05")],
            retry_items=[_row("LX0609-04-01-03", status="compliant")],
            retry_failures=[],
        )


def test_merge_keeps_valid_results_when_retry_still_fails() -> None:
    valid = _row("LX0609-06-01-04", status="compliant")
    pending = {**_row("LX0609-06-01-05"), "reason_code": "model_invalid_output"}
    retry_failure = {**_row("LX0609-06-01-05"), "reason_code": "semantic_output_unknown"}

    items, failures = merge_failed_rule_retry_results(
        base_items=[valid],
        base_failures=[pending],
        retry_items=[],
        retry_failures=[retry_failure],
    )

    assert items == [valid]
    assert failures == [retry_failure]


def test_auto_retry_plan_retries_explicit_transient_failures_until_limit() -> None:
    failure = {**_row("LX0609-06-01-05"), "error_phase": "result_status", "reason_code": "model_timeout"}

    first = build_failed_rule_auto_retry_plan(
        summary={"execution_status": "partial_failed"},
        failures=[failure],
    )
    last = build_failed_rule_auto_retry_plan(
        summary={"execution_status": "partial_failed"},
        failures=[failure],
        retry_scope={"attempt": 3},
    )

    assert first == {
        "max_attempts": 3,
        "completed_attempts": 0,
        "remaining_failure_count": 1,
        "status": "planned",
        "should_retry": True,
        "next_attempt": 1,
        "delay_seconds": 0.0,
    }
    assert last["status"] == "exhausted"
    assert last["should_retry"] is False


def test_auto_retry_plan_does_not_repeat_non_model_failure() -> None:
    failure = {**_row("LX0609-06-01-05"), "error_phase": "record_load"}

    plan = build_failed_rule_auto_retry_plan(
        summary={"execution_status": "partial_failed"},
        failures=[failure],
    )

    assert plan["status"] == "not_retryable"
    assert plan["should_retry"] is False


@pytest.mark.parametrize(("rule", "reason"), [
    ("LX0609-05-01-03", "model_invalid_output"),
    ("LX0609-05-01-03", "model_timeout"),
    ("LX0609-03-01-04", "execution_program_error"),
    ("LX0609-03-01-04", "model_configuration_error"),
    ("LX0609-03-01-04", "model_invalid_output"),
])
def test_terminal_failure_is_not_whole_rule_automatically_retried(rule, reason):
    failure = {**_row(rule), "reason_code": reason, "error_phase": "result_status"}
    plan = build_failed_rule_auto_retry_plan(summary={"execution_status": "partial_failed"}, failures=[failure])
    assert plan["status"] == "not_retryable"
    assert plan["should_retry"] is False
    job = {"status": "failed", "summary": {"execution_status": "partial_failed"}, "failed_records": [failure]}
    assert build_failed_rule_retry_scope(job, automatic_only=True) is None
    assert build_failed_rule_retry_scope(job) is not None  # 人工明确发起仍可定向重跑。


def test_mixed_terminal_and_transient_failures_retry_only_transient_and_retain_both():
    terminal = {**_row("LX0609-05-01-03"), "reason_code": "model_invalid_output", "error_phase": "result_status"}
    transient = {**_row("LX0609-03-01-04"), "reason_code": "model_timeout", "error_phase": "result_status"}
    job = {"status": "failed", "summary": {"execution_status": "partial_failed"},
           "failed_records": [terminal, transient]}
    scope, failures = build_failed_rule_retry_scope(job, automatic_only=True)
    assert scope["rule_ids"] == ["LX0609-03-01-04"]
    assert scope["pending_count"] == 1
    assert len(failures) == 2
    plan = build_failed_rule_auto_retry_plan(summary=job["summary"], failures=failures)
    assert plan["should_retry"] is True
    recovered = {**transient, "status": "compliant"}
    items, remaining = merge_failed_rule_retry_results(base_items=[], base_failures=failures,
                                                       retry_items=[recovered], retry_failures=[])
    assert items == [recovered]
    assert remaining == [failures[0]]


@pytest.mark.asyncio
@pytest.mark.usefixtures("workspace_tables_without_database")
@pytest.mark.parametrize("recovered", [True, False], ids=["recovered", "still_failed"])
@pytest.mark.parametrize("independent", [False, True], ids=["legacy_same_id", "independent_attempt"])
async def test_formal_worker_parent_retry_canonical_and_route_agree(
    monkeypatch, recovered, independent
):
    """实际 Worker 分类、定向补跑、父统计、内存保存及路由共用同一合成结果。"""
    import copy
    import json
    from datetime import datetime
    from types import SimpleNamespace
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from starlette.requests import Request
    import app.services.custom_qc_workspace_service as workspace_module
    from app.routers import qc_sichuan
    from app.services import sichuan_workspace_batch_worker as worker
    from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
    from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore,
        envelope_item_from_rule_result,
    )
    from test_qc_sichuan_batch_throughput import (
        _WorkspaceStub,
        _ServiceStub,
        _configure_formal_customer_sample_batch_fixture,
        _freeze_formal_customer_batch_fixture_runtime,
    )
    from test_qc_sichuan_result_review import _admission_facts

    rule_id = "LX0609-01-01-01"
    rule = get_luxian_0609_rule(rule_id)
    table = workspace_module._record_result_envelopes_table().to_metadata(
        MetaData(), schema=None
    )
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    children = []
    calls = []
    observation_roots = []
    snapshots = []
    parent = {
        "id": "synthetic-parent",
        "job_kind": "parent",
        "status": "failed",
        "created_by": "tester",
        "total_records": 2,
        "draft_id": "sichuan-rule-library",
        "filters": {
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
            "rule_ids": [rule_id],
            "scoped_customer_rule_ids": [rule_id],
        },
    }

    class Workspace(_WorkspaceStub):
        def complete_batch_job(self, **kwargs):
            super().complete_batch_job(**kwargs)
            items = kwargs["items"]
            assert all(item["status"] != "technical_error" for item in items)
            with Session(engine) as db:
                filters = {
                    **self.job["filters"],
                    "record_refs": self.job["filters"]["record_refs"] if items else [],
                }
                store.replace_for_job(
                    db,
                    job_row={**self.job, "filters_json": json.dumps(filters)},
                    items=items,
                    now=datetime(2026, 11, 9),
                    projection_key="synthetic-retry-key",
                    projector=lambda item: envelope_item_from_rule_result(
                        item, hmac_key="synthetic-retry-key"
                    ),
                )
                db.commit()
            snapshots.append(copy.deepcopy(self.job))

        def update_batch_job_progress(self, **kwargs):
            items = kwargs.pop("items", None)
            failures = kwargs.pop("failed_records", None)
            super().update_batch_job_progress(**kwargs)
            if items is not None:
                self.items = list(items)
            if failures is not None:
                self.failed_records = list(failures)

    service = _ServiceStub()
    for index in (1, 2):
        child = Workspace()
        _configure_formal_customer_sample_batch_fixture(
            child, rule_ids=[rule_id], record_ids=[f"visit-{index:03d}"]
        )
        child.job.update(
            id=f"synthetic-child-{index}",
            parent_job_id=parent["id"],
            job_kind="child",
            total_records=1,
            created_by="tester",
            rule_code="LX0609",
            rule_name="合成入院时限核查",
        )
        settings = _freeze_formal_customer_batch_fixture_runtime(child, service)
        children.append(child)
    parent["child_job_ids"] = [child.job["id"] for child in children]
    parent["filters"]["record_refs"] = [
        child.job["filters"]["record_refs"][0] for child in children
    ]
    attempt = {"retry": False}

    async def evaluate(**kwargs):
        from app.services.llm_observability import current_llm_observation_context
        observation_roots.append(current_llm_observation_context().root_job_id)
        visit = kwargs["bundle"]["visit_id"]
        active = tuple(kwargs["rule_ids"])
        calls.append((visit, active))
        failed = visit == "visit-002" and (not attempt["retry"] or not recovered)
        item = {
            "rule_id": rule_id,
            "rule_version": rule["rule_version"],
            "schema_version": "lx0609-customer-result-v2",
            "status": "technical_error" if failed else "compliant",
            "is_compliant": None if failed else True,
            "reason_code": "model_invalid_output"
            if failed
            else "requirement_satisfied",
            "metadata": {
                "executor_type": "program",
                "technical_error_internal": failed,
            },
        }
        if not failed:
            item.update(
                customer_display_facts=_admission_facts(), findings="入院记录在24小时内完成。"
            )
        return {
            "evaluation_results": [item],
            "token_usage": {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            },
            "luxian_0609_usage_observation_complete": True,
            "luxian_0609_usage_unknown_executor_keys": [],
        }

    service.evaluate_running_final_bundle_input = evaluate
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "load_luxian_0609_rules", lambda: [rule])
    monkeypatch.setattr(
        worker,
        "get_product_activation_service",
        lambda: SimpleNamespace(enforce=lambda: None),
    )

    async def provider():
        return service

    aggregate_service = CustomQCWorkspaceService()

    def aggregate():
        class Rows:
            def mappings(self):
                return self

            def all(self):
                return [copy.deepcopy(child.job) for child in children]

        class ReadSession:
            def execute(self, _statement):
                return Rows()

        with monkeypatch.context() as scoped:
            scoped.setattr(
                workspace_module,
                "_row_to_batch_job",
                lambda row, include_items=True: row,
            )
            return aggregate_service._aggregate_parent_job(ReadSession(), parent)

    class RouteWorkspace:
        def get_batch_job(self, *, job_id, created_by):
            assert (job_id, created_by) == (parent["id"], "tester")
            return aggregate()

        def _load_batch_job_canonical_items(self, *, job, allow_partial=False):
            return store.load_root_job_items(
                job=job,
                session_factory=lambda: Session(engine),
                allow_partial=allow_partial,
            )

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", RouteWorkspace)

    async def route():
        return await qc_sichuan.get_workspace_batch_job(
            Request({"type": "http", "headers": []}),
            parent["id"],
            current_user={"id": "tester"},
        )

    try:
        for child in children:
            await worker.run_sichuan_workspace_batch_job(
                child.job["id"], workspace=child, qc_service_provider=provider
            )
        before = aggregate()
        assert before["status"] == "failed"
        assert (before["success_count"], before["failed_count"]) == (1, 1)
        assert (
            before["summary"]["completed_rule_count"],
            before["summary"]["failed_rule_count"],
        ) == (1, 1)
        before_route = (await route())["data"]
        assert len(before_route["items"]) == 1
        assert before_route["summary"]["failed_rule_count"] == 1
        assert before_route["failed_count"] == 1
        assert children[1].failed_records[0]["rule_id"] == rule_id
        assert before_route["summary"]["status_counts"] == {"compliant": 1}
        original_success = copy.deepcopy(children[0].job)
        failed_child = children[1]
        scope, failures = build_failed_rule_retry_scope(failed_child.job)
        assert scope["pending_count"] == 1 and scope["rule_ids"] == [rule_id]
        if independent:
            import hashlib
            import uuid
            from app.services import case_material_capture, validation_material_source
            from app.database import clinical_connection
            source_job = copy.deepcopy(failed_child.job)
            source_raw = json.dumps(source_job["filters"])
            source_hash = hashlib.sha256(source_raw.encode()).hexdigest()
            new_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"medqc:retry:v1:{source_job['id']}:{source_hash}"))
            retry_child = Workspace()
            retry_child.job = copy.deepcopy(source_job)
            retry_child.job.update(id=new_id, parent_job_id=None,
                                   status="queued", items=[], failed_records=[], summary={})
            retry_child.job["filters"]["failed_rule_retry"] = scope
            retry_child.job["filters"]["retry_lineage"] = {
                "schema_version": "qc-retry-lineage-v1", "source_filters_sha256": source_hash,
                "source_attempt": source_job["filters"].get("_lx0609_attempt_id") or "",
                "source_job_id": source_job["id"], "root_job_id": source_job["id"],
                "material_job_id": parent["id"], "attempt": 1, "trigger": "manual",
            }
            retry_child.job["_claim_filters_json"] = json.dumps(retry_child.job["filters"])
            related_jobs = {source_job["id"]: {**source_job, "_claim_filters_json": source_raw},
                            parent["id"]: parent, new_id: retry_child.job}
            monkeypatch.setattr(retry_child, "get_batch_job_for_processing", lambda *, job_id: related_jobs.get(job_id))
            material_calls = []
            def frozen_material(job_id, identity, *, retry, cancellation_check):
                material_calls.append((job_id, identity, retry))
                return None
            monkeypatch.setattr(case_material_capture, "obtain", frozen_material)
            monkeypatch.setattr(clinical_connection, "configured", lambda: True)
            monkeypatch.setattr(validation_material_source, "is_material_copy", lambda *_: False)
            attempt["retry"] = True
            await worker.run_sichuan_workspace_batch_job(
                retry_child.job["id"], workspace=retry_child, qc_service_provider=provider)
            assert failed_child.job == source_job
            assert children[0].job == original_success
            assert aggregate() == before
            assert (await route())["data"]["items"] == before_route["items"]
            assert len(retry_child.items) == int(recovered)
            assert retry_child.summary["completed_rule_count"] == int(recovered)
            assert retry_child.summary["failed_rule_count"] == int(not recovered)
            assert retry_child.summary["total_records"] == 1
            assert retry_child.summary["retry_recovered_count"] == int(recovered)
            assert material_calls == [(parent["id"], tuple(source_job["filters"]["record_refs"][0][key]
                for key in ("institute_id", "patient_id", "visit_id")), True)]
            assert calls == [("visit-001", (rule_id,)), ("visit-002", (rule_id,)), ("visit-002", (rule_id,))]
            assert observation_roots == [parent["id"], parent["id"], retry_child.job["id"]]
            return
        failed_child.job["filters"]["failed_rule_retry"] = scope
        failed_child.job.update(status="queued", failed_records=failures)
        attempt["retry"] = True
        await worker.run_sichuan_workspace_batch_job(
            failed_child.job["id"], workspace=failed_child, qc_service_provider=provider
        )
        assert children[0].job == original_success
        assert calls == [
            ("visit-001", (rule_id,)),
            ("visit-002", (rule_id,)),
            ("visit-002", (rule_id,)),
        ]
        after = aggregate()
        expected = 2 if recovered else 1
        assert after["status"] == ("completed" if recovered else "failed")
        assert (after["success_count"], after["failed_count"]) == (
            expected,
            2 - expected,
        )
        assert after["summary"]["completed_rule_count"] == expected
        assert after["summary"]["failed_rule_count"] == 2 - expected
        assert failed_child.summary["retry_recovered_count"] == int(recovered)
        assert failed_child.summary["retry_remaining_count"] == int(not recovered)
        projected = (await route())["data"]
        assert projected["summary"]["status_counts"] == {"compliant": expected}
        assert len(projected["items"]) == expected
        assert projected["summary"]["failed_rule_count"] == 2 - expected
        assert projected["failed_count"] == 2 - expected
        assert all(item["status"] == "compliant" for item in projected["items"])
        assert projected["items"][0] == before_route["items"][0]
        assert len(snapshots) == 3
    finally:
        engine.dispose()
