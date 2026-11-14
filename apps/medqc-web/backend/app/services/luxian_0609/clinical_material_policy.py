"""当前质控只使用原始临床材料；历史证据解析不受此策略重写。"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

FRONTPAGE_SOURCE_KEYS = frozenset({"mr", "mr_surgery", "mr_diagnosis", "mr_bloodtrans", "mr_cost"})
CLINICAL_MATERIAL_POLICY_VERSION = "primary-clinical-documents-v1"


def is_frontpage_source(source_key: str) -> bool:
    return source_key in FRONTPAGE_SOURCE_KEYS


def clinical_source_keys(source_keys: Iterable[str]) -> tuple[str, ...]:
    """排除策略不采用的来源，不伪造其为空或完整。"""
    return tuple(key for key in source_keys if not is_frontpage_source(key))


def primary_documents_only() -> bool:
    from .. import case_material_snapshot
    context = case_material_snapshot.context()
    return bool(context and context.get("clinical_material_policy") == CLINICAL_MATERIAL_POLICY_VERSION)


def clinical_record_scene(record: Mapping[str, Any]) -> str:
    """新任务的场景不继承列表中的首页出院标记。"""
    if "qc_admission_datetime" not in record:
        return str(record.get("scope") or "unknown").strip().lower()
    return str(record.get("qc_scope") or (
        "final" if record.get("qc_discharge_datetime") or record.get("qc_discharge_horizon_conflict")
        else "running" if record.get("qc_admission_datetime") else "unknown"
    )).strip().lower()


def frozen_clinical_scene(snapshot: Mapping[str, Any] | None) -> str | None:
    """只消费新任务已冻结的场景；旧快照无标识时不改其原读取路径。"""
    if not snapshot or snapshot.get("clinical_material_policy") != CLINICAL_MATERIAL_POLICY_VERSION:
        return None
    scene = snapshot.get("record_scene")
    if scene not in {"running", "final", "unknown"}:
        raise ValueError("invalid frozen clinical record scene")
    return str(scene)


def apply_frozen_clinical_scene(record: Mapping[str, Any], snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    scene = frozen_clinical_scene(snapshot)
    if scene is not None:
        from ..case_identity import CaseRef
        if CaseRef.from_mapping(record) != CaseRef.from_mapping(snapshot):
            raise ValueError("frozen clinical scene identity mismatch")
    return {**record, "scope": scene} if scene is not None else dict(record)
