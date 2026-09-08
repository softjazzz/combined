"""独立安全反证：合成数据，不包含真实患者信息。"""
import unicodedata

import pytest

from app.services.qc_diagnostics.contracts import DiagnosticPackageError
from app.services.qc_diagnostics.sanitization import PayloadSanitizer


def _sanitize_or_reject(value):
    sanitizer = PayloadSanitizer(
        identities=[], allowed_fields=frozenset(value), date_shift_days=30,
    )
    try:
        return sanitizer.sanitize(value), sanitizer.report()
    except DiagnosticPackageError:
        return None, None


def test_labeled_identity_does_not_consume_clinical_facts():
    result, _ = _sanitize_or_reject({
        "patient_name": "张三", "text": "姓名：张三 年龄：65岁 诊断：骨折。",
    })
    if result is None:
        return
    assert "65岁" in result["text"]
    assert "骨折" in result["text"]
    assert result["patient_name"] in result["text"]
    assert "张三" not in result["text"]


@pytest.mark.parametrize("source_date", ["2026/09/07", "20260907", "2026.09.07"])
def test_mixed_date_formats_do_not_claim_false_equivalence(source_date):
    result, report = _sanitize_or_reject({
        "text": f"入院时间{source_date} 10:00，完成2026-09-07 12:00",
    })
    if result is None:
        return
    assert source_date not in result["text"] or not report["temporal_equivalent"]


def test_known_visit_id_after_ascii_label_does_not_leak():
    result, _ = _sanitize_or_reject({
        "visit_id": "7654321", "text": "病历ID7654321检查已完成",
    })
    if result is None:
        return
    assert "7654321" not in result["text"]


@pytest.mark.parametrize("separator", ["\u200b", "\u200c", "\u200d", "\ufeff"])
def test_zero_width_identity_does_not_leak(separator):
    result, _ = _sanitize_or_reject({
        "patient_name": "张三", "text": f"患者张{separator}三，住院中",
    })
    if result is None:
        return
    visible = "".join(char for char in result["text"] if unicodedata.category(char) != "Cf")
    assert "张三" not in visible


def test_fullwidth_known_identifier_does_not_leak():
    result, _ = _sanitize_or_reject({
        "visit_id": "7654321", "text": "患者７６５４３２１已完成检查",
    })
    if result is None:
        return
    assert "7654321" not in unicodedata.normalize("NFKC", result["text"])


@pytest.mark.parametrize("formatted_phone", ["138-0013-8000", "138 0013 8000"])
def test_formatted_known_phone_does_not_leak(formatted_phone):
    result, _ = _sanitize_or_reject({
        "phone": "13800138000", "text": f"请联系{formatted_phone}了解情况",
    })
    if result is None:
        return
    assert "13800138000" not in result["text"].replace("-", "").replace(" ", "")
