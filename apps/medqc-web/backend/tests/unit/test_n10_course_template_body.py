"""纯标题与签名不得证明已有临床正文，短正文仍有效。"""

import pytest
from luxian_0609_course_body_test_facts import LEGACY_MANUAL_COURSE_BODY_FACTS
from test_luxian_0609_round2_document_boundaries import _final, _surgery


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", ["LX0609-04-05-02", "LX0609-08-02-01"])
@pytest.mark.parametrize(
    "body",
    [
        "查房记录：\n医生签名：张医生",
        "主任医师查房记录",
        "病程记录：\n医师签名：李某 主治医师",
        "查房记录：医生签名：张医生",
        "病程记录： 医师签名：李某 主治医师",
        "术后首次病程记录",
    ],
)
async def test_title_and_signature_only_are_not_clinical_body(rule, body):
    final = await _run(rule, body)
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "required_field_missing"


async def _run(rule, body):
    row = {
        "document_id": "course-a",
        "document_title": "主任医师查房记录",
        "record_time": "2026-07-02 09:00:00",
        "record_content": body,
    }
    if rule == "LX0609-04-05-02":
        rows = _surgery()
        rows["senior_course_record"] = [row]
    else:
        rows = {
            "inpat_registration": [
                {"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"}
            ],
            "discharge_record": [{"document_id": "d", "discharge_date": "2026-07-03"}],
            "daily_course_record": [row],
        }
    return await _final(rule, rows, course_body_facts={body: LEGACY_MANUAL_COURSE_BODY_FACTS[body]})


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", ["LX0609-04-05-02", "LX0609-08-02-01"])
@pytest.mark.parametrize(
    "body",
    [
        "病情稳定。",
        "主任医师查房，病情稳定。\n医生签名：张医生",
        "病程记录：患者病情稳定。",
        "医生签名:继续观察。",
    ],
)
async def test_short_clinical_body_is_not_template(rule, body):
    assert (await _run(rule, body))["status"] == "compliant"
