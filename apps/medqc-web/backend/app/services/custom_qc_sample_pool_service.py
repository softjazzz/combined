from __future__ import annotations

import json
import math
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
import psycopg2
import psycopg2.extras

import sqlalchemy as sa
from sqlalchemy import MetaData, Table, and_, desc, func, or_, select, update
from sqlalchemy.orm import Session

from ..database.connection import DB_SCHEMA_MODE, SessionLocal, engine
from ..database.models.cdm import MedicalRecordFrontpage
from .bundles.assembly import refresh_domain_bundles_for_rows, refresh_scene_bundles_for_rows
from .etl_sync import (
    expand_table_groups,
    fetch_remote_rows_by_visit_keys,
    get_remote_db_url,
    list_sync_tables,
    load_db_config,
    upsert_to_local,
)
from .visit_index_service import ingest_sync_rows


def _now_utc() -> datetime:
    return datetime.utcnow()


def _schema() -> Optional[str]:
    return "qc" if DB_SCHEMA_MODE == "split" else None


def _session() -> Session:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
    return SessionLocal()


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, float) and not math.isfinite(value):
        return default
    text = str(value).strip()
    if text.lower() in {"nan", "<na>"}:
        return default
    return text


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(_sanitize_json_value(value), ensure_ascii=False, default=str, allow_nan=False)


def _safe_json_loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    text = str(value).strip()
    if not text:
        return default
    try:
        return _sanitize_json_value(json.loads(text))
    except Exception:
        return default


def _is_remote_source_unavailable_error(exc: Exception) -> bool:
    message = _safe_text(str(exc)).lower()
    if isinstance(exc, ValueError) and "patient_id/visit_id" in message:
        return True
    pgcode = _safe_text(getattr(exc, "pgcode", ""))
    if pgcode in {"42P01", "42703"}:
        return True
    unavailable_patterns = (
        "undefinedtable",
        "undefinedcolumn",
        "relation does not exist",
        "column does not exist",
        "缺少 patient_id/visit_id",
        "表不存在",
        "字段不存在",
    )
    return any(pattern in message for pattern in unavailable_patterns)


def _sanitize_json_value(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_json_value(item) for item in value]
    return value


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            serial = float(value)
            if serial > 20000:
                excel_epoch = datetime(1899, 12, 30)
                return (excel_epoch + timedelta(days=serial)).date()
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("/", "-").replace(".", "-")
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(normalized).date()
    except Exception:
        return None


def _remote_column_exists(cursor: Any, schema: str, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (schema, table, column),
    )
    return cursor.fetchone() is not None


def _to_iso_date(value: Any) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else ""


def _normalize_issue_text(text: Any) -> str:
    normalized = _safe_text(text)
    normalized = normalized.replace("\u3000", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


_DEFAULT_INTRINSIC_RULE_IDS: List[str] = [
    "SC-008",
    "SC-009",
    "SC-010",
    "SC-011",
    "SC-012",
    "SC-018",
    "SC-019",
    "SC-020",
    "SC-023",
    "SC-024",
    "SC-025",
    "SC-026",
    "SC-027",
    "SC-032",
    "SC-033",
    "SC-036",
    "SC-050",
    "SC-070",
]

_BUNDLE_SOURCE_TABLE_CATEGORY_MAP: Dict[str, List[str]] = {
    "admission_record": ["admission_consistency"],
    "first_course_record": ["first_course_reasoning"],
    "daily_course_record": ["daily_course_analysis"],
    "consultation_record": ["consultation_execution"],
    "senior_course_record": ["senior_round_content"],
    "rescue_record": ["senior_round_content"],
    "diffcase_discussion_record": ["senior_round_content"],
    "death_discussion": ["senior_round_content"],
    "discharge_record": ["discharge_content"],
    "exam_attention_report": ["exam_report_quality"],
    "lab_attention_report": ["exam_report_quality"],
    "exam_master": ["exam_report_quality"],
    "exam_item_report": ["exam_report_quality"],
    "labtest_master": ["exam_report_quality"],
    "labtest_item_report": ["exam_report_quality"],
    "pathology_exam_master": ["exam_report_quality"],
    "pathology_exam_report": ["exam_report_quality"],
    "handoff_record": ["handover_communication"],
    "handover_record": ["handover_communication"],
    "presurg_summary": ["operation_record", "presurg_summary_quality"],
    "presurg_discussion": ["operation_record"],
    "surgery_application": ["operation_record"],
    "surgery_record": ["operation_record"],
    "surgery_safecheck_record": ["operation_record"],
    "surgery_risk_assessment": ["operation_record"],
    "anesthesia_record": ["operation_record"],
    "postsurg_firstcourse_record": ["operation_record", "postsurg_firstcourse_quality"],
    "surgery_inform_consent": ["operation_record", "consent_quality"],
    "docpat_commu_record": ["consent_quality"],
}

_DOCUMENT_SCOPE_LABEL_BY_SOURCE_TABLE: Dict[str, str] = {
    "admission_record": "入院记录",
    "first_course_record": "首次病程",
    "daily_course_record": "日常病程",
    "senior_course_record": "查房讨论",
    "rescue_record": "查房讨论",
    "diffcase_discussion_record": "查房讨论",
    "death_discussion": "查房讨论",
    "consultation_record": "会诊记录",
    "discharge_record": "出院记录",
    "exam_attention_report": "检查检验",
    "lab_attention_report": "检查检验",
    "exam_master": "检查检验",
    "exam_item_report": "检查检验",
    "labtest_master": "检查检验",
    "labtest_item_report": "检查检验",
    "pathology_exam_master": "检查检验",
    "pathology_exam_report": "检查检验",
    "handoff_record": "交接班",
    "handover_record": "交接班",
    "presurg_summary": "手术麻醉",
    "presurg_discussion": "手术麻醉",
    "surgery_application": "手术麻醉",
    "surgery_record": "手术麻醉",
    "surgery_safecheck_record": "手术麻醉",
    "surgery_risk_assessment": "手术麻醉",
    "anesthesia_record": "手术麻醉",
    "postsurg_firstcourse_record": "手术麻醉",
    "surgery_inform_consent": "知情沟通",
    "docpat_commu_record": "知情沟通",
    "inpat_drug_order": "医嘱治疗",
    "inpat_nondrug_order": "医嘱治疗",
    "inpat_prescription": "医嘱治疗",
    "inpat_prescription_item": "医嘱治疗",
}

_DOCUMENT_SCOPE_LABEL_ORDER: List[str] = [
    "入院记录",
    "首次病程",
    "日常病程",
    "查房讨论",
    "会诊记录",
    "手术麻醉",
    "出院记录",
    "检查检验",
    "交接班",
    "知情沟通",
    "医嘱治疗",
]


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _looks_like_consultation_execution_issue(text: str) -> bool:
    if "会诊" not in text:
        return False
    if not _contains_any(
        text,
        (
            "会诊执行记录",
            "执行情况",
            "遵会诊意见",
            "会诊意见未在病程中落实",
            "会诊意见执行记录",
            "未落实会诊意见",
            "会诊后均未",
            "未按会诊意见执行",
            "会诊意见执行",
        ),
    ):
        return False
    return not _contains_any(text, ("无会诊记录", "会诊记录无记录", "无麻醉科会诊记录"))


def _looks_like_handover_communication_issue(text: str) -> bool:
    if not _contains_any(text, ("交接班", "交班记录", "接班记录", "管床医生发生变更")):
        return False
    return _contains_any(
        text,
        (
            "未书写交接班记录",
            "无交接班记录",
            "无交班记录",
            "无接班记录",
            "交接班记录缺项",
            "交接班记录不完整",
            "交接班记录内容不全",
            "交接班记录描述不清",
            "管床医生发生变更未书写交接班记录",
        ),
    )


def _looks_like_consent_quality_issue(text: str) -> bool:
    if not _contains_any(text, ("手术同意书", "知情同意书", "授权委托书", "术中更改术式", "受托人")):
        return False
    return _contains_any(
        text,
        (
            "非授权受托人",
            "非法定代理人",
            "非本人",
            "无患者签名",
            "无医师签名",
            "签字人员",
            "缺项",
            "描述不清",
            "术中更改术式",
            "改变手术方式",
            "扩大手术范围",
            "授权委托",
            "监护人",
        ),
    )


def _looks_like_consultation_record_quality_issue(text: str) -> bool:
    if "会诊" not in text:
        return False
    if _looks_like_consultation_execution_issue(text):
        return False
    return _contains_any(
        text,
        (
            "会诊记录",
            "综合会诊结果",
            "建设性诊疗意见",
            "复制其他科室会诊意见",
            "复制粘贴",
            "照抄",
            "结论不足",
            "建议不足",
            "内容空洞",
        ),
    )


def _looks_like_senior_round_content_issue(text: str) -> bool:
    if not _contains_any(
        text,
        ("查房", "上级医师", "主治医师", "副主任医师", "主任医师", "三级医师查房", "三级查房"),
    ):
        return False
    if _contains_any(
        text,
        (
            "48小时",
            "72小时",
            "未及时",
            "无上级医生查房记录",
            "无上级医师查房记录",
            "无主治医师查房记录",
            "无副主任医师查房记录",
            "未查见副主任医师查房记录",
        ),
    ):
        return False
    return _contains_any(
        text,
        (
            "内容空洞",
            "无内容",
            "内容却是",
            "涉嫌伪造病历",
            "病情分析较为简单",
            "无病情分析",
            "无诊疗意见",
            "身份异常",
            "本人查房",
            "执行不到位",
            "落实不到位",
            "相关处理",
        ),
    )


def _looks_like_unreasonable_copy_content_issue(text: str) -> bool:
    if "会诊" in text and not _contains_any(text, ("查房", "病程", "病例特点", "拟诊讨论", "入院记录", "现病史")):
        return False
    if not _contains_any(
        text,
        (
            "复制粘贴",
            "完全相同",
            "雷同",
            "照抄",
            "相似度100%",
            "病历复制",
            "重复病例特点",
            "同科同种疾病",
        ),
    ):
        return False
    return _contains_any(
        text,
        (
            "查房",
            "病程",
            "病例特点",
            "拟诊讨论",
            "入院记录",
            "现病史",
            "同科同种疾病",
            "病历",
        ),
    )


def _looks_like_critical_value_management_issue(text: str) -> bool:
    if "危急值" not in text:
        return False
    return _contains_any(
        text,
        (
            "报告时间",
            "处置时间",
            "处理记录",
            "处理不充分",
            "未描述",
            "未记录",
            "补钾",
            "具体处理",
            "具体补钾",
        ),
    )


def _looks_like_progress_order_consistency_issue(text: str) -> bool:
    if not _contains_any(text, ("医嘱", "病程记录", "术前小结", "术前讨论", "手术医嘱")):
        return False
    return _contains_any(
        text,
        (
            "不一致",
            "早于",
            "先于",
            "之前",
            "已经下达",
            "相反",
            "矛盾",
        ),
    )


def _looks_like_operation_record_quality_issue(text: str) -> bool:
    if not _contains_any(
        text,
        (
            "手术记录",
            "主刀医生签名",
            "签名异常",
            "手术结束时间",
            "记录错误",
            "描述不清",
            "手术名称",
        ),
    ):
        return False
    if _looks_like_progress_order_consistency_issue(text) and "手术记录" not in text:
        return False
    return True


def _looks_like_first_course_timeliness_issue(text: str) -> bool:
    if not _contains_any(text, ("首次病程", "首程", "8小时", "24小时")):
        return False
    if _contains_any(
        text,
        (
            "鉴别诊断",
            "诊断依据",
            "诊疗计划",
            "病例特点",
            "拟诊讨论",
            "术后首次病程",
            "术后病程记录",
        ),
    ):
        return False
    return _contains_any(
        text,
        (
            "8小时内未完成",
            "24小时内未完成",
            "未完成首次病程记录",
            "首次病程未及时",
            "首程未及时",
            "无首次病程记录",
            "首次病程缺失",
        ),
    )


def _looks_like_course_gap_timeliness_issue(text: str) -> bool:
    if "病程" not in text:
        return False
    return _contains_any(
        text,
        (
            "无病程记录",
            "后无病程",
            "三天未完成一次病程",
            "三天无病程",
            "病程记录未及时",
            "书写不及时",
            "每日未完成病程",
            "长时间无病程",
        ),
    )


def _looks_like_first_round_timeliness_issue(text: str) -> bool:
    if not _contains_any(text, ("查房", "主治医师", "副主任医师", "主任医师", "高级职称医师", "上级医师")):
        return False
    return _contains_any(
        text,
        (
            "48小时内，无主治医师查房记录",
            "48小时无主治医师查房记录",
            "入院48小时内",
            "72小时以内未查见副主任医师查房记录",
            "72小时无高级职称医师查房记录",
            "72小时无副主任医师查房记录",
            "72小时无上级医师查房记录",
            "首次查房",
        ),
    )


def _looks_like_consultation_timeliness_issue(text: str) -> bool:
    if "会诊" not in text:
        return False
    if _looks_like_consultation_execution_issue(text):
        return False
    return _contains_any(
        text,
        (
            "会诊记录未及时",
            "会诊记录超时",
            "会诊记录时效",
            "会诊申请时间",
            "会诊接收时间",
            "早于呼吸科会诊接收时间",
            "会诊记录时间节点",
        ),
    )


def _looks_like_operation_record_timeliness_issue(text: str) -> bool:
    if "手术记录" not in text:
        return False
    return _contains_any(
        text,
        (
            "24小时内完成手术记录",
            "未在24小时内完成手术记录",
            "术后24小时内完成",
            "手术记录时效",
            "手术记录未及时",
        ),
    )


def _looks_like_operation_preop_mdt_issue(text: str) -> bool:
    if not _contains_any(text, ("MDT", "多学科讨论", "多学科会诊")):
        return False
    return _contains_any(text, ("四级手术", "四级肿瘤手术", "术前讨论"))


def _looks_like_operation_preop_conclusion_issue(text: str) -> bool:
    if "术前讨论" not in text:
        return False
    return _contains_any(
        text,
        (
            "结论未记入病历",
            "结果未记入病历",
            "术前讨论记录未明确",
            "讨论内容未书写明确",
            "缺少参与人员发言",
            "未明确手术时间",
            "未明确手术医生",
            "新建后未书写",
        ),
    )


def _looks_like_presurg_summary_quality_issue(text: str) -> bool:
    if "术前小结" not in text:
        return False
    return _contains_any(
        text,
        (
            "未按要求书写",
            "手术要点",
            "归纳把握不准确",
            "记录不全",
            "内容不全",
            "缺项",
            "未书写",
        ),
    )


def _looks_like_postsurg_firstcourse_quality_issue(text: str) -> bool:
    if not _contains_any(text, ("术后首次病程", "术后病程记录")):
        return False
    return _contains_any(
        text,
        (
            "手术时间",
            "实际手术时间",
            "术后处理措施",
            "术后注意事项",
            "告知手术情况",
            "书写不规范",
            "缺少",
            "漏项",
            "不一致",
        ),
    )


def _looks_like_invasive_operation_record_issue(text: str) -> bool:
    return _contains_any(text, ("有创操作", "有创诊疗", "骨髓穿刺", "胸腔闭式引流", "清创记录", "穿刺记录"))


def _looks_like_transfer_record_quality_issue(text: str) -> bool:
    return _contains_any(text, ("转科记录", "转出记录", "转入记录", "转科目的", "拟转入科室", "转入时间"))


def _looks_like_difficult_case_discussion_issue(text: str) -> bool:
    return _contains_any(text, ("疑难病历讨论", "疑难病例讨论", "超过3天未明确诊断", "确诊困难", "疗效不佳"))


def _looks_like_transfusion_record_quality_issue(text: str) -> bool:
    return _contains_any(text, ("输血后评价", "输血记录", "输血反应", "输血前评估"))


def _looks_like_diagnosis_or_treatment_followup_issue(text: str) -> bool:
    return _contains_any(
        text,
        (
            "无后续血压监测",
            "无相关处理",
            "无处理",
            "无诊断",
            "未对诊断进行修正",
            "未录入主诊断",
            "检查结果",
            "辅助检查不全面",
            "病历书写不完整",
            "用药情况记录不规范",
            "用药记录不规范",
            "药物剂量",
        ),
    )


def _looks_like_preop_risk_assessment_issue(text: str) -> bool:
    return _contains_any(
        text,
        (
            "术前准备不充分",
            "预案不清晰",
            "术前评估不充分",
            "围手术期管理不到位",
            "术前缺上级医师意见",
            "术前会诊科室讨论意见",
        ),
    )


ADMISSION_ISSUE_FAMILY_RULE_IDS: tuple[str, ...] = (
    "SC-008",
    "SC-009",
    "SC-010",
    "SC-011",
    "SC-012",
    "SC-018",
    "SC-019",
    "SC-020",
)

ADMISSION_ISSUE_FAMILY_RULE_DEFINITIONS: Dict[str, str] = {
    "SC-008": "主诉书写不规范或不能导出第一诊断",
    "SC-009": "现病史记录不全或描述不清",
    "SC-010": "既往史/个人史/婚育史/月经史/家族史缺项或不规范",
    "SC-011": "现病史阳性/阴性症状采集不全或缺乏诊断支撑",
    "SC-012": "诊治经过、院外/门诊治疗经过、用药经过记录不全",
    "SC-018": "体格检查/专科检查缺项、不完整或前后矛盾",
    "SC-019": "辅助检查记录缺失、不完整、院内/院外属性错误",
    "SC-020": "初步诊断/入院诊断不完整、不准确、与病史查体检查不一致",
}

ADMISSION_ISSUE_FAMILY_ALLOWED_RESULTS = {"hit", "partial_hit", "no_hit", "uncertain"}
ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES = {"compliant", "non_compliant", "uncertain"}
ADMISSION_DIAGNOSIS_COVERAGE_STATUSES = {"covered", "partially_covered", "not_covered", "uncertain"}

CONSULTATION_FAMILY_RULE_IDS: tuple[str, ...] = (
    "SC-069",
    "SC-070",
    "LX-016",
    "SC-146",
    "SC-036",
    "SC-046",
)

CONSULTATION_FAMILY_RULE_DEFINITIONS: Dict[str, str] = {
    "SC-069": "会诊记录内容质量、复制粘贴、结论或建议不充分",
    "SC-070": "会诊执行记录缺失或仅笼统写遵会诊意见",
    "LX-016": "会诊意见已写遵执但实际未落实或执行闭环不足",
    "SC-146": "会诊意见、医嘱与病程记录不一致",
    "SC-036": "病程记录对异常结果、会诊意见或处理方案缺分析/缺处理意见",
    "SC-046": "有创诊疗操作记录缺失或书写不规范",
}
CONSULTATION_FAMILY_ALLOWED_RESULTS = {"exact_hit", "hit", "partial_hit", "no_hit", "uncertain"}


def _unique_rule_ids(rule_ids: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for item in rule_ids:
        rule_id = _safe_text(item).upper()
        if rule_id and rule_id not in result:
            result.append(rule_id)
    return result


def _extract_json_object_from_text(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    text = _safe_text(value)
    if not text:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    parsed = _safe_json_loads(text, {})
    return dict(parsed) if isinstance(parsed, dict) else {}


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, confidence))


def normalize_admission_consistency_llm_output(
    llm_output: Any,
    *,
    fallback_primary_rule_id: str = "SC-008",
) -> Dict[str, Any]:
    payload = _extract_json_object_from_text(llm_output)
    allowed = set(ADMISSION_ISSUE_FAMILY_RULE_IDS)
    fallback_primary = _safe_text(fallback_primary_rule_id).upper()
    if fallback_primary not in allowed:
        fallback_primary = "SC-008"

    invalid_rule_ids: List[str] = []
    raw_primary = _safe_text(payload.get("primary_rule_id")).upper()
    primary_rule_id = raw_primary if raw_primary in allowed else fallback_primary
    if raw_primary and raw_primary not in allowed:
        invalid_rule_ids.append(raw_primary)

    raw_recommended = _unique_rule_ids(payload.get("recommended_rule_ids") or payload.get("matched_rule_ids") or [])
    if raw_primary and raw_primary not in raw_recommended:
        raw_recommended.insert(0, raw_primary)
    recommended_rule_ids: List[str] = []
    for rule_id in raw_recommended:
        if rule_id in allowed:
            recommended_rule_ids.append(rule_id)
        elif rule_id:
            invalid_rule_ids.append(rule_id)
    if primary_rule_id not in recommended_rule_ids:
        recommended_rule_ids.insert(0, primary_rule_id)
    recommended_rule_ids = _unique_rule_ids(recommended_rule_ids)

    sub_items: List[Dict[str, Any]] = []
    for raw_item in list(payload.get("sub_items") or []):
        if not isinstance(raw_item, dict):
            continue
        rule_id = _safe_text(raw_item.get("rule_id")).upper()
        if rule_id not in allowed:
            if rule_id:
                invalid_rule_ids.append(rule_id)
            continue
        status = _safe_text(raw_item.get("status"), "uncertain").lower()
        if status not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
            status = "uncertain"
        sub_items.append(
            {
                "rule_id": rule_id,
                "item": _safe_text(raw_item.get("item")),
                "status": status,
                "matched_manual_issue_part": _safe_text(raw_item.get("matched_manual_issue_part")),
                "evidence": _safe_text(raw_item.get("evidence")),
                "reason": _safe_text(raw_item.get("reason")),
            }
        )

    overall_result = _safe_text(payload.get("overall_result"), "uncertain").lower()
    if overall_result not in ADMISSION_ISSUE_FAMILY_ALLOWED_RESULTS:
        overall_result = "uncertain"

    if overall_result == "no_hit":
        for item in sub_items:
            if item.get("status") == "non_compliant":
                item["status"] = "compliant"

    diagnosis_coverage = _safe_text(payload.get("diagnosis_coverage"), "uncertain").lower()
    if diagnosis_coverage not in ADMISSION_DIAGNOSIS_COVERAGE_STATUSES:
        diagnosis_coverage = "uncertain"
    qc_result = _safe_text(payload.get("qc_result"), "uncertain").lower()
    if qc_result not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
        qc_result = "uncertain"
    overall_status = _safe_text(payload.get("overall_status") or qc_result, "uncertain").lower()
    if overall_status not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
        overall_status = "uncertain"

    review_required = False
    if invalid_rule_ids or not payload:
        overall_result = "uncertain"
        overall_status = "uncertain"
        review_required = True

    secondary_rule_ids = [rule_id for rule_id in recommended_rule_ids if rule_id != primary_rule_id]
    return {
        "primary_rule_id": primary_rule_id,
        "secondary_rule_ids": secondary_rule_ids,
        "recommended_rule_ids": recommended_rule_ids,
        "matched_rule_ids": recommended_rule_ids,
        "sub_items": sub_items,
        "overall_status": overall_status,
        "matched_manual_issue_parts": [
            _safe_text(item) for item in list(payload.get("matched_manual_issue_parts") or []) if _safe_text(item)
        ],
        "unmatched_manual_issue_parts": [
            _safe_text(item) for item in list(payload.get("unmatched_manual_issue_parts") or []) if _safe_text(item)
        ],
        "overall_result": overall_result,
        "admission_diagnoses": [
            _safe_text(item) for item in list(payload.get("admission_diagnoses") or []) if _safe_text(item)
        ],
        "symptom_or_sign_only_diagnoses": [
            _safe_text(item)
            for item in list(payload.get("symptom_or_sign_only_diagnoses") or [])
            if _safe_text(item)
        ],
        "core_abnormal_evidence": [
            _safe_text(item) for item in list(payload.get("core_abnormal_evidence") or []) if _safe_text(item)
        ],
        "conflicts": [
            _safe_text(item) for item in list(payload.get("conflicts") or []) if _safe_text(item)
        ],
        "missing_evidence": [
            _safe_text(item) for item in list(payload.get("missing_evidence") or []) if _safe_text(item)
        ],
        "diagnosis_coverage": diagnosis_coverage,
        "qc_result": qc_result,
        "qc_conclusion": _safe_text(payload.get("qc_conclusion")),
        "confidence": _coerce_confidence(payload.get("confidence")),
        "evidence_summary": _safe_text(payload.get("evidence_summary") or payload.get("qc_conclusion")),
        "invalid_rule_ids": _unique_rule_ids(invalid_rule_ids),
        "review_required": review_required,
        "raw_output": payload,
    }


def build_admission_issue_family_prompt(
    *,
    manual_issue_text: Any,
    admission_bundle: Dict[str, Any],
) -> str:
    rule_lines = "\n".join(
        f"- {rule_id}: {title}"
        for rule_id, title in ADMISSION_ISSUE_FAMILY_RULE_DEFINITIONS.items()
    )
    bundle_json = _safe_json_dumps(admission_bundle)
    return f"""你是一名病历质控专家。请对 Sheet2 中“入院记录内容不完整/前后矛盾”人工问题做一次语义分流和证据核验。

【可选子规则白名单】
{rule_lines}

【判定要求】
1. 一条人工问题只执行一次语义分流，不要按子项重复调用。
2. 只允许输出白名单中的 rule_id；无法判断时保留最接近的主规则并标记 uncertain。
3. primary_rule_id 选择人工问题最核心或最先需要整改的锚点；其他锚点放入 recommended_rule_ids 和 sub_items。
4. 不要把病案首页诊断或出院诊断作为主证据；它们只能作为参考。入院记录诊断、首次病程病例特点/诊断依据/初步诊断/诊疗计划优先。
5. 如果人工问题和病历原文冲突，应输出 no_hit 或 uncertain，并在 reason 中说明冲突，不要强行 exact。
6. 如果 overall_result 是 no_hit，sub_items 中不得出现 non_compliant；冲突项应标记 compliant，证据不足项才标记 uncertain。
7. 如果人工问题包含多个锚点，且至少一个锚点能被原文明确证实为缺陷，应输出 partial_hit，不要输出 uncertain；仅把未核实或冲突的锚点标记 uncertain/compliant。
8. 当问题涉及 SC-020 入院诊断时，必须按通用诊断准确性口径判断：入院诊断是否覆盖现病史、专科查体、辅助检查、既往检查中的核心异常证据；若诊断只是症状/体征/笼统描述，而病历已有较明确病因、损伤部位、器官疾病、并发症或疾病性质，应判为诊断不准确或不完整。
9. 如证据不足以形成明确疾病诊断，且诊断中有“待查/原因待查/待排/？”等不确定表达，可判 compliant 或 uncertain，不要强打 non_compliant。
10. SC-020 不得依赖患者姓名、特定样本编号或单个疾病词；必须基于诊断文本与核心阳性证据的覆盖关系。

【人工问题】
{_safe_text(manual_issue_text)}

【证据 bundle】
{bundle_json}

请严格输出 JSON 对象，不要输出额外解释：
{{
  "primary_rule_id": "SC-008|SC-009|SC-010|SC-011|SC-012|SC-018|SC-019|SC-020",
  "recommended_rule_ids": ["..."],
  "matched_rule_ids": ["同 recommended_rule_ids，用于客户验收页按家族展示"],
  "sub_items": [
    {{
      "rule_id": "...",
      "item": "主诉规范性/现病史完整性/既往史完整性/诊治经过/查体专科/辅助检查/初步诊断/前后矛盾",
      "status": "compliant|non_compliant|uncertain",
      "matched_manual_issue_part": "...",
      "evidence": "...",
      "reason": "..."
    }}
  ],
  "matched_manual_issue_parts": [],
  "unmatched_manual_issue_parts": [],
  "overall_result": "hit|partial_hit|no_hit|uncertain",
  "overall_status": "non_compliant|compliant|uncertain",
  "admission_diagnoses": ["入院/初步诊断原文条目"],
  "symptom_or_sign_only_diagnoses": ["仅为症状、体征或笼统描述的诊断条目"],
  "core_abnormal_evidence": ["现病史/专科查体/辅助检查/既往检查中的核心异常证据"],
  "diagnosis_coverage": "covered|partially_covered|not_covered|uncertain",
  "qc_result": "non_compliant|compliant|uncertain",
  "conflicts": ["人工问题与原文冲突的子项"],
  "missing_evidence": ["缺原句、缺源表或缺关键正文的子项"],
  "qc_conclusion": "...",
  "confidence": 0.0
}}"""


def resolve_admission_consistency_rule_recommendations(
    text: Any,
    *,
    llm_output: Any = None,
    fallback_primary_rule_id: str = "SC-008",
) -> Dict[str, Any]:
    if llm_output is None:
        fallback_primary = _safe_text(fallback_primary_rule_id).upper()
        if fallback_primary not in ADMISSION_ISSUE_FAMILY_RULE_IDS:
            fallback_primary = "SC-008"
        return {
            "primary_rule_id": fallback_primary,
            "secondary_rule_ids": [],
            "recommended_rule_ids": [fallback_primary],
            "matched_rule_ids": [fallback_primary],
            "sub_items": [],
            "overall_status": "uncertain",
            "matched_manual_issue_parts": [],
            "unmatched_manual_issue_parts": [_normalize_issue_text(text)] if _normalize_issue_text(text) else [],
            "overall_result": "uncertain",
            "admission_diagnoses": [],
            "symptom_or_sign_only_diagnoses": [],
            "core_abnormal_evidence": [],
            "conflicts": [],
            "missing_evidence": [],
            "diagnosis_coverage": "uncertain",
            "qc_result": "uncertain",
            "qc_conclusion": "未提供 LLM 语义分流结果，需进入 reclassification dry-run。",
            "confidence": 0.0,
            "evidence_summary": "",
            "invalid_rule_ids": [],
            "review_required": True,
            "raw_output": {},
        }
    return normalize_admission_consistency_llm_output(
        llm_output,
        fallback_primary_rule_id=fallback_primary_rule_id,
    )


def normalize_consultation_family_llm_output(
    llm_output: Any,
    *,
    fallback_primary_rule_id: str = "SC-069",
) -> Dict[str, Any]:
    payload = _extract_json_object_from_text(llm_output)
    allowed = set(CONSULTATION_FAMILY_RULE_IDS)
    fallback_primary = _safe_text(fallback_primary_rule_id).upper()
    if fallback_primary not in allowed:
        fallback_primary = "SC-069"

    invalid_rule_ids: List[str] = []
    raw_primary = _safe_text(payload.get("primary_rule_id")).upper()
    primary_rule_id = raw_primary if raw_primary in allowed else fallback_primary
    if raw_primary and raw_primary not in allowed:
        invalid_rule_ids.append(raw_primary)

    raw_recommended = _unique_rule_ids(payload.get("recommended_rule_ids") or payload.get("matched_rule_ids") or [])
    if raw_primary and raw_primary not in raw_recommended:
        raw_recommended.insert(0, raw_primary)
    recommended_rule_ids: List[str] = []
    for rule_id in raw_recommended:
        if rule_id in allowed:
            recommended_rule_ids.append(rule_id)
        elif rule_id:
            invalid_rule_ids.append(rule_id)
    if primary_rule_id not in recommended_rule_ids:
        recommended_rule_ids.insert(0, primary_rule_id)
    recommended_rule_ids = _unique_rule_ids(recommended_rule_ids)

    sub_items: List[Dict[str, Any]] = []
    for raw_item in list(payload.get("sub_items") or []):
        if not isinstance(raw_item, dict):
            continue
        rule_id = _safe_text(raw_item.get("rule_id")).upper()
        if rule_id not in allowed:
            if rule_id:
                invalid_rule_ids.append(rule_id)
            continue
        status = _safe_text(raw_item.get("status"), "uncertain").lower()
        if status not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
            status = "uncertain"
        sub_items.append(
            {
                "rule_id": rule_id,
                "status": status,
                "item": _safe_text(raw_item.get("item") or raw_item.get("sub_item")),
                "evidence": _safe_text(raw_item.get("evidence")),
                "reason": _safe_text(raw_item.get("reason")),
            }
        )

    overall_result = _safe_text(payload.get("overall_result"), "uncertain").lower()
    if overall_result not in CONSULTATION_FAMILY_ALLOWED_RESULTS:
        overall_result = "uncertain"
    if overall_result == "hit":
        overall_result = "exact_hit"
    if overall_result == "no_hit":
        for item in sub_items:
            if item.get("status") == "non_compliant":
                item["status"] = "compliant"

    qc_result = _safe_text(payload.get("qc_result"), "uncertain").lower()
    if qc_result not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
        qc_result = "uncertain"
    overall_status = _safe_text(payload.get("overall_status") or qc_result, "uncertain").lower()
    if overall_status not in ADMISSION_ISSUE_FAMILY_ALLOWED_STATUSES:
        overall_status = "uncertain"

    review_required = False
    if invalid_rule_ids or not payload:
        overall_result = "uncertain"
        overall_status = "uncertain"
        review_required = True

    secondary_rule_ids = [rule_id for rule_id in recommended_rule_ids if rule_id != primary_rule_id]
    return {
        "primary_rule_id": primary_rule_id,
        "secondary_rule_ids": secondary_rule_ids,
        "recommended_rule_ids": recommended_rule_ids,
        "matched_rule_ids": recommended_rule_ids,
        "sub_items": sub_items,
        "overall_result": overall_result,
        "overall_status": overall_status,
        "qc_result": qc_result,
        "conflicts": [
            _safe_text(item) for item in list(payload.get("conflicts") or []) if _safe_text(item)
        ],
        "missing_evidence": [
            _safe_text(item) for item in list(payload.get("missing_evidence") or []) if _safe_text(item)
        ],
        "qc_conclusion": _safe_text(payload.get("qc_conclusion")),
        "confidence": _coerce_confidence(payload.get("confidence")),
        "evidence_summary": _safe_text(payload.get("evidence_summary") or payload.get("qc_conclusion")),
        "invalid_rule_ids": _unique_rule_ids(invalid_rule_ids),
        "review_required": review_required,
        "raw_output": payload,
    }


def build_consultation_family_prompt(
    *,
    manual_issue_text: Any,
    consultation_bundle: Dict[str, Any],
) -> str:
    rule_lines = "\n".join(
        f"- {rule_id}: {title}" for rule_id, title in CONSULTATION_FAMILY_RULE_DEFINITIONS.items()
    )
    bundle_json = _safe_json_dumps(consultation_bundle)
    return f"""你是一名病历质控专家。请对 Sheet2 中“会诊记录质量/会诊执行/会诊意见一致性”相关人工问题做一次 family-level 语义拆解和证据核验。

【可选规则白名单】
{rule_lines}

【判定要求】
1. 一条人工问题只执行一次 LLM 调用；如果包含多个锚点，必须在 sub_items 中拆开，不要按子项重复调用。
2. 只允许输出白名单中的 rule_id；无法判断时选择最接近主规则并将相关 sub_item 标记 uncertain。
3. primary_rule_id 选择人工问题中最核心或最先需要整改的会诊相关锚点；其他锚点放入 recommended_rule_ids 和 sub_items。
4. 不要把人工问题文本当作事实。只能依据 bundle 中的原始会诊记录、病程记录、查房记录、医嘱摘要、非药物/康复治疗医嘱、执行清单、有创/手术记录摘要作证据。
5. 不能因为人工问题里出现“复制粘贴严重、无建设性意见、未落实、无操作记录”等评价性表述就直接判 non_compliant；必须引用原文证据或说明缺证据。
6. 如果人工问题跨多个质控点，例如会诊执行 + 医嘱一致性 + 有创操作记录，overall_result 只能是 partial_hit 或 uncertain，不得把整条人工问题判为 exact_hit。
7. 如果某个子项与原文冲突，应将该 sub_item 标记 compliant，并在 conflicts 中说明。
8. 如果缺医嘱明细、执行清单、会诊原文或操作记录正文，应将该 sub_item 标记 uncertain，并在 missing_evidence 中说明。
9. 有创/操作记录证据可能来自手术记录表，也可能来自病程中的原始操作经过；如果 bundle 的 procedure_anchor_snippets 已给出操作时间、名称和经过，不能简单按“缺手术记录表”判无操作记录。
10. 只有人工问题所有关键锚点均由证据支持，且无 conflicts、无关键 missing_evidence 时，才允许 overall_result=exact_hit；部分成立或部分冲突必须输出 partial_hit。

【人工问题】
{_safe_text(manual_issue_text)}

【证据 bundle】
{bundle_json}

请严格输出 JSON 对象，不要输出额外解释：
{{
  "primary_rule_id": "SC-069|SC-070|LX-016|SC-146|SC-036|SC-046",
  "recommended_rule_ids": ["..."],
  "matched_rule_ids": ["同 recommended_rule_ids"],
  "overall_result": "exact_hit|partial_hit|no_hit|uncertain",
  "overall_status": "non_compliant|compliant|uncertain",
  "qc_result": "non_compliant|compliant|uncertain",
  "sub_items": [
    {{
      "rule_id": "...",
      "status": "non_compliant|compliant|uncertain",
      "item": "会诊记录内容质量/会诊意见落实/医嘱一致性/病程分析/有创操作记录",
      "evidence": "只引用 bundle 中存在的原文或结构化证据",
      "reason": "说明为什么成立、冲突或证据不足"
    }}
  ],
  "conflicts": ["与原文冲突的子项"],
  "missing_evidence": ["缺会诊原文/缺医嘱明细/缺执行清单/缺操作记录正文"],
  "qc_conclusion": "...",
  "confidence": 0.0
}}"""


def resolve_consultation_family_rule_recommendations(
    text: Any,
    *,
    llm_output: Any = None,
    fallback_primary_rule_id: str = "SC-069",
) -> Dict[str, Any]:
    if llm_output is None:
        fallback_primary = _safe_text(fallback_primary_rule_id).upper()
        if fallback_primary not in CONSULTATION_FAMILY_RULE_IDS:
            fallback_primary = "SC-069"
        return {
            "primary_rule_id": fallback_primary,
            "secondary_rule_ids": [],
            "recommended_rule_ids": [fallback_primary],
            "matched_rule_ids": [fallback_primary],
            "sub_items": [],
            "overall_result": "uncertain",
            "overall_status": "uncertain",
            "qc_result": "uncertain",
            "conflicts": [],
            "missing_evidence": [],
            "qc_conclusion": "未提供 LLM 会诊 family-level 语义拆解结果，需进入定向 dry-run。",
            "confidence": 0.0,
            "evidence_summary": "",
            "invalid_rule_ids": [],
            "review_required": True,
            "raw_output": {},
        }
    return normalize_consultation_family_llm_output(
        llm_output,
        fallback_primary_rule_id=fallback_primary_rule_id,
    )


@lru_cache(maxsize=1)
def _load_issue_category_rule_map() -> Dict[str, List[str]]:
    mapping_path = Path(__file__).resolve().parents[2] / "data" / "synthetic_qc" / "sheet2_intrinsic_issue_mapping.json"
    if not mapping_path.exists():
        return {}
    try:
        data = json.loads(mapping_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    category_map: Dict[str, List[str]] = {}
    for issue_type in data.get("issue_types") or []:
        category = _safe_text(issue_type.get("source_category"))
        if not category:
            continue
        current = category_map.setdefault(category, [])
        for rule_id in _normalize_candidate_rule_ids(issue_type.get("expected_rule_ids")):
            if rule_id not in current:
                current.append(rule_id)
    return category_map


def _derive_dynamic_candidate_rule_ids_from_source_tables(source_tables: Sequence[str]) -> List[str]:
    normalized_tables = {_safe_text(item).lower() for item in source_tables if _safe_text(item)}
    if not normalized_tables:
        return []
    category_rule_map = _load_issue_category_rule_map()
    dynamic_rule_ids: List[str] = []
    for source_table in normalized_tables:
        for category in _BUNDLE_SOURCE_TABLE_CATEGORY_MAP.get(source_table, []):
            for rule_id in category_rule_map.get(category, []):
                if rule_id not in dynamic_rule_ids:
                    dynamic_rule_ids.append(rule_id)
    return dynamic_rule_ids


def _derive_document_scope_labels_from_source_tables(source_tables: Sequence[str]) -> List[str]:
    normalized_tables = {_safe_text(item).lower() for item in source_tables if _safe_text(item)}
    if not normalized_tables:
        return []
    labels: List[str] = []
    for label in _DOCUMENT_SCOPE_LABEL_ORDER:
        for source_table in normalized_tables:
            if _DOCUMENT_SCOPE_LABEL_BY_SOURCE_TABLE.get(source_table) == label and label not in labels:
                labels.append(label)
                break
    return labels


def _merge_candidate_rule_ids(
    *,
    base_rule_ids: Sequence[str],
    dynamic_rule_ids: Sequence[str],
    coverage_type: str,
    manual_issue_text: str,
) -> List[str]:
    base = _normalize_candidate_rule_ids(base_rule_ids)
    dynamic = _normalize_candidate_rule_ids(dynamic_rule_ids)
    if not dynamic:
        return base
    if coverage_type == "llm_intrinsic" and not _safe_text(manual_issue_text):
        return dynamic
    merged = list(base)
    for rule_id in dynamic:
        if rule_id not in merged:
            merged.append(rule_id)
    return merged


def classify_manual_issue_text(text: Any) -> Dict[str, Any]:
    normalized = _normalize_issue_text(text)
    lowered = normalized.lower()

    if not normalized:
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "record_list_intrinsic",
            "expected_scene": "running",
            "candidate_rule_ids": list(_DEFAULT_INTRINSIC_RULE_IDS),
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_consent_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "consent_quality",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-128", "SC-087", "SC-089", "LX-021"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_first_course_timeliness_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "first_course_timeliness",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-021", "SC-022"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_first_round_timeliness_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "first_round_timeliness",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-048", "SC-049"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_consultation_timeliness_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "consultation_timeliness",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-071", "SC-072"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_operation_record_timeliness_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "operation_record_timeliness",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-096"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_course_gap_timeliness_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "course_gap_timeliness",
            "expected_scene": "running",
            "candidate_rule_ids": ["LXE-18"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_invasive_operation_record_issue(normalized):
        if _contains_any(normalized, ("无有创操作记录", "无有创诊疗", "无有创", "无记录")):
            rule_ids = ["SC-045", "SC-046"]
        else:
            rule_ids = ["SC-046", "SC-045"]
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "invasive_operation_record_quality",
            "expected_scene": "final",
            "candidate_rule_ids": rule_ids,
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_transfer_record_quality_issue(normalized):
        return {
            "coverage_type": "programmatic",
            "issue_category": "transfer_record_quality",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-064"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_difficult_case_discussion_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "difficult_case_discussion",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-056", "SC-057", "SC-058"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_transfusion_record_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "transfusion_record_quality",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-074", "LX-018", "SC-073"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_preop_risk_assessment_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "operation_preop_risk_assessment",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-081", "SC-082", "SC-097"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_diagnosis_or_treatment_followup_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "daily_course_analysis",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-036", "SC-032", "SC-033"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    # 纯程序/时效问题兜底，仍保留为非首批直连类别。
    if _contains_any(
        normalized,
        (
            "未及时",
            "超时",
            "24小时",
            "48小时",
            "72小时",
            "三天未",
            "两天未",
            "每日未",
            "签名",
            "签字",
            "无术前小结",
            "无术前讨论",
            "无手术记录",
            "无会诊记录",
            "无主刀医生",
            "未进行术前讨论",
        ),
    ):
        return {
            "coverage_type": "programmatic",
            "issue_category": "timeliness_or_presence",
            "expected_scene": "running",
            "candidate_rule_ids": [],
            "include_in_batch_1": False,
            "exclude_reason": "纯时效/缺文书/签名类问题，首批不纳入 LLM 内涵验证",
        }

    if _looks_like_handover_communication_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "handover_communication",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-062", "SC-063"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_postsurg_firstcourse_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "postsurg_firstcourse_quality",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-105"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_unreasonable_copy_content_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "unreasonable_copy_content",
            "expected_scene": "running",
            "candidate_rule_ids": ["CL-273", "CL-274", "CL-275", "CL-276"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _contains_any(normalized, ("鉴别诊断", "诊断依据", "诊疗计划", "病例特点", "首次病程")):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "first_course_reasoning",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-023", "SC-024", "SC-025", "SC-026", "SC-027"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _contains_any(
        normalized,
        (
            "现病史",
            "主诉",
            "既往史",
            "前后矛盾",
            "体格检查",
            "专科检查",
            "专科查体",
            "院外检查",
            "阴性症状",
            "入院记录",
            "入院诊断",
        ),
    ):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "admission_consistency",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-008", "SC-009", "SC-010", "SC-011", "SC-012", "SC-018", "SC-019", "SC-020"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_consultation_execution_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "consultation_execution",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-070", "LX-016"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_consultation_record_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "consultation_record_quality",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-069"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_senior_round_content_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "senior_round_content",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-049", "SC-050", "SC-052"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_critical_value_management_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "critical_value_management",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-039"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_operation_preop_mdt_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "operation_preop_mdt",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-083"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_presurg_summary_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "presurg_summary_quality",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-081"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_operation_preop_conclusion_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "operation_preop_conclusion",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-084", "SC-085"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_operation_record_quality_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "operation_record_quality",
            "expected_scene": "final",
            "candidate_rule_ids": ["SC-097", "SC-098"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _looks_like_progress_order_consistency_issue(normalized):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "progress_order_consistency",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-146"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if _contains_any(
        normalized,
        (
            "病情变化",
            "分析",
            "处理意见",
            "异常检查",
            "辅助检查",
            "未记录",
            "病程记录",
        ),
    ):
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "daily_course_analysis",
            "expected_scene": "running",
            "candidate_rule_ids": ["SC-032", "SC-033", "SC-036"],
            "include_in_batch_1": True,
            "exclude_reason": "",
        }

    if "llm" in lowered:
        # 避免纯字符串测试时被误判成 unsupported
        return {
            "coverage_type": "llm_intrinsic",
            "issue_category": "manual_override",
            "expected_scene": "running",
            "candidate_rule_ids": [],
            "include_in_batch_1": False,
            "exclude_reason": "",
        }

    return {
        "coverage_type": "unsupported",
        "issue_category": "unclassified",
        "expected_scene": "running",
        "candidate_rule_ids": [],
        "include_in_batch_1": False,
        "exclude_reason": "当前未归入首批内涵问题分类，请人工确认",
    }


def build_sample_pool_item_classification_update(row: Dict[str, Any]) -> Dict[str, Any]:
    manual_issue_text = _safe_text(row.get("manual_issue_text"))
    classification = classify_manual_issue_text(manual_issue_text)
    return {
        "coverage_type": classification["coverage_type"],
        "issue_category": classification["issue_category"],
        "expected_scene": classification["expected_scene"],
        "candidate_rule_ids_json": _safe_json_dumps(classification["candidate_rule_ids"]),
        "include_in_batch_1": bool(classification["include_in_batch_1"]),
        "exclude_reason": _safe_text(classification["exclude_reason"]),
    }


_ISSUE_CATEGORY_RULE_MAP: Dict[str, List[str]] = {
    "record_list_intrinsic": list(_DEFAULT_INTRINSIC_RULE_IDS),
    "first_course_timeliness": ["SC-021", "SC-022"],
    "course_gap_timeliness": ["LXE-18"],
    "first_round_timeliness": ["SC-048", "SC-049"],
    "consultation_timeliness": ["SC-071", "SC-072"],
    "operation_record_timeliness": ["SC-096"],
    "unreasonable_copy_content": ["CL-273", "CL-274", "CL-275", "CL-276"],
    "first_course_reasoning": ["SC-023", "SC-024", "SC-025", "SC-026", "SC-027"],
    "admission_consistency": ["SC-008", "SC-009", "SC-010", "SC-011", "SC-012", "SC-018", "SC-019", "SC-020"],
    "daily_course_analysis": ["SC-032", "SC-033", "SC-036"],
    "consultation_execution": ["SC-070", "LX-016"],
    "consultation_record_quality": ["SC-069"],
    "handover_communication": ["SC-062", "SC-063"],
    "consent_quality": ["SC-128", "SC-087", "SC-089", "LX-021"],
    "critical_value_management": ["SC-039"],
    "progress_order_consistency": ["SC-146"],
    "senior_round_content": ["SC-049", "SC-050", "SC-052"],
    "operation_preop_mdt": ["SC-083"],
    "presurg_summary_quality": ["SC-081"],
    "operation_preop_conclusion": ["SC-084", "SC-085"],
    "postsurg_firstcourse_quality": ["SC-105"],
    "operation_record_quality": ["SC-097", "SC-098"],
}

_SAMPLE_SC_PRIMARY_RULE_WHITELIST: Dict[str, List[str]] = {
    "first_course_timeliness": ["SC-021"],
    "course_gap_timeliness": ["LXE-18"],
    "first_round_timeliness": ["SC-048"],
    "consultation_timeliness": ["SC-071"],
    "operation_record_timeliness": ["SC-096"],
    "consultation_execution": ["SC-070"],
    "consultation_record_quality": ["SC-069"],
    "handover_communication": ["SC-062"],
    "consent_quality": ["SC-128"],
    "critical_value_management": ["SC-039"],
    "senior_round_content": ["SC-050"],
    "daily_course_analysis": ["SC-036"],
    "progress_order_consistency": ["SC-146"],
    "operation_preop_mdt": ["SC-083"],
    "presurg_summary_quality": ["SC-081"],
    "operation_preop_conclusion": ["SC-084"],
    "postsurg_firstcourse_quality": ["SC-105"],
    "operation_record_quality": ["SC-097"],
}

_UNREASONABLE_COPY_CUSTOMER_RULE_IDS = ["CL-273", "CL-274", "CL-275", "CL-276"]


def _resolve_sample_sc_primary_rule_ids(*, issue_category: str, manual_issue_text: Any) -> List[str]:
    normalized = _normalize_issue_text(manual_issue_text)
    if not normalized:
        return list(_SAMPLE_SC_PRIMARY_RULE_WHITELIST.get(issue_category) or [])

    if issue_category == "first_course_timeliness":
        if _contains_any(normalized, ("术后首次病程", "术后病程记录")):
            return ["SC-105"]
        if _contains_any(
            normalized,
            (
                "72小时",
                "副主任医师",
                "主任医师",
                "高级职称医师",
                "上级医师查房",
            ),
        ) and not _contains_any(normalized, ("48小时", "主治医师")):
            return ["SC-049"]
        if _contains_any(
            normalized,
            (
                "病例特点",
                "诊断依据",
                "鉴别诊断",
                "诊疗计划",
                "拟诊讨论",
            ),
        ):
            return _resolve_sample_sc_primary_rule_ids(
                issue_category="first_course_reasoning",
                manual_issue_text=manual_issue_text,
            )
        if _contains_any(normalized, ("首次病程记录", "首程记录", "8小时", "24小时")):
            return ["SC-021"]
        return ["SC-022"]

    if issue_category == "course_gap_timeliness":
        return ["LXE-18"]

    if issue_category == "first_round_timeliness":
        if _contains_any(
            normalized,
            (
                "72小时",
                "高级职称医师",
                "副主任医师",
                "主任医师",
                "上级医师查房记录",
            ),
        ) and not _contains_any(normalized, ("48小时", "主治医师")):
            return ["SC-049"]
        return ["SC-048"]

    if issue_category == "consultation_timeliness":
        if _contains_any(normalized, ("申请时间", "接收时间", "时间节点", "会诊申请")):
            return ["SC-071"]
        return ["SC-072"]

    if issue_category == "operation_record_timeliness":
        return ["SC-096"]

    if issue_category == "first_course_reasoning":
        if _contains_any(
            normalized,
            (
                "无病例特点",
                "病例特点缺失",
            ),
        ):
            return ["SC-023"]
        if _contains_any(
            normalized,
            (
                "病例特点未归纳提炼",
                "病例特点不全面",
                "病例特点欠全面",
            ),
        ):
            return ["SC-024"]
        if _contains_any(
            normalized,
            (
                "无诊断依据",
                "无鉴别诊断",
                "无诊疗计划",
                "未书写诊断依据",
                "未书写鉴别诊断",
                "未书写诊疗计划",
                "诊断依据书写不正确",
                "只有主诊断有诊断依据及鉴别诊断",
                "其余诊断均未书写诊断依据及鉴别诊断",
            ),
        ):
            return ["SC-025"]
        if _contains_any(
            normalized,
            (
                "诊疗计划",
                "未提出具体诊疗计划",
                "未说明具体措施",
                "计划不完整",
                "计划不全面",
                "计划不具体",
            ),
        ):
            return ["SC-027"]
        if _contains_any(
            normalized,
            (
                "鉴别诊断",
                "诊断依据",
                "未查hcg",
                "未考虑宫外孕",
                "鉴别不全",
                "鉴别不充分",
                "仅鉴别",
            ),
        ):
            return ["SC-026"]
        return ["SC-026"]

    if issue_category == "admission_consistency":
        return list(ADMISSION_ISSUE_FAMILY_RULE_IDS)

    if issue_category == "daily_course_analysis":
        if _contains_any(
            normalized,
            (
                "72小时",
                "副主任医师",
                "主任医师",
                "高级职称医师",
                "上级医师查房",
            ),
        ):
            return ["SC-049"]
        if _contains_any(
            normalized,
            (
                "现病史",
                "主诉",
                "入院记录",
                "体格检查",
                "专科检查",
                "既往史",
                "外院诊治",
                "诊治经过",
                "治疗经过",
                "阴性症状",
                "阳性症状",
                "体重变化",
                "生命体征",
            ),
        ):
            return _resolve_sample_sc_primary_rule_ids(
                issue_category="admission_consistency",
                manual_issue_text=manual_issue_text,
            )
        if _contains_any(
            normalized,
            (
                "病情变化",
                "目前症状",
                "体征",
                "过于简略",
                "过于简单",
                "无具体内容",
                "未明确说明",
                "未体现",
                "未提及",
            ),
        ):
            return ["SC-032"]
        if _contains_any(
            normalized,
            (
                "用药",
                "抗菌药",
                "补钾",
                "处理措施",
                "未给处理",
                "无处理",
                "未记录使用情况",
                "未体现具体用药处理",
                "未给出处理措施",
            ),
        ):
            return ["SC-033"]
        return list(_SAMPLE_SC_PRIMARY_RULE_WHITELIST.get(issue_category) or [])

    if issue_category == "handover_communication":
        if _contains_any(
            normalized,
            (
                "未书写交接班记录",
                "无交接班记录",
                "无交班记录",
                "无接班记录",
                "未完成交接班记录",
                "未完成接班记录",
            ),
        ):
            return ["SC-062"]
        return ["SC-063"]

    if issue_category == "consent_quality":
        if _contains_any(
            normalized,
            (
                "非授权受托人",
                "非法定代理人",
                "非本人",
                "授权委托",
                "委托人",
                "监护人",
                "签字人员",
            ),
        ):
            return ["SC-128"]
        if _contains_any(
            normalized,
            (
                "术中更改术式",
                "改变手术方式",
                "扩大手术范围",
            ),
        ):
            return ["LX-021"]
        if _contains_any(normalized, ("缺项", "描述不清")):
            return ["SC-089"]
        return ["SC-087"]

    if issue_category == "operation_record_quality":
        return ["SC-097"]

    if issue_category == "operation_preop_mdt":
        return ["SC-083"]

    if issue_category == "presurg_summary_quality":
        return ["SC-081"]

    if issue_category == "operation_preop_conclusion":
        if _contains_any(
            normalized,
            (
                "未明确手术时间",
                "未明确手术医生",
                "讨论内容未书写明确",
                "缺少参与人员发言",
                "缺项",
            ),
        ):
            return ["SC-085"]
        return ["SC-084"]

    if issue_category == "postsurg_firstcourse_quality":
        return ["SC-105"]

    return list(_SAMPLE_SC_PRIMARY_RULE_WHITELIST.get(issue_category) or [])


def _resolve_unreasonable_copy_customer_rule_ids(manual_issue_text: Any) -> List[str]:
    normalized = _normalize_issue_text(manual_issue_text)
    if not normalized:
        return list(_UNREASONABLE_COPY_CUSTOMER_RULE_IDS)
    if _contains_any(normalized, ("同科同种疾病", "同种疾病", "同科")) and _contains_any(
        normalized,
        ("拟诊讨论", "诊断依据", "鉴别诊断"),
    ):
        return ["CL-276"]
    if _contains_any(normalized, ("拟诊讨论", "诊断依据", "鉴别诊断")) and _contains_any(
        normalized,
        ("病例特点", "重复病例特点"),
    ):
        return ["CL-274"]
    if _contains_any(normalized, ("入院记录", "现病史")) and "病例特点" in normalized:
        return ["CL-273"]
    return ["CL-275"]


def _looks_like_rule_id(value: str) -> bool:
    text = _safe_text(value)
    if not text:
        return False
    return bool(re.fullmatch(r"[A-Z]{2,}(?:-[A-Z0-9]+)+", text) or re.fullmatch(r"[A-Z]{2,}-\d+", text))


def _normalize_candidate_rule_ids(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        result: List[str] = []
        for item in value:
            text = _safe_text(item)
            if text and _looks_like_rule_id(text) and text not in result:
                result.append(text)
        return result
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        parsed = _safe_json_loads(text, None)
        if parsed is not None and parsed is not value:
            return _normalize_candidate_rule_ids(parsed)
        parts = [segment.strip() for segment in re.split(r"[,\n;；]+", text) if segment.strip()]
        result: List[str] = []
        for item in parts:
            if _looks_like_rule_id(item) and item not in result:
                result.append(item)
        return result
    return []


def _fallback_candidate_rule_ids(
    *,
    coverage_type: str,
    issue_category: str,
    manual_issue_text: Any,
) -> List[str]:
    if coverage_type != "llm_intrinsic":
        return []
    mapped = _ISSUE_CATEGORY_RULE_MAP.get(issue_category)
    if mapped:
        return list(mapped)
    classification = classify_manual_issue_text(manual_issue_text)
    if classification.get("coverage_type") != "llm_intrinsic":
        return []
    return _normalize_candidate_rule_ids(classification.get("candidate_rule_ids"))


def _apply_sample_sc_rule_whitelist(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered_items: List[Dict[str, Any]] = []
    for raw_item in items:
        item = dict(raw_item)
        issue_category = _safe_text(item.get("issue_category"), "unclassified")
        if issue_category == "unreasonable_copy_content":
            item["candidate_rule_ids"] = _resolve_unreasonable_copy_customer_rule_ids(
                item.get("manual_issue_text")
            )
            filtered_items.append(item)
            continue
        if issue_category == "admission_consistency":
            existing_rule_ids = _normalize_candidate_rule_ids(item.get("candidate_rule_ids"))
            allowed = set(ADMISSION_ISSUE_FAMILY_RULE_IDS)
            filtered_rule_ids = [rule_id for rule_id in existing_rule_ids if rule_id in allowed]
            item["candidate_rule_ids"] = filtered_rule_ids or list(ADMISSION_ISSUE_FAMILY_RULE_IDS)
            filtered_items.append(item)
            continue
        whitelist_rule_ids = _resolve_sample_sc_primary_rule_ids(
            issue_category=issue_category,
            manual_issue_text=item.get("manual_issue_text"),
        )
        if whitelist_rule_ids:
            item["candidate_rule_ids"] = list(whitelist_rule_ids)
        filtered_items.append(item)
    return filtered_items


def load_manual_case_rows_from_excel(*, file_path: str, sheet_name: str = "Sheet2") -> List[Dict[str, Any]]:
    import pandas as pd

    requested_sheet = _safe_text(sheet_name)
    try:
        df = pd.read_excel(file_path, sheet_name=requested_sheet or 0, header=None)
    except ValueError:
        if requested_sheet and requested_sheet != "Sheet2":
            raise
        df = pd.read_excel(file_path, sheet_name=0, header=None)
    if df.empty or len(df.index) < 1:
        return []
    known_headers = {"科室", "患者姓名", "住院号", "visit_id", "存在问题", "责任医生", "质控日期", "质控人员"}
    header_index = 0
    for idx in range(min(len(df.index), 3)):
        row_headers = {str(item).strip() for item in df.iloc[idx].tolist() if str(item).strip()}
        if row_headers & known_headers:
            header_index = idx
            break
    header_row = [str(item).strip() for item in df.iloc[header_index].tolist()]
    data = df.iloc[header_index + 1 :].copy()
    data.columns = header_row
    rows: List[Dict[str, Any]] = []
    for index, raw in enumerate(data.to_dict(orient="records"), start=header_index + 2):
        mr_no = _safe_text(raw.get("住院号"))
        visit_id = _safe_text(raw.get("visit_id") or raw.get("VisitID") or raw.get("VISIT_ID"))
        issue_text = _safe_text(raw.get("存在问题"))
        patient_name = _safe_text(raw.get("患者姓名"))
        if not mr_no and not visit_id and not issue_text and not patient_name:
            continue
        rows.append(
            {
                "row_no": index,
                "department": _safe_text(raw.get("科室")),
                "patient_name": patient_name,
                "mr_no": mr_no,
                "visit_id": visit_id,
                "manual_issue_text": issue_text,
                "doctor_name": _safe_text(raw.get("责任医生")),
                "qc_date": raw.get("质控日期"),
                "qc_user": _safe_text(raw.get("质控人员")),
            }
        )
    return rows


def _score_candidate(
    *,
    row: Any,
    patient_name: str,
    department: str,
    qc_date_value: Optional[date],
) -> int:
    score = 0
    row_name = _safe_text(getattr(row, "name", ""))
    row_department = _safe_text(getattr(row, "admission_dept_name", "") or getattr(row, "discharge_dept_name", ""))
    if patient_name and row_name == patient_name:
        score += 100
    if department and row_department == department:
        score += 50
    admission_dt = getattr(row, "admission_datetime", None)
    discharge_dt = getattr(row, "discharge_datetime", None)
    if qc_date_value:
        admission_date = _parse_date(admission_dt)
        discharge_date = _parse_date(discharge_dt)
        if admission_date and discharge_date and admission_date <= qc_date_value <= discharge_date:
            score += 40
        elif admission_date:
            score += max(0, 15 - abs((qc_date_value - admission_date).days))
        elif discharge_date:
            score += max(0, 15 - abs((qc_date_value - discharge_date).days))
    return score


def _score_remote_candidate(
    *,
    candidate: Dict[str, Any],
    patient_name: str,
    department: str,
    qc_date_value: Optional[date],
) -> int:
    score = 0
    row_name = _safe_text(candidate.get("name"))
    row_department = _safe_text(
        candidate.get("admission_dept_name") or candidate.get("discharge_dept_name") or candidate.get("dept_name")
    )
    if patient_name and row_name == patient_name:
        score += 100
    if department and row_department == department:
        score += 50
    if qc_date_value:
        admission_date = _parse_date(candidate.get("admission_datetime"))
        discharge_date = _parse_date(candidate.get("discharge_datetime"))
        if admission_date and discharge_date and admission_date <= qc_date_value <= discharge_date:
            score += 40
        elif admission_date:
            score += max(0, 15 - abs((qc_date_value - admission_date).days))
        elif discharge_date:
            score += max(0, 15 - abs((qc_date_value - discharge_date).days))
    return score


def _pick_best_local_candidate(
    *,
    candidates: Sequence[Any],
    patient_name: str,
    department: str,
    qc_date_value: Optional[date],
) -> Optional[Any]:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    return _choose_scored_candidate(
        [
            (
                _score_candidate(
                    row=candidate,
                    patient_name=patient_name,
                    department=department,
                    qc_date_value=qc_date_value,
                ),
                candidate,
            )
            for candidate in candidates
        ],
        get_recency_key=lambda item: _candidate_recency_key(
            admission_value=getattr(item, "admission_datetime", None),
            discharge_value=getattr(item, "discharge_datetime", None),
            update_value=getattr(item, "update_time", None),
            visit_id=getattr(item, "visit_id", None),
        ),
    )


def _pick_best_remote_candidate(
    *,
    candidates: Sequence[Dict[str, Any]],
    patient_name: str,
    department: str,
    qc_date_value: Optional[date],
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    return _choose_scored_candidate(
        [
            (
                _score_remote_candidate(
                    candidate=candidate,
                    patient_name=patient_name,
                    department=department,
                    qc_date_value=qc_date_value,
                ),
                candidate,
            )
            for candidate in candidates
        ],
        get_recency_key=lambda candidate: _candidate_recency_key(
            admission_value=candidate.get("admission_datetime"),
            discharge_value=candidate.get("discharge_datetime"),
            update_value=candidate.get("update_time"),
            visit_id=candidate.get("visit_id"),
        ),
    )


def _candidate_recency_key(
    *,
    admission_value: Any,
    discharge_value: Any,
    update_value: Any,
    visit_id: Any,
) -> tuple[date, date, date, str]:
    update_date = _parse_date(update_value) or date.min
    discharge_date = _parse_date(discharge_value) or date.min
    admission_date = _parse_date(admission_value) or date.min
    return (max(update_date, discharge_date, admission_date), discharge_date, admission_date, _safe_text(visit_id))


def _choose_scored_candidate(
    scored_candidates: Sequence[tuple[int, Any]],
    *,
    get_recency_key: Callable[[Any], tuple[date, date, date, str]],
) -> Optional[Any]:
    if not scored_candidates:
        return None
    ranked = sorted(scored_candidates, key=lambda item: item[0], reverse=True)
    top_score = ranked[0][0]
    if len(ranked) == 1:
        return ranked[0][1]
    if top_score > 0 and top_score > ranked[1][0]:
        return ranked[0][1]
    recency_candidates = [candidate for score, candidate in ranked if score == top_score]
    recency_ranked = sorted(
        ((get_recency_key(candidate), candidate) for candidate in recency_candidates),
        key=lambda item: item[0],
        reverse=True,
    )
    if recency_ranked:
        return recency_ranked[0][1]
    return None


@lru_cache(maxsize=1)
def _sample_pools_table() -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
    metadata = MetaData()
    table = Table(
        "manual_problem_sample_pools",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_file", sa.String(500), nullable=False),
        sa.Column("source_sheet", sa.String(100), nullable=False),
        sa.Column("scene", sa.String(20), nullable=False, default="running"),
        sa.Column("description", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("total_items", sa.Integer, nullable=False, default=0),
        sa.Column("llm_intrinsic_items", sa.Integer, nullable=False, default=0),
        sa.Column("programmatic_items", sa.Integer, nullable=False, default=0),
        sa.Column("unsupported_items", sa.Integer, nullable=False, default=0),
        sa.Column("matched_items", sa.Integer, nullable=False, default=0),
        sa.Column("ambiguous_items", sa.Integer, nullable=False, default=0),
        sa.Column("unmatched_items", sa.Integer, nullable=False, default=0),
        sa.Column("ready_items", sa.Integer, nullable=False, default=0),
        sa.Column("latest_job_id", sa.String(36)),
        sa.Column("latest_job_status", sa.String(20)),
        schema=_schema(),
    )
    metadata.create_all(bind=engine, checkfirst=True)
    return table


@lru_cache(maxsize=1)
def _sample_pool_items_table() -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
    metadata = MetaData()
    table = Table(
        "manual_problem_sample_pool_items",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pool_id", sa.String(36), nullable=False, index=True),
        sa.Column("row_no", sa.Integer, nullable=False),
        sa.Column("department", sa.String(100)),
        sa.Column("patient_name", sa.String(100)),
        sa.Column("mr_no", sa.String(100), index=True),
        sa.Column("manual_issue_text", sa.Text, nullable=False),
        sa.Column("normalized_issue_text", sa.Text, nullable=False),
        sa.Column("doctor_name", sa.String(100)),
        sa.Column("qc_date", sa.Date),
        sa.Column("qc_user", sa.String(100)),
        sa.Column("coverage_type", sa.String(30), nullable=False, default="unsupported"),
        sa.Column("issue_category", sa.String(100), nullable=False, default="unclassified"),
        sa.Column("expected_scene", sa.String(20), nullable=False, default="running"),
        sa.Column("candidate_rule_ids_json", sa.Text, nullable=False, default="[]"),
        sa.Column("include_in_batch_1", sa.Boolean, nullable=False, default=False),
        sa.Column("exclude_reason", sa.Text),
        sa.Column("matched_institute_id", sa.String(100)),
        sa.Column("matched_patient_id", sa.String(100)),
        sa.Column("matched_visit_id", sa.String(100), index=True),
        sa.Column("match_status", sa.String(20), nullable=False, default="unmatched"),
        sa.Column("sync_status", sa.String(20), nullable=False, default="pending"),
        sa.Column("bundle_status", sa.String(20), nullable=False, default="pending"),
        sa.Column("latest_job_id", sa.String(36)),
        sa.Column("latest_match_status", sa.String(20)),
        sa.Column("raw_payload_json", sa.Text, nullable=False, default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        schema=_schema(),
    )
    metadata.create_all(bind=engine, checkfirst=True)
    return table


@lru_cache(maxsize=1)
def _sample_pool_sync_jobs_table() -> Table:
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured; sample pool unavailable")
    metadata = MetaData()
    table = Table(
        "manual_problem_sample_pool_sync_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pool_id", sa.String(36), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, default="queued"),
        sa.Column("payload_json", sa.Text, nullable=False, default="{}"),
        sa.Column("summary_json", sa.Text, nullable=False, default="{}"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        schema=_schema(),
    )
    metadata.create_all(bind=engine, checkfirst=True)
    return table


@dataclass
class SamplePoolListResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class CustomQCSamplePoolService:
    def __init__(self) -> None:
        self._pool_table = _sample_pools_table()
        self._item_table = _sample_pool_items_table()
        self._sync_job_table = _sample_pool_sync_jobs_table()

    @staticmethod
    def resolve_sync_table_names(group_ids: Optional[Sequence[str]] = None) -> Dict[str, List[str]]:
        default_group_ids = ["sample_full_domain"]
        selected_groups = [str(item).strip() for item in (group_ids or default_group_ids) if str(item).strip()]
        table_names, missing = expand_table_groups(selected_groups)
        if not table_names:
            raise ValueError("未解析到可执行同步表，请检查 table_groups 配置")
        return {
            "group_ids": selected_groups,
            "table_names": table_names,
            "missing_group_ids": missing,
        }

    def _row_to_pool(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": _safe_text(row.get("id")),
            "name": _safe_text(row.get("name")),
            "source_file": _safe_text(row.get("source_file")),
            "source_sheet": _safe_text(row.get("source_sheet")),
            "scene": _safe_text(row.get("scene"), "running"),
            "description": _safe_text(row.get("description")),
            "created_by": _safe_text(row.get("created_by")),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "total_items": int(row.get("total_items") or 0),
            "llm_intrinsic_items": int(row.get("llm_intrinsic_items") or 0),
            "programmatic_items": int(row.get("programmatic_items") or 0),
            "unsupported_items": int(row.get("unsupported_items") or 0),
            "matched_items": int(row.get("matched_items") or 0),
            "ambiguous_items": int(row.get("ambiguous_items") or 0),
            "unmatched_items": int(row.get("unmatched_items") or 0),
            "ready_items": int(row.get("ready_items") or 0),
            "latest_job_id": _safe_text(row.get("latest_job_id")),
            "latest_job_status": _safe_text(row.get("latest_job_status")),
        }

    def _row_to_item(self, row: Dict[str, Any]) -> Dict[str, Any]:
        raw_payload = _safe_json_loads(row.get("raw_payload_json"), {})
        visit_id = _safe_text(
            raw_payload.get("visit_id") if isinstance(raw_payload, dict) else ""
        )
        coverage_type = _safe_text(row.get("coverage_type"), "unsupported")
        issue_category = _safe_text(row.get("issue_category"), "unclassified")
        manual_issue_text = _safe_text(row.get("manual_issue_text"))
        candidate_rule_ids = _normalize_candidate_rule_ids(row.get("candidate_rule_ids_json"))
        if not candidate_rule_ids:
            candidate_rule_ids = _fallback_candidate_rule_ids(
                coverage_type=coverage_type,
                issue_category=issue_category,
                manual_issue_text=manual_issue_text,
            )
        return {
            "id": _safe_text(row.get("id")),
            "pool_id": _safe_text(row.get("pool_id")),
            "row_no": int(row.get("row_no") or 0),
            "department": _safe_text(row.get("department")),
            "patient_name": _safe_text(row.get("patient_name")),
            "mr_no": _safe_text(row.get("mr_no")),
            "visit_id": visit_id,
            "manual_issue_text": manual_issue_text,
            "normalized_issue_text": _safe_text(row.get("normalized_issue_text")),
            "doctor_name": _safe_text(row.get("doctor_name")),
            "qc_date": _to_iso_date(row.get("qc_date")),
            "qc_user": _safe_text(row.get("qc_user")),
            "coverage_type": coverage_type,
            "issue_category": issue_category,
            "expected_scene": _safe_text(row.get("expected_scene"), "running"),
            "candidate_rule_ids": candidate_rule_ids,
            "include_in_batch_1": bool(row.get("include_in_batch_1")),
            "exclude_reason": _safe_text(row.get("exclude_reason")),
            "matched_institute_id": _safe_text(row.get("matched_institute_id")),
            "matched_patient_id": _safe_text(row.get("matched_patient_id")),
            "matched_visit_id": _safe_text(row.get("matched_visit_id")),
            "match_status": _safe_text(row.get("match_status"), "unmatched"),
            "sync_status": _safe_text(row.get("sync_status"), "pending"),
            "bundle_status": _safe_text(row.get("bundle_status"), "pending"),
            "latest_job_id": _safe_text(row.get("latest_job_id")),
            "latest_match_status": _safe_text(row.get("latest_match_status")),
            "raw_payload": raw_payload,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def _load_bundle_source_table_map(self, *, visit_ids: Sequence[str]) -> Dict[str, set[str]]:
        normalized_ids = [str(item).strip() for item in visit_ids if str(item).strip()]
        if not normalized_ids or engine is None:
            return {}
        sql = (
            sa.text(
                """
                SELECT visit_id::text AS visit_id,
                       COALESCE(doc.value ->> 'source_table', doc.value ->> 'document_type', '') AS source_table
                FROM public.running_record_bundle
                CROSS JOIN LATERAL jsonb_array_elements(
                    COALESCE((structured_context::jsonb -> 'document_inventory'), '[]'::jsonb)
                ) AS doc(value)
                WHERE visit_id IN :visit_ids

                UNION ALL

                SELECT visit_id::text AS visit_id,
                       COALESCE(doc.value ->> 'source_table', doc.value ->> 'document_type', '') AS source_table
                FROM public.final_record_bundle
                CROSS JOIN LATERAL jsonb_array_elements(
                    COALESCE((structured_context::jsonb -> 'document_inventory'), '[]'::jsonb)
                ) AS doc(value)
                WHERE visit_id IN :visit_ids
                """
            )
            .bindparams(sa.bindparam("visit_ids", expanding=True))
        )
        source_table_map: Dict[str, set[str]] = {}
        try:
            with engine.connect() as conn:
                rows = conn.execute(sql, {"visit_ids": normalized_ids}).mappings().all()
        except Exception:
            return {}
        for row in rows:
            visit_id = _safe_text(row.get("visit_id"))
            source_table = _safe_text(row.get("source_table")).lower()
            if not visit_id or not source_table:
                continue
            source_table_map.setdefault(visit_id, set()).add(source_table)
        return source_table_map

    def _apply_dynamic_candidate_rule_ids(
        self,
        *,
        items: Sequence[Dict[str, Any]],
        source_table_map: Optional[Dict[str, set[str]]] = None,
    ) -> List[Dict[str, Any]]:
        item_list = [dict(item) for item in items]
        visit_ids = [
            str(item.get("matched_visit_id") or "").strip()
            for item in item_list
            if str(item.get("matched_visit_id") or "").strip()
        ]
        effective_source_table_map = source_table_map or self._load_bundle_source_table_map(visit_ids=visit_ids)
        if not effective_source_table_map:
            return item_list
        for item in item_list:
            visit_id = str(item.get("matched_visit_id") or "").strip()
            if not visit_id:
                continue
            dynamic_rule_ids = _derive_dynamic_candidate_rule_ids_from_source_tables(
                sorted(effective_source_table_map.get(visit_id, set()))
            )
            if not dynamic_rule_ids:
                continue
            item["candidate_rule_ids"] = _merge_candidate_rule_ids(
                base_rule_ids=item.get("candidate_rule_ids") or [],
                dynamic_rule_ids=dynamic_rule_ids,
                coverage_type=_safe_text(item.get("coverage_type"), "unsupported"),
                manual_issue_text=_safe_text(item.get("manual_issue_text")),
            )
        return item_list

    def _row_to_sync_job(self, row: Dict[str, Any]) -> Dict[str, Any]:
        summary = _safe_json_loads(row.get("summary_json"), {})
        if not isinstance(summary, dict):
            summary = {}
        return {
            "id": _safe_text(row.get("id")),
            "pool_id": _safe_text(row.get("pool_id")),
            "status": _safe_text(row.get("status"), "queued"),
            "payload": _safe_json_loads(row.get("payload_json"), {}),
            "summary": summary,
            "error_message": _safe_text(row.get("error_message")),
            "created_by": _safe_text(row.get("created_by")),
            "created_at": row.get("created_at"),
            "started_at": row.get("started_at"),
            "finished_at": row.get("finished_at"),
            "updated_at": row.get("updated_at"),
        }

    def _update_pool_counters(self, session: Session, pool_id: str) -> None:
        item_table = self._item_table
        stats_stmt = select(
            func.count().label("total_items"),
            func.sum(sa.case((item_table.c.coverage_type == "llm_intrinsic", 1), else_=0)).label("llm_intrinsic_items"),
            func.sum(sa.case((item_table.c.coverage_type == "programmatic", 1), else_=0)).label("programmatic_items"),
            func.sum(sa.case((item_table.c.coverage_type == "unsupported", 1), else_=0)).label("unsupported_items"),
            func.sum(sa.case((item_table.c.match_status == "matched", 1), else_=0)).label("matched_items"),
            func.sum(sa.case((item_table.c.match_status == "ambiguous", 1), else_=0)).label("ambiguous_items"),
            func.sum(sa.case((item_table.c.match_status == "unmatched", 1), else_=0)).label("unmatched_items"),
            func.sum(sa.case((item_table.c.bundle_status == "ready", 1), else_=0)).label("ready_items"),
        ).where(item_table.c.pool_id == pool_id)
        stats = session.execute(stats_stmt).mappings().first() or {}
        session.execute(
            update(self._pool_table)
            .where(self._pool_table.c.id == pool_id)
            .values(
                updated_at=_now_utc(),
                total_items=int(stats.get("total_items") or 0),
                llm_intrinsic_items=int(stats.get("llm_intrinsic_items") or 0),
                programmatic_items=int(stats.get("programmatic_items") or 0),
                unsupported_items=int(stats.get("unsupported_items") or 0),
                matched_items=int(stats.get("matched_items") or 0),
                ambiguous_items=int(stats.get("ambiguous_items") or 0),
                unmatched_items=int(stats.get("unmatched_items") or 0),
                ready_items=int(stats.get("ready_items") or 0),
            )
        )

    def list_pools(self, *, page: int = 1, page_size: int = 20, query: Optional[str] = None) -> SamplePoolListResult:
        session = _session()
        try:
            clauses = []
            if query:
                keyword = f"%{query.strip()}%"
                clauses.append(
                    or_(
                        self._pool_table.c.name.ilike(keyword),
                        self._pool_table.c.source_file.ilike(keyword),
                    )
                )
            where_clause = and_(*clauses) if clauses else None
            total_stmt = select(func.count()).select_from(self._pool_table)
            if where_clause is not None:
                total_stmt = total_stmt.where(where_clause)
            total = int(session.execute(total_stmt).scalar() or 0)
            stmt = select(self._pool_table)
            if where_clause is not None:
                stmt = stmt.where(where_clause)
            stmt = (
                stmt.order_by(desc(self._pool_table.c.updated_at), desc(self._pool_table.c.created_at))
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
            rows = session.execute(stmt).mappings().all()
            return SamplePoolListResult(
                items=[self._row_to_pool(dict(row)) for row in rows],
                total=total,
                page=page,
                page_size=page_size,
            )
        finally:
            session.close()

    def get_pool(self, *, pool_id: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            stmt = select(self._pool_table).where(self._pool_table.c.id == pool_id)
            row = session.execute(stmt).mappings().first()
            return self._row_to_pool(dict(row)) if row else None
        finally:
            session.close()

    def create_sync_job(
        self,
        *,
        pool_id: str,
        created_by: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        session = _session()
        now = _now_utc()
        job_id = str(uuid.uuid4())
        summary = {
            "progress": {
                "step_key": "queued",
                "step_label": "排队中",
                "total_candidates": 0,
                "eligible_visits": 0,
                "processed_tables": 0,
                "total_tables": 0,
                "current_table": "",
                "remaining_tables": 0,
            },
            "total_rows_pulled": 0,
            "total_rows_upserted": 0,
        }
        try:
            session.execute(
                self._sync_job_table.insert().values(
                    id=job_id,
                    pool_id=pool_id,
                    status="queued",
                    payload_json=_safe_json_dumps(payload),
                    summary_json=_safe_json_dumps(summary),
                    error_message=None,
                    created_by=_safe_text(created_by),
                    created_at=now,
                    started_at=None,
                    finished_at=None,
                    updated_at=now,
                )
            )
            session.commit()
            return {
                "id": job_id,
                "pool_id": pool_id,
                "status": "queued",
                "payload": payload,
                "summary": summary,
                "created_at": now,
                "updated_at": now,
            }
        finally:
            session.close()

    def get_sync_job(self, *, job_id: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            stmt = select(self._sync_job_table).where(self._sync_job_table.c.id == job_id)
            row = session.execute(stmt).mappings().first()
            return self._row_to_sync_job(dict(row)) if row else None
        finally:
            session.close()

    def get_latest_sync_job(self, *, pool_id: str) -> Optional[Dict[str, Any]]:
        session = _session()
        try:
            stmt = (
                select(self._sync_job_table)
                .where(self._sync_job_table.c.pool_id == pool_id)
                .order_by(desc(self._sync_job_table.c.created_at))
                .limit(1)
            )
            row = session.execute(stmt).mappings().first()
            return self._row_to_sync_job(dict(row)) if row else None
        finally:
            session.close()

    def mark_sync_job_running(self, *, job_id: str) -> bool:
        session = _session()
        try:
            current = session.execute(
                select(self._sync_job_table).where(self._sync_job_table.c.id == job_id)
            ).mappings().first()
            if not current:
                return False
            summary = _safe_json_loads(current.get("summary_json"), {})
            if not isinstance(summary, dict):
                summary = {}
            progress = summary.get("progress")
            if not isinstance(progress, dict):
                progress = {}
            progress.update(
                {
                    "step_key": "running",
                    "step_label": "正在同步样本病历",
                }
            )
            summary["progress"] = progress
            session.execute(
                update(self._sync_job_table)
                .where(self._sync_job_table.c.id == job_id)
                .values(
                    status="running",
                    started_at=_now_utc(),
                    updated_at=_now_utc(),
                    summary_json=_safe_json_dumps(summary),
                )
            )
            session.commit()
            return True
        finally:
            session.close()

    def update_sync_job_progress(
        self,
        *,
        job_id: str,
        progress: Dict[str, Any],
        summary_patch: Optional[Dict[str, Any]] = None,
    ) -> bool:
        session = _session()
        try:
            current = session.execute(
                select(self._sync_job_table).where(self._sync_job_table.c.id == job_id)
            ).mappings().first()
            if not current:
                return False
            summary = _safe_json_loads(current.get("summary_json"), {})
            if not isinstance(summary, dict):
                summary = {}
            current_progress = summary.get("progress")
            if not isinstance(current_progress, dict):
                current_progress = {}
            current_progress.update(progress)
            summary["progress"] = current_progress
            if summary_patch:
                summary.update(summary_patch)
            session.execute(
                update(self._sync_job_table)
                .where(self._sync_job_table.c.id == job_id)
                .values(
                    updated_at=_now_utc(),
                    summary_json=_safe_json_dumps(summary),
                )
            )
            session.commit()
            return True
        finally:
            session.close()

    def finish_sync_job(self, *, job_id: str, summary: Dict[str, Any]) -> bool:
        session = _session()
        try:
            current = session.execute(
                select(self._sync_job_table).where(self._sync_job_table.c.id == job_id)
            ).mappings().first()
            if not current:
                return False
            final_summary = _safe_json_loads(current.get("summary_json"), {})
            if not isinstance(final_summary, dict):
                final_summary = {}
            final_summary.update(summary)
            progress = final_summary.get("progress")
            if not isinstance(progress, dict):
                progress = {}
            progress.update(
                {
                    "step_key": "completed",
                    "step_label": "同步完成",
                    "remaining_tables": 0,
                }
            )
            final_summary["progress"] = progress
            session.execute(
                update(self._sync_job_table)
                .where(self._sync_job_table.c.id == job_id)
                .values(
                    status="completed",
                    finished_at=_now_utc(),
                    updated_at=_now_utc(),
                    summary_json=_safe_json_dumps(final_summary),
                )
            )
            session.commit()
            return True
        finally:
            session.close()

    def fail_sync_job(self, *, job_id: str, error_message: str, summary_patch: Optional[Dict[str, Any]] = None) -> bool:
        session = _session()
        try:
            current = session.execute(
                select(self._sync_job_table).where(self._sync_job_table.c.id == job_id)
            ).mappings().first()
            if not current:
                return False
            summary = _safe_json_loads(current.get("summary_json"), {})
            if not isinstance(summary, dict):
                summary = {}
            progress = summary.get("progress")
            if not isinstance(progress, dict):
                progress = {}
            progress.update(
                {
                    "step_key": "failed",
                    "step_label": "同步失败",
                }
            )
            summary["progress"] = progress
            if summary_patch:
                summary.update(summary_patch)
            session.execute(
                update(self._sync_job_table)
                .where(self._sync_job_table.c.id == job_id)
                .values(
                    status="failed",
                    error_message=_safe_text(error_message),
                    finished_at=_now_utc(),
                    updated_at=_now_utc(),
                    summary_json=_safe_json_dumps(summary),
                )
            )
            session.commit()
            return True
        finally:
            session.close()

    def create_pool_with_items(
        self,
        *,
        name: str,
        source_file: str,
        source_sheet: str,
        created_by: str,
        rows: Iterable[Dict[str, Any]],
        description: Optional[str] = None,
        scene: str = "running",
    ) -> Dict[str, Any]:
        session = _session()
        try:
            pool_id = str(uuid.uuid4())
            now = _now_utc()
            session.execute(
                self._pool_table.insert().values(
                    id=pool_id,
                    name=_safe_text(name, "客户样本池"),
                    source_file=_safe_text(source_file),
                    source_sheet=_safe_text(source_sheet, "Sheet2"),
                    scene=_safe_text(scene, "running"),
                    description=_safe_text(description),
                    created_by=_safe_text(created_by, "system"),
                    created_at=now,
                    updated_at=now,
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
            payload_rows = []
            for index, raw in enumerate(rows, start=1):
                classification = classify_manual_issue_text(raw.get("manual_issue_text"))
                payload_rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "pool_id": pool_id,
                        "row_no": int(raw.get("row_no") or index),
                        "department": _safe_text(raw.get("department")),
                        "patient_name": _safe_text(raw.get("patient_name")),
                        "mr_no": _safe_text(raw.get("mr_no")),
                        "manual_issue_text": _safe_text(raw.get("manual_issue_text")),
                        "normalized_issue_text": _normalize_issue_text(raw.get("manual_issue_text")),
                        "doctor_name": _safe_text(raw.get("doctor_name")),
                        "qc_date": _parse_date(raw.get("qc_date")),
                        "qc_user": _safe_text(raw.get("qc_user")),
                        "coverage_type": classification["coverage_type"],
                        "issue_category": classification["issue_category"],
                        "expected_scene": classification["expected_scene"],
                        "candidate_rule_ids_json": _safe_json_dumps(classification["candidate_rule_ids"]),
                        "include_in_batch_1": bool(classification["include_in_batch_1"]),
                        "exclude_reason": _safe_text(classification["exclude_reason"]),
                        "matched_institute_id": "",
                        "matched_patient_id": "",
                        "matched_visit_id": "",
                        "match_status": "unmatched",
                        "sync_status": "pending",
                        "bundle_status": "pending",
                        "latest_job_id": "",
                        "latest_match_status": "",
                        "raw_payload_json": _safe_json_dumps(raw),
                        "created_at": now,
                        "updated_at": now,
                    }
                )
            if payload_rows:
                session.execute(self._item_table.insert(), payload_rows)
            self._update_pool_counters(session, pool_id)
            session.commit()
            return self.get_pool(pool_id=pool_id) or {"id": pool_id}
        finally:
            session.close()

    def refresh_pool_item_classifications(
        self,
        *,
        pool_id: str,
        item_ids: Optional[Sequence[str]] = None,
        only_unclassified: bool = False,
    ) -> Dict[str, Any]:
        session = _session()
        try:
            clauses = [self._item_table.c.pool_id == pool_id]
            if only_unclassified:
                clauses.append(self._item_table.c.issue_category == "unclassified")
            normalized_item_ids = [str(item_id).strip() for item_id in list(item_ids or []) if str(item_id).strip()]
            if normalized_item_ids:
                clauses.append(self._item_table.c.id.in_(normalized_item_ids))

            stmt = (
                select(self._item_table)
                .where(and_(*clauses))
                .order_by(self._item_table.c.row_no.asc())
            )
            rows = session.execute(stmt).mappings().all()
            if not rows:
                return {
                    "pool_id": pool_id,
                    "scanned": 0,
                    "updated": 0,
                    "changed_categories": 0,
                    "changed_coverages": 0,
                    "pool": self.get_pool(pool_id=pool_id),
                }

            updated = 0
            changed_categories = 0
            changed_coverages = 0
            for row in rows:
                row_dict = dict(row)
                patch = build_sample_pool_item_classification_update(row_dict)
                current_category = _safe_text(row_dict.get("issue_category"), "unclassified")
                current_coverage = _safe_text(row_dict.get("coverage_type"), "unsupported")
                current_expected_scene = _safe_text(row_dict.get("expected_scene"), "running")
                current_candidate_rule_ids_json = _safe_text(row_dict.get("candidate_rule_ids_json"), "[]")
                current_exclude_reason = _safe_text(row_dict.get("exclude_reason"))
                current_include_in_batch_1 = bool(row_dict.get("include_in_batch_1"))

                if current_category != patch["issue_category"]:
                    changed_categories += 1
                if current_coverage != patch["coverage_type"]:
                    changed_coverages += 1

                if (
                    current_category == patch["issue_category"]
                    and current_coverage == patch["coverage_type"]
                    and current_expected_scene == patch["expected_scene"]
                    and current_candidate_rule_ids_json == patch["candidate_rule_ids_json"]
                    and current_exclude_reason == patch["exclude_reason"]
                    and current_include_in_batch_1 == patch["include_in_batch_1"]
                ):
                    continue

                session.execute(
                    update(self._item_table)
                    .where(self._item_table.c.id == row_dict["id"])
                    .values(
                        **patch,
                        updated_at=_now_utc(),
                    )
                )
                updated += 1

            self._update_pool_counters(session, pool_id)
            session.commit()
            return {
                "pool_id": pool_id,
                "scanned": len(rows),
                "updated": updated,
                "changed_categories": changed_categories,
                "changed_coverages": changed_coverages,
                "pool": self.get_pool(pool_id=pool_id),
            }
        finally:
            session.close()

    def list_pool_items(
        self,
        *,
        pool_id: str,
        coverage_type: Optional[str] = None,
        match_status: Optional[str] = None,
        include_in_batch_1: Optional[bool] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SamplePoolListResult:
        session = _session()
        try:
            clauses = [self._item_table.c.pool_id == pool_id]
            if coverage_type:
                clauses.append(self._item_table.c.coverage_type == coverage_type)
            if match_status:
                clauses.append(self._item_table.c.match_status == match_status)
            if include_in_batch_1 is not None:
                clauses.append(self._item_table.c.include_in_batch_1.is_(include_in_batch_1))
            if query:
                keyword = f"%{query.strip()}%"
                clauses.append(
                    or_(
                        self._item_table.c.patient_name.ilike(keyword),
                        self._item_table.c.mr_no.ilike(keyword),
                        self._item_table.c.raw_payload_json.ilike(f'%\"visit_id\": \"%{query.strip()}%'),
                        self._item_table.c.manual_issue_text.ilike(keyword),
                    )
                )
            where_clause = and_(*clauses)
            total_stmt = select(func.count()).select_from(self._item_table).where(where_clause)
            total = int(session.execute(total_stmt).scalar() or 0)
            stmt = (
                select(self._item_table)
                .where(where_clause)
                .order_by(self._item_table.c.row_no.asc())
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
            )
            rows = session.execute(stmt).mappings().all()
            return SamplePoolListResult(
                items=[self._row_to_item(dict(row)) for row in rows],
                total=total,
                page=page,
                page_size=page_size,
            )
        finally:
            session.close()

    def list_pool_records(
        self,
        *,
        pool_id: str,
        coverage_type: Optional[str] = None,
        match_status: Optional[str] = None,
        include_in_batch_1: Optional[bool] = None,
        query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SamplePoolListResult:
        session = _session()
        try:
            clauses = [self._item_table.c.pool_id == pool_id]
            if coverage_type:
                clauses.append(self._item_table.c.coverage_type == coverage_type)
            if match_status:
                clauses.append(self._item_table.c.match_status == match_status)
            if include_in_batch_1 is not None:
                clauses.append(self._item_table.c.include_in_batch_1.is_(include_in_batch_1))
            if query:
                keyword = f"%{query.strip()}%"
                clauses.append(
                    or_(
                        self._item_table.c.patient_name.ilike(keyword),
                        self._item_table.c.mr_no.ilike(keyword),
                        self._item_table.c.matched_visit_id.ilike(keyword),
                        self._item_table.c.manual_issue_text.ilike(keyword),
                    )
                )
            where_clause = and_(*clauses)
            stmt = select(self._item_table).where(where_clause).order_by(self._item_table.c.row_no.asc())
            rows = session.execute(stmt).mappings().all()
            items = [self._row_to_item(dict(row)) for row in rows]
            items = self._apply_dynamic_candidate_rule_ids(items=items)
            source_table_map = self._load_bundle_source_table_map(
                visit_ids=[
                    str(item.get("matched_visit_id") or "").strip()
                    for item in items
                    if str(item.get("matched_visit_id") or "").strip()
                ]
            )

            grouped: Dict[str, Dict[str, Any]] = {}
            for item in items:
                group_key = item["matched_visit_id"] or f"id:{item['visit_id'] or item['mr_no'] or item['id']}"
                current = grouped.get(group_key)
                if current is None:
                    current = {
                        "id": group_key,
                        "matched_institute_id": item["matched_institute_id"],
                        "matched_patient_id": item["matched_patient_id"],
                        "matched_visit_id": item["matched_visit_id"],
                        "patient_name": item["patient_name"],
                        "mr_no": item["mr_no"],
                        "department": item["department"],
                        "match_status": item["match_status"],
                        "sync_status": item["sync_status"],
                        "bundle_status": item["bundle_status"],
                        "coverage_types": [],
                        "candidate_rule_ids": [],
                        "document_scope_labels": [],
                        "issue_count": 0,
                        "issue_preview": [],
                        "sample_item_ids": [],
                        "sample_items": [],
                    }
                    grouped[group_key] = current

                current["issue_count"] += 1
                current["sample_item_ids"].append(item["id"])
                current["sample_items"].append(item)
                if item["manual_issue_text"] and item["manual_issue_text"] not in current["issue_preview"]:
                    current["issue_preview"].append(item["manual_issue_text"])
                if item["coverage_type"] and item["coverage_type"] not in current["coverage_types"]:
                    current["coverage_types"].append(item["coverage_type"])
                for rule_id in item.get("candidate_rule_ids") or []:
                    if rule_id not in current["candidate_rule_ids"]:
                        current["candidate_rule_ids"].append(rule_id)
                visit_id = str(item.get("matched_visit_id") or "").strip()
                if visit_id:
                    for label in _derive_document_scope_labels_from_source_tables(
                        sorted(source_table_map.get(visit_id, set()))
                    ):
                        if label not in current["document_scope_labels"]:
                            current["document_scope_labels"].append(label)

            matched_visit_ids = [
                str(item.get("matched_visit_id") or "").strip()
                for item in grouped.values()
                if str(item.get("matched_visit_id") or "").strip()
            ]
            record_display_map = self._load_record_display_map(session=session, visit_ids=matched_visit_ids)
            for row in grouped.values():
                visit_id = str(row.get("matched_visit_id") or "").strip()
                if not visit_id:
                    continue
                display = record_display_map.get(visit_id) or {}
                if not _safe_text(row.get("patient_name")):
                    row["patient_name"] = _safe_text(display.get("patient_name"))
                if not _safe_text(row.get("department")):
                    row["department"] = _safe_text(display.get("department"))
                if not _safe_text(row.get("mr_no")):
                    row["mr_no"] = _safe_text(display.get("mr_no"))

            grouped_rows = sorted(
                grouped.values(),
                key=lambda item: (
                    0 if item.get("matched_visit_id") else 1,
                    str(item.get("mr_no") or ""),
                    str(item.get("patient_name") or ""),
                ),
            )
            total = len(grouped_rows)
            start = max(page - 1, 0) * page_size
            paged_rows = grouped_rows[start : start + page_size]
            for row in paged_rows:
                row["issue_preview_text"] = "；".join(row["issue_preview"][:2]) or "-"
            return SamplePoolListResult(
                items=paged_rows,
                total=total,
                page=page,
                page_size=page_size,
            )
        finally:
            session.close()

    def _load_record_display_map(self, *, session: Session, visit_ids: Sequence[str]) -> Dict[str, Dict[str, str]]:
        normalized_ids = [str(item).strip() for item in visit_ids if str(item).strip()]
        if not normalized_ids:
            return {}
        rows = (
            session.query(
                MedicalRecordFrontpage.visit_id,
                MedicalRecordFrontpage.name,
                MedicalRecordFrontpage.mr_no,
                MedicalRecordFrontpage.inpat_no,
                MedicalRecordFrontpage.admission_dept_name,
                MedicalRecordFrontpage.discharge_dept_name,
            )
            .filter(MedicalRecordFrontpage.visit_id.in_(normalized_ids))
            .all()
        )
        display_map: Dict[str, Dict[str, str]] = {}
        for row in rows:
            visit_id = _safe_text(getattr(row, "visit_id", ""))
            if not visit_id:
                continue
            display_map[visit_id] = {
                "patient_name": _safe_text(getattr(row, "name", "")),
                "mr_no": _safe_text(getattr(row, "mr_no", "") or getattr(row, "inpat_no", "")),
                "department": _safe_text(
                    getattr(row, "admission_dept_name", "") or getattr(row, "discharge_dept_name", "")
                ),
            }
        return display_map

    def _check_running_bundle_status(self, *, institute_id: str, patient_id: str, visit_id: str) -> str:
        if engine is None:
            return "pending"
        sql = sa.text(
            """
            SELECT 1
            FROM public.running_record_bundle
            WHERE institute_id = :institute_id
              AND patient_id = :patient_id
              AND visit_id = :visit_id
            LIMIT 1
            """
        )
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    sql,
                    {
                        "institute_id": institute_id,
                        "patient_id": patient_id,
                        "visit_id": visit_id,
                    },
                ).first()
            return "ready" if row else "missing"
        except Exception:
            return "pending"

    def match_pool_items(self, *, pool_id: str) -> Dict[str, Any]:
        session = _session()
        try:
            stmt = (
                select(self._item_table)
                .where(self._item_table.c.pool_id == pool_id)
                .order_by(self._item_table.c.row_no.asc())
            )
            rows = session.execute(stmt).mappings().all()
            matched = 0
            ambiguous = 0
            unmatched = 0
            for row in rows:
                raw_payload = _safe_json_loads(row.get("raw_payload_json"), {})
                visit_id_input = _safe_text(raw_payload.get("visit_id") if isinstance(raw_payload, dict) else "")
                mr_no_input = _safe_text(raw_payload.get("mr_no") if isinstance(raw_payload, dict) else "")
                patient_name = _safe_text(raw_payload.get("patient_name") if isinstance(raw_payload, dict) else "")
                department = _safe_text(raw_payload.get("department") if isinstance(raw_payload, dict) else "")
                qc_date_value = _parse_date(raw_payload.get("qc_date") if isinstance(raw_payload, dict) else None)
                match_status = "unmatched"
                institute_id = ""
                patient_id = ""
                visit_id = ""
                sync_status = "missing"
                bundle_status = "pending"
                candidate = None
                if visit_id_input:
                    visit_candidates = (
                        session.query(MedicalRecordFrontpage)
                        .filter(MedicalRecordFrontpage.visit_id == visit_id_input)
                        .all()
                    )
                    candidate = _pick_best_local_candidate(
                        candidates=visit_candidates,
                        patient_name=patient_name,
                        department=department,
                        qc_date_value=qc_date_value,
                    )
                    if candidate is not None:
                        match_status = "matched"
                    elif visit_candidates:
                        match_status = "ambiguous"

                if candidate is None and match_status == "unmatched" and mr_no_input:
                    mr_no_candidates = (
                        session.query(MedicalRecordFrontpage)
                        .filter(MedicalRecordFrontpage.mr_no == mr_no_input)
                        .all()
                    )
                    candidate = _pick_best_local_candidate(
                        candidates=mr_no_candidates,
                        patient_name=patient_name,
                        department=department,
                        qc_date_value=qc_date_value,
                    )
                    if candidate is not None:
                        match_status = "matched"
                    elif mr_no_candidates:
                        match_status = "ambiguous"

                if candidate is not None:
                    institute_id = _safe_text(candidate.institute_id)
                    patient_id = _safe_text(candidate.patient_id)
                    visit_id = _safe_text(candidate.visit_id)
                    sync_status = "synced"
                    bundle_status = self._check_running_bundle_status(
                        institute_id=institute_id,
                        patient_id=patient_id,
                        visit_id=visit_id,
                    )
                if match_status == "matched":
                    matched += 1
                elif match_status == "ambiguous":
                    ambiguous += 1
                else:
                    unmatched += 1
                session.execute(
                    update(self._item_table)
                    .where(self._item_table.c.id == row["id"])
                    .values(
                        matched_institute_id=institute_id,
                        matched_patient_id=patient_id,
                        matched_visit_id=visit_id,
                        match_status=match_status,
                        sync_status=sync_status,
                        bundle_status=bundle_status,
                        updated_at=_now_utc(),
                    )
                )
            self._update_pool_counters(session, pool_id)
            session.commit()
            return {
                "pool_id": pool_id,
                "matched": matched,
                "ambiguous": ambiguous,
                "unmatched": unmatched,
                "pool": self.get_pool(pool_id=pool_id),
            }
        finally:
            session.close()

    def get_runnable_items(
        self,
        *,
        pool_id: str,
        validation_mode: str,
        item_ids: Optional[Sequence[str]] = None,
        record_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        session = _session()
        try:
            normalized_mode = _safe_text(validation_mode).lower() or "customer"
            clauses = [
                self._item_table.c.pool_id == pool_id,
                self._item_table.c.match_status == "matched",
                self._item_table.c.sync_status == "synced",
            ]
            if normalized_mode == "customer":
                clauses.append(self._item_table.c.bundle_status == "ready")
            elif normalized_mode == "sc":
                clauses.extend(
                    [
                        self._item_table.c.coverage_type == "llm_intrinsic",
                        self._item_table.c.include_in_batch_1.is_(True),
                        self._item_table.c.bundle_status == "ready",
                    ]
                )
            elif normalized_mode == "programmatic":
                clauses.extend(
                    [
                        self._item_table.c.coverage_type == "programmatic",
                        self._item_table.c.matched_visit_id.is_not(None),
                    ]
                )
            elif normalized_mode == "formal_fast_screen_full":
                clauses.extend(
                    [
                        self._item_table.c.matched_visit_id.is_not(None),
                        self._item_table.c.matched_visit_id != "",
                    ]
                )
            else:
                raise ValueError(f"未知验证模式: {validation_mode}")
            stmt = (
                select(self._item_table)
                .where(and_(*clauses))
                .order_by(self._item_table.c.row_no.asc())
            )
            if item_ids:
                normalized_ids = [str(item_id).strip() for item_id in item_ids if str(item_id).strip()]
                if normalized_ids:
                    stmt = stmt.where(self._item_table.c.id.in_(normalized_ids))
            if record_ids:
                normalized_record_ids = [str(record_id).strip() for record_id in record_ids if str(record_id).strip()]
                if normalized_record_ids:
                    stmt = stmt.where(self._item_table.c.matched_visit_id.in_(normalized_record_ids))
            rows = session.execute(stmt).mappings().all()
            items = [self._row_to_item(dict(row)) for row in rows]
            if normalized_mode == "sc":
                items = self._apply_dynamic_candidate_rule_ids(items=items)
                return _apply_sample_sc_rule_whitelist(items)
            return self._apply_dynamic_candidate_rule_ids(items=items)
        finally:
            session.close()

    def _list_sync_candidate_items(
        self,
        *,
        pool_id: str,
        only_intrinsic: bool = True,
        include_in_batch_1: bool = True,
    ) -> List[Dict[str, Any]]:
        session = _session()
        try:
            clauses = [self._item_table.c.pool_id == pool_id]
            if only_intrinsic:
                clauses.append(self._item_table.c.coverage_type == "llm_intrinsic")
            if include_in_batch_1:
                clauses.append(self._item_table.c.include_in_batch_1.is_(True))
            stmt = select(self._item_table).where(and_(*clauses)).order_by(self._item_table.c.row_no.asc())
            rows = session.execute(stmt).mappings().all()
            return [self._row_to_item(dict(row)) for row in rows]
        finally:
            session.close()

    def _resolve_remote_visit_keys(self, *, items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        remote_url = get_remote_db_url()
        if not remote_url:
            raise RuntimeError("远端 PG 未配置，无法执行样本定向同步")
        cfg = load_db_config()
        remote_schema = str(cfg.get("remote_schema") or "public").strip() or "public"
        schema_ident = re.sub(r"[^A-Za-z0-9_]", "", remote_schema)
        if not schema_ident:
            raise ValueError("远端 schema 非法")

        visit_ids = sorted(
            {str(item.get("visit_id") or "").strip() for item in items if str(item.get("visit_id") or "").strip()}
        )
        mr_nos = sorted(
            {str(item.get("mr_no") or "").strip() for item in items if str(item.get("mr_no") or "").strip()}
        )
        if not visit_ids and not mr_nos:
            return {
                "matched": 0,
                "ambiguous": 0,
                "unmatched": 0,
                "visit_keys": [],
            }

        visit_lookup_map: Dict[str, List[Dict[str, Any]]] = {}
        mr_no_lookup_map: Dict[str, List[Dict[str, Any]]] = {}
        conn = psycopg2.connect(remote_url, connect_timeout=10)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            admission_expr = "NULL AS admission_datetime"
            discharge_expr = "NULL AS discharge_datetime"
            update_expr = "NULL AS update_time"
            if _remote_column_exists(cursor, schema_ident, "mr", "admission_datetime"):
                admission_expr = "admission_datetime AS admission_datetime"
            elif _remote_column_exists(cursor, schema_ident, "mr", "admission_time"):
                admission_expr = "admission_time AS admission_datetime"

            if _remote_column_exists(cursor, schema_ident, "mr", "discharge_datetime"):
                discharge_expr = "discharge_datetime AS discharge_datetime"
            elif _remote_column_exists(cursor, schema_ident, "mr", "discharge_time"):
                discharge_expr = "discharge_time AS discharge_datetime"

            if _remote_column_exists(cursor, schema_ident, "mr", "update_time"):
                update_expr = "update_time AS update_time"
            elif _remote_column_exists(cursor, schema_ident, "mr", "last_modified_time"):
                update_expr = "last_modified_time AS update_time"
            elif _remote_column_exists(cursor, schema_ident, "mr", "mr_time"):
                update_expr = "mr_time AS update_time"

            chunk_size = 200

            def _fetch_lookup_rows(field_name: str, values: Sequence[str], target_map: Dict[str, List[Dict[str, Any]]]) -> None:
                for start in range(0, len(values), chunk_size):
                    chunk = values[start : start + chunk_size]
                    if not chunk:
                        continue
                    placeholders = ", ".join(["%s"] * len(chunk))
                    sql = f"""
                        SELECT
                            institute_id::text AS institute_id,
                            patient_id::text AS patient_id,
                            visit_id::text AS visit_id,
                            COALESCE(inpat_no::text, '') AS inpat_no,
                            COALESCE(mr_no::text, '') AS mr_no,
                            COALESCE(name::text, '') AS name,
                            COALESCE(admission_dept_name::text, '') AS admission_dept_name,
                            COALESCE(discharge_dept_name::text, '') AS discharge_dept_name,
                            {admission_expr},
                            {discharge_expr},
                            {update_expr}
                        FROM {schema_ident}.mr
                        WHERE COALESCE({field_name}::text, '') IN ({placeholders})
                    """
                    cursor.execute(sql, chunk)
                    for row in cursor.fetchall() or []:
                        candidate = dict(row)
                        lookup_key = str(candidate.get(field_name) or "").strip()
                        if lookup_key:
                            target_map.setdefault(lookup_key, []).append(candidate)

            _fetch_lookup_rows("visit_id", visit_ids, visit_lookup_map)
            _fetch_lookup_rows("mr_no", mr_nos, mr_no_lookup_map)
        finally:
            cursor.close()
            conn.close()

        visit_key_set: set[tuple[str, str]] = set()
        matched = 0
        ambiguous = 0
        unmatched = 0
        for item in items:
            visit_id_input = str(item.get("visit_id") or "").strip()
            mr_no_input = str(item.get("mr_no") or "").strip()
            patient_name = str(item.get("patient_name") or "").strip()
            department = str(item.get("department") or "").strip()
            qc_date_value = _parse_date(item.get("qc_date"))
            visit_candidates = visit_lookup_map.get(visit_id_input, []) if visit_id_input else []
            chosen = _pick_best_remote_candidate(
                candidates=visit_candidates,
                patient_name=patient_name,
                department=department,
                qc_date_value=qc_date_value,
            )
            if chosen is None and visit_candidates:
                ambiguous += 1
                continue
            if chosen is None and mr_no_input:
                mr_no_candidates = mr_no_lookup_map.get(mr_no_input, [])
                chosen = _pick_best_remote_candidate(
                    candidates=mr_no_candidates,
                    patient_name=patient_name,
                    department=department,
                    qc_date_value=qc_date_value,
                )
                if chosen is None and mr_no_candidates:
                    ambiguous += 1
                    continue

            if chosen is None:
                unmatched += 1
                continue

            patient_id = _safe_text(chosen.get("patient_id"))
            visit_id = _safe_text(chosen.get("visit_id"))
            if not patient_id or not visit_id:
                unmatched += 1
                continue
            matched += 1
            visit_key_set.add((patient_id, visit_id))

        return {
            "matched": matched,
            "ambiguous": ambiguous,
            "unmatched": unmatched,
            "visit_keys": sorted(visit_key_set),
        }

    def sync_pool_records(
        self,
        *,
        pool_id: str,
        only_intrinsic: bool = True,
        include_in_batch_1: bool = True,
        table_groups: Optional[Sequence[str]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        items = self._list_sync_candidate_items(
            pool_id=pool_id,
            only_intrinsic=only_intrinsic,
            include_in_batch_1=include_in_batch_1,
        )
        if not items:
            raise ValueError("当前样本池没有可同步的样本")

        sync_plan = self.resolve_sync_table_names(group_ids=table_groups)
        total_tables = len(sync_plan["table_names"])
        if progress_callback is not None:
            progress_callback(
                {
                    "step_key": "resolving",
                    "step_label": "正在解析样本病历",
                    "total_candidates": len(items),
                    "eligible_visits": 0,
                    "processed_tables": 0,
                    "total_tables": total_tables,
                    "current_table": "",
                    "remaining_tables": total_tables,
                }
            )
        resolved = self._resolve_remote_visit_keys(items=items)
        visit_keys: List[tuple[str, str]] = resolved["visit_keys"]
        if progress_callback is not None:
            progress_callback(
                {
                    "step_key": "resolved",
                    "step_label": "病历解析完成",
                    "total_candidates": len(items),
                    "eligible_visits": len(visit_keys),
                    "processed_tables": 0,
                    "total_tables": total_tables,
                    "current_table": "",
                    "remaining_tables": total_tables,
                    "matched": resolved["matched"],
                    "ambiguous": resolved["ambiguous"],
                    "unmatched": resolved["unmatched"],
                }
            )
        if not visit_keys:
            return {
                "pool_id": pool_id,
                "matched": resolved["matched"],
                "ambiguous": resolved["ambiguous"],
                "unmatched": resolved["unmatched"],
                "eligible_visits": 0,
                "synced_tables": [],
                "total_rows_pulled": 0,
                "total_rows_upserted": 0,
                "sync_group_ids": sync_plan["group_ids"],
                "missing_group_ids": sync_plan["missing_group_ids"],
                "pool": self.get_pool(pool_id=pool_id),
            }

        table_map = {str(item.get("name") or "").strip(): item for item in list_sync_tables()}
        remote_url = get_remote_db_url()
        cfg = load_db_config()
        remote_schema = str(cfg.get("remote_schema") or "public").strip() or "public"
        anchor_tables = {"mr", "admission_record"}
        results: List[Dict[str, Any]] = []
        skipped_table_errors: List[Dict[str, Any]] = []
        total_rows_pulled = 0
        total_rows_upserted = 0
        bundle_refresh_rows: List[Dict[str, Any]] = []

        for index, table_name in enumerate(sync_plan["table_names"], start=1):
            if progress_callback is not None:
                progress_callback(
                    {
                        "step_key": "syncing",
                        "step_label": "正在同步病历表",
                        "total_candidates": len(items),
                        "eligible_visits": len(visit_keys),
                        "processed_tables": index - 1,
                        "total_tables": total_tables,
                        "current_table": table_name,
                        "remaining_tables": max(total_tables - index + 1, 0),
                        "total_rows_pulled": total_rows_pulled,
                        "total_rows_upserted": total_rows_upserted,
                    }
                )
            table_config = table_map.get(table_name)
            if not table_config:
                continue
            source_table = str(table_config.get("source_table") or table_name)
            try:
                rows = fetch_remote_rows_by_visit_keys(
                    remote_url=remote_url,
                    remote_schema=remote_schema,
                    source_table=source_table,
                    visit_keys=visit_keys,
                )
            except Exception as exc:
                error_message = _safe_text(str(exc))
                if table_name in anchor_tables:
                    raise
                if not _is_remote_source_unavailable_error(exc):
                    raise
                skipped = {
                    "table_name": table_name,
                    "source_table": source_table,
                    "rows_pulled": 0,
                    "rows_upserted": 0,
                    "sync_status": "source_table_unavailable",
                    "skip_reason": error_message,
                }
                results.append(skipped)
                skipped_table_errors.append(skipped)
                if progress_callback is not None:
                    progress_callback(
                        {
                            "step_key": "syncing",
                            "step_label": "正在同步病历表",
                            "total_candidates": len(items),
                            "eligible_visits": len(visit_keys),
                            "processed_tables": index,
                            "total_tables": total_tables,
                            "current_table": table_name,
                            "remaining_tables": max(total_tables - index, 0),
                            "total_rows_pulled": total_rows_pulled,
                            "total_rows_upserted": total_rows_upserted,
                            "skipped_optional_tables": len(skipped_table_errors),
                        }
                    )
                continue
            upserted = upsert_to_local(
                table_name=table_name,
                records=rows,
                primary_keys=[str(key) for key in (table_config.get("key_fields") or []) if str(key).strip()],
            )
            for row in rows:
                institute_id = _safe_text(row.get("institute_id"))
                patient_id = _safe_text(row.get("patient_id"))
                visit_id = _safe_text(row.get("visit_id"))
                if institute_id and patient_id and visit_id:
                    bundle_refresh_rows.append(
                        {
                            "institute_id": institute_id,
                            "patient_id": patient_id,
                            "visit_id": visit_id,
                        }
                    )
            total_rows_pulled += len(rows)
            total_rows_upserted += upserted

            if table_name in anchor_tables and rows:
                ingest_sync_rows(
                    table_name=table_name,
                    rows=rows,
                    policy_version="sample_pool_sync",
                    sync_scene="running",
                    allow_frontpage_only=False,
                    latest_mirror_success_time=datetime.now(),
                    mirror_delay_base_minutes=30,
                    sync_interval_minutes=30,
                )
                refresh_scene_bundles_for_rows(
                    scene="running",
                    rows=rows,
                    policy_version="sample_pool_sync",
                )
                refresh_scene_bundles_for_rows(
                    scene="final",
                    rows=rows,
                    policy_version="sample_pool_sync",
                )

            results.append(
                {
                    "table_name": table_name,
                    "source_table": source_table,
                    "rows_pulled": len(rows),
                    "rows_upserted": upserted,
                    "sync_status": "synced",
                    "skip_reason": "",
                }
            )
            if progress_callback is not None:
                progress_callback(
                    {
                        "step_key": "syncing",
                        "step_label": "正在同步病历表",
                        "total_candidates": len(items),
                        "eligible_visits": len(visit_keys),
                        "processed_tables": index,
                        "total_tables": total_tables,
                        "current_table": table_name,
                        "remaining_tables": max(total_tables - index, 0),
                        "total_rows_pulled": total_rows_pulled,
                        "total_rows_upserted": total_rows_upserted,
                    }
                )

        if bundle_refresh_rows:
            refresh_scene_bundles_for_rows(
                scene="running",
                rows=bundle_refresh_rows,
                policy_version="sample_pool_sync",
            )
            refresh_scene_bundles_for_rows(
                scene="final",
                rows=bundle_refresh_rows,
                policy_version="sample_pool_sync",
            )
            refresh_domain_bundles_for_rows(
                rows=bundle_refresh_rows,
                policy_version="sample_pool_sync",
            )

        if progress_callback is not None:
            progress_callback(
                {
                    "step_key": "matching",
                    "step_label": "正在回写匹配结果",
                    "total_candidates": len(items),
                    "eligible_visits": len(visit_keys),
                    "processed_tables": total_tables,
                    "total_tables": total_tables,
                    "current_table": "",
                    "remaining_tables": 0,
                    "total_rows_pulled": total_rows_pulled,
                    "total_rows_upserted": total_rows_upserted,
                }
            )
        match_result = self.match_pool_items(pool_id=pool_id)
        return {
            "pool_id": pool_id,
            "matched": resolved["matched"],
            "ambiguous": resolved["ambiguous"],
            "unmatched": resolved["unmatched"],
            "eligible_visits": len(visit_keys),
            "synced_tables": results,
            "total_rows_pulled": total_rows_pulled,
            "total_rows_upserted": total_rows_upserted,
            "sync_group_ids": sync_plan["group_ids"],
            "missing_group_ids": sync_plan["missing_group_ids"],
            "skipped_optional_tables": skipped_table_errors,
            "pool": match_result.get("pool") or self.get_pool(pool_id=pool_id),
            "post_match": match_result,
        }

    def update_pool_latest_job(self, *, pool_id: str, job_id: str, job_status: str = "queued") -> None:
        session = _session()
        try:
            session.execute(
                update(self._pool_table)
                .where(self._pool_table.c.id == pool_id)
                .values(
                    latest_job_id=_safe_text(job_id),
                    latest_job_status=_safe_text(job_status),
                    updated_at=_now_utc(),
                )
            )
            session.commit()
        finally:
            session.close()
