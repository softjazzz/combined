#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_XLS = REPO_ROOT / "docs" / "运行病历质控记录.xls"
OUTPUT_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
OUTPUT_CSV = OUTPUT_DIR / "sheet2_rule_mapping_seed.csv"
OUTPUT_JSON = OUTPUT_DIR / "sheet2_rule_mapping_seed.summary.json"


@dataclass(frozen=True)
class MappingPattern:
    family: str
    keywords_any: tuple[str, ...]
    candidate_rule_ids: tuple[str, ...]
    mapping_type: str
    execution_type: str
    current_status: str
    notes: str
    keywords_all: tuple[str, ...] = ()
    keywords_none: tuple[str, ...] = ()

    def matches(self, issue_text: str) -> bool:
        if self.keywords_all and not all(keyword in issue_text for keyword in self.keywords_all):
            return False
        if self.keywords_any and not any(keyword in issue_text for keyword in self.keywords_any):
            return False
        if self.keywords_none and any(keyword in issue_text for keyword in self.keywords_none):
            return False
        return True


PATTERNS: tuple[MappingPattern, ...] = (
    MappingPattern(
        family="首次病程记录存在/时效",
        keywords_any=("首次病程记录", "入院8小时内未完成首次病程记录"),
        candidate_rule_ids=("SC-021", "SC-022"),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="implemented",
        notes="已在 sample_programmatic_gate_v1 中实现。",
    ),
    MappingPattern(
        family="非危重三天无病程",
        keywords_any=("非危重症患者三天未完成一次病程",),
        candidate_rule_ids=("LXE-18",),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="implemented",
        notes="已在 sample_programmatic_gate_v1 中实现。",
    ),
    MappingPattern(
        family="主治首次查房48小时",
        keywords_any=("48小时无主治医师查房记录", "入院48小时内，无主治医师查房记录", "入院48小时无主治医师查房记录"),
        candidate_rule_ids=("SC-048",),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="implemented",
        notes="已按主治医师严格口径实现。",
    ),
    MappingPattern(
        family="高级医师首次查房72小时",
        keywords_any=("72小时无高级职称医师查房记录", "入院72小时以内无副主任医师", "入院72小时以内未查见副主任医师查房记录", "72小时无高级职称医师", "入院72小时无高级职称医师查房记录"),
        candidate_rule_ids=("SC-049",),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="implemented",
        notes="当前只按副主任医师/主任医师口径判定。",
    ),
    MappingPattern(
        family="上级查房内容空洞/复制粘贴/身份异常",
        keywords_any=("查房记录无内容", "查房记录内容空洞", "复制粘贴严重", "复制粘贴", "涉嫌伪造病历", "内容却是", "三级医师查房执行不到位", "三级查房落实不到位"),
        candidate_rule_ids=("SC-049", "SC-051", "SC-052"),
        mapping_type="extend_existing",
        execution_type="semantic",
        current_status="todo_semantic",
        notes="规则库已有查房规则，但需补语义评估：内容完整性、身份一致性、复制粘贴/代写异常。",
    ),
    MappingPattern(
        family="会诊记录缺失/申请记录缺失",
        keywords_any=("无会诊记录", "会诊记录无记录", "会诊病人无会诊记录", "无麻醉科会诊记录"),
        candidate_rule_ids=("SC-067", "SC-068", "SC-069"),
        mapping_type="direct_match",
        execution_type="hybrid",
        current_status="partial",
        notes="SC-067 已可程序判定；SC-068/069 需补内容质量语义检查。",
    ),
    MappingPattern(
        family="会诊记录内容质量/复制粘贴/结论不足",
        keywords_any=("会诊记录中存在大量复制其他科室会诊意见", "会诊意见：患者未在病房", "无综合会诊结果提出建设性诊疗意见", "会诊记录意见为"),
        candidate_rule_ids=("SC-069",),
        mapping_type="extend_existing",
        execution_type="semantic",
        current_status="todo_semantic",
        notes="现有会诊记录质量规则可承接，但需补会诊意见质量、综合建议充分性语义判断。",
    ),
    MappingPattern(
        family="会诊记录时效",
        keywords_any=("会诊申请", "会诊接收时间", "24小时内完成"),
        keywords_all=("会诊",),
        candidate_rule_ids=("SC-071", "SC-072"),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="partial",
        notes="常规会诊 24h 已实现；急会诊 10 分钟到场/即刻记录尚未补齐。",
    ),
    MappingPattern(
        family="会诊执行记录缺失/未写执行情况",
        keywords_any=("无会诊执行记录", "无请会诊执行记录", "请会诊执行记录未", "会诊执行记录未记录具体执行情况", "请会诊执行记录不能体现", "请会诊执行记录为书写具体执行情况", "无会诊意见执行记录"),
        candidate_rule_ids=("SC-070", "LX-016"),
        mapping_type="extend_existing",
        execution_type="semantic",
        current_status="todo_semantic",
        notes="规则库已有闭环规则，但当前样本链路未实现会诊执行语义判定。",
    ),
    MappingPattern(
        family="会诊意见已写遵执但实际未落实",
        keywords_any=("遵会诊意见", "遵执", "实际并未按照会诊意见执行", "实际未按会诊意见执行", "会诊7天后均未进行复查", "只予以了"),
        candidate_rule_ids=("SC-070", "LX-016"),
        mapping_type="new_rule",
        execution_type="semantic",
        current_status="new_rule_needed",
        notes="现有 SC-070 偏记录闭环，需新增或扩展“记录与实际医嘱/治疗不一致”的语义规则。",
    ),
    MappingPattern(
        family="病程记录病情变化记录不全",
        keywords_any=("病情变化", "症状及体征", "无具体内容", "未描述患者情况", "仅一句话", "过于简略", "内容空洞", "记录不全"),
        keywords_none=("会诊", "术前", "手术", "输血", "危急值"),
        candidate_rule_ids=("SC-032",),
        mapping_type="direct_match",
        execution_type="semantic",
        current_status="ready_in_rule_library",
        notes="规则库已有，适合先纳入语义批次。",
    ),
    MappingPattern(
        family="病程记录缺分析/缺处理意见",
        keywords_any=("未分析", "未做分析", "无分析判断", "无处理意见", "未做处理", "未请相关科室会诊", "用药病程记录未体现"),
        keywords_none=("危急值", "会诊执行"),
        candidate_rule_ids=("SC-033", "SC-036"),
        mapping_type="direct_match",
        execution_type="semantic",
        current_status="ready_in_rule_library",
        notes="异常检查检验未分析、治疗方案未体现，可直接复用现有内涵规则。",
    ),
    MappingPattern(
        family="病程时效/缺失",
        keywords_any=("无病程记录", "无后续日常病程记录", "未及时书写日常病程记录", "病程记录未在规定时间内完成", "未及时书写病程记录", "后无病程", "无病程查房记录", "新建后未书写"),
        keywords_none=("术后", "主刀", "出院记录"),
        candidate_rule_ids=("LXE-18",),
        mapping_type="extend_existing",
        execution_type="hybrid",
        current_status="partial",
        notes="普通住院阶段可先用 LXE-18 覆盖长间隔；细粒度逐日时效需补更多程序规则。",
    ),
    MappingPattern(
        family="上级医师查房缺失/未及时书写",
        keywords_any=("无上级医生查房记录", "无上级医师查房记录", "出院前上级医师查房记录新建后未及时书写"),
        candidate_rule_ids=("SC-051", "SC-077"),
        mapping_type="extend_existing",
        execution_type="hybrid",
        current_status="todo_semantic",
        notes="存在性可程序化，出院同意及前一天/当天窗口仍需补语义和时间轴规则。",
    ),
    MappingPattern(
        family="危急值记录不完整/处理不充分",
        keywords_any=("危急值",),
        candidate_rule_ids=("SC-039",),
        mapping_type="direct_match",
        execution_type="semantic",
        current_status="ready_in_rule_library",
        notes="规则库已有危急值规则，当前样本模式尚未单独接入。",
    ),
    MappingPattern(
        family="术前小结缺失",
        keywords_any=("无术前小结", "未按要求书写术前小结记录"),
        candidate_rule_ids=("SC-080",),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="ready_in_rule_library",
        notes="规则库已有，建议补入硬门槛程序包第二批。",
    ),
    MappingPattern(
        family="术前小结缺项/不清",
        keywords_any=("术前小结缺项", "术前小结记录", "术前小结新建后未书写"),
        candidate_rule_ids=("SC-081",),
        mapping_type="direct_match",
        execution_type="semantic",
        current_status="ready_in_rule_library",
        notes="适合语义规则，重点看手术指征、拟行术式、麻醉方式、注意事项。",
    ),
    MappingPattern(
        family="术前讨论缺失/术者未参加",
        keywords_any=("缺术前讨论记录", "无术前讨论", "未进行术前讨论"),
        candidate_rule_ids=("SC-082",),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="implemented",
        notes="已在 sample_programmatic_gate_v1 中实现存在性。",
    ),
    MappingPattern(
        family="四级手术未 MDT",
        keywords_any=("多学科讨论", "MDT", "四级手术术前讨论未多学科讨论", "四级肿瘤手术"),
        candidate_rule_ids=("SC-083",),
        mapping_type="direct_match",
        execution_type="semantic",
        current_status="ready_in_rule_library",
        notes="规则库已有，需针对 MDT 文书/会诊记录补语义实现。",
    ),
    MappingPattern(
        family="术前讨论结论未入病历/缺项",
        keywords_any=("术前讨论结果未记入病历", "术前讨论的结论未记入病历", "术前讨论记录未明确", "讨论内容未书写明确"),
        candidate_rule_ids=("SC-084", "SC-085"),
        mapping_type="direct_match",
        execution_type="semantic",
        current_status="ready_in_rule_library",
        notes="现有规则可承接，需补面向术前讨论结论的语义检查。",
    ),
    MappingPattern(
        family="术前主刀医生查房/麻醉术前访视缺失",
        keywords_any=("无术前主刀医师查房记录", "术前主刀医生查房记录应在术前小结之前", "无术前一天内主刀医生查看病人的记录", "缺麻醉术前访视记录"),
        candidate_rule_ids=("SC-086", "LX-020"),
        mapping_type="direct_match",
        execution_type="hybrid",
        current_status="todo_programmatic",
        notes="规则库已有，需补手术前一天窗口与主刀身份识别。",
    ),
    MappingPattern(
        family="手术同意书/知情同意签署异常",
        keywords_any=("手术同意书", "知情同意书", "非授权受托人", "术中更改术式"),
        candidate_rule_ids=("SC-087", "SC-089", "SC-128", "LX-021"),
        mapping_type="direct_match",
        execution_type="semantic",
        current_status="ready_in_rule_library",
        notes="已有规则较多，需后续按签署主体、术式变更等再细分。",
    ),
    MappingPattern(
        family="手术记录缺失",
        keywords_any=("无手术记录",),
        candidate_rule_ids=("SC-095",),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="implemented",
        notes="已在 sample_programmatic_gate_v1 中实现。",
    ),
    MappingPattern(
        family="手术记录时效异常",
        keywords_any=("手术记录未在术后24小时内完成", "手术未在24小时内完成手术记录"),
        candidate_rule_ids=("SC-096",),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="implemented",
        notes="已在 sample_programmatic_gate_v1 中实现，并增加脏值保护。",
    ),
    MappingPattern(
        family="手术记录缺项/时间错误/逻辑不清/签名异常",
        keywords_any=("手术记录缺项", "手术记录手术结束时间错误", "手术记录无主刀医生签名", "手术记录非手术医生或第一助手书写且主刀医生未签名确认", "手术记录病历记录时间早于手术结束时间", "手术名称不一致", "术中情况描述"),
        candidate_rule_ids=("SC-097", "SC-098"),
        mapping_type="direct_match",
        execution_type="semantic",
        current_status="ready_in_rule_library",
        notes="已有规则可承接，适合纳入围术期语义批次。",
    ),
    MappingPattern(
        family="手术安全核查/风险评估缺失",
        keywords_any=("手术安全核查记录", "手术风险评估表"),
        candidate_rule_ids=("SC-102", "SC-103", "SC-111", "SC-112"),
        mapping_type="direct_match",
        execution_type="hybrid",
        current_status="ready_in_rule_library",
        notes="已有规则存在，需确认本地 CDM/文书字段承载情况。",
    ),
    MappingPattern(
        family="术后首次病程/麻醉术后访视缺失",
        keywords_any=("无术后首次病程记录", "缺术后首次病程记录", "无麻醉术后访视记录", "无术后首次病程记录或无麻醉术后访视记录"),
        candidate_rule_ids=("SC-104",),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="deferred_data_gap",
        notes="规则库和执行器都已有入口，但客户数据里麻醉相关字段仍偏瘦，之前刻意排除在 v1 外。",
    ),
    MappingPattern(
        family="术后首次病程记录缺项/不清",
        keywords_any=("术后首次病程记录缺项", "术后首次病程记录书写不规范", "术后首次病程记录中"),
        candidate_rule_ids=("SC-105",),
        mapping_type="direct_match",
        execution_type="semantic",
        current_status="ready_in_rule_library",
        notes="规则库已有，适合围术期语义批次。",
    ),
    MappingPattern(
        family="术后三天连续病程/查房缺失",
        keywords_any=("术后连续三天查房记录", "术后三天无连续病程记录", "术后连续3天", "术后查房记录"),
        candidate_rule_ids=("SC-107", "LXE-35"),
        mapping_type="extend_existing",
        execution_type="programmatic",
        current_status="partial",
        notes="LXE-35 已实现术后连续 3 天病程/查房；可进一步切换到 SC-107 口径。",
    ),
    MappingPattern(
        family="转科24小时内转入/转出记录",
        keywords_any=("24小时内未完成转入记录", "24小时内未完成转入、转出记录", "转科病人24小时"),
        candidate_rule_ids=("SC-064",),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="ready_in_rule_library",
        notes="规则库已有，需补转科记录时间轴证据。",
    ),
    MappingPattern(
        family="住院超30天阶段小结/讨论缺失",
        keywords_any=("住院超30天", "阶段小结", "超过30天讨论记录"),
        candidate_rule_ids=("SC-065",),
        mapping_type="direct_match",
        execution_type="programmatic",
        current_status="ready_in_rule_library",
        notes="规则库已有，适合程序化存在性校验。",
    ),
    MappingPattern(
        family="交接班记录缺失/缺项",
        keywords_any=("交接班记录", "交(接)班记录", "管床医生发生变更未书写交接班记录"),
        candidate_rule_ids=("SC-062", "SC-063"),
        mapping_type="direct_match",
        execution_type="semantic",
        current_status="ready_in_rule_library",
        notes="规则库已有，需补交接班文书抽取与语义检查。",
    ),
    MappingPattern(
        family="输血记录链缺失/不全",
        keywords_any=("无输血前评估", "无输血记录", "无输血后评估", "输血记录未", "输血患者缺少输血记录单", "未及时书写输血后评价记录"),
        candidate_rule_ids=("SC-073", "SC-074", "LX-018"),
        mapping_type="direct_match",
        execution_type="hybrid",
        current_status="ready_in_rule_library",
        notes="规则库已有，需把输血前评估、输血记录、输血后评价记录串起来。",
    ),
    MappingPattern(
        family="输血时间/量/前后记录不一致",
        keywords_any=("输血时间不一致", "输血日期及输血量有误", "输血时间记录错误", "早于输血时间", "未分别记录输血开始时间及结束时间"),
        candidate_rule_ids=("SC-074", "SC-146"),
        mapping_type="extend_existing",
        execution_type="hybrid",
        current_status="todo_programmatic",
        notes="已有规则可承接，但需新增输血时间一致性比对逻辑。",
    ),
    MappingPattern(
        family="出院前一天/当天上级医师查房或病程缺失",
        keywords_any=("出院前一天", "出院当天", "上级医师同意出院"),
        candidate_rule_ids=("SC-077",),
        mapping_type="direct_match",
        execution_type="hybrid",
        current_status="ready_in_rule_library",
        notes="规则库已有，需补前一天/当天窗口和出院同意语义。",
    ),
    MappingPattern(
        family="出院记录缺失/提前书写/时效异常/签名缺失",
        keywords_any=("出院记录", "提前书写出院记录", "新建出院记录", "未在24小时内完成出院记录", "无医师签名"),
        candidate_rule_ids=("SC-116", "SC-117", "SC-118", "SC-126"),
        mapping_type="direct_match",
        execution_type="hybrid",
        current_status="partial",
        notes="SC-116/117/126 已在程序规则链实现；提前书写与内容质量需补语义判定。",
    ),
    MappingPattern(
        family="诊疗医嘱与病程记录不一致",
        keywords_any=("医嘱", "与病程记录不一致", "未体现高血压用药情况", "抗菌药物使用", "开具手术申请医嘱时间早于"),
        candidate_rule_ids=("SC-146",),
        mapping_type="direct_match",
        execution_type="semantic",
        current_status="ready_in_rule_library",
        notes="规则库已有，适合做跨文书一致性语义规则。",
    ),
)


def _load_unique_issues() -> list[str]:
    dataframe = pd.read_excel(SOURCE_XLS, sheet_name=1, header=1)
    values = [
        str(value).strip()
        for value in dataframe["存在问题"].tolist()
        if str(value).strip() and str(value).strip().lower() != "nan"
    ]
    return sorted(set(values))


def _merge_execution_types(values: list[str]) -> str:
    unique_values = sorted(set(values))
    if len(unique_values) == 1:
        return unique_values[0]
    if "hybrid" in unique_values or ("programmatic" in unique_values and "semantic" in unique_values):
        return "hybrid"
    return "/".join(unique_values)


def _merge_mapping_types(values: list[str]) -> str:
    unique_values = sorted(set(values))
    if "new_rule" in unique_values:
        return "new_rule"
    if "extend_existing" in unique_values:
        return "extend_existing"
    if "direct_match" in unique_values:
        return "direct_match"
    return "/".join(unique_values)


def _merge_current_status(values: list[str]) -> str:
    priority = (
        "new_rule_needed",
        "todo_semantic",
        "todo_programmatic",
        "deferred_data_gap",
        "ready_in_rule_library",
        "partial",
        "implemented",
    )
    unique_values = set(values)
    for item in priority:
        if item in unique_values:
            return item
    return "/".join(sorted(unique_values))


def _build_seed_rows(unique_issues: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for issue_text in unique_issues:
        matched_patterns = [pattern for pattern in PATTERNS if pattern.matches(issue_text)]
        families = [pattern.family for pattern in matched_patterns]
        rule_ids = sorted({rule_id for pattern in matched_patterns for rule_id in pattern.candidate_rule_ids})
        mapping_types = [pattern.mapping_type for pattern in matched_patterns] or ["manual_review"]
        execution_types = [pattern.execution_type for pattern in matched_patterns] or ["manual"]
        statuses = [pattern.current_status for pattern in matched_patterns] or ["manual_review"]
        notes = "；".join(dict.fromkeys(pattern.notes for pattern in matched_patterns if pattern.notes))
        rows.append(
            {
                "sheet2_issue_text": issue_text,
                "normalized_issue_family": "；".join(families) if families else "待人工归类",
                "candidate_rule_ids": "|".join(rule_ids),
                "mapping_type": _merge_mapping_types(mapping_types),
                "execution_type": _merge_execution_types(execution_types),
                "current_status": _merge_current_status(statuses),
                "notes": notes or "未命中现有映射规则，需人工补充。",
            }
        )
    return rows


def _write_csv(rows: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sheet2_issue_text",
        "normalized_issue_family",
        "candidate_rule_ids",
        "mapping_type",
        "execution_type",
        "current_status",
        "notes",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(rows: list[dict[str, Any]]) -> None:
    summary = {
        "source": str(SOURCE_XLS),
        "output_csv": str(OUTPUT_CSV),
        "unique_issue_count": len(rows),
        "mapping_type_breakdown": dict(Counter(row["mapping_type"] for row in rows)),
        "execution_type_breakdown": dict(Counter(row["execution_type"] for row in rows)),
        "current_status_breakdown": dict(Counter(row["current_status"] for row in rows)),
        "unmapped_examples": [
            row["sheet2_issue_text"]
            for row in rows
            if row["normalized_issue_family"] == "待人工归类"
        ][:30],
    }
    OUTPUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def main() -> int:
    unique_issues = _load_unique_issues()
    rows = _build_seed_rows(unique_issues)
    _write_csv(rows)
    _write_summary(rows)
    print(f"unique_issues={len(unique_issues)}")
    print(f"csv={OUTPUT_CSV}")
    print(f"summary={OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
