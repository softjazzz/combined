from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from app.services import case_material_snapshot as material


@pytest.mark.parametrize(
    "value",
    [
        "",
        "bad",
        "2026-01-01T12:00:00",
        "2020-01-01T00:00:00+00:00",
        "2099-01-01T00:00:00+00:00",
    ],
)
def test_window_invalid(value, monkeypatch):
    from app.services.material_admission import require_publication_window

    monkeypatch.setenv("QC_CDM_CAPTURE_WINDOW_UNTIL", value)
    with pytest.raises(
        material.MaterialSnapshotError, match="cdm_publication_window_unconfirmed"
    ):
        require_publication_window()


def test_window_current(monkeypatch):
    from app.services.material_admission import require_publication_window

    monkeypatch.setenv(
        "QC_CDM_CAPTURE_WINDOW_UNTIL",
        (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    require_publication_window()


def test_create_rejects_before_insert(monkeypatch):
    from app.services import custom_qc_workspace_service as ws, clinical_sources

    monkeypatch.delenv("QC_CDM_CAPTURE_WINDOW_UNTIL", raising=False)
    monkeypatch.setattr(
        ws,
        "_session",
        lambda: SimpleNamespace(
            close=lambda: None, execute=lambda *a, **k: pytest.fail("task inserted")
        ),
    )
    monkeypatch.setattr(
        clinical_sources,
        "freeze",
        lambda f: f.update(clinical_source={"id": "independent_cdm"}),
    )
    service = object.__new__(ws.CustomQCWorkspaceService)
    with pytest.raises(
        material.MaterialSnapshotError, match="cdm_publication_window_unconfirmed"
    ):
        service.create_batch_job(
            draft={},
            created_by="synthetic",
            scope="final",
            filters={},
            record_ids=["V"],
            total_records=1,
        )


def test_safe_failure_dto_no_raw_text():
    from app.services.custom_qc_workspace_service import project_customer_safe_batch_job

    job = {
        "id": "synthetic",
        "status": "failed",
        "summary": {
            "material_failure": {
                "code": "cdm_publication_window_unconfirmed",
                "message": "SECRET",
            },
            "progress": {"rule_index": 0},
        },
        "items": [],
    }
    dto = project_customer_safe_batch_job(
        job, hmac_key="synthetic", _validate_luxian=False
    )
    assert (
        dto["summary"]["material_failure"]["code"]
        == "cdm_publication_window_unconfirmed"
    )
    assert "SECRET" not in str(dto)


@pytest.mark.asyncio
async def test_worker_material_failure_is_one_case_not_rules(monkeypatch, tmp_path):
    from app.services import (
        sichuan_workspace_batch_worker as worker,
        case_material_capture,
    )
    from app.services.bundles import assembly
    from test_qc_sichuan_batch_throughput import _WorkspaceStub, _ServiceStub

    workspace, service = _WorkspaceStub(), _ServiceStub()
    workspace.job["record_ids"] = ["visit-001"]
    update = workspace.update_batch_job_progress

    def persist_progress(*, items=None, failed_records=None, **kwargs):
        if items is not None:
            workspace.items = items
        if failed_records is not None:
            workspace.failed_records = failed_records
        return update(**kwargs)

    workspace.update_batch_job_progress = persist_progress
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    monkeypatch.setattr(
        assembly, "engine", SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    )

    def reject(*a, **k):
        raise material.MaterialSnapshotError("cdm_publication_window_unconfirmed")

    monkeypatch.setattr(case_material_capture, "obtain", reject)
    monkeypatch.setattr(
        worker,
        "get_product_activation_service",
        lambda: SimpleNamespace(enforce=lambda: None),
    )

    async def provider():
        return service

    await worker.run_sichuan_workspace_batch_job(
        workspace.job["id"], workspace=workspace, qc_service_provider=provider
    )
    assert service.evaluate_calls == 0
    assert workspace.job["status"] == "failed"
    assert (
        workspace.summary["material_failure"]["code"]
        == "cdm_publication_window_unconfirmed"
    )
    assert workspace.job["progress"]["rule_index"] == 0
    assert workspace.summary["failed_rule_count"] == 0
    assert len(workspace.failed_records) == 1
    assert not workspace.failed_records[0].get("rule_id")


@pytest.mark.asyncio
@pytest.mark.parametrize("retry", [False, True])
async def test_formal_material_failure_preserves_old_results(
    monkeypatch, tmp_path, retry
):
    from app.services import (
        sichuan_workspace_batch_worker as worker,
        case_material_capture,
    )
    from app.services.bundles import assembly
    from app.services.case_identity import CaseRef
    from app.core.settings import Settings
    from app.services.luxian_0609.rule_decision_settings import (
        LX0609_TASK_SETTINGS_FILTER_KEY,
        LX0609_TASK_RUNTIME_FILTER_KEY,
        capture_luxian_0609_task_settings,
        capture_luxian_0609_task_runtime,
        resolve_mainline_rule_decision_settings,
    )
    from test_qc_sichuan_batch_throughput import (
        _WorkspaceStub,
        _ServiceStub,
        _configure_formal_customer_sample_batch_fixture,
        _luxian_native_settings,
    )

    workspace, service = _WorkspaceStub(), _ServiceStub()
    rule = "LX0609-06-01-04"
    _configure_formal_customer_sample_batch_fixture(
        workspace, rule_ids=[rule], record_ids=["visit-001"]
    )
    ref = workspace.job["filters"]["record_refs"][0]
    base_failure = {
        **ref,
        "record_id": ref["visit_id"],
        "record_key": CaseRef.from_mapping(ref).as_key(),
        "rule_id": rule,
        "error_phase": "result_status",
    }
    base_item = {**base_failure, "rule_id": "LX0609-06-01-05", "status": "compliant"}
    if retry:
        workspace.job.update(
            summary={"execution_status": "partial_failed", "total_records": 1},
            items=[base_item],
            failed_records=[base_failure],
        )
        workspace.job["filters"]["failed_rule_retry"] = {
            "schema_version": "failed-rule-retry-v1",
            "attempt": 1,
            "record_refs": [ref],
            "rule_ids": [rule],
            "record_rule_map": {CaseRef.from_mapping(ref).as_key(): [rule]},
            "pending_count": 1,
        }
    settings = Settings(
        _env_file=None,
        JWT_SECRET="synthetic-admission",
        **vars(_luxian_native_settings()),
    )
    workspace.job["filters"][LX0609_TASK_SETTINGS_FILTER_KEY] = (
        capture_luxian_0609_task_settings(
            resolve_mainline_rule_decision_settings(settings)
        )
    )
    workspace.job["filters"][LX0609_TASK_RUNTIME_FILTER_KEY] = (
        capture_luxian_0609_task_runtime(service)
    )
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(
        worker,
        "get_product_activation_service",
        lambda: SimpleNamespace(enforce=lambda: None),
    )
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    monkeypatch.setattr(
        assembly, "engine", SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    )

    def reject(*a, **k):
        raise material.MaterialSnapshotError(
            "original_task_material_not_retained"
            if retry
            else "cdm_publication_window_unconfirmed"
        )

    monkeypatch.setattr(case_material_capture, "obtain", reject)

    async def provider():
        return service

    await worker.run_sichuan_workspace_batch_job(
        workspace.job["id"], workspace=workspace, qc_service_provider=provider
    )
    assert workspace.job["status"] == "failed"
    assert workspace.summary["material_failure"]["code"] == (
        "original_task_material_not_retained"
        if retry
        else "cdm_publication_window_unconfirmed"
    )
    assert service.evaluate_calls == 0
    assert workspace.job["progress"]["processed_rule_count"] == 0
    if retry:
        assert workspace.items == [base_item]
        assert workspace.failed_records == [base_failure]


@pytest.mark.asyncio
async def test_custom_submission_returns_409_without_dispatch():
    from fastapi import BackgroundTasks, HTTPException
    from app.routers import custom_qc
    from test_custom_qc_workspace_batch_record_refs import (
        _CreateWorkspace,
        _request,
        RECORD_REFS,
    )

    workspace = _CreateWorkspace()

    def reject(**kwargs):
        raise material.MaterialSnapshotError("cdm_publication_window_unconfirmed")

    workspace.create_batch_job = reject
    tasks = BackgroundTasks()
    with pytest.raises(HTTPException) as exc:
        await custom_qc.create_workspace_batch_job(
            request=_request(),
            payload=custom_qc.WorkspaceBatchJobCreateRequest(
                draft_id="draft-1", record_refs=RECORD_REFS
            ),
            background_tasks=tasks,
            current_user={"id": "qc-user"},
            workspace=workspace,
        )
    assert exc.value.status_code == 409
    assert "cdm_publication_window_unconfirmed" in exc.value.detail
    assert not tasks.tasks


def test_material_failure_real_sqlite_roundtrip_preserves_history(monkeypatch):
    import json
    import sqlalchemy as sa
    from sqlalchemy.orm import sessionmaker
    from app.services import custom_qc_workspace_service as ws
    from app.services.material_admission import safe_material_failure

    metadata = sa.MetaData()
    strings = "id status summary_json filters_json items_json failed_records_json error_message parent_job_id created_by record_ids_json".split()
    numbers = "total_records success_count failed_count issue_records compliant_records total_tokens total_processing_time".split()
    table = sa.Table(
        "jobs",
        metadata,
        *(sa.Column(k, sa.Text) for k in strings),
        *(sa.Column(k, sa.Integer) for k in numbers),
        *(sa.Column(k, sa.DateTime) for k in ["updated_at", "finished_at"]),
    )
    engine = sa.create_engine("sqlite://")
    metadata.create_all(engine)
    monkeypatch.setattr(ws, "_session", sessionmaker(bind=engine))
    service = object.__new__(ws.CustomQCWorkspaceService)
    service._batch_job_table = table
    monkeypatch.setattr(service, "refresh_parent_batch_job", lambda **k: None)
    with engine.begin() as conn:
        conn.execute(
            table.insert(),
            [
                {
                    "id": "new",
                    "status": "running",
                    "filters_json": "{}",
                    "summary_json": "{}",
                },
                {
                    "id": "history",
                    "status": "completed",
                    "filters_json": "{}",
                    "summary_json": '{"original":true}',
                },
            ],
        )
    failure = safe_material_failure("cdm_publication_window_unconfirmed")
    service.update_batch_job_progress(
        job_id="new",
        step_key="failed",
        rule_index=0,
        rule_count=76,
        processed_records=1,
        total_records=1,
        summary_patch={
            "material_failure": failure,
            "processed_rule_count": 0,
            "failed_rule_count": 0,
            "material_failed_record_count": 1,
            "failed_count": 1,
        },
        items=[],
        failed_records=[{"error_phase": "material_capture", "error": failure["code"]}],
    )
    service.fail_batch_job(job_id="new", error_message=failure["message"])
    with engine.connect() as conn:
        row = dict(
            conn.execute(sa.select(table).where(table.c.id == "new")).mappings().one()
        )
        assert (
            conn.execute(
                sa.select(table.c.summary_json).where(table.c.id == "history")
            ).scalar_one()
            == '{"original":true}'
        )
    saved = ws._row_to_batch_job(row)
    dto = ws.project_customer_safe_batch_job(
        saved, hmac_key="synthetic", _validate_luxian=False
    )
    assert dto["status"] == "failed"
    assert dto["summary"]["processed_rule_count"] == 0
    assert dto["summary"]["failed_rule_count"] == 0
    assert dto["summary"]["material_failure"] == failure
    assert len(json.loads(row["failed_records_json"])) == 1
    engine.dispose()
