"""N08：未知后续空标签不得抹掉本字段已记录的值。"""

import pytest
from luxian_0609_anesthesia_test_facts import N08_EMPTY_CASES, N08_FILLED_CASES, POST_TEXT

from test_luxian_0609_round2_document_boundaries import _final, _visits


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["心率：", "后续项目：", "心率：___", "心率：80次/分"])
async def test_filled_consciousness_survives_adjacent_unrelated_label(suffix):
    rows = _visits()
    rows["postane_surveil_record"][0]["record_content"] = POST_TEXT.replace("神志清醒", "神志清醒" + suffix, 1)
    final = await _final("LX0609-04-04-02", rows, anesthesia_facts=N08_FILLED_CASES[suffix])
    assert final["status"] == "compliant"
    assert "missing_fields_by_visit" not in final["customer_display_facts"]


@pytest.mark.asyncio
@pytest.mark.parametrize("body,missing", [
    ("术后意识：；恢复良好，呼吸循环稳定；已拔除气管导管；医嘱：继续监护6小时；无麻醉并发症。", "consciousness_status"),
    ("神志清醒；恢复情况：；已拔除气管导管；医嘱：继续监护6小时；无麻醉并发症。", "recovery_status"),
    ("神志清醒；恢复良好，呼吸循环稳定；已拔除气管导管；医嘱：继续监护6小时；特殊情况：", "special_situations"),
    ("术后意识：恢复情况：良好；已拔除气管导管；医嘱：继续监护6小时；无麻醉并发症。", "consciousness_status"),
])
async def test_own_empty_label_still_missing(body, missing):
    rows = _visits()
    rows["postane_surveil_record"][0]["record_content"] = body
    final = await _final("LX0609-04-04-02", rows, anesthesia_facts=N08_EMPTY_CASES[body])
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["missing_fields_by_visit"] == {
        "postanesthesia_visit": [missing],
    }
