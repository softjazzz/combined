"""T1-Batch 1 安全回归单测（纯离线 / 内存 SQLite / tmp_path）。

覆盖 6 项 P0 安全修复：
1. 全局 super_admin 角色展开基座（roles.py / security.py / account_management_service.py）与禁止停用/降权本机构最后活跃管理员
2. 认证链路漏洞清零（PUT /auth/password 旧密码与 72 字节校验、login/forgot-password 限流、下线 reset_token 直出与 some-reset-token 后门）
3. SSRF / 内网探测防护（core/http.py IPv6 urlsplit、llm_endpoint_settings.py、clinical_sources.py /check、sync.py PUT /config/pg）
4. 全局系统配置 12 个路由与 daily_qc 绑定院区 admin IDOR 封堵
5. sync.py 忽略 "***" 掩码、llm_configs.py 写响应投影与元数据角色收紧、scoring_config.py 读鉴权/Pydantic 校验/500 脱敏、frontpage_settings.py 加锁原子写
"""

from __future__ import annotations

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import http as http_module
from app.core import roles as roles_module
from app.core import security as security_module
from app.core.rate_limit import reset_rate_limit_store_for_testing
from app.core.settings import Settings
from app.database.models.cdm import InpatRegistration, MedicalRecordFrontpage
from app.database.models.v36_reports import SysUser
from app.routers import (
    auth as auth_router,
    clinical_sources as clinical_sources_router,
    daily_qc as daily_qc_router,
    data_pipelines as data_pipelines_router,
    frontpage_settings as frontpage_settings_router,
    llm_configs as llm_configs_router,
    llm_info as llm_info_router,
    llm_observability_read as llm_obs_router,
    qc_llm_configs as qc_llm_configs_router,
    qc_runtime_settings as qc_runtime_router,
    qc_settings as qc_settings_router,
    scoring_config as scoring_config_router,
    sync as sync_router,
    system_config as system_config_router,
)
from app.services import frontpage_settings as frontpage_settings_service
from app.services import llm_endpoint_settings as endpoint_settings
from app.services.account_management_service import AccountManagementService
from app.services.daily_qc import service as daily_qc_service
from app.services.daily_qc.contracts import PlanInput
from app.services.daily_qc.store import ScheduleStore, tables as daily_qc_tables
from app.services.defect_rectification_service import RectificationError
from app.services.llm_observability_read import LLMObservabilityReadService
from app.storage.memory import llm_configs as memory_llm_configs


# ============================================================================
# 1. 全局 super_admin 角色展开基座 & 账号管理最后管理员保护
# ============================================================================


def test_super_admin_role_expansion_and_security_dependencies() -> None:
    expanded = roles_module.effective_roles(["super_admin"])
    assert {"super_admin", "admin", "qc_manager", "developer"} <= set(expanded)
    assert "doctor" not in expanded
    assert "sync_admin" not in expanded

    app = FastAPI()

    @app.get("/need-admin")
    async def need_admin(user: dict = Depends(security_module.require_admin)):
        return {"ok": True, "id": user["id"]}

    @app.get("/need-coder")
    async def need_coder(user: dict = Depends(security_module.require_roles("coder"))):
        return {"ok": True, "id": user["id"]}

    current = {"id": "u-super", "roles": ["super_admin"], "institute_id": ""}
    app.dependency_overrides[security_module.get_current_user] = lambda: dict(current)

    with TestClient(app) as client:
        assert client.get("/need-admin").status_code == 200
        assert client.get("/need-coder").status_code == 200
        current["roles"] = ["doctor"]
        assert client.get("/need-admin").status_code == 403
        assert client.get("/need-coder").status_code == 403


def test_account_management_super_admin_and_last_active_admin_guard() -> None:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    SysUser.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with sessions.begin() as session:
        for uid, role, inst in (
            ("super1", "super_admin", None),
            ("adm-a1", "admin", "H-A"),
            ("adm-a2", "admin", "H-A"),
            ("adm-b1", "admin", "H-B"),
        ):
            session.add(
                SysUser(
                    id=uid,
                    username=uid,
                    email=f"{uid}@example.com",
                    display_name=uid,
                    institute_id=inst,
                    department="信息科",
                    role=role,
                    roles_json=json.dumps([role]),
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
    try:
        svc = AccountManagementService(sessions)
        listed = svc.list("super1")
        assert listed["total"] == 4
        assert listed["managed_institute_id"] is None

        # H-A 有两名活跃管理员，停用其中一名允许
        a2_row = next(item for item in listed["items"] if item["id"] == "adm-a2")
        disabled = svc.update(
            "super1",
            "adm-a2",
            {
                "display_name": "adm-a2",
                "institute_id": "H-A",
                "department": "信息科",
                "roles": ["admin"],
                "is_active": False,
                "expected_updated_at": datetime.fromisoformat(a2_row["updated_at"]),
            },
        )
        assert disabled["is_active"] is False

        # 现在 adm-a1 是 H-A 最后一个活跃管理员：停用、降权、迁出院区均必须 409 拦截
        a1_row = next(item for item in svc.list("super1")["items"] if item["id"] == "adm-a1")
        for forbidden_change in (
            {"is_active": False},
            {"roles": ["qc_manager"]},
            {"institute_id": "H-B"},
        ):
            with pytest.raises(RectificationError) as exc:
                svc.update(
                    "super1",
                    "adm-a1",
                    {
                        "display_name": "adm-a1",
                        "institute_id": "H-A",
                        "department": "信息科",
                        "roles": ["admin"],
                        "is_active": True,
                        "expected_updated_at": datetime.fromisoformat(a1_row["updated_at"]),
                        **forbidden_change,
                    },
                )
            assert exc.value.status == 409
    finally:
        engine.dispose()


# ============================================================================
# 2. 认证链路漏洞清零（routers/auth.py）
# ============================================================================


def _make_auth_test_app(monkeypatch):
    user = {
        "id": "u-auth-1",
        "email": "user@example.com",
        "username": "user1",
        "display_name": "测试用户",
        "department": "内科",
        "institute_id": "H-A",
        "roles": ["doctor"],
        "password_hash": security_module.get_password_hash("OldPass123!"),
        "avatar": "",
        "phone": "13800001111",
        "bio": "",
        "created_at": "2026-01-01T00:00:00Z",
        "last_login": None,
        "is_active": True,
    }
    monkeypatch.setattr(
        auth_router,
        "find_user_by_account",
        lambda acc: user if str(acc or "").strip().lower() in {user["email"], user["username"]} else None,
    )
    monkeypatch.setattr(
        auth_router,
        "resolve_auth_store_user_by_subject",
        lambda sub: user if str(sub or "").strip().lower() in {user["email"], user["id"]} else None,
    )
    monkeypatch.setattr(auth_router, "touch_last_login", lambda _uid: user)

    def _update_pwd(*, user_id: str, password_hash: str):
        if user_id != user["id"]:
            return None
        user["password_hash"] = password_hash
        return dict(user)

    monkeypatch.setattr(auth_router, "update_user_password", _update_pwd)
    app = FastAPI()
    app.include_router(auth_router.router)
    app.dependency_overrides[auth_router.get_current_user] = lambda: user
    return TestClient(app), user


def test_update_password_requires_current_password_and_enforces_72_byte_limit(monkeypatch) -> None:
    client, user = _make_auth_test_app(monkeypatch)
    # 1. 缺失 current_password -> 422
    assert client.put("/api/v1/auth/password", data={"new_password": "NewPass123!"}).status_code == 422
    # 2. 空 current_password -> 400
    assert (
        client.put("/api/v1/auth/password", data={"current_password": "   ", "new_password": "NewPass123!"}).status_code
        == 400
    )
    # 3. 错误 current_password -> 400
    assert (
        client.put("/api/v1/auth/password", data={"current_password": "WrongPass!", "new_password": "NewPass123!"}).status_code
        == 400
    )
    # 4. 超 72 字节 UTF-8 新密码 -> 422（绝不触发 bcrypt ValueError 500）
    assert (
        client.put("/api/v1/auth/password", data={"current_password": "OldPass123!", "new_password": "密" * 25}).status_code
        == 422
    )
    assert (
        client.put("/api/v1/auth/password", data={"current_password": "OldPass123!", "new_password": "a" * 73}).status_code
        == 422
    )
    # 5. 空白新密码 -> 422
    assert (
        client.put("/api/v1/auth/password", data={"current_password": "OldPass123!", "new_password": "   "}).status_code
        == 422
    )
    # 6. 正确旧密码 + 合法新密码 -> 200
    ok = client.put(
        "/api/v1/auth/password",
        data={"current_password": "OldPass123!", "new_password": "NewPass456!"},
    )
    assert ok.status_code == 200
    assert security_module.verify_password("NewPass456!", user["password_hash"])


def test_login_and_forgot_password_rate_limit_and_no_reset_token_leak(monkeypatch) -> None:
    reset_rate_limit_store_for_testing()
    client, user = _make_auth_test_app(monkeypatch)

    # 登录限流：失败尝试也计入桶，第 11 次触发 429；超 72 字节口令绝不 500
    long_resp = client.post("/api/v1/auth/login", json={"email": user["email"], "password": "x" * 100})
    assert long_resp.status_code in (401, 422)
    reset_rate_limit_store_for_testing()
    for _ in range(10):
        assert client.post("/api/v1/auth/login", json={"email": user["email"], "password": "WrongPassword123!"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": user["email"], "password": "OldPass123!"}).status_code == 429

    # 忘记密码：非生产环境也不回传 reset_token，存在/不存在邮箱返回一致，第 6 次触发 429
    resp_exist = client.post("/api/v1/auth/forgot-password", json={"email": user["email"]})
    resp_missing = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp_exist.status_code == 200
    assert resp_missing.status_code == 200
    assert resp_exist.json()["data"] == {}
    assert resp_missing.json()["data"] == {}
    assert "reset_token" not in resp_exist.text
    for _ in range(3):
        assert client.post("/api/v1/auth/forgot-password", json={"email": user["email"]}).status_code == 200
    assert client.post("/api/v1/auth/forgot-password", json={"email": user["email"]}).status_code == 429

    # reset-password：占位后门 some-reset-token 被拒绝（401），超长新密码返回 422
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": "some-reset-token", "new_password": "NewPass123!"},
        ).status_code
        == 401
    )
    real_token = security_module.create_password_reset_token(user["email"])
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": real_token, "new_password": "密" * 25},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": real_token, "new_password": "ValidReset123!"},
        ).status_code
        == 200
    )
    # 重放必须 401
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": real_token, "new_password": "AnotherReset123!"},
        ).status_code
        == 401
    )


# ============================================================================
# 3. SSRF / 内网探测防护
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_url",
    [
        "http://[::1]:11434/v1/chat/completions",
        "http://[::ffff:169.254.169.254]/latest/meta-data",
        "http://[::ffff:127.0.0.1]:8080/v1",
        "http://127.0.0.1:8080/v1",
        "http://0.0.0.0/v1",
        "http://169.254.169.254/latest/meta-data",
        "http://100.100.100.200/latest/meta-data",
    ],
)
async def test_core_http_safe_post_json_blocks_ipv6_and_ssrf_targets(monkeypatch, bad_url: str) -> None:
    clean_cfg = Settings(
        _env_file=None,
        JWT_SECRET="test-only",
        OUTBOUND_ALLOWLIST=["dashscope.aliyuncs.com", "api.deepseek.com"],
    )
    monkeypatch.setattr(http_module, "get_settings", lambda: clean_cfg)
    with pytest.raises(ValueError):
        await http_module.safe_post_json(bad_url, {}, {}, 5)


@pytest.mark.parametrize(
    "bad_endpoint",
    [
        "http://127.0.0.1:11434/v1",
        "http://[::1]:11434/v1",
        "http://0.0.0.0:8000/v1",
        "http://10.0.0.1/v1",
        "http://172.16.0.5/v1",
        "http://192.168.1.10/v1",
        "http://169.254.169.254/latest/meta-data",
        "http://100.100.100.200/latest/meta-data",
        "http://[::ffff:169.254.169.254]/latest/meta-data",
        "http://[::ffff:127.0.0.1]/v1",
        "http://localhost:11434/v1",
        "http://sub.localhost/v1",
        "http://metadata.google.internal/computeMetadata/v1",
        "http://2130706433/v1",
    ],
)
def test_llm_endpoint_settings_blocks_ssrf_addresses(monkeypatch, bad_endpoint: str) -> None:
    clean_cfg = Settings(
        _env_file=None,
        JWT_SECRET="test-only",
        OUTBOUND_ALLOWLIST=["dashscope.aliyuncs.com", "api.deepseek.com"],
    )
    monkeypatch.setattr("app.core.settings.get_settings", lambda: clean_cfg)
    with pytest.raises(ValueError):
        endpoint_settings.EndpointUpdate(version=0, enabled=True, endpoint=bad_endpoint)


def test_llm_endpoint_settings_blocks_dns_resolving_to_private_and_allows_allowlist(monkeypatch) -> None:
    monkeypatch.setattr(
        endpoint_settings.socket,
        "getaddrinfo",
        lambda host, *_a, **_kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 0))]
        if host == "rebind.example"
        else (_ for _ in ()).throw(socket.gaierror("offline")),
    )
    with pytest.raises(ValueError):
        endpoint_settings.EndpointUpdate(version=0, enabled=True, endpoint="http://rebind.example/v1")

    # 显式 OUTBOUND_ALLOWLIST 放行
    cfg = Settings(_env_file=None, JWT_SECRET="test-only", OUTBOUND_ALLOWLIST=["127.0.0.1", "ollama.internal"])
    monkeypatch.setattr("app.core.settings.get_settings", lambda: cfg)
    allowed = endpoint_settings.EndpointUpdate(version=0, enabled=True, endpoint="http://127.0.0.1:11434/v1")
    assert allowed.endpoint == "http://127.0.0.1:11434/v1"


@pytest.mark.parametrize(
    "bad_host",
    ["127.0.0.1", "::1", "0.0.0.0", "169.254.169.254", "::ffff:169.254.169.254", "100.100.100.200", "localhost"],
)
def test_clinical_sources_check_and_sync_pg_config_block_ssrf_hosts(monkeypatch, bad_host: str) -> None:
    monkeypatch.delenv("CLINICAL_SOURCE_HOST_ALLOWLIST", raising=False)
    monkeypatch.delenv("SYNC_PG_HOST_ALLOWLIST", raising=False)
    monkeypatch.delenv("DB_TARGET_HOST_ALLOWLIST", raising=False)

    # 1. clinical_sources /check
    cs_app = FastAPI()
    cs_app.include_router(clinical_sources_router.router)
    cs_app.dependency_overrides[data_pipelines_router.require_pipeline_admin] = lambda: {
        "id": "sync-1",
        "roles": {"sync_admin"},
        "institute_id": None,
    }
    with TestClient(cs_app) as client:
        resp = client.post(
            "/api/v1/clinical-sources/check",
            json={"version": 0, "cdm": {"enabled": True, "host": bad_host, "port": 5432, "database": "cdm", "username": "r"}},
        )
        assert resp.status_code == 422

    # 2. sync PUT /config/pg
    sync_app = FastAPI()
    sync_app.include_router(sync_router.router)
    sync_app.dependency_overrides[sync_router.require_legacy_sync_available] = lambda: None
    sync_app.dependency_overrides[sync_router.get_current_user] = lambda: {
        "id": "u-sync",
        "roles": ["sync_admin"],
    }
    monkeypatch.setattr(
        "app.services.etl_sync.load_db_config",
        lambda: {"remote_host": "10.10.10.8", "remote_port": "5432", "default_institute_id": "H-A"},
    )
    monkeypatch.setattr(
        "app.services.etl_sync.save_db_config",
        lambda *_a, **_kw: pytest.fail("unsafe host must not save"),
    )
    monkeypatch.setattr(
        "app.services.etl_sync.test_remote_connection",
        lambda: pytest.fail("unsafe host must not probe"),
    )
    with TestClient(sync_app) as client:
        resp = client.put(
            "/api/v1/sync/config/pg",
            json={"remote_host": bad_host, "default_institute_id": "H-A"},
        )
        assert resp.status_code == 422


def test_sync_pg_config_respects_explicit_host_allowlist_and_ignores_password_mask(monkeypatch) -> None:
    monkeypatch.setenv("SYNC_PG_HOST_ALLOWLIST", "127.0.0.1,10.20.0.0/16")
    saved = {}
    monkeypatch.setattr(
        "app.services.etl_sync.load_db_config",
        lambda: {
            "remote_host": "10.20.1.5",
            "remote_port": "5432",
            "remote_database": "his",
            "remote_username": "reader",
            "remote_password": "real-secret-password",
            "default_institute_id": "H-A",
        },
    )
    monkeypatch.setattr(
        "app.services.etl_sync.save_db_config",
        lambda cfg, runtime_password=None: saved.update(cfg=dict(cfg), runtime_password=runtime_password) or cfg,
    )
    monkeypatch.setattr("app.services.etl_sync.test_remote_connection", lambda: {"connected": True, "error": ""})
    monkeypatch.setattr(sync_router, "audit_event", lambda *_a, **_kw: None)

    app = FastAPI()
    app.include_router(sync_router.router)
    app.dependency_overrides[sync_router.require_legacy_sync_available] = lambda: None
    app.dependency_overrides[sync_router.get_current_user] = lambda: {
        "id": "u-sync",
        "roles": ["sync_admin"],
    }
    with TestClient(app) as client:
        # 不在白名单 -> 422
        assert (
            client.put("/api/v1/sync/config/pg", json={"remote_host": "10.99.1.1", "default_institute_id": "H-A"}).status_code
            == 422
        )
        # 在白名单 + 回传 "***" 掩码 -> 200 且不覆写原密码
        ok = client.put(
            "/api/v1/sync/config/pg",
            json={"remote_host": "127.0.0.1", "remote_password": "***", "default_institute_id": "H-A"},
        )
        assert ok.status_code == 200, ok.text
        assert saved["cfg"]["remote_password"] == "real-secret-password"
        assert saved["runtime_password"] is None


# ============================================================================
# 4. 全局系统配置与定时质控绑定院区 admin IDOR 封堵
# ============================================================================


def test_bound_institute_admin_rejected_across_all_global_system_config_routers(monkeypatch, tmp_path) -> None:
    # 准备内存 SQLite 持久账号表：包含绑定院区 admin、绑定院区 super_admin、全局 admin、全局 super_admin、sync_admin
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    SysUser.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as session:
        for uid, role, inst in (
            ("bound-admin", "admin", "H-A"),
            ("bound-super", "super_admin", "H-A"),
            ("global-admin", "admin", None),
            ("global-super", "super_admin", ""),
            ("sync-bound", "sync_admin", "H-A"),
        ):
            session.add(
                SysUser(
                    id=uid,
                    username=uid,
                    display_name=uid,
                    institute_id=inst,
                    role=role,
                    roles_json=json.dumps([role]),
                    is_active=True,
                )
            )

    from app.database import connection as db_conn

    monkeypatch.setattr(db_conn, "SessionLocal", sessions)
    monkeypatch.setattr(data_pipelines_router, "SessionLocal", sessions)
    monkeypatch.setattr(qc_settings_router, "CONFIG_PATH", tmp_path / "qc_settings.json")
    monkeypatch.setattr(frontpage_settings_service, "CONFIG_PATH", tmp_path / "frontpage_settings.json")
    monkeypatch.setattr(llm_info_router, "CUSTOM_MODELS_FILE", tmp_path / "custom_models.json")
    monkeypatch.setattr(llm_configs_router, "get_supabase", lambda: None)
    monkeypatch.setattr(scoring_config_router, "get_supabase", lambda: MagicMock())
    monkeypatch.setattr(scoring_config_router, "async_execute", AsyncMock(return_value=MagicMock(data=[])))

    app = FastAPI()
    for r in (
        data_pipelines_router.router,
        clinical_sources_router.router,
        llm_configs_router.router,
        llm_info_router.router,
        qc_runtime_router.router,
        qc_settings_router.router,
        qc_llm_configs_router.router,
        frontpage_settings_router.router,
        llm_obs_router.router,
        system_config_router.router,
        sync_router.router,
        scoring_config_router.router,
    ):
        app.include_router(r)
    app.dependency_overrides[sync_router.require_legacy_sync_available] = lambda: None
    app.dependency_overrides[llm_obs_router.get_llm_observability_read_service] = lambda: (
        LLMObservabilityReadService(reader=SimpleNamespace(fetch_events=AsyncMock(return_value=[])))
    )

    actor: dict = {"id": "bound-admin", "roles": ["admin"], "institute_id": "H-A"}
    app.dependency_overrides[security_module.get_current_user] = lambda: dict(actor)

    endpoints = [
        ("GET", "/api/v1/sync/pipelines", None),
        ("PUT", "/api/v1/sync/pipelines", {"version": 0, "independent_enabled": False}),
        ("GET", "/api/v1/clinical-sources", None),
        ("POST", "/api/v1/clinical-sources/check", {"version": 0}),
        ("GET", "/api/v1/llm/configs", None),
        ("POST", "/api/v1/llm/configs", {"config_name": "default", "provider_code": "alibaba", "model_code": "qwen3.8-flash"}),
        ("GET", "/api/v1/llm/configs/default/summary", None),
        ("GET", "/api/v1/llm/providers", None),
        ("GET", "/api/v1/llm/models", None),
        ("POST", "/api/v1/llm/models/custom", {"provider_code": "alibaba", "model_code": "x"}),
        ("GET", "/api/v1/system/qc-runtime", None),
        ("GET", "/api/v1/qc/settings", None),
        ("PUT", "/api/v1/qc/settings", {"temperature": 0.3}),
        ("GET", "/api/v1/qc/llm-configs", None),
        ("PUT", "/api/v1/frontpage/settings", {"demo_hide_threshold": 2}),
        ("POST", "/api/v1/frontpage/settings/reset", None),
        ("GET", "/api/v1/system/llm-observability/overview", None),
        ("GET", "/api/system/db/status", None),
        ("PUT", "/api/v1/sync/config/pg", {"remote_host": "10.10.10.8", "default_institute_id": "H-A"}),
        ("PUT", "/api/v1/sync/config/policy", {}),
        ("PUT", "/api/v1/scoring-config", {"pass_score": 70}),
    ]

    try:
        with TestClient(app) as client:
            # 1. 绑定院区 admin（即使伪造 token 省略 institute_id，也会被持久账号表复核拦截 403！）
            for stub in (
                {"id": "bound-admin", "roles": ["admin"], "institute_id": "H-A"},
                {"id": "bound-admin", "roles": ["admin"]},  # 令牌省略 institute_id
            ):
                actor.clear()
                actor.update(stub)
                for method, path, body in endpoints:
                    resp = client.request(method, path, json=body)
                    assert resp.status_code == 403, f"{stub} {method} {path} expected 403, got {resp.status_code}"

            # 2. 全局 admin 与任意 super_admin / sync_admin 均放行（以代表性端点验证）
            for stub in (
                {"id": "global-admin", "roles": ["admin"], "institute_id": ""},
                {"id": "global-super", "roles": ["super_admin"], "institute_id": ""},
                {"id": "bound-super", "roles": ["super_admin"], "institute_id": "H-A"},
                {"id": "sync-bound", "roles": ["sync_admin"], "institute_id": "H-A"},
            ):
                actor.clear()
                actor.update(stub)
                assert client.get("/api/v1/qc/settings").status_code == 200
                assert client.put("/api/v1/frontpage/settings", json={"demo_hide_threshold": 3}).status_code == 200
                assert client.get("/api/v1/system/llm-observability/overview").status_code == 200
                assert client.put("/api/v1/scoring-config", json={"pass_score": 70}).status_code == 200
    finally:
        engine.dispose()


def test_daily_qc_super_admin_access_and_bound_admin_institute_isolation(monkeypatch) -> None:
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    sessions = sessionmaker(bind=engine)
    metadata, _, _ = daily_qc_tables()
    metadata.create_all(engine)
    SysUser.__table__.create(engine)
    InpatRegistration.__table__.create(engine)
    MedicalRecordFrontpage.__table__.create(engine)
    with sessions.begin() as session:
        session.add_all(
            [
                SysUser(
                    id="pure-super",
                    username="pure-super",
                    display_name="纯超管",
                    institute_id=None,
                    role="super_admin",
                    roles_json='["super_admin"]',
                    is_active=True,
                ),
                SysUser(
                    id="bound-a",
                    username="bound-a",
                    display_name="A院管理员",
                    institute_id="H-A",
                    role="admin",
                    roles_json='["admin"]',
                    is_active=True,
                ),
            ]
        )
        session.add_all(
            [
                MedicalRecordFrontpage(
                    institute_id="H-A", patient_id="P1", visit_id="V1", discharge_dept_name="内科"
                ),
                MedicalRecordFrontpage(
                    institute_id="H-B", patient_id="P2", visit_id="V2", discharge_dept_name="外科"
                ),
            ]
        )

    store = ScheduleStore(sessions)
    from app.services import clinical_read, clinical_source_policy
    from app.database import clinical_connection
    from app.services.qc_workspace.record_repository import RecordRepository

    monkeypatch.setattr(clinical_source_policy, "fixed_cdm", lambda: False)
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: None)
    monkeypatch.setattr(
        RecordRepository,
        "get_record_filters",
        lambda self, *, scope, department=None, institute_id=None: {
            "departments": ["内科"] if institute_id == "H-A" else ["外科"]
        },
    )

    app = FastAPI()
    app.include_router(daily_qc_router.router)
    app.dependency_overrides[daily_qc_router.store_dependency] = lambda: store
    current = {"id": "pure-super", "roles": ["super_admin"]}
    app.dependency_overrides[daily_qc_router.get_current_user] = lambda: dict(current)

    try:
        with TestClient(app) as client:
            # 1. 纯 super_admin 放行并可见所有已同步机构
            super_opts = client.get("/api/v1/qc/daily-schedules/options")
            assert super_opts.status_code == 200, super_opts.text
            assert super_opts.json()["data"]["institutes"] == ["H-A", "H-B"]

            # 2. 绑定院区 admin 仅见本院 H-A，请求 H-B 选项或创建 H-B 计划均 403
            current.update(id="bound-a", roles=["admin"])
            a_opts = client.get("/api/v1/qc/daily-schedules/options")
            assert a_opts.status_code == 200, a_opts.text
            assert a_opts.json()["data"]["institutes"] == ["H-A"]

            assert client.get("/api/v1/qc/daily-schedules/options", params={"institute_id": "H-B"}).status_code == 403
            plan_b = PlanInput(
                name="越权计划", time_of_day="08:05", timezone="Asia/Shanghai", institute_id="H-B", rule_set_key="luxian_0609_qc_v1"
            ).model_dump()
            assert client.post("/api/v1/qc/daily-schedules", json=plan_b).status_code == 403

            # 本院计划允许创建
            plan_a = PlanInput(
                name="本院计划", time_of_day="08:05", timezone="Asia/Shanghai", institute_id="H-A", rule_set_key="luxian_0609_qc_v1"
            ).model_dump()
            created = client.post("/api/v1/qc/daily-schedules", json=plan_a)
            assert created.status_code == 200, created.text
            plan_id = created.json()["data"]["id"]
            # 更新时切换为 H-B 也必须 403
            assert (
                client.put(
                    f"/api/v1/qc/daily-schedules/{plan_id}",
                    json={"revision": 1, "definition": plan_b},
                ).status_code
                == 403
            )
    finally:
        engine.dispose()


# ============================================================================
# 5. 写响应投影 / LLM 元数据鉴权 / scoring_config 校验脱敏 / frontpage 原子写
# ============================================================================


def test_llm_configs_post_projects_row_and_metadata_routes_block_non_admins(monkeypatch) -> None:
    before = dict(memory_llm_configs)
    app = FastAPI()
    app.include_router(llm_configs_router.router)
    app.include_router(llm_info_router.router)

    actor = {"id": "u-sync", "roles": ["sync_admin"]}
    app.dependency_overrides[security_module.get_current_user] = lambda: dict(actor)

    async def _fake_save(_payload, _request):
        return {
            "id": "cfg-1",
            "user_id": None,
            "config_name": "default",
            "provider_code": "alibaba",
            "model_code": "qwen3.8-flash",
            "api_key_encrypted": "TOP-SECRET-CIPHERTEXT",
            "api_key": "RAW-SECRET",
            "unexpected_col": "should-never-leak",
            "custom_parameters": {"temperature": 0.2},
            "is_active": True,
        }

    monkeypatch.setattr(llm_configs_router, "_save_config_internal", _fake_save)
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/llm/configs",
                json={"config_name": "default", "provider_code": "alibaba", "model_code": "qwen3.8-flash"},
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["api_key_configured"] is True
            assert "api_key_encrypted" not in data
            assert "api_key" not in data
            assert "unexpected_col" not in data
            assert "TOP-SECRET-CIPHERTEXT" not in resp.text
            assert "RAW-SECRET" not in resp.text

            # 非管理员不能读取 /providers /models /configs/default/summary
            for role in ("doctor", "qc_manager"):
                actor["roles"] = [role]
                assert client.get("/api/v1/llm/providers").status_code == 403
                assert client.get("/api/v1/llm/models").status_code == 403
                assert client.get("/api/v1/llm/configs/default/summary").status_code == 403
    finally:
        memory_llm_configs.clear()
        memory_llm_configs.update(before)


def test_scoring_config_read_rbac_validation_and_error_desensitization(monkeypatch) -> None:
    fake_sb = MagicMock()
    monkeypatch.setattr(scoring_config_router, "get_supabase", lambda: fake_sb)
    monkeypatch.setattr(scoring_config_router, "async_execute", AsyncMock(return_value=MagicMock(data=[])))

    app = FastAPI()
    app.include_router(scoring_config_router.router)
    actor = {"id": "u-doc", "roles": ["doctor"]}
    app.dependency_overrides[security_module.get_current_user] = lambda: dict(actor)

    with TestClient(app) as client:
        # 读接口与预览接口拒绝 doctor
        assert client.get("/api/v1/scoring-config").status_code == 403
        assert client.post("/api/v1/scoring-config/preview", json={"score": 88}).status_code == 403

        # qc_manager 可读/预览，不可写
        actor.update(id="u-qcm", roles=["qc_manager"])
        assert client.get("/api/v1/scoring-config").status_code == 200
        assert client.post("/api/v1/scoring-config/preview", json={"score": 88}).status_code == 200
        assert client.put("/api/v1/scoring-config", json={"pass_score": 65}).status_code == 403

        # 全局管理员校验非法/倒挂阈值 -> 422
        actor.update(id="u-gadm", roles=["admin"], institute_id="")
        for bad_payload in (
            {"grade_thresholds": {"甲": {"min_score": 60}, "乙": {"min_score": 70}}},
            {"grade_thresholds": {"乙": {"min_score": 0}, "丙": {"min_score": 0}}},
            {"grade_thresholds": {"丙": {"min_score": -1}}},
            {"grade_thresholds": {"甲": {"min_score": "not-a-number"}}},
            {"grade_thresholds": {"甲": {"min_score": True}}},
            {"pass_score": 120},
            {"unknown_key": 1},
        ):
            assert client.put("/api/v1/scoring-config", json=bad_payload).status_code == 422, bad_payload

        # 500 错误脱敏（不得泄露底层异常原文）
        monkeypatch.setattr(
            scoring_config_router,
            "async_execute",
            AsyncMock(side_effect=RuntimeError("SECRET_PG_DSN=postgres://admin:pwd@10.0.0.1/medqc")),
        )
        for method, path, body in (
            ("GET", "/api/v1/scoring-config", None),
            ("PUT", "/api/v1/scoring-config", {"pass_score": 70}),
            ("POST", "/api/v1/scoring-config/preview", {"score": 88}),
        ):
            resp = client.request(method, path, json=body)
            assert resp.status_code == 500
            assert "SECRET_PG_DSN" not in resp.text
            assert "postgres://" not in resp.text


def test_frontpage_settings_atomic_write_and_failure_preserves_file(monkeypatch, tmp_path) -> None:
    cfg_path = tmp_path / "frontpage_settings.json"
    monkeypatch.setattr(frontpage_settings_service, "CONFIG_PATH", cfg_path)
    monkeypatch.setattr(frontpage_settings_service, "_is_production_env", lambda: False)

    # 并发更新不损坏 JSON
    def _worker(idx: int):
        frontpage_settings_service.update_frontpage_settings({"demo_hide_threshold": idx})

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(_worker, range(1, 13)))
    parsed = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert 1 <= parsed["demo_hide_threshold"] <= 12
    assert list(tmp_path.glob("*.tmp")) == []

    # 模拟 os.replace 失败：旧文件必须保持完整且不残留临时文件
    before_text = cfg_path.read_text(encoding="utf-8")
    monkeypatch.setattr(
        frontpage_settings_service.os,
        "replace",
        lambda *_a, **_kw: (_ for _ in ()).throw(PermissionError("synthetic replace failure")),
    )
    with pytest.raises(PermissionError):
        frontpage_settings_service.update_frontpage_settings({"demo_hide_threshold": 999})
    assert cfg_path.read_text(encoding="utf-8") == before_text
    assert list(tmp_path.glob("*.tmp")) == []
