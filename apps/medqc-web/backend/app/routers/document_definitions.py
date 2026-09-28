"""V3.6 文书定义列表、模板下载与原子导入。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from ..core.audit import audit_event
from ..core.response import get_trace_id, success_response
from ..core.security import get_current_user, require_roles
from ..services.document_definition_excel_service import (
    MAX_UPLOAD_BYTES,
    DocumentDefinitionExcelError,
    build_document_definition_template,
    parse_document_definition_workbook,
)
from ..services.document_definition_service import (
    DocumentDefinitionConflict,
    DocumentDefinitionInvalid,
    DocumentDefinitionUnavailable,
    import_document_definitions,
    list_document_definitions,
)

router = APIRouter(
    prefix="/api/v1/document-definitions",
    tags=["document-definitions"],
    dependencies=[Depends(require_roles("admin", "qc_manager"))],
)
logger = logging.getLogger(__name__)

_TEMPLATE_FILENAME = "V3.6-document-definition-import-template.xlsx"
_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class DocumentDefinitionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    code: str
    name: str
    category: str
    template_content: str
    import_batch_id: str
    created_by: str
    created_at: datetime


def _actor(current_user: dict) -> str:
    value = current_user.get("id") or current_user.get("user_id") or current_user.get("email")
    if not value or not str(value).strip():
        raise HTTPException(status_code=401, detail="当前用户缺少有效身份")
    return str(value).strip()


def _validation_detail(exc: DocumentDefinitionExcelError) -> dict:
    return {
        "code": "document_definition_import_invalid",
        "message": "文书定义导入校验失败",
        "problems": [problem.as_dict() for problem in exc.problems],
    }


def _raise_http(exc: Exception, action: str) -> None:
    if isinstance(exc, DocumentDefinitionExcelError):
        raise HTTPException(status_code=422, detail=_validation_detail(exc)) from exc
    if isinstance(exc, DocumentDefinitionInvalid):
        if action == "list":
            raise HTTPException(status_code=422, detail={
                "code": "document_definition_query_invalid", "message": str(exc),
            }) from exc
        raise HTTPException(status_code=422, detail={
            "code": "document_definition_import_invalid", "message": str(exc), "problems": [],
        }) from exc
    if isinstance(exc, DocumentDefinitionConflict):
        raise HTTPException(status_code=409, detail={
            "code": exc.code,
            "message": str(exc),
            "codes": exc.codes,
        }) from exc
    logger.error(
        "document_definition_%s_failed error_type=%s unavailable=%s",
        action, type(exc).__name__, isinstance(exc, DocumentDefinitionUnavailable),
    )
    if action == "import":
        raise HTTPException(
            status_code=503,
            detail="文书定义导入结果未确认，请刷新列表核对，勿直接重复导入",
        ) from None
    raise HTTPException(status_code=503, detail="文书定义服务暂不可用，请稍后重试") from None


def _dump(item: dict) -> dict:
    normalized = dict(item)
    created_at = normalized.get("created_at")
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        normalized["created_at"] = created_at.replace(tzinfo=timezone.utc)
    return DocumentDefinitionItem.model_validate(normalized).model_dump(mode="json")


@router.get("")
async def get_document_definitions(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
):
    del current_user
    try:
        data = await run_in_threadpool(
            list_document_definitions, page=page, page_size=page_size, q=q,
        )
        result = {**data, "items": [_dump(item) for item in data["items"]]}
    except Exception as exc:
        _raise_http(exc, "list")
    return success_response(data=result, trace_id=get_trace_id(request))


@router.get("/import-template")
async def get_document_definition_import_template(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    del request, current_user
    try:
        content = await run_in_threadpool(build_document_definition_template)
    except Exception as exc:
        _raise_http(exc, "template")
    return Response(
        content=content,
        media_type=_XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{_TEMPLATE_FILENAME}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/import")
async def post_document_definition_import(
    request: Request,
    file: UploadFile = File(..., description="V3.6 文书定义 .xlsx 文件"),
    current_user: dict = Depends(get_current_user),
):
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".xlsx"):
        await file.close()
        raise HTTPException(status_code=422, detail={
            "code": "document_definition_import_invalid",
            "message": "文书定义导入校验失败",
            "problems": [{
                "sheet": "文件", "row": 0, "field": "文件",
                "code": "file_type_invalid", "message": "仅支持 .xlsx 文件",
            }],
        })
    actor = _actor(current_user)
    try:
        try:
            content = await file.read(MAX_UPLOAD_BYTES + 1)
            definitions = await run_in_threadpool(parse_document_definition_workbook, content)
            data = await run_in_threadpool(
                import_document_definitions, actor=actor, definitions=definitions,
            )
            result = {**data, "items": [_dump(item) for item in data["items"]]}
        except Exception as exc:
            _raise_http(exc, "import")
    finally:
        await file.close()
    audit_event(
        request,
        action="document_definition.import",
        resource="qc_document_definition",
        outcome="success",
        details={
            "import_batch_id": result["import_batch_id"],
            "imported_count": result["imported_count"],
        },
        current_user=current_user,
    )
    return success_response(
        data=result, message="文书定义已导入", trace_id=get_trace_id(request),
    )
