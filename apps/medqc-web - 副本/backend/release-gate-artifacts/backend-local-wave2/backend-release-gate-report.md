# Backend Release Gate Report

- total gates: 9
- passed gates: 9
- failed gates: 0
- all passed: True

## Gate Details
- auth_guard: PASS (0.08s)
  metrics: {"required_checks": 7, "passed_checks": 7, "coverage_ratio": 1.0}
- secret_hygiene: PASS (0.09s)
  metrics: {"findings": 0}
- alert_rules: PASS (0.09s)
  metrics: {"pass_marker_found": true}
- openapi_contract: PASS (7.25s)
  metrics: {"pass_marker_found": true}
- metrics_catalog: PASS (0.11s)
  metrics: {"pass_marker_found": true}
- migration_roundtrip: PASS (3.88s)
  metrics: {"head_count": 1, "head": "20260315_000002"}
- pytest_contract: PASS (11.82s)
  metrics: {"passed": 33, "failed": 0, "skipped": 0}
- pytest_security_consistency: PASS (15.6s)
  metrics: {"passed": 48, "failed": 0, "skipped": 0}
- pytest_integration_smoke: PASS (11.92s)
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
2026-03-26 15:25:19 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:25:19 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:25:20 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:20 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:20 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:20 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:20 - app.access - INFO - [f90d3bde-b2fe-444d-ab3e-daeb3b0418a5] - Request started
2026-03-26 15:25:20 - app.access - INFO - [f90d3bde-b2fe-444d-ab3e-daeb3b0418a5] - Request completed
2026-03-26 15:25:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
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
======================= 33 passed, 13 warnings in 4.55s =======================
2026-03-26 15:25:31 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:25:31 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:25:31 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:25:31 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:25:32 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:32 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:32 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:32 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:32 - app.access - INFO - [e885ff23-0c06-442b-aef4-af69194b35e2] - Request started
2026-03-26 15:25:32 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:32 - app.access - INFO - [e885ff23-0c06-442b-aef4-af69194b35e2] - Request completed
2026-03-26 15:25:32 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:32 - app.access - INFO - [2027e8a4-a59a-4098-93cc-599772563ef0] - Request started
2026-03-26 15:25:32 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 15:25:32 - app.access - INFO - [2027e8a4-a59a-4098-93cc-599772563ef0] - Request completed
2026-03-26 15:25:32 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 15:25:32 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:32 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:32 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:32 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:32 - app.access - INFO - [4b43ac22-5e04-41e0-bb95-a7d90ae764f9] - Request started
2026-03-26 15:25:33 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:33 - app.access - INFO - [4b43ac22-5e04-41e0-bb95-a7d90ae764f9] - Request completed
2026-03-26 15:25:33 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:33 - app.access - INFO - [0c7ee9aa-842b-4947-8009-ad57b3b402ac] - Request started
2026-03-26 15:25:33 - app.access - INFO - [0c7ee9aa-842b-4947-8009-ad57b3b402ac] - Request completed
2026-03-26 15:25:33 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 15:25:33 - app.access - INFO - [df6d3e88-ac28-4c26-b1e1-64a2dca40b34] - Request started
2026-03-26 15:25:33 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.pg.update resource=/api/v1/sync/config/pg outcome=success actor=admin@medqc.com roles=admin,qc_manager trace_id=df6d3e88-ac28-4c26-b1e1-64a2dca40b34 details={"changed_fields": ["remote_host", "remote_password", "remote_password_ref", "remote_port"], "connection_ok": true, "remote_host": "10.8.8.8", "remote_port": "5544"}
2026-03-26 15:25:33 - app.access - INFO - [df6d3e88-ac28-4c26-b1e1-64a2dca40b34] - Request completed
2026-03-26 15:25:33 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 15:25:33 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:33 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:33 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:33 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:33 - app.access - INFO - [412b7ce4-7e2c-4400-a4d5-6017a1b919b7] - Request started
2026-03-26 15:25:33 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 15:25:33 - app.access - INFO - [412b7ce4-7e2c-4400-a4d5-6017a1b919b7] - Request completed
2026-03-26 15:25:33 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:33 - app.access - INFO - [e791aa0a-0176-4ce1-a5f4-6d1af4602586] - Request started
2026-03-26 15:25:33 - app.main - WARNING - [e791aa0a-0176-4ce1-a5f4-6d1af4602586] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 15:25:33 - app.access - WARNING - [e791aa0a-0176-4ce1-a5f4-6d1af4602586] - Request completed
2026-03-26 15:25:33 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 15:25:33 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:33 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:33 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:33 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:33 - app.access - INFO - [938e1fbb-715a-4bf0-93d0-f285d6742cf0] - Request started
2026-03-26 15:25:33 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:33 - app.access - INFO - [938e1fbb-715a-4bf0-93d0-f285d6742cf0] - Request completed
2026-03-26 15:25:33 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:33 - app.access - INFO - [505def69-f80d-4523-961d-131d78b29f24] - Request started
2026-03-26 15:25:33 - app.routers.qc_sichuan - INFO - [no-trace-id] - Loaded 179 Sichuan rules from JSON file
2026-03-26 15:25:33 - app.access - INFO - [505def69-f80d-4523-961d-131d78b29f24] - Request completed
2026-03-26 15:25:33 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/rules "HTTP/1.1 200 OK"
2026-03-26 15:25:33 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:33 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:33 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:33 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:33 - app.access - INFO - [1c511ced-67c0-4990-bea9-94c79c6bfd52] - Request started
2026-03-26 15:25:34 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:34 - app.access - INFO - [1c511ced-67c0-4990-bea9-94c79c6bfd52] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.access - INFO - [c1c29819-f2f3-48fd-ac9b-24a992f35833] - Request started
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251110_041209.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251109_233517.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_234838.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_070941.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065547.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065421.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_062819.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_053504.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_021345.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_015054.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_014934.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_013113.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_005230.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\fe17a51e-5db0-4d37-ab6d-ac41cecca752_sequential_batch_20251112_130619.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f41ab06d-0f77-4f0f-ad27-e9c08fea5756_sequential_batch_20251112_143049.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f158d3cf-7fa9-4059-82e6-01e478d60399_sequential_batch_20251112_142617.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\e6cd1e70-88ac-4df9-a164-1326d35a6874_sequential_batch_20251110_064046.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\daf44f72-0baa-453b-bf32-b9355bd3bd01_sequential_batch_20251112_011112.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\defbcbd9-94e9-4723-b6df-dbf0b21ea4f7_sequential_batch_20251112_233633.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\c79d0012-c564-4d1c-bd4c-cf5aebe1fd92_sequential_batch_20251112_132237.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_083256.json: 'list' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a9c69ec9-9675-40ed-b203-5d830842a11c_sequential_batch_20251112_013953.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_082322.json: 'list' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a2bbfbe5-48de-4da8-bb47-e0cc59424775_sequential_batch_20251112_233854.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\9d5ec2a7-dc69-40dc-86ac-2c1e52f9aafd_sequential_batch_20251112_031338.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\89bb0a9d-14b9-48bc-8f67-f04f89fbb9c5_sequential_batch_20251112_031203.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\81d4a41f-bd3d-457d-aea6-1c32a412312e_sequential_batch_20251111_120900.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\818fe627-f5ad-4101-b06d-8a2addf10a71_sequential_batch_20251111_134659.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6fd14104-4d02-4b52-bc3d-a012cf4ede90_sequential_batch_20251112_232848.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6de19991-4266-4aa4-8bef-ee3001fb3ddc_sequential_batch_20251113_000427.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6154a09c-c692-4cfd-83a7-eb2773a9ad8b_sequential_batch_20251112_141218.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\5a2b1859-a0a8-436b-a4a0-af30eb6db6dc_sequential_batch_20251111_235912.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\57c72978-223b-4e01-b6ff-180e802c1718_sequential_batch_20251112_130944.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4eb1f192-80d8-48fa-8393-0c91b788d0d9_sequential_batch_20251111_235832.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4798fb59-6450-4f11-94c3-848d2702cf6c_sequential_batch_20251112_151503.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4596298c-eca7-4ca2-89ce-30ce5ae2898d_sequential_batch_20251111_012838.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\36f11425-d816-4f8a-b624-dced1ac4c164_sequential_batch_20251112_060145.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\2c59b9ef-9b2f-4ef8-b671-d0840df86da8_sequential_batch_20251112_231936.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1e2886a3-253f-4008-b4c7-da32548e5826_sequential_batch_20251111_121107.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1ca2602c-56e6-4310-b686-19a73531a8a9_sequential_batch_20251112_232958.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\13c4efdd-6bff-4ff7-aa51-2bc906aad435_sequential_batch_20251112_232048.json: 'NoneType' object has no attribute 'get'
2026-03-26 15:25:34 - app.access - INFO - [c1c29819-f2f3-48fd-ac9b-24a992f35833] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/results/history?page=1&page_size=10 "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:34 - app.access - INFO - [17c94ecd-96bb-453a-8d2a-ffa4ed0ec6ef] - Request started
2026-03-26 15:25:34 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:34 - app.access - INFO - [17c94ecd-96bb-453a-8d2a-ffa4ed0ec6ef] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.access - INFO - [d750bed1-62e5-4d44-9ec3-2f2abfc1c920] - Request started
2026-03-26 15:25:34 - app.access - INFO - [d750bed1-62e5-4d44-9ec3-2f2abfc1c920] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:34 - app.access - INFO - [c260a543-7962-41f8-b190-2cefea1946c5] - Request started
2026-03-26 15:25:34 - app.access - INFO - [c260a543-7962-41f8-b190-2cefea1946c5] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:34 - app.access - INFO - [9f09ea89-7ecd-4505-96ab-e7f850e32c36] - Request started
2026-03-26 15:25:34 - app.access - INFO - [9f09ea89-7ecd-4505-96ab-e7f850e32c36] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:34 - app.access - INFO - [a53bc532-de0a-44b1-8979-156d79bbecc2] - Request started
2026-03-26 15:25:34 - app.access - INFO - [a53bc532-de0a-44b1-8979-156d79bbecc2] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.access - INFO - [a80c4c26-dd77-42ef-9e80-bedbb708e3ee] - Request started
2026-03-26 15:25:34 - app.access - INFO - [a80c4c26-dd77-42ef-9e80-bedbb708e3ee] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.access - INFO - [7e96c2c6-c8ab-43fb-82b6-d3823cad7735] - Request started
2026-03-26 15:25:34 - app.main - WARNING - [7e96c2c6-c8ab-43fb-82b6-d3823cad7735] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 15:25:34 - app.access - WARNING - [7e96c2c6-c8ab-43fb-82b6-d3823cad7735] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 403 Forbidden"
2026-03-26 15:25:34 - app.access - INFO - [5aa6fff1-893f-45d4-8a10-5ef814f9d350] - Request started
2026-03-26 15:25:34 - app.main - WARNING - [5aa6fff1-893f-45d4-8a10-5ef814f9d350] - HTTP Exception: 401 - Authentication required
2026-03-26 15:25:34 - app.access - WARNING - [5aa6fff1-893f-45d4-8a10-5ef814f9d350] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 401 Unauthorized"
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:34 - app.access - INFO - [998c7e18-71f4-42eb-9f0f-117fb9050189] - Request started
2026-03-26 15:25:34 - app.main - WARNING - [998c7e18-71f4-42eb-9f0f-117fb9050189] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 15:25:34 - app.access - WARNING - [998c7e18-71f4-42eb-9f0f-117fb9050189] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:34 - app.access - INFO - [5d5d92fe-d927-4f5b-b4df-9480833c5573] - Request started
2026-03-26 15:25:34 - app.main - WARNING - [5d5d92fe-d927-4f5b-b4df-9480833c5573] - Validation Error: [{'type': 'greater_than_equal', 'loc': ('body', 'lookback_minutes'), 'msg': 'Input should be greater than or equal to 0', 'input': -1, 'ctx': {'ge': 0}, 'url': 'https://errors.pydantic.dev/2.5/v/greater_than_equal'}]
2026-03-26 15:25:34 - app.access - WARNING - [5d5d92fe-d927-4f5b-b4df-9480833c5573] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 15:25:34 - app.access - INFO - [f9646714-f5d8-42b9-b52e-b828342fb168] - Request started
2026-03-26 15:25:34 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.mongo.update resource=/api/v1/sync/config/mongo outcome=success actor=sync@test.local roles=admin trace_id=f9646714-f5d8-42b9-b52e-b828342fb168 details={"changed_fields": ["connect_timeout_ms", "enabled", "inter_request_delay_ms", "lookback_minutes", "max_batch_size", "night_window_end", "night_window_start", "rescan_recent_days", "tier1_interval_minutes", "tier2_interval_minutes", "tier3_cron"], "enabled": true}
2026-03-26 15:25:34 - app.access - INFO - [f9646714-f5d8-42b9-b52e-b828342fb168] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:34 - app.access - INFO - [956fb8d8-078f-43eb-8590-0cc5403da591] - Request started
2026-03-26 15:25:34 - app.access - INFO - [956fb8d8-078f-43eb-8590-0cc5403da591] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:34 - app.access - INFO - [58c8eef3-709c-4dbb-9d04-ddf14deb9785] - Request started
2026-03-26 15:25:34 - app.access - INFO - [58c8eef3-709c-4dbb-9d04-ddf14deb9785] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/test-connection/all "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:34 - app.access - INFO - [3f11ddc8-ff09-4ccf-9c1e-6f5fd1e91333] - Request started
2026-03-26 15:25:34 - app.access - INFO - [3f11ddc8-ff09-4ccf-9c1e-6f5fd1e91333] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:34 - app.access - INFO - [265c5a8e-8b85-40d1-9789-1a01937ec6c8] - Request started
2026-03-26 15:25:34 - app.access - INFO - [265c5a8e-8b85-40d1-9789-1a01937ec6c8] - Request completed
2026-03-26 15:25:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 15:25:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [0e34b160-58ff-40ac-85b3-e3d2e489385a] - Request started
2026-03-26 15:25:35 - app.audit - INFO - [no-trace-id] - audit.event action=sync.trigger resource=/api/v1/sync/trigger outcome=rejected_running actor=sync@test.local roles=admin trace_id=0e34b160-58ff-40ac-85b3-e3d2e489385a details={"idempotency_key": "mongo:all:2026-03-26:sync@test.local", "run_id": "syncrun-04eac36db4fd", "source": "mongo", "sync_date": "2026-03-26", "tier": "all"}
2026-03-26 15:25:35 - app.access - INFO - [0e34b160-58ff-40ac-85b3-e3d2e489385a] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [c83bdc31-5779-46e7-ac83-c2718395db5b] - Request started
2026-03-26 15:25:35 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 15:25:35 - app.audit - INFO - [no-trace-id] - audit.event action=sync.trigger resource=/api/v1/sync/trigger outcome=success actor=sync@test.local roles=admin trace_id=c83bdc31-5779-46e7-ac83-c2718395db5b details={"idempotency_key": "mongo:tier1:2026-03-26:sync@test.local", "run_id": "syncrun-7dda594ec283", "source": "mongo", "status": "success", "sync_date": "2026-03-26", "tier": "tier1", "total_records": 2}
2026-03-26 15:25:35 - app.access - INFO - [c83bdc31-5779-46e7-ac83-c2718395db5b] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [b3418153-246c-4c68-94d1-e67e5aaac0d7] - Request started
2026-03-26 15:25:35 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 15:25:35 - app.access - INFO - [b3418153-246c-4c68-94d1-e67e5aaac0d7] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.access - INFO - [1ddb292d-d7a1-4545-a483-c2b817fa91b8] - Request started
2026-03-26 15:25:35 - app.access - INFO - [1ddb292d-d7a1-4545-a483-c2b817fa91b8] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [a5ea6b67-e95f-48ee-bc24-d232516cb252] - Request started
2026-03-26 15:25:35 - app.access - INFO - [a5ea6b67-e95f-48ee-bc24-d232516cb252] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/runs?source=mongo&tier=tier2&limit=20 "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [abddbfce-8888-4e2d-8e46-911f499441e4] - Request started
2026-03-26 15:25:35 - app.access - INFO - [abddbfce-8888-4e2d-8e46-911f499441e4] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.access - INFO - [13e7082f-d990-47ff-8b5a-aba1f29d10ef] - Request started
2026-03-26 15:25:35 - app.main - WARNING - [13e7082f-d990-47ff-8b5a-aba1f29d10ef] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 15:25:35 - app.access - WARNING - [13e7082f-d990-47ff-8b5a-aba1f29d10ef] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 403 Forbidden"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [c3e34943-3987-4a09-8af4-097704a0c38e] - Request started
2026-03-26 15:25:35 - app.audit - INFO - [no-trace-id] - audit.event action=sync.template.apply resource=/api/v1/sync/templates/apply outcome=success actor=sync@test.local roles=admin trace_id=c3e34943-3987-4a09-8af4-097704a0c38e details={"departments_count": 1, "enabled": false, "template_id": "single_department_focus"}
2026-03-26 15:25:35 - app.access - INFO - [c3e34943-3987-4a09-8af4-097704a0c38e] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [76aa515e-d79b-4e0f-802d-6d07d8b155e6] - Request started
2026-03-26 15:25:35 - app.main - WARNING - [76aa515e-d79b-4e0f-802d-6d07d8b155e6] - HTTP Exception: 422 - 该模板必须选择科室
2026-03-26 15:25:35 - app.access - WARNING - [76aa515e-d79b-4e0f-802d-6d07d8b155e6] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 15:25:35 - app.access - INFO - [a3c6af57-b509-4a20-9bb4-86e41c930253] - Request started
2026-03-26 15:25:35 - app.main - WARNING - [a3c6af57-b509-4a20-9bb4-86e41c930253] - HTTP Exception: 422 - 科室列表不允许同时包含 * 和具体科室
2026-03-26 15:25:35 - app.access - WARNING - [a3c6af57-b509-4a20-9bb4-86e41c930253] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [78e21ee2-53aa-4a0a-8112-e0fa38236d81] - Request started
2026-03-26 15:25:35 - app.access - INFO - [78e21ee2-53aa-4a0a-8112-e0fa38236d81] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [d758813b-aa3a-4f71-99f2-94d51d1e9f3b] - Request started
2026-03-26 15:25:35 - app.main - WARNING - [d758813b-aa3a-4f71-99f2-94d51d1e9f3b] - HTTP Exception: 422 - mongo_uri 未配置
2026-03-26 15:25:35 - app.access - WARNING - [d758813b-aa3a-4f71-99f2-94d51d1e9f3b] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [6063214c-3237-46d2-9421-a54c7274f607] - Request started
2026-03-26 15:25:35 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 15:25:35 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 15:25:35 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:25:35 - app.access - INFO - [6063214c-3237-46d2-9421-a54c7274f607] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [abd54f7e-bd3b-409b-83b1-89b27ece342b] - Request started
2026-03-26 15:25:35 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:25:35 - app.access - INFO - [abd54f7e-bd3b-409b-83b1-89b27ece342b] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics/prometheus "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [trace-client-123] - Request started
2026-03-26 15:25:35 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:25:35 - app.access - INFO - [trace-client-123] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [req-client-456] - Request started
2026-03-26 15:25:35 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:25:35 - app.access - INFO - [req-client-456] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request started
2026-03-26 15:25:35 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:25:35 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [e0aaaf2e-7c50-4803-b0d5-4b0f0378fc04] - Request started
2026-03-26 15:25:35 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:25:35 - app.access - INFO - [e0aaaf2e-7c50-4803-b0d5-4b0f0378fc04] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request started
2026-03-26 15:25:35 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:25:35 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request completed
2026-03-26 15:25:35 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:35 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:25:35 - app.core.otel - WARNING - [no-trace-id] - OpenTelemetry dependencies unavailable, skip instrumentation: No module named 'opentelemetry'
2026-03-26 15:25:36 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:36 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:36 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:36 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:36 - app.access - INFO - [322ef7fc-b566-46ef-96da-32f2002a8727] - Request started
2026-03-26 15:25:36 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:25:36 - app.access - ERROR - [322ef7fc-b566-46ef-96da-32f2002a8727] - Request failed: boom
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
2026-03-26 15:25:36 - app.core.middleware_errors - ERROR - [322ef7fc-b566-46ef-96da-32f2002a8727] - Internal Server Error: boom
2026-03-26 15:25:36 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 500 Internal Server Error"
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
======================= 48 passed, 13 warnings in 8.34s =======================
2026-03-26 15:25:43 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:25:43 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:25:43 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.pg.update resource=/api/v1/sync/config/pg outcome=success actor=admin@medqc.com roles=admin trace_id=trace-unit-audit details={"nested": {"token": "***"}, "remote_host": "127.0.0.1", "remote_password": "***"}
2026-03-26 15:25:43 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:25:43 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:25:44 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:44 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:44 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:44 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:44 - app.access - INFO - [09feaa6d-aa1b-4f90-beed-038e588014b1] - Request started
2026-03-26 15:25:44 - app.main - WARNING - [09feaa6d-aa1b-4f90-beed-038e588014b1] - HTTP Exception: 401 - Authentication required
2026-03-26 15:25:44 - app.access - WARNING - [09feaa6d-aa1b-4f90-beed-038e588014b1] - Request completed
2026-03-26 15:25:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 15:25:44 - app.access - INFO - [2e14d800-872d-4a7b-b58b-c23213f56cca] - Request started
2026-03-26 15:25:44 - app.main - WARNING - [2e14d800-872d-4a7b-b58b-c23213f56cca] - HTTP Exception: 401 - Authentication required
2026-03-26 15:25:44 - app.access - WARNING - [2e14d800-872d-4a7b-b58b-c23213f56cca] - Request completed
2026-03-26 15:25:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/drg/config/current "HTTP/1.1 401 Unauthorized"
2026-03-26 15:25:44 - app.access - INFO - [3ba9a61e-83e2-40e4-a92d-fff8c3ccea35] - Request started
2026-03-26 15:25:44 - app.main - WARNING - [3ba9a61e-83e2-40e4-a92d-fff8c3ccea35] - HTTP Exception: 401 - Authentication required
2026-03-26 15:25:44 - app.access - WARNING - [3ba9a61e-83e2-40e4-a92d-fff8c3ccea35] - Request completed
2026-03-26 15:25:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/settlement/list "HTTP/1.1 401 Unauthorized"
2026-03-26 15:25:44 - app.access - INFO - [df1e1542-9422-4efc-be98-8dc0b2ec858c] - Request started
2026-03-26 15:25:44 - app.main - WARNING - [df1e1542-9422-4efc-be98-8dc0b2ec858c] - HTTP Exception: 401 - Authentication required
2026-03-26 15:25:44 - app.access - WARNING - [df1e1542-9422-4efc-be98-8dc0b2ec858c] - Request completed
2026-03-26 15:25:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 401 Unauthorized"
2026-03-26 15:25:44 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:44 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:44 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:44 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:44 - app.access - INFO - [d99b5f28-72b4-44b7-95bb-272b06b3abc1] - Request started
2026-03-26 15:25:44 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 15:25:44 - app.access - INFO - [d99b5f28-72b4-44b7-95bb-272b06b3abc1] - Request completed
2026-03-26 15:25:44 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:44 - app.access - INFO - [5e3f542b-3331-426a-adbe-2c62a949d1ad] - Request started
2026-03-26 15:25:44 - app.main - WARNING - [5e3f542b-3331-426a-adbe-2c62a949d1ad] - HTTP Exception: 403 - 此操作需要系统管理员权限
2026-03-26 15:25:44 - app.access - WARNING - [5e3f542b-3331-426a-adbe-2c62a949d1ad] - Request completed
2026-03-26 15:25:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 403 Forbidden"
2026-03-26 15:25:44 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:44 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:44 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:44 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:44 - app.access - INFO - [3f838926-4691-4eb5-90e9-1312da840fae] - Request started
2026-03-26 15:25:44 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:44 - app.access - INFO - [3f838926-4691-4eb5-90e9-1312da840fae] - Request completed
2026-03-26 15:25:44 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:44 - app.access - INFO - [de0c77f7-c978-4882-9f5a-0c465d680038] - Request started
2026-03-26 15:25:44 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 15:25:44 - app.access - INFO - [de0c77f7-c978-4882-9f5a-0c465d680038] - Request completed
2026-03-26 15:25:44 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 15:25:44 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:44 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:44 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:44 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:44 - app.access - INFO - [9f21ec9a-680b-47f3-84cf-2eb404ceb9ff] - Request started
2026-03-26 15:25:45 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=reset-1469cb01@medqc.com roles=doctor trace_id=9f21ec9a-680b-47f3-84cf-2eb404ceb9ff details={"assigned_roles": ["doctor"], "department": "测试科室", "target_email": "reset-1469cb01@medqc.com"}
2026-03-26 15:25:45 - app.access - INFO - [9f21ec9a-680b-47f3-84cf-2eb404ceb9ff] - Request completed
2026-03-26 15:25:45 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 15:25:45 - app.access - INFO - [f065ebb5-c502-4e9f-824b-5524cdcce04b] - Request started
2026-03-26 15:25:45 - app.routers.auth - INFO - [no-trace-id] - auth.forgot_password.issued email=reset-1469cb01@medqc.com
2026-03-26 15:25:45 - app.access - INFO - [f065ebb5-c502-4e9f-824b-5524cdcce04b] - Request completed
2026-03-26 15:25:45 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/forgot-password "HTTP/1.1 200 OK"
2026-03-26 15:25:45 - app.access - INFO - [4fc2ed43-33fd-439f-9127-ace18d2e5e13] - Request started
2026-03-26 15:25:45 - app.routers.auth - INFO - [no-trace-id] - auth.reset_password.success email=reset-1469cb01@medqc.com
2026-03-26 15:25:45 - app.access - INFO - [4fc2ed43-33fd-439f-9127-ace18d2e5e13] - Request completed
2026-03-26 15:25:45 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 200 OK"
2026-03-26 15:25:45 - app.access - INFO - [59ce1578-2d6e-4d0b-b278-26b330031ccb] - Request started
2026-03-26 15:25:45 - app.main - WARNING - [59ce1578-2d6e-4d0b-b278-26b330031ccb] - HTTP Exception: 401 - 重置令牌已使用或失效
2026-03-26 15:25:45 - app.access - WARNING - [59ce1578-2d6e-4d0b-b278-26b330031ccb] - Request completed
2026-03-26 15:25:45 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 401 Unauthorized"
2026-03-26 15:25:45 - app.access - INFO - [36aa9ef6-259e-4d2e-ba92-8cb0a14cd754] - Request started
2026-03-26 15:25:45 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=reset-1469cb01@medqc.com
2026-03-26 15:25:45 - app.access - INFO - [36aa9ef6-259e-4d2e-ba92-8cb0a14cd754] - Request completed
2026-03-26 15:25:45 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:45 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:45 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:45 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:45 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:45 - app.access - INFO - [514c40d5-4e3f-494b-8857-363df0763a2e] - Request started
2026-03-26 15:25:46 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:46 - app.access - INFO - [514c40d5-4e3f-494b-8857-363df0763a2e] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.access - INFO - [a3f88fdd-0cc7-48ba-9008-f95cb6f53375] - Request started
2026-03-26 15:25:46 - app.main - WARNING - [a3f88fdd-0cc7-48ba-9008-f95cb6f53375] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/db/config. Please use /api/v1/sync/*
2026-03-26 15:25:46 - app.access - WARNING - [a3f88fdd-0cc7-48ba-9008-f95cb6f53375] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/system/db/config "HTTP/1.1 410 Gone"
2026-03-26 15:25:46 - app.access - INFO - [9dc00e3c-e4ce-4f3e-9300-502ded497570] - Request started
2026-03-26 15:25:46 - app.main - WARNING - [9dc00e3c-e4ce-4f3e-9300-502ded497570] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/sync/trigger. Please use /api/v1/sync/*
2026-03-26 15:25:46 - app.access - WARNING - [9dc00e3c-e4ce-4f3e-9300-502ded497570] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/system/sync/trigger "HTTP/1.1 410 Gone"
2026-03-26 15:25:46 - app.services.etl_sync - INFO - [no-trace-id] - 同步 病案首页 (web.mr)...
2026-03-26 15:25:46 - app.services.etl_sync - INFO - [no-trace-id] -   \u2705 病案首页: 1 条
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [bfaeb62a-5c96-4de4-bb55-787a9cb220f2] - Request started
2026-03-26 15:25:46 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 15:25:46 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 15:25:46 - app.access - INFO - [bfaeb62a-5c96-4de4-bb55-787a9cb220f2] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [2f533353-395e-4544-8a18-d00c8e393e2e] - Request started
2026-03-26 15:25:46 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:25:46 - app.access - INFO - [2f533353-395e-4544-8a18-d00c8e393e2e] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [74df51ef-3175-461c-8fe3-e4f7baa14f52] - Request started
2026-03-26 15:25:46 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:25:46 - app.access - INFO - [74df51ef-3175-461c-8fe3-e4f7baa14f52] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics/prometheus "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [e7b5b5c7-7de2-4082-bea6-6da10b0df71b] - Request started
2026-03-26 15:25:46 - app.access - INFO - [e7b5b5c7-7de2-4082-bea6-6da10b0df71b] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [2fe8ef0b-c6a3-45b2-a071-7c0cb051a2d3] - Request started
2026-03-26 15:25:46 - app.access - WARNING - [2fe8ef0b-c6a3-45b2-a071-7c0cb051a2d3] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: OPTIONS http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [8d8a9a60-428e-45d6-82e5-00b26dd4f6d8] - Request started
2026-03-26 15:25:46 - app.access - INFO - [8d8a9a60-428e-45d6-82e5-00b26dd4f6d8] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [1cf6c4a4-9ecc-40f5-9b33-6b8345bfe7a1] - Request started
2026-03-26 15:25:46 - app.access - INFO - [1cf6c4a4-9ecc-40f5-9b33-6b8345bfe7a1] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [eecca362-4dc3-4a1b-875b-dc0a96212b47] - Request started
2026-03-26 15:25:46 - app.access - INFO - [eecca362-4dc3-4a1b-875b-dc0a96212b47] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [1b3289b5-9053-4741-92f2-89cb587db4a9] - Request started
2026-03-26 15:25:46 - app.access - INFO - [1b3289b5-9053-4741-92f2-89cb587db4a9] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [1e9a6ad7-995a-426c-b682-a8ae85eb3c24] - Request started
2026-03-26 15:25:46 - app.access - INFO - [1e9a6ad7-995a-426c-b682-a8ae85eb3c24] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [f6f672a1-4fc4-4ac9-a384-f4d73bfa5ccb] - Request started
2026-03-26 15:25:46 - app.access - INFO - [f6f672a1-4fc4-4ac9-a384-f4d73bfa5ccb] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [32f228ef-6d3b-4cfb-b9c4-3edf78e237d9] - Request started
2026-03-26 15:25:46 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 15:25:46 - app.access - INFO - [32f228ef-6d3b-4cfb-b9c4-3edf78e237d9] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [381d467c-f3c6-4a5c-8b50-6325d1788ea9] - Request started
2026-03-26 15:25:46 - app.access - WARNING - [381d467c-f3c6-4a5c-8b50-6325d1788ea9] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/nonexistent "HTTP/1.1 404 Not Found"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [34fa0b99-28a8-4bac-b4ea-8c89eec82613] - Request started
2026-03-26 15:25:46 - app.access - WARNING - [34fa0b99-28a8-4bac-b4ea-8c89eec82613] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:46 - app.access - INFO - [be4c2e35-299f-43fc-b37f-791805364320] - Request started
2026-03-26 15:25:46 - app.access - INFO - [24755f6f-68ab-4651-a952-c3b1cb436fb1] - Request started
2026-03-26 15:25:46 - app.access - INFO - [b4254eeb-81e8-44c1-a96a-4fd79aa6339d] - Request started
2026-03-26 15:25:46 - app.access - INFO - [8a506397-0a5b-4274-8dea-bf7f8d64929e] - Request started
2026-03-26 15:25:46 - app.access - INFO - [cff00d88-3571-4615-92b1-efb327ebf556] - Request started
2026-03-26 15:25:46 - app.access - INFO - [09f1f20b-1699-418a-a549-1de800fe4b74] - Request started
2026-03-26 15:25:46 - app.access - INFO - [f7050088-c964-47a1-a669-01c86dcb5af1] - Request started
2026-03-26 15:25:46 - app.access - INFO - [be4c2e35-299f-43fc-b37f-791805364320] - Request completed
2026-03-26 15:25:46 - app.access - INFO - [dc0045d7-00a9-4a06-9885-da29c2f7571c] - Request started
2026-03-26 15:25:46 - app.access - INFO - [ad33ce6f-dec7-4c1f-84bf-d59b0e47b11b] - Request started
2026-03-26 15:25:46 - app.access - INFO - [cd971d3d-eeee-4fd1-9c74-dcb6c2f8c7c6] - Request started
2026-03-26 15:25:46 - app.access - INFO - [24755f6f-68ab-4651-a952-c3b1cb436fb1] - Request completed
2026-03-26 15:25:46 - app.access - INFO - [b4254eeb-81e8-44c1-a96a-4fd79aa6339d] - Request completed
2026-03-26 15:25:46 - app.access - INFO - [8a506397-0a5b-4274-8dea-bf7f8d64929e] - Request completed
2026-03-26 15:25:46 - app.access - INFO - [cff00d88-3571-4615-92b1-efb327ebf556] - Request completed
2026-03-26 15:25:46 - app.access - INFO - [09f1f20b-1699-418a-a549-1de800fe4b74] - Request completed
2026-03-26 15:25:46 - app.access - INFO - [f7050088-c964-47a1-a669-01c86dcb5af1] - Request completed
2026-03-26 15:25:46 - app.access - INFO - [dc0045d7-00a9-4a06-9885-da29c2f7571c] - Request completed
2026-03-26 15:25:46 - app.access - INFO - [ad33ce6f-dec7-4c1f-84bf-d59b0e47b11b] - Request completed
2026-03-26 15:25:46 - app.access - INFO - [cd971d3d-eeee-4fd1-9c74-dcb6c2f8c7c6] - Request completed
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:47 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:47 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:47 - app.access - INFO - [fa148ecf-9ef1-4d14-be7f-dc937c6ebceb] - Request started
2026-03-26 15:25:47 - app.access - INFO - [fa148ecf-9ef1-4d14-be7f-dc937c6ebceb] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:47 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:47 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:47 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:47 - app.access - INFO - [82ff37d3-e763-4772-bf49-86ac7e6f2101] - Request started
2026-03-26 15:25:47 - app.access - INFO - [82ff37d3-e763-4772-bf49-86ac7e6f2101] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:47 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:47 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:47 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:47 - app.access - INFO - [d58f7fe0-0ad7-4475-a55a-2ea5ec4e073f] - Request started
2026-03-26 15:25:47 - app.access - INFO - [d58f7fe0-0ad7-4475-a55a-2ea5ec4e073f] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:47 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:47 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:47 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:47 - app.access - INFO - [dedb335e-0c71-438b-80a5-bdef3bd191db] - Request started
2026-03-26 15:25:47 - app.access - INFO - [dedb335e-0c71-438b-80a5-bdef3bd191db] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health?test=1&test=2 "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:47 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:47 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:47 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:47 - app.access - INFO - [ce2a1084-9ba4-4898-be82-215506a083d1] - Request started
2026-03-26 15:25:47 - app.access - INFO - [ce2a1084-9ba4-4898-be82-215506a083d1] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [8cd0f7db-a5d2-40fe-9cff-d390d2471a8c] - Request started
2026-03-26 15:25:47 - app.access - INFO - [8cd0f7db-a5d2-40fe-9cff-d390d2471a8c] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [4d865033-e6c5-444b-a298-3fc387faed7f] - Request started
2026-03-26 15:25:47 - app.access - INFO - [4d865033-e6c5-444b-a298-3fc387faed7f] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [1b8b8ad7-8272-44b4-94aa-138d5be13987] - Request started
2026-03-26 15:25:47 - app.access - INFO - [1b8b8ad7-8272-44b4-94aa-138d5be13987] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [519e599f-d507-4e80-8023-9a91f155c482] - Request started
2026-03-26 15:25:47 - app.access - INFO - [519e599f-d507-4e80-8023-9a91f155c482] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [4ef54cff-05bf-45a3-a6fd-64cbb63c25cb] - Request started
2026-03-26 15:25:47 - app.access - INFO - [4ef54cff-05bf-45a3-a6fd-64cbb63c25cb] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [b5862f6f-4c46-4615-87ac-72db85da586a] - Request started
2026-03-26 15:25:47 - app.access - INFO - [b5862f6f-4c46-4615-87ac-72db85da586a] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [a822f223-0236-48c6-8669-20b8c1c46d15] - Request started
2026-03-26 15:25:47 - app.access - INFO - [a822f223-0236-48c6-8669-20b8c1c46d15] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [003107fc-85de-4ed9-a893-2467809e2799] - Request started
2026-03-26 15:25:47 - app.access - INFO - [003107fc-85de-4ed9-a893-2467809e2799] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [7cee9688-4669-41f2-bf97-8f2d5c7fcfe7] - Request started
2026-03-26 15:25:47 - app.access - INFO - [7cee9688-4669-41f2-bf97-8f2d5c7fcfe7] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [ca9bd5b4-2af5-44f1-b486-a49252abdae7] - Request started
2026-03-26 15:25:47 - app.access - INFO - [ca9bd5b4-2af5-44f1-b486-a49252abdae7] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [a5e80462-1260-4ce6-a1a8-f9b654ab7fa3] - Request started
2026-03-26 15:25:47 - app.access - INFO - [a5e80462-1260-4ce6-a1a8-f9b654ab7fa3] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [2bf9759b-4d2d-4d58-87b2-a494da4e8005] - Request started
2026-03-26 15:25:47 - app.access - INFO - [2bf9759b-4d2d-4d58-87b2-a494da4e8005] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [69b1e90a-3962-427b-a015-feb8f7ecba7b] - Request started
2026-03-26 15:25:47 - app.access - INFO - [69b1e90a-3962-427b-a015-feb8f7ecba7b] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [62e303f7-3c29-4dad-8070-4d3089a2dfa1] - Request started
2026-03-26 15:25:47 - app.access - INFO - [62e303f7-3c29-4dad-8070-4d3089a2dfa1] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [58168377-652b-4b83-9871-c46420d5b624] - Request started
2026-03-26 15:25:47 - app.access - INFO - [58168377-652b-4b83-9871-c46420d5b624] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [b100f634-23fd-4ef8-ab53-7f3e41c92991] - Request started
2026-03-26 15:25:47 - app.access - INFO - [b100f634-23fd-4ef8-ab53-7f3e41c92991] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [cbca1980-8984-4a11-a1e4-6aae195dfded] - Request started
2026-03-26 15:25:47 - app.access - INFO - [cbca1980-8984-4a11-a1e4-6aae195dfded] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [de062031-892d-4a43-9003-6c9c347198c2] - Request started
2026-03-26 15:25:47 - app.access - INFO - [de062031-892d-4a43-9003-6c9c347198c2] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [871a33b9-57c1-4f89-be27-82888377ea41] - Request started
2026-03-26 15:25:47 - app.access - INFO - [871a33b9-57c1-4f89-be27-82888377ea41] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [dddbb36c-ae79-479b-8b2e-dac73d318780] - Request started
2026-03-26 15:25:47 - app.access - INFO - [dddbb36c-ae79-479b-8b2e-dac73d318780] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [a0302ed8-3d3e-483b-93d3-9c1e344ec846] - Request started
2026-03-26 15:25:47 - app.access - INFO - [a0302ed8-3d3e-483b-93d3-9c1e344ec846] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [c47c1fcc-9596-4164-97c2-c5941836f9ad] - Request started
2026-03-26 15:25:47 - app.access - INFO - [c47c1fcc-9596-4164-97c2-c5941836f9ad] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [b23004b2-f49c-44eb-8f33-6ab3d211a4b7] - Request started
2026-03-26 15:25:47 - app.access - INFO - [b23004b2-f49c-44eb-8f33-6ab3d211a4b7] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [e071d898-8c8a-416d-8687-173fcd823cb0] - Request started
2026-03-26 15:25:47 - app.access - INFO - [e071d898-8c8a-416d-8687-173fcd823cb0] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [bcace93c-568d-46a0-9cd2-57c65be2cf4d] - Request started
2026-03-26 15:25:47 - app.access - INFO - [bcace93c-568d-46a0-9cd2-57c65be2cf4d] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [77c7b036-db29-4366-8e4e-5be4afc3921c] - Request started
2026-03-26 15:25:47 - app.access - INFO - [77c7b036-db29-4366-8e4e-5be4afc3921c] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [99c97bc6-afaa-494f-a895-cc1471ab70e9] - Request started
2026-03-26 15:25:47 - app.access - INFO - [99c97bc6-afaa-494f-a895-cc1471ab70e9] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [34377ecc-300c-4861-8f11-41dbd75d49c2] - Request started
2026-03-26 15:25:47 - app.access - INFO - [34377ecc-300c-4861-8f11-41dbd75d49c2] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [2cd7afff-775b-4ccf-99eb-fb390c2bbc27] - Request started
2026-03-26 15:25:47 - app.access - INFO - [2cd7afff-775b-4ccf-99eb-fb390c2bbc27] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [e71fcd5f-f962-493d-8c46-3fc11c0f64a3] - Request started
2026-03-26 15:25:47 - app.access - INFO - [e71fcd5f-f962-493d-8c46-3fc11c0f64a3] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [858213f6-f088-4400-b2d5-111b56b428af] - Request started
2026-03-26 15:25:47 - app.access - INFO - [858213f6-f088-4400-b2d5-111b56b428af] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [423f8e65-a283-4888-8b25-db54f8a027b3] - Request started
2026-03-26 15:25:47 - app.access - INFO - [423f8e65-a283-4888-8b25-db54f8a027b3] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [45f2f086-56d9-4fd2-8da9-84ca5fbdcd3b] - Request started
2026-03-26 15:25:47 - app.access - INFO - [45f2f086-56d9-4fd2-8da9-84ca5fbdcd3b] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [ec47ebf1-5ba9-45f4-8aa5-5762a3571515] - Request started
2026-03-26 15:25:47 - app.access - INFO - [ec47ebf1-5ba9-45f4-8aa5-5762a3571515] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [70de2f5b-9901-4f21-94d3-d79206f3002c] - Request started
2026-03-26 15:25:47 - app.access - INFO - [70de2f5b-9901-4f21-94d3-d79206f3002c] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [8e9fcf43-f498-450b-8550-388d47e0a425] - Request started
2026-03-26 15:25:47 - app.access - INFO - [8e9fcf43-f498-450b-8550-388d47e0a425] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [ab603555-9464-43dc-b309-44d8f9d309b3] - Request started
2026-03-26 15:25:47 - app.access - INFO - [ab603555-9464-43dc-b309-44d8f9d309b3] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [a693760e-8abf-460f-8ca4-0eaaa567d34d] - Request started
2026-03-26 15:25:47 - app.access - INFO - [a693760e-8abf-460f-8ca4-0eaaa567d34d] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [7930f7c3-4f20-4b2d-84cd-0ff1a9c1370f] - Request started
2026-03-26 15:25:47 - app.access - INFO - [7930f7c3-4f20-4b2d-84cd-0ff1a9c1370f] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [0ce7c6a1-8f30-45cc-8da9-cb3c22f3a2d1] - Request started
2026-03-26 15:25:47 - app.access - INFO - [0ce7c6a1-8f30-45cc-8da9-cb3c22f3a2d1] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [5d03f1b2-dd30-4aca-8935-a21c08f66422] - Request started
2026-03-26 15:25:47 - app.access - INFO - [5d03f1b2-dd30-4aca-8935-a21c08f66422] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [eb69905f-40a5-4c39-ae0e-08a70231dd85] - Request started
2026-03-26 15:25:47 - app.access - INFO - [eb69905f-40a5-4c39-ae0e-08a70231dd85] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [ece3ae00-5a27-4926-a726-d75b2ad637d0] - Request started
2026-03-26 15:25:47 - app.access - INFO - [ece3ae00-5a27-4926-a726-d75b2ad637d0] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [53c5b507-482d-4db3-9326-50a430d73d65] - Request started
2026-03-26 15:25:47 - app.access - INFO - [53c5b507-482d-4db3-9326-50a430d73d65] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [908156f9-7e61-44bb-afd6-cbce8b167f84] - Request started
2026-03-26 15:25:47 - app.access - INFO - [908156f9-7e61-44bb-afd6-cbce8b167f84] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [d7683430-6c56-4739-814e-060b6956b9d6] - Request started
2026-03-26 15:25:47 - app.access - INFO - [d7683430-6c56-4739-814e-060b6956b9d6] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [775ac9c8-7dfe-4b3d-b747-01eb8c596734] - Request started
2026-03-26 15:25:47 - app.access - INFO - [775ac9c8-7dfe-4b3d-b747-01eb8c596734] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [49e39c50-9c3c-430c-a2bd-f732ab96357a] - Request started
2026-03-26 15:25:47 - app.access - INFO - [49e39c50-9c3c-430c-a2bd-f732ab96357a] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [4343b78d-4579-4691-b523-b5b0e6961daa] - Request started
2026-03-26 15:25:47 - app.access - INFO - [4343b78d-4579-4691-b523-b5b0e6961daa] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [7fed8020-07dc-45db-8ff3-451996c0d926] - Request started
2026-03-26 15:25:47 - app.access - INFO - [7fed8020-07dc-45db-8ff3-451996c0d926] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [6a2a9037-b32a-40ad-a775-9abbe653583e] - Request started
2026-03-26 15:25:47 - app.access - INFO - [6a2a9037-b32a-40ad-a775-9abbe653583e] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [f5fe871a-3c38-4e2a-b6b9-dd86790f30db] - Request started
2026-03-26 15:25:47 - app.access - INFO - [f5fe871a-3c38-4e2a-b6b9-dd86790f30db] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [094d3342-bd93-41e2-8a3a-181dc1ffb4b1] - Request started
2026-03-26 15:25:47 - app.access - INFO - [094d3342-bd93-41e2-8a3a-181dc1ffb4b1] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [560a63dc-b23c-499e-afaf-6c56bf5b8389] - Request started
2026-03-26 15:25:47 - app.access - INFO - [560a63dc-b23c-499e-afaf-6c56bf5b8389] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [64099166-3ae5-4a70-85db-175be3eb222c] - Request started
2026-03-26 15:25:47 - app.access - INFO - [64099166-3ae5-4a70-85db-175be3eb222c] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [12124d3b-4e4b-4dea-818e-5583a75b3384] - Request started
2026-03-26 15:25:47 - app.access - INFO - [12124d3b-4e4b-4dea-818e-5583a75b3384] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [6eb8bfc8-e3f7-409e-aa92-17d022c3672b] - Request started
2026-03-26 15:25:47 - app.access - INFO - [6eb8bfc8-e3f7-409e-aa92-17d022c3672b] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [5ea5b3be-0b11-4e69-832c-b0ce7ebbe71d] - Request started
2026-03-26 15:25:47 - app.access - INFO - [5ea5b3be-0b11-4e69-832c-b0ce7ebbe71d] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [e445112d-b3eb-4e21-b95a-cb3bd3282530] - Request started
2026-03-26 15:25:47 - app.access - INFO - [e445112d-b3eb-4e21-b95a-cb3bd3282530] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [085a9a9c-8c9d-4e5a-a055-0e25d6c84b26] - Request started
2026-03-26 15:25:47 - app.access - INFO - [085a9a9c-8c9d-4e5a-a055-0e25d6c84b26] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [dfc92fe9-0b75-4286-919e-f4a5da4c4d78] - Request started
2026-03-26 15:25:47 - app.access - INFO - [dfc92fe9-0b75-4286-919e-f4a5da4c4d78] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [bddd6099-b152-4ce6-a644-c62da7abcc62] - Request started
2026-03-26 15:25:47 - app.access - INFO - [bddd6099-b152-4ce6-a644-c62da7abcc62] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [9e7db7ad-7a2f-47fb-86d8-8987c6f9331b] - Request started
2026-03-26 15:25:47 - app.access - INFO - [9e7db7ad-7a2f-47fb-86d8-8987c6f9331b] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [4fbd4cea-e4c4-4015-9d1f-b90557c170aa] - Request started
2026-03-26 15:25:47 - app.access - INFO - [4fbd4cea-e4c4-4015-9d1f-b90557c170aa] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [7ed5e706-79e0-4bca-9139-7f70269e4ed4] - Request started
2026-03-26 15:25:47 - app.access - INFO - [7ed5e706-79e0-4bca-9139-7f70269e4ed4] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [4f81f4bc-7267-4b85-a3b6-9fcdbb7624a1] - Request started
2026-03-26 15:25:47 - app.access - INFO - [4f81f4bc-7267-4b85-a3b6-9fcdbb7624a1] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [fff41041-2be0-4824-8685-7d28c0180595] - Request started
2026-03-26 15:25:47 - app.access - INFO - [fff41041-2be0-4824-8685-7d28c0180595] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [d1ccd26e-9899-4c28-82fa-4d9d56649609] - Request started
2026-03-26 15:25:47 - app.access - INFO - [d1ccd26e-9899-4c28-82fa-4d9d56649609] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [db064f40-3777-4a5f-bc65-fcc828161238] - Request started
2026-03-26 15:25:47 - app.access - INFO - [db064f40-3777-4a5f-bc65-fcc828161238] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [194fc754-d0a6-49f3-b0f4-16bafb00f133] - Request started
2026-03-26 15:25:47 - app.access - INFO - [194fc754-d0a6-49f3-b0f4-16bafb00f133] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [088da2bd-8aa4-4a0f-ac39-208fbaf45241] - Request started
2026-03-26 15:25:47 - app.access - INFO - [088da2bd-8aa4-4a0f-ac39-208fbaf45241] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [cf5eaf05-7ee0-428c-bc27-576fdbc88ca3] - Request started
2026-03-26 15:25:47 - app.access - INFO - [cf5eaf05-7ee0-428c-bc27-576fdbc88ca3] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [004f8a87-f06a-4345-9332-7b0787316c2f] - Request started
2026-03-26 15:25:47 - app.access - INFO - [004f8a87-f06a-4345-9332-7b0787316c2f] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [47fcf98f-0905-4434-b8bd-2de44555e89b] - Request started
2026-03-26 15:25:47 - app.access - INFO - [47fcf98f-0905-4434-b8bd-2de44555e89b] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [0f74de93-9ea6-44cc-b1f6-a1aa09211fe7] - Request started
2026-03-26 15:25:47 - app.access - INFO - [0f74de93-9ea6-44cc-b1f6-a1aa09211fe7] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [86af020a-21b8-4712-9104-6a3a4b04f087] - Request started
2026-03-26 15:25:47 - app.access - INFO - [86af020a-21b8-4712-9104-6a3a4b04f087] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [427a99b1-50b0-40f5-8dff-9fbf3330fcb0] - Request started
2026-03-26 15:25:47 - app.access - INFO - [427a99b1-50b0-40f5-8dff-9fbf3330fcb0] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [6fab8b84-9dd6-421c-bea6-de4bd9629911] - Request started
2026-03-26 15:25:47 - app.access - INFO - [6fab8b84-9dd6-421c-bea6-de4bd9629911] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [72f53a66-2e2d-47f2-b1a8-075f33bc78f0] - Request started
2026-03-26 15:25:47 - app.access - INFO - [72f53a66-2e2d-47f2-b1a8-075f33bc78f0] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [2ce2c5e9-2ed4-4432-82d6-a9ce3dbf645e] - Request started
2026-03-26 15:25:47 - app.access - INFO - [2ce2c5e9-2ed4-4432-82d6-a9ce3dbf645e] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [9888f843-661f-4fad-ac9e-0384ca7e6cc4] - Request started
2026-03-26 15:25:47 - app.access - INFO - [9888f843-661f-4fad-ac9e-0384ca7e6cc4] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [7ecbffaa-32ac-46c9-93d0-157bad68895e] - Request started
2026-03-26 15:25:47 - app.access - INFO - [7ecbffaa-32ac-46c9-93d0-157bad68895e] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [347ab4ee-5680-4ad0-aa49-91b2d2dcf4e6] - Request started
2026-03-26 15:25:47 - app.access - INFO - [347ab4ee-5680-4ad0-aa49-91b2d2dcf4e6] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [e6a7b8d4-50f3-4714-b9ce-8217b199bc61] - Request started
2026-03-26 15:25:47 - app.access - INFO - [e6a7b8d4-50f3-4714-b9ce-8217b199bc61] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [dd1f4ac5-56ff-4b6f-8280-74887e3c2562] - Request started
2026-03-26 15:25:47 - app.access - INFO - [dd1f4ac5-56ff-4b6f-8280-74887e3c2562] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [692d68f6-d9ac-46ca-a4ae-7d52943f3158] - Request started
2026-03-26 15:25:47 - app.access - INFO - [692d68f6-d9ac-46ca-a4ae-7d52943f3158] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [e3738c15-ec49-4f99-b1a6-e9ab94604ea7] - Request started
2026-03-26 15:25:47 - app.access - INFO - [e3738c15-ec49-4f99-b1a6-e9ab94604ea7] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [f82a1a7e-38b8-40ef-b9c6-aac5e4958fe7] - Request started
2026-03-26 15:25:47 - app.access - INFO - [f82a1a7e-38b8-40ef-b9c6-aac5e4958fe7] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [d209b115-eaac-43a6-8f11-1f46e3f68097] - Request started
2026-03-26 15:25:47 - app.access - INFO - [d209b115-eaac-43a6-8f11-1f46e3f68097] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [9fd8cabb-5073-4146-ab28-93e91a944db3] - Request started
2026-03-26 15:25:47 - app.access - INFO - [9fd8cabb-5073-4146-ab28-93e91a944db3] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [3cd38ce6-a703-48e7-9bd2-17efed5fe2eb] - Request started
2026-03-26 15:25:47 - app.access - INFO - [3cd38ce6-a703-48e7-9bd2-17efed5fe2eb] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [883e3a4c-5c1b-45b5-a845-083cbc457fa1] - Request started
2026-03-26 15:25:47 - app.access - INFO - [883e3a4c-5c1b-45b5-a845-083cbc457fa1] - Request completed
2026-03-26 15:25:47 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:47 - app.access - INFO - [de33da5e-15c1-4b33-9e1e-7ebd086304af] - Request started
2026-03-26 15:25:48 - app.access - INFO - [de33da5e-15c1-4b33-9e1e-7ebd086304af] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:48 - app.access - INFO - [7b46b8ab-b03b-4344-96c9-057b0a2a620d] - Request started
2026-03-26 15:25:48 - app.access - INFO - [7b46b8ab-b03b-4344-96c9-057b0a2a620d] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:48 - app.access - INFO - [c6f0dc25-44d0-4238-b432-3ce55fab856e] - Request started
2026-03-26 15:25:48 - app.access - INFO - [c6f0dc25-44d0-4238-b432-3ce55fab856e] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:48 - app.access - INFO - [be6b6099-4f59-42eb-b66e-92bc36d4839f] - Request started
2026-03-26 15:25:48 - app.access - INFO - [be6b6099-4f59-42eb-b66e-92bc36d4839f] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:48 - app.access - INFO - [7f61e413-780c-43a5-b1e0-66444ad1c88e] - Request started
2026-03-26 15:25:48 - app.access - INFO - [7f61e413-780c-43a5-b1e0-66444ad1c88e] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:48 - app.access - INFO - [d0919753-1928-488d-b60e-caae47d02287] - Request started
2026-03-26 15:25:48 - app.access - INFO - [d0919753-1928-488d-b60e-caae47d02287] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:48 - app.access - INFO - [84644435-4872-4aaa-ac10-c0fa3ee7795b] - Request started
2026-03-26 15:25:48 - app.access - INFO - [84644435-4872-4aaa-ac10-c0fa3ee7795b] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:25:48 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:48 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:48 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:48 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:48 - app.access - INFO - [5363298a-aad4-4ea1-acc9-d7a821c36514] - Request started
2026-03-26 15:25:48 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:48 - app.access - INFO - [5363298a-aad4-4ea1-acc9-d7a821c36514] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:48 - app.access - INFO - [f0e8d65b-3a8a-4e8a-93c6-b94d77c01163] - Request started
2026-03-26 15:25:48 - app.core.permissions - INFO - [no-trace-id] - 权限允许: 用户 admin@medqc.com 执行 update 操作在 medical_records 资源上
2026-03-26 15:25:48 - app.access - INFO - [f0e8d65b-3a8a-4e8a-93c6-b94d77c01163] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/tasks/task-1/assign "HTTP/1.1 200 OK"
2026-03-26 15:25:48 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:48 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:48 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:48 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:48 - app.access - INFO - [56fc84d6-e8b9-436c-a21c-994385a9a77a] - Request started
2026-03-26 15:25:48 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:48 - app.access - INFO - [56fc84d6-e8b9-436c-a21c-994385a9a77a] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:48 - app.access - INFO - [e14be959-14dd-4b33-842b-ec64d4064c29] - Request started
2026-03-26 15:25:48 - app.access - INFO - [e14be959-14dd-4b33-842b-ec64d4064c29] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: DELETE http://testserver/api/v1/tasks/task-del-1 "HTTP/1.1 200 OK"
2026-03-26 15:25:48 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:48 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:48 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:48 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:48 - app.access - INFO - [bd813fd0-2726-45e8-8417-d95c47e5c936] - Request started
2026-03-26 15:25:48 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:48 - app.access - INFO - [bd813fd0-2726-45e8-8417-d95c47e5c936] - Request completed
2026-03-26 15:25:48 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:49 - app.access - INFO - [d2d7aa43-9592-4f04-81f8-b07a096e9779] - Request started
2026-03-26 15:25:49 - app.main - WARNING - [d2d7aa43-9592-4f04-81f8-b07a096e9779] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 15:25:49 - app.access - WARNING - [d2d7aa43-9592-4f04-81f8-b07a096e9779] - Request completed
2026-03-26 15:25:49 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/parse-medical-file-public "HTTP/1.1 429 Too Many Requests"
2026-03-26 15:25:49 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:49 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:49 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:49 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:49 - app.access - INFO - [0276e10b-7cb2-495a-89c2-363dc97b5b09] - Request started
2026-03-26 15:25:49 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:49 - app.access - INFO - [0276e10b-7cb2-495a-89c2-363dc97b5b09] - Request completed
2026-03-26 15:25:49 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:49 - app.access - INFO - [8087c53c-a7cf-4ce6-baa8-fdeba332cbb1] - Request started
2026-03-26 15:25:49 - app.main - WARNING - [8087c53c-a7cf-4ce6-baa8-fdeba332cbb1] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 15:25:49 - app.access - WARNING - [8087c53c-a7cf-4ce6-baa8-fdeba332cbb1] - Request completed
2026-03-26 15:25:49 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/batch-upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 15:25:49 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:49 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:49 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:49 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:49 - app.access - INFO - [1b2a7431-dff9-4e11-a122-5f10d5338ff1] - Request started
2026-03-26 15:25:49 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:49 - app.access - INFO - [1b2a7431-dff9-4e11-a122-5f10d5338ff1] - Request completed
2026-03-26 15:25:49 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:49 - app.access - INFO - [85c6e38b-cfef-423b-9e46-442e0269da0b] - Request started
2026-03-26 15:25:49 - app.main - WARNING - [85c6e38b-cfef-423b-9e46-442e0269da0b] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 15:25:49 - app.access - WARNING - [85c6e38b-cfef-423b-9e46-442e0269da0b] - Request completed
2026-03-26 15:25:49 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/records/upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 15:25:49 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:49 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:49 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:49 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:49 - app.access - INFO - [66df2262-b6be-44d1-832b-e25e0fe6dccd] - Request started
2026-03-26 15:25:49 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:49 - app.access - INFO - [66df2262-b6be-44d1-832b-e25e0fe6dccd] - Request completed
2026-03-26 15:25:49 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:49 - app.access - INFO - [1c782a01-1ae9-43a1-8589-52bf95990df0] - Request started
2026-03-26 15:25:49 - app.main - WARNING - [1c782a01-1ae9-43a1-8589-52bf95990df0] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:25:49 - app.access - WARNING - [1c782a01-1ae9-43a1-8589-52bf95990df0] - Request completed
2026-03-26 15:25:49 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:49 - app.access - INFO - [ae37853b-e52d-4acc-9b71-338d93d6ea72] - Request started
2026-03-26 15:25:49 - app.main - WARNING - [ae37853b-e52d-4acc-9b71-338d93d6ea72] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:25:49 - app.access - WARNING - [ae37853b-e52d-4acc-9b71-338d93d6ea72] - Request completed
2026-03-26 15:25:49 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:49 - app.access - INFO - [5230b7a1-09dc-48f0-bd41-55dae77852c0] - Request started
2026-03-26 15:25:49 - app.main - WARNING - [5230b7a1-09dc-48f0-bd41-55dae77852c0] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:25:49 - app.access - WARNING - [5230b7a1-09dc-48f0-bd41-55dae77852c0] - Request completed
2026-03-26 15:25:49 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:49 - app.access - INFO - [2a5f61e4-d585-4318-b728-fbdb24e866a8] - Request started
2026-03-26 15:25:50 - app.main - WARNING - [2a5f61e4-d585-4318-b728-fbdb24e866a8] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:25:50 - app.access - WARNING - [2a5f61e4-d585-4318-b728-fbdb24e866a8] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:50 - app.access - INFO - [3ac00610-6068-44fe-86b5-686b0906980f] - Request started
2026-03-26 15:25:50 - app.main - WARNING - [3ac00610-6068-44fe-86b5-686b0906980f] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:25:50 - app.access - WARNING - [3ac00610-6068-44fe-86b5-686b0906980f] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:50 - app.access - INFO - [439dbc64-02a4-4c93-98f9-9f768b857c90] - Request started
2026-03-26 15:25:50 - app.main - WARNING - [439dbc64-02a4-4c93-98f9-9f768b857c90] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:25:50 - app.access - WARNING - [439dbc64-02a4-4c93-98f9-9f768b857c90] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:50 - app.access - INFO - [81c1d5b7-ea89-4c8c-b160-24e2c5787bb5] - Request started
2026-03-26 15:25:50 - app.main - WARNING - [81c1d5b7-ea89-4c8c-b160-24e2c5787bb5] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:25:50 - app.access - WARNING - [81c1d5b7-ea89-4c8c-b160-24e2c5787bb5] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:50 - app.access - INFO - [8b404bf1-6f3a-4f9d-9762-b3d684b5a4cf] - Request started
2026-03-26 15:25:50 - app.main - WARNING - [8b404bf1-6f3a-4f9d-9762-b3d684b5a4cf] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:25:50 - app.access - WARNING - [8b404bf1-6f3a-4f9d-9762-b3d684b5a4cf] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:50 - app.access - INFO - [c6e9b23e-12e9-49cf-a593-fc6b67a41185] - Request started
2026-03-26 15:25:50 - app.main - WARNING - [c6e9b23e-12e9-49cf-a593-fc6b67a41185] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:25:50 - app.access - WARNING - [c6e9b23e-12e9-49cf-a593-fc6b67a41185] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:50 - app.access - INFO - [b38be39b-06df-4983-b27e-91bd748c8638] - Request started
2026-03-26 15:25:50 - app.main - WARNING - [b38be39b-06df-4983-b27e-91bd748c8638] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 15:25:50 - app.access - WARNING - [b38be39b-06df-4983-b27e-91bd748c8638] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:50 - app.access - INFO - [eaac527c-2baa-448e-b289-7cc3793582b5] - Request started
2026-03-26 15:25:50 - app.core.rate_limit - WARNING - [eaac527c-2baa-448e-b289-7cc3793582b5] - audit.rate_limit.exceeded bucket=drg_smart_upload key=drg_smart_upload:testclient method=POST path=/api/v1/drg/smart-upload
2026-03-26 15:25:50 - app.main - WARNING - [eaac527c-2baa-448e-b289-7cc3793582b5] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 15:25:50 - app.access - WARNING - [eaac527c-2baa-448e-b289-7cc3793582b5] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 15:25:50 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:50 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:50 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:50 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:50 - app.access - INFO - [7f56117a-376e-4d43-a281-cb900100882f] - Request started
2026-03-26 15:25:50 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:50 - app.access - INFO - [7f56117a-376e-4d43-a281-cb900100882f] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:50 - app.access - INFO - [4789f076-548b-496c-96bc-995647c25a20] - Request started
2026-03-26 15:25:50 - app.core.upload_security - WARNING - [4789f076-548b-496c-96bc-995647c25a20] - audit.upload.rejected reason=extension_not_allowed filename=malicious.exe content_type=application/octet-stream size_bytes=4
2026-03-26 15:25:50 - app.main - WARNING - [4789f076-548b-496c-96bc-995647c25a20] - HTTP Exception: 400 - 不支持的文件扩展名: .exe
2026-03-26 15:25:50 - app.access - WARNING - [4789f076-548b-496c-96bc-995647c25a20] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/parse-medical-file-public "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:50 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:50 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:50 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:50 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:50 - app.access - INFO - [c98ceb3f-2504-4b6a-8aee-a1007258d8d9] - Request started
2026-03-26 15:25:50 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:50 - app.access - INFO - [c98ceb3f-2504-4b6a-8aee-a1007258d8d9] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:50 - app.access - INFO - [7982985b-20c5-4948-8019-2f5d9c1d8040] - Request started
2026-03-26 15:25:50 - app.core.upload_security - WARNING - [7982985b-20c5-4948-8019-2f5d9c1d8040] - audit.upload.rejected reason=virus_scan_blocked filename=record.txt content_type=text/plain size_bytes=68
2026-03-26 15:25:50 - app.main - WARNING - [7982985b-20c5-4948-8019-2f5d9c1d8040] - HTTP Exception: 400 - 检测到潜在恶意文件签名
2026-03-26 15:25:50 - app.access - WARNING - [7982985b-20c5-4948-8019-2f5d9c1d8040] - Request completed
2026-03-26 15:25:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/records/upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:50 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:50 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:50 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:50 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:50 - app.access - INFO - [d7c0eefe-a66a-4bc9-baf4-39755e5122d5] - Request started
2026-03-26 15:25:51 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:51 - app.access - INFO - [d7c0eefe-a66a-4bc9-baf4-39755e5122d5] - Request completed
2026-03-26 15:25:51 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:51 - app.access - INFO - [10821ad5-5042-47d1-8ae6-8bb2ee63dc84] - Request started
2026-03-26 15:25:51 - app.core.upload_security - WARNING - [10821ad5-5042-47d1-8ae6-8bb2ee63dc84] - audit.upload.rejected reason=mime_not_allowed filename=sample.csv content_type=image/png size_bytes=81
2026-03-26 15:25:51 - app.main - WARNING - [10821ad5-5042-47d1-8ae6-8bb2ee63dc84] - HTTP Exception: 400 - 不支持的文件类型: image/png
2026-03-26 15:25:51 - app.access - WARNING - [10821ad5-5042-47d1-8ae6-8bb2ee63dc84] - Request completed
2026-03-26 15:25:51 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/batch-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:51 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 15:25:51 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 15:25:51 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 15:25:51 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 15:25:51 - app.access - INFO - [d23dabe0-0a3d-444a-9878-86a4e69af6e6] - Request started
2026-03-26 15:25:51 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:25:51 - app.access - INFO - [d23dabe0-0a3d-444a-9878-86a4e69af6e6] - Request completed
2026-03-26 15:25:51 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:25:51 - app.access - INFO - [d38aef05-65c5-4330-944f-72191db5a3b3] - Request started
2026-03-26 15:25:51 - app.core.upload_security - WARNING - [d38aef05-65c5-4330-944f-72191db5a3b3] - audit.upload.rejected reason=file_too_large filename=sample.csv content_type=text/csv size_bytes=10
2026-03-26 15:25:51 - app.main - WARNING - [d38aef05-65c5-4330-944f-72191db5a3b3] - HTTP Exception: 400 - 文件大小不能超过 8B
2026-03-26 15:25:51 - app.access - WARNING - [d38aef05-65c5-4330-944f-72191db5a3b3] - Request completed
2026-03-26 15:25:51 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 15:25:51 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:25:51 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:25:51 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
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
======================= 5 passed, 19 warnings in 4.11s ========================
2026-03-26 15:25:59 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:25:59 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:25:59 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:25:59 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:26:00 - app.access - INFO - [95865ff0-ee41-480a-83fd-6036149c6524] - Request started
2026-03-26 15:26:00 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=release-gate-ce6d8a761751@example.com roles=doctor trace_id=95865ff0-ee41-480a-83fd-6036149c6524 details={"assigned_roles": ["doctor"], "department": "质控科", "target_email": "release-gate-ce6d8a761751@example.com"}
2026-03-26 15:26:00 - app.access - INFO - [95865ff0-ee41-480a-83fd-6036149c6524] - Request completed
2026-03-26 15:26:00 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 15:26:00 - app.access - INFO - [d3377035-37e8-4d3c-bf27-e84b4d2ed655] - Request started
2026-03-26 15:26:00 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-ce6d8a761751@example.com
2026-03-26 15:26:00 - app.access - INFO - [d3377035-37e8-4d3c-bf27-e84b4d2ed655] - Request completed
2026-03-26 15:26:00 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:26:00 - app.access - INFO - [4a7dc885-d12c-476d-bc78-4e1295cea0c4] - Request started
2026-03-26 15:26:00 - app.access - INFO - [4a7dc885-d12c-476d-bc78-4e1295cea0c4] - Request completed
2026-03-26 15:26:00 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/auth/me "HTTP/1.1 200 OK"
2026-03-26 15:26:00 - app.access - INFO - [39ec66ca-4937-4e09-b751-98dfd4c568c3] - Request started
2026-03-26 15:26:00 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=release-gate-ce6d8a761751@example.com
2026-03-26 15:26:00 - app.access - INFO - [39ec66ca-4937-4e09-b751-98dfd4c568c3] - Request completed
2026-03-26 15:26:00 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 15:26:00 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:26:00 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:26:01 - app.access - INFO - [b0781bd3-5fee-4c5a-8ece-6570e40d7464] - Request started
2026-03-26 15:26:01 - app.main - WARNING - [b0781bd3-5fee-4c5a-8ece-6570e40d7464] - HTTP Exception: 401 - Authentication required
2026-03-26 15:26:01 - app.access - WARNING - [b0781bd3-5fee-4c5a-8ece-6570e40d7464] - Request completed
2026-03-26 15:26:01 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 15:26:01 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:26:01 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:26:01 - app.access - INFO - [eb52815b-0970-4861-adb2-cd09d390f50d] - Request started
2026-03-26 15:26:01 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=release-gate-fe9595d90176@example.com roles=doctor trace_id=eb52815b-0970-4861-adb2-cd09d390f50d details={"assigned_roles": ["doctor"], "department": "质控科", "target_email": "release-gate-fe9595d90176@example.com"}
2026-03-26 15:26:01 - app.access - INFO - [eb52815b-0970-4861-adb2-cd09d390f50d] - Request completed
2026-03-26 15:26:01 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 15:26:01 - app.access - INFO - [f9d5b550-1de4-4c4f-b5a4-b2a7cf46d13f] - Request started
2026-03-26 15:26:02 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-fe9595d90176@example.com
2026-03-26 15:26:02 - app.access - INFO - [f9d5b550-1de4-4c4f-b5a4-b2a7cf46d13f] - Request completed
2026-03-26 15:26:02 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:26:02 - app.access - INFO - [0cdbf9f0-d67f-4b66-bf3b-13564a4ace2a] - Request started
2026-03-26 15:26:02 - app.main - WARNING - [0cdbf9f0-d67f-4b66-bf3b-13564a4ace2a] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 15:26:02 - app.access - WARNING - [0cdbf9f0-d67f-4b66-bf3b-13564a4ace2a] - Request completed
2026-03-26 15:26:02 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 15:26:02 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:26:02 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:26:02 - app.access - INFO - [ae79376b-a85e-473c-bb89-a16e5b7432c5] - Request started
2026-03-26 15:26:02 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 15:26:02 - app.access - INFO - [ae79376b-a85e-473c-bb89-a16e5b7432c5] - Request completed
2026-03-26 15:26:02 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 15:26:02 - app.access - INFO - [d42baf6e-fb55-4bf2-9755-fa2f0509cc5f] - Request started
2026-03-26 15:26:02 - app.core.permissions - INFO - [no-trace-id] - 权限允许: 用户 admin@medqc.com 执行 read 操作在 medical_records 资源上
2026-03-26 15:26:02 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 15:26:02 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 15:26:03 - app.access - INFO - [d42baf6e-fb55-4bf2-9755-fa2f0509cc5f] - Request completed
2026-03-26 15:26:03 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/records?page=1&page_size=5 "HTTP/1.1 200 OK"
2026-03-26 15:26:03 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 15:26:03 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 15:26:03 - app.access - INFO - [02b6551b-e6e0-4b88-bd4e-490c3fcd3ee4] - Request started
2026-03-26 15:26:03 - app.access - INFO - [02b6551b-e6e0-4b88-bd4e-490c3fcd3ee4] - Request completed
2026-03-26 15:26:03 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 15:26:03 - app.access - INFO - [46e4160d-0628-48fb-b1c2-c1fd3d97a36c] - Request started
2026-03-26 15:26:03 - app.access - INFO - [46e4160d-0628-48fb-b1c2-c1fd3d97a36c] - Request completed
2026-03-26 15:26:03 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
```