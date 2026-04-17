from __future__ import annotations

import asyncio
import csv
import json
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from sqlalchemy import text

from ..database.connection import engine
from .sc_rule_family import DEFAULT_RULE_FAMILY
from .sichuan_qc_service import SichuanQCService

SC_RULE_FAMILY_POC_COHORTS: tuple[str, ...] = (
    "running_admission_course",
    "running_surgery",
    "running_consult_or_discussion",
    "final_terminal",
)
DEFAULT_COHORT_SIZE = 10
DEFAULT_REPLAY_ROUNDS = 2
LOW_CONFIDENCE_THRESHOLD = 0.45

_RUNNING_SCENE_TABLE = "running_record_bundle"
_FINAL_SCENE_TABLE = "final_record_bundle"
_RUNNING_ADMISSION_DOCS = {
    "admission_record",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
    "summary_record",
    "transfer_in_record",
    "transfer_out_record",
    "newborn_record",
}
_RUNNING_SURGERY_DOCS = {
    "presurg_summary",
    "presurg_discussion",
    "surgery_record",
    "anesthesia_record",
    "postsurg_firstcourse_record",
    "surgery_safecheck_record",
    "surgery_risk_assessment",
}
_RUNNING_CONSULT_DOCS = {
    "consultation_record",
    "diffcase_discussion_record",
    "death_discussion",
    "handoff_record",
    "handover_record",
}
_FINAL_TERMINAL_DOCS = {
    "discharge_record",
    "death_record",
}
_COHORT_DONOR_ORDER: dict[str, tuple[str, ...]] = {
    "running_admission_course": ("running_consult_or_discussion", "running_surgery"),
    "running_surgery": ("running_admission_course", "running_consult_or_discussion"),
    "running_consult_or_discussion": ("running_admission_course", "running_surgery"),
    "final_terminal": (),
}
_STATUS_ORDER = {
    "non_compliant": 0,
    "uncertain": 1,
    "compliant": 2,
    "not_applicable": 3,
    "failed": 4,
    "missing": 5,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loads_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _bucket_metric_value(pack_metrics: dict[str, Any], field_name: str) -> float:
    if field_name == "avg_pack_size":
        return _safe_float(pack_metrics.get(field_name))
    return float(_safe_int(pack_metrics.get(field_name)))


def _truncate_text(value: Any, limit: int = 320) -> str:
    text_value = str(value or "").strip()
    if len(text_value) <= limit:
        return text_value
    return f"{text_value[:limit]}..."


def _manifest_key(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("institute_id") or "").strip(),
        str(entry.get("patient_id") or "").strip(),
        str(entry.get("visit_id") or "").strip(),
    )


def classify_scene_bundle_cohort(
    *,
    scene: str,
    document_hits: dict[str, Any],
    source_doc_priority: list[Any] | None = None,
) -> str | None:
    normalized_scene = str(scene or "").strip().lower()
    hit_map = {str(key): bool(value) for key, value in dict(document_hits or {}).items()}
    priority_docs = {str(item) for item in list(source_doc_priority or []) if str(item).strip()}

    if normalized_scene == "final":
        if any(hit_map.get(doc) or doc in priority_docs for doc in _FINAL_TERMINAL_DOCS):
            return "final_terminal"
        return None

    if normalized_scene != "running":
        return None

    if any(hit_map.get(doc) or doc in priority_docs for doc in _RUNNING_SURGERY_DOCS):
        return "running_surgery"
    if any(hit_map.get(doc) or doc in priority_docs for doc in _RUNNING_CONSULT_DOCS):
        return "running_consult_or_discussion"
    if any(hit_map.get(doc) or doc in priority_docs for doc in _RUNNING_ADMISSION_DOCS):
        return "running_admission_course"
    return None


def _bundle_richness_score(row: dict[str, Any]) -> tuple[int, int, str]:
    hit_map = dict(row.get("document_hits") or {})
    hit_count = sum(1 for value in hit_map.values() if bool(value))
    priority_count = len([item for item in list(row.get("source_doc_priority") or []) if str(item).strip()])
    updated_at = str(row.get("bundle_updated_at") or "")
    return (hit_count, priority_count, updated_at)


def _normalize_manifest_row(row: dict[str, Any]) -> dict[str, Any]:
    document_hits = _loads_json(row.get("document_hits"))
    source_doc_priority = _loads_json(row.get("source_doc_priority"))
    if not isinstance(document_hits, dict):
        document_hits = {}
    if not isinstance(source_doc_priority, list):
        source_doc_priority = []
    normalized = {
        "institute_id": str(row.get("institute_id") or "").strip(),
        "patient_id": str(row.get("patient_id") or "").strip(),
        "visit_id": str(row.get("visit_id") or "").strip(),
        "scene": str(row.get("scene") or "").strip().lower(),
        "document_hits": document_hits,
        "source_doc_priority": [str(item) for item in source_doc_priority if str(item).strip()],
        "bundle_updated_at": str(row.get("bundle_updated_at") or ""),
    }
    normalized["cohort_tag"] = classify_scene_bundle_cohort(
        scene=normalized["scene"],
        document_hits=normalized["document_hits"],
        source_doc_priority=normalized["source_doc_priority"],
    )
    return normalized


def select_manifest_entries(
    candidates: list[dict[str, Any]],
    *,
    cohort_size: int = DEFAULT_COHORT_SIZE,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw_row in candidates:
        cohort_tag = str(raw_row.get("cohort_tag") or "").strip()
        if cohort_tag not in SC_RULE_FAMILY_POC_COHORTS:
            continue
        grouped[cohort_tag].append(dict(raw_row))

    for cohort_tag in grouped:
        grouped[cohort_tag].sort(
            key=lambda item: _bundle_richness_score(item),
            reverse=True,
        )

    selected: list[dict[str, Any]] = []
    used_keys: set[tuple[str, str, str]] = set()

    def _pick_from_group(group_name: str, remaining: int) -> list[dict[str, Any]]:
        picked: list[dict[str, Any]] = []
        for item in grouped.get(group_name, []):
            key = _manifest_key(item)
            if key in used_keys:
                continue
            picked.append(item)
            used_keys.add(key)
            if len(picked) >= remaining:
                break
        return picked

    for cohort_tag in SC_RULE_FAMILY_POC_COHORTS:
        remaining = max(0, int(cohort_size or DEFAULT_COHORT_SIZE))
        cohort_selected = _pick_from_group(cohort_tag, remaining)
        remaining -= len(cohort_selected)
        if remaining > 0:
            for donor in _COHORT_DONOR_ORDER.get(cohort_tag, ()):
                donor_selected = _pick_from_group(donor, remaining)
                cohort_selected.extend(donor_selected)
                remaining -= len(donor_selected)
                if remaining <= 0:
                    break
        if remaining > 0:
            raise ValueError(f"样本不足，cohort={cohort_tag} 缺少 {remaining} 份病历")
        selected.extend(cohort_selected)

    manifest = [
        {
            "institute_id": str(item.get("institute_id") or ""),
            "patient_id": str(item.get("patient_id") or ""),
            "visit_id": str(item.get("visit_id") or ""),
            "scene": str(item.get("scene") or ""),
            "cohort_tag": str(item.get("cohort_tag") or ""),
        }
        for item in selected
    ]
    manifest.sort(key=lambda item: (item["scene"], item["cohort_tag"], item["visit_id"]))
    return manifest


def build_sc_rule_family_manifest(
    *,
    schema: str = "public",
    cohort_size: int = DEFAULT_COHORT_SIZE,
    limit_per_scene: int = 500,
) -> list[dict[str, Any]]:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; 无法构建 rule_family manifest")

    def _fetch_scene_rows(table_name: str, scene: str) -> list[dict[str, Any]]:
        sql = text(
            f"""
            SELECT
                institute_id,
                patient_id,
                visit_id,
                scene,
                document_hits,
                source_doc_priority,
                bundle_updated_at
            FROM {schema}.{table_name}
            WHERE text_available = true
            ORDER BY bundle_updated_at DESC
            LIMIT :limit
            """
        )
        with engine.connect() as conn:
            rows = conn.execute(sql, {"limit": max(50, int(limit_per_scene or 500))}).mappings().all()
        normalized_rows = []
        for row in rows:
            normalized = _normalize_manifest_row(dict(row))
            if normalized.get("scene") != scene:
                normalized["scene"] = scene
                normalized["cohort_tag"] = classify_scene_bundle_cohort(
                    scene=scene,
                    document_hits=normalized["document_hits"],
                    source_doc_priority=normalized["source_doc_priority"],
                )
            normalized_rows.append(normalized)
        return normalized_rows

    candidates = [
        *_fetch_scene_rows(_RUNNING_SCENE_TABLE, "running"),
        *_fetch_scene_rows(_FINAL_SCENE_TABLE, "final"),
    ]
    return select_manifest_entries(candidates, cohort_size=cohort_size)


async def _evaluate_manifest_entry(
    *,
    service: SichuanQCService,
    manifest_entry: dict[str, Any],
    rule_ids: list[str],
    bucket_strategy: str,
    schema: str,
) -> dict[str, Any]:
    from .qc_input_adapters.running_final_bundle_runtime import load_running_final_bundle

    bundle = load_running_final_bundle(
        scene=str(manifest_entry.get("scene") or ""),
        institute_id=str(manifest_entry.get("institute_id") or ""),
        patient_id=str(manifest_entry.get("patient_id") or ""),
        visit_id=str(manifest_entry.get("visit_id") or ""),
        schema=schema,
    )
    started_at = time.perf_counter()
    result = await service.evaluate_running_final_bundle_input(
        bundle=bundle,
        rule_ids=rule_ids,
        bucket_strategy=bucket_strategy,
        use_execution_cache=False,
    )
    result["_wall_clock_time"] = round(time.perf_counter() - started_at, 4)
    return result


def _collect_rule_rows(
    *,
    manifest_entry: dict[str, Any],
    result: dict[str, Any],
    round_index: int,
    arm_name: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    primary_excerpt = _truncate_text(
        ((result.get("evidence_payload") or {}).get("primary_document_text") or ""),
        limit=280,
    )
    for item in list(result.get("evaluation_results") or []):
        metadata = dict(item.get("metadata") or {})
        rows.append(
            {
                "arm": arm_name,
                "round_index": int(round_index),
                "visit_id": str(manifest_entry.get("visit_id") or ""),
                "patient_id": str(manifest_entry.get("patient_id") or ""),
                "institute_id": str(manifest_entry.get("institute_id") or ""),
                "scene": str(manifest_entry.get("scene") or ""),
                "cohort_tag": str(manifest_entry.get("cohort_tag") or ""),
                "rule_id": str(item.get("rule_id") or ""),
                "rule_name": str(item.get("rule_name") or ""),
                "status": str(item.get("status") or ""),
                "is_compliant": bool(item.get("is_compliant") is True),
                "findings": str(item.get("findings") or ""),
                "evidence": str(item.get("evidence") or ""),
                "suggestion": str(item.get("suggestion") or ""),
                "confidence": _safe_float(item.get("confidence")),
                "execution_domain": str(metadata.get("execution_domain") or ""),
                "doc_scope": str(metadata.get("doc_scope") or ""),
                "rule_family": str(metadata.get("rule_family") or DEFAULT_RULE_FAMILY),
                "bucket_strategy": str(metadata.get("bucket_strategy") or ""),
                "bucket_key": str(metadata.get("bucket_key") or ""),
                "pack_id": str(metadata.get("pack_id") or ""),
                "pack_size": _safe_int(metadata.get("pack_size")),
                "prompt_strategy": str(metadata.get("prompt_strategy") or ""),
                "record_excerpt": primary_excerpt,
            }
        )
    return rows


def summarize_arm_round(
    *,
    manifest: list[dict[str, Any]],
    rule_ids: list[str],
    record_outputs: list[dict[str, Any]],
    round_index: int,
    arm_name: str,
    bucket_strategy: str,
    sc_source: str,
    model_version: str,
) -> dict[str, Any]:
    expected_rules = max(1, len(manifest) * len(rule_ids))
    observed_rows: list[dict[str, Any]] = []
    total_tokens = 0
    total_api_time = 0.0
    total_wall_clock = 0.0
    total_packs = 0
    weighted_pack_size = 0.0
    fallback_packs = 0
    single_rule_retries = 0
    bucket_count = 0
    parse_error_count = 0
    missing_rule_items = 0
    pack_parse_retry_count = 0
    pack_fallback_count = 0
    failed_records = 0
    low_confidence_count = 0
    status_counts = defaultdict(int)
    family_status_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    selected_pack_size_by_bucket: dict[str, list[int]] = defaultdict(list)

    for output in record_outputs:
        if output.get("error"):
            failed_records += 1
            continue
        result = dict(output.get("result") or {})
        pack_metrics = dict(result.get("pack_metrics") or {})
        rows = _collect_rule_rows(
            manifest_entry=dict(output.get("manifest_entry") or {}),
            result=result,
            round_index=round_index,
            arm_name=arm_name,
        )
        observed_rows.extend(rows)
        total_tokens += _safe_int(((result.get("token_usage") or {}).get("total_tokens")))
        total_api_time += _safe_float(result.get("api_time"))
        total_wall_clock += _safe_float(result.get("_wall_clock_time"))
        pack_count = _safe_int(pack_metrics.get("total_packs"))
        avg_pack_size = _safe_float(pack_metrics.get("avg_pack_size"))
        total_packs += pack_count
        weighted_pack_size += avg_pack_size * pack_count
        fallback_packs += _safe_int(pack_metrics.get("fallback_packs"))
        single_rule_retries += _safe_int(pack_metrics.get("single_rule_retries"))
        bucket_count += _safe_int(pack_metrics.get("bucket_count"))
        parse_error_count += _safe_int(pack_metrics.get("pack_parse_error_count"))
        missing_rule_items += _safe_int(pack_metrics.get("missing_rule_items"))
        pack_parse_retry_count += _safe_int(pack_metrics.get("pack_parse_retry_count"))
        pack_fallback_count += _safe_int(pack_metrics.get("pack_fallback_count"))
        for bucket_key, pack_size in dict(pack_metrics.get("selected_pack_size_by_bucket") or {}).items():
            selected_pack_size_by_bucket[str(bucket_key)].append(_safe_int(pack_size))

        for row in rows:
            status = str(row.get("status") or "missing")
            family = str(row.get("rule_family") or DEFAULT_RULE_FAMILY)
            confidence = _safe_float(row.get("confidence"))
            status_counts[status] += 1
            family_status_counts[family][status] += 1
            if confidence < LOW_CONFIDENCE_THRESHOLD:
                low_confidence_count += 1

    non_compliant_count = int(status_counts.get("non_compliant") or 0)
    uncertain_count = int(status_counts.get("uncertain") or 0)
    observed_rules = len(observed_rows)
    return {
        "arm": arm_name,
        "round_index": int(round_index),
        "bucket_strategy": bucket_strategy,
        "sc_source": sc_source,
        "model_version": model_version,
        "manifest_size": len(manifest),
        "rule_count": len(rule_ids),
        "expected_rule_results": expected_rules,
        "observed_rule_results": observed_rules,
        "rule_coverage": round((observed_rules / expected_rules) * 100, 2) if expected_rules else 0.0,
        "failed_records": failed_records,
        "total_tokens": total_tokens,
        "total_api_time": round(total_api_time, 4),
        "wall_clock_time": round(total_wall_clock, 4),
        "avg_pack_size": round((weighted_pack_size / total_packs), 2) if total_packs else 0.0,
        "total_packs": total_packs,
        "fallback_packs": fallback_packs,
        "single_rule_retries": single_rule_retries,
        "bucket_count": bucket_count,
        "parse_error_count": parse_error_count,
        "missing_rule_items": missing_rule_items,
        "pack_parse_retry_count": pack_parse_retry_count,
        "pack_fallback_count": pack_fallback_count,
        "non_compliant_count": non_compliant_count,
        "uncertain_count": uncertain_count,
        "low_confidence_rate": round((low_confidence_count / observed_rules) * 100, 2) if observed_rules else 0.0,
        "selected_pack_size_by_bucket": {
            bucket_key: values
            for bucket_key, values in sorted(selected_pack_size_by_bucket.items())
        },
        "status_breakdown": dict(status_counts),
        "family_status_breakdown": {
            family: dict(status_counts_by_family)
            for family, status_counts_by_family in family_status_counts.items()
        },
        "observed_rows": observed_rows,
    }


def build_rule_level_diff(
    *,
    arm_a_rows: list[dict[str, Any]],
    arm_b_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    row_map_a = {(row["visit_id"], row["rule_id"]): row for row in arm_a_rows}
    row_map_b = {(row["visit_id"], row["rule_id"]): row for row in arm_b_rows}
    all_keys = sorted(set(row_map_a.keys()) | set(row_map_b.keys()))
    diff_rows: list[dict[str, Any]] = []

    for key in all_keys:
        row_a = dict(row_map_a.get(key) or {})
        row_b = dict(row_map_b.get(key) or {})
        status_a = str(row_a.get("status") or "missing")
        status_b = str(row_b.get("status") or "missing")
        same_status = status_a == status_b
        base_row = row_b or row_a
        diff_rows.append(
            {
                "visit_id": key[0],
                "rule_id": key[1],
                "rule_name": str(base_row.get("rule_name") or ""),
                "scene": str(base_row.get("scene") or ""),
                "cohort_tag": str(base_row.get("cohort_tag") or ""),
                "execution_domain": str(base_row.get("execution_domain") or ""),
                "doc_scope": str(base_row.get("doc_scope") or ""),
                "rule_family": str(base_row.get("rule_family") or DEFAULT_RULE_FAMILY),
                "status_a": status_a,
                "status_b": status_b,
                "same_status": same_status,
                "confidence_a": _safe_float(row_a.get("confidence")),
                "confidence_b": _safe_float(row_b.get("confidence")),
                "findings_a": str(row_a.get("findings") or ""),
                "findings_b": str(row_b.get("findings") or ""),
                "evidence_a": str(row_a.get("evidence") or ""),
                "evidence_b": str(row_b.get("evidence") or ""),
                "suggestion_a": str(row_a.get("suggestion") or ""),
                "suggestion_b": str(row_b.get("suggestion") or ""),
                "bucket_key_a": str(row_a.get("bucket_key") or ""),
                "bucket_key_b": str(row_b.get("bucket_key") or ""),
                "record_excerpt": str(base_row.get("record_excerpt") or ""),
            }
        )

    diff_rows.sort(
        key=lambda item: (
            item["execution_domain"],
            item["rule_family"],
            item["visit_id"],
            item["rule_id"],
        )
    )
    return diff_rows


def build_review_queue(
    diff_rows: list[dict[str, Any]],
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    divergent = [dict(item) for item in diff_rows if not bool(item.get("same_status"))]
    if len(divergent) <= max(1, int(limit or 40)):
        return [
            {
                **item,
                "review_verdict": "",
                "review_notes": "",
            }
            for item in divergent
        ]

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in divergent:
        grouped[(str(item.get("execution_domain") or ""), str(item.get("rule_family") or ""))].append(item)

    for group_items in grouped.values():
        group_items.sort(key=lambda item: (item["visit_id"], item["rule_id"]))

    selected: list[dict[str, Any]] = []
    group_keys = sorted(grouped.keys())
    while len(selected) < limit and group_keys:
        next_round: list[tuple[str, str]] = []
        for key in group_keys:
            bucket = grouped[key]
            if bucket and len(selected) < limit:
                selected.append(bucket.pop(0))
            if bucket:
                next_round.append(key)
        group_keys = next_round
    return [
        {
            **item,
            "review_verdict": "",
            "review_notes": "",
        }
        for item in selected
    ]


def build_ab_summary(
    *,
    manifest: list[dict[str, Any]],
    rule_ids: list[str],
    arm_round_summaries: dict[str, list[dict[str, Any]]],
    diff_rows: list[dict[str, Any]],
    sc_source: str,
    model_version: str,
) -> dict[str, Any]:
    def _median(field_name: str, rows: list[dict[str, Any]]) -> float:
        values = [_bucket_metric_value(row, field_name) for row in rows]
        return round(float(statistics.median(values)), 4) if values else 0.0

    family_totals: dict[str, int] = defaultdict(int)
    family_drifts: dict[str, int] = defaultdict(int)
    status_drift_count = 0
    for row in diff_rows:
        family = str(row.get("rule_family") or DEFAULT_RULE_FAMILY)
        family_totals[family] += 1
        if not bool(row.get("same_status")):
            status_drift_count += 1
            family_drifts[family] += 1

    summary = {
        "generated_at": _now_iso(),
        "sc_source": sc_source,
        "model_version": model_version,
        "manifest_size": len(manifest),
        "rule_count": len(rule_ids),
        "status_drift_rate": round((status_drift_count / len(diff_rows)) * 100, 2) if diff_rows else 0.0,
        "family_drift_rate": {
            family: round((family_drifts[family] / count) * 100, 2)
            for family, count in sorted(family_totals.items())
            if count > 0
        },
        "arms": {},
    }

    for arm_name, rounds in arm_round_summaries.items():
        summary["arms"][arm_name] = {
            "rounds": [
                {key: value for key, value in row.items() if key != "observed_rows"}
                for row in rounds
            ],
            "medians": {
                "rule_coverage": _median("rule_coverage", rounds),
                "total_tokens": _median("total_tokens", rounds),
                "total_api_time": _median("total_api_time", rounds),
                "wall_clock_time": _median("wall_clock_time", rounds),
                "avg_pack_size": _median("avg_pack_size", rounds),
                "total_packs": _median("total_packs", rounds),
                "fallback_packs": _median("fallback_packs", rounds),
                "single_rule_retries": _median("single_rule_retries", rounds),
                "bucket_count": _median("bucket_count", rounds),
                "parse_error_count": _median("parse_error_count", rounds),
                "missing_rule_items": _median("missing_rule_items", rounds),
                "non_compliant_count": _median("non_compliant_count", rounds),
                "uncertain_count": _median("uncertain_count", rounds),
                "low_confidence_rate": _median("low_confidence_rate", rounds),
            },
        }
    return summary


def write_ab_outputs(
    *,
    output_dir: Path,
    summary: dict[str, Any],
    diff_rows: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "ab_summary.json"
    diff_path = output_dir / "ab_rule_level_diff.csv"
    review_path = output_dir / "ab_review_queue.csv"

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        fieldnames: list[str] = []
        if rows:
            fieldnames = list(rows[0].keys())
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if fieldnames:
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)

    _write_csv(diff_path, diff_rows)
    _write_csv(review_path, review_queue)
    return {
        "ab_summary.json": str(summary_path),
        "ab_rule_level_diff.csv": str(diff_path),
        "ab_review_queue.csv": str(review_path),
    }


async def run_sc_rule_family_ab_experiment(
    *,
    manifest: list[dict[str, Any]],
    schema: str = "public",
    rounds: int = DEFAULT_REPLAY_ROUNDS,
    output_dir: Path | None = None,
    service: SichuanQCService | None = None,
    evaluator: Callable[..., Awaitable[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    qc_service = service or SichuanQCService()
    overview = qc_service.assert_sc_rule_source_ready(
        context="rule_family_ab_runner",
        block_batch=True,
    )
    sc_source = str(overview.get("sc_source") or "")
    if sc_source != "pg_governance":
        raise RuntimeError(f"SC 规则来源不满足 POC 要求: {sc_source}")

    sc_rules = qc_service.get_sc_rules_for_rule_family_poc()
    rule_ids = [str(rule.get("rule_id") or "") for rule in sc_rules]
    if not rule_ids:
        raise RuntimeError("未加载到 SC 146 规则")

    eval_fn = evaluator or _evaluate_manifest_entry
    arm_configs = {
        "A": "domain_only",
        "B": "domain_family",
    }
    arm_round_summaries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    latest_rows_by_arm: dict[str, list[dict[str, Any]]] = {}

    for arm_name, bucket_strategy in arm_configs.items():
        for round_index in range(1, max(1, int(rounds or DEFAULT_REPLAY_ROUNDS)) + 1):
            record_outputs: list[dict[str, Any]] = []
            for manifest_entry in manifest:
                try:
                    result = await eval_fn(
                        service=qc_service,
                        manifest_entry=dict(manifest_entry),
                        rule_ids=rule_ids,
                        bucket_strategy=bucket_strategy,
                        schema=schema,
                    )
                    record_outputs.append(
                        {
                            "manifest_entry": dict(manifest_entry),
                            "result": result,
                        }
                    )
                except Exception as exc:
                    record_outputs.append(
                        {
                            "manifest_entry": dict(manifest_entry),
                            "error": str(exc),
                        }
                    )

            round_summary = summarize_arm_round(
                manifest=manifest,
                rule_ids=rule_ids,
                record_outputs=record_outputs,
                round_index=round_index,
                arm_name=arm_name,
                bucket_strategy=bucket_strategy,
                sc_source=sc_source,
                model_version=str(qc_service.client.model or ""),
            )
            arm_round_summaries[arm_name].append(round_summary)
            latest_rows_by_arm[arm_name] = list(round_summary.get("observed_rows") or [])

    diff_rows = build_rule_level_diff(
        arm_a_rows=latest_rows_by_arm.get("A", []),
        arm_b_rows=latest_rows_by_arm.get("B", []),
    )
    review_queue = build_review_queue(diff_rows)
    summary = build_ab_summary(
        manifest=manifest,
        rule_ids=rule_ids,
        arm_round_summaries=arm_round_summaries,
        diff_rows=diff_rows,
        sc_source=sc_source,
        model_version=str(qc_service.client.model or ""),
    )

    resolved_output_dir = output_dir or (
        Path(__file__).resolve().parents[2]
        / "release-gate-artifacts"
        / "sc_rule_family_ab"
        / datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    written_paths = write_ab_outputs(
        output_dir=resolved_output_dir,
        summary=summary,
        diff_rows=diff_rows,
        review_queue=review_queue,
    )
    return {
        "summary": summary,
        "diff_rows": diff_rows,
        "review_queue": review_queue,
        "paths": written_paths,
        "manifest_size": len(manifest),
        "rule_count": len(rule_ids),
    }
