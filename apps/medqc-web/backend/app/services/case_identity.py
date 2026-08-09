from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, NamedTuple


class CaseRef(NamedTuple):
    """一份住院病历的稳定身份。"""

    institute_id: str
    patient_id: str
    visit_id: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CaseRef":
        return cls(
            str(value.get("institute_id") or "").strip(),
            str(value.get("patient_id") or "").strip(),
            str(value.get("visit_id") or value.get("record_id") or "").strip(),
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "institute_id": self.institute_id,
            "patient_id": self.patient_id,
            "visit_id": self.visit_id,
        }

    def as_key(self) -> str:
        """返回无分隔符碰撞、可逆的内部病例键。"""

        return json.dumps(list(self), ensure_ascii=False, separators=(",", ":"))


CaseRefInput = CaseRef | Mapping[str, Any] | Sequence[str]


def coerce_case_ref(value: CaseRefInput) -> CaseRef:
    if isinstance(value, CaseRef):
        return value
    if isinstance(value, Mapping):
        return CaseRef.from_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 3:
        return CaseRef(*(str(part or "").strip() for part in value))
    raise ValueError("病例三坐标格式无效")


def normalize_case_refs(values: Sequence[CaseRefInput]) -> tuple[CaseRef, ...]:
    normalized: list[CaseRef] = []
    seen: set[CaseRef] = set()
    for value in values:
        case_ref = coerce_case_ref(value)
        if not all(case_ref):
            raise ValueError("病例三坐标不能为空")
        if case_ref in seen:
            continue
        seen.add(case_ref)
        normalized.append(case_ref)
    if not normalized:
        raise ValueError("病例三坐标集合不能为空")
    return tuple(normalized)


def normalize_source_case_refs(
    values: Sequence[CaseRefInput],
    *,
    default_institute_id: str,
) -> tuple[CaseRef, ...]:
    """在源库同步边界补固定机构号，其他坐标仍严格失败关闭。"""

    fallback = str(default_institute_id or "").strip()
    resolved: list[CaseRef] = []
    for value in values:
        case_ref = coerce_case_ref(value)
        resolved.append(
            CaseRef(
                case_ref.institute_id or fallback,
                case_ref.patient_id,
                case_ref.visit_id,
            )
        )
    return normalize_case_refs(resolved)


def stamp_source_rows_institute_id(
    values: Sequence[Mapping[str, Any]],
    *,
    default_institute_id: str,
) -> list[dict[str, Any]]:
    """给源库缺失机构号的行补固定值；已有机构号原样保留。"""

    fallback = str(default_institute_id or "").strip()
    normalized: list[dict[str, Any]] = []
    for value in values:
        row = dict(value)
        institute_id = str(row.get("institute_id") or "").strip()
        if not institute_id:
            if not fallback:
                raise ValueError("源病例缺少 institute_id，且未配置固定机构标识")
            row["institute_id"] = fallback
        else:
            row["institute_id"] = institute_id
        normalized.append(row)
    return normalized


def case_refs_from_records(values: Sequence[Mapping[str, Any]]) -> tuple[CaseRef, ...]:
    """从已解析病历行冻结三坐标；缺任一坐标立即失败关闭。"""

    return normalize_case_refs([CaseRef.from_mapping(value) for value in values])
