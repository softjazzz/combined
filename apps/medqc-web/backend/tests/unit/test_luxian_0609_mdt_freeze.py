from __future__ import annotations

from collections.abc import Mapping

import pytest

from app.services.luxian_0609 import native_mdt_execution
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.engine import FamilyExecutionContext
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import (
    LegacyFamilyExecutionResources,
    LegacyNativeExecutorFunctions,
    build_luxian_0609_legacy_executor_registry,
)
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609.source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)
from app.services.luxian_0609_result_aggregator import (
    Luxian0609CustomerDisplayFactsError,
    aggregate_luxian_0609_results,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules


RULE_ID = "LX0609-040"
_SOURCE_KEYS = (
    "mr_surgery",
    "presurg_summary",
    "presurg_discussion",
    "consultation_record",
)


class _RecordedLlm:
    def __init__(
        self,
        *,
        content: str = '{"state":"unknown","confidence":0.5}',
        raises: bool = False,
    ) -> None:
        self.content = content
        self.raises = raises
        self.calls: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.calls.append(prompt)
        if self.raises:
            raise TimeoutError("controlled timeout")
        return {
            "choices": [{"message": {"content": self.content}}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 12,
                "total_tokens": 132,
            },
            "_api_time": 0.25,
        }


def _session(
    rows_by_source: Mapping[str, list[dict]],
    *,
    failed_source: str = "",
    unavailable: bool = False,
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == failed_source:
            error = SourceEvidenceUnavailable if unavailable else SourceEvidenceQueryError
            raise error("controlled source failure")
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE_ID,),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-09-06T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=_SOURCE_KEYS,
    )


async def _unexpected_executor(**_kwargs):
    raise AssertionError("only surgery_mdt may run in this freeze")


async def _execute_and_project(session, llm: _RecordedLlm | None, *, project: bool = True):
    """走正式 registry -> executor -> Binding -> 客户投影，不伪造 RuleDecision。"""

    contract = next(
        item for item in load_luxian_0609_rule_contracts() if item.rule_id == RULE_ID
    )
    assert contract.executor_key == "surgery_mdt"
    resources = LegacyFamilyExecutionResources(
        wrapper_rules=tuple(
            rule for rule in load_luxian_0609_rules() if rule["rule_id"] == RULE_ID
        ),
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=(RULE_ID,),
    )
    functions = LegacyNativeExecutorFunctions(
        surgery_presence=_unexpected_executor,
        basic_timeliness=_unexpected_executor,
        exam_lab=_unexpected_executor,
        consultation_quality=_unexpected_executor,
        transfusion=_unexpected_executor,
        tumor_pathology=_unexpected_executor,
        course_quality=_unexpected_executor,
        surgery_gate=_unexpected_executor,
        surgery_document=_unexpected_executor,
        surgery_mdt=native_mdt_execution.execute_luxian_0609_native_mdt_rule,
        extended_document=_unexpected_executor,
    )
    registry = build_luxian_0609_legacy_executor_registry(
        resources=resources,
        functions=functions,
    )
    envelope = await registry.resolve("surgery_mdt").executor.evaluate(
        FamilyExecutionContext(
            selected_rule_ids=(RULE_ID,),
            snapshot=session.snapshot,
            contracts=(contract,),
            deadline_seconds=1.0,
        )
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=envelope.decisions,
        expected_rule_ids=(RULE_ID,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    if not project:
        return envelope, reduced[0], None
    results = aggregate_luxian_0609_results(
        wrapper_rules=list(resources.wrapper_rules),
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=envelope.customer_display_facts,
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )
    assert len(results) == 1
    return envelope, reduced[0], results[0]


def _surgery(
    *,
    level: str = "四级",
    surgery_id: str = "SURGERY-040",
    begin: str = "2026-01-02T09:00:00",
) -> dict:
    return {
        "surgery_id": surgery_id,
        "surgery_name": "测试四级手术",
        "surgical_level": level,
        "surgery_begin_datetime": begin,
    }


def _ordinary_preop_rows() -> dict[str, list[dict]]:
    return {
        "mr_surgery": [_surgery()],
        "presurg_discussion": [
            {
                "document_id": "DISC-ORDINARY",
                "record_time": "2026-01-01T09:00:00",
                "record_content": "请单一专科协助评估手术风险。",
            }
        ],
        "consultation_record": [],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "rows", "llm", "state", "reason", "calls"),
    (
        ("无手术", {}, None, "not_applicable", "trigger_absent_complete", 0),
        (
            "非四级手术",
            {"mr_surgery": [_surgery(level="三级")]},
            None,
            "not_applicable",
            "trigger_absent_complete",
            0,
        ),
        (
            "择期四级手术已完成MDT",
            {
                "mr_surgery": [_surgery()],
                "presurg_discussion": [
                    {
                        "document_id": "DISC-MDT",
                        "record_time": "2026-01-01T09:00:00",
                        "record_content": "经多学科讨论后一致认为可实施手术。",
                    }
                ],
            },
            None,
            "compliant",
            "requirement_satisfied",
            0,
        ),
        (
            "择期四级手术缺MDT",
            {"mr_surgery": [_surgery()]},
            None,
            "non_compliant",
            "requirement_violated",
            0,
        ),
        (
            "多台四级手术",
            {
                "mr_surgery": [
                    _surgery(surgery_id="SURGERY-1"),
                    _surgery(surgery_id="SURGERY-2", begin="2026-01-05T09:00:00"),
                ]
            },
            None,
            "data_gap",
            "required_field_missing",
            0,
        ),
    ),
    ids=lambda value: value if isinstance(value, str) else None,
)
async def test_mdt_typed_registry_binding_and_public_projection_are_frozen(
    name,
    rows,
    llm,
    state,
    reason,
    calls,
):
    session = _session(rows)
    envelope, reduced, result = await _execute_and_project(session, llm)

    assert envelope.usage_attribution.executor_key == "surgery_mdt"
    assert reduced.final_state.value == state, name
    assert reduced.reason_code == reason, name
    assert result["status"] == state, name
    assert result["reason_code"] == reason, name
    assert envelope.llm_call_count == calls, name
    assert envelope.total_tokens == 0, name


@pytest.mark.asyncio
async def test_mdt_emergency_exemption_is_blocked_by_current_public_facts_contract():
    session = _session(
        {
            "mr_surgery": [_surgery()],
            "presurg_summary": [
                {"record_content": "本次急诊抢救，为挽救生命立即手术。"}
            ],
        }
    )
    envelope, reduced, _ = await _execute_and_project(session, None, project=False)

    assert (reduced.final_state.value, reduced.reason_code) == (
        "not_applicable",
        "trigger_absent_complete",
    )
    assert dict(envelope.customer_display_facts)[RULE_ID]["mdt_exception"] == (
        "emergency_lifesaving_surgery"
    )
    with pytest.raises(Luxian0609CustomerDisplayFactsError):
        await _execute_and_project(session, None)


@pytest.mark.asyncio
async def test_mdt_public_evidence_is_limited_to_trigger_surgery_coordinates():
    session = _session(
        {
            "mr_surgery": [_surgery(surgery_id="SURGERY-EXACT")],
            "presurg_discussion": [
                {
                    "document_id": "DISC-PRIVATE",
                    "record_time": "2026-01-01T09:00:00",
                    "record_content": "经多学科讨论后一致认为可实施手术。",
                }
            ],
        }
    )
    envelope, reduced, result = await _execute_and_project(session, None)

    assert reduced.final_state.value == "compliant"
    assert envelope.customer_display_facts == (
        (
            RULE_ID,
            {
                "performed_surgery_confirmed": True,
                "procedure_kind": "surgery",
                "effective_surgery_level": "四级",
                "surgery_level_source": "structured_field",
                "mdt_discussion_state": "completed",
                "source_document_refs": [
                    {"source_type": "mr_surgery", "source_document_id": "SURGERY-EXACT"}
                ],
            },
        ),
    )
    assert result["customer_display_facts"] == {
        "performed_surgery_confirmed": True,
        "procedure_kind": "surgery",
        "effective_surgery_level": "四级",
        "surgery_level_source": "structured_field",
        "mdt_discussion_state": "completed",
    }
    assert result["customer_evidence"] == [
        {
            "source_type": "mr_surgery",
            "source_document_id": "SURGERY-EXACT",
            "record_time": "2026-01-02 09:00:00",
        },
        {
            "source_type": "presurg_discussion",
            "source_document_id": "DISC-PRIVATE",
            "record_time": "2026-01-01 09:00:00",
            "field_path": "record_content",
            "evidence_excerpt": "经多学科讨论后一致认为可实施手术。",
            "excerpt_kind": "文书级依据",
        },
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "llm", "expected_calls", "expected_tokens"),
    (
        ("模型超时", _RecordedLlm(raises=True), 1, 0),
        ("模型非法JSON", _RecordedLlm(content="not-json"), 1, 132),
        ("模型合法unknown", _RecordedLlm(), 1, 132),
    ),
)
async def test_mdt_model_failures_and_semantic_unknown_currently_collapse_to_one_data_gap(
    name,
    llm,
    expected_calls,
    expected_tokens,
):
    session = _session(_ordinary_preop_rows())
    envelope, reduced, result = await _execute_and_project(session, llm)

    assert len(llm.calls) == expected_calls, name
    assert "术前证据窗口" in llm.calls[0], name
    assert "请单一专科协助评估手术风险。" in llm.calls[0], name
    assert envelope.llm_call_count == expected_calls, name
    assert envelope.total_tokens == expected_tokens, name
    # 这是冻结的阻塞反例：timeout、协议非法与语义 unknown 都丢失了失败语义。
    assert (reduced.final_state.value, reduced.reason_code) == (
        "data_gap",
        "required_field_missing",
    ), name
    assert (result["status"], result["reason_code"]) == (
        "data_gap",
        "required_field_missing",
    ), name


@pytest.mark.asyncio
async def test_mdt_source_query_failure_remains_technical_error_through_binding():
    session = _session({}, failed_source="mr_surgery")
    envelope, reduced, result = await _execute_and_project(session, None)

    assert envelope.llm_call_count == 0
    assert (reduced.final_state.value, reduced.reason_code) == (
        "technical_error",
        "source_query_error",
    )
    assert (result["status"], result["reason_code"]) == (
        "technical_error",
        "source_query_error",
    )


@pytest.mark.asyncio
async def test_mdt_incomplete_discussion_source_is_data_gap_without_model_call():
    session = _session(
        {"mr_surgery": [_surgery()]},
        failed_source="presurg_discussion",
        unavailable=True,
    )
    envelope, reduced, result = await _execute_and_project(session, None)

    assert envelope.llm_call_count == 0
    assert (reduced.final_state.value, reduced.reason_code) == (
        "data_gap",
        "source_unavailable",
    )
    assert (result["status"], result["reason_code"]) == (
        "data_gap",
        "source_unavailable",
    )


@pytest.mark.asyncio
async def test_mdt_missing_model_client_currently_collapses_to_required_field_missing():
    session = _session(_ordinary_preop_rows())
    envelope, reduced, result = await _execute_and_project(session, None)

    assert envelope.llm_call_count == 0
    assert (reduced.final_state.value, reduced.reason_code) == (
        "data_gap",
        "required_field_missing",
    )
    assert (result["status"], result["reason_code"]) == (
        "data_gap",
        "required_field_missing",
    )


@pytest.mark.asyncio
async def test_mdt_parser_does_not_validate_confidence_or_reason_code_types():
    session = _session(_ordinary_preop_rows())
    llm = _RecordedLlm(
        content='{"state":"present","confidence":"not-a-number","reason_code":[]}'
    )
    envelope, reduced, result = await _execute_and_project(session, llm)

    assert envelope.llm_call_count == 1
    assert envelope.total_tokens == 132
    assert (reduced.final_state.value, reduced.reason_code) == (
        "compliant",
        "requirement_satisfied",
    )
    assert (result["status"], result["reason_code"]) == (
        "compliant",
        "requirement_satisfied",
    )
