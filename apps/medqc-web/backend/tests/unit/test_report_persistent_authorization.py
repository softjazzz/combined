import csv
import io
from datetime import datetime

import pytest
import sqlalchemy as sa
from app.database import connection
from app.database.models import v36_reports as models
from app.database.models.v36_reports import QCDefect, QCDefectHistory, SysUser
from app.services import frontpage_quality_report_service as frontpage
from app.services import manual_defect_review_service as manual
from app.services import record_quality_report_service as record
from app.services import staff_work_analysis_service as staff
from app.services.defect_rectification_service import RectificationError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def database(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
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
            session.add(
                SysUser(
                    id=actor,
                    username=actor,
                    display_name=actor,
                    role=role,
                    institute_id=institute,
                    is_active=active,
                    roles_json=roles,
                )
            )
        for institute in ("A", "B"):
            for suffix, scene in (
                ("running", "running"),
                ("final", "final"),
                ("unknown", None),
            ):
                session.add(
                    QCDefect(
                        id=f"{institute}-{suffix}",
                        record_id="same",
                        institute_id=institute,
                        patient_id="same",
                        visit_id="same",
                        origin="manual",
                        identity_version=1,
                        source_key="task_assigned_qc",
                        scene=scene,
                        manual_review_status="pending",
                        manual_created_by="creator",
                        rule_code="R",
                        status="pending",
                        created_at=datetime(2026, 10, 1),
                    )
                )
    monkeypatch.setattr(connection, "SessionLocal", sessions)
    monkeypatch.setattr(manual, "SessionLocal", sessions)
    yield sessions
    engine.dispose()


def context(service, actor, *, builder=None):
    build = builder or service.build_report_context
    records = [
        dict(
            institute_id=i,
            patient_id="same",
            visit_id="same",
            department="same",
            attending_physician="same",
        )
        for i in ("A", "B")
    ]
    if service is record:
        return build(
            actor_id=actor,
            scene="running",
            scope_loader=lambda **kwargs: records,
            results_loader=lambda refs: {
                (row["institute_id"], "same", "same"): {
                    "status": "ready",
                    "completed_at": "2026-10-01T00:00:00Z",
                    "items": [],
                    "root_job_id": f"job-{row['institute_id']}",
                    "envelope_id": "env",
                }
                for row in refs
            },
            review_loader=lambda anchors: {},
            manual_loader=lambda identities: [],
            standard_loader=lambda scene: None,
            projector=list,
            rule_meta_loader=dict,
        )
    return build(
        actor_id=actor,
        scope_loader=lambda **kwargs: records,
        latest_loader=lambda sources, **kwargs: [
            dict(
                institute_id=i,
                patient_id="same",
                visit_id="same",
                source_key="frontpage_formal_qc",
                result={"id": f"result-{i}", "analysis_date": "2026-10-01T00:00:00Z"},
                defects=[],
            )
            for i in ("A", "B")
        ],
    )


@pytest.mark.parametrize("service", [record, frontpage])
@pytest.mark.parametrize(
    "actor,expected",
    [("manager-a", {"A"}), ("manager-b", {"B"}), ("global", {"A", "B"})],
)
def test_report_owner_filters_before_summary_records_and_export(
    database, service, actor, expected
):
    ctx = context(service, actor)
    assert {row.identity[0] for row in ctx.rows} == expected
    assert {
        row["institute_id"] for row in service.records_page(ctx)["items"]
    } == expected
    assert len(ctx.rows) == service.records_page(ctx)["total"]
    exported = service.export_csv(ctx, sheet="records")
    assert exported.startswith(b"\xef\xbb\xbf")
    header = "机构编号" if service is record else "机构"
    assert {
        row[header] for row in csv.DictReader(io.StringIO(exported.decode("utf-8-sig")))
    } == expected


@pytest.mark.parametrize("service", [record, frontpage])
@pytest.mark.parametrize(
    "actor", [None, "missing", "disabled", "doctor", "corrupt", "nonexistent"]
)
def test_report_owner_requires_trusted_actor(database, service, actor):
    with pytest.raises(RectificationError) as error:
        context(service, actor)
    assert error.value.status == 403


def test_record_pool_applies_institute_in_real_sql(database, monkeypatch):
    from app.database.models.cdm import MedicalRecordFrontpage
    from app.services.medical_records import query_service
    from app.services.report_case_scope import load_current_workstation_records

    engine = database.kw["bind"]
    MedicalRecordFrontpage.__table__.create(engine)
    with database.begin() as session:
        session.add_all(
            [
                MedicalRecordFrontpage(
                    institute_id=i, patient_id="same", visit_id="same"
                )
                for i in ("A", "B")
            ]
        )
    queries = []
    sa.event.listen(
        engine,
        "before_cursor_execute",
        lambda _c, _u, sql, params, _x, _m: queries.append((sql, params)),
    )
    monkeypatch.setattr(query_service, "_session_factory", database)
    monkeypatch.setattr(
        query_service, "_workstation_discharge_summary_subquery", lambda session: None
    )
    monkeypatch.setattr(
        query_service, "_apply_workstation_filters", lambda query, **kwargs: query
    )
    monkeypatch.setattr(
        query_service, "_load_hospitalization_projection_map", lambda session: {}
    )
    rows = load_current_workstation_records(
        department=None, doctor=None, hospital_status="all", institute_id="A"
    )
    assert {row["institute_id"] for row in rows} == {"A"}
    assert any(
        "mr.institute_id = ?" in sql and "A" in params for sql, params in queries
    )


@pytest.mark.parametrize("service", [record, frontpage])
@pytest.mark.parametrize("suffix", ["", "/records", "/export"])
def test_http_claims_cannot_widen_persistent_institute(
    database, monkeypatch, service, suffix
):
    from app.core.security import get_current_user
    from app.routers import quality_reports
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    real_build = service.build_report_context

    # 用真实 owner 验证认证 ID 的传递；只注入合成来源，不 mock 掉授权或汇总。
    def build(**query):
        assert query["actor_id"] == "manager-a"
        return context(service, query["actor_id"], builder=real_build)

    monkeypatch.setattr(service, "build_report_context", build)
    app = FastAPI()
    app.include_router(quality_reports.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "manager-a",
        "roles": ["admin"],
        "institute_id": "B",
    }
    path = "record-quality" if service is record else "frontpage-quality"
    client = TestClient(app)
    response = client.get(
        f"/api/v1/quality-reports/{path}{suffix}",
        params={"scene": "running", "institute_id": "B", "sheet": "records"},
    )
    assert response.status_code == 200
    if suffix == "/records":
        assert {item["institute_id"] for item in response.json()["data"]["items"]} == {
            "A"
        }
    elif suffix == "/export":
        header = "机构编号" if service is record else "机构"
        assert {
            row[header]
            for row in csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")))
        } == {"A"}
    else:
        key = "qc_ready_total" if service is record else "case_total"
        assert response.json()["data"]["kpis"][key] == 1


@pytest.fixture
def staff_database(database, monkeypatch):
    engine = database.kw["bind"]
    models.ReportBase.metadata.create_all(
        engine.execution_options(schema_translate_map={"qc": None})
    )
    monkeypatch.setattr(staff, "SessionLocal", database)
    with database.begin() as session:
        for institute in ("A", "B"):
            session.add(
                models.QCRecordReview(
                    id=f"review-{institute}",
                    request_id=f"req-{institute}",
                    institute_id=institute,
                    patient_id="same",
                    visit_id="same",
                    rule_set_key="synthetic",
                    rule_set_version="v1",
                    job_id=f"job-{institute}",
                    envelope_id="env",
                    review_context="workspace",
                    scene="running",
                    stage="initial",
                    decision="approved",
                    reviewer_id=f"reviewer-{institute}",
                    created_at=datetime(2026, 10, 1, 1),
                )
            )
    return database


STAFF_FILTERS = dict(period="this_month", as_of="2026-10-23T00:00:00Z", scene="running")


@pytest.mark.parametrize(
    "actor,institutes",
    [("manager-a", {"A"}), ("manager-b", {"B"}), ("global", {"A", "B"})],
)
def test_staff_institute_only_scopes_summary_options_details_and_csv(
    staff_database, monkeypatch, actor, institutes
):
    # 故意让维度读取器返回越界选项，owner仍只能显示本次可见身份。
    monkeypatch.setattr(staff, "load_scoring_departments", lambda *args, **kwargs: {})
    data = staff.get_staff_work_analysis(
        actor_id=actor,
        department_loader=lambda refs, **kwargs: {
            ("A", "same", "same"): "内科",
            ("B", "same", "same"): "内科",
        },
        **STAFF_FILTERS,
    )
    assert data["summary"]["record_review_count"] == len(institutes)
    assert {row["user_id"] for row in data["staff"]} == {
        f"reviewer-{i}" for i in institutes
    }
    assert {
        row["institute_id"] for row in data["filter_options"]["departments"]
    } == institutes
    for institute in ("A", "B"):
        page = staff.get_staff_work_details(
            actor_id=actor,
            user_id=f"reviewer-{institute}",
            metric="record_review_count",
            **STAFF_FILTERS,
        )
        assert page["total"] == int(institute in institutes)
    content, rows = staff.export_staff_work_csv(actor_id=actor, **STAFF_FILTERS)
    assert rows == len(institutes)
    for institute in ("A", "B"):
        assert (f"reviewer-{institute}" in content.decode("utf-8-sig")) == (
            institute in institutes
        )


@pytest.mark.parametrize("suffix", ["", "/export", "/reviewer-B/details"])
def test_staff_http_claims_and_other_institute_request_cannot_widen(
    staff_database, suffix
):
    from app.core.security import get_current_user
    from app.routers import staff_work_analysis as routes
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "manager-a",
        "roles": ["admin"],
        "institute_id": "B",
    }
    client = TestClient(app)
    filters = {**STAFF_FILTERS, "metric": "record_review_count"}
    response = client.get("/api/v1/quality-reports/staff-work" + suffix, params=filters)
    assert response.status_code == 200
    if suffix.endswith("/details"):
        assert response.json()["data"]["total"] == 0
        assert response.json()["data"]["items"] == []
    else:
        assert "reviewer-B" not in response.text
    response = client.get(
        "/api/v1/quality-reports/staff-work" + suffix,
        params={**filters, "institute_id": "B"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "actor", [None, "missing", "disabled", "doctor", "corrupt", "nonexistent"]
)
def test_staff_rejects_untrusted_actor_before_event_load(database, monkeypatch, actor):
    monkeypatch.setattr(
        staff, "_read", lambda *args, **kwargs: pytest.fail("越权时不能读取事件")
    )
    for method, kwargs in [
        (staff.get_staff_work_analysis, {}),
        (
            staff.get_staff_work_details,
            {"user_id": "reviewer", "metric": "record_review_count"},
        ),
        (staff.export_staff_work_csv, {}),
    ]:
        with pytest.raises(RectificationError) as error:
            method(actor_id=actor, **kwargs, **STAFF_FILTERS)
        assert error.value.status == 403


@pytest.mark.parametrize(
    "path,existing,owner",
    [
        (["public", "sys"], ["public", "sys"], "public"),
        (["sys", "public"], ["public", "sys"], "sys"),
        ([], ["sys"], "sys"),
    ],
)
def test_trusted_account_owner_is_explicit(path, existing, owner):
    from app.services.user_scope_owner import select_user_owner_schema

    assert (
        select_user_owner_schema(search_path=path, schemas_with_user_table=existing)
        == owner
    )


@pytest.mark.parametrize(
    "path,existing",
    [
        ([], ["sys", "public"]),
        ([], ["sys", "shadow"]),
        (["shadow", "sys"], ["sys", "shadow"]),
        (["qc"], ["sys"]),
    ],
)
def test_ambiguous_or_shadow_account_owner_fails_closed(path, existing):
    from app.services.user_scope_owner import (
        UserOwnerUnavailable,
        select_user_owner_schema,
    )

    with pytest.raises(UserOwnerUnavailable):
        select_user_owner_schema(search_path=path, schemas_with_user_table=existing)


def test_manual_report_default_readers_never_bootstrap_tables(
    staff_database, monkeypatch
):
    from datetime import date

    from app.services import custom_qc_workspace_service as workspace
    from app.services.manual_quality_report_service import ManualQualityReportService

    engine = staff_database.kw["bind"]
    monkeypatch.setattr(workspace, "engine", engine)
    monkeypatch.setattr(workspace, "_draft_schema", lambda: None)
    workspace._batch_jobs_table.cache_clear()
    workspace._record_result_envelopes_table.cache_clear()
    jobs = workspace._batch_jobs_table(readonly=True)
    assert not sa.inspect(engine).has_table(jobs.name)
    # 所有结构都由测试显式建立；运行报表期间禁止任何DDL/写入。
    jobs.create(engine)
    workspace._record_result_envelopes_table().create(engine)
    statements = []

    def read_only(_conn, _cursor, sql, params, context, many):
        assert sql.lstrip().split()[0].upper() in {
            "SELECT",
            "PRAGMA",
            "SAVEPOINT",
            "RELEASE",
        }
        statements.append(sql)

    sa.event.listen(engine, "before_cursor_execute", read_only)
    try:
        sessions = sessionmaker(
            bind=engine.execution_options(schema_translate_map={"qc": None})
        )
        data = ManualQualityReportService(sessions=sessions).report(
            "manager-a",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
        )
        assert data["total"] == 3
        assert {row["institute_id"] for row in data["items"]} == {"A"}
        assert all(row["source_verified"] is False for row in data["items"])
        assert all(row["rectification_status"] == "unknown" for row in data["items"])
        assert any("qc_defects.institute_id" in sql for sql in statements)
    finally:
        sa.event.remove(engine, "before_cursor_execute", read_only)
        workspace._batch_jobs_table.cache_clear()
        workspace._record_result_envelopes_table.cache_clear()
