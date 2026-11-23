from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List

from fastapi import HTTPException, status

from app.core.roles import effective_roles
from app.services.qc_agent.intent_router import (
    merge_llm_intent,
    normalize_intent_message,
    resolve_intent_with_llm,
)
from app.services.qc_agent.schemas import QCAgentChatRequest, QCAgentChatResponse
from app.services.qc_agent.tool_registry import AgentToolRegistry
from app.services.qc_agent.tools import assert_no_sensitive_output


_ALLOWED_USER_CONTEXT_KEYS = {
    "dept",
    "department",
    "name",
    "patient_name",
    "visit_id",
    "patient_id",
    "mr_no",
    "institute_id",
}
_GLOBAL_SCOPE_ROLES = frozenset({"admin", "super_admin", "sync_admin"})

_DOCUMENT_PATTERNS = [
    (("入院记录", "再次入院记录", "多次入院记录"), "admission", None),
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


def parse_intent(request: QCAgentChatRequest) -> tuple[Dict[str, Any], List[str]]:
    raw_message = request.message.strip()
    message = normalize_intent_message(raw_message)
    context = _safe_user_context(request.user_context)
    warnings: List[str] = []
    rule_ids = [item.upper() for item in _RULE_ID_PATTERN.findall(message)]
    safety_unsupported = bool(_UNSUPPORTED_PATTERNS.search(message))
    intent = {
        "message": raw_message,
        "normalized_message": message,
        "unsupported": False,
        "visit_id": _text(context.get("visit_id")),
        "patient_id": _first_pattern([r"patient_id\s*[=:：]?\s*([A-Za-z0-9_-]+)"], message)
        or _text(context.get("patient_id")),
        "mr_no": _first_pattern([r"(?:住院号|病案号|mr_no)\s*[=:：]?\s*([A-Za-z0-9_-]+)"], message)
        or _text(context.get("mr_no")),
        "patient_name": _text(context.get("name")) or _text(context.get("patient_name")),
        "department": _text(context.get("dept")) or _text(context.get("department")),
        "document_alias": None,
        "document_type": None,
        "qc_point_type": None,
        "rule_ids": rule_ids,
    }
    llm_intent, llm_warnings = resolve_intent_with_llm(message, context)
    warnings.extend(llm_warnings)
    if llm_intent:
        intent = merge_llm_intent(intent, llm_intent)
    else:
        intent.update(
            {
                "task_type": "unsupported",
                "capability": "unsupported",
                "result_type": "unsupported",
                "intent_router": "llm_unavailable",
            }
        )
    if safety_unsupported:
        intent.update(
            {
                "unsupported": True,
                "task_type": "unsupported",
                "capability": "unsupported",
                "result_type": "unsupported",
            }
        )
        intent.pop("intent_router", None)
    if not intent.get("visit_id"):
        intent["visit_id"] = _infer_visit_id(message, context)
    if not intent.get("patient_name"):
        intent["patient_name"] = _infer_patient_name(message)
    if not intent.get("department"):
        intent["department"] = _infer_department(message)
    if rule_ids:
        merged_rule_ids = list(dict.fromkeys(list(intent.get("rule_ids") or []) + rule_ids))
        intent["rule_ids"] = merged_rule_ids
    if intent.get("source") == "all":
        intent["source"] = None
    if intent.get("capability") == "list_qc_rules" and "source" not in intent:
        intent["source"] = "sc146"
    if intent.get("document_alias") == "frontpage":
        warnings.append("当前自然语言编排仅支持单病历文书质控，病案首页请使用 run_frontpage_qc 工具")
    if rule_ids and not intent.get("qc_point_type"):
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


def _result_type_from_intent(intent: Dict[str, Any], result: Dict[str, Any] | None = None) -> str:
    capability = _text(intent.get("capability"))
    raw_type = _text(intent.get("result_type"))
    if capability == "list_qc_rules" or "rules" in (result or {}):
        return "qc_rules_catalog"
    if capability == "run_document_qc" or "qc_summary" in (result or {}):
        return "document_qc_report"
    if capability == "search_icd_codes":
        return "icd_candidates"
    if capability == "suggest_record_icd_codes":
        return "record_icd_suggestions"
    if capability == "predict_dip_group":
        return "dip_grouping_result"
    if capability == "predict_drg_group":
        return "drg_grouping_result"
    if raw_type == "dip_group":
        return "dip_grouping_result"
    if raw_type == "drg_group":
        return "drg_grouping_result"
    return raw_type or "clarification"


def _result_title(result_type: str, result: Dict[str, Any] | None = None) -> str:
    if result_type == "qc_rules_catalog":
        return "规则目录"
    if result_type == "document_qc_report":
        return "文书质控报告"
    if result_type == "icd_candidates":
        query = _text((result or {}).get("query"))
        return f"ICD 候选检索：{query}" if query else "ICD 候选检索"
    if result_type == "record_icd_suggestions":
        return "当前病历编码建议"
    if result_type == "dip_grouping_result":
        return "DIP 模拟入组"
    if result_type == "drg_grouping_result":
        return "DRG 模拟入组"
    if result_type == "system_health":
        return "智能助手配置异常"
    if result_type == "unsupported":
        return "暂不支持的请求"
    return "需要补充信息"


def _summary_from_result(result_type: str, result: Dict[str, Any]) -> Dict[str, Any]:
    if result_type == "qc_rules_catalog":
        return {
            "returned": result.get("returned"),
            "total": result.get("total"),
            "document_alias": (result.get("filters") or {}).get("document_alias"),
            "document_type": (result.get("filters") or {}).get("document_type"),
            "source": (result.get("filters") or {}).get("source"),
        }
    if result_type == "document_qc_report":
        return dict(result.get("qc_summary") or {})
    if result_type == "icd_candidates":
        return {
            "query": result.get("query"),
            "code_type": result.get("code_type"),
            "version": result.get("version"),
            "returned": result.get("returned"),
            "total": result.get("total"),
        }
    if result_type == "record_icd_suggestions":
        return {
            "diagnosis_count": len(result.get("diagnosis_candidates") or []),
            "procedure_count": len(result.get("procedure_candidates") or []),
        }
    if result_type in {"dip_grouping_result", "drg_grouping_result"}:
        return dict(result.get("input_summary") or {})
    return {}


def _cards_from_result(result_type: str, result: Dict[str, Any]) -> List[Dict[str, Any]]:
    if result_type == "qc_rules_catalog":
        return [
            {
                "card_type": "qc_rules_catalog",
                "title": "质控规则",
                "summary": _summary_from_result(result_type, result),
                "items": list(result.get("rules") or []),
            }
        ]
    if result_type == "document_qc_report":
        return [
            {
                "card_type": "document_qc_report",
                "title": "质控结果",
                "summary": dict(result.get("qc_summary") or {}),
                "items": list(result.get("issues") or result.get("results") or []),
                "data": {
                    "executed_rules": result.get("executed_rules") or [],
                    "skipped_rules": result.get("skipped_rules") or [],
                    "record_summary": result.get("record_summary") or {},
                    "document_selection_summary": result.get("document_selection_summary") or {},
                },
            }
        ]
    if result_type == "icd_candidates":
        return [
            {
                "card_type": "icd_candidates",
                "title": "候选编码",
                "summary": _summary_from_result(result_type, result),
                "items": list(result.get("candidates") or []),
            }
        ]
    if result_type == "record_icd_suggestions":
        return [
            {
                "card_type": "record_icd_suggestions",
                "title": "编码建议",
                "summary": _summary_from_result(result_type, result),
                "data": {
                    "diagnosis_candidates": result.get("diagnosis_candidates") or [],
                    "procedure_candidates": result.get("procedure_candidates") or [],
                },
            }
        ]
    if result_type in {"dip_grouping_result", "drg_grouping_result", "system_health", "clarification", "unsupported"}:
        return [{"card_type": result_type, "title": _result_title(result_type, result), "summary": _summary_from_result(result_type, result), "data": result}]
    return []


def _envelope_result(intent: Dict[str, Any], result: Dict[str, Any] | None, *, result_type: str | None = None) -> Dict[str, Any] | None:
    if result is None:
        return None
    normalized_type = result_type or _result_type_from_intent(intent, result)
    envelope = {
        "result_type": normalized_type,
        "title": _result_title(normalized_type, result),
        "summary": _summary_from_result(normalized_type, result),
        "cards": _cards_from_result(normalized_type, result),
        "actions": [],
        "raw_kind": _text(intent.get("capability")) or normalized_type,
    }
    envelope.update(result)
    return envelope


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
        result=_envelope_result(intent, {"warnings": warnings}, result_type="clarification"),
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
        result=_envelope_result(intent, result),
        legacy_result=result,
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


def _resolve_chat_institute_scope(current_user: Dict[str, Any] | None) -> tuple[bool, str | None]:
    """解析对话请求者的院区作用域。

    返回 `(is_scoped, allowed_institute_id)`：
    - `current_user is None` 或全局角色（admin/super_admin/sync_admin）返回 `(False, None)`；
    - 非全局角色优先从持久 `SysUser` 读取院区与角色，否则回退 `current_user['institute_id']`。
    """
    if not isinstance(current_user, dict):
        return False, None

    actor_id = _text(current_user.get("id") or current_user.get("user_id"))
    if actor_id:
        try:
            from app.database.connection import SessionLocal
            from app.services.defect_rectification_service import _person

            if SessionLocal is not None:
                with SessionLocal() as session:
                    actor = _person(session, actor_id)
                if actor["roles"] & _GLOBAL_SCOPE_ROLES:
                    return False, None
                return True, _text(actor.get("institute_id")) or None
        except Exception:
            pass

    roles = set(effective_roles(current_user.get("roles")))
    single_role = _text(current_user.get("role"))
    if single_role:
        roles.update(effective_roles([single_role]))
    if roles & _GLOBAL_SCOPE_ROLES:
        return False, None
    return True, _text(current_user.get("institute_id")) or None


def _lookup_visit_institutes(visit_ids: List[str]) -> Dict[str, set[str]]:
    """从本地 CDM 索引表查询 visit_id 对应的院区集合（用于非全局角色的院区隔离校验）。"""
    normalized_ids = [vid for vid in dict.fromkeys(_text(v) for v in visit_ids) if vid]
    if not normalized_ids:
        return {}
    mapping: Dict[str, set[str]] = {}
    try:
        from app.database.connection import SessionLocal
        from app.database.models.cdm import InpatRegistration, MedicalRecordFrontpage

        if SessionLocal is None:
            return {}
        with SessionLocal() as session:
            for model in (MedicalRecordFrontpage, InpatRegistration):
                try:
                    rows = (
                        session.query(model.visit_id, model.institute_id)
                        .filter(model.visit_id.in_(normalized_ids))
                        .all()
                    )
                    for vid, inst in rows:
                        vid_s = _text(vid)
                        inst_s = _text(inst)
                        if vid_s and inst_s:
                            mapping.setdefault(vid_s, set()).add(inst_s)
                except Exception:
                    continue
    except Exception:
        return {}
    return mapping


def _require_scoped_institute(
    is_scoped: bool,
    allowed_institute: str | None,
    request: QCAgentChatRequest,
) -> None:
    if not is_scoped:
        return
    if not allowed_institute:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号缺少可信院区归属，无法查询或质控病历",
        )
    for container in (request.user_context, request.confirm_selection):
        if isinstance(container, dict):
            req_inst = _text(container.get("institute_id"))
            if req_inst and req_inst != allowed_institute:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权查询或质控其他院区病历",
                )


def _filter_candidates_by_institute(
    candidates: List[Dict[str, Any]],
    *,
    is_scoped: bool,
    allowed_institute: str | None,
) -> List[Dict[str, Any]]:
    if not is_scoped:
        return candidates
    if not allowed_institute:
        return []
    db_map = _lookup_visit_institutes([_text(c.get("visit_id")) for c in candidates])
    filtered: List[Dict[str, Any]] = []
    for cand in candidates:
        cand_inst = _text(cand.get("institute_id"))
        if cand_inst:
            if cand_inst == allowed_institute:
                filtered.append(cand)
            continue
        vid = _text(cand.get("visit_id"))
        known_insts = db_map.get(vid, set())
        if allowed_institute in known_insts:
            filtered.append(cand)
    return filtered


def _enforce_visit_institute_access(
    visit_id: str,
    *,
    is_scoped: bool,
    allowed_institute: str | None,
    confirmed_institute: str = "",
) -> None:
    if not is_scoped:
        return
    if not allowed_institute:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前账号缺少可信院区归属，无法访问病历",
        )
    if confirmed_institute:
        if confirmed_institute != allowed_institute:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问其他院区病历",
            )
        return
    db_map = _lookup_visit_institutes([visit_id])
    known_insts = db_map.get(_text(visit_id), set())
    if allowed_institute not in known_insts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问其他院区或未确认院区归属的病历",
        )


def _record_ref_from_confirmation(confirm_selection: Dict[str, Any] | None) -> Dict[str, str]:
    if not isinstance(confirm_selection, dict):
        return {}
    return {
        "visit_id": _text(confirm_selection.get("visit_id")),
        "patient_id": _text(confirm_selection.get("patient_id")),
        "institute_id": _text(confirm_selection.get("institute_id")),
    }


def _search_candidates(
    registry: AgentToolRegistry,
    intent: Dict[str, Any],
    plan: List[Dict[str, Any]],
    *,
    is_scoped: bool = False,
    allowed_institute: str | None = None,
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
    records = list(public_data.get("records") or [])
    return _filter_candidates_by_institute(
        records,
        is_scoped=is_scoped,
        allowed_institute=allowed_institute,
    )


def _resolve_single_record_for_coding(
    *,
    request: QCAgentChatRequest,
    registry: AgentToolRegistry,
    run_id: str,
    intent: Dict[str, Any],
    plan: List[Dict[str, Any]],
    warnings: List[str],
    is_scoped: bool = False,
    allowed_institute: str | None = None,
) -> tuple[str, str, QCAgentChatResponse | None]:
    _require_scoped_institute(is_scoped, allowed_institute, request)
    confirmed_ref = _record_ref_from_confirmation(request.confirm_selection)
    visit_id = confirmed_ref.get("visit_id") or intent.get("visit_id")
    patient_id = confirmed_ref.get("patient_id") or intent.get("patient_id")
    if visit_id:
        _enforce_visit_institute_access(
            _text(visit_id),
            is_scoped=is_scoped,
            allowed_institute=allowed_institute,
        )
        return _text(visit_id), _text(patient_id), None
    candidates = _search_candidates(
        registry,
        intent,
        plan,
        is_scoped=is_scoped,
        allowed_institute=allowed_institute,
    )
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
    is_scoped: bool = False,
    allowed_institute: str | None = None,
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
            is_scoped=is_scoped,
            allowed_institute=allowed_institute,
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


def run_intent(
    request: QCAgentChatRequest,
    registry: AgentToolRegistry,
    *,
    current_user: Dict[str, Any] | None = None,
) -> QCAgentChatResponse:
    run_id = str(uuid.uuid4())
    plan: List[Dict[str, Any]] = []
    is_scoped, allowed_institute = _resolve_chat_institute_scope(current_user)
    intent, warnings = parse_intent(request)
    if intent.get("intent_router") == "llm_unavailable":
        response = QCAgentChatResponse(
            status="needs_clarification",
            parsed_intent=intent,
            plan=plan,
            result=_envelope_result(
                intent,
                {
                    "intent_router_enabled": False,
                    "last_check_status": "unavailable",
                    "last_error_summary": "LLM 意图识别不可用",
                    "degraded_reason": "LLM 意图识别不可用，未执行规则兜底，请检查 LLM 配置后重试",
                    "can_chat_execute": False,
                },
                result_type="system_health",
            ),
            warnings=warnings + ["LLM 意图识别不可用，未执行规则兜底，请检查 LLM 配置后重试"],
            run_id=run_id,
            session_id=request.session_id,
        )
        assert_no_sensitive_output(response.model_dump())
        return response

    if intent.get("unsupported") or intent.get("capability") == "unsupported":
        unsupported_warning = (
            "当前受控 Agent 不支持写入、删除、导出或持久化类操作"
            if intent.get("unsupported")
            else "当前问题未匹配到可执行的受控工具"
        )
        response = QCAgentChatResponse(
            status="unsupported",
            parsed_intent=intent,
            plan=plan,
            result=_envelope_result(intent, {"warnings": warnings + [unsupported_warning]}, result_type="unsupported"),
            warnings=warnings + [unsupported_warning],
            run_id=run_id,
            session_id=request.session_id,
        )
        assert_no_sensitive_output(response.model_dump())
        return response

    if intent.get("capability") == "list_qc_rules":
        result = _execute_tool(
            registry,
            "list_qc_rules",
            {
                "document_alias": intent.get("document_alias"),
                "document_type": intent.get("document_type"),
                "qc_point_type": intent.get("qc_point_type"),
                "source": intent.get("source"),
                "limit": 50,
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

    capability_response = _run_coding_or_grouping_intent(
        request=request,
        registry=registry,
        run_id=run_id,
        intent=intent,
        plan=plan,
        warnings=warnings,
        is_scoped=is_scoped,
        allowed_institute=allowed_institute,
    )
    if capability_response is not None:
        return capability_response

    if intent.get("document_alias") == "frontpage":
        response = QCAgentChatResponse(
            status="unsupported",
            parsed_intent=intent,
            plan=plan,
            result=_envelope_result(intent, {"warnings": warnings}, result_type="unsupported"),
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

    _require_scoped_institute(is_scoped, allowed_institute, request)
    confirmed_ref = _record_ref_from_confirmation(request.confirm_selection)
    visit_id = confirmed_ref.get("visit_id") or intent.get("visit_id")
    patient_id = confirmed_ref.get("patient_id") or intent.get("patient_id")
    candidates: List[Dict[str, Any]] = []
    matched_candidate_institute = ""
    if not visit_id:
        candidates = _search_candidates(
            registry,
            intent,
            plan,
            is_scoped=is_scoped,
            allowed_institute=allowed_institute,
        )
        if not candidates:
            response = QCAgentChatResponse(
                status="needs_clarification",
                parsed_intent=intent,
                plan=plan,
                candidates=[],
                result=_envelope_result(intent, {"warnings": warnings + ["未找到匹配病历，请补充 visit_id、住院号、患者姓名或科室"]}, result_type="clarification"),
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
                result=_envelope_result(
                    intent,
                    {"confirmation_type": "record_selection", "candidates": candidates},
                    result_type="clarification",
                ),
                warnings=warnings + ["命中多份病历，请确认单个 visit_id 后再执行质控"],
                run_id=run_id,
                session_id=request.session_id,
            )
            assert_no_sensitive_output(response.model_dump())
            return response
        visit_id = candidates[0].get("visit_id", "")
        patient_id = patient_id or candidates[0].get("patient_id", "")
        matched_candidate_institute = _text(candidates[0].get("institute_id"))
    _enforce_visit_institute_access(
        _text(visit_id),
        is_scoped=is_scoped,
        allowed_institute=allowed_institute,
        confirmed_institute=matched_candidate_institute,
    )

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
        result=_envelope_result(intent, result),
        legacy_result=result,
        warnings=response_warnings,
        run_id=run_id,
        session_id=request.session_id,
    )
    assert_no_sensitive_output(response.model_dump())
    return response
