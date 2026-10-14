"""首页质控 V2：存储、迁移与后台任务（SQLite，不连接业务数据库）。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import sessionmaker

from app.services.frontpage_qc_v2 import FrontpageRef, evaluate_frontpage
from app.services.frontpage_qc_v2.jobs import run_frontpage_qc_job
from app.services.frontpage_qc_v2.reporting import build_analytics, build_export_workbook
from app.services.frontpage_qc_v2.store import (
    FrontpageQcNotFound,
    FrontpageQcStore,
    FrontpageQcStoreUnavailable,
    build_tables,
)
from tests.unit.frontpage_qc_v2_support import make_doc, seed_cdm_frontpages

MIGRATION = Path(__file__).resolve().parents[2] / "alembic/versions/20261013_000048_frontpage_qc_v2.py"


@pytest.fixture()
def engine(tmp_path):
    eng = sa.create_engine(f"sqlite:///{tmp_path / 'fpqc.sqlite'}")
    yield eng
    eng.dispose()


@pytest.fixture()
def store(engine):
    s = FrontpageQcStore(sessionmaker(bind=engine))
    s.create_all(engine)
    return s


def _ref(n: int) -> FrontpageRef:
    return FrontpageRef("INST-SYN", f"C{n:02d}", f"C{n:02d}-V1")


def _outcome(ref: FrontpageRef, **mr_overrides):
    doc = make_doc(mr_overrides=mr_overrides)
    doc.institute_id, doc.patient_id, doc.visit_id = ref.institute_id, ref.patient_id, ref.visit_id
    return evaluate_frontpage(doc)


def test_migration_roundtrip_matches_runtime_tables(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("fpqc_migration", MIGRATION)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "20261013_000048"
    assert migration.down_revision == "20261006_000047"
    monkeypatch.setenv("DB_SCHEMA_MODE", "single")
    eng = sa.create_engine(f"sqlite:///{tmp_path / 'migration.sqlite'}")
    try:
        with eng.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
                inspector = sa.inspect(conn)
                for table in build_tables():
                    columns = {c["name"] for c in inspector.get_columns(table.name)}
                    assert columns == set(table.c.keys()), table.name
                    indexes = {i["name"] for i in inspector.get_indexes(table.name)}
                    assert indexes == {i.name for i in table.indexes}, table.name
                migration.downgrade()
                assert not any(sa.inspect(conn).has_table(t.name) for t in build_tables())
    finally:
        eng.dispose()


def test_missing_tables_report_unavailable_instead_of_success(engine):
    unmigrated = FrontpageQcStore(sessionmaker(bind=engine))
    with pytest.raises(FrontpageQcStoreUnavailable):
        unmigrated.create_run(created_by="u", refs=[_ref(1)], filters={}, ruleset_version="v")
    with pytest.raises(FrontpageQcStoreUnavailable):
        unmigrated.latest_by_keys(["x"])


def test_run_lifecycle_and_cancel(store):
    run = store.create_run(created_by="u1", refs=[_ref(1), _ref(2)], filters={"mode": "selected"}, ruleset_version="v")
    assert run["status"] == "queued"
    assert run["total_records"] == 2
    assert store.run_refs(run["id"]) == [_ref(1), _ref(2)]

    cancelled = store.request_cancel(run["id"])
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancel_requested"] is True

    with pytest.raises(FrontpageQcNotFound):
        store.get_run("missing")


def test_rerun_replaces_latest_and_keeps_review_decisions(store):
    ref = _ref(1)
    first = store.save_outcome(run_id="r1", outcome=_outcome(ref, leaving_hospital_way="", sex=""), department="外科", discharge_date="2026-03-08")
    detail = store.latest_detail(ref)
    assert detail["id"] == first
    by_rule = {f["rule_id"]: f for f in detail["findings"]}
    store.review_finding(by_rule["C-H24"]["id"], status="false_alarm", note="HIS 已填，首页同步缺失", reviewer="u1")

    second = store.save_outcome(run_id="r2", outcome=_outcome(ref, leaving_hospital_way="", sex=""), department="外科", discharge_date="2026-03-08")
    latest = store.latest_detail(ref)
    assert latest["id"] == second
    carried = {f["rule_id"]: f for f in latest["findings"]}
    assert carried["C-H24"]["review_status"] == "false_alarm"
    assert carried["C-H24"]["review_note"] == "HIS 已填，首页同步缺失"
    assert carried["C-P05"]["review_status"] == "pending"

    # 旧结果上的问题不能再复核
    with pytest.raises(FrontpageQcNotFound):
        store.review_finding(by_rule["C-P05"]["id"], status="confirmed", note="", reviewer="u1")


def test_query_latest_filters(store):
    store.save_outcome(run_id="r", outcome=_outcome(_ref(1)), department="外科", discharge_date="2026-03-08")
    store.save_outcome(run_id="r", outcome=_outcome(_ref(2), leaving_hospital_way="", mr_no="", sex="", admission_dept_name="", discharge_dept_name="", transfer_dept_name=""), department="内科", discharge_date="2026-04-01")

    items, total = store.query_latest(issue="fail")
    assert total == 1 and items[0]["record_key"] == _ref(2).as_key()
    items, total = store.query_latest(grade="excellent")
    assert total == 1 and items[0]["record_key"] == _ref(1).as_key()
    items, total = store.query_latest(grade="qualified")
    assert total == 1 and items[0]["score"] == 89  # 离院4 + 病案号2 + 性别1 + 入院科别1 + 出院科别2 + 转科科别1
    _, total = store.query_latest(department="外科")
    assert total == 1
    _, total = store.query_latest(start_date="2026-04-01", end_date="2026-04-30")
    assert total == 1
    _, total = store.query_latest(record_keys=[_ref(1).as_key()])
    assert total == 1
    assert set(store.latest_by_keys([_ref(1).as_key(), _ref(2).as_key(), "x"])) == {_ref(1).as_key(), _ref(2).as_key()}


def test_review_status_must_be_known(store):
    store.save_outcome(run_id="r", outcome=_outcome(_ref(1), sex=""))
    finding = store.latest_detail(_ref(1))["findings"][0]
    with pytest.raises(ValueError):
        store.review_finding(finding["id"], status="approved", note="", reviewer="u")


def test_analytics_and_export(store):
    store.save_outcome(run_id="r", outcome=_outcome(_ref(1)), department="外科", discharge_date="2026-03-08")
    store.save_outcome(run_id="r", outcome=_outcome(_ref(2), leaving_hospital_way=""), department="内科", discharge_date="2026-03-09")
    rows = store.latest_rows_for_analytics()
    report = build_analytics(rows)

    assert report["summary"]["records"] == 2
    assert report["summary"]["issue_records"] == 1
    assert report["top_rules"][0]["rule_id"] == "C-H24"
    assert report["departments"][0]["department"] == "内科"
    indicators = {item["key"]: item for item in report["indicators"]}
    assert indicators["completeness"]["numerator"] == 1
    assert indicators["completeness"]["denominator"] == 2
    assert indicators["excellent"]["rate"] == 1.0

    results, _ = store.query_latest()
    findings = store.latest_findings([r["id"] for r in results])
    content = build_export_workbook(filters_summary="全部科室", results=results, findings=findings, record_info={})
    from io import BytesIO

    from openpyxl import load_workbook

    workbook = load_workbook(BytesIO(content))
    assert workbook.sheetnames == ["病历结果", "问题明细"]
    assert workbook["病历结果"].max_row == 4
    assert any(row[2].value == "C-H24" for row in workbook["问题明细"].iter_rows(min_row=2))


def _cdm(engine, refs, broken=None):
    factory = sessionmaker(bind=engine)
    with factory() as session:
        seed_cdm_frontpages(session, refs, broken=broken)
    return factory


def test_job_completes_and_saves_results(engine, store):
    refs = [_ref(1), _ref(2)]
    factory = _cdm(engine, refs, broken={_ref(2)})
    run = store.create_run(created_by="u", refs=refs, filters={}, ruleset_version="v")

    finished = run_frontpage_qc_job(
        run["id"], store=store, cdm_session_factory=factory, cdm_schema=None,
        record_meta={_ref(1).as_key(): {"department": "外科", "discharge_date": "2026-03-08"}},
    )

    assert finished["status"] == "completed"
    assert finished["processed_records"] == 2
    assert finished["success_count"] == 2
    assert finished["issue_records"] == 1
    assert store.latest_detail(_ref(1))["department"] == "外科"
    assert store.latest_detail(_ref(2))["score"] == 96


def test_job_reports_missing_frontpage_without_stopping(engine, store):
    factory = _cdm(engine, [_ref(1)])
    run = store.create_run(created_by="u", refs=[_ref(1), _ref(9)], filters={}, ruleset_version="v")

    finished = run_frontpage_qc_job(run["id"], store=store, cdm_session_factory=factory, cdm_schema=None)

    assert finished["status"] == "completed_with_errors"
    assert finished["success_count"] == 1
    assert finished["failed_count"] == 1
    assert finished["failed_records"][0]["patient_id"] == "C09"
    assert finished["failed_records"][0]["error"] == "LookupError"


def test_job_stops_when_cancel_requested(engine, store, monkeypatch):
    refs = [_ref(n) for n in range(1, 26)]
    factory = _cdm(engine, refs)
    run = store.create_run(created_by="u", refs=refs, filters={}, ruleset_version="v")
    store.update_run(run["id"], cancel_requested=True)

    finished = run_frontpage_qc_job(run["id"], store=store, cdm_session_factory=factory, cdm_schema=None)

    assert finished["status"] == "cancelled"
    assert finished["processed_records"] == 10


def test_job_does_not_restart_non_queued_run(engine, store):
    factory = _cdm(engine, [_ref(1)])
    run = store.create_run(created_by="u", refs=[_ref(1)], filters={}, ruleset_version="v")
    store.request_cancel(run["id"])

    finished = run_frontpage_qc_job(run["id"], store=store, cdm_session_factory=factory, cdm_schema=None)
    assert finished["status"] == "cancelled"
    assert store.latest_detail(_ref(1)) is None
