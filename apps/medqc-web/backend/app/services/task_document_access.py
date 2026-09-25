"""按受领任务和病例三坐标授权已保存文书读取。"""

from sqlalchemy import String, column, select, table

from ..database.connection import SessionLocal


class TaskDocumentAccessDenied(PermissionError):
    pass


_TASKS = table(
    "qc_tasks",
    column("id", String),
    column("status", String),
)
_RECORDS = table(
    "qc_task_records",
    column("id", String),
    column("task_id", String),
    column("record_id", String),
    column("assignee_id", String),
    column("institute_id", String),
    column("patient_id", String),
    column("visit_id", String),
)


def require_assigned_task_document(
    *,
    task_id: str,
    task_record_id: str,
    actor_id: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
) -> None:
    values = (task_id, task_record_id, actor_id, institute_id, patient_id, visit_id)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise TaskDocumentAccessDenied("当前病历不在受领任务范围")
    if len(actor_id) > 64 or any(len(value) > 100 for value in values[3:]):
        raise TaskDocumentAccessDenied("当前病历不在受领任务范围")
    if SessionLocal is None:
        raise RuntimeError("数据库会话不可用")

    statement = (
        select(_RECORDS.c.id)
        .join(_TASKS, _TASKS.c.id == _RECORDS.c.task_id)
        .where(
            _TASKS.c.id == task_id,
            _TASKS.c.status.in_(("assigned", "in_progress", "completed")),
            _RECORDS.c.id == task_record_id,
            _RECORDS.c.task_id == task_id,
            _RECORDS.c.record_id == task_record_id,
            _RECORDS.c.assignee_id == actor_id,
            _RECORDS.c.institute_id == institute_id,
            _RECORDS.c.patient_id == patient_id,
            _RECORDS.c.visit_id == visit_id,
        )
    )
    with SessionLocal() as session:
        found = session.execute(statement).scalar_one_or_none()
    if found is None:
        raise TaskDocumentAccessDenied("当前病历不在受领任务范围")
