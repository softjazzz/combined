"""严格、无执行能力的内部类型编解码。

本模块不做脱敏，输出可能包含完整敏感数据，禁止直接用于对外导出。
映射采用有序键值对，保留缺字段、空值以及容器类型的差异。
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .contracts import DiagnosticPackageError


def _require(condition: bool) -> None:
    if not condition:
        raise DiagnosticPackageError("invalid_typed_value")


class _Budget:
    def __init__(self) -> None:
        self.nodes = 0
        self.text_bytes = 0

    def node(self, depth: int) -> None:
        self.nodes += 1
        if depth > 30 or self.nodes > 50000:
            raise DiagnosticPackageError("typed_value_limit")

    def text(self, value: str) -> str:
        _require(type(value) is str)
        if len(value) > 1048576:
            raise DiagnosticPackageError("typed_value_limit")
        try:
            size = len(value.encode("utf-8"))
        except UnicodeError:
            raise DiagnosticPackageError("invalid_typed_value") from None
        self.text_bytes += size
        if size > 1048576 or self.text_bytes > 4194304:
            raise DiagnosticPackageError("typed_value_limit")
        return value


def _zone(value: object, budget: _Budget) -> str | None:
    if value is None:
        return None
    key = budget.text(value)
    _require(len(key) <= 255 and re.fullmatch(r"[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*", key) is not None)
    return key


def encode_value(value: object) -> dict:
    """仅接受明确列举的精确内建类型；不执行自定义序列化或 repr。"""
    return _encode(value, _Budget(), 0)


def _encode(value: object, budget: _Budget, depth: int) -> dict:
    budget.node(depth)
    kind = type(value)
    if value is None:
        return {"type": "none"}
    if kind in (bool, int, float, str):
        if kind is int:
            _require(value.bit_length() <= 4096)
        if kind is float:
            _require(math.isfinite(value))
        if kind is str:
            budget.text(value)
        return {"type": kind.__name__, "value": value}
    if kind in (date, datetime, time):
        if kind in (datetime, time):
            _require(value.tzinfo is None or type(value.tzinfo) in (timezone, ZoneInfo))
        result = {"type": kind.__name__, "value": budget.text(value.isoformat())}
        if kind in (datetime, time):
            result["fold"] = value.fold
            result["zone"] = _zone(value.tzinfo.key, budget) if type(value.tzinfo) is ZoneInfo else None
        return result
    if kind is Decimal:
        _require(value.is_finite())
        return {"type": "decimal", "value": budget.text(str(value))}
    if kind is UUID:
        return {"type": "uuid", "value": budget.text(str(value))}
    if kind in (list, tuple):
        _require(len(value) <= 50000)
        return {"type": kind.__name__, "value": [_encode(item, budget, depth + 1) for item in value]}
    if kind in (dict, MappingProxyType):
        _require(len(value) <= 50000)
        return {"type": "dict" if kind is dict else "mappingproxy", "value": [
            [budget.text(key), _encode(item, budget, depth + 1)] for key, item in value.items()
        ]}
    raise DiagnosticPackageError("invalid_typed_value")


def decode_value(payload: object) -> object:
    """读取已解析 JSON，严格拒绝额外字段与不合法类型；JSON 层另须拒绝重复属性。"""
    return _decode(payload, _Budget(), 0)


def _decode(payload: object, budget: _Budget, depth: int) -> object:
    budget.node(depth)
    _require(type(payload) is dict)
    _require(all(type(key) is str for key in payload))
    tag = payload.get("type")
    _require(type(tag) is str)
    budget.text(tag)
    keys = {"type"} if tag == "none" else {"type", "value"}
    if tag in ("datetime", "time"):
        keys |= {"fold", "zone"}
    _require(set(payload) == keys)
    if tag == "none":
        return None
    value = payload["value"]
    primitive = {"bool": bool, "int": int, "float": float, "str": str}
    if tag in primitive:
        _require(type(value) is primitive[tag])
        if tag == "int":
            _require(value.bit_length() <= 4096)
        if tag == "float":
            _require(math.isfinite(value))
        if tag == "str":
            budget.text(value)
        return value
    if tag in ("list", "tuple", "dict", "mappingproxy"):
        _require(type(value) is list and len(value) <= 50000)
        if tag in ("list", "tuple"):
            items = [_decode(item, budget, depth + 1) for item in value]
            return tuple(items) if tag == "tuple" else items
        result = {}
        for pair in value:
            _require(type(pair) is list and len(pair) == 2)
            key = budget.text(pair[0])
            _require(key not in result)
            result[key] = _decode(pair[1], budget, depth + 1)
        return MappingProxyType(result) if tag == "mappingproxy" else result
    _require(tag in ("decimal", "uuid", "date", "datetime", "time"))
    budget.text(value)
    try:
        if tag == "decimal":
            _require(re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value, flags=re.ASCII) is not None)
            result = Decimal(value)
            _require(result.is_finite())
            return result
        if tag == "uuid":
            result = UUID(value)
            _require(str(result) == value)
            return result
        if tag == "date":
            result = date.fromisoformat(value)
            _require(result.isoformat() == value)
            return result
        fold = payload["fold"]
        _require(type(fold) is int and fold in (0, 1))
        zone = _zone(payload["zone"], budget)
        result = (datetime if tag == "datetime" else time).fromisoformat(value)
        _require(result.isoformat() == value)
        result = result.replace(fold=fold)
        if zone is not None:
            with_zone = result.replace(tzinfo=ZoneInfo(zone))
            _require(with_zone.utcoffset() == result.utcoffset())
            result = with_zone
        return result
    except (ValueError, TypeError, OverflowError, InvalidOperation, ZoneInfoNotFoundError):
        raise DiagnosticPackageError("invalid_typed_value") from None
