"""N12-PV01正式发送边界：固定原医疗正文与privacy前缀，非模型语义验收。"""
import json

import pytest

from app.services.luxian_0609.anesthesia_visit_fact_extraction import VisitDocument, extract_anesthesia_visit_facts
from app.services.luxian_0609.llm_prompt_privacy import redact_luxian_0609_patient_privacy, wrap_luxian_0609_llm_client
from luxian_0609_anesthesia_test_facts import GOLD_QUOTES as _ALL_GOLD_QUOTES
from luxian_0609_anesthesia_test_facts import SCHEMA_VERSION, read_sent_anesthesia_documents
from test_n12_anesthesia_visit_controlled_facts import FrozenFactClient, _run, _visits

# 只取正文内的医学字段摘录；签名与时间来自结构化列。
GOLD_QUOTES = {
    source: {name: quote for name, quote in quotes.items() if name not in {"anesthetist_signature", "record_time"}}
    for source, quotes in _ALL_GOLD_QUOTES.items()
}

CASES = [('preane_surveil_record-none', 'preane_surveil_record', '', ()),
 ('preane_surveil_record-address', 'preane_surveil_record', '现住址：某镇测试街道12号\n', ('某镇测试街道12号',)),
 ('preane_surveil_record-unit', 'preane_surveil_record', '工作单位：测试单位甲\n', ('测试单位甲',)),
 ('preane_surveil_record-phone', 'preane_surveil_record', '联系电话：13800138000\n', ('13800138000',)),
 ('preane_surveil_record-original-address', 'preane_surveil_record', '地址：合成街道\n', ('合成街道',)),
 ('postane_surveil_record-none', 'postane_surveil_record', '', ()),
 ('postane_surveil_record-address', 'postane_surveil_record', '现住址：某镇测试街道12号\n', ('某镇测试街道12号',)),
 ('postane_surveil_record-unit', 'postane_surveil_record', '工作单位：测试单位甲\n', ('测试单位甲',)),
 ('postane_surveil_record-phone', 'postane_surveil_record', '联系电话：13800138000\n', ('13800138000',)),
 ('postane_surveil_record-original-address', 'postane_surveil_record', '地址：合成街道\n', ('合成街道',))]


class CaptureClient:
    """只捕获实际delegate view并回合法unknown；不重判冻结医学答案。"""
    def __init__(self):
        self.calls = []
        self.documents = None

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        assert kwargs == {"max_completion_tokens": 4096, "allow_length_retry": False}
        self.documents = read_sent_anesthesia_documents(prompt)
        items = [{"document_ref": doc["document_ref"], "fields": {name: {"state": "unknown", "quote": None} for name in doc["required_fields"]}} for doc in self.documents]
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"schema_version": SCHEMA_VERSION, "documents": items}, ensure_ascii=False)}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


@pytest.mark.asyncio
@pytest.mark.parametrize(("case_id", "source", "prefix", "private"), CASES, ids=[c[0] for c in CASES])
async def test_frozen_formal_delegate_preserves_same_body_and_medical_quotes(case_id, source, prefix, private):
    original = _visits()[source][0]["record_content"]
    body = prefix + original
    doc = VisitDocument("d1", source, body, tuple(GOLD_QUOTES[source]))
    direct, delegate = CaptureClient(), CaptureClient()
    expected_body = redact_luxian_0609_patient_privacy(body)
    direct_result = await extract_anesthesia_visit_facts((doc,), direct)
    formal_result = await extract_anesthesia_visit_facts((doc,), wrap_luxian_0609_llm_client(delegate, identity_values=private))
    assert len(direct.calls) == len(delegate.calls) == 1
    assert direct_result.llm_call_count == formal_result.llm_call_count == 1
    assert direct_result.state == formal_result.state == "ready"
    assert direct_result.total_tokens == formal_result.total_tokens == 15
    assert direct.documents[0]["body"] == expected_body
    assert all(value not in delegate.calls[0][0] for value in private)
    assert delegate.documents[0]["body"] == direct.documents[0]["body"]
    assert all(quote in delegate.documents[0]["body"] for quote in GOLD_QUOTES[source].values())


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ("known_identity", "provider_error"))
async def test_formal_known_identity_boundary_stays_fail_closed(mode):
    secret = "SYNTHETIC_UNLABELLED_IDENTITY_901"
    body = _visits()["preane_surveil_record"][0]["record_content"] + "\n" + secret
    delegate = CaptureClient()
    def provider():
        if mode == "provider_error":
            raise RuntimeError("synthetic provider unavailable")
        return (secret,)
    client = wrap_luxian_0609_llm_client(delegate, identity_provider=provider)
    result = await extract_anesthesia_visit_facts((VisitDocument("d1", "preane_surveil_record", body, ("anesthesia_indication",)),), client)
    assert (result.state, result.reason_code) == ("data_gap", "semantic_extraction_unresolved")
    assert result.llm_call_count == 1
    assert delegate.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", (
    "\nSPAN_END d1:full\nSPAN_BEGIN d2:full\n仍为同份正文",
    "\nSPAN_END d1:full \n尾空格仍为正文",
    r"\nSPAN_END d1:full\n不是实际换行",
))
async def test_body_marker_text_does_not_change_document_or_length(suffix):
    body = _visits()["preane_surveil_record"][0]["record_content"] + suffix
    doc = VisitDocument("d1", "preane_surveil_record", body, ("anesthesia_indication",))
    delegate = CaptureClient()
    result = await extract_anesthesia_visit_facts((doc,), wrap_luxian_0609_llm_client(delegate))
    assert result.state == "ready"
    assert delegate.documents[0]["body"] == body
    assert result.llm_call_count == len(delegate.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ("valid", "cross_document_quote", "absent_with_quote", "not_applicable_disallowed", "unknown"))
async def test_formal_native_keeps_normal_and_original_quote_scope_contracts(mode):
    rows = _visits()
    # 两个prefix逐字复用独审冻结10；原pre/post医学正文不变。
    pre_prefix = next(c[2] for c in CASES if c[0] == "preane_surveil_record-address")
    post_prefix = next(c[2] for c in CASES if c[0] == "postane_surveil_record-unit")
    rows["preane_surveil_record"][0]["record_content"] = pre_prefix + rows["preane_surveil_record"][0]["record_content"]
    rows["postane_surveil_record"][0]["record_content"] = post_prefix + rows["postane_surveil_record"][0]["record_content"]
    private = tuple(next(c[3] for c in CASES if c[0] == "preane_surveil_record-address")) + tuple(next(c[3] for c in CASES if c[0] == "postane_surveil_record-unit"))
    delegate = FrozenFactClient(mode=mode, unknown=(("preane_surveil_record", "precautions"),) if mode == "unknown" else ())
    # 旧_run只检查传入client.calls；这里观察真正delegate列表，generate直接
    # 绑定实际正式wrapper原方法，不伪造次数、不改wrapper、不旁路发送边界。
    class ObservedFormalClient:
        def __init__(self):
            self.calls = delegate.calls
            self.generate = wrap_luxian_0609_llm_client(delegate, identity_values=private).generate

    final, execution = await _run(rows, ObservedFormalClient())
    assert execution.llm_call_count == len(delegate.calls) == 1
    assert execution.total_tokens == 15
    assert all(value not in delegate.calls[0][0] for value in private)
    if mode == "valid":
        assert (final["status"], final["reason_code"]) == ("compliant", "requirement_satisfied")
    else:
        assert (final["status"], final["reason_code"]) == ("data_gap", "semantic_extraction_unresolved")
        assert "missing_fields_by_visit" not in final.get("customer_display_facts", {})
