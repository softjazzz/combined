"""LX0609 所选规则证据来源的一次性只读快照 provider。"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

from .evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
    build_luxian_0609_visit_ref,
)
from .fact_schema import FACT_SCHEMA_VERSION, FactV2
from .evaluation_horizon import (
    EVALUATION_HORIZON_POLICIES,
    EVALUATION_HORIZON_POLICY_AUTHORITATIVE_DISCHARGE,
    EVALUATION_HORIZON_POLICY_DISABLED,
    EVALUATION_HORIZON_POLICY_FROZEN_TASK_DATE,
    resolve_frozen_discharge_horizon,
)
from .evidence_material import (
    Luxian0609EvidenceMaterialStore,
    Luxian0609EvidenceReadSession,
    build_material_document_refs,
    build_material_snapshot_ref,
)
from .source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
    EVALUATION_HORIZON_SOURCE_KEY,
    SnapshotSourceRows,
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
    canonical_source_evidence,
    digest_source_evidence,
    has_trusted_performed_surgery,
    read_luxian_0609_snapshot_source_rows,
)
from .source_manifest import QueryStatus
from .source_registry import (
    SOURCE_REGISTRY_VERSION,
    SourceAccessMode,
    resolve_luxian_0609_controlled_fact_source_keys,
    resolve_luxian_0609_decision_support_source_keys,
    resolve_luxian_0609_rule_sources,
    resolve_luxian_0609_physical_source_entry,
)


SnapshotRowReader = Callable[..., SnapshotSourceRows]
_LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
_EMERGENCY_RESCUE_NEGATIVE_PATTERN = re.compile(
    r"(?:非|不是|不属于|排除)(?:急诊|紧急).{0,12}(?:抢救|救命|挽救生命)"
)
_EMERGENCY_RESCUE_POSITIVE_PATTERN = re.compile(
    r"(?:急诊|紧急).{0,12}(?:抢救|救命|挽救生命)"
)
_EFFECTIVE_SURGERY_ORDER_STATUSES = frozenset({"新开", "执行中", "停止"})
_EXCLUDED_SURGERY_ORDER_STATUSES = frozenset({"取消", "撤销", "作废"})
_KNOWN_NON_SURGERY_ORDER_TYPES = frozenset(
    {"检查", "检验", "治疗", "护理", "嘱托", "转科", "其他"}
)


def classify_current_visit_surgery_order_rows(
    *,
    rows: tuple[Mapping[str, Any], ...],
    completeness: SourceCompleteness,
) -> tuple[str, tuple[str, ...]]:
    """按029既定结构化口径判定手术医嘱，并返回仅供材料定位的原始 ID。

    返回的 ID 绝不能写入 FactV2；它只用于把同一次冻结材料行还原为公共
    证据投影所需的 document_ref。判定本身只依赖 ``order_type`` 和
    ``order_status``，不从名称推断手术。
    """

    ordered_rows = tuple(sorted(rows, key=lambda row: canonical_source_evidence(dict(row))))
    states: list[tuple[str, str]] = []
    for row in ordered_rows:
        source_document_id = next(
            (
                str(row.get(field) or "").strip()
                for field in ("order_id", "document_id", "id")
                if str(row.get(field) or "").strip()
            ),
            "",
        )
        order_type = str(row.get("order_type") or "").strip()
        order_status = str(row.get("order_status") or "").strip()
        if order_status in _EXCLUDED_SURGERY_ORDER_STATUSES:
            states.append(("negated", source_document_id))
        elif order_status not in _EFFECTIVE_SURGERY_ORDER_STATUSES:
            states.append(("uncertain", source_document_id))
        elif order_type == "手术":
            states.append(("affirmed", source_document_id))
        elif order_type in _KNOWN_NON_SURGERY_ORDER_TYPES:
            states.append(("negated", source_document_id))
        else:
            states.append(("uncertain", source_document_id))

    positive_ids = tuple(value for state, value in states if state == "affirmed")
    uncertain_ids = tuple(value for state, value in states if state == "uncertain")
    if positive_ids:
        return "affirmed", positive_ids
    if uncertain_ids or completeness is not SourceCompleteness.COMPLETE:
        return "uncertain", uncertain_ids
    return "negated", ()


def _surgery_order_facts(
    *,
    rows: tuple[Mapping[str, Any], ...],
    completeness: SourceCompleteness,
    visit_ref: str,
    source_snapshot_hash: str,
    created_at: str,
) -> tuple[FactV2, ...]:
    """将受控医嘱类型投影为029的单一聚合手术医嘱事实。

    只信任结构化 ``order_type == 手术`` 与既有有效医嘱状态；不从医嘱名称
    猜测术式。完整来源中的全部已知非手术类型才能给出否定，其他情形保留未知。
    """

    assertion, _ = classify_current_visit_surgery_order_rows(
        rows=rows,
        completeness=completeness,
    )
    return (
        FactV2.create(
            visit_ref=visit_ref,
            family="surgery_anesthesia",
            fact_type="current_visit_surgery_order_confirmed",
            normalized_value={"surgery_order": assertion == "affirmed"},
            trigger_scope="current_visit",
            current_visit_relevance="relevant",
            assertion=assertion,
            assertion_context="other",
            event_status="ordered" if assertion == "affirmed" else "unknown",
            source_key="inpat_nondrug_order",
            # 这是来源聚合 Fact；逐条医嘱坐标只由 EvidenceMaterial 承载，
            # 不能把真实 ID 或材料摘要塞入 Fact 合同。
            source_document_id="",
            source_document_type="inpat_nondrug_order",
            record_time=None,
            submit_time=None,
            update_time=None,
            quote="",
            redaction_terms=(),
            confidence=1.0,
            extractor="deterministic",
            extractor_version="snapshot-provider-surgery-order-v1",
            fact_schema_version=FACT_SCHEMA_VERSION,
            source_snapshot_hash=source_snapshot_hash,
            created_at=created_at,
            extensions={},
            known_upstream_fact_ids=(),
        ),
    )


def _explicit_emergency_rescue_state(
    rows: tuple[Mapping[str, Any], ...],
) -> bool | None:
    """仅从明确肯定/否定文本生成039急诊抢救事实；沉默和冲突保持未知。"""

    states: set[bool] = set()
    for row in rows:
        text = " ".join(
            str(row.get(key) or "").strip()
            for key in ("record_content", "document_title", "surgery_name")
            if str(row.get(key) or "").strip()
        )
        if not text:
            continue
        if _EMERGENCY_RESCUE_NEGATIVE_PATTERN.search(text):
            states.add(False)
            text = _EMERGENCY_RESCUE_NEGATIVE_PATTERN.sub("", text)
        if _EMERGENCY_RESCUE_POSITIVE_PATTERN.search(text):
            states.add(True)
    return next(iter(states)) if len(states) == 1 else None


def _require_coordinates(*, institute_id: str, patient_id: str, visit_id: str) -> None:
    if not all(
        isinstance(value, str) and value.strip()
        for value in (institute_id, patient_id, visit_id)
    ):
        raise ValueError("three visit coordinates are required")


def _unavailable_observation(*, source_key: str, query_version: str) -> SourceObservation:
    completeness = SourceCompleteness.UNPROVEN
    return SourceObservation.create(
        source_key=source_key,
        query_state=QueryStatus.UNAVAILABLE,
        completeness=completeness,
        record_count=None,
        query_version=query_version,
        snapshot_ref=build_material_snapshot_ref(
            source_key=source_key,
            query_version=query_version,
            query_state=QueryStatus.UNAVAILABLE,
            completeness=completeness,
            document_refs=(),
        ),
        reason_code="SOURCE_READER_NOT_REGISTERED",
    )


def _parse_evaluation_as_of_date(value: str | None) -> date | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("evaluation_as_of_date must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError("evaluation_as_of_date must be YYYY-MM-DD") from None
    if parsed.isoformat() != value:
        raise ValueError("evaluation_as_of_date must be YYYY-MM-DD")
    return parsed


def _parse_authoritative_date(value: Any, *, field_name: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return (
            value.astimezone(_LOCAL_TIMEZONE).date()
            if value.tzinfo is not None
            else value.date()
        )
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a valid date")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed_datetime = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            return date.fromisoformat(normalized)
        except ValueError:
            raise ValueError(f"{field_name} must be a valid date") from None
    return (
        parsed_datetime.astimezone(_LOCAL_TIMEZONE).date()
        if parsed_datetime.tzinfo is not None
        else parsed_datetime.date()
    )


def _parse_authoritative_datetime(
    value: Any, *, field_name: str
) -> datetime | None:
    """保留权威时间的分钟级精度；纯日期输入不臆造零点。"""

    if (
        value is None
        or value == ""
        or isinstance(value, date) and not isinstance(value, datetime)
    ):
        return None
    if isinstance(value, datetime):
        return (
            value.astimezone(_LOCAL_TIMEZONE).replace(tzinfo=None)
            if value.tzinfo is not None
            else value
        )
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a valid date")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        # 纯日期仍由 date 口径消费，不伪造分钟级终点。
        try:
            date.fromisoformat(normalized)
        except ValueError:
            raise ValueError(f"{field_name} must be a valid date") from None
        return None
    return (
        parsed.astimezone(_LOCAL_TIMEZONE).replace(tzinfo=None)
        if parsed.tzinfo is not None
        else parsed
    )


def _parse_discharge_date(value: Any) -> date | None:
    return _parse_authoritative_date(value, field_name="discharge_datetime")


def _parse_admission_date(value: Any) -> date | None:
    return _parse_authoritative_date(value, field_name="admission_datetime")


def build_luxian_0609_evidence_read_session(
    *,
    selected_rule_ids: tuple[str, ...],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    created_at: str,
    evaluation_as_of_date: str | None = None,
    evaluation_horizon_policy: str | None = None,
    evaluation_horizon_snapshot: Mapping[str, Any] | None = None,
    horizon_unavailable_reason: str | None = None,
    row_reader: SnapshotRowReader = read_luxian_0609_snapshot_source_rows,
    additional_source_keys: tuple[str, ...] = (),
) -> Luxian0609EvidenceReadSession:
    """一次读取生成安全快照与请求内材料；raw rows 不进入快照。"""

    _require_coordinates(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
    )
    if not selected_rule_ids:
        raise ValueError("selected_rule_ids must not be empty")
    needs_evaluation_horizon = bool(
        {
            "LX0609-01-01-01",
            "LX0609-01-02-01",
            "LX0609-04-02-01",
            "LX0609-02-01-01",
            "LX0609-02-01-02",
            "LX0609-02-01-03",
            "LX0609-02-01-04",
            "LX0609-02-01-05",
            "LX0609-06-01-04",
            "LX0609-06-01-05",
            "LX0609-06-03-03",
            "LX0609-06-03-04",
            "LX0609-03-01-01",
            "LX0609-03-01-04",
            "LX0609-07-03-01",
            "LX0609-09-02-01",
            "LX0609-06-04-01",
            "LX0609-05-01-03",
            "LX0609-08-01-01",
            "LX0609-10-02-01",
            "LX0609-04-05-01",
            "LX0609-04-05-02",
            "LX0609-08-02-01",
            "LX0609-08-02-02",
            # 036/037 术后24小时访视时限未到时暂不判缺失。
            "LX0609-04-04-01",
            "LX0609-04-04-02",
            # 06-01-01/06-03-02 区分出院终末与在院运行中的未到时限。
            "LX0609-06-01-01",
            "LX0609-06-03-02",
        }.intersection(selected_rule_ids)
    )
    if (
        evaluation_horizon_policy is not None
        and evaluation_horizon_policy not in EVALUATION_HORIZON_POLICIES
    ):
        raise ValueError("evaluation_horizon_policy is invalid")
    if horizon_unavailable_reason not in {
        None,
        "authoritative_time_missing",
        "authoritative_time_conflict",
    }:
        raise ValueError("horizon_unavailable_reason is invalid")
    if (
        horizon_unavailable_reason is not None
        and evaluation_horizon_policy != EVALUATION_HORIZON_POLICY_DISABLED
    ):
        raise ValueError("horizon_unavailable_reason requires disabled policy")
    explicit_as_of_date = (
        _parse_evaluation_as_of_date(evaluation_as_of_date)
        if needs_evaluation_horizon
        and evaluation_horizon_policy
        in {None, EVALUATION_HORIZON_POLICY_FROZEN_TASK_DATE}
        else None
    )
    if (
        needs_evaluation_horizon
        and evaluation_horizon_policy
        == EVALUATION_HORIZON_POLICY_FROZEN_TASK_DATE
        and explicit_as_of_date is None
    ):
        raise ValueError("frozen_task_date policy requires evaluation_as_of_date")
    resolved = resolve_luxian_0609_rule_sources(tuple(selected_rule_ids))
    entries_by_document = {
        entry.document_type: entry
        for entries in resolved.values()
        for entry in entries
    }

    observations: list[SourceObservation] = []
    facts: list[FactV2] = []
    all_document_refs: list[str] = []
    bounded_requests: dict[str, Any] = {}
    for document_type in sorted(entries_by_document):
        entry = entries_by_document[document_type]
        if entry.access_mode is not SourceAccessMode.BOUNDED_SOURCE_V1:
            observations.append(
                _unavailable_observation(
                    source_key=entry.document_type,
                    query_version=entry.query_version,
                )
            )
            continue
        for source_key in entry.physical_source_keys:
            existing = bounded_requests.get(source_key)
            if existing is not None and existing.query_version != entry.query_version:
                raise ValueError("conflicting source query versions")
            bounded_requests[source_key] = entry
    for source_key in additional_source_keys:
        entry = resolve_luxian_0609_physical_source_entry(source_key)
        if entry.access_mode is not SourceAccessMode.BOUNDED_SOURCE_V1:
            raise ValueError("additional material source is not bounded")
        existing = bounded_requests.get(source_key)
        if existing is not None and existing.query_version != entry.query_version:
            raise ValueError("conflicting source query versions")
        bounded_requests[source_key] = entry
    for source_key in resolve_luxian_0609_decision_support_source_keys(
        selected_rule_ids
    ):
        if source_key == EVALUATION_HORIZON_SOURCE_KEY:
            # 请求内派生来源在物理读取完成后生成，不能被当成数据库表读取。
            continue
        entry = resolve_luxian_0609_physical_source_entry(source_key)
        if entry.access_mode is not SourceAccessMode.BOUNDED_SOURCE_V1:
            raise ValueError("decision support source is not bounded")
        existing = bounded_requests.get(source_key)
        if existing is not None and existing.query_version != entry.query_version:
            raise ValueError("conflicting source query versions")
        bounded_requests[source_key] = entry
    if needs_evaluation_horizon and "inpat_registration" not in bounded_requests:
        # 评价终点必须与本次入院时间核对，不能只凭孤立的出院日期闭合时间窗。
        bounded_requests["inpat_registration"] = (
            resolve_luxian_0609_physical_source_entry("inpat_registration")
        )
    for source_key in resolve_luxian_0609_controlled_fact_source_keys(
        selected_rule_ids
    ):
        entry = resolve_luxian_0609_physical_source_entry(source_key)
        if entry.access_mode is not SourceAccessMode.CONTROLLED_FACT_V1:
            raise ValueError("controlled fact source has invalid access mode")
        bounded_requests[source_key] = entry

    material_sources: dict[str, SnapshotSourceRows] = {}
    for source_key in sorted(bounded_requests):
        entry = bounded_requests[source_key]
        try:
            result = row_reader(
                source_key=source_key,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
            )
        except SourceEvidenceUnavailable:
            completeness = SourceCompleteness.UNPROVEN
            observations.append(
                SourceObservation.create(
                    source_key=source_key,
                    query_state=QueryStatus.UNAVAILABLE,
                    completeness=completeness,
                    record_count=None,
                    query_version=entry.query_version,
                    snapshot_ref=build_material_snapshot_ref(
                        source_key=source_key,
                        query_version=entry.query_version,
                        query_state=QueryStatus.UNAVAILABLE,
                        completeness=completeness,
                        document_refs=(),
                    ),
                    reason_code="SOURCE_CAPABILITY_UNAVAILABLE",
                )
            )
            continue
        except SourceEvidenceQueryError:
            completeness = SourceCompleteness.UNPROVEN
            observations.append(
                SourceObservation.create(
                    source_key=source_key,
                    query_state=QueryStatus.ERROR,
                    completeness=completeness,
                    record_count=None,
                    query_version=entry.query_version,
                    snapshot_ref=build_material_snapshot_ref(
                        source_key=source_key,
                        query_version=entry.query_version,
                        query_state=QueryStatus.ERROR,
                        completeness=completeness,
                        document_refs=(),
                    ),
                    error_code="QUERY_ERROR",
                )
            )
            continue

        # reader 之外的契约或组装错误必须显式失败，不能伪装成数据库查询 ERROR。
        if not isinstance(result, SnapshotSourceRows) or result.source_key != source_key:
            raise TypeError("invalid snapshot row reader result")
        if entry.access_mode is SourceAccessMode.CONTROLLED_FACT_V1:
            if result.truncated or len(result.rows) > 1:
                raise ValueError("controlled fact result must be exact")
            if result.rows:
                if len(result.rows) != 1 or result.rows[0].get("present") is not True:
                    raise ValueError("invalid controlled fact positive result")
                query_state = QueryStatus.AVAILABLE
                record_count = 1
                assertion = "affirmed"
                present = True
            else:
                query_state = QueryStatus.EMPTY
                record_count = 0
                assertion = "negated"
                present = False
            completeness = SourceCompleteness.COMPLETE
            snapshot_ref = build_material_snapshot_ref(
                source_key=source_key,
                query_version=entry.query_version,
                query_state=query_state,
                completeness=completeness,
                document_refs=(),
            )
            observation = SourceObservation.create(
                source_key=source_key,
                query_state=query_state,
                completeness=completeness,
                record_count=record_count,
                query_version=entry.query_version,
                snapshot_ref=snapshot_ref,
            )
            observations.append(observation)
            if source_key == CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY:
                facts.append(
                    FactV2.create(
                        visit_ref=build_luxian_0609_visit_ref(
                            institute_id=institute_id,
                            patient_id=patient_id,
                            visit_id=visit_id,
                        ),
                        family="course_quality",
                        fact_type="current_visit_unstable_order",
                        normalized_value={"present": present},
                        trigger_scope="current_visit",
                        current_visit_relevance="relevant",
                        assertion=assertion,
                        assertion_context="other",
                        event_status="ordered" if present else "unknown",
                        source_key=source_key,
                        source_document_id="",
                        source_document_type="medical_order",
                        record_time=None,
                        submit_time=None,
                        update_time=None,
                        quote="",
                        redaction_terms=(),
                        confidence=1.0,
                        extractor="deterministic",
                        extractor_version="snapshot-provider-unstable-order-v1",
                        fact_schema_version=FACT_SCHEMA_VERSION,
                        source_snapshot_hash=snapshot_ref.removeprefix("sha256:"),
                        created_at=created_at,
                        extensions={},
                        known_upstream_fact_ids=(),
                    )
                )
            continue

        refs = build_material_document_refs(source_key, result.rows)
        if result.rows:
            query_state = QueryStatus.AVAILABLE
            completeness = (
                SourceCompleteness.TRUNCATED
                if result.truncated
                else SourceCompleteness.COMPLETE
            )
            record_count: int | None = len(result.rows)
        else:
            query_state = QueryStatus.EMPTY
            completeness = SourceCompleteness.COMPLETE
            record_count = 0
        snapshot_ref = build_material_snapshot_ref(
            source_key=source_key,
            query_version=entry.query_version,
            query_state=query_state,
            completeness=completeness,
            document_refs=refs,
        )
        observation = SourceObservation.create(
            source_key=source_key,
            query_state=query_state,
            completeness=completeness,
            record_count=record_count,
            query_version=entry.query_version,
            snapshot_ref=snapshot_ref,
        )
        observations.append(observation)
        if source_key == "inpat_nondrug_order" and "LX0609-04-01-01" in selected_rule_ids:
            facts.extend(
                _surgery_order_facts(
                    rows=result.rows,
                    completeness=completeness,
                    visit_ref=build_luxian_0609_visit_ref(
                        institute_id=institute_id,
                        patient_id=patient_id,
                        visit_id=visit_id,
                    ),
                    source_snapshot_hash=snapshot_ref.removeprefix("sha256:"),
                    created_at=created_at,
                )
            )
        if source_key == "surgery_inform_consent":
            facts.append(
                FactV2.create(
                    visit_ref=build_luxian_0609_visit_ref(
                        institute_id=institute_id,
                        patient_id=patient_id,
                        visit_id=visit_id,
                    ),
                    family="surgery_anesthesia",
                    fact_type="current_visit_surgery_consent_source_readiness",
                    normalized_value={
                        "complete": completeness is SourceCompleteness.COMPLETE,
                    },
                    trigger_scope="current_visit",
                    current_visit_relevance="relevant",
                    assertion=(
                        "affirmed"
                        if completeness is SourceCompleteness.COMPLETE
                        else "unknown"
                    ),
                    assertion_context="other",
                    event_status="unknown",
                    source_key=source_key,
                    source_document_id="",
                    source_document_type=source_key,
                    record_time=None,
                    submit_time=None,
                    update_time=None,
                    quote="",
                    redaction_terms=(),
                    confidence=1.0,
                    extractor="deterministic",
                    extractor_version="snapshot-provider-surgery-consent-readiness-v1",
                    fact_schema_version=FACT_SCHEMA_VERSION,
                    source_snapshot_hash=snapshot_ref.removeprefix("sha256:"),
                    created_at=created_at,
                    extensions={},
                    known_upstream_fact_ids=(),
                )
            )
        if source_key == "surgery_record" or (
            source_key == "mr_surgery" and "LX0609-04-01-02" in selected_rule_ids
        ):
            performed = any(
                has_trusted_performed_surgery(source_key=source_key, row=row)
                for row in result.rows
            )
            if performed or query_state is QueryStatus.EMPTY:
                facts.append(
                    FactV2.create(
                        visit_ref=build_luxian_0609_visit_ref(
                            institute_id=institute_id,
                            patient_id=patient_id,
                            visit_id=visit_id,
                        ),
                        family="surgery_anesthesia",
                        fact_type="current_visit_surgery_confirmed",
                        normalized_value={"performed": performed},
                        trigger_scope="current_visit",
                        current_visit_relevance="relevant",
                        assertion="affirmed" if performed else "negated",
                        assertion_context="other",
                        event_status="performed" if performed else "unknown",
                        source_key=source_key,
                        source_document_id="",
                        source_document_type=source_key,
                        record_time=None,
                        submit_time=None,
                        update_time=None,
                        quote="",
                        redaction_terms=(),
                        confidence=1.0,
                        extractor="deterministic",
                        extractor_version=(
                            "snapshot-provider-surgery-record-v1"
                            if source_key == "surgery_record"
                            else "snapshot-provider-mr-surgery-v1"
                        ),
                        fact_schema_version=FACT_SCHEMA_VERSION,
                        source_snapshot_hash=snapshot_ref.removeprefix("sha256:"),
                        created_at=created_at,
                        extensions={},
                        known_upstream_fact_ids=(),
                    )
                )
        if source_key in {"surgery_record", "mr_surgery", "rescue_record"}:
            emergency_rescue = _explicit_emergency_rescue_state(result.rows)
            if emergency_rescue is not None:
                facts.append(
                    FactV2.create(
                        visit_ref=build_luxian_0609_visit_ref(
                            institute_id=institute_id,
                            patient_id=patient_id,
                            visit_id=visit_id,
                        ),
                        family="surgery_anesthesia",
                        fact_type="current_visit_emergency_rescue_surgery",
                        normalized_value={"emergency_rescue": emergency_rescue},
                        trigger_scope="current_visit",
                        current_visit_relevance="relevant",
                        assertion="affirmed" if emergency_rescue else "negated",
                        assertion_context="other",
                        event_status="performed" if emergency_rescue else "unknown",
                        source_key=source_key,
                        source_document_id="",
                        source_document_type=source_key,
                        record_time=None,
                        submit_time=None,
                        update_time=None,
                        quote="",
                        redaction_terms=(),
                        confidence=1.0,
                        extractor="deterministic",
                        extractor_version="snapshot-provider-emergency-rescue-v1",
                        fact_schema_version=FACT_SCHEMA_VERSION,
                        source_snapshot_hash=snapshot_ref.removeprefix("sha256:"),
                        created_at=created_at,
                        extensions={},
                        known_upstream_fact_ids=(),
                    )
                )
        all_document_refs.extend(refs)
        material_sources[source_key] = result

    if needs_evaluation_horizon:
        horizon_date: date | None = None
        horizon_datetime: datetime | None = None
        horizon_basis = ""
        resolved_horizon_reason = horizon_unavailable_reason or ""
        if (
            evaluation_horizon_policy
            == EVALUATION_HORIZON_POLICY_FROZEN_TASK_DATE
        ):
            horizon_date = explicit_as_of_date
            horizon_basis = "evaluation_as_of"
        elif (
            evaluation_horizon_policy == EVALUATION_HORIZON_POLICY_AUTHORITATIVE_DISCHARGE
            and evaluation_horizon_snapshot is not None
        ):
            horizon_datetime, resolved_horizon_reason = resolve_frozen_discharge_horizon(
                evaluation_horizon_snapshot, institute_id=institute_id,
                patient_id=patient_id, visit_id=visit_id,
            )
            if horizon_datetime is not None:
                horizon_date = horizon_datetime.date()
                horizon_basis = "discharge_date"
        elif evaluation_horizon_policy != EVALUATION_HORIZON_POLICY_DISABLED:
            admission_material = material_sources.get("inpat_registration")
            admission_value = (
                admission_material.rows[0].get("admission_datetime")
                if admission_material is not None and admission_material.rows
                else None
            )
            admission_date = _parse_admission_date(admission_value)
            admission_datetime = _parse_authoritative_datetime(
                admission_value,
                field_name="admission_datetime",
            )
            if "LX0609-02-01-03" in selected_rule_ids:
                from .basic_timeliness_facts import extract_admission_anchor, AdmissionAnchorState
                fallback_material = material_sources.get("admission_record")
                anchor = extract_admission_anchor(
                    registration_rows=admission_material.rows if admission_material else (),
                    admission_rows=fallback_material.rows if fallback_material and not fallback_material.truncated else (),
                    discharge_rows=(), allow_date_fallback=False,
                )
                if anchor.state is AdmissionAnchorState.EXACT:
                    admission_datetime = anchor.anchor_time
                    admission_date = admission_datetime.date()
            discharge_observation = next(
                (
                    item
                    for item in observations
                    if item.source_key == CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY
                ),
                None,
            )
            discharge_material = material_sources.get(
                CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY
            )
            if (
                discharge_observation is not None
                and discharge_observation.query_state is QueryStatus.AVAILABLE
                and discharge_observation.completeness is SourceCompleteness.COMPLETE
                and discharge_material is not None
                and len(discharge_material.rows) == 1
            ):
                discharge_value = discharge_material.rows[0].get("discharge_datetime")
                discharge_date = _parse_discharge_date(discharge_value)
                discharge_datetime = _parse_authoritative_datetime(
                    discharge_value,
                    field_name="discharge_datetime",
                )
                has_time_conflict = (
                    discharge_datetime < admission_datetime
                    if discharge_datetime is not None
                    and admission_datetime is not None
                    else bool(
                        discharge_date is not None
                        and admission_date is not None
                        and discharge_date < admission_date
                    )
                )
                if has_time_conflict:
                    resolved_horizon_reason = "authoritative_time_conflict"
                if not has_time_conflict and discharge_date is not None and (
                    evaluation_horizon_policy
                    == EVALUATION_HORIZON_POLICY_AUTHORITATIVE_DISCHARGE
                    or explicit_as_of_date is None
                    or discharge_date <= explicit_as_of_date
                ):
                    horizon_date = discharge_date
                    horizon_datetime = discharge_datetime
                    horizon_basis = "discharge_date"
                elif (
                    not has_time_conflict
                    and explicit_as_of_date is not None
                    and evaluation_horizon_policy is None
                ):
                    horizon_date = explicit_as_of_date
                    horizon_basis = "evaluation_as_of"
            elif (
                explicit_as_of_date is not None
                and evaluation_horizon_policy is None
            ):
                # 升级前任务保留原有在院日期回退；新任务由显式策略控制。
                horizon_date = explicit_as_of_date
                horizon_basis = "evaluation_as_of"

            if (
                evaluation_horizon_policy
                == EVALUATION_HORIZON_POLICY_AUTHORITATIVE_DISCHARGE
                and horizon_date is None
                and not resolved_horizon_reason
            ):
                resolved_horizon_reason = "authoritative_time_missing"

        horizon_entry = resolve_luxian_0609_physical_source_entry(
            EVALUATION_HORIZON_SOURCE_KEY
        )
        horizon_payload = (
            {
                "horizon_date": horizon_date.isoformat(),
                **(
                    {"horizon_datetime": horizon_datetime.isoformat()}
                    if horizon_datetime is not None
                    else {}
                ),
                "basis": horizon_basis,
                "row_ref": digest_source_evidence(
                    (
                        EVALUATION_HORIZON_SOURCE_KEY,
                        horizon_basis,
                        horizon_date.isoformat(),
                        horizon_datetime.isoformat() if horizon_datetime else "",
                    )
                ),
            }
            if horizon_date is not None
            else None
        )
        horizon_rows = (
            (horizon_payload,)
            if horizon_payload is not None
            else ()
        )
        horizon_material = SnapshotSourceRows.create(
            source_key=EVALUATION_HORIZON_SOURCE_KEY,
            rows=horizon_rows,
            truncated=False,
            limit_rows=1,
        )
        horizon_refs = build_material_document_refs(
            EVALUATION_HORIZON_SOURCE_KEY,
            horizon_material.rows,
        )
        # 派生来源同样须登记进快照文书引用，否则按快照读取该来源会判身份不符，
        # 遍历全部来源的发送前身份核验随之失败，整例模型调用被拒发。
        all_document_refs.extend(horizon_refs)
        horizon_query_state = (
            QueryStatus.AVAILABLE if horizon_rows else QueryStatus.EMPTY
        )
        horizon_snapshot_ref = build_material_snapshot_ref(
            source_key=EVALUATION_HORIZON_SOURCE_KEY,
            query_version=horizon_entry.query_version,
            query_state=horizon_query_state,
            completeness=SourceCompleteness.COMPLETE,
            document_refs=horizon_refs,
        )
        observations.append(
            SourceObservation.create(
                source_key=EVALUATION_HORIZON_SOURCE_KEY,
                query_state=horizon_query_state,
                completeness=SourceCompleteness.COMPLETE,
                record_count=len(horizon_rows),
                query_version=horizon_entry.query_version,
                snapshot_ref=horizon_snapshot_ref,
                reason_code=resolved_horizon_reason,
            )
        )
        material_sources[EVALUATION_HORIZON_SOURCE_KEY] = horizon_material
        if horizon_date is not None:
            facts.append(
                FactV2.create(
                    visit_ref=build_luxian_0609_visit_ref(
                        institute_id=institute_id,
                        patient_id=patient_id,
                        visit_id=visit_id,
                    ),
                    family="course_quality",
                    fact_type="evaluation_horizon",
                    normalized_value={
                        "horizon_date": horizon_date.isoformat(),
                        **(
                            {"horizon_datetime": horizon_datetime.isoformat()}
                            if horizon_datetime is not None
                            else {}
                        ),
                        "basis": horizon_basis,
                    },
                    trigger_scope="current_visit",
                    current_visit_relevance="relevant",
                    assertion="affirmed",
                    assertion_context="other",
                    event_status="unknown",
                    source_key=EVALUATION_HORIZON_SOURCE_KEY,
                    source_document_id="",
                    source_document_type="evaluation_context",
                    record_time=None,
                    submit_time=None,
                    update_time=None,
                    quote="",
                    redaction_terms=(),
                    confidence=1.0,
                    extractor="deterministic",
                    extractor_version="snapshot-provider-evaluation-horizon-v1",
                    fact_schema_version=FACT_SCHEMA_VERSION,
                    source_snapshot_hash=horizon_snapshot_ref.removeprefix("sha256:"),
                    created_at=created_at,
                    extensions={},
                    known_upstream_fact_ids=(),
                )
            )

    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=observations,
        facts=facts,
        document_refs=all_document_refs,
        created_at=created_at,
    )
    return Luxian0609EvidenceReadSession(
        snapshot=snapshot,
        materials=Luxian0609EvidenceMaterialStore.create(
            snapshot=snapshot,
            sources=material_sources,
        ),
    )


def build_luxian_0609_evidence_snapshot(
    *,
    selected_rule_ids: tuple[str, ...],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    created_at: str,
    evaluation_as_of_date: str | None = None,
    evaluation_horizon_policy: str | None = None,
    evaluation_horizon_snapshot: Mapping[str, Any] | None = None,
    horizon_unavailable_reason: str | None = None,
    row_reader: SnapshotRowReader = read_luxian_0609_snapshot_source_rows,
) -> Luxian0609EvidenceSnapshot:
    """兼容安全快照入口；请求内材料由 read-session 入口消费。"""

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema=source_schema,
        created_at=created_at,
        evaluation_as_of_date=evaluation_as_of_date,
        evaluation_horizon_policy=evaluation_horizon_policy,
        evaluation_horizon_snapshot=evaluation_horizon_snapshot,
        horizon_unavailable_reason=horizon_unavailable_reason,
        row_reader=row_reader,
    ).snapshot


__all__ = [
    "SnapshotSourceRows",
    "build_luxian_0609_evidence_read_session",
    "build_luxian_0609_evidence_snapshot",
]
