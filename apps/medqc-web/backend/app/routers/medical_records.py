"""
病案数据 API 路由
连接 Repository 层，提供 workstation 前端所需的所有数据接口

路由前缀: /api/medical-records
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from datetime import date

from ..database.repository import get_repository

router = APIRouter(prefix="/api/medical-records", tags=["病案数据"])


# ==================== 患者/病案列表 ====================

@router.get("/list")
async def list_medical_records(
    dept: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号搜索"),
    start_date: Optional[date] = Query(None, description="入院开始日期"),
    end_date: Optional[date] = Query(None, description="出院截止日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """获取患者/病案列表（支持分页、筛选、搜索）"""
    repo = get_repository()
    result = repo.list_patients(
        dept=dept, keyword=keyword,
        start_date=start_date, end_date=end_date,
        page=page, page_size=page_size,
    )
    return result


# ==================== 病案首页（核心）====================

@router.get("/frontpage/{institute_id}/{patient_id}/{visit_id}")
async def get_frontpage(institute_id: str, patient_id: str, visit_id: str):
    """获取单条病案首页（含诊断、手术、费用）"""
    repo = get_repository()
    fp = repo.get_frontpage(institute_id, patient_id, visit_id)
    if not fp:
        raise HTTPException(status_code=404, detail="病案首页未找到")
    return fp


@router.get("/frontpage-by-mr/{mr_no}")
async def get_frontpage_by_mr_no(mr_no: str):
    """通过病案号获取病案首页（便捷接口）"""
    repo = get_repository()
    # 先查列表找到对应的 visit
    result = repo.list_patients(keyword=mr_no, page_size=1)
    if not result["items"]:
        raise HTTPException(status_code=404, detail="病案号未找到: " + mr_no)
    item = result["items"][0]
    fp = repo.get_frontpage(item["institute_id"], item["patient_id"], item["visit_id"])
    return fp


@router.put("/frontpage")
async def save_frontpage(data: dict):
    """保存/更新病案首页"""
    repo = get_repository()
    try:
        result = repo.save_frontpage(data)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 诊断 ====================

@router.get("/diagnoses/{institute_id}/{patient_id}/{visit_id}")
async def get_diagnoses(institute_id: str, patient_id: str, visit_id: str):
    """获取某次就诊的全部诊断"""
    repo = get_repository()
    return repo.get_diagnoses(institute_id, patient_id, visit_id)


# ==================== 手术 ====================

@router.get("/surgeries/{institute_id}/{patient_id}/{visit_id}")
async def get_surgeries(institute_id: str, patient_id: str, visit_id: str):
    """获取某次就诊的全部手术"""
    repo = get_repository()
    return repo.get_surgeries(institute_id, patient_id, visit_id)


# ==================== 费用 ====================

@router.get("/cost/{institute_id}/{patient_id}/{visit_id}")
async def get_cost(institute_id: str, patient_id: str, visit_id: str):
    """获取某次就诊的费用明细"""
    repo = get_repository()
    cost = repo.get_cost(institute_id, patient_id, visit_id)
    if not cost:
        raise HTTPException(status_code=404, detail="费用数据未找到")
    return cost


# ==================== 病历原文 ====================

@router.get("/record-content/{institute_id}/{patient_id}/{visit_id}")
async def get_record_content(
    institute_id: str, patient_id: str, visit_id: str,
    record_type: str = Query("admission", description="记录类型: admission/discharge"),
):
    """获取病历原文内容（供 AI 提取使用）"""
    repo = get_repository()
    content = repo.get_record_content(institute_id, patient_id, visit_id, record_type)
    if not content:
        raise HTTPException(status_code=404, detail="病历记录未找到")
    return {"content": content}


@router.get("/documents/{visit_id}")
async def get_documents(
    visit_id: str,
    mode: Optional[str] = Query(None, description="返回模式: 默认返回列表, concat=拼接全文"),
):
    """获取某次就诊的全部病历文书列表及内容（供前端预览使用）"""
    from ..database.connection import engine
    from sqlalchemy.orm import Session
    from sqlalchemy import text as sql_text

    # 定义需要查询的文书类型
    # 按病历实际排列顺序
    doc_types = [
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

    documents = []
    try:
        with Session(engine) as session:
            for table_name, label in doc_types:
                try:
                    rows = session.execute(sql_text(
                        f"SELECT record_content FROM {table_name} WHERE visit_id = :vid"
                    ), {"vid": visit_id}).mappings().all()

                    if rows:
                        for idx, row in enumerate(rows):
                            content = row.get("record_content") or ""
                            content_str = str(content).strip()
                            doc_label = label if len(rows) == 1 else f"{label} ({idx + 1})"
                            documents.append({
                                "type": table_name,
                                "label": doc_label,
                                "has_content": bool(content_str),
                                "content": content_str if content_str else None,
                                "length": len(content_str),
                            })
                    else:
                        documents.append({
                            "type": table_name,
                            "label": label,
                            "has_content": False,
                            "content": None,
                            "length": 0,
                        })
                except Exception:
                    # 表不存在时静默跳过
                    documents.append({
                        "type": table_name,
                        "label": label,
                        "has_content": False,
                        "content": None,
                        "length": 0,
                    })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询文书失败: {str(e)}")

    # concat 模式：拼接所有文书内容成完整病历
    if mode == "concat":
        sections = []
        for doc in documents:
            if doc["has_content"] and doc["content"]:
                sep = "=" * 40
                section = f"{sep}\n\U0001f4cb {doc['label']}\n{sep}\n\n{doc['content']}"
                sections.append(section)
        concat_text = "\n\n\n".join(sections)
        return {
            "visit_id": visit_id,
            "mode": "concat",
            "text": concat_text,
            "total_length": len(concat_text),
            "document_count": len([d for d in documents if d["has_content"]]),
        }

    return {"documents": documents, "visit_id": visit_id}


# ==================== 质控结果 ====================

@router.post("/qc-results")
async def save_qc_results(data: dict):
    """批量保存质控结果
    body: {"results": [{"institute_id":..., "patient_id":..., ...}]}
    """
    repo = get_repository()
    results = data.get("results", [])
    if not results:
        raise HTTPException(status_code=400, detail="results 不能为空")
    count = repo.save_qc_results(results)
    return {"success": True, "saved_count": count}


@router.get("/qc-results/{institute_id}/{patient_id}/{visit_id}")
async def get_qc_results(institute_id: str, patient_id: str, visit_id: str):
    """获取某次就诊的质控结果"""
    repo = get_repository()
    return repo.get_qc_results(institute_id, patient_id, visit_id)


# ==================== 统计 ====================

@router.get("/stats")
async def get_stats(
    dept: Optional[str] = Query(None, description="科室筛选"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    """获取统计概览"""
    repo = get_repository()
    return repo.get_stats(dept=dept, start_date=start_date, end_date=end_date)


# ==================== 科室列表 ====================

@router.get("/departments")
async def get_departments():
    """获取所有科室列表（从已有数据中提取）"""
    repo = get_repository()
    result = repo.list_patients(page_size=1000)
    depts = set()
    for item in result["items"]:
        dept = item.get("discharge_dept_name")
        if dept:
            depts.add(dept)
    return sorted(list(depts))


# ==================== V4 工作台（科室+卡片）====================

@router.get("/workstation")
async def get_workstation_data(
    dept: Optional[str] = Query(None, description="科室筛选，不传则返回全部"),
    keyword: Optional[str] = Query(None, description="搜索姓名/病案号"),
    page_size: int = Query(200, ge=1, le=1000, description="每页条数"),
):
    """V4 工作台专用接口 — 返回病案列表 + 科室统计 + 主诊断 + 床号"""
    from ..database.connection import engine
    from ..database.models.cdm import MedicalRecordFrontpage, Diagnosis, AdmissionRecord
    from sqlalchemy.orm import Session
    from sqlalchemy import func

    with Session(engine) as session:
        # 1. 查病案首页
        q = session.query(MedicalRecordFrontpage)
        if dept:
            q = q.filter(MedicalRecordFrontpage.discharge_dept_name == dept)
        if keyword:
            kw = f"%{keyword}%"
            q = q.filter(
                MedicalRecordFrontpage.name.like(kw) |
                MedicalRecordFrontpage.mr_no.like(kw) |
                MedicalRecordFrontpage.inpat_no.like(kw)
            )
        records = q.order_by(MedicalRecordFrontpage.admission_datetime.desc()).limit(page_size).all()

        # 2. 批量查主诊断
        pids = [(r.patient_id, r.visit_id) for r in records]
        diag_map = {}
        if pids:
            diags = session.query(Diagnosis).filter(
                Diagnosis.diagnosis_type == "出院主要诊断"
            ).all()
            for d in diags:
                diag_map[(d.patient_id, d.visit_id)] = {
                    "name": d.diagnosis_name,
                    "code": d.diagnosis_code,
                }

        # 3. 批量查床号
        bed_map = {}
        if pids:
            beds = session.query(
                AdmissionRecord.patient_id,
                AdmissionRecord.visit_id,
                AdmissionRecord.bed_no,
            ).all()
            for b in beds:
                bed_map[(b.patient_id, b.visit_id)] = b.bed_no

        # 4. 组装科室统计
        dept_stats = session.query(
            MedicalRecordFrontpage.discharge_dept_name,
            func.count().label("total"),
        ).group_by(MedicalRecordFrontpage.discharge_dept_name).all()

        departments = [{"name": "全部科室", "total": sum(d.total for d in dept_stats), "warningCount": 0}]
        for d in sorted(dept_stats, key=lambda x: x.total, reverse=True):
            departments.append({"name": d.discharge_dept_name, "total": d.total, "warningCount": 0})

        # 5. 组装响应
        items = []
        for r in records:
            key = (r.patient_id, r.visit_id)
            diag = diag_map.get(key, {})
            items.append({
                "id": r.visit_id,
                "instituteId": r.institute_id,
                "patientId": r.patient_id,
                "bedNo": bed_map.get(key, ""),
                "name": r.name or "",
                "sex": r.sex or "",
                "age": int(r.age_year) if r.age_year else 0,
                "insurance": r.insurance_type or "",
                "department": r.discharge_dept_name or r.admission_dept_name or "",
                "admissionDate": r.admission_datetime.strftime("%m-%d") if r.admission_datetime else "",
                "dischargeDate": r.discharge_datetime.strftime("%m-%d") if r.discharge_datetime else "",
                "days": int(r.hospital_duration) if r.hospital_duration else 0,
                "diagnosis": diag.get("name", ""),
                "diagnosisCode": diag.get("code", ""),
                "doctor": r.attending_physician_sign or "",
                "status": "completed",  # 后续接入质控状态
            })

    return {
        "departments": departments,
        "records": items,
        "total": len(items),
    }


# ==================== 表结构元数据 ====================

@router.get("/schema")
async def get_schema():
    """返回 CDM 所有表的结构元数据（字段名、类型、中文说明）"""
    from ..database.connection import Base

    TABLE_LABELS = {
        "patient_information": "患者信息",
        "inpat_registration": "入院登记",
        "mr": "病案首页",
        "mr_surgery": "手术明细",
        "mr_cost": "费用明细",
        "diagnosis": "诊断表",
        "admission_record": "入院记录",
        "discharge_record": "出院记录",
        "qc_result": "质控结果",
    }

    tables = []
    for table_name, table_obj in Base.metadata.tables.items():
        col_list = []
        for col in table_obj.columns:
            col_list.append({
                "name": col.name,
                "type": str(col.type),
                "comment": col.comment or "",
                "nullable": col.nullable,
                "primary_key": col.primary_key,
            })
        tables.append({
            "name": table_name,
            "label": TABLE_LABELS.get(table_name, table_name),
            "column_count": len(col_list),
            "columns": col_list,
        })

    return {"tables": tables, "total_tables": len(tables)}


@router.get("/table-data/{table_name}")
async def get_table_data(
    table_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """返回指定表的实际数据行（分页）"""
    from ..database.connection import Base, engine
    from sqlalchemy import select, func, text
    from sqlalchemy.orm import Session

    # 安全检查：只允许查询 CDM 表
    allowed = set(Base.metadata.tables.keys())
    if table_name not in allowed:
        raise HTTPException(status_code=404, detail=f"表不存在: {table_name}")

    table_obj = Base.metadata.tables[table_name]

    with Session(engine) as session:
        # 总数
        count_q = select(func.count()).select_from(table_obj)
        total = session.execute(count_q).scalar() or 0

        # 分页数据
        offset = (page - 1) * page_size
        data_q = select(table_obj).limit(page_size).offset(offset)
        rows = session.execute(data_q).fetchall()

        # 列名
        columns = [col.name for col in table_obj.columns]

        # 转换为 dict 列表（截断过长的文本字段）
        items = []
        for row in rows:
            item = {}
            for i, col_name in enumerate(columns):
                val = row[i]
                # 截断长文本，避免响应过大
                if isinstance(val, str) and len(val) > 200:
                    val = val[:200] + "..."
                item[col_name] = val
            items.append(item)

    return {
        "table_name": table_name,
        "total": total,
        "page": page,
        "page_size": page_size,
        "columns": columns,
        "items": items,
    }


# ==================== 病案首页官方格式数据 ====================

@router.get("/frontpage-sheet/{patient_id}/{visit_id}")
async def get_frontpage_sheet(patient_id: str, visit_id: str):
    """获取病案首页完整数据（基本信息+诊断+手术+费用），用于官方格式渲染"""
    from sqlalchemy.orm import Session
    from ..database.connection import engine
    from ..database.models.cdm import (
        MedicalRecordFrontpage, Diagnosis, MrSurgery, MrCost
    )

    with Session(engine) as session:
        # 1. 基本信息
        fp = session.query(MedicalRecordFrontpage).filter_by(
            patient_id=patient_id, visit_id=visit_id
        ).first()

        if not fp:
            raise HTTPException(status_code=404, detail="未找到病案首页数据")

        # 序列化基本信息
        basic = {}
        for col in MedicalRecordFrontpage.__table__.columns:
            val = getattr(fp, col.name, None)
            if val is not None:
                basic[col.name] = str(val)
            else:
                basic[col.name] = None

        # 2. 诊断列表
        diag_rows = session.query(Diagnosis).filter_by(
            patient_id=patient_id, visit_id=visit_id
        ).order_by(Diagnosis.diagnosis_type, Diagnosis.diagnosis_no).all()

        diagnoses = []
        for d in diag_rows:
            diagnoses.append({
                "diagnosis_type": d.diagnosis_type,
                "diagnosis_no": d.diagnosis_no,
                "diagnosis_name": d.diagnosis_name,
                "diagnosis_code": d.diagnosis_code,
                "admission_condition": d.admission_condition,
                "discharge_condition": d.discharge_condition,
            })

        # 3. 手术列表
        surg_rows = session.query(MrSurgery).filter_by(
            patient_id=patient_id, visit_id=visit_id
        ).all()

        surgeries = []
        for s in surg_rows:
            surgeries.append({
                "surgery_name": s.surgery_name,
                "surgery_code": s.surgery_code,
                "surgical_level": s.surgical_level,
                "surgery_begin_datetime": str(s.surgery_begin_datetime) if s.surgery_begin_datetime else None,
                "surgeon": s.surgeon,
                "first_assistant": s.first_assistant,
                "second_assistant": s.second_assistant,
                "anesthesia_method": s.anesthesia_method,
                "anesthesiologist": s.anesthesiologist,
                "surgial_incision_level": s.surgial_incision_level,
                "surgical_incisionheal_level": s.surgical_incisionheal_level,
                "main_surgery_sign": s.main_surgery_sign,
            })

        # 4. 费用
        cost_row = session.query(MrCost).filter_by(
            patient_id=patient_id, visit_id=visit_id
        ).first()

        cost_data = None
        if cost_row:
            cost_data = {}
            for col in MrCost.__table__.columns:
                val = getattr(cost_row, col.name, None)
                if val is not None:
                    cost_data[col.name] = str(val)
                else:
                    cost_data[col.name] = None

        return {
            "basic": basic,
            "diagnoses": diagnoses,
            "surgeries": surgeries,
            "cost": cost_data,
        }
