"""2025 院内手术/操作目录：编码优先、名称精确回退，不使用关键词猜测。"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
import unicodedata
from typing import Any, Mapping


CATALOG_VERSION = "luxian-surgery-procedure-2025-v1"
SURGERY_CATEGORY = "手术"
OPERATION_CATEGORIES = frozenset({"治疗性操作", "诊断性操作", "介入治疗"})
_DATA_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "surgery_procedure_catalog_2025.csv"
)
_COMPOSITE_SEPARATOR = re.compile(r"[+＋|｜、；;，,]+")
_SUBCATEGORY_PATTERN = re.compile(r"^(\d{2})\.(\d{1,2})")
# 用户口径（2026-10-20）：目录未收录的编码，先看同一 ICD-9-CM-3 四位亚目下的目录条目，
# 全部为同一类操作时按该操作处理（1019 C21 电子结肠镜 45.2302 → 45.23 诊断性操作）。
# 目录连亚目都未收录时只认下列补充：床旁气管插管、暂时性气管切开、心肺复苏按治疗性操作
# （源库医嘱类型或首页手术操作栏即使写“手术”也不触发手术类文书，C03、C10）；胃镜、
# 支气管镜检查按基线029诊断性操作不触发（C21、C25）。名称只做精确匹配，不做关键词猜测。
_SUPPLEMENT_OPERATION_SUBCATEGORIES = {
    "31.1": "治疗性操作",
    "96.04": "治疗性操作",
    "99.60": "治疗性操作",
    "44.13": "诊断性操作",
    "33.23": "诊断性操作",
}
_SUPPLEMENT_OPERATION_NAMES = {
    "气管插管术": "治疗性操作",
    "气管内插管": "治疗性操作",
    "经口气管插管术": "治疗性操作",
    "气管切开术": "治疗性操作",
    "暂时性气管切开术": "治疗性操作",
    "经皮气管切开术": "治疗性操作",
    "经皮扩张气管切开术": "治疗性操作",
    "心肺复苏术": "治疗性操作",
    "心肺复苏": "治疗性操作",
    "胃镜检查": "诊断性操作",
    "电子胃镜检查": "诊断性操作",
    "电子结肠镜检查": "诊断性操作",
    "结肠镜检查": "诊断性操作",
    "电子支气管镜检查": "诊断性操作",
}


@dataclass(frozen=True)
class SurgeryProcedureClassification:
    code: str
    name: str
    category: str
    effective_level: str
    raw_level: str
    source: str
    match_mode: str

    @property
    def is_surgery(self) -> bool:
        return self.category == SURGERY_CATEGORY


def _normalize_code(value: Any) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or ""))).upper()


def _normalize_name(value: Any) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or ""))).strip()


@lru_cache(maxsize=1)
def _catalog_indexes() -> tuple[
    dict[str, SurgeryProcedureClassification],
    dict[str, SurgeryProcedureClassification],
]:
    by_code: dict[str, SurgeryProcedureClassification] = {}
    by_name: dict[str, SurgeryProcedureClassification] = {}
    with _DATA_PATH.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            item = SurgeryProcedureClassification(
                code=_normalize_code(row.get("code")),
                name=str(row.get("name") or "").strip(),
                category=str(row.get("category") or "").strip(),
                effective_level=str(row.get("effective_level") or "").strip(),
                raw_level=str(row.get("raw_level") or "").strip(),
                source=str(row.get("source") or "").strip(),
                match_mode="",
            )
            if not item.code or not item.name or item.category not in {
                SURGERY_CATEGORY,
                *OPERATION_CATEGORIES,
            }:
                raise ValueError("invalid surgery/procedure catalog row")
            if item.code in by_code or _normalize_name(item.name) in by_name:
                raise ValueError("duplicate surgery/procedure catalog key")
            by_code[item.code] = item
            by_name[_normalize_name(item.name)] = item
    if len(by_code) != 6513 or len(by_name) != len(by_code):
        raise ValueError("unexpected surgery/procedure catalog size")
    return by_code, by_name


def load_surgery_procedure_catalog() -> tuple[SurgeryProcedureClassification, ...]:
    """返回与质控引擎共用的只读目录，供配置查询和审计展示使用。"""

    by_code, _ = _catalog_indexes()
    return tuple(by_code.values())


def _matched(
    item: SurgeryProcedureClassification, match_mode: str
) -> SurgeryProcedureClassification:
    return SurgeryProcedureClassification(
        code=item.code,
        name=item.name,
        category=item.category,
        effective_level=item.effective_level,
        raw_level=item.raw_level,
        source=item.source,
        match_mode=match_mode,
    )


def classify_surgery_procedure(
    *, code: Any = None, name: Any = None
) -> SurgeryProcedureClassification | None:
    by_code, by_name = _catalog_indexes()
    normalized_code = _normalize_code(code)
    if normalized_code and (item := by_code.get(normalized_code)) is not None:
        return _matched(item, "code")
    normalized_name = _normalize_name(name)
    if normalized_name and (item := by_name.get(normalized_name)) is not None:
        return _matched(item, "name")

    candidates: list[SurgeryProcedureClassification] = []
    for token in _COMPOSITE_SEPARATOR.split(normalized_code):
        if token and (item := by_code.get(token)) is not None:
            candidates.append(_matched(item, "composite_code"))
    if not candidates:
        for token in _COMPOSITE_SEPARATOR.split(normalized_name):
            if token and (item := by_name.get(token)) is not None:
                candidates.append(_matched(item, "composite_name"))
    if not candidates:
        return _subcategory_operation(normalized_code) or _supplement_operation(
            normalized_code, normalized_name
        )
    candidates.sort(
        key=lambda item: (
            item.is_surgery,
            {"一级": 1, "二级": 2, "三级": 3, "四级": 4}.get(
                item.effective_level, 0
            ),
            item.source == "hospital_performance",
        ),
        reverse=True,
    )
    return candidates[0]


def _subcategory(code: str) -> str:
    match = _SUBCATEGORY_PATTERN.match(code)
    return f"{match.group(1)}.{match.group(2)}" if match else ""


@lru_cache(maxsize=1)
def _subcategory_categories() -> dict[str, frozenset[str]]:
    by_code, _ = _catalog_indexes()
    grouped: dict[str, set[str]] = {}
    for item in by_code.values():
        if key := _subcategory(item.code):
            grouped.setdefault(key, set()).add(item.category)
    return {key: frozenset(value) for key, value in grouped.items()}


def _operation(code: str, name: str, category: str, match_mode: str) -> SurgeryProcedureClassification:
    return SurgeryProcedureClassification(
        code=code, name=name, category=category, effective_level="",
        raw_level="", source="lx0609_supplement", match_mode=match_mode,
    )


def _subcategory_operation(code: str) -> SurgeryProcedureClassification | None:
    """同亚目目录条目全是同一类操作时才推断；含手术或多类混合不推断。"""

    key = _subcategory(code)
    categories = _subcategory_categories().get(key, frozenset())
    if len(categories) != 1 or SURGERY_CATEGORY in categories:
        return None
    return _operation(code, "", next(iter(categories)), "subcategory")


def _supplement_operation(code: str, name: str) -> SurgeryProcedureClassification | None:
    if category := _SUPPLEMENT_OPERATION_SUBCATEGORIES.get(_subcategory(code)):
        return _operation(code, name, category, "supplement_code")
    if category := _SUPPLEMENT_OPERATION_NAMES.get(name):
        return _operation(code, name, category, "supplement_name")
    return None


def is_non_surgical_procedure_order(row: Mapping[str, Any]) -> bool:
    """“手术”类型医嘱的名称精确命中目录或补充清单中的操作时，不作为手术医嘱。"""

    classification = classify_surgery_procedure(name=row.get("order_name"))
    return classification is not None and not classification.is_surgery


def classify_surgery_row(
    row: Mapping[str, Any],
) -> SurgeryProcedureClassification | None:
    code = next(
        (
            row.get(key)
            for key in (
                "surgery_code",
                "operation_code",
                "procedure_code",
                "planned_operation_code",
                "icd9_code",
            )
            if str(row.get(key) or "").strip()
        ),
        None,
    )
    name = next(
        (
            row.get(key)
            for key in (
                "surgery_name",
                "operation_name",
                "procedure_name",
                "planned_operation_name",
            )
            if str(row.get(key) or "").strip()
        ),
        None,
    )
    return classify_surgery_procedure(code=code, name=name)


def catalog_surgery_state(row: Mapping[str, Any]) -> bool | None:
    classification = classify_surgery_row(row)
    return None if classification is None else classification.is_surgery


def normalize_surgery_level(value: Any) -> str:
    normalized = _normalize_name(value).upper()
    if normalized in {
        "国考四级手术",
        "院内四级",
        "条件四级",
        "介入四级",
        "四级",
        "4",
        "Ⅳ",
        "IV",
    }:
        return "四级"
    if normalized in {"院内三级", "介入三级", "三级", "3", "Ⅲ", "III"}:
        return "三级"
    if normalized in {"二级", "2", "Ⅱ", "II"}:
        return "二级"
    if normalized in {"一级", "1", "Ⅰ", "I"}:
        return "一级"
    return ""


def effective_surgery_level(row: Mapping[str, Any]) -> str:
    classification = classify_surgery_row(row)
    if classification is not None:
        return classification.effective_level if classification.is_surgery else ""
    return normalize_surgery_level(row.get("surgical_level"))
