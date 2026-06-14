from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_backend_env() -> None:
    """POC 脚本从仓库根目录运行时，显式加载 backend/.env。"""
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_backend_env()

from app.services.custom_qc_workspace_service import CustomQCWorkspaceService  # noqa: E402
from app.services.effect_priority_qc import BATCH_OUTPUT_MODE_MINIMAL, QUALITY_PROFILE_THROUGHPUT  # noqa: E402
from app.services.medical_records.detail_service import get_documents  # noqa: E402
from app.services.programmatic_rule_executor import ProgrammaticRuleExecutor  # noqa: E402
from app.services.qc_rule_orchestrator import resolve_rule_execution_meta  # noqa: E402
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402


DEFAULT_VISIT_ID = "2313364"
DEFAULT_RULE_SET_KEY = "luxian_0609_qc_v1"
DEFAULT_STRATEGIES = (
    "baseline_current",
    "domain_family_max4",
    "domain_family_max5",
    "hybrid_medqc_v1",
    "partial_accept_max4",
    "network_retry_partial_max4",
)
CUSTOMER_RULE_CATALOG_PATH = ROOT / "backend" / "app" / "data" / "luxian_0609_rules_v1.json"


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _rule_id(rule: dict[str, Any]) -> str:
    return _safe_text(rule.get("rule_id") or rule.get("rule_code") or rule.get("id")).upper()


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _slug(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_\-]+", "-", value.strip())
    return normalized.strip("-") or "generic"


def _chunks(items: Sequence[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    chunk_size = max(1, int(size or 1))
    for start in range(0, len(items), chunk_size):
        yield list(items[start : start + chunk_size])


def _normalize_strategy_list(value: str) -> list[str]:
    if not value:
        return list(DEFAULT_STRATEGIES)
    selected = [item.strip() for item in value.split(",") if item.strip()]
    invalid = sorted(set(selected) - set(DEFAULT_STRATEGIES))
    if invalid:
        raise ValueError(f"未知策略: {', '.join(invalid)}")
    return selected or list(DEFAULT_STRATEGIES)


def _load_customer_point_count() -> int:
    if not CUSTOMER_RULE_CATALOG_PATH.exists():
        return 0
    data = json.loads(CUSTOMER_RULE_CATALOG_PATH.read_text(encoding="utf-8"))
    return len(data) if isinstance(data, list) else 0


def _compact_counter(counter: Counter[str], limit: int = 10) -> list[dict[str, Any]]:
    return [{"key": key, "count": count} for key, count in counter.most_common(limit)]


def _normalize_bucket_strategy(value: str) -> str:
    normalized = str(value or "domain_only").strip().lower() or "domain_only"
    return normalized if normalized in {"domain_only", "domain_family"} else "domain_only"


def _rule_text(rule: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "rule_id",
        "rule_code",
        "name",
        "rule_name",
        "description",
        "check_content",
        "applicable_documents",
        "rule_family",
    ):
        value = rule.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value or ""))
    return " ".join(parts).lower()


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _hybrid_logic_type(rule: dict[str, Any]) -> str:
    meta = resolve_rule_execution_meta(rule)
    text = _rule_text(rule)
    family = str(meta.rule_family or "general").lower()
    if _contains_any(text, ("ct", "mri", "影像", "检查报告", "阳性结果")):
        return "imaging_followup"
    if _contains_any(text, ("检验", "培养", "细菌", "危急值", "血常规", "血凝", "dic", "隐血")):
        return "lab_followup"
    if _contains_any(text, ("同意书", "签名", "授权", "知情", "麻醉", "输血")) or family == "signature_authority":
        return "signature_consent"
    if _contains_any(text, ("24小时", "8小时", "6小时", "48", "72", "时间", "及时", "时限")) or family == "timeliness":
        return "timeliness"
    if _contains_any(text, ("医嘱", "费用", "收费", "一致", "执行情况", "相符")) or family in {
        "consistency_cross_doc",
        "procedure_order_linkage",
    }:
        return "cross_doc_consistency"
    if _contains_any(text, ("缺", "无", "未见", "未书写", "未完成")) or family == "presence_required":
        return "existence"
    if family == "content_completeness":
        return "semantic_content"
    return "general_semantic"


def _hybrid_evidence_group(rule: dict[str, Any], logic_type: str) -> str:
    meta = resolve_rule_execution_meta(rule)
    text = _rule_text(rule)
    if logic_type == "imaging_followup":
        return "imaging_reports_course_notes"
    if logic_type == "lab_followup":
        return "lab_reports_course_notes"
    if _contains_any(text, ("麻醉", "麻醉同意")):
        return "anesthesia_docs"
    if _contains_any(text, ("输血", "血浆", "输血前")):
        return "transfusion_docs"
    if _contains_any(text, ("手术", "术前", "术后", "安全核查", "风险评估")):
        return "surgery_docs"
    if _contains_any(text, ("会诊", "讨论", "mdt")):
        return "consult_discussion_docs"
    if meta.execution_domain == "admission":
        return "admission_record"
    if meta.execution_domain == "course":
        return "course_records"
    return f"{meta.execution_domain}_records"


def _hybrid_trigger_group(rule: dict[str, Any], logic_type: str) -> str:
    text = _rule_text(rule)
    if _contains_any(text, ("病危", "病重", "抢救")):
        return "critical_status"
    if _contains_any(text, ("手术", "术前", "术后", "麻醉", "安全核查")):
        return "surgery_event"
    if _contains_any(text, ("输血", "血浆")):
        return "transfusion_event"
    if _contains_any(text, ("会诊", "讨论", "mdt")):
        return "consult_event"
    if logic_type == "lab_followup":
        return "abnormal_lab"
    if logic_type == "imaging_followup":
        return "abnormal_imaging"
    if _contains_any(text, ("入院", "首次病程", "主诉")):
        return "admission_event"
    return "general_trigger"


def _hybrid_risk_tier(rule: dict[str, Any], logic_type: str, trigger_group: str) -> str:
    text = _rule_text(rule)
    if _contains_any(text, ("危急值", "病危", "抢救", "输血", "麻醉", "四级手术")):
        return "high"
    if trigger_group in {"critical_status", "transfusion_event"}:
        return "high"
    if logic_type in {"cross_doc_consistency", "signature_consent", "lab_followup", "imaging_followup"}:
        return "normal_high"
    return "normal"


def _hybrid_pack_cap(logic_type: str, risk_tier: str) -> int:
    if risk_tier == "high":
        return 3 if logic_type in {"cross_doc_consistency", "lab_followup", "imaging_followup", "result_followup"} else 5
    if logic_type == "cross_doc_consistency":
        return 3
    if logic_type in {"lab_followup", "imaging_followup", "result_followup"}:
        return 5
    if logic_type == "signature_consent":
        return 5
    if logic_type in {"timeliness", "existence"}:
        return 8
    return 8


def _hybrid_logic_bucket(logic_type: str) -> str:
    if logic_type in {"timeliness", "existence"}:
        return "structure_time_presence"
    if logic_type in {"lab_followup", "imaging_followup"}:
        return "result_followup"
    if logic_type == "semantic_content":
        return "semantic_content"
    if logic_type == "signature_consent":
        return "signature_consent"
    if logic_type == "cross_doc_consistency":
        return "cross_doc_consistency"
    return "general_semantic"


def _bucket_key_for_rule(rule: dict[str, Any], *, bucket_strategy: str) -> str:
    meta = resolve_rule_execution_meta(rule)
    if bucket_strategy == "domain_family":
        return f"{meta.execution_domain}::{meta.doc_scope}::{meta.rule_family}"
    return f"{meta.execution_domain}::{meta.doc_scope}"


def _hybrid_bucket_key_for_rule(rule: dict[str, Any]) -> str:
    meta = resolve_rule_execution_meta(rule)
    logic_type = _hybrid_logic_type(rule)
    evidence_group = _hybrid_evidence_group(rule, logic_type)
    logic_bucket = _hybrid_logic_bucket(logic_type)
    return "::".join(
        [
            meta.execution_domain,
            meta.doc_scope,
            evidence_group,
            logic_bucket,
        ]
    )


def _expected_rule_ids(rules: Sequence[dict[str, Any]]) -> list[str]:
    return [_rule_id(rule) for rule in rules if _rule_id(rule)]


def _clip(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _compact_rule_result(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    return {
        "rule_id": _rule_id(item),
        "rule_name": _safe_text(item.get("rule_name") or item.get("name")),
        "status": _safe_text(item.get("status")),
        "is_compliant": bool(item.get("is_compliant") is True),
        "confidence": _to_float(item.get("confidence")),
        "findings": _clip(item.get("findings"), 420),
        "evidence": _clip(item.get("evidence"), 420),
        "suggestion": _clip(item.get("suggestion"), 260),
        "bucket_key": _safe_text(metadata.get("bucket_key")),
        "pack_id": _safe_text(metadata.get("pack_id")),
        "pack_size": _to_int(metadata.get("pack_size")),
        "pack_fallback": bool(metadata.get("pack_fallback") is True),
    }


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    input_bucket_strategy: str
    effective_bucket_strategy: str
    candidates: tuple[int, ...]
    max_pack_size: int
    partial_accept: bool = False
    network_retry_first: bool = False


@dataclass
class LabConfig:
    visit_id: str
    rule_set_key: str
    strategies: list[str]
    output_dir: Path
    low_confidence_threshold: float
    dry_run: bool
    max_rules: int
    network_retry: int


STRATEGY_CONFIGS: dict[str, StrategyConfig] = {
    "baseline_current": StrategyConfig(
        name="baseline_current",
        input_bucket_strategy="fixed_packs",
        effective_bucket_strategy="domain_only",
        candidates=(3, 5, 8, 10, 12, 15),
        max_pack_size=15,
    ),
    "domain_family_max4": StrategyConfig(
        name="domain_family_max4",
        input_bucket_strategy="domain_family",
        effective_bucket_strategy="domain_family",
        candidates=(2, 3, 4),
        max_pack_size=4,
    ),
    "domain_family_max5": StrategyConfig(
        name="domain_family_max5",
        input_bucket_strategy="domain_family",
        effective_bucket_strategy="domain_family",
        candidates=(3, 4, 5),
        max_pack_size=5,
    ),
    "hybrid_medqc_v1": StrategyConfig(
        name="hybrid_medqc_v1",
        input_bucket_strategy="hybrid_medqc_v1",
        effective_bucket_strategy="hybrid_medqc_v1",
        candidates=(3, 5, 8),
        max_pack_size=8,
        partial_accept=True,
        network_retry_first=True,
    ),
    "partial_accept_max4": StrategyConfig(
        name="partial_accept_max4",
        input_bucket_strategy="domain_family",
        effective_bucket_strategy="domain_family",
        candidates=(2, 3, 4),
        max_pack_size=4,
        partial_accept=True,
    ),
    "network_retry_partial_max4": StrategyConfig(
        name="network_retry_partial_max4",
        input_bucket_strategy="domain_family",
        effective_bucket_strategy="domain_family",
        candidates=(2, 3, 4),
        max_pack_size=4,
        partial_accept=True,
        network_retry_first=True,
    ),
}


class Luxian0609PackStrategyLab:
    def __init__(self, config: LabConfig) -> None:
        self.config = config
        self.workspace = CustomQCWorkspaceService()
        self.qc_service = SichuanQCService()
        self.program_executor = ProgrammaticRuleExecutor()
        self._record: dict[str, Any] = {}
        self._pack_counter = 0

    def load_record(self) -> dict[str, Any]:
        records = self.workspace.collect_records(
            scope="all",
            department=None,
            doctor=None,
            date_field="discharge",
            start_date=None,
            end_date=None,
            keyword=None,
            record_ids=[self.config.visit_id],
        )
        hydrated = self.workspace.hydrate_records_with_medical_text(records)
        if not hydrated:
            raise RuntimeError(f"未找到病历或病历正文为空: visit_id={self.config.visit_id}")

        record = dict(hydrated[0])
        medical_text = _safe_text(record.get("medical_text") or record.get("content"))
        if not medical_text:
            concat_bundle = get_documents(self.config.visit_id, mode="concat")
            medical_text = _safe_text((concat_bundle or {}).get("text"))
            record["document_count"] = _to_int((concat_bundle or {}).get("document_count"))
            record["medical_text_source"] = "documents_concat"
        else:
            record["medical_text_source"] = "frontpage_record_content"
        if not medical_text:
            raise RuntimeError(f"病历正文为空: visit_id={self.config.visit_id}")

        record["medical_text"] = medical_text
        record["content"] = medical_text
        record["document_type"] = ""
        record.setdefault("record_id", self.config.visit_id)
        record.setdefault("visit_id", self.config.visit_id)
        return record

    def load_rules(self) -> tuple[list[dict[str, Any]], list[str]]:
        rule_set = get_sichuan_rule_set(self.config.rule_set_key)
        if rule_set is None:
            raise RuntimeError(f"未找到规则集: {self.config.rule_set_key}")

        rules: list[dict[str, Any]] = []
        missing_rule_ids: list[str] = []
        for rule_id in rule_set.rule_ids:
            rule = self.qc_service.get_rule_by_id(rule_id)
            if not rule:
                missing_rule_ids.append(str(rule_id))
                continue
            rules.append(dict(rule))

        if self.config.max_rules > 0:
            rules = rules[: self.config.max_rules]
        return rules, missing_rule_ids

    def split_executor_types(self, rules: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        program_rules: list[dict[str, Any]] = []
        llm_rules: list[dict[str, Any]] = []
        program_fallback_rule_ids: list[str] = []
        for rule in rules:
            meta = resolve_rule_execution_meta(rule)
            if meta.executor_type == "program" and self.program_executor.can_execute(rule):
                program_rules.append(rule)
                continue
            if meta.executor_type == "program":
                program_fallback_rule_ids.append(_rule_id(rule))
            llm_rules.append(rule)
        return program_rules, llm_rules, program_fallback_rule_ids

    def build_buckets(self, rules: list[dict[str, Any]], strategy: StrategyConfig) -> dict[str, list[dict[str, Any]]]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        if strategy.name == "hybrid_medqc_v1":
            for rule in rules:
                buckets[_hybrid_bucket_key_for_rule(rule)].append(rule)
            return dict(sorted(buckets.items(), key=lambda item: item[0]))

        effective_bucket = _normalize_bucket_strategy(strategy.effective_bucket_strategy)
        for rule in rules:
            buckets[_bucket_key_for_rule(rule, bucket_strategy=effective_bucket)].append(rule)
        return dict(sorted(buckets.items(), key=lambda item: item[0]))

    def pack_cap_for_bucket(self, strategy: StrategyConfig, bucket_key: str, entries: Sequence[dict[str, Any]]) -> int:
        if strategy.name != "hybrid_medqc_v1":
            return max(1, int(strategy.max_pack_size or 1))
        caps: list[int] = []
        for rule in entries:
            logic_type = _hybrid_logic_type(rule)
            trigger_group = _hybrid_trigger_group(rule, logic_type)
            risk_tier = _hybrid_risk_tier(rule, logic_type, trigger_group)
            caps.append(_hybrid_pack_cap(_hybrid_logic_bucket(logic_type), risk_tier))
        cap = min(caps) if caps else int(strategy.max_pack_size or 8)
        return max(1, min(int(strategy.max_pack_size or 8), cap))

    async def call_pack(
        self,
        *,
        strategy: StrategyConfig,
        bucket_key: str,
        pack_rules: list[dict[str, Any]],
        retry_count: int,
        mode: str,
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        self._pack_counter += 1
        pack_id = f"{strategy.name}-{mode}-{_slug(bucket_key)}-{self._pack_counter}"
        expected_ids = _expected_rule_ids(pack_rules)

        if self.config.dry_run:
            return {
                "strategy": strategy.name,
                "bucket_key": bucket_key,
                "pack_id": pack_id,
                "rule_ids": expected_ids,
                "pack_size": len(pack_rules),
                "accepted_rule_ids": [],
                "retry_rule_ids": [],
                "parsed_rule_ids": [],
                "missing_rule_ids": [],
                "low_confidence_rule_ids": [],
                "parse_error": False,
                "provider_error": "",
                "retry_count": retry_count,
                "fallback_reason": "",
                "elapsed_ms": 0,
                "tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "context_tokens_estimate": 0,
                "mode": mode,
                "skipped": True,
            }, {}

        started = time.perf_counter()
        response: dict[str, Any] = {}
        provider_error = ""
        try:
            first_meta = resolve_rule_execution_meta(pack_rules[0]) if pack_rules else None
            response = await self.qc_service._llm_evaluate_batch_compact(
                pack_rules,
                self._record,
                {
                    "pack_id": pack_id,
                    "pack_size": len(pack_rules),
                    "prompt_strategy": "batch_compact_v1",
                    "quality_profile": QUALITY_PROFILE_THROUGHPUT,
                    "batch_output_mode": BATCH_OUTPUT_MODE_MINIMAL,
                    "low_confidence_threshold": self.config.low_confidence_threshold,
                    "execution_domain": first_meta.execution_domain if first_meta else "generic",
                    "doc_scope": first_meta.doc_scope if first_meta else "primary",
                    "rule_family": first_meta.rule_family if first_meta else "",
                    "mode": mode,
                },
            )
        except Exception as exc:  # noqa: BLE001 - POC 要完整记录模型/网络异常
            provider_error = f"{type(exc).__name__}: {exc}"

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        parsed_by_rule: dict[str, dict[str, Any]] = {}
        for item in list(response.get("results") or []):
            rid = _rule_id(dict(item))
            if rid and rid in expected_ids and rid not in parsed_by_rule:
                parsed_by_rule[rid] = dict(item)

        missing_ids = {
            _safe_text(item).upper()
            for item in (response.get("missing_rule_ids") or [])
            if _safe_text(item)
        }
        missing_ids.update(set(expected_ids) - set(parsed_by_rule.keys()))

        low_ids = {
            _safe_text(item).upper()
            for item in (response.get("low_confidence_rule_ids") or [])
            if _safe_text(item)
        }
        for rid, item in parsed_by_rule.items():
            confidence = _to_float(item.get("confidence"))
            if confidence and confidence < self.config.low_confidence_threshold:
                low_ids.add(rid)

        parse_error = bool(response.get("parse_error") is True)
        accepted_ids = sorted(set(parsed_by_rule.keys()) - missing_ids - low_ids)
        if provider_error or parse_error:
            accepted_ids = []

        retry_ids = sorted(set(expected_ids) - set(accepted_ids))
        reasons: list[str] = []
        if provider_error:
            reasons.append("provider_error")
        else:
            if parse_error:
                reasons.append("parse_error")
            if missing_ids:
                reasons.append("missing_rule_ids")
            if low_ids:
                reasons.append("low_confidence_rule_ids")

        return {
            "strategy": strategy.name,
            "bucket_key": bucket_key,
            "pack_id": pack_id,
            "rule_ids": expected_ids,
            "pack_size": len(pack_rules),
            "accepted_rule_ids": accepted_ids,
            "retry_rule_ids": retry_ids,
            "parsed_rule_ids": sorted(parsed_by_rule.keys()),
            "missing_rule_ids": sorted(missing_ids),
            "low_confidence_rule_ids": sorted(low_ids),
            "parse_error": parse_error,
            "provider_error": provider_error,
            "retry_count": retry_count,
            "fallback_reason": "+".join(reasons),
            "elapsed_ms": elapsed_ms,
            "tokens": _to_int(response.get("tokens_used")),
            "prompt_tokens": _to_int(response.get("prompt_tokens")),
            "completion_tokens": _to_int(response.get("completion_tokens")),
            "context_tokens_estimate": _to_int(response.get("context_tokens_estimate")),
            "mode": mode,
            "skipped": False,
        }, {rid: parsed_by_rule[rid] for rid in accepted_ids if rid in parsed_by_rule}

    async def probe_pack_size(self, strategy: StrategyConfig, bucket_key: str, entries: list[dict[str, Any]], diagnostics: list[dict[str, Any]]) -> int:
        pack_cap = self.pack_cap_for_bucket(strategy, bucket_key, entries)
        candidates = sorted(
            {
                max(1, int(value))
                for value in strategy.candidates
                if int(value) <= pack_cap and int(value) <= len(entries)
            },
            reverse=True,
        )
        if not candidates:
            return min(len(entries), pack_cap)

        selected = candidates[-1]
        for candidate in candidates:
            diag, _ = await self.call_pack(
                strategy=strategy,
                bucket_key=bucket_key,
                pack_rules=list(entries[:candidate]),
                retry_count=0,
                mode="probe",
            )
            diagnostics.append(diag)
            if diag.get("provider_error") or diag.get("parse_error") or diag.get("missing_rule_ids"):
                continue
            low_count = len(list(diag.get("low_confidence_rule_ids") or []))
            if low_count >= max(1, candidate // 2):
                continue
            selected = candidate
            break
        return max(1, selected)

    async def run_whole_pack(
        self,
        *,
        strategy: StrategyConfig,
        bucket_key: str,
        pack_rules: list[dict[str, Any]],
        diagnostics: list[dict[str, Any]],
        accepted_results: dict[str, dict[str, Any]],
        retry_count: int = 0,
    ) -> None:
        diag, accepted = await self.call_pack(
            strategy=strategy,
            bucket_key=bucket_key,
            pack_rules=pack_rules,
            retry_count=retry_count,
            mode="execute",
        )
        diagnostics.append(diag)
        accepted_results.update(accepted)
        if diag.get("skipped") or not diag.get("fallback_reason"):
            return

        if (
            strategy.network_retry_first
            and diag.get("provider_error")
            and retry_count < self.config.network_retry
        ):
            await self.run_whole_pack(
                strategy=strategy,
                bucket_key=bucket_key,
                pack_rules=pack_rules,
                diagnostics=diagnostics,
                accepted_results=accepted_results,
                retry_count=retry_count + 1,
            )
            return

        if len(pack_rules) <= 1:
            return
        mid = max(1, len(pack_rules) // 2)
        await self.run_whole_pack(
            strategy=strategy,
            bucket_key=bucket_key,
            pack_rules=pack_rules[:mid],
            diagnostics=diagnostics,
            accepted_results=accepted_results,
        )
        await self.run_whole_pack(
            strategy=strategy,
            bucket_key=bucket_key,
            pack_rules=pack_rules[mid:],
            diagnostics=diagnostics,
            accepted_results=accepted_results,
        )

    async def run_partial_pack(
        self,
        *,
        strategy: StrategyConfig,
        bucket_key: str,
        pack_rules: list[dict[str, Any]],
        diagnostics: list[dict[str, Any]],
        accepted_results: dict[str, dict[str, Any]],
        retry_count: int = 0,
    ) -> None:
        diag, accepted = await self.call_pack(
            strategy=strategy,
            bucket_key=bucket_key,
            pack_rules=pack_rules,
            retry_count=retry_count,
            mode="execute",
        )
        diagnostics.append(diag)
        accepted_results.update(accepted)
        if diag.get("skipped") or not diag.get("fallback_reason"):
            return

        if (
            strategy.network_retry_first
            and diag.get("provider_error")
            and retry_count < self.config.network_retry
        ):
            await self.run_partial_pack(
                strategy=strategy,
                bucket_key=bucket_key,
                pack_rules=pack_rules,
                diagnostics=diagnostics,
                accepted_results=accepted_results,
                retry_count=retry_count + 1,
            )
            return

        if diag.get("provider_error") or diag.get("parse_error"):
            if len(pack_rules) <= 1:
                return
            mid = max(1, len(pack_rules) // 2)
            await self.run_partial_pack(
                strategy=strategy,
                bucket_key=bucket_key,
                pack_rules=pack_rules[:mid],
                diagnostics=diagnostics,
                accepted_results=accepted_results,
            )
            await self.run_partial_pack(
                strategy=strategy,
                bucket_key=bucket_key,
                pack_rules=pack_rules[mid:],
                diagnostics=diagnostics,
                accepted_results=accepted_results,
            )
            return

        retry_ids = set(diag.get("retry_rule_ids") or [])
        remaining = [rule for rule in pack_rules if _rule_id(rule) in retry_ids]
        if not remaining:
            return
        if len(remaining) == len(pack_rules):
            if len(remaining) <= 1:
                return
            mid = max(1, len(remaining) // 2)
            await self.run_partial_pack(
                strategy=strategy,
                bucket_key=bucket_key,
                pack_rules=remaining[:mid],
                diagnostics=diagnostics,
                accepted_results=accepted_results,
            )
            await self.run_partial_pack(
                strategy=strategy,
                bucket_key=bucket_key,
                pack_rules=remaining[mid:],
                diagnostics=diagnostics,
                accepted_results=accepted_results,
            )
            return
        await self.run_partial_pack(
            strategy=strategy,
            bucket_key=bucket_key,
            pack_rules=remaining,
            diagnostics=diagnostics,
            accepted_results=accepted_results,
            retry_count=retry_count + 1,
        )

    async def run_strategy(self, strategy_name: str, llm_rules: list[dict[str, Any]]) -> dict[str, Any]:
        strategy = STRATEGY_CONFIGS[strategy_name]
        self._pack_counter = 0
        diagnostics: list[dict[str, Any]] = []
        accepted_results: dict[str, dict[str, Any]] = {}
        buckets = self.build_buckets(llm_rules, strategy)
        bucket_details: dict[str, Any] = {}
        planned_pack_count = 0
        started = time.perf_counter()

        for bucket_key, entries in buckets.items():
            selected_size = await self.probe_pack_size(strategy, bucket_key, entries, diagnostics)
            planned_chunks = list(_chunks(entries, selected_size))
            planned_pack_count += len(planned_chunks)
            bucket_details[bucket_key] = {
                "rule_count": len(entries),
                "selected_pack_size": selected_size,
                "planned_pack_count": len(planned_chunks),
                "rule_ids": _expected_rule_ids(entries),
            }
            for chunk in planned_chunks:
                if strategy.partial_accept:
                    await self.run_partial_pack(
                        strategy=strategy,
                        bucket_key=bucket_key,
                        pack_rules=chunk,
                        diagnostics=diagnostics,
                        accepted_results=accepted_results,
                    )
                else:
                    await self.run_whole_pack(
                        strategy=strategy,
                        bucket_key=bucket_key,
                        pack_rules=chunk,
                        diagnostics=diagnostics,
                        accepted_results=accepted_results,
                    )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return self.build_strategy_summary(
            strategy=strategy,
            bucket_details=bucket_details,
            planned_pack_count=planned_pack_count,
            diagnostics=diagnostics,
            accepted_results=accepted_results,
            elapsed_ms=elapsed_ms,
            llm_rule_count=len(llm_rules),
        )

    def build_strategy_summary(
        self,
        *,
        strategy: StrategyConfig,
        bucket_details: dict[str, Any],
        planned_pack_count: int,
        diagnostics: list[dict[str, Any]],
        accepted_results: dict[str, dict[str, Any]],
        elapsed_ms: int,
        llm_rule_count: int,
    ) -> dict[str, Any]:
        execute_diags = [item for item in diagnostics if item.get("mode") == "execute"]
        rejected = [item for item in execute_diags if item.get("fallback_reason")]
        reason_counter: Counter[str] = Counter()
        missing_counter: Counter[str] = Counter()
        low_counter: Counter[str] = Counter()
        terminal_status_counter: Counter[str] = Counter()
        for item in rejected:
            for reason in str(item.get("fallback_reason") or "").split("+"):
                if reason:
                    reason_counter[reason] += 1
            missing_counter.update(item.get("missing_rule_ids") or [])
            low_counter.update(item.get("low_confidence_rule_ids") or [])
        for item in accepted_results.values():
            terminal_status_counter[str(item.get("status") or "unknown")] += 1

        total_tokens = sum(_to_int(item.get("tokens")) for item in diagnostics)
        total_prompt_tokens = sum(_to_int(item.get("prompt_tokens")) for item in diagnostics)
        total_completion_tokens = sum(_to_int(item.get("completion_tokens")) for item in diagnostics)
        final_result_count = len(accepted_results)
        total_pack_count = len(execute_diags)
        return {
            "strategy": strategy.name,
            "input_bucket_strategy": strategy.input_bucket_strategy,
            "effective_bucket_strategy": strategy.effective_bucket_strategy,
            "candidates": list(strategy.candidates),
            "max_pack_size": strategy.max_pack_size,
            "partial_accept": strategy.partial_accept,
            "network_retry_first": strategy.network_retry_first,
            "bucket_count": len(bucket_details),
            "bucket_details": bucket_details,
            "planned_pack_count": planned_pack_count,
            "probe_count": len([item for item in diagnostics if item.get("mode") == "probe"]),
            "pack_count": total_pack_count,
            "fallback_pack_count": len(rejected),
            "fallback_rate": round(len(rejected) / max(1, total_pack_count), 4),
            "single_retry_count": len([item for item in rejected if _to_int(item.get("pack_size")) <= 1]),
            "parse_error_count": reason_counter.get("parse_error", 0),
            "missing_rule_count": sum(len(item.get("missing_rule_ids") or []) for item in rejected),
            "low_confidence_count": sum(len(item.get("low_confidence_rule_ids") or []) for item in rejected),
            "provider_error_count": reason_counter.get("provider_error", 0),
            "fallback_reason_distribution": dict(reason_counter),
            "missing_rule_topn": _compact_counter(missing_counter),
            "low_confidence_rule_topn": _compact_counter(low_counter),
            "accepted_rule_count": final_result_count,
            "final_result_count": final_result_count,
            "terminal_status_count": dict(terminal_status_counter),
            "elapsed_ms": elapsed_ms,
            "first_result_elapsed_ms": next((_to_int(item.get("elapsed_ms")) for item in diagnostics if item.get("accepted_rule_ids")), 0),
            "tokens": total_tokens,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "rule_results": sorted(
                [_compact_rule_result(item) for item in accepted_results.values()],
                key=lambda item: str(item.get("rule_id") or ""),
            ),
            "diagnostics": diagnostics,
        }

    @staticmethod
    def score_strategies(strategy_summaries: dict[str, dict[str, Any]], llm_rule_count: int) -> list[dict[str, Any]]:
        baseline = strategy_summaries.get("baseline_current") or {}
        baseline_elapsed = max(1, _to_int(baseline.get("elapsed_ms")))
        baseline_tokens = max(1, _to_int(baseline.get("tokens")))
        baseline_provider_errors = _to_int(baseline.get("provider_error_count"))
        scored: list[dict[str, Any]] = []
        for name, summary in strategy_summaries.items():
            pack_count = max(1, _to_int(summary.get("pack_count")))
            completion_score = _to_float(summary.get("final_result_count")) / max(1, llm_rule_count)
            fallback_score = 1 - (_to_float(summary.get("fallback_pack_count")) / pack_count)
            stability_score = 1 - (
                (_to_float(summary.get("parse_error_count")) + _to_float(summary.get("provider_error_count"))) / pack_count
            )
            elapsed = max(1, _to_int(summary.get("elapsed_ms")))
            tokens = max(1, _to_int(summary.get("tokens")))
            speed_score = min(baseline_elapsed / elapsed, 1.5) / 1.5
            cost_score = min(baseline_tokens / tokens, 1.5) / 1.5
            final_score = (
                0.35 * completion_score
                + 0.25 * fallback_score
                + 0.20 * stability_score
                + 0.15 * speed_score
                + 0.05 * cost_score
            )
            eliminated_reasons: list[str] = []
            if completion_score < 0.98:
                eliminated_reasons.append("completion_score_lt_0.98")
            if _to_int(summary.get("provider_error_count")) > baseline_provider_errors + 1:
                eliminated_reasons.append("provider_error_exceeds_baseline_plus_1")
            scored.append(
                {
                    "strategy": name,
                    "completion_score": round(completion_score, 4),
                    "fallback_score": round(fallback_score, 4),
                    "stability_score": round(stability_score, 4),
                    "speed_score": round(speed_score, 4),
                    "cost_score": round(cost_score, 4),
                    "final_score": round(final_score, 4),
                    "elapsed_ms": elapsed,
                    "tokens": tokens,
                    "eliminated": bool(eliminated_reasons),
                    "eliminated_reasons": eliminated_reasons,
                }
            )

        survivors = [item for item in scored if not item["eliminated"]]
        survivors.sort(key=lambda item: (-_to_float(item["final_score"]), _to_int(item["elapsed_ms"])))
        for rank, item in enumerate(survivors, start=1):
            item["rank"] = rank
        eliminated = [item for item in scored if item["eliminated"]]
        eliminated.sort(key=lambda item: (-_to_float(item["final_score"]), _to_int(item["elapsed_ms"])))
        for item in eliminated:
            item["rank"] = None
        return survivors + eliminated

    async def run(self) -> dict[str, Any]:
        self._record = self.load_record()
        rules, missing_configured_rule_ids = self.load_rules()
        program_rules, llm_rules, program_fallback_rule_ids = self.split_executor_types(rules)

        strategy_summaries: dict[str, dict[str, Any]] = {}
        for strategy_name in self.config.strategies:
            strategy_summaries[strategy_name] = await self.run_strategy(strategy_name, llm_rules)

        score_table = self.score_strategies(strategy_summaries, len(llm_rules))
        winner = next((item for item in score_table if item.get("rank") == 1), None)
        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "dry_run": self.config.dry_run,
            "visit_id": self.config.visit_id,
            "rule_set_key": self.config.rule_set_key,
            "customer_qc_point_count": _load_customer_point_count(),
            "configured_execution_rule_count": len(get_sichuan_rule_set(self.config.rule_set_key).rule_ids),  # type: ignore[union-attr]
            "loaded_execution_rule_count": len(rules),
            "missing_configured_rule_ids": missing_configured_rule_ids,
            "llm_rule_count": len(llm_rules),
            "program_rule_count": len(program_rules),
            "program_rule_ids": [_rule_id(rule) for rule in program_rules],
            "program_fallback_rule_ids": program_fallback_rule_ids,
            "model": str(getattr(self.qc_service.client, "model", "") or ""),
            "record": {
                "visit_id": self._record.get("visit_id"),
                "patient_name": self._record.get("patient_name"),
                "department": self._record.get("department"),
                "scope": self._record.get("scope"),
                "medical_text_length": len(_safe_text(self._record.get("medical_text"))),
                "medical_text_source": self._record.get("medical_text_source"),
                "document_count": self._record.get("document_count"),
            },
            "config": {
                "strategies": self.config.strategies,
                "low_confidence_threshold": self.config.low_confidence_threshold,
                "max_rules": self.config.max_rules,
                "network_retry": self.config.network_retry,
            },
            "strategies": strategy_summaries,
            "score_table": score_table,
            "recommended_strategy": (winner or {}).get("strategy"),
        }


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# 泸县0609质控分桶策略旁路 POC 报告")
    lines.append("")
    lines.append(f"- 生成时间：{report.get('generated_at')}")
    lines.append(f"- dry-run：{'是' if report.get('dry_run') else '否'}")
    lines.append(f"- 病历：`{report.get('visit_id')}`")
    lines.append(f"- 规则集：`{report.get('rule_set_key')}`")
    lines.append(f"- 模型：`{report.get('model') or '-'}`")
    lines.append(f"- 客户质控点数：{report.get('customer_qc_point_count')}")
    lines.append(f"- 底层执行规则数：{report.get('configured_execution_rule_count')}")
    lines.append(f"- LLM 规则数 / 程序规则数：{report.get('llm_rule_count')} / {report.get('program_rule_count')}")
    lines.append(f"- 推荐策略：`{report.get('recommended_strategy') or '-'}`")
    lines.append("")
    lines.append("## 评分结果")
    lines.append("")
    lines.append("| 排名 | 策略 | 总分 | 完整性 | fallback | 稳定性 | 速度 | 成本 | 耗时(ms) | token | 淘汰原因 |")
    lines.append("| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for item in report.get("score_table") or []:
        lines.append(
            "| "
            f"{item.get('rank') or '-'} | {item.get('strategy')} | {item.get('final_score')} | "
            f"{item.get('completion_score')} | {item.get('fallback_score')} | {item.get('stability_score')} | "
            f"{item.get('speed_score')} | {item.get('cost_score')} | {item.get('elapsed_ms')} | "
            f"{item.get('tokens')} | {', '.join(item.get('eliminated_reasons') or []) or '-'} |"
        )
    lines.append("")
    lines.append("## 策略对比")
    lines.append("")
    lines.append("| 策略 | bucket数 | probe数 | pack总数 | fallback pack数 | fallback率 | 返回规则数 | parse错误 | 缺规则项 | 低置信项 | provider错误 | 耗时(ms) | token |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for name, summary in (report.get("strategies") or {}).items():
        lines.append(
            "| "
            f"{name} | {summary.get('bucket_count')} | {summary.get('probe_count')} | "
            f"{summary.get('pack_count')} | {summary.get('fallback_pack_count')} | {summary.get('fallback_rate')} | "
            f"{summary.get('final_result_count')} | {summary.get('parse_error_count')} | "
            f"{summary.get('missing_rule_count')} | {summary.get('low_confidence_count')} | "
            f"{summary.get('provider_error_count')} | {summary.get('elapsed_ms')} | {summary.get('tokens')} |"
        )
    lines.append("")

    for name, summary in (report.get("strategies") or {}).items():
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"- 输入分桶策略：`{summary.get('input_bucket_strategy')}`")
        lines.append(f"- 实际分桶策略：`{summary.get('effective_bucket_strategy')}`")
        lines.append(f"- 候选包大小：`{summary.get('candidates')}`，最大包：{summary.get('max_pack_size')}")
        lines.append(f"- fallback 原因分布：`{json.dumps(summary.get('fallback_reason_distribution') or {}, ensure_ascii=False)}`")
        lines.append(f"- 缺失规则 TopN：`{json.dumps(summary.get('missing_rule_topn') or [], ensure_ascii=False)}`")
        lines.append(f"- 低置信度规则 TopN：`{json.dumps(summary.get('low_confidence_rule_topn') or [], ensure_ascii=False)}`")
        lines.append(f"- 终态分布：`{json.dumps(summary.get('terminal_status_count') or {}, ensure_ascii=False)}`")
        lines.append("")
        lines.append("| bucket | 规则数 | selected pack size | 计划 pack 数 |")
        lines.append("| --- | ---: | ---: | ---: |")
        for bucket_key, detail in (summary.get("bucket_details") or {}).items():
            lines.append(
                f"| `{bucket_key}` | {detail.get('rule_count')} | "
                f"{detail.get('selected_pack_size')} | {detail.get('planned_pack_count')} |"
            )
        lines.append("")

    lines.append("## 说明")
    lines.append("")
    lines.append("- 本报告由旁路脚本生成，不创建正式批量任务，不写正式质控结果表。")
    lines.append("- `baseline_current` 用于暴露当前 `fixed_packs` 配置被归一化为 `domain_only` 的真实行为。")
    lines.append("- `partial_accept` 类策略中，合法返回规则先接收，只重试缺失、低置信度或解析失败规则。")
    lines.append("- `provider_error` 代表模型服务或网络异常，不应归因于规则组合本身。")
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now_stamp()
    json_path = output_dir / f"luxian_0609_pack_strategy_{stamp}.json"
    md_path = output_dir / f"luxian_0609_pack_strategy_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def parse_args() -> LabConfig:
    parser = argparse.ArgumentParser(description="泸县0609质控分桶策略旁路 POC")
    parser.add_argument("--visit-id", default=DEFAULT_VISIT_ID)
    parser.add_argument("--rule-set-key", default=DEFAULT_RULE_SET_KEY)
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    parser.add_argument("--output-dir", default=str(ROOT / ".runtime-logs" / "qc-pack-poc"))
    parser.add_argument("--low-confidence-threshold", type=float, default=0.45)
    parser.add_argument("--network-retry", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-rules", type=int, default=0, help="调试用；0 表示不限制规则数")
    args = parser.parse_args()
    return LabConfig(
        visit_id=str(args.visit_id),
        rule_set_key=str(args.rule_set_key),
        strategies=_normalize_strategy_list(str(args.strategies)),
        output_dir=Path(args.output_dir),
        low_confidence_threshold=float(args.low_confidence_threshold),
        dry_run=bool(args.dry_run),
        max_rules=max(0, int(args.max_rules)),
        network_retry=max(0, int(args.network_retry)),
    )


async def main_async() -> int:
    config = parse_args()
    lab = Luxian0609PackStrategyLab(config)
    report = await lab.run()
    json_path, md_path = write_report(report, config.output_dir)
    print(f"POC JSON: {json_path}")
    print(f"POC Markdown: {md_path}")
    print(f"recommended_strategy={report.get('recommended_strategy') or '-'}")
    for item in report.get("score_table") or []:
        print(
            f"{item.get('strategy')}: rank={item.get('rank') or '-'} "
            f"score={item.get('final_score')} elapsed_ms={item.get('elapsed_ms')} "
            f"tokens={item.get('tokens')} eliminated={item.get('eliminated')}"
        )
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
