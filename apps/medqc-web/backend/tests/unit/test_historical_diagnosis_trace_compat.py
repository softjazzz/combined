"""历史074展示合同兼容：全部合成数据，不读取临床库或运行规则。"""
from copy import deepcopy
import json

import pytest

from app.services.custom_qc_workspace_service import project_customer_safe_batch_job
from app.services.luxian_0609.continuity_result_mapping import validate_published_continuity_facts


RULE = "LX0609-12-02-01"


def facts(mode="structured_transitions"):
    return {
        "verification_kind": "diagnosis_change_documentation_check",
        "diagnosis_change_count": 1 if mode == "structured_transitions" else None,
        "reason_recorded": False, "basis_recorded": False,
        "diagnosis_change_trace": {
            "schema_version": "diagnosis-change-trace-v1", "count_basis": mode,
            "observed_document_count": 1,
            "entries": [{
                "change_time": "2026-07-02", "original_diagnosis": "合成甲",
                "changed_diagnosis": "合成乙", "reason_state": "missing",
                "basis_state": "missing", "documents": [{
                    "source_ref": "src_" + "a" * 24, "source_type": "daily_course_record",
                    "record_time": "2026-07-02", "snippets": [{
                        "role": "change", "field_path": "record_content", "start": 0,
                        "end": 4, "text": "合成引文", "truncated": False,
                    }],
                }],
            }],
        },
    }


def job(raw):
    return {"id": "synthetic-history", "status": "completed",
            "filters": {"rule_set_key": "luxian_0609_qc_v1"},
            "items": [{"schema_version": "lx0609-customer-result-v2", "rule_id": RULE,
                       "rule_code": RULE, "status": "non_compliant",
                       "result_status": "non_compliant", "is_compliant": False,
                       "record_id": "SYNTHETIC-VISIT", "patient_id": "SYNTHETIC-PATIENT",
                       "institute_id": "SYNTHETIC-INSTITUTE", "patient_name": "SYNTHETIC-NAME",
                       "conclusion": "历史已保存结论", "suggestion": "历史已保存建议",
                       "diagnostic_trace": "SECRET-DEBUG", "customer_display_facts": raw}]}


@pytest.mark.parametrize("mode", ["structured_transitions", "declared_diagnoses", "document_mentions"])
def test_legacy_trace_projects_without_rewriting_saved_result(mode):
    raw = facts(mode); original = deepcopy(raw)
    valid, safe = validate_published_continuity_facts(rule_id=RULE, raw=raw, status="non_compliant")
    assert valid and safe == raw
    saved = job(raw); before = deepcopy(saved)
    dto = project_customer_safe_batch_job(saved, hmac_key="synthetic-test")
    assert saved == before and raw == original
    item = dto["items"][0]
    assert item["status"] == "non_compliant"
    assert item["conclusion"] == "历史已保存结论"
    assert item["customer_display_facts"] == raw
    for secret in ("SECRET-DEBUG", "SYNTHETIC-PATIENT", "SYNTHETIC-VISIT", "SYNTHETIC-NAME"):
        assert secret not in json.dumps(dto, ensure_ascii=False)


@pytest.mark.parametrize("mutation", [
    lambda f: f.update(unrecognized="SECRET"),
    lambda f: f.update(diagnosis_change_count=2),
    lambda f: f.update(reason_recorded="false"),
    lambda f: f["diagnosis_change_trace"].update(schema_version="diagnosis-change-events-v3"),
    lambda f: f["diagnosis_change_trace"].update(observed_document_count=2),
    lambda f: f["diagnosis_change_trace"].update(entries=[]),
    lambda f: f["diagnosis_change_trace"]["entries"][0].update(change_time="invalid"),
    lambda f: f["diagnosis_change_trace"]["entries"][0]["documents"][0].update(source_ref="RAW-PATIENT-ID"),
    lambda f: f["diagnosis_change_trace"]["entries"][0]["documents"][0].update(patient_id="SECRET"),
    lambda f: f["diagnosis_change_trace"]["entries"][0]["documents"][0]["snippets"][0].update(end=5),
    lambda f: f["diagnosis_change_trace"]["entries"][0]["documents"][0]["snippets"][0].update(field_path={}),
    lambda f: f["diagnosis_change_trace"]["entries"][0]["documents"][0]["snippets"][0].update(text="X" * 2001, end=2001),
])
def test_invalid_legacy_trace_is_not_silently_discarded(mutation):
    raw = facts(); mutation(raw)
    valid, _ = validate_published_continuity_facts(rule_id=RULE, raw=raw, status="non_compliant")
    assert not valid
    with pytest.raises(ValueError):
        project_customer_safe_batch_job(job(raw), hmac_key="synthetic-test")


def test_other_rule_and_conflicting_identity_still_rejected():
    raw = facts()
    assert not validate_published_continuity_facts(rule_id="LX0609-10-01-01", raw=raw)[0]
    saved = job(raw); saved["items"][0]["rule_code"] = "LX0609-10-01-01"
    with pytest.raises(ValueError):
        project_customer_safe_batch_job(saved, hmac_key="synthetic-test")


def test_existing_summary_contract_remains_readable():
    raw = facts(); raw.pop("diagnosis_change_trace")
    assert validate_published_continuity_facts(rule_id=RULE, raw=raw, status="non_compliant") == (True, raw)


def test_saved_envelope_roundtrip_preserves_history_and_rejects_wrong_scope():
    """合成落盘后按正式Canonical读取，不伪造授权，也不连接PG。"""
    from datetime import datetime
    import sqlalchemy as sa
    from sqlalchemy.orm import Session, sessionmaker
    from app.services.custom_qc_workspace_service import _record_result_envelopes_table
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

    table = _record_result_envelopes_table().to_metadata(sa.MetaData(), schema=None)
    engine = sa.create_engine("sqlite://")
    table.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    store = CanonicalResultStore(table)
    saved = job(facts("document_mentions"))
    saved.update(created_by="synthetic-owner", total_records=1)
    saved["filters"].update(rule_set_version="2026-06-09", record_refs=[{
        "institute_id": "SYNTHETIC-INSTITUTE", "patient_id": "SYNTHETIC-PATIENT", "visit_id": "SYNTHETIC-VISIT",
    }])
    saved["items"][0]["visit_id"] = "SYNTHETIC-VISIT"
    try:
        with Session(engine) as db:
            store.replace_for_job(db, job_row={**saved, "filters_json": json.dumps(saved["filters"])},
                                  items=saved["items"], now=datetime(2026, 7, 3),
                                  projector=lambda item: envelope_item_from_rule_result(item, hmac_key="synthetic-test"),
                                  projection_key="synthetic-test")
            db.commit()
            original = db.execute(sa.select(table.c.envelope_json)).scalar_one()
        items = store.load_root_job_items(job=saved, session_factory=factory)
        dto = project_customer_safe_batch_job({**saved, "items": items}, hmac_key="rotated-synthetic-key")
        assert dto["items"][0]["conclusion"] == "历史已保存结论"
        assert dto["items"][0]["customer_display_facts"] == saved["items"][0]["customer_display_facts"]
        for changed in ({"created_by": "different-owner"}, {"id": "different-job"},
                        {"filters": {**saved["filters"], "record_refs": [{
                            **saved["filters"]["record_refs"][0], "institute_id": "different-institute"}]}}):
            with pytest.raises(ValueError):
                store.load_root_job_items(job={**saved, **changed}, session_factory=factory)
        with Session(engine) as db:
            assert db.execute(sa.select(table.c.envelope_json)).scalar_one() == original
            corrupt = json.loads(original)
            corrupt["items"][0]["is_compliant"] = True
            db.execute(table.update().values(envelope_json=json.dumps(corrupt)))
            db.commit()
        with pytest.raises(ValueError, match="canonical_result_envelope_invalid"):
            store.load_root_job_items(job=saved, session_factory=factory)
    finally:
        engine.dispose()
