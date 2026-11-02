"""首页质控 V2：取值归一与格式校验。"""
from __future__ import annotations

import pytest

from app.services.frontpage_qc_v2 import values as v
from tests.unit.frontpage_qc_v2_support import synthetic_id_card


@pytest.mark.parametrize("value", ["-", "—", "无", "张三", "0"])
def test_dash_and_none_markers_count_as_filled(value):
    assert v.is_filled(value)


@pytest.mark.parametrize("value", [None, "", "  ", "None", "null"])
def test_blank_values_are_not_filled(value):
    assert not v.is_filled(value)


def test_has_content_excludes_dash():
    assert not v.has_content("-")
    assert not v.has_content("无")
    assert v.has_content("青霉素")


@pytest.mark.parametrize(
    "code",
    ["K35.8", "K35.800", "K35.800x001", "I10.x00", "I10.x00x002", "A15.000+J99.8*", "K29.7G", "S06.000x002"],
)
def test_icd10_accepts_national_clinical_extension_codes(code):
    assert v.is_icd10(code)


@pytest.mark.parametrize("code", ["", "-", "K35800", "35.8", "肺炎"])
def test_icd10_rejects_malformed_codes(code):
    assert not v.is_icd10(code)


@pytest.mark.parametrize("code", ["47.01", "47.0100x001", "88.7x01", "39.95001", "93.391E3"])
def test_icd9cm3_accepts_national_clinical_extension_codes(code):
    assert v.is_icd9cm3(code)


@pytest.mark.parametrize("code", ["", "4701", "K35.8", "手术"])
def test_icd9cm3_rejects_malformed_codes(code):
    assert not v.is_icd9cm3(code)


def test_external_cause_and_morphology():
    assert v.is_external_cause("W19.x00x001")
    assert not v.is_external_cause("S06.000")
    assert v.is_morphology("M8140/3")
    assert v.is_morphology("m81403/3")
    assert not v.is_morphology("K80.1")


def test_icd10_range_uses_three_character_category():
    assert v.icd10_in_ranges("N40.x00", (("N40", "N51"),))
    assert not v.icd10_in_ranges("N52.0", (("N40", "N51"),))


def test_id_card_checksum():
    assert v.is_valid_id_card(synthetic_id_card())
    broken = synthetic_id_card()[:-1] + ("0" if synthetic_id_card()[-1] != "0" else "1")
    assert not v.is_valid_id_card(broken)
    assert not v.is_valid_id_card("510000********0000")


@pytest.mark.parametrize("value", ["13800000000", "0830-1234567", "12345678", "-"])
def test_valid_phone(value):
    assert v.is_valid_phone(value)


def test_invalid_phone():
    assert not v.is_valid_phone("123")


@pytest.mark.parametrize(
    ("value", "years"),
    [("45", 45.0), ("45岁", 45.0), ("6月", 0.5), ("2月15天", 2 / 12 + 15 / 365), ("10天", 10 / 365)],
)
def test_parse_age_years(value, years):
    assert v.parse_age_years(value) == pytest.approx(years)


def test_parse_age_rejects_garbage():
    assert v.parse_age_years("不详") is None


def test_codes_accept_codes_and_chinese_names():
    assert v.normalize_code("急诊", v.ADMISSION_ROUTE) == "1"
    assert v.normalize_code("2", v.ADMISSION_ROUTE) == "2"
    assert v.normalize_code("医嘱转社区卫生服务机构/乡镇卫生院", v.LEAVING_WAY) == "3"
    assert v.normalize_code("5", v.DISCHARGE_CONDITION) == "9"
    assert v.normalize_code("M", v.SEX) is None


def test_parse_datetime_variants():
    assert v.parse_datetime("2026-03-01 08:30:00").minute == 30
    assert v.parse_datetime("2026-03-01 08:30:00.123456") is not None
    assert v.parse_datetime("2026-08-19 08:01:00+08").hour == 8
    assert v.parse_datetime("2026/03/01") is not None
    assert v.parse_datetime("昨天") is None
