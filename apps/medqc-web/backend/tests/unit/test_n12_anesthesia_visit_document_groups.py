"""N12附加7项预先冻结：同实际文书分段与同事件多文书不得混淆。"""
import pytest
from luxian_0609_anesthesia_test_facts import (
    PRE_TEXT,
    SCHEMA_VERSION,
    anesthesia_fact_atom,
    anesthesia_fact_response,
    read_sent_anesthesia_documents,
)

from test_n12_anesthesia_visit_controlled_facts import _run, _visits


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
            source = doc["source_type"]
            absent = frozenset((source, name) for name in self.absent_by_index.get(index, ()))
            unknown = frozenset((source, name) for name in self.unknown_by_index.get(index, ()))
            items.append({"document_ref": doc["document_ref"], "fields": {
                name: anesthesia_fact_atom(doc, name, absent=absent, unknown=unknown) for name in doc["required_fields"]}})
        return anesthesia_fact_response({"schema_version": SCHEMA_VERSION, "documents": items})


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
    rows["preane_surveil_record"][0]["record_content"] = rows["preane_surveil_record"][0]["record_content"].replace("防误吸", "")
    rows["preane_surveil_record"][1]["record_content"] = rows["preane_surveil_record"][1]["record_content"].replace("禁食8小时禁饮2小时", "")
    client = FrozenPerDocumentFactClient(absent_by_index={0: {"precautions"}, 1: {"preoperative_orders"}})
    final, execution = await _run(rows, client)
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["missing_fields_by_visit"] == {"preanesthesia_visit": ["precautions", "preoperative_orders"]}
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
    client = FrozenPerDocumentFactClient(unknown_by_index={1: {"precautions"}})
    final, execution = await _run(_same_event_two_previsits(), client)
    assert (final["status"], final["reason_code"]) == ("data_gap", "semantic_extraction_unresolved")
    assert "missing_fields_by_visit" not in final.get("customer_display_facts", {})
    assert execution.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("unknown_field", ["precautions", "preoperative_orders"])
async def test_known_missing_in_independent_visit_survives_other_visit_unknown(unknown_field):
    from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result

    rows = _same_event_two_previsits()
    rows["preane_surveil_record"][0]["record_content"] = rows["preane_surveil_record"][0]["record_content"].replace("防误吸", "")
    client = FrozenPerDocumentFactClient(absent_by_index={0: {"precautions"}},
                                        unknown_by_index={1: {unknown_field}})
    final, execution = await _run(rows, client)
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["missing_fields_by_visit"] == {"preanesthesia_visit": ["precautions"]}
    envelope_item_from_rule_result(final, hmac_key="synthetic-independent-visit-save-validation")
    assert execution.llm_call_count == len(client.calls) == 1


class FrozenWholeDocumentFactClient:
    """固定完整文书临床引文；错误拆成半份输入时给非法引用而非制造fixture异常。"""
    def __init__(self):
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        documents = read_sent_anesthesia_documents(prompt)
        items = [{"document_ref": doc["document_ref"], "fields": {
            name: anesthesia_fact_atom(doc, name) for name in doc["required_fields"]}} for doc in documents]
        return anesthesia_fact_response({"schema_version": SCHEMA_VERSION, "documents": items})


@pytest.mark.asyncio
@pytest.mark.parametrize("distributed_structure", [False, True])
async def test_same_actual_document_parts_preserve_complete_content_and_trusted_structure(distributed_structure):
    rows = _visits()
    pre = rows["preane_surveil_record"][0]
    split = PRE_TEXT.index("拟行手术及麻醉")
    parts = [{**pre, "record_content": PRE_TEXT[:split]}, {**pre, "record_content": PRE_TEXT[split:]}]
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
