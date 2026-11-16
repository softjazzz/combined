"""候选版事件规则暂停：正式门禁、无取材及历史结果隔离。"""

import asyncio
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import execution
from app.services.luxian_0609.phase_scope import (
    frozen_luxian_0609_delivery_scope,
    get_luxian_0609_phase_scope,
    partition_luxian_0609_rule_scope,
)
from app.services.luxian_0609.rule_decision_settings import RULE_DECISION_ROLLOUT_GROUPS
from app.services.luxian_0609_rule_catalog import (
    build_luxian_0609_engine_judgment,
    load_luxian_0609_engine_judgment,
)


# 按逐项验收和来源合同暂停，不能按手术或会诊前缀批量扩展范围。
EVENT_RULE_IDS = tuple("LX0609-" + item for item in (
    "03-01-04",
    "05-01-02", "05-01-05",
    "04-01-02", "04-01-03", "04-01-04", "04-01-05",
    "04-02-02", "04-02-03", "04-02-04", "04-02-05",
    "04-03-01", "04-04-01", "04-04-02", "04-04-03",
    "04-05-01", "04-05-02", "05-01-01",
    "11-01-01", "11-02-01", "11-02-02",
    "07-01-01", "07-01-02", "07-01-03", "07-02-01", "07-02-02",
    "07-03-01", "07-04-01", "07-04-02", "11-03-01", "11-03-02",
))
SPECIFIC_REASONS = {
    "LX0609-03-01-04": "consultation_source_document_unavailable_customer_scope",
    "LX0609-04-02-04": "implant_five_field_real_gold_pending",
    "LX0609-04-04-01": "anesthesia_visit_sources_unavailable_customer_scope",
    "LX0609-04-04-02": "anesthesia_visit_sources_unavailable_customer_scope",
    "LX0609-07-04-02": "charging_source_unavailable_customer_scope",
    "LX0609-05-01-02": "antimicrobial_reason_quote_validation_pending",
    "LX0609-05-01-05": "antimicrobial_reason_quote_validation_pending",
}
NEW_REASON = "event_quality_control_paused_current_release"


@pytest.mark.parametrize("rule_id", EVENT_RULE_IDS)
def test_event_rule_cannot_enter_formal_execution(rule_id):
    executable, paused = partition_luxian_0609_rule_scope((rule_id,))
    assert executable == ()
    assert paused == (rule_id,)
    scope = get_luxian_0609_phase_scope(rule_id)
    assert scope.pending_reason_code == SPECIFIC_REASONS.get(rule_id, NEW_REASON)


@pytest.mark.parametrize("rule_id", ("LX0609-05-01-02", "LX0609-05-01-05"))
def test_antimicrobial_reason_pause_explains_validation_and_preserves_history(rule_id):
    from app.services.luxian_0609.phase_scope import build_luxian_0609_pending_definition_result

    result = build_luxian_0609_pending_definition_result(rule_id)
    assert result["status"] == "not_executed"
    assert result["is_compliant"] is None
    assert result["evidence"] == []
    assert "引文" in result["findings"]
    assert "验收" in result["suggestion"]
    assert "历史结果" in result["suggestion"]
    assert result["metadata"]["pending_reason_code"] == "antimicrobial_reason_quote_validation_pending"


def test_antimicrobial_reason_pause_keeps_other_drug_rules_executable():
    executable, paused = partition_luxian_0609_rule_scope((
        "LX0609-05-01-02", "LX0609-05-01-03", "LX0609-05-01-05", "LX0609-05-01-06",
    ))
    assert executable == ("LX0609-05-01-03", "LX0609-05-01-06")
    assert paused == ("LX0609-05-01-02", "LX0609-05-01-05")


def test_death_consultation_and_other_existing_pauses_are_preserved():
    kept = tuple("LX0609-04-02-" + suffix for suffix in ("06", "08", "09"))
    executable, paused = partition_luxian_0609_rule_scope(kept)
    assert set(executable) == set(kept)
    assert paused == ()
    assert get_luxian_0609_phase_scope("LX0609-08-01-03").pending_reason_code == "frontpage_comparison_policy_pending"
    assert get_luxian_0609_phase_scope("LX0609-03-01-01").pending_reason_code == "consultation_source_document_unavailable_customer_scope"
    assert get_luxian_0609_phase_scope("LX0609-05-03-01").pending_reason_code == "treatment_event_order_course_real_gold_pending"


def test_all_event_rules_return_not_executed_before_material_or_model_access(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("暂停规则不得取材或调用执行器")

    monkeypatch.setattr(execution, "build_luxian_0609_evidence_snapshot", forbidden)
    monkeypatch.setattr(execution, "build_luxian_0609_evidence_read_session", forbidden)
    values = {name: True for name, _ in RULE_DECISION_ROLLOUT_GROUPS if name}
    values.update(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED=True,
    )
    executable, context = asyncio.run(execution.prepare_luxian_0609_execution(
        rule_set_key="luxian_0609_qc_v1", prepared_rules=[], visit_id="synthetic-visit",
        institute_id="synthetic-institute", patient_id="synthetic-patient",
        medical_text="", evidence_payload=None, llm_client=object(),
        settings=SimpleNamespace(**values), selected_customer_rule_ids=EVENT_RULE_IDS,
    ))
    assert executable == []
    assert context.package_plan.executable_rule_ids == ()
    assert context.package_plan.native_executor_batches == ()
    assert context.native_llm_call_count == 0
    assert context.evidence_snapshot is None
    result = execution.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []}, context=context, visit_id="synthetic-visit",
        model_name="unused", evidence_payload=None,
    )
    assert {item["rule_id"] for item in result["results"]} == set(EVENT_RULE_IDS)
    for item in result["results"]:
        assert item["status"] == "not_executed"
        assert item["is_compliant"] is None
        assert item["evidence"] == []
        assert item["metadata"]["pending_reason_code"] == SPECIFIC_REASONS.get(item["rule_id"], NEW_REASON)
        if item["rule_id"] not in SPECIFIC_REASONS:
            assert "按当前版本安排暂未启用" in item["findings"]


def test_rule_page_projects_master_pause_instead_of_old_engine_steps():
    for rule_id in (*EVENT_RULE_IDS, "LX0609-08-01-03"):
        raw = load_luxian_0609_engine_judgment()["rules"][rule_id]
        assert raw.get("withheld") is True
        assert "steps" not in raw
        displayed = build_luxian_0609_engine_judgment(rule_id, decision_authority="program_only")
        assert displayed["withheld"] is True
        assert "trigger" not in displayed


def test_saved_task_scope_is_not_reinterpreted_using_current_pauses():
    saved = {"rule_ids": ["LX0609-07-02-01", "LX0609-04-02-01", "LX0609-05-01-02", "LX0609-05-01-05"], "paused_customer_rule_ids": []}
    assert frozen_luxian_0609_delivery_scope(saved) == ["LX0609-07-02-01", "LX0609-04-02-01", "LX0609-05-01-02", "LX0609-05-01-05"]
    assert saved["paused_customer_rule_ids"] == []


@pytest.mark.parametrize("rule_id", ("LX0609-07-02-01", "LX0609-04-02-01", "LX0609-03-01-04", "LX0609-05-01-02", "LX0609-05-01-05"))
@pytest.mark.parametrize("status,is_compliant", (("compliant", True), ("non_compliant", False)))
def test_saved_event_results_keep_frozen_conclusion_at_read_boundary(rule_id, status, is_compliant):
    from app.services.qc_workspace.canonical_result_store import (
        canonical_envelope_items_are_consistent,
        envelope_item_from_rule_result,
    )

    saved = {
        "rule_id": rule_id, "rule_code": rule_id,
        "status": status, "result_status": status, "display_status": status,
        "is_compliant": is_compliant, "reason_code": "synthetic_historical_reason",
        "conclusion": "历史任务冻结结论", "suggestion": "历史任务冻结建议",
        "evidence": [],
    }
    assert canonical_envelope_items_are_consistent([saved]) is True
    projected = envelope_item_from_rule_result(saved, hmac_key="synthetic-test-key")
    assert projected["status"] == status
    assert projected["is_compliant"] is is_compliant
    assert projected["conclusion"] == "历史任务冻结结论"
    assert projected["suggestion"] == "历史任务冻结建议"
