from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.rate_limit import enforce_rate_limit
from ..core.security import require_roles
from ..core.upload_security import validate_uploaded_file
from ..services.drg_grouping_service import get_drg_grouping_service as _get_drg_grouping_service
from ..services.drg_config_store import get_drg_config_store as _get_drg_config_store
from ..services.drg_demo_store import get_demo_drg_store as _get_demo_drg_store

from . import drg_analysis as drg_analysis_router
from . import drg_config as drg_config_router
from . import drg_operations as drg_operations_router

router = APIRouter(
    prefix="/api/v1/drg",
    tags=["drg"],
    dependencies=[Depends(require_roles("admin", "qc_manager", "doctor", "reviewer"))],
)


def get_demo_drg_store():
    return _get_demo_drg_store()


def get_drg_config_store():
    return _get_drg_config_store()


def get_drg_grouping_service():
    return _get_drg_grouping_service()


router.include_router(drg_config_router.router)
router.include_router(drg_analysis_router.router)
router.include_router(drg_operations_router.router)
