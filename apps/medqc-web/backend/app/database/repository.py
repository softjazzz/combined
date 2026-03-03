"""
数据访问抽象层（Repository Pattern）

设计目标：
- SQLite（测试）和 MongoDB API（生产）共用同一套接口
- 上层业务代码和路由不关心数据从哪来
- 切换数据源只需改 DATA_SOURCE 配置

使用方式：
    from app.database.repository import get_repository
    repo = get_repository()
    patients = repo.list_frontpages(dept="内科")
"""

import os
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import date, datetime


# ==================== 数据传输对象 ====================
# 用 dict 做 DTO，兼容 SQLAlchemy 和 MongoDB API 两种来源

class MedicalRecordRepository(ABC):
    """病案数据访问接口 - 所有实现必须遵循此接口"""

    # ---------- 患者列表 ----------
    @abstractmethod
    def list_patients(
        self,
        dept: Optional[str] = None,
        keyword: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """查询患者/就诊列表
        Returns: {"total": int, "items": [dict], "page": int, "page_size": int}
        """
        ...

    # ---------- 病案首页 ----------
    @abstractmethod
    def get_frontpage(self, institute_id: str, patient_id: str, visit_id: str) -> Optional[Dict]:
        """获取单条病案首页（含诊断、手术、费用）"""
        ...

    @abstractmethod
    def save_frontpage(self, data: Dict) -> Dict:
        """保存/更新病案首页"""
        ...

    # ---------- 诊断 ----------
    @abstractmethod
    def get_diagnoses(self, institute_id: str, patient_id: str, visit_id: str) -> List[Dict]:
        """获取某次就诊的全部诊断"""
        ...

    # ---------- 手术 ----------
    @abstractmethod
    def get_surgeries(self, institute_id: str, patient_id: str, visit_id: str) -> List[Dict]:
        """获取某次就诊的全部手术"""
        ...

    # ---------- 费用 ----------
    @abstractmethod
    def get_cost(self, institute_id: str, patient_id: str, visit_id: str) -> Optional[Dict]:
        """获取某次就诊的费用明细"""
        ...

    # ---------- 病历原文 ----------
    @abstractmethod
    def get_record_content(self, institute_id: str, patient_id: str, visit_id: str,
                           record_type: str = "admission") -> Optional[str]:
        """获取病历原文内容（入院记录/出院记录）"""
        ...

    # ---------- 质控结果 ----------
    @abstractmethod
    def save_qc_results(self, results: List[Dict]) -> int:
        """批量保存质控结果，返回保存数量"""
        ...

    @abstractmethod
    def get_qc_results(self, institute_id: str, patient_id: str, visit_id: str) -> List[Dict]:
        """获取某次就诊的质控结果"""
        ...

    # ---------- 统计 ----------
    @abstractmethod
    def get_stats(self, dept: Optional[str] = None,
                  start_date: Optional[date] = None,
                  end_date: Optional[date] = None) -> Dict:
        """获取统计概览"""
        ...


# ==================== SQLite 实现 ====================

class SqliteRepository(MedicalRecordRepository):
    """SQLite 实现 - 开发/测试用"""

    def __init__(self):
        from .connection import SessionLocal
        self._session_factory = SessionLocal

    def _to_dict(self, obj) -> Dict:
        """ORM 对象转 dict"""
        if obj is None:
            return {}
        d = {}
        for col in obj.__table__.columns:
            val = getattr(obj, col.name)
            if isinstance(val, (datetime, date)):
                val = val.isoformat() if val else None
            d[col.name] = val
        return d

    def list_patients(self, dept=None, keyword=None, start_date=None, end_date=None,
                      page=1, page_size=20) -> Dict[str, Any]:
        from .models.cdm import MedicalRecordFrontpage
        session = self._session_factory()
        try:
            q = session.query(MedicalRecordFrontpage)
            if dept:
                q = q.filter(MedicalRecordFrontpage.discharge_dept_name == dept)
            if keyword:
                q = q.filter(MedicalRecordFrontpage.name.contains(keyword))
            if start_date:
                q = q.filter(MedicalRecordFrontpage.admission_datetime >= datetime.combine(start_date, datetime.min.time()))
            if end_date:
                q = q.filter(MedicalRecordFrontpage.discharge_datetime <= datetime.combine(end_date, datetime.max.time()))

            total = q.count()
            items = q.order_by(MedicalRecordFrontpage.admission_datetime.desc()) \
                     .offset((page - 1) * page_size).limit(page_size).all()

            return {
                "total": total,
                "items": [self._to_dict(item) for item in items],
                "page": page,
                "page_size": page_size,
            }
        finally:
            session.close()

    def get_frontpage(self, institute_id, patient_id, visit_id) -> Optional[Dict]:
        from .models.cdm import MedicalRecordFrontpage, Diagnosis, MrSurgery, MrCost
        session = self._session_factory()
        try:
            fp = session.query(MedicalRecordFrontpage).filter_by(
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id
            ).first()
            if not fp:
                return None

            result = self._to_dict(fp)

            # 附加诊断
            diags = session.query(Diagnosis).filter_by(
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id
            ).order_by(Diagnosis.diagnosis_no).all()
            result["diagnoses"] = [self._to_dict(d) for d in diags]

            # 附加手术
            surgs = session.query(MrSurgery).filter_by(
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id
            ).all()
            result["surgeries"] = [self._to_dict(s) for s in surgs]

            # 附加费用
            cost = session.query(MrCost).filter_by(
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id
            ).first()
            result["cost"] = self._to_dict(cost) if cost else None

            return result
        finally:
            session.close()

    def save_frontpage(self, data: Dict) -> Dict:
        from .models.cdm import MedicalRecordFrontpage
        session = self._session_factory()
        try:
            keys = {
                "institute_id": data["institute_id"],
                "patient_id": data["patient_id"],
                "visit_id": data["visit_id"],
            }
            existing = session.query(MedicalRecordFrontpage).filter_by(**keys).first()
            if existing:
                for k, v in data.items():
                    if hasattr(existing, k) and k not in ("institute_id", "patient_id", "visit_id"):
                        setattr(existing, k, v)
            else:
                existing = MedicalRecordFrontpage(**data)
                session.add(existing)
            session.commit()
            return self._to_dict(existing)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_diagnoses(self, institute_id, patient_id, visit_id) -> List[Dict]:
        from .models.cdm import Diagnosis
        session = self._session_factory()
        try:
            items = session.query(Diagnosis).filter_by(
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id
            ).order_by(Diagnosis.diagnosis_no).all()
            return [self._to_dict(d) for d in items]
        finally:
            session.close()

    def get_surgeries(self, institute_id, patient_id, visit_id) -> List[Dict]:
        from .models.cdm import MrSurgery
        session = self._session_factory()
        try:
            items = session.query(MrSurgery).filter_by(
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id
            ).all()
            return [self._to_dict(s) for s in items]
        finally:
            session.close()

    def get_cost(self, institute_id, patient_id, visit_id) -> Optional[Dict]:
        from .models.cdm import MrCost
        session = self._session_factory()
        try:
            cost = session.query(MrCost).filter_by(
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id
            ).first()
            return self._to_dict(cost) if cost else None
        finally:
            session.close()

    def get_record_content(self, institute_id, patient_id, visit_id,
                           record_type="admission") -> Optional[str]:
        from .models.cdm import AdmissionRecord, DischargeRecord
        session = self._session_factory()
        try:
            Model = AdmissionRecord if record_type == "admission" else DischargeRecord
            record = session.query(Model).filter_by(
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id
            ).first()
            return record.record_content if record else None
        finally:
            session.close()

    def save_qc_results(self, results: List[Dict]) -> int:
        from .models.cdm import QCResult
        session = self._session_factory()
        try:
            objs = [QCResult(**r) for r in results]
            session.add_all(objs)
            session.commit()
            return len(objs)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_qc_results(self, institute_id, patient_id, visit_id) -> List[Dict]:
        from .models.cdm import QCResult
        session = self._session_factory()
        try:
            items = session.query(QCResult).filter_by(
                institute_id=institute_id, patient_id=patient_id, visit_id=visit_id
            ).order_by(QCResult.created_at.desc()).all()
            return [self._to_dict(q) for q in items]
        finally:
            session.close()

    def get_stats(self, dept=None, start_date=None, end_date=None) -> Dict:
        from .models.cdm import MedicalRecordFrontpage, QCResult
        from sqlalchemy import func
        session = self._session_factory()
        try:
            q = session.query(func.count(MedicalRecordFrontpage.visit_id))
            if dept:
                q = q.filter(MedicalRecordFrontpage.discharge_dept_name == dept)
            total_records = q.scalar() or 0

            total_qc = session.query(func.count(QCResult.id)).scalar() or 0
            open_qc = session.query(func.count(QCResult.id)).filter(QCResult.status == "open").scalar() or 0

            return {
                "total_records": total_records,
                "total_qc_issues": total_qc,
                "open_qc_issues": open_qc,
                "resolved_qc_issues": total_qc - open_qc,
            }
        finally:
            session.close()


# ==================== MongoDB API 实现（骨架）====================

class MongoApiRepository(MedicalRecordRepository):
    """MongoDB API 实现 - 生产用，对接医院真实 API

    TODO: 对接真实 MongoDB API 时实现以下方法
    预期 API 格式参考 CDM V1.0 字段命名
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key

    def list_patients(self, **kwargs):
        raise NotImplementedError("MongoDB API 对接待实现")

    def get_frontpage(self, institute_id, patient_id, visit_id):
        raise NotImplementedError("MongoDB API 对接待实现")

    def save_frontpage(self, data):
        raise NotImplementedError("MongoDB API 对接待实现")

    def get_diagnoses(self, institute_id, patient_id, visit_id):
        raise NotImplementedError("MongoDB API 对接待实现")

    def get_surgeries(self, institute_id, patient_id, visit_id):
        raise NotImplementedError("MongoDB API 对接待实现")

    def get_cost(self, institute_id, patient_id, visit_id):
        raise NotImplementedError("MongoDB API 对接待实现")

    def get_record_content(self, institute_id, patient_id, visit_id, record_type="admission"):
        raise NotImplementedError("MongoDB API 对接待实现")

    def save_qc_results(self, results):
        raise NotImplementedError("MongoDB API 对接待实现")

    def get_qc_results(self, institute_id, patient_id, visit_id):
        raise NotImplementedError("MongoDB API 对接待实现")

    def get_stats(self, **kwargs):
        raise NotImplementedError("MongoDB API 对接待实现")


# ==================== 工厂函数 ====================

_repo_instance: Optional[MedicalRecordRepository] = None


def get_repository() -> MedicalRecordRepository:
    """获取 Repository 单例

    通过 DATA_SOURCE 环境变量切换:
    - sqlite（默认）: 使用本地 SQLite
    - mongo_api: 对接 MongoDB API
    """
    global _repo_instance
    if _repo_instance is None:
        source = os.getenv("DATA_SOURCE", "sqlite").lower()
        if source == "mongo_api":
            mongo_url = os.getenv("MONGO_API_URL", "http://localhost:8080")
            mongo_key = os.getenv("MONGO_API_KEY")
            _repo_instance = MongoApiRepository(base_url=mongo_url, api_key=mongo_key)
        else:
            _repo_instance = SqliteRepository()
    return _repo_instance
