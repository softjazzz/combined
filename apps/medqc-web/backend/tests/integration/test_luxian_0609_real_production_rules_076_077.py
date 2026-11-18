from __future__ import annotations

from collections.abc import Mapping
from types import SimpleNamespace

import pytest

from app.services.custom_qc_workspace_service import project_customer_safe_result_item
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
from app.services.qc_workspace.canonical_result_store import (
    safe_criterion_results,
    validated_customer_explanation,
)


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
    # 正式执行结果必须继续通过保存前解释校验和客户投影，不能只验聚合成功。
    _facts, criteria = validated_customer_explanation(
        result, rule_id=rule_id, status=result["status"]
    )
    projected = project_customer_safe_result_item(
        result, hmac_key="production-extension-test-key"
    )
    assert projected["status"] == result["status"]
    assert projected["reason_code"] == result["reason_code"]
    assert projected.get("criterion_results", []) == criteria
    if rule_id == "LX0609-04-02-08" and result["status"] in {"compliant", "non_compliant"}:
        assert len(criteria) == 1
        assert criteria[0]["kind"] == "completeness"
        assert criteria[0]["source_fact"] == "death_record.death_time"
        assert criteria[0]["status"] == (
            "failed" if result["status"] == "non_compliant" else "passed"
        )
    return reduced[0], result


@pytest.mark.parametrize("kind", ["unknown_kind", "temporal", "completeness_unapproved"])
def test_unapproved_criterion_kind_cannot_bypass_non_compliant_explanation(kind) -> None:
    item = {
        "rule_id": "LX0609-04-02-08",
        "status": "non_compliant",
        "criterion_results": [
            {
                "criterion_id": "death_time_complete",
                "kind": kind,
                "status": "failed",
                "reason_code": "defect_proven",
                "source_fact": "death_record.death_time",
            }
        ],
    }
    assert safe_criterion_results(item) == []
    with pytest.raises(ValueError):
        validated_customer_explanation(
            item, rule_id="LX0609-04-02-08", status="non_compliant"
        )
    with pytest.raises(ValueError):
        project_customer_safe_result_item(item, hmac_key="production-extension-test-key")


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
        (
            {
                "document_id": "death-076-unreadable",
                "record_content": None,
                "record_time": "2026-09-01 10:20:00",
            },
            CustomerFinalState.DATA_GAP,
        ),
    ],
)
async def test_076_runs_as_a_real_native_rule_and_never_uses_record_time(
    death_row, expected
) -> None:
    session = _session(
        "LX0609-04-02-08",
        {
            "inpat_registration": [{"death_datetime": "2026-09-01 03:45:00"}],
            "death_record": [death_row],
            "discharge_record": [],
        },
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-04-02-08",),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-02-08",),
    )
    reduced, result = _canonical("LX0609-04-02-08", session, execution)

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
        "LX0609-04-02-08",
        {
            "inpat_registration": [{"death_datetime": "2026-09-01 03:45:00"}],
            "death_record": [],
            "discharge_record": [],
        },
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-04-02-08",),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-02-08",),
    )
    reduced, result = _canonical("LX0609-04-02-08", session, execution)

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "eligibility_not_met"
    assert result["status"] == "not_applicable"


@pytest.mark.asyncio
async def test_076_source_unavailable_is_data_gap() -> None:
    session = _session(
        "LX0609-04-02-08",
        {
            "inpat_registration": [{"death_datetime": "2026-09-01 03:45:00"}],
            "discharge_record": [],
        },
        unavailable=frozenset({"death_record"}),
    )
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-04-02-08",),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-02-08",),
    )
    reduced, _result = _canonical("LX0609-04-02-08", session, execution)

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_unavailable"


class _SemanticClient:
    def __init__(self, state: str = "related", *, invalid: bool = False) -> None:
        self.state = state
        self.invalid = invalid
        self.prompts: list[str] = []
        self.calls: list[dict[str, object]] = []

    async def generate(self, prompt: str, **kwargs: object) -> dict[str, object]:
        self.prompts.append(prompt)
        self.calls.append(dict(kwargs))
        content = (
            "不是JSON"
            if self.invalid
            else (
                '{"relation_state":"%s","rationale_code":"%s"}'
                % (
                    self.state,
                    "no_related_item"
                    if self.state == "unrelated"
                    else "insufficient_information"
                    if self.state == "unknown"
                    else "same_clinical_problem",
                )
            )
        )
        if not self.invalid:
            import json

            payload = json.loads(content)
            payload.update({
                "medical_analysis": "第一诊断为急性胆囊炎，需结合腹痛的部位、体征和辅助检查核对鉴别诊断是否解释同一临床问题。",
                "evidence_id": "p01",
            })
            content = json.dumps(payload, ensure_ascii=False)
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
        "first_course_record_diagnosis": [
            {
                "document_id": "first-course-077",
                "diagnosis_type": "初步诊断",
                "diagnosis_no": "1",
                "diagnosis_name": "1.急性胆囊炎；2.慢性胆囊炎",
            }
        ],
        "diagnosis": [],
        "admission_record_diagnosis": [],
    }


@pytest.mark.asyncio
async def test_077_same_document_clinical_background_and_analysis_survive_save_projection() -> None:
    rows = _077_rows()
    rows["first_course_record"][0].update({
        "case_characteristic": "外伤后上肢疼痛，额部包块，伴意识改变。",
        "diagnose_based_on": "影像提示上肢骨折及颞叶可疑挫伤。",
    })
    session = _session("LX0609-01-02-02", rows)
    client = _SemanticClient("unrelated")
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    assert "外伤后上肢疼痛，额部包块，伴意识改变。" in client.prompts[0]
    assert "影像提示上肢骨折及颞叶可疑挫伤。" in client.prompts[0]
    assert "不要求鉴别诊断与第一诊断逐病名、一对一替代" in client.prompts[0]
    assert "仅同次住院或仅共同外伤史" in client.prompts[0]
    _reduced, result = _canonical("LX0609-01-02-02", session, execution)
    analysis = result["criterion_results"][0]["medical_analysis"]
    assert "第一诊断为急性胆囊炎" in analysis
    assert "消化性溃疡穿孔；急性胰腺炎" in analysis


@pytest.mark.asyncio
@pytest.mark.parametrize("analysis,evidence_id", [
    ("", "p01"),
    ("不相关", "p01"),
    ("第一诊断所涉及的临床问题与所列鉴别诊断缺少合理解释关系。", "p99"),
    ("第一诊断所涉及的临床问题与所列鉴别诊断缺少合理解释关系。", ""),
])
async def test_077_unrelated_without_concrete_grounded_explanation_is_not_a_defect(analysis, evidence_id) -> None:
    import json

    class Client:
        async def generate(self, prompt, **kwargs):
            return {"content": json.dumps({
                "relation_state": "unrelated", "rationale_code": "no_related_item",
                "medical_analysis": analysis, "evidence_id": evidence_id,
            }, ensure_ascii=False)}

    session = _session("LX0609-01-02-02", _077_rows())
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None, llm_client=Client(),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    _reduced, result = _canonical("LX0609-01-02-02", session, execution)
    assert result["status"] == "technical_error"
    assert execution.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("evidence_id", "expected"), [
    ("p01", "non_compliant"),
    ("p02", "non_compliant"),
    ("p03", "non_compliant"),
    ("p02,p03", "technical_error"),
    (" p02", "technical_error"),
    ("p99", "technical_error"),
])
async def test_077_selects_one_contiguous_source_passage(evidence_id, expected) -> None:
    import json

    class Client:
        async def generate(self, prompt, **kwargs):
            return {"content": json.dumps({
                "relation_state": "unrelated", "rationale_code": "no_related_item",
                "medical_analysis": "第一诊断对应的临床问题与所列鉴别缺少对应依据，所列鉴别均未解释该问题。",
                "evidence_id": evidence_id,
            }, ensure_ascii=False)}

    rows = _077_rows()
    rows["first_course_record"][0].update({
        "case_characteristic": "患者诉右上腹持续疼痛。", "diagnose_based_on": "入院胆囊影像提示异常。",
    })
    session = _session("LX0609-01-02-02", rows)
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None, llm_client=Client(),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    _reduced, result = _canonical("LX0609-01-02-02", session, execution)
    assert result["status"] == expected
    if expected == "non_compliant":
        assert "原文依据" in result["criterion_results"][0]["medical_analysis"]


@pytest.mark.asyncio
async def test_077_rejection_logs_specific_safe_codes_without_patient_content(caplog) -> None:
    import json
    import logging

    class Client:
        async def generate(self, prompt, **kwargs):
            return {"content": json.dumps({
                "relation_state": "unrelated", "rationale_code": "same_clinical_problem",
                "medical_analysis": "过短说明", "evidence_id": "synthetic-unknown-evidence-id",
            }, ensure_ascii=False)}

    session = _session("LX0609-01-02-02", _077_rows())
    with caplog.at_level(logging.WARNING):
        execution = await execute_luxian_0609_native_course_quality_rules(
            rule_ids=("LX0609-01-02-02",),
            wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
            evidence_payload=None, llm_client=Client(),
            evidence_snapshot=session.snapshot, evidence_materials=session.materials,
            decision_rule_ids=("LX0609-01-02-02",),
        )
    _reduced, result = _canonical("LX0609-01-02-02", session, execution)
    assert result["status"] == "technical_error"
    assert "rationale_state_mismatch" in caplog.text
    assert "analysis_too_short" in caplog.text
    assert "evidence_id_unknown" in caplog.text
    assert "过短说明" not in caplog.text
    assert "synthetic-unknown-evidence-id" not in caplog.text
    assert "急性胆囊炎" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["medical_analysis", "evidence_id"])
async def test_077_model_objects_are_not_silently_converted_to_valid_strings(field) -> None:
    import json

    class Client:
        async def generate(self, prompt, **kwargs):
            payload = {"relation_state": "related", "rationale_code": "same_clinical_problem",
                       "medical_analysis": "说明", "evidence_id": ""}
            payload[field] = {"text": "模型返回了对象"}
            return {"content": json.dumps(payload, ensure_ascii=False)}

    session = _session("LX0609-01-02-02", _077_rows())
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None, llm_client=Client(),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    _reduced, result = _canonical("LX0609-01-02-02", session, execution)
    assert result["status"] == "technical_error"


def test_077_prompt_declares_the_existing_validation_requirements() -> None:
    from app.services.luxian_0609.course_quality.rule_077 import _prompt

    prompt = _prompt(first_diagnosis="合成诊断", full_diagnosis="合成诊断", differential="合成鉴别")
    assert "unrelated 的 medical_analysis 必须为20至240字" in prompt
    assert "related 对应 same_clinical_problem" in prompt
    assert "unrelated 对应 no_related_item" in prompt
    assert "unknown 对应 insufficient_information" in prompt


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
    diagnosis_fields = source_evidence_reader._NATIVE_SOURCE_FIELDS[
        "first_course_record_diagnosis"
    ]
    assert {"document_id", "diagnosis_type", "diagnosis_name"}.issubset(
        diagnosis_fields
    )


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
    rows["first_course_record_diagnosis"][0]["document_id"] = (
        "first-course-077-body-only"
    )
    session = _session("LX0609-01-02-02", rows)
    client = _SemanticClient("related")

    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    reduced, _result = _canonical("LX0609-01-02-02", session, execution)

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert len(client.prompts) == 1
    assert "急性胆囊炎" in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("semantic_state", "expected"),
    [
        ("related", CustomerFinalState.COMPLIANT),
        ("unrelated", CustomerFinalState.NON_COMPLIANT),
        ("unknown", CustomerFinalState.DATA_GAP),
    ],
)
async def test_077_runs_one_controlled_semantic_call_on_the_formal_native_family(
    semantic_state, expected
) -> None:
    session = _session("LX0609-01-02-02", _077_rows())
    client = _SemanticClient(semantic_state)
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    reduced, result = _canonical("LX0609-01-02-02", session, execution)

    assert reduced.final_state is expected
    assert result["status"] == expected.value
    assert execution.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "急性胆囊炎" in client.prompts[0]
    assert "慢性胆囊炎" in client.prompts[0]
    assert client.calls == [
        {"max_completion_tokens": 768, "allow_length_retry": False}
    ]
    assert "消化性溃疡穿孔" in client.prompts[0]
    assert any(
        item.get("source_document_id") == "first-course-077"
        for item in result.get("customer_evidence", [])
    )
    evidence_source_types = {
        item.get("source_type") for item in result.get("customer_evidence", [])
    }
    assert evidence_source_types == {
        "first_course_record",
        "first_course_record_diagnosis",
    }


@pytest.mark.asyncio
async def test_077_rejects_unbound_structured_diagnosis_without_model_call() -> None:
    rows = _077_rows()
    rows["first_course_record_diagnosis"][0]["document_id"] = "another-document"
    session = _session("LX0609-01-02-02", rows)
    client = _SemanticClient("related")

    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    reduced, result = _canonical("LX0609-01-02-02", session, execution)

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "linkage_unresolved"
    assert result["status"] == "data_gap"
    assert execution.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_077_bound_structured_diagnosis_is_authoritative_over_body_fallback() -> None:
    rows = _077_rows()
    rows["first_course_record"][0]["first_diagnosis"] = "正文回退诊断"
    rows["first_course_record"][0]["record_content"] = (
        "初步诊断：正文回退诊断。鉴别诊断：消化性溃疡穿孔。"
    )
    session = _session("LX0609-01-02-02", rows)
    client = _SemanticClient("related")

    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    reduced, _result = _canonical("LX0609-01-02-02", session, execution)

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert "第一诊断：急性胆囊炎" in client.prompts[0]
    # 正文作为背景可以保留，但不能覆盖已绑定结构化第一诊断。
    assert "第一诊断：正文回退诊断" not in client.prompts[0]


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
    session = _session("LX0609-01-02-02", rows)
    client = _SemanticClient()
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    reduced, _result = _canonical("LX0609-01-02-02", session, execution)

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert execution.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_077_invalid_model_output_is_technical_error() -> None:
    session = _session("LX0609-01-02-02", _077_rows())
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None,
        llm_client=_SemanticClient(invalid=True),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    reduced, result = _canonical("LX0609-01-02-02", session, execution)

    assert reduced.final_state is CustomerFinalState.TECHNICAL_ERROR
    assert result["status"] == "technical_error"
    assert reduced.reason_code == "model_invalid_output"
    assert result["criterion_results"][0]["reason_code"] == "model_invalid_output"


@pytest.mark.asyncio
async def test_077_ten_stub_runs_keep_prompt_usage_and_canonical_result_identical() -> None:
    session = _session("LX0609-01-02-02", _077_rows())
    client = _SemanticClient("related")
    outcomes: list[tuple[object, ...]] = []

    for _ in range(10):
        execution = await execute_luxian_0609_native_course_quality_rules(
            rule_ids=("LX0609-01-02-02",),
            wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
            evidence_payload=None,
            llm_client=client,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
            decision_rule_ids=("LX0609-01-02-02",),
        )
        reduced, result = _canonical("LX0609-01-02-02", session, execution)
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
    selected = ("LX0609-04-02-08", "LX0609-01-02-02")
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
        ("extended_document", ("LX0609-04-02-08",)),
        ("course_quality", ("LX0609-01-02-02",)),
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


@pytest.mark.asyncio
async def test_077_capable_client_uses_non_thinking_strict_json_through_privacy_wrapper() -> None:
    from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client

    class CapableClient(_SemanticClient):
        def supports_strict_json_schema(self):
            return True

        async def generate(self, prompt, **kwargs):
            # 旧入口只有提示词约束，模拟 HTTP 成功但正文是说明文字。
            if kwargs.get("enable_thinking") is not False or "response_format" not in kwargs:
                self.calls.append(dict(kwargs))
                return {"content": "需要结合临床背景判断，未输出JSON。"}
            return await super().generate(prompt, **kwargs)

    client = CapableClient()
    session = _session("LX0609-01-02-02", _077_rows())
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None, llm_client=wrap_luxian_0609_llm_client(client),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    reduced, result = _canonical("LX0609-01-02-02", session, execution)
    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert result["status"] == "compliant"
    assert len(client.calls) == 1
    options = client.calls[0]
    assert options["enable_thinking"] is False
    assert options["max_completion_tokens"] == 768
    assert options["allow_length_retry"] is False
    response_format = options["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    schema = response_format["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "relation_state", "rationale_code", "medical_analysis", "evidence_id",
    }


@pytest.mark.asyncio
async def test_077_unconstrained_clients_keep_compatibility_and_single_call() -> None:
    client = _SemanticClient()
    session = _session("LX0609-01-02-02", _077_rows())
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    reduced, _ = _canonical("LX0609-01-02-02", session, execution)
    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert len(client.calls) == 1
    assert "enable_thinking" not in client.calls[0]
    assert "response_format" not in client.calls[0]


@pytest.mark.asyncio
async def test_077_invalid_json_logs_safe_output_shape_not_content(caplog) -> None:
    class Client(_SemanticClient):
        async def generate(self, prompt, **kwargs):
            return {"choices": [{"finish_reason": "length", "message": {
                "content": "PRIVATE_MODEL_PROSE_ONLY", "reasoning_content": "PRIVATE_REASONING",
            }}], "usage": {"completion_tokens": 768}}

    session = _session("LX0609-01-02-02", _077_rows())
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None, llm_client=Client(),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    reduced, _ = _canonical("LX0609-01-02-02", session, execution)
    assert reduced.reason_code == "model_invalid_output"
    assert "json_payload_invalid" in caplog.text
    assert "finish_reason=length" in caplog.text
    assert "completion_tokens=768" in caplog.text
    assert "content_chars=24" in caplog.text
    assert "reasoning_present=True" in caplog.text
    assert "PRIVATE_MODEL" not in caplog.text
    assert "PRIVATE_REASONING" not in caplog.text


@pytest.mark.asyncio
async def test_077_strict_json_and_thinking_override_reach_real_http_payload(monkeypatch) -> None:
    import jsonschema
    import app.services.qc_llm_client as client_module
    from app.services.llm_observability import LLMObservabilityRecorder, NullLLMCallEventStore
    from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
    from app.services.qc_llm_client import SichuanQCLLMClient

    recorded = await _SemanticClient().generate("synthetic input")
    sent = []

    async def fake_post(**kwargs):
        sent.append(kwargs["payload"])
        return {"choices": [{"message": {"content": recorded["content"]}, "finish_reason": "stop"}],
                "usage": recorded["usage"]}

    monkeypatch.setattr(client_module, "safe_post_json", fake_post)
    client = SichuanQCLLMClient(
        config={"api_endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key": "synthetic-not-a-key", "model": "qwen3.8-flash", "provider_code": "alibaba",
                "custom_parameters": {"enable_thinking": True, "thinking_budget": 256}},
        observability_recorder=LLMObservabilityRecorder(store=NullLLMCallEventStore()),
    )
    session = _session("LX0609-01-02-02", _077_rows())
    execution = await execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-01-02-02",),
        wrapper_rules=[get_luxian_0609_rule("LX0609-01-02-02")],
        evidence_payload=None, llm_client=wrap_luxian_0609_llm_client(client),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-01-02-02",),
    )
    reduced, _ = _canonical("LX0609-01-02-02", session, execution)
    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert len(sent) == 1
    assert sent[0]["enable_thinking"] is False
    assert "thinking_budget" not in sent[0]
    assert sent[0]["max_tokens"] == 768
    assert sent[0]["response_format"]["type"] == "json_schema"
    import json
    jsonschema.validate(json.loads(recorded["content"]), sent[0]["response_format"]["json_schema"]["schema"])
    assert client.enable_thinking is True  # 只改此规则调用参数，持久/共享配置不变。
