"""病案数据 - 查询子域。"""

from datetime import date, datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.security import get_current_user
from ..core.pagination import HEAVY_MAX_PAGE_SIZE, page_param, page_size_param
from ..services.medical_records.query_service import (
    WORKSTATION_REVIEW_STATES,
    WorkstationDefectRangeTooLarge,
    WorkstationDefectUnavailable,
    WorkstationReviewStateUnavailable,
    WorkstationScoreRangeTooLarge,
    WorkstationScoreUnavailable,
    get_departments,
    get_stats,
    get_workstation_data,
    list_medical_records,
)
from ..services.scoring_service import ScoringStandardSelectionInvalid
from ..services.medical_records.hospitalization_status_service import (
    default_hospitalization_status_service,
)
from .medical_records_common import raise_medical_records_http_error

router = APIRouter(tags=["病案数据-查询"])

_REVIEW_STATE_UNAVAILABLE_DETAIL = "病历审核状态暂不可用，无法按审核状态筛选，请稍后重试"


def _parse_review_state(value: Optional[str]) -> Optional[tuple[str, ...]]:
    """解析逗号分隔的 review_state；不传为 None（不筛选），空值或非法值 422。"""

    if value is None:
        return None
    items = [item.strip() for item in value.split(",")]
    if not items or any(item not in WORKSTATION_REVIEW_STATES for item in items):
        raise HTTPException(
            status_code=422,
            detail="review_state 取值无效，仅支持 pending_review/pending_recheck/approved/doubtful",
        )
    return tuple(dict.fromkeys(items))


@router.post("/workstation/hospitalization-status/verify")
async def verify_workstation_hospitalization_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """轻量核验病历池病例当前是否仍在院，不同步病历文书。"""

    try:
        return default_hospitalization_status_service.verify_current_statuses()
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/list")
async def list_medical_records_api(
    dept: Optional[str] = Query(None, description="科室筛选"),
    keyword: Optional[str] = Query(None, description="患者姓名/病案号搜索"),
    start_date: Optional[date] = Query(None, description="入院开始日期"),
    end_date: Optional[date] = Query(None, description="出院截止日期"),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(description="每页条数"),
):
    try:
        return list_medical_records(
            dept=dept,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/stats")
async def get_stats_api(
    dept: Optional[str] = Query(None, description="科室筛选"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    try:
        return get_stats(dept=dept, start_date=start_date, end_date=end_date)
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/departments")
async def get_departments_api():
    try:
        return get_departments()
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/workstation")
async def get_workstation_data_api(
    dept: Optional[str] = Query(None, description="科室筛选，不传则返回全部"),
    doctor: Optional[str] = Query(None, description="主管医师筛选，不传则返回全部"),
    keyword: Optional[str] = Query(None, description="搜索姓名/病案号"),
    start_date: Optional[date] = Query(None, description="筛选开始日期"),
    end_date: Optional[date] = Query(None, description="筛选结束日期"),
    date_field: Optional[str] = Query("visit", description="日期字段：visit/admission/discharge/updated"),
    hospital_status: Literal["all", "inpatient", "discharged"] = Query(
        "all",
        description="住院状态：all/inpatient/discharged；按权威出院时间判定",
    ),
    sync_scope: Literal["all", "today_inpatient"] = Query(
        "all",
        description="快捷范围：today_inpatient 仅返回今日已核验且仍在院的病历",
    ),
    inpatient_sort: Literal["default", "longest", "recent"] = Query(
        "default",
        description="在院病历排序：default/longest/recent",
    ),
    page: int = page_param(description="页码"),
    page_size: int = page_size_param(default=50, max_value=HEAVY_MAX_PAGE_SIZE, description="每页条数"),
    analytics_job_id: Optional[UUID] = Query(None, description="统计下钻的已完成根任务 ID"),
    analytics_completed_from: Optional[datetime] = Query(None, description="统计下钻完成时间起点"),
    analytics_completed_to: Optional[datetime] = Query(None, description="统计下钻完成时间终点"),
    analytics_rule_id: Optional[str] = Query(None, description="统计下钻规则 ID"),
    analytics_result_status: Optional[
        Literal[
            "non_compliant",
            "data_gap",
            "uncertain",
            "compliant",
            "not_applicable",
            "not_executed",
            "technical_error",
        ]
    ] = Query(None, description="统计下钻 Canonical 结果状态"),
    analytics_scope: Optional[Literal["final"]] = Query(None, description="统计下钻资料范围"),
    review_state: Optional[str] = Query(
        None,
        description="审核状态筛选，逗号分隔：pending_review/pending_recheck/approved/doubtful",
    ),
    standard_id: Optional[UUID] = Query(None, description="评分标准 ID；不传使用场景默认标准"),
    score_status: Optional[Literal["scored", "no_standard", "unavailable"]] = Query(
        None, description="计分状态筛选",
    ),
    grade: Optional[str] = Query(None, min_length=1, max_length=50, description="评分等级筛选"),
    score_min: Optional[float] = Query(None, description="最低得分（含）"),
    score_max: Optional[float] = Query(None, description="最高得分（含）"),
    result_view: Literal["records", "defects"] = Query("records", description="结果视图：病历或缺陷"),
    defect_source: Optional[Literal["all", "auto", "manual"]] = Query(
        None, description="缺陷来源：全部、Canonical 自动缺陷、任务人工缺陷",
    ),
    has_defect: Optional[bool] = Query(None, description="病历视图按是否存在指定来源缺陷筛选"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if result_view == "defects" and has_defect is not None:
        raise HTTPException(status_code=422, detail="缺陷结果视图不支持 has_defect 参数")
    if result_view == "records" and defect_source is not None and has_defect is None:
        raise HTTPException(status_code=422, detail="defect_source 必须与 has_defect 同时使用")
    if result_view == "defects" or has_defect is not None:
        roles = {
            str(role).strip().lower()
            for role in (current_user.get("roles") or [])
            if str(role).strip()
        }
        if not roles.intersection({"admin", "qc_manager", "qc_staff"}):
            raise HTTPException(status_code=403, detail="缺陷查询权限不足")
    review_states = _parse_review_state(review_state)
    extra: Dict[str, Any] = {} if review_states is None else {"review_state": review_states}
    try:
        return get_workstation_data(
            dept=dept,
            doctor=doctor,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            date_field=date_field,
            hospital_status=hospital_status,
            sync_scope=sync_scope,
            inpatient_sort=inpatient_sort,
            page=page,
            page_size=page_size,
            analytics_job_id=str(analytics_job_id) if analytics_job_id else None,
            analytics_completed_from=analytics_completed_from,
            analytics_completed_to=analytics_completed_to,
            analytics_rule_id=analytics_rule_id,
            analytics_result_status=analytics_result_status,
            analytics_scope=analytics_scope,
            standard_id=str(standard_id) if standard_id else None,
            score_status=score_status,
            grade=grade,
            score_min=score_min,
            score_max=score_max,
            result_view=result_view,
            defect_source=defect_source,
            has_defect=has_defect,
            **extra,
        )
    except WorkstationReviewStateUnavailable:
        # 带审核状态筛选却读不到审核状态：不能返回未过滤结果，固定脱敏 503。
        raise HTTPException(status_code=503, detail=_REVIEW_STATE_UNAVAILABLE_DETAIL) from None
    except WorkstationScoreRangeTooLarge:
        raise HTTPException(
            status_code=422,
            detail={"code": "range_too_large", "message": "评分筛选范围超过 5000 例，请缩小范围"},
        ) from None
    except WorkstationDefectRangeTooLarge:
        raise HTTPException(
            status_code=422,
            detail={"code": "range_too_large", "message": "缺陷查询范围超过 5000 例，请缩小范围"},
        ) from None
    except ScoringStandardSelectionInvalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except WorkstationScoreUnavailable:
        raise HTTPException(
            status_code=503,
            detail="评分数据暂不可用，无法按评分条件筛选，请稍后重试",
        ) from None
    except WorkstationDefectUnavailable:
        raise HTTPException(
            status_code=503,
            detail="缺陷数据暂不可用，无法按当前条件查询，请稍后重试",
        ) from None
    except Exception as exc:
        raise_medical_records_http_error(exc)
