"""解析已保存任务的材料所有者；只校验任务图，不捕获或复制材料。"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import uuid


@dataclass(frozen=True)
class _Origin:
    material_job_id: str
    root_job_id: str
    attempt: int


def _filters(job: Mapping) -> tuple[dict, str | None]:
    raw = job.get("filters_json", job.get("_claim_filters_json"))
    if raw is not None:
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            raise ValueError("retry_lineage_filters_invalid") from None
    else:
        value = job.get("filters", {})
    if not isinstance(value, dict):
        raise ValueError("retry_lineage_filters_invalid")
    return value, raw


def _refs(filters: dict) -> set[tuple[str, str, str]]:
    refs = filters.get("record_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError("retry_lineage_case_identity_missing")
    result = set()
    for ref in refs:
        if not isinstance(ref, dict):
            raise ValueError("retry_lineage_case_identity_missing")
        identity = tuple(ref.get(key) for key in ("institute_id", "patient_id", "visit_id"))
        if not all(isinstance(value, str) and value.strip() for value in identity):
            raise ValueError("retry_lineage_case_identity_missing")
        result.add(identity)
    return result


def _same_scope(job: Mapping, filters: dict, source: Mapping, source_filters: dict) -> None:
    from .clinical_sources import saved_snapshot
    from ..database.clinical_connection import ClinicalSourceConfigurationError

    if not job.get("created_by") or job.get("created_by") != source.get("created_by"):
        raise ValueError("retry_lineage_owner_mismatch")
    if not _refs(filters).issubset(_refs(source_filters)):
        raise ValueError("retry_lineage_case_identity_mismatch")
    try:
        same_source = saved_snapshot(filters) == saved_snapshot(source_filters)
    except (ValueError, ClinicalSourceConfigurationError):
        raise ValueError("retry_lineage_clinical_source_invalid") from None
    if not same_source:
        raise ValueError("retry_lineage_clinical_source_mismatch")


def resolve_material_job_id(job: Mapping, lookup: Callable[[str], Mapping | None]) -> str:
    """校验完整重试链和原始父子关系；不能由任意 material_job_id 借用其他任务。"""
    seen: set[str] = set()

    def load(job_id: str) -> Mapping:
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("retry_lineage_source_unavailable")
        source = lookup(job_id)
        if source is None or source.get("id") != job_id:
            raise ValueError("retry_lineage_source_unavailable")
        return source

    def resolve(current: Mapping) -> _Origin:
        job_id = current.get("id")
        if not isinstance(job_id, str) or not job_id or job_id in seen or len(seen) >= 64:
            raise ValueError("retry_lineage_cycle_or_depth_invalid")
        seen.add(job_id)
        filters, _ = _filters(current)
        row_parent, filter_parent = current.get("parent_job_id"), filters.get("parent_job_id")
        if row_parent and filter_parent and row_parent != filter_parent:
            raise ValueError("retry_lineage_parent_mismatch")
        parent_id = row_parent or filter_parent
        lineage = filters.get("retry_lineage")
        if lineage is not None:
            if (not isinstance(lineage, dict) or lineage.get("schema_version") != "qc-retry-lineage-v1"
                    or parent_id or current.get("job_kind") == "parent"):
                raise ValueError("retry_lineage_invalid")
            source = load(lineage.get("source_job_id"))
            source_filters, source_raw = _filters(source)
            if not isinstance(source_raw, str):
                raise ValueError("retry_lineage_source_filters_unavailable")
            digest = hashlib.sha256(source_raw.encode("utf-8")).hexdigest()
            expected_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"medqc:retry:v1:{source['id']}:{digest}"))
            if (job_id != expected_id or lineage.get("source_filters_sha256") != digest
                    or lineage.get("source_attempt") != (source_filters.get("_lx0609_attempt_id") or "")):
                raise ValueError("retry_lineage_identity_mismatch")
            _same_scope(current, filters, source, source_filters)
            origin = resolve(source)
            if (lineage.get("root_job_id") != origin.root_job_id
                    or lineage.get("material_job_id") != origin.material_job_id
                    or type(lineage.get("attempt")) is not int or lineage["attempt"] != origin.attempt + 1):
                raise ValueError("retry_lineage_identity_mismatch")
            return _Origin(origin.material_job_id, origin.root_job_id, lineage["attempt"])
        if parent_id:
            if row_parent != parent_id or current.get("job_kind") != "child":
                raise ValueError("retry_lineage_parent_mismatch")
            parent = load(parent_id)
            parent_filters, _ = _filters(parent)
            if (parent_id in seen or parent.get("job_kind") != "parent"
                    or parent.get("parent_job_id") or parent_filters.get("parent_job_id")
                    or parent_filters.get("retry_lineage") is not None):
                raise ValueError("retry_lineage_parent_mismatch")
            try:
                children = json.loads(parent["child_job_ids_json"]) if parent.get("child_job_ids_json") is not None else parent.get("child_job_ids", [])
            except (TypeError, ValueError):
                raise ValueError("retry_lineage_parent_mismatch") from None
            if not isinstance(children, list) or job_id not in children:
                raise ValueError("retry_lineage_parent_mismatch")
            _same_scope(current, filters, parent, parent_filters)
            return _Origin(parent_id, job_id, 0)
        return _Origin(job_id, job_id, 0)

    return resolve(job).material_job_id
