"""诊断及手术操作完整性校验 API。"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services.clinical_timeline_service import ClinicalTimelineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/clinical-completeness", tags=["clinical-completeness"])


def _load_clinical_bundle(
    *,
    visit_id: str,
    patient_id: str = "",
    institute_id: str = "",
    force_refresh: bool = False,
) -> dict[str, Any]:
    """加载用于诊断/手术完整性校验的病历 bundle。"""
    from ..services.bundles.assembly import load_or_assemble_scene_bundle

    return load_or_assemble_scene_bundle(
        scene="final",
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        force_refresh=force_refresh,
    )


@router.get("/{visit_id}")
async def get_clinical_completeness(
    request: Request,
    visit_id: str,
    patient_id: str = Query("", description="患者 ID；有值时可更精确定位 bundle"),
    institute_id: str = Query("", description="机构 ID"),
    force_refresh: bool = Query(False, description="是否强制刷新 bundle"),
    current_user: dict = Depends(get_current_user),
):
    """返回诊断发生发展时间轴和手术操作执行验证。

    该接口只读，不写正式病案首页、医保结算清单或正式质控结果。
    """
    if not str(visit_id or "").strip():
        raise HTTPException(status_code=400, detail="visit_id 不能为空")

    try:
        from .qc_sichuan import _cdm_bundle_read_guard

        async with _cdm_bundle_read_guard():
            bundle = await run_in_threadpool(
                _load_clinical_bundle,
                visit_id=visit_id,
                patient_id=patient_id,
                institute_id=institute_id,
                force_refresh=force_refresh,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("加载临床完整性 bundle 失败 visit_id=%s error=%s", visit_id, exc)
        raise HTTPException(status_code=503, detail=f"病历文书 bundle 暂不可用：{exc}") from exc

    timeline = ClinicalTimelineService().build_from_bundle(bundle)
    data = timeline.to_dict()
    data["safety"] = {
        "mode": "read_only_analysis",
        "writes_formal_frontpage": False,
        "writes_settlement": False,
        "writes_formal_qc_result": False,
    }
    return success_response(
        data=data,
        message="诊断及手术操作完整性分析完成",
        trace_id=get_trace_id(request),
    )
