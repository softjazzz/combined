from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from typing import Any, Iterable

from app.core.settings import get_settings
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.luxian_0609 import build_family_scopes, load_luxian_0609_rules
from app.services.luxian_0609_fact_extraction import (
    evaluate_luxian_0609_gates_from_facts,
    extract_luxian_0609_unified_fact_table,
    render_luxian_0609_fact_context,
)
from app.services.luxian_0609_trigger_gate import (
    TRIGGER_ABSENT,
    TRIGGER_DATA_GAP,
    TRIGGER_PRESENT,
    TRIGGER_UNKNOWN,
)
from app.services.medical_records.detail_service import get_documents
from app.services.qc_llm_client import SichuanQCLLMClient


DEFAULT_FULL_TEXT_JOB_ID = "d1bb5cf9-d78d-4bcb-932a-96657fa3bd64"
DEFAULT_MODEL = "qwen3-next-80b-a3b-instruct"
DEFAULT_FAMILIES = ("surgery_anesthesia", "tumor_pathology")
DEFAULT_SELECTED_RULE_IDS = (
    "LX0609-04-02-01",
    "LX0609-04-02-03",
    "LX0609-04-02-04",
    "LX0609-05-01-01",
    "LX0609-04-01-01",
    "LX0609-04-02-02",
    "LX0609-04-02-05",
    "LX0609-04-03-01",
    "LX0609-11-01-01",
    "LX0609-11-02-01",
    "LX0609-11-02-02",
    "LX0609-04-04-01",
    "LX0609-04-04-02",
    "LX0609-04-04-03",
    "LX0609-04-01-02",
    "LX0609-04-01-03",
    "LX0609-06-02-03",
    "LX0609-06-02-02",
    "LX0609-05-02-01",
    "LX0609-08-01-04",
)
DEFAULT_RECORD_IDS = (
    "1870471",
    "1874568",
    "1872902",
    "1876706",
    "2137894",
    "1883111",
    "1880557",
    "1430048",
    "1880757",
    "1878110",
)

B2_FINAL_STATUSES = {
    "non_compliant",
    "compliant",
    "data_gap",
    "not_applicable",
    "ai_suggested_non_compliant",
    "ai_suggested_compliant",
    "technical_error",
}

TELEMETRY_SCHEMA_VERSION = "lx0609.llm-call-ledger.v1"
TELEMETRY_STAGES = ("fact_extraction", "semantic_evaluation", "fallback")
_FACT_FAMILY_PROMPT_MARKERS = {
    "basic_timeliness": "基础时限",
    "course_quality": "查房病程",
    "exam_lab": "检查检验",
    "consultation_quality": "会诊质量",
    "surgery_anesthesia": "手术麻醉",
    "transfusion": "输血",
    "tumor_pathology": "肿瘤病理",
}
_FILTER_REPLAY_KEYS = {
    "b2_limit",
    "customer_rule_count",
    "execution_rule_count",
    "families",
    "family_key",
    "gate_only_customer_rule_ids",
    "max_parallel_records",
    "parallel_records",
    "record_ids",
    "record_rule_map",
    "rule_ids",
    "rule_set_key",
    "rule_set_version",
    "scoped_customer_rule_ids",
    "selected_draft_ids",
    "selected_record_ids",
    "selected_rule_ids",
    "source",
    "validation_mode",
}
_SENSITIVE_REPORT_KEYS = {
    "address",
    "apikey",
    "authorization",
    "idcard",
    "mobile",
    "name",
    "patientname",
    "phone",
    "身份证",
    "患者姓名",
}
_ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_AUTHORIZATION_PATTERN = re.compile(r"(?i)authorization\s*:\s*bearer\s+[^\s,;]+")
_API_KEY_PATTERN = re.compile(r"(?i)(api[_ -]?key\s*[:=]\s*)[^\s,;]+")


class FullTextJobPayload(dict[str, Any]):
    """Dict-compatible payload with in-memory-only report redaction terms."""

    redaction_terms_by_record: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class LLMCallContext:
    stage: str
    record_id: str
    family_key: str
    rule_ids: tuple[str, ...]
    rule_ids_by_family: tuple[tuple[str, tuple[str, ...]], ...] = ()


_LLM_CALL_CONTEXT: ContextVar[LLMCallContext | None] = ContextVar(
    "lx0609_ab_llm_call_context",
    default=None,
)


@contextmanager
def llm_call_context(
    *,
    stage: str,
    record_id: str,
    family_key: str,
    rule_ids: Iterable[str],
    rule_ids_by_family: dict[str, Iterable[str]] | None = None,
):
    if stage not in TELEMETRY_STAGES:
        raise ValueError(f"unsupported telemetry stage: {stage}")
    family_items = tuple(
        (str(key), tuple(sorted({str(rule_id).upper() for rule_id in value})))
        for key, value in sorted((rule_ids_by_family or {}).items())
    )
    token = _LLM_CALL_CONTEXT.set(
        LLMCallContext(
            stage=stage,
            record_id=str(record_id),
            family_key=str(family_key),
            rule_ids=tuple(sorted({str(rule_id).upper() for rule_id in rule_ids})),
            rule_ids_by_family=family_items,
        )
    )
    try:
        yield
    finally:
        _LLM_CALL_CONTEXT.reset(token)


def _fact_family_from_prompt(prompt: str) -> str:
    for family_key, marker in _FACT_FAMILY_PROMPT_MARKERS.items():
        if f"“{marker}”" in prompt or f'"{marker}"' in prompt:
            return family_key
    return ""


def _usage_breakdown(response: dict[str, Any] | None) -> tuple[int, int, int, int, str]:
    payload = dict(response or {})
    usage = payload.get("_usage_breakdown")
    if not isinstance(usage, dict):
        usage = payload.get("usage")
    usage = dict(usage or {})
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    reported_total = int(usage.get("total_tokens") or usage.get("total") or 0)
    total_tokens = reported_total or (input_tokens + output_tokens)
    usage_error = ""
    if total_tokens < input_tokens + output_tokens:
        usage_error = "reported_total_less_than_components"
        total_tokens = input_tokens + output_tokens
    unattributed_tokens = total_tokens - input_tokens - output_tokens
    return input_tokens, output_tokens, total_tokens, unattributed_tokens, usage_error


def _safe_error_code(exc: Exception) -> str:
    raw = str(getattr(exc, "code", None) or getattr(exc, "status_code", None) or "")
    return "".join(character for character in raw if character.isalnum() or character in "._-")[:80]


def _entry_summary(entries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(entries)
    return {
        "call_count": len(items),
        "success_count": sum(1 for item in items if item.get("success") is True),
        "error_count": sum(1 for item in items if item.get("success") is False),
        "input_tokens": sum(int(item.get("input_tokens") or 0) for item in items),
        "output_tokens": sum(int(item.get("output_tokens") or 0) for item in items),
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in items),
        "unattributed_tokens": sum(int(item.get("unattributed_tokens") or 0) for item in items),
        "elapsed_sec": round(sum(float(item.get("elapsed_sec") or 0) for item in items), 4),
    }


class LLMCallLedger:
    def __init__(self, *, model: str, run_id: str | None = None) -> None:
        self.model = str(model)
        self.run_id = run_id or hashlib.sha256(
            f"{self.model}:{time.time_ns()}".encode("utf-8")
        ).hexdigest()[:12]
        self._lock = threading.Lock()
        self._sequence = 0
        self._entries: list[dict[str, Any]] = []

    def allocate_call_id(self) -> str:
        with self._lock:
            self._sequence += 1
            return f"{self.run_id}-call-{self._sequence:06d}"

    def append(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._entries.append(dict(entry))

    def entries(
        self,
        *,
        stage: str | None = None,
        record_id: str | None = None,
        rule_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            items = [dict(item) for item in self._entries]
        if stage is not None:
            items = [item for item in items if item.get("stage") == stage]
        if record_id is not None:
            items = [item for item in items if item.get("record_id") == str(record_id)]
        if rule_id is not None:
            normalized = str(rule_id).upper()
            items = [item for item in items if normalized in list(item.get("rule_ids") or [])]
        return sorted(items, key=lambda item: str(item.get("call_id") or ""))

    def summary(
        self,
        *,
        stage: str | None = None,
        record_id: str | None = None,
        rule_id: str | None = None,
    ) -> dict[str, Any]:
        return _entry_summary(self.entries(stage=stage, record_id=record_id, rule_id=rule_id))

    def build_telemetry(self, *, client: Any | None = None) -> dict[str, Any]:
        entries = self.entries()
        stage_summary = {
            stage: _entry_summary(item for item in entries if item.get("stage") == stage)
            for stage in TELEMETRY_STAGES
        }
        extra_stages = sorted({str(item.get("stage") or "") for item in entries} - set(TELEMETRY_STAGES))
        for stage in extra_stages:
            stage_summary[stage] = _entry_summary(item for item in entries if item.get("stage") == stage)
        total = _entry_summary(entries)
        invariant_errors: list[str] = []
        if total["call_count"] != sum(item["call_count"] for item in stage_summary.values()):
            invariant_errors.append("ledger_call_count_does_not_equal_stage_call_count")
        for entry in entries:
            if int(entry.get("total_tokens") or 0) != (
                int(entry.get("input_tokens") or 0)
                + int(entry.get("output_tokens") or 0)
                + int(entry.get("unattributed_tokens") or 0)
            ):
                invariant_errors.append(f"call_token_equation_failed:{entry.get('call_id')}")
            if entry.get("usage_invariant_error"):
                invariant_errors.append(
                    f"usage_breakdown_invalid:{entry.get('call_id')}:{entry.get('usage_invariant_error')}"
                )
            if entry.get("capture_success") is False:
                invariant_errors.append(
                    f"telemetry_capture_failed:{entry.get('call_id')}:{entry.get('failure_phase')}"
                )
            if entry.get("telemetry_context_missing"):
                invariant_errors.append(f"telemetry_context_missing:{entry.get('call_id')}")
        if total["total_tokens"] != (
            total["input_tokens"] + total["output_tokens"] + total["unattributed_tokens"]
        ):
            invariant_errors.append("ledger_total_token_equation_failed")

        client_observation: dict[str, Any] = {"available": False}
        if client is not None and all(
            hasattr(client, name)
            for name in ("call_count", "success_count", "error_count", "total_tokens")
        ):
            client_observation = {
                "available": True,
                "call_count": int(client.call_count),
                "success_count": int(client.success_count),
                "error_count": int(client.error_count),
                "total_tokens": int(client.total_tokens),
            }
            expected = {
                "call_count": total["call_count"],
                "success_count": total["success_count"],
                "error_count": total["error_count"],
                "total_tokens": total["total_tokens"],
            }
            for key, value in expected.items():
                if client_observation[key] != value:
                    invariant_errors.append(
                        f"client_{key}_mismatch:client={client_observation[key]},ledger={value}"
                    )

        return {
            "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
            "run_id": self.run_id,
            "llm_call_ledger": entries,
            "stage_summary": stage_summary,
            "llm_call_count": total["call_count"],
            "llm_success_count": total["success_count"],
            "llm_error_count": total["error_count"],
            "input_tokens": total["input_tokens"],
            "output_tokens": total["output_tokens"],
            "total_tokens": total["total_tokens"],
            "unattributed_tokens": total["unattributed_tokens"],
            "llm_total_elapsed_sec": total["elapsed_sec"],
            "client_observation": client_observation,
            "telemetry_invariant_ok": not invariant_errors,
            "telemetry_invariant_error": invariant_errors,
        }


class LedgeredLLMClient:
    def __init__(self, client: Any, *, ledger: LLMCallLedger) -> None:
        self._client = client
        self.ledger = ledger

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    async def generate(self, prompt: str) -> dict[str, Any]:
        context = _LLM_CALL_CONTEXT.get()
        call_id = self.ledger.allocate_call_id()
        started = time.perf_counter()
        resolved_family = context.family_key if context else ""
        resolved_rule_ids = list(context.rule_ids if context else ())
        if context and context.stage == "fact_extraction":
            inferred_family = _fact_family_from_prompt(prompt)
            if inferred_family:
                resolved_family = inferred_family
                family_map = dict(context.rule_ids_by_family)
                resolved_rule_ids = list(family_map.get(inferred_family) or context.rule_ids)
        base_entry = {
            "call_id": call_id,
            "stage": context.stage if context else "unattributed",
            "record_id": context.record_id if context else "",
            "family_key": resolved_family,
            "rule_ids": sorted(set(resolved_rule_ids)),
            "model": str(getattr(self._client, "model", None) or self.ledger.model),
            "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "cache_hit": None,
            "cache_observation": "unavailable",
            "telemetry_context_missing": context is None,
        }
        failure_phase = "upstream_generate"
        upstream_success = False
        try:
            raw_response = await self._client.generate(prompt)
            upstream_success = True
            failure_phase = "response_normalization"
            response = dict(raw_response or {})
            failure_phase = "usage_parse"
            input_tokens, output_tokens, total_tokens, unattributed_tokens, usage_error = _usage_breakdown(
                response
            )
        except Exception as exc:
            self.ledger.append(
                {
                    **base_entry,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "unattributed_tokens": 0,
                    "elapsed_sec": round(time.perf_counter() - started, 4),
                    "success": upstream_success,
                    "capture_success": not upstream_success,
                    "failure_phase": failure_phase,
                    "error_type": type(exc).__name__ if not upstream_success else "",
                    "error_code": _safe_error_code(exc) if not upstream_success else "",
                    "capture_error_type": type(exc).__name__ if upstream_success else "",
                    "capture_error_code": _safe_error_code(exc) if upstream_success else "",
                    "usage_invariant_error": (
                        f"telemetry_capture_failed:{failure_phase}" if upstream_success else ""
                    ),
                }
            )
            raise
        self.ledger.append(
            {
                **base_entry,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "unattributed_tokens": unattributed_tokens,
                "elapsed_sec": round(time.perf_counter() - started, 4),
                "success": True,
                "capture_success": True,
                "failure_phase": "",
                "error_type": "",
                "error_code": "",
                "capture_error_type": "",
                "capture_error_code": "",
                "usage_invariant_error": usage_error,
            }
        )
        response["_telemetry_call_id"] = call_id
        return response


def _telemetry_aliases(telemetry: dict[str, Any]) -> dict[str, Any]:
    return {
        "telemetry_schema_version": telemetry["telemetry_schema_version"],
        "llm_call_count": telemetry["llm_call_count"],
        "llm_success_count": telemetry["llm_success_count"],
        "llm_error_count": telemetry["llm_error_count"],
        "llm_total_tokens": telemetry["total_tokens"],
        "llm_total_elapsed_sec": telemetry["llm_total_elapsed_sec"],
        "unattributed_tokens": telemetry["unattributed_tokens"],
        "telemetry_invariant_error": telemetry["telemetry_invariant_error"],
        "telemetry": telemetry,
    }


def _telemetry_slice(telemetry: dict[str, Any], *, stages: Iterable[str]) -> dict[str, Any]:
    selected_stages = set(stages)
    entries = [
        dict(entry)
        for entry in list(telemetry.get("llm_call_ledger") or [])
        if str(entry.get("stage") or "") in selected_stages
    ]
    stage_summary = {
        stage: _entry_summary(entry for entry in entries if entry.get("stage") == stage)
        for stage in TELEMETRY_STAGES
    }
    total = _entry_summary(entries)
    errors: list[str] = []
    for entry in entries:
        if int(entry.get("total_tokens") or 0) != (
            int(entry.get("input_tokens") or 0)
            + int(entry.get("output_tokens") or 0)
            + int(entry.get("unattributed_tokens") or 0)
        ):
            errors.append(f"call_token_equation_failed:{entry.get('call_id')}")
        if entry.get("usage_invariant_error"):
            errors.append(
                f"usage_breakdown_invalid:{entry.get('call_id')}:{entry.get('usage_invariant_error')}"
            )
        if entry.get("capture_success") is False:
            errors.append(
                f"telemetry_capture_failed:{entry.get('call_id')}:{entry.get('failure_phase')}"
            )
        if entry.get("telemetry_context_missing"):
            errors.append(f"telemetry_context_missing:{entry.get('call_id')}")
    return {
        "telemetry_schema_version": str(telemetry.get("telemetry_schema_version") or TELEMETRY_SCHEMA_VERSION),
        "run_id": str(telemetry.get("run_id") or ""),
        "llm_call_ledger": entries,
        "stage_summary": stage_summary,
        "llm_call_count": total["call_count"],
        "llm_success_count": total["success_count"],
        "llm_error_count": total["error_count"],
        "input_tokens": total["input_tokens"],
        "output_tokens": total["output_tokens"],
        "total_tokens": total["total_tokens"],
        "unattributed_tokens": total["unattributed_tokens"],
        "llm_total_elapsed_sec": total["elapsed_sec"],
        "client_observation": {"available": False, "reason": "stage_slice"},
        "telemetry_invariant_ok": not errors,
        "telemetry_invariant_error": errors,
    }


def _llm_client(model: str) -> SichuanQCLLMClient:
    settings = get_settings()
    endpoint = str(settings.DASHSCOPE_BASE_URL or settings.LLM_API_ENDPOINT or "").rstrip("/")
    api_key = settings.DASHSCOPE_API_KEY or settings.LLM_API_KEY
    return SichuanQCLLMClient(
        {
            "api_endpoint": endpoint,
            "api_key": api_key,
            "model": model,
            "timeout_seconds": 120,
            "source": "tmp_lx0609_fact_gate_ab",
            "custom_parameters": {
                "temperature": 0.0,
                "top_p": 0.8,
                "max_tokens": 4096,
                "enable_thinking": False,
            },
        }
    )


def _flatten_batch_items(job: dict[str, Any]) -> list[dict[str, Any]]:
    items = [item for item in list(job.get("items") or []) if isinstance(item, dict)]
    for child_key in ("children", "child_jobs"):
        for child in job.get(child_key) or []:
            if isinstance(child, dict):
                items.extend(_flatten_batch_items(child))
    return items


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _rule_id(item: dict[str, Any]) -> str:
    for key in ("rule_id", "rule_code", "qc_point_id", "customer_rule_id"):
        value = _as_str(item.get(key)).upper()
        if value.startswith("LX0609-"):
            return value
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    for key in ("customer_rule_id", "selected_execution_rule_id"):
        value = _as_str(metadata.get(key)).upper()
        if value.startswith("LX0609-"):
            return value
    return ""


def _record_id(item: dict[str, Any]) -> str:
    return _as_str(item.get("record_id") or item.get("visit_id") or item.get("draft_id"))


def _short_text(value: Any, limit: int = 90) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _normalized_report_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value or "").lower())


def _is_sensitive_report_key(value: Any) -> bool:
    return _normalized_report_key(value) in _SENSITIVE_REPORT_KEYS


def _redact_report_text(value: Any, *, redaction_terms: Iterable[str] = ()) -> str:
    text = str(value or "")
    terms = sorted(
        {str(term) for term in redaction_terms if str(term)},
        key=len,
        reverse=True,
    )
    for term in terms:
        text = text.replace(term, "[REDACTED]")
    text = _ID_CARD_PATTERN.sub("[REDACTED_ID]", text)
    text = _PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    text = _AUTHORIZATION_PATTERN.sub("[REDACTED_CREDENTIAL]", text)
    text = _API_KEY_PATTERN.sub(r"\1[REDACTED_CREDENTIAL]", text)
    return text


def _redacted_short_text(value: Any, *, patient_name: str = "", limit: int = 90) -> str:
    return _short_text(
        _redact_report_text(value, redaction_terms=[patient_name] if patient_name else []),
        limit,
    )


def sanitize_report_payload(
    value: Any,
    *,
    redaction_terms_by_record: dict[str, Iterable[str]] | None = None,
) -> Any:
    term_map = {
        str(record_id): tuple(str(term) for term in terms if str(term))
        for record_id, terms in (redaction_terms_by_record or {}).items()
    }

    def sanitize(item: Any, *, record_id: str = "") -> Any:
        if isinstance(item, dict):
            local_record_id = record_id
            for key in ("record_id", "visit_id", "draft_id"):
                candidate = item.get(key)
                if candidate is not None and str(candidate):
                    local_record_id = str(candidate)
                    break
            sanitized: dict[Any, Any] = {}
            for key, nested in item.items():
                if _is_sensitive_report_key(key):
                    continue
                if isinstance(key, tuple):
                    sanitized_key = "::".join(str(part) for part in key)
                elif isinstance(key, str):
                    sanitized_key = _redact_report_text(
                        key,
                        redaction_terms=term_map.get(local_record_id, ()),
                    )
                else:
                    sanitized_key = key
                sanitized[sanitized_key] = sanitize(nested, record_id=local_record_id)
            return sanitized
        if isinstance(item, list):
            return [sanitize(nested, record_id=record_id) for nested in item]
        if isinstance(item, tuple):
            return tuple(sanitize(nested, record_id=record_id) for nested in item)
        if isinstance(item, str):
            return _redact_report_text(item, redaction_terms=term_map.get(record_id, ()))
        return item

    return sanitize(value)


def _sanitize_replay_filters(filters: dict[str, Any]) -> dict[str, Any]:
    whitelisted = {
        str(key): value
        for key, value in filters.items()
        if str(key) in _FILTER_REPLAY_KEYS
    }
    return sanitize_report_payload(whitelisted)


def _extract_llm_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def _parse_json_object(text: str) -> dict[str, Any] | None:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        cleaned = cleaned.removesuffix("```").strip()
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_b2_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "不合规": "non_compliant",
        "确定问题": "non_compliant",
        "合规": "compliant",
        "无问题": "compliant",
        "数据不足": "data_gap",
        "资料不足": "data_gap",
        "不适用": "not_applicable",
        "无需质控": "not_applicable",
        "ai判断不合规": "ai_suggested_non_compliant",
        "ai建议不合规": "ai_suggested_non_compliant",
        "ai判断合规": "ai_suggested_compliant",
        "ai建议合规": "ai_suggested_compliant",
    }
    normalized = aliases.get(text, text)
    if normalized == "uncertain":
        return "ai_suggested_non_compliant"
    if normalized in B2_FINAL_STATUSES:
        return normalized
    return "data_gap"


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _elapsed_between(started: Any, ended: Any) -> float | None:
    start = _parse_dt(started)
    end = _parse_dt(ended)
    if not start or not end:
        return None
    return max(0.0, (end - start).total_seconds())


def _duration_from_item(item: dict[str, Any]) -> float:
    profile = item.get("performance_profile") if isinstance(item.get("performance_profile"), dict) else {}
    for key in ("duration_seconds", "api_time", "first_result_latency_seconds"):
        try:
            value = float(profile.get(key) or 0)
            if value > 0:
                return value
        except Exception:
            pass
    for key in ("api_time", "first_result_latency"):
        try:
            value = float(item.get(key) or 0)
            if value > 0:
                return value
        except Exception:
            pass
    return 0.0


def _tokens_from_item(item: dict[str, Any]) -> int:
    profile = item.get("performance_profile") if isinstance(item.get("performance_profile"), dict) else {}
    for key in ("tokens_total", "total_tokens", "tokens_used"):
        try:
            value = int(profile.get(key) or 0)
            if value > 0:
                return value
        except Exception:
            pass
    for key in ("tokens_used", "prompt_tokens", "completion_tokens"):
        try:
            value = int(item.get(key) or 0)
            if key == "tokens_used" and value > 0:
                return value
        except Exception:
            pass
    return int(item.get("prompt_tokens") or 0) + int(item.get("completion_tokens") or 0)


def load_full_text_job(job_id: str) -> dict[str, Any]:
    service = CustomQCWorkspaceService()
    job = service.get_batch_job_for_processing(job_id=job_id)
    if not job:
        raise RuntimeError(f"full_text job not found: {job_id}")
    items = _flatten_batch_items(job)
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    redaction_terms_by_record: dict[str, set[str]] = defaultdict(set)
    for item in items:
        record_id = _record_id(item)
        rule_id = _rule_id(item)
        if not record_id or not rule_id:
            continue
        patient_name = _as_str(item.get("patient_name"))
        if patient_name:
            redaction_terms_by_record[record_id].add(patient_name)
        rows[(record_id, rule_id)] = {
            "record_id": record_id,
            "rule_id": rule_id,
            "status": _as_str(item.get("status") or "unknown"),
            "rule_name": _as_str(item.get("rule_name")),
            "department": _as_str(item.get("department")),
            "duration_sec": _duration_from_item(item),
            "tokens": _tokens_from_item(item),
            "evidence": _redacted_short_text(item.get("evidence"), patient_name=patient_name, limit=120),
            "conclusion": _redacted_short_text(
                item.get("conclusion") or item.get("source_conclusion"),
                patient_name=patient_name,
                limit=120,
            ),
        }
    summary = job.get("summary") if isinstance(job.get("summary"), dict) else {}
    wall_elapsed = (
        _elapsed_between(job.get("started_at"), job.get("finished_at"))
        or _elapsed_between(job.get("started_at"), job.get("updated_at"))
        or float(job.get("total_processing_time") or 0)
    )
    payload = FullTextJobPayload(
        {
        "job_id": job_id,
        "status": job.get("status"),
        "created_at": str(job.get("created_at") or ""),
        "started_at": str(job.get("started_at") or ""),
        "finished_at": str(job.get("finished_at") or ""),
        "updated_at": str(job.get("updated_at") or ""),
        "wall_elapsed_sec": round(float(wall_elapsed or 0), 2),
        "processing_time_sec": round(float(job.get("total_processing_time") or summary.get("total_processing_time") or 0), 2),
        "total_tokens": int(job.get("total_tokens") or summary.get("total_tokens") or 0),
        "item_count": len(rows),
        "rows": rows,
        "status_counter": dict(Counter(row["status"] for row in rows.values())),
        "filters": _sanitize_replay_filters(
            job.get("filters") if isinstance(job.get("filters"), dict) else {}
        ),
        }
    )
    payload.redaction_terms_by_record = {
        record_id: tuple(sorted(terms, key=len, reverse=True))
        for record_id, terms in redaction_terms_by_record.items()
    }
    return payload


def _documents_for_visit(visit_id: str) -> list[dict[str, Any]]:
    payload = get_documents(visit_id)
    return [document for document in payload.get("documents") or [] if document.get("has_content")]


def _gate_status(status: str) -> str:
    if status == TRIGGER_ABSENT:
        return "not_applicable"
    if status == TRIGGER_DATA_GAP:
        return "data_gap"
    if status == TRIGGER_PRESENT:
        return "needs_full_qc"
    if status == TRIGGER_UNKNOWN:
        return "needs_full_qc"
    return "not_executed"


def _rule_catalog(selected_rule_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    wanted = {str(rule_id).upper() for rule_id in selected_rule_ids}
    catalog: dict[str, dict[str, Any]] = {}
    for rule in load_luxian_0609_rules():
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").upper()
        if rule_id in wanted:
            catalog[rule_id] = rule
    for rule_id in wanted:
        catalog.setdefault(
            rule_id,
            {
                "rule_id": rule_id,
                "name": rule_id,
                "description": rule_id,
                "trigger_condition": "",
                "non_trigger_condition": "",
            },
        )
    return catalog


def _build_b2_trimmed_qc_prompt(
    *,
    visit_id: str,
    rule: dict[str, Any],
    fact_context: str,
    gate_reason: str,
    data_gap_fields: Iterable[str],
) -> str:
    rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").upper()
    rule_name = str(rule.get("name") or rule.get("customer_text") or rule_id)
    description = str(rule.get("description") or rule.get("standardized_rule") or "")
    trigger_condition = str(rule.get("trigger_condition") or "")
    non_trigger_condition = str(rule.get("non_trigger_condition") or "")
    dependencies = "、".join(str(item) for item in rule.get("data_dependencies") or [])
    gaps = "、".join(str(item) for item in data_gap_fields if item) or "-"
    return f"""你是泸县0609医疗质控的 B2 事实表质控器。

任务：只基于“结构化事实摘要”判断一个 LX0609 客户质控点。不要使用病历全文，不要补写事实，不要输出内部调试词。

病历 visit_id：{visit_id}
规则ID：{rule_id}
规则名称：{rule_name}
规则描述：{description}
触发条件：{trigger_condition}
不触发条件：{non_trigger_condition}
依赖数据：{dependencies or "-"}
gate 依据：{gate_reason or "-"}
gate 缺失字段：{gaps}

结构化事实摘要：
{fact_context or "未抽取到相关事实。"}

判定口径：
1. 事实明确证明违反规则，输出 non_compliant。
2. 事实明确证明符合规则，输出 compliant。
3. 缺少完成判定所需字段，输出 data_gap，并写清缺失字段。
4. 没有当前规则适用的强触发事实，输出 not_applicable。
5. 只能做语义建议但证据不足以作为硬规则结论时，输出 ai_suggested_non_compliant 或 ai_suggested_compliant。

必须输出 JSON，不要输出 Markdown：
{{
  "status": "non_compliant|compliant|data_gap|not_applicable|ai_suggested_non_compliant|ai_suggested_compliant",
  "conclusion": "一句客户可读结论",
  "evidence": "最关键事实或来源片段，限 200 字",
  "suggestion": "处理建议，合规或不适用时可为空",
  "missing_fields": ["缺失字段1"],
  "confidence": 0.0
}}
"""


async def _run_b2_trimmed_qc_one(
    *,
    client: LedgeredLLMClient,
    model: str,
    visit_id: str,
    rule: dict[str, Any],
    fact_context: str,
    gate_reason: str,
    data_gap_fields: Iterable[str],
) -> dict[str, Any]:
    started = time.perf_counter()
    prompt = _build_b2_trimmed_qc_prompt(
        visit_id=visit_id,
        rule=rule,
        fact_context=fact_context,
        gate_reason=gate_reason,
        data_gap_fields=data_gap_fields,
    )
    rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").upper()
    before_call_ids = {entry["call_id"] for entry in client.ledger.entries()}
    try:
        with llm_call_context(
            stage="semantic_evaluation",
            record_id=visit_id,
            family_key="single_rule_b2",
            rule_ids=[rule_id],
        ):
            response = await client.generate(prompt)
        parsed = _parse_json_object(_extract_llm_text(response)) or {}
        new_entries = [
            entry for entry in client.ledger.entries() if entry["call_id"] not in before_call_ids
        ]
        entry = new_entries[-1] if new_entries else {}
        status = _normalize_b2_status(parsed.get("status"))
        return {
            "status": status,
            "conclusion": _short_text(parsed.get("conclusion"), 180),
            "evidence": _short_text(parsed.get("evidence"), 220),
            "suggestion": _short_text(parsed.get("suggestion"), 180),
            "missing_fields": list(parsed.get("missing_fields") or []),
            "confidence": parsed.get("confidence"),
            "duration_sec": round(time.perf_counter() - started, 4),
            "tokens": int(entry.get("total_tokens") or 0),
            "api_time_sec": round(float(entry.get("elapsed_sec") or 0), 4),
            "llm_calls": 1 if entry else 0,
            "telemetry_call_id": str(entry.get("call_id") or ""),
            "token_attribution": "unique_call",
            "model": model,
            "parse_ok": bool(parsed),
        }
    except Exception as exc:
        new_entries = [
            entry for entry in client.ledger.entries() if entry["call_id"] not in before_call_ids
        ]
        entry = new_entries[-1] if new_entries else {}
        return {
            "status": "technical_error",
            "conclusion": "B2 事实表质控调用失败。",
            "evidence": type(exc).__name__,
            "suggestion": "请检查模型服务或重试。",
            "missing_fields": [],
            "confidence": 0,
            "duration_sec": round(time.perf_counter() - started, 4),
            "tokens": int(entry.get("total_tokens") or 0),
            "api_time_sec": round(float(entry.get("elapsed_sec") or 0), 4),
            "llm_calls": 1 if entry else 0,
            "telemetry_call_id": str(entry.get("call_id") or ""),
            "token_attribution": "unique_call",
            "model": model,
            "parse_ok": False,
        }


async def run_fact_gate_trimmed(
    *,
    record_ids: Iterable[str],
    selected_rule_ids: Iterable[str],
    families: Iterable[str],
    model: str,
) -> dict[str, Any]:
    raw_client = _llm_client(model)
    ledger = LLMCallLedger(model=model)
    client = LedgeredLLMClient(raw_client, ledger=ledger)
    started = time.perf_counter()
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    rule_ids = [str(rule_id).upper() for rule_id in selected_rule_ids]
    family_keys = [str(family) for family in families]
    rules = [{"rule_id": rule_id, "rule_name": rule_id} for rule_id in rule_ids]
    family_rule_ids = {
        str(scope.get("key") or ""): list(scope.get("rule_ids") or [])
        for scope in build_family_scopes(rule_ids)
    }
    for visit_id in record_ids:
        documents = _documents_for_visit(str(visit_id))
        record_started = time.perf_counter()
        with llm_call_context(
            stage="fact_extraction",
            record_id=str(visit_id),
            family_key="multi_family",
            rule_ids=rule_ids,
            rule_ids_by_family=family_rule_ids,
        ):
            table = await extract_luxian_0609_unified_fact_table(
                documents,
                families=family_keys,
                llm_client=client,
                llm_model=model,
                include_llm=True,
            )
        evaluation = evaluate_luxian_0609_gates_from_facts(
            rules=rules,
            facts=table.facts,
            visit_id=str(visit_id),
            families=family_keys,
        )
        record_elapsed = time.perf_counter() - record_started
        fact_entries = ledger.entries(stage="fact_extraction", record_id=str(visit_id))
        fact_summary = _entry_summary(fact_entries)
        records.append(
            {
                "record_id": str(visit_id),
                "document_count": len(documents),
                "fact_count": len(table.facts),
                "stage_counts": table.stats.get("stage_counts") or {},
                "llm_calls": fact_summary["call_count"],
                "llm_tokens": fact_summary["total_tokens"],
                "llm_api_time_sec": fact_summary["elapsed_sec"],
                "llm_call_ids": [entry["call_id"] for entry in fact_entries],
                "elapsed_sec": round(record_elapsed, 2),
            }
        )
        for rule_id in rule_ids:
            decision = evaluation.decisions.get(rule_id)
            status = _gate_status(decision.status) if decision else "not_executed"
            rows[(str(visit_id), rule_id)] = {
                "record_id": str(visit_id),
                "rule_id": rule_id,
                "status": status,
                "gate_raw_status": decision.status if decision else "",
                "gate_reason": decision.reason if decision else "fact gate did not return decision",
                "data_gap_fields": list(decision.data_gap_fields) if decision else [],
                "matched_keywords": list(decision.matched_keywords) if decision else [],
                "duration_sec": round(record_elapsed, 4),
                "duration_basis": "shared_fact_extraction_per_record",
                "duration_additive": False,
                "tokens": fact_summary["total_tokens"],
                "tokens_additive": False,
                "token_attribution": "shared_fact_extraction_non_additive",
                "shared_call_ids": [entry["call_id"] for entry in fact_entries],
                "fact_count": len(table.facts),
            }
    wall_elapsed = time.perf_counter() - started
    telemetry = ledger.build_telemetry(client=raw_client)
    fact_summary = telemetry["stage_summary"]["fact_extraction"]
    return {
        "mode": "fact_gate_trimmed",
        "model": model,
        "families": family_keys,
        "wall_elapsed_sec": round(wall_elapsed, 2),
        **_telemetry_aliases(telemetry),
        "fact_extraction_llm_call_count": fact_summary["call_count"],
        "fact_extraction_llm_total_tokens": fact_summary["total_tokens"],
        "fact_extraction_llm_elapsed_sec": fact_summary["elapsed_sec"],
        "gate_llm_call_count": fact_summary["call_count"],
        "gate_llm_total_tokens": fact_summary["total_tokens"],
        "gate_llm_elapsed_sec": fact_summary["elapsed_sec"],
        "record_count": len(records),
        "item_count": len(rows),
        "status_counter": dict(Counter(row["status"] for row in rows.values())),
        "records": records,
        "rows": rows,
    }


async def run_fact_gate_plus_trimmed_qc(
    *,
    record_ids: Iterable[str],
    selected_rule_ids: Iterable[str],
    families: Iterable[str],
    model: str,
    b2_limit: int = 0,
) -> dict[str, Any]:
    """Run B1 fact gate, then B2 direct QC only for gate-positive rows.

    This is an experimental path. It does not replace the production LX0609
    executor; it measures whether fact-context QC can approach full_text status
    with lower token/time cost.
    """

    raw_client = _llm_client(model)
    ledger = LLMCallLedger(model=model)
    client = LedgeredLLMClient(raw_client, ledger=ledger)
    started = time.perf_counter()
    gate_rows: dict[tuple[str, str], dict[str, Any]] = {}
    b2_rows: dict[tuple[str, str], dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    rule_ids = [str(rule_id).upper() for rule_id in selected_rule_ids]
    family_keys = [str(family) for family in families]
    rules = [{"rule_id": rule_id, "rule_name": rule_id} for rule_id in rule_ids]
    catalog = _rule_catalog(rule_ids)
    family_rule_ids = {
        str(scope.get("key") or ""): list(scope.get("rule_ids") or [])
        for scope in build_family_scopes(rule_ids)
    }
    b2_calls = 0
    b2_wall_time = 0.0

    for visit_id in record_ids:
        visit_id = str(visit_id)
        documents = _documents_for_visit(visit_id)
        record_started = time.perf_counter()
        with llm_call_context(
            stage="fact_extraction",
            record_id=visit_id,
            family_key="multi_family",
            rule_ids=rule_ids,
            rule_ids_by_family=family_rule_ids,
        ):
            table = await extract_luxian_0609_unified_fact_table(
                documents,
                families=family_keys,
                llm_client=client,
                llm_model=model,
                include_llm=True,
            )
        evaluation = evaluate_luxian_0609_gates_from_facts(
            rules=rules,
            facts=table.facts,
            visit_id=visit_id,
            families=family_keys,
        )
        gate_elapsed = time.perf_counter() - record_started
        fact_context = render_luxian_0609_fact_context(table.facts, families=family_keys)[:12000]
        record_b2_wall = 0.0
        fact_entries = ledger.entries(stage="fact_extraction", record_id=visit_id)
        fact_summary = _entry_summary(fact_entries)

        for rule_id in rule_ids:
            decision = evaluation.decisions.get(rule_id)
            gate_status = _gate_status(decision.status) if decision else "not_executed"
            gate_row = {
                "record_id": visit_id,
                "rule_id": rule_id,
                "status": gate_status,
                "gate_raw_status": decision.status if decision else "",
                "gate_reason": decision.reason if decision else "fact gate did not return decision",
                "data_gap_fields": list(decision.data_gap_fields) if decision else [],
                "matched_keywords": list(decision.matched_keywords) if decision else [],
                "duration_sec": round(gate_elapsed, 4),
                "duration_basis": "shared_fact_extraction_per_record",
                "duration_additive": False,
                "tokens": fact_summary["total_tokens"],
                "tokens_additive": False,
                "token_attribution": "shared_fact_extraction_non_additive",
                "shared_call_ids": [entry["call_id"] for entry in fact_entries],
                "fact_count": len(table.facts),
            }
            gate_rows[(visit_id, rule_id)] = gate_row

            if gate_status in {"not_applicable", "data_gap", "not_executed"}:
                b2_rows[(visit_id, rule_id)] = {
                    **gate_row,
                    "mode": "fact_gate_plus_trimmed_qc",
                    "status": gate_status,
                    "b2_source": "gate_shortcut",
                    "conclusion": gate_row["gate_reason"],
                    "evidence": "; ".join(gate_row["matched_keywords"])[:220],
                    "suggestion": "如需进一步判断，请补齐 gate 缺失字段。" if gate_status == "data_gap" else "",
                    "b2_duration_sec": 0.0,
                    "b2_tokens": 0,
                    "b2_api_time_sec": 0.0,
                }
                continue

            if b2_limit and b2_calls >= b2_limit:
                b2_rows[(visit_id, rule_id)] = {
                    **gate_row,
                    "mode": "fact_gate_plus_trimmed_qc",
                    "status": "b2_skipped",
                    "b2_source": "limit_skipped",
                    "conclusion": "B2 调用达到本次限制，未执行事实表质控。",
                    "evidence": gate_row["gate_reason"],
                    "suggestion": "",
                    "b2_duration_sec": 0.0,
                    "b2_tokens": 0,
                    "b2_api_time_sec": 0.0,
                }
                continue

            b2_result = await _run_b2_trimmed_qc_one(
                client=client,
                model=model,
                visit_id=visit_id,
                rule=catalog[rule_id],
                fact_context=fact_context,
                gate_reason=gate_row["gate_reason"],
                data_gap_fields=gate_row["data_gap_fields"],
            )
            b2_calls = ledger.summary(stage="semantic_evaluation")["call_count"]
            b2_wall_time += float(b2_result.get("duration_sec") or 0)
            record_b2_wall += float(b2_result.get("duration_sec") or 0)
            b2_rows[(visit_id, rule_id)] = {
                **gate_row,
                "mode": "fact_gate_plus_trimmed_qc",
                "status": b2_result["status"],
                "b2_source": "trimmed_llm_qc",
                "conclusion": b2_result["conclusion"],
                "evidence": b2_result["evidence"],
                "suggestion": b2_result["suggestion"],
                "missing_fields": b2_result["missing_fields"],
                "confidence": b2_result["confidence"],
                "parse_ok": b2_result["parse_ok"],
                "b2_duration_sec": b2_result["duration_sec"],
                "b2_tokens": b2_result["tokens"],
                "b2_api_time_sec": b2_result["api_time_sec"],
                "b2_call_id": b2_result["telemetry_call_id"],
                "b2_token_attribution": "unique_call",
                "duration_sec": round(gate_elapsed + float(b2_result["duration_sec"]), 4),
                "duration_additive": False,
                "tokens": int(gate_row["tokens"]) + int(b2_result["tokens"]),
                "tokens_additive": False,
                "token_attribution": "shared_fact_extraction_plus_unique_b2_non_additive",
                "shared_call_ids": [
                    *list(gate_row.get("shared_call_ids") or []),
                    *([b2_result["telemetry_call_id"]] if b2_result["telemetry_call_id"] else []),
                ],
            }

        record_b2_entries = ledger.entries(stage="semantic_evaluation", record_id=visit_id)
        record_b2_summary = _entry_summary(record_b2_entries)
        records.append(
            {
                "record_id": visit_id,
                "document_count": len(documents),
                "fact_count": len(table.facts),
                "stage_counts": table.stats.get("stage_counts") or {},
                "fact_extraction_llm_calls": fact_summary["call_count"],
                "fact_extraction_llm_tokens": fact_summary["total_tokens"],
                "fact_extraction_llm_api_time_sec": fact_summary["elapsed_sec"],
                "fact_extraction_call_ids": [entry["call_id"] for entry in fact_entries],
                "gate_llm_calls": fact_summary["call_count"],
                "gate_llm_tokens": fact_summary["total_tokens"],
                "gate_llm_api_time_sec": fact_summary["elapsed_sec"],
                "gate_elapsed_sec": round(gate_elapsed, 2),
                "b2_llm_calls": record_b2_summary["call_count"],
                "b2_llm_tokens": record_b2_summary["total_tokens"],
                "b2_llm_api_time_sec": record_b2_summary["elapsed_sec"],
                "b2_call_ids": [entry["call_id"] for entry in record_b2_entries],
                "b2_elapsed_sec": round(record_b2_wall, 2),
                "elapsed_sec": round(time.perf_counter() - record_started, 2),
            }
        )

    wall_elapsed = time.perf_counter() - started
    telemetry = ledger.build_telemetry(client=raw_client)
    fact_stage = telemetry["stage_summary"]["fact_extraction"]
    b2_stage = telemetry["stage_summary"]["semantic_evaluation"]
    gate_wall_time = sum(float(record.get("gate_elapsed_sec") or 0) for record in records)
    return {
        "mode": "fact_gate_plus_trimmed_qc",
        "model": model,
        "families": family_keys,
        "wall_elapsed_sec": round(wall_elapsed, 2),
        **_telemetry_aliases(telemetry),
        "gate_wall_elapsed_sec": round(gate_wall_time, 2),
        "fact_extraction_llm_call_count": fact_stage["call_count"],
        "fact_extraction_llm_total_tokens": fact_stage["total_tokens"],
        "fact_extraction_llm_elapsed_sec": fact_stage["elapsed_sec"],
        "gate_llm_call_count": fact_stage["call_count"],
        "gate_llm_total_tokens": fact_stage["total_tokens"],
        "gate_llm_elapsed_sec": fact_stage["elapsed_sec"],
        "gate_only_status_counter": dict(Counter(row["status"] for row in gate_rows.values())),
        "b2_llm_call_count": b2_stage["call_count"],
        "b2_llm_total_tokens": b2_stage["total_tokens"],
        "b2_llm_elapsed_sec": b2_stage["elapsed_sec"],
        "b2_wall_elapsed_sec": round(b2_wall_time, 2),
        "record_count": len(records),
        "item_count": len(b2_rows),
        "status_counter": dict(Counter(row["status"] for row in b2_rows.values())),
        "records": records,
        "gate_rows": gate_rows,
        "rows": b2_rows,
    }


def compare(full: dict[str, Any], trimmed: dict[str, Any]) -> dict[str, Any]:
    full_rows = full["rows"]
    trimmed_rows = trimmed["rows"]
    all_keys = sorted(set(full_rows) | set(trimmed_rows))
    diff_rows: list[dict[str, Any]] = []
    rule_stats: dict[str, dict[str, Any]] = {}
    for key in all_keys:
        record_id, rule_id = key
        left = full_rows.get(key)
        right = trimmed_rows.get(key)
        full_status = left.get("status") if left else "missing"
        trimmed_status = right.get("status") if right else "missing"
        changed = full_status != trimmed_status
        diff_rows.append(
            {
                "record_id": record_id,
                "rule_id": rule_id,
                "full_text_status": full_status,
                "fact_gate_status": trimmed_status,
                "status_changed": changed,
                "full_text_duration_sec": round(float((left or {}).get("duration_sec") or 0), 4),
                "fact_gate_shared_duration_sec": round(float((right or {}).get("duration_sec") or 0), 4),
                "full_text_tokens": int((left or {}).get("tokens") or 0),
                "fact_gate_record_tokens": int((right or {}).get("tokens") or 0),
                "fact_gate_duration_additive": bool((right or {}).get("duration_additive", False)),
                "fact_gate_tokens_additive": bool((right or {}).get("tokens_additive", False)),
                "fact_gate_token_attribution": str((right or {}).get("token_attribution") or ""),
                "fact_gate_call_ids": list((right or {}).get("shared_call_ids") or []),
                "gate_reason": _short_text((right or {}).get("gate_reason"), 160),
                "full_text_evidence": _short_text((left or {}).get("evidence"), 160),
            }
        )
    for rule_id in sorted({row["rule_id"] for row in diff_rows}):
        subset = [row for row in diff_rows if row["rule_id"] == rule_id]
        rule_stats[rule_id] = {
            "total": len(subset),
            "status_diff_count": sum(1 for row in subset if row["status_changed"]),
            "full_text_status_counter": dict(Counter(row["full_text_status"] for row in subset)),
            "fact_gate_status_counter": dict(Counter(row["fact_gate_status"] for row in subset)),
            "full_text_duration_sum_sec": round(sum(row["full_text_duration_sec"] for row in subset), 2),
            "fact_gate_shared_duration_sum_sec": None,
            "fact_gate_duration_aggregation": "shared_non_additive",
            "full_text_tokens_sum": sum(row["full_text_tokens"] for row in subset),
            "fact_gate_record_tokens_sum": None,
            "fact_gate_token_aggregation": "shared_non_additive",
            "fact_gate_unique_call_ids": sorted(
                {
                    call_id
                    for row in subset
                    for call_id in list(row.get("fact_gate_call_ids") or [])
                    if call_id
                }
            ),
        }
    return {
        "row_count": len(diff_rows),
        "status_diff_count": sum(1 for row in diff_rows if row["status_changed"]),
        "diff_rows": diff_rows,
        "rule_stats": rule_stats,
    }


def _counter_text(counter: dict[str, Any]) -> str:
    if not counter:
        return "-"
    return "，".join(f"{key}={value}" for key, value in sorted(counter.items()))


def _stringify_row_keys(rows: dict[tuple[str, str], dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {f"{key[0]}::{key[1]}": value for key, value in (rows or {}).items()}


def write_markdown(
    payload: dict[str, Any],
    path: Path,
    *,
    redaction_terms_by_record: dict[str, Iterable[str]] | None = None,
) -> None:
    payload = sanitize_report_payload(
        payload,
        redaction_terms_by_record=redaction_terms_by_record,
    )
    full = payload["full_text"]
    trimmed = payload["fact_gate_trimmed"]
    b2 = payload.get("fact_gate_plus_trimmed_qc")
    compared_mode = "fact_gate_plus_trimmed_qc" if b2 else "fact_gate_trimmed"
    compared_payload = b2 or trimmed
    telemetry = compared_payload.get("telemetry") if isinstance(compared_payload.get("telemetry"), dict) else {}
    stage_summary = telemetry.get("stage_summary") if isinstance(telemetry.get("stage_summary"), dict) else {}
    fact_stage = stage_summary.get("fact_extraction") if isinstance(stage_summary.get("fact_extraction"), dict) else {}
    semantic_stage = (
        stage_summary.get("semantic_evaluation")
        if isinstance(stage_summary.get("semantic_evaluation"), dict)
        else {}
    )
    comparison = payload["comparison"]
    lines = [
        f"# LX0609 full_text vs {compared_mode} 严格 A/B",
        "",
        "## 实验条件",
        "",
        f"- full_text job_id: `{full['job_id']}`",
        f"- 模型: `{payload['model']}`",
        f"- 并发: `{payload['parallel_records']}`",
        f"- 病历数: `{len(payload['record_ids'])}`",
        f"- LX 点数: `{len(payload['selected_rule_ids'])}`",
        f"- fact_gate_trimmed 说明: 这是门控阶段状态，`needs_full_qc` 表示需要进入后续完整质控，不等同于不合规。",
        f"- B2 说明: `fact_gate_plus_trimmed_qc` 只对 gate 命中的规则调用事实上下文质控，gate 排除项和数据缺口直接短路。",
        "",
        "## 总耗时与 token",
        "",
        "| 模式 | wall elapsed | LLM/API elapsed | tokens | items | 状态分布 |",
        "|---|---:|---:|---:|---:|---|",
        f"| full_text | {full['wall_elapsed_sec']}s | {full['processing_time_sec']}s | {full['total_tokens']} | {full['item_count']} | {_counter_text(full['status_counter'])} |",
        f"| fact_gate_trimmed | {trimmed['wall_elapsed_sec']}s | {trimmed['llm_total_elapsed_sec']}s | {trimmed['llm_total_tokens']} | {trimmed['item_count']} | {_counter_text(trimmed['status_counter'])} |",
        *(
            [
                f"| fact_gate_plus_trimmed_qc | {b2['wall_elapsed_sec']}s | {b2['llm_total_elapsed_sec']}s | {b2['llm_total_tokens']} | {b2['item_count']} | {_counter_text(b2['status_counter'])} |",
            ]
            if b2
            else []
        ),
        "",
        "## LLM 唯一调用账本",
        "",
        f"- telemetry schema: `{telemetry.get('telemetry_schema_version') or '-'}`",
        f"- unique calls: `{telemetry.get('llm_call_count', 0)}`",
        f"- ledger tokens: `{telemetry.get('total_tokens', 0)}` = input `{telemetry.get('input_tokens', 0)}` + output `{telemetry.get('output_tokens', 0)}` + unattributed `{telemetry.get('unattributed_tokens', 0)}`",
        f"- fact_extraction: calls `{fact_stage.get('call_count', 0)}`, tokens `{fact_stage.get('total_tokens', 0)}`",
        f"- semantic_evaluation: calls `{semantic_stage.get('call_count', 0)}`, tokens `{semantic_stage.get('total_tokens', 0)}`",
        f"- invariant: `{'PASS' if telemetry.get('telemetry_invariant_ok') else 'FAIL'}`",
        "",
        "## B2 分段耗时",
        "",
        "| 指标 | 值 |",
        "|---|---:|",
        f"| gate-only 状态分布 | {_counter_text((b2 or {}).get('gate_only_status_counter') or trimmed['status_counter'])} |",
        f"| B2 LLM 调用数 | {(b2 or {}).get('b2_llm_call_count', 0)} |",
        f"| B2 LLM API 耗时 | {(b2 or {}).get('b2_llm_elapsed_sec', 0)}s |",
        f"| B2 LLM tokens | {(b2 or {}).get('b2_llm_total_tokens', 0)} |",
        "",
        "## 每个 LX 点状态与耗时差异",
        "",
        f"| LX 点 | 对齐条数 | 状态差异数 | full_text 状态 | {compared_mode} 状态 | full_text耗时和 | {compared_mode}耗时归因 | full_text tokens | {compared_mode} token归因 |",
        "|---|---:|---:|---|---|---:|---:|---:|---:|",
    ]
    for rule_id, stat in comparison["rule_stats"].items():
        lines.append(
            "| {rule_id} | {total} | {diffs} | {full_status} | {gate_status} | {full_time}s | {gate_time}s | {full_tokens} | {gate_tokens} |".format(
                rule_id=rule_id,
                total=stat["total"],
                diffs=stat["status_diff_count"],
                full_status=_counter_text(stat["full_text_status_counter"]),
                gate_status=_counter_text(stat["fact_gate_status_counter"]),
                full_time=stat["full_text_duration_sum_sec"],
                gate_time="shared/non-additive",
                full_tokens=stat["full_text_tokens_sum"],
                gate_tokens=f"shared/non-additive ({len(stat['fact_gate_unique_call_ids'])} unique calls)",
            )
        )
    lines.extend(
        [
            "",
            "## 状态差异明细",
            "",
            f"| 病历 | LX 点 | full_text | {compared_mode} | gate 原因 | full_text 证据摘要 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in comparison["diff_rows"]:
        if not row["status_changed"]:
            continue
        lines.append(
            "| {record_id} | {rule_id} | {full_status} | {gate_status} | {gate_reason} | {evidence} |".format(
                record_id=row["record_id"],
                rule_id=row["rule_id"],
                full_status=row["full_text_status"],
                gate_status=row["fact_gate_status"],
                gate_reason=str(row["gate_reason"]).replace("|", "/"),
                evidence=str(row["full_text_evidence"]).replace("|", "/"),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Strict LX0609 A/B: full_text vs fact_gate_trimmed/B2")
    parser.add_argument(
        "--mode",
        choices=("full_text", "fact_gate_trimmed", "fact_gate_trimmed_qc", "both"),
        default="both",
    )
    parser.add_argument("--full-text-job-id", default=DEFAULT_FULL_TEXT_JOB_ID)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--parallel-records", type=int, default=2)
    parser.add_argument("--b2-limit", type=int, default=0, help="Limit B2 trimmed QC calls for smoke tests; 0 means no limit.")
    parser.add_argument("--output-dir", default="../tmp-lx0609-ab-test")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    full = load_full_text_job(args.full_text_job_id)
    redaction_terms_by_record = getattr(full, "redaction_terms_by_record", {})
    if args.mode == "full_text":
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "full_text",
            "model": args.model,
            "parallel_records": args.parallel_records,
            "full_text": {**full, "rows": _stringify_row_keys(full["rows"])},
        }
        output = sanitize_report_payload(
            output,
            redaction_terms_by_record=redaction_terms_by_record,
        )
        path = output_dir / f"full-text-summary-{timestamp}.json"
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"mode": "full_text", "json": str(path), "wall_sec": full["wall_elapsed_sec"]}, ensure_ascii=False, indent=2))
        return
    filters = full.get("filters") if isinstance(full.get("filters"), dict) else {}
    record_ids = [str(item) for item in filters.get("selected_draft_ids") or filters.get("record_ids") or DEFAULT_RECORD_IDS]
    selected_rule_ids = [
        str(item).upper()
        for item in filters.get("scoped_customer_rule_ids") or filters.get("selected_rule_ids") or DEFAULT_SELECTED_RULE_IDS
    ]
    # Keep deterministic ordering for strict comparison.
    record_ids = [record_id for record_id in DEFAULT_RECORD_IDS if record_id in set(record_ids)] or list(DEFAULT_RECORD_IDS)
    selected_rule_ids = [rule_id for rule_id in DEFAULT_SELECTED_RULE_IDS if rule_id in set(selected_rule_ids)] or list(DEFAULT_SELECTED_RULE_IDS)
    b2_payload: dict[str, Any] | None = None
    if args.mode in {"fact_gate_trimmed_qc", "both"}:
        b2_payload = await run_fact_gate_plus_trimmed_qc(
            record_ids=record_ids,
            selected_rule_ids=selected_rule_ids,
            families=DEFAULT_FAMILIES,
            model=args.model,
            b2_limit=max(0, int(args.b2_limit or 0)),
        )
        fact_only_telemetry = _telemetry_slice(
            b2_payload["telemetry"],
            stages=["fact_extraction"],
        )
        trimmed = {
            **b2_payload,
            **_telemetry_aliases(fact_only_telemetry),
            "mode": "fact_gate_trimmed",
            "rows": b2_payload["gate_rows"],
            "status_counter": b2_payload["gate_only_status_counter"],
            "wall_elapsed_sec": b2_payload["gate_wall_elapsed_sec"],
        }
    else:
        trimmed = await run_fact_gate_trimmed(
            record_ids=record_ids,
            selected_rule_ids=selected_rule_ids,
            families=DEFAULT_FAMILIES,
            model=args.model,
        )
    if args.mode == "fact_gate_trimmed":
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "fact_gate_trimmed",
            "model": args.model,
            "parallel_records": args.parallel_records,
            "record_ids": record_ids,
            "selected_rule_ids": selected_rule_ids,
            "fact_gate_trimmed": {
                **trimmed,
                "rows": _stringify_row_keys(trimmed["rows"]),
                "gate_rows": _stringify_row_keys(trimmed.get("gate_rows")),
            },
        }
        output = sanitize_report_payload(
            output,
            redaction_terms_by_record=redaction_terms_by_record,
        )
        path = output_dir / f"fact-gate-trimmed-summary-{timestamp}.json"
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "mode": "fact_gate_trimmed",
                    "json": str(path),
                    "wall_sec": trimmed["wall_elapsed_sec"],
                    "tokens": trimmed["llm_total_tokens"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    comparison_target = b2_payload or trimmed
    comparison = compare(full, comparison_target)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "parallel_records": args.parallel_records,
        "record_ids": record_ids,
        "selected_rule_ids": selected_rule_ids,
        "full_text": {**full, "rows": _stringify_row_keys(full["rows"])},
        "fact_gate_trimmed": {
            **trimmed,
            "rows": _stringify_row_keys(trimmed["rows"]),
            "gate_rows": _stringify_row_keys(trimmed.get("gate_rows")),
        },
        **(
            {
                "fact_gate_plus_trimmed_qc": {
                    **b2_payload,
                    "rows": _stringify_row_keys(b2_payload["rows"]),
                    "gate_rows": _stringify_row_keys(b2_payload["gate_rows"]),
                }
            }
            if b2_payload
            else {}
        ),
        "comparison": comparison,
    }
    payload = sanitize_report_payload(
        payload,
        redaction_terms_by_record=redaction_terms_by_record,
    )
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"ab-result-{timestamp}.json"
    md_path = output_dir / f"ab-summary-{timestamp}.md"
    latest_json = output_dir / "latest.json"
    latest_md = output_dir / "latest.md"
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    write_markdown(
        payload,
        md_path,
        redaction_terms_by_record=redaction_terms_by_record,
    )
    write_markdown(
        payload,
        latest_md,
        redaction_terms_by_record=redaction_terms_by_record,
    )
    print(
        json.dumps(
            {
                "full_text_job_id": args.full_text_job_id,
                "model": args.model,
                "record_count": len(record_ids),
                "rule_count": len(selected_rule_ids),
                "full_text_wall_sec": full["wall_elapsed_sec"],
                "fact_gate_trimmed_wall_sec": trimmed["wall_elapsed_sec"],
                "fact_gate_plus_trimmed_qc_wall_sec": (b2_payload or {}).get("wall_elapsed_sec"),
                "full_text_tokens": full["total_tokens"],
                "fact_gate_trimmed_tokens": trimmed["llm_total_tokens"],
                "fact_gate_plus_trimmed_qc_tokens": (b2_payload or {}).get("llm_total_tokens"),
                "b2_llm_call_count": (b2_payload or {}).get("b2_llm_call_count"),
                "row_count": comparison["row_count"],
                "status_diff_count": comparison["status_diff_count"],
                "json": str(json_path),
                "markdown": str(md_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
