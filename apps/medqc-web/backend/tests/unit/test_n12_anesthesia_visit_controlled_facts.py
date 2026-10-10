"""N12预先冻结工程合同：原输入不变，受控Fake只给原子事实。"""


import pytest
from luxian_0609_anesthesia_test_facts import (
    POST_TEXT,
    SCHEMA_VERSION,
    anesthesia_fact_atom,
    anesthesia_fact_response,
    read_sent_anesthesia_documents,
)

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from tests.unit.test_luxian_0609_round2_document_boundaries import _visits


RULE = "LX0609-04-04-02"
class FrozenFactClient:
    def __init__(self, *, absent=(), unknown=(), mode="valid", overrides=None):
        self.absent, self.unknown, self.mode = frozenset(absent), frozenset(unknown), mode
        self.overrides = overrides or {}
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.mode == "transport":
            raise RuntimeError("synthetic transport failure")
        documents = read_sent_anesthesia_documents(prompt)
        items = [{"document_ref": doc["document_ref"], "fields": {
            field: anesthesia_fact_atom(doc, field, absent=self.absent, unknown=self.unknown, overrides=self.overrides)
            for field in doc["required_fields"]}} for doc in documents]
        payload = {"schema_version": SCHEMA_VERSION, "documents": items}
        if self.mode == "bad_schema":
            payload["schema_version"] = "invalid"
        elif self.mode == "duplicate_doc":
            payload["documents"].append(items[0])
        elif self.mode == "missing_field":
            items[0]["fields"].pop(next(iter(items[0]["fields"])))
        elif self.mode == "extra_field":
            items[0]["fields"]["invented_required_field"] = {"state": "unknown", "quote": None}
        elif self.mode == "cross_document_quote":
            # 术前字段借用术后访视原文。
            items[0]["fields"]["precautions"] = {"state": "present", "quote": "神志清醒"}
        elif self.mode == "absent_with_quote":
            items[1]["fields"]["consciousness_status"] = {"state": "absent", "quote": "神志清醒"}
        elif self.mode == "not_applicable_disallowed":
            items[1]["fields"]["consciousness_status"] = {"state": "not_applicable", "quote": "神志清醒"}
        return anesthesia_fact_response(payload)


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
    ("postane_surveil_record", "recovery_status", "恢复良好，呼吸循环稳定", "恢复情况：", "postanesthesia_visit"),
    ("postane_surveil_record", "special_situations", "无麻醉并发症", "特殊情况：", "postanesthesia_visit"),
    ("preane_surveil_record", "relevant_examinations", "血常规、凝血功能未见异常", "", "preanesthesia_visit"),
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
        rows["postane_surveil_record"][0]["record_content"] = POST_TEXT.replace("神志清醒", "神志清醒" + suffix, 1)
    client = FrozenFactClient()
    final, execution = await _run(rows, client)
    assert final["status"] == "compliant"
    assert execution.llm_call_count == len(client.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["transport", "bad_schema", "duplicate_doc", "missing_field", "extra_field", "cross_document_quote", "absent_with_quote", "not_applicable_disallowed"])
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
    client = FrozenFactClient()
    final, execution = await _run(rows, client)
    assert final["status"] == "non_compliant"
    missing = final["customer_display_facts"]["missing_fields_by_visit"]
    # 结构化可信的签名、时间与术后48小时内访视不需送模，也不被判缺失。
    assert "anesthetist_signature" not in missing["preanesthesia_visit"]
    assert "record_time" not in missing["postanesthesia_visit"]
    assert "visit_within_48h" not in missing["postanesthesia_visit"]
    assert "general_condition" in missing["preanesthesia_visit"]
    assert execution.llm_call_count == len(client.calls) == 0


@pytest.mark.asyncio
async def test_structured_visit_columns_are_sent_as_document_text():
    rows = _visits()
    rows["preane_surveil_record"][0]["record_content"] = ""
    rows["preane_surveil_record"][0]["planned_anesthesia_method"] = "全身麻醉"
    client = FrozenFactClient()
    await _run(rows, client)
    sent = read_sent_anesthesia_documents(client.calls[0][0])
    assert any(doc["body"] == "拟施麻醉方式：全身麻醉" for doc in sent)


@pytest.mark.asyncio
async def test_unknown_in_same_receipt_blocks_a_definite_missing_result():
    client = FrozenFactClient(absent=(("preane_surveil_record", "precautions"),), unknown=(("postane_surveil_record", "consciousness_status"),))
    final, execution = await _run(_visits(), client)
    assert final["status"] == "data_gap"
    assert execution.llm_call_count == 1
    assert "missing_fields_by_visit" not in final.get("customer_display_facts", {})


def test_final_compiled_prompt_version_and_definition_are_consistent():
    from app.services.luxian_0609_rule_master import LUXIAN_0609_RULE_DEFINITION_VERSION
    contract = next(c for c in load_luxian_0609_rule_contracts() if c.rule_id == RULE)
    assert contract.prompt_version == "lx0609-anesthesia-visit-facts-v2"
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


@pytest.mark.asyncio
async def test_postanesthesia_visit_after_48_hours_is_a_missing_timeliness_item():
    rows = _visits()
    # 手术 07-01 10:00 结束，术后访视 07-03 11:00 已超过48小时。
    rows["postane_surveil_record"][0]["record_time"] = "2026-07-03 11:00:00"
    client = FrozenFactClient()
    final, execution = await _run(rows, client)
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["missing_fields_by_visit"] == {"postanesthesia_visit": ["visit_within_48h"]}
    assert "术后48小时内访视" in final["findings"]
    assert execution.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["no_surgery_row", "no_end_time"])
async def test_missing_surgery_end_time_cannot_verify_48_hour_visit(mode):
    rows = _visits()
    if mode == "no_surgery_row":
        rows.pop("surgery_record")
    else:
        rows["surgery_record"][0].pop("surgery_end_time")
    client = FrozenFactClient()
    final, execution = await _run(rows, client)
    assert (final["status"], final["reason_code"]) == ("data_gap", "authoritative_time_missing")
    assert execution.llm_call_count == len(client.calls) == 0


@pytest.mark.asyncio
async def test_running_record_without_front_page_uses_surgery_record_end_time():
    """运行病历质控时病案首页尚未生成：只凭手术记录结束时间即可核对48小时。"""
    rows = _visits()
    assert "mr_surgery" not in rows
    final, _execution = await _run(rows, FrozenFactClient())
    assert final["status"] == "compliant"


@pytest.mark.asyncio
async def test_front_page_end_time_is_only_a_fallback_for_untimed_surgery_record():
    rows = _visits()
    rows["surgery_record"][0].pop("surgery_end_time")
    rows["mr_surgery"] = [{"surgery_id": "S-A", "anesthesia_method": "全身麻醉",
                           "surgery_begin_datetime": "2026-07-01 08:00:00", "surgery_end_datetime": "2026-07-01 10:00:00"}]
    final, _execution = await _run(rows, FrozenFactClient())
    assert final["status"] == "compliant"
    # 手术记录写明结束时间时以手术记录为准，不被病案首页覆盖。
    rows = _visits()
    rows["mr_surgery"] = [{"surgery_id": "S-A", "anesthesia_method": "全身麻醉",
                           "surgery_begin_datetime": "2026-06-28 08:00:00", "surgery_end_datetime": "2026-06-28 10:00:00"}]
    final, _execution = await _run(rows, FrozenFactClient())
    assert final["status"] == "compliant"


@pytest.mark.asyncio
async def test_extubation_not_applicable_without_intubation_stays_compliant():
    class NotIntubatedClient(FrozenFactClient):
        async def generate(self, prompt, **kwargs):
            response = await super().generate(prompt, **kwargs)
            import json as _json
            payload = _json.loads(response["choices"][0]["message"]["content"])
            for item in payload["documents"]:
                if "extubation_status" in item["fields"]:
                    item["fields"]["extubation_status"] = {"state": "not_applicable", "quote": "神志清醒"}
            response["choices"][0]["message"]["content"] = _json.dumps(payload, ensure_ascii=False)
            return response

    final, execution = await _run(_visits(), NotIntubatedClient())
    assert final["status"] == "compliant"
    assert execution.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("quote,expected", [
    # 真实模型曾跳过中间一句拼接两段原文：逐句均来自本文书时接受。
    ("神志清醒。无麻醉并发症", "compliant"),
    # 任一句不是本文书原文即拒收整批。
    ("神志清醒。术后无任何不适", "data_gap"),
])
async def test_stitched_quote_is_accepted_only_when_every_sentence_is_verbatim(quote, expected):
    client = FrozenFactClient(overrides={("postane_surveil_record", "special_situations"): quote})

    original = client.generate

    async def generate(prompt, **kwargs):
        import json as _json
        response = await original(prompt, **kwargs)
        payload = _json.loads(response["choices"][0]["message"]["content"])
        for item in payload["documents"]:
            if "special_situations" in item["fields"]:
                item["fields"]["special_situations"]["quote"] = quote
        response["choices"][0]["message"]["content"] = _json.dumps(payload, ensure_ascii=False)
        return response

    client.generate = generate
    final, _execution = await _run(_visits(), client)
    assert final["status"] == expected
