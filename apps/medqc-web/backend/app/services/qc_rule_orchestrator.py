from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Awaitable, Callable, Optional, Sequence
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
LLMBatchEvaluateFn = Callable[
    [list[dict[str, Any]], dict[str, Any], dict[str, Any]],
    Awaitable[dict[str, Any]],
]

DEFAULT_PACK_CANDIDATES: tuple[int, ...] = (3, 5, 8, 10, 12, 15)
LOW_CONFIDENCE_THRESHOLD = 0.45


def _rule_identity(rule: dict[str, Any]) -> str:
    return str(rule.get("rule_id") or rule.get("rule_code") or rule.get("id") or "").strip().upper()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


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
        llm_batch_evaluate: Optional[LLMBatchEvaluateFn] = None,
        prompt_strategy: str = "single_rule_v1",
        batch_pack_candidates: Optional[Sequence[int]] = None,
        batch_pack_max_size: int = 15,
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
        prompt_strategy_normalized = str(prompt_strategy or "single_rule_v1").strip().lower() or "single_rule_v1"

        program_results: dict[int, dict[str, Any]] = {}
        cached_results: dict[int, tuple[dict[str, Any], RuleExecutionMeta, str]] = {}
        llm_buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
        llm_results: dict[int, tuple[dict[str, Any], RuleExecutionMeta, bool]] = {}
        pack_metrics = {
            "prompt_strategy": prompt_strategy_normalized,
            "total_packs": 0,
            "avg_pack_size": 0.0,
            "fallback_packs": 0,
            "single_rule_retries": 0,
            "pack_parse_retry_count": 0,
            "pack_fallback_count": 0,
            "pack_parse_failures": 0,
            "context_tokens_estimate": 0,
            "probe_calls": 0,
            "selected_pack_size": 1,
            "selected_pack_size_by_bucket": {},
        }
        pack_size_sum = 0
        context_tokens_sum = 0
        pack_call_counter = 0

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

        async def run_llm_pack(
            pack_rules: list[dict[str, Any]],
            *,
            options: dict[str, Any],
        ) -> dict[str, Any]:
            if llm_batch_evaluate is None:
                raise RuntimeError("llm_batch_evaluate 未配置")
            async with semaphore:
                return await llm_batch_evaluate(pack_rules, medical_record, options)

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
                    {
                        "idx": idx,
                        "rule": rule,
                        "meta": meta,
                        "is_fallback": is_fallback,
                    }
                )

        async def _run_single_entry(
            entry: dict[str, Any],
            *,
            force_pack_fallback: bool = False,
        ) -> None:
            idx = int(entry["idx"])
            rule = dict(entry["rule"])
            meta = entry["meta"]
            is_fallback = bool(entry.get("is_fallback") is True or force_pack_fallback)
            single_result = await run_llm_rule(idx, rule, meta, is_fallback)
            single_payload = dict(single_result[1] or {})
            if force_pack_fallback:
                metadata = dict(single_payload.get("metadata") or {})
                metadata["prompt_strategy"] = prompt_strategy_normalized
                metadata["pack_size"] = 1
                metadata["pack_fallback"] = True
                metadata["pack_id"] = f"single-fallback-{idx}"
                single_payload["metadata"] = metadata
            llm_results[idx] = (single_payload, meta, is_fallback)

        async def _accept_pack_results(
            entries: list[dict[str, Any]],
            response: dict[str, Any],
            *,
            pack_id: str,
            pack_size: int,
            force_pack_fallback: bool,
        ) -> bool:
            nonlocal total_tokens, total_api_time, pack_size_sum, context_tokens_sum
            response_items = list(response.get("results") or [])
            expected_keys: dict[str, dict[str, Any]] = {}
            for entry in entries:
                expected_keys[_rule_identity(entry["rule"])] = entry

            parsed_by_rule: dict[str, dict[str, Any]] = {}
            for item in response_items:
                key = _rule_identity(item)
                if key and key in expected_keys and key not in parsed_by_rule:
                    parsed_by_rule[key] = dict(item)

            missing_rule_ids = {
                str(item).strip().upper()
                for item in (response.get("missing_rule_ids") or [])
                if str(item).strip()
            }
            missing_rule_ids.update(set(expected_keys.keys()) - set(parsed_by_rule.keys()))

            low_confidence_rule_ids = {
                str(item).strip().upper()
                for item in (response.get("low_confidence_rule_ids") or [])
                if str(item).strip()
            }
            parse_error = bool(response.get("parse_error") is True)
            if parse_error or missing_rule_ids or low_confidence_rule_ids:
                return False

            tokens_used = _safe_int(response.get("tokens_used"))
            api_time = _safe_float(response.get("api_time"))
            context_tokens = _safe_int(response.get("context_tokens_estimate"))
            total_tokens += tokens_used
            total_api_time += api_time
            pack_metrics["total_packs"] = int(pack_metrics.get("total_packs") or 0) + 1
            pack_size_sum += int(pack_size or len(entries))
            context_tokens_sum += context_tokens

            for key, entry in expected_keys.items():
                idx = int(entry["idx"])
                meta = entry["meta"]
                rule_result = parsed_by_rule.get(key) or {}
                metadata = dict(rule_result.get("metadata") or {})
                metadata.setdefault("tokens_used", _safe_int(tokens_used / max(1, len(entries))))
                metadata.setdefault("api_time", _safe_float(api_time / max(1, len(entries))))
                metadata["prompt_strategy"] = prompt_strategy_normalized
                metadata["pack_size"] = int(pack_size or len(entries))
                metadata["pack_id"] = pack_id
                metadata["pack_fallback"] = bool(force_pack_fallback)
                metadata["context_tokens_estimate"] = context_tokens
                rule_result["metadata"] = metadata
                llm_results[idx] = (rule_result, meta, bool(entry.get("is_fallback") is True))
            return True

        async def _execute_pack(
            entries: list[dict[str, Any]],
            *,
            pack_size: int,
            pack_id_prefix: str,
            bucket_key: tuple[str, str] = ("generic", "primary"),
            force_pack_fallback: bool = False,
        ) -> None:
            nonlocal pack_call_counter, total_tokens, total_api_time
            if not entries:
                return
            if len(entries) == 1 and llm_batch_evaluate is None:
                await _run_single_entry(entries[0], force_pack_fallback=force_pack_fallback)
                return

            if llm_batch_evaluate is None:
                await asyncio.gather(*[_run_single_entry(entry, force_pack_fallback=force_pack_fallback) for entry in entries])
                return

            pack_call_counter += 1
            pack_id = f"{pack_id_prefix}-{pack_call_counter}"
            response: dict[str, Any] = {}
            try:
                response = await run_llm_pack(
                    [dict(item["rule"]) for item in entries],
                    options={
                        "pack_id": pack_id,
                        "pack_size": int(pack_size or len(entries)),
                        "prompt_strategy": prompt_strategy_normalized,
                        "execution_domain": str(bucket_key[0] or "generic"),
                        "doc_scope": str(bucket_key[1] or "primary"),
                        "model_version": str(model_version or ""),
                        "mode": "execute",
                    },
                )
            except Exception:
                logger.warning("规则分包执行失败，触发回退: pack_id=%s", pack_id, exc_info=True)
                response = {
                    "results": [],
                    "parse_error": True,
                    "missing_rule_ids": [_rule_identity(item["rule"]) for item in entries],
                    "low_confidence_rule_ids": [],
                }

            accepted = await _accept_pack_results(
                entries,
                response,
                pack_id=pack_id,
                pack_size=pack_size,
                force_pack_fallback=force_pack_fallback,
            )
            if accepted:
                return

            pack_metrics["pack_parse_retry_count"] = int(pack_metrics.get("pack_parse_retry_count") or 0) + 1
            pack_metrics["pack_fallback_count"] = int(pack_metrics.get("pack_fallback_count") or 0) + 1
            pack_metrics["pack_parse_failures"] = int(pack_metrics.get("pack_parse_failures") or 0) + 1

            if len(entries) <= 1:
                pack_metrics["single_rule_retries"] = int(pack_metrics.get("single_rule_retries") or 0) + 1
                await _run_single_entry(entries[0], force_pack_fallback=True)
                return

            pack_metrics["fallback_packs"] = int(pack_metrics.get("fallback_packs") or 0) + 1
            mid = max(1, len(entries) // 2)
            await _execute_pack(
                entries[:mid],
                pack_size=max(1, min(pack_size, mid)),
                pack_id_prefix=f"{pack_id}-L",
                bucket_key=bucket_key,
                force_pack_fallback=True,
            )
            await _execute_pack(
                entries[mid:],
                pack_size=max(1, min(pack_size, len(entries) - mid)),
                pack_id_prefix=f"{pack_id}-R",
                bucket_key=bucket_key,
                force_pack_fallback=True,
            )

        async def _probe_best_pack_size(
            entries: list[dict[str, Any]],
            *,
            bucket_key: tuple[str, str] = ("generic", "primary"),
        ) -> int:
            nonlocal total_tokens, total_api_time
            if llm_batch_evaluate is None:
                return 1
            if not entries:
                return 1

            candidate_raw = list(batch_pack_candidates or DEFAULT_PACK_CANDIDATES)
            normalized_candidates: list[int] = []
            max_pack_size = max(1, int(batch_pack_max_size or 1))
            for candidate in candidate_raw:
                value = max(1, int(candidate))
                if value <= max_pack_size and value <= len(entries) and value not in normalized_candidates:
                    normalized_candidates.append(value)
            if not normalized_candidates:
                return min(len(entries), max_pack_size)
            normalized_candidates.sort(reverse=True)

            probe_pool = entries[: min(len(entries), max(normalized_candidates))]
            selected = normalized_candidates[-1]
            for candidate in normalized_candidates:
                probe_rules = [dict(item["rule"]) for item in probe_pool[:candidate]]
                pack_metrics["probe_calls"] = int(pack_metrics.get("probe_calls") or 0) + 1
                try:
                    probe_response = await run_llm_pack(
                        probe_rules,
                        options={
                            "pack_id": f"probe-{bucket_key[0]}-{bucket_key[1]}-{candidate}",
                            "pack_size": candidate,
                            "prompt_strategy": prompt_strategy_normalized,
                            "execution_domain": str(bucket_key[0] or "generic"),
                            "doc_scope": str(bucket_key[1] or "primary"),
                            "model_version": str(model_version or ""),
                            "mode": "probe",
                        },
                    )
                except Exception:
                    logger.warning("规则分包探测失败，候选大小=%s", candidate, exc_info=True)
                    continue

                total_tokens += _safe_int(probe_response.get("tokens_used"))
                total_api_time += _safe_float(probe_response.get("api_time"))
                missing_rule_ids = probe_response.get("missing_rule_ids") or []
                parse_error = bool(probe_response.get("parse_error") is True)
                low_confidence = probe_response.get("low_confidence_rule_ids") or []
                if parse_error or missing_rule_ids:
                    continue
                if low_confidence and len(low_confidence) >= max(1, candidate // 2):
                    continue
                selected = candidate
                break
            return max(1, selected)

        use_batch_mode = (
            prompt_strategy_normalized == "batch_compact_v1"
            and llm_batch_evaluate is not None
            and llm_count > 0
        )

        if use_batch_mode:
            selected_by_bucket: dict[str, int] = {}
            max_selected_pack_size = 1

            for bucket_key, bucket_entries in llm_buckets.items():
                if not bucket_entries:
                    continue

                selected_pack_size = await _probe_best_pack_size(
                    bucket_entries,
                    bucket_key=bucket_key,
                )
                max_selected_pack_size = max(max_selected_pack_size, int(selected_pack_size))
                bucket_metric_key = f"{bucket_key[0]}::{bucket_key[1]}"
                selected_by_bucket[bucket_metric_key] = int(selected_pack_size)

                chunk_size = max(1, min(int(selected_pack_size), len(bucket_entries)))
                for start in range(0, len(bucket_entries), chunk_size):
                    chunk = bucket_entries[start : start + chunk_size]
                    await _execute_pack(
                        chunk,
                        pack_size=chunk_size,
                        pack_id_prefix=f"pack-{bucket_key[0]}-{bucket_key[1]}",
                        bucket_key=bucket_key,
                    )

            pack_metrics["selected_pack_size"] = int(max_selected_pack_size)
            pack_metrics["selected_pack_size_by_bucket"] = selected_by_bucket
        else:
            llm_tasks: list[Awaitable[tuple[int, dict[str, Any], RuleExecutionMeta, bool]]] = []
            for entries in llm_buckets.values():
                for entry in entries:
                    llm_tasks.append(
                        run_llm_rule(
                            int(entry["idx"]),
                            dict(entry["rule"]),
                            entry["meta"],
                            bool(entry.get("is_fallback") is True),
                        )
                    )
            for idx, result, meta, is_fallback in await asyncio.gather(*llm_tasks):
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
            metadata.setdefault("prompt_strategy", prompt_strategy_normalized)
            metadata.setdefault("pack_size", int(metadata.get("pack_size") or 1))
            metadata.setdefault("pack_id", "")
            metadata.setdefault("pack_fallback", bool(metadata.get("pack_fallback") is True))
            metadata.setdefault("context_tokens_estimate", _safe_int(metadata.get("context_tokens_estimate")))
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

        total_packs = int(pack_metrics.get("total_packs") or 0)
        pack_metrics["avg_pack_size"] = round((pack_size_sum / total_packs), 2) if total_packs else 0.0
        pack_metrics["context_tokens_estimate"] = int(context_tokens_sum / total_packs) if total_packs else 0

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
            "pack_metrics": pack_metrics,
            "trace": [item.to_dict() for item in trace],
        }
