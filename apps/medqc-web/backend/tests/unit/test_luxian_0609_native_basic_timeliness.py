from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import execution as luxian_execution
from app.services.luxian_0609 import native_basic_timeliness as basic_timeliness
from app.services.luxian_0609 import source_evidence_reader
from app.services.luxian_0609.native_basic_timeliness import (
    BASIC_TIMELINESS_RULE_IDS,
    execute_luxian_0609_native_basic_timeliness,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)
from app.services.luxian_0609_programmatic_rules import (
    evaluate_luxian_0609_programmatic_rules,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services import sample_programmatic_evidence as programmatic_evidence


_LEGACY_RULE_IDS = ("SC-002", "CL-081", "SC-021", "SC-054", "SC-048", "SC-049", "CL-080")


def _typed_basic_session(
    rows_by_source: dict[str, list[dict]],
    *,
    selected_rule_ids: tuple[str, ...] = (
        "LX0609-001",
        "LX0609-005",
        "LX0609-006",
    ),
    failures: dict[str, Exception] | None = None,
    truncated_sources: frozenset[str] = frozenset(),
    evaluation_as_of_date: str | None = "2026-07-16",
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if failures and source_key in failures:
            raise failures[source_key]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=source_key in truncated_sources,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        evaluation_as_of_date=evaluation_as_of_date,
        row_reader=read,
        additional_source_keys=(
            "admission_record",
            "inpat_registration",
            "daily_course_record",
            "first_course_record",
            "rescue_record",
            "senior_course_record",
        ),
    )


@pytest.mark.unit
def test_004_complete_empty_rescue_records_fail_closed_in_canonical_result() -> None:
    session = _typed_basic_session(
        {"rescue_record": []},
        selected_rule_ids=("LX0609-004",),
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-004",))
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=_rules("LX0609-004"),
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        format_evidence=False,
    )[0]

    assert execution.results == ()
    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "applicability_source_gap"
    assert canonical["status"] == canonical["result_status"] == "data_gap"
    assert canonical["is_compliant"] is None
    assert canonical["reason_code"] == "applicability_source_gap"
    assert canonical["findings"] == "暂无法确认本次住院是否发生抢救"
    assert "缺少可独立证明是否发生抢救的权威事件资料" in canonical["evidence"]
    assert "不能据此确认未发生抢救" in canonical["evidence"]
    assert "权威抢救事件资料" in canonical["suggestion"]
    assert "无需" not in canonical["suggestion"]
    assert getattr(execution, "llm_call_count", 0) == 0
    assert getattr(execution, "total_tokens", 0) == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("rule_id", "evaluation_as_of_date"),
    [
        ("LX0609-001", "2026-06-02"),
        ("LX0609-002", "2026-06-01"),
        ("LX0609-005", "2026-06-03"),
        ("LX0609-006", "2026-06-04"),
    ],
)
def test_missing_timeliness_document_before_maturity_is_not_non_compliant(
    rule_id: str,
    evaluation_as_of_date: str,
):
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
        },
        selected_rule_ids=(rule_id,),
        evaluation_as_of_date=evaluation_as_of_date,
    )

    _, reduced = _reduce_typed_basic(session, (rule_id,))

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "evaluation_window_not_mature"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("rule_id", "evaluation_as_of_date"),
    [
        ("LX0609-001", "2026-06-03"),
        ("LX0609-002", "2026-06-02"),
        ("LX0609-005", "2026-06-04"),
        ("LX0609-006", "2026-06-05"),
    ],
)
def test_missing_timeliness_document_after_maturity_is_data_gap(
    rule_id: str,
    evaluation_as_of_date: str,
):
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
        },
        selected_rule_ids=(rule_id,),
        evaluation_as_of_date=evaluation_as_of_date,
    )

    _, reduced = _reduce_typed_basic(session, (rule_id,))

    if rule_id in {"LX0609-005", "LX0609-006"}:
        assert reduced[0].final_state is CustomerFinalState.DATA_GAP
        assert reduced[0].reason_code == "source_empty"
    else:
        assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
        assert reduced[0].reason_code == "required_document_missing"


@pytest.mark.unit
def test_001_empty_template_after_maturity_is_treated_as_missing_admission_record():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "empty-template",
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 10:00:00",
                    "chief_complaint": " ",
                    "history_of_present_illness": None,
                    "record_content": "入院记录\n记录时间：2026-06-01 10:00:00\n正文：",
                }
            ],
        },
        selected_rule_ids=("LX0609-001",),
        evaluation_as_of_date="2026-06-03",
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-001",))

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "required_document_missing"
    assert dict(execution.customer_display_facts)["LX0609-001"]["timeliness_state"] == "missing"
    assert (
        dict(execution.customer_display_facts)["LX0609-001"]["document_content_state"]
        == "blank_or_placeholder"
    )


@pytest.mark.unit
def test_001_empty_template_before_maturity_keeps_evaluation_window_open():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "empty-template",
                    "record_time": "2026-06-01 10:00:00",
                    "record_content": "入院记录 记录时间 2026-06-01 10:00:00 正文",
                }
            ],
        },
        selected_rule_ids=("LX0609-001",),
        evaluation_as_of_date="2026-06-02",
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-001",))

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "evaluation_window_not_mature"
    assert execution.customer_display_facts == ()


@pytest.mark.unit
@pytest.mark.parametrize(
    "placeholder_body",
    (
        "。",
        "-",
        "--",
        "无",
        "否",
        "无/否",
        "暂无",
        "无特殊",
        "未填",
        "未填写",
        "不详",
        "未知",
        "null",
        "none",
        "主诉：无；现病史：否",
    ),
)
def test_001_short_placeholder_body_is_not_a_substantive_admission_record(
    placeholder_body: str,
):
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "placeholder-template",
                    "record_time": "2026-06-01 10:00:00",
                    "record_content": placeholder_body,
                }
            ],
        },
        selected_rule_ids=("LX0609-001",),
        evaluation_as_of_date="2026-06-03",
    )

    _, reduced = _reduce_typed_basic(session, ("LX0609-001",))

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "required_document_missing"


@pytest.mark.unit
@pytest.mark.parametrize(
    "admission_row",
    (
        {"chief_complaint": "腹痛"},
        {"history_of_present_illness": "腹痛3天"},
    ),
)
def test_001_short_clinical_content_is_a_substantive_admission_record(
    admission_row: dict[str, str],
):
    """001只核对文书是否完成，不能把短但真实的临床内容当作空模板。"""

    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "short-clinical-document",
                    "record_time": "2026-06-01 10:00:00",
                    **admission_row,
                }
            ],
        },
        selected_rule_ids=("LX0609-001",),
        evaluation_as_of_date="2026-06-03",
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-001",))

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_within_threshold"
    assert dict(execution.customer_display_facts)["LX0609-001"]["source_document_id"] == (
        "short-clinical-document"
    )


@pytest.mark.unit
def test_001_substantive_admission_record_without_authoritative_time_is_data_gap():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "substantive-without-time",
                    "chief_complaint": "反复腹痛三天",
                }
            ],
        },
        selected_rule_ids=("LX0609-001",),
        evaluation_as_of_date="2026-06-03",
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-001",))

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "authoritative_time_missing"
    assert execution.customer_display_facts == ()


@pytest.mark.unit
def test_001_ignores_earlier_empty_template_and_uses_substantive_document():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "empty-template",
                    "record_time": "2026-06-01 09:00:00",
                    "record_content": "入院记录 记录时间 2026-06-01 09:00:00 正文",
                },
                {
                    "document_id": "substantive-document",
                    "record_time": "2026-06-01 10:00:00",
                    "history_of_present_illness": "患者反复腹痛三天后入院。",
                },
            ],
        },
        selected_rule_ids=("LX0609-001",),
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-001",))

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_within_threshold"
    facts = dict(execution.customer_display_facts)["LX0609-001"]
    assert facts["observed_time"] == "2026-06-01 10:00:00"
    assert facts["source_document_id"] == "substantive-document"


@pytest.mark.unit
def test_missing_timeliness_document_with_negative_evaluation_interval_fails_closed():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
        },
        selected_rule_ids=("LX0609-001",),
        evaluation_as_of_date="2026-05-31",
    )

    _, reduced = _reduce_typed_basic(session, ("LX0609-001",))

    assert reduced[0].final_state is CustomerFinalState.EVALUATION_UNKNOWN
    assert reduced[0].reason_code == "evidence_conflict"


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


def _private_course_rows(attending_time: str, senior_time: str) -> dict[str, list[dict]]:
    return {
        "daily_course_record": [
            {
                "document_id": "safe-attending-ref",
                "title": "主治医师首次查房记录",
                "authored_at": attending_time,
                "source_table": "daily_course_record",
            }
        ],
        "senior_course_record": [
            {
                "document_id": "safe-senior-ref",
                "title": "副主任医师首次查房记录",
                "authored_at": senior_time,
                "source_table": "senior_course_record",
            }
        ],
    }


def _reduce_typed_basic(
    session,
    rule_ids: tuple[str, ...] = (
        "LX0609-001",
        "LX0609-005",
        "LX0609-006",
    ),
):
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=rule_ids,
        decision_rule_ids=rule_ids,
        evidence_payload=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=rule_ids,
        snapshot=session.snapshot,
    )
    return execution, reduced


@pytest.mark.unit
def test_001_005_006_emit_snapshot_bound_python_decisions_from_one_admission_anchor():
    session = _typed_basic_session(
        {
            "inpat_registration": [],
            "admission_record": [
                {
                    "document_id": "safe-admission-ref",
                    "document_title": "入院记录",
                    "admission_datetime": "2026-06-01 08:00:00",
                    "record_time": "2026-06-01 08:00:00",
                    "chief_complaint": "反复腹痛三天",
                }
            ],
            "daily_course_record": [
                {
                    "document_id": "safe-attending-ref",
                    "document_title": "主治医师首次查房记录",
                    "record_time": "2026-06-02 08:00:00",
                }
            ],
            "senior_course_record": [
                {
                    "document_id": "safe-senior-ref",
                    "document_title": "副主任医师首次查房记录",
                    "record_time": "2026-06-03 08:00:00",
                }
            ],
        }
    )

    execution, reduced = _reduce_typed_basic(session)

    assert execution.results == ()
    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    assert all(item.fact_refs for item in reduced)
    assert execution.customer_display_facts == (
        (
            "LX0609-001",
            {
                "failure_kind": "timeliness_requirement_satisfied",
                "target_document": "admission_record",
                "source_label": "入院记录",
                "timeliness_state": "within",
                "threshold_hours": 24,
                "anchor_time": "2026-06-01 08:00:00",
                "observed_time": "2026-06-01 08:00:00",
                "elapsed_hours": 0.0,
                "remaining_hours": 24.0,
                "source_document_id": "safe-admission-ref",
            },
        ),
        (
            "LX0609-005",
            {
                "failure_kind": "timeliness_requirement_satisfied",
                "target_document": "attending_course_record",
                "source_label": "主治医师及以上首次查房记录",
                "timeliness_state": "within",
                "threshold_hours": 48,
                "anchor_time": "2026-06-01 08:00:00",
                "observed_time": "2026-06-02 08:00:00",
                "elapsed_hours": 24.0,
                "remaining_hours": 24.0,
                "source_document_id": "safe-attending-ref",
            },
        ),
        (
            "LX0609-006",
            {
                "failure_kind": "timeliness_requirement_satisfied",
                "target_document": "senior_course_record",
                "source_label": "副主任医师或主任医师首次查房记录",
                "timeliness_state": "within",
                "threshold_hours": 72,
                "anchor_time": "2026-06-01 08:00:00",
                "observed_time": "2026-06-03 08:00:00",
                "elapsed_hours": 48.0,
                "remaining_hours": 24.0,
                "source_document_id": "safe-senior-ref",
            },
        ),
    )


@pytest.mark.unit
def test_001_compliant_keeps_time_facts_without_guessing_a_missing_document_id():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 10:00:00",
                    "chief_complaint": "反复腹痛三天",
                }
            ],
            "daily_course_record": [],
            "senior_course_record": [],
        },
        selected_rule_ids=("LX0609-001",),
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-001",))

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert execution.customer_display_facts == (
        (
            "LX0609-001",
            {
                "failure_kind": "timeliness_requirement_satisfied",
                "target_document": "admission_record",
                "source_label": "入院记录",
                "timeliness_state": "within",
                "threshold_hours": 24,
                "anchor_time": "2026-06-01 08:00:00",
                "observed_time": "2026-06-01 10:00:00",
                "elapsed_hours": 2.0,
                "remaining_hours": 22.0,
            },
        ),
    )


@pytest.mark.unit
def test_001_time_conflict_exposes_both_times_and_exact_lead_for_customer_projection():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-08-16 22:39:10"}
            ],
            "admission_record": [
                {
                    "document_id": "admission-conflict-document",
                    "document_title": "入院记录",
                    "record_time": "2026-08-16 22:20:29",
                    "chief_complaint": "左侧腹股沟包块伴不适半年",
                }
            ],
            "daily_course_record": [],
            "senior_course_record": [],
        },
        selected_rule_ids=("LX0609-001",),
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-001",))

    assert reduced[0].final_state is CustomerFinalState.EVALUATION_UNKNOWN
    assert reduced[0].reason_code == "evidence_conflict"
    assert execution.customer_display_facts == (
        (
            "LX0609-001",
            {
                "failure_kind": "evidence_time_conflict",
                "target_document": "admission_record",
                "source_label": "入院记录",
                "timeliness_state": "before",
                "threshold_hours": 24,
                "anchor_time": "2026-08-16 22:39:10",
                "observed_time": "2026-08-16 22:20:29",
                "time_conflict_seconds": 1121,
                "source_document_id": "admission-conflict-document",
            },
        ),
    )


@pytest.mark.unit
def test_typed_basic_timeliness_projects_only_safe_late_or_missing_explanation_facts():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "admission-private-id",
                    "document_title": "入院记录",
                    "record_time": "2026-06-02 10:00:00",
                    "history_of_present_illness": "患者反复腹痛三天后入院。",
                }
            ],
            "daily_course_record": [],
            "senior_course_record": [],
        }
    )

    execution, reduced = _reduce_typed_basic(session)

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.NON_COMPLIANT,
        CustomerFinalState.DATA_GAP,
        CustomerFinalState.DATA_GAP,
    ]
    assert execution.customer_display_facts == (
        (
            "LX0609-001",
            {
                "failure_kind": "timeliness_requirement_not_met",
                "target_document": "admission_record",
                "source_label": "入院记录",
                "timeliness_state": "late",
                "threshold_hours": 24,
                "anchor_time": "2026-06-01 08:00:00",
                "observed_time": "2026-06-02 10:00:00",
                "elapsed_hours": 26.0,
                "overdue_hours": 2.0,
                "source_document_id": "admission-private-id",
            },
        ),
    )
    assert [item.reason_code for item in reduced] == [
        "threshold_exceeded",
        "source_empty",
        "source_empty",
    ]


@pytest.mark.unit
def test_002_006_accept_authoritative_submit_datetime_used_by_customer_documents():
    """客户同步文书以 submit_datetime 展示记录时间时，原生时限链必须使用同一权威值。"""

    selected = ("LX0609-002", "LX0609-006")
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-13 10:00:00"}
            ],
            "admission_record": [],
            "first_course_record": [
                {
                    "document_id": "safe-first-course-ref",
                    "document_title": "首次病程记录",
                    "record_time": " ",
                    "submit_datetime": "2026-06-13 15:57:27",
                    "record_content": "患者入院后完成病史采集、体格检查及初步诊疗计划。",
                }
            ],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_id": "safe-senior-ref",
                    "document_title": "王飞副主任医师查房记录",
                    "submit_datetime": "2026-06-15 08:00:00",
                }
            ],
        },
        selected_rule_ids=selected,
    )

    _, reduced = _reduce_typed_basic(session, selected)

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    assert {item.reason_code for item in reduced} == {
        "requirement_within_threshold"
    }


@pytest.mark.unit
def test_001_002_accept_the_localized_customer_record_time_and_document_identity():
    """客户源 record_time/sys_index_id 经同步映射后必须形成可定位的确定结论。"""

    selected = ("LX0609-001", "LX0609-002")
    session = _typed_basic_session(
        {
            "inpat_registration": [],
            "admission_record": [
                {
                    "document_id": "101",
                    "document_title": "入院记录",
                    "admission_datetime": "2026-08-16 20:00:00",
                    "record_datetime": "2026-08-16 22:20:29",
                    "chief_complaint": "左侧腹股沟包块伴不适半年",
                }
            ],
            "first_course_record": [
                {
                    "document_id": "102",
                    "document_title": "首次病程记录",
                    "record_datetime": "2026-08-16 22:38:08",
                    "case_characteristic": "患者为31岁男性，起病缓，病程长。",
                }
            ],
            "daily_course_record": [],
            "senior_course_record": [],
        },
        selected_rule_ids=selected,
    )

    execution, reduced = _reduce_typed_basic(session, selected)

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    facts = dict(execution.customer_display_facts)
    assert facts["LX0609-001"]["source_document_id"] == "101"
    assert facts["LX0609-002"]["source_document_id"] == "102"


@pytest.mark.unit
def test_001_005_006_do_not_use_admission_record_time_as_its_own_anchor():
    session = _typed_basic_session(
        {
            "inpat_registration": [],
            "admission_record": [
                {
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 08:00:00",
                }
            ],
            "daily_course_record": [
                {
                    "document_title": "主治医师首次查房记录",
                    "record_time": "2026-06-02 08:00:00",
                }
            ],
            "senior_course_record": [
                {
                    "document_title": "副主任医师首次查房记录",
                    "record_time": "2026-06-03 08:00:00",
                }
            ],
        }
    )

    _, reduced = _reduce_typed_basic(session)

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.DATA_GAP,
        CustomerFinalState.DATA_GAP,
        CustomerFinalState.DATA_GAP,
    ]
    assert {item.reason_code for item in reduced} == {
        "authoritative_time_missing"
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    (
        "admission_record_time",
        "attending_time",
        "senior_time",
        "expected_state",
        "expected_reason",
    ),
    [
        (
            "2026-06-01 23:59:59",
            "2026-06-02 23:59:59",
            "2026-06-03 23:59:59",
            CustomerFinalState.COMPLIANT,
            "requirement_within_threshold",
        ),
        (
            "2026-06-02 12:00:00",
            "2026-06-03 12:00:00",
            "2026-06-04 12:00:00",
            CustomerFinalState.DATA_GAP,
            "authoritative_time_missing",
        ),
        (
            "2026-06-03 00:00:00",
            "2026-06-04 00:00:00",
            "2026-06-05 00:00:00",
            CustomerFinalState.NON_COMPLIANT,
            "threshold_exceeded",
        ),
    ],
)
def test_001_005_006_use_discharge_admission_date_only_for_conclusive_boundaries(
    admission_record_time: str,
    attending_time: str,
    senior_time: str,
    expected_state: CustomerFinalState,
    expected_reason: str,
):
    """只有日期时按全天区间计算；边界不确定不得猜测入院时分秒。"""

    session = _typed_basic_session(
        {
            "inpat_registration": [],
            "admission_record": [
                {
                    "document_title": "入院记录",
                    "record_time": admission_record_time,
                    "chief_complaint": "反复腹痛三天",
                }
            ],
            "discharge_record": [{"admission_date": "2026-06-01"}],
            "daily_course_record": [
                {
                    "document_title": "主治医师首次查房记录",
                    "record_time": attending_time,
                }
            ],
            "senior_course_record": [
                {
                    "document_title": "副主任医师首次查房记录",
                    "record_time": senior_time,
                }
            ],
        }
    )

    _, reduced = _reduce_typed_basic(session)

    assert [item.final_state for item in reduced] == [expected_state] * 3
    assert {item.reason_code for item in reduced} == {expected_reason}
    assert all("2026-06" not in repr(item) for item in reduced)


@pytest.mark.unit
def test_001_005_006_exact_admission_datetime_wins_over_discharge_date_fallback():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-10 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_title": "入院记录",
                    "record_time": "2026-06-11 08:00:00",
                    "chief_complaint": "反复腹痛三天",
                }
            ],
            "discharge_record": [{"admission_date": "2026-06-01"}],
            "daily_course_record": [
                {
                    "document_title": "主治医师首次查房记录",
                    "record_time": "2026-06-12 08:00:00",
                }
            ],
            "senior_course_record": [
                {
                    "document_title": "副主任医师首次查房记录",
                    "record_time": "2026-06-13 08:00:00",
                }
            ],
        }
    )

    _, reduced = _reduce_typed_basic(session)

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    assert {item.reason_code for item in reduced} == {
        "requirement_within_threshold"
    }


@pytest.mark.unit
@pytest.mark.parametrize("incomplete_time", ["2026-06-01", "2026-06-01T08"])
def test_001_005_006_reject_incomplete_admission_datetime(incomplete_time: str):
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": incomplete_time}
            ],
            "admission_record": [
                {
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 09:00:00",
                }
            ],
            "daily_course_record": [],
            "senior_course_record": [],
        }
    )

    _, reduced = _reduce_typed_basic(session)

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.DATA_GAP,
        CustomerFinalState.DATA_GAP,
        CustomerFinalState.DATA_GAP,
    ]
    assert {item.reason_code for item in reduced} == {
        "authoritative_time_missing"
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("record_time", "record_content", "expected_state", "expected_reason"),
    [
        (
            "2026-06-01 16:00:00",
            "患者入院后完成病史采集、体格检查和诊疗计划。",
            CustomerFinalState.COMPLIANT,
            "requirement_within_threshold",
        ),
        (
            "2026-06-01 16:00:01",
            "患者入院后完成病史采集、体格检查和诊疗计划。",
            CustomerFinalState.NON_COMPLIANT,
            "threshold_exceeded",
        ),
        (
            None,
            "首次病程记录 记录时间",
            CustomerFinalState.DATA_GAP,
            "required_field_missing",
        ),
    ],
)
def test_002_uses_authoritative_first_course_time_without_model(
    record_time,
    record_content: str,
    expected_state: CustomerFinalState,
    expected_reason: str,
):
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [],
            "first_course_record": [
                {
                    "document_title": "首次病程记录",
                    "record_time": record_time,
                    "record_content": record_content,
                }
            ],
        },
        selected_rule_ids=("LX0609-002",),
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-002",))

    assert execution.results == ()
    assert reduced[0].final_state is expected_state
    assert reduced[0].reason_code == expected_reason
    assert "诊疗计划" not in repr(reduced[0])


def test_002_late_result_exposes_actual_and_overdue_hours():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [],
            "first_course_record": [
                {
                    "document_title": "首次病程记录",
                    "record_time": "2026-06-01 18:30:00",
                    "record_content": "患者入院后完成病史采集、体格检查和诊疗计划。",
                }
            ],
        },
        selected_rule_ids=("LX0609-002",),
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-002",))

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert dict(execution.customer_display_facts)["LX0609-002"] == {
        "failure_kind": "timeliness_requirement_not_met",
        "target_document": "first_course_record",
        "source_label": "首次病程记录",
        "timeliness_state": "late",
        "threshold_hours": 8,
        "anchor_time": "2026-06-01 08:00:00",
        "observed_time": "2026-06-01 18:30:00",
        "elapsed_hours": 10.5,
        "overdue_hours": 2.5,
    }


def test_002_compliant_result_exposes_actual_interval_and_source_document():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [],
            "first_course_record": [
                {
                    "document_id": "first-course-safe-ref",
                    "document_title": "首次病程记录",
                    "record_time": "2026-06-01 10:30:00",
                    "record_content": "患者入院后完成病史采集、体格检查和诊疗计划。",
                }
            ],
        },
        selected_rule_ids=("LX0609-002",),
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-002",))

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert dict(execution.customer_display_facts)["LX0609-002"] == {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "first_course_record",
        "source_label": "首次病程记录",
        "timeliness_state": "within",
        "threshold_hours": 8,
        "anchor_time": "2026-06-01 08:00:00",
        "observed_time": "2026-06-01 10:30:00",
        "elapsed_hours": 2.5,
        "remaining_hours": 5.5,
        "source_document_id": "first-course-safe-ref",
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("rows", "expected_state", "expected_reason"),
    [
        ([], CustomerFinalState.DATA_GAP, "applicability_source_gap"),
        (
            [
                {
                    "record_time": "2026-06-01 14:00:00",
                    "record_content": "抢救结束时间：2026-06-01 08:00:00",
                }
            ],
            CustomerFinalState.COMPLIANT,
            "requirement_within_threshold",
        ),
        (
            [
                {
                    "record_time": "2026-06-01 14:00:01",
                    "record_content": "抢救结束时间：2026-06-01 08:00:00",
                }
            ],
            CustomerFinalState.NON_COMPLIANT,
            "threshold_exceeded",
        ),
        (
            [
                {
                    "record_time": "2026-06-01 10:00:00",
                    "record_content": "拟抢救结束时间：2026-06-01 08:00:00",
                }
            ],
            CustomerFinalState.DATA_GAP,
            "required_field_missing",
        ),
    ],
)
def test_004_uses_exact_rescue_end_label_without_model(
    rows: list[dict],
    expected_state: CustomerFinalState,
    expected_reason: str,
):
    session = _typed_basic_session(
        {"rescue_record": rows},
        selected_rule_ids=("LX0609-004",),
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-004",))

    assert execution.results == ()
    assert reduced[0].final_state is expected_state
    assert reduced[0].reason_code == expected_reason
    assert "抢救结束时间" not in repr(reduced[0])


@pytest.mark.unit
def test_004_projects_safe_late_rescue_timeline_facts() -> None:
    session = _typed_basic_session(
        {
            "rescue_record": [
                {
                    "document_id": "rescue-private-id",
                    "record_time": "2026-06-01 16:15:00",
                    "record_content": "抢救结束时间：2026年06月01日 09:00。",
                }
            ]
        },
        selected_rule_ids=("LX0609-004",),
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-004",))

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert execution.customer_display_facts == (
        (
            "LX0609-004",
            {
                "failure_kind": "timeliness_requirement_not_met",
                "target_document": "rescue_record",
                "source_label": "抢救记录",
                "timeliness_state": "late",
                "threshold_hours": 6,
                "anchor_time": "2026-06-01 09:00:00",
                "observed_time": "2026-06-01 16:15:00",
                "elapsed_hours": 7.25,
                "overdue_hours": 1.25,
                "source_document_id": "rescue-private-id",
            },
        ),
    )


@pytest.mark.unit
def test_004_compliant_result_projects_worst_rescue_interval() -> None:
    session = _typed_basic_session(
        {
            "rescue_record": [
                {
                    "document_id": "rescue-first",
                    "record_time": "2026-06-01 11:00:00",
                    "record_content": "抢救结束时间：2026年06月01日 09:00。",
                },
                {
                    "document_id": "rescue-worst",
                    "record_time": "2026-06-02 15:30:00",
                    "record_content": "抢救结束时间：2026年06月02日 10:00。",
                },
            ]
        },
        selected_rule_ids=("LX0609-004",),
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-004",))

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert dict(execution.customer_display_facts)["LX0609-004"] == {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "rescue_record",
        "source_label": "抢救记录",
        "timeliness_state": "within",
        "threshold_hours": 6,
        "anchor_time": "2026-06-02 10:00:00",
        "observed_time": "2026-06-02 15:30:00",
        "elapsed_hours": 5.5,
        "remaining_hours": 0.5,
        "source_document_id": "rescue-worst",
    }


@pytest.mark.unit
def test_004_uses_submit_datetime_and_keeps_late_evidence_ref() -> None:
    session = _typed_basic_session(
        {
            "rescue_record": [
                {
                    "document_id": "rescue-submit-ref",
                    "submit_datetime": "2026-06-01 15:00:01",
                    "record_content": "抢救结束时间：2026-06-01 09:00:00",
                }
            ]
        },
        selected_rule_ids=("LX0609-004",),
    )

    execution, reduced = _reduce_typed_basic(session, ("LX0609-004",))

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(execution.customer_display_facts)["LX0609-004"]
    assert facts["source_document_id"] == "rescue-submit-ref"
    assert facts["elapsed_hours"] == pytest.approx(6.0, abs=0.01)
    assert facts["overdue_hours"] == pytest.approx(0.0, abs=0.01)


@pytest.mark.unit
def test_conflicting_admission_anchors_fail_closed_for_all_anchor_rules() -> None:
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"},
                {"admission_datetime": "2026-06-01 09:00:00"},
            ],
            "admission_record": [
                {
                    "document_id": "admission-1",
                    "record_time": "2026-06-01 10:00:00",
                }
            ],
            **_private_course_rows(
                "2026-06-02 10:00:00",
                "2026-06-03 10:00:00",
            ),
        }
    )

    _execution, reduced = _reduce_typed_basic(session)

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.EVALUATION_UNKNOWN,
        CustomerFinalState.EVALUATION_UNKNOWN,
        CustomerFinalState.EVALUATION_UNKNOWN,
    ]
    assert {item.reason_code for item in reduced} == {"evidence_conflict"}


@pytest.mark.unit
def test_complete_empty_and_unavailable_rescue_sources_are_distinct() -> None:
    complete = _typed_basic_session({}, selected_rule_ids=("LX0609-004",))
    unavailable = _typed_basic_session(
        {},
        selected_rule_ids=("LX0609-004",),
        failures={"rescue_record": SourceEvidenceUnavailable()},
    )

    _complete_execution, complete_reduced = _reduce_typed_basic(
        complete, ("LX0609-004",)
    )
    _unavailable_execution, unavailable_reduced = _reduce_typed_basic(
        unavailable, ("LX0609-004",)
    )

    assert complete_reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert complete_reduced[0].reason_code == "applicability_source_gap"
    assert unavailable_reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert unavailable_reduced[0].reason_code == "source_unavailable"


@pytest.mark.unit
def test_001_005_006_typed_thresholds_are_exact_and_senior_satisfies_attending_or_above():
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_title": "入院记录",
                    "record_time": "2026-06-02 08:00:01",
                    "chief_complaint": "反复腹痛三天",
                }
            ],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_title": "副主任医师首次查房记录",
                    "record_time": "2026-06-03 08:00:00",
                }
            ],
        }
    )

    _, reduced = _reduce_typed_basic(session)

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.NON_COMPLIANT,
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    assert [item.reason_code for item in reduced] == [
        "threshold_exceeded",
        "requirement_within_threshold",
        "requirement_within_threshold",
    ]


@pytest.mark.unit
def test_2496813_basic_timeliness_002_004_005_matches_source_truth():
    selected = ("LX0609-002", "LX0609-004", "LX0609-005")
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-07-07 13:55:17"}
            ],
            "admission_record": [],
            "first_course_record": [
                {
                    "document_title": "首次病程记录",
                    "record_datetime": "2026-07-07 18:00:41",
                    "record_content": "",
                    "case_characteristic": (
                        "患者为54岁女性，起病急，病程短；摔倒致头面部外伤、"
                        "持续出血、呼唤无反应，伴肢体不自主抖动。"
                    ),
                }
            ],
            "rescue_record": [
                {
                    "record_time": "2026-07-07 17:50:15",
                    "record_content": (
                        "抢救开始时间：2026年07月07日 14:20       "
                        "抢救结束时间:2026年07月07日 14:30 "
                        "患者经抢救后生命体征相对稳定。"
                    ),
                }
            ],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_title": "主刀医师韩平副主任医师查房记录",
                    "record_time": "2026-07-07 15:10:30",
                }
            ],
        },
        selected_rule_ids=selected,
    )

    execution, reduced = _reduce_typed_basic(session, selected)

    assert execution.results == ()
    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    assert {item.reason_code for item in reduced} == {
        "requirement_within_threshold"
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("scenario", "expected_state", "expected_reason"),
    [
        ("missing_time", CustomerFinalState.DATA_GAP, "authoritative_time_missing"),
        ("ambiguous_role", CustomerFinalState.DATA_GAP, "required_field_missing"),
        ("unavailable", CustomerFinalState.DATA_GAP, "source_unavailable"),
        ("query_error", CustomerFinalState.TECHNICAL_ERROR, "source_query_error"),
        ("truncated", CustomerFinalState.DATA_GAP, "source_truncated"),
    ],
)
def test_005_006_typed_fail_closed_without_text_time_guess(
    scenario: str,
    expected_state: CustomerFinalState,
    expected_reason: str,
):
    failures = {}
    truncated = frozenset()
    rows = {
        "inpat_registration": [],
        "admission_record": [
            {
                "document_title": "入院记录",
                "admission_datetime": "2026-06-01 07:00:00",
                "record_time": "2026-06-01 08:00:00",
            }
        ],
        "daily_course_record": [],
        "senior_course_record": [],
    }
    if scenario == "missing_time":
        rows["senior_course_record"] = [
            {
                "document_title": "副主任医师首次查房记录",
                "record_time": None,
                "update_time": "2026-06-02 08:00:00",
            }
        ]
    elif scenario == "ambiguous_role":
        rows["senior_course_record"] = [
            {
                "document_title": "医师查房记录",
                "record_time": "2026-06-02 08:00:00",
            }
        ]
    elif scenario == "unavailable":
        failures["senior_course_record"] = SourceEvidenceUnavailable()
    elif scenario == "query_error":
        failures["senior_course_record"] = SourceEvidenceQueryError()
    else:
        rows["senior_course_record"] = [
            {
                "document_title": "主治医师首次查房记录",
                "record_time": "2026-06-02 08:00:00",
            }
        ]
        truncated = frozenset({"senior_course_record"})
    session = _typed_basic_session(
        rows,
        failures=failures,
        truncated_sources=truncated,
    )

    _, reduced = _reduce_typed_basic(session)

    # 006 正好覆盖高级别查房；005在同一来源异常/字段缺失时也必须保守。
    target = reduced[2]
    assert target.final_state is expected_state
    assert target.reason_code == expected_reason
    assert "2026-06" not in repr(target)


@pytest.mark.unit
def test_005_accepts_customer_standard_upper_physician_round_within_48_hours():
    selected = ("LX0609-005", "LX0609-006")
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-07-15 13:48:49"}
            ],
            "admission_record": [],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_id": "safe-upper-round-ref",
                    "document_title": "上级医师查房记录",
                    "record_time": "2026-07-16 10:30:02",
                }
            ],
        },
        selected_rule_ids=selected,
    )

    execution, reduced = _reduce_typed_basic(session, selected)

    assert execution.results == ()
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_within_threshold"
    facts = dict(execution.customer_display_facts)
    assert facts["LX0609-005"]["source_document_id"] == "safe-upper-round-ref"
    assert facts["LX0609-005"]["elapsed_hours"] == 20.69
    # “上级医师”只满足主治医师及以上，不得放宽副主任/主任医师规则。
    assert reduced[1].final_state is not CustomerFinalState.COMPLIANT


@pytest.mark.unit
def test_005_accepts_senior_course_source_without_redundant_document_title():
    selected = ("LX0609-005", "LX0609-006")
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-07-15 13:48:49"}
            ],
            "admission_record": [],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_id": "upper-round-without-title",
                    "record_time": "2026-07-16 10:30:02",
                    "record_content": "上级医师查房记录正文。",
                }
            ],
        },
        selected_rule_ids=selected,
    )

    execution, reduced = _reduce_typed_basic(session, selected)

    assert execution.results == ()
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_within_threshold"
    facts = dict(execution.customer_display_facts)
    assert facts["LX0609-005"]["source_document_id"] == "upper-round-without-title"
    assert facts["LX0609-005"]["elapsed_hours"] == 20.69
    # 来源身份只证明“上级医师”，不能自动升级为副主任医师或主任医师。
    assert reduced[1].final_state is not CustomerFinalState.COMPLIANT


@pytest.mark.unit
def test_006_explicit_senior_round_remains_zero_llm_call():
    class _LLM:
        async def generate(self, _prompt: str) -> dict:
            raise AssertionError("结构化职称已明确时不应调用模型")

    selected = ("LX0609-006",)
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-07-15 13:48:49"}
            ],
            "admission_record": [],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_id": "explicit-senior-round-ref",
                    "document_title": "主任医师首次查房记录",
                    "record_time": "2026-07-16 10:30:02",
                    "record_content": "今日主任医师查房。",
                },
                {
                    "document_id": "generic-upper-round-ref",
                    "document_title": "上级医师查房记录",
                    "record_time": "2026-07-16 11:00:02",
                    "record_content": "今日上级医师查房。",
                },
            ],
        },
        selected_rule_ids=selected,
    )

    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=selected,
        decision_rule_ids=selected,
        evidence_payload=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=_LLM(),
    )
    assert not hasattr(execution, "__await__")
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=selected,
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_within_threshold"


@pytest.mark.unit
def test_006_recognizes_explicit_senior_round_role_from_customer_record_body():
    selected = ("LX0609-006",)
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-08-13 10:13:00"}
            ],
            "admission_record": [],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_id": "zhang-yunhai-senior-round",
                    "record_time": "2026-08-14 09:30:38",
                    "record_content": (
                        "今日张云海副主任医师查房后指出:患者一般情况尚可。"
                    ),
                }
            ],
        },
        selected_rule_ids=selected,
    )

    execution, reduced = _reduce_typed_basic(session, selected)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_within_threshold"
    facts = dict(execution.customer_display_facts)
    assert facts["LX0609-006"]["source_document_id"] == (
        "zhang-yunhai-senior-round"
    )
    assert facts["LX0609-006"]["elapsed_hours"] == 23.29
    assert not hasattr(execution, "__await__")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_006_uses_one_bounded_semantic_call_for_upper_physician_round_body():
    class _LLM:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def generate(self, prompt: str) -> dict:
            self.prompts.append(prompt)
            return {
                "content": (
                    '{"schema_version":"lx0609-006-round-role-v1",'
                    '"documents":[{"position":1,"role":"senior",'
                    '"physician_name":"彭中","physician_title":"主任医师",'
                    '"evidence_quote":"今日彭中主任医师联合神经疾病"}]}'
                ),
                "usage": {
                    "prompt_tokens": 40,
                    "completion_tokens": 12,
                    "total_tokens": 52,
                },
                "response_time": 0.2,
            }

    selected = ("LX0609-005", "LX0609-006")
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-07-15 13:48:49"}
            ],
            "admission_record": [],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_id": "safe-upper-round-ref",
                    "document_title": "上级医师查房记录",
                    "record_time": "2026-07-16 10:30:02",
                    "record_content": "今日彭中主任医师联合神经疾病相关专业医师查房。",
                }
            ],
        },
        selected_rule_ids=selected,
    )
    llm = _LLM()

    execution = await execute_luxian_0609_native_basic_timeliness(
        rule_ids=selected,
        decision_rule_ids=selected,
        evidence_payload=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=llm,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=selected,
        snapshot=session.snapshot,
    )

    assert len(llm.prompts) == 1
    assert "safe-upper-round-ref" not in llm.prompts[0]
    assert execution.llm_call_count == 1
    assert execution.total_tokens == 52
    assert reduced[1].final_state is CustomerFinalState.COMPLIANT
    assert reduced[1].reason_code == "requirement_within_threshold"
    facts = dict(execution.customer_display_facts)
    assert facts["LX0609-006"]["source_document_id"] == "safe-upper-round-ref"
    assert facts["LX0609-006"]["elapsed_hours"] == 20.69


@pytest.mark.unit
@pytest.mark.asyncio
async def test_006_rejects_semantic_role_when_quote_is_not_in_same_document():
    class _LLM:
        async def generate(self, _prompt: str) -> dict:
            return {
                "content": (
                    '{"schema_version":"lx0609-006-round-role-v1",'
                    '"documents":[{"position":1,"role":"senior",'
                    '"physician_name":"彭中","physician_title":"主任医师",'
                    '"evidence_quote":"伪造的彭中主任医师查房证据"}]}'
                ),
                "usage": {"prompt_tokens": 30, "completion_tokens": 10},
            }

    selected = ("LX0609-006",)
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-07-15 13:48:49"}
            ],
            "admission_record": [],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_id": "safe-upper-round-ref",
                    "document_title": "上级医师查房记录",
                    "record_time": "2026-07-16 10:30:02",
                    "record_content": "今日主治医师查房，患者病情稳定。",
                }
            ],
        },
        selected_rule_ids=selected,
    )

    execution = await execute_luxian_0609_native_basic_timeliness(
        rule_ids=selected,
        decision_rule_ids=selected,
        evidence_payload=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=_LLM(),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=selected,
        snapshot=session.snapshot,
    )

    assert execution.llm_call_count == 1
    assert execution.total_tokens == 40
    assert reduced[0].final_state is CustomerFinalState.EVALUATION_UNKNOWN
    assert reduced[0].reason_code == "semantic_output_unknown"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_006_unavailable_llm_does_not_report_unaccounted_call():
    selected = ("LX0609-006",)
    session = _typed_basic_session(
        {
            "inpat_registration": [
                {"admission_datetime": "2026-07-15 13:48:49"}
            ],
            "admission_record": [],
            "daily_course_record": [],
            "senior_course_record": [
                {
                    "document_id": "safe-upper-round-ref",
                    "document_title": "上级医师查房记录",
                    "record_time": "2026-07-16 10:30:02",
                    "record_content": "今日彭中主任医师联合神经疾病相关专业医师查房。",
                }
            ],
        },
        selected_rule_ids=selected,
    )

    execution = await execute_luxian_0609_native_basic_timeliness(
        rule_ids=selected,
        decision_rule_ids=selected,
        evidence_payload=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=object(),
    )

    assert execution.llm_call_count == 0
    assert execution.prompt_tokens == 0
    assert execution.completion_tokens == 0
    assert execution.total_tokens == 0
    assert execution.decisions[0].reason_code == "semantic_output_unknown"


@pytest.mark.unit
def test_course_reader_uses_exact_coordinates_stable_order_and_safe_refs(monkeypatch):
    captured: list[tuple[str, dict]] = []

    class _Rows:
        def __init__(self, rows):
            self.rows = rows

        def mappings(self):
            return self

        def all(self):
            return list(self.rows)

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, params):
            sql = str(statement)
            captured.append((sql, dict(params)))
            return _Rows(
                [
                    {
                        "document_id": "RAW-DOCUMENT-ID",
                        "document_title": "副主任医师查房记录",
                        "record_time": "2026-06-02 08:00:00",
                    }
                ]
            )

    class _Engine:
        def connect(self):
            return _Connection()

    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _Engine())
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda *_args: {
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "document_title",
            "record_time",
        },
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_qualified_table",
        lambda _schema, table: f'"cdm"."{table}"',
    )

    rows = source_evidence_reader.read_luxian_0609_course_round_timeline(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
    )

    assert len(captured) == 2
    for sql, params in captured:
        assert '"institute_id" = :institute_id' in sql
        assert '"patient_id" = :patient_id' in sql
        assert '"visit_id" = :visit_id' in sql
        assert sql.index('ORDER BY "record_time" ASC NULLS LAST') < sql.index("LIMIT")
        assert params["institute_id"] == "I"
        assert params["patient_id"] == "P"
        assert params["visit_id"] == "V"
        assert params["limit_rows"] == (
            source_evidence_reader._source_limit("daily_course_record") + 1
        )
    assert "RAW-DOCUMENT-ID" not in repr(rows)
    assert len(rows["daily_course_record"][0]["document_id"]) == 64


@pytest.mark.unit
def test_course_reader_rejects_truncated_source(monkeypatch):
    class _Rows:
        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "document_id": f"doc-{index}",
                    "document_title": "主治医师查房记录",
                    "record_time": f"2026-06-0{index + 1} 08:00:00",
                }
                for index in range(3)
            ]

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _statement, params):
            assert params["limit_rows"] == 3
            return _Rows()

    class _Engine:
        def connect(self):
            return _Connection()

    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _Engine())
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda *_args: {
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "document_title",
            "record_time",
        },
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_qualified_table",
        lambda _schema, table: f'"cdm"."{table}"',
    )
    monkeypatch.setattr(source_evidence_reader, "_source_limit", lambda _source: 2)

    with pytest.raises(source_evidence_reader.SourceEvidenceTruncated):
        source_evidence_reader.read_luxian_0609_course_round_timeline(
            institute_id="I",
            patient_id="P",
            visit_id="V",
            source_schema=None,
        )


@pytest.mark.unit
def test_live_course_source_uses_private_time_only_rows_for_005_and_006(
    monkeypatch,
):
    """正式执行只读权威标题/时间，不把查房正文扩进共享证据。"""

    calls: list[dict] = []

    def _read(**kwargs):
        calls.append(kwargs)
        return {
            "daily_course_record": [
                {
                    "document_id": "safe-attending-ref",
                    "title": "主治医师首次查房记录",
                    "authored_at": "2026-06-02 08:00:00",
                    "source_table": "daily_course_record",
                }
            ],
            "senior_course_record": [
                {
                    "document_id": "safe-senior-ref",
                    "title": "副主任医师首次查房记录",
                    "authored_at": "2026-06-03 08:00:00",
                    "source_table": "senior_course_record",
                }
            ],
        }

    monkeypatch.setattr(basic_timeliness, "read_luxian_0609_course_round_timeline", _read)
    payload = {
        "programmatic_timeline": {
            "admission_time": "2026-06-01 08:00:00",
            "admission_time_basis": "timeline_primary_admission_datetime",
            "admission_time_trusted": True,
            "documents": {"daily_course_record": [{"raw_text": "MUST_STAY_PRIVATE"}]},
        }
    }

    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-005", "LX0609-006"),
        evidence_payload=payload,
        institute_id="I",
        patient_id="P",
        visit_id="V",
    )

    assert [item["status"] for item in execution.results] == ["compliant", "compliant"]
    assert calls == [
        {
            "institute_id": "I",
            "patient_id": "P",
            "visit_id": "V",
            "source_schema": None,
        }
    ]
    assert payload["programmatic_timeline"]["documents"] == {
        "daily_course_record": [{"raw_text": "MUST_STAY_PRIVATE"}]
    }
    assert "MUST_STAY_PRIVATE" not in repr(execution.results)


@pytest.mark.unit
def test_basic_timeliness_consumes_shared_course_material_without_live_reader(
    monkeypatch,
):
    rows_by_source = {
        "daily_course_record": [
            {
                "document_id": "private-attending-id",
                "document_title": "主治医师首次查房记录",
                "record_time": "2026-06-02 08:00:00",
                "record_content": "private body",
            }
        ],
        "senior_course_record": [
            {
                "document_id": "private-senior-id",
                "document_title": "副主任医师首次查房记录",
                "record_time": "2026-06-03 08:00:00",
                "record_content": "private body",
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

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-005", "LX0609-006"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=("daily_course_record", "senior_course_record"),
    )
    monkeypatch.setattr(
        basic_timeliness,
        "read_luxian_0609_course_round_timeline",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("shared material path must not query")
        ),
    )
    payload = {
        "programmatic_timeline": {
            "admission_time": "2026-06-01 08:00:00",
            "admission_time_basis": "timeline_primary_admission_datetime",
            "admission_time_trusted": True,
            "documents": {},
        }
    }

    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-005", "LX0609-006"),
        evidence_payload=payload,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in execution.results] == [
        "compliant",
        "compliant",
    ]
    assert "private body" not in repr(execution.results)


@pytest.mark.unit
def test_course_source_read_failure_is_data_gap_only_for_005_and_006(monkeypatch):
    """查房源读取异常必须失败关闭，且不改变001的既有确定性判断。"""

    def _raise(**_kwargs):
        raise RuntimeError("sensitive database failure")

    monkeypatch.setattr(basic_timeliness, "read_luxian_0609_course_round_timeline", _raise)
    payload = programmatic_evidence.build_programmatic_evidence_payload(
        bundle={
            "institute_id": "i",
            "patient_id": "p",
            "visit_id": "v",
            "timeline_facts": [
                {
                    "source_table": "inpat_registration",
                    "field": "admission_datetime",
                    "value": "2026-06-01 08:00:00",
                }
            ],
            "structured_context": {
                "documents": {
                    "admission_record": [
                        {
                            "source_table": "admission_record",
                            "record_time": "2026-06-02 08:00:00",
                        }
                    ]
                }
            },
        }
    )

    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-001", "LX0609-005", "LX0609-006"),
        evidence_payload=payload,
        institute_id="I",
        patient_id="P",
        visit_id="V",
    )

    assert [item["status"] for item in execution.results] == [
        "compliant",
        "data_gap",
        "data_gap",
    ]
    assert {
        item["metadata"]["reason_code"] for item in execution.results[1:]
    } == {"course_source_read_unavailable"}
    assert "sensitive database failure" not in repr(execution.results)


@pytest.mark.unit
def test_missing_source_coordinates_fail_closed_for_005_and_006():
    payload = programmatic_evidence.build_programmatic_evidence_payload(
        bundle={
            "timeline_facts": [
                {
                    "source_table": "inpat_registration",
                    "field": "admission_datetime",
                    "value": "2026-06-01 08:00:00",
                }
            ],
            "structured_context": {"documents": {}},
        }
    )

    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-005", "LX0609-006"),
        evidence_payload=payload,
    )

    assert [item["status"] for item in execution.results] == [
        "data_gap",
        "data_gap",
    ]
    assert {
        item["metadata"]["reason_code"] for item in execution.results
    } == {"course_source_read_unavailable"}


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
def test_admission_record_time_is_approved_for_0426_timeliness_rules(monkeypatch):
    monkeypatch.setattr(
        basic_timeliness,
        "read_luxian_0609_course_round_timeline",
        lambda **_kwargs: _private_course_rows(
            "2026-06-03 08:00:00", "2026-06-04 08:00:00"
        ),
    )
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
        institute_id="I",
        patient_id="P",
        visit_id="V",
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
    monkeypatch,
):
    monkeypatch.setattr(
        basic_timeliness,
        "read_luxian_0609_course_round_timeline",
        lambda **_kwargs: _private_course_rows(attending_time, senior_time),
    )
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
        institute_id="I",
        patient_id="P",
        visit_id="V",
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
def test_native_basic_family_returns_five_results_in_catalog_order_without_llm(
    monkeypatch,
):
    monkeypatch.setattr(
        basic_timeliness,
        "read_luxian_0609_course_round_timeline",
        lambda **_kwargs: _private_course_rows(
            "2026-06-02 09:00:00", "2026-06-03 09:00:00"
        ),
    )
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
        institute_id="I",
        patient_id="P",
        visit_id="V",
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
