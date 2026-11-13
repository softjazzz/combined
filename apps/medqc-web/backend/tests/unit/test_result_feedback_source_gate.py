"""结果反馈读取不依赖当前临床来源；保留认证和反馈权限。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from app.core import access_control
from app.routers import qc_sichuan
from app.services import clinical_sources as sources, doctor_case_scope
from tests.unit.test_clinical_sources import request

PATH = "/api/v1/qc/sichuan/workspace/result-feedback-demo"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "fixed_donghua_cdm")
    monkeypatch.setattr(sources, "configuration", lambda: sources.SourceSettings())
    users = {"demo": {"id": "admin-001", "email": "admin@medqc.com", "roles": ["qc_manager"]},
             "other": {"id": "other", "email": "other@example.com", "roles": ["qc_manager"]}}
    monkeypatch.setattr(access_control, "resolve_current_user_from_token", lambda token: users[token])
    monkeypatch.setattr(doctor_case_scope, "enforce_doctor_case_access", AsyncMock())
    read = Mock(return_value={})
    monkeypatch.setattr(qc_sichuan, "get_result_feedback_demo_store",
                        lambda: SimpleNamespace(list_for_record=read))
    app = FastAPI(dependencies=[Depends(access_control.enforce_default_auth), Depends(sources.bind_request)])
    app.add_api_route(PATH, qc_sichuan.get_demo_result_feedback, methods=["GET"])
    with TestClient(app) as value:
        yield value, read


@pytest.mark.parametrize("token,status", [(None, 401), ("other", 403), ("demo", 200)])
def test_saved_feedback_get_with_disabled_cdm_keeps_permissions(client, token, status):
    http, read = client
    response = http.get(PATH, params={"root_job_id": "synthetic-job", "record_ref": "rec_synthetic"},
                        headers={"Authorization": f"Bearer {token}"} if token else {})
    assert response.status_code == status
    if status == 200:
        read.assert_called_once_with(root_job_id="synthetic-job", record_ref="rec_synthetic",
                                     created_by="admin-001")
    else:
        read.assert_not_called()


@pytest.mark.parametrize("suffix,method", [("/all", "GET"), ("-extra", "GET"), ("/RULE", "PUT")])
def test_feedback_exception_does_not_cover_live_enrichment_or_writes(monkeypatch, suffix, method):
    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "fixed_donghua_cdm")
    monkeypatch.setattr(sources, "configuration", lambda: sources.SourceSettings())
    req = request(PATH + suffix)
    req.scope["method"] = method
    with pytest.raises(HTTPException) as caught:
        sources.prepare_request(req)
    assert caught.value.detail == "clinical_source_disabled"


@pytest.mark.parametrize("query,header", [("", "unknown"), ("source_id=legacy_pg", "independent_cdm")])
def test_feedback_source_identity_errors_still_rejected(query, header):
    with pytest.raises(HTTPException) as caught:
        sources.prepare_request(request(PATH, query, header))
    assert caught.value.status_code == 422
