from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0508"
INPUT_JSON = DOCS_DIR / "formal_qc_aliyun_bailian_10_visit_after_evidence_enrichment_issue_review.json"
OUTPUT_CSV = DOCS_DIR / "formal_qc_implant_pathology_applicability_review.csv"
OUTPUT_JSON = DOCS_DIR / "formal_qc_implant_pathology_applicability_review.json"
OUTPUT_MD = DOCS_DIR / "正式质控SC099-SC100-SC101适用性修复报告.md"

TARGET_RULE_IDS = {"SC-099", "SC-100", "SC-101"}
SPECIMEN_TERMS = ("术中取材", "取材", "送病理", "送病检", "快速病理", "冰冻", "活检", "标本", "骨髓穿刺")
IMPLANT_TERMS = ("植入物", "植入", "内固定", "螺钉", "连接棒", "钢板", "骨水泥", "支架", "假体", "融合器", "钉棒")
BARCODE_TERMS = ("条形码", "条码", "追溯码", "UDI", "标签", "唯一标识")
QUANTITY_TERMS = ("枚", "根", "套", "支", "个", "ml", "ML", "数量", "剂量")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _record_time_only(text: str) -> bool:
    stripped = "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
    return stripped in {"当前文书记录时间", "记录时间", "文书记录时间"} or stripped.endswith("记录时间")


def _review_item(item: dict[str, Any]) -> dict[str, Any]:
    rule_id = _safe_text(item.get("rule_id"))
    evidence = _safe_text(item.get("evidence"))
    quote = _safe_text(item.get("adjudicator_supporting_quote"))
    evidence_text = "\n".join([evidence, quote])
    has_specimen_trigger = _contains(evidence_text, SPECIMEN_TERMS)
    has_implant_trigger = _contains(evidence_text, IMPLANT_TERMS)
    has_implant_barcode = _contains(evidence_text, BARCODE_TERMS)
    has_implant_quantity = _contains(evidence_text, QUANTITY_TERMS)
    weak_record_time = _record_time_only(evidence) or _record_time_only(quote)

    expected_status = _safe_text(item.get("display_status"))
    reason = "既有分流保持。"
    if rule_id == "SC-099":
        if expected_status == "confirmed_defect" and not has_specimen_trigger:
            expected_status = "rejected_by_system"
            reason = "未见术中取材/送病理/活检/标本等适用触发证据，SC-099 不应泛化到所有手术。"
        elif _safe_text(item.get("display_status")) == "confirmed_defect" and weak_record_time:
            expected_status = "data_quality_gap"
            reason = "仅记录时间不能支撑取材/病理缺陷，需要病理来源或取材触发片段对照。"
        elif weak_record_time:
            reason = "既有分流未作为确认缺陷；当前导出证据仍只有记录时间，正式链路需依赖新增取材/病理 flags 防止误确认。"
    elif rule_id == "SC-100":
        if expected_status == "confirmed_defect" and not has_implant_trigger:
            expected_status = "rejected_by_system"
            reason = "未见植入物触发证据，SC-100 不适用。"
        elif not has_implant_barcode:
            expected_status = "data_quality_gap"
            reason = (
                "缺少条码/追溯码来源域，不能直接确认为医生缺陷。"
                if has_implant_trigger
                else "既有分流未作为确认缺陷；当前导出证据未包含植入物原文，正式链路需依赖新增植入物 flags。"
            )
    elif rule_id == "SC-101":
        if expected_status == "confirmed_defect" and not has_implant_trigger:
            expected_status = "rejected_by_system"
            reason = "未见植入物触发证据，SC-101 不适用。"
        elif expected_status == "confirmed_defect" and has_implant_quantity:
            expected_status = "data_quality_gap"
            reason = "已见植入物种类或数量/剂量片段，属于部分记录，需完整对照后再判定。"
        elif weak_record_time:
            expected_status = "data_quality_gap"
            reason = "仅记录时间不能支撑植入物种类和数量未记录。"

    return {
        "job_id": _safe_text(item.get("job_id")),
        "visit_id": _safe_text(item.get("visit_id")),
        "patient_name": _safe_text(item.get("patient_name")),
        "department": _safe_text(item.get("department")),
        "rule_id": rule_id,
        "rule_name": _safe_text(item.get("rule_name")),
        "old_display_status": _safe_text(item.get("display_status")),
        "expected_display_status_after_fix": expected_status,
        "status_changed_by_applicability_review": expected_status != _safe_text(item.get("display_status")),
        "has_specimen_or_pathology_trigger": has_specimen_trigger,
        "has_implant_trigger": has_implant_trigger,
        "has_implant_barcode_source": has_implant_barcode,
        "has_implant_quantity_or_detail": has_implant_quantity,
        "weak_record_time_only_evidence": weak_record_time,
        "evidence": evidence,
        "adjudicator_reason": _safe_text(item.get("adjudicator_reason")),
        "adjudicator_supporting_quote": quote,
        "review_reason": reason,
    }


def main() -> None:
    payload = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    issues = payload.get("issues") if isinstance(payload, dict) else payload
    rows = [_review_item(item) for item in issues if _safe_text(item.get("rule_id")) in TARGET_RULE_IDS]

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    old_counts = Counter(row["old_display_status"] for row in rows)
    next_counts = Counter(row["expected_display_status_after_fix"] for row in rows)
    result = {
        "input": str(INPUT_JSON.relative_to(ROOT)),
        "total_target_items": len(rows),
        "old_display_status_counts": dict(old_counts),
        "expected_display_status_counts_after_fix": dict(next_counts),
        "changed_count": sum(1 for row in rows if row["status_changed_by_applicability_review"]),
        "rows": rows,
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    leidechao_rows = [row for row in rows if row["visit_id"] == "1915580"]
    md = [
        "# 正式质控 SC-099/SC-100/SC-101 适用性修复报告",
        "",
        "## 修复范围",
        "- SC-099 增加取材/送病理/活检/标本等适用触发判断，避免泛化到所有手术。",
        "- SC-100 增加植入物触发与条码/追溯码来源域判断，缺来源时进入数据缺口。",
        "- SC-101 增加植入物详情完整性判断，已有部分种类/数量记录时不得直接确认“未记录”。",
        "",
        "## 10 病历既有输出只读复核",
        f"- 复核目标条目：{len(rows)}",
        f"- 修复前分布：{dict(old_counts)}",
        f"- 适用性修复后预期分布：{dict(next_counts)}",
        f"- 预期分流变化条数：{sum(1 for row in rows if row['status_changed_by_applicability_review'])}",
        "",
        "## 1915580 雷德超专项验证",
    ]
    for row in leidechao_rows:
        md.append(
            f"- {row['rule_id']}：修复前 {row['old_display_status']}，"
            f"修复后预期 {row['expected_display_status_after_fix']}；{row['review_reason']}"
        )
    md.extend(
        [
            "",
            "## 验收结论",
            "- 页面不应把仅有“记录时间”的 SC-099/SC-100/SC-101 展示为确认缺陷。",
            "- SC-099 无取材/病理触发时应系统驳回；有触发但缺病理来源时应数据缺口。",
            "- SC-100 有植入物但缺条码/耗材来源时应数据缺口。",
            "- SC-101 已有植入物种类/数量片段时属于部分记录，不得直接确认“未记录”。",
        ]
    )
    OUTPUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
