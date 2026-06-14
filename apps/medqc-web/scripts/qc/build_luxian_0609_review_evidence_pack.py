from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND_PATH = ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

REVIEW_QUEUE_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_review_queue.json"
CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
OUTPUT_JSON_PATH = ROOT / "docs" / "0602" / "luxian_0609_review_evidence_pack.json"
OUTPUT_MD_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-golden-cases复核证据包.md"

MAX_SNIPPETS_PER_ROW = 4
MAX_SNIPPET_CHARS = 220
MAX_DOCUMENTS_PER_ROW = 12

DOCUMENT_ALIASES = {
    "入院记录": {"入院记录", "admission_record"},
    "入院记录诊断": {"入院记录诊断", "admission_record_diagnosis"},
    "首次病程记录": {"首次病程记录", "first_course_record"},
    "首次病程": {"首次病程记录", "first_course_record"},
    "日常病程记录": {"日常病程记录", "daily_course_record"},
    "日常病程": {"日常病程记录", "daily_course_record"},
    "查房记录": {"上级医师查房记录", "senior_course_record"},
    "上级医师查房记录": {"上级医师查房记录", "senior_course_record"},
    "会诊记录": {"会诊记录", "consultation_record"},
    "手术记录": {"手术记录", "surgery_record"},
    "术后首次病程记录": {"术后首次病程记录", "postsurg_firstcourse_record"},
    "术后首次病程": {"术后首次病程记录", "postsurg_firstcourse_record"},
    "抢救记录": {"抢救记录", "rescue_record"},
    "转入记录": {"转入记录", "transfer_in_record"},
    "转出记录": {"转出记录", "transfer_out_record"},
    "护理记录": {"护理记录", "nursing_record"},
    "出院记录": {"出院记录", "discharge_record"},
    "出院记录诊断": {"出院记录诊断", "discharge_record_diagnosis"},
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(value: Any) -> str:
    return str(value or "").strip()


def compact_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def build_catalog_map() -> dict[str, dict[str, Any]]:
    data = load_json(CATALOG_PATH, [])
    if not isinstance(data, list):
        return {}
    return {
        normalize(item.get("qc_point_id")): item
        for item in data
        if isinstance(item, dict) and normalize(item.get("qc_point_id"))
    }


def load_review_rows(
    *,
    review_json: Path = REVIEW_QUEUE_PATH,
    review_csv: Path | None = None,
    review_id: str | None = None,
    qc_point_id: str | None = None,
    max_rows: int | None = None,
) -> list[dict[str, Any]]:
    if review_csv:
        if not review_csv.exists():
            raise FileNotFoundError(f"review csv not found: {review_csv}")
        with review_csv.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
    else:
        data = load_json(review_json, {"rows": []})
        rows = data.get("rows") if isinstance(data, dict) else []
        if not isinstance(rows, list):
            rows = []
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if review_id and normalize(row.get("review_id")) != review_id:
            continue
        if qc_point_id and normalize(row.get("qc_point_id")) != qc_point_id:
            continue
        filtered.append(row)
        if max_rows is not None and len(filtered) >= max_rows:
            break
    return filtered


def resolve_document_filters(catalog_item: dict[str, Any], row: dict[str, Any]) -> set[str]:
    raw_values: list[str] = []
    raw_docs = catalog_item.get("applicable_documents")
    if isinstance(raw_docs, list):
        raw_values.extend(normalize(item) for item in raw_docs)
    elif isinstance(raw_docs, str):
        raw_values.append(raw_docs)
    for field in ("source_document", "required_documents_label"):
        value = normalize(catalog_item.get(field))
        if value:
            raw_values.extend(part.strip() for part in re.split(r"[、,，/]", value) if part.strip())
    customer_text = normalize(row.get("customer_text") or catalog_item.get("customer_text"))
    for keyword, aliases in DOCUMENT_ALIASES.items():
        if keyword in customer_text:
            raw_values.extend(aliases)

    filters: set[str] = set()
    for value in raw_values:
        if not value:
            continue
        filters.add(value)
        filters.update(DOCUMENT_ALIASES.get(value, set()))
    return filters


def tokenize_for_snippets(*values: str) -> list[str]:
    terms: list[str] = []
    stop_terms = {
        "记录",
        "文书",
        "病历",
        "患者",
        "问题",
        "要求",
        "是否",
        "未按",
        "完成",
        "书写",
        "质控",
    }
    for value in values:
        cleaned = re.sub(r"[，。；;:：、（）()\[\]【】,.\s]+", " ", value or "")
        for part in cleaned.split():
            token = part.strip()
            if len(token) < 2 or token in stop_terms:
                continue
            if token not in terms:
                terms.append(token)
    return terms[:10]


def pick_snippets(content: str, terms: list[str]) -> list[dict[str, Any]]:
    if not content:
        return []
    snippets: list[dict[str, Any]] = []
    for term in terms:
        pos = content.find(term)
        if pos < 0:
            continue
        start = max(0, pos - 70)
        end = min(len(content), pos + len(term) + 120)
        snippets.append(
            {
                "term": term,
                "snippet": compact_space(content[start:end])[:MAX_SNIPPET_CHARS],
            }
        )
        if len(snippets) >= MAX_SNIPPETS_PER_ROW:
            break
    if snippets:
        return snippets
    return [{"term": "文书开头", "snippet": compact_space(content[:MAX_SNIPPET_CHARS])}]


def load_visit_context(visit_id: str) -> dict[str, Any]:
    try:
        from app.database.connection import SessionLocal
        from app.database.models.cdm import MedicalRecordFrontpage
    except Exception as exc:
        return {"data_status": "db_import_failed", "error": str(exc)}

    if SessionLocal is None:
        return {"data_status": "db_unavailable", "error": "DATABASE_URL 未配置"}

    try:
        with SessionLocal() as session:
            row = session.query(MedicalRecordFrontpage).filter_by(visit_id=visit_id).first()
            if not row:
                return {"data_status": "frontpage_not_found"}
            return {
                "data_status": "ready",
                "patient_id": normalize(getattr(row, "patient_id", "")),
                "patient_name": normalize(getattr(row, "patient_name", "")),
                "sex": normalize(getattr(row, "sex", "")),
                "age": normalize(getattr(row, "age", "")),
                "department": normalize(getattr(row, "dept_name", "") or getattr(row, "department", "")),
                "admission_time": normalize(getattr(row, "admission_datetime", "")),
                "discharge_time": normalize(getattr(row, "discharge_datetime", "")),
            }
    except Exception as exc:
        return {"data_status": "frontpage_query_failed", "error": str(exc)}


def load_documents(visit_id: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        from app.services.medical_records.detail_service import get_documents
    except Exception as exc:
        return [], f"文书服务导入失败: {exc}"

    try:
        result = get_documents(visit_id)
    except Exception as exc:
        return [], f"文书查询失败: {exc}"
    docs = result.get("documents") if isinstance(result, dict) else []
    if not isinstance(docs, list):
        return [], "文书查询结果格式异常"
    return [doc for doc in docs if isinstance(doc, dict) and doc.get("has_content")], None


def build_pack_row(row: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    qc_point_id = normalize(row.get("qc_point_id"))
    visit_id = normalize(row.get("visit_id"))
    catalog_item = catalog.get(qc_point_id) or {}
    visit_context = load_visit_context(visit_id)
    docs, doc_error = load_documents(visit_id)
    doc_filters = resolve_document_filters(catalog_item, row)
    terms = tokenize_for_snippets(
        normalize(row.get("manual_issue_text")),
        normalize(row.get("customer_text")),
        normalize(catalog_item.get("standardized_rule")),
    )

    selected_docs: list[dict[str, Any]] = []
    for doc in docs:
        source_table = normalize(doc.get("source_table") or doc.get("type"))
        label = normalize(doc.get("label") or doc.get("document_title"))
        is_relevant = not doc_filters or source_table in doc_filters or label in doc_filters
        if not is_relevant and any(filter_value and filter_value in label for filter_value in doc_filters):
            is_relevant = True
        if not is_relevant:
            continue
        snippets = pick_snippets(normalize(doc.get("content")), terms)
        selected_docs.append(
            {
                "source_table": source_table,
                "label": label,
                "document_id": normalize(doc.get("document_id")),
                "record_time": normalize(doc.get("record_time") or doc.get("sort_time")),
                "length": int(doc.get("length") or 0),
                "snippets": snippets,
            }
        )
        if len(selected_docs) >= MAX_DOCUMENTS_PER_ROW:
            break

    data_status = "ready"
    warnings: list[str] = []
    if doc_error:
        data_status = "document_query_failed"
        warnings.append(doc_error)
    elif not docs:
        data_status = "no_documents"
        warnings.append("该住院号未查询到可装配文书。")
    elif not selected_docs:
        data_status = "no_relevant_documents"
        warnings.append("已查询到文书，但未命中该质控点的推荐文书范围。")
    if visit_context.get("data_status") != "ready":
        warnings.append(f"首页上下文状态: {visit_context.get('data_status')}")

    return {
        "review_id": row.get("review_id"),
        "qc_point_id": qc_point_id,
        "source_index": row.get("source_index"),
        "customer_text": row.get("customer_text") or catalog_item.get("customer_text"),
        "implementation_status": row.get("implementation_status") or catalog_item.get("implementation_status"),
        "visit_id": visit_id,
        "patient_name": row.get("patient_name") or visit_context.get("patient_name"),
        "department": row.get("department") or visit_context.get("department"),
        "source_rule_id": row.get("source_rule_id"),
        "manual_issue_text": row.get("manual_issue_text"),
        "review_status": row.get("review_status"),
        "accepted_case_type": row.get("accepted_case_type"),
        "expected_hit": row.get("expected_hit"),
        "visit_context": visit_context,
        "document_filters": sorted(doc_filters),
        "document_inventory": [
            {
                "source_table": normalize(doc.get("source_table") or doc.get("type")),
                "label": normalize(doc.get("label") or doc.get("document_title")),
                "record_time": normalize(doc.get("record_time") or doc.get("sort_time")),
                "length": int(doc.get("length") or 0),
            }
            for doc in docs[:30]
        ],
        "evidence_documents": selected_docs,
        "data_status": data_status,
        "warnings": warnings,
    }


def build_evidence_pack(
    *,
    review_json: Path = REVIEW_QUEUE_PATH,
    review_csv: Path | None = None,
    review_id: str | None = None,
    qc_point_id: str | None = None,
    max_rows: int | None = None,
) -> dict[str, Any]:
    catalog = build_catalog_map()
    rows = load_review_rows(
        review_json=review_json,
        review_csv=review_csv,
        review_id=review_id,
        qc_point_id=qc_point_id,
        max_rows=max_rows,
    )
    evidence_rows = [build_pack_row(row, catalog) for row in rows]
    status_counts = Counter(normalize(row.get("data_status")) for row in evidence_rows)
    return {
        "version": "2026-06-10",
        "description": "泸县0609 golden cases 复核证据包。只包含病历上下文、文书清单和短证据片段，不输出完整病历全文。",
        "summary": {
            "review_rows": len(evidence_rows),
            "by_data_status": dict(sorted(status_counts.items())),
            "covered_qc_points": len({row.get("qc_point_id") for row in evidence_rows if row.get("qc_point_id")}),
        },
        "rows": evidence_rows,
    }


def render_report(data: dict[str, Any]) -> str:
    summary = data.get("summary") or {}
    rows = data.get("rows") or []
    lines = [
        "# 泸县0609质控点 golden cases 复核证据包",
        "",
        "## 说明",
        "",
        "本证据包用于复核候选样本是否能进入正式 golden cases。内容仅包含文书清单和短证据片段，不输出完整病历全文。",
        "",
        "## 汇总",
        "",
        f"- 复核行数：{summary.get('review_rows', 0)}",
        f"- 覆盖质控点：{summary.get('covered_qc_points', 0)}",
        "",
        "| 数据状态 | 数量 |",
        "|---|---:|",
    ]
    for status, count in (summary.get("by_data_status") or {}).items():
        lines.append(f"| {status} | {count} |")

    lines.extend(["", "## 复核证据 Top 50", ""])
    for row in rows[:50]:
        lines.extend(
            [
                f"### {row.get('review_id')} · {row.get('qc_point_id')}",
                "",
                f"- 住院号：{row.get('visit_id')}",
                f"- 患者：{row.get('patient_name') or '-'}",
                f"- 科室：{row.get('department') or '-'}",
                f"- 客户质控点：{row.get('customer_text') or '-'}",
                f"- 人工问题：{row.get('manual_issue_text') or '-'}",
                f"- 数据状态：{row.get('data_status')}",
            ]
        )
        warnings = row.get("warnings") or []
        if warnings:
            lines.append(f"- 提示：{'；'.join(str(item) for item in warnings)}")
        documents = row.get("evidence_documents") or []
        if not documents:
            lines.extend(["", "未找到推荐文书范围内的可展示片段。", ""])
            continue
        lines.extend(["", "| 文书 | 时间 | 片段 |", "|---|---|---|"])
        for doc in documents[:6]:
            snippets = doc.get("snippets") or []
            snippet_text = "<br>".join(
                f"【{snippet.get('term') or ''}】{str(snippet.get('snippet') or '').replace('|', '/')}"
                for snippet in snippets[:2]
            )
            lines.append(
                "| {label} | {time} | {snippet} |".format(
                    label=str(doc.get("label") or doc.get("source_table") or "").replace("|", "/"),
                    time=str(doc.get("record_time") or "").replace("|", "/"),
                    snippet=snippet_text or "-",
                )
            )
        lines.append("")

    lines.extend(
        [
            "## 使用建议",
            "",
            "1. 先复核 `data_status=ready` 的候选样本。",
            "2. 如果片段与客户质控点不匹配，在复核队列中标记 `review_status=rejected`。",
            "3. 如果片段匹配且能覆盖触发条件、排除条件和整改建议，在复核队列中标记 `review_status=accepted` 并填写 case type。",
            "4. `no_relevant_documents` 不代表规则错误，通常表示该病历缺少推荐文书范围或文书类型映射仍需补齐。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build evidence pack for Luxian 0609 golden case review queue.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--review-json", type=Path, default=REVIEW_QUEUE_PATH)
    parser.add_argument("--review-csv", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON_PATH)
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD_PATH)
    parser.add_argument("--review-id", default=None)
    parser.add_argument("--qc-point-id", default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args()
    data = build_evidence_pack(
        review_json=args.review_json,
        review_csv=args.review_csv,
        review_id=args.review_id,
        qc_point_id=args.qc_point_id,
        max_rows=args.max_rows,
    )
    summary = data["summary"]
    print(f"review_rows={summary['review_rows']}")
    print(f"covered_qc_points={summary['covered_qc_points']}")
    print(f"by_data_status={summary['by_data_status']}")
    if args.write:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.output_md.write_text(render_report(data), encoding="utf-8")
        print(f"wrote={args.output_json}")
        print(f"wrote={args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
