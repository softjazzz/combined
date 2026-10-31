"""合成检查材料经真实 client/Gateway 的固定流，不访问业务库或真实推理。"""

import asyncio
from contextlib import contextmanager
from copy import deepcopy
import json

import httpx
import pytest

from app.core.settings import Settings
from app.llm_gateway.config import CaseContinuationConfig, GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import create_app
from app.services import llm_observability, qc_llm_client
from app.services.llm_dispatch import client as dispatch_module
from app.services.llm_dispatch.client import GatewayDispatchClient
from app.services.llm_observability import LLMObservabilityRecorder, NullLLMCallEventStore
from app.services.luxian_0609.exam_lab_fact_extraction import ExamLabEventFact, build_exam_lab_text_projection
from app.services.luxian_0609 import exam_result_record_check as check
from app.services.strata_case_context import exam_result_prefix_scope
from app.services.strata_observation import capture_strata_observations


def projection(*, extra=""):
    return build_exam_lab_text_projection(rows_by_source={
        "exam_master": ({"exam_id": "SYN-EX", "exam_name": "胸部CT平扫",
                         "exam_time": "2026-01-02 10:30:00", "report_time": "2026-01-02 11:30:00",
                         "exam_conclusion": "右肺下叶占位，考虑恶性可能；主动脉壁钙化。"},),
        "daily_course_record": ({"record_time": "2026-01-02 15:00:00",
                                 "record_content": "合成稳定观察记录。" * 150 + extra
                                 + "拟完善胸部CT，外院超声提示胆囊结石。"},),
    })


def original_prompt(p):
    return check._prompt(p, check._targets(p))


def response(content="{\"unchanged\":true}", *, cached=800, prime=False):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 1 if prime else 20,
                      "prompt_tokens_details": {"cached_tokens": cached}},
            "timings": {"cache_n": cached, "prompt_n": 200, "prompt_ms": 2,
                        "predicted_n": 1 if prime else 20, "predicted_ms": 3}}


def restored_prompt(payload):
    messages = payload["messages"]
    if len(messages) == 2:
        return messages[1]["content"] + messages[0]["content"]
    return messages[0]["content"]


@contextmanager
def identity(*, patient="synthetic-patient-a", version="v1"):
    with llm_observability.llm_observation_context(
        business_scene="synthetic", root_job_id="synthetic-root",
        record_identity=("synthetic-institute", patient, "synthetic-visit"),
        executor_key="exam_lab", rule_set_key="synthetic-rules", rule_set_version=version,
    ):
        yield


def harness(monkeypatch, tmp_path, handler, *, mode="prefix", continuation=True):
    settings = Settings(
        _env_file=None, JWT_SECRET="synthetic-observation-secret", STRATA_CASE_CACHE_MODE=mode,
        LLM_DISPATCH_MODE="gateway", LLM_GATEWAY_URL="http://gateway.test",
        LLM_GATEWAY_TOKEN="test-gateway-token-at-least-32-chars", LLM_GATEWAY_PROFILE="strata_first_pass",
    )
    for module in (qc_llm_client, llm_observability, dispatch_module):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    profile = ProfileConfig("strata_first_pass", "gpu", "strata", "synthetic-model",
                            "http://strata.test/v1/chat/completions")
    app = create_app(GatewaySettings(
        token="test-gateway-token-at-least-32-chars", resources={"gpu": ResourceConfig("gpu", 2, 8)},
        profiles={profile.name: profile}, allowed_hosts=frozenset({"strata.test"}), state_dir=tmp_path,
        startup_isolation_seconds=0, cache_enabled=True, cache_deployment_version="synthetic-deploy-v1",
        continuation=CaseContinuationConfig(enabled=continuation),
    ), http_transport=httpx.MockTransport(handler), enforce_single_instance=False)
    dispatch = GatewayDispatchClient(transport=httpx.ASGITransport(app=app))
    client = qc_llm_client.SichuanQCLLMClient(
        {"api_endpoint": "http://strata.test/v1", "api_key": "synthetic-key",
         "model": "synthetic-model", "provider_code": "strata", "dispatch_mode": "gateway",
         "gateway_profile": "strata_first_pass"}, gateway_dispatch_client=dispatch,
        observability_recorder=LLMObservabilityRecorder(store=NullLLMCallEventStore()),
    )
    return app, client


@pytest.mark.asyncio
async def test_real_original_and_recheck_prime_once_and_collect_all_http_cost(monkeypatch, tmp_path):
    sent = []

    def fixed(request):
        payload = json.loads(request.content)
        sent.append(payload)
        return httpx.Response(200, json=response(prime=payload["max_tokens"] == 1))

    app, client = harness(monkeypatch, tmp_path, fixed)
    prompt = original_prompt(projection())
    retry = check._retry_prompt(prompt, ValueError("synthetic protocol error"), {})
    with identity(), capture_strata_observations() as observed, exam_result_prefix_scope(expected_requests=2):
        first = await client.generate(prompt)
        second = await client.generate(retry)
    assert len(sent) == 3 and sum(p["max_tokens"] == 1 for p in sent) == 1
    prime, original, recheck = sent
    assert restored_prompt(original) == prompt and restored_prompt(recheck) == retry
    assert original["messages"][0] == recheck["messages"][0]
    assert prime["messages"] == [original["messages"][0]]
    assert all(not any(k.startswith("_strata") for k in p) and "case_prefix" not in p for p in sent)
    assert first["choices"] == second["choices"] == response()["choices"]
    assert first["usage"]["prompt_tokens"] == 1000  # 既有临床usage保持单条规则语义
    report = observed.report()
    assert report["logical_call_count"] == 2 and report["attempt_count"] == 3
    assert report["prime_requests_started"] == 1
    assert report["cost"]["model_requests_started"] == {"known_sum": 3, "unknown_count": 0}
    assert report["cost"]["nominal_input_tokens"] == {"known_sum": 3000, "unknown_count": 0}
    assert report["cost"]["output_tokens"] == {"known_sum": 41, "unknown_count": 0}
    assert report["prime_wall_ms"]["known_sum"] >= 0
    assert sum(event["purpose"] == "prime" for event in observed.events) == 1
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_real_concurrent_calls_share_one_prime(monkeypatch, tmp_path):
    sent, started, release = [], asyncio.Event(), asyncio.Event()

    async def fixed(request):
        payload = json.loads(request.content)
        sent.append(payload)
        if payload["max_tokens"] == 1:
            started.set()
            await release.wait()
        return httpx.Response(200, json=response(prime=payload["max_tokens"] == 1))

    app, client = harness(monkeypatch, tmp_path, fixed)
    with identity(), capture_strata_observations() as observed, exam_result_prefix_scope(expected_requests=2):
        first = asyncio.create_task(client.generate(original_prompt(projection())))
        await asyncio.wait_for(started.wait(), 1)
        second = asyncio.create_task(client.generate(original_prompt(projection())))
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(first, second)
    assert len(sent) == 3 and sum(p["max_tokens"] == 1 for p in sent) == 1
    assert all(r["choices"] == response()["choices"] for r in results)
    assert observed.report()["prime_requests_started"] == 1
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["patient", "evidence", "version"])
async def test_real_client_case_evidence_and_rule_version_are_isolated(monkeypatch, tmp_path, changed):
    sent = []

    def fixed(request):
        payload = json.loads(request.content)
        sent.append(payload)
        return httpx.Response(200, json=response(prime=payload["max_tokens"] == 1))

    app, client = harness(monkeypatch, tmp_path, fixed)
    with identity(), exam_result_prefix_scope(expected_requests=2):
        await client.generate(original_prompt(projection()))
    kwargs = {"patient": "synthetic-patient-b"} if changed == "patient" else {"version": "v2"} if changed == "version" else {}
    with identity(**kwargs), exam_result_prefix_scope(expected_requests=2):
        await client.generate(original_prompt(projection(extra="新的合成观察。" if changed == "evidence" else "")))
    assert len(sent) == 4 and sum(p["max_tokens"] == 1 for p in sent) == 2
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["prime_http_failure", "cache_miss"])
async def test_real_cache_failure_or_miss_preserves_success_without_reasking(monkeypatch, tmp_path, failure):
    sent = []

    def fixed(request):
        payload = json.loads(request.content)
        sent.append(payload)
        prime = payload["max_tokens"] == 1
        if prime and failure == "prime_http_failure":
            return httpx.Response(400, json={"error": "synthetic"})
        return httpx.Response(200, json=response(prime=prime, cached=0 if failure == "cache_miss" else 800))

    app, client = harness(monkeypatch, tmp_path, fixed)
    prompt = original_prompt(projection())
    with identity(), capture_strata_observations() as observed, exam_result_prefix_scope(expected_requests=2):
        result = await client.generate(prompt)
    assert len(sent) == 2 and result["choices"] == response()["choices"]
    assert restored_prompt(sent[-1]) == prompt
    assert observed.report()["cost"]["model_requests_started"]["known_sum"] == 2
    if failure == "prime_http_failure":
        assert not observed.report()["cost_complete"]
        assert observed.report()["cost"]["nominal_input_tokens"]["unknown_count"] == 1
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit_budget", [False, True])
async def test_actual_checker_original_recheck_and_fact_application_match_cold(monkeypatch, tmp_path, explicit_budget):
    p = projection()
    [ref] = list(p.course_times)
    sent, rule_count = [], 0

    def fixed(request):
        nonlocal rule_count
        payload = json.loads(request.content)
        sent.append(payload)
        if payload["max_tokens"] == 1:
            return httpx.Response(200, json=response(prime=True))
        rule_count += 1
        # 真正的第一轮coverage失败触发既有补核；第二轮明确没有记录本次CT。
        docs = [] if rule_count == 1 else [{"event_position": 1, "course_doc_ref": ref,
                                          "quote_type": "none", "quote": "", "report_span": ""}]
        content = json.dumps({"schema_version": check.SCHEMA_VERSION, "docs": docs}, ensure_ascii=False)
        return httpx.Response(200, json=response(content))

    app, client = harness(monkeypatch, tmp_path, fixed)
    with identity(), exam_result_prefix_scope(expected_requests=2 if explicit_budget else 1):
        outcome = await check.check_exam_result_record(p, client)
    assert outcome.state == "ready" and outcome.recorded_refs == {1: ()} and outcome.llm_call_count == 2
    assert sum(payload["max_tokens"] == 1 for payload in sent) == int(explicit_budget)
    rule_payloads = [payload for payload in sent if payload["max_tokens"] != 1]
    assert len(rule_payloads) == 2
    original, retry = map(restored_prompt, rule_payloads)
    assert original == original_prompt(p) and "上一次输出未通过校验" in retry
    assert original.rpartition("\nEVENTS_JSON=")[2] == retry.rpartition("\nEVENTS_JSON=")[2]
    fact = ExamLabEventFact(check.RULE_ID, "applicable", "present", "not_relevant", (ref,), (ref,))
    [applied] = check.apply_result_record((fact,), outcome)
    assert applied.semantic_state == "absent" and applied.course_doc_refs == ()
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", ["这句并不存在于合成材料", "外院超声提示胆囊结石"])
async def test_cached_checker_cannot_accept_fabricated_quote_or_ultrasound_as_ct(monkeypatch, tmp_path, quote):
    p = projection()
    [ref] = list(p.course_times)
    sent = []

    def fixed(request):
        payload = json.loads(request.content)
        sent.append(deepcopy(payload))
        if payload["max_tokens"] == 1:
            return httpx.Response(200, json=response(prime=True))
        doc = {"event_position": 1, "course_doc_ref": ref, "quote_type": "result_recorded",
               "quote": quote, "report_span": "右肺下叶占位"}
        return httpx.Response(200, json=response(json.dumps({"schema_version": check.SCHEMA_VERSION, "docs": [doc]})))

    app, client = harness(monkeypatch, tmp_path, fixed)
    with identity(), exam_result_prefix_scope(expected_requests=2):
        outcome = await check.check_exam_result_record(p, client)
    if quote == "这句并不存在于合成材料":
        assert outcome.state == "failed" and outcome.recorded_refs == {}
        assert outcome.llm_call_count == 2 and len(sent) == 3
    else:
        # 原句真实存在也不能把超声当作本次CT结果；缓存不能绕过原定位合同。
        assert outcome.state == "ready" and outcome.recorded_refs == {1: ()}
        assert outcome.llm_call_count == 1 and len(sent) == 2
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_fixed_response_facts_survive_formal_binding_finalizer_and_sqlite_equally(monkeypatch, tmp_path):
    """实际核验事实进入正式裁决/绑定/发布/保存，不另造一份临床结论。"""
    from datetime import datetime

    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session

    from test_luxian_0609_native_exam_lab_execution import _typed_session
    from app.services import custom_qc_workspace_service as workspace
    from app.services.luxian_0609 import native_exam_lab_execution as native
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
    from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE
    from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

    exam_rows = ({"document_id": "SYN-REPORT", "exam_id": "SYN-EX", "exam_name": "胸部CT平扫",
                  "exam_time": "2026-01-02 10:30:00", "report_time": "2026-01-02 11:30:00",
                  "exam_conclusion": "右肺下叶占位，考虑恶性可能；主动脉壁钙化。"},)
    course_rows = ({"document_id": "SYN-COURSE", "record_time": "2026-01-02 15:00:00",
                    "record_content": "合成稳定观察记录。" * 150 + "拟完善胸部CT，外院超声提示胆囊结石。"},)
    horizon = ({"discharge_datetime": "2026-01-05 12:00:00"},)
    evaluation = ({"horizon_datetime": "2026-01-05 12:00:00", "horizon_date": "2026-01-05"},)
    snapshot, materials = _typed_session(
        monkeypatch, exam_rows=exam_rows, course_rows=course_rows,
        discharge_horizon_rows=horizon, evaluation_horizon_rows=evaluation,
    )
    p = build_exam_lab_text_projection(rows_by_source={
        "exam_master": exam_rows, "daily_course_record": course_rows,
        "inpat_registration.discharge_horizon": horizon, "evaluation_context.horizon": evaluation,
    })
    [ref] = list(p.course_times)
    event_refs = p.imaging_events[0].document_refs
    original_fact = ExamLabEventFact(check.RULE_ID, "applicable", "present", "not_relevant",
                                     (ref,), (*event_refs, ref))
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    compared = []
    try:
        for mode in ("off", "prefix"):
            sent, rule_count = [], 0

            def fixed(request):
                nonlocal rule_count
                payload = json.loads(request.content)
                sent.append(payload)
                if payload["max_tokens"] == 1:
                    return httpx.Response(200, json=response(prime=True))
                rule_count += 1
                docs = [] if rule_count == 1 else [{"event_position": 1, "course_doc_ref": ref,
                                                  "quote_type": "none", "quote": "", "report_span": ""}]
                return httpx.Response(200, json=response(json.dumps({"schema_version": check.SCHEMA_VERSION, "docs": docs})))

            app, client = harness(monkeypatch, tmp_path / mode, fixed, mode=mode)
            with identity(), exam_result_prefix_scope(expected_requests=2):
                checked = await check.check_exam_result_record(p, client)
            applied = check.apply_result_record((original_fact,), checked)
            outcome = native._text_fact_outcome(rule_id=check.RULE_ID, facts=applied, projection=p)
            decision = native._decision_from_outcome(outcome=outcome, snapshot=snapshot)
            [reduced] = bind_and_reduce_luxian_0609_rule_decisions(
                decisions=(decision,), expected_rule_ids=(check.RULE_ID,), snapshot=snapshot,
                evidence_materials=materials,
            )
            display = native._display_facts_for_text_outcome(
                rule_id=check.RULE_ID, facts=applied, projection=p, outcome=outcome,
            )
            final = finalize_luxian_0609_reduced_customer_result(
                decision=reduced, raw_customer_display_facts=display,
                evidence_snapshot=snapshot, evidence_materials=materials,
            )
            assert final["status"] == "non_compliant"
            assert reduced.reason_code == final["reason_code"] == "requirement_violated"
            assert final["customer_evidence"]
            [published] = aggregate_luxian_0609_results(
                wrapper_rules=[get_luxian_0609_rule(check.RULE_ID)], execution_results=[],
                canonical_results=(final,), delivery_mode=CANONICAL_RESULT_DELIVERY_MODE,
            )
            job_id = f"synthetic-prefix-{mode}"
            with Session(engine) as session:
                store.replace_for_job(
                    session, job_row={"id": job_id, "created_by": "synthetic-tester",
                                      "filters_json": json.dumps({
                                          "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                                          "scoped_customer_rule_ids": [check.RULE_ID],
                                          "record_refs": [{"institute_id": "safe-institute", "patient_id": "safe-patient",
                                                           "visit_id": "safe-visit"}],
                                      })},
                    items=[{**published, "record_id": "safe-visit", "institute_id": "safe-institute",
                            "patient_id": "safe-patient", "visit_id": "safe-visit"}],
                    now=datetime(2026, 1, 6),
                    projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="synthetic-ref-key"),
                    projection_key="synthetic-ref-key",
                )
                session.commit()
                saved = store.load_selected(
                    session, root_job_id=job_id, institute_id="safe-institute", patient_id="safe-patient",
                    visit_id="safe-visit", rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
                )["items"][0]
            assert saved["status"] == final["status"] and saved["reason_code"] == final["reason_code"]
            compared.append((applied, reduced, final, {
                key: saved.get(key) for key in ("status", "reason_code", "customer_display_facts", "customer_evidence",
                                                "conclusion", "suggestion")
            }))
            assert sum(payload["max_tokens"] == 1 for payload in sent) == int(mode == "prefix")
            assert await app.state.gateway_runtime.shutdown()
        assert compared[0] == compared[1]
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_old_prompt_three_cases_real_dispatch_continuation_matches_fifo(monkeypatch, tmp_path):
    from app.services.strata_scheduling import strata_rule_package_scope

    async def run(enabled):
        seen, active_cases = [], set()
        max_active = 0
        async def fixed(request):
            nonlocal max_active
            body = json.loads(request.content)
            case_name, pack = body["messages"][0]["content"].split(":")
            assert case_name not in active_cases
            active_cases.add(case_name)
            max_active = max(max_active, len(active_cases))
            assert set(body) == {"model", "messages", "temperature", "top_p", "max_tokens", "stream", "chat_template_kwargs"}
            assert "package_key" not in body and len(body["messages"]) == 1
            seen.append(body)
            await asyncio.sleep(0)
            active_cases.remove(case_name)
            return httpx.Response(200, json=response(content=json.dumps({
                "rule_id": pack, "event_id": case_name + pack,
                "evidence_ids": [case_name], "status": "compliant"})))

        app, client = harness(monkeypatch, tmp_path, fixed, mode="off", continuation=enabled)
        async def visit(case_name):
            result = []
            with identity(patient=case_name):
                for pack in ("original", "recheck", "next"):
                    with strata_rule_package_scope(pack):
                        value = await client.generate(case_name + ":" + pack)
                        result.append(value["choices"][0]["message"]["content"])
            return result
        results = await asyncio.gather(*(visit(case_name) for case_name in ("a", "b", "c")))
        assert max_active == 2 and len(seen) == 9
        assert await app.state.gateway_runtime.shutdown()
        return results, sorted(json.dumps(body, sort_keys=True) for body in seen)

    baseline = await run(False)
    priority = await run(True)
    assert baseline == priority
