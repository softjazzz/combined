"""病案数据 - 导出子域。"""

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ..core.pagination import page_param, page_size_param
from ..core.roles import effective_roles
from ..core.security import require_roles, resolve_current_user_from_token
from ..services.medical_records.detail_service import inspect_institute_scope
from ..services.medical_records.export_service import (
    get_frontpage_sheet,
    get_schema,
    get_table_data,
)
from .medical_records_common import raise_medical_records_http_error

router = APIRouter(tags=["病案数据-导出"])

_TABLE_DATA_ROLES = ("admin", "sync_admin", "super_admin")


def _resolve_table_data_scope(current_user: dict) -> tuple[str | None, bool]:
    """解析通用查表的机构隔离范围。

    统一全局视角条件：
    ("sync_admin" in roles) or (bool(roles & {"admin", "super_admin"}) and not actor_institute_id)
    - 满足全局视角条件返回 (None, False)；
    - 绑定了 institute_id 的 admin / super_admin 强制按本院区过滤；
    - 非全局且缺少可信机构范围则 fail-closed 403。
    """
    roles = set(effective_roles(current_user.get("roles")))
    if not roles.intersection(_TABLE_DATA_ROLES):
        raise HTTPException(status_code=403, detail="无权访问病案表数据接口")

    resolved = inspect_institute_scope(current_user)
    if resolved.kind == "global":
        return None, False
    if resolved.kind == "institute" and resolved.institute_id:
        return resolved.institute_id, True
    raise HTTPException(status_code=403, detail="非全局用户缺少可信机构范围")


def _resolve_request_user(request: Request) -> dict | None:
    cached = getattr(request.state, "current_user", None)
    if isinstance(cached, dict):
        return cached
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            user = resolve_current_user_from_token(token)
            request.state.current_user = user
            return user
    return None


@router.get("/schema", dependencies=[Depends(require_roles(*_TABLE_DATA_ROLES))])
def get_schema_api():
    try:
        return get_schema()
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/table-data/{table_name}")
def get_table_data_api(
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


def _get_frontpage_sheet_sync(request: Request, patient_id: str, visit_id: str):
    try:
        identity = getattr(request.state, "doctor_case_identity", None)
        institute = request.query_params.get("institute_id")
        if identity and institute and institute != identity["institute_id"]:
            raise HTTPException(403, "clinical_case_identity_forbidden")
        if identity:
            institute = identity["institute_id"]
        else:
            current_user = _resolve_request_user(request)
            if not isinstance(current_user, dict):
                raise HTTPException(401, "Authentication required")
            scope = inspect_institute_scope(current_user)
            if scope.kind == "global":
                pass
            elif scope.kind == "institute" and scope.institute_id:
                if institute and institute != scope.institute_id:
                    raise HTTPException(403, "clinical_case_identity_forbidden")
                institute = scope.institute_id
            else:
                raise HTTPException(403, "clinical_case_identity_forbidden")
        return get_frontpage_sheet(patient_id, visit_id, **({"institute_id": institute} if institute else {}))
    except Exception as exc:
        raise_medical_records_http_error(exc)


@router.get("/frontpage-sheet/{patient_id}/{visit_id}")
async def get_frontpage_sheet_api(request: Request, patient_id: str, visit_id: str):
    return await run_in_threadpool(_get_frontpage_sheet_sync, request, patient_id, visit_id)
