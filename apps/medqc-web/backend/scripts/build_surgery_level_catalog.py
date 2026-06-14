#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(BACKEND_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from run_formal_qc_three_visit_adjudicated_audit import _load_visit_keys  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
OUTPUT_DIR = DOCS_DIR / "surgery_level_catalog"
DEFAULT_SOURCE_PDF = DOCS_DIR / "三四级手术目录.pdf"

CATALOG_CSV = OUTPUT_DIR / "surgery_level_catalog.csv"
CATALOG_JSON = OUTPUT_DIR / "surgery_level_catalog.json"
NEEDS_REVIEW_CSV = OUTPUT_DIR / "surgery_level_catalog_needs_review.csv"
QUALITY_JSON = OUTPUT_DIR / "surgery_level_catalog_quality_report.json"
REPORT_MD = OUTPUT_DIR / "手术分级目录结构化转换报告.md"
MATCH_PROBE_CSV = OUTPUT_DIR / "surgery_level_catalog_match_probe.csv"
MATCH_PROBE_JSON = OUTPUT_DIR / "surgery_level_catalog_match_probe.json"

SEARCH_ROOTS = [
    REPO_ROOT / "apps" / "medqc-web" / "docs",
    REPO_ROOT / "docs",
    REPO_ROOT / "release",
    BACKEND_ROOT / "data",
    BACKEND_ROOT / "resources",
    BACKEND_ROOT / "rules",
    BACKEND_ROOT,
]
PDF_NAME_PATTERN = re.compile(r"手术分级|四级手术|手术目录|surgery|operation|procedure|分级目录|手术", re.IGNORECASE)
LEVEL_PATTERN = re.compile(r"([一二三四1234])\s*级")
SURGERY_NAME_PATTERNS = [
    re.compile(r"(?:手术名称|拟行手术|手术方式|术式|手术及操作名称)\s*[:：]\s*([^\n\r；;。]+)"),
    re.compile(r"(?:行|拟行)([^，,。；;\n\r]{2,60}(?:术|置入|置换|内固定|切除|成形|吻合|修补|取出))"),
]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _safe_text(value))
    text = re.sub(r"[\s　]+", "", text)
    text = re.sub(r"[，,。；;：:、/\\（）()\[\]【】<>《》\"'“”‘’·]", "", text)
    text = text.upper()
    # Only remove redundant long suffixes. Do not strip the common "术" suffix because it is often distinctive.
    text = re.sub(r"(手术)$", "术", text)
    return text


def _standardize_level(value: Any) -> str:
    text = _safe_text(value)
    match = LEVEL_PATTERN.search(text)
    if not match:
        return ""
    raw = match.group(1)
    return {"一": "1", "二": "2", "三": "3", "四": "4"}.get(raw, raw)


def _alias_from_name(name: str) -> str:
    aliases: list[str] = []
    for match in re.finditer(r"[\[（(]([^\]）)]+)[\]）)]", name):
        value = match.group(1).strip()
        if value and value not in aliases:
            aliases.append(value)
    for sep in ("/", "、"):
        if sep in name:
            for part in name.split(sep):
                value = part.strip()
                if value and value != name and value not in aliases:
                    aliases.append(value)
    return "|".join(aliases)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _pdf_page_count(path: Path) -> tuple[int, bool]:
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            has_text = any(bool((page.extract_text() or "").strip()) for page in pdf.pages[: min(3, len(pdf.pages))])
            return len(pdf.pages), has_text
    except Exception:
        return 0, False


def _find_pdf_candidates() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.pdf"):
            if path in seen:
                continue
            seen.add(path)
            if not (PDF_NAME_PATTERN.search(path.name) or PDF_NAME_PATTERN.search(str(path))):
                continue
            pages, has_text = _pdf_page_count(path)
            score = 0
            name = path.name.lower()
            if "三四级" in path.name or "四级" in path.name:
                score += 5
            if "目录" in path.name or "分级" in path.name:
                score += 4
            if pages:
                score += min(5, pages // 10)
            candidates.append(
                {
                    "path": str(path),
                    "size_bytes": path.stat().st_size,
                    "page_count": pages,
                    "modified_time": datetime.fromtimestamp(path.stat().st_mtime).isoformat(sep=" ", timespec="seconds"),
                    "has_text_layer": has_text,
                    "selection_score": score,
                    "name": name,
                }
            )
    return sorted(candidates, key=lambda row: (-int(row["selection_score"]), row["path"]))


def _extract_catalog(source_pdf: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import pdfplumber

    rows: list[dict[str, Any]] = []
    raw_line_count = 0
    table_count = 0
    with pdfplumber.open(source_pdf) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            raw_line_count += len([line for line in page_text.splitlines() if line.strip()])
            tables = page.extract_tables() or []
            table_count += len(tables)
            for table in tables:
                if not table:
                    continue
                header = [_safe_text(item) for item in table[0]]
                for raw_row in table[1:]:
                    if not raw_row or not any(_safe_text(item) for item in raw_row):
                        continue
                    cells = [_safe_text(item).replace("\n", "") for item in raw_row]
                    if cells and cells[0] in {"序号", "编号"}:
                        continue
                    raw_text = " ".join(cell for cell in cells if cell)
                    surgery_code = cells[1] if len(cells) > 1 else ""
                    surgery_name = cells[2] if len(cells) > 2 else ""
                    raw_level = cells[3] if len(cells) > 3 else ""
                    level = _standardize_level(raw_level)
                    review_status = "ok" if surgery_name and level else "needs_review"
                    rows.append(
                        {
                            "catalog_id": f"{source_pdf.stem}-{len(rows)+1:05d}",
                            "source_file": str(source_pdf.relative_to(REPO_ROOT)) if source_pdf.is_relative_to(REPO_ROOT) else str(source_pdf),
                            "source_page": page_index,
                            "raw_row_text": raw_text,
                            "department": "",
                            "specialty": "",
                            "surgery_code": surgery_code,
                            "surgery_name": surgery_name,
                            "normalized_name": _normalize_name(surgery_name),
                            "surgery_level": level,
                            "alias": _alias_from_name(surgery_name),
                            "confidence": 0.98 if review_status == "ok" else 0.35,
                            "extraction_method": "pdfplumber_table",
                            "review_status": review_status,
                            "notes": "" if review_status == "ok" else f"列解析不完整；header={header}",
                        }
                    )
    metadata = {"raw_line_count": raw_line_count, "table_count": table_count}
    return rows, metadata


def _quality_report(rows: list[dict[str, Any]], *, source_pdf: Path, candidates: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    normalized_to_levels: dict[str, set[str]] = defaultdict(set)
    normalized_counts: Counter[str] = Counter()
    for row in rows:
        name = _safe_text(row.get("normalized_name"))
        if name:
            normalized_counts[name] += 1
            if row.get("surgery_level"):
                normalized_to_levels[name].add(_safe_text(row.get("surgery_level")))
    duplicates = {name: count for name, count in normalized_counts.items() if count > 1}
    conflicts = {
        name: sorted(levels)
        for name, levels in normalized_to_levels.items()
        if len(levels) > 1
    }
    level_counts = Counter(_safe_text(row.get("surgery_level")) or "empty" for row in rows)
    level4_rows = [row for row in rows if row.get("surgery_level") == "4"]
    non_level4_rows = [row for row in rows if row.get("surgery_level") and row.get("surgery_level") != "4"]
    needs_review = [row for row in rows if row.get("review_status") == "needs_review"]
    return {
        "source_file": str(source_pdf),
        "source_file_size_bytes": source_pdf.stat().st_size if source_pdf.exists() else 0,
        "pdf_candidates": candidates,
        "extraction_metadata": metadata,
        "total_rows": len(rows),
        "recognizable_level_rows": sum(1 for row in rows if row.get("surgery_level")),
        "level_counts": dict(level_counts),
        "level_4_rows": len(level4_rows),
        "empty_surgery_name_rows": sum(1 for row in rows if not row.get("surgery_name")),
        "normalized_name_duplicate_count": len(duplicates),
        "normalized_name_duplicate_examples": dict(list(duplicates.items())[:30]),
        "normalized_name_level_conflict_count": len(conflicts),
        "normalized_name_level_conflicts": dict(list(conflicts.items())[:30]),
        "needs_review_rows": len(needs_review),
        "level4_sample_30": level4_rows[:30],
        "non_level4_sample_30": non_level4_rows[:30],
        "quality_flags": [
            flag
            for flag, active in {
                "needs_review_rows_present": bool(needs_review),
                "normalized_name_duplicates_present": bool(duplicates),
                "normalized_name_level_conflicts_present": bool(conflicts),
            }.items()
            if active
        ],
    }


def _extract_surgery_names_from_text(text: str) -> list[str]:
    names: list[str] = []
    for pattern in SURGERY_NAME_PATTERNS:
        for match in pattern.finditer(text or ""):
            value = re.sub(r"\s+", "", match.group(1)).strip("，,。；;：:")
            if 2 <= len(value) <= 80 and value not in names:
                names.append(value)
    return names


def _extract_visit_surgery_names(visit_id: str) -> tuple[dict[str, str], list[str]]:
    visit_keys = _load_visit_keys()
    visit_row = visit_keys.get(visit_id) or {}
    patient_id = _safe_text(visit_row.get("patient_id"))
    institute_id = _safe_text(visit_row.get("institute_id"))
    names: list[str] = []
    if patient_id and institute_id:
        try:
            bundle = assemble_final_record_bundle(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema="cdm",
            )
            docs = []
            structured = bundle.get("structured_context") if isinstance(bundle, dict) else {}
            for item in (bundle.get("source_documents") or []) if isinstance(bundle, dict) else []:
                if isinstance(item, dict):
                    docs.append(item)
            for value in structured.values() if isinstance(structured, dict) else []:
                if isinstance(value, list):
                    docs.extend([item for item in value if isinstance(item, dict)])
            for doc in docs:
                source = _safe_text(doc.get("source_table") or doc.get("document_type"))
                if not any(key in source for key in ("surgery", "presurg", "postsurg", "operation", "手术", "术前", "术后")):
                    continue
                text = json.dumps(doc, ensure_ascii=False) if not doc.get("content") else _safe_text(doc.get("content"))
                for name in _extract_surgery_names_from_text(text):
                    if name not in names:
                        names.append(name)
        except Exception:
            pass
    return dict(visit_row), names[:10]


def _match_catalog_name(name: str, catalog_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    normalized = _normalize_name(name)
    if not normalized:
        return None
    by_norm = {row["normalized_name"]: row for row in catalog_rows if row.get("normalized_name")}
    if normalized in by_norm:
        return {**by_norm[normalized], "match_type": "exact_normalized", "match_confidence": 0.96}
    contains: list[tuple[int, dict[str, Any], str]] = []
    for row in catalog_rows:
        row_norm = _safe_text(row.get("normalized_name"))
        if not row_norm:
            continue
        if normalized in row_norm or row_norm in normalized:
            overlap = min(len(normalized), len(row_norm))
            if overlap >= 4:
                contains.append((overlap, row, "contains_normalized"))
        for alias in _safe_text(row.get("alias")).split("|"):
            alias_norm = _normalize_name(alias)
            if alias_norm and (alias_norm in normalized or normalized in alias_norm):
                contains.append((len(alias_norm), row, "alias_contains"))
    if not contains:
        return None
    contains.sort(key=lambda item: item[0], reverse=True)
    _, row, match_type = contains[0]
    return {**row, "match_type": match_type, "match_confidence": 0.72}


def _run_match_probe(catalog_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    probe_files = [
        DOCS_DIR / "formal_qc_random10_original_chain_issue_review.json",
        DOCS_DIR / "formal_qc_random10_batch3_original_chain_issue_review.json",
    ]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in probe_files:
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("issues", []):
            if not isinstance(item, dict) or _safe_text(item.get("rule_id")) != "SC-083":
                continue
            visit_id = _safe_text(item.get("visit_id"))
            if (path.name, visit_id) in seen:
                continue
            seen.add((path.name, visit_id))
            visit_row, names = _extract_visit_surgery_names(visit_id)
            if not names:
                names = _extract_surgery_names_from_text(
                    " ".join([_safe_text(item.get("conclusion")), _safe_text(item.get("evidence")), _safe_text(item.get("supporting_quote"))])
                )
            if not names:
                rows.append(
                    {
                        "source_issue_file": path.name,
                        "visit_id": visit_id,
                        "patient_name": item.get("patient_name", visit_row.get("name", "")),
                        "surgery_name": "",
                        "matched_catalog_name": "",
                        "matched_level": "",
                        "match_type": "no_surgery_name_extracted",
                        "match_confidence": 0,
                        "source_page": "",
                        "review_status": "needs_review",
                    }
                )
                continue
            for name in names[:5]:
                match = _match_catalog_name(name, catalog_rows)
                rows.append(
                    {
                        "source_issue_file": path.name,
                        "visit_id": visit_id,
                        "patient_name": item.get("patient_name", visit_row.get("name", "")),
                        "surgery_name": name,
                        "matched_catalog_name": match.get("surgery_name") if match else "",
                        "matched_level": match.get("surgery_level") if match else "",
                        "match_type": match.get("match_type") if match else "no_match",
                        "match_confidence": match.get("match_confidence") if match else 0,
                        "source_page": match.get("source_page") if match else "",
                        "review_status": "matched" if match and float(match.get("match_confidence") or 0) >= 0.9 else "needs_review",
                    }
                )
    return rows


def _write_report(path: Path, quality: dict[str, Any], match_rows: list[dict[str, Any]]) -> None:
    candidates = quality.get("pdf_candidates") or []
    selected = quality.get("source_file")
    lines = [
        "# 手术分级目录结构化转换报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 源 PDF 定位",
        "",
        "| path | size | pages | modified | text_layer | score |",
        "| --- | ---: | ---: | --- | --- | ---: |",
    ]
    for item in candidates:
        lines.append(
            f"| `{item['path']}` | {item['size_bytes']} | {item['page_count']} | {item['modified_time']} | {item['has_text_layer']} | {item['selection_score']} |"
        )
    lines.extend(
        [
            "",
            f"- 选用源文件：`{selected}`。",
            "- 抽取方式：`pdfplumber_table`，保留 source_page 与 raw_row_text。",
            "",
            "## 质量统计",
            "",
            f"- 总行数：{quality['total_rows']}。",
            f"- 可识别 surgery_level 行数：{quality['recognizable_level_rows']}。",
            f"- 四级手术行数：{quality['level_4_rows']}。",
            f"- surgery_name 为空行数：{quality['empty_surgery_name_rows']}。",
            f"- normalized_name 重复数：{quality['normalized_name_duplicate_count']}。",
            f"- 同 normalized_name 不同 level 冲突数：{quality['normalized_name_level_conflict_count']}。",
            f"- needs_review 行数：{quality['needs_review_rows']}。",
            f"- level 分布：`{json.dumps(quality['level_counts'], ensure_ascii=False, sort_keys=True)}`。",
            "",
            "## 可用性结论",
            "",
        ]
    )
    if quality["needs_review_rows"] or quality["normalized_name_level_conflict_count"]:
        lines.append("- catalog 可作为后续 SC-083 程序化适用性判断的候选来源，但需先复核 needs_review/冲突项。")
    else:
        lines.append("- catalog 抽取结构完整，未发现 level 缺失或同名跨等级冲突，可进入下一步只读匹配评估。")
    lines.extend(["", "## 四级手术抽样 30 条", ""])
    for row in quality["level4_sample_30"][:30]:
        lines.append(f"- p{row['source_page']} `{row['surgery_code']}` {row['surgery_name']} -> {row['surgery_level']}")
    lines.extend(["", "## 非四级手术抽样 30 条", ""])
    for row in quality["non_level4_sample_30"][:30]:
        lines.append(f"- p{row['source_page']} `{row['surgery_code']}` {row['surgery_name']} -> {row['surgery_level']}")
    lines.extend(["", "## SC-083 匹配预检", ""])
    if match_rows:
        counts = Counter(row["review_status"] for row in match_rows)
        lines.append(f"- 预检行数：{len(match_rows)}；状态分布：`{json.dumps(dict(counts), ensure_ascii=False, sort_keys=True)}`。")
        for row in match_rows[:30]:
            lines.append(
                f"- `{row['visit_id']}` {row['surgery_name']} -> {row['matched_catalog_name']} level={row['matched_level']} type={row['match_type']} confidence={row['match_confidence']}"
            )
    else:
        lines.append("- 未生成匹配预检行。")
    lines.extend(["", "## 边界", "", "- 本轮未接入 SC-083，未改正式质控主链路，未写数据库。"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将手术分级 PDF 目录转换为结构化 catalog。")
    parser.add_argument("--source-pdf", type=Path, default=DEFAULT_SOURCE_PDF)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--skip-match-probe", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidates = _find_pdf_candidates()
    source_pdf = args.source_pdf if args.source_pdf.exists() else (Path(candidates[0]["path"]) if candidates else args.source_pdf)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if not source_pdf.exists():
        quality = {
            "source_file": "",
            "pdf_candidates": candidates,
            "total_rows": 0,
            "recognizable_level_rows": 0,
            "level_4_rows": 0,
            "empty_surgery_name_rows": 0,
            "normalized_name_duplicate_count": 0,
            "normalized_name_level_conflict_count": 0,
            "needs_review_rows": 0,
            "level_counts": {},
            "level4_sample_30": [],
            "non_level4_sample_30": [],
            "quality_flags": ["source_pdf_missing"],
        }
        _write_json(args.output_dir / QUALITY_JSON.name, quality)
        _write_report(args.output_dir / REPORT_MD.name, quality, [])
        print(json.dumps({"status": "source_pdf_missing", "candidates": len(candidates)}, ensure_ascii=False))
        return
    catalog_rows, metadata = _extract_catalog(source_pdf)
    quality = _quality_report(catalog_rows, source_pdf=source_pdf, candidates=candidates, metadata=metadata)
    needs_review_rows = [row for row in catalog_rows if row["review_status"] == "needs_review"]
    match_rows = [] if args.skip_match_probe else _run_match_probe(catalog_rows)

    _write_csv(args.output_dir / CATALOG_CSV.name, catalog_rows)
    _write_json(args.output_dir / CATALOG_JSON.name, {"rows": catalog_rows})
    _write_csv(args.output_dir / NEEDS_REVIEW_CSV.name, needs_review_rows)
    _write_json(args.output_dir / QUALITY_JSON.name, quality)
    _write_csv(args.output_dir / MATCH_PROBE_CSV.name, match_rows)
    _write_json(args.output_dir / MATCH_PROBE_JSON.name, {"rows": match_rows})
    _write_report(args.output_dir / REPORT_MD.name, quality, match_rows)
    print(json.dumps({"status": "completed", "rows": len(catalog_rows), "level4": quality["level_4_rows"], "needs_review": len(needs_review_rows), "match_probe_rows": len(match_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
