from __future__ import annotations

import pytest

from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.customer_renderer import (
    customer_finding_from_controlled_facts,
    render_luxian_0609_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.source_registry import (
    resolve_luxian_0609_decision_support_source_keys,
)
from app.services.luxian_0609.tumor_pathology_result_mapping import (
    safe_tumor_pathology_customer_display_facts,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from test_luxian_0609_native_tumor_pathology_execution import _Client, _wrapper


CREATED_AT = "2026-09-10T12:00:00+08:00"
SNAPSHOT_HASH = "a" * 64
FACT_REF = "b" * 64
C30_SENIOR_TEXT = (
    "今日上级医师查房。辅助检查：2025-08-13电子食管胃十二指肠镜（治疗），"
    "贲门息肉，内镜下钳除术。查房后指出：追踪病检结果，拟明日出院。"
)


def _session(
    *,
    senior_rows: tuple[dict, ...],
    surgery_rows: tuple[dict, ...] = ({"record_content": "术后情况平稳。"},),
    daily_rows: tuple[dict, ...] = ({"record_content": "继续观察病情变化。"},),
):
    rows_by_source = {
        "pathology_exam_master": ({"specimen_name": "胃组织"},),
        "pathology_exam_report": ({
            "diagnosis": "病理诊断资料。",
            "report_datetime": "2025-08-15 09:00:00",
        },),
        "surgery_record": surgery_rows,
        "daily_course_record": daily_rows,
        "senior_course_record": senior_rows,
    }

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-019",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",), selected_rule_ids=("LX0609-019",)
        ),
    )


async def _execute(session, client):
    return await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-019",),
    )


def test_019_declares_senior_course_as_decision_support_source() -> None:
    assert "senior_course_record" in resolve_luxian_0609_decision_support_source_keys(
        ("LX0609-019",)
    )


def test_019_runtime_prompt_accepts_senior_as_course_sampling_evidence() -> None:
    prompt = next(
        item["custom_prompt"]
        for item in load_luxian_0609_rules()
        if item["rule_id"] == "LX0609-019"
    )

    assert (
        "适用文书: daily_course_record、surgery_record、senior_course_record"
        in prompt
    )
    assert "上级医师查房记录属于病程证据" in prompt
    assert "已明确实施的取材情况" in prompt
    assert "任一来源证明" in prompt
    assert "不得把取材部位、数量或送检信息作为额外强制条件" in prompt


@pytest.mark.asyncio
async def test_019_c30_senior_text_enters_single_semantic_call_and_exact_refs() -> None:
    session = _session(senior_rows=({"record_content": C30_SENIOR_TEXT},))
    client = _Client([{"is_compliant": False}])

    result = await _execute(session, client)

    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "[senior_course_record-1]" in client.prompts[0]
    assert "贲门息肉，内镜下钳除术" in client.prompts[0]
    senior_ref = session.materials.document_rows(
        "senior_course_record", snapshot=session.snapshot
    )[0][0]
    assert senior_ref.removeprefix("sha256:") in result.decisions[0].fact_refs
    facts = dict(result.customer_display_facts)["LX0609-019"]
    assert [item["source"] for item in facts["checked_target_sources"]] == [
        "surgery_record",
        "daily_course_record",
        "senior_course_record",
    ]


@pytest.mark.asyncio
async def test_019_senior_documented_sampling_is_programmatic() -> None:
    session = _session(
        senior_rows=({"record_content": "术中切取组织标本，已送病理检查。"},)
    )
    client = _Client([])

    result = await _execute(session, client)

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-019",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    assert reduced.final_state.value == "compliant"
    assert reduced.reason_code == "requirement_satisfied"
    assert result.llm_call_count == 0
    facts = dict(result.customer_display_facts)["LX0609-019"]
    assert facts["documented_sources"] == ["senior_course_record"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    (
        "拟于明日术中取材送病理检查。",
        "病理结果提示慢性炎症，继续随访。",
    ),
)
async def test_019_senior_plan_or_result_only_stays_semantic(content: str) -> None:
    session = _session(senior_rows=({"record_content": content},))
    client = _Client([{"is_compliant": False}])

    result = await _execute(session, client)

    assert result.llm_call_count == 1
    assert content in client.prompts[0]
    assert result.decisions[0].reason_code == "requirement_violated"


def test_019_mapping_accepts_legacy_two_sources_and_new_three_sources() -> None:
    for expected in (
        ("surgery_record", "daily_course_record"),
        ("surgery_record", "daily_course_record", "senior_course_record"),
    ):
        raw = {
            "failure_kind": "pathology_sampling_not_documented",
            "pathology_trigger_sources": ["pathology_exam_master"],
            "checked_target_sources": [
                {"source": source, "state": "present"} for source in expected
            ],
        }
        safe = safe_tumor_pathology_customer_display_facts(
            rule_id="LX0609-019", raw=raw
        )
        assert safe is not None
        assert [item["source"] for item in safe["checked_target_sources"]] == list(
            expected
        )


def test_019_mapping_rejects_senior_documented_with_legacy_checked_sources() -> None:
    assert safe_tumor_pathology_customer_display_facts(
        rule_id="LX0609-019",
        raw={
            "verification_kind": "pathology_sampling_documentation_check",
            "pathology_trigger_sources": ["pathology_exam_master"],
            "checked_target_sources": [
                {"source": "surgery_record", "state": "present"},
                {"source": "daily_course_record", "state": "present"},
            ],
            "documented_sources": ["senior_course_record"],
            "requirement_met": True,
        },
    ) is None


@pytest.mark.parametrize(
    ("checked_sources", "expected_scope"),
    (
        (("surgery_record", "daily_course_record"), "手术记录和病程记录"),
        (
            ("surgery_record", "daily_course_record", "senior_course_record"),
            "手术记录、日常病程记录和上级医师查房记录",
        ),
    ),
)
def test_019_renderer_names_only_checked_target_sources(
    checked_sources: tuple[str, ...], expected_scope: str
) -> None:
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-019",
        facts={
            "failure_kind": "pathology_sampling_not_documented",
            "pathology_trigger_sources": ["pathology_exam_master"],
            "checked_target_sources": [
                {"source": source, "state": "present"} for source in checked_sources
            ],
        },
    )

    assert finding == (
        f"已确认存在病理取材事件；已核对{expected_scope}，均未找到取材情况记录。"
    )


def test_019_trigger_absent_does_not_claim_target_sources_were_checked() -> None:
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-019",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="trigger_absent_complete",
            fact_refs=(FACT_REF,),
            evaluator_version="f09-trigger-absent-copy-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["evidence"] == "现有病理检查资料未发现需要记录取材情况的病理事件。"
    assert "手术记录" not in result["evidence"]
    assert "上级医师查房记录" not in result["evidence"]


@pytest.mark.asyncio
async def test_013_does_not_consume_senior_course_source() -> None:
    session = _session(senior_rows=({"record_content": C30_SENIOR_TEXT},))
    client = _Client([{"is_compliant": True}])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013",),
        wrapper_rules=[_wrapper("LX0609-013")],
        evidence_payload={},
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-013",),
    )

    assert result.llm_call_count == 1
    assert "senior_course_record" not in client.prompts[0]
    senior_ref = session.materials.document_rows(
        "senior_course_record", snapshot=session.snapshot
    )[0][0]
    assert senior_ref.removeprefix("sha256:") not in result.decisions[0].fact_refs
