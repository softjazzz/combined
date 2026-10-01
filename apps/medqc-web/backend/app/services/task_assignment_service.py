"""单事务保存任务病历分配。

支持三种方式（合同 docs/plans/2026-09-27-v36-task-assignment-strategies-design.md）：
- by_ratio：按 created_at, id 顺序平均切分；已分配时按同一计划做幂等校验（行为保持不变）；
- by_original_reviewer：取同一三坐标在 qc_record_reviews 中最近一次决定的 reviewer_id；
- by_department：病历科室（抽样时持久化）与受领人 sys_users.department 精确相等。
三种方式共用任务行锁、受领人校验、三坐标校验与逐行 CAS 写入，只有“计划生成”不同。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, update

from ..database.connection import SessionLocal
from ..database.models.qc import QCRecordReview, QCTask, QCTaskRecord, SysUser
from .auth_store import _normalize_roles

SUPPORTED_ASSIGN_METHODS = frozenset({"by_ratio", "by_original_reviewer", "by_department"})
ORIGINAL_REVIEWER_FALLBACKS = frozenset({"by_ratio", "reject"})
REASON_KEYS = ("original_reviewer", "department", "ratio_fallback")
_REVIEW_LOOKUP_CHUNK = 500

# 计划项：(任务病历行, 受领人, 获得途径)
PlanItem = tuple[dict[str, Any], dict[str, str], str]


class AssignmentNotFound(LookupError):
    pass


class AssignmentForbidden(PermissionError):
    pass


class AssignmentConflict(ValueError):
    """分配冲突；带 code 的冲突由路由输出结构化 409 detail。"""

    def __init__(self, message: str, *, code: str | None = None, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


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


def _row_identity(row: dict[str, Any]) -> tuple[str, str, str] | None:
    institute_id, patient_id, visit_id = (
        str(row.get(key) or "").strip() for key in ("institute_id", "patient_id", "visit_id")
    )
    if not (institute_id and patient_id and visit_id):
        return None
    return institute_id, patient_id, visit_id


def _row_department(row: dict[str, Any]) -> str:
    return str(row.get("department") or "").strip()


def _split_by_ratio(
    rows: list[dict[str, Any]], assignees: list[dict[str, str]], reason: str
) -> list[PlanItem]:
    """现有按比例切分算法：按给定顺序平均切分，余数依次给靠前的人。"""
    batch_size, remainder = divmod(len(rows), len(assignees))
    planned: list[PlanItem] = []
    for index, person in enumerate(assignees):
        start = index * batch_size + min(index, remainder)
        count = batch_size + (1 if index < remainder else 0)
        planned.extend((row, person, reason) for row in rows[start:start + count])
    return planned


def _latest_reviewers(session, rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], str]:
    """按三坐标取最近一次审核决定（created_at desc, id desc）的 reviewer_id；按 visit_id 分块批量查询。"""
    identities = {identity for row in rows if (identity := _row_identity(row)) is not None}
    visit_ids = sorted({identity[2] for identity in identities})
    latest: dict[tuple[str, str, str], tuple[tuple[Any, str], str]] = {}
    for start in range(0, len(visit_ids), _REVIEW_LOOKUP_CHUNK):
        chunk = visit_ids[start:start + _REVIEW_LOOKUP_CHUNK]
        reviews = session.execute(
            select(
                QCRecordReview.institute_id, QCRecordReview.patient_id, QCRecordReview.visit_id,
                QCRecordReview.reviewer_id, QCRecordReview.created_at, QCRecordReview.id,
            ).where(QCRecordReview.visit_id.in_(chunk))
        ).all()
        for review in reviews:
            identity = (review.institute_id, review.patient_id, review.visit_id)
            if identity not in identities:
                continue
            order_key = (review.created_at, review.id)
            current = latest.get(identity)
            if current is None or order_key > current[0]:
                latest[identity] = (order_key, str(review.reviewer_id or "").strip())
    return {identity: reviewer for identity, (_, reviewer) in latest.items() if reviewer}


def load_latest_task_reviewers(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], str]:
    """抽样与原质控员分配共用最近审核人 owner 及三坐标、排序合同。"""
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")
    with SessionLocal() as session:
        return _latest_reviewers(session, rows)


def _plan_by_original_reviewer(
    rows: list[dict[str, Any]],
    assignees: list[dict[str, str]],
    latest_reviewers: dict[tuple[str, str, str], str],
    fallback: str,
) -> list[PlanItem]:
    by_id = {person["user_id"]: person for person in assignees}
    planned: list[PlanItem] = []
    unmatched: list[dict[str, Any]] = []
    for row in rows:
        identity = _row_identity(row)
        reviewer = latest_reviewers.get(identity) if identity else None
        person = by_id.get(reviewer) if reviewer else None
        if person is None:
            unmatched.append(row)
        else:
            planned.append((row, person, "original_reviewer"))
    if unmatched:
        if fallback == "reject":
            raise AssignmentConflict(
                f"{len(unmatched)} 条病历无原质控员或原质控员不在选定人员中",
                code="original_reviewer_unmatched",
                unmatched_count=len(unmatched),
            )
        planned.extend(_split_by_ratio(unmatched, assignees, "ratio_fallback"))
    return planned


def _plan_by_department(
    rows: list[dict[str, Any]], assignees: list[dict[str, str]], user_departments: dict[str, str]
) -> list[PlanItem]:
    missing = sum(1 for row in rows if not _row_department(row))
    if missing:
        raise AssignmentConflict(
            f"{missing} 条病历缺少科室，无法按科室分配",
            code="department_missing",
            missing_count=missing,
        )
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(_row_department(row), []).append(row)
    staff: dict[str, list[dict[str, str]]] = {}
    for person in assignees:
        department = user_departments.get(person["user_id"], "")
        if department:
            staff.setdefault(department, []).append(person)
    unassigned = sorted(department for department in groups if department not in staff)
    if unassigned:
        raise AssignmentConflict(
            f"以下科室没有对应受领人：{'、'.join(unassigned)}",
            code="department_unassigned",
            departments=unassigned,
        )
    planned: list[PlanItem] = []
    for department, department_rows in groups.items():
        planned.extend(_split_by_ratio(department_rows, staff[department], "department"))
    return planned


def _stored_fallback(task: dict[str, Any]) -> Any:
    config = task.get("assignee_config")
    if isinstance(config, str):
        try:
            config = json.loads(config) if config.strip() else {}
        except ValueError as exc:
            raise AssignmentConflict("任务分配配置无效") from exc
    if config is None:
        return None
    if not isinstance(config, dict):
        raise AssignmentConflict("任务分配配置无效")
    return config.get("fallback")


def _existing_assignment(
    rows: list[dict[str, Any]], assignees: list[dict[str, str]], method: str
) -> dict[str, Any]:
    """已分配任务按已写入结果汇总，不重新计算（审核数据可能已变化）。"""
    order = [person["user_id"] for person in assignees]
    requested_names = {person["user_id"]: person["user_name"] for person in assignees}
    names: dict[str, str] = {}
    counts: dict[str, int] = {}
    for row in rows:
        user_id, user_name = row.get("assignee_id"), row.get("assignee_name")
        if not user_id or not user_name:
            raise AssignmentConflict("任务已分配但存在未分配病历")
        if user_id not in counts:
            counts[user_id] = 0
            names[user_id] = user_name
            if user_id not in order:
                order.append(user_id)
        counts[user_id] += 1
    summary: dict[str, int] = {}
    details: list[dict[str, Any]] = []
    for user_id in order:
        name = names.get(user_id) or requested_names[user_id]
        count = counts.get(user_id, 0)
        summary[name] = summary.get(name, 0) + count
        # 获得途径未持久化：按科室分配全部来自科室；原质控员方式重放时来源分布未知，不伪造。
        reason_counts = (
            {**dict.fromkeys(REASON_KEYS, 0), "department": count} if method == "by_department" else None
        )
        details.append({"user_id": user_id, "user_name": name, "count": count, "reason_counts": reason_counts})
    return {"summary": summary, "details": details, "total": len(rows)}


def assign_task_records(
    *,
    task_id: str,
    actor_id: str,
    assignees: list[dict[str, str]],
    method: str,
    fallback: str | None = None,
) -> dict[str, Any]:
    if method not in SUPPORTED_ASSIGN_METHODS:
        raise AssignmentConflict("不支持的分配方式")
    if method == "by_original_reviewer":
        if fallback not in ORIGINAL_REVIEWER_FALLBACKS:
            raise AssignmentConflict("按原质控员分配须指定 fallback（by_ratio 或 reject）")
    elif fallback is not None:
        raise AssignmentConflict("fallback 仅适用于按原质控员分配")
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
            if method == "by_original_reviewer":
                stored_fallback = _stored_fallback(task)
                if stored_fallback is not None and stored_fallback != fallback:
                    raise AssignmentConflict("fallback 与任务创建配置不一致")

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

            if method != "by_ratio" and task["status"] == "assigned":
                existing = _existing_assignment(rows, verified_assignees, method)
                return {
                    "task_id": task_id,
                    "total_assigned": existing["total"],
                    "assignment_summary": existing["summary"],
                    "assignment_details": existing["details"],
                    "idempotent": True,
                }

            planned: list[PlanItem]
            if method == "by_ratio":
                planned = _split_by_ratio(rows, verified_assignees, "ratio")
            elif method == "by_original_reviewer":
                planned = _plan_by_original_reviewer(
                    rows, verified_assignees, _latest_reviewers(session, rows), str(fallback)
                )
            else:
                planned = _plan_by_department(rows, verified_assignees, {
                    user_id: str(users[user_id].get("department") or "").strip()
                    for user_id in requested_ids
                })
            if len(planned) != len(rows) or len({row["id"] for row, _, _ in planned}) != len(rows):
                raise RuntimeError("分配计划未覆盖全部任务病历")

            if task["status"] == "assigned":
                if any(
                    row.get("status") != "pending"
                    or row.get("assignee_id") != person["user_id"]
                    or row.get("assignee_name") != person["user_name"]
                    for row, person, _ in planned
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
                for row, person, _ in planned:
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
                reasons = [reason for _, assigned, reason in planned if assigned["user_id"] == person["user_id"]]
                count = len(reasons)
                summary[person["user_name"]] = summary.get(person["user_name"], 0) + count
                detail: dict[str, Any] = {**person, "count": count}
                if method != "by_ratio":
                    # by_ratio 响应保持原样；新方法按人统计获得途径。
                    detail["reason_counts"] = {key: reasons.count(key) for key in REASON_KEYS}
                details.append(detail)
            return {
                "task_id": task_id,
                "total_assigned": len(planned),
                "assignment_summary": summary,
                "assignment_details": details,
                "idempotent": task["status"] == "assigned",
            }
