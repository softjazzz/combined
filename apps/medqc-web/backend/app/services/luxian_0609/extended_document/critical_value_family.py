"""LX0609 危急值规则族（06-04-01 / 06-04-02）独立执行器。

由 `native_extended_document_execution.py` 拆出（Batch 4 Pilot #1）：
- 拥有危急值病程处置识别、项目标签绑定、跨报告隔离与逐行证据绑定逻辑；
- 仅依赖不可变快照/材料仓、`extended_document_critical_value` 确定性内核与
  `extended_document.family_runtime` 公共契约，不反向依赖总调度模块。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import re
from typing import Any, Mapping, Sequence

from ..evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from ..evidence_snapshot import Luxian0609EvidenceSnapshot
from ..extended_document_critical_value import (
    CRITICAL_VALUE_RULE_IDS,
    CriticalValueDisposition,
    CriticalValueInput,
    CriticalValueItem,
    CriticalValueOutcome,
    effective_disposition_elapsed_seconds,
    evaluate_critical_value_rules,
    select_critical_value_fact_refs,
)
from .family_runtime import (
    ExtendedDocumentFamilyOutcome,
    SourceRowsCache,
    build_extended_decision as _decision,
    fact_refs as _fact_refs,
    material_text as _material_text,
    resolve_evaluation_horizon,
    source_rows as _source_rows,
)
from .shared import _clean, _parse_datetime, _row_time


# 危急值病程处置识别（合并扫描 daily_course_record / senior_course_record）。
_CRITICAL_VALUE_TITLE_PATTERN = re.compile(r"危急值")
_CRITICAL_VALUE_TITLE_STRIP_PATTERN = re.compile(r"危急值(?:处理|处置|报告)?记录")
_CRITICAL_VALUE_UNHANDLED_PATTERN = re.compile(
    r"(?:尚|暂|仍|并)?未(?:予|做|作|行|进行|被)?(?:处理|处置|执行|实施|落实|采取(?:任何|有效)?(?:措施|处理|处置))|"
    r"暂无(?:特殊)?(?:处理|处置)|"
    r"未(?:见|有)(?:明确)?(?:处理|处置)|"
    r"(?<![已予经])待(?:医师|医生|值班医师|值班医生|上级医师|临床)?(?:处理|处置|评估处理)|"
    r"等待(?:医师|医生|值班医师|值班医生|上级医师)(?:处理|处置|查看|评估)?"
)
_CRITICAL_VALUE_UNEXECUTED_DECLARATION_PATTERN = re.compile(
    r"(?:尚|暂|仍|并)?未(?:予|行|被)?(?:执行|实施|落实)"
)
_CRITICAL_VALUE_SENTENCE_SPLIT_PATTERN = re.compile(r"[。；;！？!?\r\n]+")
_CRITICAL_VALUE_CLAUSE_SPLIT_PATTERN = re.compile(r"[，,]+")
_CRITICAL_VALUE_CLAUSE_NEGATION_PATTERN = re.compile(
    r"(?:尚|暂|并|仍)?未(?:予|行|做|作|给|再|见|有|能)?|"
    r"不(?:予|给|行|做|作|能|再|拟|考虑|建议|需要?)|"
    r"暂不|暂无法|无法|无需|不必|拒绝|拒不|无特殊|取消|暂缓|免予"
)
_CRITICAL_VALUE_CLAUSE_CONDITIONAL_OPENER_PATTERN = re.compile(
    r"(?:^|[：:])\s*(?:若|如果|倘若|假如|一旦|万一|必要时|"
    r"如(?:有|再|仍|复查|继续|出现|无|下降|升高|恶化|加重|持续|不缓解|未改善)|"
    r"(?:待|等)[^，,。；;\r\n]{0,16}(?:后再?|时再?))"
)
_CRITICAL_VALUE_CLAUSE_CONDITIONAL_PREFIX_PATTERN = re.compile(
    r"若|如果|倘若|假如|一旦|万一|必要时|"
    r"如(?:有|再|仍|复查|继续|出现|无改善|无好转|无缓解|下降|升高|恶化|加重|持续|不缓解|未改善)|"
    r"再予|再行|再考虑|再决定|则予|则行|则考虑|是否|"
    r"(?:待|等)[^，,。；;\r\n]{0,16}(?:后|时)|"
    r"(?<![已予经])待\s*$"
)
_CRITICAL_VALUE_CLAUSE_PLANNED_PREFIX_PATTERN = re.compile(
    r"(?<![模疑比])拟(?!诊)|"
    r"计划|(?<!做好)准备(?!完毕|工作|充分)|打算|"
    r"待(?:行|予|给|请|复查|复测|进一步)|"
    r"将(?:予|行|给|于)"
)
_CRITICAL_VALUE_CLAUSE_EXECUTED_RESET_PATTERN = re.compile(
    r"^(?:现已|目前(?:已|予|正|继续|维持)|已经?|实际已|"
    r"(?:随后|之后|稍后|后续|后)(?:已|予|给)|"
    r"(?:于\s*)?\d{1,2}\s*[:：]\s*\d{2}\s*(?:已|予|给|完成|针对[^，,。；;\r\n]{0,12}?已))"
)
_CRITICAL_VALUE_TOPIC_CONTINUATION_PATTERN = re.compile(
    r"危急值|初报|复报|本次|该值|上述"
)
# PDF 版面硬折行常把连续中文词组拦腰断行（如“积极抗感\n染”）；仅在行长>=24且前后均为汉字时合并折行，
# 保留短行、标点断句及标题/签名换行边界。
_CRITICAL_VALUE_PDF_LINE_WRAP_PATTERN = re.compile(
    r"(?<=[^\r\n]{23}[\u4e00-\u9fff])\r?\n(?=[\u4e00-\u9fff])"
)
_CRITICAL_VALUE_CLAUSE_COMPLETED_PATTERN = re.compile(
    r"已经?|现已|(?<![发出体实呈表再显])现(?:行)?(?=[予给行补输调复监])"
)
_CRITICAL_VALUE_HANDLING_ACTION_PATTERN = re.compile(
    r"补钾|氯化钾|泵钾|降钾|葡萄糖酸钙|补钙|纠酸|碳酸氢钠|补液|"
    r"输注血小板|输血小板|合血小板|备血小板|预约血小板|输注.{0,8}血浆|输血浆|合血浆|备血浆|"
    r"冷沉淀|输注.{0,8}红细胞|输血|合血|备血|CRRT|透析|"
    r"呼吸机|无创(?:辅助)?通气|有创(?:辅助)?通气|氧疗|吸氧|氧流量|吸痰|排痰|"
    r"调高|下调|调整|复查|复测|监测|密观|密切观察|密切关注|"
    r"对症(?:处理|处置|支持|治疗)?|静滴|静推|泵入|"
    r"胰岛素|补糖|葡萄糖|高糖|利尿|呋塞米|甲泼尼龙|止血|抗血小板|营养心肌|"
    r"加强.{0,6}(?:治疗|抗感染|气道管理)|抗感染|予以|给予|加用|改用|换用|停用|"
    r"维持目前|继续(?:当前|目前|无创|加强|合血|预约|动态|密切|观察|治疗|利尿)|"
    r"(?:与|向)(?:患者)?(?:及其)?家属沟通|请.{0,8}会诊|联系输血科|"
    r"(?:经|已予|已|积极|紧急|及时)(?:处理|处置)"
)
_CRITICAL_VALUE_CLOCK_PATTERN = re.compile(r"(?<!\d)(\d{1,2})\s*[:：]\s*(\d{2})(?!\d)")
_CRITICAL_VALUE_NON_LAB_UNIT_PATTERN = re.compile(
    r"^\s*(?:mg|ml|μg|ug|片|粒|袋|支|瓶|小时|分钟|min|天|日|月|年|岁|次|kg|cm|g(?![/／]))(?![a-z0-9])",
    re.IGNORECASE,
)
_CRITICAL_VALUE_ITEM_SYNONYMS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("钾",), ("钾", "血钾", "低钾", "高钾", "补钾", "k+")),
    (("钠",), ("钠", "血钠", "低钠", "高钠", "na+")),
    (("钙",), ("钙", "血钙", "低钙", "高钙", "ca2+")),
    (("血小板", "plt"), ("血小板", "plt")),
    (("血红蛋白", "hgb", "hb"), ("血红蛋白", "hb", "hgb", "贫血")),
    (("白细胞", "wbc"), ("白细胞", "wbc")),
    (("活化部分凝血", "凝血活酶", "aptt"), ("aptt", "活化部分凝血", "凝血活酶", "凝血")),
    (("凝血酶原", "国际标准化比值", "inr"), ("pt", "inr", "凝血酶原", "国际标准化比值", "凝血")),
    (("纤维蛋白原", "fib"), ("纤维蛋白原", "fib", "凝血")),
    (("ph", "酸碱度"), ("ph", "酸碱度", "酸中毒", "碱中毒", "纠酸")),
    (("氧分压", "po2", "pao2"), ("氧分压", "po2", "pao2", "低氧")),
    (("二氧化碳分压", "pco2", "paco2"), ("二氧化碳分压", "pco2", "paco2", "二氧化碳")),
    (("血糖", "葡萄糖", "glu"), ("血糖", "葡萄糖", "glu", "低血糖", "高血糖")),
    (("肌钙蛋白", "ctni", "ctnt"), ("肌钙蛋白", "ctni", "ctnt", "tni", "tnt")),
    (("乳酸", "lac"), ("乳酸", "lac")),
    (("肌酐", "crea"), ("肌酐", "crea")),
    (("胆红素", "tbil", "dbil"), ("胆红素", "tbil", "dbil")),
    (("淀粉酶", "amy"), ("淀粉酶", "amy")),
)
_CRITICAL_VALUE_UNRELATED_TOPIC_PATTERN = re.compile(
    r"另因|此外|另有|另予|发热|退热|退烧|降压|镇痛|失眠|助眠|安眠"
)
_CRITICAL_VALUE_ITEM_ACTION_KEYWORDS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("钾",), ("补钾", "降钾", "氯化钾", "泵钾", "葡萄糖酸钙", "电解质", "透析", "crrt")),
    (("钠",), ("补钠", "降钠", "电解质", "高渗盐")),
    (("钙",), ("补钙", "降钙", "葡萄糖酸钙", "氯化钙", "电解质")),
    (("血小板", "plt"), ("血小板", "输血", "血常规", "出血", "止血")),
    (("血红蛋白", "hgb", "hb"), ("红细胞", "输血", "血常规", "止血", "贫血", "出血")),
    (("白细胞", "wbc"), ("血常规", "升白", "抗感染", "骨髓")),
    (
        ("活化部分凝血", "凝血活酶", "aptt", "凝血酶原", "国际标准化比值", "inr", "纤维蛋白原", "fib"),
        ("凝血", "血浆", "冷沉淀", "输血", "止血", "出血", "维生素k"),
    ),
    (("ph", "酸碱度"), ("纠酸", "碳酸氢钠", "血气", "酸中毒", "碱中毒", "呼吸机", "通气", "透析", "crrt")),
    (("氧分压", "po2", "pao2"), ("氧疗", "吸氧", "氧流量", "呼吸机", "通气", "气道", "吸痰", "血气", "低氧")),
    (("二氧化碳分压", "pco2", "paco2"), ("呼吸机", "通气", "气道", "吸痰", "排痰", "血气", "二氧化碳")),
    (("血糖", "葡萄糖", "glu"), ("胰岛素", "补糖", "高糖", "葡萄糖", "降糖", "血糖")),
    (("肌钙蛋白", "ctni", "ctnt"), ("营养心肌", "抗血小板", "心电图", "心内科", "心肌", "冠脉")),
    (("乳酸", "lac"), ("乳酸", "血气", "补液", "纠酸", "灌注", "crrt")),
    (("肌酐", "crea"), ("透析", "crrt", "肾功", "肾内科", "利尿")),
    (("胆红素", "tbil", "dbil"), ("护肝", "保肝", "退黄", "肝功", "胆红素")),
    (("淀粉酶", "amy"), ("抑酸", "抑酶", "禁食", "胃肠减压", "胰腺", "淀粉酶")),
)
_CRITICAL_VALUE_LAB_LABEL_GROUPS: tuple[tuple[str, ...], ...] = (
    ("血钾", "钾离子", "血清钾", "钾测定", "低钾", "高钾", "k+", "k", "钾"),
    ("血钠", "钠离子", "血清钠", "钠测定", "低钠", "高钠", "na+", "na", "钠"),
    ("血氯", "氯离子", "血清氯", "氯测定", "cl-", "cl", "氯"),
    ("血钙", "游离钙", "钙离子", "血清钙", "钙测定", "低钙", "高钙", "ca2+", "ca++", "ca", "钙"),
    ("血镁", "镁离子", "血清镁", "mg2+"),
    ("血磷", "无机磷", "血清磷"),
    ("空腹血糖", "随机血糖", "指尖血糖", "末梢血糖", "餐后血糖", "血糖", "低血糖", "高血糖", "葡萄糖", "glu"),
    ("血小板计数", "血小板", "plt"),
    ("血红蛋白", "hgb", "hb"),
    ("白细胞计数", "白细胞", "wbc"),
    ("中性粒细胞", "中性粒", "neut", "anc"),
    ("红细胞计数", "红细胞压积", "血细胞比容", "红细胞", "rbc", "hct"),
    ("活化部分凝血活酶时间", "活化部分凝血", "凝血活酶", "aptt"),
    ("凝血酶原时间", "凝血酶原", "国际标准化比值", "inr", "pt"),
    ("纤维蛋白原", "fib"),
    ("凝血酶时间", "tt"),
    ("d-二聚体", "d二聚体", "d-dimer", "fdp"),
    ("酸碱度", "ph"),
    ("动脉氧分压", "氧分压", "pao2", "po2"),
    ("动脉二氧化碳分压", "二氧化碳分压", "paco2", "pco2"),
    ("碳酸氢根", "hco3"),
    ("碱剩余", "be"),
    ("血氧饱和度", "氧饱和度", "spo2", "sao2"),
    ("乳酸", "lac"),
    ("肌酐", "scr", "crea", "cr"),
    ("尿素氮", "尿素", "bun"),
    ("尿酸", "ua"),
    ("总胆红素", "直接胆红素", "间接胆红素", "胆红素", "tbil", "dbil", "ibil"),
    ("谷丙转氨酶", "丙氨酸氨基转移酶", "alt"),
    ("谷草转氨酶", "天门冬氨酸氨基转移酶", "ast"),
    ("白蛋白", "总蛋白", "alb"),
    ("淀粉酶", "amy"),
    ("肌钙蛋白t", "肌钙蛋白i", "超敏肌钙蛋白", "肌钙蛋白", "ctnt", "ctni", "tnt", "tni"),
    ("脑钠肽", "nt-probnp", "probnp", "bnp"),
    ("降钙素原", "pct"),
    ("超敏c反应蛋白", "c反应蛋白", "超敏crp", "crp"),
    ("体温", "心率", "脉搏", "呼吸频率", "血压", "收缩压", "舒张压", "血氧", "尿量", "bp", "hr", "rr"),
)


def _compile_lab_label_pattern(label: str) -> re.Pattern[str]:
    if label == "钾":
        return re.compile(r"(?<!氯化)(?<!枸橼酸)(?<!门冬氨酸)(?<!磷酸)(?<!补)(?<!降)钾")
    if label == "钠":
        return re.compile(r"(?<!碳酸氢)(?<!氯化)(?<!补)(?<!降)钠")
    if label == "钙":
        return re.compile(r"(?<!葡萄糖酸)(?<!氯化)(?<!补)(?<!降)钙")
    if label == "氯":
        return re.compile(r"氯(?!化钾|化钠|化钙)")
    if label == "葡萄糖":
        return re.compile(r"葡萄糖(?!酸钙)")
    if label in {"k", "na", "cl", "ca"}:
        return re.compile(rf"(?<![a-z0-9]){re.escape(label)}(?=\s*[:：=]?\s*(?:\d|$))")
    if label.isascii():
        escaped = re.escape(label)
        if label[-1].isdigit():
            return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])")
        return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z])")
    return re.compile(re.escape(label))


_CRITICAL_VALUE_COMPILED_LAB_LABEL_GROUPS: tuple[
    tuple[tuple[str, ...], tuple[re.Pattern[str], ...]], ...
] = tuple(
    (group, tuple(_compile_lab_label_pattern(label) for label in group))
    for group in _CRITICAL_VALUE_LAB_LABEL_GROUPS
)


def _critical_value_event_key(
    source_key: str,
    row: Mapping[str, Any],
) -> str | None:
    """按来源选择可跨表证明的危急值事件键，不把处置文书自身 ID 当关联键。"""

    fields = (
        ("report_id", "test_id", "document_id")
        if source_key == "labtest_item_report"
        else ("report_id", "test_id")
        if source_key == "crisis_value_record"
        else ()
    )
    for field in fields:
        value = _clean(row.get(field))
        if value:
            return f"{field}:{value}"
    return None


def _critical_value_item_from_row(row: Mapping[str, Any]) -> CriticalValueItem:
    # 报告字段共同证明同一时刻；记录时间不属于危急值报告的权威来源。
    report_times = tuple(
        _parse_datetime(row.get(key))
        for key in ("report_time", "report_datetime")
        if _clean(row.get(key))
    )
    report_time_error = (
        "authoritative_time_missing"
        if not report_times or any(value is None for value in report_times)
        else "authoritative_time_conflict"
        if len(set(report_times)) > 1
        else None
    )
    return CriticalValueItem(
        item_name=_clean(row.get("item_name") or row.get("item_code")),
        flag_values=tuple(
            _clean(row.get(key))
            for key in (
                "result_flag",
                "abnormal_flag",
                "abnormal_indicator",
                "result_status",
                "result_hint",
            )
        ),
        marker_text=_material_text(row),
        display_flag=_clean(
            row.get("result_flag")
            or row.get("abnormal_flag")
            or row.get("abnormal_indicator")
        ),
        report_time=report_times[0] if report_time_error is None else None,
        event_key=_critical_value_event_key("labtest_item_report", row),
        report_time_error=report_time_error,
    )


def _critical_value_disposition_from_row(
    row: Mapping[str, Any],
) -> CriticalValueDisposition | None:
    disposition_time = _row_time(row)
    return CriticalValueDisposition(
        disposition_time=disposition_time,
        event_key=_critical_value_event_key("crisis_value_record", row),
    )


def _critical_value_item_keywords(item_name: str) -> tuple[str, ...]:
    normalized = _clean(item_name).lstrip("*＊").strip()
    lower = normalized.lower()
    keywords: list[str] = []
    for triggers, synonyms in _CRITICAL_VALUE_ITEM_SYNONYMS:
        if any(trigger in lower for trigger in triggers):
            keywords.extend(synonyms)
    stem = re.sub(r"(?:测定|计数|定量|浓度|检查|离子|检测)$", "", normalized).strip()
    for candidate in (normalized.lower(), stem.lower()):
        if len(candidate) >= 2 and candidate not in keywords:
            keywords.append(candidate)
    return tuple(dict.fromkeys(keywords))


def _critical_value_result_tokens(row: Mapping[str, Any]) -> tuple[str, ...]:
    raw = _clean(row.get("result_value") or row.get("result"))
    if not raw:
        return ()
    tokens: list[str] = []
    for match in re.findall(r"\d+(?:\.\d+)?", raw):
        tokens.append(match)
        if "." in match:
            trimmed = match.rstrip("0").rstrip(".")
            if trimmed and trimmed not in tokens:
                tokens.append(trimmed)
    return tuple(dict.fromkeys(tokens))


def _text_mentions_critical_keyword(lower_text: str, keywords: Sequence[str]) -> bool:
    for keyword in keywords:
        if keyword.isascii():
            if re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", lower_text):
                return True
        elif keyword in lower_text:
            return True
    return False


def _lab_label_group_matches_keywords(
    group: tuple[str, ...],
    lower_keywords: frozenset[str],
) -> bool:
    for alias in group:
        if alias in lower_keywords:
            return True
        if not alias.isascii() and len(alias) >= 2:
            if any(
                not kw.isascii() and len(kw) >= 2 and (kw in alias or alias in kw)
                for kw in lower_keywords
            ):
                return True
    return False


def _is_clock_colon_token(text: str, start: int, end: int, token: str) -> bool:
    """仅排除真实时钟数字（如 08:25、08:25:30、2026-06-01T08:25），保留紧跟冒号的检验值（如 血钾：6.7、pH:7.18、pCO2:71）。"""

    if "." in token:
        return False
    if start >= 2 and text[start - 1] in ":：" and text[start - 2].isdigit():
        digit_start = start - 2
        while digit_start > 0 and text[digit_start - 1].isdigit():
            digit_start -= 1
        is_lab_code_prefix = (
            digit_start > 0
            and text[digit_start - 1].isascii()
            and text[digit_start - 1].isalpha()
            and not (
                text[digit_start - 1] in "Tt"
                and digit_start >= 2
                and text[digit_start - 2].isdigit()
            )
        )
        if not is_lab_code_prefix:
            return True
    if end + 1 < len(text) and text[end] in ":：" and text[end + 1].isdigit():
        return True
    return False


def _text_mentions_critical_result_value(
    text: str,
    lower_text: str,
    tokens: Sequence[str],
    keywords: Sequence[str],
) -> bool:
    lower_keywords = frozenset(kw.lower() for kw in keywords if kw)
    target_patterns: list[re.Pattern[str]] = []
    other_patterns: list[re.Pattern[str]] = []
    for group, patterns in _CRITICAL_VALUE_COMPILED_LAB_LABEL_GROUPS:
        if _lab_label_group_matches_keywords(group, lower_keywords):
            target_patterns.extend(patterns)
        else:
            other_patterns.extend(patterns)
    # 补充未纳入标准分组的罕见项目关键词（排除“补钾/降钾”等动作词）。
    action_only = frozenset({"补钾", "降钾", "纠酸", "贫血", "凝血", "酸中毒", "碱中毒", "低氧"})
    covered_aliases = {
        alias
        for group, _patterns in _CRITICAL_VALUE_COMPILED_LAB_LABEL_GROUPS
        if _lab_label_group_matches_keywords(group, lower_keywords)
        for alias in group
    }
    for kw in lower_keywords:
        if kw in action_only or kw in covered_aliases or len(kw) < 2:
            continue
        target_patterns.append(_compile_lab_label_pattern(kw))

    for token in tokens:
        pattern = re.compile(rf"(?<![\d.]){re.escape(token)}(?![\d.])")
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            # 排除时钟（如 08:25）与日期字段及药品剂量/时长单位（如 2.5g / 15ml / 2.5小时），
            # 但保留紧跟冒号的检验值（如 血钾：6.7 mmol/L、pH:7.18）。
            if _is_clock_colon_token(text, start, end, token):
                continue
            if (
                start > 0
                and end < len(text)
                and text[start - 1] in "-/"
                and text[end] in "-/"
            ):
                continue
            following = lower_text[end: min(len(lower_text), end + 12)]
            if _CRITICAL_VALUE_NON_LAB_UNIT_PATTERN.match(following):
                continue

            # 取同一句内紧邻该数值之前的局部窗口，核验最近的项目标签归属，
            # 防止“血钾 2.8，已补钾，血糖 2.5 mmol/L”把血糖的 2.5 误计入另一份血钾 2.5 报告。
            window_start = max(0, start - 60)
            preceding_raw = lower_text[window_start:start]
            last_sent_end = -1
            for boundary in _CRITICAL_VALUE_SENTENCE_SPLIT_PATTERN.finditer(preceding_raw):
                last_sent_end = boundary.end()
            if last_sent_end >= 0:
                window_start += last_sent_end
            preceding = lower_text[window_start:start]

            last_target_end = -1
            for pat in target_patterns:
                for hit in pat.finditer(preceding):
                    if hit.end() > last_target_end:
                        last_target_end = hit.end()

            last_other_end = -1
            for pat in other_patterns:
                for hit in pat.finditer(preceding):
                    if hit.end() > last_other_end:
                        last_other_end = hit.end()

            # 若紧邻该数值之前最近的项目标签属于其他检验/体征项目，则该数值不属于目标项目。
            if last_other_end > last_target_end:
                continue

            # 含小数点或两位数以上的数值边界匹配可靠；个位数需邻近项目关键词或检验单位。
            if "." in token or len(token) >= 2:
                return True
            window = lower_text[max(window_start, start - 28): min(len(lower_text), end + 20)]
            if (
                last_target_end >= 0
                or _text_mentions_critical_keyword(window, keywords)
                or re.search(r"(?:×|x|\*)\s*10|10\^|mmol|g/l|u/l|mmhg|kpa|/l", window)
            ):
                return True
    return False


def _normalize_critical_value_number_text(text: str) -> str:
    """合并 PDF 折行导致的数值小数点后断行空格（如 '18.\\n00mmHg' -> '18.00mmHg'）。"""

    return re.sub(r"(?<=\d\.)\s+(?=\d)", "", text)


def _has_affirmative_critical_value_handling(body: str) -> bool:
    """逐分句判定病程正文是否包含明确的已执行危急值临床处置/评估动作。

    - 排除未处理/待处理/尚未执行分句（如“尚未处理”“尚未执行”“等待医师”），但不让前句既往未处理
      否定后句明确已执行处置（如“当时尚未处理；10:20 已静脉补钾”）；
    - 排除同分句否定处置（如“未予补钾”“拒绝输血”）、计划/意向性表述（如“拟复查”“计划降钾”“准备复查”）
      与条件/假设性计划（如“若再次下降再予补钾”“必要时复查”）；
    - 同句中若后文明确声明“尚未执行/未执行/未实施/未落实”（且其后无同句已执行重置），
      否决前文缺乏已完成标志或紧邻该声明的待执行匹配。
    """

    cleaned = _CRITICAL_VALUE_PDF_LINE_WRAP_PATTERN.sub(
        "",
        _CRITICAL_VALUE_TITLE_STRIP_PATTERN.sub(" ", body),
    )
    for sentence in _CRITICAL_VALUE_SENTENCE_SPLIT_PATTERN.split(cleaned):
        sentence_text = sentence.strip()
        if not sentence_text:
            continue
        conditional_open = False
        sent_has_affirmative = False
        sent_has_completed_affirmative = False
        prev_clause_was_planned = False
        for clause in _CRITICAL_VALUE_CLAUSE_SPLIT_PATTERN.split(sentence_text):
            clause_text = clause.strip()
            if not clause_text:
                continue
            if _CRITICAL_VALUE_UNHANDLED_PATTERN.search(clause_text):
                conditional_open = False
                if _CRITICAL_VALUE_UNEXECUTED_DECLARATION_PATTERN.search(clause_text):
                    if not (sent_has_completed_affirmative and prev_clause_was_planned):
                        sent_has_affirmative = False
                        sent_has_completed_affirmative = False
                prev_clause_was_planned = False
                continue
            if conditional_open:
                if _CRITICAL_VALUE_CLAUSE_EXECUTED_RESET_PATTERN.search(clause_text):
                    conditional_open = False
                else:
                    # 承接前分句条件（如“若再次下降，再予补钾”），不作为已执行处置。
                    if not _CRITICAL_VALUE_CLAUSE_CONDITIONAL_OPENER_PATTERN.search(clause_text):
                        conditional_open = False
                    prev_clause_was_planned = False
                    continue
            clause_is_conditional_opener = bool(
                _CRITICAL_VALUE_CLAUSE_CONDITIONAL_OPENER_PATTERN.search(clause_text)
            )
            matched_affirmative = False
            matched_completed = False
            matched_planned = False
            for match in _CRITICAL_VALUE_HANDLING_ACTION_PATTERN.finditer(clause_text):
                prefix = clause_text[: match.start()]
                if _CRITICAL_VALUE_CLAUSE_CONDITIONAL_PREFIX_PATTERN.search(prefix):
                    continue
                completed = tuple(_CRITICAL_VALUE_CLAUSE_COMPLETED_PATTERN.finditer(prefix))
                planned = tuple(_CRITICAL_VALUE_CLAUSE_PLANNED_PREFIX_PATTERN.finditer(prefix))
                if planned and (not completed or planned[-1].start() > completed[-1].start()):
                    matched_planned = True
                    continue
                negations = tuple(_CRITICAL_VALUE_CLAUSE_NEGATION_PATTERN.finditer(prefix))
                if negations and (not completed or negations[-1].start() > completed[-1].start()):
                    continue
                matched_affirmative = True
                matched_completed = bool(
                    completed or _CRITICAL_VALUE_CLAUSE_EXECUTED_RESET_PATTERN.search(clause_text)
                )
                break
            if matched_affirmative:
                sent_has_affirmative = True
                if matched_completed:
                    sent_has_completed_affirmative = True
                prev_clause_was_planned = False
            else:
                prev_clause_was_planned = matched_planned
                if clause_is_conditional_opener:
                    conditional_open = True
        if sent_has_affirmative:
            return True
    return False


def _critical_value_action_keywords_for_item_keywords(
    keywords: Sequence[str],
) -> tuple[str, ...]:
    lower_keywords = tuple(kw.lower() for kw in keywords if kw)
    action_keywords: list[str] = []
    for triggers, actions in _CRITICAL_VALUE_ITEM_ACTION_KEYWORDS:
        if any(
            trigger in kw or kw in trigger
            for trigger in triggers
            for kw in lower_keywords
            if len(kw) >= 2 or kw == "钾" or kw == "钠" or kw == "钙"
        ):
            action_keywords.extend(actions)
    return tuple(dict.fromkeys(action_keywords))


def _has_affirmative_handling_for_critical_event(
    body: str,
    lower_body: str,
    keywords: Sequence[str],
    tokens: Sequence[str],
    is_crisis_doc: bool,
    single_event: bool,
    title: str,
    *,
    event_specs: Sequence[tuple[Sequence[str], Sequence[str]]] | None = None,
    generic_single_crisis_title: bool | None = None,
) -> bool:
    """按目标危急值事件绑定逐句核验已执行临床处置，防止无关诊疗（如另因发热退热）误替未处置危急值。"""

    specs: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
        tuple((tuple(kws), tuple(toks)) for kws, toks in event_specs)
        if event_specs is not None
        else ((tuple(keywords), tuple(tokens)),)
    )
    all_keywords = tuple(dict.fromkeys(kw for kws, _ in specs for kw in kws if kw))
    lower_keywords = frozenset(kw.lower() for kw in all_keywords)
    all_action_keywords = _critical_value_action_keywords_for_item_keywords(all_keywords)

    other_lab_patterns: list[re.Pattern[str]] = []
    for group, patterns in _CRITICAL_VALUE_COMPILED_LAB_LABEL_GROUPS:
        if not _lab_label_group_matches_keywords(group, lower_keywords):
            other_lab_patterns.extend(patterns)

    allow_generic_title = (
        generic_single_crisis_title
        if generic_single_crisis_title is not None
        else (
            is_crisis_doc
            and single_event
            and bool(_CRITICAL_VALUE_TITLE_PATTERN.search(title))
            and "血培养" not in body
        )
    )

    def _mentions_item(text_chunk: str, lower_chunk: str) -> bool:
        return any(
            _text_mentions_critical_keyword(lower_chunk, kws)
            for kws, _ in specs
            if kws
        ) or any(
            _text_mentions_critical_result_value(text_chunk, lower_chunk, toks, kws)
            for kws, toks in specs
            if toks
        )

    cleaned = _CRITICAL_VALUE_PDF_LINE_WRAP_PATTERN.sub(
        "",
        _CRITICAL_VALUE_TITLE_STRIP_PATTERN.sub(" ", body),
    )
    active_target_topic = False
    active_target_negated = False
    any_target_negated = False
    generic_candidate_found = False

    for sentence in _CRITICAL_VALUE_SENTENCE_SPLIT_PATTERN.split(cleaned):
        sentence_text = sentence.strip()
        if not sentence_text:
            continue
        sent_lower = sentence_text.lower()
        sent_mentions_item = _mentions_item(sentence_text, sent_lower)
        sent_mentions_action_kw = (
            _text_mentions_critical_keyword(sent_lower, all_action_keywords)
            if all_action_keywords
            else False
        )
        sent_unrelated_topic = bool(_CRITICAL_VALUE_UNRELATED_TOPIC_PATTERN.search(sentence_text))
        sent_other_lab = any(pat.search(sent_lower) for pat in other_lab_patterns)
        sent_topic_continuation = bool(_CRITICAL_VALUE_TOPIC_CONTINUATION_PATTERN.search(sentence_text))

        conditional_open = False
        sent_had_unhandled_or_negated = False
        sent_had_planned = False
        sent_has_valid_affirmative = False
        sent_has_item_or_action_affirmative = False
        sent_has_completed_affirmative = False
        sent_has_executed_reset = False
        prev_clause_was_planned = False

        for clause in _CRITICAL_VALUE_CLAUSE_SPLIT_PATTERN.split(sentence_text):
            clause_text = clause.strip()
            if not clause_text:
                continue
            if _CRITICAL_VALUE_UNHANDLED_PATTERN.search(clause_text):
                conditional_open = False
                sent_had_unhandled_or_negated = True
                if _CRITICAL_VALUE_UNEXECUTED_DECLARATION_PATTERN.search(clause_text):
                    if not (sent_has_completed_affirmative and prev_clause_was_planned):
                        sent_has_valid_affirmative = False
                        sent_has_item_or_action_affirmative = False
                        sent_has_completed_affirmative = False
                        sent_has_executed_reset = False
                prev_clause_was_planned = False
                continue
            if conditional_open:
                if _CRITICAL_VALUE_CLAUSE_EXECUTED_RESET_PATTERN.search(clause_text):
                    conditional_open = False
                else:
                    if not _CRITICAL_VALUE_CLAUSE_CONDITIONAL_OPENER_PATTERN.search(clause_text):
                        conditional_open = False
                    prev_clause_was_planned = False
                    continue

            clause_is_conditional_opener = bool(
                _CRITICAL_VALUE_CLAUSE_CONDITIONAL_OPENER_PATTERN.search(clause_text)
            )
            clause_lower = clause_text.lower()
            clause_mentions_item = _mentions_item(clause_text, clause_lower)
            clause_mentions_action_kw = (
                _text_mentions_critical_keyword(clause_lower, all_action_keywords)
                if all_action_keywords
                else False
            )
            clause_unrelated = bool(_CRITICAL_VALUE_UNRELATED_TOPIC_PATTERN.search(clause_text))
            clause_other_lab = any(pat.search(clause_lower) for pat in other_lab_patterns)
            clause_executed_reset = bool(
                _CRITICAL_VALUE_CLAUSE_EXECUTED_RESET_PATTERN.search(clause_text)
            )

            clause_negated_action = False
            clause_planned_action = False
            clause_matched_affirmative = False
            clause_matched_completed = False
            for match in _CRITICAL_VALUE_HANDLING_ACTION_PATTERN.finditer(clause_text):
                prefix = clause_text[: match.start()]
                if _CRITICAL_VALUE_CLAUSE_CONDITIONAL_PREFIX_PATTERN.search(prefix):
                    continue
                completed = tuple(_CRITICAL_VALUE_CLAUSE_COMPLETED_PATTERN.finditer(prefix))
                planned = tuple(_CRITICAL_VALUE_CLAUSE_PLANNED_PREFIX_PATTERN.finditer(prefix))
                if planned and (not completed or planned[-1].start() > completed[-1].start()):
                    clause_planned_action = True
                    continue
                negations = tuple(_CRITICAL_VALUE_CLAUSE_NEGATION_PATTERN.finditer(prefix))
                if negations and (not completed or negations[-1].start() > completed[-1].start()):
                    clause_negated_action = True
                    continue
                clause_matched_affirmative = True
                clause_matched_completed = bool(completed or clause_executed_reset)
                break

            if clause_negated_action and not clause_matched_affirmative:
                sent_had_unhandled_or_negated = True
            if clause_planned_action and not clause_matched_affirmative:
                sent_had_planned = True

            if clause_matched_affirmative:
                # 若本分句切换至无关临床主题（如“另因发热予以退热治疗”）且未提及目标项目，严禁计数。
                if clause_unrelated and not clause_mentions_item:
                    prev_clause_was_planned = False
                    continue
                # 若本分句提及其他检验/体征且未提及目标项目或其专属处置，仅在同句未提及目标项目时跳过。
                if clause_other_lab and not (clause_mentions_item or clause_mentions_action_kw) and not sent_mentions_item:
                    prev_clause_was_planned = False
                    continue
                # 同句前文已显式否定/未处理目标项目时，仅允许目标项目/专属处置动作或明确时间/现已重置覆盖。
                if sent_had_unhandled_or_negated and not (
                    clause_mentions_item or clause_mentions_action_kw or clause_executed_reset
                ):
                    prev_clause_was_planned = False
                    continue
                sent_has_valid_affirmative = True
                if clause_mentions_item or clause_mentions_action_kw:
                    sent_has_item_or_action_affirmative = True
                if clause_matched_completed:
                    sent_has_completed_affirmative = True
                if clause_executed_reset:
                    sent_has_executed_reset = True
                prev_clause_was_planned = False
            else:
                prev_clause_was_planned = clause_planned_action
                if clause_is_conditional_opener:
                    conditional_open = True

        if sent_has_valid_affirmative:
            # (i) 本句自身提及目标项目或目标项目专属处置（且至少有一条专属分句未切至无关主题，如 ICU“镇静镇痛，继续呼吸机辅助通气”）
            if sent_has_item_or_action_affirmative or (
                (sent_mentions_item or sent_mentions_action_kw)
                and not (sent_unrelated_topic and not sent_mentions_item)
            ):
                return True
            # (ii) 处于目标项目活跃话题下的承接句：本句不得切换至无关主题或其他检验项目；
            #      若前序话题已被标记未处理/否定，须有明确的已执行重置（如“15:28 已针对本次完成…”、“现已…”、“随后已…”）。
            if (
                active_target_topic
                and not sent_unrelated_topic
                and not sent_other_lab
                and (not active_target_negated or sent_has_executed_reset)
            ):
                return True
            # (iii) 单事件专用《危急值处理记录》标题兜底：本句不得切换无关主题/他项检验，且全篇无目标否定
            if allow_generic_title and not sent_unrelated_topic and not sent_other_lab:
                generic_candidate_found = True

        if sent_mentions_item:
            active_target_topic = True
            active_target_negated = bool(sent_had_unhandled_or_negated and not sent_has_valid_affirmative)
            if active_target_negated:
                any_target_negated = True
        elif sent_unrelated_topic or sent_other_lab:
            active_target_topic = False
            active_target_negated = False
            if sent_had_unhandled_or_negated and not sent_has_valid_affirmative:
                any_target_negated = True
        elif active_target_topic and (
            sent_had_unhandled_or_negated or sent_had_planned or sent_topic_continuation
        ):
            if sent_had_unhandled_or_negated and not sent_has_valid_affirmative:
                active_target_negated = True
                any_target_negated = True
        else:
            if sent_had_unhandled_or_negated and not sent_has_valid_affirmative:
                any_target_negated = True
            active_target_topic = False
            active_target_negated = False

    return bool(allow_generic_title and generic_candidate_found and not any_target_negated)


def _text_mentions_critical_report_clock(body: str, report_time: datetime) -> bool:
    report_minutes = report_time.hour * 60 + report_time.minute
    for hour_str, minute_str in _CRITICAL_VALUE_CLOCK_PATTERN.findall(body):
        hour, minute = int(hour_str), int(minute_str)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            diff = abs((hour * 60 + minute) - report_minutes)
            if diff <= 5 or diff >= 24 * 60 - 5:
                return True
    return False


def _course_critical_value_disposition_refs(
    *,
    lab_item_rows: Sequence[Mapping[str, Any]],
    course_ref_rows: Sequence[tuple[str, str, Mapping[str, Any]]],
) -> tuple[tuple[str, str, CriticalValueDisposition], ...]:
    """从日常病程与上级查房记录中识别危急值处置，并返回精确来源与文书引用。"""

    if not lab_item_rows or not course_ref_rows:
        return ()
    from ..extended_document_critical_value import _critical_display_flag, _is_critical_item

    grouped: dict[tuple[str | None, datetime], list[tuple[Mapping[str, Any], CriticalValueItem]]] = {}
    has_unkeyed = False
    for row in lab_item_rows:
        item = _critical_value_item_from_row(row)
        if not _is_critical_item(item):
            continue
        if (
            item.report_time is None
            or item.report_time_error is not None
            or _critical_display_flag(item) is None
        ):
            continue
        if item.event_key is None:
            has_unkeyed = True
        grouped.setdefault((item.event_key, item.report_time), []).append((row, item))
    if not grouped:
        return ()
    if has_unkeyed and len(grouped) > 1:
        # 多事件缺业务键时按既有合同不猜测跨事件关联。
        return ()
    # 同一业务键对应多个不同报告时间属于冲突，不生成伪关联。
    times_by_key: dict[str, set[datetime]] = {}
    for event_key, report_time in grouped:
        if event_key is not None:
            times_by_key.setdefault(event_key, set()).add(report_time)
    conflicting_keys = {key for key, times in times_by_key.items() if len(times) > 1}

    single_event = len(grouped) == 1
    parsed_courses: list[tuple[str, str, datetime, str, str, str, bool]] = []
    for source_key, reference, row in course_ref_rows:
        disposition_time = _row_time(row)
        if disposition_time is None:
            continue
        title = _clean(row.get("document_title"))
        body = _material_text(row)
        if not body:
            continue
        # 无论是否专用《危急值处理记录》，均须排除“尚未处理/未处理/等待医师”等未处置表述并要求明确临床处置动作。
        if not _has_affirmative_critical_value_handling(body):
            continue
        is_crisis_doc = bool(
            _CRITICAL_VALUE_TITLE_PATTERN.search(title)
            or _CRITICAL_VALUE_TITLE_PATTERN.search(body)
        )
        normalized_body = _normalize_critical_value_number_text(body)
        parsed_courses.append(
            (source_key, reference, disposition_time, title, normalized_body, normalized_body.lower(), is_crisis_doc)
        )
    if not parsed_courses:
        return ()

    event_keywords: dict[tuple[str | None, datetime], frozenset[str]] = {}
    event_tokens: dict[tuple[str | None, datetime], frozenset[str]] = {}
    candidates_by_course: dict[
        int,
        list[tuple[tuple[str | None, datetime], str, str, datetime, float, float, bool, bool, bool]],
    ] = {}
    for (event_key, report_time), pairs in grouped.items():
        if event_key is not None and event_key in conflicting_keys:
            continue
        event_specs = tuple(
            (
                _critical_value_item_keywords(item.item_name),
                _critical_value_result_tokens(row),
            )
            for row, item in pairs
        )
        event_id = (event_key, report_time)
        event_keywords[event_id] = frozenset(kw for keywords, _tokens in event_specs for kw in keywords)
        event_tokens[event_id] = frozenset(tok for _keywords, tokens in event_specs for tok in tokens)
        for course_index, (
            source_key,
            reference,
            disposition_time,
            title,
            body,
            lower_body,
            is_crisis_doc,
        ) in enumerate(parsed_courses):
            delta_seconds = effective_disposition_elapsed_seconds(disposition_time, report_time)
            if delta_seconds is None:
                continue
            delta_hours = delta_seconds / 3600.0
            item_hit = any(
                _text_mentions_critical_keyword(lower_body, keywords)
                for keywords, _tokens in event_specs
                if keywords
            )
            value_hit = any(
                _text_mentions_critical_result_value(body, lower_body, tokens, keywords)
                for keywords, tokens in event_specs
                if tokens
            )
            if is_crisis_doc:
                # 专用《危急值处理记录/危急值记录》放宽至报告后24h以便 06-04-01 准确判超时、06-04-02 判已处置；
                # 必须匹配项目关键词（或单事件6h内专用危急值标题且非血培养等无关项目）。
                if delta_hours > 24.0:
                    continue
                generic_single_crisis_title = (
                    single_event
                    and delta_hours <= 6.0
                    and bool(_CRITICAL_VALUE_TITLE_PATTERN.search(title))
                    and "血培养" not in body
                )
                if not (item_hit or generic_single_crisis_title):
                    continue
            else:
                generic_single_crisis_title = False
                # 普通日常病程/上级查房严格限定 6h 内，且必须同时命中项目关键词 + 实测危急值 + 明确临床处置动作。
                if delta_hours > 6.0:
                    continue
                if not (item_hit and value_hit):
                    continue
            # 按目标危急值事件绑定逐句核验已执行处置，防止“未予补钾。另因发热予以退热治疗”借无关治疗过关。
            if not _has_affirmative_handling_for_critical_event(
                body,
                lower_body,
                tuple(event_keywords[event_id]),
                tuple(event_tokens[event_id]),
                is_crisis_doc,
                single_event,
                title,
                event_specs=event_specs,
                generic_single_crisis_title=generic_single_crisis_title,
            ):
                continue
            clock_hit = _text_mentions_critical_report_clock(body, report_time)
            candidates_by_course.setdefault(course_index, []).append(
                (event_id, source_key, reference, disposition_time, delta_seconds, delta_hours, is_crisis_doc, value_hit, clock_hit)
            )

    matched_refs: list[tuple[str, str, CriticalValueDisposition]] = []
    seen: set[tuple[str | None, datetime, str]] = set()
    for cands in candidates_by_course.values():
        # 若该病程记录已精确命中某事件的实测数值（value_hit=True），不得再串配给未命中数值的其他事件。
        if any(cand[7] for cand in cands):
            cands = [cand for cand in cands if cand[7]]
        # 若该专用危急值记录已精准归属某后续危急值事件的 6h 窗内，且未提及早先事件的具体数值，
        # 不得跨事件借用为早先事件的“超时处置”。
        if any(cand[5] <= 6.0 for cand in cands):
            cands = [cand for cand in cands if cand[5] <= 6.0 or cand[7]]
        # 同一病程若仍命中多个同项目危急值事件，仅当两事件实测值互不相交且均命中数值时允许同记；
        # 否则（均未写数值或同数值重复报告）按报告时刻精确归属，无时刻则仅归属最近一次报告，严禁一条病程双计两事件。
        kept: list[tuple[tuple[str | None, datetime], str, str, datetime, float, float, bool, bool, bool]] = []
        used = [False] * len(cands)
        for index in range(len(cands)):
            if used[index]:
                continue
            group = [cands[index]]
            used[index] = True
            changed = True
            while changed:
                changed = False
                for other_idx in range(len(cands)):
                    if used[other_idx]:
                        continue
                    other_ev = cands[other_idx][0]
                    other_val_hit = cands[other_idx][7]
                    conflicts_with_group = any(
                        bool(event_keywords[member[0]] & event_keywords[other_ev])
                        and not (
                            member[7]
                            and other_val_hit
                            and event_tokens[member[0]]
                            and event_tokens[other_ev]
                            and event_tokens[member[0]].isdisjoint(event_tokens[other_ev])
                        )
                        for member in group
                    )
                    if conflicts_with_group:
                        group.append(cands[other_idx])
                        used[other_idx] = True
                        changed = True
            if len(group) == 1:
                kept.append(group[0])
            else:
                clock_group = [member for member in group if member[8]]
                pool = clock_group if clock_group else group
                kept.append(min(pool, key=lambda member: member[4]))
        for event_id, source_key, reference, disposition_time, *_ in kept:
            event_key, _report_time = event_id
            dedupe_key = (event_key, disposition_time, reference)
            if dedupe_key not in seen:
                seen.add(dedupe_key)
                matched_refs.append(
                    (
                        source_key,
                        reference,
                        CriticalValueDisposition(
                            disposition_time=disposition_time,
                            event_key=event_key,
                        ),
                    )
                )
    return tuple(matched_refs)


def _course_critical_value_dispositions(
    *,
    lab_item_rows: Sequence[Mapping[str, Any]],
    course_rows: Sequence[Mapping[str, Any]],
) -> tuple[CriticalValueDisposition, ...]:
    """从日常病程与上级查房记录中识别危急值处置，补足空 crisis_value_record 场景。"""

    matched = _course_critical_value_disposition_refs(
        lab_item_rows=lab_item_rows,
        course_ref_rows=tuple(("", "", row) for row in course_rows),
    )
    dispositions: list[CriticalValueDisposition] = []
    seen: set[tuple[str | None, datetime | None]] = set()
    for _source_key, _reference, disposition in matched:
        dedupe_key = (disposition.event_key, disposition.disposition_time)
        if dedupe_key not in seen:
            seen.add(dedupe_key)
            dispositions.append(disposition)
    return tuple(dispositions)


def _critical_value_document_refs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    outcome: CriticalValueOutcome,
    course_disposition_refs: Sequence[tuple[str, CriticalValueDisposition]] = (),
) -> tuple[str, ...]:
    """返回危急值判定实际消费的逐行证据；评价终点不属于客户文书证据。"""

    def rows(source_key: str) -> tuple[tuple[str, Mapping[str, Any]], ...]:
        try:
            return tuple(
                (reference, dict(row))
                for reference, row in materials.document_rows(
                    source_key, snapshot=snapshot
                )
            )
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
            return ()

    item_rows = rows("labtest_item_report")
    disposition_rows = rows("crisis_value_record")
    master_rows = rows("labtest_master")
    daily_course_rows = rows("daily_course_record")
    senior_course_rows = rows("senior_course_record")
    selected_refs = select_critical_value_fact_refs(
        outcome=outcome,
        item_refs=tuple(
            (reference, _critical_value_item_from_row(row))
            for reference, row in item_rows
        ),
        disposition_refs=(
            *tuple(
                (reference, disposition)
                for reference, row in disposition_rows
                for disposition in (_critical_value_disposition_from_row(row),)
                if disposition is not None
            ),
            *tuple(
                (reference, disposition)
                for reference, disposition in course_disposition_refs
                if reference
            ),
        ),
        master_refs=tuple(reference for reference, _row in master_rows),
    )
    # RuleDecision 的逐条引用上限为 128。大量检验的完整否定证据不能
    # 截断为前 128 行；改用已有来源快照绑定完整材料，不改变任何判定。
    if len(selected_refs) > 128:
        selected = frozenset(selected_refs)
        return _fact_refs(snapshot, tuple(
            source_key
            for source_key, source_rows in (
                ("labtest_item_report", item_rows),
                ("crisis_value_record", disposition_rows),
                ("labtest_master", master_rows),
                ("daily_course_record", daily_course_rows),
                ("senior_course_record", senior_course_rows),
            )
            if any(reference in selected for reference, _row in source_rows)
        ))
    return selected_refs


def execute_critical_value_family(
    *,
    rule_ids: Sequence[str],
    evidence_snapshot: Luxian0609EvidenceSnapshot,
    evidence_materials: Luxian0609EvidenceMaterialStore,
    horizon_rows: Sequence[Mapping[str, Any]],
    horizon_error: str,
    source_cache: SourceRowsCache | None = None,
) -> ExtendedDocumentFamilyOutcome:
    """执行 LX0609 危急值规则族（06-04-01 时效性 / 06-04-02 处置记录完整性）。"""

    selected = tuple(
        rule_id for rule_id in rule_ids if rule_id in CRITICAL_VALUE_RULE_IDS
    )
    if not selected:
        return ExtendedDocumentFamilyOutcome(decisions=(), display_facts=())

    (
        critical_horizon_date,
        critical_horizon_datetime,
        critical_horizon_error,
    ) = (
        resolve_evaluation_horizon(horizon_rows, horizon_error)
        if "LX0609-06-04-01" in selected
        else (None, None, None)
    )

    crisis_rows, crisis_error = _source_rows(
        evidence_materials, "crisis_value_record", cache=source_cache
    )
    lab_item_rows, lab_item_error = _source_rows(
        evidence_materials, "labtest_item_report", cache=source_cache
    )
    lab_master_rows, lab_master_error = _source_rows(
        evidence_materials, "labtest_master", cache=source_cache
    )

    crisis_dispositions = tuple(
        disposition
        for row in crisis_rows
        for disposition in (_critical_value_disposition_from_row(row),)
        if disposition is not None
    )
    course_crisis_ref_rows: list[tuple[str, str, Mapping[str, Any]]] = []
    for course_source_key in ("daily_course_record", "senior_course_record"):
        try:
            course_crisis_ref_rows.extend(
                (course_source_key, reference, dict(row))
                for reference, row in evidence_materials.document_rows(
                    course_source_key, snapshot=evidence_snapshot
                )
            )
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
            continue
    course_crisis_matches = _course_critical_value_disposition_refs(
        lab_item_rows=lab_item_rows,
        course_ref_rows=course_crisis_ref_rows,
    )
    course_crisis_dispositions = tuple(
        dict.fromkeys(
            disposition
            for _source_key, _reference, disposition in course_crisis_matches
        )
    )
    course_crisis_disposition_refs = tuple(
        (reference, disposition)
        for _source_key, reference, disposition in course_crisis_matches
        if reference
    )

    critical_value_outcomes = {
        item.rule_id: item
        for item in evaluate_critical_value_rules(
            rule_ids=tuple(
                rule_id for rule_id in CRITICAL_VALUE_RULE_IDS if rule_id in selected
            ),
            inputs=CriticalValueInput(
                lab_item_error=lab_item_error or None,
                crisis_error=crisis_error or None,
                lab_report_count=len(lab_master_rows),
                lab_detail_count=len(lab_item_rows),
                items=tuple(
                    _critical_value_item_from_row(row) for row in lab_item_rows
                ),
                dispositions=(*crisis_dispositions, *course_crisis_dispositions),
                evaluation_horizon_date=critical_horizon_date,
                evaluation_horizon_datetime=critical_horizon_datetime,
                evaluation_horizon_error=critical_horizon_error,
            ),
        )
    }

    decisions = []
    display: list[tuple[str, Mapping[str, Any]]] = []
    for rule_id in selected:
        outcome = critical_value_outcomes[rule_id]
        blocked_pending_window = (
            outcome.reason_code == "evaluation_window_not_mature"
            and bool(lab_master_error)
        )
        if blocked_pending_window:
            outcome = replace(
                outcome,
                final_state="data_gap",
                reason_code=lab_master_error,
                display_facts=None,
            )
        if outcome.display_facts is not None:
            display.append((rule_id, outcome.display_facts))
        document_refs = _critical_value_document_refs(
            snapshot=evidence_snapshot,
            materials=evidence_materials,
            outcome=outcome,
            course_disposition_refs=course_crisis_disposition_refs,
        )
        horizon_refs = (
            _fact_refs(evidence_snapshot, ("evaluation_context.horizon",))
            if outcome.reason_code == "evaluation_window_not_mature"
            and document_refs
            and set(document_refs).issubset(evidence_snapshot.document_refs)
            and len(document_refs) < 128
            else ()
        )
        decisions.append(
            _decision(
                rule_id=rule_id,
                snapshot=evidence_snapshot,
                # 完整资料已读取但确无任何检验明细时，不适用结论仍需一个
                # snapshot 级负向证据；它不会被投影为客户文书。
                source_keys=(
                    ("labtest_master",)
                    if blocked_pending_window
                    else ("labtest_item_report",)
                    if not document_refs and outcome.final_state == "not_applicable"
                    else ()
                ),
                document_refs=(*document_refs, *horizon_refs),
                final_state=outcome.final_state,
                reason_code=outcome.reason_code,
                affirmative_applicability=bool(horizon_refs),
            )
        )

    return ExtendedDocumentFamilyOutcome(
        decisions=tuple(decisions),
        display_facts=tuple(display),
    )
