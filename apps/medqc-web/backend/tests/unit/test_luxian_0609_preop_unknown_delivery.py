"""079内容未知经正式发布链仍交付资料不足；不虚构手术归属。"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_preop_content_execution import RULE_FIELDS
from app.services.luxian_0609.native_surgery_document_execution import (
    execute_luxian_0609_native_surgery_document_rules,
)

RULE = "LX0609-04-01-05"


class FixedFacts:
    def __init__(self, items, source_type):
        self.items = items
        self.source_type = source_type
        self.calls = 0

    async def generate(self, _prompt, **_kwargs):
        self.calls += 1
        return {
            "content": json.dumps({
                "documents": [{
                    "document_id": "D1",
                    "source_type": self.source_type,
                    "items": self.items,
                }],
            }),
            "usage": {},
        }


def present_items():
    return {
        field: {"state": "present", "quote": "术前准备已完成", "reviewed_all_sections": True}
        for field in RULE_FIELDS[RULE]
    }


def publish(items, *, rule=RULE, source_rows=None):
    rows = source_rows or {
        "presurg_discussion": [{
            "document_id": "D1",
            "record_content": "术前准备已完成。手术方案、讨论意见、人员职称、风险防范等在本原文内受控核验。",
        }],
    }

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50,
        )

    evidence = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,), institute_id="test-I", patient_id="test-P", visit_id="test-V",
        source_schema=None, created_at="2026-10-07T18:00:00+00:00", row_reader=reader,
    )
    client = FixedFacts(items, "presurg_discussion" if rule == RULE else "presurg_summary")

    async def execute():
        result = await execute_luxian_0609_native_surgery_document_rules(
            rule_ids=(rule,), wrapper_rules=(), evidence_payload=None, llm_client=client,
            evidence_snapshot=evidence.snapshot, evidence_materials=evidence.materials,
            decision_rule_ids=(rule,),
        )
        reduced = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=result.decisions, expected_rule_ids=(rule,),
            snapshot=evidence.snapshot, evidence_materials=evidence.materials,
        )
        final = finalize_luxian_0609_reduced_customer_result(
            decision=reduced[0], raw_customer_display_facts=dict(result.customer_display_facts).get(rule),
            evidence_snapshot=evidence.snapshot, evidence_materials=evidence.materials,
        )
        return final, client.calls

    return asyncio.run(execute())


@pytest.mark.parametrize("reviewed", [False, True])
def test_unknown_discussion_content_remains_data_gap_after_finalizer(reviewed):
    items = present_items()
    items["specific_opinions"] = {
        "state": "unknown", "quote": None, "reviewed_all_sections": reviewed,
    }
    final, calls = publish(items)
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "source_readiness_unproven"
    facts = final["customer_display_facts"]
    assert facts["verification_kind"] == "preop_discussion_content_uncertain"
    assert facts["uncertain_fields"] == ["specific_opinions"]
    assert facts["missing_fields"] == []
    assert facts["documents"][0]["association_state"] == "not_required"
    assert calls == 1


def test_normal_discussion_keeps_existing_complete_contract():
    final, calls = publish(present_items())
    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["verification_kind"] == "preop_content_complete"
    assert "uncertain_fields" not in final["customer_display_facts"]
    assert calls == 1


def test_confirmed_missing_survives_another_unknown_content_field():
    items = present_items()
    items["specific_opinions"] = {
        "state": "unknown", "quote": None, "reviewed_all_sections": False,
    }
    items["recorder_signature"] = {
        "state": "missing", "quote": None, "reviewed_all_sections": True,
    }
    final, _ = publish(items)
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["verification_kind"] == "preop_content_incomplete"
    assert final["customer_display_facts"]["missing_fields"] == ["recorder_signature"]
    assert "uncertain_fields" not in final["customer_display_facts"]


def test_actual_surgery_association_ambiguity_keeps_strict_existing_contract():
    rule = "LX0609-04-01-04"
    procedure = "右侧腹股沟疝修补术"
    rows = {
        "presurg_summary": [{
            "document_id": "D1", "record_time": "2026-10-06 10:00:00",
            "record_content": f"术前准备已完成。拟行{procedure}，拟全麻，术者已查看患者。",
        }],
        "surgery_record": [{
            "document_id": "SURG",
            "surgery_name": "左侧腹股沟疝修补术",
            "surgery_begin_time": "2026-10-07 09:00:00+08:00",
            "surgery_end_time": "2026-10-07 10:00:00+08:00",
            "surgery_process": "实际手术已完成。",
        }],
    }
    items = {field: "术前准备已完成" for field in RULE_FIELDS[rule]}
    items["planned_procedure"] = procedure
    final, _ = publish(items, rule=rule, source_rows=rows)
    assert final["status"] == "data_gap"
    facts = final["customer_display_facts"]
    assert facts["verification_kind"] == "preop_surgery_association_ambiguous"
    assert any(doc["association_state"] == "ambiguous" for doc in facts["documents"])
    assert "uncertain_fields" not in facts

    from copy import deepcopy
    from app.services.luxian_0609.surgery_document_result_mapping import (
        safe_surgery_document_customer_display_facts,
    )
    forged = deepcopy(facts)
    for doc in forged["documents"]:
        doc["association_state"] = "not_required"
    assert safe_surgery_document_customer_display_facts(rule_id=rule, raw=forged) is None


@pytest.mark.parametrize("mutation", [
    lambda f: f.update(uncertain_fields=[]),
    lambda f: f.update(uncertain_fields=["not_a_field"]),
    lambda f: f.update(uncertain_fields=["specific_opinions", "specific_opinions"]),
    lambda f: f.update(uncertain_fields=[{}]),
    lambda f: f.update(missing_fields=["specific_opinions"]),
    lambda f: f.update(pending_fields=["specific_opinions"]),
    lambda f: f.update(raw_quote="未请求原文"),
    lambda f: f.update(documents=[]),
    lambda f: f["documents"][0].update(association_state="ambiguous"),
    lambda f: f["documents"][0].update(event_index=1),
    lambda f: f["documents"][0].update(missing_fields=["specific_opinions"]),
    lambda f: f["documents"][0].update(missing_fields=["not_a_field"]),
    lambda f: f["documents"][0].update(document_index=True),
    lambda f: f["documents"].append(dict(f["documents"][0])),
])
def test_content_uncertainty_rejects_forged_public_facts(mutation):
    from copy import deepcopy
    from app.services.luxian_0609.surgery_document_result_mapping import (
        safe_surgery_document_customer_display_facts,
        surgery_document_customer_fact_status_is_valid,
    )
    items = present_items()
    items["specific_opinions"] = {
        "state": "unknown", "quote": None, "reviewed_all_sections": False,
    }
    final, _ = publish(items)
    facts = final["customer_display_facts"]
    assert not surgery_document_customer_fact_status_is_valid(
        rule_id=RULE, status="compliant", safe_facts=facts,
    )
    assert safe_surgery_document_customer_display_facts(
        rule_id="LX0609-04-01-04", raw=facts,
    ) is None
    forged = deepcopy(facts)
    mutation(forged)
    assert safe_surgery_document_customer_display_facts(rule_id=RULE, raw=forged) is None


@pytest.mark.parametrize("reviewed", [False, True])
def test_unknown_discussion_persists_and_reads_in_new_sqlite_session(tmp_path, reviewed):
    from datetime import datetime

    import sqlalchemy as sa
    from sqlalchemy.orm import Session

    from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result

    items = present_items()
    items["specific_opinions"] = {
        "state": "unknown", "quote": None, "reviewed_all_sections": reviewed,
    }
    final, _ = publish(items)
    assert final["status"] == "data_gap"
    final.update(institute_id="test-I", patient_id="test-P", visit_id="test-V")
    store, engine = sqlite_store(tmp_path)
    filters = {
        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
        "scoped_customer_rule_ids": [RULE],
        "record_refs": [{"institute_id": "test-I", "patient_id": "test-P", "visit_id": "test-V"}],
    }
    expected = envelope_item_from_rule_result(final, hmac_key="g15-test-key")
    with Session(engine) as write_session:
        store.replace_for_job(
            write_session,
            job_row={"id": "g15-unknown", "created_by": "test", "filters_json": json.dumps(filters)},
            items=[final], now=datetime(2026, 10, 7, 18, 0, 0),
            projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="g15-test-key"),
            projection_key="g15-test-key",
        )
        write_session.commit()
    engine.dispose()
    read_engine = sa.create_engine(f"sqlite:///{tmp_path / 'unknown.sqlite'}")
    with Session(read_engine) as read_session:
        assert read_session is not write_session
        loaded = store.load_selected(
            read_session, root_job_id="g15-unknown",
            institute_id="test-I", patient_id="test-P", visit_id="test-V",
            rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
        )["items"][0]
    read_engine.dispose()
    assert loaded["status"] == "data_gap"
    for key in ("status", "reason_code", "customer_display_facts", "customer_evidence", "conclusion", "suggestion"):
        assert loaded.get(key) == expected.get(key)
    assert loaded["customer_display_facts"]["uncertain_fields"] == ["specific_opinions"]


@pytest.mark.parametrize("rule", ["LX0609-04-01-04", "LX0609-04-04-02", "LX0609-11-02-01"])
def test_content_unknown_status_contract_cannot_be_used_by_another_rule(rule):
    from app.services.luxian_0609.surgery_document_result_mapping import (
        surgery_document_customer_fact_status_is_valid,
    )
    items = present_items()
    items["specific_opinions"] = {
        "state": "unknown", "quote": None, "reviewed_all_sections": True,
    }
    final, _ = publish(items)
    assert not surgery_document_customer_fact_status_is_valid(
        rule_id=rule, status="data_gap", safe_facts=final["customer_display_facts"],
    )


def test_content_unknown_customer_message_explains_content_uncertainty():
    items = present_items()
    items["specific_opinions"] = {
        "state": "unknown", "quote": None, "reviewed_all_sections": True,
    }
    final, _ = publish(items)
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "source_readiness_unproven"
    assert final["findings"] == "术前讨论记录的具体讨论意见内容无法确认，本项暂无法判定。"
    assert final["suggestion"] == "请人工核对术前讨论记录的具体讨论意见原文，确认后重新质控。"
    assert final["customer_message"] == final["findings"]
    assert final["data_gap_details"]["reason_label"] == "术前讨论记录内容待确认"
    assert final["missing_sources"] == []
    assert "同步状态" not in json.dumps(final, ensure_ascii=False)


@pytest.mark.parametrize("status", ["compliant", "non_compliant", "not_applicable"])
def test_published_and_store_contract_reject_wrong_unknown_status(tmp_path, status):
    from app.services.luxian_0609.canonical_result_finalizer import (
        validate_luxian_0609_published_customer_display_facts,
    )
    from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result

    items = present_items()
    items["specific_opinions"] = {
        "state": "unknown", "quote": None, "reviewed_all_sections": True,
    }
    final, _ = publish(items)
    with pytest.raises(ValueError, match="合同"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=RULE, raw=final["customer_display_facts"], status=status,
            reason_code=final["reason_code"],
        )
    forged = dict(final, status=status, result_status=status, display_status=status,
                  is_compliant=True if status == "compliant" else False if status == "non_compliant" else None,
                  institute_id="test-I", patient_id="test-P", visit_id="test-V")
    from datetime import datetime
    from sqlalchemy.orm import Session

    store, engine = sqlite_store(tmp_path)
    filters = {
        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
        "scoped_customer_rule_ids": [RULE],
        "record_refs": [{"institute_id": "test-I", "patient_id": "test-P", "visit_id": "test-V"}],
    }
    try:
        with Session(engine) as write_session, pytest.raises(ValueError, match="合同"):
            store.replace_for_job(
                write_session,
                job_row={"id": "g15-forged", "created_by": "test", "filters_json": json.dumps(filters)},
                items=[forged], now=datetime(2026, 10, 7, 18, 0, 0),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="g15-test-key"),
                projection_key="g15-test-key",
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("association", [[], {}])
def test_content_unknown_rejects_non_string_document_association(association):
    from copy import deepcopy
    from app.services.luxian_0609.surgery_document_result_mapping import (
        safe_surgery_document_customer_display_facts,
    )
    items = present_items()
    items["specific_opinions"] = {
        "state": "unknown", "quote": None, "reviewed_all_sections": True,
    }
    final, _ = publish(items)
    forged = deepcopy(final["customer_display_facts"])
    forged["documents"][0]["association_state"] = association
    assert safe_surgery_document_customer_display_facts(rule_id=RULE, raw=forged) is None


def sqlite_store(tmp_path):
    import sqlalchemy as sa
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore
    metadata = sa.MetaData()
    # Store的可注入表合同；仅本地SQLite，绝不加载正式库连接。
    table = sa.Table(
        "luxian_0609_record_result_envelopes", metadata,
        *[sa.Column(k, sa.String, primary_key=k == "id") for k in (
            "id", "job_id", "root_job_id", "created_by", "record_id",
            "institute_id", "patient_id", "visit_id", "rule_set_key", "rule_set_version",
        )],
        sa.Column("envelope_json", sa.Text),
        sa.Column("result_count", sa.Integer),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'unknown.sqlite'}")
    metadata.create_all(engine)
    store = CanonicalResultStore(table)
    return store, engine
