"""隔离 SQLite + 正式质控路由的合成 HTTP 验收服务。

仅供本机页面读回测试；不加载客户数据库，也不产生医学验收结论。
从 backend 目录运行：py -3.10 -m uvicorn
scripts.acceptance.lx0609_live_http_fixture:app --host 127.0.0.1 --port 8001
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy import Column, DateTime, MetaData, String, Table, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.routers import qc_sichuan
import app.services.custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.luxian_0609.basic_timeliness_customer_projection import (
    safe_basic_timeliness_customer_display_facts,
)
from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609_result_schema import RULE_SET_VERSION
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore,
    envelope_item_from_rule_result,
)


RULE_ID = "LX0609-09-01-01"
RECORD_REF = {
    "institute_id": "inst-1",
    "patient_id": "patient-1",
    "visit_id": "visit-1",
}
JOB_ID = "job-live-http-004"
USER_ID = "acceptance-admin"
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
metadata = MetaData()
canonical_table = workspace_module._record_result_envelopes_table().to_metadata(
    metadata, schema=None,
)
batch_table = Table(
    "custom_qc_batch_jobs",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("status", String(20)),
    Column("parent_job_id", String(64)),
    Column("created_at", DateTime),
    Column("finished_at", DateTime),
)
metadata.create_all(engine)

facts = safe_basic_timeliness_customer_display_facts(
    rule_id=RULE_ID,
    raw={
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "rescue_record",
        "source_label": "抢救记录",
        "timeliness_state": "within",
        "threshold_hours": 6,
        "elapsed_hours": 5,
    },
)
assert facts is not None
item = {
    "record_id": RECORD_REF["visit_id"],
    **RECORD_REF,
    "schema_version": "lx0609-customer-result-v2",
    "rule_id": RULE_ID,
    "rule_name": "抢救记录：及时完成",
    "status": "compliant",
    "result_status": "compliant",
    "display_status": "compliant",
    "is_compliant": True,
    "reason_code": "requirement_satisfied",
    "conclusion": "合成004结果：抢救记录已在时限内完成。",
    "suggestion": "合成004建议：无需补充。",
    "customer_display_facts": facts,
}
now = datetime(2026, 9, 25, 10, 0, 0)
with Session(engine) as session:
    session.execute(batch_table.insert().values(
        id=JOB_ID,
        status="completed",
        parent_job_id=None,
        created_at=now,
        finished_at=now,
    ))
    CanonicalResultStore(canonical_table).replace_for_job(
        session,
        job_row={
            "id": JOB_ID,
            "created_by": USER_ID,
            "filters_json": json.dumps({
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "rule_set_version": RULE_SET_VERSION,
                "scoped_customer_rule_ids": [RULE_ID],
            }),
        },
        items=[item],
        now=now,
        projector=lambda value: envelope_item_from_rule_result(
            value, hmac_key="synthetic-live-http-key",
        ),
        projection_key="synthetic-live-http-key",
    )
    session.commit()

service = object.__new__(CustomQCWorkspaceService)
service._record_result_envelope_table = canonical_table
service._batch_job_table = batch_table
service._aggregate_parent_job = lambda _session, job: job
workspace_module._session = lambda: Session(engine)
workspace_module._row_to_batch_job = lambda row: {
    **dict(row),
    "record_ids": [RECORD_REF["visit_id"]],
    "filters": {
        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
    },
}

detail_job = {
    "id": JOB_ID,
    "draft_id": "sichuan-rule-library",
    "created_by": USER_ID,
    "status": "completed",
    "total_records": 1,
    "filters": {
        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
        "record_refs": [RECORD_REF],
    },
    # 旧任务项故意与 Canonical 冲突，验证详情不会使用它。
    "items": [{"rule_id": "LX0609-99-99-99", "status": "non_compliant"}],
}
service.get_batch_job = lambda *, job_id, created_by: (
    detail_job if job_id == JOB_ID and created_by == USER_ID else None
)
service._load_batch_job_canonical_items = lambda *, job, allow_partial=False: (
    CanonicalResultStore(canonical_table).load_root_job_items(
        job=job,
        session_factory=lambda: Session(engine),
        allow_partial=allow_partial,
    )
)
service.get_latest_luxian_0609_record_result = lambda **kwargs: (
    service.build_latest_single_record_result_dto(
        **kwargs,
        expected_rule_ids=[RULE_ID],
    )
)
qc_sichuan._sichuan_workspace_service = lambda: service

app = FastAPI()
app.include_router(qc_sichuan.router)
app.dependency_overrides[get_current_user] = lambda: {
    "id": USER_ID,
    "roles": ["admin"],
}


@app.get("/api/v1/auth/me")
def auth_me() -> dict[str, object]:
    return {"id": USER_ID, "display_name": "合成验收", "roles": ["admin"]}


@app.get("/api/medical-records/workstation")
def workstation_records() -> dict[str, object]:
    return {"data": {
        "records": [{
            "id": "synthetic-record",
            "record_key": "synthetic-record-ref",
            **RECORD_REF,
            "name": "合成病例",
            "department": "合成科室",
            "hospitalization_status": "inpatient",
            "admission_date": "2026-09-20",
            "latest_qc_summary": {
                "status": "ready",
                "completed_at": "2026-09-25T10:00:00+08:00",
                "total_rule_count": 1,
                "status_counts": {"compliant": 1},
            },
        }],
        "total": 1,
        "page": 1,
        "qc_summary": {
            "total_records": 1,
            "ready_records": 1,
            "status_counts": {"compliant": 1},
        },
    }}


@app.get("/api/{path:path}")
def unrelated_read(path: str) -> dict[str, object]:
    del path
    return {"success": True, "data": {}}
