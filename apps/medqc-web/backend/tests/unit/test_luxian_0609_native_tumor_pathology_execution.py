from __future__ import annotations

import json

import pytest

from app.services.luxian_0609 import native_tumor_pathology_execution as tumor


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


def _payload(*, facts: list[dict] | None = None, **overrides: list[dict]) -> dict:
    documents = {
        "pathology_exam_master": [
            {"specimen_name": "手术标本", "record_content": "病理送检申请资料。"}
        ],
        "pathology_exam_report": [
            {
                "diagnosis": "病理诊断资料。",
                "report_datetime": "2026-04-26 10:00:00",
            }
        ],
        "surgery_record": [{"content": "手术记录中包含本次手术经过。"}],
        "daily_course_record": [{"content": "病程记录中已记录病理结果与处理计划。"}],
        "diagnosis": [{"diagnosis_code": "C18.9"}],
        "inpat_drug_order": [
            {"generic_name": "受控化疗药物", "single_dose": "1", "drug_apply_method": "静滴"}
        ],
        "discharge_record": [{"content": "出院记录中包含后续肿瘤治疗计划。"}],
    }
    documents.update(overrides)
    return {
        "timeline_facts": list(facts or []),
        "programmatic_timeline": {"documents": documents},
    }


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        content = (
            output
            if isinstance(output, str)
            else json.dumps(output, ensure_ascii=False)
        )
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
            },
            "_api_time": 0.2,
        }


@pytest.mark.asyncio
async def test_pathology_source_triggers_013_019_once_each_and_keeps_customer_order():
    client = _Client([{"is_compliant": True}, {"is_compliant": False}])

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019", "LX0609-013"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert [item["rule_id"] for item in result.results] == ["LX0609-013", "LX0609-019"]
    assert [item["status"] for item in result.results] == ["compliant", "non_compliant"]
    assert result.llm_call_count == 2
    assert result.total_tokens == 220
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_no_pathology_rows_returns_not_applicable_without_model(monkeypatch):
    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", lambda **_: [])
    client = _Client([])

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(pathology_exam_master=[], pathology_exam_report=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "not_applicable",
        "not_applicable",
    ]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_pathology_report_without_result_is_data_gap_but_sampling_rule_can_run():
    client = _Client([{"is_compliant": True}])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(pathology_exam_report=[{"report_status": "完成"}]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "compliant"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "report_row",
    [
        {"report_status": "完成"},
        {"eye_findings": "肉眼所见材料", "microscope_findings": "镜下所见材料"},
        {"diagnosis": "病理诊断资料。"},
        {"report_datetime": "2026-04-26 10:00:00"},
        {"diagnosis": "病理诊断资料。", "report_datetime": "待补录"},
        {
            "record_content": "本报告尚在审核中，最终病理诊断待补充，请结合后续正式报告。",
            "report_datetime": "2026-04-26 10:00:00",
        },
        {"diagnosis": "病理诊断资料。", "report_datetime": "2026-04-26"},
        {"diagnosis": "待诊断", "report_datetime": "2026-04-26 10:00:00"},
        {"diagnosis": "诊断待定", "report_datetime": "2026-04-26 10:00:00"},
        {
            "record_content": "病理结果待定。",
            "report_datetime": "2026-04-26 10:00:00",
        },
        {
            "record_content": "病理诊断待完善。",
            "report_datetime": "2026-04-26 10:00:00",
        },
    ],
)
async def test_013_requires_final_result_and_report_time_before_model(
    report_row: dict,
):
    client = _Client([])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013",),
        wrapper_rules=[_wrapper("LX0609-013")],
        evidence_payload=_payload(pathology_exam_report=[report_row]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert (
        result.results[0]["metadata"]["reason_code"]
        == "pathology_final_result_or_report_time_unavailable"
    )
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_key", "content"),
    [
        ("surgery_record", "切除阑尾后向家属展示，标本送病检。"),
        ("surgery_record", "术中取材并送病理检查。"),
        ("daily_course_record", "术中切取组织标本，已送病理检查。"),
    ],
)
async def test_019_documented_sampling_is_programmatic_compliant_without_model(
    source_key: str, content: str
):
    client = _Client([])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(**{source_key: [{"content": content}]}),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.results[0]["metadata"]["reason_code"] == "pathology_sampling_recorded"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        "拟将标本送病理检查。",
        "建议术中取材送病检。",
        "未送病理，待术后结合结果。",
        "手术记录未记录术中取材及送检情况。",
        "术中取材：    ",
        "标本送检情况：无。",
        "切除阑尾后，家属拒绝标本送病检。",
        "切除阑尾，标本不送病检。",
        "标本送检已取消。",
        "暂缓取材送病理检查。",
        "已填写标本送检申请资料。",
        "病理送检单已打印。",
        "标本送检单已打印。",
        "送检。",
    ],
)
async def test_019_prospective_negative_or_empty_sampling_text_does_not_short_circuit(
    content: str,
):
    client = _Client([{"is_compliant": False}])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(surgery_record=[{"content": content}]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "non_compliant"
    assert result.results[0]["metadata"]["executor_type"] == "llm"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        "术前未取材，术中切取阑尾标本并送病检。",
        "拟术中取材，实际术中取材并送病理检查。",
    ],
)
async def test_019_local_completed_action_is_not_blocked_by_earlier_negative_clause(
    content: str,
):
    client = _Client([])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-019",),
        wrapper_rules=[_wrapper("LX0609-019")],
        evidence_payload=_payload(surgery_record=[{"content": content}]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "compliant"
    assert result.results[0]["metadata"]["executor_type"] == "program"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_019_sampling_override_does_not_change_013_or_its_model_call():
    client = _Client([{"is_compliant": False}])
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload=_payload(
            surgery_record=[{"content": "术中切取病灶标本并送病理检查。"}]
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "compliant",
    ]
    assert [item["metadata"]["executor_type"] for item in result.results] == [
        "llm",
        "program",
    ]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_malignant_and_chemo_facts_gate_026_027_without_keyword_fallback():
    facts = [
        {
            "fact_type": "current_visit_chemotherapy_order",
            "state": "present",
            "source_key": "inpat_drug_order",
            "current_visit_bound": True,
        }
    ]
    client = _Client([{"is_compliant": False}, {"is_compliant": True}])

    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026", "LX0609-027"),
        wrapper_rules=[_wrapper("LX0609-026"), _wrapper("LX0609-027")],
        evidence_payload=_payload(facts=facts),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "compliant"]
    assert result.llm_call_count == 2

    no_strong_fact = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026",),
        wrapper_rules=[_wrapper("LX0609-026")],
        evidence_payload=_payload(
            facts=[],
            daily_course_record=[{"content": "病程自由文本仅写拟行化疗。"}],
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert no_strong_fact.results[0]["status"] == "data_gap"
    assert no_strong_fact.llm_call_count == 0


@pytest.mark.asyncio
async def test_nonmalignant_diagnosis_is_not_applicable_and_source_error_is_sanitized(
    monkeypatch,
):
    nonmalignant = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-026", "LX0609-027"),
        wrapper_rules=[_wrapper("LX0609-026"), _wrapper("LX0609-027")],
        evidence_payload=_payload(diagnosis=[{"diagnosis_code": "K35.9"}]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert [item["status"] for item in nonmalignant.results] == [
        "not_applicable",
        "not_applicable",
    ]

    uncoded = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-027",),
        wrapper_rules=[_wrapper("LX0609-027")],
        evidence_payload=_payload(diagnosis=[{"diagnosis_type": "出院诊断"}]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert uncoded.results[0]["status"] == "data_gap"

    secret = "Bearer_secret_13800138000"

    def _failed_reader(**_: object) -> list[dict]:
        raise RuntimeError(secret)

    monkeypatch.setattr(tumor, "read_luxian_0609_native_source_rows", _failed_reader)
    failed = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=tumor.TUMOR_PATHOLOGY_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in tumor.TUMOR_PATHOLOGY_RULE_IDS],
        evidence_payload=_payload(
            pathology_exam_master=[],
            pathology_exam_report=[],
            diagnosis=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert [item["status"] for item in failed.results] == ["data_gap"] * 4
    assert secret not in repr(failed)
