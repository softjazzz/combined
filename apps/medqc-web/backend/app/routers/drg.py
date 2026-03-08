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


class RealtimeDRGRequest(BaseModel):
    """实时 DRG 分组请求 - 直接传入首页数据"""
    primary_diagnosis_code: str
    primary_diagnosis_text: Optional[str] = None
    secondary_diagnosis_codes: Optional[List[str]] = None
    procedure_codes: Optional[List[str]] = None
    patient_age: int = 50
    patient_gender: str = "M"  # M / F
    los: int = 7
    total_cost: float = 0
    region: str = "四川省"


class HandleSuggestionRequest(BaseModel):
    suggestion_id: int
    action: str  # accept / reject
    handled_by: Optional[str] = None


class HandleAlertRequest(BaseModel):
    alert_id: int
    action: str  # acknowledge / resolve
    handled_by: Optional[str] = None


@router.post("/predict-realtime")
async def predict_drg_realtime(payload: RealtimeDRGRequest) -> Dict[str, Any]:
    """
    实时 DRG 分组预测 - 直接传入首页数据（无需 admission_id）
    
    用于事前分析场景，从病历文本实时抽取后直接调用分组
    """
    from ..services.drg_grouping_service import get_drg_grouping_service
    
    service = get_drg_grouping_service()
    result = await service.group_drg(
        primary_diagnosis=payload.primary_diagnosis_code,
        secondary_diagnoses=payload.secondary_diagnosis_codes or [],
        procedures=payload.procedure_codes or [],
        patient_age=payload.patient_age,
        patient_gender=payload.patient_gender,
        los=payload.los,
        city_name=payload.region,
        total_fee=payload.total_cost
    )
    
    # 计算盈亏
    baseline_payment = result.get("baseline_payment", 0)
    profit_margin = round((baseline_payment - payload.total_cost) / baseline_payment, 4) if baseline_payment else 0.0
    result["actual_cost"] = payload.total_cost
    result["profit_margin"] = profit_margin
    
    return {"data": result, "message": "分组成功" if result.get("success") else "分组失败（降级模式）"}


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
    
    每次上传创建新的 session，数据仅用于当次分析。
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
        
        # ⭐ 创建新 session（多租户隔离）
        session_id = drg_batch_store.create_session()
        
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
                
                # 保存到 session 数据库
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
                
                drg_batch_store.save_batch_record(session_id, record_data)
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
            "session_id": session_id,  # 返回 session_id 给前端
            "batch_id": batch_id,
            "total_records": len(df),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results[:100]
        }
        
    except Exception as e:
        logger.error(f"批量上传处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量处理失败: {str(e)}")


@router.get("/statistics")
async def get_drg_statistics(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None, description="批次ID"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    department: Optional[str] = Query(None, description="科室代码"),
    doctor: Optional[str] = Query(None, description="医生姓名"),
) -> Dict[str, Any]:
    """
    获取指定 session 的 DRG 统计数据
    
    返回：MDC分布、DRG Top-10、科室统计、医师统计、费用结构。
    同时集成 EnhancedAnalyzer 提供的高级指标、AI 洞察和图表配置。
    """
    try:
        # 获取基础的 SQLite 聚合统计（兼容原有前端）
        basic_stats = drg_batch_store.get_statistics(
            session_id=session_id,
            batch_id=batch_id,
            start_date=start_date,
            end_date=end_date,
            department=department,
            doctor=doctor
        )
        
        # 获取所有明细数据用于高级分析
        records, total = drg_batch_store.drill_down(
            session_id=session_id, 
            dimension="all", 
            value="all", 
            batch_id=batch_id, 
            page=1, 
            per_page=10000  # 获取全部数据进行分析
        )
        
        if not records:
            basic_stats["ai_insights"] = []
            basic_stats["charts"] = {}
            return {"success": True, "data": basic_stats}
            
        # 转换为 DataFrame 用于 EnhancedAnalyzer
        df = pd.DataFrame(records)
        
        # 执行高级分析
        try:
            from ..services.enhanced_analysis import EnhancedAnalyzer
            from ..services.chart_service import ChartService
            
            # 使用 LLM 分析器进行多维计算
            # 建立 medqc -> drg 表字段映射
            mappings = {
                "baseline_payment": "dip_payment",
                "drg_weight": "dip_weight",
                "drg": "dip_name",
                "department_name": "department"
            }
            analyzer = EnhancedAnalyzer(df, user_mappings=mappings)
            analysis_results = analyzer.run_full_analysis()
            
            # 将高级分析结果附加到响应中
            basic_stats["advanced_analysis"] = analysis_results
            
            # TODO: 暂时构造一些基础的 AI insight，后续可以接入真正的 LLM
            insights = []
            overview = analysis_results.get("overview", {})
            if overview.get("loss_case_count", 0) > 0:
                insights.append(f"发现 {overview['loss_case_count']} 例亏损病案，建议关注。")
            
            top_loss_depts = overview.get("top_loss_departments", [])
            if top_loss_depts:
                dept_names = ", ".join([d["name"] for d in top_loss_depts])
                insights.append(f"前三大亏损科室为: {dept_names}。")
                
            basic_stats["ai_insights"] = insights
            
            # 生成图表配置
            basic_stats["charts"] = ChartService.generate_all_charts(analysis_results)
            
        except Exception as e:
            logger.error(f"高级分析或图表生成失败: {e}", exc_info=True)
            basic_stats["advanced_analysis"] = {}
            basic_stats["ai_insights"] = ["高级分析引擎运行出错"]
            basic_stats["charts"] = {}
            
        return {"success": True, "data": basic_stats}
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drill-down")
async def drg_drill_down(
    session_id: str = Query(..., description="Session ID"),
    dimension: str = Query(..., description="钻取维度: department/doctor/drg/mdc"),
    value: str = Query(..., description="维度值"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    batch_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    钻取查询指定 session 的明细
    """
    try:
        records, total = drg_batch_store.drill_down(
            session_id=session_id,
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
async def list_batches(
    session_id: str = Query(..., description="Session ID")
) -> Dict[str, Any]:
    """获取指定 session 的批次列表"""
    try:
        batches = drg_batch_store.get_batch_list(session_id)
        return {"success": True, "data": batches}
    except Exception as e:
        logger.error(f"获取批次列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str) -> Dict[str, Any]:
    """删除 session 及其临时数据（报告生成后调用）"""
    try:
        deleted = drg_batch_store.delete_session(session_id)
        if deleted:
            return {"success": True, "message": f"Session {session_id} 已删除"}
        else:
            return {"success": False, "message": f"Session {session_id} 不存在"}
    except Exception as e:
        logger.error(f"删除 session 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup-sessions")
async def cleanup_expired_sessions() -> Dict[str, Any]:
    """清理超时的 session（后台定时任务调用）"""
    try:
        cleaned = drg_batch_store.cleanup_expired_sessions()
        return {"success": True, "cleaned_count": cleaned}
    except Exception as e:
        logger.error(f"清理超时 session 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_active_sessions() -> Dict[str, Any]:
    """列出所有活跃的 session（调试用）"""
    try:
        sessions = drg_batch_store.list_active_sessions()
        return {"success": True, "data": sessions}
    except Exception as e:
        logger.error(f"获取 session 列表失败: {e}")
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


@router.get("/export/excel")
async def export_excel_report(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None),
    days: int = Query(30)
) -> StreamingResponse:
    """导出 Excel 分析报告"""
    try:
        # 获取统计数据
        stats = drg_batch_store.get_statistics(session_id=session_id, batch_id=batch_id)
        records = drg_batch_store.get_all_records(session_id=session_id, batch_id=batch_id)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Sheet 1: 汇总统计
            summary = stats['summary']
            summary_data = {
                '指标': ['总病例数', '入组成功率', '平均CMI', '总费用', '总盈亏', '平均住院日'],
                '数值': [
                    summary.get('total_cases', 0),
                    f"{summary.get('success_rate', 0):.1f}%",
                    f"{summary.get('avg_cmi', 0):.2f}",
                    f"¥{summary.get('total_cost', 0):,.2f}",
                    f"¥{summary.get('total_profit', 0):,.2f}",
                    f"{summary.get('avg_los', 0):.1f} 天"
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, index=False, sheet_name='统计汇总')
            
            # Sheet 2: 科室统计
            if stats.get('department_stats'):
                dept_df = pd.DataFrame(stats['department_stats'])
                dept_df.to_excel(writer, index=False, sheet_name='科室统计')
            
            # Sheet 3: 病例明细
            if records:
                records_df = pd.DataFrame(records)
                # 重命名列
                col_map = {
                    'record_id': '病案号', 'patient_gender': '性别', 'patient_age': '年龄',
                    'dept_name': '科室', 'primary_diagnosis': '主诊断', 
                    'drg_code': 'DRG编码', 'drg_name': 'DRG名称', 
                    'weight': '权重', 'total_cost': '总费用', 'profit_margin': '盈亏'
                }
                records_df = records_df.rename(columns=col_map)
                records_df.to_excel(writer, index=False, sheet_name='病例明细')
        
        output.seek(0)
        filename = f"drg_report_{batch_id or 'all'}.xlsx"
        
        return StreamingResponse(
            output,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except Exception as e:
        logger.error(f"导出 Excel 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notify")
async def trigger_notification(
    batch_id: str = Query(...),
    notification_type: str = Query("batch_complete")
) -> Dict[str, Any]:
    """触发通知（预留接口）
    
    notification_type:
    - batch_complete: 批量处理完成
    - cost_warning: 费用超标预警
    - high_loss: 高亏损病例提醒
    """
    # 获取批次统计用于通知内容
    stats = drg_batch_store.get_statistics(batch_id=batch_id)
    
    notification_content = {
        "batch_complete": f"DRG批量分析完成：共{stats['summary']['total_records']}例，"
                         f"平均CMI {stats['summary']['avg_cmi']:.2f}，"
                         f"总盈亏 ¥{stats['summary']['total_profit']:,.0f}",
        "cost_warning": f"费用预警：发现超标病例",
        "high_loss": f"高亏损提醒：发现亏损病例"
    }
    
    message = notification_content.get(notification_type, "通知")
    
    # TODO: 实际发送通知（邮件/钉钉/企业微信）
    # 目前只返回消息内容，供前端展示
    logger.info(f"Notification triggered: {notification_type} - {message}")
    
    return {
        "success": True,
        "notification_type": notification_type,
        "message": message,
        "note": "通知服务预留接口，实际发送需配置 Webhook/SMTP"
    }


@router.get("/export/pdf")
async def export_pdf_report(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None),
    days: int = Query(30)
) -> StreamingResponse:
    """导出 PDF 分析报告"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        # 获取数据
        stats = drg_batch_store.get_statistics(session_id=session_id, batch_id=batch_id)
        summary = stats['summary']
        
        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', fontSize=18, alignment=1, spaceAfter=20)
        heading_style = ParagraphStyle('Heading', fontSize=14, spaceAfter=10, spaceBefore=15)
        
        elements = []
        
        # 标题
        elements.append(Paragraph("DRG Analysis Report", title_style))
        elements.append(Spacer(1, 20))
        
        # 汇总表格
        elements.append(Paragraph("Summary Statistics", heading_style))
        summary_data = [
            ['Metric', 'Value'],
            ['Total Cases', str(summary.get('total_cases', 0))],
            ['Success Rate', f"{summary.get('success_rate', 0):.1f}%"],
            ['Average CMI', f"{summary.get('avg_cmi', 0):.2f}"],
            ['Total Cost', f"¥{summary.get('total_cost', 0):,.2f}"],
            ['Total Profit', f"¥{summary.get('total_profit', 0):,.2f}"],
            ['Average LOS', f"{summary.get('avg_los', 0):.1f} days"]
        ]
        
        t = Table(summary_data, colWidths=[8*cm, 8*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))
        
        # 科室统计
        if stats.get('department_stats'):
            elements.append(Paragraph("Department Statistics", heading_style))
            dept_data = [['Department', 'Cases', 'CMI', 'Profit']]
            for d in stats['department_stats'][:10]:
                dept_data.append([
                    d.get('department_name', d.get('department', '-'))[:20],
                    str(d.get('count', 0)),
                    f"{d.get('cmi', 0):.2f}",
                    f"¥{d.get('profit', 0):,.0f}"
                ])
            
            t2 = Table(dept_data, colWidths=[6*cm, 3*cm, 3*cm, 4*cm])
            t2.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#22c55e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
            ]))
            elements.append(t2)
        
        doc.build(elements)
        output.seek(0)
        
        filename = f"drg_report_{batch_id or 'all'}.pdf"
        return StreamingResponse(
            output,
            media_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except ImportError as e:
        logger.error(f"PDF导出依赖缺失: {e}")
        raise HTTPException(status_code=500, detail="PDF导出需要安装 reportlab: pip install reportlab")
    except Exception as e:
        logger.error(f"导出 PDF 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/word")
async def export_word_report(
    session_id: str = Query(..., description="Session ID"),
    batch_id: Optional[str] = Query(None),
    days: int = Query(30)
) -> StreamingResponse:
    """导出 Word 分析报告"""
    try:
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        
        # 获取数据
        stats = drg_batch_store.get_statistics(session_id=session_id, batch_id=batch_id)
        summary = stats['summary']
        records = drg_batch_store.get_all_records(session_id=session_id, batch_id=batch_id)
        
        doc = Document()
        
        # 标题
        title = doc.add_heading('DRG 分析报告', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 报告信息
        doc.add_paragraph(f'生成时间: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}')
        doc.add_paragraph(f'批次ID: {batch_id or "全部"}')
        doc.add_paragraph()
        
        # 统计汇总
        doc.add_heading('一、统计汇总', level=1)
        
        table = doc.add_table(rows=7, cols=2)
        table.style = 'Table Grid'
        
        summary_items = [
            ('总病例数', str(summary.get('total_cases', 0))),
            ('入组成功率', f"{summary.get('success_rate', 0):.1f}%"),
            ('平均CMI', f"{summary.get('avg_cmi', 0):.2f}"),
            ('总费用', f"¥{summary.get('total_cost', 0):,.2f}"),
            ('总盈亏', f"¥{summary.get('total_profit', 0):,.2f}"),
            ('平均住院日', f"{summary.get('avg_los', 0):.1f} 天"),
            ('分析天数', f"{days} 天")
        ]
        
        for i, (label, value) in enumerate(summary_items):
            table.rows[i].cells[0].text = label
            table.rows[i].cells[1].text = value
        
        doc.add_paragraph()
        
        # 科室分析
        if stats.get('department_stats'):
            doc.add_heading('二、科室分析', level=1)
            
            dept_table = doc.add_table(rows=1, cols=4)
            dept_table.style = 'Table Grid'
            headers = dept_table.rows[0].cells
            headers[0].text = '科室'
            headers[1].text = '病例数'
            headers[2].text = 'CMI'
            headers[3].text = '盈亏'
            
            for d in stats['department_stats'][:15]:
                row = dept_table.add_row().cells
                row[0].text = d.get('department_name', d.get('department', '-'))[:20]
                row[1].text = str(d.get('count', 0))
                row[2].text = f"{d.get('cmi', 0):.2f}"
                row[3].text = f"¥{d.get('profit', 0):,.0f}"
        
        doc.add_paragraph()
        
        # 病例明细 (前20条)
        if records:
            doc.add_heading('三、病例明细 (前20条)', level=1)
            
            case_table = doc.add_table(rows=1, cols=5)
            case_table.style = 'Table Grid'
            headers = case_table.rows[0].cells
            headers[0].text = '病案号'
            headers[1].text = '科室'
            headers[2].text = 'DRG'
            headers[3].text = '费用'
            headers[4].text = '盈亏'
            
            for r in records[:20]:
                row = case_table.add_row().cells
                row[0].text = str(r.get('admission_id', '-'))[:15]
                row[1].text = str(r.get('department_name', r.get('department', '-')))[:10]
                row[2].text = str(r.get('drg', '-'))[:10]
                row[3].text = f"¥{r.get('total_cost', 0):,.0f}"
                row[4].text = f"¥{r.get('profit_margin', 0):,.0f}"
        
        output = io.BytesIO()
        doc.save(output)
        output.seek(0)
        
        filename = f"drg_report_{batch_id or 'all'}.docx"
        return StreamingResponse(
            output,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except ImportError as e:
        logger.error(f"Word导出依赖缺失: {e}")
        raise HTTPException(status_code=500, detail="Word导出需要安装 python-docx: pip install python-docx")
    except Exception as e:
        logger.error(f"导出 Word 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


