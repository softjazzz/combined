"""危急值合法资料缺口经正式执行/归约/发布/保存后保持资料不足。"""

import json

import pytest

from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows, SourceEvidenceUnavailable,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_published_customer_display_facts,
)

RULES = ("LX0609-06-04-01", "LX0609-06-04-02")


@pytest.fixture(autouse=True)
def no_network_or_non_sqlite(monkeypatch):
    import socket
    import httpx
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def blocked(*args, **kwargs):
        raise AssertionError("危急值合同测试禁止网络调用")

    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite"

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    event.listen(Engine, "before_cursor_execute", sqlite_only)
    yield
    event.remove(Engine, "before_cursor_execute", sqlite_only)


async def evaluate(*, unavailable=(), truncated=(), report_time="2026-10-01 08:00:00",
                   disposition_time="2026-10-01 10:00:00", items=True):
    rows = {
        "labtest_item_report": [{"test_id": "SYN-CV", "item_name": "血钾",
            "abnormal_indicator": "PH", "report_time": report_time}] if items else [],
        "crisis_value_record": [{"test_id": "SYN-CV", "record_time": disposition_time,
            "record_content": "已复查并完成危急值处置。"}] if disposition_time is not False else [],
    }

    def read(**kwargs):
        key = kwargs["source_key"]
        if key in unavailable:
            raise SourceEvidenceUnavailable("synthetic source unavailable")
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, []),
                                         truncated=key in truncated, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=RULES, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-10-07T12:00:00+08:00",
        evaluation_as_of_date="2026-10-07", evaluation_horizon_policy="frozen_task_date",
        row_reader=read,
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=RULES, decision_rule_ids=RULES, evidence_snapshot=session.snapshot,
        evidence_materials=session.materials, llm_client=None,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=RULES,
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule} for rule in RULES], execution_results=[],
        reduced_decisions=reduced, customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials},
    )
    assert execution.llm_call_count == execution.total_tokens == 0
    return reduced, canonical


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ("crisis_value_record", "labtest_item_report"))
async def test_unavailable_critical_material_keeps_data_gap_in_final_result(source):
    reduced, canonical = await evaluate(unavailable=(source,))
    for decision, result in zip(reduced, canonical):
        assert decision.final_state.value == result["status"] == "data_gap"
        assert decision.reason_code == result["reason_code"] == "source_unavailable"
        facts = result["customer_display_facts"]
        assert facts == {"failure_kind": "critical_value_source_unavailable",
                         "missing_source": source, "issue": "source_unavailable"}
        assert result["findings"] and result["suggestion"]
        assert "未找到报告后的危急值处置记录" not in result["findings"]
        assert validate_luxian_0609_published_customer_display_facts(
            rule_id=result["rule_id"], raw=json.loads(json.dumps(facts)),
            status=result["status"], reason_code=result["reason_code"],
        ) == facts


@pytest.mark.asyncio
@pytest.mark.parametrize("report_time", (None, "not-a-time"))
async def test_missing_report_time_keeps_data_gap_in_final_result(report_time):
    reduced, canonical = await evaluate(report_time=report_time)
    for decision, result in zip(reduced, canonical):
        assert decision.final_state.value == result["status"] == "data_gap"
        assert decision.reason_code == result["reason_code"] == "authoritative_time_missing"
        facts = result["customer_display_facts"]
        assert facts == {"failure_kind": "critical_value_report_time_missing",
                         "critical_item_names": ["血钾"], "critical_flags": ["PH"],
                         "missing_report_time_count": 1}
        assert "报告时间" in result["findings"] and "无法核对" in result["findings"]
        assert "未找到报告后的危急值处置记录" not in result["findings"]
        assert validate_luxian_0609_published_customer_display_facts(
            rule_id=result["rule_id"], raw=json.loads(json.dumps(facts)),
            status=result["status"], reason_code=result["reason_code"],
        ) == facts


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments,expected", [
    ({"items": False, "disposition_time": False}, ("not_applicable", "not_applicable")),
    ({"disposition_time": False}, ("non_compliant", "non_compliant")),
    ({}, ("compliant", "compliant")),
    ({"disposition_time": "2026-10-01 15:00:00"}, ("non_compliant", "compliant")),
    ({"disposition_time": None}, ("data_gap", "data_gap")),
])
async def test_empty_complete_and_existing_disposition_controls(arguments, expected):
    _, canonical = await evaluate(**arguments)
    assert tuple(result["status"] for result in canonical) == expected


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("facts", [
    {"failure_kind": "critical_value_source_unavailable", "missing_source": "unknown_table", "issue": "source_unavailable"},
    {"failure_kind": "critical_value_source_unavailable", "missing_source": "crisis_value_record", "issue": "trigger_absent_complete"},
    {"failure_kind": "critical_value_source_unavailable", "missing_source": "crisis_value_record", "issue": "source_unavailable", "source_document_ids": ["INVENTED"]},
    {"failure_kind": "critical_value_report_time_missing", "critical_item_names": ["血钾"], "critical_flags": ["N"], "missing_report_time_count": 1},
    {"failure_kind": "critical_value_report_time_missing", "critical_item_names": ["血钾"], "critical_flags": ["PH"], "missing_report_time_count": True},
    {"failure_kind": "critical_value_report_time_missing", "critical_item_names": ["血钾"], "critical_flags": ["PH"], "missing_report_time_count": 0},
    {"failure_kind": "critical_value_report_time_missing", "critical_item_names": ["血钾"], "critical_flags": ["PH"], "missing_report_time_count": 2},
    {"failure_kind": "critical_value_report_time_missing", "critical_item_names": ["血钾"], "critical_flags": [], "missing_report_time_count": 1},
    {"failure_kind": "critical_value_report_time_missing", "critical_item_names": ["血钾"], "critical_flags": ["PH"], "missing_report_time_count": 1, "report_time": "INVENTED"},
])
def test_forged_gap_facts_are_rejected_at_published_boundary(rule, facts):
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule, raw=facts, status="data_gap", reason_code="source_unavailable",
        )


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("state", ("compliant", "non_compliant", "not_applicable"))
def test_valid_gap_shape_cannot_justify_a_determined_state(rule, state):
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule, raw={"failure_kind": "critical_value_source_unavailable",
                              "missing_source": "crisis_value_record", "issue": "source_unavailable"},
            status=state, reason_code="source_unavailable",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", [
    {"unavailable": ("crisis_value_record",)},
    {"unavailable": ("labtest_item_report",)},
    {"report_time": None},
    {"report_time": "not-a-time"},
    {},
    {"items": False, "disposition_time": False},
    {"disposition_time": False},
    {"disposition_time": "2026-10-01 15:00:00"},
])
async def test_canonical_store_new_session_preserves_gaps_and_controls(arguments, tmp_path):
    from datetime import datetime
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace_module
    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore, envelope_item_from_rule_result,
    )

    _, canonical = await evaluate(**arguments)
    items = [{**result, "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
             for result in canonical]
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "critical-gaps.sqlite").as_posix()
    engine = create_engine(url)
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    try:
        with Session(engine) as write_db:
            store.replace_for_job(
                write_db, job_row={"id": "J", "created_by": "reviewer",
                    "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1",
                                                 "rule_set_version": "2026-06-09"})},
                items=items, now=datetime(2026, 10, 7, 12),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"),
                projection_key="test-key",
            )
            write_db.commit()
        # 关闭写Session与引擎，再用新引擎、新Session经过正式读取校验。
        engine.dispose()
        engine = create_engine(url)
        with Session(engine) as read_db:
            loaded = store.load_selected(
                read_db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            )
            assert len(loaded["items"]) == 2
            originals = {result["rule_id"]: result for result in items}
            for saved in loaded["items"]:
                original = originals[saved["rule_id"]]
                for key in ("status", "reason_code", "customer_display_facts", "findings", "suggestion"):
                    assert saved.get(key) == original.get(key)
                projected = envelope_item_from_rule_result(original, hmac_key="test-key")
                assert saved["evidence"] == projected["evidence"]
                assert all("source_document_id" not in evidence for evidence in saved["evidence"])
                for key in ("is_compliant", "criterion_results"):
                    assert saved.get(key) == projected.get(key), key
                api = workspace_module.project_customer_safe_result_item(saved, hmac_key="test-key")
                for key in ("status", "reason_code", "is_compliant", "customer_display_facts", "criterion_results", "evidence", "findings", "suggestion"):
                    actual = api.get(key, []) if key == "criterion_results" else api.get(key)
                    assert actual == saved.get(key), key
    finally:
        engine.dispose()

@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("status", ("", "unknown", "technical_error", "uncertain", "not_executed"))
@pytest.mark.parametrize("facts", [
    {"failure_kind": "critical_value_source_unavailable", "missing_source": "crisis_value_record", "issue": "source_unavailable"},
    {"failure_kind": "critical_value_report_time_missing", "critical_item_names": ["血钾"], "critical_flags": ["PH"], "missing_report_time_count": 1},
])
def test_new_gap_kinds_reject_empty_unknown_and_internal_status(rule, status, facts):
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule, raw=facts, status=status, reason_code="source_unavailable",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ("crisis_value_record", "labtest_item_report"))
async def test_truncated_sources_keep_gap_facts_and_no_absence_claim(source):
    reduced, canonical = await evaluate(truncated=(source,))
    for decision, result in zip(reduced, canonical):
        assert decision.final_state.value == result["status"] == "data_gap"
        assert result["reason_code"] == "source_truncated"
        assert result["customer_display_facts"] == {
            "failure_kind": "critical_value_source_unavailable",
            "missing_source": source, "issue": "source_truncated",
        }
        assert "无法核对" in result["findings"]
        assert "未找到" not in result["findings"]
