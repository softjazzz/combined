import uuid
from datetime import datetime, date
import json
from typing import Any, Dict, Optional, List
import logging

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request, Query
from sqlalchemy import and_, desc, func, or_, text

from ..services.clinical_read import clinical_query, clinical_read_model
from ..core.supabase_client import get_supabase, async_execute
from ..core.security import get_current_user
from ..services.doctor_case_scope import get_doctor_case_scope
from ..core.response import success_response, paginated_response, get_trace_id, StatusCode
from ..schemas.records import MedicalRecordResponse
from ..storage.memory import medical_records_db
from ..core.settings import get_settings
from ..database.connection import DB_SCHEMA_MODE, SessionLocal, engine
from ..database.models.cdm import AdmissionRecord, DischargeRecord, MedicalRecordFrontpage
from ..database.models.qc import QCDefect, QCResultBiz
from ..services.bundles.emr_view import build_documents_tree, load_bundle_documents
from ..services.sample_validation_rule_sets import WORKSPACE_BATCH_DRAFT_IDS
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
                clinical_query(session, model)
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


def _load_bundle_payload_for_record(record_id: str, *, authorized_identity=None) -> Dict[str, Any]:
    identity = authorized_identity or _resolve_visit_identity(record_id)
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
    from ..services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY

    schema = _workspace_schema()
    draft_id_list = ", ".join(f"'{draft_id}'" for draft_id in sorted(WORKSPACE_BATCH_DRAFT_IDS))
    sql = text(
        f"""
        SELECT id, created_at, filters_json, items_json
        FROM {schema}.custom_qc_batch_jobs
        WHERE draft_id IN ({draft_id_list})
          AND status = 'completed'
          AND items_json IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 50
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    for row in rows:
        filters = _safe_json_loads(row.get("filters_json"), {})
        if isinstance(filters, dict) and str(filters.get("rule_set_key") or "").strip() == LUXIAN_0609_RULE_SET_KEY:
            # 以任务冻结的规则集身份阻断整批原始项；单项缺编号时仍不可绕过。
            continue
        items = _safe_json_loads(row.get("items_json"), [])
        if not isinstance(items, list):
            continue
        matched: List[Dict[str, Any]] = []
        for idx, raw_item in enumerate(items):
            if not isinstance(raw_item, dict):
                continue
            if _is_luxian_0609_result_item(raw_item):
                # 正式 0609 结果只能由已发布 Canonical Envelope 交付；
                # items_json 原始项一律不进入客户可见结果，避免绕过发布签章。
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


LUXIAN_0609_RULE_ID_PREFIX = "LX0609-"
# Canonical 未发布或受控失败时的状态；前端据此显示“结果不可用”而非“无问题”。
LUXIAN_0609_NO_RESULT_STATE = "unavailable"


def _is_luxian_0609_result_item(item: Any) -> bool:
    """0609 正式/历史编号的原始项；其他规则集 legacy 项不命中。"""

    if not isinstance(item, dict):
        return False
    return any(
        str(item.get(field) or "").strip().upper().startswith(LUXIAN_0609_RULE_ID_PREFIX)
        for field in ("rule_id", "rule_code")
    )


def _controlled_review_state(value: Any) -> str:
    """只透传已知读取状态，禁止把任意文本带进响应。"""

    state = str(value or "").strip().lower()
    if not state:
        return LUXIAN_0609_NO_RESULT_STATE
    return state if state in {"ready", "incomplete", "not_found", "technical_error", "identity_unresolved", "identity_ambiguous", "identity_conflict"} else "technical_error"


def _luxian_0609_envelope_identities(
    record_id: str, *, rule_set_key: str, rule_set_version: str
) -> set:
    """只按 visit_id 反查当前规则集/版本的 Canonical 三坐标身份，不读取正文。"""

    if engine is None:
        return set()
    schema = _workspace_schema()
    sql = text(
        f"""
        SELECT DISTINCT institute_id, patient_id, visit_id
        FROM {schema}.luxian_0609_record_result_envelopes
        WHERE visit_id = :record_id
          AND rule_set_key = :rule_set_key
          AND rule_set_version = :rule_set_version
        LIMIT 2
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(
            sql,
            {
                "record_id": record_id,
                "rule_set_key": rule_set_key,
                "rule_set_version": rule_set_version,
            },
        ).mappings().all()
    identities = {
        (
            str(row.get("institute_id") or "").strip(),
            str(row.get("patient_id") or "").strip(),
            str(row.get("visit_id") or "").strip(),
        )
        for row in rows
    }
    return {identity for identity in identities if all(identity)}


def _resolve_luxian_0609_identity(
    record_id: str, *, rule_set_key: str, rule_set_version: str
) -> tuple[Optional[tuple], str]:
    """以当前 Envelope 唯一身份为准确定三坐标；CDM 身份只作一致性核对。"""

    envelope_identities = _luxian_0609_envelope_identities(
        record_id, rule_set_key=rule_set_key, rule_set_version=rule_set_version
    )
    if len(envelope_identities) != 1:
        # 没有当前版本 Envelope 时，CDM 身份不能单独证明存在已发布结果。
        return None, "identity_ambiguous" if envelope_identities else "identity_unresolved"
    identity = next(iter(envelope_identities))
    cdm = _resolve_visit_identity(record_id)
    cdm_identity = (
        str(cdm.get("institute_id") or "").strip(),
        str(cdm.get("patient_id") or "").strip(),
        str(cdm.get("visit_id") or "").strip(),
    )
    if all(cdm_identity) and cdm_identity != identity:
        return None, "identity_conflict"
    return identity, "ready"


def _map_canonical_item_to_review_item(
    item: Dict[str, Any], *, job_id: str, record_id: str, index: int
) -> Dict[str, Any]:
    """把已发布 Canonical 项映射为既有 review_items 结构。

    只搬运 Canonical 的 ``conclusion``/``suggestion``/``status``；缺少必需字段
    时抛出 ValueError，由调用方收敛为受控无结果，不用旧内部字段兜底。
    """

    rule_id = str(item.get("rule_id") or item.get("rule_code") or "").strip()
    conclusion = item.get("conclusion")
    status = str(item.get("status") or "").strip().lower()
    if not rule_id or not isinstance(conclusion, str) or not conclusion.strip() or not status:
        raise ValueError("canonical item missing required published fields")
    # 只复用已发布证据的现有客户排版；格式错误时由调用方拒绝整份结果。
    from ..services.luxian_0609_result_export_service import customer_evidence_summary

    evidence = customer_evidence_summary(
        list(item.get("evidence") or []), facts=item.get("customer_display_facts")
    )
    return {
        "id": f"canonical:{job_id}:{rule_id or index}",
        "source": "canonical_result_envelope",
        "job_id": job_id,
        "created_at": "",
        "record_id": record_id,
        "visit_id": record_id,
        "patient_name": "",
        "rule_code": rule_id,
        "rule_name": str(item.get("qc_point") or item.get("rule_name") or "").strip(),
        "status": status,
        "document_type": str(item.get("source_document") or "").strip(),
        "rule_family": "",
        "defect_level": "",
        "findings": conclusion.strip(),
        "evidence": evidence,
        "suggestion": str(item.get("suggestion") or "").strip(),
        "confidence": None,
    }


def _load_luxian_0609_review_items_from_canonical(record_id: str) -> Dict[str, Any]:
    """0609 单病历复核项的唯一正式读取入口：只交付已发布 Canonical 结果。

    身份缺失/歧义或与 CDM 冲突、Envelope 缺失或损坏都收敛为“无 0609 结果”，
    绝不回退到 ``items_json`` 原始项。异常在此吞掉，避免被路由总 catch 变成 500。
    """

    empty = {"review_items": [], "review_job": None, "state": LUXIAN_0609_NO_RESULT_STATE}
    try:
        from ..services.custom_qc_workspace_service import CustomQCWorkspaceService
        from ..services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
        from ..services.luxian_0609_result_schema import RULE_SET_VERSION
    except Exception as exc:  # pragma: no cover - 依赖缺失时保持空结果
        logger.warning("加载 0609 Canonical 读取依赖失败（%s）", type(exc).__name__)
        return dict(empty)

    try:
        identity, state = _resolve_luxian_0609_identity(
            record_id, rule_set_key=LUXIAN_0609_RULE_SET_KEY, rule_set_version=RULE_SET_VERSION
        )
    except Exception as exc:
        # 数据库异常可能包含 SQL 绑定参数，只记录异常类型。
        logger.warning("核对 0609 病历身份失败（%s）", type(exc).__name__)
        return {**empty, "state": "technical_error"}
    if identity is None:
        return {**empty, "state": state}

    institute_id, patient_id, visit_id = identity
    try:
        result = CustomQCWorkspaceService().get_latest_luxian_0609_record_result(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        )
    except Exception as exc:
        logger.warning("读取 0609 Canonical 结果失败（%s）", type(exc).__name__)
        return {**empty, "state": "technical_error"}

    if not isinstance(result, dict):
        logger.warning("0609 Canonical 结果结构无效")
        return {**empty, "state": "technical_error"}
    if str(result.get("state") or "").strip() != "ready":
        # Canonical 缺失或损坏：受控返回无 0609 结果，不读取任何原始结果。
        return {**empty, "state": _controlled_review_state(result.get("state"))}

    items = list(result.get("items") or [])
    if not items:
        return {**empty, "state": LUXIAN_0609_NO_RESULT_STATE}
    job_id = str(result.get("job_id") or "").strip()
    try:
        review_items = [
            _map_canonical_item_to_review_item(
                item, job_id=job_id, record_id=visit_id, index=index
            )
            for index, item in enumerate(items)
        ]
    except Exception as exc:
        logger.warning("0609 Canonical 结果缺少必需字段（%s）", type(exc).__name__)
        return {**empty, "state": "technical_error"}
    return {
        "review_items": review_items,
        "review_job": {"id": job_id, "created_at": "", "source": "canonical_result_envelope"},
        "state": "incomplete" if result.get("is_complete") is False else "ready",
    }


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


def _doctor_record_page(scope, *, department=None, keyword=None, qc_status=None, final=False,
                        start_date=None, end_date=None, page=1, page_size=20):
    from ..services.medical_records.query_service import get_workstation_data

    data = get_workstation_data(
        dept=department, keyword=keyword, hospital_status="discharged" if final else "all",
        date_field="discharge" if final else "visit", start_date=start_date, end_date=end_date,
        page=1, page_size=max(len(scope.case_refs), 1), case_scope=scope,
    )
    items = []
    for row in data["records"]:
        summary = row.get("latest_qc_summary") or {}
        counts = summary.get("status_counts") or {}
        defects = int(counts.get("non_compliant") or 0)
        state = ("failed" if defects else "passed") if summary.get("status") == "ready" else "pending"
        if qc_status and qc_status != state:
            continue
        items.append({
            "id": row["id"], "record_id": row["id"], "task_id": "",
            "institute_id": row["instituteId"], "patient_id": row["patientId"], "visit_id": row["id"],
            "patient_name": row["name"], "department": row["department"], "doctor_name": row["doctor"],
            "admission_date": row["admissionDate"], "discharge_date": row["dischargeDate"],
            "created_at": row["updateTime"], "status": state, "score": None,
            "defect_count": defects, "latest_qc_summary": summary,
        })
    return items[(page - 1) * page_size:page * page_size], len(items)


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
    own_scope = get_doctor_case_scope(request)
    if own_scope is not None:
        items, total = _doctor_record_page(own_scope, department=department, keyword=keyword,
                                          qc_status=_normalize_final_status(status), page=page, page_size=page_size)
        return paginated_response(items=items, total=total, page=page, page_size=page_size,
                                  message="获取本人病历成功", trace_id=get_trace_id(request))
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
    own_scope = get_doctor_case_scope(request)
    start_dt = _parse_iso_date_or_422(start_date, "start_date")
    end_dt = _parse_iso_date_or_422(end_date, "end_date")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date 不能晚于 end_date",
        )

    if own_scope is not None:
        items, total = _doctor_record_page(
            own_scope, department=department, keyword=keyword, qc_status=normalized_status,
            final=True, start_date=start_dt, end_date=end_dt, page=page, page_size=page_size,
        )
        return paginated_response(items=items, total=total, page=page, page_size=page_size,
                                  message="获取本人终末病历成功", trace_id=get_trace_id(request))

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
        # 仅将三个临床来源限定到cdm；同一SQL中的质控结果表保持原owner。
        frontpage_source = clinical_read_model(MedicalRecordFrontpage)
        discharge_source = clinical_read_model(DischargeRecord)
        admission_source = clinical_read_model(AdmissionRecord)
        dept_expr = func.coalesce(
            frontpage_source.discharge_dept_name,
            frontpage_source.admission_dept_name,
            discharge_source.dept_name,
            admission_source.dept_name,
        )
        discharge_dt_expr = func.coalesce(
            frontpage_source.discharge_datetime,
            discharge_source.discharge_date,
            discharge_source.update_time,
        )
        admission_dt_expr = func.coalesce(
            frontpage_source.admission_datetime,
            admission_source.admission_datetime,
            admission_source.update_time,
        )
        created_at_expr = func.coalesce(
            frontpage_source.update_time,
            discharge_source.update_time,
            admission_source.update_time,
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
                    frontpage_source,
                    discharge_dt_expr.label("effective_discharge_datetime"),
                    admission_dt_expr.label("effective_admission_datetime"),
                    created_at_expr.label("effective_created_at"),
                    latest_qc_score_subquery.c.overall_score.label("overall_score"),
                    func.coalesce(defect_count_subquery.c.defect_count, 0).label("defect_count"),
                )
                .outerjoin(
                    discharge_source,
                    and_(
                        discharge_source.institute_id == frontpage_source.institute_id,
                        discharge_source.patient_id == frontpage_source.patient_id,
                        discharge_source.visit_id == frontpage_source.visit_id,
                    ),
                )
                .outerjoin(
                    admission_source,
                    and_(
                        admission_source.institute_id == frontpage_source.institute_id,
                        admission_source.patient_id == frontpage_source.patient_id,
                        admission_source.visit_id == frontpage_source.visit_id,
                    ),
                )
                .outerjoin(
                    latest_qc_score_subquery,
                    latest_qc_score_subquery.c.record_id == frontpage_source.visit_id,
                )
                .outerjoin(
                    defect_count_subquery,
                    defect_count_subquery.c.record_id == frontpage_source.visit_id,
                )
                .filter(discharge_dt_expr.is_not(None))
            )

            if keyword:
                kw = f"%{keyword.strip()}%"
                query = query.filter(
                    or_(
                        frontpage_source.visit_id.ilike(kw),
                        frontpage_source.mr_no.ilike(kw),
                        frontpage_source.inpat_no.ilike(kw),
                        frontpage_source.name.ilike(kw),
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
                    frontpage_source,
                    discharge_dt_expr.label("effective_discharge_datetime"),
                    created_at_expr.label("effective_created_at"),
                )
                .outerjoin(
                    discharge_source,
                    and_(
                        discharge_source.institute_id == frontpage_source.institute_id,
                        discharge_source.patient_id == frontpage_source.patient_id,
                        discharge_source.visit_id == frontpage_source.visit_id,
                    ),
                )
                .outerjoin(
                    admission_source,
                    and_(
                        admission_source.institute_id == frontpage_source.institute_id,
                        admission_source.patient_id == frontpage_source.patient_id,
                        admission_source.visit_id == frontpage_source.visit_id,
                    ),
                )
                .filter(discharge_dt_expr.is_not(None))
            )
            if keyword:
                kw = f"%{keyword.strip()}%"
                query = query.filter(
                    or_(
                        frontpage_source.visit_id.ilike(kw),
                        frontpage_source.mr_no.ilike(kw),
                        frontpage_source.inpat_no.ilike(kw),
                        frontpage_source.name.ilike(kw),
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
    own_identity = getattr(request.state, "doctor_case_identity", None)
    supabase = None if own_identity else get_supabase()
    settings = get_settings()

    payload: Dict[str, Any] = {
        "record": {"id": record_id, "record_id": record_id},
        "defects": [],
        "review_items": [],
        "review_job": None,
        # 受控的 0609 读取状态，供前端区分“无问题”与“结果不可用”。
        "review_result_state": "none",
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
        elif own_identity is None:
            record = medical_records_db.get(record_id)
            if record:
                payload["record"] = {**payload["record"], **record}
                payload["admissionNote"] = str(record.get("content") or "")
                payload["documents"]["admissionNote"] = payload["admissionNote"]
                payload["exists"] = True

        bundle_payload = (
            _load_bundle_payload_for_record(record_id, authorized_identity=own_identity)
            if own_identity else _load_bundle_payload_for_record(record_id)
        )
        bundle_docs = list(bundle_payload.get("documents") or [])
        if _should_prefer_bundle_documents(payload["documents"]["raw_documents"], bundle_docs):
            _apply_document_payload(
                payload["documents"],
                bundle_docs,
                list(bundle_payload.get("documents_tree") or []),
            )
            payload["exists"] = True

        if not payload["defects"]:
            # 正式 0609 结果只从已发布 Canonical Envelope 读取；raw items_json
            # 仅保留给非 0609 legacy 规则集。
            canonical_payload = _load_luxian_0609_review_items_from_canonical(record_id)
            canonical_items = list(canonical_payload.get("review_items") or [])
            canonical_state = _controlled_review_state(canonical_payload.get("state"))
            if canonical_items:
                payload["review_items"] = canonical_items
                payload["review_job"] = canonical_payload.get("review_job")
                payload["review_result_state"] = canonical_state
            elif own_identity is None:
                review_payload = _load_review_items_from_latest_batch(record_id)
                payload["review_items"] = list(review_payload.get("review_items") or [])
                payload["review_job"] = review_payload.get("review_job")
                payload["review_result_state"] = (
                    canonical_state
                    if canonical_state in {"technical_error", "identity_ambiguous", "identity_conflict", "unavailable"}
                    else ("legacy" if payload["review_items"] else canonical_state)
                )
            else:
                payload["review_result_state"] = canonical_state
                payload["review_job"] = canonical_payload.get("review_job")
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
