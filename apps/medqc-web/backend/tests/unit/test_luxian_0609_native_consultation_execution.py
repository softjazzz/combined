from __future__ import annotations

import json

import pytest

from app.services.luxian_0609 import native_consultation_execution as consultation
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)


class _SequenceClient:
    def __init__(self, *payloads: object):
        self.payloads = list(payloads)
        self.calls: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.calls.append(prompt)
        payload = self.payloads.pop(0)
        content = payload if isinstance(payload, str) else json.dumps(payload)
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "_api_time": 0.1,
        }


def _material_session(rows_by_source: dict[str, list[dict]]):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=consultation.CONSULTATION_RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-31T10:00:00+08:00",
        row_reader=read,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_complete_empty_consultation_is_not_applicable_without_llm(monkeypatch):
    session = _material_session({})
    client = _SequenceClient()
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("完整证据材料不得回退实时查询")
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=consultation.CONSULTATION_RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
    )

    assert client.calls == []
    assert [item["status"] for item in execution.results] == [
        "not_applicable"
    ] * 4
    assert {
        item["metadata"]["reason_code"] for item in execution.results
    } == {"consultation_absent"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unproven_empty_live_read_fails_closed_as_data_gap(monkeypatch):
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: [],
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=consultation.CONSULTATION_RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_SequenceClient(),
    )

    assert [item["status"] for item in execution.results] == ["data_gap"] * 4
    assert {
        item["metadata"]["reason_code"] for item in execution.results
    } == {"consultation_source_incomplete"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_four_rules_use_two_bounded_fact_calls_and_return_controlled_results(
    monkeypatch,
):
    session = _material_session(
        {
            "consultation_record": [
                {
                    "document_title": "会诊记录",
                    "record_time": "2026-07-01 10:00:00",
                    "record_content": (
                        "因持续胸闷请心内科会诊。"
                        "会诊意见：调整药物剂量并复查心电图。"
                    ),
                }
            ],
            "daily_course_record": [
                {
                    "document_title": "日常病程",
                    "record_time": "2026-07-01 12:00:00",
                    "record_content": "遵会诊意见调整药物剂量，并已复查心电图。",
                }
            ],
        }
    )
    client = _SequenceClient(
        {
            "documents": [
                [
                    "C01",
                    ["application", "opinion"],
                    "clear",
                    "clear",
                    "high",
                ]
            ]
        },
        {
            "facts": {
                "LX0609-020": {
                    "fact": "execution_all_present",
                    "evidence_refs": ["C01", "D01"],
                    "confidence": "high",
                },
                "LX0609-023": {
                    "fact": "execution_specific",
                    "evidence_refs": ["C01", "D01"],
                    "confidence": "high",
                },
            }
        },
    )
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("完整证据材料不得回退实时查询")
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=consultation.CONSULTATION_RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
    )

    assert len(client.calls) == 2
    assert execution.llm_call_count == 2
    assert execution.total_tokens == 30
    assert [item["status"] for item in execution.results] == ["compliant"] * 4
    assert all("record_content" not in repr(item) for item in execution.results)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_semantic_parse_failure_retries_once_then_uses_valid_payload(monkeypatch):
    session = _material_session(
        {
            "consultation_record": [
                {
                    "document_title": "会诊记录",
                    "record_time": "2026-07-01 10:00:00",
                    "record_content": "因持续胸闷请心内科会诊。会诊意见：调整药物剂量。",
                }
            ]
        }
    )
    client = _SequenceClient(
        "not-json",
        {"documents": [["C01", ["application", "opinion"], "clear", "clear", "high"]]},
    )
    monkeypatch.setattr(
        consultation,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("完整证据材料不得回退实时查询")
        ),
    )

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
    )

    assert len(client.calls) == 2
    assert execution.llm_call_count == 2
    assert execution.total_tokens == 30
    assert [item["status"] for item in execution.results] == ["compliant", "compliant"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_semantic_parse_failure_after_retry_is_technical_error(monkeypatch):
    session = _material_session(
        {
            "consultation_record": [
                {
                    "document_title": "会诊记录",
                    "record_time": "2026-07-01 10:00:00",
                    "record_content": "因持续胸闷请心内科会诊。会诊意见：调整药物剂量。",
                }
            ]
        }
    )
    client = _SequenceClient("not-json", "still-not-json")

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
    )

    assert execution.llm_call_count == 2
    assert [item["status"] for item in execution.results] == [
        "technical_error",
        "technical_error",
    ]
    assert {
        item["metadata"]["reason_code"] for item in execution.results
    } == {"model_invalid_output"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execution_parse_failure_retries_once_and_fails_closed(monkeypatch):
    session = _material_session(
        {
            "consultation_record": [
                {
                    "document_title": "会诊记录",
                    "record_time": "2026-07-01 10:00:00",
                    "record_content": "因持续胸闷请心内科会诊。会诊意见：调整药物剂量。",
                }
            ],
            "daily_course_record": [
                {
                    "document_title": "日常病程",
                    "record_time": "2026-07-01 12:00:00",
                    "record_content": "遵会诊意见调整药物剂量。",
                }
            ],
        }
    )
    client = _SequenceClient("not-json", "still-not-json")

    execution = await consultation.execute_luxian_0609_native_consultation_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
    )

    assert execution.llm_call_count == 2
    assert [item["status"] for item in execution.results] == [
        "technical_error",
        "technical_error",
    ]
    assert {
        item["metadata"]["reason_code"] for item in execution.results
    } == {"model_invalid_output"}


def test_fact_prompts_keep_semantic_and_execution_boundaries_separate():
    semantic_prompt = consultation._consultation_semantic_prompt(
        context='{"ref":"C01"}'
    )
    execution_prompt = consultation._consultation_rule_fact_prompt(
        selected=("LX0609-020", "LX0609-023"),
        context='{"ref":"C01"}',
    )

    assert "application_state" in semantic_prompt
    assert "opinion_state" in semantic_prompt
    assert "execution_all_present" not in semantic_prompt
    assert "execution_all_present" in execution_prompt
    assert "execution_specific" in execution_prompt


def test_022_explicit_family_decision_not_to_treat_is_not_missing_opinion():
    """真实会诊中“已沟通、家属暂不处理”属于明确处置意见。"""

    reason = consultation._opinion_state_from_record(
        "会诊意见：可请消化内科评估；家属强烈要求时建议上级医院。"
        "已与家属沟通，家属暂不处理痔疮。"
    )

    assert reason == "opinion_clear"


@pytest.mark.parametrize(
    "content",
    [
        "会诊意见：建议家属暂不处理痔疮。",
        "会诊意见：拟与家属沟通，暂不处理。",
        "会诊意见：必要时可暂缓手术。",
        "会诊意见：已与家属沟通，家属未拒绝处理痔疮。",
        "会诊意见：家属并未不同意手术。",
        "会诊意见：家属暂不处理尚未确定。",
    ],
)
def test_opinion_state_does_not_promote_suggestion_or_plan_to_clear(content):
    assert consultation._opinion_state_from_record(content) is None
