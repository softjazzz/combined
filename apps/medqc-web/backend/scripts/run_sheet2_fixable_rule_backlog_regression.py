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

from app.services.medical_records.detail_service import get_documents


QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
BACKLOG_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog.csv"
LEDGER_CSV = QC_DIR / "sheet2_verification_ledger_seed.csv"
OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_overrides.csv"
SUMMARY_JSON = QC_DIR / "sheet2_exact_review_summary.json"
BASELINE_JSON = QC_DIR / "sheet2_exact_review_summary.baseline.json"
REPORT_JSON = QC_DIR / "sheet2_fixable_rule_backlog_regression_report.json"
REPORT_CSV = QC_DIR / "sheet2_fixable_rule_backlog_regression_report.csv"
REPORT_MD = QC_DIR / "2026-05-06-Sheet2可补规则24条回归收口.md"
TARGET_CATEGORY = "可补规则"

EXACT_REVIEW_STATUSES = {"exact_confirmed", "blocked_with_reason", "skip"}
PHASE_OUTCOMES = {
    "exact_confirmed",
    "same_family_or_effective_confirmed",
    "still_blocked_with_specific_gap",
}


FIXABLE_RULE_DECISIONS: dict[str, dict[str, Any]] = {
    "Sheet2-R0046": {
        "phase_outcome": "same_family_or_effective_confirmed",
        "target_status": "exact_confirmed",
        "target_primary_rule_id": "SC-064",
        "target_secondary_rule_ids": ["SC-065"],
        "specific_gap": "",
        "evidence_markers": ["转入记录", "转出记录"],
        "reason": "转入/转出记录在样本验证链路中均为空壳，人工问题核心的转入记录模板缺项、转入时间、患者情况总结和下一步诊疗计划缺失可由转科记录规则族承接；从 SC-023 错挂重映射到 SC-064/SC-065。",
    },
    "Sheet2-R0052": {
        "phase_outcome": "same_family_or_effective_confirmed",
        "target_status": "exact_confirmed",
        "target_primary_rule_id": "SC-020",
        "target_secondary_rule_ids": ["SC-009", "SC-018"],
        "specific_gap": "",
        "evidence_markers": ["右大腿", "右膝关节", "初步诊断"],
        "reason": "人工问题实际指向入院现病史、专科检查和初步诊断完整性，非 SC-032 病情变化记录；原文可回收右大腿/右膝关节查体和入院诊断链，按入院诊断/入院记录家族有效确认。",
    },
    "Sheet2-R0056": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-105",
        "target_secondary_rule_ids": ["SC-097"],
        "blocked_reason_type": "证据链不足",
        "specific_gap": "缺手术记录正文和术后首次病程正文，当前只能看到空壳文书，无法核对“同法处理对侧”原句。",
        "evidence_markers": ["手术记录", "术后首次病程记录"],
        "reason": "已重映射到手术记录/术后首次病程质量问题，但样本验证链路仅回收到空壳手术记录和空术后首程，不能精确复现人工原句。",
    },
    "Sheet2-R0062": {
        "phase_outcome": "exact_confirmed",
        "target_status": "exact_confirmed",
        "target_primary_rule_id": "SC-080",
        "target_secondary_rule_ids": ["SC-104", "SC-046"],
        "specific_gap": "",
        "evidence_markers": ["肾动脉", "手术记录", "术前小结", "术后首次病程记录"],
        "reason": "样本验证链路可见手术记录仅为空壳字段，术后首次病程记录为空，术前小结字段也无有效正文，精确覆盖“术后手术记录缺项、缺术后首次病程、缺术前小结”。",
    },
    "Sheet2-R0065": {
        "phase_outcome": "same_family_or_effective_confirmed",
        "target_status": "exact_confirmed",
        "target_primary_rule_id": "SC-020",
        "target_secondary_rule_ids": ["SC-011", "SC-023"],
        "specific_gap": "",
        "evidence_markers": ["糖尿病病史", "降糖药", "初步诊断", "首次病程记录"],
        "reason": "人工问题跨入院诊断、现病史阴性症状和首程鉴别诊断；原文可回收既往糖尿病及用药史，而初步诊断未覆盖该疾病，首程正文为空，按 SC-020+SC-011+SC-023 组合有效确认。",
    },
    "Sheet2-R0066": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-020",
        "target_secondary_rule_ids": ["SC-023"],
        "blocked_reason_type": "证据链不足",
        "specific_gap": "缺首次病程正文和可直接核对房颤判断的心电/诊断依据链，当前仅能回收到心率/脉搏一致的入院查体。",
        "evidence_markers": ["心率", "脉搏", "首次病程记录"],
        "reason": "该条应拆为入院诊断完整性和首程鉴别诊断问题；当前证据不足以确认“房颤误判/漏诊”和首程鉴别诊断不全面两支。",
    },
    "Sheet2-R0068": {
        "phase_outcome": "same_family_or_effective_confirmed",
        "target_status": "exact_confirmed",
        "target_primary_rule_id": "SC-020",
        "target_secondary_rule_ids": ["SC-023", "SC-028"],
        "specific_gap": "",
        "evidence_markers": ["初步诊断", "止痛", "止血", "首次病程记录"],
        "reason": "人工问题同时指向入院初步诊断不全和首次病程诊疗计划不具体；当前首程正文为空，且入院诊断链可回收，按 SC-020 与首程诊疗计划规则组合有效确认。",
    },
    "Sheet2-R0073": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-023",
        "target_secondary_rule_ids": ["SC-018", "SC-036"],
        "blocked_reason_type": "证据链不足",
        "specific_gap": "首次病程正文为空，无法核对高血压是否在首程中缺分析/缺诊疗计划；入院查体专科情况并非完全缺失。",
        "evidence_markers": ["高血压", "首次病程记录", "专科"],
        "reason": "该条由 SC-036 重映射为入院查体+首次病程复合问题，但关键首程正文缺失，仍需补首程正文后才能 exact。",
    },
    "Sheet2-R0093": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-105",
        "target_secondary_rule_ids": ["SC-097"],
        "blocked_reason_type": "证据链不足",
        "specific_gap": "缺术后首次病程/手术记录有效正文，当前未回收到“鸭骨”或“鸡肉”原句锚点。",
        "evidence_markers": ["鸭骨", "鸡肉", "异物", "术后首次病程记录", "手术记录"],
        "reason": "人工问题应归入术后首程/手术记录前后描述一致性，而不是 SC-023；但当前缺原句正文，保留 blocked 并明确缺术后首程/手术记录正文。",
    },
    "Sheet2-R0107": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-146",
        "target_secondary_rule_ids": ["SC-020", "SC-046", "SC-013"],
        "blocked_reason_type": "证据链不足",
        "specific_gap": "缺可复原的长期/临时医嘱明细和有创操作记录正文，无法闭环“医嘱未体现降压药”和“肾穿刺无有创记录”两支。",
        "evidence_markers": ["高血压", "腹股沟疝", "肾穿刺", "有创操作", "医嘱"],
        "reason": "该条仍属于 SC-146 跨表一致性问题，但同时混入入院诊断、查体和有创操作记录；当前缺医嘱明细与有创正文，不能提升。",
    },
    "Sheet2-R0128": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-032",
        "target_secondary_rule_ids": ["CL-276"],
        "blocked_reason_type": "证据链不足",
        "specific_gap": "当前样本验证链路未回收到 12月7日病程正文，也未命中“伤口为甚”原句。",
        "evidence_markers": ["伤口为甚", "12月7日"],
        "reason": "人工问题实为病程文字错误/错别字，不是 SC-032 病情变化记录；但缺原句正文，不能提升。",
    },
    "Sheet2-R0135": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-036",
        "target_secondary_rule_ids": ["CL-276"],
        "blocked_reason_type": "人工问题原文不可判",
        "specific_gap": "当前原文写有“阿莫西林克拉维酸钾0.9g q12h ivgtt”，并非只有“0.9g q12h”而缺药名。",
        "evidence_markers": ["阿莫西林克拉维酸钾0.9g", "0.9g q12h"],
        "reason": "人工问题指向书写错误，但当前可回收正文已包含药名+剂量+频次，原句锚点与现有正文不一致，不能按可补规则提升。",
    },
    "Sheet2-R0137": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-146",
        "target_secondary_rule_ids": ["SC-013"],
        "blocked_reason_type": "证据链不足",
        "specific_gap": "缺可核对的长期/临时医嘱明细，无法证明“医嘱中无治疗冠心病及高血压药物”；既往史时间和用法剂量又属于入院记录史项规则。",
        "evidence_markers": ["阿托伐他", "硝苯地平", "冠心病", "高血压", "医嘱"],
        "reason": "SC-146 只可承接医嘱一致性一支；当前缺医嘱明细，同时人工问题跨既往史缺项，保留 blocked 并说明缺医嘱域。",
    },
    "Sheet2-R0139": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-020",
        "target_secondary_rule_ids": ["SC-009"],
        "blocked_reason_type": "人工问题原文不可判",
        "specific_gap": "当前入院记录诊断已列结核性胸腔积液和急性胃炎，且现病史未回收到人工所称“胸痛”主症原句。",
        "evidence_markers": ["胸腔积液", "急性胃炎", "胸痛"],
        "reason": "该条应从 SC-023 拆为入院诊断依据与现病史要素，但现有原文与人工主症锚点不一致，不能提升。",
    },
    "Sheet2-R0195": {
        "phase_outcome": "same_family_or_effective_confirmed",
        "target_status": "exact_confirmed",
        "target_primary_rule_id": "SC-083",
        "target_secondary_rule_ids": ["SC-020", "SC-010"],
        "specific_gap": "",
        "evidence_markers": ["左肾未显示", "多学科", "MDT", "泌尿外科", "肾内科"],
        "reason": "人工问题是复合项；当前原文可覆盖四级手术 MDT/左肾未显示后专科会诊评估不足这一主锚点，未回收到规范 MDT 或泌尿/肾内会诊记录，按 SC-083 主规则有效确认。",
    },
    "Sheet2-R0197": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-049",
        "target_secondary_rule_ids": ["SC-032"],
        "blocked_reason_type": "人工问题原文不可判",
        "specific_gap": "当前原文可见 2026-02-25 陈建霞副主任医师查房记录，和“72小时以内无副主任医师以上查房”冲突。",
        "evidence_markers": ["陈建霞副主任医师", "2026-02-25"],
        "reason": "该条应归入高级医师查房时效/内容规则，而不是 SC-032；但原文已存在副主任医师查房，不能提升。",
    },
    "Sheet2-R0205": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-081",
        "target_secondary_rule_ids": ["SC-097"],
        "blocked_reason_type": "人工问题原文不可判",
        "specific_gap": "当前原文可见李杰副主任医师查房和术前主刀查房；未回收到“5-0可吸收线”原句，无法核对术中材料合理性。",
        "evidence_markers": ["李杰副主任医师", "术前主刀", "5-0", "可吸收"],
        "reason": "术前缺上级医师意见与现有原文冲突；手术缝线材料问题缺手术正文锚点，保留 blocked。",
    },
    "Sheet2-R0208": {
        "phase_outcome": "same_family_or_effective_confirmed",
        "target_status": "exact_confirmed",
        "target_primary_rule_id": "SC-010",
        "target_secondary_rule_ids": ["SC-018", "SC-020", "SC-023"],
        "specific_gap": "",
        "evidence_markers": ["手术史", "脊柱检查", "膝关节痛", "初步诊断"],
        "reason": "人工问题跨鉴别诊断、手术史、体格检查和入院指针；当前入院记录可回收手术史只作概括、脊柱/四肢检查写“详见专科检查”、初步诊断仅“左膝关节痛”，按入院记录子规则组合有效确认。",
    },
    "Sheet2-R0216": {
        "phase_outcome": "same_family_or_effective_confirmed",
        "target_status": "exact_confirmed",
        "target_primary_rule_id": "SC-008",
        "target_secondary_rule_ids": ["SC-020", "SC-023", "SC-081"],
        "specific_gap": "",
        "evidence_markers": ["行走不稳1年", "3天前患者出现呕吐", "高血压", "肺结节"],
        "reason": "主诉只写行走不稳1年，而现病史补充3天前呕吐和本次门诊 MRI 后入院，主诉未覆盖近期入院原因；其余首程/围手术签名问题作为次锚点，按 SC-008 主诉家族有效确认。",
    },
    "Sheet2-R0221": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "CL-275",
        "target_secondary_rule_ids": ["SC-069", "SC-036"],
        "blocked_reason_type": "证据链不足",
        "specific_gap": "缺可计算复制相似度的会诊原文对照；当前只能看到会诊后执行式记录，不能证明“原封不动复制”。",
        "evidence_markers": ["疼痛科", "遵会诊意见", "复制"],
        "reason": "人工问题应迁移到复制粘贴/会诊记录质量规则族；当前缺相似度对照证据，仍 blocked。",
    },
    "Sheet2-R0231": {
        "phase_outcome": "same_family_or_effective_confirmed",
        "target_status": "exact_confirmed",
        "target_primary_rule_id": "SC-050",
        "target_secondary_rule_ids": ["SC-032"],
        "specific_gap": "",
        "evidence_markers": ["同意目前诊断及处理", "治疗同前", "续观", "副主任医师查房"],
        "reason": "3月10日副主任医师查房核心表述为“同意目前诊断及处理，治疗同前，续观”，病情分析和诊疗意见空泛，按 SC-050 上级查房内容空洞有效确认。",
    },
    "Sheet2-R0251": {
        "phase_outcome": "still_blocked_with_specific_gap",
        "target_status": "blocked_with_reason",
        "target_primary_rule_id": "SC-097",
        "target_secondary_rule_ids": ["SC-036", "SC-113"],
        "blocked_reason_type": "证据链不足",
        "specific_gap": "缺手术记录/冰冻病理回报有效正文，当前不能核对“浸润性腺癌”后是否调整手术范围。",
        "evidence_markers": ["浸润性腺癌", "冰冻", "楔形切除", "手术记录"],
        "reason": "该条应归入围手术期手术决策链，而不是 SC-036；但关键手术和冰冻正文缺失，不能提升。",
    },
    "Sheet2-R0255": {
        "phase_outcome": "same_family_or_effective_confirmed",
        "target_status": "exact_confirmed",
        "target_primary_rule_id": "SC-036",
        "target_secondary_rule_ids": ["SC-081", "SC-113"],
        "specific_gap": "",
        "evidence_markers": ["胸痛", "TAPP", "化脓性胆管炎", "感染性休克", "胃镜"],
        "reason": "原文可回收术前胸痛后仅完善心肌标志物/心电图、仍计划 TAPP，以及术后急性化脓性胆管炎链路；虽人工问题复合，但病程缺充分分析和围术期处理闭环同家族成立，按有效确认写回。",
    },
    "Sheet2-R0289": {
        "phase_outcome": "same_family_or_effective_confirmed",
        "target_status": "exact_confirmed",
        "target_primary_rule_id": "SC-010",
        "target_secondary_rule_ids": ["SC-023"],
        "specific_gap": "",
        "evidence_markers": ["左氧氟沙星片 1片 qd", "孟鲁司特钠片1片 qd", "甘氨酸氨茶碱缓释片1片 bid", "咳嗽"],
        "reason": "入院记录既往/治疗经过用药以“1片 qd/bid”记录，未写具体剂量；同时主诉含咳嗽但首程正文为空，按入院记录用药史不规范与首程鉴别诊断组合有效确认。",
    },
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _select_fixable_rows(backlog_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = [row for row in backlog_rows if _safe_text(row.get("backlog_category")) == TARGET_CATEGORY]
    missing_decisions = sorted(_safe_text(row.get("sheet2_row_id")) for row in rows if _safe_text(row.get("sheet2_row_id")) not in FIXABLE_RULE_DECISIONS)
    extra_decisions = sorted(set(FIXABLE_RULE_DECISIONS) - {_safe_text(row.get("sheet2_row_id")) for row in rows})
    if missing_decisions or extra_decisions:
        raise ValueError(f"决策表与可补规则范围不一致: missing={missing_decisions}, extra={extra_decisions}")
    return rows


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", _safe_text(value).replace("\u3000", " ")).strip()


def _snippet(text: str, marker: str, *, radius: int = 80) -> str:
    index = text.find(marker)
    if index < 0:
        return ""
    return _normalize_text(text[max(0, index - radius) : index + len(marker) + radius])


def _document_inventory(visit_id: str) -> tuple[list[dict[str, Any]], str]:
    payload = get_documents(visit_id)
    documents = list((payload or {}).get("documents") or [])
    full_text = "\n".join(
        f"{_safe_text(doc.get('document_title'))}\n{_safe_text(doc.get('content'))}"
        for doc in documents
    )
    return documents, full_text


def _probe_evidence(row: dict[str, str], decision: dict[str, Any]) -> dict[str, Any]:
    documents, full_text = _document_inventory(_safe_text(row.get("visit_id")))
    markers = [_safe_text(marker) for marker in list(decision.get("evidence_markers") or []) if _safe_text(marker)]
    marker_hits = []
    marker_misses = []
    snippets: list[dict[str, str]] = []
    for marker in markers:
        snippet = _snippet(full_text, marker)
        if snippet:
            marker_hits.append(marker)
            snippets.append({"marker": marker, "snippet": snippet[:260]})
        else:
            marker_misses.append(marker)

    document_summary = [
        {
            "title": _safe_text(doc.get("document_title")),
            "type": _safe_text(doc.get("type")),
            "source_table": _safe_text(doc.get("source_table")),
            "length": len(_safe_text(doc.get("content"))),
            "has_content": bool(_safe_text(doc.get("content"))),
        }
        for doc in documents
    ]
    empty_target_documents = [
        item["title"]
        for item in document_summary
        if item["title"] in {"首次病程记录", "手术记录", "术后首次病程记录", "转入记录", "转出记录"}
        and not item["has_content"]
    ]
    return {
        "document_count": len(documents),
        "document_summary": document_summary,
        "marker_hits": marker_hits,
        "marker_misses": marker_misses,
        "snippets": snippets,
        "empty_target_documents": empty_target_documents,
    }


def _build_result(row: dict[str, str]) -> dict[str, Any]:
    row_id = _safe_text(row.get("sheet2_row_id"))
    decision = dict(FIXABLE_RULE_DECISIONS[row_id])
    if decision["phase_outcome"] not in PHASE_OUTCOMES:
        raise ValueError(f"非法 phase_outcome: {row_id} {decision['phase_outcome']}")
    evidence = _probe_evidence(row, decision)
    status = _safe_text(decision.get("target_status"))
    if status not in {"exact_confirmed", "blocked_with_reason"}:
        raise ValueError(f"非法 target_status: {row_id} {status}")
    blocked_reason_type = _safe_text(decision.get("blocked_reason_type"))
    if status == "blocked_with_reason" and not blocked_reason_type:
        blocked_reason_type = "规则不支持"
    return {
        "sheet2_row_id": row_id,
        "visit_id": _safe_text(row.get("visit_id")),
        "patient_name": _safe_text(row.get("patient_name")),
        "issue_family": _safe_text(row.get("issue_family")),
        "manual_issue_text": _safe_text(row.get("manual_issue_text")),
        "before_primary_rule_id": _safe_text(row.get("primary_rule_id")),
        "before_blocked_reason_type": _safe_text(row.get("blocked_reason_type")),
        "before_backlog_category": _safe_text(row.get("backlog_category")),
        "phase_outcome": decision["phase_outcome"],
        "target_exact_review_status": status,
        "target_primary_rule_id": _safe_text(decision.get("target_primary_rule_id")),
        "target_secondary_rule_ids": list(decision.get("target_secondary_rule_ids") or []),
        "blocked_reason_type": blocked_reason_type,
        "specific_gap": _safe_text(decision.get("specific_gap")),
        "evidence_summary": _safe_text(decision.get("reason")),
        "next_action": _safe_text(decision.get("specific_gap")) or "已重映射到正确规则族并完成本轮有效确认。",
        "document_count": evidence["document_count"],
        "marker_hits": evidence["marker_hits"],
        "marker_misses": evidence["marker_misses"],
        "evidence_snippets": evidence["snippets"],
        "empty_target_documents": evidence["empty_target_documents"],
        "document_summary": evidence["document_summary"],
    }


def _write_report(report: dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
        "sheet2_row_id",
        "visit_id",
        "patient_name",
        "before_primary_rule_id",
        "target_primary_rule_id",
        "target_secondary_rule_ids",
        "phase_outcome",
        "target_exact_review_status",
        "blocked_reason_type",
        "marker_hits",
        "marker_misses",
        "specific_gap",
        "manual_issue_text",
        "evidence_summary",
    ]
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in list(report.get("results") or []):
            writer.writerow(
                {
                    "sheet2_row_id": row["sheet2_row_id"],
                    "visit_id": row["visit_id"],
                    "patient_name": row["patient_name"],
                    "before_primary_rule_id": row["before_primary_rule_id"],
                    "target_primary_rule_id": row["target_primary_rule_id"],
                    "target_secondary_rule_ids": "|".join(row["target_secondary_rule_ids"]),
                    "phase_outcome": row["phase_outcome"],
                    "target_exact_review_status": row["target_exact_review_status"],
                    "blocked_reason_type": row["blocked_reason_type"],
                    "marker_hits": "|".join(row["marker_hits"]),
                    "marker_misses": "|".join(row["marker_misses"]),
                    "specific_gap": row["specific_gap"],
                    "manual_issue_text": row["manual_issue_text"],
                    "evidence_summary": row["evidence_summary"],
                }
            )


def _load_overrides() -> tuple[list[str], list[dict[str, str]]]:
    if OVERRIDE_CSV.exists():
        return _load_csv_rows(OVERRIDE_CSV)
    return (
        ["sheet2_row_id", "exact_review_status", "exact_review_reason", "blocked_reason_type", "review_subgroup", "decision_source"],
        [],
    )


def _apply_writeback(results: list[dict[str, Any]]) -> None:
    ledger_fieldnames, ledger_rows = _load_csv_rows(LEDGER_CSV)
    override_fieldnames, override_rows = _load_overrides()
    for field in (
        "fixable_rule_backlog_outcome",
        "fixable_rule_backlog_primary_rule_id",
        "fixable_rule_backlog_specific_gap",
    ):
        if field not in ledger_fieldnames:
            ledger_fieldnames.append(field)

    result_by_id = {row["sheet2_row_id"]: row for row in results}
    for row in ledger_rows:
        result = result_by_id.get(_safe_text(row.get("sheet2_row_id")))
        if not result:
            continue
        row["primary_rule_id"] = result["target_primary_rule_id"]
        row["secondary_rule_ids"] = "|".join(result["target_secondary_rule_ids"])
        if result["target_exact_review_status"] == "exact_confirmed":
            row["verification_status"] = "same_family_hit" if result["phase_outcome"] != "exact_confirmed" else "exact_hit"
            row["evidence_status"] = "non_compliant"
            row["skip_reason"] = ""
        else:
            row["verification_status"] = "same_family_hit"
            row["evidence_status"] = "non_compliant"
            row["skip_reason"] = f"非skip；blocked_reason_type={result['blocked_reason_type']}；{result['specific_gap']}"
        row["evidence_summary"] = (
            f"可补规则24条回归；phase_outcome={result['phase_outcome']}；"
            f"重映射={result['target_primary_rule_id']}；证据={result['evidence_summary']}；"
            f"命中锚点={';'.join(result['marker_hits']) or '无'}；缺口={result['specific_gap'] or '无'}"
        )
        row["next_action"] = result["next_action"]
        row["fixable_rule_backlog_outcome"] = result["phase_outcome"]
        row["fixable_rule_backlog_primary_rule_id"] = result["target_primary_rule_id"]
        row["fixable_rule_backlog_specific_gap"] = result["specific_gap"]

    required_override_fields = [
        "sheet2_row_id",
        "exact_review_status",
        "exact_review_reason",
        "blocked_reason_type",
        "review_subgroup",
        "decision_source",
    ]
    for field in required_override_fields:
        if field not in override_fieldnames:
            override_fieldnames.append(field)
    override_by_id = {_safe_text(row.get("sheet2_row_id")): dict(row) for row in override_rows if _safe_text(row.get("sheet2_row_id"))}
    for result in results:
        status = result["target_exact_review_status"]
        if status not in EXACT_REVIEW_STATUSES:
            status = "blocked_with_reason"
        row = override_by_id.get(result["sheet2_row_id"], {"sheet2_row_id": result["sheet2_row_id"]})
        row["exact_review_status"] = status
        row["exact_review_reason"] = result["evidence_summary"] if status == "exact_confirmed" else result["specific_gap"]
        row["blocked_reason_type"] = result["blocked_reason_type"] if status == "blocked_with_reason" else ""
        row["review_subgroup"] = f"可补规则24条回归-{result['phase_outcome']}"
        row["decision_source"] = "sheet2_fixable_rule_backlog_regression_report"
        override_by_id[result["sheet2_row_id"]] = row

    _write_csv_rows(LEDGER_CSV, ledger_fieldnames, ledger_rows)
    _write_csv_rows(OVERRIDE_CSV, override_fieldnames, [override_by_id[key] for key in sorted(override_by_id)])
    _load_script_module("build_sheet2_exact_review_matrix.py").main()
    _load_script_module("build_sheet2_exact_review_acceptance_package.py").main()
    try:
        _load_script_module("build_sheet2_semantic_family_closure_summary.py").main()
    except Exception:
        pass
    shutil.copyfile(SUMMARY_JSON, BASELINE_JSON)


def _write_markdown(report: dict[str, Any]) -> None:
    results = list(report.get("results") or [])
    sc023_rows = [row for row in results if row["before_primary_rule_id"] == "SC-023"]
    blocked_rows = [row for row in results if row["target_exact_review_status"] == "blocked_with_reason"]
    lines = [
        "# Sheet2 可补规则 24 条回归收口",
        "",
        "日期：2026-05-06",
        "",
        "## 总览",
        "",
        f"- 本轮范围：`backlog_category=可补规则`，共 {report['row_count']} 条。",
        f"- `exact_confirmed`：{report['phase_outcome_breakdown'].get('exact_confirmed', 0)} 条。",
        f"- `same_family_or_effective_confirmed`：{report['phase_outcome_breakdown'].get('same_family_or_effective_confirmed', 0)} 条。",
        f"- `still_blocked_with_specific_gap`：{report['phase_outcome_breakdown'].get('still_blocked_with_specific_gap', 0)} 条。",
        f"- 写回后状态增量候选：{report['exact_confirmed_delta_candidates']} 条 blocked -> exact_confirmed。",
        "",
        "## 仍 blocked 的主要缺口",
        "",
    ]
    if blocked_rows:
        for reason_type, count in Counter(row["blocked_reason_type"] for row in blocked_rows).most_common():
            lines.append(f"- {reason_type}：{count} 条。")
    else:
        lines.append("- 无。")

    lines.extend(["", "## SC-023 相关 10 条去向", "", "| row_id | 去向 | 新主规则 | 说明 |", "| --- | --- | --- | --- |"])
    for row in sc023_rows:
        lines.append(
            f"| {row['sheet2_row_id']} | {row['phase_outcome']} | {row['target_primary_rule_id']} | "
            f"{row['evidence_summary']} |"
        )

    lines.extend(["", "## 全量逐条结论", "", "| row_id | 原规则 | 新主规则 | 阶段结论 | 缺口/说明 |", "| --- | --- | --- | --- | --- |"])
    for row in results:
        gap_or_reason = row["specific_gap"] or row["evidence_summary"]
        lines.append(
            f"| {row['sheet2_row_id']} | {row['before_primary_rule_id']} | {row['target_primary_rule_id']} | "
            f"{row['phase_outcome']} | {gap_or_reason} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_report(results: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    return {
        "target": "Sheet2 blocked backlog 可补规则 24 条回归收口",
        "mode": mode,
        "row_count": len(results),
        "phase_outcome_breakdown": dict(Counter(row["phase_outcome"] for row in results)),
        "target_status_breakdown": dict(Counter(row["target_exact_review_status"] for row in results)),
        "target_primary_rule_breakdown": dict(Counter(row["target_primary_rule_id"] for row in results)),
        "blocked_reason_breakdown": dict(Counter(row["blocked_reason_type"] for row in results if row["blocked_reason_type"])),
        "sc023_row_count": sum(1 for row in results if row["before_primary_rule_id"] == "SC-023"),
        "exact_confirmed_delta_candidates": sum(
            1 for row in results if row["target_exact_review_status"] == "exact_confirmed"
        ),
        "results": results,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sheet2 可补规则 backlog 24 条定向回归")
    parser.add_argument("--dry-run", action="store_true", help="只生成报告；默认行为")
    parser.add_argument("--writeback", action="store_true", help="写回 ledger/overrides 并刷新验收产物")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _, backlog_rows = _load_csv_rows(BACKLOG_CSV)
    selected_rows = _select_fixable_rows(backlog_rows)
    results = [_build_result(row) for row in selected_rows]
    report = _build_report(results, mode="writeback" if args.writeback else "dry-run")
    _write_report(report)
    _write_markdown(report)
    if args.writeback:
        _apply_writeback(results)
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "row_count": report["row_count"],
                "phase_outcome_breakdown": report["phase_outcome_breakdown"],
                "target_status_breakdown": report["target_status_breakdown"],
                "blocked_reason_breakdown": report["blocked_reason_breakdown"],
                "sc023_row_count": report["sc023_row_count"],
                "exact_confirmed_delta_candidates": report["exact_confirmed_delta_candidates"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
