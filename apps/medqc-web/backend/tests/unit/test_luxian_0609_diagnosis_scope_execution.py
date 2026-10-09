"""050预算/来源/技术失败的原生到Finalizer回归，人工客户端不访问网络。"""

import pytest

from diagnosis_scope_test_support import FrozenDiagnosisScopeClient
from test_luxian_0609_native_extended_document_execution import (
    _canonical_extended_result, _evaluate_selected,
)


RULE = "LX0609-03-02-01"


class BrokenTransportClient:
    async def generate(self, *args, **kwargs):
        raise RuntimeError("人工传输失败")


class InvalidOutputClient:
    async def generate(self, *args, **kwargs):
        return {"finish_reason": "stop", "content": '{"schema_version":"bad","documents":[]}',
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


@pytest.mark.asyncio
@pytest.mark.parametrize("case,body,client_factory,status,reason,calls,resolution", [
    ("capacity", "完整合成正文。" * 10000, FrozenDiagnosisScopeClient,
     "data_gap", "candidate_scope_incomplete", 0, "capacity_exceeded"),
    ("missing_body", None, FrozenDiagnosisScopeClient,
     "data_gap", "required_field_missing", 0, "unavailable"),
    ("transport", "目前诊断仍不明确。", BrokenTransportClient,
     "technical_error", "model_transport_error", 1, "invalid"),
    ("invalid_output", "目前诊断仍不明确。", InvalidOutputClient,
     "technical_error", "model_invalid_output", 1, "invalid"),
], ids=["capacity", "missing-body", "transport", "invalid-output"])
async def test_scope_failure_preserves_native_and_canonical_nonclinical_state(
    case, body, client_factory, status, reason, calls, resolution,
):
    # 超预算的长正文仅测试输入容量，不以正文长度裁定诊断语义。
    snapshot, materials, execution, reduced = await _evaluate_selected((RULE,), {
        "inpat_registration": ({"admission_datetime": "2026-06-01 08:00:00"},),
        "daily_course_record": ({"document_id": "SYN-SCOPE", "record_time": "2026-06-08 09:00:00",
                                 "record_content": body},),
    }, llm_client=client_factory())
    assert reduced[0].final_state.value == status
    assert reduced[0].reason_code == reason
    assert execution.llm_call_count == calls
    if case in {"capacity", "missing_body"}:
        assert execution.total_tokens == 0
    if case == "invalid_output":
        assert execution.total_tokens == 15
    result = _canonical_extended_result(rule_id=RULE, snapshot=snapshot,
        materials=materials, result=execution, reduced=reduced)
    assert result["status"] == status
    assert result["reason_code"] == reason
    facts = result.get("customer_display_facts", {})
    assert facts.get("diagnosis_scope_resolution") == resolution
    assert facts.get("uncertain_record_times") == []
    assert "未见疑难病例讨论" not in result["findings"]
    assert "本质控点不适用" not in result["findings"]
    assert "已完成讨论" not in result["findings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [None, "完整早期合成正文。" * 10000], ids=["missing_body", "huge_body"])
async def test_known_early_course_never_spends_scope_budget_or_creates_false_source_gap(body):
    client = FrozenDiagnosisScopeClient()
    snapshot, materials, execution, reduced = await _evaluate_selected((RULE,), {
        "inpat_registration": ({"admission_datetime": "2026-06-01 08:00:00"},),
        "daily_course_record": ({"document_id": "SYN-EARLY", "record_time": "2026-06-02 09:00:00",
                                 "record_content": body},),
    }, llm_client=client)
    assert execution.llm_call_count == execution.total_tokens == 0
    assert client.calls == [] and client.fixture_error is None
    assert reduced[0].final_state.value == "not_applicable"
    result = _canonical_extended_result(rule_id=RULE, snapshot=snapshot,
        materials=materials, result=execution, reduced=reduced)
    assert result["status"] == "not_applicable"
    assert result["reason_code"] == "trigger_absent_complete"
    assert result["customer_display_facts"]["uncertain_record_times"] == []
    assert "未见疑难病例讨论" not in result["findings"]
