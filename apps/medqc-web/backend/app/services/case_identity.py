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


def case_refs_from_records(values: Sequence[Mapping[str, Any]]) -> tuple[CaseRef, ...]:
    """从已解析病历行冻结三坐标；缺任一坐标立即失败关闭。"""

    return normalize_case_refs([CaseRef.from_mapping(value) for value in values])
