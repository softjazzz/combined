"""PR8 机构隔离反例；只连接合成内存 SQLite，执行真实账号和缺陷查询。"""

import csv
import io
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import connection
from app.database.models.qc import QCDefect, QCDefectHistory, SysUser
from app.services import frontpage_quality_report_service as frontpage
from app.services import manual_defect_review_service as manual
from app.services import record_quality_report_service as record
from app.services.defect_rectification_service import RectificationError


@pytest.fixture
def database(monkeypatch):
    engine = sa.create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    for table in (SysUser.__table__, QCDefect.__table__, QCDefectHistory.__table__):
        table.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as session:
        for actor, role, institute, active, roles in (
            ("manager-a", "qc_manager", "A", True, None),
            ("manager-b", "qc_manager", "B", True, None),
            ("global", "admin", None, True, None),
            ("missing", "qc_manager", None, True, None),
            ("disabled", "admin", None, False, None),
            ("doctor", "doctor", "A", True, None),
            ("corrupt", "admin", None, True, "broken"),
        ):
            session.add(SysUser(id=actor, username=actor, display_name=actor, role=role,
                                institute_id=institute, is_active=active, roles_json=roles))
        for institute in ("A", "B"):
            for suffix, scene in (("running", "running"), ("final", "final"), ("unknown", None)):
                session.add(QCDefect(
                    id=f"{institute}-{suffix}", record_id="same", institute_id=institute,
                    patient_id="same", visit_id="same", origin="manual", identity_version=1,
                    source_key="task_assigned_qc", scene=scene, manual_review_status="pending",
                    manual_created_by="creator", rule_code="R", status="pending",
                    created_at=datetime(2026, 10, 1),
                ))
    monkeypatch.setattr(connection, "SessionLocal", sessions)
    monkeypatch.setattr(manual, "SessionLocal", sessions)
    yield sessions
    engine.dispose()


@pytest.mark.parametrize("actor,institute", [("manager-a", "A"), ("manager-b", "B")])
@pytest.mark.parametrize("scene,count", [("all", 3), ("running", 1), ("final", 1)])
def test_manual_count_list_and_case_share_persistent_institute(database, actor, institute, scene, count):
    page = manual.list_manual_defects(actor_id=actor, scene=scene)
    assert page["total"] == manual.count_pending_manual_defects(actor_id=actor, scene=scene) == count
    assert {item["institute_id"] for item in page["items"]} == {institute}
    other = "B" if institute == "A" else "A"
    with pytest.raises(manual.ManualDefectReviewForbidden):
        manual.list_case_manual_defects(actor_id=actor, institute_id=other, patient_id="same", visit_id="same")
    with pytest.raises(manual.ManualDefectReviewNotFound):
        manual.review_manual_defect(defect_id=f"{other}-running", reviewer_id=actor, decision="approved")


@pytest.mark.parametrize("actor", [None, "missing", "disabled", "doctor", "corrupt", "nonexistent"])
def test_manual_scope_fails_closed(database, actor):
    with pytest.raises(manual.ManualDefectReviewForbidden):
        manual.count_pending_manual_defects(actor_id=actor)


def test_global_admin_can_read_both_institutes(database):
    assert manual.count_pending_manual_defects(actor_id="global") == 6
    assert manual.list_manual_defects(actor_id="global")["total"] == 6


def context(service, actor, *, builder=None):
    build = builder or service.build_report_context
    records = [dict(institute_id=i, patient_id="same", visit_id="same", department="same",
                    attending_physician="same") for i in ("A", "B")]
    if service is record:
        return build(
            actor_id=actor, scene="running", scope_loader=lambda **kwargs: records,
            results_loader=lambda refs: {(row["institute_id"], "same", "same"): {
                "status": "ready", "completed_at": "2026-10-01T00:00:00Z", "items": [],
                "root_job_id": f"job-{row['institute_id']}", "envelope_id": "env",
            } for row in refs}, review_loader=lambda anchors: {}, manual_loader=lambda identities: [],
            standard_loader=lambda scene: None, projector=list, rule_meta_loader=dict,
        )
    return build(
        actor_id=actor, scope_loader=lambda **kwargs: records,
        latest_loader=lambda sources, **kwargs: [dict(
            institute_id=i, patient_id="same", visit_id="same", source_key="frontpage_formal_qc",
            result={"id": f"result-{i}", "analysis_date": "2026-10-01T00:00:00Z"}, defects=[],
        ) for i in ("A", "B")],
    )


@pytest.mark.parametrize("service", [record, frontpage])
@pytest.mark.parametrize("actor,expected", [("manager-a", {"A"}), ("manager-b", {"B"}), ("global", {"A", "B"})])
def test_report_owner_filters_before_summary_records_and_export(database, service, actor, expected):
    ctx = context(service, actor)
    assert {row.identity[0] for row in ctx.rows} == expected
    assert {row["institute_id"] for row in service.records_page(ctx)["items"]} == expected
    assert len(ctx.rows) == service.records_page(ctx)["total"]
    exported = service.export_csv(ctx, sheet="records")
    assert exported.startswith(b"\xef\xbb\xbf")
    header = "机构编号" if service is record else "机构"
    assert {row[header] for row in csv.DictReader(io.StringIO(exported.decode("utf-8-sig")))} == expected


@pytest.mark.parametrize("service", [record, frontpage])
@pytest.mark.parametrize("actor", [None, "missing", "disabled", "doctor", "corrupt", "nonexistent"])
def test_report_owner_requires_trusted_actor(database, service, actor):
    with pytest.raises(RectificationError) as error:
        context(service, actor)
    assert error.value.status == 403


def test_record_pool_applies_institute_in_real_sql(database, monkeypatch):
    from app.database.models.cdm import MedicalRecordFrontpage
    from app.services.medical_records import query_service
    from app.services.workstation.luxian_0609_result_analysis_service import _load_current_workstation_records

    engine = database.kw["bind"]
    MedicalRecordFrontpage.__table__.create(engine)
    with database.begin() as session:
        session.add_all([MedicalRecordFrontpage(institute_id=i, patient_id="same", visit_id="same")
                         for i in ("A", "B")])
    queries = []
    sa.event.listen(engine, "before_cursor_execute", lambda _c, _u, sql, params, _x, _m: queries.append((sql, params)))
    monkeypatch.setattr(query_service, "_session_factory", database)
    monkeypatch.setattr(query_service, "_workstation_discharge_summary_subquery", lambda session: None)
    monkeypatch.setattr(query_service, "_apply_workstation_filters", lambda query, **kwargs: query)
    monkeypatch.setattr(query_service, "_load_hospitalization_projection_map", lambda session: {})
    rows = _load_current_workstation_records(department=None, doctor=None, hospital_status="all", institute_id="A")
    assert {row["institute_id"] for row in rows} == {"A"}
    assert any("mr.institute_id = ?" in sql and "A" in params for sql, params in queries)


@pytest.mark.parametrize("service", [record, frontpage])
@pytest.mark.parametrize("suffix", ["", "/records", "/export"])
def test_http_claims_cannot_widen_persistent_institute(database, monkeypatch, service, suffix):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.security import get_current_user
    from app.routers import quality_reports

    real_build = service.build_report_context
    # 用真实 owner 验证认证 ID 的传递；只注入合成来源，不 mock 掉授权或汇总。
    def build(**query):
        assert query["actor_id"] == "manager-a"
        return context(service, query["actor_id"], builder=real_build)

    monkeypatch.setattr(service, "build_report_context", build)
    app = FastAPI()
    app.include_router(quality_reports.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "manager-a", "roles": ["admin"], "institute_id": "B",
    }
    path = "record-quality" if service is record else "frontpage-quality"
    client = TestClient(app)
    response = client.get(f"/api/v1/quality-reports/{path}{suffix}",
                          params={"scene": "running", "institute_id": "B", "sheet": "records"})
    assert response.status_code == 200
    if suffix == "/records":
        assert {item["institute_id"] for item in response.json()["data"]["items"]} == {"A"}
    elif suffix == "/export":
        header = "机构编号" if service is record else "机构"
        assert {row[header] for row in csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")))} == {"A"}
    else:
        key = "qc_ready_total" if service is record else "case_total"
        assert response.json()["data"]["kpis"][key] == 1


@pytest.mark.parametrize("actor,status,total", [("manager-a", 200, 3), ("global", 200, 6), ("missing", 403, None)])
def test_review_todo_http_uses_real_manual_owner(database, monkeypatch, actor, status, total):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import dashboard_api, record_reviews

    monkeypatch.setattr(record_reviews, "count_my_record_review_todos", lambda *args: {
        "initial": None, "recheck": None, "unavailable_reason": "review_source_unavailable",
    })
    app = FastAPI()
    app.include_router(dashboard_api.router)
    app.dependency_overrides[dashboard_api.get_current_user] = lambda: {
        "id": actor, "roles": ["qc_manager"], "institute_id": "B",
    }
    response = TestClient(app).get("/api/v1/dashboard/review-todo-stats")
    assert response.status_code == status
    if total is not None:
        data = response.json()["data"]
        assert data["record_stats"]["pending_review"] is None
        assert data["record_stats"]["unavailable_reason"] == "review_source_unavailable"
        assert data["defect_stats"]["pending_review"] == total
