from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from app.services.luxian_0609.engine import (
    FamilyExecutionContext,
    FamilyExecutionFailure,
    FamilyExecutionSuccess,
    Luxian0609ExecutionEngine,
)
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.executor_registry import (
    ExecutorRegistration,
    Luxian0609ExecutorRegistry,
)
from app.services.luxian_0609.execution_contract import FamilyExecutionEnvelope
from app.services.luxian_0609.native_execution import build_luxian_0609_native_result
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION


def _snapshot() -> Luxian0609EvidenceSnapshot:
    return Luxian0609EvidenceSnapshot.create(
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=(
            SourceObservation.create(
                source_key="surgery_record",
                query_state=QueryStatus.AVAILABLE,
                completeness=SourceCompleteness.COMPLETE,
                record_count=1,
                query_version="snapshot-provider-surgery_record-v1",
                snapshot_ref="sha256:" + "a" * 64,
            ),
        ),
        facts=(),
        document_refs=(),
        created_at="2026-07-16T00:00:00+00:00",
    )


@dataclass
class _Executor:
    callback: Any

    async def evaluate(self, context: FamilyExecutionContext) -> Any:
        return await self.callback(context)


def _contracts(*rule_ids: str):
    selected = set(rule_ids)
    return tuple(
        contract
        for contract in load_luxian_0609_rule_contracts()
        if contract.rule_id in selected
    )


def _envelope(context: FamilyExecutionContext) -> FamilyExecutionEnvelope:
    return FamilyExecutionEnvelope(
        results=tuple(
            build_luxian_0609_native_result(
                rule_id=rule_id,
                final_state="compliant",
                finding_kind="test_result",
                reason_code="test_result",
            )
            for rule_id in context.selected_rule_ids
        ),
        planned_rule_ids=context.selected_rule_ids,
    )


@pytest.mark.unit
def test_executor_registry_rejects_duplicate_or_unknown_keys():
    async def _evaluate(context: FamilyExecutionContext):
        return _envelope(context)

    registry = Luxian0609ExecutorRegistry()
    registry.register(
        ExecutorRegistration(
            executor_key="family_a",
            executor=_Executor(_evaluate),
        )
    )

    with pytest.raises(ValueError, match="duplicate executor_key"):
        registry.register(
            ExecutorRegistration(
                executor_key="family_a",
                executor=_Executor(_evaluate),
            )
        )
    with pytest.raises(KeyError, match="unregistered executor_key"):
        registry.resolve("family_b")


@pytest.mark.asyncio
async def test_engine_resolves_registry_and_passes_one_snapshot_to_every_family():
    snapshot = _snapshot()
    seen: list[tuple[str, Luxian0609EvidenceSnapshot, tuple[str, ...]]] = []

    def _executor(name: str):
        async def _evaluate(context: FamilyExecutionContext):
            seen.append((name, context.snapshot, context.selected_rule_ids))
            return _envelope(context)

        return _Executor(_evaluate)

    registry = Luxian0609ExecutorRegistry(
        (
            ExecutorRegistration(
                executor_key="basic_timeliness", executor=_executor("a")
            ),
            ExecutorRegistration(executor_key="surgery_gate", executor=_executor("b")),
        )
    )
    report = await Luxian0609ExecutionEngine(registry=registry).execute(
        executor_batches=(
            ("basic_timeliness", ("LX0609-001",)),
            ("surgery_gate", ("LX0609-003",)),
        ),
        snapshot=snapshot,
        contracts=_contracts("LX0609-001", "LX0609-003"),
        default_deadline_seconds=1.0,
        max_concurrency=1,
    )

    assert [type(item) for item in report.outcomes] == [
        FamilyExecutionSuccess,
        FamilyExecutionSuccess,
    ]
    assert [item.executor_key for item in report.outcomes] == [
        "basic_timeliness",
        "surgery_gate",
    ]
    assert seen == [
        ("a", snapshot, ("LX0609-001",)),
        ("b", snapshot, ("LX0609-003",)),
    ]
    assert seen[0][1] is seen[1][1]


@pytest.mark.asyncio
async def test_engine_runs_independent_families_with_bounded_concurrency():
    active = 0
    maximum_active = 0
    release = asyncio.Event()
    both_started = asyncio.Event()

    async def _evaluate(context: FamilyExecutionContext):
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        if active == 2:
            both_started.set()
        await release.wait()
        active -= 1
        return _envelope(context)

    registry = Luxian0609ExecutorRegistry(
        (
            ExecutorRegistration(
                executor_key="basic_timeliness", executor=_Executor(_evaluate)
            ),
            ExecutorRegistration(executor_key="surgery_gate", executor=_Executor(_evaluate)),
        )
    )
    task = asyncio.create_task(
        Luxian0609ExecutionEngine(registry=registry).execute(
            executor_batches=(
                ("basic_timeliness", ("LX0609-001",)),
                ("surgery_gate", ("LX0609-003",)),
            ),
            snapshot=_snapshot(),
            contracts=_contracts("LX0609-001", "LX0609-003"),
            default_deadline_seconds=1.0,
            max_concurrency=2,
        )
    )
    await asyncio.wait_for(both_started.wait(), timeout=0.5)
    release.set()
    await task

    assert maximum_active == 2
    assert [item.executor_key for item in task.result().outcomes] == [
        "basic_timeliness",
        "surgery_gate",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("cycle", [False, True])
async def test_engine_rejects_missing_or_cyclic_dependencies(cycle: bool):
    async def _evaluate(context: FamilyExecutionContext):
        return _envelope(context)

    registrations = [
        ExecutorRegistration(
            executor_key="basic_timeliness",
            executor=_Executor(_evaluate),
            depends_on=("surgery_gate",),
        )
    ]
    batches = (("basic_timeliness", ("LX0609-001",)),)
    contracts = _contracts("LX0609-001")
    if cycle:
        registrations.append(
            ExecutorRegistration(
                executor_key="surgery_gate",
                executor=_Executor(_evaluate),
                depends_on=("basic_timeliness",),
            )
        )
        batches = (
            ("basic_timeliness", ("LX0609-001",)),
            ("surgery_gate", ("LX0609-003",)),
        )
        contracts = _contracts("LX0609-001", "LX0609-003")

    with pytest.raises(
        ValueError,
        match="cyclic executor dependency" if cycle else "dependency is not selected",
    ):
        await Luxian0609ExecutionEngine(
            registry=Luxian0609ExecutorRegistry(registrations)
        ).execute(
            executor_batches=batches,
            snapshot=_snapshot(),
            contracts=contracts,
            default_deadline_seconds=1.0,
            max_concurrency=2,
        )


@pytest.mark.asyncio
async def test_engine_preserves_explicit_dependency_order():
    events: list[str] = []

    def _executor(name: str):
        async def _evaluate(context: FamilyExecutionContext):
            events.append(f"{name}:start")
            await asyncio.sleep(0)
            events.append(f"{name}:end")
            return _envelope(context)

        return _Executor(_evaluate)

    registry = Luxian0609ExecutorRegistry(
        (
            ExecutorRegistration(
                executor_key="basic_timeliness", executor=_executor("a")
            ),
            ExecutorRegistration(
                executor_key="surgery_gate",
                executor=_executor("b"),
                depends_on=("basic_timeliness",),
            ),
        )
    )
    await Luxian0609ExecutionEngine(registry=registry).execute(
        executor_batches=(
            ("basic_timeliness", ("LX0609-001",)),
            ("surgery_gate", ("LX0609-003",)),
        ),
        snapshot=_snapshot(),
        contracts=_contracts("LX0609-001", "LX0609-003"),
        default_deadline_seconds=1.0,
        max_concurrency=2,
    )

    assert events == ["a:start", "a:end", "b:start", "b:end"]


@pytest.mark.asyncio
async def test_engine_isolates_timeout_and_exception_without_echoing_error():
    async def _timeout(context: FamilyExecutionContext):
        await asyncio.sleep(0.05)

    async def _explode(context: FamilyExecutionContext):
        raise RuntimeError("Bearer secret raw patient marker")

    async def _ok(context: FamilyExecutionContext):
        return _envelope(context)

    registry = Luxian0609ExecutorRegistry(
        (
            ExecutorRegistration(
                executor_key="basic_timeliness", executor=_Executor(_timeout)
            ),
            ExecutorRegistration(executor_key="surgery_gate", executor=_Executor(_explode)),
            ExecutorRegistration(executor_key="exam_lab", executor=_Executor(_ok)),
        )
    )
    report = await Luxian0609ExecutionEngine(registry=registry).execute(
        executor_batches=(
            ("basic_timeliness", ("LX0609-001",)),
            ("surgery_gate", ("LX0609-003",)),
            ("exam_lab", ("LX0609-010",)),
        ),
        snapshot=_snapshot(),
        contracts=_contracts("LX0609-001", "LX0609-003", "LX0609-010"),
        default_deadline_seconds=0.01,
        max_concurrency=3,
    )

    assert [type(item) for item in report.outcomes] == [
        FamilyExecutionFailure,
        FamilyExecutionFailure,
        FamilyExecutionSuccess,
    ]
    assert [item.failure_kind for item in report.outcomes[:2]] == [
        "timeout",
        "exception",
    ]
    assert [
        outcome.envelope.results[0]["status"]
        for outcome in report.outcomes[:2]
    ] == ["technical_error", "technical_error"]
    assert "Bearer" not in repr(report)
    assert "patient" not in repr(report)


@pytest.mark.asyncio
async def test_engine_isolates_executor_internal_cancellation():
    async def _cancel(context: FamilyExecutionContext):
        raise asyncio.CancelledError

    async def _ok(context: FamilyExecutionContext):
        return _envelope(context)

    registry = Luxian0609ExecutorRegistry(
        (
            ExecutorRegistration(
                executor_key="basic_timeliness", executor=_Executor(_cancel)
            ),
            ExecutorRegistration(executor_key="surgery_gate", executor=_Executor(_ok)),
        )
    )
    report = await Luxian0609ExecutionEngine(registry=registry).execute(
        executor_batches=(
            ("basic_timeliness", ("LX0609-001",)),
            ("surgery_gate", ("LX0609-003",)),
        ),
        snapshot=_snapshot(),
        contracts=_contracts("LX0609-001", "LX0609-003"),
        default_deadline_seconds=1.0,
        max_concurrency=2,
    )

    assert isinstance(report.outcomes[0], FamilyExecutionFailure)
    assert report.outcomes[0].failure_kind == "cancelled"
    assert isinstance(report.outcomes[1], FamilyExecutionSuccess)


@pytest.mark.asyncio
async def test_engine_converts_invalid_envelope_to_family_technical_results():
    async def _missing(context: FamilyExecutionContext):
        return FamilyExecutionEnvelope(
            results=(),
            planned_rule_ids=context.selected_rule_ids,
        )

    registry = Luxian0609ExecutorRegistry(
        (
            ExecutorRegistration(
                executor_key="basic_timeliness", executor=_Executor(_missing)
            ),
        )
    )
    events: list[str] = []
    report = await Luxian0609ExecutionEngine(registry=registry).execute(
        executor_batches=(
            ("basic_timeliness", ("LX0609-001", "LX0609-002")),
        ),
        snapshot=_snapshot(),
        contracts=_contracts("LX0609-001", "LX0609-002"),
        default_deadline_seconds=1.0,
        max_concurrency=1,
        trace_sink=lambda event: events.append(str(event["event"])),
    )

    failure = report.outcomes[0]
    assert isinstance(failure, FamilyExecutionFailure)
    assert failure.failure_kind == "contract"
    assert failure.reason_code == "family_result_missing"
    assert [item["rule_id"] for item in failure.envelope.results] == [
        "LX0609-001",
        "LX0609-002",
    ]
    assert [item["status"] for item in failure.envelope.results] == [
        "technical_error",
        "technical_error",
    ]
    assert events == ["started", "failed"]


@pytest.mark.asyncio
async def test_engine_rejects_rule_contract_executor_mismatch():
    async def _evaluate(context: FamilyExecutionContext):
        return _envelope(context)

    registry = Luxian0609ExecutorRegistry(
        (
            ExecutorRegistration(
                executor_key="basic_timeliness", executor=_Executor(_evaluate)
            ),
        )
    )

    with pytest.raises(ValueError, match="family rule contract executor mismatch"):
        await Luxian0609ExecutionEngine(registry=registry).execute(
            executor_batches=(("basic_timeliness", ("LX0609-003",)),),
            snapshot=_snapshot(),
            contracts=_contracts("LX0609-003"),
            default_deadline_seconds=1.0,
            max_concurrency=1,
        )


@pytest.mark.asyncio
async def test_engine_propagates_parent_cancellation():
    started = asyncio.Event()

    async def _wait(context: FamilyExecutionContext):
        started.set()
        await asyncio.Event().wait()

    registry = Luxian0609ExecutorRegistry(
        (
            ExecutorRegistration(
                executor_key="basic_timeliness", executor=_Executor(_wait)
            ),
        )
    )
    task = asyncio.create_task(
        Luxian0609ExecutionEngine(registry=registry).execute(
            executor_batches=(("basic_timeliness", ("LX0609-001",)),),
            snapshot=_snapshot(),
            contracts=_contracts("LX0609-001"),
            default_deadline_seconds=10.0,
            max_concurrency=1,
        )
    )
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_engine_internal_failure_aborts_queued_families_and_cleans_tasks(
    monkeypatch,
):
    calls: list[str] = []

    async def _first(context: FamilyExecutionContext):
        calls.append("first")
        return _envelope(context)

    async def _second(context: FamilyExecutionContext):
        calls.append("second")
        return _envelope(context)

    registry = Luxian0609ExecutorRegistry(
        (
            ExecutorRegistration(
                executor_key="basic_timeliness", executor=_Executor(_first)
            ),
            ExecutorRegistration(
                executor_key="exam_lab", executor=_Executor(_second)
            ),
        )
    )
    monkeypatch.setattr(
        "app.services.luxian_0609.engine.validate_family_execution_envelope",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("validator failed")),
    )

    with pytest.raises(RuntimeError, match="validator failed"):
        await Luxian0609ExecutionEngine(registry=registry).execute(
            executor_batches=(
                ("basic_timeliness", ("LX0609-001",)),
                ("exam_lab", ("LX0609-010",)),
            ),
            snapshot=_snapshot(),
            contracts=_contracts("LX0609-001", "LX0609-010"),
            default_deadline_seconds=1.0,
            max_concurrency=1,
        )

    await asyncio.sleep(0)
    assert calls == ["first"]
