"""CDM停用时业务元数据仍可读，临床取材与历史归属保护不放宽。"""

from unittest.mock import AsyncMock

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from app.core import access_control
from app.database import clinical_connection as clinical
from app.routers import qc_sichuan
from app.services import clinical_sources as sources
from app.services import custom_qc_workspace_service as workspace
from app.services import doctor_case_scope
from tests.unit.test_batch_job_overview import overview_store  # noqa: F401
from tests.unit.test_clinical_sources import request


PREFIX = "/api/v1/qc/sichuan/workspace"
PATHS = (f"{PREFIX}/rule-sets", f"{PREFIX}/batch-jobs")


@pytest.fixture
def metadata_client(monkeypatch, overview_store):  # noqa: F811
    stored, statements = overview_store
    engine = workspace._session.kw["bind"]
    constructors = []
    scope_check = AsyncMock()
    real_service = workspace.CustomQCWorkspaceService
    # 执行真实初始化函数，同时避免内存库表定义污染其它用例的进程级缓存。
    for name in ("_drafts_table", "_batch_jobs_table", "_record_result_envelopes_table"):
        builder = getattr(workspace, name)
        monkeypatch.setattr(workspace, name, builder.__wrapped__)
    with engine.begin() as connection:
        connection.execute(stored._batch_job_table.update().values(draft_id="sichuan-rule-library"))
    statements.clear()

    def service(*, readonly=False):
        constructors.append(readonly)
        value = real_service(readonly=readonly)
        value._batch_job_table = stored._batch_job_table
        return value

    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "fixed_donghua_cdm")
    monkeypatch.setattr(sources, "configuration", lambda: sources.SourceSettings())
    monkeypatch.setattr(workspace, "engine", engine)
    monkeypatch.setattr(workspace, "_draft_schema", lambda: None)
    monkeypatch.setattr(qc_sichuan, "CustomQCWorkspaceService", service)
    monkeypatch.setattr(
        doctor_case_scope, "enforce_doctor_case_access", scope_check
    )
    monkeypatch.setattr(
        access_control, "resolve_current_user_from_token",
        lambda token: {"id": token, "roles": ["sync_admin"]},
    )

    def forbidden(*args, **kwargs):
        pytest.fail("业务元数据不得连接CDM、读取病例或执行DDL")

    monkeypatch.setattr(clinical, "_engine", forbidden)
    monkeypatch.setattr(workspace, "_sync_batch_job_parent_columns", forbidden)
    monkeypatch.setattr(workspace.MetaData, "create_all", forbidden)
    app = FastAPI(dependencies=[
        Depends(access_control.enforce_default_auth), Depends(sources.bind_request),
    ])
    app.add_api_route(PATHS[0], qc_sichuan.list_workspace_rule_sets, methods=["GET"])
    app.add_api_route(PATHS[1], qc_sichuan.list_workspace_batch_jobs, methods=["GET"])
    with TestClient(app) as client:
        yield client, statements, constructors, scope_check


@pytest.mark.parametrize("path", PATHS)
def test_metadata_get_keeps_authentication(metadata_client, path):
    client, _, constructors, _ = metadata_client
    assert client.get(path).status_code == 401
    assert constructors == []


def test_rule_sets_without_cdm_never_initializes_workspace(metadata_client):
    client, _, constructors, scope_check = metadata_client
    response = client.get(PATHS[0], headers={"Authorization": "Bearer u-1"})
    assert response.status_code == 200
    assert any(
        item["rule_set_key"] == "luxian_0609_qc_v1"
        for item in response.json()["data"]["items"]
    )
    assert constructors == [] and scope_check.await_count == 1
    assert clinical.current_selection() is None


@pytest.mark.parametrize("view", ["", "overview"])
def test_batch_list_is_readonly_and_keeps_owner_and_pagination(metadata_client, view):
    client, statements, constructors, scope_check = metadata_client
    headers = {"Authorization": "Bearer u-1"}
    response = client.get(PATHS[1], params={"view": view, "page_size": 2}, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 5
    assert len(response.json()["data"]["items"]) == 2
    assert "other-user" not in {item["id"] for item in response.json()["data"]["items"]}
    other = client.get(PATHS[1], params={"view": view}, headers={"Authorization": "Bearer u-2"})
    assert other.status_code == 200 and other.json()["data"]["total"] == 1
    assert constructors == [True, True] and scope_check.await_count == 2
    assert statements and all(sql.lstrip().upper().startswith("SELECT") for sql in statements)
    assert clinical.current_selection() is None


@pytest.mark.parametrize("path", PATHS)
def test_metadata_unknown_source_is_not_silently_accepted(metadata_client, path):
    client, _, constructors, _ = metadata_client
    response = client.get(
        path, headers={"Authorization": "Bearer u-1", "X-Clinical-Source": "unknown"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "unknown_clinical_source"
    assert constructors == []


@pytest.mark.parametrize("path", PATHS)
def test_metadata_get_still_rejects_conflicting_source_identity(metadata_client, path):
    client, _, constructors, _ = metadata_client
    response = client.get(
        path, params={"source_id": "legacy_pg"},
        headers={"Authorization": "Bearer u-1", "X-Clinical-Source": "independent_cdm"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "clinical_source_selection_conflict"
    assert constructors == []


@pytest.mark.parametrize("path", PATHS)
def test_metadata_get_needs_no_source_configuration(monkeypatch, path):
    monkeypatch.setattr(sources, "configuration", lambda: pytest.fail("不读取临床配置"))
    req = request(path, header="independent_cdm")
    sources.prepare_request(req)
    assert req.state.clinical_source == sources.legacy_snapshot()


@pytest.mark.parametrize("path", [
    "/api/medical-records/workstation", f"{PREFIX}/records",
    f"{PREFIX}/rule-sets-extra", f"{PREFIX}/batch-jobs-extra",
])
def test_actual_clinical_get_remains_fail_closed(monkeypatch, path):
    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "fixed_donghua_cdm")
    monkeypatch.setattr(sources, "configuration", lambda: sources.SourceSettings())
    with pytest.raises(HTTPException) as caught:
        sources.prepare_request(request(path))
    assert caught.value.status_code == 409
    assert caught.value.detail == "clinical_source_disabled"


@pytest.mark.parametrize("path", PATHS)
def test_metadata_exception_does_not_apply_to_post(monkeypatch, path):
    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "fixed_donghua_cdm")
    monkeypatch.setattr(sources, "configuration", lambda: sources.SourceSettings())
    req = request(path)
    req.scope["method"] = "POST"
    with pytest.raises(HTTPException) as caught:
        sources.prepare_request(req)
    assert caught.value.status_code == 409
    assert caught.value.detail == "clinical_source_disabled"
