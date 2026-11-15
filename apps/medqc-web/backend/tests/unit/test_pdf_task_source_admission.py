import asyncio
import json
import pytest
from starlette.requests import Request
from fastapi import HTTPException
from app.services import clinical_sources as sources

REF = {"institute_id":"I", "patient_id":"pdfp_P", "visit_id":"pdfv_V"}
def request(refs, headers=()):
    body=json.dumps({"record_refs":refs}).encode()
    async def receive(): return {"type":"http.request","body":body,"more_body":False}
    return Request({"type":"http","method":"POST","path":"/api/v1/qc/sichuan/workspace/batch-jobs","headers":list(headers),"query_string":b""},receive)

def test_registered_pdf_create_uses_bound_local_source(monkeypatch):
    calls=[]
    monkeypatch.setattr(sources,"_registered_local_case",lambda ref: calls.append(ref) or True)
    r=request([REF])
    asyncio.run(sources.prepare_task_material_request(r))
    sources.prepare_request(r)
    assert r.state.clinical_source==sources.legacy_snapshot()
    assert calls==[REF]

@pytest.mark.parametrize("refs", [[{**REF,"patient_id":""}], [REF,{"institute_id":"I","patient_id":"P","visit_id":"V"}], [REF,"bad"]])
def test_invalid_or_mixed_pdf_create_rejected(monkeypatch,refs):
    monkeypatch.setattr(sources,"_registered_local_case",lambda ref: True)
    with pytest.raises(HTTPException): asyncio.run(sources.prepare_task_material_request(request(refs)))

def test_unregistered_pdf_rejected(monkeypatch):
    def reject(ref): raise ValueError("unregistered")
    monkeypatch.setattr(sources,"_registered_local_case",reject)
    with pytest.raises(HTTPException): asyncio.run(sources.prepare_task_material_request(request([REF])))

def test_conflicting_source_rejected(monkeypatch):
    monkeypatch.setattr(sources,"_registered_local_case",lambda ref: True)
    with pytest.raises(HTTPException): asyncio.run(sources.prepare_task_material_request(request([REF],[(b"x-clinical-source",b"independent_cdm")])))

def test_ordinary_create_keeps_independent_gate(monkeypatch):
    monkeypatch.setattr(sources,"fixed_cdm",lambda: True)
    monkeypatch.setattr(sources,"configuration",lambda: sources.SourceSettings())
    r=request([{"institute_id":"I","patient_id":"P","visit_id":"V"}])
    asyncio.run(sources.prepare_task_material_request(r))
    with pytest.raises(HTTPException,match="clinical_source_disabled"): sources.prepare_request(r)


def test_authenticated_http_body_survives_admission(monkeypatch):
    from fastapi import FastAPI, Depends
    from fastapi.testclient import TestClient
    from app.core import access_control
    from app.database import clinical_connection as clinical
    monkeypatch.setattr(access_control,"resolve_current_user_from_token",lambda _: {"id":"synthetic","roles":["admin"]})
    monkeypatch.setattr(sources,"_registered_local_case",lambda ref: ref==REF)
    app=FastAPI(dependencies=[Depends(access_control.enforce_default_auth),Depends(sources.bind_request)])
    @app.post("/api/v1/qc/sichuan/workspace/batch-jobs")
    def create(payload: dict):
        assert clinical.current_selection()==sources.legacy_snapshot()
        sources.freeze(payload)
        assert payload["clinical_source"]==sources.legacy_snapshot()
        return {"refs":payload["record_refs"]}
    with TestClient(app) as client:
        assert client.post("/api/v1/qc/sichuan/workspace/batch-jobs",json={"record_refs":[REF]}).status_code==401
        result=client.post("/api/v1/qc/sichuan/workspace/batch-jobs",json={"record_refs":[REF]},headers={"Authorization":"Bearer synthetic"})
        assert result.status_code==200
        assert result.json()=={"refs":[REF]}
