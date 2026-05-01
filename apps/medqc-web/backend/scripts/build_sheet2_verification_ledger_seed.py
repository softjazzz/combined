#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[4]
SOURCE_XLS = REPO_ROOT / "docs" / "运行病历质控记录.xls"
MAPPING_CSV = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC" / "sheet2_rule_mapping_seed.csv"
OUTPUT_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
OUTPUT_CSV = OUTPUT_DIR / "sheet2_verification_ledger_seed.csv"
OUTPUT_JSON = OUTPUT_DIR / "sheet2_verification_ledger_seed.summary.json"
VISIT_TEMPLATE_CANDIDATES = (
    REPO_ROOT / "apps" / "medqc-web" / "visit_id_only_template_from_sheet2_运行病历质控记录.xlsx",
    REPO_ROOT / "apps" / "medqc-web" / "visit_id_only_template_from_sheet2.xlsx",
)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if pd.isna(value):
            return ""
        if value.is_integer():
            return str(int(value))
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    return text


def _normalize_issue_text(value: Any) -> str:
    text = _safe_text(value).replace("\u3000", " ")
    return re.sub(r"\s+", " ", text)


def _detect_header_index(dataframe: pd.DataFrame, known_headers: set[str]) -> int:
    header_index = 0
    for index in range(min(len(dataframe.index), 3)):
        row_headers = {_safe_text(item) for item in dataframe.iloc[index].tolist() if _safe_text(item)}
        if row_headers & known_headers:
            header_index = index
            break
    return header_index


def _load_sheet2_rows() -> list[dict[str, str]]:
    dataframe = pd.read_excel(SOURCE_XLS, sheet_name="Sheet2", header=None)
    if dataframe.empty:
        return []

    header_index = _detect_header_index(
        dataframe,
        {"科室", "患者姓名", "住院号", "visit_id", "VisitID", "VISIT_ID", "存在问题", "责任医生", "质控日期", "质控人员"},
    )
    header_row = [_safe_text(item) for item in dataframe.iloc[header_index].tolist()]
    data = dataframe.iloc[header_index + 1 :].copy()
    data.columns = header_row

    rows: list[dict[str, str]] = []
    for row_no, raw in enumerate(data.to_dict(orient="records"), start=header_index + 2):
        patient_name = _safe_text(raw.get("患者姓名"))
        manual_issue_text = _normalize_issue_text(raw.get("存在问题"))
        mr_no = _safe_text(raw.get("住院号"))
        visit_id = _safe_text(raw.get("visit_id") or raw.get("VisitID") or raw.get("VISIT_ID"))
        if not patient_name and not manual_issue_text and not mr_no and not visit_id:
            continue
        rows.append(
            {
                "sheet2_row_id": f"Sheet2-R{row_no:04d}",
                "visit_id": visit_id,
                "patient_name": patient_name,
                "manual_issue_text": manual_issue_text,
                "mr_no": mr_no,
            }
        )
    return rows


def _load_issue_mapping() -> dict[str, dict[str, str]]:
    with MAPPING_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return {
            _normalize_issue_text(row.get("sheet2_issue_text")): {
                "issue_family": _safe_text(row.get("normalized_issue_family")) or "待人工归类",
                "candidate_rule_ids": _safe_text(row.get("candidate_rule_ids")),
                "current_status": _safe_text(row.get("current_status")),
            }
            for row in reader
            if _normalize_issue_text(row.get("sheet2_issue_text"))
        }


def _load_visit_template_rows(file_path: Path) -> list[dict[str, str]]:
    dataframe = pd.read_excel(file_path, header=None)
    if dataframe.empty:
        return []

    header_index = _detect_header_index(dataframe, {"visit_id", "VisitID", "VISIT_ID", "存在问题"})
    header_row = [_safe_text(item) for item in dataframe.iloc[header_index].tolist()]
    data = dataframe.iloc[header_index + 1 :].copy()
    data.columns = header_row

    rows: list[dict[str, str]] = []
    for raw in data.to_dict(orient="records"):
        issue_text = _normalize_issue_text(raw.get("存在问题"))
        visit_id = _safe_text(raw.get("visit_id") or raw.get("VisitID") or raw.get("VISIT_ID"))
        if not issue_text and not visit_id:
            continue
        rows.append({"manual_issue_text": issue_text, "visit_id": visit_id})
    return rows


def _apply_visit_template(base_rows: list[dict[str, str]]) -> str:
    if all(row["visit_id"] for row in base_rows):
        return "source_excel"

    for candidate in VISIT_TEMPLATE_CANDIDATES:
        if not candidate.exists():
            continue
        template_rows = _load_visit_template_rows(candidate)
        if not template_rows:
            continue

        base_issue_sequence = [row["manual_issue_text"] for row in base_rows]
        template_issue_sequence = [row["manual_issue_text"] for row in template_rows]

        if len(template_rows) == len(base_rows) and template_issue_sequence == base_issue_sequence:
            for base_row, template_row in zip(base_rows, template_rows):
                if not base_row["visit_id"]:
                    base_row["visit_id"] = template_row["visit_id"]
            return str(candidate)

        issue_to_visit_ids: dict[str, list[str]] = defaultdict(list)
        for template_row in template_rows:
            issue_to_visit_ids[template_row["manual_issue_text"]].append(template_row["visit_id"])

        issue_offsets: dict[str, int] = defaultdict(int)
        for base_row in base_rows:
            issue_text = base_row["manual_issue_text"]
            offset = issue_offsets[issue_text]
            visit_ids = issue_to_visit_ids.get(issue_text) or []
            if not base_row["visit_id"] and offset < len(visit_ids):
                base_row["visit_id"] = visit_ids[offset]
            issue_offsets[issue_text] += 1
        return str(candidate)

    return "missing"


def _split_rule_ids(raw_rule_ids: str) -> list[str]:
    return [rule_id.strip() for rule_id in raw_rule_ids.split("|") if rule_id.strip()]


def _derive_next_action(
    *,
    visit_id: str,
    manual_issue_text: str,
    issue_family: str,
    primary_rule_id: str,
    current_status: str,
) -> str:
    if not manual_issue_text:
        return "先补人工问题原文"
    if not visit_id:
        return "先补visit_id并绑定目标病历"
    if not primary_rule_id or issue_family == "待人工归类":
        return "先人工归类问题并补主规则"
    if current_status in {"implemented", "ready_in_rule_library"}:
        return "按主规则做真实核验"
    if current_status == "partial":
        return "先跑现有规则并记录缺口"
    if current_status == "todo_programmatic":
        return "先核现有证据，再补程序规则"
    if current_status == "todo_semantic":
        return "先核现有证据，再补语义规则"
    if current_status == "deferred_data_gap":
        return "先核原始文书是否缺失，再判定是否skip"
    return "先人工归类问题并补主规则"


def _build_ledger_rows(
    base_rows: list[dict[str, str]],
    issue_mapping: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    ledger_rows: list[dict[str, str]] = []
    for base_row in base_rows:
        mapping = issue_mapping.get(base_row["manual_issue_text"], {})
        issue_family = _safe_text(mapping.get("issue_family")) or "待人工归类"
        candidate_rule_ids = _split_rule_ids(_safe_text(mapping.get("candidate_rule_ids")))
        primary_rule_id = candidate_rule_ids[0] if candidate_rule_ids else ""
        secondary_rule_ids = "|".join(candidate_rule_ids[1:])
        current_status = _safe_text(mapping.get("current_status"))
        ledger_rows.append(
            {
                "sheet2_row_id": base_row["sheet2_row_id"],
                "visit_id": base_row["visit_id"],
                "patient_name": base_row["patient_name"],
                "manual_issue_text": base_row["manual_issue_text"],
                "issue_family": issue_family,
                "primary_rule_id": primary_rule_id,
                "secondary_rule_ids": secondary_rule_ids,
                "verification_status": "pending",
                "skip_reason": "",
                "next_action": _derive_next_action(
                    visit_id=base_row["visit_id"],
                    manual_issue_text=base_row["manual_issue_text"],
                    issue_family=issue_family,
                    primary_rule_id=primary_rule_id,
                    current_status=current_status,
                ),
            }
        )
    return ledger_rows


def _write_csv(rows: list[dict[str, str]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sheet2_row_id",
        "visit_id",
        "patient_name",
        "manual_issue_text",
        "issue_family",
        "primary_rule_id",
        "secondary_rule_ids",
        "verification_status",
        "skip_reason",
        "next_action",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_summary(rows: list[dict[str, str]], *, visit_id_source: str) -> None:
    summary = {
        "source_excel": str(SOURCE_XLS),
        "mapping_csv": str(MAPPING_CSV),
        "visit_id_source": visit_id_source,
        "output_csv": str(OUTPUT_CSV),
        "row_count": len(rows),
        "blank_manual_issue_text_count": sum(1 for row in rows if not row["manual_issue_text"]),
        "visit_id_filled_count": sum(1 for row in rows if row["visit_id"]),
        "visit_id_missing_count": sum(1 for row in rows if not row["visit_id"]),
        "primary_rule_missing_count": sum(1 for row in rows if not row["primary_rule_id"]),
        "issue_family_breakdown": dict(Counter(row["issue_family"] for row in rows)),
        "next_action_breakdown": dict(Counter(row["next_action"] for row in rows)),
    }
    OUTPUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def main() -> int:
    base_rows = _load_sheet2_rows()
    if not base_rows:
        raise SystemExit("未读取到有效 Sheet2 行")

    issue_mapping = _load_issue_mapping()
    visit_id_source = _apply_visit_template(base_rows)
    ledger_rows = _build_ledger_rows(base_rows, issue_mapping)
    _write_csv(ledger_rows)
    _write_summary(ledger_rows, visit_id_source=visit_id_source)

    print(f"rows={len(ledger_rows)}")
    print(f"csv={OUTPUT_CSV}")
    print(f"summary={OUTPUT_JSON}")
    print(f"visit_id_source={visit_id_source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
