from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional

from .llm_experiment import current_llm_experiment_namespace


@dataclass
class _CacheEntry:
    value: dict[str, Any]
    expires_at: float


def build_record_snapshot_hash(medical_record: dict[str, Any]) -> str:
    payload = {
        "id": str(medical_record.get("id") or ""),
        "document_type": str(medical_record.get("document_type") or ""),
        "content": str(medical_record.get("content") or ""),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_prompt_hash(rule: dict[str, Any]) -> str:
    prompt_text = str(rule.get("custom_prompt") or "")
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


def build_execution_cache_key(
    *,
    record_snapshot_hash: str,
    rule_id: str,
    rule_version: str,
    prompt_hash: str,
    model_version: str,
) -> str:
    key = "|".join(
        [
            str(record_snapshot_hash or ""),
            str(rule_id or ""),
            str(rule_version or ""),
            str(prompt_hash or ""),
            str(model_version or ""),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


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
