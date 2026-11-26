"""Wave 2 runtime-a 离线回归单测：覆盖 P1-A1~A5、P1-D1/D2、P1-E3、P2-A1、P2-A3。"""

from __future__ import annotations

import asyncio
from dataclasses import fields as dataclass_fields
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from openpyxl import load_workbook
import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from app.llm_gateway.admission import AdmissionDeadlineError
from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import GatewayRuntime
from app.qc_worker.batch_consumer import BatchConsumer, ConsumerDecision
from app.qc_worker.recovery import RecoveryOutcome, WorkerRecovery
from app.services import custom_qc_workspace_service as workspace_module
from app.services import qc_llm_client as llm_client_module
from app.services import sichuan_workspace_batch_worker as sichuan_worker
from app.services.daily_qc.store import ScheduleStore, tables as daily_qc_tables
from app.services.llm_dispatch.contracts import (
    GatewayCasePrefix,
    GatewayCompletionRequest,
)
from app.services.luxian_0609 import execution as luxian_0609_execution
from app.services.luxian_0916 import batch_worker as luxian_0916_worker
from app.services.luxian_0916.contracts import Luxian0916RuleResult
from app.services.luxian_0916.orchestrator import Luxian0916Execution
from app.services.qc_cancellation import (
    QCJobCancelled,
    cancellation_scope,
    current_cancellation_check,
    is_cancelled,
    raise_if_cancelled,
)
from app.services.qc_dispatch.contracts import BatchDispatchEnvelope
from app.services.qc_dispatch.control import deployment_identity
from app.services.qc_dispatch.maintenance import OutboxMaintenance
from app.services.qc_dispatch.outbox import batch_job_identity_table
from app.services.qc_dispatch.repository import QCDispatchRepository
from app.services.qc_dispatch.status import Heartbeat, service_status
from app.services.sichuan_qc import running_final_bundle_service


# ---------------------------------------------------------------------------
# 1. P1-A1 + P1-D1 + P1-D2: 取消信号全链路贯通 & luxian_0916 隐私脱敏与合规计数
# ---------------------------------------------------------------------------


def test_p1_a1_cancellation_scope_composes_nested_checks() -> None:
    outer_flag = False
    inner_flag = False
    assert current_cancellation_check() is None
    assert not is_cancelled()

    with cancellation_scope(lambda: outer_flag):
        assert not is_cancelled()
        with cancellation_scope(lambda: inner_flag):
            assert not is_cancelled()
            outer_flag = True
            assert is_cancelled()
            with pytest.raises(QCJobCancelled):
                raise_if_cancelled()
        # 退出内层作用域后外层依然有效
        assert is_cancelled()
        outer_flag = False
        assert not is_cancelled()

    assert current_cancellation_check() is None


@pytest.mark.asyncio
async def test_p1_a1_running_final_bundle_propagates_cancellation_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled = False
    observed_in_prepare: list[bool] = []

    async def fake_prepare(**_kwargs: Any):
        observed_in_prepare.append(current_cancellation_check() is not None)
        raise_if_cancelled()
        raise AssertionError("should have been cancelled inside prepare")

    fake_module = SimpleNamespace(
        normalize_quality_profile=lambda value: value,
        get_settings=lambda: SimpleNamespace(
            LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
            LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        ),
        resolve_mainline_rule_decision_settings=lambda s: s,
        assert_luxian_0609_customer_native_delivery_ready=lambda *_a, **_kw: None,
        load_luxian_0609_dependency_inventory=lambda: {},
        build_luxian_0609_package_plan_from_settings=lambda **_kw: SimpleNamespace(
            compatibility_execution_rule_ids=(),
        ),
        assert_luxian_0609_formal_package_plan_native_only=lambda *_a, **_kw: None,
        load_luxian_0609_rules=lambda: [],
        prepare_luxian_0609_execution=fake_prepare,
        raise_if_cancelled=raise_if_cancelled,
    )
    monkeypatch.setattr(
        running_final_bundle_service,
        "_resolve_facade_module",
        lambda _host: fake_module,
    )
    monkeypatch.setattr(
        "app.services.qc_input_adapters.adapt_bundle_to_sichuan_eval_args",
        lambda bundle, rule_ids=None: {
            "document_id": "doc-1",
            "document_type": "终末病历",
            "content": "病历文本",
            "rule_ids": list(rule_ids or []),
            "evidence_payload": {},
            "metadata": {},
        },
    )
    monkeypatch.setattr(
        "app.services.qc_input_adapters.extract_bundle_documents",
        lambda _bundle: [],
    )

    class _Host:
        adjudicator_client = object()

        async def _resolve_rules_for_document(self, **_kwargs: Any):
            return []

    def check() -> bool:
        return cancelled

    # 在进入 prepare 之前已触发取消
    cancelled = True
    with pytest.raises(QCJobCancelled):
        await running_final_bundle_service.evaluate_running_final_bundle_input(
            _Host(),
            {"scene": "final", "visit_id": "V-1"},
            rule_set_key="luxian_0609_qc_v1",
            cancellation_check=check,
        )
    assert observed_in_prepare == []

    # 在 prepare 内部检测到取消信号（通过 ContextVar 作用域）
    calls = 0

    def cancel_on_third_check() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 3

    with pytest.raises(QCJobCancelled):
        await running_final_bundle_service.evaluate_running_final_bundle_input(
            _Host(),
            {"scene": "final", "visit_id": "V-1"},
            rule_set_key="luxian_0609_qc_v1",
            cancellation_check=cancel_on_third_check,
        )
    assert observed_in_prepare == [True]


@pytest.mark.asyncio
async def test_p1_a1_luxian_0609_execution_aborts_when_cancelled() -> None:
    with cancellation_scope(lambda: True):
        with pytest.raises(QCJobCancelled):
            await luxian_0609_execution.prepare_luxian_0609_execution(
                rule_set_key="luxian_0609_qc_v1",
                prepared_rules=[],
                visit_id="V-1",
                medical_text="正文",
                evidence_payload={},
                llm_client=object(),
                settings=SimpleNamespace(LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True),
            )


@pytest.mark.asyncio
async def test_p1_a1_qc_llm_client_stops_before_send_and_before_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_count = 0
    cancel_flag = False

    async def fake_post_json(**_kwargs: Any) -> dict[str, Any]:
        nonlocal sent_count, cancel_flag
        sent_count += 1
        cancel_flag = True
        return {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": "partial"},
                }
            ],
            "usage": {"total_tokens": 10},
        }

    monkeypatch.setattr(llm_client_module, "safe_post_json", fake_post_json)
    client = llm_client_module.SichuanQCLLMClient(
        {
            "api_endpoint": "https://example.test/v1",
            "api_key": "test-key",
            "model": "deepseek-reasoner",
            "provider_code": "deepseek",
            "dispatch_mode": "direct",
            "custom_parameters": {"max_tokens": 8192},
        }
    )

    # 1) 发送前已取消 -> 0 次 HTTP 调用
    with cancellation_scope(lambda: True):
        with pytest.raises(QCJobCancelled):
            await client.generate("hello")
    assert sent_count == 0

    # 2) length 重试前被取消 -> 只发 1 次，不发重试请求，且不包装成 SafeExecutionError
    cancel_flag = False
    with cancellation_scope(lambda: cancel_flag):
        with pytest.raises(QCJobCancelled):
            await client.generate("hello", allow_length_retry=True)
    assert sent_count == 1


def test_p1_a1_sichuan_batch_worker_re_raises_cancel_instead_of_bundle_fallback() -> None:
    import inspect

    source = inspect.getsource(sichuan_worker.run_sichuan_workspace_batch_job)
    assert "except QCJobCancelled:\n                        raise\n                    except Exception as bundle_exc:" in source
    assert "with cancellation_scope(_is_cancelled)" in source


@pytest.mark.asyncio
async def test_p1_a1_d1_d2_luxian_0916_cancel_privacy_and_compliant_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        luxian_0916_worker,
        "load_luxian_0916_bundle",
        lambda **_kw: {
            "structured_context": {
                "patient": {"name": "张敏华", "id_card_no": "510101198801023456"}
            },
            "source_documents": [
                {
                    "document_id": "ADM-1",
                    "source_table": "admission_record",
                    "authored_at": "2026-09-16 09:00:00",
                    "content": (
                        "患者姓名：张敏华，身份证：510101198801023456，"
                        "手机号：13800138000，现住址：成都市高新区天府大道100号；"
                        "主治医师：李明。张敏华因胸痛入院。"
                    ),
                }
            ],
        },
    )
    monkeypatch.setattr(
        luxian_0916_worker,
        "build_programmatic_evidence_payload",
        lambda **_kw: {
            "programmatic_timeline": {
                "documents": {
                    "admission_record": [
                        {
                            "document_id": "ADM-1",
                            "authored_at": "2026-09-16 09:00:00",
                            "content": (
                                "患者姓名：张敏华，身份证：510101198801023456，"
                                "手机号：13800138000，现住址：成都市高新区天府大道100号；"
                                "主治医师：李明。张敏华因胸痛入院。"
                            ),
                        }
                    ]
                }
            }
        },
    )
    monkeypatch.setattr(
        luxian_0916_worker,
        "build_critical_value_018_facts",
        lambda **_kw: {
            "event_facts": {"critical_values": []},
            "event_source_state_by_rule": {"LX0916-018": "critical_value_source_complete"},
            "diagnostic": {"code": "critical_value_018_stage1_ready", "event_count": 0, "llm_call_count": 0},
        },
    )
    monkeypatch.setattr(
        luxian_0916_worker,
        "load_disease_change_015016_facts",
        lambda **_kw: {
            "event_facts": {"disease_changes": []},
            "event_source_state_by_rule": {
                "LX0916-015": "structured_complete",
                "LX0916-016": "structured_complete",
            },
            "diagnostic": {"code": "structured_disease_change_trigger_ready", "event_count": 0, "llm_call_count": 0},
        },
    )

    async def fake_stage2(**kwargs: Any) -> dict[str, Any]:
        result = dict(kwargs["structured_facts"])
        result["diagnostic"] = {"code": "not_triggered", "event_count": 0, "llm_call_count": 0}
        return result

    monkeypatch.setattr(luxian_0916_worker, "extract_disease_change_stage2_facts", fake_stage2)

    def make_result(rule_id: str, status: str) -> Luxian0916RuleResult:
        return Luxian0916RuleResult(
            rule_id=rule_id,
            status=status,
            reason_code="document_complete",
            findings="f",
            evidence=("e",),
            suggestion="",
            document_anchors=(),
            diagnostics={},
        )

    # 病历 1：1 条 non_compliant + 31 条 compliant（不应计入 compliant_records）
    # 病历 2：全部 32 条 compliant（应计入 compliant_records）
    # 病历 3：1 条 data_quality_gap + 31 条 compliant（不应计入 compliant_records）
    def fake_execute(_context: Any, rule_ids: Any) -> Luxian0916Execution:
        idx = fake_execute.counter
        fake_execute.counter += 1
        statuses: dict[str, str] = {}
        if idx == 0:
            statuses[rule_ids[0]] = "non_compliant"
        elif idx == 2:
            statuses[rule_ids[0]] = "data_quality_gap"
        return Luxian0916Execution(
            results=tuple(
                make_result(rid, statuses.get(rid, "compliant")) for rid in rule_ids
            )
        )

    fake_execute.counter = 0
    monkeypatch.setattr(luxian_0916_worker, "execute_luxian_0916", fake_execute)

    captured_prompts: list[str] = []

    async def fake_generate(prompt: str, **_kwargs: Any) -> dict[str, Any]:
        captured_prompts.append(prompt)
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "semantic_facts": {},
                                "event_facts": {},
                                "document_facts": {},
                                "discharge_facts": {},
                            }
                        )
                    }
                }
            ],
            "usage": {"total_tokens": 12},
            "_api_time": 0.01,
        }

    class _FakeWorkspace:
        def __init__(self, records: list[dict[str, Any]], *, canceled: bool = False) -> None:
            self.records = records
            self.canceled = canceled
            self.completed: dict[str, Any] | None = None
            self.failed: list[dict[str, Any]] = []

        def get_batch_job_for_processing(self, *, job_id: str) -> dict[str, Any]:
            return {
                "id": job_id,
                "scope": "running",
                "status": "canceled" if self.canceled else "running",
                "filters": {
                    "rule_set_key": luxian_0916_worker.LUXIAN_0916_RULE_SET_KEY,
                    "record_refs": [
                        {k: r[k] for k in ("institute_id", "patient_id", "visit_id")}
                        for r in self.records
                    ],
                },
            }

        def is_batch_job_canceled_or_missing(self, *, job_id: str) -> bool:
            return self.canceled

        def mark_batch_job_running(self, *, job_id: str) -> bool:
            return True

        def collect_records(self, **_kw: Any) -> list[dict[str, Any]]:
            return list(self.records)

        def hydrate_records_with_medical_text(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return list(records)

        def update_batch_job_progress(self, **_kw: Any) -> None:
            return None

        def complete_batch_job(self, **kwargs: Any) -> None:
            self.completed = kwargs

        def fail_batch_job(self, **kwargs: Any) -> None:
            self.failed.append(kwargs)

    records = [
        {
            "institute_id": "I-1",
            "patient_id": f"P-{i}",
            "visit_id": f"V-{i}",
            "record_id": f"V-{i}",
            "patient_name": "张敏华",
            "scope": "running",
            "medical_text": "病历正文",
        }
        for i in range(1, 4)
    ]
    ws = _FakeWorkspace(records)
    await luxian_0916_worker.run_luxian_0916_batch_job(
        "job-0916-metrics",
        workspace=ws,
        max_record_concurrency=1,
        semantic_generate=fake_generate,
    )
    assert ws.failed == []
    assert ws.completed is not None
    summary = ws.completed["summary"]
    # P1-D2 验证：issue_records=1, compliant_records=1 (仅第 2 份全合规), issue + compliant <= total_records(3)
    assert summary["total_records"] == 3
    assert summary["issue_records"] == 1
    assert summary["compliant_records"] == 1
    assert summary["issue_records"] + summary["compliant_records"] <= summary["total_records"]

    # P1-D1 验证：所有发往 LLM 的 prompt 均已脱敏患者 PHI，保留主治医师姓名
    assert captured_prompts
    for prompt in captured_prompts:
        assert "张敏华" not in prompt
        assert "510101198801023456" not in prompt
        assert "13800138000" not in prompt
        assert "天府大道100号" not in prompt
        assert "李明" in prompt

    # P1-A1 验证：在第一份病历 LLM 调用时触发取消，不继续跑剩余病历且不写 fail/complete
    cancel_ws = _FakeWorkspace(records)
    calls_before_cancel = 0

    async def cancel_mid_run(prompt: str, **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls_before_cancel
        calls_before_cancel += 1
        cancel_ws.canceled = True
        return await fake_generate(prompt)

    await luxian_0916_worker.run_luxian_0916_batch_job(
        "job-0916-cancel",
        workspace=cancel_ws,
        max_record_concurrency=1,
        semantic_generate=cancel_mid_run,
    )
    assert calls_before_cancel == 1
    assert cancel_ws.completed is None
    assert cancel_ws.failed == []


# ---------------------------------------------------------------------------
# 2. P1-A2: llm_gateway case_cache 解耦 Prime 预算、锁外取消与失败清理
# ---------------------------------------------------------------------------


def _gateway_settings(*, min_prime_budget: float | None = None) -> Any:
    profile = ProfileConfig(
        "strata_first_pass",
        "gpu",
        "strata",
        "synthetic-model",
        "http://provider.test/v1/chat/completions",
        strata_protocol="strata-p9b-v1",
    )
    settings = GatewaySettings(
        token="synthetic-gateway-token-at-least-32-chars",
        resources={"gpu": ResourceConfig("gpu", 2, 4)},
        profiles={profile.name: profile},
        allowed_hosts=frozenset({"provider.test"}),
        state_dir=Path("unused-synthetic-state"),
        startup_isolation_seconds=0,
        cache_enabled=True,
        cache_deployment_version="synthetic-q2-template-v1",
        cache_max_entries=64,
    )
    if min_prime_budget is not None:
        values = {f.name: getattr(settings, f.name) for f in dataclass_fields(GatewaySettings)}
        values["cache_min_prime_budget_seconds"] = min_prime_budget
        return SimpleNamespace(**values)
    return settings


def _gateway_request(*, case: str = "a", timeout: float = 2.0) -> GatewayCompletionRequest:
    prefix = "\nEVENTS_JSON=" + "synthetic-evidence " * 100
    suffix = "Use only supplied evidence and return the existing schema."
    return GatewayCompletionRequest(
        request_id=uuid4(),
        profile="strata_first_pass",
        case_key=case * 64,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=timeout),
        timeout_seconds=timeout,
        payload={
            "model": "synthetic-model",
            "messages": [{"role": "user", "content": suffix + prefix}],
            "max_tokens": 100,
            "stream": False,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        },
        case_prefix=GatewayCasePrefix(
            case_key=case * 64,
            evidence_version=sha256(prefix.encode()).hexdigest(),
            context_version="v1",
            prefix_start=len(suffix),
            expected_requests=2,
        ),
    )


@pytest.mark.asyncio
async def test_p1_a2_short_creator_does_not_quarantine_gpu_or_fail_long_waiter() -> None:
    class SlowSender:
        def __init__(self) -> None:
            self.prime_started = asyncio.Event()
            self.prime_count = 0

        async def send(self, _profile: Any, payload: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
            if payload.get("max_tokens") == 1:
                self.prime_count += 1
                self.prime_started.set()
                await asyncio.sleep(0.2)
                return {
                    "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 1200, "completion_tokens": 1},
                    "timings": {"cache_n": 0, "prompt_n": 1200},
                }
            return {
                "choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}],
                "usage": {
                    "prompt_tokens": 1250,
                    "completion_tokens": 5,
                    "prompt_tokens_details": {"cached_tokens": 1200},
                },
                "timings": {"cache_n": 1200, "prompt_n": 50},
            }

    sender = SlowSender()
    runtime = GatewayRuntime(_gateway_settings(), sender)
    req1 = asyncio.create_task(runtime.complete(_gateway_request(timeout=0.05)))
    await sender.prime_started.wait()
    req2 = asyncio.create_task(runtime.complete(_gateway_request(timeout=10.0)))

    with pytest.raises(AdmissionDeadlineError):
        await req1
    result2 = await req2
    assert result2["choices"][0]["message"]["content"] == '{"ok":true}'
    assert result2["_strata_cache"]["strategy"] == "reused"
    assert sender.prime_count == 1
    assert runtime.lifecycle.remote_inflight_unknown is False
    counts = await runtime.resource_counts()
    assert counts[0]["unknown_inflight"] is False
    assert counts[0]["accepting"] is True
    assert await runtime.shutdown() is True


@pytest.mark.asyncio
async def test_p1_a2_cancel_runs_outside_global_lock_and_build_failure_cleans_pending() -> None:
    cancel_entered = asyncio.Event()
    release_cancel = asyncio.Event()

    class DummySender:
        async def send(self, _profile: Any, _payload: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
            raise AssertionError("not used directly")

    # 1) 验证 cancel/gather 在全局 case_cache.lock 外执行
    settings = _gateway_settings()
    runtime = GatewayRuntime(settings, DummySender())

    async def slow_prime_invoke(_payload: dict[str, Any]) -> dict[str, Any]:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancel_entered.set()
            await release_cancel.wait()
            raise

    req = _gateway_request(timeout=0.05)
    profile = settings.profiles["strata_first_pass"]
    loop = asyncio.get_running_loop()
    task = asyncio.create_task(
        runtime.case_cache.run(
            req,
            profile,
            slow_prime_invoke,
            deadline=loop.time() + 0.05,
            prime_invoke=slow_prime_invoke,
        )
    )
    await asyncio.wait_for(cancel_entered.wait(), timeout=2.0)
    # 此时 task 正在 finally 中等待 pending.task 取消结束；全局 lock 必须可立即获取！
    await asyncio.wait_for(runtime.case_cache.lock.acquire(), timeout=0.5)
    runtime.case_cache.lock.release()
    release_cancel.set()
    with pytest.raises(AdmissionDeadlineError):
        await task
    assert not runtime.case_cache.pending

    # 2) 验证 _build 失败时主动清理 pending[key]
    async def failing_invoke(_payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await runtime.case_cache.run(
            _gateway_request(case="b", timeout=5.0),
            profile,
            failing_invoke,
            deadline=loop.time() + 5.0,
            prime_invoke=failing_invoke,
        )
    assert not runtime.case_cache.pending
    assert await runtime.shutdown() is True


@pytest.mark.asyncio
async def test_p1_a2_low_remaining_budget_skips_prime() -> None:
    payloads: list[dict[str, Any]] = []

    class RecordingSender:
        async def send(self, _profile: Any, payload: dict[str, Any], *, timeout_seconds: float) -> dict[str, Any]:
            payloads.append(payload)
            return {
                "choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 5},
            }

    runtime = GatewayRuntime(_gateway_settings(min_prime_budget=5.0), RecordingSender())
    result = await runtime.complete(_gateway_request(timeout=1.0))
    assert len(payloads) == 1
    assert payloads[0]["max_tokens"] != 1
    assert result["_strata_cache"]["strategy"] == "cold"
    assert result["_strata_cache"]["prime_requests_started"] == 0
    assert await runtime.shutdown() is True


# ---------------------------------------------------------------------------
# 3. P1-A3 + P1-A4 + P1-E3: Outbox aware UTC、非 LX0609 严格 CAS、导出防公式注入
# ---------------------------------------------------------------------------


def _make_workspace_with_sqlite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    db_file = tmp_path / "w2_runtime_a.sqlite"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "SessionLocal", sessions)
    monkeypatch.setattr(workspace_module, "DB_SCHEMA_MODE", "single")
    service = workspace_module.CustomQCWorkspaceService(readonly=True)
    service._draft_table.metadata.create_all(engine)
    service._batch_job_table.metadata.create_all(engine)
    service._record_result_envelope_table.metadata.create_all(engine)
    service._qc_dispatch.dispatch_table.metadata.create_all(engine)
    return service, engine, sessions


def test_p1_a3_outbox_available_at_is_normalized_to_aware_utc(tmp_path: Path) -> None:
    db_file = tmp_path / "outbox_utc.sqlite"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    jobs = batch_job_identity_table(schema=None)
    jobs.metadata.create_all(engine)
    repo = QCDispatchRepository(sessions, jobs, schema=None)
    repo.dispatch_table.metadata.create_all(engine)
    captured_values: list[Any] = []

    try:
        job_id = str(uuid4())
        naive_dt = datetime(2026, 11, 23, 10, 0, 0)
        with sessions.begin() as session:
            session.execute(jobs.insert().values(id=job_id, status="queued", filters_json="{}"))
            orig_execute = session.execute

            def spy_execute(stmt, *args, **kwargs):
                if getattr(stmt, "is_insert", False) or getattr(stmt, "is_update", False):
                    params = stmt.compile().params
                    if "available_at" in params:
                        captured_values.append(params["available_at"])
                return orig_execute(stmt, *args, **kwargs)

            session.execute = spy_execute  # type: ignore[method-assign]
            repo.add_dispatch(session, job_id=job_id, mode="rabbitmq", available_at=naive_dt)

        assert captured_values
        assert all(isinstance(v, datetime) and v.tzinfo == timezone.utc for v in captured_values)
        assert captured_values[0] == datetime(2026, 11, 23, 10, 0, 0, tzinfo=timezone.utc)
        # 同时验证 custom_qc_workspace_service._now_utc_aware() 返回 aware UTC
        aware = workspace_module._now_utc_aware()
        assert aware.tzinfo == timezone.utc
    finally:
        engine.dispose()


def test_p1_a4_non_0609_mark_running_and_retry_enforce_strict_cas(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service, engine, _sessions = _make_workspace_with_sqlite(monkeypatch, tmp_path)
    try:
        # 1) LX0916 任务：mark_batch_job_running 只能成功领取一次，不能覆盖 running/canceled
        job = service.create_batch_job(
            draft={
                "id": "draft-0916",
                "rule_code": "LUXIAN_0916",
                "name": "LX0916测试",
                "scene": "running",
            },
            created_by="tester",
            scope="running",
            filters={"rule_set_key": "luxian_0916_qc_v1"},
            record_ids=["V-1"],
            total_records=1,
        )
        job_id = job["id"]
        assert service.mark_batch_job_running(job_id=job_id) is True
        # 二次并发领取必须返回 False
        assert service.mark_batch_job_running(job_id=job_id) is False
        # running 状态下不允许 retry_batch_job
        assert service.retry_batch_job(job_id=job_id, created_by="tester") is None

        # 2) 自定义规则任务：queued 状态不允许 retry；取消后不允许 mark_batch_job_running 复活
        job_cancel = service.create_batch_job(
            draft={
                "id": "draft-custom",
                "rule_code": "CUSTOM-01",
                "name": "自定义规则",
                "scene": "final",
            },
            created_by="tester",
            scope="final",
            filters={"rule_set_key": "custom_rule_set"},
            record_ids=["V-2"],
            total_records=1,
        )
        assert service.retry_batch_job(job_id=job_cancel["id"], created_by="tester") is None
        service.cancel_batch_job(job_id=job_cancel["id"], created_by="tester")
        assert service.mark_batch_job_running(job_id=job_cancel["id"]) is False

        # 终态（canceled）允许 retry_batch_job 重置为 queued
        retried = service.retry_batch_job(job_id=job_cancel["id"], created_by="tester")
        assert retried is not None
        assert retried["status"] == "queued"
        # 重置为 queued 后可再次唯一领取
        assert service.mark_batch_job_running(job_id=job_cancel["id"]) is True
        assert service.mark_batch_job_running(job_id=job_cancel["id"]) is False
    finally:
        engine.dispose()


def test_p1_e3_csv_and_excel_exports_neutralize_formula_injection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service, engine, _sessions = _make_workspace_with_sqlite(monkeypatch, tmp_path)
    try:
        payloads = [
            '=CMD|"/C calc"!A0',
            "+SUM(A1:A2)",
            "-2+3",
            '@HYPERLINK("http://evil")',
            "\t=1+1",
        ]
        legacy_job = {
            "id": "=job-1",
            "rule_name": "+恶意任务名",
            "scene": "final",
            "scope": "final",
            "status": "completed",
            "filters": {},
            "summary": {"total_records": 1, "issue_records": 1, "compliant_records": 0, "rule_count": 1},
            "items": [
                {
                    "record_id": payloads[0],
                    "patient_name": payloads[1],
                    "department": payloads[2],
                    "rule_code": "R-001",
                    "rule_name": payloads[3],
                    "status": "non_compliant",
                    "is_compliant": False,
                    "findings": payloads[0],
                    "suggestion": payloads[4],
                    "evidence": payloads[1],
                    "confidence": 0.92,
                }
            ],
            "failed_records": [
                {
                    "record_id": "=fail-1",
                    "patient_name": "@bad",
                    "department": "-dept",
                    "error": "+err",
                }
            ],
        }
        csv_text = service.export_batch_job_csv(job=legacy_job).getvalue()
        assert "'=CMD" in csv_text
        assert "'+SUM(A1:A2)" in csv_text
        assert "'-2+3" in csv_text
        assert "'@HYPERLINK" in csv_text
        assert "'\t=1+1" in csv_text

        wb = load_workbook(BytesIO(service.export_batch_job_workbook(job=legacy_job).getvalue()))
        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    assert cell.data_type != "f", f"formula cell found in {sheet.title}!{cell.coordinate}: {cell.value}"
        assert wb["问题明细"]["A2"].value == '\'=CMD|"/C calc"!A0'
        assert wb["问题明细"]["L2"].value == pytest.approx(0.92)

        # 客户安全版（_export_customer_safe_csv / _export_customer_safe_workbook）也必须防护公式注入
        customer_job = {
            "id": "job-safe-1",
            "filters": {"rule_set_key": "luxian_0609_qc_v1"},
            "items": [
                {
                    "institute_id": "I-1",
                    "patient_id": "P-1",
                    "visit_id": "V-1",
                    "rule_id": "LX0609-01-01-01",
                    "rule_name": '=CMD|"/C calc"!A0',
                    "status": "non_compliant",
                    "reason_code": "+missing_doc",
                    "customer_conclusion": '=CMD|"/C calc"!A0',
                    "customer_suggestion": "+请立即整改",
                    "evidence": [],
                }
            ],
        }
        safe_csv = workspace_module._export_customer_safe_csv(customer_job, hmac_key="test-hmac-key").getvalue()
        assert "'=CMD" in safe_csv

        safe_wb = load_workbook(
            BytesIO(
                workspace_module._export_customer_safe_workbook(
                    customer_job, hmac_key="test-hmac-key"
                ).getvalue()
            )
        )
        for sheet in safe_wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    assert cell.data_type != "f"
        assert safe_wb["全部明细"]["C2"].value == '\'=CMD|"/C calc"!A0'
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 4. P1-A5: BatchConsumer 失败即时恢复分类 & WorkerRecovery.run 异步线程卸载
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p1_a5_batch_consumer_recovers_failed_job_before_defer_in_thread() -> None:
    loop_thread_id = threading.get_ident()
    recovery_thread_ids: list[int] = []

    class _Dispatch:
        mode = "rabbitmq"
        generation = 1
        recovery_kind: str | None = None
        last_failure_code: str | None = None

    class _Repo:
        def __init__(self) -> None:
            self.status = "queued"
            self.dispatch = _Dispatch()

        def get_dispatch(self, _job_id: str) -> Any:
            return self.dispatch

        def get_job_status(self, _job_id: str) -> str:
            return self.status

        def record_terminal_failure(self, _job_id: str, _gen: int, *, error_code: str) -> bool:
            self.dispatch.last_failure_code = error_code
            return True

    class _Delivery:
        def __init__(self, body: bytes) -> None:
            self.body = body
            self.acked = False

        async def ack(self) -> None:
            self.acked = True

        async def reject(self, *, requeue: bool = False) -> None:
            raise AssertionError("should not reject")

    repo = _Repo()
    job_id = str(uuid4())
    envelope = BatchDispatchEnvelope.new(job_id=job_id, generation=1, message_id=str(uuid4()))

    async def execute_that_fails(_env: BatchDispatchEnvelope) -> None:
        # 模拟常规失败：状态落为 failed，但尚未分类 recovery_kind / last_failure_code
        repo.status = "failed"

    def immediate_recovery(target_job_id: str) -> RecoveryOutcome:
        assert target_job_id == job_id
        recovery_thread_ids.append(threading.get_ident())
        repo.dispatch.last_failure_code = "worker_failed"
        return RecoveryOutcome.TERMINAL_FAILURE

    delivery = _Delivery(envelope.to_bytes())
    consumer = BatchConsumer(
        repository=repo,
        execute_job=execute_that_fails,
        recover_failed_job=immediate_recovery,
    )
    decision = await consumer.handle_delivery(delivery)
    assert decision is ConsumerDecision.ACK_FAILED_RECORDED
    assert delivery.acked is True
    assert len(recovery_thread_ids) == 1
    assert recovery_thread_ids[0] != loop_thread_id


@pytest.mark.asyncio
async def test_p1_a5_worker_recovery_run_offloads_sync_db_to_thread() -> None:
    loop_thread_id = threading.get_ident()
    observed_threads: list[tuple[str, int]] = []
    first_scan_done = asyncio.Event()

    class _RecordingRecovery(WorkerRecovery):
        def recover_startup_queued(self) -> dict[str, RecoveryOutcome]:
            observed_threads.append(("startup", threading.get_ident()))
            return {}

        def recover_failed_candidates(self) -> dict[str, RecoveryOutcome]:
            observed_threads.append(("failed", threading.get_ident()))
            if len([k for k, _ in observed_threads if k == "failed"]) >= 2:
                first_scan_done.set()
            return {}

        def recover_stale_once(self, *, now: datetime | None = None) -> dict[str, RecoveryOutcome]:
            observed_threads.append(("stale", threading.get_ident()))
            return {}

    recovery = _RecordingRecovery(
        repository=object(),
        workspace=object(),
        scan_interval_seconds=0.01,
    )
    task = asyncio.create_task(recovery.run())
    try:
        await asyncio.wait_for(first_scan_done.wait(), timeout=2.0)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert {name for name, _ in observed_threads} == {"startup", "failed", "stale"}
    assert all(tid != loop_thread_id for _, tid in observed_threads)


# ---------------------------------------------------------------------------
# 5. P2-A1 + P2-A3: Outbox 终态归档、心跳无 128 硬截断、daily_qc missing 不停摆
# ---------------------------------------------------------------------------


def test_p2_a1_outbox_maintenance_blocks_when_unconfirmed_outbox_remains(tmp_path: Path) -> None:
    db_file = tmp_path / "maint_p2a1.sqlite"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    sessions = sessionmaker(bind=engine)
    jobs = batch_job_identity_table()
    jobs.metadata.create_all(engine)
    repo = QCDispatchRepository(sessions, jobs, None)
    repo.dispatch_table.metadata.create_all(engine)
    maintenance = OutboxMaintenance(repo)
    now = datetime(2026, 11, 23, tzinfo=timezone.utc)
    try:
        job_id = str(uuid4())
        with sessions.begin() as session:
            session.execute(jobs.insert().values(id=job_id, status="failed", filters_json="{}"))
            repo.add_dispatch(session, job_id=job_id, mode="rabbitmq")
            session.execute(
                update(repo.outbox_table)
                .where(repo.outbox_table.c.job_id == job_id)
                .values(status="confirmed", confirmed_at=now - timedelta(days=35))
            )
            session.execute(
                update(repo.dispatch_table)
                .where(repo.dispatch_table.c.job_id == job_id)
                .values(status="failed", last_failure_code="worker_failed")
            )
            repo.ensure_due_delivery(job_id, 1, target="dead", available_at=now, session=session)

        # 存在未确认 dead outbox，不能搬移
        assert maintenance.archive(apply=True, now=now)["archived_rows"] == 0

        # dead outbox 也确认且过保留期后，两条均可归档
        with sessions.begin() as session:
            session.execute(
                update(repo.outbox_table)
                .where(repo.outbox_table.c.job_id == job_id, repo.outbox_table.c.target == "dead")
                .values(status="confirmed", confirmed_at=now - timedelta(days=35))
            )
        assert maintenance.archive(apply=True, now=now)["archived_rows"] == 2
    finally:
        engine.dispose()


def test_p2_a3_service_status_scans_beyond_128_stale_heartbeats(tmp_path: Path) -> None:
    settings = SimpleNamespace(
        QC_DISPATCH_STATE_DIR=str(tmp_path),
        DATABASE_URL="sqlite:///test.db",
        QC_RABBITMQ_URL="amqp://guest:guest@localhost:5672/medqc",
        QC_RABBITMQ_EXCHANGE="qc.exchange",
        QC_RABBITMQ_QUEUE="qc.main",
        QC_RABBITMQ_DEAD_QUEUE="qc.dead",
    )
    identity = deployment_identity(settings)
    services_dir = tmp_path / "services"
    services_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    stale_ts = (now - timedelta(hours=2)).timestamp()

    # 制造 150 个已过期的崩溃残留心跳文件（超过旧 128 截断上限）
    for i in range(150):
        stale_file = services_dir / f"worker-stale-{i:04d}.json"
        stale_file.write_text(
            Heartbeat(
                role="worker",
                deployment=identity,
                ready=True,
                observed_at=now - timedelta(hours=2),
            ).model_dump_json(),
            encoding="utf-8",
        )
        os.utime(stale_file, (stale_ts, stale_ts))

    # 写入最新活跃心跳文件（文件名按字母序在 128 之后）
    for role in ("publisher", "worker"):
        fresh_file = services_dir / f"zzz-{role}-active.json"
        fresh_file.write_text(
            Heartbeat(
                role=role,
                deployment=identity,
                ready=True,
                observed_at=now - timedelta(seconds=2),
            ).model_dump_json(),
            encoding="utf-8",
        )

    status = service_status(settings, now=now)
    assert status == {"publisher": True, "worker": True}


def test_p2_a3_daily_qc_store_missing_previous_job_does_not_skip_overlap(tmp_path: Path) -> None:
    db_file = tmp_path / "daily_qc_missing.sqlite"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    sessions = sessionmaker(bind=engine)
    meta, _plans, _runs = daily_qc_tables()
    meta.create_all(engine)
    store = ScheduleStore(sessions)
    try:
        definition = {
            "enabled": True,
            "time_of_day": "08:00",
            "timezone": "Asia/Shanghai",
            "rule_set_key": "luxian_0609_qc_v1",
            "scope": "running",
        }
        now = datetime(2026, 11, 22, 23, 30, tzinfo=timezone.utc)  # 2026-11-23 07:30 CST
        store.save("admin-1", definition, now)
        due = datetime(2026, 11, 23, 0, 5, tzinfo=timezone.utc)  # 2026-11-23 08:05 CST

        # 1) 历史任务缺失（"missing"）不再触发 skipped_overlap，应正常进入 submitting
        claimed = store.claim(due)
        assert claimed is not None
        run = store.prepare(claimed, due, previous_job_status="missing")
        assert run is not None
        assert run["state"] == "submitting"
        store.finish(claimed, run["id"], "submitted", due, job_id=run["job_id"])

        # 2) 上一任务仍在运行（"running"）仍正常触发 skipped_overlap
        next_due = due + timedelta(days=1)
        claimed2 = store.claim(next_due)
        assert claimed2 is not None
        run2 = store.prepare(claimed2, next_due, previous_job_status="running")
        assert run2 is not None
        assert run2["state"] == "skipped_overlap"
    finally:
        engine.dispose()
