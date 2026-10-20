"""1016 引擎 P0：单点失败只影响该点，不再连带整族、整病例或整批任务。"""

from __future__ import annotations

from dataclasses import dataclass
import logging

import httpx
import pytest

from app.services import luxian_0609_result_aggregator as aggregator
from app.services.luxian_0609.canonical_result_finalizer import (
    CUSTOMER_RESULT_CONTRACT_VIOLATION,
    enforce_luxian_0609_customer_result_contract,
    finalize_luxian_0609_canonical_result,
    luxian_0609_customer_result_contract_holds,
)
from app.services.luxian_0609.engine import (
    FamilyExecutionContext,
    FamilyExecutionSuccess,
    Luxian0609ExecutionEngine,
)
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.execution_contract import FamilyExecutionEnvelope
from app.services.luxian_0609.executor_registry import (
    ExecutorRegistration,
    Luxian0609ExecutorRegistry,
)
from app.services.luxian_0609.llm_prompt_privacy import (
    PatientPrivacyViolation,
    PrivacyIdentityContextError,
    classify_luxian_0609_llm_call_failure,
    wrap_luxian_0609_llm_client,
)
from app.services.luxian_0609.native_execution import build_luxian_0609_native_result
from app.services.luxian_0609.rule_contracts import (
    CRITERION_KINDS,
    load_luxian_0609_rule_contracts,
)
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION
from app.services.luxian_0609.transfusion_course_presence import (
    classify_transfusion_course_records,
)
from app.services.qc_workspace.canonical_result_store import (
    LX0609_CUSTOMER_RESULT_CONTRACT_ERROR,
    validated_customer_explanation,
)
from app.services.qc_workspace.execution_failure import validate_failed_task_items
from app.services.qc_workspace.failed_rule_retry import (
    build_failed_rule_auto_retry_plan,
    build_failed_rule_retry_scope,
)
from app.services.luxian_0609_result_schema import CANONICAL_RESULT_DELIVERY_MODE


COMPLIANT_RULE = "LX0609-01-01-01"
RAISING_RULE = "LX0609-01-02-01"
UNEXPLAINED_RULE = "LX0609-04-02-01"
CASE = {"institute_id": "safe-inst", "patient_id": "safe-pat", "visit_id": "safe-visit"}


def _published(rule_id: str, status: str, reason_code: str, **extra) -> dict:
    return finalize_luxian_0609_canonical_result(
        {
            "rule_id": rule_id,
            "rule_code": rule_id,
            "qc_point_id": rule_id,
            "status": status,
            "reason_code": reason_code,
            "findings": "合成结论",
            **extra,
        }
    )


def _wrapper(rule_id: str) -> dict:
    return {"rule_id": rule_id, "name": f"合成规则{rule_id[-2:]}"}


@pytest.mark.unit
def test_non_compliant_without_explanation_is_isolated_before_save():
    published = _published(UNEXPLAINED_RULE, "non_compliant", "requirement_violated")
    # 第三轮整批失败的同类条目：保存层会拒收。
    with pytest.raises(ValueError, match=LX0609_CUSTOMER_RESULT_CONTRACT_ERROR):
        validated_customer_explanation(
            published, rule_id=UNEXPLAINED_RULE, status="non_compliant"
        )

    assert luxian_0609_customer_result_contract_holds(published) is False
    demoted = enforce_luxian_0609_customer_result_contract(
        published, wrapper=_wrapper(UNEXPLAINED_RULE)
    )
    assert demoted["status"] == "technical_error"
    assert demoted["reason_code"] == CUSTOMER_RESULT_CONTRACT_VIOLATION
    assert demoted["is_compliant"] is None
    assert "customer_display_facts" not in demoted


@pytest.mark.unit
def test_failed_criterion_satisfies_the_same_contract_in_finalizer_and_store():
    published = _published(
        UNEXPLAINED_RULE,
        "non_compliant",
        "requirement_violated",
        criterion_results=[
            {
                "criterion_id": "surgery_record_timeliness",
                "kind": sorted(CRITERION_KINDS)[0],
                "status": "failed",
                "reason_code": "threshold_exceeded",
            }
        ],
    )

    assert luxian_0609_customer_result_contract_holds(published) is True
    validated_customer_explanation(
        published, rule_id=UNEXPLAINED_RULE, status="non_compliant"
    )


@dataclass(frozen=True)
class _Decision:
    rule_id: str


@pytest.mark.unit
def test_one_bad_rule_does_not_block_the_case_or_the_job(monkeypatch):
    wrappers = [_wrapper(COMPLIANT_RULE), _wrapper(RAISING_RULE), _wrapper(UNEXPLAINED_RULE)]
    monkeypatch.setattr(
        aggregator,
        "_index_reduced_decisions",
        lambda **_: {item["rule_id"]: _Decision(item["rule_id"]) for item in wrappers},
    )

    def _finalize(*, decision, **_):
        if decision.rule_id == RAISING_RULE:
            raise ValueError("invalid customer display facts")
        if decision.rule_id == UNEXPLAINED_RULE:
            return _published(UNEXPLAINED_RULE, "non_compliant", "requirement_violated")
        return _published(COMPLIANT_RULE, "compliant", "requirement_satisfied")

    monkeypatch.setattr(aggregator, "finalize_luxian_0609_reduced_customer_result", _finalize)

    results = aggregator.aggregate_luxian_0609_results(
        wrapper_rules=wrappers,
        execution_results=[],
        delivery_mode=CANONICAL_RESULT_DELIVERY_MODE,
    )

    by_rule = {item["rule_id"]: item for item in results}
    assert [item["rule_id"] for item in results] == [item["rule_id"] for item in wrappers]
    assert by_rule[COMPLIANT_RULE]["status"] == "compliant"
    for rule_id in (RAISING_RULE, UNEXPLAINED_RULE):
        assert by_rule[rule_id]["status"] == "technical_error"
        assert by_rule[rule_id]["reason_code"] == CUSTOMER_RESULT_CONTRACT_VIOLATION

    # 保存层：坏点进入失败清单，其余条目通过与第三轮同一处的保存校验。
    items = [
        {**item, **CASE}
        for item in results
        if item["status"] not in {"technical_error", "uncertain"}
    ]
    failures = [
        {
            "rule_id": item["rule_id"],
            **CASE,
            "error_phase": "result_status",
            "reason_code": item["reason_code"],
        }
        for item in results
        if item["status"] == "technical_error"
    ]
    validate_failed_task_items(
        {
            "execution_status": "partial_failed",
            "completed_rule_count": len(items),
            "failed_rule_count": len(failures),
        },
        items,
        failures,
    )


@pytest.mark.unit
def test_automatic_retry_selects_only_retryable_failures():
    failures = [
        {"rule_id": UNEXPLAINED_RULE, **CASE, "error_phase": "result_status",
         "reason_code": CUSTOMER_RESULT_CONTRACT_VIOLATION},
        {"rule_id": "LX0609-07-01-01", **CASE, "error_phase": "result_status",
         "reason_code": "privacy_guard_blocked"},
        {"rule_id": "LX0609-01-02-02", **CASE, "error_phase": "result_status",
         "reason_code": "execution_program_error"},
        # 格式错误在温度 0 下重跑无效，也不补跑；只有超时等偶发错误进入补跑范围。
        {"rule_id": "LX0609-08-01-02", **CASE, "error_phase": "result_status",
         "reason_code": "model_invalid_output"},
        {"rule_id": "LX0609-08-01-04", **CASE, "error_phase": "result_status",
         "reason_code": "model_timeout"},
    ]
    summary = {"execution_status": "partial_failed"}

    plan = build_failed_rule_auto_retry_plan(summary=summary, failures=failures)
    assert plan["should_retry"] is True
    scope, _ = build_failed_rule_retry_scope(
        {"status": "failed", "summary": summary, "failed_records": failures, "filters": {}},
        automatic_only=True,
    )
    assert scope["rule_ids"] == ["LX0609-08-01-04"]

    deterministic_only = failures[:4]
    assert build_failed_rule_auto_retry_plan(
        summary=summary, failures=deterministic_only,
    )["should_retry"] is False


@pytest.mark.unit
@pytest.mark.parametrize(
    ("error", "reason_code"),
    [
        (PatientPrivacyViolation("blocked"), "privacy_guard_blocked"),
        (PrivacyIdentityContextError("blocked"), "privacy_guard_blocked"),
        (TimeoutError(), "model_timeout"),
        (httpx.ConnectTimeout("timeout"), "model_timeout"),
        (httpx.ConnectError("refused"), "model_transport_error"),
        (RuntimeError("upstream_http_error upstream_http_status=503"), "model_transport_error"),
        (ValueError("bad prompt"), "execution_program_error"),
        (KeyError("field"), "execution_program_error"),
    ],
)
def test_llm_call_failures_are_classified_instead_of_all_transport(error, reason_code):
    assert classify_luxian_0609_llm_call_failure(error) == reason_code


class _NeverCalledClient:
    calls = 0

    async def generate(self, prompt: str, **kwargs):
        type(self).calls += 1
        raise AssertionError("privacy guard must block before delegate")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_privacy_guard_block_is_logged_and_reported_as_its_own_reason(caplog):
    client = wrap_luxian_0609_llm_client(
        _NeverCalledClient(), identity_values=("合成身份值甲",),
    )
    rows = [{"document_id": "course-1", "content": "合成身份值甲 输注悬浮红细胞2U，过程顺利。"}]

    with caplog.at_level(logging.WARNING):
        result = await classify_transfusion_course_records(rows, client)

    assert _NeverCalledClient.calls == 0
    assert result.state == "technical_error"
    assert result.reason_code == "privacy_guard_blocked"
    assert any("隐私护栏拦截模型请求" in record.getMessage() for record in caplog.records)
    assert all("合成身份值甲" not in record.getMessage() for record in caplog.records)


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
                query_version="snapshot-provider-surgery_record-v2",
                snapshot_ref="sha256:" + "a" * 64,
            ),
        ),
        facts=(),
        document_refs=(),
        created_at="2026-10-17T00:00:00+00:00",
    )


@dataclass
class _Executor:
    async def evaluate(self, context: FamilyExecutionContext):
        # 只返回第一条规则的结果，模拟执行器漏掉同族另一条。
        return FamilyExecutionEnvelope(
            results=(
                build_luxian_0609_native_result(
                    rule_id=context.selected_rule_ids[0],
                    final_state="compliant",
                    finding_kind="test_result",
                    reason_code="test_result",
                ),
            ),
            planned_rule_ids=context.selected_rule_ids,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_engine_keeps_completed_rules_when_one_family_rule_is_missing():
    rule_ids = (COMPLIANT_RULE, RAISING_RULE)
    report = await Luxian0609ExecutionEngine(
        registry=Luxian0609ExecutorRegistry(
            (ExecutorRegistration(executor_key="basic_timeliness", executor=_Executor()),)
        )
    ).execute(
        executor_batches=(("basic_timeliness", rule_ids),),
        snapshot=_snapshot(),
        contracts=tuple(
            item for item in load_luxian_0609_rule_contracts() if item.rule_id in rule_ids
        ),
        default_deadline_seconds=1.0,
        max_concurrency=1,
    )

    outcome = report.outcomes[0]
    assert isinstance(outcome, FamilyExecutionSuccess)
    assert [item["status"] for item in outcome.envelope.results] == [
        "compliant",
        "technical_error",
    ]
    assert outcome.envelope.results[1]["metadata"]["reason_code"] == "family_result_missing"
