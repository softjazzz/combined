"""Offline unit tests for QC home overview performance optimizations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from app.services import custom_qc_workspace_service as workspace
from app.services.workstation.worklist_service import WorkstationAggregationService


def _make_valid_envelope_json(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    rule_id: str = "LX0609-06-01-04",
    status: str = "compliant",
) -> str:
    projected_item = workspace.CustomQCWorkspaceService._envelope_item_from_rule_result(
        {
            "rule_id": rule_id,
            "rule_code": rule_id,
            "rule_name": "测试规则",
            "status": status,
            "result_status": status,
            "is_compliant": status == "compliant",
            "severity": "major" if status == "non_compliant" else "none",
            "customer_summary": "未发现该质控点对应的明确问题。" if status == "compliant" else "发现该质控点对应的明确问题。",
            "customer_suggestion": "无需处理。" if status == "compliant" else "请按质控要求补充或修正。",
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
            "record_id": visit_id,
        }
    )
    return json.dumps(
        {
            "schema_version": workspace._RECORD_RESULT_ENVELOPE_SCHEMA,
            "delivery_mode": workspace._CANONICAL_RESULT_DELIVERY_MODE,
            "record_identity": {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
            },
            "items": [projected_item],
        },
        ensure_ascii=False,
    )


def _create_sqlite_workspace_env():
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    jobs = sa.Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("draft_id", sa.String(36), nullable=False),
        sa.Column("rule_code", sa.String(32), nullable=False),
        sa.Column("rule_name", sa.String(200), nullable=False),
        sa.Column("scene", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
        sa.Column("record_ids_json", sa.Text, nullable=False),
        sa.Column("summary_json", sa.Text),
        sa.Column("items_json", sa.Text),
        sa.Column("failed_records_json", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("total_records", sa.Integer, nullable=False, default=0),
        sa.Column("success_count", sa.Integer, nullable=False, default=0),
        sa.Column("failed_count", sa.Integer, nullable=False, default=0),
        sa.Column("issue_records", sa.Integer, nullable=False, default=0),
        sa.Column("compliant_records", sa.Integer, nullable=False, default=0),
        sa.Column("total_tokens", sa.Integer, nullable=False, default=0),
        sa.Column("total_processing_time", sa.Float, nullable=False, default=0.0),
        sa.Column("job_kind", sa.String(20), nullable=False, default="leaf"),
        sa.Column("parent_job_id", sa.String(36)),
        sa.Column("child_job_ids_json", sa.Text),
        sa.Column("child_summary_json", sa.Text),
        sa.Column("family_key", sa.String(64)),
        sa.Column("family_name", sa.String(64)),
    )
    envelopes = sa.Table(
        "luxian_0609_record_result_envelopes",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("root_job_id", sa.String(36), nullable=False),
        sa.Column("institute_id", sa.String(64), nullable=False),
        sa.Column("patient_id", sa.String(64), nullable=False),
        sa.Column("visit_id", sa.String(64), nullable=False),
        sa.Column("rule_set_key", sa.String(64), nullable=False),
        sa.Column("rule_set_version", sa.String(64), nullable=False),
        sa.Column("envelope_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    metadata.create_all(bind=engine)
    svc = object.__new__(workspace.CustomQCWorkspaceService)
    svc._batch_job_table = jobs
    svc._record_result_envelope_table = envelopes
    factory = sessionmaker(bind=engine)
    return svc, engine, jobs, envelopes, factory


def _insert_completed_record(
    conn,
    *,
    jobs: sa.Table,
    envelopes: sa.Table,
    job_id: str,
    env_id: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    ts: datetime,
    status: str = "compliant",
    rule_id: str = "LX0609-06-01-04",
) -> None:
    filters_json = json.dumps(
        {
            "rule_set_key": workspace.LUXIAN_0609_RULE_SET_KEY,
            "rule_set_version": workspace.RULE_SET_VERSION,
            "selected_rule_ids": [rule_id],
            "record_refs": [
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                }
            ],
        },
        ensure_ascii=False,
    )
    conn.execute(
        jobs.insert().values(
            id=job_id,
            draft_id="draft-1",
            rule_code="LX0609",
            rule_name="LX0609",
            scene="final",
            scope="final",
            status="completed",
            filters_json=filters_json,
            record_ids_json=json.dumps([visit_id]),
            summary_json=None,
            items_json=None,
            failed_records_json=None,
            error_message=None,
            created_by="tester",
            created_at=ts,
            started_at=ts,
            finished_at=ts,
            updated_at=ts,
            total_records=1,
            success_count=1,
            failed_count=0,
            issue_records=0 if status == "compliant" else 1,
            compliant_records=1 if status == "compliant" else 0,
            total_tokens=0,
            total_processing_time=0.0,
            job_kind="root",
            parent_job_id=None,
        )
    )
    conn.execute(
        envelopes.insert().values(
            id=env_id,
            root_job_id=job_id,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
            rule_set_version=workspace.RULE_SET_VERSION,
            envelope_json=_make_valid_envelope_json(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                rule_id=rule_id,
                status=status,
            ),
            created_at=ts,
            updated_at=ts,
        )
    )


def test_watermark_and_envelope_caches_hit_and_invalidate_immediately(monkeypatch):
    workspace.clear_luxian_0609_summary_caches()
    svc, engine, jobs, envelopes, factory = _create_sqlite_workspace_env()
    try:
        t1 = datetime(2026, 10, 1, 10, 0, 0)
        ref_a = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}
        ref_b = {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"}
        with engine.begin() as conn:
            _insert_completed_record(
                conn,
                jobs=jobs,
                envelopes=envelopes,
                job_id="job-a",
                env_id="env-a",
                ts=t1,
                status="compliant",
                **ref_a,
            )

        parse_calls: list[str] = []
        orig_summarize = workspace.CustomQCWorkspaceService._summarize_completed_record_result_envelope

        def tracked_summarize(*, envelope_row, **kwargs):
            parse_calls.append(str(envelope_row["id"]))
            return orig_summarize(envelope_row=envelope_row, **kwargs)

        monkeypatch.setattr(
            workspace.CustomQCWorkspaceService,
            "_summarize_completed_record_result_envelope",
            staticmethod(tracked_summarize),
        )

        executed_sql: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def _capture_sql(_conn, _cursor, statement, _params, _ctx, _many):
            executed_sql.append(statement)

        # Call 1 (cold): parses env-a once
        res1 = svc.build_luxian_0609_completed_record_result_summaries(
            record_refs=[ref_a, ref_b],
            session_factory=factory,
            include_latest_partial=True,
        )
        assert res1[("H1", "P1", "V1")]["status"] == "ready"
        assert res1[("H1", "P2", "V2")]["status"] == "not_run"
        assert parse_calls == ["env-a"]

        # Call 2 (warm, unchanged watermark): hits Tier 1 watermark cache, 0 filters_json scans, 0 parses
        executed_sql.clear()
        res2 = svc.build_luxian_0609_completed_record_result_summaries(
            record_refs=[ref_a],
            session_factory=factory,
            include_latest_partial=True,
        )
        assert res2[("H1", "P1", "V1")] == res1[("H1", "P1", "V1")]
        assert parse_calls == ["env-a"]
        assert not any("filters_json" in sql for sql in executed_sql)

        # Mutate DB: insert a new completed job + envelope for ref_b
        # Tier 1 watermark changes immediately, but ref_a hits Tier 2 envelope cache (NOT re-parsed)!
        t2 = t1 + timedelta(minutes=1)
        with engine.begin() as conn:
            _insert_completed_record(
                conn,
                jobs=jobs,
                envelopes=envelopes,
                job_id="job-b",
                env_id="env-b",
                ts=t2,
                status="non_compliant",
                **ref_b,
            )

        res3 = svc.build_luxian_0609_completed_record_result_summaries(
            record_refs=[ref_a, ref_b],
            session_factory=factory,
            include_latest_partial=True,
        )
        assert res3[("H1", "P1", "V1")]["status"] == "ready"
        assert res3[("H1", "P2", "V2")]["status"] == "ready"
        assert res3[("H1", "P2", "V2")]["status_counts"] == {"non_compliant": 1}
        # Only env-b was parsed; env-a was served from Tier 2 envelope cache
        assert parse_calls == ["env-a", "env-b"]
    finally:
        workspace.clear_luxian_0609_summary_caches()
        engine.dispose()


def test_large_visit_batch_skips_n_way_record_ids_ilike_explosion():
    workspace.clear_luxian_0609_summary_caches()
    svc, engine, jobs, envelopes, factory = _create_sqlite_workspace_env()
    try:
        t1 = datetime(2026, 10, 2, 10, 0, 0)
        refs = [
            {"institute_id": "H1", "patient_id": f"P{i}", "visit_id": f"V{i}"}
            for i in range(60)
        ]
        with engine.begin() as conn:
            _insert_completed_record(
                conn,
                jobs=jobs,
                envelopes=envelopes,
                job_id="job-59",
                env_id="env-59",
                ts=t1,
                status="compliant",
                **refs[59],
            )

        job_selects: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def _capture_sql(_conn, _cursor, statement, _params, _ctx, _many):
            if "filters_json" in statement:
                job_selects.append(statement)

        res = svc.build_luxian_0609_completed_record_result_summaries(
            record_refs=refs,
            session_factory=factory,
            include_latest_partial=True,
        )
        assert res[("H1", "P59", "V59")]["status"] == "ready"
        assert res[("H1", "P0", "V0")]["status"] == "not_run"
        assert len(job_selects) == 1
        assert "record_ids_json LIKE" not in job_selects[0]
        assert "record_ids_json ILIKE" not in job_selects[0]
    finally:
        workspace.clear_luxian_0609_summary_caches()
        engine.dispose()


def test_worklist_service_reuses_readonly_custom_qc_workspace_service(monkeypatch):
    init_calls: list[bool] = []

    class _FakeWorkspace:
        def __init__(self, *, readonly: bool = False):
            init_calls.append(readonly)

        def build_luxian_0609_completed_record_result_summaries(self, **_kwargs):
            return {("H1", "P1", "V1"): {"status": "ready"}}

    monkeypatch.setattr(workspace, "CustomQCWorkspaceService", _FakeWorkspace)
    owner = WorkstationAggregationService(session_factory=lambda: None)
    r1 = owner._load_luxian_0609_summaries(
        [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}]
    )
    r2 = owner._load_luxian_0609_summaries(
        [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}]
    )
    assert r1 == r2 == {("H1", "P1", "V1"): {"status": "ready"}}
    assert init_calls == [True]


def test_qc_home_router_offloads_aggregation_to_threadpool(client, monkeypatch):
    from app.routers import workstation as workstation_router

    monkeypatch.setattr(
        "app.core.security._decode_token",
        lambda _token, expected_type=None: {"sub": "u-home"},
    )
    monkeypatch.setattr(
        "app.core.security.resolve_user_by_subject",
        lambda _subject: {"id": "u-home", "roles": ["admin"]},
    )

    offloaded: list[str] = []
    orig_run_in_threadpool = workstation_router.run_in_threadpool

    async def tracked_run_in_threadpool(func, *args, **kwargs):
        offloaded.append(getattr(func, "__name__", str(func)))
        return await orig_run_in_threadpool(func, *args, **kwargs)

    payload = {
        "department_options": ["心内科"],
        "scope": {"scene": "final"},
        "clinical_qc": {"kpis": {"records_total": 1}},
    }

    def fake_get_luxian_0609_home(**kwargs):
        assert kwargs["priority_limit"] == 20
        return payload

    monkeypatch.setattr(workstation_router, "run_in_threadpool", tracked_run_in_threadpool)
    monkeypatch.setattr(
        workstation_router.default_workstation_aggregation_service,
        "get_luxian_0609_home",
        fake_get_luxian_0609_home,
    )

    resp = client.get(
        "/api/v1/workstation/qc-home?priority_limit=20",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    assert offloaded == ["fake_get_luxian_0609_home"]
