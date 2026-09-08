"""冻结 LX0609 当次已读资料及评价参数，不查询任何新的资料来源。

输出仍含原始信息，只可交给有界内存采集器，不得直接写文件或对外返回。
"""

from .contracts import DiagnosticPackageError
from .typed_values import decode_value, encode_value


def freeze_execution_inputs(session: object, *, selected_rule_ids: tuple[str, ...],
                            evaluation_as_of_date: str | None,
                            evaluation_horizon_policy: str | None,
                            horizon_unavailable_reason: str | None) -> dict[str, object]:
    # 延迟导入：关闭诊断时不额外加载引擎依赖。
    from ..luxian_0609.evidence_material import (
        Luxian0609EvidenceReadSession, Luxian0609EvidenceMaterialStore,
    )
    from ..luxian_0609.source_evidence_reader import SnapshotSourceRows

    if type(session) is not Luxian0609EvidenceReadSession:
        raise DiagnosticPackageError("invalid_execution_session")
    snapshot = session.snapshot
    sources = session.materials.diagnostic_sources(snapshot=snapshot)
    if any(type(source) is not SnapshotSourceRows or source.source_key != key
           for key, source in sources.items()):
        raise DiagnosticPackageError("invalid_execution_source")
    # 先拒绝自定义对象并冻结嵌套可变值，避免摘要算法的 default=str 执行任意 repr。
    frozen_sources = decode_value(encode_value({key: {
        "rows": source.rows, "truncated": source.truncated, "limit_rows": source.limit_rows,
    } for key, source in sources.items()}))
    rebuilt = {key: SnapshotSourceRows.create(source_key=key, **source)
               for key, source in frozen_sources.items()}
    Luxian0609EvidenceMaterialStore.create(snapshot=snapshot, sources=rebuilt)
    # 评价上下文的材料摘要不属于临床文书 document_refs；沿用材料仓合同，
    # 不擅自要求每个资料行都必须是可引用文书，也不改写原快照引用集合。
    # 安全 trace 只含事实摘要；这里必须使用原事实的正式完整序列化。
    captured_snapshot = {**snapshot.to_safe_dict(), "facts": [fact.to_dict() for fact in snapshot.facts]}
    return {
        "snapshot": captured_snapshot, "sources": frozen_sources,
        "selected_rule_ids": selected_rule_ids,
        "evaluation_as_of_date": evaluation_as_of_date,
        "evaluation_horizon_policy": evaluation_horizon_policy,
        "horizon_unavailable_reason": horizon_unavailable_reason,
    }
