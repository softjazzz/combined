import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from starlette import status

from ..core.http import safe_post_json
from ..core.settings import get_settings
from .llm_config_loader import LLMConfigLoader
from .llm_observability import observe_llm_http_attempt
from .document_domain_alignment import align_document_domain_fields
from .sichuan_qc_service import SichuanQCService

logger = logging.getLogger(__name__)

GENERATION_SYSTEM_PROMPT = (
    "你是一名资深病历质控专家和医疗提示词工程师。"
    "你的任务是根据给定场景与质控点描述，生成一个可直接用于病历质控的中文 Prompt。"
    "输出必须是合法 JSON，不要输出额外说明。"
)

SEVERITY_TO_DEFECT_LEVEL = {
    "critical": "严重缺陷",
    "major": "一般缺陷",
    "minor": "提示性缺陷",
}


def normalize_document_type(document_type: Optional[str]) -> str:
    return (document_type or "日常病程记录").strip() or "日常病程记录"


def severity_to_defect_level(severity: Optional[str]) -> str:
    return SEVERITY_TO_DEFECT_LEVEL.get(str(severity or "").strip().lower(), "一般缺陷")


def build_inline_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    check_logic = dict(rule.get("check_logic") or {})
    document_type, applicable_documents, aligned_check_logic = align_document_domain_fields(
        document_type=rule.get("document_type"),
        applicable_documents=rule.get("applicable_documents") or check_logic.get("applicable_documents"),
        check_logic=check_logic,
    )
    prompt_template = str(rule.get("prompt_template") or "").strip()
    raw_executor_type = str(rule.get("executor_type") or "").strip().lower()
    executor_type = raw_executor_type if raw_executor_type in {"llm", "program"} else "llm"

    return {
        "rule_id": str(rule.get("rule_code") or "INLINE-DRAFT"),
        "rule_code": str(rule.get("rule_code") or "INLINE-DRAFT"),
        "name": str(rule.get("name") or "未命名质控点"),
        "description": str(rule.get("description") or "").strip(),
        "category": document_type,
        "defect_level": severity_to_defect_level(rule.get("severity")),
        "complexity": "中复杂度",
        "applicable_documents": applicable_documents,
        "custom_prompt": prompt_template or build_fallback_prompt(
            scene=str(rule.get("scene") or ""),
            document_type=document_type,
            rule_name=str(rule.get("name") or "未命名质控点"),
            description=str(rule.get("description") or "").strip(),
            check_points=[],
        )["prompt_template"],
        "check_logic": aligned_check_logic,
        "executor_type": executor_type,
        "execution_domain": str(
            rule.get("execution_domain") or aligned_check_logic.get("execution_domain") or ""
        ).strip(),
        "doc_scope": str(rule.get("doc_scope") or aligned_check_logic.get("doc_scope") or "primary").strip(),
        "rule_version": str(rule.get("rule_version") or "workspace-v1").strip(),
        "prompt_version": str(rule.get("prompt_version") or "workspace-prompt-v1").strip(),
        "cost_class": str(rule.get("cost_class") or ("low" if executor_type == "program" else "medium")).strip(),
    }


def build_fallback_prompt(
    scene: str,
    document_type: str,
    rule_name: str,
    description: str,
    check_points: List[str],
) -> Dict[str, Any]:
    normalized_points = [point.strip() for point in check_points if str(point).strip()]
    if not normalized_points:
        normalized_points = [
            f"检查{document_type}中是否满足“{rule_name}”要求",
            "定位病历原文中的明确证据或缺失点",
            "结合上下文判断问题是否成立，避免过度推断",
        ]

    prompt_template = (
        "你是一名经验丰富的病历质控专家，负责审阅病历并判断是否符合指定质控点。\n\n"
        f"【适用场景】\n{scene or '病历质控'}\n\n"
        f"【文书类型】\n{document_type}\n\n"
        f"【质控点名称】\n{rule_name}\n\n"
        f"【质控要求】\n{description}\n\n"
        "【检查要点】\n"
        + "\n".join(f"{index + 1}. {point}" for index, point in enumerate(normalized_points))
        + "\n\n【输出要求】\n"
        "请严格输出一个 JSON 对象：\n"
        "{\n"
        '  "is_compliant": true/false,\n'
        '  "findings": "汇总判断依据，如不适用请说明原因",\n'
        '  "issues": [\n'
        '    {\n'
        '      "description": "问题描述（简洁明确）",\n'
        '      "evidence": "问题位置或证据摘要"\n'
        "    }\n"
        "  ],\n"
        '  "evidence": "必须引用病历原文或明确说明缺失项",\n'
        '  "suggestion": "给出具体整改建议，使用(1)(2)(3)格式",\n'
        '  "confidence": 0.6\n'
        "}\n\n"
        "【待评估病历文本】\n{medical_text}\n"
    )

    return {
        "prompt_template": prompt_template,
        "generation_mode": "fallback_template",
        "summary": f"围绕“{rule_name}”生成了可直接测试的质控 Prompt。",
        "check_points": normalized_points,
        "examples": [],
    }


def _build_prompt_generation_user_prompt(
    scene: str,
    document_type: str,
    rule_name: str,
    description: str,
    severity: str,
) -> str:
    return (
        "请根据以下输入生成一个病历质控 Prompt。\n\n"
        f"场景：{scene}\n"
        f"文书类型：{document_type}\n"
        f"质控点名称：{rule_name}\n"
        f"质控点描述：{description}\n"
        f"严重程度：{severity}\n\n"
        "请严格输出以下 JSON 结构：\n"
        "{\n"
        '  "prompt_template": "完整中文 Prompt，必须包含 {medical_text} 占位符",\n'
        '  "summary": "80字以内概述",\n'
        '  "check_points": ["检查要点1", "检查要点2", "检查要点3"],\n'
        '  "examples": [\n'
        '    { "title": "示例标题", "content": "简短示例内容" }\n'
        "  ]\n"
        "}\n\n"
        "要求：\n"
        "1. Prompt 必须明确检查要点、分析方法和输出 JSON 要求。\n"
        "2. 输出 JSON 中不要包含 markdown 代码块。\n"
        "3. 示例可以为空数组，但 check_points 至少 3 条。\n"
    )


def _extract_json_payload(raw_text: str) -> Dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?", "", raw_text.strip(), flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("未找到合法 JSON 对象")

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM 返回内容不是 JSON 对象")
    return parsed


async def generate_custom_prompt(
    *,
    scene: str,
    document_type: str,
    rule_name: str,
    description: str,
    severity: str,
) -> Dict[str, Any]:
    settings = get_settings()
    endpoint = os.getenv("DEMO_RULE_LLM_ENDPOINT") or settings.LLM_API_ENDPOINT
    api_key = os.getenv("DEMO_RULE_LLM_API_KEY") or settings.LLM_API_KEY
    model = os.getenv("DEMO_RULE_LLM_MODEL") or settings.LLM_MODEL

    fallback = build_fallback_prompt(
        scene=scene,
        document_type=document_type,
        rule_name=rule_name,
        description=description,
        check_points=[],
    )

    if not endpoint or not api_key or not model:
        logger.warning("custom-qc Prompt 生成缺少 LLM 配置，回退模板生成")
        return fallback

    target_url = str(endpoint).rstrip("/")
    if not target_url.endswith("/chat/completions"):
        target_url = f"{target_url}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_prompt_generation_user_prompt(
                    scene=scene,
                    document_type=document_type,
                    rule_name=rule_name,
                    description=description,
                    severity=severity,
                ),
            },
        ],
    }
    llm_response = await observe_llm_http_attempt(
        lambda: safe_post_json(
            target_url,
            headers,
            payload,
            timeout_seconds=60,
        ),
        provider_code=str(
            getattr(settings, "LLM_DEFAULT_PROVIDER", None) or "unknown"
        ),
        model=str(model),
        business_scene="custom_qc_prompt_generation",
        executor_key="custom_qc_prompt_generation",
    )

    if isinstance(llm_response, dict) and llm_response.get("__error__"):
        logger.warning("custom-qc Prompt 生成调用 LLM 失败，回退模板生成: %s", llm_response)
        return fallback

    try:
        content = (
            llm_response.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _extract_json_payload(content)
        prompt_template = str(parsed.get("prompt_template") or "").strip()
        if "{medical_text}" not in prompt_template:
            raise ValueError("prompt_template 缺少 {medical_text} 占位符")

        check_points = [
            str(point).strip()
            for point in (parsed.get("check_points") or [])
            if str(point).strip()
        ]

        examples = []
        for example in parsed.get("examples") or []:
            if isinstance(example, dict):
                title = str(example.get("title") or "").strip()
                content_text = str(example.get("content") or "").strip()
                if title or content_text:
                    examples.append({"title": title, "content": content_text})

        return {
            "prompt_template": prompt_template,
            "generation_mode": "llm",
            "summary": str(parsed.get("summary") or "").strip() or fallback["summary"],
            "check_points": check_points or fallback["check_points"],
            "examples": examples,
        }
    except Exception as exc:
        logger.warning("custom-qc Prompt 生成解析失败，回退模板生成: %s", exc)
        return fallback


async def create_custom_qc_service() -> SichuanQCService:
    try:
        config = await LLMConfigLoader.load_config(config_name="default", user_id=None)
        return SichuanQCService(config)
    except Exception as exc:
        logger.warning("加载默认 LLM 配置失败，custom-qc 使用 .env 配置: %s", exc)
        return SichuanQCService()


async def evaluate_inline_rule(
    *,
    qc_service: SichuanQCService,
    rule: Dict[str, Any],
    record: Dict[str, Any],
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """
    兼容旧调用入口，内部统一走 orchestrator 执行链。
    """
    return await evaluate_inline_rule_orchestrated(
        qc_service=qc_service,
        rule=rule,
        record=record,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )


async def evaluate_inline_rule_orchestrated(
    *,
    qc_service: SichuanQCService,
    rule: Dict[str, Any],
    record: Dict[str, Any],
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    if temperature is not None:
        qc_service.client.temperature = temperature
    if top_p is not None:
        qc_service.client.top_p = top_p
    if max_tokens is not None:
        qc_service.client.max_tokens = max_tokens

    inline_rule = build_inline_rule(rule)
    ensure_meta = getattr(qc_service, "_ensure_rule_execution_meta", None)
    if callable(ensure_meta):
        try:
            inline_rule = ensure_meta(inline_rule)
        except Exception:
            logger.warning("custom-qc 内联规则补齐执行元数据失败，回退原始规则", exc_info=True)

    started_at = time.perf_counter()
    medical_record: Dict[str, Any] = {
        "id": str(record.get("record_id") or record.get("visit_id") or record.get("id") or ""),
        "content": str(record.get("medical_text") or ""),
        "document_type": str(inline_rule.get("category") or normalize_document_type(rule.get("document_type"))),
    }
    if str(record.get("institute_id") or "").strip():
        medical_record["institute_id"] = str(record.get("institute_id")).strip()
    if str(record.get("patient_id") or "").strip():
        medical_record["patient_id"] = str(record.get("patient_id")).strip()
    if str(record.get("visit_id") or "").strip():
        medical_record["visit_id"] = str(record.get("visit_id")).strip()
    if str(record.get("source_schema") or "").strip():
        medical_record["source_schema"] = str(record.get("source_schema")).strip()
    if isinstance(record.get("evidence_payload"), dict) and record.get("evidence_payload"):
        medical_record["evidence_payload"] = dict(record["evidence_payload"])
    medical_record["llm_sampling_params"] = {
        "temperature": getattr(qc_service.client, "temperature", None),
        "top_p": getattr(qc_service.client, "top_p", None),
        "max_tokens": getattr(qc_service.client, "max_tokens", None),
    }

    async def _llm_evaluate(candidate_rule: Dict[str, Any], candidate_record: Dict[str, Any]) -> Dict[str, Any]:
        return await qc_service.rule_engine.evaluate(
            rule=candidate_rule,
            medical_record=candidate_record,
        )

    orchestrated = await qc_service.rule_orchestrator.evaluate_rules(
        rules=[inline_rule],
        medical_record=medical_record,
        llm_evaluate=_llm_evaluate,
        evidence_source="custom_qc_workspace",
        llm_concurrency=1,
        model_version=str(qc_service.client.model or ""),
        execution_cache=qc_service.execution_cache,
        cache_ttl_seconds=1800,
    )
    orchestrated_results = list(orchestrated.get("results") or [])
    if not orchestrated_results:
        raise ValueError("自定义规则执行失败：未返回结果")
    result = orchestrated_results[0]

    duration = time.perf_counter() - started_at
    metadata = result.get("metadata", {}) or {}

    return {
        "record_id": str(record.get("record_id") or ""),
        "visit_id": str(record.get("visit_id") or ""),
        "patient_name": str(record.get("patient_name") or ""),
        "department": str(record.get("department") or ""),
        "document_type": str(inline_rule.get("category") or normalize_document_type(rule.get("document_type"))),
        "status": result.get("status"),
        "is_compliant": result.get("is_compliant", True),
        "issues": result.get("issues", []),
        "findings": result.get("findings", ""),
        "evidence": result.get("evidence", ""),
        "suggestion": result.get("suggestion", ""),
        "confidence": result.get("confidence", 0.7),
        "llm_raw_output": result.get("llm_raw_output"),
        "applicability": result.get("applicability"),
        "evidence_verified": result.get("evidence_verified", True),
        "evidence_span": result.get("evidence_span"),
        "metadata": metadata,
        "executor_breakdown": orchestrated.get("executor_breakdown") or {},
        "cache_breakdown": orchestrated.get("cache_breakdown") or {},
        "trace": orchestrated.get("trace") or [],
        "performance": {
            "processing_time": duration,
            "token_usage": int(metadata.get("tokens_used") or 0),
            "estimated_cost": float(metadata.get("tokens_used") or 0) / 1000 * 0.002,
        },
    }


def ensure_record_medical_text(records: List[Dict[str, Any]]) -> None:
    for index, record in enumerate(records):
        medical_text = str(record.get("medical_text") or "").strip()
        if not medical_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"第 {index + 1} 条病历缺少 medical_text",
            )
