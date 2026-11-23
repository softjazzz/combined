from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from threading import Lock
from typing import Any, Optional

from .llm_experiment import current_llm_experiment_namespace


@dataclass
class _CacheEntry:
    value: dict[str, Any]
    expires_at: float


def _norm_scope_field(value: Any) -> str:
    return str(value or "").strip()


def _canonicalize_cache_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else {"__non_finite_float__": str(value)}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return {"__bytes_sha256__": hashlib.sha256(bytes(value)).hexdigest()}
    if isinstance(value, Mapping):
        return {
            str(k): _canonicalize_cache_value(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize_cache_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        canonical_items = [_canonicalize_cache_value(item) for item in value]
        return sorted(
            canonical_items,
            key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonicalize_cache_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _canonicalize_cache_value(to_dict())
    raise TypeError(f"Unsupported cache snapshot value type: {type(value).__name__}")


def build_record_snapshot_hash(medical_record: dict[str, Any]) -> str:
    raw_evidence_payload = medical_record.get("evidence_payload")
    raw_sampling_params = medical_record.get("llm_sampling_params")
    try:
        canonical_evidence_payload = (
            _canonicalize_cache_value(raw_evidence_payload)
            if raw_evidence_payload is not None
            else {}
        )
        canonical_sampling_params = (
            _canonicalize_cache_value(raw_sampling_params)
            if raw_sampling_params is not None
            else {}
        )
        payload = {
            "id": str(medical_record.get("id") or ""),
            "document_type": str(medical_record.get("document_type") or ""),
            "content": str(medical_record.get("content") or ""),
            "institute_id": _norm_scope_field(
                medical_record.get("institute_id") or medical_record.get("source_institute_id")
            ),
            "patient_id": _norm_scope_field(
                medical_record.get("patient_id") or medical_record.get("source_patient_id")
            ),
            "visit_id": _norm_scope_field(
                medical_record.get("visit_id") or medical_record.get("source_visit_id")
            ),
            "source_schema": _norm_scope_field(medical_record.get("source_schema")),
            "evidence_payload": canonical_evidence_payload,
            "llm_sampling_params": canonical_sampling_params,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError:
        # Fail closed when an unserializable runtime object is attached to the record:
        # empty snapshot hash disables cache lookup/write instead of risking key collisions.
        return ""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_prompt_hash(rule: dict[str, Any]) -> str:
    applicable_documents = rule.get("applicable_documents") or []
    try:
        canonical_docs = _canonicalize_cache_value(applicable_documents)
    except TypeError:
        canonical_docs = [str(item) for item in applicable_documents] if isinstance(applicable_documents, (list, tuple)) else str(applicable_documents)
    payload = {
        "custom_prompt": str(rule.get("custom_prompt") or ""),
        "prompt_template": str(rule.get("prompt_template") or ""),
        "name": str(rule.get("name") or rule.get("rule_name") or ""),
        "description": str(rule.get("description") or ""),
        "defect_level": str(rule.get("defect_level") or ""),
        "rule_family": str(rule.get("rule_family") or ""),
        "applicable_documents": canonical_docs,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_execution_cache_key(
    *,
    record_snapshot_hash: str,
    rule_id: str,
    rule_version: str,
    prompt_hash: str,
    model_version: str,
    prompt_version: str = "",
    evidence_source: str = "",
    prompt_strategy: str = "",
    quality_profile: str = "",
    batch_output_mode: str = "",
    bucket_strategy: str = "",
) -> str:
    if not str(record_snapshot_hash or "").strip():
        return ""
    payload = {
        "record_snapshot_hash": str(record_snapshot_hash or ""),
        "rule_id": str(rule_id or ""),
        "rule_version": str(rule_version or ""),
        "prompt_hash": str(prompt_hash or ""),
        "model_version": str(model_version or ""),
        "prompt_version": str(prompt_version or ""),
        "evidence_source": str(evidence_source or ""),
        "prompt_strategy": str(prompt_strategy or ""),
        "quality_profile": str(quality_profile or ""),
        "batch_output_mode": str(batch_output_mode or ""),
        "bucket_strategy": str(bucket_strategy or ""),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class QCExecutionCache:
    def __init__(self, default_ttl_seconds: int = 1800) -> None:
        self._default_ttl_seconds = max(60, int(default_ttl_seconds))
        self._entries: dict[str | tuple[str, str], _CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[dict[str, Any]]:
        if not key:
            return None
        namespace = current_llm_experiment_namespace()
        storage_key = (namespace, key) if namespace is not None else key
        now = time.time()
        with self._lock:
            entry = self._entries.get(storage_key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._entries.pop(storage_key, None)
                return None
            return copy.deepcopy(entry.value)

    def set(self, key: str, value: dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        if not key:
            return
        namespace = current_llm_experiment_namespace()
        storage_key = (namespace, key) if namespace is not None else key
        ttl = max(60, int(ttl_seconds or self._default_ttl_seconds))
        with self._lock:
            self._entries[storage_key] = _CacheEntry(
                value=copy.deepcopy(value),
                expires_at=time.time() + ttl,
            )

    def clear(self) -> None:
        namespace = current_llm_experiment_namespace()
        with self._lock:
            for key in list(self._entries):
                is_baseline = namespace is None and isinstance(key, str)
                is_experiment = isinstance(key, tuple) and key[0] == namespace
                if is_baseline or is_experiment:
                    self._entries.pop(key, None)
