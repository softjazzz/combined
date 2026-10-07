"""固定响应验证分阶段合同；不将这些替身测试当作语义准确性验收。"""
import copy
import json

import pytest

from app.services.luxian_0609.extended_document.discharge_course_content import (
    RULE_ID, SCHEMA, evaluate_discharge_course_content,
)
from app.services.luxian_0609.extended_document import discharge_course_stages as stages
from app.services.luxian_0609.discharge_result_mapping import validate_published_discharge_facts
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from tests.unit.test_luxian_0609_native_extended_document_execution import _session, _canonical_extended_result

TEXT = "入院后予头孢曲松抗感染治疗。发热消退，咳嗽较前减轻。出院时体温正常、能自主活动。"
SURGERY = "腹腔镜胆囊切除术。"


def atom(state="present", span=1):
    return {"state": state, "span_id": span if state != "missing" else None,
            "conflict_span_id": span if state == "uncertain" else None,
            "conflict_kind": "meaning" if state == "uncertain" else "none"}


def payload(*, missing=None, uncertain=None, surgery=False, event_state="present"):
    return {
        "A": {"schema_version": SCHEMA + "-A", "discharges": [{"document_index": 1, "fields": {
            f: atom("missing" if missing == f else "uncertain" if uncertain == f else "present", i)
            for i, f in enumerate(stages.FIELDS, 1)}}]},
        "B": {"schema_version": SCHEMA + "-B", "references": ([{"document_index": 2, "events": [{
            "kind": "surgery", "span_id": 1, "importance_kind": "actual_procedure",
            "importance_refs": [{"document_index": 2, "span_id": 1}]}]}] if surgery else [])},
        "C": {"schema_version": SCHEMA + "-C", "events": ([{"event_id": 1, "matches": [
            {"document_index": 1, **atom(event_state, 4 if event_state == "present" else 1)}]}] if surgery else [])},
    }


class Client:
    def __init__(self, result=None, fail=()):
        self.result, self.fail, self.calls = result or payload(), fail, []

    def supports_strict_json_schema(self):
        return True

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        stage = prompt.splitlines()[0][-1]
        if stage in self.fail:
            raise TimeoutError()
        return {"content": json.dumps(self.result[stage], ensure_ascii=False),
                "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}}


async def run(response=None, *, text=TEXT, surgery=False, unavailable=(), fail=()):
    rows = {"discharge_record": [{"document_id": "discharge", "treatment_course": text}]}
    if surgery:
        rows["surgery_record"] = [{"document_id": "surgery", "surgery_name": SURGERY}]
    snapshot, materials = _session(rows, unavailable_sources=frozenset(unavailable))
    client = Client(response, fail)
    executed = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(RULE_ID,), decision_rule_ids=(RULE_ID,), evidence_snapshot=snapshot,
        evidence_materials=materials, llm_client=client,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=executed.decisions, expected_rule_ids=(RULE_ID,), snapshot=snapshot, evidence_materials=materials,
    )
    final = _canonical_extended_result(rule_id=RULE_ID, snapshot=snapshot, materials=materials,
                                       result=executed, reduced=reduced)
    return executed, final, client


def test_span_coordinates_preserve_duplicate_text_and_unicode():
    text = "字段：恢复良好。\n另一个字段：恢复良好。🙂可活动！"
    for span in stages.segments(text):
        ref = stages.anchor({"document_index": 1, "text": text}, span["span_id"])
        assert text[ref["start"]:ref["end"]] == span["text"]


@pytest.mark.parametrize("span", [True, 0, -1, 999, "1", None])
def test_invalid_span_cannot_create_evidence(span):
    with pytest.raises(ValueError):
        stages.anchor({"document_index": 1, "text": TEXT}, span)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [None, *stages.FIELDS])
async def test_field_completeness_survives_publication(missing):
    result, final, client = await run(payload(missing=missing))
    assert final["status"] == ("non_compliant" if missing else "compliant")
    assert result.llm_call_count == len(client.calls) == 2
    assert result.total_tokens == 60
    assert all(not c[1]["allow_length_retry"] for c in client.calls)
    assert final["customer_display_facts"] == dict(result.customer_display_facts)[RULE_ID]
    assert final["customer_display_facts"]["review"]["stages"]["C"] == "skipped"


@pytest.mark.asyncio
@pytest.mark.parametrize("state,expected", [("present", "compliant"), ("missing", "non_compliant"), ("uncertain", "data_gap")])
async def test_fixed_event_comparison(state, expected):
    result, final, client = await run(payload(surgery=True, event_state=state), text=TEXT + SURGERY, surgery=True)
    assert final["status"] == expected
    assert result.llm_call_count == len(client.calls) == 3
    facts = final["customer_display_facts"]
    assert facts == dict(result.customer_display_facts)[RULE_ID]
    assert bool(facts["review"]["conflicts"]) == (state == "uncertain")
    assert facts["review"]["event_basis"][0]["anchors"][0]["document_index"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["A", "B", "C"])
async def test_stage_failure_preserves_other_facts_and_reports_incomplete(stage):
    response = payload(missing="treatment" if stage != "A" else None, surgery=True, event_state="missing")
    result, final, client = await run(response, text=TEXT + SURGERY, surgery=True, fail=(stage,))
    assert final["status"] == "non_compliant"
    facts = final["customer_display_facts"]
    assert facts["review"]["stages"][stage] == "failed"
    from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts
    assert "未完成" in customer_finding_from_controlled_facts(rule_id=RULE_ID, facts=facts)
    assert len(client.calls) == (2 if stage == "B" else 3)
    assert result.total_tokens == (len(client.calls) - 1) * 30


@pytest.mark.asyncio
async def test_b_failure_does_not_produce_compliant_or_run_c():
    _, final, client = await run(payload(surgery=True), text=TEXT + SURGERY, surgery=True, fail=("B",))
    assert final["status"] == "data_gap" and len(client.calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["duplicate_a", "missing_a", "invalid_span", "omit_surgery", "new_c_event", "uncertain_without_evidence"])
async def test_invalid_response_fails_closed_without_retry(mode):
    response = payload(surgery=True)
    if mode == "duplicate_a":
        response["A"]["discharges"] *= 2
    elif mode == "missing_a":
        response["A"]["discharges"] = []
    elif mode == "invalid_span":
        response["A"]["discharges"][0]["fields"]["treatment"]["span_id"] = 999
    elif mode == "omit_surgery":
        response["B"]["references"][0]["events"] = []
    elif mode == "new_c_event":
        response["C"]["events"][0]["event_id"] = 2
    else:
        response["C"]["events"][0]["matches"][0].update(state="uncertain", span_id=None)
    _, final, client = await run(response, text=TEXT + SURGERY, surgery=True)
    assert final["status"] == "data_gap"
    assert len(client.calls) <= 3


@pytest.mark.asyncio
async def test_unavailable_and_truncated_material_skip_model():
    for kwargs in ({"unavailable": ("daily_course_record",)}, {"text": "长" * 60001}, {"text": ""}):
        result, final, client = await run(**kwargs)
        assert final["status"] == "data_gap" and result.llm_call_count == 0 and not client.calls


@pytest.mark.asyncio
async def test_no_discharge_is_not_applicable():
    snapshot, materials = _session({})
    client = Client()
    result = await evaluate_discharge_course_content(snapshot=snapshot, materials=materials, llm_client=client)
    assert result.state == "not_applicable" and not client.calls


@pytest.mark.asyncio
async def test_shared_summary_and_input_isolation():
    rows = {"discharge_record": [{"document_id": "d", "treatment_course": TEXT, "positive_assist_exam": "影像提示骨折。"}],
            "daily_course_record": [{"document_id": "c", "record_content": "CT提示骨折。MRI证实相同骨折，为主要诊断依据。"}],
            "discharge_record_diagnosis": [{"document_id": "d", "diagnosis_name": "骨折"}]}
    response = payload()
    response["B"]["references"] = [{"document_index": 2, "events": [
        {"kind": "test", "span_id": i, "importance_kind": "diagnostic_basis",
         "importance_refs": [{"document_index": 2, "span_id": 2}]} for i in (1, 2)]}]
    response["C"]["events"] = [{"event_id": i, "matches": [{"document_index": 1, **atom(span=4)}]} for i in (1, 2)]
    snapshot, materials = _session(rows)
    client = Client(response)
    result = await evaluate_discharge_course_content(snapshot=snapshot, materials=materials, llm_client=client)
    assert result.state == "compliant"
    assert result.facts["events"][0]["matches"] == result.facts["events"][1]["matches"]
    assert validate_published_discharge_facts(rule_id=RULE_ID, raw=result.facts) == result.facts
    inputs = {p.splitlines()[0][-1]: json.loads(p.split("以下为受控资料：\n")[1]) for p, _ in client.calls}
    assert [d["source"] for d in inputs["A"]["documents"]] == ["discharge_record", "discharge_record_diagnosis"]
    assert [d["source"] for d in inputs["B"]["documents"]] == ["daily_course_record"]
    assert len(inputs["C"]["fixed_events"]) == 2
    assert inputs["A"]["documents"][1]["parent_document_index"] == 1


@pytest.mark.asyncio
async def test_unresolved_importance_cannot_be_silent_compliance():
    response = payload()
    response["B"]["references"] = [{"document_index": 2, "events": [{"kind": "test", "span_id": 1,
        "importance_kind": "uncertain", "importance_refs": [{"document_index": 2, "span_id": 1}]}]}]
    snapshot, materials = _session({"discharge_record": [{"treatment_course": TEXT}],
        "daily_course_record": [{"record_content": "该检查与此次症状关系尚不明确。"}]})
    result = await evaluate_discharge_course_content(snapshot=snapshot, materials=materials, llm_client=Client(response))
    assert result.state == "data_gap" and result.llm_call_count == 2
    assert result.facts["review"]["unresolved_events"]
    assert validate_published_discharge_facts(rule_id=RULE_ID, raw=result.facts) == result.facts


@pytest.mark.asyncio
async def test_publication_rejects_missing_basis_and_conflicts():
    _, final, _ = await run(payload(surgery=True, event_state="uncertain"), text=TEXT + SURGERY, surgery=True)
    facts = final["customer_display_facts"]
    for key in ("event_basis", "conflicts"):
        bad = copy.deepcopy(facts)
        bad["review"][key] = []
        assert validate_published_discharge_facts(rule_id=RULE_ID, raw=bad) is None
    bad = copy.deepcopy(facts)
    bad["review"]["event_basis"][0]["anchors"][0]["end"] = 999999
    assert validate_published_discharge_facts(rule_id=RULE_ID, raw=bad) is None


@pytest.mark.asyncio
async def test_legacy_saved_facts_remain_readable():
    _, final, _ = await run()
    old = copy.deepcopy(final["customer_display_facts"])
    old.pop("review")
    assert validate_published_discharge_facts(rule_id=RULE_ID, raw=old) == old


@pytest.mark.asyncio
async def test_unlinked_diagnosis_stops_before_model():
    snapshot, materials = _session({"discharge_record": [{"document_id": "d", "treatment_course": TEXT}],
                                  "discharge_record_diagnosis": [{"document_id": "other", "diagnosis_name": "骨折"}]})
    client = Client()
    result = await evaluate_discharge_course_content(snapshot=snapshot, materials=materials, llm_client=client)
    assert result.state == "data_gap" and not client.calls


@pytest.mark.asyncio
async def test_prompt_budget_never_silently_truncates_or_counts_non_calls(monkeypatch):
    from app.services.luxian_0609.extended_document import discharge_course_content as module
    monkeypatch.setattr(module, "MAX_PROMPT_CHARS", 1)
    result, final, client = await run()
    assert final["status"] == "data_gap"
    assert result.llm_call_count == 0 and not client.calls


@pytest.mark.asyncio
async def test_multiple_discharges_cannot_share_missing_coverage():
    response = payload(surgery=True)
    response["A"]["discharges"].append({"document_index": 2, "fields": {f: atom(span=i) for i, f in enumerate(stages.FIELDS, 1)}})
    response["B"]["references"][0]["document_index"] = 3
    response["B"]["references"][0]["events"][0]["importance_refs"][0]["document_index"] = 3
    response["C"]["events"][0]["matches"] = [
        {"document_index": 1, **atom(span=4)}, {"document_index": 2, **atom("missing")}]
    snapshot, materials = _session({"discharge_record": [
        {"document_id": "d1", "treatment_course": TEXT + SURGERY},
        {"document_id": "d2", "treatment_course": TEXT}], "surgery_record": [{"surgery_name": SURGERY}]})
    result = await evaluate_discharge_course_content(snapshot=snapshot, materials=materials, llm_client=Client(response))
    assert result.state == "non_compliant"
    assert validate_published_discharge_facts(rule_id=RULE_ID, raw=result.facts) == result.facts
    response["C"]["events"][0]["matches"] = response["C"]["events"][0]["matches"][:1]
    result = await evaluate_discharge_course_content(snapshot=snapshot, materials=materials, llm_client=Client(response))
    assert result.state == "data_gap" and result.facts["review"]["stages"]["C"] == "failed"


@pytest.mark.asyncio
async def test_cross_document_importance_anchor_must_belong_to_its_document():
    response = payload()
    response["B"]["references"] = [
        {"document_index": 2, "events": [{"kind": "test", "span_id": 1, "importance_kind": "diagnostic_basis",
          "importance_refs": [{"document_index": 3, "span_id": 2}]}]}, {"document_index": 3, "events": []}]
    snapshot, materials = _session({"discharge_record": [{"treatment_course": TEXT}],
        "daily_course_record": [{"document_id": "r1", "record_content": "发现骨折。作为诊断依据。"},
                                {"document_id": "r2", "record_content": "只有一个片段。"}]})
    result = await evaluate_discharge_course_content(snapshot=snapshot, materials=materials, llm_client=Client(response))
    assert result.state == "data_gap" and result.facts["review"]["stages"]["B"] == "failed"
