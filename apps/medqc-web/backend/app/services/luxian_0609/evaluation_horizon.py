from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _parse_datetime(value: Any, *, field_name: str) -> datetime | None:
    text = _normalized_text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(normalized), datetime.min.time())
        except ValueError:
            raise ValueError(f"{field_name} must be a valid ISO date or datetime") from None


@dataclass(frozen=True)
class RecordEvaluationHorizon:
    """任务创建时冻结的逐病例评价终点；不承担规则状态判定。"""

    record_id: str
    record_scene: str
    admission_datetime: str
    discharge_datetime: str
    evaluation_horizon: str
    evaluation_basis: str
    resolution_status: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def resolve_record_evaluation_horizon(
    *,
    record_id: str,
    record_scene: str,
    admission_datetime: Any,
    discharge_datetime: Any,
    task_frozen_date: str,
) -> RecordEvaluationHorizon:
    normalized_record_id = _normalized_text(record_id)
    if not normalized_record_id:
        raise ValueError("record_id must not be empty")
    frozen_date = date.fromisoformat(_normalized_text(task_frozen_date))
    normalized_scene = _normalized_text(record_scene).lower()
    if normalized_scene not in {"running", "final"}:
        normalized_scene = "unknown"

    admission_text = _normalized_text(admission_datetime)
    discharge_text = _normalized_text(discharge_datetime)
    admission_time = _parse_datetime(admission_text, field_name="admission_datetime")
    discharge_time = _parse_datetime(discharge_text, field_name="discharge_datetime")

    if normalized_scene == "running":
        return RecordEvaluationHorizon(
            record_id=normalized_record_id,
            record_scene=normalized_scene,
            admission_datetime=admission_text,
            discharge_datetime=discharge_text,
            evaluation_horizon=frozen_date.isoformat(),
            evaluation_basis="task_frozen_date",
            resolution_status="resolved",
        )
    if normalized_scene == "unknown":
        return RecordEvaluationHorizon(
            record_id=normalized_record_id,
            record_scene=normalized_scene,
            admission_datetime=admission_text,
            discharge_datetime=discharge_text,
            evaluation_horizon="",
            evaluation_basis="",
            resolution_status="scene_uncertain",
        )
    if admission_time is None or discharge_time is None:
        return RecordEvaluationHorizon(
            record_id=normalized_record_id,
            record_scene=normalized_scene,
            admission_datetime=admission_text,
            discharge_datetime=discharge_text,
            evaluation_horizon="",
            evaluation_basis="",
            resolution_status="authoritative_time_missing",
        )
    if discharge_time < admission_time:
        return RecordEvaluationHorizon(
            record_id=normalized_record_id,
            record_scene=normalized_scene,
            admission_datetime=admission_text,
            discharge_datetime=discharge_text,
            evaluation_horizon="",
            evaluation_basis="",
            resolution_status="time_conflict",
        )
    return RecordEvaluationHorizon(
        record_id=normalized_record_id,
        record_scene=normalized_scene,
        admission_datetime=admission_text,
        discharge_datetime=discharge_text,
        evaluation_horizon=discharge_time.date().isoformat(),
        evaluation_basis="discharge_datetime",
        resolution_status="resolved",
    )


def build_record_evaluation_horizon_snapshot(
    records: list[dict[str, Any]],
    *,
    task_frozen_date: str,
) -> list[dict[str, str]]:
    snapshots = []
    for record in records:
        record_id = _normalized_text(record.get("record_id") or record.get("visit_id"))
        if not record_id:
            continue
        snapshots.append(
            resolve_record_evaluation_horizon(
                record_id=record_id,
                record_scene=record.get("scope"),
                admission_datetime=(
                    record.get("admission_datetime") or record.get("admission_date")
                ),
                discharge_datetime=(
                    record.get("discharge_datetime") or record.get("discharge_date")
                ),
                task_frozen_date=task_frozen_date,
            ).to_dict()
        )
    return sorted(snapshots, key=lambda item: item["record_id"])
