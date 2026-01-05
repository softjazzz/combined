from __future__ import annotations

from typing import Any, Dict, List, Optional
import io
import logging

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import pandas as pd

from ..services.drg_demo_store import get_demo_drg_store
from ..services import drg_batch_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/drg", tags=["drg"])


class DRGPredictRequest(BaseModel):
    admission_id: str
    region: Optional[str] = None


class HandleSuggestionRequest(BaseModel):
    suggestion_id: int
    action: str  # accept / reject
    handled_by: Optional[str] = None


class HandleAlertRequest(BaseModel):
    alert_id: int
    action: str  # acknowledge / resolve
    handled_by: Optional[str] = None


@router.post("/predict")
async def predict_drg_grouping(payload: DRGPredictRequest) -> Dict[str, Any]:
    from ..services.drg_grouping_service import get_drg_grouping_service
    
    store = get_demo_drg_store()
    case = store.get_case_detail(payload.admission_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"未找到住院号 {payload.admission_id} 的病案首页")

    # 从病案首页提取分组所需信息
    primary_diagnosis = case.get("principal_diagnosis_code", "I10.x00")
    secondary_diagnoses = case.get("secondary_diagnosis_codes", [])
    procedures = case.get("procedure_codes", [])
    patient_age = case.get("patient_age", 58)
    patient_gender = case.get("patient_gender", "M")
    los = case.get("hospital_days", 7)
    total_cost = float(case.get("total_cost") or 0.0)
    
    # 调用真实 DRG 分组 API
    service = get_drg_grouping_service()
    result = await service.group_drg(
        primary_diagnosis=primary_diagnosis,
        secondary_diagnoses=secondary_diagnoses,
        procedures=procedures,
        patient_age=patient_age,
        patient_gender=patient_gender,
        los=los,
        city_name=payload.region or "四川省",
        total_fee=total_cost
    )
    
    # 计算盈亏
    baseline_payment = result.get("baseline_payment", 0)
    profit_margin = round((baseline_payment - total_cost) / baseline_payment, 4) if baseline_payment else 0.0
    result["actual_cost"] = total_cost
    result["profit_margin"] = profit_margin
    
    # 记录分组历史
    store.append_grouping_history(payload.admission_id, result)

    return {"data": result, "message": "分组成功" if result.get("success") else "分组失败（降级模式）"}


@router.get("/grouping/{admission_id}/history")
async def get_grouping_history(admission_id: str) -> Dict[str, Any]:
    store = get_demo_drg_store()
    history = store.get_grouping_history(admission_id)
    return {"history": history, "total": len(history)}


@router.get("/suggestions")
async def list_coding_suggestions(
    admission_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    store = get_demo_drg_store()
    items = store.list_suggestions(admission_id=admission_id, status=status, limit=limit)
    return {"suggestions": items, "total": len(items)}


@router.post("/suggestions/handle")
async def handle_coding_suggestion(payload: HandleSuggestionRequest) -> Dict[str, Any]:
    store = get_demo_drg_store()
    new_status = "accepted" if payload.action == "accept" else "rejected"
    ok = store.update_suggestion_status(payload.suggestion_id, new_status)
    if not ok:
        raise HTTPException(status_code=404, detail="建议未找到或更新失败")
    return {"success": True, "message": "建议已处理"}


@router.get("/alerts")
async def get_drg_alerts(
    admission_id: Optional[str] = Query(None),
    alert_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    store = get_demo_drg_store()
    items = store.list_alerts(admission_id=admission_id, alert_level=alert_level, status=status, limit=limit)
    return {"alerts": items, "total": len(items)}


@router.post("/alerts/handle")
async def handle_drg_alert(payload: HandleAlertRequest) -> Dict[str, Any]:
    store = get_demo_drg_store()
    new_status = "acknowledged" if payload.action == "acknowledge" else "resolved"
    ok = store.update_alert_status(payload.alert_id, new_status)
    if not ok:
        raise HTTPException(status_code=404, detail="预警未找到或更新失败")
    return {"success": True, "message": "预警已处理"}


@router.get("/demo/story-cases")
async def get_demo_story_cases() -> Dict[str, Any]:
    store = get_demo_drg_store()
    cases = store.story_cases
    if not cases:
        return {"cases": []}
    return {
        "cases": [
            {"name": "高风险亏损", "admission_id": cases.high_risk_loss},
            {"name": "编码冲突", "admission_id": cases.coding_conflict},
            {"name": "高费用预警", "admission_id": cases.high_cost_alert},
        ]
    }


# ============================================================================
# 批量上传和统计分析 API
# ============================================================================

# Excel 列名映射
COLUMN_MAPPING = {
    '病案号': 'admission_id',
    '性别': 'gender',
    '年龄': 'age',
    '年龄天数': 'age_day',
    '出生体重': 'weight',
    '科室代码': 'department',
    '科室名称': 'department_name',
    '住院天数': 'los',
    '离院方式': 'leaving_type',
    '入院日期': 'admission_date',
    '出院日期': 'discharge_date',
    '诊断列表': 'diagnosis_codes',
    '手术操作列表': 'procedure_codes',
    '总费用': 'total_cost',
    '医保支付': 'insurance_payment',
    '主管医生': 'doctor',
    '药品费': 'drug_cost',
    '耗材费': 'material_cost',
    '检查费': 'exam_cost',
    '治疗费': 'treatment_cost',
}


@router.post("/batch-upload")
async def batch_upload_drg(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    批量上传 Excel/CSV 文件进行 DRG 分组
    
    支持的列：病案号, 性别, 年龄, 住院天数, 离院方式, 诊断列表, 手术操作列表, 总费用 等
    """
    from ..services.drg_grouping_service import get_drg_grouping_service
    
    try:
        # 读取文件
        contents = await file.read()
        file_ext = file.filename.rsplit('.', 1)[-1].lower() if file.filename else 'xlsx'
        
        if file_ext == 'csv':
            df = pd.read_csv(io.BytesIO(contents), encoding='utf-8-sig')
        elif file_ext in ['xlsx', 'xls']:
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(status_code=400, detail="不支持的文件格式，请上传 CSV 或 Excel 文件")
        
        # 列名映射
        df = df.rename(columns=COLUMN_MAPPING)
        
        # 生成批次ID
        batch_id = drg_batch_store.generate_batch_id()
        
        # 获取分组服务
        grouping_service = get_drg_grouping_service()
        
        results = []
        success_count = 0
        failed_count = 0
        
        for idx, row in df.iterrows():
            try:
                # 提取字段
                admission_id = str(row.get('admission_id', f'ROW_{idx}'))
                gender = int(row.get('gender', 1))
                age = int(row.get('age', 0))
                los = int(row.get('los', 1))
                total_cost = float(row.get('total_cost', 0) or 0)
                
                # 诊断和手术
                diagnosis_codes = str(row.get('diagnosis_codes', ''))
                procedure_codes = str(row.get('procedure_codes', '') or '')
                
                # 解析诊断
                diagnoses = [d.strip() for d in diagnosis_codes.split('|') if d.strip()]
                primary_diagnosis = diagnoses[0] if diagnoses else 'Z53.900'
                secondary_diagnoses = diagnoses[1:] if len(diagnoses) > 1 else []
                
                # 解析手术
                procedures = [p.strip() for p in procedure_codes.split('|') if p.strip()]
                
                # 调用分组 API
                drg_result = await grouping_service.group_drg(
                    primary_diagnosis=primary_diagnosis,
                    secondary_diagnoses=secondary_diagnoses,
                    procedures=procedures,
                    patient_age=age,
                    patient_gender='M' if gender == 1 else 'F',
                    los=los,
                    city_name="四川省",
                    total_fee=total_cost
                )
                
                # 计算盈亏
                baseline_payment = drg_result.get('baseline_payment', 0)
                profit_margin = round(baseline_payment - total_cost, 2) if baseline_payment else 0
                
                # 保存到数据库
                record_data = {
                    'batch_id': batch_id,
                    'admission_id': admission_id,
                    'gender': gender,
                    'age': age,
                    'age_day': row.get('age_day'),
                    'weight': row.get('weight'),
                    'department': row.get('department'),
                    'department_name': row.get('department_name'),
                    'los': los,
                    'leaving_type': row.get('leaving_type'),
                    'admission_date': row.get('admission_date'),
                    'discharge_date': row.get('discharge_date'),
                    'diagnosis_codes': diagnosis_codes,
                    'procedure_codes': procedure_codes,
                    'total_cost': total_cost,
                    'insurance_payment': row.get('insurance_payment'),
                    'drug_cost': row.get('drug_cost'),
                    'material_cost': row.get('material_cost'),
                    'exam_cost': row.get('exam_cost'),
                    'treatment_cost': row.get('treatment_cost'),
                    'doctor': row.get('doctor'),
                    'mdc': drg_result.get('adrg_code', '')[:4] if drg_result.get('adrg_code') else None,
                    'adrg': drg_result.get('adrg_code'),
                    'drg': drg_result.get('drg_code'),
                    'drg_weight': drg_result.get('weight'),
                    'baseline_payment': baseline_payment,
                    'profit_margin': profit_margin,
                    'status': '分组成功' if drg_result.get('success') else '分组失败',
                    'messages': drg_result.get('grouping_logic', '')
                }
                
                drg_batch_store.save_batch_record(record_data)
                success_count += 1
                
                results.append({
                    'admission_id': admission_id,
                    'drg': drg_result.get('drg_code'),
                    'status': '成功',
                    'profit': profit_margin
                })
                
            except Exception as e:
                failed_count += 1
                results.append({
                    'admission_id': str(row.get('admission_id', f'ROW_{idx}')),
                    'error': str(e),
                    'status': '失败'
                })
                logger.error(f"处理行 {idx} 失败: {e}")
        
        return {
            "success": True,
            "batch_id": batch_id,
            "total_records": len(df),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results[:100]  # 只返回前100条结果
        }
        
    except Exception as e:
        logger.error(f"批量上传处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量处理失败: {str(e)}")


@router.get("/statistics")
async def get_drg_statistics(
    batch_id: Optional[str] = Query(None, description="批次ID"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    department: Optional[str] = Query(None, description="科室代码"),
    doctor: Optional[str] = Query(None, description="医生姓名"),
) -> Dict[str, Any]:
    """
    获取 DRG 统计数据
    
    返回：MDC分布、DRG Top-10、科室统计、医师统计、每日趋势、费用结构
    """
    try:
        stats = drg_batch_store.get_statistics(
            batch_id=batch_id,
            start_date=start_date,
            end_date=end_date,
            department=department,
            doctor=doctor
        )
        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drill-down")
async def drg_drill_down(
    dimension: str = Query(..., description="钻取维度: department/doctor/drg/mdc"),
    value: str = Query(..., description="维度值"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    batch_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    钻取查询明细
    
    点击图表后获取具体病例列表
    """
    try:
        records, total = drg_batch_store.drill_down(
            dimension=dimension,
            value=value,
            page=page,
            per_page=per_page,
            batch_id=batch_id
        )
        return {
            "success": True,
            "data": {
                "records": records,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            }
        }
    except Exception as e:
        logger.error(f"钻取查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batches")
async def list_batches() -> Dict[str, Any]:
    """获取所有批次列表"""
    try:
        batches = drg_batch_store.get_batch_list()
        return {"success": True, "data": batches}
    except Exception as e:
        logger.error(f"获取批次列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/template")
async def download_template() -> StreamingResponse:
    """下载 Excel 模板"""
    template_data = {
        '病案号': ['22058878', '22058879'],
        '性别': [2, 1],
        '年龄': [88, 65],
        '年龄天数': ['', ''],
        '出生体重': ['', ''],
        '科室代码': ['13040503', '13040501'],
        '科室名称': ['心内科', '心内科'],
        '住院天数': [94, 15],
        '离院方式': [1, 1],
        '入院日期': ['2024-01-01', '2024-01-05'],
        '出院日期': ['2024-04-04', '2024-01-20'],
        '诊断列表': ['K22.301|K11.901|E11.900|I10.x05', 'I21.001|E11.900|I10.x05'],
        '手术操作列表': ['96.0800x005', '36.0600'],
        '总费用': [85000.00, 45000.00],
        '医保支付': [68000.00, 36000.00],
        '主管医生': ['张三', '李四'],
        '药品费': [25000.00, 15000.00],
        '耗材费': [30000.00, 20000.00],
        '检查费': [10000.00, 5000.00],
        '治疗费': [20000.00, 5000.00],
    }
    
    df = pd.DataFrame(template_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='DRG批量上传模板')
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=drg_batch_template.xlsx'}
    )
