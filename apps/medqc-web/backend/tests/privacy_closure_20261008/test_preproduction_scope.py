"""PRIV004准生产当前入口/执行绑定/最终attempt的离线接缝验证。"""
import asyncio
from types import SimpleNamespace

import pytest

from offline_support import bind_execution_source, client_with_counters, load_pure_privacy, load_runner


def bundle(patient="P-A", name="合成患者甲"):
    return {"scene": "running", "institute_id": "I-A", "patient_id": patient, "visit_id": "V-" + patient, "synthetic_name": name, "medical_text": "合成无身份材料"}


def run_arguments(case, client):
    return dict(bundle=case, selected_customer_rule_ids=("LX0609-04-01-04",), evaluation_as_of_date="2026-10-08", llm_client=client, base_settings=SimpleNamespace(), model_name="synthetic")


def attempt(client, text="合成无身份材料", attempt_no=1):
    return client._perform_observed_attempt(logical_call_id="offline", attempt_no=attempt_no, headers={}, payload={"messages": [{"content": text}]})


@pytest.mark.parametrize("attempt_no", [1, 2])
def test_actual_runner_execution_binding_blocks_final_payload_before_side_effects(attempt_no):
    privacy, scope = load_pure_privacy()
    client, events = client_with_counters(scope)
    blocked = []

    async def prepare(**kwargs):
        bind_execution_source(scope=scope, privacy=privacy, kwargs=kwargs)
        with pytest.raises(privacy.PatientPrivacyViolation):
            await attempt(client, "档案别称【合成患者甲】", attempt_no)
        blocked.append(attempt_no)
        return [], SimpleNamespace()

    runner = load_runner(scope, prepare=prepare)
    result = asyncio.run(runner(**run_arguments(bundle(), client)))
    assert blocked == [attempt_no]
    assert events == []
    assert result["results"][0]["status"] == "compliant"
    assert scope.is_luxian_0609_privacy_scope_active() is False


def test_actual_runner_safe_payload_retains_normal_attempts_and_restores_scope():
    privacy, scope = load_pure_privacy()
    client, events = client_with_counters(scope)

    async def prepare(**kwargs):
        wrapped = bind_execution_source(scope=scope, privacy=privacy, kwargs=kwargs)
        assert wrapped is not client
        await attempt(client)
        await attempt(client, attempt_no=2)
        return [], SimpleNamespace()

    result = asyncio.run(load_runner(scope, prepare=prepare)(**run_arguments(bundle(), client)))
    assert result["results"][0]["status"] == "compliant"
    assert [kind for kind, _ in events] == ["observation", "capture", "transport"] * 2
    assert scope.is_luxian_0609_privacy_scope_active() is False


def test_runner_without_provider_fails_before_observation_and_keeps_failure_dto():
    privacy, scope = load_pure_privacy()
    client, events = client_with_counters(scope)

    async def prepare(**kwargs):
        await attempt(client)
        return [], SimpleNamespace()

    result = asyncio.run(load_runner(scope, prepare=prepare)(**run_arguments(bundle(), client)))
    assert result["results"][0]["status"] == "technical_error"
    assert events == []
    assert scope.is_luxian_0609_privacy_scope_active() is False


def test_same_case_scope_inherits_provider_and_other_case_cannot_use_it():
    privacy, scope = load_pure_privacy()
    payload = {"messages": [{"content": "合成患者甲"}]}

    @scope.luxian_0609_case_privacy_scope
    async def inner(*, bundle):
        return scope.protect_current_payload(payload)

    @scope.luxian_0609_privacy_scope
    async def outer(*, rule_set_key, bundle):
        scope.bind_luxian_0609_identity_provider(lambda: ("合成患者甲",))
        with pytest.raises(privacy.PatientPrivacyViolation):
            await inner(bundle=bundle)
        with pytest.raises(privacy.PrivacyIdentityContextError):
            await inner(bundle={**bundle, "patient_id": "P-B"})
        with pytest.raises(privacy.PrivacyIdentityContextError):
            await inner(bundle={"patient_id": "P-A"})
        with pytest.raises(privacy.PatientPrivacyViolation):
            scope.protect_current_payload(payload)
    asyncio.run(outer(rule_set_key="luxian_0609_qc_v1", bundle=bundle()))
    assert scope.protect_current_payload(payload) is payload


def test_concurrent_cases_have_separate_provider_and_no_identity_in_repr():
    privacy, scope = load_pure_privacy()

    @scope.luxian_0609_case_privacy_scope
    async def run(*, bundle, own, other):
        scope.bind_luxian_0609_identity_provider(lambda: (own,))
        await asyncio.sleep(0)
        scope.protect_current_payload({"messages": [{"content": other}]})
        with pytest.raises(privacy.PatientPrivacyViolation):
            scope.protect_current_payload({"messages": [{"content": own}]})
        assert own not in repr(scope._SCOPE.get())
        assert bundle["patient_id"] not in repr(scope._SCOPE.get())

    async def concurrent():
        await asyncio.gather(run(bundle=bundle(), own="合成患者甲", other="合成患者乙"), run(bundle=bundle("P-B", "合成患者乙"), own="合成患者乙", other="合成患者甲"))
    asyncio.run(concurrent())
    assert scope.is_luxian_0609_privacy_scope_active() is False


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
def test_runner_failure_or_cancel_restores_outer_case_provider(failure):
    privacy, scope = load_pure_privacy()

    async def prepare(**kwargs):
        scope.bind_luxian_0609_identity_provider(lambda: ("合成患者乙",))
        raise failure("合成错误正文")
    runner = load_runner(scope, prepare=prepare)

    @scope.luxian_0609_case_privacy_scope
    async def outer(*, bundle):
        scope.bind_luxian_0609_identity_provider(lambda: ("合成患者甲",))
        if failure is asyncio.CancelledError:
            with pytest.raises(asyncio.CancelledError):
                await runner(**run_arguments(globals()["bundle"]("P-B"), object()))
        else:
            result = await runner(**run_arguments(globals()["bundle"]("P-B"), object()))
            assert result["results"][0]["status"] == "technical_error"
        with pytest.raises(privacy.PatientPrivacyViolation):
            scope.protect_current_payload({"messages": [{"content": "合成患者甲"}]})
        scope.protect_current_payload({"messages": [{"content": "合成患者乙"}]})
    asyncio.run(outer(bundle=bundle()))
    assert scope.is_luxian_0609_privacy_scope_active() is False


def test_retry_rechecks_provider_that_becomes_invalid_after_first_send():
    privacy, scope = load_pure_privacy()
    client, events = client_with_counters(scope)
    state = {"valid": True}

    def provider():
        if not state["valid"]:
            raise ValueError("合成患者甲 provider-error")
        return ("合成患者甲",)

    @scope.luxian_0609_case_privacy_scope
    async def run(*, bundle):
        scope.bind_luxian_0609_identity_provider(provider)
        await attempt(client)
        state["valid"] = False
        with pytest.raises(privacy.PrivacyIdentityContextError) as caught:
            await attempt(client, attempt_no=2)
        assert "合成患者甲" not in str(caught.value)
    asyncio.run(run(bundle=bundle()))
    assert [kind for kind, _ in events] == ["observation", "capture", "transport"]


def test_child_task_inherited_scope_cannot_send_after_parent_case_exits():
    privacy, scope = load_pure_privacy()
    client, events = client_with_counters(scope)

    async def scenario():
        release = asyncio.Event()
        async def delayed():
            await release.wait()
            with pytest.raises(privacy.PrivacyIdentityContextError):
                await attempt(client)
        @scope.luxian_0609_case_privacy_scope
        async def parent(*, bundle):
            scope.bind_luxian_0609_identity_provider(lambda: ("合成患者甲",))
            return asyncio.create_task(delayed())
        task = await parent(bundle=bundle())
        release.set()
        await task
    asyncio.run(scenario())
    assert events == []


@pytest.mark.parametrize("inherited_failure", [False, True])
def test_runner_execution_cannot_replace_same_case_inherited_provider(inherited_failure):
    privacy, scope = load_pure_privacy()
    client, events = client_with_counters(scope)
    verified = []
    case = bundle(name="合成新材料乙")

    def existing_provider():
        if inherited_failure:
            raise ValueError("合成外层甲 private-provider-failure")
        return ("合成外层甲",)

    async def prepare(**kwargs):
        bind_execution_source(scope=scope, privacy=privacy, kwargs=kwargs)
        error = privacy.PrivacyIdentityContextError if inherited_failure else privacy.PatientPrivacyViolation
        with pytest.raises(error):
            await attempt(client, "档案别称【合成外层甲】")
        if not inherited_failure:
            with pytest.raises(privacy.PatientPrivacyViolation):
                await attempt(client, "档案别称【合成新材料乙】")
        verified.append(True)
        return [], SimpleNamespace()

    @scope.luxian_0609_case_privacy_scope
    async def outer(*, bundle):
        scope.bind_luxian_0609_identity_provider(existing_provider)
        await load_runner(scope, prepare=prepare)(**run_arguments(bundle, client))
        error = privacy.PrivacyIdentityContextError if inherited_failure else privacy.PatientPrivacyViolation
        with pytest.raises(error):
            scope.protect_current_payload({"messages": [{"content": "合成外层甲"}]})
        if not inherited_failure:
            # 内层新增身份不能回写外层provider。
            scope.protect_current_payload({"messages": [{"content": "合成新材料乙"}]})
    asyncio.run(outer(bundle=case))
    assert verified == [True]
    assert events == []
