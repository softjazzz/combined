from __future__ import annotations

import json

import pytest

from app.services.luxian_0609 import native_surgery_document_execution as surgery_doc


def _wrapper(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "defect_level": "一般缺陷",
        "custom_prompt": (
            f"规则ID: {rule_id}\n"
            "主执行规则: SHOULD_NOT_LEAK\n"
            "映射执行规则: SHOULD_NOT_LEAK\n"
            "病历文本：\n{medical_text}\n"
            '只输出JSON：{"is_compliant": true}'
        ),
    }


def _fact(
    fact_type: str,
    *,
    source_key: str,
    state: str = "performed",
    anesthesia_method: str = "全身麻醉",
) -> dict:
    return {
        "fact_type": fact_type,
        "source_key": source_key,
        "state": state,
        "current_visit_bound": True,
        "normalized_value": {"anesthesia_method": anesthesia_method},
    }


def _payload(*, facts: list[dict] | None = None, **overrides: list[dict]) -> dict:
    documents = {
        "anesthesia_record": [
            {"content": ("麻醉记录：麻醉诱导完成，气管插管顺利，术中持续监测并维持麻醉，" "术毕苏醒拔管。")}
        ],
        "consent_form": [{"content": "麻醉知情同意书：已告知风险，患者和麻醉医师签名，签署时间精确到分钟。"}],
        "preane_surveil_record": [{"content": "麻醉术前访视记录：完成病史、检查、ASA评估、麻醉计划及医师签名。"}],
        "postane_surveil_record": [{"content": "麻醉术后访视记录：神志清楚，恢复情况稳定，麻醉医师已签名。"}],
        "presurg_discussion": [{"content": "术前讨论记录：术者参加并讨论手术指征、方案、风险及应对措施。"}],
        "surgery_record": [{"content": "手术记录：本次手术已完成，记录手术经过及术者。"}],
        "rescue_record": [],
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
            "usage": {"prompt_tokens": 80, "completion_tokens": 8, "total_tokens": 88},
            "_api_time": 0.1,
        }


def _strong_facts(*, anesthesia_method: str = "全身麻醉") -> list[dict]:
    return [
        _fact(
            "current_visit_anesthesia_performed",
            source_key="anesthesia_record",
            anesthesia_method=anesthesia_method,
        ),
        _fact("current_visit_surgery_confirmed", source_key="surgery_record"),
    ]


@pytest.mark.asyncio
async def test_strong_facts_run_each_selected_rule_once_in_customer_order():
    unrelated_marker = "UNRELATED_DAILY_COURSE_MUST_NOT_ENTER_PROMPT"
    client = _Client([{"is_compliant": index % 2 == 0} for index in range(6)])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=tuple(reversed(surgery_doc.SURGERY_DOCUMENT_RULE_IDS)),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in surgery_doc.SURGERY_DOCUMENT_RULE_IDS
        ],
        evidence_payload=_payload(
            facts=_strong_facts(),
            daily_course_record=[{"content": unrelated_marker}],
        ),
        llm_client=client,
    )

    assert result.planned_rule_ids == surgery_doc.SURGERY_DOCUMENT_RULE_IDS
    assert [item["rule_id"] for item in result.results] == list(
        surgery_doc.SURGERY_DOCUMENT_RULE_IDS
    )
    assert [item["status"] for item in result.results] == [
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
    ]
    assert result.llm_call_count == 6
    assert result.total_tokens == 528
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)
    assert all(unrelated_marker not in prompt for prompt in client.prompts)
    assert all("mapped_rule_ids" not in repr(item) for item in result.results)


@pytest.mark.asyncio
async def test_planned_anesthesia_template_and_method_only_are_not_performed_facts():
    marker = "SAFE_FALSE_EVIDENCE_MARKER"
    client = _Client([])
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034", "LX0609-035", "LX0609-036", "LX0609-037", "LX0609-038"),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in surgery_doc.SURGERY_DOCUMENT_RULE_IDS
        ],
        evidence_payload=_payload(
            facts=[],
            anesthesia_record=[
                {"content": f"拟请麻醉科会诊。{marker}"},
                {"content": "麻醉方式：全身麻醉"},
                {"content": "麻醉记录（空模板）"},
            ],
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"] * 5
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert marker not in repr(result)


@pytest.mark.asyncio
async def test_fully_silent_anesthesia_and_surgery_facts_are_data_gap_not_na():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034", "LX0609-039"),
        wrapper_rules=[_wrapper("LX0609-034"), _wrapper("LX0609-039")],
        evidence_payload=_payload(
            facts=[],
            anesthesia_record=[],
            surgery_record=[],
            presurg_discussion=[],
        ),
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_anesthesia_consent_source_unknown_is_data_gap_not_missing_defect():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034", "LX0609-035"),
        wrapper_rules=[_wrapper("LX0609-034"), _wrapper("LX0609-035")],
        evidence_payload=_payload(facts=_strong_facts(), consent_form=[]),
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert all(
        item["metadata"]["reason_code"] == "anesthesia_consent_source_unproven"
        for item in result.results
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_unrelated_generic_consent_does_not_qualify_as_anesthesia_consent():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034",),
        wrapper_rules=[_wrapper("LX0609-034")],
        evidence_payload=_payload(
            facts=_strong_facts(),
            consent_form=[{"content": "手术知情同意书：已完成手术风险告知和患者签名。"}],
        ),
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.results[0]["metadata"]["reason_code"] == (
        "anesthesia_consent_source_unproven"
    )


@pytest.mark.asyncio
async def test_consent_rules_do_not_require_anesthesia_method_when_performed_fact_exists():
    performed_without_method = {
        "fact_type": "current_visit_anesthesia_performed",
        "source_key": "anesthesia_record",
        "state": "performed",
        "current_visit_bound": True,
    }
    client = _Client([{"is_compliant": True}, {"is_compliant": True}])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034", "LX0609-035"),
        wrapper_rules=[_wrapper("LX0609-034"), _wrapper("LX0609-035")],
        evidence_payload=_payload(facts=[performed_without_method]),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_local_anesthesia_is_not_applicable_to_visit_and_record_sheet_rules():
    client = _Client([])
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-036", "LX0609-037", "LX0609-038"),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in surgery_doc.SURGERY_DOCUMENT_RULE_IDS
        ],
        evidence_payload=_payload(facts=_strong_facts(anesthesia_method="局部麻醉")),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["not_applicable"] * 3
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_nonlocal_anesthesia_missing_visit_projection_is_data_gap_not_defect():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-036", "LX0609-037"),
        wrapper_rules=[_wrapper("LX0609-036"), _wrapper("LX0609-037")],
        evidence_payload=_payload(
            facts=_strong_facts(),
            preane_surveil_record=[],
            postane_surveil_record=[],
        ),
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_emergency_rescue_surgery_is_039_exception_without_model():
    facts = _strong_facts() + [
        _fact(
            "current_visit_emergency_rescue_surgery",
            source_key="rescue_record",
            state="present",
        )
    ]
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-039",),
        wrapper_rules=[_wrapper("LX0609-039")],
        evidence_payload=_payload(facts=facts, presurg_discussion=[]),
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "not_applicable"
    assert result.results[0]["metadata"]["reason_code"] == "emergency_rescue_exception"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_performed_surgery_without_attested_preop_source_is_data_gap():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-039",),
        wrapper_rules=[_wrapper("LX0609-039")],
        evidence_payload=_payload(facts=_strong_facts(), presurg_discussion=[]),
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "data_gap"
    assert (
        result.results[0]["metadata"]["reason_code"]
        == "preop_discussion_source_unproven"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_llm_failure_and_invalid_json_are_sanitized_data_gap():
    secret = "Bearer_secret_13800138000"
    client = _Client([RuntimeError(secret), "not-json"])
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034", "LX0609-039"),
        wrapper_rules=[_wrapper("LX0609-034"), _wrapper("LX0609-039")],
        evidence_payload=_payload(facts=_strong_facts()),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "surgery_document_llm_failure",
        "surgery_document_llm_invalid_output",
    ]
    assert result.llm_call_count == 2
    assert secret not in repr(result)
