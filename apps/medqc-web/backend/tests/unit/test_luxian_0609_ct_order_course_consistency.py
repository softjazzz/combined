"""CT医嘱一致性：事件归属、缺口语义及真实族调用/发布合同。"""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.ct_order_course_consistency import (
    RULE_ID, REPORT_RULE_ID, COURSE_SOURCES, SCHEMA_VERSION,
    CourseClause, CtReviewInput, build_ct_review_input, build_ct_fact_prompt,
    ct_display_status_matches, evaluate_ct_review, validate_ct_display_facts,
    CtEvidenceBudgetExceeded,
)
from app.services.luxian_0609.evidence_material import (
    Luxian0609EvidenceMaterialStore, build_material_document_refs, build_material_snapshot_ref,
)
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION, Luxian0609EvidenceSnapshot,
    SourceCompleteness, SourceObservation,
)
from app.services.luxian_0609.handbook_exam_lab import (
    HandbookEvent, HandbookFinding, ORDER_SOURCE, build_handbook_ledger,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import (
    SOURCE_REGISTRY_VERSION, resolve_luxian_0609_physical_source_entry,
)


def _event(key="EXAM-001"):
    return HandbookEvent("exam", key, "左膝CT", (("master:1", {"exam_id": key}),),
                         (("order:1", {"order_id": "ORDER-001", "order_name": "左膝CT"}),),
                         (("report:1", {"report_time": "2026-09-01T09:00:00+08:00"}),),
                         True, True, False, True)


def _review(text="本次左膝CT已完成，示骨折。", events=None, complete=True, initial=None):
    return CtReviewInput(tuple(events or (_event(),)), (1,),
                         (CourseClause("C1", "course:1", text, field_path="record_content", end=len(text)),), initial or {}, complete)


def _payload(state="consistent_description", *, clauses=None):
    return {"schema_version": SCHEMA_VERSION,
            "events": [{"event_position": 1, "order_position": 1, "record_state": state,
                        "clause_ids": clauses if clauses is not None else ["C1"]}],
            "unmatched_current_clause_ids": []}


def test_complete_positive_facts_keep_same_event_refs_and_publish_without_text():
    result = evaluate_ct_review(_review(), _payload())
    assert result.status == "compliant"
    assert "course:1" in result.refs
    assert validate_ct_display_facts(result.display_facts) == result.display_facts
    assert "左膝" not in json.dumps(result.display_facts, ensure_ascii=False)
    assert ct_display_status_matches("compliant", result.display_facts)
    assert not ct_display_status_matches("non_compliant", result.display_facts)


@pytest.mark.parametrize("state,clauses", [("absent", []), ("unknown", [])])
def test_no_clinical_defect_from_missing_or_uncertain_material(state, clauses):
    assert evaluate_ct_review(_review(), _payload(state, clauses=clauses)).status == "data_gap"


@pytest.mark.parametrize("text,expected", [
    ("EXAM-001医嘱为左膝CT，实际完成右膝CT。", "non_compliant"),
    ("ORDER-001医嘱为左膝CT，实际完成右膝CT。", "non_compliant"),
    ("完成右膝CT。", "data_gap"),
    ("EXAM-0012完成右膝CT。", "data_gap"),
])
def test_conflict_cannot_force_association_to_another_exam(text, expected):
    result = evaluate_ct_review(_review(text), _payload("contradictory_description"))
    assert result.status == expected


def test_known_conflict_is_not_hidden_by_an_unrelated_missing_event():
    initial = {2: HandbookFinding("data_gap", "execution_unconfirmed", ("order:2",))}
    review = _review("EXAM-001医嘱为左膝CT，实际右膝CT。", events=(_event(), _event("EXAM-002")), initial=initial)
    result = evaluate_ct_review(review, _payload("contradictory_description"))
    assert result.status == "non_compliant"
    assert [r["event_status"] for r in result.display_facts["event_results"]] == ["non_compliant", "data_gap"]


def test_one_merged_report_cannot_use_one_order_to_cover_all_body_sites():
    event = replace(_event(), orders=(*_event().orders,
        ("order:2", {"order_id": "ORDER-002", "order_name": "胸部CT"})))
    review = _review(events=(event,))
    payload = _payload()
    with pytest.raises(ValueError, match="incomplete CT fact scope"):
        evaluate_ct_review(review, payload)
    payload["events"].append({"event_position": 1, "order_position": 2,
                              "record_state": "absent", "clause_ids": []})
    result = evaluate_ct_review(review, payload)
    assert result.status == "data_gap"
    assert result.display_facts["event_count"] == 1


@pytest.mark.parametrize("state,text", [
    ("consistent_description", "左膝CT：胸部另见炎症。"),
    ("contradictory_description", "ORDER-001左膝CT与实际不同。"),
    ("contradictory_description", "EXAM-001检查存在矛盾。"),
])
def test_merged_order_cannot_borrow_sibling_name_result_or_identifier(state, text):
    event = replace(_event(), orders=(*_event().orders,
        ("order:2", {"order_id": "ORDER-002", "order_name": "胸部CT"})))
    payload = _payload()
    payload["events"].append({"event_position": 1, "order_position": 2,
                              "record_state": state, "clause_ids": ["C1"]})
    result = evaluate_ct_review(_review(text, events=(event,)), payload)
    assert result.status == "data_gap"


def test_semantic_positive_without_explicit_exam_description_remains_unresolved():
    result = evaluate_ct_review(_review("本次检查发现左膝骨折。"), _payload())
    assert result.status == "data_gap"


def test_unmatched_current_exam_prevents_whole_record_compliance():
    payload = _payload()
    payload["unmatched_current_clause_ids"] = ["C1"]
    assert evaluate_ct_review(_review(), payload).status == "data_gap"


@pytest.mark.parametrize("mutation", [
    lambda p: p["events"].append(deepcopy(p["events"][0])),
    lambda p: p["events"].clear(),
    lambda p: p["events"][0].update(event_position=True),
    lambda p: p["events"][0].update(event_position=2),
    lambda p: p["events"][0].update(clause_ids=["foreign:C1"]),
    lambda p: p["events"][0].update(clause_ids=[]),
    lambda p: p["events"][0].update(clause_ids=["C1", "C1"]),
    lambda p: p["events"][0].update(record_state="absent"),
    lambda p: p.update(raw_text="private"),
    lambda p: p["events"][0].update(final_state="compliant"),
])
def test_model_contract_failure_is_not_a_medical_judgement(mutation):
    payload = _payload()
    mutation(payload)
    with pytest.raises(ValueError):
        evaluate_ct_review(_review(), payload)


@pytest.mark.parametrize("mutation", [
    lambda f: f.update(raw_text="private"),
    lambda f: f["event_results"][0].update(quote="private"),
    lambda f: f["event_results"][0].update(event_status="non_compliant"),
    lambda f: f["event_results"][0].update(event_position=True),
    lambda f: f.update(event_count=2),
    lambda f: f.update(review_scope_complete=False),
])
def test_public_contract_rejects_internal_text_forged_status_and_incomplete_scope(mutation):
    facts = deepcopy(evaluate_ct_review(_review(), _payload()).display_facts)
    mutation(facts)
    assert validate_ct_display_facts(facts) is None


def _session(rows=None, incomplete=()):
    rows = rows or {}
    observations, refs, materials = [], [], {}
    for source in (ORDER_SOURCE, "exam_master", "exam_item_report", *COURSE_SOURCES):
        material = SnapshotSourceRows.create(source_key=source, rows=tuple(rows.get(source, ())), truncated=False, limit_rows=1000)
        if source not in incomplete:
            materials[source] = material
        documents = build_material_document_refs(source, material.rows)
        refs.extend(documents)
        state = QueryStatus.AVAILABLE if material.rows else QueryStatus.EMPTY
        complete = SourceCompleteness.UNPROVEN if source in incomplete else SourceCompleteness.COMPLETE
        version = resolve_luxian_0609_physical_source_entry(source).query_version
        observations.append(SourceObservation.create(
            source_key=source, query_state=state, completeness=complete,
            record_count=len(material.rows), query_version=version,
            snapshot_ref=build_material_snapshot_ref(source_key=source, query_version=version, query_state=state, completeness=complete, document_refs=documents),
        ))
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="test", patient_id="patient", visit_id="visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=observations, facts=(), document_refs=refs, created_at="2026-09-23T10:00:00+08:00",
    )
    return snapshot, Luxian0609EvidenceMaterialStore.create(snapshot=snapshot, sources=materials)


def _rows():
    return {
        ORDER_SOURCE: [{"order_id": "ORDER-001", "order_name": "左膝CT", "order_status": "新开"}],
        "exam_master": [{"exam_id": "EXAM-001", "order_id": "ORDER-001"}],
        "exam_item_report": [{"exam_id": "EXAM-001", "description": "骨折。", "report_time": "2026-09-01T09:00:00+08:00"}],
        "daily_course_record": [{"document_id": "D1", "record_content": "本次左膝CT已完成，示骨折。"}],
    }


def _project(rows=None, incomplete=()):
    snapshot, material = _session(rows, incomplete)
    ledger = build_handbook_ledger(rule_ids=(REPORT_RULE_ID,), snapshot=snapshot, materials=material)
    return build_ct_review_input(ledger=ledger, snapshot=snapshot, materials=material)


def test_formal_report_proves_execution_despite_new_order_status_and_unnamed_master():
    review = _project(_rows())
    assert review.needs_model
    assert review.events[0].performed
    assert evaluate_ct_review(review, _payload()).status == "compliant"


def test_pending_order_without_execution_never_calls_model_or_becomes_a_defect():
    rows = _rows()
    rows["exam_item_report"] = []
    review = _project(rows)
    assert not review.needs_model
    assert evaluate_ct_review(review).status == "data_gap"


@pytest.mark.parametrize("change", ["empty_course", "truncated_course", "missing_order", "unproven_course"])
def test_gaps_stop_model_and_prevent_false_compliance(change):
    rows = _rows()
    if change == "empty_course":
        rows["daily_course_record"] = []
    elif change == "truncated_course":
        rows["daily_course_record"][0]["record_content"] = "检查" * 20000
    elif change == "missing_order":
        rows[ORDER_SOURCE] = []
        rows["exam_master"][0]["exam_name"] = "左膝CT"
    review = _project(rows, ("daily_course_record",) if change == "unproven_course" else ())
    assert not review.needs_model
    assert evaluate_ct_review(review).status == "data_gap"


def test_empty_sources_and_course_only_trigger_have_different_results():
    assert evaluate_ct_review(_project()).status == "not_applicable"
    review = _project({"daily_course_record": [{"document_id": "D1", "record_content": "本次已行左膝CT。"}]})
    assert evaluate_ct_review(review).status == "data_gap"


@pytest.mark.parametrize("order_count", [1, 3])
def test_unrelated_canceled_orders_do_not_hide_current_course_event(order_count):
    rows = {ORDER_SOURCE: [{"order_id": f"O{i}", "order_name": "左膝CT", "order_status": "取消"}
                          for i in range(order_count)],
            "daily_course_record": [{"document_id": "D1", "record_content": "本次已完成胸部CT，提示炎症。"}]}
    assert evaluate_ct_review(_project(rows)).status == "data_gap"
    rows["daily_course_record"][0]["record_content"] = "患者病情平稳。"
    assert evaluate_ct_review(_project(rows)).status == "not_applicable"


def test_prompt_retains_document_context_and_real_order_time_alias():
    rows = _rows()
    rows[ORDER_SOURCE][0]["prescribed_datetime"] = "2026-09-01 09:00:00"
    rows["daily_course_record"][0].update(record_time="2026-09-01 11:00:00", record_content="今日左膝CT完成。")
    first = build_ct_fact_prompt(_project(rows))
    rows["daily_course_record"][0]["record_time"] = "2026-09-02 11:00:00"
    second = build_ct_fact_prompt(_project(rows))
    assert first != second
    assert '"prescribed_time": "2026-09-01 09:00:00"' in first
    assert '"document_position": 1' in first and '"source": "daily_course_record"' in first


@pytest.mark.parametrize("text,record_time,same_day,expected", [
    ("今日已完成左膝CT。", "2026-09-01 11:00:00", False, "data_gap"),
    ("今日已完成左膝CT。", "2026-09-02 11:00:00", False, "data_gap"),
    ("今日已完成左膝CT。", "2026-09-01 11:00:00", True, "data_gap"),
    ("2026-09-01和2026-09-02分别完成左膝CT。", "2026-09-03 11:00:00", False, "compliant"),
    ("E1和E2均完成左膝CT。", "2026-09-03 11:00:00", True, "compliant"),
])
def test_repeated_same_name_events_require_distinct_temporal_or_id_support(text, record_time, same_day, expected):
    events = tuple(replace(_event(f"E{i}"),
                           rows=((f"master:{i}", {"exam_time": f"2026-09-0{1 if same_day else i} 09:00:00"}),),
                           orders=((f"order:{i}", {"order_id": f"O{i}", "order_name": "左膝CT"}),))
                   for i in (1, 2))
    review = CtReviewInput(events, (1, 2), (CourseClause("C1", "course:1", text, 1, "daily_course_record", record_time, "record_content", 0, len(text)),), {}, True)
    payload = _payload()
    payload["events"].append({**payload["events"][0], "event_position": 2})
    assert evaluate_ct_review(review, payload).status == expected


@pytest.mark.parametrize("count", [32, 33])
def test_reference_budget_matches_public_decision_without_truncation(count):
    events = tuple(replace(_event(f"E{i}"), rows=((f"m{i}", {}),),
                           orders=((f"o{i}", {"order_id": f"O{i}", "order_name": "左膝CT"}),),
                           reports=((f"r{i}", {}),)) for i in range(count))
    clauses = tuple(CourseClause(f"C{i+1}", f"d{i}", f"O{i}左膝CT完成。", field_path="record_content", end=len(f"O{i}左膝CT完成。")) for i in range(count))
    review = CtReviewInput(events, tuple(range(1, count + 1)), clauses, {}, True)
    payload = {"schema_version": SCHEMA_VERSION, "unmatched_current_clause_ids": [],
               "events": [{"event_position": i + 1, "order_position": 1,
                           "record_state": "consistent_description", "clause_ids": [f"C{i+1}"]} for i in range(count)]}
    if count == 33:
        assert not review.needs_model
        with pytest.raises(CtEvidenceBudgetExceeded):
            evaluate_ct_review(review, payload)
    else:
        result = evaluate_ct_review(review, payload)
        assert result.status == "compliant" and len(result.refs) == 128


def test_prompt_scopes_event_and_returns_ids_instead_of_generated_quotes():
    prompt = build_ct_fact_prompt(_review())
    assert "UNTRUSTED_CLINICAL_DATA" in prompt
    assert "ORDER-001" in prompt and "EXAM-001" in prompt
    assert '"clause_id": "C1"' in prompt
    assert '"quote"' not in prompt


class _Client:
    def __init__(self, response=None):
        self.calls = 0
        self.response = _payload() if response is None else response

    async def generate(self, prompt, *, allow_length_retry):
        assert allow_length_retry is False
        self.calls += 1
        return {"content": json.dumps(self.response), "usage": {"prompt_tokens": 100, "completion_tokens": 20}, "_api_time": 0.01}


@pytest.mark.asyncio
async def test_native_execution_shares_ledger_and_isolates_bad_model_from_report_rule():
    snapshot, material = _session(_rows())
    client = _Client({"bad": True})
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(RULE_ID, REPORT_RULE_ID), decision_rule_ids=(RULE_ID, REPORT_RULE_ID),
        wrapper_rules=(), evidence_payload=None, llm_client=client,
        evidence_snapshot=snapshot, evidence_materials=material,
    )
    by_rule = {d.rule_id: d for d in result.decisions}
    assert by_rule[RULE_ID].reason_code == "model_invalid_output"
    assert by_rule[REPORT_RULE_ID].reason_code == "requirement_satisfied"
    assert client.calls == result.llm_call_count == 1
    assert result.total_tokens == 120


@pytest.mark.asyncio
async def test_native_success_exposes_new_id_facts_and_controlled_usage():
    snapshot, material = _session(_rows())
    client = _Client()
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(RULE_ID,), decision_rule_ids=(RULE_ID,), wrapper_rules=(),
        evidence_payload=None, llm_client=client, evidence_snapshot=snapshot, evidence_materials=material,
    )
    assert result.decisions[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 1
    facts = dict(result.customer_display_facts)[RULE_ID]
    assert validate_ct_display_facts(facts) == facts
    assert result.model_execution_stats["failed_rule_count"] == 0


@pytest.mark.asyncio
async def test_timeout_only_fails_new_rule_and_keeps_report_result_without_retry():
    class TimeoutClient(_Client):
        async def generate(self, prompt, *, allow_length_retry):
            assert allow_length_retry is False
            self.calls += 1
            raise TimeoutError("frozen timeout")

    snapshot, material = _session(_rows())
    client = TimeoutClient()
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(RULE_ID, REPORT_RULE_ID), decision_rule_ids=(RULE_ID, REPORT_RULE_ID),
        wrapper_rules=(), evidence_payload=None, llm_client=client,
        evidence_snapshot=snapshot, evidence_materials=material,
    )
    by_rule = {item.rule_id: item for item in result.decisions}
    assert by_rule[RULE_ID].reason_code == "model_transport_error"
    assert by_rule[REPORT_RULE_ID].reason_code == "requirement_satisfied"
    assert client.calls == result.llm_call_count == 1


@pytest.mark.asyncio
async def test_native_reference_budget_failure_does_not_erase_report_rule():
    rows = {source: [] for source in (ORDER_SOURCE, "exam_master", "exam_item_report", "daily_course_record")}
    for index in range(33):
        rows[ORDER_SOURCE].append({"order_id": f"O{index}", "order_name": "左膝CT", "order_status": "新开"})
        rows["exam_master"].append({"exam_id": f"E{index}", "order_id": f"O{index}"})
        rows["exam_item_report"].append({"exam_id": f"E{index}", "description": "骨折", "report_time": "2026-09-01T09:00:00+08:00"})
        rows["daily_course_record"].append({"document_id": f"D{index}", "record_content": f"O{index}左膝CT完成。"})
    snapshot, material = _session(rows)
    client = _Client()
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(RULE_ID, REPORT_RULE_ID), decision_rule_ids=(RULE_ID, REPORT_RULE_ID),
        wrapper_rules=(), evidence_payload=None, llm_client=client,
        evidence_snapshot=snapshot, evidence_materials=material,
    )
    by_rule = {item.rule_id: item for item in result.decisions}
    assert by_rule[RULE_ID].reason_code == "executor_exception"
    assert by_rule[REPORT_RULE_ID].reason_code == "requirement_satisfied"
    assert client.calls == result.llm_call_count == 0
    assert len(by_rule[REPORT_RULE_ID].fact_refs) == 99


def test_each_order_keeps_its_distinct_outcome_and_exact_source_span():
    event = replace(_event(), orders=(("o1", {"order_id": "O1", "order_name": "左膝CT"}),
                                     ("o2", {"order_id": "O2", "order_name": "胸部CT"})))
    text = "O1记载右膝CT；O2记载腹部CT。"
    split = text.index("O2")
    review = CtReviewInput((event,), (1,), (
        CourseClause("C1", "doc", text[:split], field_path="record_content", end=split),
        CourseClause("C2", "doc", text[split:], field_path="record_content", start=split, end=len(text)),
    ), {}, True)
    def evaluate(conflict_order):
        payload = {"schema_version": SCHEMA_VERSION, "unmatched_current_clause_ids": [], "events": [
            {"event_position": 1, "order_position": index,
             "record_state": "contradictory_description" if index == conflict_order else "unknown",
             "clause_ids": [f"C{index}"] if index == conflict_order else []}
            for index in (1, 2)
        ]}
        return evaluate_ct_review(review, payload)
    left, right = evaluate(1), evaluate(2)
    assert left.status == right.status == "non_compliant"
    assert left.refs == right.refs
    assert left.display_facts != right.display_facts
    for result in (left, right):
        assert validate_ct_display_facts(result.display_facts) == result.display_facts
        for order in result.display_facts["order_results"]:
            for location in order["course_locations"]:
                assert location["offset_unit"] == "unicode_codepoint"
                assert text[location["start"]:location["end"]] == review.clauses[order["order_position"] - 1].text


def test_raw_field_locations_survive_whitespace_and_non_bmp_characters():
    rows = _rows()
    body = "  🩺左膝CT已完成；\n  检查结果  骨折。"
    rows["daily_course_record"][0]["record_content"] = body
    review = _project(rows)
    for clause in review.clauses:
        assert clause.field_path == "record_content"
        assert body[clause.start:clause.end] == clause.text


@pytest.mark.asyncio
@pytest.mark.parametrize("state,expected", [("consistent_description", "compliant"), ("contradictory_description", "non_compliant")])
async def test_ct_order_evidence_survives_finalizer_sqlite_and_customer_projection(state, expected):
    from datetime import datetime
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    from app.services import custom_qc_workspace_service as workspace
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore, envelope_item_from_rule_result,
    )
    from app.services.custom_qc_workspace_service import project_customer_safe_result_item
    rows = _rows()
    body = "ORDER-001左膝CT完成。" if expected == "compliant" else "ORDER-001实际为右膝CT，与医嘱左膝不一致。"
    rows["daily_course_record"][0]["record_content"] = body
    snapshot, material = _session(rows)
    result = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=(RULE_ID,), decision_rule_ids=(RULE_ID,), wrapper_rules=(), evidence_payload=None,
        llm_client=_Client(_payload(state)), evidence_snapshot=snapshot, evidence_materials=material,
    )
    facts = dict(result.customer_display_facts)[RULE_ID]
    item = finalize_luxian_0609_reduced_customer_result(
        decision=reduce_luxian_0609_rule_decision(result.decisions[0]), raw_customer_display_facts=facts,
        evidence_snapshot=snapshot, evidence_materials=material,
    )
    item.update(record_id="visit", visit_id="visit", institute_id="test", patient_id="patient")
    assert item["status"] == expected
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    with Session(engine) as session:
        store.replace_for_job(session, job_row={"id": "ct-job", "created_by": "tester", "filters_json": json.dumps({
            "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
        })}, items=[item], now=datetime(2026, 9, 23),
            projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"), projection_key="test-key")
        session.commit()
        loaded = store.load_selected(session, root_job_id="ct-job", institute_id="test", patient_id="patient",
                                     visit_id="visit", rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")
    engine.dispose()
    published = project_customer_safe_result_item(loaded["items"][0], hmac_key="test-key")
    assert published["status"] == expected
    assert published["customer_display_facts"] == facts
    order = facts["order_results"][0]
    location = order["course_locations"][0]
    evidence = next(row for row in published["evidence"] if location["reference_position"] in row["decision_reference_positions"])
    assert evidence["source_type"] == "daily_course_record"
    assert evidence["source_ref"].startswith("src_")
    assert "source_document_id" not in evidence
    assert body[location["start"]:location["end"]] == body
    assert any(set(order["order_reference_positions"]) <= set(row["decision_reference_positions"]) for row in published["evidence"])

    # 任务导出的三种格式使用同一组已发布事实与文书定位，不重做语义关联。
    from io import StringIO
    import csv
    from openpyxl import load_workbook
    from app.services.qc_workspace.export_service import render_customer_safe_csv, render_customer_safe_workbook, render_customer_safe_html
    source_job = {"id": "ct-job", "filters": {"rule_set_key": "luxian_0609_qc_v1"}, "items": loaded["items"]}
    export_items, export_rows, summary = workspace._customer_export_rows(source_job, hmac_key="test-key")
    assert export_items[0]["customer_display_facts"] == facts
    evidence_text = export_rows[0][-1]
    assert "检查事件1/医嘱1" in evidence_text
    assert "record_content，字符0至" in evidence_text
    assert "定位缺失" not in evidence_text
    html = render_customer_safe_html(items=export_items, rows=export_rows, summary=summary)
    assert "检查事件1/医嘱1" in html and "record_content，字符0至" in html
    csv_rows = list(csv.reader(StringIO(render_customer_safe_csv(rows=export_rows, summary=summary).getvalue())))
    assert csv_rows[-1][-1] == evidence_text
    book = load_workbook(render_customer_safe_workbook(items=export_items, rows=export_rows, summary=summary))
    assert book["全部明细"].cell(2, 8).value == evidence_text
    assert "src_" not in evidence_text


@pytest.mark.parametrize("mutation", [
    lambda facts: facts["order_results"][0].update(status=[], issue_kind="order_course_consistent"),
    lambda facts: facts["order_results"][0].update(status=None, issue_kind="invented"),
    lambda facts: facts["event_results"][0].update(event_status=None, issue_kind="invented"),
    lambda facts: facts["order_results"][0].update(order_reference_positions=[{}]),
    lambda facts: facts["order_results"][0]["course_locations"][0].update(start=20, end=2),
    lambda facts: facts["order_results"][0]["course_locations"][0].update(field_path="patient_id"),
    lambda facts: facts.update(order_results=[]),
])
def test_public_order_binding_contract_rejects_invalid_types_and_missing_provenance(mutation):
    facts = deepcopy(evaluate_ct_review(_review(), _payload()).display_facts)
    mutation(facts)
    assert validate_ct_display_facts(facts) is None
