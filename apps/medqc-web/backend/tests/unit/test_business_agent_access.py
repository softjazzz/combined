"""试点范围必须来自服务端授权，不能来自个人资料或模型筛选。"""
import json

import pytest
from fastapi import HTTPException

from app.services.qc_agent.business_access import BusinessAccess, get_business_access
from app.services.qc_agent.business_schemas import BusinessContext


DOCTOR = {"id": "doctor-a", "roles": ["doctor"], "department": "可自行修改的科室"}
MANAGER = {"id": "manager-a", "roles": ["qc_manager"], "department": "可自行修改的科室"}
CASE = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}


def policy():
    return BusinessAccess({"version": 1, "accounts": {
        "doctor-a": {"doctor_cases": [CASE]},
        "manager-a": {"manager_scopes": [{"institute_id": "H1", "department": "本科室"}]},
    }})


def test_doctor_exact_case_and_role_are_both_required():
    access = policy()
    access.require_context(DOCTOR, BusinessContext(view="doctor", **CASE))
    for identity in [{**CASE, "institute_id": "H2"}, {**CASE, "patient_id": "P2"}, {**CASE, "visit_id": "V2"}]:
        with pytest.raises(HTTPException) as denied:
            access.require_context(DOCTOR, BusinessContext(view="doctor", **identity))
        assert denied.value.status_code == 403
    with pytest.raises(HTTPException):
        access.require_context({**DOCTOR, "roles": ["reviewer"]}, BusinessContext(view="doctor", **CASE))
    with pytest.raises(HTTPException):
        access.require_context({"id": "other", "roles": ["admin"]}, BusinessContext(view="doctor", **CASE))


def test_manager_scope_binds_institution_and_ignores_profile_department():
    access = policy()
    context = BusinessContext(view="manager", institute_id="H1", department="本科室", care_phase="discharged", completed_from="2026-09-01T00:00:00+08:00", completed_to="2026-09-30T23:59:59+08:00")
    access.require_context(MANAGER, context)
    for changes in [{"institute_id": "H2"}, {"department": MANAGER["department"]}, {"completed_to": None}]:
        with pytest.raises(HTTPException):
            access.require_context(MANAGER, context.model_copy(update=changes))
    assert access.visible_scope(MANAGER)["manager_scopes"] == [{"institute_id": "H1", "department": "本科室"}]
    assert access.visible_scope(DOCTOR)["manager_scopes"] == []


def test_configuration_is_reloaded_and_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "access-private.json"
    monkeypatch.setenv("MEDQC_AGENT_ACCESS_FILE", str(path))
    with pytest.raises(HTTPException) as missing:
        get_business_access()
    assert missing.value.status_code == 503
    path.write_text(json.dumps({"version": 1, "accounts": {"doctor-a": {"doctor_cases": [CASE]}}}), encoding="utf-8")
    get_business_access().require_context(DOCTOR, BusinessContext(view="doctor", **CASE))
    path.write_text('{"version":1,"accounts":{}}', encoding="utf-8")
    with pytest.raises(HTTPException) as revoked:
        get_business_access().require_context(DOCTOR, BusinessContext(view="doctor", **CASE))
    assert revoked.value.status_code == 403


def test_case_scope_is_checked_before_formal_service_reads(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.security import get_current_user
    from app.routers.business_agent import router, business_reads
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: DOCTOR
    app.dependency_overrides[get_business_access] = policy
    calls = []
    def read(identity):
        calls.append(identity)
        return {"state": "ready", "items": []}
    monkeypatch.setattr(business_reads, "saved_record", read)
    client = TestClient(app)
    assert client.get("/business/records/V2/latest-result", params={"institute_id": "H1", "patient_id": "P1"}).status_code == 403
    assert calls == []
    assert client.get("/business/records/V1/latest-result", params={"institute_id": "H1", "patient_id": "P1"}).status_code == 200
    assert calls == [CASE]


def test_manager_same_department_other_institution_is_excluded_before_results(monkeypatch):
    from app.services.qc_agent import business_reads
    from app.services.workstation import luxian_0609_result_analysis_service as formal
    from app.services import custom_qc_workspace_service as workspace
    rows = [{**CASE, "department": "本科室"}, {**CASE, "institute_id": "H2", "department": "本科室"}, {**CASE, "visit_id": "V3", "department": "其他科室"}]
    monkeypatch.setattr(formal, "_load_current_workstation_records", lambda **_: rows)
    result_calls = []
    class ReadonlyWorkspace:
        def __init__(self, *, readonly):
            assert readonly is True
        def build_luxian_0609_completed_record_result_summaries(self, *, record_refs, include_items):
            result_calls.extend(record_refs)
            assert include_items is True
            return {}
    monkeypatch.setattr(workspace, "CustomQCWorkspaceService", ReadonlyWorkspace)
    data = business_reads.department_analysis(institute_id="H1", department="本科室", care_phase="discharged")
    assert data["kpis"]["scoped_record_total"] == 1
    assert result_calls == [CASE]
    with pytest.raises(HTTPException):
        business_reads.require_record(policy(), MANAGER, {**CASE, "institute_id": "H2"}, "manager", "本科室")
    with pytest.raises(HTTPException):
        business_reads.require_record(policy(), MANAGER, {**CASE, "visit_id": "V4"}, "manager", "本科室")


def test_formal_statistics_route_cannot_bypass_manager_scope(tmp_path, monkeypatch):
    import importlib.util
    import sys
    from pathlib import Path
    from types import ModuleType
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.security import get_current_user
    from app.services.qc_agent import business_reads
    # 单独执行真实 router 源码；只隔离无关工作队列的导入，不初始化共享库或 Worker。
    unrelated = ModuleType("app.services.workstation.worklist_service")
    unrelated.default_workstation_aggregation_service = object()
    monkeypatch.setitem(sys.modules, unrelated.__name__, unrelated)
    spec = importlib.util.spec_from_file_location("app.routers._isolated_business_statistics", Path(__file__).resolve().parents[2] / "app/routers/workstation.py")
    workstation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(workstation)
    path = tmp_path / "access-private.json"
    path.write_text(policy().config.model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("MEDQC_AGENT_ACCESS_FILE", str(path))
    user = {"value": DOCTOR}
    app = FastAPI()
    app.include_router(workstation.router)
    app.dependency_overrides[get_current_user] = lambda: user["value"]
    calls = []
    def read(**filters):
        calls.append(filters)
        return {"kpis": {"scoped_record_total": 1}}
    monkeypatch.setattr(business_reads, "department_analysis", read)
    monkeypatch.setattr(workstation.default_luxian_0609_result_analysis_service, "get_analysis", read)
    client = TestClient(app)
    url = "/api/v1/workstation/qc-result-analysis/luxian-0609"
    assert client.get(url, params={"care_phase": "discharged"}).status_code == 403
    assert calls == []
    user["value"] = MANAGER
    assert client.get(url, params={"care_phase": "discharged", "department": "其他科室"}).status_code == 403
    assert client.get(url, params={"care_phase": "discharged", "department": "本科室", "institute_id": "H2"}).status_code == 403
    assert calls == []
    assert client.get(url, params={"care_phase": "discharged", "department": "本科室"}).status_code == 200
    assert calls[0]["institute_id"] == "H1"
    user["value"] = {"id": "admin", "roles": ["admin"]}
    assert client.get(url, params={"care_phase": "inpatient", "page": 2, "page_size": 10}).status_code == 200
    assert calls[-1]["care_phase"] == "inpatient"
    assert calls[-1]["page"] == 2
    assert calls[-1]["page_size"] == 10


def test_readonly_workspace_initialization_never_creates_or_alters_tables(monkeypatch):
    from app.services import custom_qc_workspace_service as workspace
    monkeypatch.setattr(workspace, "engine", object())
    def forbidden(*args, **kwargs):
        raise AssertionError("只读初始化不得执行建表或补列")
    monkeypatch.setattr(workspace.MetaData, "create_all", forbidden)
    monkeypatch.setattr(workspace, "_sync_batch_job_parent_columns", forbidden)
    workspace._drafts_table.cache_clear()
    workspace._batch_jobs_table.cache_clear()
    try:
        service = workspace.CustomQCWorkspaceService(readonly=True)
        assert service._batch_job_table.name == "custom_qc_batch_jobs"
        assert service._record_result_envelope_table.name == "luxian_0609_record_result_envelopes"
    finally:
        workspace._drafts_table.cache_clear()
        workspace._batch_jobs_table.cache_clear()
