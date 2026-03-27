"""medical_records 域共享常量与工具。"""

from __future__ import annotations

from typing import Any, Optional


DOC_TYPES: list[tuple[str, str]] = [
    ("admission_record", "入院记录"),
    ("first_course_record", "首次病程记录"),
    ("daily_course_record", "日常病程记录"),
    ("senior_course_record", "上级医师查房记录"),
    ("consultation_record", "会诊记录"),
    ("surgery_record", "手术记录"),
    ("postsurg_firstcourse_record", "术后首次病程记录"),
    ("rescue_record", "抢救记录"),
    ("transfer_in_record", "转入记录"),
    ("transfer_out_record", "转出记录"),
    ("nursing_record", "护理记录"),
    ("discharge_record", "出院记录"),
]


def build_demo_workstation_records() -> list[dict]:
    """演示病历数据（独立于 mr 正式表）。"""
    return [
        {
            "id": "V-ZS-001",
            "visitId": "V-ZS-001",
            "instituteId": "DEMO",
            "patientId": "P-ZS-001",
            "bedNo": "",
            "name": "张三",
            "sex": "男",
            "age": 58,
            "insurance": "演示数据",
            "department": "心内科",
            "admissionDate": "01-05",
            "dischargeDate": "01-17",
            "days": 12,
            "doctor": "",
            "status": "pending",
            "cdmFrontpageEmpty": True,
            "isDemoRecord": True,
        },
        {
            "id": "V-LM-001",
            "visitId": "V-LM-001",
            "instituteId": "DEMO",
            "patientId": "P-LM-001",
            "bedNo": "",
            "name": "李明",
            "sex": "男",
            "age": 35,
            "insurance": "演示数据",
            "department": "外二科（肛肠外科）",
            "admissionDate": "03-29",
            "dischargeDate": "03-29",
            "days": 0,
            "doctor": "",
            "status": "pending",
            "cdmFrontpageEmpty": True,
            "isDemoRecord": True,
        },
    ]


def filter_demo_records(
    records: list[dict],
    dept: Optional[str],
    keyword: Optional[str],
) -> list[dict]:
    out = records
    if dept:
        out = [item for item in out if (item.get("department") or "") == dept]
    if keyword:
        kw = keyword.strip().lower()
        out = [
            item for item in out
            if kw in str(item.get("name") or "").lower()
            or kw in str(item.get("id") or "").lower()
        ]
    return out


def normalize_content(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def build_concat_text(documents: list[dict]) -> str:
    sections = []
    for doc in documents:
        if doc.get("has_content") and doc.get("content"):
            sep = "=" * 40
            sections.append(f"{sep}\n📋 {doc['label']}\n{sep}\n\n{doc['content']}")
    return "\n\n\n".join(sections)

