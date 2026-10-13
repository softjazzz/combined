"""PRIV003先红：执行三个现有脚本AST与actual attempt；外部接缝全内存。"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from offline_support import client_with_counters, load_pure_privacy, load_script_namespace


ORDINARY = "run_luxian_0609_consultation_ordinary_shadow_validation.py"
SEMANTIC = "review_luxian_0609_semantic20.py"
GOLDEN = "run_luxian_0609_028_synthetic_golden.py"


def delegate():
    _, scope = load_pure_privacy()
    client, events = client_with_counters(scope)
    async def generate(prompt):
        return await client._perform_observed_attempt(
            payload={"messages": [{"role": "user", "content": prompt}]},
            headers={}, logical_call_id="offline-script-call", attempt_no=1,
        )
    return SimpleNamespace(generate=generate), events


def source_errors(namespace):
    _, scope = load_pure_privacy()
    return (scope.PrivacyIdentityContextError,
            namespace["PrivacyIdentityContextUnavailable"])


def ordinary_namespace(coordinates, prompt="合成原名甲维持130mg，观察1.5h"):
    client, events = delegate()
    external = []
    source = dict(zip(("institute_id", "patient_id", "visit_id"), coordinates))
    session = SimpleNamespace(snapshot=None, materials=None)
    async def native(**kwargs):
        await kwargs["llm_client"].generate(prompt)
        return SimpleNamespace(results=[], llm_call_count=1, prompt_tokens=0,
                               completion_tokens=0, total_tokens=0, api_time=0)
    episode = SimpleNamespace(
        _candidate_documents=lambda **kwargs: SimpleNamespace(source_complete_keys=[], source_incomplete_keys=[]),
        _resolve_execution_stay_window=lambda **kwargs: None,
        execute_luxian_0609_native_consultation_episode_rules=native,
    )
    ns = load_script_namespace(
        ORDINARY, DB_SCHEMA_MODE="single", episode=episode,
        read_ordinary_consultation_source_rows=lambda **kwargs: external.append("source") or [source],
        select_ordinary_consultation_cases=lambda rows, **kwargs: {
            "cases": [{"coordinate_hash": "fixed", "case_label": "case-01"}],
            "selector_fingerprint": "0" * 64,
        },
        _coordinate_hash=lambda row: "fixed",
        build_luxian_0609_evidence_read_session=lambda **kwargs: session,
        SichuanQCLLMClient=lambda: external.append("config") or client,
        datetime=datetime, timezone=timezone,
    )
    ns["build_safe_ledger_rows"] = lambda **kwargs: []
    return ns, events, external


@pytest.mark.parametrize("coordinates", [("I-A", "P-A", "V-A"), ("SYNTHETIC-I", "SYNTHETIC-P", "golden-01-24h")])
def test_ordinary_missing_source_cannot_use_three_ids_or_synthetic_label(coordinates):
    ns, events, _ = ordinary_namespace(coordinates)
    with pytest.raises(source_errors(ns)):
        asyncio.run(ns["_run"](snapshot_as_of="2026-01-01", limit_rows=20))
    assert events == []


def semantic_namespace(branch):
    client, events = delegate()
    ns = load_script_namespace(SEMANTIC)
    case = {"case_label": "case-01", "institute_id": "I-A", "patient_id": "P-A", "visit_id": "V-A"}
    rule = "LX0609-12-01-02" if branch == "copy" else "LX0609-03-01-01"
    target = {"case_label": "case-01", "rule_id": rule}
    ns.update(
        _case_rows=lambda raw: (case,), _review_rows=lambda raw: (target,),
        _candidate_index=lambda raw: {("case-01", rule): {}},
        _copy_review_context=lambda raw: ("合成原名甲维持130mg，观察1.5h", {}),
        consultation_context=lambda raw: "合成原名甲维持130mg，观察1.5h",
        _evidence_hashes=lambda **kwargs: [], _usage=lambda response: {},
        _parse_reviews=lambda response, rules: {
            key: {"state": "compliant", "reason": "safe_reason", "confidence": "high"} for key in rules
        },
        _validate_safe_output=lambda output: None,
    )
    return ns, client, events


@pytest.mark.parametrize("branch", ["copy", "consultation"])
def test_semantic_both_generate_branches_refuse_missing_source(branch):
    ns, client, events = semantic_namespace(branch)
    try:
        output = asyncio.run(ns["build_semantic20_review"](
            case_map={}, candidate={}, review_queue=[], llm_client=client,
            row_loader=lambda **kwargs: [{"record_content": "合成材料"}],
        ))
    except source_errors(ns):
        output = None
    assert events == []
    if output is not None:
        assert output["summary"]["completed_count"] == 0
        assert output["rows"][0]["review_reason_code"] == "privacy_boundary_error"
        assert output["usage"]["call_count"] == 0


def golden_namespace():
    client, events = delegate()
    async def native(**kwargs):
        await kwargs["llm_client"].generate("SYNTHETIC-P维持130mg，观察1.5h")
        return SimpleNamespace(decisions=[], llm_call_count=1, total_tokens=0)
    ns = load_script_namespace(
        GOLDEN, SichuanQCLLMClient=lambda config: client,
        build_adjudicator_runtime_config=lambda: object(),
        execute_luxian_0609_native_surgery_gate_rules=native,
        bind_and_reduce_luxian_0609_rule_decisions=lambda **kwargs: [
            SimpleNamespace(final_state=SimpleNamespace(value="compliant"))
        ],
        build_luxian_0609_evidence_read_session=lambda **kwargs: SimpleNamespace(snapshot=None, materials=None),
        SnapshotSourceRows=SimpleNamespace(create=lambda **kwargs: kwargs),
    )
    return ns, events


def test_golden_actual_attempt_cannot_send_residual_synthetic_identity():
    ns, events = golden_namespace()
    privacy, _ = load_pure_privacy()
    with pytest.raises(privacy.PatientPrivacyViolation):
        asyncio.run(ns["_run"]())
    assert events == []


@pytest.mark.parametrize("label", ["golden-01-24h", "SYNTHETIC-P"])
def test_golden_rejects_new_scenario_even_with_existing_or_synthetic_label(label):
    ns, events = golden_namespace()
    forged = ns["Scenario"](label, "compliant", "I", "任意来源材料合成原名甲")
    with pytest.raises(source_errors(ns)):
        ns["_session_for"](forged)
    assert events == []


def test_golden_rejects_replaced_scenario_tuple_before_any_attempt():
    ns, events = golden_namespace()
    ns["SCENARIOS"] = (ns["Scenario"](
        "golden-01-24h", "compliant", "I", "任意替换来源合成原名甲",
    ),)
    with pytest.raises(source_errors(ns)):
        asyncio.run(ns["_run"]())
    assert events == []


def collector_for(namespace, coordinates=("I-A", "P-A", "V-A"), *, name="合成原名甲"):
    collector = namespace["_Luxian0609IdentityCollector"]()
    collector.capture("mr", SimpleNamespace(
        institute_id=coordinates[0], patient_id=coordinates[1], visit_id=coordinates[2],
        name=name, mr_no="MR-RAW-A", contact_name="合成联系人甲",
    ))
    return collector


def event_count(events, kind):
    return sum(event[0] == kind for event in events)


def test_ordinary_valid_collected_source_allows_privacy_processed_clinical_text():
    ns, events, external = ordinary_namespace(("I-A", "P-A", "V-A"), "患者姓名：合成原名甲；维持130mg，观察1.5h")
    collector = collector_for(ns)
    try:
        asyncio.run(ns["_run"](snapshot_as_of="2026-01-01", limit_rows=20,
                    _private_identity_collector=collector))
        assert event_count(events, "transport") == 1
        payload = next(value for kind, value in events if kind == "transport")
        text = payload["messages"][0]["content"]
        assert "130mg" in text and "1.5h" in text and "合成原名甲" not in text
        assert external == ["source", "config"]
    finally:
        collector.close()


@pytest.mark.parametrize("mode", ["dict", "callable", "three_ids", "masked", "wrong_case", "closed"])
def test_ordinary_does_not_trust_unverified_or_unavailable_source(mode):
    ns, events, _ = ordinary_namespace(("I-A", "P-A", "V-A"))
    collector = collector_for(ns, ("I-A", "P-B", "V-B") if mode == "wrong_case" else ("I-A", "P-A", "V-A"),
                              name="" if mode == "three_ids" else "合成*甲" if mode == "masked" else "合成原名甲")
    supplied = {"name": "合成原名甲"} if mode == "dict" else (lambda: ("合成原名甲",)) if mode == "callable" else collector
    if mode == "closed":
        collector.close()
    try:
        with pytest.raises(source_errors(ns)):
            asyncio.run(ns["_run"](snapshot_as_of="2026-01-01", limit_rows=20,
                                 _private_identity_collector=supplied))
        assert events == []
    finally:
        collector.close()


@pytest.mark.parametrize("branch", ["copy", "consultation"])
def test_semantic_valid_source_allows_normal_transport_and_business_double(branch):
    ns, client, events = semantic_namespace(branch)
    ns["_copy_review_context"] = lambda raw: ("患者姓名：合成原名甲；维持130mg，观察1.5h", {})
    ns["consultation_context"] = lambda raw: "患者姓名：合成原名甲；维持130mg，观察1.5h"
    collector = collector_for(ns)
    try:
        output = asyncio.run(ns["build_semantic20_review"](
            case_map={}, candidate={}, review_queue=[], llm_client=client,
            row_loader=lambda **kwargs: [{"record_content": "安全合成临床材料"}],
            _private_identity_collector=collector,
        ))
        assert event_count(events, "transport") == 1
        assert output["summary"]["completed_count"] == 1
        assert output["usage"]["call_count"] == 1
        text = next(value for kind, value in events if kind == "transport")["messages"][0]["content"]
        assert "130mg" in text and "1.5h" in text and "合成原名甲" not in text
    finally:
        collector.close()


@pytest.mark.parametrize("branch", ["copy", "consultation"])
@pytest.mark.parametrize("mode", ["residual", "wrong_row_case", "closed", "masked", "dict"])
def test_semantic_privacy_failure_is_fixed_error_without_model_attempt(branch, mode):
    ns, client, events = semantic_namespace(branch)
    collector = collector_for(ns, name="合成*甲" if mode == "masked" else "合成原名甲")
    if mode == "closed":
        collector.close()
    row = {"record_content": "安全合成材料"}
    if mode == "wrong_row_case":
        row.update(institute_id="I-A", patient_id="P-B", visit_id="V-B")
    try:
        output = asyncio.run(ns["build_semantic20_review"](
            case_map={}, candidate={}, review_queue=[], llm_client=client,
            row_loader=lambda **kwargs: [row],
            _private_identity_collector={"name": "合成原名甲"} if mode == "dict" else collector,
        ))
        assert events == []
        assert output["summary"]["completed_count"] == 0
        assert output["rows"][0]["review_reason_code"] == "privacy_boundary_error"
        assert output["rows"][0]["agreement"] is None
        assert output["usage"]["call_count"] == 0
    finally:
        collector.close()


def safe_golden_native(namespace, hook=None):
    async def native(**kwargs):
        if hook is None:
            await kwargs["llm_client"].generate("维持130mg，观察1.5h")
        else:
            await hook(kwargs["llm_client"])
        return SimpleNamespace(decisions=[kwargs["visit_id"]], llm_call_count=1, total_tokens=0)
    expected = {item.label: item.expected for item in namespace["SCENARIOS"]}
    namespace.update(
        execute_luxian_0609_native_surgery_gate_rules=native,
        bind_and_reduce_luxian_0609_rule_decisions=lambda **kwargs: [
            SimpleNamespace(final_state=SimpleNamespace(value=expected[kwargs["decisions"][0]]))
        ],
    )


def test_fixed_golden_normal_scenarios_send_and_keep_mocked_expected_contract():
    ns, events = golden_namespace()
    safe_golden_native(ns)
    report = asyncio.run(ns["_run"]())
    assert report["case_count"] == 10 and report["passed"] == 10
    assert report["privacy_safe"] is True
    assert event_count(events, "transport") == 10
    for kind, payload in events:
        if kind == "transport":
            text = payload["messages"][0]["content"]
            assert "130mg" in text and "1.5h" in text
            assert "SYNTHETIC-P" not in text


def test_golden_delayed_children_cannot_send_after_each_case_scope_closes():
    ns, events = golden_namespace()
    async def run():
        release = asyncio.Event()
        tasks = []
        async def hook(client):
            async def delayed():
                await release.wait()
                await client.generate("维持130mg，观察1.5h")
            tasks.append(asyncio.create_task(delayed()))
        safe_golden_native(ns, hook)
        await ns["_run"]()
        release.set()
        errors = await asyncio.gather(*tasks, return_exceptions=True)
        assert len(errors) == 10
        assert all(isinstance(error, source_errors(ns)) for error in errors)
    asyncio.run(run())
    assert events == []


@pytest.mark.parametrize("failure", ["exception", "cancel"])
def test_ordinary_exception_or_cancel_closes_scope_but_not_borrowed_collector(failure):
    ns, events, _ = ordinary_namespace(("I-A", "P-A", "V-A"))
    collector = collector_for(ns)
    _, scope = load_pure_privacy()
    async def native(**kwargs):
        if failure == "cancel":
            raise asyncio.CancelledError()
        raise RuntimeError("合成异常原名甲")
    ns["episode"].execute_luxian_0609_native_consultation_episode_rules = native
    try:
        with pytest.raises(asyncio.CancelledError if failure == "cancel" else RuntimeError):
            asyncio.run(ns["_run"](snapshot_as_of="2026-01-01", limit_rows=20,
                                 _private_identity_collector=collector))
        assert not scope.is_luxian_0609_privacy_scope_active()
        assert collector.provider_for_case(ns["CaseRef"]("I-A", "P-A", "V-A"))()
        assert events == []
    finally:
        collector.close()


def test_ordinary_closed_source_before_second_actual_attempt_is_not_cached():
    ns, _, _ = ordinary_namespace(("I-A", "P-A", "V-A"), "维持130mg，观察1.5h")
    collector = collector_for(ns)
    _, scope = load_pure_privacy()
    client, events = client_with_counters(scope)
    async def generate(prompt):
        payload = {"messages": [{"role": "user", "content": "维持130mg，观察1.5h"}]}
        await client._perform_observed_attempt(payload=payload, headers={}, logical_call_id="retry", attempt_no=1)
        collector.close()
        await client._perform_observed_attempt(payload=payload, headers={}, logical_call_id="retry", attempt_no=2)
    try:
        with pytest.raises(scope.PrivacyIdentityContextError):
            asyncio.run(ns["_run"](snapshot_as_of="2026-01-01", limit_rows=20,
                llm_client=SimpleNamespace(generate=generate), _private_identity_collector=collector))
        assert [value for kind, value in events if kind == "observation"] == [1]
        assert event_count(events, "transport") == 1
    finally:
        collector.close()


@pytest.mark.parametrize("entry", ["ordinary", "semantic"])
def test_real_cli_refuses_before_source_or_runtime_configuration(entry, capsys):
    if entry == "ordinary":
        ns, events, external = ordinary_namespace(("I-A", "P-A", "V-A"))
        code = ns["main"](["--snapshot-as-of", "2026-01-01"])
    else:
        ns = load_script_namespace(SEMANTIC)
        events, external = [], []
        ns["_load_json"] = lambda path: external.append("file") or {}
        ns["_build_llm_client"] = lambda: external.append("config")
        code = ns["main"](["--case-map", "not-read.json", "--candidate", "not-read.json",
                           "--review-queue", "not-read.json", "--output", "not-written.json"])
    assert code == 1 and events == [] and external == []
    assert "trusted in-memory identity source" in capsys.readouterr().err


LEGACY_TEST_NAMES = (
    "test_review_maps_exact_80_queue_and_rejects_candidate_duplicates_or_missing",
    "test_candidate_state_never_enters_prompt_and_each_case_uses_at_most_two_calls",
    "test_medium_or_low_confidence_is_forced_to_unknown",
    "test_not_applicable_is_a_valid_high_confidence_review_state",
    "test_one_invalid_consultation_rule_does_not_fail_three_valid_rules",
    "test_consultation_accepts_complete_json_list_inside_think_fence_and_prose",
    "test_copy_template_shell_or_dynamic_update_is_synthesized_compliant",
    "test_invalid_json_is_review_error_and_does_not_echo_raw_response",
    "test_transport_error_is_review_error",
    "test_output_is_allowlisted_and_contains_no_raw_body_coordinates_or_prompt",
)


@pytest.mark.parametrize("name", LEGACY_TEST_NAMES)
def test_original_semantic_assertions_with_explicit_synthetic_source(name):
    from offline_support import load_semantic_legacy_tests
    ns = load_semantic_legacy_tests()
    try:
        asyncio.run(ns[name]())
    finally:
        for collector in ns["_IDENTITY_COLLECTORS"]:
            collector.close()
        ns["_IDENTITY_COLLECTORS"].clear()


def test_concurrent_ordinary_cases_keep_providers_and_failure_isolated():
    left, left_events, _ = ordinary_namespace(("I-A", "P-A", "V-A"))
    right, right_events, _ = ordinary_namespace(("I-A", "P-B", "V-B"), "维持130mg，观察1.5h")
    collectors = [collector_for(left), collector_for(right, ("I-A", "P-B", "V-B"), name="合成原名乙")]
    for namespace in [left, right]:
        original = namespace["episode"].execute_luxian_0609_native_consultation_episode_rules
        async def yielding_native(original=original, **kwargs):
            await asyncio.sleep(0)
            return await original(**kwargs)
        namespace["episode"].execute_luxian_0609_native_consultation_episode_rules = yielding_native
    async def run():
        return await asyncio.gather(*[
            namespace["_run"](snapshot_as_of="2026-01-01", limit_rows=20,
                              _private_identity_collector=collector)
            for namespace, collector in zip([left, right], collectors)
        ], return_exceptions=True)
    try:
        result = asyncio.run(run())
        privacy, scope = load_pure_privacy()
        assert isinstance(result[0], privacy.PatientPrivacyViolation)
        assert result[1] == []
        assert left_events == [] and event_count(right_events, "transport") == 1
        assert not scope.is_luxian_0609_privacy_scope_active()
    finally:
        for collector in collectors:
            collector.close()


def test_same_case_ordinary_preserves_outer_collected_identity_and_lease():
    ns, events, _ = ordinary_namespace(("I-A", "P-A", "V-A"), "合成外层原名甲维持130mg")
    inner, outer = collector_for(ns), collector_for(ns, name="合成外层原名甲")
    privacy, scope = load_pure_privacy()
    async def run():
        coordinates = ("I-A", "P-A", "V-A")
        with scope.luxian_0609_case_identity_scope(
            case_coordinates=coordinates, identity_provider=outer.provider_for_case(ns["CaseRef"](*coordinates)),
        ):
            with pytest.raises(privacy.PatientPrivacyViolation):
                await ns["_run"](snapshot_as_of="2026-01-01", limit_rows=20,
                                 _private_identity_collector=inner)
            assert scope.protect_current_payload({"messages": [{"content": "维持130mg"}]})
        assert not scope.is_luxian_0609_privacy_scope_active()
    try:
        asyncio.run(run())
        assert events == []
    finally:
        inner.close()
        outer.close()


def test_semantic_normal_phone_style_marker_is_processed_before_transport():
    ns, client, events = semantic_namespace("copy")
    ns["_copy_review_context"] = lambda raw: ("PHONE_13800138000_BEARER_SECRET；维持130mg，观察1.5h", {})
    collector = collector_for(ns)
    try:
        output = asyncio.run(ns["build_semantic20_review"](
            case_map={}, candidate={}, review_queue=[], llm_client=client,
            row_loader=lambda **kwargs: [{"record_content": "安全合成临床材料"}],
            _private_identity_collector=collector,
        ))
        assert output["summary"]["completed_count"] == 1
        text = next(value for kind, value in events if kind == "transport")["messages"][0]["content"]
        assert "PHONE_13800138000_BEARER_SECRET" not in text
        assert "13800138000" not in text
        assert "130mg" in text and "1.5h" in text
    finally:
        collector.close()
