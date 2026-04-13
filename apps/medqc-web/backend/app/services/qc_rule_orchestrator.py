from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Awaitable, Callable, Optional
import logging
import asyncio
import copy

from .programmatic_rule_executor import ProgrammaticRuleExecutor
from .qc_execution_cache import (
    QCExecutionCache,
    build_execution_cache_key,
    build_prompt_hash,
    build_record_snapshot_hash,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuleExecutionMeta:
    executor_type: str
    execution_domain: str
    doc_scope: str
    rule_version: str
    prompt_version: str
    cost_class: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidencePayload:
    primary_document_text: str
    supporting_documents: list[dict[str, Any]]
    timeline_facts: list[dict[str, Any]]
    document_hits: dict[str, Any]
    data_quality_flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProgrammaticExecutionResult:
    rule_id: str
    status: str
    is_compliant: bool
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrchestratedRuleResult:
    rule_id: str
    executor_type: str
    status: str
    is_compliant: bool
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


LLMEvaluateFn = Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]


def resolve_rule_execution_meta(rule: dict[str, Any]) -> RuleExecutionMeta:
    executor_type = str(rule.get("executor_type") or "llm").strip().lower()
    if executor_type not in {"llm", "program"}:
        executor_type = "llm"
    execution_domain = str(rule.get("execution_domain") or "generic").strip().lower() or "generic"
    doc_scope = str(rule.get("doc_scope") or "primary").strip().lower() or "primary"
    rule_version = str(rule.get("rule_version") or "v1").strip() or "v1"
    prompt_version = str(rule.get("prompt_version") or "v1").strip() or "v1"
    cost_class = str(rule.get("cost_class") or "standard").strip().lower() or "standard"
    return RuleExecutionMeta(
        executor_type=executor_type,
        execution_domain=execution_domain,
        doc_scope=doc_scope,
        rule_version=rule_version,
        prompt_version=prompt_version,
        cost_class=cost_class,
    )


class QCRuleOrchestrator:
    def __init__(self) -> None:
        self._program_executor = ProgrammaticRuleExecutor()

    async def evaluate_rules(
        self,
        *,
        rules: list[dict[str, Any]],
        medical_record: dict[str, Any],
        llm_evaluate: LLMEvaluateFn,
        evidence_source: str = "medical_text",
        llm_concurrency: int = 6,
        model_version: str = "",
        execution_cache: Optional[QCExecutionCache] = None,
        cache_ttl_seconds: int = 1800,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        trace: list[OrchestratedRuleResult] = []
        total_tokens = 0
        total_api_time = 0.0
        llm_count = 0
        program_count = 0
        llm_fallback_count = 0
        cache_hit_count = 0

        program_results: dict[int, dict[str, Any]] = {}
        cached_results: dict[int, tuple[dict[str, Any], RuleExecutionMeta, str]] = {}
        llm_buckets: dict[
            tuple[str, str],
            list[Awaitable[tuple[int, dict[str, Any], RuleExecutionMeta, bool]]],
        ] = {}

        max_concurrency = max(1, int(llm_concurrency or 1))
        semaphore = asyncio.Semaphore(max_concurrency)
        record_snapshot_hash = build_record_snapshot_hash(medical_record)

        async def run_llm_rule(
            idx: int,
            rule: dict[str, Any],
            meta: RuleExecutionMeta,
            is_fallback: bool,
        ) -> tuple[int, dict[str, Any], RuleExecutionMeta, bool]:
            async with semaphore:
                result = await llm_evaluate(rule, medical_record)
            return idx, result, meta, is_fallback

        for idx, rule in enumerate(rules):
            meta = resolve_rule_execution_meta(rule)
            executor_type = meta.executor_type
            can_program = executor_type == "program" and self._program_executor.can_execute(rule)
            cache_key = build_execution_cache_key(
                record_snapshot_hash=record_snapshot_hash,
                rule_id=str(rule.get("rule_id") or rule.get("rule_code") or ""),
                rule_version=meta.rule_version,
                prompt_hash=build_prompt_hash(rule),
                model_version=str(model_version or "unknown"),
            )

            if execution_cache is not None:
                cached = execution_cache.get(cache_key)
                if isinstance(cached, dict):
                    cached_results[idx] = (copy.deepcopy(cached), meta, cache_key)
                    cache_hit_count += 1
                    continue

            if can_program:
                program_count += 1
                program_results[idx] = self._program_executor.evaluate(
                    rule=rule,
                    medical_record=medical_record,
                    meta=meta.to_dict(),
                )
            else:
                is_fallback = executor_type == "program"
                if is_fallback:
                    llm_fallback_count += 1
                    logger.warning(
                        "规则 %s 标注为 program 但无程序化实现，已回退到 llm",
                        rule.get("rule_id"),
                    )
                llm_count += 1
                bucket_key = (meta.execution_domain, meta.doc_scope)
                llm_buckets.setdefault(bucket_key, []).append(
                    run_llm_rule(idx, rule, meta, is_fallback)
                )

        llm_results: dict[int, tuple[dict[str, Any], RuleExecutionMeta, bool]] = {}
        for tasks in llm_buckets.values():
            for idx, result, meta, is_fallback in await asyncio.gather(*tasks):
                llm_results[idx] = (result, meta, is_fallback)

        for idx, rule in enumerate(rules):
            cache_key = ""
            is_cache_hit = False
            llm_fallback = False
            if idx in cached_results:
                result, meta, cache_key = cached_results[idx]
                executor_type = str((result.get("metadata") or {}).get("executor_type") or resolve_rule_execution_meta(rule).executor_type)
                is_cache_hit = True
                llm_fallback = bool((result.get("metadata") or {}).get("llm_fallback") is True)
            elif idx in program_results:
                result = program_results[idx]
                meta = resolve_rule_execution_meta(rule)
                executor_type = "program"
            else:
                result, meta, is_fallback = llm_results[idx]
                executor_type = "llm"
                llm_fallback = bool(is_fallback)
                cache_key = build_execution_cache_key(
                    record_snapshot_hash=record_snapshot_hash,
                    rule_id=str(rule.get("rule_id") or rule.get("rule_code") or ""),
                    rule_version=meta.rule_version,
                    prompt_hash=build_prompt_hash(rule),
                    model_version=str(model_version or "unknown"),
                )

            metadata = dict(result.get("metadata") or {})
            metadata.setdefault("executor_type", executor_type)
            metadata.setdefault("rule_version", meta.rule_version)
            metadata.setdefault("prompt_version", meta.prompt_version)
            metadata.setdefault("cost_class", meta.cost_class)
            metadata.setdefault("execution_domain", meta.execution_domain)
            metadata.setdefault("doc_scope", meta.doc_scope)
            metadata.setdefault("evidence_source", evidence_source)
            metadata.setdefault("model_version", str(model_version or ""))
            metadata["llm_fallback"] = llm_fallback
            metadata["cache_hit"] = is_cache_hit
            metadata.setdefault("cache_key", cache_key)
            result["metadata"] = metadata

            if not is_cache_hit:
                total_tokens += int(metadata.get("tokens_used") or 0)
                total_api_time += float(metadata.get("api_time") or 0.0)
                if execution_cache is not None and cache_key:
                    execution_cache.set(
                        cache_key,
                        result,
                        ttl_seconds=cache_ttl_seconds,
                    )
            trace.append(
                OrchestratedRuleResult(
                    rule_id=str(result.get("rule_id") or rule.get("rule_id") or ""),
                    executor_type=str(metadata.get("executor_type") or "llm"),
                    status=str(result.get("status") or ""),
                    is_compliant=bool(result.get("is_compliant") is True),
                    metadata=metadata,
                )
            )
            results.append(result)

        return {
            "results": results,
            "total_tokens": total_tokens,
            "total_api_time": total_api_time,
            "executor_breakdown": {
                "program": program_count,
                "llm": llm_count,
                "llm_fallback": llm_fallback_count,
            },
            "cache_breakdown": {
                "hit": cache_hit_count,
                "miss": max(0, len(rules) - cache_hit_count),
            },
            "trace": [item.to_dict() for item in trace],
        }
