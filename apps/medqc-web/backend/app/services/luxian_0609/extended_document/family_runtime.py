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


def source_rows(
    materials: Luxian0609EvidenceMaterialStore,
    source_key: str,
) -> tuple[tuple[Mapping[str, Any], ...], str]:
    """从不可变材料仓读取指定来源行；截断或不可用时返回标准错误码。"""

    try:
        rows = materials.rows(source_key)
    except EvidenceMaterialTruncated:
        return (), "source_truncated"
    except EvidenceMaterialUnavailable:
        return (), "source_unavailable"
    return tuple(dict(row) for row in rows), ""


def precise_datetime(value: Any) -> datetime | None:
    """仅接受精确到时分的时间值，纯日期返回 None。"""

    if not re.search(r"\d{2}:\d{2}", str(value or "")):
        return None
    return _parse_datetime(value)


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
