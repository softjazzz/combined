"""会诊 native 决定的冻结文书证据职责。

本模块只处理两件事：把执行器内部匿名引用稳定回填为同一 Evidence Session 的
逐文书材料引用，以及把已由执行器决定的文书选择转换为 ``RuleDecision.fact_refs``。
它不读取来源、不解释会诊业务状态，也不拼装客户证据 DTO。
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot


class ConsultationEvidenceCandidate(Protocol):
    """执行器候选文书在证据选择边界的最小合同。"""

    ref: str
    material_ref: str


class ConsultationEvidenceEpisode(Protocol):
    """执行器已确定的会诊 episode 文书角色。"""

    episode_ref: str
    application_state: str
    opinion_state: str
    confidence: str
    application_refs: Sequence[str]
    opinion_refs: Sequence[str]


class ConsultationEvidenceRecommendation(Protocol):
    recommendation_ref: str


class ConsultationEvidenceCompletedRecommendation(Protocol):
    """仅传递建议所属 episode 与建议身份，不传正文。"""

    episode_ref: str
    recommendation: ConsultationEvidenceRecommendation


class ConsultationEvidenceAssessment(Protocol):
    recommendation_ref: str
    execution_record_state: str
    trace_refs: Sequence[str]
    execution_refs: Sequence[str]


def bind_document_material_rows(
    *,
    source_key: str,
    rows: Sequence[Mapping[str, Any]],
    materials: Luxian0609EvidenceMaterialStore,
    snapshot: Luxian0609EvidenceSnapshot,
) -> list[dict[str, Any]]:
    """在不改变 ``bounded_rows`` 行序的前提下回填私有材料引用。

    ``document_rows`` 为了材料身份稳定性按 canonical 内容排序。匿名 Prompt 引用
    却依赖来源原始有界顺序；所以只能按原对象 occurrence 回填引用，不能将
    ``document_rows`` 直接作为执行输入。
    """

    refs_by_row_identity: dict[int, list[str]] = {}
    for material_ref, material_row in materials.document_rows(
        source_key,
        snapshot=snapshot,
    ):
        refs_by_row_identity.setdefault(id(material_row), []).append(material_ref)

    bound_rows: list[dict[str, Any]] = []
    for material_row in rows:
        refs = refs_by_row_identity.get(id(material_row), [])
        if not refs:
            raise ValueError("material row reference is unavailable")
        row = dict(material_row)
        row["_material_document_ref"] = refs.pop(0)
        bound_rows.append(row)
    return bound_rows


def material_refs_for_internal_refs(
    *,
    documents: Sequence[Mapping[str, str]],
    candidates: Sequence[ConsultationEvidenceCandidate],
    internal_refs: Sequence[str],
) -> tuple[str, ...]:
    """把匿名文书/候选引用严格映射为真实逐文书材料引用。

    ``internal_refs`` 已是执行器选出的决定性事实。任一引用不能唯一映射到
    当前 Evidence Session 的材料时，继续交付其余证据会造成“部分证据支撑
    完整结论”的假象，因此必须由调用方将该规则收敛为技术失败。
    """

    refs_to_materials: dict[str, set[str]] = {}

    def add_mapping(reference: Any, material_ref: Any) -> None:
        clean_reference = _clean(reference)
        clean_material_ref = _clean(material_ref)
        if clean_reference and clean_material_ref:
            refs_to_materials.setdefault(clean_reference, set()).add(clean_material_ref)

    for item in documents:
        add_mapping(item.get("ref"), item.get("material_ref"))
    for item in candidates:
        add_mapping(
            getattr(item, "ref", ""),
            getattr(item, "material_ref", ""),
        )

    resolved: list[str] = []
    for reference in internal_refs:
        clean_reference = _clean(reference)
        material_refs = refs_to_materials.get(clean_reference, set())
        if not clean_reference or len(material_refs) != 1:
            raise ValueError("consultation internal reference cannot be uniquely bound")
        resolved.append(next(iter(material_refs)))
    return tuple(dict.fromkeys(resolved))


def select_consultation_rule_material_refs(
    *,
    rule_id: str,
    status: str,
    documents: Sequence[Mapping[str, str]],
    reason_code: str,
    episodes: Sequence[ConsultationEvidenceEpisode] = (),
    completed_recommendations: Sequence[ConsultationEvidenceCompletedRecommendation] = (),
    assessments: Sequence[ConsultationEvidenceAssessment] | None = None,
    candidates: Sequence[ConsultationEvidenceCandidate] = (),
) -> tuple[str, ...]:
    """只投影执行器已决定、实际支撑该会诊规则的文书。

    020/023 的意见与执行文书选择来自既有 episode/assessment 结果；本函数不再
    解析正文、匹配建议，也不会从来源级 snapshot 引用推断文书。
    """

    if status in {"data_gap", "technical_error"}:
        return ()
    if status == "not_applicable" and reason_code != "eligibility_not_met":
        return ()
    if rule_id in {"LX0609-03-01-02", "LX0609-03-01-03"}:
        state_field = "application_state" if rule_id == "LX0609-03-01-02" else "opinion_state"
        ref_field = "application_refs" if rule_id == "LX0609-03-01-02" else "opinion_refs"
        selected_refs = tuple(
            dict.fromkeys(
                _clean(reference)
                for item in episodes
                if _clean(getattr(item, state_field)) != "absent"
                for reference in getattr(item, ref_field)
                if _clean(reference)
            )
        )
        if not selected_refs and episodes:
            return ()
        if not selected_refs:
            # 显式短路还没有 episode；执行器已判定的本次会诊文书即为事实来源。
            selected_refs = tuple(
                _clean(item.get("ref")) for item in documents if _clean(item.get("ref"))
            )
        return material_refs_for_internal_refs(
            documents=documents,
            candidates=(),
            internal_refs=selected_refs,
        )

    if rule_id not in {"LX0609-03-01-01", "LX0609-03-01-04"} or not episodes:
        return ()
    assessment_rows = tuple(assessments or ())
    assessment_by_recommendation = {
        _clean(item.recommendation_ref): item
        for item in assessment_rows
        if _clean(item.recommendation_ref)
    }
    missing_episode_refs = {
        _clean(item.episode_ref)
        for item in completed_recommendations
        if (assessment := assessment_by_recommendation.get(
            _clean(item.recommendation.recommendation_ref)
        )) is not None
        and _clean(assessment.execution_record_state) == "no_trace"
        and not assessment.execution_refs
    }
    evidence_episodes = tuple(
        item
        for item in episodes
        if not (
            rule_id == "LX0609-03-01-01"
            and status == "non_compliant"
            and missing_episode_refs
        )
        or _clean(item.episode_ref) in missing_episode_refs
    )
    opinion_refs = tuple(
        dict.fromkeys(
            _clean(reference)
            for item in evidence_episodes
            if (
                _clean(item.opinion_state) == "clear"
                and _clean(item.confidence) == "high"
            )
            for reference in item.opinion_refs
            if _clean(reference)
        )
    )
    candidate_refs: tuple[str, ...] = ()
    if not (rule_id == "LX0609-03-01-01" and status == "non_compliant"):
        candidate_refs = tuple(
            dict.fromkeys(
                _clean(reference)
                for assessment in assessment_rows
                for reference in (
                    *assessment.trace_refs,
                    *assessment.execution_refs,
                )
                if _clean(reference)
            )
        )
    offending_internal_refs: tuple[str, ...] = ()
    if status == "non_compliant":
        recommendation_episode_refs = {
            _clean(item.recommendation.recommendation_ref): _clean(item.episode_ref)
            for item in completed_recommendations
            if _clean(item.recommendation.recommendation_ref)
            and _clean(item.episode_ref)
        }
        episode_by_ref = {
            _clean(item.episode_ref): item
            for item in episodes
            if _clean(item.episode_ref)
        }
        offending_internal_ref_values: list[str] = []
        for assessment in assessment_rows:
            record_state = _clean(assessment.execution_record_state)
            offending = (
                rule_id == "LX0609-03-01-01"
                and record_state == "no_trace"
                and not assessment.execution_refs
            ) or (
                rule_id == "LX0609-03-01-04"
                and (
                    record_state in {"generic_trace", "copied_opinion"}
                    # 用户口径（2026-10-20）：023 只认会诊当日医嘱，找不到医嘱即为缺陷。
                    or (record_state == "no_trace" and not assessment.execution_refs)
                )
            )
            if not offending:
                continue
            episode = episode_by_ref.get(
                recommendation_episode_refs.get(
                    _clean(assessment.recommendation_ref),
                    "",
                )
            )
            if episode is not None:
                offending_internal_ref_values.extend(
                    _clean(reference)
                    for reference in episode.opinion_refs
                    if _clean(reference)
                )
            offending_internal_ref_values.extend(
                _clean(reference)
                for reference in (*assessment.trace_refs, *assessment.execution_refs)
                if _clean(reference)
            )
        offending_internal_refs = tuple(dict.fromkeys(offending_internal_ref_values))

    # 客户证据最多八条。先选中已确认的缺陷会诊/执行文书，再按既有顺序补足，
    # 防止第九次以后的缺陷被上下文截断；截断之外的上下文不是本次决定性引用。
    selected_internal_refs = tuple(
        dict.fromkeys((*offending_internal_refs, *opinion_refs, *candidate_refs))
    )[:8]
    return material_refs_for_internal_refs(
        documents=documents,
        candidates=candidates,
        internal_refs=selected_internal_refs,
    )


def is_material_binding_error(exc: BaseException) -> bool:
    """调用方按来源合同决定是否 fail-closed，模块不私自改业务状态。"""

    return isinstance(
        exc,
        (EvidenceMaterialUnavailable, EvidenceMaterialTruncated, TypeError, ValueError),
    )


def _clean(value: Any) -> str:
    return str(value or "").strip()
