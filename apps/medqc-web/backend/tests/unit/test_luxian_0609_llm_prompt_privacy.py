from __future__ import annotations

import pytest

from app.services.luxian_0609.llm_prompt_privacy import (
    redact_luxian_0609_patient_privacy,
    wrap_luxian_0609_llm_client,
)


class _CaptureClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **kwargs):
        self.prompts.append(prompt)
        return {"content": "{}", "kwargs": kwargs}


class _StrictSchemaCaptureClient(_CaptureClient):
    def __init__(self) -> None:
        super().__init__()
        self.capability_calls = 0

    def supports_strict_json_schema(self) -> bool:
        self.capability_calls += 1
        return True


def test_redaction_removes_patient_identifiers_and_preserves_clinician_names():
    prompt = """
患者基本信息：姓名：张三；患者张三，女，45岁。
身份证号：510521198001011234；手机号：13800138000；家庭电话：0830-1234567。
现住址：四川省泸州市泸县某镇1号；住院号：IP-20260817-001。
联系人姓名：王小明；联系人电话：13900139000。
出生日期：1980-01-01；医保号：YB-998877；工作单位：泸县某公司。
患者孙小红因发热入院。
陈秀英，女，67岁，因咳嗽入院；备用电话08301234567。
李四主治医师查房记录；主治医师姓名：李四；会诊医师 姓名：钱七；王五主任医师建议继续治疗。
"""

    redacted = redact_luxian_0609_patient_privacy(prompt)

    for private_value in (
        "张三",
        "510521198001011234",
        "13800138000",
        "0830-1234567",
        "四川省泸州市泸县某镇1号",
        "IP-20260817-001",
        "王小明",
        "13900139000",
        "1980-01-01",
        "YB-998877",
        "泸县某公司",
        "孙小红",
        "陈秀英",
        "08301234567",
    ):
        assert private_value not in redacted
    assert "李四主治医师查房记录" in redacted
    assert "主治医师姓名：李四" in redacted
    assert "会诊医师 姓名：钱七" in redacted
    assert "王五主任医师建议继续治疗" in redacted
    assert "女，45岁" in redacted


@pytest.mark.asyncio
async def test_wrapper_only_sends_redacted_prompt_and_forwards_call_contract():
    delegate = _CaptureClient()
    client = wrap_luxian_0609_llm_client(delegate)

    response = await client.generate(
        "患者姓名：赵敏；联系电话：13600136000；记录医师：周强。",
        max_completion_tokens=512,
        allow_length_retry=False,
    )

    assert len(delegate.prompts) == 1
    assert "赵敏" not in delegate.prompts[0]
    assert "13600136000" not in delegate.prompts[0]
    assert "记录医师：周强" in delegate.prompts[0]
    assert response["kwargs"] == {
        "max_completion_tokens": 512,
        "allow_length_retry": False,
    }


def test_wrapper_forwards_strict_schema_capability_and_defaults_missing_to_false():
    supported_delegate = _StrictSchemaCaptureClient()
    supported_client = wrap_luxian_0609_llm_client(supported_delegate)

    assert supported_client.supports_strict_json_schema() is True
    assert supported_delegate.capability_calls == 1

    missing_client = wrap_luxian_0609_llm_client(_CaptureClient())
    assert missing_client.supports_strict_json_schema() is False


def test_wrapper_keeps_none_and_is_idempotent():
    assert wrap_luxian_0609_llm_client(None) is None
    delegate = _CaptureClient()
    wrapped = wrap_luxian_0609_llm_client(delegate)
    assert wrap_luxian_0609_llm_client(wrapped) is wrapped


@pytest.mark.parametrize("body", [
    "现住址：某镇测试街道12号\n14:00悬浮红细胞2U输注完毕。",
    "工作单位：测试单位甲\n输注完毕。",
])
@pytest.mark.parametrize("pre_redacted", [False, True])
def test_json_embedded_labelled_address_survives_wrapper_redaction(body, pre_redacted):
    """抽取器以 JSON 承载正文，发送包装器再对整段 prompt 脱敏：不能越过转义换行吞掉 JSON。"""
    import json

    sent_body = redact_luxian_0609_patient_privacy(body) if pre_redacted else body
    prompt = "INPUT_JSON=" + json.dumps({"documents": [{"body": sent_body}]}, ensure_ascii=False)
    redacted = redact_luxian_0609_patient_privacy(prompt)
    payload = json.loads(redacted.removeprefix("INPUT_JSON="))
    assert payload["documents"][0]["body"] == redact_luxian_0609_patient_privacy(body)
    assert "某镇测试街道12号" not in redacted and "测试单位甲" not in redacted
    assert redact_luxian_0609_patient_privacy(redacted) == redacted


def test_known_ascii_identity_after_json_escape_is_still_rejected():
    """正文以 JSON 嵌入 prompt 时“\n”紧贴身份值，不能因 token 边界判断而漏检。"""
    import json

    from app.services.luxian_0609.llm_prompt_privacy import PatientPrivacyViolation, assert_no_known_identity

    prompt = "INPUT_JSON=" + json.dumps({"body": "正文\nSYNTHETIC_ID_901"}, ensure_ascii=False)
    with pytest.raises(PatientPrivacyViolation):
        assert_no_known_identity(prompt, ["SYNTHETIC_ID_901"])
    assert_no_known_identity("130mg 1.5 Patient", ["1", "P"])
