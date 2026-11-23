"""就诊号不参与映射；必须用该任务的冻结发布证据证明来源。"""
import pytest
from fastapi import HTTPException

from app.services import case_material_snapshot, saved_result_access as access
from app.services.cdm_publication_evidence import target_hash


@pytest.mark.parametrize("visit", ["case-a", "case-b"])
@pytest.mark.parametrize("fault", ["", "epoch", "key", "interface", "unverified", "missing"])
def test_frozen_source_required(monkeypatch, visit, fault):
    identity = ("机构号", "合成患者", visit)
    keys = dict(zip(("institute_id", "patient_id", "visit_id"), identity))
    epoch = "7cecd40f-047d-4458-b964-8741d0ea7399"
    interface = "web.admission_record"
    key = target_hash(keys)
    entry = {"status": "receipt_verified", "target_key_hash": key,
             "receipt": {"target_key_hash": key, "source_epoch": epoch},
             "operation": {"source_epoch": epoch, "interface_name": interface}}
    if fault == "epoch":
        entry["receipt"]["source_epoch"] = "other"
    if fault == "key":
        entry["receipt"]["target_key_hash"] = "other"
    if fault == "interface":
        entry["operation"]["interface_name"] = "clinical.public.admission_record"
    if fault == "unverified":
        entry["status"] = "receipt_unverified"
    state = {"schema": "cdm", "binding": "cdm-read-v1:" + "a"*64, "identity": list(identity),
             "automatic_material": {"publication": {"status": "metadata_available",
                 "rows": {"admission_record": [entry]}}}}
    def load(job, ref):
        assert (job, ref) == ("job", identity)
        return None if fault == "missing" else state
    monkeypatch.setattr(case_material_snapshot, "load", load)
    if fault:
        with pytest.raises(HTTPException) as caught:
            access.require_donghua_frozen_result("job", identity, state["binding"])
        assert caught.value.status_code == 403
    else:
        access.require_donghua_frozen_result("job", identity, state["binding"])

def test_result_route_checks_selected_saved_job_before_returning_items(monkeypatch, tmp_path):
    import hashlib
    import json
    from datetime import datetime

    import sqlalchemy as sa
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from app.core.security import get_current_user
    from app.database import clinical_connection
    from app.routers import qc_sichuan
    from app.services import custom_qc_workspace_service as workspace
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result
    from test_luxian_0609_canonical_result_delivery import _published_pilot_item_for_read_boundary

    engine = sa.create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    meta = sa.MetaData()
    jobs = sa.Table("jobs", meta, *[sa.Column(key, sa.Text) for key in (
        "id", "parent_job_id", "created_by", "job_kind", "child_job_ids_json", "status", "filters_json",
        "created_at", "finished_at", "record_ids_json")])
    envelopes = workspace._record_result_envelopes_table().to_metadata(meta, schema=None)
    meta.create_all(engine)
    service = object.__new__(workspace.CustomQCWorkspaceService)
    service._batch_job_table, service._record_result_envelope_table = jobs, envelopes
    monkeypatch.setattr(workspace, "_session", lambda: Session(engine))
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: service)
    hospital = "泸县人民医院"
    monkeypatch.setattr(access, "saved_result_institute_scope", lambda actor: hospital)
    app = FastAPI()
    app.include_router(qc_sichuan.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "test", "roles": ["qc_manager"]}
    identity = ("机构号", "patient-1", "visit-1")
    ref = dict(zip(("institute_id", "patient_id", "visit_id"), identity))
    binding = "cdm-read-v1:" + hashlib.sha256(json.dumps(["test", 5432, "cdm", "reader", "cdm"]).encode()).hexdigest()
    source = {"id": "independent_cdm", "binding": binding, "url": "postgresql://reader@test:5432/cdm"}
    rule = "LX0609-09-01-01"
    filters = {"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
               "clinical_source": source, "record_refs": [ref], "scoped_customer_rule_ids": [rule]}
    job = {"id": "job", "created_by": "reviewer", "status": "completed", "job_kind": "leaf",
           "created_at": "2026-10-01", "finished_at": "2026-10-02",
           "record_ids_json": json.dumps([identity[2]]), "filters_json": json.dumps(filters)}
    with Session(engine) as session:
        session.execute(jobs.insert().values(**job))
        CanonicalResultStore(envelopes).replace_for_job(
            session, job_row=job, items=[{**_published_pilot_item_for_read_boundary(rule), **ref}],
            now=datetime(2026, 10, 2), projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test"),
            projection_key="test")
        session.commit()
    monkeypatch.setattr(case_material_snapshot, "storage_root", lambda: tmp_path)
    monkeypatch.setattr(clinical_connection, "source_binding", lambda: binding)
    url = "/api/v1/qc/sichuan/workspace/records/visit-1/latest-result"
    with TestClient(app) as client:
        assert client.get(url, params=ref).status_code == 403
        epoch = "7cecd40f-047d-4458-b964-8741d0ea7399"
        key = target_hash(ref)
        entry = {"status": "receipt_verified", "target_key_hash": key,
                 "receipt": {"source_epoch": epoch, "target_key_hash": key},
                 "operation": {"source_epoch": epoch, "interface_name": "web.discharge_record"}}
        case_material_snapshot.persist("job", {"protocol": case_material_snapshot.PROTOCOL,
            "identity": list(identity), "schema": "cdm", "binding": binding,
            "automatic_material": {"publication": {"status": "metadata_available", "rows": {"discharge_record": [entry]}}}})
        response = client.get(url, params=ref)
        assert response.status_code == 200, response.text
        assert [item["rule_id"] for item in response.json()["data"]["items"]] == [rule]
        hospital = "另一家医院"
        assert client.get(url, params=ref).status_code == 403
    engine.dispose()


def test_old_snapshot_checks_only_receipt_and_contract_in_disposable_pg(monkeypatch):
    import os

    import sqlalchemy as sa
    from app.database import clinical_connection as clinical

    url = os.getenv("PR8_DISPOSABLE_PG_URL")
    if not url:
        pytest.skip("仅使用独立合成 PG")
    target = sa.engine.make_url(url)
    assert (target.host, target.username, target.database) == ("127.0.0.1", "pr8_synthetic", "postgres")
    assert 55000 <= target.port <= 55999
    engine = sa.create_engine(url)
    identity = ("机构号", "合成患者", "旧任务")
    ref = dict(zip(("institute_id", "patient_id", "visit_id"), identity))
    digest = target_hash(ref)
    binding = "cdm-read-v1:d6426d946c655b24ec8ad3915e7441e7cb5033dd69c7397a70c7431f5a3dea08"
    state = {"schema": "cdm", "binding": binding, "identity": list(identity),
             "automatic_material": {"publication": {"status": "metadata_permission_unconfirmed", "rows": {}}},
             "tables": {"admission_record": [ref]}}
    monkeypatch.setattr(case_material_snapshot, "load", lambda *_: state)
    monkeypatch.setattr(clinical, "source_binding", lambda: binding)
    monkeypatch.setattr(clinical, "get_engine", lambda: engine)
    def rejected():
        with pytest.raises(HTTPException) as caught:
            access.require_donghua_frozen_result("job", identity, binding)
        assert caught.value.status_code == 403

    with engine.begin() as c:
        c.exec_driver_sql("CREATE SCHEMA sync_delivery")
        c.exec_driver_sql("CREATE TABLE sync_delivery.contract(interface_name text, source_epoch uuid, activation int, mapping_hash text)")
        c.exec_driver_sql("CREATE TABLE sync_delivery.receipt(interface_name text, source_epoch uuid, activation int, mapping_hash text, generation bigint, target_key_hash text)")
        c.execute(sa.text("INSERT INTO sync_delivery.contract VALUES ('web.admission_record',:epoch,1,'mapping')"),
                  {"epoch": "7cecd40f-047d-4458-b964-8741d0ea7399"})
    try:
        rejected()
        with engine.begin() as c:
            c.execute(sa.text("INSERT INTO sync_delivery.receipt SELECT *, 101, :digest FROM sync_delivery.contract"),
                      {"digest": digest})
        access.require_donghua_frozen_result("job", identity, binding)
        state["tables"]["admission_record"] = [{**ref, "patient_id": "另一患者"}]
        rejected()
        state["tables"]["admission_record"] = [ref]
        with engine.begin() as c:
            c.exec_driver_sql("UPDATE sync_delivery.contract SET activation=2")
        rejected()
        with engine.begin() as c:
            c.exec_driver_sql("UPDATE sync_delivery.contract SET activation=1")
            c.exec_driver_sql("INSERT INTO sync_delivery.receipt SELECT * FROM sync_delivery.receipt")
        rejected()
    finally:
        engine.dispose()
