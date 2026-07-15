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
    "first_course_rows",
    [
        [],
        [{"title": "首次病程记录", "authored_at": "2026-06-01 10:00:00"}],
        [
            {
                "title": "首次病程记录",
                "authored_at": "2026-06-01 10:00:00",
                "text_preview": "仅供列表展示的预览",
                "content_preview": "首次病程记录",
            }
        ],
        [
            {
                "title": "首次病程记录",
                "authored_at": "2026-06-01 10:00:00",
                "assembly_status": "partial",
                "source_fields": [{"field": "record_time"}],
                "sections": [],
                "data_quality_flags": ["body_missing"],
            }
        ],
        [
            {
                "title": "首次病程记录",
                "authored_at": "2026-06-01 10:00:00",
                "content": (
                    "source_table:first_course_record；文书类型：首次病程记录；"
                    "记录时间：2026-06-01 10:00:00；assembly_status:partial"
                ),
            }
        ],
        [
            {
                "title": "首次病程记录",
                "authored_at": "2026-06-01 10:00:00",
                "content": "首次病程记录 2026年06月01日10时00分00秒",
            }
        ],
    ],
)
def test_first_course_shell_or_missing_body_is_data_gap_without_content_echo(
    first_course_rows: list[dict],
):
    marker = "SHELL_MARKER_MUST_NOT_ECHO"
    rows = [dict(item, text_preview=marker) for item in first_course_rows]
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-002",),
        evidence_payload={
            "programmatic_timeline": {
                "admission_time": "2026-06-01 08:00:00",
                "documents": {"first_course_record": rows},
            }
        },
    )

    assert execution.planned_rule_ids == ("LX0609-002",)
    assert len(execution.results) == 1
    result = execution.results[0]
    assert result["status"] == "data_gap"
    assert (
        result["metadata"]["reason_code"]
        == "first_course_substantive_content_unavailable"
    )
    assert result["metadata"]["prompt_tokens"] == 0
    assert result["metadata"]["completion_tokens"] == 0
    assert result["metadata"]["total_tokens"] == 0
    assert marker not in repr(result)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("authored_at", "expected_status"),
    [
        ("2026-06-01 16:00:00", "compliant"),
        ("2026-06-01 16:01:00", "non_compliant"),
    ],
)
def test_first_course_substantive_body_keeps_eight_hour_boundary(
    authored_at: str,
    expected_status: str,
):
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-002",),
        evidence_payload={
            "programmatic_timeline": {
                "admission_time": "2026-06-01 08:00:00",
                "documents": {
                    "first_course_record": [
                        {
                            "title": "首次病程记录",
                            "authored_at": authored_at,
                            "content": "患者入院后完成病史采集、体格检查和初步诊疗分析，记录诊断依据及后续处理计划。",
                        }
                    ]
                },
            }
        },
    )

    assert execution.results[0]["status"] == expected_status
    assert execution.results[0]["metadata"]["total_tokens"] == 0


@pytest.mark.unit
@pytest.mark.parametrize("admission_time_trusted", [False, None])
def test_admission_anchor_rules_reject_untrusted_or_unattested_legal_datetime(
    admission_time_trusted: bool | None,
):
    timeline = {
        "admission_time": "2026-06-01 08:00:00",
        "documents": {
            "admission_record": [
                {"title": "入院记录", "authored_at": "2026-06-01 09:00:00"}
            ],
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
    if admission_time_trusted is not None:
        timeline["admission_time_trusted"] = admission_time_trusted

    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-001", "LX0609-005", "LX0609-006"),
        evidence_payload={"programmatic_timeline": timeline},
    )

    assert [item["status"] for item in execution.results] == ["data_gap"] * 3
    assert {
        item["metadata"]["reason_code"] for item in execution.results
    } == {"trusted_admission_anchor_unavailable"}
    assert all(item["metadata"]["total_tokens"] == 0 for item in execution.results)
    assert "2026-06-01" not in repr(execution.results)


@pytest.mark.unit
def test_untrusted_admission_anchor_does_not_change_002_or_004():
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-002", "LX0609-004"),
        evidence_payload={
            "programmatic_timeline": {
                "admission_time": "2026-06-01 08:00:00",
                "admission_time_trusted": False,
                "documents": {
                    "first_course_record": [
                        {
                            "title": "首次病程记录",
                            "authored_at": "2026-06-01 16:00:00",
                            "content": "患者入院后完成病史采集、体格检查、诊断分析及后续诊疗计划。",
                        }
                    ],
                    "rescue_record": [
                        {
                            "title": "抢救记录",
                            "authored_at": "2026-06-01 15:00:00",
                            "content": "抢救开始时间：2026-06-01 08:30；抢救结束时间：2026-06-01 09:00。",
                        }
                    ],
                },
            }
        },
    )

    assert [item["status"] for item in execution.results] == [
        "compliant",
        "compliant",
    ]
    assert all(item["metadata"]["total_tokens"] == 0 for item in execution.results)


@pytest.mark.unit
def test_admission_anchor_rules_reject_forged_trusted_flag_without_approved_basis():
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-001", "LX0609-005", "LX0609-006"),
        evidence_payload={
            "programmatic_timeline": {
                "admission_time": "2026-06-01 08:00:00",
                "admission_time_basis": "caller_claimed_admission_time",
                "admission_time_trusted": True,
                "documents": {},
            }
        },
    )

    assert [item["status"] for item in execution.results] == ["data_gap"] * 3
    assert all(
        item["metadata"]["reason_code"]
        == "trusted_admission_anchor_unavailable"
        for item in execution.results
    )


@pytest.mark.unit
def test_admission_record_time_is_approved_for_0426_timeliness_rules():
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-001", "LX0609-005", "LX0609-006"),
        evidence_payload={
            "programmatic_timeline": {
                "admission_time": "2026-06-01 08:00:00",
                "admission_time_basis": "admission_record_record_time_fallback",
                "admission_time_trusted": False,
                "documents": {
                    "admission_record": [
                        {
                            "source_table": "admission_record",
                            "title": "入院记录",
                            "authored_at": "2026-06-01 08:00:00",
                        }
                    ],
                    "senior_course_record": [
                        {
                            "title": "主治医师首次查房记录",
                            "author_title": "主治医师",
                            "authored_at": "2026-06-03 08:00:00",
                        },
                        {
                            "title": "主任医师首次查房记录",
                            "author_title": "主任医师",
                            "authored_at": "2026-06-04 08:00:00",
                        },
                    ],
                },
            }
        },
    )

    assert [item["status"] for item in execution.results] == [
        "compliant",
        "compliant",
        "compliant",
    ]
    assert all(item["metadata"]["total_tokens"] == 0 for item in execution.results)


@pytest.mark.unit
@pytest.mark.parametrize(
    "admission_rows",
    [
        [],
        [
            {
                "source_table": "admission_record",
                "title": "入院记录",
                "authored_at": "2026-06-01 09:00:00",
            }
        ],
        [
            {
                "source_table": "discharge_record",
                "title": "入院记录",
                "authored_at": "2026-06-01 08:00:00",
            }
        ],
    ],
)
def test_customer_approved_admission_basis_must_bind_same_admission_record_time(
    admission_rows: list[dict[str, str]],
):
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-001", "LX0609-005", "LX0609-006"),
        evidence_payload={
            "programmatic_timeline": {
                "admission_time": "2026-06-01 08:00:00",
                "admission_time_basis": "admission_record_record_time_fallback",
                "admission_time_trusted": False,
                "documents": {
                    "admission_record": admission_rows,
                    "senior_course_record": [],
                },
            }
        },
    )

    assert [item["status"] for item in execution.results] == ["data_gap"] * 3
    assert {
        item["metadata"]["reason_code"] for item in execution.results
    } == {"trusted_admission_anchor_unavailable"}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("admission_record_time", "attending_time", "senior_time", "expected"),
    [
        (
            "2026-06-02 08:00:00",
            "2026-06-03 08:00:00",
            "2026-06-04 08:00:00",
            ["compliant", "compliant", "compliant"],
        ),
        (
            "2026-06-02 08:01:00",
            "2026-06-03 08:01:00",
            "2026-06-04 08:01:00",
            ["non_compliant", "non_compliant", "non_compliant"],
        ),
    ],
)
def test_trusted_admission_anchor_keeps_24_48_72_hour_boundaries(
    admission_record_time: str,
    attending_time: str,
    senior_time: str,
    expected: list[str],
):
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-001", "LX0609-005", "LX0609-006"),
        evidence_payload={
            "programmatic_timeline": {
                "admission_time": "2026-06-01 08:00:00",
                "admission_time_basis": "timeline_primary_admission_datetime",
                "admission_time_trusted": True,
                "documents": {
                    "admission_record": [
                        {"title": "入院记录", "authored_at": admission_record_time}
                    ],
                    "senior_course_record": [
                        {
                            "title": "主治医师首次查房记录",
                            "author_title": "主治医师",
                            "authored_at": attending_time,
                        },
                        {
                            "title": "主任医师首次查房记录",
                            "author_title": "主任医师",
                            "authored_at": senior_time,
                        },
                    ],
                },
            }
        },
    )

    assert [item["status"] for item in execution.results] == expected
    assert all(item["metadata"]["total_tokens"] == 0 for item in execution.results)


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
                "admission_time_basis": "timeline_primary_admission_datetime",
                "admission_time_trusted": True,
                "documents": {
                    "admission_record": [
                        {"title": "入院记录", "authored_at": "2026-06-01 09:00:00"}
                    ],
                    "first_course_record": [
                        {
                            "title": "首次病程记录",
                            "authored_at": "2026-06-01 10:00:00",
                            "content": "患者入院后已完成病史采集和体格检查，并记录诊断依据、鉴别诊断及后续诊疗计划。",
                        }
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
