"""合成 PG 任务夹具和固定执行结果；只供隔离验收，不是生产执行入口。"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app.database.connection import engine, SessionLocal
from app.services.custom_qc_workspace_service import (
    CustomQCWorkspaceService, _batch_jobs_table, _drafts_table, _record_result_envelopes_table,
)
from app.services.luxian_0609_result_schema import RULE_SET_VERSION
from app.services.qc_dispatch.outbox import qc_dispatch_tables
from app.services.qc_dispatch.repository import create_qc_dispatch_repository
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore
from tests.luxian_0609_published_result_support import ADMISSION_TIMELINESS_RULE_ID, published_lx0609_items


PROBE = sa.Table(
    "qc_infra_probe", sa.MetaData(), sa.Column("job_id", sa.String(36), primary_key=True),
    sa.Column("stage", sa.String(40)), sa.Column("executions", sa.Integer, nullable=False),
    sa.Column("attempt", sa.Text),
)


def _owner_tables(schema: str | None) -> tuple[sa.Table, ...]:
    """返回合成 055 owner；只构造元数据，不执行生产运行时 DDL。"""

    return tuple(
        owner.to_metadata(sa.MetaData(), schema=schema)
        for owner in (
            _drafts_table(readonly=True),
            _batch_jobs_table(readonly=True),
            _record_result_envelopes_table(),
        )
    )


def bootstrap() -> None:
    """在新建 PG 实际执行增量 DDL；不 stamp，不冒充历史全链升级。"""
    root = Path(__file__).resolve().parents[2]
    original = os.environ.get("DB_SCHEMA_MODE")
    try:
        for schema in (None, "qc"):
            with engine.begin() as connection:
                if schema:
                    connection.execute(sa.text("CREATE SCHEMA IF NOT EXISTS qc"))
                for owner in _owner_tables(schema):
                    owner.create(connection, checkfirst=True)
                os.environ["DB_SCHEMA_MODE"] = "split" if schema else "single"
                with Operations.context(MigrationContext.configure(connection)):
                    for filename in ("20261030_000056_qc_dispatch_outbox.py",
                                     "20261030_000057_qc_outbox_archive.py"):
                        spec = importlib.util.spec_from_file_location(
                            "synthetic_migration", root / "alembic" / "versions" / filename
                        )
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        module.upgrade()
        PROBE.create(engine, checkfirst=True)
    finally:
        if original is None:
            os.environ.pop("DB_SCHEMA_MODE", None)
        else:
            os.environ["DB_SCHEMA_MODE"] = original


def runtime():
    return create_qc_dispatch_repository(), CustomQCWorkspaceService(readonly=True)


def reset_owned_tables() -> None:
    """每例清空本轮 public/qc owner；不 DROP schema、不触碰其他数据库。"""

    with engine.begin() as connection:
        public_repo, public_workspace = runtime()
        public_tables = (
            public_repo.archive_table,
            public_repo.outbox_table,
            public_repo.dispatch_table,
            PROBE,
            public_workspace._record_result_envelope_table,
            public_workspace._batch_job_table,
            public_workspace._draft_table,
        )
        split_dispatch = qc_dispatch_tables(schema="qc")
        split_draft, split_jobs, split_envelopes = _owner_tables("qc")
        split_tables = (
            split_dispatch.archive,
            split_dispatch.outbox,
            split_dispatch.dispatch,
            split_envelopes,
            split_jobs,
            split_draft,
        )
        for table in (*public_tables, *split_tables):
            connection.execute(table.delete())


def close_runtime_connections() -> None:
    """释放当前 pytest/actor 的 PG pool；下次访问会重新建立白名单连接。"""

    engine.dispose()


def new_job() -> tuple[str, str]:
    _repo, workspace = runtime()
    job = workspace.create_batch_job(
        draft={"id": "synthetic-rule-library", "rule_code": "LX0609", "name": "synthetic", "scene": "final"},
        created_by="synthetic-infra", scope="final",
        filters={"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": RULE_SET_VERSION,
                 "rule_ids": [ADMISSION_TIMELINESS_RULE_ID],
                 "record_refs": [{"institute_id": "synthetic-institute", "patient_id": "synthetic-patient",
                                  "visit_id": "synthetic-visit"}]},
        record_ids=["synthetic-visit"], total_records=1,
    )
    with SessionLocal.begin() as session:
        session.execute(PROBE.insert().values(job_id=job["id"], stage="created", executions=0))
    return job["id"], uuid.uuid4().hex


def marker(job_id, stage, *, attempt=None, increment=False):
    with SessionLocal.begin() as session:
        values = {"stage": stage}
        if attempt is not None:
            values["attempt"] = attempt
        if increment:
            values["executions"] = PROBE.c.executions + 1
        session.execute(PROBE.update().where(PROBE.c.job_id == job_id).values(**values))


def probe(job_id):
    with SessionLocal() as session:
        return dict(session.execute(sa.select(PROBE).where(PROBE.c.job_id == job_id)).mappings().one())


def fixed_item():
    return {**published_lx0609_items()[ADMISSION_TIMELINESS_RULE_ID],
            "institute_id": "synthetic-institute", "patient_id": "synthetic-patient",
            "visit_id": "synthetic-visit", "record_id": "synthetic-visit"}


def complete(workspace, job_id, attempt, item):
    return workspace.complete_batch_job(
        job_id=job_id, attempt_filters_json=attempt,
        summary={"execution_status": "completed", "total_records": 1, "success_count": 1,
                 "failed_count": 0, "issue_records": 0, "compliant_records": 1,
                 "total_tokens": 0, "total_processing_time": 0.0},
        items=[item], failed_records=[],
    )


def outbox_rows(job_id: str | None = None) -> list[dict]:
    repo, _workspace = runtime()
    statement = sa.select(repo.outbox_table)
    if job_id is not None:
        statement = statement.where(repo.outbox_table.c.job_id == job_id)
    with SessionLocal() as session:
        return [dict(row) for row in session.execute(statement).mappings().all()]


def archive_rows(job_id: str | None = None) -> list[dict]:
    repo, _workspace = runtime()
    statement = sa.select(repo.archive_table)
    if job_id is not None:
        statement = statement.where(repo.archive_table.c.job_id == job_id)
    with SessionLocal() as session:
        return [dict(row) for row in session.execute(statement).mappings().all()]


def envelope_count(job_id: str) -> int:
    _repo, workspace = runtime()
    with SessionLocal() as session:
        return int(session.execute(
            sa.select(sa.func.count())
            .select_from(workspace._record_result_envelope_table)
            .where(workspace._record_result_envelope_table.c.job_id == job_id)
        ).scalar_one())


def canonical(job_id):
    _repo, workspace = runtime()
    with SessionLocal() as session:
        return CanonicalResultStore(workspace._record_result_envelope_table).load_selected(
            session, root_job_id=job_id, institute_id="synthetic-institute",
            patient_id="synthetic-patient", visit_id="synthetic-visit",
            rule_set_key="luxian_0609_qc_v1", rule_set_version=RULE_SET_VERSION,
        )
