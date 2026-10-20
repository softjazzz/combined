"""LX0609 请求内证据材料仓。

材料仓与可安全序列化的 :class:`Luxian0609EvidenceSnapshot` 分离：前者只在
一次请求内向规则族提供已读取的白名单行，后者才允许进入指纹和安全 trace。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
from datetime import date, datetime, time
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID

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
    return tuple(
        document_ref
        for document_ref, _ in _build_material_document_rows(source_key, rows)
    )


def _build_material_document_rows(
    source_key: str,
    rows: tuple[Mapping[str, Any], ...],
) -> tuple[tuple[str, Mapping[str, Any]], ...]:
    """按既有文书摘要顺序配对原始行，重复正文以 occurrence 区分。"""

    materials = sorted(
        ((canonical_source_evidence(dict(row)), row) for row in rows),
        key=lambda item: item[0],
    )
    occurrences: Counter[str] = Counter()
    document_rows: list[tuple[str, Mapping[str, Any]]] = []
    for material, row in materials:
        ordinal = occurrences[material]
        occurrences[material] += 1
        document_rows.append(
            (
                digest_source_evidence(
                    {
                        "material": material,
                        "occurrence": ordinal,
                        "source_key": source_key,
                    }
                ),
                row,
            )
        )
    return tuple(document_rows)


def _is_recursively_cache_safe(value: Any) -> bool:
    """仅允许不会在 snapshot 创建后被原地改写的行值进入缓存。"""

    if type(value) in (
        type(None),
        bool,
        int,
        float,
        str,
        bytes,
        date,
        datetime,
        time,
        Decimal,
        UUID,
    ):
        return True
    if type(value) is tuple:
        return all(_is_recursively_cache_safe(item) for item in value)
    if type(value) is MappingProxyType:
        return all(
            _is_recursively_cache_safe(key)
            and _is_recursively_cache_safe(item)
            for key, item in value.items()
        )
    return False


def _source_rows_are_cache_safe(rows: tuple[Mapping[str, Any], ...]) -> bool:
    """只复用顶层和嵌套层均不可变的 ``SnapshotSourceRows``。"""

    return all(
        type(row) is MappingProxyType and _is_recursively_cache_safe(row)
        for row in rows
    )


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
    _document_rows_cache: Mapping[
        str, tuple[tuple[str, Mapping[str, Any]], ...]
    ] = field(
        default_factory=lambda: MappingProxyType({}),
        init=False,
        repr=False,
        compare=False,
    )

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
        document_rows_by_source: dict[
            str, tuple[tuple[str, Mapping[str, Any]], ...]
        ] = {}
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
            document_rows = _build_material_document_rows(source_key, material.rows)
            document_refs = tuple(item[0] for item in document_rows)
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
            if _source_rows_are_cache_safe(material.rows):
                document_rows_by_source[source_key] = document_rows
        store = cls(
            snapshot_hash=snapshot.snapshot_hash,
            _sources=MappingProxyType(frozen),
        )
        # 仅缓存本次 create 已经以同一 Snapshot 逐源验证过的冻结行。该字段
        # 不参与构造，直接构造的 Store 必须继续在 document_rows 中重算校验。
        object.__setattr__(
            store,
            "_document_rows_cache",
            MappingProxyType(document_rows_by_source),
        )
        return store

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

    def document_rows(
        self,
        source_key: str,
        *,
        snapshot: Luxian0609EvidenceSnapshot,
    ) -> tuple[tuple[str, Mapping[str, object]], ...]:
        """返回经同一 snapshot 证明的 ``(document_ref, 原始行)`` 对。"""

        return self._validated_document_rows(source_key, snapshot=snapshot, require_complete=True)

    def identity_document_rows(
        self, source_key: str, *, snapshot: Luxian0609EvidenceSnapshot,
    ) -> tuple[tuple[str, Mapping[str, object]], ...]:
        """身份检查覆盖全部已冻结行，含截断前缀；不证明临床来源完整。"""

        material = self._sources.get(str(source_key or "").strip().lower())
        if material is None or not material.truncated:
            return self.document_rows(source_key, snapshot=snapshot)
        return self._validated_document_rows(source_key, snapshot=snapshot, require_complete=False)

    def _validated_document_rows(
        self, source_key: str, *, snapshot: Luxian0609EvidenceSnapshot, require_complete: bool,
    ) -> tuple[tuple[str, Mapping[str, object]], ...]:

        if not isinstance(snapshot, Luxian0609EvidenceSnapshot):
            raise TypeError("snapshot must be Luxian0609EvidenceSnapshot")
        if self.snapshot_hash != snapshot.snapshot_hash:
            raise ValueError("material store does not match snapshot")
        normalized = str(source_key or "").strip().lower()
        if not isinstance(self._sources, Mapping):
            raise ValueError("invalid material store")
        material = self._sources.get(normalized)
        if material is None:
            raise EvidenceMaterialUnavailable()
        if (
            not isinstance(material, SnapshotSourceRows)
            or material.source_key != normalized
        ):
            raise ValueError("invalid material source")
        if material.truncated and require_complete:
            raise EvidenceMaterialTruncated()
        observation = next(
            (
                item
                for item in snapshot.observations
                if item.source_key == normalized
            ),
            None,
        )
        if (
            observation is None
            or observation.query_state
            not in (QueryStatus.AVAILABLE, QueryStatus.EMPTY)
            or observation.completeness is not (
                SourceCompleteness.TRUNCATED if material.truncated else SourceCompleteness.COMPLETE
            )
            or observation.record_count != len(material.rows)
        ):
            raise ValueError("material source does not match snapshot")
        cached_document_rows = self._document_rows_cache.get(normalized)
        document_rows = (
            cached_document_rows
            if cached_document_rows is not None
            else _build_material_document_rows(normalized, material.rows)
        )
        document_refs = tuple(item[0] for item in document_rows)
        expected_snapshot_ref = build_material_snapshot_ref(
            source_key=normalized,
            query_version=observation.query_version,
            query_state=observation.query_state,
            completeness=observation.completeness,
            document_refs=document_refs,
        )
        if (
            observation.snapshot_ref != expected_snapshot_ref
            or not set(document_refs).issubset(snapshot.document_refs)
        ):
            raise ValueError("material rows do not match snapshot identity")
        return document_rows

    def bounded_rows(self, source_key: str) -> tuple[Mapping[str, object], ...]:
        """返回请求内有界前缀；是否可作否定结论必须另查 snapshot 完整性。"""

        normalized = str(source_key or "").strip().lower()
        material = self._sources.get(normalized)
        if material is None:
            raise EvidenceMaterialUnavailable()
        return material.rows

    def safe_summary(self) -> dict[str, object]:
        return {
            "source_count": len(self._sources),
            "sources": tuple(sorted(self._sources)),
        }

    def diagnostic_sources(
        self, *, snapshot: Luxian0609EvidenceSnapshot,
    ) -> Mapping[str, SnapshotSourceRows]:
        """内部诊断取材，包含截断标记/原读取上限；不是安全序列化接口。

        不重新读取资料。调用方必须先冻结类型，再用 create 校验行内容与
        snapshot 的对应关系；本方法只验证所属快照并返回只读来源映射。
        """
        if not isinstance(snapshot, Luxian0609EvidenceSnapshot) or self.snapshot_hash != snapshot.snapshot_hash:
            raise ValueError("diagnostic material snapshot mismatch")
        return MappingProxyType(dict(self._sources))

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
