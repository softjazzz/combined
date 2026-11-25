"""已保存任务结果的持久提醒；不参与执行判定或 Canonical 结果读取。"""

import json
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import MetaData, Table, and_, exists, inspect, select, update

from ..database import connection as db_connection
from .defect_rectification_service import _effective_persistent_roles
from .user_scope_owner import user_owner_options
from .sample_validation_rule_sets import is_workspace_batch_draft_id

SOURCE = "v5_qc_result_ready"
ROLES = {"admin", "qc_manager", "qc_staff", "sync_admin", "super_admin"}


def _qc_schema(connection) -> str | None:
    if connection.dialect.name == "sqlite":
        return None
    return (
        "qc"
        if str(getattr(db_connection, "DB_SCHEMA_MODE", "") or "").strip().lower()
        == "split"
        else None
    )


def result_tables(session):
    connection = session.connection()
    schema = _qc_schema(connection)
    inspector = inspect(connection)
    names = ("custom_qc_batch_jobs", "luxian_0609_record_result_envelopes")
    if not all(inspector.has_table(name, schema=schema) for name in names):
        return None
    metadata = MetaData()
    tables = tuple(
        Table(name, metadata, schema=schema, autoload_with=connection) for name in names
    )
    required = (
        {"id", "created_by", "status", "parent_job_id", "scene"},
        {
            "id",
            "job_id",
            "root_job_id",
            "created_by",
            "result_count",
            "institute_id",
            "patient_id",
            "visit_id",
        },
    )
    return (
        tables
        if all(keys <= set(table.c.keys()) for table, keys in zip(tables, required))
        else None
    )


def ready_predicate(session, actor, notification):
    if not actor["roles"] & ROLES:
        return False
    tables = result_tables(session)
    if not tables:
        return False
    jobs, envelopes = tables
    conditions = [
        jobs.c.id == notification.record_id,
        jobs.c.created_by == actor["id"],
        jobs.c.status == "completed",
        jobs.c.parent_job_id.is_(None),
        jobs.c.scene.in_(("running", "final")),
        envelopes.c.id == notification.related_id,
        envelopes.c.job_id == jobs.c.id,
        envelopes.c.root_job_id == jobs.c.id,
        envelopes.c.created_by == jobs.c.created_by,
        envelopes.c.result_count > 0,
        *(
            getattr(envelopes.c, key) == getattr(notification, key)
            for key in ("institute_id", "patient_id", "visit_id")
        ),
    ]
    if actor["institute_id"] and "sync_admin" not in actor["roles"]:
        conditions.append(envelopes.c.institute_id == actor["institute_id"])
    elif not actor["roles"] & {"admin", "super_admin"}:
        return False
    return and_(
        notification.source_key == SOURCE,
        notification.identity_version == 1,
        notification.related_type == "qc_result_ready",
        exists(
            select(jobs.c.id)
            .select_from(jobs.join(envelopes, envelopes.c.root_job_id == jobs.c.id))
            .where(*conditions)
        ),
    )


def publish_result_ready(session, *, job_row, jobs, envelopes, now):
    """只由成功写入正式结果的事务调用，叶子子任务不得单独提醒。"""
    if (
        job_row.get("scene") not in {"running", "final"}
        or job_row.get("parent_job_id")
        or not is_workspace_batch_draft_id(job_row.get("draft_id"))
    ):
        return
    from ..database.models.v36_reports import SysUser
    from .doctor_notification_service import Notification

    # 旧版本库仍可执行原任务，但尚未具备现代消息字段时不启用新能力。
    connection = session.connection()
    schema = _qc_schema(connection)
    inspector = inspect(connection)
    if not inspector.has_table("notifications", schema=schema):
        return
    columns = {
        column["name"]
        for column in inspector.get_columns("notifications", schema=schema)
    }
    if (
        not {"identity_version", "source_key", "institute_id", "patient_id", "visit_id"}
        <= columns
    ):
        return
    recipient = session.execute(
        select(SysUser).where(
            SysUser.id == job_row["created_by"], SysUser.is_active.is_(True)
        ),
        execution_options=user_owner_options(session),
    ).scalar_one_or_none()
    if (
        not recipient
        or not _effective_persistent_roles(recipient.role, recipient.roles_json) & ROLES
    ):
        return
    rows = (
        session.execute(
            select(envelopes)
            .where(
                envelopes.c.job_id == job_row["id"],
                envelopes.c.root_job_id == job_row["id"],
                envelopes.c.created_by == recipient.id,
                envelopes.c.result_count > 0,
            )
            .order_by(
                envelopes.c.institute_id, envelopes.c.patient_id, envelopes.c.visit_id
            )
        )
        .mappings()
        .all()
    )
    if not rows or any(
        not all(
            row.get(key)
            for key in (
                "institute_id",
                "patient_id",
                "visit_id",
                "rule_set_key",
                "rule_set_version",
            )
        )
        for row in rows
    ):
        return
    roles = _effective_persistent_roles(recipient.role, recipient.roles_json)
    if recipient.institute_id and "sync_admin" not in roles:
        if any(row["institute_id"] != recipient.institute_id for row in rows):
            return
    elif not roles & {"admin", "super_admin"}:
        return
    # 父任务刷新会重建信封，但不是新执行；重试的启动时刻/执行令牌才是新一轮。
    generation = [
        job_row.get("started_at"),
        job_row.get("filters_json"),
        [row["envelope_json"] for row in rows],
    ]
    if job_row.get("job_kind") == "parent":
        generation.extend(
            tuple(row)
            for row in session.execute(
                select(jobs.c.id, jobs.c.started_at, jobs.c.filters_json)
                .where(jobs.c.parent_job_id == job_row["id"])
                .order_by(jobs.c.id)
            ).all()
        )
    notice_id = str(
        uuid5(
            NAMESPACE_URL,
            f"{SOURCE}:{job_row['id']}:" + json.dumps(generation, default=str),
        )
    )
    first = rows[0]
    values = dict(
        related_id=first["id"],
        institute_id=first["institute_id"],
        patient_id=first["patient_id"],
        visit_id=first["visit_id"],
    )
    existing = session.execute(
        update(Notification)
        .where(
            Notification.id == notice_id,
            Notification.source_key == SOURCE,
            Notification.recipient_id == recipient.id,
        )
        .values(**values)
    )
    if existing.rowcount:
        return
    label = {"running": "运行", "final": "终末"}[job_row["scene"]]
    session.add(
        Notification(
            id=notice_id,
            type="qc_result_ready",
            title=f"{label}质控结果已就绪",
            content=f"{job_row.get('rule_name') or label + '质控任务'} · {len(rows)} 份病历的质控结果已保存。",
            record_id=job_row["id"],
            identity_version=1,
            source_key=SOURCE,
            severity="info",
            recipient_id=recipient.id,
            related_type="qc_result_ready",
            is_read=False,
            created_at=now,
            **values,
        )
    )
