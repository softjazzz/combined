"""病例准入与Mock容量变化；不访问任何真实模型或数据库。"""

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
from dataclasses import replace
from uuid import uuid4

import pytest
import httpx

from app.llm_gateway.admission import AdmissionDeadlineError, QueueFullError, ResourceAdmissionPool, ResourceQuarantinedError
from app.llm_gateway.config import GatewaySettings, GatewayConfigurationError, ProfileConfig, ResourceConfig
from app.llm_gateway.main import GatewayRuntime, create_app
from app.services import llm_observability, qc_llm_client
from app.services.llm_dispatch import client as dispatch
from app.core.settings import Settings
from app.services.llm_dispatch.contracts import GatewayCompletionRequest


def case(name):
    return hashlib.sha256(name.encode()).hexdigest()


async def queued(pool, expected):
    for _ in range(100):
        if (await pool.snapshot())["queued"] == expected:
            return
        await asyncio.sleep(0)
    raise AssertionError("expected queue size not reached")


@pytest.mark.asyncio
async def test_oldest_eligible_case_does_not_block_free_slot_or_starve():
    pool = ResourceAdmissionPool(ResourceConfig("local", 2, 4))
    deadline = asyncio.get_running_loop().time() + 2
    a = await pool.acquire(monotonic_deadline=deadline, case_key=case("a"))
    a_next = asyncio.create_task(pool.acquire(monotonic_deadline=deadline, case_key=case("a")))
    await queued(pool, 1)
    b = await pool.acquire(monotonic_deadline=deadline, case_key=case("b"))
    c_next = asyncio.create_task(pool.acquire(monotonic_deadline=deadline, case_key=case("c")))
    await queued(pool, 2)
    await b.release()
    c = await asyncio.wait_for(c_next, 1)
    assert not a_next.done()
    await a.release()
    a2 = await asyncio.wait_for(a_next, 1)
    await c.release()
    await a2.release()
    assert (await pool.snapshot())["inflight"] == 0


@pytest.mark.asyncio
async def test_capacity_reduction_pause_and_restore_do_not_revoke_existing_leases():
    pool = ResourceAdmissionPool(ResourceConfig("local", 2, 4))
    deadline = asyncio.get_running_loop().time() + 2
    a = await pool.acquire(monotonic_deadline=deadline, case_key=case("a"))
    b = await pool.acquire(monotonic_deadline=deadline, case_key=case("b"))
    await pool.set_capacity(1)
    c_next = asyncio.create_task(pool.acquire(monotonic_deadline=deadline, case_key=case("c")))
    await queued(pool, 1)
    await a.release()
    assert not c_next.done()
    await pool.set_capacity(0)
    await b.release()
    assert not c_next.done()
    assert (await pool.snapshot())["inflight"] == 0
    await pool.set_capacity(1)
    c = await asyncio.wait_for(c_next, 1)
    await pool.set_capacity(2)
    await c.release()
    assert (await pool.snapshot())["effective_max_inflight"] == 2


@pytest.mark.asyncio
async def test_same_case_waiting_is_bounded_and_timeout_and_cancel_release_queue():
    pool = ResourceAdmissionPool(ResourceConfig("local", 2, 1))
    deadline = asyncio.get_running_loop().time() + 2
    a = await pool.acquire(monotonic_deadline=deadline, case_key=case("a"))
    waiting = asyncio.create_task(pool.acquire(monotonic_deadline=deadline, case_key=case("a")))
    await queued(pool, 1)
    with pytest.raises(QueueFullError):
        await pool.acquire(monotonic_deadline=deadline, case_key=case("a"))
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    with pytest.raises(AdmissionDeadlineError):
        await pool.acquire(monotonic_deadline=asyncio.get_running_loop().time() + .01, case_key=case("a"))
    await a.release()
    again = await pool.acquire(monotonic_deadline=deadline, case_key=case("a"))
    await again.release()
    assert (await pool.snapshot())["queued"] == 0


@pytest.mark.asyncio
async def test_zero_queue_rejects_busy_case_but_allows_other_case_into_free_slot():
    pool = ResourceAdmissionPool(ResourceConfig("local", 2, 0))
    deadline = asyncio.get_running_loop().time() + 1
    a = await pool.acquire(monotonic_deadline=deadline, case_key=case("a"))
    with pytest.raises(QueueFullError):
        await pool.acquire(monotonic_deadline=deadline, case_key=case("a"))
    b = await pool.acquire(monotonic_deadline=deadline, case_key=case("b"))
    assert (await pool.snapshot())["inflight"] == 2
    await a.release()
    await b.release()


class Sender:
    def __init__(self):
        self.started = asyncio.Queue()
        self.releases = asyncio.Queue()
        self.active = 0
        self.peak = 0
        self.payloads = []

    async def send(self, profile, payload, *, timeout_seconds):
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.payloads.append(payload)
        release = asyncio.Event()
        await self.releases.put(release)
        await self.started.put(payload["messages"][0]["content"])
        try:
            await release.wait()
            return {"choices": [{"message": {"content": "fixed"}, "finish_reason": "stop"}], "usage": {}}
        finally:
            self.active -= 1


def settings(tmp_path):
    return GatewaySettings(token="test-only-token-01234567890123456789",
        resources={"local": ResourceConfig("local", 2, 4)},
        profiles={name: ProfileConfig(name, "local", "strata", "local-model", "http://strata.test/v1/chat/completions")
                  for name in ("strata_first", "strata_second")},
        allowed_hosts=frozenset({"strata.test"}), state_dir=tmp_path, startup_isolation_seconds=0)


def request(name, profile="strata_first", *, identity=None):
    return GatewayCompletionRequest(request_id=uuid4(), profile=profile,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=3), timeout_seconds=3,
        case_key=identity,
        payload={"model": "local-model", "messages": [{"role": "user", "content": name}], "stream": False})


@pytest.mark.asyncio
async def test_three_cases_and_same_case_roles_share_two_requests_and_keep_old_prompt(tmp_path):
    sender = Sender()
    runtime = GatewayRuntime(settings(tmp_path), sender)
    a = asyncio.create_task(runtime.complete(request("a1", identity=case("a"))))
    assert await asyncio.wait_for(sender.started.get(), 1) == "a1"
    a2 = asyncio.create_task(runtime.complete(request("a2", "strata_second", identity=case("a"))))
    b = asyncio.create_task(runtime.complete(request("b", identity=case("b"))))
    assert await asyncio.wait_for(sender.started.get(), 1) == "b"
    c = asyncio.create_task(runtime.complete(request("c", identity=case("c"))))
    (await sender.releases.get()).set()
    assert await asyncio.wait_for(sender.started.get(), 1) == "a2"
    (await sender.releases.get()).set()
    assert await asyncio.wait_for(sender.started.get(), 1) == "c"
    for _ in range(2):
        (await sender.releases.get()).set()
    results = await asyncio.gather(a, a2, b, c)
    assert sender.peak == 2
    assert all(item["choices"][0]["message"]["content"] == "fixed" for item in results)
    assert all(set(payload) == {"model", "messages", "stream"} for payload in sender.payloads)
    assert all(len(payload["messages"]) == 1 for payload in sender.payloads)
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_old_requests_without_case_identity_use_one_conservative_lane(tmp_path):
    sender = Sender()
    runtime = GatewayRuntime(settings(tmp_path), sender)
    one = asyncio.create_task(runtime.complete(request("one")))
    await asyncio.wait_for(sender.started.get(), 1)
    two = asyncio.create_task(runtime.complete(request("two")))
    for _ in range(8):
        await asyncio.sleep(0)
    assert sender.active == 1
    assert sender.started.empty()
    (await sender.releases.get()).set()
    assert await asyncio.wait_for(sender.started.get(), 1) == "two"
    (await sender.releases.get()).set()
    await asyncio.gather(one, two)
    assert sender.peak == 1
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_cancel_after_grant_returns_case_and_slot():
    pool = ResourceAdmissionPool(ResourceConfig("local", 1, 2))
    deadline = asyncio.get_running_loop().time() + 2
    lease = await pool.acquire(monotonic_deadline=deadline, case_key=case("a"))
    waiting = asyncio.create_task(pool.acquire(monotonic_deadline=deadline, case_key=case("a")))
    await queued(pool, 1)
    await lease.release()
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    assert (await pool.snapshot())["active_cases"] == 0
    again = await pool.acquire(monotonic_deadline=deadline, case_key=case("a"))
    await again.release()


@pytest.mark.asyncio
async def test_capacity_control_never_clears_quarantine_and_rejects_overcommit():
    pool = ResourceAdmissionPool(ResourceConfig("local", 2, 2))
    for invalid in (-1, 3, True, 1.5):
        with pytest.raises(ValueError):
            await pool.set_capacity(invalid)
    await pool.quarantine()
    await pool.set_capacity(2)
    with pytest.raises(ResourceQuarantinedError):
        await pool.acquire(monotonic_deadline=asyncio.get_running_loop().time() + 1, case_key=case("a"))


def test_multiple_strata_profiles_cannot_split_one_api_into_independent_two_slot_pools(tmp_path):
    cfg = settings(tmp_path)
    other = replace(cfg.profiles["strata_second"], resource_id="another")
    with pytest.raises(GatewayConfigurationError):
        replace(cfg, resources={**cfg.resources, "another": ResourceConfig("another", 2, 4)},
                profiles={**cfg.profiles, "strata_second": other})
    with pytest.raises(GatewayConfigurationError):
        replace(cfg, profiles={**cfg.profiles, "strata_second": replace(other, resource_id="local",
                api_endpoint="http://strata.test/other/chat/completions")})


@pytest.mark.asyncio
async def test_sdk_to_gateway_uses_case_hmac_across_jobs_and_never_sends_it_to_model(tmp_path, monkeypatch):
    sdk = Settings(_env_file=None, JWT_SECRET="synthetic", LLM_DISPATCH_MODE="gateway",
        LLM_GATEWAY_URL="http://gateway.test", LLM_GATEWAY_TOKEN=settings(tmp_path).token,
        LLM_GATEWAY_PROFILE="strata_first", STRATA_CASE_CACHE_MODE="off")
    for module in (dispatch, qc_llm_client, llm_observability):
        monkeypatch.setattr(module, "get_settings", lambda: sdk)
    sender = Sender()
    app = create_app(settings(tmp_path), sender=sender, enforce_single_instance=False)
    model = qc_llm_client.SichuanQCLLMClient({"provider_code": "strata", "model": "local-model",
        "api_endpoint": "http://strata.test/v1", "dispatch_mode": "gateway", "gateway_profile": "strata_first"},
        gateway_dispatch_client=dispatch.GatewayDispatchClient(transport=httpx.ASGITransport(app=app)))

    async def send(patient, text, job):
        with llm_observability.llm_observation_context(business_scene="synthetic", root_job_id=job,
                record_identity=("synthetic-hospital", patient, "synthetic-visit")):
            return await model.generate(text, allow_length_retry=False)

    a = asyncio.create_task(send("patient-a", "a1", "job-one"))
    assert await asyncio.wait_for(sender.started.get(), 1) == "a1"
    a2 = asyncio.create_task(send("patient-a", "a2", "job-two"))
    b = asyncio.create_task(send("patient-b", "b", "job-three"))
    assert await asyncio.wait_for(sender.started.get(), 1) == "b"
    c = asyncio.create_task(send("patient-c", "c", "job-four"))
    (await sender.releases.get()).set()
    assert await asyncio.wait_for(sender.started.get(), 1) == "a2"
    (await sender.releases.get()).set()
    assert await asyncio.wait_for(sender.started.get(), 1) == "c"
    for _ in range(2):
        (await sender.releases.get()).set()
    outcomes = await asyncio.gather(a, a2, b, c)
    assert len(outcomes) == 4 and sender.peak == 2
    assert all("case_key" not in payload and "strata_prefix" not in payload for payload in sender.payloads)
    assert {payload["messages"][0]["content"] for payload in sender.payloads} == {"a1", "a2", "b", "c"}
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_mock_capacity_is_gateway_status_not_claimed_replica_health(tmp_path):
    app = create_app(settings(tmp_path), sender=Sender(), enforce_single_instance=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gateway.test",
            headers={"Authorization": "Bearer " + settings(tmp_path).token}) as client:
        for capacity, status in ((1, 503), (0, 503), (2, 200)):
            await app.state.gateway_runtime.set_resource_capacity("local", capacity)
            assert (await client.get("/health")).status_code == status
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("cloud", [False, True])
async def test_rollback_fifo_and_cloud_calls_do_not_acquire_case_serial_lane(tmp_path, cloud):
    cfg = settings(tmp_path)
    profile = cfg.profiles["strata_first"]
    if cloud:
        profile = replace(profile, name="alibaba_first", provider_code="alibaba", api_key="synthetic")
        cfg = replace(cfg, profiles={profile.name: profile})
    else:
        cfg = replace(cfg, strata_case_sequential=False)
    sender = Sender()
    runtime = GatewayRuntime(cfg, sender)
    tasks = [asyncio.create_task(runtime.complete(request(str(i), profile.name, identity=case("same")))) for i in range(2)]
    for _ in range(2):
        await asyncio.wait_for(sender.started.get(), 1)
    assert sender.active == 2
    for _ in range(2):
        (await sender.releases.get()).set()
    await asyncio.gather(*tasks)
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_mock_runtime_drain_pause_restore_preserves_all_fixed_responses(tmp_path):
    sender = Sender()
    runtime = GatewayRuntime(settings(tmp_path), sender)
    a = asyncio.create_task(runtime.complete(request("a", identity=case("a"))))
    b = asyncio.create_task(runtime.complete(request("b", identity=case("b"))))
    for _ in range(2):
        await asyncio.wait_for(sender.started.get(), 1)
    await runtime.set_resource_capacity("local", 1)
    c = asyncio.create_task(runtime.complete(request("c", identity=case("c"))))
    await queued(runtime.admission._pools["local"], 1)
    (await sender.releases.get()).set()
    await a
    assert sender.started.empty()
    await runtime.set_resource_capacity("local", 0)
    (await sender.releases.get()).set()
    await b
    assert not c.done()
    assert (await runtime.resource_counts())[0]["queued"] == 1
    await runtime.set_resource_capacity("local", 1)
    assert await asyncio.wait_for(sender.started.get(), 1) == "c"
    (await sender.releases.get()).set()
    results = await asyncio.gather(a, b, c)
    assert len(results) == 3
    assert all(result["choices"][0]["message"]["content"] == "fixed" for result in results)
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_cancelled_caller_does_not_release_same_case_before_provider_finishes(tmp_path):
    sender = Sender()
    runtime = GatewayRuntime(settings(tmp_path), sender)
    a = asyncio.create_task(runtime.complete(request("a", identity=case("a"))))
    await asyncio.wait_for(sender.started.get(), 1)
    a.cancel()
    with pytest.raises(asyncio.CancelledError):
        await a
    a2 = asyncio.create_task(runtime.complete(request("a2", identity=case("a"))))
    await queued(runtime.admission._pools["local"], 1)
    b = asyncio.create_task(runtime.complete(request("b", identity=case("b"))))
    assert await asyncio.wait_for(sender.started.get(), 1) == "b"
    assert sender.active == 2
    (await sender.releases.get()).set()
    assert await asyncio.wait_for(sender.started.get(), 1) == "a2"
    for _ in range(2):
        (await sender.releases.get()).set()
    await asyncio.gather(a2, b)
    assert await runtime.shutdown()
