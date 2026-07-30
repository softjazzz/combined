from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609.native_package import Luxian0609PackagePlan
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY


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
        "LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED": False,
        "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": False,
        "LUXIAN_0609_RULE_DECISION_007_ENABLED": False,
        "LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED": False,
        "LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED": False,
        "LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_snapshot_build_failure_is_distinct_from_missing_snapshot(
    monkeypatch,
) -> None:
    selected = ("LX0609-001",)
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
        raise AssertionError("快照构建失败后不得静默回放旧链")

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
            {
                "rule_id": "LX0609-001",
                "name": "LX0609-001",
                "mapped_rule_ids": ["RAW-LX0609-001"],
                "primary_execution_rule_id": "RAW-LX0609-001",
                "trigger_condition": "test",
                "dependency_type": "单文书",
                "data_dependencies": [],
            }
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
    assert [item["rule_id"] for item in context.native_results] == ["LX0609-001"]
    assert context.native_results[0]["status"] == "technical_error"
    assert (
        context.native_results[0]["metadata"]["reason_code"]
        == "evidence_snapshot_build_failed"
    )
    assert "private failure" not in repr(context.native_results)
