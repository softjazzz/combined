"""诊断和手术操作完整性校验的数据结构。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ClinicalEvidenceKind = Literal["diagnosis", "procedure"]
DiagnosisStatus = Literal["suspected", "confirmed", "ruled_out"]
ProcedureStatus = Literal["planned_only", "executed_only", "verified"]
CompletenessIssueType = Literal["missing_in_frontpage", "not_supported_by_record", "inconsistent"]
CompletenessItemCategory = Literal["diagnosis", "procedure"]


@dataclass(frozen=True)
class ClinicalEvidence:
    """来自病历文书的一条诊断或手术证据。"""

    kind: ClinicalEvidenceKind
    name: str
    code: str = ""
    record_time: str = ""
    source_doc_type: str = ""
    source_title: str = ""
    status: str = ""
    confidence: float = 0.8
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiagnosisTimelineItem:
    """单个诊断的发生发展时间轴。"""

    diagnosis_name: str
    icd_code: str = ""
    first_mention_time: str = ""
    first_mention_source: str = ""
    status: DiagnosisStatus = "suspected"
    evidence: list[ClinicalEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [item.to_dict() for item in self.evidence]
        return payload


@dataclass(frozen=True)
class ProcedureTimelineItem:
    """单个手术/操作的计划和执行验证结果。"""

    procedure_name: str
    icd9_code: str = ""
    plan_time: str = ""
    plan_source: str = ""
    execution_time: str = ""
    execution_source: str = ""
    status: ProcedureStatus = "executed_only"
    evidence: list[ClinicalEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = [item.to_dict() for item in self.evidence]
        return payload


@dataclass(frozen=True)
class ClinicalCompletenessIssue:
    """诊断/手术与草稿首页对照后的完整性问题。"""

    issue_type: CompletenessIssueType
    item_category: CompletenessItemCategory
    item_name: str
    severity: str = "warning"
    suggestion: str = ""
    evidence_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ClinicalTimeline:
    """病历级诊断和手术操作时间轴。"""

    visit_id: str = ""
    diagnoses: list[DiagnosisTimelineItem] = field(default_factory=list)
    procedures: list[ProcedureTimelineItem] = field(default_factory=list)
    issues: list[ClinicalCompletenessIssue] = field(default_factory=list)
    data_quality_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "visit_id": self.visit_id,
            "diagnoses": [item.to_dict() for item in self.diagnoses],
            "procedures": [item.to_dict() for item in self.procedures],
            "issues": [item.to_dict() for item in self.issues],
            "data_quality_flags": list(self.data_quality_flags),
        }
