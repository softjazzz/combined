from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609.native_basic_timeliness import (
    BASIC_TIMELINESS_RULE_IDS,
    execute_luxian_0609_native_basic_timeliness,
)
from app.services.luxian_0609_programmatic_rules import (
    evaluate_luxian_0609_programmatic_rules,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules


_LEGACY_RULE_IDS = ("SC-002", "CL-081", "SC-021", "SC-054", "SC-048", "SC-049", "CL-080")


def _settings(*, basic_enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=False,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=basic_enabled,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=False,
    )


def _rules(*rule_ids: str) -> list[dict]:
    selected = set(rule_ids)
    return [rule for rule in load_luxian_0609_rules() if rule["rule_id"] in selected]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("record_time", "expected_status"),
    [
        ("2026-06-01 15:00:00", "compliant"),
        ("2026-06-01 15:01:00", "non_compliant"),
    ],
)
def test_rescue_record_uses_strict_end_label_and_six_hour_boundary(
    record_time: str,
    expected_status: str,
):
    results = evaluate_luxian_0609_programmatic_rules(
        wrapper_rules=_rules("LX0609-004"),
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "rescue_record": [
                        {
                            "title": "抢救记录",
                            "authored_at": record_time,
                            "content": "抢救开始时间：2026-06-01 08:30；抢救结束时间：2026-06-01 09:00。",
                        }
                    ]
                }
            }
        },
    )

    assert len(results) == 1
    assert results[0]["status"] == expected_status
    assert results[0]["metadata"]["tokens_used"] == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    "content",
    [
        "抢救结束，患者生命体征稳定。",
        "计划于2026-06-01 09:00结束抢救。",
        "抢救结束时间：",
        "记录完成时间：2026-06-01 09:00。",
    ],
)
def test_rescue_record_rejects_nonexact_or_missing_end_time(content: str):
    results = evaluate_luxian_0609_programmatic_rules(
        wrapper_rules=_rules("LX0609-004"),
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "rescue_record": [
                        {
                            "title": "抢救记录",
                            "authored_at": "2026-06-01 10:00:00",
                            "content": content,
                        }
                    ]
                }
            }
        },
    )

    assert results[0]["status"] == "data_gap"


@pytest.mark.unit
def test_native_basic_family_returns_five_results_in_catalog_order_without_llm():
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=BASIC_TIMELINESS_RULE_IDS,
        evidence_payload={
            "programmatic_timeline": {
                "admission_time": "2026-06-01 08:00:00",
                "documents": {
                    "admission_record": [
                        {"title": "入院记录", "authored_at": "2026-06-01 09:00:00"}
                    ],
                    "first_course_record": [
                        {"title": "首次病程记录", "authored_at": "2026-06-01 10:00:00"}
                    ],
                    "rescue_record": [],
                    "senior_course_record": [
                        {
                            "title": "主治医师首次查房记录",
                            "author_title": "主治医师",
                            "authored_at": "2026-06-02 09:00:00",
                        },
                        {
                            "title": "主任医师首次查房记录",
                            "author_title": "主任医师",
                            "authored_at": "2026-06-03 09:00:00",
                        },
                    ],
                },
            }
        },
    )

    assert execution.planned_rule_ids == BASIC_TIMELINESS_RULE_IDS
    assert tuple(item["rule_id"] for item in execution.results) == BASIC_TIMELINESS_RULE_IDS
    assert [item["status"] for item in execution.results] == [
        "compliant",
        "compliant",
        "not_applicable",
        "compliant",
        "compliant",
    ]
    assert all(item["metadata"]["execution_source"] == "lx0609_native" for item in execution.results)
    assert all(int(item["metadata"].get("total_tokens") or 0) == 0 for item in execution.results)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_basic_family_enabled_removes_all_seven_legacy_rules_at_package_entry():
    evidence_payload = {
        "programmatic_timeline": {
            "admission_time": "2026-06-01 08:00:00",
            "documents": {
                "admission_record": [{"authored_at": "2026-06-01 09:00:00"}],
                "first_course_record": [{"authored_at": "2026-06-01 10:00:00"}],
                "rescue_record": [],
                "senior_course_record": [],
            },
        }
    }

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key="luxian_0609_qc_v1",
        prepared_rules=[{"rule_id": rule_id} for rule_id in _LEGACY_RULE_IDS],
        visit_id="visit-basic-native",
        medical_text="",
        evidence_payload=evidence_payload,
        llm_client=None,
        settings=_settings(basic_enabled=True),
        selected_customer_rule_ids=BASIC_TIMELINESS_RULE_IDS,
    )

    assert executable == []
    assert context.legacy_wrapper_rules == []
    assert tuple(item["rule_id"] for item in context.native_results) == BASIC_TIMELINESS_RULE_IDS
    assert context.package_plan is not None
    assert context.package_plan.bypassed_execution_rule_ids == _LEGACY_RULE_IDS


@pytest.mark.unit
@pytest.mark.asyncio
async def test_basic_family_flag_off_preserves_all_legacy_rules():
    raw_rules = [{"rule_id": rule_id} for rule_id in _LEGACY_RULE_IDS]

    executable, context = await luxian_execution.prepare_luxian_0609_execution(
        rule_set_key="luxian_0609_qc_v1",
        prepared_rules=raw_rules,
        visit_id="visit-basic-compatibility",
        medical_text="",
        evidence_payload={},
        llm_client=None,
        settings=_settings(basic_enabled=False),
        selected_customer_rule_ids=BASIC_TIMELINESS_RULE_IDS,
    )

    assert executable == raw_rules
    assert context.native_results == []
    assert [item["rule_id"] for item in context.legacy_wrapper_rules] == list(
        BASIC_TIMELINESS_RULE_IDS
    )
