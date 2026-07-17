from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.services.luxian_0609 import native_course_quality_execution as course
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
    CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)


def _severity_session(
    *,
    rows: list[dict] | None = None,
    failure: Exception | None = None,
    truncated: bool = False,
    daily_rows: list[dict] | None = None,
    senior_rows: list[dict] | None = None,
    course_failure: Exception | None = None,
    course_truncated: bool = False,
    evaluation_as_of_date: str | None = "2026-01-03",
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY:
            if failure is not None:
                raise failure
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=rows or [],
                truncated=truncated,
                limit_rows=50,
            )
        if source_key in {"daily_course_record", "senior_course_record"}:
            if course_failure is not None:
                raise course_failure
            course_rows = (
                daily_rows if source_key == "daily_course_record" else senior_rows
            )
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=course_rows or [],
                truncated=course_truncated and bool(course_rows),
                limit_rows=50,
            )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=[],
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-008", "LX0609-009"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        evaluation_as_of_date=evaluation_as_of_date,
        row_reader=read,
        additional_source_keys=(CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,),
    )


async def _run_typed_severity(session):
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        decision_rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-008", "LX0609-009"),
        snapshot=session.snapshot,
    )
    return result, reduced


def _row(content: str, record_time: str = "2026-06-01 09:00:00") -> dict:
    return {"record_content": content, "record_time": record_time}


def _payload(
    *,
    documents: dict[str, list[dict]] | None = None,
    facts: list[dict] | None = None,
) -> dict:
    return {
        "timeline_facts": list(facts or []),
        "programmatic_timeline": {"documents": dict(documents or {})},
    }


def _wrapper(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "defect_level": "轻微缺陷",
        "custom_prompt": (
            f"规则ID: {rule_id}\n"
            "主执行规则: SHOULD_NOT_LEAK\n"
            "映射执行规则: SHOULD_NOT_LEAK\n"
            "病历文本：\n{medical_text}\n"
            '只输出JSON：{"is_compliant": true}'
        ),
    }


def _strong_fact(fact_type: str, *, state: str = "present") -> dict:
    return {
        "fact_type": fact_type,
        "state": state,
        "source_key": "inpat_nondrug_order",
        "current_visit_bound": True,
    }


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        content = (
            output
            if isinstance(output, str)
            else json.dumps(output, ensure_ascii=False)
        )
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 5, "total_tokens": 45},
            "_api_time": 0.1,
        }


@pytest.mark.asyncio
async def test_course_017_consumes_shared_material_without_live_reader(
    monkeypatch,
):
    copied = "患者病情平稳，查体无明显变化，继续当前治疗方案并观察。"
    rows_by_source = {
        "daily_course_record": [
            {
                "document_id": "private-a",
                "record_time": "2026-01-01 09:00:00",
                "record_content": copied,
            }
        ],
        "senior_course_record": [
            {
                "document_id": "private-b",
                "record_time": "2026-01-02 09:00:00",
                "record_content": copied,
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
        selected_rule_ids=("LX0609-017",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=(
            "daily_course_record",
            "senior_course_record",
        ),
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("shared course material must not query")
        ),
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.llm_call_count == 0
    assert "private-a" not in repr(result)


@pytest.mark.asyncio
async def test_typed_017_strong_copy_emits_bound_decision_without_customer_dto(
    monkeypatch,
):
    copied = "患者病情平稳，查体无明显变化，继续当前治疗方案并观察病情变化。"
    private_marker = "PRIVATE_COPY_MATERIAL_MARKER"
    rows_by_source = {
        "daily_course_record": [
            {
                "document_id": "private-a",
                "record_time": "2026-01-01 09:00:00",
                "record_content": f"{private_marker}{copied}",
            }
        ],
        "senior_course_record": [
            {
                "document_id": "private-b",
                "record_time": "2026-01-02 09:00:00",
                "record_content": f"{private_marker}{copied}",
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
        selected_rule_ids=("LX0609-017",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=("daily_course_record", "senior_course_record"),
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("typed copy path must use one evidence session")
        ),
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        decision_rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(
            documents={"daily_course_record": [_row("stale payload must not win")]}
        ),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([{"is_compliant": True}]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.results == ()
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-017",),
        snapshot=session.snapshot,
    )
    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].fact_refs
    assert result.llm_call_count == 0
    assert private_marker not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_state", "expected_state", "expected_reason"),
    (
        ("empty", CustomerFinalState.NOT_APPLICABLE, "trigger_absent_complete"),
        ("unavailable", CustomerFinalState.DATA_GAP, "source_unavailable"),
        ("error", CustomerFinalState.TECHNICAL_ERROR, "source_query_error"),
        ("truncated", CustomerFinalState.DATA_GAP, "source_truncated"),
    ),
)
async def test_typed_017_preserves_source_query_state_without_model(
    source_state: str,
    expected_state: CustomerFinalState,
    expected_reason: str,
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "daily_course_record":
            if source_state == "unavailable":
                raise SourceEvidenceUnavailable()
            if source_state == "error":
                raise SourceEvidenceQueryError()
            if source_state == "empty":
                return SnapshotSourceRows.create(
                    source_key=source_key,
                    rows=[],
                    truncated=False,
                    limit_rows=50,
                )
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=[{"record_content": "private material" * 4}],
                truncated=True,
                limit_rows=1,
            )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=[],
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-017",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
    )
    client = _Client([{"is_compliant": True}])
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        decision_rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-017",),
        snapshot=session.snapshot,
    )

    assert result.results == ()
    assert reduced[0].final_state is expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_typed_017_gray_llm_matches_raw_state_calls_tokens_and_privacy():
    common = "患者神志清楚生命体征平稳腹部柔软双肺呼吸音清继续观察病情变化"
    private_marker = "PRIVATE_GRAY_COPY_MARKER"
    left = f"{private_marker}{common}今日腹痛减轻复查指标下降停止静脉补液{common}"
    right = f"{private_marker}{common}今日仍有发热复查提示感染继续静脉抗感染{common}"

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            [
                {**_row(left), "document_id": "private-left"},
                {
                    **_row(right, "2026-06-02 09:00:00"),
                    "document_id": "private-right",
                },
            ]
            if source_key == "daily_course_record"
            else []
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-017",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
    )
    raw_client = _Client([{"is_compliant": False}])
    typed_client = _Client([{"is_compliant": False}])
    raw = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=raw_client,
        evidence_materials=session.materials,
    )
    typed = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        decision_rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(
            documents={"daily_course_record": [_row("stale payload is irrelevant")]}
        ),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=typed_client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=typed.decisions,
        expected_rule_ids=("LX0609-017",),
        snapshot=session.snapshot,
    )

    assert typed.results == ()
    assert reduced[0].final_state.value == raw.results[0]["status"]
    assert raw.llm_call_count == typed.llm_call_count == 1
    assert raw.total_tokens == typed.total_tokens == 45
    assert len(raw_client.prompts) == len(typed_client.prompts) == 1
    assert private_marker not in repr(typed)
    assert "private-left" not in repr(typed)


@pytest.mark.asyncio
async def test_course_017_preserves_truncated_material_reason() -> None:
    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            [{"document_id": "private-a", "record_content": "a" * 40}]
            if source_key == "daily_course_record"
            else []
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=bool(rows),
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-017",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=("daily_course_record", "senior_course_record"),
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "course_comparison_source_truncated"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("present", "expected_status", "expected_reason"),
    [
        (True, "not_applicable", "unstable_patient_order_present"),
        (False, "compliant", "course_record_interval_within_72h"),
    ],
)
async def test_course_007_consumes_snapshot_fact_without_live_queries(
    monkeypatch,
    present: bool,
    expected_status: str,
    expected_reason: str,
) -> None:
    rows_by_source = {
        CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY: (
            [{"present": True}] if present else []
        ),
        "daily_course_record": [
            _row("患者病情稳定，继续当前治疗。", "2026-01-01 09:00:00"),
            _row("患者病情稳定，继续当前治疗。", "2026-01-02 09:00:00"),
        ],
        "senior_course_record": [],
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
        selected_rule_ids=("LX0609-007",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=("daily_course_record", "senior_course_record"),
    )
    monkeypatch.setattr(
        course,
        "has_luxian_0609_current_visit_unstable_order",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("007 must consume the request snapshot fact")
        ),
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("007 must consume request materials")
        ),
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        wrapper_rules=[],
        evidence_payload=_payload(documents={}),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == [expected_status]
    assert result.results[0]["metadata"]["reason_code"] == expected_reason
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_course_007_emits_snapshot_bound_rule_decision_without_legacy_result(
    monkeypatch,
) -> None:
    rows_by_source = {
        CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY: [],
        "daily_course_record": [
            _row("患者病情稳定，继续当前治疗。", "2026-01-01 09:00:00"),
            _row("患者症状改善，继续观察。", "2026-01-02 09:00:00"),
        ],
        "senior_course_record": [],
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
        selected_rule_ids=("LX0609-007",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=("daily_course_record", "senior_course_record"),
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("typed 007 must consume request materials")
        ),
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        decision_rule_ids=("LX0609-007",),
        wrapper_rules=[],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == ["LX0609-007"]
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-007",),
        snapshot=session.snapshot,
    )
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_within_threshold"
    assert reduced[0].fact_refs
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected_state", "expected_reason"),
    [
        ("unstable", CustomerFinalState.NOT_APPLICABLE, "eligibility_not_met"),
        ("over_72h", CustomerFinalState.NON_COMPLIANT, "threshold_exceeded"),
        ("missing_time", CustomerFinalState.DATA_GAP, "authoritative_time_missing"),
        ("unavailable", CustomerFinalState.DATA_GAP, "source_unavailable"),
        ("query_error", CustomerFinalState.TECHNICAL_ERROR, "source_query_error"),
        ("truncated", CustomerFinalState.DATA_GAP, "source_truncated"),
    ],
)
async def test_course_007_typed_truth_table_is_python_only_and_fail_closed(
    scenario: str,
    expected_state: CustomerFinalState,
    expected_reason: str,
) -> None:
    normal_rows = [
        _row("患者病情稳定，继续当前治疗。", "2026-01-01 09:00:00"),
        _row("患者症状改善，继续观察。", "2026-01-02 09:00:00"),
    ]

    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY:
            rows = [{"present": True}] if scenario == "unstable" else []
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=rows,
                truncated=False,
                limit_rows=50,
            )
        if source_key == "daily_course_record":
            if scenario == "unavailable":
                raise SourceEvidenceUnavailable()
            if scenario == "query_error":
                raise SourceEvidenceQueryError()
            if scenario == "over_72h":
                rows = [
                    _row("首次查房。", "2026-01-01 09:00:00"),
                    _row("再次查房。", "2026-01-05 09:00:01"),
                ]
            elif scenario == "missing_time":
                rows = [
                    {
                        "record_content": "实质查房记录。",
                        "record_time": None,
                        "update_time": "2026-01-03 09:00:00",
                    }
                ]
            else:
                rows = normal_rows
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=rows,
                truncated=scenario == "truncated",
                limit_rows=50,
            )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=[],
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-007",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=("daily_course_record", "senior_course_record"),
    )
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        decision_rule_ids=("LX0609-007",),
        wrapper_rules=[],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-007",),
        snapshot=session.snapshot,
    )

    assert result.results == ()
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert reduced[0].final_state is expected_state
    assert reduced[0].reason_code == expected_reason
    assert "2026-01" not in repr(result.decisions)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected_states", "expected_reasons"),
    [
        (
            "no_order",
            (CustomerFinalState.NOT_APPLICABLE, CustomerFinalState.NOT_APPLICABLE),
            ("trigger_absent_complete", "trigger_absent_complete"),
        ),
        (
            "serious_within_two_days",
            (CustomerFinalState.COMPLIANT, CustomerFinalState.NOT_APPLICABLE),
            ("requirement_within_threshold", "trigger_absent_complete"),
        ),
        (
            "serious_gap",
            (CustomerFinalState.NON_COMPLIANT, CustomerFinalState.NOT_APPLICABLE),
            ("threshold_exceeded", "trigger_absent_complete"),
        ),
        (
            "serious_no_followup",
            (CustomerFinalState.NON_COMPLIANT, CustomerFinalState.NOT_APPLICABLE),
            ("threshold_exceeded", "trigger_absent_complete"),
        ),
        (
            "critical_daily_complete",
            (CustomerFinalState.NOT_APPLICABLE, CustomerFinalState.DATA_GAP),
            ("trigger_absent_complete", "required_field_missing"),
        ),
        (
            "critical_missing_day",
            (CustomerFinalState.NOT_APPLICABLE, CustomerFinalState.NON_COMPLIANT),
            ("trigger_absent_complete", "requirement_violated"),
        ),
        (
            "order_time_missing",
            (CustomerFinalState.DATA_GAP, CustomerFinalState.NOT_APPLICABLE),
            ("authoritative_time_missing", "trigger_absent_complete"),
        ),
        (
            "record_time_missing",
            (CustomerFinalState.DATA_GAP, CustomerFinalState.NOT_APPLICABLE),
            ("authoritative_time_missing", "trigger_absent_complete"),
        ),
        (
            "malformed_severity",
            (CustomerFinalState.TECHNICAL_ERROR, CustomerFinalState.TECHNICAL_ERROR),
            ("snapshot_mismatch", "snapshot_mismatch"),
        ),
        (
            "query_error",
            (CustomerFinalState.TECHNICAL_ERROR, CustomerFinalState.TECHNICAL_ERROR),
            ("source_query_error", "source_query_error"),
        ),
        (
            "source_unavailable",
            (CustomerFinalState.DATA_GAP, CustomerFinalState.DATA_GAP),
            ("source_unavailable", "source_unavailable"),
        ),
        (
            "source_truncated",
            (CustomerFinalState.DATA_GAP, CustomerFinalState.DATA_GAP),
            ("source_truncated", "source_truncated"),
        ),
    ],
)
async def test_course_008_009_typed_natural_day_truth_table_is_python_only(
    scenario: str,
    expected_states: tuple[CustomerFinalState, CustomerFinalState],
    expected_reasons: tuple[str, str],
) -> None:
    severity_rows: list[dict] = []
    daily_rows: list[dict] = []
    failure: Exception | None = None
    truncated = False
    if scenario.startswith("serious") or scenario in {
        "order_time_missing",
        "record_time_missing",
    }:
        severity_rows = [
            {
                "severity": "serious",
                "prescribed_datetime": (
                    None if scenario == "order_time_missing" else "2026-01-01 23:59:59"
                ),
                "row_ref": "a" * 64,
            }
        ]
    elif scenario.startswith("critical"):
        severity_rows = [
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 23:59:59",
                "row_ref": "b" * 64,
            }
        ]
    elif scenario == "malformed_severity":
        severity_rows = [
            {
                "severity": "unknown",
                "prescribed_datetime": "2026-01-01 00:00:00",
                "row_ref": "c" * 64,
            }
        ]
    elif scenario == "query_error":
        failure = SourceEvidenceQueryError()
    elif scenario == "source_unavailable":
        failure = SourceEvidenceUnavailable()
    elif scenario == "source_truncated":
        severity_rows = [
            {
                "severity": "serious",
                "prescribed_datetime": "2026-01-01 00:00:00",
                "row_ref": "d" * 64,
            }
        ]
        truncated = True

    if scenario == "serious_within_two_days":
        daily_rows = [
            _row("记录一", "2026-01-01 00:01:00"),
            _row("记录二", "2026-01-03 23:59:59"),
        ]
    elif scenario == "serious_gap":
        daily_rows = [_row("记录一", "2026-01-04 00:00:00")]
    elif scenario == "critical_daily_complete":
        daily_rows = [
            _row("记录一", "2026-01-01 23:59:59"),
            _row("记录二", "2026-01-02 00:00:01"),
            _row("记录三", "2026-01-03 12:00:00"),
        ]
    elif scenario == "critical_missing_day":
        daily_rows = [
            _row("记录一", "2026-01-01 08:00:00"),
            _row("记录三", "2026-01-03 08:00:00"),
        ]
    elif scenario == "record_time_missing":
        daily_rows = [_row("有内容但无权威时间", None)]

    session = _severity_session(
        rows=severity_rows,
        failure=failure,
        truncated=truncated,
        daily_rows=daily_rows,
        evaluation_as_of_date=(
            "2026-01-04"
            if scenario in {"serious_gap", "serious_no_followup"}
            else "2026-01-03"
        ),
    )
    result, reduced = await _run_typed_severity(session)

    assert tuple(item.final_state for item in reduced) == expected_states
    assert tuple(item.reason_code for item in reduced) == expected_reasons
    assert result.results == ()
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert "2026-01" not in repr(result.decisions)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("horizon", "record_times", "expected_state", "expected_reason"),
    [
        ("2026-01-03", [], CustomerFinalState.COMPLIANT, "requirement_within_threshold"),
        ("2026-01-04", [], CustomerFinalState.NON_COMPLIANT, "threshold_exceeded"),
        (
            "2026-01-05",
            ["2026-01-01 08:00:00", "2026-01-03 08:00:00"],
            CustomerFinalState.COMPLIANT,
            "requirement_within_threshold",
        ),
        (
            "2026-01-06",
            ["2026-01-01 08:00:00", "2026-01-03 08:00:00"],
            CustomerFinalState.NON_COMPLIANT,
            "threshold_exceeded",
        ),
        (
            None,
            ["2026-01-01 08:00:00", "2026-01-03 08:00:00"],
            CustomerFinalState.DATA_GAP,
            "authoritative_time_missing",
        ),
        (
            None,
            ["2026-01-04 08:00:00"],
            CustomerFinalState.NON_COMPLIANT,
            "threshold_exceeded",
        ),
    ],
)
async def test_course_008_checks_anchor_internal_and_tail_natural_day_gaps(
    horizon: str | None,
    record_times: list[str],
    expected_state: CustomerFinalState,
    expected_reason: str,
) -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "serious",
                "prescribed_datetime": "2026-01-01 23:59:59",
                "row_ref": "8" * 64,
            }
        ],
        daily_rows=[_row("查房记录", value) for value in record_times],
        evaluation_as_of_date=horizon,
    )
    result, reduced = await _run_typed_severity(session)

    assert reduced[0].final_state is expected_state
    assert reduced[0].reason_code == expected_reason
    if horizon is not None:
        horizon_fact = next(
            fact for fact in session.snapshot.facts if fact.fact_type == "evaluation_horizon"
        )
        assert horizon_fact.fact_id in result.decisions[0].fact_refs
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("horizon", "record_times", "expected_state", "expected_reason"),
    [
        (
            "2026-01-03",
            ["2026-01-01 08:00:00", "2026-01-02 08:00:00"],
            CustomerFinalState.NON_COMPLIANT,
            "requirement_violated",
        ),
        (
            "2026-01-03",
            [
                "2026-01-01 08:00:00",
                "2026-01-02 08:00:00",
                "2026-01-03 08:00:00",
            ],
            CustomerFinalState.DATA_GAP,
            "required_field_missing",
        ),
        (
            None,
            ["2026-01-01 08:00:00", "2026-01-03 08:00:00"],
            CustomerFinalState.NON_COMPLIANT,
            "requirement_violated",
        ),
        (
            None,
            ["2026-01-01 08:00:00", "2026-01-02 08:00:00"],
            CustomerFinalState.DATA_GAP,
            "authoritative_time_missing",
        ),
    ],
)
async def test_course_009_checks_every_day_through_horizon_then_keeps_semantic_unknown(
    horizon: str | None,
    record_times: list[str],
    expected_state: CustomerFinalState,
    expected_reason: str,
) -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 23:59:59",
                "row_ref": "9" * 64,
            }
        ],
        senior_rows=[_row("上级医师查房", value) for value in record_times],
        evaluation_as_of_date=horizon,
    )
    result, reduced = await _run_typed_severity(session)

    assert reduced[1].final_state is expected_state
    assert reduced[1].reason_code == expected_reason
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_course_009_daily_complete_uses_one_semantic_call_and_can_comply() -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 23:59:59",
                "row_ref": "9" * 64,
            }
        ],
        daily_rows=[
            _row("病情稳定，无新发变化。", "2026-01-01 08:00:00"),
            _row("病情变化已记录并及时处理。", "2026-01-02 08:00:00"),
            _row("病情平稳，继续观察。", "2026-01-03 08:00:00"),
        ],
        evaluation_as_of_date="2026-01-03",
    )
    client = _Client([{"semantic_state": "satisfied"}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-009",),
        decision_rule_ids=("LX0609-009",),
        wrapper_rules=[_wrapper("LX0609-009")],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-009",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_output", "expected_state", "expected_reason"),
    [
        (
            {"semantic_state": "defect"},
            CustomerFinalState.NON_COMPLIANT,
            "requirement_violated",
        ),
        (
            {"semantic_state": "unknown"},
            CustomerFinalState.DATA_GAP,
            "required_field_missing",
        ),
        (
            {"semantic_state": "unsupported"},
            CustomerFinalState.TECHNICAL_ERROR,
            "model_invalid_output",
        ),
        (
            RuntimeError("sensitive model failure"),
            CustomerFinalState.TECHNICAL_ERROR,
            "model_transport_error",
        ),
    ],
)
async def test_course_009_semantic_three_state_and_fail_closed(
    model_output: object,
    expected_state: CustomerFinalState,
    expected_reason: str,
) -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 23:59:59",
                "row_ref": "b" * 64,
            }
        ],
        daily_rows=[
            _row("病情记录一。", "2026-01-01 08:00:00"),
            _row("病情记录二。", "2026-01-02 08:00:00"),
            _row("病情记录三。", "2026-01-03 08:00:00"),
        ],
        evaluation_as_of_date="2026-01-03",
    )
    client = _Client([model_output])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-009",),
        decision_rule_ids=("LX0609-009",),
        wrapper_rules=[_wrapper("LX0609-009")],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-009",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "sensitive model failure" not in repr(result)


@pytest.mark.asyncio
async def test_course_009_missing_day_stays_python_only_with_client_available() -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 23:59:59",
                "row_ref": "c" * 64,
            }
        ],
        daily_rows=[
            _row("首日记录。", "2026-01-01 08:00:00"),
            _row("第三日记录。", "2026-01-03 08:00:00"),
        ],
        evaluation_as_of_date="2026-01-03",
    )
    client = _Client([{"semantic_state": "satisfied"}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-009",),
        decision_rule_ids=("LX0609-009",),
        wrapper_rules=[_wrapper("LX0609-009")],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-009",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_course_008_remains_python_only_with_client_available() -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "serious",
                "prescribed_datetime": "2026-01-01 23:59:59",
                "row_ref": "d" * 64,
            }
        ],
        daily_rows=[_row("病重查房记录。", "2026-01-02 08:00:00")],
        evaluation_as_of_date="2026-01-03",
    )
    client = _Client([{"semantic_state": "defect"}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008",),
        decision_rule_ids=("LX0609-008",),
        wrapper_rules=[_wrapper("LX0609-008")],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-008",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_course_009_semantic_prompt_uses_only_bounded_daily_and_senior_rows() -> None:
    daily_rows = [_row("OUTSIDE_WINDOW_MUST_NOT_LEAK", "2025-12-31 23:59:59")] + [
        _row(f"DAILY_ALLOWED_{index} " + "甲" * 1600, "2026-01-01 08:00:00")
        for index in range(8)
    ] + [_row("DAILY_NINTH_MUST_NOT_LEAK", "2026-01-01 09:00:00")]
    senior_rows = [
        _row(f"SENIOR_ALLOWED_{index}", "2026-01-01 10:00:00")
        for index in range(8)
    ] + [_row("SENIOR_NINTH_MUST_NOT_LEAK", "2026-01-01 11:00:00")]
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 00:00:00",
                "row_ref": "a" * 64,
            }
        ],
        daily_rows=daily_rows,
        senior_rows=senior_rows,
        evaluation_as_of_date="2026-01-01",
    )
    client = _Client([{"semantic_state": "satisfied"}])
    forbidden = {
        "first_course_record": "FIRST_MUST_NOT_LEAK",
        "rescue_record": "RESCUE_MUST_NOT_LEAK",
        "exam_attention_report": "EXAM_MUST_NOT_LEAK",
        "lab_attention_report": "LAB_MUST_NOT_LEAK",
    }

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-009",),
        decision_rule_ids=("LX0609-009",),
        wrapper_rules=[_wrapper("LX0609-009")],
        evidence_payload=_payload(
            documents={key: [_row(marker)] for key, marker in forbidden.items()}
        ),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    prompt = client.prompts[0]
    assert "DAILY_ALLOWED_0" in prompt
    assert "SENIOR_ALLOWED_0" in prompt
    assert "DAILY_NINTH_MUST_NOT_LEAK" not in prompt
    assert "SENIOR_NINTH_MUST_NOT_LEAK" not in prompt
    assert "OUTSIDE_WINDOW_MUST_NOT_LEAK" not in prompt
    assert all(marker not in prompt for marker in forbidden.values())
    assert "SHOULD_NOT_LEAK" not in prompt
    assert "甲" * 1401 not in prompt
    assert len(
        course._rule_009_semantic_context(
            snapshot=session.snapshot,
            materials=session.materials,
        )
    ) <= 18000
    assert "DAILY_ALLOWED_0" not in repr(result)
    assert all(marker not in repr(result) for marker in forbidden.values())


@pytest.mark.asyncio
async def test_course_008_record_source_failure_is_fail_closed_after_trigger() -> None:
    serious = [
        {
            "severity": "serious",
            "prescribed_datetime": "2026-01-01 08:00:00",
            "row_ref": "e" * 64,
        }
    ]
    session = _severity_session(
        rows=serious,
        course_failure=SourceEvidenceQueryError(),
    )
    result, reduced = await _run_typed_severity(session)

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.TECHNICAL_ERROR,
        CustomerFinalState.NOT_APPLICABLE,
    ]
    assert [item.reason_code for item in reduced] == [
        "source_query_error",
        "trigger_absent_complete",
    ]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [SourceEvidenceUnavailable(), SourceEvidenceQueryError()],
)
async def test_course_007_source_failure_is_data_gap_without_live_query(
    monkeypatch,
    failure: Exception,
) -> None:
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY:
            raise failure
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=[],
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-007",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=("daily_course_record", "senior_course_record"),
    )
    monkeypatch.setattr(
        course,
        "has_luxian_0609_current_visit_unstable_order",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("007 must not retry a failed snapshot query")
        ),
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        wrapper_rules=[],
        evidence_payload=_payload(documents={}),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "course_time_source_unavailable"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_selected_rules_keep_customer_catalog_order_and_missing_projection_is_data_gap():
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018", "LX0609-007", "LX0609-016"),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=None,
    )

    assert course.COURSE_QUALITY_RULE_IDS == (
        "LX0609-007",
        "LX0609-008",
        "LX0609-009",
        "LX0609-016",
        "LX0609-017",
        "LX0609-018",
    )
    assert course.EXECUTOR_KEY == "course_quality"
    assert [item["rule_id"] for item in result.results] == [
        "LX0609-007",
        "LX0609-016",
        "LX0609-018",
    ]
    assert [item["status"] for item in result.results] == ["data_gap"] * 3
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("senior_time", "expected_status"),
    [
        (datetime(2026, 6, 4, 9, 0), "compliant"),
        (datetime(2026, 6, 4, 9, 0, 1), "non_compliant"),
    ],
)
async def test_007_uses_only_daily_and_senior_record_time_without_model(
    monkeypatch, senior_time: datetime, expected_status: str
):
    reader_calls: list[str] = []

    def fake_reader(**kwargs):
        source_key = kwargs["source_key"]
        reader_calls.append(source_key)
        if source_key == "daily_course_record":
            return [
                {"record_time": datetime(2026, 6, 1, 9, 0)},
                {"record_time": None},
            ]
        if source_key == "senior_course_record":
            return [{"record_time": senior_time}]
        raise AssertionError(source_key)

    monkeypatch.setattr(course, "read_luxian_0609_native_source_rows", fake_reader)
    monkeypatch.setattr(
        course, "has_luxian_0609_current_visit_unstable_order", lambda **_: False
    )
    client = _Client([{"is_compliant": False}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        wrapper_rules=[_wrapper("LX0609-007")],
        evidence_payload=_payload(
            documents={
                "first_course_record": [_row("不得计入007", "2026-06-02 09:00:00")],
                "rescue_record": [_row("不得计入007", "2026-06-03 09:00:00")],
            }
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [expected_status]
    assert reader_calls == ["daily_course_record", "senior_course_record"]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []
    assert "不得计入007" not in repr(result)


@pytest.mark.asyncio
async def test_007_unstable_order_is_not_applicable_without_reading_course_rows(
    monkeypatch,
):
    monkeypatch.setattr(
        course, "has_luxian_0609_current_visit_unstable_order", lambda **_: True
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **_: (_ for _ in ()).throw(AssertionError("course rows must not be read")),
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        wrapper_rules=[_wrapper("LX0609-007")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["not_applicable"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_007_missing_authoritative_record_times_is_data_gap_without_model(
    monkeypatch,
):
    monkeypatch.setattr(
        course, "has_luxian_0609_current_visit_unstable_order", lambda **_: False
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **_: [{"record_time": None, "update_time": datetime(2026, 6, 1, 9, 0)}],
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        wrapper_rules=[_wrapper("LX0609-007")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "authoritative_course_time_unavailable"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_007_substantive_record_without_authoritative_time_blocks_non_compliant(
    monkeypatch,
):
    monkeypatch.setattr(
        course, "has_luxian_0609_current_visit_unstable_order", lambda **_: False
    )

    def fake_reader(**kwargs):
        if kwargs["source_key"] == "daily_course_record":
            return [
                _row("患者病情稳定，继续当前治疗。", "2026-06-01 08:00:00"),
                _row("上级医师查房后调整治疗方案。", None),
                _row("患者症状改善，复查指标下降。", "2026-06-05 08:00:00"),
            ]
        if kwargs["source_key"] == "senior_course_record":
            return []
        raise AssertionError(kwargs["source_key"])

    monkeypatch.setattr(
        course, "read_luxian_0609_native_source_rows", fake_reader
    )
    client = _Client([])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        wrapper_rules=[_wrapper("LX0609-007")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "authoritative_course_time_incomplete"
    )
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_007_substantive_record_without_time_does_not_downgrade_compliant_timeline(
    monkeypatch,
):
    monkeypatch.setattr(
        course, "has_luxian_0609_current_visit_unstable_order", lambda **_: False
    )

    def fake_reader(**kwargs):
        if kwargs["source_key"] == "daily_course_record":
            return [
                _row("患者病情稳定，继续当前治疗。", "2026-06-01 08:00:00"),
                _row("上级医师查房后调整治疗方案。", None),
                _row("患者症状改善，复查指标下降。", "2026-06-03 08:00:00"),
            ]
        if kwargs["source_key"] == "senior_course_record":
            return []
        raise AssertionError(kwargs["source_key"])

    monkeypatch.setattr(
        course, "read_luxian_0609_native_source_rows", fake_reader
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        wrapper_rules=[_wrapper("LX0609-007")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["compliant"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_008_009_require_current_visit_serious_or_critical_strong_fact():
    documents = {
        "daily_course_record": [
            _row("病重患者日常病程记录。"),
            _row("上级医师查房记录。", "2026-06-02 09:00:00"),
        ]
    }
    client = _Client([{"is_compliant": False}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(
            documents=documents,
            facts=[
                _strong_fact("current_visit_serious_order"),
                _strong_fact("current_visit_critical_order", state="absent"),
            ],
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "not_applicable",
    ]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "当前就诊存在病重医嘱" in client.prompts[0]

    critical_client = _Client([{"is_compliant": True}])
    critical = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(
            documents=documents,
            facts=[
                _strong_fact("current_visit_serious_order", state="absent"),
                _strong_fact("current_visit_critical_order"),
            ],
        ),
        llm_client=critical_client,
    )
    assert [item["status"] for item in critical.results] == [
        "not_applicable",
        "compliant",
    ]
    assert critical.llm_call_count == 1
    assert "当前就诊存在病危医嘱" in critical_client.prompts[0]

    silence = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(documents=documents),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in silence.results] == ["data_gap"] * 2
    assert silence.llm_call_count == 0

    explicit_negative = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(
            documents=documents,
            facts=[
                _strong_fact("current_visit_serious_order", state="absent"),
                _strong_fact("current_visit_critical_order", state="absent"),
            ],
        ),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in explicit_negative.results] == [
        "not_applicable",
        "not_applicable",
    ]
    assert explicit_negative.llm_call_count == 0


@pytest.mark.asyncio
async def test_016_requires_admission_and_first_course_before_model():
    missing = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(documents={"admission_record": [_row("入院记录现病史。")]}),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in missing.results] == ["data_gap"]
    assert missing.llm_call_count == 0

    client = _Client([{"is_compliant": False}])
    complete = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(
            documents={
                "admission_record": [_row("入院记录现病史与病例特点。")],
                "first_course_record": [_row("首次病程病例特点与诊断依据。")],
            }
        ),
        llm_client=client,
    )
    assert [item["status"] for item in complete.results] == ["non_compliant"]
    assert complete.llm_call_count == 1


@pytest.mark.asyncio
async def test_typed_016_018_use_same_material_session_without_legacy_payload():
    private_marker = "PRIVATE_ADMISSION_MATERIAL_MARKER"
    rows_by_source = {
        "admission_record": [
            _row(
                f"{private_marker} 主诉：反复胸痛3个月。入院诊断：不稳定型心绞痛。"
                "现病史与病例特点完整。"
            )
        ],
        "first_course_record": [
            _row("首次病程记录包含病例特点、诊断依据、鉴别诊断和诊疗计划。")
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
        selected_rule_ids=("LX0609-016", "LX0609-018"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
    )
    client = _Client([{"is_compliant": False}, {"is_compliant": True}])
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016", "LX0609-018"),
        decision_rule_ids=("LX0609-016", "LX0609-018"),
        wrapper_rules=[_wrapper("LX0609-016"), _wrapper("LX0609-018")],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.results == ()
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-016", "LX0609-018"),
        snapshot=session.snapshot,
    )
    assert [item.final_state.value for item in reduced] == [
        "non_compliant",
        "compliant",
    ]
    assert all(item.fact_refs for item in reduced)
    assert result.llm_call_count == 2
    assert result.total_tokens == 90
    assert private_marker not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_state", "expected_state", "expected_reason"),
    (
        ("empty", CustomerFinalState.DATA_GAP, "required_field_missing"),
        ("unavailable", CustomerFinalState.DATA_GAP, "source_unavailable"),
        ("error", CustomerFinalState.TECHNICAL_ERROR, "source_query_error"),
        ("truncated", CustomerFinalState.DATA_GAP, "source_truncated"),
    ),
)
async def test_typed_018_preserves_source_state_without_model(
    source_state: str,
    expected_state: CustomerFinalState,
    expected_reason: str,
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "admission_record":
            if source_state == "unavailable":
                raise SourceEvidenceUnavailable()
            if source_state == "error":
                raise SourceEvidenceQueryError()
            rows = (
                []
                if source_state == "empty"
                else [_row("主诉：胸痛。入院诊断：心绞痛。现病史完整。")]
            )
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=rows,
                truncated=source_state == "truncated",
                limit_rows=1 if source_state == "truncated" else 50,
            )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=[],
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-018",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
    )
    client = _Client([{"is_compliant": True}])
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        decision_rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-018",),
        snapshot=session.snapshot,
    )

    assert result.results == ()
    assert reduced[0].final_state is expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_typed_018_matches_raw_state_calls_and_tokens():
    admission_row = _row(
        "主诉：反复胸痛3个月。入院诊断：不稳定型心绞痛。现病史完整。"
    )

    def read(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=[admission_row] if source_key == "admission_record" else [],
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-018",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
    )
    raw = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(documents={"admission_record": [admission_row]}),
        llm_client=_Client([{"is_compliant": False}]),
    )
    typed = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        decision_rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload={"stale": "payload"},
        llm_client=_Client([{"is_compliant": False}]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=typed.decisions,
        expected_rule_ids=("LX0609-018",),
        snapshot=session.snapshot,
    )

    assert raw.results[0]["status"] == reduced[0].final_state.value
    assert typed.results == ()
    assert typed.llm_call_count == raw.llm_call_count == 1
    assert typed.total_tokens == raw.total_tokens == 45


@pytest.mark.asyncio
async def test_typed_018_accepts_only_controlled_primary_diagnosis_material():
    rows_by_source = {
        "admission_record": [
            _row("主诉：反复腹痛2个月。现病史与既往诊疗经过记录完整。")
        ],
        "diagnosis": [
            *[
                {"diagnosis_type": "其他诊断", "diagnosis_name": f"不应采信的诊断{index}"}
                for index in range(8)
            ],
            {"diagnosis_type": "主要诊断", "diagnosis_name": "结肠恶性肿瘤"},
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
        selected_rule_ids=("LX0609-018",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
    )
    client = _Client([{"is_compliant": False}])
    typed = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        decision_rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=typed.decisions,
        expected_rule_ids=("LX0609-018",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert typed.llm_call_count == 1
    assert "结肠恶性肿瘤" in client.prompts[0]
    assert "不应采信的诊断" not in client.prompts[0]
    assert "结肠恶性肿瘤" not in repr(typed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_output", "expected_reason", "expected_tokens"),
    (
        (RuntimeError("private model transport detail"), "model_transport_error", 0),
        ("not-json private model output", "model_invalid_output", 45),
    ),
)
async def test_typed_016_model_failures_are_explicit_technical_errors(
    model_output: object,
    expected_reason: str,
    expected_tokens: int,
):
    rows_by_source = {
        "admission_record": [
            _row("主诉：反复胸痛3个月。入院诊断：不稳定型心绞痛。现病史完整。")
        ],
        "first_course_record": [
            _row("首次病程记录包含病例特点、诊断依据、鉴别诊断和诊疗计划。")
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
        selected_rule_ids=("LX0609-016",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
    )
    typed = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        decision_rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=None,
        llm_client=_Client([model_output]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=typed.decisions,
        expected_rule_ids=("LX0609-016",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == expected_reason
    assert typed.total_tokens == expected_tokens
    assert "private model" not in repr(typed)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_course_row",
    [
        {
            "title": "首次病程记录",
            "record_time": "2026-06-01 09:00:00",
            "content_preview": "首次病程病例特点、诊断依据和诊疗计划已经完整记录。",
            "text_preview": "首次病程记录预览",
        },
        {
            "title": "首次病程记录",
            "record_time": "2026-06-01 09:00:00",
            "source_table": "first_course_record",
            "assembled_fields": ["record_time", "document_title"],
        },
        {
            "title": "首次病程记录",
            "record_time": "2026-06-01 09:00:00",
            "content": (
                "source_table:first_course_record；文书类型：首次病程记录；"
                "记录时间：2026年06月01日09时00分00秒；assembly_status:partial"
            ),
        },
    ],
)
async def test_016_preview_or_assembly_shell_is_data_gap_without_model(
    first_course_row: dict,
):
    client = _Client([{"is_compliant": False}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(
            documents={
                "admission_record": [_row("入院记录现病史与病例特点。")],
                "first_course_record": [first_course_row],
            }
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "首次病程病例特点、诊断依据和诊疗计划已经完整记录" not in repr(result)


@pytest.mark.asyncio
async def test_016_admission_preview_shell_is_data_gap_without_model():
    client = _Client([{"is_compliant": True}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(
            documents={
                "admission_record": [
                    {
                        "title": "入院记录",
                        "record_time": "2026-06-01 08:00:00",
                        "text_preview": "入院记录预览",
                    }
                ],
                "first_course_record": [_row("首次病程病例特点与诊断依据。")],
            }
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_017_requires_two_comparable_records_and_never_outputs_review_pending():
    one_record = course._copy_result(
        {"daily_course_record": [_row("患者病情稳定，继续观察治疗。")]},
        source_complete=True,
    )
    assert one_record["status"] == "not_applicable"
    assert "复核" not in repr(one_record)

    copied = "患者神志清楚，咳嗽咳痰，双肺呼吸音粗，继续抗感染平喘化痰治疗，观察病情变化。"
    similar = course._copy_result(
        {
            "daily_course_record": [
                _row(copied),
                _row(copied, "2026-06-02 09:00:00"),
            ]
        },
        source_complete=True,
    )
    assert similar["status"] == "non_compliant"
    assert "复核" not in repr(similar)

    different = course._copy_result(
        {
            "daily_course_record": [
                _row("患者胸痛缓解，复查心肌酶阴性，计划完善冠脉CTA检查并调整药物。"),
                _row(
                    "冠脉CTA提示前降支狭窄，活动后仍有胸闷，已请介入组会诊评估造影。",
                    "2026-06-02 09:00:00",
                ),
            ]
        },
        source_complete=True,
    )
    assert different["status"] == "compliant"
    assert "复核" not in repr(different)

    exact_threshold = course._copy_result(
        {
            "daily_course_record": [
                _row("a" * 21 + "b" * 9),
                _row("a" * 21 + "c" * 9, "2026-06-02 09:00:00"),
            ]
        },
        source_complete=True,
    )
    assert exact_threshold["metadata"]["maximum_similarity"] == 0.7
    assert exact_threshold["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("llm_output", "expected_status"),
    [
        ({"is_compliant": True}, "compliant"),
        ({"is_compliant": False}, "non_compliant"),
    ],
)
async def test_017_gray_similarity_uses_one_cropped_llm_call(
    monkeypatch, llm_output: dict, expected_status: str
):
    common_blocks = [
        "患者神志清楚生命体征平稳腹部柔软无明显压痛",
        "双肺呼吸音清心律齐双下肢无明显水肿",
        "继续观察症状体征以及复查指标变化",
        "已向患者及家属说明当前病情和后续安排",
    ]
    left = "。".join(
        (
            common_blocks[0],
            "今日腹痛减轻进食改善复查炎症指标下降",
            common_blocks[1],
            "停止静脉补液改为口服药物准备出院",
            common_blocks[2],
            common_blocks[3],
        )
    )
    right = "。".join(
        (
            common_blocks[0],
            "今日仍有发热咳嗽复查胸部影像提示感染",
            common_blocks[1],
            "继续静脉抗感染并增加雾化治疗暂不出院",
            common_blocks[2],
            common_blocks[3],
        )
    )

    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(left), "document_id": "safe-left"},
            {
                **_row(right, "2026-06-02 09:00:00"),
                "document_id": "safe-right",
            },
        ]
        if kwargs["source_key"] == "daily_course_record"
        else [],
    )
    client = _Client([llm_output])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [expected_status]
    assert result.results[0]["metadata"]["reason_code"] == "copy_gray_llm"
    assert result.results[0]["metadata"]["executor_type"] == "llm"
    assert result.llm_call_count == 1
    assert result.total_tokens == 45
    assert len(client.prompts) == 1
    assert "只比较以下两份" in client.prompts[0]
    assert "safe-left" not in client.prompts[0]
    assert "safe-right" not in client.prompts[0]
    assert left not in repr(result)
    assert right not in repr(result)


@pytest.mark.asyncio
async def test_017_long_template_block_below_95_percent_uses_one_cropped_llm_call(
    monkeypatch,
):
    template = (
        "患者神志清楚，生命体征平稳，双肺呼吸音清，心律齐，腹部柔软，"
        "双下肢无水肿，继续观察病情变化并复查相关指标。"
    ) * 5
    left = (
        f"{template}今日腹痛明显缓解，炎症指标下降，停止静脉补液，"
        "调整为口服治疗并准备出院。"
    )
    right = (
        f"{template}今日出现发热咳嗽，胸部影像提示感染进展，"
        "继续静脉抗感染并增加雾化治疗，暂缓出院。"
    )

    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(left), "document_id": "safe-left"},
            {
                **_row(right, "2026-06-02 09:00:00"),
                "document_id": "safe-right",
            },
        ]
        if kwargs["source_key"] == "senior_course_record"
        else [],
    )
    client = _Client([{"is_compliant": True}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant"]
    assert 0.70 < result.results[0]["metadata"]["maximum_similarity"] < 0.95
    assert result.results[0]["metadata"]["reason_code"] == "copy_gray_llm"
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "只比较以下两份" in client.prompts[0]
    assert left not in repr(result)
    assert right not in repr(result)


@pytest.mark.asyncio
async def test_017_strong_copy_uses_python_without_model(monkeypatch):
    copied = (
        "患者神志清楚，生命体征平稳，查体无明显变化。"
        "复查结果与前次一致，继续当前治疗方案并密切观察病情变化。"
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(copied), "document_id": "safe-left"},
            {
                **_row(copied, "2026-06-02 09:00:00"),
                "document_id": "safe-right",
            },
        ]
        if kwargs["source_key"] == "daily_course_record"
        else [],
    )
    client = _Client([{"is_compliant": True}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.results[0]["metadata"]["reason_code"] == "strong_copy_evidence"
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("client", "expected_reason"),
    [
        (_Client(["not-json"]), "copy_llm_invalid_output"),
        (_Client([RuntimeError("raw Bearer_secret 13800138000")]), "copy_llm_failure"),
    ],
)
async def test_017_gray_llm_failure_is_safe_data_gap(
    monkeypatch, client: _Client, expected_reason: str
):
    common = "患者神志清楚生命体征平稳腹部柔软双肺呼吸音清继续观察病情变化"
    left = f"{common}今日腹痛减轻复查指标下降停止静脉补液{common}"
    right = f"{common}今日仍有发热复查提示感染继续静脉抗感染{common}"
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(left), "document_id": "safe-left"},
            {
                **_row(right, "2026-06-02 09:00:00"),
                "document_id": "safe-right",
            },
        ]
        if kwargs["source_key"] == "daily_course_record"
        else [],
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.results[0]["metadata"]["reason_code"] == expected_reason
    assert result.llm_call_count == 1
    assert "Bearer_secret" not in repr(result)
    assert "13800138000" not in repr(result)
    assert left not in repr(result)
    assert right not in repr(result)


@pytest.mark.asyncio
async def test_017_uses_complete_current_visit_sources_instead_of_truncated_bundle(
    monkeypatch,
):
    bundle_rows = [
        _row(f"第{index}次病程内容各不相同，仅用于证明旧投影不完整。")
        for index in range(1, 4)
    ]
    copied = "患者神志清楚，生命体征平稳，继续原治疗方案并密切观察病情变化。"
    source_rows = {
        "daily_course_record": [
            _row(
                f"完整来源中的日常病程记录第{index}次，患者症状、检查结果、"
                f"治疗方案和后续观察计划均按当日实际情况记录。"
            )
            for index in range(1, 10)
        ],
        "senior_course_record": [
            _row(copied, "2026-06-10 09:00:00"),
            _row(copied, "2026-06-11 09:00:00"),
        ],
    }
    reader_calls: list[str] = []

    def _read(**kwargs):
        source_key = str(kwargs["source_key"])
        reader_calls.append(source_key)
        return list(source_rows[source_key])

    monkeypatch.setattr(course, "read_luxian_0609_native_source_rows", _read)

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={"daily_course_record": bundle_rows}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert reader_calls == ["daily_course_record", "senior_course_record"]
    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.llm_call_count == 0
    metadata = result.results[0]["metadata"]
    assert metadata["comparable_document_count"] == 11
    assert metadata["maximum_similarity"] == 1.0
    assert metadata["similarity_threshold"] == 0.7
    assert metadata["best_match_source_types"] == [
        "senior_course_record",
        "senior_course_record",
    ]
    assert copied not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reader_result", "expected_status", "expected_reason"),
    [
        ([], "not_applicable", "insufficient_comparable_course_records"),
        (
            RuntimeError("raw SQL Bearer_secret 13800138000"),
            "data_gap",
            "course_comparison_source_unavailable",
        ),
    ],
)
async def test_017_complete_source_empty_or_failure_keeps_controlled_state(
    monkeypatch,
    reader_result,
    expected_status: str,
    expected_reason: str,
):
    def _read(**_kwargs):
        if isinstance(reader_result, Exception):
            raise reader_result
        return list(reader_result)

    monkeypatch.setattr(course, "read_luxian_0609_native_source_rows", _read)

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={"daily_course_record": [_row("旧投影内容不应兜底。")]}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == [expected_status]
    assert result.results[0]["metadata"]["reason_code"] == expected_reason
    assert result.llm_call_count == 0
    assert "Bearer_secret" not in repr(result)
    assert "13800138000" not in repr(result)


@pytest.mark.asyncio
async def test_017_without_complete_coordinates_or_with_source_limit_is_data_gap(
    monkeypatch,
):
    reader_calls: list[str] = []

    def _read(**kwargs):
        reader_calls.append(str(kwargs["source_key"]))
        return [
            {
                **_row(f"完整来源第{index}条病程记录，患者病情和治疗计划均有详细描述。"),
                "document_id": f"safe-{index}",
            }
            for index in range(200)
        ]

    monkeypatch.setattr(course, "read_luxian_0609_native_source_rows", _read)

    no_coordinates = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(
            documents={
                "daily_course_record": [
                    _row("a" * 40),
                    _row("a" * 40, "2026-06-02 09:00:00"),
                ]
            }
        ),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in no_coordinates.results] == ["data_gap"]
    assert reader_calls == []

    truncated = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert [item["status"] for item in truncated.results] == ["data_gap"]
    assert truncated.results[0]["metadata"]["reason_code"] == (
        "course_comparison_source_truncated"
    )
    assert reader_calls == ["daily_course_record"]


@pytest.mark.asyncio
async def test_017_does_not_treat_duplicate_database_rows_as_two_course_records(
    monkeypatch,
):
    row = {
        **_row("患者病情稳定，继续当前治疗方案并观察症状、体征及复查指标变化。"),
        "document_id": "safe-document-ref",
    }

    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [dict(row), dict(row)]
        if kwargs["source_key"] == "daily_course_record"
        else [],
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["not_applicable"]
    assert result.results[0]["metadata"]["comparable_document_count"] == 1
    assert "safe-document-ref" not in repr(result)


@pytest.mark.asyncio
async def test_018_requires_complaint_and_primary_diagnosis_material():
    client = _Client([])
    incomplete = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(
            documents={"admission_record": [_row("主诉：腹痛2天。现病史待查。")]}
        ),
        llm_client=client,
    )
    assert [item["status"] for item in incomplete.results] == ["data_gap"]
    assert incomplete.llm_call_count == 0

    client = _Client([{"is_compliant": True}])
    complete = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(
            documents={"admission_record": [_row("主诉：反复胸痛3个月。入院诊断：不稳定型心绞痛。")]}
        ),
        llm_client=client,
    )
    assert [item["status"] for item in complete.results] == ["compliant"]
    assert complete.llm_call_count == 1


@pytest.mark.asyncio
async def test_model_failure_and_invalid_json_are_isolated_and_safe():
    secret = "Bearer_secret_13800138000"
    client = _Client([RuntimeError(secret), f"not-json {secret}"])
    payload = _payload(
        documents={
            "admission_record": [_row("主诉：反复胸痛3个月。入院诊断：不稳定型心绞痛。")],
            "first_course_record": [_row("首次病程病例特点与诊断依据。")],
        }
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016", "LX0609-018"),
        wrapper_rules=[_wrapper("LX0609-016"), _wrapper("LX0609-018")],
        evidence_payload=payload,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 2
    assert secret not in repr(result)
