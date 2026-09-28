"""规则集版本路由（V3.6 P1-E1 规则集版本发布合同第 6 节）。

- GET    /api/v1/rule-set-versions?rule_set_key=            版本列表（标明当前版本与草稿）
- GET    /api/v1/rule-set-versions/{key}/draft              草稿详情
- GET    /api/v1/rule-set-versions/{key}/{version}          版本详情（含解析结果）
- POST   /api/v1/rule-set-versions/{key}/draft              从基础版本创建草稿（已有草稿 409 draft_exists）
- PUT    /api/v1/rule-set-versions/{key}/draft              修改草稿（version_seq CAS）
- DELETE /api/v1/rule-set-versions/{key}/draft?version_seq= 删除草稿（version_seq CAS）
- POST   /api/v1/rule-set-versions/{key}/draft/publish      发布 {version, note}
- POST   /api/v1/rule-set-versions/{key}/{version}/retire   下线（不能下线当前/内置版本）
读取需登录；写操作沿用规则管理路由的 admin/qc_manager 角色要求。数据库故障固定脱敏为 503。
响应中的 entries（含列表里的草稿）附加只读派生字段 executable、qc_point、source_document；写接口 entries 只接受 rule_id/state。
"""

from __future__ import annotations

import logging
from urllib.parse import quote
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from ..core.permissions import UserRole, require_role
from ..core.audit import audit_event
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user
from ..services.rule_set_version_service import (
    RuleSetVersionConflict,
    RuleSetVersionInvalid,
    RuleSetVersionNotFound,
    RuleSetVersionUnavailable,
    create_draft,
    delete_draft,
    get_draft,
    get_draft_export_snapshot,
    get_version_detail,
    import_draft_snapshot,
    list_versions,
    preflight_draft_import_snapshot,
    publish_draft,
    retire_version,
    update_draft,
    with_executable_flags,
)
from ..services.rule_set_version_excel_service import (
    ExcelIssue,
    MAX_FILE_BYTES,
    RuleSetVersionExcelInvalid,
    build_workbook,
    parse_workbook,
    validate_readonly_metadata,
)

router = APIRouter(prefix="/api/v1/rule-set-versions", tags=["rule-set-versions"])
logger = logging.getLogger(__name__)

_UNAVAILABLE_DETAIL = "规则集版本服务暂不可用，请稍后重试"
_MANAGER_ROLES = [UserRole.ADMIN, UserRole.QC_MANAGER]


class RuleSetEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: StrictStr
    state: StrictStr


class DraftCreateRequest(BaseModel):
    """base_version 缺省为当前版本；entries 缺省复制基础版本内容。"""

    model_config = ConfigDict(extra="forbid")

    base_version: Optional[StrictStr] = None
    entries: Optional[list[RuleSetEntry]] = None
    note: Optional[StrictStr] = None


class DraftUpdateRequest(BaseModel):
    """未传或为 null 的字段保持不变；version_seq 用于 CAS。"""

    model_config = ConfigDict(extra="forbid")

    version_seq: StrictInt = Field(..., ge=1)
    entries: Optional[list[RuleSetEntry]] = None
    note: Optional[StrictStr] = None


class DraftPublishRequest(BaseModel):
    """version 由发布人填写；version_seq 可选，传入时对草稿做 CAS。"""

    model_config = ConfigDict(extra="forbid")

    version: StrictStr
    note: Optional[StrictStr] = None
    version_seq: Optional[StrictInt] = Field(default=None, ge=1)


def _actor(current_user: dict) -> str:
    """与任务路由一致：真实认证字段 id 优先，兼容历史 user_id。"""
    user_id = current_user.get("id") or current_user.get("user_id")
    if not user_id or not str(user_id).strip():
        raise HTTPException(status_code=401, detail="当前用户缺少有效身份")
    return str(user_id)


def _entries(entries: Optional[list[RuleSetEntry]]) -> Optional[list[dict[str, Any]]]:
    return None if entries is None else [item.model_dump() for item in entries]


def _raise_http(exc: Exception, action: str) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, RuleSetVersionInvalid):
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": str(exc), "problems": exc.problems},
        ) from exc
    if isinstance(exc, RuleSetVersionNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, RuleSetVersionConflict):
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    # RuleSetVersionUnavailable 与未知异常一律脱敏为 503；只记录异常类型。
    logger.error(
        "rule_set_version_%s_failed error_type=%s unavailable=%s",
        action, type(exc).__name__, isinstance(exc, RuleSetVersionUnavailable),
    )
    raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from None


def _flagged(rule_set_key: str, data: Any) -> Any:
    """响应 entries（含列表中的草稿）附加只读派生字段（可执行标记与质控点名称/来源文书），由服务层给出。"""
    if not isinstance(data, dict):
        return data
    if isinstance(data.get("draft"), dict):
        data = {**data, "draft": with_executable_flags(rule_set_key, data["draft"])}
    if isinstance(data.get("entries"), list):
        data = with_executable_flags(rule_set_key, data)
    return data


def _with_flags(func: Any, rule_set_key: str, *args: Any, **kwargs: Any) -> Any:
    return _flagged(rule_set_key, func(rule_set_key, *args, **kwargs))


def _ok(request: Request, data: Any, message: str = "success"):
    return success_response(data=data, message=message, trace_id=get_trace_id(request))


def _json(data: Any) -> Any:
    """datetime 转 ISO 字符串，其余原样返回。"""
    if isinstance(data, dict):
        return {key: _json(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_json(item) for item in data]
    if hasattr(data, "isoformat"):
        return data.isoformat()
    return data


def _xlsx_response(content: bytes, filename: str) -> Response:
    encoded = quote(filename)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _raise_import_http(exc: Exception) -> None:
    if isinstance(exc, RuleSetVersionExcelInvalid):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "excel_validation_failed",
                "message": str(exc),
                "issues": [issue.as_dict() for issue in exc.issues],
            },
        ) from exc
    if isinstance(exc, RuleSetVersionInvalid):
        problems = exc.problems or [str(exc)]
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "message": str(exc),
                "issues": [
                    {
                        "sheet": "质控点",
                        "row": None,
                        "field": None,
                        "code": exc.code,
                        "message": problem,
                    }
                    for problem in problems
                ],
            },
        ) from exc
    _raise_http(exc, "excel_import")


@router.get("")
async def get_rule_set_versions(
    request: Request,
    rule_set_key: str = Query(..., min_length=1, max_length=96),
    current_user: dict = Depends(get_current_user),
):
    try:
        data = await run_in_threadpool(_with_flags, list_versions, rule_set_key)
    except Exception as exc:
        _raise_http(exc, "list")
    return _ok(request, _json(data))


@router.get("/{rule_set_key}/draft")
async def get_rule_set_draft(
    request: Request,
    rule_set_key: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = await run_in_threadpool(_with_flags, get_draft, rule_set_key)
    except Exception as exc:
        _raise_http(exc, "draft_get")
    return _ok(request, _json(data))


@router.get("/{rule_set_key}/draft/export")
async def export_rule_set_draft(
    request: Request,
    rule_set_key: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        exported = await run_in_threadpool(get_draft_export_snapshot, rule_set_key)
        snapshot = with_executable_flags(rule_set_key, exported["snapshot"])
        content = await run_in_threadpool(
            build_workbook,
            snapshot,
            base_version=exported["base_version"],
            base_content_digest=exported["base_content_digest"],
        )
    except Exception as exc:
        _raise_http(exc, "draft_export")
    audit_event(
        request,
        action="rule_set_versions.draft.export",
        resource="qc_rule_set_versions",
        outcome="success",
        details={
            "rule_set_key": rule_set_key,
            "base_version": exported["base_version"],
            "draft_version_seq": snapshot["version_seq"],
            "entry_count": len(snapshot["entries"]),
        },
        current_user=current_user,
    )
    return _xlsx_response(content, f"{rule_set_key}-draft-v{snapshot['version_seq']}.xlsx")


@router.get("/{rule_set_key}/{version}/export")
async def export_rule_set_version(
    request: Request,
    rule_set_key: str,
    version: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        snapshot = await run_in_threadpool(_with_flags, get_version_detail, rule_set_key, version)
        content = await run_in_threadpool(
            build_workbook,
            snapshot,
            base_version=snapshot["version"],
            base_content_digest=snapshot["content_digest"],
        )
    except Exception as exc:
        _raise_http(exc, "version_export")
    audit_event(
        request,
        action="rule_set_versions.version.export",
        resource="qc_rule_set_versions",
        outcome="success",
        details={
            "rule_set_key": rule_set_key,
            "version": snapshot["version"],
            "base_version": snapshot["version"],
            "entry_count": len(snapshot["entries"]),
        },
        current_user=current_user,
    )
    return _xlsx_response(content, f"{rule_set_key}-{version}.xlsx")


@router.get("/{rule_set_key}/{version}")
async def get_rule_set_version(
    request: Request,
    rule_set_key: str,
    version: str,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = await run_in_threadpool(_with_flags, get_version_detail, rule_set_key, version)
    except Exception as exc:
        _raise_http(exc, "detail")
    return _ok(request, _json(data))


@router.post("/{rule_set_key}/draft")
@require_role(_MANAGER_ROLES)
async def post_rule_set_draft(
    request: Request,
    rule_set_key: str,
    body: DraftCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(
            _with_flags, create_draft, rule_set_key, actor=actor, base_version=body.base_version,
            entries=_entries(body.entries), note=body.note,
        )
    except Exception as exc:
        _raise_http(exc, "draft_create")
    return _ok(request, _json(data), "规则集草稿已创建")


@router.post("/{rule_set_key}/draft/import")
@require_role(_MANAGER_ROLES)
async def import_rule_set_draft(
    request: Request,
    rule_set_key: str,
    file: UploadFile = File(..., description="规则集版本 .xlsx 工作簿"),
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        if not (file.filename or "").lower().endswith(".xlsx"):
            raise RuleSetVersionExcelInvalid(
                "规则集版本工作簿校验失败",
                issues=[ExcelIssue("文件", None, None, "invalid_extension", "仅支持 .xlsx 文件")],
            )
        content = await file.read(MAX_FILE_BYTES + 1)
        parsed = await run_in_threadpool(
            parse_workbook, content, expected_rule_set_key=rule_set_key,
        )
        preflight = await run_in_threadpool(
            preflight_draft_import_snapshot,
            rule_set_key,
            base_version=parsed.base_version,
            base_content_digest=parsed.base_content_digest,
            entries=parsed.entries,
        )
        catalog = with_executable_flags(rule_set_key, {"entries": preflight["catalog_entries"]})["entries"]
        await run_in_threadpool(validate_readonly_metadata, parsed, catalog)
        data = await run_in_threadpool(
            _with_flags,
            import_draft_snapshot,
            rule_set_key,
            actor=actor,
            base_version=parsed.base_version,
            base_content_digest=parsed.base_content_digest,
            entries=parsed.entries,
            expected_draft_version=parsed.expected_draft_version,
            expected_draft_version_seq=parsed.expected_draft_version_seq,
        )
    except Exception as exc:
        _raise_import_http(exc)
    finally:
        await file.close()
    audit_event(
        request,
        action="rule_set_versions.draft.import",
        resource="qc_rule_set_versions",
        outcome="success",
        details={
            "rule_set_key": rule_set_key,
            "base_version": data["base_version"],
            "draft_version_seq": data["version_seq"],
            "entry_count": len(data["entries"]),
        },
        current_user=current_user,
    )
    return _ok(request, _json(data), "规则集草稿已导入")


@router.put("/{rule_set_key}/draft")
@require_role(_MANAGER_ROLES)
async def put_rule_set_draft(
    request: Request,
    rule_set_key: str,
    body: DraftUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(
            _with_flags, update_draft, rule_set_key, actor=actor, version_seq=body.version_seq,
            entries=_entries(body.entries), note=body.note,
        )
    except Exception as exc:
        _raise_http(exc, "draft_update")
    return _ok(request, _json(data), "规则集草稿已更新")


@router.delete("/{rule_set_key}/draft")
@require_role(_MANAGER_ROLES)
async def delete_rule_set_draft(
    request: Request,
    rule_set_key: str,
    version_seq: int = Query(..., ge=1),
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(
            delete_draft, rule_set_key, actor=actor, version_seq=version_seq,
        )
    except Exception as exc:
        _raise_http(exc, "draft_delete")
    return _ok(request, data, "规则集草稿已删除")


@router.post("/{rule_set_key}/draft/publish")
@require_role(_MANAGER_ROLES)
async def post_rule_set_draft_publish(
    request: Request,
    rule_set_key: str,
    body: DraftPublishRequest,
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(
            _with_flags, publish_draft, rule_set_key, actor=actor, version=body.version,
            note=body.note, version_seq=body.version_seq,
        )
    except Exception as exc:
        _raise_http(exc, "publish")
    return _ok(request, _json(data), "规则集版本已发布")


@router.post("/{rule_set_key}/{version}/retire")
@require_role(_MANAGER_ROLES)
async def post_rule_set_version_retire(
    request: Request,
    rule_set_key: str,
    version: str,
    current_user: dict = Depends(get_current_user),
):
    actor = _actor(current_user)
    try:
        data = await run_in_threadpool(_with_flags, retire_version, rule_set_key, version, actor=actor)
    except Exception as exc:
        _raise_http(exc, "retire")
    return _ok(request, _json(data), "规则集版本已下线")
