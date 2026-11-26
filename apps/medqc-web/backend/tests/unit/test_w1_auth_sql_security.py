"""Wave 1 安全与数据隔离回归单测（纯离线 / 内存 SQLite / tmp_path）。

覆盖缺陷：
- P0-2 (`supabase_client.py`): `.or_()` 列名标识符与运算符白名单防 SQL 注入
- P2-C3 (`supabase_client.py`): `async_execute()` 异常禁止回退二次同步执行
- P0-1 (`medical_records_export.py` + `export_service.py`): `/table-data/{table_name}` 角色门禁、业务表白名单、非全局机构过滤
- P1-E5 (`export_service.py`): `get_frontpage_sheet` 跨院冲突 409 与 `fp.institute_id` 锁定后续子查询
- P0-3 (`access_control.py` + `main.py` + `demo.py`): 禁止 `/api/v1/demo/` 免认证/默认挂载、`mode` 白名单防路径穿越、`result_id` UUID 防 glob 泄露、去除绝对路径回显、写/LLM 端点补鉴权
- P1-B3 (`security.py` + `auth.py`): Access Token 写入 `type=access`，拒绝 `refresh`/`password_reset` 令牌冒用为 Access Token
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core import access_control, security
from app.core.settings import clear_settings_snapshot, get_settings
from app.core.supabase_client import _Query, async_execute
from app.database.models.cdm import Diagnosis, MedicalRecordFrontpage, MrCost, MrSurgery
from app.database.models.qc import SysUser
from app.main import create_app
from app.routers import auth, demo, medical_records_export
from app.services.medical_records import export_service


# ============================================================================
# 1. P0-2 + P2-C3: supabase_client.py
# ============================================================================


def test_or_filter_allows_valid_ilike_and_qc_document_category_clauses() -> None:
    query = _Query(lambda: None, "qc_rules").select("*").or_(
        "name.ilike.%发热%,description.ilike.%发热%,rule_code.ilike.%发热%"
    )
    where, params = query._build_where()
    assert where == '("name" ILIKE :p0 OR "description" ILIKE :p1 OR "rule_code" ILIKE :p2)'
    assert params == {"p0": "%发热%", "p1": "%发热%", "p2": "%发热%"}

    doc_query = _Query(lambda: None, "qc_rules").select("*").or_(
        "applicable_documents.cs.{入院记录},"
        "applicable_documents.is.null,"
        "applicable_documents.eq.{},"
        "primary_document_category.eq.入院记录"
    )
    doc_where, doc_params = doc_query._build_where()
    assert '"applicable_documents" IS NULL' in doc_where
    assert '"primary_document_category" = :p2' in doc_where
    assert doc_params == {"p0": "{入院记录}", "p1": "{}", "p2": "入院记录"}


def test_or_filter_folds_comma_keywords_safely_into_bound_params() -> None:
    keyword = '高血压,糖尿病" OR 1=1 --'
    query = _Query(lambda: None, "qc_rules").select("*").or_(
        f"name.ilike.%{keyword}%,description.ilike.%{keyword}%"
    )
    where, params = query._build_where()
    assert where == '("name" ILIKE :p0 OR "description" ILIKE :p1)'
    assert params == {"p0": f"%{keyword}%", "p1": f"%{keyword}%"}


@pytest.mark.parametrize(
    "bad_or",
    [
        'name.ilike.%foo,x"=1 OR 1=1--.eq.1%,description.ilike.%foo%',
        'bad"col.ilike.%x%',
        "123bad.eq.1",
        "name.exec.1",
        "name.is.1 OR 1=1",
        "orphan_without_dots",
        "name.eq.1,trailing_garbage",
    ],
)
def test_or_filter_rejects_invalid_column_operator_or_sqli_payload(bad_or: str) -> None:
    query = _Query(lambda: None, "qc_rules").select("*").or_(bad_or)
    with pytest.raises(ValueError):
        query._build_where()


def test_filters_and_orders_reject_invalid_column_identifiers() -> None:
    with pytest.raises(ValueError):
        _Query(lambda: None, "qc_rules").eq('bad"col', "1")._build_where()
    with pytest.raises(ValueError):
        _Query(lambda: None, "qc_rules").select("*").order('bad"col')._build_select_sql()


@pytest.mark.asyncio
async def test_async_execute_propagates_error_without_sync_fallback() -> None:
    sync_calls = 0

    class FailingAsyncWriteQuery:
        async def execute_async(self):
            raise RuntimeError("db_write_timeout")

        def execute(self):
            nonlocal sync_calls
            sync_calls += 1
            return "should_not_run"

    with pytest.raises(RuntimeError, match="db_write_timeout"):
        await async_execute(FailingAsyncWriteQuery())
    assert sync_calls == 0


@pytest.mark.asyncio
async def test_async_execute_preserves_magicmock_and_asyncmock_behavior() -> None:
    plain_mock = MagicMock()
    plain_mock.execute.return_value = "sync_ok"
    assert await async_execute(plain_mock) == "sync_ok"
    assert plain_mock.execute.call_count == 1

    async_mock_query = MagicMock()
    async_mock_query.execute_async = AsyncMock(side_effect=RuntimeError("async_boom"))
    with pytest.raises(RuntimeError, match="async_boom"):
        await async_execute(async_mock_query)
    assert async_mock_query.execute.call_count == 0


# ============================================================================
# 2. P0-1 + P1-E5: medical_records_export.py + export_service.py
# ============================================================================


@pytest.fixture
def export_sqlite_engine(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (MedicalRecordFrontpage, Diagnosis, MrSurgery, MrCost, SysUser):
        model.__table__.create(engine)

    with engine.begin() as conn:
        conn.execute(
            insert(MedicalRecordFrontpage.__table__),
            [
                {
                    "institute_id": "H-A",
                    "patient_id": "P-1",
                    "visit_id": "V-SINGLE",
                    "name": "单院患者",
                    "discharge_dept_name": "心内科",
                    "admission_datetime": datetime(2026, 1, 1),
                },
                {
                    "institute_id": "H-A",
                    "patient_id": "P-2",
                    "visit_id": "V-SHARED",
                    "name": "A院患者",
                    "discharge_dept_name": "内科",
                    "admission_datetime": datetime(2026, 1, 2),
                },
                {
                    "institute_id": "H-B",
                    "patient_id": "P-2",
                    "visit_id": "V-SHARED",
                    "name": "B院患者",
                    "discharge_dept_name": "外科",
                    "admission_datetime": datetime(2026, 1, 2),
                },
                {
                    "institute_id": "H-A",
                    "patient_id": "P-3",
                    "visit_id": "V-COLLIDE",
                    "name": "A院同就诊号",
                    "discharge_dept_name": "呼吸科",
                    "admission_datetime": datetime(2026, 1, 3),
                },
                {
                    "institute_id": "H-B",
                    "patient_id": "P-4",
                    "visit_id": "V-COLLIDE",
                    "name": "B院同就诊号",
                    "discharge_dept_name": "骨科",
                    "admission_datetime": datetime(2026, 1, 3),
                },
            ],
        )
        conn.execute(
            insert(Diagnosis.__table__),
            [
                {
                    "institute_id": "H-A",
                    "patient_id": "P-1",
                    "visit_id": "V-SINGLE",
                    "diagnosis_id": "D-A",
                    "diagnosis_no": "1",
                    "diagnosis_type": "出院主要诊断（病理）",
                    "diagnosis_name": "A院诊断",
                    "diagnosis_code": "I10",
                },
                {
                    "institute_id": "H-B",
                    "patient_id": "P-1",
                    "visit_id": "V-SINGLE",
                    "diagnosis_id": "D-B",
                    "diagnosis_no": "1",
                    "diagnosis_type": "出院主要诊断（病理）",
                    "diagnosis_name": "B院串扰诊断",
                    "diagnosis_code": "E11",
                },
                {
                    "institute_id": "H-A",
                    "patient_id": "P-2",
                    "visit_id": "V-SHARED",
                    "diagnosis_id": "D-SHARED-A",
                    "diagnosis_no": "1",
                    "diagnosis_type": "出院主要诊断（病理）",
                    "diagnosis_name": "A院共享诊断",
                    "diagnosis_code": "I20",
                },
                {
                    "institute_id": "H-B",
                    "patient_id": "P-2",
                    "visit_id": "V-SHARED",
                    "diagnosis_id": "D-SHARED-B",
                    "diagnosis_no": "1",
                    "diagnosis_type": "出院主要诊断（病理）",
                    "diagnosis_name": "B院共享诊断",
                    "diagnosis_code": "I25",
                },
            ],
        )
        conn.execute(
            insert(MrSurgery.__table__),
            [
                {
                    "institute_id": "H-A",
                    "patient_id": "P-1",
                    "visit_id": "V-SINGLE",
                    "surgery_id": "S-A",
                    "surgery_name": "A院手术",
                },
                {
                    "institute_id": "H-B",
                    "patient_id": "P-1",
                    "visit_id": "V-SINGLE",
                    "surgery_id": "S-B",
                    "surgery_name": "B院串扰手术",
                },
            ],
        )
        conn.execute(
            insert(MrCost.__table__),
            [
                {
                    "institute_id": "H-A",
                    "patient_id": "P-1",
                    "visit_id": "V-SINGLE",
                    "total_cost": "1000.00",
                },
                {
                    "institute_id": "H-B",
                    "patient_id": "P-1",
                    "visit_id": "V-SINGLE",
                    "total_cost": "9999.00",
                },
            ],
        )
        conn.execute(
            insert(SysUser.__table__),
            [
                {
                    "id": "u-secret",
                    "username": "secret_user",
                    "display_name": "Secret Admin",
                    "email": "secret@medqc.com",
                    "password_hash": "$2b$12$fakehash",
                    "role": "admin",
                    "is_active": True,
                }
            ],
        )

    from app.services import clinical_read

    monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: None)
    monkeypatch.setattr(export_service, "_session_factory", lambda: Session(engine))
    yield engine
    engine.dispose()


def _build_export_client(monkeypatch):
    users = {
        "doctor": {"id": "u-doc", "roles": ["doctor"], "institute_id": "H-A", "is_active": True},
        "qc_manager": {"id": "u-qcm", "roles": ["qc_manager"], "institute_id": "H-A", "is_active": True},
        "qc_staff": {"id": "u-qcs", "roles": ["qc_staff"], "institute_id": "H-A", "is_active": True},
        "admin_ha": {"id": "u-adm-ha", "roles": ["admin"], "institute_id": "H-A", "is_active": True},
        "admin_global": {"id": "u-adm", "roles": ["admin"], "institute_id": "", "is_active": True},
        "sync_admin": {"id": "u-sync", "roles": ["sync_admin"], "institute_id": "H-A", "is_active": True},
        "super_admin": {"id": "u-sup", "roles": ["super_admin"], "institute_id": "H-A", "is_active": True},
    }
    monkeypatch.setattr(security, "resolve_user_by_subject", lambda sub: users.get(sub))

    app = FastAPI()
    app.include_router(medical_records_export.router, prefix="/api/medical-records")

    def headers(user_key: str) -> dict[str, str]:
        token = security.create_access_token({"sub": user_key})
        return {"Authorization": f"Bearer {token}"}

    return TestClient(app), headers


def test_table_data_rbac_whitelist_and_institute_scope(export_sqlite_engine, monkeypatch) -> None:
    client, headers = _build_export_client(monkeypatch)

    # 1. 未认证 / 非管理员角色拒绝
    assert client.get("/api/medical-records/table-data/mr").status_code in (401, 403)
    for role_key in ("doctor", "qc_manager", "qc_staff"):
        resp = client.get("/api/medical-records/table-data/mr", headers=headers(role_key))
        assert resp.status_code == 403

    # 2. sys_users / 凭据 / token 类表即便是 super_admin / sync_admin 也严禁访问
    for admin_key in ("admin_ha", "admin_global", "sync_admin", "super_admin"):
        for forbidden_table in ("sys_users", "user_llm_configs", "auth_tokens"):
            resp = client.get(
                f"/api/medical-records/table-data/{forbidden_table}",
                headers=headers(admin_key),
            )
            assert resp.status_code == 403, f"{admin_key} accessing {forbidden_table}"
            assert "secret_user" not in resp.text

    # 3. get_schema 也不暴露 sys_users
    schema_resp = client.get("/api/medical-records/schema", headers=headers("super_admin"))
    assert schema_resp.status_code == 200
    table_names = {t["name"] for t in schema_resp.json()["tables"]}
    assert "mr" in table_names
    assert "sys_users" not in table_names

    # 4. 绑定院区的 admin 只能看到本院（H-A）数据；sync_admin / super_admin 可看全院区
    scoped_resp = client.get("/api/medical-records/table-data/mr", headers=headers("admin_ha"))
    assert scoped_resp.status_code == 200
    scoped_body = scoped_resp.json()
    assert scoped_body["total"] == 3
    assert {item["institute_id"] for item in scoped_body["items"]} == {"H-A"}

    global_resp = client.get("/api/medical-records/table-data/mr", headers=headers("sync_admin"))
    assert global_resp.status_code == 200
    assert global_resp.json()["total"] == 5


def test_table_data_rejects_unscoped_table_for_non_global_user() -> None:
    metadata = MetaData()
    Table("mr", metadata, Column("id", Integer, primary_key=True), Column("name", String))

    with pytest.raises(HTTPException) as exc:
        export_service.get_table_data(
            "mr",
            metadata=metadata,
            session_factory=lambda: None,
            institute_id="H-A",
            require_institute_scope=True,
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc_missing:
        export_service.get_table_data(
            "mr",
            metadata=metadata,
            session_factory=lambda: None,
            institute_id="",
            require_institute_scope=True,
        )
    assert exc_missing.value.status_code == 403


def test_frontpage_sheet_detects_cross_institute_conflict_and_locks_institute(
    export_sqlite_engine,
) -> None:
    # 1. 同 (patient_id, visit_id) 跨多院冲突 -> 409
    with pytest.raises(HTTPException) as exc_shared:
        export_service.get_frontpage_sheet(
            "P-2", "V-SHARED", session_factory=lambda: Session(export_sqlite_engine)
        )
    assert exc_shared.value.status_code == 409

    # 2. 同 visit_id 跨多院冲突（即使 patient_id 不同） -> 409
    with pytest.raises(HTTPException) as exc_collide:
        export_service.get_frontpage_sheet(
            "P-3", "V-COLLIDE", session_factory=lambda: Session(export_sqlite_engine)
        )
    assert exc_collide.value.status_code == 409

    # 3. 显式传入 institute_id 后可正常查询指定院区
    resolved = export_service.get_frontpage_sheet(
        "P-2",
        "V-SHARED",
        session_factory=lambda: Session(export_sqlite_engine),
        institute_id="H-A",
    )
    assert resolved["basic"]["institute_id"] == "H-A"
    assert resolved["basic"]["name"] == "A院患者"
    assert [d["diagnosis_name"] for d in resolved["diagnoses"]] == ["A院共享诊断"]

    # 4. 未传 institute_id 且 mr 仅单院存在时，用 fp.institute_id 锁定后续诊断/手术/费用查询，不串读 B 院
    sheet = export_service.get_frontpage_sheet(
        "P-1", "V-SINGLE", session_factory=lambda: Session(export_sqlite_engine)
    )
    assert sheet["basic"]["institute_id"] == "H-A"
    assert [d["diagnosis_name"] for d in sheet["diagnoses"]] == ["A院诊断"]
    assert [s["surgery_name"] for s in sheet["surgeries"]] == ["A院手术"]
    assert sheet["cost"]["total_cost"] == "1000.00"


# ============================================================================
# 3. P0-3: access_control.py + main.py + demo.py
# ============================================================================


def test_demo_prefix_is_not_public() -> None:
    assert "/api/v1/demo/" not in access_control.PUBLIC_PREFIX_PATHS
    assert access_control.is_public_path("/api/v1/demo/custom-rules") is False
    assert access_control.is_public_path("/api/v1/demo/qc-results/save") is False
    assert access_control.is_public_path("/api/v1/demo/frontpage-demo") is False


def test_demo_router_disabled_by_default_and_always_off_in_production(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_DEMO_API", raising=False)
    monkeypatch.setenv("ENV", "development")
    clear_settings_snapshot()
    app_default = create_app()
    assert TestClient(app_default).get("/api/v1/demo/custom-rules").status_code == 404

    monkeypatch.setenv("ENABLE_DEMO_API", "true")
    monkeypatch.setenv("ENV", "production")
    clear_settings_snapshot()
    app_prod = create_app()
    assert TestClient(app_prod).get("/api/v1/demo/custom-rules").status_code == 404

    monkeypatch.setenv("ENABLE_DEMO_API", "true")
    monkeypatch.setenv("ENV", "development")
    clear_settings_snapshot()
    app_dev = create_app()
    # 即使显式开启 ENABLE_DEMO_API，也不允许免认证访问（返回 401 而非 200 或 404）
    assert TestClient(app_dev).get("/api/v1/demo/custom-rules").status_code == 401
    clear_settings_snapshot()


def test_demo_endpoints_auth_mode_whitelist_uuid_validation_and_no_path_echo(
    tmp_path, monkeypatch
) -> None:
    demo_results_dir = tmp_path / "demo_qc_results"
    monkeypatch.setattr(demo, "DEMO_QC_RESULTS_DIR", demo_results_dir)

    users = {
        "doctor": {"id": "u-doc", "roles": ["doctor"], "is_active": True},
        "admin": {"id": "u-adm", "roles": ["admin"], "is_active": True},
    }
    monkeypatch.setattr(security, "resolve_user_by_subject", lambda sub: users.get(sub))

    app = FastAPI()
    app.include_router(demo.router)
    client = TestClient(app)

    doc_headers = {"Authorization": "Bearer " + security.create_access_token({"sub": "doctor"})}
    adm_headers = {"Authorization": "Bearer " + security.create_access_token({"sub": "admin"})}

    valid_save_payload = {
        "mode": "sequential_batch",
        "document_type": "admission_record",
        "rule_ids": ["LX-01"],
        "medical_text": "synthetic text",
        "medical_text_length": 14,
        "stats": {"total": 1, "issues": 0, "compliance_rate": 100},
        "performance": {"duration_ms": 10},
    }

    # 1. 写/LLM 端点未认证 401，非管理员 403
    for path, body in (
        ("/api/v1/demo/qc-results/save", valid_save_payload),
        ("/api/v1/demo/custom-rules/generate", {"requirement": "检查主诉完整性"}),
        ("/api/v1/demo/custom-rules/save", {"rule": {"name": "r", "description": "d", "custom_prompt": "p", "category": "c"}}),
    ):
        assert client.post(path, json=body).status_code in (401, 403)
        assert client.post(path, json=body, headers=doc_headers).status_code == 403

    # 读端点未认证拒绝
    for path in (
        "/api/v1/demo/custom-rules",
        "/api/v1/demo/qc-results/history",
        "/api/v1/demo/qc-results/latest",
        "/api/v1/demo/frontpage-demo",
    ):
        assert client.get(path).status_code in (401, 403)

    # 2. mode 路径穿越被严格枚举白名单拒绝 (422)
    bad_payload = {**valid_save_payload, "mode": "../../../evil"}
    bad_resp = client.post("/api/v1/demo/qc-results/save", json=bad_payload, headers=adm_headers)
    assert bad_resp.status_code == 422

    # 3. 合法保存不回显服务器绝对路径
    ok_resp = client.post("/api/v1/demo/qc-results/save", json=valid_save_payload, headers=adm_headers)
    assert ok_resp.status_code == 200, ok_resp.text
    ok_data = ok_resp.json()["data"]
    saved_id = ok_data["id"]
    uuid.UUID(saved_id)
    assert "path" not in ok_data
    assert str(tmp_path) not in ok_resp.text

    # 4. result_id 通配符/非 UUID 被 400 拒绝，杜绝 glob 泄露
    for bad_id in ("*", "%3F%3F*", "demo_*", "not-a-uuid"):
        resp = client.get(f"/api/v1/demo/qc-results/{bad_id}", headers=adm_headers)
        assert resp.status_code == 400, f"bad_id={bad_id} got {resp.status_code}"

    # 5. 合法 UUID 查询与 /latest 均正常工作
    detail_resp = client.get(f"/api/v1/demo/qc-results/{saved_id}", headers=adm_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["data"]["id"] == saved_id

    latest_resp = client.get("/api/v1/demo/qc-results/latest", headers=adm_headers)
    assert latest_resp.status_code == 200
    assert latest_resp.json()["data"]["id"] == saved_id


# ============================================================================
# 4. P1-B3: security.py + auth.py
# ============================================================================


def test_access_token_type_claim_and_rejection_of_non_access_tokens(monkeypatch) -> None:
    settings = get_settings()
    fake_user = {
        "id": "u-jwt-1",
        "email": "jwt@medqc.com",
        "username": "jwt_user",
        "display_name": "JWT用户",
        "department": "内科",
        "institute_id": "H-A",
        "roles": ["doctor"],
        "password_hash": security.get_password_hash("StrongPass123!"),
        "avatar": "",
        "phone": "13800000000",
        "bio": "",
        "created_at": "2026-01-01T00:00:00Z",
        "last_login": None,
        "is_active": True,
    }
    monkeypatch.setattr(security, "resolve_user_by_subject", lambda sub: fake_user if sub == fake_user["email"] else None)
    monkeypatch.setattr(auth, "find_user_by_account", lambda acc: fake_user if acc == fake_user["email"] else None)
    monkeypatch.setattr(auth, "resolve_auth_store_user_by_subject", lambda sub: fake_user if sub == fake_user["email"] else None)
    monkeypatch.setattr(auth, "touch_last_login", lambda _uid: fake_user)

    app = FastAPI(dependencies=[Depends(access_control.enforce_default_auth)])
    app.include_router(auth.router)
    client = TestClient(app)

    # 1. 登录签发的 access_token 包含 type=access，refresh_token 包含 type=refresh
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": fake_user["email"], "password": "StrongPass123!"},
    )
    assert login_resp.status_code == 200, login_resp.text
    access_token = login_resp.json()["access_token"]
    refresh_token = login_resp.json()["refresh_token"]

    access_payload = jwt.decode(access_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    refresh_payload = jwt.decode(refresh_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"

    # 2. 刷新签发的新 access_token 也包含 type=access
    ref_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert ref_resp.status_code == 200, ref_resp.text
    refreshed_access = ref_resp.json()["access_token"]
    refreshed_payload = jwt.decode(refreshed_access, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert refreshed_payload["type"] == "access"

    # 3. 合法 access_token 可访问 /me
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}).status_code == 200

    # 4. refresh_token 与 password_reset_token 不能冒用为 Bearer Access Token
    reset_token = security.create_password_reset_token(fake_user["email"])
    for non_access_token in (refresh_token, reset_token):
        assert (
            client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {non_access_token}"},
            ).status_code
            == 401
        )
        with pytest.raises(HTTPException) as exc1:
            security.resolve_current_user_from_token(non_access_token)
        assert exc1.value.status_code == 401
        with pytest.raises(HTTPException) as exc2:
            security._decode_token(non_access_token, expected_type="access")
        assert exc2.value.status_code == 401

    # 5. 兼容无 type 字段的历史合法 access token（但仍不可用于 refresh / password_reset）
    legacy_access = jwt.encode(
        {"sub": fake_user["email"], "exp": datetime.utcnow() + timedelta(minutes=15)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    resolved = security.resolve_current_user_from_token(legacy_access)
    assert resolved["id"] == fake_user["id"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {legacy_access}"}).status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": legacy_access}).status_code == 401
    with pytest.raises(HTTPException) as exc3:
        security.verify_password_reset_token(legacy_access)
    assert exc3.value.status_code == 401
