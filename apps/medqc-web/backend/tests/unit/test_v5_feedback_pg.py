"""真实专属PG：正式保存结果、持久账号、整改HTTP与报表同一事件链。"""

import csv
import io
import json
import secrets
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
import sqlalchemy as sa
from app.core.security import get_password_hash
from app.database import connection
from app.database.models.v36_reports import DefectRectification as Task
from app.database.models.v36_reports import SysUser
from app.routers import auth, notifications, quality_reports
from app.routers import defect_rectifications as api
from app.services import (
    auth_store,
    custom_qc_sample_pool_service as sample_pools,
    manual_defect_review_service,
    record_review_service,
    rule_set_version_service,
    scoring_standard_service,
    user_scope_owner,
)
from app.services import custom_qc_workspace_service as workspace
from app.services import record_quality_report_service as quality
from app.services import record_remediation_report_service as remediation
from app.services.bundles import assembly, frontpage_view
from app.services.defect_rectification_service import (
    DefectRectificationService,
    RectificationError,
)
from app.services.doctor_notification_service import DoctorNotificationService
from app.services.case_identity import CaseRef
from app.services.luxian_0609.basic_timeliness_customer_projection import (
    safe_basic_timeliness_customer_display_facts,
)
from app.services.medical_records import query_service
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


def test_bundle_inventory_isolated_by_full_case_identity(feedback, monkeypatch):
    engine, *_ = feedback
    monkeypatch.setattr(sample_pools, "engine", engine)
    first = CaseRef("SYN-A", "P", "V")
    second = CaseRef("SYN-B", "P", "V")
    third = CaseRef("SYN-A", "OTHER-P", "V")
    with engine.begin() as connection:
        for name in ("running_record_bundle", "final_record_bundle"):
            table = sa.Table(name, sa.MetaData(),
                             sa.Column("institute_id", sa.Text), sa.Column("patient_id", sa.Text),
                             sa.Column("visit_id", sa.Text), sa.Column("structured_context", sa.Text),
                             schema="public")
            table.create(connection)
            if name == "final_record_bundle":
                connection.execute(table.insert(), [
                    {**ref.as_dict(), "structured_context": json.dumps({"document_inventory": [
                        {"source_table": source}
                    ]})}
                    for ref, source in ((first, "surgery_record"), (second, "discharge_record"),
                                        (third, "consultation_record"))
                ])
    service = sample_pools.CustomQCSamplePoolService.__new__(sample_pools.CustomQCSamplePoolService)
    sources = service._load_bundle_source_table_map(case_refs=[first, second])
    assert sources == {first: {"surgery_record"}, second: {"discharge_record"}}
    items = [{**{f"matched_{key}": value for key, value in ref.as_dict().items()},
              "coverage_type": "llm_intrinsic", "manual_issue_text": "", "candidate_rule_ids": []}
             for ref in (first, second, third)]
    enriched = service._apply_dynamic_candidate_rule_ids(items=items, source_table_map=sources)
    assert "SC-093" in enriched[0]["candidate_rule_ids"]
    assert "SC-118" in enriched[1]["candidate_rule_ids"]
    assert "SC-093" not in enriched[1]["candidate_rule_ids"]
    assert enriched[2]["candidate_rule_ids"] == []


def publish_result(saved, scene):
    """每轮均经过原保存合同，不手写Envelope或改变Canonical选轮。"""
    job = saved.create_batch_job(
        draft={
            "id": "sichuan-rule-library",
            "rule_code": "SC-BATCH",
            "name": "合成反馈闭环",
            "scene": scene,
        },
        created_by="qc",
        scope=scene,
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
    return job


@pytest.fixture(params=["running", "final"])
def feedback(raw_pg, monkeypatch, request):
    scene = request.param
    initialize(raw_pg.url.database)
    engine = sa.create_engine(
        raw_pg.url, connect_args={"options": "-csearch_path=qc,sys,cdm,public,legacy"}
    )
    sessions = sessionmaker(engine)
    monkeypatch.setattr(workspace, "engine", engine)
    monkeypatch.setattr(workspace, "DB_SCHEMA_MODE", "split")
    monkeypatch.setattr(workspace, "SessionLocal", sessions)
    monkeypatch.setattr(connection, "SessionLocal", sessions)
    monkeypatch.setattr(auth_store, "SessionLocal", sessions)
    # 绑定专属PG，不替换认证解析或默认CDM文书读取实现。
    monkeypatch.setattr(auth_store, "users_db", {})
    monkeypatch.setattr(assembly, "engine", engine)
    # 当前文书快照新增首页四表投影；与组装器绑定同一个专属PG，不能留在离线None连接。
    monkeypatch.setattr(frontpage_view, "engine", engine)
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
    monkeypatch.setattr(query_service, "engine", engine)
    for module in (
        manual_defect_review_service,
        record_review_service,
        rule_set_version_service,
        scoring_standard_service,
    ):
        monkeypatch.setattr(module, "SessionLocal", sessions)
    # 离线导入时默认SessionLocal为空，仅替换同一个实现的连接绑定，不伪造报表来源。
    monkeypatch.setattr(
        remediation.build_analysis,
        "__kwdefaults__",
        {**remediation.build_analysis.__kwdefaults__, "sessions": sessions},
    )
    monkeypatch.setattr(user_scope_owner, "DB_SEARCH_PATH", "qc,sys,cdm,public,legacy")
    workspace._record_result_envelopes_table.cache_clear()
    assembly._get_table_columns.cache_clear()
    password = secrets.token_urlsafe(24)
    password_hash = get_password_hash(password)
    with engine.begin() as conn:
        # mr_diagnosis 是同步/导入管理的既有CDM镜像前置，不属于报表51的新增表。
        # 合成库显式准备与正式诊断相同的列合同，不用假的首页响应替代真实读取。
        conn.exec_driver_sql("CREATE TABLE cdm.mr_diagnosis (LIKE cdm.diagnosis INCLUDING ALL)")
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
                    email=f"{identifier}@feedback.synthetic.invalid",
                    password_hash=password_hash,
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
                **IDENTITY,
                name="合成病例",
                document_id="synthetic-frontpage",
                admission_dept_name="合成内科",
                discharge_dept_name="合成内科",
                admission_datetime=datetime(2026, 10, 20, 8),
                discharge_datetime=datetime(2026, 10, 22, 8)
                if scene == "final"
                else None,
            )
        )
        document = sa.Table(
            "admission_record", sa.MetaData(), schema="cdm", autoload_with=conn
        )
        conn.execute(
            document.insert().values(
                **IDENTITY,
                document_id="synthetic-document",
                admission_datetime=datetime(2026, 10, 20, 8),
                record_datetime=datetime(2026, 10, 21, 9),
                dept_name="合成内科",
                record_content="合成整改前正文",
                chief_complaint="合成整改前主诉",
            )
        )
    saved = workspace.CustomQCWorkspaceService(readonly=True)
    job = publish_result(saved, scene)
    service = DefectRectificationService(sessions)
    monkeypatch.setattr(api, "service", service)
    monkeypatch.setattr(notifications, "service", DoctorNotificationService(sessions))
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(api.router)
    app.include_router(quality_reports.router)
    app.include_router(notifications.router)
    with TestClient(app) as client:
        assert not app.dependency_overrides
        assert client.get("/api/v1/defect-rectifications").status_code in {401, 403}
        assert (
            client.post(
                "/api/v1/auth/login", json={"account": "doc", "password": "wrong"}
            ).status_code
            == 401
        )
        headers = {}
        for identifier in ("qc", "doc", "other", "cross"):
            response = client.post(
                "/api/v1/auth/login",
                json={"account": identifier, "password": password, "role": "admin"},
            )
            assert response.status_code == 200
            headers[identifier] = {
                "Authorization": f"Bearer {response.json()['access_token']}"
            }
            me = client.get("/api/v1/auth/me", headers=headers[identifier])
            assert me.status_code == 200
            assert me.json()["data"]["id"] == identifier
            assert me.json()["data"]["is_demo_account"] is False
            assert "admin" not in me.json()["data"]["roles"]

        def select_actor(identifier):
            client.headers.update(headers[identifier])

        select_actor("qc")
        yield engine, sessions, saved, service, client, select_actor, job, scene
    engine.dispose()
    workspace._record_result_envelopes_table.cache_clear()
    assembly._get_table_columns.cache_clear()


def test_dispatch_snapshot_reads_frontpage_and_documents_from_same_pg(feedback):
    _, _, _, service, _, _, _, _ = feedback
    captured = json.loads(service._snapshot(SimpleNamespace(**IDENTITY)))
    assert captured["identity"] == IDENTITY
    assert {
        (document["doc_type"], document["document_id"])
        for document in captured["documents"]
    } >= {("mr", "synthetic-frontpage"), ("admission_record", "synthetic-document")}


def test_saved_result_to_rectification_and_report_with_real_pg(feedback, monkeypatch):
    engine, sessions, saved, service, http, actor, job, scene = feedback
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
        actor(user)
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
    actor("cross")
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
    actor("doc")
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
        scene=scene,
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
            ("qc", "notifications"),
        }:
            assert old["rows"] == after[key]["rows"], key
    actor("doc")
    notices = http.get("/api/v1/notifications").json()["data"]
    assert notices["total"] == notices["unread_count"] == 4
    assert all(
        item["interaction_target"] == {"kind": "rectification", "id": task["id"]}
        for item in notices["items"]
    )
    print(
        json.dumps(
            {
                "from_saved_result": True,
                "events": 6,
                "event_failure_rolled_back": True,
                "report_state": "approved",
                "protected_tables": len(before) - 3,
            }
        )
    )


def test_normal_login_cdm_comparison_and_http_report(feedback, monkeypatch):
    engine, sessions, saved, service, http, actor, job, scene = feedback
    base = "/api/v1/defect-rectifications"
    report = "/api/v1/quality-reports/record-quality/remediations"
    params = {"scene": scene, "defect_source": "auto"}

    def analysis(label=None):
        response = http.get(
            report, params={**params, **({"label": label} if label else {})}
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]

    initial = analysis("not_dispatched")
    assert initial["total"] == 1
    assert initial["items"][0]["rectification_state"] == "not_dispatched"
    candidates = http.get(
        f"{base}/candidates", params={**IDENTITY, "expected_job_id": job["id"]}
    )
    assert candidates.status_code == 200, candidates.text
    source = {
        k: v for k, v in candidates.json()["data"]["targets"][0].items() if k != "label"
    }
    payload = {
        **IDENTITY,
        **source,
        "assignee_id": "doc",
        "requirement": "请核对并补全这份合成病历的记录",
    }
    for changed, status in (
        ({"institute_id": "SYN-OTHER"}, 403),
        ({"patient_id": "different-patient"}, 409),
        ({"visit_id": "different-visit"}, 409),
        ({"scene": "final" if scene == "running" else "running"}, 409),
        ({"root_job_id": "wrong-job"}, 409),
        ({"target_id": "wrong-rule"}, 409),
    ):
        assert http.post(base, json={**payload, **changed}).status_code == status
    actor("doc")
    assert http.post(base, json=payload).status_code == 403
    assert http.get(report, params=params).status_code == 403
    actor("qc")
    with engine.begin() as conn:
        conn.execute(
            sa.text("UPDATE sys.sys_users SET department='合成外科' WHERE id='doc'")
        )
    assert http.post(base, json=payload).status_code == 403
    with engine.begin() as conn:
        conn.execute(
            sa.text("UPDATE sys.sys_users SET department='合成内科' WHERE id='doc'")
        )
    created = http.post(base, json=payload)
    assert created.status_code == 200, created.text
    task = created.json()["data"]
    url = f"{base}/{task['id']}"

    def act(user, version, action, *, expected=200, **extra):
        actor(user)
        response = http.post(
            f"{url}/actions",
            json={
                "version": version,
                "action": action,
                "comment": "这是仅用于专属合成数据库的处理说明",
                **extra,
            },
        )
        assert response.status_code == expected, response.text
        return response.json().get("data")

    # 已签发的真实登录令牌不能绕过实时账号状态、角色或科室授权。
    for change, restore, expected_status in (
        ({"is_active": False}, {"is_active": True}, 401),
        ({"department": "合成外科"}, {"department": "合成内科"}, 403),
        ({"role": "nurse"}, {"role": "doctor"}, 403),
        ({"roles_json": "invalid-json"}, {"roles_json": None}, 403),
    ):
        with sessions() as session, session.begin():
            users = SysUser.__table__.to_metadata(sa.MetaData(), schema="sys")
            session.execute(users.update().where(users.c.id == "doc").values(**change))
        # 停用账号由真实认证入口拒绝401，仍启用但无对象权限的账号由owner拒绝403。
        act("doc", 1, "submit", expected=expected_status)
        assert http.get(url).status_code == expected_status
        with sessions() as session, session.begin():
            session.execute(users.update().where(users.c.id == "doc").values(**restore))
    actor("qc")
    detail = http.get(url).json()["data"]
    assert (detail["version"], len(detail["events"])) == (1, 1)
    assert analysis("not_urged_pending")["total"] == 1
    act("qc", 1, "urge")
    assert analysis("urged_pending")["total"] == 1
    detail = http.get(url).json()["data"]
    urge = detail["events"][-1]["id"]
    act("qc", 2, "withdraw_urge", urge_event_id=urge)
    assert analysis("not_urged_pending")["total"] == 1
    act("qc", 3, "withdraw_urge", expected=409, urge_event_id=urge)

    with monkeypatch.context() as scoped:
        # 仅负例注入源读取失败；正例始终走默认CDM实现。
        scoped.setattr(
            assembly,
            "_select_records",
            lambda **_: (_ for _ in ()).throw(RuntimeError("synthetic source failure")),
        )
        act("doc", 3, "submit", expected=503)
    actor("qc")
    rolled_back = http.get(url).json()["data"]
    assert (
        rolled_back["status"],
        rolled_back["version"],
        len(rolled_back["events"]),
    ) == ("pending", 3, 3)

    def update_document(content, complaint):
        with engine.begin() as conn:
            document = sa.Table(
                "admission_record", sa.MetaData(), schema="cdm", autoload_with=conn
            )
            conn.execute(
                document.update()
                .where(*[document.c[key] == value for key, value in IDENTITY.items()])
                .values(record_content=content, chief_complaint=complaint)
            )

    update_document("合成首次提交正文", "合成首次提交主诉")
    act("doc", 3, "submit")
    actor("qc")
    pending = analysis("pending_acceptance")
    assert pending["total"] == 1
    assert analysis("self_rectified")["total"] == 0
    first_submit = http.get(url).json()["data"]["events"][-1]["id"]

    def comparison(event_id):
        response = http.get(f"{url}/comparison", params={"event_id": event_id})
        assert response.status_code == 200, response.text
        result = response.json()["data"]
        assert result["available"] is True
        assert result["unavailable_documents"] == 0
        return next(
            doc for doc in result["documents"] if doc["key"][1] == "admission_record"
        )

    first = comparison(first_submit)
    assert first["state"] == "matched"
    assert "合成整改前主诉" in first["before"]["content"]
    assert "合成首次提交主诉" in first["after"]["content"]
    assert any(
        section["source_field"] == "chief_complaint"
        for section in first["after"]["sections"]
    )
    assert http.get(f"{url}/comparison", params={"event_id": urge}).status_code == 404
    act("qc", 4, "reject")
    act("qc", 5, "urge")
    update_document("合成再次提交正文", "合成再次提交主诉")
    act("doc", 6, "submit")
    actor("qc")
    second_submit = http.get(url).json()["data"]["events"][-1]["id"]
    assert first_submit != second_submit
    assert comparison(first_submit) == first
    second = comparison(second_submit)
    assert second["before"] == first["before"]
    assert "合成再次提交主诉" in second["after"]["content"]
    act("qc", 7, "approve")
    final = analysis("urged_rectified")
    assert final["total"] == 1
    row = final["items"][0]
    assert row["rectification_id"] == task["id"]
    assert row["submission_event_id"] == second_submit
    assert row["root_job_id"] == job["id"]
    assert row["envelope_id"] == source["envelope_id"]
    assert row["appeals"] == []
    exported = http.get(
        f"{report}/export", params={**params, "label": "urged_rectified"}
    )
    assert exported.status_code == 200, exported.text
    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert len(rows) == final["total"]
    assert rows[0]["rectification_id"] == task["id"]
    assert rows[0]["rectification_state"] == "approved"
    assert rows[0]["labels"] == "催办已整改"
    empty_export = http.get(
        f"{report}/export", params={**params, "label": "self_rectified"}
    )
    assert empty_export.status_code == 200, empty_export.text
    assert (
        list(csv.DictReader(io.StringIO(empty_export.content.decode("utf-8-sig"))))
        == []
    )
    actor("other")
    assert http.get(url).status_code == 403
    assert (
        http.get(f"{url}/comparison", params={"event_id": second_submit}).status_code
        == 403
    )
    actor("cross")
    assert analysis()["total"] == 0
    actor("doc")
    assert http.get(f"{base}?state=pending").json()["data"]["total"] == 0
    assert comparison(second_submit) == second
    actor("qc")
    detail = http.get(url).json()["data"]
    assert [event["action"] for event in detail["events"]] == [
        "assign",
        "urge",
        "withdraw_urge",
        "submit",
        "reject",
        "urge",
        "submit",
        "approve",
    ]
    assert "dispatch_document_snapshot" not in detail
    assert all(
        "submission_document_snapshot" not in event for event in detail["events"]
    )


def test_new_saved_round_isolates_dispatch_history_and_reports(feedback, monkeypatch):
    engine, sessions, saved, service, http, actor, old_job, scene = feedback
    base = "/api/v1/defect-rectifications"
    report = "/api/v1/quality-reports/record-quality/remediations"

    def candidates(job_id, status=200):
        response = http.get(
            f"{base}/candidates", params={**IDENTITY, "expected_job_id": job_id}
        )
        assert response.status_code == status, response.text
        if status == 200:
            targets = response.json()["data"]["targets"]
            assert len(targets) == 1
            return {key: value for key, value in targets[0].items() if key != "label"}

    def payload(source, assignee):
        return {
            **IDENTITY,
            **source,
            "assignee_id": assignee,
            "requirement": "请核对本轮合成病例并提交整改说明",
        }

    def post(body, status=200):
        response = http.post(base, json=body)
        assert response.status_code == status, response.text
        return response.json().get("data")

    def act(user, task, version, action, status=200):
        actor(user)
        response = http.post(
            f"{base}/{task['id']}/actions",
            json={
                "version": version,
                "action": action,
                "comment": "合成新旧轮次隔离验收处理说明",
            },
        )
        assert response.status_code == status, response.text

    def analysis(label=None):
        response = http.get(
            report,
            params={
                "scene": scene,
                "defect_source": "auto",
                **({"label": label} if label else {}),
            },
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]

    old_source = candidates(old_job["id"])
    old_payload = payload(old_source, "doc")
    old_task = post(old_payload)
    act("qc", old_task, 1, "urge")
    assert analysis("urged_pending")["total"] == 1

    # 两轮都是真实保存的非合规结果；没有修改选轮实现或伪造新Envelope。
    new_job = publish_result(saved, scene)
    assert new_job["id"] != old_job["id"]
    candidates(old_job["id"], 409)
    post(old_payload, 409)
    new_source = candidates(new_job["id"])
    assert new_source["root_job_id"] == new_job["id"]
    assert new_source["envelope_id"] != old_source["envelope_id"]
    post(
        payload({**new_source, "envelope_id": old_source["envelope_id"]}, "other"), 409
    )
    current = analysis("not_dispatched")
    assert current["total"] == 1
    assert current["items"][0]["root_job_id"] == new_job["id"]
    assert current["items"][0]["rectification_id"] is None
    assert analysis("urged_pending")["total"] == 0
    envelopes = workspace._record_result_envelopes_table()
    with engine.connect() as conn:
        saved_before = (
            conn.execute(
                sa.select(envelopes)
                .where(envelopes.c.root_job_id.in_([old_job["id"], new_job["id"]]))
                .order_by(envelopes.c.id)
            )
            .mappings()
            .all()
        )

    # 已派发旧轮仍按原受领人处理历史，但不能改变当前轮分类或偷换冻结来源。
    act("doc", old_task, 2, "submit")
    act("qc", old_task, 3, "approve")
    old_response = http.get(f"{base}/{old_task['id']}")
    assert old_response.status_code == 200
    old_detail = old_response.json()["data"]
    assert old_detail["root_job_id"] == old_job["id"]
    assert old_detail["envelope_id"] == old_source["envelope_id"]
    assert old_detail["status"] == "approved"
    old_submission = old_detail["events"][-2]["id"]
    assert analysis("not_dispatched")["total"] == 1
    assert analysis("urged_rectified")["total"] == 0

    new_payload = payload(new_source, "other")
    real_create = service.create

    def committed_create_without_receipt(*args, **kwargs):
        real_create(*args, **kwargs)
        raise ConnectionError("synthetic committed write receipt unavailable")

    # 只在真实提交之后注入回执故障；503不代表数据库未写入。
    with monkeypatch.context() as scoped:
        scoped.setattr(service, "create", committed_create_without_receipt)
        post(new_payload, 503)
    refreshed = http.get(base, params={**IDENTITY, **new_source})
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["data"]["total"] == 1
    new_task = refreshed.json()["data"]["items"][0]
    assert (new_task["status"], new_task["version"]) == ("pending", 1)
    post(new_payload, 409)
    assert new_task["id"] != old_task["id"]
    act("doc", new_task, 1, "submit", 403)
    real_transition = service.transition

    def committed_action_without_receipt(*args, **kwargs):
        real_transition(*args, **kwargs)
        raise ConnectionError("synthetic committed action receipt unavailable")

    with monkeypatch.context() as scoped:
        scoped.setattr(service, "transition", committed_action_without_receipt)
        act("other", new_task, 1, "submit", 503)
    refreshed = http.get(f"{base}/{new_task['id']}")
    assert refreshed.status_code == 200, refreshed.text
    submitted = refreshed.json()["data"]
    assert (submitted["status"], submitted["version"], len(submitted["events"])) == (
        "submitted",
        2,
        2,
    )
    act("other", new_task, 1, "submit", 409)
    act("qc", new_task, 2, "approve")
    current = analysis("self_rectified")
    assert current["total"] == 1
    row = current["items"][0]
    assert (row["rectification_id"], row["root_job_id"], row["envelope_id"]) == (
        new_task["id"],
        new_job["id"],
        new_source["envelope_id"],
    )
    assert len(row["events"]) == 3
    assert old_submission not in {event["id"] for event in row["events"]}
    assert analysis("urged_rectified")["total"] == 0
    exported = http.get(
        f"{report}/export", params={"scene": scene, "defect_source": "auto"}
    )
    assert exported.status_code == 200, exported.text
    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0]["rectification_id"] == new_task["id"]
    assert rows[0]["root_job_id"] == new_job["id"]

    # 八维精确筛选须先于分页；旧轮历史不因最新结果变化而消失。
    for source, task in ((old_source, old_task), (new_source, new_task)):
        listed = http.get(base, params={**IDENTITY, **source, "page_size": 1})
        assert listed.status_code == 200, listed.text
        assert listed.json()["data"]["total"] == 1
        assert listed.json()["data"]["items"][0]["id"] == task["id"]
    actor("doc")
    assert http.get(f"{base}/{old_task['id']}").status_code == 200
    assert http.get(f"{base}/{new_task['id']}").status_code == 403
    assert (
        http.get(
            f"{base}/{old_task['id']}/comparison", params={"event_id": old_submission}
        ).status_code
        == 200
    )
    actor("other")
    assert http.get(f"{base}/{old_task['id']}").status_code == 403
    assert (
        http.get(
            f"{base}/{new_task['id']}/comparison", params={"event_id": old_submission}
        ).status_code
        == 404
    )

    # 整改没有倒改任一轮保存的Envelope和原始非合规结论。
    with engine.connect() as conn:
        saved_after = (
            conn.execute(
                sa.select(envelopes)
                .where(envelopes.c.root_job_id.in_([old_job["id"], new_job["id"]]))
                .order_by(envelopes.c.id)
            )
            .mappings()
            .all()
        )
        assert saved_after == saved_before
        assert {row["id"] for row in saved_after} == {
            old_source["envelope_id"],
            new_source["envelope_id"],
        }
    raw = saved.build_luxian_0609_completed_record_result_summaries(
        record_refs=[IDENTITY], include_items=True, include_rule_set_context=True
    )[tuple(IDENTITY.values())]
    assert raw["root_job_id"] == new_job["id"]
    assert raw["items"][0]["status"] == "non_compliant"
