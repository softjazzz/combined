"""024 院方“病种—术式”目录门控（院方口径 2026-10-11）。"""

from __future__ import annotations

import pytest

from app.services.luxian_0609.surgery_lymph_node_catalog import (
    colon_pathology_missing_items,
    evaluate_lymph_node_catalog_gate,
)


def _gate(
    *,
    code: str,
    name: str = "手术",
    process: str = "",
    diagnosis: dict[str, str] | None = None,
    pathology: str = "",
    discharge: str = "",
):
    return evaluate_lymph_node_catalog_gate(
        surgery_rows=({"surgery_code": code, "surgery_name": name, "surgery_process": process},),
        mr_surgery_rows=(),
        diagnosis_rows=(diagnosis or {},),
        pathology_rows=({"diagnosis": pathology},) if pathology else (),
        discharge_rows=({"record_content": discharge},) if discharge else (),
    )


@pytest.mark.parametrize(
    ("code", "diagnosis", "site"),
    (
        ("32.4100", {"diagnosis_code": "C34.100"}, "lung"),
        ("32.2901", {"diagnosis_name": "右肺上叶腺癌"}, "lung"),
        ("85.4300", {"diagnosis_name": "左乳腺浸润性导管癌"}, "breast"),
    ),
)
def test_lung_and_breast_target_combinations_apply(code, diagnosis, site) -> None:
    gate = _gate(code=code, diagnosis=diagnosis)

    assert gate.state == "applicable"
    assert gate.sites == (site,)
    assert gate.colon_pathology_required is False


def test_metastatic_lung_lesion_is_not_primary_lung_cancer() -> None:
    gate = _gate(code="32.4100", diagnosis={"diagnosis_name": "肺转移癌"})

    assert (gate.state, gate.reason_code) == ("not_applicable", "catalog_combination_absent")


def test_malignant_surgery_outside_catalog_is_not_applicable() -> None:
    gate = _gate(code="06.4x00", diagnosis={"diagnosis_code": "C73.x00"})

    assert (gate.state, gate.reason_code) == ("not_applicable", "catalog_combination_absent")


def test_missing_procedure_code_is_data_gap() -> None:
    gate = _gate(code="", diagnosis={"diagnosis_code": "C34.100"})

    assert (gate.state, gate.reason_code) == ("data_gap", "surgery_code_unavailable")


@pytest.mark.parametrize(
    ("code", "name", "process", "expected"),
    (
        ("43.7x01", "腹腔镜下根治性远端胃大部切除术", "", "applicable"),
        ("43.4105", "内镜下胃息肉切除术", "", "not_applicable"),
        ("43.9901", "姑息性全胃切除术", "", "not_applicable"),
        ("43.7x01", "远端胃大部切除术", "行胃癌根治术，D2淋巴结清扫", "applicable"),
        ("43.7x01", "远端胃大部切除术", "", "data_gap"),
    ),
)
def test_gastric_only_radical_surgery_applies(code, name, process, expected) -> None:
    gate = _gate(code=code, name=name, process=process, diagnosis={"diagnosis_code": "C16.300"})

    assert gate.state == expected
    if expected == "data_gap":
        assert gate.reason_code == "gastric_radical_intent_unresolved"


@pytest.mark.parametrize(
    ("pathology", "discharge", "expected"),
    (
        ("乙状结肠腺癌，pT3N1a，淋巴结 2/15", "", "applicable"),
        ("", "术后分期 T2N0M0", "applicable"),
        ("结肠腺癌，pT1N0", "", "not_applicable"),
        ("", "分期 T3N1M1", "not_applicable"),
        ("结肠腺癌，未见分期", "", "data_gap"),
    ),
)
def test_colon_requires_t2_4_n0_2_m0_stage(pathology, discharge, expected) -> None:
    gate = _gate(
        code="45.7301",
        diagnosis={"diagnosis_code": "C18.700"},
        pathology=pathology,
        discharge=discharge,
    )

    assert gate.state == expected
    if expected == "applicable":
        assert gate.colon_pathology_required is True
    if expected == "data_gap":
        assert gate.reason_code == "colon_stage_unavailable"


@pytest.mark.parametrize(
    ("text", "missing"),
    (
        ("肠周淋巴结 2/15 见癌转移，pT3N1a", ()),
        ("共检出淋巴结十二枚，未见转移；ypT2N0", ()),
        ("肠周淋巴结 0/12；分期待定", ("pathologic_stage",)),
        ("结肠腺癌，pT3N0", ("lymph_node_count",)),
        ("结肠腺癌，中分化", ("lymph_node_count", "pathologic_stage")),
    ),
)
def test_colon_pathology_items(text, missing) -> None:
    assert colon_pathology_missing_items(({"diagnosis": text},)) == missing


# ---- 执行链路 ----

from app.services.luxian_0609 import native_surgery_gate_execution as surgery  # noqa: E402
from app.services.luxian_0609.customer_renderer import (  # noqa: E402
    customer_finding_from_controlled_facts,
)
from app.services.luxian_0609.decision_binding import (  # noqa: E402
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (  # noqa: E402
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows  # noqa: E402
from app.services.luxian_0609.surgery_gate_result_mapping import (  # noqa: E402
    safe_surgery_gate_customer_display_facts,
)

_RULE = "LX0609-04-02-03"


async def _execute(rows_by_source):
    def reader(**kwargs):
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=rows_by_source.get(kwargs["source_key"], ()),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(_RULE,),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=reader,
    )
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=(_RULE,),
        decision_rule_ids=(_RULE,),
        wrapper_rules=[],
        evidence_payload={},
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
        expected_rule_ids=(_RULE,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    return result, reduced[0]


def _colon_surgery_row():
    return {
        "document_id": "colon-surgery-1",
        "surgery_begin_time": "2026-01-01 08:00:00+08",
        "surgery_name": "腹腔镜下乙状结肠癌根治术",
        "surgery_code": "45.7601",
        "surgery_process": "术中清扫253组淋巴结，标本送检。",
    }


@pytest.mark.asyncio
async def test_colon_target_with_pathology_missing_stage_is_non_compliant() -> None:
    result, reduced = await _execute({
        "surgery_record": (_colon_surgery_row(),),
        "diagnosis": ({"diagnosis_name": "乙状结肠腺癌", "diagnosis_code": "C18.700"},),
        "discharge_record": ({"record_content": "术后分期 T3N0M0。"},),
        "pathology_exam_report": ({"document_id": "path-1", "diagnosis": "乙状结肠腺癌，肠周淋巴结 0/14。"},),
    })

    assert reduced.final_state.value == "non_compliant"
    raw = dict(result.customer_display_facts)[_RULE]
    safe = safe_surgery_gate_customer_display_facts(rule_id=_RULE, raw=raw)
    assert safe["missing_items"] == ["pathologic_stage"]
    assert customer_finding_from_controlled_facts(rule_id=_RULE, facts=safe) == (
        "结肠癌目标手术的病理报告未记录：pTNM/ypTNM 分期。"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_colon_target_with_complete_pathology_is_compliant() -> None:
    _result, reduced = await _execute({
        "surgery_record": (_colon_surgery_row(),),
        "diagnosis": ({"diagnosis_name": "乙状结肠腺癌", "diagnosis_code": "C18.700"},),
        "pathology_exam_report": ({"document_id": "path-1", "diagnosis": "乙状结肠腺癌，pT3N0，肠周淋巴结 0/14。"},),
    })

    assert reduced.final_state.value == "compliant"


@pytest.mark.asyncio
async def test_malignant_surgery_outside_catalog_reports_eligibility_not_met() -> None:
    result, reduced = await _execute({
        "surgery_record": ({
            "document_id": "thyroid-1",
            "surgery_begin_time": "2026-01-01 08:00:00+08",
            "surgery_name": "甲状腺癌根治术",
            "surgery_code": "06.4x00",
            "surgery_process": "术中清扫中央区淋巴结。",
        },),
        "diagnosis": ({"diagnosis_name": "甲状腺乳头状癌", "diagnosis_code": "C73.x00"},),
    })

    assert reduced.final_state.value == "not_applicable"
    assert result.decisions[0].reason_code == "eligibility_not_met"


def test_procedures_outside_catalog_short_circuit() -> None:
    from app.services.luxian_0609.surgery_lymph_node_catalog import procedures_outside_catalog

    assert procedures_outside_catalog(
        surgery_rows=({"surgery_code": "51.2300"},), mr_surgery_rows=({"surgery_code": "51.2300"},),
    )
    # 正式手术记录缺编码时以首页编码为准。
    assert procedures_outside_catalog(
        surgery_rows=({"surgery_name": "输尿管镜检查"},), mr_surgery_rows=({"surgery_code": "56.3100"},),
    )
    assert not procedures_outside_catalog(
        surgery_rows=({"surgery_code": "32.4100"},), mr_surgery_rows=(),
    )
    assert not procedures_outside_catalog(surgery_rows=({"surgery_name": "手术"},), mr_surgery_rows=())
