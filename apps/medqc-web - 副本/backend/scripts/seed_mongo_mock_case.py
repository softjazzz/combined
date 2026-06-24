#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MongoDB 全量 mock 病历造数脚本（25集合 + 双 visit）

用途：
1. 为同一患者生成两条就诊记录（已出院 + 在院中）
2. 覆盖 etl_config.MONGO_COLLECTION_MAP 中全部集合
3. 幂等写入（replace_one + upsert）
4. 提供 verify-only 验证能力，输出结构化 JSON 报告
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.etl_config import COLLECTION_KEY_FIELDS, MONGO_COLLECTION_MAP, load_mongo_config
from app.services.mongo_sync import MongoConnector
from app.database.connection import SessionLocal
from app.database.models.cdm import MedicalInsuranceSettlement, MedicalInsuranceSettlementCost


DISCHARGED_LABEL = "discharged"
INPATIENT_LABEL = "inpatient"


@dataclass
class VisitMeta:
    label: str
    visit_id: str
    inpat_no: str
    mr_no: str
    admission_datetime: datetime
    discharge_datetime: Optional[datetime]
    admission_dept_name: str
    discharge_dept_name: str
    ward_name: str


def _now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _to_jsonable(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat(sep=" ")
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj


def _dt(y: int, m: int, d: int, hh: int = 0, mm: int = 0, ss: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, ss)


def _visit_metas(visit_id_discharged: str, visit_id_inpatient: str) -> Dict[str, VisitMeta]:
    return {
        DISCHARGED_LABEL: VisitMeta(
            label=DISCHARGED_LABEL,
            visit_id=visit_id_discharged,
            inpat_no="INP-MOCK-D-001",
            mr_no="MR-MOCK-D-001",
            admission_datetime=_dt(2026, 1, 5, 9, 30, 0),
            discharge_datetime=_dt(2026, 1, 17, 14, 0, 0),  # 固定历史时间，满足 tier1 stable 条件
            admission_dept_name="心内科",
            discharge_dept_name="心内科",
            ward_name="心内科一病区",
        ),
        INPATIENT_LABEL: VisitMeta(
            label=INPATIENT_LABEL,
            visit_id=visit_id_inpatient,
            inpat_no="INP-MOCK-I-001",
            mr_no="MR-MOCK-I-001",
            admission_datetime=_dt(2026, 3, 20, 10, 0, 0),
            discharge_datetime=None,  # 在院中
            admission_dept_name="外二科（肛肠外科）",
            discharge_dept_name="外二科（肛肠外科）",
            ward_name="外二科病区",
        ),
    }


def _base_person(now: datetime, patient_id: str) -> Dict[str, Any]:
    return {
        "institute_id": "SCPH",
        "patient_id": patient_id,
        "name": "王磊",
        "sex": "男",
        "birthday": _dt(1968, 1, 15),
        "age_year": "58",
        "id_card_type": "身份证",
        "id_card_no": "510521196801151234",
        "ethnicity": "汉族",
        "nationality": "中国",
        "marital_status": "已婚",
        "occupation_category": "退休",
        "contact_number": "13812345678",
        "work_unit": "泸县机械集团",
        "nativeplace": "四川泸州",
        "currentaddress": "四川省泸州市泸县滨江路123号",
        "contact_name": "王小红",
        "contact_relationship": "女儿",
        "contact_address": "四川省泸州市广场路88号",
        "contact_telephone": "13987654321",
        "visit_type": "I",
        "update_time": now,
        "last_modifier": "mock_seed",
        "last_modifier_id": "mock_seed",
        "last_modified_datetime": now,
    }


def _mr_doc(base: Dict[str, Any], visit: VisitMeta, now: datetime, discharged: bool) -> Dict[str, Any]:
    doc = {
        **base,
        "visit_id": visit.visit_id,
        "document_id": f"DOC-MR-{visit.visit_id}",
        "inpat_no": visit.inpat_no,
        "mr_no": visit.mr_no,
        "visit_cnt": "1",
        "institute_code": "510521001",
        "institute_county_desc": "泸县人民医院",
        "medical_payment_method": "城镇职工基本医疗保险",
        "insurance_type": "城镇职工基本医疗保险",
        "insurance_no": "YB5105210001",
        "admission_route": "门诊",
        "admission_datetime": visit.admission_datetime,
        "admission_dept_name": visit.admission_dept_name,
        "admission_ward_name": visit.ward_name,
        "admission_condition": "一般",
        "discharge_datetime": visit.discharge_datetime,
        "discharge_dept_name": visit.discharge_dept_name if discharged else None,
        "discharge_ward_name": visit.ward_name if discharged else None,
        "hospital_duration": "12" if discharged else "0",
        "pathology_id": "BL-2026-0110" if discharged else "",
        "allergy_sign": "有",
        "allergy_history": "青霉素",
        "abo_blood_code": "O型",
        "rh_blood_code": "阳性",
        "medicalrecord_quality": "甲",
        "leaving_hospital_way": "1" if discharged else None,
        "clinical_pathway": "是",
        "archive_sign": "是" if discharged else "否",
        "mr_datetime": now,
        "record_content": f"{'出院' if discharged else '在院'}病案首页 mock 数据",
        "update_time": now,
    }
    return doc


def _diagnosis_docs(base: Dict[str, Any], visit: VisitMeta, now: datetime, discharged: bool) -> List[Dict[str, Any]]:
    if discharged:
        items = [
            ("出院主要诊断", "1", "不稳定型心绞痛", "I20.000", "1"),
            ("出院其他诊断", "2", "冠状动脉粥样硬化性心脏病", "I25.103", "1"),
            ("出院其他诊断", "3", "2型糖尿病", "E11.900", "2"),
            ("出院其他诊断", "4", "高血压病3级（极高危）", "I10.x00x002", "1"),
        ]
    else:
        items = [
            ("入院诊断", "1", "混合痔", "I84.700", "1"),
            ("入院诊断", "2", "慢性便秘", "K59.000", "1"),
        ]

    docs: List[Dict[str, Any]] = []
    for idx, (diag_type, diag_no, diag_name, diag_code, admission_condition) in enumerate(items, start=1):
        docs.append(
            {
                **base,
                "visit_id": visit.visit_id,
                "document_id": f"DOC-DIAG-{visit.visit_id}",
                "inpat_no": visit.inpat_no,
                "dept_name": visit.admission_dept_name,
                "diagnosis_id": f"DIAG-{visit.visit_id}-{idx}",
                "diagnosis_type": diag_type,
                "diagnosis_no": diag_no,
                "diagnosis_name": diag_name,
                "diagnosis_code": diag_code,
                "admission_condition": admission_condition,
                "discharge_condition": "好转" if discharged else None,
                "diagnosis_source": "出院记录" if discharged else "入院记录",
                "diagnosis_datetime": visit.admission_datetime,
                "diagnosis_updatetime": now,
                "update_time": now,
            }
        )
    return docs


def _surgery_docs(base: Dict[str, Any], visit: VisitMeta, now: datetime, discharged: bool) -> List[Dict[str, Any]]:
    if discharged:
        rows = [
            ("SURG-1", "经皮冠状动脉药物洗脱支架植入术", "36.0701", "1", _dt(2026, 1, 10, 9, 0, 0), "王建华"),
            ("SURG-2", "冠状动脉造影术", "88.5500", "0", _dt(2026, 1, 9, 14, 30, 0), "王建华"),
        ]
    else:
        rows = [
            ("SURG-1", "痔切除术", "49.4600", "1", _dt(2026, 3, 21, 10, 15, 0), "李明华"),
        ]
    out: List[Dict[str, Any]] = []
    for suffix, surgery_name, surgery_code, main_sign, begin_dt, surgeon in rows:
        out.append(
            {
                **base,
                "visit_id": visit.visit_id,
                "document_id": f"DOC-SURG-{visit.visit_id}",
                "surgery_id": f"{visit.visit_id}-{suffix}",
                "inpat_no": visit.inpat_no,
                "mr_no": visit.mr_no,
                "surgery_name": surgery_name,
                "surgery_code": surgery_code,
                "surgical_level": "4" if main_sign == "1" else "2",
                "surgial_incision_level": "0类切口",
                "surgical_incisionheal_level": "甲级愈合",
                "anesthesia_method": "局部麻醉" if not discharged else "局部麻醉",
                "surgery_begin_datetime": begin_dt,
                "surgery_end_datetime": begin_dt,
                "surgeon": surgeon,
                "first_assistant": "周丽",
                "second_assistant": "陈亮",
                "anesthesiologist": "周丽",
                "main_surgery_sign": main_sign,
                "update_time": now,
            }
        )
    return out


def _cost_doc(base: Dict[str, Any], visit: VisitMeta, now: datetime, discharged: bool) -> Dict[str, Any]:
    return {
        **base,
        "visit_id": visit.visit_id,
        "document_id": f"DOC-COST-{visit.visit_id}",
        "inpat_no": visit.inpat_no,
        "mr_no": visit.mr_no,
        "total_cost": "85672.34" if discharged else "12500.00",
        "self_pay": "12345.67" if discharged else "2200.00",
        "general_medical_service_fee": "1200.00",
        "nursing_care_fee": "600.00",
        "laboratory_diagnostic_fee": "2600.00",
        "imaging_diagnostic_fee": "2300.00",
        "surgery_treatment_fee": "21000.00" if discharged else "9800.00",
        "anesthesia_fee": "1800.00" if discharged else "700.00",
        "western_medicine_fee": "18600.00",
        "chinese_herbal_medicine_fee": "0.00",
        "blood_fee": "0.00",
        "surgery_disposable_mat_fee": "6200.00",
        "other_fee": "1800.00",
        "settle_datetime": visit.discharge_datetime if discharged else now,
        "update_time": now,
    }


def _simple_doc(
    base: Dict[str, Any],
    visit: VisitMeta,
    now: datetime,
    collection_name: str,
    discharged: bool,
    *,
    with_document_id: bool = True,
) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        **base,
        "visit_id": visit.visit_id,
        "inpat_no": visit.inpat_no,
        "mr_no": visit.mr_no,
        "document_title": f"{collection_name}（{'已出院' if discharged else '在院'}）",
        "document_status": "已归档" if discharged else "在院中",
        "submitter": "系统",
        "submitter_id": "mock_seed",
        "submit_datetime": now,
        "record_content": f"{collection_name} mock 内容（{visit.visit_id}）",
        "update_time": now,
    }
    if with_document_id:
        doc["document_id"] = f"DOC-{collection_name.upper()}-{visit.visit_id}"
    return doc


def build_mock_documents(
    patient_id: str,
    visit_id_discharged: str,
    visit_id_inpatient: str,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, VisitMeta]]:
    now = _now()
    visits = _visit_metas(visit_id_discharged, visit_id_inpatient)
    base = _base_person(now, patient_id)

    docs: Dict[str, List[Dict[str, Any]]] = {name: [] for name in MONGO_COLLECTION_MAP.keys()}

    # 核心 4 表
    docs["mr"].append(_mr_doc(base, visits[DISCHARGED_LABEL], now, discharged=True))
    docs["mr"].append(_mr_doc(base, visits[INPATIENT_LABEL], now, discharged=False))

    docs["diagnosis"].extend(_diagnosis_docs(base, visits[DISCHARGED_LABEL], now, discharged=True))
    docs["diagnosis"].extend(_diagnosis_docs(base, visits[INPATIENT_LABEL], now, discharged=False))

    docs["mr_surgery"].extend(_surgery_docs(base, visits[DISCHARGED_LABEL], now, discharged=True))
    docs["mr_surgery"].extend(_surgery_docs(base, visits[INPATIENT_LABEL], now, discharged=False))

    docs["mr_cost"].append(_cost_doc(base, visits[DISCHARGED_LABEL], now, discharged=True))
    docs["mr_cost"].append(_cost_doc(base, visits[INPATIENT_LABEL], now, discharged=False))

    # 其余集合（Tier3 + admission/discharge/death）
    all_other = [c for c in MONGO_COLLECTION_MAP.keys() if c not in {"mr", "diagnosis", "mr_surgery", "mr_cost"}]
    for coll in all_other:
        keys = COLLECTION_KEY_FIELDS.get(coll, ["institute_id", "patient_id", "visit_id", "document_id"])
        with_doc_id = "document_id" in keys
        docs[coll].append(_simple_doc(base, visits[DISCHARGED_LABEL], now, coll, discharged=True, with_document_id=with_doc_id))
        docs[coll].append(_simple_doc(base, visits[INPATIENT_LABEL], now, coll, discharged=False, with_document_id=with_doc_id))

    return docs, visits


def _upsert_pg_row(session: Any, model: Any, key_fields: List[str], payload: Dict[str, Any]) -> str:
    """基于主键查询后更新/插入，返回 created|updated。"""
    filters = [getattr(model, k) == payload[k] for k in key_fields]
    row = session.query(model).filter(*filters).first()
    if row is None:
        row = model(**payload)
        session.add(row)
        return "created"
    for k, v in payload.items():
        setattr(row, k, v)
    return "updated"


def seed_pg_settlement(patient_id: str, visits: Dict[str, VisitMeta]) -> Dict[str, Any]:
    """为双 visit 写入/更新 PG 结算主表与费用明细。"""
    now = _now()
    institute_id = "SCPH"
    summary = {
        "enabled": True,
        "main_table": {"created": 0, "updated": 0},
        "cost_table": {"created": 0, "updated": 0},
        "errors": [],
    }

    def _main_payload(visit: VisitMeta, discharged: bool) -> Dict[str, Any]:
        return {
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": visit.visit_id,
            "visit_type": "I",
            "document_id": f"SETTLE-{visit.visit_id}",
            "designated_medical_institution": "510521001",
            "medical_insurance_record_dept": visit.admission_dept_name,
            "medical_insurance_recorder": "系统管理员",
            "medinsur_serial_no": f"MSN-{visit.visit_id}",
            "business_serial_no": f"BSN-{visit.visit_id}",
            "medinsur_receipt_id": f"MRC-{visit.visit_id}",
            "ticket_code": "TICK-001",
            "ticket_no": f"TK-{visit.visit_id}",
            "settlement_method": "按项目",
            "patient_insurance_no": "YB5105210001",
            "inpat_no": visit.inpat_no,
            "mr_no": visit.mr_no,
            "nationality": "中国",
            "occupation_category": "退休",
            "currentaddress": "四川省泸州市泸县滨江路123号",
            "currentaddress_postcode": "646100",
            "currentaddress_phone": "13812345678",
            "work_unit": "泸县机械集团",
            "workplace": "四川省泸州市泸县工业园区",
            "work_telephone": "0830-3456789",
            "contact_name": "王小红",
            "contact_relationship": "女儿",
            "contact_address": "四川省泸州市广场路88号",
            "contact_telephone": "13987654321",
            "admission_route": "门诊",
            "admission_datetime": visit.admission_datetime,
            "admission_dept_name": visit.admission_dept_name,
            "transfer_dept_name": "",
            "discharge_datetime": visit.discharge_datetime,
            "discharge_dept_name": visit.discharge_dept_name if discharged else "",
            "leaving_hospital_way": "1" if discharged else "",
            "rehospital_with_month": "0",
            "rehospital_with_month_purpose": "",
            "insurance_no": "YB5105210001",
            "declaration_time": now,
            "inpat_type": "普通住院",
            "therapy_type": "西医治疗",
            "diagnosis_code_cnt": "4" if discharged else "2",
            "surgery_code_cnt": "2" if discharged else "1",
            "ventilator_usetime": "0",
            "primary_care_days": "0",
            "secondary_care_days": "0",
            "tertiary_care_days": "12" if discharged else "3",
            "intensive_care_days": "0",
            "insured_place": "泸县",
            "out_of_pocket_advance": "12345.67" if discharged else "2200.00",
            "out_of_pocket_amount": "8000.00" if discharged else "1800.00",
            "personal_account_expend": "5000.00" if discharged else "1200.00",
            "cash_payment_amount": "3000.00" if discharged else "900.00",
            "insurance_type": "城镇职工基本医疗保险",
            "medical_insurance_institution": "泸县医保局",
            "medical_insurance_agent": "李审核",
            "medical_insurance_agent_code": "YB001",
            "attending_physician_code": "DOC001",
            "responsible_nurse_code": "NUR001",
            "settlement_status": "已结算" if discharged else "待结算",
            "start_date": visit.admission_datetime,
            "end_date": visit.discharge_datetime if discharged else now,
            "update_time": now,
        }

    def _cost_payloads(visit: VisitMeta, discharged: bool) -> List[Dict[str, Any]]:
        base = {
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": visit.visit_id,
            "visit_type": "I",
            "document_id": f"SETTLE-{visit.visit_id}",
            "medinsur_serial_no": f"MSN-{visit.visit_id}",
            "update_time": now,
        }
        if discharged:
            return [
                {
                    **base,
                    "medinsur_serial_item_id": f"{visit.visit_id}-ITEM-001",
                    "charge": "42000.00",
                    "type_of_medicalcharge": "手术治疗费",
                    "charge_item_level": "甲类",
                    "item_class_a_amount": "40000.00",
                    "item_class_b_amount": "1500.00",
                    "item_own_pay_amount": "500.00",
                    "item_other_amount": "0.00",
                },
                {
                    **base,
                    "medinsur_serial_item_id": f"{visit.visit_id}-ITEM-002",
                    "charge": "18600.00",
                    "type_of_medicalcharge": "西药费",
                    "charge_item_level": "乙类",
                    "item_class_a_amount": "12000.00",
                    "item_class_b_amount": "5000.00",
                    "item_own_pay_amount": "1600.00",
                    "item_other_amount": "0.00",
                },
            ]
        return [
            {
                **base,
                "medinsur_serial_item_id": f"{visit.visit_id}-ITEM-001",
                "charge": "9800.00",
                "type_of_medicalcharge": "手术治疗费",
                "charge_item_level": "甲类",
                "item_class_a_amount": "8200.00",
                "item_class_b_amount": "1100.00",
                "item_own_pay_amount": "500.00",
                "item_other_amount": "0.00",
            }
        ]

    session = SessionLocal()
    try:
        for label, visit in visits.items():
            discharged = label == DISCHARGED_LABEL
            payload = _main_payload(visit, discharged=discharged)
            state = _upsert_pg_row(
                session,
                MedicalInsuranceSettlement,
                ["institute_id", "patient_id", "visit_id"],
                payload,
            )
            summary["main_table"][state] += 1

            for c in _cost_payloads(visit, discharged=discharged):
                c_state = _upsert_pg_row(
                    session,
                    MedicalInsuranceSettlementCost,
                    ["institute_id", "patient_id", "visit_id", "medinsur_serial_item_id"],
                    c,
                )
                summary["cost_table"][c_state] += 1

        session.commit()
        return summary
    except Exception as exc:
        session.rollback()
        summary["errors"].append(str(exc))
        return summary
    finally:
        session.close()


def _get_filter_from_keys(doc: Dict[str, Any], keys: List[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    filt: Dict[str, Any] = {}
    for key in keys:
        value = doc.get(key)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None, f"主键字段缺失: {key}"
        filt[key] = value
    return filt, None


def write_mock_documents(
    connector: MongoConnector,
    docs: Dict[str, List[Dict[str, Any]]],
    *,
    do_upsert: bool,
    dry_run: bool,
) -> Dict[str, Any]:
    db = connector.get_db()
    summary: Dict[str, Any] = {
        "collections_total": len(docs),
        "collections_processed": 0,
        "records_total": 0,
        "records_written": 0,
        "records_matched": 0,
        "records_upserted": 0,
        "records_failed": 0,
        "per_collection": {},
    }

    for coll, records in docs.items():
        keys = COLLECTION_KEY_FIELDS.get(coll, ["institute_id", "patient_id", "visit_id", "document_id"])
        coll_stat = {
            "records": len(records),
            "written": 0,
            "matched": 0,
            "upserted": 0,
            "failed": 0,
            "errors": [],
            "key_fields": keys,
        }
        summary["collections_processed"] += 1
        summary["records_total"] += len(records)

        for doc in records:
            filt, err = _get_filter_from_keys(doc, keys)
            if err:
                coll_stat["failed"] += 1
                summary["records_failed"] += 1
                coll_stat["errors"].append(err)
                continue

            if dry_run:
                coll_stat["written"] += 1
                summary["records_written"] += 1
                continue

            try:
                if do_upsert:
                    result = db[coll].replace_one(filt, doc, upsert=True)
                else:
                    result = db[coll].replace_one(filt, doc, upsert=False)
                coll_stat["written"] += 1
                summary["records_written"] += 1
                coll_stat["matched"] += int(result.matched_count or 0)
                summary["records_matched"] += int(result.matched_count or 0)
                if result.upserted_id is not None:
                    coll_stat["upserted"] += 1
                    summary["records_upserted"] += 1
            except Exception as exc:
                coll_stat["failed"] += 1
                summary["records_failed"] += 1
                coll_stat["errors"].append(str(exc))

        summary["per_collection"][coll] = coll_stat

    return summary


def _count_by_visit(db: Any, collection: str, patient_id: str, visit_ids: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for vid in visit_ids:
        out[vid] = int(db[collection].count_documents({"patient_id": patient_id, "visit_id": vid}))
    return out


def verify_mock_documents(
    connector: MongoConnector,
    patient_id: str,
    visit_id_discharged: str,
    visit_id_inpatient: str,
) -> Dict[str, Any]:
    db = connector.get_db()
    visit_ids = [visit_id_discharged, visit_id_inpatient]

    per_collection: Dict[str, Any] = {}
    covered = 0
    total = len(MONGO_COLLECTION_MAP)
    consistency_checks: List[Dict[str, Any]] = []

    # 覆盖率 + 主键完整性
    for coll in MONGO_COLLECTION_MAP.keys():
        counts = _count_by_visit(db, coll, patient_id, visit_ids)
        total_count = sum(counts.values())
        if total_count > 0:
            covered += 1

        keys = COLLECTION_KEY_FIELDS.get(coll, ["institute_id", "patient_id", "visit_id", "document_id"])
        docs = list(db[coll].find({"patient_id": patient_id, "visit_id": {"$in": visit_ids}}, {"_id": 0}))
        missing_pk_docs = 0
        for d in docs:
            for k in keys:
                v = d.get(k)
                if v is None or (isinstance(v, str) and v.strip() == ""):
                    missing_pk_docs += 1
                    break

        per_collection[coll] = {
            "counts_by_visit": counts,
            "total_count": total_count,
            "key_fields": keys,
            "missing_pk_docs": missing_pk_docs,
            "covered": total_count > 0,
        }

        consistency_checks.append(
            {
                "check_id": f"coverage_{coll}",
                "passed": counts.get(visit_id_discharged, 0) > 0 and counts.get(visit_id_inpatient, 0) > 0,
                "message": f"{coll} 两条 visit 均有数据",
                "detail": counts,
            }
        )
        consistency_checks.append(
            {
                "check_id": f"pk_integrity_{coll}",
                "passed": missing_pk_docs == 0,
                "message": f"{coll} 主键字段完整性检查",
                "detail": {"missing_pk_docs": missing_pk_docs},
            }
        )

    # 核心字段完整性（已出院）
    mr_d = db["mr"].find_one({"patient_id": patient_id, "visit_id": visit_id_discharged}, {"_id": 0}) or {}
    diag_d = list(db["diagnosis"].find({"patient_id": patient_id, "visit_id": visit_id_discharged}, {"_id": 0}))
    surg_d = list(db["mr_surgery"].find({"patient_id": patient_id, "visit_id": visit_id_discharged}, {"_id": 0}))
    cost_d = db["mr_cost"].find_one({"patient_id": patient_id, "visit_id": visit_id_discharged}, {"_id": 0}) or {}

    main_diag = [x for x in diag_d if "主要" in str(x.get("diagnosis_type") or "")]
    other_diag = [x for x in diag_d if "主要" not in str(x.get("diagnosis_type") or "")]
    main_surg = [x for x in surg_d if str(x.get("main_surgery_sign") or "") in {"1", "true", "True", "是"}]

    consistency_checks.extend(
        [
            {
                "check_id": "core_mr_discharged",
                "passed": bool(mr_d.get("update_time")) and bool(mr_d.get("admission_datetime"))
                and bool(mr_d.get("discharge_datetime")) and bool(mr_d.get("discharge_dept_name")),
                "message": "已出院 visit 的 mr 核心字段完整",
                "detail": {
                    "update_time": bool(mr_d.get("update_time")),
                    "admission_datetime": bool(mr_d.get("admission_datetime")),
                    "discharge_datetime": bool(mr_d.get("discharge_datetime")),
                    "discharge_dept_name": bool(mr_d.get("discharge_dept_name")),
                },
            },
            {
                "check_id": "core_diagnosis_discharged",
                "passed": len(main_diag) >= 1 and len(other_diag) >= 1 and all(bool(x.get("diagnosis_code")) for x in diag_d),
                "message": "已出院 visit 的 diagnosis 主/其他诊断及编码完整",
                "detail": {
                    "main_diag_count": len(main_diag),
                    "other_diag_count": len(other_diag),
                    "total_diag_count": len(diag_d),
                    "all_have_code": all(bool(x.get("diagnosis_code")) for x in diag_d) if diag_d else False,
                },
            },
            {
                "check_id": "core_surgery_discharged",
                "passed": len(main_surg) >= 1 and all(bool(x.get("surgery_code")) for x in surg_d),
                "message": "已出院 visit 的 mr_surgery 主手术及编码完整",
                "detail": {
                    "main_surgery_count": len(main_surg),
                    "total_surgery_count": len(surg_d),
                    "all_have_code": all(bool(x.get("surgery_code")) for x in surg_d) if surg_d else False,
                },
            },
            {
                "check_id": "core_cost_discharged",
                "passed": bool(cost_d.get("total_cost")) and bool(cost_d.get("self_pay")),
                "message": "已出院 visit 的 mr_cost 总费用/自付完整",
                "detail": {
                    "total_cost": bool(cost_d.get("total_cost")),
                    "self_pay": bool(cost_d.get("self_pay")),
                },
            },
        ]
    )

    # 核心字段完整性（在院）
    mr_i = db["mr"].find_one({"patient_id": patient_id, "visit_id": visit_id_inpatient}, {"_id": 0}) or {}
    diag_i = list(db["diagnosis"].find({"patient_id": patient_id, "visit_id": visit_id_inpatient}, {"_id": 0}))
    consistency_checks.extend(
        [
            {
                "check_id": "core_mr_inpatient",
                "passed": bool(mr_i.get("update_time")) and bool(mr_i.get("admission_datetime")) and (mr_i.get("discharge_datetime") is None),
                "message": "在院 visit 的 mr 状态正确（discharge_datetime 为空）",
                "detail": {
                    "update_time": bool(mr_i.get("update_time")),
                    "admission_datetime": bool(mr_i.get("admission_datetime")),
                    "discharge_datetime_is_none": mr_i.get("discharge_datetime") is None,
                },
            },
            {
                "check_id": "core_diag_inpatient",
                "passed": len(diag_i) >= 1 and all(bool(x.get("diagnosis_code")) for x in diag_i),
                "message": "在院 visit 的 diagnosis 至少一条且编码完整",
                "detail": {
                    "diag_count": len(diag_i),
                    "all_have_code": all(bool(x.get("diagnosis_code")) for x in diag_i) if diag_i else False,
                },
            },
        ]
    )

    coverage_rate = round(100.0 * covered / total, 2) if total else 0.0
    passed_count = sum(1 for x in consistency_checks if x["passed"])
    failed_checks = [x["check_id"] for x in consistency_checks if not x["passed"]]

    return {
        "coverage_summary": {
            "total_collections": total,
            "covered_collections": covered,
            "coverage_rate_pct": coverage_rate,
            "per_collection": per_collection,
        },
        "consistency_checks": consistency_checks,
        "consistency_summary": {
            "total_checks": len(consistency_checks),
            "passed_checks": passed_count,
            "failed_checks": len(consistency_checks) - passed_count,
            "failed_check_ids": failed_checks,
        },
    }


def _build_report(
    patient_id: str,
    visit_id_discharged: str,
    visit_id_inpatient: str,
    mongo_db: str,
    mode: str,
    write_summary: Dict[str, Any],
    pg_settlement_summary: Dict[str, Any],
    verify_summary: Dict[str, Any],
    warnings: List[str],
) -> Dict[str, Any]:
    consistency = verify_summary.get("consistency_summary") or {}
    passed = int(consistency.get("failed_checks", 1)) == 0
    return {
        "case_meta": {
            "patient_id": patient_id,
            "visit_ids": {
                "discharged": visit_id_discharged,
                "inpatient": visit_id_inpatient,
            },
            "mongo_db": mongo_db,
            "mode": mode,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "write_summary": write_summary,
        "pg_settlement_summary": pg_settlement_summary,
        "coverage_summary": verify_summary.get("coverage_summary", {}),
        "consistency_checks": verify_summary.get("consistency_checks", []),
        "final_status": {
            "passed": passed,
            "warnings": warnings,
            "failed_check_ids": consistency.get("failed_check_ids", []),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成并验证 MongoDB 全量 mock 病历（25集合+双visit）")
    parser.add_argument("--patient-id", default="P-MOCK-001", help="患者ID")
    parser.add_argument("--visit-id-discharged", default="V-MOCK-D-001", help="已出院 visit_id")
    parser.add_argument("--visit-id-inpatient", default="V-MOCK-I-001", help="在院 visit_id")
    parser.add_argument("--mongo-uri", default="", help="Mongo URI，默认读取 etl_config")
    parser.add_argument("--mongo-db", default="", help="Mongo 数据库名，默认读取 etl_config")
    parser.add_argument("--upsert", dest="upsert", action="store_true", default=True, help="启用 upsert（默认开启）")
    parser.add_argument("--no-upsert", dest="upsert", action="store_false", help="关闭 upsert")
    parser.add_argument("--dry-run", action="store_true", help="仅模拟写入，不落库")
    parser.add_argument("--verify-only", action="store_true", help="仅做验证，不写入")
    parser.add_argument("--seed-pg-settlement", dest="seed_pg_settlement", action="store_true", default=True, help="同步写入 PG 结算主表与费用明细（默认开启）")
    parser.add_argument("--no-seed-pg-settlement", dest="seed_pg_settlement", action="store_false", help="关闭 PG 结算写入")
    parser.add_argument("--output-dir", default="reports/mock_seed", help="报告输出目录（相对 backend 根目录）")
    args = parser.parse_args()

    cfg = load_mongo_config()
    mongo_uri = args.mongo_uri or cfg.mongo_uri
    mongo_db = args.mongo_db or cfg.mongo_database
    if not mongo_uri:
        print("[ERROR] 未提供 mongo_uri 且配置中为空", file=sys.stderr)
        return 2

    connector = MongoConnector(
        uri=mongo_uri,
        database=mongo_db,
        read_preference=cfg.read_preference,
        max_pool_size=1,
        socket_timeout_ms=cfg.query_timeout_s * 1000,
        connect_timeout_ms=cfg.connect_timeout_ms,
    )
    warnings: List[str] = []

    try:
        conn_test = connector.test_connection()
        if not conn_test.get("connected"):
            print(f"[ERROR] Mongo 连接失败: {conn_test.get('error')}", file=sys.stderr)
            return 2

        write_summary: Dict[str, Any] = {
            "mode": "verify_only" if args.verify_only else ("dry_run" if args.dry_run else "write"),
            "collections_total": len(MONGO_COLLECTION_MAP),
            "collections_processed": 0,
            "records_total": 0,
            "records_written": 0,
            "records_matched": 0,
            "records_upserted": 0,
            "records_failed": 0,
            "per_collection": {},
        }

        if not args.verify_only:
            docs, _ = build_mock_documents(
                patient_id=args.patient_id,
                visit_id_discharged=args.visit_id_discharged,
                visit_id_inpatient=args.visit_id_inpatient,
            )
            write_summary = write_mock_documents(
                connector=connector,
                docs=docs,
                do_upsert=args.upsert,
                dry_run=args.dry_run,
            )
            write_summary["mode"] = "dry_run" if args.dry_run else "write"

        pg_settlement_summary: Dict[str, Any] = {"enabled": bool(args.seed_pg_settlement), "skipped": True}
        if not args.verify_only and not args.dry_run and args.seed_pg_settlement:
            _, visits = build_mock_documents(
                patient_id=args.patient_id,
                visit_id_discharged=args.visit_id_discharged,
                visit_id_inpatient=args.visit_id_inpatient,
            )
            pg_settlement_summary = seed_pg_settlement(
                patient_id=args.patient_id,
                visits=visits,
            )
            pg_settlement_summary["skipped"] = False
            if pg_settlement_summary.get("errors"):
                warnings.append("PG 结算数据写入失败，请查看 pg_settlement_summary.errors")

        verify_summary = verify_mock_documents(
            connector=connector,
            patient_id=args.patient_id,
            visit_id_discharged=args.visit_id_discharged,
            visit_id_inpatient=args.visit_id_inpatient,
        )

        report = _build_report(
            patient_id=args.patient_id,
            visit_id_discharged=args.visit_id_discharged,
            visit_id_inpatient=args.visit_id_inpatient,
            mongo_db=mongo_db,
            mode=write_summary.get("mode", "verify_only"),
            write_summary=write_summary,
            pg_settlement_summary=pg_settlement_summary,
            verify_summary=verify_summary,
            warnings=warnings,
        )

        out_dir = (BACKEND_ROOT / args.output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = out_dir / f"mongo_mock_seed_{args.patient_id}_{ts}.json"
        out_path.write_text(json.dumps(_to_jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8")

        print("=" * 72)
        print("Mongo mock 病历处理完成")
        print(f"patient_id: {args.patient_id}")
        print(f"visit_id(discharged): {args.visit_id_discharged}")
        print(f"visit_id(inpatient): {args.visit_id_inpatient}")
        print(f"写入模式: {write_summary.get('mode')}")
        print(f"集合覆盖率: {verify_summary['coverage_summary']['coverage_rate_pct']}%")
        print(f"一致性检查: {verify_summary['consistency_summary']['passed_checks']}/{verify_summary['consistency_summary']['total_checks']}")
        print(f"报告文件: {out_path}")
        print("=" * 72)

        return 0 if report["final_status"]["passed"] else 1
    finally:
        connector.close()


if __name__ == "__main__":
    raise SystemExit(main())
