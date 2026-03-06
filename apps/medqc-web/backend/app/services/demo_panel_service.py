"""
演示面板数据服务

为 P4-P8 的前端面板提供后端数据接口：
- P5: 质控消息概览
- P7: 事中监控数据（DRG 预警、CMI 趋势、费用消耗指数）
- P8: 事后分析报告（KPI、DRG 分布、AI 洞察）

数据优先级：
1. 优先从 CDM 数据库查询真实数据
2. 数据库无数据或异常时降级到 Mock 数据
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, desc

logger = logging.getLogger(__name__)

# ---------- Mock 数据（降级用） ----------

_MOCK_DRG_ALERTS = [
    {"id": 1, "case_no": "#2026010101", "dept": "心内科",
     "diagnosis": "急性心肌梗死", "drg": "FM19", "ratio": 1.35,
     "status": "warning", "los": 12, "est_cost": 85000},
    {"id": 2, "case_no": "#2026010108", "dept": "神经外科",
     "diagnosis": "颅内动脉瘤", "drg": "IC15", "ratio": 1.28,
     "status": "warning", "los": 18, "est_cost": 125000},
    {"id": 3, "case_no": "#2026010115", "dept": "骨科",
     "diagnosis": "股骨颈骨折", "drg": "IB19", "ratio": 1.22,
     "status": "warning", "los": 15, "est_cost": 65000},
    {"id": 4, "case_no": "#2026010103", "dept": "骨科",
     "diagnosis": "腰椎间盘突出", "drg": "EB13", "ratio": 1.08,
     "status": "warning", "los": 8, "est_cost": 38000},
    {"id": 5, "case_no": "#2026010105", "dept": "神经内科",
     "diagnosis": "急性脑梗死", "drg": "BR23", "ratio": 1.05,
     "status": "warning", "los": 10, "est_cost": 42000},
    {"id": 6, "case_no": "#2026010112", "dept": "消化内科",
     "diagnosis": "上消化道出血", "drg": "GD21", "ratio": 1.03,
     "status": "warning", "los": 7, "est_cost": 28000},
    {"id": 7, "case_no": "#2026010102", "dept": "呼吸科",
     "diagnosis": "社区获得性肺炎", "drg": "BW15", "ratio": 0.92,
     "status": "normal", "los": 6, "est_cost": 18000},
    {"id": 8, "case_no": "#2026010104", "dept": "普外科",
     "diagnosis": "急性阑尾炎", "drg": "GD15", "ratio": 0.85,
     "status": "normal", "los": 4, "est_cost": 12000},
]

_MOCK_CMI_DATA = {
    "labels": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
    "values": [1.0, 1.05, 1.03, 1.08, 1.12, 1.09, 1.15],
    "benchmark": 1.0,
}

_MOCK_DEPT_COST = {
    "departments": ["心内科", "呼吸科", "骨科", "普外科",
                     "神经内科", "神经外科", "消化内科", "泌尿外科"],
    "values": [0.92, 0.89, 1.15, 0.85, 1.05, 1.28, 0.95, 0.88],
    "benchmark": 1.0,
}


class DemoPanelService:
    """演示面板数据服务（CDM 数据库优先 + Mock 降级）。"""

    # ===========================================
    # 辅助方法
    # ===========================================

    @staticmethod
    def _get_session():
        """获取数据库 session（容错：数据库不存在也不报错}。"""
        try:
            from ..database.connection import SessionLocal
            return SessionLocal()
        except Exception:
            return None

    @staticmethod
    def _safe_close(session):
        if session:
            try:
                session.close()
            except Exception:
                pass

    # ===========================================
    # P5: 质控消息概览
    # ===========================================

    def get_qc_message_summary(self) -> dict:
        """获取质控消息统计摘要。"""
        return {
            "total": 156,
            "by_severity": {
                "error": 23,
                "warning": 45,
                "info": 88,
            },
            "by_category": {
                "首页质控": 42,
                "编码质控": 35,
                "时限质控": 28,
                "内涵质控": 51,
            },
            "unread": 18,
            "today_new": 12,
        }

    def get_qc_messages(self, page: int = 1, limit: int = 20) -> dict:
        """获取质控消息列表。"""
        messages = [
            {
                "id": f"msg-{i:03d}",
                "title": title,
                "severity": severity,
                "category": category,
                "patient_name": name,
                "dept": dept,
                "created_at": (datetime.now() - timedelta(hours=i * 3)).isoformat(),
                "is_read": i > 5,
            }
            for i, (title, severity, category, name, dept) in enumerate([
                ("主诊断编码格式错误", "error", "编码质控", "张三", "心内科"),
                ("入院记录超48h未完成", "error", "时限质控", "李四", "骨科"),
                ("出院诊断与入院诊断不一致", "warning", "内涵质控", "王五", "呼吸科"),
                ("首页缺少手术编码", "error", "首页质控", "赵六", "普外科"),
                ("病程记录间隔超72h", "warning", "时限质控", "孙七", "神经内科"),
                ("诊断与性别不符", "error", "编码质控", "周八", "妇产科"),
                ("入院病情未填写", "info", "首页质控", "吴九", "消化内科"),
                ("手术记录不完整", "warning", "内涵质控", "郑十", "骨科"),
                ("主诊断选择不当(Z码)", "warning", "编码质控", "刘一", "内分泌科"),
                ("离院方式与诊断不一致", "error", "首页质控", "陈二", "心内科"),
                ("病理诊断未填写", "info", "首页质控", "黄三", "肿瘤科"),
                ("住院天数与日期不匹配", "warning", "首页质控", "林四", "呼吸科"),
            ], 1)
        ]

        total = len(messages)
        start = (page - 1) * limit
        end = start + limit
        return {
            "items": messages[start:end],
            "total": total,
            "page": page,
            "limit": limit,
        }

    # ===========================================
    # P7: 事中监控（CDM 数据库优先）
    # ===========================================

    def get_drg_alerts(self) -> List[dict]:
        """获取 DRG 预警列表 — 优先从数据库查询近期出院病例。"""
        session = self._get_session()
        if session is None:
            return _MOCK_DRG_ALERTS

        try:
            from ..database.models.cdm import MedicalRecordFrontpage, Diagnosis

            # 查询最近出院的病例
            records = (
                session.query(MedicalRecordFrontpage)
                .filter(MedicalRecordFrontpage.discharge_datetime.isnot(None))
                .order_by(desc(MedicalRecordFrontpage.discharge_datetime))
                .limit(20)
                .all()
            )

            if not records:
                logger.info("数据库无出院记录，使用 Mock 数据")
                return _MOCK_DRG_ALERTS

            alerts = []
            for idx, rec in enumerate(records, 1):
                # 查询主诊断
                main_diag = (
                    session.query(Diagnosis)
                    .filter(
                        Diagnosis.institute_id == rec.institute_id,
                        Diagnosis.patient_id == rec.patient_id,
                        Diagnosis.visit_id == rec.visit_id,
                        Diagnosis.diagnosis_type == "主诊断",
                    )
                    .first()
                )

                diag_name = main_diag.diagnosis_name if main_diag else "未知"
                diag_code = main_diag.diagnosis_code if main_diag else ""

                # 计算住院天数
                los = 0
                if rec.admission_datetime and rec.discharge_datetime:
                    los = (rec.discharge_datetime - rec.admission_datetime).days

                # 简单模拟费用消耗比（真实环境需要 DRG 分组后计算）
                ratio = round(0.8 + (idx % 5) * 0.12, 2)

                alerts.append({
                    "id": idx,
                    "case_no": f"#{rec.inpat_no or rec.patient_id}",
                    "dept": rec.discharge_dept_name or rec.admission_dept_name or "未知科室",
                    "diagnosis": diag_name,
                    "drg": diag_code[:4].upper() if diag_code else "待分组",
                    "ratio": ratio,
                    "status": "warning" if ratio > 1.0 else "normal",
                    "los": los,
                    "est_cost": 0,
                })

            return alerts

        except Exception as e:
            logger.warning(f"查询 DRG 预警失败，降级到 Mock: {e}")
            return _MOCK_DRG_ALERTS
        finally:
            self._safe_close(session)

    def get_cmi_trend(self, days: int = 7) -> dict:
        """获取 CMI 趋势数据 — 优先从数据库计算。"""
        session = self._get_session()
        if session is None:
            return _MOCK_CMI_DATA

        try:
            from ..database.models.cdm import MedicalRecordFrontpage

            now = datetime.now()
            labels = []
            values = []

            for i in range(days):
                d = now - timedelta(days=days - 1 - i)
                day_start = d.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)

                # 查询当日出院的病例数
                count = (
                    session.query(func.count(MedicalRecordFrontpage.patient_id))
                    .filter(
                        MedicalRecordFrontpage.discharge_datetime >= day_start,
                        MedicalRecordFrontpage.discharge_datetime < day_end,
                    )
                    .scalar()
                ) or 0

                labels.append(d.strftime("%m/%d"))
                # 简单的 CMI 近似（真实 CMI 需要 DRG 权重）
                # 这里用出院量的对数变化来模拟趋势
                values.append(round(1.0 + count * 0.005, 2) if count > 0 else 1.0)

            if all(v == 1.0 for v in values):
                # 全为 1.0 说明数据库没有数据
                return _MOCK_CMI_DATA

            return {
                "labels": labels,
                "values": values,
                "benchmark": 1.0,
            }

        except Exception as e:
            logger.warning(f"查询 CMI 趋势失败，降级到 Mock: {e}")
            return _MOCK_CMI_DATA
        finally:
            self._safe_close(session)

    def get_dept_cost_index(self) -> dict:
        """获取各科室费用消耗指数 — 优先从数据库聚合。"""
        session = self._get_session()
        if session is None:
            return _MOCK_DEPT_COST

        try:
            from ..database.models.cdm import MedicalRecordFrontpage, MrCost

            # 按出院科室统计平均费用
            results = (
                session.query(
                    MedicalRecordFrontpage.discharge_dept_name,
                    func.count(MedicalRecordFrontpage.patient_id).label("cnt"),
                    func.avg(
                        func.cast(MrCost.total_fee, float)
                    ).label("avg_cost"),
                )
                .join(
                    MrCost,
                    (MedicalRecordFrontpage.institute_id == MrCost.institute_id) &
                    (MedicalRecordFrontpage.patient_id == MrCost.patient_id) &
                    (MedicalRecordFrontpage.visit_id == MrCost.visit_id),
                    isouter=True,
                )
                .filter(MedicalRecordFrontpage.discharge_dept_name.isnot(None))
                .group_by(MedicalRecordFrontpage.discharge_dept_name)
                .order_by(desc("cnt"))
                .limit(10)
                .all()
            )

            if not results or len(results) < 2:
                return _MOCK_DEPT_COST

            # 计算全院平均费用作为标杆
            all_avg = sum(r.avg_cost or 0 for r in results) / len(results) if results else 1
            if all_avg == 0:
                all_avg = 1

            departments = []
            values = []
            for r in results:
                dept = r.discharge_dept_name or "未知"
                avg = r.avg_cost or 0
                departments.append(dept)
                values.append(round(avg / all_avg, 2) if all_avg else 1.0)

            return {
                "departments": departments,
                "values": values,
                "benchmark": 1.0,
            }

        except Exception as e:
            logger.warning(f"查询科室费用指数失败，降级到 Mock: {e}")
            return _MOCK_DEPT_COST
        finally:
            self._safe_close(session)

    def get_monitoring_stats(self) -> dict:
        """获取事中监控统计卡片数据。"""
        alerts = self.get_drg_alerts()
        return {
            "total_alerts": len(alerts),
            "severe_alerts": sum(1 for a in alerts if a.get("ratio", 0) > 1.2),
            "pending_suggestions": 8,
            "today_new": 15,
        }

    # ===========================================
    # P8: 事后分析（CDM 数据库优先）
    # ===========================================

    def get_post_analysis_kpis(self) -> List[dict]:
        """获取事后分析 KPI 卡片 — 优先从数据库统计。"""
        session = self._get_session()
        kpis_from_db = False

        if session:
            try:
                from ..database.models.cdm import MedicalRecordFrontpage

                total = session.query(func.count(MedicalRecordFrontpage.patient_id)).scalar() or 0

                if total > 0:
                    avg_los_result = (
                        session.query(func.avg(MedicalRecordFrontpage.actual_hospitalized_day))
                        .filter(MedicalRecordFrontpage.actual_hospitalized_day.isnot(None))
                        .scalar()
                    )
                    avg_los = round(float(avg_los_result or 0), 1)

                    kpis_from_db = True
                    return [
                        {"name": "总病例数", "value": total, "unit": "例",
                         "trend": "", "trend_type": "up"},
                        {"name": "平均住院日", "value": avg_los, "unit": "天",
                         "trend": "", "trend_type": "down"},
                        {"name": "CMI 值", "value": 1.05, "unit": "",
                         "trend": "+0.03", "trend_type": "up"},
                        {"name": "低风险组死亡率", "value": 0.02, "unit": "%",
                         "trend": "-0.01", "trend_type": "down"},
                        {"name": "入组率", "value": 98.5, "unit": "%",
                         "trend": "+0.5", "trend_type": "up"},
                        {"name": "费用消耗指数", "value": 0.95, "unit": "",
                         "trend": "-0.02", "trend_type": "down"},
                    ]

            except Exception as e:
                logger.warning(f"查询 KPI 失败: {e}")
            finally:
                self._safe_close(session)

        if not kpis_from_db:
            return [
                {"name": "总病例数", "value": 1256, "unit": "例",
                 "trend": "+12%", "trend_type": "up"},
                {"name": "平均住院日", "value": 8.2, "unit": "天",
                 "trend": "-0.3", "trend_type": "down"},
                {"name": "CMI 值", "value": 1.05, "unit": "",
                 "trend": "+0.03", "trend_type": "up"},
                {"name": "低风险组死亡率", "value": 0.02, "unit": "%",
                 "trend": "-0.01", "trend_type": "down"},
                {"name": "入组率", "value": 98.5, "unit": "%",
                 "trend": "+0.5", "trend_type": "up"},
                {"name": "费用消耗指数", "value": 0.95, "unit": "",
                 "trend": "-0.02", "trend_type": "down"},
            ]

    def get_post_analysis_report(self) -> dict:
        """获取事后分析报告。"""
        return {
            "summary": {
                "period": "2025年12月",
                "total_cases": 1256,
                "total_drg_groups": 89,
                "avg_los": 8.2,
                "cmi": 1.05,
            },
            "drg_distribution": [
                {"drg": "FM19", "name": "心脏介入手术", "count": 45, "avg_cost": 82000},
                {"drg": "BW15", "name": "呼吸道感染", "count": 38, "avg_cost": 18000},
                {"drg": "EB13", "name": "脊柱手术", "count": 32, "avg_cost": 45000},
                {"drg": "GD15", "name": "腹部手术", "count": 28, "avg_cost": 15000},
                {"drg": "BR23", "name": "脑血管疾病", "count": 25, "avg_cost": 42000},
            ],
            "ai_insights": [
                "心内科 CMI 持续上升趋势，建议关注高值耗材使用情况",
                "骨科费用消耗指数超标 15%，主要原因为人工关节耗材成本上升",
                "神经外科平均住院日偏高，建议优化术后康复流程",
                "呼吸科入组率 99.2%，为全院最佳，建议推广其病历规范化经验",
                "低风险组死亡率持续下降，质控效果显著",
            ],
        }
