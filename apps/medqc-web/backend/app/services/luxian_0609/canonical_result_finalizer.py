"""LX0609 客户结果的状态一致性与资料缺口补全接口。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from types import NotImplementedType
from typing import Any

from ..luxian_0609_result_schema import CANONICAL_RESULT_STATUSES


_DATA_GAP_EXPLANATIONS = {
    "required_field_missing": {
        "reason_label": "关键字段缺失",
        "missing_sources": [],
        "missing_fields": ["完成判定所需的关键字段"],
        "customer_message": "已读取到相关资料，但缺少完成判定所需的关键字段，暂时无法完成本项质控。",
    },
    "source_unavailable": {
        "reason_label": "数据源未接入",
        "missing_sources": ["质控所需数据源"],
        "missing_fields": [],
        "customer_message": "本项质控所需的数据源尚未接入或本次未读取到，暂时无法完成判定。",
    },
    "source_empty": {
        "reason_label": "未读取到相关资料",
        "missing_sources": ["质控所需资料"],
        "missing_fields": [],
        "customer_message": "本次未读取到完成本项质控所需的相关资料，暂时无法完成判定。",
    },
    "source_truncated": {
        "reason_label": "输入资料不完整",
        "missing_sources": ["超出读取范围的后续资料"],
        "missing_fields": [],
        "customer_message": "相关资料数量超过本次读取范围，当前资料不完整，暂时无法完成本项质控。",
    },
    "source_readiness_unproven": {
        "reason_label": "数据同步状态未确认",
        "missing_sources": ["质控所需资料"],
        "missing_fields": [],
        "customer_message": "本项质控所需资料的同步状态尚未确认，暂时无法判断资料是否完整。",
    },
    "association_failed": {
        "reason_label": "资料关联失败",
        "missing_sources": ["需要相互核对的事件与文书"],
        "missing_fields": [],
        "customer_message": "已读取到相关资料，但暂时无法准确关联对应事件与文书，无法完成本项质控。",
    },
    "linkage_unresolved": {
        "reason_label": "关联资料不足",
        "missing_sources": ["需要相互核对的事件与文书"],
        "missing_fields": [],
        "customer_message": "现有资料不足以确认事件与文书的对应关系，暂时无法完成本项质控。",
    },
    "authoritative_time_missing": {
        "reason_label": "权威时间缺失",
        "missing_sources": [],
        "missing_fields": ["用于计算质控时限的权威时间"],
        "customer_message": "缺少用于计算质控时限的权威时间，暂时无法完成本项质控。",
    },
    "target_report_missing": {
        "reason_label": "目标报告缺失",
        "missing_sources": ["对应的正式检查检验报告"],
        "missing_fields": [],
        "customer_message": (
            "已读取到目标检查检验医嘱，但未读取到对应的正式报告，"
            "暂时无法核对24小时要求。"
        ),
    },
    "authoritative_report_time_missing": {
        "reason_label": "报告时间缺失",
        "missing_sources": [],
        "missing_fields": ["检查检验报告的权威报告时间"],
        "customer_message": "已读取到目标检查检验事件，但缺少权威报告时间，暂时无法核对24小时要求。",
    },
    "authoritative_time_conflict": {
        "reason_label": "权威时间冲突",
        "missing_sources": [],
        "missing_fields": ["相互一致的报告时间与评价截止时间"],
        "customer_message": "报告时间与本次住院的评价截止时间存在冲突，暂时无法完成本项质控。",
    },
    "evaluation_window_not_mature": {
        "reason_label": "评价窗口尚未结束",
        "missing_sources": [],
        "missing_fields": [],
        "customer_message": "截至本次评价日期尚未满规则要求的观察时限，本次暂不判定缺陷。",
    },
    "applicability_source_gap": {
        "reason_label": "适用性资料缺失",
        "missing_sources": ["判断质控点是否适用的关键资料"],
        "missing_fields": [],
        "customer_message": "缺少判断本质控点是否适用的关键资料，暂时无法继续判定。",
    },
}

_RULE_DATA_GAP_EXPLANATIONS = {
    ("LX0609-069", "source_unavailable"): {
        "reason_label": "机构数据源未接入",
        "missing_sources": ["会诊申请时间"],
        "missing_fields": [],
        "customer_message": (
            "当前机构会诊接口未提供会诊申请时间，无法核对会诊记录是否在申请发出后24小时内完成。"
        ),
    },
    ("LX0609-009", "candidate_scope_incomplete"): {
        "reason_label": "自动核对范围超限",
        "missing_sources": [],
        "missing_fields": [],
        "customer_message": (
            "本次病情变化候选超出单次自动核对的安全容量，暂未形成确定结论；"
            "现有资料无需补充，请重新执行本项质控，如仍出现请联系系统管理员。"
        ),
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
        "customer_message": (
            "已读取手术及用药资料，但尚缺切口等级、预防性用药属性或抗菌药物实际给药/"
            "停用时间中的至少一项；医嘱更新时间不能替代实际停用时间。"
        ),
    },
    ("LX0609-031", "association_failed"): {
        "reason_label": "手术签名信息暂无法核对",
        "missing_sources": [],
        "missing_fields": ["主刀医师签名", "手术事件与手术记录的对应关系"],
        "customer_message": (
            "已读取手术主表和手术记录，但尚未取得可与每次手术对应的主刀医师签名，"
            "暂时无法完成签名资格核对。"
        ),
    },
    ("LX0609-048", "transfusion_comparison_fields_unavailable"): {
        "reason_label": "术中输血比对资料不完整",
        "missing_sources": [],
        "missing_fields": [],
        "customer_message": (
            "已确认存在术中输血，但三份文书的比对资料不完整，暂时无法完成一致性核对。"
        ),
    },
}

_DEFAULT_DATA_GAP_EXPLANATION = {
    "reason_label": "现有资料不足",
    "missing_sources": ["完成本项质控所需资料"],
    "missing_fields": [],
    "customer_message": "现有资料不足，暂时无法完成本项质控；请补充或同步相关资料后重新评估。",
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

_SURGERY_PRESENCE_DOCUMENT_TARGETS = {
    "LX0609-030": "surgery_record",
    "LX0609-032": "surgery_safecheck_record",
}


def _safe_surgery_presence_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """校验 030/032 执行器已判定的安全展示事实，不重算业务结论。"""

    if not isinstance(raw, Mapping):
        return None
    target_document = _SURGERY_PRESENCE_DOCUMENT_TARGETS[rule_id]
    if (
        raw.get("verification_kind") == "surgery_document_present"
        and raw.get("target_document") == target_document
        and raw.get("performed_surgery_confirmed") is True
    ):
        return {
            "verification_kind": "surgery_document_present",
            "target_document": target_document,
            "performed_surgery_confirmed": True,
        }
    failure_kind = raw.get("failure_kind")
    if (
        failure_kind not in {"surgery_document_missing", "surgery_document_blank"}
        or raw.get("target_document") != target_document
        or raw.get("performed_surgery_confirmed") is not True
    ):
        return None
    return {
        "failure_kind": failure_kind,
        "target_document": target_document,
        "performed_surgery_confirmed": True,
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
    from .consultation_customer_projection import (
        is_consultation_customer_rule,
        safe_consultation_customer_display_facts,
    )
    from .exam_lab_result_mapping import (
        is_exam_lab_customer_rule,
        safe_exam_lab_customer_display_facts,
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

    if rule_id in _SURGERY_PRESENCE_DOCUMENT_TARGETS:
        safe_facts = _safe_surgery_presence_customer_display_facts(
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

    return (
        rule_id in _SURGERY_PRESENCE_DOCUMENT_TARGETS
        or is_surgery_gate_customer_rule(rule_id)
        or is_surgery_document_customer_rule(rule_id)
        or is_surgery_mdt_customer_rule(rule_id)
        or is_course_quality_customer_rule(rule_id)
        or is_tumor_pathology_customer_rule(rule_id)
        or is_difficult_case_customer_rule(rule_id)
        or is_death_document_customer_rule(rule_id)
        or is_consultation_customer_rule(rule_id)
        or is_exam_lab_customer_rule(rule_id)
        or is_transfusion_customer_rule(rule_id)
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
    rule_id = str(finalized.get("rule_id") or finalized.get("rule_code") or "")
    if (
        safe_facts is not None
        and is_transfusion_customer_rule(
            str(finalized.get("rule_id") or finalized.get("rule_code") or "")
        )
        and not transfusion_customer_fact_status_is_valid(
            rule_id=str(finalized.get("rule_id") or finalized.get("rule_code") or ""),
            status=str(finalized.get("status") or "").strip().lower(),
            safe_facts=safe_facts,
        )
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
    if raw_facts is None and surgery_gate_status_valid:
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
    default_customer_message = defaults["customer_message"]
    if (
        rule_id == "LX0609-048"
        and reason_code == "transfusion_comparison_fields_unavailable"
        and missing_sources
    ):
        default_customer_message = (
            f"已确认存在术中输血，但缺少{'、'.join(missing_sources)}，"
            "暂时无法完成手术记录、麻醉记录单和术后首次病程记录的一致性核对。"
        )
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
