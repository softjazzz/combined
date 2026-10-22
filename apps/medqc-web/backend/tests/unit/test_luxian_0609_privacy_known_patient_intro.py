"""已知身份仅帮助识别明确患者介绍，不能替代发送前身份残留拦截。"""
from __future__ import annotations

import json

import pytest

from app.services.luxian_0609 import llm_prompt_privacy as privacy
from app.services.luxian_0609.privacy_request_scope import (
    _case_scope,
    luxian_0609_case_identity_scope,
    protect_current_payload,
)
from app.services.luxian_0609.transfusion_course_presence import classify_transfusion_course_records


COORDINATES = ("synthetic-I", "synthetic-P", "synthetic-V")


@pytest.mark.parametrize("text", [
    "患者牟甲乙，输血目的：纠正贫血；输注红细胞。",
    "病人牟甲乙，性别男，年龄60岁。",
    "患儿牟甲乙，因贫血入院。",
    "患者赵甲乙，老年男性，因贫血入院。",
    "新建S章节:牟甲乙，男，79岁，因反复咳嗽入院。",
    "牟甲乙，女，60岁，因贫血入院。",
])
def test_known_patient_intro_is_redacted_before_fact_preparation(text):
    name = "赵甲乙" if "赵甲乙" in text else "牟甲乙"
    with luxian_0609_case_identity_scope(case_coordinates=COORDINATES, identity_provider=lambda: (name,)):
        safe = privacy.redact_luxian_0609_patient_privacy(text)
        assert safe == text.replace(name, "[患者姓名已脱敏]")
        assert privacy.redact_luxian_0609_patient_privacy(safe) == safe


@pytest.mark.asyncio
async def test_wrapper_uses_known_patient_intro_without_scope():
    class Capture:
        async def generate(self, prompt, **kwargs):
            self.prompt = prompt
            return {}

    capture = Capture()
    wrapper = privacy.wrap_luxian_0609_llm_client(capture, identity_values=("牟甲乙",))
    await wrapper.generate("患者牟甲乙，输血目的：纠正贫血。")
    assert capture.prompt == "患者[患者姓名已脱敏]，输血目的：纠正贫血。"


@pytest.mark.asyncio
async def test_fact_preparation_and_http_redaction_keep_identical_quote_binding():
    class Echo:
        async def generate(self, prompt, **kwargs):
            payload = protect_current_payload({"messages": [{"role": "user", "content": prompt}]})
            sent = payload["messages"][0]["content"]
            assert "牟甲乙" not in sent
            assert "记录医师：周丙丁" in sent
            batch = json.loads(sent.split("INPUT_JSON=", 1)[1])["records"]
            return {"content": json.dumps({
                "schema_version": "lx0609-transfusion-course-presence-v1",
                "records": [{"index": row["index"], "kind": "record", "quote": row["content"]} for row in batch],
            }, ensure_ascii=False)}

    with luxian_0609_case_identity_scope(case_coordinates=COORDINATES, identity_provider=lambda: ("牟甲乙",)):
        with _case_scope(COORDINATES):
            client = privacy.wrap_luxian_0609_llm_client(Echo(), identity_values=("牟甲乙",))
            result = await classify_transfusion_course_records([
                {"document_id": "synthetic-record", "record_content": "患者牟甲乙，输血目的：纠正贫血。记录医师：周丙丁。"},
            ], client)
    assert result.state == "present"
    assert result.valid_document_ids == ("synthetic-record",)


@pytest.mark.parametrize("text,identities", [
    ("拟为牟甲乙实施治疗。", ("牟甲乙",)),
    ("患者牟甲乙丰，拟行检查。", ("牟甲乙",)),
    ("检验值130mg。", ("130",)),
    ("患者神志清醒，继续观察。", ("牟甲乙",)),
    ("会诊意见:牟甲乙丰，男，60岁。", ("牟甲乙",)),
])
def test_known_intro_does_not_blindly_replace_identity_or_medical_text(text, identities):
    with luxian_0609_case_identity_scope(case_coordinates=COORDINATES, identity_provider=lambda: identities):
        assert privacy.redact_luxian_0609_patient_privacy(text) == text


@pytest.mark.parametrize("text", ["牟甲乙", "拟为牟甲乙实施治疗。", "患者牟甲乙丰，拟行检查。"])
def test_unlabelled_or_partial_identity_still_blocks_at_http_boundary(text):
    with luxian_0609_case_identity_scope(case_coordinates=COORDINATES, identity_provider=lambda: ("牟甲乙",)):
        with pytest.raises(privacy.PatientPrivacyViolation):
            protect_current_payload({"messages": [{"role": "user", "content": text}]})
