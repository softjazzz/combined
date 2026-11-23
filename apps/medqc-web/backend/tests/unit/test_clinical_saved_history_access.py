"""所有代际历史文书的持久账号授权；仅合成内存数据。"""
import json

from fastapi import HTTPException
import pytest
from app.database import connection
from app.database.models.v36_reports import SysUser
from app.services import clinical_sources as sources
from app.services.data_pipeline_settings import PipelineError
from tests.unit.test_material_job_lineage import REF, family, job, request, saved  # noqa: F401


def saved_generation(saved, generation):
    rows, _ = family()
    if generation in {"leaf", "untagged"}:
        selected = job("original")
        if generation == "untagged":
            filters = json.loads(selected["filters_json"])
            filters.pop("clinical_source")
            selected["filters_json"] = json.dumps(filters)
        rows[selected["id"]] = selected
    else:
        selected = rows[generation]
    saved(rows.values())
    return selected


@pytest.mark.parametrize("generation", ["leaf", "child", "parent", "untagged"])
@pytest.mark.parametrize("case", ["foreign_manager", "transferred_owner", "inactive", "unknown", "invalid_roles", "missing_institute", "forged_role"])
def test_every_saved_generation_rechecks_current_persistent_account(saved, generation, case):
    selected = saved_generation(saved, generation)
    actor_id = "foreign-manager" if case == "foreign_manager" else "unknown" if case == "unknown" else "synthetic-owner"
    with connection.SessionLocal() as session:
        actor = session.get(SysUser, "synthetic-owner")
        if case == "foreign_manager":
            actor = SysUser(id=actor_id, username=actor_id, display_name="合成他院管理者", role="qc_manager",
                            roles_json='["qc_manager"]', is_active=True)
            session.add(actor)
        if case in {"foreign_manager", "transferred_owner"}:
            actor.institute_id = "OTHER-HOSPITAL"
        elif case == "inactive":
            actor.is_active = False
        elif case == "invalid_roles":
            actor.roles_json = "broken"
        elif case == "missing_institute":
            actor.institute_id = None
        elif case == "forged_role":
            actor.role, actor.roles_json = "viewer", '["viewer"]'
        session.commit()
    req = request(actor=actor_id)
    req.state.current_user["roles"] = ["super_admin", "qc_manager"]
    with pytest.raises(HTTPException) as caught:
        sources.source_for_saved_job(req, selected["id"])
    assert caught.value.status_code == 403
    assert not getattr(req.state, "material_root_job_id", "")


@pytest.mark.parametrize("roles", [["qc_manager"], ["qc_staff"], ["admin"], ["sync_admin"], ["super_admin"]])
def test_history_authorizes_persistent_roles_without_request_role_claims(saved, roles, monkeypatch):
    from app.services import doctor_case_scope

    saved([job("original")])
    with connection.SessionLocal() as session:
        session.add(SysUser(id="reader", username="reader", display_name="合成读取者", role=roles[0],
                            roles_json=json.dumps(roles), institute_id=REF["institute_id"] if roles[0].startswith("qc_") else "GLOBAL",
                            is_active=True))
        session.commit()
    monkeypatch.setattr(sources, "configuration", lambda: pytest.fail("历史读取不得依赖当前CDM配置"))
    monkeypatch.setattr(doctor_case_scope, "resolve_doctor_case_scope", lambda *a, **kw: pytest.fail("管理角色不进入医生范围查询"))
    req = request(actor="reader")
    assert sources.source_for_saved_job(req, "original") == sources.legacy_snapshot()
    assert req.state.material_root_job_id == "original"


@pytest.mark.parametrize("refs", [None, [], [{**REF, "institute_id": "OTHER-HOSPITAL"}]])
def test_untagged_history_requires_trusted_saved_identity_before_material_access(saved, refs):
    original = job("untagged")
    original["filters_json"] = json.dumps({"record_refs": refs})
    saved([original])
    req = request()
    with pytest.raises(PipelineError) as caught:
        sources.source_for_saved_job(req, "untagged")
    assert caught.value.status == 403
    assert not getattr(req.state, "material_root_job_id", "")


@pytest.mark.parametrize("own_case", [True, False])
def test_original_history_preserves_real_doctor_personal_scope(saved, own_case, monkeypatch):
    from app.services import doctor_case_scope

    saved([job("original")])
    with connection.SessionLocal() as session:
        actor = session.get(SysUser, "synthetic-owner")
        actor.role, actor.roles_json = "doctor", '["doctor"]'
        session.commit()
    scope = doctor_case_scope.DoctorCaseScope(REF["institute_id"], "合成科室", "合成医生", (tuple(REF.values()),) if own_case else ())
    monkeypatch.setattr(doctor_case_scope, "resolve_doctor_case_scope", lambda *a, **kw: scope)
    req = request()
    req.state.current_user["roles"] = ["super_admin"]
    if own_case:
        assert sources.source_for_saved_job(req, "original") == sources.legacy_snapshot()
    else:
        with pytest.raises(HTTPException) as caught:
            sources.source_for_saved_job(req, "original")
        assert caught.value.status_code == 403
        assert not getattr(req.state, "material_root_job_id", "")


@pytest.mark.asyncio
async def test_original_child_history_reads_frozen_material_without_live_cdm(saved, monkeypatch, tmp_path):
    from app.database import clinical_connection as clinical
    from app.services import case_material_snapshot as material
    from app.services.bundles import current_view

    saved_generation(saved, "child")
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    state = {"protocol": material.PROTOCOL, "identity": list(REF.values()), "binding": "", "schema": "cdm",
             "columns": {}, "tables": {}, "queries": {}, "documents": {"documents": [{"content": "合成首轮正文"}]}}
    with clinical.selected(sources.legacy_snapshot()):
        original = material.persist("parent", state)
    monkeypatch.setattr(sources, "configuration", lambda: pytest.fail("历史读取不依赖当前来源配置"))
    monkeypatch.setattr(clinical, "get_engine", lambda: pytest.fail("历史读取不得连接当前CDM"))
    monkeypatch.setattr(current_view, "_assemble_current_documents", lambda **_: pytest.fail("历史读取不得补查当前材料"))
    req = request()
    req.state.clinical_source = sources.source_for_saved_job(req, "child")
    dependency = sources.bind_request(req)
    await anext(dependency)
    try:
        assert material.current()["fingerprint"] == original["fingerprint"]
        assert current_view.load_current_documents(**REF) == state["documents"]
    finally:
        await dependency.aclose()


@pytest.mark.asyncio
async def test_result_comparison_opens_frozen_directory_and_exact_document(saved, monkeypatch, tmp_path):
    import hashlib

    import httpx
    from fastapi import Depends, FastAPI, Request
    from app.core.security import get_current_user
    from app.database import clinical_connection as clinical
    from app.routers import emr_render
    from app.services import case_material_snapshot as material
    from app.services.cdm_publication_evidence import target_hash
    from app.services.qc_workspace.canonical_result_store import customer_safe_projection_key, keyed_ref

    coord = {**REF, "institute_id": "机构号"}
    identity = tuple(coord.values())
    binding = "cdm-read-v1:" + hashlib.sha256(json.dumps(["synthetic", 5432, "cdm", "ro", "cdm"]).encode()).hexdigest()
    source = {"id": "independent_cdm", "url": "postgresql://ro@synthetic/cdm", "binding": binding}
    filters = {"clinical_source": source, "record_refs": [coord]}
    saved([{**job("original"), "filters_json": json.dumps(filters)}])
    with connection.SessionLocal() as session:
        session.get(SysUser, "synthetic-owner").institute_id = "泸县人民医院"
        session.commit()
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    monkeypatch.setattr(emr_render, "_load_live_cdm_documents", lambda *args: pytest.fail("历史文书不能回查当前正文"))
    epoch = "7cecd40f-047d-4458-b964-8741d0ea7399"
    digest = target_hash(coord)
    evidence = {"status": "receipt_verified", "target_key_hash": digest,
                "receipt": {"source_epoch": epoch, "target_key_hash": digest},
                "operation": {"source_epoch": epoch, "interface_name": "web.admission_record"}}
    doc = {"document_id": "SYN-ADM", "doc_type": "admission_record", "content": "冻结入院原文"}
    state = {"protocol": material.PROTOCOL, "schema": "cdm", "identity": list(identity), "binding": binding,
             "documents": {"documents": [doc]}, "tables": {},
             "automatic_material": {"publication": {"status": "metadata_available", "rows": {"admission_record": [evidence]}}}}
    with clinical.selected(source):
        material.persist("original", state)

    async def prepare(req: Request):
        req.state.current_user = {"id": "synthetic-owner"}
        sources.prepare_request(req)
    app = FastAPI(dependencies=[Depends(prepare), Depends(sources.bind_request)])
    app.include_router(emr_render.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "synthetic-owner", "roles": ["qc_manager"]}
    params = {**coord, "job_id": "original"}
    path = f"/api/v1/emr/{coord['visit_id']}"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://local.test") as client:
        response = await client.get(path + "/documents", params={**params, "view": "summary", "document_scope": "clinical"})
        assert response.status_code == 200, response.text
        [summary] = response.json()["data"]["documents"]
        assert summary["source_ref"] == keyed_ref("src", doc["document_id"], hmac_key=customer_safe_projection_key())
        assert doc["content"] not in response.text
        body = await client.get(path + "/render", params={**params, "doc_type": doc["doc_type"], "doc_id": summary["document_id"]})
        assert body.status_code == 200 and body.json()["data"]["content"] == doc["content"]
        missing = await client.get(path + "/render", params={**params, "doc_id": "another-doc"})
        assert missing.json()["data"]["empty_reason"] == "document_not_found"
        wrong_case = await client.get(path + "/documents", params={**params, "patient_id": "another-patient"})
        assert wrong_case.status_code == 403
        with connection.SessionLocal() as session:
            session.get(SysUser, "synthetic-owner").institute_id = "其他医院"
            session.commit()
        denied = await client.get(path + "/render", params={**params, "doc_id": doc["document_id"]})
        assert denied.status_code == 403 and doc["content"] not in denied.text
