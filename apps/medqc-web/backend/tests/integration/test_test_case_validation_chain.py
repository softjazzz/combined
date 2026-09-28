"""单病例预期→真实Worker→SQLite→正式API→人工验收，无真实模型。"""
import json
import pytest

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.integration.test_luxian_0609_all_rules_three_entry_acceptance import (
    _install_sample_pool_sqlite, _create_ready_sample_pool,
    _install_evidence_fixture, _settings, _wire_production_entry, _api_app,
    _wait_for_terminal_job,
)
from tests.integration import test_luxian_0609_all_rules_three_entry_acceptance as chain

from app.services import sichuan_qc_service
from app.services.qc_input_adapters import running_final_bundle_runtime
from app.services.custom_qc_sample_pool_service import CUSTOMER_TEST_POOL_ID

_isolated_database = chain._isolated_database


@pytest.mark.parametrize("rule_id", ["LX0609-03-01-04", "LX0609-06-01-04"])
def test_expected_to_real_worker_store_api_review(monkeypatch, _isolated_database, rule_id):
    engine, workspace = _isolated_database
    pool_service = _install_sample_pool_sqlite(monkeypatch, engine)
    old_pool, item_id = _create_ready_sample_pool(engine, pool_service)
    with engine.begin() as c:
        c.execute(sa.update(pool_service._pool_table).where(pool_service._pool_table.c.id == old_pool).values(id=CUSTOMER_TEST_POOL_ID))
        c.execute(sa.update(pool_service._item_table).where(pool_service._item_table.c.id == item_id).values(pool_id=CUSTOMER_TEST_POOL_ID))
    _install_evidence_fixture(monkeypatch, consultation_row=False)
    service = sichuan_qc_service.SichuanQCService({"provider_code": "isolated", "model": "no-model", "allow_mock_when_unconfigured": False})
    _wire_production_entry(monkeypatch, workspace, pool_service, _settings(), service)
    async def no_model(*args, **kwargs):
        raise AssertionError("合成无会诊病例不应调用模型，更不得传入预期答案")
    monkeypatch.setattr(sichuan_qc_service.SichuanQCLLMClient, "generate", no_model)
    monkeypatch.setattr(running_final_bundle_runtime, "load_running_final_bundle",
                        lambda **kw: chain._bundle(**{k: kw[k] for k in ("institute_id", "patient_id", "visit_id")}))
    def no_live_bundle(**kwargs):
        raise AssertionError("Worker禁止重新读取实时bundle")
    monkeypatch.setattr(chain.batch_worker, "load_running_final_bundle", no_live_bundle)
    base = f"/api/v1/qc/sample-pools/test-records/{item_id}/validation"
    answer = {"qc_point_id": rule_id, "expected_status": "not_applicable", "human_reason": "人工基线：完整来源无会诊事件"}
    with TestClient(_api_app(service)) as client:
        saved = client.put(base, json={"revision": 0, "answers": [answer]})
        assert saved.status_code == 200, saved.text
        assert client.get(base).json()["data"]["answers"][0]["human_reason"] == answer["human_reason"]
        started = client.post(base + "/runs", json={"revision": 1})
        assert started.status_code == 200, started.text
        ids = started.json()["data"]
        job = _wait_for_terminal_job(workspace, ids["job_id"])
        assert job["status"] == "completed", job.get("error_message")
        assert job["filters"]["test_validation_snapshot"]["run_id"] == ids["run_id"]
        assert "golden_answers" not in json.dumps(job["filters"])
        assert answer["human_reason"] not in json.dumps(job["filters"], ensure_ascii=False)
        path = base + "/runs/" + ids["run_id"]
        checked = client.get(path)
        assert checked.status_code == 200, checked.text
        assert checked.json()["data"]["comparisons"][0]["comparison"] == "same"
        # 修改当前答案不得影响这次已经固定的预期与比较。
        client.put(base, json={"revision": 1, "answers": [{**answer, "expected_status": "non_compliant"}]})
        assert client.get(path).json()["data"]["comparisons"][0]["expected_status"] == "not_applicable"
        reviewed = client.post(path + "/reviews", json={"decision": "accepted", "note": "核对无会诊事件且建议适当"})
        assert reviewed.status_code == 200, reviewed.text
        frozen = client.get(path).json()["data"]["run"]
        assert len(frozen["reviews"]) == 1
        assert frozen["execution_material_frozen_at"]
        assert frozen["execution_version"]["lx0609_task_runtime"] == job["filters"]["lx0609_task_runtime"]
    # 新连接核对实际持久化，不能仅依赖服务对象内存。
    with Session(engine) as session:
        payload = json.loads(session.execute(sa.select(pool_service._item_table.c.raw_payload_json).where(pool_service._item_table.c.id == item_id)).scalar_one())
        assert payload["rule_validation"]["runs"][0]["reviews"][0]["decision"] == "accepted"

    # 首次正式执行之后底层资料发生变化，恢复同一材料不得重新访问源表。
    from app.services.test_case_validation import TestCaseValidationService, ValidationConflict
    from app.services.qc_diagnostics.typed_values import decode_value
    validator = TestCaseValidationService()
    archived = payload["rule_validation_sessions"][ids["run_id"]]
    context = decode_value(archived["context"])
    parameters = {**context, **chain._RECORD_A, "source_schema": "public", "created_at": "later"}
    def forbidden_builder(**kwargs):
        raise AssertionError("历史验收材料不得重查CDM")
    restored = validator.execution_session(reference=job["filters"]["test_validation_snapshot"], job=job,
                                           builder=forbidden_builder, parameters=parameters)
    assert restored.snapshot.to_safe_dict() == decode_value(archived["inputs"])["snapshot"] | {"facts": restored.snapshot.to_safe_dict()["facts"]}
    with pytest.raises(ValidationConflict):
        validator.load_material(reference=job["filters"]["test_validation_snapshot"], job={**job, "id": "other-job"},
                                record_ref=chain._RECORD_A, scenes=["final"])
    with pytest.raises(ValidationConflict):
        validator.execution_session(reference=job["filters"]["test_validation_snapshot"], job=job,
                                    builder=forbidden_builder, parameters={**parameters, "evaluation_as_of_date": "2099-01-01"})
