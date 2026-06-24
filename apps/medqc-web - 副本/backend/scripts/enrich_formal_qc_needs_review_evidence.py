#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.bundles import assemble_final_record_bundle  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
INPUT_CSV = DOCS_DIR / "formal_qc_sample_postprocessed_issue_review.csv"
RELEASE_MR = REPO_ROOT / "release" / "0426_full_auto" / "0426_full_auto" / "mr.csv"
OUTPUT_CANDIDATES_CSV = DOCS_DIR / "formal_qc_needs_review_evidence_enrichment_candidates.csv"
OUTPUT_REPORT_CSV = DOCS_DIR / "formal_qc_needs_review_evidence_enrichment_report.csv"
OUTPUT_REPORT_JSON = DOCS_DIR / "formal_qc_needs_review_evidence_enrichment_report.json"
OUTPUT_MD = DOCS_DIR / "正式质控needs_review证据补强回放报告.md"

RULE_PRIORITY = ["SC-036", "SC-020", "SC-125", "SC-118", "SC-123", "SC-146", "SC-107", "SC-083"]
RULE_QUOTAS = {
    "SC-036": 2,
    "SC-020": 1,
    "SC-125": 2,
    "SC-118": 2,
    "SC-123": 2,
    "SC-146": 1,
    "SC-107": 1,
    "SC-083": 1,
}
MAX_CANDIDATES = 12

ABNORMAL_KEYWORDS = [
    "异常",
    "阳性",
    "偏高",
    "偏低",
    "CRP",
    "CT",
    "结节",
    "空洞",
    "感染",
    "骨折",
    "病理",
    "肿瘤",
    "癌",
    "低钾",
    "肾功",
    "肝功",
    "抗酸",
    "结核",
]
DIAGNOSIS_TABLES = {"admission_record_diagnosis", "discharge_record_diagnosis"}
COURSE_TABLES = {"daily_course_record", "senior_course_record", "first_course_record", "postsurg_firstcourse_record"}
ORDER_TABLES = {"inpat_drug_order", "inpat_nondrug_order", "inpat_execution_record"}
EXAM_LAB_TABLES = {"exam_master", "exam_item_report", "labtest_master", "labtest_item_report", "pathology_exam_master", "pathology_exam_report"}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _truncate(text: Any, limit: int = 500) -> str:
    normalized = re.sub(r"\s+", " ", _safe_text(text))
    return normalized[:limit]


def _contains_any(text: str, keywords: list[str] | set[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _keyword_terms(row: dict[str, Any]) -> list[str]:
    text = f"{row.get('findings', '')} {row.get('evidence', '')} {row.get('suggestion', '')}"
    terms = re.findall(r"[\u4e00-\u9fffA-Za-z0-9%#/\-+]{2,}", text)
    stop = {"记录", "当前文书", "患者", "缺失", "缺少", "未记录", "补充", "分析", "处理", "诊断", "病程"}
    return [term for term in dict.fromkeys(terms) if term not in stop][:20]


def _load_visit_keys() -> dict[str, dict[str, str]]:
    return {_safe_text(row.get("visit_id")): row for row in _read_csv(RELEASE_MR) if _safe_text(row.get("visit_id"))}


def _docs_by_table(bundle: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in list(bundle.get("source_documents") or []):
        if not isinstance(doc, dict):
            continue
        table = _safe_text(doc.get("source_table") or doc.get("document_type"))
        if table:
            grouped[table].append(dict(doc))
    return grouped


def _snippets(docs: list[dict[str, Any]], keywords: list[str] | set[str], *, max_items: int = 3, limit: int = 360) -> list[str]:
    out: list[str] = []
    for doc in docs:
        content = _safe_text(doc.get("content") or doc.get("text_preview"))
        if not content:
            continue
        if keywords and not _contains_any(content, keywords):
            continue
        title = _safe_text(doc.get("document_title") or doc.get("source_table") or doc.get("document_type"))
        time = _safe_text(doc.get("display_time") or doc.get("record_time"))
        out.append(f"[{title} {time}] {_truncate(content, limit)}")
        if len(out) >= max_items:
            break
    return out


def _all_docs(grouped: dict[str, list[dict[str, Any]]], tables: set[str]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for table in tables:
        docs.extend(grouped.get(table) or [])
    return docs


def _diagnosis_names(docs: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for doc in docs:
        content = _safe_text(doc.get("content"))
        for match in re.findall(r"诊断名称[:：]\s*([^\n;；]+)", content):
            names.append(match.strip())
    return list(dict.fromkeys(names))


def _discharge_sections(doc: dict[str, Any]) -> dict[str, str]:
    sections: dict[str, str] = {}
    for section in list(doc.get("sections") or []):
        if isinstance(section, dict):
            key = _safe_text(section.get("section_key") or section.get("section_label"))
            text = _safe_text(section.get("text"))
            if key:
                sections[key] = text
    return sections


def _enrich_sc036(row: dict[str, Any], grouped: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    terms = list(dict.fromkeys([*_keyword_terms(row), *ABNORMAL_KEYWORDS]))
    abnormal = _snippets(_all_docs(grouped, EXAM_LAB_TABLES), terms, max_items=3)
    courses = _snippets(_all_docs(grouped, COURSE_TABLES), _keyword_terms(row) + ["查房", "病程", "处理", "复查", "分析"], max_items=3)
    score = 0
    reasons: list[str] = []
    if abnormal:
        score = max(score, 2)
        reasons.append("找到检查/检验/病理异常相关证据。")
    if courses:
        score = max(score, 1)
        reasons.append("找到后续病程/查房片段。")
    if abnormal and courses:
        course_text = " ".join(courses)
        if not _contains_any(course_text, ["CRP", "CT", "病理", "异常", "结节", "肿瘤", "结核", "感染", "复查", "处理"]):
            score = 3
            reasons.append("异常证据与后续病程片段可形成初步对照，但仍需人工确认病程全文是否未分析。")
        else:
            score = 2
            reasons.append("病程片段已出现部分相关词，不能仅凭片段确认未分析。")
    evidence = "\n".join([*abnormal, *courses])
    return _decision(row, score, evidence, reasons, required_gap="需补异常结果与后续病程全文对照证据。")


def _enrich_diagnosis(row: dict[str, Any], grouped: dict[str, list[dict[str, Any]]], *, admission: bool) -> dict[str, Any]:
    diagnosis_docs = _all_docs(grouped, {"admission_record_diagnosis"} if admission else {"discharge_record_diagnosis"})
    diagnosis_names = _diagnosis_names(diagnosis_docs)
    support_tables = {"admission_record", "discharge_record", "exam_master", "exam_item_report", "labtest_item_report", "pathology_exam_report", "surgery_record", "mr_surgery"}
    support = _snippets(_all_docs(grouped, support_tables), _keyword_terms(row) + ["结核", "肿瘤", "癌", "病理", "CT", "检查"], max_items=4)
    diagnosis_text = "；".join(diagnosis_names)
    score = 0
    reasons: list[str] = []
    pieces: list[str] = []
    if diagnosis_names:
        score = max(score, 2)
        pieces.append(f"诊断列表：{diagnosis_text}")
        reasons.append("找到诊断列表证据。")
    if support:
        score = max(score, 2)
        pieces.extend(support)
        reasons.append("找到病史/检查/病理/手术支持证据。")
    if diagnosis_names and support:
        score = 3
        reasons.append("诊断列表与支持证据可形成初步闭环，但诊断顺序/漏诊仍需人工核对完整诊断列表。")
    return _decision(row, score, "\n".join(pieces), reasons, required_gap="需补完整诊断列表及支持疾病证据。")


def _enrich_sc118(row: dict[str, Any], grouped: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    discharge_docs = grouped.get("discharge_record") or []
    pieces: list[str] = []
    missing: list[str] = []
    fields = {
        "admission_condition": "入院情况",
        "treatment_course": "诊疗经过",
        "discharge_condition": "出院情况",
        "discharge_order": "出院医嘱",
    }
    for doc in discharge_docs[:2]:
        sections = _discharge_sections(doc)
        for key, label in fields.items():
            text = sections.get(key, "")
            if text:
                pieces.append(f"{label}: {_truncate(text, 220)}")
            else:
                missing.append(label)
    score = 0
    reasons: list[str] = []
    if discharge_docs:
        score = 1
        reasons.append("找到出院记录文书。")
    if pieces:
        score = 2
        reasons.append("找到出院记录结构字段上下文。")
    if missing and pieces:
        score = 3
        reasons.append(f"结构字段中缺失/为空：{'、'.join(dict.fromkeys(missing))}。")
    return _decision(row, score, "\n".join(pieces), reasons, required_gap="需补出院记录各字段是否为空的结构化上下文。")


def _enrich_sc123(row: dict[str, Any], grouped: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    discharge_docs = grouped.get("discharge_record") or []
    snippets: list[str] = []
    for doc in discharge_docs:
        content = _safe_text(doc.get("content"))
        match = re.search(r"(出院带药[:：].{0,260})", content)
        if match:
            snippets.append(match.group(1))
    score = 0
    reasons: list[str] = []
    if discharge_docs:
        score = 1
        reasons.append("找到出院记录。")
    if snippets:
        score = 3
        reasons.append("找到出院带药段落，可进一步核查药名、剂量、途径、频次、天数。")
    else:
        reasons.append("未在出院记录中定位到明确“出院带药”段落。")
    return _decision(row, score, "\n".join(snippets), reasons, required_gap="需补明确出院带药段落。")


def _enrich_sc146(row: dict[str, Any], grouped: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    course = _snippets(_all_docs(grouped, COURSE_TABLES), _keyword_terms(row) + ["CT", "MRI", "检查", "治疗", "用药"], max_items=3)
    orders = _snippets(_all_docs(grouped, ORDER_TABLES), _keyword_terms(row) + ["CT", "MRI", "检查", "治疗", "用药"], max_items=3)
    score = 0
    reasons: list[str] = []
    if course:
        score = max(score, 2)
        reasons.append("找到病程中治疗/检查/用药相关证据。")
    if orders:
        score = max(score, 2)
        reasons.append("找到医嘱或执行清单对照证据。")
    if course and orders:
        score = 3
        reasons.append("病程与医嘱/执行清单可形成初步对照，但仍需完整医嘱域确认不一致。")
    return _decision(row, score, "\n".join([*course, *orders]), reasons, required_gap="需补医嘱/执行清单对照。")


def _enrich_sc107(row: dict[str, Any], grouped: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    surgery = _snippets(_all_docs(grouped, {"surgery_record", "mr_surgery"}), ["手术", "时间", "开始", "术毕"], max_items=2)
    courses = _snippets(_all_docs(grouped, {"daily_course_record", "senior_course_record", "postsurg_firstcourse_record"}), ["术后", "查房", "手术", "第"], max_items=6, limit=180)
    dates = sorted(set(re.findall(r"\d{4}[-年/]\d{1,2}[-月/]\d{1,2}日?", "\n".join([*surgery, *courses]))))
    score = 0
    reasons: list[str] = []
    if surgery:
        score = max(score, 2)
        reasons.append("找到手术时间/手术记录证据。")
    if courses:
        score = max(score, 2)
        reasons.append("找到术后病程或上级查房记录片段。")
    if surgery and courses and len(dates) >= 3:
        score = 2
        reasons.append(f"形成手术+术后日期列表：{', '.join(dates[:8])}；该证据用于人工核对连续性，不能单独证明缺陷。")
    return _decision(row, score, "\n".join([*surgery, *courses]), reasons, required_gap="需补手术时间及术后三天病程/查房日期列表。")


def _enrich_sc083(row: dict[str, Any], grouped: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    surgery = _snippets(_all_docs(grouped, {"surgery_record", "mr_surgery"}), ["手术", "四级", "级别", "名称"], max_items=3)
    discussion = _snippets(_all_docs(grouped, {"presurg_discussion", "presurg_summary"}), ["讨论", "多学科", "MDT", "参与人员", "主任"], max_items=3)
    surgery_text = " ".join(surgery)
    has_level_four = _contains_any(surgery_text, ["四级", "4级", "Ⅳ级", "IV级", "手术等级:4", "手术等级：4", "手术级别:4", "手术级别：4"])
    score = 0
    reasons: list[str] = []
    if surgery:
        score = max(score, 2)
        reasons.append("找到手术名称/手术记录证据。")
    if discussion:
        score = max(score, 2)
        reasons.append("找到术前讨论/术前小结证据。")
    if surgery and discussion and _contains_any(" ".join(discussion), ["多学科", "MDT"]):
        score = 2
        reasons.append("讨论中出现 MDT/多学科字样，不能确认缺陷。")
    elif surgery and discussion and has_level_four:
        score = 3
        reasons.append("找到四级手术证据和术前讨论文书，但未在片段中看到 MDT/多学科证据。")
    elif surgery and discussion:
        score = 2
        reasons.append("手术与讨论文书均存在，但未确认四级手术等级，不能作为确认缺陷。")
    return _decision(row, score, "\n".join([*surgery, *discussion]), reasons, required_gap="需补手术等级及 MDT/多学科讨论覆盖证据。")


def _decision(row: dict[str, Any], score: int, evidence: str, reasons: list[str], *, required_gap: str) -> dict[str, Any]:
    if score >= 3:
        label = "confirmed_candidate"
    elif score == 0:
        label = "not_supported"
    elif "缺医嘱" in required_gap or "医嘱/执行" in required_gap:
        label = "data_gap"
    else:
        label = "still_needs_review"
    if not evidence and score > 0:
        score = 1
    return {
        "evidence_support_score": score,
        "enhanced_evidence": evidence,
        "enhanced_postprocess_label": label,
        "enhanced_reason": "；".join(reasons) if reasons else required_gap,
    }


def _enrich(row: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    grouped = _docs_by_table(bundle)
    rule_id = _safe_text(row.get("rule_id")).upper()
    if rule_id == "SC-036":
        return _enrich_sc036(row, grouped)
    if rule_id == "SC-020":
        return _enrich_diagnosis(row, grouped, admission=True)
    if rule_id == "SC-125":
        return _enrich_diagnosis(row, grouped, admission=False)
    if rule_id == "SC-118":
        return _enrich_sc118(row, grouped)
    if rule_id == "SC-123":
        return _enrich_sc123(row, grouped)
    if rule_id == "SC-146":
        return _enrich_sc146(row, grouped)
    if rule_id == "SC-107":
        return _enrich_sc107(row, grouped)
    if rule_id == "SC-083":
        return _enrich_sc083(row, grouped)
    return _decision(row, 0, "", ["未配置该规则的证据补强器。"], required_gap="需补规则证据构造器。")


def _candidate_reason(row: dict[str, Any]) -> tuple[str, str, str]:
    rule_id = _safe_text(row.get("rule_id")).upper()
    if rule_id == "SC-036":
        return ("异常检查/检验类 findings 疑似真实，当前缺异常结果与病程对照。", "异常结果+后续病程对照", "lab/exam/pathology + daily/senior course")
    if rule_id in {"SC-020", "SC-125"}:
        return ("诊断漏填/顺序类 findings 需要诊断列表和支持证据闭环。", "诊断列表+支持疾病证据", "admission/discharge diagnosis + admission/discharge/exam/pathology")
    if rule_id == "SC-118":
        return ("出院记录缺项可用结构化字段验证。", "出院记录字段上下文", "discharge_record sections/source_fields")
    if rule_id == "SC-123":
        return ("出院带药细节可用出院带药段落验证。", "出院带药段落", "discharge_record.discharge_order")
    if rule_id == "SC-146":
        return ("医嘱一致性需要病程与医嘱/执行清单对照。", "病程+医嘱/执行清单", "course + inpat orders/execution")
    if rule_id == "SC-107":
        return ("术后连续病程/查房可用手术时间和日期列表验证。", "手术时间+术后日期列表", "surgery_record/mr_surgery + daily/senior course")
    if rule_id == "SC-083":
        return ("四级手术 MDT 需要手术等级和讨论文书证据。", "手术等级+MDT讨论覆盖", "mr_surgery/surgery_record + presurg_discussion")
    return ("高价值规则候选。", "规则专项证据", "bundle source_documents")


def _select_candidates(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    eligible = [
        dict(row)
        for row in rows
        if _safe_text(row.get("display_status")) == "needs_review"
        and _safe_text(row.get("rule_id")).upper() in RULE_PRIORITY
        and _safe_text(row.get("postprocess_label")) in {"evidence_insufficient", "needs_human_review"}
    ]
    selected: list[dict[str, Any]] = []
    used_keys: set[tuple[str, str]] = set()
    for rule_id in RULE_PRIORITY:
        quota = RULE_QUOTAS.get(rule_id, 1)
        rule_rows = [row for row in eligible if _safe_text(row.get("rule_id")).upper() == rule_id]
        rule_rows.sort(key=lambda row: (0 if _safe_text(row.get("status")) == "non_compliant" else 1, _safe_text(row.get("visit_id"))))
        for row in rule_rows[:quota]:
            key = (_safe_text(row.get("visit_id")), _safe_text(row.get("rule_id")))
            if key in used_keys:
                continue
            why, missing, sources = _candidate_reason(row)
            row.update(
                {
                    "original_status": row.get("status", ""),
                    "current_evidence": row.get("evidence", ""),
                    "why_candidate": why,
                    "missing_evidence_type": missing,
                    "expected_supporting_sources": sources,
                }
            )
            selected.append(row)
            used_keys.add(key)
            if len(selected) >= MAX_CANDIDATES:
                return selected
    return selected


def _load_bundle(visit_id: str, visit_keys: dict[str, dict[str, str]]) -> dict[str, Any]:
    mr = visit_keys.get(visit_id) or {}
    patient_id = _safe_text(mr.get("patient_id"))
    institute_id = _safe_text(mr.get("institute_id"))
    if not patient_id or not institute_id:
        return {}
    return assemble_final_record_bundle(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
    )


def _run() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows = _read_csv(INPUT_CSV)
    visit_keys = _load_visit_keys()
    candidates = _select_candidates(rows)
    bundles: dict[str, dict[str, Any]] = {}
    report_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        visit_id = _safe_text(candidate.get("visit_id"))
        bundle = bundles.setdefault(visit_id, _load_bundle(visit_id, visit_keys))
        enriched = _enrich(candidate, bundle) if bundle else _decision(candidate, 0, "", ["本地 bundle 不可用。"], required_gap="需补 bundle。")
        report_rows.append({**candidate, **enriched})
    stats = {
        "candidate_count": len(candidates),
        "support_score_counts": dict(Counter(str(row.get("evidence_support_score")) for row in report_rows)),
        "enhanced_label_counts": dict(Counter(str(row.get("enhanced_postprocess_label")) for row in report_rows)),
        "score_gte_3": sum(1 for row in report_rows if int(row.get("evidence_support_score") or 0) >= 3),
        "still_needs_review": sum(1 for row in report_rows if row.get("enhanced_postprocess_label") == "still_needs_review"),
        "data_gap": sum(1 for row in report_rows if row.get("enhanced_postprocess_label") == "data_gap"),
        "not_supported": sum(1 for row in report_rows if row.get("enhanced_postprocess_label") == "not_supported"),
    }
    return candidates, report_rows, stats


def _md_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_truncate(row.get(col), 160).replace("|", "/") for col in columns) + " |")
    return lines


def _write_report(report_rows: list[dict[str, Any]], stats: dict[str, Any]) -> None:
    promising = [row for row in report_rows if int(row.get("evidence_support_score") or 0) >= 3]
    still = [row for row in report_rows if row.get("enhanced_postprocess_label") == "still_needs_review"]
    data_gap = [row for row in report_rows if row.get("enhanced_postprocess_label") == "data_gap"]
    domain_counter = Counter(_safe_text(row.get("missing_evidence_type")) for row in report_rows)
    lines = [
        "# 正式质控needs_review证据补强回放报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 结论",
        "",
        f"- 本轮选择 needs_review 候选：{stats['candidate_count']} 条。",
        f"- evidence_support_score >= 3：{stats['score_gte_3']} 条。",
        f"- 仍需复核：{stats['still_needs_review']} 条；data_gap：{stats['data_gap']} 条；not_supported：{stats['not_supported']} 条。",
        "- 本轮仅验证证据组织可行性，不接页面、不扩大样本、不放宽准入层。",
        "",
        "## 候选明细与补强结果",
        "",
    ]
    lines += _md_table(
        report_rows,
        ["visit_id", "rule_id", "findings", "evidence_support_score", "enhanced_postprocess_label", "enhanced_reason"],
    )
    lines += ["", "## 可能进入 confirmed_candidate 的问题", ""]
    lines += _md_table(promising, ["visit_id", "rule_id", "findings", "enhanced_reason", "enhanced_evidence"])
    lines += ["", "## 仍需人工复核的问题", ""]
    lines += _md_table(still, ["visit_id", "rule_id", "findings", "missing_evidence_type", "enhanced_reason"])
    lines += ["", "## 数据缺口问题", ""]
    lines += _md_table(data_gap, ["visit_id", "rule_id", "findings", "missing_evidence_type", "enhanced_reason"])
    lines += [
        "",
        "## 需要补强的 bundle 证据域",
        "",
    ]
    lines += _md_table(
        [{"evidence_domain": key, "count": value} for key, value in domain_counter.most_common()],
        ["evidence_domain", "count"],
    )
    lines += [
        "",
        "## 验收问题回答",
        "",
        f"1. 本轮选取 {stats['candidate_count']} 条 needs_review 候选。",
        "2. 最有希望的规则是 `SC-020/SC-125`、`SC-118`、`SC-123` 以及具备完整病程+医嘱对照的 `SC-146`；`SC-107/SC-083` 本轮只补到核对材料，不能确认缺陷。",
        f"3. 补强后 evidence_support_score >= 3 的条目：{stats['score_gte_3']} 条。",
        f"4. 仍为 needs_review：{stats['still_needs_review']} 条。",
        f"5. data_gap：{stats['data_gap']} 条。",
        "6. 需要补强的 bundle 域见上表，重点是异常结果+病程对照、诊断列表+支持证据、出院记录结构字段、医嘱/执行清单；手术时间链和 MDT 仍需更强判定器。",
        "7. 建议下一步将高分规则的 evidence builder 作为正式后处理前置证据构造器设计，但本轮不接正式业务。",
        "8. 仍不建议接页面或扩大样本；需要先把 confirmed_candidate 做人工复核。",
    ]
    with OUTPUT_MD.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    candidates, report_rows, stats = _run()
    _write_csv(OUTPUT_CANDIDATES_CSV, candidates)
    _write_csv(OUTPUT_REPORT_CSV, report_rows)
    _write_json(OUTPUT_REPORT_JSON, {"rows": report_rows, "stats": stats})
    _write_report(report_rows, stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"wrote: {OUTPUT_CANDIDATES_CSV}")
    print(f"wrote: {OUTPUT_REPORT_CSV}")
    print(f"wrote: {OUTPUT_REPORT_JSON}")
    print(f"wrote: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
