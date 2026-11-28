"""扩展文书规则族共用的执行上下文、材料读取、时间终点与受控决策构造。

供 `native_extended_document_execution.py` 与各拆分后的规则族执行模块共享，
避免规则族模块反向依赖总调度文件造成循环导入。
"""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from ..course_body_fact_extraction import CourseBodyDocument
from ..decision_model import (
    ALLOWED_REASON_CODES_BY_FINAL_STATE,
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from ..evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from ..evidence_snapshot import Luxian0609EvidenceSnapshot
from .shared import _clean, _parse_datetime

logger = logging.getLogger(__name__)
HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
BLOCKING_DISCHARGE_HORIZON_ERRORS = frozenset(
    {"authoritative_time_missing", "authoritative_time_conflict"}
)
_BLOCKING_DISCHARGE_HORIZON_ERRORS = BLOCKING_DISCHARGE_HORIZON_ERRORS


@dataclass(frozen=True)
class ExtendedDocumentFamilyOutcome:
    """单个扩展文书规则族的标准执行输出。"""

    decisions: tuple[RuleDecision, ...]
    display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


SourceRowsCache = dict[str, tuple[tuple[Mapping[str, Any], ...], str]]


def source_rows(
    materials: Luxian0609EvidenceMaterialStore,
    source_key: str,
    *,
    cache: SourceRowsCache | None = None,
) -> tuple[tuple[Mapping[str, Any], ...], str]:
    """从不可变材料仓读取指定来源行；截断或不可用时返回标准错误码，并支持组内缓存复用。"""

    if cache is not None and source_key in cache:
        return cache[source_key]
    try:
        rows = materials.rows(source_key)
    except EvidenceMaterialTruncated:
        result: tuple[tuple[Mapping[str, Any], ...], str] = ((), "source_truncated")
    except EvidenceMaterialUnavailable:
        result = ((), "source_unavailable")
    else:
        result = (tuple(dict(row) for row in rows), "")
    if cache is not None:
        cache[source_key] = result
    return result


def precise_datetime(value: Any) -> datetime | None:
    """仅接受精确到时分的时间值，纯日期返回 None。"""

    if not re.search(r"\d{2}:\d{2}", str(value or "")):
        return None
    return _parse_datetime(value)


def parse_hospital_datetime(value: Any) -> datetime | None:
    """解析时间字符串并将带时区偏移的值转换至医院本地时间（Asia/Shanghai）后再去 tzinfo。"""

    text = _clean(value)
    if not text:
        return None
    normalized = text.replace("T", " ").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(HOSPITAL_TIMEZONE).replace(tzinfo=None)
    return parsed


def has_any_text(row: Mapping[str, Any], fields: Sequence[str]) -> bool:
    return any(_clean(row.get(field)) for field in fields)


def resolve_horizon_rows(
    evidence_snapshot: Luxian0609EvidenceSnapshot,
    evidence_materials: Luxian0609EvidenceMaterialStore,
    *,
    cache: SourceRowsCache | None = None,
) -> tuple[tuple[Mapping[str, Any], ...], str]:
    """读取冻结评价终点来源行；若观测为空则保留观测层原因码。"""

    horizon_rows, horizon_error = source_rows(
        evidence_materials, "evaluation_context.horizon", cache=cache
    )
    if not horizon_rows and not horizon_error:
        horizon_observation = next(
            (
                observation
                for observation in evidence_snapshot.observations
                if observation.source_key == "evaluation_context.horizon"
            ),
            None,
        )
        if (
            horizon_observation is not None
            and horizon_observation.query_state.value == "empty"
        ):
            horizon_error = _clean(horizon_observation.reason_code)
    return horizon_rows, horizon_error


def discharge_time_with_source(
    registration_rows: Sequence[Mapping[str, Any]],
    discharge_rows: Sequence[Mapping[str, Any]],
    horizon_rows: Sequence[Mapping[str, Any]] = (),
    horizon_error: str = "",
) -> tuple[datetime | None, str]:
    """按权威优先级解析出院时间及其来源标记。"""

    if horizon_error in _BLOCKING_DISCHARGE_HORIZON_ERRORS:
        return None, ""
    if len(horizon_rows) == 1:
        horizon_row = horizon_rows[0]
        if _clean(horizon_row.get("basis")) == "discharge_date":
            horizon_time = _parse_datetime(horizon_row.get("horizon_datetime"))
            horizon_date = _parse_datetime(horizon_row.get("horizon_date"))
            if (
                horizon_time is not None
                and horizon_date is not None
                and horizon_time.date() != horizon_date.date()
            ):
                return None, ""
            if (
                horizon_row.get("time_precision") == "date"
                or horizon_time is None
                or precise_datetime(horizon_row.get("horizon_datetime")) is None
            ):
                return horizon_time or horizon_date, "evaluation_context.horizon_date_only"
            if horizon_time is not None or horizon_date is not None:
                return (
                    horizon_time or horizon_date,
                    "evaluation_context.horizon",
                )

    for row in registration_rows:
        for field_name in ("discharge_datetime", "discharge_time"):
            parsed = _parse_datetime(row.get(field_name))
            if parsed is not None:
                return parsed, (
                    f"inpat_registration.{field_name}"
                    if precise_datetime(row.get(field_name)) is not None
                    else "inpat_registration.date_only"
                )

    for row in discharge_rows:
        discharge_date = _parse_datetime(row.get("discharge_date"))
        precise_time: tuple[datetime, str] | None = None
        for field_name in ("discharge_datetime", "discharge_time"):
            parsed = precise_datetime(row.get(field_name))
            if parsed is not None:
                precise_time = (parsed, field_name)
                break
        # CDM 标准 discharge_date 决定业务日；同日的兼容时间补足精度，
        # 跨日矛盾时不能让兼容字段覆盖标准日期。
        if discharge_date is not None:
            if precise_time is not None and precise_time[0].date() == discharge_date.date():
                return precise_time[0], f"discharge_record.{precise_time[1]}"
            return discharge_date, "discharge_record.date_only"
        if precise_time is not None:
            return precise_time[0], f"discharge_record.{precise_time[1]}"
    return None, ""


def discharge_time(
    registration_rows: Sequence[Mapping[str, Any]],
    discharge_rows: Sequence[Mapping[str, Any]],
    horizon_rows: Sequence[Mapping[str, Any]] = (),
    horizon_error: str = "",
) -> datetime | None:
    return discharge_time_with_source(
        registration_rows,
        discharge_rows,
        horizon_rows,
        horizon_error,
    )[0]


def resolve_evaluation_horizon(
    horizon_rows: Sequence[Mapping[str, Any]],
    horizon_error: str,
) -> tuple[date | None, datetime | None, str | None]:
    """读取单一冻结评价终点，拒绝缺失、重复及日期时间冲突。"""

    if horizon_error:
        return None, None, horizon_error
    if not horizon_rows:
        return None, None, "authoritative_time_missing"
    if len(horizon_rows) != 1:
        return None, None, "authoritative_time_conflict"
    row = horizon_rows[0]
    declared_time = precise_datetime(row.get("horizon_datetime"))
    if _clean(row.get("horizon_datetime")) and declared_time is None:
        return None, None, "authoritative_time_missing"
    horizon_time = None if row.get("time_precision") == "date" else declared_time
    raw_date = _clean(row.get("horizon_date"))
    try:
        horizon_date = date.fromisoformat(raw_date) if raw_date else None
    except ValueError:
        horizon_date = None
    if declared_time is not None and horizon_date is not None:
        if declared_time.date() != horizon_date:
            return None, None, "authoritative_time_conflict"
    if horizon_time is None and horizon_date is None:
        return None, None, "authoritative_time_missing"
    return horizon_date, horizon_time, None


def fact_refs(
    snapshot: Luxian0609EvidenceSnapshot,
    source_keys: Sequence[str],
) -> tuple[str, ...]:
    """按来源键提取证据快照级观测引用（去 sha256: 前缀并排序）。"""

    wanted = set(source_keys)
    return tuple(
        sorted(
            observation.snapshot_ref.removeprefix("sha256:")
            for observation in snapshot.observations
            if observation.source_key in wanted
        )
    )


def material_text(row: Mapping[str, Any]) -> str:
    """拼接单条文书/医嘱/检验行的受控正文检索文本。"""

    return "\n".join(
        _clean(row.get(key))
        for key in (
            "record_content", "document_title", "order_name", "generic_name",
            "case_characteristic", "diagnose_based_on", "differential_diagnosis", "treatment_plan",
            # 转入记录的诊疗计划章节（通用正文为空时药物与处置只写在这里，1019 C10）。
            "transfer_treatment_plan",
            # 手术记录正文在手术经过（054/057 围术期预防用药引文）。
            "surgery_process",
            "item_code", "item_name", "item_abbreviation", "result",
            "result_flag", "abnormal_flag", "diagnosis_name", "labtest_subject",
            "specimen",
        )
        if _clean(row.get(key))
    )


def course_body_candidate_inputs(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    candidates: Sequence[tuple[str, int, Mapping[str, Any]]],
) -> tuple[tuple[CourseBodyDocument, ...], Mapping[tuple[str, int], str]]:
    """按原行 occurrence 绑定，不能把摘要排序与原行索引 zip 或按 docID 合并。"""

    available: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    documents: list[CourseBodyDocument] = []
    refs: dict[tuple[str, int], str] = {}
    for source, ordinal, row in candidates:
        if source not in available:
            available[source] = list(materials.document_rows(source, snapshot=snapshot))
        matches = available[source]
        position = next(
            (index for index, (_ref, original) in enumerate(matches) if original == row),
            None,
        )
        if position is None:
            raise ValueError("course body material occurrence mismatch")
        ref, _original = matches.pop(position)
        refs[(source, ordinal)] = ref
        documents.append(CourseBodyDocument(ref, source, row.get("record_content")))
    return tuple(documents), refs


def build_extended_decision(
    *,
    rule_id: str,
    snapshot: Luxian0609EvidenceSnapshot,
    source_keys: Sequence[str],
    final_state: str,
    reason_code: str,
    document_refs: Sequence[str] = (),
    exact_document_refs: bool = False,
    criterion_results: Sequence[Any] = (),
    positive_document_refs: Sequence[str] = (),
    affirmative_applicability: bool = False,
) -> RuleDecision:
    """构造扩展文书规则族的受控 RuleDecision，保持既有 evaluator_version 与错误降级口径。"""

    if final_state == "technical_error":
        if reason_code not in ALLOWED_REASON_CODES_BY_FINAL_STATE["technical_error"]:
            reason_code = "execution_program_error"
        # 诊断日志：只记规则、原因码与出错代码行，不含病历或模型内容。
        logger.warning(
            "LX0609 扩展文书族技术错误: rule_id=%s reason_code=%s call_line=%s",
            rule_id, reason_code, sys._getframe(1).f_lineno,
        )
    dimensions = {
        "compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
        ),
        "non_compliant": (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
        ),
        "not_applicable": (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
        ),
        "data_gap": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
        ),
        "uncertain": (
            ApplicabilityState.UNKNOWN,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
        ),
        "technical_error": (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
        ),
    }
    applicability, evidence_state, direction = dimensions[final_state]
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=direction,
        reason_code=reason_code,
        fact_refs=(
            tuple(dict.fromkeys(document_refs))
            if exact_document_refs
            else tuple(dict.fromkeys((*fact_refs(snapshot, source_keys), *document_refs)))
        ),
        positive_document_refs=tuple(positive_document_refs),
        affirmative_applicability=affirmative_applicability,
        evaluator_version="extended-document-v2",
        confidence=None,
        criterion_results=tuple(criterion_results),
    )
