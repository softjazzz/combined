"""Wave 1 离线回归单测：覆盖 qc_sichuan / custom_qc / medical_records / emr_render / records / workstation / qc_sample_pools。"""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database import connection as db_connection
from app.database.models.cdm import (
    AdmissionRecord,
    Diagnosis,
    DischargeRecord,
    MedicalRecordFrontpage,
    MrCost,
    MrSurgery,
)
from app.database.models.qc import QCDefect, QCResultBiz
from app.database.models.v36_reports import SysUser
from app.routers import (
    custom_qc,
    emr_render,
    medical_records_detail,
    medical_records_query,
    qc_sample_pools,
    qc_sichuan,
    records,
    workstation,
)
from app.services.medical_records import detail_service
from app.services.product_activation import require_product_activation


def _make_persistent_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    for table in (
        SysUser.__table__,
        MedicalRecordFrontpage.__table__,
        AdmissionRecord.__table__,
        DischargeRecord.__table__,
        Diagnosis.__table__,
        MrSurgery.__table__,
        MrCost.__table__,
        QCResultBiz.__table__,
        QCDefect.__table__,
    ):
        table.create(engine, checkfirst=True)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as session:
        session.add_all(
            [
                SysUser(id="u-admin", username="admin", display_name="管理员", role="admin", institute_id=None, is_active=True),
                SysUser(id="u-sync", username="sync_admin", display_name="同步管理员", role="sync_admin", institute_id="H1", is_active=True),
                SysUser(id="u-mgr-h1", username="mgr_h1", display_name="H1质控主管", role="qc_manager", institute_id="H1", is_active=True),
                SysUser(id="u-mgr-h2", username="mgr_h2", display_name="H2质控主管", role="qc_manager", institute_id="H2", is_active=True),
                SysUser(id="u-staff-h1", username="staff_h1", display_name="H1质控员", role="qc_staff", institute_id="H1", is_active=True),
            ]
        )
    monkeypatch.setattr(db_connection, "SessionLocal", sessions)
    monkeypatch.setattr(db_connection, "engine", engine)
    monkeypatch.setattr(records, "SessionLocal", sessions)
    monkeypatch.setattr(detail_service, "engine", engine)
    monkeypatch.setattr(detail_service, "_session_factory", sessions)
    return engine, sessions


@pytest.fixture
def persistent_db(monkeypatch):
    engine, sessions = _make_persistent_db(monkeypatch)
    yield engine, sessions
    engine.dispose()


def _user_dict(user_id: str, role: str, institute_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": user_id,
        "email": f"{user_id}@test.local",
        "roles": [role],
        "role": role,
    }
    if institute_id is not None:
        payload["institute_id"] = institute_id
    return payload


# ============================================================================
# 1. qc_sichuan.py: P0-4, P1-B4, P2-B2, P2-E2
# ============================================================================


class _FakeClient:
    def __init__(self) -> None:
        self.model = "default-model"
        self.temperature = 0.1
        self.max_tokens = 512
        self.api_endpoint = "http://internal-llm.local/v1"


class _FakeQCService:
    def __init__(self) -> None:
        self.client = _FakeClient()
        self.seen_configs: list[tuple[str, float, int]] = []

    async def evaluate_document_fast(self, **_kwargs):
        self.seen_configs.append((self.client.model, self.client.temperature, self.client.max_tokens))
        return {"status": "success", "model_used": self.client.model}

    async def evaluate_document(self, **_kwargs):
        self.seen_configs.append((self.client.model, self.client.temperature, self.client.max_tokens))
        return {
            "evaluation_summary": {"total_rules": 1, "compliant_rules": 1, "issues_found": 0, "compliance_rate": 100.0},
            "evaluation_results": [],
            "token_usage": {"total_tokens": 100},
            "api_time": 0.2,
        }

    async def evaluate_rule_for_visit(self, **_kwargs):
        self.seen_configs.append((self.client.model, self.client.temperature, self.client.max_tokens))
        return {"rule_id": _kwargs["rule_id"], "model_used": self.client.model}

    def stats(self):
        return {
            "total_calls": 10,
            "success_calls": 9,
            "error_calls": 1,
            "success_rate": 0.9,
            "avg_api_time": 1.2,
            "total_api_time": 12.0,
            "total_tokens": 1000,
        }


def test_qc_sichuan_p1_b4_no_global_client_mutation_and_admin_only_override(persistent_db, monkeypatch):
    fake_service = _FakeQCService()
    app = FastAPI()
    app.include_router(qc_sichuan.router)
    current = {"user": _user_dict("u-mgr-h1", "qc_manager", "H1")}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: fake_service
    monkeypatch.setattr(qc_sichuan, "_enforce_sc_source_guard", lambda *a, **kw: None)
    client = TestClient(app)

    # 非管理员覆写 model / temperature / max_tokens 应返回 403，且全局单例不被修改
    r_fast = client.post(
        "/api/v1/qc/sichuan/evaluate-fast",
        json={"document_id": "D1", "document_content": "正文", "model": "evil-model"},
    )
    assert r_fast.status_code == 403
    assert fake_service.client.model == "default-model"

    r_eval = client.post(
        "/api/v1/qc/sichuan/evaluate",
        json={
            "document_id": "D1",
            "document_content": "正文",
            "temperature": 0.95,
            "max_tokens": 4096,
            "persist": False,
        },
    )
    assert r_eval.status_code == 403
    assert fake_service.client.temperature == 0.1
    assert fake_service.client.max_tokens == 512

    # 管理员覆写仅作用于本次请求浅拷贝，全局单例保持原值
    current["user"] = _user_dict("u-admin", "admin")
    r_admin_fast = client.post(
        "/api/v1/qc/sichuan/evaluate-fast",
        json={"document_id": "D1", "document_content": "正文", "model": "ab-model"},
    )
    assert r_admin_fast.status_code == 200
    assert r_admin_fast.json()["model_used"] == "ab-model"
    assert fake_service.client.model == "default-model"

    r_admin_eval = client.post(
        "/api/v1/qc/sichuan/evaluate",
        json={
            "document_id": "D1",
            "document_content": "正文",
            "model": "ab-model-2",
            "temperature": 0.7,
            "max_tokens": 2048,
            "persist": False,
        },
    )
    assert r_admin_eval.status_code == 200
    assert fake_service.seen_configs[-1] == ("ab-model-2", 0.7, 2048)
    assert fake_service.client.model == "default-model"
    assert fake_service.client.temperature == 0.1
    assert fake_service.client.max_tokens == 512


def test_qc_sichuan_p0_4_evaluate_bundle_and_rule_for_visit_enforce_role_and_institute(persistent_db, monkeypatch):
    fake_service = _FakeQCService()
    app = FastAPI()
    app.include_router(qc_sichuan.router)
    current = {"user": _user_dict("u-staff-h1", "qc_staff", "H1")}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: fake_service
    monkeypatch.setattr(qc_sichuan, "_enforce_sc_source_guard", lambda *a, **kw: None)

    async def _fake_bundle(**kwargs):
        return {"ok": True, "institute_id": kwargs.get("institute_id")}

    monkeypatch.setattr(qc_sichuan, "evaluate_running_final_bundle", _fake_bundle)
    client = TestClient(app)

    # qc_staff 无权调用 evaluate-bundle / evaluate-rule-for-visit
    assert client.post(
        "/api/v1/qc/sichuan/evaluate-bundle",
        json={"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
    ).status_code == 403
    assert client.post(
        "/api/v1/qc/sichuan/evaluate-rule-for-visit",
        json={"rule_id": "SC-001", "institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
    ).status_code == 403

    # H1 质控主管跨院请求 H2 -> 403
    current["user"] = _user_dict("u-mgr-h1", "qc_manager", "H1")
    assert client.post(
        "/api/v1/qc/sichuan/evaluate-bundle",
        json={"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"},
    ).status_code == 403
    assert client.post(
        "/api/v1/qc/sichuan/evaluate-rule-for-visit",
        json={"rule_id": "SC-001", "institute_id": "H2", "patient_id": "P2", "visit_id": "V2"},
    ).status_code == 403
    # 非全局主管未传 institute_id 同样 fail-closed 403
    assert client.post(
        "/api/v1/qc/sichuan/evaluate-bundle",
        json={"bundle_input": {"documents": []}},
    ).status_code == 403

    # 本院 H1 放行
    assert client.post(
        "/api/v1/qc/sichuan/evaluate-bundle",
        json={"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
    ).status_code == 200
    assert client.post(
        "/api/v1/qc/sichuan/evaluate-rule-for-visit",
        json={"rule_id": "SC-001", "institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
    ).status_code == 200


def test_qc_sichuan_p0_4_batch_jobs_and_shared_pool_and_export_institute_scope(persistent_db, monkeypatch):
    fake_service = _FakeQCService()
    app = FastAPI()
    app.include_router(qc_sichuan.router)
    current = {"user": _user_dict("u-staff-h1", "qc_staff", "H1")}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.dependency_overrides[require_product_activation] = lambda: current["user"]
    app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: fake_service
    monkeypatch.setattr(qc_sichuan, "_enforce_sc_source_guard", lambda *a, **kw: None)

    class _Workspace:
        def __init__(self):
            self.collect_calls = []

        def collect_records(self, **kwargs):
            self.collect_calls.append(kwargs)
            return []

        def get_batch_job(self, *, job_id: str, created_by: str):
            if job_id == "job-h2" and created_by in {"u-admin", "u-mgr-h1"}:
                return {
                    "id": job_id,
                    "draft_id": "sichuan-rule-library",
                    "rule_code": "SC-BATCH",
                    "status": "completed",
                    "created_by": created_by,
                    "filters": {
                        "sample_pool_id": "pool-shared",
                        "source": "manual_problem_sample_pool",
                        "record_refs": [{"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"}],
                    },
                    "items": [{"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"}],
                }
            if job_id == "job-h1" and created_by == "u-admin":
                return {
                    "id": job_id,
                    "draft_id": "sichuan-rule-library",
                    "rule_code": "SC-BATCH",
                    "status": "completed",
                    "created_by": created_by,
                    "filters": {
                        "sample_pool_id": "pool-shared-h1",
                        "source": "manual_problem_sample_pool",
                        "record_refs": [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
                    },
                    "items": [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
                }
            return None

    ws = _Workspace()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: ws)
    monkeypatch.setattr(
        qc_sichuan,
        "_shared_sample_pool_service",
        lambda: SimpleNamespace(
            resolve_unique_pool_id_for_latest_job=lambda job_id: (
                ("pool-shared", "u-admin") if job_id == "job-h2" else ("pool-shared-h1", "u-admin")
            )
        ),
    )
    client = TestClient(app)

    # 1) qc_staff 建单 -> 403
    assert client.post(
        "/api/v1/qc/sichuan/workspace/batch-jobs",
        json={
            "rule_ids": ["SC-001"],
            "record_refs": [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
        },
    ).status_code == 403

    # 2) H1 主管提交 H2 record_refs 建单 -> 403（且不进入 collect_records）
    current["user"] = _user_dict("u-mgr-h1", "qc_manager", "H1")
    r_cross = client.post(
        "/api/v1/qc/sichuan/workspace/batch-jobs",
        json={
            "rule_ids": ["SC-001"],
            "record_refs": [{"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"}],
        },
    )
    assert r_cross.status_code == 403
    assert ws.collect_calls == []

    # 3) _resolve_shared_sample_pool_latest_job 拦截非全局 H1 主管跨院读取 H2 共享样本池任务
    assert qc_sichuan._resolve_shared_sample_pool_latest_job(
        workspace=ws, job_id="job-h2", current_user=_user_dict("u-mgr-h1", "qc_manager", "H1")
    ) is None
    # H1 主管可读纯 H1 共享样本池任务
    resolved_h1 = qc_sichuan._resolve_shared_sample_pool_latest_job(
        workspace=ws, job_id="job-h1", current_user=_user_dict("u-mgr-h1", "qc_manager", "H1")
    )
    assert resolved_h1 is not None and resolved_h1["id"] == "job-h1"
    # 全局 admin 可读任意共享样本池任务
    resolved_admin = qc_sichuan._resolve_shared_sample_pool_latest_job(
        workspace=ws, job_id="job-h2", current_user=_user_dict("u-admin", "admin")
    )
    assert resolved_admin is not None and resolved_admin["id"] == "job-h2"

    # 4) H1 主管导出含 H2 病历的旧任务 -> 403
    r_export = client.get("/api/v1/qc/sichuan/workspace/batch-jobs/job-h2/export")
    assert r_export.status_code == 403


def test_qc_sichuan_p2_b2_filtered_export_pushes_institute_scope_to_query_layer(persistent_db, monkeypatch):
    app = FastAPI()
    app.include_router(qc_sichuan.router)
    app.dependency_overrides[get_current_user] = lambda: _user_dict("u-mgr-h1", "qc_manager", "H1")

    class _MultiInstituteWorkspace:
        def __init__(self):
            self.count_calls = []
            self.collect_calls = []

        def count_records(self, **kwargs):
            self.count_calls.append(kwargs)
            if kwargs.get("institute_id") == "H1":
                return 1
            return 1500  # 多院区总量超过 1000，若未下推会误触 422

        def collect_records(self, **kwargs):
            self.collect_calls.append(kwargs)
            if kwargs.get("institute_id") == "H1":
                return [
                    {
                        "institute_id": "H1",
                        "patient_id": "P1",
                        "visit_id": "V1",
                        "patient_name": "患者1",
                        "department": "心内科",
                        "doctor": "张医生",
                    }
                ]
            return [
                {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
                {"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"},
            ]

        def build_latest_luxian_0609_record_result_dtos(self, *, record_refs):
            return {
                (ref["institute_id"], ref["patient_id"], ref["visit_id"]): {
                    "schema_version": "lx0609-single-record-result-v1",
                    "state": "ready",
                    "record_ref": "r1",
                    "job_id": "j1",
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                    "expected_rule_count": 1,
                    "result_rule_count": 1,
                    "is_complete": True,
                    "items": [],
                }
                for ref in record_refs
            }

    ws = _MultiInstituteWorkspace()
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: ws)
    client = TestClient(app)

    resp = client.post("/api/v1/qc/sichuan/workspace/records/export", json={"scope": "final"})
    assert resp.status_code == 200
    assert ws.count_calls[0]["institute_id"] == "H1"
    assert ws.collect_calls[0]["institute_id"] == "H1"


def test_qc_sichuan_p2_e2_history_end_date_inclusive_and_stats_hardening(persistent_db, monkeypatch, tmp_path):
    fake_service = _FakeQCService()
    app = FastAPI()
    app.include_router(qc_sichuan.router)
    current = {"user": _user_dict("u-mgr-h1", "qc_manager", "H1")}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: fake_service
    monkeypatch.setattr(qc_sichuan, "__file__", str(tmp_path / "app" / "routers" / "qc_sichuan.py"))

    storage_dir = tmp_path / "app" / "storage" / "qc_results"
    storage_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("00000000-0000-0000-0000-000000000001.json", {"id": "r1", "created_by": "u-mgr-h1", "created_at": "2026-07-31T14:20:00+00:00", "payload": {}}),
        ("00000000-0000-0000-0000-000000000002.json", {"id": "r2", "created_by": "u-mgr-h1", "created_at": "2026-08-01T01:00:00+00:00", "payload": {}}),
        ("00000000-0000-0000-0000-000000000003.json", {"id": "r3", "created_by": "u-mgr-h1", "payload": {}}),  # 缺失 created_at 不应 TypeError
    ):
        (storage_dir / name).write_text(json.dumps(payload), encoding="utf-8")

    client = TestClient(app)
    hist = client.get("/api/v1/qc/sichuan/results/history", params={"start_date": "2026-07-31", "end_date": "2026-07-31"})
    assert hist.status_code == 200
    ids = [row["id"] for row in hist.json()["data"]["records"]]
    assert ids == ["r1"]

    # /stats 仅限管理员，且不暴露 api_endpoint 和假 optimization_achievements
    assert client.get("/api/v1/qc/sichuan/stats").status_code == 403
    current["user"] = _user_dict("u-admin", "admin")
    stats_resp = client.get("/api/v1/qc/sichuan/stats")
    assert stats_resp.status_code == 200
    body = stats_resp.json()
    assert "optimization_achievements" not in body
    assert "api_endpoint" not in body["real_time_status"]


# ============================================================================
# 2. custom_qc.py: P0-4 & P2-A2
# ============================================================================


def test_custom_qc_p0_4_workspace_endpoints_enforce_institute_scope(persistent_db):
    class _Workspace:
        def __init__(self):
            self.collect_calls = []

        def list_records(self, **_kwargs):
            # 模拟尚未支持 institute_id 的旧签名，验证路由层回退到 collect_records(..., institute_id=...)
            if "institute_id" in _kwargs:
                raise TypeError("unexpected keyword argument 'institute_id'")
            return SimpleNamespace(items=[], total=0, page=1, page_size=20)

        def get_record_filters(self, **_kwargs):
            if "institute_id" in _kwargs:
                raise TypeError("unexpected keyword argument 'institute_id'")
            return {"departments": ["心内科", "外院科"], "doctors": []}

        def collect_records(self, **kwargs):
            self.collect_calls.append(kwargs)
            all_rows = [
                {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "department": "心内科", "doctor": "王医生", "admission_date": "2026-07-01"},
                {"institute_id": "H2", "patient_id": "P2", "visit_id": "V2", "department": "神经科", "doctor": "李医生", "admission_date": "2026-07-02"},
            ]
            inst = kwargs.get("institute_id")
            if inst:
                all_rows = [r for r in all_rows if r["institute_id"] == inst]
            if kwargs.get("record_ids"):
                all_rows = [r for r in all_rows if r["visit_id"] in kwargs["record_ids"]]
            return all_rows

        def get_draft(self, *, draft_id: str, created_by: str):
            return {"id": draft_id, "rule_code": "CUST-1", "name": "规则1", "prompt_template": "检查", "scene": "final"}

        def hydrate_records_with_medical_text(self, recs):
            return [{**r, "medical_text": "正文"} for r in recs]

        def get_batch_job(self, *, job_id: str, created_by: str):
            return {
                "id": job_id,
                "draft_id": "d1",
                "created_by": created_by,
                "status": "completed",
                "filters": {"record_refs": [{"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"}]},
                "items": [],
            }

    ws = _Workspace()
    app = FastAPI()
    app.include_router(custom_qc.router)
    app.dependency_overrides[get_current_user] = lambda: _user_dict("u-mgr-h1", "qc_manager", "H1")
    app.dependency_overrides[require_product_activation] = lambda: _user_dict("u-mgr-h1", "qc_manager", "H1")
    app.dependency_overrides[custom_qc.get_workspace_service] = lambda: ws
    app.dependency_overrides[custom_qc.get_custom_qc_service] = lambda: _FakeQCService()
    client = TestClient(app)

    # 列病历仅返回 H1
    r_list = client.get("/api/v1/custom-qc/workspace/records")
    assert r_list.status_code == 200
    assert [row["institute_id"] for row in r_list.json()["data"]["items"]] == ["H1"]

    # 筛选项仅返回 H1 科室与医生
    r_filters = client.get("/api/v1/custom-qc/workspace/filters")
    assert r_filters.status_code == 200
    assert r_filters.json()["data"]["departments"] == ["心内科"]

    # 单测/批测尝试水合他院 V2 -> 403
    assert client.post(
        "/api/v1/custom-qc/workspace/test",
        json={"draft_id": "d1", "records": [{"record_id": "V2", "visit_id": "V2"}]},
    ).status_code == 403
    assert client.post(
        "/api/v1/custom-qc/workspace/test/batch",
        json={"draft_id": "d1", "records": [{"institute_id": "H2", "patient_id": "P2", "record_id": "V2", "visit_id": "V2"}]},
    ).status_code == 403

    # 批量建单提交他院 H2 -> 403
    assert client.post(
        "/api/v1/custom-qc/workspace/batch-jobs",
        json={"draft_id": "d1", "record_refs": [{"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"}]},
    ).status_code == 403

    # 查看 / 导出 / 重试含他院记录的批量任务 -> 403
    assert client.get("/api/v1/custom-qc/workspace/batch-jobs/job-h2").status_code == 403
    assert client.get("/api/v1/custom-qc/workspace/batch-jobs/job-h2/export").status_code == 403
    assert client.post("/api/v1/custom-qc/workspace/batch-jobs/job-h2/retry").status_code == 403


@pytest.mark.asyncio
async def test_custom_qc_p2_a2_background_job_offloads_sync_db_to_worker_thread(monkeypatch):
    main_thread_id = threading.get_ident()
    observed_threads: dict[str, int] = {}
    cancel_check_calls = {"count": 0}
    full_fetch_calls = {"count": 0}

    class _ThreadedWorkspace:
        def get_batch_job_for_processing(self, *, job_id: str):
            full_fetch_calls["count"] += 1
            observed_threads["get_job"] = threading.get_ident()
            return {
                "id": job_id,
                "draft_id": "d1",
                "draft_ids": ["d1"],
                "created_by": "u-admin",
                "scope": "final",
                "status": "queued",
                "filters": {"record_refs": [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}]},
            }

        def is_batch_job_canceled_or_missing(self, *, job_id: str):
            cancel_check_calls["count"] += 1
            observed_threads["cancel_check"] = threading.get_ident()
            return False

        def mark_batch_job_running(self, *, job_id: str):
            observed_threads["mark_running"] = threading.get_ident()
            return True

        def get_draft(self, *, draft_id: str, created_by: str):
            return {"id": draft_id, "rule_code": "CUST-1", "name": "规则1", "prompt_template": "检查", "scene": "final"}

        def collect_records(self, **_kwargs):
            observed_threads["collect"] = threading.get_ident()
            return [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "record_id": "V1"}]

        def hydrate_records_with_medical_text(self, recs):
            observed_threads["hydrate"] = threading.get_ident()
            return [{**r, "medical_text": "病历全文"} for r in recs]

        def update_batch_job_progress(self, **_kwargs):
            observed_threads["progress"] = threading.get_ident()

        def complete_batch_job(self, **_kwargs):
            observed_threads["complete"] = threading.get_ident()

        def save_last_test_summary(self, **_kwargs):
            observed_threads["save_summary"] = threading.get_ident()

        def fail_batch_job(self, **_kwargs):
            raise AssertionError("should not fail")

    monkeypatch.setattr(custom_qc, "get_workspace_service", lambda: _ThreadedWorkspace())

    async def _fake_service():
        return _FakeQCService()

    async def _fake_eval(**_kwargs):
        return {"status": "compliant", "is_compliant": True, "performance": {"token_usage": 10, "processing_time": 0.1}, "metadata": {}}

    monkeypatch.setattr(custom_qc, "create_custom_qc_service", _fake_service)
    monkeypatch.setattr(custom_qc, "evaluate_inline_rule_orchestrated", _fake_eval)

    await custom_qc._run_workspace_batch_job("job-thread-1")

    for step_name in ("get_job", "mark_running", "collect", "hydrate", "progress", "cancel_check", "complete", "save_summary"):
        assert observed_threads[step_name] != main_thread_id, f"{step_name} ran on event loop thread"
    assert cancel_check_calls["count"] >= 2
    assert full_fetch_calls["count"] == 2  # 仅入口与领取时读取，循环内不再全量反序列化


# ============================================================================
# 3. P1-B1 + P2-B1: medical_records_query, detail_service, medical_records_detail,
#    emr_render, records, workstation
# ============================================================================


def test_p1_b1_p2_b1_detail_service_and_medical_records_isolation(persistent_db):
    engine, sessions = persistent_db
    with sessions.begin() as session:
        session.add_all(
            [
                MedicalRecordFrontpage(
                    institute_id="H1", patient_id="P-SHARED", visit_id="V-SHARED",
                    mr_no="MR-DUP", name="H1患者", discharge_dept_name="心内科",
                    discharge_datetime=datetime(2026, 7, 10),
                ),
                MedicalRecordFrontpage(
                    institute_id="H2", patient_id="P-SHARED", visit_id="V-SHARED",
                    mr_no="MR-DUP", name="H2患者", discharge_dept_name="骨科",
                    discharge_datetime=datetime(2026, 7, 11),
                ),
                Diagnosis(diagnosis_id="D-H1", institute_id="H1", patient_id="P-SHARED", visit_id="V-SHARED", diagnosis_type="主要诊断", diagnosis_no=1, diagnosis_name="H1诊断"),
                Diagnosis(diagnosis_id="D-H2", institute_id="H2", patient_id="P-SHARED", visit_id="V-SHARED", diagnosis_type="主要诊断", diagnosis_no=1, diagnosis_name="H2诊断"),
            ]
        )
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO admission_record (institute_id, patient_id, visit_id, chief_complaint) "
            "VALUES ('H1', 'P-SHARED', 'V-SHARED', 'H1主诉'), ('H2', 'P-SHARED', 'V-SHARED', 'H2主诉')"
        ))

    # detail_service: 裸 visit_id / mr_no / frontpage_sheet 在跨院重号时 fail-closed 返回 409
    with pytest.raises(Exception) as exc_mr:
        detail_service.get_frontpage_by_mr_no("MR-DUP")
    assert getattr(exc_mr.value, "status_code", None) == 409

    with pytest.raises(Exception) as exc_docs:
        detail_service.get_documents("V-SHARED", session_factory=sessions)
    assert getattr(exc_docs.value, "status_code", None) == 409

    with pytest.raises(Exception) as exc_sheet:
        detail_service.get_frontpage_sheet("P-SHARED", "V-SHARED", session_factory=sessions)
    assert getattr(exc_sheet.value, "status_code", None) == 409

    # 指定 institute_id="H1" 精准隔离，绝不混读 H2
    h1_docs = detail_service.get_documents("V-SHARED", session_factory=sessions, institute_id="H1", patient_id="P-SHARED")
    h1_texts = [d["content"] for d in h1_docs["documents"] if d.get("has_content")]
    assert any("H1主诉" in t for t in h1_texts)
    assert all("H2主诉" not in t for t in h1_texts)

    h1_sheet = detail_service.get_frontpage_sheet("P-SHARED", "V-SHARED", session_factory=sessions, institute_id="H1")
    assert [d["diagnosis_name"] for d in h1_sheet["diagnoses"]] == ["H1诊断"]

    # medical_records_detail / medical_records_query 路由级隔离
    app = FastAPI()
    app.include_router(medical_records_query.router, prefix="/api/medical-records")
    app.include_router(medical_records_detail.router, prefix="/api/medical-records")
    app.dependency_overrides[get_current_user] = lambda: _user_dict("u-staff-h1", "qc_staff", "H1")
    client = TestClient(app)

    assert client.get("/api/medical-records/frontpage/H2/P-SHARED/V-SHARED").status_code == 403
    assert client.get("/api/medical-records/diagnoses/H2/P-SHARED/V-SHARED").status_code == 403
    assert client.get("/api/medical-records/surgeries/H2/P-SHARED/V-SHARED").status_code == 403
    assert client.get("/api/medical-records/cost/H2/P-SHARED/V-SHARED").status_code == 403
    assert client.get("/api/medical-records/record-content/H2/P-SHARED/V-SHARED").status_code == 403
    assert client.get("/api/medical-records/documents/V-SHARED", params={"institute_id": "H2"}).status_code == 403

    depts_resp = client.get("/api/medical-records/departments")
    assert depts_resp.status_code == 200
    assert depts_resp.json() == ["心内科"]

    docs_resp = client.get("/api/medical-records/documents/V-SHARED")
    assert docs_resp.status_code == 200
    contents = [d["content"] for d in docs_resp.json()["documents"] if d.get("has_content")]
    assert any("H1主诉" in c for c in contents)
    assert all("H2主诉" not in c for c in contents)


def test_p1_b1_emr_render_enforces_persistent_institute(persistent_db, monkeypatch):
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(
        emr_render,
        "_load_documents_from_bundle",
        lambda **kwargs: (captured.append(kwargs) or {"documents": [], "documents_tree": [], "empty_reason": ""}),
    )
    app = FastAPI()
    app.include_router(emr_render.router)
    app.dependency_overrides[get_current_user] = lambda: _user_dict("u-mgr-h1", "qc_manager", "H1")
    client = TestClient(app)

    assert client.get("/api/v1/emr/V1/documents", params={"institute_id": "H2"}).status_code == 403
    assert client.get("/api/v1/emr/V1/render", params={"institute_id": "H2"}).status_code == 403

    ok_resp = client.get("/api/v1/emr/V1/documents")
    assert ok_resp.status_code == 200
    assert captured[-1]["institute_id"] == "H1"


def test_p1_b1_p2_b1_records_final_isolates_institute_and_blocks_cross_institute_visit_join(persistent_db):
    _engine, sessions = persistent_db
    with sessions.begin() as session:
        session.add_all(
            [
                MedicalRecordFrontpage(
                    institute_id="H1", patient_id="P1", visit_id="V-COLLIDE",
                    name="H1患者", discharge_dept_name="心内科",
                    discharge_datetime=datetime(2026, 7, 15),
                ),
                MedicalRecordFrontpage(
                    institute_id="H2", patient_id="P2", visit_id="V-COLLIDE",
                    name="H2患者", discharge_dept_name="骨科",
                    discharge_datetime=datetime(2026, 7, 16),
                ),
                QCDefect(
                    id="def-collide", record_id="V-COLLIDE", rule_name="测试规则",
                    category="completeness", severity="major", description="跨院同号缺陷",
                    status="pending", created_at=datetime(2026, 7, 17), updated_at=datetime(2026, 7, 17),
                ),
            ]
        )

    app = FastAPI()
    app.include_router(records.router)
    app.dependency_overrides[get_current_user] = lambda: _user_dict("u-mgr-h1", "qc_manager", "H1")
    client = TestClient(app)

    resp = client.get("/api/v1/records/final")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["institute_id"] == "H1"
    # 跨院重号 V-COLLIDE 不应被裸 record_id 缺陷误关联
    assert items[0]["defect_count"] == 0
    assert items[0]["status"] == "pending"

    assert client.get("/api/v1/records/final", params={"institute_id": "H2"}).status_code == 403


def test_p1_b1_p2_b1_workstation_scope_and_snapshot_collision(persistent_db, monkeypatch):
    _engine, sessions = persistent_db
    with sessions.begin() as session:
        session.add_all(
            [
                MedicalRecordFrontpage(institute_id="H1", patient_id="P1", visit_id="V-COLLIDE", name="H1患者"),
                MedicalRecordFrontpage(institute_id="H2", patient_id="P2", visit_id="V-COLLIDE", name="H2患者"),
                MedicalRecordFrontpage(institute_id="H2", patient_id="P9", visit_id="V-H2-ONLY", name="H2独有患者"),
            ]
        )

    captured_scopes: list[Any] = []
    monkeypatch.setattr(
        workstation.default_workstation_aggregation_service,
        "get_luxian_0609_home",
        lambda **kwargs: (captured_scopes.append(kwargs.get("case_scope")) or {"department_options": []}),
    )
    monkeypatch.setattr(
        workstation.default_workstation_aggregation_service,
        "get_frontpage_worklist",
        lambda **kwargs: {
            "items": [
                {"visit_id": "V1", "institute_id": "H1"},
                {"visit_id": "V2", "institute_id": "H2"},
            ],
            "total": 2,
        },
    )
    monkeypatch.setattr(
        workstation.default_workstation_aggregation_service,
        "get_frontpage_snapshot",
        lambda visit_id, **kwargs: {"visit_id": visit_id, "institute_id": "H1", "patient_id": "P1"},
    )

    app = FastAPI()
    app.include_router(workstation.router)
    current = {"user": _user_dict("u-mgr-h1", "qc_manager", "H1")}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    client = TestClient(app)

    # /qc-home 下推 InstituteCaseScope("H1")
    assert client.get("/api/v1/workstation/qc-home").status_code == 200
    assert captured_scopes[-1].institute_id == "H1"

    # worklist 过滤掉 H2
    wl = client.get("/api/v1/workstation/frontpage-qc/worklist")
    assert wl.status_code == 200
    assert [i["institute_id"] for i in wl.json()["data"]["items"]] == ["H1"]

    # H1 主管访问 H2 独有 snapshot -> 403
    assert client.get("/api/v1/workstation/frontpage-qc/V-H2-ONLY/snapshot").status_code == 403
    assert client.get("/api/v1/workstation/frontpage-qc/V-COLLIDE/snapshot", params={"institute_id": "H2"}).status_code == 403

    # 全局 admin 传裸重号 visit_id（跨院冲突）-> fail-closed 409
    current["user"] = _user_dict("u-admin", "admin")
    assert client.get("/api/v1/workstation/frontpage-qc/V-COLLIDE/snapshot").status_code == 409
    # 提供完整三坐标 -> 200
    assert client.get(
        "/api/v1/workstation/frontpage-qc/V-COLLIDE/snapshot",
        params={"institute_id": "H1", "patient_id": "P1"},
    ).status_code == 200


# ============================================================================
# 4. qc_sample_pools.py: P1-B1 + P2-F3
# ============================================================================


def test_qc_sample_pools_p1_b1_institute_isolation_and_manual_sheet_confinement(persistent_db, monkeypatch, tmp_path):
    upload_dir = tmp_path / "allowed_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    outside_file = tmp_path / "outside_secret.xlsx"
    outside_file.write_bytes(b"fake-excel-outside")
    inside_file = upload_dir / "allowed.xlsx"
    inside_file.write_bytes(b"fake-excel-inside")

    class _PoolSvc:
        def __init__(self):
            self.pools = {
                "pool-h1": {"id": "pool-h1", "name": "H1池", "created_by": "u-mgr-h1"},
                "pool-h2": {"id": "pool-h2", "name": "H2池", "created_by": "u-mgr-h2"},
            }

        def list_pools(self, *, page: int, page_size: int, query=None):
            return SimpleNamespace(items=list(self.pools.values()), total=len(self.pools), page=page, page_size=page_size)

        def get_pool(self, *, pool_id: str):
            return self.pools.get(pool_id)

        def delete_pool(self, *, pool_id: str):
            return {"deleted": True, "pool_id": pool_id}

        def list_pool_items(self, *, pool_id: str, **_kwargs):
            inst = "H1" if pool_id == "pool-h1" else "H2"
            return SimpleNamespace(items=[{"id": "i1", "matched_institute_id": inst}], total=1, page=1, page_size=20)

        def create_pool_with_items(self, **kwargs):
            return {"id": "pool-new", "name": kwargs["name"], "source_file": kwargs["source_file"]}

    monkeypatch.setattr(qc_sample_pools, "_service", lambda: _PoolSvc())
    monkeypatch.setattr(qc_sample_pools, "_IMPORT_UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(qc_sample_pools, "load_manual_case_rows_from_excel", lambda **kwargs: [{"row": 1}])

    app = FastAPI()
    app.include_router(qc_sample_pools.router)
    current = {"user": _user_dict("u-mgr-h1", "qc_manager", "H1")}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    client = TestClient(app)

    # 非全局 H1 主管仅可见 H1 池，不可读/删 H2 池
    r_list = client.get("/api/v1/qc/sample-pools")
    assert r_list.status_code == 200
    assert [p["id"] for p in r_list.json()["data"]["items"]] == ["pool-h1"]
    assert client.get("/api/v1/qc/sample-pools/pool-h2").status_code == 403
    assert client.delete("/api/v1/qc/sample-pools/pool-h2").status_code == 403
    assert client.get("/api/v1/qc/sample-pools/pool-h1").status_code == 200

    # import-manual-sheet 仅限 admin/super_admin
    assert client.post(
        "/api/v1/qc/sample-pools/import-manual-sheet",
        json={"pool_name": "测试", "source_file": str(inside_file)},
    ).status_code == 403

    # admin 路径穿越读取允许目录外文件 -> 403
    current["user"] = _user_dict("u-admin", "admin")
    assert client.post(
        "/api/v1/qc/sample-pools/import-manual-sheet",
        json={"pool_name": "穿越", "source_file": str(outside_file)},
    ).status_code == 403
    assert client.post(
        "/api/v1/qc/sample-pools/import-manual-sheet",
        json={"pool_name": "穿越2", "source_file": "../outside_secret.xlsx"},
    ).status_code == 403

    # admin 读取允许目录内合法文件 -> 200
    ok = client.post(
        "/api/v1/qc/sample-pools/import-manual-sheet",
        json={"pool_name": "合法", "source_file": "allowed.xlsx"},
    )
    assert ok.status_code == 200


def test_qc_sample_pools_p2_f3_import_upload_enforces_size_limit_and_cleans_temp_file(persistent_db, monkeypatch, tmp_path):
    upload_dir = tmp_path / "uploads_cleanup"
    upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(qc_sample_pools, "_IMPORT_UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(qc_sample_pools, "_IMPORT_UPLOAD_MAX_BYTES", 1024)  # 1KB 便于离线验证上限
    monkeypatch.setattr(
        qc_sample_pools,
        "_service",
        lambda: SimpleNamespace(
            create_pool_with_items=lambda **kwargs: {"id": "pool-up", "name": kwargs["name"], "source_file": kwargs["source_file"]}
        ),
    )

    app = FastAPI()
    app.include_router(qc_sample_pools.router)
    app.dependency_overrides[get_current_user] = lambda: _user_dict("u-admin", "admin")
    client = TestClient(app)

    # 1) 超过上限 -> 413 且无文件留盘
    too_big = client.post(
        "/api/v1/qc/sample-pools/import-upload",
        data={"pool_name": "超大模板"},
        files={"file": ("big.xlsx", BytesIO(b"x" * 2048), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert too_big.status_code == 413
    assert list(upload_dir.iterdir()) == []

    # 2) 解析成功 -> 200 且临时文件已被清理
    monkeypatch.setattr(qc_sample_pools, "load_manual_case_rows_from_excel", lambda **kwargs: [{"row": 1}])
    ok = client.post(
        "/api/v1/qc/sample-pools/import-upload",
        data={"pool_name": "正常模板"},
        files={"file": ("ok.xlsx", BytesIO(b"small-excel"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert ok.status_code == 200
    assert list(upload_dir.iterdir()) == []

    # 3) 解析失败 -> 422 且临时文件同样被清理
    monkeypatch.setattr(qc_sample_pools, "load_manual_case_rows_from_excel", lambda **kwargs: [])
    bad = client.post(
        "/api/v1/qc/sample-pools/import-upload",
        data={"pool_name": "空行模板"},
        files={"file": ("empty_rows.xlsx", BytesIO(b"small-excel"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert bad.status_code == 422
    assert list(upload_dir.iterdir()) == []
