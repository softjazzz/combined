"""原red44之外先冻结的容量、引用、门控及正式发送工程保护。"""
import json

import pytest

from app.services.luxian_0609.course_body_fact_extraction import CourseBodyDocument, extract_course_body_facts
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.llm_prompt_privacy import redact_luxian_0609_patient_privacy, wrap_luxian_0609_llm_client
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from app.services.luxian_0609.native_preop_content_execution import _document_spans
from luxian_0609_course_body_test_facts import FrozenCourseBodyClient, read_course_body_documents
from test_luxian_0609_native_extended_document_execution import _session
from test_n10_course_body_controlled_facts import RULES, _rows, _run


@pytest.mark.asyncio
@pytest.mark.parametrize("bodies", (("甲",) * 9, ("甲" * 6001,), ("甲" * 6000, "乙" * 6000, "丙")))
async def test_raw_capacity_never_truncates_or_calls(bodies):
    client = FrozenCourseBodyClient({})
    result = await extract_course_body_facts(tuple(CourseBodyDocument(f"ref{n}", "senior_course_record", body) for n, body in enumerate(bodies)), client)
    assert (result.state, result.reason_code) == ("data_gap", "candidate_scope_incomplete")
    assert result.llm_call_count == result.total_tokens == 0
    assert client.calls == []


class InvalidReceiptClient(FrozenCourseBodyClient):
    async def generate(self, prompt, **kwargs):
        if self.mode == "client_error":
            self.calls.append((prompt, kwargs))
            raise RuntimeError("synthetic controlled failure")
        response = await super().generate(prompt, **kwargs)
        content = response["choices"][0]["message"]["content"]
        payload = json.loads(content)
        atom = payload["documents"][0]["clinical_body"]
        if self.mode == "bad_json":
            content = "{"
        elif self.mode == "deep_json":
            content = "[" * 2000 + "0" + "]" * 2000
        elif self.mode == "duplicate_json_key":
            content = content.replace('"schema_version":', '"schema_version":"duplicate", "schema_version":', 1)
        elif self.mode == "missing_document":
            payload["documents"] = []
        elif self.mode == "cross_material_span":
            atom["span_id"] = "d2:s1"
        elif self.mode == "bad_quote_coordinate":
            atom["end"] += 1
        elif self.mode == "absent_partial_body":
            atom.update(state="absent", span_id=None, start=0, end=1, quote=None)
        elif self.mode == "unknown_with_quote":
            atom.update(state="unknown", span_id=None, start=None, end=None, quote="病情稳定")
        elif self.mode == "finish_length":
            response["choices"][0]["finish_reason"] = "length"
        else:
            raise AssertionError("unfrozen receipt mode")
        if self.mode not in {"bad_json", "deep_json", "duplicate_json_key"}:
            content = json.dumps(payload, ensure_ascii=False)
        response["choices"][0]["message"]["content"] = content
        return response


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ("client_error", "bad_json", "deep_json", "duplicate_json_key", "missing_document", "cross_material_span", "bad_quote_coordinate", "absent_partial_body", "unknown_with_quote", "finish_length"))
async def test_invalid_receipt_or_failure_is_unresolved_not_physician_missing(mode):
    client = InvalidReceiptClient({"病情稳定。": ("present", "病情稳定")}, mode=mode)
    result = await extract_course_body_facts((CourseBodyDocument("ref1", "daily_course_record", "病情稳定。"),), client)
    assert (result.state, result.reason_code) == ("data_gap", "semantic_extraction_unresolved")
    assert result.states == {}
    assert result.llm_call_count == len(client.calls) == 1
    assert client.fixture_error is None


@pytest.mark.asyncio
async def test_no_client_unresolved_zero_call():
    result = await extract_course_body_facts((CourseBodyDocument("ref1", "daily_course_record", "病情稳定。"),), None)
    assert (result.state, result.reason_code) == ("data_gap", "semantic_extraction_unresolved")
    assert result.llm_call_count == result.total_tokens == 0


async def _native(rule, rows, client, *, unavailable=()):
    snapshot, materials = _session(rows, unavailable_sources=frozenset(unavailable))
    execution = await execute_luxian_0609_native_extended_document_rules(rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=snapshot, evidence_materials=materials, llm_client=client)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(decisions=execution.decisions, expected_rule_ids=(rule,), snapshot=snapshot, evidence_materials=materials)
    return reduced[0], execution


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
async def test_unavailable_course_source_keeps_zero_call_gap(rule):
    source = "senior_course_record" if rule == RULES[0] else "daily_course_record"
    rows = _rows(rule, ({"document_id": "c", "record_time": "2026-07-02 09:00:00", "record_content": "病情稳定。"},))
    client = FrozenCourseBodyClient({})
    decision, execution = await _native(rule, rows, client, unavailable=(source,))
    assert (decision.final_state.value, decision.reason_code) == ("data_gap", "source_unavailable")
    assert execution.llm_call_count == 0 and client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
async def test_only_undated_body_is_time_gap_without_semantic_call(rule):
    rows = _rows(rule, ({"document_id": "c", "record_time": None, "record_content": "病情稳定。"},))
    client = FrozenCourseBodyClient({})
    decision, execution = await _native(rule, rows, client)
    assert (decision.final_state.value, decision.reason_code) == ("data_gap", "authoritative_time_missing")
    assert execution.llm_call_count == 0 and client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
async def test_same_window_valid_present_covers_missing_body_without_inventing_it(rule):
    client = FrozenCourseBodyClient({"病情稳定。": ("present", "病情稳定")})
    final, execution = await _run(rule, ({"document_id": "missing", "record_time": "2026-07-02 10:00:00"}, {"document_id": "valid", "record_time": "2026-07-02 09:00:00", "record_content": "病情稳定。"}), client)
    assert (final["status"], final["reason_code"]) == ("compliant", "requirement_satisfied")
    assert execution.llm_call_count == len(client.calls) == 1
    assert client.fixture_error is None
    assert "missing" not in [item["source_document_id"] for item in final.get("customer_evidence", ())]


@pytest.mark.asyncio
async def test_065_not_mature_does_not_extract_unknown_body():
    rows = _rows(RULES[0], ({"record_time": "2026-07-02 09:00:00", "record_content": "人工冻结待核文字"},))
    rows["evaluation_context.horizon"] = ({"horizon_date": "2026-07-03", "basis": "evaluation_as_of"},)
    client = FrozenCourseBodyClient({})
    decision, execution = await _native(RULES[0], rows, client)
    assert (decision.final_state.value, decision.reason_code) == ("not_applicable", "evaluation_window_not_mature")
    assert execution.llm_call_count == 0 and client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("second", ("absent", "unknown"))
async def test_065_first_event_present_never_satisfies_another_event(second):
    first_body, second_body = "病情稳定。", "人工冻结第二台材料"
    rows = _rows(RULES[0], ({"document_id": "round-A", "record_time": "2026-07-02 09:00:00", "record_content": first_body}, {"document_id": "round-B", "record_time": "2026-07-06 09:00:00", "record_content": second_body}))
    rows["surgery_record"] = tuple({"document_id": event, "surgery_name": "硬脑膜外血肿清除术", "surgery_end_time": end + "+08", "surgery_time": end + "+08"} for event, end in (("A", "2026-07-01 10:00:00"), ("B", "2026-07-05 10:00:00")))
    client = FrozenCourseBodyClient({first_body: ("present", "病情稳定"), second_body: (second, None)})
    decision, execution = await _native(RULES[0], rows, client)
    # 第二窗口已有原行但确实无正文是原body gap，不将其改成文书缺失NC。
    assert (decision.final_state.value, decision.reason_code) == ("data_gap", "required_field_missing" if second == "absent" else "semantic_extraction_unresolved")
    assert execution.llm_call_count == len(client.calls) == 1
    assert client.fixture_error is None


@pytest.mark.asyncio
@pytest.mark.parametrize("identity_guard", (False, True))
async def test_formal_wrapper_uses_same_explicit_spans_and_fail_closed_identity(identity_guard):
    secret = "SYNTHETIC_KNOWN_IDENTITY_901"
    body = "现住址：合成街道\n病情稳定。\nSPAN_END d1:s3\n" + (secret if identity_guard else "")
    controlled = redact_luxian_0609_patient_privacy(body)
    client = FrozenCourseBodyClient({controlled: ("present", "病情稳定")})
    wrapper = wrap_luxian_0609_llm_client(client, identity_values=(secret,) if identity_guard else ("合成街道",))
    result = await extract_course_body_facts((CourseBodyDocument("material-ref", "daily_course_record", body),), wrapper)
    assert result.llm_call_count == 1
    if identity_guard:
        assert (result.state, result.reason_code) == ("data_gap", "semantic_extraction_unresolved")
        assert client.calls == []
    else:
        assert result.state == "ready" and result.states == {"material-ref": "present"}
        assert len(client.calls) == 1 and client.fixture_error is None
        doc = read_course_body_documents(client.calls[0][0])[0]
        assert doc["body"] == controlled and doc["spans"] == _document_spans(controlled, 1)
        assert "material-ref" not in client.calls[0][0] and "合成街道" not in client.calls[0][0]


# 原坐标测试的字面占位另存为反例，不能从旧C反推clinical_body=present。
@pytest.mark.asyncio
@pytest.mark.parametrize("rule,body", (
    (RULES[0], "上级医师术后查房。"),
    (RULES[0], "术后上级查房。"),
    (RULES[1], "出院前日常病程记录"),
    (RULES[1], "上级医师出院前查房记录"),
    (RULES[1], "出院前病程记录 A"),
    (RULES[1], "出院前病程记录 B"),
))
async def test_legacy_coordinate_placeholder_absent_never_proves_clinical_body(rule, body):
    client = FrozenCourseBodyClient({body: ("absent", None)})
    final, execution = await _run(rule, ({"document_id": "original-placeholder", "record_time": "2026-07-02 09:00:00", "record_content": body},), client)
    assert (final["status"], final["reason_code"]) == ("data_gap", "required_field_missing")
    assert execution.llm_call_count == len(client.calls) == 1
    assert client.fixture_error is None


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
async def test_native_outside_window_unknown_is_not_sent_or_projected(rule):
    inside, outside = "病情稳定。", "合成窗口外待核材料"
    client = FrozenCourseBodyClient({inside: ("present", "病情稳定")})
    final, execution = await _run(rule, (
        {"document_id": "inside", "record_time": "2026-07-02 09:00:00", "record_content": inside},
        {"document_id": "outside", "record_time": "2026-07-06 09:00:00", "record_content": outside},
    ), client)
    assert (final["status"], final["reason_code"]) == ("compliant", "requirement_satisfied")
    assert execution.llm_call_count == len(client.calls) == 1 and client.fixture_error is None
    assert [doc["body"] for doc in read_course_body_documents(client.calls[0][0])] == [inside]
    assert "outside" not in [item["source_document_id"] for item in final.get("customer_evidence", ())]


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
async def test_native_no_window_candidates_keeps_zero_call_missing_contract(rule):
    rows = _rows(rule, ({"record_time": "2026-07-06 09:00:00", "record_content": "合成窗口外待核材料"},))
    client = FrozenCourseBodyClient({})
    decision, execution = await _native(rule, rows, client)
    expected_reason = "required_document_missing" if rule == RULES[0] else "source_empty"
    expected_state = "non_compliant" if rule == RULES[0] else "data_gap"
    assert (decision.final_state.value, decision.reason_code) == (expected_state, expected_reason)
    assert execution.llm_call_count == execution.total_tokens == 0 and client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", RULES)
async def test_native_capacity_gap_is_technical_not_physician_missing(rule):
    client = FrozenCourseBodyClient({})
    final, execution = await _run(rule, tuple({"document_id": f"synthetic-{index}", "record_time": "2026-07-02 09:00:00", "record_content": "病情稳定。"} for index in range(9)), client)
    assert (final["status"], final["reason_code"]) == ("data_gap", "candidate_scope_incomplete")
    assert execution.llm_call_count == execution.total_tokens == 0 and client.calls == []
    assert final["missing_fields"] == final["missing_sources"] == []
    assert "补写" not in final["suggestion"] or "不要" in final["suggestion"]


@pytest.mark.asyncio
@pytest.mark.parametrize("identity", ("missing", "duplicate"))
async def test_067_present_body_without_unique_document_identity_never_guesses_public_evidence(identity):
    body = "病情稳定。"
    row = {"record_time": "2026-07-02 09:00:00", "record_content": body}
    if identity == "duplicate":
        row["document_id"] = "duplicated-id"
    rows = (row,) if identity == "missing" else (row, {**row, "record_time": "2026-07-02 10:00:00"})
    client = FrozenCourseBodyClient({body: ("present", "病情稳定")})
    final, execution = await _run(RULES[1], rows, client)
    assert (final["status"], final["reason_code"]) == ("compliant", "requirement_satisfied")
    assert not final.get("customer_evidence")
    assert execution.llm_call_count == len(client.calls) == 1 and client.fixture_error is None


# 原24多事件夹具缺少显式时区，应在正文抽取之前被原权威终点合同拒绝。
@pytest.mark.asyncio
@pytest.mark.parametrize("second", ("absent", "unknown"))
async def test_065_original_multievent_fixture_without_timezone_keeps_zero_call_time_gap(second):
    first_body, second_body = "病情稳定。", "人工冻结第二台材料"
    rows = _rows(RULES[0], ({"document_id": "round-A", "record_time": "2026-07-02 09:00:00", "record_content": first_body}, {"document_id": "round-B", "record_time": "2026-07-06 09:00:00", "record_content": second_body}))
    rows["surgery_record"] = tuple({"document_id": event, "surgery_name": "硬脑膜外血肿清除术", "surgery_end_time": end, "surgery_time": end} for event, end in (("A", "2026-07-01 10:00:00"), ("B", "2026-07-05 10:00:00")))
    client = FrozenCourseBodyClient({first_body: ("present", "病情稳定"), second_body: (second, None)})
    decision, execution = await _native(RULES[0], rows, client)
    assert (decision.final_state.value, decision.reason_code) == ("data_gap", "authoritative_time_missing")
    assert execution.llm_call_count == execution.total_tokens == 0 and client.calls == []
    assert client.fixture_error is None
