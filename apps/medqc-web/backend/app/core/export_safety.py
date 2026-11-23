"""电子表格导出安全工具。

防止 CSV / Excel 单元格中的公式注入（DDE / Excel Formula Injection）：
- 对以 ``=``, ``+``, ``-``, ``@``, ``\\t``, ``\\r`` 开头，或前导空白后紧跟上述字符的字符串，
  统一添加前导单引号 ``'`` 转义，确保电子表格软件将其视为纯文本；
- 保留纯数字 / 合法负数等数值类型（``int`` / ``float`` / ``Decimal`` / ``bool``）及 ``None`` 不受破坏。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Sequence

_FORMULA_PREFIX_CHARS = frozenset({"=", "+", "-", "@", "\t", "\r"})
_LEADING_FORMULA_CHARS = frozenset({"=", "+", "-", "@"})
_CONTROL_WHITESPACE_CHARS = frozenset({"\t", "\r"})


def sanitize_spreadsheet_cell(value: Any) -> Any:
    """对电子表格单元格值进行公式注入安全转义。

    规则：
    - 非字符串（包括 ``None``、``bool``、``int``、``float``、``Decimal``、日期时间等）原样返回，
      避免破坏纯数字与合法负数的数值类型；
    - 空字符串原样返回；
    - 首字符属于 ``=``, ``+``, ``-``, ``@``, ``\\t``, ``\\r``，
      或跳过前导空白后首字符属于 ``=``, ``+``, ``-``, ``@``，
      或前导空白中包含 ``\\t`` / ``\\r`` 时，在原字符串前加单引号 ``'`` 转义。
    """
    if not isinstance(value, str) or not value:
        return value

    if value[0] in _FORMULA_PREFIX_CHARS:
        return f"'{value}"

    stripped = value.lstrip()
    leading_ws_len = len(value) - len(stripped)
    if leading_ws_len > 0:
        leading_ws = value[:leading_ws_len]
        if any(ch in _CONTROL_WHITESPACE_CHARS for ch in leading_ws):
            return f"'{value}"
        if stripped and stripped[0] in _LEADING_FORMULA_CHARS:
            return f"'{value}"

    return value


def sanitize_spreadsheet_row(values: Sequence[Any]) -> List[Any]:
    """对整行电子表格单元格应用 ``sanitize_spreadsheet_cell``。"""
    return [sanitize_spreadsheet_cell(value) for value in values]


def is_numeric_value(value: Any) -> bool:
    """判断值是否为受保护的数值类型（不含 bool）。"""
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


__all__ = [
    "sanitize_spreadsheet_cell",
    "sanitize_spreadsheet_row",
    "is_numeric_value",
]
