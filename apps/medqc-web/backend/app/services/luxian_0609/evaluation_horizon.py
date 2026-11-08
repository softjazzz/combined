from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Mapping, TYPE_CHECKING

from ..case_identity import CaseRef
from ..discharge_time import DISCHARGE_TIME_POLICY, hospital_business_time

if TYPE_CHECKING:
    from .evidence_material import Luxian0609EvidenceMaterialStore
    from .evidence_snapshot import Luxian0609EvidenceSnapshot


EVALUATION_HORIZON_POLICY_FROZEN_TASK_DATE = "frozen_task_date"
EVALUATION_HORIZON_POLICY_AUTHORITATIVE_DISCHARGE = "authoritative_discharge"
EVALUATION_HORIZON_POLICY_DISABLED = "disabled"
EVALUATION_HORIZON_POLICIES = frozenset(
    {
        EVALUATION_HORIZON_POLICY_FROZEN_TASK_DATE,
        EVALUATION_HORIZON_POLICY_AUTHORITATIVE_DISCHARGE,
        EVALUATION_HORIZON_POLICY_DISABLED,
    }
)
EVALUATION_HORIZON_REASON_AUTHORITATIVE_TIME_MISSING = "authoritative_time_missing"
EVALUATION_HORIZON_REASON_AUTHORITATIVE_TIME_CONFLICT = "authoritative_time_conflict"


def read_frozen_evaluation_horizon(
    *, snapshot: Luxian0609EvidenceSnapshot, materials: Luxian0609EvidenceMaterialStore,
) -> tuple[datetime | date | None, str, str]:
    """保留统一冻结终点的日期/时刻精度，不从当前库或当前时间补值。"""
    from .evidence_material import EvidenceMaterialUnavailable, EvidenceMaterialTruncated
    from .evidence_snapshot import SourceCompleteness
    from .source_manifest import QueryStatus
    key = "evaluation_context.horizon"
    observation = next((item for item in snapshot.observations if item.source_key == key), None)
    if observation is None:
        return None, "", "authoritative_time_missing"
    if observation.query_state is QueryStatus.ERROR:
        return None, "", "source_query_error"
    if observation.completeness is not SourceCompleteness.COMPLETE:
        return None, "", "candidate_scope_incomplete"
    try:
        rows = tuple(row for _, row in materials.document_rows(key, snapshot=snapshot))
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return None, "", "authoritative_time_missing"
    if not rows:
        reason = observation.reason_code
        return None, "", reason if reason in {"authoritative_time_missing", "authoritative_time_conflict"} else "authoritative_time_missing"
    if len(rows) != 1:
        return None, "", "authoritative_time_conflict"
    row = rows[0]
    basis = str(row.get("basis") or "")
    if basis not in {"discharge_date", "evaluation_as_of"}:
        return None, basis, "authoritative_time_missing"
    raw = str(row.get("horizon_datetime") or "")
    raw_date = str(row.get("horizon_date") or "")
    if row.get("time_precision") == "date" or not raw:
        try:
            day = date.fromisoformat(raw_date)
            # 日期有效不表示可以忽略同一冻结行中的矛盾时刻。
            if raw and hospital_business_time(datetime.fromisoformat(raw.replace("Z", "+00:00"))).date() != day:
                return None, basis, "authoritative_time_conflict"
            return day, basis, ""
        except ValueError:
            return None, basis, "authoritative_time_missing"
    try:
        moment = hospital_business_time(datetime.fromisoformat(raw.replace("Z", "+00:00")))
        if ":" not in raw:
            return None, basis, "authoritative_time_missing"
        if raw_date and date.fromisoformat(raw_date) != moment.date():
            return None, basis, "authoritative_time_conflict"
    except (TypeError, ValueError):
        return None, basis, "authoritative_time_missing"
    return moment, basis, ""


def frozen_window_is_mature(horizon: datetime | date, deadline: datetime) -> bool:
    """时刻沿用精确边界；日期只有明确晚于截止日才足以证明窗口完成。"""
    if isinstance(horizon, datetime):
        return horizon >= deadline
    return horizon > deadline.date()


def after_frozen_horizon(moment: datetime, horizon: datetime | date) -> bool:
    """日期级范围内的同日时刻不可被擅自排除。"""
    if isinstance(horizon, datetime):
        return moment > horizon
    return moment.date() > horizon


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _is_date_only(value: Any) -> bool:
    """来源值只有日期（无时分）时，不能把补出的零点当作真实时刻参与先后比较。"""
    text = _normalized_text(value)
    return bool(text) and ":" not in text


def _discharge_before_admission(
    discharge: datetime, admission: datetime, *, discharge_raw: Any, admission_raw: Any,
) -> bool:
    """任一侧只有日期时按自然日比较：同日入出院不构成时间冲突。"""
    if _is_date_only(discharge_raw) or _is_date_only(admission_raw):
        return discharge.date() < admission.date()
    return discharge < admission


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
        precision = "datetime" if ":" in self.discharge_datetime else "date" if self.discharge_datetime else "unknown"
        return {**asdict(self), "discharge_time_precision": precision}


def resolve_record_evaluation_horizon_policy(
    snapshot: Mapping[str, Any] | None,
) -> str | None:
    """将逐病例快照收敛为 Provider 可执行的三态策略。

    ``None`` 仅保留给升级前已排队、没有逐病例快照的兼容任务。
    """

    if snapshot is None:
        return None
    if _normalized_text(snapshot.get("resolution_status")) != "resolved":
        return EVALUATION_HORIZON_POLICY_DISABLED
    basis = _normalized_text(snapshot.get("evaluation_basis"))
    if basis == "task_frozen_date":
        return EVALUATION_HORIZON_POLICY_FROZEN_TASK_DATE
    if basis == "discharge_datetime":
        return EVALUATION_HORIZON_POLICY_AUTHORITATIVE_DISCHARGE
    return EVALUATION_HORIZON_POLICY_DISABLED


def resolve_record_evaluation_horizon_unavailable_reason(
    snapshot: Mapping[str, Any] | None,
) -> str | None:
    """为禁用终点的逐病例快照提供受控缺口原因。"""

    if snapshot is None:
        return None
    status = _normalized_text(snapshot.get("resolution_status"))
    if status == "time_conflict":
        return EVALUATION_HORIZON_REASON_AUTHORITATIVE_TIME_CONFLICT
    if status in {"authoritative_time_missing", "scene_uncertain"}:
        return EVALUATION_HORIZON_REASON_AUTHORITATIVE_TIME_MISSING
    return None


def _frozen_snapshot_case_binding(
    snapshot: Mapping[str, Any],
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
) -> str:
    """复用冻结终点的三坐标/旧 record_id 身份校验。"""

    context = CaseRef(institute_id.strip(), patient_id.strip(), visit_id.strip())
    coordinate_fields = ("institute_id", "patient_id", "visit_id")
    if any(key in snapshot for key in coordinate_fields):
        coordinates = tuple(
            _normalized_text(snapshot.get(key)) for key in coordinate_fields
        )
        if not all(coordinates) or coordinates != tuple(context):
            return "conflict"
    else:
        record_id = _normalized_text(snapshot.get("record_id"))
        if not record_id:
            return "missing"
        if record_id != context.visit_id:
            return "conflict"
    if (
        "record_key" in snapshot
        and _normalized_text(snapshot.get("record_key")) != context.as_key()
    ):
        return "conflict"
    return "match"


def resolve_frozen_running_record_scene(
    snapshot: Mapping[str, Any] | None,
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    expected_horizon_date: date | None,
) -> str:
    """只返回与病例、策略和冻结日一致的 ``running`` 场景。"""

    if not isinstance(snapshot, Mapping) or expected_horizon_date is None:
        return ""
    if (
        _normalized_text(snapshot.get("resolution_status")) != "resolved"
        or _normalized_text(snapshot.get("record_scene")) != "running"
        or _normalized_text(snapshot.get("evaluation_basis")) != "task_frozen_date"
        or _frozen_snapshot_case_binding(
            snapshot,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
        ) != "match"
    ):
        return ""
    try:
        frozen_horizon = date.fromisoformat(
            _normalized_text(snapshot.get("evaluation_horizon"))
        )
    except ValueError:
        return ""
    return "running" if frozen_horizon == expected_horizon_date else ""


def resolve_frozen_discharge_horizon(
    snapshot: Mapping[str, Any], *, institute_id: str, patient_id: str, visit_id: str,
) -> tuple[datetime | date | None, str]:
    """只校验本病例已冻结的 final 终点；失败时不得用执行时资料补值。

    日期级出院返回 ``date``：不得补成“出院日 00:00”精确时刻，否则出院当日的事件会被排除。
    """
    missing = EVALUATION_HORIZON_REASON_AUTHORITATIVE_TIME_MISSING
    conflict = EVALUATION_HORIZON_REASON_AUTHORITATIVE_TIME_CONFLICT
    if not isinstance(snapshot, Mapping):
        return None, missing
    status = _normalized_text(snapshot.get("resolution_status"))
    scene = _normalized_text(snapshot.get("record_scene"))
    basis = _normalized_text(snapshot.get("evaluation_basis"))
    if status == "time_conflict":
        return None, conflict
    if not status or status in {"authoritative_time_missing", "scene_uncertain"} or not scene or not basis:
        return None, missing
    if status != "resolved" or scene != "final" or basis != "discharge_datetime":
        return None, conflict
    binding = _frozen_snapshot_case_binding(
        snapshot,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
    )
    if binding != "match":
        return None, missing if binding == "missing" else conflict
    try:
        admission = _parse_datetime(snapshot.get("admission_datetime"), field_name="admission_datetime")
        discharge = _parse_datetime(snapshot.get("discharge_datetime"), field_name="discharge_datetime")
        horizon = date.fromisoformat(_normalized_text(snapshot.get("evaluation_horizon")))
    except (TypeError, ValueError):
        return None, missing
    if admission is None or discharge is None:
        return None, missing
    discharge_raw = snapshot.get("discharge_datetime")
    try:
        if horizon != discharge.date() or _discharge_before_admission(
            discharge, admission,
            discharge_raw=discharge_raw, admission_raw=snapshot.get("admission_datetime"),
        ):
            return None, conflict
    except TypeError:
        # 混用无时区/有时区时间无法证明先后，不能隐式假设时区。
        return None, conflict
    if _is_date_only(discharge_raw):
        return discharge.date(), ""
    return discharge, ""


def resolve_snapshot_task_frozen_date(snapshot: Mapping[str, Any] | None) -> date | None:
    """读取快照随附的任务冻结日；仅供死后才产生的文书核对时限，不改变病例评价终点。"""
    if not isinstance(snapshot, Mapping):
        return None
    try:
        return date.fromisoformat(_normalized_text(snapshot.get("task_frozen_date")))
    except ValueError:
        return None


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
    admission_time = _parse_datetime(admission_text, field_name="admission_datetime")
    discharge_time = _parse_datetime(discharge_text, field_name="discharge_datetime")
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
    try:
        time_conflict = _discharge_before_admission(
            discharge_time, admission_time,
            discharge_raw=discharge_text, admission_raw=admission_text,
        )
    except TypeError:
        # 与冻结终点读取口径一致：时区信息混用时保留冲突，不隐式补时区或中断建任务。
        time_conflict = True
    if time_conflict:
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
    record_frozen_dates: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    """``record_frozen_dates`` 按 record_key 覆盖冻结日，仅供自建测试病例固定评价时间点。"""
    snapshots = []
    for record in records:
        record_id = _normalized_text(record.get("record_id") or record.get("visit_id"))
        if not record_id:
            continue
        record_ref = CaseRef.from_mapping(record)
        frozen_date = (
            _normalized_text((record_frozen_dates or {}).get(record_ref.as_key()))
            if all(record_ref)
            else ""
        ) or task_frozen_date
        admission_value = record.get("admission_datetime") or record.get("admission_date")
        discharge_value = record.get("discharge_datetime") or record.get("discharge_date")
        # 只归一新建任务的业务时间；历史快照读取器仍严格校验原值，禁止执行时补值。
        def local_value(value):
            try:
                parsed = hospital_business_time(value)
                original = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")) if value else None
                if isinstance(parsed, datetime) and original is not None and original.tzinfo is not None:
                    return parsed.isoformat(sep=" ")
            except (TypeError, ValueError, OverflowError):
                pass
            return value

        if record.get("scope") == "final" and record.get("discharge_horizon_conflict"):
            # 已识别的来源冲突（含非空非法时间）保留原值和原因，不先解析成任务创建异常。
            snapshot = RecordEvaluationHorizon(
                record_id=record_id, record_scene="final",
                admission_datetime=_normalized_text(local_value(admission_value)),
                discharge_datetime=_normalized_text(local_value(discharge_value)),
                evaluation_horizon="", evaluation_basis="", resolution_status="time_conflict",
            ).to_dict()
        else:
            snapshot = resolve_record_evaluation_horizon(
                record_id=record_id,
                record_scene=record.get("scope"),
                admission_datetime=local_value(admission_value),
                discharge_datetime=local_value(discharge_value),
                task_frozen_date=frozen_date,
            ).to_dict()
        if record.get("discharge_horizon_source"):
            snapshot["discharge_horizon_source"] = record["discharge_horizon_source"]
            snapshot["discharge_horizon_policy"] = DISCHARGE_TIME_POLICY
        # 用户决定（2026-10-20）：死亡讨论等死后文书的时限按“死亡时间+7天”与任务冻结日中较早者评价，
        # 已出院病例的终点是出院日，故另随快照保存冻结日。
        if frozen_date:
            snapshot["task_frozen_date"] = frozen_date
        if all(record_ref):
            snapshot.update(
                {
                    **record_ref.as_dict(),
                    "record_key": record_ref.as_key(),
                }
            )
        snapshots.append(snapshot)
    return sorted(
        snapshots,
        key=lambda item: (item.get("record_key") or item["record_id"]),
    )
