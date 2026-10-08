"""N12附加7项预先冻结：同实际文书分段与同事件多文书不得混淆。"""
import json

import pytest
from luxian_0609_anesthesia_test_facts import read_sent_anesthesia_documents

from test_n12_anesthesia_visit_controlled_facts import GOLD_QUOTES, _run, _visits


class FrozenPerDocumentFactClient:
    """附加多文书固定预期，逐输入文书给事实，不从生产状态生成答案。"""
    def __init__(self, *, absent_by_index=None, unknown_by_index=None):
        self.absent_by_index = absent_by_index or {}
        self.unknown_by_index = unknown_by_index or {}
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        documents = read_sent_anesthesia_documents(prompt)
        items = []
        for index, doc in enumerate(documents):
            fields = {}
            for name in doc["required_fields"]:
                if name in self.unknown_by_index.get(index, ()):
                    atom = {"state": "unknown", "span_id": None, "start": None, "end": None, "quote": None}
                elif name in self.absent_by_index.get(index, ()):
                    atom = {"state": "absent", "span_id": None, "start": 0, "end": len(doc["body"]), "quote": None}
                else:
                    quote = GOLD_QUOTES[doc["source_type"]][name]
                    start = doc["body"].index(quote)
                    atom = {"state": "present", "span_id": next(sid for sid, span in doc["spans"].items() if quote in span),
                        "start": start, "end": start + len(quote), "quote": quote}
                fields[name] = atom
            items.append({"document_ref": doc["document_ref"], "fields": fields})
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"schema_version": "lx0609-anesthesia-visit-facts-v1", "documents": items}, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def _same_event_two_previsits():
    rows = _visits()
    pre = rows["preane_surveil_record"][0]
    rows["preane_surveil_record"] = [{**pre, "document_id": "pre-A-1"}, {**pre, "document_id": "pre-A-2"}]
    return rows


@pytest.mark.asyncio
async def test_multiple_individually_complete_visits_in_one_reliable_event_stay_compliant():
    client = FrozenPerDocumentFactClient()
    final, execution = await _run(_same_event_two_previsits(), client)
    assert final["status"] == "compliant"
    assert execution.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
async def test_two_partial_documents_cannot_fill_each_others_missing_fields():
    rows = _same_event_two_previsits()
    rows["preane_surveil_record"][0]["record_content"] = rows["preane_surveil_record"][0]["record_content"].replace("气道评估正常", "")
    rows["preane_surveil_record"][1]["record_content"] = rows["preane_surveil_record"][1]["record_content"].replace("禁食禁饮已核对", "")
    client = FrozenPerDocumentFactClient(absent_by_index={0: {"airway_assessment"}, 1: {"fasting_status"}})
    final, execution = await _run(rows, client)
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["missing_fields_by_visit"] == {"preanesthesia_visit": ["airway_assessment", "fasting_status"]}
    assert execution.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("identity", ["different_event", "unproven"])
async def test_multiple_visits_do_not_bypass_original_event_identity_gate(identity):
    rows = _same_event_two_previsits()
    if identity == "different_event":
        rows["preane_surveil_record"][1]["application_id"] = "B"
    else:
        for row in rows["preane_surveil_record"]:
            row.pop("application_id")
    client = FrozenPerDocumentFactClient()
    final, execution = await _run(rows, client)
    assert (final["status"], final["reason_code"]) == ("data_gap", "association_failed")
    assert execution.llm_call_count == len(client.calls) == 0


@pytest.mark.asyncio
async def test_any_unknown_document_blocks_definite_multi_document_judgment():
    client = FrozenPerDocumentFactClient(unknown_by_index={1: {"airway_assessment"}})
    final, execution = await _run(_same_event_two_previsits(), client)
    assert (final["status"], final["reason_code"]) == ("data_gap", "semantic_extraction_unresolved")
    assert "missing_fields_by_visit" not in final.get("customer_display_facts", {})
    assert execution.llm_call_count == len(client.calls) == 1


class FrozenWholeDocumentFactClient:
    """固定完整文书临床引文；错误拆成半份输入时给非法引用而非制造fixture异常。"""
    def __init__(self):
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        documents = read_sent_anesthesia_documents(prompt)
        items = []
        for doc in documents:
            fields = {}
            for name in doc["required_fields"]:
                quote = GOLD_QUOTES[doc["source_type"]].get(name, "测试医师")
                start = max(0, doc["body"].find(quote))
                span_id = next((sid for sid, text in doc["spans"].items() if quote in text), next(iter(doc["spans"])))
                fields[name] = {"state": "present", "span_id": span_id, "start": start, "end": start + len(quote), "quote": quote}
            items.append({"document_ref": doc["document_ref"], "fields": fields})
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"schema_version": "lx0609-anesthesia-visit-facts-v1", "documents": items}, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


@pytest.mark.asyncio
@pytest.mark.parametrize("distributed_structure", [False, True])
async def test_same_actual_document_parts_preserve_complete_content_and_trusted_structure(distributed_structure):
    rows = _visits()
    pre = rows["preane_surveil_record"][0]
    parts = [{**pre, "record_content": "ASA II级；气道评估正常；"},
        {**pre, "record_content": "禁食禁饮已核对；否认麻醉史；已完成麻醉风险告知。"}]
    if distributed_structure:
        parts[0].pop("anesthetist_sign")
        parts[0]["ASA_level"] = "II级"
        parts[1].pop("record_time")
    rows["preane_surveil_record"] = parts
    client = FrozenWholeDocumentFactClient()
    final, execution = await _run(rows, client)
    assert final["status"] == "compliant"
    assert execution.llm_call_count == len(client.calls) == 1
    sent = read_sent_anesthesia_documents(client.calls[0][0])
    assert len(sent) == 2
    assert all(raw_id not in client.calls[0][0] for raw_id in ("pre-A", "post-A"))
    from app.services.luxian_0609.evidence_material import build_material_document_refs
    original_refs = {ref for source in ("preane_surveil_record", "postane_surveil_record") for ref in build_material_document_refs(source, tuple(rows[source]))}
    assert original_refs.issubset(execution.decisions[0].fact_refs)
