from __future__ import annotations

import json
import re
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.luxian_0609 import native_course_quality_execution as course
from app.services.luxian_0609.course_quality import rules_016_017
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.decision_model import EvidenceState
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
    CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
)


def _severity_session(
    *,
    rows: list[dict] | None = None,
    failure: Exception | None = None,
    truncated: bool = False,
    daily_rows: list[dict] | None = None,
    senior_rows: list[dict] | None = None,
    external_rows: dict[str, list[dict]] | None = None,
    external_failures: dict[str, Exception] | None = None,
    external_truncated: frozenset[str] = frozenset(),
    course_failure: Exception | None = None,
    course_truncated: bool = False,
    discharge_failure: Exception | None = None,
    discharge_truncated: bool = False,
    discharge_rows: list[dict] | None = None,
    admission_rows: list[dict] | None = None,
    evaluation_as_of_date: str | None = "2026-01-03",
    evaluation_horizon_policy: str | None = None,
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
        if source_key == CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY:
            if discharge_failure is not None:
                raise discharge_failure
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=(
                    discharge_rows
                    if discharge_rows is not None
                    else (
                        [{"discharge_datetime": "2026-01-04 00:00:00"}]
                        if discharge_truncated
                        else []
                    )
                ),
                truncated=discharge_truncated,
                limit_rows=1,
            )
        if source_key == "inpat_registration":
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=admission_rows or [],
                truncated=False,
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
        if source_key in (external_rows or {}):
            if source_key in (external_failures or {}):
                raise (external_failures or {})[source_key]
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=(external_rows or {})[source_key],
                truncated=source_key in external_truncated,
                limit_rows=50,
            )
        if source_key in (external_failures or {}):
            raise (external_failures or {})[source_key]
        if source_key in external_truncated:
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=[{}],
                truncated=True,
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
        evaluation_horizon_policy=evaluation_horizon_policy,
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


async def _run_typed_009(session, client):
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
    def __init__(
        self,
        outputs: list[object],
        *,
        complete_009_candidates: bool = True,
    ) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []
        self.complete_009_candidates = complete_009_candidates

    async def generate(self, prompt: str, **_: Any) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        if (
            self.complete_009_candidates
            and isinstance(output, dict)
            and isinstance(output.get("events"), list)
            and (expected_refs := re.findall(r"\[external_event_ref=(E\d+)\]", prompt))
        ):
            supplied = list(output["events"])
            supplied_refs = [str(item.get("event_ref") or "") for item in supplied]
            if (
                len(supplied_refs) == len(set(supplied_refs))
                and set(supplied_refs).issubset(set(expected_refs))
            ):
                supplied_by_ref = {
                    str(item["event_ref"]): item for item in supplied
                }
                output = {
                    **output,
                    "events": [
                        supplied_by_ref.get(
                            ref,
                            {
                                "event_ref": ref,
                                "change_category": "exam_lab",
                                "is_explicit_change": False,
                                "corresponding_course_ref": "",
                            },
                        )
                        for ref in expected_refs
                    ],
                }
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


class _UnexpectedLLMClient:
    """017 的纯相似度路径若调用模型，测试必须立刻失败。"""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_: Any) -> dict:
        self.prompts.append(prompt)
        raise AssertionError("LX0609-017 不得调用 LLM")


class _CopyReviewClient:
    def __init__(self, verdict: str = "substantial_copy", response: object = None):
        self.verdict = verdict
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def generate(self, prompt: str, **kwargs: Any) -> dict:
        self.calls.append({"prompt": prompt, **kwargs})
        if isinstance(self.response, Exception):
            raise self.response
        if isinstance(self.response, dict):
            return self.response
        pairs = re.findall(
            r'"pair_ref":"(P\d+)","left_ref":"(D\d+)","right_ref":"(D\d+)"',
            prompt,
        )
        return {
            "content": json.dumps(
                {
                    "schema_version": "lx0609_017_v1",
                    "pair_results": [
                        {
                            "pair_ref": pair_ref,
                            "verdict": self.verdict,
                            "document_refs": [left_ref, right_ref],
                        }
                        for pair_ref, left_ref, right_ref in pairs
                    ],
                }
            ),
            "usage": {"prompt_tokens": 40, "completion_tokens": 8, "total_tokens": 48},
        }


def _copy_review_response(
    pair_results: list[dict[str, Any]],
    *,
    usage: object = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "content": json.dumps(
            {
                "schema_version": "lx0609_017_v1",
                "pair_results": pair_results,
            }
        )
    }
    if usage is None:
        usage = {"prompt_tokens": 40, "completion_tokens": 8, "total_tokens": 48}
    if usage is not False:
        response["usage"] = usage
    return response


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
        llm_client=_CopyReviewClient("substantial_copy"),
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.llm_call_count == 1
    assert result.total_tokens == 48
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
        llm_client=None,
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
    assert result.customer_display_facts == (
        (
            "LX0609-017",
            {
                "failure_kind": "copy_similarity_threshold_exceeded",
                "copy_similarity": 1.0,
                "copy_similarity_threshold": 0.7,
                "copy_document_sources": [
                    "daily_course_record",
                    "senior_course_record",
                ],
                "copy_document_record_times": [
                    "2026-01-01 09:00:00",
                    "2026-01-02 09:00:00",
                ],
                "copy_match_pairs": [
                    {
                        "source_types": [
                            "daily_course_record",
                            "senior_course_record",
                        ],
                        "record_times": [
                            "2026-01-01 09:00:00",
                            "2026-01-02 09:00:00",
                        ],
                        "similarity": 1.0,
                    }
                ],
            },
        ),
    )
    assert result.llm_call_count == 0
    assert not result.prompt_tokens and not result.total_tokens
    assert private_marker not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_state", "expected_state", "expected_reason"),
    (
        (
            "empty",
            CustomerFinalState.NOT_APPLICABLE,
            "eligibility_not_met",
        ),
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
    client = _Client(
        [
            {
                "diagnostic_relation_state": "supported",
                "diagnostic_reason_dimensions": [
                    "anatomic_site",
                    "symptom_pattern",
                ],
                "diagnostic_rationale_code": "supported",
                "medical_analysis": "胸痛症状支持心绞痛诊断方向。",
            }
        ]
    )
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        decision_rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_UnexpectedLLMClient(),
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
async def test_typed_017_python_path_matches_raw_state_and_keeps_privacy():
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
    raw_client = _CopyReviewClient("substantial_copy")
    typed_client = _CopyReviewClient("substantial_copy")
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
    assert raw.total_tokens == typed.total_tokens == 48
    assert len(raw_client.calls) == len(typed_client.calls) == 1
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
        "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [
            {"discharge_datetime": "2026-01-02 12:00:00"}
        ],
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
        evaluation_as_of_date="2026-01-02",
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
    ("horizon", "expected_state", "expected_reason"),
    [
        ("2026-01-04 07:59:59", CustomerFinalState.COMPLIANT, "requirement_within_threshold"),
        ("2026-01-04 08:00:01", CustomerFinalState.DATA_GAP, "authoritative_time_missing"),
    ],
)
async def test_course_007_uses_admission_to_first_record_maturity_boundary(
    horizon: str,
    expected_state: CustomerFinalState,
    expected_reason: str,
) -> None:
    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY: [],
            "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [
                {"discharge_datetime": horizon}
            ],
            "daily_course_record": [],
            "senior_course_record": [],
        }
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
        evaluation_as_of_date="2026-01-04",
        row_reader=read,
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
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-007",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("evaluation_as_of_date", "expected_state", "expected_reason"),
    [
        ("2026-01-03", CustomerFinalState.COMPLIANT, "requirement_within_threshold"),
        ("2026-01-04", CustomerFinalState.DATA_GAP, "authoritative_time_missing"),
        ("2026-01-05", CustomerFinalState.DATA_GAP, "authoritative_time_missing"),
    ],
)
async def test_course_007_uses_date_only_evaluation_horizon_conservatively(
    evaluation_as_of_date: str,
    expected_state: CustomerFinalState,
    expected_reason: str,
) -> None:
    """冻结评价日缺少时分秒时，只对末段作可证明的三态判断。"""

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY: [],
            "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [],
            "daily_course_record": [],
            "senior_course_record": [],
        }
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
        evaluation_as_of_date=evaluation_as_of_date,
        row_reader=read,
    )
    assert "horizon_datetime" not in session.materials.rows("evaluation_context.horizon")[0]
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
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-007",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is expected_state
    assert reduced[0].reason_code == expected_reason
    if expected_state is CustomerFinalState.NON_COMPLIANT:
        facts = dict(result.customer_display_facts)["LX0609-007"]
        assert facts["interval_end_source"] == "evaluation_context.horizon"
        assert facts["interval_end_date"] == evaluation_as_of_date
        assert facts["interval_end_precision"] == "date"
        assert "interval_end_time" not in facts
        assert "interval_end_document_id" not in facts


@pytest.mark.asyncio
async def test_course_007_date_only_horizon_does_not_hide_exact_internal_gap() -> None:
    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY: [],
            "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [],
            "daily_course_record": [_row("已精确计时的病程", "2026-01-05 09:00:00")],
            "senior_course_record": [],
        }
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
        evaluation_as_of_date="2026-01-08",
        row_reader=read,
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
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-007",),
        snapshot=session.snapshot,
    )

    assert reduced[0].reason_code == "threshold_exceeded"
    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
async def test_course_007_date_only_horizon_with_same_day_record_is_data_gap() -> None:
    """同日病程可能早于冻结时点，不能据此前一条病程断言尾段超时。"""

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY: [],
            "inpat_registration": [{"admission_datetime": "2026-01-14 08:00:00"}],
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [],
            "daily_course_record": [
                _row("末次既有病程", "2026-01-14 08:00:00"),
                _row("冻结当日候选病程", "2026-01-18 01:00:00"),
            ],
            "senior_course_record": [],
        }
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
        evaluation_as_of_date="2026-01-18",
        row_reader=read,
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
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-007",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "authoritative_time_missing"
    assert result.customer_display_facts == ()


@pytest.mark.asyncio
async def test_course_007_checks_last_record_to_evaluation_horizon() -> None:
    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY: [],
            "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [
                {"discharge_datetime": "2026-01-05 08:00:01"}
            ],
            "daily_course_record": [
                _row("首次查房", "2026-01-01 08:00:00"),
                _row("末次查房", "2026-01-02 08:00:00"),
            ],
            "senior_course_record": [],
        }
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
        evaluation_as_of_date="2026-01-05",
        row_reader=read,
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
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-007",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "threshold_exceeded"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "daily_rows", "horizon", "expected_document_field"),
    [
        (
            "admission_to_first",
            [
                {
                    **_row("首条病程", "2026-01-04 08:00:01"),
                    "document_id": "first-course-document",
                }
            ],
            "2026-01-04 09:00:00",
            ("interval_end_document_id", "first-course-document"),
        ),
        (
            "last_to_horizon",
            [
                {
                    **_row("末条病程", "2026-01-02 08:00:00"),
                    "document_id": "last-course-document",
                }
            ],
            "2026-01-05 08:00:01",
            ("interval_start_document_id", "last-course-document"),
        ),
    ],
)
async def test_course_007_keeps_real_document_id_at_boundary_interval(
    scenario: str,
    daily_rows: list[dict],
    horizon: str,
    expected_document_field: tuple[str, str],
) -> None:
    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY: [],
            "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [
                {"discharge_datetime": horizon}
            ],
            "daily_course_record": daily_rows,
            "senior_course_record": [],
        }
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
        evaluation_as_of_date=horizon[:10],
        row_reader=read,
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
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-007",),
        snapshot=session.snapshot,
    )

    assert scenario
    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-007"]
    assert facts[expected_document_field[0]] == expected_document_field[1]
    if scenario == "admission_to_first":
        assert "interval_start_document_id" not in facts
    else:
        assert "interval_end_document_id" not in facts


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected_state", "expected_reason"),
    [
        ("unstable", CustomerFinalState.NOT_APPLICABLE, "eligibility_not_met"),
        ("over_72h", CustomerFinalState.NON_COMPLIANT, "threshold_exceeded"),
        ("submit_time", CustomerFinalState.COMPLIANT, "requirement_within_threshold"),
        ("missing_time", CustomerFinalState.COMPLIANT, "requirement_within_threshold"),
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
        if source_key == "inpat_registration":
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=[{"admission_datetime": "2026-01-01 08:00:00"}],
                truncated=False,
                limit_rows=50,
            )
        if source_key == CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY:
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=[{
                    "discharge_datetime": (
                        "2026-01-05 09:00:02"
                        if scenario == "over_72h"
                        else "2026-01-02 12:00:00"
                    )
                }],
                truncated=False,
                limit_rows=50,
            )
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
                    {
                        **_row("首次查房。", "2026-01-01 09:00:00"),
                        "document_id": "round-1",
                    },
                    {
                        **_row("再次查房。", "2026-01-05 09:00:01"),
                        "document_id": "round-2",
                    },
                ]
            elif scenario == "submit_time":
                rows = [
                    {
                        "record_content": "首次查房。",
                        "record_time": None,
                        "submit_datetime": "2026-01-01 09:00:00",
                    },
                    {
                        "record_content": "再次查房。",
                        "record_time": None,
                        "submit_datetime": "2026-01-02 09:00:00",
                    },
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
        evaluation_as_of_date=("2026-01-05" if scenario == "over_72h" else "2026-01-02"),
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
    if scenario == "over_72h":
        assert result.customer_display_facts == (("LX0609-007", {
            "failure_kind": "course_record_interval_over_72h",
            "interval_start_source": "daily_course_record",
            "interval_end_source": "daily_course_record",
            "interval_start_time": "2026-01-01 09:00:00",
            "interval_end_time": "2026-01-05 09:00:01",
            "interval_start_position": 1,
            "interval_end_position": 2,
            "record_count": 2,
            "interval_seconds": 345601,
            "overdue_seconds": 86401,
            "interval_hours": 96.0,
            "threshold_hours": 72,
            "recorded_dates": ["2026-01-01", "2026-01-05"],
            "interval_start_document_id": "round-1",
            "interval_end_document_id": "round-2",
        }),)
        assert "首次查房" not in repr(result.customer_display_facts)
    elif scenario == "submit_time":
        assert result.customer_display_facts == (("LX0609-007", {
            "failure_kind": "course_record_interval_within_72h",
            "interval_start_source": "daily_course_record",
            "interval_end_source": "daily_course_record",
            "interval_start_time": "2026-01-01 09:00:00",
            "interval_end_time": "2026-01-02 09:00:00",
            "interval_start_position": 1,
            "interval_end_position": 2,
            "record_count": 2,
            "interval_seconds": 86400,
            "overdue_seconds": 0,
            "interval_hours": 24.0,
            "threshold_hours": 72,
            "recorded_dates": ["2026-01-01", "2026-01-02"],
        }),)
    elif scenario == "unstable":
        assert result.customer_display_facts == (("LX0609-007", {
            "failure_kind": "unstable_patient_order_present",
            "stable_course_rule_applicable": False,
        }),)
    elif scenario == "missing_time":
        assert dict(result.customer_display_facts)["LX0609-007"]["failure_kind"] == (
            "course_record_interval_within_72h"
        )
    else:
        assert result.customer_display_facts == ()


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
            (CustomerFinalState.NOT_APPLICABLE, CustomerFinalState.COMPLIANT),
            ("trigger_absent_complete", "requirement_satisfied"),
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
            "severity_status_unresolved",
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
async def test_course_008_009_typed_natural_day_truth_table_requires_009_semantic_client(
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
    elif scenario in {"source_unavailable", "severity_status_unresolved"}:
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
async def test_2496813_009_daily_frequency_and_semantics_are_both_compliant():
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-07-07 14:25:24",
                "row_ref": "9" * 64,
            }
        ],
        daily_rows=[
            _row("七月七日病程", "2026-07-07 18:04:51"),
            _row("七月八日病程", "2026-07-08 11:47:05"),
            _row("七月十日病程", "2026-07-10 20:38:53"),
            _row("七月十一日病程", "2026-07-11 11:41:05"),
            _row("七月十三日病程", "2026-07-13 17:09:07"),
        ],
        senior_rows=[
            _row("七月九日上级查房", "2026-07-09 10:24:03"),
            _row("七月十二日上级查房", "2026-07-12 09:30:26"),
        ],
        evaluation_as_of_date="2026-07-13",
    )
    client = _Client([{"events": []}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 0
    assert dict(result.customer_display_facts)["LX0609-009"] == {
        "failure_kind": "critical_daily_record_coverage_satisfied",
        "severity": "critical",
        "evaluated_scope": "critical_daily_course_coverage",
        "pending_scope": ["condition_change_course_documentation"],
        "anchor_date": "2026-07-07",
        "horizon_date": "2026-07-13",
        "required_dates": [
            "2026-07-07",
            "2026-07-08",
            "2026-07-09",
            "2026-07-10",
            "2026-07-11",
            "2026-07-12",
            "2026-07-13",
        ],
        "covered_dates": [
            "2026-07-07",
            "2026-07-08",
            "2026-07-09",
            "2026-07-10",
            "2026-07-11",
            "2026-07-12",
            "2026-07-13",
        ],
        "missing_count": 0,
    }
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("horizon", "record_times", "expected_state", "expected_reason"),
    [
        ("2026-01-01", [], CustomerFinalState.COMPLIANT, "requirement_within_threshold"),
        ("2026-01-03", [], CustomerFinalState.COMPLIANT, "requirement_within_threshold"),
        ("2026-01-04", [], CustomerFinalState.NON_COMPLIANT, "threshold_exceeded"),
        (
            "2026-01-05",
            ["2026-01-01 08:00:00", "2026-01-04 08:00:00"],
            CustomerFinalState.NON_COMPLIANT,
            "threshold_exceeded",
        ),
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
    assert "2026-01" not in repr(result.decisions)
    assert "查房记录" not in repr(result.decisions)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_state", "expected_state", "expected_reason"),
    [
        ("effective", CustomerFinalState.COMPLIANT, "requirement_within_threshold"),
        ("excluded", CustomerFinalState.NOT_APPLICABLE, "trigger_absent_complete"),
        ("unresolved", CustomerFinalState.DATA_GAP, "source_unavailable"),
    ],
)
async def test_course_008_respects_effective_cancelled_and_unknown_order_statuses(
    status_state: str,
    expected_state: CustomerFinalState,
    expected_reason: str,
) -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "serious",
                "status_state": status_state,
                "prescribed_datetime": "2026-01-01 08:00:00",
                "row_ref": "s" * 64,
            }
        ],
        evaluation_as_of_date="2026-01-03",
    )

    result, reduced = await _run_typed_severity(session)

    assert reduced[0].final_state is expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_course_008_009_stop_events_cut_off_the_required_interval() -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "serious",
                "event_kind": "start",
                "status_state": "effective",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "row_ref": "s" * 64,
            },
            {
                "severity": "serious",
                "event_kind": "end",
                "status_state": "effective",
                "prescribed_datetime": "2026-01-02 08:00:00",
                "row_ref": "t" * 64,
            },
            {
                "severity": "critical",
                "event_kind": "start",
                "status_state": "effective",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "row_ref": "c" * 64,
            },
            {
                "severity": "critical",
                "event_kind": "end",
                "status_state": "effective",
                "prescribed_datetime": "2026-01-02 08:00:00",
                "row_ref": "d" * 64,
            },
        ],
        daily_rows=[
            _row("第一日病程", "2026-01-01 08:00:00"),
            _row("第二日病程", "2026-01-02 08:00:00"),
        ],
        evaluation_as_of_date="2026-01-05",
    )

    result, reduced = await _run_typed_severity(session)

    assert tuple(item.final_state for item in reduced) == (
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    )
    assert tuple(item.reason_code for item in reduced) == (
        "requirement_within_threshold",
        "requirement_satisfied",
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_course_008_009_restart_after_stop_opens_a_new_required_interval() -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "serious", "event_kind": "start", "status_state": "effective",
                "prescribed_datetime": "2026-01-01 08:00:00", "row_ref": "s" * 64,
            },
            {
                "severity": "serious", "event_kind": "end", "status_state": "effective",
                "prescribed_datetime": "2026-01-02 08:00:00", "row_ref": "t" * 64,
            },
            {
                "severity": "serious", "event_kind": "start", "status_state": "effective",
                "prescribed_datetime": "2026-01-04 08:00:00", "row_ref": "u" * 64,
            },
            {
                "severity": "critical", "event_kind": "start", "status_state": "effective",
                "prescribed_datetime": "2026-01-01 08:00:00", "row_ref": "c" * 64,
            },
            {
                "severity": "critical", "event_kind": "end", "status_state": "effective",
                "prescribed_datetime": "2026-01-02 08:00:00", "row_ref": "d" * 64,
            },
            {
                "severity": "critical", "event_kind": "start", "status_state": "effective",
                "prescribed_datetime": "2026-01-04 08:00:00", "row_ref": "e" * 64,
            },
        ],
        daily_rows=[
            _row("第一日病程", "2026-01-01 08:00:00"),
            _row("第二日病程", "2026-01-02 08:00:00"),
        ],
        evaluation_as_of_date="2026-01-07",
    )

    result, reduced = await _run_typed_severity(session)

    assert tuple(item.final_state for item in reduced) == (
        CustomerFinalState.NON_COMPLIANT,
        CustomerFinalState.NON_COMPLIANT,
    )
    assert tuple(item.reason_code for item in reduced) == (
        "threshold_exceeded",
        "requirement_violated",
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_course_008_display_uses_largest_adjacent_gap_not_active_span_length() -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "serious", "event_kind": "start", "status_state": "effective",
                "prescribed_datetime": "2026-01-01 08:00:00", "row_ref": "s" * 64,
            },
            {
                "severity": "serious", "event_kind": "end", "status_state": "effective",
                "prescribed_datetime": "2026-01-04 08:00:00", "row_ref": "e" * 64,
            },
        ],
        daily_rows=[_row("中间病程", "2026-01-02 08:00:00")],
        evaluation_as_of_date="2026-01-05",
    )

    result, reduced = await _run_typed_severity(session)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-008"]["maximum_gap_days"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("discharge_truncated", [False, True])
async def test_course_008_uses_frozen_as_of_when_discharge_source_unavailable(
    discharge_truncated: bool,
) -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "serious",
                "status_state": "effective",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "row_ref": "h" * 64,
            }
        ],
        evaluation_as_of_date="2026-01-03",
        discharge_failure=(None if discharge_truncated else SourceEvidenceUnavailable()),
        discharge_truncated=discharge_truncated,
    )

    result, reduced = await _run_typed_severity(session)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_within_threshold"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_course_008_discharge_query_error_is_technical_error_even_with_as_of() -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "serious",
                "status_state": "effective",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "row_ref": "e" * 64,
            }
        ],
        evaluation_as_of_date="2026-01-03",
        discharge_failure=SourceEvidenceQueryError(),
    )

    result, reduced = await _run_typed_severity(session)

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "source_query_error"
    assert result.llm_call_count == 0


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
            CustomerFinalState.COMPLIANT,
            "requirement_satisfied",
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
async def test_course_009_checks_every_day_through_horizon_and_fails_without_semantic_client(
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
async def test_course_008_009_emit_only_safe_missing_interval_facts() -> None:
    serious_session = _severity_session(
        rows=[{
            "severity": "serious",
            "prescribed_datetime": "2026-01-01 08:00:00",
            "row_ref": "s" * 64,
        }],
        daily_rows=[_row("PRIVATE_COURSE_TEXT", "2026-01-04 08:00:00")],
        evaluation_as_of_date="2026-01-04",
    )
    serious_result, serious_reduced = await _run_typed_severity(serious_session)
    assert serious_reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert serious_result.customer_display_facts[0] == (
        "LX0609-008",
        {
            "failure_kind": "severity_course_gap_exceeded",
            "severity": "serious",
            "anchor_date": "2026-01-01",
            "horizon_date": "2026-01-04",
            "gap_start_date": "2026-01-01",
            "gap_end_date": "2026-01-04",
            "gap_days": 3,
            "threshold_days": 2,
            "recorded_dates": ["2026-01-04"],
        },
    )

    critical_session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-01-01 08:00:00",
            "row_ref": "c" * 64,
        }],
        daily_rows=[
            _row("PRIVATE_COURSE_TEXT", "2026-01-01 08:00:00"),
            _row("PRIVATE_COURSE_TEXT", "2026-01-03 08:00:00"),
        ],
        evaluation_as_of_date="2026-01-03",
    )
    critical_result, critical_reduced = await _run_typed_severity(critical_session)
    assert critical_reduced[1].final_state is CustomerFinalState.NON_COMPLIANT
    assert critical_result.customer_display_facts[0] == (
        "LX0609-009",
        {
            "failure_kind": "critical_daily_record_missing",
            "severity": "critical",
            "evaluated_scope": "critical_daily_course_coverage",
            "pending_scope": ["condition_change_course_documentation"],
            "anchor_date": "2026-01-01",
            "horizon_date": "2026-01-03",
            "required_dates": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "covered_dates": ["2026-01-01", "2026-01-03"],
            "missing_dates": ["2026-01-02"],
            "missing_count": 1,
            "missing_first_date": "2026-01-02",
            "missing_last_date": "2026-01-02",
        },
    )
    assert "PRIVATE_COURSE_TEXT" not in repr(serious_result)
    assert "PRIVATE_COURSE_TEXT" not in repr(critical_result)


@pytest.mark.asyncio
async def test_course_009_daily_complete_without_external_candidates_needs_no_model() -> None:
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
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-009",),
        decision_rule_ids=("LX0609-009",),
        wrapper_rules=[_wrapper("LX0609-009")],
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
        expected_rule_ids=("LX0609-009",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "semantic_state",
    [
        "satisfied",
        "defect",
        "unknown",
    ],
)
async def test_course_009_rejects_legacy_semantic_state_payload(
    semantic_state: str,
) -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 23:59:59",
                "row_ref": "g" * 64,
            }
        ],
        daily_rows=[
            _row("PRIVATE_009_BODY 病情稳定，无新发变化。", "2026-01-01 08:00:00"),
            _row("病情变化已记录并及时处理。", "2026-01-02 08:00:00"),
            _row("病情平稳，继续观察。", "2026-01-03 08:00:00"),
        ],
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00",
            "exam_impression": "外部检查候选。",
        }]},
        evaluation_as_of_date="2026-01-03",
    )
    client = _Client([{"semantic_state": semantic_state}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "model_invalid_output"
    assert result.llm_call_count == 1
    assert result.total_tokens == 45
    assert len(client.prompts) == 1
    assert "PRIVATE_009_BODY" not in repr(result)


@pytest.mark.asyncio
async def test_course_009_semantic_call_binds_same_snapshot_external_event() -> None:
    """009 不能只看病程：同次检查变化必须进入一次裁剪语义事实。"""

    external_marker = "EXTERNAL_EVENT_ONLY_FOR_009"
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "row_ref": "j" * 64,
            }
        ],
        daily_rows=[
            _row("第一日病情稳定。", "2026-01-01 08:00:00"),
            _row("第二日继续观察。", "2026-01-02 08:00:00"),
        ],
        external_rows={
            "exam_item_report": [
                {
                    "report_time": "2026-01-02 10:00:00",
                    "exam_impression": external_marker,
                }
            ]
        },
        evaluation_as_of_date="2026-01-02",
    )
    client = _Client([{"events": []}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert result.llm_call_count == 1
    assert external_marker in client.prompts[0]
    assert external_marker not in repr(result)


@pytest.mark.asyncio
async def test_course_009_complete_exam_lab_rows_are_grouped_as_clinical_events() -> None:
    """完整来源的明细行不能因内部投影行数上限伪装成 source_truncated。"""

    lab_items = [
        {
            "document_id": f"LAB-ITEM-{index}",
            "test_id": "LAB-EVENT-1" if index < 5 else "LAB-EVENT-2",
            "item_name": f"检验项目{index}",
            "result": f"结果{index}",
            "report_time": (
                "2026-01-01 10:00:00"
                if index < 5
                else "2026-01-02 10:00:00"
            ),
        }
        for index in range(10)
    ]
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "row_ref": "n" * 64,
            }
        ],
        daily_rows=[
            _row("第一日病情记录。", "2026-01-01 08:00:00"),
            _row("第二日病情记录。", "2026-01-02 08:00:00"),
        ],
        external_rows={
            "exam_item_report": [
                {
                    "document_id": "EXAM-ROW-1",
                    "exam_id": "EXAM-EVENT-1",
                    "report_time": "2026-01-01 09:00:00",
                    "exam_impression": "检查结果。",
                }
            ],
            "labtest_master": [
                {
                    "test_id": "LAB-EVENT-1",
                    "report_datetime": "2026-01-01 10:00:00",
                    "labtest_subject": "检验事件一",
                },
                {
                    "test_id": "LAB-EVENT-2",
                    "report_datetime": "2026-01-02 10:00:00",
                    "labtest_subject": "检验事件二",
                },
            ],
            "labtest_item_report": lab_items,
        },
        evaluation_as_of_date="2026-01-02",
    )
    client = _Client([{"events": []}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert client.prompts[0].count("[external_event_ref=") == 3
    assert client.prompts[0].count("[course_event_ref=") == 2


@pytest.mark.asyncio
async def test_course_009_208790_shape_fits_one_event_window_call() -> None:
    """冻结208790结构：12+7病程、13条外部行仍只能调用一次模型。"""

    daily_rows = []
    for index in range(12):
        day = 7 + (index % 7)
        daily_rows.append(
            _row(
                f"每日病程{index}。" + "甲" * 800,
                f"2026-07-{day:02d} {8 + index % 8:02d}:00:00",
            )
        )
    senior_rows = [
        _row(
            f"上级查房{index}。" + "乙" * 1200,
            f"2026-07-{7 + index:02d} 15:00:00",
        )
        for index in range(7)
    ]
    lab_items = [
        {
            "test_id": "LAB-A" if index < 5 else "LAB-B",
            "item_name": f"项目{index}",
            "result": f"结果{index}",
            "report_time": (
                "2026-07-08 10:00:00"
                if index < 5
                else "2026-07-10 10:00:00"
            ),
        }
        for index in range(10)
    ]
    session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-07-07 14:25:24",
        }],
        daily_rows=daily_rows,
        senior_rows=senior_rows,
        external_rows={
            "exam_item_report": [{
                "exam_id": "EXAM-A",
                "report_time": "2026-07-09 10:00:00",
                "exam_impression": "检查结论。",
            }],
            "labtest_master": [
                {
                    "test_id": "LAB-A",
                    "report_datetime": "2026-07-08 10:00:00",
                    "labtest_subject": "检验A",
                },
                {
                    "test_id": "LAB-B",
                    "report_datetime": "2026-07-10 10:00:00",
                    "labtest_subject": "检验B",
                },
            ],
            "labtest_item_report": lab_items,
        },
        evaluation_as_of_date="2026-07-13",
    )
    client = _Client([{"events": []}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 1
    assert result.total_tokens == 45
    assert len(client.prompts) == 1
    assert client.prompts[0].count("[external_event_ref=") == 3
    assert client.prompts[0].count("[course_event_ref=") == 19


@pytest.mark.asyncio
async def test_course_009_208790_course_only_projection_needs_no_model() -> None:
    """冻结真实重建后的29份病程规模；没有外部事件时不得无意义调用模型。"""

    daily_rows = [
        _row(
            f"日常病程{index}。" + "甲" * 450,
            f"2026-07-{7 + index % 7:02d} {8 + index % 8:02d}:00:00",
        )
        for index in range(22)
    ]
    senior_lengths = (915, 4140, 2104, 2022, 1195, 1579, 1742)
    senior_rows = [
        _row(
            f"上级查房{index}。" + "乙" * length,
            f"2026-07-{7 + index:02d} 15:00:00",
        )
        for index, length in enumerate(senior_lengths)
    ]
    session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-07-07 14:25:24",
        }],
        daily_rows=daily_rows,
        senior_rows=senior_rows,
        evaluation_as_of_date="2026-07-13",
    )
    client = _Client([{"events": []}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_course_009_course_record_is_documentation_not_a_model_candidate() -> None:
    session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-01-01 08:00:00",
        }],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("患者新发胸痛，已立即评估处理。", "2026-01-02 10:00:00"),
        ],
        evaluation_as_of_date="2026-01-02",
    )
    client = _Client([{"events": [{
        "event_ref": "C02",
        "change_category": "subjective",
        "change_time": "2026-01-02 10:00:00",
        "is_explicit_change": True,
        "corresponding_course_ref": "C02",
    }]}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 0
    assert client.prompts == []
    facts = dict(result.customer_display_facts)["LX0609-009"]
    assert facts["failure_kind"] == "critical_daily_record_coverage_satisfied"


@pytest.mark.asyncio
async def test_course_009_unknown_model_event_ref_fails_closed() -> None:
    """模型编造事件引用是输出无效，不是客户病历缺少权威时间。"""

    session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-01-01 08:00:00",
        }],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("次日病危记录。", "2026-01-02 09:00:00"),
        ],
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00",
            "exam_impression": "外部检查候选。",
        }]},
        evaluation_as_of_date="2026-01-02",
    )
    client = _Client([{"events": [{
        "event_ref": "Z99",
        "change_category": "objective",
        "is_explicit_change": True,
        "corresponding_course_ref": "",
    }]}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "model_invalid_output"
    assert result.llm_call_count == 1
    assert dict(result.customer_display_facts)["LX0609-009"]["failure_kind"] == (
        "critical_daily_record_coverage_satisfied"
    )


@pytest.mark.asyncio
async def test_course_009_model_must_classify_every_external_candidate_once() -> None:
    session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-01-01 08:00:00",
        }],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("次日病危记录。", "2026-01-02 12:00:00"),
        ],
        external_rows={
            "exam_item_report": [
                {
                    "exam_id": "EXAM-1",
                    "report_time": "2026-01-01 10:00:00",
                    "exam_impression": "检查事件一。",
                },
                {
                    "exam_id": "EXAM-2",
                    "report_time": "2026-01-02 10:00:00",
                    "exam_impression": "检查事件二。",
                },
            ]
        },
        evaluation_as_of_date="2026-01-02",
    )
    client = _Client([{"events": [{
        "event_ref": "E01",
        "change_category": "exam_lab",
        "is_explicit_change": False,
        "corresponding_course_ref": "",
    }]}], complete_009_candidates=False)

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "model_invalid_output"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_course_009_course_rows_are_documentation_not_model_change_candidates() -> None:
    session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-01-01 08:00:00",
        }],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("次日新发胸痛，已评估处理。", "2026-01-02 09:00:00"),
        ],
        evaluation_as_of_date="2026-01-02",
    )
    client = _Client([{"events": []}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_course_009_model_cannot_bind_event_to_course_before_event() -> None:
    session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-01-01 08:00:00",
        }],
        daily_rows=[
            _row("事件前病程。", "2026-01-01 08:00:00"),
            _row("事件后病程。", "2026-01-02 12:00:00"),
        ],
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00",
            "exam_impression": "新发异常改变。",
        }]},
        evaluation_as_of_date="2026-01-02",
    )
    client = _Client([{"events": [{
        "event_ref": "E01",
        "change_category": "exam_lab",
        "is_explicit_change": True,
        "corresponding_course_ref": "C01",
    }]}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "model_invalid_output"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_course_009_external_candidate_category_is_strictly_exam_lab() -> None:
    session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-01-01 08:00:00",
        }],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("次日病危记录。", "2026-01-02 12:00:00"),
        ],
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00",
            "exam_impression": "新发异常改变。",
        }]},
        evaluation_as_of_date="2026-01-02",
    )
    client = _Client([{"events": [{
        "event_ref": "E01",
        "change_category": "objective",
        "is_explicit_change": True,
        "corresponding_course_ref": "C02",
    }]}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "model_invalid_output"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_course_009_negative_candidates_are_ignored_but_duplicate_positive_refs_fail() -> None:
    session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-01-01 08:00:00",
        }],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("次日病危记录。", "2026-01-02 09:00:00"),
        ],
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00",
            "exam_impression": "外部检查候选。",
        }]},
        evaluation_as_of_date="2026-01-02",
    )
    negative_result, negative_reduced = await _run_typed_009(
        session,
        _Client([{
            "events": [{
                "event_ref": "E01",
                "change_category": "exam_lab",
                "is_explicit_change": False,
                "corresponding_course_ref": "",
            }],
        }]),
    )
    duplicate_result, duplicate_reduced = await _run_typed_009(
        session,
        _Client([{
            "events": [
                {
                    "event_ref": "E01",
                    "change_category": "exam_lab",
                    "is_explicit_change": True,
                    "corresponding_course_ref": "C02",
                },
                {
                    "event_ref": "E01",
                    "change_category": "exam_lab",
                    "is_explicit_change": True,
                    "corresponding_course_ref": "C02",
                },
            ],
        }]),
    )

    assert negative_reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert negative_result.llm_call_count == 1
    assert duplicate_reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert duplicate_reduced[0].reason_code == "model_invalid_output"
    assert duplicate_result.llm_call_count == 1


@pytest.mark.asyncio
async def test_course_009_more_than_twenty_change_events_fails_closed_without_truncation() -> None:
    daily_rows = [
        _row(
            f"第{index}日病危记录，出现明确病情变化并已处理。",
            f"2026-01-{index:02d} 09:00:00",
        )
        for index in range(1, 22)
    ]
    session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-01-01 08:00:00",
        }],
        daily_rows=daily_rows,
        external_rows={"exam_item_report": [
            {
                "report_time": f"2026-01-{index:02d} 08:00:00",
                "exam_impression": f"第{index}个外部明确改变。",
            }
            for index in range(1, 22)
        ]},
        evaluation_as_of_date="2026-01-21",
    )
    client = _Client([{
        "events": [
            {
                "event_ref": f"E{index:02d}",
                "change_category": "exam_lab",
                "is_explicit_change": True,
                "corresponding_course_ref": f"C{index:02d}",
            }
            for index in range(1, 22)
        ]
    }])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "candidate_scope_incomplete"
    assert result.customer_display_facts == ()
    assert result.llm_call_count == 1
    assert "超过20个" in client.prompts[0]


@pytest.mark.asyncio
async def test_course_009_daily_complete_model_failure_fails_closed() -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 23:59:59",
                "row_ref": "h" * 64,
            }
        ],
        daily_rows=[
            _row("第一日病情稳定。", "2026-01-01 08:00:00"),
            _row("第二日病情稳定。", "2026-01-02 08:00:00"),
        ],
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00",
            "exam_impression": "外部检查候选。",
        }]},
        evaluation_as_of_date="2026-01-02",
    )
    client = _Client([RuntimeError("MODEL_ERROR_MUST_NOT_LEAK")])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "model_transport_error"
    assert result.llm_call_count == 1
    assert "MODEL_ERROR_MUST_NOT_LEAK" not in repr(result)


@pytest.mark.asyncio
async def test_course_009_daily_complete_invalid_json_fails_closed() -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 23:59:59",
                "row_ref": "i" * 64,
            }
        ],
        daily_rows=[
            _row("第一日病情稳定。", "2026-01-01 08:00:00"),
            _row("第二日病情稳定。", "2026-01-02 08:00:00"),
        ],
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00",
            "exam_impression": "外部检查候选。",
        }]},
        evaluation_as_of_date="2026-01-02",
    )
    result, reduced = await _run_typed_009(session, _Client(["not-json"]))

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "model_invalid_output"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_course_009_semantic_prompt_ignores_unbound_payload_text() -> None:
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
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00",
            "exam_impression": "外部检查候选。",
        }]},
        evaluation_as_of_date="2026-01-03",
    )
    client = _Client([{"events": []}])

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
async def test_course_009_unreferenced_external_event_without_time_keeps_frequency_pass() -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "row_ref": "k" * 64,
            }
        ],
        daily_rows=[
            _row("第一日病情稳定。", "2026-01-01 08:00:00"),
            _row("第二日继续观察。", "2026-01-02 08:00:00"),
        ],
        external_rows={
            "exam_item_report": [{"exam_impression": "外部事件缺权威时间"}]
        },
        evaluation_as_of_date="2026-01-02",
    )
    client = _Client([{"events": []}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_course_009_external_query_error_keeps_frequency_pass() -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "row_ref": "l" * 64,
            }
        ],
        daily_rows=[
            _row("第一日病情稳定。", "2026-01-01 08:00:00"),
            _row("第二日继续观察。", "2026-01-02 08:00:00"),
        ],
        external_failures={"exam_item_report": SourceEvidenceQueryError()},
        evaluation_as_of_date="2026-01-02",
    )
    client = _UnexpectedLLMClient()

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "source_query_error"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("external_failures", "external_truncated", "expected_reason"),
    [
        ({"exam_item_report": SourceEvidenceUnavailable()}, frozenset(), "source_unavailable"),
        ({}, frozenset({"exam_item_report"}), "source_truncated"),
    ],
)
async def test_course_009_external_unavailable_or_truncated_keeps_frequency_pass(
    external_failures: dict[str, Exception],
    external_truncated: frozenset[str],
    expected_reason: str,
) -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "row_ref": "m" * 64,
            }
        ],
        daily_rows=[
            _row("第一日病情稳定。", "2026-01-01 08:00:00"),
            _row("第二日继续观察。", "2026-01-02 08:00:00"),
        ],
        external_failures=external_failures,
        external_truncated=external_truncated,
        evaluation_as_of_date="2026-01-02",
    )
    client = _UnexpectedLLMClient()

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == 0
    assert client.prompts == []


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
async def test_course_009_time_only_phase_does_not_project_text_to_llm() -> None:
    daily_rows = [_row("OUTSIDE_WINDOW_MUST_NOT_LEAK", "2025-12-31 23:59:59")]
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 00:00:00",
                "row_ref": "a" * 64,
            }
        ],
        daily_rows=daily_rows,
        evaluation_as_of_date="2026-01-01",
    )
    client = _UnexpectedLLMClient()
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

    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "OUTSIDE_WINDOW_MUST_NOT_LEAK" not in repr(result)
    assert all(marker not in repr(result) for marker in forbidden.values())


@pytest.mark.asyncio
@pytest.mark.parametrize("shell_content", ["", "[]", "空模板"])
async def test_course_009_timed_shell_only_day_is_a_missing_daily_record(
    shell_content: str,
) -> None:
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 00:00:00",
                "row_ref": "e" * 64,
            }
        ],
        daily_rows=[
            _row("第一日实质病程。", "2026-01-01 08:00:00"),
            _row(shell_content, "2026-01-02 08:00:00"),
            _row("第三日实质病程。", "2026-01-03 08:00:00"),
        ],
        evaluation_as_of_date="2026-01-03",
    )
    client = _Client([{"semantic_state": "satisfied"}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "requirement_violated"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize("overflow_kind", ["ninth_row", "long_row", "total_context"])
async def test_course_009_previous_row_caps_now_use_one_bounded_semantic_call(
    overflow_kind: str,
) -> None:
    daily_rows = [_row("第一日病程。", "2026-01-01 08:00:00")]
    senior_rows: list[dict] = []
    if overflow_kind == "ninth_row":
        daily_rows = [
            _row(f"同日实质病程{index}。", f"2026-01-01 {index:02d}:00:00")
            for index in range(9)
        ]
    elif overflow_kind == "long_row":
        daily_rows = [_row("甲" * 1401, "2026-01-01 08:00:00")]
    else:
        daily_rows = [
            _row(f"日常{index}" + "甲" * 1195, "2026-01-01 08:00:00")
            for index in range(8)
        ]
        senior_rows = [
            _row(f"上级{index}" + "乙" * 1195, "2026-01-01 09:00:00")
            for index in range(8)
        ]
    session = _severity_session(
        rows=[
            {
                "severity": "critical",
                "prescribed_datetime": "2026-01-01 00:00:00",
                "row_ref": "f" * 64,
            }
        ],
        daily_rows=daily_rows,
        senior_rows=senior_rows,
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-01 10:00:00",
            "exam_impression": "外部检查候选。",
        }]},
        evaluation_as_of_date="2026-01-01",
    )
    client = _Client([{"events": []}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_course_009_real_semantic_capacity_limit_is_not_source_truncated() -> None:
    session = _severity_session(
        rows=[{
            "severity": "critical",
            "prescribed_datetime": "2026-01-01 00:00:00",
        }],
        daily_rows=[_row("甲" * 34000, "2026-01-01 08:00:00")],
        evaluation_as_of_date="2026-01-01",
    )
    client = _UnexpectedLLMClient()

    result, reduced = await _run_typed_009(session, client)
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-009"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "candidate_scope_incomplete"
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert canonical["status"] == "data_gap"
    assert canonical["reason_code"] == "candidate_scope_incomplete"
    assert canonical["missing_sources"] == []
    assert canonical["missing_fields"] == []
    assert "现有资料无需补充" in canonical["customer_message"]
    assert "病情变化候选超过单次安全核对范围" in canonical["findings"]


@pytest.mark.asyncio
async def test_course_009_explicit_external_change_within_24h_is_compliant() -> None:
    session = _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 08:00:00"}],
        daily_rows=[
            {
                **_row("首日病危记录。", "2026-01-01 08:00:00"),
                "document_id": "PRIVATE-COURSE-001",
            },
            {
                **_row("患者突发胸痛，已评估并处理。", "2026-01-02 14:00:00"),
                "document_id": "PRIVATE-COURSE-002",
            },
            _row("第三日病危记录。", "2026-01-03 08:00:00"),
            _row("第四日病危记录。", "2026-01-04 08:00:00"),
        ],
        external_rows={"exam_item_report": [{
            "report_id": "PRIVATE-EXAM-001",
            "report_time": "2026-01-02 10:00:00",
            "exam_impression": "新发异常改变",
        }]},
        evaluation_as_of_date="2026-01-04",
    )
    client = _Client([{"events": [{
        "event_ref": "E01", "change_category": "exam_lab",
        "change_time": "2026-01-02 10:00:00", "is_explicit_change": True,
        "corresponding_course_ref": "C02",
    }]}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 1
    assert result.total_tokens == 45
    assert "PRIVATE-" not in client.prompts[0]
    assert "[external_event_ref=E01]" in client.prompts[0]
    assert "[course_event_ref=C02]" in client.prompts[0]
    facts = dict(result.customer_display_facts)["LX0609-009"]
    assert facts["failure_kind"] == "critical_change_course_timely"
    assert facts["change_events"][0]["threshold_hours"] == 24


@pytest.mark.asyncio
async def test_course_009_uses_authoritative_event_time_without_model_echo() -> None:
    session = _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 08:00:00"}],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("患者突发胸痛，已评估并处理。", "2026-01-02 14:00:00"),
            _row("第三日病危记录。", "2026-01-03 08:00:00"),
            _row("第四日病危记录。", "2026-01-04 08:00:00"),
        ],
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00",
            "exam_impression": "新发异常改变",
        }]},
        evaluation_as_of_date="2026-01-04",
    )
    client = _Client([{"events": [{
        "event_ref": "E01",
        "change_category": "exam_lab",
        "is_explicit_change": True,
        "corresponding_course_ref": "C02",
    }]}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    facts = dict(result.customer_display_facts)["LX0609-009"]
    assert facts["change_events"][0]["event_time"] == "2026-01-02 10:00:00"


@pytest.mark.asyncio
async def test_course_009_unreferenced_external_row_without_time_does_not_downgrade() -> None:
    session = _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 08:00:00"}],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("已针对检查变化评估并处理。", "2026-01-02 14:00:00"),
            _row("第三日病危记录。", "2026-01-03 08:00:00"),
            _row("第四日病危记录。", "2026-01-04 08:00:00"),
        ],
        external_rows={"exam_item_report": [
            {"exam_impression": "仅补录检查名称，未见病情变化描述"},
            {
                "report_time": "2026-01-02 10:00:00",
                "exam_impression": "新发异常改变",
            },
        ]},
        evaluation_as_of_date="2026-01-04",
    )
    client = _Client([{"events": [{
        "event_ref": "E01", "change_category": "exam_lab",
        "change_time": "2026-01-02 10:00:00", "is_explicit_change": True,
        "corresponding_course_ref": "C02",
    }]}])

    result, reduced = await _run_typed_009(session, client)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 1
    assert result.total_tokens == 45


@pytest.mark.asyncio
async def test_course_009_explicit_change_without_course_within_24h_is_non_compliant() -> None:
    session = _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 08:00:00"}],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("次日病危记录。", "2026-01-02 09:00:00"),
            _row("第三日病危记录。", "2026-01-03 08:00:00"),
            _row("第四日病危记录。", "2026-01-04 08:00:00"),
        ],
        external_rows={"exam_item_report": [{"report_time": "2026-01-02 10:00:00", "exam_impression": "新发异常改变"}]},
        evaluation_as_of_date="2026-01-04",
    )
    client = _Client([{"events": [{
        "event_ref": "E01", "change_category": "exam_lab",
        "change_time": "2026-01-02 10:00:00", "is_explicit_change": True,
        "corresponding_course_ref": "",
    }]}])
    result, reduced = await _run_typed_009(session, client)
    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "requirement_violated"
    assert result.llm_call_count == 1
    assert dict(result.customer_display_facts)["LX0609-009"]["unmet_events"][0]["event_ref"] == "E01"


@pytest.mark.asyncio
async def test_course_009_change_deadline_is_delivered_through_production_canonical_result() -> None:
    """009 的变化类别、时间、阈值和受控引用必须穿透真实客户交付出口。"""
    session = _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 08:00:00"}],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("次日病危记录。", "2026-01-02 09:00:00"),
            _row("第三日病危记录。", "2026-01-03 08:00:00"),
            _row("第四日病危记录。", "2026-01-04 08:00:00"),
        ],
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00", "exam_impression": "新发异常改变",
        }]},
        evaluation_as_of_date="2026-01-04",
    )
    client = _Client([{"events": [{
        "event_ref": "E01", "change_category": "exam_lab",
        "change_time": "2026-01-02 10:00:00", "is_explicit_change": True,
        "corresponding_course_ref": "",
    }]}])

    result, reduced = await _run_typed_009(session, client)
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-009"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]

    assert canonical["status"] == "non_compliant"
    assert canonical["reason_code"] == "requirement_violated"
    facts = canonical["customer_display_facts"]
    assert facts["failure_kind"] == "critical_change_course_not_timely"
    assert facts["threshold_hours"] == 24
    assert facts["unmet_events"] == [{
        "event_ref": "E01",
        "change_category": "exam_lab",
        "event_time": "2026-01-02 10:00:00",
        "corresponding_course_ref": "",
        "corresponding_course_time": "",
        "deadline_time": "2026-01-03 10:00:00",
        "threshold_hours": 24,
        "timely": False,
    }]
    assert "检查检验变化" in canonical["findings"]
    assert "2026-01-03 10:00:00" in canonical["findings"]
    assert result.llm_call_count == 1
    assert result.total_tokens == 45


@pytest.mark.asyncio
async def test_course_009_missing_change_time_and_unresolved_course_are_delivered_as_data_gaps() -> None:
    def canonical_for() -> dict:
        return aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": "LX0609-009"}],
            execution_results=[],
            reduced_decisions=reduced,
            customer_display_facts=result.customer_display_facts,
            audit_context={
                "evidence_snapshot": session.snapshot,
                "evidence_materials": session.materials,
            },
        )[0]

    session = _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 08:00:00"}],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("次日病危记录。", "2026-01-02 09:00:00"),
            _row("第三日病危记录。", "2026-01-03 08:00:00"),
        ],
        external_rows={"labtest_item_report": [{"result": "指标明显升高"}]},
        evaluation_as_of_date="2026-01-03",
    )
    result, reduced = await _run_typed_009(session, _Client([{"events": [{
        "event_ref": "E01", "change_category": "exam_lab",
        "change_time": "", "is_explicit_change": True,
        "corresponding_course_ref": "",
    }]}]))
    canonical = canonical_for()
    assert canonical["status"] == "data_gap"
    assert canonical["reason_code"] == "authoritative_time_missing"
    assert canonical["customer_display_facts"] == {
        "failure_kind": "critical_change_time_unavailable", "threshold_hours": 24,
    }
    assert "缺少可核验的变化发生时间" in canonical["findings"]

    session = _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 08:00:00"}],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("次日病危记录。", "2026-01-02 09:00:00"),
            _row("第三日病危记录。", "2026-01-03 08:00:00"),
            _row("第四日病危记录。", "2026-01-04 08:00:00"),
        ],
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00", "exam_impression": "新发异常改变",
        }]},
        evaluation_as_of_date="2026-01-04",
    )
    result, reduced = await _run_typed_009(session, _Client([{"events": [{
        "event_ref": "E01", "change_category": "exam_lab",
        "change_time": "2026-01-02 10:00:00", "is_explicit_change": True,
        "corresponding_course_ref": "C99",
    }]}]))
    canonical = canonical_for()
    assert canonical["status"] == "technical_error"
    assert canonical["reason_code"] == "model_invalid_output"
    assert canonical["customer_display_facts"]["failure_kind"] == (
        "critical_daily_record_coverage_satisfied"
    )
    assert "C99" not in repr(canonical)


@pytest.mark.asyncio
async def test_course_009_precise_horizon_before_change_24h_deadline_is_not_mature() -> None:
    session = _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 08:00:00"}],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("次日病危记录。", "2026-01-02 09:00:00"),
        ],
        admission_rows=[{
            "admission_datetime": "2026-01-01 07:00:00",
        }],
        discharge_rows=[{"discharge_datetime": "2026-01-02 12:00:00"}],
        external_rows={"exam_item_report": [{
            "report_time": "2026-01-02 10:00:00", "exam_impression": "新发异常改变",
        }]},
        evaluation_as_of_date=None,
        evaluation_horizon_policy="authoritative_discharge",
    )
    result, reduced = await _run_typed_009(session, _Client([{"events": [{
        "event_ref": "E01", "change_category": "exam_lab",
        "change_time": "2026-01-02 10:00:00", "is_explicit_change": True,
        "corresponding_course_ref": "",
    }]}]))
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-009"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]

    assert canonical["status"] == "data_gap"
    assert canonical["reason_code"] == "evaluation_window_not_mature"
    assert canonical["customer_display_facts"] == {
        "failure_kind": "critical_change_window_not_mature",
        "event_ref": "E01",
        "event_time": "2026-01-02 10:00:00",
        "deadline_time": "2026-01-03 10:00:00",
        "threshold_hours": 24,
    }
    assert "尚未满 24 小时" in canonical["findings"]
    assert result.llm_call_count == 1
    assert result.total_tokens == 45


@pytest.mark.asyncio
async def test_course_009_ignores_model_echoed_time_and_uses_event_reference() -> None:
    session = _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 08:00:00"}],
        daily_rows=[
            _row("首日病危记录。", "2026-01-01 08:00:00"),
            _row("次日病危记录。", "2026-01-02 09:00:00"),
            _row("第三日病危记录。", "2026-01-03 09:00:00"),
            _row("第四日病危记录。", "2026-01-04 09:00:00"),
        ],
        external_rows={"exam_item_report": [{"report_time": "2026-01-02 10:00:00", "exam_impression": "新发异常改变"}]},
        evaluation_as_of_date="2026-01-04",
    )
    client = _Client([{"events": [{
        "event_ref": "E01", "change_category": "exam_lab",
        "change_time": "2026-01-02 10:01:00", "is_explicit_change": True,
        "corresponding_course_ref": "",
    }]}])
    result, reduced = await _run_typed_009(session, client)
    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "requirement_violated"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_course_009_model_unknown_does_not_overturn_daily_coverage() -> None:
    session = _severity_session(
        rows=[{"severity": "critical", "prescribed_datetime": "2026-01-01 08:00:00"}],
        daily_rows=[_row("首日病危记录。", "2026-01-01 08:00:00"), _row("次日病危记录。", "2026-01-02 09:00:00")],
        external_rows={"exam_item_report": [{"report_time": "2026-01-02 10:00:00", "exam_impression": "新发异常改变"}]},
        evaluation_as_of_date="2026-01-02",
    )
    result, reduced = await _run_typed_009(session, _Client([{"events": []}]))
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert result.llm_call_count == 1


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
async def test_007_accepts_authoritative_record_datetime_fallback_without_model(
    monkeypatch,
):
    def fake_reader(**kwargs):
        if kwargs["source_key"] == "daily_course_record":
            return [{"record_time": None, "record_datetime": "2026-06-01 09:00:00"}]
        if kwargs["source_key"] == "senior_course_record":
            return [{"record_time": None, "submit_time": "2026-06-04 09:00:00"}]
        raise AssertionError(kwargs["source_key"])

    monkeypatch.setattr(course, "read_luxian_0609_native_source_rows", fake_reader)
    monkeypatch.setattr(
        course, "has_luxian_0609_current_visit_unstable_order", lambda **_: False
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
async def test_008_legacy_timeline_keeps_first_course_and_rescue_sources() -> None:
    client = _Client([{"is_compliant": True}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008",),
        wrapper_rules=[_wrapper("LX0609-008")],
        evidence_payload=_payload(
            documents={
                "first_course_record": [
                    _row("首次病程记录病重情况。", "2026-06-01 09:00:00")
                ],
                "rescue_record": [
                    _row("抢救记录复核病情变化。", "2026-06-02 09:00:00")
                ],
            },
            facts=[_strong_fact("current_visit_serious_order")],
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant"]
    assert result.llm_call_count == 1
    assert "首次病程记录病重情况" in client.prompts[0]
    assert "抢救记录复核病情变化" in client.prompts[0]


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
async def test_016_requires_two_comparable_documents_before_model():
    missing = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(documents={"admission_record": [_row("入院记录现病史。")]}),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in missing.results] == ["not_applicable"]
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
    assert [item["status"] for item in complete.results] == ["data_gap"]
    assert complete.llm_call_count == 0


@pytest.mark.asyncio
async def test_2496813_016_contained_history_is_not_treated_as_complete_copy():
    history = (
        "患者于1小时前骑电动车不慎侧滑，摔倒致头面部外伤、持续出血、"
        "呼唤无反应，伴肢体不自主抖动、小便失禁。"
    )
    rows_by_source = {
        "admission_record": [
            {
                "record_content": "",
                "history_of_present_illness": history,
            }
        ],
        "first_course_record": [
            {
                "record_content": "",
                "case_characteristic": (
                    "1.患者为54岁女性，起病急，病程短；"
                    f"2.{history}"
                    "3.既往史一般；4.体格检查完整。"
                ),
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
        selected_rule_ids=("LX0609-016",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-28T12:00:00+08:00",
        row_reader=read,
    )
    client = _Client([])
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        decision_rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-016",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rows_by_source", "expected_state"),
    [
        (
            {
                "admission_record": [],
                "first_course_record": [],
            },
            CustomerFinalState.NOT_APPLICABLE,
        ),
        (
            {
                "admission_record": [
                    {"record_content": "入院记录现病史具备可比正文。"}
                ],
                "first_course_record": [],
            },
            CustomerFinalState.NOT_APPLICABLE,
        ),
        (
            {
                "admission_record": [],
                "first_course_record": [
                    {"record_content": "首次病程病例特点具备可比正文。"}
                ],
            },
            CustomerFinalState.NOT_APPLICABLE,
        ),
        (
            {
                "admission_record": [
                    {"record_content": "", "history_of_present_illness": ""}
                ],
                "first_course_record": [
                    {"record_content": "首次病程病例特点具备可比正文。"}
                ],
            },
            CustomerFinalState.DATA_GAP,
        ),
        (
            {
                "admission_record": [
                    {
                        "record_content": "",
                        "history_of_present_illness": (
                            "患者反复咳嗽咳痰伴活动后气促三月，加重两天，"
                            "入院后予氧疗及抗感染等对症支持治疗。"
                        ),
                    }
                ],
                "first_course_record": [
                    {
                        "record_content": "",
                        "case_characteristic": (
                            "患者反复咳嗽咳痰伴活动后气促三月，加重两天，"
                            "入院后予氧疗及抗感染等对症支持治疗。"
                        ),
                    }
                ],
            },
            CustomerFinalState.NON_COMPLIANT,
        ),
    ],
)
async def test_typed_016_distinguishes_absent_unavailable_and_structured_comparable_bodies(
    rows_by_source: dict[str, list[dict[str, str]]],
    expected_state: CustomerFinalState,
):
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
        created_at="2026-07-28T12:00:00+08:00",
        row_reader=read,
    )
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        decision_rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-016",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is expected_state
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_016_018_use_same_material_session_without_legacy_payload():
    private_marker = "PRIVATE_ADMISSION_MATERIAL_MARKER"
    rows_by_source = {
        "admission_record": [
            {
                **_row(
                    f"{private_marker} 主诉：反复胸痛伴胸闷气短三个月，"
                    "活动后加重，休息后可缓解。入院诊断：不稳定型心绞痛。"
                    "现病史与病例特点完整。"
                ),
                "chief_complaint": (
                    "反复胸痛3个月，加重2天"
                ),
            }
        ],
        "first_course_record": [
            _row("首次病程记录包含病例特点、诊断依据、鉴别诊断和诊疗计划。")
        ],
        "diagnosis": [
            {
                "diagnosis_type": "入院诊断",
                "diagnosis_no": "1",
                "diagnosis_name": "不稳定型心绞痛",
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
        selected_rule_ids=("LX0609-016", "LX0609-018"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
    )
    client = _Client(
        [{
            "diagnostic_relation_state": "supported",
            "diagnostic_reason_dimensions": ["anatomic_site", "symptom_pattern"],
            "diagnostic_rationale_code": "supported",
            "medical_analysis": "主诉与第一诊断方向一致。",
        }]
    )
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
        "data_gap",
        "compliant",
    ]
    assert all(item.fact_refs for item in reduced)
    assert result.llm_call_count == 1
    assert result.total_tokens == 45
    assert len(client.prompts) == 1
    assert "不稳定型心绞痛" in client.prompts[0]
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
    client = _Client(
        [
            {
                "diagnostic_relation_state": "supported",
                "diagnostic_reason_dimensions": [
                    "anatomic_site",
                    "symptom_pattern",
                ],
                "diagnostic_rationale_code": "supported",
                "medical_analysis": "胸痛症状支持心绞痛诊断方向。",
            }
        ]
    )
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
@pytest.mark.parametrize(
    ("complaint", "expected_state", "expected_criterion_state"),
    (
        ("胸痛" * 10, CustomerFinalState.COMPLIANT, "passed"),
        ("胸痛" * 10 + "加", CustomerFinalState.NON_COMPLIANT, "failed"),
    ),
)
async def test_typed_018_combines_length_and_diagnostic_direction(
    complaint: str,
    expected_state: CustomerFinalState,
    expected_criterion_state: str,
) -> None:
    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            [{**_row("入院记录正文完整。"), "chief_complaint": complaint}]
            if source_key == "admission_record"
            else [
                {
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                    "diagnosis_name": "稳定型心绞痛",
                }
            ]
            if source_key == "diagnosis"
            else []
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
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
    client = _Client(
        [
            {
                "diagnostic_relation_state": "supported",
                "diagnostic_reason_dimensions": ["symptom_pattern"],
                "diagnostic_rationale_code": "supported",
            }
        ]
    )

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

    assert reduced[0].final_state is expected_state
    assert [item.criterion_id for item in reduced[0].criterion_results] == [
        "chief_complaint_length",
        "diagnostic_direction",
    ]
    assert reduced[0].criterion_results[0].status.value == expected_criterion_state
    assert reduced[0].criterion_results[1].status.value == "passed"
    assert result.llm_call_count == 1
    assert result.total_tokens == 45
    assert len(client.prompts) == 1
    assert "稳定型心绞痛" in client.prompts[0]


@pytest.mark.asyncio
async def test_typed_018_matches_raw_state_calls_and_tokens():
    admission_row = _row(
        "主诉：反复胸痛3个月。入院诊断：不稳定型心绞痛。现病史完整。"
    )
    diagnosis_row = {
        "diagnosis_type": "入院诊断",
        "diagnosis_no": "1",
        "diagnosis_name": "不稳定型心绞痛",
    }

    def read(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=(
                [admission_row]
                if source_key == "admission_record"
                else [diagnosis_row]
                if source_key == "diagnosis"
                else []
            ),
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
        evidence_payload=_payload(
            documents={
                "admission_record": [admission_row],
                "diagnosis": [diagnosis_row],
            }
        ),
        llm_client=_Client(
            [
                {
                    "is_compliant": False,
                    "diagnostic_relation_state": "supported",
                    "diagnostic_rationale_code": "supported",
                }
            ]
        ),
    )
    typed = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        decision_rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload={"stale": "payload"},
        llm_client=_Client(
            [
                {
                    "is_compliant": False,
                    "diagnostic_relation_state": "supported",
                    "diagnostic_rationale_code": "supported",
                }
            ]
        ),
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
async def test_typed_018_uses_only_authoritative_primary_diagnosis():
    rows_by_source = {
        "admission_record": [
            _row("主诉：反复腹痛2个月。现病史与既往诊疗经过记录完整。")
        ],
        "diagnosis": [
            *[
                {"diagnosis_type": "其他诊断", "diagnosis_name": f"不应采信的诊断{index}"}
                for index in range(8)
            ],
            {
                "diagnosis_type": "入院诊断",
                "diagnosis_no": "1",
                "diagnosis_name": "结肠恶性肿瘤",
            },
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
    client = _Client(
        [
            {
                "is_compliant": False,
                "diagnostic_relation_state": "mismatch",
                "diagnostic_rationale_code": "diagnosis_mismatch",
            }
        ]
    )
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
    assert len(client.prompts) == 1
    assert "结肠恶性肿瘤" in client.prompts[0]
    assert "不应采信的诊断" not in client.prompts[0]
    assert "结肠恶性肿瘤" not in repr(typed)


@pytest.mark.asyncio
async def test_typed_018_reads_only_first_numbered_diagnosis():
    rows_by_source = {
        "admission_record": [
            _row("主诉：反复腰腹部疼痛伴尿频1月。现病史与诊疗经过记录完整。")
        ],
        "diagnosis": [
            {
                "diagnosis_type": "初步诊断",
                "diagnosis_no": "1",
                "diagnosis_name": "1、双侧肾周围炎,2、前列腺增生,3、2型糖尿病",
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
        selected_rule_ids=("LX0609-018",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
    )
    client = _Client([{
        "diagnostic_relation_state": "supported",
        "diagnostic_reason_dimensions": ["anatomic_site"],
        "diagnostic_rationale_code": "supported",
    }])
    typed = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        decision_rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert typed.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "双侧肾周围炎" in client.prompts[0]
    assert "前列腺增生" not in client.prompts[0]
    assert typed.results == ()


@pytest.mark.asyncio
async def test_typed_018_reads_admission_first_diagnosis():
    rows_by_source = {
        "admission_record": [
            _row("主诉：反复咳嗽咳痰气促10余年，加重伴纳差1天。现病史完整。")
        ],
        "diagnosis": [],
        "admission_record_diagnosis": [
            {
                "diagnosis_type": "初步诊断",
                "diagnosis_no": "1",
                "diagnosis_name": (
                    "1、慢性阻塞性肺病伴有急性下呼吸道感染；"
                    "2、慢性呼吸衰竭；3、尘肺？"
                ),
            },
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
    client = _Client([{
        "diagnostic_relation_state": "supported",
        "diagnostic_reason_dimensions": ["symptom_pattern"],
        "diagnostic_rationale_code": "supported",
    }])
    typed = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        decision_rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert typed.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "慢性阻塞性肺病伴有急性下呼吸道感染" in client.prompts[0]
    assert "慢性呼吸衰竭" not in client.prompts[0]
    assert typed.results == ()


@pytest.mark.asyncio
async def test_typed_018_accepts_structured_complaint_when_record_content_is_empty():
    rows_by_source = {
        "admission_record": [
            {
                "chief_complaint": "无明显诱因出现左膝疼痛3月。",
                "record_content": "",
            }
        ],
        "diagnosis": [],
        "admission_record_diagnosis": [
            {
                "diagnosis_type": "初步诊断",
                "diagnosis_no": "1",
                "diagnosis_name": "左侧膝关节骨性关节病",
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
        selected_rule_ids=("LX0609-018",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
    )
    client = _Client([{
        "diagnostic_relation_state": "supported",
        "diagnostic_reason_dimensions": ["laterality", "anatomic_site"],
        "diagnostic_rationale_code": "supported",
    }])
    typed = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        decision_rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert typed.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "左侧膝关节骨性关节病" in client.prompts[0]
    assert typed.results == ()


@pytest.mark.asyncio
async def test_typed_016_missing_structured_sections_is_data_gap_without_model():
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
        llm_client=_Client([RuntimeError("must not call model")]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=typed.decisions,
        expected_rule_ids=("LX0609-016",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "required_field_missing"
    assert typed.llm_call_count == 0
    assert typed.total_tokens == 0


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
async def test_017_similarity_threshold_routes_ambiguous_pair_to_review():
    one_record = course._copy_result(
        {"daily_course_record": [_row("患者病情稳定，继续观察治疗。")]},
        source_complete=True,
    )
    assert one_record["status"] == "not_applicable"
    assert one_record["metadata"]["reason_code"] == (
        "insufficient_independent_course_records"
    )
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
    assert similar["metadata"]["reason_code"] == "copy_similarity_threshold_exceeded"
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
    assert different["metadata"]["reason_code"] == "copy_similarity_within_threshold"
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
    assert exact_threshold["status"] == "uncertain"
    assert exact_threshold["metadata"]["reason_code"] == "semantic_low_confidence"


@pytest.mark.parametrize(
    "fallback_field",
    ["record_datetime", "submit_time", "submit_datetime"],
)
def test_017_accepts_controlled_authoritative_time_fallback(fallback_field):
    copied = "患者神志清楚，咳嗽咳痰，双肺呼吸音粗，继续抗感染平喘化痰治疗，观察病情变化。"
    result = course._copy_result(
        {
            "daily_course_record": [
                {
                    "record_content": copied,
                    "record_time": None,
                    fallback_field: "2026-06-01 09:00:00",
                },
                {
                    "record_content": copied,
                    "record_time": None,
                    fallback_field: "2026-06-02 09:00:00",
                },
            ]
        },
        source_complete=True,
    )

    assert result["status"] == "non_compliant"
    assert result["metadata"]["reason_code"] == "copy_similarity_threshold_exceeded"


def test_017_same_day_records_are_compared_without_date_gate():
    result = course._copy_result(
        {
            "daily_course_record": [
                _row("患者病情稳定，继续观察治疗并记录当日查体及生命体征变化情况。"),
                _row("患者病情稳定，继续观察治疗并补充记录当日饮食睡眠及出入量情况。", "2026-06-01 16:00:00"),
            ]
        },
        source_complete=True,
    )

    assert result["status"] == "uncertain"
    assert result["metadata"]["reason_code"] == "semantic_low_confidence"


def test_017_template_shell_only_pair_is_compliant_without_llm():
    """人工确认的纯模板壳不能形成复制问题。"""
    template_shell = (
        "患者病情稳定，生命体征平稳，查体无明显异常，"
        "继续当前治疗，观察病情。"
    )

    result = course._copy_result(
        {
            "daily_course_record": [
                _row(template_shell),
                _row(template_shell, "2026-06-02 09:00:00"),
            ]
        },
        source_complete=True,
    )

    assert result["status"] == "compliant"
    assert result["metadata"]["reason_code"] == "copy_similarity_within_threshold"
    assert result["metadata"]["maximum_similarity"] == 1.0
    assert result["metadata"]["template_shell_only"] is True


def test_017_template_pair_does_not_hide_another_ambiguous_substantive_pair():
    template_shell = (
        "患者病情稳定，生命体征平稳，查体无明显异常，"
        "继续当前治疗，观察病情。"
    )
    common = "患者神志清楚生命体征平稳继续观察症状体征以及复查指标变化" * 4

    result = course._copy_result(
        {
            "daily_course_record": [
                _row(template_shell, "2026-06-01 09:00:00"),
                _row(template_shell, "2026-06-02 09:00:00"),
                _row(f"{common}腹痛缓解停止补液。", "2026-06-03 09:00:00"),
                _row(f"{common}高热感染进展恢复静脉治疗。", "2026-06-04 09:00:00"),
            ]
        },
        source_complete=True,
    )

    assert result["status"] == "uncertain"
    assert result["metadata"]["reason_code"] == "semantic_low_confidence"


def test_017_specific_content_repeat_remains_non_compliant_above_threshold():
    """任何特异症状、检查、诊断、用药或处置残留都不能走模板豁免。"""
    specific_repeat = (
        "患者病情稳定，生命体征平稳，查体无明显异常，"
        "CT提示右下肺炎，诊断社区获得性肺炎，继续头孢曲松静滴治疗。"
    )

    result = course._copy_result(
        {
            "daily_course_record": [
                _row(specific_repeat),
                _row(specific_repeat, "2026-06-02 09:00:00"),
            ]
        },
        source_complete=True,
    )

    assert result["status"] == "non_compliant"
    assert result["metadata"]["reason_code"] == "copy_similarity_threshold_exceeded"
    assert result["metadata"]["template_shell_only"] is False


def test_017_similarity_above_point_70_requires_semantic_review():
    result = course._copy_result(
        {
            "daily_course_record": [
                _row("a" * 71 + "b" * 29),
                _row("a" * 71 + "c" * 29, "2026-06-02 09:00:00"),
            ]
        },
        source_complete=True,
    )

    assert result["metadata"]["maximum_similarity"] == 0.71
    assert result["status"] == "uncertain"
    assert result["metadata"]["reason_code"] == "semantic_low_confidence"


@pytest.mark.asyncio
async def test_017_long_template_with_material_change_uses_one_review(monkeypatch):
    """模板与实质变化难区分时只做一次候选复核。"""
    template = "患者病情稳定生命体征平稳继续观察病情" * 12
    left = (
        f"{template}腹痛缓解，改口服药，准备出院。"
        "safe-left PRIVATE-INSTITUTE PRIVATE-PATIENT PRIVATE-VISIT"
    )
    right = (
        f"{template}突发高热，影像感染进展，恢复静脉抗感染。"
        "safe-right PRIVATE-INSTITUTE PRIVATE-PATIENT PRIVATE-VISIT"
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(left), "document_id": "safe-left"},
            {**_row(right, "2026-06-02 09:00:00"), "document_id": "safe-right"},
        ] if kwargs["source_key"] == "senior_course_record" else [],
    )
    client = _CopyReviewClient("substantial_copy")
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",), wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}), institute_id="PRIVATE-INSTITUTE",
        patient_id="PRIVATE-PATIENT", visit_id="PRIVATE-VISIT",
        source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.results[0]["metadata"]["reason_code"] == "copy_similarity_threshold_exceeded"
    assert result.llm_call_count == 1
    assert len(client.calls) == 1
    assert client.calls[0]["max_completion_tokens"] == 512
    assert client.calls[0]["allow_length_retry"] is False
    assert "safe-left" not in client.calls[0]["prompt"]
    assert "safe-right" not in client.calls[0]["prompt"]
    assert "PRIVATE-" not in client.calls[0]["prompt"]
    assert '"pair_ref":"P01"' in client.calls[0]["prompt"]
    assert '"left_ref":"D01"' in client.calls[0]["prompt"]
    assert (
        '"schema_version":"lx0609_017_v1","pair_results":['
        '{"pair_ref":"P01","verdict":"uncertain",'
        '"document_refs":["D01","D02"]}]'
    ) in client.calls[0]["prompt"]
    assert "禁止使用pair_ref作为JSON对象的键" in client.calls[0]["prompt"]
    assert left not in repr(result)
    assert right not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "case_id"),
    [
        (RuntimeError("transport"), "transport"),
        (_copy_review_response([]), "missing_pair"),
        (_copy_review_response([{"pair_ref": "P99", "verdict": "template_only", "document_refs": ["D01", "D02"]}]), "unknown_pair"),
        (_copy_review_response([{"pair_ref": "P01", "verdict": "template_only", "document_refs": ["D01", "D99"]}]), "unknown_document"),
        (_copy_review_response([
            {"pair_ref": "P01", "verdict": "template_only", "document_refs": ["D01", "D02"]},
            {"pair_ref": "P01", "verdict": "template_only", "document_refs": ["D01", "D02"]},
        ]), "duplicate_pair"),
        (_copy_review_response([
            {"pair_ref": "P01", "verdict": "template_only", "document_refs": ["D01", "D02"]}
        ], usage=False), "missing_usage"),
        (_copy_review_response([
            {"pair_ref": "P01", "verdict": "template_only", "document_refs": ["D01", "D02"]}
        ], usage={"prompt_tokens": True, "completion_tokens": 8, "total_tokens": 9}), "bool_usage"),
        (_copy_review_response([
            {"pair_ref": "P01", "verdict": "template_only", "document_refs": ["D01", "D02"]}
        ], usage={"prompt_tokens": "40", "completion_tokens": 8, "total_tokens": 48}), "string_usage"),
        (_copy_review_response([
            {"pair_ref": "P01", "verdict": "template_only", "document_refs": ["D01", "D02"]}
        ], usage={"prompt_tokens": -1, "completion_tokens": 8, "total_tokens": 7}), "negative_usage"),
        (_copy_review_response([
            {"pair_ref": "P01", "verdict": "template_only", "document_refs": ["D01", "D02"]}
        ], usage={"prompt_tokens": 4097, "completion_tokens": 8, "total_tokens": 4105}), "prompt_limit"),
        (_copy_review_response([
            {"pair_ref": "P01", "verdict": "template_only", "document_refs": ["D01", "D02"]}
        ], usage={"prompt_tokens": 40, "completion_tokens": 8, "total_tokens": 49}), "total_mismatch"),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
async def test_017_semantic_review_invalid_response_fails_closed(
    monkeypatch, response: object, case_id: str
):
    template = "患者病情稳定生命体征平稳继续观察病情" * 10
    left = f"{template}今日腹痛缓解停止补液改为口服治疗。"
    right = f"{template}今日高热影像进展恢复静脉抗感染。"
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(left), "document_id": "PRIVATE-LEFT"},
            {**_row(right, "2026-06-02 09:00:00"), "document_id": "PRIVATE-RIGHT"},
        ] if kwargs["source_key"] == "daily_course_record" else [],
    )
    client = _CopyReviewClient(response=response)

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",), wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}), institute_id="PRIVATE-I",
        patient_id="PRIVATE-P", visit_id="PRIVATE-V", source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["technical_error"], case_id
    assert result.llm_call_count == 1
    assert len(client.calls) == 1
    assert client.calls[0]["max_completion_tokens"] == 512
    assert client.calls[0]["allow_length_retry"] is False
    assert "PRIVATE-" not in client.calls[0]["prompt"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("verdict", "expected_status", "expected_reason"),
    [
        ("template_only", "compliant", "copy_similarity_within_threshold"),
        ("uncertain", "uncertain", "semantic_low_confidence"),
    ],
)
async def test_017_semantic_review_verdict_is_mapped_by_python_once(
    monkeypatch, verdict: str, expected_status: str, expected_reason: str
):
    template = "患者病情稳定生命体征平稳继续观察病情" * 10
    rows = [
        {**_row(f"{template}今日腹痛缓解。", "2026-06-01 09:00:00"), "document_id": "PRIVATE-A"},
        {**_row(f"{template}今日高热感染进展。", "2026-06-02 09:00:00"), "document_id": "PRIVATE-B"},
        {**_row(f"{template}今日胸闷调整治疗。", "2026-06-03 09:00:00"), "document_id": "PRIVATE-C"},
    ]
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: rows if kwargs["source_key"] == "daily_course_record" else [],
    )
    client = _CopyReviewClient(verdict)

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",), wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}), institute_id="I", patient_id="P",
        visit_id="V", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == [expected_status]
    assert result.results[0]["metadata"]["reason_code"] == expected_reason
    assert result.llm_call_count == 1
    assert len(client.calls) == 1
    assert '"pair_ref":"P02"' in client.calls[0]["prompt"]
    assert "PRIVATE-" not in client.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_017_confirmed_substantial_copy_takes_priority_over_uncertain_pair(
    monkeypatch,
) -> None:
    template = "患者病情稳定生命体征平稳继续观察病情" * 10
    rows = [
        {**_row(f"{template}今日腹痛减轻。", "2026-06-01 09:00:00"), "document_id": "PRIVATE-A"},
        {**_row(f"{template}今日高热感染进展。", "2026-06-02 09:00:00"), "document_id": "PRIVATE-B"},
        {**_row(f"{template}今日胸闷调整治疗。", "2026-06-03 09:00:00"), "document_id": "PRIVATE-C"},
    ]
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: rows if kwargs["source_key"] == "daily_course_record" else [],
    )
    class _MixedReviewClient(_CopyReviewClient):
        async def generate(self, prompt: str, **kwargs: Any) -> dict:
            self.calls.append({"prompt": prompt, **kwargs})
            pairs = re.findall(
                r'"pair_ref":"(P\d+)","left_ref":"(D\d+)","right_ref":"(D\d+)"',
                prompt,
            )
            assert len(pairs) >= 2
            return _copy_review_response([
                {
                    "pair_ref": pair_ref,
                    "verdict": "substantial_copy" if index == 0 else "uncertain",
                    "document_refs": [left_ref, right_ref],
                }
                for index, (pair_ref, left_ref, right_ref) in enumerate(pairs)
            ])

    client = _MixedReviewClient()

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "copy_similarity_threshold_exceeded"
    )
    assert len(result.results[0]["metadata"]["best_match_pairs"]) == 1
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_017_high_similarity_uses_one_semantic_review(
    monkeypatch,
):
    template = "患者病情稳定生命体征平稳继续观察病情" * 10
    left = f"{template}今日腹痛减轻，停止补液改口服。"
    right = f"{template}今日发热咳嗽，恢复静脉抗感染。"
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(left), "document_id": "safe-left"},
            {**_row(right, "2026-06-02 09:00:00"), "document_id": "safe-right"},
        ] if kwargs["source_key"] == "daily_course_record" else [],
    )
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",), wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}), institute_id="I", patient_id="P",
        visit_id="V", source_schema=None, llm_client=_CopyReviewClient(),
    )
    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.results[0]["metadata"]["reason_code"] == "copy_similarity_threshold_exceeded"
    assert result.llm_call_count == 1
    assert left not in repr(result)
    assert right not in repr(result)


def test_017_copy_input_deduplicates_cross_source_document_id_and_excludes_long_term_order():
    copied = "患者病情平稳，查体无明显变化，继续当前治疗方案并观察。"
    long_term_order = {
        **_row(copied, "2026-06-02 09:00:00"),
        "document_id": "long-term-order",
        "document_title": "长期医嘱",
    }
    assessment = course._copy_result(
        {
            "daily_course_record": [
                {**_row(copied), "document_id": "synced-document"},
                long_term_order,
            ],
            "senior_course_record": [
                {
                    **_row(copied, "2026-06-03 09:00:00"),
                    "document_id": "synced-document",
                }
            ],
        },
        source_complete=True,
    )

    assert assessment["status"] == "not_applicable"
    assert assessment["metadata"]["reason_code"] == (
        "insufficient_independent_course_records"
    )
    assert assessment["metadata"]["comparable_document_count"] == 1


def test_017_same_content_without_document_id_remains_independent_copy_pair():
    copied = (
        "患者右下肺炎伴持续发热咳嗽，胸部CT提示感染灶扩大，"
        "继续头孢曲松静滴并增加雾化治疗，复查炎症指标。"
    )

    result = course._copy_result(
        {
            "daily_course_record": [
                _row(copied),
                _row(copied, "2026-06-02 09:00:00"),
            ],
            "senior_course_record": [],
        },
        source_complete=True,
    )

    assert result["status"] == "non_compliant"
    assert result["metadata"]["comparable_document_count"] == 2
    assert result["metadata"]["maximum_similarity"] == 1.0


@pytest.mark.asyncio
async def test_017_low_similarity_is_compliant_without_llm_call(monkeypatch):
    left = "患者腹痛明显缓解，复查炎症指标下降，停止静脉补液改为口服治疗。"
    right = "患者突发胸闷，心电图提示心肌缺血，请心内科会诊并启动抗栓治疗。"
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(left), "document_id": "safe-left"},
            {**_row(right, "2026-06-02 09:00:00"), "document_id": "safe-right"},
        ]
        if kwargs["source_key"] == "daily_course_record"
        else [],
    )
    client = _UnexpectedLLMClient()

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
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert left not in repr(result)
    assert right not in repr(result)


@pytest.mark.asyncio
async def test_017_high_similarity_with_material_change_is_reviewed_once(monkeypatch):
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
    client = _CopyReviewClient()

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
    assert result.results[0]["metadata"]["reason_code"] == "copy_similarity_threshold_exceeded"
    assert result.results[0]["metadata"]["executor_type"] == "llm"
    assert result.llm_call_count == 1
    assert result.total_tokens == 48
    assert len(client.calls) == 1
    assert left not in repr(result)
    assert right not in repr(result)


@pytest.mark.asyncio
async def test_017_long_template_block_with_material_change_is_reviewed_once(
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
    client = _CopyReviewClient()

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
    assert 0.70 < result.results[0]["metadata"]["maximum_similarity"] < 0.95
    assert result.results[0]["metadata"]["reason_code"] == "copy_similarity_threshold_exceeded"
    assert result.llm_call_count == 1
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_017_high_similarity_nonidentical_current_update_is_reviewed_once(
    monkeypatch,
):
    template = (
        "患者神志清楚，生命体征平稳，双肺呼吸音清，心律齐，腹部柔软，"
        "双下肢无水肿，继续观察病情变化并复查相关指标。"
    ) * 8
    left = f"{template}今日腹痛缓解，继续原治疗。"
    right = f"{template}今日腹痛明显缓解，停止静脉补液，调整为口服治疗并准备出院。"
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
    client = _CopyReviewClient()

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

    assert result.results[0]["status"] == "non_compliant"
    assert result.results[0]["metadata"]["reason_code"] == "copy_similarity_threshold_exceeded"
    assert result.results[0]["metadata"]["maximum_similarity"] >= 0.95
    assert result.llm_call_count == 1
    assert len(client.calls) == 1
    assert left not in repr(result)
    assert right not in repr(result)


@pytest.mark.asyncio
async def test_017_high_similarity_does_not_call_llm_for_document_roles(monkeypatch):
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
    client = _UnexpectedLLMClient()

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
    assert result.results[0]["metadata"]["reason_code"] == "copy_similarity_threshold_exceeded"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_017_strong_similarity_is_programmatic_and_never_calls_model(
    monkeypatch,
):
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
    client = _UnexpectedLLMClient()

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
    assert result.results[0]["metadata"]["reason_code"] == "copy_similarity_threshold_exceeded"
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert copied not in repr(result)


@pytest.mark.asyncio
async def test_typed_017_high_similarity_is_non_compliant_without_model():
    private_marker = "PRIVATE_017_UNKNOWN_MATERIAL"
    copied = f"{private_marker}患者病情平稳，查体无明显变化，继续当前治疗方案。"

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            [
                {**_row(copied), "document_id": "private-left"},
                {
                    **_row(copied, "2026-06-02 09:00:00"),
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
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    client = _UnexpectedLLMClient()
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

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "threshold_exceeded"
    assert result.decisions[0].evidence_state is EvidenceState.SUFFICIENT
    assert result.decisions[0].confidence is None
    assert result.llm_call_count == 0
    assert private_marker not in repr(result)
    assert "private-left" not in repr(result)


@pytest.mark.asyncio
async def test_typed_017_keeps_exact_evidence_when_record_time_is_ambiguous():
    copied = "患者病情平稳，查体无明显变化，继续当前治疗方案。" * 4

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            [
                {
                    **_row(copied, "2026-06-01 09:00:00"),
                    "document_id": "copy-left",
                },
                {
                    **_row(copied, "2026-06-02 09:00:00"),
                    "document_id": "copy-right-selected",
                },
                {
                    **_row("甲" * 120, "2026-06-02 09:00:00"),
                    "document_id": "copy-right-other-a",
                },
                {
                    **_row("乙" * 120, "2026-06-02 09:00:00"),
                    "document_id": "copy-right-other-b",
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
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    native = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        decision_rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_UnexpectedLLMClient(),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions,
        expected_rule_ids=("LX0609-017",),
        snapshot=session.snapshot,
    )

    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-017", "name": "不合理复制病历"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=native.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
        format_evidence=False,
    )[0]

    raw_facts = dict(native.customer_display_facts)["LX0609-017"]
    assert len(raw_facts["copy_match_document_fingerprints"]) == 1
    assert all(
        value.startswith("sha256:")
        for value in raw_facts["copy_match_document_fingerprints"][0]
    )
    assert canonical["status"] == "non_compliant"
    evidence = canonical["customer_evidence"]
    assert [item["source_document_id"] for item in evidence] == [
        "copy-left",
        "copy-right-selected",
    ]
    assert all(item["source_type"] == "daily_course_record" for item in evidence)
    assert all(item.get("record_time") for item in evidence)
    assert all(item.get("field_path") == "record_content" for item in evidence)
    assert all(item.get("evidence_excerpt") for item in evidence)
    assert "copy_match_document_fingerprints" not in canonical["customer_display_facts"]
    assert "copy-right-selected" not in repr(native)


@pytest.mark.asyncio
async def test_typed_017_finds_non_adjacent_copy_across_twenty_course_records():
    distinct_bodies = tuple(
        character * 80
        for character in "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未"
    )
    copied_body = "患者病情稳定继续当前治疗方案密切观察病情变化" * 5

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = []
        if source_key == "daily_course_record":
            bodies = (copied_body, *distinct_bodies, copied_body)
            rows = [
                {
                    **_row(body, f"2026-06-{index:02d} 09:00:00"),
                    "document_id": f"course-{index:02d}",
                }
                for index, body in enumerate(bodies, start=1)
            ]
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
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        decision_rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_UnexpectedLLMClient(),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-017",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert result.results == ()
    facts = dict(result.customer_display_facts)["LX0609-017"]
    assert facts["copy_similarity"] == 1.0
    assert facts["copy_match_pairs"][0] == {
        "source_types": ["daily_course_record", "daily_course_record"],
        "record_times": ["2026-06-01 09:00:00", "2026-06-20 09:00:00"],
        "similarity": 1.0,
    }
    assert result.llm_call_count == 0


def test_017_twenty_records_screen_all_pairs_but_precisely_compare_only_twenty():
    rows = [
        {
            **_row(
                f"第{index}次病程记录包含当日症状检查治疗方案以及后续观察计划" * 3,
                f"2026-06-{index:02d} 09:00:00",
            ),
            "document_id": f"course-{index:02d}",
        }
        for index in range(1, 21)
    ]

    result = course._copy_result(
        {"daily_course_record": rows, "senior_course_record": []},
        source_complete=True,
    )

    assert result["metadata"]["screened_pair_count"] == 190
    assert result["metadata"]["precise_pair_count"] == 20


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("similarity", "expected_state", "expected_reason", "expected_failure_kind"),
    [
        (0.6999, CustomerFinalState.COMPLIANT, "requirement_within_threshold", "copy_similarity_within_threshold"),
        (0.7000, CustomerFinalState.NON_COMPLIANT, "threshold_exceeded", "copy_similarity_threshold_exceeded"),
        (0.7001, CustomerFinalState.NON_COMPLIANT, "threshold_exceeded", "copy_similarity_threshold_exceeded"),
    ],
)
async def test_typed_017_similarity_threshold_is_inclusive_without_model(
    monkeypatch,
    similarity,
    expected_state,
    expected_reason,
    expected_failure_kind,
):
    """017 的 70% 边界必须经公开 Native 入口成为受控终态。"""

    class _FixedSimilarityMatcher:
        def __init__(self, _isjunk, left, right, *, autojunk=False):
            self._shortest_length = min(len(left), len(right))

        def ratio(self):
            return similarity

        def get_matching_blocks(self):
            return [SimpleNamespace(size=self._shortest_length)]

    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            [
                {**_row("甲" * 60), "document_id": "copy-left"},
                {
                    **_row("乙" * 60, "2026-06-02 09:00:00"),
                    "document_id": "copy-right",
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

    monkeypatch.setattr(rules_016_017, "SequenceMatcher", _FixedSimilarityMatcher)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-017",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T12:00:00+08:00",
        row_reader=read,
    )
    client = (
        _CopyReviewClient("substantial_copy")
        if similarity >= 0.7
        else _UnexpectedLLMClient()
    )
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

    assert reduced[0].final_state is expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.decisions[0].reason_code == expected_reason
    expected_facts = {
        "failure_kind": expected_failure_kind,
        "copy_similarity": round(similarity, 4),
        "copy_similarity_threshold": 0.7,
        "copy_document_sources": ["daily_course_record", "daily_course_record"],
        "copy_document_record_times": [
            "2026-06-01 09:00:00",
            "2026-06-02 09:00:00",
        ],
        "copy_match_pairs": [],
    }
    if similarity >= 0.7:
        expected_facts["copy_match_pairs"] = [
            {
                "source_types": ["daily_course_record", "daily_course_record"],
                "record_times": [
                    "2026-06-01 09:00:00",
                    "2026-06-02 09:00:00",
                ],
                "similarity": round(similarity, 4),
            }
        ]
    actual_facts = dict(result.customer_display_facts)["LX0609-017"]
    fingerprints = actual_facts.pop("copy_match_document_fingerprints", None)
    assert actual_facts == expected_facts
    if similarity >= 0.7:
        assert fingerprints and len(fingerprints) == 1
        assert len(fingerprints[0]) == 2
        assert result.llm_call_count == 1
        assert result.total_tokens == 48
    else:
        assert fingerprints is None
        assert result.llm_call_count == result.prompt_tokens == result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "client",
    [
        _Client(["not-json"]),
        _Client([RuntimeError("raw Bearer_secret 13800138000")]),
    ],
)
async def test_017_high_similarity_fails_closed_when_semantic_review_fails(
    monkeypatch, client: _Client
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

    assert [item["status"] for item in result.results] == ["technical_error"]
    assert result.results[0]["metadata"]["reason_code"] in {
        "model_invalid_output",
        "model_transport_error",
    }
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
        llm_client=_CopyReviewClient("substantial_copy"),
    )

    assert reader_calls == ["daily_course_record", "senior_course_record"]
    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.llm_call_count == 1
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
        ([], "not_applicable", "insufficient_independent_course_records"),
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
    assert result.results[0]["metadata"]["reason_code"] == (
        "insufficient_independent_course_records"
    )
    assert result.results[0]["metadata"]["comparable_document_count"] == 1
    assert "safe-document-ref" not in repr(result)


@pytest.mark.asyncio
async def test_017_fast5_high_similarity_is_reviewed_once(
    monkeypatch,
):
    """Fast5：模板与实质难区分的高相似病程只复核一次。"""
    template = "患者一般情况可生命体征平稳继续当前治疗观察病情变化" * 8
    left = f"{template}今日腹痛较前减轻，继续观察。"
    right = (
        f"{template}今日腹痛较前减轻，继续观察并复查，同时记录饮食睡眠、"
        "排便排尿及后续门诊随访安排，未出现新的诊疗风险。"
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(left), "document_id": "safe-left"},
            {**_row(right, "2026-06-02 09:00:00"), "document_id": "safe-right"},
        ]
        if kwargs["source_key"] == "daily_course_record"
        else [],
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_CopyReviewClient("substantial_copy"),
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_017_fast5_missing_authoritative_course_time_is_data_gap(monkeypatch):
    """Fast5：任一可比病程缺权威时间，不能把相似度硬判为缺陷。"""
    copied = "患者神志清楚生命体征平稳继续当前治疗并观察病情变化。"
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(copied, ""), "document_id": "safe-left"},
            {**_row(copied, "2026-06-02 09:00:00"), "document_id": "safe-right"},
        ]
        if kwargs["source_key"] == "daily_course_record"
        else [],
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_UnexpectedLLMClient(),
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "copy_authoritative_time_missing"
    )


@pytest.mark.asyncio
async def test_017_compares_distinct_same_day_records_in_authoritative_time_order(
    monkeypatch,
):
    """同日两份不同文书仍须按权威时间成为可比候选，不能被日期门控遗漏。"""

    copied = (
        "患者腹部压痛范围较前缩小且白细胞复查持续下降，"
        "继续根据培养结果调整抗感染方案并观察病情变化。"
    )
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(copied, "2026-06-01 08:00:00"), "document_id": "same-day-a"},
            {**_row(copied, "2026-06-01 16:00:00"), "document_id": "same-day-b"},
        ]
        if kwargs["source_key"] == "daily_course_record"
        else [],
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_UnexpectedLLMClient(),
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "copy_similarity_threshold_exceeded"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_017_same_timestamp_distinct_documents_are_data_gap(monkeypatch):
    """两份独立文书的权威时间相同，不能伪造先后顺序或判为不适用。"""

    copied = "患者腹部压痛范围较前缩小，继续抗感染治疗并观察病情变化。"
    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {**_row(copied, "2026-06-01 08:00:00"), "document_id": "same-time-a"},
            {**_row(copied, "2026-06-01 08:00:00"), "document_id": "same-time-b"},
        ]
        if kwargs["source_key"] == "daily_course_record"
        else [],
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_UnexpectedLLMClient(),
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.results[0]["metadata"]["reason_code"] == (
        "copy_authoritative_time_ambiguous"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_017_same_day_distinct_content_is_compared_without_model_call(monkeypatch):
    """同日记录内容不同也要形成候选，并维持纯程序判定。"""

    monkeypatch.setattr(
        course,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: [
            {
                **_row(
                    "患者腹痛较前明显减轻，复查炎症指标下降，继续当前抗感染治疗并观察。",
                    "2026-06-01 08:00:00",
                ),
                "document_id": "same-day-a",
            },
            {
                **_row(
                    "患者咳嗽咳痰加重，听诊双肺湿啰音，调整雾化治疗并复查胸部影像。",
                    "2026-06-01 16:00:00",
                ),
                "document_id": "same-day-b",
            },
        ]
        if kwargs["source_key"] == "daily_course_record"
        else [],
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(documents={}),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_UnexpectedLLMClient(),
    )

    assert [item["status"] for item in result.results] == ["compliant"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_018_sends_only_lowest_structured_admission_diagnosis_to_model():
    """第二诊断即使更贴合主诉，也不得冒充结构化第一入院诊断。"""

    client = _Client(
        [
            {
                "diagnostic_relation_state": "mismatch",
                "diagnostic_reason_dimensions": ["anatomic_site"],
                "diagnostic_rationale_code": "diagnosis_mismatch",
            }
        ]
    )
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(
            documents={
                "admission_record": [_row("主诉：反复胸痛3个月。现病史完整。")],
                "admission_record_diagnosis": [
                    {
                        "diagnosis_type": "入院诊断",
                        "diagnosis_no": "1",
                        "diagnosis_name": "急性胆囊炎",
                    },
                    {
                        "diagnosis_type": "入院诊断",
                        "diagnosis_no": "2",
                        "diagnosis_name": "不稳定型心绞痛",
                    },
                ],
            }
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.llm_call_count == 1
    assert "急性胆囊炎" in client.prompts[0]
    assert "不稳定型心绞痛" not in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "diagnoses",
    [
        [
            {
                "diagnosis_type": "入院诊断",
                "diagnosis_name": "不稳定型心绞痛",
            }
        ],
        [
            {
                "diagnosis_type": "入院诊断",
                "diagnosis_no": "1",
                "diagnosis_name": "急性胆囊炎",
            },
            {
                "diagnosis_type": "入院诊断",
                "diagnosis_no": "1",
                "diagnosis_name": "不稳定型心绞痛",
            },
        ],
    ],
)
async def test_018_missing_or_conflicting_structured_order_fails_closed(
    diagnoses: list[dict[str, str]],
):
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(
            documents={
                "admission_record": [_row("主诉：反复胸痛3个月。现病史完整。")],
                "admission_record_diagnosis": diagnoses,
            }
        ),
        llm_client=_UnexpectedLLMClient(),
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_018_requires_chief_complaint_and_primary_diagnosis():
    client = _Client([{
        "diagnostic_relation_state": "supported",
        "diagnostic_reason_dimensions": ["symptom_pattern"],
        "diagnostic_rationale_code": "supported",
    }])
    incomplete = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(
            documents={"admission_record": [_row("现病史待查。")]}
        ),
        llm_client=client,
    )
    assert [item["status"] for item in incomplete.results] == ["data_gap"]
    assert incomplete.llm_call_count == 0

    complete = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(
            documents={
                "admission_record": [_row("主诉：反复胸痛3个月。现病史待查。")],
                "diagnosis": [
                    {
                        "diagnosis_type": "入院诊断",
                        "diagnosis_no": "1",
                        "diagnosis_name": "不稳定型心绞痛",
                    }
                ],
            }
        ),
        llm_client=client,
    )
    assert [item["status"] for item in complete.results] == ["compliant"]
    assert complete.llm_call_count == 1


@pytest.mark.asyncio
async def test_018_returns_safe_criterion_results_without_returning_admission_text():
    client = _Client(
        [
            {
                "diagnostic_relation_state": "unsupported",
                "diagnostic_reason_dimensions": ["symptom_pattern"],
                "diagnostic_rationale_code": "symptom_only",
                "medical_analysis": "主诉症状与第一诊断缺少特异性对应。",
            }
        ]
    )
    complaint = "胸痛" * 10 + "加"
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(
            documents={
                "admission_record": [
                    _row(f"主诉：{complaint}。入院诊断：急性胆囊炎。")
                ],
                "diagnosis": [
                    {
                        "diagnosis_type": "入院诊断",
                        "diagnosis_no": "1",
                        "diagnosis_name": "急性胆囊炎",
                    }
                ],
            }
        ),
        llm_client=client,
    )

    item = result.results[0]
    criteria = item["criterion_results"]
    assert [(row["criterion_id"], row["status"]) for row in criteria] == [
        ("chief_complaint_length", "failed"),
        ("diagnostic_direction", "failed"),
    ]
    assert criteria[0]["actual_value"] == 21
    assert criteria[0]["expected_value"] == 20
    assert criteria[0]["operator"] == "lte"
    assert complaint not in repr(item)
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_018_length_boundary_allows_20_chars_and_rejects_21_chars():
    client = _Client([
        {
            "diagnostic_relation_state": "supported",
            "diagnostic_reason_dimensions": ["symptom_pattern"],
            "diagnostic_rationale_code": "supported",
        },
        {
            "diagnostic_relation_state": "supported",
            "diagnostic_reason_dimensions": ["symptom_pattern"],
            "diagnostic_rationale_code": "supported",
        },
    ])
    statuses = []
    lengths = []
    for complaint in ("胸痛" * 10, "胸痛" * 10 + "加"):
        result = await course.execute_luxian_0609_native_course_quality_rules(
            rule_ids=("LX0609-018",),
            wrapper_rules=[_wrapper("LX0609-018")],
            evidence_payload=_payload(
                documents={
                    "admission_record": [
                        _row(f"主诉：{complaint}。入院诊断：冠心病。")
                    ],
                    "diagnosis": [
                        {
                            "diagnosis_type": "入院诊断",
                            "diagnosis_no": "1",
                            "diagnosis_name": "冠心病",
                        }
                    ],
                }
            ),
            llm_client=client,
        )
        statuses.append(result.results[0]["status"])
        lengths.append(result.results[0]["criterion_results"][0]["actual_value"])
        assert result.llm_call_count == 1

    assert lengths == [20, 21]
    assert statuses == ["compliant", "non_compliant"]


def test_018_diagnostic_rationale_code_cannot_contradict_returned_dimensions():
    response = {
        "content": json.dumps(
            {
                "diagnostic_rationale_code": "symptom_only",
            }
        )
    }

    assert course._parse_lx018_diagnostic_rationale_code(
        response,
        relation_state="unsupported",
        dimensions=("anatomic_site", "symptom_pattern"),
    ) == "site_symptom_not_specific"


@pytest.mark.asyncio
async def test_018_model_failure_is_controlled_without_leaking_upstream_text():
    secret = "Bearer_secret_13800138000"
    client = _Client([RuntimeError(secret), f"not-json {secret}"])
    payload = _payload(
        documents={
            "admission_record": [_row("主诉：反复胸痛3个月。入院诊断：不稳定型心绞痛。")],
            "first_course_record": [_row("首次病程病例特点与诊断依据。")],
            "diagnosis": [
                {
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                    "diagnosis_name": "不稳定型心绞痛",
                }
            ],
        }
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016", "LX0609-018"),
        wrapper_rules=[_wrapper("LX0609-016"), _wrapper("LX0609-018")],
        evidence_payload=payload,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "data_gap",
        "technical_error",
    ]
    assert result.llm_call_count == 1
    assert secret not in repr(result)
