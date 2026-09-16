"""Luxian0916 面向客户交付的唯一结果合同。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from types import MappingProxyType
from typing import Any


CUSTOMER_RESULT_STATUSES = frozenset(
    {
        "compliant",
        "non_compliant",
        "not_applicable",
        "data_quality_gap",
        "not_executed",
    }
)

_RULE_ID_PATTERN = re.compile(r"^LX0916-(?:00[1-9]|0[12]\d|03[0-2])$")
_REASON_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _freeze_mapping(value: Mapping[str, Any], *, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class Luxian0916RuleResult:
    """规则族一次性产出的客户可交付结果。"""

    rule_id: str
    status: str
    reason_code: str
    findings: str
    evidence: tuple[str, ...] = ()
    suggestion: str = ""
    document_anchors: tuple[Mapping[str, Any], ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not _RULE_ID_PATTERN.fullmatch(self.rule_id):
            raise ValueError("invalid Luxian0916 rule_id")
        if self.status not in CUSTOMER_RESULT_STATUSES:
            raise ValueError("invalid customer status")
        if not isinstance(self.reason_code, str) or not _REASON_CODE_PATTERN.fullmatch(
            self.reason_code
        ):
            raise ValueError("invalid reason_code")
        if self.status == "not_executed" and self.reason_code != "evaluation_window_not_mature":
            raise ValueError("not_executed requires evaluation_window_not_mature")
        for value, field_name in ((self.findings, "findings"), (self.suggestion, "suggestion")):
            if not isinstance(value, str) or "\x00" in value:
                raise ValueError(f"invalid {field_name}")
        if (
            not isinstance(self.evidence, tuple)
            or any(not isinstance(value, str) or "\x00" in value for value in self.evidence)
        ):
            raise ValueError("invalid evidence")
        if not isinstance(self.document_anchors, tuple):
            raise TypeError("document_anchors must be a tuple")
        object.__setattr__(
            self,
            "document_anchors",
            tuple(
                _freeze_mapping(anchor, field_name="document_anchor")
                for anchor in self.document_anchors
            ),
        )
        object.__setattr__(
            self,
            "diagnostics",
            _freeze_mapping(self.diagnostics, field_name="diagnostics"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "status": self.status,
            "reason_code": self.reason_code,
            "findings": self.findings,
            "evidence": list(self.evidence),
            "suggestion": self.suggestion,
            "document_anchors": [dict(anchor) for anchor in self.document_anchors],
            "diagnostics": dict(self.diagnostics),
        }
