"""024 恶性肿瘤手术淋巴结记录的“病种—术式”适用目录（院方口径 2026-10-11）。

院方依据单病种质控指标确认，只有下列组合要求核对淋巴结处理记录：

- 肺癌 C34，主要手术 32.2–32.6、32.9（LC-4）：记录清扫情况；
- 乳腺癌 C50，主要手术 85.2–85.4（BC-1）：记录前哨淋巴结活检情况，不要求必须腋窝清扫；
- 胃癌 C16，主要手术 43.4–43.9（GC-4）：仅确认属于根治性手术时适用；
- 结肠癌 C18、D01.0，主要手术 45.4、45.73–45.79、45.8（CoC-3.2）：仅 T2–4、N0–2、M0
  适用；分期取不到时资料不足。同时按 CoC-7 核对病理报告的淋巴结清扫个数及
  pTNM/ypTNM 分期，不设最低个数。

本模块只做确定性的编码、名称和分期解析，不调用模型。
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class _SiteRule:
    site: str
    diagnosis_code_pattern: re.Pattern[str]
    diagnosis_name_pattern: re.Pattern[str]
    procedure_code_pattern: re.Pattern[str]


_SITE_RULES = (
    _SiteRule(
        "lung",
        re.compile(r"^C34"),
        re.compile(r"肺|支气管"),
        re.compile(r"^32\.(?:[2-6]|9)"),
    ),
    _SiteRule(
        "breast",
        re.compile(r"^C50"),
        re.compile(r"乳腺|乳房"),
        re.compile(r"^85\.[2-4]"),
    ),
    _SiteRule(
        "gastric",
        re.compile(r"^C16"),
        re.compile(r"胃|贲门"),
        re.compile(r"^43\.[4-9]"),
    ),
    _SiteRule(
        "colon",
        re.compile(r"^(?:C18|D01\.0)"),
        re.compile(r"结肠|盲肠"),
        re.compile(r"^45\.(?:4|7[3-9]|8)"),
    ),
)
_MALIGNANT_NAME_PATTERN = re.compile(r"癌|恶性")
_METASTASIS_PATTERN = re.compile(r"转移")
_RADICAL_PATTERN = re.compile(r"根治")
_NON_RADICAL_PATTERN = re.compile(r"姑息|非根治")
_GASTRIC_LOCAL_EXCISION_PATTERN = re.compile(r"^43\.4")
_MAIN_SURGERY_SIGNS = frozenset({"1", "Y", "YES", "TRUE", "是", "主要手术", "主手术"})
# TNM 分期：前缀 yp/p/c 可选；病理报告常不写 M，M 缺失时只要未明确 M1 即不视为远处转移。
_STAGE_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<prefix>yp|p|c)?\s*T\s*(?P<t>is|[0-4][a-d]?|x)"
    r"\s*N\s*(?P<n>[0-3][a-c]?|x)"
    r"(?:\s*M\s*(?P<m>[01][a-c]?|x))?",
    re.IGNORECASE,
)
_PATHOLOGIC_STAGE_PATTERN = re.compile(
    r"(?<![A-Za-z])y?p\s*T\s*(?:is|[0-4][a-d]?|x)\s*N\s*(?:[0-3][a-c]?|x)",
    re.IGNORECASE,
)
_CHINESE_NUMBER = r"[一二三四五六七八九十两百]+"
_LYMPH_NODE_COUNT_PATTERN = re.compile(
    r"淋巴结[^。；;]{0,40}?(?:\d+|" + _CHINESE_NUMBER + r")\s*[枚个只](?!月)"
    r"|淋巴结[^。；;]{0,40}?\d+\s*/\s*\d+"
    r"|\d+\s*/\s*\d+[^。；;]{0,8}淋巴结"
)

SITE_LABELS = {
    "lung": "肺癌",
    "breast": "乳腺癌",
    "gastric": "胃癌",
    "colon": "结肠癌",
}
PATHOLOGY_ITEM_LABELS = {
    "lymph_node_count": "淋巴结清扫个数",
    "pathologic_stage": "pTNM/ypTNM 分期",
}


@dataclass(frozen=True)
class LymphNodeCatalogGate:
    """state: applicable / not_applicable / data_gap。"""

    state: str
    reason_code: str
    sites: tuple[str, ...] = ()
    colon_pathology_required: bool = False


def _clean(value: Any) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or ""))).strip()


def _code(value: Any) -> str:
    return _clean(value).upper()


def _row_text(row: Mapping[str, Any]) -> str:
    return unicodedata.normalize(
        "NFKC", " ".join(str(value) for value in row.values() if isinstance(value, str))
    )


def _procedure_rows(
    surgery_rows: Sequence[Mapping[str, Any]],
    mr_surgery_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, str, Mapping[str, Any]], ...]:
    main_rows = tuple(
        row for row in mr_surgery_rows
        if _code(row.get("main_surgery_sign")) in _MAIN_SURGERY_SIGNS
    )
    rows = (*surgery_rows, *(main_rows or mr_surgery_rows))
    return tuple(
        (_code(row.get("surgery_code")), _clean(row.get("surgery_name")), row)
        for row in rows
    )


def _site_cancer_confirmed(
    rule: _SiteRule, diagnosis_rows: Iterable[Mapping[str, Any]]
) -> bool:
    for row in diagnosis_rows:
        code = _code(row.get("diagnosis_code") or row.get("icd_code"))
        if code and rule.diagnosis_code_pattern.match(code):
            return True
        name = _clean(
            row.get("diagnosis_name") or row.get("diagnosis") or row.get("pathology_diagnosis")
        )
        if (
            name
            and rule.diagnosis_name_pattern.search(name)
            and _MALIGNANT_NAME_PATTERN.search(name)
            and not _METASTASIS_PATTERN.search(name)
        ):
            return True
    return False


def _parse_stages(texts: Iterable[str]) -> list[tuple[str, str, str]]:
    stages: list[tuple[str, str, str]] = []
    for text in texts:
        for match in _STAGE_PATTERN.finditer(text):
            stages.append((
                match.group("t").lower(),
                match.group("n").lower(),
                (match.group("m") or "").lower(),
            ))
    return stages


def _colon_stage_state(
    pathology_rows: Sequence[Mapping[str, Any]],
    other_rows: Sequence[Mapping[str, Any]],
) -> str:
    """返回 qualifying / out_of_scope / unknown；病理分期优先，分期冲突视为 unknown。"""

    stages = _parse_stages(_row_text(row) for row in pathology_rows)
    if not stages:
        stages = _parse_stages(_row_text(row) for row in other_rows)
    verdicts = set()
    for t, n, m in stages:
        if t == "x" or n == "x":
            continue
        if m.startswith("1"):
            verdicts.add("out_of_scope")
        elif t[0] in "234" and n[0] in "012":
            verdicts.add("qualifying")
        else:
            verdicts.add("out_of_scope")
    return verdicts.pop() if len(verdicts) == 1 else "unknown"


def procedures_outside_catalog(
    *,
    surgery_rows: Sequence[Mapping[str, Any]],
    mr_surgery_rows: Sequence[Mapping[str, Any]],
) -> bool:
    """手术均有编码且无一落在目录术式范围内时，无需判断恶性即可确定不适用。"""

    procedures = _procedure_rows(surgery_rows, mr_surgery_rows)
    codes = [code for code, _name, _row in procedures]
    return (
        bool(codes)
        and all(codes)
        and not any(
            rule.procedure_code_pattern.match(code) for rule in _SITE_RULES for code in codes
        )
    ) or (
        # 正式手术记录缺编码时，以首页全部手术编码为准。
        bool(mr_surgery_rows)
        and all(_code(row.get("surgery_code")) for row in mr_surgery_rows)
        and not any(
            rule.procedure_code_pattern.match(_code(row.get("surgery_code")))
            for rule in _SITE_RULES
            for row in (*surgery_rows, *mr_surgery_rows)
            if _code(row.get("surgery_code"))
        )
    )


def evaluate_lymph_node_catalog_gate(
    *,
    surgery_rows: Sequence[Mapping[str, Any]],
    mr_surgery_rows: Sequence[Mapping[str, Any]],
    diagnosis_rows: Sequence[Mapping[str, Any]],
    pathology_rows: Sequence[Mapping[str, Any]],
    discharge_rows: Sequence[Mapping[str, Any]],
) -> LymphNodeCatalogGate:
    """在已确认本次存在恶性肿瘤后，按院方目录判断 024 是否适用。"""

    procedures = _procedure_rows(surgery_rows, mr_surgery_rows)
    if not any(code for code, _name, _row in procedures):
        return LymphNodeCatalogGate("data_gap", "surgery_code_unavailable")
    sites: list[str] = []
    unresolved: list[str] = []
    for rule in _SITE_RULES:
        targets = [
            (code, name, row) for code, name, row in procedures
            if code and rule.procedure_code_pattern.match(code)
        ]
        if not targets or not _site_cancer_confirmed(rule, diagnosis_rows):
            continue
        if rule.site == "gastric":
            radical = unknown = False
            for code, name, row in targets:
                if _RADICAL_PATTERN.search(name) and not _NON_RADICAL_PATTERN.search(name):
                    radical = True
                elif _NON_RADICAL_PATTERN.search(name) or _GASTRIC_LOCAL_EXCISION_PATTERN.match(code):
                    continue
                else:
                    text = _row_text(row)
                    if _RADICAL_PATTERN.search(text) and not _NON_RADICAL_PATTERN.search(text):
                        radical = True
                    else:
                        unknown = True
            if radical:
                sites.append(rule.site)
            elif unknown:
                unresolved.append("gastric_radical_intent_unresolved")
            continue
        if rule.site == "colon":
            stage = _colon_stage_state(pathology_rows, (*discharge_rows, *surgery_rows))
            if stage == "qualifying":
                sites.append(rule.site)
            elif stage == "unknown":
                unresolved.append("colon_stage_unavailable")
            continue
        sites.append(rule.site)
    if sites:
        return LymphNodeCatalogGate(
            "applicable",
            "catalog_combination_confirmed",
            tuple(sites),
            colon_pathology_required="colon" in sites,
        )
    if unresolved:
        return LymphNodeCatalogGate("data_gap", unresolved[0])
    return LymphNodeCatalogGate("not_applicable", "catalog_combination_absent")


def colon_pathology_missing_items(
    pathology_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """CoC-7：病理报告须记录淋巴结清扫个数及 pTNM/ypTNM 分期。"""

    text = " ".join(_row_text(row) for row in pathology_rows)
    missing = []
    if not _LYMPH_NODE_COUNT_PATTERN.search(text):
        missing.append("lymph_node_count")
    # 否定须直接修饰分期填写/存在；“未见淋巴结转移 pT3N0”仍有真实分期。
    positive_stages = [
        match for match in _PATHOLOGIC_STAGE_PATTERN.finditer(text)
        if not re.search(
            r"(?:未(?:见|记录|填写)|无|缺少|待填)\s*(?:(?:病理)?分期\s*[:：]?\s*)?$",
            text[max(0, match.start() - 20):match.start()],
        )
        and not re.match(r"\s*(?:未(?:记录|填写)|待填)", text[match.end():])
    ]
    if not positive_stages:
        missing.append("pathologic_stage")
    return tuple(missing)
