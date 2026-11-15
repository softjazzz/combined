"""LX0609-10-03-01 模型输出合同：合法输出被接受、无效输出严格拒绝且可定位。

1026 验收只留下 result_status/model_invalid_output/retryable=false，未留存原响应。
本文件不调用任何模型：以合成响应经同一隐私包装、病例身份作用域与解析器，
证明合同合法（含空白归一、身份脱敏后的逐字摘录）的输出不会被本地误拒；
各类无效输出仍为不可重试的 model_invalid_output，并记录不含内容的诊断分类。
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

import pytest

from app.services.luxian_0609.extended_document import invasive_procedure_record as module
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
from app.services.luxian_0609.privacy_request_scope import luxian_0609_case_identity_scope
from app.services.qc_execution_errors import safe_failure_projection

IDENTITY = "合成甲"
PROCEDURE = module.load_invasive_procedure_catalog()[0]
TRIGGER = module.ProcedureTrigger(PROCEDURE, date(2026, 1, 2), ("合成治疗医嘱",))
RECORD = {
    "document_id": "SYN-D1",
    "record_time": "2026-01-02 10:00",
    "record_content": f"病程记录\n患者{IDENTITY}，男，60岁。\n今日  行{PROCEDURE.name}，过程顺利。",
}


class _Reply:
    """合成供应商：记录模型实际可见 prompt，按给定构造器返回响应。"""

    def __init__(self, build):
        self.build = build
        self.prompt = ""

    def supports_strict_json_schema(self) -> bool:
        return True

    async def generate(self, prompt: str, **_: Any) -> dict:
        self.prompt = prompt
        payload = json.loads(prompt.split("INPUT_JSON=", 1)[1])
        content, finish = self.build(payload)
        return {
            "choices": [{"finish_reason": finish, "message": {"content": content}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        }


def _visible_quote(payload: dict) -> str:
    text = payload["records"][0]["text"]
    start = text.index("今日")
    return text[start:start + 16]


def _record_items(payload: dict, **overrides: Any) -> str:
    item = {"id": "P01", "state": "documented", "record": "R01", "quote": _visible_quote(payload)}
    item.update(overrides)
    return json.dumps({"schema_version": module.RECORD_SCHEMA_VERSION, "items": [item]}, ensure_ascii=False)


async def _check(build) -> tuple[module.RecordDocumentationResult, _Reply]:
    reply = _Reply(build)
    with luxian_0609_case_identity_scope(case_coordinates=("I", "P", "V"), identity_provider=lambda: (IDENTITY,)):
        client = wrap_luxian_0609_llm_client(reply, identity_provider=lambda: (IDENTITY,))
        result = await module.check_invasive_procedure_records((TRIGGER,), (RECORD,), client)
    return result, reply


@pytest.mark.asyncio
async def test_contract_valid_quote_from_model_visible_redacted_text_is_accepted() -> None:
    result, reply = await _check(lambda payload: (_record_items(payload), "stop"))
    assert IDENTITY not in reply.prompt
    assert (result.state, result.reason_code) == ("ready", "")
    assert result.states == ((module.trigger_key(TRIGGER), "documented"),)


@pytest.mark.asyncio
async def test_contract_valid_fenced_json_and_not_documented_nulls_are_accepted() -> None:
    def build(payload: dict) -> tuple[str, str]:
        body = json.dumps({"schema_version": module.RECORD_SCHEMA_VERSION, "items": [
            {"id": "P01", "state": "not_documented", "record": None, "quote": None},
        ]})
        return f"```json\n{body}\n```", "stop"

    result, _ = await _check(build)
    assert result.states == ((module.trigger_key(TRIGGER), "not_documented"),)


INVALID_RECORD_OUTPUTS = {
    "json_syntax": lambda p: ("下面是结果：{\"schema_version\":", "stop"),
    "provider_incomplete": lambda p: (_record_items(p), "length"),
    "root_schema": lambda p: (json.dumps({"schema_version": module.RECORD_SCHEMA_VERSION, "items": [], "note": "x"}), "stop"),
    "item_shape": lambda p: (json.dumps({"schema_version": module.RECORD_SCHEMA_VERSION, "items": [
        {"id": "P01", "state": "not_documented"}]}), "stop"),
    "id_binding": lambda p: (_record_items(p, id="P09"), "stop"),
    "record_binding": lambda p: (_record_items(p, record="R07"), "stop"),
    "quote_grounding": lambda p: (_record_items(p, quote="今日行另一项未记载操作"), "stop"),
    "state_fields": lambda p: (_record_items(p, state="not_documented"), "stop"),
    "state_value": lambda p: (_record_items(p, state="done"), "stop"),
    "coverage": lambda p: (json.dumps({"schema_version": module.RECORD_SCHEMA_VERSION, "items": []}), "stop"),
    "json_duplicate_key": lambda p: (
        '{"schema_version":"%s","items":[],"items":[]}' % module.RECORD_SCHEMA_VERSION, "stop"),
}


@pytest.mark.parametrize("category", sorted(INVALID_RECORD_OUTPUTS))
@pytest.mark.asyncio
async def test_invalid_record_output_stays_strict_non_retryable_and_logs_safe_category(
    category: str, caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=module.__name__)
    result, _ = await _check(INVALID_RECORD_OUTPUTS[category])
    assert (result.state, result.reason_code, result.states) == ("technical_error", "model_invalid_output", ())
    assert safe_failure_projection({"reason_code": result.reason_code})["retryable"] is False
    messages = [record.getMessage() for record in caplog.records if record.name == module.__name__]
    assert messages == [
        f"LX0609 有创操作模型输出未通过合同: step=record_documentation category={category}",
    ]
    # 诊断日志不含病历正文、身份或模型内容。
    assert not any(token in messages[0] for token in (IDENTITY, PROCEDURE.name, "今日"))


@pytest.mark.asyncio
async def test_order_mapping_accepts_catalog_match_and_rejects_duplicate_binding(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=module.__name__)

    class _Mapping(_Reply):
        async def generate(self, prompt: str, **_: Any) -> dict:
            self.prompt = prompt
            return {"choices": [{"finish_reason": "stop", "message": {"content": self.build}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}

    valid = json.dumps({"schema_version": module.MAPPING_SCHEMA_VERSION,
                        "matches": [{"id": "O001", "catalog": "C01"}]})
    ok = await module.map_orders_to_invasive_catalog(["合成治疗医嘱"], _Mapping(valid))
    assert (ok.state, ok.mapped) == ("ready", (("合成治疗医嘱", PROCEDURE),))

    duplicated = json.dumps({"schema_version": module.MAPPING_SCHEMA_VERSION, "matches": [
        {"id": "O001", "catalog": "C01"}, {"id": "O001", "catalog": "C02"}]})
    rejected = await module.map_orders_to_invasive_catalog(["合成治疗医嘱"], _Mapping(duplicated))
    assert (rejected.state, rejected.reason_code) == ("technical_error", "model_invalid_output")
    assert [record.getMessage() for record in caplog.records if record.name == module.__name__] == [
        "LX0609 有创操作模型输出未通过合同: step=order_mapping category=id_binding",
    ]
