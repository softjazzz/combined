"""病案数据 - 导出子域。"""

from fastapi import APIRouter, Depends, HTTPException, Request

from ..core.pagination import page_param, page_size_param
from ..core.roles import effective_roles
from ..core.security import require_roles
from ..services.medical_records.export_service import (
    get_frontpage_sheet,
    get_schema,
    get_table_data,
)
from .medical_records_common import raise_medical_records_http_error

router = APIRouter(tags=["病案数据-导出"])

_TABLE_DATA_ROLES = ("admin", "sync_admin", "super_admin")
_GLOBAL_ROLES = frozenset({"sync_admin", "super_admin"})


def _resolve_table_data_scope(current_user: dict) -> tuple[str | None, bool]:
    """解析通用查表的机构隔离范围。

    - sync_admin / super_admin 具备全院区访问权限；
    - 绑定了 institute_id 的非全局管理员（含单院区 admin）强制按其 institute_id 过滤；
    - 未绑定 institute_id 的全局 admin 允许全院区查看白名单业务表。
    """
    roles = set(effective_roles(current_user.get("roles")))
    if not roles.intersection(_TABLE_DATA_ROLES):
        raise HTTPException(status_code=403, detail="无权访问病案表数据接口")
    if roles.intersection(_GLOBAL_ROLES):
        return None, False
    user_institute = str(current_user.get("institute_id") or "").strip()
    if user_institute:
        return user_institute, True
    if "admin" in roles:
        return None, False
    raise HTTPException(status_code=403, detail="非全局用户缺少可信机构范围")


@router.get("/schema", dependencies=[Depends(require_roles(*_TABLE_DATA_ROLES))])
async def get_schema_api():
    try:
        return get_schema()
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/table-data/{table_name}")
async def get_table_data_api(
    table_name: str,
    page: int = page_param(),
    page_size: int = page_size_param(),
    current_user: dict = Depends(require_roles(*_TABLE_DATA_ROLES)),
):
    try:
        institute_id, require_institute_scope = _resolve_table_data_scope(current_user)
        return get_table_data(
            table_name,
            page=page,
            page_size=page_size,
            institute_id=institute_id,
            require_institute_scope=require_institute_scope,
        )
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/frontpage-sheet/{patient_id}/{visit_id}")
async def get_frontpage_sheet_api(request: Request, patient_id: str, visit_id: str):
    try:
        identity = getattr(request.state, "doctor_case_identity", None)
        institute = request.query_params.get("institute_id")
        if identity and institute and institute != identity["institute_id"]:
            raise HTTPException(403, "clinical_case_identity_forbidden")
        if identity:
            institute = identity["institute_id"]
        else:
            current_user = getattr(request.state, "current_user", None)
            if isinstance(current_user, dict):
                roles = set(effective_roles(current_user.get("roles")))
                if not roles.intersection({"admin", "sync_admin", "super_admin"}):
                    user_institute = str(current_user.get("institute_id") or "").strip()
                    if user_institute:
                        if institute and institute != user_institute:
                            raise HTTPException(403, "clinical_case_identity_forbidden")
                        institute = user_institute
        return get_frontpage_sheet(patient_id, visit_id, **({"institute_id": institute} if institute else {}))
    except Exception as exc:
        raise_medical_records_http_error(exc)
