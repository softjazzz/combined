"""Super-Admin Batch 1：超级管理员跨用户批量质控诊断 + LX0609 trace 水合与 record_ref 精确匹配单测。"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.routers import qc_sichuan
from app.services import custom_qc_workspace_service as workspace_module
from app.services.case_identity import CaseRef
from app.services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    customer_safe_projection_key,
)
from app.services.luxian_0609_result_schema import CUSTOMER_SCHEMA_VERSION
from app.services.qc_workspace.canonical_result_store import keyed_ref


def _request() -> Any:
    return SimpleNamespace(headers={}, state=SimpleNamespace(trace_id="test-trace-id"))


def _admission_facts() -> dict[str, Any]:
    return {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "admission_record",
        "source_label": "入院记录",
        "timeliness_state": "within",
        "threshold_hours": 24,
        "anchor_time": "2026-09-01T08:00:00",
        "observed_time": "2026-09-01T09:00:00",
        "elapsed_hours": 1.0,
        "remaining_hours": 23.0,
    }


def _canonical_item(
    *,
    record_ref: str,
    rule_id: str,
    status: str,
    conclusion: str,
    reason_code: str = "within_deadline",
    customer_display_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": CUSTOMER_SCHEMA_VERSION,
        "record_ref": record_ref,
        "rule_id": rule_id,
        "rule_code": rule_id,
        "rule_name": "入院记录时限检查",
        "rule_version": "2026-06-09",
        "status": status,
        "result_status": status,
        "display_status": status,
        "is_compliant": True if status == "compliant" else False if status == "non_compliant" else None,
        "reason_code": reason_code,
        "conclusion": conclusion,
        "customer_display_facts": customer_display_facts if customer_display_facts is not None else _admission_facts(),
    }


# ---------------------------------------------------------------------------
# 1. Helper unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("user", "expected"),
    [
        ({"id": "u-sa", "roles": ["super_admin"]}, True),
        ({"id": "u-sa-single", "role": "super_admin"}, True),
        ({"id": "u-sync", "roles": ["sync_admin"]}, True),
        ({"id": "u-sync-upper", "roles": ["SYNC_ADMIN"]}, True),
        ({"id": "u-admin", "roles": ["admin"]}, False),
        ({"id": "u-mgr", "roles": ["qc_manager"]}, False),
        ({"id": "u-doc", "roles": ["doctor"]}, False),
        ({}, False),
        (None, False),
    ],
)
def test_is_batch_job_super_admin_and_owner_filter(user, expected):
    assert qc_sichuan._is_batch_job_super_admin(user) is expected
    if isinstance(user, dict) and user.get("id"):
        expected_filter = None if expected else user["id"]
        assert qc_sichuan._batch_job_owner_filter(user) == expected_filter


# ---------------------------------------------------------------------------
# 2. CustomQCWorkspaceService SQLite integration: created_by=None vs self
# ---------------------------------------------------------------------------


@pytest.fixture
def sqlite_workspace(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "_draft_schema", lambda: None)
    monkeypatch.setattr(workspace_module, "_sync_batch_job_parent_columns", lambda **_: None)
    service = CustomQCWorkspaceService()
    metadata = sa.MetaData()
    table = service._batch_job_table.to_metadata(metadata, schema=None)
    metadata.create_all(engine)
    service._batch_job_table = table
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(workspace_module, "_session", sessions)

    with engine.begin() as conn:
        conn.execute(
            table.insert(),
            [
                {
                    "id": "job-user-a-running",
                    "draft_id": "sichuan-rule-library",
                    "created_by": "user-a",
                    "status": "running",
                    "rule_code": "SC-BATCH",
                    "rule_name": "用户A运行中任务",
                    "scope": "final",
                    "scene": "final",
                    "job_kind": "leaf",
                    "total_records": 2,
                    "created_at": datetime(2026, 11, 1, 10, 0, 0),
                    "updated_at": datetime(2026, 11, 1, 10, 0, 0),
                    "filters_json": json.dumps({"rule_ids": ["SC-001"]}),
                    "summary_json": json.dumps({"rule_count": 1}),
                },
                {
                    "id": "job-user-b-failed",
                    "draft_id": "sichuan-rule-library",
                    "created_by": "user-b",
                    "status": "failed",
                    "rule_code": "SC-BATCH",
                    "rule_name": "用户B失败任务",
                    "scope": "final",
                    "scene": "final",
                    "job_kind": "leaf",
                    "total_records": 1,
                    "created_at": datetime(2026, 11, 1, 11, 0, 0),
                    "updated_at": datetime(2026, 11, 1, 11, 0, 0),
                    "filters_json": json.dumps({"rule_ids": ["SC-002"]}),
                    "summary_json": json.dumps({"rule_count": 1}),
                },
            ],
        )
    yield service
    engine.dispose()


def test_workspace_service_cross_user_super_admin_and_owner_isolation(sqlite_workspace):
    ws = sqlite_workspace

    # List & overview: created_by=None sees both; non-super-admin sees only own
    all_list = ws.list_batch_jobs(created_by=None, page=1, page_size=10)
    assert {item["id"] for item in all_list.items} == {"job-user-a-running", "job-user-b-failed"}
    assert all_list.total == 2

    all_overview = ws.list_batch_job_overviews(created_by=None, page=1, page_size=10)
    assert {item["id"] for item in all_overview.items} == {"job-user-a-running", "job-user-b-failed"}
    assert all_overview.total == 2

    user_a_list = ws.list_batch_jobs(created_by="user-a", page=1, page_size=10)
    assert [item["id"] for item in user_a_list.items] == ["job-user-a-running"]
    user_a_overview = ws.list_batch_job_overviews(created_by="user-a", page=1, page_size=10)
    assert [item["id"] for item in user_a_overview.items] == ["job-user-a-running"]

    # Get: created_by=None reads any user's job; wrong owner returns None
    assert ws.get_batch_job(job_id="job-user-b-failed", created_by=None)["created_by"] == "user-b"
    assert ws.get_batch_job(job_id="job-user-b-failed", created_by="user-a") is None

    # Update review report: wrong owner blocked, super-admin succeeds
    assert (
        ws.update_batch_job_review_report(
            job_id="job-user-b-failed",
            created_by="user-a",
            review_report={"scope": "luxian_0609_qc_v1", "findings": []},
        )
        is None
    )
    reviewed = ws.update_batch_job_review_report(
        job_id="job-user-b-failed",
        created_by=None,
        review_report={"scope": "luxian_0609_qc_v1", "findings": []},
    )
    assert reviewed is not None
    assert reviewed["summary"]["review_report"]["scope"] == "luxian_0609_qc_v1"

    # Cancel: wrong owner blocked, super-admin cancels user-a's running job
    assert ws.cancel_batch_job(job_id="job-user-a-running", created_by="user-b") is None
    canceled = ws.cancel_batch_job(job_id="job-user-a-running", created_by=None)
    assert canceled is not None
    assert canceled["status"] == "canceled"
    assert canceled["summary"]["cancelled_by"] == "super_admin"

    # Retry: wrong owner blocked, super-admin retries user-b's failed job
    assert ws.retry_batch_job(job_id="job-user-b-failed", created_by="user-a") is None
    retried = ws.retry_batch_job(job_id="job-user-b-failed", created_by=None)
    assert retried is not None
    assert retried["status"] == "queued"


# ---------------------------------------------------------------------------
# 3. Router endpoints: super-admin cross-user + trace LX0609 hydration/record_ref
# ---------------------------------------------------------------------------


class _CrossUserWorkspaceStub:
    def __init__(self, jobs: dict[str, dict[str, Any]], canonical_items: list[dict[str, Any]] | None = None):
        self.jobs = jobs
        self.canonical_items = canonical_items or []
        self.calls: list[tuple[str, Any]] = []

    def _match(self, job_id: str, created_by: str | None) -> dict[str, Any] | None:
        job = self.jobs.get(job_id)
        if not job:
            return None
        if created_by is not None and job.get("created_by") != created_by:
            return None
        return dict(job)

    def list_batch_jobs(self, *, created_by: str | None = None, **kwargs):
        self.calls.append(("list_batch_jobs", created_by))
        items = [
            dict(j)
            for j in self.jobs.values()
            if created_by is None or j.get("created_by") == created_by
        ]
        return SimpleNamespace(items=items, total=len(items), page=1, page_size=10)

    def list_batch_job_overviews(self, *, created_by: str | None = None, **kwargs):
        self.calls.append(("list_batch_job_overviews", created_by))
        items = [
            dict(j)
            for j in self.jobs.values()
            if created_by is None or j.get("created_by") == created_by
        ]
        return SimpleNamespace(items=items, total=len(items), page=1, page_size=10)

    def get_batch_job(self, *, job_id: str, created_by: str | None = None):
        self.calls.append(("get_batch_job", created_by))
        return self._match(job_id, created_by)

    def cancel_batch_job(self, *, job_id: str, created_by: str | None = None):
        self.calls.append(("cancel_batch_job", created_by))
        job = self._match(job_id, created_by)
        if not job:
            return None
        job["status"] = "canceled"
        return job

    def update_batch_job_review_report(self, *, job_id: str, created_by: str | None = None, review_report: dict):
        self.calls.append(("update_batch_job_review_report", created_by))
        job = self._match(job_id, created_by)
        if not job:
            return None
        job["summary"] = {**dict(job.get("summary") or {}), "review_report": review_report}
        return job

    def export_batch_job_html(self, *, job: dict[str, Any]) -> str:
        self.calls.append(("export_batch_job_html", job["id"]))
        return "<html>ok</html>"

    def list_record_result_case_refs(self, *, job_id: str):
        return [CaseRef("H1", "P1", "V1"), CaseRef("H1", "P2", "V2")]

    def collect_records(self, **kwargs):
        return [
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "mr_no": "MR001",
                "department": "心内科",
                "doctor": "张医生",
                "admission_date": "2026-09-01",
                "discharge_date": "2026-09-05",
            },
            {
                "institute_id": "H1",
                "patient_id": "P2",
                "visit_id": "V2",
                "mr_no": "MR002",
                "department": "骨科",
                "doctor": "李医生",
                "admission_date": "2026-09-02",
                "discharge_date": "2026-09-06",
            },
        ]

    def _load_batch_job_canonical_items(self, *, job: dict[str, Any], allow_partial: bool = False):
        self.calls.append(("_load_batch_job_canonical_items", job["id"]))
        return [dict(item) for item in self.canonical_items]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["super_admin", "sync_admin"])
async def test_super_admin_can_access_all_batch_job_endpoints_across_users(monkeypatch, role):
    proj_key = customer_safe_projection_key()
    ref1 = keyed_ref("rec", CaseRef("H1", "P1", "V1").as_key(), hmac_key=proj_key)
    ref2 = keyed_ref("rec", CaseRef("H1", "P2", "V2").as_key(), hmac_key=proj_key)

    canonical_items = [
        _canonical_item(record_ref=ref1, rule_id="LX0609-01-01-01", status="compliant", conclusion="病历一合规"),
        _canonical_item(record_ref=ref2, rule_id="LX0609-01-01-01", status="compliant", conclusion="病历二合规"),
    ]
    other_user_job = {
        "id": "job-other-owner",
        "draft_id": "sichuan-rule-library",
        "created_by": "other-user-999",
        "status": "completed",
        "rule_code": "LX0609",
        "rule_name": "泸县0609任务",
        "scope": "final",
        "total_records": 2,
        "filters": {
            "rule_set_key": "luxian_0609_qc_v1",
            "record_refs": [
                {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
                {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"},
            ],
        },
        "summary": {"rule_count": 1, "total_records": 2},
        # 故意留空原始 items，验证 /trace 必须走 _hydrate_luxian_canonical_batch_job_or_409
        "items": [],
        "failed_records": [],
        "rule_results": [],
    }
    ws = _CrossUserWorkspaceStub({"job-other-owner": other_user_job}, canonical_items=canonical_items)

    from app.services import saved_result_access

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda readonly=False: ws)
    monkeypatch.setattr(saved_result_access, "saved_result_institute_scope", lambda _uid: None)

    super_user = {"id": "sa-001", "roles": [role]}
    regular_admin = {"id": "regular-admin", "roles": ["admin"]}

    # 1. List & overview
    res_list = await qc_sichuan.list_workspace_batch_jobs(
        _request(),
        status=None,
        scope=None,
        q=None,
        executor_type=None,
        cache_hit=None,
        created_start_date=None,
        created_end_date=None,
        record_id=None,
        view=None,
        exclude_validation=False,
        page=1,
        page_size=10,
        current_user=super_user,
    )
    assert res_list["data"]["total"] == 1
    res_overview = await qc_sichuan.list_workspace_batch_jobs(
        _request(),
        status=None,
        scope=None,
        q=None,
        executor_type=None,
        cache_hit=None,
        created_start_date=None,
        created_end_date=None,
        record_id=None,
        view="overview",
        exclude_validation=False,
        page=1,
        page_size=10,
        current_user=super_user,
    )
    assert res_overview["data"]["total"] == 1

    # Non-super-admin cannot see other user's job
    res_list_regular = await qc_sichuan.list_workspace_batch_jobs(
        _request(),
        status=None,
        scope=None,
        q=None,
        executor_type=None,
        cache_hit=None,
        created_start_date=None,
        created_end_date=None,
        record_id=None,
        view=None,
        exclude_validation=False,
        page=1,
        page_size=10,
        current_user=regular_admin,
    )
    assert res_list_regular["data"]["total"] == 0

    # 2. Detail
    res_detail = await qc_sichuan.get_workspace_batch_job(
        _request(), "job-other-owner", current_user=super_user
    )
    assert res_detail["data"]["id"] == "job-other-owner"
    assert len(res_detail["data"]["items"]) == 2

    # 3. Record identities: super-admin gets coordinates; owner non-super-admin does NOT
    res_ids_sa = await qc_sichuan.get_workspace_batch_job_record_identities(
        _request(), "job-other-owner", current_user=super_user
    )
    id_by_ref = {item["record_ref"]: item for item in res_ids_sa["data"]["items"]}
    assert id_by_ref[ref2]["institute_id"] == "H1"
    assert id_by_ref[ref2]["patient_id"] == "P2"
    assert id_by_ref[ref2]["visit_id"] == "V2"

    owner_user = {"id": "other-user-999", "roles": ["admin"]}
    res_ids_owner = await qc_sichuan.get_workspace_batch_job_record_identities(
        _request(), "job-other-owner", current_user=owner_user
    )
    for item in res_ids_owner["data"]["items"]:
        assert "patient_id" not in item
        assert "visit_id" not in item
        assert "institute_id" not in item

    # 4. Debug snapshot
    res_debug = await qc_sichuan.get_workspace_batch_job_debug(
        _request(), "job-other-owner", rule_job_id=None, item_limit=30, current_user=super_user
    )
    assert res_debug["success"] is True

    # 5. Trace: LX0609 hydration + exact record_ref matching (second record, NOT first!)
    res_trace = await qc_sichuan.get_workspace_batch_job_result_trace(
        _request(),
        "job-other-owner",
        record_id=None,
        visit_id=None,
        record_ref=ref2,
        rule_id="LX0609-01-01-01",
        item_index=None,
        current_user=super_user,
    )
    assert res_trace["success"] is True
    assert res_trace["data"]["final_result"]["record_ref"] == ref2
    assert res_trace["data"]["final_result"]["status"] == "compliant"
    assert res_trace["data"]["final_result"]["conclusion"] == "病历二合规"

    # Trace with non-existent record_ref returns 404
    with pytest.raises(HTTPException) as exc_missing:
        await qc_sichuan.get_workspace_batch_job_result_trace(
            _request(),
            "job-other-owner",
            record_id=None,
            visit_id=None,
            record_ref="rec_" + "f" * 24,
            rule_id="LX0609-01-01-01",
            item_index=None,
            current_user=super_user,
        )
    assert exc_missing.value.status_code == 404

    # Non-super-admin cannot trace/debug/cancel/export/review other user's job
    for call in (
        qc_sichuan.get_workspace_batch_job_debug(
            _request(), "job-other-owner", rule_job_id=None, item_limit=30, current_user=regular_admin
        ),
        qc_sichuan.get_workspace_batch_job_result_trace(
            _request(),
            "job-other-owner",
            record_id=None,
            visit_id=None,
            record_ref=ref2,
            rule_id="LX0609-01-01-01",
            item_index=None,
            current_user=regular_admin,
        ),
        qc_sichuan.cancel_workspace_batch_job(_request(), "job-other-owner", current_user=regular_admin),
        qc_sichuan.export_workspace_batch_job(_request(), "job-other-owner", format="html", current_user=regular_admin),
        qc_sichuan.review_workspace_batch_job(_request(), "job-other-owner", current_user=regular_admin),
    ):
        with pytest.raises(HTTPException) as exc_denied:
            await call
        assert exc_denied.value.status_code == 404

    # 6. Export
    res_export = await qc_sichuan.export_workspace_batch_job(
        _request(), "job-other-owner", format="html", current_user=super_user
    )
    assert res_export.status_code == 200

    # 7. Review
    res_review = await qc_sichuan.review_workspace_batch_job(
        _request(), "job-other-owner", current_user=super_user
    )
    assert res_review["success"] is True

    # 8. Cancel
    res_cancel = await qc_sichuan.cancel_workspace_batch_job(
        _request(), "job-other-owner", current_user=super_user
    )
    assert res_cancel["success"] is True
    assert res_cancel["data"]["status"] == "canceled"
