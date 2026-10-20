"""LX0609-03-01-04 医嘱核对范围：核对窗口与会诊记录内写明拒绝/暂缓的措施。

用户口径（2026-10-20）：
- 执行证据按“会诊记录前 3 天至会诊记录当天”开立的住院医嘱核对。系统没有可靠的
  会诊日期（consultation_record 的 consultation_time / request_time 全库为空，病程里
  “请××科会诊”只有约一半能找到且可能对错会诊），故固定回看 3 天，不从病程推断。
- 会诊记录写明患者或家属拒绝（或本科室暂缓、暂不考虑）某项措施时，只免该项，
  同一建议中的其余措施仍按医嘱核对。

本模块只做确定性的文本与日期判断，不调用模型，不决定规则状态。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, timedelta
import re

ORDER_WINDOW_LOOKBACK_DAYS = 3

_NORMALIZE_PATTERN = re.compile(r"[^一-鿿A-Za-z0-9]+")
_CLAUSE_BOUNDARY_PATTERN = re.compile(r"[，,；;。\n]")
_MEASURE_CLAUSE_SPLIT_PATTERN = re.compile(r"[，,；;。\n、]")
_OBJECT_SPLIT_PATTERN = re.compile(r"[、/]|和")

# 患者或家属明确不接受某项措施；写在会诊记录任意位置都算，但条件句（“若家属拒绝…”）不算。
_DECLINE_PATTERN = re.compile(
    r"(?:患者|家属|患方|病人)[^，,。；;:：\n]{0,8}?"
    r"(?:拒绝|不同意|不愿意?|不接受|表示不行|不行|不做|放弃|要求不|暂不|暂缓)"
    r"(?:行|做|进行|接受|使用|予以)?"
    r"(?P<object>[^，,。；;:：\n]{2,24})"
)
# 本科室写明的不执行决定。“暂不考虑/不予”几乎只出现在原科室的执行反馈里，全文都算；
# “暂缓/暂不”也常是会诊医师的建议本身（“建议暂缓抗凝”），只认“会诊执行”段之后的。
_EXECUTION_SECTION_PATTERN = re.compile(r"(?:会诊执行|执行情况)[^:：，,。\n]{0,4}[:：]")
_CLINICAL_DECISION_PATTERN = re.compile(
    r"(?:暂不考虑|不予)(?:行|做|进行|予以)?(?P<object>[^，,。；;:：\n]{2,24})"
)
_DEFER_PATTERN = re.compile(
    r"(?:暂缓|暂不)(?:行|做|进行|予以)?(?P<object>[^，,。；;:：\n]{2,24})"
)
_OBJECT_LEADING_PATTERN = re.compile(r"^(?:考虑|行|做|进行|接受|该|此|上述|相关|进一步|再)+")
_OBJECT_TRAILING_PATTERN = re.compile(r"(?:检查|治疗|操作|处理|手术治疗)+$")
# 同一措施的常见异名；只收录在真实会诊记录中出现过的写法。
_MEASURE_ALIASES = (
    (re.compile(r"纤维支气管镜|纤支镜|支纤镜|支气管镜|气管镜"), "支气管镜"),
    (re.compile(r"核磁共振|磁共振|核磁"), "MRI"),
)
_MIN_CORE_CHARS = 2
_MIN_CORE_COVERAGE = 0.6


def normalize_measure_text(text: str) -> str:
    value = _NORMALIZE_PATTERN.sub("", text or "")
    for pattern, alias in _MEASURE_ALIASES:
        value = pattern.sub(alias, value)
    return value.upper()


def _measure_core(text: str) -> str:
    value = normalize_measure_text(_OBJECT_LEADING_PATTERN.sub("", (text or "").strip()))
    core = _OBJECT_TRAILING_PATTERN.sub("", value)
    return core if len(core) >= _MIN_CORE_CHARS else ""


def _longest_common_run(left: str, right: str) -> int:
    best = 0
    previous = [0] * (len(right) + 1)
    for left_char in left:
        current = [0] * (len(right) + 1)
        for index, right_char in enumerate(right, start=1):
            if left_char == right_char:
                current[index] = previous[index - 1] + 1
                best = max(best, current[index])
        previous = current
    return best


def _core_matches(core: str, text: str) -> bool:
    normalized = normalize_measure_text(text)
    if not core or not normalized:
        return False
    if core in normalized:
        return True
    run = _longest_common_run(core, normalized)
    return run >= _MIN_CORE_CHARS and run >= len(core) * _MIN_CORE_COVERAGE


def _enclosing_clause(text: str, start: int) -> str:
    left = max((m.end() for m in _CLAUSE_BOUNDARY_PATTERN.finditer(text, 0, start)), default=0)
    right_match = _CLAUSE_BOUNDARY_PATTERN.search(text, start)
    return text[left:right_match.start() if right_match else len(text)]


def _split_objects(raw: str) -> list[str]:
    return [
        part for part in (
            _OBJECT_LEADING_PATTERN.sub("", item.strip()) for item in _OBJECT_SPLIT_PATTERN.split(raw)
        )
        if part
    ]


def declined_measure_objects(
    consultation_text: str,
    *,
    is_conditional: Callable[[str], bool],
) -> tuple[str, ...]:
    """返回会诊记录中写明不执行的措施原文（如“纤支镜检查”），不含条件句中的假设。"""

    text = consultation_text or ""
    section = _EXECUTION_SECTION_PATTERN.search(text)
    matches = [
        *_DECLINE_PATTERN.finditer(text),
        *_CLINICAL_DECISION_PATTERN.finditer(text),
        *(_DEFER_PATTERN.finditer(text, section.end()) if section is not None else ()),
    ]
    objects: list[str] = []
    for match in sorted(matches, key=lambda item: item.start()):
        if is_conditional(_enclosing_clause(text, match.start())):
            continue
        objects.extend(_split_objects(match.group("object")))
    return tuple(dict.fromkeys(item for item in objects if _measure_core(item)))


def recommendation_decline(
    recommendation_text: str,
    declined_objects: Sequence[str],
    *,
    is_conditional: Callable[[str], bool],
) -> tuple[tuple[str, ...], bool]:
    """逐个措施分句比对拒绝对象。

    返回（命中的拒绝措施原文, 是否整条建议都已写明不执行）。条件分句不计入“其余措施”。
    """

    cores = [(item, core) for item in declined_objects if (core := _measure_core(item))]
    if not cores:
        return (), False
    matched: list[str] = []
    remaining = False
    for clause in _MEASURE_CLAUSE_SPLIT_PATTERN.split(recommendation_text or ""):
        if len(normalize_measure_text(clause)) < _MIN_CORE_CHARS:
            continue
        hits = [item for item, core in cores if _core_matches(core, clause)]
        if hits:
            matched.extend(hits)
            continue
        if is_conditional(clause) or normalize_measure_text(clause) in {"建议", "可", "予"}:
            continue
        remaining = True
    unique = tuple(dict.fromkeys(matched))
    return unique, bool(unique) and not remaining


def measure_is_declined(measure: str, declined_objects: Sequence[str]) -> bool:
    """逐项核对返回的缺失措施是否正是会诊记录写明不执行的那一项。"""

    return any(
        (core := _measure_core(item)) and _core_matches(core, measure)
        for item in declined_objects
    )


def order_window_start(opinion_day: date) -> date:
    """医嘱核对窗口起点：会诊记录日期前 3 天（含当天共 4 个自然日）。"""

    return opinion_day - timedelta(days=ORDER_WINDOW_LOOKBACK_DAYS)


def current_checks_declined_after_communication(
    text: str, *, is_conditional: Callable[[str], bool],
) -> bool:
    """单一检查建议的本科室反馈：与患方沟通后实际拒绝进一步检查。"""
    sections = list(re.finditer(r"(?:处理|会诊执行|执行情况)\s*[:：;；]", text or ""))
    if not sections:
        return False
    feedback = text[sections[-1].end():]
    match = re.search(
        r"(?:患者|家属|患方|病人)[^。；;\n]{0,12}沟通后\s*[,，]\s*拒绝进一步检查",
        feedback,
    )
    return bool(match and not is_conditional(feedback[:match.end()]))
