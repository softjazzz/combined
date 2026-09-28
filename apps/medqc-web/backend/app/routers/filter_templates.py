"""用户个人筛选模板路由（V3.6 P1-A 合同第 3 节）。

- GET    /api/v1/filter-templates?page_key=        本人该页全部模板
- POST   /api/v1/filter-templates                  新建（可同时设为默认）
- PUT    /api/v1/filter-templates/{template_id}    CAS 更新（version 必填）
- DELETE /api/v1/filter-templates/{template_id}?version=  CAS 删除
均需登录，只能操作本人模板（他人模板 404）；数据库故障固定脱敏为 503。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr
from starlette.concurrency import run_in_threadpool

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services.filter_template_service import (
    FilterTemplateConflict,
    FilterTemplateInvalid,
    FilterTemplateNotFound,
    FilterTemplateUnavailable,
    create_template,
    delete_template,
    list_templates,
    update_template,
)

router = APIRouter(prefix="/api/v1/filter-templates", tags=["filter-templates"])
logger = logging.getLogger(__name__)

_UNAVAILABLE_DETAIL = "筛选模板服务暂不可用，请稍后重试"

PageKey = Literal[
    "v5_records_inpatient",
    "v5_records_discharged",
    "v5_records_outpatient_emergency",
]


class FilterTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_key: PageKey
    name: StrictStr
    filters: dict[str, Any]
    is_default: StrictBool = False


class FilterTemplateUpdateRequest(BaseModel):
    """未传或为 null 的字段保持不变；version 用于 CAS。"""

    model_config = ConfigDict(extra="forbid")

    version: StrictInt = Field(..., ge=1)
    name: Optional[StrictStr] = None
    filters: Optional[dict[str, Any]] = None
    is_default: Optional[StrictBool] = None


class FilterTemplateItem(BaseModel):
    """对外字段白名单（不输出 owner_id）。filters 为 None 表示存量内容不可用。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    page_key: PageKey
    name: str
    filters: Optional[dict[str, Any]]
    is_default: bool
    version: int
    created_at: datetime
    updated_at: datetime


def _owner_id(current_user: dict) -> str:
    """与任务路由一致：真实认证字段 id 优先，兼容历史 user_id。"""
    user_id = current_user.get("id") or current_user.get("user_id")
    if not user_id or not str(user_id).strip():
        raise HTTPException(status_code=401, detail="当前用户缺少有效身份")
    return str(user_id)


def _raise_http(exc: Exception, action: str) -> None:
    if isinstance(exc, FilterTemplateInvalid):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, FilterTemplateNotFound):
        raise HTTPException(status_code=404, detail="筛选模板不存在") from exc
    if isinstance(exc, FilterTemplateConflict):
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    # FilterTemplateUnavailable 与未知异常一律脱敏为 503；只记录异常类型。
    logger.error(
        "filter_template_%s_failed error_type=%s unavailable=%s",
        action, type(exc).__name__, isinstance(exc, FilterTemplateUnavailable),
    )
    raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None


def _dump(item: dict[str, Any]) -> dict[str, Any]:
    return FilterTemplateItem.model_validate(item).model_dump(mode="json")


@router.get("")
async def get_filter_templates(
    request: Request,
    page_key: PageKey = Query(...),
    current_user: dict = Depends(get_current_user),
):
    owner_id = _owner_id(current_user)
    try:
        data = await run_in_threadpool(list_templates, owner_id=owner_id, page_key=page_key)
        result = {
            "items": [_dump(item) for item in data["items"]],
            "page_key": data["page_key"],
            "max_per_page": data["max_per_page"],
        }
    except Exception as exc:
        _raise_http(exc, "list")
    return success_response(data=result, trace_id=get_trace_id(request))


@router.post("")
async def post_filter_template(
    request: Request,
    body: FilterTemplateCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    owner_id = _owner_id(current_user)
    try:
        data = await run_in_threadpool(
            create_template,
            owner_id=owner_id, page_key=body.page_key, name=body.name,
            filters=body.filters, is_default=body.is_default,
        )
        result = _dump(data)
    except Exception as exc:
        _raise_http(exc, "create")
    return success_response(data=result, message="筛选模板已保存", trace_id=get_trace_id(request))


@router.put("/{template_id}")
async def put_filter_template(
    request: Request,
    template_id: str,
    body: FilterTemplateUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    owner_id = _owner_id(current_user)
    try:
        data = await run_in_threadpool(
            update_template,
            owner_id=owner_id, template_id=template_id, version=body.version,
            name=body.name, filters=body.filters, is_default=body.is_default,
        )
        result = _dump(data)
    except Exception as exc:
        _raise_http(exc, "update")
    return success_response(data=result, message="筛选模板已更新", trace_id=get_trace_id(request))


@router.delete("/{template_id}")
async def delete_filter_template(
    request: Request,
    template_id: str,
    version: int = Query(..., ge=1),
    current_user: dict = Depends(get_current_user),
):
    owner_id = _owner_id(current_user)
    try:
        data = await run_in_threadpool(
            delete_template, owner_id=owner_id, template_id=template_id, version=version,
        )
    except Exception as exc:
        _raise_http(exc, "delete")
    return success_response(data=data, message="筛选模板已删除", trace_id=get_trace_id(request))
