#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.medical_records.detail_service import get_documents  # noqa: E402


QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
RELEASE_DIR = REPO_ROOT / "release" / "0426_full_auto" / "0426_full_auto"
BACKLOG_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog.csv"
LEDGER_CSV = QC_DIR / "sheet2_verification_ledger_seed.csv"
OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_overrides.csv"
BACKLOG_OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog_overrides.csv"
SUMMARY_JSON = QC_DIR / "sheet2_exact_review_summary.json"
BASELINE_JSON = QC_DIR / "sheet2_exact_review_summary.baseline.json"
REPORT_CSV = QC_DIR / "sheet2_p0_anchor_enhancement_replay_report.csv"
REPORT_JSON = QC_DIR / "sheet2_p0_anchor_enhancement_replay_report.json"
REPORT_MD = QC_DIR / "2026-05-08-Sheet2-P0专项锚点增强回放.md"

REPORT_FIELDS = [
    "sample_id",
    "visit_id",
    "patient_name",
    "parent_rule_id",
    "anchor_id",
    "anchor_triggered",
    "evidence_status",
    "old_status",
    "new_status",
    "target_blocked_reason_type",
    "target_backlog_category",
    "decision_reason",
    "used_documents",
    "evidence_snippet",
]


P0_DECISIONS: dict[str, dict[str, Any]] = {
    "Sheet2-R0035": {
        "parent_rule_id": "SC-009",
        "anchor_id": "SC-009-trauma-location",
        "markers": ["外伤", "在家里用电剪子剪花椒丫时损伤"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_exclusion_met",
        "reason": "触发外伤现病史 anchor，但原文已写“在家里用电剪子剪花椒丫时损伤”，受伤地点/场景/机制均已覆盖，不能按“未描述受伤地点”升级 exact。",
    },
    "Sheet2-R0254": {
        "parent_rule_id": "SC-009",
        "anchor_id": "SC-009-trauma-location",
        "markers": ["外伤", "在泸县谭坝过路时被叫帮忙被钢架砸伤"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_exclusion_met",
        "reason": "触发外伤现病史 anchor，但原文已写“在泸县谭坝过路时被叫帮忙被钢架砸伤”，已覆盖受伤地点和致伤机制，不能按“未描述受伤地点”升级 exact。",
    },
    "Sheet2-R0058": {
        "parent_rule_id": "SC-008",
        "anchor_id": "SC-009-symptom-detail",
        "markers": ["剑突下疼痛不适半月", "伴反酸", "类风湿病史"],
        "status": "blocked_with_reason",
        "reason_type": "证据链不足",
        "backlog_category": "需补源文书",
        "evidence_status": "partial_anchor_evidence_gap",
        "reason": "现病史能看到疼痛部位、持续时间和伴随症状，但人工问题还包含疼痛性质/缓解方式及既往肺结核病史漏问，当前证据不能完整覆盖整条人工问题。",
    },
    "Sheet2-R0021": {
        "parent_rule_id": "SC-009",
        "anchor_id": "SC-009-symptom-detail",
        "markers": ["咽痛、咽部异物感10+天", "持续性疼痛", "白色粘痰", "当地卫生院输液治疗"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_exclusion_met",
        "reason": "症状细节 anchor 被触发，但原文已记录疼痛持续性、痰液性状、夜间加重、卫生院治疗和体重变化，人工问题多项锚点与现有原文冲突。",
    },
    "Sheet2-R0112": {
        "parent_rule_id": "SC-008",
        "anchor_id": "SC-009-symptom-detail",
        "markers": ["右侧腋区、肋部皮肤红斑", "伴疼痛2天", "胰腺脓肿引流术", "混合性高脂血症"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "partial_anchor_only",
        "reason": "可见症状部位、病程时间和既往手术史，但人工问题同时包含阴性病史、高血压监测筛查、既往手术进一步描述等多锚点，不能作为单一 SC-009/SC-008 exact。",
    },
    "Sheet2-R0139": {
        "parent_rule_id": "SC-020",
        "anchor_id": "SC-009-symptom-detail",
        "markers": ["左侧胸部不适5天", "胸部胀痛", "牵扯样疼痛"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_exclusion_met",
        "reason": "胸痛症状 anchor 被触发，但原文已记录部位、持续时间、性质及伴随症状；人工问题称缺疼痛要素与原文冲突。",
    },
    "Sheet2-R0060": {
        "parent_rule_id": "SC-009",
        "anchor_id": "SC-009-symptom-detail",
        "markers": ["疼痛", "治疗经过", "转入外二科"],
        "status": "blocked_with_reason",
        "reason_type": "需客户确认口径",
        "backlog_category": "需客户确认口径",
        "evidence_status": "composite_scope_requires_customer_policy",
        "reason": "现病史疼痛/治疗经过只是复合人工问题的一部分，原问题还包含月经史、入转科时间和收治科室欠妥，需客户先拆分并确认口径。",
    },
    "Sheet2-R0141": {
        "parent_rule_id": "SC-009",
        "anchor_id": "SC-009-symptom-detail",
        "markers": ["头晕", "手术史", "主治医师查房"],
        "status": "blocked_with_reason",
        "reason_type": "需客户确认口径",
        "backlog_category": "需客户确认口径",
        "evidence_status": "composite_scope_requires_customer_policy",
        "reason": "人工问题混合头晕阴性症状、手术史查体、主治查房分析水平多个评价口径，不适合用单一症状明细 anchor 升级 exact。",
    },
    "Sheet2-R0283": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["肾功", "尿常规提示泌尿道感染", "请泌尿血管外科会诊"],
        "status": "blocked_with_reason",
        "reason_type": "证据链不足",
        "backlog_category": "需补源文书",
        "evidence_status": "evidence_gap_latest_lab_anchor_missing",
        "reason": "当前可见病程已分析 4月1日尿常规并请会诊，但未复原人工所称 4月7日肾功异常原始检验结果，仍需补最新检验明细。",
    },
    "Sheet2-R0214": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["K 3.08mmol/l", "低钾", "补充电解质", "香蕉"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_exclusion_met",
        "reason": "异常结果 anchor 被触发，但病程已写低钾并嘱进食香蕉等补充电解质，人工称无处理与原文冲突。",
    },
    "Sheet2-R0224": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["哌拉西林他唑巴坦抗感染", "出院诊断", "胆囊结石伴急性胆囊炎"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_or_missing_anchor",
        "reason": "当前可见病程有抗感染处理，但未命中人工所称“双肺感染”原句；不能证明胸部 CT 感染未分析/未会诊成立。",
    },
    "Sheet2-R0225": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["K 3.44mmol/l", "未见明显异常", "双肺结节"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_or_missing_anchor",
        "reason": "当前可见电解质 K 3.44mmol/l 被病程描述为未见明显异常，未命中“双肺结节”核心原句，不能按异常未处理升级 exact。",
    },
    "Sheet2-R0226": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["WBC 9.58", "NEUT% 87.6%", "CRP 4.4mg/L", "血气分析提示氧合指数尚可"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_exclusion_met",
        "reason": "异常结果 anchor 被触发，但病程已记录血常规/CRP并分析拔管、镇痛、基础血栓预防等处理，不能按“未分析和记录”升级 exact。",
    },
    "Sheet2-R0241": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["双侧基底节区腔隙性脑梗塞", "神经内科门诊随访脑梗塞情况", "诊断名称"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_exclusion_met",
        "reason": "脑梗 anchor 被触发，但入院/出院诊断均已纳入双侧基底节区腔隙性脑梗塞，出院医嘱亦要求神经内科门诊随访，不能整条判为未分析/未处理。",
    },
    "Sheet2-R0243": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["血气分析", "血气分析提示氧合指数尚可", "对症处理"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_or_overbroad_anchor",
        "reason": "人工问题未指定异常项目；当前可见病程已对血气分析、咳嗽咳痰等作记录和处理，不能用宽泛“异常检验”升级 exact。",
    },
    "Sheet2-R0265": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["尿常规提示存在白细胞", "无尿频", "考虑膀胱结石", "头孢呋辛抗感染"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_exclusion_met",
        "reason": "尿常规 anchor 被触发，但首程/查房已分析无尿路感染症状、考虑膀胱结石所致并予抗感染处理，人工称未分析处理与原文冲突。",
    },
    "Sheet2-R0266": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["左侧部分肋骨骨折", "呼吸科会诊意见", "哌拉西林他唑巴坦抗感染"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "partial_anchor_with_source_conflict",
        "reason": "可见胸部 CT 肋骨骨折 anchor，但病程已记录胸部 CT 和呼吸科会诊/抗感染处理；人工称病程未体现不能整条 exact。",
    },
    "Sheet2-R0268": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["4.1", "异常", "检验"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "overbroad_anchor_not_exact",
        "reason": "人工问题只写“4.1异常检查检验结果”但未指定异常项目，当前回放无法建立单一可复现锚点；需客户提供具体异常项。",
    },
    "Sheet2-R0272": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["2026-03-24 电解质3", "动态复查感染指标", "动态复查电解质"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_or_missing_latest_anchor",
        "reason": "可见病程已有动态复查检验和处理表述，但未复原人工所称 4月1日最新检验原句，不能判定病程停留在 3月22日。",
    },
    "Sheet2-R0262": {
        "parent_rule_id": "SC-036",
        "anchor_id": "SC-036-abnormal-result-unaddressed",
        "markers": ["双下肢动脉粥样硬化伴斑块", "阿托伐他汀 20mg qn", "心内科"],
        "status": "blocked_with_reason",
        "reason_type": "需客户确认口径",
        "backlog_category": "需客户确认口径",
        "evidence_status": "source_conflict_requires_policy",
        "reason": "血管彩超阳性 anchor 被触发，但已有心内科/神经科会诊及阿托伐他汀处理；是否仍认为“无相关处理”需客户确认处理充分性口径。",
    },
    "Sheet2-R0061": {
        "parent_rule_id": "SC-020",
        "anchor_id": "SC-020-admission-diagnosis-omission",
        "markers": ["类风湿性关节炎", "诊断名称", "12、类风湿性关节炎"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_exclusion_met",
        "reason": "诊断遗漏 anchor 被触发，但入院诊断列表已包含“类风湿性关节炎”，人工称未体现与原文冲突。",
    },
    "Sheet2-R0069": {
        "parent_rule_id": "SC-020",
        "anchor_id": "SC-020-admission-diagnosis-omission",
        "markers": ["右侧输尿管结石", "右肾积水", "右侧肾绞痛"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_text_conflict_keep_blocked",
        "reason": "当前原文支持结石/肾积水/肾绞痛，缺少前列腺增生和泌尿道感染确诊依据，延续第三方纠偏的原文冲突口径。",
    },
    "Sheet2-R0107": {
        "parent_rule_id": "SC-020",
        "anchor_id": "SC-020-admission-diagnosis-omission",
        "markers": ["既往有高血压病史多年", "长期口服苯磺酸氨氯地平", "穿刺活检", "操作记录"],
        "status": "blocked_with_reason",
        "reason_type": "证据链不足",
        "backlog_category": "需补源文书",
        "evidence_status": "partial_anchor_evidence_gap",
        "reason": "高血压诊断遗漏可作为局部 anchor，但人工问题同时包含医嘱用药、腹股沟疝查体、有创穿刺操作记录缺失；当前仍缺手术/操作记录证据，不能 pure exact。",
    },
    "Sheet2-R0124": {
        "parent_rule_id": "SC-020",
        "anchor_id": "SC-020-admission-diagnosis-omission",
        "markers": ["社区获得性肺炎", "呛咳", "吸入"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "missing_anchor_or_source_conflict",
        "reason": "当前回放未命中人工所述呛咳/吸入性证据链，不能证明社区获得性肺炎诊断不合理成立。",
    },
    "Sheet2-R0264": {
        "parent_rule_id": "SC-020",
        "anchor_id": "SC-020-admission-diagnosis-omission",
        "markers": ["直肠Ca手术治疗", "诊断名称: 1.肠梗阻2.急性腹膜炎3.直肠术后"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_exclusion_met",
        "reason": "诊断遗漏 anchor 被触发，但入院/初步诊断已写“直肠术后”，人工称无相关诊断与原文冲突。",
    },
    "Sheet2-R0070": {
        "parent_rule_id": "SC-020",
        "anchor_id": "SC-020-admission-diagnosis-omission",
        "markers": ["高脂血症？", "活动后呼吸困难、胸前区不适1月", "初步诊断"],
        "status": "blocked_with_reason",
        "reason_type": "需客户确认口径",
        "backlog_category": "需客户确认口径",
        "evidence_status": "source_conflict_requires_policy",
        "reason": "初步诊断已纳入“高脂血症？”且现病史写活动后呼吸困难；是否待查式诊断仍算未诊断需客户确认口径。",
    },
    "Sheet2-R0028": {
        "parent_rule_id": "SC-070",
        "anchor_id": "SC-070-consultation-not-implemented",
        "markers": ["可予左氧氟沙星滴眼液", "已遵嘱执行"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "source_conflict_exclusion_met",
        "reason": "会诊执行 anchor 被触发，但原文已写具体眼科处理“左氧氟沙星滴眼液”并“已遵嘱执行”，人工称仅描述遵执与原文冲突。",
    },
    "Sheet2-R0153": {
        "parent_rule_id": "SC-070",
        "anchor_id": "SC-070-consultation-not-implemented",
        "markers": ["针灸", "低频", "中药贴敷", "关节松动"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "missing_execution_evidence",
        "reason": "当前样本验证链路未命中康复会诊建议和执行清单完整证据，不能证明具体治疗项目未落实。",
    },
    "Sheet2-R0173": {
        "parent_rule_id": "SC-070",
        "anchor_id": "SC-070-consultation-not-implemented",
        "markers": ["心血管内科", "呼吸内科", "麻醉科", "皮肤科"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "missing_execution_evidence",
        "reason": "可见多科会诊相关锚点，但源库执行清单/inpat_execution_record 缺失，不能用“无执行记录”直接升级 exact。",
    },
    "Sheet2-R0200": {
        "parent_rule_id": "SC-070",
        "anchor_id": "SC-070-consultation-not-implemented",
        "markers": ["拟遵照执行", "遵会诊", "执行"],
        "status": "blocked_with_reason",
        "reason_type": "证据链不足",
        "backlog_category": "需补源文书",
        "evidence_status": "missing_consultation_or_execution_text",
        "reason": "当前回放未复原“拟遵照执行/已遵会诊意见执行”原句，仍需补会诊执行记录原文。",
    },
    "Sheet2-R0279": {
        "parent_rule_id": "SC-070",
        "anchor_id": "SC-070-consultation-not-implemented",
        "markers": ["针灸", "电刺激治疗", "耳穴", "中药塌渍"],
        "status": "blocked_with_reason",
        "reason_type": "证据链不足",
        "backlog_category": "需补源文书",
        "evidence_status": "missing_execution_evidence",
        "reason": "可见会诊建议含耳穴等康复项目，但缺少执行清单证明实际未予耳穴治疗，不能升级 exact。",
    },
    "Sheet2-R0220": {
        "parent_rule_id": "SC-070",
        "anchor_id": "SC-070-consultation-not-implemented",
        "markers": ["拒绝康复治疗", "电刺激", "超声波", "清创"],
        "status": "blocked_with_reason",
        "reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "evidence_status": "partial_anchor_with_cross_family_conflict",
        "reason": "会诊拒绝康复与后续康复治疗锚点仅部分成立；清创无操作记录与现有清创/手术摘要冲突，BP 未复测属跨质控点，不能整条 exact。",
    },
    "Sheet2-R0239": {
        "parent_rule_id": "SC-046",
        "anchor_id": "SC-046-invasive-operation-required-fields",
        "markers": ["息肉", "圈套器切除", "送检"],
        "status": "blocked_with_reason",
        "reason_type": "证据链不足",
        "backlog_category": "需补源文书",
        "evidence_status": "missing_operation_record_text",
        "reason": "有创操作必填项 anchor 需要操作记录正文；当前仍缺可进入样本验证页的 surgery_record/mr_surgery 原文，不能判 exact。",
    },
    "Sheet2-R0249": {
        "parent_rule_id": "SC-046",
        "anchor_id": "SC-046-invasive-operation-required-fields",
        "markers": ["脓肿", "体位", "送检", "局麻"],
        "status": "blocked_with_reason",
        "reason_type": "证据链不足",
        "backlog_category": "需补源文书",
        "evidence_status": "missing_operation_record_text",
        "reason": "有创操作必填项 anchor 需要清创/操作记录正文；当前只见入院记录和辅助证据，仍缺操作记录原文。",
    },
    "Sheet2-R0288": {
        "parent_rule_id": "SC-046",
        "anchor_id": "SC-046-invasive-operation-required-fields",
        "markers": ["头面部被人打伤", "右侧面部皮肤裂伤", "清创"],
        "status": "blocked_with_reason",
        "reason_type": "证据链不足",
        "backlog_category": "需补源文书",
        "evidence_status": "missing_operation_record_text",
        "reason": "入院记录可见右侧面部裂伤，但人工问题核心是清创记录标题/部位及操作字段缺项，当前缺清创记录正文，不能升级 exact。",
    },
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _safe_text(row.get(field)) for field in fields})


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", _safe_text(value)).strip()


def _release_text(visit_id: str) -> str:
    chunks: list[str] = []
    for path in RELEASE_DIR.glob("*.csv"):
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    if _safe_text(row.get("visit_id")) == visit_id:
                        chunks.append(f"[release:{path.stem}] " + " ".join(_safe_text(value) for value in row.values() if _safe_text(value)))
        except UnicodeDecodeError:
            continue
    return "\n".join(chunks)


def _bundle_text(visit_id: str) -> str:
    payload = get_documents(visit_id)
    chunks: list[str] = []
    for doc in list((payload or {}).get("documents") or []):
        source = _safe_text(doc.get("source_table"))
        title = _safe_text(doc.get("document_title") or doc.get("title"))
        content = _safe_text(doc.get("content"))
        chunks.append(f"[bundle:{source}] {title}\n{content}")
    return "\n".join(chunks)


def _snippet(text: str, marker: str, radius: int = 95) -> str:
    index = text.find(marker)
    if index < 0:
        return ""
    return _normalize(text[max(0, index - radius) : index + len(marker) + radius])


def _evaluate(row: dict[str, str]) -> dict[str, str]:
    sample_id = _safe_text(row.get("sheet2_row_id"))
    decision = P0_DECISIONS[sample_id]
    evidence_text = _bundle_text(_safe_text(row.get("visit_id"))) + "\n" + _release_text(_safe_text(row.get("visit_id")))
    snippets = []
    for marker in decision["markers"]:
        snippet = _snippet(evidence_text, marker)
        if snippet:
            snippets.append(f"{marker}: {snippet[:260]}")
    old_status = _safe_text(row.get("exact_review_status") or "blocked_with_reason")
    new_status = decision["status"]
    return {
        "sample_id": sample_id,
        "visit_id": _safe_text(row.get("visit_id")),
        "patient_name": _safe_text(row.get("patient_name")),
        "parent_rule_id": decision["parent_rule_id"],
        "anchor_id": decision["anchor_id"],
        "anchor_triggered": "yes" if snippets else "uncertain",
        "evidence_status": decision["evidence_status"],
        "old_status": old_status,
        "new_status": new_status,
        "target_blocked_reason_type": decision["reason_type"],
        "target_backlog_category": decision["backlog_category"],
        "decision_reason": decision["reason"],
        "used_documents": "sample_validation_bundle|release_0426_full_auto",
        "evidence_snippet": "；".join(snippets[:3]),
    }


def build_report() -> list[dict[str, str]]:
    _, backlog_rows = _load_csv(BACKLOG_CSV)
    by_id = {_safe_text(row.get("sheet2_row_id")): row for row in backlog_rows}
    missing = sorted(set(P0_DECISIONS) - set(by_id))
    if missing:
        raise ValueError(f"P0 样本不在当前 blocked backlog 中: {missing}")
    return [_evaluate(by_id[sample_id]) for sample_id in P0_DECISIONS]


def _merge_rows(path: Path, key: str, updates: dict[str, dict[str, str]], fields: list[str]) -> None:
    existing_fields, rows = _load_csv(path) if path.exists() else ([], [])
    output_fields = list(dict.fromkeys(existing_fields + fields))
    by_id = {_safe_text(row.get(key)): row for row in rows if _safe_text(row.get(key))}
    for row_id, update in updates.items():
        current = by_id.get(row_id, {key: row_id})
        current.update(update)
        by_id[row_id] = current
    ordered: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        row_id = _safe_text(row.get(key))
        if row_id in by_id:
            ordered.append(by_id[row_id])
            seen.add(row_id)
    for row_id in sorted(set(by_id) - seen):
        ordered.append(by_id[row_id])
    _write_csv(path, ordered, output_fields)


def _update_ledger(results: list[dict[str, str]]) -> None:
    fields, rows = _load_csv(LEDGER_CSV)
    added = [
        "p0_anchor_id",
        "p0_anchor_evidence_status",
        "p0_anchor_replay_reason",
        "p0_anchor_replay_snippet",
    ]
    by_id = {_safe_text(row.get("sheet2_row_id")): row for row in rows}
    for result in results:
        row = by_id.get(result["sample_id"])
        if not row:
            continue
        row["primary_rule_id"] = result["parent_rule_id"] or row.get("primary_rule_id", "")
        row["evidence_summary"] = result["decision_reason"]
        row["next_action"] = (
            "P0 anchor 已回放；若需 exact，需补齐缺失源文书/执行清单或拆分复合人工问题后再回归。"
            if result["new_status"] == "blocked_with_reason"
            else "P0 anchor 已 exact_confirmed。"
        )
        row["p0_anchor_id"] = result["anchor_id"]
        row["p0_anchor_evidence_status"] = result["evidence_status"]
        row["p0_anchor_replay_reason"] = result["decision_reason"]
        row["p0_anchor_replay_snippet"] = result["evidence_snippet"]
    _write_csv(LEDGER_CSV, rows, list(dict.fromkeys(fields + added)))


def _writeback(results: list[dict[str, str]]) -> None:
    override_updates = {}
    backlog_updates = {}
    for result in results:
        sample_id = result["sample_id"]
        override_updates[sample_id] = {
            "sheet2_row_id": sample_id,
            "exact_review_status": result["new_status"],
            "exact_review_reason": result["decision_reason"],
            "blocked_reason_type": result["target_blocked_reason_type"],
            "review_subgroup": f"P0专项锚点增强-{result['anchor_id']}-{result['evidence_status']}",
            "decision_source": "sheet2_p0_anchor_enhancement_replay_report",
        }
        if result["new_status"] == "blocked_with_reason":
            backlog_updates[sample_id] = {
                "sheet2_row_id": sample_id,
                "backlog_category": result["target_backlog_category"],
                "backlog_reason": result["decision_reason"],
                "next_action": "按 P0 anchor 回放结果补齐源文书/执行清单、拆分复合人工问题或确认客户口径后再回归。",
            }
    _merge_rows(
        OVERRIDE_CSV,
        "sheet2_row_id",
        override_updates,
        ["sheet2_row_id", "exact_review_status", "exact_review_reason", "blocked_reason_type", "review_subgroup", "decision_source"],
    )
    _merge_rows(
        BACKLOG_OVERRIDE_CSV,
        "sheet2_row_id",
        backlog_updates,
        ["sheet2_row_id", "backlog_category", "backlog_reason", "next_action"],
    )
    _update_ledger(results)
    _load_script_module("build_sheet2_exact_review_matrix.py").main()
    _load_script_module("build_sheet2_exact_review_acceptance_package.py").main()
    shutil.copyfile(SUMMARY_JSON, BASELINE_JSON)
    gap_script = Path(__file__).resolve().parent / "build_sheet2_blocked_customer_gap_list.py"
    if gap_script.exists():
        try:
            _load_script_module("build_sheet2_blocked_customer_gap_list.py").main()
        except PermissionError as exc:
            print(f"warning: 客户沟通清单文件可能被占用，已跳过自动刷新：{exc}")


def _write_reports(results: list[dict[str, str]], writeback: bool) -> None:
    _write_csv(REPORT_CSV, results, REPORT_FIELDS)
    summary = {
        "total": len(results),
        "writeback": writeback,
        "status_breakdown": dict(Counter(row["new_status"] for row in results)),
        "anchor_breakdown": dict(Counter(row["anchor_id"] for row in results)),
        "evidence_status_breakdown": dict(Counter(row["evidence_status"] for row in results)),
        "blocked_to_exact_rows": [row for row in results if row["new_status"] == "exact_confirmed"],
        "kept_blocked_rows": [row for row in results if row["new_status"] == "blocked_with_reason"],
    }
    REPORT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Sheet2 P0 专项锚点增强回放",
        "",
        "日期：2026-05-08",
        "",
        "## 结论",
        "",
        f"- 本轮回放 P0 anchor 样本：{len(results)} 条。",
        f"- blocked -> exact_confirmed：{len(summary['blocked_to_exact_rows'])} 条。",
        f"- 保持 blocked_with_reason：{len(summary['kept_blocked_rows'])} 条。",
        "- 本轮只作用于客户样本验证/Sheet2 回归链路，不改 dashboard 全量质控入口。",
        "- 未将 covered bundle、same_family_hit 或 partial/effective 直接包装为 exact。",
        "",
        "## Anchor 统计",
        "",
        "| anchor_id | count |",
        "| --- | ---: |",
    ]
    for anchor_id, count in summary["anchor_breakdown"].items():
        lines.append(f"| {anchor_id} | {count} |")
    lines.extend(["", "## 逐条结论", "", "| sample | rule | anchor | evidence_status | new_status | reason |", "| --- | --- | --- | --- | --- | --- |"])
    for row in results:
        lines.append(
            f"| {row['sample_id']} | {row['parent_rule_id']} | {row['anchor_id']} | {row['evidence_status']} | {row['new_status']} | {row['decision_reason']} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sheet2 P0 专项锚点增强回放")
    parser.add_argument("--writeback", action="store_true")
    args = parser.parse_args()
    results = build_report()
    _write_reports(results, args.writeback)
    if args.writeback:
        _writeback(results)
    print(
        json.dumps(
            {
                "total": len(results),
                "status_breakdown": dict(Counter(row["new_status"] for row in results)),
                "evidence_status_breakdown": dict(Counter(row["evidence_status"] for row in results)),
                "writeback": args.writeback,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
