"""LX0609-03-01-04 医嘱核对范围：核对窗口与会诊记录内写明拒绝/暂缓的措施。

用户口径（2026-10-20）：
- 执行证据按“会诊记录前 3 天至会诊记录当天”开立的住院医嘱核对。系统没有可靠的
  会诊日期（consultation_record 的 consultation_time / request_time 全库为空，病程里
  “请××科会诊”只有约一半能找到且可能对错会诊），故固定回看 3 天，不从病程推断。
- 会诊记录写明患者或家属拒绝（或本科室暂缓、暂不考虑）某项措施时，只免该项，
  同一建议中的其余措施仍按医嘱核对。哪些措施被拒绝由第一阶段模型抽取并核对原文
  （用户口径 2026-10-22），本模块不再用拒绝词正则识别，只做措施名比对与日期计算。

本模块只做确定性的文本与日期判断，不调用模型，不决定规则状态。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
import re

ORDER_WINDOW_LOOKBACK_DAYS = 3

_NORMALIZE_PATTERN = re.compile(r"[^一-鿿A-Za-z0-9]+")
_OBJECT_LEADING_PATTERN = re.compile(r"^(?:考虑|行|做|进行|接受|该|此|上述|相关|进一步|再)+")
_GENERIC_MEASURE_PATTERN = re.compile(r"(?:检查|治疗|操作|处理|手术治疗)+")
# 同一措施的常见异名；只收录在真实会诊记录中出现过的写法。
_MEASURE_ALIASES = (
    (re.compile(r"纤维支气管镜|纤支镜|支纤镜|支气管镜|气管镜"), "支气管镜"),
    (re.compile(r"核磁共振|磁共振|核磁"), "MRI"),
)
_MIN_CORE_CHARS = 2


def normalize_measure_text(text: str) -> str:
    value = _NORMALIZE_PATTERN.sub("", text or "")
    for pattern, alias in _MEASURE_ALIASES:
        value = pattern.sub(alias, value)
    return value.upper()


def _measure_core(text: str) -> str:
    value = normalize_measure_text(_OBJECT_LEADING_PATTERN.sub("", (text or "").strip()))
    if _GENERIC_MEASURE_PATTERN.fullmatch(value):
        return ""
    # 只在已有明确检查/操作身份后折叠摘取边界，不能把器官名当作操作身份。
    # “肝脏检查/肝脏治疗”及“支气管镜检查/支气管镜治疗”仍不同。
    if re.fullmatch(r".+(?:镜|CT|MRI|超声|活检)检查", value):
        value = value[:-2]
    elif value.endswith("穿刺活检术"):
        value = value[:-1]
    for _, alias in _MEASURE_ALIASES:
        if value == f"{alias.upper()}检查":
            value = alias.upper()
            break
    return value if len(value) >= _MIN_CORE_CHARS else ""


def measure_is_declined(measure: str, declined_objects: Sequence[str]) -> bool:
    """逐项核对返回的缺失措施是否正是会诊记录写明不执行的那一项。"""

    # 公共子串不能证明是同一措施：左右肾穿刺、肝/肾活检和不同部位CT高度相似。
    # 只折叠明确异名及引导语，其余完整核心必须相同；一侧缺部位/侧别也不扩大拒绝范围。
    core = _measure_core(measure)
    return bool(core) and any(core == _measure_core(item) for item in declined_objects)


def order_window_start(opinion_day: date) -> date:
    """医嘱核对窗口起点：会诊记录日期前 3 天（含当天共 4 个自然日）。"""

    return opinion_day - timedelta(days=ORDER_WINDOW_LOOKBACK_DAYS)
