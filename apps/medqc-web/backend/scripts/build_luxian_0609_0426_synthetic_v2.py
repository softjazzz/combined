from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import sqlalchemy as sa
from sqlalchemy import MetaData, Table, and_, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import engine  # noqa: E402
from app.services.custom_qc_sample_pool_service import (  # noqa: E402
    CustomQCSamplePoolService,
    _normalize_issue_text,
    _safe_json_dumps,
    _sample_pool_items_table,
    _sample_pools_table,
)
from app.services.bundles.assembly import refresh_domain_bundles_for_rows, refresh_scene_bundles_for_rows  # noqa: E402
from app.services.document_assembly import assemble_document  # noqa: E402


SOURCE_POOL_NAME = "0426"
TARGET_POOL_ID = "luxian-0609-0426-syn-v2"
TARGET_POOL_NAME = "泸县0609真实结构合成样本v2（30）"
TARGET_SOURCE_FILE = "derived://0426/luxian_0609_0426_synthetic_v2"
TARGET_SOURCE_SHEET = "0426-derived"
TARGET_INSTITUTE_ID = "LX0609_0426_SYN"
TARGET_VISIT_PREFIX = "LX0609_0426_SYN_"
TARGET_MR_PREFIX = "LX0609V2-"
TARGET_ITEM_PREFIX = "lx0609-v2"
BUNDLE_POLICY_VERSION = "luxian_0609_0426_syn_v2"
DEID_VERSION = "local-rule-deid-v1"
DEFAULT_OUTPUT_DIR = ROOT / "tmp-lx0609-0426-synthetic-v2"

REAL_GOLDEN_CANDIDATES_PATH = ROOT / "docs" / "0602" / "luxian_0609_real_golden_candidates.json"
GOLDEN_REVIEW_QUEUE_JSON_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_review_queue.json"
GOLDEN_REVIEW_QUEUE_MERGED_CSV_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_review_queue_merged.csv"

FAMILY_QUOTAS: dict[str, int] = {
    "时限": 4,
    "查房/病重病危": 4,
    "检查检验": 4,
    "会诊": 4,
    "手术麻醉": 6,
    "输血": 5,
    "肿瘤病理/化疗": 3,
}

FAMILY_RULE_IDS: dict[str, list[str]] = {
    "时限": ["LX0609-001", "LX0609-002", "LX0609-004", "LX0609-005", "LX0609-006"],
    "查房/病重病危": ["LX0609-007", "LX0609-008", "LX0609-009", "LX0609-016", "LX0609-017", "LX0609-018"],
    "检查检验": ["LX0609-010", "LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"],
    "会诊": ["LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"],
    "手术麻醉": [
        "LX0609-003",
        "LX0609-024",
        "LX0609-025",
        "LX0609-028",
        "LX0609-029",
        "LX0609-030",
        "LX0609-031",
        "LX0609-032",
        "LX0609-033",
        "LX0609-034",
        "LX0609-035",
        "LX0609-036",
        "LX0609-037",
        "LX0609-038",
        "LX0609-039",
        "LX0609-040",
    ],
    "输血": [
        "LX0609-041",
        "LX0609-042",
        "LX0609-043",
        "LX0609-044",
        "LX0609-045",
        "LX0609-046",
        "LX0609-047",
        "LX0609-048",
        "LX0609-049",
    ],
    "肿瘤病理/化疗": ["LX0609-013", "LX0609-019", "LX0609-026", "LX0609-027"],
}

FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "时限": ("入院记录", "首次病程", "48小时", "24小时", "8小时", "时限", "超时"),
    "查房/病重病危": ("查房", "病重", "病危", "病程记录", "复制", "重复"),
    "检查检验": ("CT", "MRI", "检查", "检验", "培养", "阳性", "报告", "细菌"),
    "会诊": ("会诊", "会诊申请", "会诊记录", "会诊意见"),
    "手术麻醉": ("手术", "麻醉", "术前", "术后", "安全核查", "知情同意"),
    "输血": ("输血", "红细胞", "血浆", "配血", "输血同意", "血型"),
    "肿瘤病理/化疗": ("肿瘤", "病理", "化疗", "癌", "恶性", "取材"),
}

FAMILY_KEYWORD_ORDER: tuple[str, ...] = (
    "输血",
    "肿瘤病理/化疗",
    "手术麻醉",
    "会诊",
    "查房/病重病危",
    "检查检验",
    "时限",
)

EXTENDED_SOURCE_TABLES: tuple[str, ...] = (
    "mr",
    "mr_diagnosis",
    "mr_surgery",
    "mr_cost",
    "mr_bloodtrans",
    "patient_information",
    "inpat_registration",
    "diagnosis",
    "admission_record",
    "admission_record_diagnosis",
    "first_course_record",
    "first_course_record_diagnosis",
    "daily_course_record",
    "senior_course_record",
    "summary_record",
    "consultation_record",
    "rescue_record",
    "diffcase_discussion_record",
    "presurg_discussion",
    "presurg_summary",
    "surgery_record",
    "surgery_safecheck_record",
    "surgery_risk_assessment",
    "anesthesia_record",
    "postsurg_firstcourse_record",
    "surgery_application",
    "surgery_inform_consent",
    "consent_form",
    "surgery_inventory_record",
    "preane_surveil_record",
    "postane_surveil_record",
    "docpat_commu_record",
    "exam_master",
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
    "pathology_exam_master",
    "pathology_exam_report",
    "inpat_drug_order",
    "inpat_nondrug_order",
    "inpat_prescription",
    "inpat_prescription_item",
    "inpat_bill_item",
    "blood_application",
    "bloodtrans_record",
    "crisis_value_record",
    "transfer_in_record",
    "transfer_out_record",
    "handoff_record",
    "handover_record",
    "death_record",
    "death_discussion",
    "discharge_record",
    "discharge_record_diagnosis",
)

TEXT_FIELD_MARKERS = (
    "content",
    "text",
    "history",
    "diagnosis",
    "result",
    "findings",
    "impression",
    "conclusion",
    "memo",
    "note",
    "address",
    "contact",
    "telephone",
    "phone",
    "id_card",
    "birthday",
    "birthplace",
    "nativeplace",
    "workplace",
    "work_unit",
    "submitter",
    "doctor",
    "physician",
    "reporter",
    "reviewer",
    "recorder",
    "sign",
    "name",
)

DEID_PATIENT_NAMES = (
    "李某某",
    "陈某某",
    "王某某",
    "赵某某",
    "周某某",
    "刘某某",
    "黄某某",
    "何某某",
    "罗某某",
    "徐某某",
)

MIN_MEANINGFUL_CORE_DOCUMENT_LENGTH = 40
TABLE_MIN_MEANINGFUL_DOCUMENT_LENGTH = {
    "presurg_summary": 180,
    "surgery_application": 80,
    "surgery_inventory_record": 80,
    "pathology_exam_report": 80,
    "consultation_record": 40,
}

FORBIDDEN_TOKENS = (
    "测试患者",
    "模拟患者",
    "为了测试",
    "故意缺失",
    "synthetic_pg_fixture",
)

CORE_DOCUMENT_TABLES = {
    "admission_record",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "consultation_record",
    "rescue_record",
    "presurg_discussion",
    "presurg_summary",
    "surgery_record",
    "surgery_safecheck_record",
    "anesthesia_record",
    "postsurg_firstcourse_record",
    "surgery_application",
    "surgery_inventory_record",
    "surgery_inform_consent",
    "blood_application",
    "bloodtrans_record",
    "pathology_exam_report",
    "discharge_record",
}


@dataclass(frozen=True)
class CandidateCase:
    target_index: int
    family: str
    selected_rule_ids: list[str]
    source_item: dict[str, Any]
    source_reason: str
    source_status: str
    target_visit_id: str
    target_patient_id: str
    target_mr_no: str
    target_patient_name: str


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _json_loads(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = _text(value)
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def _normalize_rule_ids(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw = values.strip()
        if not raw:
            return []
        parsed = _json_loads(raw, None)
        if isinstance(parsed, list):
            values = parsed
        else:
            for sep in ("，", "、", ";", "；", "\n", "\t", " "):
                raw = raw.replace(sep, ",")
            values = raw.split(",")
    if not isinstance(values, Iterable):
        values = [values]
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        rule_id = _text(item).upper()
        if not rule_id or not re.match(r"^LX0609-\d{3}$", rule_id):
            continue
        if rule_id not in seen:
            seen.add(rule_id)
            result.append(rule_id)
    return result


def classify_family(*, rule_ids: Sequence[str], text: str) -> str:
    rule_id_set = {item.upper() for item in rule_ids}
    for family, family_rule_ids in FAMILY_RULE_IDS.items():
        if rule_id_set.intersection(family_rule_ids):
            return family
    upper_text = text.upper()
    for family in FAMILY_KEYWORD_ORDER:
        keywords = FAMILY_KEYWORDS[family]
        if any(keyword.upper() in upper_text for keyword in keywords):
            return family
    return "其他"


def family_rules_from_text(family: str, text: str) -> list[str]:
    rules = list(FAMILY_RULE_IDS.get(family) or [])
    if family == "检查检验":
        if "MRI" in text.upper() or "CT" in text.upper() or "影像" in text:
            return ["LX0609-012"]
        if "培养" in text or "细菌" in text:
            return ["LX0609-014"]
    if family == "输血":
        picked = [rule_id for rule_id in ("LX0609-041", "LX0609-043", "LX0609-044", "LX0609-047", "LX0609-049") if rule_id in rules]
        return picked or rules
    if family == "肿瘤病理/化疗":
        picked = [rule_id for rule_id in ("LX0609-013", "LX0609-019", "LX0609-026") if rule_id in rules]
        return picked or rules
    return rules[:]


def load_source_pool_items(source_pool_name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    service = CustomQCSamplePoolService()
    pools = service.list_pools(query=source_pool_name, page=1, page_size=20).items
    pool = next((item for item in pools if item.get("name") == source_pool_name), None)
    if pool is None:
        pool = next((item for item in pools if item.get("id") == source_pool_name), None)
    if pool is None:
        raise RuntimeError(f"未找到源样本池: {source_pool_name}")

    page = 1
    items: list[dict[str, Any]] = []
    while True:
        result = service.list_pool_items(
            pool_id=str(pool["id"]),
            match_status="matched",
            page=page,
            page_size=100,
        )
        items.extend(result.items)
        if page * result.page_size >= result.total:
            break
        page += 1
    return pool, [item for item in items if _text(item.get("matched_visit_id"))]


def load_existing_candidate_hints() -> dict[str, list[dict[str, Any]]]:
    hints: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if REAL_GOLDEN_CANDIDATES_PATH.exists():
        data = _json_loads(REAL_GOLDEN_CANDIDATES_PATH.read_text(encoding="utf-8"), {})
        for row in list(data.get("candidates") or data.get("items") or data.get("rows") or []):
            if not isinstance(row, dict):
                continue
            visit_id = _text(row.get("visit_id"))
            family = _text(row.get("rule_family"))
            if visit_id and family:
                hints[visit_id].append(row)
        for row in list(data.get("family_coverage") or []):
            if not isinstance(row, dict):
                continue
            family = _text(row.get("rule_family"))
            for visit_id in list(row.get("candidate_visit_ids") or []):
                if _text(visit_id) and family:
                    hints[_text(visit_id)].append(row)

    if GOLDEN_REVIEW_QUEUE_JSON_PATH.exists():
        data = _json_loads(GOLDEN_REVIEW_QUEUE_JSON_PATH.read_text(encoding="utf-8"), {})
        for row in list(data.get("rows") or data.get("candidates") or []):
            if not isinstance(row, dict):
                continue
            visit_id = _text(row.get("visit_id"))
            if visit_id:
                hints[visit_id].append(row)

    if GOLDEN_REVIEW_QUEUE_MERGED_CSV_PATH.exists():
        with GOLDEN_REVIEW_QUEUE_MERGED_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                visit_id = _text(row.get("visit_id"))
                if visit_id:
                    hints[visit_id].append(dict(row))
    return dict(hints)


def candidate_score(item: dict[str, Any], family: str, hints: list[dict[str, Any]]) -> tuple[int, int, int]:
    text = "\n".join(
        [
            _text(item.get("manual_issue_text")),
            _text(item.get("department")),
            _text(item.get("issue_category")),
        ]
    )
    hint_bonus = 2 if hints else 0
    family_bonus = 1 if any(keyword.upper() in text.upper() for keyword in FAMILY_KEYWORDS.get(family, ())) else 0
    ready_bonus = 1 if _text(item.get("bundle_status")) == "ready" else 0
    return hint_bonus, family_bonus, ready_bonus


def build_selection(
    *,
    source_pool: dict[str, Any],
    source_items: list[dict[str, Any]],
    target_size: int,
) -> tuple[list[CandidateCase], dict[str, Any]]:
    hints_by_visit = load_existing_candidate_hints()
    grouped: dict[str, list[tuple[dict[str, Any], list[dict[str, Any]], str]]] = defaultdict(list)
    for item in source_items:
        visit_id = _text(item.get("matched_visit_id"))
        hints = hints_by_visit.get(visit_id, [])
        rule_ids = _normalize_rule_ids(item.get("candidate_rule_ids"))
        text = "\n".join(
            [
                _text(item.get("manual_issue_text")),
                _text(item.get("department")),
                _text(item.get("issue_category")),
                "\n".join(_text(hint.get("trigger_basis") or hint.get("manual_issue_text") or hint.get("customer_text")) for hint in hints),
            ]
        )
        family = classify_family(rule_ids=rule_ids, text=text)
        if family == "其他":
            for candidate_family in FAMILY_QUOTAS:
                if any(keyword.upper() in text.upper() for keyword in FAMILY_KEYWORDS[candidate_family]):
                    family = candidate_family
                    break
        if family in FAMILY_QUOTAS:
            grouped[family].append((item, hints, text))

    selected: list[CandidateCase] = []
    used_visits: set[str] = set()
    source_gaps: dict[str, dict[str, Any]] = {}
    for family, quota in FAMILY_QUOTAS.items():
        pool = sorted(
            grouped.get(family, []),
            key=lambda entry: candidate_score(entry[0], family, entry[1]),
            reverse=True,
        )
        count = 0
        for item, hints, text in pool:
            if count >= quota or len(selected) >= target_size:
                break
            source_visit_id = _text(item.get("matched_visit_id"))
            if not source_visit_id or source_visit_id in used_visits:
                continue
            used_visits.add(source_visit_id)
            selected_rule_ids = _normalize_rule_ids(item.get("candidate_rule_ids"))
            if not selected_rule_ids:
                selected_rule_ids = family_rules_from_text(family, text)
            else:
                selected_rule_ids = [rule_id for rule_id in selected_rule_ids if rule_id in set(FAMILY_RULE_IDS.get(family, []))]
                if not selected_rule_ids:
                    selected_rule_ids = family_rules_from_text(family, text)
            target_index = len(selected) + 1
            patient_name = DEID_PATIENT_NAMES[(target_index - 1) % len(DEID_PATIENT_NAMES)]
            selected.append(
                CandidateCase(
                    target_index=target_index,
                    family=family,
                    selected_rule_ids=selected_rule_ids,
                    source_item=item,
                    source_reason=_text(
                        (hints[0].get("trigger_basis") or hints[0].get("manual_issue_text") or hints[0].get("next_action"))
                        if hints
                        else item.get("manual_issue_text")
                    ),
                    source_status="candidate_ready" if hints else "keyword_discovered",
                    target_visit_id=f"{TARGET_VISIT_PREFIX}{target_index:03d}",
                    target_patient_id=f"P-{TARGET_VISIT_PREFIX}{target_index:03d}",
                    target_mr_no=f"{TARGET_MR_PREFIX}{target_index:03d}",
                    target_patient_name=patient_name,
                )
            )
            count += 1
        if count < quota:
            source_gaps[family] = {
                "quota": quota,
                "selected": count,
                "gap": quota - count,
                "reason": "0426 可匹配且有文书的候选不足，已按关键词二次发现后仍不足。",
            }

    if len(selected) < target_size:
        backfill_pool: list[tuple[str, dict[str, Any], list[dict[str, Any]], str]] = []
        for family, entries in grouped.items():
            for item, hints, text in entries:
                backfill_pool.append((family, item, hints, text))
        backfill_pool.sort(
            key=lambda entry: candidate_score(entry[1], entry[0], entry[2]),
            reverse=True,
        )
        for family, item, hints, text in backfill_pool:
            if len(selected) >= target_size:
                break
            source_visit_id = _text(item.get("matched_visit_id"))
            if not source_visit_id or source_visit_id in used_visits:
                continue
            used_visits.add(source_visit_id)
            selected_rule_ids = _normalize_rule_ids(item.get("candidate_rule_ids"))
            selected_rule_ids = [rule_id for rule_id in selected_rule_ids if rule_id in set(FAMILY_RULE_IDS.get(family, []))]
            if not selected_rule_ids:
                selected_rule_ids = family_rules_from_text(family, text)
            target_index = len(selected) + 1
            patient_name = DEID_PATIENT_NAMES[(target_index - 1) % len(DEID_PATIENT_NAMES)]
            selected.append(
                CandidateCase(
                    target_index=target_index,
                    family=family,
                    selected_rule_ids=selected_rule_ids,
                    source_item=item,
                    source_reason=_text(
                        (hints[0].get("trigger_basis") or hints[0].get("manual_issue_text") or hints[0].get("next_action"))
                        if hints
                        else item.get("manual_issue_text")
                    ),
                    source_status="quota_backfill_due_source_gap",
                    target_visit_id=f"{TARGET_VISIT_PREFIX}{target_index:03d}",
                    target_patient_id=f"P-{TARGET_VISIT_PREFIX}{target_index:03d}",
                    target_mr_no=f"{TARGET_MR_PREFIX}{target_index:03d}",
                    target_patient_name=patient_name,
                )
            )

    return selected, {
        "source_pool": source_pool,
        "source_item_count": len(source_items),
        "grouped_counts": {family: len(items) for family, items in sorted(grouped.items())},
        "selected_counts": dict(Counter(case.family for case in selected)),
        "source_gaps": source_gaps,
    }


def _hash_short(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def _deid_text(value: Any, *, source_identity: dict[str, str], target_identity: dict[str, str]) -> Any:
    if not isinstance(value, str):
        return value
    text = value
    replacements = {
        source_identity.get("patient_name", ""): target_identity["patient_name"],
        source_identity.get("mr_no", ""): target_identity["mr_no"],
        source_identity.get("visit_id", ""): target_identity["visit_id"],
        source_identity.get("patient_id", ""): target_identity["patient_id"],
        source_identity.get("doctor_name", ""): "陈某医师",
        source_identity.get("qc_user", ""): "质控员",
    }
    for old, new in replacements.items():
        if old:
            text = text.replace(old, new)
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "13800000000", text)
    text = re.sub(r"(?<!\d)\d{17}[\dXx](?!\d)", "510000********0000", text)
    text = re.sub(r"(?<!\d)\d{15}(?!\d)", "510000********000", text)
    text = re.sub(r"[\u4e00-\u9fa5]{0,8}(省|市|县|区|镇|乡|街道|路|村|组)[\u4e00-\u9fa5A-Za-z0-9\-号栋单元室]{2,40}", "四川省泸州市某县某街道", text)
    return text


def _needs_deid(column_name: str) -> bool:
    lower_name = column_name.lower()
    return any(marker in lower_name for marker in TEXT_FIELD_MARKERS)


def _quality_text(table_name: str, row: dict[str, Any]) -> str:
    if table_name in CORE_DOCUMENT_TABLES:
        try:
            assembled = assemble_document(table_name, row)
            if _text(assembled.assembled_text):
                return _text(assembled.assembled_text)
        except Exception:
            pass
    return _text(row.get("record_content") or row.get("content") or row.get("diagnosis") or row.get("result"))


def is_meaningful_core_document(table_name: str, row: dict[str, Any]) -> bool:
    if table_name not in CORE_DOCUMENT_TABLES:
        return True
    text_value = _quality_text(table_name, row)
    min_length = TABLE_MIN_MEANINGFUL_DOCUMENT_LENGTH.get(table_name, MIN_MEANINGFUL_CORE_DOCUMENT_LENGTH)
    if len(text_value) < min_length:
        return False
    title = _text(row.get("document_title") or row.get("title") or row.get("record_title"))
    if title and text_value == title:
        return False
    return True


def _dt_for_case(case: CandidateCase, day_offset: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, 1 + day_offset, hour, minute)


def _case_base_row(case: CandidateCase) -> dict[str, Any]:
    item = case.source_item
    return {
        "institute_id": TARGET_INSTITUTE_ID,
        "patient_id": case.target_patient_id,
        "visit_id": case.target_visit_id,
        "visit_type": "I",
        "inpat_no": case.target_mr_no,
        "mr_no": case.target_mr_no,
        "name": case.target_patient_name,
        "sex": item.get("sex") or "男",
        "age_year": item.get("age_year") or "62",
        "dept_name": item.get("department") or item.get("dept_name") or "普通外科",
        "last_modifier": "陈某医师",
        "last_modifier_id": "DEID",
        "last_modified_datetime": _dt_for_case(case, 0, 9),
        "update_time": _dt_for_case(case, 0, 9),
    }


def _has_meaningful_rows(rows_by_table: dict[str, list[dict[str, Any]]], table_name: str, case: CandidateCase) -> bool:
    rows = [
        row
        for row in rows_by_table.get(table_name, [])
        if row.get("visit_id") == case.target_visit_id
    ]
    if not rows:
        return False
    return any(is_meaningful_core_document(table_name, row) for row in rows)


def _append_row(rows_by_table: dict[str, list[dict[str, Any]]], table_name: str, row: dict[str, Any]) -> None:
    rows_by_table.setdefault(table_name, []).append(row)


def _family_diagnosis(case: CandidateCase) -> tuple[str, str]:
    if case.family == "检查检验":
        return "腰椎间盘突出症", "M51.202"
    if case.family == "会诊":
        return "胆总管结石伴胆管炎", "K80.501"
    if case.family == "手术麻醉":
        return "股骨骨折", "S72.900"
    if case.family == "查房/病重病危":
        return "重症肺炎", "J18.900"
    if case.family == "输血":
        return "胃恶性肿瘤伴贫血", "C16.900"
    if case.family == "肿瘤病理/化疗":
        return "胃腺癌", "C16.900"
    return "脑梗死", "I63.900"


def supplement_first_course_rows(rows_by_table: dict[str, list[dict[str, Any]]], case: CandidateCase) -> list[dict[str, Any]]:
    added: list[dict[str, Any]] = []
    if _has_meaningful_rows(rows_by_table, "first_course_record", case):
        return added
    base = _case_base_row(case)
    record_time = _dt_for_case(case, 0, 16, 0)
    diagnosis_name, diagnosis_code = _family_diagnosis(case)
    context_by_family = {
        "时限": (
            "患者急性起病入院，主诉与入院诊断记录较完整，入院后需尽快完成入院记录、首次病程及上级医师查房等时限性文书。入院时生命体征基本平稳，但存在基础疾病和病情变化风险，需结合入院时间、记录时间、提交时间连续核对文书完成情况。",
            "根据入院主诉、专科查体、初步辅助检查及既往病史，当前诊断方向基本明确。首次病程需围绕病例特点、诊断依据和后续处理计划形成完整闭环，并与入院记录、查房记录保持时间线一致。",
            "需与症状相近的急性发作性疾病、慢性疾病急性加重、药物或代谢因素导致的不适相鉴别。若后续检查结果与初步判断不一致，应在病程中及时修正诊断并补充鉴别依据。",
            "完善血常规、生化、凝血、心电图及专科相关检查；根据病情给予对症治疗和风险监测。重点核对入院后24小时内入院记录、8小时内首次病程及48小时内上级医师首次查房记录是否完成，超时或缺失需纳入质控复核。",
        ),
        "检查检验": (
            "患者因腰痛伴右下肢麻木入院，疼痛活动后加重，休息后稍缓解。查体腰椎活动受限，右下肢直腿抬高试验阳性，末梢感觉较对侧减退。入院后拟完善腰椎MRI、感染指标、尿培养及药敏等检查，以判断神经受压和感染相关因素。",
            "依据腰痛及神经根受压体征，结合既往影像提示腰椎退变，初步考虑腰椎间盘突出症。后续需结合MRI报告明确突出节段、硬膜囊受压程度及神经根受累情况，同时结合细菌培养结果判断是否需要调整抗感染方案。",
            "需与腰椎管狭窄、梨状肌综合征、周围神经病变、泌尿系感染相关腰痛及骨质疏松性压缩骨折相鉴别。若出现发热、尿路刺激征或炎症指标升高，应结合培养结果重新评估感染来源。",
            "完善腰椎MRI、血常规、尿常规、尿培养及药敏；予止痛、营养神经、卧床休息和康复指导。检查检验报告出具后，应在24小时内于病程中记录阳性结果、临床意义、治疗调整依据和患者病情变化，避免报告回看缺失。",
        ),
        "会诊": (
            "患者腹痛、发热入院，伴食欲下降和乏力，查体右上腹压痛明显。实验室检查提示炎症指标及胆红素升高，影像提示胆道扩张可能。入院后需请相关专科协助评估是否存在胆总管梗阻、感染控制风险及内镜或手术干预指征。",
            "根据右上腹疼痛、发热、胆红素及炎症指标升高，结合胆道影像异常，初步诊断胆总管结石伴胆管炎。会诊申请需明确会诊目的、待解决问题和期望专科给出的处理建议。",
            "需与急性胰腺炎、急性胆囊炎、消化性溃疡穿孔、肝脓肿及急性胃肠炎鉴别。若腹痛范围扩大、黄疸加重或感染指标持续升高，应及时调整诊疗策略并再次评估会诊必要性。",
            "予抗感染、补液、解痉、监测体温及肝胆胰酶，完善腹部影像。申请消化内镜或普外科会诊后，应在后续病程中记录会诊意见是否执行、执行时间、执行结果及未执行原因，避免会诊目的不清、意见笼统或执行记录缺失。",
        ),
        "手术麻醉": (
            "患者外伤后局部疼痛、肿胀及活动受限入院，患肢负重困难，局部压痛明显。影像学提示骨折，需评估手术适应证、麻醉风险、围手术期出血和血栓风险。入院后需完成术前小结、术前讨论、手术记录、麻醉记录和术后首次病程等关键文书。",
            "根据明确外伤史、局部压痛畸形、活动障碍及影像学骨折征象，初步诊断股骨骨折。诊断依据还需结合血常规、凝血功能、心肺功能评估和麻醉访视结果，判断患者是否具备手术条件。",
            "需与软组织挫伤、病理性骨折、骨肿瘤、既往陈旧骨折及骨质疏松性骨折相鉴别。若术前评估提示贫血、凝血异常或心肺功能风险，应调整手术时机并记录处理意见。",
            "完善血常规、凝血、心电图、胸片、麻醉评估和手术风险告知；评估手术适应证后择期行切开复位内固定术。术后严密观察切口渗血、疼痛、下肢血运、麻醉恢复和并发症，并按时完成手术记录、麻醉记录及术后病程。",
        ),
        "查房/病重病危": (
            "患者因发热、咳嗽、咳痰伴气促入院，入院时精神差，氧饱和度下降，双肺可闻及湿啰音，炎症指标升高，影像提示肺部感染。患者年龄偏大并伴基础疾病，存在病情进展、呼吸衰竭和感染性休克风险，需按病重病危管理要求连续观察。",
            "依据感染症状、肺部湿啰音、影像炎症改变、低氧表现及实验室炎症指标升高，初步诊断重症肺炎。病情评估需结合体温、呼吸频率、血压、氧合指数、尿量和意识状态动态判断。",
            "需与肺栓塞、急性心力衰竭、慢阻肺急性加重、肺结核及间质性肺炎急性加重鉴别。若呼吸困难加重或氧合下降，应及时复查血气、胸部影像和心功能相关指标。",
            "予吸氧、抗感染、祛痰、补液、营养支持和生命体征监测；根据培养结果调整抗感染方案。病重/病危期间应按规定完成查房和病程记录，记录病情变化、治疗反应、上级医师意见、危急值处理及家属沟通情况。",
        ),
        "输血": (
            "患者因胃部肿瘤相关贫血入院，诉乏力、活动后心悸，血红蛋白下降，术前评估存在输血指征。入院后需完善血型鉴定、交叉配血、输血前感染筛查、输血知情同意和输血风险评估，并核对输血医嘱与收费项目。",
            "结合胃部肿瘤病史、贫血症状、血红蛋白降低及围手术期失血风险，初步诊断胃恶性肿瘤伴贫血。是否输血需根据贫血程度、症状、手术计划及患者基础心肺功能综合判断。",
            "需与营养性贫血、慢性失血性贫血、骨髓抑制、溶血性贫血及肿瘤相关炎症性贫血鉴别。若输血后血红蛋白提升不明显，应复查血常规并评估持续出血或溶血可能。",
            "完善ABO/Rh血型、交叉配血、乙肝/丙肝/HIV/梅毒等输血前检查及知情同意；按医嘱输注红细胞并记录输血开始结束时间、过程观察、疗效评价、不良反应和输血后复查结果，同时核对医嘱、病程记录和收费数量一致性。",
        ),
        "肿瘤病理/化疗": (
            "患者因上腹不适、食欲下降、体重减轻入院，胃镜提示胃窦占位，影像考虑胃部恶性病变可能。拟完善术前评估后行手术治疗，术后需根据病理类型、浸润深度、切缘和淋巴结情况决定后续肿瘤治疗方案。",
            "依据胃镜占位、临床消瘦、肿瘤标志物异常及影像提示胃部病灶，初步诊断胃腺癌可能。病理报告是明确诊断和分期的重要依据，术后病程需及时回看病理结果并记录取材情况。",
            "需与胃溃疡、胃间质瘤、胃淋巴瘤、慢性胃炎伴糜烂及转移性胃部病变鉴别。若病理结果与术前判断不一致，应结合免疫组化和多学科讨论修正治疗计划。",
            "完善肿瘤标志物、增强CT、心肺功能及术前评估；术后关注病理报告、切缘、淋巴结分组和取材记录，结合TNM分期制定化疗或随访方案。若开具化疗医嘱，病程中需同步记录药物名称、剂量、使用方法、时间和疗效/不良反应观察。",
        ),
    }
    case_characteristic, diagnose_based_on, differential_diagnosis, treatment_plan = context_by_family.get(
        case.family,
        (
            "患者急性起病，存在神经系统定位体征，入院后需完善影像及实验室检查评估病情。",
            "根据主诉、体格检查及既往基础疾病情况，初步考虑脑梗死。",
            "需与短暂性脑缺血发作、颅内出血、低血糖反应和周围性眩晕鉴别。",
            "完善头颅影像、血常规、凝血及心电检查，予抗血小板、调脂、改善循环及康复评估，动态记录病情变化。",
        ),
    )
    document_id = f"{case.target_visit_id}-first_course_record-supp-001"
    row = {
        **base,
        "document_id": document_id,
        "document_title": "首次病程记录",
        "document_status": "Submitted",
        "submitter": "陈某医师",
        "submitter_id": "DEID",
        "submit_datetime": record_time,
        "record_time": record_time,
        "record_datetime": record_time,
        "dept_name": base["dept_name"],
        "ward_name": "普通病区",
        "ward_no": "A",
        "bed_no": f"{case.target_index:02d}",
        "case_characteristic": case_characteristic,
        "diagnosis_discussion": diagnose_based_on,
        "checkup": "入院查体及专科查体已记录，生命体征和阳性体征需结合后续病程动态复核。",
        "assist_exam": "入院后完善血常规、生化、凝血、心电图及专科相关检查，部分报告待回报。",
        "diagnose_based_on": diagnose_based_on,
        "differential_diagnosis": differential_diagnosis,
        "treatment_plan": treatment_plan,
        "record_content": "",
        "physician_sign": "陈某医师",
        "physician_sign_datetime": record_time,
        "last_modified_datetime": record_time,
        "update_time": record_time,
    }
    _append_row(rows_by_table, "first_course_record", row)
    added.append({"table": "first_course_record", "reason": "supplement_first_course_record"})
    diagnosis_row = {
        **base,
        "document_id": document_id,
        "diagnosis_id": f"{case.target_visit_id}-first-course-diagnosis-supp-001",
        "dept_name": base["dept_name"],
        "ward_name": "普通病区",
        "ward_no": "A",
        "bed_no": f"{case.target_index:02d}",
        "diagnosis_main": "1",
        "diagnosis_type": "初步诊断",
        "diagnosis_no": "1",
        "diagnosis_name": diagnosis_name,
        "diagnosis_code": diagnosis_code,
        "diagnosis_source": "supplement_first_course_record",
        "diagnosis_time": record_time.isoformat(sep=" "),
        "diagnosis_uptime": record_time.isoformat(sep=" "),
        "record_time": record_time.isoformat(sep=" "),
        "update_time": record_time.isoformat(sep=" "),
    }
    _append_row(rows_by_table, "first_course_record_diagnosis", diagnosis_row)
    added.append({"table": "first_course_record_diagnosis", "reason": "supplement_first_course_diagnosis"})
    return added


def supplement_exam_lab_rows(rows_by_table: dict[str, list[dict[str, Any]]], case: CandidateCase) -> list[dict[str, Any]]:
    added: list[dict[str, Any]] = []
    base = _case_base_row(case)
    if not _has_meaningful_rows(rows_by_table, "exam_item_report", case):
        report_time = _dt_for_case(case, 1, 14, 20)
        row = {
            **base,
            "document_id": f"{case.target_visit_id}-exam_item_report-supp-001",
            "document_title": "腰椎MRI检查报告",
            "document_status": "Submitted",
            "submitter": "陈某医师",
            "submitter_id": "DEID",
            "submit_datetime": report_time,
            "record_time": report_time.isoformat(sep=" "),
            "exam_no": f"EX-{case.target_index:03d}",
            "exam_id": f"EX-{case.target_index:03d}",
            "item_no": "1",
            "item_id": f"EXITEM-{case.target_index:03d}",
            "item_code": "MRI-LSPINE",
            "item_name": "腰椎MRI平扫",
            "exam_name": "腰椎MRI检查",
            "exam_item_name": "腰椎MRI平扫",
            "exam_type": "MRI",
            "exam_findings": "腰椎生理曲度变直，L4/5椎间盘向右后方突出，硬膜囊受压，右侧神经根受压；椎管轻度狭窄。",
            "exam_impression": "L4/5椎间盘突出并右侧神经根受压。",
            "exam_conclusion": "L4/5椎间盘突出并右侧神经根受压，建议结合临床症状及体征分析。",
            "record_content": "腰椎MRI提示L4/5椎间盘向右后方突出，右侧神经根受压。报告出具后病程记录未见24小时内针对阳性影像结果进行分析。",
            "report_time": report_time,
        }
        _append_row(rows_by_table, "exam_item_report", row)
        added.append({"table": "exam_item_report", "reason": "supplement_exam_report"})
    if not _has_meaningful_rows(rows_by_table, "labtest_item_report", case):
        report_time = _dt_for_case(case, 2, 10, 30)
        row = {
            **base,
            "document_id": f"{case.target_visit_id}-labtest_item_report-supp-001",
            "document_title": "尿培养及药敏报告",
            "document_status": "Submitted",
            "submitter": "陈某医师",
            "submitter_id": "DEID",
            "submit_datetime": report_time,
            "record_time": report_time.isoformat(sep=" "),
            "test_no": f"LAB-{case.target_index:03d}",
            "test_id": f"LAB-{case.target_index:03d}",
            "item_no": "1",
            "item_id": f"LABITEM-{case.target_index:03d}",
            "item_code": "URINE-CULTURE",
            "item_name": "尿培养+药敏",
            "item_abbreviation": "尿培养",
            "result": "大肠埃希菌阳性；对头孢曲松敏感，对左氧氟沙星耐药。",
            "unit": "",
            "reference_range": "阴性",
            "abnormal_indicator": "阳性",
            "record_content": "尿培养结果：大肠埃希菌阳性。药敏：头孢曲松敏感，左氧氟沙星耐药。报告出具后病程记录未见24小时内记录培养结果分析和抗感染方案调整依据。",
            "report_time": report_time,
            "report_datetime": report_time,
        }
        _append_row(rows_by_table, "labtest_item_report", row)
        added.append({"table": "labtest_item_report", "reason": "supplement_lab_report"})
    return added


def supplement_blood_rows(rows_by_table: dict[str, list[dict[str, Any]]], case: CandidateCase) -> list[dict[str, Any]]:
    added: list[dict[str, Any]] = []
    base = _case_base_row(case)
    if not _has_meaningful_rows(rows_by_table, "blood_application", case):
        request_time = _dt_for_case(case, 1, 11, 0)
        row = {
            **base,
            "application_id": f"{case.target_visit_id}-blood-application-supp-001",
            "dept_name": base["dept_name"],
            "patient_bloodtype_abo": "A",
            "patient_bloodtype_rhd": "阳性",
            "transfuse_variety": "去白悬浮红细胞",
            "transfuse_volume": "2",
            "transfuse_volume_unit": "U",
            "request_datetime": request_time,
            "physician_name": "陈某医师",
            "record_content": "输血申请：患者血红蛋白68g/L，拟输注去白悬浮红细胞2U。申请单记录ABO血型A型、Rh(D)阳性，但输血前感染筛查项目记录不完整，未见完整输血知情同意书归档。",
            "last_modified_datetime": request_time,
            "update_time": request_time,
        }
        _append_row(rows_by_table, "blood_application", row)
        added.append({"table": "blood_application", "reason": "supplement_blood_application"})
    if not _has_meaningful_rows(rows_by_table, "inpat_bill_item", case):
        billing_time = _dt_for_case(case, 1, 17, 20)
        for index, (name, quantity, cost) in enumerate(
            [("去白悬浮红细胞", "4", "1680.00"), ("交叉配血", "1", "80.00")],
            start=1,
        ):
            row = {
                **base,
                "bill_item_id": f"{case.target_visit_id}-bill-supp-{index:03d}",
                "receipt_id": f"RCPT-{case.target_index:03d}",
                "order_id": f"{case.target_visit_id}-blood-order-supp-001",
                "item_type": "输血",
                "medical_catalog_name": name,
                "medinsur_catalog_name": name,
                "item_specification": "U" if "红细胞" in name else "次",
                "quantity": quantity,
                "quantity_unit": "U" if "红细胞" in name else "次",
                "unit_price": "420.00" if "红细胞" in name else "80.00",
                "cost": cost,
                "charge": cost,
                "billing_datetime": billing_time,
                "order_dept_name": base["dept_name"],
                "executive_dept_name": "输血科",
                "record_content": f"费用明细：{name} {quantity}{'U' if '红细胞' in name else '次'}，用于核对输血医嘱与收费一致性。",
                "last_modified_datetime": billing_time,
                "update_time": billing_time,
            }
            _append_row(rows_by_table, "inpat_bill_item", row)
        added.append({"table": "inpat_bill_item", "reason": "supplement_blood_bill_items"})
    return added


def supplement_pathology_rows(rows_by_table: dict[str, list[dict[str, Any]]], case: CandidateCase) -> list[dict[str, Any]]:
    added: list[dict[str, Any]] = []
    base = _case_base_row(case)
    report_time = _dt_for_case(case, 3, 9, 30)
    pathology_exam_id = f"PATH-{case.target_index:03d}"
    if not _has_meaningful_rows(rows_by_table, "pathology_exam_master", case):
        row = {
            **base,
            "pathology_exam_id": pathology_exam_id,
            "pathology_id": pathology_exam_id,
            "clinical_history": "胃窦占位，行胃癌根治术后送检。",
            "surgery_name": "腹腔镜远端胃癌根治术",
            "specimen_name": "远端胃及淋巴结",
            "request_dept": base["dept_name"],
            "request_physician": "陈某医师",
            "request_datetime": _dt_for_case(case, 2, 16, 0),
            "record_content": "病理检查申请：胃窦占位术后标本，送检远端胃及淋巴结，需明确肿瘤类型、浸润深度及淋巴结转移情况。",
        }
        _append_row(rows_by_table, "pathology_exam_master", row)
        added.append({"table": "pathology_exam_master", "reason": "supplement_pathology_master"})
    if not _has_meaningful_rows(rows_by_table, "pathology_exam_report", case):
        row = {
            **base,
            "pathology_exam_id": pathology_exam_id,
            "pathology_id": pathology_exam_id,
            "specimen_name": "远端胃及淋巴结",
            "eye_findings": "远端胃标本见胃窦部溃疡型肿物，切面灰白质硬。",
            "microscope_findings": "肿瘤腺管样排列，细胞异型明显，浸润至浆膜下层，部分淋巴结见转移癌。",
            "diagnosis": "胃中分化腺癌，浸润至浆膜下层，淋巴结转移2/18。",
            "report_status": "Final",
            "report_datetime": report_time,
            "reporter": "陈某医师",
            "review_datetime": report_time,
            "reviewer": "陈某医师",
            "record_content": "病理诊断：胃中分化腺癌，浸润至浆膜下层，淋巴结转移2/18。报告出具后病程记录未见病理结果回看、取材情况说明及后续肿瘤治疗计划。",
            "last_modified_datetime": report_time,
            "update_time": report_time,
        }
        _append_row(rows_by_table, "pathology_exam_report", row)
        added.append({"table": "pathology_exam_report", "reason": "supplement_pathology_report"})
    return added


def add_supplemental_evidence_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
    cases: Sequence[CandidateCase],
) -> list[dict[str, Any]]:
    supplements: list[dict[str, Any]] = []
    for case in cases:
        added: list[dict[str, Any]] = supplement_first_course_rows(rows_by_table, case)
        if case.family == "检查检验":
            added.extend(supplement_exam_lab_rows(rows_by_table, case))
        elif case.family == "输血":
            added.extend(supplement_blood_rows(rows_by_table, case))
        elif case.family == "肿瘤病理/化疗":
            added.extend(supplement_pathology_rows(rows_by_table, case))
        for item in added:
            supplements.append(
                {
                    "target_visit_id": case.target_visit_id,
                    "source_visit_id": _text(case.source_item.get("matched_visit_id")),
                    "rule_family": case.family,
                    **item,
                }
            )
    return supplements


def _target_identity(case: CandidateCase) -> dict[str, str]:
    return {
        "institute_id": TARGET_INSTITUTE_ID,
        "patient_id": case.target_patient_id,
        "visit_id": case.target_visit_id,
        "mr_no": case.target_mr_no,
        "inpat_no": case.target_mr_no,
        "patient_name": case.target_patient_name,
        "name": case.target_patient_name,
    }


def _source_identity(case: CandidateCase) -> dict[str, str]:
    item = case.source_item
    raw_payload = item.get("raw_payload") if isinstance(item.get("raw_payload"), dict) else {}
    return {
        "institute_id": _text(item.get("matched_institute_id") or raw_payload.get("institute_id")),
        "patient_id": _text(item.get("matched_patient_id") or raw_payload.get("patient_id")),
        "visit_id": _text(item.get("matched_visit_id") or raw_payload.get("visit_id")),
        "mr_no": _text(item.get("mr_no") or raw_payload.get("mr_no")),
        "patient_name": _text(item.get("patient_name") or raw_payload.get("patient_name")),
        "doctor_name": _text(item.get("doctor_name") or raw_payload.get("doctor_name")),
        "qc_user": _text(item.get("qc_user") or raw_payload.get("qc_user")),
    }


def reflect_table(table_name: str, metadata: MetaData) -> Table | None:
    try:
        return Table(table_name, metadata, autoload_with=engine)
    except Exception:
        return None


def fetch_source_rows(case: CandidateCase, table_name: str, table: Table, session: Session) -> list[dict[str, Any]]:
    if "visit_id" not in table.c:
        return []
    source_visit_id = _text(case.source_item.get("matched_visit_id"))
    if not source_visit_id:
        return []
    rows = session.execute(select(table).where(table.c.visit_id == source_visit_id)).mappings().all()
    return [dict(row) for row in rows]


def transform_row(
    *,
    table: Table,
    table_name: str,
    source_row: dict[str, Any],
    case: CandidateCase,
    row_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_identity = _source_identity(case)
    target_identity = _target_identity(case)
    row: dict[str, Any] = {}
    changed_fields: list[str] = []
    pk_columns = {column.name for column in table.primary_key.columns}
    columns = set(table.c.keys())
    for column in columns:
        value = source_row.get(column)
        lower = column.lower()
        column_type = table.c[column].type
        if column == "institute_id":
            value = TARGET_INSTITUTE_ID
        elif column == "patient_id":
            value = case.target_patient_id
        elif column == "visit_id":
            value = case.target_visit_id
        elif column in {"mr_no", "inpat_no", "hospitalization_no"}:
            value = case.target_mr_no
        elif column in {"name", "patient_name"}:
            value = case.target_patient_name
        elif column == "birthday":
            value = date(1960 + (case.target_index % 30), 1, 1)
        elif "id_card" in lower or "identity" in lower:
            value = "510000********0000"
        elif any(marker in lower for marker in ("telephone", "phone", "contact_number")):
            value = "13800000000"
        elif any(marker in lower for marker in ("address", "currentaddress", "birthplace", "nativeplace", "workplace", "work_unit")):
            value = "四川省泸州市某县某街道"
        elif any(marker in lower for marker in ("submitter", "doctor", "physician", "reporter", "reviewer", "recorder", "surgeon", "anesthesiologist")):
            if isinstance(value, str) and _text(value):
                value = "陈某医师"
        elif "sign" in lower:
            if isinstance(value, str) and _text(value):
                value = "已脱敏签名"
        elif column in pk_columns and value is not None:
            if isinstance(column_type, sa.Integer):
                value = case.target_index * 100000 + row_index * 100 + len(row)
            else:
                value = f"{case.target_visit_id}-{table_name}-{column}-{row_index:03d}"
        elif column == "document_id":
            value = f"{case.target_visit_id}-{table_name}-{row_index:03d}"
        elif column.endswith("_id") and column not in {"patient_id", "visit_id"} and isinstance(value, str):
            value = f"{case.target_visit_id}-{column}-{row_index:03d}"
        elif isinstance(value, str) and _needs_deid(column):
            new_value = _deid_text(value, source_identity=source_identity, target_identity=target_identity)
            if new_value != value:
                changed_fields.append(column)
            value = new_value
        row[column] = value
    return row, {"changed_fields": changed_fields}


def build_clone_rows(cases: Sequence[CandidateCase]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    metadata = MetaData()
    rows_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    audit: dict[str, Any] = {
        "cases": [],
        "tables": {},
        "warnings": [],
        "skipped_shell_documents": [],
        "supplemental_evidence_rows": [],
    }
    with Session(engine) as session:
        for table_name in EXTENDED_SOURCE_TABLES:
            table = reflect_table(table_name, metadata)
            if table is None:
                audit["warnings"].append({"table": table_name, "warning": "table_reflection_failed"})
                continue
            for case in cases:
                source_rows = fetch_source_rows(case, table_name, table, session)
                for row_index, source_row in enumerate(source_rows, start=1):
                    transformed, row_audit = transform_row(
                        table=table,
                        table_name=table_name,
                        source_row=source_row,
                        case=case,
                        row_index=row_index,
                    )
                    if not is_meaningful_core_document(table_name, transformed):
                        audit["skipped_shell_documents"].append(
                            {
                                "target_visit_id": case.target_visit_id,
                                "source_visit_id": _text(case.source_item.get("matched_visit_id")),
                                "table": table_name,
                                "document_id": _text(transformed.get("document_id") or source_row.get("document_id")),
                                "document_title": _text(transformed.get("document_title") or source_row.get("document_title")),
                                "assembled_length": len(_quality_text(table_name, transformed)),
                                "preview": _quality_text(table_name, transformed)[:80],
                            }
                        )
                        continue
                    rows_by_table[table_name].append(transformed)
                    if row_audit["changed_fields"]:
                        audit["tables"].setdefault(table_name, Counter()).update(row_audit["changed_fields"])

        audit["supplemental_evidence_rows"] = add_supplemental_evidence_rows(rows_by_table, cases)

        for case in cases:
            source_table_counts = Counter(
                table_name for table_name, rows in rows_by_table.items() for row in rows if row.get("visit_id") == case.target_visit_id
            )
            text_lengths = []
            core_text_lengths = []
            first_course_lengths = []
            for rows in rows_by_table.values():
                for row in rows:
                    if row.get("visit_id") != case.target_visit_id:
                        continue
                    text_value = _quality_text("structured", row)
                    if text_value:
                        text_lengths.append(len(text_value))
            for table_name, rows in rows_by_table.items():
                if table_name not in CORE_DOCUMENT_TABLES:
                    continue
                for row in rows:
                    if row.get("visit_id") != case.target_visit_id:
                        continue
                    text_value = _quality_text(table_name, row)
                    if text_value:
                        core_text_lengths.append(len(text_value))
                        if table_name == "first_course_record":
                            first_course_lengths.append(len(text_value))
            audit["cases"].append(
                {
                    "target_visit_id": case.target_visit_id,
                    "source_visit_id": _text(case.source_item.get("matched_visit_id")),
                    "family": case.family,
                    "selected_rule_ids": case.selected_rule_ids,
                    "row_count": sum(source_table_counts.values()),
                    "source_tables": dict(sorted(source_table_counts.items())),
                    "document_count_after_fetch": "pending_db_write",
                    "min_text_length": min(text_lengths) if text_lengths else 0,
                    "short_text_rows": sum(1 for length in text_lengths if length < 180),
                    "core_document_count": len(core_text_lengths),
                    "min_core_document_length": min(core_text_lengths) if core_text_lengths else 0,
                    "max_core_document_length": max(core_text_lengths) if core_text_lengths else 0,
                    "long_core_document_count": sum(1 for length in core_text_lengths if length >= 300),
                    "short_core_documents": sum(1 for length in core_text_lengths if length < 180),
                    "first_course_record_count": len(first_course_lengths),
                    "min_first_course_record_length": min(first_course_lengths) if first_course_lengths else 0,
                }
            )
    audit["tables"] = {
        table_name: dict(counter)
        for table_name, counter in sorted(audit["tables"].items())
    }
    return dict(rows_by_table), audit


def upsert_rows(session: Session, table: Table, rows: Sequence[dict[str, Any]]) -> int:
    if not rows:
        return 0
    allowed = set(table.c.keys())
    normalized_rows = [{key: row.get(key) for key in allowed if key in row and row.get(key) is not None} for row in rows]
    normalized_rows = [row for row in normalized_rows if row]
    if not normalized_rows:
        return 0
    insert_columns = sorted({key for row in normalized_rows for key in row.keys()})
    payload_rows = [{column: row.get(column) for column in insert_columns} for row in normalized_rows]
    pk_columns = [column.name for column in table.primary_key.columns]
    stmt = pg_insert(table).values(payload_rows)
    update_columns = [column for column in insert_columns if column not in pk_columns]
    if pk_columns and update_columns:
        stmt = stmt.on_conflict_do_update(
            index_elements=pk_columns,
            set_={column: getattr(stmt.excluded, column) for column in update_columns},
        )
    elif pk_columns:
        stmt = stmt.on_conflict_do_nothing(index_elements=pk_columns)
    session.execute(stmt)
    return len(payload_rows)


def delete_target_visit_rows(session: Session, metadata: MetaData, cases: Sequence[CandidateCase]) -> dict[str, int]:
    target_visit_ids = [case.target_visit_id for case in cases]
    deleted_tables: dict[str, int] = {}
    if not target_visit_ids:
        return deleted_tables
    for table_name in EXTENDED_SOURCE_TABLES:
        table = reflect_table(table_name, metadata)
        if table is None or "visit_id" not in table.c:
            continue
        result = session.execute(delete(table).where(table.c.visit_id.in_(target_visit_ids)))
        deleted_count = int(result.rowcount or 0)
        if deleted_count:
            deleted_tables[table_name] = deleted_count
    return deleted_tables


def write_pool_and_items(
    *,
    source_pool: dict[str, Any],
    cases: Sequence[CandidateCase],
    rows_by_table: dict[str, list[dict[str, Any]]],
    supplemental_rows: Sequence[dict[str, Any]],
    replace_items: bool,
) -> dict[str, Any]:
    pool_table = _sample_pools_table()
    item_table = _sample_pool_items_table()
    metadata = MetaData()
    inserted_tables: dict[str, int] = {}
    deleted_tables: dict[str, int] = {}
    bundle_status_by_item: dict[str, str] = {}
    bundle_errors: dict[str, str] = {}
    supplemental_by_visit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in supplemental_rows:
        supplemental_by_visit[_text(item.get("target_visit_id"))].append(dict(item))
    now = datetime.now()
    with Session(engine) as session:
        existing = session.execute(select(pool_table.c.id).where(pool_table.c.id == TARGET_POOL_ID)).first()
        pool_values = {
            "id": TARGET_POOL_ID,
            "name": TARGET_POOL_NAME,
            "source_file": TARGET_SOURCE_FILE,
            "source_sheet": TARGET_SOURCE_SHEET,
            "scene": "running",
            "description": "基于 0426 样本池真实文书结构本地脱敏改写生成，仅用于 LX0609 客户演示和合成回归，不代表真实样本准确率。",
            "created_by": "system",
            "updated_at": now,
        }
        if existing:
            session.execute(update(pool_table).where(pool_table.c.id == TARGET_POOL_ID).values(**pool_values))
        else:
            session.execute(
                pool_table.insert().values(
                    **pool_values,
                    created_at=now,
                    total_items=0,
                    llm_intrinsic_items=0,
                    programmatic_items=0,
                    unsupported_items=0,
                    matched_items=0,
                    ambiguous_items=0,
                    unmatched_items=0,
                    ready_items=0,
                )
            )
        if replace_items:
            session.execute(delete(item_table).where(item_table.c.pool_id == TARGET_POOL_ID))
            deleted_tables = delete_target_visit_rows(session, metadata, cases)

        for table_name, rows in rows_by_table.items():
            table = reflect_table(table_name, metadata)
            if table is None:
                continue
            inserted_tables[table_name] = upsert_rows(session, table, rows)

        item_values = []
        for case in cases:
            item = case.source_item
            source_identity = _source_identity(case)
            doc_rows = [
                row
                for rows in rows_by_table.values()
                for row in rows
                if row.get("visit_id") == case.target_visit_id
            ]
            source_tables = sorted(
                {
                    table_name
                    for table_name, rows in rows_by_table.items()
                    if any(row.get("visit_id") == case.target_visit_id for row in rows)
                }
            )
            configured_golden_answers = item.get("synthetic_golden_answers")
            golden_answers = list(configured_golden_answers) if isinstance(configured_golden_answers, list) else [
                {
                    "qc_point_id": rule_id,
                    "expected_status": "pending",
                    "expected_hit": True,
                    "review_status": "pending",
                    "human_reason": "0426 派生合成样本，需人工复核后确认 golden answer。",
                }
                for rule_id in case.selected_rule_ids
            ]
            raw_payload = {
                "source": "manual_problem_sample_pool_0426_derived",
                "source_pool_id": source_pool.get("id"),
                "source_pool_name": source_pool.get("name"),
                "source_item_id": item.get("id"),
                "source_row_no": item.get("row_no"),
                "source_matched_institute_id": item.get("matched_institute_id"),
                "source_matched_patient_id": item.get("matched_patient_id"),
                "source_matched_visit_id": item.get("matched_visit_id"),
                "source_mr_no_hash": _hash_short(source_identity.get("mr_no", "")),
                "source_patient_name_hash": _hash_short(source_identity.get("patient_name", "")),
                "visit_id": case.target_visit_id,
                "patient_id": case.target_patient_id,
                "mr_no": case.target_mr_no,
                "patient_name": case.target_patient_name,
                "department": item.get("department"),
                "selected_rule_ids": case.selected_rule_ids,
                "rule_family": case.family,
                "deid_version": DEID_VERSION,
                "document_count": len(doc_rows),
                "source_tables": source_tables,
                "supplemental_evidence_rows": supplemental_by_visit.get(case.target_visit_id, []),
                "golden_answers": golden_answers,
                "review_status": "pending",
                "manual_issue_text": item.get("manual_issue_text"),
                "source_reason": case.source_reason,
            }
            item_values.append(
                {
                    "id": f"{TARGET_ITEM_PREFIX}-{case.target_index:03d}",
                    "pool_id": TARGET_POOL_ID,
                    "row_no": case.target_index,
                    "department": item.get("department"),
                    "patient_name": case.target_patient_name,
                    "mr_no": case.target_mr_no,
                    "manual_issue_text": _text(item.get("manual_issue_text"), f"{case.family} 0426 脱敏合成样本"),
                    "normalized_issue_text": _normalize_issue_text(item.get("manual_issue_text")),
                    "doctor_name": "陈某医师",
                    "qc_date": now.date(),
                    "qc_user": "system",
                    "coverage_type": "llm_intrinsic",
                    "issue_category": case.family,
                    "expected_scene": "running",
                    "candidate_rule_ids_json": _safe_json_dumps(case.selected_rule_ids),
                    "include_in_batch_1": True,
                    "exclude_reason": "",
                    "matched_institute_id": TARGET_INSTITUTE_ID,
                    "matched_patient_id": case.target_patient_id,
                    "matched_visit_id": case.target_visit_id,
                    "match_status": "matched",
                    "sync_status": "synced",
                    "bundle_status": "pending",
                    "latest_job_id": "",
                    "latest_match_status": "matched",
                    "raw_payload_json": _safe_json_dumps(raw_payload),
                    "created_at": now,
                    "updated_at": now,
                }
            )
        if item_values:
            stmt = pg_insert(item_table).values(item_values)
            update_columns = [key for key in item_values[0] if key != "id"]
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={column: getattr(stmt.excluded, column) for column in update_columns},
            )
            session.execute(stmt)
        CustomQCSamplePoolService()._update_pool_counters(session, TARGET_POOL_ID)
        session.commit()

    service = CustomQCSamplePoolService()
    for case in cases:
        bundle_rows = [
            {
                "institute_id": TARGET_INSTITUTE_ID,
                "patient_id": case.target_patient_id,
                "visit_id": case.target_visit_id,
            }
        ]
        item_id = f"{TARGET_ITEM_PREFIX}-{case.target_index:03d}"
        bundle_status = "pending"
        try:
            refresh_scene_bundles_for_rows(
                scene="running",
                rows=bundle_rows,
                policy_version=BUNDLE_POLICY_VERSION,
            )
            refresh_scene_bundles_for_rows(
                scene="final",
                rows=bundle_rows,
                policy_version=BUNDLE_POLICY_VERSION,
            )
            refresh_domain_bundles_for_rows(
                rows=bundle_rows,
                policy_version=BUNDLE_POLICY_VERSION,
            )
            bundle_status = service._wait_running_bundle_ready(
                institute_id=TARGET_INSTITUTE_ID,
                patient_id=case.target_patient_id,
                visit_id=case.target_visit_id,
                attempts=3,
                sleep_seconds=0.3,
            )
        except Exception as exc:
            bundle_errors[item_id] = _text(str(exc))
        bundle_status_by_item[item_id] = bundle_status

    with Session(engine) as session:
        for item_id, bundle_status in bundle_status_by_item.items():
            session.execute(
                update(item_table)
                .where(item_table.c.id == item_id)
                .values(bundle_status=bundle_status, updated_at=datetime.now())
            )
        service._update_pool_counters(session, TARGET_POOL_ID)
        session.commit()

    return {
        "pool_id": TARGET_POOL_ID,
        "item_count": len(cases),
        "inserted_tables": inserted_tables,
        "deleted_tables": deleted_tables,
        "bundle_status_counts": dict(Counter(bundle_status_by_item.values())),
        "bundle_errors": bundle_errors,
    }


def write_selection_csv(path: Path, cases: Sequence[CandidateCase]) -> None:
    fields = [
        "target_index",
        "target_visit_id",
        "target_mr_no",
        "target_patient_name",
        "rule_family",
        "selected_rule_ids",
        "source_item_id",
        "source_row_no",
        "source_matched_visit_id",
        "department",
        "source_status",
        "source_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for case in cases:
            item = case.source_item
            writer.writerow(
                {
                    "target_index": case.target_index,
                    "target_visit_id": case.target_visit_id,
                    "target_mr_no": case.target_mr_no,
                    "target_patient_name": case.target_patient_name,
                    "rule_family": case.family,
                    "selected_rule_ids": "、".join(case.selected_rule_ids),
                    "source_item_id": item.get("id"),
                    "source_row_no": item.get("row_no"),
                    "source_matched_visit_id": item.get("matched_visit_id"),
                    "department": item.get("department"),
                    "source_status": case.source_status,
                    "source_reason": case.source_reason,
                }
            )


def write_text_lf(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content.replace("\r\n", "\n").replace("\r", "\n"))


def forbidden_token_hits(rows_by_table: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    hits: Counter[str] = Counter()
    for rows in rows_by_table.values():
        for row in rows:
            for value in row.values():
                if not isinstance(value, str):
                    continue
                for token in FORBIDDEN_TOKENS:
                    if token in value:
                        hits[token] += 1
    return dict(hits)


def render_report(
    *,
    source_pool: dict[str, Any],
    cases: Sequence[CandidateCase],
    selection_summary: dict[str, Any],
    clone_audit: dict[str, Any],
    write_summary: dict[str, Any] | None,
    forbidden_hits: dict[str, int],
) -> str:
    selected_counts = Counter(case.family for case in cases)
    lines = [
        "# LX0609 0426 派生合成样本池 v2 构建报告",
        "",
        f"- 目标样本池：`{TARGET_POOL_ID}` / {TARGET_POOL_NAME}",
        f"- 源样本池：`{source_pool.get('id')}` / {source_pool.get('name')}",
        f"- 脱敏版本：`{DEID_VERSION}`",
        f"- 写库状态：{'已写入' if write_summary else 'dry-run 未写库'}",
        "",
        "## 分层抽样",
        "",
        "| 规则族 | 配额 | 已选 |",
        "|---|---:|---:|",
    ]
    for family, quota in FAMILY_QUOTAS.items():
        lines.append(f"| {family} | {quota} | {selected_counts.get(family, 0)} |")
    lines.extend(["", "## 缺口", ""])
    gaps = selection_summary.get("source_gaps") or {}
    if not gaps:
        lines.append("- 无配额缺口。")
    else:
        for family, gap in gaps.items():
            lines.append(f"- {family}: 配额 {gap.get('quota')}，已选 {gap.get('selected')}，缺口 {gap.get('gap')}；{gap.get('reason')}")
    lines.extend(["", "## 脱敏与文书质量", ""])
    lines.append(f"- 禁止词命中：{forbidden_hits or {}}")
    no_long_core_cases = [
        item
        for item in list(clone_audit.get("cases") or [])
        if int(item.get("long_core_document_count") or 0) <= 0
    ]
    lines.append(f"- 无 300 字以上核心文书样本数：{len(no_long_core_cases)}")
    skipped_shell_documents = list(clone_audit.get("skipped_shell_documents") or [])
    supplemental_rows = list(clone_audit.get("supplemental_evidence_rows") or [])
    lines.append(f"- 已过滤空壳核心文书：{len(skipped_shell_documents)}")
    lines.append(f"- 已补全派生证据行：{len(supplemental_rows)}")
    case_audits = list(clone_audit.get("cases") or [])
    first_course_ready = [
        item
        for item in case_audits
        if int(item.get("first_course_record_count") or 0) > 0
    ]
    first_course_lengths = [
        int(item.get("min_first_course_record_length") or 0)
        for item in first_course_ready
        if int(item.get("min_first_course_record_length") or 0) > 0
    ]
    lines.append(
        "- 派生首次病程："
        f"{len(first_course_ready)}/{len(cases)} 份；"
        f"最短 {min(first_course_lengths) if first_course_lengths else 0} 字"
    )
    if skipped_shell_documents:
        lines.extend(["", "### 空壳文书过滤样例", "", "| 新 visit_id | 来源 visit_id | 表 | 标题 | 长度 | 预览 |", "|---|---|---|---|---:|---|"])
        for item in skipped_shell_documents[:12]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _text(item.get("target_visit_id")),
                        _text(item.get("source_visit_id")),
                        _text(item.get("table")),
                        _text(item.get("document_title")).replace("|", "/"),
                        str(item.get("assembled_length") or 0),
                        _text(item.get("preview")).replace("|", "/"),
                    ]
                )
                + " |"
            )
    if supplemental_rows:
        lines.extend(["", "### 派生证据补全", "", "| 新 visit_id | 来源 visit_id | 规则族 | 表 | 原因 |", "|---|---|---|---|---|"])
        for item in supplemental_rows[:30]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _text(item.get("target_visit_id")),
                        _text(item.get("source_visit_id")),
                        _text(item.get("rule_family")),
                        _text(item.get("table")),
                        _text(item.get("reason")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## 写库摘要", ""])
    if write_summary:
        lines.append(f"- 样本项：{write_summary.get('item_count')}")
        deleted_tables = write_summary.get("deleted_tables") or {}
        if deleted_tables:
            lines.append(f"- replace 清理旧目标 visit 行：{sum(int(value or 0) for value in deleted_tables.values())}")
        for table_name, count in sorted((write_summary.get("inserted_tables") or {}).items()):
            lines.append(f"- {table_name}: {count}")
    else:
        lines.append("- dry-run 未写库；确认审计后使用 `--write-db` 写入。")
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 本池是 0426 真实结构脱敏改写的合成/演示样本池。",
            "- golden answer 默认 `pending`，不能声明真实客户样本准确率。",
            "- 不覆盖旧 `luxian-0609-synthetic-v1` fixture。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_validation_summary(path: Path, cases: Sequence[CandidateCase], clone_audit: dict[str, Any]) -> None:
    payload = {
        "pool_id": TARGET_POOL_ID,
        "pool_name": TARGET_POOL_NAME,
        "status": "pending_system_run",
        "message": "样本池构建完成后需通过客户样本验证页面或接口运行 scoped LX0609 验证。",
        "acceptance_rows": [
            {
                "target_visit_id": item.get("target_visit_id"),
                "source_visit_id": item.get("source_visit_id"),
                "rule_family": item.get("family"),
                "selected_rule_ids": item.get("selected_rule_ids"),
                "document_count": item.get("row_count"),
                "min_text_length": item.get("min_text_length"),
                "first_course_record_count": item.get("first_course_record_count"),
                "min_first_course_record_length": item.get("min_first_course_record_length"),
                "qc_status": "pending",
                "evidence_summary": "pending",
            }
            for item in list(clone_audit.get("cases") or [])
        ],
        "selected_rules_by_visit": {
            case.target_visit_id: case.selected_rule_ids
            for case in cases
        },
    }
    write_text_lf(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LX0609 0426-derived synthetic sample pool v2.")
    parser.add_argument("--source-pool", default=SOURCE_POOL_NAME)
    parser.add_argument("--target-size", type=int, default=30)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--write-db", action="store_true", help="Write de-identified rows and sample pool items to local DB.")
    parser.add_argument("--replace-items", action="store_true", help="When writing DB, replace existing target pool items.")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_pool, source_items = load_source_pool_items(args.source_pool)
    cases, selection_summary = build_selection(
        source_pool=source_pool,
        source_items=source_items,
        target_size=args.target_size,
    )
    rows_by_table, clone_audit = build_clone_rows(cases)
    forbidden_hits = forbidden_token_hits(rows_by_table)
    write_summary = None
    if args.write_db:
        write_summary = write_pool_and_items(
            source_pool=source_pool,
            cases=cases,
            rows_by_table=rows_by_table,
            supplemental_rows=clone_audit.get("supplemental_evidence_rows") or [],
            replace_items=bool(args.replace_items),
        )

    write_selection_csv(output_dir / "selection.csv", cases)
    write_text_lf(
        output_dir / "deid-audit.json",
        json.dumps(
            {
                "selection_summary": selection_summary,
                "clone_audit": clone_audit,
                "forbidden_token_hits": forbidden_hits,
                "write_summary": write_summary,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
    )
    write_text_lf(
        output_dir / "pool-import-report.md",
        render_report(
            source_pool=source_pool,
            cases=cases,
            selection_summary=selection_summary,
            clone_audit=clone_audit,
            write_summary=write_summary,
            forbidden_hits=forbidden_hits,
        ),
    )
    write_validation_summary(output_dir / "validation-summary.md", cases, clone_audit)

    print(f"selected={len(cases)}")
    print(f"selected_counts={dict(Counter(case.family for case in cases))}")
    print(f"source_gaps={selection_summary.get('source_gaps') or {}}")
    print(f"forbidden_token_hits={forbidden_hits}")
    print(f"wrote={output_dir}")
    print(f"db_write={'yes' if args.write_db else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
