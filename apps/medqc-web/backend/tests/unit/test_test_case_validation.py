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

def test_persist_conflict_and_append_review(store):
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
    with pytest.raises(ValueError, match="缺少执行版本"):
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


def _pin(engine, table, value):
    with engine.begin() as c:
        raw = json.loads(c.execute(select(table.c.raw_payload_json).where(table.c.id == "case")).scalar_one())
        c.execute(table.update().where(table.c.id == "case").values(
            raw_payload_json=json.dumps({**raw, "evaluation_as_of_date": value})))


def test_accept_requires_pinned_evaluation_date(store):
    service, engine, table = store
    rows = [{**ANSWER, "actual_status": "non_compliant", "comparison": "same"}]
    version = {"lx0609_task_runtime": {"implementation": {"kind": "process"}}}
    service.save_answers("case", 0, [ANSWER], "u")
    # 历史病例未固定评价时间点：可记录不通过，不能通过。
    legacy = service.begin("case", 1, "u")
    assert legacy["evaluation_as_of_date"] is None
    service.bind("case", legacy["id"], "u", "job", version)
    with pytest.raises(ValueError, match="未固定评价时间点"):
        service.review("case", legacy["id"], "u", "accepted", "已核对", rows)
    service.review("case", legacy["id"], "u", "rejected", "评价时间点未固定", rows)
    # 固定后的新运行记录该时间点，可以通过。
    _pin(engine, table, "2026-07-05")
    assert service.read("case")["evaluation_as_of_date"] == "2026-07-05"
    run = service.begin("case", 1, "u")
    assert run["evaluation_as_of_date"] == "2026-07-05"
    service.bind("case", run["id"], "u", "job2", version)
    service.review("case", run["id"], "u", "accepted", "证据与建议已核对", rows)


def test_record_frozen_dates_override_only_matching_running_records():
    from app.services.case_identity import CaseRef
    from app.services.luxian_0609.evaluation_horizon import build_record_evaluation_horizon_snapshot
    base = {"admission_datetime": "2026-07-01T08:00:00", "institute_id": "CUSTOMER_TEST", "patient_id": "P"}
    records = [
        {**base, "record_id": "V1", "visit_id": "V1", "scope": "running"},
        {**base, "record_id": "V2", "visit_id": "V2", "scope": "running"},
        {**base, "record_id": "V3", "visit_id": "V3", "scope": "final", "discharge_datetime": "2026-07-03T10:00:00"},
    ]
    pinned = {CaseRef("CUSTOMER_TEST", "P", v).as_key(): "2026-07-05" for v in ("V1", "V3")}
    for task_date in ("2026-09-29", "2026-10-06"):
        by_id = {s["record_id"]: s for s in build_record_evaluation_horizon_snapshot(
            records, task_frozen_date=task_date, record_frozen_dates=pinned)}
        assert by_id["V1"]["evaluation_horizon"] == "2026-07-05"  # 固定：不随运行日期变化
        assert by_id["V2"]["evaluation_horizon"] == task_date  # 未固定：沿用任务当天
        assert by_id["V3"]["evaluation_horizon"] == "2026-07-03"  # 终末病历仍以出院为终点


def test_create_rejects_evaluation_date_before_admission():
    from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
    service = object.__new__(CustomQCSamplePoolService)
    payload = {"basic_info": {"admission_time": "2026-07-01 08:00:00"}, "evaluation_as_of_date": "2026-06-30",
               "documents": [{"document_type": "admission_record", "title": "入院记录", "content": "测试"}]}
    with pytest.raises(ValueError, match="不能早于入院日期"):
        service.create_customer_test_record(payload=payload, created_by="u")


def test_sample_list_does_not_publish_private_validation_materials():
    from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
    row = {"raw_payload_json": json.dumps({"golden_answers": [ANSWER],
        "rule_validation_materials": {"private": "原文"}, "rule_validation_sessions": {"source": "原文"},
        "rule_validation": {"runs": [{"created_by": "other"}]}})}
    item = CustomQCSamplePoolService._row_to_item(None, row)
    assert item["raw_payload"] == {"golden_answers": [ANSWER]}
