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
