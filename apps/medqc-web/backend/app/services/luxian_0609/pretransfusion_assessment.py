from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Mapping


AssessmentOutcome = tuple[str, str, Mapping[str, Any]]

INDICATOR_FIELDS = (
    "hemoglobin",
    "hematocrit",
    "rbc",
    "prothrombin_time",
    "partial_thromboplastin_time",
    "fibrinogen",
    "albumin",
    "teg",
    "platelet_antibody",
    "rbc_antibody",
)
_EMPTY_VALUES = {"", "-", "--", "无", "未查", "未检测", "不详"}
_APPLICATION_TEXT_FIELDS = ("record_content", "content", "assembled_text", "raw_text")
_NUMBER = r"\d+(?:\.\d+)?"
_TEXT_INDICATOR_PATTERNS = (
    ("hemoglobin", re.compile(rf"(?:血红蛋白|HGB|Hb)\s*[:：=]?\s*{_NUMBER}\s*(?:g/L|g\/l)?", re.I)),
    ("hematocrit", re.compile(rf"(?:红细胞压积|HCT)\s*[:：=]?\s*{_NUMBER}\s*%?", re.I)),
    ("rbc", re.compile(rf"(?:红细胞计数|RBC)\s*[:：=]?\s*{_NUMBER}", re.I)),
    ("prothrombin_time", re.compile(rf"(?:凝血酶原时间|PT)\s*[:：=]?\s*{_NUMBER}\s*(?:s|秒)?", re.I)),
    ("partial_thromboplastin_time", re.compile(rf"(?:活化部分凝血活酶时间|APTT)\s*[:：=]?\s*{_NUMBER}\s*(?:s|秒)?", re.I)),
    ("fibrinogen", re.compile(rf"(?:纤维蛋白原|FIB)\s*[:：=]?\s*{_NUMBER}", re.I)),
    ("albumin", re.compile(rf"(?:白蛋白|ALB)\s*[:：=]?\s*{_NUMBER}\s*(?:g/L|g\/l)?", re.I)),
    ("teg", re.compile(rf"(?:血栓弹力图|TEG)\s*[:：=]?\s*{_NUMBER}", re.I)),
    ("platelet_antibody", re.compile(r"(?:血小板抗体)\s*[:：=]?\s*(?:阳性|阴性|\+|-)")),
    ("rbc_antibody", re.compile(r"(?:红细胞抗体|不规则抗体)\s*[:：=]?\s*(?:阳性|阴性|\+|-)")),
)


@dataclass(frozen=True)
class PretransfusionReasonCandidate:
    application_ref: str
    application_text: str
    application_time: datetime
    transfusion_time: datetime
    indicators: tuple[str, ...]
    source_document_refs: tuple[tuple[str, str], ...]

    def display_facts(self, *, reason_present: bool) -> dict[str, Any]:
        facts = {
            "performed_transfusion_confirmed": True,
            "checked_fields": ["application_reason", "laboratory_indicator"],
            "missing_fields": [] if reason_present else ["application_reason"],
            "assessment_indicators": list(self.indicators),
            "application_time": self.application_time.isoformat(sep=" "),
            "transfusion_time": self.transfusion_time.isoformat(sep=" "),
            "source_document_refs": [
                {"source_type": source_type, "source_document_id": document_id}
                for source_type, document_id in self.source_document_refs
            ],
        }
        facts[
            "verification_kind" if reason_present else "failure_kind"
        ] = (
            "pretransfusion_assessment_complete"
            if reason_present
            else "pretransfusion_assessment_incomplete"
        )
        return facts


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed


def _rows(documents: Mapping[str, Any], source_key: str) -> list[Mapping[str, Any]]:
    raw = documents.get(source_key)
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, Mapping)]


def _event_time(row: Mapping[str, Any]) -> datetime | None:
    for field in (
        "transfution_datetime",
        "transfusion_datetime",
        "start_time",
        "transfusion_start_time",
        "record_time",
    ):
        if (parsed := _datetime(row.get(field))) is not None:
            return parsed
    return None


def _application_text(row: Mapping[str, Any]) -> str:
    return _text(next((row.get(field) for field in _APPLICATION_TEXT_FIELDS if _text(row.get(field))), ""))


def _indicators(row: Mapping[str, Any]) -> list[str]:
    found = {
        field for field in INDICATOR_FIELDS if _text(row.get(field)) not in _EMPTY_VALUES
    }
    content = _application_text(row)
    found.update(field for field, pattern in _TEXT_INDICATOR_PATTERNS if pattern.search(content))
    return [field for field in INDICATOR_FIELDS if field in found]


def _source_document_refs(
    *,
    application: Mapping[str, Any],
    transfusion_records: list[Mapping[str, Any]],
    transfusion_time: datetime,
) -> tuple[tuple[str, str], ...]:
    refs: list[tuple[str, str]] = []
    application_id = _text(application.get("application_id") or application.get("document_id"))
    if application_id:
        refs.append(("blood_application", application_id))
    located_records = [
        (row, _text(row.get("document_id")), _event_time(row))
        for row in transfusion_records
        if _text(row.get("document_id"))
    ]
    if located_records:
        _selected_row, document_id, _record_time = min(
            located_records,
            key=lambda item: (
                item[2] is None,
                abs((item[2] - transfusion_time).total_seconds())
                if item[2] is not None
                else float("inf"),
                item[1],
            ),
        )
        refs.append(("bloodtrans_record", document_id))
    return tuple(refs)


def _structured_applications(documents: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in _rows(documents, "blood_application")
        if any(
            field in row
            for field in ("reason_for_blood", "transfusion_reason", *INDICATOR_FIELDS)
        )
    ]


def has_structured_pretransfusion_application(documents: Mapping[str, Any]) -> bool:
    """是否存在结构化输血申请单（只有这条路径需要实际输血时间作时序比较）。"""

    return bool(_structured_applications(documents))


def evaluate_structured_pretransfusion_application(
    documents: Mapping[str, Any],
) -> AssessmentOutcome | None:
    """按输血申请单结构化事实核对 LX0609-07-01-02；非结构化旧资料交还调用方。"""

    applications = _structured_applications(documents)
    if not applications:
        return None

    event_rows = _rows(documents, "mr_bloodtrans")
    event_times = sorted(
        {value for row in event_rows if (value := _event_time(row)) is not None}
    )
    if not event_times or len(event_times) != len(event_rows):
        return (
            "data_gap",
            "authoritative_time_missing",
            {
                "failure_kind": "pretransfusion_assessment_time_unavailable",
                "performed_transfusion_confirmed": True,
                "checked_fields": [],
                "missing_fields": [],
                "missing_time_fields": ["transfusion_time"],
            },
        )

    transfusion_time = event_times[0]
    transfusion_records = _rows(documents, "bloodtrans_record")
    evaluated = []
    for row in applications:
        application_time = _datetime(
            row.get("request_datetime") or row.get("request_time")
        )
        evaluated.append(
            {
                "application_time": application_time,
                "reason_present": bool(
                    _text(row.get("reason_for_blood") or row.get("transfusion_reason"))
                ),
                "indicators": _indicators(row),
                "source_document_refs": _source_document_refs(
                    application=row,
                    transfusion_records=transfusion_records,
                    transfusion_time=transfusion_time,
                ),
            }
        )

    timely = [
        item
        for item in evaluated
        if item["application_time"] is not None
        and item["application_time"] < transfusion_time
    ]
    complete = [
        item for item in timely if item["reason_present"] and item["indicators"]
    ]
    if complete:
        selected = max(complete, key=lambda item: item["application_time"])
        return _outcome(
            status="compliant",
            reason_code="pretransfusion_assessment_complete",
            kind_key="verification_kind",
            selected=selected,
            transfusion_time=transfusion_time,
        )

    late_complete = [
        item
        for item in evaluated
        if item["application_time"] is not None
        and item["application_time"] >= transfusion_time
        and item["reason_present"]
        and item["indicators"]
    ]
    if late_complete:
        selected = min(late_complete, key=lambda item: item["application_time"])
        outcome = _outcome(
            status="non_compliant",
            reason_code="pretransfusion_assessment_time_conflict",
            kind_key="failure_kind",
            selected=selected,
            transfusion_time=transfusion_time,
        )
        facts = dict(outcome[2])
        facts["elapsed_minutes"] = round(
            (selected["application_time"] - transfusion_time).total_seconds() / 60
        )
        return outcome[0], outcome[1], facts

    if not timely and any(item["application_time"] is None for item in evaluated):
        return (
            "data_gap",
            "authoritative_time_missing",
            {
                "failure_kind": "pretransfusion_assessment_time_unavailable",
                "performed_transfusion_confirmed": True,
                "checked_fields": [],
                "missing_fields": [],
                "missing_time_fields": ["application_time"],
                "transfusion_time": transfusion_time.isoformat(sep=" "),
            },
        )

    selected = (
        max(timely, key=lambda item: item["application_time"])
        if timely
        else evaluated[0]
    )
    return _outcome(
        status="non_compliant",
        reason_code="pretransfusion_assessment_incomplete",
        kind_key="failure_kind",
        selected=selected,
        transfusion_time=transfusion_time,
    )


def build_pretransfusion_reason_candidate(
    documents: Mapping[str, Any],
) -> PretransfusionReasonCandidate | None:
    """只为“指标已确定、申请理由待语义确认”的及时申请单生成单次模型输入。"""

    event_rows = _rows(documents, "mr_bloodtrans")
    event_times = sorted(
        {value for row in event_rows if (value := _event_time(row)) is not None}
    )
    if not event_times or len(event_times) != len(event_rows):
        return None
    transfusion_time = event_times[0]
    transfusion_records = _rows(documents, "bloodtrans_record")
    candidates: list[PretransfusionReasonCandidate] = []
    for index, row in enumerate(_rows(documents, "blood_application"), start=1):
        application_time = _datetime(row.get("request_datetime") or row.get("request_time"))
        application_text = _application_text(row)
        reason_present = bool(
            _text(row.get("reason_for_blood") or row.get("transfusion_reason"))
        )
        indicators = tuple(_indicators(row))
        if (
            application_time is None
            or application_time >= transfusion_time
            or reason_present
            or not indicators
            or not application_text
        ):
            continue
        candidates.append(
            PretransfusionReasonCandidate(
                application_ref=(
                    _text(row.get("application_id") or row.get("document_id"))
                    or f"blood_application-{index}"
                ),
                application_text=application_text[:1200],
                application_time=application_time,
                transfusion_time=transfusion_time,
                indicators=indicators,
                source_document_refs=_source_document_refs(
                    application=row,
                    transfusion_records=transfusion_records,
                    transfusion_time=transfusion_time,
                ),
            )
        )
    return max(candidates, key=lambda item: item.application_time) if candidates else None


def _outcome(
    *,
    status: str,
    reason_code: str,
    kind_key: str,
    selected: Mapping[str, Any],
    transfusion_time: datetime,
) -> AssessmentOutcome:
    missing_fields = []
    if not selected["reason_present"]:
        missing_fields.append("application_reason")
    if not selected["indicators"]:
        missing_fields.append("laboratory_indicator")
    application_time = selected["application_time"]
    return (
        status,
        reason_code,
        {
            kind_key: reason_code,
            "performed_transfusion_confirmed": True,
            "checked_fields": ["application_reason", "laboratory_indicator"],
            "missing_fields": missing_fields,
            "assessment_indicators": selected["indicators"],
            "application_time": (
                application_time.isoformat(sep=" ")
                if application_time is not None
                else None
            ),
            "transfusion_time": transfusion_time.isoformat(sep=" "),
            "source_document_refs": [
                {"source_type": source_type, "source_document_id": document_id}
                for source_type, document_id in selected.get(
                    "source_document_refs", ()
                )
            ],
        },
    )
