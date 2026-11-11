"""感染事实正式入口：合成材料、固定应答、禁网及内存Canonical保存。"""
from copy import deepcopy
from datetime import datetime
import asyncio
import json

import pytest

from infection_event_test_support import (
    _STOPPED, _finalize, _loaded, _prophylaxis_rows, _session, isolated_freeze,  # noqa: F401
)

RULE = "LX0609-05-01-01"
VERSION = "postop-infection-surgery-facts-v1"
FIRST = "腹腔镜下阑尾切除术"
SECOND = "腹腔镜胆囊切除术"
FINDING = "肺部感染，体温38.9℃，白细胞升高，需抗感染治疗"
TIMED = f"{FIRST}后：2026-06-03 08:00:00 出现{FINDING}。"


class FixedFactsClient:
    def __init__(self, facts, *, mutate=None, error=None, finish="stop"):
        self.facts, self.mutate, self.error = facts, mutate, error
        self.finish = finish
        self.calls, self.inputs, self.kwargs = 0, [], []

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        body = json.loads(prompt.split("INPUT_JSON=", 1)[1])
        self.inputs.append(body)
        self.kwargs.append(kwargs)
        assert body["schema_version"] == VERSION
        if self.error:
            raise self.error
        documents = []
        for doc in body["documents"]:
            fact = self.facts[doc["text"]]
            state = fact if isinstance(fact, str) else "present"
            events = []
            if state == "present":
                linked = next((item for item in body["surgeries"] if any(
                    part["name"] == fact.get("name") for part in item["components"])), None)
                events.append({"action": "anti_infective_treatment", "infection_quote": fact.get("quote", FINDING),
                    "site": "肺部", "recorded_at": doc["recorded_at"],
                    "occurred_at": {"value": fact.get("occurred"), "precision": "datetime" if fact.get("occurred") else "unknown",
                                    "quote": fact.get("occurred")},
                    "relations": [{"target_surgery_ref": target,
                        "relation": "unattributed" if linked is None else "this_surgery" if linked["surgery_ref"] == target else "other_surgery",
                        "related_surgery_ref": linked["surgery_ref"] if linked else None,
                        "identity_quote": fact.get("identity", doc["text"]) if linked else None}
                        for target in body["target_surgery_refs"]]})
            documents.append({"document_ref": doc["document_ref"], "state": state, "events": events})
        payload = {"schema_version": VERSION, "documents": documents}
        if self.mutate:
            self.mutate(payload, body)
        return {"choices": [{"finish_reason": self.finish, "message": {"content": json.dumps(payload, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 11, "total_tokens": 18}}


def rows_for(text=TIMED, *, second=False, begin="2026-06-04 12:00:00", end="2026-06-04 14:00:00"):
    rows = _prophylaxis_rows([deepcopy(_STOPPED)], [{"document_id": "C1", "record_time": "2026-06-05 09:00:00", "record_content": text}])
    if second:
        rows["surgery_record"].append({**rows["surgery_record"][0], "document_id": "S2", "surgery_name": SECOND,
            "surgery_begin_time": begin + "+08:00", "surgery_end_time": end + "+08:00", "record_time": end,
            "surgery_process": "手术经过：顺利。切口等级：Ⅲ类。", "record_content": "手术经过：顺利。切口等级：Ⅲ类。"})
    return rows


async def run_actual(rows, client, *, persist=True):
    from app.services.luxian_0609.native_surgery_gate_execution import execute_luxian_0609_native_surgery_gate_rules
    session = _session((RULE,), rows, "surgery_gate", day="2026-06-20", scene="final", admission="2026-05-30 08:00:00")
    native = await execute_luxian_0609_native_surgery_gate_rules(rule_ids=(RULE,), decision_rule_ids=(RULE,), wrapper_rules=(),
        evidence_payload={}, institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials)
    final = _finalize(RULE, native, session)
    return (_loaded(final) if persist else final), native


@pytest.mark.asyncio
async def test_actual_single_other_site_infection_roundtrip():
    client = FixedFactsClient({TIMED: {"name": FIRST, "occurred": "2026-06-03 08:00:00"}})
    loaded, native = await run_actual(rows_for(), client)
    assert loaded["status"] == "compliant"
    assert loaded["customer_display_facts"]["duration_hours"] == 70.0
    assert loaded["customer_display_facts"]["threshold_hours"] == 24
    assert client.calls == native.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("recorded,expected", [(False, "non_compliant"), (True, "compliant")])
async def test_e05_proven_duration_survives_unknown_follow_on_stop(recorded, expected):
    """必要前置：未知停止时间不抹去已证明超限，仍由逐台感染证据决定。"""
    rows = rows_for()
    rows["inpat_drug_order"].append({**_STOPPED, "order_id": "FOLLOW", "planned_start_datetime": "2026-06-05 08:00:00",
                                    "stop_datetime": None, "order_status": "执行"})
    client = FixedFactsClient({TIMED: {"name": FIRST} if recorded else "absent"})
    loaded, _ = await run_actual(rows, client)
    assert loaded["status"] == expected
    facts = loaded["customer_display_facts"]
    assert facts["stop_time_unknown"] is True
    assert facts["duration_hours"] == 70.0
    assert "实际停药时间未知" in loaded["findings"]


@pytest.mark.asyncio
async def test_actual_multiple_surgeries_explicit_first_roundtrip():
    client = FixedFactsClient({TIMED: {"name": FIRST, "occurred": "2026-06-03 08:00:00"}})
    loaded, _ = await run_actual(rows_for(second=True), client)
    assert loaded["status"] == "compliant"
    assert len(client.inputs[0]["surgeries"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("begin,end", [("2026-06-04 12:00:00", "2026-06-04 14:00:00"),
    ("2026-06-02 10:00:00", "2026-06-02 11:00:00")], ids=["later", "starts_at_first_end"])
async def test_only_second_cannot_release_first(begin, end):
    text = f"{SECOND}后出现{FINDING}。"
    loaded, native = await run_actual(rows_for(text, second=True, begin=begin, end=end), FixedFactsClient({text: {"name": SECOND}}))
    assert loaded["status"] == "non_compliant"
    assert native.diagnostic_semantic_snapshot["schema_version"] == VERSION


@pytest.mark.asyncio
async def test_generic_infection_stays_unknown_and_preserves_occurrence_unknown():
    text = f"用药后，术后出现{FINDING}。"
    client = FixedFactsClient({text: {}})
    loaded, native = await run_actual(rows_for(text, second=True), client)
    assert (loaded["status"], loaded["reason_code"]) == ("data_gap", "required_field_missing")
    audit = native.diagnostic_semantic_snapshot
    assert audit["rule_id"] == RULE and audit["complete"] is False
    event = next(iter(audit["infection_events"].values()))
    assert event["occurred_at"] == {"value": None, "precision": "unknown"}
    assert all(item["validated_state"] == "unknown" for item in event["relations"].values())


@pytest.mark.asyncio
@pytest.mark.parametrize("dated", [False, True, "infection_time_only"], ids=["same_name_unresolved", "explicit_original_time", "onset_clock_is_not_identity"])
async def test_same_name_requires_distinguishing_original_time(dated):
    text = f"{FIRST}（2026-06-02 08:00:00开始）后出现{FINDING}。" if dated else f"{FIRST}后出现{FINDING}。"
    if dated == "infection_time_only":
        text = f"{FIRST}术后：2026-06-02 08:00:00出现{FINDING}。"
    rows = rows_for(text, second=True)
    rows["surgery_record"][1]["surgery_name"] = FIRST
    loaded, _ = await run_actual(rows, FixedFactsClient({text: {"name": FIRST}}))
    assert loaded["status"] == ("compliant" if dated is True else "data_gap")


def mr_row(**changes):
    return {"surgery_id": "MR1", "surgery_name": FIRST, "surgical_level": "二级", "surgial_incision_level": "Ⅱ",
        "surgery_begin_datetime": datetime(2026, 6, 2, 8), "surgery_end_datetime": datetime(2026, 6, 2, 10), **changes}


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", [False, True], ids=["matching_cross_source", "mr_fallback"])
async def test_real_mr_context_and_fallback(fallback):
    rows = rows_for()
    rows["mr_surgery"] = [mr_row()]
    if fallback:
        rows["surgery_record"] = []
    client = FixedFactsClient({TIMED: {"name": FIRST}})
    loaded, _ = await run_actual(rows, client)
    assert loaded["status"] == "compliant"
    components = client.inputs[0]["surgeries"][0]["components"]
    assert {item["source_key"] for item in components} == ({"mr_surgery"} if fallback else {"mr_surgery", "surgery_record"})
    assert all(item["begin"]["precision"] == "datetime" for item in components)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["begin", "end"])
async def test_original_single_surgery_duration_anchor_fallback_is_preserved(missing):
    rows = rows_for()
    rows["surgery_record"][0][f"surgery_{missing}_time"] = None
    rows["inpat_drug_order"][0]["stop_datetime"] = "2026-06-03 06:00:00" if missing == "begin" else "2026-06-03 04:00:00"
    client = FixedFactsClient({})
    loaded, _ = await run_actual(rows, client)
    assert loaded["status"] == "compliant" and loaded["customer_display_facts"]["duration_hours"] == 20.0
    assert loaded["customer_display_facts"]["anchor"] == ("surgery_end" if missing == "begin" else "surgery_begin")
    assert client.calls == 0


@pytest.mark.asyncio
async def test_components_and_source_duplicates_keep_stable_event_identity():
    rows = rows_for()
    rows["surgery_record"] += [deepcopy(rows["surgery_record"][0]),
        {**rows["surgery_record"][0], "document_id": "S1b", "surgery_name": "粘连松解术"}]
    identities = []
    for records in (rows["surgery_record"], list(reversed(rows["surgery_record"]))):
        client = FixedFactsClient({TIMED: {"name": FIRST}})
        loaded, native = await run_actual({**rows, "surgery_record": records}, client)
        assert loaded["status"] == "compliant"
        assert len(client.inputs[0]["surgeries"]) == 1
        identities.append(set(native.diagnostic_semantic_snapshot["surgery_events"]))
    assert identities[0] == identities[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["missing_id", "duplicate_conflict", "cross_source_conflict"])
async def test_source_identity_conflict_is_unresolved_without_model(kind):
    rows = rows_for()
    if kind == "missing_id":
        rows["surgery_record"][0].pop("document_id")
    elif kind == "duplicate_conflict":
        rows["surgery_record"].append({**rows["surgery_record"][0], "surgery_name": SECOND})
    else:
        rows["mr_surgery"] = [mr_row(surgery_begin_datetime=datetime(2026, 6, 8, 8), surgery_end_datetime=datetime(2026, 6, 8, 10))]
    client = FixedFactsClient({})
    loaded, native = await run_actual(rows, client)
    assert loaded["status"] == "data_gap" and client.calls == 0
    assert native.diagnostic_semantic_snapshot["complete"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["fabricated_quote", "wrong_identity", "disconnected_quote", "future_occurrence", "wrong_record_clock"])
async def test_fabricated_or_contradictory_facts_are_technical(kind):
    text = f"{SECOND}后出现{FINDING}。" if kind == "wrong_identity" else TIMED

    def corrupt(payload, body):
        event = payload["documents"][0]["events"][0]
        if kind == "fabricated_quote":
            event["infection_quote"] = "原文不存在的切口流脓"
        elif kind == "wrong_identity":
            event["relations"][0].update(relation="this_surgery", related_surgery_ref=body["target_surgery_refs"][0])
        elif kind == "disconnected_quote":
            event["relations"][0]["identity_quote"] = FIRST
        elif kind == "future_occurrence":
            event["occurred_at"] = {"value": "2026-06-07 08:00:00", "precision": "datetime", "quote": "2026-06-07 08:00:00"}
        else:
            event["recorded_at"] = "2026-06-06 09:00:00"

    if kind == "future_occurrence":
        text = TIMED.replace("2026-06-03", "2026-06-07")
    client = FixedFactsClient({text: {"name": SECOND if kind == "wrong_identity" else FIRST}}, mutate=corrupt)
    final, _ = await run_actual(rows_for(text, second=kind == "wrong_identity"), client, persist=False)
    assert (final["status"], final["reason_code"]) == ("technical_error", "model_invalid_output")


@pytest.mark.asyncio
async def test_independent_success_survives_unknown_or_invalid_other_document():
    rows = rows_for()
    rows["senior_course_record"].append({"document_id": "C2", "record_time": "2026-06-05 10:00:00", "record_content": "另一份病程待核。"})
    for state in ("unknown", "invalid"):
        def corrupt(payload, body):
            if state == "invalid":
                payload["documents"][1]["state"] = "invalid"
        loaded, native = await run_actual(rows, FixedFactsClient({TIMED: {"name": FIRST}, "另一份病程待核。": "unknown"}, mutate=corrupt))
        assert loaded["status"] == "compliant"
        assert native.diagnostic_semantic_snapshot["complete"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("late_state", ["unknown", "invalid"])
async def test_independent_defect_survives_other_event_unknown_or_failure(late_state):
    early, late = "第一台术后无感染证据。", "第二台术后感染情况待核。"
    rows = rows_for(early, second=True, begin="2026-06-10 08:00:00", end="2026-06-10 10:00:00")
    rows["senior_course_record"][0]["record_time"] = "2026-06-03 09:00:00"
    rows["senior_course_record"].append({"document_id": "C2", "record_time": "2026-06-11 09:00:00", "record_content": late})
    rows["surgery_record"][1]["surgery_process"] = rows["surgery_record"][1]["record_content"] = "切口等级：Ⅱ类。"
    rows["inpat_drug_order"].append({**_STOPPED, "order_id": "LATE", "planned_start_datetime": "2026-06-10 07:30:00", "stop_datetime": "2026-06-13 08:00:00"})
    def corrupt(payload, body):
        if late_state == "invalid":
            payload["documents"][1]["state"] = "invalid"
    loaded, native = await run_actual(rows, FixedFactsClient({early: "absent", late: "unknown"}, mutate=corrupt))
    assert loaded["status"] == "non_compliant"
    statuses = {item["status"] for item in native.diagnostic_semantic_snapshot["surgery_events"].values()}
    assert statuses == {"non_compliant", "data_gap" if late_state == "unknown" else "technical_error"}


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["timeout", "budget", "length", "untimed_protocol"])
async def test_technical_failures_preserve_reason_and_do_not_become_clinical_results(kind):
    from app.services.llm_token_budget import BudgetError, BudgetVerdict
    error = TimeoutError("fixed") if kind == "timeout" else BudgetError(BudgetVerdict("OVER_BUDGET", "fixed", "synthetic", "fixed")) if kind == "budget" else None
    def corrupt(payload, body):
        if kind == "untimed_protocol":
            payload["documents"][0]["state"] = "invalid"
    client = FixedFactsClient({TIMED: {"name": FIRST}}, error=error, mutate=corrupt, finish="length" if kind == "length" else "stop")
    rows = rows_for()
    if kind == "untimed_protocol":
        rows["senior_course_record"][0]["record_time"] = None
    final, _ = await run_actual(rows, client, persist=False)
    assert (final["status"], final["reason_code"]) == ("technical_error", {
        "timeout": "model_timeout", "budget": "llm_context_over_budget", "length": "model_invalid_output", "untimed_protocol": "model_invalid_output"}[kind])
    assert client.calls == 1 and client.kwargs[0]["max_completion_tokens"] == 2048
    assert client.kwargs[0]["allow_length_retry"] is False


@pytest.mark.asyncio
async def test_cancellation_is_not_swallowed():
    with pytest.raises(asyncio.CancelledError):
        await run_actual(rows_for(), FixedFactsClient({}, error=asyncio.CancelledError()), persist=False)


@pytest.mark.asyncio
async def test_complete_body_and_capacity_failure_are_explicit():
    text = "合成背景。" * 700 + TIMED
    client = FixedFactsClient({text: {"name": FIRST, "identity": TIMED}})
    loaded, _ = await run_actual(rows_for(text), client)
    assert loaded["status"] == "compliant" and client.inputs[0]["documents"][0]["text"] == text
    client = FixedFactsClient({})
    final, _ = await run_actual(rows_for("合成背景。" * 8000), client, persist=False)
    assert (final["status"], final["reason_code"]) == ("technical_error", "llm_context_over_budget")
    assert client.calls == 0


@pytest.mark.asyncio
async def test_private_evidence_positions_refer_to_original_material_after_redaction():
    from app.services.luxian_0609.llm_prompt_privacy import redact_luxian_0609_patient_privacy
    text = "合成联系电话：13800138000。\n" + TIMED
    redacted = redact_luxian_0609_patient_privacy(text)
    client = FixedFactsClient({redacted: {"name": FIRST, "identity": TIMED, "occurred": "2026-06-03 08:00:00"}})
    loaded, native = await run_actual(rows_for(text), client)
    assert loaded["status"] == "compliant" and "13800138000" not in client.inputs[0]["documents"][0]["text"]
    event = next(iter(native.diagnostic_semantic_snapshot["infection_events"].values()))
    assert text[slice(*event["infection_span"])] == event["infection_quote"]
    assert text[slice(*event["occurrence_span"])] == "2026-06-03 08:00:00"
    relation = next(iter(event["relations"].values()))
    assert text[slice(*relation["identity_span"])] == TIMED


class CacheClient(FixedFactsClient):
    provider_code, model, api_endpoint = "synthetic", "fixed-facts", "synthetic://offline"


@pytest.mark.asyncio
async def test_fact_role_and_new_cache_are_material_catalog_and_model_bound(tmp_path, monkeypatch):
    from app.services.luxian_0609.infection_surgery_extraction import FREEZE_NAMESPACE
    # 没有覆盖/清理旧文件；原协议/旧namespace的冻结完全保留。
    directory = tmp_path / "cache"
    monkeypatch.setenv("LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR", str(directory))
    old = directory / "postop_infection_v2" / "old.json"
    old.parent.mkdir(parents=True)
    old.write_text('{"legacy":true}\n', encoding="utf-8")
    selected = CacheClient({TIMED: {"name": FIRST}})
    class Routed:
        roles = []
        def for_task_role(self, role):
            self.roles.append(role)
            return selected
        async def generate(self, *args, **kwargs):
            raise AssertionError("必须选择实际fact_extraction客户端")
    routed = Routed()
    first, _ = await run_actual(rows_for(), routed)
    second, native = await run_actual(rows_for(), routed)
    assert first["status"] == second["status"] == "compliant"
    assert routed.roles == ["fact_extraction", "fact_extraction"] and selected.calls == 1
    assert native.llm_call_count == 0
    assert old.read_text(encoding="utf-8") == '{"legacy":true}\n'
    assert len(list((directory / FREEZE_NAMESPACE).glob("*.json"))) == 1
    # 相同正文但目录新增另一台、材料改变、实际角色模型改变都须重新调用。
    await run_actual(rows_for(second=True), routed)
    changed = TIMED + "病情观察。"
    selected.facts[changed] = {"name": FIRST, "identity": TIMED}
    await run_actual(rows_for(changed), routed)
    selected.model = "another-fixed-facts"
    await run_actual(rows_for(), routed)
    assert selected.calls == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["unknown", "invalid", "failure", "unconfigured", "untimed"])
async def test_unknown_failure_invalid_and_unknown_client_identity_never_freeze(tmp_path, monkeypatch, kind):
    from app.services.luxian_0609.infection_surgery_extraction import FREEZE_NAMESPACE
    monkeypatch.setenv("LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR", str(tmp_path / "cache"))
    client_type = FixedFactsClient if kind == "unconfigured" else CacheClient
    def corrupt(payload, body):
        if kind == "invalid":
            payload["documents"][0]["events"][0]["infection_quote"] = "伪引文"
    client = client_type({TIMED: "unknown" if kind == "unknown" else {"name": FIRST}},
                         mutate=corrupt, error=TimeoutError("fixed") if kind == "failure" else None)
    rows = rows_for()
    if kind == "untimed":
        rows["senior_course_record"].append({"document_id": "C2", "record_content": "时间未知的完整病程。"})
        client.facts["时间未知的完整病程。"] = "absent"
    for _ in range(2):
        final, native = await run_actual(rows, client, persist=kind in {"unknown", "unconfigured", "untimed"})
        if kind == "untimed":
            assert final["status"] == "compliant" and native.diagnostic_semantic_snapshot["complete"] is False
            assert len(client.inputs[-1]["documents"]) == 2
    assert client.calls == 2
    assert not list((tmp_path / "cache" / FREEZE_NAMESPACE).glob("*.json"))
