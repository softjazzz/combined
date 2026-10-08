from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.llm_prompt_privacy import (
    redact_luxian_0609_patient_privacy as redact,
    wrap_luxian_0609_llm_client,
)


@pytest.mark.parametrize(
    "text",
    [
        "患者张三,性别男,年龄60岁",
        "患者张三，性别：男，年龄60岁",
        "患者张三、性别 女、年龄60岁",
        "病人张三,性别:男,年龄60岁",
        "患儿张三，性别女，年龄6岁",
        "张三,性别男,年龄60岁",
        "病情摘要：\n张三，性别：女，年龄60岁",
        "患者欧阳小明，性别男，年龄60岁",
    ],
)
def test_explicit_sex_label_identifies_demographic_name(text):
    original_name = "欧阳小明" if "欧阳小明" in text else "张三"
    redacted = redact(text)
    assert original_name not in redacted
    assert redacted == text.replace(original_name, "[患者姓名已脱敏]")
    assert redact(redacted) == redacted


def test_detected_name_is_removed_from_later_spans_but_clinician_label_is_preserved():
    text = "患者张三,性别男,年龄60岁。张三诉腹痛，建议观察；记录医师：张三。"
    assert redact(text) == (
        "患者[患者姓名已脱敏],性别男,年龄60岁。"
        "[患者姓名已脱敏]诉腹痛，建议观察；记录医师：张三。"
    )


@pytest.mark.parametrize(
    "medical_text",
    [
        "患者神志清醒，性别对本项判断无影响。",
        "患者精神尚可，食欲可，年龄60岁。",
        "患者行CT检查，未见异常。",
        "患者有性别相关危险因素。",
        "性别男，年龄60岁，拟行腹腔镜下胆囊切除术。",
    ],
)
def test_medical_text_without_demographic_name_is_unchanged(medical_text):
    assert redact(medical_text) == medical_text


@pytest.mark.asyncio
async def test_wrapped_span_json_sends_only_redacted_valid_json():
    payload = {
        "documents": [
            {
                "document_id": "SYN-DOC",
                "spans": [
                    {"span_id": "d1:s1", "text": "患者张三,性别男,年龄60岁。"},
                    {"span_id": "d1:s2", "text": "张三诉腹痛。"},
                ],
            }
        ]
    }

    class Capture:
        async def generate(self, prompt, **kwargs):
            self.prompt = prompt
            return {"content": "{}"}

    capture = Capture()
    wrapper = wrap_luxian_0609_llm_client(capture)
    await wrapper.generate(json.dumps(payload, ensure_ascii=False))
    assert "张三" not in capture.prompt
    safe = json.loads(capture.prompt)
    assert safe["documents"][0]["spans"][0]["span_id"] == "d1:s1"
    assert safe["documents"][0]["spans"][1]["text"] == "[患者姓名已脱敏]诉腹痛。"
    assert redact(capture.prompt) == capture.prompt


@pytest.mark.parametrize(
    "text",
    [
        "患者张三,性别,年龄60岁",
        "患者张三，性别：不详，年龄60岁",
        "患者张三，性别未知，年龄60岁",
        "患者张三，性别男装，年龄60岁",
        "患者精神好，性别男，拟复查CT。",
        "患者一般情况可，性别女，继续观察。",
    ],
)
def test_absent_or_unrecognized_sex_value_does_not_expand_name_inference(text):
    assert redact(text) == text
