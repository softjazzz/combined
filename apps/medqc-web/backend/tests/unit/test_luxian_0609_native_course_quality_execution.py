from __future__ import annotations

import json

import pytest

from app.services.luxian_0609 import native_course_quality_execution as course


def _row(content: str, record_time: str = "2026-06-01 09:00:00") -> dict:
    return {"record_content": content, "record_time": record_time}


def _payload(
    *,
    documents: dict[str, list[dict]] | None = None,
    facts: list[dict] | None = None,
) -> dict:
    return {
        "timeline_facts": list(facts or []),
        "programmatic_timeline": {"documents": dict(documents or {})},
    }


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


def _strong_fact(fact_type: str, *, state: str = "present") -> dict:
    return {
        "fact_type": fact_type,
        "state": state,
        "source_key": "inpat_nondrug_order",
        "current_visit_bound": True,
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
            "usage": {"prompt_tokens": 40, "completion_tokens": 5, "total_tokens": 45},
            "_api_time": 0.1,
        }


@pytest.mark.asyncio
async def test_selected_rules_keep_customer_catalog_order_and_missing_projection_is_data_gap():
    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018", "LX0609-007", "LX0609-016"),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=None,
    )

    assert course.COURSE_QUALITY_RULE_IDS == (
        "LX0609-007",
        "LX0609-008",
        "LX0609-009",
        "LX0609-016",
        "LX0609-017",
        "LX0609-018",
    )
    assert course.EXECUTOR_KEY == "course_quality"
    assert [item["rule_id"] for item in result.results] == [
        "LX0609-007",
        "LX0609-016",
        "LX0609-018",
    ]
    assert [item["status"] for item in result.results] == ["data_gap"] * 3
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_007_uses_bounded_course_timeline_and_one_customer_prompt_call():
    client = _Client([{"is_compliant": True}])
    payload = _payload(
        documents={
            "first_course_record": [_row("首次病程记录，病情稳定。")],
            "daily_course_record": [_row("日常病程记录，病情平稳。", "2026-06-03 09:00:00")],
        },
        facts=[
            _strong_fact("current_visit_serious_order", state="absent"),
            _strong_fact("current_visit_critical_order", state="absent"),
        ],
    )
    payload["primary_document_text"] = "FULL_CHART_MUST_NOT_ENTER_PROMPT"
    payload["medical_text"] = "FULL_MEDICAL_TEXT_MUST_NOT_ENTER_PROMPT"

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-007",),
        wrapper_rules=[_wrapper("LX0609-007")],
        evidence_payload=payload,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant"]
    assert result.llm_call_count == 1
    assert result.total_tokens == 45
    assert result.results[0]["metadata"]["total_tokens"] == 45
    assert "首次病程记录" in client.prompts[0]
    assert "SHOULD_NOT_LEAK" not in client.prompts[0]
    assert "FULL_CHART_MUST_NOT_ENTER_PROMPT" not in client.prompts[0]
    assert "FULL_MEDICAL_TEXT_MUST_NOT_ENTER_PROMPT" not in client.prompts[0]


@pytest.mark.asyncio
async def test_008_009_require_current_visit_serious_or_critical_strong_fact():
    documents = {
        "daily_course_record": [
            _row("病重患者日常病程记录。"),
            _row("上级医师查房记录。", "2026-06-02 09:00:00"),
        ]
    }
    client = _Client([{"is_compliant": False}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(
            documents=documents,
            facts=[
                _strong_fact("current_visit_serious_order"),
                _strong_fact("current_visit_critical_order", state="absent"),
            ],
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "not_applicable",
    ]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "当前就诊存在病重医嘱" in client.prompts[0]

    critical_client = _Client([{"is_compliant": True}])
    critical = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(
            documents=documents,
            facts=[
                _strong_fact("current_visit_serious_order", state="absent"),
                _strong_fact("current_visit_critical_order"),
            ],
        ),
        llm_client=critical_client,
    )
    assert [item["status"] for item in critical.results] == [
        "not_applicable",
        "compliant",
    ]
    assert critical.llm_call_count == 1
    assert "当前就诊存在病危医嘱" in critical_client.prompts[0]

    silence = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(documents=documents),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in silence.results] == ["data_gap"] * 2
    assert silence.llm_call_count == 0

    explicit_negative = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-008", "LX0609-009"),
        wrapper_rules=[_wrapper("LX0609-008"), _wrapper("LX0609-009")],
        evidence_payload=_payload(
            documents=documents,
            facts=[
                _strong_fact("current_visit_serious_order", state="absent"),
                _strong_fact("current_visit_critical_order", state="absent"),
            ],
        ),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in explicit_negative.results] == [
        "not_applicable",
        "not_applicable",
    ]
    assert explicit_negative.llm_call_count == 0


@pytest.mark.asyncio
async def test_016_requires_admission_and_first_course_before_model():
    missing = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(documents={"admission_record": [_row("入院记录现病史。")]}),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in missing.results] == ["data_gap"]
    assert missing.llm_call_count == 0

    client = _Client([{"is_compliant": False}])
    complete = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(
            documents={
                "admission_record": [_row("入院记录现病史与病例特点。")],
                "first_course_record": [_row("首次病程病例特点与诊断依据。")],
            }
        ),
        llm_client=client,
    )
    assert [item["status"] for item in complete.results] == ["non_compliant"]
    assert complete.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_course_row",
    [
        {
            "title": "首次病程记录",
            "record_time": "2026-06-01 09:00:00",
            "content_preview": "首次病程病例特点、诊断依据和诊疗计划已经完整记录。",
            "text_preview": "首次病程记录预览",
        },
        {
            "title": "首次病程记录",
            "record_time": "2026-06-01 09:00:00",
            "source_table": "first_course_record",
            "assembled_fields": ["record_time", "document_title"],
        },
        {
            "title": "首次病程记录",
            "record_time": "2026-06-01 09:00:00",
            "content": (
                "source_table:first_course_record；文书类型：首次病程记录；"
                "记录时间：2026年06月01日09时00分00秒；assembly_status:partial"
            ),
        },
    ],
)
async def test_016_preview_or_assembly_shell_is_data_gap_without_model(
    first_course_row: dict,
):
    client = _Client([{"is_compliant": False}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(
            documents={
                "admission_record": [_row("入院记录现病史与病例特点。")],
                "first_course_record": [first_course_row],
            }
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "首次病程病例特点、诊断依据和诊疗计划已经完整记录" not in repr(result)


@pytest.mark.asyncio
async def test_016_admission_preview_shell_is_data_gap_without_model():
    client = _Client([{"is_compliant": True}])

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016",),
        wrapper_rules=[_wrapper("LX0609-016")],
        evidence_payload=_payload(
            documents={
                "admission_record": [
                    {
                        "title": "入院记录",
                        "record_time": "2026-06-01 08:00:00",
                        "text_preview": "入院记录预览",
                    }
                ],
                "first_course_record": [_row("首次病程病例特点与诊断依据。")],
            }
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_017_requires_two_comparable_records_and_never_outputs_review_pending():
    one_record = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(
            documents={"daily_course_record": [_row("患者病情稳定，继续观察治疗。")]}
        ),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in one_record.results] == ["not_applicable"]
    assert "复核" not in repr(one_record)

    copied = "患者神志清楚，咳嗽咳痰，双肺呼吸音粗，继续抗感染平喘化痰治疗，观察病情变化。"
    similar = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(
            documents={
                "daily_course_record": [
                    _row(copied),
                    _row(copied, "2026-06-02 09:00:00"),
                ]
            }
        ),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in similar.results] == ["non_compliant"]
    assert similar.llm_call_count == 0
    assert "复核" not in repr(similar)

    different = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-017",),
        wrapper_rules=[_wrapper("LX0609-017")],
        evidence_payload=_payload(
            documents={
                "daily_course_record": [
                    _row("患者胸痛缓解，复查心肌酶阴性，计划完善冠脉CTA检查并调整药物。"),
                    _row(
                        "冠脉CTA提示前降支狭窄，活动后仍有胸闷，已请介入组会诊评估造影。",
                        "2026-06-02 09:00:00",
                    ),
                ]
            }
        ),
        llm_client=_Client([]),
    )
    assert [item["status"] for item in different.results] == ["compliant"]
    assert "复核" not in repr(different)


@pytest.mark.asyncio
async def test_018_requires_complaint_and_primary_diagnosis_material():
    client = _Client([])
    incomplete = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(
            documents={"admission_record": [_row("主诉：腹痛2天。现病史待查。")]}
        ),
        llm_client=client,
    )
    assert [item["status"] for item in incomplete.results] == ["data_gap"]
    assert incomplete.llm_call_count == 0

    client = _Client([{"is_compliant": True}])
    complete = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-018",),
        wrapper_rules=[_wrapper("LX0609-018")],
        evidence_payload=_payload(
            documents={"admission_record": [_row("主诉：反复胸痛3个月。入院诊断：不稳定型心绞痛。")]}
        ),
        llm_client=client,
    )
    assert [item["status"] for item in complete.results] == ["compliant"]
    assert complete.llm_call_count == 1


@pytest.mark.asyncio
async def test_model_failure_and_invalid_json_are_isolated_and_safe():
    secret = "Bearer_secret_13800138000"
    client = _Client([RuntimeError(secret), f"not-json {secret}"])
    payload = _payload(
        documents={
            "admission_record": [_row("主诉：反复胸痛3个月。入院诊断：不稳定型心绞痛。")],
            "first_course_record": [_row("首次病程病例特点与诊断依据。")],
        }
    )

    result = await course.execute_luxian_0609_native_course_quality_rules(
        rule_ids=("LX0609-016", "LX0609-018"),
        wrapper_rules=[_wrapper("LX0609-016"), _wrapper("LX0609-018")],
        evidence_payload=payload,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 2
    assert secret not in repr(result)
