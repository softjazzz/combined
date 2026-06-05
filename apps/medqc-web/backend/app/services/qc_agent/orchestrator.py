from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List

from fastapi import HTTPException

from app.services.qc_agent.schemas import QCAgentChatRequest, QCAgentChatResponse
from app.services.qc_agent.tool_registry import AgentToolRegistry
from app.services.qc_agent.tools import assert_no_sensitive_output


_ALLOWED_USER_CONTEXT_KEYS = {"dept", "department", "name", "patient_name", "visit_id", "patient_id", "mr_no"}

_DOCUMENT_PATTERNS = [
    (("查房", "上级医师查房", "主任医师查房", "主治医师查房"), "ward_round", None),
    (("出院记录", "出院小结", "出院"), "discharge", None),
    (("会诊", "MDT", "多学科会诊"), "consultation", None),
    (("首次病程",), "course", "首次病程记录"),
    (("病程记录", "病程"), "course", None),
    (("手术",), None, "手术记录"),
    (("麻醉",), None, "麻醉记录"),
    (("首页", "病案首页"), "frontpage", None),
]

_QC_POINT_PATTERNS = [
    (("完整性", "完整", "缺失"), "completeness"),
    (("时效性", "时效", "及时", "超时"), "timeliness"),
    (("一致性", "一致", "矛盾", "不符"), "consistency"),
    (("诊断依据", "依据"), "diagnosis_evidence"),
    (("病情变化", "临床推理", "推理"), "clinical_reasoning"),
    (("治疗合理性", "治疗", "诊疗计划"), "treatment_rationality"),
    (("医嘱一致性", "医嘱"), "order_consistency"),
    (("编码",), "coding"),
    (("签名", "签字"), "signature"),
    (("危急值",), "critical_value"),
    (("特殊风险", "高风险"), "special_risk"),
]

_UNSUPPORTED_PATTERNS = re.compile(r"删除|写入|保存|提交|入库|正式表|正式结果|持久化|导出", re.IGNORECASE)
_RULE_ID_PATTERN = re.compile(r"\b(?:SC|WR|DG|CL|LX|LXE|FQ)-\d+\b", re.IGNORECASE)
_DIAGNOSIS_CODE_PATTERN = re.compile(r"\b[A-Z]\d{2}(?:\.[A-Z0-9]{1,8})?\b", re.IGNORECASE)
_PROCEDURE_CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9.])\d{2}\.\d{2,6}(?![A-Za-z0-9.])")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_user_context(value: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key: value.get(key) for key in _ALLOWED_USER_CONTEXT_KEYS if value.get(key) not in (None, "")}


def _first_pattern(patterns: List[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _text(match.group(1))
    return ""


def _infer_document(message: str) -> tuple[str | None, str | None]:
    for keywords, document_alias, document_type in _DOCUMENT_PATTERNS:
        if any(keyword in message for keyword in keywords):
            return document_alias, document_type
    return None, None


def _infer_qc_point(message: str) -> str | None:
    for keywords, qc_point_type in _QC_POINT_PATTERNS:
        if any(keyword in message for keyword in keywords):
            return qc_point_type
    return None


def _infer_department(message: str) -> str:
    return _first_pattern([r"([\u4e00-\u9fa5A-Za-z0-9]{2,12}科)"], message)


def _infer_patient_name(message: str) -> str:
    patterns = [
        r"患者\s*([\u4e00-\u9fa5]{2,4})",
        r"病人\s*([\u4e00-\u9fa5]{2,4})",
        r"(?:^|[，,。；;\s])[\u4e00-\u9fa5]{2,12}科\s*([\u4e00-\u9fa5]{2,4})的",
        r"(?:^|[，,。；;\s])([\u4e00-\u9fa5]{2,4})的(?:查房|病程|出院|会诊)",
    ]
    name = _first_pattern(patterns, message)
    blocked = {"查房", "病程", "出院", "会诊", "质控", "记录", "首页", "完整", "时效", "一致"}
    return "" if name in blocked else name


def _infer_visit_id(message: str, context: Dict[str, Any]) -> str:
    explicit = _first_pattern([r"visit_id\s*[=:：]?\s*([A-Za-z0-9_-]+)"], message)
    if explicit:
        return explicit
    bare_record = _first_pattern(
        [
            r"(?:给|对)\s*([0-9]{4,})\s*(?:推荐|做|进行).*编码",
            r"(?:visit|病历|住院)\s*([0-9]{4,})\s*(?:推荐|做|进行).*编码",
        ],
        message,
    )
    return bare_record or _text(context.get("visit_id"))


def _extract_patient_age(message: str) -> int | None:
    value = _first_pattern([r"年龄\s*[=:：]?\s*(\d{1,3})", r"(\d{1,3})\s*岁"], message)
    return int(value) if value else None


def _extract_los(message: str) -> int | None:
    value = _first_pattern([r"住院\s*[=:：]?\s*(\d{1,3})\s*天", r"LOS\s*[=:：]?\s*(\d{1,3})"], message)
    return int(value) if value else None


def _extract_fee(message: str) -> float | None:
    value = _first_pattern([r"(?:费用|总费用|total_fee|total_cost)\s*[=:：]?\s*(\d+(?:\.\d+)?)"], message)
    return float(value) if value else None


def _extract_gender(message: str) -> str:
    if "女" in message:
        return "F"
    if "男" in message:
        return "M"
    return ""


def _extract_icd_search_query(message: str) -> str:
    diagnosis_codes = _DIAGNOSIS_CODE_PATTERN.findall(message)
    procedure_codes = _PROCEDURE_CODE_PATTERN.findall(message)
    if diagnosis_codes:
        return diagnosis_codes[0].upper()
    if procedure_codes:
        return procedure_codes[0]

    cleaned = message
    cleaned = re.sub(r"(?i)\bICD\b", " ", cleaned)
    cleaned = re.sub(r"(?:查询|查一下|查|编码|代码|的|医保版|国临版|临床版|诊断|疾病|手术|操作|ICD-10|ICD-9|CM-3)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ：:，,。；;")
    return cleaned


def _infer_code_type(message: str) -> str:
    if any(keyword in message for keyword in ("手术", "操作", "术式", "ICD-9", "CM-3")):
        return "procedure"
    if any(keyword in message for keyword in ("诊断", "疾病", "ICD-10")):
        return "diagnosis"
    return "all"


def _infer_version(message: str) -> str:
    if any(keyword in message for keyword in ("国临", "临床版", "临床")):
        return "clinical"
    return "insurance"


def _is_grouping_request(message: str) -> bool:
    return bool(re.search(r"\b(?:DRG|DIP)\b", message, flags=re.IGNORECASE) or "入组" in message)


def _is_coding_suggestion_request(message: str, visit_id: str) -> bool:
    if "入组" in message or re.search(r"\b(?:DRG|DIP)\b", message, flags=re.IGNORECASE):
        return False
    if "编码建议" in message:
        return True
    if re.search(r"推荐.*(?:诊断|手术|操作)?.*编码", message):
        return True
    return bool(visit_id and "编码" in message and not any(keyword in message for keyword in ("查询", "查 ")))


def _is_icd_search_request(message: str, visit_id: str) -> bool:
    if _is_grouping_request(message) or _is_coding_suggestion_request(message, visit_id):
        return False
    if re.search(r"\bICD\b", message, flags=re.IGNORECASE):
        return True
    if "编码" in message and any(keyword in message for keyword in ("查询", "查", "医保版", "国临版", "临床版")):
        return True
    return False


def _enrich_capability_intent(intent: Dict[str, Any], message: str, warnings: List[str]) -> None:
    visit_id = _text(intent.get("visit_id"))
    diagnosis_codes = [item.upper() for item in _DIAGNOSIS_CODE_PATTERN.findall(message)]
    procedure_codes = _PROCEDURE_CODE_PATTERN.findall(message)
    if re.search(r"\bDIP\b", message, flags=re.IGNORECASE) or ("DIP" in message.upper() and "入组" in message):
        intent.update(
            {
                "task_type": "grouping",
                "capability": "predict_dip_group",
                "result_type": "dip_group",
                "pdx_code": diagnosis_codes[0] if diagnosis_codes else "",
                "adx_codes": diagnosis_codes[1:],
                "proc_codes": procedure_codes,
                "patient_age": _extract_patient_age(message),
                "patient_gender": _extract_gender(message),
                "los": _extract_los(message),
                "total_fee": _extract_fee(message),
            }
        )
        return
    if re.search(r"\bDRG\b", message, flags=re.IGNORECASE):
        intent.update(
            {
                "task_type": "grouping",
                "capability": "predict_drg_group",
                "result_type": "drg_group",
                "primary_diagnosis_code": diagnosis_codes[0] if diagnosis_codes else "",
                "secondary_diagnosis_codes": diagnosis_codes[1:],
                "procedure_codes": procedure_codes,
                "patient_age": _extract_patient_age(message),
                "patient_gender": _extract_gender(message),
                "los": _extract_los(message),
                "total_cost": _extract_fee(message),
            }
        )
        return
    if _is_coding_suggestion_request(message, visit_id):
        include_procedures = any(keyword in message for keyword in ("手术", "操作", "诊断和手术", "诊断及手术"))
        intent.update(
            {
                "task_type": "coding",
                "capability": "suggest_record_icd_codes",
                "result_type": "record_icd_suggestions",
                "include_procedures": include_procedures,
            }
        )
        return
    if _is_icd_search_request(message, visit_id):
        query = _extract_icd_search_query(message)
        intent.update(
            {
                "task_type": "coding",
                "capability": "search_icd_codes",
                "result_type": "icd_candidates",
                "icd_query": query,
                "code_type": _infer_code_type(message),
                "version": _infer_version(message),
            }
        )
        if not query:
            warnings.append("未识别到 ICD 查询关键词或编码")
        return
    intent.update({"task_type": "qc", "capability": "run_document_qc", "result_type": "document_qc"})


def parse_intent(request: QCAgentChatRequest) -> tuple[Dict[str, Any], List[str]]:
    message = request.message.strip()
    context = _safe_user_context(request.user_context)
    warnings: List[str] = []
    document_alias, document_type = _infer_document(message)
    qc_point_type = _infer_qc_point(message)
    rule_ids = [item.upper() for item in _RULE_ID_PATTERN.findall(message)]
    intent = {
        "message": message,
        "unsupported": bool(_UNSUPPORTED_PATTERNS.search(message)),
        "visit_id": _infer_visit_id(message, context),
        "patient_id": _first_pattern([r"patient_id\s*[=:：]?\s*([A-Za-z0-9_-]+)"], message)
        or _text(context.get("patient_id")),
        "mr_no": _first_pattern([r"(?:住院号|病案号|mr_no)\s*[=:：]?\s*([A-Za-z0-9_-]+)"], message)
        or _text(context.get("mr_no")),
        "patient_name": _infer_patient_name(message)
        or _text(context.get("name"))
        or _text(context.get("patient_name")),
        "department": _infer_department(message)
        or _text(context.get("dept"))
        or _text(context.get("department")),
        "document_alias": document_alias,
        "document_type": document_type,
        "qc_point_type": qc_point_type,
        "rule_ids": rule_ids,
    }
    _enrich_capability_intent(intent, message, warnings)
    if intent["document_alias"] == "frontpage":
        warnings.append("当前自然语言编排仅支持单病历文书质控，病案首页请使用 run_frontpage_qc 工具")
    if rule_ids and not qc_point_type:
        warnings.append("已识别显式 rule_ids，将优先按 rule_ids 执行或跳过")
    return intent, warnings


def _plan_item(tool_name: str, status: str, arguments: Dict[str, Any], public_data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "tool_name": tool_name,
        "status": status,
        "arguments": arguments,
    }
    if public_data:
        item["summary"] = {
            key: public_data.get(key)
            for key in ("total", "returned", "rule_count")
            if key in public_data
        }
    return item


def _needs_clarification_response(
    *,
    request: QCAgentChatRequest,
    run_id: str,
    intent: Dict[str, Any],
    plan: List[Dict[str, Any]],
    warnings: List[str],
) -> QCAgentChatResponse:
    response = QCAgentChatResponse(
        status="needs_clarification",
        parsed_intent=intent,
        plan=plan,
        warnings=warnings,
        run_id=run_id,
        session_id=request.session_id,
    )
    assert_no_sensitive_output(response.model_dump())
    return response


def _completed_response(
    *,
    request: QCAgentChatRequest,
    run_id: str,
    intent: Dict[str, Any],
    plan: List[Dict[str, Any]],
    result: Dict[str, Any],
    warnings: List[str],
) -> QCAgentChatResponse:
    response = QCAgentChatResponse(
        status="completed",
        parsed_intent=intent,
        plan=plan,
        result=result,
        warnings=warnings + list(result.get("warnings") or []),
        run_id=run_id,
        session_id=request.session_id,
    )
    assert_no_sensitive_output(response.model_dump())
    return response


def _http_detail_text(exc: HTTPException) -> str:
    detail = getattr(exc, "detail", "")
    if isinstance(detail, str):
        return detail
    return str(detail)


def _is_missing_document_context_error(exc: HTTPException) -> bool:
    detail = _http_detail_text(exc)
    if getattr(exc, "status_code", None) not in {404, 422}:
        return False
    patterns = (
        "缺少可用文书文本",
        "缺少 medical_text",
        "未命中文书",
        "未找到目标文书",
        "文书为空",
        "无可用文书",
    )
    return any(pattern in detail for pattern in patterns)


def _execute_tool(
    registry: AgentToolRegistry,
    tool_name: str,
    arguments: Dict[str, Any],
    plan: List[Dict[str, Any]],
) -> Dict[str, Any]:
    response = registry.execute(tool_name, arguments)
    public_data = response.observation.public_data
    assert_no_sensitive_output(public_data)
    plan.append(_plan_item(tool_name, response.observation.status, arguments, public_data))
    return public_data


def _record_ref_from_confirmation(confirm_selection: Dict[str, Any] | None) -> Dict[str, str]:
    if not isinstance(confirm_selection, dict):
        return {}
    return {
        "visit_id": _text(confirm_selection.get("visit_id")),
        "patient_id": _text(confirm_selection.get("patient_id")),
    }


def _search_candidates(
    registry: AgentToolRegistry,
    intent: Dict[str, Any],
    plan: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    keyword = intent.get("mr_no") or intent.get("patient_name") or intent.get("patient_id") or ""
    arguments = {
        "scope": "final",
        "department": intent.get("department") or None,
        "doctor": None,
        "date_field": "discharge",
        "start_date": None,
        "end_date": None,
        "keyword": keyword or None,
        "page": 1,
        "page_size": 20,
    }
    public_data = _execute_tool(registry, "search_records", arguments, plan)
    return list(public_data.get("records") or [])


def _resolve_single_record_for_coding(
    *,
    request: QCAgentChatRequest,
    registry: AgentToolRegistry,
    run_id: str,
    intent: Dict[str, Any],
    plan: List[Dict[str, Any]],
    warnings: List[str],
) -> tuple[str, str, QCAgentChatResponse | None]:
    confirmed_ref = _record_ref_from_confirmation(request.confirm_selection)
    visit_id = confirmed_ref.get("visit_id") or intent.get("visit_id")
    patient_id = confirmed_ref.get("patient_id") or intent.get("patient_id")
    if visit_id:
        return _text(visit_id), _text(patient_id), None
    candidates = _search_candidates(registry, intent, plan)
    if not candidates:
        return "", "", QCAgentChatResponse(
            status="needs_clarification",
            parsed_intent=intent,
            plan=plan,
            candidates=[],
            warnings=warnings + ["未找到匹配病历，请补充 visit_id、住院号、患者姓名或科室"],
            run_id=run_id,
            session_id=request.session_id,
        )
    if len(candidates) > 1:
        return "", "", QCAgentChatResponse(
            status="needs_confirmation",
            parsed_intent=intent,
            plan=plan,
            candidates=candidates,
            warnings=warnings + ["命中多份病历，请确认单个 visit_id 后再执行编码建议"],
            run_id=run_id,
            session_id=request.session_id,
        )
    return _text(candidates[0].get("visit_id")), _text(patient_id or candidates[0].get("patient_id")), None


def _run_coding_or_grouping_intent(
    *,
    request: QCAgentChatRequest,
    registry: AgentToolRegistry,
    run_id: str,
    intent: Dict[str, Any],
    plan: List[Dict[str, Any]],
    warnings: List[str],
) -> QCAgentChatResponse | None:
    capability = _text(intent.get("capability"))
    if capability == "search_icd_codes":
        query = _text(intent.get("icd_query"))
        if not query:
            return _needs_clarification_response(
                request=request,
                run_id=run_id,
                intent=intent,
                plan=plan,
                warnings=warnings + ["请补充要查询的诊断/手术名称或 ICD 编码"],
            )
        result = _execute_tool(
            registry,
            "search_icd_codes",
            {
                "query": query,
                "code_type": intent.get("code_type") or "all",
                "version": intent.get("version") or "insurance",
                "limit": 20,
            },
            plan,
        )
        return _completed_response(
            request=request,
            run_id=run_id,
            intent=intent,
            plan=plan,
            result=result,
            warnings=warnings,
        )
    if capability == "suggest_record_icd_codes":
        visit_id, patient_id, response = _resolve_single_record_for_coding(
            request=request,
            registry=registry,
            run_id=run_id,
            intent=intent,
            plan=plan,
            warnings=warnings,
        )
        if response is not None:
            assert_no_sensitive_output(response.model_dump())
            return response
        result = _execute_tool(
            registry,
            "suggest_record_icd_codes",
            {
                "visit_id": visit_id,
                "patient_id": patient_id or None,
                "include_procedures": bool(intent.get("include_procedures")),
                "limit_per_item": 5,
            },
            plan,
        )
        return _completed_response(
            request=request,
            run_id=run_id,
            intent={**intent, "visit_id": visit_id, "patient_id": patient_id or ""},
            plan=plan,
            result=result,
            warnings=warnings,
        )
    if capability == "predict_dip_group":
        pdx_code = _text(intent.get("pdx_code"))
        if not pdx_code:
            return _needs_clarification_response(
                request=request,
                run_id=run_id,
                intent=intent,
                plan=plan,
                warnings=warnings + ["DIP 入组需要主诊断 ICD 编码"],
            )
        result = _execute_tool(
            registry,
            "predict_dip_group",
            {
                "city_name": "泸州市",
                "pdx_code": pdx_code,
                "adx_codes": intent.get("adx_codes") or [],
                "proc_codes": intent.get("proc_codes") or [],
                "patient_gender": intent.get("patient_gender") or None,
                "patient_age": intent.get("patient_age"),
                "los": intent.get("los"),
                "total_fee": intent.get("total_fee"),
            },
            plan,
        )
        return _completed_response(
            request=request,
            run_id=run_id,
            intent=intent,
            plan=plan,
            result=result,
            warnings=warnings,
        )
    if capability == "predict_drg_group":
        primary_code = _text(intent.get("primary_diagnosis_code"))
        if not primary_code:
            return _needs_clarification_response(
                request=request,
                run_id=run_id,
                intent=intent,
                plan=plan,
                warnings=warnings + ["DRG 入组需要主诊断 ICD 编码"],
            )
        result = _execute_tool(
            registry,
            "predict_drg_group",
            {
                "primary_diagnosis_code": primary_code,
                "secondary_diagnosis_codes": intent.get("secondary_diagnosis_codes") or [],
                "procedure_codes": intent.get("procedure_codes") or [],
                "patient_age": intent.get("patient_age"),
                "patient_gender": intent.get("patient_gender") or None,
                "los": intent.get("los"),
                "total_cost": intent.get("total_cost"),
                "region": "四川省",
            },
            plan,
        )
        return _completed_response(
            request=request,
            run_id=run_id,
            intent=intent,
            plan=plan,
            result=result,
            warnings=warnings,
        )
    return None


def run_intent(request: QCAgentChatRequest, registry: AgentToolRegistry) -> QCAgentChatResponse:
    run_id = str(uuid.uuid4())
    plan: List[Dict[str, Any]] = []
    intent, warnings = parse_intent(request)
    if intent.get("unsupported"):
        response = QCAgentChatResponse(
            status="unsupported",
            parsed_intent=intent,
            plan=plan,
            warnings=warnings + ["当前受控 Agent 不支持写入、删除、导出或持久化类操作"],
            run_id=run_id,
            session_id=request.session_id,
        )
        assert_no_sensitive_output(response.model_dump())
        return response

    capability_response = _run_coding_or_grouping_intent(
        request=request,
        registry=registry,
        run_id=run_id,
        intent=intent,
        plan=plan,
        warnings=warnings,
    )
    if capability_response is not None:
        return capability_response

    if intent.get("document_alias") == "frontpage":
        response = QCAgentChatResponse(
            status="unsupported",
            parsed_intent=intent,
            plan=plan,
            warnings=warnings,
            run_id=run_id,
            session_id=request.session_id,
        )
        assert_no_sensitive_output(response.model_dump())
        return response

    if not intent.get("document_alias") and not intent.get("document_type"):
        response = QCAgentChatResponse(
            status="needs_clarification",
            parsed_intent=intent,
            plan=plan,
            warnings=warnings + ["未识别到明确文书类型，请说明查房记录、病程记录、出院记录或会诊记录"],
            run_id=run_id,
            session_id=request.session_id,
        )
        assert_no_sensitive_output(response.model_dump())
        return response

    confirmed_ref = _record_ref_from_confirmation(request.confirm_selection)
    visit_id = confirmed_ref.get("visit_id") or intent.get("visit_id")
    patient_id = confirmed_ref.get("patient_id") or intent.get("patient_id")
    candidates: List[Dict[str, Any]] = []
    if not visit_id:
        candidates = _search_candidates(registry, intent, plan)
        if not candidates:
            response = QCAgentChatResponse(
                status="needs_clarification",
                parsed_intent=intent,
                plan=plan,
                candidates=[],
                warnings=warnings + ["未找到匹配病历，请补充 visit_id、住院号、患者姓名或科室"],
                run_id=run_id,
                session_id=request.session_id,
            )
            assert_no_sensitive_output(response.model_dump())
            return response
        if len(candidates) > 1:
            response = QCAgentChatResponse(
                status="needs_confirmation",
                parsed_intent=intent,
                plan=plan,
                candidates=candidates,
                warnings=warnings + ["命中多份病历，请确认单个 visit_id 后再执行质控"],
                run_id=run_id,
                session_id=request.session_id,
            )
            assert_no_sensitive_output(response.model_dump())
            return response
        visit_id = candidates[0].get("visit_id", "")
        patient_id = patient_id or candidates[0].get("patient_id", "")

    context_args = {
        "visit_id": visit_id,
        "patient_id": patient_id or None,
        "scene": "final",
        "include_preview": False,
    }
    context_public = _execute_tool(registry, "get_record_context", context_args, plan)
    context_status = context_public.get("context_status") if isinstance(context_public, dict) else {}
    if isinstance(context_status, dict) and not context_status.get("text_available"):
        context_warnings = list(context_public.get("warnings") or [])
        return _needs_clarification_response(
            request=request,
            run_id=run_id,
            intent={**intent, "visit_id": visit_id, "patient_id": patient_id or ""},
            plan=plan,
            warnings=warnings + context_warnings + ["病历上下文缺少可用文书文本，无法执行文书质控"],
        )

    document_scope: Dict[str, Any] = {"max_documents": 10}
    if intent.get("document_alias") in {"ward_round", "discharge", "course", "consultation"}:
        document_scope["alias"] = intent["document_alias"]
    if intent.get("document_type"):
        document_scope["document_types"] = [intent["document_type"]]
    select_args = {
        "visit_id": visit_id,
        "patient_id": patient_id or None,
        "document_scope": document_scope,
    }
    try:
        selection_public = _execute_tool(registry, "select_record_documents", select_args, plan)
    except HTTPException as exc:
        if _is_missing_document_context_error(exc):
            return _needs_clarification_response(
                request=request,
                run_id=run_id,
                intent={**intent, "visit_id": visit_id, "patient_id": patient_id or ""},
                plan=plan,
                warnings=warnings + [_http_detail_text(exc)],
            )
        raise
    selection_summary = selection_public.get("selection_summary") if isinstance(selection_public, dict) else {}
    matched_count = selection_summary.get("matched_document_count") if isinstance(selection_summary, dict) else None
    if matched_count == 0:
        selection_warnings = list(selection_public.get("warnings") or [])
        return _needs_clarification_response(
            request=request,
            run_id=run_id,
            intent={**intent, "visit_id": visit_id, "patient_id": patient_id or ""},
            plan=plan,
            warnings=warnings + selection_warnings + ["未找到目标文书，无法执行文书质控"],
        )

    if intent.get("rule_ids"):
        plan.append(
            _plan_item(
                "resolve_rule_scope",
                "skipped",
                {"rule_ids": intent["rule_ids"]},
                {"rule_count": len(intent["rule_ids"])},
            )
        )
    else:
        resolve_args = {
            "document_alias": intent.get("document_alias"),
            "document_type": intent.get("document_type"),
            "qc_point_type": intent.get("qc_point_type"),
            "limit": 20,
        }
        _execute_tool(registry, "resolve_rule_scope", resolve_args, plan)

    run_args = {
        "visit_id": visit_id,
        "patient_id": patient_id or None,
        "document_alias": intent.get("document_alias"),
        "document_type": intent.get("document_type"),
        "qc_point_type": intent.get("qc_point_type"),
        "rule_ids": intent.get("rule_ids") or None,
        "include_passed": False,
        "max_rules": 20,
    }
    try:
        result = _execute_tool(registry, "run_document_qc", run_args, plan)
    except HTTPException as exc:
        if _is_missing_document_context_error(exc):
            return _needs_clarification_response(
                request=request,
                run_id=run_id,
                intent={**intent, "visit_id": visit_id, "patient_id": patient_id or ""},
                plan=plan,
                warnings=warnings + [_http_detail_text(exc)],
            )
        raise
    response_warnings = warnings + list(result.get("warnings") or [])
    response = QCAgentChatResponse(
        status="completed",
        parsed_intent={**intent, "visit_id": visit_id, "patient_id": patient_id or ""},
        plan=plan,
        result=result,
        warnings=response_warnings,
        run_id=run_id,
        session_id=request.session_id,
    )
    assert_no_sensitive_output(response.model_dump())
    return response
