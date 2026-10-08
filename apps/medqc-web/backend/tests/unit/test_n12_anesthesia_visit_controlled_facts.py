"""N12预先冻结工程合同：原输入不变，受控Fake只给原子事实。"""

import json

import pytest
from luxian_0609_anesthesia_test_facts import read_sent_anesthesia_documents

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from tests.unit.test_luxian_0609_round2_document_boundaries import _visits


RULE = "LX0609-04-04-02"
GOLD_QUOTES = {
    "preane_surveil_record": {"asa_level": "ASA II级", "airway_assessment": "气道评估正常",
        "fasting_status": "禁食禁饮已核对", "anesthesia_history": "否认麻醉史", "risk_discussion": "已完成麻醉风险告知"},
    "postane_surveil_record": {"consciousness_status": "神志清醒", "respiratory_status": "呼吸平稳",
        "circulatory_status": "循环稳定", "complication_assessment": "无麻醉并发症"},
}


class FrozenFactClient:
    def __init__(self, *, absent=(), unknown=(), mode="valid", overrides=None):
        self.absent, self.unknown, self.mode = set(absent), set(unknown), mode
        self.overrides = overrides or {}
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.mode == "transport":
            raise RuntimeError("synthetic transport failure")
        documents = read_sent_anesthesia_documents(prompt)
        items = []
        for doc in documents:
            fields = {}
            for field in doc["required_fields"]:
                key = (doc["source_type"], field)
                if key in self.unknown:
                    atom = {"state": "unknown", "span_id": None, "start": None, "end": None, "quote": None}
                elif key in self.absent:
                    atom = {"state": "absent", "span_id": None, "start": 0, "end": len(doc["body"]), "quote": None}
                else:
                    quote = self.overrides.get(key, GOLD_QUOTES[doc["source_type"]][field])
                    start = doc["body"].index(quote)
                    span_id = next(sid for sid, span in doc["spans"].items() if quote in span)
                    atom = {"state": "present", "span_id": span_id, "start": start, "end": start + len(quote), "quote": quote}
                fields[field] = atom
            items.append({"document_ref": doc["document_ref"], "fields": fields})
        payload = {"schema_version": "lx0609-anesthesia-visit-facts-v1", "documents": items}
        if self.mode == "bad_schema":
            payload["schema_version"] = "invalid"
        elif self.mode == "duplicate_doc":
            payload["documents"].append(items[0])
        elif self.mode == "missing_field":
            items[0]["fields"].pop(next(iter(items[0]["fields"])))
        elif self.mode == "extra_field":
            items[0]["fields"]["invented_required_field"] = {"state": "unknown", "span_id": None, "start": None, "end": None, "quote": None}
        elif self.mode == "cross_document_quote":
            atom = items[0]["fields"]["airway_assessment"]
            atom.update(quote="神志清醒", start=0, end=4)
        elif self.mode == "wrong_absent_scope":
            items[1]["fields"]["consciousness_status"] = {"state": "absent", "span_id": None, "start": 0, "end": 1, "quote": None}
        elif self.mode == "cross_document_span":
            items[0]["fields"]["airway_assessment"]["span_id"] = next(iter(documents[1]["spans"]))
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


async def _run(rows, client):
    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=tuple(rows.get(key, ())), truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(selected_rule_ids=(RULE,), institute_id="synthetic", patient_id="synthetic", visit_id="synthetic", source_schema=None, created_at="2026-07-10T12:00:00", row_reader=reader)
    execution = await execute_luxian_0609_native_surgery_document_rules(rule_ids=(RULE,), decision_rule_ids=(RULE,), wrapper_rules=[], evidence_payload=None, llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=execution.decisions, expected_rule_ids=(RULE,), snapshot=session.snapshot, evidence_materials=session.materials)
    final = finalize_luxian_0609_reduced_customer_result(decision=reduced[0], raw_customer_display_facts=dict(execution.customer_display_facts).get(RULE), evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    assert final["status"] == reduced[0].final_state.value
    if client is not None:
        assert len(client.calls) <= 1
        for _prompt, kwargs in client.calls:
            assert kwargs["allow_length_retry"] is False
            assert 0 < kwargs["max_completion_tokens"] <= 4096
    return final, execution


def test_only_n12_contract_explicitly_authorizes_one_controlled_call():
    contract = next(c for c in load_luxian_0609_rule_contracts() if c.rule_id == RULE)
    assert contract.contract_version == "v3"
    assert contract.decision_authority == "program_then_optional_llm"
    assert contract.max_llm_calls_per_rule == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("source,field,old,new,visit", [
    ("postane_surveil_record", "consciousness_status", "神志清醒", "术后意识状态：", "postanesthesia_visit"),
    ("postane_surveil_record", "respiratory_status", "呼吸平稳", "术后呼吸情况：", "postanesthesia_visit"),
    ("postane_surveil_record", "complication_assessment", "无麻醉并发症", "术后并发症情况：", "postanesthesia_visit"),
    ("preane_surveil_record", "airway_assessment", "气道评估正常", "Mallampati气道分级：", "preanesthesia_visit"),
])
async def test_original_n12_empty_labels_remain_original_input_and_are_missing(source, field, old, new, visit):
    rows = _visits()
    rows[source][0]["record_content"] = rows[source][0]["record_content"].replace(old, new)
    client = FrozenFactClient(absent=((source, field),))
    final, execution = await _run(rows, client)
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["missing_fields_by_visit"] == {visit: [field]}
    assert execution.llm_call_count == len(client.calls) == 1
    assert execution.total_tokens == 15
    assert client.calls[0][1]["allow_length_retry"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", [None, "心率：", "后续项目：", "心率：___", "心率：80次/分"])
async def test_original_normal_negatives_and_adjacent_unrelated_labels_stay_compliant(suffix):
    rows = _visits()
    if suffix is not None:
        rows["postane_surveil_record"][0]["record_content"] = "神志清醒" + suffix + "；呼吸平稳；循环稳定；无麻醉并发症。"
    client = FrozenFactClient()
    final, execution = await _run(rows, client)
    assert final["status"] == "compliant"
    assert execution.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["transport", "bad_schema", "duplicate_doc", "missing_field", "extra_field", "cross_document_quote", "wrong_absent_scope", "cross_document_span"])
async def test_invalid_or_failed_controlled_facts_never_claim_filled_or_complete(mode):
    final, execution = await _run(_visits(), FrozenFactClient(mode=mode))
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == 1
    assert "checked_fields_by_visit" not in final.get("customer_display_facts", {})
    assert "missing_fields_by_visit" not in final.get("customer_display_facts", {})


@pytest.mark.asyncio
async def test_unknown_semantics_never_becomes_a_definite_missing_field():
    client = FrozenFactClient(unknown=(("postane_surveil_record", "consciousness_status"),))
    final, execution = await _run(_visits(), client)
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == 1
    assert "missing_fields_by_visit" not in final.get("customer_display_facts", {})


@pytest.mark.asyncio
async def test_no_client_closes_as_data_gap_without_a_hidden_call():
    final, execution = await _run(_visits(), None)
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_explicit_cross_event_records_stop_before_model():
    rows = _visits()
    rows["postane_surveil_record"][0]["application_id"] = "B"
    client = FrozenFactClient()
    final, execution = await _run(rows, client)
    assert (final["status"], final["reason_code"]) == ("data_gap", "association_failed")
    assert execution.llm_call_count == len(client.calls) == 0


@pytest.mark.asyncio
async def test_trusted_structural_empty_body_does_not_need_model_or_invent_filled_fields():
    rows = _visits()
    for source in ("preane_surveil_record", "postane_surveil_record"):
        rows[source][0]["record_content"] = ""
    rows["preane_surveil_record"][0]["ASA_level"] = "II级"
    client = FrozenFactClient()
    final, execution = await _run(rows, client)
    assert final["status"] == "non_compliant"
    assert "asa_level" not in final["customer_display_facts"]["missing_fields_by_visit"]["preanesthesia_visit"]
    assert execution.llm_call_count == len(client.calls) == 0


@pytest.mark.asyncio
async def test_unknown_in_same_receipt_blocks_a_definite_missing_result():
    client = FrozenFactClient(absent=(("preane_surveil_record", "airway_assessment"),), unknown=(("postane_surveil_record", "consciousness_status"),))
    final, execution = await _run(_visits(), client)
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == 1
    assert "missing_fields_by_visit" not in final.get("customer_display_facts", {})


def test_final_compiled_prompt_version_and_definition_are_consistent():
    from app.services.luxian_0609_rule_master import LUXIAN_0609_RULE_DEFINITION_VERSION
    contract = next(c for c in load_luxian_0609_rule_contracts() if c.rule_id == RULE)
    assert contract.prompt_version == "lx0609-anesthesia-visit-facts-v1"
    assert contract.definition_version == LUXIAN_0609_RULE_DEFINITION_VERSION
    assert contract.max_llm_calls_per_rule == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["no_client", "unknown", "transport"])
async def test_semantic_gap_does_not_claim_a_doctor_missing_field(failure):
    if failure == "no_client":
        client = None
    elif failure == "unknown":
        client = FrozenFactClient(unknown=(("postane_surveil_record", "consciousness_status"),))
    else:
        client = FrozenFactClient(mode="transport")
    final, _execution = await _run(_visits(), client)
    assert (final["status"], final["reason_code"]) == ("data_gap", "semantic_extraction_unresolved")
    assert "missing_fields_by_visit" not in final.get("customer_display_facts", {})


async def _source_gap_run(rows, client, mode):
    from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable

    def reader(**kwargs):
        key = kwargs["source_key"]
        if key == "preane_surveil_record" and mode == "unavailable":
            raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(source_key=key, rows=tuple(rows.get(key, ())), truncated=(key == "preane_surveil_record" and mode == "truncated"), limit_rows=50)
    session = build_luxian_0609_evidence_read_session(selected_rule_ids=(RULE,), institute_id="synthetic", patient_id="synthetic", visit_id="synthetic", source_schema=None, created_at="2026-07-10T12:00:00", row_reader=reader)
    execution = await execute_luxian_0609_native_surgery_document_rules(rule_ids=(RULE,), decision_rule_ids=(RULE,), wrapper_rules=[], evidence_payload=None, llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=execution.decisions, expected_rule_ids=(RULE,), snapshot=session.snapshot, evidence_materials=session.materials)
    assert reduced[0].final_state.value == "data_gap"
    assert execution.llm_call_count == len(client.calls) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["unavailable", "truncated"])
async def test_source_unavailable_or_incomplete_closes_before_model(mode):
    await _source_gap_run(_visits(), FrozenFactClient(), mode)


@pytest.mark.asyncio
@pytest.mark.parametrize("flag,value", [("record_content_truncated", True), ("record_content_complete", False)])
async def test_explicit_body_scope_failure_closes_before_model(flag, value):
    rows = _visits()
    rows["preane_surveil_record"][0][flag] = value
    client = FrozenFactClient()
    final, execution = await _run(rows, client)
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == len(client.calls) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["documents", "single_body", "total_body"])
async def test_candidate_scope_limits_close_before_model_without_dropping_records(mode):
    rows = _visits()
    pre = rows["preane_surveil_record"][0]
    if mode == "documents":
        rows["preane_surveil_record"] = [{**pre, "document_id": f"pre-{index}"} for index in range(8)]
    elif mode == "single_body":
        pre["record_content"] += "。" * (6001 - len(pre["record_content"]))
    else:
        body = pre["record_content"] + "。" * (4000 - len(pre["record_content"]))
        rows["preane_surveil_record"] = [{**pre, "document_id": f"pre-{index}", "record_content": body} for index in range(2)]
        post = rows["postane_surveil_record"][0]
        post["record_content"] += "。" * (4001 - len(post["record_content"]))
    client = FrozenFactClient()
    final, execution = await _run(rows, client)
    assert (final["status"], final["reason_code"]) == ("data_gap", "candidate_scope_incomplete")
    assert execution.llm_call_count == len(client.calls) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [None, 123])
async def test_unavailable_or_nonstring_body_does_not_become_a_full_document(body):
    rows = _visits()
    rows["preane_surveil_record"][0]["record_content"] = body
    client = FrozenFactClient()
    final, execution = await _run(rows, client)
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == len(client.calls) == 0
