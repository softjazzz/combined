from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services.payment_monitoring_service import PaymentMonitoringService

router = APIRouter(prefix="/api/v1/payment-monitoring", tags=["payment-monitoring"])


class PaymentMonitoringRequest(BaseModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)
    payment_standard: Optional[Dict[str, Any]] = None


@router.post("/simulate")
async def simulate_payment_monitoring(
    request: Request,
    payload: PaymentMonitoringRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _ = current_user
    result = PaymentMonitoringService().simulate(
        payload.records,
        payment_standard=payload.payment_standard,
    )
    return success_response(data=result, trace_id=get_trace_id(request))
