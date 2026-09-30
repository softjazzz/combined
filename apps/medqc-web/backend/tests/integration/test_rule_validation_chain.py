"""规则验收全链路：两个测试病例预期→真实Worker→正式API比较→逐例复核→结论→批准，无真实模型。"""
import json

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.test_luxian_0609_all_rules_three_entry_acceptance import (
    _install_sample_pool_sqlite, _create_ready_sample_pool,
    _install_evidence_fixture, _settings, _wire_production_entry, _api_app,
    _wait_for_terminal_job, _RECORD_B,
)
from tests.integration import test_luxian_0609_all_rules_three_entry_acceptance as chain

from app.routers import rule_validation as rule_validation_api
from app.services import rule_validation as rule_validation_module
from app.services import sichuan_qc_service
from app.services.custom_qc_sample_pool_service import CUSTOMER_TEST_POOL_ID

_isolated_database = chain._isolated_database
RULE = "LX0609-06-01-04"


def test_rule_centric_validation_to_release_sheet(monkeypatch, _isolated_database):
    engine, workspace = _isolated_database
    pool_service = _install_sample_pool_sqlite(monkeypatch, engine)
    old_pool, item_a = _create_ready_sample_pool(engine, pool_service)
    items = pool_service._item_table
    with engine.begin() as c:
        c.execute(sa.update(pool_service._pool_table).where(pool_service._pool_table.c.id == old_pool)
                  .values(id=CUSTOMER_TEST_POOL_ID, scene="running"))
        row = dict(c.execute(sa.select(items).where(items.c.id == item_a)).mappings().one())
        pinned = json.dumps({"case_title": "合成无CT病例", "evaluation_as_of_date": "2026-07-05"})
        c.execute(sa.update(items).where(items.c.id == item_a).values(pool_id=CUSTOMER_TEST_POOL_ID, raw_payload_json=pinned))
        c.execute(items.insert().values(**{**row, "id": "case-b", "row_no": 2, "pool_id": CUSTOMER_TEST_POOL_ID,
                                           "raw_payload_json": pinned,
                                           **{"matched_" + k: v for k, v in _RECORD_B.items()}}))
    rule_validation_module._tables.cache_clear()
    monkeypatch.setattr(rule_validation_module.pools, "engine", engine)
    _install_evidence_fixture(monkeypatch, consultation_row=False)
    service = sichuan_qc_service.SichuanQCService({"provider_code": "isolated", "model": "no-model", "allow_mock_when_unconfigured": False})
    _wire_production_entry(monkeypatch, workspace, pool_service, _settings(), service)

    async def no_model(*args, **kwargs):
        raise AssertionError("合成无CT病例不应调用模型，更不得传入预期答案")
    monkeypatch.setattr(sichuan_qc_service.SichuanQCLLMClient, "generate", no_model)

    # 该CT规则在目录中已上线；这里只借用其执行链，视图中按待验收规则走完整流程。
    def pending_catalog():
        catalog = rule_validation_module.rule_catalog()
        return {**catalog, RULE: {**catalog[RULE], "release_scope": "acceptance_only"}}
    monkeypatch.setattr(rule_validation_api, "_service",
                        lambda: rule_validation_module.RuleValidationService(catalog=pending_catalog))
    app = _api_app(service)
    app.include_router(rule_validation_api.router)
    base = f"/api/v1/qc/rule-validation/rules/{RULE}"
    with TestClient(app) as client:
        listed = client.get("/api/v1/qc/rule-validation/rules")
        assert listed.status_code == 200, listed.text
        assert any(r["rule_id"] == RULE and r["stage"] == "preparing" for r in listed.json()["data"]["items"])
        for item_id in (item_a, "case-b"):
            saved = client.put(f"{base}/cases/{item_id}", json={
                "revision": 0, "expected_status": "not_applicable", "human_reason": "人工基线：无CT/MRI检查", "purpose": "acceptance"})
            assert saved.status_code == 200, saved.text
        assert client.get(base).json()["data"]["stage"] == "ready_to_run"

        started = client.post(f"{base}/runs", json={})
        assert started.status_code == 200, started.text
        ids = started.json()["data"]
        job = _wait_for_terminal_job(workspace, ids["job_id"])
        assert job["status"] == "completed", job.get("error_message")
        filters = json.dumps(job["filters"], ensure_ascii=False)
        assert "golden_answers" not in filters and "人工基线" not in filters
        assert sorted(job["filters"]["selected_sample_item_ids"]) == sorted([item_a, "case-b"])

        run = client.get(f"/api/v1/qc/rule-validation/runs/{ids['run_id']}").json()["data"]
        assert {r["item_id"]: r["comparison"] for r in run["rows"]} == {item_a: "same", "case-b": "same"}
        # 逐例核对所需结果为客户安全投影：有结论/建议，不含病例坐标
        assert all(r["result"]["status"] == "not_applicable" for r in run["rows"])
        assert not any(k in r["result"] for r in run["rows"] for k in ("visit_id", "patient_id", "record_ref"))
        assert client.get(base).json()["data"]["stage"] == "reviewing"

        early = client.post(f"{base}/conclusion", json={"run_id": ids["run_id"], "decision": "accepted", "note": "通过", "gap_ack": "x"})
        assert early.status_code == 422 and "未逐例确认" in early.json()["detail"]
        for item_id in (item_a, "case-b"):
            reviewed = client.post(f"/api/v1/qc/rule-validation/runs/{ids['run_id']}/cases/{item_id}/reviews",
                                   json={"decision": "confirmed", "note": "无CT事件，结论与建议恰当"})
            assert reviewed.status_code == 200, reviewed.text
        concluded = client.post(f"{base}/conclusion", json={
            "run_id": ids["run_id"], "decision": "accepted", "note": "两例均核对", "gap_ack": "合规、不合规、资料不足待补真实病例"})
        assert concluded.status_code == 200, concluded.text
        approved = client.post(f"{base}/approval", json={"decision": "approved", "note": "开发环境试点批准"})
        assert approved.status_code == 200, approved.text
        sheet = approved.json()["data"]["payload"]
        assert sheet["run"]["job_id"] == ids["job_id"]
        assert sheet["version"]["development_version"] is True  # 本地进程版本须标注开发版本
        detail = client.get(base).json()["data"]
        assert detail["stage"] == "approved_pending_release"
        assert [e["kind"] for e in detail["events"]] == ["case_review", "case_review", "conclusion", "approval"]
        assert all("result" not in e["payload"].get("comparison", {}) for e in detail["events"])

    # 新连接核对持久化
    with Session(engine) as session:
        kinds = session.execute(sa.select(rule_validation_module._tables()[1].c.kind)).scalars().all()
    assert sorted(kinds) == ["approval", "case_review", "case_review", "conclusion"]
