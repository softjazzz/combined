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
