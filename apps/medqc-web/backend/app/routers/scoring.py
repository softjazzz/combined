"""评分标准与计分路由（V3.6 P2-S 评分标准与计分服务合同第 3、4 节）。

- GET    /api/v1/scoring/scenes                          场景与可用规则集
- GET    /api/v1/scoring/standards?scene=&status=        标准列表（不含条目）
- GET    /api/v1/scoring/standards/{id}                  标准详情（含项目组与条目）
- POST   /api/v1/scoring/standards                       新建草稿
- PUT    /api/v1/scoring/standards/{id}                  修改草稿基本信息（version_seq CAS）
- PUT    /api/v1/scoring/standards/{id}/items            项目组与条目整表保存（version_seq CAS）
- POST   /api/v1/scoring/standards/{id}/copy             复制为新草稿 {name}
- POST   /api/v1/scoring/standards/{id}/activate         启用并设为场景默认 {version_seq, replace_mode}
- POST   /api/v1/scoring/standards/{id}/set-default      已启用标准直接设为场景默认
- POST   /api/v1/scoring/standards/{id}/archive          归档 {version_seq}
- DELETE /api/v1/scoring/standards/{id}?version_seq=     删除草稿
- GET    /api/v1/scoring/case?institute_id&patient_id&visit_id&scene=   单病历计分（不落库）
读取需登录；写操作沿用规则集版本路由的 admin/qc_manager 角色要求。数据库故障固定脱敏为 503。
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr
from starlette.concurrency import run_in_threadpool

from ..core.permissions import UserRole, require_role
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services import scoring_service
from ..services.scoring_standard_service import (
    ScoringStandardConflict,
    ScoringStandardInvalid,
    ScoringStandardNotFound,
    ScoringStandardUnavailable,
    activate_standard,
    archive_standard,
    copy_standard,
    create_standard,
    delete_standard,
    get_standard,
    list_standards,
    save_items,
    scene_catalog,
    set_default_standard,
    update_standard,
)

router = APIRouter(prefix="/api/v1/scoring", tags=["scoring"])
logger = logging.getLogger(__name__)

_UNAVAILABLE_DETAIL = "评分服务暂不可用，请稍后重试"
_MANAGER_ROLES = [UserRole.ADMIN, UserRole.QC_MANAGER]

Number = Union[StrictInt, StrictFloat]
Scene = Literal["running", "final", "outpatient"]


class GradeBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    min_score: Number
    max_score: Number


class StandardCreateRequest(BaseModel):
    """rule_set_key 缺省时，场景只有一个可用规则集才自动选定。"""

    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    scene: StrictStr
    rule_set_key: Optional[StrictStr] = None
    base_score: Number
    grade_bands: list[GradeBand]
    veto_grade: StrictStr


class StandardUpdateRequest(BaseModel):
    """未传或为 null 的字段保持不变；version_seq 用于 CAS。场景与规则集创建后不可改。"""

    model_config = ConfigDict(extra="forbid")

    version_seq: StrictInt = Field(..., ge=1)
    name: Optional[StrictStr] = None
    base_score: Optional[Number] = None
    grade_bands: Optional[list[GradeBand]] = None
    veto_grade: Optional[StrictStr] = None


class ScoringGroupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_name: StrictStr
    max_deduction: Optional[Number] = None
    sort_order: Optional[StrictInt] = None


class ScoringItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_name: StrictStr
    rule_id: StrictStr
    deduction: Number
    is_veto: StrictBool = False
    enabled: StrictBool = True


class ItemsSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_seq: StrictInt = Field(..., ge=1)
    groups: list[ScoringGroupIn]
    items: list[ScoringItemIn]


class CopyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr


class ActivateRequest(BaseModel):
    """replace_mode：archive 归档原默认标准（默认）；undefault 只取消其默认标记。"""

    model_config = ConfigDict(extra="forbid")

    version_seq: StrictInt = Field(..., ge=1)
    replace_mode: Literal["archive", "undefault"] = "archive"


class ArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_seq: StrictInt = Field(..., ge=1)


def _actor(current_user: dict) -> str:
    """与任务路由一致：真实认证字段 id 优先，兼容历史 user_id。"""
    user_id = current_user.get("id") or current_user.get("user_id")
    if not user_id or not str(user_id).strip():
        raise HTTPException(status_code=401, detail="当前用户缺少有效身份")
    return str(user_id)


def _raise_http(exc: Exception, action: str) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, ScoringStandardInvalid):
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc), "problems": exc.problems},
        ) from exc
    if isinstance(exc, ScoringStandardNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ScoringStandardConflict):
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    # 不可用与未知异常一律脱敏为 503；只记录异常类型。
    logger.error(
        "scoring_%s_failed error_type=%s unavailable=%s",
        action, type(exc).__name__, isinstance(exc, ScoringStandardUnavailable),
    )
    raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None


def _json(data: Any) -> Any:
    """datetime 转 ISO 字符串，其余原样返回。"""
    if isinstance(data, dict):
        return {key: _json(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_json(item) for item in data]
    if hasattr(data, "isoformat"):
        return data.isoformat()
    return data


def _ok(request: Request, data: Any, message: str = "success"):
    return success_response(data=_json(data), message=message, trace_id=get_trace_id(request))


def _dump(models: Optional[list[BaseModel]], *, exclude_none: bool = False) -> Optional[list[dict[str, Any]]]:
    return None if models is None else [item.model_dump(exclude_none=exclude_none) for item in models]


@router.get("/scenes")
async def get_scoring_scenes(request: Request, current_user: dict = Depends(get_current_user)):
    return _ok(request, {"items": scene_catalog()})


@router.get("/standards")
async def get_scoring_standards(
    request: Request,
    scene: Optional[Scene] = Query(None),
    status: Optional[Literal["draft", "active", "archived"]] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    try:
        data = await run_in_threadpool(list_standards, scene=scene, status=status)
    except Exception as exc:
        _raise_http(exc, "list")
    return _ok(request, data)


@router.get("/standards/{standard_id}")
async def get_scoring_standard(
    request: Request, standard_id: str, current_user: dict = Depends(get_current_user),
):
    try:
        data = await run_in_threadpool(get_standard, standard_id)
    except Exception as exc:
        _raise_http(exc, "detail")
    return _ok(request, data)


@router.post("/standards")
@require_role(_MANAGER_ROLES)
async def post_scoring_standard(
    request: Request, body: StandardCreateRequest, current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(
            create_standard, actor=actor, name=body.name, scene=body.scene,
            rule_set_key=body.rule_set_key, base_score=body.base_score,
            grade_bands=_dump(body.grade_bands), veto_grade=body.veto_grade,
        )
    except Exception as exc:
        _raise_http(exc, "create")
    return _ok(request, data, "评分标准草稿已创建")


@router.put("/standards/{standard_id}")
@require_role(_MANAGER_ROLES)
async def put_scoring_standard(
    request: Request, standard_id: str, body: StandardUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(
            update_standard, standard_id, actor=actor, version_seq=body.version_seq, name=body.name,
            base_score=body.base_score, grade_bands=_dump(body.grade_bands), veto_grade=body.veto_grade,
        )
    except Exception as exc:
        _raise_http(exc, "update")
    return _ok(request, data, "评分标准已更新")


@router.put("/standards/{standard_id}/items")
@require_role(_MANAGER_ROLES)
async def put_scoring_items(
    request: Request, standard_id: str, body: ItemsSaveRequest,
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(
            save_items, standard_id, actor=actor, version_seq=body.version_seq,
            groups=_dump(body.groups, exclude_none=True), items=_dump(body.items),
        )
    except Exception as exc:
        _raise_http(exc, "items_save")
    return _ok(request, data, "评分条目已保存")


@router.post("/standards/{standard_id}/copy")
@require_role(_MANAGER_ROLES)
async def post_scoring_standard_copy(
    request: Request, standard_id: str, body: CopyRequest, current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(copy_standard, standard_id, actor=actor, name=body.name)
    except Exception as exc:
        _raise_http(exc, "copy")
    return _ok(request, data, "评分标准已复制为草稿")


@router.post("/standards/{standard_id}/activate")
@require_role(_MANAGER_ROLES)
async def post_scoring_standard_activate(
    request: Request, standard_id: str, body: ActivateRequest,
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(
            activate_standard, standard_id, actor=actor, version_seq=body.version_seq,
            replace_mode=body.replace_mode,
        )
    except Exception as exc:
        _raise_http(exc, "activate")
    return _ok(request, data, "评分标准已启用")


@router.post("/standards/{standard_id}/archive")
@require_role(_MANAGER_ROLES)
async def post_scoring_standard_archive(
    request: Request, standard_id: str, body: ArchiveRequest,
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(archive_standard, standard_id, actor=actor, version_seq=body.version_seq)
    except Exception as exc:
        _raise_http(exc, "archive")
    return _ok(request, data, "评分标准已归档")


@router.post("/standards/{standard_id}/set-default")
@require_role(_MANAGER_ROLES)
async def post_scoring_standard_set_default(
    request: Request, standard_id: str, body: ActivateRequest,
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(
            set_default_standard, standard_id, actor=actor, version_seq=body.version_seq,
            replace_mode=body.replace_mode,
        )
    except Exception as exc:
        _raise_http(exc, "set_default")
    return _ok(request, data, "评分标准已设为默认")


@router.delete("/standards/{standard_id}")
@require_role(_MANAGER_ROLES)
async def delete_scoring_standard(
    request: Request, standard_id: str, version_seq: int = Query(..., ge=1),
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(delete_standard, standard_id, actor=actor, version_seq=version_seq)
    except Exception as exc:
        _raise_http(exc, "delete")
    return _ok(request, data, "评分标准草稿已删除")


@router.get("/case")
async def get_case_score(
    request: Request,
    institute_id: str = Query(..., min_length=1, max_length=128),
    patient_id: str = Query(..., min_length=1, max_length=128),
    visit_id: str = Query(..., min_length=1, max_length=128),
    scene: Scene = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """按单病历最新 ready 结果与场景默认标准计分；不落库。"""
    identity = tuple(value.strip() for value in (institute_id, patient_id, visit_id))
    if not all(identity):
        raise HTTPException(status_code=422, detail="病历三坐标无效")
    try:
        data = await run_in_threadpool(
            scoring_service.score_case,
            institute_id=identity[0], patient_id=identity[1], visit_id=identity[2], scene=scene,
        )
    except Exception as exc:
        _raise_http(exc, "case")
    return _ok(request, data)
