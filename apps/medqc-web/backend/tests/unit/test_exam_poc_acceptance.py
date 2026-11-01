"""POC 验收：既有应答/合成难例、真实结果链、严格网络隔离；不执行患者质控。"""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import asyncio

import httpx
import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

from app.services import custom_qc_workspace_service as workspace
from app.services import exam_result_model_route as route
from app.services.luxian_0609 import exam_result_record_check as check
from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result
from scripts.exam_poc_acceptance import CASES, MODELS, SyntheticCase, inspect_completion, inspect_recording, validate_recording
from tests.scheduler_support.isolation import OfflineIsolationError
from tests.unit.test_exam_result_model_route import answer, harness, policy, response
from tests.unit.test_luxian_0609_native_exam_lab_execution import _fact_response, _typed_session


def completion_for(p, kind, *, quote="", span=""):
    value = answer(p, kind=kind)
    for item in value["docs"]:
        item.update(quote=quote, report_span=span)
    return response(value)


def synthetic_recording():
    """CI 可重建的协议夹具；不是新增真实请求，也不伪称原始模型应答。"""
    results, requests = [], []
    for case in CASES:
        for arm, model in zip(("reference", "cascade"), MODELS):
            kind = "none" if case.name == "external_prior_exam" and arm == "cascade" else case.expected_kind
            completion = completion_for(case.projection(), kind,
                quote=case.course if kind == "result_recorded" else "",
                span="右肺下叶见8mm结节影，考虑炎性结节" if kind == "result_recorded" else "")
            completion["model"] = model
            results.append({"case": case.name, "arm": arm, "http_calls": 1})
            requests.append({"model": model, "returned_model": model, "status": "success", "http_status": 200,
                             "enable_thinking_sent": False, "completion": completion})
    return {"synthetic_only": True, "database_writes": 0, "models": list(MODELS),
            "results": results, "requests": requests}


async def formal_replay(monkeypatch, tmp_path, *, case, recordings, arm, mature):
    monkeypatch.setenv("LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR", str(tmp_path / "f"))
    rows = case.rows()
    horizon = ({"discharge_datetime": "2026-01-05 12:00:00"},) if mature else ()
    evaluation = ({"horizon_datetime": "2026-01-05 12:00:00", "horizon_date": "2026-01-05"},) if mature else ()
    snapshot, materials = _typed_session(monkeypatch, exam_rows=rows["exam_master"],
        course_rows=rows["daily_course_record"], discharge_horizon_rows=horizon, evaluation_horizon_rows=evaluation)
    p = build_exam_lab_text_projection(rows_by_source={**rows, "inpat_registration.discharge_horizon": horizon,
                                                      "evaluation_context.horizon": evaluation})
    remaining, sent, traces = deepcopy(recordings), [], []
    old_observe = route.RouteSession.observe

    def observe(self, event, **metrics):
        traces.append({"event": event, **metrics})
        old_observe(self, event, **metrics)

    monkeypatch.setattr(route.RouteSession, "observe", observe)

    def fixed(request):
        body = json.loads(request.content)
        specialty = check.SCHEMA_VERSION in body["messages"][0]["content"]
        sent.append({"host": request.url.host, "specialty": specialty})
        if not specialty:
            # 原 POC 未录制主抽取；显式固定“已记录”以检验专项负面核验能否纠正。
            return httpx.Response(200, json=response(_fact_response((check.RULE_ID,))))
        assert remaining, "recorded response exhausted; no network fallback"
        item = remaining.pop(0)
        assert request.url.host == ("candidate.test" if arm == "cascade" and not any(
            s["specialty"] for s in sent[:-1]) else "reference.test")
        return httpx.Response(200, json=item["completion"])

    _, app, client = harness(monkeypatch, tmp_path, fixed, cloud=True,
        config=policy("cascade" if arm == "cascade" else "off", experiment="A1-replay"))
    engine = None
    try:
        batch = await native._extract_exam_lab_batch(projection=p, eligible_rule_ids=[check.RULE_ID], llm_client=client)
        assert not remaining and batch.facts and not batch.rule_failures
        assert not batch.incomplete_specialty_rule_ids
        outcome = native._text_fact_outcome(rule_id=check.RULE_ID, facts=batch.facts, projection=p)
        decision = native._decision_from_outcome(outcome=outcome, snapshot=snapshot)
        [reduced] = bind_and_reduce_luxian_0609_rule_decisions(decisions=(decision,),
            expected_rule_ids=(check.RULE_ID,), snapshot=snapshot, evidence_materials=materials)
        display = native._with_result_conflicts(native._display_facts_for_text_outcome(
            rule_id=check.RULE_ID, facts=batch.facts, projection=p, outcome=outcome),
            conflicts=batch.result_conflicts, projection=p)
        final = finalize_luxian_0609_reduced_customer_result(decision=reduced,
            raw_customer_display_facts=display, evidence_snapshot=snapshot, evidence_materials=materials)
        [published] = aggregate_luxian_0609_results(wrapper_rules=[get_luxian_0609_rule(check.RULE_ID)],
            execution_results=[], canonical_results=(final,), delivery_mode=CANONICAL_RESULT_DELIVERY_MODE)
        table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
        engine = create_engine("sqlite://")
        table.metadata.create_all(engine)
        store = CanonicalResultStore(table)
        ref = {"institute_id": "safe-institute", "patient_id": "safe-patient", "visit_id": "safe-visit"}
        with Session(engine) as session:
            store.replace_for_job(session, job_row={"id": "synthetic-replay", "created_by": "synthetic-tester",
                "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                    "scoped_customer_rule_ids": [check.RULE_ID], "record_refs": [ref]})},
                items=[{**published, **ref, "record_id": ref["visit_id"]}], now=datetime(2026, 1, 6),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="synthetic-ref-key"),
                projection_key="synthetic-ref-key")
            session.commit()
            saved = store.load_selected(session, root_job_id="synthetic-replay", **ref,
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")["items"][0]
        assert saved["rule_id"] == final["rule_id"] == check.RULE_ID
        assert saved["status"] == final["status"] == outcome.status
        assert saved["reason_code"] == final["reason_code"] == reduced.reason_code
        assert saved.get("customer_display_facts") == final.get("customer_display_facts")
        assert saved["conclusion"] == (final.get("conclusion") or final.get("customer_conclusion") or final["findings"])
        # Canonical 客户投影把 customer_evidence 改名为 evidence，并将来源 ID HMAC 化。
        # 核对内容/时间/顺序与条数，不能把合法字段映射误当证据丢失。
        from app.services.qc_workspace.canonical_result_store import keyed_ref

        evidence = final.get("customer_evidence", [])
        assert len(saved["evidence"]) == len(evidence)
        for original, restored in zip(evidence, saved["evidence"]):
            source = original.get("source_ref") or original.get("document_ref") or original.get("fact_ref") or original.get("source_document_id")
            assert restored["source_ref"] == keyed_ref("src", source, hmac_key="synthetic-ref-key")
            assert {k: v for k, v in restored.items() if k != "source_ref"} == {
                k: v for k, v in original.items() if k not in {"source_ref", "document_ref", "fact_ref", "document_id", "source_document_id"}}
        assert batch.llm_call_count == len(sent) == len(recordings) + 1
        # 相同输入的热冻结必须不再取应答；分区/上界均由原正式键负责。
        count = len(sent)
        hot = await native._extract_exam_lab_batch(projection=p, eligible_rule_ids=[check.RULE_ID], llm_client=client)
        assert hot.facts == batch.facts and hot.result_conflicts == batch.result_conflicts and not hot.llm_call_count
        assert len(sent) == count
        return {"case": case.name, "arm": arm, "context": "explicit_synthetic_mature_horizon" if mature else "original_no_horizon",
                "main_extraction": "fixed_present_fixture_not_recorded_live", "specialty": "reused_recording",
                "facts": [asdict(fact) for fact in batch.facts], "conflict_refs": batch.result_conflicts,
                "native_status": outcome.status, "native_reason": outcome.reason_code,
                "bound_decision": asdict(reduced),
                "final": final, "saved": {key: saved.get(key) for key in
                    ("rule_id", "status", "reason_code", "customer_display_facts", "evidence", "conclusion")},
                "logical_calls": batch.llm_call_count, "new_model_calls": 0,
                "hot_freeze_calls": hot.llm_call_count, "route_events": traces}
    finally:
        if engine is not None:
            engine.dispose()
        assert await app.state.gateway_runtime.shutdown()


async def replay_recording(monkeypatch, tmp_path, payload):
    report = inspect_recording(payload)
    report["formal_chain"] = []
    for case, result, recordings in validate_recording(payload):
        for mature in (False, True):
            # 每例独立 monkeypatch 作用域，避免 trace wrapper 层层累积。
            with monkeypatch.context() as patch:
                row = await formal_replay(patch, tmp_path / f"{CASES.index(case)}{result['arm'][0]}{int(mature)}",
                    case=case, recordings=recordings, arm=result["arm"], mature=mature)
            expected = "compliant" if case.expected_kind == "result_recorded" else "non_compliant" if mature else "data_gap"
            assert row["native_status"] == expected
            report["formal_chain"].append(row)
    for case in CASES[:len(report["arms"]) // 2]:
        for context in ("original_no_horizon", "explicit_synthetic_mature_horizon"):
            rows = [row for row in report["formal_chain"] if row["case"] == case.name and row["context"] == context]
            assert len(rows) == 2 and rows[0]["saved"] == rows[1]["saved"]
            assert rows[0]["facts"] == rows[1]["facts"] and rows[0]["conflict_refs"] == rows[1]["conflict_refs"]
    return report


@pytest.mark.asyncio
async def test_self_contained_recording_replays_original_and_declared_context(monkeypatch, tmp_path):
    report = await replay_recording(monkeypatch, tmp_path, synthetic_recording())
    assert len(report["formal_chain"]) == 12
    assert all(not arm["recorded_upgrade_observed"] for arm in report["arms"])
    difference = report["comparisons"][-1]
    assert difference["same_recorded_direction"] and difference["same_conflict_facts"]
    assert difference["manual_review_required"]
    assert difference["differences"][0]["fields"] == ["quote_type"]
    assert report["arms"][-1]["accepted"]["pairs"][0]["category_matches_expectation"] is False


@pytest.mark.asyncio
async def test_fixed_upgrade_reason_and_recovered_answer_reach_saved_result(monkeypatch, tmp_path):
    payload = synthetic_recording()
    # 计划场景的候选漏项，升级 Flash 后恢复；其余录制段保持原归属。
    recovered = deepcopy(payload["requests"][3])
    recovered.update(model=MODELS[0], returned_model=MODELS[0])
    recovered["completion"]["model"] = MODELS[0]
    payload["requests"][3]["completion"] = {**payload["requests"][3]["completion"],
        **response({"schema_version": check.SCHEMA_VERSION, "docs": []})}
    payload["requests"].insert(4, recovered)
    payload["results"][3]["http_calls"] = 2
    report = await replay_recording(monkeypatch, tmp_path, payload)
    arm = report["arms"][3]
    assert arm["upgrade_count"] == 1 and arm["upgrade_reasons"][0]["reason"] == "invalid doc coverage"
    assert "invalid doc coverage" in arm["upgrade_reasons"][0]["details"]
    assert arm["model_sequence"] == [MODELS[1], MODELS[0]]
    rows = [r for r in report["formal_chain"] if r["case"] == "plan_only" and r["arm"] == "cascade"]
    assert all(row["logical_calls"] == 3 and row["hot_freeze_calls"] == 0 for row in rows)


def test_audit_parser_accepts_same_json_envelope_as_production_parser():
    p = CASES[1].projection()
    completion = completion_for(p, "plan_only")
    message = completion["choices"][0]["message"]
    message["content"] = "```json\n" + message["content"] + "\n```"
    assert inspect_completion(p, completion)["protocol_valid"]


def test_reference_protocol_retry_is_not_misreported_as_model_upgrade():
    payload = synthetic_recording()
    original = deepcopy(payload["requests"][0])
    payload["requests"][0]["completion"] = {**original["completion"],
        **response({"schema_version": check.SCHEMA_VERSION, "docs": []})}
    payload["requests"].insert(1, original)
    payload["results"][0]["http_calls"] = 2
    arm = inspect_recording(payload)["arms"][0]
    assert arm["upgrade_count"] == 0 and not arm["recorded_upgrade_observed"]
    assert len(arm["protocol_retry_reasons"]) == 1


@pytest.mark.asyncio
async def test_existing_recording_full_offline_chain(monkeypatch, tmp_path):
    artifact = os.environ.get("MEDQC_EXAM_POC_ARTIFACT")
    if not artifact:
        pytest.skip("显式传入既有合成报告才执行本地真实应答回放；CI 使用可重建夹具")
    path = Path(artifact)
    assert path.stat().st_size <= 2_000_000
    report = await replay_recording(monkeypatch, tmp_path, json.loads(path.read_text(encoding="utf-8")))
    output = Path(os.environ["MEDQC_EXAM_POC_REPORT"])
    assert not output.exists(), "禁止覆盖原始记录或既有验收报告"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


@pytest.mark.parametrize("change", ["order", "model", "extra", "missing", "explicit", "not_synthetic"])
def test_ambiguous_or_incomplete_recordings_fail_closed(change):
    payload = synthetic_recording()
    if change == "order":
        payload["results"][0], payload["results"][2] = payload["results"][2], payload["results"][0]
    elif change == "model":
        payload["requests"][0]["completion"]["model"] = MODELS[1]
    elif change == "extra":
        payload["requests"].append(payload["requests"][0])
    elif change == "missing":
        payload["requests"].pop()
    elif change == "explicit":
        payload["requests"][0]["case"] = "foreign_case"
    else:
        payload["synthetic_only"] = False
    with pytest.raises(ValueError):
        validate_recording(payload)


def test_network_and_business_database_guards_remain_active():
    with pytest.raises(OfflineIsolationError):
        socket.getaddrinfo("dashscope.aliyuncs.com", 443)
    with pytest.raises(OfflineIsolationError):
        create_engine("sqlite:///must-not-exist.db").connect()


@pytest.mark.asyncio
@pytest.mark.parametrize("name,course,kind", [
    ("conflict", "本次胸部CT未见右肺下叶结节。", "result_conflicting"),
    ("laterality", "本次胸部CT提示左肺下叶小结节。", "other_exam"),
    ("mention", "胸部CT结果已回报，详见报告。", "mention_only"),
])
async def test_hard_categories_and_conflicts_survive_formal_save(monkeypatch, tmp_path, name, course, kind):
    case = SyntheticCase(name, course, kind)
    p = case.projection()
    completion = completion_for(p, kind, quote=course if kind == "result_conflicting" else "",
                                span="右肺下叶见8mm结节影" if kind == "result_conflicting" else "")
    inspected = inspect_completion(p, completion, expected_kinds={(1, "D06-01"): kind})
    assert inspected["protocol_valid"] and inspected["coverage_complete"]
    assert inspected["pairs"][0]["category_matches_expectation"]
    assert inspected["pairs"][0]["source_document"] == ["daily_course_record", "SYN-DOC-1"]
    row = await formal_replay(monkeypatch, tmp_path, case=case,
        recordings=[{"completion": completion}], arm="cascade", mature=True)
    assert row["saved"]["status"] == "non_compliant"
    if kind == "result_conflicting":
        assert row["conflict_refs"] == {1: ("D06-01",)}
        assert row["saved"]["customer_display_facts"]["result_conflict_record_times"] == ["2026-01-02 15:00:00"]
    else:
        assert not row["conflict_refs"]


@pytest.mark.asyncio
async def test_repeated_exam_pairs_keep_event_and_source_identity(monkeypatch, tmp_path):
    rows = CASES[0].rows()
    first = rows["exam_master"][0]
    rows["exam_master"] = (first, {**first, "exam_id": "SYN-EX-2", "report_time": "2026-01-02 16:00:00",
                                  "exam_conclusion": "左肺上叶新发斑片影，考虑炎症。"})
    rows["daily_course_record"] += ({"document_id": "SYN-DOC-2", "record_time": "2026-01-02 18:00:00",
                                      "record_content": "复查胸部CT左肺上叶斑片状渗出。"},)
    p = build_exam_lab_text_projection(rows_by_source=rows)
    value = answer(p)
    for item in value["docs"]:
        if item["event_position"] == 1 and item["course_doc_ref"] == "D06-01":
            item.update(quote_type="result_recorded", quote=CASES[0].course, report_span="右肺下叶见8mm结节影")
        elif item["event_position"] == 2:
            item.update(quote_type="result_recorded", quote="复查胸部CT左肺上叶斑片状渗出。", report_span="左肺上叶新发斑片影")
        else:
            item["quote_type"] = "other_exam"
    inspected = inspect_completion(p, response(value), source_rows=rows)
    assert inspected["protocol_valid"] and inspected["coverage_complete"]
    assert inspected["recorded_refs"] == {1: ("D06-01",), 2: ("D06-02",)}
    assert len({tuple(pair["event_refs"]) for pair in inspected["pairs"]}) == 2
    assert {pair["event_position"]: pair["event_sources"][0]["exam_id"] for pair in inspected["pairs"]} == {
        1: "SYN-EX-1", 2: "SYN-EX-2"}
    assert {tuple(pair["source_document"]) for pair in inspected["pairs"]} == {
        ("daily_course_record", "SYN-DOC-1"), ("daily_course_record", "SYN-DOC-2")}
    _, app, client = harness(monkeypatch, tmp_path, lambda _: httpx.Response(200, json=response(value)))
    try:
        result = await check.check_exam_result_record(p, client)
        assert result.recorded_refs == inspected["recorded_refs"]
    finally:
        assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_valid_but_semantically_wrong_answer_is_flagged_by_independent_expectation(monkeypatch, tmp_path):
    case = CASES[2]
    p = case.projection()
    wrong = completion_for(p, "result_recorded", quote=case.course, span="右肺下叶见8mm结节影")
    checked = inspect_completion(p, wrong, expected_kinds={(1, "D06-01"): case.expected_kind})
    assert checked["protocol_valid"] and checked["pairs"][0]["accepted_recorded"]
    assert checked["pairs"][0]["category_matches_expectation"] is False
    sent = []

    def fixed(request):
        sent.append(request.url.host)
        return httpx.Response(200, json=wrong)

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    try:
        result = await check.check_exam_result_record(p, client)
        assert result.recorded_refs == {1: ("D06-01",)} and sent == ["candidate.test"]
        # 固定保护明确展示自动结构检查的能力边界，不伪称能够发现所有语义错判。
    finally:
        assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_long_tail_cannot_be_claimed_as_complete_candidate_validation(monkeypatch, tmp_path):
    case = SyntheticCase("tail", "观察。" * 2200 + CASES[0].course, "result_recorded")
    p, sent, traces = case.projection(), [], []
    monkeypatch.setattr(route.RouteSession, "observe", lambda self, event, **metrics: traces.append({"event": event, **metrics}))

    def fixed(request):
        sent.append(request)
        return httpx.Response(200, json=completion_for(p, "none"))

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    try:
        await check.check_exam_result_record(p, client)
        assert len(sent) == 1 and sent[0].url.host == "reference.test"
        assert CASES[0].course not in json.loads(sent[0].content)["messages"][0]["content"]
        assert any(t.get("reason") == "input_projection_limit" and t.get("input_complete") is False for t in traces)
        inspected = inspect_completion(p, completion_for(p, "none"), expected_kinds={(1, "D06-01"): "result_recorded"})
        assert inspected["input_projection_complete"] is False
        assert inspected["pairs"][0]["category_matches_expectation"] is False
    finally:
        assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,expected_reason", [
    ("truncated", "incomplete response"), ("missing", "invalid doc coverage"),
    ("event", "invalid doc coverage"), ("quote", "quote not in course"),
])
async def test_upgrade_failure_keeps_incomplete_and_is_not_frozen(monkeypatch, tmp_path, failure, expected_reason):
    p, sent, trace = CASES[1].projection(), [], []
    value = answer(p)
    if failure == "missing":
        value["docs"] = []
    elif failure == "event":
        value["docs"][0]["event_position"] = 999
    elif failure == "quote":
        value["docs"][0].update(quote_type="result_recorded", quote="原文不存在的右肺结节", report_span="右肺下叶见8mm结节影")
    bad = response(value, finish="length" if failure == "truncated" else "stop")
    diagnostic = inspect_completion(p, bad)
    assert not diagnostic["protocol_valid"] and diagnostic["validation_reason"] == expected_reason
    monkeypatch.setattr(route.RouteSession, "observe", lambda self, event, **metrics: trace.append({"event": event, **metrics}))

    def fixed(request):
        body = json.loads(request.content)
        sent.append(request.url.host)
        return httpx.Response(200, json=bad if check.SCHEMA_VERSION in body["messages"][0]["content"]
                              else response(_fact_response((check.RULE_ID,), semantic_state="absent")))

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    try:
        for _ in range(2):
            batch = await native._extract_exam_lab_batch(projection=p, eligible_rule_ids=[check.RULE_ID], llm_client=client)
            assert batch.incomplete_specialty_rule_ids == frozenset({check.RULE_ID})
            assert batch.facts and batch.facts[0].semantic_state == "absent"
            assert batch.llm_call_count == 3
        assert sent == ["reference.test", "candidate.test", "reference.test"] * 2
        upgrades = [t for t in trace if t["event"] == "upgraded"]
        assert len(upgrades) == 2 and all(t["reason"] == ("truncated" if failure == "truncated" else "protocol_validation") for t in upgrades)
        assert all(not t.get("freeze_hit") for t in trace if t["event"] == "family_freeze")
    finally:
        assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http", "timeout", "cancel"])
async def test_reference_upgrade_transport_failure_does_not_accept_candidate(monkeypatch, tmp_path, failure):
    p, sent = CASES[1].projection(), []
    started, release = asyncio.Event(), asyncio.Event()

    async def fixed(request):
        sent.append(request.url.host)
        if request.url.host == "candidate.test":
            return httpx.Response(200, json=response({"schema_version": check.SCHEMA_VERSION, "docs": []}))
        if failure == "cancel":
            started.set()
            await release.wait()
            return httpx.Response(200, json=completion_for(p, "none"))
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic timeout")
        return httpx.Response(400, json={"error": "synthetic failure"})

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    try:
        if failure == "cancel":
            task = asyncio.create_task(check.check_exam_result_record(p, client))
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            outcome = await check.check_exam_result_record(p, client)
            assert outcome.state == "failed" and not outcome.recorded_refs and not outcome.conflict_refs
        assert sent[0] == "candidate.test" and set(sent[1:]) == {"reference.test"} and len(sent) <= 3
    finally:
        release.set()
        await asyncio.sleep(0)
        clean = await app.state.gateway_runtime.shutdown()
        if failure == "timeout":
            assert not clean  # 未知在途按原 Gateway 隔离，不能为实验清槽。
