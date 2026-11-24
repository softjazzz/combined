"""Batch 1 P0-1 / P0-2 离线回归单测：
- medical_records_query.py 与 workstation.py 的显式角色门禁（require_roles）
- workstation.py HTTP 500 脱敏（不回显原始异常）
- _filter_home_payload 同时过滤 priority_items 与 priority_records
- _has_other_institute_records 与 _validate_snapshot_scope 异常 fail-closed 及忽略 CUSTOMER_TEST
- get_home / get_luxian_0609_analytics / get_analysis 传递 institute_id / case_scope 与安全回退
- medical_records_common.raise_medical_records_http_error 将 ValueError 映射为 400（含 CDM 模式）
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database import clinical_connection, connection as db_connection
from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    InpatRegistration,
    MedicalRecordFrontpage,
)
from app.routers import medical_records_common, medical_records_query, workstation
from app.services import clinical_case_catalog, clinical_read
from app.services.medical_records.detail_service import InstituteCaseScope
from app.services.medical_records.errors import (
    MedicalRecordsNotFoundError,
    MedicalRecordsValidationError,
)


def _make_user(
    *,
    user_id: str = "u-test",
    roles: list[str],
    institute_id: str | None = "H1",
) -> dict[str, Any]:
    user: dict[str, Any] = {
        "id": user_id,
        "user_id": user_id,
        "roles": roles,
        "is_active": True,
    }
    if institute_id is not None:
        user["institute_id"] = institute_id
    return user


def _make_query_client(user_holder: dict[str, Any]) -> TestClient:
    app = FastAPI()
    app.include_router(medical_records_query.router, prefix="/api/medical-records")
    app.dependency_overrides[get_current_user] = lambda: user_holder["user"]
    return TestClient(app)


def _make_workstation_client(user_holder: dict[str, Any]) -> TestClient:
    app = FastAPI()
    app.include_router(workstation.router)
    app.dependency_overrides[get_current_user] = lambda: user_holder["user"]
    return TestClient(app)


# ============================================================================
# 1. P0-1: 显式角色门禁（medical_records_query.py & workstation.py）
# ============================================================================


@pytest.mark.parametrize("denied_roles", [[], ["guest"], ["read_only_observer"], ["doctor"], ["coder"], ["qc_staff"]])
def test_hospitalization_status_verify_rejects_unprivileged_roles(monkeypatch, denied_roles):
    called: list[bool] = []
    monkeypatch.setattr(
        medical_records_query.default_hospitalization_status_service,
        "verify_current_statuses",
        lambda: called.append(True) or {"checked": 0},
    )
    holder = {"user": _make_user(roles=denied_roles)}
    client = _make_query_client(holder)

    resp = client.post("/api/medical-records/workstation/hospitalization-status/verify")
    assert resp.status_code == 403
    assert called == []


@pytest.mark.parametrize("allowed_role", ["admin", "super_admin", "qc_manager", "sync_admin"])
def test_hospitalization_status_verify_allows_privileged_roles(monkeypatch, allowed_role):
    monkeypatch.setattr(
        medical_records_query.default_hospitalization_status_service,
        "verify_current_statuses",
        lambda: {"checked": 3},
    )
    holder = {"user": _make_user(roles=[allowed_role])}
    client = _make_query_client(holder)

    resp = client.post("/api/medical-records/workstation/hospitalization-status/verify")
    assert resp.status_code == 200
    assert resp.json() == {"checked": 3}


@pytest.mark.parametrize("denied_roles", [[], ["guest"], ["read_only_observer"], ["unknown_role"]])
def test_medical_records_query_read_endpoints_reject_unknown_roles(monkeypatch, denied_roles):
    monkeypatch.setattr(medical_records_query, "list_medical_records", lambda **_kw: {"items": [], "total": 0})
    monkeypatch.setattr(medical_records_query, "get_stats", lambda **_kw: {"total": 0})
    monkeypatch.setattr(medical_records_query, "get_departments", lambda **_kw: [])
    monkeypatch.setattr(medical_records_query, "list_departments_for_institute", lambda _inst: [])
    monkeypatch.setattr(medical_records_query, "get_workstation_data", lambda **_kw: {"records": [], "total": 0})

    holder = {"user": _make_user(roles=denied_roles)}
    client = _make_query_client(holder)

    for method, path, payload in (
        ("GET", "/api/medical-records/list", None),
        ("GET", "/api/medical-records/stats", None),
        ("GET", "/api/medical-records/departments", None),
        ("GET", "/api/medical-records/workstation", None),
        ("POST", "/api/medical-records/workstation/qc-summary", {"record_keys": []}),
    ):
        resp = client.request(method, path, json=payload)
        assert resp.status_code == 403, f"{method} {path} for {denied_roles} got {resp.status_code}"


@pytest.mark.parametrize("allowed_role", ["admin", "super_admin", "qc_manager", "qc_staff", "sync_admin", "doctor", "coder"])
def test_medical_records_query_read_endpoints_allow_legitimate_roles(monkeypatch, allowed_role):
    monkeypatch.setattr(db_connection, "SessionLocal", None)
    monkeypatch.setattr(medical_records_query, "list_medical_records", lambda **_kw: {"items": [], "total": 0})
    monkeypatch.setattr(medical_records_query, "get_workstation_data", lambda **_kw: {"records": [], "total": 0})

    holder = {"user": _make_user(roles=[allowed_role], institute_id="H1")}
    client = _make_query_client(holder)

    assert client.get("/api/medical-records/list").status_code == 200
    assert client.get("/api/medical-records/workstation").status_code == 200


@pytest.mark.parametrize(
    "path,denied_roles",
    [
        ("/api/v1/workstation/home", ["guest"]),
        ("/api/v1/workstation/home", ["coder"]),
        ("/api/v1/workstation/qc-home", []),
        ("/api/v1/workstation/home/hotspots", ["guest"]),
        ("/api/v1/workstation/home/todos", ["guest"]),
        ("/api/v1/workstation/analytics/luxian-0609", ["doctor"]),
        ("/api/v1/workstation/analytics/luxian-0609", ["coder"]),
        ("/api/v1/workstation/analytics/luxian-0609", ["qc_staff"]),
        ("/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=discharged", ["doctor"]),
        ("/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=inpatient", ["coder"]),
        ("/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=discharged", ["guest"]),
        ("/api/v1/workstation/frontpage-qc/worklist", ["guest"]),
        ("/api/v1/workstation/coding-qc/worklist", []),
        ("/api/v1/workstation/settlement-qc/worklist", ["unknown"]),
        ("/api/v1/workstation/frontpage-qc/V1/snapshot", ["guest"]),
        ("/api/v1/workstation/coding-qc/V1/snapshot", ["guest"]),
        ("/api/v1/workstation/settlement-qc/V1/snapshot", ["guest"]),
    ],
)
def test_workstation_endpoints_reject_unauthorized_roles(path, denied_roles):
    holder = {"user": _make_user(roles=denied_roles)}
    client = _make_workstation_client(holder)
    resp = client.get(path)
    assert resp.status_code == 403, f"{path} for {denied_roles} got {resp.status_code}"


def test_workstation_500_hides_raw_exception_and_logs_traceback(monkeypatch, caplog):
    secret_msg = "postgresql://admin:TopSecretPwd@10.0.0.9/medqc"

    def boom(**_kwargs):
        raise RuntimeError(secret_msg)

    monkeypatch.setattr(
        workstation.default_workstation_aggregation_service,
        "get_luxian_0609_home",
        boom,
    )
    holder = {"user": _make_user(roles=["admin"])}
    client = _make_workstation_client(holder)

    with caplog.at_level(logging.ERROR, logger=workstation.logger.name):
        resp = client.get("/api/v1/workstation/qc-home")

    assert resp.status_code == 500
    assert resp.json()["detail"] == "工作台聚合失败，请稍后重试"
    assert secret_msg not in resp.text
    assert any(record.exc_info is not None for record in caplog.records)


# ============================================================================
# 2. P0-2: 跨院隔离、priority_items 过滤、fail-closed 与 CUSTOMER_TEST
# ============================================================================


def test_filter_home_payload_strips_cross_institute_priority_items_and_legacy_records():
    payload = {
        "hotspots": [
            {"visit_id": "V1", "institute_id": "H1"},
            {"visit_id": "V2", "institute_id": "H2"},
        ],
        "my_todo_items": [
            {"visit_id": "V1", "institute_id": "H1"},
            {"visit_id": "V3"},  # 缺 institute_id 也必须过滤
        ],
        "items": [
            {"visit_id": "V1", "institute_id": "H1"},
            {"visit_id": "V2", "institute_id": "H2"},
        ],
        "total": 2,
        "clinical_qc": {
            "kpis": {"records_total": 2},
            "priority_items": [
                {"visit_id": "V1", "institute_id": "H1", "patient_name": "本院甲"},
                {"visit_id": "V2", "institute_id": "H2", "patient_name": "外院乙"},
                {"visit_id": "V3", "patient_name": "缺机构丙"},
            ],
            "priority_records": [
                {"visit_id": "V1", "institute_id": "H1"},
                {"visit_id": "V2", "institute_id": "H2"},
            ],
        },
    }

    filtered = workstation._filter_home_payload(payload, "H1")

    assert [x["visit_id"] for x in filtered["hotspots"]] == ["V1"]
    assert [x["visit_id"] for x in filtered["my_todo_items"]] == ["V1"]
    assert [x["visit_id"] for x in filtered["items"]] == ["V1"]
    assert filtered["total"] == 1
    assert [x["visit_id"] for x in filtered["clinical_qc"]["priority_items"]] == ["V1"]
    assert [x["visit_id"] for x in filtered["clinical_qc"]["priority_records"]] == ["V1"]
    # 原对象未被就地破坏
    assert len(payload["clinical_qc"]["priority_items"]) == 3


def test_workstation_home_passes_scope_and_filters_priority_items(monkeypatch):
    monkeypatch.setattr(db_connection, "SessionLocal", None)
    captured: dict[str, Any] = {}

    def fake_get_home(
        *,
        target_date=None,
        department=None,
        severity=None,
        workflow_type=None,
        keyword=None,
        recipient_id=None,
        hotspot_limit=50,
        todo_limit=12,
        case_scope=None,
        institute_id=None,
    ):
        captured["case_scope"] = case_scope
        captured["institute_id"] = institute_id
        return {
            "clinical_qc": {
                "priority_items": [
                    {"visit_id": "V1", "institute_id": "H1"},
                    {"visit_id": "V2", "institute_id": "H2"},
                ]
            }
        }

    monkeypatch.setattr(
        workstation.default_workstation_aggregation_service,
        "get_home",
        fake_get_home,
    )
    holder = {"user": _make_user(roles=["qc_manager"], institute_id="H1")}
    client = _make_workstation_client(holder)

    resp = client.get("/api/v1/workstation/home")
    assert resp.status_code == 200
    assert isinstance(captured["case_scope"], InstituteCaseScope)
    assert captured["case_scope"].institute_id == "H1"
    assert captured["institute_id"] == "H1"
    assert resp.json()["data"]["clinical_qc"]["priority_items"] == [
        {"visit_id": "V1", "institute_id": "H1"}
    ]


def test_workstation_analytics_and_result_analysis_pass_institute_id_and_fail_closed_on_fallback(monkeypatch):
    monkeypatch.setattr(db_connection, "SessionLocal", None)
    analytics_calls: list[dict[str, Any]] = []
    analysis_calls: list[dict[str, Any]] = []

    def fake_analytics(**kwargs):
        analytics_calls.append(kwargs)
        return {"scope": {"time_basis": "qc_completed_at"}}

    def fake_analysis(**kwargs):
        analysis_calls.append(kwargs)
        return {"scope": {"care_phase": kwargs["care_phase"]}, "record_page": {"items": []}}

    monkeypatch.setattr(
        workstation.default_workstation_aggregation_service,
        "get_luxian_0609_analytics",
        fake_analytics,
    )
    monkeypatch.setattr(
        workstation.default_luxian_0609_result_analysis_service,
        "get_analysis",
        fake_analysis,
    )

    holder = {"user": _make_user(roles=["qc_manager"], institute_id="H1")}
    client = _make_workstation_client(holder)

    r1 = client.get("/api/v1/workstation/analytics/luxian-0609")
    assert r1.status_code == 200
    assert analytics_calls[-1]["institute_id"] == "H1"

    r2 = client.get("/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=discharged")
    assert r2.status_code == 200
    assert analysis_calls[-1]["institute_id"] == "H1"

    # 若底层不支持 institute_id 且存在跨院数据（或检查异常 fail-closed -> True），应返回 403
    def legacy_analytics(**kwargs):
        if "institute_id" in kwargs:
            raise TypeError("unexpected keyword argument 'institute_id'")
        return {"scope": {}}

    monkeypatch.setattr(
        workstation.default_workstation_aggregation_service,
        "get_luxian_0609_analytics",
        legacy_analytics,
    )
    monkeypatch.setattr(workstation, "_has_other_institute_records", lambda _inst: True)
    r3 = client.get("/api/v1/workstation/analytics/luxian-0609")
    assert r3.status_code == 403


def test_has_other_institute_records_ignores_customer_test_and_fails_closed(monkeypatch, caplog):
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: None)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    MedicalRecordFrontpage.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(db_connection, "SessionLocal", sessions)

    try:
        # 1) 单医院 H1 + CUSTOMER_TEST 合成测试病历 -> 不应误判为多院区
        with sessions.begin() as session:
            session.add_all(
                [
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V1",
                        name="本院患者",
                    ),
                    MedicalRecordFrontpage(
                        institute_id="CUSTOMER_TEST",
                        patient_id="PT1",
                        visit_id="VT1",
                        name="合成测试病历",
                    ),
                ]
            )
        assert workstation._has_other_institute_records("H1") is False

        # 2) 加入真实外院 H2 -> 返回 True
        with sessions.begin() as session:
            session.add(
                MedicalRecordFrontpage(
                    institute_id="H2",
                    patient_id="P2",
                    visit_id="V2",
                    name="外院患者",
                )
            )
        assert workstation._has_other_institute_records("H1") is True
    finally:
        engine.dispose()

    # 3) DB 抛出异常时 fail-closed 返回 True 并记录日志
    def broken_session():
        raise OperationalError("SELECT 1", {}, Exception("connection lost"))

    monkeypatch.setattr(db_connection, "SessionLocal", broken_session)
    with caplog.at_level(logging.ERROR, logger=workstation.logger.name):
        assert workstation._has_other_institute_records("H1") is True

    # 4) SessionLocal 缺失同样 fail-closed 返回 True
    monkeypatch.setattr(db_connection, "SessionLocal", None)
    assert workstation._has_other_institute_records("H1") is True


def test_has_other_institute_records_cdm_ignores_customer_test_and_fails_closed(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        with engine.begin() as conn:
            conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
        for model in (InpatRegistration, AdmissionRecord, DischargeRecord):
            model.__table__.to_metadata(
                MedicalRecordFrontpage.metadata.__class__(), schema="cdm"
            ).create(engine)
        with Session(engine.execution_options(schema_translate_map={None: "cdm"})) as session:
            session.add_all(
                [
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V1",
                        name="本院患者",
                        admission_datetime=datetime(2026, 5, 1),
                    ),
                    InpatRegistration(
                        institute_id="CUSTOMER_TEST",
                        patient_id="PT1",
                        visit_id="VT1",
                        name="测试患者",
                        admission_datetime=datetime(2026, 5, 1),
                    ),
                ]
            )
            session.commit()

        monkeypatch.setattr(clinical_connection, "configured", lambda: True)
        monkeypatch.setattr(clinical_connection, "get_engine", lambda: engine)
        clinical_case_catalog.catalog.cache_clear()

        assert workstation._has_other_institute_records("H1") is False

        # 加入真实外院 H2 后应返回 True
        with Session(engine.execution_options(schema_translate_map={None: "cdm"})) as session:
            session.add(
                InpatRegistration(
                    institute_id="H2",
                    patient_id="P2",
                    visit_id="V2",
                    name="外院患者",
                    admission_datetime=datetime(2026, 5, 2),
                )
            )
            session.commit()
        assert workstation._has_other_institute_records("H1") is True

        # CDM 异常时 fail-closed 返回 True
        monkeypatch.setattr(
            clinical_connection,
            "get_engine",
            lambda: (_ for _ in ()).throw(RuntimeError("cdm_unreachable")),
        )
        assert workstation._has_other_institute_records("H1") is True
    finally:
        clinical_case_catalog.catalog.cache_clear()
        engine.dispose()


def test_validate_snapshot_scope_fails_closed_on_db_error_and_missing_session(monkeypatch):
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(workstation, "resolve_non_global_institute_scope", lambda _u: "H1")
    user = _make_user(roles=["qc_manager"], institute_id="H1")

    # 1) SessionLocal 为 None -> fail-closed 503
    monkeypatch.setattr(db_connection, "SessionLocal", None)
    with pytest.raises(HTTPException) as missing_exc:
        workstation._validate_snapshot_scope(
            visit_id="V1",
            institute_id=None,
            patient_id=None,
            current_user=user,
        )
    assert missing_exc.value.status_code == 503

    # 2) Session 查询异常 -> fail-closed 503（绝不静默 pass）
    class _BrokenSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def query(self, *_args, **_kwargs):
            raise OperationalError("SELECT", {}, Exception("db down"))

    monkeypatch.setattr(db_connection, "SessionLocal", lambda: _BrokenSession())
    with pytest.raises(HTTPException) as db_exc:
        workstation._validate_snapshot_scope(
            visit_id="V1",
            institute_id=None,
            patient_id=None,
            current_user=user,
        )
    assert db_exc.value.status_code == 503

    # 3) CDM 模式下底层异常 -> 同样 fail-closed 503
    monkeypatch.setattr(clinical_connection, "configured", lambda: True)
    monkeypatch.setattr(
        clinical_connection,
        "get_engine",
        lambda: (_ for _ in ()).throw(RuntimeError("cdm down")),
    )
    with pytest.raises(HTTPException) as cdm_exc:
        workstation._validate_snapshot_scope(
            visit_id="V1",
            institute_id=None,
            patient_id=None,
            current_user=user,
        )
    assert cdm_exc.value.status_code == 503


# ============================================================================
# 3. medical_records_common.py: ValueError -> 400（即使 CDM configured=True）
# ============================================================================


@pytest.mark.parametrize("cdm_configured", [False, True])
def test_raise_medical_records_http_error_maps_value_error_to_400(monkeypatch, cdm_configured):
    monkeypatch.setattr(clinical_connection, "configured", lambda: cdm_configured)

    with pytest.raises(HTTPException) as exc:
        medical_records_common.raise_medical_records_http_error(ValueError("无效的筛选日期范围"))
    assert exc.value.status_code == 400
    assert exc.value.detail == "无效的筛选日期范围"

    with pytest.raises(HTTPException) as val_exc:
        medical_records_common.raise_medical_records_http_error(
            MedicalRecordsValidationError("参数校验失败")
        )
    assert val_exc.value.status_code == 400

    with pytest.raises(HTTPException) as nf_exc:
        medical_records_common.raise_medical_records_http_error(
            MedicalRecordsNotFoundError("未找到病历")
        )
    assert nf_exc.value.status_code == 404


def test_raise_medical_records_http_error_keeps_503_for_cdm_operational_failures(monkeypatch):
    monkeypatch.setattr(clinical_connection, "configured", lambda: True)

    with pytest.raises(HTTPException) as exc:
        medical_records_common.raise_medical_records_http_error(
            OperationalError("SELECT 1", {}, Exception("timeout"))
        )
    assert exc.value.status_code == 503
    assert exc.value.detail == "clinical_source_read_unavailable"
