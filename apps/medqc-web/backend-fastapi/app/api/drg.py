"""
DRG 分组 API
PRD 3.2.2 - 自动入组预测
PRD 3.3 - 事中监控
"""

from fastapi import APIRouter, HTTPException, Query
try:
    from loguru import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)
from typing import Optional

from app.config import settings
from app.models.schemas import (
    DRGPredictRequest,
    DRGPredictionResponse,
    DRGGroupingHistoryResponse,
    DRGGroupingHistoryItem,
    CodingSuggestionsResponse,
    CodingSuggestionItem,
    HandleSuggestionRequest,
    HandleSuggestionResponse,
    HandleAlertRequest,
    HandleAlertResponse,
    DRGAlertsRequest,
    DRGAlertsResponse,
    DRGAlertItem
)
from app.services.drg_grouper import drg_grouper
from app.services.database import db_service
from app.services.demo_data_store import get_demo_store
from app.services.demo_store import demo_store

router = APIRouter(prefix="/drg", tags=["DRG分组"])


@router.get(
    "/demo/story-cases",
    summary="获取演示故事病例",
    description="DEMO 模式：返回固定的演示病例列表，便于前端一键跳转演示"
)
async def get_demo_story_cases():
    if not settings.DEMO_MODE:
        return {"cases": []}
    store = get_demo_store()
    return store.get_story_cases()


@router.post(
    "/predict",
    response_model=DRGPredictionResponse,
    summary="DRG 入组预测",
    description="PRD 3.2.2：根据病案首页进行 DRG 分组预测"
)
async def predict_drg_grouping(request: DRGPredictRequest):
    """
    DRG 入组预测

    调用 OpenDRG 引擎进行 DRG 分组，返回 ADRG、DRG、权重、基准支付金额等信息。

    **示例请求**：
    ```json
    {
      "admission_id": "ADM20250104001",
      "region": "sichuan"
    }
    ```

    **返回**：
    - adrg_code: ADRG 编码
    - drg_code: DRG 编码
    - weight: DRG 权重系数
    - baseline_payment: 基准支付金额（元）
    - expected_los: 预期住院日范围
    - confidence: 分组置信度
    - risk_level: 风险等级
    - grouping_logic: 分组逻辑说明
    """
    try:
        logger.info(f"接收 DRG 分组预测请求: {request.admission_id}")

        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()

            case_front_page = store.get_case_detail(request.admission_id)
            if not case_front_page:
                raise HTTPException(
                    status_code=404,
                    detail=f"未找到住院号 {request.admission_id} 的病案首页"
                )

            primary_diagnosis = case_front_page['primary_diagnosis_code']
            secondary_diagnoses = [d['code'] for d in (case_front_page.get('secondary_diagnoses') or [])]
            procedure_codes = [p['code'] for p in (case_front_page.get('procedures') or [])]
            if case_front_page.get('main_procedure_code'):
                procedure_codes.insert(0, case_front_page['main_procedure_code'])

            result = await drg_grouper.group(
                primary_diagnosis=primary_diagnosis,
                secondary_diagnoses=secondary_diagnoses,
                procedures=procedure_codes,
                patient_age=case_front_page.get('patient_age', 50),
                patient_gender=case_front_page.get('patient_gender', 'M'),
                total_hospital_days=case_front_page.get('total_hospital_days'),
                discharge_status=case_front_page.get('discharge_status')
            )

            store.append_grouping_history(request.admission_id, result)
            await _check_and_create_alerts_demo(
                store=store,
                admission_id=request.admission_id,
                drg_result=result,
                case_data=case_front_page
            )

            return DRGPredictionResponse(
                data=result,
                message="分组成功"
            )

        # 1. 获取病案首页数据（DB 优先，空/失败时使用演示数据兜底）
        case_front_page = await db_service.get_case_front_page(request.admission_id)
        demo_case = None

        if not case_front_page:
            store = get_demo_store()
            demo_case = store.get_case_detail(request.admission_id)
            if not demo_case:
                demo_case = demo_store.get_case_front_page_detail(request.admission_id)
                if not demo_case:
                    raise HTTPException(
                        status_code=404,
                        detail=f"未找到住院号 {request.admission_id} 的病案首页"
                    )

        # 2. 获取次诊断和手术操作
        if case_front_page:
            front_page_id = case_front_page['front_page_id']
            diagnoses = await db_service.get_case_diagnoses(front_page_id)
            procedures = await db_service.get_case_procedures(front_page_id)
            primary_diagnosis = case_front_page['primary_diagnosis_code']
            secondary_diagnoses = [d['diagnosis_code'] for d in diagnoses]
            procedure_codes = [p['procedure_code'] for p in procedures]
            if case_front_page.get('main_procedure_code'):
                procedure_codes.insert(0, case_front_page['main_procedure_code'])
        else:
            # demo_case 的 secondary_diagnoses/procedures 已是 {code,name,...} 格式
            primary_diagnosis = demo_case['primary_diagnosis_code']
            secondary_diagnoses = [d['code'] for d in demo_case.get('secondary_diagnoses', []) if d.get('code')]
            procedure_codes = [p['code'] for p in demo_case.get('procedures', []) if p.get('code')]
            if demo_case.get('main_procedure_code'):
                procedure_codes.insert(0, demo_case['main_procedure_code'])

        case_data = case_front_page or demo_case or {}

        # 4. 调用 DRG 分组引擎
        result = await drg_grouper.group(
            primary_diagnosis=primary_diagnosis,
            secondary_diagnoses=secondary_diagnoses,
            procedures=procedure_codes,
            patient_age=case_data.get('patient_age', 50),
            patient_gender=case_data.get('patient_gender', 'M'),
            total_hospital_days=case_data.get('total_hospital_days'),
            discharge_status=case_data.get('discharge_status')
        )

        # 5. 保存分组结果到数据库（如 DB 不可用，写入演示 store）
        grouping_id = await db_service.save_drg_grouping(
            admission_id=request.admission_id,
            region=request.region,
            adrg_code=result['adrg_code'],
            adrg_name=result['adrg_name'],
            drg_code=result['drg_code'],
            drg_name=result['drg_name'],
            weight=result['weight'],
            baseline_payment=result['baseline_payment'],
            grouping_logic=result['grouping_logic']
        )

        if grouping_id is None:
            store = get_demo_store()
            store.append_grouping_history(request.admission_id, result)

        logger.info(f"DRG 分组成功: {result['drg_code']}, grouping_id={grouping_id}")

        # 6. 检查是否需要触发预警
        await _check_and_create_alerts(
            admission_id=request.admission_id,
            drg_result=result,
            case_data=case_front_page or demo_case
        )

        return DRGPredictionResponse(
            data=result,
            message="分组成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DRG 分组失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"分组失败: {str(e)}")


@router.get(
    "/code-info/{code}",
    summary="查询编码详细信息",
    description="查询 ICD 编码的 ADRG/MDC 映射关系（调用外部 API）"
)
async def get_code_info(
    code: str,
    city: Optional[str] = Query("四川省", description="城市名称")
):
    try:
        logger.info(f"查询编码详情: {code}, city={city}")
        return await drg_grouper.lookup_code_info(code, city)
    except Exception as e:
        logger.error(f"查询编码详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/grouping/{admission_id}/history",
    response_model=DRGGroupingHistoryResponse,
    summary="DRG 分组历史",
    description="获取指定病案的 DRG 分组历史记录"
)
async def get_grouping_history(admission_id: str):
    """
    DRG 分组历史

    查询指定病案的所有历史分组记录（支持版本控制）。

    **参数**：
    - admission_id: 住院号

    **返回**：
    - history: 分组历史列表（按时间倒序）
    - total: 历史记录总数
    """
    try:
        logger.info(f"查询 DRG 分组历史: {admission_id}")

        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            records = store.get_grouping_history(admission_id)
            history_items = [DRGGroupingHistoryItem(**record) for record in records]
            return DRGGroupingHistoryResponse(
                history=history_items,
                total=len(history_items)
            )

        records = await db_service.get_drg_grouping_history(admission_id)
        if not records:
            store = get_demo_store()
            records = store.get_grouping_history(admission_id)

        history_items = [
            DRGGroupingHistoryItem(**record) for record in records
        ]

        return DRGGroupingHistoryResponse(
            history=history_items,
            total=len(history_items)
        )

    except Exception as e:
        logger.error(f"查询分组历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get(
    "/suggestions",
    response_model=CodingSuggestionsResponse,
    summary="获取编码建议列表（可按条件过滤）",
    description="获取编码建议列表，支持按住院号/状态过滤"
)
async def list_coding_suggestions(
    admission_id: Optional[str] = Query(None, description="住院号（可选）"),
    status: Optional[str] = Query(None, description="建议状态：pending/accepted/rejected"),
    limit: int = Query(50, ge=1, le=200, description="返回数量")
):
    try:
        logger.info(f"查询编码建议列表: admission_id={admission_id}, 状态={status}, limit={limit}")

        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            suggestions = store.list_suggestions(
                admission_id=admission_id,
                status=status,
                limit=limit
            )
            suggestion_items = [CodingSuggestionItem(**s) for s in suggestions]
            return CodingSuggestionsResponse(
                suggestions=suggestion_items,
                total=len(suggestion_items)
            )

        suggestions = await db_service.list_coding_suggestions(
            admission_id=admission_id,
            status=status,
            limit=limit
        )

        if not suggestions:
            store = get_demo_store()
            suggestions = store.list_suggestions(
                admission_id=admission_id,
                status=status,
                limit=limit
            )

        suggestion_items = [CodingSuggestionItem(**s) for s in suggestions]

        return CodingSuggestionsResponse(
            suggestions=suggestion_items,
            total=len(suggestion_items)
        )

    except Exception as e:
        logger.error(f"查询编码建议列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get(
    "/suggestions/{admission_id}",
    response_model=CodingSuggestionsResponse,
    summary="获取编码建议",
    description="PRD 3.3：获取指定病案的编码优化建议"
)
async def get_coding_suggestions(
    admission_id: str,
    status: Optional[str] = Query(None, description="建议状态：pending/accepted/rejected")
):
    """
    获取编码建议

    查询 LLM 分析病历后给出的编码优化建议。

    **参数**：
    - admission_id: 住院号
    - status: 建议状态（可选）

    **返回**：
    - suggestions: 编码建议列表
    - total: 建议总数
    """
    try:
        logger.info(f"查询编码建议: {admission_id}, 状态: {status}")

        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            suggestions = store.list_suggestions(
                admission_id=admission_id,
                status=status,
                limit=200
            )
            suggestion_items = [CodingSuggestionItem(**s) for s in suggestions]
            return CodingSuggestionsResponse(
                suggestions=suggestion_items,
                total=len(suggestion_items)
            )

        suggestions = await db_service.get_coding_suggestions(admission_id, status)

        if not suggestions:
            store = get_demo_store()
            suggestions = store.list_suggestions(
                admission_id=admission_id,
                status=status,
                limit=50
            )

        suggestion_items = [
            CodingSuggestionItem(**s) for s in suggestions
        ]

        return CodingSuggestionsResponse(
            suggestions=suggestion_items,
            total=len(suggestion_items)
        )

    except Exception as e:
        logger.error(f"查询编码建议失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post(
    "/suggestions/handle",
    response_model=HandleSuggestionResponse,
    summary="处理编码建议",
    description="接受或拒绝编码建议"
)
async def handle_coding_suggestion(request: HandleSuggestionRequest):
    """
    处理编码建议

    编码员或医生对编码建议进行处理（接受/拒绝）。

    **示例请求**：
    ```json
    {
      "suggestion_id": 123,
      "action": "accept",
      "handled_by": "coder_001"
    }
    ```
    """
    try:
        logger.info(f"处理编码建议: {request.suggestion_id}, 操作: {request.action}")

        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            status = 'accepted' if request.action == 'accept' else 'rejected'
            success = store.update_suggestion_status(
                suggestion_id=request.suggestion_id,
                status=status,
                handled_by=request.handled_by
            )
            if not success:
                raise HTTPException(status_code=404, detail="建议未找到或更新失败")
            message = "建议已接受" if request.action == 'accept' else "建议已拒绝"
            return HandleSuggestionResponse(
                success=True,
                message=message
            )

        # 更新建议状态
        status = 'accepted' if request.action == 'accept' else 'rejected'
        success = await db_service.update_suggestion_status(
            suggestion_id=request.suggestion_id,
            status=status,
            handled_by=request.handled_by
        )

        if not success:
            store = get_demo_store()
            success = store.update_suggestion_status(
                suggestion_id=request.suggestion_id,
                status=status,
                handled_by=request.handled_by
            )

        if not success:
            raise HTTPException(status_code=404, detail="建议未找到或更新失败")

        message = "建议已接受" if request.action == 'accept' else "建议已拒绝"

        return HandleSuggestionResponse(
            success=True,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理编码建议失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.get(
    "/alerts",
    response_model=DRGAlertsResponse,
    summary="获取 DRG 预警",
    description="PRD 3.3：获取 DRG 监控预警信息"
)
async def get_drg_alerts(
    admission_id: Optional[str] = Query(None, description="住院号（可选）"),
    alert_level: Optional[str] = Query(None, description="预警级别：info/warning/critical"),
    status: Optional[str] = Query(None, description="预警状态：pending/acknowledged/resolved"),
    limit: int = Query(50, ge=1, le=200, description="返回数量")
):
    """
    获取 DRG 预警

    查询实时监控产生的预警信息（费用超标、住院日过长等）。

    **预警类型**：
    - cost_overrun: 费用超标
    - los_long: 住院日过长
    - coding_abnormal: 编码异常
    - profit_loss: 预计亏损

    **预警级别**：
    - info: 信息
    - warning: 警告
    - critical: 严重

    **返回**：
    - alerts: 预警列表
    - total: 预警总数
    """
    try:
        logger.info(f"查询 DRG 预警: admission_id={admission_id}, level={alert_level}")

        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            alerts = store.list_alerts(
                admission_id=admission_id,
                alert_level=alert_level,
                status=status,
                limit=limit
            )
            alert_items = [DRGAlertItem(**alert) for alert in alerts]
            return DRGAlertsResponse(
                alerts=alert_items,
                total=len(alert_items)
            )

        alerts = await db_service.get_drg_alerts(
            admission_id=admission_id,
            alert_level=alert_level,
            status=status,
            limit=limit
        )

        if not alerts:
            store = get_demo_store()
            alerts = store.list_alerts(
                admission_id=admission_id,
                alert_level=alert_level,
                status=status,
                limit=limit
            )

        alert_items = [
            DRGAlertItem(**alert) for alert in alerts
        ]

        return DRGAlertsResponse(
            alerts=alert_items,
            total=len(alert_items)
        )

    except Exception as e:
        logger.error(f"查询 DRG 预警失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post(
    "/alerts/handle",
    response_model=HandleAlertResponse,
    summary="处理 DRG 预警",
    description="确认或关闭 DRG 预警"
)
async def handle_drg_alert(request: HandleAlertRequest):
    try:
        logger.info(f"处理 DRG 预警: {request.alert_id}, 操作: {request.action}")

        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            status = 'acknowledged' if request.action == 'acknowledge' else 'resolved'
            success = store.update_alert_status(
                alert_id=request.alert_id,
                status=status,
                handled_by=request.handled_by
            )
            if not success:
                raise HTTPException(status_code=404, detail="预警未找到或更新失败")
            message = "预警已确认" if request.action == 'acknowledge' else "预警已关闭"
            return HandleAlertResponse(
                success=True,
                message=message
            )

        status = 'acknowledged' if request.action == 'acknowledge' else 'resolved'

        success = await db_service.update_alert_status(
            alert_id=request.alert_id,
            status=status,
            handled_by=request.handled_by
        )

        if not success:
            store = get_demo_store()
            success = store.update_alert_status(
                alert_id=request.alert_id,
                status=status,
                handled_by=request.handled_by
            )

        if not success:
            raise HTTPException(status_code=404, detail="预警未找到或更新失败")

        message = "预警已确认" if request.action == 'acknowledge' else "预警已关闭"

        return HandleAlertResponse(
            success=True,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理 DRG 预警失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


# ============================================
# 辅助函数
# ============================================

async def _check_and_create_alerts(
    admission_id: str,
    drg_result: dict,
    case_data: dict
):
    """检查并创建预警"""
    try:
        # 1. 检查费用超标预警
        if case_data.get('total_cost'):
            baseline = drg_result['baseline_payment']
            actual = case_data['total_cost']
            cost_rate = (actual / baseline) * 100 if baseline > 0 else 0

            if cost_rate > 120:
                alert_id = await db_service.save_drg_alert(
                    admission_id=admission_id,
                    alert_type='cost_overrun',
                    alert_level='critical',
                    message=f"费用超标严重，费用消耗率 {cost_rate:.1f}%",
                    metric_value=cost_rate,
                    threshold_value=100.0
                )
                if alert_id is None:
                    store = get_demo_store()
                    store.create_alert(
                        admission_id=admission_id,
                        alert_type='cost_overrun',
                        alert_level='critical',
                        message=f"费用超标严重，费用消耗率 {cost_rate:.1f}%",
                        metric_value=float(cost_rate),
                        threshold_value=100.0
                    )
            elif cost_rate > 100:
                alert_id = await db_service.save_drg_alert(
                    admission_id=admission_id,
                    alert_type='cost_overrun',
                    alert_level='warning',
                    message=f"费用超标，费用消耗率 {cost_rate:.1f}%",
                    metric_value=cost_rate,
                    threshold_value=100.0
                )
                if alert_id is None:
                    store = get_demo_store()
                    store.create_alert(
                        admission_id=admission_id,
                        alert_type='cost_overrun',
                        alert_level='warning',
                        message=f"费用超标，费用消耗率 {cost_rate:.1f}%",
                        metric_value=float(cost_rate),
                        threshold_value=100.0
                    )

        # 2. 检查住院日预警
        if case_data.get('total_hospital_days'):
            actual_los = case_data['total_hospital_days']
            expected_max = drg_result['expected_los']['max']

            if actual_los > expected_max:
                days_over = actual_los - expected_max
                alert_id = await db_service.save_drg_alert(
                    admission_id=admission_id,
                    alert_type='los_long',
                    alert_level='warning' if days_over <= 5 else 'critical',
                    message=f"住院日超标 {days_over} 天，当前 {actual_los} 天，预期最多 {expected_max} 天",
                    metric_value=float(actual_los),
                    threshold_value=float(expected_max)
                )
                if alert_id is None:
                    store = get_demo_store()
                    store.create_alert(
                        admission_id=admission_id,
                        alert_type='los_long',
                        alert_level='warning' if days_over <= 5 else 'critical',
                        message=f"住院日超标 {days_over} 天，当前 {actual_los} 天，预期最多 {expected_max} 天",
                        metric_value=float(actual_los),
                        threshold_value=float(expected_max)
                    )

        # 3. 检查高风险预警
        if drg_result['risk_level'] == 'high':
            alert_id = await db_service.save_drg_alert(
                admission_id=admission_id,
                alert_type='profit_loss',
                alert_level='warning',
                message=f"高风险病例，建议关注费用控制",
                metric_value=None,
                threshold_value=None
            )
            if alert_id is None:
                store = get_demo_store()
                store.create_alert(
                    admission_id=admission_id,
                    alert_type='profit_loss',
                    alert_level='warning',
                    message=f"高风险病例，建议关注费用控制",
                    metric_value=None,
                    threshold_value=None
                )

        logger.info(f"预警检查完成: {admission_id}")

    except Exception as e:
        logger.error(f"创建预警失败: {str(e)}")
        # 不抛出异常，避免影响主流程


async def _check_and_create_alerts_demo(
    store,
    admission_id: str,
    drg_result: dict,
    case_data: dict
):
    """DEMO 模式下检查并创建预警（写入 DemoDataStore）。"""
    try:
        if case_data.get('total_cost'):
            baseline = drg_result['baseline_payment']
            actual = case_data['total_cost']
            cost_rate = (actual / baseline) * 100 if baseline > 0 else 0

            if cost_rate > 120:
                store.create_alert(
                    admission_id=admission_id,
                    alert_type='cost_overrun',
                    alert_level='critical',
                    message=f"费用超标严重，费用消耗率 {cost_rate:.1f}%",
                    metric_value=float(cost_rate),
                    threshold_value=100.0
                )
            elif cost_rate > 100:
                store.create_alert(
                    admission_id=admission_id,
                    alert_type='cost_overrun',
                    alert_level='warning',
                    message=f"费用超标，费用消耗率 {cost_rate:.1f}%",
                    metric_value=float(cost_rate),
                    threshold_value=100.0
                )

        if case_data.get('total_hospital_days') and drg_result.get('expected_los'):
            actual_los = case_data['total_hospital_days']
            expected_max = drg_result['expected_los']['max']

            if actual_los > expected_max:
                days_over = actual_los - expected_max
                store.create_alert(
                    admission_id=admission_id,
                    alert_type='los_long',
                    alert_level='warning' if days_over <= 5 else 'critical',
                    message=f"住院日超标 {days_over} 天，当前 {actual_los} 天，预期最多 {expected_max} 天",
                    metric_value=float(actual_los),
                    threshold_value=float(expected_max)
                )

        if drg_result.get('risk_level') == 'high':
            store.create_alert(
                admission_id=admission_id,
                alert_type='profit_loss',
                alert_level='warning',
                message=f"高风险病例，建议关注费用控制",
                metric_value=None,
                threshold_value=None
            )

        logger.info(f"[DEMO] 预警检查完成: {admission_id}")

    except Exception as e:
        logger.error(f"[DEMO] 创建预警失败: {str(e)}")
