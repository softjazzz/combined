"""LX0609-074 空证据定位说明的交付合同。

锁定三件事：
1. 「结构化诊断声明成立、病程未记录理由与依据」的确定问题（`non_compliant`
   且 `customer_evidence` 为空）必须在客户结论后追加固定说明，且原有结论句子
   逐字保留；
2. 有证据的 `non_compliant`、`compliant`、`not_applicable` 一律不得带该说明；
3. 文案常量唯一所有者在 `customer_renderer`，Finalizer 只引用，不另写字面量。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.custom_qc_workspace_service import (
    project_customer_safe_result_item,
)
from app.services.luxian_0609.customer_renderer import (
    LX0609_074_NO_EVIDENCE_LOCATION_NOTE,
)
from app.services.luxian_0609.decision_reducer import CustomerFinalState
from app.services.qc_workspace.canonical_result_store import (
    envelope_item_from_rule_result,
)
from tests.unit.test_luxian_0609_native_extended_document_execution import (
    _canonical_extended_result,
    _DiagnosisChangeClient,
    _diagnosis_change_item,
    _evaluate_selected,
)

EMPTY_EVIDENCE_CONCLUSION = "共识别 1 次诊断修正或补充，修改理由和诊断依据未完整记录。"


def _declared_change_only_rows() -> dict:
    """结构化声明成立、病程无理由/依据标记（客户样本的父子表形态）。"""

    return {
        "admission_record": (
            {
                "document_id": "ADMISSION-074",
                "record_content": "入院记录：初步诊断左膝半月板损伤，补充诊断肺结节。",
            },
        ),
        "admission_record_diagnosis": (
            {
                "document_id": "ADMISSION-074",
                "diagnosis_type": "入院诊断",
                "diagnosis_name": "左膝半月板损伤",
            },
            {
                "document_id": "ADMISSION-074",
                "diagnosis_type": "补充诊断",
                "diagnosis_name": "肺结节",
            },
        ),
        "daily_course_record": (
            {
                "document_id": "COURSE-074-PLAIN",
                "record_time": "2025-08-20 10:00:00",
                "record_content": "今日查房，患者一般情况可，继续当前治疗。",
            },
        ),
    }


def _declared_change_with_marked_course_rows() -> dict:
    """结构化声明成立，且病程带理由/依据标记（产生逐条证据定位）。"""

    return {
        "admission_record_diagnosis": (
            {"diagnosis_type": "补充诊断", "diagnosis_name": "细菌性肺炎"},
        ),
        "daily_course_record": (
            {
                "document_id": "COURSE-074-EVIDENCE",
                "record_time": "2025-08-20 10:00:00",
                "record_content": (
                    "结合痰培养结果，细菌性肺炎诊断依据：痰培养提示肺炎克雷伯菌，"
                    "修改理由：抗感染方案需调整。"
                ),
            },
        ),
    }


def _declared_change_without_document_id_rows() -> dict:
    """声明行无可公开文书坐标时，仍保留既有受控说明。"""

    return {
        "admission_record_diagnosis": (
            {
                "diagnosis_type": "补充诊断",
                "diagnosis_name": "肺结节",
            },
        ),
    }


@pytest.mark.asyncio
async def test_074_structured_declaration_projects_its_parent_admission_record() -> None:
    client = _DiagnosisChangeClient()
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-074",), _declared_change_only_rows(), llm_client=client
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert execution.llm_call_count == 0
    assert client.calls == []

    final = _canonical_extended_result(
        rule_id="LX0609-074",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert final["status"] == "non_compliant"
    assert final["reason_code"] == "requirement_violated"
    assert final["customer_evidence"] == [
        {
            "source_type": "admission_record",
            "source_document_id": "ADMISSION-074",
            "field_path": "admission_record_diagnosis.diagnosis_name",
            "evidence_excerpt": "肺结节",
            "excerpt_kind": "字段级依据",
        }
    ]
    assert final["findings"] == EMPTY_EVIDENCE_CONCLUSION
    assert "customer_conclusion" not in final
    assert final["customer_display_facts"] == {
        "verification_kind": "diagnosis_change_documentation_check",
        "diagnosis_change_count": 1,
        "reason_recorded": False,
        "basis_recorded": False,
    }


@pytest.mark.asyncio
async def test_074_empty_evidence_explanation_reaches_customer_delivery_path() -> None:
    """说明必须经 Envelope 与客户投影到达 customer_conclusion / conclusion。"""

    client = _DiagnosisChangeClient()
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-074",),
        _declared_change_without_document_id_rows(),
        llm_client=client,
    )
    final = _canonical_extended_result(
        rule_id="LX0609-074",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    envelope_item = envelope_item_from_rule_result({**final, "record_id": "PRIVATE-074"})
    projected = project_customer_safe_result_item(envelope_item, hmac_key="unit-test-key")

    assert projected["status"] == "non_compliant"
    assert projected["reason_code"] == "requirement_violated"
    assert LX0609_074_NO_EVIDENCE_LOCATION_NOTE in projected["customer_conclusion"]
    assert projected["conclusion"] == projected["customer_conclusion"]
    assert projected["findings"] == projected["customer_conclusion"]
    dumped = projected["customer_conclusion"]
    assert dumped.startswith(EMPTY_EVIDENCE_CONCLUSION)
    assert "PRIVATE-074" not in str(projected)


@pytest.mark.asyncio
async def test_074_non_compliant_with_evidence_does_not_get_explanation() -> None:
    client = _DiagnosisChangeClient()
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-074",), _declared_change_with_marked_course_rows(), llm_client=client
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert execution.llm_call_count == 0

    final = _canonical_extended_result(
        rule_id="LX0609-074",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert final["status"] == "non_compliant"
    assert final.get("customer_evidence"), "该分支必须产生逐条证据定位"
    assert "customer_conclusion" not in final
    assert LX0609_074_NO_EVIDENCE_LOCATION_NOTE not in str(final.get("findings") or "")


@pytest.mark.asyncio
async def test_074_compliant_does_not_get_explanation() -> None:
    course_text = (
        "结合痰培养结果，修正诊断为细菌性肺炎。诊断依据：痰培养提示肺炎克雷伯菌。"
    )
    client = _DiagnosisChangeClient(
        _diagnosis_change_item(
            "doc_01",
            reason_quote="结合痰培养结果，修正诊断为细菌性肺炎",
            basis_quote="诊断依据：痰培养提示肺炎克雷伯菌",
        )
    )
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-074",),
        {
            "admission_record_diagnosis": (
                {"diagnosis_type": "修正诊断", "diagnosis_name": "细菌性肺炎"},
            ),
            "daily_course_record": (
                {"record_time": "2025-08-20 10:00:00", "record_content": course_text},
            ),
        },
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT

    final = _canonical_extended_result(
        rule_id="LX0609-074",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert final["status"] == "compliant"
    assert "customer_conclusion" not in final


@pytest.mark.asyncio
async def test_074_not_applicable_does_not_get_explanation() -> None:
    client = _DiagnosisChangeClient()
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-074",),
        {
            "admission_record_diagnosis": (
                {"diagnosis_type": "入院诊断", "diagnosis_name": "肺部感染"},
                {"diagnosis_type": "修正诊断", "diagnosis_name": "   "},
            ),
            "daily_course_record": (
                {
                    "document_id": "COURSE-074-NA",
                    "record_time": "2025-08-20 10:00:00",
                    "record_content": "病情平稳，继续当前治疗。",
                },
            ),
        },
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.NOT_APPLICABLE

    final = _canonical_extended_result(
        rule_id="LX0609-074",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert final["status"] == "not_applicable"
    assert "customer_conclusion" not in final


def test_074_explanation_copy_is_owned_by_customer_renderer_only() -> None:
    backend = Path(__file__).resolve().parents[2]
    renderer_source = (
        backend / "app/services/luxian_0609/customer_renderer.py"
    ).read_text(encoding="utf-8")
    finalizer_source = (
        backend / "app/services/luxian_0609/canonical_result_finalizer.py"
    ).read_text(encoding="utf-8")

    assert "LX0609_074_NO_EVIDENCE_LOCATION_NOTE" in renderer_source
    assert "LX0609_074_NO_EVIDENCE_LOCATION_NOTE" in finalizer_source
    # Finalizer 不得另写一份客户文案字面量。
    assert "不提供逐条证据定位" not in finalizer_source
    assert "结构化诊断声明作出判定" not in finalizer_source
