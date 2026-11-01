"""连续包选择只影响控制面；用假时钟和固定应答验证边界。"""

from dataclasses import dataclass

import asyncio
import hashlib
from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.llm_gateway.admission import (
    AdmissionDeadlineError,
    GatewayShuttingDownError,
    QueueFullError,
    ResourceAdmissionPool,
    ResourceQuarantinedError,
)
from app.llm_gateway.config import GatewayConfigurationError, ResourceConfig
from app.services import llm_observability
from app.services.llm_dispatch.contracts import GatewayCompletionRequest
from app.services.strata_scheduling import (
    current_strata_package_key,
    strata_rule_package_scope,
)


from app.llm_gateway.config import CaseContinuationConfig
from app.llm_gateway.continuation import CaseContinuationPolicy


@dataclass
class Candidate:
    case_key: str
    package_key: str | None
    queued_at: float


def config(**overrides):
    return CaseContinuationConfig(
        **{
            "enabled": True,
            "burst_requests": 4,
            "turn_seconds": 30,
            "fair_wait_seconds": 30,
            "idle_grace_seconds": 0.05,
            **overrides,
        }
    )


def test_same_package_then_next_package_get_priority_with_bounded_gap():
    policy = CaseContinuationPolicy(config())
    policy.granted("a", "one", 0, capacity=1)
    policy.released("a", 1)
    old = Candidate("b", "x", 0.1)
    next_pack = Candidate("a", "two", 1)
    same = Candidate("a", "one", 1)
    selected, _ = policy.choose([old, next_pack, same], set(), 1.01, capacity=1)
    assert selected is same
    selected, wake = policy.choose([old, next_pack], set(), 1.01, capacity=1)
    assert selected is None and wake == 1.05
    selected, _ = policy.choose([old, next_pack], set(), 1.06, capacity=1)
    assert selected is next_pack


def test_burst_turn_limit_and_aged_waiter_force_yield():
    for overrides, now in (
        ({"burst_requests": 1}, 1.01),
        ({"turn_seconds": 1}, 1.01),
        ({"fair_wait_seconds": 0.2}, 1.01),
    ):
        policy = CaseContinuationPolicy(config(**overrides))
        policy.granted("a", "one", 0, capacity=1)
        policy.released("a", 1)
        old = Candidate("b", "x", 0.1)
        same = Candidate("a", "one", 0.05)
        candidates = [old, same] if "fair_wait_seconds" in overrides else [same, old]
        selected, _ = policy.choose(candidates, set(), now, capacity=1)
        assert selected is old


def test_short_gap_expires_and_cannot_hold_model_work_for_missing_followup():
    policy = CaseContinuationPolicy(config())
    policy.granted("a", "one", 0, capacity=1)
    policy.released("a", 1)
    other = Candidate("b", "x", 0.1)
    selected, wake = policy.choose([other], set(), 1.01, capacity=1)
    assert selected is None and wake == 1.05
    assert policy.choose([other], set(), 1.06, capacity=1)[0] is other


def test_two_case_turns_do_not_reserve_unused_second_slot_and_legacy_is_fifo():
    policy = CaseContinuationPolicy(config())
    policy.granted("a", "one", 0, capacity=2)
    other = Candidate("b", "x", 0.1)
    assert policy.choose([other], {"a"}, 0.1, capacity=2)[0] is other
    legacy = Candidate("legacy", None, 0.01)
    assert policy.choose([legacy, other], {"a"}, 0.1, capacity=2)[0] is legacy


def key(value):
    return hashlib.sha256(value.encode()).hexdigest()


async def wait_queued(pool, count):
    for _ in range(100):
        if (await pool.snapshot())["queued"] == count:
            return
        await asyncio.sleep(0)
    raise AssertionError("queue did not reach expected size")


def acquire(pool, case, pack="one", seconds=2):
    return pool.acquire(
        monotonic_deadline=asyncio.get_running_loop().time() + seconds,
        case_key=key(case),
        package_key=key(pack) if pack else None,
    )


@pytest.mark.asyncio
async def test_pool_continues_package_then_case_and_yields_at_burst_limit():
    pool = ResourceAdmissionPool(
        ResourceConfig("local", 1, 5), continuation=config(burst_requests=3)
    )
    first = await acquire(pool, "a")
    other = asyncio.create_task(acquire(pool, "b"))
    await wait_queued(pool, 1)
    next_package = asyncio.create_task(acquire(pool, "a", "two"))
    same = asyncio.create_task(acquire(pool, "a"))
    await wait_queued(pool, 3)
    await first.release()
    same_lease = await asyncio.wait_for(same, 1)
    assert not other.done() and not next_package.done()
    await same_lease.release()
    # 短间隙不是模型lease；等待后同病例下一包继续。
    assert (await pool.snapshot())["inflight"] == 0
    next_lease = await asyncio.wait_for(next_package, 1)
    more = asyncio.create_task(acquire(pool, "a", "three"))
    await wait_queued(pool, 2)
    await next_lease.release()
    other_lease = await asyncio.wait_for(other, 1)
    assert not more.done()
    await other_lease.release()
    await (await asyncio.wait_for(more, 1)).release()
    await pool.close()
    snapshot = await pool.snapshot()
    assert (
        snapshot["inflight"]
        == snapshot["queued"]
        == snapshot["continuation_cases"]
        == 0
    )
    assert not snapshot["continuation_wakeup_pending"]


@pytest.mark.asyncio
async def test_three_cases_cap_two_and_same_case_serial_with_fixed_responses():
    pool = ResourceAdmissionPool(ResourceConfig("local", 2, 16), continuation=config())
    active = set()
    maximum = 0
    observed = []

    async def execute(case, pack):
        nonlocal maximum
        async with await acquire(pool, case, pack):
            assert case not in active
            active.add(case)
            maximum = max(maximum, len(active))
            await asyncio.sleep(0)
            observed.append(
                (
                    case,
                    pack,
                    {
                        "rule_id": pack,
                        "event_id": case + pack,
                        "evidence_ids": [case],
                        "status": "compliant",
                    },
                )
            )
            active.remove(case)

    async def run_case(case):
        for pack in ("original", "recheck", "next"):
            await execute(case, pack)

    await asyncio.gather(*(run_case(case) for case in ("a", "b", "c")))
    assert maximum == 2
    assert len(observed) == 9
    assert {(case, pack) for case, pack, _ in observed} == {
        (case, pack)
        for case in ("a", "b", "c")
        for pack in ("original", "recheck", "next")
    }
    await pool.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["timeout", "cancel", "close", "quarantine"])
async def test_gap_waiter_timeout_cancel_close_and_quarantine_leave_no_lease(outcome):
    pool = ResourceAdmissionPool(
        ResourceConfig("local", 1, 2), continuation=config(idle_grace_seconds=0.2)
    )
    first = await acquire(pool, "a")
    task = asyncio.create_task(
        acquire(pool, "b", seconds=0.02 if outcome == "timeout" else 2)
    )
    await wait_queued(pool, 1)
    await first.release()
    assert (await pool.snapshot())["continuation_wakeup_pending"]
    if outcome == "cancel":
        task.cancel()
        expected = asyncio.CancelledError
    elif outcome == "close":
        await pool.close()
        expected = GatewayShuttingDownError
    elif outcome == "quarantine":
        await pool.quarantine()
        await pool.set_capacity(1)
        expected = ResourceQuarantinedError
    else:
        expected = AdmissionDeadlineError
    with pytest.raises(expected):
        await task
    snapshot = await pool.snapshot()
    assert snapshot["inflight"] == snapshot["queued"] == 0
    assert not snapshot["continuation_wakeup_pending"]
    if outcome == "quarantine":
        with pytest.raises(ResourceQuarantinedError):
            await acquire(pool, "c")
    await pool.close()


@pytest.mark.asyncio
async def test_queue_bound_pause_restore_and_rollback_fifo():
    pool = ResourceAdmissionPool(ResourceConfig("local", 2, 1), continuation=config())
    first = await acquire(pool, "a")
    second = await acquire(pool, "b")
    waiting = asyncio.create_task(acquire(pool, "c"))
    await wait_queued(pool, 1)
    with pytest.raises(QueueFullError):
        await acquire(pool, "d")
    await pool.set_capacity(0)
    await first.release()
    await second.release()
    assert not waiting.done()
    await pool.set_capacity(1)
    await (await asyncio.wait_for(waiting, 1)).release()
    await pool.set_capacity(2)
    await pool.close()
    rollback = ResourceAdmissionPool(
        ResourceConfig("local", 1, 2), continuation=config(enabled=False)
    )
    first = await acquire(rollback, "a")
    other = asyncio.create_task(acquire(rollback, "b"))
    await wait_queued(rollback, 1)
    same = asyncio.create_task(acquire(rollback, "a"))
    await wait_queued(rollback, 2)
    await first.release()
    lease = await asyncio.wait_for(other, 1)
    assert not same.done()
    await lease.release()
    await (await same).release()
    await rollback.close()


@pytest.mark.parametrize(
    "overrides",
    [
        {"enabled": "true"},
        {"turn_seconds": True},
        {"turn_seconds": "30"},
        {"burst_requests": 0},
        {"burst_requests": 65},
        {"turn_seconds": float("nan")},
        {"fair_wait_seconds": -1},
        {"idle_grace_seconds": 1.1},
        {"turn_seconds": 0.01, "idle_grace_seconds": 0.02},
    ],
)
def test_invalid_policy_settings_fail_closed(overrides):
    with pytest.raises(GatewayConfigurationError):
        config(**overrides)


def test_policy_state_is_bounded_and_age_wakeup_is_not_delayed():
    policy = CaseContinuationPolicy(config(fair_wait_seconds=0.1))
    for index in range(20):
        policy.granted(str(index), "one", index, capacity=2)
        policy.released(str(index), index)
        assert policy.case_count <= 2
    policy.clear()
    policy.granted("a", "one", 0, capacity=1)
    policy.released("a", 0.09)
    candidate = Candidate("b", "x", 0)
    assert policy.choose([candidate], set(), 0.095, capacity=1) == (None, 0.1)


def test_package_metadata_is_control_only_and_requires_case():
    from datetime import datetime, timezone
    from uuid import uuid4

    source = dict(
        request_id=uuid4(),
        profile="strata",
        deadline_at=datetime.now(timezone.utc),
        timeout_seconds=1,
        payload={"messages": [{"role": "user", "content": "unchanged"}]},
    )
    with pytest.raises(ValidationError):
        GatewayCompletionRequest(**source, package_key=key("pack"))
    request = GatewayCompletionRequest(
        **source, case_key=key("case"), package_key=key("pack")
    )
    assert request.payload == source["payload"]
    with pytest.raises(ValidationError):
        request.model_validate(
            {**source, "case_key": key("case"), "package_key": "raw-patient"}
        )


def test_native_and_legacy_package_identity_uses_existing_owner(monkeypatch):
    context = llm_observability.LLMObservationContext(
        record_key_hash=key("case"),
        root_job_id="job",
        executor_key="exam_lab",
        rule_set_key="rules",
        rule_set_version="v1",
    )
    monkeypatch.setattr(
        llm_observability,
        "get_settings",
        lambda: type("Settings", (), {"JWT_SECRET": "synthetic-only"})(),
    )
    token = llm_observability._OBSERVATION_CONTEXT.set(context)
    try:
        native = current_strata_package_key()
        assert len(native) == 64
        with strata_rule_package_scope("pack-1"):
            original = current_strata_package_key()
            assert current_strata_package_key() == original and original != native
        with strata_rule_package_scope("pack-2"):
            assert current_strata_package_key() != original
        assert current_strata_package_key() == native
        llm_observability._OBSERVATION_CONTEXT.set(
            replace(context, record_key_hash=None)
        )
        assert current_strata_package_key() is None
        llm_observability._OBSERVATION_CONTEXT.set(
            replace(context, executor_key="legacy_orchestrated")
        )
        assert current_strata_package_key() is None
    finally:
        llm_observability._OBSERVATION_CONTEXT.reset(token)


@pytest.mark.asyncio
async def test_child_task_cannot_keep_expired_package_scope(monkeypatch):
    context = llm_observability.LLMObservationContext(
        record_key_hash=key("case"), executor_key="exam_lab"
    )
    token = llm_observability._OBSERVATION_CONTEXT.set(context)
    ready = asyncio.Event()

    async def later():
        await ready.wait()
        return current_strata_package_key()

    try:
        with strata_rule_package_scope("pack"):
            task = asyncio.create_task(later())
        ready.set()
        assert await task is None
    finally:
        llm_observability._OBSERVATION_CONTEXT.reset(token)


@pytest.mark.asyncio
async def test_compact_callback_preserves_pack_and_model_arguments(monkeypatch):
    from types import SimpleNamespace
    from app.services.sichuan_qc_service import SichuanQCService

    captured = []

    async def fixed(**kwargs):
        captured.append((kwargs, current_strata_package_key()))
        return {"results": [{"rule_id": "synthetic-rule", "status": "compliant"}]}

    service = SichuanQCService.__new__(SichuanQCService)
    service.client = SimpleNamespace(model="synthetic-model")
    service.rule_engine = SimpleNamespace(evaluate_batch_compact=fixed)
    context = llm_observability.LLMObservationContext(
        record_key_hash=key("case"),
        executor_key="legacy_orchestrated",
        root_job_id="job",
    )
    monkeypatch.setattr(
        llm_observability,
        "get_settings",
        lambda: SimpleNamespace(JWT_SECRET="synthetic-only"),
    )
    token = llm_observability._OBSERVATION_CONTEXT.set(context)
    rules = [{"rule_id": "synthetic-rule"}]
    material = {"content": "unchanged synthetic evidence"}
    try:
        for pack in ("existing-pack-1", "existing-pack-2"):
            result = await service._llm_evaluate_batch_compact(
                rules, material, {"pack_id": pack}
            )
            assert result == {
                "results": [{"rule_id": "synthetic-rule", "status": "compliant"}]
            }
        assert captured[0][1] != captured[1][1]
        assert len(captured[0][1]) == 64
        for (args, _), pack in zip(captured, ("existing-pack-1", "existing-pack-2")):
            assert (
                args["rules"] == rules
                and args["pack_id"] == pack
                and args["pack_size"] == 1
            )
            assert args["medical_record"]["content"] == material["content"]
        assert material == {"content": "unchanged synthetic evidence"}
        assert current_strata_package_key() is None
    finally:
        llm_observability._OBSERVATION_CONTEXT.reset(token)


@pytest.mark.asyncio
async def test_cancel_after_grant_before_claim_returns_case_and_physical_slot():
    pool = ResourceAdmissionPool(ResourceConfig("local", 1, 2), continuation=config())
    first = await acquire(pool, "a")
    following = asyncio.create_task(acquire(pool, "a"))
    await wait_queued(pool, 1)
    outsider = asyncio.create_task(acquire(pool, "b"))
    await wait_queued(pool, 2)
    await first.release()
    following.cancel()
    with pytest.raises(asyncio.CancelledError):
        await following
    await (await asyncio.wait_for(outsider, 1)).release()
    await pool.close()
    snapshot = await pool.snapshot()
    assert snapshot["inflight"] == snapshot["active_cases"] == snapshot["queued"] == 0


@pytest.mark.parametrize("enabled", ["true", "false"])
def test_gateway_environment_continuation_settings_are_independent_of_prompt(enabled):
    import json
    from app.llm_gateway.config import GatewaySettings
    env = {
        "LLM_GATEWAY_TOKEN": "synthetic-gateway-token-at-least-32-chars",
        "LLM_GATEWAY_RESOURCES_JSON": json.dumps([{"resource_id": "gpu", "max_inflight": 2, "max_queue": 4}]),
        "LLM_GATEWAY_PROFILES_JSON": json.dumps([{"profile": "strata_main", "resource_id": "gpu",
            "provider_code": "strata", "model": "synthetic", "api_endpoint": "http://strata.test/v1"}]),
        "LLM_GATEWAY_ALLOWED_HOSTS": '["strata.test"]', "LLM_GATEWAY_STATE_DIR": "synthetic-state",
        "STRATA_CASE_CONTINUATION_ENABLED": enabled,
    }
    settings = GatewaySettings.from_env(env)
    assert settings.continuation.enabled is (enabled == "true")
    assert settings.continuation.burst_requests == 4
    assert settings.continuation.idle_grace_seconds == .05
    assert settings.strata_case_sequential and not settings.cache_enabled
    with pytest.raises(GatewayConfigurationError):
        GatewaySettings.from_env({**env, "STRATA_CASE_BURST_REQUESTS": "65"})
    with pytest.raises(GatewayConfigurationError):
        GatewaySettings.from_env({**env, "STRATA_CASE_CONTINUATION_ENABLED": "maybe"})
