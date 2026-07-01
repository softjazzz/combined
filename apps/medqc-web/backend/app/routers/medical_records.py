"""
病案数据 API 路由聚合入口。

只负责：
- 鉴权
- 路由挂载
- 少量兼容性导出
"""

from fastapi import APIRouter, Depends

from ..core.security import require_roles
from ..services.medical_records.shared import (
    build_demo_workstation_records as _build_demo_workstation_records,
    filter_demo_records as _filter_demo_records,
)

from .medical_records_query import router as medical_records_query_router
from .medical_records_detail import router as medical_records_detail_router
from .medical_records_maintenance import router as medical_records_maintenance_router
from .medical_records_export import router as medical_records_export_router

router = APIRouter(
    prefix="/api/medical-records",
    tags=["病案数据"],
    dependencies=[Depends(require_roles("admin", "qc_manager", "doctor", "reviewer", "sync_admin", "super_admin"))],
)

router.include_router(medical_records_query_router)
router.include_router(medical_records_detail_router)
router.include_router(medical_records_maintenance_router)
router.include_router(medical_records_export_router)
