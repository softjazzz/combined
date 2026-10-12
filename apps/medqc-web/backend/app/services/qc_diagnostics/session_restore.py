"""仅用已冻结资料还原执行 session；不查询数据库、不提取新事实。

此入口也用于脱敏前后的结构校验，不代表输入已脱敏或临床结论正确。
就诊坐标由调用方显式提供；不能从现库补齐缺失材料。
"""
from __future__ import annotations

from .contracts import DiagnosticPackageError
from .typed_values import decode_value, encode_value


def _same(left, right) -> bool:
    # Python 的 True == 1 不能作为诊断材料等价证据。
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same(left[key], right[key]) for key in left)
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _restore_facts(rows):
    from ..luxian_0609.fact_schema import FactV2, TimeValue

    if type(rows) is not list or len(rows) > 1000:
        raise ValueError()
    pending = {}
    for row in rows:
        if type(row) is not dict or type(row.get("fact_id")) is not str or row["fact_id"] in pending:
            raise ValueError()
        pending[row["fact_id"]] = row
    restored = {}
    while pending:
        progressed = False
        for fact_id, row in tuple(pending.items()):
            extensions = row.get("extensions")
            if type(extensions) is not dict:
                raise ValueError()
            dependencies = set()
            for projection in extensions.values():
                if type(projection) is not dict or type(projection.get("derived_from_fact_ids")) is not list:
                    raise ValueError()
                dependencies.update(projection["derived_from_fact_ids"])
            if not dependencies <= restored.keys():
                continue
            parameters = {key: value for key, value in row.items() if key != "fact_id"}
            for key in ("record_time", "submit_time", "update_time"):
                raw_time = parameters[key]
                parameters[key] = None if raw_time is None else TimeValue.create(**raw_time)
            fact = FactV2.create(**parameters, redaction_terms=(), known_upstream_fact_ids=tuple(restored))
            if not _same(fact.to_dict(), row):
                raise ValueError()
            restored[fact_id] = fact
            del pending[fact_id]
            progressed = True
        if not progressed:
            # 缺失、循环或自引用均不得通过猜测依赖关系修补。
            raise ValueError()
    return tuple(restored.values())


def restore_execution_session(inputs: object, *, coordinates: tuple[str, str, str]):
    """严格重建冻结 session，任何不一致只返回固定安全错误。

    资源边界先于官方摘要函数，避免其 default=str 接触自定义对象。
    已查询来源的空值、重复行、顺序、截断和 limit 均按录制值保留。
    """
    try:
        # 深复制将返回对象与调用方可变输入隔离，且先限制类型/深度/总量。
        data = decode_value(encode_value(inputs))
        if type(coordinates) is not tuple or len(coordinates) != 3 or any(
            type(value) is not str or not value.strip() or len(value) > 128 for value in coordinates
        ):
            raise ValueError()
        required = {"snapshot", "sources", "selected_rule_ids", "evaluation_as_of_date",
                    "evaluation_horizon_policy", "horizon_unavailable_reason"}
        if type(data) is not dict or data.keys() != required:
            raise ValueError()
        snapshot_data, sources_data = data["snapshot"], data["sources"]
        if type(snapshot_data) is not dict or type(sources_data) is not dict or len(sources_data) > 128:
            raise ValueError()
        from ..luxian_0609.evidence_material import (
            Luxian0609EvidenceMaterialStore, Luxian0609EvidenceReadSession,
            build_material_document_refs, build_material_snapshot_ref,
        )
        from ..luxian_0609.evidence_snapshot import Luxian0609EvidenceSnapshot, SourceObservation
        from ..luxian_0609.source_evidence_reader import SnapshotSourceRows
        from ..luxian_0609.source_registry import resolve_luxian_0609_controlled_fact_source_keys

        if type(data["selected_rule_ids"]) is not tuple:
            raise ValueError()
        controlled_sources = resolve_luxian_0609_controlled_fact_source_keys(data["selected_rule_ids"])

        sources = {}
        count = 0
        for key, source in sources_data.items():
            if type(source) is not dict or source.keys() != {"rows", "truncated", "limit_rows"}:
                raise ValueError()
            if type(source["rows"]) is not tuple or type(source["truncated"]) is not bool:
                raise ValueError()
            if type(source["limit_rows"]) is not int:
                raise ValueError()
            count += len(source["rows"])
            if count > 10000:
                raise ValueError()
            sources[key] = SnapshotSourceRows.create(source_key=key, **source)
        observation_rows = snapshot_data["observations"]
        if type(observation_rows) is not list or len(observation_rows) > 128:
            raise ValueError()
        observations = []
        all_refs = set()
        for row in observation_rows:
            observation = SourceObservation.create(**row)
            if not _same(observation.to_dict(), row):
                raise ValueError()
            material = sources.get(observation.source_key)
            available = observation.query_state.value in {"available", "empty"}
            controlled = observation.source_key in controlled_sources
            if controlled and material is not None:
                raise ValueError()
            if not controlled and available != (material is not None):
                raise ValueError()
            refs = build_material_document_refs(observation.source_key, material.rows) if material else ()
            # 与快照构建一致（2026-10-10 起）：派生时间界限行同样登记进快照文书引用。
            all_refs.update(refs)
            expected = build_material_snapshot_ref(
                source_key=observation.source_key, query_version=observation.query_version,
                query_state=observation.query_state, completeness=observation.completeness, document_refs=refs,
            )
            if observation.snapshot_ref != expected:
                raise ValueError()
            observations.append(observation)
        # 文书引用既不能悬空，也不能遗漏材料行。
        if set(snapshot_data["document_refs"]) != all_refs:
            raise ValueError()
        snapshot = Luxian0609EvidenceSnapshot.create(
            institute_id=coordinates[0], patient_id=coordinates[1], visit_id=coordinates[2],
            snapshot_schema_version=snapshot_data["snapshot_schema_version"],
            source_registry_version=snapshot_data["source_registry_version"],
            observations=observations, facts=_restore_facts(snapshot_data["facts"]),
            document_refs=snapshot_data["document_refs"], created_at=snapshot_data["created_at"],
        )
        if not _same({**snapshot.to_safe_dict(), "facts": [fact.to_dict() for fact in snapshot.facts]}, snapshot_data):
            raise ValueError()
        materials = Luxian0609EvidenceMaterialStore.create(snapshot=snapshot, sources=sources)
        return Luxian0609EvidenceReadSession(snapshot=snapshot, materials=materials)
    except Exception:
        # 不回显正文、坐标、事实值、异常 repr 或底层对象类型。
        raise DiagnosticPackageError("invalid_execution_session_archive") from None
