"""以规则为中心的验收服务：预期、运行、逐例复核、结论、批准与阶段推导。"""
import json

import pytest
from sqlalchemy import Column, MetaData, String, Table, Text, create_engine
from sqlalchemy.orm import sessionmaker

from app.services.custom_qc_sample_pool_service import CUSTOMER_TEST_POOL_ID
from app.services.rule_validation import (
    RuleValidationConflict,
    RuleValidationService,
    compare_cases,
    define_tables,
    derive_stage,
)

RULE = "LX0609-06-01-04"
CATALOG = {RULE: {"rule_id": RULE, "name": "CT报告未记录", "source_document": "CT/MRI检查记录",
                  "release_scope": "acceptance_only", "policy_summary": "口径"}}
RELEASE = {"lx0609_task_runtime": {"implementation": {"kind": "release", "build_id": "b1", "git_commit": "c1"}}}
PROCESS = {"lx0609_task_runtime": {"implementation": {"kind": "process", "id": "local"}}}


def _ref(visit):
    return {"institute_id": "CUSTOMER_TEST", "patient_id": "P" + visit, "visit_id": visit}


@pytest.fixture
def make_service(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rv.db'}")
    metadata = MetaData()
    items = Table("items", metadata, Column("id", String, primary_key=True), Column("pool_id", String),
                  Column("patient_name", String), Column("raw_payload_json", Text),
                  *[Column("matched_" + k, String) for k in ("institute_id", "patient_id", "visit_id")])
    runs, events = define_tables(metadata)
    metadata.create_all(engine)
    with engine.begin() as c:
        for item_id, raw in (("c1", {"case_title": "合成一", "evaluation_as_of_date": "2026-07-05"}),
                             ("c2", {"case_title": "真实副本", "evaluation_as_of_date": "2026-07-05",
                                     "source_record": {"type": "customer_source_editable_copy"}}),
                             ("c3", {"case_title": "历史病例"})):
            ref = _ref(item_id.upper())
            c.execute(items.insert().values(id=item_id, pool_id=CUSTOMER_TEST_POOL_ID, raw_payload_json=json.dumps(raw),
                                            **{"matched_" + k: v for k, v in ref.items()}))
        c.execute(items.insert().values(id="other", pool_id="other-pool", raw_payload_json="{}"))

    def build(env="development"):
        return RuleValidationService(item_table=items, runs_table=runs, events_table=events,
                                     session_factory=sessionmaker(bind=engine), catalog=lambda: CATALOG, env=env)
    yield build
    engine.dispose()


def _label(service, item_id, status="not_applicable", revision=0, purpose="acceptance"):
    return service.upsert_answer(RULE, item_id, revision=revision, expected_status=status,
                                 human_reason="人工核对", purpose=purpose, user="u")


def _job(statuses):
    return {"status": "completed", "items": [
        {"rule_id": RULE, "status": s, **_ref(v.upper())} for v, s in statuses.items()]}


def test_answers_are_per_rule_with_own_revision(make_service):
    service = make_service()
    assert _label(service, "c1")["revision"] == 1
    with pytest.raises(RuleValidationConflict):
        _label(service, "c1", revision=0)
    assert _label(service, "c1", status="non_compliant", revision=1)["revision"] == 2
    cases = service.list_cases(RULE)
    assert [(c["item_id"], c["expected_status"], c["answer_revision"]) for c in cases] == [("c1", "non_compliant", 2)]
    assert {c["item_id"] for c in service.list_candidate_cases(RULE)} == {"c2", "c3"}
    with pytest.raises(LookupError):
        _label(service, "other")  # 非自建测试池
    service.remove_answer(RULE, "c1", revision=2)
    assert service.list_cases(RULE) == []


def test_compare_matches_by_record_and_never_passes_missing(make_service):
    cases = [{"item_id": "c1", "record_ref": _ref("C1"), "expected_status": "not_applicable"},
             {"item_id": "c2", "record_ref": _ref("C2"), "expected_status": "non_compliant"}]
    rows = {r["item_id"]: r["comparison"] for r in compare_cases(RULE, cases, _job({"c1": "not_applicable"}))}
    assert rows == {"c1": "same", "c2": "missing"}
    rows = {r["item_id"]: r["comparison"] for r in compare_cases(RULE, cases, _job({"c1": "compliant", "c2": "non_compliant"}))}
    assert rows == {"c1": "different", "c2": "same"}
    assert {r["comparison"] for r in compare_cases(RULE, cases, {"status": "running"})} == {"pending"}
    assert {r["comparison"] for r in compare_cases(RULE, cases, {"status": "failed"})} == {"failed"}


def test_full_flow_stages_conclusion_and_release_sheet(make_service):
    service = make_service()
    rule = CATALOG[RULE]
    assert derive_stage(rule, [], [], [], None) == "preparing"
    _label(service, "c1")
    _label(service, "c2", status="non_compliant")
    cases = service.list_cases(RULE)
    assert derive_stage(rule, cases, [], [], None) == "ready_to_run"

    run = service.begin_run(RULE, None, "u")
    with pytest.raises(RuleValidationConflict):
        service.begin_run(RULE, None, "u")  # 未绑定任务前禁止重复提交
    assert [c["item_id"] for c in run["cases"]] == ["c1", "c2"]
    service.bind_run(run["id"], "job-1", RELEASE)
    with pytest.raises(RuleValidationConflict):
        service.bind_run(run["id"], "job-2", RELEASE)
    run = service.get_run(run["id"])
    assert run["build_kind"] == "release"

    # 运行后改预期不影响本次快照
    _label(service, "c1", status="compliant", revision=1)
    assert service.get_run(run["id"])["cases"][0]["expected_status"] == "not_applicable"

    rows = compare_cases(RULE, run["cases"], _job({"c1": "not_applicable", "c2": "non_compliant"}))
    runs = service.list_runs(RULE)
    assert derive_stage(rule, cases, runs, service.list_events(RULE), rows) == "reviewing"
    with pytest.raises(ValueError, match="未逐例确认"):
        service.conclude(run, rows, decision="accepted", note="通过", gap_ack="缺口已知", user="u")

    service.review_case(run, rows, "c1", decision="confirmed", note="证据对", user="r")
    service.review_case(run, rows, "c2", decision="problem", note="建议不可用", user="r")
    with pytest.raises(ValueError, match="未逐例确认"):
        service.conclude(run, rows, decision="accepted", note="通过", gap_ack="缺口已知", user="u")
    service.review_case(run, rows, "c2", decision="confirmed", note="复查后建议可用", user="r")
    assert derive_stage(rule, cases, runs, service.list_events(RULE), rows) == "pending_conclusion"

    with pytest.raises(ValueError, match="覆盖缺口"):
        service.conclude(run, rows, decision="accepted", note="通过", gap_ack="", user="u")
    service.conclude(run, rows, decision="accepted", note="通过", gap_ack="合规、资料不足暂无病例", user="u")
    assert derive_stage(rule, cases, runs, service.list_events(RULE), rows) == "pending_approval"

    approval = service.approve(RULE, decision="approved", note="同意上线", user="boss")
    sheet = approval["payload"]
    assert sheet["version"]["development_version"] is False
    assert [i["item_id"] for i in sheet["inputs"]] == ["c1", "c2"]
    assert sheet["release_action"]["release_scope"] == {"from": "acceptance_only", "to": "default"}
    assert derive_stage(rule, cases, runs, service.list_events(RULE), rows) == "approved_pending_release"
    assert derive_stage({**rule, "release_scope": "default"}, cases, runs, [], rows) == "released"

    # 新运行使旧结论与批准失效
    service.begin_run(RULE, ["c1"], "u")
    runs = service.list_runs(RULE)
    assert derive_stage(rule, cases, runs, service.list_events(RULE), None) == "running"
    with pytest.raises(ValueError, match="新的运行"):
        service.approve(RULE, decision="approved", note="再次批准", user="boss")


def test_confirm_requires_same_status_and_completed_run(make_service):
    service = make_service()
    _label(service, "c1")
    run = service.begin_run(RULE, None, "u")
    pending = compare_cases(RULE, run["cases"], {"status": "running"})
    with pytest.raises(RuleValidationConflict):
        service.review_case(run, pending, "c1", decision="confirmed", note="x", user="r")
    different = compare_cases(RULE, run["cases"], _job({"c1": "compliant"}))
    with pytest.raises(ValueError, match="不一致"):
        service.review_case(run, different, "c1", decision="confirmed", note="x", user="r")
    service.review_case(run, different, "c1", decision="problem", note="状态错", user="r")


def test_blocks_unpinned_case_and_missing_version(make_service):
    service = make_service()
    _label(service, "c3")  # 历史病例未固定评价时间点
    run = service.begin_run(RULE, None, "u")
    service.bind_run(run["id"], "job", None)
    run = service.get_run(run["id"])
    rows = compare_cases(RULE, run["cases"], _job({"c3": "not_applicable"}))
    service.review_case(run, rows, "c3", decision="confirmed", note="证据对", user="r")
    blockers = service.summarize(RULE, run=run, rows=rows)["acceptance_blockers"]
    assert "存在未固定评价时间点的历史病例" in blockers and "运行缺少执行版本记录" in blockers
    service.conclude(run, rows, decision="rejected", note="需固定评价时间点", gap_ack="", user="u")


@pytest.mark.parametrize("env,allowed", [("development", True), ("production", False), ("customer", False)])
def test_process_build_approval_depends_on_environment(make_service, env, allowed):
    service = make_service(env)
    for item_id, status in (("c1", "compliant"), ("c2", "non_compliant")):
        _label(service, item_id, status=status)
    run = service.begin_run(RULE, None, "u")
    service.bind_run(run["id"], "job", PROCESS)
    run = service.get_run(run["id"])
    rows = compare_cases(RULE, run["cases"], _job({"c1": "compliant", "c2": "non_compliant"}))
    for item_id in ("c1", "c2"):
        service.review_case(run, rows, item_id, decision="confirmed", note="已核对", user="r")
    service.conclude(run, rows, decision="accepted", note="通过", gap_ack="不适用、资料不足暂缺", user="u")
    if allowed:
        sheet = service.approve(RULE, decision="approved", note="开发验收", user="boss")["payload"]
        assert sheet["version"]["development_version"] is True
    else:
        with pytest.raises(ValueError, match="客户环境"):
            service.approve(RULE, decision="approved", note="上线", user="boss")
        assert service.approve(RULE, decision="rejected", note="需正式构建重跑", user="boss")["decision"] == "rejected"


def test_coverage_splits_synthetic_and_real_copy(make_service):
    service = make_service()
    _label(service, "c1", status="non_compliant", purpose="development")
    _label(service, "c2", status="non_compliant")
    coverage = service.summarize(RULE)["coverage"]
    assert coverage["counts"]["non_compliant"] == {"synthetic": 1, "real_copy": 1}
    assert coverage["gaps"] == ["compliant", "not_applicable", "data_gap"]
    assert coverage["acceptance_cases"] == 1
