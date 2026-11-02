"""首页质控 V2：统一首页文档模型。

规则只读 FrontpageDoc，不直接读数据库行。字段名、取值归一都在 adapter 里完成。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DiagnosisItem:
    index: int
    name: str
    code: str
    raw_admission_condition: str
    raw_discharge_condition: str
    is_main: bool
    source: str


@dataclass(frozen=True)
class SurgeryItem:
    index: int
    name: str
    code: str
    begin_at_raw: str
    begin_at: Optional[datetime]
    surgeon: str
    first_assistant: str
    second_assistant: str
    anesthesia_method: str
    anesthesiologist: str
    raw_level: str
    raw_incision: str
    raw_healing: str


@dataclass(frozen=True)
class SimpleDiagnosis:
    name: str
    code: str
    pathology_no: str


@dataclass
class FrontpageDoc:
    institute_id: str
    patient_id: str
    visit_id: str
    # 首页 mr 表原值（统一转为去空白字符串，None 转为空串）
    basic: Dict[str, str]
    discharge_diagnoses: List[DiagnosisItem]
    outpatient_diagnoses: List[SimpleDiagnosis]
    pathology_diagnoses: List[SimpleDiagnosis]
    surgeries: List[SurgeryItem]
    # None 表示首页没有费用记录
    cost: Optional[Dict[str, str]]
    admission_at: Optional[datetime] = None
    discharge_at: Optional[datetime] = None
    # 数据层面的提示，例如诊断来源，供结果追溯
    notes: List[str] = field(default_factory=list)

    def get(self, key: str) -> str:
        return self.basic.get(key, "")

    @property
    def main_diagnoses(self) -> List[DiagnosisItem]:
        return [item for item in self.discharge_diagnoses if item.is_main]

    @property
    def main_diagnosis(self) -> Optional[DiagnosisItem]:
        mains = self.main_diagnoses
        return mains[0] if mains else None

    @property
    def other_diagnoses(self) -> List[DiagnosisItem]:
        main = self.main_diagnosis
        return [item for item in self.discharge_diagnoses if item is not main]

    @property
    def main_surgery(self) -> Optional[SurgeryItem]:
        return self.surgeries[0] if self.surgeries else None

    @property
    def other_surgeries(self) -> List[SurgeryItem]:
        return self.surgeries[1:]

    def all_diagnosis_codes(self) -> List[str]:
        return [item.code for item in self.discharge_diagnoses if item.code]

    def as_display(self) -> Dict[str, Any]:
        """供结果详情展示的首页字段视图。"""
        return {
            "basic": dict(self.basic),
            "discharge_diagnoses": [item.__dict__ for item in self.discharge_diagnoses],
            "outpatient_diagnoses": [item.__dict__ for item in self.outpatient_diagnoses],
            "pathology_diagnoses": [item.__dict__ for item in self.pathology_diagnoses],
            "surgeries": [
                {k: (v.isoformat(sep=" ") if isinstance(v, datetime) else v) for k, v in item.__dict__.items()}
                for item in self.surgeries
            ],
            "cost": dict(self.cost) if self.cost is not None else None,
        }
