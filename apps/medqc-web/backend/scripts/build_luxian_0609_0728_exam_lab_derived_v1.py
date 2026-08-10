"""为 0728 样本池的两份真实病历生成可追溯的受控资料补件副本。

这是一次性、受控的验证资料构建器：不修改源病例；每份副本使用新三坐标，
并把原始三坐标、补件清单和 recipe 版本写入样本池 raw_payload。它不试图
解决其他真实缺失资料；本轮补齐检查检验、输血、收费、会诊及交接班受控资料。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping

from sqlalchemy import MetaData, Table, and_, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import engine  # noqa: E402
from app.services.bundles.assembly import (  # noqa: E402
    refresh_domain_bundles_for_rows,
    refresh_scene_bundles_for_rows,
)
from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService  # noqa: E402


RECIPE_VERSION = "lx0609-0728-controlled-supplement-v3"
POOL_ID = "aacc704a-ef30-47bf-a74c-86fc91d29273"
TARGET_INSTITUTE_ID = "LX0609_0728_DERIVED_V1"
RULE_IDS = [
    "LX0609-010", "LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015",
    "LX0609-043", "LX0609-049", "LX0609-069", "LX0609-070", "LX0609-071",
]
OUTPUT_PATH = ROOT / "tmp-0728-controlled-supplement-v3-manifest.json"
_CT_MRI_ORDER_PATTERN = re.compile(
    r"(?:^|[^A-Z])CT(?:$|[^A-Z])|(?:^|[^A-Z])MRI(?:$|[^A-Z])|磁共振|核磁",
    flags=re.IGNORECASE,
)
_CANCELLED_ORDER_PATTERN = re.compile(r"撤销|作废|取消")
_CT_MRI_MASTER_FIELDS = (
    "exam_type",
    "modality",
    "exam_name",
    "item_name",
    "exam_item_name",
    "performed_dept",
    "exam_result",
    "exam_impression",
    "exam_conclusion",
    "record_content",
)


@dataclass(frozen=True)
class SourceCase:
    source_item_id: str
    source_institute_id: str
    source_patient_id: str
    source_visit_id: str
    source_mr_no: str
    source_patient_name: str
    target_index: int
    target_patient_id: str
    target_visit_id: str
    target_mr_no: str
    target_patient_name: str
    target_item_id: str


CASES = (
    SourceCase(
        source_item_id="fdbd06cb-226f-48b5-b92a-18d69ca95968",
        source_institute_id="泸县人民医院",
        source_patient_id="0000225510",
        source_visit_id="2496813",
        source_mr_no="208790",
        source_patient_name="冯丽平",
        target_index=1,
        target_patient_id="LX0609_DERIVED_208790_V1",
        target_visit_id="LX0609_DERIVED_208790_V1",
        target_mr_no="208790-合成检验v1",
        target_patient_name="冯丽平（合成检查检验）",
        target_item_id="0728-derived-exam-lab-208790-v1",
    ),
    SourceCase(
        source_item_id="0728-2465281",
        source_institute_id="泸县人民医院",
        source_patient_id="0000525453",
        source_visit_id="2465281",
        source_mr_no="359787",
        source_patient_name="李孝西",
        target_index=2,
        target_patient_id="LX0609_DERIVED_359787_V1",
        target_visit_id="LX0609_DERIVED_359787_V1",
        target_mr_no="359787-合成检验v1",
        target_patient_name="李孝西（合成检查检验）",
        target_item_id="0728-derived-exam-lab-359787-v1",
    ),
)


def _load_v2_module() -> ModuleType:
    path = Path(__file__).with_name("build_luxian_0609_0426_synthetic_v2.py")
    spec = importlib.util.spec_from_file_location("lx0609_v2_clone_helper_for_0728", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载既有脱敏克隆工具")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V2 = _load_v2_module()


def _configure_clone_identity() -> None:
    V2.TARGET_INSTITUTE_ID = TARGET_INSTITUTE_ID


def _candidate(case: SourceCase) -> Any:
    return V2.CandidateCase(
        target_index=case.target_index,
        family="检查检验",
        selected_rule_ids=list(RULE_IDS),
        source_item={
            "id": case.source_item_id,
            "matched_institute_id": case.source_institute_id,
            "matched_patient_id": case.source_patient_id,
            "matched_visit_id": case.source_visit_id,
            "mr_no": case.source_mr_no,
            "patient_name": case.source_patient_name,
            "department": "重症医学科（ICU）",
        },
        source_reason="真实病例派生：补齐检查检验结构化报告及核对病程",
        source_status="derived_for_exam_lab_validation",
        target_visit_id=case.target_visit_id,
        target_patient_id=case.target_patient_id,
        target_mr_no=case.target_mr_no,
        target_patient_name=case.target_patient_name,
    )


def _reflect(table_name: str, metadata: MetaData) -> Table | None:
    return V2.reflect_table(table_name, metadata)


def _source_rows(*, case: SourceCase, table: Table, session: Session) -> list[dict[str, Any]]:
    if "visit_id" not in table.c:
        return []
    clauses = [table.c.visit_id == case.source_visit_id]
    if "institute_id" in table.c:
        clauses.append(table.c.institute_id == case.source_institute_id)
    if "patient_id" in table.c:
        clauses.append(table.c.patient_id == case.source_patient_id)
    return [dict(row) for row in session.execute(select(table).where(and_(*clauses))).mappings().all()]


def _first_datetime(rows: Iterable[dict[str, Any]], *field_names: str) -> datetime | None:
    for row in rows:
        for field_name in field_names:
            value = row.get(field_name)
            if isinstance(value, datetime):
                return value
    return None


def _case_times(rows_by_table: dict[str, list[dict[str, Any]]], case: SourceCase) -> tuple[datetime, datetime]:
    registration_rows = [row for row in rows_by_table.get("inpat_registration", []) if row.get("visit_id") == case.target_visit_id]
    mr_rows = [row for row in rows_by_table.get("mr", []) if row.get("visit_id") == case.target_visit_id]
    admission = _first_datetime(registration_rows, "admission_datetime") or _first_datetime(mr_rows, "admission_datetime")
    discharge = _first_datetime(registration_rows, "discharge_datetime") or _first_datetime(mr_rows, "discharge_datetime")
    if admission is None or discharge is None or discharge <= admission:
        raise ValueError(f"{case.source_mr_no} 缺少一致的入/出院时间，不能生成 final 合成副本")
    return admission, discharge


def _base(case: SourceCase, at: datetime) -> dict[str, Any]:
    return {
        "institute_id": TARGET_INSTITUTE_ID,
        "patient_id": case.target_patient_id,
        "visit_id": case.target_visit_id,
        "visit_type": "I",
        "inpat_no": case.target_mr_no,
        "mr_no": case.target_mr_no,
        "name": case.target_patient_name,
        "sex": "女" if case.source_mr_no == "208790" else "男",
        "age_year": "60",
        "age": "60",
        "last_modifier": "合成验证医师",
        "last_modifier_id": "SYNTHETIC",
        "last_modified_datetime": at,
        "update_time": at,
    }


def _append(rows_by_table: dict[str, list[dict[str, Any]]], table_name: str, row: dict[str, Any]) -> None:
    rows_by_table.setdefault(table_name, []).append(row)


def _target_ct_mri_orders(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: SourceCase,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows_by_table.get("inpat_nondrug_order", [])
        if row.get("institute_id") == TARGET_INSTITUTE_ID
        and row.get("patient_id") == case.target_patient_id
        and row.get("visit_id") == case.target_visit_id
        and not _CANCELLED_ORDER_PATTERN.search(str(row.get("order_status") or ""))
        and _CT_MRI_ORDER_PATTERN.search(str(row.get("order_name") or ""))
    ]


def _complete_ct_mri_associations(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: SourceCase,
) -> None:
    """为派生病例的每条有效 CT/MRI 医嘱补齐稳定的一对主记录和报告。"""

    admission, discharge = _case_times(rows_by_table, case)
    masters = [
        row
        for row in rows_by_table.get("exam_master", [])
        if row.get("institute_id") == TARGET_INSTITUTE_ID
        and row.get("patient_id") == case.target_patient_id
        and row.get("visit_id") == case.target_visit_id
    ]
    reports = [
        row
        for row in rows_by_table.get("exam_item_report", [])
        if row.get("institute_id") == TARGET_INSTITUTE_ID
        and row.get("patient_id") == case.target_patient_id
        and row.get("visit_id") == case.target_visit_id
    ]
    course_rows = [
        row
        for row in rows_by_table.get("daily_course_record", [])
        if row.get("institute_id") == TARGET_INSTITUTE_ID
        and row.get("patient_id") == case.target_patient_id
        and row.get("visit_id") == case.target_visit_id
    ]

    for order in _target_ct_mri_orders(rows_by_table, case):
        order_id = str(order.get("order_id") or "").strip()
        order_name = str(order.get("order_name") or "CT/MRI检查").strip()
        order_time = order.get("prescribed_datetime") or order.get("order_time") or order.get("start_time")
        if not order_id or not isinstance(order_time, datetime):
            raise ValueError(f"{case.source_mr_no} 的有效 CT/MRI 医嘱缺少稳定医嘱号或开立时间")

        linked_masters = [row for row in masters if str(row.get("order_id") or "").strip() == order_id]
        if len(linked_masters) > 1:
            raise ValueError(f"{case.source_mr_no} 的 CT/MRI 医嘱存在重复检查主记录")
        if linked_masters:
            exam = linked_masters[0]
            exam_id = str(exam.get("exam_id") or "").strip()
        else:
            exam_time = order_time + timedelta(hours=1)
            report_time = order_time + timedelta(hours=2)
            if not (admission <= order_time < exam_time < report_time <= discharge):
                raise ValueError(f"{case.source_mr_no} 的 CT/MRI 医嘱无法在本次住院窗内形成受控闭环")
            exam_id = f"{order_id}-exam"
            exam_type = "MRI" if re.search(r"MRI|磁共振|核磁", order_name, flags=re.IGNORECASE) else "CT"
            exam = {
                **_base(case, report_time),
                "exam_id": exam_id,
                "order_id": order_id,
                "exam_type": exam_type,
                "exam_reason": "按原医嘱完成受控检查关联补件",
                "request_dept": str(order.get("dept_name") or "重症医学科（ICU）"),
                "request_physician": str(order.get("prescribed_doctor") or "合成验证医师"),
                "request_time": order_time,
                "exam_time": exam_time,
                "report_time": report_time,
                "exam_result_status": "Final",
                "record_content": f"{order_name}检查主记录（受控关联补件）。",
                "record_time": report_time,
            }
            _append(rows_by_table, "exam_master", exam)
            masters.append(exam)

        if not exam_id:
            raise ValueError(f"{case.source_mr_no} 的 CT/MRI 检查主记录缺少稳定检查号")
        linked_reports = [row for row in reports if str(row.get("exam_id") or "").strip() == exam_id]
        if len(linked_reports) > 1:
            raise ValueError(f"{case.source_mr_no} 的 CT/MRI 检查存在重复报告")
        report_time = exam.get("report_time") or exam.get("report_datetime")
        if not isinstance(report_time, datetime):
            raise ValueError(f"{case.source_mr_no} 的 CT/MRI 检查主记录缺少报告时间")
        if not linked_reports:
            report = {
                **_base(case, report_time),
                "document_id": f"{exam_id}-report",
                "document_title": f"{order_name}检查报告（受控关联补件）",
                "document_status": "Submitted",
                "submitter": "影像科报告医师",
                "submitter_id": "SYNTHETIC-RAD",
                "submit_datetime": report_time,
                "record_time": report_time,
                "exam_no": exam_id,
                "exam_id": exam_id,
                "item_no": "1",
                "item_id": f"{exam_id}-item-001",
                "item_code": str(exam.get("exam_type") or "CT-MRI"),
                "item_name": order_name,
                "exam_name": order_name,
                "exam_item_name": order_name,
                "exam_type": str(exam.get("exam_type") or "CT/MRI"),
                "exam_findings": "受控补件：未见明确急性异常。",
                "exam_impression": "受控补件：未见明确急性异常。",
                "exam_conclusion": "受控补件：未见明确急性异常。",
                "record_content": f"{order_name}报告已完成，未见明确急性异常。",
                "report_time": report_time,
            }
            _append(rows_by_table, "exam_item_report", report)
            reports.append(report)

        linked_course = [row for row in course_rows if str(row.get("order_id") or "").strip() == order_id]
        if not linked_course:
            before_time = order_time - timedelta(minutes=30)
            after_time = report_time + timedelta(hours=1)
            if not (admission <= before_time <= order_time <= report_time <= after_time <= discharge):
                raise ValueError(f"{case.source_mr_no} 的 CT/MRI 医嘱无法在本次住院窗内补齐病程关联")
            for phase, record_time, content in (
                ("before", before_time, f"根据当前病情，拟行{order_name}以进一步明确病因。"),
                ("after", after_time, f"已阅{order_name}报告，未见明确急性异常，继续结合病情观察。"),
            ):
                course = {
                    **_base(case, record_time),
                    "document_id": f"{order_id}-course-{phase}",
                    "document_title": "日常病程记录（受控检查关联补件）",
                    "document_status": "Submitted",
                    "submitter": "合成验证医师",
                    "submitter_id": "SYNTHETIC",
                    "submit_datetime": record_time,
                    "record_time": record_time,
                    "order_id": order_id,
                    "record_content": content,
                }
                _append(rows_by_table, "daily_course_record", course)
                course_rows.append(course)


def _validate_ct_mri_associations(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: SourceCase,
) -> None:
    orders = _target_ct_mri_orders(rows_by_table, case)
    order_ids = [str(row.get("order_id") or "").strip() for row in orders]
    if not order_ids or any(not order_id for order_id in order_ids) or len(order_ids) != len(set(order_ids)):
        raise ValueError(f"{case.source_mr_no} 的有效 CT/MRI 医嘱自然键缺失或重复")
    order_id_set = set(order_ids)

    masters = [
        row
        for row in rows_by_table.get("exam_master", [])
        if row.get("institute_id") == TARGET_INSTITUTE_ID
        and row.get("patient_id") == case.target_patient_id
        and row.get("visit_id") == case.target_visit_id
        and any(
            _CT_MRI_ORDER_PATTERN.search(str(row.get(field) or ""))
            for field in _CT_MRI_MASTER_FIELDS
        )
    ]
    master_keys = [
        (str(row.get("order_id") or "").strip(), str(row.get("exam_id") or "").strip())
        for row in masters
    ]
    if any(not order_id or not exam_id for order_id, exam_id in master_keys):
        raise ValueError(f"{case.source_mr_no} 的 CT/MRI 检查主记录自然键缺失")
    if len(master_keys) != len(set(master_keys)):
        raise ValueError(f"{case.source_mr_no} 的 CT/MRI 检查主记录自然键重复")
    master_order_ids = [order_id for order_id, _exam_id in master_keys]
    if set(master_order_ids) != order_id_set or len(master_order_ids) != len(order_ids):
        raise ValueError(f"{case.source_mr_no} 的 CT/MRI 医嘱与检查主记录未形成一一对应")

    exam_ids = [exam_id for _order_id, exam_id in master_keys]
    if len(exam_ids) != len(set(exam_ids)):
        raise ValueError(f"{case.source_mr_no} 的 CT/MRI 检查号重复")
    exam_id_set = set(exam_ids)
    reports = [
        row
        for row in rows_by_table.get("exam_item_report", [])
        if row.get("institute_id") == TARGET_INSTITUTE_ID
        and row.get("patient_id") == case.target_patient_id
        and row.get("visit_id") == case.target_visit_id
        and str(row.get("exam_id") or "").strip() in exam_id_set
    ]
    report_exam_ids = [str(row.get("exam_id") or "").strip() for row in reports]
    report_keys = [
        (
            str(row.get("exam_id") or "").strip(),
            str(row.get("item_id") or row.get("document_id") or "").strip(),
        )
        for row in reports
    ]
    if any(not exam_id or not item_id for exam_id, item_id in report_keys) or len(report_keys) != len(set(report_keys)):
        raise ValueError(f"{case.source_mr_no} 的 CT/MRI 报告自然键缺失或重复")
    if set(report_exam_ids) != exam_id_set or len(report_exam_ids) != len(exam_ids):
        raise ValueError(f"{case.source_mr_no} 的 CT/MRI 检查主记录与报告未形成一一对应")


def _normalize_discharge_diagnosis_contract(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: SourceCase,
) -> None:
    """将派生病例的出院诊断整理为唯一、可重复构建的双来源序列。"""

    def is_target(row: Mapping[str, Any]) -> bool:
        return (
            row.get("institute_id") == TARGET_INSTITUTE_ID
            and row.get("patient_id") == case.target_patient_id
            and row.get("visit_id") == case.target_visit_id
        )

    source_rows = [
        row
        for row in rows_by_table.get("discharge_record_diagnosis", [])
        if is_target(row) and str(row.get("diagnosis_name") or "").strip()
    ]
    if not source_rows:
        return

    discharge_time = _case_times(rows_by_table, case)[1]
    discharge_document_id = next(
        (
            str(row.get("document_id") or "").strip()
            for row in rows_by_table.get("discharge_record", [])
            if is_target(row) and str(row.get("document_id") or "").strip()
        ),
        f"{case.target_visit_id}-discharge-record",
    )
    unique_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in source_rows:
        name = str(row.get("diagnosis_name") or "").strip()
        code = str(row.get("diagnosis_code") or "").strip()
        key = (name, code)
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(dict(row))

    normalized_discharge: list[dict[str, Any]] = []
    normalized_authoritative: list[dict[str, Any]] = []
    for index, source in enumerate(unique_rows, start=1):
        diagnosis_id = f"{case.target_visit_id}-discharge-diagnosis-{index:03d}"
        common = {
            "diagnosis_id": diagnosis_id,
            "diagnosis_main": "1" if index == 1 else "0",
            "diagnosis_no": index,
            "diagnosis_name": str(source.get("diagnosis_name") or "").strip(),
            "diagnosis_code": str(source.get("diagnosis_code") or "").strip(),
            "diagnosis_type": "出院诊断",
            "diagnosis_source": "controlled_discharge_diagnosis_contract",
            "document_id": discharge_document_id,
        }
        normalized_discharge.append({
            **source,
            **common,
            "diagnosis_time": source.get("diagnosis_time") or discharge_time,
            "record_time": source.get("record_time") or discharge_time,
        })
        normalized_authoritative.append({
            **_base(case, discharge_time),
            **common,
            "diagnosis_datetime": discharge_time,
            "diagnosis_updatetime": discharge_time,
        })

    rows_by_table["discharge_record_diagnosis"] = [
        row
        for row in rows_by_table.get("discharge_record_diagnosis", [])
        if not is_target(row)
    ] + normalized_discharge
    rows_by_table["diagnosis"] = [
        row for row in rows_by_table.get("diagnosis", []) if not is_target(row)
    ] + normalized_authoritative


def _validate_discharge_diagnosis_contract(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: SourceCase,
) -> None:
    def target_rows(table_name: str) -> list[dict[str, Any]]:
        return [
            row
            for row in rows_by_table.get(table_name, [])
            if row.get("institute_id") == TARGET_INSTITUTE_ID
            and row.get("patient_id") == case.target_patient_id
            and row.get("visit_id") == case.target_visit_id
        ]

    written = target_rows("discharge_record_diagnosis")
    if not written:
        return
    authoritative = target_rows("diagnosis")

    def sequence(rows: list[dict[str, Any]]) -> list[tuple[int, str]]:
        return sorted(
            (
                int(row.get("diagnosis_no") or 0),
                str(row.get("diagnosis_name") or "").strip(),
            )
            for row in rows
        )

    ids = [str(row.get("diagnosis_id") or "").strip() for row in authoritative]
    if (
        not authoritative
        or any(not diagnosis_id for diagnosis_id in ids)
        or len(ids) != len(set(ids))
        or sequence(authoritative) != sequence(written)
    ):
        raise ValueError(f"{case.source_mr_no} 的权威诊断与出院记录诊断序列不一致")


def _append_exam_lab_supplements(rows_by_table: dict[str, list[dict[str, Any]]], case: SourceCase) -> list[dict[str, Any]]:
    admission, discharge = _case_times(rows_by_table, case)
    exam_request = admission + timedelta(days=1, hours=2)
    exam_time = admission + timedelta(days=1, hours=3)
    exam_report = admission + timedelta(days=1, hours=4)
    exam_course_before = admission + timedelta(days=1, hours=1, minutes=30)
    exam_course_after = admission + timedelta(days=1, hours=8)
    lab_request = admission + timedelta(days=2, hours=2)
    lab_report = admission + timedelta(days=2, hours=10)
    lab_course_after = admission + timedelta(days=2, hours=14)
    if lab_course_after >= discharge:
        raise ValueError(f"{case.source_mr_no} 出院时间过早，无法放置受控检查检验补件")

    exam_id = f"{case.target_visit_id}-exam-mri-001"
    lab_id = f"{case.target_visit_id}-lab-culture-001"
    base_exam = _base(case, exam_report)
    base_lab = _base(case, lab_report)
    _append(rows_by_table, "exam_master", {
        **base_exam,
        "exam_id": exam_id,
        "order_id": f"{case.target_visit_id}-exam-order-001",
        "exam_type": "MRI",
        "exam_reason": "腰痛伴右下肢麻木，明确神经根受压情况",
        "request_dept": "重症医学科（ICU）",
        "request_physician": "合成验证医师",
        "request_time": exam_request,
        "exam_time": exam_time,
        "report_time": exam_report,
        "exam_result_status": "Final",
        "record_content": "补齐的腰椎MRI检查主记录，用于验证检查前病程、报告记录及阳性结果分析规则。",
        "record_time": exam_report,
    })
    _append(rows_by_table, "inpat_nondrug_order", {
        **_base(case, exam_request),
        "order_id": f"{case.target_visit_id}-exam-order-001",
        "application_id": exam_id,
        "dept_name": "重症医学科（ICU）",
        "order_type": "临时医嘱",
        "order_name": "腰椎MRI平扫",
        "quantity": "1",
        "quantity_unit": "次",
        "prescribed_datetime": exam_request,
        "prescribed_doctor": "合成验证医师",
        "order_status": "已执行",
        "record_content": "因腰痛伴右下肢麻木，为明确神经根受压情况，拟行腰椎MRI检查。",
    })
    _append(rows_by_table, "exam_item_report", {
        **base_exam,
        "document_id": f"{case.target_visit_id}-exam-item-report-001",
        "document_title": "腰椎MRI检查报告（合成补件）",
        "document_status": "Submitted",
        "submitter": "影像科报告医师",
        "submitter_id": "SYNTHETIC-RAD",
        "submit_datetime": exam_report,
        "record_time": exam_report,
        "exam_no": exam_id,
        "exam_id": exam_id,
        "item_no": "1",
        "item_id": f"{exam_id}-item-001",
        "item_code": "MRI-LSPINE",
        "item_name": "腰椎MRI平扫",
        "exam_name": "腰椎MRI检查",
        "exam_item_name": "腰椎MRI平扫",
        "exam_type": "MRI",
        "exam_findings": "L4/5椎间盘向右后方突出，硬膜囊受压，右侧神经根受压。",
        "exam_impression": "阳性：L4/5椎间盘突出并右侧神经根受压。",
        "exam_conclusion": "阳性：L4/5椎间盘突出并右侧神经根受压。",
        "record_content": "检查结论明确记载：阳性，L4/5椎间盘突出并右侧神经根受压。",
        "report_time": exam_report,
    })
    _append(rows_by_table, "labtest_master", {
        **base_lab,
        "test_id": lab_id,
        "order_id": f"{case.target_visit_id}-lab-order-001",
        "labtest_subject": "尿培养+药敏",
        "labtest_cause": "发热，排查尿路感染",
        "specimen": "中段尿",
        "request_dept": "重症医学科（ICU）",
        "request_physician": "合成验证医师",
        "request_datetime": lab_request,
        "report_datetime": lab_report,
        "labtest_result_status": "Final",
        "record_content": "补齐的尿培养主记录，用于验证培养结果记录及阳性菌分析规则。",
    })
    _append(rows_by_table, "labtest_item_report", {
        **base_lab,
        "document_id": f"{case.target_visit_id}-lab-item-report-001",
        "document_title": "尿培养及药敏报告（合成补件）",
        "document_status": "Submitted",
        "submitter": "检验科报告医师",
        "submitter_id": "SYNTHETIC-LAB",
        "submit_datetime": lab_report,
        "record_time": lab_report,
        "test_no": lab_id,
        "test_id": lab_id,
        "item_no": "1",
        "item_id": f"{lab_id}-item-001",
        "item_code": "URINE-CULTURE",
        "item_name": "尿培养+药敏",
        "item_abbreviation": "尿培养",
        "result": "大肠埃希菌阳性；对头孢曲松敏感，对左氧氟沙星耐药。",
        "reference_range": "阴性",
        "abnormal_indicator": "阳性",
        "record_content": "尿培养结果：大肠埃希菌阳性；药敏提示头孢曲松敏感、左氧氟沙星耐药。",
        "report_time": lab_report,
    })
    _append(rows_by_table, "daily_course_record", {
        **_base(case, exam_course_before),
        "document_id": f"{case.target_visit_id}-course-exam-before-001",
        "document_title": "日常病程记录（检查前）",
        "document_status": "Submitted",
        "submitter": "合成验证医师",
        "submitter_id": "SYNTHETIC",
        "submit_datetime": exam_course_before,
        "record_time": exam_course_before,
        "order_id": f"{case.target_visit_id}-exam-order-001",
        "record_content": "患者腰痛伴右下肢麻木持续，拟行腰椎MRI检查以明确神经根受压情况，已向患者说明检查目的。",
    })
    _append(rows_by_table, "daily_course_record", {
        **_base(case, exam_course_after),
        "document_id": f"{case.target_visit_id}-course-exam-after-001",
        "document_title": "日常病程记录（影像结果记录）",
        "document_status": "Submitted",
        "submitter": "合成验证医师",
        "submitter_id": "SYNTHETIC",
        "submit_datetime": exam_course_after,
        "record_time": exam_course_after,
        "order_id": f"{case.target_visit_id}-exam-order-001",
        "record_content": "已阅腰椎MRI报告，记录提示L4/5椎间盘突出并右侧神经根受压。",
    })
    _append(rows_by_table, "daily_course_record", {
        **_base(case, lab_course_after),
        "document_id": f"{case.target_visit_id}-course-lab-after-001",
        "document_title": "日常病程记录（培养结果记录）",
        "document_status": "Submitted",
        "submitter": "合成验证医师",
        "submitter_id": "SYNTHETIC",
        "submit_datetime": lab_course_after,
        "record_time": lab_course_after,
        "record_content": "已阅细菌培养（尿培养）报告，记录大肠埃希菌阳性及药敏结果，待结合病情继续观察。",
    })
    return [
        {"table": "exam_master", "reason": "controlled_positive_mri"},
        {"table": "exam_item_report", "reason": "controlled_explicit_positive_mri"},
        {"table": "labtest_master", "reason": "controlled_urine_culture"},
        {"table": "labtest_item_report", "reason": "controlled_positive_culture"},
        {"table": "daily_course_record", "reason": "controlled_exam_lab_course_records"},
    ]


def _append_transfusion_supplements(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: SourceCase,
) -> list[dict[str, Any]]:
    """补一笔受控单次输血及其九项、医嘱和收费资料，不覆盖来源病例原始行。"""

    admission, discharge = _case_times(rows_by_table, case)
    transfusion_time = admission + timedelta(days=2, hours=5)
    test_report_time = transfusion_time - timedelta(hours=2)
    application_time = transfusion_time - timedelta(hours=3)
    order_time = transfusion_time - timedelta(minutes=30)
    billing_time = transfusion_time + timedelta(minutes=30)
    if not (admission <= application_time < test_report_time < transfusion_time < billing_time <= discharge):
        raise ValueError(f"{case.source_mr_no} 住院时间窗不足，无法补齐受控输血资料")

    prefix = f"{case.target_visit_id}-transfusion-controlled-001"
    bloodtrans_id = f"{prefix}-event"
    order_id = f"{prefix}-order"
    application_id = f"{prefix}-application"
    test_id = f"{prefix}-pretest"
    component = "去白细胞悬浮红细胞"
    _append(rows_by_table, "mr_bloodtrans", {
        **_base(case, transfusion_time),
        "document_id": f"{prefix}-record",
        "bloodtrans_id": bloodtrans_id,
        "transfuse_variety": component,
        "blood_transfusion_volume": "2",
        "blood_transfusion_unit": "U",
        "transfution_datetime": transfusion_time,
        "transfusion_reason": "受控验证：纠正贫血",
    })
    _append(rows_by_table, "blood_application", {
        **_base(case, application_time),
        "application_id": application_id,
        "dept_name": "重症医学科（ICU）",
        "patient_bloodtype_abo": "O",
        "patient_bloodtype_rhd": "阳性(+)",
        "transfuse_variety": component,
        "transfuse_volume": "2",
        "transfuse_volume_unit": "U",
        "request_datetime": application_time,
        "physician_name": "合成验证医师",
        "record_content": "受控验证输血申请：纠正贫血，拟输注去白细胞悬浮红细胞2U。",
    })
    _append(rows_by_table, "inpat_nondrug_order", {
        **_base(case, order_time),
        "order_id": order_id,
        "application_id": application_id,
        "dept_name": "重症医学科（ICU）",
        "order_type": "临时医嘱",
        "order_name": f"输注{component}",
        "quantity": "2",
        "quantity_unit": "U",
        "prescribed_datetime": order_time,
        "prescribed_doctor": "合成验证医师",
        "order_status": "已执行",
        "record_content": "受控验证输血医嘱，与补充输血事件及收费使用同一医嘱编号。",
    })
    _append(rows_by_table, "inpat_bill_item", {
        **_base(case, billing_time),
        "bill_item_id": f"{prefix}-bill",
        "receipt_id": f"{prefix}-receipt",
        "order_id": order_id,
        "item_type": "治疗",
        "medical_catalog_code": "SYNTHETIC-RBC",
        "medical_catalog_name": component,
        "item_specification": "2U",
        "quantity": "2",
        "quantity_unit": "U",
        "unit_price": "200",
        "cost": "400",
        "charge": "400",
        "billing_datetime": billing_time,
        "order_dept_name": "重症医学科（ICU）",
        "executive_dept_name": "输血科",
        "record_content": "受控验证收费：与补充输血医嘱同一order_id，不用于推断真实病例收费。",
    })
    _append(rows_by_table, "labtest_master", {
        **_base(case, test_report_time),
        "test_id": test_id,
        "order_id": f"{prefix}-pretest-order",
        "labtest_subject": "输血前九项检查（合成补件）",
        "labtest_cause": "输血前感染性筛查",
        "specimen": "静脉血",
        "request_dept": "重症医学科（ICU）",
        "request_physician": "合成验证医师",
        "request_datetime": application_time,
        "report_datetime": test_report_time,
        "labtest_result_status": "Final",
        "record_content": "受控验证：输血前九项检查，报告时间早于受控输血时间。",
    })
    for item_no, (item_name, abbreviation, result) in enumerate((
        ("乙肝表面抗原", "HBsAg", "阴性"),
        ("乙肝表面抗体", "HBsAb", "阳性"),
        ("乙肝e抗原", "HBeAg", "阴性"),
        ("乙肝e抗体", "HBeAb", "阳性"),
        ("乙肝核心抗体", "HBcAb", "阳性"),
        ("丙肝抗体", "抗-HCV", "阴性"),
        ("艾滋病抗体", "HIV", "阴性"),
        ("梅毒螺旋体抗体", "TP", "阴性"),
        ("谷丙转氨酶", "ALT", "18 U/L"),
    ), start=1):
        _append(rows_by_table, "labtest_item_report", {
            **_base(case, test_report_time),
            "document_id": f"{prefix}-pretest-{item_no:02d}",
            "document_title": "输血前九项检验报告（合成补件）",
            "document_status": "Submitted",
            "submitter": "检验科报告医师",
            "submitter_id": "SYNTHETIC-LAB",
            "submit_datetime": test_report_time,
            "record_time": test_report_time,
            "test_no": test_id,
            "test_id": test_id,
            "item_no": str(item_no),
            "item_id": f"{test_id}-item-{item_no:02d}",
            "item_code": abbreviation,
            "item_name": item_name,
            "item_abbreviation": abbreviation,
            "result": result,
            "reference_range": "阴性",
            "record_content": f"输血前九项受控补件：{item_name} {result}。",
            "report_time": test_report_time,
        })
    return [
        {"table": "mr_bloodtrans", "reason": "controlled_single_transfusion_event"},
        {"table": "blood_application", "reason": "controlled_pretransfusion_application"},
        {"table": "labtest_master", "reason": "controlled_pretransfusion_nine_items"},
        {"table": "labtest_item_report", "reason": "controlled_pretransfusion_nine_items"},
        {"table": "inpat_nondrug_order", "reason": "controlled_transfusion_order"},
        {"table": "inpat_bill_item", "reason": "controlled_transfusion_billing"},
    ]


def _append_consultation_and_handover_supplements(
    rows_by_table: dict[str, list[dict[str, Any]]],
    case: SourceCase,
) -> list[dict[str, Any]]:
    """补一组单次会诊和一组经治医师变更/交接班，均使用现有主资料链。"""

    admission, discharge = _case_times(rows_by_table, case)
    consultation_request_time = admission + timedelta(days=1, hours=4)
    consultation_record_time = consultation_request_time + timedelta(hours=4)
    physician_change_time = admission + timedelta(days=3, hours=2)
    handoff_time = physician_change_time - timedelta(minutes=10)
    handover_time = physician_change_time + timedelta(hours=1)
    all_times = (
        consultation_request_time,
        consultation_record_time,
        handoff_time,
        physician_change_time,
        handover_time,
    )
    if not all(admission <= value <= discharge for value in all_times):
        raise ValueError(f"{case.source_mr_no} 住院时间窗不足，无法补齐会诊或交接班资料")

    consultation_prefix = f"{case.target_visit_id}-consultation-controlled-001"
    _append(rows_by_table, "consultation_record", {
        **_base(case, consultation_request_time),
        "document_id": f"{consultation_prefix}-application",
        "document_title": "会诊申请单（合成补件）",
        "document_status": "Submitted",
        "submitter": "合成验证医师",
        "submitter_id": "SYNTHETIC",
        "submit_datetime": consultation_request_time,
        "record_time": consultation_request_time,
        "record_content": "会诊目的：请相关专科协助评估并提出诊疗建议。",
    })
    _append(rows_by_table, "consultation_record", {
        **_base(case, consultation_record_time),
        "document_id": f"{consultation_prefix}-record",
        "document_title": "会诊记录单（合成补件）",
        "document_status": "Submitted",
        "submitter": "会诊医师",
        "submitter_id": "SYNTHETIC-CONSULT",
        "submit_datetime": consultation_record_time,
        "record_time": consultation_record_time,
        "record_content": "会诊意见：建议继续监测病情，结合检查结果调整治疗方案。",
    })

    handover_prefix = f"{case.target_visit_id}-physician-change-controlled-001"
    _append(rows_by_table, "inpat_nondrug_order", {
        **_base(case, physician_change_time),
        "order_id": f"{handover_prefix}-order",
        "dept_name": "重症医学科（ICU）",
        "order_type": "临时医嘱",
        "order_name": "经治医师变更",
        "quantity": "1",
        "quantity_unit": "次",
        "prescribed_datetime": physician_change_time,
        "prescribed_doctor": "合成验证医师",
        "order_status": "已执行",
        "record_content": "经治医师由合成甲医师变更为合成乙医师，已按要求交接班。",
    })
    _append(rows_by_table, "handoff_record", {
        **_base(case, handoff_time),
        "document_id": f"{handover_prefix}-handoff",
        "document_title": "交班记录（合成补件）",
        "document_status": "Submitted",
        "submitter": "合成甲医师",
        "submitter_id": "SYNTHETIC-A",
        "submit_datetime": handoff_time,
        "record_time": handoff_time,
        "record_content": "交班医师：合成甲医师；接班医师：合成乙医师。已交接当前病情、治疗计划及风险事项。",
    })
    _append(rows_by_table, "handover_record", {
        **_base(case, handover_time),
        "document_id": f"{handover_prefix}-handover",
        "document_title": "接班记录（合成补件）",
        "document_status": "Submitted",
        "submitter": "合成乙医师",
        "submitter_id": "SYNTHETIC-B",
        "submit_datetime": handover_time,
        "record_time": handover_time,
        "record_content": "接班医师：合成乙医师。已完成接班，确认病情、治疗计划及重点风险。",
    })
    return [
        {"table": "consultation_record", "reason": "controlled_consultation_timeliness_pair"},
        {"table": "inpat_nondrug_order", "reason": "controlled_physician_change_event"},
        {"table": "handoff_record", "reason": "controlled_physician_handoff"},
        {"table": "handover_record", "reason": "controlled_physician_handover"},
    ]


def _ensure_authoritative_registration(rows_by_table: dict[str, list[dict[str, Any]]], case: SourceCase) -> None:
    """派生 final 病例固定一条本次住院的登记时间，避免 Provider 回退到 mr。"""
    if any(row.get("visit_id") == case.target_visit_id for row in rows_by_table.get("inpat_registration", [])):
        return
    admission, discharge = _case_times(rows_by_table, case)
    _append(rows_by_table, "inpat_registration", {
        **_base(case, discharge),
        "visit_cnt": "1",
        "admission_dept_name": "重症医学科（ICU）",
        "discharge_dept_name": "重症医学科（ICU）",
        "admission_datetime": admission,
        "discharge_datetime": discharge,
        "record_content": "派生合成验证病例的本次住院登记；入出院时间从来源病例本次住院记录受控复制。",
    })


def build_rows() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if engine is None:
        raise RuntimeError("DATABASE_URL 未配置，不能构建派生验证资料")
    _configure_clone_identity()
    rows_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    metadata = MetaData()
    source_counts: dict[str, dict[str, int]] = {}
    with Session(engine) as session:
        for table_name in V2.EXTENDED_SOURCE_TABLES:
            table = _reflect(table_name, metadata)
            if table is None:
                continue
            for case in CASES:
                count = 0
                candidate = _candidate(case)
                for row_index, source_row in enumerate(_source_rows(case=case, table=table, session=session), start=1):
                    transformed, _ = V2.transform_row(
                        table=table,
                        table_name=table_name,
                        source_row=source_row,
                        case=candidate,
                        row_index=row_index,
                    )
                    if not V2.is_meaningful_core_document(table_name, transformed):
                        continue
                    rows_by_table[table_name].append(transformed)
                    count += 1
                if count:
                    source_counts.setdefault(case.target_visit_id, {})[table_name] = count
    for case in CASES:
        _ensure_authoritative_registration(rows_by_table, case)
    supplements: dict[str, list[dict[str, Any]]] = {}
    for case in CASES:
        _normalize_discharge_diagnosis_contract(rows_by_table, case)
        supplements[case.target_visit_id] = [
            *_append_exam_lab_supplements(rows_by_table, case),
            *_append_transfusion_supplements(rows_by_table, case),
            *_append_consultation_and_handover_supplements(rows_by_table, case),
        ]
        _complete_ct_mri_associations(rows_by_table, case)
        supplements[case.target_visit_id].append({
            "table": "inpat_nondrug_order+exam_master+exam_item_report+daily_course_record",
            "reason": "controlled_complete_ct_mri_association_set",
        })
        if any(
            row.get("patient_id") == case.target_patient_id
            and row.get("visit_id") == case.target_visit_id
            for row in rows_by_table.get("diagnosis", [])
        ):
            supplements[case.target_visit_id].append({
                "table": "diagnosis+discharge_record_diagnosis",
                "reason": "controlled_consistent_discharge_diagnosis_sequence",
            })
    return dict(rows_by_table), {"source_counts": source_counts, "supplements": supplements}


def _upsert_rows(session: Session, table: Table, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    allowed = set(table.c.keys())
    payload = [{key: value for key, value in row.items() if key in allowed and value is not None} for row in rows]
    payload = [row for row in payload if row]
    if not payload:
        return 0
    columns = sorted({key for row in payload for key in row})
    payload = [{key: row.get(key) for key in columns} for row in payload]
    primary_keys = [column.name for column in table.primary_key.columns]
    statement = pg_insert(table).values(payload)
    update_columns = [column for column in columns if column not in primary_keys]
    if primary_keys and update_columns:
        statement = statement.on_conflict_do_update(
            index_elements=primary_keys,
            set_={column: getattr(statement.excluded, column) for column in update_columns},
        )
    elif primary_keys:
        statement = statement.on_conflict_do_nothing(index_elements=primary_keys)
    session.execute(statement)
    return len(payload)


def _replace_target_rows(session: Session, table: Table, rows: list[dict[str, Any]]) -> int:
    """仅在脚本专用三坐标内先删后写，兼容没有主键的 CDM 表。"""

    if not rows:
        return 0
    coordinate_columns = ("institute_id", "patient_id", "visit_id")
    missing_columns = [column for column in coordinate_columns if column not in table.c]
    if missing_columns:
        raise ValueError(f"{table.name} 缺少三坐标字段，拒绝执行派生病例替换")

    allowed_coordinates = {
        (TARGET_INSTITUTE_ID, case.target_patient_id, case.target_visit_id)
        for case in CASES
    }
    row_coordinates = {
        (
            str(row.get("institute_id") or ""),
            str(row.get("patient_id") or ""),
            str(row.get("visit_id") or ""),
        )
        for row in rows
    }
    if not row_coordinates or not row_coordinates.issubset(allowed_coordinates):
        raise ValueError(f"{table.name} 包含脚本专用三坐标之外的资料，拒绝替换")

    for institute_id, patient_id, visit_id in sorted(row_coordinates):
        session.execute(
            delete(table).where(
                and_(
                    table.c.institute_id == institute_id,
                    table.c.patient_id == patient_id,
                    table.c.visit_id == visit_id,
                )
            )
        )
    return _upsert_rows(session, table, rows)


def _validate_before_write(rows_by_table: dict[str, list[dict[str, Any]]]) -> None:
    for case in CASES:
        visit_rows = [row for rows in rows_by_table.values() for row in rows if row.get("visit_id") == case.target_visit_id]
        if not visit_rows:
            raise ValueError(f"{case.source_mr_no} 未生成任何派生资料")
        for table_name in (
            "exam_master", "exam_item_report", "labtest_master", "labtest_item_report",
            "mr_bloodtrans", "blood_application", "inpat_bill_item", "consultation_record",
            "handoff_record", "handover_record",
        ):
            if not any(row.get("visit_id") == case.target_visit_id for row in rows_by_table.get(table_name, [])):
                raise ValueError(f"{case.source_mr_no} 缺少 {table_name} 补件")
        _validate_ct_mri_associations(rows_by_table, case)
        _validate_discharge_diagnosis_contract(rows_by_table, case)
        admission, discharge = _case_times(rows_by_table, case)
        prefix = case.target_visit_id
        controlled_mr_bloodtrans = [
            row for row in rows_by_table.get("mr_bloodtrans", [])
            if row.get("visit_id") == case.target_visit_id
            and str(row.get("bloodtrans_id") or "").startswith(f"{prefix}-transfusion-controlled-")
        ]
        controlled_lab_items = [
            row for row in rows_by_table.get("labtest_item_report", [])
            if row.get("visit_id") == case.target_visit_id
            and str(row.get("test_id") or "").startswith(f"{prefix}-transfusion-controlled-")
        ]
        if len(controlled_mr_bloodtrans) != 1 or len(controlled_lab_items) != 9:
            raise ValueError(f"{case.source_mr_no} 未生成完整的受控单次输血与九项检验资料")
        transfusion_time = controlled_mr_bloodtrans[0].get("transfution_datetime")
        if not isinstance(transfusion_time, datetime) or any(
            not isinstance(row.get("report_time"), datetime) or row["report_time"] >= transfusion_time
            for row in controlled_lab_items
        ):
            raise ValueError(f"{case.source_mr_no} 的输血前九项报告时间不满足早于输血时间的合同")
        controlled_consultation = [
            row for row in rows_by_table.get("consultation_record", [])
            if row.get("visit_id") == case.target_visit_id
            and str(row.get("document_id") or "").startswith(f"{prefix}-consultation-controlled-")
        ]
        if len(controlled_consultation) != 2:
            raise ValueError(f"{case.source_mr_no} 未生成受控会诊申请/记录对")
        consultation_times = sorted(
            row.get("record_time") for row in controlled_consultation if isinstance(row.get("record_time"), datetime)
        )
        if len(consultation_times) != 2 or not timedelta(0) <= consultation_times[1] - consultation_times[0] <= timedelta(hours=24):
            raise ValueError(f"{case.source_mr_no} 的受控会诊完成时间不满足24小时合同")
        handoff_times = [
            row.get("record_time") for row in rows_by_table.get("handoff_record", [])
            if row.get("visit_id") == case.target_visit_id
            and str(row.get("document_id") or "").startswith(f"{prefix}-physician-change-controlled-")
        ]
        handover_times = [
            row.get("record_time") for row in rows_by_table.get("handover_record", [])
            if row.get("visit_id") == case.target_visit_id
            and str(row.get("document_id") or "").startswith(f"{prefix}-physician-change-controlled-")
        ]
        if len(handoff_times) != 1 or len(handover_times) != 1:
            raise ValueError(f"{case.source_mr_no} 未生成完整的受控交班/接班资料")
        for row in visit_rows:
            document_id = str(row.get("document_id") or "")
            is_controlled_supplement = (
                document_id.startswith(case.target_visit_id)
                and any(token in document_id for token in (
                    "exam-item-report", "lab-item-report", "course-exam", "course-lab",
                    "transfusion-controlled", "consultation-controlled", "physician-change-controlled",
                ))
            ) or str(row.get("exam_id") or "").startswith(case.target_visit_id) or str(row.get("test_id") or "").startswith(case.target_visit_id)
            if not is_controlled_supplement:
                continue
            for key in ("request_time", "exam_time", "report_time", "request_datetime", "report_datetime", "record_time", "submit_datetime"):
                value = row.get(key)
                if isinstance(value, datetime) and not (admission <= value <= discharge):
                    raise ValueError(f"{case.source_mr_no} 的 {key} 超出本次住院时间窗")


def _pool_item_values(case: SourceCase, now: datetime, source_tables: list[str], supplement_manifest: list[dict[str, Any]]) -> dict[str, Any]:
    raw_payload = {
        "source": "0728_real_record_derived_controlled_supplement",
        "recipe_version": RECIPE_VERSION,
        "record_scene": "final",
        "derivation_key": f"{RECIPE_VERSION}:{case.source_institute_id}:{case.source_patient_id}:{case.source_visit_id}",
        "source_record": {
            "source_pool_id": POOL_ID,
            "source_item_id": case.source_item_id,
            "institute_id": case.source_institute_id,
            "patient_id": case.source_patient_id,
            "visit_id": case.source_visit_id,
            "mr_no": case.source_mr_no,
            "patient_name": case.source_patient_name,
        },
        "supplement_manifest": supplement_manifest,
        "selected_rule_ids": RULE_IDS,
        "source_tables": source_tables,
        "visit_id": case.target_visit_id,
        "patient_id": case.target_patient_id,
        "mr_no": case.target_mr_no,
        "patient_name": case.target_patient_name,
    }
    return {
        "id": case.target_item_id,
        "pool_id": POOL_ID,
        "row_no": 9000 + case.target_index,
        "department": "重症医学科（ICU）",
        "patient_name": case.target_patient_name,
        "mr_no": case.target_mr_no,
        "manual_issue_text": "基于真实病历结构派生，受控补齐检查检验、输血前九项、会诊时限和交接班资料，用于验证相关质控点。",
        "normalized_issue_text": "基于真实病历结构派生受控补齐检查检验输血会诊交接班资料",
        "doctor_name": "合成验证",
        "qc_date": now.date(),
        "qc_user": "system",
        "coverage_type": "programmatic",
        "issue_category": "受控资料补件验证",
        "expected_scene": "final",
        "candidate_rule_ids_json": json.dumps(RULE_IDS, ensure_ascii=False),
        "include_in_batch_1": True,
        "exclude_reason": "",
        "matched_institute_id": TARGET_INSTITUTE_ID,
        "matched_patient_id": case.target_patient_id,
        "matched_visit_id": case.target_visit_id,
        "match_status": "matched",
        "sync_status": "synthetic_seeded",
        "bundle_status": "pending",
        "latest_job_id": "",
        "latest_match_status": "matched",
        "raw_payload_json": json.dumps(raw_payload, ensure_ascii=False),
        "created_at": now,
        "updated_at": now,
    }


def write_rows(rows_by_table: dict[str, list[dict[str, Any]]], audit: dict[str, Any]) -> dict[str, Any]:
    _validate_before_write(rows_by_table)
    service = CustomQCSamplePoolService()
    if service.get_pool(pool_id=POOL_ID) is None:
        raise ValueError(f"目标样本池不存在: {POOL_ID}")
    metadata = MetaData()
    inserted: dict[str, int] = {}
    now = datetime.now()
    with Session(engine) as session:
        for table_name, rows in rows_by_table.items():
            table = _reflect(table_name, metadata)
            if table is not None:
                inserted[table_name] = _replace_target_rows(session, table, rows)
        item_table = service._item_table
        for case in CASES:
            source_tables = sorted(audit["source_counts"].get(case.target_visit_id, {}))
            values = _pool_item_values(case, now, source_tables, audit["supplements"][case.target_visit_id])
            statement = pg_insert(item_table).values(values)
            statement = statement.on_conflict_do_update(
                index_elements=["id"],
                set_={key: getattr(statement.excluded, key) for key in values if key not in {"id", "created_at"}},
            )
            session.execute(statement)
        service._update_pool_counters(session, POOL_ID)
        session.commit()

    bundle_status: dict[str, Any] = {}
    for case in CASES:
        coordinate = [{"institute_id": TARGET_INSTITUTE_ID, "patient_id": case.target_patient_id, "visit_id": case.target_visit_id}]
        running = refresh_scene_bundles_for_rows(scene="running", rows=coordinate, policy_version=RECIPE_VERSION, source_schema="cdm")
        final = refresh_scene_bundles_for_rows(scene="final", rows=coordinate, policy_version=RECIPE_VERSION, source_schema="cdm")
        domain = refresh_domain_bundles_for_rows(rows=coordinate, policy_version=RECIPE_VERSION, source_schema="cdm")
        bundle_status[case.target_item_id] = {"running": running, "final": final, "domain": domain}

    with Session(engine) as session:
        for case in CASES:
            ready = all(not status.get("failed") for status in bundle_status[case.target_item_id].values())
            session.execute(update(service._item_table).where(service._item_table.c.id == case.target_item_id).values(bundle_status="ready" if ready else "failed", updated_at=datetime.now()))
        service._update_pool_counters(session, POOL_ID)
        session.commit()
    return {"inserted": inserted, "bundle_status": bundle_status}


def main() -> int:
    parser = argparse.ArgumentParser(description="构建0728检查检验合成补件副本")
    parser.add_argument("--write-db", action="store_true", help="校验通过后写入CDM、样本池并刷新Bundle")
    args = parser.parse_args()
    rows_by_table, audit = build_rows()
    _validate_before_write(rows_by_table)
    manifest = {
        "recipe_version": RECIPE_VERSION,
        "pool_id": POOL_ID,
        "write_db": bool(args.write_db),
        "row_counts": dict(sorted((name, len(rows)) for name, rows in rows_by_table.items())),
        **audit,
    }
    if args.write_db:
        manifest["write_result"] = write_rows(rows_by_table, audit)
    OUTPUT_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
