"""公开投影不能截掉执行器已经选定的证据定位。"""
from app.services.custom_qc_workspace_service import _safe_evidence_rows


def test_public_evidence_keeps_interval_anchor_after_eighth_document():
    evidence = [
        {"source_type": "senior_course_record", "source_ref": f"src_{i:024x}",
         "field_path": "record_content", "record_time": "2025-08-26 09:50:29"}
        for i in range(10)
    ]
    item = {"customer_evidence": evidence, "evidence_items": evidence[:2]}
    rows = _safe_evidence_rows(item, hmac_key="test-only")
    assert len(rows) == 10
    assert [row["source_ref"] for row in rows] == [row["source_ref"] for row in evidence]
    assert rows[8]["record_time"] == "2025-08-26 09:50:29"


def test_public_evidence_keeps_sanitization_and_deduplication():
    rows = _safe_evidence_rows({"customer_evidence": [
        {"source_type": "daily_course_record", "source_document_id": "private-id",
         "record_content": "private raw text", "field_path": "../unsafe"},
        {"source_type": "daily_course_record", "source_document_id": "private-id"},
        {"source_type": "daily_course_record"},
    ]}, hmac_key="test-only")
    assert len(rows) == 1
    assert set(rows[0]) == {"source_type", "source_ref"}
    assert rows[0]["source_ref"].startswith("src_")
    assert "private" not in str(rows)
