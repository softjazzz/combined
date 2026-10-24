"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from sqlalchemy import select

from .record_review_service import (
    _batch_job_table,
)

SOURCE_KEYS = (
    "institute_id",
    "patient_id",
    "visit_id",
    "scene",
    "target_kind",
    "target_id",
    "root_job_id",
    "envelope_id",
)


def source_key(source):
    values = tuple(str(source.get(key) or "").strip() for key in SOURCE_KEYS)
    return values if all(values) else None


def _load_jobs(session, rows):
    ids = sorted(
        {
            row["root_job_id"]
            for row in rows
            if row["source"] == "auto" and row.get("root_job_id")
        }
    )
    if not ids:
        return {}
    table = _batch_job_table()
    jobs = {}
    for start in range(0, len(ids), 500):
        statement = select(
            table.c.id, table.c.scene, table.c.scope, table.c.filters_json
        ).where(
            table.c.id.in_(ids[start : start + 500]),
        )
        jobs.update(
            {row["id"]: row for row in session.execute(statement).mappings().all()}
        )
    return jobs
