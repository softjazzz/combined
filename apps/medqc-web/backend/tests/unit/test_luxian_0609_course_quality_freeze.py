"""Freeze the current course-quality family through native → Binding → Aggregator.

This is the pre-migration baseline only.  It deliberately records current canonical
behaviour and controlled semantic-stub usage; it does not prescribe the target
customer facts or aggregator ownership after a later migration.
"""

from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any, Mapping, Sequence

import pytest

from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_course_quality_execution import (
    COURSE_QUALITY_RULE_IDS,
    execute_luxian_0609_native_course_quality_rules,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
    CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
)
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
)


_FAMILY_RULE_IDS = (
    "LX0609-02-01-03",
    "LX0609-02-01-04",
    "LX0609-02-01-05",
    "LX0609-12-01-01",
    "LX0609-12-01-02",
    "LX0609-01-01-02",
)


class _StubClient:
    """Deterministic semantic response with a stable, inspectable usage payload."""

    def __init__(self, *payloads: Mapping[str, Any]) -> None:
        self._payloads = list(payloads)
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
        assert self._payloads, "unexpected course-quality LLM call"
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            self._payloads.pop(0), ensure_ascii=False
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 41,
                "completion_tokens": 7,
                "total_tokens": 48,
            },
            "_api_time": 0.01,
        }


class _CopyStubClient:
    """Return the exact one-pair schema required by LX0609-12-01-02."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
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
                            "verdict": "substantial_copy",
                            "document_refs": [left_ref, right_ref],
                        }
                        for pair_ref, left_ref, right_ref in pairs
                    ],
                },
                ensure_ascii=False,
            ),
            "usage": {
                "prompt_tokens": 41,
                "completion_tokens": 7,
                "total_tokens": 48,
            },
            "_api_time": 0.01,
        }


class _Rule009StubClient:
    """Return every supplied 009 event as an explicit non-change."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_kwargs: Any) -> dict[str, Any]:
        self.prompts.append(prompt)
        event_refs = re.findall(r"external_event_ref=(E\d+)", prompt)
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "events": [
                                    {
                                        "event_ref": event_ref,
                                        "change_category": "exam_lab",
                                        "is_explicit_change": False,
                                        "corresponding_course_ref": "",
                                    }
                                    for event_ref in event_refs
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 41,
                "completion_tokens": 7,
                "total_tokens": 48,
            },
            "_api_time": 0.01,
        }


def _wrapper(rule_id: str) -> dict[str, str]:
    return {
        "rule_id": rule_id,
        "rule_code": rule_id,
        "name": rule_id,
        "description": rule_id,
        "defect_level": "轻微缺陷",
        "custom_prompt": (
            f"规则ID: {rule_id}\\n"
            "病历文本：\\n{medical_text}\\n"
            '只输出JSON：{"is_compliant": true}'
        ),
    }


def _row(content: str, record_time: str) -> dict[str, str]:
    return {"document_id": f"doc-{record_time}", "record_content": content, "record_time": record_time}


def _session(
    rule_id: str,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    evaluation_as_of_date: str = "2026-01-04",
):
    def _reader(*, source_key: str, **_kwargs: Any) -> SnapshotSourceRows:
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=tuple(rows_by_source.get(source_key, ())),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,),
        institute_id="course-freeze-institute",
        patient_id="course-freeze-patient",
        visit_id="course-freeze-visit",
        source_schema=None,
        created_at="2026-09-07T08:00:00+08:00",
        evaluation_as_of_date=evaluation_as_of_date,
        row_reader=_reader,
    )


async def _run_chain(
    rule_id: str,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    client: Any = None,
    evaluation_as_of_date: str = "2026-01-04",
):
    session = _session(
        rule_id, rows_by_source, evaluation_as_of_date=evaluation_as_of_date
    )
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=(rule_id,),
        decision_rule_ids=(rule_id,),
        wrapper_rules=(_wrapper(rule_id),),
        evidence_payload=None,
        institute_id="course-freeze-institute",
        patient_id="course-freeze-patient",
        visit_id="course-freeze-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert execution.results == ()
    assert len(execution.decisions) == 1
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=(rule_id,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert len(reduced) == 1
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=(_wrapper(rule_id),),
        execution_results=(),
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )
    assert len(canonical) == 1
    return session, execution, reduced[0], canonical[0]


def _evidence_coordinates(result: Mapping[str, Any]) -> set[tuple[str, str, str, str]]:
    """将客户证据冻结为顺序无关、可定位的坐标集合。"""
    return {
        (
            str(item.get("source_type") or ""),
            str(item.get("source_document_id") or ""),
            str(item.get("record_time") or ""),
            str(item.get("field_path") or ""),
        )
        for item in result.get("customer_evidence") or ()
    }


def _fact_ref_sources(snapshot: Any, fact_refs: Sequence[str]) -> set[str]:
    source_by_ref = {
        str(item.snapshot_ref).removeprefix("sha256:"): item.source_key
        for item in snapshot.observations
    }
    return {source_by_ref.get(str(ref), "document_ref") for ref in fact_refs}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "rule_id",
        "rows_by_source",
        "expected_status",
        "expected_reason",
        "expected_evidence",
    ),
    (
        (
            "LX0609-02-01-03",
            {
                CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY: (),
                "inpat_registration": (
                    {"document_id": "admission-1", "admission_datetime": "2026-01-01 08:00:00"},
                ),
                CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: (
                    {"document_id": "horizon-1", "discharge_datetime": "2026-01-04 08:00:00"},
                ),
                "daily_course_record": (
                    _row("入院后第72小时完成查房。", "2026-01-04 08:00:00"),
                ),
                "senior_course_record": (),
            },
            "compliant",
            "requirement_within_threshold",
            {
                ("daily_course_record", "doc-2026-01-04 08:00:00", "2026-01-04 08:00:00", "record_content"),
                ("inpat_registration", "admission-1", "", ""),
            },
        ),
        (
            "LX0609-02-01-04",
            {"inpat_nondrug_order": (), "daily_course_record": (), "senior_course_record": ()},
            "not_applicable",
            "trigger_absent_complete",
            set(),
        ),
        (
            "LX0609-02-01-05",
            {"inpat_nondrug_order": (), "daily_course_record": (), "senior_course_record": ()},
            "not_applicable",
            "trigger_absent_complete",
            set(),
        ),
        (
            "LX0609-12-01-01",
            {
                "admission_record": (
                    {"document_id": "admission-16", "record_content": "", "history_of_present_illness": "病例特点完全一致。"},
                ),
                "first_course_record": (
                    {"document_id": "first-course-16", "record_content": "", "case_characteristic": "病例特点完全一致。"},
                ),
            },
            "non_compliant",
            "requirement_violated",
            {
                ("admission_record", "admission-16", "", ""),
                ("first_course_record", "first-course-16", "", "case_characteristic"),
            },
        ),
        (
            "LX0609-12-01-02",
            {
                "daily_course_record": (
                    _row("患者病情稳定，继续当前治疗方案并观察病情变化。" * 3, "2026-01-01 09:00:00"),
                ),
                "senior_course_record": (
                    _row("患者病情稳定，继续当前治疗方案并观察病情变化。" * 3, "2026-01-02 09:00:00"),
                ),
            },
            "non_compliant",
            "threshold_exceeded",
            {
                ("daily_course_record", "doc-2026-01-01 09:00:00", "2026-01-01 09:00:00", "record_content"),
                ("senior_course_record", "doc-2026-01-02 09:00:00", "2026-01-02 09:00:00", "record_content"),
            },
        ),
    ),
)
async def test_course_quality_freezes_native_binding_aggregate_outputs(
    rule_id: str,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    expected_status: str,
    expected_reason: str,
    expected_evidence: set[tuple[str, str, str, str]],
) -> None:
    client = _CopyStubClient() if rule_id == "LX0609-12-01-02" else None
    session, execution, reduced, result = await _run_chain(
        rule_id, rows_by_source, client=client
    )

    decision = execution.decisions[0]
    assert decision.reason_code == expected_reason
    assert reduced.reason_code == expected_reason
    assert reduced.final_state.value == expected_status
    assert reduced.fact_refs == decision.fact_refs
    assert result["status"] == expected_status
    assert result["reason_code"] == expected_reason
    if rule_id == "LX0609-02-01-03":
        # 当前聚合器会移除执行器已经选中的末端文书 ID；这是冻结到的
        # 双重展示事实所有者，迁移前不能把它“顺手修正”。
        assert result.get("customer_display_facts") == {
            "failure_kind": "course_record_interval_within_72h",
            "interval_start_source": "inpat_registration",
            "interval_end_source": "daily_course_record",
            "interval_start_time": "2026-01-01 08:00:00",
            "threshold_hours": 72,
            "recorded_dates": ["2026-01-04"],
            "interval_end_time": "2026-01-04 08:00:00",
            "interval_hours": 72.0,
            "interval_start_position": 0,
            "interval_end_position": 1,
            "record_count": 1,
            "interval_seconds": 259200,
            "overdue_seconds": 0,
        }
    elif rule_id == "LX0609-12-01-02":
        # 017 同样存在旧聚合层的展示投影：它会丢弃执行器提供的内部
        # 文书指纹，不应在冻结提交中改变这种当前客户 DTO 行为。
        expected_facts = dict(execution.customer_display_facts)[rule_id]
        assert result.get("customer_display_facts") == {
            key: value
            for key, value in expected_facts.items()
            if key != "copy_match_document_fingerprints"
        }
    elif rule_id == "LX0609-12-01-01":
        # source_document_ids 是执行器内部坐标；迁移后只能由 fact_refs
        # 经公共投影形成 customer_evidence，不能继续进入客户展示 facts。
        assert result.get("customer_display_facts") == {
            key: value
            for key, value in dict(execution.customer_display_facts)[rule_id].items()
            if key != "source_document_ids"
        }
    else:
        assert result.get("customer_display_facts") == dict(execution.customer_display_facts).get(rule_id)
    assert _fact_ref_sources(session.snapshot, decision.fact_refs)
    assert _evidence_coordinates(result) == expected_evidence
    expected_llm_calls = 1 if rule_id == "LX0609-12-01-02" else 0
    assert execution.llm_call_count == expected_llm_calls
    if expected_llm_calls:
        assert (execution.prompt_tokens, execution.completion_tokens, execution.total_tokens) == (41, 7, 48)
        assert client is not None and len(client.prompts) == 1
    else:
        assert execution.prompt_tokens == execution.total_tokens == 0


@pytest.mark.asyncio
async def test_course_quality_freezes_lx018_semantic_stub_prompt_usage_and_canonical_result() -> None:
    client = _StubClient(
        {
            "chief_signal_kind": "localized_symptom_or_sign",
            "anatomic_relation": "not_applicable",
            "laterality_relation": "not_applicable",
            "symptom_relation": "supports",
            "disease_course_relation": "not_applicable",
            "disease_direction_relation": "not_applicable",
            "medical_analysis": "主诉与第一诊断方向一致。",
        }
    )
    session, execution, reduced, result = await _run_chain(
        "LX0609-01-01-02",
        {
            "admission_record": (
                {
                    "document_id": "admission-18",
                    "record_content": "入院记录正文完整。",
                    "chief_complaint": "反复胸痛3个月",
                },
            ),
            "diagnosis": (
                {
                    "document_id": "diagnosis-18",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                    "diagnosis_name": "稳定型心绞痛",
                },
            ),
        },
        client=client,
    )

    assert execution.decisions[0].reason_code == "requirement_satisfied"
    assert reduced.final_state.value == "compliant"
    assert result["status"] == "compliant"
    assert result["reason_code"] == "requirement_satisfied"
    assert reduced.fact_refs == execution.decisions[0].fact_refs
    assert _fact_ref_sources(session.snapshot, reduced.fact_refs) == {
        "admission_record",
        "admission_record_diagnosis",
        "diagnosis",
    }
    assert execution.llm_call_count == 1
    assert (execution.prompt_tokens, execution.completion_tokens, execution.total_tokens) == (41, 7, 48)
    assert len(client.prompts) == 1
    assert "稳定型心绞痛" in client.prompts[0]
    assert _evidence_coordinates(result) == {
        ("admission_record", "admission-18", "", "record_content"),
        ("diagnosis", "diagnosis-18", "", ""),
    }


@pytest.mark.asyncio
async def test_course_quality_freezes_lx009_semantic_stub_prompt_usage_and_canonical_result() -> None:
    client = _Rule009StubClient()
    session, execution, reduced, result = await _run_chain(
        "LX0609-02-01-05",
        {
            CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY: (
                {
                    "document_id": "critical-order-1",
                    "severity": "critical",
                    "prescribed_datetime": "2026-01-01 08:00:00",
                },
            ),
            "daily_course_record": (
                _row("第一日病情稳定。", "2026-01-01 08:00:00"),
                _row("第二日继续观察。", "2026-01-02 08:00:00"),
            ),
            "senior_course_record": (),
            "exam_item_report": (
                {
                    "document_id": "exam-009",
                    "report_time": "2026-01-02 10:00:00",
                    "exam_impression": "复查结果无新发异常改变",
                },
            ),
        },
        client=client,
        evaluation_as_of_date="2026-01-02",
    )

    assert execution.decisions[0].reason_code == "requirement_satisfied"
    assert reduced.final_state.value == result["status"] == "compliant"
    assert reduced.reason_code == result["reason_code"] == "requirement_satisfied"
    assert reduced.fact_refs == execution.decisions[0].fact_refs
    assert _fact_ref_sources(session.snapshot, reduced.fact_refs)
    assert execution.llm_call_count == 1
    assert (execution.prompt_tokens, execution.completion_tokens, execution.total_tokens) == (41, 7, 48)
    assert len(client.prompts) == 1
    assert "复查结果无新发异常改变" in client.prompts[0]
    assert _evidence_coordinates(result) == {
        ("exam_item_report", "exam-009", "2026-01-02 10:00:00", "exam_impression"),
        ("daily_course_record", "doc-2026-01-01 08:00:00", "2026-01-01 08:00:00", "record_content"),
        ("daily_course_record", "doc-2026-01-02 08:00:00", "2026-01-02 08:00:00", "record_content"),
        ("inpat_nondrug_order", "critical-order-1", "", ""),
    }


def test_course_quality_freezes_family_membership_before_migration() -> None:
    assert tuple(rule_id for rule_id in COURSE_QUALITY_RULE_IDS if rule_id != "LX0609-01-02-02") == _FAMILY_RULE_IDS


def test_course_quality_rules_have_no_aggregator_specific_branches() -> None:
    """迁移完成后聚合器不得继续解释本族业务事实或选择客户证据。"""

    aggregator = (
        Path(__file__).resolve().parents[2]
        / "app/services/luxian_0609_result_aggregator.py"
    ).read_text(encoding="utf-8")
    for rule_id in _FAMILY_RULE_IDS:
        assert rule_id not in aggregator
