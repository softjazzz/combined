from __future__ import annotations

import asyncio
from copy import deepcopy
from inspect import isawaitable
import json

import pytest

from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_basic_timeliness import (
    EXECUTABLE_BASIC_TIMELINESS_RULE_IDS,
    execute_luxian_0609_native_basic_timeliness,
)
from app.services.luxian_0609.rescue_record_completeness import (
    MAX_COMPLETION_TOKENS,
    RESCUE_COMPLETENESS_RULE_ID as RULE,
    RESCUE_CONTENT_FIELDS,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY as ORDERS,
    SourceEvidenceUnavailable,
)


OLD = "LX0609-09-01-01"
ROUND = "LX0609-02-01-02"
SNIPPETS = {
    "condition_change": "病情变化：突发呼吸困难。",
    "rescue_time": "抢救时间：2026-07-16 09:00。",
    "rescue_measures": "抢救措施：立即给予吸氧并监测生命体征。",
    "rescue_outcome": "抢救结果：呼吸困难改善，生命体征稳定。",
    "participant_names": "参加人员姓名：测试医师甲。",
    "participant_titles": "测试医师甲的专业技术职称：主治医师。",
}


def _row(document_id="R1", *, missing=(), body=None, **extra):
    return {
        "document_id": document_id, "document_title": "抢救记录",
        "record_time": "2026-07-16 10:00:00",
        "record_content": body if body is not None else "\n".join(value for key, value in SNIPPETS.items() if key not in missing),
        **extra,
    }


def _session(rows=(), *, failures=(), truncated=(), orders=(), extra=None):
    sources = {"rescue_record": list(rows), ORDERS: list(orders), **(extra or {})}

    def reader(**kwargs):
        source = kwargs["source_key"]
        if source in failures:
            raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(
            source_key=source, rows=sources.get(source, []),
            truncated=source in truncated, limit_rows=50,
        )

    # 用现有来源合同建同一会话，使本测试独立于目录注册工作。
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(OLD, ROUND), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-07-20T12:00:00+08:00",
        evaluation_as_of_date="2026-07-20", row_reader=reader,
        additional_source_keys=("rescue_record", ORDERS),
    )


def _response(session, *, missing_by_id=None, unknown_by_id=None):
    items = []
    for ref, row in session.materials.document_rows("rescue_record", snapshot=session.snapshot):
        body = row["record_content"]
        if not body or row.get("content_truncated") or row.get("content_complete") is False:
            continue
        fields = {}
        for key, quote in SNIPPETS.items():
            if key in (unknown_by_id or {}).get(row["document_id"], ()):
                fields[key] = {"state": "unknown", "start": None, "end": None, "quote": None}
            elif key in (missing_by_id or {}).get(row["document_id"], ()):
                fields[key] = {"state": "absent", "start": 0, "end": len(body), "quote": None}
            else:
                start = body.index(quote)
                fields[key] = {"state": "present", "start": start, "end": start + len(quote), "quote": quote}
        items.append({"document_ref": ref, "fields": fields})
    return {"schema_version": "lx0609-rescue-content-v1", "documents": items}


class FakeLLM:
    def __init__(self, payload=None, *, failure=False):
        self.payload = payload
        self.failure = failure
        self.calls = []

    def supports_strict_json_schema(self):
        return True

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.failure:
            raise TimeoutError("synthetic timeout")
        return {
            "content": json.dumps(self.payload, ensure_ascii=False),
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            "response_time": 0.2,
        }


def _execute(session, llm=None, rules=(RULE,)):
    result = execute_luxian_0609_native_basic_timeliness(
        rule_ids=rules, decision_rule_ids=rules, evidence_payload=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials, llm_client=llm,
    )
    return asyncio.run(result) if isawaitable(result) else result


def _state(result):
    decision = next(item for item in result.decisions if item.rule_id == RULE)
    return reduce_luxian_0609_rule_decision(decision).final_state.value


def _facts(result):
    return dict(result.customer_display_facts)[RULE]


def test_complete_body_with_empty_structured_fields_is_compliant_and_one_bounded_call():
    session = _session([_row(rescue_measures=None, rescue_outcome="", submitter="不作为参与者证据")])
    llm = FakeLLM(_response(session))
    result = _execute(session, llm)
    assert _state(result) == "compliant"
    assert result.llm_call_count == len(llm.calls) == 1
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens, result.api_time) == (100, 20, 120, 0.2)
    prompt, kwargs = llm.calls[0]
    assert "不作为参与者证据" not in prompt
    assert kwargs["max_completion_tokens"] == MAX_COMPLETION_TOKENS
    assert kwargs["allow_length_retry"] is False
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert _facts(result)["missing_fields"] == []
    assert set(_facts(result)["rescue_content_events"][0]["field_facts"]) == set(RESCUE_CONTENT_FIELDS)


@pytest.mark.parametrize("missing", list(RESCUE_CONTENT_FIELDS))
def test_each_missing_field_in_complete_body_is_a_proven_defect(missing):
    session = _session([_row(missing=(missing,))])
    result = _execute(session, FakeLLM(_response(session, missing_by_id={"R1": (missing,)})))
    assert _state(result) == "non_compliant"
    assert _facts(result)["missing_fields"] == [missing]


def test_python_labeled_time_prevents_model_false_absence():
    session = _session([_row()])
    result = _execute(session, FakeLLM(_response(session, missing_by_id={"R1": ("rescue_time",)})))
    assert _state(result) == "compliant"
    assert _facts(result)["rescue_content_events"][0]["field_facts"]["rescue_time"]["quote"].startswith("抢救时间")


def test_complete_empty_trigger_sources_are_not_applicable_without_llm():
    llm = FakeLLM()
    result = _execute(_session(), llm)
    assert _state(result) == "not_applicable"
    assert result.llm_call_count == 0
    assert llm.calls == []
    assert len(result.decisions[0].fact_refs) == 2


@pytest.mark.parametrize("options,reason", [
    ({"orders": [{"status_state": "effective"}]}, "rescue_record_missing_after_trigger"),
    ({"orders": [{"status_state": "unknown"}]}, "applicability_source_gap"),
    ({"failures": (ORDERS,)}, "source_unavailable"),
    ({"failures": ("rescue_record",)}, "source_unavailable"),
    ({"rows": [_row()], "truncated": ("rescue_record",)}, "source_truncated"),
])
def test_incomplete_trigger_or_record_sources_are_data_gap(options, reason):
    llm = FakeLLM()
    result = _execute(_session(**options), llm)
    assert _state(result) == "data_gap"
    assert result.decisions[0].reason_code == reason
    assert llm.calls == []


@pytest.mark.parametrize("row", [
    _row(body=""), _row(body="无"), _row(body="--"),
    _row(body="抢救记录\n病情变化：\n抢救时间：\n抢救措施：\n抢救结果：\n姓名：\n职称："),
    _row(content_truncated=True), _row(content_complete=False),
    _row(body="文字" * 3001),
    _row(record_content=None, content="摘要不能证明完整正文"),
])
def test_no_usable_complete_body_does_not_call_llm(row):
    llm = FakeLLM()
    result = _execute(_session([row]), llm)
    assert _state(result) == "data_gap"
    assert result.llm_call_count == 0
    assert llm.calls == []


@pytest.mark.parametrize("reverse", [False, True])
def test_proven_missing_item_wins_over_another_blank_document(reverse):
    rows = [_row("defect", missing=("participant_titles",)), _row("gap", body="")]
    if reverse:
        rows.reverse()
    session = _session(rows)
    result = _execute(session, FakeLLM(_response(session, missing_by_id={"defect": ("participant_titles",)})))
    assert _state(result) == "non_compliant"
    facts = _facts(result)
    assert facts["missing_fields"] == ["participant_titles"]
    assert len(facts["rescue_content_events"]) == 2
    assert set(facts["unknown_fields"]) == set(RESCUE_CONTENT_FIELDS)


def test_facts_from_another_document_cannot_supply_a_missing_item():
    session = _session([_row("missing", missing=("rescue_outcome",)), _row("complete")])
    result = _execute(session, FakeLLM(_response(session, missing_by_id={"missing": ("rescue_outcome",)})))
    assert _state(result) == "non_compliant"
    assert [event["source_document_id"] for event in _facts(result)["rescue_content_events"] if event["missing_fields"]] == ["missing"]


@pytest.mark.parametrize("bad_kind", ["forged_ref", "duplicate_ref", "missing_document", "missing_field", "forged_quote", "bad_offset", "bool_offset", "partial_absence", "extra_state"])
def test_unverifiable_semantic_output_is_rejected_once(bad_kind):
    session = _session([_row("R1"), _row("R2")])
    payload = deepcopy(_response(session))
    docs = payload["documents"]
    atom = docs[0]["fields"]["condition_change"]
    if bad_kind == "forged_ref":
        docs[0]["document_ref"] = "f" * 64
    elif bad_kind == "duplicate_ref":
        docs[1]["document_ref"] = docs[0]["document_ref"]
    elif bad_kind == "missing_document":
        docs.pop()
    elif bad_kind == "missing_field":
        del docs[0]["fields"]["rescue_outcome"]
    elif bad_kind == "forged_quote":
        atom["quote"] = "从未提供的原文"
    elif bad_kind == "bad_offset":
        atom["start"] = -1
    elif bad_kind == "bool_offset":
        atom["start"] = False
    elif bad_kind == "partial_absence":
        atom.update(state="absent", start=0, end=20, quote=None)
    else:
        docs[0]["final_state"] = "compliant"
    llm = FakeLLM(payload)
    result = _execute(session, llm)
    assert _state(result) == "data_gap"
    assert _facts(result)["failure_kind"] == "model_invalid_output"
    assert result.llm_call_count == len(llm.calls) == 1
    assert result.total_tokens == 120


def test_transport_failure_is_only_new_rule_gap_and_old_timeliness_is_identical():
    row = _row(body="\n".join(SNIPPETS.values()) + "\n抢救结束时间：2026-07-16 09:30")
    session = _session([row])
    baseline = _execute(session, rules=(OLD,))
    result = _execute(session, FakeLLM(failure=True), rules=(OLD, RULE))
    assert _state(result) == "data_gap"
    assert result.decisions[0] == baseline.decisions[0]
    assert dict(result.customer_display_facts)[OLD] == dict(baseline.customer_display_facts)[OLD]
    assert result.llm_call_count == 1
    assert result.total_tokens == 0


@pytest.mark.parametrize("rows", [
    [_row(str(index)) for index in range(9)],
    [_row(str(index), body="文字" * 2500) for index in range(3)],
])
def test_batch_size_and_total_char_bounds_do_not_call_llm(rows):
    llm = FakeLLM()
    result = _execute(_session(rows), llm)
    assert _state(result) == "data_gap"
    assert result.decisions[0].reason_code == "candidate_scope_incomplete"
    assert llm.calls == []


def test_missing_llm_and_unknown_atoms_are_data_gap():
    session = _session([_row()])
    assert _state(_execute(session)) == "data_gap"
    result = _execute(session, FakeLLM(_response(session, unknown_by_id={"R1": ("participant_titles",)})))
    assert _state(result) == "data_gap"


def test_old_006_retries_and_usage_are_unchanged_when_new_rule_runs():
    session = _session([_row()], extra={
        "inpat_registration": [{"admission_datetime": "2026-07-15 13:48:49"}],
        "senior_course_record": [{"document_id": "round", "document_title": "上级医师查房记录",
                                  "record_time": "2026-07-16 10:30:02",
                                  "record_content": "今日测试甲主任医师联合相关专业医师查房。"}],
    })

    class MixedLLM(FakeLLM):
        def __init__(self):
            super().__init__(_response(session))
            self.round_calls = 0

        async def generate(self, prompt, **kwargs):
            if "lx0609-006-round-role-v1" not in prompt:
                return await super().generate(prompt, **kwargs)
            self.round_calls += 1
            if self.round_calls == 1:
                return {"content": "invalid", "usage": {"prompt_tokens": 20, "completion_tokens": 2}}
            return {"content": json.dumps({"schema_version": "lx0609-006-round-role-v1", "documents": [{
                "position": 1, "role": "senior", "physician_name": "测试甲", "physician_title": "主任医师",
                "evidence_quote": "今日测试甲主任医师联合相关专业医师查房",
            }]}, ensure_ascii=False), "usage": {"prompt_tokens": 20, "completion_tokens": 8}}

    baseline_llm = MixedLLM()
    baseline = _execute(session, baseline_llm, rules=(ROUND,))
    llm = MixedLLM()
    result = _execute(session, llm, rules=(ROUND, RULE))
    assert llm.round_calls == baseline_llm.round_calls == 2
    assert result.llm_call_count == 3
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (140, 30, 170)
    assert next(item for item in result.decisions if item.rule_id == ROUND) == baseline.decisions[0]
    assert dict(result.customer_display_facts)[ROUND] == dict(baseline.customer_display_facts)[ROUND]
    assert result.planned_rule_ids == tuple(
        rule_id
        for rule_id in EXECUTABLE_BASIC_TIMELINESS_RULE_IDS
        if rule_id in {ROUND, RULE}
    )
    assert tuple(item.rule_id for item in result.decisions) == result.planned_rule_ids
