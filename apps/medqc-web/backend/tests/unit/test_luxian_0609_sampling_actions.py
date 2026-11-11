"""06-02-02：动作事实合同与真实执行边界的定向保护。"""

import asyncio
from copy import deepcopy
import json

import pytest

from pathology_event_test_support import _loaded, _pathology_master, _pathology_report, _session
from app.services.luxian_0609 import pathology_sampling_extraction as sampling
from app.services.luxian_0609.native_tumor_pathology_execution import execute_luxian_0609_native_tumor_pathology_rules


SAMPLING = "胃镜下取胃窦组织送病理检查"
RULE = sampling.RULE_ID


@pytest.fixture(autouse=True)
def freeze_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR", str(tmp_path))


def _rows(body=None, *, two=False, surgery=False, report_body=None):
    rows = {"pathology_exam_master": [_pathology_master("P1", 1)],
            "pathology_exam_report": [_pathology_report("P1", 3)]}
    if two:
        rows["pathology_exam_master"].append(_pathology_master("P2", 6))
        rows["pathology_exam_report"].append(_pathology_report("P2", 8))
    if report_body:
        rows["pathology_exam_report"][0]["record_content"] = report_body
    if body is not None:
        rows["surgery_record" if surgery else "daily_course_record"] = [{
            "document_id": "C1", "record_time": "2026-06-06 11:00:00",
            "surgery_process" if surgery else "record_content": body}]
    return rows


def _action(data, identifier, quote, *, raw_time=None, value=None, repeat=None, target=True):
    doc, name = next((d, name) for d in data["documents"] if d["target"] is target
                     for name, body in d["fields"].items() if quote in body)
    start = doc["fields"][name].index(quote)
    return {"action": identifier, "document": doc["document"], "field": name, "start": start,
            "end": start + len(quote), "quote": quote, "specimen_quote": "胃窦组织",
            "time": {"precision": "month_day" if raw_time else "unknown", "value": value, "quote": raw_time},
            "repeat_of": repeat}


def _payload(data, actions, links, *, complete=True):
    return {"schema_version": sampling.SCHEMA_VERSION, "actions": actions,
            "associations": [{"event": e["event"], "state": state, "action": action}
                             for e, (state, action) in zip(data["pathology_events"], links)],
            "document_coverage": [{"document": d["document"], "state": "complete" if complete else "incomplete"}
                                  for d in data["documents"]]}


class FixedClient:
    def __init__(self, responder, *, expected_ids=("P1",)):
        self.responder, self.expected_ids = responder, expected_ids
        self.prompts, self.roles = [], []

    def for_task_role(self, role):
        self.roles.append(role)
        return self

    async def generate(self, prompt, **kwargs):
        data = json.loads(prompt.split("INPUT_JSON=", 1)[1])
        assert data["schema_version"] == sampling.SCHEMA_VERSION
        assert [e["exam_id"] for e in data["pathology_events"]] == list(self.expected_ids)
        assert all(e["auxiliary_times"]["role"] == "clue_only" and e["actual_sampling"] is None
                   and len(e["material_refs"]) == 2 for e in data["pathology_events"])
        assert "申请/报告/记录时间均为clue_only" in prompt
        assert kwargs == {"max_completion_tokens": 4096, "allow_length_retry": False}
        self.prompts.append(data)
        out = self.responder(data)
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(out, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}}


async def _run(rows, client):
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions

    session = _session(RULE, rows, executor="tumor_pathology")
    result = await execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(RULE,), wrapper_rules=[], evidence_payload={}, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=(RULE,))
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(RULE,), snapshot=session.snapshot,
        evidence_materials=session.materials)[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(result.customer_display_facts).get(RULE),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    return final, result


@pytest.mark.asyncio
@pytest.mark.parametrize("body,quotes", [
    (f"6月1日{SAMPLING}。6月6日复核记录：6月1日{SAMPLING}，未进行新的取材。",
     (f"6月1日{SAMPLING}", f"6月6日复核记录：6月1日{SAMPLING}，未进行新的取材")),
    (f"6月1日{SAMPLING}。该次操作过程为{SAMPLING}，预约6月6日随访。",
     (f"6月1日{SAMPLING}", f"该次操作过程为{SAMPLING}，预约6月6日随访")),
])
async def test_repeated_action_cannot_prove_two_exams(body, quotes):
    def answer(data):
        return _payload(data, [_action(data, "a1", quotes[0], raw_time="6月1日", value="--06-01"),
                               _action(data, "a2", quotes[1], repeat="a1")],
                        [("confirmed", "a1"), ("confirmed", "a2")])
    client = FixedClient(answer, expected_ids=("P1", "P2"))
    final, native = await _run(_rows(body, two=True), client)
    assert (_loaded(final)["status"], final["reason_code"]) == ("data_gap", "association_failed")
    assert native.diagnostic_semantic_snapshot["actions"]["a2"]["repeat_of"] == "a1"
    assert client.roles == ["fact_extraction"] and len(client.prompts) == 1


@pytest.mark.asyncio
async def test_true_two_actions_one_document_and_order_independent_identity():
    first, second = f"病理号P1，6月1日{SAMPLING}", f"病理号P2，6月6日{SAMPLING}"
    def answer(data):
        return _payload(data, [_action(data, "a1", first, raw_time="6月1日", value="--06-01"),
                               _action(data, "a2", second, raw_time="6月6日", value="--06-06")],
                        [("confirmed", "a1"), ("confirmed", "a2")])
    rows = _rows(first + "。" + second + "。", two=True)
    rows["pathology_exam_report"].reverse()
    final, native = await _run(rows, FixedClient(answer, expected_ids=("P1", "P2")))
    assert _loaded(final)["status"] == "compliant"
    assert native.decisions[0].evaluator_version == sampling.EVALUATOR_VERSION
    audit = native.diagnostic_semantic_snapshot
    assert audit["rule_id"] == RULE and audit["complete"]
    assert set(audit["associations"]) == {"P1", "P2"} and len(audit["actions"]) == 2
    assert all(len(a["material_ref"]) == 64 and a["source_field"] == "record_content" for a in audit["actions"].values())
    assert "documents" not in audit and "fields" not in audit


@pytest.mark.asyncio
async def test_unknown_or_incorrect_event_identity_never_becomes_missing():
    body = f"病理号P1，6月1日{SAMPLING}。"
    for has_id in (False, True):
        quote = body if has_id else f"6月1日{SAMPLING}。"
        def answer(data):
            return _payload(data, [_action(data, "a1", quote, raw_time="6月1日", value="--06-01")],
                            [("unknown", None), ("confirmed", "a1")])
        final, native = await _run(_rows(quote, two=True), FixedClient(answer, expected_ids=("P1", "P2")))
        assert _loaded(final)["status"] == "data_gap"
        assert native.diagnostic_semantic_snapshot["associations"]["P2"]["validated_state"] == "unknown"


@pytest.mark.asyncio
async def test_empty_targets_without_actual_time_gap_but_independent_actual_action_can_prove_absence():
    final, native = await _run(_rows(), FixedClient(lambda data: pytest.fail("空输入不调用模型")))
    assert _loaded(final)["status"] == "data_gap" and native.llm_call_count == 0
    proof = f"病理号P1，6月1日{SAMPLING}。"
    def answer(data):
        return _payload(data, [_action(data, "a1", proof, raw_time="6月1日", value="--06-01", target=False)], [("absent", "a1")])
    final, native = await _run(_rows(report_body=proof), FixedClient(answer))
    assert _loaded(final)["status"] == "non_compliant"
    assert native.diagnostic_semantic_snapshot["associations"]["P1"]["validated_state"] == "absent"
    # 另一成功事件和未决事件不抹去已证实缺项，也不能被计成缺项。
    recorded = f"病理号P1，6月1日{SAMPLING}。"
    missing = f"病理号P2，6月6日{SAMPLING}。"
    rows = _rows(recorded, two=True)
    rows["pathology_exam_report"][1]["record_content"] = missing
    rows["pathology_exam_master"].append(_pathology_master("P3", 8))
    rows["pathology_exam_report"].append(_pathology_report("P3", 10))
    def mixed(data):
        return _payload(data, [_action(data, "a1", recorded, raw_time="6月1日", value="--06-01"),
                               _action(data, "a2", missing, raw_time="6月6日", value="--06-06", target=False)],
                        [("confirmed", "a1"), ("absent", "a2"), ("unknown", None)])
    final, native = await _run(rows, FixedClient(mixed, expected_ids=("P1", "P2", "P3")))
    loaded = _loaded(final)
    assert loaded["status"] == "non_compliant"
    facts = loaded["customer_display_facts"]
    assert [facts[key] for key in ("confirmed_event_count", "absent_event_count", "unknown_event_count")] == [1, 1, 1]
    assert [item["validated_state"] for item in native.diagnostic_semantic_snapshot["associations"].values()] == [
        "confirmed", "absent", "unknown"]
    from app.services.luxian_0609.tumor_pathology_result_mapping import safe_tumor_pathology_customer_display_facts
    assert safe_tumor_pathology_customer_display_facts(rule_id=RULE, raw={**facts, "absent_event_count": 0}) is None


@pytest.mark.asyncio
async def test_surgery_only_policy_and_untrimmed_original_field():
    quote = f"病理号P1，6月1日{SAMPLING}。"
    rows = _rows("开头\n  " + quote + "\n结尾", surgery=True)
    rows["daily_course_record"] = [{"document_id": "D2", "record_content": "不能送出"}]
    def answer(data):
        assert data["checked_sources"] == ["surgery_record"]
        assert not any(d["source_key"] == "daily_course_record" for d in data["documents"])
        assert next(d for d in data["documents"] if d["target"])["fields"]["surgery_process"] == "开头\n  " + quote + "\n结尾"
        return _payload(data, [_action(data, "a1", quote, raw_time="6月1日", value="--06-01")], [("confirmed", "a1")])
    final, _native = await _run(rows, FixedClient(answer))
    assert _loaded(final)["status"] == "compliant"
    assert final["customer_display_facts"]["documented_sources"] == ["surgery_record"]


@pytest.mark.asyncio
async def test_different_quote_ranges_or_copied_source_do_not_duplicate_action():
    first = f"病理号P1，病理号P2，6月1日{SAMPLING}。"
    for copy in (False, True):
        rows = _rows(first, two=True)
        if copy:
            rows["daily_course_record"].append({**rows["daily_course_record"][0]})
        def answer(data):
            a1 = _action(data, "a1", first, raw_time="6月1日", value="--06-01")
            a2 = _action(data, "a2", f"6月1日{SAMPLING}", raw_time="6月1日", value="--06-01")
            if copy:
                a2["document"] = [d for d in data["documents"] if d["target"]][-1]["document"]
            return _payload(data, [a1, a2], [("confirmed", "a1"), ("confirmed", "a2")])
        final, _native = await _run(rows, FixedClient(answer, expected_ids=("P1", "P2")))
        assert final["status"] == "data_gap"


@pytest.mark.asyncio
async def test_wrong_document_quote_time_and_repeat_conflict_are_technical():
    quote = f"病理号P1，6月1日{SAMPLING}。"
    for corruption in ("document", "quote", "time", "repeat"):
        def answer(data):
            a = _action(data, "a1", quote, raw_time="6月1日", value="--06-01")
            out = _payload(data, [a], [("confirmed", "a1")])
            if corruption == "document":
                a["document"] = "d404"
            elif corruption == "quote":
                a["quote"] += "伪造"
            elif corruption == "time":
                a["time"]["value"] = "--06-06"
            else:
                other = deepcopy(a)
                other.update(action="a2", repeat_of="a1", specimen_quote="病理")
                out["actions"].append(other)
            return out
        final, _native = await _run(_rows(quote), FixedClient(answer))
        assert (final["status"], final["reason_code"]) == ("technical_error", "model_invalid_output")


@pytest.mark.asyncio
async def test_transport_budget_failure_and_cancellation_remain_technical(tmp_path):
    from app.services.llm_token_budget import BudgetError, BudgetVerdict
    quote = f"病理号P1，6月1日{SAMPLING}。"
    errors = [RuntimeError("synthetic transport"), BudgetError(BudgetVerdict("BUDGET_EXHAUSTED", "full_request", "x", "x"))]
    for error in errors:
        def fail(data):
            raise error
        final, _native = await _run(_rows(quote), FixedClient(fail))
        assert final["status"] == "technical_error"
        assert final["reason_code"] == (error.code if isinstance(error, BudgetError) else "model_transport_error")
    def cancel(data):
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await _run(_rows(quote), FixedClient(cancel))
    assert not list(tmp_path.rglob("*.json"))


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["confirmed", "absent"])
async def test_new_freeze_complete_only_and_full_comparison_directory_isolated(tmp_path, decision):
    class IdentityClient(FixedClient):
        provider_code, model, api_endpoint = "synthetic", "sampling-v1", "https://synthetic.invalid/v1"
    quote = f"病理号P1，6月1日{SAMPLING}。"
    def answer(data):
        return _payload(data, [_action(data, "a1", quote, raw_time="6月1日", value="--06-01", target=decision == "confirmed")],
                        [(decision, "a1")])
    client = IdentityClient(answer)
    rows = _rows(quote) if decision == "confirmed" else _rows(report_body=quote)
    expected = "compliant" if decision == "confirmed" else "non_compliant"
    first, _ = await _run(rows, client)
    assert first["status"] == expected and len(client.prompts) == 1
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1 and sampling.FREEZE_NAMESPACE in str(files[0])
    from app.services.luxian_0609.exam_analysis_freeze import _windows_storage_path
    frozen = _windows_storage_path(files[0]).read_text(encoding="utf-8")
    assert "quote" not in frozen and "胃镜" not in frozen
    second, native = await _run(rows, client)
    assert second["status"] == expected and native.llm_call_count == 0 and len(client.prompts) == 1
    # 旧事实协议键与新动作协议键隔离；没有旧取材主冻结可迁移。
    from app.services.luxian_0609.validated_fact_freeze import fact_freeze_key
    data = client.prompts[0]
    context = sampling.SamplingContext(tuple(data["pathology_events"]), tuple(data["documents"]), tuple(data["checked_sources"]))
    options = dict(prompt=sampling.build_sampling_prompt(context), client=client, materials=context.documents,
                   scope={"events": context.events, "checked_sources": context.checked_sources})
    assert fact_freeze_key(protocol=("lx0609-pathology-documentation-facts-v1", "legacy"), **options) != files[0].stem
    # 新增比较事件必须换键；此前单事件成功不可覆盖另一事件。
    other = IdentityClient(lambda data: _payload(data, [], [("unknown", None), ("unknown", None)], complete=False),
                           expected_ids=("P1", "P2"))
    third, _ = await _run(_rows(quote, two=True), other)
    assert third["status"] == "technical_error" and len(other.prompts) == 1
    assert list(tmp_path.rglob("*.json")) == files


@pytest.mark.asyncio
@pytest.mark.parametrize("mixed", [False, True], ids=["coverage_complete_unknown", "confirmed_absent_unknown"])
async def test_complete_coverage_unknown_never_freezes_or_hot_hits(tmp_path, mixed):
    class IdentityClient(FixedClient):
        provider_code, model, api_endpoint = "synthetic", "sampling-v1", "https://synthetic.invalid/v1"

    recorded = f"病理号P1，6月1日{SAMPLING}。"
    missing = f"病理号P2，6月6日{SAMPLING}。"
    unowned = f"6月1日{SAMPLING}。"
    rows = _rows(recorded if mixed else unowned, two=mixed)
    if mixed:
        rows["pathology_exam_report"][1]["record_content"] = missing
        rows["pathology_exam_master"].append(_pathology_master("P3", 8))
        rows["pathology_exam_report"].append(_pathology_report("P3", 10))

    def answer(data):
        if not mixed:
            # 模型误报confirmed，生产校验因无原文检查ID降为validated unknown。
            return _payload(data, [_action(data, "a1", unowned, raw_time="6月1日", value="--06-01")], [("confirmed", "a1")])
        return _payload(data, [_action(data, "a1", recorded, raw_time="6月1日", value="--06-01"),
                               _action(data, "a2", missing, raw_time="6月6日", value="--06-06", target=False)],
                        [("confirmed", "a1"), ("absent", "a2"), ("unknown", None)])

    client = IdentityClient(answer, expected_ids=("P1", "P2", "P3") if mixed else ("P1",))
    for _ in range(2):
        final, native = await _run(rows, client)
        assert final["status"] == ("non_compliant" if mixed else "data_gap")
        assert native.llm_call_count == 1
        audit = native.diagnostic_semantic_snapshot
        assert audit["coverage_complete"] is True and audit["association_complete"] is False
        assert audit["complete"] is False
        assert not list(tmp_path.rglob("*.json"))
    assert len(client.prompts) == 2

    # 模拟旧提交留下的同协议unknown冻结；必须忽略，且不删除/覆盖旧文件。
    from app.services.llm_task_roles import task_role_scope
    from app.services.luxian_0609.validated_fact_freeze import fact_freeze_key, save_facts
    from app.services.luxian_0609.exam_analysis_freeze import _windows_storage_path
    data = client.prompts[0]
    context = sampling.SamplingContext(tuple(data["pathology_events"]), tuple(data["documents"]), tuple(data["checked_sources"]))
    key = fact_freeze_key(protocol=(sampling.SCHEMA_VERSION, sampling.EVALUATOR_VERSION),
                          prompt=sampling.build_sampling_prompt(context), client=client, materials=context.documents,
                          scope={"events": context.events, "checked_sources": context.checked_sources})
    with task_role_scope(client):
        save_facts(sampling.FREEZE_NAMESPACE, key, sampling._freeze_payload(answer(data)))
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    before = _windows_storage_path(files[0]).read_bytes()
    final, native = await _run(rows, client)
    assert final["status"] == ("non_compliant" if mixed else "data_gap")
    assert native.llm_call_count == 1 and len(client.prompts) == 3
    assert list(tmp_path.rglob("*.json")) == files and _windows_storage_path(files[0]).read_bytes() == before
