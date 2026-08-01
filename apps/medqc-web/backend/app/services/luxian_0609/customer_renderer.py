"""LX0609 native 决策的客户结果白名单渲染器。"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from ..luxian_0609_rule_catalog import (
    LUXIAN_0609_RULE_SET_KEY,
    get_luxian_0609_rule,
)
from .decision_reducer import CustomerFinalState, ReducedRuleDecision
from .rule_contracts import load_luxian_0609_rule_contracts


CUSTOMER_SCHEMA_VERSION = "lx0609-customer-result-v2"
RULE_SET_VERSION = "2026-06-09"
CUSTOMER_RESULT_KEYS = frozenset(
    {
        "rule_id",
        "rule_code",
        "rule_name",
        "qc_point_id",
        "rule_set_key",
        "rule_set_version",
        "rule_version",
        "schema_version",
        "status",
        "result_status",
        "is_compliant",
        "findings",
        "evidence",
        "suggestion",
        "confidence",
        "reason_code",
        "evidence_items",
        "criterion_results",
    }
)

_SAFE_CODE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
_STATUS_MAP = {
    CustomerFinalState.COMPLIANT: "compliant",
    CustomerFinalState.NON_COMPLIANT: "non_compliant",
    CustomerFinalState.NOT_APPLICABLE: "not_applicable",
    CustomerFinalState.DATA_GAP: "data_gap",
    CustomerFinalState.TECHNICAL_ERROR: "technical_error",
    CustomerFinalState.EVALUATION_UNKNOWN: "uncertain",
}
_CUSTOMER_MESSAGES = {
    CustomerFinalState.COMPLIANT: (
        "符合质控要求",
        "已根据受控证据完成判断。",
        "继续保持。",
    ),
    CustomerFinalState.NON_COMPLIANT: (
        "发现质控问题",
        "受控证据表明本次记录未满足质控要求。",
        "请按质控要求核对并完善相关记录。",
    ),
    CustomerFinalState.NOT_APPLICABLE: (
        "本次就诊不适用该质控点",
        "完整适用性证据未触发本质控点。",
        "无需处理。",
    ),
    CustomerFinalState.DATA_GAP: (
        "现有数据不足",
        "当前受控数据不足以形成确定结论。",
        "请补充或同步所需数据后重新评估。",
    ),
    CustomerFinalState.TECHNICAL_ERROR: (
        "质控执行未完成",
        "本次执行未形成临床结论。",
        "请在技术问题处理后重新评估。",
    ),
    CustomerFinalState.EVALUATION_UNKNOWN: (
        "暂无法形成确定结论",
        "现有受控证据存在冲突或语义不确定性。",
        "建议补充证据后复核。",
    ),
}
_DATA_GAP_MESSAGES = {
    "source_unavailable": (
        "本次未读取到判断所需资料",
        "当前可查看的病历资料不足以完成本项判断。",
        "请确认相关资料已同步完整后重新评估。",
    ),
    "source_truncated": (
        "本次读取的相关资料不完整",
        "当前结果仅依据部分病历资料，暂时不能形成确定结论。",
        "请确认全部相关资料已同步后重新评估。",
    ),
    "source_readiness_unproven": (
        "相关资料是否完整尚待确认",
        "目前无法确认本项判断所需资料是否已经全部读取。",
        "请确认相关资料完整后重新评估。",
    ),
    "required_field_missing": (
        "相关记录缺少判断所需信息",
        "当前读取到的记录中缺少完成本项判断的关键信息。",
        "请核对相关记录内容是否完整后重新评估。",
    ),
    "authoritative_time_missing": (
        "相关记录缺少明确时间",
        "目前缺少本项判断所需的起始、完成或评估时间。",
        "请核对相关记录时间后重新评估。",
    ),
    "linkage_unresolved": (
        "暂未找到可相互核对的对应记录",
        "现有资料中尚未找到能够明确对应的前后记录。",
        "请核对相关记录及时间是否完整后重新评估。",
    ),
    "applicability_source_gap": (
        "暂无法确认本质控点是否适用",
        "现有资料不足以确认本次诊疗是否属于本质控点的检查范围。",
        "请核对相关诊疗记录后重新评估。",
    ),
}
_RULE_DATA_GAP_MESSAGES = {
    "LX0609-011": (
        "暂无法核对 CT/MRI 报告后 24 小时内是否记录病程",
        "当前缺少可关联的检查报告时间、报告类型或报告后病程记录。",
        "请确认 CT/MRI 报告及对应病程记录已完整同步后重新评估。",
    ),
    "LX0609-012": (
        "暂无法核对 CT/MRI 阳性结果是否及时分析",
        "当前缺少可确认的阳性结果、报告时间或报告后 24 小时内的分析记录。",
        "请确认检查结果和对应分析病程已完整同步后重新评估。",
    ),
    "LX0609-014": (
        "暂无法核对细菌培养结果是否在 24 小时内记入病程",
        "当前缺少可关联的细菌培养报告、报告时间或报告后病程记录。",
        "请确认培养报告和对应病程记录已完整同步后重新评估。",
    ),
    "LX0609-015": (
        "暂无法核对阳性菌结果是否在 24 小时内完成分析",
        "当前缺少阳性菌结果、报告时间或对应的分析病程记录。",
        "请确认培养结果和分析病程已完整同步后重新评估。",
    ),
    "LX0609-025": (
        "暂无法核对手术记录中的植入物信息",
        "当前手术记录缺少可核对的植入物名称、种类、规格型号、材质或数量字段，或正文内容不完整。",
        "请确认完整手术记录及植入物明细已同步后重新评估。",
    ),
    "LX0609-028": (
        "暂无法核对预防性抗菌药物使用时长",
        "当前缺少切口等级、预防用药属性或抗菌药物使用起止时间。",
        "请补充手术切口等级和预防用药明细后重新评估。",
    ),
    "LX0609-031": (
        "暂无法核对手术记录是否由术者签名",
        "当前缺少可相互核对的手术者和签名医师字段。",
        "请确认手术者及签名医师信息已完整同步后重新评估。",
    ),
    "LX0609-033": (
        "暂无法确认手术知情同意书是否存在",
        "已确认实施手术，但当前未读取到可核对的手术知情同意书。",
        "请确认手术知情同意书已归档并同步后重新评估。",
    ),
    "LX0609-034": (
        "暂无法确认麻醉知情同意书是否存在",
        "已确认实施麻醉，但当前未读取到可核对的麻醉知情同意书。",
        "请确认麻醉知情同意书已归档并同步后重新评估。",
    ),
    "LX0609-035": (
        "暂无法核对麻醉知情同意书填写是否完整",
        "当前缺少患者或医师签名，以及精确到分钟的签署时间。",
        "请确认麻醉知情同意书签名和签署时间已完整同步后重新评估。",
    ),
    "LX0609-039": (
        "暂无法完整核对术前讨论及术者参加情况",
        "当前缺少急诊抢救手术标志、术前讨论记录或术者参加信息中的至少一项。",
        "请确认手术属性、术前讨论和参加人员信息已完整同步后重新评估。",
    ),
    "LX0609-041": (
        "本次未读取到输血知情同意书",
        "已读取到输血相关记录，但没有可核对的输血知情同意书。",
        "请确认输血知情同意书已归档并同步后重新评估。",
    ),
    "LX0609-042": (
        "输血知情同意书的签名信息不完整",
        "当前资料不足以核对患者、家属或医师签名及签署时间是否完整。",
        "请补充完整的签名和签署时间后重新评估。",
    ),
    "LX0609-043": (
        "输血前检查资料不完整",
        "当前未读取到可完整核对的输血前常规检查项目、结果和检查时间。",
        "请补充输血前检查结果及检查时间后重新评估。",
    ),
    "LX0609-049": (
        "暂时无法核对输血医嘱与收费",
        "已读取到输血记录，但缺少可相互核对的输血医嘱或收费明细。",
        "请确认输血医嘱和收费明细已同步后重新评估。",
    ),
    "LX0609-048": (
        "已确认存在术中输血，但暂无法完成三份文书的一致性核对",
        "当前尚缺手术记录、麻醉记录和术后首次病程中可相互比较的输血成分、剂量或时间信息。",
        "请确认三份文书的输血明细均已完整同步后重新评估。",
    ),
    "LX0609-051": (
        "暂无法确认是否需要核对死亡病历讨论",
        "当前缺少可确认患者死亡状态及死亡时间的权威资料。",
        "请确认死亡状态、死亡时间及死亡讨论记录已完整同步后重新评估。",
    ),
    "LX0609-060": (
        "暂无法确认本次就诊是否属于死亡病例",
        "当前缺少可确认患者死亡状态及死亡时间的权威资料。",
        "请确认住院结局和死亡相关资料已完整同步后重新评估。",
    ),
    "LX0609-062": (
        "暂无法核对出院带药信息是否完整",
        "当前缺少药品名称、剂量、给药途径或用药时间中的至少一项。",
        "请确认出院带药明细已完整同步后重新评估。",
    ),
    "LX0609-069": (
        "暂无法核对会诊记录是否在 24 小时内完成",
        "当前缺少会诊申请时间或会诊记录完成时间。",
        "请确认会诊申请及会诊记录时间已完整同步后重新评估。",
    ),
    "LX0609-071": (
        "暂无法核对交接班记录",
        "当前未读取到经治医师变更事件或对应的交班、接班记录及完成时间。",
        "请确认医师变更和交接班资料已完整同步后重新评估。",
    ),
    "LX0609-072": (
        "暂无法核对转入、转出记录是否在 24 小时内完成",
        "当前读取到的转科医嘱或转入、转出记录不完整。",
        "请确认转科医嘱和转科记录已完整同步后重新评估。",
    ),
    "LX0609-073": (
        "暂无法核对转科医嘱是否具备转入、转出记录",
        "当前读取到的转科医嘱或转入、转出记录不完整。",
        "请确认转科医嘱和转科记录已完整同步后重新评估。",
    ),
}
_RULE_NON_COMPLIANT_MESSAGES = {
    "LX0609-016": (
        "入院记录与首次病程记录存在高度重复",
        "入院记录现病史与首次病程记录病例特点的相似度超过 70% 判定标准。",
        "请结合首次病程记录要求，补充病例特点的归纳、分析和诊疗思路。",
    ),
    "LX0609-023": (
        "会诊意见执行情况记录过于笼统",
        "当前仅记录已按会诊意见执行，未说明具体执行措施、执行结果或后续安排。",
        "请归纳记录会诊意见的具体执行措施、执行结果及后续安排。",
    ),
    "LX0609-036": (
        "已实施麻醉，但缺少麻醉术前或术后访视记录",
        "当前未同时检出麻醉术前访视和麻醉术后访视记录。",
        "请补齐缺失的麻醉访视记录。",
    ),
    "LX0609-044": (
        "本次输血未见输血前评估记录",
        "已核对输血相关记录，未检出可确认适应证、风险或用血必要性的输血前评估。",
        "请在输血前补充完整的评估记录。",
    ),
    "LX0609-047": (
        "本次输血后未见输血效果评价",
        "已核对输血病程及相关病程资料，未检出输血后效果或不良反应评价。",
        "请补充输血后的疗效和不良反应评价。",
    ),
    "LX0609-068": (
        "出院前一天或当天未见上级医师同意出院意见",
        "已核对出院前一天及出院当天的上级医师病程记录，未检出同意出院、准予出院或可以出院意见。",
        "请由上级医师补充明确的同意出院意见。",
    ),
}
_RULE_NOT_APPLICABLE_MESSAGES = {
    ("LX0609-007", "eligibility_not_met"): (
        "本次存在病危或病重医嘱，不按病情稳定患者规则核对",
        "病情稳定患者 3 天查房频次规则仅适用于未下病危、病重医嘱的住院阶段。",
        "无需按本质控点处理。",
    ),
    ("LX0609-008", "trigger_absent_complete"): (
        "本次未发现符合规则定义的有效病重医嘱",
        "病重患者 2 天查房频次规则未被触发。",
        "无需按本质控点处理。",
    ),
    ("LX0609-013", "trigger_absent_complete"): (
        "本次未发现病理检查结果",
        "病理检查主表和报告资料已完成核对，未发现需要在手术记录或病程中追踪的病理结果。",
        "无需按本质控点处理。",
    ),
    ("LX0609-019", "trigger_absent_complete"): (
        "本次未发现病理取材事件",
        "病理检查及手术资料已完成核对，未发现需要记录取材情况的病理事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-024", "trigger_absent_complete"): (
        "本次未触发恶性肿瘤手术规则",
        "现有诊断和手术资料未表明本次属于恶性肿瘤手术。",
        "无需按本质控点处理。",
    ),
    ("LX0609-026", "trigger_absent_complete"): (
        "本次未发现恶性肿瘤化学治疗事件",
        "现有医嘱和病程资料未触发化学治疗记录一致性核对。",
        "无需按本质控点处理。",
    ),
    ("LX0609-027", "trigger_absent_complete"): (
        "本次出院诊断未触发恶性肿瘤治疗计划规则",
        "现有出院诊断未表明本次属于需要核对后续肿瘤治疗计划的病例。",
        "无需按本质控点处理。",
    ),
    ("LX0609-037", "eligibility_not_met"): (
        "已确认实施麻醉，但麻醉术前或术后访视记录缺失，本项规范性检查不再重复判定",
        "麻醉访视记录是否缺失由 LX0609-036 判定；本质控点仅在术前、术后访视记录均存在时核对填写规范。",
        "请先补齐麻醉访视记录，再核对记录填写是否规范。",
    ),
    ("LX0609-074", "trigger_absent_complete"): (
        "本次未发现修正或补充诊断事件",
        "现有诊断记录未触发修改或补充诊断依据核对。",
        "无需按本质控点处理。",
    ),
}
_RULE_UNCERTAIN_MESSAGES = {
    "LX0609-020": (
        "暂无法确认会诊记录单是否具有对应的执行记录",
        "已读取到会诊资料，但当前关联信息不足以确定会诊记录与执行记录的对应关系。",
        "请核对会诊申请、会诊记录及执行记录的时间和关联标识。",
    ),
    "LX0609-023": (
        "暂无法确认会诊意见执行记录是否完成归纳",
        "当前无法确定执行记录是否只是照抄会诊意见，以及是否明确记录了具体执行情况。",
        "请核对会诊意见原文和执行记录，补充具体执行措施及结果。",
    ),
    "LX0609-040": (
        "暂无法确认是否需要进行四级手术术前多学科讨论",
        "当前缺少明确的手术级别或可核对的多学科讨论资料。",
        "请确认手术级别、术前讨论记录及参加科室信息。",
    ),
}

# 合规结果也必须回答“为什么合规”。这里仅使用规则目录身份和 reducer 已确认的
# 终态生成受控短句，不读取病历原文，也不在展示层重新判断规则。
_RULE_COMPLIANT_FINDINGS = {
    "LX0609-001": "已确认入院记录在入院后 24 小时内完成。",
    "LX0609-002": "已确认首次病程记录在入院后 8 小时内完成。",
    "LX0609-003": "已确认手术记录在手术后 24 小时内完成。",
    "LX0609-004": "已确认抢救记录在抢救结束后 6 小时内完成。",
    "LX0609-005": "已确认主治医师首次查房记录在入院后 48 小时内完成。",
    "LX0609-006": "已确认最高级别医师首次查房记录在入院后 72 小时内完成。",
    "LX0609-007": "已核对病情稳定期间的查房记录，未发现超过 3 天的记录缺口。",
    "LX0609-008": "已核对病重期间的查房记录，未发现超过 2 天的记录缺口。",
    "LX0609-009": "已核对病危期间的查房记录，未发现应记录日期缺失。",
    "LX0609-010": "已核对 CT/MRI 检查前病程，已记录检查原因。",
    "LX0609-011": "已确认 CT/MRI 报告结果在出具后 24 小时内记入病程。",
    "LX0609-012": "已确认 CT/MRI 阳性结果在出具后 24 小时内完成分析记录。",
    "LX0609-013": "已确认病理检查结果已在手术记录或病程中记录。",
    "LX0609-014": "已确认细菌培养结果在报告后 24 小时内记入病程。",
    "LX0609-015": "已确认细菌培养阳性结果在报告后 24 小时内完成分析记录。",
    "LX0609-016": "已核对入院记录与首次病程记录，重复程度未达到不合理复制判定标准。",
    "LX0609-017": "已核对病程记录，未发现相似度超过 70% 的重复记录。",
    "LX0609-018": "已确认主诉长度及诊断指向符合书写要求。",
    "LX0609-019": "已确认病理取材情况已在手术记录或病程中记录。",
    "LX0609-020": "已确认会诊记录具备对应的会诊执行记录。",
    "LX0609-021": "已核对会诊申请单，会诊目的表述明确。",
    "LX0609-022": "已核对会诊记录单，会诊意见表述明确。",
    "LX0609-023": "已核对会诊执行记录，已归纳具体执行情况。",
    "LX0609-024": "已核对恶性肿瘤手术记录，淋巴结清扫情况已有记录。",
    "LX0609-025": "已核对手术记录，未发现植入物信息缺项。",
    "LX0609-026": "已核对化学治疗记录与医嘱，未发现用药信息不一致。",
    "LX0609-027": "已核对恶性肿瘤患者出院记录，已记录后续治疗计划。",
    "LX0609-028": "已核对预防性抗菌药物使用时长，符合规定要求。",
    "LX0609-029": "已确认本次手术具备术前小结。",
    "LX0609-030": "已确认本次手术具备手术记录。",
    "LX0609-031": "已核对手术记录签名，签名医师与术者要求相符。",
    "LX0609-032": "已确认本次手术具备手术安全核查表。",
    "LX0609-033": "已确认本次手术具备手术知情同意书。",
    "LX0609-034": "已确认本次麻醉具备麻醉知情同意书。",
    "LX0609-035": "已核对麻醉知情同意书，签名及签署时间完整。",
    "LX0609-036": "已确认本次麻醉具备术前、术后访视记录。",
    "LX0609-037": "已核对麻醉访视记录，填写内容符合要求。",
    "LX0609-038": "已确认本次麻醉具备麻醉记录单。",
    "LX0609-039": "已确认本次手术具备术前讨论记录，且术者参加情况符合要求。",
    "LX0609-040": "已确认四级手术术前已完成多学科讨论。",
    "LX0609-041": "已确认本次输血具备输血知情同意书。",
    "LX0609-042": "已核对输血知情同意书，填写及签名完整。",
    "LX0609-043": "已核对输血前常规检查，所需项目完整。",
    "LX0609-044": "已确认本次输血具备输血前评估记录。",
    "LX0609-045": "已确认本次输血具备输血病程记录。",
    "LX0609-046": "已核对输血病程记录，内容完整且符合要求。",
    "LX0609-047": "已确认输血后已完成评价记录。",
    "LX0609-048": "已核对术中输血相关记录，未发现文书间内容不一致。",
    "LX0609-049": "已核对输血医嘱与收费记录，未发现不一致。",
    "LX0609-051": "已确认死亡后 7 天内完成死亡病历讨论记录。",
    "LX0609-060": "已确认死亡患者具备死亡记录。",
    "LX0609-061": "已确认出院记录在出院后 24 小时内完成。",
    "LX0609-062": "已核对出院带药信息，药名、剂量、途径及用药时间记录完整。",
    "LX0609-064": "已确认术后连续 3 天具备病程记录及术者查房记录。",
    "LX0609-065": "已确认术后 3 天内具备上级医师查房记录。",
    "LX0609-066": "已确认本次手术具备术后首次病程记录。",
    "LX0609-067": "已确认出院前一天或当天具备病程记录。",
    "LX0609-068": "已确认病程中记录了上级医师同意出院意见。",
    "LX0609-069": "已确认会诊记录在会诊申请后 24 小时内完成。",
    "LX0609-071": "已核对经治医师变更记录，交接班文书及完成时间符合要求。",
    "LX0609-072": "已确认转科后 24 小时内完成转入、转出记录。",
    "LX0609-073": "已确认转科医嘱具备对应的转入、转出记录。",
    "LX0609-074": "已确认修正或补充诊断时记录了理由及诊断依据。",
}


def compliant_customer_finding(
    *,
    rule_id: str,
    criterion_results: Any = (),
) -> str:
    """只根据规则身份和已校验子结论生成合规短句，供 Envelope 单次生成复用。"""

    if rule_id == "LX0609-018":
        criteria = {}
        for item in criterion_results if isinstance(criterion_results, (tuple, list)) else ():
            criterion_id = (
                item.get("criterion_id")
                if isinstance(item, Mapping)
                else getattr(item, "criterion_id", "")
            )
            if isinstance(criterion_id, str) and criterion_id:
                criteria[criterion_id] = item
        length = criteria.get("chief_complaint_length")
        diagnostic = criteria.get("diagnostic_direction")
        length_actual = (
            length.get("actual_value")
            if isinstance(length, Mapping)
            else getattr(length, "actual_value", None)
        )
        diagnostic_status = (
            diagnostic.get("status")
            if isinstance(diagnostic, Mapping)
            else getattr(getattr(diagnostic, "status", None), "value", "")
        )
        if (
            length is not None
            and isinstance(length_actual, int)
            and diagnostic is not None
            and diagnostic_status == "passed"
        ):
            return f"主诉共 {length_actual} 字，不超过 20 字；诊断指向明确。"
    return _RULE_COMPLIANT_FINDINGS.get(
        rule_id,
        "已完成本质控点核对，未发现违反质控要求的情况。",
    )

SafeTraceSink = Callable[[Mapping[str, Any]], None]


def _safe_code(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return text if _SAFE_CODE.fullmatch(text) else ""


def _trusted_catalog_identity(rule_id: str) -> tuple[str, str, str]:
    rule = get_luxian_0609_rule(rule_id)
    if not isinstance(rule, dict):
        raise ValueError("decision rule is missing from trusted catalog")
    catalog_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
    if catalog_id != rule_id:
        raise ValueError("trusted catalog rule mismatch")
    name = str(rule.get("name") or rule.get("rule_name") or "").strip()
    if not name or len(name) > 120:
        raise ValueError("trusted catalog rule name is invalid")
    version = _safe_code(rule.get("rule_version") or rule.get("version")) or "v1"
    contract = next(
        (item for item in load_luxian_0609_rule_contracts() if item.rule_id == rule_id),
        None,
    )
    if contract is None or not _safe_code(contract.executor_key):
        raise ValueError("trusted rule contract is missing executor identity")
    return name, version, contract.executor_key


def _emit_safe_trace(
    sink: SafeTraceSink | None,
    *,
    decision: ReducedRuleDecision,
    executor_key: str,
) -> None:
    if sink is None:
        return
    payload = {
        "event": "customer_result_rendered",
        "rule_id": decision.rule_id,
        "snapshot_hash": decision.snapshot_hash,
        "decision_fingerprint": decision.decision_fingerprint,
        "reason_code": decision.reason_code,
        "fact_refs": decision.fact_refs,
        "evaluator_version": decision.evaluator_version,
        "executor_key": _safe_code(executor_key),
        "final_state": decision.final_state.value,
    }
    try:
        sink(payload)
    except Exception:
        return


def render_luxian_0609_customer_result(
    *,
    decision: ReducedRuleDecision,
    trace_sink: SafeTraceSink | None = None,
) -> dict[str, Any]:
    """从可信目录和 reducer 决策零构造 DTO，不接受任意展示字符串。"""

    if not isinstance(decision, ReducedRuleDecision):
        raise TypeError("decision must be ReducedRuleDecision")
    rule_name, rule_version, executor_key = _trusted_catalog_identity(decision.rule_id)
    status = _STATUS_MAP[decision.final_state]
    findings, evidence, suggestion = _CUSTOMER_MESSAGES[decision.final_state]
    if decision.final_state is CustomerFinalState.COMPLIANT:
        findings = compliant_customer_finding(
            rule_id=decision.rule_id,
            criterion_results=decision.criterion_results,
        )
    elif decision.final_state is CustomerFinalState.DATA_GAP:
        findings, evidence, suggestion = _RULE_DATA_GAP_MESSAGES.get(
            decision.rule_id,
            _DATA_GAP_MESSAGES.get(
                decision.reason_code,
                (findings, evidence, suggestion),
            ),
        )
    elif decision.final_state is CustomerFinalState.NON_COMPLIANT:
        findings, evidence, suggestion = _RULE_NON_COMPLIANT_MESSAGES.get(
            decision.rule_id,
            (findings, evidence, suggestion),
        )
    elif decision.final_state is CustomerFinalState.NOT_APPLICABLE:
        findings, evidence, suggestion = _RULE_NOT_APPLICABLE_MESSAGES.get(
            (decision.rule_id, decision.reason_code),
            (findings, evidence, suggestion),
        )
    elif decision.final_state is CustomerFinalState.EVALUATION_UNKNOWN:
        findings, evidence, suggestion = _RULE_UNCERTAIN_MESSAGES.get(
            decision.rule_id,
            (findings, evidence, suggestion),
        )
    if decision.final_state in {
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.NOT_APPLICABLE,
    }:
        is_compliant: bool | None = True
    elif decision.final_state is CustomerFinalState.NON_COMPLIANT:
        is_compliant = False
    else:
        is_compliant = None

    result = {
        "rule_id": decision.rule_id,
        "rule_code": decision.rule_id,
        "rule_name": rule_name,
        "qc_point_id": decision.rule_id,
        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
        "rule_version": rule_version,
        "schema_version": CUSTOMER_SCHEMA_VERSION,
        "status": status,
        "result_status": status,
        "is_compliant": is_compliant,
        "findings": findings,
        "evidence": evidence,
        "suggestion": suggestion,
        "confidence": decision.confidence,
        # 仅返回 reducer 已验证的受控枚举码；不返回快照、文书、坐标或模型原文。
        "reason_code": _safe_code(decision.reason_code),
        "evidence_items": [],
        "criterion_results": [],
    }
    if decision.criterion_results:
        contract = next(
            item
            for item in load_luxian_0609_rule_contracts()
            if item.rule_id == decision.rule_id
        )
        criteria_by_id = {
            item.criterion_id: item for item in contract.criteria
        }
        criterion_rows: list[dict[str, Any]] = []
        for criterion_result in decision.criterion_results:
            criterion = criteria_by_id.get(criterion_result.criterion_id)
            if criterion is None:
                raise ValueError("decision criterion is missing from rule contract")
            criterion_rows.append(
                {
                    **criterion_result.to_safe_dict(),
                    "kind": criterion.kind,
                    "source_fact": criterion.source_fact,
                    "left_fact": criterion.left_fact,
                    "right_fact": criterion.right_fact,
                }
            )
        result["criterion_results"] = criterion_rows
    _emit_safe_trace(
        trace_sink,
        decision=decision,
        executor_key=executor_key,
    )
    return result
