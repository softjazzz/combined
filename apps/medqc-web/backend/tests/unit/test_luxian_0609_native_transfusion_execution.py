from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.services.luxian_0609 import native_transfusion_execution as transfusion


def _documents(**overrides: list[dict]) -> dict:
    documents = {
        "bloodtrans_record": [{"content": "输血记录正文，记录实际输注过程及观察情况。"}],
        "consent_form": [{"content": "输血治疗知情同意书，已完成风险告知及签名。"}],
        "labtest_master": [{"content": "输血前常规检查资料。"}],
        "labtest_item_report": [],
        "blood_application": [{"content": "输血前评估及申请资料。"}],
        "daily_course_record": [{"content": "输血过程及输血后评价记录。"}],
        "surgery_record": [{"content": "手术记录中的术中输血信息。"}],
        "anesthesia_record": [{"content": "麻醉记录中的术中输血信息。"}],
        "postsurg_firstcourse_record": [{"content": "术后首次病程中的输血信息。"}],
        "inpat_nondrug_order": [{"content": "输血医嘱中的成分和数量。"}],
        "inpat_bill_item": [{"content": "输血收费中的成分和数量。"}],
    }
    documents.update(overrides)
    return {"programmatic_timeline": {"documents": documents}}


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


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            "_api_time": 0.2,
        }


def _reader(*, source_key: str, **_: object) -> list[dict]:
    if source_key == "mr_bloodtrans":
        return []
    if source_key == "bloodtrans_record":
        return [{"record_content": "输血记录正文，记录实际输注过程及观察情况。"}]
    raise AssertionError(source_key)


@pytest.mark.asyncio
async def test_no_dedicated_transfusion_source_rows_returns_not_applicable_without_model(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", lambda **_: [])
    client = _Client([])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=transfusion.TRANSFUSION_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in transfusion.TRANSFUSION_RULE_IDS],
        evidence_payload=_documents(
            bloodtrans_record=[],
            daily_course_record=[{"content": "普通病程仅提到拟输血和备血。"}],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["not_applicable"] * 9
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_dedicated_record_triggers_selected_rules_once_each_and_keeps_customer_order(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client(
        [{"is_compliant": index % 2 == 0} for index in range(len(transfusion.TRANSFUSION_RULE_IDS))]
    )

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=tuple(reversed(transfusion.TRANSFUSION_RULE_IDS)),
        wrapper_rules=[_wrapper(rule_id) for rule_id in transfusion.TRANSFUSION_RULE_IDS],
        evidence_payload=_documents(bloodtrans_record=[{"content": "输血记录"}]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["rule_id"] for item in result.results] == list(transfusion.TRANSFUSION_RULE_IDS)
    assert [item["status"] for item in result.results] == [
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
        "compliant",
    ]
    assert result.llm_call_count == 9
    assert result.total_tokens == 990
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_typed_transfusion_event_triggers_but_shell_record_fails_closed(monkeypatch):
    def _typed_reader(*, source_key: str, **_: object) -> list[dict]:
        if source_key == "mr_bloodtrans":
            return [{"transfution_datetime": datetime(2026, 6, 5, 14, 20)}]
        return []

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _typed_reader)
    client = _Client([{"is_compliant": True}])
    typed = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-045",),
        wrapper_rules=[_wrapper("LX0609-045")],
        evidence_payload=_documents(bloodtrans_record=[{"content": "空模板"}]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )
    assert typed.results[0]["status"] == "compliant"
    assert typed.llm_call_count == 1

    def _shell_reader(*, source_key: str, **_: object) -> list[dict]:
        if source_key == "bloodtrans_record":
            return [{"record_content": "空模板"}]
        return []

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _shell_reader)
    shell = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-045",),
        wrapper_rules=[_wrapper("LX0609-045")],
        evidence_payload=_documents(bloodtrans_record=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert shell.results[0]["status"] == "data_gap"
    assert shell.llm_call_count == 0


@pytest.mark.asyncio
async def test_missing_consent_projection_is_data_gap_and_other_rules_are_not_blocked(monkeypatch):
    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    client = _Client([{"is_compliant": True}])

    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-041", "LX0609-042", "LX0609-045"),
        wrapper_rules=[_wrapper("LX0609-041"), _wrapper("LX0609-042"), _wrapper("LX0609-045")],
        evidence_payload=_documents(consent_form=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap", "compliant"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_source_error_and_invalid_model_output_fail_closed_without_echo(monkeypatch):
    secret = "Bearer_secret_13800138000"

    def _failed_reader(**_: object) -> list[dict]:
        raise RuntimeError(secret)

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _failed_reader)
    result = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-041", "LX0609-049"),
        wrapper_rules=[_wrapper("LX0609-041"), _wrapper("LX0609-049")],
        evidence_payload=_documents(bloodtrans_record=[]),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert secret not in repr(result)

    monkeypatch.setattr(transfusion, "read_luxian_0609_native_source_rows", _reader)
    invalid = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-049",),
        wrapper_rules=[_wrapper("LX0609-049")],
        evidence_payload=_documents(),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([f"not-json {secret}"]),
    )
    assert invalid.results[0]["status"] == "data_gap"
    assert secret not in repr(invalid)
