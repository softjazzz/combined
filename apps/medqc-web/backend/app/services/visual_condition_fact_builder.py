from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .visual_condition_service import document_types


_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class VisualFact:
    known: bool
    value: Any = None
    evidence: str = ""


class VisualFactSourceUnavailable(RuntimeError):
    pass


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _aware_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    # 现有 programmatic_timeline 的 CDM 时间为医院本地 naive 值；显式绑定
    # Asia/Shanghai，不能依赖应用服务器时区。带 offset 的值统一到同一基准。
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=_HOSPITAL_TIMEZONE)
    return parsed.astimezone(_HOSPITAL_TIMEZONE)


def _timeline(medical_record: Mapping[str, Any]) -> dict[str, Any]:
    evidence_payload = _mapping(medical_record.get("evidence_payload"))
    return _mapping(evidence_payload.get("programmatic_timeline"))


def build_visual_condition_facts(
    medical_record: Mapping[str, Any],
    *,
    required_fact_keys: set[str] | None = None,
) -> dict[str, VisualFact]:
    """只从服务端 programmatic_timeline 构造事实，不读取客户端正文或展示字段。"""
    evidence_error = str(medical_record.get("visual_evidence_error") or "").strip()
    if evidence_error:
        raise VisualFactSourceUnavailable(evidence_error)
    timeline = _timeline(medical_record)
    result: dict[str, VisualFact] = {}
    required = set(required_fact_keys or ())
    if "record.department" in required:
        identity = tuple(
            str(medical_record.get(key) or "").strip()
            for key in ("institute_id", "patient_id", "visit_id")
        )
        department = ""
        if not all(identity):
            result["record.department"] = VisualFact(known=False)
        else:
            try:
                from .medical_records.query_service import load_scoring_departments

                department = str(load_scoring_departments([identity]).get(identity) or "").strip()
            except Exception as exc:
                raise VisualFactSourceUnavailable("department_source_unavailable") from exc
            result["record.department"] = VisualFact(
                known=bool(department),
                value=department or None,
                evidence="medical_records.query_service.load_scoring_departments" if department else "",
            )
    if not timeline:
        return result
    if (
        {"record.admission_datetime", "record.discharge_datetime"} & required
        and timeline.get("registration_source_readiness") == "unavailable"
    ):
        raise VisualFactSourceUnavailable("registration_source_unavailable")
    admission = _aware_datetime(timeline.get("admission_time"))
    admission_trusted = timeline.get("admission_time_trusted") is True
    result["record.admission_datetime"] = VisualFact(
        known=bool(admission and admission_trusted),
        value=admission if admission and admission_trusted else None,
        evidence=str(timeline.get("admission_time_basis") or ""),
    )
    discharge = _aware_datetime(timeline.get("discharge_time"))
    result["record.discharge_datetime"] = VisualFact(
        known=bool(discharge and timeline.get("discharge_time_trusted") is True),
        value=discharge if discharge and timeline.get("discharge_time_trusted") is True else None,
        evidence=(
            "programmatic_timeline.discharge_time"
            if discharge and timeline.get("discharge_time_trusted") is True
            else ""
        ),
    )

    documents = _mapping(timeline.get("documents"))
    source_readiness = _mapping(timeline.get("source_readiness"))
    for document_type in document_types():
        source_table = document_type["value"]
        source_required = any(
            key == f"document.{source_table}.exists"
            or key.startswith(f"document.{source_table}.")
            for key in required
        )
        if source_required and source_readiness.get(source_table) == "unavailable":
            raise VisualFactSourceUnavailable(f"document_source_unavailable:{source_table}")
        raw_items = documents.get(source_table)
        if not isinstance(raw_items, list):
            raw_items = []
        items = [dict(item) for item in raw_items if isinstance(item, Mapping)]
        source_complete = source_readiness.get(source_table) == "complete"
        presence_known = bool(items) or source_complete
        result[f"document.{source_table}.exists"] = VisualFact(
            known=presence_known,
            value=bool(items) if presence_known else None,
            evidence=f"programmatic_timeline.documents.{source_table}",
        )
        authored_values = [
            _aware_datetime(item.get("visual_record_time"))
            if item.get("visual_record_time_trusted") is True
            else None
            for item in items
        ]
        extrema_known = source_complete and bool(items) and all(authored_values)
        authored = sorted(item for item in authored_values if item is not None) if extrema_known else []
        result[f"document.{source_table}.earliest_authored_at"] = VisualFact(
            known=bool(authored),
            value=authored[0] if authored else None,
            evidence=f"{source_table}.authored_at.earliest" if authored else "",
        )
        result[f"document.{source_table}.latest_authored_at"] = VisualFact(
            known=bool(authored),
            value=authored[-1] if authored else None,
            evidence=f"{source_table}.authored_at.latest" if authored else "",
        )
    return result
