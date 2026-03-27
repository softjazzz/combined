# Backend Release Gate Report

- total gates: 9
- passed gates: 9
- failed gates: 0
- all passed: True

## Gate Details
- auth_guard: PASS (0.12s)
  metrics: {"required_checks": 7, "passed_checks": 7, "coverage_ratio": 1.0}
- secret_hygiene: PASS (0.12s)
  metrics: {"findings": 0}
- alert_rules: PASS (0.13s)
  metrics: {"pass_marker_found": true}
- openapi_contract: PASS (10.29s)
  metrics: {"pass_marker_found": true}
- metrics_catalog: PASS (0.11s)
  metrics: {"pass_marker_found": true}
- migration_roundtrip: PASS (4.69s)
  metrics: {"head_count": 1, "head": "20260315_000002"}
- pytest_contract: PASS (14.56s)
  metrics: {"passed": 33, "failed": 0, "skipped": 0}
- pytest_security_consistency: PASS (17.74s)
  metrics: {"passed": 48, "failed": 0, "skipped": 0}
- pytest_integration_smoke: PASS (12.82s)
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
[openapi] PASS {"paths": 261, "schemas": 105}
2026-03-26 15:46:40 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:46:40 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:46:40 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:40 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:40 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:40 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:40 - app.access - INFO - [d3641ab7-e407-474f-a164-a2200c8c292c] - Request started
2026-03-26 15:46:41 - app.access - INFO - [d3641ab7-e407-474f-a164-a2200c8c292c] - Request completed
2026-03-26 15:46:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
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
======================= 33 passed, 13 warnings in 5.41s =======================
2026-03-26 15:46:54 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:46:54 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:46:55 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:46:55 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:46:55 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:55 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:55 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:55 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:55 - app.access - INFO - [badca08c-0c95-46b8-b1bc-8b8eb62aae81] - Request started
2026-03-26 15:46:56 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:46:56 - app.access - INFO - [badca08c-0c95-46b8-b1bc-8b8eb62aae81] - Request completed
2026-03-26 15:46:56 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:46:56 - app.access - INFO - [18c9422f-09f3-4e6a-bc3d-f733e4113cef] - Request started
2026-03-26 15:46:56 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 15:46:56 - app.access - INFO - [18c9422f-09f3-4e6a-bc3d-f733e4113cef] - Request completed
2026-03-26 15:46:56 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 15:46:56 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:56 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:56 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:56 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:56 - app.access - INFO - [735420d6-0855-4c8d-9e95-a994d7c71fad] - Request started
2026-03-26 15:46:56 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:46:56 - app.access - INFO - [735420d6-0855-4c8d-9e95-a994d7c71fad] - Request completed
2026-03-26 15:46:56 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:46:56 - app.access - INFO - [caffa3c0-2af7-4d69-8f94-f560218ee84a] - Request started
2026-03-26 15:46:56 - app.access - INFO - [caffa3c0-2af7-4d69-8f94-f560218ee84a] - Request completed
2026-03-26 15:46:56 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 15:46:56 - app.access - INFO - [647f0aae-5771-421c-bb88-b285c44a6bf2] - Request started
2026-03-26 15:46:56 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.pg.update resource=/api/v1/sync/config/pg outcome=success actor=admin@medqc.com roles=admin,qc_manager trace_id=647f0aae-5771-421c-bb88-b285c44a6bf2 details={"changed_fields": ["remote_host", "remote_password", "remote_password_ref", "remote_port"], "connection_ok": true, "remote_host": "10.8.8.8", "remote_port": "5544"}
2026-03-26 15:46:56 - app.access - INFO - [647f0aae-5771-421c-bb88-b285c44a6bf2] - Request completed
2026-03-26 15:46:56 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 15:46:56 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:56 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:56 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:56 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:56 - app.access - INFO - [6680bb54-7406-4f2f-b69e-7c5de73a71da] - Request started
2026-03-26 15:46:57 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 15:46:57 - app.access - INFO - [6680bb54-7406-4f2f-b69e-7c5de73a71da] - Request completed
2026-03-26 15:46:57 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:46:57 - app.access - INFO - [8b268fb4-de33-472e-937f-47402c40a062] - Request started
2026-03-26 15:46:57 - app.main - WARNING - [8b268fb4-de33-472e-937f-47402c40a062] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 15:46:57 - app.access - WARNING - [8b268fb4-de33-472e-937f-47402c40a062] - Request completed
2026-03-26 15:46:57 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 15:46:57 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:57 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:57 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:57 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:57 - app.access - INFO - [82e0bf90-8e96-43de-941a-8b842d11faec] - Request started
2026-03-26 15:46:57 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:46:57 - app.access - INFO - [82e0bf90-8e96-43de-941a-8b842d11faec] - Request completed
2026-03-26 15:46:57 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:46:57 - app.access - INFO - [ff3e97ec-4c7d-4870-831c-5711ceff812a] - Request started
2026-03-26 15:46:57 - app.routers.qc_sichuan - INFO - [no-trace-id] - Loaded 179 Sichuan rules from JSON file
2026-03-26 15:46:57 - app.access - INFO - [ff3e97ec-4c7d-4870-831c-5711ceff812a] - Request completed
2026-03-26 15:46:57 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/rules "HTTP/1.1 200 OK"
2026-03-26 15:46:57 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:57 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:57 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:57 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:57 - app.access - INFO - [890a5b91-1e23-4fe9-92c3-9a7ea7b2741a] - Request started
2026-03-26 15:46:57 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:46:57 - app.access - INFO - [890a5b91-1e23-4fe9-92c3-9a7ea7b2741a] - Request completed
2026-03-26 15:46:57 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:46:57 - app.access - INFO - [c773ccfc-a5a7-436c-a06a-96a0a16efd55] - Request started
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251110_041209.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251109_233517.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_234838.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_070941.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065547.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065421.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_062819.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_053504.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_021345.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_015054.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_014934.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_013113.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_005230.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\fe17a51e-5db0-4d37-ab6d-ac41cecca752_sequential_batch_20251112_130619.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f41ab06d-0f77-4f0f-ad27-e9c08fea5756_sequential_batch_20251112_143049.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f158d3cf-7fa9-4059-82e6-01e478d60399_sequential_batch_20251112_142617.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\e6cd1e70-88ac-4df9-a164-1326d35a6874_sequential_batch_20251110_064046.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\daf44f72-0baa-453b-bf32-b9355bd3bd01_sequential_batch_20251112_011112.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\defbcbd9-94e9-4723-b6df-dbf0b21ea4f7_sequential_batch_20251112_233633.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\c79d0012-c564-4d1c-bd4c-cf5aebe1fd92_sequential_batch_20251112_132237.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_083256.json: 'list' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a9c69ec9-9675-40ed-b203-5d830842a11c_sequential_batch_20251112_013953.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_082322.json: 'list' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a2bbfbe5-48de-4da8-bb47-e0cc59424775_sequential_batch_20251112_233854.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\9d5ec2a7-dc69-40dc-86ac-2c1e52f9aafd_sequential_batch_20251112_031338.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\89bb0a9d-14b9-48bc-8f67-f04f89fbb9c5_sequential_batch_20251112_031203.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\81d4a41f-bd3d-457d-aea6-1c32a412312e_sequential_batch_20251111_120900.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\818fe627-f5ad-4101-b06d-8a2addf10a71_sequential_batch_20251111_134659.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6fd14104-4d02-4b52-bc3d-a012cf4ede90_sequential_batch_20251112_232848.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6de19991-4266-4aa4-8bef-ee3001fb3ddc_sequential_batch_20251113_000427.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6154a09c-c692-4cfd-83a7-eb2773a9ad8b_sequential_batch_20251112_141218.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\5a2b1859-a0a8-436b-a4a0-af30eb6db6dc_sequential_batch_20251111_235912.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\57c72978-223b-4e01-b6ff-180e802c1718_sequential_batch_20251112_130944.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4eb1f192-80d8-48fa-8393-0c91b788d0d9_sequential_batch_20251111_235832.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4798fb59-6450-4f11-94c3-848d2702cf6c_sequential_batch_20251112_151503.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4596298c-eca7-4ca2-89ce-30ce5ae2898d_sequential_batch_20251111_012838.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\36f11425-d816-4f8a-b624-dced1ac4c164_sequential_batch_20251112_060145.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\2c59b9ef-9b2f-4ef8-b671-d0840df86da8_sequential_batch_20251112_231936.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1e2886a3-253f-4008-b4c7-da32548e5826_sequential_batch_20251111_121107.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1ca2602c-56e6-4310-b686-19a73531a8a9_sequential_batch_20251112_232958.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\13c4efdd-6bff-4ff7-aa51-2bc906aad435_sequential_batch_20251112_232048.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:46:57 - app.access - INFO - [c773ccfc-a5a7-436c-a06a-96a0a16efd55] - Request completed
2026-03-26 15:46:57 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/results/history?page=1&page_size=10 "HTTP/1.1 200 OK"
2026-03-26 15:46:57 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:57 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:57 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:57 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:57 - app.access - INFO - [76aaae55-3a80-4d4c-8f82-c175828f397c] - Request started
2026-03-26 15:46:58 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:46:58 - app.access - INFO - [76aaae55-3a80-4d4c-8f82-c175828f397c] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.access - INFO - [39c7a51d-afac-4ee9-8bb4-3218f065c998] - Request started
2026-03-26 15:46:58 - app.access - INFO - [39c7a51d-afac-4ee9-8bb4-3218f065c998] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [39658101-7abf-4665-9a67-2008b601cc7e] - Request started
2026-03-26 15:46:58 - app.access - INFO - [39658101-7abf-4665-9a67-2008b601cc7e] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [ffd36073-7992-4a5a-8145-9b3576525019] - Request started
2026-03-26 15:46:58 - app.access - INFO - [ffd36073-7992-4a5a-8145-9b3576525019] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [ff7642c0-90d0-4c81-b563-256b2b11ee2b] - Request started
2026-03-26 15:46:58 - app.access - INFO - [ff7642c0-90d0-4c81-b563-256b2b11ee2b] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.access - INFO - [09cd45a1-d86c-4f4b-be38-a5fc53c6b41a] - Request started
2026-03-26 15:46:58 - app.access - INFO - [09cd45a1-d86c-4f4b-be38-a5fc53c6b41a] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.access - INFO - [ec1677ee-4e4f-4509-93f6-54caa99fa155] - Request started
2026-03-26 15:46:58 - app.main - WARNING - [ec1677ee-4e4f-4509-93f6-54caa99fa155] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 15:46:58 - app.access - WARNING - [ec1677ee-4e4f-4509-93f6-54caa99fa155] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 403 Forbidden"
2026-03-26 15:46:58 - app.access - INFO - [3b96cd7d-4c79-43d6-989a-d1cf7abecc70] - Request started
2026-03-26 15:46:58 - app.main - WARNING - [3b96cd7d-4c79-43d6-989a-d1cf7abecc70] - HTTP Exception: 401 - Authentication required
2026-03-26 15:46:58 - app.access - WARNING - [3b96cd7d-4c79-43d6-989a-d1cf7abecc70] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 401 Unauthorized"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [83b0c149-826f-4bf8-ab4f-b7975348c659] - Request started
2026-03-26 15:46:58 - app.main - WARNING - [83b0c149-826f-4bf8-ab4f-b7975348c659] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 15:46:58 - app.access - WARNING - [83b0c149-826f-4bf8-ab4f-b7975348c659] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [6e218283-7487-4eca-8479-ed9ed89ac184] - Request started
2026-03-26 15:46:58 - app.main - WARNING - [6e218283-7487-4eca-8479-ed9ed89ac184] - Validation Error: [{'type': 'greater_than_equal', 'loc': ('body', 'lookback_minutes'), 'msg': 'Input should be greater than or equal to 0', 'input': -1, 'ctx': {'ge': 0}, 'url': 'https://errors.pydantic.dev/2.5/v/greater_than_equal'}]
2026-03-26 15:46:58 - app.access - WARNING - [6e218283-7487-4eca-8479-ed9ed89ac184] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 15:46:58 - app.access - INFO - [7d44dca4-10f2-4bb2-96e2-cf3648a135d4] - Request started
2026-03-26 15:46:58 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.mongo.update resource=/api/v1/sync/config/mongo outcome=success actor=sync@test.local roles=admin trace_id=7d44dca4-10f2-4bb2-96e2-cf3648a135d4 details={"changed_fields": ["connect_timeout_ms", "enabled", "inter_request_delay_ms", "lookback_minutes", "max_batch_size", "night_window_end", "night_window_start", "rescan_recent_days", "tier1_interval_minutes", "tier2_interval_minutes", "tier3_cron"], "enabled": true}
2026-03-26 15:46:58 - app.access - INFO - [7d44dca4-10f2-4bb2-96e2-cf3648a135d4] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [2498db30-e3e5-44d8-b563-d8b794839b8b] - Request started
2026-03-26 15:46:58 - app.access - INFO - [2498db30-e3e5-44d8-b563-d8b794839b8b] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [3be63f2c-5d71-4c30-b57b-fc56d5cf60b7] - Request started
2026-03-26 15:46:58 - app.access - INFO - [3be63f2c-5d71-4c30-b57b-fc56d5cf60b7] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/test-connection/all "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [c6ea1fbd-49f7-4b42-841b-3f7f1238529e] - Request started
2026-03-26 15:46:58 - app.access - INFO - [c6ea1fbd-49f7-4b42-841b-3f7f1238529e] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [49bd7542-cbb3-4847-84d3-442216a89deb] - Request started
2026-03-26 15:46:58 - app.access - INFO - [49bd7542-cbb3-4847-84d3-442216a89deb] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [24c8cb11-09b1-4fce-b8ab-d6f250ed1543] - Request started
2026-03-26 15:46:58 - app.audit - INFO - [no-trace-id] - audit.event action=sync.trigger resource=/api/v1/sync/trigger outcome=rejected_running actor=sync@test.local roles=admin trace_id=24c8cb11-09b1-4fce-b8ab-d6f250ed1543 details={"idempotency_key": "mongo:all:2026-03-26:sync@test.local", "run_id": "syncrun-c9597f430f68", "source": "mongo", "sync_date": "2026-03-26", "tier": "all"}
2026-03-26 15:46:58 - app.access - INFO - [24c8cb11-09b1-4fce-b8ab-d6f250ed1543] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [f72fdaad-a418-4330-8e94-4f341d0174a2] - Request started
2026-03-26 15:46:58 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 15:46:58 - app.audit - INFO - [no-trace-id] - audit.event action=sync.trigger resource=/api/v1/sync/trigger outcome=success actor=sync@test.local roles=admin trace_id=f72fdaad-a418-4330-8e94-4f341d0174a2 details={"idempotency_key": "mongo:tier1:2026-03-26:sync@test.local", "run_id": "syncrun-a0f5c37697f0", "source": "mongo", "status": "success", "sync_date": "2026-03-26", "tier": "tier1", "total_records": 2}
2026-03-26 15:46:58 - app.access - INFO - [f72fdaad-a418-4330-8e94-4f341d0174a2] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:58 - app.access - INFO - [5f44d852-9765-49da-a2a7-aed2b16decd9] - Request started
2026-03-26 15:46:58 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 15:46:58 - app.access - INFO - [5f44d852-9765-49da-a2a7-aed2b16decd9] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 15:46:58 - app.access - INFO - [7f04f0df-744b-498c-b35c-a9fbf083bcde] - Request started
2026-03-26 15:46:58 - app.access - INFO - [7f04f0df-744b-498c-b35c-a9fbf083bcde] - Request completed
2026-03-26 15:46:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [1acbe174-1654-4ff7-ad3b-29211d19aacd] - Request started
2026-03-26 15:46:59 - app.access - INFO - [1acbe174-1654-4ff7-ad3b-29211d19aacd] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/runs?source=mongo&tier=tier2&limit=20 "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [3644e415-bb7a-4d17-aa55-1f06cb43917b] - Request started
2026-03-26 15:46:59 - app.access - INFO - [3644e415-bb7a-4d17-aa55-1f06cb43917b] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.access - INFO - [30e2ed05-9479-436f-8bdb-bb744984ee34] - Request started
2026-03-26 15:46:59 - app.main - WARNING - [30e2ed05-9479-436f-8bdb-bb744984ee34] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 15:46:59 - app.access - WARNING - [30e2ed05-9479-436f-8bdb-bb744984ee34] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 403 Forbidden"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [31b6846d-db3a-4446-a1ed-926646fe2ca5] - Request started
2026-03-26 15:46:59 - app.audit - INFO - [no-trace-id] - audit.event action=sync.template.apply resource=/api/v1/sync/templates/apply outcome=success actor=sync@test.local roles=admin trace_id=31b6846d-db3a-4446-a1ed-926646fe2ca5 details={"departments_count": 1, "enabled": false, "template_id": "single_department_focus"}
2026-03-26 15:46:59 - app.access - INFO - [31b6846d-db3a-4446-a1ed-926646fe2ca5] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [c264d296-958f-4d8a-9346-72173a6e7fce] - Request started
2026-03-26 15:46:59 - app.main - WARNING - [c264d296-958f-4d8a-9346-72173a6e7fce] - HTTP Exception: 422 - 该模板必须选择科室
2026-03-26 15:46:59 - app.access - WARNING - [c264d296-958f-4d8a-9346-72173a6e7fce] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 15:46:59 - app.access - INFO - [e71a8a33-b495-44dd-ba40-738f73ea44b6] - Request started
2026-03-26 15:46:59 - app.main - WARNING - [e71a8a33-b495-44dd-ba40-738f73ea44b6] - HTTP Exception: 422 - 科室列表不允许同时包含 * 和具体科室
2026-03-26 15:46:59 - app.access - WARNING - [e71a8a33-b495-44dd-ba40-738f73ea44b6] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [bf1118a7-c1c4-49c3-af4e-9fda40bf5458] - Request started
2026-03-26 15:46:59 - app.access - INFO - [bf1118a7-c1c4-49c3-af4e-9fda40bf5458] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [d2169b2a-6626-449b-9e8e-e79049a8d154] - Request started
2026-03-26 15:46:59 - app.main - WARNING - [d2169b2a-6626-449b-9e8e-e79049a8d154] - HTTP Exception: 422 - mongo_uri 未配置
2026-03-26 15:46:59 - app.access - WARNING - [d2169b2a-6626-449b-9e8e-e79049a8d154] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [3a9d145a-ac5e-4f60-b230-44add423861f] - Request started
2026-03-26 15:46:59 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 15:46:59 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 15:46:59 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:46:59 - app.access - INFO - [3a9d145a-ac5e-4f60-b230-44add423861f] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [db695ae2-8904-4a75-bb07-e436c7580cdd] - Request started
2026-03-26 15:46:59 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:46:59 - app.access - INFO - [db695ae2-8904-4a75-bb07-e436c7580cdd] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics/prometheus "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [trace-client-123] - Request started
2026-03-26 15:46:59 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:46:59 - app.access - INFO - [trace-client-123] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [req-client-456] - Request started
2026-03-26 15:46:59 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:46:59 - app.access - INFO - [req-client-456] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request started
2026-03-26 15:46:59 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:46:59 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [d77ab983-490e-4786-a06c-fd80e41bd69f] - Request started
2026-03-26 15:46:59 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:46:59 - app.access - INFO - [d77ab983-490e-4786-a06c-fd80e41bd69f] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request started
2026-03-26 15:46:59 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:46:59 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request completed
2026-03-26 15:46:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:46:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:46:59 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:46:59 - app.core.otel - WARNING - [no-trace-id] - OpenTelemetry dependencies unavailable, skip instrumentation: No module named 'opentelemetry'
2026-03-26 15:47:00 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:00 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:00 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:00 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:00 - app.access - INFO - [9fddb18c-4969-4f6c-9c10-4c2b869aa126] - Request started
2026-03-26 15:47:00 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:47:00 - app.access - ERROR - [9fddb18c-4969-4f6c-9c10-4c2b869aa126] - Request failed: boom
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
2026-03-26 15:47:00 - app.core.middleware_errors - ERROR - [9fddb18c-4969-4f6c-9c10-4c2b869aa126] - Internal Server Error: boom
2026-03-26 15:47:00 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 500 Internal Server Error"
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
======================= 48 passed, 13 warnings in 9.56s =======================
2026-03-26 15:47:08 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:47:08 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:47:08 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.pg.update resource=/api/v1/sync/config/pg outcome=success actor=admin@medqc.com roles=admin trace_id=trace-unit-audit details={"nested": {"token": "***"}, "remote_host": "127.0.0.1", "remote_password": "***"}
2026-03-26 15:47:08 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:47:08 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:47:09 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:09 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:09 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:09 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:09 - app.access - INFO - [24c110f0-0e27-4e6b-ac11-420ed9b93ae2] - Request started
2026-03-26 15:47:09 - app.main - WARNING - [24c110f0-0e27-4e6b-ac11-420ed9b93ae2] - HTTP Exception: 401 - Authentication required
2026-03-26 15:47:09 - app.access - WARNING - [24c110f0-0e27-4e6b-ac11-420ed9b93ae2] - Request completed
2026-03-26 15:47:09 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 15:47:09 - app.access - INFO - [f4fb2111-ca52-4e96-bf78-efc71762339e] - Request started
2026-03-26 15:47:09 - app.main - WARNING - [f4fb2111-ca52-4e96-bf78-efc71762339e] - HTTP Exception: 401 - Authentication required
2026-03-26 15:47:09 - app.access - WARNING - [f4fb2111-ca52-4e96-bf78-efc71762339e] - Request completed
2026-03-26 15:47:09 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/drg/config/current "HTTP/1.1 401 Unauthorized"
2026-03-26 15:47:09 - app.access - INFO - [c5304165-93f4-4e9d-bd66-6e674330146a] - Request started
2026-03-26 15:47:09 - app.main - WARNING - [c5304165-93f4-4e9d-bd66-6e674330146a] - HTTP Exception: 401 - Authentication required
2026-03-26 15:47:09 - app.access - WARNING - [c5304165-93f4-4e9d-bd66-6e674330146a] - Request completed
2026-03-26 15:47:09 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/settlement/list "HTTP/1.1 401 Unauthorized"
2026-03-26 15:47:09 - app.access - INFO - [f3414896-691f-4fa5-8878-44f09cd154ce] - Request started
2026-03-26 15:47:09 - app.main - WARNING - [f3414896-691f-4fa5-8878-44f09cd154ce] - HTTP Exception: 401 - Authentication required
2026-03-26 15:47:09 - app.access - WARNING - [f3414896-691f-4fa5-8878-44f09cd154ce] - Request completed
2026-03-26 15:47:09 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 401 Unauthorized"
2026-03-26 15:47:09 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:09 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:09 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:09 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:09 - app.access - INFO - [15e192d7-09d6-4853-a512-9311180ccbb7] - Request started
2026-03-26 15:47:09 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 15:47:09 - app.access - INFO - [15e192d7-09d6-4853-a512-9311180ccbb7] - Request completed
2026-03-26 15:47:09 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:09 - app.access - INFO - [b3b6e44d-ef87-4051-9282-9aba0258142b] - Request started
2026-03-26 15:47:09 - app.main - WARNING - [b3b6e44d-ef87-4051-9282-9aba0258142b] - HTTP Exception: 403 - 此操作需要系统管理员权限
2026-03-26 15:47:09 - app.access - WARNING - [b3b6e44d-ef87-4051-9282-9aba0258142b] - Request completed
2026-03-26 15:47:09 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 403 Forbidden"
2026-03-26 15:47:09 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:09 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:09 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:09 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:09 - app.access - INFO - [2f640395-d43c-4531-bfb9-b307e1a14beb] - Request started
2026-03-26 15:47:10 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:10 - app.access - INFO - [2f640395-d43c-4531-bfb9-b307e1a14beb] - Request completed
2026-03-26 15:47:10 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:10 - app.access - INFO - [9f2b8df7-2a0b-40b1-9f7b-139747a45c84] - Request started
2026-03-26 15:47:10 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 15:47:10 - app.access - INFO - [9f2b8df7-2a0b-40b1-9f7b-139747a45c84] - Request completed
2026-03-26 15:47:10 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 15:47:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:10 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:10 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:10 - app.access - INFO - [cf98170e-1cb7-46d6-8381-0ba4176f29d8] - Request started
2026-03-26 15:47:10 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=reset-442f1b85@medqc.com roles=doctor trace_id=cf98170e-1cb7-46d6-8381-0ba4176f29d8 details={"assigned_roles": ["doctor"], "department": "测试科室", "target_email": "reset-442f1b85@medqc.com"}
2026-03-26 15:47:10 - app.access - INFO - [cf98170e-1cb7-46d6-8381-0ba4176f29d8] - Request completed
2026-03-26 15:47:10 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 15:47:10 - app.access - INFO - [ade885c8-b9a3-4ef0-8036-a21f6369982b] - Request started
2026-03-26 15:47:10 - app.routers.auth - INFO - [no-trace-id] - auth.forgot_password.issued email=reset-442f1b85@medqc.com
2026-03-26 15:47:10 - app.access - INFO - [ade885c8-b9a3-4ef0-8036-a21f6369982b] - Request completed
2026-03-26 15:47:10 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/forgot-password "HTTP/1.1 200 OK"
2026-03-26 15:47:10 - app.access - INFO - [22643f18-b683-4cae-9cbb-9fb8b592991e] - Request started
2026-03-26 15:47:10 - app.routers.auth - INFO - [no-trace-id] - auth.reset_password.success email=reset-442f1b85@medqc.com
2026-03-26 15:47:10 - app.access - INFO - [22643f18-b683-4cae-9cbb-9fb8b592991e] - Request completed
2026-03-26 15:47:10 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 200 OK"
2026-03-26 15:47:10 - app.access - INFO - [bc920b8e-cae2-4874-95e6-b7bc3694fb9d] - Request started
2026-03-26 15:47:10 - app.main - WARNING - [bc920b8e-cae2-4874-95e6-b7bc3694fb9d] - HTTP Exception: 401 - 重置令牌已使用或失效
2026-03-26 15:47:10 - app.access - WARNING - [bc920b8e-cae2-4874-95e6-b7bc3694fb9d] - Request completed
2026-03-26 15:47:10 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 401 Unauthorized"
2026-03-26 15:47:10 - app.access - INFO - [3eedaf00-6139-4ce8-96cb-a0e93e5b46da] - Request started
2026-03-26 15:47:10 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=reset-442f1b85@medqc.com
2026-03-26 15:47:10 - app.access - INFO - [3eedaf00-6139-4ce8-96cb-a0e93e5b46da] - Request completed
2026-03-26 15:47:10 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:10 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:10 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:11 - app.access - INFO - [6c5e9708-708e-4d94-87cd-36a3d36685c0] - Request started
2026-03-26 15:47:11 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:11 - app.access - INFO - [6c5e9708-708e-4d94-87cd-36a3d36685c0] - Request completed
2026-03-26 15:47:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:11 - app.access - INFO - [56141820-2abc-4cd5-91da-831aab2552a1] - Request started
2026-03-26 15:47:11 - app.main - WARNING - [56141820-2abc-4cd5-91da-831aab2552a1] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/db/config. Please use /api/v1/sync/*
2026-03-26 15:47:11 - app.access - WARNING - [56141820-2abc-4cd5-91da-831aab2552a1] - Request completed
2026-03-26 15:47:11 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/system/db/config "HTTP/1.1 410 Gone"
2026-03-26 15:47:11 - app.access - INFO - [0cd5bfd9-3603-4591-bdbf-793b4b04a909] - Request started
2026-03-26 15:47:11 - app.main - WARNING - [0cd5bfd9-3603-4591-bdbf-793b4b04a909] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/sync/trigger. Please use /api/v1/sync/*
2026-03-26 15:47:11 - app.access - WARNING - [0cd5bfd9-3603-4591-bdbf-793b4b04a909] - Request completed
2026-03-26 15:47:11 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/system/sync/trigger "HTTP/1.1 410 Gone"
2026-03-26 15:47:11 - app.services.etl_sync - INFO - [no-trace-id] - 同步 病案首页 (web.mr)...
2026-03-26 15:47:11 - app.services.etl_sync - INFO - [no-trace-id] -   \u2705 病案首页: 1 条
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:11 - app.access - INFO - [ad00866f-a3e1-4842-9e55-384faddd5e07] - Request started
2026-03-26 15:47:11 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 15:47:11 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 15:47:11 - app.access - INFO - [ad00866f-a3e1-4842-9e55-384faddd5e07] - Request completed
2026-03-26 15:47:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:11 - app.access - INFO - [6ff22a54-8e69-4ee7-9b93-eb26a4d930b7] - Request started
2026-03-26 15:47:11 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:47:11 - app.access - INFO - [6ff22a54-8e69-4ee7-9b93-eb26a4d930b7] - Request completed
2026-03-26 15:47:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:11 - app.access - INFO - [750ebff9-0910-4a63-9b85-5cb61af2ff33] - Request started
2026-03-26 15:47:11 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:47:11 - app.access - INFO - [750ebff9-0910-4a63-9b85-5cb61af2ff33] - Request completed
2026-03-26 15:47:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics/prometheus "HTTP/1.1 200 OK"
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:11 - app.access - INFO - [4b311048-5aef-443b-9ebf-dec5e0ee9d1e] - Request started
2026-03-26 15:47:11 - app.access - INFO - [4b311048-5aef-443b-9ebf-dec5e0ee9d1e] - Request completed
2026-03-26 15:47:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:11 - app.access - INFO - [86f55e0f-e26f-47c2-8c44-c819cfbb316f] - Request started
2026-03-26 15:47:11 - app.access - WARNING - [86f55e0f-e26f-47c2-8c44-c819cfbb316f] - Request completed
2026-03-26 15:47:11 - httpx - INFO - [no-trace-id] - HTTP Request: OPTIONS http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:11 - app.access - INFO - [2fdd8b45-d52d-4841-85d0-fa2c424201c3] - Request started
2026-03-26 15:47:11 - app.access - INFO - [2fdd8b45-d52d-4841-85d0-fa2c424201c3] - Request completed
2026-03-26 15:47:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:11 - app.access - INFO - [39da0330-248f-4855-b5af-a81c88229d09] - Request started
2026-03-26 15:47:11 - app.access - INFO - [39da0330-248f-4855-b5af-a81c88229d09] - Request completed
2026-03-26 15:47:11 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:11 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:11 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [9cd48683-5e1d-40d5-aa05-885dc8145ecf] - Request started
2026-03-26 15:47:12 - app.access - INFO - [9cd48683-5e1d-40d5-aa05-885dc8145ecf] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [0ae3632b-2228-4535-9d3f-daed2ce66566] - Request started
2026-03-26 15:47:12 - app.access - INFO - [0ae3632b-2228-4535-9d3f-daed2ce66566] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [7680178c-6047-4532-b4ba-04f943aad8ba] - Request started
2026-03-26 15:47:12 - app.access - INFO - [7680178c-6047-4532-b4ba-04f943aad8ba] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [e243432d-0208-48f8-b6c9-312bfa4ddf23] - Request started
2026-03-26 15:47:12 - app.access - INFO - [e243432d-0208-48f8-b6c9-312bfa4ddf23] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [916a217c-1fb8-4814-aff3-60431027f54d] - Request started
2026-03-26 15:47:12 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:47:12 - app.access - INFO - [916a217c-1fb8-4814-aff3-60431027f54d] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [c21196c4-25a4-468a-b908-f299447b7e5c] - Request started
2026-03-26 15:47:12 - app.access - WARNING - [c21196c4-25a4-468a-b908-f299447b7e5c] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/nonexistent "HTTP/1.1 404 Not Found"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [ba4c4c44-7baa-4437-972d-3bbc2c28a34d] - Request started
2026-03-26 15:47:12 - app.access - WARNING - [ba4c4c44-7baa-4437-972d-3bbc2c28a34d] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [d8abb79d-b321-4b3c-8f36-073bc710cd14] - Request started
2026-03-26 15:47:12 - app.access - INFO - [3bacbd4b-fbf3-4bb2-800b-4e3a94b2e6f1] - Request started
2026-03-26 15:47:12 - app.access - INFO - [7bb4d9fb-8358-4306-9a56-f6e51fb061e0] - Request started
2026-03-26 15:47:12 - app.access - INFO - [fec87cba-5d51-4189-a554-21f467a5fa25] - Request started
2026-03-26 15:47:12 - app.access - INFO - [defe9c75-3a2e-4b5d-abd8-24b0b5004996] - Request started
2026-03-26 15:47:12 - app.access - INFO - [77337169-35b8-495a-baf5-4fc2e90ac680] - Request started
2026-03-26 15:47:12 - app.access - INFO - [862640c5-680c-41d7-bd49-65a4ec3e6dae] - Request started
2026-03-26 15:47:12 - app.access - INFO - [36bc5c40-20f1-4ab4-bd76-8d540fe1d221] - Request started
2026-03-26 15:47:12 - app.access - INFO - [fa8e85f6-344b-44a6-a019-ca05e343d61d] - Request started
2026-03-26 15:47:12 - app.access - INFO - [6a230577-2d68-4cde-8e7f-c87b96e2e893] - Request started
2026-03-26 15:47:12 - app.access - INFO - [d8abb79d-b321-4b3c-8f36-073bc710cd14] - Request completed
2026-03-26 15:47:12 - app.access - INFO - [3bacbd4b-fbf3-4bb2-800b-4e3a94b2e6f1] - Request completed
2026-03-26 15:47:12 - app.access - INFO - [7bb4d9fb-8358-4306-9a56-f6e51fb061e0] - Request completed
2026-03-26 15:47:12 - app.access - INFO - [fec87cba-5d51-4189-a554-21f467a5fa25] - Request completed
2026-03-26 15:47:12 - app.access - INFO - [defe9c75-3a2e-4b5d-abd8-24b0b5004996] - Request completed
2026-03-26 15:47:12 - app.access - INFO - [77337169-35b8-495a-baf5-4fc2e90ac680] - Request completed
2026-03-26 15:47:12 - app.access - INFO - [862640c5-680c-41d7-bd49-65a4ec3e6dae] - Request completed
2026-03-26 15:47:12 - app.access - INFO - [36bc5c40-20f1-4ab4-bd76-8d540fe1d221] - Request completed
2026-03-26 15:47:12 - app.access - INFO - [fa8e85f6-344b-44a6-a019-ca05e343d61d] - Request completed
2026-03-26 15:47:12 - app.access - INFO - [6a230577-2d68-4cde-8e7f-c87b96e2e893] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [db0c2af3-3324-4c41-a2f4-62ba2e75fc53] - Request started
2026-03-26 15:47:12 - app.access - INFO - [db0c2af3-3324-4c41-a2f4-62ba2e75fc53] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [b4a0b728-ad6e-4263-8eb8-bcf3def82e08] - Request started
2026-03-26 15:47:12 - app.access - INFO - [b4a0b728-ad6e-4263-8eb8-bcf3def82e08] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [195b61e1-be8a-490c-9294-fed87029779e] - Request started
2026-03-26 15:47:12 - app.access - INFO - [195b61e1-be8a-490c-9294-fed87029779e] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [c3e49132-f37f-4f9d-8ac9-5e80f2a1c1db] - Request started
2026-03-26 15:47:12 - app.access - INFO - [c3e49132-f37f-4f9d-8ac9-5e80f2a1c1db] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health?test=1&test=2 "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:12 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:12 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:12 - app.access - INFO - [8862953a-8306-433b-b313-50142747cffb] - Request started
2026-03-26 15:47:12 - app.access - INFO - [8862953a-8306-433b-b313-50142747cffb] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [c4afb854-27a1-4b9e-82cd-d489e22da692] - Request started
2026-03-26 15:47:12 - app.access - INFO - [c4afb854-27a1-4b9e-82cd-d489e22da692] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [0173bd2d-9cb5-463b-8f8b-9db7d9687d80] - Request started
2026-03-26 15:47:12 - app.access - INFO - [0173bd2d-9cb5-463b-8f8b-9db7d9687d80] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [e62aa90e-3d9e-4406-83c6-059439819faf] - Request started
2026-03-26 15:47:12 - app.access - INFO - [e62aa90e-3d9e-4406-83c6-059439819faf] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [10e9a3d1-1d9f-4853-b0e6-011460c38f0a] - Request started
2026-03-26 15:47:12 - app.access - INFO - [10e9a3d1-1d9f-4853-b0e6-011460c38f0a] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [1cd662f3-234d-49eb-9153-d84ca9cb7beb] - Request started
2026-03-26 15:47:12 - app.access - INFO - [1cd662f3-234d-49eb-9153-d84ca9cb7beb] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [285b6813-45a4-4d7e-a0a6-79edcdbc31a7] - Request started
2026-03-26 15:47:12 - app.access - INFO - [285b6813-45a4-4d7e-a0a6-79edcdbc31a7] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [2ab936ac-0e46-47a7-ab89-085b2b5599f6] - Request started
2026-03-26 15:47:12 - app.access - INFO - [2ab936ac-0e46-47a7-ab89-085b2b5599f6] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [62e0f7d5-e264-4eba-95c4-988ca3de7bc9] - Request started
2026-03-26 15:47:12 - app.access - INFO - [62e0f7d5-e264-4eba-95c4-988ca3de7bc9] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [4ccb90d8-ca69-47a2-b8a1-f7cdd7cbb810] - Request started
2026-03-26 15:47:12 - app.access - INFO - [4ccb90d8-ca69-47a2-b8a1-f7cdd7cbb810] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [24111970-aec7-4fd8-96e2-c89779d67be8] - Request started
2026-03-26 15:47:12 - app.access - INFO - [24111970-aec7-4fd8-96e2-c89779d67be8] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [e7fda974-d976-475e-a19d-e4f01725dd9e] - Request started
2026-03-26 15:47:12 - app.access - INFO - [e7fda974-d976-475e-a19d-e4f01725dd9e] - Request completed
2026-03-26 15:47:12 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:12 - app.access - INFO - [983d881c-e985-4bbe-86a8-7aa01137a798] - Request started
2026-03-26 15:47:13 - app.access - INFO - [983d881c-e985-4bbe-86a8-7aa01137a798] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [5db453bc-5eb3-493f-ade8-5dd189f7aec5] - Request started
2026-03-26 15:47:13 - app.access - INFO - [5db453bc-5eb3-493f-ade8-5dd189f7aec5] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [11801d4d-42f0-4c90-83e7-adbb0845dd2e] - Request started
2026-03-26 15:47:13 - app.access - INFO - [11801d4d-42f0-4c90-83e7-adbb0845dd2e] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [3af47520-8bc4-4090-a99f-02e7eefddd41] - Request started
2026-03-26 15:47:13 - app.access - INFO - [3af47520-8bc4-4090-a99f-02e7eefddd41] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [37decdc4-8796-4f0e-9f8a-4444a739997b] - Request started
2026-03-26 15:47:13 - app.access - INFO - [37decdc4-8796-4f0e-9f8a-4444a739997b] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [cf232f8d-b359-4394-992e-9e05eee4eec7] - Request started
2026-03-26 15:47:13 - app.access - INFO - [cf232f8d-b359-4394-992e-9e05eee4eec7] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [4157a75b-91ed-4192-b673-e0612c8e6c76] - Request started
2026-03-26 15:47:13 - app.access - INFO - [4157a75b-91ed-4192-b673-e0612c8e6c76] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [a9661169-d1ae-47df-9de1-437544673c33] - Request started
2026-03-26 15:47:13 - app.access - INFO - [a9661169-d1ae-47df-9de1-437544673c33] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [e6d3e659-e423-4237-ac2c-5f3c03e0a914] - Request started
2026-03-26 15:47:13 - app.access - INFO - [e6d3e659-e423-4237-ac2c-5f3c03e0a914] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [f52a0818-f57f-4c36-b5dc-956934648a49] - Request started
2026-03-26 15:47:13 - app.access - INFO - [f52a0818-f57f-4c36-b5dc-956934648a49] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [009e04f6-9f57-451c-bb0f-1901f8e1e0ca] - Request started
2026-03-26 15:47:13 - app.access - INFO - [009e04f6-9f57-451c-bb0f-1901f8e1e0ca] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [9a0cc8c3-a682-4163-9e59-42959a43e6bf] - Request started
2026-03-26 15:47:13 - app.access - INFO - [9a0cc8c3-a682-4163-9e59-42959a43e6bf] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [c425170c-8bbc-49a0-8af6-aa49ed7d7b20] - Request started
2026-03-26 15:47:13 - app.access - INFO - [c425170c-8bbc-49a0-8af6-aa49ed7d7b20] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [53c1d57a-d12b-4d7d-a0ee-2a21d0e951d4] - Request started
2026-03-26 15:47:13 - app.access - INFO - [53c1d57a-d12b-4d7d-a0ee-2a21d0e951d4] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [a709ab3f-c6e8-4eed-af98-e6e53c93649d] - Request started
2026-03-26 15:47:13 - app.access - INFO - [a709ab3f-c6e8-4eed-af98-e6e53c93649d] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [318e79e9-d0a5-400e-a784-906a4fbd996d] - Request started
2026-03-26 15:47:13 - app.access - INFO - [318e79e9-d0a5-400e-a784-906a4fbd996d] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [62afeb4d-5eaa-41bc-be35-fed5ca860cab] - Request started
2026-03-26 15:47:13 - app.access - INFO - [62afeb4d-5eaa-41bc-be35-fed5ca860cab] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [b7db8790-a297-412d-9ba5-79804ae4226b] - Request started
2026-03-26 15:47:13 - app.access - INFO - [b7db8790-a297-412d-9ba5-79804ae4226b] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [0516e711-95b8-48e1-8e9e-3972abc09a85] - Request started
2026-03-26 15:47:13 - app.access - INFO - [0516e711-95b8-48e1-8e9e-3972abc09a85] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [7669aee7-ed21-4177-9bf5-6464f3ea4e87] - Request started
2026-03-26 15:47:13 - app.access - INFO - [7669aee7-ed21-4177-9bf5-6464f3ea4e87] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [0977a0c4-1212-4297-85d6-351f16a814be] - Request started
2026-03-26 15:47:13 - app.access - INFO - [0977a0c4-1212-4297-85d6-351f16a814be] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [863b6cc5-f6f6-4bd3-a32e-7d780550eca5] - Request started
2026-03-26 15:47:13 - app.access - INFO - [863b6cc5-f6f6-4bd3-a32e-7d780550eca5] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [e64839bc-23e8-4bd7-a5ab-19aadc301cd2] - Request started
2026-03-26 15:47:13 - app.access - INFO - [e64839bc-23e8-4bd7-a5ab-19aadc301cd2] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [89b18666-6a83-4308-b58f-9c647b2da2d3] - Request started
2026-03-26 15:47:13 - app.access - INFO - [89b18666-6a83-4308-b58f-9c647b2da2d3] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [8dc8bc85-2a54-4f75-b75b-58a38714e6d7] - Request started
2026-03-26 15:47:13 - app.access - INFO - [8dc8bc85-2a54-4f75-b75b-58a38714e6d7] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [9ea4c71c-c501-469e-b8a5-107d30b2e5ca] - Request started
2026-03-26 15:47:13 - app.access - INFO - [9ea4c71c-c501-469e-b8a5-107d30b2e5ca] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [49329ff4-24db-48d1-a911-6cb651adeb26] - Request started
2026-03-26 15:47:13 - app.access - INFO - [49329ff4-24db-48d1-a911-6cb651adeb26] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [6bc29894-b359-402f-b22e-fe4455c493d7] - Request started
2026-03-26 15:47:13 - app.access - INFO - [6bc29894-b359-402f-b22e-fe4455c493d7] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [2b01d385-ebf7-4aa0-aef3-f7deb16a720c] - Request started
2026-03-26 15:47:13 - app.access - INFO - [2b01d385-ebf7-4aa0-aef3-f7deb16a720c] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [55c3fed8-7f38-4e83-8d2c-62d80c82b44c] - Request started
2026-03-26 15:47:13 - app.access - INFO - [55c3fed8-7f38-4e83-8d2c-62d80c82b44c] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [0ba651da-9c1c-4699-a697-9cdd833048d5] - Request started
2026-03-26 15:47:13 - app.access - INFO - [0ba651da-9c1c-4699-a697-9cdd833048d5] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [e189f3d9-431f-4359-8216-391b5c06f00d] - Request started
2026-03-26 15:47:13 - app.access - INFO - [e189f3d9-431f-4359-8216-391b5c06f00d] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [297bb11a-5036-49d5-9403-91e3f0562777] - Request started
2026-03-26 15:47:13 - app.access - INFO - [297bb11a-5036-49d5-9403-91e3f0562777] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [8ef383b5-00e9-4231-9055-c611feea3213] - Request started
2026-03-26 15:47:13 - app.access - INFO - [8ef383b5-00e9-4231-9055-c611feea3213] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [917d0061-dec9-4989-8bef-2f9475c41eb1] - Request started
2026-03-26 15:47:13 - app.access - INFO - [917d0061-dec9-4989-8bef-2f9475c41eb1] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [27bf7314-6a47-444e-8136-d05773598fac] - Request started
2026-03-26 15:47:13 - app.access - INFO - [27bf7314-6a47-444e-8136-d05773598fac] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [93920b6a-8342-4948-8377-e2cd1a55cdc1] - Request started
2026-03-26 15:47:13 - app.access - INFO - [93920b6a-8342-4948-8377-e2cd1a55cdc1] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [20dad7cd-5666-45e3-8c3c-44fefaefd427] - Request started
2026-03-26 15:47:13 - app.access - INFO - [20dad7cd-5666-45e3-8c3c-44fefaefd427] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [952eee02-1221-4ce3-b281-e6311a166621] - Request started
2026-03-26 15:47:13 - app.access - INFO - [952eee02-1221-4ce3-b281-e6311a166621] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [2da7eab9-bb11-4ca4-943b-528a82a30a65] - Request started
2026-03-26 15:47:13 - app.access - INFO - [2da7eab9-bb11-4ca4-943b-528a82a30a65] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [b076d40f-fed7-4e13-9283-e40cb5de1136] - Request started
2026-03-26 15:47:13 - app.access - INFO - [b076d40f-fed7-4e13-9283-e40cb5de1136] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [f943e443-734d-49dd-81cd-7018546879d1] - Request started
2026-03-26 15:47:13 - app.access - INFO - [f943e443-734d-49dd-81cd-7018546879d1] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [43ee9cd2-96b5-404e-b9f9-f251e231e68e] - Request started
2026-03-26 15:47:13 - app.access - INFO - [43ee9cd2-96b5-404e-b9f9-f251e231e68e] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [bf7eddae-7026-4df0-96bb-ee6dc0b32512] - Request started
2026-03-26 15:47:13 - app.access - INFO - [bf7eddae-7026-4df0-96bb-ee6dc0b32512] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [7d86f142-3edb-4c9d-a165-1a56186b2f86] - Request started
2026-03-26 15:47:13 - app.access - INFO - [7d86f142-3edb-4c9d-a165-1a56186b2f86] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [c24345b0-00b6-4150-82b1-ddfc38d624e7] - Request started
2026-03-26 15:47:13 - app.access - INFO - [c24345b0-00b6-4150-82b1-ddfc38d624e7] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [23b9031d-b951-4dd8-be71-9d992d5dcedf] - Request started
2026-03-26 15:47:13 - app.access - INFO - [23b9031d-b951-4dd8-be71-9d992d5dcedf] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [6f57564d-2d36-4821-ae65-3f3b5351d48a] - Request started
2026-03-26 15:47:13 - app.access - INFO - [6f57564d-2d36-4821-ae65-3f3b5351d48a] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [a79b279b-0ced-469b-9ecf-23d42dc960e1] - Request started
2026-03-26 15:47:13 - app.access - INFO - [a79b279b-0ced-469b-9ecf-23d42dc960e1] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [e0c227b3-3597-4b8a-8938-7d9ce46b905a] - Request started
2026-03-26 15:47:13 - app.access - INFO - [e0c227b3-3597-4b8a-8938-7d9ce46b905a] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [28ba4ed1-ce45-49aa-8b29-e7b4d61fbdf6] - Request started
2026-03-26 15:47:13 - app.access - INFO - [28ba4ed1-ce45-49aa-8b29-e7b4d61fbdf6] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [c76e78a2-c320-4944-ab48-220ee407cdea] - Request started
2026-03-26 15:47:13 - app.access - INFO - [c76e78a2-c320-4944-ab48-220ee407cdea] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [8cb84814-03e7-4d94-b222-05af28a0994f] - Request started
2026-03-26 15:47:13 - app.access - INFO - [8cb84814-03e7-4d94-b222-05af28a0994f] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [7781f064-4918-43c8-bebd-a90bd63b9002] - Request started
2026-03-26 15:47:13 - app.access - INFO - [7781f064-4918-43c8-bebd-a90bd63b9002] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [e8b1e7e9-e82c-4511-a8b5-b88b71f5a301] - Request started
2026-03-26 15:47:13 - app.access - INFO - [e8b1e7e9-e82c-4511-a8b5-b88b71f5a301] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [e48b8ffb-ddf9-4f17-9947-27420a65583a] - Request started
2026-03-26 15:47:13 - app.access - INFO - [e48b8ffb-ddf9-4f17-9947-27420a65583a] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [c05cc651-c04f-4641-944b-bc3586e217b2] - Request started
2026-03-26 15:47:13 - app.access - INFO - [c05cc651-c04f-4641-944b-bc3586e217b2] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [d17dec3b-8de4-47b6-912b-a31b59a48155] - Request started
2026-03-26 15:47:13 - app.access - INFO - [d17dec3b-8de4-47b6-912b-a31b59a48155] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [eb6a42be-b040-4ed4-b724-9575077e866b] - Request started
2026-03-26 15:47:13 - app.access - INFO - [eb6a42be-b040-4ed4-b724-9575077e866b] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [0478291d-0b0b-428f-8622-79e11a80fa43] - Request started
2026-03-26 15:47:13 - app.access - INFO - [0478291d-0b0b-428f-8622-79e11a80fa43] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [8b4d2b57-7b3a-4eef-8ea3-b947231c61f2] - Request started
2026-03-26 15:47:13 - app.access - INFO - [8b4d2b57-7b3a-4eef-8ea3-b947231c61f2] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [ad89e5a8-b5fa-4272-9910-30701aedfe6f] - Request started
2026-03-26 15:47:13 - app.access - INFO - [ad89e5a8-b5fa-4272-9910-30701aedfe6f] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [67925158-c95e-4fc7-aa0b-e27b21e5cc7c] - Request started
2026-03-26 15:47:13 - app.access - INFO - [67925158-c95e-4fc7-aa0b-e27b21e5cc7c] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [ae4f177b-98b3-459b-b80b-0e7a81f3e009] - Request started
2026-03-26 15:47:13 - app.access - INFO - [ae4f177b-98b3-459b-b80b-0e7a81f3e009] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [796e5330-c2c3-4709-b3a0-79f459cc0765] - Request started
2026-03-26 15:47:13 - app.access - INFO - [796e5330-c2c3-4709-b3a0-79f459cc0765] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [70cad744-d545-4d08-ae6b-8d841d9ad268] - Request started
2026-03-26 15:47:13 - app.access - INFO - [70cad744-d545-4d08-ae6b-8d841d9ad268] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [c581b91c-faa6-4877-8d1d-85e35db363a2] - Request started
2026-03-26 15:47:13 - app.access - INFO - [c581b91c-faa6-4877-8d1d-85e35db363a2] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [096f1ef4-3878-4ef6-b27d-a19d8ddd6774] - Request started
2026-03-26 15:47:13 - app.access - INFO - [096f1ef4-3878-4ef6-b27d-a19d8ddd6774] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [fb1e5703-9c80-4124-9a29-0126f9c52ab6] - Request started
2026-03-26 15:47:13 - app.access - INFO - [fb1e5703-9c80-4124-9a29-0126f9c52ab6] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [8ba8f4cc-9b54-475b-ac3e-e3be0e68069c] - Request started
2026-03-26 15:47:13 - app.access - INFO - [8ba8f4cc-9b54-475b-ac3e-e3be0e68069c] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [4057637c-0bc4-4dd0-bd14-88ef5abdc8a5] - Request started
2026-03-26 15:47:13 - app.access - INFO - [4057637c-0bc4-4dd0-bd14-88ef5abdc8a5] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [b187b5f5-a81b-48c5-a6d7-b3f617b58956] - Request started
2026-03-26 15:47:13 - app.access - INFO - [b187b5f5-a81b-48c5-a6d7-b3f617b58956] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [3f03cad5-1dbd-45ea-8df9-419c2021547b] - Request started
2026-03-26 15:47:13 - app.access - INFO - [3f03cad5-1dbd-45ea-8df9-419c2021547b] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [6ddc2233-1ea9-4feb-85ed-3d8160f224e2] - Request started
2026-03-26 15:47:13 - app.access - INFO - [6ddc2233-1ea9-4feb-85ed-3d8160f224e2] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [0d4139c0-9048-4b87-ac14-5078cc845afe] - Request started
2026-03-26 15:47:13 - app.access - INFO - [0d4139c0-9048-4b87-ac14-5078cc845afe] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [df1a07aa-97a7-4ac6-b820-1c13902378b0] - Request started
2026-03-26 15:47:13 - app.access - INFO - [df1a07aa-97a7-4ac6-b820-1c13902378b0] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [dcf4975a-4d0a-4c6f-94f1-3e7d7edbbfa3] - Request started
2026-03-26 15:47:13 - app.access - INFO - [dcf4975a-4d0a-4c6f-94f1-3e7d7edbbfa3] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [7a8e80d5-f4ec-49f2-800d-770cb1e0194d] - Request started
2026-03-26 15:47:13 - app.access - INFO - [7a8e80d5-f4ec-49f2-800d-770cb1e0194d] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [23558041-bd62-46e1-b9fa-a9a489e10bc9] - Request started
2026-03-26 15:47:13 - app.access - INFO - [23558041-bd62-46e1-b9fa-a9a489e10bc9] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [1134602d-85b6-4615-8e38-36f9bb599fff] - Request started
2026-03-26 15:47:13 - app.access - INFO - [1134602d-85b6-4615-8e38-36f9bb599fff] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [e22bb3e7-0b29-4f51-9970-c3dcaf008ad0] - Request started
2026-03-26 15:47:13 - app.access - INFO - [e22bb3e7-0b29-4f51-9970-c3dcaf008ad0] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [c949b04e-2cef-4d04-b174-cebe75aee83e] - Request started
2026-03-26 15:47:13 - app.access - INFO - [c949b04e-2cef-4d04-b174-cebe75aee83e] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [8aa423b0-ca6d-4d83-ad84-aec9ea12d359] - Request started
2026-03-26 15:47:13 - app.access - INFO - [8aa423b0-ca6d-4d83-ad84-aec9ea12d359] - Request completed
2026-03-26 15:47:13 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:13 - app.access - INFO - [f59ec0e8-a11f-482b-8ae5-f3824b4e0447] - Request started
2026-03-26 15:47:14 - app.access - INFO - [f59ec0e8-a11f-482b-8ae5-f3824b4e0447] - Request completed
2026-03-26 15:47:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:14 - app.access - INFO - [6f4f5984-8c00-4eb6-ae55-e0a1f0faa971] - Request started
2026-03-26 15:47:14 - app.access - INFO - [6f4f5984-8c00-4eb6-ae55-e0a1f0faa971] - Request completed
2026-03-26 15:47:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:14 - app.access - INFO - [5e5290c9-c443-42e5-bfd7-87f6d0f1b3c0] - Request started
2026-03-26 15:47:14 - app.access - INFO - [5e5290c9-c443-42e5-bfd7-87f6d0f1b3c0] - Request completed
2026-03-26 15:47:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:14 - app.access - INFO - [7397fce0-a2d6-4508-b40f-45eb0f6f92d2] - Request started
2026-03-26 15:47:14 - app.access - INFO - [7397fce0-a2d6-4508-b40f-45eb0f6f92d2] - Request completed
2026-03-26 15:47:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:14 - app.access - INFO - [464d46e2-93f0-4402-8420-d7c52330fed8] - Request started
2026-03-26 15:47:14 - app.access - INFO - [464d46e2-93f0-4402-8420-d7c52330fed8] - Request completed
2026-03-26 15:47:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:14 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:14 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:14 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:14 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:14 - app.access - INFO - [de6b2762-0848-4d8c-bfd0-5bb5cb5fbc42] - Request started
2026-03-26 15:47:14 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:14 - app.access - INFO - [de6b2762-0848-4d8c-bfd0-5bb5cb5fbc42] - Request completed
2026-03-26 15:47:14 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:14 - app.access - INFO - [74f8e059-3000-416a-9cdb-ee5bce140397] - Request started
2026-03-26 15:47:14 - app.core.permissions - INFO - [no-trace-id] - 权限允许: 用户 admin@medqc.com 执行 update 操作在 medical_records 资源上
2026-03-26 15:47:14 - app.access - INFO - [74f8e059-3000-416a-9cdb-ee5bce140397] - Request completed
2026-03-26 15:47:14 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/tasks/task-1/assign "HTTP/1.1 200 OK"
2026-03-26 15:47:14 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:14 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:14 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:14 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:14 - app.access - INFO - [a4fbfce6-08f2-4648-85c4-6c4b7783d384] - Request started
2026-03-26 15:47:14 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:14 - app.access - INFO - [a4fbfce6-08f2-4648-85c4-6c4b7783d384] - Request completed
2026-03-26 15:47:14 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:14 - app.access - INFO - [2eeef7c4-5c98-464f-838d-96cba0db31a7] - Request started
2026-03-26 15:47:14 - app.access - INFO - [2eeef7c4-5c98-464f-838d-96cba0db31a7] - Request completed
2026-03-26 15:47:14 - httpx - INFO - [no-trace-id] - HTTP Request: DELETE http://testserver/api/v1/tasks/task-del-1 "HTTP/1.1 200 OK"
2026-03-26 15:47:14 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:14 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:14 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:14 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:14 - app.access - INFO - [80a61c95-5a29-4931-80f2-2aabc542bfe0] - Request started
2026-03-26 15:47:15 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:15 - app.access - INFO - [80a61c95-5a29-4931-80f2-2aabc542bfe0] - Request completed
2026-03-26 15:47:15 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:15 - app.access - INFO - [dcc82c6a-cba8-40e7-bab2-8d00ecff447a] - Request started
2026-03-26 15:47:15 - app.main - WARNING - [dcc82c6a-cba8-40e7-bab2-8d00ecff447a] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 15:47:15 - app.access - WARNING - [dcc82c6a-cba8-40e7-bab2-8d00ecff447a] - Request completed
2026-03-26 15:47:15 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/parse-medical-file-public "HTTP/1.1 429 Too Many Requests"
2026-03-26 15:47:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:15 - app.access - INFO - [c4357985-b244-46f0-814b-f832153312cf] - Request started
2026-03-26 15:47:15 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:15 - app.access - INFO - [c4357985-b244-46f0-814b-f832153312cf] - Request completed
2026-03-26 15:47:15 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:15 - app.access - INFO - [be37ef60-f203-4f03-a48a-15c35b765bd9] - Request started
2026-03-26 15:47:15 - app.main - WARNING - [be37ef60-f203-4f03-a48a-15c35b765bd9] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 15:47:15 - app.access - WARNING - [be37ef60-f203-4f03-a48a-15c35b765bd9] - Request completed
2026-03-26 15:47:15 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/batch-upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 15:47:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:15 - app.access - INFO - [e38309ff-3f36-4f28-97e1-16e488793771] - Request started
2026-03-26 15:47:15 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:15 - app.access - INFO - [e38309ff-3f36-4f28-97e1-16e488793771] - Request completed
2026-03-26 15:47:15 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:15 - app.access - INFO - [bf42b8d0-c7b9-4a70-89d8-54305f40c18e] - Request started
2026-03-26 15:47:15 - app.main - WARNING - [bf42b8d0-c7b9-4a70-89d8-54305f40c18e] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 15:47:15 - app.access - WARNING - [bf42b8d0-c7b9-4a70-89d8-54305f40c18e] - Request completed
2026-03-26 15:47:15 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/records/upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 15:47:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:15 - app.access - INFO - [e5ba585c-ccca-4f23-b8cf-72cc1e0a3f3b] - Request started
2026-03-26 15:47:16 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:16 - app.access - INFO - [e5ba585c-ccca-4f23-b8cf-72cc1e0a3f3b] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:16 - app.access - INFO - [a56b64ec-ce7b-46fd-8b08-d6dc36891172] - Request started
2026-03-26 15:47:16 - app.main - WARNING - [a56b64ec-ce7b-46fd-8b08-d6dc36891172] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:47:16 - app.access - WARNING - [a56b64ec-ce7b-46fd-8b08-d6dc36891172] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.access - INFO - [f3bb0320-9c60-41ac-a47e-d6fe953fa2e9] - Request started
2026-03-26 15:47:16 - app.main - WARNING - [f3bb0320-9c60-41ac-a47e-d6fe953fa2e9] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:47:16 - app.access - WARNING - [f3bb0320-9c60-41ac-a47e-d6fe953fa2e9] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.access - INFO - [8a0981d6-67bd-4839-b7cf-48fe751033f0] - Request started
2026-03-26 15:47:16 - app.main - WARNING - [8a0981d6-67bd-4839-b7cf-48fe751033f0] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:47:16 - app.access - WARNING - [8a0981d6-67bd-4839-b7cf-48fe751033f0] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.access - INFO - [d50b22ea-a7cc-490f-9c9a-b38037bb7fc9] - Request started
2026-03-26 15:47:16 - app.main - WARNING - [d50b22ea-a7cc-490f-9c9a-b38037bb7fc9] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:47:16 - app.access - WARNING - [d50b22ea-a7cc-490f-9c9a-b38037bb7fc9] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.access - INFO - [1a8a6385-b6cc-4d6e-860c-bdae8d0ee33f] - Request started
2026-03-26 15:47:16 - app.main - WARNING - [1a8a6385-b6cc-4d6e-860c-bdae8d0ee33f] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:47:16 - app.access - WARNING - [1a8a6385-b6cc-4d6e-860c-bdae8d0ee33f] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.access - INFO - [502b180c-31c3-4df2-8880-fed729e4bdbb] - Request started
2026-03-26 15:47:16 - app.main - WARNING - [502b180c-31c3-4df2-8880-fed729e4bdbb] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:47:16 - app.access - WARNING - [502b180c-31c3-4df2-8880-fed729e4bdbb] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.access - INFO - [a1c5f0c0-b077-452a-b474-44f899f9a850] - Request started
2026-03-26 15:47:16 - app.main - WARNING - [a1c5f0c0-b077-452a-b474-44f899f9a850] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:47:16 - app.access - WARNING - [a1c5f0c0-b077-452a-b474-44f899f9a850] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.access - INFO - [a0ecf41d-8d33-45c2-a12d-9771aa8eb925] - Request started
2026-03-26 15:47:16 - app.main - WARNING - [a0ecf41d-8d33-45c2-a12d-9771aa8eb925] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:47:16 - app.access - WARNING - [a0ecf41d-8d33-45c2-a12d-9771aa8eb925] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.access - INFO - [bfa07e47-99c5-4edb-bc9f-eb95d60acc4e] - Request started
2026-03-26 15:47:16 - app.main - WARNING - [bfa07e47-99c5-4edb-bc9f-eb95d60acc4e] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:47:16 - app.access - WARNING - [bfa07e47-99c5-4edb-bc9f-eb95d60acc4e] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.access - INFO - [87b27a12-1249-4477-97b2-26f7c8eceb46] - Request started
2026-03-26 15:47:16 - app.main - WARNING - [87b27a12-1249-4477-97b2-26f7c8eceb46] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:47:16 - app.access - WARNING - [87b27a12-1249-4477-97b2-26f7c8eceb46] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.access - INFO - [ac7fbebd-6f17-43bc-a0d7-e799a3b94f35] - Request started
2026-03-26 15:47:16 - app.core.rate_limit - WARNING - [ac7fbebd-6f17-43bc-a0d7-e799a3b94f35] - audit.rate_limit.exceeded bucket=drg_smart_upload key=drg_smart_upload:testclient method=POST path=/api/v1/drg/smart-upload
2026-03-26 15:47:16 - app.main - WARNING - [ac7fbebd-6f17-43bc-a0d7-e799a3b94f35] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 15:47:16 - app.access - WARNING - [ac7fbebd-6f17-43bc-a0d7-e799a3b94f35] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 15:47:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:16 - app.access - INFO - [77ec0077-09dc-4f56-9c19-55ceabf64e04] - Request started
2026-03-26 15:47:16 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:16 - app.access - INFO - [77ec0077-09dc-4f56-9c19-55ceabf64e04] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:16 - app.access - INFO - [610deeb8-833d-45f8-b44c-7c35471385a7] - Request started
2026-03-26 15:47:16 - app.core.upload_security - WARNING - [610deeb8-833d-45f8-b44c-7c35471385a7] - audit.upload.rejected reason=extension_not_allowed filename=malicious.exe content_type=application/octet-stream size_bytes=4
2026-03-26 15:47:16 - app.main - WARNING - [610deeb8-833d-45f8-b44c-7c35471385a7] - HTTP Exception: 400 - 不支持的文件扩展名: .exe
2026-03-26 15:47:16 - app.access - WARNING - [610deeb8-833d-45f8-b44c-7c35471385a7] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/parse-medical-file-public "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:16 - app.access - INFO - [792aaf9e-6d5c-4da2-9829-ca41af0451d2] - Request started
2026-03-26 15:47:16 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:16 - app.access - INFO - [792aaf9e-6d5c-4da2-9829-ca41af0451d2] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:16 - app.access - INFO - [48000049-9e3c-4d8a-ada2-a86a2d375390] - Request started
2026-03-26 15:47:16 - app.core.upload_security - WARNING - [48000049-9e3c-4d8a-ada2-a86a2d375390] - audit.upload.rejected reason=virus_scan_blocked filename=record.txt content_type=text/plain size_bytes=68
2026-03-26 15:47:16 - app.main - WARNING - [48000049-9e3c-4d8a-ada2-a86a2d375390] - HTTP Exception: 400 - 检测到潜在恶意文件签名
2026-03-26 15:47:16 - app.access - WARNING - [48000049-9e3c-4d8a-ada2-a86a2d375390] - Request completed
2026-03-26 15:47:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/records/upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:16 - app.access - INFO - [8890cfab-b82c-443b-b47a-b979b8310f5e] - Request started
2026-03-26 15:47:17 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:17 - app.access - INFO - [8890cfab-b82c-443b-b47a-b979b8310f5e] - Request completed
2026-03-26 15:47:17 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:17 - app.access - INFO - [52886383-8d0d-403b-ac19-7e81f2e3fdb6] - Request started
2026-03-26 15:47:17 - app.core.upload_security - WARNING - [52886383-8d0d-403b-ac19-7e81f2e3fdb6] - audit.upload.rejected reason=mime_not_allowed filename=sample.csv content_type=image/png size_bytes=81
2026-03-26 15:47:17 - app.main - WARNING - [52886383-8d0d-403b-ac19-7e81f2e3fdb6] - HTTP Exception: 400 - 不支持的文件类型: image/png
2026-03-26 15:47:17 - app.access - WARNING - [52886383-8d0d-403b-ac19-7e81f2e3fdb6] - Request completed
2026-03-26 15:47:17 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/batch-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:17 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:47:17 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:47:17 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:47:17 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:47:17 - app.access - INFO - [6db4978d-e774-4ad3-af6a-a0d7d4bc4829] - Request started
2026-03-26 15:47:17 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:17 - app.access - INFO - [6db4978d-e774-4ad3-af6a-a0d7d4bc4829] - Request completed
2026-03-26 15:47:17 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:17 - app.access - INFO - [cc3c03d3-d103-4b30-8ecd-fdb78be12fb4] - Request started
2026-03-26 15:47:17 - app.core.upload_security - WARNING - [cc3c03d3-d103-4b30-8ecd-fdb78be12fb4] - audit.upload.rejected reason=file_too_large filename=sample.csv content_type=text/csv size_bytes=10
2026-03-26 15:47:17 - app.main - WARNING - [cc3c03d3-d103-4b30-8ecd-fdb78be12fb4] - HTTP Exception: 400 - 文件大小不能超过 8B
2026-03-26 15:47:17 - app.access - WARNING - [cc3c03d3-d103-4b30-8ecd-fdb78be12fb4] - Request completed
2026-03-26 15:47:17 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:47:17 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:47:17 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:47:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
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
======================= 5 passed, 19 warnings in 4.20s ========================
2026-03-26 15:47:26 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:47:26 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:47:26 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:47:26 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:47:27 - app.access - INFO - [546d220b-fa6c-431b-900a-32330ab8d1b2] - Request started
2026-03-26 15:47:27 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=release-gate-7325276a5ca0@example.com roles=doctor trace_id=546d220b-fa6c-431b-900a-32330ab8d1b2 details={"assigned_roles": ["doctor"], "department": "质控科", "target_email": "release-gate-7325276a5ca0@example.com"}
2026-03-26 15:47:27 - app.access - INFO - [546d220b-fa6c-431b-900a-32330ab8d1b2] - Request completed
2026-03-26 15:47:27 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 15:47:27 - app.access - INFO - [d67d9d33-3e5b-4022-a188-903b64b1720f] - Request started
2026-03-26 15:47:28 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-7325276a5ca0@example.com
2026-03-26 15:47:28 - app.access - INFO - [d67d9d33-3e5b-4022-a188-903b64b1720f] - Request completed
2026-03-26 15:47:28 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:28 - app.access - INFO - [53e0ef00-99f1-45c3-bd0d-ce343c13c257] - Request started
2026-03-26 15:47:28 - app.access - INFO - [53e0ef00-99f1-45c3-bd0d-ce343c13c257] - Request completed
2026-03-26 15:47:28 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/auth/me "HTTP/1.1 200 OK"
2026-03-26 15:47:28 - app.access - INFO - [5dc2f164-b90c-4769-a6db-d90067196151] - Request started
2026-03-26 15:47:28 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=release-gate-7325276a5ca0@example.com
2026-03-26 15:47:28 - app.access - INFO - [5dc2f164-b90c-4769-a6db-d90067196151] - Request completed
2026-03-26 15:47:28 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 15:47:28 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:47:28 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:47:28 - app.access - INFO - [2d0c4862-39a6-4ab2-b94e-1f4849f1b58b] - Request started
2026-03-26 15:47:28 - app.main - WARNING - [2d0c4862-39a6-4ab2-b94e-1f4849f1b58b] - HTTP Exception: 401 - Authentication required
2026-03-26 15:47:28 - app.access - WARNING - [2d0c4862-39a6-4ab2-b94e-1f4849f1b58b] - Request completed
2026-03-26 15:47:28 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 15:47:28 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:47:28 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:47:29 - app.access - INFO - [6e0f9d3d-1a3f-41b9-b766-dfe70bff2f0e] - Request started
2026-03-26 15:47:29 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=release-gate-6791a031e19e@example.com roles=doctor trace_id=6e0f9d3d-1a3f-41b9-b766-dfe70bff2f0e details={"assigned_roles": ["doctor"], "department": "质控科", "target_email": "release-gate-6791a031e19e@example.com"}
2026-03-26 15:47:29 - app.access - INFO - [6e0f9d3d-1a3f-41b9-b766-dfe70bff2f0e] - Request completed
2026-03-26 15:47:29 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 15:47:29 - app.access - INFO - [38f920ac-782b-4ca6-b5e3-ab3a1bc64275] - Request started
2026-03-26 15:47:29 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-6791a031e19e@example.com
2026-03-26 15:47:29 - app.access - INFO - [38f920ac-782b-4ca6-b5e3-ab3a1bc64275] - Request completed
2026-03-26 15:47:29 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:29 - app.access - INFO - [962a5c11-7459-44d4-bd70-b5585100655f] - Request started
2026-03-26 15:47:29 - app.main - WARNING - [962a5c11-7459-44d4-bd70-b5585100655f] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 15:47:29 - app.access - WARNING - [962a5c11-7459-44d4-bd70-b5585100655f] - Request completed
2026-03-26 15:47:29 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 15:47:29 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:47:29 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:47:30 - app.access - INFO - [ac184f60-c11e-4aa1-87e6-529cf6408cc8] - Request started
2026-03-26 15:47:30 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:47:30 - app.access - INFO - [ac184f60-c11e-4aa1-87e6-529cf6408cc8] - Request completed
2026-03-26 15:47:30 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:47:30 - app.access - INFO - [28a7b1fa-231b-4d70-a5c1-ac7180e23e1d] - Request started
2026-03-26 15:47:30 - app.core.permissions - INFO - [no-trace-id] - 权限允许: 用户 admin@medqc.com 执行 read 操作在 medical_records 资源上
2026-03-26 15:47:30 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 15:47:30 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 15:47:30 - app.access - INFO - [28a7b1fa-231b-4d70-a5c1-ac7180e23e1d] - Request completed
2026-03-26 15:47:30 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/records?page=1&page_size=5 "HTTP/1.1 200 OK"
2026-03-26 15:47:30 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:47:30 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:47:30 - app.access - INFO - [d4b0c8c6-c10c-4bf0-8897-17ac14eaf334] - Request started
2026-03-26 15:47:31 - app.access - INFO - [d4b0c8c6-c10c-4bf0-8897-17ac14eaf334] - Request completed
2026-03-26 15:47:31 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:47:31 - app.access - INFO - [9fb2022e-1409-4663-9b50-d802f43cd1a3] - Request started
2026-03-26 15:47:31 - app.access - INFO - [9fb2022e-1409-4663-9b50-d802f43cd1a3] - Request completed
2026-03-26 15:47:31 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
```