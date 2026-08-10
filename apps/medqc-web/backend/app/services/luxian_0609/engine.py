"""LX0609 注册表驱动的规则族调度骨架。

本阶段只统一调度、快照传递、deadline 和故障隔离；临床结果仍由现有执行器
生成，下一阶段再统一 exactly-once 和 ``RuleDecision`` 契约。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import math
from typing import Any, Callable, Iterable, Mapping

from app.services.llm_observability import llm_executor_observation_context

from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .execution_contract import (
    FamilyExecutionEnvelope,
    build_family_technical_envelope,
    validate_family_execution_envelope,
)
from .executor_registry import (
    ExecutorRegistration,
    Luxian0609ExecutorRegistry,
)
from .rule_contracts import Luxian0609RuleContract


logger = logging.getLogger(__name__)


_FAILURE_REASON_CODES = {
    "cancelled": "family_execution_cancelled",
    "contract": "family_result_contract_violation",
    "dependency": "family_dependency_failed",
    "exception": "family_execution_failed",
    "timeout": "family_execution_timeout",
}

SafeTraceSink = Callable[[Mapping[str, Any]], None]


@dataclass(frozen=True)
class FamilyExecutionContext:
    selected_rule_ids: tuple[str, ...]
    snapshot: Luxian0609EvidenceSnapshot
    contracts: tuple[Luxian0609RuleContract, ...]
    deadline_seconds: float
    trace_sink: SafeTraceSink | None = None

    def __post_init__(self) -> None:
        if not self.selected_rule_ids or len(self.selected_rule_ids) != len(
            set(self.selected_rule_ids)
        ):
            raise ValueError("invalid family rule scope")
        if not isinstance(self.snapshot, Luxian0609EvidenceSnapshot):
            raise TypeError("snapshot must be Luxian0609EvidenceSnapshot")
        if tuple(item.rule_id for item in self.contracts) != self.selected_rule_ids:
            raise ValueError("family contracts must match selected rules")
        if (
            isinstance(self.deadline_seconds, bool)
            or not isinstance(self.deadline_seconds, (int, float))
            or not math.isfinite(self.deadline_seconds)
            or self.deadline_seconds <= 0
        ):
            raise ValueError("deadline_seconds must be positive")


@dataclass(frozen=True)
class FamilyExecutionSuccess:
    executor_key: str
    selected_rule_ids: tuple[str, ...]
    envelope: FamilyExecutionEnvelope

    def __post_init__(self) -> None:
        if self.envelope.planned_rule_ids != self.selected_rule_ids:
            raise ValueError("success envelope scope mismatch")


@dataclass(frozen=True)
class FamilyExecutionFailure:
    executor_key: str
    selected_rule_ids: tuple[str, ...]
    failure_kind: str
    reason_code: str
    envelope: FamilyExecutionEnvelope

    def __post_init__(self) -> None:
        if self.failure_kind not in _FAILURE_REASON_CODES:
            raise ValueError("invalid family failure kind")
        if not self.reason_code or self.envelope.planned_rule_ids != self.selected_rule_ids:
            raise ValueError("failure envelope scope mismatch")

    @classmethod
    def create(
        cls,
        *,
        executor_key: str,
        selected_rule_ids: tuple[str, ...],
        failure_kind: str,
        reason_code: str = "",
        envelope: FamilyExecutionEnvelope | None = None,
    ) -> FamilyExecutionFailure:
        if failure_kind not in _FAILURE_REASON_CODES:
            raise ValueError("invalid family failure kind")
        return cls(
            executor_key=executor_key,
            selected_rule_ids=selected_rule_ids,
            failure_kind=failure_kind,
            reason_code=reason_code or _FAILURE_REASON_CODES[failure_kind],
            envelope=envelope
            or build_family_technical_envelope(
                expected_rule_ids=selected_rule_ids,
                reason_code=reason_code or _FAILURE_REASON_CODES[failure_kind],
            ),
        )


FamilyExecutionOutcome = FamilyExecutionSuccess | FamilyExecutionFailure


@dataclass(frozen=True)
class Luxian0609EngineReport:
    outcomes: tuple[FamilyExecutionOutcome, ...]


def _emit_trace(
    sink: SafeTraceSink | None,
    *,
    executor_key: str,
    event: str,
    rule_count: int,
    reason_code: str = "",
) -> None:
    if sink is None:
        return
    try:
        sink(
            {
                "event": event,
                "executor_key": executor_key,
                "reason_code": reason_code,
                "rule_count": rule_count,
            }
        )
    except Exception:
        # trace 是诊断旁路，禁止反向影响临床执行。
        return


def _validate_dependency_graph(
    registrations: Mapping[str, ExecutorRegistration],
) -> None:
    for registration in registrations.values():
        for dependency in registration.depends_on:
            if dependency not in registrations:
                raise ValueError("executor dependency is not selected")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(executor_key: str) -> None:
        if executor_key in visiting:
            raise ValueError("cyclic executor dependency")
        if executor_key in visited:
            return
        visiting.add(executor_key)
        for dependency in registrations[executor_key].depends_on:
            visit(dependency)
        visiting.remove(executor_key)
        visited.add(executor_key)

    for key in registrations:
        visit(key)


class Luxian0609ExecutionEngine:
    def __init__(self, *, registry: Luxian0609ExecutorRegistry) -> None:
        if not isinstance(registry, Luxian0609ExecutorRegistry):
            raise TypeError("registry must be Luxian0609ExecutorRegistry")
        self._registry = registry

    async def execute(
        self,
        *,
        executor_batches: Iterable[tuple[str, tuple[str, ...]]],
        snapshot: Luxian0609EvidenceSnapshot,
        contracts: Iterable[Luxian0609RuleContract],
        default_deadline_seconds: float,
        max_concurrency: int,
        trace_sink: SafeTraceSink | None = None,
    ) -> Luxian0609EngineReport:
        batches = tuple(executor_batches)
        if not batches:
            return Luxian0609EngineReport(())
        if (
            isinstance(max_concurrency, bool)
            or not isinstance(max_concurrency, int)
            or max_concurrency <= 0
        ):
            raise ValueError("max_concurrency must be positive")
        if (
            isinstance(default_deadline_seconds, bool)
            or not isinstance(default_deadline_seconds, (int, float))
            or not math.isfinite(default_deadline_seconds)
            or default_deadline_seconds <= 0
        ):
            raise ValueError("default_deadline_seconds must be positive")

        executor_keys = tuple(str(item[0] or "").strip() for item in batches)
        if len(executor_keys) != len(set(executor_keys)):
            raise ValueError("duplicate executor batch")
        registrations = {
            executor_key: self._registry.resolve(executor_key)
            for executor_key in executor_keys
        }
        _validate_dependency_graph(registrations)

        contracts_by_id: dict[str, Luxian0609RuleContract] = {}
        for contract in contracts:
            if not isinstance(contract, Luxian0609RuleContract):
                raise TypeError("contracts must contain Luxian0609RuleContract")
            if contract.rule_id in contracts_by_id:
                raise ValueError("duplicate rule contract")
            contracts_by_id[contract.rule_id] = contract

        contexts: dict[str, FamilyExecutionContext] = {}
        seen_rule_ids: set[str] = set()
        for executor_key, rule_ids in batches:
            if (
                not isinstance(rule_ids, tuple)
                or not rule_ids
                or len(rule_ids) != len(set(rule_ids))
                or any(rule_id in seen_rule_ids for rule_id in rule_ids)
            ):
                raise ValueError("invalid executor rule batch")
            try:
                family_contracts = tuple(contracts_by_id[rule_id] for rule_id in rule_ids)
            except KeyError:
                raise ValueError("missing family rule contract") from None
            if any(contract.executor_key != executor_key for contract in family_contracts):
                raise ValueError("family rule contract executor mismatch")
            seen_rule_ids.update(rule_ids)
            registration = registrations[executor_key]
            contexts[executor_key] = FamilyExecutionContext(
                selected_rule_ids=rule_ids,
                snapshot=snapshot,
                contracts=family_contracts,
                deadline_seconds=float(
                    registration.deadline_seconds or default_deadline_seconds
                ),
                trace_sink=trace_sink,
            )

        semaphore = asyncio.Semaphore(max_concurrency)
        abort_event = asyncio.Event()
        tasks: dict[str, asyncio.Task[FamilyExecutionOutcome]] = {}

        async def run_family(executor_key: str) -> FamilyExecutionOutcome:
            registration = registrations[executor_key]
            context = contexts[executor_key]
            for dependency in registration.depends_on:
                dependency_outcome = await tasks[dependency]
                if isinstance(dependency_outcome, FamilyExecutionFailure):
                    failure = FamilyExecutionFailure.create(
                        executor_key=executor_key,
                        selected_rule_ids=context.selected_rule_ids,
                        failure_kind="dependency",
                    )
                    _emit_trace(
                        trace_sink,
                        executor_key=executor_key,
                        event="failed",
                        rule_count=len(context.selected_rule_ids),
                        reason_code=failure.reason_code,
                    )
                    return failure

            async with semaphore:
                if abort_event.is_set():
                    return FamilyExecutionFailure.create(
                        executor_key=executor_key,
                        selected_rule_ids=context.selected_rule_ids,
                        failure_kind="dependency",
                        reason_code="engine_execution_aborted",
                    )
                _emit_trace(
                    trace_sink,
                    executor_key=executor_key,
                    event="started",
                    rule_count=len(context.selected_rule_ids),
                )
                # ContextVar 会在 create_task 时复制；并发规则族各自携带真实执行器键。
                with llm_executor_observation_context(executor_key):
                    evaluation_task = asyncio.create_task(
                        registration.executor.evaluate(context)
                    )
                try:
                    done, _ = await asyncio.wait(
                        {evaluation_task},
                        timeout=context.deadline_seconds,
                    )
                except asyncio.CancelledError:
                    # 外层取消必须清理正在执行的 family，并继续向上抛。
                    evaluation_task.cancel()
                    await asyncio.gather(evaluation_task, return_exceptions=True)
                    raise
                if not done:
                    evaluation_task.cancel()
                    await asyncio.gather(evaluation_task, return_exceptions=True)
                    failure_kind = "timeout"
                else:
                    try:
                        payload = evaluation_task.result()
                    except asyncio.CancelledError:
                        # 执行器自行取消只污染本族，不得误伤独立 family。
                        failure_kind = "cancelled"
                    except Exception:
                        logger.exception(
                            "LX0609 规则族执行适配失败: executor_key=%s",
                            executor_key,
                        )
                        failure_kind = "exception"
                    else:
                        if not isinstance(payload, FamilyExecutionEnvelope):
                            failure_kind = "contract"
                            contract_reason_code = "family_envelope_invalid"
                        else:
                            validation = validate_family_execution_envelope(
                                envelope=payload,
                                expected_rule_ids=context.selected_rule_ids,
                            )
                            if validation.valid:
                                _emit_trace(
                                    trace_sink,
                                    executor_key=executor_key,
                                    event="completed",
                                    rule_count=len(context.selected_rule_ids),
                                )
                                return FamilyExecutionSuccess(
                                    executor_key=executor_key,
                                    selected_rule_ids=context.selected_rule_ids,
                                    envelope=validation.envelope,
                                )
                            failure_kind = "contract"
                            contract_reason_code = validation.reason_code
                            payload = validation.envelope

                failure = FamilyExecutionFailure.create(
                    executor_key=executor_key,
                    selected_rule_ids=context.selected_rule_ids,
                    failure_kind=failure_kind,
                    reason_code=(
                        contract_reason_code if failure_kind == "contract" else ""
                    ),
                    envelope=(
                        payload
                        if failure_kind == "contract"
                        and isinstance(payload, FamilyExecutionEnvelope)
                        else None
                    ),
                )
                _emit_trace(
                    trace_sink,
                    executor_key=executor_key,
                    event="failed",
                    rule_count=len(context.selected_rule_ids),
                    reason_code=failure.reason_code,
                )
                return failure

        async def run(executor_key: str) -> FamilyExecutionOutcome:
            try:
                return await run_family(executor_key)
            except asyncio.CancelledError:
                raise
            except Exception:
                # 引擎内部异常必须先阻止尚未开始的族进入执行器，再由外层统一
                # 取消和等待所有任务，避免请求返回后仍产生未计量的模型调用。
                abort_event.set()
                raise

        for executor_key in executor_keys:
            tasks[executor_key] = asyncio.create_task(run(executor_key))
        try:
            outcomes = await asyncio.gather(*(tasks[key] for key in executor_keys))
        except asyncio.CancelledError:
            for task in tasks.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)
            raise
        except Exception:
            abort_event.set()
            for task in tasks.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)
            raise
        return Luxian0609EngineReport(tuple(outcomes))
