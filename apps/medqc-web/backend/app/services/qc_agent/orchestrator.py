from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List

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
        "visit_id": _first_pattern([r"visit_id\s*[=:：]?\s*([A-Za-z0-9_-]+)"], message)
        or _text(context.get("visit_id")),
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
    _execute_tool(registry, "get_record_context", context_args, plan)

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
    _execute_tool(registry, "select_record_documents", select_args, plan)

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
    result = _execute_tool(registry, "run_document_qc", run_args, plan)
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
