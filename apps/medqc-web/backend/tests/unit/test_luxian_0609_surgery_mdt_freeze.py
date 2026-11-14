"""LX0609-04-01-03 的正式主链行为冻结。

040 的客户事实合同和旧直调证据适配已迁入 Finalizer；聚合器只装配结果。
证据数组视为坐标集合，顺序不代表优先级。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from app.services.luxian_0609 import native_mdt_execution
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.engine import FamilyExecutionContext
from app.services.luxian_0609.evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
)
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
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules


RULE_ID = "LX0609-04-01-03"
_SOURCE_KEYS = (
    "surgery_record",
    "presurg_summary",
    "presurg_discussion",
    "consultation_record",
)


class _PresentLlm:
    async def generate(self, prompt, **_):
        # 急诊豁免须由模型确认本次手术为急诊（2026-10-22）。
        content = ('{"state":"emergency","quote":"为挽救生命立即手术"}'
                   if "本次住院的这次手术属于急诊" in prompt else '{"state":"present"}')
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 12,
                "total_tokens": 132,
            },
        }


class _NoLlmCall:
    """本冻结集只覆盖结构化、零 LLM 的可达形状。"""

    async def generate(self, _prompt: str) -> object:
        raise AssertionError("the deterministic MDT freeze must not call LLM")


def _session(
    rows_by_source: Mapping[str, list[dict]],
    *,
    unavailable_source: str = "",
    error_source: str = "",
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == unavailable_source:
            raise SourceEvidenceUnavailable("controlled unavailable source")
        if source_key == error_source:
            raise SourceEvidenceQueryError("controlled query error")
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
        created_at="2026-09-07T00:00:00+08:00",
        row_reader=read,
        additional_source_keys=_SOURCE_KEYS,
    )


async def _unexpected_executor(**_kwargs):
    raise AssertionError("only surgery_mdt may run in this freeze")


async def _execute_and_project(session):
    """强制经过正式 registry、Binding、公共投影，不伪造 Decision。"""

    contract = next(
        item for item in load_luxian_0609_rule_contracts() if item.rule_id == RULE_ID
    )
    resources = LegacyFamilyExecutionResources(
        wrapper_rules=tuple(
            rule for rule in load_luxian_0609_rules() if rule["rule_id"] == RULE_ID
        ),
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_PresentLlm(),
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
    )[0]
    result = aggregate_luxian_0609_results(
        wrapper_rules=list(resources.wrapper_rules),
        execution_results=[],
        reduced_decisions=(reduced,),
        customer_display_facts=envelope.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]
    return envelope, reduced, result


def _surgery(
    *,
    document_id: str,
    level: str = "四级",
) -> dict:
    return {
        "document_id": document_id,
        "surgery_name": "测试手术",
        "surgical_level": level,
        "surgery_begin_time": "2026-01-02 09:00:00+08",
        "record_time": "2026-01-02 09:00:00",
    }


def _fact_ref_source_keys(session, fact_refs: tuple[str, ...]) -> set[str]:
    source_by_ref: dict[str, str] = {}
    for source_key in _SOURCE_KEYS:
        try:
            document_rows = session.materials.document_rows(
                source_key,
                snapshot=session.snapshot,
            )
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
            continue
        source_by_ref.update(
            {document_ref: source_key for document_ref, _ in document_rows}
        )
    source_by_ref.update(
        {
            observation.snapshot_ref.removeprefix("sha256:"): observation.source_key
            for observation in session.snapshot.observations
        }
    )
    return {source_by_ref[ref] for ref in fact_refs}


def _evidence_coordinates(
    result: Mapping[str, object]
) -> set[tuple[str, str, str, str]]:
    return {
        (
            str(item["source_type"]),
            str(item["source_document_id"]),
            str(item.get("field_path") or ""),
            str(item.get("record_time") or ""),
        )
        for item in result.get("customer_evidence", [])  # type: ignore[union-attr]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "name",
        "rows",
        "unavailable_source",
        "error_source",
        "expected_status",
        "expected_reason",
        "expected_fact_sources",
        "expected_evidence",
        "expected_facts",
    ),
    (
        (
            "四级手术已完成多学科讨论",
            {
                "surgery_record": [_surgery(document_id="SURG-C")],
                "presurg_discussion": [
                    {
                        "document_id": "DISC-C",
                        "record_time": "2026-01-01T09:00:00",
                        "discuss_staff": "骨科甲主任医师、麻醉科乙主任医师",
                        "record_content": "经多学科讨论后一致认为可实施手术。",
                    }
                ],
            },
            "",
            "",
            "compliant",
            "requirement_satisfied",
            {"surgery_record", "presurg_discussion"},
            {
                ("surgery_record", "SURG-C", "", "2026-01-02 09:00:00"),
                (
                    "presurg_discussion",
                    "DISC-C",
                    "discuss_staff",
                    "2026-01-01 09:00:00",
                ),
            },
            {
                "performed_surgery_confirmed": True,
                "procedure_kind": "surgery",
                "effective_surgery_level": "四级",
                "surgery_level_source": "structured_field",
                "mdt_discussion_state": "completed",
                "mdt_assessment_basis": "discuss_staff",
            },
        ),
        (
            "四级手术缺少讨论记录",
            {"surgery_record": [_surgery(document_id="SURG-NC")]},
            "",
            "",
            "non_compliant",
            "requirement_violated",
            {"surgery_record"},
            {("surgery_record", "SURG-NC", "", "2026-01-02 09:00:00")},
            {
                "performed_surgery_confirmed": True,
                "procedure_kind": "surgery",
                "effective_surgery_level": "四级",
                "surgery_level_source": "structured_field",
                "mdt_discussion_state": "missing",
            },
        ),
        (
            "非四级手术不适用",
            {"surgery_record": [_surgery(document_id="SURG-NA", level="三级")]},
            "",
            "",
            "not_applicable",
            "trigger_absent_complete",
            {"surgery_record"},
            {("surgery_record", "SURG-NA", "", "2026-01-02 09:00:00")},
            {
                "performed_surgery_confirmed": True,
                "procedure_kind": "surgery",
                "effective_surgery_level": "三级",
                "surgery_level_source": "structured_field",
            },
        ),
        (
            "讨论来源未接入",
            {"surgery_record": [_surgery(document_id="SURG-DG")]},
            "presurg_discussion",
            "",
            "data_gap",
            "source_unavailable",
            {"surgery_record"},
            {("surgery_record", "SURG-DG", "", "2026-01-02 09:00:00")},
            {
                "performed_surgery_confirmed": True,
                "procedure_kind": "surgery",
                "effective_surgery_level": "四级",
                "surgery_level_source": "structured_field",
                "mdt_discussion_state": "unknown",
            },
        ),
        (
            "手术来源查询异常",
            {},
            "",
            "surgery_record",
            "technical_error",
            "source_query_error",
            set(),
            set(),
            None,
        ),
    ),
    ids=lambda value: value if isinstance(value, str) else None,
)
async def test_surgery_mdt_current_canonical_results_are_frozen(
    name,
    rows,
    unavailable_source,
    error_source,
    expected_status,
    expected_reason,
    expected_fact_sources,
    expected_evidence,
    expected_facts,
):
    session = _session(
        rows,
        unavailable_source=unavailable_source,
        error_source=error_source,
    )
    envelope, reduced, result = await _execute_and_project(session)

    assert envelope.usage_attribution.executor_key == "surgery_mdt", name
    assert envelope.llm_call_count == (1 if expected_status == "compliant" else 0), name
    assert envelope.total_tokens == (132 if expected_status == "compliant" else 0)
    assert (reduced.final_state.value, reduced.reason_code) == (
        expected_status,
        expected_reason,
    ), name
    assert (result["status"], result["reason_code"]) == (
        expected_status,
        expected_reason,
    ), name
    assert (
        _fact_ref_source_keys(session, reduced.fact_refs) == expected_fact_sources
    ), name
    assert _evidence_coordinates(result) == expected_evidence, name
    assert result.get("customer_display_facts") == expected_facts, name


@pytest.mark.asyncio
async def test_surgery_mdt_emergency_lifesaving_exemption_is_publicly_projected():
    session = _session(
        {
            "surgery_record": [_surgery(document_id="SURG-EMERGENCY")],
            "presurg_summary": [
                {
                    "document_id": "SUMMARY-EMERGENCY",
                    "record_content": "本次急诊抢救，为挽救生命立即手术。",
                }
            ],
        }
    )
    envelope, reduced, result = await _execute_and_project(session)

    # 急诊豁免由受控模型确认一次（2026-10-22）。
    assert envelope.llm_call_count == 1 and envelope.total_tokens == 132
    assert (reduced.final_state.value, reduced.reason_code) == (
        "not_applicable",
        "trigger_absent_complete",
    )
    assert (result["status"], result["reason_code"]) == (
        "not_applicable",
        "trigger_absent_complete",
    )
    assert _fact_ref_source_keys(session, reduced.fact_refs) == {
        "surgery_record",
        "presurg_summary",
    }
    assert _evidence_coordinates(result) == {
        ("surgery_record", "SURG-EMERGENCY", "", "2026-01-02 09:00:00"),
        ("presurg_summary", "SUMMARY-EMERGENCY", "record_content", ""),
    }
    assert result["customer_display_facts"] == {
        "performed_surgery_confirmed": True,
        "procedure_kind": "surgery",
        "effective_surgery_level": "四级",
        "surgery_level_source": "structured_field",
        "emergency_surgery_confirmed": True,
        "mdt_exception": "emergency_lifesaving_surgery",
        "mdt_discussion_state": "exempt",
    }


def test_surgery_mdt_aggregator_ownership_is_zero() -> None:
    aggregator_source = (
        Path(__file__).parents[2]
        / "app"
        / "services"
        / "luxian_0609_result_aggregator.py"
    ).read_text(encoding="utf-8")

    assert RULE_ID not in aggregator_source
