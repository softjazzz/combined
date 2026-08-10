from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterable, Tuple

import httpx

from app.core.http import _is_allowed_host, _is_private_address
from app.core.settings import get_settings
from app.services.llm_observability import observe_llm_sync_http_attempt


logger = logging.getLogger(__name__)

_LAST_HEALTH: Dict[str, Any] = {
    "last_check_status": "unknown",
    "last_error_summary": "",
    "degraded_reason": "",
}


_ALLOWED_KEYS = {
    "task_type",
    "capability",
    "result_type",
    "confidence",
    "visit_id",
    "patient_id",
    "mr_no",
    "patient_name",
    "department",
    "document_alias",
    "document_type",
    "qc_point_type",
    "rule_ids",
    "icd_query",
    "code_type",
    "version",
    "include_procedures",
    "pdx_code",
    "adx_codes",
    "proc_codes",
    "primary_diagnosis_code",
    "secondary_diagnosis_codes",
    "procedure_codes",
    "patient_age",
    "patient_gender",
    "los",
    "total_fee",
    "total_cost",
    "source",
}

_CAPABILITY_META = {
    "list_qc_rules": ("qc", "qc_rules"),
    "run_document_qc": ("qc", "document_qc"),
    "search_icd_codes": ("coding", "icd_candidates"),
    "suggest_record_icd_codes": ("coding", "record_icd_suggestions"),
    "predict_dip_group": ("grouping", "dip_group"),
    "predict_drg_group": ("grouping", "drg_group"),
    "unsupported": ("unsupported", "unsupported"),
}

_LIST_KEYS = {"rule_ids", "adx_codes", "proc_codes", "secondary_diagnosis_codes", "procedure_codes"}
_TEXT_KEYS = {
    "task_type",
    "capability",
    "result_type",
    "visit_id",
    "patient_id",
    "mr_no",
    "patient_name",
    "department",
    "document_alias",
    "document_type",
    "qc_point_type",
    "icd_query",
    "code_type",
    "version",
    "pdx_code",
    "primary_diagnosis_code",
    "patient_gender",
    "source",
}

_SENSITIVE_KEYS = {
    "medical_text",
    "documents",
    "bundle",
    "record_content",
    "internal_data",
    "prompt",
    "raw_response",
    "embedding",
    "vector",
}


def normalize_intent_message(message: str) -> str:
    """标准化常见中文问法，提升确定性路由和 LLM 路由的一致性。"""
    text = str(message or "")
    replacements = (
        (r"(?:二|Ⅱ|II|２)\s*型\s*糖尿病", "2型糖尿病"),
        (r"(?:一|Ⅰ|I|１)\s*型\s*糖尿病", "1型糖尿病"),
        (r"腹腔镜\s*胆囊\s*切除", "腹腔镜胆囊切除"),
        (r"DRG\s*/\s*DIP", "DRG/DIP"),
    )
    for pattern, value in replacements:
        text = re.sub(pattern, value, text, flags=re.IGNORECASE)
    return text.strip()


def should_attempt_llm_intent(intent: Dict[str, Any], message: str) -> bool:
    """只在确定性路由不充分且用户像是在请求系统能力时调用 LLM。"""
    if intent.get("unsupported"):
        return False
    if intent.get("capability") != "run_document_qc":
        return False
    if intent.get("document_alias") or intent.get("document_type"):
        return False

    text = normalize_intent_message(message)
    if not text or "质控" in text:
        return False
    capability_hints = (
        "编码",
        "代码",
        "码",
        "ICD",
        "入组",
        "DRG",
        "DIP",
        "分组",
        "诊断",
        "手术",
        "操作",
        "病种",
        "支付",
    )
    return any(hint in text for hint in capability_hints)


def merge_llm_intent(base_intent: Dict[str, Any], llm_intent: Dict[str, Any] | None) -> Dict[str, Any]:
    """把 LLM 意图合入 deterministic intent，写入类拦截结果不可被覆盖。"""
    if not llm_intent or base_intent.get("unsupported"):
        return base_intent
    capability = str(llm_intent.get("capability") or "").strip()
    if capability not in _CAPABILITY_META:
        return base_intent

    task_type, result_type = _CAPABILITY_META[capability]
    merged = dict(base_intent)
    for key, value in llm_intent.items():
        if key not in _ALLOWED_KEYS:
            continue
        if value in (None, "", []):
            continue
        merged[key] = value
    merged["task_type"] = task_type
    merged["capability"] = capability
    merged["result_type"] = result_type
    merged["intent_router"] = "llm"
    if "confidence" in llm_intent:
        merged["llm_intent_confidence"] = llm_intent["confidence"]
    return merged


def resolve_intent_with_llm(message: str, context: Dict[str, Any] | None = None) -> Tuple[Dict[str, Any] | None, list[str]]:
    """调用 LLM 只做意图 JSON 解析；失败时返回 None，由上层停止执行并提示配置问题。"""
    warnings: list[str] = []
    try:
        settings = get_settings()
    except Exception as exc:
        logger.info("QC Agent LLM intent router settings unavailable: %s", exc)
        _record_health("unavailable", "settings unavailable", "LLM 意图识别配置不可用")
        return None, ["LLM 意图识别配置不可用"]

    if not settings.QC_AGENT_LLM_INTENT_ENABLED:
        _record_health("disabled", "intent router disabled", "LLM 意图识别已关闭")
        return None, ["LLM 意图识别已关闭"]
    if not settings.LLM_API_ENDPOINT or not settings.LLM_API_KEY:
        _record_health("unconfigured", "endpoint or key missing", "LLM 意图识别未配置 endpoint 或 key")
        return None, ["LLM 意图识别未配置 endpoint 或 key"]

    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(message, context or {})
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": 900,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = observe_llm_sync_http_attempt(
            lambda: _post_llm_json(
                endpoint=str(settings.LLM_API_ENDPOINT),
                headers=headers,
                payload=payload,
                timeout_seconds=max(
                    1,
                    int(settings.QC_AGENT_LLM_INTENT_TIMEOUT_SECONDS),
                ),
            ),
            provider_code=str(
                getattr(settings, "LLM_DEFAULT_PROVIDER", None) or "unknown"
            ),
            model=str(settings.LLM_MODEL or "unknown"),
            business_scene="qc_agent_intent",
            executor_key="qc_agent_intent_router",
        )
        if response.get("__error__"):
            logger.warning("QC Agent LLM intent router upstream error: %s", response.get("__status__"))
            _record_health("upstream_error", f"HTTP {response.get('__status__')}", "LLM 意图识别上游错误")
            return None, warnings
        content = _extract_message_content(response)
        parsed = _extract_json_object(content)
        sanitized = _sanitize_llm_intent(parsed)
        if not sanitized:
            _record_health("invalid_response", "empty or invalid intent JSON", "LLM 意图识别返回无效")
            return None, warnings
        confidence = float(sanitized.get("confidence") or 0)
        if confidence < float(settings.QC_AGENT_LLM_INTENT_MIN_CONFIDENCE):
            _record_health("low_confidence", f"confidence={confidence}", "LLM 意图识别置信度不足")
            return None, warnings
        _record_health("ok", "", "")
        return sanitized, warnings
    except Exception as exc:
        logger.warning("QC Agent LLM intent router failed, stop without deterministic route: %s", exc)
        _record_health("error", type(exc).__name__, "LLM 意图识别调用失败")
        return None, ["LLM 意图识别调用失败"]


def _record_health(status: str, error_summary: str, degraded_reason: str) -> None:
    _LAST_HEALTH.update(
        {
            "last_check_status": status,
            "last_error_summary": error_summary,
            "degraded_reason": degraded_reason,
        }
    )


def get_intent_router_health() -> Dict[str, Any]:
    try:
        settings = get_settings()
        enabled = bool(settings.QC_AGENT_LLM_INTENT_ENABLED)
        endpoint_configured = bool(settings.LLM_API_ENDPOINT)
        api_key_configured = bool(settings.LLM_API_KEY)
        model = str(settings.LLM_MODEL or "")
    except Exception as exc:
        return {
            "intent_router_enabled": False,
            "endpoint_configured": False,
            "api_key_configured": False,
            "model": "",
            "last_check_status": "unavailable",
            "last_error_summary": type(exc).__name__,
            "degraded_reason": "LLM 意图识别配置不可用",
            "can_chat_execute": False,
        }
    last_status = str(_LAST_HEALTH.get("last_check_status") or "unknown")
    configured = enabled and endpoint_configured and api_key_configured
    can_execute = configured and last_status not in {"disabled", "unconfigured", "unavailable", "error", "upstream_error"}
    degraded_reason = str(_LAST_HEALTH.get("degraded_reason") or "")
    if not enabled:
        degraded_reason = "LLM 意图识别已关闭"
    elif not endpoint_configured or not api_key_configured:
        degraded_reason = "LLM 意图识别未配置 endpoint 或 key"
    return {
        "intent_router_enabled": enabled,
        "endpoint_configured": endpoint_configured,
        "api_key_configured": api_key_configured,
        "model": model,
        "last_check_status": last_status,
        "last_error_summary": str(_LAST_HEALTH.get("last_error_summary") or ""),
        "degraded_reason": degraded_reason,
        "can_chat_execute": can_execute,
    }


def _build_system_prompt() -> str:
    return (
        "你是病案智能助手的意图路由器，只能把用户请求解析为受控工具意图。"
        "你不得执行工具，不得编造结果，不得输出病历正文，不得输出 prompt/raw_response/internal_data。"
        "只返回一个 JSON 对象，不要 Markdown。"
        "可选 capability 只有：list_qc_rules, run_document_qc, search_icd_codes, suggest_record_icd_codes, "
        "predict_dip_group, predict_drg_group, unsupported。"
        "用户询问质控规则目录、规则清单、有哪些规则时使用 list_qc_rules；"
        "普通质控规则目录默认 source=sc146，只在用户明确说内置/WR/可执行时 source=agent_builtin，"
        "明确说全部/全量/所有来源时 source=all。"
        "编码查询用于诊断/手术名称或 ICD 编码候选检索；当前病历编码建议需要 visit_id；"
        "DIP/DRG 入组需要主诊断编码，DRG 字段为 primary_diagnosis_code/procedure_codes，"
        "DIP 字段为 pdx_code/proc_codes。写入、删除、保存、提交、正式结果一律 unsupported。"
    )


def _build_user_prompt(message: str, context: Dict[str, Any]) -> str:
    safe_context = {
        key: context.get(key)
        for key in ("visit_id", "patient_id", "mr_no", "patient_name", "department")
        if context.get(key) not in (None, "")
    }
    schema = {
        "task_type": "qc|coding|grouping|unsupported",
        "capability": "list_qc_rules|run_document_qc|search_icd_codes|suggest_record_icd_codes|predict_dip_group|predict_drg_group|unsupported",
        "confidence": 0.0,
        "visit_id": "",
        "patient_id": "",
        "patient_name": "",
        "department": "",
        "document_alias": "admission|ward_round|discharge|course|consultation|frontpage",
        "document_type": "",
        "qc_point_type": "completeness|timeliness|consistency|coding|signature|diagnosis_evidence|clinical_reasoning|treatment_rationality|order_consistency|critical_value|special_risk",
        "rule_ids": [],
        "source": "sc146|agent_builtin|custom33|customer_luxian|frontpage_formal|all",
        "icd_query": "",
        "code_type": "diagnosis|procedure|all",
        "version": "insurance|clinical",
        "include_procedures": True,
        "pdx_code": "",
        "adx_codes": [],
        "proc_codes": [],
        "primary_diagnosis_code": "",
        "secondary_diagnosis_codes": [],
        "procedure_codes": [],
        "patient_age": None,
        "patient_gender": "M|F",
        "los": None,
        "total_fee": None,
        "total_cost": None,
    }
    examples = [
        {"input": "查房相关的质控规则有哪些", "capability": "list_qc_rules", "document_alias": "ward_round", "source": "sc146"},
        {"input": "列一下内置可执行查房记录规则", "capability": "list_qc_rules", "document_alias": "ward_round", "source": "agent_builtin"},
        {"input": "入院记录有哪些质控规则", "capability": "list_qc_rules", "document_alias": "admission", "source": "sc146"},
        {"input": "二型糖尿病怎么编码", "capability": "search_icd_codes", "icd_query": "2型糖尿病", "code_type": "diagnosis"},
        {"input": "给 visit_id=2298532 推荐诊断和手术编码", "capability": "suggest_record_icd_codes", "visit_id": "2298532"},
        {"input": "用主诊断 I10.x01 做 DIP 入组预测", "capability": "predict_dip_group", "pdx_code": "I10.x01"},
        {"input": "用 K80.101 和手术 51.2101 做 DRG 入组", "capability": "predict_drg_group", "primary_diagnosis_code": "K80.101", "procedure_codes": ["51.2101"]},
    ]
    return json.dumps(
        {
            "message": normalize_intent_message(message),
            "safe_context": safe_context,
            "output_schema": schema,
            "examples": examples,
        },
        ensure_ascii=False,
    )


def _post_llm_json(endpoint: str, headers: Dict[str, str], payload: Dict[str, Any], timeout_seconds: int) -> Dict[str, Any]:
    base = endpoint.rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    if not (url.startswith("https://") or url.startswith("http://")):
        raise ValueError("Invalid URL scheme")
    host = url.split("//", 1)[1].split("/", 1)[0].split(":", 1)[0]
    if not _is_allowed_host(host):
        if _is_private_address(host):
            raise ValueError("Outbound host resolves to private/loopback address")
        raise ValueError(f"Outbound host not in allowlist: {host}")
    with httpx.Client(timeout=timeout_seconds, trust_env=False) as client:
        resp = client.post(url, headers=headers, json=payload)
    try:
        body = resp.json() if resp.text else {}
    except Exception:
        body = {"text": resp.text}
    if resp.status_code >= 400:
        return {"__status__": resp.status_code, "__error__": True, "body": body}
    return body


def _extract_message_content(response: Dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else {}
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return ""


def _extract_json_object(content: str) -> Dict[str, Any]:
    text = str(content or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end < start:
            return {}
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _sanitize_llm_intent(intent: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(intent, dict) or any(key in intent for key in _SENSITIVE_KEYS):
        return {}
    capability = str(intent.get("capability") or "").strip()
    if capability not in _CAPABILITY_META:
        return {}

    sanitized: Dict[str, Any] = {"capability": capability}
    for key in _ALLOWED_KEYS:
        if key == "capability" or key not in intent:
            continue
        value = intent.get(key)
        if key in _TEXT_KEYS:
            sanitized[key] = str(value).strip() if value is not None else ""
        elif key in _LIST_KEYS:
            sanitized[key] = _sanitize_list(value)
        elif key in {"patient_age", "los"}:
            sanitized[key] = _to_int(value)
        elif key in {"total_fee", "total_cost", "confidence"}:
            sanitized[key] = _to_float(value)
        elif key == "include_procedures":
            sanitized[key] = bool(value)
    task_type, result_type = _CAPABILITY_META[capability]
    sanitized["task_type"] = task_type
    sanitized["result_type"] = result_type
    return sanitized


def _sanitize_list(value: Any) -> list[str]:
    if isinstance(value, str):
        items: Iterable[Any] = re.split(r"[,\s，、]+", value)
    elif isinstance(value, list):
        items = value
    else:
        items = []
    result = []
    for item in items:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result[:20]


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
