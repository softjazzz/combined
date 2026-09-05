from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import execution as execution_module
from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.execution import (
    aggregate_luxian_0609_orchestrated_results,
    prepare_luxian_0609_execution,
)
from app.services.luxian_0609.native_course_quality_execution import (
    execute_luxian_0609_native_course_quality_rules,
)
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule


def _session(
    rule_id: str,
    rows_by_source: Mapping[str, list[Mapping[str, object]]],
    *,
    unavailable: frozenset[str] = frozenset(),
):
    def read_rows(**kwargs: object) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        if source_key in unavailable:
            raise SourceEvidenceUnavailable(source_key)
        rows = rows_by_source.get(source_key, [])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,),
        institute_id="production-extension-institute",
        patient_id="production-extension-patient",
        visit_id="production-extension-visit",
        source_schema=None,
        created_at="2026-09-05T10:00:00+08:00",
        row_reader=read_rows,
    )


def _canonical(rule_id: str, session, execution):
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=(rule_id,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    wrapper = get_luxian_0609_rule(rule_id)
    assert wrapper is not None
    result = aggregate_luxian_0609_results(
        wrapper_rules=[wrapper],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]
    return reduced[0], result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("death_row", "expected"),
    [
        (
            {
                "document_id": "death-076-field",
                "document_title": "死亡记录",
                "death_time": "2026-09-01 03:45:00",
                "record_time": "2026-09-01 10:20:00",
            },
            CustomerFinalState.COMPLIANT,
        ),
        (
            {
                "document_id": "death-076-body",
                "document_title": "死亡记录",
                "record_content": "患者于2026年09月01日 03时45分宣告临床死亡。",
                "record_time": "2026-09-01 10:20:00",
            },
            CustomerFinalState.COMPLIANT,
        ),
        (
            {
                "document_id": "death-076-missing",
                "document_title": "死亡记录",
                "record_content": "经抢救无效死亡。",
                "record_time": "2026-09-01 10:20:00",
            },
            CustomerFinalState.NON_COMPLIANT,
        ),
    ],
)
async def test_076_runs_as_a_real_native_rule_and_never_uses_record_time(
    death_row, expected
) -> None:
    session = _session(
        "LX0609-076",
        {
            "inpat_registration": [{"death_datetime": "2026-09-01 03:45:00"}],
            "death_record": [death_row],
            "discharge_record": [],
        },
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-076",),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-076",),
    )
    reduced, result = _canonical("LX0609-076", session, execution)

    assert reduced.final_state is expected
    assert result["status"] == expected.value
    assert execution.llm_call_count == 0
    assert any(
        item.get("source_document_id") == death_row["document_id"]
        for item in result.get("customer_evidence", [])
    )


@pytest.mark.asyncio
async def test_076_does_not_duplicate_060_when_death_record_is_absent() -> None:
    session = _session(
        "LX0609-076",
        {
            "inpat_registration": [{"death_datetime": "2026-09-01 03:45:00"}],
            "death_record": [],
            "discharge_record": [],
        },
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-076",),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-076",),
    )
    reduced, result = _canonical("LX0609-076", session, execution)

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "eligibility_not_met"
    assert result["status"] == "not_applicable"


@pytest.mark.asyncio
async def test_076_source_unavailable_is_data_gap() -> None:
    session = _session(
        "LX0609-076",
        {
            "inpat_registration": [{"death_datetime": "2026-09-01 03:45:00"}],
            "discharge_record": [],
        },
        unavailable=frozenset({"death_record"}),
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-076",),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-076",),
    )
    reduced, _result = _canonical("LX0609-076", session, execution)

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_unavailable"


class _SemanticClient:
    def __init__(self, state: str = "related", *, invalid: bool = False) -> None:
        self.state = state
        self.invalid = invalid
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_kwargs: object) -> dict[str, object]:
        self.prompts.append(prompt)
        content = (
            "不是JSON"
            if self.invalid
            else (
                '{"relation_state":"%s","rationale_code":"%s"}'
                % (
                    self.state,
                    "obvious_unrelated_item"
                    if self.state == "unrelated"
                    else "insufficient_semantic_context"
                    if self.state == "unknown"
                    else "same_clinical_problem",
                )
            )
        )
        return {
            "content": content,
            "usage": {"prompt_tokens": 50, "completion_tokens": 8, "total_tokens": 58},
            "_api_time": 0.1,
        }


def _077_rows() -> dict[str, list[Mapping[str, object]]]:
    return {
        "first_course_record": [
            {
                "document_id": "first-course-077",
                "document_title": "首次病程记录",
                "record_time": "2026-09-01 09:00:00",
                "first_diagnosis": "急性胆囊炎",
                "differential_diagnosis": "消化性溃疡穿孔；急性胰腺炎",
                "record_content": "初步诊断：急性胆囊炎。鉴别诊断：消化性溃疡穿孔；急性胰腺炎。",
            }
        ],
        "diagnosis": [],
        "admission_record_diagnosis": [],
    }


def test_077_required_structured_fields_survive_the_production_source_projection() -> None:
    from app.services.luxian_0609 import source_evidence_reader

    approved = source_evidence_reader._NATIVE_SOURCE_FIELDS["first_course_record"]
    assert {  # 真实数据库读取只会选择这份白名单内实际存在的列。
        "first_diagnosis",
        "primary_diagnosis",
        "initial_diagnosis",
        "differential_diagnosis",
    }.issubset(approved)
    assert "unrelated_private_field" not in approved


@pytest.mark.asyncio
async def test_077_can_read_first_diagnosis_from_the_bounded_first_course_body() -> None:
    rows = _077_rows()
    rows["first_course_record"][0] = {
        "document_id": "first-course-077-body-only",
        "document_title": "首次病程记录",
        "record_time": "2026-09-01 09:00:00",
        "record_content": (
            "初步诊断：1.急性胆囊炎。\n"
            "鉴别诊断：消化性溃疡穿孔；急性胰腺炎。\n"
            "诊疗计划：完善检查。"
        ),
    }
    session = _session("LX0609-077", rows)
    client = _SemanticClient("related")

    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-077",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-077")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-077",),
    )
    reduced, _result = _canonical("LX0609-077", session, execution)

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert len(client.prompts) == 1
    assert "急性胆囊炎" in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("semantic_state", "expected"),
    [
        ("related", CustomerFinalState.COMPLIANT),
        ("unrelated", CustomerFinalState.NON_COMPLIANT),
        ("unknown", CustomerFinalState.EVALUATION_UNKNOWN),
    ],
)
async def test_077_runs_one_controlled_semantic_call_on_the_formal_native_family(
    semantic_state, expected
) -> None:
    session = _session("LX0609-077", _077_rows())
    client = _SemanticClient(semantic_state)
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-077",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-077")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-077",),
    )
    reduced, result = _canonical("LX0609-077", session, execution)

    assert reduced.final_state is expected
    assert result["status"] == expected.value.replace("evaluation_unknown", "uncertain")
    assert execution.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "急性胆囊炎" in client.prompts[0]
    assert "消化性溃疡穿孔" in client.prompts[0]
    assert any(
        item.get("source_document_id") == "first-course-077"
        for item in result.get("customer_evidence", [])
    )


@pytest.mark.asyncio
async def test_077_missing_inputs_are_data_gap_without_calling_model() -> None:
    rows = _077_rows()
    rows["first_course_record"] = [
        {
            "document_id": "first-course-077-missing",
            "first_diagnosis": "急性胆囊炎",
            "record_content": "初步诊断：急性胆囊炎。",
        }
    ]
    session = _session("LX0609-077", rows)
    client = _SemanticClient()
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-077",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-077")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-077",),
    )
    reduced, _result = _canonical("LX0609-077", session, execution)

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert execution.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_077_invalid_model_output_is_technical_error() -> None:
    session = _session("LX0609-077", _077_rows())
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-077",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-077")],
        evidence_payload=None,
        llm_client=_SemanticClient(invalid=True),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-077",),
    )
    reduced, result = _canonical("LX0609-077", session, execution)

    assert reduced.final_state is CustomerFinalState.TECHNICAL_ERROR
    assert result["status"] == "technical_error"
    assert reduced.reason_code == "model_invalid_output"


@pytest.mark.asyncio
async def test_077_ten_stub_runs_keep_prompt_usage_and_canonical_result_identical() -> None:
    session = _session("LX0609-077", _077_rows())
    client = _SemanticClient("related")
    outcomes: list[tuple[object, ...]] = []

    for _ in range(10):
        execution = await execute_luxian_0609_native_course_quality_rules(
            rule_ids=("LX0609-077",),
            wrapper_rules=[get_luxian_0609_rule("LX0609-077")],
            evidence_payload=None,
            llm_client=client,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
            decision_rule_ids=("LX0609-077",),
        )
        reduced, result = _canonical("LX0609-077", session, execution)
        outcomes.append(
            (
                reduced.final_state,
                reduced.reason_code,
                result["status"],
                execution.llm_call_count,
                execution.prompt_tokens,
                execution.completion_tokens,
                execution.total_tokens,
            )
        )

    assert len(client.prompts) == 10
    assert len(set(client.prompts)) == 1
    assert len(set(outcomes)) == 1
    assert outcomes[0] == (
        CustomerFinalState.COMPLIANT,
        "requirement_satisfied",
        "compliant",
        1,
        50,
        8,
        58,
    )


def _production_settings() -> SimpleNamespace:
    return SimpleNamespace(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_NATIVE_CONSULTATION_ENABLED=True,
        LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED=True,
        LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED=True,
        LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED=True,
        LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED=True,
        LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED=True,
        LUXIAN_0609_NATIVE_MDT_040_ENABLED=True,
        LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED=True,
        LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
    )


@pytest.mark.asyncio
async def test_076_077_use_the_formal_production_plan_without_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ("LX0609-076", "LX0609-077")
    rows = _077_rows()
    rows.update(
        {
            "inpat_registration": [{"death_datetime": "2026-09-01 03:45:00"}],
            "death_record": [
                {
                    "document_id": "death-076-production-plan",
                    "document_title": "死亡记录",
                    "death_time": "2026-09-01 03:45:00",
                    "record_time": "2026-09-01 10:20:00",
                }
            ],
            "discharge_record": [],
        }
    )

    def read_rows(**kwargs: object) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="production-extension-institute",
        patient_id="production-extension-patient",
        visit_id="production-extension-visit",
        source_schema=None,
        created_at="2026-09-05T10:00:00+08:00",
        row_reader=read_rows,
    )

    def build_session(**kwargs: object):
        assert tuple(kwargs["selected_rule_ids"]) == selected
        return session

    monkeypatch.setattr(
        execution_module,
        "build_luxian_0609_evidence_read_session",
        build_session,
    )
    client = _SemanticClient("related")
    executable, context = await prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[],
        visit_id="production-extension-visit",
        medical_text="",
        evidence_payload=None,
        llm_client=client,
        settings=_production_settings(),
        institute_id="production-extension-institute",
        patient_id="production-extension-patient",
        selected_customer_rule_ids=selected,
    )

    assert executable == []
    assert context.unified_engine_used is True
    assert context.package_plan is not None
    assert context.package_plan.native_executor_batches == (
        ("extended_document", ("LX0609-076",)),
        ("course_quality", ("LX0609-077",)),
    )
    assert context.package_plan.compatibility_rule_ids == ()
    assert context.package_plan.compatibility_execution_rule_ids == ()
    assert context.legacy_wrapper_rules == []
    assert [item.rule_id for item in context.reduced_decisions] == list(selected)
    assert context.native_llm_call_count == 1
    assert len(client.prompts) == 1

    orchestrated: dict[str, object] = {
        "results": [],
        "total_tokens": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
    }
    aggregate_luxian_0609_orchestrated_results(
        orchestrated=orchestrated,
        context=context,
        visit_id="production-extension-visit",
        model_name="controlled-production-extension",
        evidence_payload=None,
    )
    results = orchestrated["results"]
    assert isinstance(results, list)
    assert [item["rule_id"] for item in results] == list(selected)
    assert [item["status"] for item in results] == ["compliant", "compliant"]
    assert all(item.get("customer_evidence") for item in results)
