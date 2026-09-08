"""LX0609 客户结果的状态一致性与资料缺口补全接口。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from types import NotImplementedType
from typing import TYPE_CHECKING, Any, Callable

from ..luxian_0609_result_schema import CANONICAL_RESULT_STATUSES
from .customer_evidence_enrichment import (
    enrich_customer_evidence,
    project_legacy_source_level_evidence,
    project_selected_document_evidence,
)
from .customer_renderer import (
    customer_finding_from_controlled_facts,
    render_luxian_0609_customer_result,
)

if TYPE_CHECKING:
    from .decision_reducer import ReducedRuleDecision


SafeTraceSink = Callable[[Mapping[str, Any]], None]


_DATA_GAP_EXPLANATIONS = {
    "required_field_missing": {
        "reason_label": "关键字段缺失",
        "missing_sources": [],
        "missing_fields": ["完成判定所需的关键字段"],
    },
    "source_unavailable": {
        "reason_label": "数据源未接入",
        "missing_sources": ["质控所需数据源"],
        "missing_fields": [],
    },
    "source_empty": {
        "reason_label": "未读取到相关资料",
        "missing_sources": ["质控所需资料"],
        "missing_fields": [],
    },
    "source_truncated": {
        "reason_label": "输入资料不完整",
        "missing_sources": ["超出读取范围的后续资料"],
        "missing_fields": [],
    },
    "source_readiness_unproven": {
        "reason_label": "数据同步状态未确认",
        "missing_sources": ["质控所需资料"],
        "missing_fields": [],
    },
    "association_failed": {
        "reason_label": "资料关联失败",
        "missing_sources": ["需要相互核对的事件与文书"],
        "missing_fields": [],
    },
    "linkage_unresolved": {
        "reason_label": "关联资料不足",
        "missing_sources": ["需要相互核对的事件与文书"],
        "missing_fields": [],
    },
    "authoritative_time_missing": {
        "reason_label": "权威时间缺失",
        "missing_sources": [],
        "missing_fields": ["用于计算质控时限的权威时间"],
    },
    "target_report_missing": {
        "reason_label": "目标报告缺失",
        "missing_sources": ["对应的正式检查检验报告"],
        "missing_fields": [],
    },
    "authoritative_report_time_missing": {
        "reason_label": "报告时间缺失",
        "missing_sources": [],
        "missing_fields": ["检查检验报告的权威报告时间"],
    },
    "authoritative_time_conflict": {
        "reason_label": "权威时间冲突",
        "missing_sources": [],
        "missing_fields": ["相互一致的报告时间与评价截止时间"],
    },
    "evaluation_window_not_mature": {
        "reason_label": "评价窗口尚未结束",
        "missing_sources": [],
        "missing_fields": [],
    },
    "applicability_source_gap": {
        "reason_label": "适用性资料缺失",
        "missing_sources": ["判断质控点是否适用的关键资料"],
        "missing_fields": [],
    },
}

_RULE_DATA_GAP_EXPLANATIONS = {
    ("LX0609-069", "source_unavailable"): {
        "reason_label": "机构数据源未接入",
        "missing_sources": ["会诊申请时间"],
        "missing_fields": [],
    },
    ("LX0609-009", "candidate_scope_incomplete"): {
        "reason_label": "自动核对范围超限",
        "missing_sources": [],
        "missing_fields": [],
    },
    ("LX0609-028", "required_field_missing"): {
        "reason_label": "预防性抗菌药物时长字段不完整",
        "missing_sources": [],
        "missing_fields": [
            "手术切口等级",
            "预防性用药属性",
            "抗菌药物实际给药时间",
            "抗菌药物实际停用时间",
        ],
    },
    ("LX0609-031", "association_failed"): {
        "reason_label": "手术签名信息暂无法核对",
        "missing_sources": [],
        "missing_fields": ["主刀医师签名", "手术事件与手术记录的对应关系"],
    },
    ("LX0609-048", "transfusion_comparison_fields_unavailable"): {
        "reason_label": "术中输血比对资料不完整",
        "missing_sources": [],
        "missing_fields": [],
    },
}

_DEFAULT_DATA_GAP_EXPLANATION = {
    "reason_label": "现有资料不足",
    "missing_sources": ["完成本项质控所需资料"],
    "missing_fields": [],
}

_CUSTOMER_SOURCE_LABELS = {
    "labtest_item_report": "检验结果明细",
    "exam_item_report": "检查报告明细",
    "consultation_record": "会诊记录",
    "inpat_drug_order": "药品医嘱",
    "inpat_nondrug_order": "非药品医嘱",
    "physician_change_event": "经治医师变更记录",
    "medical_order": "诊疗医嘱",
    "inpat_bill_item": "住院收费明细",
    "surgery_risk_assessment": "手术风险评估",
    "surgery_record": "手术记录",
    "anesthesia_record": "麻醉记录单",
    "postsurg_firstcourse_record": "术后首次病程记录",
    "exam_attention_report": "检查危急值报告",
    "lab_attention_report": "检验危急值报告",
}

def validate_luxian_0609_executor_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None | NotImplementedType:
    """接收执行器已验证的客户事实，拒绝任何内部文书标识。"""

    private_keys = frozenset(
        {
            "source_document_id",
            "source_document_ids",
            "source_document_refs",
            "trigger_order_id",
            "trigger_source",
        }
    )

    def contains_private_identifier(value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(
                not isinstance(key, str)
                or key in private_keys
                or contains_private_identifier(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple)):
            return any(contains_private_identifier(item) for item in value)
        return False

    # 规则族的受控字段合同仍由其执行器侧投影器拥有；Finalizer 只提供
    # 一个统一接收边界，避免聚合层重新解释客户事实。
    from .basic_timeliness_customer_projection import (
        is_basic_timeliness_customer_rule,
        safe_basic_timeliness_customer_display_facts,
    )
    from .antimicrobial_result_mapping import (
        is_antimicrobial_customer_rule,
        safe_antimicrobial_customer_display_facts,
    )
    from .postoperative_result_mapping import (
        is_postoperative_customer_rule,
        safe_postoperative_customer_display_facts,
    )
    from .consultation_customer_projection import (
        is_consultation_customer_rule,
        safe_consultation_customer_display_facts,
    )
    from .exam_lab_result_mapping import (
        is_exam_lab_customer_rule,
        safe_exam_lab_customer_display_facts,
    )
    from .critical_value_result_mapping import (
        is_critical_value_customer_rule,
        safe_critical_value_customer_display_facts,
    )
    from .transfusion_result_mapping import (
        is_transfusion_customer_rule,
        safe_transfusion_customer_display_facts,
    )
    from .surgery_gate_result_mapping import (
        is_surgery_gate_customer_rule,
        safe_surgery_gate_customer_display_facts,
    )
    from .surgery_document_result_mapping import (
        is_surgery_document_customer_rule,
        safe_surgery_document_customer_display_facts,
    )
    from .surgery_mdt_result_mapping import (
        is_surgery_mdt_customer_rule,
        safe_surgery_mdt_customer_display_facts,
    )
    from .course_quality_result_mapping import (
        is_course_quality_customer_rule,
        safe_course_quality_customer_display_facts,
    )
    from .tumor_pathology_result_mapping import (
        is_tumor_pathology_customer_rule,
        safe_tumor_pathology_customer_display_facts,
    )
    from .difficult_case_result_mapping import (
        is_difficult_case_customer_rule,
        safe_difficult_case_customer_display_facts,
    )
    from .death_document_result_mapping import (
        is_death_document_customer_rule,
        safe_death_document_customer_display_facts,
    )
    from .discharge_result_mapping import (
        is_discharge_customer_rule,
        safe_discharge_customer_display_facts,
    )
    from .continuity_result_mapping import (
        is_continuity_customer_rule,
        safe_continuity_customer_display_facts,
    )
    from .surgery_presence_result_mapping import (
        is_surgery_presence_customer_rule,
        safe_surgery_presence_customer_display_facts,
    )

    if is_surgery_presence_customer_rule(rule_id):
        safe_facts = safe_surgery_presence_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_continuity_customer_rule(rule_id):
        safe_facts = safe_continuity_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_surgery_gate_customer_rule(rule_id):
        safe_facts = safe_surgery_gate_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_surgery_document_customer_rule(rule_id):
        safe_facts = safe_surgery_document_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_surgery_mdt_customer_rule(rule_id):
        safe_facts = safe_surgery_mdt_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_course_quality_customer_rule(rule_id):
        safe_facts = safe_course_quality_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_tumor_pathology_customer_rule(rule_id):
        safe_facts = safe_tumor_pathology_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_difficult_case_customer_rule(rule_id):
        safe_facts = safe_difficult_case_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_death_document_customer_rule(rule_id):
        safe_facts = safe_death_document_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_discharge_customer_rule(rule_id):
        safe_facts = safe_discharge_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_consultation_customer_rule(rule_id):
        safe_facts = safe_consultation_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_exam_lab_customer_rule(rule_id):
        safe_facts = safe_exam_lab_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_critical_value_customer_rule(rule_id):
        safe_facts = safe_critical_value_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_antimicrobial_customer_rule(rule_id):
        safe_facts = safe_antimicrobial_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_postoperative_customer_rule(rule_id):
        safe_facts = safe_postoperative_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if is_transfusion_customer_rule(rule_id):
        safe_facts = safe_transfusion_customer_display_facts(
            rule_id=rule_id,
            raw=raw,
        )
        return (
            safe_facts
            if safe_facts is not None and not contains_private_identifier(safe_facts)
            else None
        )
    if not is_basic_timeliness_customer_rule(rule_id):
        return NotImplemented
    if not isinstance(raw, Mapping) or contains_private_identifier(raw):
        return None
    return safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=raw)


def finalizer_owns_executor_customer_display_facts(rule_id: str) -> bool:
    """返回由 Finalizer 负责 fail-closed 收敛的执行器事实合同。

    该函数只暴露合同归属，不解释规则的业务状态或事实；聚合器据此把单规则原始
    facts 交给统一 Finalizer，避免继续持有会诊族的失败语义。
    """

    from .consultation_customer_projection import is_consultation_customer_rule
    from .exam_lab_result_mapping import is_exam_lab_customer_rule
    from .transfusion_result_mapping import is_transfusion_customer_rule
    from .surgery_gate_result_mapping import is_surgery_gate_customer_rule
    from .surgery_document_result_mapping import is_surgery_document_customer_rule
    from .surgery_mdt_result_mapping import is_surgery_mdt_customer_rule
    from .course_quality_result_mapping import is_course_quality_customer_rule
    from .tumor_pathology_result_mapping import is_tumor_pathology_customer_rule
    from .difficult_case_result_mapping import is_difficult_case_customer_rule
    from .death_document_result_mapping import is_death_document_customer_rule
    from .discharge_result_mapping import is_discharge_customer_rule
    from .critical_value_result_mapping import is_critical_value_customer_rule
    from .basic_timeliness_customer_projection import is_basic_timeliness_customer_rule
    from .antimicrobial_result_mapping import is_antimicrobial_customer_rule
    from .postoperative_result_mapping import is_postoperative_customer_rule
    from .continuity_result_mapping import is_continuity_customer_rule
    from .surgery_presence_result_mapping import is_surgery_presence_customer_rule

    return (
        is_surgery_presence_customer_rule(rule_id)
        or is_surgery_gate_customer_rule(rule_id)
        or is_surgery_document_customer_rule(rule_id)
        or is_surgery_mdt_customer_rule(rule_id)
        or is_course_quality_customer_rule(rule_id)
        or is_tumor_pathology_customer_rule(rule_id)
        or is_difficult_case_customer_rule(rule_id)
        or is_death_document_customer_rule(rule_id)
        or is_discharge_customer_rule(rule_id)
        or is_consultation_customer_rule(rule_id)
        or is_exam_lab_customer_rule(rule_id)
        or is_critical_value_customer_rule(rule_id)
        or is_basic_timeliness_customer_rule(rule_id)
        or is_antimicrobial_customer_rule(rule_id)
        or is_postoperative_customer_rule(rule_id)
        or is_transfusion_customer_rule(rule_id)
        or is_continuity_customer_rule(rule_id)
    )


def finalizer_requires_public_fact_ref_evidence(rule_id: str) -> bool:
    """返回仅允许公共逐行 fact_refs 投影证据的已迁出合同。

    此处只声明证据所有权，聚合器据此停止旧来源级反查；不选择文书、也不拼装
    客户证据。其他已迁移规则族保持其已冻结的兼容证据合同。
    """

    from .critical_value_result_mapping import is_critical_value_customer_rule
    from .basic_timeliness_customer_projection import is_basic_timeliness_customer_rule
    from .antimicrobial_result_mapping import is_antimicrobial_customer_rule
    from .discharge_result_mapping import is_discharge_customer_rule
    from .postoperative_result_mapping import is_postoperative_customer_rule
    from .transfusion_result_mapping import is_transfusion_public_fact_ref_evidence_rule
    from .continuity_result_mapping import is_continuity_customer_rule
    from .surgery_mdt_result_mapping import is_surgery_mdt_customer_rule
    from .surgery_document_result_mapping import (
        is_surgery_document_public_fact_ref_evidence_rule,
    )

    return (
        is_discharge_customer_rule(rule_id)
        or is_critical_value_customer_rule(rule_id)
        or is_basic_timeliness_customer_rule(rule_id)
        or is_antimicrobial_customer_rule(rule_id)
        or is_postoperative_customer_rule(rule_id)
        or is_transfusion_public_fact_ref_evidence_rule(rule_id)
        or is_continuity_customer_rule(rule_id)
        or is_surgery_mdt_customer_rule(rule_id)
        or is_surgery_document_public_fact_ref_evidence_rule(rule_id)
    )


def finalizer_rejects_invalid_public_executor_customer_display_facts(
    rule_id: str,
) -> bool:
    """返回仍需保持公共 direct 聚合入口 ValueError 的已迁出合同。"""

    from .antimicrobial_result_mapping import is_antimicrobial_customer_rule
    from .basic_timeliness_customer_projection import is_basic_timeliness_customer_rule
    from .postoperative_result_mapping import is_postoperative_customer_rule
    from .continuity_result_mapping import is_continuity_customer_rule

    return (
        is_antimicrobial_customer_rule(rule_id)
        or is_basic_timeliness_customer_rule(rule_id)
        or is_postoperative_customer_rule(rule_id)
        or is_continuity_customer_rule(rule_id)
    )


def finalizer_validates_missing_executor_customer_display_facts(rule_id: str) -> bool:
    """仅保留需验证缺事实例外的执行器合同，不扩大到其他规则族。"""

    from .surgery_gate_result_mapping import requires_missing_facts_status_validation

    return requires_missing_facts_status_validation(rule_id)


def finalize_luxian_0609_executor_customer_display_facts(
    *,
    result: Mapping[str, Any],
    raw_facts: Any,
    contract_failure: bool = False,
    preserve_legacy_exception: bool = False,
) -> tuple[dict[str, Any], bool]:
    """在单规则边界收敛执行器客户事实合同失败。

    ``handled`` 为 ``False`` 表示该规则不属于已迁出的执行器事实合同，调用方可
    继续使用原有兼容处理。对于已拥有合同的规则，事实无效必须只影响该规则并形成
    ``technical_error``；不得把技术失败误交付成临床结论或资料不足。
    """

    finalized = deepcopy(dict(result))
    if not finalizer_owns_executor_customer_display_facts(
        str(finalized.get("rule_id") or finalized.get("rule_code") or "")
    ):
        return finalized, False
    safe_facts = (
        None
        if contract_failure
        else validate_luxian_0609_executor_customer_display_facts(
            rule_id=str(finalized.get("rule_id") or finalized.get("rule_code") or ""),
            raw=raw_facts,
        )
    )
    if safe_facts is NotImplemented:
        return finalized, False
    from .transfusion_result_mapping import (
        is_transfusion_customer_rule,
        is_transfusion_public_fact_ref_evidence_rule,
        transfusion_customer_fact_status_is_valid,
    )
    from .surgery_gate_result_mapping import (
        is_surgery_gate_customer_rule,
        legacy_surgery_gate_contract_error,
        surgery_gate_customer_fact_status_is_valid,
    )
    from .surgery_document_result_mapping import (
        is_surgery_document_customer_rule,
        surgery_document_customer_fact_status_is_valid,
    )
    from .surgery_mdt_result_mapping import (
        is_surgery_mdt_customer_rule,
        legacy_surgery_mdt_contract_error,
        surgery_mdt_customer_fact_status_is_valid,
    )
    from .course_quality_result_mapping import (
        course_quality_customer_fact_status_is_valid,
        is_course_quality_customer_rule,
    )
    from .difficult_case_result_mapping import (
        difficult_case_customer_fact_status_is_valid,
        is_difficult_case_customer_rule,
    )
    from .death_document_result_mapping import (
        death_document_customer_fact_status_is_valid,
        is_death_document_customer_rule,
    )
    from .discharge_result_mapping import (
        discharge_customer_fact_status_is_valid,
        is_discharge_customer_rule,
    )
    from .critical_value_result_mapping import (
        critical_value_customer_fact_status_is_valid,
        is_critical_value_customer_rule,
    )
    from .tumor_pathology_result_mapping import (
        is_tumor_pathology_customer_rule,
        tumor_pathology_customer_fact_status_is_valid,
    )
    from .basic_timeliness_customer_projection import (
        basic_timeliness_customer_fact_status_is_valid,
        is_basic_timeliness_customer_rule,
    )
    from .antimicrobial_result_mapping import (
        antimicrobial_customer_fact_status_is_valid,
        is_antimicrobial_customer_rule,
    )
    from .postoperative_result_mapping import (
        is_postoperative_customer_rule,
        postoperative_customer_fact_status_is_valid,
    )
    rule_id = str(finalized.get("rule_id") or finalized.get("rule_code") or "")
    transfusion_status_valid = (
        is_transfusion_customer_rule(rule_id)
        and transfusion_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
    )
    if (
        safe_facts is not None
        and is_transfusion_customer_rule(rule_id)
        and not transfusion_status_valid
    ):
        safe_facts = None
    surgery_gate_status_valid = (
        is_surgery_gate_customer_rule(rule_id)
        and surgery_gate_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            reason_code=str(finalized.get("reason_code") or "").strip(),
            raw_facts=raw_facts,
            safe_facts=safe_facts,
        )
    )
    if preserve_legacy_exception:
        legacy_error = legacy_surgery_gate_contract_error(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            reason_code=str(finalized.get("reason_code") or "").strip(),
            raw_facts=raw_facts,
            safe_facts=safe_facts,
        )
        if legacy_error:
            raise ValueError(legacy_error)
        if is_surgery_mdt_customer_rule(rule_id):
            legacy_mdt_error = legacy_surgery_mdt_contract_error(
                raw_facts=raw_facts,
                safe_facts=safe_facts,
            )
            if legacy_mdt_error:
                raise ValueError(legacy_mdt_error)
    if is_surgery_gate_customer_rule(rule_id) and not surgery_gate_status_valid:
        safe_facts = None
    surgery_document_status_valid = (
        is_surgery_document_customer_rule(rule_id)
        and surgery_document_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
    )
    if is_surgery_document_customer_rule(rule_id) and not surgery_document_status_valid:
        safe_facts = None
    surgery_mdt_status_valid = (
        is_surgery_mdt_customer_rule(rule_id)
        and surgery_mdt_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
    )
    if is_surgery_mdt_customer_rule(rule_id) and not surgery_mdt_status_valid:
        safe_facts = None
    course_quality_status_valid = (
        is_course_quality_customer_rule(rule_id)
        and course_quality_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            raw_facts=raw_facts,
            safe_facts=safe_facts,
        )
    )
    if is_course_quality_customer_rule(rule_id) and not course_quality_status_valid:
        safe_facts = None
    difficult_case_status_valid = (
        is_difficult_case_customer_rule(rule_id)
        and difficult_case_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
    )
    if is_difficult_case_customer_rule(rule_id) and not difficult_case_status_valid:
        safe_facts = None
    death_document_status_valid = (
        is_death_document_customer_rule(rule_id)
        and death_document_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
    )
    if is_death_document_customer_rule(rule_id) and not death_document_status_valid:
        safe_facts = None
    discharge_status_valid = (
        is_discharge_customer_rule(rule_id)
        and discharge_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
    )
    if is_discharge_customer_rule(rule_id) and not discharge_status_valid:
        safe_facts = None
    critical_value_status_valid = (
        is_critical_value_customer_rule(rule_id)
        and critical_value_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
    )
    if is_critical_value_customer_rule(rule_id) and not critical_value_status_valid:
        safe_facts = None
    tumor_pathology_status_valid = (
        is_tumor_pathology_customer_rule(rule_id)
        and tumor_pathology_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
    )
    if is_tumor_pathology_customer_rule(rule_id) and not tumor_pathology_status_valid:
        safe_facts = None
    basic_timeliness_status_valid = (
        is_basic_timeliness_customer_rule(rule_id)
        and basic_timeliness_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
    )
    if is_basic_timeliness_customer_rule(rule_id) and not basic_timeliness_status_valid:
        safe_facts = None
    antimicrobial_status_valid = (
        is_antimicrobial_customer_rule(rule_id)
        and antimicrobial_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
    )
    if is_antimicrobial_customer_rule(rule_id) and not antimicrobial_status_valid:
        safe_facts = None
    postoperative_status_valid = (
        is_postoperative_customer_rule(rule_id)
        and postoperative_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
    )
    if is_postoperative_customer_rule(rule_id) and not postoperative_status_valid:
        safe_facts = None
    if raw_facts is None and (
        surgery_gate_status_valid
        or postoperative_status_valid
        or (
            is_transfusion_public_fact_ref_evidence_rule(rule_id)
            and transfusion_status_valid
        )
    ):
        finalized.pop("customer_display_facts", None)
        return finalized, True
    if safe_facts is not None:
        finalized["customer_display_facts"] = safe_facts
        return finalized, True

    original_status = str(finalized.get("status") or "").strip().lower()
    original_reason_code = str(finalized.get("reason_code") or "").strip()
    # 合同失败不应保留由无效 facts 导出的临床结论、证据或资料缺口说明。
    for key in (
        "customer_display_facts",
        "customer_evidence",
        "criterion_results",
        "data_gap_details",
        "missing_sources",
        "missing_fields",
        "customer_message",
        "findings",
        "evidence",
        "suggestion",
        "evidence_items",
    ):
        finalized.pop(key, None)
    finalized["status"] = "technical_error"
    finalized["result_status"] = "technical_error"
    finalized["is_compliant"] = None
    finalized["reason_code"] = (
        original_reason_code
        if original_status == "technical_error" and original_reason_code
        else "model_invalid_output"
    )
    return finalized, True


def finalize_luxian_0609_reduced_customer_result(
    *,
    decision: "ReducedRuleDecision",
    raw_customer_display_facts: Mapping[str, Any] | None,
    evidence_snapshot: Any,
    evidence_materials: Any,
    trace_sink: SafeTraceSink | None = None,
) -> dict[str, Any]:
    """交付一条已裁决的客户结果，集中事实、文案和证据的唯一所有权。

    调用方只能提供 ``ReducedRuleDecision``、执行器原始事实和冻结证据会话；本
    函数负责事实合同、Renderer、公共证据投影及最终 Canonical 收敛。这样聚合器
    不再根据规则族选择事实合同或证据回退路径。
    """

    from .decision_reducer import ReducedRuleDecision

    if not isinstance(decision, ReducedRuleDecision):
        raise TypeError("decision must be a ReducedRuleDecision")
    if raw_customer_display_facts is not None and not isinstance(
        raw_customer_display_facts, Mapping
    ):
        raise ValueError("invalid customer display facts")

    rule_id = decision.rule_id
    safe_facts = None
    finalizer_owns_facts = finalizer_owns_executor_customer_display_facts(rule_id)
    if raw_customer_display_facts is not None:
        validated_facts = validate_luxian_0609_executor_customer_display_facts(
            rule_id=rule_id,
            raw=raw_customer_display_facts,
        )
        if validated_facts is not NotImplemented:
            safe_facts = validated_facts
        if safe_facts is None and not finalizer_owns_facts:
            raise ValueError("invalid customer display facts")

    result = render_luxian_0609_customer_result(
        decision=decision,
        safe_customer_display_facts=safe_facts,
        trace_sink=trace_sink,
    )
    if safe_facts is not None:
        result["customer_display_facts"] = safe_facts
        precise_findings = customer_finding_from_controlled_facts(
            rule_id=rule_id,
            facts=safe_facts,
        )
        if precise_findings:
            result["findings"] = precise_findings

    if (
        raw_customer_display_facts is not None
        or finalizer_validates_missing_executor_customer_display_facts(rule_id)
    ):
        result, handled = finalize_luxian_0609_executor_customer_display_facts(
            result=result,
            raw_facts=raw_customer_display_facts,
            preserve_legacy_exception=True,
        )
        if handled and "customer_display_facts" not in result:
            return finalize_luxian_0609_canonical_result(result)

    selected_document_evidence = project_selected_document_evidence(
        decision=decision,
        evidence_snapshot=evidence_snapshot,
        evidence_materials=evidence_materials,
    )
    if selected_document_evidence is not None:
        customer_evidence = selected_document_evidence
    elif finalizer_requires_public_fact_ref_evidence(rule_id):
        customer_evidence = []
    else:
        customer_evidence = project_legacy_source_level_evidence(
            decision=decision,
            evidence_snapshot=evidence_snapshot,
            evidence_materials=evidence_materials,
        )
    customer_evidence = enrich_customer_evidence(
        customer_evidence,
        evidence_materials=evidence_materials,
        preferred_source_fields=(
            {"presurg_discussion": "discuss_staff"}
            if rule_id == "LX0609-040" and safe_facts
            and safe_facts.get("mdt_assessment_basis") == "discuss_staff"
            else None
        ),
    )
    if customer_evidence:
        result["customer_evidence"] = customer_evidence
    return finalize_luxian_0609_canonical_result(result)


def _missing_sources_from_customer_facts(result: Mapping[str, Any]) -> list[str]:
    facts = result.get("customer_display_facts")
    if not isinstance(facts, Mapping):
        return []
    raw_values = facts.get("missing_sources")
    if not isinstance(raw_values, (list, tuple)):
        raw_values = [facts.get("missing_source")]
    labels: list[str] = []
    for value in raw_values:
        label = _CUSTOMER_SOURCE_LABELS.get(str(value or "").strip().lower())
        if label and label not in labels:
            labels.append(label)
    return labels


def _complete_data_gap_explanation(result: dict[str, Any]) -> None:
    rule_id = str(result.get("rule_id") or result.get("rule_code") or "").strip().upper()
    reason_code = str(result.get("reason_code") or "").strip().lower()
    defaults = _RULE_DATA_GAP_EXPLANATIONS.get(
        (rule_id, reason_code),
        _DATA_GAP_EXPLANATIONS.get(reason_code, _DEFAULT_DATA_GAP_EXPLANATION),
    )
    existing_details = result.get("data_gap_details")
    from .surgery_gate_result_mapping import surgery_timeliness_gap_display
    surgery_gap = surgery_timeliness_gap_display(result.get("customer_display_facts")) if rule_id == "LX0609-003" else None
    if surgery_gap is not None:
        defaults = {**defaults, "missing_fields": surgery_gap[0]}
    from .course_quality_result_mapping import course_007_gap_display
    course_gap = course_007_gap_display(result.get("customer_display_facts")) if rule_id == "LX0609-007" else None
    if course_gap is not None:
        defaults = {**defaults, "missing_sources": course_gap[0], "missing_fields": course_gap[1], "reason_label": "查房间隔核对资料不足"}
    completed_details = (
        dict(existing_details) if isinstance(existing_details, Mapping) else {}
    )

    def is_present(value: Any) -> bool:
        return value is not None and not (
            isinstance(value, str) and not value.strip()
        )

    def consistent_value(field: str, default: Any) -> Any:
        top_present = field in result and is_present(result.get(field))
        detail_present = field in completed_details and is_present(
            completed_details.get(field)
        )
        top_value = result.get(field)
        detail_value = completed_details.get(field)
        if top_present and detail_present and top_value != detail_value:
            raise ValueError(f"conflicting data gap explanation field: {field}")
        if top_present:
            return top_value
        if detail_present:
            return detail_value
        return default

    missing_sources = list(
        consistent_value(
            "missing_sources",
            _missing_sources_from_customer_facts(result)
            or defaults["missing_sources"],
        )
    )
    missing_fields = list(
        consistent_value("missing_fields", defaults["missing_fields"])
    )
    from .customer_renderer import data_gap_customer_message

    default_customer_message = data_gap_customer_message(
        rule_id=rule_id,
        reason_code=reason_code,
        missing_sources=missing_sources,
    )
    if surgery_gap is not None:
        default_customer_message = surgery_gap[1]
    if course_gap is not None:
        default_customer_message = course_gap[2]
    customer_message = str(
        consistent_value("customer_message", default_customer_message)
    ).strip()
    result["missing_sources"] = missing_sources
    result["missing_fields"] = missing_fields
    result["customer_message"] = customer_message
    detail_reason_code = str(completed_details.get("reason_code") or "").strip().lower()
    if detail_reason_code and detail_reason_code != reason_code:
        raise ValueError("conflicting data gap explanation field: reason_code")
    completed_details.setdefault("reason_code", reason_code)
    completed_details.setdefault("reason_label", defaults["reason_label"])
    completed_details.setdefault("missing_sources", missing_sources)
    completed_details.setdefault("missing_fields", missing_fields)
    completed_details.setdefault("customer_message", customer_message)
    result["data_gap_details"] = completed_details


def _is_compliant_for_status(status: str) -> bool | None:
    if status == "compliant":
        return True
    if status == "non_compliant":
        return False
    return None


def finalize_luxian_0609_canonical_result(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """补齐状态兼容字段与资料缺口说明，不重新判定业务状态。"""

    if not isinstance(result, Mapping):
        raise TypeError("result must be a mapping")
    rule_id = str(result.get("rule_id") or result.get("rule_code") or "").strip().upper()
    if not rule_id:
        raise ValueError("canonical result requires rule_id")
    status = str(result.get("status") or "").strip().lower()
    if status not in CANONICAL_RESULT_STATUSES:
        raise ValueError("canonical result has invalid status")

    finalized = deepcopy(dict(result))
    finalized["rule_id"] = rule_id
    finalized["status"] = status
    finalized["result_status"] = status
    finalized["is_compliant"] = _is_compliant_for_status(status)

    if status == "data_gap":
        _complete_data_gap_explanation(finalized)
    return finalized


def finalize_luxian_0609_missing_decision_result(
    *, wrapper: Mapping[str, Any]
) -> dict[str, Any]:
    """把正式 Canonical 主链缺少裁决收敛为纯技术失败。

    该入口只处理交付合同失败，不读取旧执行结果、临床事实或证据；因此不会
    把编排缺陷伪装成资料不足，也不会把聚合器重新变成规则解释器。
    """

    from ..luxian_0609_result_schema import (
        CUSTOMER_SCHEMA_VERSION,
        RULE_SET_VERSION,
    )
    from ..luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY

    rule_id = str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper()
    if not rule_id:
        raise ValueError("canonical wrapper requires rule_id")
    return finalize_luxian_0609_canonical_result({
        "rule_id": rule_id,
        "rule_code": rule_id,
        "qc_point_id": rule_id,
        "rule_name": str(wrapper.get("name") or wrapper.get("rule_name") or rule_id).strip(),
        "rule_version": str(wrapper.get("rule_version") or "").strip(),
        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
        "schema_version": CUSTOMER_SCHEMA_VERSION,
        "status": "technical_error",
        "reason_code": "decision_contract_violation",
        "findings": "质控执行结果不完整，本项未形成可交付的判定。",
        "evidence": "",
        "suggestion": "请重试本次质控；若仍失败，请检查规则执行与裁决绑定链路。",
        "confidence": 0.0,
        "evidence_items": [],
        "criterion_results": [],
        "metadata": {
            "execution_source": "lx0609_canonical_delivery_guard",
            "executor_type": "program",
            "reason_code": "decision_contract_violation",
            "technical_error_internal": True,
        },
    })
