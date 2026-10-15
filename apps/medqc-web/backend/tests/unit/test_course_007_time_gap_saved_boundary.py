"""资料不足须能保存，不能把没有病程区间事实变成整批任务失败。"""

from datetime import datetime
import json

import pytest
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

from app.services import custom_qc_workspace_service as workspace_module
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore,
    envelope_item_from_rule_result,
    safe_customer_display_facts,
)
from test_luxian_0609_course_quality_freeze import _run_chain


RULE = "LX0609-02-01-03"


@pytest.mark.asyncio
@pytest.mark.parametrize("day,status,reason", [
    ("2026-01-01", "not_applicable", "evaluation_window_not_mature"),
    ("2026-01-04", "data_gap", "authoritative_time_missing"),
    ("2026-01-03", "compliant", "requirement_within_threshold"),
])
async def test_no_course_result_survives_native_to_saved_roundtrip(day, status, reason):
    # 没有病程：入院当天尚未成熟；第 3 天仅知截止日期，不能精确判断 72 小时。
    rows = {"inpat_registration": ({"document_id": "admission-synthetic",
                                     "admission_datetime": "2026-01-01 08:00:00"},)}
    if status == "compliant":
        rows["daily_course_record"] = ({
            "document_id": "course-synthetic", "record_time": "2026-01-02 08:00:00",
            "record_content": "今日查房，继续观察。",
        },)
    _, _, _, item = await _run_chain(
        RULE, rows,
        evaluation_as_of_date=day,
    )
    assert item["status"] == status
    assert item["reason_code"] == reason
    assert item.get("customer_display_facts") is None
    item.update(record_id="V", visit_id="V", institute_id="I", patient_id="P")
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    try:
        with Session(engine) as db:
            store.replace_for_job(
                db,
                job_row={"id": "J", "created_by": "tester", "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})},
                items=[item], now=datetime(2026, 1, 4, 10),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"),
                projection_key="test-key",
            )
            db.commit()
            loaded = store.load_selected(
                db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            )["items"][0]
            assert loaded["status"] == status
            assert loaded["reason_code"] == reason
            assert not loaded.get("customer_display_facts")
    finally:
        engine.dispose()


@pytest.mark.parametrize("facts", [None, {}])
def test_customer_reported_time_gap_accepts_absent_facts(facts):
    assert safe_customer_display_facts({
        "rule_id": RULE, "status": "data_gap", "reason_code": "authoritative_time_missing",
        "customer_display_facts": facts,
    }, rule_id=RULE) == {}


@pytest.mark.parametrize("rule,status,reason,facts", [
    (RULE, "non_compliant", "authoritative_time_missing", None),
    (RULE, "data_gap", "authoritative_time_missing", {"medical_text": "合成敏感正文"}),
    ("LX0609-02-01-04", "non_compliant", "requirement_violated", None),
])
def test_defects_and_nonempty_invalid_facts_still_require_validation(rule, status, reason, facts):
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts({
            "rule_id": rule, "status": status, "reason_code": reason,
            "customer_display_facts": facts,
        }, rule_id=rule)
