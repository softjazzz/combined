"""培养事件中结构化菌名的 positive_hint seam。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.luxian_0609.exam_lab_fact_extraction import (
    SCHEMA_VERSION,
    build_exam_lab_fact_prompt,
    build_exam_lab_text_projection,
    events_for_family,
    parse_exam_lab_fact_response,
)


def _culture_projection(
    item_rows: list[dict[str, Any]],
) -> Any:
    return build_exam_lab_text_projection(
        rows_by_source={
            "labtest_master": [
                {
                    "test_id": "T-1",
                    "labtest_subject": "微生物实验室",
                    "specimen": "尿液",
                    "report_time": "2026-09-12 10:00:00",
                }
            ],
            "labtest_item_report": item_rows,
        }
    )


def _culture_row(
    item_name: str,
    result: str | None,
    *,
    test_id: str = "T-1",
    report_time: str = "2026-09-12 10:00:00",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "item_name": item_name,
        "result": result,
        "report_time": report_time,
        **extra,
    }


def _unknown_015_response() -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "schema_version": SCHEMA_VERSION,
                            "facts": [
                                {
                                    "rule_id": "LX0609-06-03-04",
                                    "applicability": "unknown",
                                    "semantic_state": "unknown",
                                    "positive_state": "unknown",
                                    "course_doc_positions": [],
                                }
                            ],
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }


def test_identified_organism_promotes_projection_and_parser_to_positive() -> None:
    projection = _culture_projection(
        [
            _culture_row("尿一般细菌培养", None),
            _culture_row("细菌结果（质谱法）1：", "粪肠球菌"),
            _culture_row("细菌结果（质谱法）2：", None),
        ]
    )

    event = events_for_family(projection, "culture")[0]
    assert event.target_confirmed is True
    assert event.positive_hint == "positive"

    fact = parse_exam_lab_fact_response(
        response=_unknown_015_response(),
        selected_rule_ids=["LX0609-06-03-04"],
        projection=projection,
    )[0]
    assert fact.positive_state == "positive"
    assert fact.applicability == "applicable"
    assert fact.semantic_state == "absent"


def test_pending_sensitivity_and_empty_alternate_slots_do_not_downgrade_identified_organism() -> None:
    projection = _culture_projection(
        [
            _culture_row("尿一般细菌培养", None),
            _culture_row("细菌结果（质谱法）1：", "粪肠球菌"),
            _culture_row("细菌结果（质谱法）2：", None),
            _culture_row("细菌结果3：", "未填写"),
            _culture_row("药敏结果", "待报告"),
        ]
    )

    assert events_for_family(projection, "culture")[0].positive_hint == "positive"


@pytest.mark.parametrize(
    "item_name",
    [
        "细菌结果",
        "细菌结果1",
        "细菌结果 (质谱法) 1:",
        "细菌结果（质谱法）2",
    ],
)
def test_bacteria_result_item_name_allows_optional_method_number_and_colon(
    item_name: str,
) -> None:
    projection = _culture_projection(
        [
            _culture_row("尿一般细菌培养", None),
            _culture_row(item_name, "大肠埃希菌"),
        ]
    )

    assert events_for_family(projection, "culture")[0].positive_hint == "positive"


@pytest.mark.parametrize("result", ["待定", "考虑污染", "正常菌群", "混合菌群"])
def test_ambiguous_or_non_organism_result_does_not_become_structured_positive(
    result: str,
) -> None:
    projection = _culture_projection(
        [
            _culture_row("尿一般细菌培养", None),
            _culture_row("细菌结果（质谱法）1：", result),
        ]
    )

    assert events_for_family(projection, "culture")[0].positive_hint != "positive"


@pytest.mark.parametrize(
    "result",
    [
        "暂无结果",
        "报告未出",
        "培养中",
        "未完成",
        "详见报告",
        "未知细菌",
        "疑似某菌",
        "可能为某菌",
        "待鉴定菌",
        "无细菌",
        "混合菌",
    ],
)
def test_unresolved_result_text_does_not_match_organism_name_shape(result: str) -> None:
    projection = _culture_projection(
        [
            _culture_row("尿一般细菌培养", None),
            _culture_row("细菌结果（质谱法）1：", result),
        ]
    )

    assert events_for_family(projection, "culture")[0].positive_hint != "positive"


def test_identified_organism_conflicting_with_no_growth_stays_unknown() -> None:
    projection = _culture_projection(
        [
            _culture_row("尿一般细菌培养", "培养两日无细菌生长"),
            _culture_row("细菌结果（质谱法）1：", "粪肠球菌"),
        ]
    )

    assert events_for_family(projection, "culture")[0].positive_hint == "unknown"


@pytest.mark.parametrize(
    "result", ["未培养出细菌", "未分离出细菌", "未鉴定菌", "未确定菌"]
)
def test_explicit_unidentified_or_not_isolated_result_does_not_become_positive(
    result: str,
) -> None:
    projection = _culture_projection(
        [
            _culture_row("尿一般细菌培养", None),
            _culture_row("细菌结果（质谱法）1：", result),
        ]
    )

    assert events_for_family(projection, "culture")[0].positive_hint != "positive"


@pytest.mark.parametrize("result", ["阴性", "培养两日无细菌生长", "考虑污染"])
def test_conflict_in_any_same_event_result_row_stays_unknown(result: str) -> None:
    projection = _culture_projection(
        [
            _culture_row("尿一般细菌培养", None),
            _culture_row("细菌结果（质谱法）1：", "粪肠球菌"),
            _culture_row("备注", result),
        ]
    )

    assert events_for_family(projection, "culture")[0].positive_hint == "unknown"


def test_named_organism_starting_with_wu_is_not_treated_as_no_bacteria() -> None:
    projection = _culture_projection(
        [
            _culture_row("尿一般细菌培养", None),
            _culture_row("细菌结果（质谱法）1：", "无乳链球菌"),
        ]
    )

    assert events_for_family(projection, "culture")[0].positive_hint == "positive"


def test_negative_master_indicator_conflicts_even_without_item_name() -> None:
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "labtest_master": [
                {
                    "test_id": "T-1",
                    "labtest_subject": "微生物实验室",
                    "specimen": "尿液",
                    "report_time": "2026-09-12 10:00:00",
                    "abnormal_indicator": "阴性",
                }
            ],
            "labtest_item_report": [
                _culture_row("尿一般细菌培养", None),
                _culture_row("细菌结果（质谱法）1：", "粪肠球菌"),
            ],
        }
    )

    assert events_for_family(projection, "culture")[0].positive_hint == "unknown"


def test_only_result_field_on_exact_item_name_counts_and_unrelated_item_does_not() -> None:
    projection = _culture_projection(
        [
            _culture_row("尿一般细菌培养", None),
            _culture_row("涂片细菌结果", "革兰阴性杆菌3+"),
        ]
    )

    assert events_for_family(projection, "culture")[0].positive_hint != "positive"


def test_organism_name_in_course_text_or_record_content_is_not_structured_evidence() -> None:
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "labtest_item_report": [
                _culture_row("尿一般细菌培养", None),
                _culture_row(
                    "细菌结果（质谱法）1：",
                    None,
                    record_content="细菌结果（质谱法）1：粪肠球菌",
                ),
            ],
            "daily_course_record": [
                {
                    "record_time": "2026-09-12 12:00:00",
                    "record_content": "病程提到培养检出粪肠球菌。",
                }
            ],
        }
    )

    assert events_for_family(projection, "culture")[0].positive_hint != "positive"


def test_identified_organism_isolated_to_its_bound_culture_event() -> None:
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "labtest_item_report": [
                _culture_row(
                    "尿一般细菌培养",
                    None,
                    test_id="T-1",
                    report_time="2026-09-12 10:00:00",
                ),
                _culture_row(
                    "细菌结果（质谱法）1：",
                    "粪肠球菌",
                    test_id="T-1",
                    report_time="2026-09-12 10:00:00",
                ),
                _culture_row(
                    "痰一般细菌培养",
                    None,
                    test_id="T-2",
                    report_time="2026-09-13 10:00:00",
                ),
            ]
        }
    )

    events = events_for_family(projection, "culture")
    assert len(events) == 2
    assert [event.positive_hint for event in events] == ["positive", "unknown"]


def test_prompt_uses_identified_organism_policy_without_drug_sensitivity_prerequisite() -> None:
    projection = _culture_projection(
        [_culture_row("尿一般细菌培养", None)]
    )
    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=["LX0609-06-03-04"],
        projection=projection,
    )

    old = "送检、培养中、待报告、污染可能、无生长不得标阳性；阳性但药敏待出时015为unknown。"
    new = (
        "送检、培养中、待报告、污染可能、无生长不得标阳性。015依据已报告的阳性菌评价分析、临床意义或处理，"
        "不以药敏报告齐全为前提；已明确检出菌名但药敏待出，仍应评价对已有阳性结果的分析。培养报告同一事件的"
        "细菌结果/菌种鉴定栏中已填写明确菌名，即已有阳性菌结果；其他备选菌栏、备注或培养总栏为空，不得将这个"
        "已填写菌名的结果降为unknown或negative。具体抗菌药物是否符合药敏不在015判定范围内。"
    )
    assert old not in prompt
    assert new in prompt
