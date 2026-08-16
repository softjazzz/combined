"""历史单规则执行入口。

该模块只搬运 ``SichuanQCService.evaluate_rule_for_visit`` 的既有流程；
规则判定和运行时依赖仍由原服务实例拥有。
"""

from collections.abc import Callable
from typing import Any

from ..qc_cancellation import raise_if_cancelled
from ..rule_domain_router import (
    build_evidence_payload_from_rule_input,
    render_rule_execution_medical_text,
    route_rule_to_domain,
)


async def evaluate_legacy_rule_for_visit(
    host: Any,
    *,
    load_domain_bundle: Callable[..., dict[str, Any]],
    rule_id: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None = None,
    bundle_schema: str = "public",
    force_refresh_bundle: bool = False,
    cancellation_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """按既有语义执行一条历史四川质控规则。"""

    raise_if_cancelled(cancellation_check)
    rule = host.get_rule_by_id(str(rule_id or "").strip())
    if not rule:
        raise ValueError(f"规则不存在: {rule_id}")

    routing = route_rule_to_domain(rule)
    domain_bundle = load_domain_bundle(
        execution_domain=routing.execution_domain,
        institute_id=str(institute_id or "").strip(),
        patient_id=str(patient_id or "").strip(),
        visit_id=str(visit_id or "").strip(),
        source_schema=source_schema,
        bundle_schema=bundle_schema,
        force_refresh=force_refresh_bundle,
    )
    surgery_bundle: dict[str, Any] | None = None
    if str(rule.get("rule_id") or "").strip().upper() == "SC-146":
        surgery_bundle = load_domain_bundle(
            execution_domain="surgery",
            institute_id=str(institute_id or "").strip(),
            patient_id=str(patient_id or "").strip(),
            visit_id=str(visit_id or "").strip(),
            source_schema=source_schema,
            bundle_schema=bundle_schema,
            force_refresh=force_refresh_bundle,
        )

    try:
        rule_input = host._build_rule_execution_input_from_bundle(
            rule=rule,
            routing=routing,
            domain_bundle=domain_bundle,
        )
    except LookupError:
        return host._build_missing_primary_result(
            rule=rule,
            routing=routing,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            domain_bundle=domain_bundle,
        )

    normalized_rule_id = str(rule.get("rule_id") or "").strip().upper()
    if normalized_rule_id == "SC-070":
        consultation_bundle = load_domain_bundle(
            execution_domain="consult_discussion",
            institute_id=str(institute_id or "").strip(),
            patient_id=str(patient_id or "").strip(),
            visit_id=str(visit_id or "").strip(),
            source_schema=source_schema,
            bundle_schema=bundle_schema,
            force_refresh=force_refresh_bundle,
        )
        rule_input = host._merge_rule_input_with_bundle_documents(
            rule_input=rule_input,
            bundle=consultation_bundle,
            include_doc_types=("consultation_record",),
        )
    elif normalized_rule_id == "SC-146" and surgery_bundle is not None:
        rule_input = host._merge_rule_input_with_bundle_documents(
            rule_input=rule_input,
            bundle=surgery_bundle,
            include_doc_types=(
                "presurg_discussion",
                "presurg_summary",
                "anesthesia_record",
                "postsurg_firstcourse_record",
            ),
        )

    medical_text = render_rule_execution_medical_text(rule_input)
    raise_if_cancelled(cancellation_check)
    orchestrated = await host._evaluate_rules_orchestrated(
        document_id=f"{visit_id}:{rule.get('rule_id')}",
        content=medical_text,
        document_type=rule_input.document_type,
        rules=[rule],
        evidence_source="bundle",
        cancellation_check=cancellation_check,
    )
    orchestrated_results = list(orchestrated.get("results") or [])
    if not orchestrated_results:
        raise ValueError("规则执行失败：未返回结果")
    engine_result = host._apply_rule_text_only_fallbacks(
        rule_input=rule_input,
        engine_result=orchestrated_results[0],
        surgery_bundle=surgery_bundle,
    )

    evaluation_results = [
        {
            "rule_id": engine_result.get("rule_id"),
            "rule_name": engine_result.get("rule_name"),
            "is_compliant": engine_result.get("is_compliant"),
            "status": engine_result.get("status"),
            "findings": engine_result.get("findings"),
            "evidence": engine_result.get("evidence"),
            "suggestion": engine_result.get("suggestion"),
            "confidence": engine_result.get("confidence"),
            "applicability": engine_result.get("applicability"),
            "evidence_verified": engine_result.get("evidence_verified"),
            "evidence_items": engine_result.get("evidence_items"),
            "metadata": engine_result.get("metadata"),
        }
    ]
    status = str(engine_result.get("status") or "")
    not_applicable = 1 if status == "not_applicable" else 0
    compliant_rules = 1 if status in {"compliant", "not_applicable"} else 0
    issues_found = 1 if status == "non_compliant" else 0
    metadata = engine_result.get("metadata") or {}
    primary_source_document: dict[str, Any] = {}
    if list(rule_input.source_documents or []):
        primary_source_document = max(
            (dict(item) for item in list(rule_input.source_documents or [])),
            key=lambda item: host._score_primary_candidate_for_rule(
                rule_id=str(rule.get("rule_id") or rule.get("rule_code") or ""),
                candidate=item,
            ),
        )
    derived_signals = host._build_copy_content_similarity_signals(
        primary_document=primary_source_document,
        source_documents=[dict(item) for item in list(rule_input.source_documents or [])],
        rule_ids=[str(rule.get("rule_id") or rule.get("rule_code") or "")],
    )
    return {
        "document_id": visit_id,
        "document_type": rule_input.document_type,
        "total_rules": 1,
        "applicable_rules": [str(rule.get("rule_id") or "")],
        "evaluation_summary": {
            "compliance_rate": 100.0 if compliant_rules else 0.0,
            "issues_found": issues_found,
            "not_applicable": not_applicable,
            "total_rules": 1,
            "compliant_rules": compliant_rules,
            "model": host.client.model,
        },
        "parsed_evaluation_results": [engine_result],
        "evaluation_results": evaluation_results,
        "llm_output": engine_result.get("llm_raw_output"),
        "token_usage": {"total_tokens": int(metadata.get("tokens_used") or 0)},
        "api_time": float(metadata.get("api_time") or 0.0),
        "routing": routing.to_dict(),
        "rule_execution_input": rule_input.to_dict(),
        "evidence_payload": build_evidence_payload_from_rule_input(
            rule_input=rule_input,
            document_hits=domain_bundle.get("document_hits") or {},
            data_quality_flags=domain_bundle.get("data_quality_flags") or [],
            derived_signals=derived_signals,
        ).to_dict(),
        "executor_breakdown": orchestrated.get("executor_breakdown") or {},
        "cache_breakdown": orchestrated.get("cache_breakdown") or {},
        "pack_metrics": orchestrated.get("pack_metrics") or {},
        "trace": orchestrated.get("trace") or [],
        "bundle_metadata": {
            "execution_domain": routing.execution_domain,
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
            "document_hits": domain_bundle.get("document_hits") or {},
            "data_quality_flags": domain_bundle.get("data_quality_flags") or [],
            "bundle_schema_version": domain_bundle.get("bundle_schema_version") or "",
            "policy_version": domain_bundle.get("policy_version") or "",
        },
    }
