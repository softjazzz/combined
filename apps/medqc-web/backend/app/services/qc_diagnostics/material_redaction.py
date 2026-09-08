"""重建脱敏材料的 document refs，不重建 FactV2 或声明整快照等价。"""
from __future__ import annotations

from collections.abc import Mapping
import re
from types import MappingProxyType

from app.services.luxian_0609.evidence_material import _build_material_document_rows
from app.services.luxian_0609.source_evidence_reader import (
    SnapshotSourceRows,
    SourceEvidenceUnavailable,
)

from .contracts import DiagnosticPackageError
from .sanitization import PayloadSanitizer
from .typed_values import encode_value


class MaterialRedaction:
    """只向调用方暴露新材料；原引用映射只存在内存，不提供序列化接口。"""

    __slots__ = ("_sources", "_reference_map", "related_values")

    def __init__(self, sources: Mapping[str, SnapshotSourceRows], reference_map: Mapping[str, str], related_values=()):
        self._sources = MappingProxyType(dict(sources))
        self._reference_map = MappingProxyType(dict(reference_map))
        self.related_values = related_values

    def __repr__(self) -> str:
        return f"MaterialRedaction(source_count={len(self._sources)})"

    @property
    def sources(self) -> Mapping[str, SnapshotSourceRows]:
        return self._sources

    def remap_document_refs(self, refs: tuple[str, ...]) -> tuple[str, ...]:
        if type(refs) is not tuple or len(refs) > 10000 or any(
            type(ref) is not str or re.fullmatch(r"[0-9a-f]{64}", ref) is None
            for ref in refs
        ):
            raise DiagnosticPackageError("invalid_document_references")
        if any(ref not in self._reference_map for ref in refs):
            raise DiagnosticPackageError("unresolved_document_reference")
        return tuple(self._reference_map[ref] for ref in refs)


def sanitize_material_sources(
    sources: Mapping[str, SnapshotSourceRows], *, sanitizer: PayloadSanitizer, related_values=(),
) -> MaterialRedaction:
    """先整体脱敏，再按新行 identity 配对；排序改变不改变引用归属。"""
    if type(sources) not in (dict, MappingProxyType) or len(sources) > 128 or not isinstance(sanitizer, PayloadSanitizer):
        raise DiagnosticPackageError("invalid_material_sources")
    validated: dict[str, SnapshotSourceRows] = {}
    flattened = []
    old_refs: dict[str, tuple[str, ...]] = {}
    row_count = 0
    try:
        for key, material in sources.items():
            if type(key) is not str or type(material) is not SnapshotSourceRows or key != material.source_key:
                raise ValueError()
            if type(material.rows) is not tuple or row_count + len(material.rows) > 10000:
                raise ValueError()
            row_count += len(material.rows)
            # 哈希的 default=str 不得接触自定义对象；先验证类型和单源资源。
            encode_value(material.rows)
            checked = SnapshotSourceRows.create(
                source_key=key, rows=material.rows, truncated=material.truncated,
                limit_rows=material.limit_rows,
            )
            if checked.source_key != key:
                raise ValueError()
            validated[key] = checked
        # 在任何 canonical 哈希分配前也验证所有来源的总载荷上限。
        encode_value((tuple(row for material in validated.values() for row in material.rows), related_values))
        for key, checked in validated.items():
            pairs = _build_material_document_rows(key, checked.rows)
            ref_by_row_identity = {id(row): ref for ref, row in pairs}
            old_refs[key] = tuple(ref_by_row_identity[id(row)] for row in checked.rows)
            # occurrence 已由权威算法区分；即使调用方重复传同一个 row 对象，
            # create 后也是独立行，脱敏时每个 occurrence 都有独立新行。
            # 保留源行原顺序，不能让摘要排序改变执行器见到的输入顺序。
            flattened.extend(checked.rows)
    except (TypeError, ValueError, SourceEvidenceUnavailable):
        raise DiagnosticPackageError("invalid_material_sources") from None

    # 事实、模型文本等附带材料必须在同一次 collect 中发现身份；不能先脱敏
    # 正文，再发现只出现在附带材料字段里的姓名而让前面的正文漏脱敏。
    cleaned, cleaned_related = sanitizer.sanitize((tuple(flattened), related_values))
    rebuilt: dict[str, SnapshotSourceRows] = {}
    reference_map: dict[str, str] = {}
    offset = 0
    for key, original in validated.items():
        size = len(original.rows)
        new_source = SnapshotSourceRows.create(
            source_key=key, rows=cleaned[offset:offset + size],
            truncated=original.truncated, limit_rows=original.limit_rows,
        )
        # create 保持行输入顺序，但权威摘要排序可能改变，必须通过 identity 回连。
        old_ref_by_new_identity = {
            id(row): old_refs[key][index] for index, row in enumerate(new_source.rows)
        }
        for new_ref, row in _build_material_document_rows(key, new_source.rows):
            reference_map[old_ref_by_new_identity[id(row)]] = new_ref
        rebuilt[key] = new_source
        offset += size
    return MaterialRedaction(rebuilt, reference_map, cleaned_related)
