from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from ...core.execution_timing import timed

from ...database.connection import engine
from ..bundles import load_or_assemble_scene_bundle
from ..sichuan_qc_service import SichuanQCService
from .running_final_bundle_adapter import adapt_bundle_to_sichuan_eval_args

_SCENE_TABLE = {
    "running": "running_record_bundle",
    "final": "final_record_bundle",
}


def _normalize_scene(scene: str) -> str:
    value = str(scene or "").strip().lower()
    if value not in _SCENE_TABLE:
        raise ValueError(f"Unsupported bundle scene: {scene}")
    return value


def _loads_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return {} if value != [] else []
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


@timed("bundle_read")
def load_running_final_bundle(
    *,
    scene: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    schema: str = "public",
) -> dict[str, Any]:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; bundle loading unavailable.")
    normalized_scene = _normalize_scene(scene)
    payload = load_or_assemble_scene_bundle(
        scene=normalized_scene,
        institute_id=str(institute_id or "").strip(),
        patient_id=str(patient_id or "").strip(),
        visit_id=str(visit_id or "").strip(),
        bundle_schema=schema,
        force_refresh=False,
        force_refresh_if_empty=True,
    )
    if not payload:
        raise LookupError(f"Bundle not found: {normalized_scene} {institute_id}/{patient_id}/{visit_id}")

    payload["structured_context"] = _loads_json(payload.get("structured_context"))
    payload["document_hits"] = _loads_json(payload.get("document_hits"))
    payload["data_quality_flags"] = _loads_json(payload.get("data_quality_flags"))
    payload["source_doc_priority"] = _loads_json(payload.get("source_doc_priority"))
    return payload


async def evaluate_running_final_bundle(
    *,
    qc_service: SichuanQCService,
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
    if isinstance(bundle_input, dict) and bundle_input:
        bundle = dict(bundle_input)
    else:
        if not all([scene, institute_id, patient_id, visit_id]):
            raise ValueError("未提供 bundle_input 时，scene/institute_id/patient_id/visit_id 必填")
        bundle = load_running_final_bundle(
            scene=str(scene),
            institute_id=str(institute_id),
            patient_id=str(patient_id),
            visit_id=str(visit_id),
            schema=schema,
        )

    # Adapter-first unified path: always bridge bundle -> legacy evaluate_document.
    result = await qc_service.evaluate_running_final_bundle_input(
        bundle=bundle,
        rule_ids=list(rule_ids or []),
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
    eval_args = adapt_bundle_to_sichuan_eval_args(bundle, rule_ids=rule_ids or [])
    result["bundle_metadata"] = {
        "scene": bundle.get("scene"),
        "visit_id": bundle.get("visit_id"),
        "policy_version": bundle.get("policy_version"),
        "bundle_schema_version": bundle.get("bundle_schema_version"),
        "document_hits": bundle.get("document_hits"),
        "text_available": bundle.get("text_available"),
        "bundle_updated_at": str(bundle.get("bundle_updated_at") or ""),
    }
    return result
