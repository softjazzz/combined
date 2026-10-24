"""真实专属PG：正式保存结果、持久账号、整改HTTP与报表同一事件链。"""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
import sqlalchemy as sa
from app.core.security import get_current_user
from app.database import connection
from app.database.models.v36_reports import DefectRectification as Task
from app.database.models.v36_reports import SysUser
from app.routers import defect_rectifications as api
from app.services import custom_qc_workspace_service as workspace
from app.services import record_quality_report_service as quality
from app.services import user_scope_owner
from app.services.defect_rectification_service import (
    DefectRectificationService,
    RectificationError,
)
from app.services.luxian_0609.basic_timeliness_customer_projection import (
    safe_basic_timeliness_customer_display_facts,
)
from app.services.record_remediation_report_service import build_analysis
from fastapi import FastAPI
from fastapi.testclient import TestClient
from scripts.bootstrap_pr8_empty_database import initialize
from sqlalchemy.orm import sessionmaker
from test_report_alembic_upgrade import snapshot

pytest_plugins = ("test_report_migration_compatibility",)
IDENTITY = {
    "institute_id": "SYN-FEEDBACK",
    "patient_id": "synthetic-patient",
    "visit_id": "synthetic-visit",
}
RULE = "LX0609-01-01-01"


@pytest.fixture
def feedback(raw_pg, monkeypatch):
    initialize(raw_pg.url.database)
    engine = sa.create_engine(
        raw_pg.url, connect_args={"options": "-csearch_path=qc,sys,cdm,public,legacy"}
    )
    sessions = sessionmaker(engine)
    monkeypatch.setattr(workspace, "engine", engine)
    monkeypatch.setattr(workspace, "DB_SCHEMA_MODE", "split")
    monkeypatch.setattr(workspace, "SessionLocal", sessions)
    monkeypatch.setattr(connection, "SessionLocal", sessions)
    monkeypatch.setattr(user_scope_owner, "DB_SEARCH_PATH", "qc,sys,cdm,public,legacy")
    workspace._record_result_envelopes_table.cache_clear()
    with engine.begin() as conn:
        # 原workspace表由历史runtime owner管理，不在1–51空库迁移完整性声明内。
        # 夹具显式准备既有owner的qc表；反馈生产路径始终readonly，不允许自动DDL。
        for table in (
            workspace._drafts_table(readonly=True),
            workspace._batch_jobs_table(readonly=True),
            workspace._record_result_envelopes_table(),
        ):
            table.create(conn, checkfirst=True)
        users = SysUser.__table__.to_metadata(sa.MetaData(), schema="sys")
        for identifier, role, hospital in (
            ("qc", "qc_manager", IDENTITY["institute_id"]),
            ("doc", "doctor", IDENTITY["institute_id"]),
            ("other", "doctor", IDENTITY["institute_id"]),
            ("cross", "qc_manager", "SYN-OTHER"),
        ):
            conn.execute(
                users.insert().values(
                    id=identifier,
                    username=identifier,
                    display_name=identifier,
                    role=role,
                    institute_id=hospital,
                    department="合成内科",
                    is_active=True,
                )
            )
        mr = sa.Table("mr", sa.MetaData(), schema="cdm", autoload_with=conn)
        conn.execute(
            mr.insert().values(
                **IDENTITY, name="合成病例", discharge_dept_name="合成内科"
            )
        )
    saved = workspace.CustomQCWorkspaceService(readonly=True)
    job = saved.create_batch_job(
        draft={
            "id": "sichuan-rule-library",
            "rule_code": "SC-BATCH",
            "name": "合成反馈闭环",
            "scene": "running",
        },
        created_by="qc",
        scope="running",
        filters={
            "rule_set_key": workspace.LUXIAN_0609_RULE_SET_KEY,
            "rule_set_version": workspace.RULE_SET_VERSION,
            "rule_ids": [RULE],
            "scoped_customer_rule_ids": [RULE],
        },
        record_ids=[IDENTITY["visit_id"]],
        record_refs=[IDENTITY],
        total_records=1,
        rule_count=1,
    )
    attempt = saved.mark_batch_job_running(job_id=job["id"])
    item = {
        **IDENTITY,
        "record_id": IDENTITY["visit_id"],
        "schema_version": "lx0609-customer-result-v2",
        "rule_id": RULE,
        "status": "non_compliant",
        "result_status": "non_compliant",
        "display_status": "non_compliant",
        "is_compliant": False,
        "reason_code": "timeliness_requirement_not_met",
        "conclusion": "合成入院记录超时",
        "suggestion": "请核对合成文书时限",
        "customer_display_facts": {
            "failure_kind": "timeliness_requirement_not_met",
            "target_document": "admission_record",
            "source_label": "入院记录",
            "timeliness_state": "late",
            "threshold_hours": 24,
            "elapsed_hours": 25.0,
        },
    }
    item["customer_display_facts"] = safe_basic_timeliness_customer_display_facts(
        rule_id=RULE, raw=item["customer_display_facts"]
    )
    assert saved.complete_batch_job(
        job_id=job["id"],
        items=[item],
        failed_records=[],
        attempt_filters_json=attempt,
        summary={
            "execution_status": "completed",
            "total_records": 1,
            "success_count": 1,
            "failed_count": 0,
        },
    )
    # 本测试的正文快照源为显式合成夹具；真实CDM抓取另验，不声称临床整改证明。
    document = {
        "documents": [
            {
                "execution_domain": "admission",
                "doc_type": "admission_record",
                "document_id": "synthetic-document",
                "content": "合成整改正文",
            }
        ],
        "domain_projection": {
            "domains": {
                "admission": {"per_source": {"admission_record": {"has_more": False}}}
            }
        },
    }
    service = DefectRectificationService(sessions, document_loader=lambda **_: document)
    monkeypatch.setattr(api, "service", service)
    app = FastAPI()
    app.include_router(api.router)
    # HTTP认证解析不在此用例范围；业务服务仍必须读取上述真实持久账号，不信任角色声明。
    actor = {"id": "qc", "roles": ["admin"]}
    app.dependency_overrides[get_current_user] = lambda: actor
    with TestClient(app) as client:
        yield engine, sessions, saved, service, client, actor, job
    engine.dispose()
    workspace._record_result_envelopes_table.cache_clear()


def test_saved_result_to_rectification_and_report_with_real_pg(feedback, monkeypatch):
    engine, sessions, saved, service, http, actor, job = feedback
    with engine.connect() as conn:
        before = snapshot(conn)
    response = http.get(
        "/api/v1/defect-rectifications/candidates",
        params={**IDENTITY, "expected_job_id": job["id"]},
    )
    assert response.status_code == 200, response.text
    candidates = response.json()["data"]
    assert {row["id"] for row in candidates["doctors"]} == {"doc", "other"}
    assert len(candidates["targets"]) == 1
    target = {
        key: value for key, value in candidates["targets"][0].items() if key != "label"
    }
    request = {
        **IDENTITY,
        **target,
        "assignee_id": "doc",
        "requirement": "请核实合成记录并提交整改说明",
    }
    bad = http.post(
        "/api/v1/defect-rectifications", json={**request, "envelope_id": "old-envelope"}
    )
    assert bad.status_code == 409
    created = http.post("/api/v1/defect-rectifications", json=request)
    assert created.status_code == 200, created.text
    task = created.json()["data"]
    assert http.post("/api/v1/defect-rectifications", json=request).status_code == 409

    def act(user, version, action, expected=200):
        actor["id"] = user
        response = http.post(
            f"/api/v1/defect-rectifications/{task['id']}/actions",
            json={
                "version": version,
                "action": action,
                "comment": "这是合成验收中足够长的处理说明",
            },
        )
        assert response.status_code == expected, response.text
        return response.json().get("data")

    act("other", 1, "submit", 403)
    actor["id"] = "cross"
    assert http.get(f"/api/v1/defect-rectifications/{task['id']}").status_code == 403
    assert http.get("/api/v1/defect-rectifications").json()["data"]["total"] == 0
    act("qc", 1, "urge")
    act("doc", 1, "submit", 409)
    act("doc", 2, "submit")
    act("qc", 3, "reject")
    act("doc", 4, "submit")
    with monkeypatch.context() as scoped:
        scoped.setattr(
            service,
            "_event",
            lambda *a, **k: (_ for _ in ()).throw(
                RuntimeError("synthetic event failure")
            ),
        )
        act("qc", 5, "approve", 503)
    with sessions() as session:
        row = session.get(Task, task["id"])
        assert (row.status, row.version) == ("submitted", 5)

    def approve():
        try:
            service.transition(
                "qc",
                task["id"],
                version=5,
                action="approve",
                comment="并发验收仅允许一次生效的说明",
            )
            return 200
        except RectificationError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: approve(), range(2)))
    assert sorted(results) == [200, 409]
    act("qc", 5, "approve", 409)
    actor["id"] = "doc"
    detail = http.get(f"/api/v1/defect-rectifications/{task['id']}").json()["data"]
    assert [event["action"] for event in detail["events"]] == [
        "assign",
        "urge",
        "submit",
        "reject",
        "submit",
        "approve",
    ]
    assert (
        http.get("/api/v1/defect-rectifications?state=pending").json()["data"]["total"]
        == 0
    )
    assert "dispatch_document_snapshot" not in detail

    # 结果仍由正式Canonical owner读取；仅将固定病例范围/无人工缺陷作为本测试夹具。
    raw = saved.build_luxian_0609_completed_record_result_summaries(
        record_refs=[IDENTITY], include_items=True, include_rule_set_context=True
    )
    context = quality.build_report_context(
        scene="running",
        actor_id="qc",
        scope_loader=lambda **_: [
            {**IDENTITY, "patient_name": "合成病例", "department": "合成内科"}
        ],
        results_loader=lambda refs: raw,
        review_loader=lambda anchors: {},
        manual_loader=lambda ids: [],
        standard_loader=lambda scene: None,
    )
    analysis = build_analysis(
        context, actor_id="qc", sessions=sessions, manual_loader=lambda *args: []
    )
    assert analysis["rows"][0]["rectification_state"] == "approved"
    # 第二次提交前此前催办已被第一次提交回应，因此本轮验收属于无有效催办。
    assert analysis["rows"][0]["labels"] == ["self_rectified"]
    assert analysis["rows"][0]["appeals"] == []
    with engine.connect() as conn:
        after = snapshot(conn)
    for key, old in before.items():
        assert old["columns"] == after[key]["columns"]
        assert old["indexes"] == after[key]["indexes"]
        assert old["constraints"] == after[key]["constraints"]
        if key not in {
            ("qc", "qc_defect_rectifications"),
            ("qc", "qc_defect_rectification_events"),
        }:
            assert old["rows"] == after[key]["rows"], key
    print(
        json.dumps(
            {
                "from_saved_result": True,
                "events": 6,
                "event_failure_rolled_back": True,
                "report_state": "approved",
                "protected_tables": len(before) - 2,
            }
        )
    )
