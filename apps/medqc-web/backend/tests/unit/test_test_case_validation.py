import json
from copy import deepcopy

import pytest
from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.services.test_case_validation import TestCaseValidationService as ValidationService, ValidationConflict, compare
from app.services.custom_qc_sample_pool_service import CUSTOMER_TEST_POOL_ID
from app.routers import qc_sample_pools as api, qc_sichuan

ANSWER = {"qc_point_id": "LX0609-01-01-01", "expected_status": "non_compliant",
          "human_reason": "入院记录26小时后完成", "trigger_facts": ["26小时"], "evidence_keywords": ["入院记录"]}

@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'validation.db'}")
    table = Table("samples", MetaData(), Column("id", String, primary_key=True), Column("pool_id", String),
        Column("raw_payload_json", Text), *[Column("matched_" + k, String) for k in ("institute_id", "patient_id", "visit_id")])
    table.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(table.insert().values(id="case", pool_id=CUSTOMER_TEST_POOL_ID, raw_payload_json='{"other": "keep"}',
                                     matched_institute_id="TEST", matched_patient_id="P", matched_visit_id="V"))
    yield ValidationService(table, sessionmaker(bind=engine)), engine, table
    engine.dispose()

def test_persist_freeze_conflict_and_append_review(store):
    service, engine, table = store
    service.save_answers("case", 0, [ANSWER], "u")
    with engine.connect() as c:
        raw = json.loads(c.execute(select(table.c.raw_payload_json)).scalar_one())
    assert raw["golden_answers"] == [ANSWER] and raw["other"] == "keep"
    run = service.begin("case", 1, "u")
    service.bind("case", run["id"], "u", "job")
    service.save_answers("case", 1, [{**ANSWER, "expected_status": "compliant"}], "u")
    assert service.read("case")["runs"][0]["answers"] == [ANSWER]
    with pytest.raises(ValidationConflict):
        service.save_answers("case", 1, [ANSWER], "u")
    rows = compare(run, {"status": "completed", "items": [{"rule_id": ANSWER["qc_point_id"], "status": "non_compliant"}]})
    service.review("case", run["id"], "u", "accepted", "证据定位和建议已核对", rows)
    service.review("case", run["id"], "u", "rejected", "二次发现证据错误", rows)
    assert len(service.read("case")["runs"][0]["reviews"]) == 2
    with pytest.raises(LookupError):
        service.review("case", run["id"], "other", "accepted", "检查", rows)

@pytest.mark.parametrize("status,items,expected", [
    ("running", [], "pending"), ("failed", [], "failed"), ("completed", [], "missing"),
    ("completed", [{"rule_id": ANSWER["qc_point_id"], "status": "compliant"}], "different"),
    ("completed", [{"rule_id": ANSWER["qc_point_id"], "status": "non_compliant"}] * 2, "ambiguous"),
])
def test_no_false_pass(status, items, expected):
    source = {"status": status, "items": items}
    before = deepcopy(source)
    assert compare({"answers": [ANSWER]}, source)[0]["comparison"] == expected
    assert source == before

def test_legacy_answer_and_empty_reason_rejected(store):
    service, _, _ = store
    for patch in ({"qc_point_id": "LX0609-001"}, {"human_reason": " "}, {"expected_status": "uncertain"}):
        with pytest.raises(ValueError):
            service.save_answers("case", 0, [{**ANSWER, **patch}], "u")

@pytest.mark.asyncio
async def test_router_without_answer_leak_reads_formal_endpoint(store, monkeypatch):
    service, _, _ = store
    monkeypatch.setattr(api, "_test_validation_service", lambda: service)
    request = Request({"type": "http", "headers": [], "method": "POST", "path": "/"})
    user = {"id": "u"}
    await api.save_test_validation(request, "case", api.TestValidationAnswersRequest(revision=0, answers=[ANSWER]), user)
    captured = []
    async def run(request, pool_id, payload, current_user, activation):
        captured.append(payload.model_dump())
        return {"data": {"job_id": "job"}}
    monkeypatch.setattr(api, "run_sample_pool_intrinsic_validation", run)
    created = await api.run_test_validation(request, "case", api.TestValidationRunRequest(revision=1), user, {})
    run_id = created["data"]["run_id"]
    assert captured[0]["selected_rule_ids"] == [ANSWER["qc_point_id"]]
    assert "golden_answers" not in json.dumps(captured) and ANSWER["human_reason"] not in json.dumps(captured, ensure_ascii=False)
    async def read(request, job_id, current_user):
        assert job_id == "job"
        return {"data": {"status": "completed", "items": [{"rule_id": ANSWER["qc_point_id"], "status": "non_compliant"}]}}
    monkeypatch.setattr(qc_sichuan, "get_workspace_batch_job", read)
    result = await api.get_test_validation_result(request, "case", run_id, user)
    assert result["data"]["comparisons"][0]["comparison"] == "same"
    result = await api.review_test_validation(request, "case", run_id,
        api.TestValidationReviewRequest(decision="accepted", note="已核对原文证据和建议"), user)
    assert len(result["data"]["run"]["reviews"]) == 1
    with pytest.raises(Exception) as error:
        await api.get_test_validation_result(request, "case", run_id, {"id": "other"})
    assert error.value.status_code == 404
