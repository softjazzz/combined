"""LX0609 客户整改建议的受控投影。

本模块只把规则身份、已通过白名单校验的展示事实和受控子结论组织为
客户可执行的修改建议。它不读取病历正文、不调用模型，也不参与状态归约。
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .phase_scope import load_luxian_0609_phase_scope

_RULE_SCOPE = load_luxian_0609_phase_scope()
PENDING_RULE_IDS = frozenset(
    entry.rule_id
    for entry in _RULE_SCOPE
    if entry.phase_status != "phase_1_target"
)
ACTIVE_FORMAL_RULE_IDS = tuple(
    entry.rule_id
    for entry in _RULE_SCOPE
    if entry.phase_status == "phase_1_target"
)

_SAFE_NOTE = (
    "请依据本次实际诊疗事实补充，保留原始记录；"
    "不要编造未核实事实，不要倒签。"
)

# 每条正式规则均有一个完整的四段式整改模板。第三项保留现有规则建议的
# 业务动作，前两项用于把“改什么、补什么”显式呈现给客户。
_RULE_ACTIONS: dict[str, tuple[str, str, str]] = {
    "LX0609-001": ("入院记录", "入院记录及完成时间", "请补充入院记录，并确保在入院后24小时内完成。"),
    "LX0609-002": ("首次病程记录", "首次病程记录、病例特点及完成时间", "请补充首次病程记录，并确保在入院后8小时内完成。"),
    "LX0609-003": ("每台已实施手术的手术记录", "手术名称、术者、手术经过及完成时间", "请按每台已实施手术补充对应手术记录，并在手术结束后24小时内完成。"),
    "LX0609-004": ("抢救记录", "抢救经过、处置结果及完成时间", "请补充本次抢救记录，并确保在抢救结束后6小时内完成。"),
    "LX0609-005": ("主治医师及以上首次查房记录", "首次查房判断、处理意见及完成时间", "请补充主治医师及以上首次查房记录，并确保在入院后48小时内完成。"),
    "LX0609-006": ("副主任医师或主任医师首次查房记录", "首次查房判断、处理意见及完成时间", "请补充副主任医师或主任医师首次查房记录，并确保在入院后72小时内完成。"),
    "LX0609-007": ("病情稳定阶段的上级医师查房病程", "病情判断、查房意见及记录日期", "请在病情稳定阶段至少每3天记录一次上级医师查房病程。"),
    "LX0609-008": ("病重期间的查房或相关病程", "病重医嘱期间的病情判断、处置及记录日期", "请在病重医嘱期间至少每2天记录一次查房或相关病程。"),
    "LX0609-009": ("病危期间每日病程及病情变化记录", "病情变化、处置措施和每日记录日期", "请在病危医嘱期间每日记录病程，并在明确病情变化后24小时内记录处置情况。"),
    "LX0609-010": ("CT/MRI医嘱、检查主记录、报告及检查前病程", "每条医嘱的唯一关联、检查原因和对应结果", "请逐条核对结果列出的CT/MRI医嘱，补齐对应检查主记录、检查报告及检查前病程中的检查原因。"),
    "LX0609-011": ("CT/MRI报告后病程记录", "报告结果、临床意义及报告后24小时内的记录时间", "请在CT/MRI报告出具后24小时内的病程中记录检查结果。"),
    "LX0609-012": ("CT/MRI阳性结果分析病程", "阳性结果的临床意义、处置措施和后续计划", "请在检查报告出具后24小时内的病程中，记录阳性结果的临床意义、处置措施及后续计划。"),
    "LX0609-013": ("手术记录或病程中的病理结果记录", "病理最终结果、临床意义及后续处置", "请在手术记录或病程记录中补充病理报告结果及后续处置。"),
    "LX0609-014": ("细菌培养报告后病程记录", "培养结果、临床意义和报告后24小时内的记录时间", "请在细菌培养报告出具后24小时内的病程中记录培养结果。"),
    "LX0609-015": ("阳性菌结果分析病程", "阳性菌结果的临床意义、抗感染调整和后续计划", "请在培养报告出具后24小时内的病程中，记录阳性菌结果的临床意义、抗感染调整及后续计划。"),
    "LX0609-016": ("入院记录现病史和首次病程病例特点", "本次病情分析、诊疗判断和记录差异", "请补充本次病情的独立分析、检查结果和诊疗调整，避免直接复制另一份文书。"),
    "LX0609-017": ("高相似病程记录", "当日病情变化、检查结果、诊疗判断和调整依据", "请逐组核对结果列出的高相似病程，删除机械复制内容，并补充当日病情变化、检查结果和诊疗调整。"),
    "LX0609-018": ("主诉及入院第一诊断", "支持第一诊断的关键症状、体征和持续时间", "请精简主诉，并补充能够支持入院第一诊断的关键临床线索。"),
    "LX0609-019": ("手术记录或对应病程中的病理取材记录", "取材部位、取材时间、送检项目和送检情况", "请在手术记录或对应病程中补充病理取材部位、时间及送检情况。"),
    "LX0609-020": ("每次会诊意见及对应执行记录", "对应的执行措施、执行结果或未执行原因", "请针对结果列出的未闭环建议，在后续病程中补记具体执行措施、执行结果或未执行原因。"),
    "LX0609-021": ("会诊申请单", "具体临床问题、会诊理由和明确目的", "请在会诊申请中写明具体临床问题、会诊理由和明确目的。"),
    "LX0609-022": ("会诊记录单", "针对当前病情的判断、具体措施、执行条件、观察指标及复评安排", "请按“病情判断—具体措施—执行时点或条件—观察指标—复评或随访安排”书写，例如：“结合目前……，考虑……；建议于……完成……或给予……，观察……；如……则……，并于……复评。”"),
    "LX0609-023": ("会诊意见执行记录", "具体措施、执行结果、未执行原因和后续安排", "请在会诊意见执行记录中归纳具体措施、执行结果和后续安排，不要仅照抄会诊意见。"),
    "LX0609-024": ("本次正式手术记录", "淋巴结清扫、取样或前哨淋巴结处理情况；未处理时写明原因", "请在本次正式手术记录中如实写明淋巴结清扫、取样或前哨淋巴结处理的范围、数量和送检情况；未实施时应记录临床原因。"),
    "LX0609-026": ("化疗医嘱和治疗病程", "药物名称、剂量、用法、时间及两份记录的对应关系", "请核对化疗医嘱与病程记录，统一药物名称、剂量、用法和用药时间。"),
    "LX0609-027": ("恶性肿瘤出院记录", "后续诊疗计划、治疗安排、复诊时间和随访要求", "请在出院记录中补充恶性肿瘤后续诊疗计划、治疗安排和随访要求。"),
    "LX0609-029": ("本次已实施手术的术前小结", "术前诊断、手术指征、拟施手术及注意事项", "请为本次已实施手术补充术前小结，并记录术前诊断、手术指征、拟施手术及注意事项。"),
    "LX0609-030": ("每台已实施手术的手术记录", "手术名称、时间、术者、经过、结果和术后注意事项", "请为每台已实施手术补充对应手术记录，并核对手术名称、时间和术者。"),
    "LX0609-031": ("手术记录签名", "术者身份、签名医师身份和签署时间", "请由本次手术的术者完成手术记录签名，并核对术者与签名医师信息。"),
    "LX0609-032": ("手术安全核查表", "麻醉前、手术前及手术后核查项目和相关签名", "请为本次已实施手术补充手术安全核查表，并完成相关核查和签名。"),
    "LX0609-033": ("手术知情同意书", "告知内容、手术风险、替代方案及相关签名", "请补充并归档本次手术知情同意书，完成告知内容和相关签名。"),
    "LX0609-034": ("麻醉知情同意书", "麻醉方式、风险告知、替代方案及相关签名", "请补充并归档本次麻醉知情同意书，完成麻醉风险告知和相关签名。"),
    "LX0609-035": ("麻醉知情同意书缺项", "结果列出的告知内容、双方签名及签署时间", "请按结果列出的缺项补全麻醉知情同意书内容、双方签名及签署时间。"),
    "LX0609-036": ("麻醉术前及术后访视记录", "麻醉前风险评估、术后恢复情况和记录时间", "请补充本次麻醉的术前和术后访视记录，并分别记录评估结论及处理计划。"),
    "LX0609-037": ("麻醉访视记录缺项", "结果列出的麻醉评估、患者状态、并发症和签名字段", "请按结果列出的缺项补全麻醉术前和术后访视记录。"),
    "LX0609-038": ("麻醉记录单", "麻醉方式、用药、生命体征及术中事件", "请补充本次麻醉记录单，并核对麻醉方式、用药、生命体征及术中事件记录。"),
    "LX0609-039": ("术前讨论记录", "手术指征、风险、方案、术者参加情况和讨论结论", "请补充术前讨论记录，写明手术指征、风险、方案并记录术者参加情况。"),
    "LX0609-040": ("四级手术术前多学科讨论记录", "参会科室、讨论意见、手术方案和讨论结论", "请补充本次四级手术的术前多学科讨论记录，并记录参会科室、讨论意见及手术方案。"),
    "LX0609-041": ("输血知情同意书", "输血告知内容、风险、替代方案和双方签名", "请补充并归档本次输血知情同意书，完成告知内容和相关签名。"),
    "LX0609-042": ("输血知情同意书缺项", "告知内容、患者或代理人签名、医师签名及签署时间", "请按结果列出的缺项补全输血知情同意书内容、双方签名及签署时间。"),
    "LX0609-043": ("输血前九项检查", "缺失项目、检验结果、报告时间及输血前时序", "请补充缺失的输血前检查结果及权威报告时间，并核对其早于输血开始。"),
    "LX0609-044": ("输血申请单", "输血申请理由、至少一项客观评估指标、申请时间及实际输血时间", "请补全输血申请理由和客观评估指标，并确保申请在实际输血前完成。"),
    "LX0609-045": ("输血病程记录", "本次输血事件与病程的对应关系、输血原因及过程", "请补充与本次输血事件对应的输血病程记录，并写明原因、过程和结果。"),
    "LX0609-046": ("输血病程记录缺项", "输血原因、起止时间、成分、剂量、过程观察及反应处理", "请补充输血病程记录中结果列出的缺项，并记录输血效果和不良反应处理。"),
    "LX0609-047": ("输血后评价记录", "输血结束时间、评价时间、疗效及不良反应", "请在输血结束后24小时内完成效果评价，并记录疗效及不良反应处理。"),
    "LX0609-048": ("手术、麻醉和术后首次病程中的输血明细", "血液成分、剂量、时间及三份文书的一致性说明", "请逐项核对三份文书的输血成分、剂量和时间，并补充差异说明。"),
    "LX0609-050": ("入院7天后疑难病例讨论记录", "诊断不明确的依据、讨论意见、诊疗方案和讨论结论", "请补充疑难病例讨论记录，写明诊断难点、讨论意见、诊疗方案及结论。"),
    "LX0609-051": ("死亡病历讨论记录", "死亡原因、诊疗经过、经验教训和讨论结论", "请在患者死亡后7天内完成死亡病历讨论，并记录讨论结论。"),
    "LX0609-052": ("PL/PH危急值处置记录", "报告时间、接收人、患者评估、处置措施、复查结果及完成时间", "请补充危急值报告、接收、评估、处置和复查全过程记录，并核对6小时时限。"),
    "LX0609-053": ("PL/PH危急值报告后的处置记录", "危急值报告、患者评估、具体处置、复查结果和未处置原因", "请在危急值报告后补充患者评估、具体处置、复查结果及处理依据。"),
    "LX0609-054": ("抗菌药物医嘱及相关病程", "用药原因、方案调整动作、调整理由和依据", "请在病程中补充抗菌药物的使用原因、方案调整理由及相关依据。"),
    "LX0609-055": ("抗菌药物48至72小时效果评价", "疗效、检验变化、病原学结果和方案调整", "请在首次使用抗菌药物后48至72小时内记录疗效、检验变化和方案调整。"),
    "LX0609-057": ("经验性抗菌药物用药病程", "经验用药理由、病情依据及无样本可采原因", "请在病程中记录经验使用抗菌药物的理由，或明确记录无样本可采原因。"),
    "LX0609-058": ("特殊级抗菌药物专家支持记录", "专家查房或会诊意见、用药依据和后续评价", "请补充使用特殊级抗菌药物前的专家查房或会诊意见，并记录用药依据。"),
    "LX0609-060": ("死亡记录", "死亡时间、死亡过程、死亡原因和记录完成时间", "请补充并归档本次住院的死亡记录，写明死亡时间、过程和死亡原因。"),
    "LX0609-061": ("出院记录", "出院诊断、住院经过、出院情况及完成时间", "请补充出院记录，并确保在患者出院后24小时内完成。"),
    "LX0609-062": ("出院带药明细", "每项药品的名称、剂量、给药途径和用药时间", "请按每项出院带药补全药品名称、剂量、给药途径和用药时间。"),
    "LX0609-063": ("出院记录诊断", "权威出院诊断、出院记录诊断及排列顺序", "请核对出院记录与权威出院诊断，统一诊断内容和排列顺序。"),
    "LX0609-064": ("每台手术术后连续3天病程及术者查房", "术后次日起连续3天的病程记录和术者查房情况", "请按每台手术分别补齐术后次日起连续3天的病程记录，并记录术者查房情况。"),
    "LX0609-065": ("术后72小时内上级医师查房记录", "术后病情、处置、计划、查房医师身份和完成时间", "请在术后72小时内完成上级医师查房，并记录术后病情、处置及计划。"),
    "LX0609-066": ("每台手术术后首次病程记录", "手术关联、术后病情、术后诊断和处置计划", "请为每台已实施手术补充对应的术后首次病程记录。"),
    "LX0609-067": ("出院前一天或当天病程记录", "出院前病情、治疗结果、出院安排和记录日期", "请在出院前一天或出院当天补充病程，记录出院前病情和出院安排。"),
    "LX0609-068": ("出院前上级医师意见或自动出院记录", "同意出院意见，或请示、劝阻、风险告知及书面签署过程", "请补充上级医师出院意见；自动出院时应记录请示、劝阻或风险告知及书面签署情况。"),
    "LX0609-069": ("会诊申请和会诊记录时间", "申请时间、完成时间及24小时内的完成关系", "请在会诊申请后24小时内完成会诊，并准确记录申请和完成时间。"),
    "LX0609-070": ("输血前九项检查", "乙肝五项、丙肝、艾滋、梅毒和谷丙转氨酶检查结果及时间", "请在输血前补齐乙肝五项、丙肝、艾滋、梅毒和谷丙转氨酶检查。"),
    "LX0609-071": ("经治医师变更的交班和接班记录", "每次变更对应的交班记录、接班记录、完成时间及未完成原因", "请在经治医师变更时完成交班记录，并在24小时内完成接班记录。"),
    "LX0609-072": ("转科医嘱后的转出和转入记录", "转科医嘱、转出记录、转入记录及完成时间", "请在转科医嘱后24小时内完成转出和转入记录。"),
    "LX0609-073": ("转科医嘱对应的转入、转出记录", "转科原因、转出交接、转入评估和两份记录的关联", "请为本次转科同时补齐转出记录和转入记录。"),
    "LX0609-074": ("每次诊断修正或补充记录", "修改理由、诊断依据、修改时间和修正后的诊断", "请对每次诊断修正或补充记录修改理由及诊断依据。"),
}

_MISSING_FIELD_LABELS = {
    "drug_name": "药品名称",
    "dose": "剂量",
    "route": "给药途径",
    "duration": "用药时间",
    "patient_information": "患者基本信息",
    "diagnosis": "诊断",
    "indication": "输血指征",
    "component": "血液成分",
    "risks": "输血风险",
    "alternatives": "替代方案",
    "patient_or_agent_signature": "患者或代理人签名",
    "physician_signature": "医师签名",
    "signed_time": "签署时间",
    "laboratory_indicator": "输血前检验指标",
    "application_reason": "输血申请理由",
    "risk_history_or_status": "输血风险或患者当前情况",
    "transfusion_history_or_reaction": "既往输血史或输血反应史",
    "planned_component": "拟输注血液成分",
    "expected_effect": "预期效果",
    "reason_or_indication": "输血原因或指征",
    "start_and_end_time": "输血开始及结束时间",
    "process_observation": "输血过程观察",
    "reaction_and_handling": "输血反应及处理",
    "effect": "输血效果",
}


def _controlled_missing_fields(
    facts: Mapping[str, Any] | None,
    *,
    rule_id: str = "",
) -> str:
    if not isinstance(facts, Mapping):
        return ""
    values = facts.get("missing_fields")
    if not isinstance(values, (list, tuple)):
        return ""
    labels = []
    for item in values:
        if not isinstance(item, str) or item not in _MISSING_FIELD_LABELS:
            continue
        label = _MISSING_FIELD_LABELS[item]
        if item == "dose" and rule_id == "LX0609-046":
            label = "输注量"
        labels.append(label)
    return "、".join(dict.fromkeys(labels))


def _consultation_targets(facts: Mapping[str, Any] | None) -> tuple[str, str]:
    if not isinstance(facts, Mapping):
        return "", ""
    episodes = facts.get("episode_results")
    if not isinstance(episodes, (list, tuple)):
        return "", ""
    vague: list[tuple[int, str]] = []
    missing: list[tuple[int, str]] = []
    for item in episodes:
        if not isinstance(item, Mapping):
            continue
        index = item.get("episode_index")
        state = item.get("semantic_state")
        if type(index) is not int or index <= 0 or index > 100:
            continue
        record_time = str(item.get("record_time") or "")
        if re.fullmatch(
            r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?",
            record_time,
        ) is None:
            record_time = ""
        document_title = (
            "会诊记录单" if item.get("document_title") == "会诊记录单" else ""
        )
        locator = f"第{index}次会诊记录"
        if document_title:
            locator = f"《{document_title}》（第{index}次）"
        if record_time:
            locator = f"{record_time}{locator}"
        if state == "vague":
            vague.append((index, locator))
        elif state == "missing":
            missing.append((index, locator))
    issue_items = sorted({*vague, *missing})
    if not issue_items:
        return "", ""
    if all(locator == f"第{index}次会诊记录" for index, locator in issue_items):
        target = "、".join(f"第{index}次" for index, _ in issue_items) + "会诊记录"
        needs = []
        if vague:
            needs.append(
                "、".join(f"第{index}次" for index, _ in sorted(set(vague)))
                + "意见补充明确诊疗判断"
            )
        if missing:
            needs.append(
                "、".join(f"第{index}次" for index, _ in sorted(set(missing)))
                + "意见补充明确诊疗意见"
            )
        return target, "；".join(needs)
    target = "、".join(locator for _, locator in issue_items)
    needs = []
    if vague:
        needs.append(
            "、".join(locator for _, locator in sorted(set(vague)))
            + "意见补充明确诊疗判断"
        )
    if missing:
        needs.append(
            "、".join(locator for _, locator in sorted(set(missing)))
            + "意见补充明确诊疗意见"
        )
    return target, "；".join(needs)


def _personalized_action(
    *,
    rule_id: str,
    facts: Mapping[str, Any] | None,
) -> tuple[str, str] | None:
    if rule_id == "LX0609-022":
        target, need = _consultation_targets(facts)
        if target and need:
            return target, need
    missing = _controlled_missing_fields(facts, rule_id=rule_id)
    if missing and rule_id in {"LX0609-042", "LX0609-044", "LX0609-046", "LX0609-062"}:
        return _RULE_ACTIONS[rule_id][0], missing
    return None


def _structured_action(
    *,
    target: str,
    required: str,
    recommendation: str,
    note: str = _SAFE_NOTE,
) -> str:
    return (
        f"修改对象：{target}\n"
        f"需要补充：{required}\n"
        f"推荐写法：{recommendation}\n"
        f"注意事项：{note}"
    )


def build_customer_remediation_suggestion(
    *,
    rule_id: str,
    status: str,
    reason_code: str = "",
    facts: Mapping[str, Any] | None = None,
) -> str:
    """生成结构化建议；输入只能是已通过白名单的受控事实。"""

    normalized_rule_id = str(rule_id or "").strip().upper()
    normalized_status = str(status or "").strip().lower()
    if normalized_rule_id in PENDING_RULE_IDS or normalized_status == "not_executed":
        return ""
    if normalized_status == "non_compliant":
        action = _RULE_ACTIONS.get(normalized_rule_id)
        if action is None:
            return ""
        target, required, recommendation = action
        personalized = _personalized_action(
            rule_id=normalized_rule_id,
            facts=facts,
        )
        if personalized is not None:
            target, required = personalized
        return _structured_action(
            target=target,
            required=required,
            recommendation=recommendation,
        )

    if normalized_status == "data_gap":
        action = _RULE_ACTIONS.get(normalized_rule_id)
        target = f"{action[0]}的核对资料" if action else "本质控点所需核对资料"
        required = "完整可读取的文书、权威时间及必要关联字段"
        recommendation = (
            "先确认资料同步完整并补齐关联信息后重新评估；"
            "仅在人工确认内容确实缺失后再按本质控点整改。"
        )
        note = "资料不足不代表病历内容缺失，不得直接判定合规或不合规。"
        if reason_code == "candidate_scope_incomplete":
            recommendation = "无需补充病历资料；请缩小本次候选核对范围后重新执行。"
            note = "候选超过安全核对范围时不得据此判定病历缺失，也不得伪造完整结论。"
        return _structured_action(
            target=target,
            required=required,
            recommendation=recommendation,
            note=note,
        )

    if normalized_status == "evaluation_unknown":
        if (
            normalized_rule_id == "LX0609-001"
            and reason_code == "evidence_conflict"
            and isinstance(facts, Mapping)
            and facts.get("failure_kind") == "evidence_time_conflict"
            and facts.get("timeliness_state") == "before"
        ):
            return "请核对住院登记时间和入院记录完成时间。"
        action = _RULE_ACTIONS.get(normalized_rule_id)
        target = action[0] if action else "本质控点待复核资料"
        return _structured_action(
            target=target,
            required="可核验的完整文书、权威时间及必要关联信息",
            recommendation="请人工核对相关文书与结构化资料，必要时补齐可验证信息后重新评估。",
            note="当前结论不确定，不得将其当作合规或确定问题，也不得按建议倒推补写事实。",
        )

    if normalized_status == "technical_error":
        return _structured_action(
            target="本质控点的质控执行链",
            required="可用的数据源、规则执行服务及结果保存能力",
            recommendation="请排查数据读取、规则执行或结果保存异常，恢复后重新质控。",
            note="技术异常不代表病历存在缺陷，不应要求医务人员据此补写临床记录。",
        )

    # 当前无异常状态时不生成整改建议，避免给合规或不适用结果附加动作。
    _ = reason_code
    return ""
