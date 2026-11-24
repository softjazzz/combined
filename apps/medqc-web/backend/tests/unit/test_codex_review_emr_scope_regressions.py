"""Codex 复核 3 项 P1 定向回归测试：
1. P1-1：东华历史已核验冻结材料的目录与正文放行正反例（不误拒 403，缺证明/三键不符仍拒 403）。
2. P1-2：显式区分 global / institute / missing 三类账号范围，未绑定机构的非全局账号在发起临床查询前即 403 拒绝。
3. P1-3：单库路径下 EMR 缺陷标注严格绑定病例三键与历史任务/结果信封，无法证明归属时保留正文、省略标注。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.core.supabase_client import _PgClient
from app.database import clinical_connection as clinical
from app.database import connection as db_connection
from app.database.models.v36_reports import SysUser
from app.routers import emr_render, medical_records_query
from app.services import case_material_snapshot as case_material
from app.services.medical_records.detail_service import (
    ResolvedInstituteScope,
    inspect_institute_scope,
    resolve_non_global_institute_scope,
)


def _make_auth_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SysUser.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add_all(
            [
                SysUser(
                    id="u-admin",
                    username="admin_u",
                    display_name="管理员",
                    email="admin@local.test",
                    password_hash="x",
                    role="admin",
                    institute_id=None,
                    is_active=True,
                ),
                SysUser(
                    id="u-luxian-mgr",
                    username="luxian_mgr",
                    display_name="泸县经理",
                    email="luxian@local.test",
                    password_hash="x",
                    role="qc_manager",
                    institute_id="泸县人民医院",
                    is_active=True,
                ),
                SysUser(
                    id="u-hosp-a-mgr",
                    username="hosp_a_mgr",
                    display_name="A院经理",
                    email="hosp_a@local.test",
                    password_hash="x",
                    role="qc_manager",
                    institute_id="HOSP-A",
                    is_active=True,
                ),
                SysUser(
                    id="u-other-mgr",
                    username="other_mgr",
                    display_name="他院经理",
                    email="other@local.test",
                    password_hash="x",
                    role="qc_manager",
                    institute_id="其他医院",
                    is_active=True,
                ),
                SysUser(
                    id="u-unbound-mgr",
                    username="unbound_mgr",
                    display_name="未绑机构经理",
                    email="unbound@local.test",
                    password_hash="x",
                    role="qc_manager",
                    institute_id=None,
                    is_active=True,
                ),
                SysUser(
                    id="u-blank-staff",
                    username="blank_staff",
                    display_name="空机构质控员",
                    email="blank@local.test",
                    password_hash="x",
                    role="qc_staff",
                    institute_id="   ",
                    is_active=True,
                ),
            ]
        )
        session.commit()
    return engine, factory


# ---------------------------------------------------------------------------
# P1-1: 东华历史冻结材料目录与正文正反例
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p1_1_donghua_verified_history_allows_directory_and_render_and_blocks_invalid(
    monkeypatch,
):
    _engine, auth_factory = _make_auth_session_factory()
    monkeypatch.setattr(db_connection, "SessionLocal", auth_factory)
    monkeypatch.setattr(clinical, "configured", lambda: False)
    monkeypatch.setattr(
        emr_render,
        "_load_live_cdm_documents",
        lambda *args, **kwargs: pytest.fail("已核验历史查看不得回查当前 CDM"),
    )

    coord = {"institute_id": "机构号", "patient_id": "P-DH-1", "visit_id": "V-DH-1"}
    binding = "cdm-read-v1:" + hashlib.sha256(b"donghua-synthetic").hexdigest()
    source = {"id": "independent_cdm", "url": "postgresql://ro@synthetic/cdm", "binding": binding}
    doc = {
        "document_id": "DOC-DH-1",
        "doc_type": "admission_record",
        "doc_name": "入院记录",
        "content": "东华历史冻结入院正文",
    }
    verified_material = {
        "protocol": case_material.PROTOCOL,
        "schema": "cdm",
        "job_id": "JOB-DH-ROOT",
        "identity": [coord["institute_id"], coord["patient_id"], coord["visit_id"]],
        "binding": binding,
        "documents": {"documents": [doc]},
        "tables": {},
    }

    state_holder: dict = {
        "verified": verified_material,
        "root_job": "JOB-DH-ROOT",
        "source": source,
        "user": {"id": "u-luxian-mgr", "roles": ["qc_manager"]},
    }

    async def inject_upstream_state(req: Request):
        if state_holder["source"] is not None:
            req.state.clinical_source = state_holder["source"]
        if state_holder["verified"] is not None:
            req.state.verified_history_material = state_holder["verified"]
        if state_holder["root_job"]:
            req.state.material_root_job_id = state_holder["root_job"]

    app = FastAPI(dependencies=[Depends(inject_upstream_state)])
    app.include_router(emr_render.router)
    app.dependency_overrides[get_current_user] = lambda: state_holder["user"]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://local.test"
    ) as client:
        # 1) 正例：证明有效、三键匹配、本院东华经理 -> 目录与正文均可读 200
        dir_summary = await client.get(
            "/api/v1/emr/V-DH-1/documents",
            params={**coord, "view": "summary", "job_id": "JOB-DH-ROOT"},
        )
        assert dir_summary.status_code == 200, dir_summary.text
        assert dir_summary.json()["data"]["documents"][0]["document_id"] == "DOC-DH-1"

        dir_full = await client.get(
            "/api/v1/emr/V-DH-1/documents",
            params={**coord, "view": "full", "job_id": "JOB-DH-ROOT"},
        )
        assert dir_full.status_code == 200, dir_full.text
        assert dir_full.json()["data"]["documents"][0]["content"] == "东华历史冻结入院正文"

        body = await client.get(
            "/api/v1/emr/V-DH-1/render",
            params={
                **coord,
                "doc_type": "admission_record",
                "doc_id": "DOC-DH-1",
                "job_id": "JOB-DH-ROOT",
            },
        )
        assert body.status_code == 200, body.text
        assert body.json()["data"]["content"] == "东华历史冻结入院正文"

        # 2) 反例：缺少上游已核验冻结证明 -> 403
        state_holder["verified"] = None
        for url in ("/api/v1/emr/V-DH-1/documents", "/api/v1/emr/V-DH-1/render"):
            resp = await client.get(url, params={**coord, "job_id": "JOB-DH-ROOT"})
            assert resp.status_code == 403

        # 3) 反例：病例三键不符 -> 403
        state_holder["verified"] = verified_material
        wrong_pat_dir = await client.get(
            "/api/v1/emr/V-DH-1/documents",
            params={**coord, "patient_id": "P-WRONG", "job_id": "JOB-DH-ROOT"},
        )
        assert wrong_pat_dir.status_code == 403
        wrong_pat_render = await client.get(
            "/api/v1/emr/V-DH-1/render",
            params={**coord, "patient_id": "P-WRONG", "doc_id": "DOC-DH-1", "job_id": "JOB-DH-ROOT"},
        )
        assert wrong_pat_render.status_code == 403

        # 4) 反例：current 实时视图不可借历史证明跨机构 -> 403
        current_resp = await client.get(
            "/api/v1/emr/V-DH-1/documents",
            params={**coord, "source_view": "current", "view": "full"},
        )
        assert current_resp.status_code == 403

        # 5) 反例：其他医院质控经理不可借东华证明读取 -> 403
        state_holder["user"] = {"id": "u-other-mgr", "roles": ["qc_manager"]}
        other_resp = await client.get(
            "/api/v1/emr/V-DH-1/render",
            params={**coord, "doc_id": "DOC-DH-1", "job_id": "JOB-DH-ROOT"},
        )
        assert other_resp.status_code == 403


# ---------------------------------------------------------------------------
# P1-2: 三类账号范围（global / institute / missing）与双机构数据隔离
# ---------------------------------------------------------------------------


def test_p1_2_three_scope_kinds_and_fail_closed_before_clinical_query(monkeypatch):
    _engine, auth_factory = _make_auth_session_factory()
    monkeypatch.setattr(db_connection, "SessionLocal", auth_factory)

    # 直接单元测试三态区分
    assert inspect_institute_scope({"id": "u-admin", "roles": ["admin"]}) == ResolvedInstituteScope(
        kind="global", institute_id=None
    )
    assert inspect_institute_scope(
        {"id": "u-hosp-a-mgr", "roles": ["qc_manager"]}
    ) == ResolvedInstituteScope(kind="institute", institute_id="HOSP-A")
    assert inspect_institute_scope(
        {"id": "u-unbound-mgr", "roles": ["qc_manager"]}
    ) == ResolvedInstituteScope(kind="missing", institute_id=None)
    assert inspect_institute_scope(
        {"id": "u-blank-staff", "roles": ["qc_staff"]}
    ) == ResolvedInstituteScope(kind="missing", institute_id=None)
    # 即使请求态伪造 institute_id，持久账号机构缺失也必须返回 missing / 403
    assert inspect_institute_scope(
        {"id": "u-unbound-mgr", "roles": ["qc_manager"], "institute_id": "HOSP-A"}
    ) == ResolvedInstituteScope(kind="missing", institute_id=None)

    assert resolve_non_global_institute_scope({"id": "u-admin", "roles": ["admin"]}) is None
    assert (
        resolve_non_global_institute_scope({"id": "u-hosp-a-mgr", "roles": ["qc_manager"]})
        == "HOSP-A"
    )
    with pytest.raises(HTTPException) as exc_info:
        resolve_non_global_institute_scope({"id": "u-unbound-mgr", "roles": ["qc_manager"]})
    assert exc_info.value.status_code == 403

    # 双机构合成数据验证病历池 /list 与 /stats 路由：missing 账号必须在发起临床查询前被 403 拒绝
    dual_records = [
        {"institute_id": "HOSP-A", "patient_id": "PA1", "visit_id": "VA1"},
        {"institute_id": "HOSP-B", "patient_id": "PB1", "visit_id": "VB1"},
    ]
    query_calls: list[object] = []

    def fake_list_records(*, case_scope=None, **_kwargs):
        query_calls.append(case_scope)
        if case_scope is None:
            return {"records": list(dual_records), "total": len(dual_records)}
        filtered = [r for r in dual_records if r["institute_id"] == case_scope.institute_id]
        return {"records": filtered, "total": len(filtered)}

    def fake_get_stats(*, case_scope=None, **_kwargs):
        query_calls.append(case_scope)
        if case_scope is None:
            return {"total": len(dual_records)}
        return {"total": sum(1 for r in dual_records if r["institute_id"] == case_scope.institute_id)}

    monkeypatch.setattr(medical_records_query, "list_medical_records", fake_list_records)
    monkeypatch.setattr(medical_records_query, "get_stats", fake_get_stats)
    monkeypatch.setattr(
        medical_records_query,
        "list_departments_for_institute",
        lambda inst: [f"{inst}-内科"],
    )
    monkeypatch.setattr(
        medical_records_query,
        "get_departments",
        lambda case_scope=None: ["HOSP-A-内科", "HOSP-B-外科"],
    )

    active_user = {"value": {"id": "u-admin", "roles": ["admin"]}}
    app = FastAPI()
    app.include_router(medical_records_query.router, prefix="/api/medical-records")
    app.dependency_overrides[get_current_user] = lambda: active_user["value"]
    client = TestClient(app)

    # 1) 全局管理员：可见双机构
    r_admin = client.get("/api/medical-records/list")
    assert r_admin.status_code == 200
    assert r_admin.json()["total"] == 2
    assert client.get("/api/medical-records/stats").json()["total"] == 2
    assert len(client.get("/api/medical-records/departments").json()) == 2

    # 2) 本机构经理（HOSP-A）：仅见 HOSP-A
    active_user["value"] = {"id": "u-hosp-a-mgr", "roles": ["qc_manager"]}
    r_inst = client.get("/api/medical-records/list")
    assert r_inst.status_code == 200
    assert r_inst.json()["records"] == [dual_records[0]]
    assert client.get("/api/medical-records/stats").json()["total"] == 1
    assert client.get("/api/medical-records/departments").json() == ["HOSP-A-内科"]

    # 3) 机构缺失非全局账号：在任何临床查询发生前直接 403
    query_calls.clear()
    active_user["value"] = {"id": "u-unbound-mgr", "roles": ["qc_manager"]}
    for path in (
        "/api/medical-records/list",
        "/api/medical-records/stats",
        "/api/medical-records/departments",
    ):
        resp = client.get(path)
        assert resp.status_code == 403
    assert query_calls == []


# ---------------------------------------------------------------------------
# P1-3: 单库路径下缺陷标注三键与历史任务/结果信封绑定
# ---------------------------------------------------------------------------

_QC_RESULTS_DDL = """
CREATE TABLE qc_results (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    record_id VARCHAR(100) NOT NULL,
    rule_set VARCHAR(100),
    overall_score FLOAT,
    grade VARCHAR(10),
    defect_count INTEGER NOT NULL,
    analysis_engine VARCHAR(30),
    analysis_date TIMESTAMP,
    raw_output TEXT,
    created_by VARCHAR(36),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
)
"""

_ENVELOPES_DDL = """
CREATE TABLE luxian_0609_record_result_envelopes (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL,
    root_job_id VARCHAR(36) NOT NULL,
    created_by VARCHAR(64) NOT NULL,
    record_id VARCHAR(128) NOT NULL,
    institute_id VARCHAR(128) NOT NULL,
    patient_id VARCHAR(128) NOT NULL,
    visit_id VARCHAR(128) NOT NULL,
    rule_set_key VARCHAR(96) NOT NULL,
    rule_set_version VARCHAR(96) NOT NULL,
    envelope_json TEXT NOT NULL,
    result_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
)
"""


def _make_single_db_for_annotations():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SysUser.__table__.create(bind=engine)
    with engine.begin() as conn:
        conn.execute(text(_QC_RESULTS_DDL))
        conn.execute(text(_ENVELOPES_DDL))
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add_all(
            [
                SysUser(
                    id="u-admin",
                    username="admin_a",
                    display_name="管理员A",
                    email="admin_a@local.test",
                    password_hash="x",
                    role="admin",
                    institute_id=None,
                    is_active=True,
                ),
                SysUser(
                    id="u-hosp-a-mgr",
                    username="mgr_a",
                    display_name="A院质控经理",
                    email="mgr_a@local.test",
                    password_hash="x",
                    role="qc_manager",
                    institute_id="HOSP-A",
                    is_active=True,
                ),
            ]
        )
        session.commit()
    return engine, factory


def _insert_qc_result(engine, *, result_id: str, record_id: str, raw_output: dict, created_at: datetime):
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO qc_results (id, record_id, defect_count, raw_output, created_at, updated_at) "
                "VALUES (:id, :record_id, :defect_count, :raw_output, :created_at, :updated_at)"
            ),
            {
                "id": result_id,
                "record_id": record_id,
                "defect_count": len(raw_output.get("issues") or []),
                "raw_output": json.dumps(raw_output, ensure_ascii=False),
                "created_at": created_at,
                "updated_at": created_at,
            },
        )


def test_p1_3_single_db_annotations_bind_tri_key_and_history_job_and_omit_unproven(monkeypatch):
    engine, factory = _make_single_db_for_annotations()
    monkeypatch.setattr(clinical, "configured", lambda: False)
    monkeypatch.setattr(db_connection, "SessionLocal", factory)
    monkeypatch.setattr(emr_render, "get_supabase", lambda: _PgClient(factory))

    content = "主诉：发热3天。现病史：患者出现反复咳嗽。"

    def fake_load_bundle(*, institute_id, patient_id, visit_id, **_kwargs):
        return {
            "documents": [
                {
                    "id": "DOC-1",
                    "doc_type": "admission_record",
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "content": content,
                }
            ],
            "documents_tree": [],
            "empty_reason": "",
        }

    monkeypatch.setattr(emr_render, "_load_documents_from_bundle", fake_load_bundle)
    monkeypatch.setattr(emr_render, "pick_document", lambda documents, **_kwargs: documents[0])
    monkeypatch.setattr(
        emr_render,
        "build_render_view",
        lambda selected: {"content": selected["content"], "content_type": "text"},
    )

    # 同号病例 V-DUP：
    # 1) HOSP-A / P-A 旧结果（JOB-1）
    _insert_qc_result(
        engine,
        result_id="R-A-1",
        record_id="V-DUP",
        raw_output={
            "institute_id": "HOSP-A",
            "patient_id": "P-A",
            "visit_id": "V-DUP",
            "job_id": "JOB-1",
            "issues": [{"id": "DEF-A-JOB1", "description": "A院旧任务缺陷", "evidence": "发热3天"}],
        },
        created_at=datetime(2026, 10, 1, 10, 0, 0),
    )
    # 2) HOSP-A / P-A 较新结果（JOB-2）
    _insert_qc_result(
        engine,
        result_id="R-A-2",
        record_id="V-DUP",
        raw_output={
            "institute_id": "HOSP-A",
            "patient_id": "P-A",
            "visit_id": "V-DUP",
            "job_id": "JOB-2",
            "issues": [{"id": "DEF-A-JOB2", "description": "A院新任务缺陷", "evidence": "反复咳嗽"}],
        },
        created_at=datetime(2026, 10, 2, 10, 0, 0),
    )
    # 3) HOSP-B / P-B 最新结果（同号 V-DUP，时间最新！）
    _insert_qc_result(
        engine,
        result_id="R-B-LATEST",
        record_id="V-DUP",
        raw_output={
            "institute_id": "HOSP-B",
            "patient_id": "P-B",
            "visit_id": "V-DUP",
            "job_id": "JOB-B",
            "issues": [{"id": "DEF-B-CROSS", "description": "B院他患缺陷", "evidence": "发热3天"}],
        },
        created_at=datetime(2026, 10, 3, 10, 0, 0),
    )
    # 4) 另一病例 V-LEGACY：旧库行无 institute_id / patient_id，无法证明归属
    _insert_qc_result(
        engine,
        result_id="R-LEGACY-UNPROVEN",
        record_id="V-LEGACY",
        raw_output={"issues": [{"id": "DEF-UNPROVEN", "description": "无归属旧缺陷", "evidence": "主诉"}]},
        created_at=datetime(2026, 10, 4, 10, 0, 0),
    )
    # 5) 历史任务 JOB-ENV 的 Canonical Envelope
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO luxian_0609_record_result_envelopes "
                "(id, job_id, root_job_id, created_by, record_id, institute_id, patient_id, visit_id, "
                "rule_set_key, rule_set_version, envelope_json, result_count, created_at, updated_at) "
                "VALUES (:id, :job_id, :root_job_id, 'u-hosp-a-mgr', 'V-DUP', 'HOSP-A', 'P-A', 'V-DUP', "
                "'luxian_0609', 'v1', :envelope_json, 1, :ts, :ts)"
            ),
            {
                "id": "ENV-1",
                "job_id": "JOB-ENV",
                "root_job_id": "JOB-ENV",
                "envelope_json": json.dumps(
                    {
                        "visit_id": "V-DUP",
                        "items": [
                            {
                                "rule_id": "LX-ENV-1",
                                "status": "non_compliant",
                                "is_compliant": False,
                                "findings": "历史信封缺陷",
                                "evidence": "发热3天",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                "ts": datetime(2026, 10, 1, 9, 0, 0),
            },
        )

    app = FastAPI()
    app.include_router(emr_render.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-hosp-a-mgr",
        "roles": ["qc_manager"],
    }
    client = TestClient(app)

    # A) 正常读取 HOSP-A / P-A / V-DUP：命中 A 院最新（JOB-2），绝不串入时间更新的 B 院结果！
    r_a = client.get(
        "/api/v1/emr/V-DUP/render",
        params={"institute_id": "HOSP-A", "patient_id": "P-A", "visit_id": "V-DUP"},
    )
    assert r_a.status_code == 200
    data_a = r_a.json()["data"]
    assert data_a["content"] == content
    assert data_a["annotation_status"] == "loaded"
    assert [a["defect_id"] for a in data_a["defect_annotations"]] == ["DEF-A-JOB2"]

    # B) 打开旧任务 JOB-1：仅返回 JOB-1 标注，绝不看到后来任务 JOB-2 的标注！
    r_job1 = client.get(
        "/api/v1/emr/V-DUP/render",
        params={"institute_id": "HOSP-A", "patient_id": "P-A", "visit_id": "V-DUP", "job_id": "JOB-1"},
    )
    assert r_job1.status_code == 200
    data_job1 = r_job1.json()["data"]
    assert data_job1["content"] == content
    assert data_job1["annotation_status"] == "loaded"
    assert [a["defect_id"] for a in data_job1["defect_annotations"]] == ["DEF-A-JOB1"]

    # C) 打开历史信封任务 JOB-ENV：精确返回该历史任务的 Canonical Envelope 标注！
    r_env = client.get(
        "/api/v1/emr/V-DUP/render",
        params={"institute_id": "HOSP-A", "patient_id": "P-A", "visit_id": "V-DUP", "job_id": "JOB-ENV"},
    )
    assert r_env.status_code == 200
    data_env = r_env.json()["data"]
    assert data_env["content"] == content
    assert data_env["annotation_status"] == "loaded"
    assert [a["defect_id"] for a in data_env["defect_annotations"]] == ["LX-ENV-1"]

    # D) 打开无对应结果的旧任务 JOB-MISSING：保留正文、不回退给最新任务标注！
    r_missing_job = client.get(
        "/api/v1/emr/V-DUP/render",
        params={
            "institute_id": "HOSP-A",
            "patient_id": "P-A",
            "visit_id": "V-DUP",
            "job_id": "JOB-MISSING",
        },
    )
    assert r_missing_job.status_code == 200
    data_missing = r_missing_job.json()["data"]
    assert data_missing["content"] == content
    assert data_missing["annotation_status"] == "no_result"
    assert data_missing["defect_annotations"] == []

    # E) 同院不同患者 P-OTHER：不会串用 P-A 的标注，保留正文、省略标注！
    r_other_pat = client.get(
        "/api/v1/emr/V-DUP/render",
        params={"institute_id": "HOSP-A", "patient_id": "P-OTHER", "visit_id": "V-DUP"},
    )
    assert r_other_pat.status_code == 200
    assert r_other_pat.json()["data"]["content"] == content
    assert r_other_pat.json()["data"]["annotation_status"] == "no_result"
    assert r_other_pat.json()["data"]["defect_annotations"] == []

    # F) 无法证明归属的旧数据（缺 institute_id/patient_id）：保留正文、省略该组标注！
    r_legacy = client.get(
        "/api/v1/emr/V-LEGACY/render",
        params={"institute_id": "HOSP-A", "patient_id": "P-LEGACY", "visit_id": "V-LEGACY"},
    )
    assert r_legacy.status_code == 200
    assert r_legacy.json()["data"]["content"] == content
    assert r_legacy.json()["data"]["annotation_status"] == "no_result"
    assert r_legacy.json()["data"]["defect_annotations"] == []
