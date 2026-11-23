from __future__ import annotations

from tests.luxian_0609_identity_test_support import published_rule_ids

from datetime import datetime
from types import SimpleNamespace

import pytest

from transfusion_order_test_support import OPEN_TRANSFUSION_ORDER, FrozenTransfusionProtocolClient
from intraoperative_transfusion_test_support import UNKNOWN, FrozenIntraoperativeClient

from app.core.settings import Settings
from app.routers.qc_sichuan import _build_record_status_counts
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
    summarize_luxian_0609_results,
)
from app.services.luxian_0609_evidence_formatter import format_luxian_0609_evidence
from app.services.luxian_0609_programmatic_rules import evaluate_luxian_0609_programmatic_rules
from app.services.luxian_0609_result_schema import apply_luxian_0609_result_schema
from app.services.luxian_0609.rule_decision_settings import (
    FULL_RULE_DECISION_OVERRIDES,
    RULE_DECISION_ROLLOUT_GROUPS,
)
from app.services.sichuan_qc_service import SichuanQCService
import app.services.sichuan_qc_service as sichuan_qc_service_module
from app.services.luxian_0609_trigger_gate import (
    TRIGGER_ABSENT,
    TRIGGER_DATA_GAP,
    Luxian0609GateDecision,
    TRIGGER_PRESENT,
    decision_to_result,
    evaluate_luxian_0609_trigger_gates,
    filter_executable_rules_by_gate,
)
from app.services.luxian_0609_llm_gate import evaluate_luxian_0609_trigger_gates_with_llm
from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609 import native_course_quality_execution as native_course
from app.services.luxian_0609 import native_surgery_document_execution as surgery_doc
from app.services.luxian_0609 import native_surgery_gate_execution as surgery_gate
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.native_execution import NativeExecutionResult
from app.services.luxian_0609.native_consultation_episode_execution import (
    NativeConsultationEpisodeExecutionResult,
)
from app.services.luxian_0609 import source_evidence_reader
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.evidence_material import (
    Luxian0609EvidenceMaterialStore,
    Luxian0609EvidenceReadSession,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_mdt_execution import NativeMdtExecutionResult
from app.services.luxian_0609.native_package import (
    Luxian0609PackagePlan,
    load_luxian_0609_dependency_inventory,
    resolve_package_entry_execution_rule_ids,
)
from app.services.luxian_0609.surgery_text_fact_contract import (
    LX0609_025_REQUIRED_FIELDS,
)
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY


def _use_synthetic_legacy_bundle_material(monkeypatch):
    """Bundle兼容投影只接收本用例资料；Native仍使用各用例独立的真实Provider/材料会话。"""
    monkeypatch.setattr(
        "app.services.sample_programmatic_evidence._fetch_source_table_fallback_items",
        lambda *_args, **_kwargs: ([], {}),
    )
    monkeypatch.setattr(
        "app.services.sample_programmatic_evidence._fetch_detail_service_fallback_items",
        lambda *_args, **_kwargs: [],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_ids", (["LX0609-01-01-01"], [], None))
async def test_luxian_direct_service_rejects_customer_aggregation_without_unified_engine(
    monkeypatch,
    rule_ids,
):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    monkeypatch.setattr(
        sichuan_qc_service_module,
        "get_settings",
        lambda: SimpleNamespace(
            LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
            LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False,
        ),
    )

    with pytest.raises(ValueError, match="客户结果聚合已开启，但统一Native引擎未启用"):
        await SichuanQCService().evaluate_running_final_bundle_input(
            bundle={"scene": "running", "structured_context": {"documents": {}}},
            rule_ids=rule_ids,
            rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        )


@pytest.mark.asyncio
async def test_formal_direct_service_rejects_exam_lab_compatibility_before_legacy_prepare(
    monkeypatch,
):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    monkeypatch.setattr(
        sichuan_qc_service_module,
        "get_settings",
        lambda: _all_native_settings(
            LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
            LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=False,
        ),
    )

    with pytest.raises(ValueError, match="正式质控禁止兼容执行.*LX0609-06-01-02.*LXE-23"):
        await SichuanQCService().evaluate_running_final_bundle_input(
            bundle={"scene": "running", "structured_context": {"documents": {}}},
            rule_ids=["LX0609-06-01-02"],
            rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        )


def _wrapper(
    rule_id: str,
    *,
    name: str,
    mapped_rule_ids: list[str],
    primary: str | None = None,
    trigger_condition: str,
    data_dependencies: list[str] | None = None,
    dependency_type: str = "单文书",
) -> dict:
    return {
        "rule_id": rule_id,
        "name": name,
        "mapped_rule_ids": mapped_rule_ids,
        "primary_execution_rule_id": primary or mapped_rule_ids[0],
        "trigger_condition": trigger_condition,
        "dependency_type": dependency_type,
        "data_dependencies": data_dependencies or [],
    }


@pytest.mark.asyncio
async def test_paused_040_enabled_bypasses_all_dispatch_and_reports_zero_usage(monkeypatch):
    await _assert_current_paused_public_entry(monkeypatch, ("LX0609-04-01-03",), settings_overrides={}, documents={})


def test_orchestrated_aggregation_projects_usage_executor_key_without_forging_unattributed_result(
    monkeypatch,
):
    customer_results = [
        {"rule_id": "LX0609-01-01-01", "metadata": {}},
        {"rule_id": "LX0609-01-02-01", "metadata": {}},
    ]
    monkeypatch.setattr(
        luxian_execution,
        "aggregate_luxian_0609_results",
        lambda **_kwargs: customer_results,
    )
    context = luxian_execution.Luxian0609ExecutionContext(
        enabled=True,
        native_usage_attributions=(
            luxian_execution.build_family_usage_attribution(
                executor_key="consultation_quality",
                covered_customer_rule_ids=("LX0609-01-01-01",),
                llm_call_count=1,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                api_time=0.0,
            ),
        ),
    )

    delivered = luxian_execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []},
        context=context,
        visit_id="V",
        model_name="",
        evidence_payload=None,
    )

    by_rule_id = {item["rule_id"]: item for item in delivered["results"]}
    assert by_rule_id["LX0609-01-01-01"]["metadata"]["executor_key"] == "consultation_quality"
    assert "executor_key" not in by_rule_id["LX0609-01-02-01"]["metadata"]


def test_formal_orchestration_explicitly_delivers_canonical_mode(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _capture_aggregate(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        luxian_execution,
        "aggregate_luxian_0609_results",
        _capture_aggregate,
    )
    context = luxian_execution.Luxian0609ExecutionContext(
        enabled=True,
        delivery_mode=luxian_execution.CANONICAL_RESULT_DELIVERY_MODE,
    )

    delivered = luxian_execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []},
        context=context,
        visit_id="V",
        model_name="unused",
        evidence_payload=None,
    )

    assert captured["delivery_mode"] == "canonical_straight_through"
    assert delivered["luxian_0609_delivery_mode"] == "canonical_straight_through"


@pytest.mark.parametrize(
    ("attributions", "customer_result", "error_match"),
    (
        (("invalid",), {"rule_id": "LX0609-01-01-01", "metadata": {}}, "invalid native usage attribution"),
        (
            (
                luxian_execution.build_family_usage_attribution(
                    executor_key="basic_timeliness",
                    covered_customer_rule_ids=("LX0609-01-01-01",),
                    llm_call_count=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    api_time=0.0,
                ),
                luxian_execution.build_family_usage_attribution(
                    executor_key="exam_lab",
                    covered_customer_rule_ids=("LX0609-01-01-01",),
                    llm_call_count=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    api_time=0.0,
                ),
            ),
            {"rule_id": "LX0609-01-01-01", "metadata": {}},
            "duplicate native usage attribution",
        ),
        (
            (
                luxian_execution.build_family_usage_attribution(
                    executor_key="surgery_mdt",
                    covered_customer_rule_ids=("LX0609-01-01-01",),
                    llm_call_count=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    api_time=0.0,
                ),
                luxian_execution.build_family_usage_attribution(
                    executor_key="surgery_mdt",
                    covered_customer_rule_ids=("LX0609-01-01-01",),
                    llm_call_count=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    api_time=0.0,
                ),
            ),
            {"rule_id": "LX0609-01-01-01", "metadata": {}},
            "duplicate native usage attribution",
        ),
        (
            (
                luxian_execution.build_family_usage_attribution(
                    executor_key="consultation_quality",
                    covered_customer_rule_ids=("LX0609-01-01-01",),
                    llm_call_count=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    api_time=0.0,
                ),
            ),
            {
                "rule_id": "LX0609-01-01-01",
                "metadata": {"executor_key": "basic_timeliness"},
            },
            "conflicting customer result executor_key",
        ),
    ),
)
def test_orchestrated_aggregation_rejects_invalid_usage_executor_attribution(
    monkeypatch,
    attributions,
    customer_result,
    error_match,
):
    monkeypatch.setattr(
        luxian_execution,
        "aggregate_luxian_0609_results",
        lambda **_kwargs: [customer_result],
    )

    with pytest.raises(ValueError, match=error_match):
        luxian_execution.aggregate_luxian_0609_orchestrated_results(
            orchestrated={"results": []},
            context=luxian_execution.Luxian0609ExecutionContext(
                enabled=True,
                native_usage_attributions=attributions,
            ),
            visit_id="V",
            model_name="",
            evidence_payload=None,
        )


async def _async_value(value):
    return value


_PRODUCTION_FAMILY_MAX_CONCURRENCY = Settings.model_fields[
    "LUXIAN_0609_FAMILY_MAX_CONCURRENCY"
].default


def _all_native_settings(**overrides):
    values = {
        "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": True,
        "LUXIAN_0609_TRIGGER_GATE_ENABLED": False,
        "LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED": False,
        "LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED": False,
        "LUXIAN_0609_NATIVE_EXECUTION_ENABLED": True,
        "LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED": True,
        "LUXIAN_0609_NATIVE_CONSULTATION_ENABLED": True,
        "LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED": True,
        "LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED": True,
        "LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED": True,
        "LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED": True,
        "LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED": True,
        "LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED": True,
        "LUXIAN_0609_NATIVE_MDT_040_ENABLED": True,
        "LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED": True,
        "LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED": False,
        "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": False,
        "LUXIAN_0609_RULE_DECISION_007_ENABLED": False,
        "LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED": False,
        "LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED": False,
        "LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED": False,
        # 统一引擎族并发上限是生产 Settings 必备字段；取模型默认值，避免替身与合同漂移。
        "LUXIAN_0609_FAMILY_MAX_CONCURRENCY": _PRODUCTION_FAMILY_MAX_CONCURRENCY,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _safe_evidence_snapshot() -> Luxian0609EvidenceSnapshot:
    return Luxian0609EvidenceSnapshot.create(
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=(
            SourceObservation.create(
                source_key="surgery_record",
                query_state=QueryStatus.EMPTY,
                completeness=SourceCompleteness.COMPLETE,
                record_count=0,
                query_version="snapshot-provider-surgery_record-v2",
                snapshot_ref=f"sha256:{'a' * 64}",
            ),
        ),
        facts=(),
        document_refs=(),
        created_at="2026-07-16T12:00:00+08:00",
    )


def _safe_evidence_session() -> Luxian0609EvidenceReadSession:
    snapshot = _safe_evidence_snapshot()
    return Luxian0609EvidenceReadSession(
        snapshot=snapshot,
        materials=Luxian0609EvidenceMaterialStore.create(
            snapshot=snapshot,
            sources={},
        ),
    )


def _rule_007_evidence_session() -> Luxian0609EvidenceReadSession:
    rows_by_source = {
        "inpat_nondrug_order.unstable_order": [],
        "inpat_registration": [
            {"admission_datetime": "2026-01-01 08:00:00"}
        ],
        "daily_course_record": [
            {
                "record_content": "患者病情稳定，继续当前治疗。",
                "record_time": "2026-01-01 09:00:00",
            },
            {
                "record_content": "患者症状改善，继续观察。",
                "record_time": "2026-01-02 09:00:00",
            },
        ],
        "senior_course_record": [],
    }

    def read(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-02-01-03",),
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        evaluation_as_of_date="2026-01-03",
        row_reader=read,
        additional_source_keys=("daily_course_record", "senior_course_record"),
    )


def _course_severity_evidence_session() -> Luxian0609EvidenceReadSession:
    rows_by_source = {
        "inpat_nondrug_order.severity_order": [
            {
                "severity": "serious",
                "prescribed_datetime": "2026-01-01 23:59:59",
                "row_ref": "a" * 64,
            }
        ],
        "daily_course_record": [
            {
                "record_content": "病重患者日常病程记录。",
                "record_time": "2026-01-01 00:01:00",
            },
            {
                "record_content": "病重患者再次病程记录。",
                "record_time": "2026-01-03 23:59:59",
            },
        ],
        "senior_course_record": [],
    }

    def read(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-02-01-04", "LX0609-02-01-05"),
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        evaluation_as_of_date="2026-01-03",
        row_reader=read,
        additional_source_keys=("inpat_nondrug_order.severity_order",),
    )


def _basic_timeliness_evidence_session() -> Luxian0609EvidenceReadSession:
    rows_by_source = {
        "inpat_registration": [
            {"admission_datetime": "2026-01-01 08:00:00"}
        ],
        "admission_record": [
            {
                "document_title": "入院记录",
                "admission_datetime": "2026-01-01 08:00:00",
                "record_time": "2026-01-01 09:00:00",
                "chief_complaint": "反复腹痛三天",
            }
        ],
        "daily_course_record": [
            {
                "document_title": "主治医师首次查房记录",
                "record_time": "2026-01-02 09:00:00",
            }
        ],
        "first_course_record": [
            {
                "document_title": "首次病程记录",
                "record_time": "2026-01-01 15:00:00",
                "record_content": "患者入院后完成病史采集、体格检查和诊疗计划。",
            }
        ],
        "rescue_record": [],
        "senior_course_record": [
            {
                "document_title": "副主任医师首次查房记录",
                "record_time": "2026-01-03 09:00:00",
            }
        ],
    }

    def read(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(
            "LX0609-01-01-01",
            "LX0609-01-02-01",
            "LX0609-09-01-01",
            "LX0609-02-01-01",
            "LX0609-02-01-02",
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        evaluation_as_of_date="2026-07-16",
        evaluation_horizon_policy="frozen_task_date",
        row_reader=read,
        additional_source_keys=(
            "admission_record",
            "daily_course_record",
            "first_course_record",
            "inpat_registration",
            "rescue_record",
            "senior_course_record",
        ),
    )


def _transfusion_044_047_evidence_session() -> Luxian0609EvidenceReadSession:
    course_text = (
        "输血目的：纠正贫血；2026-01-01 14:20 开始输血，"
        "输注去白悬浮红细胞2U。输血过程中严密观察，生命体征平稳；"
        "2026-01-01 16:10 输血结束后评价未见异常，无输血不良反应。"
    )
    rows_by_source = {
        # 044–046 按已开立且未取消的输血医嘱触发。
        "inpat_nondrug_order": [dict(OPEN_TRANSFUSION_ORDER)],
        "mr_bloodtrans": [
            {"transfution_datetime": datetime(2026, 1, 1, 14, 20)}
        ],
        "bloodtrans_record": [
            {
                "document_id": "typed-transfusion-document",
                "record_content": course_text,
                "record_time": "2026-01-01 16:20:00",
            }
        ],
        "daily_course_record": [
            {
                "document_id": "typed-daily-document",
                "document_title": "输血后效果评价记录",
                "record_content": "输血后复查血红蛋白较前改善，输血有效。",
                "record_time": "2026-01-01 17:00:00",
            }
        ],
    }

    def read(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(
            "LX0609-07-01-02",
            "LX0609-07-02-01",
            "LX0609-07-02-02",
            "LX0609-07-03-01",
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )


def test_evidence_snapshot_rule_refs_bind_all_49_to_one_hash() -> None:
    selected = published_rule_ids(1, 49)
    snapshot = _safe_evidence_snapshot()

    refs = luxian_execution.build_luxian_0609_evidence_snapshot_rule_refs(
        snapshot=snapshot,
        selected_rule_ids=selected,
    )

    assert tuple(rule_id for rule_id, _ in refs) == selected
    assert {snapshot_hash for _, snapshot_hash in refs} == {snapshot.snapshot_hash}
    with pytest.raises(ValueError, match="invalid LX0609 snapshot rule scope"):
        luxian_execution.build_luxian_0609_evidence_snapshot_rule_refs(
            snapshot=snapshot,
            selected_rule_ids=("LX0609-999",),
        )


@pytest.mark.asyncio
async def test_unified_engine_uses_registry_order_once_and_keeps_customer_order(
    monkeypatch,
) -> None:
    selected = ("LX0609-01-01-01", "LX0609-06-01-02", "LX0609-12-01-01")
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="private-institute", patient_id="private-patient", visit_id="private-visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=(SourceObservation.create(
            source_key="first_course_record", query_state=QueryStatus.EMPTY,
            completeness=SourceCompleteness.COMPLETE, record_count=0,
            query_version="snapshot-provider-first_course_record-v1", snapshot_ref=f"sha256:{'a' * 64}",
        ),),
        facts=(), document_refs=(), created_at="2026-07-16T12:00:00+08:00",
    )
    session = Luxian0609EvidenceReadSession(
        snapshot=snapshot,
        materials=Luxian0609EvidenceMaterialStore.create(
            snapshot=snapshot,
            sources={},
        ),
    )
    calls: list[tuple[str, tuple[str, ...]]] = []
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=("LX0609-01-01-01",),
        native_async_rule_ids=("LX0609-06-01-02", "LX0609-12-01-01"),
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(
            ("basic_timeliness", ("LX0609-01-01-01",)),
            ("exam_lab", ("LX0609-06-01-02",)),
            ("course_quality", ("LX0609-12-01-01",)),
        ),
    )

    def _native_result(rule_id: str) -> dict:
        return {
            "rule_id": rule_id,
            "status": "compliant",
            "is_compliant": True,
            "findings": "",
            "evidence": "",
            "suggestion": "",
            "confidence": 1.0,
            "metadata": {
                "execution_source": "lx0609_native",
                "reason_code": "test_result",
            },
        }

    def _sync(name: str):
        def invoke(**kwargs):
            rule_ids = tuple(kwargs["rule_ids"])
            decision_rule_ids = tuple(kwargs.get("decision_rule_ids") or ())
            calls.append((name, rule_ids))
            return NativeExecutionResult(
                results=tuple(
                    _native_result(rule_id)
                    for rule_id in rule_ids
                    if rule_id not in decision_rule_ids
                ),
                planned_rule_ids=rule_ids,
                decisions=tuple(
                    RuleDecision(
                        rule_id=rule_id,
                        snapshot_hash=snapshot.snapshot_hash,
                        applicability=ApplicabilityState.APPLICABLE,
                        evidence_state=EvidenceState.SUFFICIENT,
                        qc_direction=QcDirection.SATISFIED,
                        reason_code="requirement_satisfied",
                        fact_refs=("a" * 64,),
                        evaluator_version="test-ruledecision-v1",
                    )
                    for rule_id in decision_rule_ids
                ),
            )

        return invoke

    async def _exam(**kwargs):
        rule_ids = tuple(kwargs["rule_ids"])
        calls.append(("exam_lab", rule_ids))
        return SimpleNamespace(
            results=tuple(_native_result(rule_id) for rule_id in rule_ids),
            planned_rule_ids=rule_ids,
            llm_call_count=1,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            api_time=0.2,
        )

    async def _course_quality(**kwargs):
        rule_ids = tuple(kwargs["rule_ids"])
        calls.append(("course_quality", rule_ids))
        unexpected_non_typed_decision = RuleDecision(
            # 回归：当前选择范围外的合法 RuleDecision 不得污染 typed 绑定。
            rule_id="LX0609-09-01-01",
            snapshot_hash=snapshot.snapshot_hash,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.SATISFIED,
            reason_code="requirement_satisfied",
            fact_refs=("a" * 64,),
            evaluator_version="test-ruledecision-v1",
        )
        return SimpleNamespace(
            results=(),
            planned_rule_ids=rule_ids,
            decisions=tuple(
                RuleDecision(
                    rule_id=rule_id,
                    snapshot_hash=snapshot.snapshot_hash,
                    applicability=ApplicabilityState.APPLICABLE,
                    evidence_state=EvidenceState.SUFFICIENT,
                    qc_direction=QcDirection.SATISFIED,
                    reason_code="requirement_satisfied",
                    fact_refs=("a" * 64,),
                    evaluator_version="test-ruledecision-v1",
                )
                for rule_id in rule_ids
            ) + (unexpected_non_typed_decision,),
            llm_call_count=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            api_time=0.0,
        )

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: session,
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                rule_id,
                name=rule_id,
                mapped_rule_ids=[f"RAW-{rule_id}"],
                trigger_condition="test",
            )
            for rule_id in selected
        ],
    )
    monkeypatch.setattr(
        luxian_execution,
        "execute_luxian_0609_native_rules",
        _sync("surgery_presence"),
    )
    monkeypatch.setattr(
        luxian_execution,
        "execute_luxian_0609_native_basic_timeliness",
        _sync("basic_timeliness"),
    )
    monkeypatch.setattr(
        luxian_execution,
        "execute_luxian_0609_native_exam_lab_rules",
        _exam,
    )
    monkeypatch.setattr(
        luxian_execution,
        "execute_luxian_0609_native_course_quality_rules",
        _course_quality,
    )

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload={"programmatic_timeline": {}},
        llm_client=object(),
        settings=_all_native_settings(
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
            LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED=True,
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        source_schema="cdm",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    assert calls == [
        ("basic_timeliness", ("LX0609-01-01-01",)),
        ("exam_lab", ("LX0609-06-01-02",)),
        ("course_quality", ("LX0609-12-01-01",)),
    ]
    assert [item["rule_id"] for item in context.native_results] == [
        "LX0609-01-01-01",
        "LX0609-06-01-02",
    ]
    assert [item.rule_id for item in context.reduced_decisions] == ["LX0609-12-01-01"]
    # 族输出逐点校验：范围外的多余决策被丢弃，不再连带范围内已形成的合法结论。
    assert context.reduced_decisions[0].final_state.value == "compliant", context.reduced_decisions[0].reason_code
    assert context.reduced_decisions[0].reason_code == "requirement_satisfied"
    assert context.native_llm_call_count == 1
    assert context.native_total_tokens == 15
    assert [
        item.to_safe_dict() for item in context.native_usage_attributions
    ] == [
        {
            "executor_key": "basic_timeliness",
            "llm_call_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "covered_customer_rule_ids": ["LX0609-01-01-01"],
            "latency_ms": 0.0,
        },
        {
            "executor_key": "exam_lab",
            "llm_call_count": 1,
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "covered_customer_rule_ids": ["LX0609-06-01-02"],
            "latency_ms": 200.0,
        },
        {
            "executor_key": "course_quality",
            "llm_call_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "covered_customer_rule_ids": ["LX0609-12-01-01"],
            "latency_ms": 0.0,
        },
    ]
    assert context.unified_engine_used is True
    assert context.evidence_snapshot is snapshot


@pytest.mark.asyncio
async def test_unified_027_missing_decision_and_projection_fail_closed(
    monkeypatch,
) -> None:
    """027 正式执行缺少决策/投影时必须失败关闭，不能交给聚合器补判。"""
    selected = ("LX0609-08-01-04",)
    snapshot = _safe_evidence_snapshot()
    session = Luxian0609EvidenceReadSession(
        snapshot=snapshot,
        materials=Luxian0609EvidenceMaterialStore.create(
            snapshot=snapshot,
            sources={},
        ),
    )
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=(),
        native_async_rule_ids=selected,
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(("tumor_pathology", selected),),
    )

    async def _missing_decision(**_kwargs):
        return NativeExecutionResult(
            results=(),
            planned_rule_ids=selected,
            decisions=(),
            customer_display_facts=(),
        )

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: session,
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                "LX0609-08-01-04",
                name="出院记录中是否记录肿瘤后续治疗计划",
                mapped_rule_ids=["SC-114"],
                trigger_condition="肿瘤患者出院记录应体现后续治疗计划。",
            )
        ],
    )
    monkeypatch.setattr(
        luxian_execution,
        "execute_luxian_0609_native_tumor_pathology_rules",
        _missing_decision,
    )

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload={"programmatic_timeline": {}},
        llm_client=object(),
        settings=_all_native_settings(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True),
        institute_id="private-institute",
        patient_id="private-patient",
        source_schema="cdm",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    assert [item["rule_id"] for item in context.native_results] == ["LX0609-08-01-04"]
    assert context.native_results[0]["status"] == "technical_error"
    assert context.native_results[0]["is_compliant"] is False
    assert context.native_results[0]["metadata"]["reason_code"] == "family_result_missing"
    assert context.reduced_decisions == ()
    assert context.customer_display_facts == ()

    delivered = luxian_execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []},
        context=context,
        visit_id="private-visit",
        model_name="unused",
        evidence_payload={"programmatic_timeline": {}},
    )
    assert [item["rule_id"] for item in delivered["results"]] == ["LX0609-08-01-04"]
    customer_result = delivered["results"][0]
    assert customer_result["status"] == "technical_error"
    assert customer_result["result_status"] == "technical_error"
    assert customer_result["metadata"]["reason_code"] == "family_result_missing"
    assert not customer_result.get("source_rule_id")
    visible_result = repr(customer_result)
    assert "底层" not in visible_result
    assert "映射规则" not in visible_result


@pytest.mark.parametrize(
    ("migration_case", "rule_id", "expected_owner"),
    (
        ("003-positive-time", "LX0609-04-02-01", "surgery_gate"),
        ("007-critical-context", "LX0609-02-01-03", "course_quality"),
        ("019-safe-evidence", "LX0609-06-02-02", "tumor_pathology"),
        ("019-recorded-specimen", "LX0609-06-02-02", "tumor_pathology"),
        ("019-final-pathology-gap", "LX0609-06-02-02", "tumor_pathology"),
        ("019-source-absent", "LX0609-06-02-02", "tumor_pathology"),
        ("024-current-malignancy", "LX0609-04-02-03", "surgery_gate"),
        ("025-required-facts", "LX0609-04-02-04", "not_executed"),
        ("028-antibiotic-time", "LX0609-05-01-01", "surgery_gate"),
        ("033-source-gap-1", "LX0609-11-01-01", "surgery_gate"),
        ("033-source-gap-2", "LX0609-11-01-01", "surgery_gate"),
        ("033-source-gap-3", "LX0609-11-01-01", "surgery_gate"),
        ("038-anesthesia-source", "LX0609-04-04-03", "surgery_document"),
        ("039-signature-fact", "LX0609-04-01-02", "surgery_document"),
        ("026-chemo-trigger", "LX0609-05-02-01", "tumor_pathology"),
        ("040-level-4-trigger", "LX0609-04-01-03", "surgery_mdt"),
    ),
)
def test_migrated_customer_guard_is_owned_by_native_or_pending_contract(
    migration_case,
    rule_id,
    expected_owner,
) -> None:
    """旧聚合器防误判用例迁移后，正式所有者只能是 Native 或阶段门。"""
    plan = luxian_execution.build_luxian_0609_package_plan_from_settings(
        inventory=load_luxian_0609_dependency_inventory(),
        selected_rule_ids=(rule_id,),
        settings=_all_native_settings(),
    )

    assert migration_case
    assert plan.compatibility_rule_ids == ()
    assert plan.compatibility_execution_rule_ids == ()
    from app.services.luxian_0609.phase_scope import get_luxian_0609_phase_scope
    scope = get_luxian_0609_phase_scope(rule_id)
    assert scope is not None
    if scope.phase_status == "pending_definition":
        assert plan.not_executed_rule_ids == (rule_id,)
        assert plan.native_executor_batches == ()
    else:
        assert plan.not_executed_rule_ids == ()
        assert plan.native_executor_batches == ((expected_owner, (rule_id,)),)


@pytest.mark.asyncio
async def test_rule_007_typed_decision_reaches_customer_renderer_without_legacy_result(
    monkeypatch,
) -> None:
    selected = ("LX0609-02-01-03",)
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=(),
        native_async_rule_ids=selected,
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(("course_quality", selected),),
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: _rule_007_evidence_session(),
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                "LX0609-02-01-03",
                name="LX0609-02-01-03",
                mapped_rule_ids=["LXE-18"],
                trigger_condition="test",
            )
        ],
    )

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload=None,
        llm_client=None,
        settings=_all_native_settings(
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
            LUXIAN_0609_RULE_DECISION_007_ENABLED=True,
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    assert context.native_results == []
    assert [item.rule_id for item in context.reduced_decisions] == ["LX0609-02-01-03"]
    assert context.reduced_decisions[0].final_state.value == "compliant"
    assert context.native_llm_call_count == 0
    assert context.native_total_tokens == 0

    orchestrated = {
        "results": [],
        "total_tokens": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
    }
    luxian_execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated=orchestrated,
        context=context,
        visit_id="private-visit",
        model_name="",
        evidence_payload=None,
    )
    assert [item["rule_id"] for item in orchestrated["results"]] == ["LX0609-02-01-03"]
    assert orchestrated["results"][0]["status"] == "compliant"
    assert orchestrated["results"][0]["metadata"] == {
        "executor_key": "course_quality"
    }
    assert "LXE-18" not in repr(orchestrated["results"])


@pytest.mark.asyncio
async def test_course_008_009_typed_decisions_use_natural_days_and_zero_model(
    monkeypatch,
) -> None:
    selected = ("LX0609-02-01-04", "LX0609-02-01-05")
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=(),
        native_async_rule_ids=selected,
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(("course_quality", selected),),
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    provider_kwargs: dict[str, object] = {}

    def build_session(**kwargs):
        provider_kwargs.update(kwargs)
        return _course_severity_evidence_session()

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        build_session,
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                rule_id,
                name=rule_id,
                mapped_rule_ids=[f"RAW-{rule_id}"],
                trigger_condition="test",
            )
            for rule_id in selected
        ],
    )

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload=None,
        llm_client=None,
        settings=_all_native_settings(
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
            LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED=True,
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        evaluation_as_of_date="2026-01-03",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    assert context.native_results == []
    assert [item.rule_id for item in context.reduced_decisions] == list(selected)
    assert [item.final_state.value for item in context.reduced_decisions] == [
        "compliant",
        "not_applicable",
    ]
    assert all(item.fact_refs for item in context.reduced_decisions)
    assert context.native_llm_call_count == 0
    assert context.native_total_tokens == 0
    assert provider_kwargs["evaluation_as_of_date"] == "2026-01-03"

    orchestrated = {
        "results": [],
        "total_tokens": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
    }
    luxian_execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated=orchestrated,
        context=context,
        visit_id="private-visit",
        model_name="",
        evidence_payload=None,
    )
    assert [item["rule_id"] for item in orchestrated["results"]] == list(selected)
    assert [item["status"] for item in orchestrated["results"]] == [
        "compliant",
        "not_applicable",
    ]
    assert "RAW-LX0609" not in repr(orchestrated["results"])
    assert "2026-01-01" in repr(orchestrated["results"])
    assert "2026-01-03" in repr(orchestrated["results"])


@pytest.mark.asyncio
async def test_basic_timeliness_typed_decisions_share_snapshot_and_skip_legacy_results(
    monkeypatch,
) -> None:
    selected = (
        "LX0609-01-01-01",
        "LX0609-01-02-01",
        "LX0609-09-01-01",
        "LX0609-02-01-01",
        "LX0609-02-01-02",
    )
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=selected,
        native_async_rule_ids=(),
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(("basic_timeliness", selected),),
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: _basic_timeliness_evidence_session(),
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                rule_id,
                name=rule_id,
                mapped_rule_ids=[f"RAW-{rule_id}"],
                trigger_condition="test",
            )
            for rule_id in selected
        ],
    )

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload=None,
        llm_client=None,
        settings=_all_native_settings(
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
            LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED=True,
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    assert context.native_results == []
    assert [item.rule_id for item in context.reduced_decisions] == list(selected)
    assert [item.final_state.value for item in context.reduced_decisions] == [
        "compliant",
        "compliant",
        "not_applicable",
        "compliant",
        "compliant",
    ]
    assert context.reduced_decisions[2].reason_code == "trigger_absent_complete"
    assert all(item.fact_refs for item in context.reduced_decisions)
    assert context.native_llm_call_count == 0
    assert context.native_total_tokens == 0

    orchestrated = {
        "results": [],
        "total_tokens": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
    }
    luxian_execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated=orchestrated,
        context=context,
        visit_id="private-visit",
        model_name="",
        evidence_payload=None,
    )
    assert [item["rule_id"] for item in orchestrated["results"]] == list(selected)
    assert [item["status"] for item in orchestrated["results"]] == [
        "compliant",
        "compliant",
        "not_applicable",
        "compliant",
        "compliant",
    ]
    assert "RAW-LX0609" not in repr(orchestrated["results"])
    assert all("fact_refs" not in item for item in orchestrated["results"])
    receipt = orchestrated["results"][2]["applicability_receipt"]
    assert receipt["fact_refs"] == list(context.reduced_decisions[2].fact_refs)


@pytest.mark.asyncio
async def test_public_entry_keeps_native_result_when_scene_bundles_are_unavailable_but_material_store_is_complete(
    monkeypatch,
) -> None:
    _use_synthetic_legacy_bundle_material(monkeypatch)
    selected = ("LX0609-01-01-01",)
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=selected,
        native_async_rule_ids=(),
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(("basic_timeliness", selected),),
    )
    settings = _all_native_settings(
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED=True,
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: _basic_timeliness_evidence_session(),
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                "LX0609-01-01-01",
                name="入院记录：入院后24小时内是否完成",
                mapped_rule_ids=["RAW-LX0609-01-01-01"],
                trigger_condition="入院记录应在入院后24小时内完成。",
            )
        ],
    )

    result = await SichuanQCService().evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "institute_id": "private-institute",
            "patient_id": "private-patient",
            "visit_id": "private-visit",
            "medical_text": "",
            "structured_context": {},
            "document_hits": {},
            "source_doc_priority": [],
            "data_quality_flags": ["bundle_unavailable"],
            "scene_resolution": {
                "query_scope": "all",
                "record_scene": "unknown",
                "resolved_scene": "",
                "attempted_scenes": ["running", "final"],
                "loaded_scene": "",
                "used_fallback": False,
                "resolution_status": "unavailable",
            },
            "text_available": False,
        },
        rule_ids=list(selected),
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    customer_results = list(result["evaluation_results"])
    assert [item["rule_id"] for item in customer_results] == ["LX0609-01-01-01"]
    assert customer_results[0]["status"] == "compliant"
    assert customer_results[0]["reason_code"] == "requirement_within_threshold"
    assert all(item["status"] != "data_gap" for item in customer_results)
    assert result["token_usage"]["total_tokens"] == 0


@pytest.mark.asyncio
async def test_paused_transfusion_typed_flags_do_not_create_decisions(
    monkeypatch,
) -> None:
    await _assert_current_paused_public_entry(monkeypatch, ("LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02", "LX0609-07-03-01"), settings_overrides={}, documents={})


@pytest.mark.asyncio
async def test_transfusion_rule_decision_flag_off_preserves_raw_result_contract(
    monkeypatch,
) -> None:
    selected = ("LX0609-07-02-01",)
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=(),
        native_async_rule_ids=selected,
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(("transfusion", selected),),
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: _transfusion_044_047_evidence_session(),
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                "LX0609-07-02-01",
                name="LX0609-07-02-01",
                mapped_rule_ids=["RAW-LX0609-07-02-01"],
                trigger_condition="test",
            )
        ],
    )
    course_text = (
        "输血目的：纠正贫血；开始时间14:20，输注红细胞2U，"
        "结束时间16:10。输血过程中严密观察，未见不良反应。"
    )

    _, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "bloodtrans_record": [{"content": course_text}],
                    "daily_course_record": [{"content": "输血后继续观察。"}],
                }
            }
        },
        llm_client=None,
        settings=_all_native_settings(
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
            LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED=False,
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        selected_customer_rule_ids=selected,
    )

    assert [item["rule_id"] for item in context.native_results] == list(selected)
    # 兼容入口的证据投影不携带医嘱身份字段，045 的医嘱触发只能保守判资料不足。
    assert [item["status"] for item in context.native_results] == ["data_gap"]
    assert context.reduced_decisions == ()
    assert context.native_llm_call_count == 0
    assert context.native_total_tokens == 0


def _allow_consultation_023_for_internal_contract(monkeypatch):
    """仅为内部绑定/模型合同开放023；正式准入测试仍使用真实暂停范围。"""
    from app.services.luxian_0609 import native_package, rule_decision_settings
    from app.services.luxian_0609.phase_scope import partition_luxian_0609_rule_scope

    def partition(selected_rule_ids):
        selected = tuple(selected_rule_ids)
        executable, pending = partition_luxian_0609_rule_scope(selected)
        allowed = set(executable) | {"LX0609-03-01-04"}
        return (tuple(rule_id for rule_id in selected if rule_id in allowed),
                tuple(rule_id for rule_id in pending if rule_id != "LX0609-03-01-04"))

    monkeypatch.setattr(native_package, "partition_luxian_0609_rule_scope", partition)
    monkeypatch.setattr(rule_decision_settings, "partition_luxian_0609_rule_scope", partition)


@pytest.mark.asyncio
async def test_consultation_episode_typed_decisions_replace_raw_results(
    monkeypatch,
) -> None:
    _allow_consultation_023_for_internal_contract(monkeypatch)
    # 内部合同仅开放023，保留其他暂停项，检验真实执行器的绑定和替代。
    paused = ("LX0609-03-01-02", "LX0609-03-01-03")
    selected = (*paused, "LX0609-03-01-04")

    def read(**kwargs):
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=[],
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: session,
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                rule_id,
                name=rule_id,
                mapped_rule_ids=[f"RAW-{rule_id}"],
                trigger_condition="test",
            )
            for rule_id in selected
        ],
    )

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload=None,
        llm_client=None,
        settings=_all_native_settings(
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
            LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED=True,
            # 内部合同仍要求执行链接入原生执行。
            LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED=True,
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    # 暂停项只由阶段门控生成 not_executed，不经执行器、不产生判定。
    assert [
        (
            item["rule_id"],
            item["status"],
            item["reason_code"],
            item["metadata"]["execution_source"],
            item["metadata"]["pending_reason_code"],
        )
        for item in context.native_results
    ] == [
        (
            rule_id,
            "not_executed",
            "policy_definition_pending",
            "lx0609_phase_gate",
            "consultation_source_document_unavailable_customer_scope",
        )
        for rule_id in paused
    ]
    assert [item.rule_id for item in context.reduced_decisions] == ["LX0609-03-01-04"]
    assert [item.final_state.value for item in context.reduced_decisions] == [
        "not_applicable",
    ]
    # 无事件保留实际来源观察供审计，不伪造文书或客户证据。
    checked_refs = {item.snapshot_ref.removeprefix("sha256:")
                    for item in context.evidence_snapshot.observations if item.source_key == "consultation_record"}
    assert all(set(item.fact_refs) == checked_refs for item in context.reduced_decisions)
    assert context.native_llm_call_count == 0
    assert context.native_total_tokens == 0


@pytest.mark.asyncio
async def test_consultation_invalid_model_output_survives_prepare_binding_and_aggregate(
    monkeypatch,
) -> None:
    _allow_consultation_023_for_internal_contract(monkeypatch)
    selected = ("LX0609-03-01-01", "LX0609-03-01-04")
    rows_by_source = {
        "consultation_record": [
            {
                "document_id": "consultation-record-001",
                "document_title": "会诊记录",
                "record_time": "2026-07-02 09:00:00",
                "record_content": "申请会诊协助诊治。会诊意见：建议复查血常规。",
            }
        ],
        "inpat_registration": [
            {"admission_datetime": "2026-07-01 08:00:00"},
        ],
        "inpat_registration.discharge_horizon": [
            {"discharge_datetime": "2026-07-03 08:00:00"},
        ],
    }

    def read(**kwargs):
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=rows_by_source.get(kwargs["source_key"], []),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
        created_at="2026-09-05T12:00:00+08:00",
        evaluation_as_of_date="2026-07-05",
        row_reader=read,
        additional_source_keys=("consultation_record",),
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: session,
    )
    class InvalidModelClient:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def generate(self, prompt: str, **_kwargs: object) -> dict[str, str]:
            self.prompts.append(prompt)
            return {"content": "not-json"}

    client = InvalidModelClient()

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload=None,
        llm_client=client,
        settings=_all_native_settings(
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
            LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED=True,
            LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED=True,
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        selected_customer_rule_ids=selected,
        evaluation_as_of_date="2026-07-05",
    )

    assert executable == []
    # 03-01-01 因上游会诊申请单来源缺失而暂停，不得进入执行决策；
    # 测试限定开放的023调用一次固定应答客户端，非法输出按技术失败处理。
    assert [
        (item.rule_id, item.final_state.value, item.reason_code)
        for item in context.reduced_decisions
    ] == [("LX0609-03-01-04", "technical_error", "model_invalid_output")]
    assert len(client.prompts) == 1
    assert context.native_llm_call_count == 1
    orchestrated = luxian_execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []},
        context=context,
        visit_id="private-visit",
        model_name="test-model",
        evidence_payload={},
    )
    paused, consultation_023 = orchestrated["results"]
    assert (paused["rule_id"], paused["status"], paused["reason_code"]) == (
        "LX0609-03-01-01", "not_executed", "policy_definition_pending",
    )
    assert paused["metadata"]["pending_reason_code"] == (
        "consultation_source_document_unavailable_customer_scope"
    )
    assert (
        consultation_023["rule_id"], consultation_023["status"], consultation_023["reason_code"],
    ) == ("LX0609-03-01-04", "technical_error", "model_invalid_output")
    assert all("data_gap_details" not in item for item in orchestrated["results"])
    assert consultation_023["criterion_results"] == []


@pytest.mark.asyncio
async def test_executor_contract_stub_projection_keeps_invalid_display_facts_technical(
    monkeypatch,
) -> None:
    """仅冻结非法展示 facts 的聚合投影；模型合同回归见上一测试。"""

    _allow_consultation_023_for_internal_contract(monkeypatch)
    selected = ("LX0609-03-01-01", "LX0609-03-01-04")

    def read(**kwargs):
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=[],
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
        created_at="2026-09-05T12:00:00+08:00",
        row_reader=read,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: session,
    )

    dispatched_rule_ids: list[tuple[str, ...]] = []

    async def invalid_display_facts(**kwargs):
        snapshot = kwargs["evidence_snapshot"]
        # 与真实执行器一致：只对引擎实际派发的规则产出决策。
        planned = tuple(kwargs["rule_ids"])
        dispatched_rule_ids.append(planned)
        return NativeConsultationEpisodeExecutionResult(
            results=(),
            planned_rule_ids=planned,
            decisions=tuple(
                RuleDecision(
                    rule_id=rule_id,
                    snapshot_hash=snapshot.snapshot_hash,
                    applicability=ApplicabilityState.ERROR,
                    evidence_state=EvidenceState.TECHNICAL_ERROR,
                    qc_direction=QcDirection.UNKNOWN,
                    reason_code="model_invalid_output",
                    fact_refs=(),
                    evaluator_version="test-consultation-stub-v1",
                )
                for rule_id in planned
            ),
            customer_display_facts=tuple(
                (rule_id, {"invalid_model_contract": True})
                for rule_id in planned
            ),
        )

    monkeypatch.setattr(
        luxian_execution,
        "execute_luxian_0609_native_consultation_episode_rules",
        invalid_display_facts,
    )
    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload=None,
        llm_client=None,
        settings=_all_native_settings(
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
            LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED=True,
            LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED=True,
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    orchestrated = luxian_execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []},
        context=context,
        visit_id="private-visit",
        model_name="test-model",
        evidence_payload=None,
    )
    # 暂停的 03-01-01 不派发给执行器；023 的非法展示事实仍按技术失败处理。
    assert dispatched_rule_ids == [("LX0609-03-01-04",)]
    assert [
        (item["rule_id"], item["status"], item["reason_code"])
        for item in orchestrated["results"]
    ] == [
        ("LX0609-03-01-01", "not_executed", "policy_definition_pending"),
        ("LX0609-03-01-04", "technical_error", "model_invalid_output"),
    ]
    assert all("data_gap_details" not in item for item in orchestrated["results"])
    # 客户事实合同非法属于技术失败；不得保留可能由非法事实导出的临床
    # criterion 结构，缺省比伪造一个“空临床结论”更安全。
    assert all("criterion_results" not in item for item in orchestrated["results"])


@pytest.mark.asyncio
async def test_tumor_and_course_admission_typed_flags_reach_unified_reducer(
    monkeypatch,
) -> None:
    selected = (
        "LX0609-06-02-03",
        "LX0609-12-01-01",
        "LX0609-01-01-02",
        "LX0609-06-02-02",
        "LX0609-08-01-04",
    )
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=(),
        native_async_rule_ids=selected,
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(
            ("tumor_pathology", ("LX0609-06-02-03", "LX0609-06-02-02", "LX0609-08-01-04")),
            ("course_quality", ("LX0609-12-01-01", "LX0609-01-01-02")),
        ),
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )

    def read(**kwargs):
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=(),
            truncated=False,
            limit_rows=50,
        )

    def build_session(**kwargs):
        return build_luxian_0609_evidence_read_session(
            **kwargs,
            row_reader=read,
        )

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        build_session,
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                rule_id,
                name=rule_id,
                mapped_rule_ids=[f"RAW-{rule_id}"],
                trigger_condition="test",
            )
            for rule_id in selected
        ],
    )

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload=None,
        llm_client=None,
        settings=_all_native_settings(
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
            LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED=True,
            LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED=True,
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    assert context.native_results == []
    assert [item.rule_id for item in context.reduced_decisions] == list(selected)
    decision_summary = [
        (item.final_state.value, item.reason_code)
        for item in context.reduced_decisions
    ]
    assert decision_summary == [
        ("not_applicable", "trigger_absent_complete"),
        ("not_applicable", "trigger_absent_complete"),
        ("data_gap", "required_field_missing"),
        ("not_applicable", "trigger_absent_complete"),
        ("not_applicable", "trigger_absent_complete"),
    ]
    assert context.native_llm_call_count == 0
    assert context.native_total_tokens == 0


@pytest.mark.asyncio
async def test_lx018_typed_reaches_unified_reducer_when_shared_course_flag_off(
    monkeypatch,
) -> None:
    selected = ("LX0609-01-01-02",)
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=(),
        native_async_rule_ids=selected,
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(("course_quality", selected),),
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )

    def read(**kwargs):
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=(),
            truncated=False,
            limit_rows=50,
        )

    def build_session(**kwargs):
        return build_luxian_0609_evidence_read_session(
            **kwargs,
            row_reader=read,
        )

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        build_session,
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                "LX0609-01-01-02",
                name="LX0609-01-01-02",
                mapped_rule_ids=["RAW-LX0609-01-01-02"],
                trigger_condition="test",
            )
        ],
    )

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload=None,
        llm_client=None,
        settings=_all_native_settings(
            LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
            LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED=False,
        ),
        institute_id="private-institute",
        patient_id="private-patient",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    assert context.native_results == []
    assert [
        (item.rule_id, item.final_state.value, item.reason_code)
        for item in context.reduced_decisions
    ] == [("LX0609-01-01-02", "data_gap", "required_field_missing")]
    assert context.native_llm_call_count == 0
    assert context.native_total_tokens == 0


@pytest.mark.asyncio
async def test_restored_surgery_003_typed_flag_reaches_unified_reducer(
    monkeypatch,
) -> None:
    await _assert_restored_surgery_public_entry(monkeypatch, ("LX0609-04-02-01",), settings_overrides={})


@pytest.mark.asyncio
async def test_unified_engine_infrastructure_failure_never_replays_legacy_chain(
    monkeypatch,
) -> None:
    selected = ("LX0609-01-01-01",)
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=selected,
        native_async_rule_ids=(),
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(
            ("basic_timeliness", selected),
            ("basic_timeliness", selected),
        ),
    )
    legacy_calls = 0

    def legacy_executor(**_kwargs):
        nonlocal legacy_calls
        legacy_calls += 1
        raise AssertionError("统一引擎异常后不得重放旧链")

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: _safe_evidence_session(),
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                "LX0609-01-01-01",
                name="LX0609-01-01-01",
                mapped_rule_ids=["RAW-LX0609-01-01-01"],
                trigger_condition="test",
            )
        ],
    )
    monkeypatch.setattr(
        luxian_execution,
        "execute_luxian_0609_native_basic_timeliness",
        legacy_executor,
    )
    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload={"programmatic_timeline": {}},
        llm_client=object(),
        settings=_all_native_settings(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True),
        institute_id="private-institute",
        patient_id="private-patient",
        source_schema="cdm",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    assert legacy_calls == 0
    assert context.unified_engine_used is True
    assert [item["rule_id"] for item in context.native_results] == ["LX0609-01-01-01"]
    assert context.native_results[0]["status"] == "technical_error"
    assert (
        context.native_results[0]["metadata"]["reason_code"]
        == "unified_engine_infrastructure_failed"
    )


@pytest.mark.asyncio
async def test_unified_engine_snapshot_failure_is_technical_not_silent_legacy_fallback(
    monkeypatch,
) -> None:
    selected = ("LX0609-01-01-01",)
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=selected,
        native_async_rule_ids=(),
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(("basic_timeliness", selected),),
    )
    legacy_calls = 0

    def legacy_executor(**_kwargs):
        nonlocal legacy_calls
        legacy_calls += 1
        raise AssertionError("快照失败后不得静默回放旧链")

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_read_session",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("private failure")),
    )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                "LX0609-01-01-01",
                name="LX0609-01-01-01",
                mapped_rule_ids=["RAW-LX0609-01-01-01"],
                trigger_condition="test",
            )
        ],
    )
    monkeypatch.setattr(
        luxian_execution,
        "execute_luxian_0609_native_basic_timeliness",
        legacy_executor,
    )

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload={"programmatic_timeline": {}},
        llm_client=object(),
        settings=_all_native_settings(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True),
        institute_id="private-institute",
        patient_id="private-patient",
        source_schema="cdm",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    assert legacy_calls == 0
    assert context.unified_engine_used is True
    assert [item["rule_id"] for item in context.native_results] == ["LX0609-01-01-01"]
    assert context.native_results[0]["status"] == "technical_error"
    assert (
        context.native_results[0]["metadata"]["reason_code"]
        == "evidence_snapshot_build_failed"
    )
    assert "private failure" not in repr(context.native_results)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_mode", ["snapshot_build_failed", "snapshot_unavailable", "infrastructure_failed"])
@pytest.mark.parametrize("selection_kind", ["none", "generator", "list"])
async def test_unified_engine_failure_branches_support_none_and_single_use_generator_selection(
    monkeypatch,
    failure_mode: str,
    selection_kind: str,
) -> None:
    selected = ("LX0609-01-01-01", "LX0609-01-02-01")
    batches = (
        (("basic_timeliness", selected), ("basic_timeliness", selected))
        if failure_mode == "infrastructure_failed"
        else (("basic_timeliness", selected),)
    )
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=selected,
        native_sync_rule_ids=selected,
        native_async_rule_ids=(),
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=batches,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    if failure_mode == "infrastructure_failed":
        monkeypatch.setattr(
            luxian_execution,
            "build_luxian_0609_evidence_read_session",
            lambda **_kwargs: _safe_evidence_session(),
        )
    elif failure_mode == "snapshot_build_failed":
        monkeypatch.setattr(
            luxian_execution,
            "build_luxian_0609_evidence_read_session",
            lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("private failure")),
        )
    monkeypatch.setattr(
        luxian_execution,
        "load_luxian_0609_rules",
        lambda: [
            _wrapper(
                rule_id,
                name=rule_id,
                mapped_rule_ids=[f"RAW-{rule_id}"],
                trigger_condition="test",
            )
            for rule_id in selected
        ],
    )
    selection_arg = (
        None
        if selection_kind == "none"
        else ((rule_id for rule_id in selected) if selection_kind == "generator" else list(selected))
    )
    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="" if failure_mode == "snapshot_unavailable" else "private-visit",
        medical_text="",
        evidence_payload={"programmatic_timeline": {}},
        llm_client=object(),
        settings=_all_native_settings(LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True),
        institute_id="private-institute",
        patient_id="private-patient",
        source_schema="cdm",
        selected_customer_rule_ids=selection_arg,
    )

    expected_reason = {
        "snapshot_build_failed": "evidence_snapshot_build_failed",
        "snapshot_unavailable": "unified_engine_snapshot_unavailable",
        "infrastructure_failed": "unified_engine_infrastructure_failed",
    }[failure_mode]
    assert executable == []
    assert context.unified_engine_used is True
    assert [item["rule_id"] for item in context.native_results] == list(selected)
    assert all(item["status"] == "technical_error" for item in context.native_results)
    assert all(
        item["metadata"]["reason_code"] == expected_reason
        for item in context.native_results
    )


@pytest.mark.asyncio
async def test_public_entry_rejects_restored_029_compatibility_before_legacy_lookup(monkeypatch):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    selected = list(published_rule_ids(1, 49))
    captured: dict[str, object] = {}

    async def _prepare(**kwargs):
        captured["prepared_rule_ids"] = [
            str(rule.get("rule_id") or rule.get("rule_code") or "")
            for rule in kwargs["prepared_rules"]
        ]
        captured["selected_customer_rule_ids"] = tuple(
            kwargs["selected_customer_rule_ids"]
        )
        return [], SimpleNamespace(enabled=True)

    def _aggregate(*, orchestrated, **_):
        orchestrated["results"] = [
            {
                "rule_id": rule_id,
                "status": "data_gap",
                "is_compliant": None,
                "findings": "当前资料不足。",
                "evidence": "",
                "suggestion": "请补齐资料后重新质控。",
                "confidence": 1.0,
                "metadata": {"execution_source": "lx0609_native"},
            }
            for rule_id in selected
        ]
        orchestrated["display_rule_ids"] = selected
        orchestrated["display_rule_count"] = len(selected)

    monkeypatch.setattr(
        "app.services.sichuan_qc_service.get_settings",
        lambda: _all_native_settings(),
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.prepare_luxian_0609_execution", _prepare
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.aggregate_luxian_0609_orchestrated_results",
        _aggregate,
    )
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)
    service = SichuanQCService()

    legacy_lookups: list[str] = []

    def _legacy_lookup(rule_id):
        normalized = str(rule_id)
        legacy_lookups.append(normalized)
        if normalized not in {"LX-017", "CL-250", "CL-248", "CL-071", "CL-181", "SC-081"}:
            raise AssertionError(f"全量公共入口加载了未预期的兼容执行规则: {normalized}")
        return {"rule_id": normalized, "rule_name": normalized}

    monkeypatch.setattr(service, "get_rule_by_id", _legacy_lookup)

    with pytest.raises(ValueError, match="LX0609"):
        await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "visit_id": "safe-visit",
            "structured_context": {"documents": {}},
            "text_available": False,
        },
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    assert captured == {}
    assert legacy_lookups == []


@pytest.mark.asyncio
async def test_mainline_master_switch_enables_all_rule_decisions_and_freezes_as_of(
    monkeypatch,
):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    selected = list(published_rule_ids(1, 49))
    captured: dict[str, object] = {}
    base_settings = _all_native_settings(
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_CONSULTATION_EXECUTION_LINK_ENABLED=True,
        **FULL_RULE_DECISION_OVERRIDES,
    )

    async def _prepare(**kwargs):
        settings = kwargs["settings"]
        captured["selected"] = tuple(kwargs["selected_customer_rule_ids"])
        captured["as_of"] = kwargs["evaluation_as_of_date"]
        captured["unified"] = settings.LUXIAN_0609_UNIFIED_ENGINE_ENABLED
        captured["decision_flags"] = tuple(
            getattr(settings, name)
            for name in (
                "LUXIAN_0609_RULE_DECISION_007_ENABLED",
                "LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED",
                "LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED",
                "LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED",
                "LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED",
                "LUXIAN_0609_RULE_DECISION_COURSE_COPY_ENABLED",
                "LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED",
                "LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED",
                "LUXIAN_0609_RULE_DECISION_MDT_040_ENABLED",
                "LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED",
                "LUXIAN_0609_RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED",
                "LUXIAN_0609_RULE_DECISION_EXAM_LAB_ENABLED",
                "LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED",
            )
        )
        return [], SimpleNamespace(enabled=True)

    def _aggregate(*, orchestrated, **_kwargs):
        orchestrated["results"] = [
            {
                "rule_id": rule_id,
                "status": "data_gap",
                "is_compliant": None,
                "metadata": {"execution_source": "lx0609_native"},
            }
            for rule_id in selected
        ]

    monkeypatch.setattr(
        "app.services.sichuan_qc_service.get_settings", lambda: base_settings
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.prepare_luxian_0609_execution", _prepare
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.aggregate_luxian_0609_orchestrated_results",
        _aggregate,
    )
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)
    service = SichuanQCService()
    monkeypatch.setattr(
        service,
        "get_rule_by_id",
        lambda rule_id: (
            {"rule_id": rule_id, "rule_name": rule_id}
            if rule_id in {"LX-017", "CL-250", "CL-248", "CL-071"}
            else (_ for _ in ()).throw(
                AssertionError(f"除020/023兼容映射外不得加载旧规则: {rule_id}")
            )
        ),
    )

    result = await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "visit_id": "safe-visit",
            "structured_context": {"documents": {}},
            "text_available": False,
        },
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        evaluation_as_of_date="2026-07-17",
        use_execution_cache=False,
    )

    assert captured == {
        "selected": tuple(selected),
        "as_of": "2026-07-17",
        "unified": True,
        "decision_flags": (True,) * 13,
    }
    assert [item["rule_id"] for item in result["evaluation_results"]] == selected


@pytest.mark.asyncio
async def test_public_entry_snapshot_sidecar_is_once_internal_and_output_compatible(
    monkeypatch,
) -> None:
    _use_synthetic_legacy_bundle_material(monkeypatch)
    selected = list(published_rule_ids(1, 49))
    snapshot = _safe_evidence_snapshot()
    sidecar_enabled = False
    provider_calls: list[dict] = []
    context_refs: list[tuple[tuple[str, str], ...]] = []
    context_snapshots: list[Luxian0609EvidenceSnapshot | None] = []
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=tuple(selected),
        native_sync_rule_ids=(),
        native_async_rule_ids=(),
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(),
    )

    def _provider(**kwargs):
        provider_calls.append(dict(kwargs))
        return snapshot

    def _aggregate(*, orchestrated, context, **_kwargs):
        context_refs.append(context.evidence_snapshot_rule_refs)
        context_snapshots.append(context.evidence_snapshot)
        orchestrated["results"] = [
            {
                "rule_id": rule_id,
                "status": "data_gap",
                "is_compliant": None,
                "findings": "当前资料不足。",
                "evidence": "",
                "suggestion": "请补齐资料后重新质控。",
                "confidence": 1.0,
                "metadata": {"execution_source": "lx0609_native"},
            }
            for rule_id in selected
        ]
        orchestrated["display_rule_ids"] = selected
        orchestrated["display_rule_count"] = len(selected)

    monkeypatch.setattr(
        "app.services.sichuan_qc_service.get_settings",
        lambda: _all_native_settings(
            LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED=sidecar_enabled
        ),
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_snapshot",
        _provider,
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(luxian_execution, "load_luxian_0609_rules", lambda: [])
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.aggregate_luxian_0609_orchestrated_results",
        _aggregate,
    )
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)
    service = SichuanQCService()

    def _legacy_lookup(rule_id):
        raise AssertionError(f"全原生入口不应加载旧规则: {rule_id}")

    monkeypatch.setattr(service, "get_rule_by_id", _legacy_lookup)
    bundle = {
        "scene": "running",
        "institute_id": "private-institute",
        "patient_id": "private-patient",
        "visit_id": "private-visit",
        "structured_context": {"documents": {}},
        "text_available": False,
    }

    disabled_result = await service.evaluate_running_final_bundle_input(
        bundle=bundle,
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )
    sidecar_enabled = True
    enabled_result = await service.evaluate_running_final_bundle_input(
        bundle=bundle,
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    def _failing_provider(**_kwargs):
        raise RuntimeError("raw SQL Bearer_secret 13800138000")

    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_snapshot",
        _failing_provider,
    )
    failed_sidecar_result = await service.evaluate_running_final_bundle_input(
        bundle=bundle,
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    assert disabled_result == enabled_result == failed_sidecar_result
    # 029/032 需要来源状态防护，即使 sidecar 关闭也会建立仅内部使用的安全快照。
    assert tuple(rule_id for rule_id, _ in context_refs[0]) == tuple(selected)
    assert {snapshot_hash for _, snapshot_hash in context_refs[0]} == {
        snapshot.snapshot_hash
    }
    assert tuple(rule_id for rule_id, _ in context_refs[1]) == tuple(selected)
    assert {snapshot_hash for _, snapshot_hash in context_refs[1]} == {
        snapshot.snapshot_hash
    }
    assert context_refs[2] == ()
    assert context_snapshots == [snapshot, snapshot, None]
    assert len(provider_calls) == 2
    assert all(
        tuple(call["selected_rule_ids"]) == tuple(selected)
        for call in provider_calls
    )
    assert snapshot.snapshot_hash not in repr(enabled_result)
    assert "evidence_snapshot" not in repr(enabled_result)
    assert "Bearer_secret" not in repr(failed_sidecar_result)
    assert "13800138000" not in repr(failed_sidecar_result)


@pytest.mark.asyncio
async def test_snapshot_sidecar_requires_three_coordinates_before_provider(
    monkeypatch,
) -> None:
    package_plan = Luxian0609PackagePlan(
        selected_rule_ids=("LX0609-01-01-01",),
        native_sync_rule_ids=(),
        native_async_rule_ids=(),
        compatibility_rule_ids=(),
        compatibility_execution_rule_ids=(),
        bypassed_execution_rule_ids=(),
        native_executor_batches=(),
    )
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_package_plan_from_settings",
        lambda **_kwargs: package_plan,
    )
    monkeypatch.setattr(luxian_execution, "load_luxian_0609_rules", lambda: [])
    monkeypatch.setattr(
        luxian_execution,
        "build_luxian_0609_evidence_snapshot",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("缺少三坐标时不得读取provider")
        ),
    )

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="private-visit",
        medical_text="",
        evidence_payload={},
        llm_client=object(),
        settings=_all_native_settings(
            LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED=True
        ),
        institute_id="",
        patient_id="private-patient",
        selected_customer_rule_ids=("LX0609-01-01-01",),
    )

    assert executable == []
    assert context.evidence_snapshot is None
    assert context.evidence_snapshot_rule_refs == ()


@pytest.mark.asyncio
async def test_public_entry_rejects_disabled_family_before_legacy_lookup(monkeypatch):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    selected = ["LX0609-01-01-01", "LX0609-12-01-01"]
    lookups: list[str] = []
    captured: dict[str, object] = {}

    async def _prepare(**kwargs):
        captured["prepared_rule_ids"] = [
            str(rule.get("rule_id") or rule.get("rule_code") or "")
            for rule in kwargs["prepared_rules"]
        ]
        return [], SimpleNamespace(enabled=True)

    def _aggregate(*, orchestrated, **_):
        orchestrated["results"] = []
        orchestrated["display_rule_ids"] = selected
        orchestrated["display_rule_count"] = 0

    monkeypatch.setattr(
        "app.services.sichuan_qc_service.get_settings",
        lambda: _all_native_settings(LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED=False),
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.prepare_luxian_0609_execution", _prepare
    )
    monkeypatch.setattr(
        "app.services.sichuan_qc_service.aggregate_luxian_0609_orchestrated_results",
        _aggregate,
    )
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)
    service = SichuanQCService()

    def _legacy_lookup(rule_id):
        lookups.append(str(rule_id))
        return {"rule_id": str(rule_id), "rule_name": str(rule_id)}

    monkeypatch.setattr(service, "get_rule_by_id", _legacy_lookup)
    monkeypatch.setattr(
        service,
        "_evaluate_rules_orchestrated",
        lambda **_: _async_value(
            {
                "results": [],
                "total_tokens": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_api_time": 0.0,
            }
        ),
    )

    with pytest.raises(ValueError, match="LX0609"):
        await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "visit_id": "safe-visit",
            "structured_context": {"documents": {}},
            "text_available": False,
        },
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    assert lookups == []
    assert captured == {}


@pytest.mark.asyncio
async def test_public_entry_customer_package_off_keeps_full_legacy_rollback(monkeypatch):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    lookups: list[str] = []
    dispatched: list[list[str]] = []

    monkeypatch.setattr(
        "app.services.sichuan_qc_service.get_settings",
        lambda: _all_native_settings(
            LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=False
        ),
    )
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)
    service = SichuanQCService()

    def _legacy_lookup(rule_id):
        lookups.append(str(rule_id))
        return {"rule_id": str(rule_id), "rule_name": str(rule_id)}

    async def _dispatch(**kwargs):
        dispatched.append([str(rule.get("rule_id")) for rule in kwargs["rules"]])
        return {
            "results": [],
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_api_time": 0.0,
        }

    monkeypatch.setattr(service, "get_rule_by_id", _legacy_lookup)
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _dispatch)

    await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "visit_id": "safe-visit",
            "structured_context": {"documents": {}},
            "text_available": False,
        },
        rule_ids=["LX0609-01-01-01", "LX0609-04-01-03"],
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    assert lookups == ["SC-002", "SC-083", "CL-108"]
    assert dispatched == [lookups]


@pytest.mark.asyncio
async def test_paused_040_flag_off_does_not_restore_legacy_rules(monkeypatch):
    await _assert_current_paused_public_entry(monkeypatch, ("LX0609-04-01-03",), settings_overrides={"LUXIAN_0609_NATIVE_MDT_040_ENABLED": False}, documents={})


@pytest.mark.asyncio
async def test_restored_029_dispatch_keeps_other_paused_surgery_rules_out(monkeypatch):
    await _assert_restored_surgery_public_entry(monkeypatch, ("LX0609-04-01-01", "LX0609-04-02-02", "LX0609-04-03-01"), settings_overrides={})


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
async def test_paused_consultation_public_entry_never_dispatches_for_either_flag_state(
    monkeypatch, enabled,
):
    await _assert_current_paused_public_entry(
        monkeypatch,
        ("LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03", "LX0609-03-01-04"),
        settings_overrides={"LUXIAN_0609_NATIVE_CONSULTATION_ENABLED": enabled},
        documents={},
    )


@pytest.mark.asyncio
async def test_native_exam_lab_public_entry_bypasses_four_legacy_rules_and_keeps_order(monkeypatch):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    selected = ["LX0609-06-01-02", "LX0609-06-01-04", "LX0609-06-01-05", "LX0609-06-03-03", "LX0609-06-03-04"]
    mappings = {
        "LX0609-06-01-02": ["LXE-23"],
        "LX0609-06-01-04": ["LXE-23", "SC-114"],
        "LX0609-06-01-05": ["LXE-23"],
        "LX0609-06-03-03": ["LXE-24"],
        "LX0609-06-03-04": ["LXE-24", "LX-031"],
    }
    wrappers = []
    for rule_id in selected:
        wrapper = _wrapper(
            rule_id,
            name=rule_id,
            mapped_rule_ids=mappings[rule_id],
            trigger_condition="明确检查检验事实",
        )
        wrapper["custom_prompt"] = (
            f"规则ID: {rule_id}\n病历文本：{{medical_text}}\n"
            '只输出JSON：{"is_compliant": true}'
        )
        wrappers.append(wrapper)

    settings = SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=False,
    )
    dispatched: list[list[str]] = []

    class _Client:
        def __init__(self):
            self.prompts: list[str] = []

        async def generate(self, prompt: str):
            self.prompts.append(prompt)
            return {
                "choices": [{"message": {"content": '{"is_compliant": true}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
            }

    async def _dispatch(**kwargs):
        dispatched.append([str(rule.get("rule_id")) for rule in kwargs["rules"]])
        raise AssertionError("原生检查检验族不应派发旧规则")

    monkeypatch.setattr("app.services.sichuan_qc_service.get_settings", lambda: settings)
    monkeypatch.setattr(luxian_execution, "load_luxian_0609_rules", lambda: wrappers)
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)
    service = SichuanQCService()
    client = _Client()
    service.adjudicator_client = client
    monkeypatch.setattr(
        service,
        "get_rule_by_id",
        lambda rule_id: {"rule_id": rule_id, "rule_name": rule_id},
    )
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _dispatch)

    result = await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "visit_id": "safe-visit",
            "timeline_facts": [
                {
                    "fact_type": "current_visit_ct_mri_exam",
                    "state": "present",
                    "source_key": "exam_master",
                    "current_visit_bound": True,
                },
                {
                    "fact_type": "current_visit_culture_or_ast",
                    "state": "present",
                    "source_key": "labtest_master",
                    "current_visit_bound": True,
                },
            ],
            "structured_context": {
                "documents": {
                    "exam_master": [{"content": "头颅MRI检查报告"}],
                    "labtest_master": [{"content": "血培养检出细菌并完成药敏试验"}],
                }
            },
            "text_available": False,
        },
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    assert dispatched == []
    assert len(client.prompts) == 5
    assert [item["rule_id"] for item in result["evaluation_results"]] == selected
    assert result["token_usage"] == {
        "total_tokens": 55,
        "prompt_tokens": 50,
        "completion_tokens": 5,
    }
    assert result["executor_breakdown"]["llm"] == 5
    assert all(raw_id not in repr(result["evaluation_results"]) for raw_id in ("LXE-23", "SC-114", "LXE-24", "LX-031"))


@pytest.mark.asyncio
async def test_native_exam_lab_flag_off_rejects_legacy_dispatch(monkeypatch):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    selected = ["LX0609-06-01-02", "LX0609-06-01-04", "LX0609-06-01-05", "LX0609-06-03-03", "LX0609-06-03-04"]
    mappings = {
        "LX0609-06-01-02": ["LXE-23"],
        "LX0609-06-01-04": ["LXE-23", "SC-114"],
        "LX0609-06-01-05": ["LXE-23"],
        "LX0609-06-03-03": ["LXE-24"],
        "LX0609-06-03-04": ["LXE-24", "LX-031"],
    }
    wrappers = [
        _wrapper(rule_id, name=rule_id, mapped_rule_ids=mappings[rule_id], trigger_condition="test")
        for rule_id in selected
    ]
    settings = SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=False,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=False,
    )
    dispatched: list[list[str]] = []

    async def _dispatch(**kwargs):
        raw_ids = [str(rule.get("rule_id")) for rule in kwargs["rules"]]
        dispatched.append(raw_ids)
        return {
            "results": [],
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_api_time": 0.0,
        }

    monkeypatch.setattr("app.services.sichuan_qc_service.get_settings", lambda: settings)
    monkeypatch.setattr(luxian_execution, "load_luxian_0609_rules", lambda: wrappers)
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)
    service = SichuanQCService()
    monkeypatch.setattr(
        service,
        "get_rule_by_id",
        lambda rule_id: {"rule_id": rule_id, "rule_name": rule_id},
    )
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _dispatch)

    with pytest.raises(ValueError, match="LX0609"):
        await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "visit_id": "safe-visit",
            "structured_context": {"documents": {}},
            "text_available": False,
        },
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    assert dispatched == []


@pytest.mark.asyncio
async def test_paused_transfusion_public_entry_keeps_customer_order_without_dispatch(monkeypatch):
    await _assert_current_paused_public_entry(monkeypatch, published_rule_ids(41, 49), settings_overrides={}, documents={})


@pytest.mark.asyncio
async def test_paused_transfusion_flag_off_does_not_dispatch_legacy(monkeypatch):
    await _assert_current_paused_public_entry(monkeypatch, published_rule_ids(41, 49), settings_overrides={"LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED": False}, documents={})


@pytest.mark.asyncio
async def test_native_tumor_pathology_public_entry_bypasses_legacy_rules_and_keeps_order(
    monkeypatch,
):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    selected = ["LX0609-06-02-03", "LX0609-06-02-02", "LX0609-05-02-01", "LX0609-08-01-04"]
    mappings = {
        "LX0609-06-02-03": ["SC-037", "SC-099", "SC-114"],
        "LX0609-06-02-02": ["SC-037", "SC-099"],
        "LX0609-05-02-01": ["SC-034", "SC-146"],
        "LX0609-08-01-04": ["SC-116", "SC-124"],
    }
    wrappers = []
    for rule_id in selected:
        wrapper = _wrapper(
            rule_id,
            name=rule_id,
            mapped_rule_ids=mappings[rule_id],
            trigger_condition="受控肿瘤病理事实",
        )
        wrapper["custom_prompt"] = (
            f"规则ID: {rule_id}\n主执行规则: SHOULD_NOT_LEAK\n"
            "病历文本：{medical_text}\n"
            '只输出JSON：{"is_compliant": true}'
        )
        wrappers.append(wrapper)
    settings = SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED=True,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=False,
    )
    dispatched: list[list[str]] = []

    class _Client:
        def __init__(self):
            self.prompts: list[str] = []

        async def generate(self, prompt: str):
            self.prompts.append(prompt)
            return {
                "choices": [{"message": {"content": '{"is_compliant": true}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            }

    async def _dispatch(**kwargs):
        dispatched.append([str(rule.get("rule_id")) for rule in kwargs["rules"]])
        raise AssertionError("原生肿瘤病理族不应派发旧规则")

    marker = "SAFE_TUMOR_BODY_MARKER"
    documents = {
        "pathology_exam_master": [{"content": "病理送检申请资料。"}],
        "pathology_exam_report": [
            {
                "diagnosis": "病理诊断资料。",
                "content": "病理诊断明确，完整病理结果资料已经形成。",
                "report_datetime": "2026-04-26 10:00:00",
                "record_time": "2026-04-26 10:00:00",
            }
        ],
        "surgery_record": [{"content": "手术记录中包含本次手术经过。"}],
        "daily_course_record": [{"content": f"病程记录中已记录病理结果。{marker}"}],
        "inpat_drug_order": [{"content": "受控化疗医嘱资料。"}],
        "discharge_record": [{"content": "出院后肿瘤治疗计划。"}],
    }
    monkeypatch.setattr(
        "app.services.luxian_0609.native_tumor_pathology_execution.read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: ([{"diagnosis_code": "C18.9"}] if source_key == "diagnosis" else []),
    )
    monkeypatch.setattr("app.services.sichuan_qc_service.get_settings", lambda: settings)
    monkeypatch.setattr(luxian_execution, "load_luxian_0609_rules", lambda: wrappers)
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)
    service = SichuanQCService()
    client = _Client()
    service.adjudicator_client = client
    monkeypatch.setattr(
        service,
        "get_rule_by_id",
        lambda rule_id: {"rule_id": rule_id, "rule_name": rule_id},
    )
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _dispatch)

    result = await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "institute_id": "safe-institute",
            "patient_id": "safe-patient",
            "visit_id": "safe-visit",
            "structured_context": {"documents": documents},
            "timeline_facts": [
                {
                    "fact_type": "current_visit_chemotherapy_order",
                    "state": "present",
                    "source_key": "inpat_drug_order",
                    "current_visit_bound": True,
                }
            ],
            "text_available": False,
        },
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    assert dispatched == []
    assert len(client.prompts) == 3, [
        (item.get("rule_id"), item.get("status"), (item.get("metadata") or {}).get("reason_code"))
        for item in result["evaluation_results"]
    ]
    assert [item["rule_id"] for item in result["evaluation_results"]] == selected
    assert [item["status"] for item in result["evaluation_results"]] == ["compliant"] * 4
    assert result["token_usage"]["total_tokens"] == 330
    assert all(raw_id not in repr(result["evaluation_results"]) for ids in mappings.values() for raw_id in ids)
    assert marker not in repr(result)


@pytest.mark.asyncio
async def test_native_tumor_pathology_flag_off_rejects_legacy_dispatch(monkeypatch):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    selected = ["LX0609-06-02-03", "LX0609-06-02-02", "LX0609-05-02-01", "LX0609-08-01-04"]
    mappings = {
        "LX0609-06-02-03": ["SC-037", "SC-099", "SC-114"],
        "LX0609-06-02-02": ["SC-037", "SC-099"],
        "LX0609-05-02-01": ["SC-034", "SC-146"],
        "LX0609-08-01-04": ["SC-116", "SC-124"],
    }
    wrappers = [
        _wrapper(
            rule_id,
            name=rule_id,
            mapped_rule_ids=mappings[rule_id],
            trigger_condition="test",
        )
        for rule_id in selected
    ]
    settings = SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED=False,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=False,
    )
    dispatched: list[list[str]] = []

    async def _dispatch(**kwargs):
        dispatched.append([str(rule.get("rule_id")) for rule in kwargs["rules"]])
        return {
            "results": [],
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_api_time": 0.0,
        }

    monkeypatch.setattr("app.services.sichuan_qc_service.get_settings", lambda: settings)
    monkeypatch.setattr(luxian_execution, "load_luxian_0609_rules", lambda: wrappers)
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)
    service = SichuanQCService()
    monkeypatch.setattr(
        service,
        "get_rule_by_id",
        lambda rule_id: {"rule_id": rule_id, "rule_name": rule_id},
    )
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _dispatch)

    with pytest.raises(ValueError, match="LX0609"):
        await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "visit_id": "safe-visit",
            "structured_context": {"documents": {}},
            "text_available": False,
        },
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    assert dispatched == []


@pytest.mark.asyncio
async def test_remaining_native_families_bypass_all_legacy_rules_and_keep_customer_order(
    monkeypatch,
):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    selected = [
        "LX0609-04-02-01", "LX0609-02-01-03", "LX0609-02-01-04", "LX0609-02-01-05", "LX0609-12-01-01",
        "LX0609-12-01-02", "LX0609-01-01-02", "LX0609-04-02-03", "LX0609-04-02-04", "LX0609-05-01-01",
        "LX0609-04-02-05", "LX0609-11-01-01", "LX0609-11-02-01", "LX0609-11-02-02", "LX0609-04-04-01",
        "LX0609-04-04-02", "LX0609-04-04-03", "LX0609-04-01-02",
    ]
    mappings = {
        "LX0609-04-02-01": ["LX-026", "SC-096"], "LX0609-02-01-03": ["LXE-18"],
        "LX0609-02-01-04": ["SC-051", "CL-231"], "LX0609-02-01-05": ["SC-051", "CL-231"],
        "LX0609-12-01-01": ["CL-273"], "LX0609-12-01-02": ["CL-275", "LXE-21"],
        "LX0609-01-01-02": ["SC-008", "LX-001", "CL-068"], "LX0609-04-02-03": ["SC-099"],
        "LX0609-04-02-04": ["SC-100", "SC-101"], "LX0609-05-01-01": ["SC-044", "LX-012"],
        "LX0609-04-02-05": ["LX-027", "CL-173", "SC-098"], "LX0609-11-01-01": ["SC-087", "LXE-31"],
        "LX0609-11-02-01": ["LX-022", "SC-090"], "LX0609-11-02-02": ["SC-090", "LX-022"],
        "LX0609-04-04-01": ["LX-020"], "LX0609-04-04-02": ["LX-020", "SC-090"],
        "LX0609-04-04-03": ["SC-090"], "LX0609-04-01-02": ["LX-019", "SC-082"],
    }
    wrappers = [
        _wrapper(rule_id, name=rule_id, mapped_rule_ids=mappings[rule_id], trigger_condition="native-test")
        for rule_id in selected
    ]
    settings = SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED=True,
        LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED=True,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=False,
    )
    calls: list[tuple[str, tuple[str, ...]]] = []
    dispatched: list[list[str]] = []

    def _result(rule_id: str) -> dict:
        return {
            "rule_id": rule_id, "status": "data_gap", "is_compliant": None,
            "findings": "当前资料不足。", "evidence": "",
            "suggestion": "请补齐资料后重新质控。", "confidence": 1.0,
            "metadata": {
                "execution_source": "lx0609_native",
                "aggregation_source": "native_programmatic",
                "reason_code": "test_data_gap",
            },
        }

    async def _execute(executor_key: str, **kwargs):
        rule_ids = tuple(kwargs["rule_ids"])
        calls.append((executor_key, rule_ids))
        return SimpleNamespace(
            results=tuple(_result(rule_id) for rule_id in rule_ids),
            planned_rule_ids=rule_ids,
            decisions=(),
            customer_display_facts=(),
            llm_call_count=0, prompt_tokens=0, completion_tokens=0,
            total_tokens=0, api_time=0.0,
        )

    async def _dispatch(**kwargs):
        dispatched.append([str(rule.get("rule_id")) for rule in kwargs["rules"]])
        raise AssertionError("剩余原生规则族不应派发旧规则")

    monkeypatch.setattr("app.services.sichuan_qc_service.get_settings", lambda: settings)
    monkeypatch.setattr(luxian_execution, "load_luxian_0609_rules", lambda: wrappers)
    monkeypatch.setattr(
        luxian_execution, "execute_luxian_0609_native_course_quality_rules",
        lambda **kwargs: _execute("course_quality", **kwargs),
    )
    monkeypatch.setattr(
        luxian_execution, "execute_luxian_0609_native_surgery_gate_rules",
        lambda **kwargs: _execute("surgery_gate", **kwargs),
    )
    monkeypatch.setattr(
        luxian_execution, "execute_luxian_0609_native_surgery_document_rules",
        lambda **kwargs: _execute("surgery_document", **kwargs),
    )
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)
    service = SichuanQCService()
    monkeypatch.setattr(service, "get_rule_by_id", lambda rule_id: {"rule_id": rule_id})
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _dispatch)

    result = await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running", "visit_id": "safe-visit",
            "structured_context": {"documents": {}}, "timeline_facts": [],
            "text_available": False,
        },
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    # 暂停规则（含来源缺失而暂停的麻醉访视 04-04-01/04-04-02）不得进入任何执行批次。
    from app.services.luxian_0609.phase_scope import get_luxian_0609_phase_scope
    paused = {rule_id for rule_id in selected if get_luxian_0609_phase_scope(rule_id).phase_status == "pending_definition"}
    assert paused.isdisjoint(rule_id for _key, batch in calls for rule_id in batch)
    assert dispatched == []
    assert calls == [
        ("course_quality", ("LX0609-02-01-03", "LX0609-02-01-04", "LX0609-02-01-05", "LX0609-12-01-01", "LX0609-12-01-02", "LX0609-01-01-02")),
        ("surgery_gate", ("LX0609-04-02-01",)),
    ]
    assert [item["rule_id"] for item in result["evaluation_results"]] == selected
    assert [
        item["status"] for item in result["evaluation_results"]
        if item["rule_id"] in paused
    ] == ["not_executed"] * len(paused)
    anesthesia = next(
        item for item in result["evaluation_results"] if item["rule_id"] == "LX0609-04-04-01"
    )
    assert anesthesia["metadata"]["pending_reason_code"] == (
        "anesthesia_visit_sources_unavailable_customer_scope"
    )
    assert [
        item["status"] for item in result["evaluation_results"]
        if item["rule_id"] not in paused
    ] == ["data_gap"] * (len(selected) - len(paused))
    assert result["token_usage"]["total_tokens"] == 0
    legacy_ids = {
        raw_id
        for rule_id, values in mappings.items()
        if rule_id not in paused
        for raw_id in values
    }
    # 暂停项按现有合同在 metadata 中保留映射追溯；04-04-01 与启用的 04-04-02
    # 共用 LX-020，因此旧结果隔离只对实际执行的规则断言。
    active_results = [
        item for item in result["evaluation_results"] if item["rule_id"] not in paused
    ]
    assert all(raw_id not in repr(active_results) for raw_id in legacy_ids)


@pytest.mark.asyncio
async def test_remaining_native_family_flags_off_reject_legacy_dispatch(monkeypatch):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    selected = [
        "LX0609-04-02-01", "LX0609-02-01-03", "LX0609-02-01-04", "LX0609-02-01-05", "LX0609-12-01-01",
        "LX0609-12-01-02", "LX0609-01-01-02", "LX0609-04-02-03", "LX0609-04-02-04", "LX0609-05-01-01",
        "LX0609-04-02-05", "LX0609-11-01-01", "LX0609-11-02-01", "LX0609-11-02-02", "LX0609-04-04-01",
        "LX0609-04-04-02", "LX0609-04-04-03", "LX0609-04-01-02",
    ]
    mappings = {
        "LX0609-04-02-01": ["LX-026", "SC-096"], "LX0609-02-01-03": ["LXE-18"],
        "LX0609-02-01-04": ["SC-051", "CL-231"], "LX0609-02-01-05": ["SC-051", "CL-231"],
        "LX0609-12-01-01": ["CL-273"], "LX0609-12-01-02": ["CL-275", "LXE-21"],
        "LX0609-01-01-02": ["SC-008", "LX-001", "CL-068"], "LX0609-04-02-03": ["SC-099"],
        "LX0609-04-02-04": ["SC-100", "SC-101"], "LX0609-05-01-01": ["SC-044", "LX-012"],
        "LX0609-04-02-05": ["LX-027", "CL-173", "SC-098"], "LX0609-11-01-01": ["SC-087", "LXE-31"],
        "LX0609-11-02-01": ["LX-022", "SC-090"], "LX0609-11-02-02": ["SC-090", "LX-022"],
        "LX0609-04-04-01": ["LX-020"], "LX0609-04-04-02": ["LX-020", "SC-090"],
        "LX0609-04-04-03": ["SC-090"], "LX0609-04-01-02": ["LX-019", "SC-082"],
    }
    wrappers = [
        _wrapper(rule_id, name=rule_id, mapped_rule_ids=mappings[rule_id], trigger_condition="test")
        for rule_id in selected
    ]
    settings = SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED=True,
        LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED=False,
        LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED=False,
        LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED=False,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=False,
    )
    dispatched: list[list[str]] = []

    async def _dispatch(**kwargs):
        dispatched.append([str(rule.get("rule_id")) for rule in kwargs["rules"]])
        return {
            "results": [], "total_tokens": 0, "total_prompt_tokens": 0,
            "total_completion_tokens": 0, "total_api_time": 0.0,
        }

    monkeypatch.setattr("app.services.sichuan_qc_service.get_settings", lambda: settings)
    monkeypatch.setattr(luxian_execution, "load_luxian_0609_rules", lambda: wrappers)
    monkeypatch.setattr("app.services.sample_programmatic_evidence.engine", None)
    service = SichuanQCService()
    monkeypatch.setattr(service, "get_rule_by_id", lambda rule_id: {"rule_id": rule_id})
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _dispatch)

    with pytest.raises(ValueError, match="LX0609"):
        await service.evaluate_running_final_bundle_input(
        bundle={"scene": "running", "visit_id": "safe-visit", "structured_context": {"documents": {}}},
        rule_ids=selected,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    assert dispatched == []


@pytest.mark.asyncio
async def test_public_bundle_entry_rejects_customer_id_when_its_family_is_not_native(monkeypatch):
    """正式客户入口不得因关闭规则族而转入共享旧规则。"""
    _use_synthetic_legacy_bundle_material(monkeypatch)

    settings = SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=False,
    )
    looked_up: list[str] = []
    dispatched: list[list[str]] = []

    def _get_rule(rule_id: str):
        looked_up.append(rule_id)
        return {
            "rule_id": rule_id,
            "rule_name": rule_id,
            "applicable_documents": ["daily_course_record"],
        }

    async def _dispatch(**kwargs):
        raw_ids = [str(rule.get("rule_id")) for rule in kwargs["rules"]]
        dispatched.append(raw_ids)
        return {
            "results": [
                {
                    "rule_id": rule_id,
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "未发现该项缺失。",
                    "evidence": "",
                    "suggestion": "",
                    "confidence": 1.0,
                    "metadata": {},
                }
                for rule_id in raw_ids
            ],
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_api_time": 0.0,
        }

    monkeypatch.setattr("app.services.sichuan_qc_service.get_settings", lambda: settings)
    service = SichuanQCService()
    monkeypatch.setattr(service, "get_rule_by_id", _get_rule)
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _dispatch)

    with pytest.raises(ValueError, match="LX0609"):
        await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "institute_id": "safe-inst",
            "patient_id": "safe-patient",
            "visit_id": "safe-visit",
            "structured_context": {"documents": {}},
            "text_available": False,
        },
        rule_ids=["LX0609-06-02-03"],
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        use_execution_cache=False,
    )

    assert looked_up == []
    assert dispatched == []


@pytest.mark.asyncio
async def test_restored_surgery_flag_off_rejects_before_native_or_legacy(monkeypatch):
    await _assert_restored_surgery_public_entry(monkeypatch, ("LX0609-04-01-01",), settings_overrides={"LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED": False})


@pytest.mark.asyncio
async def test_evaluate_document_forwards_native_source_coordinates(monkeypatch):
    captured = {}
    service = SichuanQCService()

    async def _resolve_rules(**_):
        return []

    async def _evaluate_with_rules(**kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(service, "_resolve_rules_for_document", _resolve_rules)
    monkeypatch.setattr(service, "evaluate_document_with_rules", _evaluate_with_rules)

    await service.evaluate_document(
        document_id="record-native-fallback",
        content="",
        rule_ids=[],
        source_institute_id="i",
        source_patient_id="p",
        source_visit_id="visit-native-fallback",
        source_schema="cdm",
    )

    assert (
        captured["source_institute_id"],
        captured["source_patient_id"],
        captured["source_visit_id"],
        captured["source_schema"],
    ) == ("i", "p", "visit-native-fallback", "cdm")


@pytest.mark.asyncio
async def test_restored_029_without_triple_flags_rejects_legacy_fallback(monkeypatch):
    await _assert_restored_surgery_public_entry(monkeypatch, ("LX0609-04-01-01",), settings_overrides={"LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED": False})


@pytest.mark.asyncio
async def test_restored_029_disabled_with_paused_consent_rejects_legacy_partition(monkeypatch):
    await _assert_restored_surgery_public_entry(monkeypatch, ("LX0609-04-01-01", "LX0609-11-01-01"), settings_overrides={"LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED": False})


@pytest.mark.asyncio
async def test_generic_gate_never_receives_restored_native_or_paused_wrappers(monkeypatch):
    await _assert_restored_surgery_public_entry(monkeypatch, ("LX0609-04-01-01", "LX0609-11-01-01"), settings_overrides={})


@pytest.mark.asyncio
async def test_paused_033_skips_live_performed_source_before_dispatch(monkeypatch):
    await _assert_current_paused_public_entry(monkeypatch, ("LX0609-11-01-01",), settings_overrides={}, documents={"first_course_record": [{"content": "本次手术相关病程。"}]})


@pytest.mark.asyncio
async def test_paused_033_keeps_customer_scope_without_live_guard(monkeypatch):
    await _assert_current_paused_public_entry(monkeypatch, ("LX0609-11-01-01",), settings_overrides={}, documents={})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reader_mode,expected_status,expected_source_state",
    [
        ("zero_rows", "not_applicable", "zero_rows"),
        ("nonexact_rows", "data_gap", "nonexact_rows"),
        ("unavailable", "data_gap", "unavailable"),
        ("error", "data_gap", "error"),
    ],
)
async def test_paused_033_cannot_be_overridden_by_reader_outcome(
    monkeypatch, reader_mode, expected_status, expected_source_state
):
    await _assert_current_paused_public_entry(monkeypatch, ("LX0609-11-01-01",), settings_overrides={}, documents={"first_course_record": [{"content": reader_mode}]})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule_set_key,rule_ids,trigger_enabled",
    [
        (LUXIAN_0609_RULE_SET_KEY, ["SC-087", "LXE-31"], False),
        ("other_rule_set", ["SC-087", "LXE-31"], True),
        (LUXIAN_0609_RULE_SET_KEY, ["SC-099"], True),
    ],
)
async def test_lx0609_033_live_reader_is_off_for_disabled_non_package_or_unselected_scope(
    monkeypatch, rule_set_key, rule_ids, trigger_enabled
):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    wrappers = [
        _wrapper(
            "LX0609-11-01-01",
            name="手术知情同意书：无手术知情同意书",
            mapped_rule_ids=["SC-087", "LXE-31"],
            trigger_condition="手术患者应有手术知情同意书。",
        ),
        _wrapper(
            "LX0609-04-02-03",
            name="恶性肿瘤手术记录",
            mapped_rule_ids=["SC-099"],
            trigger_condition="仅用于范围隔离。",
        ),
    ]
    settings = SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=trigger_enabled,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
    )
    reader_calls = []

    def _reader(**kwargs):
        reader_calls.append(dict(kwargs))
        raise AssertionError("未选 033 或 package/gate 关闭时不得查询来源")

    async def _generic_gate(**kwargs):
        return evaluate_luxian_0609_trigger_gates(
            rules=kwargs["rules"],
            visit_id=kwargs["visit_id"],
            medical_text=kwargs["medical_text"],
            evidence_payload=kwargs["evidence_payload"],
        )

    async def _unexpected_model_dispatch(**kwargs):
        raise AssertionError("本测试的缺文书路径不应分派模型")

    monkeypatch.setattr(
        "app.services.luxian_0609.source_evidence_reader.read_luxian_0609_runtime_source_rows", _reader
    )
    monkeypatch.setattr("app.services.sichuan_qc_service.get_settings", lambda: settings)
    monkeypatch.setattr(luxian_execution, "load_luxian_0609_rules", lambda: wrappers)
    monkeypatch.setattr(luxian_execution, "evaluate_luxian_0609_trigger_gates_with_llm", _generic_gate)

    service = SichuanQCService()
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _unexpected_model_dispatch)
    await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "institute_id": "inst-033-off-001",
            "patient_id": "patient-033-off-001",
            "visit_id": "visit-033-off-001",
            "source_doc_priority": ["first_course_record"],
            "document_hits": {"first_course_record": True, "surgery_inform_consent": False},
            "structured_context": {
                "documents": {"first_course_record": [{"content": "本次手术相关病程。"}]}
            },
            "text_available": True,
        },
        rule_ids=rule_ids,
        rule_set_key=rule_set_key,
        use_execution_cache=False,
    )

    assert reader_calls == []


@pytest.mark.asyncio
async def test_paused_033_gate_off_preserves_pending_result_without_live_reader(monkeypatch):
    await _assert_current_paused_public_entry(monkeypatch, ("LX0609-11-01-01",), settings_overrides={"LUXIAN_0609_TRIGGER_GATE_ENABLED": False}, documents={})


@pytest.mark.asyncio
@pytest.mark.parametrize("raw_status", ["compliant", "non_compliant"])
async def test_paused_033_available_consent_does_not_restore_semantic_dispatch(
    monkeypatch, raw_status
):
    await _assert_current_paused_public_entry(monkeypatch, ("LX0609-11-01-01",), settings_overrides={}, documents={"surgery_inform_consent": [{"content": "手术知情同意书：" + raw_status}]})


@pytest.mark.asyncio
async def test_non_lx0609_running_bundle_preserves_legacy_evidence_payload(monkeypatch):
    _use_synthetic_legacy_bundle_material(monkeypatch)
    raw_body_marker = "SAFE_BODY_MARKER_NON_LX0609_LEGACY"

    async def _unexpected_model_dispatch(**kwargs):
        raise AssertionError("缺少同意书的非 LX0609 bundle guard 不应分派模型")

    service = SichuanQCService()
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", _unexpected_model_dispatch)
    result = await service.evaluate_running_final_bundle_input(
        bundle={
            "scene": "running",
            "institute_id": "inst-non-lx0609-001",
            "patient_id": "patient-non-lx0609-001",
            "visit_id": "visit-non-lx0609-001",
            "source_doc_priority": ["first_course_record"],
            "document_hits": {"first_course_record": True, "surgery_inform_consent": False},
            "structured_context": {
                "documents": {"first_course_record": [{"content": raw_body_marker}]}
            },
            "text_available": True,
        },
        rule_ids=["SC-087"],
        rule_set_key="other_rule_set",
        use_execution_cache=False,
    )

    assert "evidence_payload" in result
    assert raw_body_marker in repr(result["evidence_payload"])


def test_surgery_inform_consent_alias_is_isolated_to_sc087():
    service = SichuanQCService()
    bundle_documents = [
        {
            "id": "synthetic-consent",
            "document_type": "病程记录",
            "source_table": "surgery_inform_consent",
            "content": "synthetic-consent-document-content",
        }
    ]
    matched_rule_ids = {
        rule_id
        for rule_id in ("SC-087", "SC-090", "SC-134")
        if service._select_bundle_document_for_rule(
            rule=service.get_rule_by_id(rule_id),
            bundle_documents=bundle_documents,
        )
        is not None
    }

    assert matched_rule_ids == {"SC-087"}


def test_trigger_gate_should_mark_absent_trigger_as_not_applicable_candidate():
    rules = [
        _wrapper(
            "LX0609-06-01-02",
            name="CT/MRI检查前记录",
            mapped_rule_ids=["SC-146"],
            trigger_condition="当存在或应存在 CT/MRI 检查，需要读取报告时间。",
            data_dependencies=["CT/MRI医嘱", "报告时间"],
            dependency_type="跨表联查",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="入院记录：患者腹痛入院。病程记录：继续治疗。",
        evidence_payload={},
    )

    assert decisions["LX0609-06-01-02"].status == TRIGGER_ABSENT
    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[],
        gate_decisions=decisions,
    )
    assert aggregated[0]["status"] == "not_applicable"
    assert aggregated[0]["is_compliant"] is None
    assert aggregated[0]["metadata"]["trigger_gate_status"] == TRIGGER_ABSENT
    assert aggregated[0]["metadata"]["mapped_rule_ids"] == ["SC-146"]
    assert aggregated[0]["metadata"]["primary_execution_rule_id"] == "SC-146"
    assert aggregated[0]["metadata"]["aggregation_source"] == "trigger_gate"




def test_trigger_gate_decision_result_should_use_customer_readable_evidence():
    absent = decision_to_result(
        _wrapper(
            "LX0609-06-01-02",
            name="CT/MRI检查前记录",
            mapped_rule_ids=["SC-146"],
            trigger_condition="当存在或应存在 CT/MRI 检查，需要读取报告时间。",
        ),
        Luxian0609GateDecision(
            rule_id="LX0609-06-01-02",
            status=TRIGGER_ABSENT,
            reason="未发现触发事实",
        ),
    )
    data_gap = decision_to_result(
        _wrapper(
            "LX0609-06-01-05",
            name="CT/MRI检查结果未分析",
            mapped_rule_ids=["SC-147"],
            trigger_condition="存在 CT/MRI 检查报告后需分析。",
        ),
        Luxian0609GateDecision(
            rule_id="LX0609-06-01-05",
            status=TRIGGER_DATA_GAP,
            reason="缺少报告时间",
            data_gap_fields=["报告时间"],
        ),
    )

    assert absent is not None
    assert data_gap is not None
    assert "适用性：未发现与本质控点直接相关的触发事实" in absent["evidence"]
    assert "数据不足：已发现相关事件，但缺少自动判定所需字段" in data_gap["evidence"]
    assert "判定依据" not in absent["evidence"]
    assert "判定依据" not in data_gap["evidence"]


def test_trigger_gate_absent_should_override_customer_programmatic_gap():
    rules = [
        _wrapper(
            "LX0609-11-03-01",
            name="输血知情同意书：无输血知情同意书",
            mapped_rule_ids=["SC-133"],
            trigger_condition="存在输血事件时检查输血知情同意记录。",
            data_dependencies=["输血记录", "输血医嘱"],
            dependency_type="跨表联查",
        )
    ]
    decisions = {
        "LX0609-11-03-01": Luxian0609GateDecision(
            rule_id="LX0609-11-03-01",
            status=TRIGGER_ABSENT,
            reason="病历文本和证据中未发现transfusion相关触发事实",
        )
    }

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "LX0609-11-03-01",
                "status": "data_gap",
                "is_compliant": False,
                "findings": "已发现触发事件，但缺少输血记录。",
                "evidence": "数据缺口：输血记录",
                "suggestion": "补齐输血记录。",
            }
        ],
        gate_decisions=decisions,
    )

    assert aggregated[0]["status"] == "not_applicable"
    assert aggregated[0]["metadata"]["aggregation_source"] == "trigger_gate"


def test_trigger_gate_should_mark_structured_gap_and_data_gap_not_compliant():
    rules = [
        _wrapper(
            "LX0609-07-01-01",
            name="输血前常规检查不完整",
            mapped_rule_ids=["SC-133"],
            trigger_condition="当存在输血事件，需要读取输血记录、输血前常规检查。",
            data_dependencies=["输血记录", "输血前常规检查", "费用"],
            dependency_type="跨表联查",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="输血记录：输注红细胞悬液2U。",
        evidence_payload={},
    )

    assert decisions["LX0609-07-01-01"].status == TRIGGER_DATA_GAP
    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[],
        gate_decisions=decisions,
    )
    assert aggregated[0]["status"] == "data_gap"
    assert aggregated[0]["is_compliant"] is None
    assert "缺失字段" in aggregated[0]["evidence"]
    assert aggregated[0]["metadata"]["mapped_rule_ids"] == ["SC-133"]


def test_aggregator_should_prioritize_non_compliant_over_primary_compliant():
    rules = [
        _wrapper(
            "LX0609-04-02-01",
            name="手术后24小时内是否完成",
            mapped_rule_ids=["LX-026", "SC-096"],
            primary="LX-026",
            trigger_condition="当存在手术记录，需要读取手术时间、记录时间。",
        )
    ]
    execution_results = [
        {
            "rule_id": "LX-026",
            "rule_name": "手术记录时限",
            "status": "compliant",
            "is_compliant": True,
            "findings": "合规",
            "evidence": "手术记录存在",
            "suggestion": "",
            "confidence": 0.9,
            "metadata": {},
        },
        {
            "rule_id": "SC-096",
            "rule_name": "术后记录",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "手术记录超时",
            "evidence": "记录时间超过术后24小时",
            "suggestion": "及时补写",
            "confidence": 0.91,
            "metadata": {},
            "criterion_results": [{"criterion_id": "timeliness", "status": "non_compliant"}],
        },
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    assert aggregated[0]["rule_id"] == "LX0609-04-02-01"
    assert aggregated[0]["status"] == "non_compliant"
    assert aggregated[0]["metadata"]["selected_execution_rule_id"] == "SC-096"
    assert aggregated[0]["metadata"]["mapped_rule_ids"] == ["LX-026", "SC-096"]
    assert "手术记录超时" in aggregated[0]["findings"]










def test_aggregator_should_keep_specimen_detail_absence_as_non_compliant():
    rules = [
        _wrapper(
            "LX0609-06-02-02",
            name="病理检查：取材情况未在病程记录或手术记录中进行记录",
            mapped_rule_ids=["SC-099"],
            trigger_condition="病理取材情况应在手术记录或病程中记录。",
        )
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "SC-099",
                "rule_name": "术中取材和病理结果记录",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "手术记录仅笼统描述送检组织，未详细记录取材部位、切缘及淋巴结分组。",
                "evidence": "执行证据：【手术记录】标本处理：远端胃及胃周组织送病理检查。",
                "suggestion": "补充记录各切缘及淋巴结分组的取材详情。",
                "criterion_results": [{"criterion_id": "specimen_detail", "status": "non_compliant"}],
                "confidence": 0.92,
                "metadata": {},
            }
        ],
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "non_compliant"
    assert aggregated[0]["is_compliant"] is False
    assert "未详细记录取材部位" in aggregated[0]["findings"]






def test_filter_executable_rules_should_skip_only_when_all_mapped_wrappers_terminal():
    wrappers = [
        _wrapper(
            "LX0609-06-01-02",
            name="CT检查",
            mapped_rule_ids=["SC-146"],
            trigger_condition="当存在 CT/MRI 检查，需要读取报告时间。",
        ),
        _wrapper(
            "LX0609-06-01-04",
            name="CT报告后记录",
            mapped_rule_ids=["SC-146"],
            trigger_condition="当存在 CT/MRI 检查，需要读取报告时间。",
        ),
    ]
    absent_decisions = evaluate_luxian_0609_trigger_gates(
        rules=wrappers,
        medical_text="入院记录：患者腹痛入院。",
        evidence_payload={},
    )
    executable = [{"rule_id": "SC-146", "name": "CT规则"}]
    assert filter_executable_rules_by_gate(
        executable_rules=executable,
        wrapper_rules=wrappers,
        decisions=absent_decisions,
    ) == []

    present_decisions = dict(absent_decisions)
    present_decisions["LX0609-06-01-04"] = type(absent_decisions["LX0609-06-01-04"])(
        rule_id="LX0609-06-01-04",
        status=TRIGGER_PRESENT,
        reason="已发现检查触发事实",
        matched_keywords=("CT",),
    )
    assert filter_executable_rules_by_gate(
        executable_rules=executable,
        wrapper_rules=wrappers,
        decisions=present_decisions,
    ) == executable


def test_filter_executable_rules_should_skip_direct_customer_rule_when_gate_terminal():
    wrappers = [
        _wrapper(
            "LX0609-12-01-01",
            name="不合理复制病历",
            mapped_rule_ids=["CL-273"],
            trigger_condition="首次病程记录病例特点与入院记录、现病史完全相同。",
        )
    ]
    decisions = evaluate_luxian_0609_trigger_gates(
        rules=wrappers,
        medical_text="入院记录：腰背部疼痛伴活动受限3天。",
        evidence_payload={},
    )
    executable = [
        {"rule_id": "LX0609-12-01-01", "name": "不合理复制病历"},
        {"rule_id": "LX0609-12-01-02", "name": "病程记录重复"},
    ]

    assert filter_executable_rules_by_gate(
        executable_rules=executable,
        wrapper_rules=wrappers,
        decisions=decisions,
    ) == [{"rule_id": "LX0609-12-01-02", "name": "病程记录重复"}]


def test_trigger_gate_should_not_run_antibiotic_rule_without_antibiotic_fact():
    rules = [
        _wrapper(
            "LX0609-05-01-01",
            name="抗菌药物使用记录：I类、II类切口手术预防使用抗菌药物时间超过24小时",
            mapped_rule_ids=["SC-ANTIBIOTIC"],
            trigger_condition="手术患者预防使用抗菌药物时需核对医嘱起止时间。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="手术记录：患者行腹股沟疝修补术，I类切口，术后返回病房。未见抗菌药物医嘱。",
        evidence_payload={},
    )

    assert decisions["LX0609-05-01-01"].status == TRIGGER_ABSENT
    assert "未发现抗菌药物医嘱" in decisions["LX0609-05-01-01"].reason


def test_trigger_gate_should_not_run_antibiotic_rule_without_class_i_ii_incision_fact():
    rules = [
        _wrapper(
            "LX0609-05-01-01",
            name="抗菌药物使用记录",
            mapped_rule_ids=["SC-ANTIBIOTIC"],
            trigger_condition="手术患者预防使用抗菌药物时需核对医嘱起止时间。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="医嘱：术前30分钟给予头孢呋辛预防感染，术后24小时停用。",
        evidence_payload={},
    )

    assert decisions["LX0609-05-01-01"].status == TRIGGER_ABSENT
    assert "未发现I类/II类切口" in decisions["LX0609-05-01-01"].reason


def test_trigger_gate_should_return_data_gap_when_antibiotic_time_is_incomplete():
    rules = [
        _wrapper(
            "LX0609-05-01-01",
            name="抗菌药物使用记录",
            mapped_rule_ids=["SC-ANTIBIOTIC"],
            trigger_condition="手术患者预防使用抗菌药物时需核对医嘱起止时间。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="手术记录：患者行腹股沟疝修补术，I类切口。医嘱：术前30分钟给予头孢呋辛预防感染，术后继续抗菌药物治疗。",
        evidence_payload={},
    )

    assert decisions["LX0609-05-01-01"].status == TRIGGER_DATA_GAP
    assert "抗菌药物医嘱停止时间" in decisions["LX0609-05-01-01"].data_gap_fields


def test_trigger_gate_should_run_antibiotic_rule_with_class_i_ii_incision_and_order_times():
    rules = [
        _wrapper(
            "LX0609-05-01-01",
            name="抗菌药物使用记录",
            mapped_rule_ids=["SC-ANTIBIOTIC"],
            trigger_condition="手术患者预防使用抗菌药物时需核对医嘱起止时间。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="手术记录：患者行腹股沟疝修补术，I类切口。医嘱：术前30分钟给予头孢呋辛预防感染，术后24小时停用。",
        evidence_payload={},
    )

    assert decisions["LX0609-05-01-01"].status == TRIGGER_PRESENT


def test_trigger_gate_should_not_run_pathology_result_rule_on_tumor_keyword_only():
    rules = [
        _wrapper(
            "LX0609-06-02-03",
            name="病理检查：病理检查结果在手术记录、病程中未记录",
            mapped_rule_ids=["SC-PATH"],
            trigger_condition="有病理报告时，应在手术记录或病程中记录病理结果。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="入院诊断：胃恶性肿瘤。拟完善检查后治疗。",
        evidence_payload={},
    )

    assert decisions["LX0609-06-02-03"].status == TRIGGER_ABSENT
    assert "未发现病理报告" in decisions["LX0609-06-02-03"].reason


def test_trigger_gate_should_run_pathology_result_rule_with_report_fact():
    rules = [
        _wrapper(
            "LX0609-06-02-03",
            name="病理检查：病理检查结果在手术记录、病程中未记录",
            mapped_rule_ids=["SC-PATH"],
            trigger_condition="有病理报告时，应在手术记录或病程中记录病理结果。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="【病理检查报告】记录时间：2026-06-04，病理诊断提示胃中分化腺癌。",
        evidence_payload={},
    )

    assert decisions["LX0609-06-02-03"].status == TRIGGER_PRESENT


def test_evidence_formatter_should_add_family_slots_without_changing_decision():
    rule = _wrapper(
        "LX0609-07-01-01",
        name="输血前常规检查不完整",
        mapped_rule_ids=["SC-133"],
        trigger_condition="存在输血事件时检查输血申请、医嘱、记录和费用。",
    )
    result = {
        "rule_id": "LX0609-07-01-01",
        "rule_name": "输血前常规检查不完整",
        "status": "data_gap",
        "is_compliant": False,
        "findings": "",
        "evidence": "",
        "suggestion": "",
        "confidence": 0.72,
        "metadata": {},
    }
    gate = Luxian0609GateDecision(
        rule_id="LX0609-07-01-01",
        status=TRIGGER_DATA_GAP,
        reason="已发现输血触发事实，但缺少输血前检查项",
        data_gap_fields=("输血前检查项",),
        matched_keywords=("输血",),
    )

    formatted = format_luxian_0609_evidence(
        result=result,
        wrapper_rule=rule,
        gate_decision=gate,
    )

    assert formatted["status"] == "data_gap"
    assert formatted["is_compliant"] is False
    assert "证据模板" not in formatted["evidence"]
    assert "映射执行规则" not in formatted["evidence"]
    assert "输血前检查项" in formatted["evidence"]
    assert "触发状态" not in formatted["evidence"]
    assert "触发说明" not in formatted["evidence"]
    assert "trigger_status" not in formatted["evidence"]
    assert "来源线索" not in formatted["evidence"]
    assert formatted["metadata"]["evidence_template_family"] == "输血类"


def test_luxian_evidence_formatter_should_hide_internal_unknown_gate_status():
    rule = _wrapper(
        "LX0609-06-01-05",
        name="CT/MRI检查结果24小时内分析",
        mapped_rule_ids=["SC-036"],
        trigger_condition="CT/MRI影像报告结果出具后24小时内阳性结果未进行分析。",
    )
    result = {
        "rule_id": "LX0609-06-01-05",
        "status": "non_compliant",
        "is_compliant": False,
        "findings": "影像阳性结果未在病程中分析。",
        "evidence": "腰椎MRI检查报告：L4/5椎间盘突出。",
        "suggestion": "",
        "metadata": {},
    }
    gate = Luxian0609GateDecision(
        rule_id="LX0609-06-01-05",
        status="unknown",
        reason="未识别到可安全门控的触发族，进入常规执行",
    )

    formatted = format_luxian_0609_evidence(
        result=result,
        wrapper_rule=rule,
        gate_decision=gate,
    )

    assert "判定依据" not in formatted["evidence"]
    assert "腰椎MRI检查报告" in formatted["evidence"]
    assert "来源文书/表字段" in "、".join(formatted["metadata"]["evidence_template_slots"])
    assert "触发状态" not in formatted["evidence"]
    assert "触发说明" not in formatted["evidence"]
    assert "unknown" not in formatted["evidence"]


def test_luxian_evidence_formatter_should_not_emit_internal_gate_reason_only():
    rule = _wrapper(
        "LX0609-04-02-01",
        name="手术记录：手术后24小时内是否完成",
        mapped_rule_ids=["SC-061"],
        trigger_condition="手术后24小时内应完成手术记录。",
    )
    result = {
        "rule_id": "LX0609-04-02-01",
        "status": "data_gap",
        "is_compliant": False,
        "findings": "已发现手术事件，但缺少手术时间。",
        "evidence": "判定依据：已发现相关事件，但自动判定所需字段不完整。\n缺失字段：手术时间\n缺失字段：手术时间",
        "suggestion": "请补齐手术时间后复核。",
        "metadata": {},
    }
    gate = Luxian0609GateDecision(
        rule_id="LX0609-04-02-01",
        status=TRIGGER_DATA_GAP,
        reason="已发现手术触发事实，但缺少手术时间",
        data_gap_fields=("手术时间",),
    )

    formatted = format_luxian_0609_evidence(
        result=result,
        wrapper_rule=rule,
        gate_decision=gate,
    )

    assert "判定依据" not in formatted["evidence"]
    assert formatted["evidence"].count("缺失字段：手术时间") == 1
    assert "数据不足" in formatted["evidence"]


def test_luxian_result_schema_should_not_expose_internal_evidence_template_as_fallback_quote():
    rule = _wrapper(
        "LX0609-01-01-02",
        name="主诉能导出第一诊断",
        mapped_rule_ids=["SC-008", "LX-001"],
        trigger_condition="主诉应能导出第一诊断。",
    )
    result = {
        "rule_id": "LX0609-01-01-02",
        "status": "non_compliant",
        "is_compliant": False,
        "findings": "主诉与第一诊断逻辑链条不完整。",
        "evidence": (
            "证据模板：通用质控\n"
            "质控点：LX0609-01-01-02 主诉能导出第一诊断\n"
            "映射执行规则：SC-008、LX-001\n"
            "应包含证据要素：触发事实、来源文书、判定依据\n"
            "执行证据：【入院记录】纳差3天，腹泻1天"
        ),
        "suggestion": "请补充主诉与主要诊断之间的逻辑依据。",
        "metadata": {},
    }

    normalized = apply_luxian_0609_result_schema(result=result, wrapper_rule=rule)

    assert normalized["source_document"] == "质控结果"
    assert normalized["source_field"] == "关键证据"
    assert normalized["quote"] == "【入院记录】纳差3天，腹泻1天"
    assert "证据模板" not in normalized["quote"]
    assert "映射执行规则" not in normalized["quote"]


def test_aggregator_should_strip_sensitive_raw_fields():
    rules = [
        _wrapper(
            "LX0609-01-01-01",
            name="入院记录24小时内完成",
            mapped_rule_ids=["SC-002"],
            trigger_condition="入院记录是否24小时内完成。",
        )
    ]
    execution_results = [
        {
            "rule_id": "SC-002",
            "rule_name": "入院记录时限",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "入院记录超时",
            "evidence": "入院记录记录时间晚于入院后24小时",
            "suggestion": "及时完成入院记录",
            "confidence": 0.95,
            "metadata": {},
            "raw_response": "sensitive",
            "prompt": "sensitive",
            "llm_raw_output": "sensitive",
            "embedding": [1, 2, 3],
            "criterion_results": [{"criterion_id": "timeliness", "status": "non_compliant"}],
        }
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "non_compliant"
    assert "raw_response" not in aggregated[0]
    assert "prompt" not in aggregated[0]
    assert "llm_raw_output" not in aggregated[0]
    assert "embedding" not in aggregated[0]


def test_aggregator_should_strip_nested_sensitive_fields():
    rules = [
        _wrapper(
            "LX0609-01-01-01",
            name="入院记录24小时内完成",
            mapped_rule_ids=["SC-002"],
            trigger_condition="入院记录是否24小时内完成。",
        )
    ]
    execution_results = [
        {
            "rule_id": "SC-002",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "入院记录超时",
            "evidence": "入院记录记录时间晚于入院后24小时",
            "suggestion": "及时完成入院记录",
            "confidence": 0.95,
            "metadata": {
                "safe": "kept",
                "raw_response": "sensitive",
                "nested": {
                    "prompt": "sensitive",
                    "embedding": [1, 2, 3],
                    "safe_nested": "kept",
                },
                "items": [{"medical_text": "sensitive", "safe_item": "kept"}],
            },
        }
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    metadata = aggregated[0]["metadata"]
    assert metadata["safe"] == "kept"
    assert "raw_response" not in metadata
    assert "prompt" not in metadata["nested"]
    assert "embedding" not in metadata["nested"]
    assert metadata["nested"]["safe_nested"] == "kept"
    assert "medical_text" not in metadata["items"][0]
    assert metadata["items"][0]["safe_item"] == "kept"


def test_aggregator_should_add_schema_fields_for_non_compliant_result():
    rules = [
        _wrapper(
            "LX0609-12-01-02",
            name="不合理复制病历：2次以上病程记录完全相同",
            mapped_rule_ids=["CL-275"],
            trigger_condition="当存在多篇日常病程记录时检查相似度。",
            dependency_type="同域多文书文本相似度",
        )
    ]
    execution_results = [
        {
            "rule_id": "CL-275",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "2次以上病程记录高度重复。",
            "evidence": "2026-06-03 日常病程记录与 2026-06-04 日常病程记录重复片段：患者一般情况尚可。",
            "suggestion": "请补充每日病情变化分析。",
            "confidence": 0.93,
            "metadata": {"executor_type": "cross_document", "document_type": "日常病程记录"},
            "criterion_results": [{"criterion_id": "similarity", "status": "non_compliant"}],
        }
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
        audit_context={"visit_id": "2313364", "model_name": "unit-test-model"},
    )

    row = aggregated[0]
    assert row["qc_point_id"] == "LX0609-12-01-02"
    assert row["rule_set_key"] == "luxian_0609_qc_v1"
    assert row["rule_set_version"] == "2026-06-09"
    assert row["result_status"] == "non_compliant"
    assert row["executor_type"] == "cross_document"
    assert row["trigger"]["applicable"] is True
    assert row["dependencies"]["source_coverage_level"] in {"full", "unknown"}
    assert row["evidence_items"][0]["source_document_type"] == "日常病程记录"
    assert "重复片段" in row["evidence_items"][0]["quote"]
    assert row["trigger_facts"] == row["trigger"]["trigger_facts"]
    assert row["missing_sources"] == row["dependencies"]["missing_sources"]
    assert row["source_document"] == "日常病程记录"
    assert "重复片段" in row["quote"]
    assert row["threshold"] == "当存在多篇日常病程记录时检查相似度。"
    assert "重复片段" in row["actual_value"]
    assert row["decision"]["is_violation"] is True
    assert row["review"]["review_status"] == "pending"
    assert row["review_status"] == "pending"
    assert row["audit"]["visit_id"] == "2313364"
    assert row["audit"]["model_name"] == "unit-test-model"


def test_aggregator_should_add_schema_fields_for_data_gap_result():
    rules = [
        _wrapper(
            "LX0609-02-01-04",
            name="病重患者2天内无查房病程记录",
            mapped_rule_ids=["SC-051"],
            trigger_condition="当存在病重医嘱时检查2天内查房病程记录。",
            data_dependencies=["病重医嘱起止时间", "记录时间轴"],
            dependency_type="跨表联查",
        )
    ]
    gate = Luxian0609GateDecision(
        rule_id="LX0609-02-01-04",
        status=TRIGGER_DATA_GAP,
        reason="已发现病重触发事实，但缺少医嘱起止时间",
        data_gap_fields=("病重医嘱起止时间",),
        matched_keywords=("病重",),
    )

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[],
        gate_decisions={"LX0609-02-01-04": gate},
    )

    row = aggregated[0]
    assert row["status"] == "data_gap"
    assert row["result_status"] == "data_gap"
    assert row["trigger"]["applicable"] is True
    assert row["trigger"]["trigger_facts"][0]["fact_value"] == "病重"
    assert row["dependencies"]["source_coverage_level"] == "partial"
    assert row["dependencies"]["missing_sources"][0]["source_name"] == "病重医嘱起止时间"
    assert "病重医嘱起止时间" in row["dependencies"]["data_gap_reason"]
    assert row["review"]["review_status"] == "pending"


def test_aggregator_should_add_schema_fields_for_not_applicable_result():
    rules = [
        _wrapper(
            "LX0609-07-04-02",
            name="输血医嘱与收费不一致",
            mapped_rule_ids=["SC-146"],
            trigger_condition="当存在输血记录时检查医嘱与费用一致性。",
            data_dependencies=["输血医嘱", "费用明细"],
            dependency_type="跨表联查",
        )
    ]
    gate = Luxian0609GateDecision(
        rule_id="LX0609-07-04-02",
        status=TRIGGER_ABSENT,
        reason="病历文本和证据中未发现transfusion相关触发事实",
    )

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[],
        gate_decisions={"LX0609-07-04-02": gate},
    )

    row = aggregated[0]
    assert row["status"] == "not_applicable"
    assert row["result_status"] == "not_applicable"
    assert row["trigger"]["applicable"] is False
    assert "未发现" in row["trigger"]["not_applicable_reason"]
    assert row["dependencies"]["missing_sources"] == []
    assert row["review"]["review_status"] == "not_required"


def test_aggregator_should_prioritize_data_gap_over_compliant():
    rules = [
        _wrapper(
            "LX0609-07-01-01",
            name="输血前常规检查不完整",
            mapped_rule_ids=["SC-133", "LXE-52"],
            primary="SC-133",
            trigger_condition="存在输血事件时检查输血申请、医嘱、记录和费用。",
        )
    ]
    execution_results = [
        {
            "rule_id": "SC-133",
            "status": "compliant",
            "is_compliant": True,
            "findings": "未发现问题",
            "confidence": 0.88,
            "metadata": {},
        },
        {
            "rule_id": "LXE-52",
            "status": "data_gap",
            "is_compliant": False,
            "findings": "缺少输血费用明细，无法判断一致性",
            "evidence": "输血记录存在，但费用数据缺失",
            "suggestion": "补齐费用数据后复核",
            "confidence": 0.82,
            "metadata": {},
        },
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "data_gap"
    assert aggregated[0]["is_compliant"] is None
    assert aggregated[0]["metadata"]["selected_execution_rule_id"] == "LXE-52"
    assert aggregated[0]["metadata"]["aggregation_source"] == "mapped_data_gap"


def test_aggregator_should_prioritize_data_gap_over_uncertain():
    rules = [
        _wrapper(
            "LX0609-07-01-01",
            name="输血前常规检查不完整",
            mapped_rule_ids=["SC-133", "LXE-52"],
            primary="SC-133",
            trigger_condition="存在输血事件时检查输血申请、医嘱、记录和费用。",
        )
    ]
    execution_results = [
        {
            "rule_id": "SC-133",
            "status": "uncertain",
            "is_compliant": False,
            "findings": "证据边界不清，需人工复核",
            "confidence": 0.95,
            "metadata": {},
        },
        {
            "rule_id": "LXE-52",
            "status": "data_gap",
            "is_compliant": False,
            "findings": "缺少输血费用明细，无法判断一致性",
            "evidence": "输血记录存在，但费用数据缺失",
            "confidence": 0.82,
            "metadata": {},
        },
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "data_gap"
    assert aggregated[0]["metadata"]["aggregation_source"] == "mapped_data_gap"


def test_luxian_0609_summary_should_use_canonical_statuses_and_exclude_not_applicable_denominator():
    summary = summarize_luxian_0609_results(
        [
            {"status": "compliant", "is_compliant": True},
            {"status": "not_applicable", "is_compliant": None},
            {"status": "data_gap", "is_compliant": False},
            {"status": "uncertain", "is_compliant": False},
            {"status": "technical_error_internal", "is_compliant": False},
        ]
    )

    assert summary["status_counts"] == {
        "non_compliant": 0,
        "ai_suggested_non_compliant": 0,
        "ai_suggested_compliant": 0,
        "compliant": 1,
        "not_applicable": 1,
        "data_gap": 1,
        "uncertain": 1,
        "not_executed": 0,
        "technical_error": 1,
    }
    assert summary["confirmed_compliant_count"] == 1
    assert summary["compliant_count"] == 1
    assert summary["not_applicable_count"] == 1
    assert summary["data_gap_count"] == 1
    assert summary["technical_error_count"] == 1
    assert summary["compliance_denominator"] == 2
    assert summary["compliance_rate_calculable"] is True
    assert summary["confirmed_compliance_rate"] == 50.0
    assert summary["compliance_rate"] == 50.0


def test_luxian_0609_summary_zero_denominator_returns_not_calculable_instead_of_100():
    summary = summarize_luxian_0609_results(
        [
            {"status": "data_gap"},
            {"status": "technical_error"},
        ]
    )

    assert summary["confirmed_compliant_count"] == 0
    assert summary["ai_suggested_compliant_count"] == 0
    assert summary["compliant_count"] == 0
    assert summary["compliance_denominator"] == 0
    assert summary["compliance_rate_calculable"] is False
    assert summary["confirmed_compliance_rate"] is None
    assert summary["compliance_rate"] is None


def test_luxian_0609_summary_separates_ai_suggested_compliant_from_confirmed_compliance():
    summary = summarize_luxian_0609_results(
        [
            {"status": "ai_suggested_compliant"},
        ]
    )

    assert summary["confirmed_compliant_count"] == 0
    assert summary["compliant_count"] == 0
    assert summary["ai_suggested_compliant_count"] == 1
    assert summary["compliance_denominator"] == 1
    assert summary["compliance_rate_calculable"] is True
    assert summary["confirmed_compliance_rate"] == 0.0
    assert summary["compliance_rate"] == 0.0


def test_batch_record_status_counts_should_separate_not_applicable_from_compliant():
    counts = _build_record_status_counts(
        total_records=4,
        issue_record_ids={"VISIT-ISSUE"},
        uncertain_record_ids=set(),
        data_gap_record_ids={"VISIT-GAP"},
        failed_record_ids=set(),
        not_applicable_record_ids={"VISIT-NA", "VISIT-ISSUE"},
    )

    assert counts == {
        "non_compliant": 1,
        "uncertain": 0,
        "data_gap": 1,
        "not_applicable": 1,
        "not_executed": 0,
        "failed": 0,
        "compliant": 1,
    }


def test_aggregator_should_prioritize_direct_customer_programmatic_result():
    rules = [
        _wrapper(
            "LX0609-01-02-01",
            name="首次病程8小时内完成",
            mapped_rule_ids=["CL-081", "SC-021"],
            primary="CL-081",
            trigger_condition="入院后8小时内完成首次病程记录。",
        )
    ]
    execution_results = [
        {
            "rule_id": "CL-081",
            "status": "compliant",
            "is_compliant": True,
            "findings": "LLM 判断合规",
            "confidence": 0.8,
            "metadata": {},
        },
        {
            "rule_id": "LX0609-01-02-01",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "首次病程记录未在入院后8小时内完成。",
            "evidence": "入院时间：2026-06-01 08:00:00；首次病程记录时间：2026-06-01 18:30:00；间隔：10.5小时",
            "suggestion": "请核对首次病程记录完成时间。",
            "confidence": 0.94,
            "metadata": {"executor_type": "program"},
            "criterion_results": [{"criterion_id": "timeliness", "status": "non_compliant"}],
        },
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "non_compliant"
    assert aggregated[0]["metadata"]["aggregation_source"] == "customer_programmatic"
    assert aggregated[0]["metadata"]["selected_execution_rule_id"] == "LX0609-01-02-01"
    assert "10.5小时" in aggregated[0]["evidence"]


def test_luxian_programmatic_rules_should_evaluate_core_timeline_rules():
    rules = [
        _wrapper(
            "LX0609-01-01-01",
            name="入院记录24小时内完成",
            mapped_rule_ids=["SC-002"],
            trigger_condition="入院记录是否24小时内完成。",
        ),
        _wrapper(
            "LX0609-01-02-01",
            name="首次病程8小时内完成",
            mapped_rule_ids=["CL-081", "SC-021"],
            trigger_condition="首次病程是否8小时内完成。",
        ),
        _wrapper(
            "LX0609-02-01-01",
            name="主治医师首次查房48小时内完成",
            mapped_rule_ids=["SC-048"],
            trigger_condition="主治医师首次查房是否48小时内完成。",
        ),
        _wrapper(
            "LX0609-02-01-02",
            name="高级职称首次查房72小时内完成",
            mapped_rule_ids=["SC-049"],
            trigger_condition="副主任/主任医师首次查房是否72小时内完成。",
        ),
    ]
    evidence_payload = {
        "programmatic_timeline": {
            "admission_time": "2026-06-01 08:00:00",
            "documents": {
                "admission_record": [
                    {"title": "入院记录", "authored_at": "2026-06-02 10:30:00"}
                ],
                "first_course_record": [
                    {"title": "首次病程记录", "authored_at": "2026-06-01 18:30:00"}
                ],
                "daily_course_record": [],
                "senior_course_record": [
                    {"title": "主任医师查房记录", "authored_at": "2026-06-04 13:30:00"}
                ],
            },
        }
    }

    results = evaluate_luxian_0609_programmatic_rules(
        wrapper_rules=rules,
        evidence_payload=evidence_payload,
    )
    by_id = {item["rule_id"]: item for item in results}

    assert by_id["LX0609-01-01-01"]["status"] == "non_compliant"
    assert "26.5小时" in by_id["LX0609-01-01-01"]["evidence"]
    assert by_id["LX0609-01-02-01"]["status"] == "non_compliant"
    assert "10.5小时" in by_id["LX0609-01-02-01"]["evidence"]
    assert by_id["LX0609-02-01-01"]["status"] == "non_compliant"
    assert "主治医师首次查房：缺失" in by_id["LX0609-02-01-01"]["evidence"]
    assert by_id["LX0609-02-01-02"]["status"] == "non_compliant"
    assert "77.5小时" in by_id["LX0609-02-01-02"]["evidence"]


def test_luxian_programmatic_rules_should_accept_deputy_acting_attending_round():
    rules = [
        _wrapper(
            "LX0609-02-01-01",
            name="主治医师首次查房48小时内完成",
            mapped_rule_ids=["SC-048"],
            trigger_condition="主治医师首次查房是否48小时内完成。",
        )
    ]
    evidence_payload = {
        "programmatic_timeline": {
            "admission_time": "2026-02-02 10:07:26",
            "documents": {
                "admission_record": [
                    {"title": "入院记录", "authored_at": "2026-02-02 10:07:26"}
                ],
                "senior_course_record": [
                    {
                        "title": "郑瑞清副主任医师代主治医师查房记录",
                        "author_title": "副主任医师",
                        "authored_at": "2026-02-03 11:07:40",
                    }
                ],
            },
        }
    }

    results = evaluate_luxian_0609_programmatic_rules(
        wrapper_rules=rules,
        evidence_payload=evidence_payload,
    )

    assert results[0]["rule_id"] == "LX0609-02-01-01"
    assert results[0]["status"] == "compliant"
    assert "副主任医师代主治医师查房记录" in results[0]["evidence"]


def test_luxian_programmatic_rules_should_detect_stable_round_gap_over_three_days():
    rules = [
        _wrapper(
            "LX0609-02-01-03",
            name="病情稳定患者3天内无查房病程记录",
            mapped_rule_ids=["SC-051", "CL-231"],
            trigger_condition="未下病危、病重医嘱的病情稳定患者3天内应有查房病程记录。",
        )
    ]
    evidence_payload = {
        "programmatic_timeline": {
            "visit_id": "2207717",
            "documents": {
                "senior_course_record": [
                    {"title": "上级医师查房记录", "authored_at": "2026-02-04 11:08:49"},
                    {"title": "出院前查房记录", "authored_at": "2026-02-09 09:34:44"},
                ],
                "daily_course_record": [
                    {"title": "日常病程记录", "authored_at": "2026-02-13 15:48:50"},
                ],
            },
        }
    }

    results = evaluate_luxian_0609_programmatic_rules(
        wrapper_rules=rules,
        evidence_payload=evidence_payload,
    )

    assert results[0]["rule_id"] == "LX0609-02-01-03"
    assert results[0]["status"] == "non_compliant"
    assert "间隔：4.9天" in results[0]["evidence"]
    assert "未见病危/病重医嘱" in results[0]["evidence"]
    assert {item["evidence_role"] for item in results[0]["evidence_items"]} == {
        "previous_course_record",
        "next_course_record",
    }


def test_luxian_programmatic_rules_should_not_apply_stable_round_when_critical_order_exists():
    rules = [
        _wrapper(
            "LX0609-02-01-03",
            name="病情稳定患者3天内无查房病程记录",
            mapped_rule_ids=["SC-051", "CL-231"],
            trigger_condition="未下病危、病重医嘱的病情稳定患者3天内应有查房病程记录。",
        )
    ]
    evidence_payload = {
        "primary_document_text": "2026-02-02 09:00 下达病重医嘱。",
        "programmatic_timeline": {
            "visit_id": "2207717",
            "documents": {
                "daily_course_record": [
                    {"title": "日常病程记录", "authored_at": "2026-02-02 10:00:00"},
                    {"title": "日常病程记录", "authored_at": "2026-02-07 10:00:00"},
                ],
            },
        },
    }

    results = evaluate_luxian_0609_programmatic_rules(
        wrapper_rules=rules,
        evidence_payload=evidence_payload,
    )

    assert results[0]["status"] == "not_applicable"
    assert "病危或病重医嘱" in results[0]["findings"]


def test_programmatic_timeline_schema_should_include_threshold_actual_and_delta():
    rules = [
        _wrapper(
            "LX0609-01-02-01",
            name="首次病程8小时内完成",
            mapped_rule_ids=["CL-081", "SC-021"],
            trigger_condition="首次病程是否8小时内完成。",
        )
    ]
    evidence_payload = {
        "programmatic_timeline": {
            "admission_time": "2026-06-01 08:00:00",
            "documents": {
                "first_course_record": [
                    {"document_id": "F1", "title": "首次病程记录", "authored_at": "2026-06-01 18:30:00"}
                ],
            },
        }
    }

    execution_results = evaluate_luxian_0609_programmatic_rules(
        wrapper_rules=rules,
        evidence_payload=evidence_payload,
    )
    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    row = aggregated[0]
    assert row["status"] == "non_compliant"
    assert row["is_compliant"] is False
    assert row["threshold"] == "首次病程记录应在入院后8小时内完成"
    assert row["expected_value"] == "<=8小时"
    assert row["actual_value"] == "10.5小时"
    assert row["delta"] == "2.5小时"
    assert row["source_table"] == "first_course_record"
    assert row["source_document"] == "首次病程记录"
    assert "2026-06-01 18:30:00" in row["quote"]


def test_cross_document_schema_should_keep_multiple_source_documents_and_quotes():
    rules = [
        _wrapper(
            "LX0609-12-01-02",
            name="不合理复制病历：2次以上病程记录完全相同",
            mapped_rule_ids=["CL-275"],
            trigger_condition="当存在多篇日常病程记录时检查相似度。",
            dependency_type="同域多文书文本相似度",
        )
    ]
    execution_results = [
        {
            "rule_id": "CL-275",
            "status": "non_compliant",
            "is_compliant": False,
            "findings": "两份病程记录相似度0.99，超过70%阈值。",
            "evidence": "两份病程记录重复。",
            "suggestion": "请复核复制病历。",
            "confidence": 0.94,
            "metadata": {"executor_type": "cross_document"},
            "evidence_items": [
                {
                    "source_table": "daily_course_record",
                    "source_document_type": "日常病程记录",
                    "source_document_name": "2026-06-03日常病程记录",
                    "record_time": "2026-06-03 09:00:00",
                    "field_path": "record_content",
                    "quote": "患者一般情况尚可，生命体征平稳。",
                },
                {
                    "source_table": "daily_course_record",
                    "source_document_type": "日常病程记录",
                    "source_document_name": "2026-06-04日常病程记录",
                    "record_time": "2026-06-04 09:00:00",
                    "field_path": "record_content",
                    "quote": "患者一般情况尚可，生命体征平稳。",
                },
            ],
            "threshold": "相似度<=70%",
            "actual_value": "相似度99%",
            "delta": "超出29个百分点",
        }
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=execution_results,
        gate_decisions={},
    )

    row = aggregated[0]
    assert row["executor_type"] == "cross_document"
    assert len(row["evidence_items"]) == 2
    assert {item["source_document_name"] for item in row["evidence_items"]} == {
        "2026-06-03日常病程记录",
        "2026-06-04日常病程记录",
    }
    assert all(item["quote"] for item in row["evidence_items"])
    assert row["threshold"] == "相似度<=70%"
    assert row["actual_value"] == "相似度99%"
    assert row["delta"] == "超出29个百分点"
    assert row["status"] == "non_compliant"
    assert row["is_compliant"] is False


def test_document_result_should_use_display_rule_count_and_not_count_data_gap_compliant():
    service = SichuanQCService.__new__(SichuanQCService)
    service.client = type("Client", (), {"model": "unit-test-model"})()
    orchestrated = {
        "display_rule_ids": ["LX0609-01-01-01", "LX0609-01-02-01", "LX0609-04-02-01"],
        "display_rule_count": 3,
        "results": [
            {
                "rule_id": "LX0609-01-01-01",
                "rule_name": "入院记录24小时内完成",
                "status": "compliant",
                "is_compliant": True,
                "reason_code": "requirement_satisfied",
                "customer_display_facts": {"timeliness_state": "within_threshold"},
                "criterion_results": [
                    {
                        "criterion_id": "chief_complaint_length",
                        "kind": "text_length",
                        "status": "passed",
                        "reason_code": "within_limit",
                        "actual_value": 14,
                        "expected_value": 20,
                    }
                ],
                "customer_evidence": [
                    {
                        "source_type": "admission_record",
                        "source_document_id": "admission-document-1",
                    }
                ],
                "model_analysis": "模型已完成该规则的医学关系分析。",
                "metadata": {},
            },
            {
                "rule_id": "LX0609-01-02-01",
                "rule_name": "首次病程8小时内完成",
                "status": "not_applicable",
                "is_compliant": True,
                "metadata": {},
            },
            {
                "rule_id": "LX0609-04-02-01",
                "rule_name": "手术记录24小时内完成",
                "status": "data_gap",
                "is_compliant": False,
                "reason_code": "authoritative_time_missing",
                "customer_message": "缺少用于计算质控时限的权威时间，暂时无法完成本项质控。",
                "missing_sources": [],
                "missing_fields": ["用于计算质控时限的权威时间"],
                "data_gap_details": {
                    "reason_code": "authoritative_time_missing",
                    "reason_label": "权威时间缺失",
                    "missing_sources": [],
                    "missing_fields": ["用于计算质控时限的权威时间"],
                    "customer_message": "缺少用于计算质控时限的权威时间，暂时无法完成本项质控。",
                },
                "metadata": {},
            },
        ],
        "luxian_0609_summary": {
            "customer_rule_count": 3,
            "data_gap_count": 1,
        },
    }

    result = service._build_document_evaluation_result(
        document_id="visit-1",
        document_type="运行病历",
        rules=[{"rule_id": "SC-002"}],
        orchestrated=orchestrated,
    )

    assert result["total_rules"] == 3
    assert result["applicable_rules"] == ["LX0609-01-01-01", "LX0609-01-02-01", "LX0609-04-02-01"]
    assert result["evaluation_summary"]["compliant_rules"] == 1
    assert result["evaluation_summary"]["not_applicable"] == 1
    assert result["evaluation_summary"]["data_gap_count"] == 1
    assert result["evaluation_summary"]["compliance_denominator"] == 1
    assert result["evaluation_summary"]["compliance_rate"] == 100.0
    assert result["evaluation_summary"]["luxian_0609_summary"]["data_gap_count"] == 1
    assert result["evaluation_results"][0]["reason_code"] == "requirement_satisfied"
    assert result["evaluation_results"][0]["customer_display_facts"] == {
        "timeliness_state": "within_threshold"
    }
    assert result["evaluation_results"][0]["criterion_results"][0]["criterion_id"] == "chief_complaint_length"
    assert result["evaluation_results"][0]["customer_evidence"] == [
        {
            "source_type": "admission_record",
            "source_document_id": "admission-document-1",
        }
    ]
    assert result["evaluation_results"][0]["model_analysis"] == "模型已完成该规则的医学关系分析。"
    gap_result = result["evaluation_results"][2]
    assert gap_result["customer_message"] == "缺少用于计算质控时限的权威时间，暂时无法完成本项质控。"
    assert gap_result["missing_sources"] == []
    assert gap_result["missing_fields"] == ["用于计算质控时限的权威时间"]
    assert gap_result["data_gap_details"]["reason_label"] == "权威时间缺失"


def test_trigger_gate_should_ignore_clear_negated_trigger_phrases():
    rules = [
        _wrapper(
            "LX0609-11-03-01",
            name="输血知情同意记录",
            mapped_rule_ids=["SC-133"],
            trigger_condition="当存在输血事件，需要检查输血知情同意记录。",
        ),
        _wrapper(
            "LX0609-04-02-01",
            name="手术记录24小时内完成",
            mapped_rule_ids=["LX-026"],
            trigger_condition="当存在手术记录，需要读取手术时间、记录时间。",
        ),
        _wrapper(
            "LX0609-02-01-05",
            name="病危每日记录",
            mapped_rule_ids=["SC-051"],
            trigger_condition="当存在病危医嘱时，检查每日病程记录。",
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="患者本次住院无输血，未行手术，未下达病危医嘱。",
        evidence_payload={},
    )

    assert decisions["LX0609-11-03-01"].status == TRIGGER_ABSENT
    assert decisions["LX0609-04-02-01"].status == TRIGGER_ABSENT
    assert decisions["LX0609-02-01-05"].status == TRIGGER_ABSENT


def test_critical_round_gate_should_require_explicit_critical_order():
    rules = [
        _wrapper(
            "LX0609-02-01-04",
            name="病重患者2天内无查房病程记录",
            mapped_rule_ids=["SC-051", "CL-231"],
            trigger_condition="病重患者应至少每2天记录查房病程。",
            data_dependencies=["病重医嘱起止时间", "记录时间轴"],
            dependency_type="跨表联查",
        ),
        _wrapper(
            "LX0609-02-01-05",
            name="病危患者每日查房病程",
            mapped_rule_ids=["SC-051", "CL-231"],
            trigger_condition="病危患者应每日记录查房病程。",
            data_dependencies=["病危医嘱起止时间", "记录时间轴"],
            dependency_type="跨表联查",
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="入院记录：患者病情危重，需严密观察。病程记录：继续抗感染及支持治疗。",
        evidence_payload={
            "summary": "数据缺口：病危医嘱起止时间；病重医嘱起止时间",
            "missing_sources": ["病危医嘱起止时间", "病重医嘱起止时间"],
        },
    )

    assert decisions["LX0609-02-01-04"].status == TRIGGER_ABSENT
    assert decisions["LX0609-02-01-05"].status == TRIGGER_ABSENT


def test_critical_round_gate_should_continue_when_order_has_timing_context():
    rules = [
        _wrapper(
            "LX0609-02-01-05",
            name="病危患者每日查房病程",
            mapped_rule_ids=["SC-051", "CL-231"],
            trigger_condition="病危患者应每日记录查房病程。",
            data_dependencies=["病危医嘱起止时间", "记录时间轴"],
            dependency_type="跨表联查",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "医嘱记录：2026-06-02 09:00下达病危医嘱，起始时间：2026-06-02 09:00，"
            "停止时间：未停止，持续执行。"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-02-01-05"].status == TRIGGER_PRESENT
    assert decisions["LX0609-02-01-05"].matched_keywords == ("病危医嘱",)


def test_transfusion_gate_should_not_treat_generic_infusion_as_transfusion():
    rules = [
        _wrapper(
            "LX0609-07-03-01",
            name="输血后评价",
            mapped_rule_ids=["CL-255", "SC-074"],
            trigger_condition="存在输血事件时检查输血后评价。",
            data_dependencies=["输血记录"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="日常病程记录：现患者症状好转，甘露醇、维生素C、地塞米松静滴已达疗效，今日输注后停止。",
        evidence_payload={},
    )

    assert decisions["LX0609-07-03-01"].status == TRIGGER_ABSENT


def test_transfusion_gate_should_ignore_rule_metadata_in_evidence_payload():
    rules = [
        _wrapper(
            "LX0609-07-02-01",
            name="输血记录：无输血病程记录",
            mapped_rule_ids=["SC-074"],
            trigger_condition="存在输血事件时检查输血病程记录。",
            data_dependencies=["输血记录"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="日常病程记录：甘露醇、维生素C、地塞米松静滴，今日输注后停止。",
        evidence_payload={
            "rule_name": "输血记录：无输血病程记录",
            "data_dependencies": ["输血记录"],
            "source_documents": [
                {
                    "document_type": "日常病程记录",
                    "content": "患者症状好转，继续康复治疗，未见特殊治疗不良反应。",
                }
            ],
        },
    )

    assert decisions["LX0609-07-02-01"].status == TRIGGER_ABSENT


def test_transfusion_gate_should_ignore_missing_document_requirements():
    rules = [
        _wrapper(
            "LX0609-11-03-01",
            name="输血知情同意书：无输血知情同意书",
            mapped_rule_ids=["SC-133"],
            trigger_condition="存在输血事件时检查输血知情同意记录。",
            data_dependencies=["输血记录", "输血医嘱"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="日常病程记录：甘露醇、维生素C、地塞米松静滴后患者腰背痛较前缓解。",
        evidence_payload={
            "missing_sources": ["输血记录", "输血医嘱"],
            "document_hits": {"输血记录": 0},
            "required_documents": ["输血记录"],
        },
    )

    assert decisions["LX0609-11-03-01"].status == TRIGGER_ABSENT


def test_transfusion_gate_should_ignore_internal_gap_summary_keywords():
    rules = [
        _wrapper(
            "LX0609-07-03-01",
            name="输血后评价：无输血后评价",
            mapped_rule_ids=["CL-255", "SC-074"],
            trigger_condition="存在输血事件时检查输血后评价。",
            data_dependencies=["输血记录", "输血医嘱"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="日常病程记录：现患者症状好转，甘露醇、维生素C、地塞米松静滴已达疗效，今日输注后停止。",
        evidence_payload={
            "summary": "触发关键词：输血记录\n数据缺口：输血医嘱或输血记录\n应包含证据要素：输血申请、输血医嘱、输血记录、费用、输血前检查项",
        },
    )

    assert decisions["LX0609-07-03-01"].status == TRIGGER_ABSENT


def test_transfusion_gate_should_ignore_result_gap_text_without_patient_fact():
    rules = [
        _wrapper(
            "LX0609-11-03-01",
            name="输血知情同意书：无输血知情同意书",
            mapped_rule_ids=["SC-133"],
            trigger_condition="存在输血事件时检查输血知情同意记录。",
            data_dependencies=["输血记录", "输血医嘱"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "判定依据：已发现相关事件，但自动判定所需字段不完整。\n"
            "缺失字段：输血医嘱或输血记录\n"
            "应包含证据要素：输血申请、输血医嘱、输血记录、费用、输血前检查项"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-11-03-01"].status == TRIGGER_ABSENT


def test_transfusion_gate_should_require_blood_product_or_transfusion_document():
    rules = [
        _wrapper(
            "LX0609-11-03-01",
            name="输血知情同意书",
            mapped_rule_ids=["SC-133"],
            trigger_condition="存在输血事件时检查输血知情同意记录。",
            data_dependencies=["输血记录", "输血知情同意书"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="输血记录：2026-06-02 15:00 输注去白悬浮红细胞2U。",
        evidence_payload={},
    )

    assert decisions["LX0609-11-03-01"].status == TRIGGER_PRESENT
    assert decisions["LX0609-11-03-01"].matched_keywords


def test_transfusion_gate_should_accept_real_transfusion_application_context():
    rules = [
        _wrapper(
            "LX0609-07-01-02",
            name="输血前评估",
            mapped_rule_ids=["SC-074"],
            trigger_condition="存在输血事件时检查输血前评估。",
            data_dependencies=["输血申请", "输血医嘱"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="输血申请：患者血红蛋白68g/L，拟输注去白悬浮红细胞2U，已完成ABO血型及交叉配血。",
        evidence_payload={},
    )

    assert decisions["LX0609-07-01-02"].status == TRIGGER_DATA_GAP
    assert "输血申请" in decisions["LX0609-07-01-02"].matched_keywords


def test_transfusion_gate_should_ignore_blood_product_words_without_strong_trigger():
    rules = [
        _wrapper(
            "LX0609-07-03-01",
            name="输血后评价",
            mapped_rule_ids=["SC-074"],
            trigger_condition="存在输血事件时检查输血后评价。",
            data_dependencies=["输血记录", "输血医嘱"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "日常病程记录：患者凝血功能复查，血浆D-二聚体略高，血小板计数正常。"
            "既往史中否认输血史。"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-07-03-01"].status == TRIGGER_ABSENT


def test_trigger_gate_should_use_lx0609_rule_family_before_keyword_guessing():
    rules = [
        _wrapper(
            "LX0609-06-01-05",
            name="CT/MRI 阳性结果未分析",
            mapped_rule_ids=["LXE-23"],
            trigger_condition="CT/MRI影像报告结果出具后24小时内阳性结果未进行分析。",
            data_dependencies=["报告时间"],
        ),
        _wrapper(
            "LX0609-06-02-03",
            name="病理检查结果在手术记录、病程中未记录",
            mapped_rule_ids=["SC-037"],
            trigger_condition="病理检查结果应在手术记录、病程中记录。",
            data_dependencies=["病理报告时间"],
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="术前讨论、手术记录、麻醉记录齐全；另见腰椎MRI阳性报告，病理报告提示腺癌。",
        evidence_payload={},
    )

    assert decisions["LX0609-06-01-05"].status == TRIGGER_DATA_GAP
    assert decisions["LX0609-06-01-05"].matched_keywords == ("MRI",)
    assert decisions["LX0609-06-02-03"].status == TRIGGER_DATA_GAP
    assert "病理报告" in decisions["LX0609-06-02-03"].matched_keywords


def test_investigation_gate_should_ignore_course_keywords_without_report_entity():
    rules = [
        _wrapper(
            "LX0609-06-01-05",
            name="CT/MRI 阳性结果未分析",
            mapped_rule_ids=["LXE-23"],
            trigger_condition="CT/MRI影像报告结果出具后24小时内阳性结果未进行分析。",
            data_dependencies=["报告时间"],
        ),
        _wrapper(
            "LX0609-06-03-03",
            name="细菌培养结果在病程中未记录",
            mapped_rule_ids=["SC-036"],
            trigger_condition="细菌培养结果出具后应在病程中记录分析。",
            data_dependencies=["培养报告时间"],
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="日常病程记录：建议复查胸部CT，注意痰培养送检可能，继续观察病情变化。",
        evidence_payload={},
    )

    assert decisions["LX0609-06-01-05"].status == TRIGGER_ABSENT
    assert decisions["LX0609-06-03-03"].status == TRIGGER_ABSENT


def test_investigation_gate_should_accept_report_entity_or_order_with_report_time():
    rules = [
        _wrapper(
            "LX0609-06-01-05",
            name="CT/MRI 阳性结果未分析",
            mapped_rule_ids=["LXE-23"],
            trigger_condition="CT/MRI影像报告结果出具后24小时内阳性结果未进行分析。",
            data_dependencies=["报告时间"],
        ),
        _wrapper(
            "LX0609-06-03-03",
            name="细菌培养结果在病程中未记录",
            mapped_rule_ids=["SC-036"],
            trigger_condition="细菌培养结果出具后应在病程中记录分析。",
            data_dependencies=["培养报告时间"],
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "腰椎MRI检查报告：报告时间2026-06-01 14:00，L4/5椎间盘突出。"
            "尿培养报告：培养结果大肠埃希菌阳性，药敏结果提示头孢曲松敏感。"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-06-01-05"].status == TRIGGER_PRESENT
    assert decisions["LX0609-06-03-03"].status == TRIGGER_DATA_GAP


def test_trigger_gate_should_not_treat_empty_surgery_template_as_surgery_event():
    rules = [
        _wrapper(
            "LX0609-04-02-01",
            name="手术记录24小时内完成",
            mapped_rule_ids=["LX-026", "SC-096"],
            trigger_condition="手术记录应在术后24小时内完成。",
            data_dependencies=["手术时间", "手术记录"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "既往史：患者既往行痔疮手术。手术记录模板：记录时间:  科室:  病房:  记录者:  "
            "手术医生签名:  术前小结:  手术项目:  手术编码:  手术开始时间:  手术结束时间:  "
            "麻醉方式:  术后诊断:"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-04-02-01"].status == TRIGGER_ABSENT


def test_lx0609_024_gate_should_not_apply_to_non_tumor_surgery():
    rules = [
        _wrapper(
            "LX0609-04-02-03",
            name="恶性肿瘤手术记录未书写淋巴结清扫情况",
            mapped_rule_ids=["SC-099"],
            trigger_condition="恶性肿瘤手术记录应书写淋巴结清扫情况。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "手术记录：手术名称：膝关节镜下左膝内侧半月板成形术+滑膜切除术。"
            "术前诊断：左膝半月板损伤。手术经过：清理关节腔增生滑膜及脂肪垫，"
            "修整内侧半月板，冲洗关节腔后缝合。"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-04-02-03"].status == TRIGGER_ABSENT
    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "SC-099",
                "rule_code": "SC-099",
                "rule_name": "术中取材情况和病理结果未在手术记录中记录",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "手术记录未记录取材情况。",
            }
        ],
        gate_decisions=decisions,
    )

    assert aggregated[0]["rule_id"] == "LX0609-04-02-03"
    assert aggregated[0]["status"] == "not_applicable"
    assert aggregated[0]["metadata"]["trigger_gate_status"] == TRIGGER_ABSENT


def test_lx0609_024_gate_should_apply_to_malignant_tumor_surgery():
    rules = [
        _wrapper(
            "LX0609-04-02-03",
            name="恶性肿瘤手术记录未书写淋巴结清扫情况",
            mapped_rule_ids=["SC-099"],
            trigger_condition="恶性肿瘤手术记录应书写淋巴结清扫情况。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "手术记录：手术名称：腹腔镜远端胃癌根治术。术前诊断：胃窦癌。"
            "术后诊断：胃中分化腺癌。手术经过：远端胃切除并处理胃周组织。"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-04-02-03"].status == TRIGGER_PRESENT
    assert any("胃癌" in keyword or "腺癌" in keyword for keyword in decisions["LX0609-04-02-03"].matched_keywords)


def test_lx0609_024_gate_should_not_use_history_cancer_for_current_urology_surgery():
    rules = [
        _wrapper(
            "LX0609-04-02-03",
            name="恶性肿瘤手术记录未书写淋巴结清扫情况",
            mapped_rule_ids=["SC-099"],
            trigger_condition="恶性肿瘤手术记录应书写淋巴结清扫情况。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "入院记录：既往史：肺癌术后，定期复查。"
            "手术记录：手术名称：经尿道输尿管镜碎石取石术+双J管置入术。"
            "术前诊断：输尿管结石。手术经过：置入斑马导丝，留置双J管，使用泌尿手术耗材。"
        ),
        evidence_payload={},
    )

    assert decisions["LX0609-04-02-03"].status == TRIGGER_ABSENT


class _FakeLLMGateClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        return {"choices": [{"message": {"content": self.content}}]}


@pytest.mark.asyncio
async def test_lx0609_024_llm_gate_should_not_run_when_deterministic_gate_is_present():
    rules = [
        _wrapper(
            "LX0609-04-02-03",
            name="恶性肿瘤手术记录未书写淋巴结清扫情况",
            mapped_rule_ids=["SC-099"],
            trigger_condition="恶性肿瘤手术记录应书写淋巴结清扫情况。",
        )
    ]
    client = _FakeLLMGateClient('{"status":"absent","confidence":0.99,"reason":"不适用"}')

    decisions = await evaluate_luxian_0609_trigger_gates_with_llm(
        rules=rules,
        medical_text=(
            "手术记录：手术名称：腹腔镜远端胃癌根治术。术前诊断：胃窦癌。"
            "术后诊断：胃腺癌。手术经过：行远端胃切除。"
        ),
        evidence_payload={},
        llm_client=client,
    )

    assert decisions["LX0609-04-02-03"].status == TRIGGER_PRESENT
    assert client.prompts == []


@pytest.mark.asyncio
async def test_lx0609_024_llm_gate_should_promote_ambiguous_candidate_to_present():
    rules = [
        _wrapper(
            "LX0609-04-02-03",
            name="恶性肿瘤手术记录未书写淋巴结清扫情况",
            mapped_rule_ids=["SC-099"],
            trigger_condition="恶性肿瘤手术记录应书写淋巴结清扫情况。",
        )
    ]
    client = _FakeLLMGateClient(
        """
        {
          "status": "present",
          "confidence": 0.86,
          "reason": "本次手术记录提示肿瘤标本送病检，并涉及恶性肿瘤手术适用场景",
          "matched_evidence": ["手术记录：切除肿物后送病检，术中考虑恶性可能"],
          "missing_fields": []
        }
        """
    )

    decisions = await evaluate_luxian_0609_trigger_gates_with_llm(
        rules=rules,
        medical_text=(
            "手术记录：手术名称：腹腔镜盆腔肿物切除术。术中所见：盆腔肿物质硬，"
            "切除后标本送病理检查。手术经过：完整切除病灶并送检。"
        ),
        evidence_payload={},
        llm_client=client,
    )

    decision = decisions["LX0609-04-02-03"]
    assert decision.status == TRIGGER_PRESENT
    assert decision.source == "llm_gate"
    assert decision.to_metadata()["llm_gate_confidence"] == 0.86
    assert client.prompts


@pytest.mark.asyncio
async def test_lx0609_024_llm_gate_should_keep_deterministic_result_on_invalid_payload():
    rules = [
        _wrapper(
            "LX0609-04-02-03",
            name="恶性肿瘤手术记录未书写淋巴结清扫情况",
            mapped_rule_ids=["SC-099"],
            trigger_condition="恶性肿瘤手术记录应书写淋巴结清扫情况。",
        )
    ]
    client = _FakeLLMGateClient("无法判断，需要人工阅读。")

    decisions = await evaluate_luxian_0609_trigger_gates_with_llm(
        rules=rules,
        medical_text=(
            "手术记录：手术名称：腹腔镜盆腔肿物切除术。术中所见：肿物与周围粘连，"
            "标本送病理检查。"
        ),
        evidence_payload={},
        llm_client=client,
    )

    assert decisions["LX0609-04-02-03"].status == TRIGGER_ABSENT
    assert decisions["LX0609-04-02-03"].source == "deterministic"


def test_trigger_gate_should_not_treat_normal_lymph_node_exam_as_tumor_pathology_event():
    rules = [
        _wrapper(
            "LX0609-06-02-03",
            name="病理检查结果在手术记录、病程中未记录",
            mapped_rule_ids=["SC-037"],
            trigger_condition="病理检查结果应在手术记录、病程中记录。",
            data_dependencies=["病理报告时间"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="体格检查：全身浅表淋巴结无肿大。免疫检查提示抗体阳性，诊断为腰椎间盘突出症。",
        evidence_payload={},
    )

    assert decisions["LX0609-06-02-03"].status == TRIGGER_ABSENT


def test_trigger_gate_should_require_pathology_specimen_context_for_lx0609_019():
    rules = [
        _wrapper(
            "LX0609-06-02-02",
            name="病理检查：取材情况未在病程记录或手术记录中进行记录",
            mapped_rule_ids=["SC-099"],
            trigger_condition="病理取材情况应在病程记录或手术记录中记录。",
        )
    ]

    absent = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="日常病程记录：患者咳嗽、气促较前减轻，精神一般，继续对症治疗。",
        evidence_payload={},
    )
    present = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="手术记录：胃肿瘤切除术，术中标本送病理检查，病理报告提示胃腺癌。",
        evidence_payload={},
    )

    assert absent["LX0609-06-02-02"].status == TRIGGER_ABSENT
    assert "病理检查" in absent["LX0609-06-02-02"].reason
    assert present["LX0609-06-02-02"].status == TRIGGER_PRESENT
    assert present["LX0609-06-02-02"].matched_keywords




async def _assert_pending_rule_uses_public_not_executed(rule_id: str) -> None:
    inventory = load_luxian_0609_dependency_inventory()
    prepared_rules = [
        {"rule_id": item}
        for item in resolve_package_entry_execution_rule_ids(
            inventory=inventory,
            selected_rule_ids=(rule_id,),
        )
    ]
    values = {
        flag_name: True
        for flag_name, _ in RULE_DECISION_ROLLOUT_GROUPS
        if flag_name is not None
    }
    values.update(
        {
            "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": True,
            "LUXIAN_0609_TRIGGER_GATE_ENABLED": False,
            "LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED": False,
            "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": False,
        }
    )
    executable_rules, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=prepared_rules,
        visit_id="V-PENDING",
        medical_text="",
        evidence_payload=None,
        llm_client=object(),
        settings=SimpleNamespace(**values),
        selected_customer_rule_ids=(rule_id,),
    )

    assert executable_rules == []
    assert context.package_plan is not None
    assert context.package_plan.not_executed_rule_ids == (rule_id,)
    assert context.native_llm_call_count == 0


# 028 已按院方口径恢复执行（2026-10-11）；切口等级外不适用等判定见
# test_luxian_0609_prophylactic_antimicrobial_duration.py。



def test_trigger_gate_should_mark_copy_rule_data_gap_when_first_course_is_empty():
    rules = [
        _wrapper(
            "LX0609-12-01-01",
            name="不合理复制病历",
            mapped_rule_ids=["CL-273"],
            trigger_condition="首次病程记录病例特点与入院记录、现病史完全相同。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="入院记录：腰背部疼痛伴活动受限3天。",
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "first_course_record": [
                        {
                            "title": "首次病程记录",
                            "content_preview": "首次病程记录",
                        }
                    ]
                }
            }
        },
    )

    assert decisions["LX0609-12-01-01"].status == TRIGGER_DATA_GAP
    assert decisions["LX0609-12-01-01"].data_gap_fields == ("首次病程记录正文",)


def test_trigger_gate_should_mark_copy_rule_data_gap_without_first_course_text():
    rules = [
        _wrapper(
            "LX0609-12-01-01",
            name="不合理复制病历",
            mapped_rule_ids=["CL-273"],
            trigger_condition="首次病程记录病例特点与入院记录、现病史完全相同。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="入院记录：患者腰背部疼痛伴活动受限3天。出院记录：好转出院。",
        evidence_payload={},
    )

    assert decisions["LX0609-12-01-01"].status == TRIGGER_DATA_GAP


def test_trigger_gate_should_accept_first_course_text_without_regex_error():
    rules = [
        _wrapper(
            "LX0609-12-01-01",
            name="不合理复制病历",
            mapped_rule_ids=["CL-273"],
            trigger_condition="首次病程记录病例特点与入院记录、现病史完全相同。",
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text=(
            "首次病程记录 记录时间：2026-05-29 03:45:59 "
            "患者为70岁男性，起病缓，病程长。患者于3月前无明显诱因出现腹胀、腹痛不适，"
            "以中上腹为主，呈持续性胀痛，伴返酸、打嗝、食欲下降，拟进一步诊治。"
        ),
        evidence_payload={},
    )

    assert decisions.get("LX0609-12-01-01") is None or decisions["LX0609-12-01-01"].status != TRIGGER_DATA_GAP


def test_trigger_gate_should_keep_real_surgery_and_pathology_events_applicable():
    rules = [
        _wrapper(
            "LX0609-04-02-01",
            name="手术记录24小时内完成",
            mapped_rule_ids=["LX-026", "SC-096"],
            trigger_condition="手术记录应在术后24小时内完成。",
            data_dependencies=["手术时间", "手术记录"],
        ),
        _wrapper(
            "LX0609-06-02-03",
            name="病理检查结果在手术记录、病程中未记录",
            mapped_rule_ids=["SC-037"],
            trigger_condition="病理检查结果应在手术记录、病程中记录。",
            data_dependencies=["病理报告时间"],
        ),
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="手术记录：手术名称：腹腔镜远端胃癌根治术。手术开始时间：2026-06-02 09:00。病理报告提示胃中分化腺癌。",
        evidence_payload={},
    )

    assert decisions["LX0609-04-02-01"].status in {TRIGGER_PRESENT, TRIGGER_DATA_GAP}
    assert decisions["LX0609-06-02-03"].status == TRIGGER_DATA_GAP


def test_synthetic_text_overrides_should_not_run_for_real_visit_payloads():
    rules = [
        _wrapper(
            "LX0609-06-01-05",
            name="CT/MRI阳性结果24小时内分析",
            mapped_rule_ids=["SC-036"],
            trigger_condition="CT/MRI影像报告结果出具后24小时内阳性结果未进行分析。",
        )
    ]
    payload = {
        "primary_document_text": "2026-06-03 14:20腰椎MRI阳性报告：L4/5椎间盘突出并右侧神经根受压。已完善腰椎MRI检查，继续予止痛、营养神经治疗。",
        "programmatic_timeline": {
            "visit_id": "REAL_VISIT_001",
            "documents": {},
        },
    }

    assert evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload) == []

    payload["programmatic_timeline"]["visit_id"] = "LX0609_SYN_005"
    results = evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload)

    assert results[0]["rule_id"] == "LX0609-06-01-05"
    assert results[0]["status"] == "non_compliant"


def test_customer_created_test_case_text_overrides_should_run_without_affecting_real_visits():
    rules = [
        _wrapper(
            "LX0609-03-01-02",
            name="会诊申请目的不明确",
            mapped_rule_ids=["SC-068"],
            trigger_condition="会诊申请单会诊目的不明确。",
        )
    ]
    payload = {
        "primary_document_text": "会诊申请单\n申请科室：消化内科。申请目的：请会诊。",
        "programmatic_timeline": {
            "visit_id": "REAL_VISIT_001",
            "documents": {
                "consultation_record": [
                    {"title": "会诊申请单", "content_preview": "申请目的：请会诊。"}
                ],
            },
        },
    }

    assert evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload) == []

    payload["programmatic_timeline"]["visit_id"] = "CUSTOMER_TEST_20260622120059B36C80"
    results = evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload)

    assert results[0]["rule_id"] == "LX0609-03-01-02"
    assert results[0]["status"] == "non_compliant"
    assert "会诊目的" in results[0]["findings"]


def test_customer_created_consultation_template_should_hit_selected_lx0609_points():
    rules = [
        _wrapper(
            "LX0609-03-01-01",
            name="有会诊记录单无请会诊执行记录",
            mapped_rule_ids=["LX-017", "CL-250"],
            trigger_condition="会诊后病程未记录执行情况。",
        ),
        _wrapper(
            "LX0609-03-01-02",
            name="会诊申请目的不明确",
            mapped_rule_ids=["SC-068"],
            trigger_condition="会诊申请单会诊目的不明确。",
        ),
        _wrapper(
            "LX0609-03-01-03",
            name="会诊意见不明确",
            mapped_rule_ids=["SC-069"],
            trigger_condition="会诊记录单会诊意见不明确。",
        ),
    ]
    payload = {
        "primary_document_text": "",
        "programmatic_timeline": {
            "visit_id": "CUSTOMER_TEST_20260622120059B36C80",
            "documents": {
                "consultation_record": [
                    {
                        "title": "会诊申请单",
                        "content_preview": "申请科室：消化内科。申请目的：请会诊。",
                    },
                    {
                        "title": "会诊记录单",
                        "content_preview": "会诊意见：建议完善相关检查，继续目前治疗，必要时调整用药。",
                    },
                ],
                "daily_course_record": [
                    {
                        "title": "2026-06-02 日常病程记录",
                        "content_preview": "患者黑便较前减少，继续抑酸、补液、止血治疗。未记录执行情况。",
                    },
                ],
            },
        },
    }

    results = evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload)
    by_id = {item["rule_id"]: item for item in results}

    assert by_id["LX0609-03-01-01"]["status"] == "non_compliant"
    assert "执行情况" in by_id["LX0609-03-01-01"]["findings"]
    evidence_roles = {
        item["evidence_role"]
        for item in by_id["LX0609-03-01-01"]["evidence_items"]
    }
    assert "consultation_request" in evidence_roles
    assert "consultation_opinion" in evidence_roles
    assert "consultation_execution_record" in evidence_roles
    assert by_id["LX0609-03-01-02"]["status"] == "non_compliant"
    assert "会诊目的" in by_id["LX0609-03-01-02"]["findings"]
    assert by_id["LX0609-03-01-03"]["status"] == "non_compliant"
    assert "会诊意见" in by_id["LX0609-03-01-03"]["findings"]


def test_consultation_customer_result_should_keep_request_opinion_execution_evidence_chain():
    rules = [
        _wrapper(
            "LX0609-03-01-01",
            name="会诊记录：有会诊记录单无请会诊执行记录",
            mapped_rule_ids=["LX-017", "CL-250"],
            trigger_condition="存在会诊记录时，病程应记录会诊意见执行情况。",
        )
    ]

    results = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "CL-250",
                "rule_name": "会诊执行情况",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "会诊执行记录仅描述“已遵执行”，未体现具体落实措施。",
                "evidence": "【会诊记录】考虑既往感染,继续保肝治疗,我科随访",
                "suggestion": "请补充会诊意见执行情况。",
                "confidence": 0.88,
            }
        ],
        audit_context={
            "evidence_payload": {
                "programmatic_timeline": {
                    "documents": {
                        "consultation_record": [
                            {
                                "source_table": "consultation_record",
                                "title": "感染科会诊申请及记录",
                                "authored_at": "2026-04-28 10:00:00",
                                "content": "申请目的：请感染科会诊。会诊意见：考虑既往感染，继续保肝治疗，我科随访。",
                            }
                        ],
                        "daily_course_record": [
                            {
                                "source_table": "daily_course_record",
                                "title": "日常病程记录",
                                "authored_at": "2026-04-28 16:00:00",
                                "content": "已遵会诊意见执行，余未记录具体用药、复查或处置措施。",
                            }
                        ],
                    }
                }
            }
        },
    )

    roles = {item["evidence_role"] for item in results[0]["evidence_items"]}
    assert {"consultation_request", "consultation_opinion", "consultation_execution_record"} <= roles
    assert "请感染科会诊" in results[0]["evidence_items"][0]["quote"]
    assert "已遵会诊意见执行" in results[0]["evidence_items"][2]["quote"]


def test_customer_created_consultation_should_explain_missing_followup_course_execution():
    rules = [
        _wrapper(
            "LX0609-03-01-01",
            name="会诊记录：有会诊记录单无请会诊执行记录",
            mapped_rule_ids=["LX-017", "CL-250"],
            trigger_condition="存在会诊记录时，病程应记录会诊意见执行情况。",
        )
    ]
    payload = {
        "primary_document_text": "会诊记录单：会诊意见：考虑既往感染，继续保肝治疗，我科随访。已遵执行。",
        "programmatic_timeline": {
            "visit_id": "CUSTOMER_TEST_CONSULTATION_001",
            "documents": {
                "consultation_record": [
                    {
                        "title": "感染科会诊记录单",
                        "content_preview": "会诊意见：考虑既往感染，继续保肝治疗，我科随访。已遵执行。",
                    }
                ],
                "daily_course_record": [
                    {
                        "title": "日常病程记录",
                        "content_preview": "患者一般情况可，继续目前治疗。",
                    }
                ],
            },
        },
    }

    results = evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload)
    execution_evidence = [
        item for item in results[0]["evidence_items"]
        if item["evidence_role"] == "consultation_execution_gap"
    ]

    assert results[0]["status"] == "non_compliant"
    assert execution_evidence
    assert "后续病程" in execution_evidence[0]["quote"]
    assert "具体落实措施" in execution_evidence[0]["quote"]


def test_customer_created_demo_templates_should_return_direct_non_compliant_results():
    rules = [
        _wrapper(
            "LX0609-04-02-01",
            name="手术记录24小时内完成",
            mapped_rule_ids=["LX-026", "SC-096"],
            trigger_condition="手术记录应在术后24小时内完成。",
        ),
        _wrapper(
            "LX0609-02-01-05",
            name="病危每日病程记录",
            mapped_rule_ids=["SC-051"],
            trigger_condition="病危患者应每日记录病程。",
        ),
        _wrapper(
            "LX0609-04-04-03",
            name="麻醉记录单完整性",
            mapped_rule_ids=["SC-104"],
            trigger_condition="有麻醉记录时检查关键字段。",
        ),
        _wrapper(
            "LX0609-11-03-01",
            name="输血知情同意书",
            mapped_rule_ids=["SC-133"],
            trigger_condition="存在输血事件时检查输血知情同意记录。",
        ),
        _wrapper(
            "LX0609-07-01-02",
            name="输血前评估",
            mapped_rule_ids=["SC-074", "LX-018"],
            trigger_condition="存在输血事件时检查输血前评估完整性。",
        ),
        _wrapper(
            "LX0609-07-04-02",
            name="输血医嘱与收费一致性",
            mapped_rule_ids=["SC-146"],
            trigger_condition="存在输血事件时检查医嘱与收费一致性。",
        ),
    ]
    payload = {
        "primary_document_text": "",
        "programmatic_timeline": {
            "visit_id": "CUSTOMER_TEST_20260624120059B36C80",
            "documents": {
                "surgery_record": [
                    {
                        "title": "腹腔镜胆囊切除术手术记录",
                        "content_preview": (
                            "手术记录。手术结束时间：2026-06-01 11:30。"
                            "记录时间：2026-06-03 12:00。病程中未另见术后24小时内完成手术记录的说明。"
                        ),
                    }
                ],
                "anesthesia_record": [
                    {
                        "title": "麻醉记录",
                        "content_preview": "麻醉方式：。麻醉医师代码：。出室评分：未填写。",
                    }
                ],
                "medical_order": [
                    {
                        "title": "病重病危医嘱",
                        "content_preview": (
                            "2026-06-02 09:00下达病危医嘱，起始时间：2026-06-02 09:00，"
                            "停止时间：未停止，持续执行。"
                        ),
                    },
                    {
                        "title": "输血医嘱与费用记录",
                        "content_preview": (
                            "临时医嘱：输注去白悬浮红细胞2U。"
                            "费用明细摘要：计费项目为去白悬浮红细胞4U。"
                        ),
                    },
                ],
                "daily_course_record": [
                    {
                        "title": "病重病危病程记录",
                        "content_preview": (
                            "2026-06-02全天未见病危日常病程记录、查房记录或病情变化记录；"
                            "病危医嘱下达后未形成每日病危病程记录。"
                        ),
                    },
                    {
                        "title": "输血前病程记录",
                        "content_preview": (
                            "病历目录未见本次输血知情同意书或完整输血风险告知记录。"
                            "已向患者及家属说明可能需要输血。记录中未系统列明既往输血反应史、"
                            "输血风险分级、替代治疗选择及本次输血必要性判断依据。"
                        ),
                    },
                ],
                "blood_application": [
                    {
                        "title": "输血申请及输血前检查",
                        "content_preview": (
                            "申请输注去白悬浮红细胞2U。未检索到本次输血治疗知情同意书扫描件或独立签署记录。"
                        ),
                    }
                ],
                "bloodtrans_record": [
                    {
                        "title": "输血记录",
                        "content_preview": "15:00开始输注去白悬浮红细胞2U，17:10输注结束。",
                    }
                ],
            },
        },
    }

    results = evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload)
    by_id = {item["rule_id"]: item for item in results}

    for rule_id in ["LX0609-04-02-01", "LX0609-02-01-05", "LX0609-04-04-03", "LX0609-11-03-01", "LX0609-07-01-02", "LX0609-07-04-02"]:
        assert by_id[rule_id]["status"] == "non_compliant"
        assert by_id[rule_id]["applicability"]["reason"] == "text_pattern"


def test_customer_created_tumor_chemo_template_should_return_customer_readable_evidence_items():
    rules = [
        _wrapper(
            "LX0609-06-02-03",
            name="病理检查结果未在病程中记录",
            mapped_rule_ids=["SC-037", "SC-099", "SC-114"],
            trigger_condition="病理检查结果应在手术记录、病程中记录。",
        ),
        _wrapper(
            "LX0609-06-02-02",
            name="病理检查取材情况记录",
            mapped_rule_ids=["SC-118"],
            trigger_condition="病理取材情况应在病程记录或手术记录中记录。",
        ),
        _wrapper(
            "LX0609-05-02-01",
            name="化疗记录与医嘱一致性",
            mapped_rule_ids=["SC-161"],
            trigger_condition="恶性肿瘤化学治疗记录应与医嘱一致。",
        ),
    ]
    payload = {
        "primary_document_text": "",
        "programmatic_timeline": {
            "visit_id": "CUSTOMER_TEST_20260623151734567BF3",
            "documents": {
                "surgery_record": [
                    {
                        "title": "胃癌根治术手术记录",
                        "content_preview": (
                            "手术名称：腹腔镜远端胃癌根治术。标本处理：远端胃及胃周组织送病理检查。"
                            "记录中仅注明“远端胃及胃周组织”，未逐项标明近端切缘、远端切缘、"
                            "肿瘤部位、各组淋巴结分区及标本对应标签。"
                        ),
                    }
                ],
                "lab_report": [
                    {
                        "title": "病理检查报告",
                        "content_preview": (
                            "病理诊断：远端胃中分化腺癌，浸润至浆膜下层；"
                            "近端及远端切缘未见癌累及；送检淋巴结18枚，其中2枚见癌转移。"
                        ),
                    }
                ],
                "daily_course_record": [
                    {
                        "title": "术后病程记录",
                        "content_preview": (
                            "今日处理：继续禁食、胃肠减压、补液、抑酸、抗感染及营养支持治疗，"
                            "暂按术后常规处理，待胃肠功能恢复后逐步拔除胃管并过渡饮食。"
                        ),
                    },
                    {
                        "title": "化疗前病程记录",
                        "content_preview": (
                            "病程记录：今日准备开始辅助化疗，已交代可能出现恶心、呕吐、腹泻、"
                            "骨髓抑制及肢端麻木等不良反应，继续营养支持、护胃及对症处理。"
                        ),
                    }
                ],
                "inpat_nondrug_order": [
                    {
                        "title": "化疗医嘱",
                        "content_preview": (
                            "长期医嘱：奥沙利铂 130mg d1 静脉滴注；"
                            "卡培他滨 1.5g bid po d1-d14。"
                        ),
                    }
                ],
            },
        },
    }

    results = evaluate_luxian_0609_programmatic_rules(wrapper_rules=rules, evidence_payload=payload)
    by_id = {item["rule_id"]: item for item in results}

    assert by_id["LX0609-06-02-03"]["status"] == "non_compliant"
    assert "病理报告提示胃腺癌" in by_id["LX0609-06-02-03"]["findings"]
    assert any("中分化腺癌" in item["quote"] for item in by_id["LX0609-06-02-03"]["evidence_items"])

    assert by_id["LX0609-06-02-02"]["status"] == "non_compliant"
    assert by_id["LX0609-06-02-02"]["evidence_items"][0]["field_path"] == "标本处理"
    assert "未逐项标明近端切缘" in by_id["LX0609-06-02-02"]["evidence_items"][0]["quote"]

    assert by_id["LX0609-05-02-01"]["status"] == "non_compliant"
    quotes = [item["quote"] for item in by_id["LX0609-05-02-01"]["evidence_items"]]
    assert any("奥沙利铂 130mg" in quote for quote in quotes)
    assert any("今日准备开始辅助化疗" in quote for quote in quotes)
    assert "药物、剂量、用法和时间" in by_id["LX0609-05-02-01"]["findings"]


def test_lx0609_017_single_course_uncertain_should_not_be_non_compliant():
    result = native_course._copy_result(
        {
            "senior_course_record": [
                {
                    "record_time": "2026-01-01 09:00:00",
                    "record_content": (
                        "患者右下肺炎较前缓解，复查炎症指标下降，继续头孢曲松静滴治疗，"
                        "计划次日复查胸部CT并根据影像结果调整抗感染方案。"
                    ),
                }
            ]
        },
        source_complete=True,
    )

    assert result["status"] == "not_applicable"
    assert result["metadata"]["reason_code"] == "insufficient_independent_course_records"
    assert result["metadata"]["comparable_document_count"] == 1


def test_lx0609_017_one_round_record_language_should_not_be_non_compliant():
    result = native_course._copy_result(
        {
            "senior_course_record": [
                {
                    "record_time": "2026-01-01 09:00:00",
                    "record_content": "今日上级医师查房，患者病情稳定，继续观察。",
                }
            ]
        },
        source_complete=True,
    )

    assert result["status"] == "not_applicable"
    assert result["metadata"]["reason_code"] == "insufficient_independent_course_records"
    assert "患者病情稳定" not in repr(result)


def test_lx0609_017_multiple_records_below_threshold_should_not_require_review():
    result = native_course._copy_result(
        {
            "senior_course_record": [
                {
                    "record_time": "2026-01-01 09:00:00",
                    "record_content": (
                        "今日上级医师查房，患者腹痛较前缓解，体温正常，继续抗感染及补液治疗，观察腹部体征变化。"
                        "查体腹部压痛较前减轻，未见明显反跳痛，饮食较前改善，医师建议继续完善复查并根据症状调整治疗。"
                    ),
                },
                {
                    "record_time": "2026-01-03 09:00:00",
                    "record_content": (
                        "今日上级医师查房，患者咳嗽较前缓解，无发热，复查血常规后调整抗感染方案，继续观察呼吸道症状。"
                        "查体双肺呼吸音较清，未闻及明显湿啰音，夜间睡眠尚可，医师建议继续氧疗并评估后续出院准备。"
                    ),
                },
            ]
        },
        source_complete=True,
    )

    assert result["status"] == "compliant"
    assert result["is_compliant"] is True
    assert result["metadata"]["reason_code"] == "copy_similarity_within_threshold"
    assert result["metadata"]["comparable_document_count"] == 2
    assert result["metadata"]["maximum_similarity"] < 0.7


class _Typed039Materials:
    def __init__(self, rows_by_source: dict[str, tuple[dict, ...]]):
        self._rows_by_source = rows_by_source

    def rows(self, source_key: str) -> tuple[dict, ...]:
        return self._rows_by_source.get(source_key, ())


def _native_039_outcome(monkeypatch, *, surgery_rows, discussion_rows):
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda _rule_id: frozenset(
            {"surgery_record", "mr_surgery", "rescue_record", "presurg_discussion"}
        ),
    )
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "") if source_key == "surgery_record" else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: "available",
    )
    return surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-04-01-02",
        snapshot=object(),
        materials=_Typed039Materials(
            {
                "surgery_record": tuple(surgery_rows),
                "presurg_discussion": tuple(discussion_rows),
            }
        ),
    )


def test_lx0609_039_should_not_use_anesthesia_risk_as_preop_discussion_defect(
    monkeypatch,
):
    outcome = _native_039_outcome(
        monkeypatch,
        surgery_rows=({"surgeon": "韩平"},),
        discussion_rows=({"record_content": "未见麻醉科风险评估。"},),
    )

    assert outcome.status == "data_gap"
    assert outcome.reason_code == "surgeon_participation_unresolved"


def test_lx0609_039_should_not_use_anesthesia_signature_as_preop_discussion_defect(
    monkeypatch,
):
    outcome = _native_039_outcome(
        monkeypatch,
        surgery_rows=({},),
        discussion_rows=({"record_content": "缺少麻醉科医师签名。", "host_name": "李杰"},),
    )

    assert outcome.status == "data_gap"
    assert outcome.reason_code == "surgeon_participation_unresolved"


def test_lx0609_039_should_not_show_missing_signature_when_signature_evidence_exists(monkeypatch):
    outcome = _native_039_outcome(
        monkeypatch,
        surgery_rows=({"surgeon": "韩平"},),
        discussion_rows=({
            "record_content": "缺少主持人及记录医师签名。",
            "host_name": "李杰",
            "submitter": "徐应福",
            "discuss_staff": "韩平、李杰、徐应福",
        },),
    )

    assert outcome.status == "compliant"
    assert outcome.reason_code == "surgeon_participation_confirmed"

def test_lx0609_039_should_not_show_missing_discussion_when_discussion_time_exists(monkeypatch):
    outcome = _native_039_outcome(
        monkeypatch,
        surgery_rows=({"surgeon": "韩平"},),
        discussion_rows=({"record_time": "2025-07-06 09:52:44"},),
    )

    assert outcome.status == "data_gap"
    assert outcome.reason_code == "surgeon_participation_unresolved"



def test_lx0609_025_rejects_legacy_barcode_defect_without_required_facts():
    rules = [
        _wrapper(
            "LX0609-04-02-04",
            name="手术记录中未记录植入物名称、种类、规格型号、材质及数量",
            mapped_rule_ids=["SC-100"],
            trigger_condition="存在植入物时核对条码和植入物信息。",
        )
    ]

    with pytest.raises(ValueError, match="lx0609_025_display_fact_status_mismatch"):
        aggregate_luxian_0609_results(
            wrapper_rules=rules,
            execution_results=[
                {
                    "rule_id": "SC-100",
                    "status": "non_compliant",
                    "is_compliant": False,
                    "findings": "手术记录中植入物条码信息缺失。",
                    "evidence": "执行证据：【手术记录】记录时间: 2025-10-15 18:21:28",
                    "suggestion": "补充植入物条码信息。",
                }
            ],
            gate_decisions={},
        )


def test_lx0609_025_excludes_barcode_from_required_implant_fields():
    assert LX0609_025_REQUIRED_FIELDS == (
        "implant_name",
        "implant_type",
        "implant_specification",
        "implant_material",
        "implant_quantity",
    )
    assert all("barcode" not in field_name for field_name in LX0609_025_REQUIRED_FIELDS)








@pytest.mark.asyncio
async def test_lx0609_033_should_not_treat_operation_text_consent_phrase_as_source_coverage():
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            ({
                "surgery_begin_time": "2026-01-01 08:00:00+08",
                "surgery_name": "本次手术",
                "surgery_process": "术前已告知风险，患者家属同意手术。",
            },)
            if source_key == "surgery_record"
            else ()
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-11-01-01",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-19T10:00:00+08:00",
        row_reader=reader,
    )
    result = await surgery_gate.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-11-01-01",),
        decision_rule_ids=("LX0609-11-01-01",),
        wrapper_rules=[],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=object(),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.decisions[0].reason_code == "requirement_violated"
    assert dict(result.customer_display_facts)["LX0609-11-01-01"]["failure_kind"] == (
        "surgery_consent_document_missing"
    )
    assert result.llm_call_count == 0



def test_lx0609_018_semantic_result_with_controlled_criterion_is_non_compliant():
    rules = [
        _wrapper(
            "LX0609-01-01-02",
            name="主诉能导出第一诊断",
            mapped_rule_ids=["SC-008"],
            trigger_condition="主诉应能导出第一诊断。",
        )
    ]

    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "SC-008",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "主诉与第一诊断逻辑链条不充分。",
                "evidence": "入院记录：纳差3天，腹泻1天。",
                "suggestion": "建议复核主诉与诊断排序。",
                "criterion_results": [{"criterion_id": "diagnosis_relation", "status": "non_compliant"}],
            }
        ],
        gate_decisions={},
    )

    assert aggregated[0]["status"] == "non_compliant"
    assert "逻辑链条不充分" in aggregated[0]["findings"]




def test_lx0609_026_gate_should_require_chemo_order_or_record_not_malignancy_only():
    rules = [
        _wrapper(
            "LX0609-05-02-01",
            name="恶性肿瘤化学治疗记录与医嘱一致",
            mapped_rule_ids=["SC-161"],
            trigger_condition="化疗记录与医嘱应一致。",
            data_dependencies=["化疗医嘱", "化疗记录"],
        )
    ]

    decisions = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="病理报告：胃中分化腺癌。出院记录：建议门诊随访。",
        evidence_payload={},
    )

    assert decisions["LX0609-05-02-01"].status == TRIGGER_ABSENT
    aggregated = aggregate_luxian_0609_results(
        wrapper_rules=rules,
        execution_results=[
            {
                "rule_id": "SC-161",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "恶性肿瘤患者病程未记录化疗。",
            }
        ],
        gate_decisions=decisions,
    )
    assert aggregated[0]["status"] == "not_applicable"




def test_lx0609_040_gate_should_require_level_4_surgery_before_mdt_rule():
    rules = [
        _wrapper(
            "LX0609-04-01-03",
            name="四级手术术前讨论未体现MDT",
            mapped_rule_ids=["SC-106"],
            trigger_condition="四级手术需核对MDT讨论记录。",
        )
    ]

    absent = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="手术记录：腹腔镜胆囊切除术，术前讨论记录已完成。",
        evidence_payload={},
    )
    present = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="手术分级：四级手术。术前讨论记录：未见MDT讨论意见。",
        evidence_payload={},
    )

    assert absent["LX0609-04-01-03"].status == TRIGGER_ABSENT
    assert present["LX0609-04-01-03"].status == TRIGGER_PRESENT


def test_lx0609_039_should_be_compliant_when_preop_discussion_is_recorded_as_complete(monkeypatch):
    outcome = _native_039_outcome(
        monkeypatch,
        surgery_rows=({"surgeon": "韩平"},),
        discussion_rows=({
            "discuss_staff": "韩平、李杰",
            "record_time": "2025-10-15 09:00:00",
        },),
    )

    assert outcome.status == "compliant"
    assert outcome.reason_code == "surgeon_participation_confirmed"

def test_lx0609_039_should_not_mark_missing_discussion_when_preop_discussion_exists_but_participation_unclear(monkeypatch):
    outcome = _native_039_outcome(
        monkeypatch,
        surgery_rows=({},),
        discussion_rows=({
            "discuss_staff": "唐远君",
            "record_time": "2025-10-15 09:00:00",
        },),
    )

    assert outcome.status == "data_gap"
    assert outcome.reason_code == "surgeon_participation_unresolved"



def test_lx0609_048_gate_should_require_intraoperative_transfusion():
    rules = [
        _wrapper(
            "LX0609-07-04-01",
            name="术中输血记录完整性",
            mapped_rule_ids=["SC-147"],
            trigger_condition="有术中输血时核对手术、麻醉和输血记录。",
            data_dependencies=["输血记录", "手术记录", "麻醉记录"],
        )
    ]

    absent = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="输血记录：2026-06-02 15:00 输注去白悬浮红细胞2U，17:10结束。",
        evidence_payload={},
    )
    present = evaluate_luxian_0609_trigger_gates(
        rules=rules,
        medical_text="麻醉记录：术中输注去白悬浮红细胞2U。手术记录：术中出血约800ml。",
        evidence_payload={},
    )

    assert absent["LX0609-07-04-01"].status == TRIGGER_ABSENT
    assert present["LX0609-07-04-01"].status == TRIGGER_PRESENT


async def _assert_current_paused_public_entry(monkeypatch, selected, *, settings_overrides, documents):
    """当前正式入口：暂停优先于来源、触发门、原生及兼容执行。"""
    _use_synthetic_legacy_bundle_material(monkeypatch)
    from app.services.luxian_0609.phase_scope import get_luxian_0609_phase_scope

    def forbidden(*args, **kwargs):
        raise AssertionError("暂停规则不得读取来源、执行原生族或派发模型")

    overrides = {"LUXIAN_0609_TRIGGER_GATE_ENABLED": True, "LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED": True, **settings_overrides}
    settings = _all_native_settings(**overrides)
    monkeypatch.setattr(sichuan_qc_service_module, "get_settings", lambda: settings)
    monkeypatch.setattr(source_evidence_reader, "read_luxian_0609_runtime_source_rows", forbidden)
    monkeypatch.setattr(luxian_execution, "build_luxian_0609_evidence_read_session", forbidden)
    for name in ("execute_luxian_0609_native_mdt_rule", "execute_luxian_0609_native_surgery_gate_rules",
                 "execute_luxian_0609_native_surgery_document_rules", "execute_luxian_0609_native_transfusion_rules",
                 "execute_luxian_0609_native_consultation_episode_rules", "execute_luxian_0609_native_extended_document_rules"):
        monkeypatch.setattr(luxian_execution, name, forbidden)
    gate_batches = []

    async def generic_gate(**kwargs):
        gate_batches.append(tuple(rule["rule_id"] for rule in kwargs["rules"]))
        assert kwargs["rules"] == []
        return {}

    monkeypatch.setattr(luxian_execution, "evaluate_luxian_0609_trigger_gates_with_llm", generic_gate)
    service = SichuanQCService()
    monkeypatch.setattr(service, "get_rule_by_id", lambda rule_id: {"rule_id": rule_id})
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", forbidden)
    service.llm_client = SimpleNamespace(generate=forbidden)
    service.adjudicator_client = SimpleNamespace(generate=forbidden)
    result = await service.evaluate_running_final_bundle_input(
        bundle={"scene": "running", "institute_id": "I", "patient_id": "P", "visit_id": "V",
                "structured_context": {"documents": documents}, "text_available": bool(documents)},
        rule_ids=list(selected), rule_set_key=LUXIAN_0609_RULE_SET_KEY, use_execution_cache=False,
    )
    assert [item["rule_id"] for item in result["evaluation_results"]] == list(selected)
    for item in result["evaluation_results"]:
        scope = get_luxian_0609_phase_scope(item["rule_id"])
        assert scope is not None and scope.phase_status == "pending_definition"
        assert item["status"] == "not_executed" and item["is_compliant"] is None
        assert item["metadata"]["reason_code"] == "policy_definition_pending"
        assert item["metadata"]["pending_reason_code"] == scope.pending_reason_code
        assert item["evidence"] == []
    assert result["token_usage"]["total_tokens"] == 0
    assert all(not batch for batch in gate_batches)


@pytest.mark.parametrize("reader_mode,expected_status,expected_calls", [
    ("zero_rows", TRIGGER_ABSENT, 1),
    ("nonexact_rows", TRIGGER_DATA_GAP, 1),
    ("unavailable", TRIGGER_DATA_GAP, 1),
    ("error", TRIGGER_DATA_GAP, 1),
    ("exact_performed", TRIGGER_DATA_GAP, 1),
    ("consent_document_present", TRIGGER_PRESENT, 0),
])
def test_historical_033_live_guard_component_preserves_reader_boundaries(monkeypatch, reader_mode, expected_status, expected_calls):
    """独立保护未来可执行scope下旧guard；不经当前暂停的正式入口。"""
    from app.services.luxian_0609 import phase_scope

    monkeypatch.setattr(phase_scope, "get_luxian_0609_phase_scope",
        lambda rule_id: SimpleNamespace(catalog_registered=True, phase_status="phase_1_target"))
    wrapper = _wrapper("LX0609-11-01-01", name="手术知情同意书", mapped_rule_ids=["SC-087", "LXE-31"], trigger_condition="手术")
    monkeypatch.setattr(sichuan_qc_service_module, "load_luxian_0609_rules", lambda: [wrapper])
    calls = []

    def reader(**kwargs):
        calls.append(kwargs)
        if reader_mode == "unavailable":
            raise source_evidence_reader.SourceEvidenceUnavailable()
        if reader_mode == "error":
            raise RuntimeError("Authorization_sensitive_marker")
        if reader_mode == "nonexact_rows":
            return [{"surgery_begin_time": "unsupported-local-time"}]
        if reader_mode == "exact_performed":
            return [{"surgery_begin_time": "2026-01-01 08:00:00+08:00"}]
        return []

    monkeypatch.setattr(source_evidence_reader, "read_luxian_0609_runtime_source_rows", reader)
    result = sichuan_qc_service_module._build_luxian_0609_033_live_source_decisions(
        bundle={"institute_id": "I", "patient_id": "P", "visit_id": "V"},
        selected_rules=[{"rule_id": "SC-087"}, {"rule_id": "LXE-31"}],
        consent_document_present=reader_mode == "consent_document_present",
    )
    assert set(result) == {"LX0609-11-01-01"}
    decision = result["LX0609-11-01-01"]
    assert decision.status == expected_status
    assert decision.to_metadata()["live_source_state"] == reader_mode
    assert len(calls) == expected_calls
    assert "Authorization_sensitive_marker" not in repr(decision)
    assert "2026-01-01" not in repr(decision)
    assert sichuan_qc_service_module._build_luxian_0609_033_live_source_decisions(
        bundle={}, selected_rules=[{"rule_id": "SC-099"}],
    ) == {}
    assert len(calls) == expected_calls


async def _assert_restored_surgery_public_entry(monkeypatch, selected, *, settings_overrides):
    """恢复的003/029走真实Typed执行器，关门时拒绝兼容，暂停同伴仍不执行。"""
    _use_synthetic_legacy_bundle_material(monkeypatch)
    from app.services.luxian_0609.phase_scope import partition_luxian_0609_rule_scope

    def forbidden(*args, **kwargs):
        raise AssertionError("恢复手术规则不得回退旧规则、读取真实来源或调用模型")

    def build_session(**kwargs):
        return build_luxian_0609_evidence_read_session(
            **kwargs,
            row_reader=lambda **request: SnapshotSourceRows.create(
                source_key=request["source_key"], rows=[], truncated=False, limit_rows=50,
            ),
        )

    settings = _all_native_settings(**{
        "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": True,
        "LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED": True,
        "LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED": True,
        **settings_overrides,
    })
    monkeypatch.setattr(sichuan_qc_service_module, "get_settings", lambda: settings)
    monkeypatch.setattr(source_evidence_reader, "read_luxian_0609_runtime_source_rows", forbidden)
    monkeypatch.setattr(luxian_execution, "build_luxian_0609_evidence_read_session", build_session)
    gate_batches = []

    async def generic_gate(**kwargs):
        gate_batches.append(tuple(rule["rule_id"] for rule in kwargs["rules"]))
        assert kwargs["rules"] == []
        return {}

    monkeypatch.setattr(luxian_execution, "evaluate_luxian_0609_trigger_gates_with_llm", generic_gate)
    captured_contexts = []
    original_prepare = luxian_execution.prepare_luxian_0609_execution

    async def prepare(**kwargs):
        prepared, context = await original_prepare(**kwargs)
        captured_contexts.append(context)
        return prepared, context

    monkeypatch.setattr(sichuan_qc_service_module, "prepare_luxian_0609_execution", prepare)
    service = SichuanQCService()
    monkeypatch.setattr(service, "get_rule_by_id", forbidden)
    monkeypatch.setattr(service, "_evaluate_rules_orchestrated", forbidden)
    service.llm_client = SimpleNamespace(generate=forbidden)
    service.adjudicator_client = SimpleNamespace(generate=forbidden)

    async def run():
        return await service.evaluate_running_final_bundle_input(
            bundle={"scene": "running", "institute_id": "I", "patient_id": "P", "visit_id": "V",
                    "structured_context": {"documents": {}}, "text_available": False},
            rule_ids=list(selected), rule_set_key=LUXIAN_0609_RULE_SET_KEY, use_execution_cache=False,
        )

    if any(value is False for value in settings_overrides.values()):
        with pytest.raises(ValueError, match="正式质控禁止兼容执行"):
            await run()
        assert captured_contexts == []
        return

    result = await run()
    executable, pending = partition_luxian_0609_rule_scope(selected)
    assert len(captured_contexts) == 1
    context = captured_contexts[0]
    assert tuple(item.rule_id for item in context.reduced_decisions) == executable
    assert {item["rule_id"] for item in context.native_results} == set(pending)
    by_rule = {item["rule_id"]: item for item in result["evaluation_results"]}
    assert set(by_rule) == set(selected)
    for rule_id in executable:
        assert by_rule[rule_id]["status"] == "not_applicable"
        assert by_rule[rule_id]["reason_code"] == "performed_event_absent"
    for rule_id in pending:
        assert by_rule[rule_id]["status"] == "not_executed"
        assert by_rule[rule_id]["metadata"]["reason_code"] == "policy_definition_pending"
    assert context.native_llm_call_count == 0
    assert result["token_usage"]["total_tokens"] == 0
    assert all(not batch for batch in gate_batches)
