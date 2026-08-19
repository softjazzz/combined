"""产品离线激活 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user, require_admin
from ..services.product_activation import (
    ProductActivationError,
    get_product_activation_service,
)


router = APIRouter(prefix="/api/v1/product-activation", tags=["product-activation"])


class ProductActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_code: str = Field(..., min_length=8, max_length=20000)


@router.get("/status")
async def get_product_activation_status(
    request: Request,
    _: dict[str, Any] = Depends(get_current_user),
):
    return success_response(
        data=get_product_activation_service().status(),
        message="获取产品激活状态成功",
        trace_id=get_trace_id(request),
    )


@router.post("/activate")
async def activate_product(
    request: Request,
    payload: ProductActivationRequest,
    _: dict[str, Any] = Depends(require_admin),
):
    try:
        data = get_product_activation_service().activate(payload.activation_code)
    except ProductActivationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="激活码无效或已过期，请核对激活码后重试",
        ) from exc
    return success_response(
        data=data,
        message="产品激活成功",
        trace_id=get_trace_id(request),
    )
