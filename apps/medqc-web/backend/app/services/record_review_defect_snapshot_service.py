"""初审时冻结缺陷事实；报表只读校验，不重算历史。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Mapping

from sqlalchemy import select

from ..database.models.qc import QCDefect, QCDefectHistory
from .appeal_manual_target_service import resolve_task_manual_defect_target
from .qc_workspace.canonical_result_store import CanonicalResultStore
from .scoring_service import project_customer_items

SOURCE_KEYS = (
    "job_id", "envelope_id", "institute_id", "patient_id", "visit_id",
    "rule_set_key", "rule_set_version", "scene",
)


class DefectSnapshotInvalid(ValueError):
    """缺陷快照或其冻结来源不完整。"""


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def validate_snapshot(snapshot: Any, *, source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """校验完整快照，失败抛错；返回原始字典，不补历史或修改事实。"""
    if not isinstance(snapshot, dict) or type(snapshot.get("schema_version")) is not int:
        raise DefectSnapshotInvalid("缺陷快照格式无效")
    frozen = snapshot.get("source")
    if (snapshot["schema_version"] != 1 or snapshot.get("complete") is not True
            or not isinstance(frozen, dict) or any(not _text(frozen.get(k)) for k in SOURCE_KEYS)
            or frozen["scene"] not in {"running", "final", "outpatient_emergency"}):
        raise DefectSnapshotInvalid("缺陷快照来源无效")
    if source is not None and any(source.get(k) != frozen[k] for k in SOURCE_KEYS):
        raise DefectSnapshotInvalid("缺陷快照与审核来源不一致")
    try:
        if not isinstance(snapshot.get("captured_at"), str):
            raise ValueError()
        captured = datetime.fromisoformat(snapshot["captured_at"].replace("Z", "+00:00"))
        if captured.tzinfo is None:
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise DefectSnapshotInvalid("缺陷快照时间无效") from exc
    if source is not None and source.get("created_at") is not None:
        expected = source["created_at"]
        if not isinstance(expected, datetime):
            raise DefectSnapshotInvalid("审核事件时间无效")
        expected_utc = expected.astimezone(timezone.utc).replace(tzinfo=None) if expected.tzinfo else expected
        if captured.astimezone(timezone.utc).replace(tzinfo=None) != expected_utc:
            raise DefectSnapshotInvalid("缺陷快照时间与审核事件不一致")
    for kind, keys in (("auto", ("defect_id", "rule_id")),
                       ("manual", ("defect_id", "created_by", "creation_history_id", "approval_history_id"))):
        group = snapshot.get(kind)
        if (not isinstance(group, dict) or type(group.get("count")) is not int
                or not isinstance(group.get("items"), list) or group["count"] != len(group["items"])):
            raise DefectSnapshotInvalid("缺陷快照数量无效")
        ids = set()
        for item in group["items"]:
            if not isinstance(item, dict) or any(not _text(item.get(k)) for k in keys):
                raise DefectSnapshotInvalid("缺陷快照条目无效")
            if item["defect_id"] in ids or (kind == "auto" and item["defect_id"] != item["rule_id"]):
                raise DefectSnapshotInvalid("缺陷快照条目身份冲突")
            ids.add(item["defect_id"])
    return snapshot


def capture_snapshot(session: Any, *, source: Mapping[str, Any], captured_at: datetime,
                     envelope_table: Any, batch_job_table_factory: Any) -> dict[str, Any]:
    """在审核事务与病例锁内读取所选Envelope及人工来源。"""
    try:
        rows = session.execute(select(envelope_table).where(
            envelope_table.c.id == source["envelope_id"],
        ).with_for_update(read=True)).mappings().all()
        if len(rows) != 1:
            raise DefectSnapshotInvalid("审核结果信封缺失或不唯一")
        row = rows[0]
        if any(row.get(k) != source[k] for k in SOURCE_KEYS if k not in {"job_id", "envelope_id", "scene"}) or row.get("root_job_id") != source["job_id"]:
            raise DefectSnapshotInvalid("审核结果信封来源不一致")
        if source["rule_set_key"].startswith("sc_content_") and source["scene"] == "final":
            from .sc_final_task_review_envelope_service import load_items

            projected = load_items(row, source=dict(source))
            raw = projected
            envelope_id = row["id"]
        else:
            payload, envelope_id = CanonicalResultStore(envelope_table).load_selected_with_id(
                session, root_job_id=source["job_id"],
                **{k: source[k] for k in ("institute_id", "patient_id", "visit_id", "rule_set_key", "rule_set_version")},
            )
            raw = payload.get("items")
            projected = project_customer_items(raw) if isinstance(raw, list) else None
        if envelope_id != source["envelope_id"] or not isinstance(raw, list) or not raw or type(row.get("result_count")) is not int or row["result_count"] != len(raw):
            raise DefectSnapshotInvalid("审核结果信封内容无效")
        raw_ids = [item.get("rule_id") if isinstance(item, dict) else None for item in raw]
        if any(not _text(item) for item in raw_ids) or len(set(raw_ids)) != len(raw_ids):
            raise DefectSnapshotInvalid("质控规则身份缺失或重复")
        if not isinstance(projected, list) or len(projected) != len(raw):
            raise DefectSnapshotInvalid("质控条目投影不完整")
        auto = []
        for original, item in zip(raw, projected):
            if not isinstance(item, dict) or item.get("rule_id") != original["rule_id"] or type(item.get("is_confirmed_issue")) is not bool:
                raise DefectSnapshotInvalid("质控条目投影身份无效")
            if item["is_confirmed_issue"] is True:
                auto.append({"defect_id": original["rule_id"], "rule_id": original["rule_id"]})
        manual = []
        from .manual_defect_review_service import _manual_scope

        # 现代人工来源范围内先核实来源，不能把损坏的旧轮条目静默当作零。
        defects = session.execute(select(QCDefect).where(
            *_manual_scope(), QCDefect.institute_id == source["institute_id"],
            QCDefect.patient_id == source["patient_id"], QCDefect.visit_id == source["visit_id"],
        ).with_for_update()).scalars().all()
        def factory():
            return SimpleNamespace(_batch_job_table=batch_job_table_factory())
        for defect in defects:
            target = resolve_task_manual_defect_target(defect_id=defect.id, workspace_factory=factory, session=session, lock=True)
            if any(target.get("root_job_id" if k == "job_id" else k) != source[k] for k in SOURCE_KEYS):
                continue  # 完整解析已证明这是其他结果对象。
            if defect.manual_review_status != "approved":
                continue
            histories = session.execute(select(QCDefectHistory).where(
                QCDefectHistory.defect_id == defect.id,
                QCDefectHistory.action.in_(("manual_create", "manual_review_approved", "manual_review_rejected")),
            ).with_for_update(read=True)).scalars().all()
            creation = [h for h in histories if h.action == "manual_create"]
            approval = [h for h in histories if h.action == "manual_review_approved"]
            if len(creation) != 1 or len(approval) != 1 or len(histories) != 2:
                raise DefectSnapshotInvalid("人工缺陷审核历史不唯一")
            create, approve = creation[0], approval[0]
            creation_details = json.loads(create.details)
            details = json.loads(approve.details)
            if (create.actor_id != defect.manual_created_by or not _text(approve.actor_id)
                    or not isinstance(creation_details, dict)
                    or creation_details.get("envelope_id") != source["envelope_id"]
                    or not isinstance(details, dict) or details.get("from_status") != "pending"
                    or details.get("to_status") != "approved" or details.get("reviewer") != approve.actor_id
                    or create.created_at is None or approve.created_at is None
                    or not create.created_at <= approve.created_at <= captured_at):
                raise DefectSnapshotInvalid("人工缺陷审核时点不明确")
            manual.append({"defect_id": defect.id, "created_by": defect.manual_created_by,
                           "creation_history_id": create.id, "approval_history_id": approve.id})
        snapshot = {"schema_version": 1, "complete": True,
                    "captured_at": captured_at.replace(tzinfo=timezone.utc).isoformat(), "source": dict(source),
                    "auto": {"count": len(auto), "items": auto}, "manual": {"count": len(manual), "items": manual}}
        return validate_snapshot(snapshot, source=source)
    except DefectSnapshotInvalid:
        raise
    except Exception as exc:
        raise DefectSnapshotInvalid("缺陷来源读取失败，审核未提交") from exc
