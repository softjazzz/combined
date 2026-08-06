from __future__ import annotations

"""为 0728 样本池的两份真实病历生成可追溯的检查检验补件副本。

这是一次性、受控的验证资料构建器：不修改源病例；每份副本使用新三坐标，
并把原始三坐标、补件清单和 recipe 版本写入样本池 raw_payload。它不试图
解决其他真实缺失资料，只补检查/检验报告与核对病程，验证 010/011/012/014/015。
"""

import argparse
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

import sqlalchemy as sa
from sqlalchemy import MetaData, Table, and_, select, update
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


RECIPE_VERSION = "lx0609-0728-exam-lab-derived-v1"
POOL_ID = "aacc704a-ef30-47bf-a74c-86fc91d29273"
TARGET_INSTITUTE_ID = "LX0609_0728_DERIVED_V1"
RULE_IDS = ["LX0609-010", "LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"]
OUTPUT_PATH = ROOT / "tmp-0728-exam-lab-derived-v1-manifest.json"


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
    supplements = {case.target_visit_id: _append_exam_lab_supplements(rows_by_table, case) for case in CASES}
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


def _validate_before_write(rows_by_table: dict[str, list[dict[str, Any]]]) -> None:
    for case in CASES:
        visit_rows = [row for rows in rows_by_table.values() for row in rows if row.get("visit_id") == case.target_visit_id]
        if not visit_rows:
            raise ValueError(f"{case.source_mr_no} 未生成任何派生资料")
        for table_name in ("exam_master", "exam_item_report", "labtest_master", "labtest_item_report"):
            if not any(row.get("visit_id") == case.target_visit_id for row in rows_by_table.get(table_name, [])):
                raise ValueError(f"{case.source_mr_no} 缺少 {table_name} 补件")
        admission, discharge = _case_times(rows_by_table, case)
        for row in visit_rows:
            document_id = str(row.get("document_id") or "")
            is_controlled_supplement = (
                document_id.startswith(case.target_visit_id)
                and any(token in document_id for token in ("exam-item-report", "lab-item-report", "course-exam", "course-lab"))
            ) or str(row.get("exam_id") or "").startswith(case.target_visit_id) or str(row.get("test_id") or "").startswith(case.target_visit_id)
            if not is_controlled_supplement:
                continue
            for key in ("request_time", "exam_time", "report_time", "request_datetime", "report_datetime", "record_time", "submit_datetime"):
                value = row.get(key)
                if isinstance(value, datetime) and not (admission <= value <= discharge):
                    raise ValueError(f"{case.source_mr_no} 的 {key} 超出本次住院时间窗")


def _pool_item_values(case: SourceCase, now: datetime, source_tables: list[str], supplement_manifest: list[dict[str, Any]]) -> dict[str, Any]:
    raw_payload = {
        "source": "0728_real_record_derived_exam_lab",
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
        "manual_issue_text": "基于真实病历结构派生，仅补齐检查检验报告与核对病程，用于验证相关质控点。",
        "normalized_issue_text": "基于真实病历结构派生补齐检查检验报告与核对病程",
        "doctor_name": "合成验证",
        "qc_date": now.date(),
        "qc_user": "system",
        "coverage_type": "programmatic",
        "issue_category": "检查检验补件验证",
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
                inserted[table_name] = _upsert_rows(session, table, rows)
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
