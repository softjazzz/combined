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
from .source_gap_contract import customer_gap_message


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
    "source_readiness_unproven": (
        "相关资料是否完整尚待确认",
        "目前无法确认本项判断所需资料是否已经全部读取。",
        "请确认相关资料完整后重新评估。",
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
_RULE_MISSING_ITEM_LABELS = {
    "LX0609-001": ("入院时间或入院记录时间",),
    "LX0609-002": ("入院时间、首次病程记录时间或有效正文",),
    "LX0609-004": ("抢救结束时间或抢救记录时间",),
    "LX0609-005": ("入院时间或主治医师首次查房时间",),
    "LX0609-006": ("入院时间或副主任医师及以上首次查房时间",),
    "LX0609-007": ("病情稳定期间查房记录时间",),
    "LX0609-008": ("病重医嘱时间、核对截止日期或查房记录时间",),
    "LX0609-009": ("病危医嘱时间、核对截止日期或每日病程记录",),
    "LX0609-016": ("入院记录现病史或首次病程记录病例特点",),
    "LX0609-018": ("主诉或入院第一诊断",),
    "LX0609-020": ("会诊意见、后续执行记录或两者的关联标识",),
    "LX0609-021": ("会诊申请中的具体临床问题、会诊理由或明确目的",),
    "LX0609-022": ("会诊记录中的明确诊疗意见",),
    "LX0609-003": ("手术结束时间、手术记录时间或单台手术关联信息",),
    "LX0609-029": ("已实施手术与术前小结的单台手术关联信息",),
    "LX0609-030": ("已实施手术与手术记录的关联信息",),
    "LX0609-032": ("已实施手术与手术安全核查表的单台手术关联信息",),
    "LX0609-036": ("实施麻醉事实、麻醉术前访视记录或麻醉术后访视记录",),
    "LX0609-037": ("麻醉术前、术后访视记录的必填内容",),
    "LX0609-038": ("非局部麻醉事实或麻醉记录单",),
    "LX0609-040": ("手术编码、有效手术等级或多学科讨论参加信息",),
    "LX0609-041": ("输血事实与同次住院输血知情同意书的关联信息",),
    "LX0609-042": ("输血知情同意书告知内容、签名或签署时间",),
    "LX0609-043": ("输血前九项检查结果、报告时间或输血开始时间",),
    "LX0609-044": ("输血前评估的指征、检验指标、输血风险、既往输血情况或患者当前情况",),
    "LX0609-045": ("输血事实与对应输血病程记录",),
    "LX0609-046": ("输血病程的原因、起止时间、成分、剂量、过程观察或反应处理",),
    "LX0609-047": ("输血结束时间、输血后评价时间或评价内容",),
    "LX0609-048": ("手术记录、麻醉记录和术后首次病程中的输血成分与剂量",),
    "LX0609-050": ("入院时间、入院满7天后的诊断状态或疑难病例讨论记录",),
    "LX0609-051": ("死亡时间、死亡病历讨论记录时间",),
    "LX0609-052": ("PL/PH危急值标志、报告时间或处置记录时间",),
    "LX0609-053": ("PL/PH危急值标志、报告时间或危急值处置记录",),
    "LX0609-054": ("抗菌药物医嘱、用药调整动作或对应理由",),
    "LX0609-055": ("抗菌药物首次用药时间或48～72小时效果评价时间",),
    "LX0609-057": ("经验用药事实、用药理由或无样可采原因",),
    "LX0609-058": ("特殊级抗菌药物医嘱或专家查房、会诊记录",),
    "LX0609-060": ("住院结局、死亡时间或死亡记录",),
    "LX0609-061": ("出院时间或出院记录完成时间",),
    "LX0609-062": ("出院带药的药名、剂量、途径或用药时间",),
    "LX0609-063": ("权威出院诊断或出院记录诊断及顺序",),
    "LX0609-064": ("手术时间、术后三日病程日期或术者身份",),
    "LX0609-065": ("手术时间、上级医师身份或术后三日查房时间",),
    "LX0609-066": ("已实施手术与术后首次病程的关联信息",),
    "LX0609-067": ("出院日期或出院前一天、当天病程记录",),
    "LX0609-068": ("出院日期、出院前病程、上级医师意见或自动出院书签署记录",),
    "LX0609-069": ("会诊申请时间或会诊记录完成时间",),
    "LX0609-070": ("输血前九项检查结果、报告时间或输血开始时间",),
    "LX0609-071": ("经治医师变更时间、交班记录或接班记录时间",),
    "LX0609-072": ("转科医嘱时间、转入记录或转出记录时间",),
    "LX0609-073": ("转科医嘱、转入记录或转出记录",),
    "LX0609-074": ("诊断修正时间、修改理由或诊断依据",),
}
_RULE_DATA_GAP_MESSAGES = {
    "LX0609-016": (
        "暂无法比较入院记录现病史与首次病程记录病例特点",
        "当前缺少可结构化读取的入院记录现病史或首次病程记录病例特点。",
        "请确认两段结构化内容已完整同步后重新评估。",
    ),
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
    "LX0609-013": (
        "暂无法核对病理结果是否记入手术记录或病程",
        "当前缺少病理最终诊断、病理报告时间，或可核对的手术记录和病程记录。",
        "请确认病理报告及相关手术、病程文书已完整同步后重新评估。",
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
    "LX0609-019": (
        "暂无法核对病理取材记录",
        "当前缺少完整的病理申请或报告来源，或缺少可核对的手术记录和病程记录。",
        "请确认病理、手术及病程资料已完整同步后重新评估。",
    ),
    "LX0609-020": (
        "暂无法核对会诊意见是否具有对应执行记录",
        "当前缺少可关联的会诊意见、后续病程执行记录，或两者的时间和关联标识。",
        "请确认会诊记录及后续执行病程已完整同步后重新评估。",
    ),
    "LX0609-021": (
        "暂无法核对会诊申请目的是否明确",
        "当前缺少可读取的会诊申请正文，或无法识别具体临床问题、会诊理由和明确目的。",
        "请确认会诊申请单正文已完整同步后重新评估。",
    ),
    "LX0609-022": (
        "暂无法核对会诊意见是否明确",
        "当前缺少可读取的会诊意见正文，或无法识别针对当前病情的明确诊疗意见。",
        "请确认会诊记录单正文已完整同步后重新评估。",
    ),
    "LX0609-026": (
        "暂无法核对化疗记录与医嘱是否一致",
        "当前缺少明确的化疗医嘱分类、药名、剂量、用法、时间，或对应化疗病程记录。",
        "请确认化疗医嘱结构化字段和治疗病程已完整同步后重新评估。",
    ),
    "LX0609-027": (
        "暂无法核对恶性肿瘤出院治疗计划",
        "当前缺少恶性肿瘤诊断依据或可核对的出院记录。",
        "请确认诊断和出院记录已完整同步后重新评估。",
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
        "暂无法完整核对输血知情同意书",
        "当前缺少可核对的告知内容、患者或代理人签名、医师签名，或精确到分钟的签署时间。",
        "请确认输血知情同意书全部必填内容已同步后重新评估。",
    ),
    "LX0609-043": (
        "暂无法完整核对输血前九项检查",
        "当前缺少乙肝五项、丙肝、艾滋、梅毒、谷丙转氨酶中的检查结果、报告时间，或输血开始时间。",
        "请补充缺失的输血前检查结果及权威时间后重新评估。",
    ),
    "LX0609-044": (
        "暂无法完整核对输血前评估",
        "当前缺少输血指征、检验指标、患者情况、拟输成分、预期效果或医师签名中的至少一项。",
        "请确认输血前评估字段已完整同步后重新评估。",
    ),
    "LX0609-045": (
        "暂无法确认输血病程记录是否对应本次输血",
        "当前缺少输血事件与输血病程记录之间的时间或关联信息。",
        "请确认输血事件和对应病程记录已完整同步后重新评估。",
    ),
    "LX0609-046": (
        "暂无法完整核对输血病程记录",
        "当前缺少输血原因、起止时间、成分、剂量、过程观察、不良反应处理或效果中的至少一项。",
        "请确认输血病程主要字段已完整同步后重新评估。",
    ),
    "LX0609-047": (
        "暂无法核对输血后24小时评价",
        "当前缺少输血结束时间、评价时间，或可确认疗效及不良反应的评价内容。",
        "请确认输血结束时间和输血后评价记录已完整同步后重新评估。",
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
    "LX0609-050": (
        "暂无法核对入院7天后诊断不明确病例的讨论记录",
        "当前缺少入院时间、满7天后的诊断状态或疑难病例讨论记录。",
        "请确认入院登记、病程和疑难病例讨论记录已完整同步后重新评估。",
    ),
    "LX0609-052": (
        "暂无法核对危急值是否在6小时内处置",
        "当前缺少PL/PH危急值标志、报告时间或对应处置记录时间。",
        "请确认危急值检验结果及处置记录已完整同步后重新评估。",
    ),
    "LX0609-053": (
        "暂无法确认危急值报告后是否有处置记录",
        "当前缺少PL/PH危急值标志、报告时间或可关联的危急值处置记录。",
        "请确认危急值检验结果及处置记录已完整同步后重新评估。",
    ),
    "LX0609-054": (
        "暂无法核对抗菌药物使用或调整理由",
        "当前缺少抗菌药物医嘱、使用调整动作或对应病程理由。",
        "请确认抗菌药物医嘱和相关病程已完整同步后重新评估。",
    ),
    "LX0609-055": (
        "暂无法核对48～72小时抗菌药物效果评价",
        "当前缺少首次用药时间、效果评价记录或评价时间。",
        "请确认抗菌药物医嘱时间和效果评价病程已完整同步后重新评估。",
    ),
    "LX0609-057": (
        "暂无法核对经验用药理由",
        "当前缺少经验用药事实、用药理由或无样可采原因。",
        "请确认抗菌药物医嘱及对应病程说明已完整同步后重新评估。",
    ),
    "LX0609-058": (
        "暂无法核对特殊级抗菌药物的专家支持记录",
        "当前缺少特殊级抗菌药物医嘱，或缺少可关联的专家查房、会诊记录。",
        "请确认特殊级抗菌药物医嘱和专家支持记录已完整同步后重新评估。",
    ),
    "LX0609-061": (
        "暂无法核对出院记录完成时限",
        "当前缺少出院时间或出院记录完成时间，无法计算24小时时限。",
        "请确认住院登记及出院记录的权威时间已完整同步后重新评估。",
    ),
    "LX0609-063": (
        "暂无法核对出院诊断内容及顺序",
        "当前缺少权威出院诊断或出院记录中的诊断及顺序。",
        "请确认诊断表和出院记录诊断已完整同步后重新评估。",
    ),
    "LX0609-064": (
        "暂无法核对术后三日连续病程及术者查房",
        "当前缺少手术时间、术后三日病程日期、术者身份或单台手术关联信息。",
        "请确认手术及术后病程资料已完整同步后重新评估。",
    ),
    "LX0609-065": (
        "暂无法核对术后三日内上级医师查房",
        "当前缺少手术时间、上级医师身份、查房时间或单台手术关联信息。",
        "请确认手术及上级医师查房资料已完整同步后重新评估。",
    ),
    "LX0609-066": (
        "暂无法核对术后首次病程记录",
        "当前缺少已实施手术与术后首次病程之间的单台手术关联信息。",
        "请确认手术和术后首次病程资料已完整同步后重新评估。",
    ),
    "LX0609-067": (
        "暂无法核对出院前病程记录",
        "当前缺少出院日期或出院前一天、当天的病程记录。",
        "请确认出院时间和病程资料已完整同步后重新评估。",
    ),
    "LX0609-068": (
        "暂无法核对上级医师同意出院意见",
        "当前缺少出院日期、出院前病程、上级医师意见或自动出院书签署记录。",
        "请确认出院时间及出院前病程资料已完整同步后重新评估。",
    ),
    "LX0609-070": (
        "暂无法完整核对输血前九项检查",
        "当前缺少输血前九项结果、报告时间或输血开始时间。",
        "请补充缺失的输血前检查结果及权威时间后重新评估。",
    ),
    "LX0609-074": (
        "暂无法核对诊断修正或补充记录",
        "当前缺少诊断修正时间、对应修改理由或诊断依据。",
        "请确认诊断变更及对应病程记录已完整同步后重新评估。",
    ),
}

_RULE_DATA_GAP_REASON_MESSAGES = {
    ("LX0609-012", "positive_assertion_not_explicit"): (
        "检查报告未明确写明阳性，暂无法启动阳性结果分析核对",
        "当前报告虽有影像描述，但未明确标注“阳性”；按本规则口径，不能据此判断是否需要在24小时内完成分析。",
        "请确认检查报告的阳性标志或补充明确阳性结论后重新评估。",
    ),
}

_EVALUATION_WINDOW_RULE_LABELS = {
    "LX0609-011": "CT/MRI 报告后病程记录",
    "LX0609-012": "CT/MRI 阳性结果分析",
    "LX0609-014": "细菌培养结果记录",
    "LX0609-015": "阳性菌结果分析",
}


def _evaluation_window_gap_message(
    *, rule_id: str, reason_code: str
) -> tuple[str, str, str] | None:
    label = _EVALUATION_WINDOW_RULE_LABELS.get(rule_id)
    if label is None:
        return None
    if reason_code == "authoritative_time_missing":
        return (
            f"暂无法核对{label}是否满足 24 小时要求",
            "缺少本次住院的评价截止日期或有效出院时间，无法确认 24 小时评价窗口是否已经结束。",
            "请确认病例住院状态及有效出院时间后重新评估。",
        )
    if reason_code == "authoritative_time_conflict":
        return (
            f"暂无法核对{label}是否满足 24 小时要求",
            "报告时间与本次住院的评价截止时间存在先后冲突，当前时间轴不能用于可靠判定。",
            "请核对本次住院、报告及出院时间后重新评估。",
        )
    if reason_code == "evaluation_window_not_mature":
        return (
            f"{label}的 24 小时评价窗口尚未结束",
            "截至本次冻结的评价日期，报告出具后尚未满 24 小时，本次暂不判定为质控问题。",
            "待 24 小时评价窗口结束后再次质控。",
        )
    return None
_RULE_NON_COMPLIANT_MESSAGES = {
    "LX0609-016": (
        "入院记录现病史与首次病程记录病例特点完全相同",
        "已按受控结构化段落逐字规范化比较，两段内容完全相同。",
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
    "LX0609-041": (
        "已确认本次实施输血，但未见输血知情同意书",
        "专用输血知情同意书来源已完成核对，未检出与本次输血对应的文书。",
        "请补充并归档本次输血知情同意书。",
    ),
    "LX0609-042": (
        "输血知情同意书填写或签署不完整",
        "已确认存在输血知情同意书，但告知内容、患者或代理人签名、医师签名或签署时间存在缺项。",
        "请按结果列出的缺失字段补充输血知情同意书。",
    ),
    "LX0609-043": (
        "输血前九项检查未全部在输血前完成",
        "已逐项核对乙肝五项、丙肝、艾滋、梅毒和谷丙转氨酶的结果及报告时间。",
        "请按结果列出的缺失或超时项目完善输血前检查。",
    ),
    "LX0609-044": (
        "本次输血未见输血前评估记录",
        "已核对输血相关记录，未检出可确认适应证、风险或用血必要性的输血前评估。",
        "请在输血前补充完整的评估记录。",
    ),
    "LX0609-045": (
        "已确认本次实施输血，但未见输血病程记录",
        "已核对输血事件及同次住院病程资料，未检出对应输血病程记录。",
        "请补充本次输血病程记录。",
    ),
    "LX0609-046": (
        "输血病程记录主要内容不完整",
        "输血原因、起止时间、成分、剂量、过程观察、不良反应处理或效果存在缺项。",
        "请按结果列出的缺失字段补充输血病程记录。",
    ),
    "LX0609-047": (
        "本次输血后未见输血效果评价",
        "已核对输血病程及相关病程资料，未检出输血后效果或不良反应评价。",
        "请补充输血后的疗效和不良反应评价。",
    ),
    "LX0609-048": (
        "术中输血在三份文书中的记录不一致",
        "已对照手术记录、麻醉记录单和术后首次病程记录中的输血成分及剂量，发现差异。",
        "请核对实际输血情况并统一修正文书记录。",
    ),
    "LX0609-050": (
        "入院 7 天后诊断仍不明确，未见疑难病例讨论记录",
        "已核对第 7 日病程和疑难病例讨论资料，当前诊断仍不明确且未检出讨论记录。",
        "请组织疑难病例讨论并记录诊断分析和后续诊疗计划。",
    ),
    "LX0609-052": (
        "危急值报告后 6 小时内未见处置记录",
        "检验结果带 PL/PH 危急值标志，报告后 6 小时内未检出对应处置记录。",
        "请及时处理危急值并记录处置时间、措施和结果。",
    ),
    "LX0609-053": (
        "危急值报告后未见处置记录",
        "检验结果带 PL/PH 危急值标志，未检出对应危急值处置记录。",
        "请补充危急值处置过程及结果。",
    ),
    "LX0609-068": (
        "出院前一天或当天病程中未见上级医师出院意见或完整自动出院记录",
        "已核对出院前一天及出院当天的病程记录，未检出上级医师同意、准予出院意见；自动出院时也未检出请示上级医师并签署自动出院书的完整记录。",
        "请在病程中补充上级医师出院意见；自动出院时应记录请示、劝阻或风险告知及书面签署情况。",
    ),
}
_RULE_NOT_APPLICABLE_MESSAGES = {
    ("LX0609-003", "performed_event_absent"): (
        "本次未实施手术，不启动手术记录24小时时限核对",
        "已核对手术主表和手术记录，未发现已实施手术事件。",
        "无需按本质控点处理。",
    ),
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
    ("LX0609-009", "trigger_absent_complete"): (
        "本次未发现符合规则定义的有效病危医嘱",
        "已核对非药物医嘱，未触发病危患者每日查房记录要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-011", "trigger_absent_complete"): (
        "本次未发现CT或MRI检查报告",
        "已核对检查主表和报告资料，未触发报告出具后24小时病程记录要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-012", "trigger_absent_complete"): (
        "本次未发现需要分析的CT或MRI阳性报告",
        "已核对检查报告及阳性标志，未触发阳性结果分析要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-013", "trigger_absent_complete"): (
        "本次未发现病理检查结果",
        "病理检查主表和报告资料已完成核对，未发现需要在手术记录或病程中追踪的病理结果。",
        "无需按本质控点处理。",
    ),
    ("LX0609-014", "trigger_absent_complete"): (
        "本次未发现细菌培养报告",
        "已核对检验报告及培养项目，未触发培养结果24小时病程记录要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-015", "trigger_absent_complete"): (
        "本次未发现阳性细菌培养结果",
        "已核对培养报告及阳性标志，未触发阳性菌结果分析要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-019", "trigger_absent_complete"): (
        "本次未发现病理取材事件",
        "病理检查及手术资料已完成核对，未发现需要记录取材情况的病理事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-020", "trigger_absent_complete"): (
        "本次未发现已完成的会诊意见，不启动会诊执行记录核对",
        "已核对会诊申请和会诊记录，未发现需要追踪执行情况的已完成会诊意见。",
        "无需按本质控点处理。",
    ),
    ("LX0609-021", "trigger_absent_complete"): (
        "本次未发现会诊申请单，不启动会诊申请目的核对",
        "已核对会诊资料，未发现需要检查目的是否明确的会诊申请。",
        "无需按本质控点处理。",
    ),
    ("LX0609-022", "trigger_absent_complete"): (
        "本次未发现会诊记录单，不启动会诊意见明确性核对",
        "已核对会诊资料，未发现需要检查意见是否明确的会诊记录。",
        "无需按本质控点处理。",
    ),
    ("LX0609-024", "trigger_absent_complete"): (
        "本次未触发恶性肿瘤手术规则",
        "现有诊断和手术资料未表明本次属于恶性肿瘤手术。",
        "无需按本质控点处理。",
    ),
    ("LX0609-025", "performed_event_absent"): (
        "本次未实施手术，不启动手术记录植入物信息核对",
        "已核对手术主表和手术记录，未发现已实施手术事件。",
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
    ("LX0609-029", "performed_event_absent"): (
        "本次未实施手术，不要求形成术前小结",
        "已核对手术主表、手术医嘱和手术记录，未发现已实施手术事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-030", "performed_event_absent"): (
        "本次未实施手术，不要求形成手术记录",
        "已核对手术主表、手术医嘱和手术记录，未发现已实施手术事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-030", "trigger_absent_complete"): (
        "本次未发现已实施手术，不要求形成手术记录",
        "完整手术来源未触发已实施手术事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-031", "performed_event_absent"): (
        "本次未实施手术，不启动手术记录签名核对",
        "已核对手术主表和手术记录，未发现已实施手术事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-032", "performed_event_absent"): (
        "本次未实施手术，不要求形成手术安全核查表",
        "已核对手术主表和手术记录，未发现已实施手术事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-032", "trigger_absent_complete"): (
        "本次未发现已实施手术，不要求形成手术安全核查表",
        "完整手术来源未触发已实施手术事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-033", "performed_event_absent"): (
        "本次未实施手术，不要求形成手术知情同意书",
        "已核对手术主表和手术记录，未发现已实施手术事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-034", "performed_event_absent"): (
        "本次未实施麻醉，不要求形成麻醉知情同意书",
        "已核对麻醉主表和麻醉记录，未发现已实施麻醉事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-035", "performed_event_absent"): (
        "本次未实施需签署同意书的麻醉，不启动麻醉知情同意书完整性核对",
        "已核对麻醉主表、麻醉方式和麻醉记录，未发现适用的麻醉事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-036", "performed_event_absent"): (
        "本次未实施需访视的麻醉，不要求形成麻醉术前或术后访视记录",
        "已核对麻醉主表、麻醉方式和麻醉记录，未发现需访视的麻醉事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-037", "eligibility_not_met"): (
        "已确认实施麻醉，但麻醉术前或术后访视记录缺失，本项规范性检查不再重复判定",
        "麻醉访视记录是否缺失由 LX0609-036 判定；本质控点仅在术前、术后访视记录均存在时核对填写规范。",
        "请先补齐麻醉访视记录，再核对记录填写是否规范。",
    ),
    ("LX0609-037", "performed_event_absent"): (
        "本次未实施需访视的麻醉，不启动麻醉访视填写规范核对",
        "已核对麻醉主表、麻醉方式和麻醉记录，未发现适用的麻醉事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-038", "performed_event_absent"): (
        "本次未实施需记录的麻醉，不要求形成麻醉记录单",
        "已核对麻醉主表、麻醉方式和麻醉记录，未发现需记录的麻醉事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-039", "performed_event_absent"): (
        "本次未实施手术，不要求形成术前讨论记录",
        "已核对手术主表和手术记录，未发现已实施手术事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-040", "performed_event_absent"): (
        "本次未实施四级手术，不启动术前多学科讨论核对",
        "已核对手术主表、手术分级和手术记录，未发现已实施四级手术事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-040", "trigger_absent_complete"): (
        "本次未实施四级手术，不启动术前多学科讨论核对",
        "已核对手术事件及手术分级，未发现已实施四级手术。",
        "无需按本质控点处理。",
    ),
    ("LX0609-041", "trigger_absent_complete"): (
        "本次未实施输血，不要求形成输血知情同意书",
        "已核对输血申请、医嘱和输血记录，未发现输血事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-042", "trigger_absent_complete"): (
        "本次未实施输血，不启动输血知情同意书完整性核对",
        "已核对输血申请、医嘱和输血记录，未发现输血事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-042", "eligibility_not_met"): (
        "未找到输血知情同意书，本项不再重复核对填写完整性",
        "已确认本次实施输血；知情同意书缺失问题由 LX0609-041 判定，本质控点仅核对已存在同意书的填写与签名完整性。",
        "请先按 LX0609-041 补齐输血知情同意书，再核对必要内容、双方签名和分钟级签署时间。",
    ),
    ("LX0609-043", "trigger_absent_complete"): (
        "本次未实施输血，不启动输血前辅助检查核对",
        "已核对输血申请、医嘱和输血记录，未发现输血事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-044", "trigger_absent_complete"): (
        "本次未实施输血，不要求形成输血前评估",
        "已核对输血申请、医嘱和输血记录，未发现输血事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-045", "trigger_absent_complete"): (
        "本次未实施输血，不要求形成输血病程记录",
        "已核对输血申请、医嘱和输血记录，未发现输血事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-046", "trigger_absent_complete"): (
        "本次未实施输血，不启动输血病程记录规范性核对",
        "已核对输血申请、医嘱和输血记录，未发现输血事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-047", "trigger_absent_complete"): (
        "本次未实施输血，不要求形成输血后评价",
        "已核对输血申请、医嘱和输血记录，未发现输血事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-048", "trigger_absent_complete"): (
        "本次未发现术中输血，不启动三份文书输血内容一致性核对",
        "已核对输血记录、手术记录和麻醉记录，未发现术中输血事件。",
        "无需按本质控点处理。",
    ),
    ("LX0609-074", "trigger_absent_complete"): (
        "本次未发现修正或补充诊断事件",
        "现有诊断记录未触发修改或补充诊断依据核对。",
        "无需按本质控点处理。",
    ),
    ("LX0609-050", "trigger_absent_complete"): (
        "入院满7天后未发现诊断仍不明确的记录",
        "已核对入院时间及后续病程，未触发疑难病例讨论要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-051", "trigger_absent_complete"): (
        "本次住院结局不是死亡",
        "已核对住院结局和死亡资料，未触发死亡病历讨论时限要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-052", "trigger_absent_complete"): (
        "本次未发现带PL或PH标志的危急值",
        "已核对检验结果及异常标志，未触发6小时处置时限要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-053", "trigger_absent_complete"): (
        "本次未发现带PL或PH标志的危急值",
        "已核对检验结果及异常标志，未触发危急值处置记录要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-054", "trigger_absent_complete"): (
        "本次未发现抗菌药物医嘱",
        "已核对住院药物医嘱，未触发抗菌药物使用或调整理由核对。",
        "无需按本质控点处理。",
    ),
    ("LX0609-055", "trigger_absent_complete"): (
        "本次未发现抗菌药物医嘱",
        "已核对住院药物医嘱，未触发48～72小时效果评价要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-057", "trigger_absent_complete"): (
        "本次未发现经验性抗菌药物使用",
        "已核对抗菌药物医嘱及病程，未触发经验用药理由核对。",
        "无需按本质控点处理。",
    ),
    ("LX0609-058", "trigger_absent_complete"): (
        "本次未使用特殊级抗菌药物",
        "已按院内抗菌药物分级目录核对医嘱，未触发专家查房或会诊要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-060", "trigger_absent_complete"): (
        "本次住院结局不是死亡",
        "已核对住院结局和死亡资料，未触发死亡记录要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-061", "trigger_absent_complete"): (
        "本次尚未形成出院时间",
        "现有住院登记未表明患者已出院，不启动出院记录24小时时限。",
        "无需按本质控点处理。",
    ),
    ("LX0609-062", "trigger_absent_complete"): (
        "本次未发现需要核对的出院带药",
        "已核对出院记录，未发现出院带药项目。",
        "无需按本质控点处理。",
    ),
    ("LX0609-063", "trigger_absent_complete"): (
        "本次尚未形成出院记录",
        "当前未触发出院诊断与权威诊断的一致性核对。",
        "无需按本质控点处理。",
    ),
    ("LX0609-064", "performed_event_absent"): (
        "本次未实施手术",
        "已核对手术主表和手术记录，未触发术后三日连续病程要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-065", "performed_event_absent"): (
        "本次未实施手术",
        "已核对手术主表和手术记录，未触发术后三日内上级医师查房要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-066", "performed_event_absent"): (
        "本次未实施手术",
        "已核对手术主表和手术记录，未触发术后首次病程要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-067", "trigger_absent_complete"): (
        "本次尚未出院",
        "当前未形成出院日期，不启动出院前病程核对。",
        "无需按本质控点处理。",
    ),
    ("LX0609-068", "trigger_absent_complete"): (
        "本次尚未出院",
        "当前未形成出院日期，不启动上级医师同意出院意见核对。",
        "无需按本质控点处理。",
    ),
    ("LX0609-069", "trigger_absent_complete"): (
        "本次未发现会诊申请或会诊记录",
        "已核对会诊资料，未触发会诊记录24小时时限要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-070", "trigger_absent_complete"): (
        "本次未实施输血",
        "已核对输血记录，未触发输血前九项检查要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-071", "trigger_absent_complete"): (
        "本次未发现经治医师变更事件",
        "已核对医师变更资料，未触发交接班记录要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-072", "trigger_absent_complete"): (
        "本次未发现转科医嘱",
        "已核对非药物医嘱，未触发转科记录24小时时限要求。",
        "无需按本质控点处理。",
    ),
    ("LX0609-073", "trigger_absent_complete"): (
        "本次未发现转科医嘱",
        "已核对非药物医嘱，未触发转入、转出记录存在性要求。",
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
    "LX0609-016": "已核对入院记录现病史与首次病程记录病例特点，两段内容并非完全相同。",
    "LX0609-017": "已核对病程记录，未发现相似度达到或超过 70% 的重复记录。",
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
    "LX0609-068": "已确认出院前病程记录了上级医师同意出院意见，或完整记录了自动出院的请示与书面签署过程。",
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
        finding = _lx018_criterion_finding(criterion_results)
        if finding:
            return finding
    return _RULE_COMPLIANT_FINDINGS.get(
        rule_id,
        "已完成本质控点核对，未发现违反质控要求的情况。",
    )


def _criterion_value(item: Any, field: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(field)
    value = getattr(item, field, None)
    return getattr(value, "value", value)


def _criterion_medical_analysis(item: Any) -> str:
    """把已写入受控子结论的医学分析压缩为列表可读的一句话。"""

    value = _criterion_value(item, "medical_analysis")
    if not isinstance(value, str):
        return ""
    text = re.sub(r"\s+", " ", value).strip()
    if not text:
        return ""
    text = re.sub(r"^(?:AI)?医学分析[：:]\s*", "", text)
    text = text.rstrip("。；; ")
    return f"{text[:157]}…" if len(text) > 160 else text


def _lx018_criterion_finding(criterion_results: Any) -> str:
    """把018两个受控子判定压缩为列表中可直接阅读的一句话。"""

    criteria = {}
    for item in criterion_results if isinstance(criterion_results, (tuple, list)) else ():
        criterion_id = _criterion_value(item, "criterion_id")
        if isinstance(criterion_id, str) and criterion_id:
            criteria[criterion_id] = item
    length = criteria.get("chief_complaint_length")
    relation = criteria.get("diagnostic_direction")
    if length is None or relation is None:
        return ""

    length_status = _criterion_value(length, "status")
    length_actual = _criterion_value(length, "actual_value")
    length_text = (
        f"主诉共 {length_actual} 字，符合不超过 20 字要求"
        if length_status == "passed" and isinstance(length_actual, int)
        else f"主诉共 {length_actual} 字，超过 20 字上限"
        if length_status == "failed" and isinstance(length_actual, int)
        else "主诉字数暂无法核对"
    )

    relation_status = _criterion_value(relation, "status")
    relation_value = _criterion_value(relation, "actual_value")
    medical_analysis = _criterion_medical_analysis(relation)
    relation_text = (
        f"第一诊断可导出：{medical_analysis}"
        if relation_status == "passed" and medical_analysis
        else "主诉中的临床线索与入院第一诊断相符，可以导出第一诊断"
        if relation_status == "passed"
        else f"不能据此导出第一诊断：{medical_analysis}"
        if relation_status == "failed" and medical_analysis
        else "主诉与入院第一诊断的方向不一致，不能据此导出第一诊断"
        if relation_status == "failed" and relation_value == "mismatch"
        else "主诉提供的诊断线索不足，不能据此导出第一诊断"
        if relation_status == "failed"
        else "主诉能否支持入院第一诊断暂无法判断"
    )
    return f"{length_text}；{relation_text}。"


def _unknown_criterion_labels(decision: ReducedRuleDecision) -> tuple[str, ...]:
    if not decision.criterion_results:
        return ()
    contract = next(
        (
            item
            for item in load_luxian_0609_rule_contracts()
            if item.rule_id == decision.rule_id
        ),
        None,
    )
    if contract is None:
        return ()
    labels_by_id = {item.criterion_id: item.label for item in contract.criteria}
    return tuple(
        labels_by_id[item.criterion_id]
        for item in decision.criterion_results
        if getattr(item.status, "value", "") == "unknown"
        and item.criterion_id in labels_by_id
    )


def _missing_item_labels(decision: ReducedRuleDecision) -> tuple[str, ...]:
    return _unknown_criterion_labels(decision) or _RULE_MISSING_ITEM_LABELS.get(
        decision.rule_id,
        (),
    )


_TRANSFUSION_FIELD_LABELS = {
    "patient_information": "患者基本信息",
    "diagnosis": "诊断",
    "indication": "输血指征",
    "component": "拟输血成分",
    "risks": "输血风险",
    "alternatives": "替代方案",
    "patient_or_agent_signature": "患者或代理人签名",
    "physician_signature": "医师签名",
    "signed_time": "精确到分钟的签署时间",
    "laboratory_indicator": "输血前检验指标",
    "risk_history_or_status": "输血风险、既往输血情况或患者当前情况",
    "transfusion_history_or_reaction": "既往输血史或输血反应史",
    "patient_status": "患者当前情况",
    "planned_component": "拟输注血液成分",
    "expected_effect": "预期效果",
    "reason_or_indication": "输血原因或指征",
    "start_and_end_time": "输血开始及结束时间",
    "dose": "输注量",
    "process_observation": "输血过程观察",
    "reaction_and_handling": "输血反应及处理",
    "effect": "输血效果",
    "components": "血液成分",
    "doses": "输注量",
}
_TRANSFUSION_ITEM_LABELS = {
    "hbsag": "乙肝表面抗原",
    "hbsab": "乙肝表面抗体",
    "hbeag": "乙肝e抗原",
    "hbeab": "乙肝e抗体",
    "hbcab": "乙肝核心抗体",
    "hcv": "丙肝抗体",
    "hiv": "艾滋病病毒抗体",
    "syphilis": "梅毒筛查",
    "alt": "谷丙转氨酶",
}
_TRANSFUSION_SOURCE_LABELS = {
    "bloodtrans_record": "输血记录",
    "daily_course_record": "病程记录",
    "surgery_record": "手术记录",
    "anesthesia_record": "麻醉记录",
    "postsurg_firstcourse_record": "术后首次病程记录",
}
_DISCHARGE_MEDICATION_FIELD_LABELS = {
    "drug_name": "药品名称",
    "dose": "用药剂量",
    "route": "给药途径",
    "duration": "用药时间",
}
_ANESTHESIA_VISIT_FIELD_LABELS = {
    "asa_level": "ASA分级",
    "airway_assessment": "气道评估",
    "fasting_status": "禁食禁饮情况",
    "anesthesia_history": "既往麻醉史",
    "risk_discussion": "麻醉风险告知",
    "consciousness_status": "意识状态",
    "respiratory_status": "呼吸情况",
    "circulatory_status": "循环情况",
    "complication_assessment": "麻醉并发症评估",
    "anesthetist_signature": "麻醉医师签名",
    "record_time": "记录时间",
}


def customer_finding_from_controlled_facts(
    *, rule_id: str, facts: Mapping[str, Any] | None
) -> str:
    """将已白名单化的受控事实投影为客户可核对短句，不接受原始病历正文。"""

    if rule_id not in {
        "LX0609-009",
        "LX0609-011",
        "LX0609-012",
        "LX0609-013",
        "LX0609-014",
        "LX0609-015",
        "LX0609-019",
        "LX0609-020",
        "LX0609-021",
        "LX0609-022",
        "LX0609-025",
        "LX0609-033",
        "LX0609-026",
        "LX0609-027",
        "LX0609-037",
        "LX0609-040",
        *(f"LX0609-{index:03d}" for index in range(41, 49)),
        *(f"LX0609-{index:03d}" for index in range(50, 75)),
        "LX0609-070",
    }:
        return ""
    if not isinstance(facts, Mapping):
        return ""

    kind = str(facts.get("verification_kind") or facts.get("failure_kind") or "")

    def labels(key: str, mapping: Mapping[str, str]) -> str:
        values = facts.get(key)
        if not isinstance(values, list):
            return ""
        return "、".join(mapping[value] for value in values if value in mapping)

    def joined(key: str) -> str:
        values = facts.get(key)
        return "、".join(str(value) for value in values) if isinstance(values, list) else ""

    if rule_id == "LX0609-033":
        if facts.get("performed_surgery_confirmed") is not True:
            return ""
        consent_state = str(facts.get("consent_state") or "")
        if kind == "surgery_consent_document_missing" and consent_state == "missing":
            return "已确认实施手术，未检索到手术知情同意书。"
        if kind == "surgery_consent_body_missing" and consent_state == "blank":
            return "已确认实施手术，但手术知情同意书正文为空。"
        if kind == "surgery_consent_signature_missing" and consent_state == "signature_missing":
            role_labels = {"patient": "患者或代理人", "surgeon": "术者"}
            roles = facts.get("missing_signature_roles")
            if not isinstance(roles, list) or not roles:
                return ""
            labels_text = "、".join(
                role_labels[role] for role in roles if role in role_labels
            )
            if not labels_text:
                return ""
            return f"已确认实施手术，但手术知情同意书缺少{labels_text}签名。"
        return ""

    if rule_id == "LX0609-025":
        primary_labels = {
            "implant_barcode": "植入物条码",
            "implant_type": "植入物种类",
            "implant_quantity": "植入物数量",
        }
        source = str(facts.get("source_label") or "手术记录或病程记录")
        if kind == "implant_information_incomplete":
            missing = labels("missing_fields", primary_labels)
            return f"已确认实际使用永久性植入物，但{source}缺少：{missing}。" if missing else ""
        if kind == "implant_information_complete":
            checked = labels("checked_fields", primary_labels)
            extension = labels(
                "local_extension_missing_fields",
                {
                    "implant_name": "名称",
                    "implant_specification": "规格/型号",
                    "implant_material": "材质",
                },
            )
            suffix = f"本院扩展字段待补：{extension}。" if extension else ""
            return f"已核对{source}，{checked}均有记录。{suffix}"

    if rule_id == "LX0609-009":
        change_events = facts.get("change_events")
        event_rows = change_events if isinstance(change_events, list) else []
        if kind == "critical_change_course_timely":
            return (
                f"已核对 {len(event_rows)} 个明确病情变化事件；"
                "均在变化后 24 小时内找到对应病程记录。"
            )
        if kind == "critical_change_course_not_timely":
            unmet = facts.get("unmet_events")
            first = unmet[0] if isinstance(unmet, list) and unmet else {}
            if isinstance(first, Mapping):
                category_labels = {
                    "subjective": "症状变化", "objective": "体征变化",
                    "exam_lab": "检查检验变化", "complication": "并发症或合并症变化",
                    "special_state": "特殊状态变化",
                }
                label = category_labels.get(str(first.get("change_category") or ""), "病情变化")
                return (
                    f"{label}发生于 {first.get('event_time') or '时间待核对'}，"
                    f"截至 24 小时阈值 {first.get('deadline_time') or '待核对'}"
                    "未找到对应病程记录。"
                )
        if kind == "critical_change_time_unavailable":
            return "已识别可能的病情变化，但缺少可核验的变化发生时间，暂无法核对 24 小时内记录要求。"
        if kind == "critical_change_course_association_failed":
            return "已识别明确病情变化，但无法确认其与对应病程记录的关联关系，暂无法核对 24 小时内记录要求。"
        if kind == "critical_change_window_not_mature":
            return (
                f"病情变化发生于 {facts.get('event_time') or '时间待核对'}，"
                f"截至评价终点尚未满 24 小时（截止 {facts.get('deadline_time') or '待核对'}），"
                "本次暂不判定为质控问题。"
            )
        required_values = facts.get("required_dates")
        required_dates = (
            [str(value) for value in required_values]
            if isinstance(required_values, list)
            else []
        )
        covered_values = facts.get("covered_dates")
        covered_dates = (
            [str(value) for value in covered_values]
            if isinstance(covered_values, list)
            else []
        )
        date_scope = (
            required_dates[0]
            if len(required_dates) == 1
            else f"{required_dates[0]} 至 {required_dates[-1]}"
            if required_dates
            else "日期暂缺"
        )
        required_count = len(required_dates)
        covered_count = len(covered_dates)
        scope_note = "本阶段仅核对病危期间每日病程。"
        if kind == "critical_daily_record_coverage_satisfied":
            return (
                f"病危观察期 {date_scope}，共 {required_count} 天；"
                f"每日病程 {covered_count}/{required_count} 天，记录完整。{scope_note}"
            )
        if kind == "critical_daily_record_missing":
            missing_values = facts.get("missing_dates")
            missing_dates = (
                [str(value) for value in missing_values]
                if isinstance(missing_values, list)
                else []
            )
            missing_text = "、".join(missing_dates) or "未明确日期"
            return (
                f"病危观察期 {date_scope}，共 {required_count} 天；"
                f"每日病程已记录 {covered_count}/{required_count} 天，"
                f"缺少 {missing_text}。{scope_note}"
            )

    if rule_id in {"LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"}:
        subject = "CT/MRI" if rule_id in {"LX0609-011", "LX0609-012"} else "细菌培养"
        analysis_rule = rule_id in {"LX0609-012", "LX0609-015"}
        report_time = facts.get("report_time")
        response_count = facts.get("response_record_count")
        response_time = facts.get("response_record_time")
        interval = facts.get("interval_hours")
        if kind == "exam_lab_requirement_not_documented":
            if isinstance(response_count, int) and response_count > 0:
                timing = (
                    f"，最早相关病程时间 {response_time}，间隔 {interval:g} 小时"
                    if isinstance(interval, (int, float)) and response_time
                    else ""
                )
                missing_content = (
                    "但病程未记录阳性结果的临床意义判断或相应处置"
                    if analysis_rule
                    else "但病程未记录报告结果"
                )
                return f"{subject} 报告于 {report_time} 出具，找到 {response_count} 份相关病程{timing}，{missing_content}。"
            requirement = "阳性结果分析" if analysis_rule else "报告结果记录"
            return f"{subject} 报告于 {report_time} 出具，未找到报告后 24 小时内的{requirement}。"

    if rule_id == "LX0609-013" and kind == "pathology_result_documentation_check":
        return f"病理报告于 {facts.get('report_time')} 出具；已核对手术记录和病程记录，未找到病理结果记录。"

    if rule_id == "LX0609-019" and kind == "pathology_sampling_not_documented":
        return "已确认存在病理取材事件；已核对手术记录和病程记录，均未找到取材情况记录。"

    if rule_id == "LX0609-020":
        state = str(facts.get("execution_record_state") or "")
        if state == "未发现执行记录":
            return "已找到会诊意见，但未发现对应的请会诊执行记录。"
        if state == "已发现明确执行记录":
            return "已找到会诊意见及对应的明确执行记录。"

    if rule_id in {"LX0609-021", "LX0609-022"}:
        assessment = str(facts.get("consultation_assessment") or "")
        target = "会诊申请目的" if rule_id == "LX0609-021" else "会诊意见"
        requirement = (
            "具体临床问题、会诊理由或明确目的"
            if rule_id == "LX0609-021"
            else "针对当前病情的明确诊疗意见"
        )
        if assessment == "明确":
            return f"已核对{target}，其中已说明{requirement}。"
        if assessment == "不符合要求":
            return f"已核对{target}，其中未说明{requirement}。"

    if rule_id == "LX0609-026" and kind == "chemotherapy_order_course_comparison":
        field_labels = {
            "drug_name": "药物名称",
            "dose": "剂量",
            "route": "使用方法",
            "time": "用药时间",
        }
        field_results = facts.get("field_results")
        if isinstance(field_results, Mapping):
            mismatched = "、".join(
                field_labels[key]
                for key, value in field_results.items()
                if key in field_labels and value == "mismatched"
            )
            if mismatched:
                return f"已核对 {facts.get('order_count')} 条化疗医嘱及对应病程，{mismatched}记录不一致。"
            return f"已核对 {facts.get('order_count')} 条化疗医嘱及对应病程，药物名称、剂量、使用方法和用药时间一致。"

    if rule_id == "LX0609-027" and kind == "malignant_discharge_plan_check":
        items = facts.get("plan_items")
        if isinstance(items, Mapping):
            missing = "、".join(
                label
                for key, label in {
                    "future_plan": "后续诊疗计划",
                    "tumor_treatment": "肿瘤相关治疗安排",
                    "follow_up": "随访安排",
                }.items()
                if items.get(key) is False
            )
            if missing:
                return f"已确认出院诊断包含恶性肿瘤，但出院记录缺少：{missing}。"

    if rule_id == "LX0609-037":
        if kind == "anesthesia_visits_complete":
            raw_checked = facts.get("checked_fields_by_visit")
            if not isinstance(raw_checked, Mapping):
                return ""
            pre = "、".join(
                _ANESTHESIA_VISIT_FIELD_LABELS[field]
                for field in raw_checked.get("preanesthesia_visit", [])
                if field in _ANESTHESIA_VISIT_FIELD_LABELS
            )
            post = "、".join(
                _ANESTHESIA_VISIT_FIELD_LABELS[field]
                for field in raw_checked.get("postanesthesia_visit", [])
                if field in _ANESTHESIA_VISIT_FIELD_LABELS
            )
            return f"麻醉术前访视已核对：{pre}；麻醉术后访视已核对：{post}。" if pre and post else ""
        if kind == "anesthesia_visit_incomplete":
            raw_missing = facts.get("missing_fields_by_visit")
            if not isinstance(raw_missing, Mapping):
                return ""
            visit_labels = {
                "preanesthesia_visit": "麻醉术前访视",
                "postanesthesia_visit": "麻醉术后访视",
            }
            details = []
            for visit, visit_label in visit_labels.items():
                fields = raw_missing.get(visit)
                if not isinstance(fields, list):
                    continue
                field_labels = "、".join(
                    _ANESTHESIA_VISIT_FIELD_LABELS[field]
                    for field in fields
                    if field in _ANESTHESIA_VISIT_FIELD_LABELS
                )
                if field_labels:
                    details.append(f"{visit_label}缺少{field_labels}")
            return f"{'；'.join(details)}。" if details else ""

    if rule_id == "LX0609-040":
        if facts.get("performed_surgery_confirmed") is not True:
            return ""
        procedure = "".join(
            part
            for part in (
                str(facts.get("procedure_name") or ""),
                f"（{facts.get('procedure_code')}）" if facts.get("procedure_code") else "",
            )
        ) or "本次手术"
        source = {
            "hospital_performance": "院内绩效分配",
            "national_catalog": "国家临床版手术分级目录",
        }.get(str(facts.get("surgery_level_source") or ""), "受控手术分级目录")
        state = str(facts.get("mdt_discussion_state") or "")
        if state == "missing":
            return f"已确认实施四级手术 {procedure}（等级来源：{source}），未找到术前多学科讨论记录。"
        if state == "completed":
            return f"已确认实施四级手术 {procedure}（等级来源：{source}），已完成术前多学科讨论。"

    if rule_id == "LX0609-050" and kind == "uncertain_diagnosis_discussion_check":
        count = facts.get("discussion_count")
        trigger_times = joined("uncertain_record_times")
        if trigger_times:
            return (
                f"入院时间为 {facts.get('admission_time')}，入院满 7 天后仍有诊断不明确记录"
                f"（{trigger_times}）；疑难病例讨论记录 {count} 份。"
            )
        return f"入院时间为 {facts.get('admission_time')}，未发现入院满 7 天后诊断仍不明确的触发记录，本质控点不适用。"

    if rule_id == "LX0609-051":
        if kind == "death_discussion_timeliness_check":
            return (
                f"死亡时间 {facts.get('death_time')}，死亡病历讨论时间 {facts.get('discussion_time')}，"
                f"实际间隔 {facts.get('actual_interval_hours')} 小时，规定时限 168 小时。"
            )
        if kind == "death_discussion_missing_after_deadline":
            return f"患者于 {facts.get('death_time')} 死亡，超过 7 天仍未找到死亡病历讨论记录。"

    if rule_id in {"LX0609-052", "LX0609-053"}:
        if kind == "critical_value_result_detail_missing":
            return (
                f"已读取到检验报告 {facts.get('lab_report_count')} 条，但检验结果明细未同步，"
                "无法取得 PL/PH 危急值标志及报告时间。"
            )
        items = joined("critical_item_names") or "已标记 PL/PH 的检验项目"
        reports = joined("report_times")
        dispositions = joined("disposition_times")
        if rule_id == "LX0609-052":
            intervals = joined("actual_interval_hours")
            if dispositions and intervals:
                return f"危急值项目：{items}；报告时间：{reports}；处置时间：{dispositions}；实际间隔 {intervals} 小时，规定时限 6 小时。"
            return f"危急值项目：{items}；报告时间：{reports}；未找到 6 小时内的危急值处置记录。"
        if dispositions:
            return f"危急值项目：{items}；报告后已找到危急值处置记录（{dispositions}）。"
        return f"危急值项目：{items}；报告时间：{reports}；未找到报告后的危急值处置记录。"

    if rule_id == "LX0609-054" and kind == "antimicrobial_reason_documentation_check":
        medicines = joined("antimicrobials")
        return (
            f"已核对抗菌药物 {medicines}，病程中已记录使用或调整理由。"
            if facts.get("reason_documented") is True
            else f"已核对抗菌药物 {medicines}，病程中未找到明确的使用或调整理由。"
        )

    if rule_id == "LX0609-055" and kind == "antimicrobial_effect_evaluation_check":
        medicines = joined("antimicrobials")
        intervals = joined("evaluation_intervals")
        if not intervals:
            return f"已核对抗菌药物 {medicines}，未找到首次用药后 48～72 小时内的效果评价记录。"
        return f"已核对抗菌药物 {medicines}；效果评价距首次用药 {intervals} 小时，要求在 48～72 小时内完成。"

    if rule_id == "LX0609-057" and kind == "empiric_antimicrobial_reason_check":
        medicines = joined("antimicrobials")
        return (
            f"已确认经验使用 {medicines}，并记录经验用药理由或无样可采原因。"
            if facts.get("reason_or_no_specimen_documented") is True
            else f"已确认经验使用 {medicines}，但未记录经验用药理由或无样可采原因。"
        )

    if rule_id == "LX0609-058" and kind == "special_antimicrobial_expert_support_check":
        medicines = joined("special_antimicrobials")
        return (
            f"已使用特殊级抗菌药物 {medicines}，并找到专家查房或会诊支持记录。"
            if facts.get("expert_support_present") is True
            else f"已使用特殊级抗菌药物 {medicines}，未找到专家查房或会诊支持记录。"
        )

    if rule_id == "LX0609-060" and kind == "death_record_presence_check":
        return (
            f"已确认患者死亡（死亡时间 {facts.get('death_time') or '未返回'}），"
            f"死亡记录 {facts.get('death_record_count')} 份。"
        )

    if rule_id == "LX0609-061" and kind == "discharge_record_timeliness_check":
        interval = facts.get("actual_interval_hours")
        if isinstance(interval, (int, float)) and interval < 0:
            return (
                f"出院记录于出院前 {abs(interval):g} 小时完成"
                f"（记录时间 {facts.get('record_time')}；出院时间 {facts.get('discharge_time')}），"
                "符合出院后 24 小时内完成要求。"
            )
        return (
            f"出院时间 {facts.get('discharge_time')}，出院记录时间 {facts.get('record_time')}，"
            f"实际间隔 {interval} 小时，规定时限 24 小时。"
        )

    if rule_id == "LX0609-062" and kind == "discharge_medication_completeness_check":
        missing = labels("missing_fields", _DISCHARGE_MEDICATION_FIELD_LABELS)
        return (
            f"共核对 {facts.get('medication_count')} 项出院带药，药名、剂量、途径及用药时间均完整。"
            if not missing
            else f"出院带药缺少字段：{missing}。"
        )

    if rule_id == "LX0609-063" and kind == "discharge_diagnosis_consistency_check":
        authority = joined("authoritative_diagnoses")
        written = joined("written_diagnoses")
        state = "一致" if facts.get("diagnoses_consistent") is True else "不一致"
        return f"权威出院诊断为“{authority}”，出院记录诊断为“{written}”，两者顺序及内容{state}。"

    if rule_id == "LX0609-064" and kind == "postoperative_three_day_coverage_check":
        required = joined("required_postop_dates")
        covered = joined("covered_postop_dates") or "无"
        surgeon = "有" if facts.get("surgeon_round_present") is True else "无"
        return f"手术时间 {facts.get('surgery_time')}；术后应记录日期为 {required}，实际覆盖 {covered}；{surgeon}术者查房记录。"

    if rule_id == "LX0609-065" and kind == "postoperative_senior_round_check":
        rounds = joined("senior_round_times")
        return f"手术时间 {facts.get('surgery_time')}；术后 72 小时内上级医师查房时间：{rounds or '未找到'}。"

    if rule_id == "LX0609-066" and kind == "postoperative_first_course_presence_check":
        surgery_count = facts.get("performed_surgery_count")
        record_count = facts.get("postoperative_first_course_count")
        if (
            isinstance(surgery_count, int)
            and isinstance(record_count, int)
            and record_count < surgery_count
        ):
            return (
                f"已确认实施手术 {surgery_count} 台，找到术后首次病程记录 {record_count} 份；"
                "尚不能逐台关联，暂无法确认每台手术均有对应记录。"
            )
        return f"已确认实施手术 {surgery_count} 台，找到术后首次病程记录 {record_count} 份，数量及关联关系符合要求。"

    if rule_id == "LX0609-067" and kind == "predischarge_course_presence_check":
        state = "已找到" if facts.get("course_present") is True else "未找到"
        return f"出院日期 {facts.get('discharge_date')}；已核对 {joined('checked_dates')}，{state}出院前病程记录。"

    if rule_id == "LX0609-069" and kind == "consultation_timeliness_check":
        return f"会诊申请时间：{joined('request_times')}；完成时间：{joined('record_times')}；实际间隔 {joined('actual_interval_hours')} 小时，规定时限 24 小时。"

    if rule_id == "LX0609-071" and kind == "physician_handoff_timeliness_check":
        return f"经治医师变更时间 {facts.get('change_time')}；交班记录时间：{joined('handoff_times') or '未找到'}；接班记录时间：{joined('handover_times') or '未找到'}，接班时限 24 小时。"

    if rule_id == "LX0609-072" and kind == "transfer_record_timeliness_check":
        return f"转科医嘱时间 {facts.get('transfer_order_time')}；转入、转出记录时间：{joined('record_times')}；实际间隔 {joined('actual_interval_hours')} 小时，规定时限 24 小时。"

    if rule_id == "LX0609-073" and kind == "transfer_record_presence_check":
        return f"已确认转科医嘱 {facts.get('transfer_order_count')} 条，转入记录 {facts.get('transfer_in_count')} 份，转出记录 {facts.get('transfer_out_count')} 份。"

    if rule_id in {"LX0609-072", "LX0609-073"} and kind == "transfer_records_missing":
        return f"已确认转科医嘱 {facts.get('transfer_order_count')} 条，转入记录 {facts.get('transfer_in_count')} 份，转出记录 {facts.get('transfer_out_count')} 份；目标文书缺失。"

    if rule_id == "LX0609-074" and kind == "diagnosis_change_documentation_check":
        state = "均已记录" if facts.get("reason_recorded") and facts.get("basis_recorded") else "未完整记录"
        return f"共识别 {facts.get('diagnosis_change_count')} 次诊断修正或补充，修改理由和诊断依据{state}。"

    if rule_id == "LX0609-041":
        if kind == "transfusion_consent_present":
            return f"已确认本次输血具备输血知情同意书（{facts.get('consent_count', 0)} 份）。"
        if kind == "transfusion_consent_missing":
            return "已确认实施输血，但未找到对应的输血知情同意书。"

    if rule_id == "LX0609-042":
        if kind == "transfusion_consent_complete":
            return "输血知情同意书的必要内容、双方签名及分钟级签署时间均完整。"
        if kind == "transfusion_consent_incomplete":
            missing = labels("missing_fields", _TRANSFUSION_FIELD_LABELS)
            return f"输血知情同意书缺少：{missing}。" if missing else ""

    if rule_id in {"LX0609-043", "LX0609-070"}:
        if kind == "pretransfusion_items_complete":
            return (
                "输血前九项均已完成，最晚检验时间为 "
                f"{facts.get('latest_test_time')}，早于输血时间 {facts.get('transfusion_time')}。"
            )
        key = {
            "pretransfusion_items_incomplete": "missing_items",
            "pretransfusion_tests_after_transfusion": "late_items",
            "pretransfusion_test_time_missing": "missing_time_items",
        }.get(kind)
        if key:
            items = labels(key, _TRANSFUSION_ITEM_LABELS)
            prefix = {
                "pretransfusion_items_incomplete": "输血前九项缺少",
                "pretransfusion_tests_after_transfusion": "以下检验晚于输血时间",
                "pretransfusion_test_time_missing": "以下检验缺少可核对的报告时间",
            }[kind]
            return f"{prefix}：{items}。" if items else ""

    if rule_id == "LX0609-044":
        if kind == "pretransfusion_assessment_complete":
            return "输血前评估已记录输血指征、相关检验，以及输血风险、既往输血情况或患者当前情况。"
        if kind in {
            "pretransfusion_assessment_missing",
            "pretransfusion_assessment_incomplete",
        }:
            missing = labels("missing_fields", _TRANSFUSION_FIELD_LABELS)
            if kind == "pretransfusion_assessment_missing":
                return "已确认实施输血，但未找到可核对的输血前评估记录。"
            return f"输血前评估缺少：{missing}。" if missing else ""

    if rule_id == "LX0609-045":
        if kind == "transfusion_course_record_present":
            return f"已找到可核对的输血病程记录（{facts.get('record_count', 0)} 份）。"
        if kind == "transfusion_course_record_missing":
            checked = labels("checked_sources", _TRANSFUSION_SOURCE_LABELS)
            return f"已核对{checked}，未找到输血病程记录。" if checked else ""

    if rule_id == "LX0609-046":
        if kind == "transfusion_course_record_complete":
            return "输血病程已记录指征、起止时间、血液成分、输注量、过程观察及反应处理。"
        if kind == "transfusion_course_record_incomplete":
            missing = labels("missing_fields", _TRANSFUSION_FIELD_LABELS)
            return f"输血病程记录缺少：{missing}。" if missing else ""

    if rule_id == "LX0609-047":
        if kind == "posttransfusion_evaluation_complete":
            elapsed = facts.get("elapsed_hours")
            interval = f"，间隔 {elapsed:g} 小时" if isinstance(elapsed, (int, float)) else ""
            return (
                f"已在输血结束后 24 小时内完成效果评价{interval}"
                f"（结束时间 {facts.get('transfusion_end_time')}；评价时间 {facts.get('evaluation_time')}）。"
            )
        if kind == "posttransfusion_evaluation_missing":
            checked = labels("checked_sources", _TRANSFUSION_SOURCE_LABELS)
            return f"已核对{checked}，未找到输血结束后 24 小时内的效果评价。" if checked else ""

    if rule_id == "LX0609-048":
        if kind == "intraoperative_transfusion_absent":
            return "手术记录和麻醉记录均未提示术中输血，本质控点不适用。"
        if kind == "transfusion_comparison_material_missing":
            missing = labels("missing_sources", _TRANSFUSION_SOURCE_LABELS)
            return f"暂缺{missing}，无法完成术中输血三方一致性核对。" if missing else ""
        if kind == "transfusion_comparison_fields_missing":
            raw_missing = facts.get("missing_fields_by_source")
            if not isinstance(raw_missing, Mapping):
                return ""
            details = []
            for source, fields in raw_missing.items():
                if source not in _TRANSFUSION_SOURCE_LABELS or not isinstance(fields, list):
                    continue
                field_labels = "、".join(
                    _TRANSFUSION_FIELD_LABELS[field]
                    for field in fields
                    if field in _TRANSFUSION_FIELD_LABELS
                )
                if field_labels:
                    details.append(f"{_TRANSFUSION_SOURCE_LABELS[source]}缺少{field_labels}")
            return f"{'；'.join(details)}，无法完成三方一致性核对。" if details else ""
        fields_key = (
            "checked_fields" if kind == "transfusion_records_consistent" else "differing_fields"
        )
        fields = labels(fields_key, _TRANSFUSION_FIELD_LABELS)
        if kind == "transfusion_records_consistent" and fields:
            return f"手术记录、麻醉记录和术后首次病程记录中的{fields}一致。"
        if kind == "transfusion_records_inconsistent" and fields:
            return f"手术记录、麻醉记录和术后首次病程记录中的{fields}不一致。"
    return ""


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
        reason_specific_gap = _RULE_DATA_GAP_REASON_MESSAGES.get(
            (decision.rule_id, decision.reason_code)
        )
        evaluation_window_gap = _evaluation_window_gap_message(
            rule_id=decision.rule_id,
            reason_code=decision.reason_code,
        )
        controlled_gap = customer_gap_message(
            decision.reason_code,
            missing_items=_missing_item_labels(decision),
        )
        rule_gap = _RULE_DATA_GAP_MESSAGES.get(decision.rule_id)
        if reason_specific_gap is not None:
            findings, evidence, suggestion = reason_specific_gap
        elif evaluation_window_gap is not None:
            findings, evidence, suggestion = evaluation_window_gap
        elif controlled_gap is not None:
            findings, evidence, suggestion = (
                controlled_gap.findings,
                controlled_gap.evidence,
                controlled_gap.suggestion,
            )
            if rule_gap is not None:
                rule_finding, evidence, suggestion = rule_gap
                findings = f"{findings}；{rule_finding}"
        elif rule_gap is not None:
            findings, evidence, suggestion = rule_gap
        else:
            findings, evidence, suggestion = _DATA_GAP_MESSAGES.get(
                decision.reason_code,
                (findings, evidence, suggestion),
            )
    elif decision.final_state is CustomerFinalState.NON_COMPLIANT:
        findings, evidence, suggestion = _RULE_NON_COMPLIANT_MESSAGES.get(
            decision.rule_id,
            (findings, evidence, suggestion),
        )
        if decision.rule_id == "LX0609-018":
            findings = _lx018_criterion_finding(decision.criterion_results) or findings
            evidence = "已分别核对主诉字数及主诉与入院第一诊断的诊断指向。"
            suggestion = "请精简主诉，并确保主诉提供的诊断线索能够支持入院第一诊断。"
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
        if decision.rule_id == "LX0609-018":
            findings = _lx018_criterion_finding(decision.criterion_results) or findings
            evidence = "主诉字数已核对，但诊断指向的自动判断未形成可靠结论。"
            suggestion = "请人工核对主诉提供的诊断线索是否能够支持入院第一诊断。"
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
