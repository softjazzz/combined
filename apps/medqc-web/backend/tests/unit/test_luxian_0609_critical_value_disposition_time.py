"""危急值已有处置但时间不可核对的执行、归约、交付回归。"""

import json

import pytest

from test_luxian_0609_native_extended_document_execution import _evaluate_selected
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609.critical_value_result_mapping import (
    validate_published_critical_value_facts,
    critical_value_customer_fact_status_is_valid,
)

RULES = ("LX0609-06-04-01", "LX0609-06-04-02")


async def evaluate(records, extra_items=()):
    rows = {
        "labtest_item_report": (
            {
                "test_id": "REPORT-A",
                "item_name": "血钾",
                "abnormal_indicator": "PH",
                "report_time": "2026-06-01 14:00:00",
            },
            *extra_items,
        ),
        "crisis_value_record": tuple(records),
        "evaluation_context.horizon": (
            {"horizon_datetime": "2026-06-02 12:00:00", "basis": "evaluation_as_of"},
        ),
    }
    snapshot, materials, execution, reduced = await _evaluate_selected(RULES, rows)
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule} for rule in RULES],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    for result in canonical:
        # 模拟保存JSON后回读，经过与保存交付相同的已发布事实校验。
        facts = json.loads(json.dumps(result["customer_display_facts"]))
        valid, published = validate_published_critical_value_facts(
            rule_id=result["rule_id"], raw=facts
        )
        assert valid and published == facts
        assert critical_value_customer_fact_status_is_valid(
            rule_id=result["rule_id"], status=result["status"], safe_facts=facts
        )
    return snapshot, materials, execution, reduced, canonical


def disposition(time, key="REPORT-A"):
    return {
        "test_id": key,
        "record_time": time,
        "record_content": "已复查并完成危急值处置。",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "time,reason",
    [
        (None, "authoritative_time_missing"),
        ("not-a-time", "authoritative_time_missing"),
        ("2026-06-01 13:59:00", "authoritative_time_conflict"),
    ],
)
async def test_documented_disposition_time_gap_survives_delivery(time, reason):
    snapshot, materials, execution, reduced, canonical = await evaluate(
        [disposition(time)]
    )
    reference = materials.document_rows("crisis_value_record", snapshot=snapshot)[0][0]
    for decision, result in zip(reduced, canonical):
        assert decision.final_state.value == result["status"] == "data_gap"
        assert decision.reason_code == result["reason_code"] == reason
        assert "已找到与危急值报告关联的处置记录" in result["findings"]
        assert "未找到" not in result["findings"]
        assert result["customer_display_facts"]["event_results"][0]["outcome"] == reason
    assert all(reference in item.fact_refs for item in execution.decisions)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "times,expected",
    [
        ([], ("non_compliant", "non_compliant")),
        (["2026-06-01 16:00:00"], ("compliant", "compliant")),
        (["2026-06-01 21:00:00"], ("non_compliant", "compliant")),
        ([None, "2026-06-01 16:00:00"], ("compliant", "compliant")),
        ([None, "2026-06-01 21:00:00"], ("data_gap", "compliant")),
    ],
)
async def test_disposition_protection_cases(times, expected):
    *_, canonical = await evaluate([disposition(time) for time in times])
    assert tuple(item["status"] for item in canonical) == expected


@pytest.mark.asyncio
async def test_other_report_does_not_cover_missing_time():
    *_, canonical = await evaluate([disposition(None, "OTHER")])
    assert all(
        item["status"] == "data_gap" and item["reason_code"] == "association_failed"
        for item in canonical
    )


@pytest.mark.asyncio
async def test_multiple_events_keep_uncertainty_local():
    *_, canonical = await evaluate(
        [disposition(None), disposition("2026-06-01 16:00:00", "REPORT-B")],
        (
            {
                "test_id": "REPORT-B",
                "item_name": "血钠",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 14:00:00",
            },
        ),
    )
    assert [item["status"] for item in canonical] == ["data_gap", "data_gap"]
    assert [
        event["outcome"]
        for event in canonical[0]["customer_display_facts"]["event_results"]
    ] == ["authoritative_time_missing", "timely"]
    assert [
        event["outcome"]
        for event in canonical[1]["customer_display_facts"]["event_results"]
    ] == ["authoritative_time_missing", "handled"]


@pytest.mark.asyncio
@pytest.mark.parametrize("time", [None, "not-a-time", "2026-06-01 13:59:00"])
async def test_time_gap_survives_canonical_store_roundtrip(time):
    from datetime import datetime
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    import app.services.custom_qc_workspace_service as workspace_module
    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore,
        envelope_item_from_rule_result,
    )

    *_, canonical = await evaluate([disposition(time)])
    items = [
        {
            **result,
            "record_id": "V",
            "visit_id": "V",
            "institute_id": "I",
            "patient_id": "P",
        }
        for result in canonical
    ]
    table = workspace_module._record_result_envelopes_table().to_metadata(
        MetaData(), schema=None
    )
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    try:
        with Session(engine) as db:
            store.replace_for_job(
                db,
                job_row={
                    "id": "J",
                    "created_by": "reviewer",
                    "filters_json": json.dumps(
                        {
                            "rule_set_key": "luxian_0609_qc_v1",
                            "rule_set_version": "2026-06-09",
                        }
                    ),
                },
                items=items,
                now=datetime(2026, 10, 7, 12),
                projector=lambda raw: envelope_item_from_rule_result(
                    raw, hmac_key="test-key"
                ),
                projection_key="test-key",
            )
            db.commit()
            loaded = store.load_selected(
                db,
                root_job_id="J",
                institute_id="I",
                patient_id="P",
                visit_id="V",
                rule_set_key="luxian_0609_qc_v1",
                rule_set_version="2026-06-09",
            )
            assert len(loaded["items"]) == 2
            for original, saved in zip(items, loaded["items"]):
                assert saved["status"] == "data_gap"
                for key in (
                    "reason_code",
                    "customer_display_facts",
                    "findings",
                    "suggestion",
                ):
                    assert saved[key] == original[key]
    finally:
        engine.dispose()
