"""双模型调用点：真实客户端／ASGI Gateway／固定应答，全部经offline入口。"""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from app.core.settings import Settings
from app.llm_gateway.config import GatewayConfigurationError, GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import create_app
from app.llm_gateway.providers import InvalidPayloadError, prepare_provider_payload
from app.services import exam_result_model_route as route
from app.services import llm_observability, qc_llm_client
from app.services.llm_dispatch import client as dispatch_module
from app.services.llm_dispatch.client import GatewayDispatchClient
from app.services.llm_dispatch.provider_profiles import ProviderConfigurationError
from app.services.llm_experiment import current_llm_experiment_namespace
from app.services.llm_observability import LLMObservabilityRecorder, NullLLMCallEventStore
from app.services.luxian_0609 import exam_result_record_check as check
from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.exam_lab_fact_extraction import ExamLabEventFact
from app.services.luxian_0609.exam_output_batching import CallBudget
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
from tests.unit.test_strata_prefix_fixed_flow import projection


def policy(mode="cascade", **changes):
    return {"mode": mode, "experiment": "A1-exam-fixed", "candidate_profile": "local_openai_exam",
            "candidate_model": "synthetic-35b", "candidate_revision": "q4-fixed-v1",
            "reference_revision": "reference-fixed-v1", **changes}


def answer(p, *, kind="none"):
    return {"schema_version": check.SCHEMA_VERSION, "docs": [
        {"event_position": position, "course_doc_ref": ref, "quote_type": kind,
         "quote": "", "report_span": ""}
        for position, (_, refs) in check._targets(p).items() for ref in refs
    ]}


def response(payload, *, finish="stop"):
    return {"choices": [{"finish_reason": finish, "message": {"content": json.dumps(payload)}}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 12, "total_tokens": 52}}


def harness(monkeypatch, tmp_path, handler, *, mode="cascade", config=None):
    settings = Settings(
        _env_file=None, JWT_SECRET="synthetic-route-key", LLM_DISPATCH_MODE="gateway",
        LLM_GATEWAY_URL="http://gateway.test", LLM_GATEWAY_TOKEN="synthetic-gateway-token-at-least-32-characters",
        LLM_GATEWAY_PROFILES={"strata": "strata_reference", "local_openai": "local_openai_exam"},
        LLM_EXAM_RESULT_ROUTING=policy(mode) if config is None else config,
        LLM_REQUEST_OBSERVATION_ENABLED=True,
    )
    for module in (route, qc_llm_client, dispatch_module, llm_observability):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    profiles = {
        "strata_reference": ProfileConfig("strata_reference", "reference", "strata", "synthetic-flash",
                                           "http://reference.test/v1/chat/completions"),
        "local_openai_exam": ProfileConfig("local_openai_exam", "candidate", "local_openai", "synthetic-35b",
                                           "http://candidate.test/v1/chat/completions"),
    }
    gateway_settings = GatewaySettings(
        token=settings.LLM_GATEWAY_TOKEN, resources={"reference": ResourceConfig("reference", 2, 2),
                                                    "candidate": ResourceConfig("candidate", 1, 1)},
        profiles=profiles, allowed_hosts=frozenset({"reference.test", "candidate.test"}),
        state_dir=tmp_path, startup_isolation_seconds=0,
    )
    app = create_app(gateway_settings, http_transport=httpx.MockTransport(handler), enforce_single_instance=False)
    client = qc_llm_client.SichuanQCLLMClient(
        {"provider_code": "strata", "model": "synthetic-flash", "api_endpoint": "http://reference.test/v1",
         "dispatch_mode": "gateway", "gateway_profile": "strata_reference"},
        gateway_dispatch_client=GatewayDispatchClient(transport=httpx.ASGITransport(app=app)),
        observability_recorder=LLMObservabilityRecorder(store=NullLLMCallEventStore()),
    )
    return settings, app, client


@pytest.mark.asyncio
async def test_candidate_transport_uses_registered_local_profile(monkeypatch, tmp_path):
    p = projection()
    _, app, client = harness(monkeypatch, tmp_path, lambda _: httpx.Response(200, json=response(answer(p))))
    with route.exam_result_route_scope(client) as session:
        candidate, target = session.selected()
        assert target == "candidate"
        raw = await candidate.generate(check._prompt(p, check._targets(p)), max_completion_tokens=4096)
    assert raw["usage"]["total_tokens"] == 52
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["off", "shadow", "cascade"])
async def test_same_request_and_result_with_only_allowlisted_model_changed(monkeypatch, tmp_path, mode, caplog):
    p, sent = projection(), []
    caplog.set_level("INFO", logger=route.__name__)

    def fixed(request):
        sent.append((request.url.host, json.loads(request.content)))
        return httpx.Response(200, json=response(answer(p)))

    _settings, app, client = harness(monkeypatch, tmp_path, fixed, mode=mode)
    original_prompt = check._prompt(p, check._targets(p))
    result = await check.check_exam_result_record(p, client)
    assert result.state == "ready" and result.llm_call_count == 1
    assert result.recorded_refs == {1: ()}
    assert len(sent) == 1
    assert sent[0][0] == ("candidate.test" if mode == "cascade" else "reference.test")
    assert sent[0][1]["messages"] == [{"role": "user", "content": original_prompt}]
    if mode == "cascade":
        assert not set(sent[0][1]) & {"chat_template_kwargs", "strata_prefix", "enable_thinking"}
    assert ("planned_target" in caplog.text) == (mode != "off")
    assert current_llm_experiment_namespace() is None and route.current_route() is None
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["truncated", "coverage", "quote", "event", "ref", "json"])
async def test_upgrade_uses_original_input_and_preserves_shared_budget(monkeypatch, tmp_path, failure):
    p, sent = projection(), []

    def fixed(request):
        payload = json.loads(request.content)
        sent.append((request.url.host, payload))
        out = answer(p)
        if request.url.host == "candidate.test":
            if failure == "truncated":
                return httpx.Response(200, json=response(out, finish="length"))
            if failure == "coverage":
                out["docs"] = []
            if failure == "quote":
                out["docs"][0].update(quote_type="result_recorded", quote="伪造引文", report_span="占位")
            if failure == "event":
                out["docs"][0]["event_position"] = 999
            if failure == "ref":
                out["docs"][0]["course_doc_ref"] = "foreign-reference"
            if failure == "json":
                out = "not a protocol object"
        return httpx.Response(200, json=response(out))

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    result = await check.check_exam_result_record(p, client)
    assert result.state == "ready" and result.llm_call_count == 2
    assert result.total_tokens == 104
    assert [host for host, _ in sent] == ["candidate.test", "reference.test"]
    assert sent[0][1]["messages"] == sent[1][1]["messages"]
    assert "伪造引文" not in sent[1][1]["messages"][0]["content"]
    assert result.recorded_refs == {1: ()}
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_upgrade_once_then_remaining_batches_use_reference(monkeypatch, tmp_path):
    p, sent = projection(), []

    def fixed(request):
        sent.append(request.url.host)
        return httpx.Response(200, json=response({"docs": []} if request.url.host == "candidate.test" else answer(p)))

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    budget = CallBudget()
    with route.exam_result_route_scope(client):
        first = await check._check_result_batch(p, client, check._targets(p), budget)
        second = await check._check_result_batch(p, client, check._targets(p), budget)
    assert first.state == second.state == "ready"
    assert sent == ["candidate.test", "reference.test", "reference.test"]
    assert budget.used == 3
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_no_budget_for_upgrade_does_not_create_extra_request(monkeypatch, tmp_path):
    p, sent = projection(), []

    def fixed(request):
        sent.append(request.url.host)
        return httpx.Response(200, json=response({"docs": []}))

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    with route.exam_result_route_scope(client):
        result = await check._check_result_batch(p, client, check._targets(p), CallBudget(maximum=1))
    assert result.state == "failed" and result.llm_call_count == 1
    assert sent == ["candidate.test"]
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http", "timeout"])
async def test_transport_failure_does_not_upgrade_or_emit_clinical_fact(monkeypatch, tmp_path, failure):
    sent = []

    def fixed(request):
        sent.append(request.url.host)
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic failure")
        return httpx.Response(400)

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    result = await check.check_exam_result_record(projection(), client)
    assert result.state == "failed" and not result.recorded_refs
    assert sent and set(sent) == {"candidate.test"} and len(sent) <= 2
    clean = await app.state.gateway_runtime.shutdown()
    if failure == "timeout":
        # 超时后远端物理请求是否终止未知：保留原Gateway隔离，不为实验清槽。
        assert clean is False
        counts = await app.state.gateway_runtime.resource_counts()
        assert next(item for item in counts if item["resource_id"] == "candidate")["unknown_inflight"] is True
    else:
        assert clean is True


@pytest.mark.asyncio
async def test_cancellation_propagates_without_reference_call(monkeypatch, tmp_path):
    started, release, sent = asyncio.Event(), asyncio.Event(), []

    async def fixed(request):
        sent.append(request.url.host)
        started.set()
        await release.wait()
        return httpx.Response(200, json=response(answer(projection())))

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    task = asyncio.create_task(check.check_exam_result_record(projection(), client))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
    assert sent == ["candidate.test"]
    assert route.current_route() is None
    await asyncio.sleep(0)
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_empty_candidates_do_not_construct_candidate(monkeypatch, tmp_path):
    def forbidden(_request):
        pytest.fail("empty candidates must not call either service")

    _, app, client = harness(monkeypatch, tmp_path, forbidden)
    monkeypatch.setattr(check, "_targets", lambda _: {})
    monkeypatch.setattr(route, "build_candidate", lambda *_: pytest.fail("candidate must stay lazy"))
    assert (await check.check_exam_result_record(projection(), client)).state == "skipped"
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.parametrize("change", [
    {"candidate_profile": "alibaba_other"}, {"candidate_revision": ""},
    {"experiment": "../baseline"}, {"candidate_parameters": {"enable_thinking": False}},
    {"candidate_parameters": {"temperature": float("nan")}}, {"secret": "do-not-log"},
])
def test_invalid_route_fails_closed(monkeypatch, change):
    monkeypatch.setattr(route, "get_settings", lambda: SimpleNamespace(LLM_EXAM_RESULT_ROUTING=policy(**change)))
    with pytest.raises(ValueError):
        route.route_policy()


def test_local_candidate_cannot_use_direct_or_strata_parameters(monkeypatch, tmp_path):
    with pytest.raises(ProviderConfigurationError, match="controlled Gateway"):
        qc_llm_client.SichuanQCLLMClient({"provider_code": "local_openai", "model": "synthetic-35b"})
    profile = ProfileConfig("local_openai_exam", "candidate", "local_openai", "synthetic-35b",
                            "http://candidate.test/v1/chat/completions")
    for key, value in (("chat_template_kwargs", {"enable_thinking": False}),
                       ("strata_prefix", {"tokens": 100}), ("enable_thinking", False)):
        with pytest.raises(InvalidPayloadError):
            prepare_provider_payload(profile, {"model": profile.model, "messages": [{"role": "user", "content": "synthetic"}], key: value})
    with pytest.raises(GatewayConfigurationError, match="one slot"):
        GatewaySettings(token="synthetic-token-at-least-32-characters", profiles={profile.name: profile},
                        resources={"candidate": ResourceConfig("candidate", 2, 1)},
                        allowed_hosts=frozenset({"candidate.test"}), state_dir=tmp_path)


@pytest.mark.asyncio
async def test_outer_family_freeze_is_partitioned_before_lookup(monkeypatch, tmp_path):
    from app.services.luxian_0609.exam_analysis_freeze import load_payload

    settings, app, client = harness(monkeypatch, tmp_path, lambda _: pytest.fail("fixed extraction owns calls"), mode="off")
    p = projection()
    fact = ExamLabEventFact(check.RULE_ID, "applicable", "absent", "not_relevant", (), ())
    calls = []

    async def fixed(**_kwargs):
        calls.append(current_llm_experiment_namespace())
        return native._ExamLabBatchResult(facts=(fact,))

    monkeypatch.setattr(native, "_extract_exam_lab_batch_uncached", fixed)
    monkeypatch.setattr(native, "_main_freeze_key", lambda *_: "same-input")
    await native._extract_exam_lab_batch(projection=p, eligible_rule_ids=[check.RULE_ID], llm_client=client)
    baseline = load_payload("main", "same-input")
    assert len(calls) == 1 and calls[0] is None and baseline is not None
    for mode in ("shadow", "cascade"):
        settings.LLM_EXAM_RESULT_ROUTING = policy(mode)
        for _ in range(2):
            await native._extract_exam_lab_batch(projection=p, eligible_rule_ids=[check.RULE_ID], llm_client=client)
        assert len(calls) == (2 if mode == "shadow" else 3)
    for index, change in enumerate(({"candidate_revision": "q4-fixed-v2"},
                                    {"reference_revision": "new-reference-revision"},
                                    {"candidate_parameters": {"temperature": 0.0}},
                                    {"candidate_model": "new-served-model"})):
        settings.LLM_EXAM_RESULT_ROUTING = policy(**change)
        await native._extract_exam_lab_batch(projection=p, eligible_rule_ids=[check.RULE_ID], llm_client=client)
        assert len(calls) == 4 + index
    assert len(set(calls)) == 7
    assert current_llm_experiment_namespace() is None
    assert load_payload("main", "same-input") == baseline
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_privacy_and_model_attribution_follow_actual_candidate(monkeypatch, tmp_path, caplog):
    p, sent = projection(extra="姓名：张模拟；"), []
    caplog.set_level("INFO", logger=route.__name__)

    def fixed(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=response(answer(p)))

    _, app, raw = harness(monkeypatch, tmp_path, fixed)
    client = wrap_luxian_0609_llm_client(raw, identity_values=("张模拟",))
    result = await check.check_exam_result_record(p, client)
    assert result.state == "ready"
    assert sent[0]["model"] == "synthetic-35b"
    assert "张模拟" not in json.dumps(sent, ensure_ascii=False)
    assert "张模拟" not in caplog.text and "candidate.test" not in caplog.text
    assert "total_tokens" in caplog.text
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_reference_is_requested_only_after_candidate_resource_released(monkeypatch, tmp_path):
    p, snapshots = projection(), []

    async def fixed(request):
        if request.url.host == "reference.test":
            snapshots.extend(await app.state.gateway_runtime.resource_counts())
            return httpx.Response(200, json=response(answer(p)))
        return httpx.Response(200, json=response({"docs": []}))

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    assert (await check.check_exam_result_record(p, client)).state == "ready"
    candidate = next(row for row in snapshots if row["resource_id"] == "candidate")
    assert candidate["inflight"] == candidate["queued"] == 0
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_candidate_resource_queue_is_bounded_and_does_not_use_reference(monkeypatch, tmp_path):
    p, started, release, sent = projection(), asyncio.Event(), asyncio.Event(), []

    async def fixed(request):
        sent.append(request.url.host)
        started.set()
        await release.wait()
        return httpx.Response(200, json=response(answer(p)))

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    with route.exam_result_route_scope(client) as session:
        candidate, _ = session.selected()
        first = asyncio.create_task(candidate.generate("synthetic first"))
        await asyncio.wait_for(started.wait(), 2)
        second = asyncio.create_task(candidate.generate("synthetic second"))
        for _ in range(100):
            rows = await app.state.gateway_runtime.resource_counts()
            if next(row for row in rows if row["resource_id"] == "candidate")["queued"] == 1:
                break
            await asyncio.sleep(0)
        assert next(row for row in rows if row["resource_id"] == "candidate")["queued"] == 1
        from app.services.llm_dispatch.client import GatewayDispatchError

        try:
            with pytest.raises(GatewayDispatchError):
                await asyncio.wait_for(candidate.generate("synthetic queue overflow"), 2)
        finally:
            release.set()
            await asyncio.gather(first, second)
    assert sent == ["candidate.test", "candidate.test"]
    assert await app.state.gateway_runtime.shutdown()


def test_task_identity_rejects_route_changes_and_off_keeps_legacy_shape(monkeypatch):
    from app.services.luxian_0609 import rule_decision_settings as runtime

    settings = SimpleNamespace(LLM_EXAM_RESULT_ROUTING={})
    monkeypatch.setattr(route, "get_settings", lambda: settings)
    client = SimpleNamespace(provider_code="strata", model="synthetic-flash", api_endpoint="synthetic",
                             dispatch_mode="gateway", gateway_profile="strata_reference",
                             gateway_endpoint_sha256="a" * 64)
    service = SimpleNamespace(client=client, adjudicator_client=client)
    baseline = runtime.capture_luxian_0609_task_runtime(service)
    assert "exam_result_route" not in baseline["implementation"]
    settings.LLM_EXAM_RESULT_ROUTING = policy()
    frozen = runtime.capture_luxian_0609_task_runtime(service)
    with pytest.raises(ValueError):
        runtime.assert_luxian_0609_task_runtime_match(baseline, service)
    runtime.assert_luxian_0609_task_runtime_match(frozen, service)
    settings.LLM_EXAM_RESULT_ROUTING = policy(candidate_revision="other-quantization")
    with pytest.raises(ValueError):
        runtime.assert_luxian_0609_task_runtime_match(frozen, service)


def test_prefix_experiment_cannot_silently_change_dual_model_prompt(monkeypatch):
    monkeypatch.setattr(route, "get_settings", lambda: SimpleNamespace(
        LLM_EXAM_RESULT_ROUTING=policy(), STRATA_CASE_CACHE_MODE="prefix"))
    with pytest.raises(ProviderConfigurationError, match="legacy Prompt"):
        route.route_policy()


@pytest.mark.asyncio
async def test_route_contexts_are_isolated_between_concurrent_cases(monkeypatch, tmp_path):
    _, app, client = harness(monkeypatch, tmp_path, lambda _: pytest.fail("scope-only test"))

    async def run(upgrade):
        with route.exam_result_route_scope(client) as session:
            namespace = current_llm_experiment_namespace()
            if upgrade:
                assert session.upgrade()
            await asyncio.sleep(0)
            assert session.reference_only is upgrade
            assert current_llm_experiment_namespace() == namespace
            return id(session)

    identities = await asyncio.gather(run(True), run(False))
    assert identities[0] != identities[1]
    assert current_llm_experiment_namespace() is None
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_real_native_binding_finalizer_and_saved_result_preserved_across_routes(monkeypatch, tmp_path):
    from datetime import datetime
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    from tests.unit.test_luxian_0609_native_exam_lab_execution import _typed_session, _fact_response
    from app.services import custom_qc_workspace_service as workspace
    from app.services.luxian_0609.exam_lab_fact_extraction import build_exam_lab_text_projection
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
                    "record_content": "稳定观察，拟完善胸部CT，外院超声提示胆囊结石。"},)
    horizon = ({"discharge_datetime": "2026-01-05 12:00:00"},)
    evaluation = ({"horizon_datetime": "2026-01-05 12:00:00", "horizon_date": "2026-01-05"},)
    snapshot, materials = _typed_session(monkeypatch, exam_rows=exam_rows, course_rows=course_rows,
                                         discharge_horizon_rows=horizon, evaluation_horizon_rows=evaluation)
    p = build_exam_lab_text_projection(rows_by_source={"exam_master": exam_rows,
        "daily_course_record": course_rows, "inpat_registration.discharge_horizon": horizon,
        "evaluation_context.horizon": evaluation})
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    compared = []
    try:
        for mode in ("off", "shadow", "cascade", "upgrade"):
            sent = []

            def fixed(request):
                payload = json.loads(request.content)
                sent.append((request.url.host, payload))
                if check.SCHEMA_VERSION not in payload["messages"][0]["content"]:
                    assert request.url.host == "reference.test"
                    return httpx.Response(200, json=response(_fact_response((check.RULE_ID,))))
                value = {"schema_version": check.SCHEMA_VERSION, "docs": []} if mode == "upgrade" and request.url.host == "candidate.test" else answer(p)
                return httpx.Response(200, json=response(value))

            config = policy("cascade" if mode == "upgrade" else mode,
                            experiment="A1-formal-" + mode)
            _, app, client = harness(monkeypatch, tmp_path / mode, fixed, config=config)
            batch = await native._extract_exam_lab_batch(projection=p, eligible_rule_ids=[check.RULE_ID], llm_client=client)
            assert batch.facts is not None and not batch.rule_failures and not batch.incomplete_specialty_rule_ids
            assert batch.llm_call_count == (3 if mode == "upgrade" else 2)
            assert [host for host, _ in sent] == {
                "off": ["reference.test", "reference.test"],
                "shadow": ["reference.test", "reference.test"],
                "cascade": ["reference.test", "candidate.test"],
                "upgrade": ["reference.test", "candidate.test", "reference.test"],
            }[mode]
            outcome = native._text_fact_outcome(rule_id=check.RULE_ID, facts=batch.facts, projection=p)
            decision = native._decision_from_outcome(outcome=outcome, snapshot=snapshot)
            [reduced] = bind_and_reduce_luxian_0609_rule_decisions(decisions=(decision,),
                expected_rule_ids=(check.RULE_ID,), snapshot=snapshot, evidence_materials=materials)
            display = native._display_facts_for_text_outcome(rule_id=check.RULE_ID, facts=batch.facts,
                                                            projection=p, outcome=outcome)
            final = finalize_luxian_0609_reduced_customer_result(decision=reduced,
                raw_customer_display_facts=display, evidence_snapshot=snapshot, evidence_materials=materials)
            assert final["status"] == "non_compliant" and final["customer_evidence"]
            [published] = aggregate_luxian_0609_results(wrapper_rules=[get_luxian_0609_rule(check.RULE_ID)],
                execution_results=[], canonical_results=(final,), delivery_mode=CANONICAL_RESULT_DELIVERY_MODE)
            job_id = "synthetic-dual-" + mode
            ref = {"institute_id": "safe-institute", "patient_id": "safe-patient", "visit_id": "safe-visit"}
            with Session(engine) as session:
                store.replace_for_job(session, job_row={"id": job_id, "created_by": "synthetic-tester",
                    "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                        "scoped_customer_rule_ids": [check.RULE_ID], "record_refs": [ref]})},
                    items=[{**published, **ref, "record_id": ref["visit_id"]}], now=datetime(2026, 1, 6),
                    projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="synthetic-ref-key"),
                    projection_key="synthetic-ref-key")
                session.commit()
                saved = store.load_selected(session, root_job_id=job_id, **ref,
                    rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")["items"][0]
            compared.append((batch.facts, reduced, final, {key: saved.get(key) for key in
                ("rule_id", "status", "reason_code", "customer_display_facts", "customer_evidence", "conclusion")}))
            hot = await native._extract_exam_lab_batch(projection=p, eligible_rule_ids=[check.RULE_ID], llm_client=client)
            assert hot.llm_call_count == 0 and hot.facts == batch.facts
            assert await app.state.gateway_runtime.shutdown()
        assert all(value == compared[0] for value in compared[1:])
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_exhausted_time_budget_does_not_send_to_either_service(monkeypatch, tmp_path):
    from app.services.luxian_0609.execution_time_budget import execution_time_budget

    _, app, client = harness(monkeypatch, tmp_path, lambda _: pytest.fail("deadline must prevent HTTP"))
    with execution_time_budget(0):
        result = await check.check_exam_result_record(projection(), client)
    assert result.state == "failed" and not result.recorded_refs
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_bad_observer_does_not_change_accepted_result(monkeypatch, tmp_path):
    p = projection()
    _, app, client = harness(monkeypatch, tmp_path, lambda _: httpx.Response(200, json=response(answer(p))))

    def broken(*_args, **_kwargs):
        raise RuntimeError("synthetic side-channel failure")

    monkeypatch.setattr(route.logger, "info", broken)
    assert (await check.check_exam_result_record(p, client)).state == "ready"
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_changed_candidate_mapping_fails_before_family_cache_lookup(monkeypatch, tmp_path):
    settings, app, client = harness(monkeypatch, tmp_path, lambda _: pytest.fail("no HTTP expected"))
    settings.LLM_GATEWAY_PROFILES["local_openai"] = "local_openai_other"
    monkeypatch.setattr(native, "_load_frozen_exam_lab_batch", lambda *_args, **_kwargs: pytest.fail("must validate before cache"))
    with pytest.raises(ProviderConfigurationError, match="mapping"):
        await native._extract_exam_lab_batch(projection=projection(), eligible_rule_ids=[check.RULE_ID], llm_client=client)
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_known_input_projection_limit_keeps_reference_and_records_ineligibility(monkeypatch, tmp_path, caplog):
    p, sent = projection(extra="合成长文尾部。" * 1000), []
    caplog.set_level("INFO", logger=route.__name__)

    def fixed(request):
        sent.append((request.url.host, json.loads(request.content)))
        return httpx.Response(200, json=response(answer(p)))

    _, app, client = harness(monkeypatch, tmp_path, fixed)
    result = await check.check_exam_result_record(p, client)
    assert result.state == "ready"
    assert [host for host, _ in sent] == ["reference.test"]
    assert sent[0][1]["messages"] == [{"role": "user", "content": check._prompt(p, check._targets(p))}]
    assert "input_projection_limit" in caplog.text and '"input_complete": false' in caplog.text
    assert await app.state.gateway_runtime.shutdown()
