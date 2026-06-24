# Backend Release Gate Report

- total gates: 9
- passed gates: 9
- failed gates: 0
- all passed: True

## Gate Details
- auth_guard: PASS (0.13s)
  metrics: {"required_checks": 7, "passed_checks": 7, "coverage_ratio": 1.0}
- secret_hygiene: PASS (0.15s)
  metrics: {"findings": 0}
- alert_rules: PASS (0.14s)
  metrics: {"pass_marker_found": true}
- openapi_contract: PASS (11.2s)
  metrics: {"pass_marker_found": true}
- metrics_catalog: PASS (0.15s)
  metrics: {"pass_marker_found": true}
- migration_roundtrip: PASS (5.79s)
  metrics: {"head_count": 1, "head": "20260315_000002"}
- pytest_contract: PASS (33.73s)
  metrics: {"passed": 33, "failed": 0, "skipped": 0}
- pytest_security_consistency: PASS (44.79s)
  metrics: {"passed": 48, "failed": 0, "skipped": 0}
- pytest_integration_smoke: PASS (30.13s)
  metrics: {"passed": 5, "failed": 0, "skipped": 0}

## Raw Outputs
### auth_guard
```text
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\main.py: OK -> dependencies=[Depends(enforce_default_auth)]
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\system_config.py: OK -> dependencies=[Depends(require_admin)]
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\system_config.py: OK -> _reject_legacy_write_endpoint("/api/system/db/config")
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\system_config.py: OK -> _reject_legacy_write_endpoint("/api/system/sync/trigger")
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\medical_records.py: OK -> dependencies=[Depends(require_roles(
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\drg.py: OK -> dependencies=[Depends(require_roles(
D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\settlement.py: OK -> dependencies=[Depends(require_roles(
Auth guard checks passed.
```
### secret_hygiene
```text
Secret hygiene check passed.
```
### alert_rules
```text
[alert-rules] PASS file=D:\LLM\lx0222\health-qc-monorepo\scripts\medqc_prometheus_alert_rules.yml alerts=6
```
### openapi_contract
```text
Database initialized: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\data\demo_feedbacks.db
  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
[openapi] POST /api/v1/auth/login: OK
[openapi] POST /api/v1/auth/refresh: OK
[openapi] POST /api/v1/sync/trigger: OK
[openapi] GET /api/v1/sync/config/pg: OK
[openapi] PUT /api/v1/sync/config/pg: OK
[openapi] refresh contract: OK (application/json=True, refresh_token_field=True)
[openapi] sync trigger security: OK
[openapi] PASS {"paths": 255, "schemas": 105}
2026-03-26 14:54:00 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:54:00 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:54:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:01 - app.access - INFO - [77fbb05b-7e29-4ac5-94ad-1b4802494a14] - Request started
2026-03-26 14:54:02 - app.access - INFO - [77fbb05b-7e29-4ac5-94ad-1b4802494a14] - Request completed
2026-03-26 14:54:02 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
```
### metrics_catalog
```text
[metrics-catalog] PASS file=D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\system.py required=9 labels=code_class,env
```
### migration_roundtrip
```text
Alembic head: 20260315_000002
Upgrade SQL generation passed.
Downgrade SQL generation passed.
Migration roundtrip check passed.
```
### pytest_contract
```text
Database initialized: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\data\demo_feedbacks.db
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-7.4.3, pluggy-1.6.0
rootdir: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend
configfile: pytest.ini
plugins: anyio-3.7.1, devtools-0.12.2, asyncio-0.21.1, mock-3.12.0, timeout-2.4.0
asyncio: mode=strict
collected 33 items

tests\unit\test_auth_sync_contract.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.
tests\unit\test_openapi_contract.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.
tests\unit\test_sync_router.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.
tests\unit\test_observability_contract.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.

============================== warnings summary ===============================
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
  C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.5/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

app\models\demo.py:10
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\models\demo.py:10: MovedIn20Warning: The ``declarative_base()`` function is now available as sqlalchemy.orm.declarative_base(). (deprecated since: 2.0) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    Base = declarative_base()

app\main.py:308
tests/unit/test_auth_sync_contract.py::test_refresh_contract_accepts_json_and_returns_stable_shape
tests/unit/test_observability_contract.py::test_otel_enabled_with_unreachable_exporter_does_not_block_startup
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\main.py:308: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

C:\Python310\lib\site-packages\fastapi\applications.py:4547
tests/unit/test_auth_sync_contract.py::test_refresh_contract_accepts_json_and_returns_stable_shape
tests/unit/test_observability_contract.py::test_otel_enabled_with_unreachable_exporter_does_not_block_startup
  C:\Python310\lib\site-packages\fastapi\applications.py:4547: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
====================== 33 passed, 13 warnings in 13.76s =======================
2026-03-26 14:54:24 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:54:24 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:54:26 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:54:26 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:54:27 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:27 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:27 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:27 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:28 - app.access - INFO - [7998757c-dc0f-4c3c-b7b9-6c9240149447] - Request started
2026-03-26 14:54:28 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:54:28 - app.access - INFO - [7998757c-dc0f-4c3c-b7b9-6c9240149447] - Request completed
2026-03-26 14:54:28 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:54:28 - app.access - INFO - [b84309d0-54ce-4332-a08b-256abd01a59b] - Request started
2026-03-26 14:54:28 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 14:54:28 - app.access - INFO - [b84309d0-54ce-4332-a08b-256abd01a59b] - Request completed
2026-03-26 14:54:28 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 14:54:28 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:28 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:28 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:28 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:28 - app.access - INFO - [54908b65-7506-457e-9082-3c7e44c7fc4c] - Request started
2026-03-26 14:54:29 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:54:29 - app.access - INFO - [54908b65-7506-457e-9082-3c7e44c7fc4c] - Request completed
2026-03-26 14:54:29 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:54:29 - app.access - INFO - [a0553b4e-d343-4c81-88e0-2b0e59f905e0] - Request started
2026-03-26 14:54:29 - app.access - INFO - [a0553b4e-d343-4c81-88e0-2b0e59f905e0] - Request completed
2026-03-26 14:54:29 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 14:54:29 - app.access - INFO - [3bd3bc23-b511-4bac-9223-dc3e39dce7c3] - Request started
2026-03-26 14:54:29 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.pg.update resource=/api/v1/sync/config/pg outcome=success actor=admin@medqc.com roles=admin,qc_manager trace_id=3bd3bc23-b511-4bac-9223-dc3e39dce7c3 details={"changed_fields": ["remote_host", "remote_password", "remote_password_ref", "remote_port"], "connection_ok": true, "remote_host": "10.8.8.8", "remote_port": "5544"}
2026-03-26 14:54:29 - app.access - INFO - [3bd3bc23-b511-4bac-9223-dc3e39dce7c3] - Request completed
2026-03-26 14:54:29 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 14:54:29 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:29 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:29 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:29 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:29 - app.access - INFO - [70dc3eaf-2f36-42cf-a2fa-97ac0875f293] - Request started
2026-03-26 14:54:30 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 14:54:30 - app.access - INFO - [70dc3eaf-2f36-42cf-a2fa-97ac0875f293] - Request completed
2026-03-26 14:54:30 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:54:30 - app.access - INFO - [fc72587b-c8b7-4224-b594-ebe341d8f7fb] - Request started
2026-03-26 14:54:30 - app.main - WARNING - [fc72587b-c8b7-4224-b594-ebe341d8f7fb] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 14:54:30 - app.access - WARNING - [fc72587b-c8b7-4224-b594-ebe341d8f7fb] - Request completed
2026-03-26 14:54:30 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 14:54:30 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:30 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:30 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:30 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:30 - app.access - INFO - [33c06a05-78f4-4ebd-89dd-1f262ca0cef1] - Request started
2026-03-26 14:54:31 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:54:31 - app.access - INFO - [33c06a05-78f4-4ebd-89dd-1f262ca0cef1] - Request completed
2026-03-26 14:54:31 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:54:31 - app.access - INFO - [51c27251-c7a8-476d-a92e-ff1312742ecc] - Request started
2026-03-26 14:54:31 - app.routers.qc_sichuan - INFO - [no-trace-id] - Loaded 179 Sichuan rules from JSON file
2026-03-26 14:54:31 - app.access - INFO - [51c27251-c7a8-476d-a92e-ff1312742ecc] - Request completed
2026-03-26 14:54:31 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/rules "HTTP/1.1 200 OK"
2026-03-26 14:54:31 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:31 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:31 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:31 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:31 - app.access - INFO - [c4474792-9026-400a-b413-f643bcc2e7ba] - Request started
2026-03-26 14:54:32 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:54:32 - app.access - INFO - [c4474792-9026-400a-b413-f643bcc2e7ba] - Request completed
2026-03-26 14:54:32 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:54:32 - app.access - INFO - [83fb59c4-9be4-46cf-8b73-975b12a3438f] - Request started
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251110_041209.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251109_233517.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_234838.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_070941.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065547.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065421.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_062819.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_053504.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_021345.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_015054.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_014934.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_013113.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_005230.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\fe17a51e-5db0-4d37-ab6d-ac41cecca752_sequential_batch_20251112_130619.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f41ab06d-0f77-4f0f-ad27-e9c08fea5756_sequential_batch_20251112_143049.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f158d3cf-7fa9-4059-82e6-01e478d60399_sequential_batch_20251112_142617.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\e6cd1e70-88ac-4df9-a164-1326d35a6874_sequential_batch_20251110_064046.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\daf44f72-0baa-453b-bf32-b9355bd3bd01_sequential_batch_20251112_011112.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\defbcbd9-94e9-4723-b6df-dbf0b21ea4f7_sequential_batch_20251112_233633.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\c79d0012-c564-4d1c-bd4c-cf5aebe1fd92_sequential_batch_20251112_132237.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_083256.json: 'list' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a9c69ec9-9675-40ed-b203-5d830842a11c_sequential_batch_20251112_013953.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_082322.json: 'list' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a2bbfbe5-48de-4da8-bb47-e0cc59424775_sequential_batch_20251112_233854.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\9d5ec2a7-dc69-40dc-86ac-2c1e52f9aafd_sequential_batch_20251112_031338.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\89bb0a9d-14b9-48bc-8f67-f04f89fbb9c5_sequential_batch_20251112_031203.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\81d4a41f-bd3d-457d-aea6-1c32a412312e_sequential_batch_20251111_120900.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\818fe627-f5ad-4101-b06d-8a2addf10a71_sequential_batch_20251111_134659.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6fd14104-4d02-4b52-bc3d-a012cf4ede90_sequential_batch_20251112_232848.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6de19991-4266-4aa4-8bef-ee3001fb3ddc_sequential_batch_20251113_000427.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6154a09c-c692-4cfd-83a7-eb2773a9ad8b_sequential_batch_20251112_141218.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\5a2b1859-a0a8-436b-a4a0-af30eb6db6dc_sequential_batch_20251111_235912.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\57c72978-223b-4e01-b6ff-180e802c1718_sequential_batch_20251112_130944.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4eb1f192-80d8-48fa-8393-0c91b788d0d9_sequential_batch_20251111_235832.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4798fb59-6450-4f11-94c3-848d2702cf6c_sequential_batch_20251112_151503.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4596298c-eca7-4ca2-89ce-30ce5ae2898d_sequential_batch_20251111_012838.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\36f11425-d816-4f8a-b624-dced1ac4c164_sequential_batch_20251112_060145.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\2c59b9ef-9b2f-4ef8-b671-d0840df86da8_sequential_batch_20251112_231936.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1e2886a3-253f-4008-b4c7-da32548e5826_sequential_batch_20251111_121107.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1ca2602c-56e6-4310-b686-19a73531a8a9_sequential_batch_20251112_232958.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\13c4efdd-6bff-4ff7-aa51-2bc906aad435_sequential_batch_20251112_232048.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:54:32 - app.access - INFO - [83fb59c4-9be4-46cf-8b73-975b12a3438f] - Request completed
2026-03-26 14:54:32 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/results/history?page=1&page_size=10 "HTTP/1.1 200 OK"
2026-03-26 14:54:32 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:32 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:32 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:32 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:32 - app.access - INFO - [cb310ac6-69d6-4e05-b8e6-59ed7bf2a5c8] - Request started
2026-03-26 14:54:33 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:54:33 - app.access - INFO - [cb310ac6-69d6-4e05-b8e6-59ed7bf2a5c8] - Request completed
2026-03-26 14:54:33 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:54:33 - app.access - INFO - [248ac945-0912-4e15-964a-a88e028e8eeb] - Request started
2026-03-26 14:54:33 - app.access - INFO - [248ac945-0912-4e15-964a-a88e028e8eeb] - Request completed
2026-03-26 14:54:33 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 200 OK"
2026-03-26 14:54:33 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:33 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:33 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:33 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:33 - app.access - INFO - [7760dbab-9da5-4fad-a17b-fd601e645846] - Request started
2026-03-26 14:54:33 - app.access - INFO - [7760dbab-9da5-4fad-a17b-fd601e645846] - Request completed
2026-03-26 14:54:33 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
2026-03-26 14:54:33 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:33 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:33 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:33 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:33 - app.access - INFO - [e04ba0e7-3798-4719-a3f1-7f042e092ff6] - Request started
2026-03-26 14:54:33 - app.access - INFO - [e04ba0e7-3798-4719-a3f1-7f042e092ff6] - Request completed
2026-03-26 14:54:33 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
2026-03-26 14:54:33 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:33 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:34 - app.access - INFO - [f2f9a561-5cb0-4054-b4fd-dc0fbeb37bf8] - Request started
2026-03-26 14:54:34 - app.access - INFO - [f2f9a561-5cb0-4054-b4fd-dc0fbeb37bf8] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 14:54:34 - app.access - INFO - [c19819f9-1c9c-414a-8fcf-db07730b51cd] - Request started
2026-03-26 14:54:34 - app.access - INFO - [c19819f9-1c9c-414a-8fcf-db07730b51cd] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 14:54:34 - app.access - INFO - [a9512f78-0b99-4ed2-b298-ebcac0fb7f49] - Request started
2026-03-26 14:54:34 - app.main - WARNING - [a9512f78-0b99-4ed2-b298-ebcac0fb7f49] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 14:54:34 - app.access - WARNING - [a9512f78-0b99-4ed2-b298-ebcac0fb7f49] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 403 Forbidden"
2026-03-26 14:54:34 - app.access - INFO - [f839ed25-8692-4b29-aad7-005c56bdebbc] - Request started
2026-03-26 14:54:34 - app.main - WARNING - [f839ed25-8692-4b29-aad7-005c56bdebbc] - HTTP Exception: 401 - Authentication required
2026-03-26 14:54:34 - app.access - WARNING - [f839ed25-8692-4b29-aad7-005c56bdebbc] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 401 Unauthorized"
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:34 - app.access - INFO - [96eb56b6-e92c-4800-a01f-9736e6c012b2] - Request started
2026-03-26 14:54:34 - app.main - WARNING - [96eb56b6-e92c-4800-a01f-9736e6c012b2] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 14:54:34 - app.access - WARNING - [96eb56b6-e92c-4800-a01f-9736e6c012b2] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:34 - app.access - INFO - [2bc6824d-4744-4a3f-8a62-acf47a10df54] - Request started
2026-03-26 14:54:34 - app.main - WARNING - [2bc6824d-4744-4a3f-8a62-acf47a10df54] - Validation Error: [{'type': 'greater_than_equal', 'loc': ('body', 'lookback_minutes'), 'msg': 'Input should be greater than or equal to 0', 'input': -1, 'ctx': {'ge': 0}, 'url': 'https://errors.pydantic.dev/2.5/v/greater_than_equal'}]
2026-03-26 14:54:34 - app.access - WARNING - [2bc6824d-4744-4a3f-8a62-acf47a10df54] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:54:34 - app.access - INFO - [9940ca2d-4bee-44ff-a26f-3d394d946bf2] - Request started
2026-03-26 14:54:34 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.mongo.update resource=/api/v1/sync/config/mongo outcome=success actor=sync@test.local roles=admin trace_id=9940ca2d-4bee-44ff-a26f-3d394d946bf2 details={"changed_fields": ["connect_timeout_ms", "enabled", "inter_request_delay_ms", "lookback_minutes", "max_batch_size", "night_window_end", "night_window_start", "rescan_recent_days", "tier1_interval_minutes", "tier2_interval_minutes", "tier3_cron"], "enabled": true}
2026-03-26 14:54:34 - app.access - INFO - [9940ca2d-4bee-44ff-a26f-3d394d946bf2] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 200 OK"
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:34 - app.access - INFO - [dff331ec-7da4-43c7-afba-0e4eb92d54cd] - Request started
2026-03-26 14:54:34 - app.access - INFO - [dff331ec-7da4-43c7-afba-0e4eb92d54cd] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:34 - app.access - INFO - [d021622f-99dc-4d9a-ad84-418487e21cfe] - Request started
2026-03-26 14:54:34 - app.access - INFO - [d021622f-99dc-4d9a-ad84-418487e21cfe] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/test-connection/all "HTTP/1.1 200 OK"
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:34 - app.access - INFO - [0e2eb9e0-9556-4dcb-8c6d-3ad83ba258d8] - Request started
2026-03-26 14:54:34 - app.access - INFO - [0e2eb9e0-9556-4dcb-8c6d-3ad83ba258d8] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:34 - app.access - INFO - [76fdb17e-b073-4db2-bb73-b66c91d1c8b1] - Request started
2026-03-26 14:54:34 - app.access - INFO - [76fdb17e-b073-4db2-bb73-b66c91d1c8b1] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:34 - app.access - INFO - [e7d30edb-8dc5-432c-b021-9d762c89904a] - Request started
2026-03-26 14:54:34 - app.audit - INFO - [no-trace-id] - audit.event action=sync.trigger resource=/api/v1/sync/trigger outcome=rejected_running actor=sync@test.local roles=admin trace_id=e7d30edb-8dc5-432c-b021-9d762c89904a details={"idempotency_key": "mongo:all:2026-03-26:sync@test.local", "run_id": "syncrun-51ef98960d82", "source": "mongo", "sync_date": "2026-03-26", "tier": "all"}
2026-03-26 14:54:34 - app.access - INFO - [e7d30edb-8dc5-432c-b021-9d762c89904a] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:34 - app.access - INFO - [f5291357-698d-48f2-a82b-e56f98ceb1b9] - Request started
2026-03-26 14:54:34 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 14:54:34 - app.audit - INFO - [no-trace-id] - audit.event action=sync.trigger resource=/api/v1/sync/trigger outcome=success actor=sync@test.local roles=admin trace_id=f5291357-698d-48f2-a82b-e56f98ceb1b9 details={"idempotency_key": "mongo:tier1:2026-03-26:sync@test.local", "run_id": "syncrun-fa01bbcb322e", "source": "mongo", "status": "success", "sync_date": "2026-03-26", "tier": "tier1", "total_records": 2}
2026-03-26 14:54:34 - app.access - INFO - [f5291357-698d-48f2-a82b-e56f98ceb1b9] - Request completed
2026-03-26 14:54:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:54:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:35 - app.access - INFO - [e5074118-5356-4528-8819-23079e6da8c6] - Request started
2026-03-26 14:54:35 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 14:54:35 - app.access - INFO - [e5074118-5356-4528-8819-23079e6da8c6] - Request completed
2026-03-26 14:54:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:54:35 - app.access - INFO - [3f343f23-4de8-45e3-bc44-4a9a787f430d] - Request started
2026-03-26 14:54:35 - app.access - INFO - [3f343f23-4de8-45e3-bc44-4a9a787f430d] - Request completed
2026-03-26 14:54:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:35 - app.access - INFO - [3674225b-b05e-48d9-9d82-f4f238685c8e] - Request started
2026-03-26 14:54:35 - app.access - INFO - [3674225b-b05e-48d9-9d82-f4f238685c8e] - Request completed
2026-03-26 14:54:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/runs?source=mongo&tier=tier2&limit=20 "HTTP/1.1 200 OK"
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:35 - app.access - INFO - [1cc2092a-7452-4123-a323-d77f00443db2] - Request started
2026-03-26 14:54:35 - app.access - INFO - [1cc2092a-7452-4123-a323-d77f00443db2] - Request completed
2026-03-26 14:54:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 200 OK"
2026-03-26 14:54:35 - app.access - INFO - [a8754322-e17d-4155-9a0e-09036ce422b8] - Request started
2026-03-26 14:54:35 - app.main - WARNING - [a8754322-e17d-4155-9a0e-09036ce422b8] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 14:54:35 - app.access - WARNING - [a8754322-e17d-4155-9a0e-09036ce422b8] - Request completed
2026-03-26 14:54:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 403 Forbidden"
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:35 - app.access - INFO - [37b861ec-561b-4dfe-af21-ffe5866e6fe6] - Request started
2026-03-26 14:54:35 - app.audit - INFO - [no-trace-id] - audit.event action=sync.template.apply resource=/api/v1/sync/templates/apply outcome=success actor=sync@test.local roles=admin trace_id=37b861ec-561b-4dfe-af21-ffe5866e6fe6 details={"departments_count": 1, "enabled": false, "template_id": "single_department_focus"}
2026-03-26 14:54:35 - app.access - INFO - [37b861ec-561b-4dfe-af21-ffe5866e6fe6] - Request completed
2026-03-26 14:54:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 200 OK"
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:35 - app.access - INFO - [3d272b7a-1ad9-492e-9de6-996f3eab5544] - Request started
2026-03-26 14:54:35 - app.main - WARNING - [3d272b7a-1ad9-492e-9de6-996f3eab5544] - HTTP Exception: 422 - 该模板必须选择科室
2026-03-26 14:54:35 - app.access - WARNING - [3d272b7a-1ad9-492e-9de6-996f3eab5544] - Request completed
2026-03-26 14:54:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:54:35 - app.access - INFO - [b2d6554f-9e0f-4009-8292-f391d593676a] - Request started
2026-03-26 14:54:35 - app.main - WARNING - [b2d6554f-9e0f-4009-8292-f391d593676a] - HTTP Exception: 422 - 科室列表不允许同时包含 * 和具体科室
2026-03-26 14:54:35 - app.access - WARNING - [b2d6554f-9e0f-4009-8292-f391d593676a] - Request completed
2026-03-26 14:54:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:35 - app.access - INFO - [a8a4c310-fcce-4110-b65e-ad2f6713eea1] - Request started
2026-03-26 14:54:35 - app.access - INFO - [a8a4c310-fcce-4110-b65e-ad2f6713eea1] - Request completed
2026-03-26 14:54:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 200 OK"
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:35 - app.access - INFO - [df4f600d-5e58-4214-9384-e9cb7015fb78] - Request started
2026-03-26 14:54:35 - app.main - WARNING - [df4f600d-5e58-4214-9384-e9cb7015fb78] - HTTP Exception: 422 - mongo_uri 未配置
2026-03-26 14:54:35 - app.access - WARNING - [df4f600d-5e58-4214-9384-e9cb7015fb78] - Request completed
2026-03-26 14:54:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:36 - app.access - INFO - [66a69a6e-5f2c-47d8-b2f4-75fcd6784682] - Request started
2026-03-26 14:54:36 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 14:54:36 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 14:54:36 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:54:36 - app.access - INFO - [66a69a6e-5f2c-47d8-b2f4-75fcd6784682] - Request completed
2026-03-26 14:54:36 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:36 - app.access - INFO - [4820d231-d1b8-4af1-bc3b-b1120a0e42a0] - Request started
2026-03-26 14:54:36 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:54:36 - app.access - INFO - [4820d231-d1b8-4af1-bc3b-b1120a0e42a0] - Request completed
2026-03-26 14:54:36 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics/prometheus "HTTP/1.1 200 OK"
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:36 - app.access - INFO - [trace-client-123] - Request started
2026-03-26 14:54:36 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:54:36 - app.access - INFO - [trace-client-123] - Request completed
2026-03-26 14:54:36 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:36 - app.access - INFO - [req-client-456] - Request started
2026-03-26 14:54:36 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:54:36 - app.access - INFO - [req-client-456] - Request completed
2026-03-26 14:54:36 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:36 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request started
2026-03-26 14:54:36 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:54:36 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request completed
2026-03-26 14:54:36 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:36 - app.access - INFO - [6bb29f18-b574-4f27-9504-ed154cf19896] - Request started
2026-03-26 14:54:36 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:54:36 - app.access - INFO - [6bb29f18-b574-4f27-9504-ed154cf19896] - Request completed
2026-03-26 14:54:36 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:36 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:36 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:36 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request started
2026-03-26 14:54:36 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:54:37 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request completed
2026-03-26 14:54:37 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:54:37 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:37 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:37 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:37 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:37 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:54:37 - app.core.otel - WARNING - [no-trace-id] - OpenTelemetry dependencies unavailable, skip instrumentation: No module named 'opentelemetry'
2026-03-26 14:54:39 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:54:39 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:54:39 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:54:39 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:54:39 - app.access - INFO - [e7039918-11c0-4c5d-abab-14cafc71824b] - Request started
2026-03-26 14:54:39 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:54:39 - app.access - ERROR - [e7039918-11c0-4c5d-abab-14cafc71824b] - Request failed: boom
Traceback (most recent call last):
  File "C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\anyio\streams\memory.py", line 98, in receive
  File "C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\anyio\streams\memory.py", line 93, in receive_nowait
anyio.WouldBlock

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "C:\Python310\lib\site-packages\starlette\middleware\base.py", line 78, in call_next
    message = await recv_stream.receive()
  File "C:\Users\Coldplay\AppData\Local\Programs\Python\Python310\lib\site-packages\anyio\streams\memory.py", line 118, in receive
anyio.EndOfStream

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\core\logging.py", line 170, in request_logger_middleware
    response = await call_next(request)
  File "C:\Python310\lib\site-packages\starlette\middleware\base.py", line 84, in call_next
    raise app_exc
  File "C:\Python310\lib\site-packages\starlette\middleware\base.py", line 70, in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
  File "C:\Python310\lib\site-packages\starlette\middleware\base.py", line 108, in __call__
    response = await self.dispatch_func(request, call_next)
  File "D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\core\middleware_api_version.py", line 83, in dispatch
    response = await call_next(request)
  File "C:\Python310\lib\site-packages\starlette\middleware\base.py", line 84, in call_next
    raise app_exc
  File "C:\Python310\lib\site-packages\starlette\middleware\base.py", line 70, in coro
    await self.app(scope, receive_or_disconnect, send_no_error)
  File "C:\Python310\lib\site-packages\starlette\middleware\cors.py", line 83, in __call__
    await self.app(scope, receive, send)
  File "C:\Python310\lib\site-packages\starlette\middleware\exceptions.py", line 79, in __call__
    raise exc
  File "C:\Python310\lib\site-packages\starlette\middleware\exceptions.py", line 68, in __call__
    await self.app(scope, receive, sender)
  File "C:\Python310\lib\site-packages\fastapi\middleware\asyncexitstack.py", line 20, in __call__
    raise e
  File "C:\Python310\lib\site-packages\fastapi\middleware\asyncexitstack.py", line 17, in __call__
    await self.app(scope, receive, send)
  File "C:\Python310\lib\site-packages\starlette\routing.py", line 718, in __call__
    await route.handle(scope, receive, send)
  File "C:\Python310\lib\site-packages\starlette\routing.py", line 276, in handle
    await self.app(scope, receive, send)
  File "C:\Python310\lib\site-packages\starlette\routing.py", line 66, in app
    response = await func(request)
  File "C:\Python310\lib\site-packages\fastapi\routing.py", line 274, in app
    raw_response = await run_endpoint_function(
  File "C:\Python310\lib\site-packages\fastapi\routing.py", line 191, in run_endpoint_function
    return await dependant.call(**values)
  File "D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\routers\system.py", line 236, in metrics
    runtime_metrics = runtime_request_metrics.snapshot()
  File "D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\tests\unit\test_observability_contract.py", line 226, in _raise_metrics_error
    raise RuntimeError("boom")
RuntimeError: boom
2026-03-26 14:54:39 - app.core.middleware_errors - ERROR - [e7039918-11c0-4c5d-abab-14cafc71824b] - Internal Server Error: boom
2026-03-26 14:54:39 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 500 Internal Server Error"
```
### pytest_security_consistency
```text
Database initialized: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\data\demo_feedbacks.db
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-7.4.3, pluggy-1.6.0
rootdir: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend
configfile: pytest.ini
plugins: anyio-3.7.1, devtools-0.12.2, asyncio-0.21.1, mock-3.12.0, timeout-2.4.0
asyncio: mode=strict
collected 48 items

tests\unit\test_audit_logging.py .
tests\unit\test_security_hardening.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.
tests\unit\test_sync_consistency.py .......
tests\unit\test_sync_idempotency.py ..
tests\unit\test_system_api.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.
tests\unit\test_task_audit.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.
tests\unit\test_upload_rate_limit.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.
tests\unit\test_upload_security_controls.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.
tests\unit\test_production_guard.py ...

============================== warnings summary ===============================
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
  C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.5/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

app\models\demo.py:10
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\models\demo.py:10: MovedIn20Warning: The ``declarative_base()`` function is now available as sqlalchemy.orm.declarative_base(). (deprecated since: 2.0) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    Base = declarative_base()

app\main.py:308
tests/unit/test_security_hardening.py::test_high_risk_endpoints_require_auth
tests/unit/test_production_guard.py::test_startup_fails_fast_in_production_with_default_demo_users
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\main.py:308: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

C:\Python310\lib\site-packages\fastapi\applications.py:4547
tests/unit/test_security_hardening.py::test_high_risk_endpoints_require_auth
tests/unit/test_production_guard.py::test_startup_fails_fast_in_production_with_default_demo_users
  C:\Python310\lib\site-packages\fastapi\applications.py:4547: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
====================== 48 passed, 13 warnings in 23.05s =======================
2026-03-26 14:55:00 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:55:00 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:55:02 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.pg.update resource=/api/v1/sync/config/pg outcome=success actor=admin@medqc.com roles=admin trace_id=trace-unit-audit details={"nested": {"token": "***"}, "remote_host": "127.0.0.1", "remote_password": "***"}
2026-03-26 14:55:02 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:55:02 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:55:04 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:04 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:04 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:04 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:04 - app.access - INFO - [7dc378f7-7c1f-47ef-9cc0-a0cd8b3e19c0] - Request started
2026-03-26 14:55:04 - app.main - WARNING - [7dc378f7-7c1f-47ef-9cc0-a0cd8b3e19c0] - HTTP Exception: 401 - Authentication required
2026-03-26 14:55:04 - app.access - WARNING - [7dc378f7-7c1f-47ef-9cc0-a0cd8b3e19c0] - Request completed
2026-03-26 14:55:04 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 14:55:04 - app.access - INFO - [9fa4c995-c017-4174-adb9-abf73cc00c6d] - Request started
2026-03-26 14:55:04 - app.main - WARNING - [9fa4c995-c017-4174-adb9-abf73cc00c6d] - HTTP Exception: 401 - Authentication required
2026-03-26 14:55:04 - app.access - WARNING - [9fa4c995-c017-4174-adb9-abf73cc00c6d] - Request completed
2026-03-26 14:55:04 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/drg/config/current "HTTP/1.1 401 Unauthorized"
2026-03-26 14:55:04 - app.access - INFO - [1636d181-855e-4c64-91dc-8be8a0eab4f9] - Request started
2026-03-26 14:55:04 - app.main - WARNING - [1636d181-855e-4c64-91dc-8be8a0eab4f9] - HTTP Exception: 401 - Authentication required
2026-03-26 14:55:04 - app.access - WARNING - [1636d181-855e-4c64-91dc-8be8a0eab4f9] - Request completed
2026-03-26 14:55:04 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/settlement/list "HTTP/1.1 401 Unauthorized"
2026-03-26 14:55:04 - app.access - INFO - [9b1c0861-8503-4ba4-8de1-6d9ed09c9999] - Request started
2026-03-26 14:55:04 - app.main - WARNING - [9b1c0861-8503-4ba4-8de1-6d9ed09c9999] - HTTP Exception: 401 - Authentication required
2026-03-26 14:55:04 - app.access - WARNING - [9b1c0861-8503-4ba4-8de1-6d9ed09c9999] - Request completed
2026-03-26 14:55:04 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 401 Unauthorized"
2026-03-26 14:55:04 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:04 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:04 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:04 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:04 - app.access - INFO - [d885cdd0-d543-41e5-96f2-d4e8ec430dc8] - Request started
2026-03-26 14:55:05 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 14:55:05 - app.access - INFO - [d885cdd0-d543-41e5-96f2-d4e8ec430dc8] - Request completed
2026-03-26 14:55:05 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:05 - app.access - INFO - [7b9a0d03-e390-4e0b-a7dc-b3dcffc34147] - Request started
2026-03-26 14:55:05 - app.main - WARNING - [7b9a0d03-e390-4e0b-a7dc-b3dcffc34147] - HTTP Exception: 403 - 此操作需要系统管理员权限
2026-03-26 14:55:05 - app.access - WARNING - [7b9a0d03-e390-4e0b-a7dc-b3dcffc34147] - Request completed
2026-03-26 14:55:05 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 403 Forbidden"
2026-03-26 14:55:05 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:05 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:05 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:05 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:05 - app.access - INFO - [3bbecaa8-d5db-4bb8-9185-46c2e0938afe] - Request started
2026-03-26 14:55:06 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:06 - app.access - INFO - [3bbecaa8-d5db-4bb8-9185-46c2e0938afe] - Request completed
2026-03-26 14:55:06 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:06 - app.access - INFO - [70ddd2c8-c4dd-4540-a673-4229476c31c1] - Request started
2026-03-26 14:55:06 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 14:55:06 - app.access - INFO - [70ddd2c8-c4dd-4540-a673-4229476c31c1] - Request completed
2026-03-26 14:55:06 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 14:55:06 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:06 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:06 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:06 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:06 - app.access - INFO - [cf118337-9d7a-41dd-9651-e2b8b0d1d3e6] - Request started
2026-03-26 14:55:07 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=reset-3cfe08f9@medqc.com roles=doctor trace_id=cf118337-9d7a-41dd-9651-e2b8b0d1d3e6 details={"assigned_roles": ["doctor"], "department": "测试科室", "target_email": "reset-3cfe08f9@medqc.com"}
2026-03-26 14:55:07 - app.access - INFO - [cf118337-9d7a-41dd-9651-e2b8b0d1d3e6] - Request completed
2026-03-26 14:55:07 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 14:55:07 - app.access - INFO - [0f25bf19-12e4-483c-8d54-a2bf93bc0eaf] - Request started
2026-03-26 14:55:07 - app.routers.auth - INFO - [no-trace-id] - auth.forgot_password.issued email=reset-3cfe08f9@medqc.com
2026-03-26 14:55:07 - app.access - INFO - [0f25bf19-12e4-483c-8d54-a2bf93bc0eaf] - Request completed
2026-03-26 14:55:07 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/forgot-password "HTTP/1.1 200 OK"
2026-03-26 14:55:07 - app.access - INFO - [33fdda3a-df36-425d-8de6-e4105facf096] - Request started
2026-03-26 14:55:07 - app.routers.auth - INFO - [no-trace-id] - auth.reset_password.success email=reset-3cfe08f9@medqc.com
2026-03-26 14:55:07 - app.access - INFO - [33fdda3a-df36-425d-8de6-e4105facf096] - Request completed
2026-03-26 14:55:07 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 200 OK"
2026-03-26 14:55:07 - app.access - INFO - [62f14d40-7dd6-4044-acb3-cd801f634df2] - Request started
2026-03-26 14:55:07 - app.main - WARNING - [62f14d40-7dd6-4044-acb3-cd801f634df2] - HTTP Exception: 401 - 重置令牌已使用或失效
2026-03-26 14:55:07 - app.access - WARNING - [62f14d40-7dd6-4044-acb3-cd801f634df2] - Request completed
2026-03-26 14:55:07 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 401 Unauthorized"
2026-03-26 14:55:07 - app.access - INFO - [7563cf70-f59a-4bcd-86e9-b97b084e6502] - Request started
2026-03-26 14:55:08 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=reset-3cfe08f9@medqc.com
2026-03-26 14:55:08 - app.access - INFO - [7563cf70-f59a-4bcd-86e9-b97b084e6502] - Request completed
2026-03-26 14:55:08 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:08 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:08 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:08 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:08 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:08 - app.access - INFO - [f65a8e8a-ba3b-4eb8-b4bf-79781029b810] - Request started
2026-03-26 14:55:09 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:09 - app.access - INFO - [f65a8e8a-ba3b-4eb8-b4bf-79781029b810] - Request completed
2026-03-26 14:55:09 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:09 - app.access - INFO - [695cec36-66ab-4159-a272-c4bae01beaec] - Request started
2026-03-26 14:55:09 - app.main - WARNING - [695cec36-66ab-4159-a272-c4bae01beaec] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/db/config. Please use /api/v1/sync/*
2026-03-26 14:55:09 - app.access - WARNING - [695cec36-66ab-4159-a272-c4bae01beaec] - Request completed
2026-03-26 14:55:09 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/system/db/config "HTTP/1.1 410 Gone"
2026-03-26 14:55:09 - app.access - INFO - [4eb32897-1161-4926-ae20-b7be7673f655] - Request started
2026-03-26 14:55:09 - app.main - WARNING - [4eb32897-1161-4926-ae20-b7be7673f655] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/sync/trigger. Please use /api/v1/sync/*
2026-03-26 14:55:09 - app.access - WARNING - [4eb32897-1161-4926-ae20-b7be7673f655] - Request completed
2026-03-26 14:55:09 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/system/sync/trigger "HTTP/1.1 410 Gone"
2026-03-26 14:55:09 - app.services.etl_sync - INFO - [no-trace-id] - 同步 病案首页 (web.mr)...
2026-03-26 14:55:09 - app.services.etl_sync - INFO - [no-trace-id] -   \u2705 病案首页: 1 条
2026-03-26 14:55:09 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:09 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:09 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:09 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:09 - app.access - INFO - [8551c808-8c33-4fd8-875e-1ca0e2cb2553] - Request started
2026-03-26 14:55:09 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 14:55:09 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 14:55:09 - app.access - INFO - [8551c808-8c33-4fd8-875e-1ca0e2cb2553] - Request completed
2026-03-26 14:55:09 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:09 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:09 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:10 - app.access - INFO - [3f933154-8d8c-44a7-b8dd-221da6aa2dc0] - Request started
2026-03-26 14:55:10 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:55:10 - app.access - INFO - [3f933154-8d8c-44a7-b8dd-221da6aa2dc0] - Request completed
2026-03-26 14:55:10 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:10 - app.access - INFO - [ed4cc0c7-6cf5-44b3-8835-df0a231c4bfc] - Request started
2026-03-26 14:55:10 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:55:10 - app.access - INFO - [ed4cc0c7-6cf5-44b3-8835-df0a231c4bfc] - Request completed
2026-03-26 14:55:10 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics/prometheus "HTTP/1.1 200 OK"
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:10 - app.access - INFO - [28b75f39-737a-4433-b4c1-37c69f39de20] - Request started
2026-03-26 14:55:10 - app.access - INFO - [28b75f39-737a-4433-b4c1-37c69f39de20] - Request completed
2026-03-26 14:55:10 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:10 - app.access - INFO - [9531d161-bb40-4f60-a40a-3827a4cfe46a] - Request started
2026-03-26 14:55:10 - app.access - WARNING - [9531d161-bb40-4f60-a40a-3827a4cfe46a] - Request completed
2026-03-26 14:55:10 - httpx - INFO - [no-trace-id] - HTTP Request: OPTIONS http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:10 - app.access - INFO - [cd7689f3-f377-4bee-93d5-95c8af4ebda4] - Request started
2026-03-26 14:55:10 - app.access - INFO - [cd7689f3-f377-4bee-93d5-95c8af4ebda4] - Request completed
2026-03-26 14:55:10 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:10 - app.access - INFO - [d5bf3b22-5f7e-47c7-bcaa-89f220360812] - Request started
2026-03-26 14:55:10 - app.access - INFO - [d5bf3b22-5f7e-47c7-bcaa-89f220360812] - Request completed
2026-03-26 14:55:10 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:10 - app.access - INFO - [cc6ce4ad-9648-4993-8e2a-d6dd5de06c84] - Request started
2026-03-26 14:55:10 - app.access - INFO - [cc6ce4ad-9648-4993-8e2a-d6dd5de06c84] - Request completed
2026-03-26 14:55:10 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:10 - app.access - INFO - [a4a5412d-d259-402c-8efb-bfe4a9cad052] - Request started
2026-03-26 14:55:10 - app.access - INFO - [a4a5412d-d259-402c-8efb-bfe4a9cad052] - Request completed
2026-03-26 14:55:10 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:11 - app.access - INFO - [455e1259-705c-477f-bed8-311183e8dde2] - Request started
2026-03-26 14:55:11 - app.access - INFO - [455e1259-705c-477f-bed8-311183e8dde2] - Request completed
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:11 - app.access - INFO - [9a589373-4def-4325-be77-66e4b873025d] - Request started
2026-03-26 14:55:11 - app.access - INFO - [9a589373-4def-4325-be77-66e4b873025d] - Request completed
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:11 - app.access - INFO - [c33ddd0c-c732-4ff8-9765-238d4531f191] - Request started
2026-03-26 14:55:11 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:55:11 - app.access - INFO - [c33ddd0c-c732-4ff8-9765-238d4531f191] - Request completed
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:11 - app.access - INFO - [1e479232-a60a-4659-bc50-9419422aa7e8] - Request started
2026-03-26 14:55:11 - app.access - WARNING - [1e479232-a60a-4659-bc50-9419422aa7e8] - Request completed
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/nonexistent "HTTP/1.1 404 Not Found"
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:11 - app.access - INFO - [a23072f1-e8f8-4b7e-a8c6-dd6fa85b9271] - Request started
2026-03-26 14:55:11 - app.access - WARNING - [a23072f1-e8f8-4b7e-a8c6-dd6fa85b9271] - Request completed
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:11 - app.access - INFO - [ce361f04-da9e-4b86-a161-97959e8b28ae] - Request started
2026-03-26 14:55:11 - app.access - INFO - [50860447-742f-489e-9c1b-84417d9c23e7] - Request started
2026-03-26 14:55:11 - app.access - INFO - [fc027afb-ba0d-48b1-9773-51f17f997b7f] - Request started
2026-03-26 14:55:11 - app.access - INFO - [a582f085-b473-4ebf-bd71-04a5a6eee9ab] - Request started
2026-03-26 14:55:11 - app.access - INFO - [5060d7d8-fdf5-441b-92f1-a2065ef1d2ca] - Request started
2026-03-26 14:55:11 - app.access - INFO - [c30db639-9d07-4ba3-9e34-d69208efd407] - Request started
2026-03-26 14:55:11 - app.access - INFO - [808290c1-1d21-4023-b13f-908e3297402f] - Request started
2026-03-26 14:55:11 - app.access - INFO - [db52af73-0d39-4d08-ad87-3dce12fea0fa] - Request started
2026-03-26 14:55:11 - app.access - INFO - [cbc8269a-f295-40fa-a10b-b62ff7fed3e6] - Request started
2026-03-26 14:55:11 - app.access - INFO - [c42ce408-3fba-4624-bac2-32baccc29312] - Request started
2026-03-26 14:55:11 - app.access - INFO - [ce361f04-da9e-4b86-a161-97959e8b28ae] - Request completed
2026-03-26 14:55:11 - app.access - INFO - [50860447-742f-489e-9c1b-84417d9c23e7] - Request completed
2026-03-26 14:55:11 - app.access - INFO - [fc027afb-ba0d-48b1-9773-51f17f997b7f] - Request completed
2026-03-26 14:55:11 - app.access - INFO - [a582f085-b473-4ebf-bd71-04a5a6eee9ab] - Request completed
2026-03-26 14:55:11 - app.access - INFO - [5060d7d8-fdf5-441b-92f1-a2065ef1d2ca] - Request completed
2026-03-26 14:55:11 - app.access - INFO - [c30db639-9d07-4ba3-9e34-d69208efd407] - Request completed
2026-03-26 14:55:11 - app.access - INFO - [808290c1-1d21-4023-b13f-908e3297402f] - Request completed
2026-03-26 14:55:11 - app.access - INFO - [db52af73-0d39-4d08-ad87-3dce12fea0fa] - Request completed
2026-03-26 14:55:11 - app.access - INFO - [cbc8269a-f295-40fa-a10b-b62ff7fed3e6] - Request completed
2026-03-26 14:55:11 - app.access - INFO - [c42ce408-3fba-4624-bac2-32baccc29312] - Request completed
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:12 - app.access - INFO - [830fa72c-aafc-40a1-92f3-0c9beeb42e8a] - Request started
2026-03-26 14:55:12 - app.access - INFO - [830fa72c-aafc-40a1-92f3-0c9beeb42e8a] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:12 - app.access - INFO - [e5886cca-5a98-45ee-90f5-5df7acd95b64] - Request started
2026-03-26 14:55:12 - app.access - INFO - [e5886cca-5a98-45ee-90f5-5df7acd95b64] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:12 - app.access - INFO - [f55da8ba-3c1a-4cca-9911-3c298e97ffe2] - Request started
2026-03-26 14:55:12 - app.access - INFO - [f55da8ba-3c1a-4cca-9911-3c298e97ffe2] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:12 - app.access - INFO - [0b1470dc-aad4-4b50-9e52-0c022033dc9f] - Request started
2026-03-26 14:55:12 - app.access - INFO - [0b1470dc-aad4-4b50-9e52-0c022033dc9f] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health?test=1&test=2 "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:12 - app.access - INFO - [2b807e32-3468-4a03-8556-5cd405592ca9] - Request started
2026-03-26 14:55:12 - app.access - INFO - [2b807e32-3468-4a03-8556-5cd405592ca9] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.access - INFO - [05be1a96-10f6-4b3e-9bcc-ce651a820007] - Request started
2026-03-26 14:55:12 - app.access - INFO - [05be1a96-10f6-4b3e-9bcc-ce651a820007] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.access - INFO - [d6a5d1b2-837f-4f6c-b657-883729ecccb7] - Request started
2026-03-26 14:55:12 - app.access - INFO - [d6a5d1b2-837f-4f6c-b657-883729ecccb7] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.access - INFO - [229053ac-006f-4841-b2bb-babced772ebc] - Request started
2026-03-26 14:55:12 - app.access - INFO - [229053ac-006f-4841-b2bb-babced772ebc] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.access - INFO - [3a2cb6c8-acce-4b17-846c-1eb5cd32520e] - Request started
2026-03-26 14:55:12 - app.access - INFO - [3a2cb6c8-acce-4b17-846c-1eb5cd32520e] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.access - INFO - [43b17f9c-1a94-415c-a928-e051f4337f97] - Request started
2026-03-26 14:55:12 - app.access - INFO - [43b17f9c-1a94-415c-a928-e051f4337f97] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.access - INFO - [707434a5-1f60-45c1-885b-18aa977de5df] - Request started
2026-03-26 14:55:12 - app.access - INFO - [707434a5-1f60-45c1-885b-18aa977de5df] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.access - INFO - [fb5da578-dc45-4973-9641-bf39cd80a5cd] - Request started
2026-03-26 14:55:12 - app.access - INFO - [fb5da578-dc45-4973-9641-bf39cd80a5cd] - Request completed
2026-03-26 14:55:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:12 - app.access - INFO - [79e53030-1f01-4998-811c-57147ac1dca7] - Request started
2026-03-26 14:55:12 - app.access - INFO - [79e53030-1f01-4998-811c-57147ac1dca7] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [19a9646c-0444-4fec-bfae-ab176c0d7371] - Request started
2026-03-26 14:55:13 - app.access - INFO - [19a9646c-0444-4fec-bfae-ab176c0d7371] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [c0f9b3f6-cebc-4375-8161-515d5338b6ff] - Request started
2026-03-26 14:55:13 - app.access - INFO - [c0f9b3f6-cebc-4375-8161-515d5338b6ff] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [c60f7538-4da3-45cf-ad35-9e9efbab3176] - Request started
2026-03-26 14:55:13 - app.access - INFO - [c60f7538-4da3-45cf-ad35-9e9efbab3176] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [9f05c3f6-e07c-45bc-bef6-a7796d3ebd3d] - Request started
2026-03-26 14:55:13 - app.access - INFO - [9f05c3f6-e07c-45bc-bef6-a7796d3ebd3d] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [fa0667e6-f675-4fa7-aea4-3dbebc4760c4] - Request started
2026-03-26 14:55:13 - app.access - INFO - [fa0667e6-f675-4fa7-aea4-3dbebc4760c4] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [40def598-0597-443e-ab56-bfa423357ee0] - Request started
2026-03-26 14:55:13 - app.access - INFO - [40def598-0597-443e-ab56-bfa423357ee0] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [e487434b-7b2e-46e0-811c-83eacfb08019] - Request started
2026-03-26 14:55:13 - app.access - INFO - [e487434b-7b2e-46e0-811c-83eacfb08019] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [42ffc4e6-e205-40f3-9264-a210eab79689] - Request started
2026-03-26 14:55:13 - app.access - INFO - [42ffc4e6-e205-40f3-9264-a210eab79689] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [7e431367-5f46-41d0-8784-3c73d04ea924] - Request started
2026-03-26 14:55:13 - app.access - INFO - [7e431367-5f46-41d0-8784-3c73d04ea924] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [8d39ee33-5564-4c8c-b023-05e2ecb596f8] - Request started
2026-03-26 14:55:13 - app.access - INFO - [8d39ee33-5564-4c8c-b023-05e2ecb596f8] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [c214c652-9889-4b54-955a-820e2c6b0a7f] - Request started
2026-03-26 14:55:13 - app.access - INFO - [c214c652-9889-4b54-955a-820e2c6b0a7f] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [a066e2cf-d514-4c11-9b62-fac36ca33aeb] - Request started
2026-03-26 14:55:13 - app.access - INFO - [a066e2cf-d514-4c11-9b62-fac36ca33aeb] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [3c793429-5655-441c-bb45-db4d7cf125cc] - Request started
2026-03-26 14:55:13 - app.access - INFO - [3c793429-5655-441c-bb45-db4d7cf125cc] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [8b69263d-c0f9-4ca0-baa5-22b6ff5a2830] - Request started
2026-03-26 14:55:13 - app.access - INFO - [8b69263d-c0f9-4ca0-baa5-22b6ff5a2830] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [a8d86fc1-8515-4210-b164-1cdd59319a6e] - Request started
2026-03-26 14:55:13 - app.access - INFO - [a8d86fc1-8515-4210-b164-1cdd59319a6e] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [e355e989-37d0-4cb0-8e82-8d7ddfb9bebc] - Request started
2026-03-26 14:55:13 - app.access - INFO - [e355e989-37d0-4cb0-8e82-8d7ddfb9bebc] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [d479091d-824d-4a08-914e-60aa8dd090bf] - Request started
2026-03-26 14:55:13 - app.access - INFO - [d479091d-824d-4a08-914e-60aa8dd090bf] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [349b10f2-d24d-46fa-ade0-86ec3998a49d] - Request started
2026-03-26 14:55:13 - app.access - INFO - [349b10f2-d24d-46fa-ade0-86ec3998a49d] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [0dd74450-fff4-4607-a6d4-4c75ac10f1e2] - Request started
2026-03-26 14:55:13 - app.access - INFO - [0dd74450-fff4-4607-a6d4-4c75ac10f1e2] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [b5d8ad68-9182-4613-8a2a-8f8b849c17d2] - Request started
2026-03-26 14:55:13 - app.access - INFO - [b5d8ad68-9182-4613-8a2a-8f8b849c17d2] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [6492bc51-84db-4e7a-97c4-6d9e78a43cb2] - Request started
2026-03-26 14:55:13 - app.access - INFO - [6492bc51-84db-4e7a-97c4-6d9e78a43cb2] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [57d30eb5-18ab-4884-89b0-d5929a15a3bb] - Request started
2026-03-26 14:55:13 - app.access - INFO - [57d30eb5-18ab-4884-89b0-d5929a15a3bb] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [78517d0f-f80f-4fb9-82c9-499cb5189544] - Request started
2026-03-26 14:55:13 - app.access - INFO - [78517d0f-f80f-4fb9-82c9-499cb5189544] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [536b82f9-cb2a-4d3c-82a1-cfde3ffb188f] - Request started
2026-03-26 14:55:13 - app.access - INFO - [536b82f9-cb2a-4d3c-82a1-cfde3ffb188f] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [4171667f-63a0-42c1-8c2f-d2ea34239459] - Request started
2026-03-26 14:55:13 - app.access - INFO - [4171667f-63a0-42c1-8c2f-d2ea34239459] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [acabd86d-af96-4a8d-94e6-0f69c1da3eac] - Request started
2026-03-26 14:55:13 - app.access - INFO - [acabd86d-af96-4a8d-94e6-0f69c1da3eac] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [2c8cdfc7-99af-4366-bdfb-4c3216179e29] - Request started
2026-03-26 14:55:13 - app.access - INFO - [2c8cdfc7-99af-4366-bdfb-4c3216179e29] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [69796581-1e62-4c1f-a140-0eec310445e8] - Request started
2026-03-26 14:55:13 - app.access - INFO - [69796581-1e62-4c1f-a140-0eec310445e8] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [a455ec25-f314-4245-9baa-d7f5a1f93cef] - Request started
2026-03-26 14:55:13 - app.access - INFO - [a455ec25-f314-4245-9baa-d7f5a1f93cef] - Request completed
2026-03-26 14:55:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:13 - app.access - INFO - [9b160e98-6df2-4ca2-85ef-8f070eccc754] - Request started
2026-03-26 14:55:14 - app.access - INFO - [9b160e98-6df2-4ca2-85ef-8f070eccc754] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [423f2d5f-fbdd-44ef-a4d2-70e81b6408e6] - Request started
2026-03-26 14:55:14 - app.access - INFO - [423f2d5f-fbdd-44ef-a4d2-70e81b6408e6] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [fefc5db1-b9de-40b7-8cad-e06fa1d885a4] - Request started
2026-03-26 14:55:14 - app.access - INFO - [fefc5db1-b9de-40b7-8cad-e06fa1d885a4] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [3ccbf5cc-3854-4805-a603-95f3d5b79582] - Request started
2026-03-26 14:55:14 - app.access - INFO - [3ccbf5cc-3854-4805-a603-95f3d5b79582] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [6f7700cd-ec15-4780-b44b-af60685777f2] - Request started
2026-03-26 14:55:14 - app.access - INFO - [6f7700cd-ec15-4780-b44b-af60685777f2] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [f6a9155d-530d-4ab1-9ef8-34e700b01b51] - Request started
2026-03-26 14:55:14 - app.access - INFO - [f6a9155d-530d-4ab1-9ef8-34e700b01b51] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [86025866-d8a9-455d-a9ff-413db01adabb] - Request started
2026-03-26 14:55:14 - app.access - INFO - [86025866-d8a9-455d-a9ff-413db01adabb] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [236d0cad-4cb2-40af-b2f6-16b51af3a175] - Request started
2026-03-26 14:55:14 - app.access - INFO - [236d0cad-4cb2-40af-b2f6-16b51af3a175] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [28b78f18-d478-4835-a574-439544740675] - Request started
2026-03-26 14:55:14 - app.access - INFO - [28b78f18-d478-4835-a574-439544740675] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [c495fc09-1838-41f3-b34e-38adfb04de70] - Request started
2026-03-26 14:55:14 - app.access - INFO - [c495fc09-1838-41f3-b34e-38adfb04de70] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [ef2d2ad2-9427-4e2e-bbd6-d4d0e231d00e] - Request started
2026-03-26 14:55:14 - app.access - INFO - [ef2d2ad2-9427-4e2e-bbd6-d4d0e231d00e] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [cd15730a-f873-46e3-8b5e-1fa7271e5f89] - Request started
2026-03-26 14:55:14 - app.access - INFO - [cd15730a-f873-46e3-8b5e-1fa7271e5f89] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [9da90a35-01ad-421c-883f-d258e6990c53] - Request started
2026-03-26 14:55:14 - app.access - INFO - [9da90a35-01ad-421c-883f-d258e6990c53] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [6383e0ea-df9e-4d8c-a964-a85ba63008c7] - Request started
2026-03-26 14:55:14 - app.access - INFO - [6383e0ea-df9e-4d8c-a964-a85ba63008c7] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [3f7ac51b-3247-4930-943e-08f418dca225] - Request started
2026-03-26 14:55:14 - app.access - INFO - [3f7ac51b-3247-4930-943e-08f418dca225] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [a3c2481c-7e37-44cc-9432-5802ef1b02c2] - Request started
2026-03-26 14:55:14 - app.access - INFO - [a3c2481c-7e37-44cc-9432-5802ef1b02c2] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [322d8f31-9694-4148-bd2f-2fb4158b209c] - Request started
2026-03-26 14:55:14 - app.access - INFO - [322d8f31-9694-4148-bd2f-2fb4158b209c] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [40d8ad5c-b153-4574-98a2-1eb786b827b5] - Request started
2026-03-26 14:55:14 - app.access - INFO - [40d8ad5c-b153-4574-98a2-1eb786b827b5] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [60b0f611-fafe-4dc5-9354-a2347838e0ca] - Request started
2026-03-26 14:55:14 - app.access - INFO - [60b0f611-fafe-4dc5-9354-a2347838e0ca] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [f182228d-2d78-404b-9b4d-28e729576a35] - Request started
2026-03-26 14:55:14 - app.access - INFO - [f182228d-2d78-404b-9b4d-28e729576a35] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [ac822d50-86fa-4b04-818c-17c0c1ef07a9] - Request started
2026-03-26 14:55:14 - app.access - INFO - [ac822d50-86fa-4b04-818c-17c0c1ef07a9] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [f05f7d02-634f-4ba7-a78b-7e27cd41e6e9] - Request started
2026-03-26 14:55:14 - app.access - INFO - [f05f7d02-634f-4ba7-a78b-7e27cd41e6e9] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [017c7c59-a322-44aa-ac6f-11529001297a] - Request started
2026-03-26 14:55:14 - app.access - INFO - [017c7c59-a322-44aa-ac6f-11529001297a] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [7745d46e-7bda-4337-a817-85d4ddec0d54] - Request started
2026-03-26 14:55:14 - app.access - INFO - [7745d46e-7bda-4337-a817-85d4ddec0d54] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [3f810a1b-4dfd-4995-8f80-212f6d4898cf] - Request started
2026-03-26 14:55:14 - app.access - INFO - [3f810a1b-4dfd-4995-8f80-212f6d4898cf] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [357410a4-9b90-4e65-bf10-d6aa5ba7bed0] - Request started
2026-03-26 14:55:14 - app.access - INFO - [357410a4-9b90-4e65-bf10-d6aa5ba7bed0] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [c67ce6f2-41b6-4214-b1b4-aeb702345f70] - Request started
2026-03-26 14:55:14 - app.access - INFO - [c67ce6f2-41b6-4214-b1b4-aeb702345f70] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [0dd03e65-b1d5-4f0b-b8cc-8ac118d33a64] - Request started
2026-03-26 14:55:14 - app.access - INFO - [0dd03e65-b1d5-4f0b-b8cc-8ac118d33a64] - Request completed
2026-03-26 14:55:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:14 - app.access - INFO - [0dd895b1-aa2b-4e1c-b2b6-acdab5dbf9b7] - Request started
2026-03-26 14:55:15 - app.access - INFO - [0dd895b1-aa2b-4e1c-b2b6-acdab5dbf9b7] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [440b81d7-5c76-427a-8036-64defdd10e79] - Request started
2026-03-26 14:55:15 - app.access - INFO - [440b81d7-5c76-427a-8036-64defdd10e79] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [e53c0018-0bc4-4a88-86db-98939c7a16d6] - Request started
2026-03-26 14:55:15 - app.access - INFO - [e53c0018-0bc4-4a88-86db-98939c7a16d6] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [3e618b06-4d0e-4cf4-bd39-44903605afb3] - Request started
2026-03-26 14:55:15 - app.access - INFO - [3e618b06-4d0e-4cf4-bd39-44903605afb3] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [0e126cc7-f5b8-4c46-ad15-1c4f28e30672] - Request started
2026-03-26 14:55:15 - app.access - INFO - [0e126cc7-f5b8-4c46-ad15-1c4f28e30672] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [70a26cd4-9954-474f-8c17-37efbb445837] - Request started
2026-03-26 14:55:15 - app.access - INFO - [70a26cd4-9954-474f-8c17-37efbb445837] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [548e505e-6969-4074-9976-fec42c40bff5] - Request started
2026-03-26 14:55:15 - app.access - INFO - [548e505e-6969-4074-9976-fec42c40bff5] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [60a4c427-e44c-4c12-a8f0-1cda3c3092e9] - Request started
2026-03-26 14:55:15 - app.access - INFO - [60a4c427-e44c-4c12-a8f0-1cda3c3092e9] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [69f084f2-1642-47a2-a581-bb35fb67b6ab] - Request started
2026-03-26 14:55:15 - app.access - INFO - [69f084f2-1642-47a2-a581-bb35fb67b6ab] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [87496ca4-9458-4950-b5cd-11875642d832] - Request started
2026-03-26 14:55:15 - app.access - INFO - [87496ca4-9458-4950-b5cd-11875642d832] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [e636fc2a-c93c-450a-b63f-b39162b6e519] - Request started
2026-03-26 14:55:15 - app.access - INFO - [e636fc2a-c93c-450a-b63f-b39162b6e519] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [0bd2aacd-4855-474e-bb00-4968911701ad] - Request started
2026-03-26 14:55:15 - app.access - INFO - [0bd2aacd-4855-474e-bb00-4968911701ad] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [929c6110-2664-4da6-a960-06e3f962f0ec] - Request started
2026-03-26 14:55:15 - app.access - INFO - [929c6110-2664-4da6-a960-06e3f962f0ec] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [2fcd1aaf-b652-41d8-9983-9dd4d69f286c] - Request started
2026-03-26 14:55:15 - app.access - INFO - [2fcd1aaf-b652-41d8-9983-9dd4d69f286c] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [7b926536-9665-45c7-b5bc-dc1fb37a1a4c] - Request started
2026-03-26 14:55:15 - app.access - INFO - [7b926536-9665-45c7-b5bc-dc1fb37a1a4c] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [8b4d12c2-46f2-405e-9342-7c6fef468440] - Request started
2026-03-26 14:55:15 - app.access - INFO - [8b4d12c2-46f2-405e-9342-7c6fef468440] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [12191b2f-bf7e-4219-8b63-1d91fdb37b2f] - Request started
2026-03-26 14:55:15 - app.access - INFO - [12191b2f-bf7e-4219-8b63-1d91fdb37b2f] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [9f08081a-9be2-4dae-8ee7-a8288e1e718e] - Request started
2026-03-26 14:55:15 - app.access - INFO - [9f08081a-9be2-4dae-8ee7-a8288e1e718e] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [531ae627-5391-4a6d-8fd0-19beeb3832a9] - Request started
2026-03-26 14:55:15 - app.access - INFO - [531ae627-5391-4a6d-8fd0-19beeb3832a9] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [be673367-4a32-4521-a73b-805c73120c80] - Request started
2026-03-26 14:55:15 - app.access - INFO - [be673367-4a32-4521-a73b-805c73120c80] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [08c4c4eb-20cf-4d98-a676-71d026a4f21e] - Request started
2026-03-26 14:55:15 - app.access - INFO - [08c4c4eb-20cf-4d98-a676-71d026a4f21e] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [b4c9747c-7258-4c2d-b602-d1a9f1e95e70] - Request started
2026-03-26 14:55:15 - app.access - INFO - [b4c9747c-7258-4c2d-b602-d1a9f1e95e70] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [fb423b69-891b-47de-afa5-d65ce61b58de] - Request started
2026-03-26 14:55:15 - app.access - INFO - [fb423b69-891b-47de-afa5-d65ce61b58de] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [1043d44d-d1e0-4c93-aaf1-4337f569ec2a] - Request started
2026-03-26 14:55:15 - app.access - INFO - [1043d44d-d1e0-4c93-aaf1-4337f569ec2a] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [7e75790c-0ec9-448b-9740-db85a621871e] - Request started
2026-03-26 14:55:15 - app.access - INFO - [7e75790c-0ec9-448b-9740-db85a621871e] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [0c4697d3-e7fd-4eca-af4e-7ae67e23c6b7] - Request started
2026-03-26 14:55:15 - app.access - INFO - [0c4697d3-e7fd-4eca-af4e-7ae67e23c6b7] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:15 - app.access - INFO - [8e30462f-682b-441f-a51f-0dec41619e7e] - Request started
2026-03-26 14:55:15 - app.access - INFO - [8e30462f-682b-441f-a51f-0dec41619e7e] - Request completed
2026-03-26 14:55:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:16 - app.access - INFO - [d0c09289-e9f8-41b9-b0cf-695bf99955aa] - Request started
2026-03-26 14:55:16 - app.access - INFO - [d0c09289-e9f8-41b9-b0cf-695bf99955aa] - Request completed
2026-03-26 14:55:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:16 - app.access - INFO - [d801b9bf-5457-48bb-8461-79698dd2548e] - Request started
2026-03-26 14:55:16 - app.access - INFO - [d801b9bf-5457-48bb-8461-79698dd2548e] - Request completed
2026-03-26 14:55:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:16 - app.access - INFO - [26ff1906-62a5-4c3d-83b7-056937b3aebb] - Request started
2026-03-26 14:55:16 - app.access - INFO - [26ff1906-62a5-4c3d-83b7-056937b3aebb] - Request completed
2026-03-26 14:55:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:16 - app.access - INFO - [680ea71a-13a5-4bb6-bdd5-4d2244859d60] - Request started
2026-03-26 14:55:16 - app.access - INFO - [680ea71a-13a5-4bb6-bdd5-4d2244859d60] - Request completed
2026-03-26 14:55:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:16 - app.access - INFO - [6659dd98-2e24-4f55-bf0c-8eaa1f927874] - Request started
2026-03-26 14:55:16 - app.access - INFO - [6659dd98-2e24-4f55-bf0c-8eaa1f927874] - Request completed
2026-03-26 14:55:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:16 - app.access - INFO - [d544c964-eedf-48b0-8265-32d55a3bc0d1] - Request started
2026-03-26 14:55:16 - app.access - INFO - [d544c964-eedf-48b0-8265-32d55a3bc0d1] - Request completed
2026-03-26 14:55:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:16 - app.access - INFO - [f3c6d879-9a8b-4cbc-b16c-3bdc972af74b] - Request started
2026-03-26 14:55:16 - app.access - INFO - [f3c6d879-9a8b-4cbc-b16c-3bdc972af74b] - Request completed
2026-03-26 14:55:16 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:16 - app.access - INFO - [24f67835-9734-4263-8466-9ebb4942e152] - Request started
2026-03-26 14:55:16 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:17 - app.access - INFO - [24f67835-9734-4263-8466-9ebb4942e152] - Request completed
2026-03-26 14:55:17 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:17 - app.access - INFO - [24922553-80f6-43c8-b70e-e09d01d359b4] - Request started
2026-03-26 14:55:17 - app.core.permissions - INFO - [no-trace-id] - 权限允许: 用户 admin@medqc.com 执行 update 操作在 medical_records 资源上
2026-03-26 14:55:17 - app.access - INFO - [24922553-80f6-43c8-b70e-e09d01d359b4] - Request completed
2026-03-26 14:55:17 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/tasks/task-1/assign "HTTP/1.1 200 OK"
2026-03-26 14:55:17 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:17 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:17 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:17 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:17 - app.access - INFO - [44e0fa64-9789-4638-b327-1dff538e70b9] - Request started
2026-03-26 14:55:17 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:17 - app.access - INFO - [44e0fa64-9789-4638-b327-1dff538e70b9] - Request completed
2026-03-26 14:55:17 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:17 - app.access - INFO - [fae9d0d9-812b-4986-b4fc-828bdfd5f809] - Request started
2026-03-26 14:55:17 - app.access - INFO - [fae9d0d9-812b-4986-b4fc-828bdfd5f809] - Request completed
2026-03-26 14:55:17 - httpx - INFO - [no-trace-id] - HTTP Request: DELETE http://testserver/api/v1/tasks/task-del-1 "HTTP/1.1 200 OK"
2026-03-26 14:55:17 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:17 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:17 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:17 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:17 - app.access - INFO - [9886f9ea-3b2e-4941-845b-984ad3647c86] - Request started
2026-03-26 14:55:18 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:18 - app.access - INFO - [9886f9ea-3b2e-4941-845b-984ad3647c86] - Request completed
2026-03-26 14:55:18 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:18 - app.access - INFO - [a6c2700e-8c7d-4b31-b7cc-2117820d0b8a] - Request started
2026-03-26 14:55:18 - app.main - WARNING - [a6c2700e-8c7d-4b31-b7cc-2117820d0b8a] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:55:18 - app.access - WARNING - [a6c2700e-8c7d-4b31-b7cc-2117820d0b8a] - Request completed
2026-03-26 14:55:18 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/parse-medical-file-public "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:55:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:18 - app.access - INFO - [7003d12c-7a30-4858-83b3-1c59fed6e5c8] - Request started
2026-03-26 14:55:19 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:19 - app.access - INFO - [7003d12c-7a30-4858-83b3-1c59fed6e5c8] - Request completed
2026-03-26 14:55:19 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:19 - app.access - INFO - [dac91f6b-6ada-4f0f-9b4d-6578dd6507c7] - Request started
2026-03-26 14:55:19 - app.main - WARNING - [dac91f6b-6ada-4f0f-9b4d-6578dd6507c7] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:55:19 - app.access - WARNING - [dac91f6b-6ada-4f0f-9b4d-6578dd6507c7] - Request completed
2026-03-26 14:55:19 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/batch-upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:55:19 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:19 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:19 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:19 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:19 - app.access - INFO - [12009e4a-3144-4f57-ba1b-50d1d463c7b7] - Request started
2026-03-26 14:55:20 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:20 - app.access - INFO - [12009e4a-3144-4f57-ba1b-50d1d463c7b7] - Request completed
2026-03-26 14:55:20 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:20 - app.access - INFO - [6181e76e-6df4-458d-b475-74f0abe987e1] - Request started
2026-03-26 14:55:20 - app.main - WARNING - [6181e76e-6df4-458d-b475-74f0abe987e1] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:55:20 - app.access - WARNING - [6181e76e-6df4-458d-b475-74f0abe987e1] - Request completed
2026-03-26 14:55:20 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/records/upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:55:20 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:20 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:20 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:20 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:20 - app.access - INFO - [1b8ced99-b1f8-4291-bc84-0b2fe1108816] - Request started
2026-03-26 14:55:20 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:20 - app.access - INFO - [1b8ced99-b1f8-4291-bc84-0b2fe1108816] - Request completed
2026-03-26 14:55:20 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:20 - app.access - INFO - [dc078f5e-07be-4065-8223-93bb6a07737e] - Request started
2026-03-26 14:55:20 - app.main - WARNING - [dc078f5e-07be-4065-8223-93bb6a07737e] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:55:20 - app.access - WARNING - [dc078f5e-07be-4065-8223-93bb6a07737e] - Request completed
2026-03-26 14:55:20 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:20 - app.access - INFO - [198c0501-5ad6-4217-9683-32fadafd2775] - Request started
2026-03-26 14:55:20 - app.main - WARNING - [198c0501-5ad6-4217-9683-32fadafd2775] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:55:20 - app.access - WARNING - [198c0501-5ad6-4217-9683-32fadafd2775] - Request completed
2026-03-26 14:55:20 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:20 - app.access - INFO - [bcfd427f-9b4b-4aee-b724-6810d5703784] - Request started
2026-03-26 14:55:20 - app.main - WARNING - [bcfd427f-9b4b-4aee-b724-6810d5703784] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:55:20 - app.access - WARNING - [bcfd427f-9b4b-4aee-b724-6810d5703784] - Request completed
2026-03-26 14:55:20 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:20 - app.access - INFO - [7e8b4d21-9ada-431b-b1f5-93902f2ed1a9] - Request started
2026-03-26 14:55:21 - app.main - WARNING - [7e8b4d21-9ada-431b-b1f5-93902f2ed1a9] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:55:21 - app.access - WARNING - [7e8b4d21-9ada-431b-b1f5-93902f2ed1a9] - Request completed
2026-03-26 14:55:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:21 - app.access - INFO - [b3c16ffc-79b3-42c5-896b-61d3e6cab0d2] - Request started
2026-03-26 14:55:21 - app.main - WARNING - [b3c16ffc-79b3-42c5-896b-61d3e6cab0d2] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:55:21 - app.access - WARNING - [b3c16ffc-79b3-42c5-896b-61d3e6cab0d2] - Request completed
2026-03-26 14:55:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:21 - app.access - INFO - [a660b0ee-1798-4b88-b922-520543ab7997] - Request started
2026-03-26 14:55:21 - app.main - WARNING - [a660b0ee-1798-4b88-b922-520543ab7997] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:55:21 - app.access - WARNING - [a660b0ee-1798-4b88-b922-520543ab7997] - Request completed
2026-03-26 14:55:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:21 - app.access - INFO - [c788c2b3-9d50-4c6f-a664-dbf3580b3937] - Request started
2026-03-26 14:55:21 - app.main - WARNING - [c788c2b3-9d50-4c6f-a664-dbf3580b3937] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:55:21 - app.access - WARNING - [c788c2b3-9d50-4c6f-a664-dbf3580b3937] - Request completed
2026-03-26 14:55:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:21 - app.access - INFO - [411207fc-9398-4a76-857e-47b1e4a7c908] - Request started
2026-03-26 14:55:21 - app.main - WARNING - [411207fc-9398-4a76-857e-47b1e4a7c908] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:55:21 - app.access - WARNING - [411207fc-9398-4a76-857e-47b1e4a7c908] - Request completed
2026-03-26 14:55:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:21 - app.access - INFO - [7d984fa4-1fbe-4937-b747-18aeb6907ae5] - Request started
2026-03-26 14:55:21 - app.main - WARNING - [7d984fa4-1fbe-4937-b747-18aeb6907ae5] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:55:21 - app.access - WARNING - [7d984fa4-1fbe-4937-b747-18aeb6907ae5] - Request completed
2026-03-26 14:55:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:21 - app.access - INFO - [326facf3-1353-418b-9f76-fe606b0a0e7a] - Request started
2026-03-26 14:55:21 - app.main - WARNING - [326facf3-1353-418b-9f76-fe606b0a0e7a] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:55:21 - app.access - WARNING - [326facf3-1353-418b-9f76-fe606b0a0e7a] - Request completed
2026-03-26 14:55:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:21 - app.access - INFO - [86355194-085b-4239-9fd6-78a1779aa060] - Request started
2026-03-26 14:55:21 - app.core.rate_limit - WARNING - [86355194-085b-4239-9fd6-78a1779aa060] - audit.rate_limit.exceeded bucket=drg_smart_upload key=drg_smart_upload:testclient method=POST path=/api/v1/drg/smart-upload
2026-03-26 14:55:21 - app.main - WARNING - [86355194-085b-4239-9fd6-78a1779aa060] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:55:21 - app.access - WARNING - [86355194-085b-4239-9fd6-78a1779aa060] - Request completed
2026-03-26 14:55:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:55:21 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:21 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:21 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:21 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:21 - app.access - INFO - [28b8c19d-ca20-43d3-9e1e-26e9d4ca23f8] - Request started
2026-03-26 14:55:21 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:21 - app.access - INFO - [28b8c19d-ca20-43d3-9e1e-26e9d4ca23f8] - Request completed
2026-03-26 14:55:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:21 - app.access - INFO - [4965d24c-bd9b-4496-94d7-0e3ad179d36e] - Request started
2026-03-26 14:55:21 - app.core.upload_security - WARNING - [4965d24c-bd9b-4496-94d7-0e3ad179d36e] - audit.upload.rejected reason=extension_not_allowed filename=malicious.exe content_type=application/octet-stream size_bytes=4
2026-03-26 14:55:21 - app.main - WARNING - [4965d24c-bd9b-4496-94d7-0e3ad179d36e] - HTTP Exception: 400 - 不支持的文件扩展名: .exe
2026-03-26 14:55:21 - app.access - WARNING - [4965d24c-bd9b-4496-94d7-0e3ad179d36e] - Request completed
2026-03-26 14:55:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/parse-medical-file-public "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:22 - app.access - INFO - [8d5af4ec-c27c-4da9-9e08-b61b91f2e9b7] - Request started
2026-03-26 14:55:22 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:22 - app.access - INFO - [8d5af4ec-c27c-4da9-9e08-b61b91f2e9b7] - Request completed
2026-03-26 14:55:22 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:22 - app.access - INFO - [c4ba5875-ef63-402e-b905-56beaf6a467f] - Request started
2026-03-26 14:55:22 - app.core.upload_security - WARNING - [c4ba5875-ef63-402e-b905-56beaf6a467f] - audit.upload.rejected reason=virus_scan_blocked filename=record.txt content_type=text/plain size_bytes=68
2026-03-26 14:55:22 - app.main - WARNING - [c4ba5875-ef63-402e-b905-56beaf6a467f] - HTTP Exception: 400 - 检测到潜在恶意文件签名
2026-03-26 14:55:22 - app.access - WARNING - [c4ba5875-ef63-402e-b905-56beaf6a467f] - Request completed
2026-03-26 14:55:22 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/records/upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:22 - app.access - INFO - [1e268e9d-ff21-437d-b30f-b01d47fef114] - Request started
2026-03-26 14:55:23 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:23 - app.access - INFO - [1e268e9d-ff21-437d-b30f-b01d47fef114] - Request completed
2026-03-26 14:55:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:23 - app.access - INFO - [25892826-e727-4edb-8090-28e5fa9d8e32] - Request started
2026-03-26 14:55:23 - app.core.upload_security - WARNING - [25892826-e727-4edb-8090-28e5fa9d8e32] - audit.upload.rejected reason=mime_not_allowed filename=sample.csv content_type=image/png size_bytes=81
2026-03-26 14:55:23 - app.main - WARNING - [25892826-e727-4edb-8090-28e5fa9d8e32] - HTTP Exception: 400 - 不支持的文件类型: image/png
2026-03-26 14:55:23 - app.access - WARNING - [25892826-e727-4edb-8090-28e5fa9d8e32] - Request completed
2026-03-26 14:55:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/batch-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:23 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:55:23 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:55:23 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:55:23 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:55:23 - app.access - INFO - [d1e090b7-4903-4ab7-ba96-1a8affb6f0c4] - Request started
2026-03-26 14:55:24 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:24 - app.access - INFO - [d1e090b7-4903-4ab7-ba96-1a8affb6f0c4] - Request completed
2026-03-26 14:55:24 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:24 - app.access - INFO - [2abcf0d2-ca03-40fd-88ce-813a5fa904c1] - Request started
2026-03-26 14:55:24 - app.core.upload_security - WARNING - [2abcf0d2-ca03-40fd-88ce-813a5fa904c1] - audit.upload.rejected reason=file_too_large filename=sample.csv content_type=text/csv size_bytes=10
2026-03-26 14:55:24 - app.main - WARNING - [2abcf0d2-ca03-40fd-88ce-813a5fa904c1] - HTTP Exception: 400 - 文件大小不能超过 8B
2026-03-26 14:55:24 - app.access - WARNING - [2abcf0d2-ca03-40fd-88ce-813a5fa904c1] - Request completed
2026-03-26 14:55:24 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:55:24 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:55:24 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:55:25 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
```
### pytest_integration_smoke
```text
Database initialized: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\data\demo_feedbacks.db
============================= test session starts =============================
platform win32 -- Python 3.10.11, pytest-7.4.3, pluggy-1.6.0
rootdir: D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend
configfile: pytest.ini
plugins: anyio-3.7.1, devtools-0.12.2, asyncio-0.21.1, mock-3.12.0, timeout-2.4.0
asyncio: mode=strict
collected 5 items

tests\integration\test_release_gate_smoke.py .....

============================== warnings summary ===============================
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268
  C:\Python310\lib\site-packages\pydantic\_internal\_config.py:268: PydanticDeprecatedSince20: Support for class-based `config` is deprecated, use ConfigDict instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.5/migration/
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning)

app\models\demo.py:10
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\models\demo.py:10: MovedIn20Warning: The ``declarative_base()`` function is now available as sqlalchemy.orm.declarative_base(). (deprecated since: 2.0) (Background on SQLAlchemy 2.0 at: https://sqlalche.me/e/b8d9)
    Base = declarative_base()

app\main.py:308
tests/integration/test_release_gate_smoke.py::test_release_gate_auth_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_authz_reject_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_sync_trigger_permission_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_records_query_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_system_probe_smoke
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\main.py:308: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

C:\Python310\lib\site-packages\fastapi\applications.py:4547
tests/integration/test_release_gate_smoke.py::test_release_gate_auth_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_authz_reject_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_sync_trigger_permission_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_records_query_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_system_probe_smoke
  C:\Python310\lib\site-packages\fastapi\applications.py:4547: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 5 passed, 19 warnings in 10.59s =======================
2026-03-26 14:55:43 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:55:43 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:55:45 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:55:45 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:55:46 - app.access - INFO - [d6a96f03-7705-4b13-a5c5-2ca34f49d856] - Request started
2026-03-26 14:55:47 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=release-gate-bacb0c005f04@example.com roles=doctor trace_id=d6a96f03-7705-4b13-a5c5-2ca34f49d856 details={"assigned_roles": ["doctor"], "department": "质控科", "target_email": "release-gate-bacb0c005f04@example.com"}
2026-03-26 14:55:47 - app.access - INFO - [d6a96f03-7705-4b13-a5c5-2ca34f49d856] - Request completed
2026-03-26 14:55:47 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 14:55:47 - app.access - INFO - [5bb32421-50ce-4ee4-bd75-fa4a7c66e934] - Request started
2026-03-26 14:55:47 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-bacb0c005f04@example.com
2026-03-26 14:55:47 - app.access - INFO - [5bb32421-50ce-4ee4-bd75-fa4a7c66e934] - Request completed
2026-03-26 14:55:47 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:47 - app.access - INFO - [6d1571f3-726c-4889-8f1b-193df425a1a6] - Request started
2026-03-26 14:55:47 - app.access - INFO - [6d1571f3-726c-4889-8f1b-193df425a1a6] - Request completed
2026-03-26 14:55:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/auth/me "HTTP/1.1 200 OK"
2026-03-26 14:55:47 - app.access - INFO - [3f76b33f-8eb6-439f-a559-648e1628c7d6] - Request started
2026-03-26 14:55:48 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=release-gate-bacb0c005f04@example.com
2026-03-26 14:55:48 - app.access - INFO - [3f76b33f-8eb6-439f-a559-648e1628c7d6] - Request completed
2026-03-26 14:55:48 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 14:55:48 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:55:48 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:55:49 - app.access - INFO - [b3eae775-6bda-4d2d-8969-015e64338f07] - Request started
2026-03-26 14:55:49 - app.main - WARNING - [b3eae775-6bda-4d2d-8969-015e64338f07] - HTTP Exception: 401 - Authentication required
2026-03-26 14:55:49 - app.access - WARNING - [b3eae775-6bda-4d2d-8969-015e64338f07] - Request completed
2026-03-26 14:55:49 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 14:55:49 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:55:49 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:55:51 - app.access - INFO - [59ba005d-a650-40f7-beac-b3c0ec0e9f1e] - Request started
2026-03-26 14:55:51 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=release-gate-5deb03641f45@example.com roles=doctor trace_id=59ba005d-a650-40f7-beac-b3c0ec0e9f1e details={"assigned_roles": ["doctor"], "department": "质控科", "target_email": "release-gate-5deb03641f45@example.com"}
2026-03-26 14:55:51 - app.access - INFO - [59ba005d-a650-40f7-beac-b3c0ec0e9f1e] - Request completed
2026-03-26 14:55:51 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 14:55:51 - app.access - INFO - [1fedcc0c-21ba-4c31-8d16-293f81587d6a] - Request started
2026-03-26 14:55:52 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-5deb03641f45@example.com
2026-03-26 14:55:52 - app.access - INFO - [1fedcc0c-21ba-4c31-8d16-293f81587d6a] - Request completed
2026-03-26 14:55:52 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:52 - app.access - INFO - [34fddbbb-3175-4f4a-b1bd-183bb36c46d1] - Request started
2026-03-26 14:55:52 - app.main - WARNING - [34fddbbb-3175-4f4a-b1bd-183bb36c46d1] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 14:55:52 - app.access - WARNING - [34fddbbb-3175-4f4a-b1bd-183bb36c46d1] - Request completed
2026-03-26 14:55:52 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 14:55:52 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:55:52 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:55:53 - app.access - INFO - [b3a3eac3-a039-4e18-9efa-4049fd9c429e] - Request started
2026-03-26 14:55:54 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:55:54 - app.access - INFO - [b3a3eac3-a039-4e18-9efa-4049fd9c429e] - Request completed
2026-03-26 14:55:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:55:54 - app.access - INFO - [828138f0-ba4f-4cd0-a769-f92138f92e8e] - Request started
2026-03-26 14:55:54 - app.core.permissions - INFO - [no-trace-id] - 权限允许: 用户 admin@medqc.com 执行 read 操作在 medical_records 资源上
2026-03-26 14:55:54 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 14:55:54 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 14:55:54 - app.access - INFO - [828138f0-ba4f-4cd0-a769-f92138f92e8e] - Request completed
2026-03-26 14:55:54 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/records?page=1&page_size=5 "HTTP/1.1 200 OK"
2026-03-26 14:55:54 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:55:54 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:55:55 - app.access - INFO - [29d55097-4701-4980-95ec-5088b64f4db2] - Request started
2026-03-26 14:55:55 - app.access - INFO - [29d55097-4701-4980-95ec-5088b64f4db2] - Request completed
2026-03-26 14:55:55 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:55:55 - app.access - INFO - [796b5521-8a79-438e-85a1-85928401f6a0] - Request started
2026-03-26 14:55:55 - app.access - INFO - [796b5521-8a79-438e-85a1-85928401f6a0] - Request completed
2026-03-26 14:55:55 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
```