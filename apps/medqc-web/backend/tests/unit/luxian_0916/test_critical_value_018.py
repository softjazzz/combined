from __future__ import annotations

from app.services.luxian_0916.critical_value_018 import (
    build_critical_value_018_facts,
    merge_critical_value_018_facts,
)


def _source_field(name: str, value: str) -> dict[str, object]:
    return {
        "source_table": "labtest_item_report",
        "source_field": name,
        "source_path": None,
        "used": True,
        "raw_value_preview": value,
    }


def _report(
    *,
    report_id: str = "REPORT-1",
    test_id: str = "TEST-1",
    report_time: str = "2026-09-16 08:00:00",
    items: list[dict[str, str]] | None = None,
    projection_incomplete: bool = False,
) -> dict[str, object]:
    return {
        "source_table": "labtest_item_report",
        "document_type": "labtest_item_report",
        "document_id": report_id,
        "record_time": report_time,
        "report_metadata": {"report_datetime": report_time},
        "report_items": items
        or [
            {
                "item_id": "ITEM-1",
                "item_name": "血钾",
                "result": "6.8",
                "unit": "mmol/L",
                "abnormal_indicator": "PH",
            }
        ],
        "source_fields": [
            _source_field("test_id", test_id),
            _source_field("test_no", report_id),
        ],
        "projection_incomplete": projection_incomplete,
    }


def _bundle(
    *,
    reports: list[dict[str, object]] | None = None,
    masters: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    report_rows = reports if reports is not None else [_report()]
    return {
        "source_documents": report_rows,
        "structured_context": {
            "documents": {
                "labtest_master": (
                    masters
                    if masters is not None
                    else [
                        {
                            "test_id": "TEST-1",
                            "report_datetime": "2026-09-16 08:00:01",
                            "labtest_result_status": "已审核",
                        }
                    ]
                ),
                "labtest_item_report": [],
            }
        },
    }


def _evidence(
    *,
    report_ids: tuple[str, ...] = ("REPORT-1",),
    item_state: str = "complete",
    master_state: str = "complete",
    structured_source_rows: dict[str, list[dict[str, object]]] | None = None,
) -> dict[str, object]:
    timeline: dict[str, object] = {
        "documents": {
            "labtest_item_report": [
                {"document_id": report_id} for report_id in report_ids
            ]
        },
        "source_readiness": {
            "labtest_item_report": item_state,
            "labtest_master": master_state,
        },
    }
    if structured_source_rows is not None:
        timeline["structured_source_rows"] = structured_source_rows
    return {
        "programmatic_timeline": {
            **timeline,
        }
    }


def test_top_level_grouped_report_forms_018_event() -> None:
    result = build_critical_value_018_facts(
        bundle=_bundle(),
        evidence_payload=_evidence(),
    )

    assert result["event_source_state_by_rule"] == {
        "LX0916-018": "critical_value_source_complete"
    }
    assert result["diagnostic"]["evidence_read_chain"] == (
        "shared_evidence_structured_rows_with_bundle_inventory_fallback"
    )
    assert result["diagnostic"]["llm_call_count"] == 0
    assert result["event_facts"]["critical_values"] == [
        {
            "event_type": "critical_values",
            "event_id": "critical-value:REPORT-1",
            "trigger_confirmed": True,
            "evaluation_window_mature": None,
            "event_source_type": "labtest_item_report",
            "event_source_id": "REPORT-1",
            "event_time": "2026-09-16 08:00:00",
            "event_kind": "critical_lab_report",
            "related_source_type": "labtest_item_report",
            "related_source_ids": ["ITEM-1"],
            "critical_flags": ["PH"],
            "critical_items": [
                {
                    "item_id": "ITEM-1",
                    "item_name": "血钾",
                    "result": "6.8",
                    "unit": "mmol/L",
                    "critical_flag": "PH",
                }
            ],
            "report_statuses": ["已审核"],
        }
    ]


def test_persisted_scene_bundle_uses_nested_document_inventory() -> None:
    bundle = _bundle()
    inventory = bundle.pop("source_documents")
    bundle["structured_context"]["document_inventory"] = inventory
    bundle["structured_context"]["documents"] = {
        "labtest_item_report": [
            {"text_preview": "血钾：6.8（提示 PH）", "document_title": "电解质检验报告"}
        ],
        "labtest_master": [
            {"text_preview": "检验报告摘要", "document_title": "检验报告"}
        ],
    }

    result = build_critical_value_018_facts(
        bundle=bundle,
        evidence_payload=_evidence(),
    )

    assert result["event_source_state_by_rule"] == {
        "LX0916-018": "critical_value_source_complete"
    }
    assert result["event_facts"]["critical_values"][0]["event_id"] == (
        "critical-value:REPORT-1"
    )


def test_complete_empty_inventory_is_a_confirmed_no_trigger() -> None:
    result = build_critical_value_018_facts(
        bundle={
            "structured_context": {
                "document_inventory": [
                    {
                        "source_table": "daily_course_record",
                        "document_id": "COURSE-1",
                    }
                ],
                "documents": {},
            }
        },
        evidence_payload=_evidence(report_ids=()),
    )

    assert result["event_source_state_by_rule"] == {
        "LX0916-018": "critical_value_source_complete"
    }
    assert result["event_facts"]["critical_values"] == []


def test_shared_structured_rows_are_preferred_over_stale_bundle_projection() -> None:
    result = build_critical_value_018_facts(
        bundle=_bundle(
            reports=[
                _report(
                    items=[
                        {
                            "item_id": "OLD-HI",
                            "item_name": "白细胞",
                            "result": "20",
                            "unit": "10^9/L",
                            "abnormal_indicator": "HI",
                        }
                    ]
                )
            ]
        ),
        evidence_payload=_evidence(
            report_ids=("REPORT-2",),
            structured_source_rows={
                "labtest_item_report": [
                    {
                        "test_id": "TEST-2",
                        "test_no": "REPORT-2",
                        "item_id": "ITEM-2",
                        "item_name": "血钙",
                        "result": "1.5",
                        "unit": "mmol/L",
                        "abnormal_indicator": "PL",
                        "report_time": "2026-09-16 09:00:00",
                    }
                ],
                "labtest_master": [
                    {
                        "test_id": "TEST-2",
                        "report_datetime": "2026-09-16 09:00:00",
                        "labtest_result_status": "已审核",
                    }
                ],
            },
        ),
    )

    event = result["event_facts"]["critical_values"][0]
    assert event["event_id"] == "critical-value:REPORT-2"
    assert event["critical_flags"] == ["PL"]


def test_top_inventory_uses_matching_raw_rows_when_bundle_keeps_them() -> None:
    bundle = _bundle()
    bundle["structured_context"]["documents"]["labtest_item_report"] = [
        {
            "document_id": "ITEM-DOC-1",
            "test_id": "TEST-1",
            "test_no": "REPORT-1",
            "item_id": "RAW-ITEM-1",
            "item_name": "血钾",
            "result": "7.0",
            "unit": "mmol/L",
            "abnormal_indicator": "PH",
            "report_time": "2026-09-16 08:00:00",
        }
    ]

    result = build_critical_value_018_facts(
        bundle=bundle,
        evidence_payload=_evidence(),
    )

    item = result["event_facts"]["critical_values"][0]["critical_items"][0]
    assert item["item_id"] == "RAW-ITEM-1"
    assert item["result"] == "7.0"


def test_item_report_time_precedes_nonidentical_master_time() -> None:
    result = build_critical_value_018_facts(
        bundle=_bundle(),
        evidence_payload=_evidence(),
    )

    event = result["event_facts"]["critical_values"][0]
    assert event["event_time"] == "2026-09-16 08:00:00"


def test_multiple_reports_are_independent_events() -> None:
    second = _report(
        report_id="REPORT-2",
        test_id="TEST-2",
        report_time="2026-09-16 09:00:00",
        items=[
            {
                "item_id": "ITEM-2",
                "item_name": "血钙",
                "result": "1.5",
                "unit": "mmol/L",
                "abnormal_indicator": "PL",
            }
        ],
    )
    result = build_critical_value_018_facts(
        bundle=_bundle(
            reports=[_report(), second],
            masters=[
                {"test_id": "TEST-1", "labtest_result_status": "已审核"},
                {"test_id": "TEST-2", "labtest_result_status": "已审核"},
            ],
        ),
        evidence_payload=_evidence(report_ids=("REPORT-1", "REPORT-2")),
    )

    events = result["event_facts"]["critical_values"]
    assert [event["event_id"] for event in events] == [
        "critical-value:REPORT-1",
        "critical-value:REPORT-2",
    ]
    assert [event["critical_flags"] for event in events] == [["PH"], ["PL"]]


def test_hi_and_li_do_not_trigger_but_pl_and_ph_do() -> None:
    report = _report(
        items=[
            {
                "item_id": "HI",
                "item_name": "白细胞",
                "result": "20",
                "unit": "",
                "abnormal_indicator": "HI",
            },
            {
                "item_id": "LI",
                "item_name": "血红蛋白",
                "result": "80",
                "unit": "g/L",
                "abnormal_indicator": "LI",
            },
            {
                "item_id": "PL",
                "item_name": "血钙",
                "result": "1.5",
                "unit": "mmol/L",
                "abnormal_indicator": "PL",
            },
            {
                "item_id": "PH",
                "item_name": "血钾",
                "result": "6.8",
                "unit": "mmol/L",
                "abnormal_indicator": "PH",
            },
        ]
    )
    result = build_critical_value_018_facts(
        bundle=_bundle(reports=[report]),
        evidence_payload=_evidence(),
    )

    items = result["event_facts"]["critical_values"][0]["critical_items"]
    assert [item["item_id"] for item in items] == ["PL", "PH"]


def test_cancelled_or_invalid_report_does_not_trigger() -> None:
    for status in ("已取消", "作废", "invalid"):
        result = build_critical_value_018_facts(
            bundle=_bundle(
                masters=[
                    {
                        "test_id": "TEST-1",
                        "report_datetime": "2026-09-16 08:00:00",
                        "labtest_result_status": status,
                    }
                ]
            ),
            evidence_payload=_evidence(),
        )
        assert result["event_facts"]["critical_values"] == []
        assert result["event_source_state_by_rule"]["LX0916-018"] == (
            "critical_value_source_complete"
        )


def test_source_read_failure_and_truncation_are_not_no_event() -> None:
    unavailable = build_critical_value_018_facts(
        bundle=_bundle(),
        evidence_payload=_evidence(item_state="unavailable"),
    )
    partial = build_critical_value_018_facts(
        bundle=_bundle(reports=[_report(projection_incomplete=True)]),
        evidence_payload=_evidence(),
    )

    assert unavailable["event_source_state_by_rule"]["LX0916-018"] == (
        "critical_value_source_unavailable"
    )
    assert partial["event_source_state_by_rule"]["LX0916-018"] == (
        "critical_value_source_partial"
    )


def test_timeline_report_mismatch_is_partial_coverage() -> None:
    result = build_critical_value_018_facts(
        bundle=_bundle(),
        evidence_payload=_evidence(report_ids=("REPORT-1", "REPORT-2")),
    )

    assert result["event_source_state_by_rule"]["LX0916-018"] == (
        "critical_value_source_partial"
    )


def test_missing_item_context_is_invalid_not_silently_dropped() -> None:
    result = build_critical_value_018_facts(
        bundle=_bundle(
            reports=[
                _report(
                    items=[
                        {
                            "item_id": "ITEM-1",
                            "item_name": "血钾",
                            "result": "",
                            "unit": "mmol/L",
                            "abnormal_indicator": "PH",
                        }
                    ]
                )
            ]
        ),
        evidence_payload=_evidence(),
    )

    assert result["event_source_state_by_rule"]["LX0916-018"] == (
        "critical_value_source_invalid"
    )
    assert result["diagnostic"]["invalid_count"] == 1


def test_structured_documents_remain_a_supported_fallback() -> None:
    bundle = {
        "structured_context": {
            "documents": {
                "labtest_item_report": [
                    {
                        "document_id": "ITEM-DOC-1",
                        "test_id": "TEST-1",
                        "item_id": "ITEM-1",
                        "item_name": "血钾",
                        "result": "6.8",
                        "unit": "mmol/L",
                        "abnormal_indicator": "PH",
                        "report_time": "2026-09-16 08:00:00",
                    }
                ],
                "labtest_master": [
                    {"test_id": "TEST-1", "labtest_result_status": "已审核"}
                ],
            }
        }
    }
    result = build_critical_value_018_facts(
        bundle=bundle,
        evidence_payload=_evidence(report_ids=()),
    )

    assert result["event_source_state_by_rule"]["LX0916-018"] == (
        "critical_value_source_complete"
    )
    assert result["event_facts"]["critical_values"][0]["event_id"] == (
        "critical-value:TEST-1"
    )


def test_merge_replaces_only_018_owned_facts() -> None:
    merged = merge_critical_value_018_facts(
        context={
            "event_facts": {"critical_values": [{"event_id": "old"}], "other": [1]},
            "event_source_state_by_rule": {
                "LX0916-018": "selected",
                "LX0916-019": "selected",
            },
        },
        structured_facts={
            "event_facts": {"critical_values": [{"event_id": "new"}]},
            "event_source_state_by_rule": {
                "LX0916-018": "critical_value_source_complete"
            },
        },
    )

    assert merged["event_facts"] == {
        "critical_values": [{"event_id": "new"}],
        "other": [1],
    }
    assert merged["event_source_state_by_rule"] == {
        "LX0916-018": "critical_value_source_complete",
        "LX0916-019": "selected",
    }
