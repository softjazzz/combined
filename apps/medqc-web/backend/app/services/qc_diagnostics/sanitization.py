"""单病例诊断材料的本地转换；不是自由文本零遗漏或回放等价性的证明。

调用方必须先固定资料字段合同。身份字典只在本实例内存中存在，不进入报告；
导出还必须经过引用重建、规则等价验证及人工脱敏预览。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import re
import secrets
import unicodedata
from types import MappingProxyType
from uuid import UUID, uuid4

from .contracts import DiagnosticPackageError
from .package import _json
from .typed_values import encode_value


_IDENTITY_FIELDS = frozenset({
    "patient_name", "physician_name", "doctor_name", "institute_name", "institute_id",
    "patient_id", "visit_id", "document_id", "surgery_id", "order_id", "diagnosis_id",
    "phone", "mobile", "id_card", "address", "anesthetist_sign", "apply_doctor",
})
_FORBIDDEN_FIELDS = frozenset({"headers", "authorization", "api_key", "password", "token",
                               "connection_string", "dsn", "traceback", "secret"})
_LABEL = re.compile(
    r"((?:患者姓名|姓名|住院号|病案号|身份证号?|手机号?|电话|联系人|联系地址|家庭住址|医师|医生|签名|医院名称)\s*[:：]\s*)"
    r"([^\n\r;；,，。]{1,200}?)(?=\s*(?:年龄|性别|诊断|科室|床号|病区|出生日期)\s*[:：]|[\n\r;；,，。]|$)"
)
_IDENTIFIERS = re.compile(
    r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
    r"|(?<!\d)(?:\d{17}[\dXx]|1[3-9](?:[ \-–—]?\d){9})(?!\d)"
    r"|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
_FORBIDDEN_TEXT = re.compile(
    r"(?i)(?:authorization\s*[:=]|bearer\s+|api[_ -]?key\s*[:=]|password\s*[:=]|(?:access[_-]?)?token\s*[:=]"
    r"|https?://|(?:postgres(?:ql)?|mysql|redis)://|[a-z]:[/\\]|\\\\[a-z0-9]"
    r"|/(?:home|users|var|tmp|etc)/|\\u[0-9a-f]{4}|\\x[0-9a-f]{2})"
)
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})([-/.])(\d{1,2})\2(\d{1,2})(?!\d)")
_COMPACT_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})(\d{2})(\d{2})(?=(?:\d{6})?(?!\d))")
_CHINESE_DATE = re.compile(r"(?<!\d)(\d{4})年(\d{1,2})月(\d{1,2})日")
_PARTIAL_DATE = re.compile(r"(?<![\d年])(\d{1,2})月(\d{1,2})日")


def _fail(code: str) -> None:
    raise DiagnosticPackageError(code)


class PayloadSanitizer:
    """每个病例/包创建独立实例；不得作为全局对象或跨病例复用。"""

    def __init__(self, *, identities, allowed_fields: frozenset[str], date_shift_days: int):
        if type(identities) not in (list, tuple) or len(identities) > 1000:
            _fail("invalid_identity_context")
        if type(allowed_fields) not in (set, frozenset) or not all(
            type(key) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,95}", key)
            for key in allowed_fields
        ) or len(allowed_fields) > 2000:
            _fail("invalid_redaction_fields")
        if type(date_shift_days) is not int or not 0 < abs(date_shift_days) <= 3650:
            _fail("invalid_date_shift")
        self._fields = frozenset(allowed_fields)
        self._days = date_shift_days
        self._aliases: dict[str, str] = {}
        self._used: set[str] = set()
        self._changed = 0
        self._text_length_preserved = True
        self._temporal_equivalent = True
        self._short_identifier_text_unproven = False
        self._identity_bytes = 0
        self._text_normalized = False
        for identity in identities:
            if type(identity) is not str or not identity or len(identity) > 512:
                _fail("invalid_identity_context")
            self._alias(self._normalize(identity))

    def __repr__(self):
        return f"PayloadSanitizer(identity_count={len(self._aliases)})"

    def _alias(self, raw: str) -> str:
        if not raw.strip():
            _fail("invalid_identity_context")
        if re.fullmatch(r"1[3-9](?:[ \-–—]?\d){9}", raw):
            raw = re.sub(r"[ \-–—]", "", raw)
        if raw in self._aliases:
            return self._aliases[raw]
        try:
            self._identity_bytes += len(raw.encode("utf-8"))
        except UnicodeError:
            raise DiagnosticPackageError("invalid_identity_context") from None
        if len(self._aliases) >= 10000 or self._identity_bytes > 65536 or len(raw) > 512:
            _fail("identity_context_limit")
        while True:
            if raw.isascii() and raw.isdecimal():
                replacement = str(900000000 + secrets.randbelow(100000000))
            elif re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", raw):
                replacement = str(uuid4())
            else:
                replacement = "匿名_" + secrets.token_hex(8)
            if replacement not in self._used and replacement not in self._aliases and replacement != raw:
                break
        self._used.add(replacement)
        self._aliases[raw] = replacement
        return replacement

    def _normalize(self, value: str) -> str:
        # 去除视觉隐藏字符，统一全角字母/数字；不改写医疗单位或标点。
        result = unicodedata.normalize("NFC", "".join(
            chr(ord(char) - 65248) if ("０" <= char <= "９" or "Ａ" <= char <= "Ｚ" or "ａ" <= char <= "ｚ")
            else char for char in value if unicodedata.category(char) != "Cf"
        ))
        self._text_normalized |= result != value
        return result

    def _identity(self, value):
        if value is None or value == "":
            return value
        if type(value) not in (str, int, UUID) or (type(value) is int and value < 0):
            _fail("invalid_identity_value")
        raw = self._normalize(str(value))
        if raw in self._used:
            _fail("identity_alias_collision")
        mapped = self._alias(raw)
        if raw.isdecimal() and len(raw) < 4:
            self._short_identifier_text_unproven = True
        return int(mapped) if type(value) is int else UUID(mapped) if type(value) is UUID else mapped

    def _parsed(self, value: str):
        if value.lstrip().startswith(("{", "[")):
            return _json(value.encode("utf-8"), 20000)[0]
        return None

    def _collect(self, value, depth=0):
        if depth > 30:
            _fail("redaction_depth_limit")
        if type(value) in (dict, MappingProxyType):
            for key, child in value.items():
                if key not in self._fields or key.lower() in _FORBIDDEN_FIELDS:
                    _fail("unapproved_redaction_field")
                if key in _IDENTITY_FIELDS:
                    self._identity(child)
                else:
                    self._collect(child, depth + 1)
        elif type(value) in (list, tuple):
            for child in value:
                self._collect(child, depth + 1)
        elif type(value) is str:
            value = self._normalize(value)
            parsed = self._parsed(value)
            if parsed is not None:
                self._collect(parsed, depth + 1)
            else:
                if _FORBIDDEN_TEXT.search(value):
                    _fail("unsafe_unstructured_content")
                for match in _LABEL.finditer(value):
                    raw = match[2].strip()
                    # 已知姓名后面仍可能有临床正文，只收取确知的身份片段。
                    if not any(raw.startswith(known) for known in self._aliases):
                        if re.search(r"\s", raw):
                            _fail("ambiguous_identity_label")
                        self._alias(raw)
        elif type(value) is UUID:
            self._identity(value)

    def sanitize(self, value):
        # 先限定类型、深度和资源，再读取字段；不运行调用方对象的 repr/回调。
        encode_value(value)
        self._collect(value)
        literals = []
        for raw in sorted(self._aliases, key=len, reverse=True):
            if raw.isdecimal() and len(raw) < 4:
                continue
            escaped = re.escape(raw)
            literals.append(escaped)
        self._known = re.compile("|".join(literals)) if literals else None
        result = self._walk(value)
        encode_value(result)
        self._scan(result)
        return result

    def _scan(self, value):
        if type(value) in (dict, MappingProxyType):
            for child in value.values():
                self._scan(child)
        elif type(value) in (tuple, list):
            for child in value:
                self._scan(child)
        elif type(value) is str:
            if _FORBIDDEN_TEXT.search(value) or (self._known and self._known.search(value)):
                _fail("redaction_residual_detected")
        elif type(value) in (UUID, int):
            if str(value) in self._aliases and len(str(value)) >= 4:
                _fail("redaction_residual_detected")

    def _walk(self, value, depth=0):
        if depth > 30:
            _fail("redaction_depth_limit")
        if type(value) in (dict, MappingProxyType):
            result = {}
            for key, child in value.items():
                if key in _IDENTITY_FIELDS:
                    result[key] = self._identity(child)
                    self._changed += int(result[key] != child)
                elif key.endswith(("_time", "_datetime", "_date")) and type(child) is str and child:
                    normalized = self._normalize(child)
                    if not any(pattern.search(normalized) for pattern in (_ISO_DATE, _COMPACT_DATE, _CHINESE_DATE)):
                        result[key] = "[日期已隐去]"
                        self._changed += 1
                        self._temporal_equivalent = False
                        self._text_length_preserved &= len(child) == len(result[key])
                    else:
                        result[key] = self._walk(child, depth + 1)
                else:
                    result[key] = self._walk(child, depth + 1)
            return MappingProxyType(result) if type(value) is MappingProxyType else result
        if type(value) in (list, tuple):
            result = [self._walk(child, depth + 1) for child in value]
            return tuple(result) if type(value) is tuple else result
        if type(value) is UUID:
            self._changed += 1
            return self._identity(value)
        if type(value) in (date, datetime):
            try:
                shifted = value + timedelta(days=self._days)
            except OverflowError:
                _fail("date_shift_out_of_range")
            if type(value) is datetime and value.utcoffset() != shifted.utcoffset():
                self._temporal_equivalent = False
            self._changed += 1
            return shifted
        if type(value) is not str:
            return value
        parsed = self._parsed(value)
        if parsed is not None:
            result = json.dumps(self._walk(parsed, depth + 1), ensure_ascii=False, separators=(",", ":"))
        else:
            result = self._normalize(value)
            for pattern in (_ISO_DATE, _COMPACT_DATE, _CHINESE_DATE):
                if self._known and any(self._known.search(match[0]) for match in pattern.finditer(result)):
                    _fail("identity_time_overlap")
            result = self._known.sub(lambda match: self._alias(match[0]), result) if self._known else result
            result = _LABEL.sub(self._replace_label, result)
            result = _IDENTIFIERS.sub(lambda match: match[0] if match[0] in self._used else self._alias(match[0]), result)
            result = _ISO_DATE.sub(self._shift_separated_date, result)
            result = _COMPACT_DATE.sub(lambda match: self._shift_text_date(match, False).replace("-", ""), result)
            result = _CHINESE_DATE.sub(lambda match: self._shift_text_date(match, True), result)
            if _PARTIAL_DATE.search(result):
                # 无年份不能证明属于同一评价窗口；清除原值且明确失去时间等价性。
                result = _PARTIAL_DATE.sub("[日期已隐去]", result)
                self._temporal_equivalent = False
        if value != result:
            self._changed += 1
            self._text_length_preserved &= len(value) == len(result)
        return result

    def _replace_label(self, match):
        raw = match[2].strip()
        if any(raw.startswith(alias) for alias in self._used):
            return match[0]
        if re.search(r"\s", raw):
            _fail("ambiguous_identity_label")
        return match[1] + self._alias(raw)

    def _shift_separated_date(self, match):
        try:
            shifted = date(int(match[1]), int(match[3]), int(match[4])) + timedelta(days=self._days)
        except (ValueError, OverflowError):
            _fail("unparseable_source_date")
        separator = match[2]
        return separator.join((str(shifted.year), str(shifted.month).zfill(len(match[3])),
                               str(shifted.day).zfill(len(match[4]))))

    def _shift_text_date(self, match, chinese):
        try:
            shifted = date(*(int(part) for part in match.groups())) + timedelta(days=self._days)
        except (ValueError, OverflowError):
            _fail("unparseable_source_date")
        return f"{shifted.year}年{shifted.month}月{shifted.day}日" if chinese else shifted.isoformat()

    def report(self) -> dict[str, object]:
        return {
            "redaction_policy_version": "local-transform-v1",
            "changed_values": self._changed,
            "text_length_preserved": self._text_length_preserved,
            "text_normalized": self._text_normalized,
            "temporal_equivalent": self._temporal_equivalent,
            "short_identifier_text_unproven": self._short_identifier_text_unproven,
            "document_references_require_rebuild": self._changed > 0,
            "requires_human_review": True,
            "automatic_export_allowed": False,
        }
