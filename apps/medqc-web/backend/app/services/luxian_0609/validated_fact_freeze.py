"""复用现有事实存储，为剩余两条抽取绑定材料、协议及实际模型配置。"""

import hashlib
import json
import logging
from dataclasses import fields, is_dataclass
from collections.abc import Mapping

from .exam_analysis_freeze import load_payload, save_payload
from . import exam_analysis_freeze
from .rule_decision_settings import _luxian_0609_model_identity


logger = logging.getLogger(__name__)


def _material_value(value):
    # 证据行是MappingProxyType，不能用asdict的deepcopy路径。
    if is_dataclass(value):
        return {field.name: _material_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _material_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_material_value(item) for item in value]
    return value


def fact_freeze_key(*, protocol, prompt, client, materials, scope=None):
    seen = set()
    while client is not None and id(client) not in seen:
        seen.add(id(client))
        try:
            identity = _luxian_0609_model_identity(client)
            break
        except ValueError:
            attributes = getattr(client, "__dict__", {})
            client = attributes.get("delegate") or attributes.get("_inner")
    else:
        # 未知配置不能共享其他模型或测试替身的应答。
        return None
    data = {"version": "validated-facts-v1", "storage_schema": exam_analysis_freeze.FREEZE_SCHEMA_VERSION,
            "protocol": protocol, "prompt": prompt,
            "model": identity, "materials": _material_value(materials), "scope": scope}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, default=str, allow_nan=False).encode()).hexdigest()


def load_facts(namespace, key):
    return load_payload(namespace, key) if key is not None else None


def save_facts(namespace, key, payload):
    from ..llm_token_budget import context_budget_failed
    if context_budget_failed():
        return
    if key is not None:
        try:
            save_payload(namespace, key, payload)
        except OSError:
            # 无写权限不改变已经形成的临床结论，只失去跨运行复用。
            logger.warning("validated_fact_freeze_unwritable namespace=%s", namespace)
