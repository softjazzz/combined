"""合成身份与时间边界；不读取真实病历。"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from app.services.qc_diagnostics.contracts import DiagnosticPackageError
from app.services.qc_diagnostics.sanitization import PayloadSanitizer


FIELDS = frozenset({"patient_name", "visit_id", "document_id", "content", "rows", "response",
                    "record_time", "end_time", "empty", "absent", "value", "chief_complaint"})


def sanitizer(**kwargs):
    return PayloadSanitizer(identities=["张测试", "测试医院"], allowed_fields=FIELDS,
                            date_shift_days=7, **kwargs)


def test_identity_mapping_is_consistent_across_material_model_and_feedback():
    raw = {"rows": [{"content": "张测试在测试医院就诊，住院号：7654321。", "visit_id": "7654321"}],
           "response": {"content": "张测试", "visit_id": "7654321"}, "patient_name": "张测试"}
    engine = sanitizer()
    clean = engine.sanitize(raw)
    assert clean["patient_name"] == clean["response"]["content"]
    assert clean["rows"][0]["visit_id"] == clean["response"]["visit_id"]
    assert clean["rows"][0]["visit_id"] in clean["rows"][0]["content"]
    assert all(value not in str(clean) for value in ("张测试", "测试医院", "7654321"))
    assert raw["patient_name"] == "张测试"
    assert "张测试" not in repr(engine)
    assert "张测试" not in str(engine.report())
    assert engine.report()["requires_human_review"] is True


def test_profiles_are_not_shared_between_cases():
    assert sanitizer().sanitize({"patient_name": "张测试"}) != sanitizer().sanitize({"patient_name": "张测试"})


def test_null_empty_missing_duplicate_rows_and_value_types_are_preserved():
    uid = UUID("11111111-1111-4111-8111-111111111111")
    raw = {"rows": (MappingProxyType({"document_id": uid, "content": None}),
                     MappingProxyType({"document_id": uid, "content": None})),
           "empty": "", "value": Decimal("1.2300")}
    clean = sanitizer().sanitize(raw)
    assert type(clean["rows"]) is tuple
    assert type(clean["rows"][0]) is MappingProxyType
    assert clean["rows"][0]["content"] is None
    assert clean["rows"][0]["document_id"] == clean["rows"][1]["document_id"] != uid
    assert type(clean["rows"][0]["document_id"]) is UUID
    assert clean["empty"] == "" and "absent" not in clean
    assert clean["value"].as_tuple() == raw["value"].as_tuple()


def test_dates_and_cross_midnight_intervals_shift_consistently():
    start = datetime(2026, 1, 31, 23, 50, tzinfo=ZoneInfo("Asia/Shanghai"))
    raw = {"record_time": start, "end_time": start + timedelta(minutes=30),
           "value": date(2026, 1, 31), "content": "2026-01-31 23:50；2026年2月1日00:20"}
    engine = sanitizer()
    clean = engine.sanitize(raw)
    assert clean["end_time"] - clean["record_time"] == timedelta(minutes=30)
    assert clean["record_time"].tzinfo == start.tzinfo
    assert clean["value"] == date(2026, 2, 7)
    assert clean["content"] == "2026-02-07 23:50；2026年2月8日00:20"
    assert engine.report()["temporal_equivalent"] is True


def test_dst_offset_change_cannot_claim_time_equivalence():
    engine = sanitizer()
    clean = engine.sanitize({"record_time": datetime(2026, 3, 3, 12, tzinfo=ZoneInfo("America/New_York"))})
    assert clean["record_time"].day == 10
    assert engine.report()["temporal_equivalent"] is False


def test_length_sensitive_chief_complaint_is_flagged_not_silently_equivalent():
    engine = sanitizer()
    engine.sanitize({"chief_complaint": "张测试咳嗽3天"})
    assert engine.report()["text_length_preserved"] is False
    assert engine.report()["document_references_require_rebuild"] is True


@pytest.mark.parametrize("text", ["Authorization: Bearer secret-token", "api_key=sk-secret",
                                "C:/private/record.txt", "https://private.example/patient",
                                r"隐写 \u5f20\u6d4b\u8bd5"])
def test_unsafe_unstructured_content_is_rejected_without_echo(text):
    with pytest.raises(DiagnosticPackageError) as error:
        sanitizer().sanitize({"content": text})
    assert text not in str(error.value)


def test_phone_id_and_email_are_removed_from_free_text():
    raw = "手机13800138000，身份证110101199001011234，邮箱synthetic@example.test"
    clean = sanitizer().sanitize({"content": raw})
    assert all(value not in clean["content"] for value in ("13800138000", "110101199001011234", "synthetic@example.test"))


def test_unknown_fields_and_invalid_model_json_are_not_silently_dropped():
    with pytest.raises(DiagnosticPackageError):
        sanitizer().sanitize({"extra_private_field": "secret"})
    with pytest.raises(DiagnosticPackageError):
        sanitizer().sanitize({"response": '{"patient_name": invalid}'})


def test_embedded_model_json_is_parsed_before_redaction():
    import json
    clean = sanitizer().sanitize({"response": '{"patient_name":"\\u5f20\\u6d4b\\u8bd5"}'})
    decoded = json.loads(clean["response"])
    assert decoded["patient_name"] != "张测试"
    assert "\\u5f20" not in clean["response"]


def test_uuid_in_unlabelled_value_is_still_an_identifier():
    raw = UUID("11111111-1111-4111-8111-111111111111")
    clean = sanitizer().sanitize({"value": raw})
    assert type(clean["value"]) is UUID and clean["value"] != raw


def test_identity_equal_to_year_cannot_destroy_timeline_silently():
    with pytest.raises(DiagnosticPackageError):
        sanitizer().sanitize({"visit_id": "2026", "content": "记录2026-01-01 08:00"})


def test_formatted_phone_keeps_same_alias_as_structured_value():
    engine = PayloadSanitizer(identities=[], allowed_fields=frozenset({"phone", "content"}), date_shift_days=7)
    clean = engine.sanitize({"phone": "138-0013-8000", "content": "13800138000"})
    assert clean["phone"] == clean["content"]


def test_unknown_time_field_does_not_claim_temporal_equivalence():
    engine = sanitizer()
    clean = engine.sanitize({"record_time": "September 7, 2026"})
    assert "2026" not in clean["record_time"]
    assert engine.report()["temporal_equivalent"] is False


@pytest.mark.parametrize("identity", ["\u200b", "\ud800", "   "])
def test_invalid_identity_profile_fails_with_safe_error(identity):
    with pytest.raises(DiagnosticPackageError):
        PayloadSanitizer(identities=[identity], allowed_fields=FIELDS, date_shift_days=7)
