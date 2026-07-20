"""LX0609 受控只读来源证据：纯时间/摘要函数与显式有界查询。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping

from app.services.bundles import assembly as bundle_assembly


PERFORMED_TIME_FORMAT = "%Y-%m-%d %H:%M:%S+08"
SURGERY_TIME_FIELDS = (
    "surgery_begin_time",
    "surgery_begin_datetime",
    "surgery_end_time",
    "surgery_end_datetime",
)
CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY = "inpat_nondrug_order.unstable_order"
CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY = "inpat_nondrug_order.severity_order"
CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY = "inpat_registration.discharge_horizon"
EVALUATION_HORIZON_SOURCE_KEY = "evaluation_context.horizon"
_SEVERITY_ORDER_NEGATIVE_MARKERS = (
    "解除",
    "取消",
    "停止",
    "停病危",
    "停病重",
)
_EFFECTIVE_SEVERITY_ORDER_STATUSES = frozenset(("新开", "执行中", "停止"))
_EXCLUDED_SEVERITY_ORDER_STATUSES = frozenset(("取消", "撤销", "作废"))
_RESCUE_END_TIME_PATTERN = re.compile(
    r"(?:^|[\n\r；;])\s*抢救结束时间\s*[:：]\s*(?P<value>"
    r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?"
    r"|\d{4}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2}(?::\d{2})?"
    r")",
    flags=re.MULTILINE,
)

_NATIVE_SOURCE_FIELDS = {
    "inpat_registration": (
        "admission_datetime",
    ),
    "admission_record": (
        "document_id",
        "document_title",
        "record_time",
        "admission_datetime",
        "record_content",
    ),
    "first_course_record": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
    ),
    "rescue_record": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
    ),
    "mr_bloodtrans": (
        "transfuse_variety",
        "blood_transfusion_volume",
        "blood_transfusion_unit",
        "transblood_reaction_sign",
        "transfution_datetime",
    ),
    "bloodtrans_record": (
        "document_id",
        "document_title",
        "record_content",
        "record_time",
    ),
    "mr_surgery": (
        "surgery_code",
        "surgery_name",
        "surgical_level",
        "surgial_incision_level",
        "surgical_incision_level",
        "surgery_begin_datetime",
        "surgery_end_datetime",
    ),
    "presurg_discussion": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
        "host_name",
        "host_summary",
        "discuss_staff",
        "v2_schema",
    ),
    "consultation_record": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
        "v2_schema",
    ),
    "daily_course_record": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
    ),
    "senior_course_record": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
    ),
    "exam_master": (
        "exam_id",
        "exam_type",
        "exam_name",
        "exam_item_name",
        "item_name",
        "exam_time",
        "exam_datetime",
        "report_time",
        "report_datetime",
        "record_content",
    ),
    "exam_item_report": (
        "document_id",
        "exam_id",
        "item_code",
        "item_name",
        "exam_name",
        "exam_item_name",
        "exam_type",
        "report_time",
        "exam_result",
        "exam_impression",
        "exam_conclusion",
        "impression",
        "conclusion",
        "record_content",
    ),
    "labtest_master": (
        "test_id",
        "labtest_subject",
        "lab_type",
        "test_type",
        "specimen",
        "request_datetime",
        "report_datetime",
        "labtest_result_status",
        "record_content",
    ),
    "labtest_item_report": (
        "document_id",
        "test_id",
        "item_code",
        "item_name",
        "lab_item_name",
        "lab_type",
        "test_type",
        "result",
        "abnormal_indicator",
        "report_time",
        "record_content",
    ),
    "pathology_exam_master": (
        "pathology_exam_id",
        "pathology_id",
        "specimen_name",
        "surgery_name",
        "request_datetime",
        "record_content",
    ),
    "pathology_exam_report": (
        "pathology_exam_id",
        "pathology_id",
        "specimen_name",
        "diagnosis",
        "eye_findings",
        "microscope_findings",
        "report_datetime",
        "report_status",
        "record_content",
    ),
    "diagnosis": (
        "diagnosis_code",
        "diagnosis_name",
        "diagnosis_type",
        "diagnosis_source",
        "diagnosis_datetime",
    ),
    "inpat_drug_order": (
        "order_id",
        "drug_code",
        "generic_name",
        "brand_name",
        "drug_type",
        "single_dose",
        "single_dose_unit",
        "drug_apply_method",
        "drug_frequency",
        "prescribed_datetime",
        "order_status",
        "record_content",
    ),
    "discharge_record": (
        "document_id",
        "document_title",
        "record_time",
        "discharge_date",
        "discharge_time",
        "discharge_order",
        "treatment_course",
        "record_content",
    ),
    "surgery_record": (
        "document_id",
        "document_title",
        "record_time",
        "surgery_begin_time",
        "surgery_end_time",
        "surgery_name",
        "surgery_code",
        "surgery_process",
        "record_content",
    ),
    "surgery_inform_consent": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
        "patient_sign",
        "surgeon_sign",
        "planned_operation_name",
        "planned_operation_code",
    ),
    "consent_form": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
        "patient_sign",
        "surgeon_sign",
        "planned_operation_name",
        "planned_operation_code",
    ),
}

_SNAPSHOT_SOURCE_FIELDS = {
    source_key: _NATIVE_SOURCE_FIELDS[source_key]
    for source_key in (
        "inpat_registration",
        "admission_record",
        "first_course_record",
        "rescue_record",
        "mr_bloodtrans",
        "bloodtrans_record",
        "mr_surgery",
        "presurg_discussion",
        "consultation_record",
        "daily_course_record",
        "senior_course_record",
        "exam_master",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "pathology_exam_master",
        "pathology_exam_report",
        "diagnosis",
        "inpat_drug_order",
        "discharge_record",
        "surgery_record",
        "surgery_inform_consent",
        "consent_form",
    )
}
_SNAPSHOT_SOURCE_FIELDS[CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY] = ("present",)
_SNAPSHOT_SOURCE_FIELDS[CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY] = (
    "severity",
    "status_state",
    "prescribed_datetime",
    "row_ref",
)
_SNAPSHOT_SOURCE_FIELDS[CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY] = (
    "discharge_datetime",
    "row_ref",
)
_SNAPSHOT_SOURCE_FIELDS[EVALUATION_HORIZON_SOURCE_KEY] = (
    "horizon_date",
    "basis",
    "row_ref",
)
_SNAPSHOT_SOURCE_FIELDS["inpat_nondrug_order"] = (
    "order_id",
    "update_time",
    "order_status",
)
_SNAPSHOT_SOURCE_FIELDS["surgery_application"] = (
    "order_id",
    "update_time",
    "surgery_code",
)
_SNAPSHOT_SOURCE_FIELDS["surgery_record"] = tuple(
    dict.fromkeys(
        (*_SNAPSHOT_SOURCE_FIELDS["surgery_record"], *SURGERY_TIME_FIELDS)
    )
)
_SNAPSHOT_SOURCE_FIELDS.update({
    "presurg_summary": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
    ),
    "surgery_safecheck_record": (
        "document_id",
        "document_title",
        "record_time",
        "record_content",
    ),
})


class SourceEvidenceUnavailable(Exception):
    """受控来源或就诊绑定字段不可用。"""


class SourceEvidenceQueryError(Exception):
    """数据库连接或查询执行失败；不携带底层异常原文。"""


class SourceEvidenceTruncated(Exception):
    """受控来源超过读取上限，不能据截断结果作否定判断。"""


def parse_luxian_0609_rescue_end_time(value: Any) -> datetime | None:
    """只解析完整“抢救结束时间”标签值，不从任意正文猜测时间。"""

    match = _RESCUE_END_TIME_PATTERN.search(str(value or ""))
    if not match:
        return None
    normalized = (
        match.group("value")
        .strip()
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
    )
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


@dataclass(frozen=True)
class SnapshotSourceRows:
    """provider 内部读取结果；raw rows 不得进入客户或 safe summary。"""

    source_key: str
    rows: tuple[Mapping[str, Any], ...]
    truncated: bool
    limit_rows: int

    @classmethod
    def create(
        cls,
        *,
        source_key: str,
        rows: Any,
        truncated: bool,
        limit_rows: int,
    ) -> SnapshotSourceRows:
        normalized_source = str(source_key or "").strip().lower()
        if normalized_source not in _SNAPSHOT_SOURCE_FIELDS:
            raise SourceEvidenceUnavailable()
        if isinstance(limit_rows, bool) or not isinstance(limit_rows, int) or limit_rows < 1:
            raise ValueError("limit_rows must be a positive int")
        if not isinstance(truncated, bool):
            raise TypeError("truncated must be bool")
        raw_rows = tuple(rows)
        if len(raw_rows) > limit_rows:
            raise ValueError("snapshot rows exceed declared limit")
        if truncated and not raw_rows:
            raise ValueError("truncated snapshot rows cannot be empty")
        if not all(isinstance(row, Mapping) for row in raw_rows):
            raise TypeError("snapshot rows must contain mappings")
        frozen_rows = tuple(MappingProxyType(dict(row)) for row in raw_rows)
        return cls(
            source_key=normalized_source,
            rows=frozen_rows,
            truncated=truncated,
            limit_rows=limit_rows,
        )


def canonical_source_evidence(value: Any) -> str:
    """纯规范化：仅供稳定排序和不可逆摘要使用。"""
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), default=str)


def digest_source_evidence(value: Any) -> str:
    """纯不可逆摘要；调用方不得把输入原值写入输出。"""
    return hashlib.sha256(canonical_source_evidence(value).encode("utf-8")).hexdigest()


def build_luxian_0609_course_round_timeline_from_rows(
    rows_by_source: Mapping[str, tuple[Mapping[str, Any], ...]],
) -> dict[str, list[dict[str, Any]]]:
    """把共享材料转换为005/006既有安全时间线，不读取数据库。"""

    result: dict[str, list[dict[str, Any]]] = {}
    for source_key in ("daily_course_record", "senior_course_record"):
        rows = rows_by_source.get(source_key)
        if rows is None:
            raise SourceEvidenceUnavailable()
        safe_rows: list[dict[str, Any]] = []
        for row in rows:
            title = str(row.get("document_title") or "").strip()
            record_time = row.get("record_time")
            document_id = row.get("document_id") or row.get("id")
            safe_rows.append(
                {
                    "document_id": digest_source_evidence(
                        (source_key, document_id, record_time, title)
                    ),
                    "title": title,
                    "authored_at": record_time,
                    "source_table": source_key,
                }
            )
        result[source_key] = safe_rows
    return result


def read_luxian_0609_course_round_timeline(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> dict[str, list[dict[str, Any]]]:
    """读取005/006所需的权威标题与时间；不读取或返回病程正文。"""

    coordinates = (institute_id, patient_id, visit_id)
    if not all(isinstance(value, str) and value.strip() for value in coordinates):
        raise SourceEvidenceUnavailable()
    trusted_schema = bundle_assembly._default_source_schema()
    if source_schema not in (None, trusted_schema):
        raise SourceEvidenceUnavailable()
    engine = bundle_assembly.engine
    if engine is None:
        raise SourceEvidenceUnavailable()

    raw_rows_by_source: dict[str, tuple[Mapping[str, Any], ...]] = {}
    for source_key in ("daily_course_record", "senior_course_record"):
        columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
        required = {
            "institute_id",
            "patient_id",
            "visit_id",
            "document_title",
            "record_time",
        }
        if not required.issubset(columns):
            raise SourceEvidenceUnavailable()
        document_id_field = next(
            (field for field in ("document_id", "id") if field in columns),
            None,
        )
        selected = ["document_title", "record_time"]
        if document_id_field:
            selected.append(document_id_field)
        select_sql = ", ".join(
            bundle_assembly._quote_ident(field) for field in selected
        )
        order_fields = ["record_time"]
        if document_id_field:
            order_fields.append(document_id_field)
        order_sql = ", ".join(
            f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST"
            for field in order_fields
        )
        limit = _source_limit(source_key)
        sql = (
            f"SELECT {select_sql} "
            f"FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
            f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
            f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
            f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
            f"ORDER BY {order_sql} LIMIT :limit_rows"
        )
        with engine.connect() as connection:
            rows = connection.execute(
                bundle_assembly.text(sql),
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "limit_rows": limit + 1,
                },
            ).mappings().all()
        if len(rows) > limit:
            raise SourceEvidenceTruncated()
        raw_rows_by_source[source_key] = tuple(dict(row) for row in rows)
    return build_luxian_0609_course_round_timeline_from_rows(raw_rows_by_source)


def parse_strict_performed_time(value: Any) -> datetime | None:
    """仅接受整值、trim 后可 round-trip 的已验收 +08 手术时间。"""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    try:
        parsed = datetime.strptime(candidate, PERFORMED_TIME_FORMAT)
    except ValueError:
        return None
    return parsed if parsed.strftime(PERFORMED_TIME_FORMAT) == candidate else None


def has_strict_performed_time(row: Mapping[str, Any]) -> bool:
    """纯事实判定：任一批准字段具有整值已实施时间即可。"""
    return any(parse_strict_performed_time(row.get(field)) is not None for field in SURGERY_TIME_FIELDS)


def trusted_performed_surgery_times(
    *, source_key: str, row: Mapping[str, Any]
) -> tuple[datetime, ...]:
    """返回批准来源中的本次已实施手术时间；描述性字段不能触发。"""
    if source_key == "surgery_record":
        return tuple(
            parsed
            for field in SURGERY_TIME_FIELDS
            if (parsed := parse_strict_performed_time(row.get(field))) is not None
        )
    if source_key == "mr_surgery":
        return tuple(
            value
            for field in ("surgery_begin_datetime", "surgery_end_datetime")
            if isinstance((value := row.get(field)), datetime) and value.tzinfo is None
        )
    return ()


def has_trusted_performed_surgery(*, source_key: str, row: Mapping[str, Any]) -> bool:
    """仅严格手术记录时间或 mr_surgery typed 时间可证明已实施。"""
    return bool(trusted_performed_surgery_times(source_key=source_key, row=row))


def _source_limit(source_key: str) -> int:
    return int(getattr(bundle_assembly, "_DOMAIN_FETCH_LIMITS", {}).get(source_key, 50))


def luxian_0609_native_source_row_limit(source_key: str) -> int:
    """返回批准来源的有界读取上限；达到上限时调用方必须视为可能截断。"""

    if str(source_key or "").strip() not in _NATIVE_SOURCE_FIELDS:
        raise SourceEvidenceUnavailable()
    return _source_limit(source_key)


def has_luxian_0609_current_visit_unstable_order(
    *, institute_id: str, patient_id: str, visit_id: str, source_schema: str | None
) -> bool:
    """判断本次就诊是否下达过病危或病重医嘱，不返回医嘱原文。"""

    trusted_schema = bundle_assembly._default_source_schema()
    if source_schema not in (None, trusted_schema):
        raise SourceEvidenceUnavailable()
    engine = bundle_assembly.engine
    if engine is None:
        raise SourceEvidenceUnavailable()
    source_key = "inpat_nondrug_order"
    try:
        columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
    except Exception:
        raise SourceEvidenceQueryError() from None
    required = {"institute_id", "patient_id", "visit_id", "order_name"}
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()

    sql = (
        f"SELECT 1 FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"AND ({bundle_assembly._quote_ident('order_name')} LIKE :critical_name "
        f"OR {bundle_assembly._quote_ident('order_name')} LIKE :serious_name) LIMIT 1"
    )
    try:
        with engine.connect() as connection:
            row = connection.execute(
                bundle_assembly.text(sql),
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "critical_name": "%病危%",
                    "serious_name": "%病重%",
                },
            ).first()
    except Exception:
        raise SourceEvidenceQueryError() from None
    return row is not None


def read_luxian_0609_severity_order_rows(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> SnapshotSourceRows:
    """只读取病重/病危医嘱类别与权威开立时间，不返回医嘱原文。"""

    trusted_schema = bundle_assembly._default_source_schema()
    if source_schema not in (None, trusted_schema):
        raise SourceEvidenceUnavailable()
    engine = bundle_assembly.engine
    if engine is None:
        raise SourceEvidenceUnavailable()
    source_key = "inpat_nondrug_order"
    try:
        columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
    except Exception:
        raise SourceEvidenceQueryError() from None
    required = {
        "institute_id",
        "patient_id",
        "visit_id",
        "order_name",
        "order_status",
    }
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()
    selected = ["order_name"]
    selected.extend(
        field
        for field in ("order_id", "prescribed_datetime", "order_status")
        if field in columns
    )
    select_sql = ", ".join(bundle_assembly._quote_ident(field) for field in selected)
    order_columns = [
        field for field in ("prescribed_datetime", "order_id", "order_name") if field in columns
    ]
    order_sql = ", ".join(
        f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST"
        for field in order_columns
    )
    limit_rows = 50
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"AND ({bundle_assembly._quote_ident('order_name')} LIKE :critical_name "
        f"OR {bundle_assembly._quote_ident('order_name')} LIKE :serious_name) "
        f"AND {bundle_assembly._quote_ident('order_name')} NOT LIKE :relieve_name "
        f"AND {bundle_assembly._quote_ident('order_name')} NOT LIKE :cancel_name "
        f"AND {bundle_assembly._quote_ident('order_name')} NOT LIKE :stop_name "
        f"AND {bundle_assembly._quote_ident('order_name')} NOT LIKE :halt_critical_name "
        f"AND {bundle_assembly._quote_ident('order_name')} NOT LIKE :halt_serious_name "
        f"ORDER BY {order_sql} LIMIT :limit_rows"
    )
    try:
        with engine.connect() as connection:
            raw_rows = connection.execute(
                bundle_assembly.text(sql),
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "critical_name": "%病危%",
                    "serious_name": "%病重%",
                    "relieve_name": "%解除%",
                    "cancel_name": "%取消%",
                    "stop_name": "%停止%",
                    "halt_critical_name": "%停病危%",
                    "halt_serious_name": "%停病重%",
                    "limit_rows": limit_rows + 1,
                },
            ).mappings().all()
    except Exception:
        raise SourceEvidenceQueryError() from None
    safe_rows = []
    for row in raw_rows:
        order_name = str(row.get("order_name") or "")
        if any(marker in order_name for marker in _SEVERITY_ORDER_NEGATIVE_MARKERS):
            continue
        has_critical = "病危" in order_name
        has_serious = "病重" in order_name
        severity = (
            "critical"
            if has_critical and not has_serious
            else "serious" if has_serious and not has_critical else "unknown"
        )
        # 停止状态表示该次医嘱曾有效，不作为评价区间终点。初始取消、撤销、
        # 作废行不产生触发；空值及未审计状态则保守保留为 unresolved，交由
        # 008/009 映射为 data_gap，避免把未知状态伪装成无医嘱。
        order_status = row.get("order_status")
        normalized_status = (
            order_status.strip() if isinstance(order_status, str) else ""
        )
        if normalized_status in _EFFECTIVE_SEVERITY_ORDER_STATUSES:
            status_state = "effective"
        elif normalized_status in _EXCLUDED_SEVERITY_ORDER_STATUSES:
            status_state = "excluded"
        else:
            status_state = "unresolved"
        safe_rows.append(
            {
                "severity": severity,
                "status_state": status_state,
                "prescribed_datetime": row.get("prescribed_datetime"),
                "row_ref": digest_source_evidence(
                    (
                        CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
                        row.get("order_id"),
                        severity,
                        status_state,
                        order_status,
                        row.get("prescribed_datetime"),
                    )
                ),
            }
        )
    return SnapshotSourceRows.create(
        source_key=CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        rows=safe_rows[:limit_rows],
        truncated=len(safe_rows) > limit_rows,
        limit_rows=limit_rows,
    )


def read_luxian_0609_discharge_horizon_rows(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> SnapshotSourceRows:
    """只读取住院主索引的权威出院时间；不扩展既有登记投影。"""

    trusted_schema = bundle_assembly._default_source_schema()
    if source_schema not in (None, trusted_schema):
        raise SourceEvidenceUnavailable()
    engine = bundle_assembly.engine
    if engine is None:
        raise SourceEvidenceUnavailable()
    table_name = "inpat_registration"
    try:
        columns = set(bundle_assembly._get_table_columns(trusted_schema, table_name))
    except Exception:
        raise SourceEvidenceQueryError() from None
    required = {
        "institute_id",
        "patient_id",
        "visit_id",
        "discharge_datetime",
    }
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()
    sql = (
        f"SELECT {bundle_assembly._quote_ident('discharge_datetime')} "
        f"FROM {bundle_assembly._qualified_table(trusted_schema, table_name)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        "LIMIT :limit_rows"
    )
    try:
        with engine.connect() as connection:
            raw_rows = connection.execute(
                bundle_assembly.text(sql),
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "limit_rows": 2,
                },
            ).mappings().all()
    except Exception:
        raise SourceEvidenceQueryError() from None
    safe_rows = tuple(
        {
            "discharge_datetime": row.get("discharge_datetime"),
            "row_ref": digest_source_evidence(
                (
                    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
                    row.get("discharge_datetime"),
                )
            ),
        }
        for row in raw_rows[:1]
    )
    return SnapshotSourceRows.create(
        source_key=CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
        rows=safe_rows,
        truncated=len(raw_rows) > 1,
        limit_rows=1,
    )


def read_luxian_0609_runtime_source_rows(
    *, source_key: str, institute_id: str, patient_id: str, visit_id: str, source_schema: str | None
) -> list[dict[str, Any]]:
    """显式、有界、参数化的读侧查询；调用时才访问数据库。"""
    trusted_schema = bundle_assembly._default_source_schema()
    if source_schema not in (None, trusted_schema):
        raise SourceEvidenceUnavailable()
    engine = bundle_assembly.engine
    if engine is None:
        raise SourceEvidenceUnavailable()
    columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
    required = {"institute_id", "patient_id", "visit_id"}
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()

    selected = [field for field in SURGERY_TIME_FIELDS if source_key == "surgery_record" and field in columns]
    if source_key == "mr_surgery":
        if "surgery_begin_datetime" not in columns:
            raise SourceEvidenceUnavailable()
        selected.append("surgery_begin_datetime")
    if source_key == "presurg_summary":
        selected.extend(field for field in ("record_content", "record_time") if field in columns)
    if source_key == "surgery_safecheck_record":
        selected.extend(field for field in ("record_content",) if field in columns)
    select_sql = ", ".join(bundle_assembly._quote_ident(field) for field in selected) or "1 AS row_marker"

    order_candidates = (*getattr(bundle_assembly, "_ORDER_COLUMNS_PRIORITY", ()), "document_id", "id", *SURGERY_TIME_FIELDS)
    order_columns = [field for field in order_candidates if field in columns]
    order_sql = ""
    if order_columns:
        order_sql = " ORDER BY " + ", ".join(
            f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST" for field in order_columns
        )
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"{order_sql} LIMIT :limit_rows"
    )
    with engine.connect() as connection:
        rows = connection.execute(
            bundle_assembly.text(sql),
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "limit_rows": _source_limit(source_key),
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def read_luxian_0609_native_source_rows(
    *, source_key: str, institute_id: str, patient_id: str, visit_id: str, source_schema: str | None
) -> list[dict[str, Any]]:
    """读取原生质控批准字段；字段白名单固定，调用方不能扩大正文范围。"""
    approved_fields = _NATIVE_SOURCE_FIELDS.get(str(source_key or "").strip())
    if approved_fields is None:
        raise SourceEvidenceUnavailable()
    trusted_schema = bundle_assembly._default_source_schema()
    if source_schema not in (None, trusted_schema):
        raise SourceEvidenceUnavailable()
    engine = bundle_assembly.engine
    if engine is None:
        raise SourceEvidenceUnavailable()
    columns = set(bundle_assembly._get_table_columns(trusted_schema, source_key))
    required = {"institute_id", "patient_id", "visit_id"}
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()

    selected = [field for field in approved_fields if field in columns]
    if source_key == "mr_surgery" and not {"surgical_level", "surgery_begin_datetime"}.issubset(selected):
        raise SourceEvidenceUnavailable()
    if source_key == "mr_bloodtrans" and "transfution_datetime" not in selected:
        raise SourceEvidenceUnavailable()
    if source_key == "bloodtrans_record" and "record_content" not in selected:
        raise SourceEvidenceUnavailable()
    select_sql = ", ".join(bundle_assembly._quote_ident(field) for field in selected) or "1 AS row_marker"
    order_candidates = (
        *getattr(bundle_assembly, "_ORDER_COLUMNS_PRIORITY", ()),
        "document_id",
        "pathology_exam_id",
        "pathology_id",
        "diagnosis_id",
        "order_id",
        "surgery_begin_datetime",
    )
    order_columns = [field for field in order_candidates if field in columns]
    order_sql = ""
    if order_columns:
        order_sql = " ORDER BY " + ", ".join(
            f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST" for field in order_columns
        )
    sql = (
        f"SELECT {select_sql} FROM {bundle_assembly._qualified_table(trusted_schema, source_key)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"{order_sql} LIMIT :limit_rows"
    )
    with engine.connect() as connection:
        rows = connection.execute(
            bundle_assembly.text(sql),
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "limit_rows": _source_limit(source_key),
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def read_luxian_0609_snapshot_source_rows(
    *,
    source_key: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
) -> SnapshotSourceRows:
    """为 EvidenceSnapshot 执行一次 limit+1 三坐标有界读取。"""

    coordinates = (institute_id, patient_id, visit_id)
    if not all(isinstance(value, str) and value.strip() for value in coordinates):
        raise SourceEvidenceUnavailable()
    normalized_source = str(source_key or "").strip().lower()
    if normalized_source == EVALUATION_HORIZON_SOURCE_KEY:
        # 该来源由 Evidence Session 根据权威出院源与显式任务日期派生，
        # 永远不能被解释成数据库物理表。
        raise SourceEvidenceUnavailable()
    if normalized_source == CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY:
        return read_luxian_0609_discharge_horizon_rows(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
    if normalized_source == CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY:
        return read_luxian_0609_severity_order_rows(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
    if normalized_source == CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY:
        present = has_luxian_0609_current_visit_unstable_order(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
        return SnapshotSourceRows.create(
            source_key=normalized_source,
            rows=({"present": True},) if present else (),
            truncated=False,
            limit_rows=1,
        )
    approved_fields = _SNAPSHOT_SOURCE_FIELDS.get(normalized_source)
    if approved_fields is None:
        raise SourceEvidenceUnavailable()
    trusted_schema = bundle_assembly._default_source_schema()
    if source_schema not in (None, trusted_schema):
        raise SourceEvidenceUnavailable()
    engine = bundle_assembly.engine
    if engine is None:
        raise SourceEvidenceUnavailable()
    columns = set(bundle_assembly._get_table_columns(trusted_schema, normalized_source))
    required = {"institute_id", "patient_id", "visit_id"}
    if not required.issubset(columns):
        raise SourceEvidenceUnavailable()
    selected = [field for field in approved_fields if field in columns]
    if not selected:
        raise SourceEvidenceUnavailable()
    order_candidates = (
        *getattr(bundle_assembly, "_ORDER_COLUMNS_PRIORITY", ()),
        "document_id",
        "pathology_exam_id",
        "pathology_id",
        "diagnosis_id",
        "order_id",
        "record_time",
        "report_datetime",
        "surgery_begin_datetime",
        "surgery_begin_time",
        "transfution_datetime",
    )
    order_columns = []
    # 优先业务主键/时间，再补齐全部批准投影字段形成稳定全序。
    # 完全相同的重复行即使数据库交换顺序，其规范化材料仍相同。
    for field in (*order_candidates, *selected):
        if field in columns and field not in order_columns:
            order_columns.append(field)
    if not order_columns:
        raise SourceEvidenceUnavailable()

    select_sql = ", ".join(bundle_assembly._quote_ident(field) for field in selected)
    order_sql = ", ".join(
        f"{bundle_assembly._quote_ident(field)} ASC NULLS LAST"
        for field in order_columns
    )
    limit_rows = _source_limit(normalized_source)
    sql = (
        f"SELECT {select_sql} "
        f"FROM {bundle_assembly._qualified_table(trusted_schema, normalized_source)} "
        f"WHERE {bundle_assembly._quote_ident('institute_id')} = :institute_id "
        f"AND {bundle_assembly._quote_ident('patient_id')} = :patient_id "
        f"AND {bundle_assembly._quote_ident('visit_id')} = :visit_id "
        f"ORDER BY {order_sql} LIMIT :limit_rows"
    )
    try:
        with engine.connect() as connection:
            raw_rows = connection.execute(
                bundle_assembly.text(sql),
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "limit_rows": limit_rows + 1,
                },
            ).mappings().all()
    except Exception:
        raise SourceEvidenceQueryError() from None
    truncated = len(raw_rows) > limit_rows
    return SnapshotSourceRows.create(
        source_key=normalized_source,
        rows=[dict(row) for row in raw_rows[:limit_rows]],
        truncated=truncated,
        limit_rows=limit_rows,
    )
