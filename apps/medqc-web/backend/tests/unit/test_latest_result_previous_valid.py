"""最近一次取材失败后，用户显式查看上一次有效结果。

合成场景（只用隔离 SQLite 与临时冻结材料目录）：同一病例先有一轮带结果信封的
旧任务（整批状态 failed），后有一轮对该病例取材失败、零项的新任务。

- 默认视图仍选最新轮：可核验时如实返回“取材失败”，不换读旧轮；
- 用户点击后按 result_view=previous_valid 读旧轮，返回只读、原轮 job_id、
  record_ref 与完成时间；锚点过期返回 409；
- 需东华来源证明的账号：最新轮无冻结材料，默认视图保持 403；历史视图只返回
  能用旧轮自身冻结材料核验的结果；旧轮也不能核验时 404，不透露任务信息。
"""

import hashlib
import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database import clinical_connection
from app.routers import qc_sichuan
from app.services import case_material_snapshot, custom_qc_workspace_service as workspace
from app.services import saved_result_access as access
from app.services.case_identity import CaseRef
from app.services.cdm_publication_evidence import target_hash
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result
from test_luxian_0609_canonical_result_delivery import _published_pilot_item_for_read_boundary

IDENTITY = ("机构号", "patient-1", "visit-1")
REF = dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY))
OTHER_REF = {"institute_id": "机构号", "patient_id": "patient-2", "visit_id": "visit-2"}
RULE = "LX0609-09-01-01"
URL = "/api/v1/qc/sichuan/workspace/records/visit-1/latest-result"
EPOCH = "7cecd40f-047d-4458-b964-8741d0ea7399"


def _capture_failure(ref):
    return {**ref, "record_id": ref["visit_id"], "record_key": CaseRef(**ref).as_key(),
            "error_phase": "material_capture", "reason_code": "material_capture_failed",
            "error": "material_capture_failed", "retryable": False}


@pytest.fixture
def scene(monkeypatch, tmp_path):
    engine = sa.create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    meta = sa.MetaData()
    jobs = sa.Table("jobs", meta, *[sa.Column(key, sa.Text) for key in (
        "id", "parent_job_id", "created_by", "job_kind", "child_job_ids_json", "status", "filters_json",
        "created_at", "finished_at", "record_ids_json", "items_json", "summary_json", "failed_records_json")])
    envelopes = workspace._record_result_envelopes_table().to_metadata(meta, schema=None)
    meta.create_all(engine)
    service = object.__new__(workspace.CustomQCWorkspaceService)
    service._batch_job_table, service._record_result_envelope_table = jobs, envelopes
    monkeypatch.setattr(workspace, "_session", lambda: Session(engine))
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: service)
    account = {"scope": "机构号"}
    monkeypatch.setattr(access, "saved_result_institute_scope", lambda actor: account["scope"])
    binding = "cdm-read-v1:" + hashlib.sha256(json.dumps(["test", 5432, "cdm", "reader", "cdm"]).encode()).hexdigest()
    source = {"id": "independent_cdm", "binding": binding, "url": "postgresql://reader@test:5432/cdm"}
    monkeypatch.setattr(case_material_snapshot, "storage_root", lambda: tmp_path)

    def filters(*refs, frozen_source=source):
        return json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                           "clinical_source": frozen_source, "record_refs": list(refs),
                           "scoped_customer_rule_ids": [RULE]}, ensure_ascii=False)

    def old_job(job_id="job-old", finished="2026-10-02T08:00:00", frozen_source=source):
        # 整批 failed（同批另一病例失败），但本病例有独立保存的结果信封。
        row = {"id": job_id, "created_by": "someone-else", "status": "failed", "job_kind": "leaf",
               "created_at": "2026-10-01T08:00:00", "finished_at": finished,
               "record_ids_json": json.dumps(["visit-1", "visit-2"]),
               "filters_json": filters(REF, OTHER_REF, frozen_source=frozen_source)}
        with Session(engine) as session:
            session.execute(jobs.insert().values(**row))
            # 信封按病例写入：夹具只为本病例写，写入合同按单病例范围校验。
            CanonicalResultStore(envelopes).replace_for_job(
                session, job_row={**row, "filters_json": filters(REF, frozen_source=frozen_source)},
                items=[{**_published_pilot_item_for_read_boundary(RULE), **REF}],
                now=datetime(2026, 10, 2), projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test"),
                projection_key="test")
            session.commit()

    def capture_failed_job(job_id, finished, *, has_rule_results=False):
        # 同批另一病例有结果；本病例取材失败、零项。
        row = {"id": job_id, "created_by": "someone-else", "status": "failed", "job_kind": "leaf",
               "created_at": finished, "finished_at": finished,
               "record_ids_json": json.dumps(["visit-1", "visit-2"]), "filters_json": filters(REF, OTHER_REF),
               "items_json": json.dumps([{**_published_pilot_item_for_read_boundary(RULE), **OTHER_REF,
                                          "record_id": "visit-2"}], ensure_ascii=False),
               "failed_records_json": json.dumps([_capture_failure(REF)], ensure_ascii=False),
               "summary_json": json.dumps({
                   "material_failure": {"code": "material_capture_failed", "stage": "material_capture"},
                   "material_failed_record_count": 1,
                   **({"rule_results": []} if has_rule_results else {}),
               })}
        with Session(engine) as session:
            session.execute(jobs.insert().values(**row))
            session.commit()

    def prove(job_id, snapshot_binding=binding):
        key = target_hash(REF)
        entry = {"status": "receipt_verified", "target_key_hash": key,
                 "receipt": {"source_epoch": EPOCH, "target_key_hash": key},
                 "operation": {"source_epoch": EPOCH, "interface_name": "web.discharge_record"}}
        with clinical_connection.selected({**source, "binding": snapshot_binding}):
            case_material_snapshot.persist(job_id, {"protocol": case_material_snapshot.PROTOCOL,
                "identity": list(IDENTITY), "schema": "cdm", "binding": snapshot_binding,
                "automatic_material": {"publication": {"status": "metadata_available",
                                                       "rows": {"discharge_record": [entry]}}}})

    def update_new(**values):
        with Session(engine) as session:
            session.execute(jobs.update().where(jobs.c.id == "job-new").values(**values))
            session.commit()

    app = FastAPI()
    app.include_router(qc_sichuan.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "viewer", "roles": ["qc_manager"]}
    with TestClient(app) as client:
        yield type("Scene", (), dict(client=client, account=account, old_job=staticmethod(old_job),
                                     capture_failed_job=staticmethod(capture_failed_job), prove=staticmethod(prove),
                                     update_new=staticmethod(update_new), service=service, source=source))
    engine.dispose()


def test_default_view_reports_verified_capture_failure_then_user_opens_previous_valid(scene):
    scene.old_job()
    scene.prove("job-old")
    scene.capture_failed_job("job-new", "2026-10-05T08:00:00")

    latest = scene.client.get(URL, params=REF)
    assert latest.status_code == 200, latest.text
    data = latest.json()["data"]
    assert (data["state"], data["reason_code"], data["job_id"]) == ("technical_error", "material_capture_failed", "job-new")
    assert data["items"] == [] and data["result_rule_count"] == 0
    assert "result_view" not in data  # 默认视图不换读旧轮

    previous = scene.client.get(URL, params={**REF, "result_view": "previous_valid", "anchor_job_id": "job-new"})
    assert previous.status_code == 200, previous.text
    old = previous.json()["data"]
    assert old["result_view"] == "previous_valid" and old["read_only"] is True
    assert old["state"] == "ready" and old["job_id"] == "job-old"
    assert old["record_ref"].startswith("rec_")
    assert old["completed_at"].startswith("2026-10-02")
    assert [item["rule_id"] for item in old["items"]] == [RULE]
    assert not {"patient_id", "visit_id", "institute_id"} & set(old["items"][0])


def test_previous_valid_rejects_stale_or_wrong_anchor(scene):
    scene.old_job()
    scene.capture_failed_job("job-new", "2026-10-05T08:00:00")
    params = {**REF, "result_view": "previous_valid"}
    # 锚点不是当前最新轮。
    assert scene.client.get(URL, params={**params, "anchor_job_id": "job-old"}).status_code == 409
    # 用户查看期间出现更新的一轮：要求刷新，不静默读其他轮。
    scene.capture_failed_job("job-newer", "2026-10-06T08:00:00")
    assert scene.client.get(URL, params={**params, "anchor_job_id": "job-new"}).status_code == 409
    # 锚点参数只属于历史视图。
    assert scene.client.get(URL, params={**REF, "anchor_job_id": "job-newer"}).status_code == 422
    assert scene.client.get(URL, params={**REF, "result_view": "other"}).status_code == 422


def test_previous_valid_skips_older_capture_failures_and_reports_none_when_absent(scene):
    scene.capture_failed_job("job-first", "2026-10-01T08:00:00")
    scene.capture_failed_job("job-new", "2026-10-05T08:00:00")
    response = scene.client.get(URL, params={**REF, "result_view": "previous_valid", "anchor_job_id": "job-new"})
    assert response.status_code == 404
    assert "job-first" not in response.text


def test_source_proof_account_keeps_403_and_only_sees_history_provable_by_its_own_material(scene):
    scene.account["scope"] = "泸县人民医院"  # 需东华来源证明
    scene.old_job()
    scene.capture_failed_job("job-new", "2026-10-05T08:00:00")
    history = {**REF, "result_view": "previous_valid"}

    # 最新轮没有冻结材料：归属无法核验，默认视图保持 403。
    assert scene.client.get(URL, params=REF).status_code == 403
    # 带锚点也不能绕过最新轮的归属核验。
    assert scene.client.get(URL, params={**history, "anchor_job_id": "job-new"}).status_code == 403

    # 反例：旧轮同样拿不出可核验的冻结材料 -> 404，不透露任务状态。
    denied = scene.client.get(URL, params=history)
    assert denied.status_code == 404
    assert "job-old" not in denied.text and "job-new" not in denied.text

    # 旧轮自身冻结材料可证明归属 -> 返回旧轮只读结果。
    scene.prove("job-old")
    allowed = scene.client.get(URL, params=history)
    assert allowed.status_code == 200, allowed.text
    data = allowed.json()["data"]
    assert (data["job_id"], data["result_view"], data["read_only"]) == ("job-old", "previous_valid", True)
    assert data["completed_at"].startswith("2026-10-02")
    assert [item["rule_id"] for item in data["items"]] == [RULE]

    # 账号换到其他机构：账号级授权先拒绝，历史视图同样 403。
    scene.account["scope"] = "另一家医院"
    assert scene.client.get(URL, params=history).status_code == 403


def test_capture_failure_with_rule_identity_is_not_reported_as_capture_failure(scene):
    """失败记录带规则身份时是规则级失败，不是“取材阶段零项失败”，沿用既有部分结果合同。"""
    scene.old_job()
    scene.capture_failed_job("job-new", "2026-10-05T08:00:00", has_rule_results=True)
    from sqlalchemy import update
    service = qc_sichuan._sichuan_workspace_service()
    jobs = service._batch_job_table
    with workspace._session() as session:
        session.execute(update(jobs).where(jobs.c.id == "job-new").values(
            failed_records_json=json.dumps([{**_capture_failure(REF), "rule_id": RULE}], ensure_ascii=False)))
        session.commit()
    data = scene.client.get(URL, params=REF).json()["data"]
    assert data["job_id"] == "job-new" and data["reason_code"] != "material_capture_failed"
    assert data["items"] == [] and data.get("failed_rule_ids") == [RULE]
    # 不是已核实的取材失败，不能作为历史视图锚点。
    response = scene.client.get(URL, params={**REF, "result_view": "previous_valid", "anchor_job_id": "job-new"})
    assert response.status_code == 409


@pytest.mark.parametrize(("mutations", "expected"), [
    ({"items_json": "{BROKEN"}, "saved_partial_result_invalid"),
    ({"items_json": "null"}, "saved_partial_result_invalid"),
    ({"summary_json": "{BROKEN"}, "saved_partial_result_invalid"),
    ({"failed_records_json": "null"}, "saved_partial_result_invalid"),
    ({"failed_records_json": json.dumps([{
        **_capture_failure(REF), "reason_code": "material_source_contract_incomplete",
        "material_failure_stage": "projection",
    }])}, "saved_partial_result_invalid"),
    ({"failed_records_json": json.dumps([_capture_failure(OTHER_REF)])}, "saved_partial_result_invalid"),
    ({"failed_records_json": json.dumps([{**_capture_failure(REF), "reason_code": "material_projection_failed"}])},
     "saved_partial_result_invalid"),
    *[({"failed_records_json": json.dumps([{**_capture_failure(REF), "reason_code": reason}])}, reason)
      for reason in ("material_capture_failed", "material_source_contract_incomplete",
                     "material_source_contract_unavailable", "material_source_unavailable",
                     "material_publication_identity_conflict")],
])
def test_partial_failure_classification_matches_detail_and_batch(scene, mutations, expected):
    scene.old_job()
    scene.prove("job-old")
    scene.capture_failed_job("job-new", "2026-10-05T08:00:00")
    scene.update_new(**mutations)

    single = scene.client.get(URL, params=REF).json()["data"]
    bulk = scene.service.build_latest_luxian_0609_record_result_dtos(record_refs=[REF])[IDENTITY]
    assert single["state"] == bulk["state"] == "technical_error"
    assert single["reason_code"] == bulk["reason_code"] == expected
    previous = scene.client.get(URL, params={**REF, "result_view": "previous_valid", "anchor_job_id": "job-new"})
    if expected == "saved_partial_result_invalid":
        assert "failure_stage" not in single and "failure_stage" not in bulk
        assert previous.status_code == 409
    else:
        assert single["job_id"] == bulk["job_id"] == "job-new"
        expected_stage = "material_preparation" if expected == "material_source_contract_incomplete" else "material_capture"
        assert single["failure_stage"] == bulk["failure_stage"] == expected_stage
        assert previous.status_code == 200, previous.text


def test_history_respects_clinical_source_and_skips_newer_result_without_original(scene):
    old_source = {**scene.source, "url": "postgresql://reader@older:5432/cdm"}
    old_source["binding"] = "cdm-read-v1:" + hashlib.sha256(
        json.dumps(["older", 5432, "cdm", "reader", "cdm"]).encode()
    ).hexdigest()
    scene.old_job("job-other-source", "2026-10-04T08:00:00", frozen_source=old_source)
    scene.prove("job-other-source", snapshot_binding=old_source["binding"])
    scene.old_job()
    scene.prove("job-old")
    scene.old_job("job-without-original", "2026-10-03T08:00:00")
    scene.capture_failed_job("job-new", "2026-10-05T08:00:00")
    with clinical_connection.selected(scene.source):
        previous = scene.service.get_previous_valid_luxian_0609_record_result(
            institute_id=REF["institute_id"], patient_id=REF["patient_id"], visit_id=REF["visit_id"],
            anchor_job_id="job-new",
        )
    assert previous["job_id"] == "job-old"


def test_unanchored_history_does_not_relabel_current_ready_result(scene):
    scene.old_job()
    scene.prove("job-old")
    assert scene.client.get(URL, params=REF).json()["data"]["job_id"] == "job-old"
    response = scene.client.get(URL, params={**REF, "result_view": "previous_valid"})
    assert response.status_code == 404


@pytest.mark.parametrize("needs_proof", [True, False])
def test_history_generation_conflict_requires_authorized_contenders(scene, needs_proof):
    if needs_proof:
        scene.account["scope"] = "泸县人民医院"
    scene.old_job("job-a")
    scene.old_job("job-b")
    scene.capture_failed_job("job-new", "2026-10-05T08:00:00")
    scene.prove("job-a")
    params = {**REF, "result_view": "previous_valid"}
    if needs_proof:
        # 另一轮没有可核验归属，仅一轮可见，不能泄露隐藏冲突。
        available = scene.client.get(URL, params=params)
        assert available.status_code == 200, available.text
        assert available.json()["data"]["job_id"] == "job-a"
    scene.prove("job-b")
    conflict = scene.client.get(URL, params=params)
    assert conflict.status_code == 409, conflict.text
    assert "完成时间相同" in conflict.text
    assert all(job_id not in conflict.text for job_id in ("job-a", "job-b", "job-new"))


def test_history_generation_tie_ignores_round_with_no_valid_result(scene):
    scene.old_job("job-a")
    scene.capture_failed_job("job-empty", "2026-10-02T08:00:00")
    scene.prove("job-a")
    # 摘要有冻结快照，仍没有可交付的历史结果。创建时间也设为同一代。
    jobs = scene.service._batch_job_table
    with workspace._session() as session:
        session.execute(jobs.update().where(jobs.c.id == "job-empty").values(created_at="2026-10-01T08:00:00"))
        session.commit()
    scene.prove("job-empty")
    scene.capture_failed_job("job-new", "2026-10-05T08:00:00")
    response = scene.client.get(URL, params={**REF, "result_view": "previous_valid", "anchor_job_id": "job-new"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["job_id"] == "job-a"
