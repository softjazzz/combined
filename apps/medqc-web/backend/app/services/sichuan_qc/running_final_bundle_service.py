"""Running/Final Bundle 的正式编排实现。

公开门面仍由 SichuanQCService 提供；本模块只隐藏既有编排复杂度。
"""

import sys
from typing import Any, Callable, Dict, List, Optional

from ...core.settings import Settings
from ..effect_priority_qc import (
    BATCH_OUTPUT_MODE_FULL,
    DEFAULT_MAX_REFINE_CANDIDATES,
    DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
    QUALITY_PROFILE_THROUGHPUT,
)
from ..luxian_0609 import LUXIAN_0609_RULE_SET_KEY
from ..luxian_0609.privacy_request_scope import luxian_0609_privacy_scope
from ..luxian_0609.rule_decision_settings import ReadOnlySettingsOverlay
from ..luxian_0609.native_package import Luxian0609PackagePlan


def _resolve_facade_module(host: Any) -> Any:
    """沿 MRO 定位真正定义稳定门面的模块，避免子类模块误绑定。"""
    for cls in type(host).__mro__:
        facade = cls.__dict__.get("evaluate_running_final_bundle_input")
        facade_globals = getattr(facade, "__globals__", None)
        if not isinstance(facade_globals, dict):
            continue
        if (
            facade_globals.get("evaluate_running_final_bundle_input")
            is evaluate_running_final_bundle_input
        ):
            module = sys.modules.get(str(getattr(facade, "__module__", "") or ""))
            if module is not None:
                return module
    raise RuntimeError("无法定位 Running/Final Bundle 稳定门面定义模块")


@luxian_0609_privacy_scope
async def evaluate_running_final_bundle_input(
    host: Any,
    bundle: Dict[str, Any],
    *,
    rule_ids: Optional[List[str]] = None,
    bucket_strategy: str = "domain_only",
    quality_profile: str = QUALITY_PROFILE_THROUGHPUT,
    batch_output_mode: str = BATCH_OUTPUT_MODE_FULL,
    enable_selective_refine: bool = False,
    refine_confidence_threshold: float = DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
    max_refine_candidates: int = DEFAULT_MAX_REFINE_CANDIDATES,
    use_execution_cache: bool = True,
    enable_pack_probe: bool = False,
    rule_set_key: str = "",
    evaluation_as_of_date: str | None = None,
    evaluation_horizon_policy: str | None = None,
    evaluation_horizon_unavailable_reason: str | None = None,
    task_settings: Settings | ReadOnlySettingsOverlay | None = None,
    cancellation_check: Optional[Callable[[], bool]] = None,
    execution_trace_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    通过 running/final bundle 输入复用旧规则链入口（evaluate_document）。

    说明：
    - 不改规则引擎本体；
    - 仅做输入适配；
    - 仅支持 running/final 场景。
    """
    from ..qc_input_adapters import adapt_bundle_to_sichuan_eval_args
    from ..qc_input_adapters import extract_bundle_documents

    host_module = _resolve_facade_module(host)
    scene = str((bundle or {}).get("scene") or "").strip().lower()
    if scene not in {"running", "final"}:
        raise ValueError(f"仅支持 running/final bundle，当前 scene={scene or 'unknown'}")

    eval_args = adapt_bundle_to_sichuan_eval_args(bundle, rule_ids=rule_ids or [])
    document_id = str(eval_args["document_id"])
    document_type = str(eval_args["document_type"])
    content = str(eval_args["content"])
    resolved_rule_ids = list(eval_args.get("rule_ids") or [])
    evidence_payload = dict(eval_args.get("evidence_payload") or {})
    normalized_rule_set_key = str(rule_set_key or "").strip()
    quality_profile_normalized = host_module.normalize_quality_profile(quality_profile)
    settings = (
        task_settings
        if normalized_rule_set_key == LUXIAN_0609_RULE_SET_KEY
        and task_settings is not None
        else host_module.get_settings()
    )
    if normalized_rule_set_key == LUXIAN_0609_RULE_SET_KEY:
        if task_settings is None:
            settings = host_module.resolve_mainline_rule_decision_settings(settings)
        host_module.assert_luxian_0609_customer_native_delivery_ready(
            settings,
            context="evaluate_running_final_bundle_input",
        )
    package_plan: Luxian0609PackagePlan | None = None
    selected_customer_rule_ids: tuple[str, ...] | None = None
    if normalized_rule_set_key == LUXIAN_0609_RULE_SET_KEY and resolved_rule_ids:
        normalized_requested_ids = tuple(
            str(rule_id or "").strip().upper()
            for rule_id in resolved_rule_ids
            if str(rule_id or "").strip()
        )
        has_customer_ids = any(
            rule_id.startswith("LX0609-") for rule_id in normalized_requested_ids
        )
        if has_customer_ids:
            if not all(
                rule_id.startswith("LX0609-") for rule_id in normalized_requested_ids
            ):
                raise ValueError("LX0609 package entry does not accept mixed rule ids")
            selected_customer_rule_ids = normalized_requested_ids
            dependency_inventory = host_module.load_luxian_0609_dependency_inventory()
            if settings.LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED:
                package_plan = host_module.build_luxian_0609_package_plan_from_settings(
                    inventory=dependency_inventory,
                    selected_rule_ids=selected_customer_rule_ids,
                    settings=settings,
                )
                host_module.assert_luxian_0609_formal_package_plan_native_only(
                    package_plan,
                    context="evaluate_running_final_bundle_input",
                )
                resolved_rule_ids = list(
                    package_plan.compatibility_execution_rule_ids
                )
            else:
                resolved_rule_ids = list(
                    host_module.resolve_package_rollback_execution_rule_ids(
                        inventory=dependency_inventory,
                        selected_rule_ids=selected_customer_rule_ids,
                    )
                )

    selected_rules: List[Dict[str, Any]] = []
    if resolved_rule_ids:
        for rid in resolved_rule_ids:
            rule = host.get_rule_by_id(str(rid or "").strip())
            if rule:
                selected_rules.append(host._ensure_rule_execution_meta(rule))
    elif selected_customer_rule_ids is not None:
        # Native 客户规则没有 compatibility execution id，但仍必须保留
        # wrapper 供统一引擎聚合、渲染客户结果；否则 native 事实会被丢弃，
        # 工作台会退回成无逐事件事实的兼容/LLM 结果。
        customer_rules = host_module.load_luxian_0609_rules()
        selected_customer_ids = set(selected_customer_rule_ids)
        selected_rules = [
            # 纯 native 客户规则已经由正式执行计划选择；这里仅保留
            # wrapper 供统一聚合。不能再让旧宿主按 llm/program 兼容元数据
            # 归一化，否则 cross_document 会被错误观测为 llm。
            dict(rule)
            for rule in customer_rules
            if str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
            in selected_customer_ids
        ]
    elif selected_customer_rule_ids is None:
        selected_rules = await host._resolve_rules_for_document(
            document_type=document_type,
            rule_ids=resolved_rule_ids,
        )

    bundle_documents = [
        dict(item)
        for item in extract_bundle_documents(bundle)
        if str(item.get("content") or "").strip()
    ]

    luxian_context = None
    execution_rules = selected_rules
    if (
        normalized_rule_set_key == LUXIAN_0609_RULE_SET_KEY
        and settings.LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED
    ):
        source_gate_decisions: Dict[str, Any] = {}
        raw_source_schema = (bundle or {}).get("source_schema")
        source_schema = str(raw_source_schema).strip() if isinstance(raw_source_schema, str) else None
        if settings.LUXIAN_0609_TRIGGER_GATE_ENABLED:
            source_gate_decisions = host_module._build_luxian_0609_033_live_source_decisions(
                bundle=bundle,
                selected_rules=selected_rules,
                source_schema=source_schema or None,
                consent_document_present=host._has_luxian_0609_033_consent_document(
                    selected_rules=selected_rules,
                    bundle_documents=bundle_documents,
                ),
            )
        execution_rules, luxian_context = await host_module.prepare_luxian_0609_execution(
            rule_set_key=normalized_rule_set_key,
            prepared_rules=selected_rules,
            visit_id=str((bundle or {}).get("visit_id") or document_id or ""),
            medical_text=content,
            evidence_payload=evidence_payload,
            llm_client=host.adjudicator_client,
            settings=settings,
            source_gate_decisions=source_gate_decisions,
            institute_id=str((bundle or {}).get("institute_id") or ""),
            patient_id=str((bundle or {}).get("patient_id") or ""),
            source_schema=source_schema or None,
            evaluation_as_of_date=evaluation_as_of_date,
            evaluation_horizon_policy=evaluation_horizon_policy,
            evaluation_horizon_snapshot=(bundle or {}).get("evaluation_horizon_snapshot"),
            evaluation_horizon_unavailable_reason=(
                evaluation_horizon_unavailable_reason
            ),
            selected_customer_rule_ids=selected_customer_rule_ids,
            **({"prepared_package_plan": package_plan} if package_plan is not None else {}),
            trace_sink=execution_trace_sink,
        )

    if not execution_rules and luxian_context is not None:
        orchestrated = {
            "results": [],
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_api_time": 0.0,
            "executor_breakdown": {},
            "cache_breakdown": {},
            "pack_metrics": {},
            "trace": [],
            "refine_details": [],
            "refine_summary": {},
        }
    elif not execution_rules or not bundle_documents:
        orchestrated = await host._evaluate_rules_orchestrated(
            document_id=document_id,
            content=content,
            document_type=document_type,
            rules=execution_rules,
            evidence_source="bundle",
            evidence_payload=evidence_payload,
            bucket_strategy=bucket_strategy,
            quality_profile=quality_profile,
            batch_output_mode=batch_output_mode,
            enable_selective_refine=enable_selective_refine,
            refine_confidence_threshold=refine_confidence_threshold,
            max_refine_candidates=max_refine_candidates,
            use_execution_cache=use_execution_cache,
            enable_pack_probe=enable_pack_probe,
            force_rule_family_buckets=normalized_rule_set_key == LUXIAN_0609_RULE_SET_KEY,
            rule_set_key="" if luxian_context is not None else rule_set_key,
            cancellation_check=cancellation_check,
        )
    else:
        grouped_rules: Dict[str, Dict[str, Any]] = {}
        result_items: List[Dict[str, Any]] = []
        total_tokens = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_api_time = 0.0
        executor_breakdown_list: List[Dict[str, Any]] = []
        cache_breakdown_list: List[Dict[str, Any]] = []
        trace_items: List[Any] = []
        pack_metrics_list: List[Dict[str, Any]] = []
        refine_details: List[Dict[str, Any]] = []
        refine_candidate_count = 0
        refine_failed_count = 0
        refine_reasons_agg: Dict[str, int] = {}

        for rule in execution_rules:
            host_module.raise_if_cancelled(cancellation_check)
            matched_document = host._select_bundle_document_for_rule(
                rule=rule,
                bundle_documents=bundle_documents,
            )
            if matched_document is None:
                result_items.append(
                    host._build_bundle_missing_doc_result_item(
                        rule=rule,
                        bucket_strategy=bucket_strategy,
                        quality_profile=quality_profile_normalized,
                    )
                )
                continue
            doc_key = str(matched_document.get("id") or matched_document.get("document_type") or "")
            slot = grouped_rules.setdefault(
                doc_key,
                {
                    "document": matched_document,
                    "rules": [],
                },
            )
            slot["rules"].append(rule)

        for slot in grouped_rules.values():
            host_module.raise_if_cancelled(cancellation_check)
            primary_document = dict(slot.get("document") or {})
            primary_content = str(primary_document.get("content") or "").strip()
            primary_type = str(primary_document.get("document_type") or document_type or "病程记录")
            per_doc_evidence_payload = host._build_bundle_evidence_payload_for_document(
                primary_document=primary_document,
                all_documents=bundle_documents,
                bundle=bundle,
                rules=list(slot.get("rules") or []),
            )
            per_doc_orchestrated = await host._evaluate_rules_orchestrated(
                document_id=f"{document_id}:{primary_document.get('source_table') or primary_type}",
                content=primary_content,
                document_type=primary_type,
                rules=list(slot.get("rules") or []),
                evidence_source="bundle",
                evidence_payload=per_doc_evidence_payload,
                bucket_strategy=bucket_strategy,
                quality_profile=quality_profile,
                batch_output_mode=batch_output_mode,
                enable_selective_refine=enable_selective_refine,
                refine_confidence_threshold=refine_confidence_threshold,
                max_refine_candidates=max_refine_candidates,
                use_execution_cache=use_execution_cache,
                enable_pack_probe=enable_pack_probe,
                force_rule_family_buckets=normalized_rule_set_key == LUXIAN_0609_RULE_SET_KEY,
                cancellation_check=cancellation_check,
            )
            result_items.extend(list(per_doc_orchestrated.get("results") or []))
            total_tokens += int(per_doc_orchestrated.get("total_tokens") or 0)
            total_prompt_tokens += int(per_doc_orchestrated.get("total_prompt_tokens") or 0)
            total_completion_tokens += int(per_doc_orchestrated.get("total_completion_tokens") or 0)
            total_api_time += float(per_doc_orchestrated.get("total_api_time") or 0.0)
            executor_breakdown_list.append(dict(per_doc_orchestrated.get("executor_breakdown") or {}))
            cache_breakdown_list.append(dict(per_doc_orchestrated.get("cache_breakdown") or {}))
            trace_items.extend(list(per_doc_orchestrated.get("trace") or []))
            pack_metrics_list.append(dict(per_doc_orchestrated.get("pack_metrics") or {}))
            refine_details.extend(list(per_doc_orchestrated.get("refine_details") or []))
            refine_summary = dict(per_doc_orchestrated.get("refine_summary") or {})
            refine_candidate_count += int(refine_summary.get("candidate_count") or 0)
            refine_failed_count += int(refine_summary.get("refine_failed_count") or 0)
            for reason, count in dict(refine_summary.get("refine_reasons") or {}).items():
                refine_reasons_agg[str(reason)] = int(refine_reasons_agg.get(str(reason), 0)) + int(count or 0)

        orchestrated = {
            "results": result_items,
            "total_tokens": total_tokens,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_api_time": total_api_time,
            "executor_breakdown": host._sum_counter_dicts(executor_breakdown_list),
            "cache_breakdown": host._sum_counter_dicts(cache_breakdown_list),
            "pack_metrics": host._merge_pack_metrics(
                pack_metrics_list,
                quality_profile=quality_profile_normalized,
                bucket_strategy=bucket_strategy,
            ),
            "quality_profile": quality_profile_normalized,
            "refine_details": refine_details,
            "trace": trace_items,
            "refine_summary": {
                "enabled": enable_selective_refine,
                "candidate_count": refine_candidate_count,
                "eligible_candidate_count": refine_candidate_count,
                "refined_rule_count": sum(1 for item in result_items if bool((item.get("metadata") or {}).get("refined"))),
                "refine_failed_count": refine_failed_count,
                "budget_applied": max_refine_candidates,
                "budget_skipped_count": 0,
                "refine_reasons": refine_reasons_agg,
            },
            "refined_rule_count": sum(1 for item in result_items if bool((item.get("metadata") or {}).get("refined"))),
            "refine_reasons": refine_reasons_agg,
        }
    if luxian_context is not None:
        model_version = str(getattr(getattr(host, "client", None), "model", "") or "")
        host_module.aggregate_luxian_0609_orchestrated_results(
            orchestrated=orchestrated,
            context=luxian_context,
            visit_id=str((bundle or {}).get("visit_id") or document_id or ""),
            model_name=model_version,
            evidence_payload=evidence_payload,
            execution_rule_count=len(selected_customer_rule_ids or selected_rules),
        )
    result = host._build_document_evaluation_result(
        document_id=document_id,
        document_type="终末病历" if scene == "final" else "运行病历",
        rules=selected_rules,
        orchestrated=orchestrated,
    )
    result["bundle_metadata"] = {
        "scene": scene,
        "visit_id": str((bundle or {}).get("visit_id") or ""),
        "policy_version": str((bundle or {}).get("policy_version") or ""),
        "bundle_schema_version": str((bundle or {}).get("bundle_schema_version") or ""),
        "document_hits": (bundle or {}).get("document_hits") or {},
        "text_available": bool((bundle or {}).get("text_available")),
        "adapter_version": str((eval_args.get("metadata") or {}).get("adapter_version") or ""),
        "compat_strategy": str((eval_args.get("metadata") or {}).get("compat_strategy") or ""),
    }
    if normalized_rule_set_key != LUXIAN_0609_RULE_SET_KEY:
        result["evidence_payload"] = evidence_payload
    return result
