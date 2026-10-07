"""CT/MRI 报告后病程证据：record_time 只放真实记录时间，不把提交时间标成记录时间。"""

from __future__ import annotations

from app.services.luxian_0609.customer_evidence_enrichment import enrich_customer_evidence


class _Materials:
    def __init__(self, rows):
        self._rows = rows

    def rows(self, source_type):
        return self._rows.get(source_type, ())


def _evidence(source_type="senior_course_record"):
    return [{"source_type": source_type, "source_document_id": "doc-1", "source_ref": "src_" + "0" * 24}]


_ROW = {
    "document_id": "doc-1",
    "record_content": "今日查房，复查结果见上。",
    "submit_datetime": "2025-07-13 21:40:38",
}


def test_default_enrichment_keeps_legacy_submit_time_fallback_for_other_rules():
    rows = enrich_customer_evidence(
        _evidence(), evidence_materials=_Materials({"senior_course_record": (dict(_ROW),)})
    )
    assert rows[0]["record_time"] == "2025-07-13 21:40:38"


def test_strict_course_record_time_omits_submit_only_time():
    rows = enrich_customer_evidence(
        _evidence(),
        evidence_materials=_Materials({"senior_course_record": (dict(_ROW),)}),
        strict_course_record_time=True,
    )
    assert "record_time" not in rows[0]


def test_strict_course_record_time_keeps_real_record_time():
    row = dict(_ROW, record_time="2025-07-10 09:20:00")
    rows = enrich_customer_evidence(
        _evidence(),
        evidence_materials=_Materials({"senior_course_record": (row,)}),
        strict_course_record_time=True,
    )
    assert rows[0]["record_time"] == "2025-07-10 09:20:00"
