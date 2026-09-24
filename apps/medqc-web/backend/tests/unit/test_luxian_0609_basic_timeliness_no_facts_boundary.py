"""基础时限族合法无独立事实结果的发布和 Canonical 读写。"""

from __future__ import annotations

from datetime import datetime
import json

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
from app.services.luxian_0609 import source_evidence_reader
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceUnavailable
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result, safe_customer_display_facts,
)
from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_published_customer_display_facts,
)
from tests.unit.test_luxian_0609_native_basic_timeliness import (
    _reduce_typed_basic, _rules, _typed_basic_session,
)


RULE_004 = "LX0609-09-01-01"
RULE_006 = "LX0609-02-01-02"
OTHER_TIME_RULES = (
    "LX0609-01-01-01", "LX0609-01-02-01", "LX0609-02-01-01", RULE_006,
)


@pytest.mark.parametrize("rule_id,rows,failures,expected", [
    (RULE_004, {"rescue_record": []}, None, ("not_applicable", "trigger_absent_complete")),
    (RULE_004, {}, {"rescue_record": SourceEvidenceUnavailable()}, ("data_gap", "source_unavailable")),
    (RULE_004, {"rescue_record": [], source_evidence_reader.CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY: [
        {"order_id": "SYNTHETIC-ORDER", "status_state": "unresolved"},
    ]}, None, ("data_gap", "required_field_missing")),
    (RULE_006, {"inpat_registration": [{"admission_datetime": "2026-07-15 13:48:49"}],
                "admission_record": [], "daily_course_record": [], "senior_course_record": []},
     None, ("not_applicable", "evaluation_window_not_mature")),
    ("LX0609-01-02-01", {"inpat_registration": [{"admission_datetime": "2026-07-16 08:00:00"}]},
     None, ("data_gap", "evaluation_window_not_mature")),
    ("LX0609-02-01-01", {"inpat_registration": [{"admission_datetime": "2026-06-01 08:00:00"}]},
     None, ("data_gap", "source_empty")),
    *((rule_id, {}, None, ("data_gap", "authoritative_time_missing")) for rule_id in OTHER_TIME_RULES),
])
def test_native_binding_published_sqlite_read_accepts_legal_absent_facts(rule_id, rows, failures, expected):
    session = _typed_basic_session(rows, selected_rule_ids=(rule_id,), failures=failures)
    execution, reduced = _reduce_typed_basic(session, (rule_id,))
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=_rules(rule_id), execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts, format_evidence=False,
    )[0]
    assert execution.customer_display_facts == ()
    assert (canonical["status"], canonical["reason_code"]) == expected
    assert getattr(execution, "llm_call_count", 0) == getattr(execution, "total_tokens", 0) == 0

    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    item = {**canonical, "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}
    try:
        with Session(engine) as db:
            store.replace_for_job(
                db, job_row={"id": "J", "created_by": "reviewer",
                             "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1",
                                                         "rule_set_version": "2026-06-09"})},
                items=[item], now=datetime(2026, 9, 24, 10),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"),
                projection_key="test-key",
            )
            db.commit()
            loaded = store.load_selected(
                db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            )["items"][0]
            assert (loaded["status"], loaded["reason_code"]) == expected
            assert "customer_display_facts" not in loaded
            assert loaded.get("evidence", []) == []
    finally:
        engine.dispose()


@pytest.mark.parametrize("rule_id,status,reason_code", [
    (RULE_004, "compliant", "requirement_within_threshold"),
    (RULE_004, "non_compliant", "requirement_violated"),
    (RULE_004, "data_gap", "rescue_record_missing_after_trigger"),
    (RULE_004, "not_applicable", "source_unavailable"),
    ("LX0609-09-01-02", "data_gap", "source_unavailable"),
    ("LX0609-01-01-01", "not_applicable", "trigger_absent_complete"),
])
def test_damaged_absent_facts_remain_rejected(rule_id, status, reason_code):
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"status": status, "reason_code": reason_code}, rule_id=rule_id,
        )


def test_legal_absence_does_not_allow_polluted_facts_or_contextless_read():
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"status": "not_applicable", "reason_code": "trigger_absent_complete",
             "customer_display_facts": {"source_document_id": "SYNTHETIC-INTERNAL"}},
            rule_id=RULE_004,
        )
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=RULE_004, raw=None)



def test_004_native_to_finalizer_projects_once(monkeypatch):
    import app.services.luxian_0609.native_basic_timeliness as native
    import app.services.luxian_0609.basic_timeliness_customer_projection as projection
    original = projection.safe_basic_timeliness_customer_display_facts
    calls = []
    def counted(*, rule_id, raw):
        calls.append(rule_id)
        return original(rule_id=rule_id, raw=raw)
    monkeypatch.setattr(native, "safe_basic_timeliness_customer_display_facts", counted)
    monkeypatch.setattr(projection, "safe_basic_timeliness_customer_display_facts", counted)
    session = _typed_basic_session({"rescue_record": [
        {"document_id": "rescue-synthetic-1", "record_time": "2026-06-01 11:00:00",
         "record_content": "抢救结束时间：2026年06月01日 09:00。"},
    ]}, selected_rule_ids=(RULE_004,))
    execution, reduced = _reduce_typed_basic(session, (RULE_004,))
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=_rules(RULE_004), execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts, format_evidence=False,
    )[0]
    assert (canonical["status"], canonical["reason_code"]) == ("compliant", "requirement_within_threshold")
    assert canonical["customer_display_facts"] == dict(execution.customer_display_facts)[RULE_004]
    assert calls == [RULE_004]
