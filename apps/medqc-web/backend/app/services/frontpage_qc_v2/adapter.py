"""首页质控 V2：原始行 → FrontpageDoc。"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

from .document import DiagnosisItem, FrontpageDoc, SimpleDiagnosis, SurgeryItem
from .loader import RawFrontpage, is_discharge_diagnosis_type
from .values import parse_datetime, text_of


def _texts(row: Dict[str, Any]) -> Dict[str, str]:
    return {str(key): text_of(value) for key, value in row.items()}


def _sequence(value: object) -> int:
    """取序号：'1234567||3' → 3，'3' → 3，无法解析排最后。"""
    tail = text_of(value).rsplit("||", 1)[-1]
    return int(tail) if re.fullmatch(r"\d{1,6}", tail) else 999_999


def _is_main_diagnosis(row: Dict[str, str]) -> bool:
    return row.get("diagnosis_main") == "是" or "主要" in row.get("diagnosis_type", "")


def _diagnosis_sort_key(row: Dict[str, str]) -> Tuple[int, str]:
    return (_sequence(row.get("diagnosis_no")), row.get("diagnosis_id", ""))


def _surgery_sort_key(row: Dict[str, str]) -> Tuple[int, int, datetime, str]:
    begin = parse_datetime(row.get("surgery_begin_datetime")) or datetime.max
    return (
        0 if row.get("main_surgery_sign") == "是" else 1,
        _sequence(row.get("surgery_id")),
        begin,
        row.get("surgery_id", ""),
    )


def build_frontpage_doc(raw: RawFrontpage) -> FrontpageDoc:
    basic = _texts(raw.mr)
    rows = [_texts(row) for row in raw.diagnosis_rows]

    discharge_rows = sorted(
        (row for row in rows if is_discharge_diagnosis_type(row.get("diagnosis_type"))),
        key=_diagnosis_sort_key,
    )
    discharge: List[DiagnosisItem] = []
    for row in discharge_rows:
        name = row.get("diagnosis_name", "")
        code = row.get("diagnosis_code", "")
        if not name and not code:
            continue
        discharge.append(
            DiagnosisItem(
                index=len(discharge),
                name=name,
                code=code,
                raw_admission_condition=row.get("admission_condition", ""),
                raw_discharge_condition=row.get("discharge_condition", ""),
                is_main=_is_main_diagnosis(row),
                source=raw.diagnosis_source,
            )
        )

    def simple(keyword: str) -> List[SimpleDiagnosis]:
        selected = sorted(
            (
                row
                for row in rows
                if keyword in row.get("diagnosis_type", "") and not is_discharge_diagnosis_type(row.get("diagnosis_type"))
            ),
            key=_diagnosis_sort_key,
        )
        return [
            SimpleDiagnosis(
                name=row.get("diagnosis_name", ""),
                code=row.get("diagnosis_code", ""),
                pathology_no=row.get("pathology_id", ""),
            )
            for row in selected
            if row.get("diagnosis_name") or row.get("diagnosis_code")
        ]

    surgeries: List[SurgeryItem] = []
    for row in sorted((_texts(r) for r in raw.surgery_rows), key=_surgery_sort_key):
        if not row.get("surgery_name") and not row.get("surgery_code"):
            continue
        surgeries.append(
            SurgeryItem(
                index=len(surgeries),
                name=row.get("surgery_name", ""),
                code=row.get("surgery_code", ""),
                begin_at_raw=row.get("surgery_begin_datetime", ""),
                begin_at=parse_datetime(row.get("surgery_begin_datetime")),
                surgeon=row.get("surgeon", ""),
                first_assistant=row.get("first_assistant", ""),
                second_assistant=row.get("second_assistant", ""),
                anesthesia_method=row.get("anesthesia_method", ""),
                anesthesiologist=row.get("anesthesiologist", ""),
                raw_level=row.get("surgical_level", ""),
                raw_incision=row.get("surgial_incision_level", ""),
                raw_healing=row.get("surgical_incisionheal_level", ""),
            )
        )

    return FrontpageDoc(
        institute_id=raw.ref.institute_id,
        patient_id=raw.ref.patient_id,
        visit_id=raw.ref.visit_id,
        basic=basic,
        discharge_diagnoses=discharge,
        outpatient_diagnoses=simple("门"),
        pathology_diagnoses=simple("病理"),
        surgeries=surgeries,
        cost=_texts(raw.cost_row) if raw.cost_row is not None else None,
        admission_at=parse_datetime(basic.get("admission_datetime")),
        discharge_at=parse_datetime(basic.get("discharge_datetime")),
        notes=list(raw.notes),
    )
