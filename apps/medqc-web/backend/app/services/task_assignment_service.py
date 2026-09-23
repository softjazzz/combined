"""单事务保存任务病历分配。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update

from ..database.connection import SessionLocal
from ..database.models.qc import QCTask, QCTaskRecord, SysUser
from .auth_store import _normalize_roles


class AssignmentNotFound(LookupError):
    pass


class AssignmentForbidden(PermissionError):
    pass


class AssignmentConflict(ValueError):
    pass


def _has_qc_staff_role(user: dict[str, Any]) -> bool:
    return "qc_staff" in _normalize_roles(user.get("role"), user.get("roles_json"))


def list_qc_assignee_options() -> list[dict[str, str]]:
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")
    with SessionLocal() as session:
        rows = session.execute(
            select(
                SysUser.id, SysUser.display_name, SysUser.department,
                SysUser.role, SysUser.roles_json, SysUser.is_active,
            )
            .where(SysUser.is_active.is_(True))
            .order_by(SysUser.display_name, SysUser.id)
        ).mappings().all()
        return [
            {
                "user_id": row["id"],
                "user_name": str(row["display_name"]).strip(),
                "department": str(row["department"] or "").strip(),
            }
            for row in rows
            if _has_qc_staff_role(row) and str(row["display_name"] or "").strip()
        ]


def assign_task_records(
    *, task_id: str, actor_id: str, assignees: list[dict[str, str]], method: str
) -> dict[str, Any]:
    if method != "by_ratio":
        raise AssignmentConflict("当前仅支持按比例分配")
    if not assignees or any(
        not person.get("user_id", "").strip() or not person.get("user_name", "").strip()
        for person in assignees
    ):
        raise AssignmentConflict("分配人员信息不完整")
    if len({person["user_id"] for person in assignees}) != len(assignees):
        raise AssignmentConflict("分配人员 user_id 不可重复")
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")

    with SessionLocal() as session:
        with session.begin():
            task_row = session.execute(
                select(QCTask.__table__).where(QCTask.id == task_id).with_for_update()
            ).mappings().first()
            if task_row is None:
                raise AssignmentNotFound("任务不存在")
            task = dict(task_row)
            if task.get("creator_id") != actor_id:
                raise AssignmentForbidden("仅任务创建人可分配")
            if task.get("status") not in {"sampling", "assigned"}:
                raise AssignmentConflict("任务状态不允许分配")
            if task.get("assign_method") != method:
                raise AssignmentConflict("任务分配方式与创建配置不一致")

            requested_ids = [person["user_id"] for person in assignees]
            users = {
                row["id"]: dict(row)
                for row in session.execute(
                    select(SysUser.__table__)
                    .where(SysUser.id.in_(requested_ids))
                    .with_for_update()
                ).mappings().all()
            }
            if len(users) != len(requested_ids) or any(
                not users[user_id].get("is_active")
                or not _has_qc_staff_role(users[user_id])
                or not str(users[user_id].get("display_name") or "").strip()
                for user_id in requested_ids
            ):
                raise AssignmentConflict("分配人员不存在、已停用或不是有效质控员")
            verified_assignees = [
                {"user_id": user_id, "user_name": str(users[user_id]["display_name"]).strip()}
                for user_id in requested_ids
            ]

            rows = [dict(row) for row in session.execute(
                select(QCTaskRecord.__table__)
                .where(QCTaskRecord.task_id == task_id)
                .order_by(QCTaskRecord.created_at, QCTaskRecord.id)
                .with_for_update()
            ).mappings().all()]
            try:
                expected = int(task.get("total_records"))
            except (TypeError, ValueError) as exc:
                raise AssignmentConflict("任务抽样数量无效") from exc
            if expected <= 0 or len(rows) != expected:
                raise AssignmentConflict("任务抽样关联与数量不一致")

            scene = task.get("scene")
            if scene is not None and scene not in {"running", "final", "outpatient"}:
                raise AssignmentConflict("任务场景无效")
            modern = scene is not None
            if modern:
                seen: set[tuple[str, str, str]] = set()
                for row in rows:
                    identity = tuple(str(row.get(key) or "").strip() for key in (
                        "institute_id", "patient_id", "visit_id"
                    ))
                    if any(not value or len(value) > 100 for value in identity):
                        raise AssignmentConflict("任务病历缺少完整三坐标")
                    if row["record_id"] != row["id"] or identity in seen:
                        raise AssignmentConflict("任务病历身份不符合三坐标抽样合同")
                    seen.add(identity)

            batch_size, remainder = divmod(len(rows), len(verified_assignees))
            planned: list[tuple[dict[str, Any], dict[str, str]]] = []
            for index, person in enumerate(verified_assignees):
                start = index * batch_size + min(index, remainder)
                count = batch_size + (1 if index < remainder else 0)
                planned.extend((row, person) for row in rows[start:start + count])

            if task["status"] == "assigned":
                if any(
                    row.get("status") != "pending"
                    or row.get("assignee_id") != person["user_id"]
                    or row.get("assignee_name") != person["user_name"]
                    for row, person in planned
                ):
                    raise AssignmentConflict("任务已按不同计划分配")
            else:
                if any(
                    row.get("status") != "pending"
                    or row.get("assignee_id") is not None
                    or row.get("assignee_name") is not None
                    for row in rows
                ):
                    raise AssignmentConflict("任务病历已有分配或状态变化")
                for row, person in planned:
                    updated = session.execute(
                        update(QCTaskRecord.__table__)
                        .where(
                            QCTaskRecord.id == row["id"],
                            QCTaskRecord.task_id == task_id,
                            QCTaskRecord.status == "pending",
                            QCTaskRecord.assignee_id.is_(None),
                            QCTaskRecord.assignee_name.is_(None),
                        )
                        .values(assignee_id=person["user_id"], assignee_name=person["user_name"])
                    )
                    if updated.rowcount != 1:
                        raise RuntimeError("病历分配写入数量不完整")
                updated_task = session.execute(
                    update(QCTask.__table__)
                    .where(QCTask.id == task_id, QCTask.status == "sampling")
                    .values(status="assigned", updated_at=datetime.utcnow())
                )
                if updated_task.rowcount != 1:
                    raise RuntimeError("任务状态更新失败")

            summary: dict[str, int] = {}
            details: list[dict[str, Any]] = []
            for person in verified_assignees:
                count = sum(1 for _, assigned in planned if assigned["user_id"] == person["user_id"])
                summary[person["user_name"]] = summary.get(person["user_name"], 0) + count
                details.append({**person, "count": count})
            return {
                "task_id": task_id,
                "total_assigned": len(planned),
                "assignment_summary": summary,
                "assignment_details": details,
                "idempotent": task["status"] == "assigned",
            }
