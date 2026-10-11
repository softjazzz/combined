"""术前事实三态及同源日期合同；固定事实验证正式发布边界。"""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime

import pytest

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.native_preop_content_execution import RULE_FIELDS
from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules

SUMMARY = "LX0609-04-01-04"
DISCUSSION = "LX0609-04-01-05"
TEXT = "拟行甲手术。麻醉方案已拟定。术前病情、诊断、指征和注意事项已逐项讨论，术者已查看患者。"


def fact(state, quote=None, reviewed=True):
    return {"state": state, "quote": quote, "reviewed_all_sections": reviewed}


def present_items(rule):
    return {field: fact("present", "拟行甲手术") for field in RULE_FIELDS[rule]}


def publish(rule, *, items=None, rows=None, documents=None):
    source = "presurg_summary" if rule == SUMMARY else "presurg_discussion"
    rows = rows if rows is not None else {source: [{"document_id": "D1", "record_content": TEXT}]}
    documents = documents if documents is not None else [{"document_id": "D1", "source_type": source, "items": items}]

    def reader(**kw):
        return SnapshotSourceRows.create(source_key=kw["source_key"], rows=rows.get(kw["source_key"], ()), truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="test-I", patient_id="test-P", visit_id="test-V",
        source_schema=None, created_at="2026-10-08T00:00:00+00:00", row_reader=reader,
    )

    class Client:
        calls = 0
        prompt = ""

        async def generate(self, prompt, **kwargs):
            self.calls += 1
            self.prompt = prompt
            return {"content": json.dumps({"documents": documents}), "usage": {}}

    client = Client()

    async def run():
        execution = await execute_luxian_0609_native_surgery_document_rules(
            rule_ids=(rule,), wrapper_rules=(), evidence_payload=None, llm_client=client,
            evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=(rule,),
        )
        decisions = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=execution.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
        final = finalize_luxian_0609_reduced_customer_result(
            decision=decisions[0], raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
            evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        )
        return final

    final = asyncio.run(run())
    assert client.calls == 1
    return final, client.prompt


def test_reliable_same_document_date_has_priority_over_model_missing():
    items = present_items(DISCUSSION)
    items["discussion_date"] = fact("missing")
    final, _ = publish(DISCUSSION, items=items, rows={"presurg_discussion": [{
        "document_id": "D1", "record_content": TEXT, "record_time": "2026-01-01",
    }]})
    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["missing_fields"] == []


def test_legacy_summary_null_does_not_confirm_missing_or_fill_content():
    items = {field: "拟行甲手术" for field in RULE_FIELDS[SUMMARY]}
    items["precautions"] = None
    final, _ = publish(SUMMARY, items=items)
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "source_readiness_unproven"
    facts = final["customer_display_facts"]
    assert facts["verification_kind"] == "preop_summary_content_uncertain"
    assert facts["uncertain_fields"] == ["precautions"]
    assert facts["missing_fields"] == []
    assert facts["documents"][0]["association_state"] == "not_required"
    assert "对应关系" not in final["findings"]


def test_summary_explicit_missing_has_priority_over_another_unknown():
    items = present_items(SUMMARY)
    items["precautions"] = fact("unknown", reviewed=False)
    items["planned_anesthesia"] = fact("missing")
    final, _ = publish(SUMMARY, items=items)
    assert final["status"] == "non_compliant"
    facts = final["customer_display_facts"]
    assert facts["missing_fields"] == ["planned_anesthesia"]
    assert facts["uncertain_fields"] == ["precautions"]
    assert facts["documents"][0]["uncertain_fields"] == ["precautions"]


@pytest.mark.parametrize("value", [
    date(2026, 1, 1), datetime(2026, 1, 1, 12, 0), "2026-01-01", "2026-01-01 12:00",
    "2026-01-01T12:00:00+08:00", "2026-01-01T04:00:00Z", "2024-02-29",
])
def test_discussion_date_accepts_reliable_date_or_datetime_without_timeliness_judgment(value):
    items = present_items(DISCUSSION)
    items["discussion_date"] = fact("unknown", reviewed=False)
    final, _ = publish(DISCUSSION, items=items, rows={"presurg_discussion": [{
        "document_id": "D1", "record_content": TEXT, "record_time": value,
    }]})
    assert final["status"] == "compliant"
    assert "uncertain_fields" not in final["customer_display_facts"]


@pytest.mark.parametrize("value", [None, "", "待填写", "2026-02-30", "2026-01-01 25:00", "2026-01-01尾串", False, 20260101])
def test_invalid_or_absent_record_time_does_not_replace_missing_discussion_date(value):
    items = present_items(DISCUSSION)
    items["discussion_date"] = fact("missing")
    final, _ = publish(DISCUSSION, items=items, rows={"presurg_discussion": [{
        "document_id": "D1", "record_content": TEXT, "record_time": value,
        "submit_datetime": "2026-01-01 12:00:00", "submitter": "test-signature",
    }]})
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["missing_fields"] == ["discussion_date"]


def test_date_priority_does_not_accept_a_forged_model_quote():
    items = present_items(DISCUSSION)
    items["discussion_date"] = fact("present", "未经提供的日期")
    final, _ = publish(DISCUSSION, items=items, rows={"presurg_discussion": [{
        "document_id": "D1", "record_content": TEXT, "record_time": "2026-01-01",
    }]})
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"]["verification_kind"] == "preop_fact_extraction_invalid"
    assert final["customer_display_facts"]["invalid_fields"] == ["discussion_date"]


def test_body_date_quote_is_accepted_without_structured_date():
    items = present_items(DISCUSSION)
    items["discussion_date"] = fact("present", "2026-01-01")
    final, _ = publish(DISCUSSION, items=items, rows={"presurg_discussion": [{
        "document_id": "D1", "record_content": TEXT + "讨论日期：2026-01-01。",
    }]})
    assert final["status"] == "compliant"


def test_discussion_date_cannot_be_filled_from_another_document():
    first, second = present_items(DISCUSSION), present_items(DISCUSSION)
    first["discussion_date"] = fact("missing")
    second["discussion_date"] = fact("unknown")
    final, _ = publish(DISCUSSION, rows={"presurg_discussion": [
        {"document_id": "D1", "record_content": TEXT},
        {"document_id": "D2", "record_content": TEXT, "record_time": "2026-01-01"},
    ]}, documents=[
        {"document_id": "D1", "source_type": "presurg_discussion", "items": first},
        {"document_id": "D2", "source_type": "presurg_discussion", "items": second},
    ])
    assert final["customer_display_facts"]["missing_fields"] == ["discussion_date"]
    assert final["customer_display_facts"]["documents"][0]["missing_fields"] == ["discussion_date"]
    assert final["customer_display_facts"]["documents"][1]["missing_fields"] == []


@pytest.mark.parametrize("legacy", [False, True])
def test_normal_summary_keeps_complete_contract_for_typed_or_legacy_present(legacy):
    items = {field: "拟行甲手术" for field in RULE_FIELDS[SUMMARY]} if legacy else present_items(SUMMARY)
    final, _ = publish(SUMMARY, items=items)
    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["verification_kind"] == "preop_content_complete"
    assert "uncertain_fields" not in final["customer_display_facts"]


@pytest.mark.parametrize("reviewed", [False, True])
def test_typed_summary_unknown_is_content_uncertainty_without_fake_association(reviewed):
    items = present_items(SUMMARY)
    items["precautions"] = fact("unknown", reviewed=reviewed)
    final, _ = publish(SUMMARY, items=items)
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"]["verification_kind"] == "preop_summary_content_uncertain"
    assert final["customer_display_facts"]["uncertain_fields"] == ["precautions"]
    assert final["customer_display_facts"]["documents"][0]["association_state"] == "not_required"
    assert final["customer_display_facts"]["documents"][0]["uncertain_fields"] == ["precautions"]
    assert final["customer_message"] == final["findings"]
    assert final["data_gap_details"]["reason_label"] == "术前小结内容待确认"
    assert "执行器" not in final["evidence"]


@pytest.mark.parametrize("invalid", [
    fact("missing", reviewed=False), fact("present"), fact("present", "拟行甲手术麻醉方案已拟定"),
    fact("unknown", "拟行甲手术"), fact("missing", "拟行甲手术"),
    {"state": [], "quote": None, "reviewed_all_sections": True},
    {"state": "missing", "quote": None, "reviewed_all_sections": 1},
    {"state": "unknown", "quote": None, "reviewed_all_sections": True, "raw_quote": "extra"},
])
def test_summary_invalid_tristate_or_noncontinuous_quote_is_isolated(invalid):
    items = present_items(SUMMARY)
    items["precautions"] = invalid
    final, _ = publish(SUMMARY, items=items)
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"]["verification_kind"] == "preop_fact_extraction_invalid"
    assert final["customer_display_facts"]["invalid_fields"] == ["precautions"]


@pytest.mark.parametrize(("text", "value", "expected"), [
    ("术中逐层辨认组织，保护邻近血管。", fact("present", "术中逐层辨认组织，保护邻近血管。"), "compliant"),
    ("操作中应避免伤及周围血管。", fact("present", "操作中应避免伤及周围血管。"), "compliant"),
    ("注意事项：", fact("missing"), "non_compliant"),
    ("手术要点见相关记录。", fact("unknown"), "data_gap"),
])
def test_summary_accepts_extracted_regular_or_synonymous_measures_without_keyword_inference(text, value, expected):
    items = present_items(SUMMARY)
    items["precautions"] = value
    final, _ = publish(SUMMARY, items=items, rows={"presurg_summary": [{
        "document_id": "D1", "record_content": TEXT + text,
    }]})
    assert final["status"] == expected



def event_case(first_state, second_state, *, same_event=False, ambiguous_second=False):
    first, second = present_items(SUMMARY), present_items(SUMMARY)
    first["planned_procedure"] = fact("present", "甲手术")
    first["precautions"] = fact(first_state, "拟行甲手术" if first_state == "present" else None)
    second_name = "甲手术" if same_event else "乙手术"
    second = {field: fact("present", f"拟行{second_name}") for field in RULE_FIELDS[SUMMARY]}
    second["planned_procedure"] = fact("present", second_name)
    second["precautions"] = fact(second_state, f"拟行{second_name}" if second_state == "present" else None)
    rows = {"presurg_summary": [
        {"document_id": "D1", "record_content": TEXT, "record_time": "2026-01-01 07:00:00"},
        {"document_id": "D2", "record_content": TEXT.replace("甲手术", f"{second_name}"),
         "record_time": "2026-01-01 07:10:00" if same_event else "2026-01-01 08:30:00" if ambiguous_second
         else "2026-01-01 10:00:00"},
    ], "surgery_record": [{
        "document_id": "S1", "surgery_name": "甲手术", "surgery_begin_time": "2026-01-01 08:00:00+08:00",
        "surgery_end_time": "2026-01-01 09:00:00+08:00", "surgery_process": "手术已完成。",
    }]}
    if not same_event and not ambiguous_second:
        rows["surgery_record"].append({
            "document_id": "S2", "surgery_name": "乙手术", "surgery_begin_time": "2026-01-01 11:00:00+08:00",
            "surgery_end_time": "2026-01-01 12:00:00+08:00", "surgery_process": "手术已完成。",
        })
    return publish(SUMMARY, rows=rows, documents=[
        {"document_id": "D1", "source_type": "presurg_summary", "items": first},
        {"document_id": "D2", "source_type": "presurg_summary", "items": second},
    ])[0]


def test_same_event_trusted_present_covers_unknown_but_document_unknown_is_retained():
    final = event_case("unknown", "present", same_event=True)
    assert final["status"] == "compliant"
    facts = final["customer_display_facts"]
    assert "uncertain_fields" not in facts
    assert [doc["event_index"] for doc in facts["documents"]] == [1, 1]
    assert facts["documents"][0]["uncertain_fields"] == ["precautions"]


def test_another_event_present_does_not_fill_unknown():
    final = event_case("unknown", "present")
    assert final["status"] == "data_gap"
    facts = final["customer_display_facts"]
    assert facts["uncertain_fields"] == ["precautions"]
    assert [doc["event_index"] for doc in facts["documents"]] == [1, 2]


def test_another_event_missing_keeps_non_compliant_and_document_unknown():
    final = event_case("missing", "unknown")
    assert final["status"] == "non_compliant"
    facts = final["customer_display_facts"]
    assert facts["missing_fields"] == ["precautions"]
    assert "uncertain_fields" not in facts
    assert facts["documents"][1]["uncertain_fields"] == ["precautions"]


def test_content_unknown_and_association_pending_are_explained_separately():
    final = event_case("unknown", "present", ambiguous_second=True)
    assert final["status"] == "data_gap"
    facts = final["customer_display_facts"]
    assert facts["verification_kind"] == "preop_summary_content_uncertain"
    assert facts["uncertain_fields"] == ["precautions"]
    assert facts["pending_fields"] == ["precautions"]
    assert facts["documents"][0]["association_state"] == "matched"
    assert facts["documents"][1]["association_state"] == "ambiguous"
    assert "内容无法确认" in final["findings"]
    assert "无法确认归属" in final["findings"]


@pytest.mark.parametrize("mutation", [
    lambda f: f.update(uncertain_fields=[]),
    lambda f: f.update(uncertain_fields=["not_a_field"]),
    lambda f: f.update(uncertain_fields=["precautions", "precautions"]),
    lambda f: f.update(uncertain_fields=[{}]),
    lambda f: f.update(missing_fields=["precautions"]),
    lambda f: f.update(raw_quote="extra"),
    lambda f: f.update(documents=[]),
    lambda f: f["documents"][0].update(document_index=True),
    lambda f: f["documents"][0].update(event_index=True),
    lambda f: f["documents"][0].update(association_state=[]),
    lambda f: f["documents"][0].update(uncertain_fields=[]),
    lambda f: f["documents"][0].update(missing_fields=["precautions"]),
    lambda f: f["documents"][0].update(uncertain_fields=["planned_anesthesia"]),
    lambda f: f["documents"].append(dict(f["documents"][0])),
])
def test_summary_unknown_public_contract_rejects_forged_facts(mutation):
    from copy import deepcopy
    from app.services.luxian_0609.canonical_result_finalizer import validate_luxian_0609_published_customer_display_facts
    from app.services.luxian_0609.surgery_document_result_mapping import safe_surgery_document_customer_display_facts

    items = present_items(SUMMARY)
    items["precautions"] = fact("unknown")
    final, _ = publish(SUMMARY, items=items)
    forged = deepcopy(final["customer_display_facts"])
    mutation(forged)
    assert safe_surgery_document_customer_display_facts(rule_id=SUMMARY, raw=forged) is None
    with pytest.raises(ValueError):
        validate_luxian_0609_published_customer_display_facts(rule_id=SUMMARY, raw=forged, status="data_gap")


@pytest.mark.parametrize("rule", [DISCUSSION, "LX0609-04-04-02", "LX0609-02-01-03"])
def test_summary_unknown_kind_is_scoped_to_summary_rule(rule):
    from app.services.luxian_0609.surgery_document_result_mapping import surgery_document_customer_fact_status_is_valid
    items = present_items(SUMMARY)
    items["precautions"] = fact("unknown")
    final, _ = publish(SUMMARY, items=items)
    assert not surgery_document_customer_fact_status_is_valid(rule_id=rule, status="data_gap", safe_facts=final["customer_display_facts"])


def sqlite_store(tmp_path):
    import sqlalchemy as sa
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore

    metadata = sa.MetaData()
    table = sa.Table("luxian_0609_record_result_envelopes", metadata,
        *[sa.Column(k, sa.String, primary_key=k == "id") for k in (
            "id", "job_id", "root_job_id", "created_by", "record_id", "institute_id", "patient_id", "visit_id", "rule_set_key", "rule_set_version",
        )], sa.Column("envelope_json", sa.Text), sa.Column("result_count", sa.Integer),
        sa.Column("created_at", sa.DateTime), sa.Column("updated_at", sa.DateTime),
    )
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'preop.sqlite'}")
    metadata.create_all(engine)
    return CanonicalResultStore(table), engine


@pytest.mark.parametrize("incomplete", [False, True])
def test_summary_unknown_persists_and_reads_after_engine_replacement(tmp_path, incomplete):
    import sqlalchemy as sa
    from sqlalchemy.orm import Session
    from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result

    items = present_items(SUMMARY)
    items["precautions"] = fact("unknown")
    if incomplete:
        items["planned_anesthesia"] = fact("missing")
    final, _ = publish(SUMMARY, items=items)
    final.update(institute_id="test-I", patient_id="test-P", visit_id="test-V")
    expected = envelope_item_from_rule_result(final, hmac_key="preop-test-key")
    store, engine = sqlite_store(tmp_path)
    filters = {"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09", "scoped_customer_rule_ids": [SUMMARY],
               "record_refs": [{"institute_id": "test-I", "patient_id": "test-P", "visit_id": "test-V"}]}
    with Session(engine) as session:
        store.replace_for_job(session, job_row={"id": "preop-test", "created_by": "test", "filters_json": json.dumps(filters)},
                              items=[final], now=datetime(2026, 10, 8),
                              projector=lambda item: envelope_item_from_rule_result(item, hmac_key="preop-test-key"), projection_key="preop-test-key")
        session.commit()
    engine.dispose()
    read_engine = sa.create_engine(f"sqlite:///{tmp_path / 'preop.sqlite'}")
    with Session(read_engine) as session:
        loaded = store.load_selected(session, root_job_id="preop-test", institute_id="test-I", patient_id="test-P", visit_id="test-V",
                                     rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")["items"][0]
    read_engine.dispose()
    for key in ("status", "reason_code", "customer_display_facts", "customer_message", "conclusion", "suggestion", "data_gap_details"):
        assert loaded.get(key) == expected.get(key)


@pytest.mark.parametrize("incomplete", [False, True])
@pytest.mark.parametrize("status", ["compliant", "not_applicable"])
def test_summary_unknown_or_missing_unknown_wrong_status_is_rejected_at_store(tmp_path, incomplete, status):
    from sqlalchemy.orm import Session
    from app.services.luxian_0609.canonical_result_finalizer import validate_luxian_0609_published_customer_display_facts
    from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result

    items = present_items(SUMMARY)
    items["precautions"] = fact("unknown")
    if incomplete:
        items["planned_anesthesia"] = fact("missing")
    final, _ = publish(SUMMARY, items=items)
    with pytest.raises(ValueError, match="合同"):
        validate_luxian_0609_published_customer_display_facts(rule_id=SUMMARY, raw=final["customer_display_facts"], status=status)
    final.update(status=status, result_status=status, display_status=status, is_compliant=True if status == "compliant" else None,
                 institute_id="test-I", patient_id="test-P", visit_id="test-V")
    store, engine = sqlite_store(tmp_path)
    filters = {"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09", "scoped_customer_rule_ids": [SUMMARY],
               "record_refs": [{"institute_id": "test-I", "patient_id": "test-P", "visit_id": "test-V"}]}
    try:
        with Session(engine) as session, pytest.raises(ValueError, match="合同"):
            store.replace_for_job(session, job_row={"id": "forged", "created_by": "test", "filters_json": json.dumps(filters)},
                                  items=[final], now=datetime(2026, 10, 8),
                                  projector=lambda item: envelope_item_from_rule_result(item, hmac_key="preop-test-key"), projection_key="preop-test-key")
    finally:
        engine.dispose()



def test_summary_data_gap_without_display_facts_preserves_renderer_fallback():
    from app.services.luxian_0609.customer_renderer import render_luxian_0609_customer_result
    from app.services.luxian_0609.decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
    from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision

    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id=SUMMARY, snapshot_hash="b" * 64, applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.DATA_GAP, qc_direction=QcDirection.UNKNOWN, reason_code="association_failed",
        fact_refs=("a" * 64,), evaluator_version="test",
    ))
    result = render_luxian_0609_customer_result(decision=decision, safe_customer_display_facts=None)
    assert result["status"] == "data_gap"
    assert "具体手术" in result["findings"]



@pytest.mark.parametrize("mode", ["no_ambiguous_document", "ambiguous_document_missing", "ambiguous_document_unknown"])
def test_new_summary_unknown_pending_requires_present_in_a_real_ambiguous_document(mode):
    from copy import deepcopy
    from app.services.luxian_0609.canonical_result_finalizer import validate_luxian_0609_published_customer_display_facts
    from app.services.luxian_0609.surgery_document_result_mapping import safe_surgery_document_customer_display_facts

    if mode == "no_ambiguous_document":
        items = present_items(SUMMARY)
        items["precautions"] = fact("unknown")
        final, _ = publish(SUMMARY, items=items)
        forged = deepcopy(final["customer_display_facts"])
        forged["pending_fields"] = ["precautions"]
    else:
        final = event_case("unknown", "present", ambiguous_second=True)
        forged = deepcopy(final["customer_display_facts"])
        forged["documents"][1]["missing_fields" if mode.endswith("missing") else "uncertain_fields"] = ["precautions"]
    assert safe_surgery_document_customer_display_facts(rule_id=SUMMARY, raw=forged) is None
    with pytest.raises(ValueError, match="合同"):
        validate_luxian_0609_published_customer_display_facts(rule_id=SUMMARY, raw=forged, status="data_gap")
