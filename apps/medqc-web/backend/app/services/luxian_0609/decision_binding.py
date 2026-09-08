"""把规则决策绑定到本次 EvidenceSnapshot，并统一归约客户六态。"""

from __future__ import annotations

import logging
import re

from .decision_model import (
    ApplicabilityState,
    CriterionStatus,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .decision_reducer import (
    ReducedRuleDecision,
    reduce_luxian_0609_rule_decision,
)
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .rule_contracts import load_luxian_0609_rule_contracts
from .source_registry import (
    resolve_luxian_0609_controlled_fact_source_keys,
    resolve_luxian_0609_decision_support_source_keys,
    resolve_luxian_0609_rule_sources,
)


_BINDING_EVALUATOR_VERSION = "decision-binding-v1"
_RULE_ID_PATTERN = re.compile(r"^LX0609-\d{3}$")
logger = logging.getLogger(__name__)


def _technical_decision(
    *,
    rule_id: str,
    snapshot_hash: str,
    reason_code: str,
) -> RuleDecision:
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot_hash,
        applicability=ApplicabilityState.ERROR,
        evidence_state=EvidenceState.TECHNICAL_ERROR,
        qc_direction=QcDirection.UNKNOWN,
        reason_code=reason_code,
        fact_refs=(),
        evaluator_version=_BINDING_EVALUATOR_VERSION,
        confidence=None,
    )


def _allowed_source_keys(rule_id: str) -> frozenset[str]:
    entries = resolve_luxian_0609_rule_sources((rule_id,))[rule_id]
    return frozenset(
        {
            *(entry.document_type for entry in entries),
            *(source_key for entry in entries for source_key in entry.source_keys),
            *resolve_luxian_0609_controlled_fact_source_keys((rule_id,)),
            *resolve_luxian_0609_decision_support_source_keys((rule_id,)),
        }
    )


def _allowed_snapshot_refs(
    *, rule_id: str, snapshot: Luxian0609EvidenceSnapshot
) -> frozenset[str]:
    allowed_sources = _allowed_source_keys(rule_id)
    return frozenset(
        {
            *(
                fact.fact_id
                for fact in snapshot.facts
                if fact.source_key in allowed_sources
            ),
            *(
                observation.snapshot_ref.removeprefix("sha256:")
                for observation in snapshot.observations
                if observation.source_key in allowed_sources
            ),
        }
    )


def _allowed_material_document_refs(
    *,
    rule_id: str,
    snapshot: Luxian0609EvidenceSnapshot,
    evidence_materials: Luxian0609EvidenceMaterialStore | None,
    candidate_refs: frozenset[str],
    document_rows_cache: dict[str, tuple[tuple[str, object], ...] | None],
) -> frozenset[str]:
    """仅为疑似文书引用验证规则允许来源的请求内材料。"""

    if (
        not candidate_refs.intersection(snapshot.document_refs)
        or not isinstance(evidence_materials, Luxian0609EvidenceMaterialStore)
    ):
        return frozenset()
    allowed: set[str] = set()
    for source_key in _allowed_source_keys(rule_id):
        if not evidence_materials.has_source(source_key):
            continue
        document_rows = document_rows_cache.get(source_key)
        if document_rows is None and source_key not in document_rows_cache:
            try:
                document_rows = tuple(
                    evidence_materials.document_rows(source_key, snapshot=snapshot)
                )
            except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated, TypeError, ValueError):
                document_rows_cache[source_key] = None
                continue
            document_rows_cache[source_key] = document_rows
        if document_rows is not None:
            allowed.update(document_ref for document_ref, _ in document_rows)
            if candidate_refs.issubset(allowed):
                break
    return frozenset(allowed)


def _requires_evidence_ref(decision: RuleDecision) -> bool:
    if (
        decision.rule_id in {
            "LX0609-020",
            "LX0609-021",
            "LX0609-022",
            "LX0609-023",
        }
        and
        decision.applicability is ApplicabilityState.NOT_APPLICABLE
        and decision.reason_code == "trigger_absent_complete"
    ):
        # 会诊族已经由正式 episode 执行器证明来源完整；“不存在会诊事件”本身
        # 没有可定位文书。这里只豁免已迁移规则族，避免改变其他规则的旧合同。
        return False
    return (
        decision.applicability is ApplicabilityState.NOT_APPLICABLE
        or (
            decision.applicability is ApplicabilityState.APPLICABLE
            and decision.evidence_state is EvidenceState.SUFFICIENT
            and decision.qc_direction
            in {QcDirection.SATISFIED, QcDirection.DEFECT}
        )
    )


def _criterion_results_match_decision(decision: RuleDecision) -> bool:
    contract = next(
        (
            item
            for item in load_luxian_0609_rule_contracts()
            if item.rule_id == decision.rule_id
        ),
        None,
    )
    if contract is None:
        return False
    expected_ids = tuple(item.criterion_id for item in contract.criteria)
    actual_ids = tuple(item.criterion_id for item in decision.criterion_results)
    if not expected_ids:
        return not actual_ids
    # 规则族按批迁移到子判定合同：绑定层先验证已经输出的子判定，是否为
    # 可信目录中的有序前缀；是否覆盖全部子项由对应规则族验收负责。这样既
    # 不允许执行器伪造/乱序子项，也不会在迁移窗口把旧的有效结论整体打成
    # 技术异常。
    if not actual_ids:
        return True
    if actual_ids != expected_ids[: len(actual_ids)]:
        return False
    statuses = tuple(item.status for item in decision.criterion_results)
    if decision.applicability in {
        ApplicabilityState.ERROR,
        ApplicabilityState.NOT_APPLICABLE,
    }:
        return True
    if decision.evidence_state is EvidenceState.SUFFICIENT:
        if decision.qc_direction is QcDirection.SATISFIED:
            return all(status is CriterionStatus.PASSED for status in statuses)
        if decision.qc_direction is QcDirection.DEFECT:
            # “任一子项失败即不合规”的规则中，一个已证实失败的子项足以
            # 形成缺陷；其余子项仍可如实保留 unknown，不能反过来把已证实
            # 的问题降成数据不足。
            return CriterionStatus.FAILED in statuses
    if decision.evidence_state in {EvidenceState.DATA_GAP, EvidenceState.CONFLICT}:
        return (
            CriterionStatus.FAILED not in statuses
            and (
                CriterionStatus.UNKNOWN in statuses
                or len(actual_ids) < len(expected_ids)
            )
        )
    return False


def bind_and_reduce_luxian_0609_rule_decisions(
    *,
    decisions: tuple[RuleDecision, ...],
    expected_rule_ids: tuple[str, ...],
    snapshot: Luxian0609EvidenceSnapshot,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
) -> tuple[ReducedRuleDecision, ...]:
    """逐规则校验 snapshot/ref；伪绑定只污染该规则，不回退旧链。"""

    if type(decisions) is not tuple or any(
        type(item) is not RuleDecision for item in decisions
    ):
        raise TypeError("decisions must be an exact tuple of RuleDecision")
    if (
        type(expected_rule_ids) is not tuple
        or not expected_rule_ids
        or len(expected_rule_ids) != len(set(expected_rule_ids))
        or any(
            not isinstance(rule_id, str)
            or not _RULE_ID_PATTERN.fullmatch(rule_id)
            for rule_id in expected_rule_ids
        )
    ):
        raise ValueError("invalid expected decision scope")
    try:
        resolve_luxian_0609_rule_sources(expected_rule_ids)
    except ValueError as exc:
        raise ValueError("invalid expected decision scope") from exc
    if not isinstance(snapshot, Luxian0609EvidenceSnapshot):
        raise TypeError("snapshot must be Luxian0609EvidenceSnapshot")

    decisions_by_rule_id: dict[str, list[RuleDecision]] = {}
    for decision in decisions:
        decisions_by_rule_id.setdefault(decision.rule_id, []).append(decision)

    missing_rule_ids = tuple(
        rule_id for rule_id in expected_rule_ids if rule_id not in decisions_by_rule_id
    )
    duplicate_rule_ids = tuple(
        rule_id
        for rule_id in expected_rule_ids
        if len(decisions_by_rule_id.get(rule_id, ())) > 1
    )
    unexpected_rule_ids = tuple(
        sorted(set(decisions_by_rule_id).difference(expected_rule_ids))
    )
    if missing_rule_ids or duplicate_rule_ids or unexpected_rule_ids:
        logger.warning(
            "LX0609 decision scope mismatch: missing=%s duplicate=%s unexpected=%s",
            missing_rule_ids,
            duplicate_rule_ids,
            unexpected_rule_ids,
        )

    decisions = tuple(
        candidates[0]
        if len(candidates := decisions_by_rule_id.get(rule_id, ())) == 1
        else _technical_decision(
            rule_id=rule_id,
            snapshot_hash=snapshot.snapshot_hash,
            reason_code="decision_contract_violation",
        )
        for rule_id in expected_rule_ids
    )

    reduced: list[ReducedRuleDecision] = []
    document_rows_cache: dict[str, tuple[tuple[str, object], ...] | None] = {}
    for decision in decisions:
        allowed_refs = _allowed_snapshot_refs(
            rule_id=decision.rule_id,
            snapshot=snapshot,
        )
        candidate_document_refs = frozenset(decision.fact_refs).difference(allowed_refs)
        if candidate_document_refs:
            allowed_refs = allowed_refs.union(
                _allowed_material_document_refs(
                    rule_id=decision.rule_id,
                    snapshot=snapshot,
                    evidence_materials=evidence_materials,
                    candidate_refs=candidate_document_refs,
                    document_rows_cache=document_rows_cache,
                )
            )
        snapshot_binding_valid = (
            decision.snapshot_hash == snapshot.snapshot_hash
            and set(decision.fact_refs).issubset(allowed_refs)
            and (not _requires_evidence_ref(decision) or bool(decision.fact_refs))
        )
        if not snapshot_binding_valid:
            bound = _technical_decision(
                rule_id=decision.rule_id,
                snapshot_hash=snapshot.snapshot_hash,
                reason_code="snapshot_mismatch",
            )
        elif not _criterion_results_match_decision(decision):
            bound = _technical_decision(
                rule_id=decision.rule_id,
                snapshot_hash=snapshot.snapshot_hash,
                reason_code="decision_contract_violation",
            )
        else:
            bound = decision
        try:
            reduced.append(reduce_luxian_0609_rule_decision(bound))
        except (TypeError, ValueError):
            reduced.append(
                reduce_luxian_0609_rule_decision(
                    _technical_decision(
                        rule_id=decision.rule_id,
                        snapshot_hash=snapshot.snapshot_hash,
                        reason_code="decision_contract_violation",
                    )
                )
            )
    return tuple(reduced)


__all__ = ["bind_and_reduce_luxian_0609_rule_decisions"]
