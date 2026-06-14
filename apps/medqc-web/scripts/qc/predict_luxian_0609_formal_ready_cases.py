from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0602"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from discover_luxian_0609_formal_ready_cases import (  # noqa: E402
    DISCOVERERS,
    FORMAL_READY_QC_POINTS,
    load_documents_by_type,
    load_frontpage,
)


GOLDEN_CASES_PATH = DOCS_DIR / "泸县0609质控点-golden-cases.json"
DEFAULT_OUTPUT_PATH = DOCS_DIR / "luxian_0609_formal_ready_predictions.json"
CASE_TYPES = ("positive", "negative", "boundary")
MAX_TEXT_CHARS = 360


def normalize(value: Any) -> str:
    return str(value or "").strip()


def truncate(value: Any, *, max_chars: int = MAX_TEXT_CHARS) -> str:
    text = normalize(value).replace("\r", " ").replace("\n", " ")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def truthy(value: Any) -> bool:
    return normalize(value).lower() in {"true", "1", "yes", "y", "命中", "是"}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def iter_golden_cases(path: Path) -> list[dict[str, Any]]:
    data = load_json(path, {"rules": []})
    rows: list[dict[str, Any]] = []
    for rule in data.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        qc_point_id = normalize(rule.get("qc_point_id"))
        if qc_point_id not in FORMAL_READY_QC_POINTS:
            continue
        cases = rule.get("cases") if isinstance(rule.get("cases"), dict) else {}
        for case_type in CASE_TYPES:
            for case in cases.get(case_type) or []:
                if not isinstance(case, dict):
                    continue
                rows.append(
                    {
                        "case_id": normalize(case.get("case_id")),
                        "qc_point_id": qc_point_id,
                        "visit_id": normalize(case.get("visit_id")),
                        "patient_name": normalize(case.get("patient_name")),
                        "department": normalize(case.get("department")),
                        "case_type": case_type,
                        "expected_hit": bool(case.get("expected_hit")),
                    }
                )
    return rows


def iter_review_cases(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in read_csv(path):
        qc_point_id = normalize(row.get("qc_point_id"))
        if qc_point_id not in FORMAL_READY_QC_POINTS:
            continue
        case_type = normalize(row.get("accepted_case_type") or row.get("suggested_case_type")).lower()
        if case_type not in CASE_TYPES:
            continue
        rows.append(
            {
                "case_id": normalize(row.get("review_id")),
                "qc_point_id": qc_point_id,
                "visit_id": normalize(row.get("visit_id")),
                "patient_name": normalize(row.get("patient_name")),
                "department": normalize(row.get("department")),
                "case_type": case_type,
                "expected_hit": truthy(row.get("expected_hit")),
            }
        )
    return rows


def normalize_discovered(discovered: Any) -> list[dict[str, Any]]:
    if not discovered:
        return []
    if isinstance(discovered, list):
        return [item for item in discovered if isinstance(item, dict)]
    if isinstance(discovered, dict):
        return [discovered]
    return []


def choose_result(candidates: list[dict[str, Any]]) -> tuple[bool | None, str, dict[str, Any] | None]:
    if not candidates:
        return None, "not_applicable", None
    for candidate in candidates:
        if normalize(candidate.get("suggested_case_type")).lower() == "positive":
            return True, "non_compliant", candidate
    for candidate in candidates:
        if normalize(candidate.get("suggested_case_type")).lower() == "negative":
            return False, "compliant", candidate
    for candidate in candidates:
        if normalize(candidate.get("suggested_case_type")).lower() == "boundary":
            return False, "data_quality_gap", candidate
    return None, "uncertain", candidates[0]


def predict_case(row: dict[str, Any]) -> dict[str, Any]:
    qc_point_id = normalize(row.get("qc_point_id"))
    visit_id = normalize(row.get("visit_id"))
    case_id = normalize(row.get("case_id")) or visit_id
    base = {
        "case_id": case_id,
        "sample_id": case_id,
        "visit_id": visit_id,
        "qc_point_id": qc_point_id,
        "patient_name": normalize(row.get("patient_name")),
        "department": normalize(row.get("department")),
        "expected_case_type": normalize(row.get("case_type")),
        "expected_hit": bool(row.get("expected_hit")),
    }
    if not qc_point_id or qc_point_id not in FORMAL_READY_QC_POINTS:
        return {**base, "actual_hit": None, "status": "unsupported", "evidence_summary": "该规则不在 formal-ready 预测范围内。"}
    if not visit_id:
        return {**base, "actual_hit": None, "status": "data_quality_gap", "evidence_summary": "缺少 visit_id，无法执行预测。"}

    try:
        frontpage = load_frontpage(visit_id)
        docs = load_documents_by_type(visit_id)
        visit = {
            "visit_id": visit_id,
            "sample_item_id": normalize(row.get("sample_item_id")),
            "patient_name": normalize(row.get("patient_name")),
            "department": normalize(row.get("department")),
        }
        discovered = normalize_discovered(DISCOVERERS[qc_point_id](visit, frontpage, docs))
    except Exception as exc:
        return {
            **base,
            "actual_hit": None,
            "status": "data_quality_gap",
            "evidence_summary": f"执行预测失败：{type(exc).__name__}: {exc}",
        }

    actual_hit, status, chosen = choose_result(discovered)
    evidence_summary = "未发现可判定证据。"
    matched_text = ""
    confidence = None
    candidate_type = ""
    if chosen:
        evidence_summary = truncate(chosen.get("evidence_summary"))
        matched_text = truncate(chosen.get("matched_text"))
        confidence = chosen.get("confidence")
        candidate_type = normalize(chosen.get("suggested_case_type"))
    return {
        **base,
        "actual_hit": actual_hit,
        "hit": actual_hit,
        "status": status,
        "result_status": status,
        "candidate_type": candidate_type,
        "confidence": confidence,
        "evidence_summary": evidence_summary,
        "matched_text": matched_text,
        "document_type": "多文书" if qc_point_id in {"LX0609-017", "LX0609-032"} else "会诊记录",
        "document_name": "客户样本池病历文书",
        "suggestion": "请结合证据片段人工复核；若证据不足，按 data_quality_gap 处理。",
    }


def build_predictions(rows: list[dict[str, Any]], *, source: str) -> dict[str, Any]:
    predictions = [predict_case(row) for row in rows]
    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "model": "qwen3.5-35b-a3b",
        "source": source,
        "summary": {
            "input_cases": len(rows),
            "prediction_count": len(predictions),
            "hit_count": sum(1 for item in predictions if item.get("actual_hit") is True),
            "not_hit_count": sum(1 for item in predictions if item.get("actual_hit") is False),
            "unknown_count": sum(1 for item in predictions if item.get("actual_hit") is None),
        },
        "predictions": predictions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Predict Luxian 0609 formal-ready QC cases.")
    parser.add_argument("--golden-cases", type=Path, default=None, help="Read cases from golden cases JSON.")
    parser.add_argument("--review-csv", type=Path, default=None, help="Read cases from review CSV for dry-run prediction.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if args.review_csv:
        rows = iter_review_cases(args.review_csv)
        source = str(args.review_csv)
    else:
        rows = iter_golden_cases(args.golden_cases or GOLDEN_CASES_PATH)
        source = str(args.golden_cases or GOLDEN_CASES_PATH)
    data = build_predictions(rows, source=source)
    summary = data["summary"]
    print(f"input_cases={summary['input_cases']}")
    print(f"prediction_count={summary['prediction_count']}")
    print(f"hit_count={summary['hit_count']}")
    print(f"not_hit_count={summary['not_hit_count']}")
    print(f"unknown_count={summary['unknown_count']}")
    if args.write:
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
