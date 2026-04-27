import uuid
from datetime import datetime, date
import json
from typing import Any, Dict, Optional, List
import logging

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, Query
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, or_, text

from ..core.supabase_client import get_supabase, async_execute
from ..core.security import get_current_user
from ..core.response import success_response, paginated_response, get_trace_id, ErrorCode, StatusCode
from ..schemas.records import MedicalRecordResponse
from ..storage.memory import medical_records_db
from ..core.settings import get_settings
from ..database.connection import DB_SCHEMA_MODE, SessionLocal, engine
from ..database.models.cdm import AdmissionRecord, DischargeRecord, MedicalRecordFrontpage
from ..database.models.qc import QCDefect, QCResultBiz
from ..services.bundles.emr_view import build_documents_tree, load_bundle_documents
from ..core.permissions import (
    require_permission,
    ResourceType,
    PermissionAction,
)


router = APIRouter(prefix="/api/v1/records", tags=["records"])
logger = logging.getLogger(__name__)

RECORD_UPLOAD_ALLOWED_EXTENSIONS = {".pdf", ".txt", ".doc", ".docx"}
RECORD_UPLOAD_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
RECORD_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
_EICAR_SIGNATURE = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"


def enforce_rate_limit(*_args, **_kwargs) -> None:
    # Cross-cutting rate-limit helper is deferred from this development wave.
    return None


def _validate_record_upload(file: UploadFile, content: bytes) -> None:
    filename = str(file.filename or "").strip()
    lower_name = filename.lower()
    if not any(lower_name.endswith(ext) for ext in RECORD_UPLOAD_ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件扩展名不允许")

    content_type = str(file.content_type or "").strip().lower()
    if content_type not in RECORD_UPLOAD_ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件类型不允许")

    if len(content) > RECORD_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件大小不能超过限制")

    if _EICAR_SIGNATURE in content.upper():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="检测到恶意文件特征")


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_visit_type(raw_visit_type: Any, raw_record_type: Any) -> str:
    visit_type = str(raw_visit_type or "").strip().lower()
    if visit_type in {"outpatient", "emergency"}:
        return visit_type

    record_type = str(raw_record_type or "").strip().lower()
    if "emergency" in record_type or "急诊" in record_type:
        return "emergency"
    if "outpatient" in record_type or "门诊" in record_type:
        return "outpatient"
    return ""


def _normalize_date_only(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) >= 10:
        return text[:10]
    return text


def _normalize_outpatient_item(row: Dict[str, Any]) -> Dict[str, Any]:
    visit_date = (
        _normalize_date_only(row.get("visit_date"))
        or _normalize_date_only(row.get("admission_date"))
        or _normalize_date_only(row.get("admission_datetime"))
        or _normalize_date_only(row.get("created_at"))
    )
    visit_type = _normalize_visit_type(row.get("visit_type"), row.get("record_type"))
    score = _to_float(row.get("score"))
    if score is None:
        score = _to_float(row.get("overall_score"))

    return {
        "id": row.get("id") or row.get("record_id") or row.get("visit_id") or "",
        "record_id": row.get("record_id") or row.get("mr_no") or row.get("visit_id") or row.get("id") or "",
        "patient_name": row.get("patient_name") or row.get("name") or "",
        "department": row.get("department") or row.get("department_name") or row.get("admission_dept_name") or "",
        "doctor_name": row.get("doctor_name") or row.get("attending_physician_sign") or row.get("doctor") or "",
        "visit_type": visit_type,
        "visit_date": visit_date,
        "status": row.get("status") or "pending",
        "score": score,
        "defect_count": _to_int(row.get("defect_count"), 0),
        "scoring_standard": row.get("scoring_standard") or row.get("score_standard"),
        "source": "records",
    }


def _pick_document_content(documents: List[Dict[str, Any]], keywords: List[str]) -> str:
    chunks: List[str] = []
    for doc in documents:
        haystack = " ".join(
            str(doc.get(field) or "")
            for field in (
                "document_type",
                "type",
                "category",
                "doc_type",
                "doc_name",
                "title",
                "label",
                "document_title",
            )
        ).lower()
        if any(k in haystack for k in keywords):
            content = doc.get("content") or doc.get("record_content") or doc.get("text")
            if content:
                text = str(content).strip()
                if text:
                    chunks.append(text)
    if not chunks:
        return ""
    if len(chunks) == 1:
        return chunks[0]
    return "\n\n<hr />\n\n".join(chunks)


def _workspace_schema() -> str:
    return "qc" if DB_SCHEMA_MODE == "split" else "public"


def _safe_json_loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    text = str(value).strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def _resolve_visit_identity(record_id: str) -> Dict[str, str]:
    if SessionLocal is None:
        return {}
    with SessionLocal() as session:
        for model in (MedicalRecordFrontpage, DischargeRecord, AdmissionRecord):
            row = (
                session.query(model)
                .filter(or_(model.visit_id == record_id, model.mr_no == record_id))
                .first()
            )
            if row:
                return {
                    "institute_id": str(getattr(row, "institute_id", "") or "").strip(),
                    "patient_id": str(getattr(row, "patient_id", "") or "").strip(),
                    "visit_id": str(getattr(row, "visit_id", "") or "").strip(),
                }
    return {}


def _load_bundle_payload_for_record(record_id: str) -> Dict[str, Any]:
    identity = _resolve_visit_identity(record_id)
    if not identity:
        return {}
    try:
        payload = load_bundle_documents(
            institute_id=identity["institute_id"],
            patient_id=identity["patient_id"],
            visit_id=identity["visit_id"],
            bundle_schema="public",
        )
        if list(payload.get("documents") or []):
            return payload
    except Exception as exc:
        logger.warning("从 bundle 加载病历文书失败: %s", exc)
    if engine is None:
        return {}

    def _normalize_inventory_docs(items: Any) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        for idx, item in enumerate(items or []):
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or item.get("assembled_text") or item.get("text_preview") or "").strip()
            if not content:
                continue
            doc_type = str(item.get("document_type") or item.get("doc_type") or "").strip()
            document_id = str(item.get("document_id") or item.get("id") or idx).strip()
            title = str(item.get("document_title") or item.get("doc_name") or item.get("title") or "").strip()
            docs.append(
                {
                    "id": document_id,
                    "doc_id": document_id,
                    "doc_key": str(item.get("doc_key") or f"{doc_type or 'doc'}::{document_id}").strip(),
                    "document_type": doc_type,
                    "doc_type": doc_type,
                    "document_title": title,
                    "title": title,
                    "doc_name": title,
                    "content": content,
                    "record_time": str(item.get("record_time") or item.get("display_time") or "").strip(),
                    "sort_time": str(item.get("display_time") or item.get("record_time") or "").strip(),
                    "source_table": str(item.get("source_table") or "").strip(),
                    "group_key": str(item.get("group_key") or "").strip(),
                    "has_content": True,
                    "length": len(content),
                    "sections": list(item.get("sections") or []),
                    "source_fields": list(item.get("source_fields") or []),
                    "assembly_status": str(item.get("assembly_status") or "").strip(),
                    "data_quality_flags": list(item.get("data_quality_flags") or []),
                }
            )
        return docs

    visit_id = identity.get("visit_id") or record_id
    patient_id = identity.get("patient_id") or ""
    institute_id = identity.get("institute_id") or ""
    candidates = (
        ("public.final_record_bundle", "final"),
        ("public.running_record_bundle", "running"),
    )
    for table_name, scene in candidates:
        sql = text(
            f"""
            SELECT structured_context, medical_text
            FROM {table_name}
            WHERE institute_id = :institute_id
              AND patient_id = :patient_id
              AND visit_id = :visit_id
            LIMIT 1
            """
        )
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    sql,
                    {
                        "institute_id": institute_id,
                        "patient_id": patient_id,
                        "visit_id": visit_id,
                    },
                ).mappings().first()
        except Exception as exc:
            logger.warning("从 %s 读取 bundle 结构化文书失败: %s", table_name, exc)
            continue
        if not row:
            continue
        structured = row.get("structured_context") or {}
        if not isinstance(structured, dict):
            structured = {}
        docs = _normalize_inventory_docs(structured.get("document_inventory"))
        if docs:
            return {
                "layout_version": "bundle_struct_v1",
                "documents": docs,
                "documents_tree": build_documents_tree(docs),
                "domain_bundle_hits": {scene: True},
                "empty_reason": "",
            }
        medical_text = str(row.get("medical_text") or "").strip()
        if medical_text:
            return {
                "layout_version": "bundle_struct_v1",
                "documents": [
                    {
                        "id": f"{visit_id}:{scene}",
                        "document_type": f"{scene}_bundle",
                        "document_title": "病历全文",
                        "title": "病历全文",
                        "content": medical_text,
                        "record_time": "",
                        "source_table": table_name,
                    }
                ],
                "documents_tree": [],
                "domain_bundle_hits": {scene: True},
                "empty_reason": "",
            }
    return {}


def _map_batch_item_to_review_item(item: Dict[str, Any], *, job_id: str, created_at: Any, index: int) -> Dict[str, Any]:
    status = str(item.get("status") or "").strip().lower()
    normalized_status = status if status in {"non_compliant", "uncertain", "compliant", "not_applicable"} else "uncertain"
    return {
        "id": f"{job_id}:{item.get('rule_code') or index}",
        "source": "batch_job",
        "job_id": job_id,
        "created_at": str(created_at or ""),
        "record_id": str(item.get("record_id") or item.get("visit_id") or "").strip(),
        "visit_id": str(item.get("visit_id") or item.get("record_id") or "").strip(),
        "patient_name": str(item.get("patient_name") or "").strip(),
        "rule_code": str(item.get("rule_code") or "").strip(),
        "rule_name": str(item.get("rule_name") or "").strip(),
        "status": normalized_status,
        "document_type": str(item.get("document_type") or "").strip(),
        "rule_family": str(item.get("rule_family") or "").strip(),
        "defect_level": str(item.get("defect_level") or "").strip(),
        "findings": str(item.get("findings") or item.get("finding") or "").strip(),
        "evidence": str(item.get("evidence") or "").strip(),
        "suggestion": str(item.get("suggestion") or "").strip(),
        "confidence": item.get("confidence"),
    }


def _apply_document_payload(target: Dict[str, Any], docs: List[Dict[str, Any]], tree: Optional[List[Dict[str, Any]]] = None) -> None:
    target["raw_documents"] = list(docs or [])
    target["documents_tree"] = list(tree or [])
    target["admissionNote"] = _pick_document_content(docs, ["admission", "入院"])
    target["dischargeNote"] = _pick_document_content(docs, ["discharge", "出院"])
    target["progressNote"] = _pick_document_content(docs, ["progress", "病程", "course", "查房", "会诊"])
    target["surgeryNote"] = _pick_document_content(docs, ["surgery", "operation", "手术", "麻醉", "术前", "术后"])


def _should_prefer_bundle_documents(existing_docs: List[Dict[str, Any]], bundle_docs: List[Dict[str, Any]]) -> bool:
    if not bundle_docs:
        return False
    if not existing_docs:
        return True

    existing_keys = {
        str(item.get("doc_key") or item.get("document_id") or item.get("id") or "").strip()
        for item in existing_docs
        if isinstance(item, dict)
    }
    bundle_keys = {
        str(item.get("doc_key") or item.get("document_id") or item.get("id") or "").strip()
        for item in bundle_docs
        if isinstance(item, dict)
    }
    if bundle_keys and len(bundle_keys) > len(existing_keys):
        return True

    existing_types = {
        str(item.get("doc_type") or item.get("document_type") or item.get("source_table") or "").strip()
        for item in existing_docs
        if isinstance(item, dict)
    }
    bundle_types = {
        str(item.get("doc_type") or item.get("document_type") or item.get("source_table") or "").strip()
        for item in bundle_docs
        if isinstance(item, dict)
    }
    if len(bundle_types) > len(existing_types):
        return True

    return len(bundle_docs) > len(existing_docs)


def _load_review_items_from_latest_batch(record_id: str) -> Dict[str, Any]:
    if engine is None:
        return {"review_items": [], "review_job": None}
    schema = _workspace_schema()
    sql = text(
        f"""
        SELECT id, created_at, items_json
        FROM {schema}.custom_qc_batch_jobs
        WHERE draft_id = 'sichuan-rule-library'
          AND scope = 'final'
          AND status = 'completed'
          AND items_json IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 20
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    for row in rows:
        items = _safe_json_loads(row.get("items_json"), [])
        if not isinstance(items, list):
            continue
        matched: List[Dict[str, Any]] = []
        for idx, raw_item in enumerate(items):
            if not isinstance(raw_item, dict):
                continue
            item_record_id = str(raw_item.get("record_id") or raw_item.get("visit_id") or "").strip()
            if item_record_id != record_id:
                continue
            matched.append(_map_batch_item_to_review_item(raw_item, job_id=str(row.get("id") or ""), created_at=row.get("created_at"), index=idx))
        if matched:
            return {
                "review_items": matched,
                "review_job": {
                    "id": str(row.get("id") or ""),
                    "created_at": str(row.get("created_at") or ""),
                },
            }
    return {"review_items": [], "review_job": None}


def _parse_iso_date_or_422(value: Optional[str], field_name: str) -> Optional[date]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} 格式无效，应为 YYYY-MM-DD",
        ) from exc


def _normalize_final_status(status_value: Optional[str]) -> Optional[str]:
    raw = str(status_value or "").strip().lower()
    if not raw:
        return None
    if raw in {"passed", "completed"}:
        return "passed"
    if raw == "failed":
        return "failed"
    if raw == "pending":
        return "pending"
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="status 仅支持 passed|failed|pending",
    )


@router.get("")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_medical_records(
    request: Request,
    keyword: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    record_type: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_order: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    current_user: dict = Depends(get_current_user),
):
    """获取病案记录列表（支持分页、筛选、排序）"""
    supabase = get_supabase()
    settings = get_settings()
    try:
        if supabase:
            # Use our custom REST client or supabase-py, executed异步以避免阻塞
            # 默认按创建时间倒序排列（最新的在前面）
            # 同时查询关联的文档数据
            response = supabase.table(settings.RECORDS_TABLE).select(
                '*'
            ).order('created_at', {'ascending': False}).execute()  # type: ignore[attr-defined]
            records = list(response.data or [])

            # 优化：一次性查询所有文档，避免 N+1 查询问题
            if records:
                try:
                    # 收集所有记录ID
                    record_ids = [record['id'] for record in records]

                    # 一次性查询所有文档（使用 IN 查询）
                    # 注意：Supabase REST API 使用 .in_() 方法
                    all_docs_response = supabase.table(settings.DOCUMENTS_TABLE).select(
                        '*'  # 选择所有字段，确保包含 content
                    ).in_('record_id', record_ids).order('sort_order').execute()

                    all_documents = all_docs_response.data or []
                    logger.info("Loaded %s documents in one query", len(all_documents))

                    # 按 record_id 分组文档
                    docs_by_record = {}
                    for doc in all_documents:
                        record_id = doc.get('record_id')
                        if record_id not in docs_by_record:
                            docs_by_record[record_id] = []
                        docs_by_record[record_id].append(doc)

                    # 将文档分配给对应的记录
                    for record in records:
                        record['documents'] = docs_by_record.get(record['id'], [])
                        logger.debug(
                            "Record %s loaded with %s documents",
                            record.get('id'),
                            len(record.get('documents', [])),
                        )

                except Exception as doc_error:
                    logger.warning("Batch loading documents failed: %s", doc_error)
                    # 降级：为每条记录设置空文档列表
                    for record in records:
                        record['documents'] = []
        else:
            # Fallback to in-memory records when Supabase is not configured
            records = list(medical_records_db.values())
            # 按创建时间倒序排列（最新的在前面）
            records.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        # basic filtering similar to legacy
        if keyword:
            kw = keyword.lower()
            records = [
                r for r in records
                if kw in (str((r.get('record_name') or r.get('patient_name') or '')).lower())
                or kw in (str((r.get('raw_text') or r.get('content') or '')).lower())
            ]
        if department:
            records = [r for r in records if r.get('department') == department]
        if status:
            records = [r for r in records if r.get('status') == status]
        if record_type:
            # in supabase, we mark LLM parse as a special type via metadata; keep simple
            records = [r for r in records if r.get('record_type') == record_type]

        # sorting - 如果指定了排序字段则使用指定排序，否则保持默认的创建时间倒序
        if sort_field:
            reverse = sort_order == 'desc'
            records.sort(key=lambda x: x.get(sort_field, ''), reverse=reverse)
        elif not supabase:
            # 对于内存数据库，确保在过滤后重新按创建时间排序
            records.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        total = len(records)
        start = (page - 1) * page_size
        end = start + page_size
        page_data = records[start:end]

        return paginated_response(
            items=page_data,
            total=total,
            page=page,
            page_size=page_size,
            message="获取病案列表成功",
            trace_id=get_trace_id(request)
        )
    except Exception as e:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"获取记录列表失败: {e}"
        )


@router.get("/outpatient-emergency")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_outpatient_emergency_records(
    request: Request,
    keyword: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    scoring_standard: Optional[str] = None,
    sort_field: Optional[str] = "visit_date",
    sort_order: Optional[str] = "desc",
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """
    门急诊病历分页查询（最小可落地壳层）。

    返回契约:
    {
      items: [
        {
          id, record_id, patient_name, department, doctor_name,
          visit_type, visit_date, status, score, defect_count, scoring_standard, source
        }
      ],
      total, page, page_size
    }
    """
    supabase = get_supabase()
    settings = get_settings()
    rows: List[Dict[str, Any]] = []

    try:
        if supabase:
            try:
                resp = await async_execute(
                    supabase.table(settings.RECORDS_TABLE).select("*").limit(5000)
                )
                rows = list(getattr(resp, "data", None) or [])
            except Exception as exc:
                logger.warning("读取门急诊病历失败，降级内存数据: %s", exc)
                rows = list(medical_records_db.values())
        else:
            rows = list(medical_records_db.values())

        normalized = [_normalize_outpatient_item(r) for r in rows]
        normalized = [r for r in normalized if r.get("visit_type") in {"outpatient", "emergency"}]

        if keyword:
            kw = keyword.lower()
            normalized = [
                r for r in normalized
                if kw in str(r.get("record_id", "")).lower()
                or kw in str(r.get("patient_name", "")).lower()
                or kw in str(r.get("doctor_name", "")).lower()
            ]
        if department:
            normalized = [r for r in normalized if str(r.get("department") or "") == department]
        if status:
            normalized = [r for r in normalized if str(r.get("status") or "") == status]
        if scoring_standard:
            normalized = [
                r for r in normalized if str(r.get("scoring_standard") or "") == scoring_standard
            ]
        if start_date:
            normalized = [r for r in normalized if str(r.get("visit_date") or "") >= start_date]
        if end_date:
            normalized = [r for r in normalized if str(r.get("visit_date") or "") <= end_date]

        reverse = (sort_order or "desc").lower() == "desc"
        allowed_sort_fields = {"visit_date", "score", "defect_count", "patient_name", "department"}
        final_sort_field = sort_field if sort_field in allowed_sort_fields else "visit_date"
        normalized.sort(key=lambda x: x.get(final_sort_field) or "", reverse=reverse)

        total = len(normalized)
        start = (page - 1) * page_size
        end = start + page_size
        page_data = normalized[start:end]

        return paginated_response(
            items=page_data,
            total=total,
            page=page,
            page_size=page_size,
            message="获取门急诊病历成功",
            trace_id=get_trace_id(request),
        )
    except Exception as e:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"获取门急诊病历失败: {e}",
        )


@router.get("/final")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_final_records(
    request: Request,
    keyword: Optional[str] = Query(None, description="关键字（病历号/住院号/姓名）"),
    department: Optional[str] = Query(None, description="科室"),
    qc_status: Optional[str] = Query(None, alias="status", description="状态 passed|failed|pending"),
    start_date: Optional[str] = Query(None, description="出院日期开始 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="出院日期结束 YYYY-MM-DD"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页数量"),
    current_user: dict = Depends(get_current_user),
):
    """
    终末病历分页列表（已出院病历）。

    返回契约对齐 AdminRecordItem：
    id/task_id/record_id/patient_name/department/discharge_date/status/score/defect_count/created_at
    """
    normalized_status = _normalize_final_status(qc_status)
    start_dt = _parse_iso_date_or_422(start_date, "start_date")
    end_dt = _parse_iso_date_or_422(end_date, "end_date")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date 不能晚于 end_date",
        )

    if SessionLocal is None:
        # 数据库不可用时降级为内存数据（仅用于保证接口可用性）
        rows = [row for row in medical_records_db.values() if str(row.get("discharge_date") or "").strip()]
        if keyword:
            kw = keyword.strip().lower()
            rows = [
                row
                for row in rows
                if kw in str(row.get("record_id") or row.get("mr_no") or "").lower()
                or kw in str(row.get("inpat_no") or "").lower()
                or kw in str(row.get("patient_name") or row.get("name") or "").lower()
            ]
        if department:
            rows = [row for row in rows if str(row.get("department") or "").strip() == department]
        if normalized_status:
            rows = [row for row in rows if normalized_status == "pending"]
        total = len(rows)
        page_data = rows[(page - 1) * page_size : (page - 1) * page_size + page_size]
        items = [
            {
                "id": str(row.get("record_id") or row.get("id") or ""),
                "task_id": "",
                "record_id": str(row.get("record_id") or row.get("mr_no") or row.get("id") or ""),
                "visit_type": str(row.get("visit_type") or ""),
                "patient_name": str(row.get("patient_name") or row.get("name") or ""),
                "department": str(row.get("department") or ""),
                "discharge_date": _normalize_date_only(row.get("discharge_date")),
                "status": "pending",
                "score": None,
                "defect_count": 0,
                "created_at": str(row.get("created_at") or ""),
            }
            for row in page_data
        ]
        return paginated_response(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="获取终末病历成功（降级数据源）",
            trace_id=get_trace_id(request),
        )

    with SessionLocal() as session:
        dept_expr = func.coalesce(
            MedicalRecordFrontpage.discharge_dept_name,
            MedicalRecordFrontpage.admission_dept_name,
            DischargeRecord.dept_name,
            AdmissionRecord.dept_name,
        )
        discharge_dt_expr = func.coalesce(
            MedicalRecordFrontpage.discharge_datetime,
            DischargeRecord.discharge_date,
            DischargeRecord.update_time,
        )
        admission_dt_expr = func.coalesce(
            MedicalRecordFrontpage.admission_datetime,
            AdmissionRecord.admission_datetime,
            AdmissionRecord.update_time,
        )
        created_at_expr = func.coalesce(
            MedicalRecordFrontpage.update_time,
            DischargeRecord.update_time,
            AdmissionRecord.update_time,
        )
        try:
            latest_qc_time_subquery = (
                session.query(
                    QCResultBiz.record_id.label("record_id"),
                    func.max(QCResultBiz.created_at).label("latest_created_at"),
                )
                .group_by(QCResultBiz.record_id)
                .subquery()
            )
            latest_qc_score_subquery = (
                session.query(
                    QCResultBiz.record_id.label("record_id"),
                    QCResultBiz.overall_score.label("overall_score"),
                )
                .join(
                    latest_qc_time_subquery,
                    and_(
                        QCResultBiz.record_id == latest_qc_time_subquery.c.record_id,
                        QCResultBiz.created_at == latest_qc_time_subquery.c.latest_created_at,
                    ),
                )
                .subquery()
            )
            defect_count_subquery = (
                session.query(
                    QCDefect.record_id.label("record_id"),
                    func.count(QCDefect.id).label("defect_count"),
                )
                .group_by(QCDefect.record_id)
                .subquery()
            )

            query = (
                session.query(
                    MedicalRecordFrontpage,
                    discharge_dt_expr.label("effective_discharge_datetime"),
                    admission_dt_expr.label("effective_admission_datetime"),
                    created_at_expr.label("effective_created_at"),
                    latest_qc_score_subquery.c.overall_score.label("overall_score"),
                    func.coalesce(defect_count_subquery.c.defect_count, 0).label("defect_count"),
                )
                .outerjoin(
                    DischargeRecord,
                    and_(
                        DischargeRecord.institute_id == MedicalRecordFrontpage.institute_id,
                        DischargeRecord.patient_id == MedicalRecordFrontpage.patient_id,
                        DischargeRecord.visit_id == MedicalRecordFrontpage.visit_id,
                    ),
                )
                .outerjoin(
                    AdmissionRecord,
                    and_(
                        AdmissionRecord.institute_id == MedicalRecordFrontpage.institute_id,
                        AdmissionRecord.patient_id == MedicalRecordFrontpage.patient_id,
                        AdmissionRecord.visit_id == MedicalRecordFrontpage.visit_id,
                    ),
                )
                .outerjoin(
                    latest_qc_score_subquery,
                    latest_qc_score_subquery.c.record_id == MedicalRecordFrontpage.visit_id,
                )
                .outerjoin(
                    defect_count_subquery,
                    defect_count_subquery.c.record_id == MedicalRecordFrontpage.visit_id,
                )
                .filter(discharge_dt_expr.is_not(None))
            )

            if keyword:
                kw = f"%{keyword.strip()}%"
                query = query.filter(
                    or_(
                        MedicalRecordFrontpage.visit_id.ilike(kw),
                        MedicalRecordFrontpage.mr_no.ilike(kw),
                        MedicalRecordFrontpage.inpat_no.ilike(kw),
                        MedicalRecordFrontpage.name.ilike(kw),
                    )
                )
            if department:
                query = query.filter(dept_expr == department)
            if start_dt:
                query = query.filter(func.date(discharge_dt_expr) >= start_dt)
            if end_dt:
                query = query.filter(func.date(discharge_dt_expr) <= end_dt)
            if normalized_status == "pending":
                query = query.filter(
                    and_(
                        latest_qc_score_subquery.c.overall_score.is_(None),
                        func.coalesce(defect_count_subquery.c.defect_count, 0) == 0,
                    )
                )
            elif normalized_status == "passed":
                query = query.filter(
                    and_(
                        latest_qc_score_subquery.c.overall_score.is_not(None),
                        func.coalesce(defect_count_subquery.c.defect_count, 0) == 0,
                    )
                )
            elif normalized_status == "failed":
                query = query.filter(func.coalesce(defect_count_subquery.c.defect_count, 0) > 0)

            total = int(query.count() or 0)
            rows = (
                query.order_by(
                    desc(discharge_dt_expr),
                    desc(created_at_expr),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            items = []
            for (
                row,
                effective_discharge_datetime,
                _effective_admission_datetime,
                effective_created_at,
                overall_score,
                defect_count,
            ) in rows:
                score = _to_float(overall_score)
                final_defect_count = _to_int(defect_count, 0)
                final_status = "pending"
                if final_defect_count > 0:
                    final_status = "failed"
                elif score is not None:
                    final_status = "passed"
                items.append(
                    {
                        "id": str(row.visit_id or ""),
                        "task_id": "",
                        "record_id": str(row.visit_id or ""),
                        "visit_type": str(row.visit_type or ""),
                        "patient_name": str(row.name or ""),
                        "department": str(
                            row.discharge_dept_name
                            or row.admission_dept_name
                            or ""
                        ),
                        "discharge_date": _normalize_date_only(effective_discharge_datetime),
                        "status": final_status,
                        "score": score,
                        "defect_count": final_defect_count,
                        "created_at": str(
                            effective_created_at
                            or effective_discharge_datetime
                            or row.update_time
                            or ""
                        ),
                    }
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("查询终末病历列表失败，降级无质控聚合: %s", exc)
            session.rollback()
            query = (
                session.query(
                    MedicalRecordFrontpage,
                    discharge_dt_expr.label("effective_discharge_datetime"),
                    created_at_expr.label("effective_created_at"),
                )
                .outerjoin(
                    DischargeRecord,
                    and_(
                        DischargeRecord.institute_id == MedicalRecordFrontpage.institute_id,
                        DischargeRecord.patient_id == MedicalRecordFrontpage.patient_id,
                        DischargeRecord.visit_id == MedicalRecordFrontpage.visit_id,
                    ),
                )
                .outerjoin(
                    AdmissionRecord,
                    and_(
                        AdmissionRecord.institute_id == MedicalRecordFrontpage.institute_id,
                        AdmissionRecord.patient_id == MedicalRecordFrontpage.patient_id,
                        AdmissionRecord.visit_id == MedicalRecordFrontpage.visit_id,
                    ),
                )
                .filter(discharge_dt_expr.is_not(None))
            )
            if keyword:
                kw = f"%{keyword.strip()}%"
                query = query.filter(
                    or_(
                        MedicalRecordFrontpage.visit_id.ilike(kw),
                        MedicalRecordFrontpage.mr_no.ilike(kw),
                        MedicalRecordFrontpage.inpat_no.ilike(kw),
                        MedicalRecordFrontpage.name.ilike(kw),
                    )
                )
            if department:
                query = query.filter(dept_expr == department)
            if start_dt:
                query = query.filter(func.date(discharge_dt_expr) >= start_dt)
            if end_dt:
                query = query.filter(func.date(discharge_dt_expr) <= end_dt)

            if normalized_status in {"passed", "failed"}:
                total = 0
                items = []
            else:
                total = int(query.count() or 0)
                rows = (
                    query.order_by(
                        desc(discharge_dt_expr),
                        desc(created_at_expr),
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                    .all()
                )
                items = [
                    {
                        "id": str(row.visit_id or ""),
                        "task_id": "",
                        "record_id": str(row.visit_id or ""),
                        "visit_type": str(row.visit_type or ""),
                        "patient_name": str(row.name or ""),
                        "department": str(row.discharge_dept_name or row.admission_dept_name or ""),
                        "discharge_date": _normalize_date_only(effective_discharge_datetime),
                        "status": "pending",
                        "score": None,
                        "defect_count": 0,
                        "created_at": str(effective_created_at or effective_discharge_datetime or row.update_time or ""),
                    }
                    for row, effective_discharge_datetime, effective_created_at in rows
                ]

        return paginated_response(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            message="获取终末病历成功",
            trace_id=get_trace_id(request),
        )


@router.get("/{record_id}/qc-detail")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_record_qc_detail(
    request: Request,
    record_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    病历详情聚合接口（最小壳层）。

    返回契约:
    {
      record: {...},
      defects: [],
      remediation: [],
      appeals: [],
      operation_history: [],
      documents: { admissionNote, dischargeNote, progressNote, surgeryNote, raw_documents: [] },
      admissionNote, dischargeNote, progressNote, surgeryNote,
      exists: bool
    }
    """
    supabase = get_supabase()
    settings = get_settings()

    payload: Dict[str, Any] = {
        "record": {"id": record_id, "record_id": record_id},
        "defects": [],
        "review_items": [],
        "review_job": None,
        "remediation": [],
        "appeals": [],
        "operation_history": [],
        "documents": {
            "admissionNote": "",
            "dischargeNote": "",
            "progressNote": "",
            "surgeryNote": "",
            "raw_documents": [],
            "documents_tree": [],
        },
        "admissionNote": "",
        "dischargeNote": "",
        "progressNote": "",
        "surgeryNote": "",
        "documents_tree": [],
        "exists": False,
    }

    try:
        if supabase:
            record_row = None
            try:
                rec_resp = await async_execute(
                    supabase.table(settings.RECORDS_TABLE).select("*").eq("id", record_id).limit(1)
                )
                record_rows = list(getattr(rec_resp, "data", None) or [])
                if record_rows:
                    record_row = record_rows[0]
                else:
                    rec_resp_by_record_id = await async_execute(
                        supabase.table(settings.RECORDS_TABLE).select("*").eq("record_id", record_id).limit(1)
                    )
                    by_record_id_rows = list(getattr(rec_resp_by_record_id, "data", None) or [])
                    if by_record_id_rows:
                        record_row = by_record_id_rows[0]
            except Exception as exc:
                logger.warning("查询病历基础信息失败: %s", exc)

            if record_row:
                normalized = _normalize_outpatient_item(record_row)
                payload["record"] = {**normalized, **record_row}
                payload["exists"] = True

            defect_ids: List[str] = []
            try:
                defects_resp = await async_execute(
                    supabase.table("qc_defects").select("*").eq("record_id", record_id).limit(300)
                )
                defects = list(getattr(defects_resp, "data", None) or [])
                payload["defects"] = defects
                defect_ids = [str(d.get("id")) for d in defects if d.get("id")]
                if defects:
                    payload["exists"] = True
            except Exception as exc:
                logger.warning("查询缺陷列表失败: %s", exc)

            try:
                remediation_resp = await async_execute(
                    supabase.table("qc_remediation_tasks").select("*").eq("record_id", record_id).limit(300)
                )
                remediation = list(getattr(remediation_resp, "data", None) or [])
                payload["remediation"] = remediation
                if remediation:
                    payload["exists"] = True
            except Exception as exc:
                logger.warning("查询整改任务失败: %s", exc)

            try:
                appeals_resp = await async_execute(
                    supabase.table("qc_appeals").select("*").eq("record_id", record_id).limit(300)
                )
                appeals = list(getattr(appeals_resp, "data", None) or [])
                payload["appeals"] = appeals
                if appeals:
                    payload["exists"] = True
            except Exception as exc:
                logger.warning("查询申诉记录失败: %s", exc)

            if defect_ids:
                try:
                    history_resp = await async_execute(
                        supabase.table("qc_defect_history").select("*").in_("defect_id", defect_ids).limit(500)
                    )
                    payload["operation_history"] = list(getattr(history_resp, "data", None) or [])
                except Exception as exc:
                    logger.warning("查询操作历史失败: %s", exc)

            try:
                docs_resp = await async_execute(
                    supabase.table(settings.DOCUMENTS_TABLE)
                    .select("*")
                    .eq("record_id", record_id)
                    .order("sort_order")
                    .limit(200)
                )
                docs = list(getattr(docs_resp, "data", None) or [])
                _apply_document_payload(payload["documents"], docs)
                if docs:
                    payload["exists"] = True
            except Exception as exc:
                logger.warning("查询文书内容失败: %s", exc)
        else:
            record = medical_records_db.get(record_id)
            if record:
                payload["record"] = {**payload["record"], **record}
                payload["admissionNote"] = str(record.get("content") or "")
                payload["documents"]["admissionNote"] = payload["admissionNote"]
                payload["exists"] = True

        bundle_payload = _load_bundle_payload_for_record(record_id)
        bundle_docs = list(bundle_payload.get("documents") or [])
        if _should_prefer_bundle_documents(payload["documents"]["raw_documents"], bundle_docs):
            _apply_document_payload(
                payload["documents"],
                bundle_docs,
                list(bundle_payload.get("documents_tree") or []),
            )
            payload["exists"] = True

        if not payload["defects"]:
            review_payload = _load_review_items_from_latest_batch(record_id)
            payload["review_items"] = list(review_payload.get("review_items") or [])
            payload["review_job"] = review_payload.get("review_job")
            if payload["review_items"]:
                payload["exists"] = True

        payload["admissionNote"] = payload["documents"].get("admissionNote", "")
        payload["dischargeNote"] = payload["documents"].get("dischargeNote", "")
        payload["progressNote"] = payload["documents"].get("progressNote", "")
        payload["surgeryNote"] = payload["documents"].get("surgeryNote", "")
        payload["documents_tree"] = payload["documents"].get("documents_tree", [])
        payload["record"]["defect_count"] = len(payload.get("defects", [])) or len(payload.get("review_items", []))

        return success_response(
            data=payload,
            message="获取病历质控详情成功",
            trace_id=get_trace_id(request),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=StatusCode.INTERNAL_SERVER_ERROR,
            detail=f"获取病历质控详情失败: {exc}",
        )


@router.get("/{record_id}", response_model=MedicalRecordResponse)
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.READ)
async def get_medical_record(record_id: str, current_user: dict = Depends(get_current_user)):
    record = medical_records_db.get(record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医疗记录不存在")
    return MedicalRecordResponse(**record)


@router.post("")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.CREATE)
async def create_medical_record(
    request: Request,
    patient_name: str = Form(...),
    patient_age: int = Form(...),
    patient_gender: str = Form(...),
    department: str = Form(...),
    admission_date: str = Form(...),
    record_type: str = Form(...),
    content: str = Form(...),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    if file is not None:
        upload_bytes = await file.read()
        _validate_record_upload(file, upload_bytes)
    record_id = f"record-{uuid.uuid4().hex[:8]}"
    file_url = f"/uploads/{file.filename}" if file else None
    new_record = {
        "id": record_id,
        "patient_name": patient_name,
        "patient_age": patient_age,
        "patient_gender": patient_gender,
        "department": department,
        "admission_date": admission_date,
        "record_type": record_type,
        "content": content,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "created_by": current_user["id"],
        "file_url": file_url,
    }
    medical_records_db[record_id] = new_record
    return MedicalRecordResponse(**new_record)


@router.put("/{record_id}", response_model=MedicalRecordResponse)
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.UPDATE)
async def update_medical_record(
    request: Request,
    record_id: str,
    patient_name: Optional[str] = Form(None),
    patient_age: Optional[int] = Form(None),
    patient_gender: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    admission_date: Optional[str] = Form(None),
    record_type: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
):
    record = medical_records_db.get(record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医疗记录不存在")

    if patient_name is not None:
        record["patient_name"] = patient_name
    if patient_age is not None:
        record["patient_age"] = patient_age
    if patient_gender is not None:
        record["patient_gender"] = patient_gender
    if department is not None:
        record["department"] = department
    if admission_date is not None:
        record["admission_date"] = admission_date
    if record_type is not None:
        record["record_type"] = record_type
    if content is not None:
        record["content"] = content
    if file:
        upload_bytes = await file.read()
        _validate_record_upload(file, upload_bytes)
        record["file_url"] = f"/uploads/{file.filename}"

    record["updated_at"] = datetime.utcnow().isoformat() + "Z"
    return MedicalRecordResponse(**record)


@router.delete("/{record_id}")
@require_permission(ResourceType.MEDICAL_RECORDS, PermissionAction.DELETE)
async def delete_medical_record(
    request: Request,
    record_id: str,
    current_user: dict = Depends(get_current_user)
):
    """删除病案记录"""
    if record_id not in medical_records_db:
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND,
            detail="医疗记录不存在"
        )
    del medical_records_db[record_id]
    return success_response(
        data={"record_id": record_id},
        message="医疗记录删除成功",
        trace_id=get_trace_id(request)
    )


@router.delete("/batch")
async def batch_delete_records(
    request: Request,
    record_ids: List[str],
    current_user: dict = Depends(get_current_user)
):
    """批量删除病案记录"""
    deleted = 0
    for rid in record_ids:
        if rid in medical_records_db:
            del medical_records_db[rid]
            deleted += 1
    return success_response(
        data={"deleted_count": deleted, "record_ids": record_ids},
        message=f"成功删除 {deleted} 条记录",
        trace_id=get_trace_id(request)
    )


@router.post("/export")
async def export_records(
    request: Request,
    record_ids: List[str],
    current_user: dict = Depends(get_current_user)
):
    """导出病案记录"""
    export_id = f"export-{uuid.uuid4().hex[:8]}"
    download_url = f"/downloads/{export_id}.xlsx"
    return success_response(
        data={"download_url": download_url, "export_id": export_id},
        message="导出任务创建成功",
        trace_id=get_trace_id(request)
    )


@router.get("/statistics")
async def get_medical_records_statistics(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """获取病案统计信息"""
    records = list(medical_records_db.values())
    total_records = len(records)
    pending_records = len([r for r in records if r.get("status") == "pending"])
    completed_records = len([r for r in records if r.get("status") == "completed"])
    analyzing_records = len([r for r in records if r.get("status") == "analyzing"])

    department_stats = {}
    for r in records:
        dept = r.get("department")
        department_stats[dept] = department_stats.get(dept, 0) + 1

    type_stats = {}
    for r in records:
        rt = r.get("record_type")
        type_stats[rt] = type_stats.get(rt, 0) + 1

    from datetime import datetime as dt
    today_prefix = dt.utcnow().strftime("%Y-%m-%d")
    recent = {
        "today": len([r for r in records if str(r.get("created_at", "")).startswith(today_prefix)]),
        "this_week": len(records),
        "this_month": len(records),
    }

    return success_response(
        data={
            "total_records": total_records,
            "pending_records": pending_records,
            "completed_records": completed_records,
            "analyzing_records": analyzing_records,
            "department_statistics": department_stats,
            "type_statistics": type_stats,
            "recent_activity": recent,
        },
        message="获取统计信息成功",
        trace_id=get_trace_id(request)
    )


@router.post("/upload")
async def upload_record_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    enforce_rate_limit(request, bucket="records_upload", max_requests=20, window_seconds=60)
    upload_bytes = await file.read()
    _validate_record_upload(file, upload_bytes)
    file_url = f"/uploads/{file.filename}"
    return {"file_url": file_url, "file_name": file.filename, "size": len(upload_bytes)}


@router.post("/{record_id}/duplicate", response_model=MedicalRecordResponse)
async def duplicate_record(record_id: str, current_user: dict = Depends(get_current_user)):
    original = medical_records_db.get(record_id)
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="医疗记录不存在")
    new_id = f"record-{uuid.uuid4().hex[:8]}"
    new_record = {**original}
    new_record.update({
        "id": new_id,
        "patient_name": f"{original['patient_name']}_副本",
        "status": "pending",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "created_by": current_user["id"],
    })
    medical_records_db[new_id] = new_record
    return MedicalRecordResponse(**new_record)
