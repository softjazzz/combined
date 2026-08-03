"""
QC input adapters.

This package bridges new bundle payloads to legacy QC service inputs
without changing existing rule engines.
"""

from collections.abc import Callable
from typing import Any

from .running_final_bundle_adapter import (
    adapt_bundle_to_qc_service_payload,
    adapt_bundle_to_sichuan_eval_args,
    extract_bundle_documents,
)


def load_running_final_bundle(
    *,
    scene: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    schema: str = "public",
) -> dict[str, Any]:
    """按需加载含数据库依赖的 runtime，pure adapter 导入保持无副作用。"""

    from .running_final_bundle_runtime import load_running_final_bundle as _load

    return _load(
        scene=scene,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        schema=schema,
    )


async def evaluate_running_final_bundle(
    *,
    qc_service: Any,
    scene: str | None = None,
    institute_id: str | None = None,
    patient_id: str | None = None,
    visit_id: str | None = None,
    bundle_input: dict[str, Any] | None = None,
    rule_ids: list[str] | None = None,
    schema: str = "public",
    bucket_strategy: str = "domain_only",
    quality_profile: str = "throughput_v1",
    batch_output_mode: str = "full",
    enable_selective_refine: bool = False,
    refine_confidence_threshold: float = 0.75,
    max_refine_candidates: int = 3,
    use_execution_cache: bool = True,
    rule_set_key: str = "",
    evaluation_as_of_date: str | None = None,
    cancellation_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """保持原调用签名，仅在实际执行时加载旧 runtime。"""

    from .running_final_bundle_runtime import evaluate_running_final_bundle as _evaluate

    return await _evaluate(
        qc_service=qc_service,
        scene=scene,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        bundle_input=bundle_input,
        rule_ids=rule_ids,
        schema=schema,
        bucket_strategy=bucket_strategy,
        quality_profile=quality_profile,
        batch_output_mode=batch_output_mode,
        enable_selective_refine=enable_selective_refine,
        refine_confidence_threshold=refine_confidence_threshold,
        max_refine_candidates=max_refine_candidates,
        use_execution_cache=use_execution_cache,
        rule_set_key=rule_set_key,
        evaluation_as_of_date=evaluation_as_of_date,
        cancellation_check=cancellation_check,
    )

__all__ = [
    "adapt_bundle_to_qc_service_payload",
    "adapt_bundle_to_sichuan_eval_args",
    "extract_bundle_documents",
    "load_running_final_bundle",
    "evaluate_running_final_bundle",
]
