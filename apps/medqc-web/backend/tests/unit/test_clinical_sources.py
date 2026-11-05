"""严格离线；配置、请求、任务和保存读取的来源边界。"""
import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.database import clinical_connection as clinical
from app.routers import clinical_sources as api
from app.services import clinical_sources as sources
from app.services.data_pipeline_settings import PipelineError
from tests.unit.test_latest_full_record_result import RULES, REF, saved_jobs  # noqa: F401


@pytest.fixture
def settings_store():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("ATTACH DATABASE ':memory:' AS qc"))
        connection.execute(text("CREATE TABLE qc.sync_config_registry(namespace TEXT,config_key TEXT,payload_json TEXT,updated_by TEXT,source TEXT,change_reason TEXT,updated_at TEXT,PRIMARY KEY(namespace,config_key))"))
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def profile(monkeypatch, tmp_path):
    passfile = tmp_path / "synthetic.pgpass"
    passfile.write_text("127.0.0.1:62996:synthetic_cdm:reader:synthetic-only", encoding="utf-8")
    passfile.chmod(0o600)
    monkeypatch.setenv("CDM_PGPASSFILE", str(passfile))
    value = sources.SourceSettings()
    value.cdm.enabled = True
    value.cdm.port = 62996
    value.cdm.database = "synthetic_cdm"
    value.cdm.username = "reader"
    return value


def test_default_and_cas_save_never_connect(settings_store, profile, monkeypatch):
    monkeypatch.setattr(clinical, "create_engine", lambda *a, **kw: object())
    initial, raw = sources.load(settings_store)
    assert raw is None and initial.default_source == "legacy_pg" and not initial.cdm.enabled
    profile.default_source = "independent_cdm"
    saved = sources.save(settings_store, profile, "admin")
    assert saved.version == 1
    assert sources.load(settings_store)[0] == saved
    assert "synthetic-only" not in saved.model_dump_json()
    with pytest.raises(PipelineError, match="configuration_changed"):
        sources.save(settings_store, profile, "admin")


@pytest.mark.parametrize("change,reason", [
    ({"legacy_enabled": False}, "at_least_one"),
    ({"default_source": "independent_cdm"}, "disabled"),
])
def test_invalid_or_disabled_default_not_saved(settings_store, change, reason):
    with pytest.raises(PipelineError, match=reason):
        sources.save(settings_store, sources.SourceSettings(**change), "admin")
    assert sources.load(settings_store)[1] is None


def test_credentials_missing_is_fail_closed(profile, monkeypatch):
    monkeypatch.delenv("CDM_PGPASSFILE")
    with pytest.raises(PipelineError, match="credentials_unavailable"):
        sources.snapshot(profile, "independent_cdm")


def request(path, query="", header=None):
    return Request({"type": "http", "method": "GET", "path": path, "query_string": query.encode(),
        "headers": [(b"x-clinical-source", header.encode())] if header else []})


def test_request_default_explicit_and_pdf_business_route(profile, monkeypatch):
    profile.default_source = "independent_cdm"
    monkeypatch.setattr(sources, "configuration", lambda: profile)
    for req, expected in [(request("/api/medical-records/workstation"), "independent_cdm"),
        (request("/api/v1/emr/V/documents", "source_id=legacy_pg"), "legacy_pg"),
        (request("/api/v1/qc/sample-pools", header="independent_cdm"), "legacy_pg")]:
        sources.prepare_request(req)
        with sources.request_selection(req):
            assert clinical.current_selection()["id"] == expected
        assert clinical.current_selection() is None
    with pytest.raises(HTTPException) as caught:
        sources.prepare_request(request("/api/medical-records/workstation", "source_id=legacy_pg", "independent_cdm"))
    assert caught.value.status_code == 422


def test_legacy_overrides_global_cdm_without_mutating_environment(monkeypatch):
    monkeypatch.setenv("CDM_DATABASE_URL", "postgresql://reader@not-accessed/cdm")
    assert clinical.configured()
    with clinical.selected(sources.legacy_snapshot()):
        assert not clinical.configured() and clinical.get_engine() is None and clinical.source_binding() == ""
    assert clinical.configured()


def test_parallel_request_contexts_are_isolated(profile):
    selected = sources.snapshot(profile, "independent_cdm")
    async def run(selection):
        with clinical.selected(selection):
            await asyncio.sleep(0)
            return clinical.source_binding()
    async def main():
        return await asyncio.gather(run(selected), run(sources.legacy_snapshot()))
    assert asyncio.run(main()) == [selected["binding"], ""]
    assert clinical.current_selection() is None


def test_task_freezes_original_source_and_old_tasks_stay_legacy(profile):
    selected = sources.snapshot(profile, "independent_cdm")
    filters = {"record_refs": [REF]}
    with clinical.selected(selected):
        sources.freeze(filters)
        assert sources.saved_snapshot(filters) == selected
        assert not sources.job_matches({})
        assert sources.job_matches(filters)
        with pytest.raises(ValueError, match="override_forbidden"):
            sources.freeze({"clinical_source": sources.legacy_snapshot()})
        pdf = {"sample_pool_id": "1026"}
        sources.freeze(pdf)
        assert sources.saved_snapshot(pdf)["id"] == "legacy_pg"
    with clinical.selected(sources.legacy_snapshot()):
        assert not sources.job_matches(filters)
        assert sources.job_matches({})
        assert sources.job_matches(pdf, "pdfp_P", "pdfv_V")
    assert "synthetic-only" not in json.dumps(filters)


def test_snapshot_does_not_accept_mismatched_url_or_password(profile):
    value = sources.snapshot(profile, "independent_cdm")
    for changed in ({**value, "url": value["url"].replace("synthetic_cdm", "other")},
                    {**value, "binding": ""}):
        with pytest.raises(ValueError):
            sources.saved_snapshot({"clinical_source": changed})


def test_worker_reloads_persisted_source_despite_new_default(profile):
    value = sources.snapshot(profile, "independent_cdm")
    class Workspace:
        def get_batch_job_for_processing(self, **kwargs):
            return {"filters": {"clinical_source": value}}
    @sources.bound_job
    async def execute(job_id, *, workspace):
        await asyncio.sleep(0)
        return clinical.current_selection()
    with clinical.selected(sources.legacy_snapshot()):
        assert asyncio.run(execute("job", workspace=Workspace())) == value
        assert clinical.source_binding() == ""


def test_frozen_fact_directory_partitioned_without_changing_legacy(profile):
    from app.services.llm_experiment import experiment_store_dir
    base = Path("synthetic-freeze")
    with clinical.selected(sources.legacy_snapshot()):
        assert experiment_store_dir(base) == base
    with clinical.selected(sources.snapshot(profile, "independent_cdm")):
        assert experiment_store_dir(base) != base
        assert "clinical-sources" in str(experiment_store_dir(base))


def test_canonical_latest_same_keys_selects_only_matching_source(saved_jobs, profile):  # noqa: F811
    service, add, engine, jobs = saved_jobs
    add("old-legacy", 10, RULES)
    row = add("new-cdm", 12, RULES)
    value = sources.snapshot(profile, "independent_cdm")
    filters = json.loads(row["filters_json"])
    filters["clinical_source"] = value
    with engine.begin() as connection:
        connection.execute(jobs.update().where(jobs.c.id == "new-cdm").values(filters_json=json.dumps(filters)))
    for selected, expected in [(sources.legacy_snapshot(), "old-legacy"), (value, "new-cdm")]:
        with clinical.selected(selected):
            result = service.build_latest_single_record_result_dto(**REF)
            assert result["job_id"] == expected
            assert result["state"] == "ready" and result["result_rule_count"] == 2
            assert len(result["items"]) == 2


def test_options_hide_connection_and_admin_gate(profile, monkeypatch):
    monkeypatch.setattr(sources, "configuration", lambda: profile)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_current_user] = lambda: {"id": "doctor"}
    # 使用真实授权函数的失败关闭路径，不信任JWT中的admin声明。
    from app.routers import data_pipelines
    monkeypatch.setattr(data_pipelines, "SessionLocal", None)
    with TestClient(app) as client:
        response = client.get("/api/v1/clinical-sources/options")
        assert response.status_code == 200
        assert "username" not in response.text and "62996" not in response.text
        assert client.get("/api/v1/clinical-sources").status_code == 503
        assert client.put("/api/v1/clinical-sources", json=profile.model_dump()).status_code == 503


def test_actual_fastapi_dependency_chain_binds_source_and_resets(profile, monkeypatch):
    from fastapi import Depends
    from app.core import access_control
    profile.default_source = "independent_cdm"
    calls = []
    monkeypatch.setattr(sources, "configuration", lambda: calls.append(1) or profile)
    monkeypatch.setattr(access_control, "resolve_current_user_from_token", lambda _: {"id": "admin", "roles": ["admin"]})
    app = FastAPI(dependencies=[Depends(access_control.enforce_default_auth), Depends(sources.bind_request)])
    @app.get("/api/medical-records/workstation")
    def current():
        return {"source": clinical.current_selection()["id"], "configured": clinical.configured()}
    @app.get("/api/v1/health")
    def health():
        return {"configured": clinical.configured()}
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json() == {"configured": False}
        assert calls == []
        headers = {"Authorization": "Bearer synthetic"}
        assert client.get("/api/medical-records/workstation", headers=headers).json() == {"source": "independent_cdm", "configured": True}
        assert client.get("/api/medical-records/workstation?source_id=legacy_pg", headers=headers).json() == {"source": "legacy_pg", "configured": False}
        assert client.get("/api/medical-records/workstation").status_code == 401
    assert clinical.current_selection() is None and len(calls) == 2


def test_bad_saved_snapshot_cas_fails_queued_job_without_execution():
    calls = []
    class Workspace:
        def get_batch_job_for_processing(self, **kwargs):
            return {"status": "queued", "filters": {"clinical_source": {"id": "unknown"}}, "_claim_filters_json": "fixed-original"}
        def fail_batch_job(self, **kwargs):
            calls.append(kwargs)
    @sources.bound_job
    async def execute(job_id, *, workspace):
        pytest.fail("invalid source must not execute against legacy database")
    asyncio.run(execute("bad-job", workspace=Workspace()))
    assert calls == [{"job_id": "bad-job", "error_message": "clinical_source_snapshot_invalid", "queued_only": True, "expected_queued_filters_json": "fixed-original"}]


def test_same_key_current_document_requests_do_not_coalesce_across_sources(profile, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.services.bundles import current_view
    entered = Barrier(2)
    def assemble(**identity):
        entered.wait(timeout=5)
        return {"documents": [clinical.source_binding()]}
    monkeypatch.setattr(current_view, "_assemble_current_documents", assemble)
    def load(selection):
        with clinical.selected(selection):
            return current_view.load_current_documents(**REF)
    value = sources.snapshot(profile, "independent_cdm")
    with ThreadPoolExecutor(max_workers=2) as pool:
        old = pool.submit(load, sources.legacy_snapshot())
        new = pool.submit(load, value)
        assert old.result(timeout=8) == {"documents": [""]}
        assert new.result(timeout=8) == {"documents": [value["binding"]]}


def test_historical_document_source_comes_from_job_not_current_default(settings_store, profile, monkeypatch):
    from app.database import connection as owner
    value = sources.snapshot(profile, "independent_cdm")
    filters = {"record_refs": [REF], "clinical_source": value}
    settings_store.execute(text("CREATE TABLE qc.custom_qc_batch_jobs(id TEXT,created_by TEXT,filters_json TEXT,parent_job_id TEXT)"))
    settings_store.execute(text("INSERT INTO qc.custom_qc_batch_jobs VALUES('saved','owner',:filters,NULL)"), {"filters": json.dumps(filters)})
    settings_store.commit()
    monkeypatch.setattr(owner, "SessionLocal", lambda: Session(settings_store.get_bind()))
    monkeypatch.setattr(sources, "configuration", lambda: pytest.fail("历史任务不按当前默认源重新解释"))
    query = "job_id=saved&" + "&".join(f"{key}={value}" for key, value in REF.items())
    req = request("/api/v1/emr/visit-1/documents", query)
    req.state.current_user = {"id": "manager", "roles": ["qc_manager"]}
    sources.prepare_request(req)
    assert req.state.clinical_source == value
    mismatched = request("/api/v1/emr/foreign/documents", query.replace("patient-1", "foreign"))
    mismatched.state.current_user = req.state.current_user
    with pytest.raises(HTTPException) as caught:
        sources.prepare_request(mismatched)
    assert caught.value.status_code == 403

    denied = request("/api/v1/emr/visit-1/documents", query)
    denied.state.current_user = {"id": "unrelated", "roles": []}
    with pytest.raises(HTTPException) as caught:
        sources.prepare_request(denied)
    assert caught.value.status_code == 403


def test_registered_pdf_read_survives_disabled_legacy(profile, monkeypatch):
    from app.services import validation_material_source
    profile.legacy_enabled = False
    profile.default_source = "independent_cdm"
    monkeypatch.setattr(sources, "configuration", lambda: profile)
    monkeypatch.setattr(validation_material_source, "_registered_schema", lambda *args: "pdfmat_012345abcdef")
    req = request("/api/v1/emr/pdfv_V/documents", "institute_id=I&patient_id=pdfp_P&visit_id=pdfv_V", "legacy_pg")
    sources.prepare_request(req)
    with sources.request_selection(req):
        assert clinical.current_selection() == sources.legacy_snapshot()
        assert clinical.get_engine() is None
