"""IML-02：危急值报告时间只使用可靠、无冲突的报告字段。"""

from datetime import datetime
import json

import pytest

from test_luxian_0609_native_extended_document_execution import _evaluate_selected
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results

RULES = ("LX0609-06-04-01", "LX0609-06-04-02")
MISSING = {"record_time": "2026-06-01 08:00:00"}
CONFLICT = {"report_time": "2026-06-01 08:00:00", "report_datetime": "2026-06-02 08:00:00"}
NORMAL = {"report_time": "2026-06-01 08:00:00"}


def mixed_rows(gap_fields, disposition_time=False, *, reverse=False):
    items = [
        {"test_id": "A", "item_name": "血钾A", "abnormal_indicator": "PH",
         "report_time": "2026-06-01 08:00:00"},
        {"test_id": "B", "item_name": "血钾B", "abnormal_indicator": "PL", **gap_fields},
    ]
    return {
        "labtest_item_report": list(reversed(items)) if reverse else items,
        "crisis_value_record": [] if disposition_time is False else [
            {"test_id": "A", "record_time": disposition_time, "record_content": "已完成对应处置。"}],
        "evaluation_context.horizon": [{"horizon_datetime": "2026-06-03 12:00:00",
                                        "basis": "evaluation_as_of"}],
    }


@pytest.fixture(autouse=True)
def sqlite_and_no_network(monkeypatch):
    import httpx
    import socket
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    def blocked(*args, **kwargs):
        raise AssertionError("IML-02 合成测试禁止网络和真实模型")

    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite"

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    event.listen(Engine, "before_cursor_execute", sqlite_only)
    yield
    event.remove(Engine, "before_cursor_execute", sqlite_only)


async def evaluate(fields):
    rows = {
        "labtest_item_report": [{"test_id": "T1", "item_name": "血钾",
                                 "abnormal_indicator": "PH", **fields}],
        "crisis_value_record": [{"test_id": "T1", "record_time": "2026-06-01 09:00:00",
                                 "record_content": "已复查并完成危急值处置。"}],
        "evaluation_context.horizon": [{"horizon_datetime": "2026-06-03 12:00:00",
                                        "basis": "evaluation_as_of"}],
    }
    return await evaluate_rows(rows)


async def evaluate_rows(rows):
    snapshot, materials, execution, reduced = await _evaluate_selected(RULES, rows)
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule} for rule in RULES], execution_results=[],
        reduced_decisions=reduced, customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    assert execution.llm_call_count == execution.total_tokens == 0
    reference = materials.document_rows("labtest_item_report", snapshot=snapshot)[0][0]
    assert all(reference in decision.fact_refs for decision in execution.decisions)
    return execution, reduced, canonical


@pytest.mark.asyncio
@pytest.mark.parametrize("fields,reason", [
    (MISSING, "authoritative_time_missing"),
    ({"report_time": None, **MISSING}, "authoritative_time_missing"),
    ({"report_time": "not-a-time", **MISSING}, "authoritative_time_missing"),
    ({"report_time": "not-a-time", "report_datetime": "2026-06-01 08:00:00"},
     "authoritative_time_missing"),
    ({"report_time": "2026-06-01 08:00:00", "report_datetime": "not-a-time"},
     "authoritative_time_missing"),
    (CONFLICT, "authoritative_time_conflict"),
    ({"report_time": "2026-06-01 08:00:00", "report_datetime": "2026-06-01 08:00:01"},
     "authoritative_time_conflict"),
    ({"report_time": "2026-06-01T08:00:00+08:00", "report_datetime": "2026-06-01T08:00:00Z"},
     "authoritative_time_conflict"),
])
async def test_unreliable_report_time_stays_gap_through_delivery(fields, reason):
    execution, reduced, canonical = await evaluate(fields)
    assert [item.reason_code for item in execution.decisions] == [reason, reason]
    for decision, result in zip(reduced, canonical):
        assert decision.final_state.value == result["status"] == "data_gap"
        assert decision.reason_code == result["reason_code"] == reason
        assert "报告时间" in result["findings"] and "无法核对" in result["findings"]
        assert result["suggestion"] and "继续保持" not in result["suggestion"]
        assert "未找到报告后的危急值处置记录" not in result["findings"]
        if reason == "authoritative_time_conflict":
            assert "冲突" in result["findings"]
            assert "早于报告时间" not in result["findings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fields", [
    NORMAL,
    {**NORMAL, "record_time": "2026-06-02 08:00:00"},
    {"report_datetime": "2026-06-01 08:00:00"},
    {"report_time": "", "report_datetime": "2026-06-01 08:00:00"},
    {"report_time": "2026-06-01T08:00:00+08:00", "report_datetime": "2026-06-01T00:00:00Z"},
    {"report_time": "2026-06-01 08:00:00", "report_datetime": "2026-05-31T19:00:00-05:00"},
])
async def test_reliable_report_aliases_and_equivalent_offsets_stay_compliant(fields):
    _, reduced, canonical = await evaluate(fields)
    assert [item.final_state.value for item in reduced] == ["compliant", "compliant"]
    assert [item["status"] for item in canonical] == ["compliant", "compliant"]
    assert canonical[0]["customer_display_facts"]["actual_interval_hours"] == [1.0]
    assert canonical[0]["customer_display_facts"]["report_times"] == ["2026-06-01 08:00:00"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fields", [MISSING, CONFLICT, NORMAL,
                                         {"rows": mixed_rows(MISSING)},
                                         {"rows": mixed_rows(CONFLICT)}])
async def test_canonical_store_new_engine_and_session_preserve_report_time_results(fields, tmp_path):
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace_module
    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore, envelope_item_from_rule_result,
    )

    _, _, canonical = (await evaluate_rows(fields["rows"]) if "rows" in fields
                       else await evaluate(fields))
    items = [{**result, "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
             for result in canonical]
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    url = "sqlite:///" + (tmp_path / "iml02-report-time.sqlite").as_posix()
    engine = create_engine(url)
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    try:
        with Session(engine) as write_db:
            store.replace_for_job(
                write_db, job_row={"id": "J", "created_by": "reviewer",
                    "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1",
                                                 "rule_set_version": "2026-06-09"})},
                items=items, now=datetime(2026, 10, 8, 12),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"),
                projection_key="test-key",
            )
            write_db.commit()
        engine.dispose()
        engine = create_engine(url)
        with Session(engine) as read_db:
            loaded = store.load_selected(
                read_db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            )
            assert len(loaded["items"]) == 2
            originals = {item["rule_id"]: item for item in items}
            for saved in loaded["items"]:
                original = originals[saved["rule_id"]]
                for key in ("status", "reason_code", "customer_display_facts", "findings", "suggestion"):
                    assert saved.get(key) == original.get(key), key
                projected = envelope_item_from_rule_result(original, hmac_key="test-key")
                assert saved["evidence"] == projected["evidence"]
                api = workspace_module.project_customer_safe_result_item(saved, hmac_key="test-key")
                for key in ("status", "reason_code", "is_compliant", "customer_display_facts",
                            "criterion_results", "evidence", "findings", "suggestion"):
                    actual = api.get(key, []) if key == "criterion_results" else api.get(key)
                    assert actual == saved.get(key), key
    finally:
        engine.dispose()


CONFLICT_FACTS = {
    "failure_kind": "critical_value_report_time_conflict",
    "critical_item_names": ["血钾"], "critical_flags": ["PH"],
    "conflicting_report_time_count": 1,
}


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("status", ("", "unknown", "technical_error", "uncertain", "not_executed",
                                    "compliant", "non_compliant", "not_applicable"))
def test_published_report_conflict_rejects_missing_internal_and_determined_status(rule, status):
    from app.services.luxian_0609.canonical_result_finalizer import (
        validate_luxian_0609_published_customer_display_facts,
    )
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule, raw=CONFLICT_FACTS, status=status,
            reason_code="authoritative_time_conflict",
        )


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("changes", [
    {"conflicting_report_time_count": True}, {"conflicting_report_time_count": 0},
    {"conflicting_report_time_count": 2}, {"critical_flags": ["N"]},
    {"critical_flags": []}, {"critical_item_names": []},
    {"report_times": ["2026-06-01 08:00:00"]}, {"event_key": "test_id:T1"},
    {"raw_row": {"report_time": "2026-06-01 08:00:00"}},
])
def test_published_conflict_rejects_forged_or_internal_payload(rule, changes):
    from app.services.luxian_0609.canonical_result_finalizer import (
        validate_luxian_0609_published_customer_display_facts,
    )
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule, raw={**CONFLICT_FACTS, **changes}, status="data_gap",
            reason_code="authoritative_time_conflict",
        )


@pytest.mark.asyncio
async def test_report_conflict_delivers_only_safe_summary_and_actual_report_reference():
    _, _, canonical = await evaluate(CONFLICT)
    for result in canonical:
        assert result["customer_display_facts"] == CONFLICT_FACTS
        assert set(result["customer_display_facts"]) == {
            "failure_kind", "critical_item_names", "critical_flags", "conflicting_report_time_count",
        }
        assert all(item["source_type"] == "labtest_item_report" for item in result["customer_evidence"])
        assert "处置时间缺失" not in result["findings"]
        assert "评价截止时间" not in result["findings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("gap_fields,issue", [(MISSING, "authoritative_time_missing"),
                                            (CONFLICT, "authoritative_time_conflict")])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("time,states", [
    (False, ("non_compliant", "non_compliant")),
    ("2026-06-01 15:00:00", ("non_compliant", "data_gap")),
    ("2026-06-01 09:00:00", ("data_gap", "data_gap")),
])
async def test_independent_confirmed_violation_survives_report_gap_and_input_order(gap_fields, issue, reverse, time, states):
    execution, reduced, canonical = await evaluate_rows(mixed_rows(gap_fields, time, reverse=reverse))
    assert [item.final_state.value for item in reduced] == list(states)
    assert [item["status"] for item in canonical] == list(states)
    for result in canonical:
        if result["status"] == "non_compliant":
            facts = result["customer_display_facts"]
            assert facts["critical_item_names"] == ["血钾A"]
            assert facts["report_time_gaps"] == [{"critical_item_names": ["血钾B"],
                                                 "critical_flags": ["PL"], "issue": issue}]
            assert all(item["critical_item_names"] == ["血钾A"] for item in facts["event_results"])
            assert "已确认问题" in result["findings"] and "血钾A" in result["findings"]
            assert "血钾B" in result["findings"] and "暂无法核对" in result["findings"]
            assert "不得据此认定处置缺失" in result["suggestion"]
            assert result["reason_code"] == ("threshold_exceeded" if result["rule_id"] == RULES[0]
                                             else "required_document_missing")
        else:
            assert result["reason_code"] == issue
            assert "report_time_gaps" not in result["customer_display_facts"]
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["unkeyed_disposition", "unknown_disposition", "same_key", "unkeyed_item", "immature"])
async def test_report_gap_cannot_discard_ambiguous_records_or_invent_mature_violation(change):
    rows = mixed_rows(CONFLICT)
    if change in {"unkeyed_disposition", "unknown_disposition"}:
        record = {"record_time": "2026-06-01 09:00:00", "record_content": "已完成对应处置。"}
        if change == "unknown_disposition":
            record["test_id"] = "UNKNOWN"
        rows["crisis_value_record"] = [record]
    elif change == "same_key":
        rows["labtest_item_report"][1]["test_id"] = "A"
    elif change == "unkeyed_item":
        rows["labtest_item_report"][1].pop("test_id")
    else:
        rows["evaluation_context.horizon"][0]["horizon_datetime"] = "2026-06-01 10:00:00"
    _, _, canonical = await evaluate_rows(rows)
    expected = ["data_gap", "non_compliant"] if change == "immature" else ["data_gap", "data_gap"]
    assert [item["status"] for item in canonical] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("status", ("", "unknown", "technical_error", "uncertain", "not_executed",
                                    "compliant", "data_gap", "not_applicable"))
async def test_mixed_violation_and_report_gap_rejects_inconsistent_status(rule, status):
    from app.services.luxian_0609.canonical_result_finalizer import (
        validate_luxian_0609_published_customer_display_facts,
    )
    _, _, canonical = await evaluate_rows(mixed_rows(CONFLICT))
    result = next(item for item in canonical if item["rule_id"] == rule)
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule, raw=result["customer_display_facts"], status=status,
            reason_code=result["reason_code"],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["no_violation", "gap_only", "internal_key", "invented_time", "bad_issue", "bad_flag"])
async def test_report_gap_summary_cannot_forge_a_confirmed_violation_or_publish_internal_payload(change):
    from copy import deepcopy
    from app.services.luxian_0609.canonical_result_finalizer import (
        validate_luxian_0609_published_customer_display_facts,
    )
    _, _, canonical = await evaluate_rows(mixed_rows(CONFLICT))
    facts = deepcopy(canonical[0]["customer_display_facts"])
    if change == "no_violation":
        _, _, normal = await evaluate(NORMAL)
        facts = {**normal[0]["customer_display_facts"], "report_time_gaps": facts["report_time_gaps"]}
    elif change == "gap_only":
        facts = {**CONFLICT_FACTS, "report_time_gaps": facts["report_time_gaps"]}
    elif change == "internal_key":
        facts["report_time_gaps"][0]["event_key"] = "test_id:B"
    elif change == "invented_time":
        facts["report_time_gaps"][0]["report_time"] = "2026-06-01 08:00:00"
    elif change == "bad_issue":
        facts["report_time_gaps"][0]["issue"] = "source_unavailable"
    else:
        facts["report_time_gaps"][0]["critical_flags"] = ["N"]
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=RULES[0], raw=facts, status="non_compliant", reason_code="threshold_exceeded",
        )
