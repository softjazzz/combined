"""\
病案首页 API
提供病案首页的查询与维护接口
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
try:
    from loguru import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from app.config import settings
from app.models.schemas import CaseFrontPageCreate, CaseFrontPageDetail
from app.services.database import db_service
from app.services.demo_data_store import get_demo_store

router = APIRouter(prefix="/case-front-page", tags=["病案首页"])


@router.get(
    "",
    response_model=List[CaseFrontPageDetail],
    summary="获取病案首页列表",
    description="获取病案首页列表（用于编码辅助列表页）"
)
async def list_case_front_pages(
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
):
    try:
        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            records = store.list_cases(limit=limit)
            return [CaseFrontPageDetail(**record) for record in records]

        records = await db_service.list_case_front_pages(limit=limit)
        if not records:
            store = get_demo_store()
            records = store.list_cases(limit=limit)
        return [CaseFrontPageDetail(**record) for record in records]
    except Exception as e:
        logger.error(f"获取病案首页列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取列表失败: {str(e)}")


@router.get(
    "/{admission_id}",
    response_model=CaseFrontPageDetail,
    summary="获取病案首页详情",
    description="根据住院号获取病案首页详情（包含次诊断、手术操作）"
)
async def get_case_front_page_detail(admission_id: str):
    try:
        if settings.DEMO_MODE or getattr(db_service, 'client', None) is None:
            store = get_demo_store()
            record = store.get_case_detail(admission_id)
            if not record:
                raise HTTPException(status_code=404, detail=f"未找到住院号 {admission_id} 的病案首页")
            return CaseFrontPageDetail(**record)

        record = await db_service.get_case_front_page_detail(admission_id)
        if not record:
            store = get_demo_store()
            record = store.get_case_detail(admission_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"未找到住院号 {admission_id} 的病案首页")
        return CaseFrontPageDetail(**record)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取病案首页详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取详情失败: {str(e)}")


@router.post(
    "",
    response_model=CaseFrontPageDetail,
    summary="创建或更新病案首页",
    description="创建或更新病案首页（会同步保存次诊断、手术操作列表）"
)
async def upsert_case_front_page(payload: CaseFrontPageCreate):
    try:
        logger.info(f"保存病案首页: {payload.admission_id}")
        if settings.DEMO_MODE:
            store = get_demo_store()
            record = store.upsert_case(payload.model_dump())
            return CaseFrontPageDetail(**record)
        record = await db_service.upsert_case_front_page(payload)
        return CaseFrontPageDetail(**record)
    except Exception as e:
        logger.error(f"保存病案首页失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
