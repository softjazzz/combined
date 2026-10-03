"""0916 验收入口经过正式整包执行与实际保存；仅替换外部资料和模型服务。"""
import json

import sqlalchemy as sa
import pytest
from fastapi.testclient import TestClient

from app.routers import rule_validation as api
from app.services import rule_validation as validation, sichuan_qc_service
from app.services.custom_qc_sample_pool_service import CUSTOMER_TEST_POOL_ID
from app.services.luxian_0916 import batch_worker
from tests.integration import test_luxian_0609_all_rules_three_entry_acceptance as chain

_isolated_database = chain._isolated_database


@pytest.mark.parametrize("with_document", [False, True])
def test_0916_real_worker_save_read_review_without_0609_publication(monkeypatch, _isolated_database, with_document):
    engine, workspace = _isolated_database
    pools = chain._install_sample_pool_sqlite(monkeypatch, engine)
    old_pool, item_id = chain._create_ready_sample_pool(engine, pools)
    with engine.begin() as conn:
        conn.execute(sa.update(pools._pool_table).where(pools._pool_table.c.id == old_pool)
                     .values(id=CUSTOMER_TEST_POOL_ID, scene="running"))
        conn.execute(sa.update(pools._item_table).where(pools._item_table.c.id == item_id).values(
            pool_id=CUSTOMER_TEST_POOL_ID,
            raw_payload_json=json.dumps({"case_title": "0916合成无文书病例", "evaluation_as_of_date": "2026-07-05"})))
    validation._tables.cache_clear()
    monkeypatch.setattr(validation.pools, "engine", engine)
    service = sichuan_qc_service.SichuanQCService({"provider_code": "isolated", "model": "no-model"})
    chain._wire_production_entry(monkeypatch, workspace, pools, chain._settings(), service)
    # 资料获取边界为空；保留事实提取、上下文、32 条执行器、保存和读取。
    def load_bundle(scene, **kwargs):
        return {**chain._bundle(**kwargs), "source_documents": [
            {"source_table": "admission_record", "document_id": "SYN-A1"}] if with_document else []}
    monkeypatch.setattr(batch_worker, "load_luxian_0916_bundle", load_bundle)
    monkeypatch.setattr(batch_worker, "build_programmatic_evidence_payload",
                        lambda **kwargs: {"programmatic_timeline": {"documents": {
                            "admission_record": [{"document_id": "SYN-A1", "content": "患者因咳嗽入院。既往住院情况未提供。",
                                                  "authored_at": "2026-07-01 10:00:00"}] if with_document else []}}})
    monkeypatch.setattr(batch_worker, "load_disease_change_015016_facts", lambda **kwargs: {
        "event_facts": {"disease_changes": []},
        "event_source_state_by_rule": {"LX0916-015": "structured_complete", "LX0916-016": "structured_complete"},
        "diagnostic": {"code": "structured_disease_change_trigger_ready", "event_count": 0, "llm_call_count": 0}})
    calls = []

    async def generate(prompt, **kwargs):
        assert "独立人工预期标记" not in prompt and "golden_answers" not in prompt
        calls.append(prompt)
        return {"choices": [{"message": {"content": json.dumps({
            "semantic_facts": {}, "event_facts": {}, "document_facts": {}, "discharge_facts": {}})}}]}

    async def create_client(filters):
        return generate

    monkeypatch.setattr(batch_worker, "_build_semantic_generate", create_client)
    app = chain._api_app(service)
    app.include_router(api.router)
    rule_id = "LX0916-001"
    base = f"/api/v1/qc/rule-validation/rules/{rule_id}"
    with TestClient(app) as client:
        rules = client.get("/api/v1/qc/rule-validation/rules", params={"rule_set_key": validation.RULE_SET_0916})
        assert rules.status_code == 200, rules.text
        assert len(rules.json()["data"]["items"]) == 32
        assert all(r["publication_supported"] is False for r in rules.json()["data"]["items"])
        default_rules = client.get("/api/v1/qc/rule-validation/rules").json()["data"]["items"]
        assert all(r["rule_id"].startswith("LX0609-") for r in default_rules)
        assert client.get("/api/v1/qc/rule-validation/rules", params={"rule_set_key": "unknown"}).status_code == 422
        wrong_status = client.put(f"{base}/cases/{item_id}", json={"revision": 0, "expected_status": "data_gap",
            "human_reason": "0916不能使用0609状态编码", "purpose": "development"})
        assert wrong_status.status_code == 422
        answer = client.put(f"{base}/cases/{item_id}", json={"revision": 0, "expected_status": "data_quality_gap",
            "human_reason": "独立人工预期标记：资料源未提供入院文书和既往住院事实", "purpose": "development"})
        assert answer.status_code == 200, answer.text
        started = client.post(f"{base}/runs", json={})
        assert started.status_code == 200, started.text
        ids = started.json()["data"]
        job = chain._wait_for_terminal_job(workspace, ids["job_id"])
        assert job["status"] == "completed", (job.get("error_message"), job.get("failed_records"))
        assert len(job["items"]) == 32
        filters = job["filters"]
        assert filters["rule_set_key"] == validation.RULE_SET_0916
        assert "scoped_customer_rule_ids" not in filters
        assert "独立人工预期标记" not in json.dumps(filters, ensure_ascii=False)
        saved = next(item for item in job["items"] if item["rule_id"] == rule_id)
        detail = client.get(base)
        assert detail.status_code == 200, detail.text
        data = detail.json()["data"]
        assert data["coverage"]["counts"]["data_quality_gap"]["synthetic"] == 1
        assert "data_quality_gap" not in data["coverage"]["gaps"]
        run = data["runs"][0]
        assert run["execution_version"]["rule_set_key"] == validation.RULE_SET_0916
        assert run["scope_rule_ids"] == filters["rule_ids"]
        assert len(data["latest_run_rows"]) == 1
        row = data["latest_run_rows"][0]
        assert row["comparison"] == "same", row
        result = row["result"]
        for key in ("status", "reason_code", "findings", "suggestion", "evidence", "document_anchors"):
            assert result[key] == saved[key]
        assert result["customer_display_facts"] == saved.get("decision_facts", {})
        assert not {"patient_id", "visit_id", "diagnostics", "raw_response"} & result.keys()
        reviewed = client.post(f"/api/v1/qc/rule-validation/runs/{ids['run_id']}/cases/{item_id}/reviews",
                              json={"decision": "confirmed", "note": "仅验证无资料时的工程链路，不代表临床验收"})
        assert reviewed.status_code == 200, reviewed.text
        conclusion = client.post(f"{base}/conclusion", json={"run_id": ids["run_id"], "decision": "accepted",
            "note": "工程链路已对照", "gap_ack": "本轮仅合成资料不足病例，其余状态及同包规则需独立验证"})
        assert conclusion.status_code == 200, conclusion.text
        approved = client.post(f"{base}/approval", json={"decision": "approved", "note": "不应生成0609发布单"})
        assert approved.status_code == 422 and "不能批准上线" in approved.text
        assert len(calls) == (1 if with_document else 0)
        # 真正保存的历史结果没有被比较或复核改写。
        assert workspace.get_batch_job_for_processing(job_id=ids["job_id"])["items"] == job["items"]

        # 读取也校验原生合同，不把损坏的保存结果作为可复核结果。
        original_read = workspace.get_batch_job_for_processing
        def corrupt_read(**kwargs):
            record = original_read(**kwargs)
            record["items"] = record["items"][:-1]
            return record
        monkeypatch.setattr(workspace, "get_batch_job_for_processing", corrupt_read)
        assert client.get(base).status_code == 409
