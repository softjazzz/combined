"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

_VERIFIED_SOURCES = frozenset(
    {"frontpage_formal_qc", "coding_qc", "settlement_qc", "settlement_generate_qc"}
)


@dataclass(frozen=True)
class VerifiedQCIdentity:
    institute_id: str
    patient_id: str
    visit_id: str
    source_key: str

    def __post_init__(self) -> None:
        for name in ("institute_id", "patient_id", "visit_id", "source_key"):
            value = getattr(self, name)
            if (
                not isinstance(value, str)
                or not value.strip()
                or value != value.strip()
            ):
                raise ValueError(
                    f"verified QC {name} must be a nonblank canonical string"
                )
        if self.source_key not in _VERIFIED_SOURCES:
            raise ValueError(f"unsupported verified QC source: {self.source_key}")

    def columns(self) -> Dict[str, Any]:
        return {
            "identity_version": 1,
            "source_key": self.source_key,
            "institute_id": self.institute_id,
            "patient_id": self.patient_id,
            "visit_id": self.visit_id,
        }
