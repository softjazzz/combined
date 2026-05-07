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
REPORT_CSV = QC_DIR / "sheet2_fixable_12_rule_replay_report.csv"
REPORT_JSON = QC_DIR / "sheet2_fixable_12_rule_replay_report.json"
REPORT_MD = QC_DIR / "2026-05-08-Sheet2可补规则12条定向重放收口.md"

TARGET_CATEGORY = "可补规则"
REPORT_FIELDS = [
    "sheet2_row_id",
    "source_bucket",
    "visit_id",
    "patient_name",
    "primary_rule_id",
    "issue_family",
    "manual_issue_text",
    "target_exact_review_status",
    "target_blocked_reason_type",
    "target_backlog_category",
    "target_primary_rule_id",
    "target_secondary_rule_ids",
    "phase_outcome",
    "evidence_sources",
    "anchor_hits",
    "anchor_misses",
    "evidence_summary",
    "next_action",
]


DECISIONS: dict[str, dict[str, Any]] = {
    "Sheet2-R0066": {
        "status": "blocked_with_reason",
        "blocked_reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "target_primary_rule_id": "SC-020",
        "target_secondary_rule_ids": "SC-023",
        "phase_outcome": "source_text_conflict_keep_blocked",
        "markers": ["房颤", "心率", "脉搏", "初步诊断"],
        "reason": "当前可复原入院诊断未见房颤诊断，查体心率/脉搏记录一致；首次病程正文在本机链路仍为空，不能证明人工所称房颤/首程鉴别诊断缺陷成立。",
        "next_action": "如客户坚持此项，需提供首次病程原文和心电/诊断依据截图后再拆为 SC-020+SC-023。",
    },
    "Sheet2-R0073": {
        "status": "blocked_with_reason",
        "blocked_reason_type": "证据链不足",
        "backlog_category": "需补源文书",
        "target_primary_rule_id": "SC-023",
        "target_secondary_rule_ids": "SC-018|SC-036",
        "phase_outcome": "move_back_to_evidence_gap",
        "markers": ["151/121", "BP", "首次病程", "诊疗计划"],
        "reason": "本机样本验证链路未复原首次病程正文，且当前可见文书未出现 BP151/121mmHg 锚点；不能核准首程缺分析/缺计划。",
        "next_action": "待客户机刷新后的 first_course_record bundle 正文可读取后，再按 SC-023/SC-036 定向重放。",
    },
    "Sheet2-R0077": {
        "status": "blocked_with_reason",
        "blocked_reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "target_primary_rule_id": "SC-074",
        "target_secondary_rule_ids": "LX-018|SC-073",
        "phase_outcome": "source_text_conflict_keep_blocked",
        "markers": ["2025年10月29日 04:49", "22:10开始输入", "01:02输注完毕"],
        "reason": "release 输血记录显示末次输注 2025-10-29 01:02 完毕，医师签名日期 2025-10-29 04:49，未支持“评价时间早于输血时间”。",
        "next_action": "需客户提供其所称输血后评价记录截图或确认评价时间字段口径。",
    },
    "Sheet2-R0093": {
        "status": "blocked_with_reason",
        "blocked_reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "target_primary_rule_id": "SC-105",
        "target_secondary_rule_ids": "SC-097",
        "phase_outcome": "partial_anchor_conflict_keep_blocked",
        "markers": ["进食鸡肉", "鸡骨嵌顿", "鸭骨"],
        "reason": "release 手术/术后首程可见“鸡骨嵌顿”，入院记录为“进食鸡肉”；人工问题写“鸭骨”与当前原文不一致，只能确认同类前后描述差异，不能整条 exact。",
        "next_action": "需按“鸡肉/鸡骨/异物”重新确认人工锚点后，再补 SC-105/SC-097 一致性规则。",
    },
    "Sheet2-R0098": {
        "status": "blocked_with_reason",
        "blocked_reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "target_primary_rule_id": "SC-023",
        "target_secondary_rule_ids": "SC-024|SC-025",
        "phase_outcome": "source_text_conflict_keep_blocked",
        "markers": ["霍乱", "细菌性痢疾", "乙肝两对半"],
        "reason": "可复原查房记录已写细菌性痢疾鉴别，且已记录乙肝两对半阴性；人工称“仅和霍乱鉴别/建议两对半”与原文不匹配。",
        "next_action": "需客户确认是否还有另一份首次病程原文；否则按原文冲突保留 blocked。",
    },
    "Sheet2-R0108": {
        "status": "blocked_with_reason",
        "blocked_reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "target_primary_rule_id": "LX-018",
        "target_secondary_rule_ids": "SC-049|SC-050|SC-073|SC-074",
        "phase_outcome": "source_text_conflict_keep_blocked",
        "markers": ["田安琴主治医师", "2025年11月17日 15:10", "2025年11月18日 17:25"],
        "reason": "当前可见田安琴主治医师查房记录有正文，release 也有 11月17日、11月18日输血记录；人工称查房无内容且无输血记录链，不能整条成立。",
        "next_action": "如仍认为缺输血前/后评估，需补输血评估专表或确认该院以输血记录内评价作为闭环的口径。",
    },
    "Sheet2-R0117": {
        "status": "blocked_with_reason",
        "blocked_reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "target_primary_rule_id": "SC-033",
        "target_secondary_rule_ids": "SC-023",
        "phase_outcome": "source_text_conflict_keep_blocked",
        "markers": ["徐应福主治医师", "血精", "精囊结石", "精囊结核"],
        "reason": "当前可见徐应福主治医师查房记录；首次病程正文未复原，且未见人工所称精囊结石/精囊结核原句，不能证明“48小时无主治查房+首程鉴别不全”整条成立。",
        "next_action": "需客户提供首次病程鉴别诊断原文，并单独核查入院48小时查房时效。",
    },
    "Sheet2-R0132": {
        "status": "blocked_with_reason",
        "blocked_reason_type": "证据链不足",
        "backlog_category": "需补源文书",
        "target_primary_rule_id": "SC-023",
        "target_secondary_rule_ids": "SC-036",
        "phase_outcome": "move_back_to_evidence_gap",
        "markers": ["云南白药", "酚磺乙胺", "多饮水", "抗血小板"],
        "reason": "本机样本验证链路未复原首次病程正文，未命中云南白药/酚磺乙胺/多饮水/抗血小板等人工核心原句。",
        "next_action": "待 first_course_record 正文可读取后，按首程诊疗计划前后矛盾定向重放。",
    },
    "Sheet2-R0172": {
        "status": "blocked_with_reason",
        "blocked_reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "target_primary_rule_id": "LX-020",
        "target_secondary_rule_ids": "SC-083|SC-096|SC-105",
        "phase_outcome": "source_text_conflict_keep_blocked",
        "markers": ["手术时间:2026年02月04日 12:45", "膀胱镜检查", "手术记录"],
        "reason": "release 可见 2026-02-04 手术记录和术后首次病程记录，人工称无术后首次病程及手术记录与当前原文冲突；术前主刀查房仍需单独时效核查。",
        "next_action": "如客户关注术前主刀查房，应拆为单锚点 LX-020/SC-086 时效核查。",
    },
    "Sheet2-R0220": {
        "status": "blocked_with_reason",
        "blocked_reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "target_primary_rule_id": "SC-069",
        "target_secondary_rule_ids": "LX-016|SC-146|SC-046",
        "phase_outcome": "partial_effective_keep_blocked",
        "markers": ["拒绝康复治疗", "超声波", "电刺激", "清创"],
        "reason": "会诊拒绝康复后仍有康复治疗锚点可部分成立，但清创术无操作记录与当前清创/手术摘要冲突，且 BP163 未复测处理属于另一病程/生命体征质控点，不能按可补单规则 exact。",
        "next_action": "拆为会诊执行/医嘱一致性、血压处置、清创记录三条后分别回归。",
    },
    "Sheet2-R0242": {
        "status": "exact_confirmed",
        "blocked_reason_type": "",
        "backlog_category": "",
        "target_primary_rule_id": "SC-036",
        "target_secondary_rule_ids": "SC-032",
        "phase_outcome": "exact_confirmed",
        "markers": ["Cl 113.3mmol/l", "肾功4", "治疗上继续予以"],
        "reason": "术后主治查房记录列出 2026-03-13 肾功异常 Cl 113.3mmol/l，但后续处理仅泛化写抗感染、解痉、止痛、补液，未对检验异常作专门分析，精确覆盖“病程记录对检验结果未分析”。",
        "next_action": "已 exact_confirmed。",
    },
    "Sheet2-R0265": {
        "status": "blocked_with_reason",
        "blocked_reason_type": "人工问题原文不可判",
        "backlog_category": "人工问题过宽/不可判",
        "target_primary_rule_id": "SC-036",
        "target_secondary_rule_ids": "SC-032",
        "phase_outcome": "source_text_conflict_keep_blocked",
        "markers": ["尿常规提示存在白细胞", "无尿频", "考虑膀胱结石", "头孢呋辛抗感染"],
        "reason": "当前首程/查房已分析尿常规白细胞：患者无尿路感染症状，考虑膀胱结石所致尿液异常，并有抗感染等处理；人工称未分析及处理与原文冲突。",
        "next_action": "如客户认为分析不足，需确认“分析深度”评价口径后再规则化。",
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
                    if _safe_text(row.get("visit_id")) != visit_id:
                        continue
                    chunks.append(f"[release:{path.stem}] " + " ".join(_safe_text(value) for value in row.values() if _safe_text(value)))
        except UnicodeDecodeError:
            continue
    return "\n".join(chunks)


def _bundle_text(visit_id: str) -> str:
    payload = get_documents(visit_id)
    chunks = []
    for doc in list((payload or {}).get("documents") or []):
        chunks.append(
            "[bundle:{source}] {title}\n{content}".format(
                source=_safe_text(doc.get("source_table")),
                title=_safe_text(doc.get("document_title") or doc.get("title")),
                content=_safe_text(doc.get("content")),
            )
        )
    return "\n".join(chunks)


def _snippet(text: str, marker: str, radius: int = 90) -> str:
    index = text.find(marker)
    if index < 0:
        return ""
    return _normalize(text[max(0, index - radius) : index + len(marker) + radius])


def _evaluate(row: dict[str, str], source_bucket: str) -> dict[str, str]:
    row_id = _safe_text(row.get("sheet2_row_id"))
    decision = DECISIONS[row_id]
    evidence_text = _bundle_text(_safe_text(row.get("visit_id"))) + "\n" + _release_text(_safe_text(row.get("visit_id")))
    hits = []
    misses = []
    snippets = []
    for marker in decision["markers"]:
        snippet = _snippet(evidence_text, marker)
        if snippet:
            hits.append(marker)
            snippets.append(f"{marker}: {snippet[:220]}")
        else:
            misses.append(marker)
    evidence_summary = decision["reason"]
    if snippets:
        evidence_summary += " 证据摘录：" + "；".join(snippets[:3])
    return {
        "sheet2_row_id": row_id,
        "source_bucket": source_bucket,
        "visit_id": _safe_text(row.get("visit_id")),
        "patient_name": _safe_text(row.get("patient_name")),
        "primary_rule_id": _safe_text(row.get("primary_rule_id")),
        "issue_family": _safe_text(row.get("issue_family")),
        "manual_issue_text": _safe_text(row.get("manual_issue_text")),
        "target_exact_review_status": decision["status"],
        "target_blocked_reason_type": decision["blocked_reason_type"],
        "target_backlog_category": decision["backlog_category"],
        "target_primary_rule_id": decision["target_primary_rule_id"],
        "target_secondary_rule_ids": decision["target_secondary_rule_ids"],
        "phase_outcome": decision["phase_outcome"],
        "evidence_sources": "sample_validation_bundle|release_0426_full_auto",
        "anchor_hits": "|".join(hits),
        "anchor_misses": "|".join(misses),
        "evidence_summary": evidence_summary,
        "next_action": decision["next_action"],
    }


def build_report() -> list[dict[str, str]]:
    _, backlog_rows = _load_csv(BACKLOG_CSV)
    _, matrix_rows = _load_csv(QC_DIR / "sheet2_exact_review_matrix.csv")
    source_report_ids = set()
    evidence_gap_report = QC_DIR / "sheet2_evidence_gap_backlog_recheck_report.csv"
    if evidence_gap_report.exists():
        _, rows = _load_csv(evidence_gap_report)
        source_report_ids = {
            row["sheet2_row_id"]
            for row in rows
            if row.get("coverage_status") == "evidence_chain_recovered"
        }
    row_by_id = {
        _safe_text(row.get("sheet2_row_id")): row
        for row in [*matrix_rows, *backlog_rows]
        if _safe_text(row.get("sheet2_row_id"))
    }
    current_targets = [row for row in backlog_rows if _safe_text(row.get("backlog_category")) == TARGET_CATEGORY]
    targets = current_targets or [row_by_id[row_id] for row_id in DECISIONS if row_id in row_by_id]
    target_ids = {_safe_text(row.get("sheet2_row_id")) for row in targets}
    if target_ids != set(DECISIONS):
        raise ValueError(f"可补规则 12 条与决策表不一致: actual={sorted(target_ids)}, expected={sorted(DECISIONS)}")
    return [
        _evaluate(row, "新迁入可补规则" if row["sheet2_row_id"] in source_report_ids else "原可补规则")
        for row in targets
    ]


def _merge_rows(path: Path, key: str, updates: dict[str, dict[str, str]], fields: list[str]) -> None:
    existing_fields, rows = _load_csv(path) if path.exists() else ([], [])
    output_fields = list(dict.fromkeys(existing_fields + fields))
    by_id = {_safe_text(row.get(key)): row for row in rows if _safe_text(row.get(key))}
    for row_id, update in updates.items():
        current = by_id.get(row_id, {key: row_id})
        current.update(update)
        by_id[row_id] = current
    ordered = []
    seen = set()
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
        "fixable_12_rule_replay_outcome",
        "fixable_12_rule_replay_reason",
        "fixable_12_rule_replay_anchor_hits",
        "fixable_12_rule_replay_anchor_misses",
    ]
    by_id = {_safe_text(row.get("sheet2_row_id")): row for row in rows}
    for result in results:
        row = by_id.get(result["sheet2_row_id"])
        if not row:
            continue
        row["primary_rule_id"] = result["target_primary_rule_id"] or row.get("primary_rule_id", "")
        row["secondary_rule_ids"] = result["target_secondary_rule_ids"] or row.get("secondary_rule_ids", "")
        row["evidence_summary"] = result["evidence_summary"]
        row["next_action"] = result["next_action"]
        row["fixable_12_rule_replay_outcome"] = result["phase_outcome"]
        row["fixable_12_rule_replay_reason"] = result["evidence_summary"]
        row["fixable_12_rule_replay_anchor_hits"] = result["anchor_hits"]
        row["fixable_12_rule_replay_anchor_misses"] = result["anchor_misses"]
    _write_csv(LEDGER_CSV, rows, list(dict.fromkeys(fields + added)))


def _writeback(results: list[dict[str, str]]) -> None:
    override_updates = {}
    backlog_updates = {}
    for result in results:
        row_id = result["sheet2_row_id"]
        override_updates[row_id] = {
            "sheet2_row_id": row_id,
            "exact_review_status": result["target_exact_review_status"],
            "exact_review_reason": result["evidence_summary"],
            "blocked_reason_type": result["target_blocked_reason_type"],
            "review_subgroup": f"可补规则12条重放-{result['phase_outcome']}",
            "decision_source": "sheet2_fixable_12_rule_replay_report",
        }
        if result["target_exact_review_status"] == "blocked_with_reason":
            backlog_updates[row_id] = {
                "sheet2_row_id": row_id,
                "backlog_category": result["target_backlog_category"],
                "backlog_reason": result["evidence_summary"],
                "next_action": result["next_action"],
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


def _write_reports(results: list[dict[str, str]], writeback: bool) -> None:
    _write_csv(REPORT_CSV, results, REPORT_FIELDS)
    summary = {
        "total": len(results),
        "writeback": writeback,
        "source_bucket_breakdown": dict(Counter(row["source_bucket"] for row in results)),
        "target_status_breakdown": dict(Counter(row["target_exact_review_status"] for row in results)),
        "target_backlog_breakdown": dict(Counter(row["target_backlog_category"] or "not_blocked" for row in results)),
        "blocked_to_exact_rows": [row for row in results if row["target_exact_review_status"] == "exact_confirmed"],
        "moved_from_fixable_rows": [
            row
            for row in results
            if row["target_exact_review_status"] == "blocked_with_reason"
            and row["target_backlog_category"] != TARGET_CATEGORY
        ],
        "still_fixable_rows": [
            row
            for row in results
            if row["target_exact_review_status"] == "blocked_with_reason"
            and row["target_backlog_category"] == TARGET_CATEGORY
        ],
    }
    REPORT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Sheet2 可补规则 12 条定向重放收口",
        "",
        "日期：2026-05-08",
        "",
        "## 结论",
        "",
        f"- 本轮处理 `backlog_category=可补规则`：{len(results)} 条。",
        f"- blocked -> exact_confirmed：{len(summary['blocked_to_exact_rows'])} 条。",
        f"- 可补规则 -> 其他 blocked 分类：{len(summary['moved_from_fixable_rows'])} 条。",
        f"- 仍可补规则：{len(summary['still_fixable_rows'])} 条。",
        "- 本轮没有把 partial/effective 包装为 pure exact。",
        "",
        "## 逐条去向",
        "",
        "| row | 来源 | 结论 | 去向 | 说明 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in results:
        target = row["target_backlog_category"] or "exact_confirmed"
        lines.append(
            f"| {row['sheet2_row_id']} | {row['source_bucket']} | {row['phase_outcome']} | {target} | {row['evidence_summary']} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sheet2 可补规则 12 条客户样本验证链路定向重放")
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
                "target_status_breakdown": dict(Counter(row["target_exact_review_status"] for row in results)),
                "target_backlog_breakdown": dict(Counter(row["target_backlog_category"] or "not_blocked" for row in results)),
                "writeback": args.writeback,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
