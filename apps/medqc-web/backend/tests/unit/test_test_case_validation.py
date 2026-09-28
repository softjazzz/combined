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
    with pytest.raises(ValueError, match="缺少固定"):
        service.review("case", run["id"], "u", "accepted", "证据定位和建议已核对", rows)
    service.review("case", run["id"], "u", "rejected", "旧运行缺版本", rows)
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
    monkeypatch.setattr(service, "freeze_material", lambda *args: None)
    async def run(request, pool_id, payload, current_user, activation):
        captured.append(payload.model_dump())
        service.bind("case", request.state.rule_validation_reference["run_id"], "u", "job")
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
        api.TestValidationReviewRequest(decision="rejected", note="旧运行缺版本"), user)
    assert len(result["data"]["run"]["reviews"]) == 1
    with pytest.raises(Exception) as error:
        await api.get_test_validation_result(request, "case", run_id, {"id": "other"})
    assert error.value.status_code == 404


def test_material_freeze_is_bounded_private_and_immutable(store, monkeypatch):
    from app.services.qc_input_adapters import running_final_bundle_runtime
    service, _, _ = store
    source = {"institute_id": "TEST", "patient_id": "P", "visit_id": "V", "medical_text": "原始材料"}
    monkeypatch.setattr(running_final_bundle_runtime, "load_running_final_bundle", lambda **kwargs: deepcopy(source))
    service.save_answers("case", 0, [ANSWER], "u")
    run = service.begin("case", 1, "u")
    service.freeze_material("case", run["id"], "u")
    filters = {"sample_pool_id": CUSTOMER_TEST_POOL_ID, "selected_sample_item_ids": ["case"],
               "source": "manual_problem_sample_pool", "scoped_customer_rule_ids": [ANSWER["qc_point_id"]]}
    service.bind("case", run["id"], "u", "job", filters)
    reference = {"item_id": "case", "run_id": run["id"]}
    job = {"id": "job", "created_by": "u", "filters": filters}
    source["medical_text"] = "后来改写"
    loaded = service.load_material(reference=reference, job=job, record_ref=run["record_ref"], scenes=["running"])
    assert loaded[1]["medical_text"] == "原始材料"
    assert "原始材料" not in json.dumps(service.read("case"), ensure_ascii=False)
    with pytest.raises(ValidationConflict):
        service.freeze_material("case", run["id"], "u")
    for invalid in ({**job, "id": "other"}, {**job, "created_by": "other"},
                    {**job, "filters": {**filters, "scoped_customer_rule_ids": []}}):
        with pytest.raises((ValidationConflict, LookupError)):
            service.load_material(reference=reference, job=invalid, record_ref=run["record_ref"], scenes=["running"])
    run2 = service.begin("case", 1, "u")
    source["medical_text"] = "x" * (5 * 1024 * 1024)
    with pytest.raises(ValueError, match="5MiB"):
        service.freeze_material("case", run2["id"], "u")


@pytest.mark.asyncio
async def test_material_context_does_not_leak_to_other_tasks(monkeypatch):
    import asyncio
    from app.services.test_case_validation_context import validation_material_scope, build_validation_execution_session
    called = []
    monkeypatch.setattr(ValidationService, "__init__", lambda self: None)
    monkeypatch.setattr(ValidationService, "execution_session", lambda self, **kwargs: "frozen")
    def original(**kwargs):
        called.append(True)
        return "live"
    async def validation():
        with validation_material_scope({"run_id": "R"}, {"id": "J"}):
            await asyncio.sleep(0)
            assert await asyncio.to_thread(build_validation_execution_session, original) == "frozen"
        assert build_validation_execution_session(original) == "live"
    async def ordinary():
        await asyncio.sleep(0)
        assert build_validation_execution_session(original) == "live"
    await asyncio.gather(validation(), ordinary())
    assert len(called) == 2


def test_sample_list_does_not_publish_private_validation_materials():
    from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
    row = {"raw_payload_json": json.dumps({"golden_answers": [ANSWER],
        "rule_validation_materials": {"private": "原文"}, "rule_validation_sessions": {"source": "原文"},
        "rule_validation": {"runs": [{"created_by": "other"}]}})}
    item = CustomQCSamplePoolService._row_to_item(None, row)
    assert item["raw_payload"] == {"golden_answers": [ANSWER]}
