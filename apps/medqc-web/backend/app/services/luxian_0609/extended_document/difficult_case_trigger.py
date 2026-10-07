"""疑难讨论只排除已有明确当前解决声明的历史诊断不明表述。"""

import re


_HISTORICAL_PREFIX = re.compile(r"(?:入院时|入院初|既往|此前|先前)\s*$")
_CURRENT_RESOLUTION = re.compile(
    r"^\s*[，,]\s*(?:现(?:在)?|目前)(?:已)?"
    r"(?:明确诊断|诊断(?:已)?明确)([^，,。；;\n]*)"
)
_OTHER_PROBLEM = re.compile(r"另一|其他|其它|合并|并存")
_CURRENT_UNRESOLVED = re.compile(
    r"(?:至今|目前|仍|尚|依然)[^，,。；;\n]{0,24}"
    r"(?:未查明|未明确|不明|难以确定|待查)"
)


def _has_adjacent_resolution(suffix: str) -> bool:
    """只接受紧接当前问题的解决声明，并保留显式当前未解决信号。"""
    resolution = _CURRENT_RESOLUTION.match(suffix)
    return bool(
        resolution
        and not _OTHER_PROBLEM.search(resolution.group(1))
        and not _CURRENT_UNRESOLVED.search(suffix)
    )


def has_current_uncertain_diagnosis(text: str, markers: tuple[str, ...]) -> bool:
    """保留当前不明和未证实解决的触发，不改变批准的诊断范围。"""
    for marker in markers:
        for match in re.finditer(re.escape(marker), text):
            # 只消除紧邻历史时间词、且后面明确写当前已解决的这一处表述。
            # 其余当前不明仍各自生效，不能由另一诊断的明确状态全篇抵消。
            prefix = re.split(r"[，,。；;\n]", text[:match.start()])[-1]
            if _HISTORICAL_PREFIX.search(prefix) and _has_adjacent_resolution(text[match.end():]):
                continue
            return True
    return False
