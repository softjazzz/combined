"""匿名类型夹具；编解码不等于脱敏。"""
from datetime import date, datetime, time, timezone, timedelta, tzinfo
from decimal import Decimal
from enum import IntEnum
from types import MappingProxyType
from uuid import UUID
from zoneinfo import ZoneInfo
import json

import pytest

from app.services.qc_diagnostics.contracts import DiagnosticPackageError
from app.services.qc_diagnostics.typed_values import encode_value, decode_value


@pytest.mark.parametrize("value", [None, True, 12, -3, 2.5, "", "内容", date(2024, 1, 2),
    datetime(2024, 1, 2, 3, 4, tzinfo=timezone(timedelta(hours=8)), fold=1),
    time(2, 3, tzinfo=timezone.utc, fold=1), Decimal("1.2300"), UUID(int=42),
    (), [], {"present": None, "empty": ""}, MappingProxyType({"a": (1, 2)})])
def test_roundtrip_preserves_type(value):
    actual = decode_value(json.loads(json.dumps(encode_value(value), allow_nan=False)))
    assert type(actual) is type(value)
    assert actual == value
    if isinstance(value, Decimal):
        assert actual.as_tuple() == value.as_tuple()
    if isinstance(value, (datetime, time)):
        assert actual.fold == value.fold


def test_zoneinfo_fold_and_offset():
    value = datetime(2024, 11, 3, 1, 30, tzinfo=ZoneInfo("America/New_York"), fold=1)
    assert decode_value(encode_value(value)).tzinfo.key == "America/New_York"
    encoded = encode_value(value)
    encoded["value"] = "2024-11-03T01:30:00-04:00"
    with pytest.raises(DiagnosticPackageError):
        decode_value(encoded)


@pytest.mark.parametrize("value", [b"x", object(), float("nan"), float("inf"), Decimal("NaN")])
def test_reject_unsafe_values(value):
    with pytest.raises(DiagnosticPackageError):
        encode_value(value)


def test_reject_subclasses_and_enum():
    class Number(IntEnum):
        ONE = 1
    class Text(str):
        pass
    for value in [Number.ONE, Text("x")]:
        with pytest.raises(DiagnosticPackageError):
            encode_value(value)


@pytest.mark.parametrize("payload", [
    {"type": "int", "value": True}, {"type": "float", "value": float("nan")},
    {"type": "none", "extra": 1}, {"type": "unknown"},
    {"type": "dict", "value": [["a", {"type": "none"}], ["a", {"type": "none"}]]},
    {"type": "datetime", "value": "2024-01-01T00:00:00", "fold": 0, "zone": "../secret"},
])
def test_reject_malformed(payload):
    with pytest.raises(DiagnosticPackageError):
        decode_value(payload)


def test_resource_limits_and_cycle():
    for value in ["x" * (1048576 + 1), [None] * 50001, ["x" * 1048576] * 5]:
        with pytest.raises(DiagnosticPackageError):
            encode_value(value)
    value = []
    value.append(value)
    with pytest.raises(DiagnosticPackageError):
        encode_value(value)


def test_mapping_order_and_missing_remain_distinct():
    value = {"z": None, "a": ""}
    assert list(decode_value(encode_value(value))) == ["z", "a"]
    assert "missing" not in decode_value(encode_value(value))


def test_custom_timezone_not_called():
    class UnsafeZone(tzinfo):
        def utcoffset(self, dt):
            raise AssertionError("must not execute")
    with pytest.raises(DiagnosticPackageError):
        encode_value(datetime(2024, 1, 1, tzinfo=UnsafeZone()))


@pytest.mark.parametrize("value", [
    {"type": "str", "value": "x" * 1048577},
    {"type": "dict", "value": [["x" * 1048577, {"type": "none"}]]},
    {"type": "decimal", "value": "1" * 1048577},
    {"type": "decimal", "value": "NaN"},
    {"type": "decimal", "value": "1_000"},
    {"type": "decimal", "value": "1e999999999999999999999"},
    {"type": "time", "value": "12:00:00", "fold": True, "zone": None},
    {"type": "datetime", "value": "2024-01-01T00:00:00", "fold": 0, "zone": "Missing/Timezone"},
])
def test_decode_additional_strict_boundaries(value):
    with pytest.raises(DiagnosticPackageError):
        decode_value(value)


def test_decode_depth_node_and_total_text_limits():
    deep = {"type": "none"}
    for _ in range(32):
        deep = {"type": "list", "value": [deep]}
    cases = [deep, {"type": "list", "value": [{"type": "none"}] * 50000},
             {"type": "list", "value": [{"type": "str", "value": "x" * 1048576}] * 5}]
    for value in cases:
        with pytest.raises(DiagnosticPackageError):
            decode_value(value)


@pytest.mark.parametrize("value", [1 << 4096, -(1 << 4096)], ids=["positive", "negative"])
def test_large_integer_rejected_before_json_conversion(value):
    with pytest.raises(DiagnosticPackageError):
        encode_value(value)
    with pytest.raises(DiagnosticPackageError):
        decode_value({"type": "int", "value": value})


def test_maximum_integer_and_large_decimal_exponent_roundtrip():
    value = (1 << 4096) - 1
    assert decode_value(encode_value(value)) == value
    decimal = Decimal("1.2300E+999999999")
    encoded = encode_value(decimal)
    assert encoded["value"] == "1.2300E+999999999"
    assert len(encoded["value"]) < 30
    assert decode_value(encoded).as_tuple() == decimal.as_tuple()
