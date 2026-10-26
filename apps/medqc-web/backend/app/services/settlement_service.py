"""
医保结算清单数据组装服务

职责：
1. 从 PG 表查询并组装完整的结算清单 dict
2. 调用 SettlementFormalQCEngine 执行质控
3. 提供列表查询、详情查询、质控调用三种能力
"""


import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func, tuple_

from .clinical_read import clinical_query
from ..database.connection import engine
from ..database.models.cdm import (
    MedicalInsuranceSettlement,
    MedicalInsuranceSettlementCost,
    MedicalRecordFrontpage,
    Diagnosis,
    MrSurgery,
    MrCost,
)
from .settlement_formal_qc import SettlementFormalQCEngine, SettlementQCReport

logger = logging.getLogger(__name__)


def _to_str(val: Any) -> Optional[str]:
    """将 ORM 字段值转为字符串，None 保持 None。"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)


def _row_to_dict(row) -> dict:
    """将 ORM 实例转为 dict（排除 SA 内部属性）。"""
    d = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name, None)
        d[col.name] = _to_str(val)
    return d


class SettlementService:
    """医保结算清单数据服务。"""

    def __init__(self):
        self._qc_engine = SettlementFormalQCEngine()
        logger.info("SettlementService 初始化完成")

    # ==================== 列表查询 ====================

    def list_settlements(
        self,
        dept: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        查询结算清单列表（分页）。

        Returns:
            {"items": [...], "total": N, "page": P, "page_size": S}
        """
        with Session(engine) as session:
            q = clinical_query(session, MedicalInsuranceSettlement)

            if dept:
                q = q.filter(MedicalInsuranceSettlement.discharge_dept_name == dept)
            if keyword:
                kw = f"%{keyword}%"
                q = q.filter(
                    MedicalInsuranceSettlement.mr_no.like(kw)
                    | MedicalInsuranceSettlement.inpat_no.like(kw)
                )

            total = q.count()
            offset = (page - 1) * page_size
            rows = q.order_by(
                MedicalInsuranceSettlement.admission_datetime.desc()
            ).offset(offset).limit(page_size).all()

            # 批量查患者姓名（结算清单主表无姓名字段，需从 MR 表补充）
            keys = [(r.institute_id, r.patient_id, r.visit_id) for r in rows]
            name_map = {}
            if keys:
                mrs = clinical_query(
                    session,
                    MedicalRecordFrontpage.institute_id,
                    MedicalRecordFrontpage.patient_id,
                    MedicalRecordFrontpage.visit_id,
                    MedicalRecordFrontpage.name,
                    MedicalRecordFrontpage.sex,
                    MedicalRecordFrontpage.age_year,
                    MedicalRecordFrontpage.insurance_type,
                ).filter(
                    tuple_(
                        MedicalRecordFrontpage.institute_id,
                        MedicalRecordFrontpage.patient_id,
                        MedicalRecordFrontpage.visit_id,
                    ).in_(keys)
                ).all()
                for m in mrs:
                    name_map[(m.institute_id, m.patient_id, m.visit_id)] = {
                        "name": m.name or "",
                        "sex": m.sex or "",
                        "age": m.age_year or "",
                        "insurance": m.insurance_type or "",
                    }

            items = []
            for r in rows:
                key = (r.institute_id, r.patient_id, r.visit_id)
                patient = name_map.get(key, {})
                items.append({
                    "institute_id": r.institute_id,
                    "patient_id": r.patient_id,
                    "visit_id": r.visit_id,
                    "name": patient.get("name", ""),
                    "sex": patient.get("sex", ""),
                    "age": patient.get("age", ""),
                    "insurance": patient.get("insurance", ""),
                    "mr_no": r.mr_no or "",
                    "inpat_no": r.inpat_no or "",
                    "admission_dept": r.admission_dept_name or "",
                    "discharge_dept": r.discharge_dept_name or "",
                    "admission_date": _to_str(r.admission_datetime) or "",
                    "discharge_date": _to_str(r.discharge_datetime) or "",
                    "settlement_status": r.settlement_status or "待质控",
                    "medinsur_serial_no": r.medinsur_serial_no or "",
                })

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    # ==================== 详情查询 ====================

    def get_settlement_detail(
        self,
        patient_id: str,
        visit_id: str,
        institute_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        组装单条完整结算清单数据字典。

        从多表查询并组装：
        - medical_insurance_settlement（主表 98 字段）
        - mr（病案首页：补充姓名/性别/年龄等）
        - diagnosis（诊断列表）
        - mr_surgery（手术列表）
        - mr_cost（费用汇总）
        - medical_insurance_settlement_cost（费用明细）
        """
        with Session(engine) as session:
            # 1. 主表
            q = clinical_query(session, MedicalInsuranceSettlement).filter(
                MedicalInsuranceSettlement.patient_id == patient_id,
                MedicalInsuranceSettlement.visit_id == visit_id,
            )
            if institute_id:
                q = q.filter(MedicalInsuranceSettlement.institute_id == institute_id)
            settlement = q.first()

            if not settlement:
                return None

            inst_id = settlement.institute_id
            result = _row_to_dict(settlement)

            # 2. 从病案首页补充患者基本信息
            mr = clinical_query(session, MedicalRecordFrontpage).filter(
                MedicalRecordFrontpage.institute_id == inst_id,
                MedicalRecordFrontpage.patient_id == patient_id,
                MedicalRecordFrontpage.visit_id == visit_id,
            ).first()
            if mr:
                result["patient_name"] = mr.name
                result["patient_sex"] = mr.sex
                result["patient_age"] = mr.age_year
                result["patient_id_card"] = getattr(mr, "id_card", None)
                result["patient_birthday"] = _to_str(mr.birthday)
                result["patient_insurance_type"] = mr.insurance_type
                result["patient_nationality"] = mr.nationality
                result["patient_ethnicity"] = mr.ethnicity
                result["patient_marital_status"] = mr.marital_status
                result["attending_physician"] = getattr(mr, "attending_physician_sign", None)
                result["hospital_duration"] = mr.hospital_duration

            # 3. 诊断列表
            diags = clinical_query(session, Diagnosis).filter(
                Diagnosis.institute_id == inst_id,
                Diagnosis.patient_id == patient_id,
                Diagnosis.visit_id == visit_id,
            ).all()
            result["diagnoses"] = [
                {
                    "type": d.diagnosis_type,
                    "name": d.diagnosis_name,
                    "code": d.diagnosis_code,
                    "sequence": d.diagnosis_no,
                    "condition": d.admission_condition,
                }
                for d in diags
            ]

            # 4. 手术列表
            surgeries = clinical_query(session, MrSurgery).filter(
                MrSurgery.institute_id == inst_id,
                MrSurgery.patient_id == patient_id,
                MrSurgery.visit_id == visit_id,
            ).all()
            result["surgeries"] = [
                {
                    "name": s.surgery_name,
                    "code": s.surgery_code,
                    "date": _to_str(s.surgery_begin_datetime),
                    "level": s.surgical_level,
                    "surgeon": s.surgeon,
                    "sequence": s.surgery_id,
                }
                for s in surgeries
            ]

            # 5. 费用汇总（mr_cost）
            cost = clinical_query(session, MrCost).filter(
                MrCost.institute_id == inst_id,
                MrCost.patient_id == patient_id,
                MrCost.visit_id == visit_id,
            ).first()
            if cost:
                result["cost_summary"] = _row_to_dict(cost)

            # 6. 费用明细
            cost_items = clinical_query(session, MedicalInsuranceSettlementCost).filter(
                MedicalInsuranceSettlementCost.institute_id == inst_id,
                MedicalInsuranceSettlementCost.patient_id == patient_id,
                MedicalInsuranceSettlementCost.visit_id == visit_id,
            ).all()
            result["cost_details"] = [
                {
                    "item_id": c.medinsur_serial_item_id,
                    "charge": c.charge,
                    "type": c.type_of_medicalcharge,
                    "level": c.charge_item_level,
                    "class_a_amount": c.item_class_a_amount,
                    "class_b_amount": c.item_class_b_amount,
                    "own_pay_amount": c.item_own_pay_amount,
                    "other_amount": c.item_other_amount,
                }
                for c in cost_items
            ]

            return result

    # ==================== 质控 ====================

    def run_qc(
        self,
        patient_id: str,
        visit_id: str,
        institute_id: Optional[str] = None,
    ) -> Optional[dict]:
        """
        组装结算清单数据 → 执行 136 条质控规则 → 返回报告。

        Returns:
            {
                "summary": {"total": N, "passed": P, "failed": F, "pass_rate": "XX%"},
                "results": [...],
                "settlement": {...}  # 原始数据供前端展示
            }
        """
        settlement = self.get_settlement_detail(patient_id, visit_id, institute_id)
        if not settlement:
            return None

        report: SettlementQCReport = self._qc_engine.check(settlement)

        # 组装响应
        pass_rate = (
            f"{report.passed / report.total_rules * 100:.1f}%"
            if report.total_rules > 0
            else "0%"
        )

        results = []
        for r in report.results:
            results.append({
                "rule_id": r.rule_id,
                "field_name": r.field_name,
                "rule_name": r.rule_name,
                "passed": r.passed,
                "message": r.message,
                "severity": r.severity,
                "category": r.category,
                "affects_grouping": r.affects_grouping,
            })

        return {
            "summary": {
                "total": report.total_rules,
                "passed": report.passed,
                "failed": report.failed,
                "pass_rate": pass_rate,
            },
            "results": results,
            "settlement": settlement,
        }

    def get_rules_summary(self) -> dict:
        """返回质控规则摘要。"""
        return self._qc_engine.get_rules_summary()


# ==================== 单例 ====================
_settlement_service: Optional[SettlementService] = None


def get_settlement_service() -> SettlementService:
    """获取 SettlementService 单例。"""
    global _settlement_service
    if _settlement_service is None:
        _settlement_service = SettlementService()
    return _settlement_service
