"""全目录的非问题结果不能因可选展示事实缺省而整批保存失败。"""

from datetime import datetime
import json

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

from app.services import custom_qc_workspace_service as workspace_module
from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_published_customer_display_facts,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore,
    envelope_item_from_rule_result,
    validated_customer_explanation,
)


RULE_IDS = [rule["rule_id"] for rule in load_luxian_0609_rules()]
STATES = [
    ("compliant", "requirement_within_threshold"),
    ("not_applicable", "trigger_absent_complete"),
    ("data_gap", "authoritative_time_missing"),
]


def _item(rule, status, reason, facts):
    return {"rule_id": rule, "status": status, "result_status": status, "display_status": status,
            "is_compliant": True if status == "compliant" else False if status == "non_compliant" else None,
            "reason_code": reason,
            "customer_display_facts": facts, "conclusion": "合成结果说明",
            "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}


@pytest.mark.parametrize("rule", RULE_IDS)
@pytest.mark.parametrize("status,reason", STATES)
@pytest.mark.parametrize("facts", [None, {}])
def test_all_rules_allow_optional_facts_for_non_problem_results(rule, status, reason, facts):
    assert validated_customer_explanation(
        _item(rule, status, reason, facts), rule_id=rule, status=status,
    ) == ({}, [])


@pytest.mark.parametrize("rule", RULE_IDS)
def test_all_rules_still_reject_unexplained_definite_problems(rule):
    with pytest.raises(ValueError, match="解释合同不完整"):
        validated_customer_explanation(
            _item(rule, "non_compliant", "requirement_violated", None),
            rule_id=rule, status="non_compliant",
        )


@pytest.mark.parametrize("status,reason", STATES)
@pytest.mark.parametrize("facts", [None, {}])
def test_whole_catalog_can_be_saved_and_read_without_changing_decisions(status, reason, facts):
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    try:
        with Session(engine) as db:
            store.replace_for_job(
                db, job_row={"id": "J", "created_by": "tester", "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})},
                items=[_item(rule, status, reason, facts) for rule in RULE_IDS],
                now=datetime(2026, 1, 4, 10),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"),
                projection_key="test-key",
            )
            db.commit()
            items = store.load_selected(
                db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            )["items"]
            assert {item["rule_id"] for item in items} == set(RULE_IDS)
            assert all(item["status"] == status and item["reason_code"] == reason for item in items)
            assert all(item["conclusion"] == "合成结果说明" for item in items)
    finally:
        engine.dispose()


@pytest.mark.parametrize("status,reason", STATES)
@pytest.mark.parametrize("rule", ["LX0609-02-01-03", "LX0609-03-01-04", "LX0609-06-01-01"])
def test_nonempty_invalid_facts_are_not_treated_as_optional(rule, status, reason):
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule, status=status, reason_code=reason,
            raw={"patient_name": "合成姓名", "medical_text": "合成病历正文"},
        )
