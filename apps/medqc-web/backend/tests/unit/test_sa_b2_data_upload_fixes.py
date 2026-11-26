"""Targeted unit tests for Super-Admin Batch 2 Data Management & Smart Upload Fixes."""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.field_mapper as field_mapper_module
from app.core import security
from app.database import connection as db_connection
from app.database.models.cdm import Diagnosis, MedicalRecordFrontpage, PatientInformation
from app.database.models.v36_reports import SysUser
from app.routers import medical_records_export
from app.services import clinical_read, llm_config_loader
from app.services.medical_records import detail_service, export_service
from app.services.smart_upload_async_service import SmartUploadAsyncService


def _user_dict(user_id: str, role: str, institute_id: str | None) -> dict[str, Any]:
    return {
        "id": user_id,
        "username": user_id,
        "email": f"{user_id}@local.test",
        "display_name": user_id,
        "role": role,
        "roles": [role],
        "institute_id": institute_id,
        "is_active": True,
    }


def _setup_users_and_cdm_db(monkeypatch):
    users_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SysUser.__table__.create(bind=users_engine)
    users_factory = sessionmaker(autocommit=False, autoflush=False, bind=users_engine)
    now = datetime.utcnow()
    with users_factory() as session:
        session.add_all(
            [
                SysUser(
                    id="u-global-admin",
                    username="global_admin",
                    email="gadmin@local.test",
                    display_name="Global Admin",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    institute_id=None,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id="u-admin-a",
                    username="admin_a",
                    email="admin_a@local.test",
                    display_name="Admin A",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    institute_id="HOSP-A",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr(db_connection, "SessionLocal", users_factory)
    monkeypatch.setattr(detail_service, "SessionLocal", users_factory, raising=False)

    cdm_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (MedicalRecordFrontpage, Diagnosis, PatientInformation):
        model.__table__.create(bind=cdm_engine)

    with cdm_engine.begin() as conn:
        conn.execute(
            insert(MedicalRecordFrontpage.__table__),
            [
                {"institute_id": "HOSP-A", "patient_id": "P003", "visit_id": "V003", "name": "患者丙"},
                {"institute_id": "HOSP-A", "patient_id": "P001", "visit_id": "V001", "name": "患者甲"},
                {"institute_id": "HOSP-A", "patient_id": "P002", "visit_id": "V002", "name": "患者乙"},
                {"institute_id": "HOSP-B", "patient_id": "P001", "visit_id": "V001", "name": "外院同名"},
            ],
        )
        conn.execute(
            insert(PatientInformation.__table__),
            [
                {"institute_id": "HOSP-A", "patient_id": "P001", "name": "患者甲"},
                {"institute_id": "HOSP-A", "patient_id": "P002", "name": "患者乙"},
                {"institute_id": "HOSP-B", "patient_id": "P001", "name": "外院同名"},
            ],
        )

    monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: None)
    monkeypatch.setattr("app.database.clinical_connection.configured", lambda: False)
    monkeypatch.setattr(export_service, "_session_factory", lambda: Session(cdm_engine))
    monkeypatch.setattr(detail_service, "_session_factory", lambda: Session(cdm_engine))

    return users_engine, cdm_engine


@pytest.mark.unit
def test_table_data_per_patient_filtering_scope_security_and_deterministic_pagination(monkeypatch):
    users_engine, cdm_engine = _setup_users_and_cdm_db(monkeypatch)
    users = {
        "global_admin": _user_dict("u-global-admin", "admin", None),
        "admin_a": _user_dict("u-admin-a", "admin", "HOSP-A"),
    }
    monkeypatch.setattr(security, "resolve_user_by_subject", lambda sub: users.get(sub))

    app = FastAPI()
    app.include_router(medical_records_export.router, prefix="/api/medical-records")
    client = TestClient(app)

    def _hdr(key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {security.create_access_token({'sub': key})}"}

    try:
        # 1. Global admin filters by patient_id + visit_id + institute_id
        r_single = client.get(
            "/api/medical-records/table-data/mr?patient_id=P001&visit_id=V001&institute_id=HOSP-A",
            headers=_hdr("global_admin"),
        )
        assert r_single.status_code == 200, r_single.text
        body = r_single.json()
        assert body["total"] == 1
        assert [(row["institute_id"], row["patient_id"], row["visit_id"]) for row in body["items"]] == [
            ("HOSP-A", "P001", "V001")
        ]

        # 2. Table without visit_id (patient_information) still filters cleanly by patient_id
        r_pat = client.get(
            "/api/medical-records/table-data/patient_information?patient_id=P001&visit_id=V001&institute_id=HOSP-A",
            headers=_hdr("global_admin"),
        )
        assert r_pat.status_code == 200, r_pat.text
        assert r_pat.json()["total"] == 1
        assert r_pat.json()["items"][0]["patient_id"] == "P001"
        assert r_pat.json()["items"][0]["institute_id"] == "HOSP-A"

        # 3. Bound admin keeps institute scope and cannot widen to HOSP-B
        r_bound_ok = client.get(
            "/api/medical-records/table-data/mr?patient_id=P001&visit_id=V001",
            headers=_hdr("admin_a"),
        )
        assert r_bound_ok.status_code == 200, r_bound_ok.text
        assert r_bound_ok.json()["total"] == 1
        assert r_bound_ok.json()["items"][0]["institute_id"] == "HOSP-A"

        r_bound_cross = client.get(
            "/api/medical-records/table-data/mr?patient_id=P001&visit_id=V001&institute_id=HOSP-B",
            headers=_hdr("admin_a"),
        )
        assert r_bound_cross.status_code == 403

        # 4. Deterministic pagination (inserted P003, P001, P002 -> ordered deterministically by PK)
        p1 = client.get(
            "/api/medical-records/table-data/mr?page=1&page_size=2",
            headers=_hdr("admin_a"),
        )
        p2 = client.get(
            "/api/medical-records/table-data/mr?page=2&page_size=2",
            headers=_hdr("admin_a"),
        )
        assert p1.status_code == 200 and p2.status_code == 200
        ids_p1 = [row["patient_id"] for row in p1.json()["items"]]
        ids_p2 = [row["patient_id"] for row in p2.json()["items"]]
        assert ids_p1 == ["P001", "P002"]
        assert ids_p2 == ["P003"]
    finally:
        cdm_engine.dispose()
        users_engine.dispose()


@pytest.mark.unit
def test_get_table_data_order_by_fallback_without_primary_key(monkeypatch):
    monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: None)
    monkeypatch.setattr("app.database.clinical_connection.configured", lambda: False)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    metadata = MetaData()
    tbl = Table(
        "mr",
        metadata,
        Column("institute_id", String(32)),
        Column("patient_id", String(32)),
        Column("visit_id", String(32)),
        Column("label", String(32)),
    )
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            insert(tbl),
            [
                {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2", "label": "second"},
                {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "label": "first"},
                {"institute_id": "H1", "patient_id": "P3", "visit_id": "V3", "label": "third"},
            ],
        )

    try:
        res1 = export_service.get_table_data("mr", page=1, page_size=2, metadata=metadata, session_factory=lambda: Session(engine))
        res2 = export_service.get_table_data("mr", page=2, page_size=2, metadata=metadata, session_factory=lambda: Session(engine))
        assert [row["visit_id"] for row in res1["items"]] == ["V1", "V2"]
        assert [row["visit_id"] for row in res2["items"]] == ["V3"]
    finally:
        engine.dispose()


@pytest.mark.unit
@pytest.mark.parametrize("encoding", ["utf-8-sig", "gb18030", "gbk"])
def test_smart_upload_csv_multi_encoding_decode(tmp_path, monkeypatch, encoding: str):
    service = SmartUploadAsyncService(str(tmp_path))

    async def _fake_mapping(columns, samples):
        return {
            "mappings": {col: col for col in columns},
            "confidence": 0.9,
            "unmapped": [],
            "missing_required": [],
            "fallback": False,
        }

    monkeypatch.setattr("app.services.smart_upload_async_service.suggest_field_mapping", _fake_mapping)

    csv_text = "科室,总费用,DIP支付标准\n心血管内科,12800,13500\n呼吸内科,9600,9000\n"
    csv_bytes = csv_text.encode(encoding)

    result = service.process_upload_sync(
        filename=f"his_export_{encoding}.csv",
        content=csv_bytes,
    )
    assert result["success"] is True
    assert result["row_count"] == 2
    assert set(result["columns"]) == {"科室", "总费用", "DIP支付标准"}
    assert result["sample_data"][0]["科室"] == "心血管内科"


@pytest.mark.asyncio
async def test_field_mapper_prefers_active_system_config_over_env(monkeypatch):
    captured_openai_kwargs: dict[str, Any] = {}
    captured_create_kwargs: dict[str, Any] = {}

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"mappings":{"出院科室":"department_name"},"confidence":0.94}'
                )
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )

    class _FakeCompletions:
        def create(self, **kwargs: Any):
            captured_create_kwargs.update(kwargs)
            return response

    class _FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured_openai_kwargs.update(kwargs)
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    async def _fake_load_config(config_name: str = "default", user_id=None):
        return {
            "source": "database+env",
            "provider_code": "deepseek",
            "api_endpoint": "https://api.deepseek.com/v1/chat/completions",
            "api_key": "sk-system-override",
            "model": "deepseek-system-model",
        }

    monkeypatch.setattr(llm_config_loader.LLMConfigLoader, "load_config", staticmethod(_fake_load_config))
    monkeypatch.setattr(field_mapper_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-env-ignored")
    monkeypatch.setenv("FIELD_MAPPER_MODEL", "env-model-ignored")

    result = await field_mapper_module.suggest_field_mapping(
        ["出院科室"],
        [{"出院科室": "骨科"}],
    )

    assert result["fallback"] is False
    assert captured_openai_kwargs["api_key"] == "sk-system-override"
    assert captured_openai_kwargs["base_url"] == "https://api.deepseek.com/v1"
    assert captured_create_kwargs["model"] == "deepseek-system-model"


@pytest.mark.asyncio
async def test_field_mapper_falls_back_to_env_when_system_config_loader_fails(monkeypatch):
    captured_openai_kwargs: dict[str, Any] = {}
    captured_create_kwargs: dict[str, Any] = {}

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"mappings":{"出院科室":"department_name"},"confidence":0.88}'
                )
            )
        ],
        usage=SimpleNamespace(prompt_tokens=6, completion_tokens=3, total_tokens=9),
    )

    class _FakeCompletions:
        def create(self, **kwargs: Any):
            captured_create_kwargs.update(kwargs)
            return response

    class _FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured_openai_kwargs.update(kwargs)
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    async def _failing_load_config(config_name: str = "default", user_id=None):
        raise RuntimeError("db offline")

    monkeypatch.setattr(llm_config_loader.LLMConfigLoader, "load_config", staticmethod(_failing_load_config))
    monkeypatch.setattr(field_mapper_module, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(field_mapper_module, "_get_dashscope_api_key", lambda: "sk-env-fallback")
    monkeypatch.setattr(field_mapper_module, "_get_dashscope_base_url", lambda: "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setattr(field_mapper_module, "_get_field_mapper_model", lambda: "env-fallback-model")

    result = await field_mapper_module.suggest_field_mapping(
        ["出院科室"],
        [{"出院科室": "内科"}],
    )

    assert result["fallback"] is False
    assert captured_openai_kwargs["api_key"] == "sk-env-fallback"
    assert captured_openai_kwargs["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert captured_create_kwargs["model"] == "env-fallback-model"
