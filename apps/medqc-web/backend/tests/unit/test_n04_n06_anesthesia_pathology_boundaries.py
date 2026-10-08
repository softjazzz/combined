"""独立复验发现的空标签与病理申请日期回退保护。"""

import pytest
from luxian_0609_anesthesia_test_facts import N04_BLANK_CASES, N04_NEGATIVE_CASES, N04_ADJACENT_CASES, N04_FILLED_CASES
from test_luxian_0609_round2_document_boundaries import _final, _visits
from test_luxian_0609_pathology_event_association import _rows, _run, SAMPLING, RESULT


@pytest.mark.asyncio
@pytest.mark.parametrize("source,old,new,field", [
    ("preane_surveil_record", "否认麻醉史", "既往麻醉史：", "anesthesia_history"),
    ("postane_surveil_record", "无麻醉并发症", "术后并发症：", "complication_assessment"),
    ("postane_surveil_record", "神志清醒", "术后意识：", "consciousness_status"),
    ("postane_surveil_record", "呼吸平稳", "呼吸系统：", "respiratory_status"),
])
async def test_prefixed_blank_label_cannot_prove_content(source, old, new, field):
    rows = _visits()
    assert old in rows[source][0]["record_content"]
    rows[source][0]["record_content"] = rows[source][0]["record_content"].replace(old, new)
    final = await _final("LX0609-04-04-02", rows, anesthesia_facts=N04_BLANK_CASES[field])
    assert final["status"] == "non_compliant"
    assert field in str(final["customer_display_facts"])


@pytest.mark.asyncio
async def test_prefixed_blank_signature_cannot_prove_signature():
    rows = _visits()
    rows["preane_surveil_record"][0].pop("anesthetist_sign")
    rows["preane_surveil_record"][0]["record_content"] += "麻醉医师签名："
    final = await _final("LX0609-04-04-02", rows, anesthesia_facts="n04_missing_signature")
    assert final["status"] == "non_compliant"
    assert "anesthetist_signature" in str(final["customer_display_facts"])


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["无", "未见异常"])
async def test_prefixed_label_with_negative_value_remains_complete(suffix):
    rows = _visits()
    rows["postane_surveil_record"][0]["record_content"] = (
        "术后意识：清醒；呼吸系统：平稳；循环：稳定；术后并发症：" + suffix
    )
    assert (await _final("LX0609-04-04-02", rows, anesthesia_facts=N04_NEGATIVE_CASES[suffix]))["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", [SAMPLING, RESULT])
async def test_sampling_before_request_day_is_not_excluded(rule_id):
    rows = _rows()
    rows["surgery_record"][0]["record_time"] = "2026-06-30 22:00:00"
    result = await _run(rows, rule_id)
    assert result["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["generic_specimen", "missing_request_time"])
async def test_unconfirmed_association_policy_stays_unchanged(kind):
    rows = _rows()
    if kind == "generic_specimen":
        for source in ("pathology_exam_master", "pathology_exam_report"):
            rows[source][0]["specimen_name"] = "手术标本"
    else:
        rows["pathology_exam_master"][0].pop("request_datetime")
    result = await _run(rows, SAMPLING)
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "association_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("body,missing,present", [
    ("术后意识： 呼吸系统：平稳；循环：稳定；术后并发症：无", "consciousness_status", "respiratory_status"),
    ("术后意识：呼吸系统：平稳；循环：稳定；术后并发症：无", "consciousness_status", "respiratory_status"),
    ("术后意识清醒 呼吸系统：；循环：稳定；术后并发症：无", "respiratory_status", "consciousness_status"),
    ("神志清醒；呼吸平稳；循环稳定；术后并发症： 备注：已访视", "complication_assessment", "consciousness_status"),
])
async def test_adjacent_labels_do_not_borrow_values(body, missing, present):
    rows = _visits()
    rows["postane_surveil_record"][0]["record_content"] = body
    final = await _final("LX0609-04-04-02", rows, anesthesia_facts=N04_ADJACENT_CASES[body])
    assert final["status"] == "non_compliant"
    fields = final["customer_display_facts"]["missing_fields_by_visit"]
    assert missing in str(fields)
    assert present not in str(fields)


@pytest.mark.asyncio
@pytest.mark.parametrize("separator", ["", " "])
async def test_adjacent_filled_labels_keep_their_values(separator):
    rows = _visits()
    rows["postane_surveil_record"][0]["record_content"] = separator.join([
        "术后意识：清醒", "呼吸系统：平稳", "循环：稳定", "术后并发症：未见异常",
    ])
    assert (await _final("LX0609-04-04-02", rows, anesthesia_facts=N04_FILLED_CASES[separator]))["status"] == "compliant"
