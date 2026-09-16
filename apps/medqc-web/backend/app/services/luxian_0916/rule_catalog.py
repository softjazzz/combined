"""Luxian0916 的静态规则目录；此模块不依赖其它业务规则包。"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import CUSTOMER_RESULT_STATUSES


@dataclass(frozen=True)
class Luxian0916RuleDefinition:
    rule_id: str
    name: str
    target_document: str
    execution_phase: str
    trigger_type: str
    required_evidence: tuple[str, ...]
    allowed_statuses: frozenset[str] = CUSTOMER_RESULT_STATUSES

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "target_document": self.target_document,
            "execution_phase": self.execution_phase,
            "trigger_type": self.trigger_type,
            "required_evidence": list(self.required_evidence),
            "allowed_statuses": sorted(self.allowed_statuses),
        }


def _rule(
    number: int,
    name: str,
    target_document: str,
    execution_phase: str,
    trigger_type: str,
    *required_evidence: str,
) -> Luxian0916RuleDefinition:
    return Luxian0916RuleDefinition(
        rule_id=f"LX0916-{number:03d}",
        name=name,
        target_document=target_document,
        execution_phase=execution_phase,
        trigger_type=trigger_type,
        required_evidence=required_evidence,
    )


LUXIAN_0916_RULE_CATALOG: tuple[Luxian0916RuleDefinition, ...] = (
    _rule(1, "再次或多次入院记录未总结既往住院诊疗经过", "入院记录", "direct", "既往住院事实", "入院记录", "既往住院次数", "既往诊疗经过事实"),
    _rule(2, "无完全民事行为能力患者填写为病史陈述者", "入院记录", "direct", "民事行为能力", "入院记录", "民事行为能力", "病史陈述者"),
    _rule(3, "现病史记录不全或描述不清", "入院记录", "direct", "文书内容", "入院记录", "现病史完整性事实"),
    _rule(4, "未记录与鉴别诊断有关的重要阳性和阴性症状", "入院记录", "direct", "文书内容", "入院记录", "鉴别诊断症状事实"),
    _rule(5, "未详细记录入院前检查、治疗经过及效果", "入院记录", "direct", "文书内容", "入院记录", "入院前诊疗经过事实"),
    _rule(6, "既往史记录不全", "入院记录", "direct", "文书内容", "入院记录", "既往史完整性事实"),
    _rule(7, "个人史、婚育史、月经史或家族史记录缺失", "入院记录", "direct", "文书内容", "入院记录", "个人与家族史完整性事实"),
    _rule(8, "儿童患者缺婴幼儿喂养史或生长发育史", "入院记录", "direct", "儿童适用性", "入院记录", "年龄", "儿童成长史事实"),
    _rule(9, "体格检查遗漏重要体征或记录不准确", "入院记录", "direct", "文书内容", "入院记录", "体格检查完整性事实"),
    _rule(10, "首次病程记录无病例特点", "首次病程记录", "direct", "文书内容", "首次病程记录", "病例特点事实"),
    _rule(11, "首次病程记录病例特点未归纳或不全面", "首次病程记录", "direct", "文书内容", "首次病程记录", "病例特点归纳事实"),
    _rule(12, "首次病程记录缺诊断依据、鉴别诊断或诊疗计划", "首次病程记录", "direct", "文书内容", "首次病程记录", "诊疗要素事实"),
    _rule(13, "首次病程记录诊断依据或鉴别诊断不充分", "首次病程记录", "direct", "文书内容", "首次病程记录", "诊断与鉴别依据事实"),
    _rule(14, "首次病程记录诊疗计划不全面或不具体", "首次病程记录", "direct", "文书内容", "首次病程记录", "诊疗计划事实"),
    _rule(15, "重要病情变化未记录或记录不全", "病程记录", "event", "病情变化事件", "病情变化事件", "对应病程记录"),
    _rule(16, "对病情变化无分析判断或具体处理意见", "病程记录", "event", "病情变化事件", "病情变化事件", "对应病程分析与处理"),
    _rule(17, "存在不合理检查或不合理用药", "医嘱与病程记录", "event", "检查或用药医嘱", "检查或用药医嘱", "医学合理性事实"),
    _rule(18, "危急值报告及处理记录不完整", "危急值处理记录", "event", "危急值事件", "危急值事件", "报告与处理记录"),
    _rule(19, "重要操作未记录或记录不规范", "操作记录", "event", "重要操作事件", "重要操作事件", "操作记录"),
    _rule(20, "修正或补充诊断未记录理由和依据", "诊断修正记录", "event", "诊断修正或补充事件", "诊断修正事件", "理由与依据"),
    _rule(21, "手术同意书缺项或描述不清", "手术同意书", "event", "手术安排或手术事件", "手术事件", "手术同意书"),
    _rule(22, "麻醉同意书缺项或描述不清", "麻醉同意书", "event", "麻醉安排或麻醉事件", "麻醉事件", "麻醉同意书"),
    _rule(23, "无麻醉记录", "麻醉记录", "event", "已实施麻醉", "麻醉实施事件", "麻醉记录"),
    _rule(24, "麻醉记录缺项或描述不清", "麻醉记录", "event", "已形成麻醉记录", "麻醉记录", "麻醉记录完整性事实"),
    _rule(25, "手术记录缺项或描述不清", "手术记录", "event", "已实施手术", "手术实施事件", "手术记录完整性事实"),
    _rule(26, "手术安全核查记录缺项或描述不清", "手术安全核查记录", "event", "已实施手术", "手术实施事件", "安全核查记录完整性事实"),
    _rule(27, "急诊手术缺主治及以上医师指示记录", "手术相关记录", "event", "急诊手术事件", "急诊手术事件", "上级医师指示记录"),
    _rule(28, "非计划再次手术相关记录未说明上次手术情况或原因", "手术相关记录", "event", "非计划再次手术事件", "再次手术事件", "上次手术情况与原因"),
    _rule(29, "特殊诊疗、特殊用药、试验、高耗材或自费项目同意书不清", "特殊项目同意书", "event", "特殊诊疗事件", "特殊诊疗事件", "对应同意书"),
    _rule(30, "病危（重）通知书缺项或描述不清", "病危（重）通知书", "event", "病危或病重状态事件", "病危病重事件", "病危（重）通知书"),
    _rule(31, "出院记录诊疗经过不全面或不详细", "出院记录", "discharge", "出院前检查时点", "出院记录", "诊疗经过完整性事实"),
    _rule(32, "出院医嘱缺失或不完整", "出院医嘱", "discharge", "出院前检查时点", "出院安排", "出院医嘱完整性事实"),
)

_RULES_BY_ID = {item.rule_id: item for item in LUXIAN_0916_RULE_CATALOG}


def get_luxian_0916_rule_catalog() -> tuple[Luxian0916RuleDefinition, ...]:
    return LUXIAN_0916_RULE_CATALOG


def get_luxian_0916_rule_definition(rule_id: str) -> Luxian0916RuleDefinition:
    try:
        return _RULES_BY_ID[rule_id]
    except KeyError as exc:
        raise ValueError(f"unknown Luxian0916 rule_id: {rule_id}") from exc
