
from typing import Any, Dict, List, Optional

import asyncio
import contextlib
import inspect
import json
import logging
import re
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from ..services.clinical_read import clinical_query, clinical_table_sql
from ..core.response import success_response, error_response, get_trace_id
from ..core.security import get_current_user
from ..database.connection import engine
from ..database.models.cdm import MedicalRecordFrontpage
from ..schemas.frontpage import FrontPageDraft
from ..services.doctor_case_scope import get_doctor_case_scope
from ..services.frontpage_extraction_service import (
    FrontPageCaseIdentityConflictError,
    FrontPageExtractionService,
    FrontPageExtractionUnavailableError,
    default_frontpage_service,
    redact_frontpage_text_for_llm,
)
from ..services.frontpage_report_generation_service import (
    FrontPageReportGenerationService,
    FrontPageReportInputError,
    default_frontpage_report_generation_service,
)
from ..services.frontpage_export_service import FrontpageExportService, ExportFormat
from ..services.llm_observability import llm_observation_context
from ..services.medical_records.detail_service import (
    _GLOBAL_INSTITUTE_ROLES,
    _normalize_user_roles,
    enforce_institute_access,
    resolve_non_global_institute_scope,
)
from ..services.medical_records.maintenance_service import save_ai_frontpage_draft
from ..services.frontpage_settings import load_frontpage_settings, resolve_force_llm
from ..services.workflow_queue_state_service import default_workflow_queue_state_service

router = APIRouter(prefix="/api/v1/frontpage", tags=["frontpage"])
logger = logging.getLogger(__name__)

_FRONTPAGE_ALLOWED_ROLES = frozenset({
    "admin",
    "super_admin",
    "sync_admin",
    "qc_manager",
    "qc_staff",
    "coder",
    "reviewer",
    "doctor",
})


def _current_user_id(current_user: Optional[Dict[str, Any]]) -> Optional[str]:
    if not current_user:
        return None
    value = current_user.get("id") or current_user.get("user_id")
    return str(value) if value else None


def _require_frontpage_role_and_institute_scope(
    current_user: Optional[Dict[str, Any]],
    *,
    requested_institute_id: Optional[str] = None,
) -> Optional[str]:
    """校验角色权限并解析持久院区范围。全局角色返回 None，非全局角色缺少院区 fail-closed 403。"""
    if not isinstance(current_user, dict):
        raise HTTPException(status_code=401, detail="Authentication required")
    roles = _normalize_user_roles(current_user)
    if not (roles & _FRONTPAGE_ALLOWED_ROLES):
        raise HTTPException(status_code=403, detail="当前角色无权访问病案首页服务")

    if roles & _GLOBAL_INSTITUTE_ROLES:
        return str(requested_institute_id or "").strip() or None

    inst_scope = resolve_non_global_institute_scope(current_user)
    if not inst_scope:
        raise HTTPException(status_code=403, detail="账号缺少可信机构范围")
    if requested_institute_id and str(requested_institute_id).strip():
        enforce_institute_access(inst_scope, str(requested_institute_id).strip())
    return inst_scope


def _resolve_visit_identity(
    visit_id: str,
    *,
    patient_id: Optional[str] = None,
    institute_id: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    normalized_visit_id = str(visit_id or "").strip()
    normalized_patient_id = str(patient_id or "").strip() or None
    normalized_institute_id = str(institute_id or "").strip() or None
    if not normalized_visit_id:
        return {"visit_id": None, "patient_id": None, "institute_id": None}

    with Session(engine) as session:
        q = clinical_query(session, MedicalRecordFrontpage).filter(
            MedicalRecordFrontpage.visit_id == normalized_visit_id
        )
        if normalized_patient_id:
            q = q.filter(MedicalRecordFrontpage.patient_id == normalized_patient_id)
        if normalized_institute_id:
            q = q.filter(MedicalRecordFrontpage.institute_id == normalized_institute_id)
        records = q.limit(2).all()
        if len(records) > 1:
            raise HTTPException(
                status_code=409,
                detail="同一 visit_id 存在多院区或多患者重号，请显式提供 institute_id 和 patient_id",
            )
        if len(records) == 1:
            record = records[0]
            return {
                "visit_id": normalized_visit_id,
                "patient_id": record.patient_id,
                "institute_id": record.institute_id,
            }

        # 回退检查 inpat_registration（尚未生成正式 mr 行的在院/待抽取病例）
        clauses = ["visit_id = :vid"]
        params: Dict[str, Any] = {"vid": normalized_visit_id}
        if normalized_patient_id:
            clauses.append("patient_id = :pid")
            params["pid"] = normalized_patient_id
        if normalized_institute_id:
            clauses.append("institute_id = :iid")
            params["iid"] = normalized_institute_id
        try:
            rows = (
                session.execute(
                    sql_text(
                        f"SELECT DISTINCT institute_id, patient_id, visit_id "
                        f"FROM {clinical_table_sql('inpat_registration')} "
                        f"WHERE {' AND '.join(clauses)} LIMIT 2"
                    ),
                    params,
                )
                .mappings()
                .all()
            )
            if len(rows) > 1:
                raise HTTPException(
                    status_code=409,
                    detail="同一 visit_id 存在多院区或多患者重号，请显式提供 institute_id 和 patient_id",
                )
            if len(rows) == 1:
                row = rows[0]
                return {
                    "visit_id": normalized_visit_id,
                    "patient_id": str(row.get("patient_id") or "").strip() or normalized_patient_id,
                    "institute_id": str(row.get("institute_id") or "").strip() or normalized_institute_id,
                }
        except HTTPException:
            raise
        except Exception:
            pass

        return {
            "visit_id": normalized_visit_id,
            "patient_id": normalized_patient_id,
            "institute_id": normalized_institute_id,
        }


def _resolve_and_authorize_visit_identity(
    request: Request,
    current_user: Optional[Dict[str, Any]],
    *,
    visit_id: Optional[str],
    patient_id: Optional[str] = None,
    institute_id: Optional[str] = None,
    require_found_when_scoped: bool = False,
) -> Dict[str, Optional[str]]:
    """校验角色/院区/医生范围并解析三坐标，发现跨院或重号立即 fail-closed。"""
    effective_scope_inst = _require_frontpage_role_and_institute_scope(
        current_user, requested_institute_id=institute_id
    )
    vid = str(visit_id or "").strip()
    pid = str(patient_id or "").strip() or None
    iid = str(institute_id or "").strip() or effective_scope_inst
    if not vid:
        return {"visit_id": None, "patient_id": pid, "institute_id": iid}

    # 先按未收窄条件检测跨院访问（非全局角色不得探测他院病历）
    resolved = _resolve_visit_identity(
        vid,
        patient_id=pid,
        institute_id=iid,
    )
    roles = _normalize_user_roles(current_user)
    is_global = bool(roles & _GLOBAL_INSTITUTE_ROLES)
    if not is_global:
        if resolved.get("institute_id"):
            enforce_institute_access(effective_scope_inst, resolved.get("institute_id"))
        elif require_found_when_scoped:
            raise HTTPException(status_code=403, detail="未找到当前机构范围内的目标病历")

    doctor_scope = get_doctor_case_scope(request)
    if doctor_scope is not None:
        if not (resolved.get("institute_id") and resolved.get("patient_id") and resolved.get("visit_id")):
            raise HTTPException(status_code=403, detail="医生账号必须提供可验证的完整病例三坐标")
        doctor_scope.require_case(
            resolved["institute_id"],
            resolved["patient_id"],
            resolved["visit_id"],
        )
    return resolved


def _observation_record_identity(
    visit_id: str,
    *,
    patient_id: Optional[str] = None,
    institute_id: Optional[str] = None,
) -> Optional[tuple[str, str, str]]:
    if not str(visit_id or "").strip():
        return None
    if institute_id and patient_id:
        return (str(institute_id).strip(), str(patient_id).strip(), str(visit_id).strip())
    try:
        identity = _resolve_visit_identity(
            visit_id, patient_id=patient_id, institute_id=institute_id
        )
    except Exception as error:
        logger.warning(
            "frontpage_observation_identity_unavailable error_type=%s",
            type(error).__name__,
        )
        return None
    parts = (
        str(identity.get("institute_id") or "").strip(),
        str(identity.get("patient_id") or "").strip(),
        str(identity.get("visit_id") or "").strip(),
    )
    return parts if all(parts) else None



def _extract_discharge_diagnoses_from_text(medical_text: str) -> List[str]:
    if not medical_text or not medical_text.strip():
        return []

    text = medical_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    start_idx = -1
    inline_text = ""
    for idx, raw in enumerate(lines):
        line = raw.strip()
        m = re.match(r"^出院诊断\s*[：:]\s*(.*)$", line)
        if m:
            start_idx = idx
            inline_text = m.group(1).strip()
            break
        if re.match(r"^出院诊断\s*$", line):
            start_idx = idx
            break
    if start_idx < 0:
        return []

    stop_header = re.compile(
        r"^(入院诊断|诊疗经过|出院情况|出院医嘱|医师签名|记录时间|主诉|现病史|既往史|体格检查|辅助检查|手术|手术名称|手术操作|操作名称)\s*[：:]?"
    )
    numbered = re.compile(r"^\s*\d{1,2}[\.、\)]\s*(.+?)\s*$")

    section: List[str] = []
    if inline_text:
        section.append(inline_text)
    for raw in lines[start_idx + 1 :]:
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^={3,}$", line):
            break
        if stop_header.match(line):
            break
        section.append(raw)

    items: List[str] = []
    for raw in section:
        m = numbered.match(raw)
        text_line = (m.group(1) if m else raw).strip()
        if not text_line:
            continue
        split_parts = [p.strip() for p in re.split(r"[、，,；;]+", text_line) if p and p.strip()]
        if len(split_parts) == 1:
            tokens = [t.strip() for t in re.split(r"\s+", text_line) if t and t.strip()]
            if len(tokens) >= 2 and all(len(t) >= 4 for t in tokens):
                split_parts = tokens
        items.extend(split_parts if split_parts else [text_line])

    out: List[str] = []
    seen = set()
    for it in items:
        key = re.sub(r"[\s\-\u2022•·,，;；:：()（）\[\]【】]+", "", it.lower())
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


def _postprocess_frontpage_diagnoses(frontpage: Dict[str, Any], medical_text: str) -> Dict[str, Any]:
    diagnoses = frontpage.get("diagnoses")
    if not isinstance(diagnoses, dict):
        diagnoses = {}
        frontpage["diagnoses"] = diagnoses

    main = diagnoses.get("discharge_main_diagnosis_text")
    others = diagnoses.get("discharge_other_diagnoses_texts")
    has_main = isinstance(main, str) and bool(main.strip())
    has_others = isinstance(others, list) and any(str(x).strip() for x in others)
    if not has_main and not has_others:
        parsed = _extract_discharge_diagnoses_from_text(medical_text)
        if parsed:
            diagnoses["discharge_main_diagnosis_text"] = parsed[0]
            diagnoses["discharge_other_diagnoses_texts"] = parsed[1:]
            logger.info("frontpage auto-generate fallback parse filled diagnoses, count=%d", len(parsed))

    try:
        from ..services.local_icd_service import resolve_diagnosis_codes

        frontpage["diagnoses"] = resolve_diagnosis_codes(diagnoses)
    except Exception:
        logger.exception("frontpage auto-generate diagnosis postprocess failed")
    return frontpage


class FrontPageDocument(BaseModel):
    """用于直接传入文书内容的简单模型"""

    type: str = Field(..., description="文书类型，如 admission_record / discharge_record 等")
    content: str = Field(..., description="文书正文内容")
    meta: Optional[Dict[str, Any]] = Field(
        default=None, description="可选的元数据（时间、作者、科室等）"
    )


class AutoGenerateFrontPageRequest(BaseModel):
    """
    病案首页自动生成请求

    - visit_id、documents、medical_text 至少提供一个
    - 优先级：medical_text > documents > visit_id
    """

    visit_id: Optional[str] = Field(
        default=None, description="住院就诊 ID（后续用于从 EMR 获取全病历）"
    )
    patient_id: Optional[str] = Field(
        default=None, description="患者 ID（三坐标隔离）"
    )
    institute_id: Optional[str] = Field(
        default=None, description="机构 ID（三坐标隔离）"
    )
    documents: Optional[List[FrontPageDocument]] = Field(
        default=None, description="可选：直接传入文书列表，用于调试"
    )
    medical_text: Optional[str] = Field(
        default=None, description="可选：直接传入病历全文进行提取"
    )
    force_llm: bool = Field(
        default=False, description="强制使用 LLM 提取（即使 SQL 层已有数据）"
    )
    scene: Optional[str] = Field(
        default=None, description="兼容字段：统一报告生成场景，旧接口不使用"
    )
    report_scene: Optional[str] = Field(
        default=None, description="兼容字段：统一报告生成场景，旧接口不使用"
    )

    def ensure_valid(self) -> None:
        if not self.visit_id and not self.documents and not self.medical_text:
            raise ValueError("visit_id、documents、medical_text 至少需要提供一个")


def get_frontpage_service() -> FrontPageExtractionService:
    """依赖注入：获取首页抽取服务实例"""
    return default_frontpage_service


def get_frontpage_report_service() -> FrontPageReportGenerationService:
    """依赖注入：获取首页+结算清单统一生成服务实例"""
    return default_frontpage_report_generation_service


class GenerateFrontPageReportRequest(BaseModel):
    """
    病案首页/医保结算清单统一生成请求。

    - scene: nhc_frontpage / insurance_settlement / combined
    - 输入优先级：medical_text > documents > visit_id
    """

    visit_id: Optional[str] = Field(default=None, description="住院就诊 ID")
    patient_id: Optional[str] = Field(default=None, description="患者 ID，用于结算清单 SQL 补充")
    institute_id: Optional[str] = Field(default=None, description="机构 ID（三坐标隔离）")
    documents: Optional[List[FrontPageDocument]] = Field(default=None, description="直接传入文书列表")
    medical_text: Optional[str] = Field(default=None, description="直接传入整份病历文本")
    scene: str = Field(default="combined", description="生成场景")
    report_scene: Optional[str] = Field(default=None, description="scene 的兼容别名")

    def ensure_valid(self) -> None:
        if not self.visit_id and not self.documents and not self.medical_text:
            raise ValueError("visit_id、documents、medical_text 至少需要提供一个")


class FrontPageDemoPreviewRequest(BaseModel):
    """预置示例病历只读预览请求。"""

    visit_id: str = Field(..., description="住院就诊 ID")
    patient_id: Optional[str] = Field(default=None, description="患者 ID，用于定位本机病历")
    institute_id: Optional[str] = Field(default=None, description="机构 ID（三坐标隔离）")

    def ensure_valid(self) -> None:
        if not str(self.visit_id or "").strip():
            raise ValueError("visit_id 不能为空")


@router.post("/demo-visit-preview")
async def preview_frontpage_demo_visit(
    request: Request,
    payload: FrontPageDemoPreviewRequest,
    service: FrontPageReportGenerationService = Depends(get_frontpage_report_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """只读返回预置示例的脱敏病历摘要，不写入业务库。"""
    trace_id = get_trace_id(request)
    try:
        payload.ensure_valid()
    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                error=str(ve), code="BAD_REQUEST", trace_id=trace_id
            )["error"],
        )

    identity = _resolve_and_authorize_visit_identity(
        request,
        current_user,
        visit_id=payload.visit_id,
        patient_id=payload.patient_id,
        institute_id=payload.institute_id,
        require_found_when_scoped=True,
    )

    try:
        preview_params = inspect.signature(service.build_demo_visit_preview).parameters
        preview_kwargs: Dict[str, Any] = {
            "visit_id": identity["visit_id"] or payload.visit_id,
            "patient_id": identity.get("patient_id") or payload.patient_id,
        }
        if "institute_id" in preview_params:
            preview_kwargs["institute_id"] = identity.get("institute_id")
        result = await service.build_demo_visit_preview(**preview_kwargs)
        return success_response(
            data=result,
            message="获取预置病历脱敏预览成功",
            trace_id=trace_id,
        )
    except HTTPException:
        raise
    except FrontPageCaseIdentityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FrontPageReportInputError as exc:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                error=str(exc), code="FRONTPAGE_DEMO_PREVIEW_INPUT_ERROR", trace_id=trace_id
            )["error"],
        )
    except Exception as exc:
        logger.exception(
            "获取预置病历脱敏预览失败 user=%s",
            _current_user_id(current_user),
        )
        return error_response(
            error=f"获取预置病历脱敏预览失败: {exc}",
            code="FRONTPAGE_DEMO_PREVIEW_ERROR",
            trace_id=trace_id,
        )


@router.post("/generate-report-draft")
async def generate_frontpage_report_draft(
    request: Request,
    payload: GenerateFrontPageReportRequest,
    service: FrontPageReportGenerationService = Depends(get_frontpage_report_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """生成病案首页草稿、医保结算清单草稿和字段覆盖报告。"""
    trace_id = get_trace_id(request)
    try:
        payload.ensure_valid()
    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                error=str(ve), code="BAD_REQUEST", trace_id=trace_id
            )["error"],
        )

    identity = _resolve_and_authorize_visit_identity(
        request,
        current_user,
        visit_id=payload.visit_id,
        patient_id=payload.patient_id,
        institute_id=payload.institute_id,
        require_found_when_scoped=bool(payload.visit_id and not payload.medical_text and not payload.documents),
    )
    safe_medical_text = (
        redact_frontpage_text_for_llm(payload.medical_text)
        if payload.medical_text is not None
        else None
    )
    safe_documents = (
        [
            {
                **doc.model_dump(),
                "content": redact_frontpage_text_for_llm(doc.content),
            }
            for doc in payload.documents
        ]
        if payload.documents
        else None
    )

    try:
        with llm_observation_context(
            business_scene="frontpage_report_generation",
            root_job_id=trace_id,
            record_identity=_observation_record_identity(
                identity.get("visit_id") or "",
                patient_id=identity.get("patient_id"),
                institute_id=identity.get("institute_id"),
            ),
            executor_key="frontpage_report_generation",
        ):
            gen_params = inspect.signature(service.generate).parameters
            gen_kwargs: Dict[str, Any] = {
                "scene": payload.report_scene or payload.scene,
                "medical_text": safe_medical_text,
                "documents": safe_documents,
                "visit_id": identity.get("visit_id") or payload.visit_id,
                "patient_id": identity.get("patient_id") or payload.patient_id,
            }
            if "institute_id" in gen_params:
                gen_kwargs["institute_id"] = identity.get("institute_id")
            result = await service.generate(**gen_kwargs)
        return success_response(
            data=result,
            message="生成病案首页和医保结算清单草稿成功",
            trace_id=trace_id,
        )
    except HTTPException:
        raise
    except FrontPageCaseIdentityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FrontPageReportInputError as exc:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                error=str(exc), code="FRONTPAGE_REPORT_INPUT_ERROR", trace_id=trace_id
            )["error"],
        )
    except Exception as exc:
        logger.exception(
            "生成病案首页和医保结算清单草稿失败 user=%s",
            _current_user_id(current_user),
        )
        return error_response(
            error=f"生成病案首页和医保结算清单草稿失败: {exc}",
            code="FRONTPAGE_REPORT_GENERATE_ERROR",
            trace_id=trace_id,
        )


@router.post("/auto-generate-draft")
async def auto_generate_frontpage_draft(
    request: Request,
    payload: AutoGenerateFrontPageRequest,
    service: FrontPageExtractionService = Depends(get_frontpage_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    自动生成病案首页草稿（不含正式写入）。

    输入优先级：medical_text > documents > visit_id。
    当前接口只在获得明确病历正文或文书列表时执行抽取；仅提供 visit_id
    但未能加载到文书时，返回 requires_data 状态，避免用 demo 数据伪装成功。
    """
    trace_id = get_trace_id(request)
    visit_id_for_state = (payload.visit_id or "").strip()
    user_id = _current_user_id(current_user)
    run_id: Optional[str] = None
    try:
        payload.ensure_valid()
    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                error=str(ve), code="BAD_REQUEST", trace_id=trace_id
            )["error"],
        )

    identity = _resolve_and_authorize_visit_identity(
        request,
        current_user,
        visit_id=visit_id_for_state or None,
        patient_id=payload.patient_id,
        institute_id=payload.institute_id,
        require_found_when_scoped=bool(visit_id_for_state),
    )

    try:
        if visit_id_for_state:
            run_id = default_workflow_queue_state_service.start_run(
                workflow_type="frontpage_generate",
                visit_id=visit_id_for_state,
                user_id=user_id,
            )

        observation_root_job_id = run_id or trace_id
        observation_record_identity = _observation_record_identity(
            visit_id_for_state,
            patient_id=identity.get("patient_id"),
            institute_id=identity.get("institute_id"),
        )

        source_medical_text: Optional[str] = None
        source_type = "medical_text" if payload.medical_text else "documents" if payload.documents else "visit_id"

        if payload.medical_text:
            # 直接从传入的病历文本提取（发往模型前脱敏）
            source_medical_text = redact_frontpage_text_for_llm(payload.medical_text)
            with llm_observation_context(
                business_scene="frontpage_extraction",
                root_job_id=observation_root_job_id,
                record_identity=observation_record_identity,
                executor_key="frontpage_extraction",
            ):
                draft: FrontPageDraft = await service.extract_from_text(
                    source_medical_text
                )
        elif payload.documents:
            redacted_docs = [
                {
                    **doc.model_dump(),
                    "content": redact_frontpage_text_for_llm(doc.content),
                }
                for doc in payload.documents
            ]
            source_medical_text = "\n\n".join(
                f"【{doc.get('type') or '未知文书'}】\n{doc.get('content') or ''}"
                for doc in redacted_docs
                if str(doc.get("content") or "").strip()
            )
            with llm_observation_context(
                business_scene="frontpage_extraction",
                root_job_id=observation_root_job_id,
                record_identity=observation_record_identity,
                executor_key="frontpage_extraction",
            ):
                draft = await service.generate_draft_from_documents(
                    redacted_docs
                )
        else:
            get_text_params = inspect.signature(service._get_medical_text).parameters
            get_text_kwargs: Dict[str, Any] = {"allow_demo_fallback": False}
            if "patient_id" in get_text_params and identity.get("patient_id"):
                get_text_kwargs["patient_id"] = identity.get("patient_id")
            if "institute_id" in get_text_params and identity.get("institute_id"):
                get_text_kwargs["institute_id"] = identity.get("institute_id")
            visit_medical_text = await service._get_medical_text(
                visit_id_for_state,
                **get_text_kwargs,
            )
            if visit_medical_text and visit_medical_text.strip():
                source_medical_text = redact_frontpage_text_for_llm(visit_medical_text)
                with llm_observation_context(
                    business_scene="frontpage_extraction",
                    root_job_id=observation_root_job_id,
                    record_identity=observation_record_identity,
                    executor_key="frontpage_extraction",
                ):
                    draft = await service.extract_from_text(source_medical_text)
            else:
                if run_id and visit_id_for_state:
                    default_workflow_queue_state_service.finish_failed(
                        workflow_type="frontpage_generate",
                        visit_id=visit_id_for_state,
                        run_id=run_id,
                        error_message="requires_data",
                        user_id=user_id,
                    )
                return success_response(
                    data={
                        "status": "requires_data",
                        "frontpage": None,
                        "visit_id": payload.visit_id,
                        "reason": "未提供病历正文或文书列表，且 visit_id 未能读取到真实病历文书；当前接口不会用 demo 数据生成首页草稿",
                        "required_inputs": ["medical_text", "documents", "visit_id_with_emr_documents"],
                    },
                    message="需要病历正文或真实文书后才能自动生成病案首页草稿",
                    trace_id=trace_id,
                )

        frontpage = draft.model_dump()
        if source_medical_text:
            frontpage = _postprocess_frontpage_diagnoses(frontpage, source_medical_text)

        if visit_id_for_state:
            patient_id = str(identity.get("patient_id") or "").strip()
            if not patient_id:
                raise RuntimeError(f"未找到 visit_id={visit_id_for_state} 对应的 patient_id，无法保存首页草稿")
            save_ai_frontpage_draft(
                {
                    "institute_id": identity.get("institute_id"),
                    "patient_id": patient_id,
                    "visit_id": visit_id_for_state,
                    "draft_json": frontpage,
                }
            )

        if run_id and visit_id_for_state:
            default_workflow_queue_state_service.finish_success(
                workflow_type="frontpage_generate",
                visit_id=visit_id_for_state,
                run_id=run_id,
                user_id=user_id,
            )

        return success_response(
            data={
                "frontpage": frontpage,
                "source": {
                    "type": source_type,
                    "visit_id": visit_id_for_state or payload.visit_id,
                    "text_length": len(source_medical_text or ""),
                    "demo_fallback_used": False,
                },
            },
            message="自动生成病案首页草稿成功",
            trace_id=trace_id,
        )
    except HTTPException:
        if run_id and visit_id_for_state:
            default_workflow_queue_state_service.finish_failed(
                workflow_type="frontpage_generate",
                visit_id=visit_id_for_state,
                run_id=run_id,
                error_message="HTTPException",
                user_id=user_id,
            )
        raise
    except FrontPageCaseIdentityConflictError as exc:
        if run_id and visit_id_for_state:
            default_workflow_queue_state_service.finish_failed(
                workflow_type="frontpage_generate",
                visit_id=visit_id_for_state,
                run_id=run_id,
                error_message=str(exc),
                user_id=user_id,
            )
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FrontPageExtractionUnavailableError as exc:
        if run_id and visit_id_for_state:
            default_workflow_queue_state_service.finish_failed(
                workflow_type="frontpage_generate",
                visit_id=visit_id_for_state,
                run_id=run_id,
                error_message=str(exc),
                user_id=user_id,
            )
        return JSONResponse(
            status_code=503,
            content=error_response(
                error=str(exc),
                code="FRONTPAGE_EXTRACTION_UNAVAILABLE",
                trace_id=trace_id,
            ),
        )
    except Exception as exc:
        if run_id and visit_id_for_state:
            default_workflow_queue_state_service.finish_failed(
                workflow_type="frontpage_generate",
                visit_id=visit_id_for_state,
                run_id=run_id,
                error_message=str(exc),
                user_id=user_id,
            )
        # 返回统一错误格式，便于前端 debug
        return error_response(
            error=f"自动生成病案首页草稿失败: {exc}",
            code="FRONTPAGE_GENERATE_ERROR",
            trace_id=trace_id,
        )


@router.post("/auto-generate-draft-stream")
async def auto_generate_frontpage_draft_stream(
    request: Request,
    payload: AutoGenerateFrontPageRequest,
    service: FrontPageExtractionService = Depends(get_frontpage_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    自动生成病案首页草稿（流式分批返回）

    返回 `text/event-stream`：
    - event: update, data: {"module": "...", "frontpage": {...}}
    - event: done, data: {"frontpage": {...}}
    """
    trace_id = get_trace_id(request)
    try:
        payload.ensure_valid()
    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail=error_response(
                error=str(ve), code="BAD_REQUEST", trace_id=trace_id
            )["error"],
        )

    identity = _resolve_and_authorize_visit_identity(
        request,
        current_user,
        visit_id=payload.visit_id,
        patient_id=payload.patient_id,
        institute_id=payload.institute_id,
        require_found_when_scoped=bool(payload.visit_id),
    )

    async def event_generator():
        medical_text = redact_frontpage_text_for_llm(payload.medical_text or "")
        visit_id = identity.get("visit_id") or payload.visit_id or ""
        patient_id = identity.get("patient_id")
        institute_id = identity.get("institute_id")
        settings, _ = load_frontpage_settings()
        force_llm = resolve_force_llm(payload.force_llm, settings)
        stream_progress_enabled = settings.stream_progress_enabled

        if payload.force_llm and not force_llm:
            logger.info(
                "frontpage stream force_llm 被配置拒绝: visit_id=%s allow_force=%s llm_backfill=%s",
                visit_id,
                settings.allow_force_llm_regenerate,
                settings.llm_backfill_enabled,
            )

        # 如果没有直接传入文本且有 visit_id，走三层架构（三坐标透传给 stream 方法）
        # 三层架构会内部处理：SQL 直读 → 码表映射 → LLM 补缺
        if not medical_text and visit_id:
            ctx_params = inspect.signature(service._get_llm_context_text).parameters
            ctx_kwargs: Dict[str, Any] = {}
            if "patient_id" in ctx_params and patient_id:
                ctx_kwargs["patient_id"] = patient_id
            if "institute_id" in ctx_params and institute_id:
                ctx_kwargs["institute_id"] = institute_id
            medical_text = redact_frontpage_text_for_llm(
                await service._get_llm_context_text(visit_id, **ctx_kwargs)
            )
        
        queue: asyncio.Queue = asyncio.Queue()
        producer_task: Optional[asyncio.Task] = None

        async def produce():
            with llm_observation_context(
                business_scene="frontpage_extraction",
                root_job_id=trace_id,
                record_identity=_observation_record_identity(
                    visit_id,
                    patient_id=patient_id,
                    institute_id=institute_id,
                ),
                executor_key="frontpage_extraction",
            ):
                try:
                    stream_params = inspect.signature(service.extract_from_text_stream).parameters
                    stream_kwargs: Dict[str, Any] = {
                        "visit_id": visit_id,
                        "force_llm": force_llm,
                    }
                    if "patient_id" in stream_params and patient_id:
                        stream_kwargs["patient_id"] = patient_id
                    if "institute_id" in stream_params and institute_id:
                        stream_kwargs["institute_id"] = institute_id
                    async for event_name, data in service.extract_from_text_stream(
                        medical_text,
                        **stream_kwargs,
                    ):
                        await queue.put((event_name, data))
                except Exception as exc:
                    await queue.put(
                        (
                            "error",
                            {
                                "success": False,
                                "error": str(exc),
                                "trace_id": trace_id,
                            },
                        )
                    )
                finally:
                    await queue.put(("__done__", None))

        try:
            # Flush headers/body immediately to avoid proxy idle timeouts
            yield ": ping\n\n"

            producer_task = asyncio.create_task(produce())

            while True:
                try:
                    event_name, data = await asyncio.wait_for(queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    # Keep the connection alive during long LLM calls
                    yield ": ping\n\n"
                    continue

                if event_name == "__done__":
                    break

                if not stream_progress_enabled and event_name == "update":
                    continue

                if not isinstance(data, dict):
                    data = {}

                # Keep trace_id attached for debugging in devtools
                if "trace_id" not in data:
                    data["trace_id"] = trace_id

                yield f"event: {event_name}\n"
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        finally:
            if producer_task is not None and not producer_task.done():
                producer_task.cancel()
                with contextlib.suppress(Exception):
                    await producer_task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Trace-Id": trace_id,
            "X-Accel-Buffering": "no",
        },
    )


class ProfileAnalyzeRequest(BaseModel):
    """医疗画像分析请求"""
    visit_id: Optional[str] = None
    patient_id: Optional[str] = None
    institute_id: Optional[str] = None
    medical_text: Optional[str] = None
    frontpage_diagnoses: Optional[List[str]] = None
    frontpage_procedures: Optional[List[str]] = None


@router.post("/profile/analyze")
async def analyze_medical_profile(
    request: Request,
    payload: ProfileAnalyzeRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    F13：疾病诊断和手术操作画像分析
    
    功能：
    1. 诊断时间轴提取
    2. 手术闭环验证
    3. 首页差异分析
    
    返回：
    - diagnosis_timeline: 诊断时间轴
    - surgery_verification: 手术验证结果
    - discrepancies: 差异分析
    """
    from ..services.diagnosis_surgery_profiling_service import get_profiling_service
    
    trace_id = get_trace_id(request)
    identity = _resolve_and_authorize_visit_identity(
        request,
        current_user,
        visit_id=payload.visit_id,
        patient_id=payload.patient_id,
        institute_id=payload.institute_id,
        require_found_when_scoped=bool(payload.visit_id and not payload.medical_text),
    )
    
    try:
        service = get_profiling_service()
        
        # 获取病历文本（三坐标隔离 + 发往 LLM 前隐私脱敏）
        medical_text = payload.medical_text
        if not medical_text and identity.get("visit_id"):
            fp_service = get_frontpage_service()
            get_text_params = inspect.signature(fp_service._get_medical_text).parameters
            get_text_kwargs: Dict[str, Any] = {}
            if "allow_demo_fallback" in get_text_params:
                get_text_kwargs["allow_demo_fallback"] = False
            if "patient_id" in get_text_params and identity.get("patient_id"):
                get_text_kwargs["patient_id"] = identity.get("patient_id")
            if "institute_id" in get_text_params and identity.get("institute_id"):
                get_text_kwargs["institute_id"] = identity.get("institute_id")
            medical_text = await fp_service._get_medical_text(
                identity["visit_id"], **get_text_kwargs
            )
        
        if not medical_text or not str(medical_text).strip():
            return error_response(
                error="需要提供 medical_text 或有效的 visit_id",
                code="MISSING_MEDICAL_TEXT",
                trace_id=trace_id,
            )

        safe_medical_text = redact_frontpage_text_for_llm(medical_text)
        
        # 分析画像
        with llm_observation_context(
            business_scene="diagnosis_surgery_profiling",
            root_job_id=trace_id,
            record_identity=_observation_record_identity(
                identity.get("visit_id") or "",
                patient_id=identity.get("patient_id"),
                institute_id=identity.get("institute_id"),
            ),
            executor_key="diagnosis_surgery_profiling",
        ):
            analyze_params = inspect.signature(service.analyze_medical_profile).parameters
            analyze_kwargs: Dict[str, Any] = {
                "medical_text": safe_medical_text,
                "frontpage_diagnoses": payload.frontpage_diagnoses,
                "frontpage_procedures": payload.frontpage_procedures,
            }
            if "institute_id" in analyze_params:
                analyze_kwargs["institute_id"] = identity.get("institute_id")
            if "patient_id" in analyze_params:
                analyze_kwargs["patient_id"] = identity.get("patient_id")
            if "visit_id" in analyze_params:
                analyze_kwargs["visit_id"] = identity.get("visit_id")
            profile = await service.analyze_medical_profile(**analyze_kwargs)
        
        return success_response(
            data=profile.to_dict(),
            message="医疗画像分析完成",
            trace_id=trace_id,
        )
    except HTTPException:
        raise
    except FrontPageCaseIdentityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        return error_response(
            error=f"医疗画像分析失败: {exc}",
            code="PROFILE_ANALYZE_ERROR",
            trace_id=trace_id,
        )


# ==================== 首页导出 API ====================

_export_service = FrontpageExportService()


class ExportFrontpageRequest(BaseModel):
    """首页导出请求"""
    frontpage: Dict[str, Any] = Field(..., description="首页数据")
    format: str = Field("nhc", description="导出格式: nhc/insurance/settlement")


@router.post("/export")
async def export_frontpage(
    request: Request,
    payload: ExportFrontpageRequest,
):
    """
    导出病案首页为 Excel 文件。

    支持 3 种格式:
    - nhc: 卫健委标准住院病案首页
    - insurance: 医保病案首页
    - settlement: 医保结算清单
    """
    try:
        fmt = ExportFormat(payload.format)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的导出格式: {payload.format}。支持: nhc, insurance, settlement"
        )

    excel_bytes = _export_service.export(payload.frontpage, fmt)
    filename = _export_service.get_filename(payload.frontpage, fmt)

    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/export/formats")
async def get_export_formats(request: Request):
    """获取支持的导出格式列表。"""
    formats = [
        {"id": "nhc", "name": "卫健委标准住院病案首页", "description": "符合卫健委规范的标准住院病案首页"},
        {"id": "insurance", "name": "医保病案首页", "description": "医疗保险病案首页格式"},
        {"id": "settlement", "name": "医保结算清单", "description": "医疗保障基金结算清单"},
    ]
    return success_response(
        data=formats,
        message=f"支持 {len(formats)} 种导出格式",
        trace_id=get_trace_id(request),
    )
