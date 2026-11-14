"""重试、批量父子与历史文书共享材料身份；仅合成内存数据。"""
import hashlib
import json
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request
from fastapi import HTTPException

from app.database import connection
from app.services import clinical_sources
from app.services.data_pipeline_settings import PipelineError
from app.database.models.v36_reports import SysUser
from test_doctor_case_scope import database as doctor_database  # noqa: F401


REF = {"institute_id": "SYNTHETIC-I", "patient_id": "SYNTHETIC-P", "visit_id": "SYNTHETIC-V"}


def job(job_id, *, parent="", kind="leaf", children=()):
    filters = {"clinical_source": clinical_sources.legacy_snapshot(), "record_refs": [REF], "_lx0609_attempt_id": "a" * 32}
    return {"id": job_id, "created_by": "synthetic-owner", "filters_json": json.dumps(filters),
            "parent_job_id": parent, "job_kind": kind, "child_job_ids_json": json.dumps(list(children))}


def retry(source, *, material_id=None):
    filters = json.loads(source["filters_json"])
    previous = filters.get("retry_lineage", {})
    digest = hashlib.sha256(source["filters_json"].encode()).hexdigest()
    new_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"medqc:retry:v1:{source['id']}:{digest}"))
    filters["retry_lineage"] = {"schema_version": "qc-retry-lineage-v1", "source_job_id": source["id"],
        "root_job_id": previous.get("root_job_id") or source["id"],
        "material_job_id": material_id or previous.get("material_job_id") or source["id"],
        "source_filters_sha256": digest, "source_attempt": filters["_lx0609_attempt_id"],
        "attempt": previous.get("attempt", 0) + 1, "trigger": "manual"}
    filters["_lx0609_attempt_id"] = "b" * 32
    result = {**source, "id": new_id, "filters_json": json.dumps(filters), "parent_job_id": "", "job_kind": "leaf", "child_job_ids_json": "[]"}
    return result


def family():
    parent = job("parent", kind="parent", children=["child"])
    child = job("child", parent="parent", kind="child")
    first = retry(child, material_id="parent")
    second = retry(first)
    return {row["id"]: row for row in (parent, child, first, second)}, second


@pytest.fixture
def saved(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS qc"))
        conn.execute(text("CREATE TABLE qc.custom_qc_batch_jobs (id TEXT PRIMARY KEY,created_by TEXT,filters_json TEXT,parent_job_id TEXT,job_kind TEXT,child_job_ids_json TEXT)"))
    monkeypatch.setattr(connection, "SessionLocal", sessionmaker(bind=engine))
    SysUser.__table__.create(engine)
    with connection.SessionLocal() as session:
        session.add(SysUser(id="synthetic-owner", username="synthetic-owner", display_name="合成医生",
                            institute_id=REF["institute_id"], department="合成科室", role="qc_manager",
                            roles_json='["qc_manager"]', is_active=True))
        session.commit()
    def insert(rows):
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO qc.custom_qc_batch_jobs VALUES (:id,:created_by,:filters_json,:parent_job_id,:job_kind,:child_job_ids_json)"), list(rows))
    yield insert
    engine.dispose()


def request(ref=REF, actor="synthetic-owner"):
    req = Request({"type": "http", "path": "/api/v1/emr/documents", "query_string": "&".join(f"{k}={v}" for k, v in ref.items()).encode(), "headers": []})
    req.state.current_user = {"id": actor}
    return req


def test_history_retry_of_child_resolves_original_parent_material(saved):
    rows, last = family()
    saved(rows.values())
    req = request()
    assert clinical_sources.source_for_saved_job(req, last["id"]) == clinical_sources.legacy_snapshot()
    assert req.state.material_root_job_id == "parent"


@pytest.mark.parametrize("kind", ["leaf", "child", "first_retry", "second_retry"])
def test_shared_resolver_handles_first_generation_and_retries(kind):
    from app.services.material_job_lineage import resolve_material_job_id
    rows, last = family()
    original = job("leaf")
    rows["leaf"] = original
    selected = original if kind == "leaf" else rows["child"] if kind == "child" else rows[json.loads(last["filters_json"])["retry_lineage"]["source_job_id"]] if kind == "first_retry" else last
    assert resolve_material_job_id(selected, rows.get) == ("leaf" if kind == "leaf" else "parent")


@pytest.mark.parametrize("field,value", [("material_job_id", "unrelated"), ("root_job_id", "parent"), ("attempt", 99), ("source_attempt", "spoofed"), ("source_filters_sha256", "f" * 64)])
def test_forged_lineage_cannot_borrow_material(field, value):
    from app.services.material_job_lineage import resolve_material_job_id
    rows, last = family()
    filters = json.loads(last["filters_json"])
    filters["retry_lineage"][field] = value
    last["filters_json"] = json.dumps(filters)
    rows["unrelated"] = job("unrelated")
    with pytest.raises(ValueError, match="retry_lineage"):
        resolve_material_job_id(last, rows.get)


@pytest.mark.parametrize("corruption", ["owner", "parent_kind", "child_kind", "filter_only_parent", "child_backlink", "parent_identity", "parent_source", "missing_parent", "parent_filter_conflict"])
def test_first_generation_child_requires_valid_original_family(corruption):
    from app.services.material_job_lineage import resolve_material_job_id
    rows, _ = family()
    parent, child = rows["parent"], rows["child"]
    if corruption == "owner":
        parent["created_by"] = "other-owner"
    elif corruption == "parent_kind":
        parent["job_kind"] = "leaf"
    elif corruption == "child_kind":
        child["job_kind"] = "leaf"
    elif corruption == "filter_only_parent":
        child["parent_job_id"] = ""
        filters = json.loads(child["filters_json"])
        filters["parent_job_id"] = "parent"
        child["filters_json"] = json.dumps(filters)
    elif corruption == "child_backlink":
        parent["child_job_ids_json"] = '["different-child"]'
    elif corruption == "missing_parent":
        rows.pop("parent")
    else:
        target = child if corruption == "parent_filter_conflict" else parent
        filters = json.loads(target["filters_json"])
        if corruption == "parent_identity":
            filters["record_refs"] = [{**REF, "institute_id": "OTHER-HOSPITAL"}]
        elif corruption == "parent_source":
            filters["clinical_source"] = {"id": "unknown"}
        else:
            filters["parent_job_id"] = "unrelated"
        target["filters_json"] = json.dumps(filters)
    with pytest.raises(ValueError, match="retry_lineage"):
        resolve_material_job_id(child, rows.get)


def test_retry_record_scope_cannot_add_another_institution():
    from app.services.material_job_lineage import resolve_material_job_id
    original = job("original")
    followup = retry(original)
    filters = json.loads(followup["filters_json"])
    filters["record_refs"] = [{**REF, "institute_id": "OTHER-HOSPITAL"}]
    followup["filters_json"] = json.dumps(filters)
    with pytest.raises(ValueError, match="retry_lineage"):
        resolve_material_job_id(followup, {original["id"]: original}.get)


def test_processing_job_uses_exact_claim_filters_for_source_hash():
    from app.services.material_job_lineage import resolve_material_job_id
    original = job("original")
    followup = retry(original)
    def processing(row):
        value = {**row, "_claim_filters_json": row["filters_json"], "filters": json.loads(row["filters_json"])}
        value.pop("filters_json")
        value["filters"].pop("_lx0609_attempt_id")
        return value
    assert resolve_material_job_id(processing(followup), lambda _: processing(original)) == "original"


@pytest.mark.parametrize("failure", ["forged_material", "wrong_case", "wrong_owner"])
def test_history_rejects_unrelated_material_and_unauthorized_identity(saved, failure):
    rows, last = family()
    if failure == "forged_material":
        filters = json.loads(last["filters_json"])
        filters["retry_lineage"]["material_job_id"] = "unrelated"
        last["filters_json"] = json.dumps(filters)
    saved(rows.values())
    req = request({**REF, "institute_id": "OTHER"} if failure == "wrong_case" else REF,
                  actor="other-owner" if failure == "wrong_owner" else "synthetic-owner")
    expected = HTTPException if failure == "wrong_owner" else PipelineError
    with pytest.raises(expected) as caught:
        clinical_sources.source_for_saved_job(req, last["id"])
    if failure == "wrong_owner":
        assert caught.value.status_code == 403
    assert not getattr(req.state, "material_root_job_id", "")


def test_legacy_unlinked_leaf_preserves_original_material_identity():
    from app.services.material_job_lineage import resolve_material_job_id
    assert resolve_material_job_id({"id": "historical", "filters_json": "{}"}, lambda _: pytest.fail("旧leaf不追溯其他任务")) == "historical"


@pytest.mark.asyncio
async def test_retry_history_binds_original_parent_snapshot_without_live_reads(saved, monkeypatch, tmp_path):
    from app.database import clinical_connection as clinical
    from app.services import case_material_snapshot as material
    from app.services.bundles import current_view

    rows, last = family()
    saved(rows.values())
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path))
    state = {"protocol": material.PROTOCOL, "identity": list(REF.values()), "binding": "", "schema": "cdm",
             "columns": {}, "tables": {}, "queries": {}, "documents": {"documents": [{"content": "合成原轮次正文"}]}}
    with clinical.selected(clinical_sources.legacy_snapshot()):
        original = material.persist("parent", state)
    monkeypatch.setattr(current_view, "_assemble_current_documents", lambda **_: pytest.fail("历史展示不得读取当前材料"))
    req = request()
    req.state.clinical_source = clinical_sources.source_for_saved_job(req, last["id"])
    dependency = clinical_sources.bind_request(req)
    await anext(dependency)
    try:
        assert material.current()["fingerprint"] == original["fingerprint"]
        assert current_view.load_current_documents(**REF) == state["documents"]
    finally:
        await dependency.aclose()


@pytest.mark.parametrize("case", ["transferred_owner", "foreign_manager", "forged_doctor", "inactive", "unknown_account", "missing_institute", "invalid_roles"])
def test_retry_history_rechecks_persistent_actor_scope(saved, case):
    rows, last = family()
    saved(rows.values())
    actor_id = "unknown" if case == "unknown_account" else "foreign-manager" if case == "foreign_manager" else "synthetic-owner"
    with connection.SessionLocal() as session:
        actor = session.get(SysUser, "synthetic-owner")
        if case == "foreign_manager":
            actor = SysUser(id=actor_id, username=actor_id, display_name="合成他院管理者", role="qc_manager",
                            roles_json='["qc_manager"]', is_active=True)
            session.add(actor)
        if case in {"transferred_owner", "foreign_manager"}:
            actor.institute_id = "OTHER-HOSPITAL"
        elif case == "forged_doctor":
            actor.role, actor.roles_json = "viewer", '["viewer"]'
        elif case == "inactive":
            actor.is_active = False
        elif case == "missing_institute":
            actor.institute_id = None
        elif case == "invalid_roles":
            actor.roles_json = "broken"
        session.commit()
    req = request(actor=actor_id)
    req.state.current_user["roles"] = ["doctor", "super_admin"]
    with pytest.raises(HTTPException) as caught:
        clinical_sources.source_for_saved_job(req, last["id"])
    assert caught.value.status_code == 403
    assert not getattr(req.state, "material_root_job_id", "")


@pytest.mark.parametrize("own_case", [True, False, None])
def test_retry_history_doctor_uses_persistent_personal_scope(saved, monkeypatch, own_case):
    from app.services import doctor_case_scope
    rows, last = family()
    saved(rows.values())
    with connection.SessionLocal() as session:
        actor = session.get(SysUser, "synthetic-owner")
        actor.role, actor.roles_json = "doctor", '["doctor"]'
        session.commit()
    calls = []
    def resolve(actor_id, **kwargs):
        calls.append(actor_id)
        return None if own_case is None else doctor_case_scope.DoctorCaseScope(
            REF["institute_id"], "合成科室", "合成医生", (tuple(REF.values()),) if own_case else ())
    monkeypatch.setattr(doctor_case_scope, "resolve_doctor_case_scope", resolve)
    req = request()
    req.state.current_user["roles"] = ["super_admin"]
    if own_case:
        assert clinical_sources.source_for_saved_job(req, last["id"]) == clinical_sources.legacy_snapshot()
    else:
        with pytest.raises(HTTPException) as caught:
            clinical_sources.source_for_saved_job(req, last["id"])
        assert caught.value.status_code == 403
    assert calls == ["synthetic-owner"]


@pytest.mark.parametrize("roles", [["admin"], ["sync_admin"], ["super_admin"], ["qc_manager", "doctor"]])
def test_retry_history_persistent_management_scope_remains_supported(saved, monkeypatch, roles):
    from app.services import doctor_case_scope
    rows, last = family()
    saved(rows.values())
    with connection.SessionLocal() as session:
        actor = session.get(SysUser, "synthetic-owner")
        actor.role, actor.roles_json = roles[0], json.dumps(roles)
        if "qc_manager" not in roles:
            actor.institute_id = "GLOBAL"
        session.commit()
    monkeypatch.setattr(doctor_case_scope, "resolve_doctor_case_scope", lambda *a, **kw: pytest.fail("管理角色不绕入医生豁免"))
    assert clinical_sources.source_for_saved_job(request(), last["id"]) == clinical_sources.legacy_snapshot()


def test_retry_history_account_store_failure_is_safe_and_closed(saved, monkeypatch):
    from app.services import defect_rectification_service
    rows, last = family()
    saved(rows.values())
    def fail(*_args):
        raise RuntimeError("synthetic-secret-dsn")
    monkeypatch.setattr(defect_rectification_service, "_person", fail)
    with pytest.raises(HTTPException) as caught:
        clinical_sources.source_for_saved_job(request(), last["id"])
    assert caught.value.status_code == 503
    assert "synthetic-secret-dsn" not in str(caught.value)


@pytest.mark.parametrize("patient", ["P-own", "P-colleague"])
def test_retry_history_preserves_real_doctor_personal_case_gate(doctor_database, patient):
    ref = {"institute_id": "H-A", "patient_id": patient, "visit_id": "V-own" if patient == "P-own" else "V-colleague"}
    original = job("doctor-original")
    original["created_by"] = "doctor-a"
    filters = json.loads(original["filters_json"])
    filters["record_refs"] = [ref]
    original["filters_json"] = json.dumps(filters)
    followup = retry(original)
    with doctor_database() as session:
        session.execute(text("CREATE TABLE qc.custom_qc_batch_jobs (id TEXT PRIMARY KEY,created_by TEXT,filters_json TEXT,parent_job_id TEXT,job_kind TEXT,child_job_ids_json TEXT)"))
        session.execute(text("INSERT INTO qc.custom_qc_batch_jobs VALUES (:id,:created_by,:filters_json,:parent_job_id,:job_kind,:child_job_ids_json)"), [original, followup])
        session.commit()
    req = request(ref, actor="doctor-a")
    req.state.current_user["roles"] = ["super_admin"]  # 请求角色不能绕过持久医生的本人范围。
    if patient == "P-own":
        clinical_sources.source_for_saved_job(req, followup["id"])
        assert req.state.material_root_job_id == original["id"]
    else:
        with pytest.raises(HTTPException) as caught:
            clinical_sources.source_for_saved_job(req, followup["id"])
        assert caught.value.status_code == 403
