"""LX0609 请求内证据材料仓。

材料仓与可安全序列化的 :class:`Luxian0609EvidenceSnapshot` 分离：前者只在
一次请求内向规则族提供已读取的白名单行，后者才允许进入指纹和安全 trace。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
from types import MappingProxyType
from typing import Any, Mapping

from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .source_evidence_reader import (
    SnapshotSourceRows,
    canonical_source_evidence,
    digest_source_evidence,
)
from .source_manifest import QueryStatus


class EvidenceMaterialUnavailable(Exception):
    """所需来源没有可消费的完整请求内材料。"""


class EvidenceMaterialTruncated(EvidenceMaterialUnavailable):
    """来源读取成功但超过请求内上限，不能据截断材料作完整判断。"""


def build_material_document_refs(
    source_key: str,
    rows: tuple[Mapping[str, Any], ...],
) -> tuple[str, ...]:
    materials = sorted(canonical_source_evidence(dict(row)) for row in rows)
    occurrences: Counter[str] = Counter()
    refs: list[str] = []
    for material in materials:
        ordinal = occurrences[material]
        occurrences[material] += 1
        refs.append(
            digest_source_evidence(
                {
                    "material": material,
                    "occurrence": ordinal,
                    "source_key": source_key,
                }
            )
        )
    return tuple(refs)


def build_material_snapshot_ref(
    *,
    source_key: str,
    query_version: str,
    query_state: QueryStatus,
    completeness: SourceCompleteness,
    document_refs: tuple[str, ...],
) -> str:
    return "sha256:" + digest_source_evidence(
        {
            "completeness": completeness.value,
            "document_refs": document_refs,
            "query_state": query_state.value,
            "query_version": query_version,
            "source_key": source_key,
        }
    )


@dataclass(frozen=True, repr=False)
class Luxian0609EvidenceMaterialStore:
    """与一个 snapshot 绑定的内部只读材料；禁止客户序列化。"""

    snapshot_hash: str
    _sources: Mapping[str, SnapshotSourceRows] = field(repr=False)

    @classmethod
    def create(
        cls,
        *,
        snapshot: Luxian0609EvidenceSnapshot,
        sources: Mapping[str, SnapshotSourceRows],
    ) -> "Luxian0609EvidenceMaterialStore":
        if not isinstance(snapshot, Luxian0609EvidenceSnapshot):
            raise TypeError("snapshot must be Luxian0609EvidenceSnapshot")
        if not isinstance(sources, Mapping):
            raise TypeError("sources must be a mapping")
        observation_by_source = {
            item.source_key: item for item in snapshot.observations
        }
        frozen: dict[str, SnapshotSourceRows] = {}
        for raw_source_key, material in sources.items():
            source_key = str(raw_source_key or "").strip().lower()
            observation = observation_by_source.get(source_key)
            if (
                not source_key
                or not isinstance(material, SnapshotSourceRows)
                or material.source_key != source_key
                or observation is None
                or observation.query_state
                not in (QueryStatus.AVAILABLE, QueryStatus.EMPTY)
                or observation.record_count != len(material.rows)
            ):
                raise ValueError("material source does not match snapshot")
            expected_completeness = (
                SourceCompleteness.TRUNCATED
                if material.truncated
                else SourceCompleteness.COMPLETE
            )
            if observation.completeness is not expected_completeness:
                raise ValueError("material completeness does not match snapshot")
            document_refs = build_material_document_refs(source_key, material.rows)
            expected_snapshot_ref = build_material_snapshot_ref(
                source_key=source_key,
                query_version=observation.query_version,
                query_state=observation.query_state,
                completeness=observation.completeness,
                document_refs=document_refs,
            )
            if observation.snapshot_ref != expected_snapshot_ref:
                raise ValueError("material rows do not match snapshot identity")
            frozen[source_key] = material
        return cls(
            snapshot_hash=snapshot.snapshot_hash,
            _sources=MappingProxyType(frozen),
        )

    def has_source(self, source_key: str) -> bool:
        return str(source_key or "").strip().lower() in self._sources

    def source(self, source_key: str) -> SnapshotSourceRows:
        normalized = str(source_key or "").strip().lower()
        material = self._sources.get(normalized)
        if material is None:
            raise EvidenceMaterialUnavailable()
        if material.truncated:
            raise EvidenceMaterialTruncated()
        return material

    def rows(self, source_key: str) -> tuple[Mapping[str, object], ...]:
        return self.source(source_key).rows

    def safe_summary(self) -> dict[str, object]:
        return {
            "source_count": len(self._sources),
            "sources": tuple(sorted(self._sources)),
        }

    def __repr__(self) -> str:
        return (
            "Luxian0609EvidenceMaterialStore("
            f"source_count={len(self._sources)})"
        )


@dataclass(frozen=True, repr=False)
class Luxian0609EvidenceReadSession:
    snapshot: Luxian0609EvidenceSnapshot
    materials: Luxian0609EvidenceMaterialStore

    def __post_init__(self) -> None:
        if self.materials.snapshot_hash != self.snapshot.snapshot_hash:
            raise ValueError("evidence session snapshot mismatch")

    def __repr__(self) -> str:
        return (
            "Luxian0609EvidenceReadSession("
            f"source_count={self.materials.safe_summary()['source_count']})"
        )


__all__ = [
    "EvidenceMaterialTruncated",
    "EvidenceMaterialUnavailable",
    "Luxian0609EvidenceMaterialStore",
    "Luxian0609EvidenceReadSession",
    "build_material_document_refs",
    "build_material_snapshot_ref",
]
