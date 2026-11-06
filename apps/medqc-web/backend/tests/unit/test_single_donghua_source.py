"""单源普通入口、任务冻结和历史/登记材料例外；由offline runner先装护栏。"""

import asyncio
import pytest
from fastapi import HTTPException
from app.database import clinical_connection as clinical
from app.services import clinical_sources as sources
from app.services.data_pipeline_settings import PipelineError
from tests.unit.test_clinical_sources import (
    profile as original_profile,
    request,
    settings_store as original_store,
)

from tests.unit.test_latest_full_record_result import (
    saved_jobs as original_jobs,
    REF,
    RULES,
)

profile = original_profile
settings_store = original_store


@pytest.fixture(autouse=True)
def fixed_mode(monkeypatch, profile):
    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "fixed_donghua_cdm")
    monkeypatch.setattr(sources, "configuration", lambda: profile)


@pytest.mark.parametrize(
    "path",
    [
        "/api/medical-records/workstation",
        "/api/medical-records/stats",
        "/api/medical-records/departments",
        "/api/medical-records/frontpage/V",
        "/api/v1/emr/V/documents",
        "/api/medical-records/record-content/V",
    ],
)
def test_ordinary_get_without_source_is_fixed_cdm(path):
    req = request(path)
    sources.prepare_request(req)
    assert req.state.clinical_source["id"] == "independent_cdm"
    with sources.request_selection(req):
        assert clinical.configured() and clinical.source_binding().startswith(
            "cdm-read-v1:"
        )
    assert clinical.current_selection() is None


@pytest.mark.parametrize("kind", ["query", "header"])
def test_ordinary_legacy_request_rejected(kind):
    req = request(
        "/api/medical-records/workstation",
        "source_id=legacy_pg" if kind == "query" else "",
        "legacy_pg" if kind == "header" else None,
    )
    with pytest.raises(HTTPException) as caught:
        sources.prepare_request(req)
    assert caught.value.status_code == 409


def test_new_job_without_request_context_freezes_cdm():
    filters = {
        "record_refs": [dict(institute_id="0001", patient_id="0002", visit_id="0003")]
    }
    sources.freeze(filters)
    assert sources.saved_snapshot(filters)["id"] == "independent_cdm"
    assert filters["record_refs"][0]["patient_id"] == "0002"


def test_ordinary_pool_does_not_force_legacy():
    filters = {
        "sample_pool_id": "ordinary-pool",
        "record_refs": [dict(institute_id="I", patient_id="P", visit_id="V")],
    }
    sources.freeze(filters)
    assert sources.saved_snapshot(filters)["id"] == "independent_cdm"


def test_missing_cdm_credentials_never_freezes_legacy(monkeypatch):
    monkeypatch.delenv("CDM_PGPASSFILE")
    with pytest.raises(PipelineError, match="credentials_unavailable"):
        sources.freeze(
            {"record_refs": [dict(institute_id="I", patient_id="P", visit_id="V")]}
        )


def test_pdf_prefix_alone_cannot_choose_business(monkeypatch):
    from app.services import validation_material_source as material

    def missing(**kwargs):
        raise ValueError("validation_material_identity_not_registered")

    monkeypatch.setattr(material, "material_source_schema", missing)
    with pytest.raises((ValueError, PipelineError), match="material"):
        sources.freeze(
            {
                "sample_pool_id": "forged",
                "record_refs": [
                    dict(institute_id="I", patient_id="pdfp_fake", visit_id="pdfv_fake")
                ],
            }
        )


def test_verified_pdf_material_keeps_legacy(monkeypatch):
    from app.services import validation_material_source as material

    calls = []

    def registered(**kwargs):
        calls.append(kwargs)
        return "pdfmat_111111111111"

    monkeypatch.setattr(material, "material_source_schema", registered)
    filters = {
        "record_refs": [dict(institute_id="I", patient_id="pdfp_P", visit_id="pdfv_V")]
    }
    sources.freeze(filters)
    assert calls and sources.saved_snapshot(filters)["id"] == "legacy_pg"


def test_historical_missing_source_is_not_reinterpreted():
    assert sources.saved_snapshot({}) == sources.legacy_snapshot()


def test_old_ordinary_job_is_not_automatically_resumed():
    calls = []

    class Workspace:
        def get_batch_job_for_processing(self, **kwargs):
            return {
                "status": "queued",
                "filters": {
                    "record_refs": [
                        dict(institute_id="I", patient_id="P", visit_id="V")
                    ]
                },
            }

    @sources.bound_job
    async def execute(job_id, *, workspace):
        calls.append(job_id)

    assert asyncio.run(execute("historical", workspace=Workspace())) is None
    assert not calls and clinical.current_selection() is None


@pytest.mark.parametrize("enabled", [False, True])
def test_no_context_engine_never_uses_business(profile, monkeypatch, enabled):
    profile.cdm.enabled = enabled
    if enabled:
        assert clinical.get_engine().url.database == profile.cdm.database
        assert (
            clinical.source_binding()
            == sources.snapshot(profile, "independent_cdm")["binding"]
        )
    else:
        with pytest.raises(PipelineError, match="disabled"):
            clinical.get_engine()


def test_fixed_is_actual_default_and_invalid_mode_rejected(monkeypatch):
    from app.services.clinical_source_policy import fixed_cdm

    monkeypatch.delenv("MEDQC_CLINICAL_SOURCE_MODE")
    assert fixed_cdm()
    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "typo")
    with pytest.raises(ValueError, match="mode_invalid"):
        fixed_cdm()


def test_legacy_sync_rejected_before_any_work(monkeypatch):
    from app.services import etl_sync
    from app.routers.sync import require_legacy_sync_available

    calls = []
    monkeypatch.setattr(etl_sync, "engine", object())
    monkeypatch.setattr(
        etl_sync, "_upsert_sync_job_state", lambda *a, **k: calls.append(1)
    )
    with pytest.raises(ValueError, match="legacy_sync_disabled"):
        etl_sync.run_sync()
    with pytest.raises(ValueError, match="legacy_sync_disabled"):
        etl_sync.get_remote_db_url()
    with pytest.raises(HTTPException) as caught:
        require_legacy_sync_available()
    assert caught.value.status_code == 409 and calls == []


def test_history_without_material_snapshot_cannot_read_current_cdm(monkeypatch):
    from app.services import case_material_snapshot as material

    calls = []

    def saved(req, job_id):
        req.state.material_root_job_id = job_id
        return sources.legacy_snapshot()

    monkeypatch.setattr(sources, "source_for_saved_job", saved)
    monkeypatch.setattr(material, "load", lambda *a, **k: None)
    monkeypatch.setattr(clinical, "get_engine", lambda: calls.append(1))
    req = request(
        "/api/v1/emr/V/documents", "job_id=old&institute_id=I&patient_id=P&visit_id=V"
    )
    sources.prepare_request(req)

    async def bind():
        async for _ in sources.bind_request(req):
            pytest.fail("missing historical material must not execute current view")

    with pytest.raises(HTTPException) as caught:
        asyncio.run(bind())
    assert caught.value.status_code == 409
    assert caught.value.detail == "historical_material_snapshot_not_retained"
    assert calls == [] and clinical.current_selection() is None


saved_jobs = original_jobs


@pytest.mark.parametrize("kind", ["complete", "partial", "empty"])
def test_historical_results_kept_without_recomputing(saved_jobs, kind, monkeypatch):
    import json
    from app.services import custom_qc_workspace_service as workspace
    from sqlalchemy.orm import Session

    service, add, engine, jobs = saved_jobs
    before = add("history-" + kind, 10, RULES, failed=kind != "complete")
    if kind == "empty":
        with Session(engine) as session:
            session.execute(
                jobs.update().where(jobs.c.id == before["id"]).values(items_json="[]")
            )
            session.commit()

    def no_model(*args, **kwargs):
        pytest.fail("historical result must not execute QC")

    monkeypatch.setattr(workspace, "_now_utc", no_model)
    with engine.connect() as c:
        original = dict(c.execute(jobs.select()).mappings().one())
    with clinical.selected(sources.legacy_snapshot()):
        result = service.build_latest_single_record_result_dto(**REF)
    assert result["job_id"] == before["id"]
    if kind == "complete":
        assert result["result_rule_count"] == 2 and result["is_complete"] is True
    elif kind == "partial":
        assert (
            result["result_rule_count"] == 1
            and result["execution_status"] == "partial_failed"
        )
    else:
        assert result["result_rule_count"] == 0
    with engine.connect() as c:
        assert dict(c.execute(jobs.select()).mappings().one()) == original
    assert "clinical_source" not in json.loads(original["filters_json"])


def test_direct_case_sync_cannot_bypass_legacy_guard():
    from app.services.case_set_sync_service import CaseSetSyncService

    calls = []
    service = CaseSetSyncService(db_config_loader=lambda: calls.append(1))
    with pytest.raises(ValueError, match="legacy_sync_disabled"):
        service.sync_case_set(
            case_refs=[],
            table_names=[],
            policy_version="synthetic",
            sync_scene="running",
        )
    assert calls == []


def test_registered_custom_history_still_checks_job_authorization(monkeypatch):
    calls = []
    monkeypatch.setattr(sources, "_registered_local_case", lambda ref: True)

    def forbidden(req, job_id):
        calls.append(job_id)
        raise PipelineError("clinical_source_job_forbidden", 403)

    monkeypatch.setattr(sources, "source_for_saved_job", forbidden)
    req = request(
        "/api/v1/emr/V/documents",
        "job_id=old&institute_id=CUSTOMER_TEST&patient_id=P&visit_id=V",
    )
    with pytest.raises(HTTPException) as caught:
        sources.prepare_request(req)
    assert caught.value.status_code == 403 and calls == ["old"]


def test_fixed_connection_can_be_staged_disabled_without_fallback(
    settings_store, monkeypatch
):
    monkeypatch.delenv("CDM_PGPASSFILE", raising=False)
    saved = sources.save(settings_store, sources.SourceSettings(), "synthetic-admin")
    assert (
        saved.default_source == "independent_cdm"
        and not saved.legacy_enabled
        and not saved.cdm.enabled
    )
    with pytest.raises(PipelineError, match="disabled"):
        sources.snapshot(saved, saved.default_source)
