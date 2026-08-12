"""
LLM-based field mapping service.
从 drg 项目迁移并适配 medqc 项目。
支持将用户上传的 Excel 列名智能映射到标准分析字段。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List
from uuid import uuid4

import yaml
from openai import OpenAI
from dotenv import dotenv_values

from ..core.http import run_shared_http_call
from .llm_observability import (
    observe_llm_http_attempt,
    safe_status_for_exception,
)

# ========== 路径配置 ==========
SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")
FIELD_MAPPER_YAML = os.path.join(SKILLS_DIR, "field_mapper.yaml")

# 使用 medqc 后端的 .env
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_FIELD_MAPPER_MODEL = "deepseek-v3"

_config_cache: Dict[str, Any] | None = None
_config_mtime = 0.0
logger = logging.getLogger(__name__)


def _get_backend_env_fallback() -> Dict[str, str]:
    """直接读取 backend/.env（与当前工作目录无关）。"""
    env_file = os.path.join(BACKEND_DIR, ".env")
    if not os.path.exists(env_file):
        return {}
    try:
        raw = dotenv_values(env_file)
        return {str(k): str(v or "").strip() for k, v in raw.items()}
    except Exception:
        return {}


def _get_backend_llm_config() -> Dict[str, str]:
    """
    从后端统一配置读取 LLM 参数（作为环境变量的后备来源）。
    避免手工 uvicorn 启动时未 export .env 导致字段映射不可用。
    """
    try:
        from ..core.settings import get_settings

        settings = get_settings()
        return {
            "api_key": str(settings.LLM_API_KEY or "").strip(),
            "base_url": str(settings.LLM_API_ENDPOINT or "").strip(),
            "model": str(settings.LLM_MODEL or "").strip(),
        }
    except Exception:
        cfg = _get_backend_env_fallback()
        return {
            "api_key": cfg.get("LLM_API_KEY", ""),
            "base_url": cfg.get("LLM_API_ENDPOINT", ""),
            "model": cfg.get("LLM_MODEL", ""),
        }


def _get_dashscope_api_key() -> str:
    """获取 DashScope API Key，优先从环境变量读取"""
    key = (
        os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("ALIYUN_DASHSCOPE_API_KEY")
        or os.getenv("LLM_API_KEY")
        or _get_backend_llm_config().get("api_key", "")
        or ""
    ).strip()
    if not key:
        raise ValueError("Missing DASHSCOPE_API_KEY environment variable")
    return key


def _get_dashscope_base_url() -> str:
    return (
        os.getenv("DASHSCOPE_BASE_URL")
        or os.getenv("LLM_API_ENDPOINT")
        or _get_backend_llm_config().get("base_url", "")
        or DEFAULT_DASHSCOPE_BASE_URL
    ).strip()


def _get_field_mapper_model() -> str:
    return (
        os.getenv("FIELD_MAPPER_MODEL")
        or os.getenv("LLM_MODEL")
        or _get_backend_llm_config().get("model", "")
        or DEFAULT_FIELD_MAPPER_MODEL
    ).strip()


def _field_mapper_provider_code(base_url: str) -> str:
    """根据实际 OpenAI 兼容端点给出不含端点明文的供应商标识。"""
    normalized = str(base_url or "").strip().lower()
    if "dashscope.aliyuncs.com" in normalized:
        return "alibaba"
    if "api.deepseek.com" in normalized:
        return "deepseek"
    if "siliconflow" in normalized:
        return "siliconflow"
    return "openai_compatible"


def _sdk_usage_payload(response: Any) -> Dict[str, int] | None:
    """只提取 SDK usage 数值；不把响应对象交给观测存储。"""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    required_values = {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
    }
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in required_values.values()
    ):
        return None
    result = dict(required_values)
    total_tokens = getattr(usage, "total_tokens", None)
    if total_tokens is not None:
        if (
            isinstance(total_tokens, bool)
            or not isinstance(total_tokens, int)
            or total_tokens < 0
        ):
            return None
        result["total_tokens"] = total_tokens
    return result


def _load_field_config() -> Dict[str, Any]:
    """加载字段映射配置文件（带缓存）"""
    global _config_cache, _config_mtime
    try:
        current_mtime = os.path.getmtime(FIELD_MAPPER_YAML)
        if _config_cache is None or current_mtime > _config_mtime:
            with open(FIELD_MAPPER_YAML, "r", encoding="utf-8") as f:
                _config_cache = yaml.safe_load(f) or {}
            _config_mtime = current_mtime
        return _config_cache or {"standard_fields": []}
    except Exception:
        return {"standard_fields": []}


def get_standard_fields() -> Dict[str, Dict[str, Any]]:
    """获取标准字段定义"""
    config = _load_field_config()
    fields: Dict[str, Dict[str, Any]] = {}
    for field in config.get("standard_fields", []) or []:
        key = field.get("key")
        if not key:
            continue
        fields[str(key)] = {
            "name": field.get("name", str(key)),
            "description": ", ".join(field.get("aliases", []) or []),
            "required": bool(field.get("required", False)),
            "category": field.get("category", "other"),
            "aliases": field.get("aliases", []) or [],
        }
    return fields


def build_alias_map() -> Dict[str, str]:
    """构建别名到标准字段的映射表"""
    config = _load_field_config()
    alias_map: Dict[str, str] = {}
    for field in config.get("standard_fields", []) or []:
        key = str(field.get("key", "")).strip()
        if not key:
            continue
        name = str(field.get("name", "")).strip().lower()
        if name:
            alias_map[name] = key
        for alias in field.get("aliases", []) or []:
            alias_s = str(alias).strip().lower()
            if alias_s:
                alias_map[alias_s] = key
    return alias_map


STANDARD_FIELDS = get_standard_fields()


def _extract_json_object(text: str) -> str:
    """从 LLM 返回的文本中提取 JSON 对象"""
    start = text.find("{")
    if start < 0:
        raise ValueError("LLM response does not contain a JSON object")

    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    raise ValueError("Cannot find complete JSON object in LLM response")


def _parse_llm_json(content: str) -> Dict[str, Any]:
    """解析 LLM 返回的 JSON"""
    normalized = (content or "").strip()
    if not normalized:
        raise ValueError("Empty LLM response")

    if normalized.startswith("```"):
        lines = normalized.splitlines()
        if len(lines) >= 2:
            if lines[-1].strip().startswith("```"):
                normalized = "\n".join(lines[1:-1]).strip()
            else:
                normalized = "\n".join(lines[1:]).strip()

    try:
        parsed = json.loads(normalized)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    extracted = _extract_json_object(normalized)
    parsed = json.loads(extracted)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON root must be an object")
    return parsed


async def suggest_field_mapping(columns: List[str], sample_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    使用 LLM 智能推荐字段映射

    Args:
        columns: 用户 Excel 的列名列表
        sample_data: 前几行样本数据

    Returns:
        包含 mappings, confidence, unmapped, missing_required 等信息的字典
    """
    config = _load_field_config()
    standard_fields = config.get("standard_fields", []) or []

    # 构建标准字段描述
    field_definitions = []
    for field in standard_fields:
        key = str(field.get("key", ""))
        name = str(field.get("name", ""))
        aliases = field.get("aliases", []) or []
        aliases_preview = "、".join(map(str, aliases[:5]))
        field_definitions.append(f"- {key}: {name}（{aliases_preview}）")

    # 构建样本预览
    sample_preview = []
    for row in (sample_data or [])[:3]:
        row_preview = {}
        for col in columns:
            value = str((row or {}).get(col, ""))
            row_preview[col] = value[:50] + ("..." if len(value) > 50 else "")
        sample_preview.append(row_preview)

    system_prompt = (
        "你是医疗数据字段映射助手。"
        "请根据列名与样例，将用户字段映射到标准字段 key。"
        "仅返回 JSON，不要返回 markdown。"
    )
    user_prompt = (
        f"标准字段:\n{chr(10).join(field_definitions)}\n\n"
        f"用户列名: {json.dumps(columns, ensure_ascii=False)}\n\n"
        f"样例数据: {json.dumps(sample_preview, ensure_ascii=False)}\n\n"
        "返回格式: "
        '{"mappings":{"列名":"field_key"},"confidence":0.0~1.0,"reasoning":"..."}'
    )

    try:
        # 清除代理设置避免干扰
        for key in ["ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "http_proxy", "https_proxy"]:
            os.environ.pop(key, None)

        model = _get_field_mapper_model()
        base_url = _get_dashscope_base_url()
        client = OpenAI(
            api_key=_get_dashscope_api_key(),
            base_url=base_url,
            timeout=45.0,
            max_retries=0,
        )
        def _request_sync() -> Dict[str, Any]:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=1200,
            )
            observed_result: Dict[str, Any] = {"response": response}
            usage = _sdk_usage_payload(response)
            if usage is not None:
                observed_result["usage"] = usage
            return observed_result

        async def _request() -> Dict[str, Any]:
            return await run_shared_http_call(_request_sync)

        logical_call_id = str(uuid4())
        observed_result: Dict[str, Any] | None = None
        for attempt_no in range(1, 4):
            try:
                observed_result = await observe_llm_http_attempt(
                    _request,
                    provider_code=_field_mapper_provider_code(base_url),
                    model=model,
                    business_scene="smart_upload_field_mapping",
                    executor_key="field_mapper",
                    logical_call_id=logical_call_id,
                    attempt_no=attempt_no,
                )
                break
            except Exception as error:
                _, safe_error_kind = safe_status_for_exception(error)
                if attempt_no >= 3 or safe_error_kind not in {
                    "timeout",
                    "http_transport",
                    "upstream_429",
                    "upstream_5xx",
                }:
                    raise
                await asyncio.sleep(0.25 * (2 ** (attempt_no - 1)))
        if observed_result is None:
            raise RuntimeError("field_mapping_llm_no_result")
        response = observed_result["response"]

        content = (response.choices[0].message.content or "").strip()
        result = _parse_llm_json(content)

        # 过滤有效映射
        raw_mappings = result.get("mappings", {})
        mappings: Dict[str, str] = {}
        if isinstance(raw_mappings, dict):
            for src_col, target_field in raw_mappings.items():
                src = str(src_col).strip()
                target = str(target_field).strip()
                if src in columns and target in STANDARD_FIELDS:
                    mappings[src] = target

        try:
            confidence = float(result.get("confidence", 0.85))
        except Exception:
            confidence = 0.85
        confidence = max(0.0, min(1.0, confidence))

        mapped_cols = set(mappings.keys())
        unmapped = [col for col in columns if col not in mapped_cols]

        mapped_fields = set(mappings.values())
        missing_required = [
            field_key
            for field_key, field_info in STANDARD_FIELDS.items()
            if field_info.get("required") and field_key not in mapped_fields
        ]

        return {
            "mappings": mappings,
            "confidence": confidence,
            "unmapped": unmapped,
            "missing_required": missing_required,
            "standard_fields": STANDARD_FIELDS,
            "fallback": False,
        }
    except Exception as exc:
        _, safe_error_kind = safe_status_for_exception(exc)
        logger.warning(
            "field_mapping_llm_failed fallback=rule_based error_kind=%s error_type=%s",
            safe_error_kind,
            type(exc).__name__,
        )
        return _fallback_mapping(columns, reason=safe_error_kind)


def _fallback_mapping(columns: List[str], reason: str | None = None) -> Dict[str, Any]:
    """规则引擎回退：当 LLM 不可用时使用别名匹配"""
    alias_map = build_alias_map()
    mappings: Dict[str, str] = {}
    used_fields = set()

    for col in columns:
        col_norm = str(col).strip().lower()

        # 精确匹配
        if col_norm in alias_map and alias_map[col_norm] not in used_fields:
            mappings[col] = alias_map[col_norm]
            used_fields.add(alias_map[col_norm])
            continue

        # 模糊匹配
        for alias, field_key in alias_map.items():
            if field_key in used_fields:
                continue
            if alias in col_norm or col_norm in alias:
                mappings[col] = field_key
                used_fields.add(field_key)
                break

    mapped_cols = set(mappings.keys())
    unmapped = [col for col in columns if col not in mapped_cols]
    mapped_fields = set(mappings.values())
    missing_required = [
        field_key
        for field_key, field_info in STANDARD_FIELDS.items()
        if field_info.get("required") and field_key not in mapped_fields
    ]

    return {
        "mappings": mappings,
        "confidence": 0.6,
        "unmapped": unmapped,
        "missing_required": missing_required,
        "standard_fields": STANDARD_FIELDS,
        "fallback": True,
        "fallback_reason": reason or "",
    }


def apply_mapping(df, mappings: Dict[str, str]):
    """应用字段映射，将用户列名重命名为标准字段名"""
    reverse_map = {v: k for k, v in (mappings or {}).items()}
    rename_map: Dict[str, str] = {}
    for std_field, user_col in reverse_map.items():
        if user_col in df.columns and std_field in STANDARD_FIELDS:
            rename_map[user_col] = STANDARD_FIELDS[std_field]["name"]
    return df.rename(columns=rename_map)
