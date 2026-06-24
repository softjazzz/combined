# Backend Release Gate Report

- total gates: 9
- passed gates: 9
- failed gates: 0
- all passed: True

## Gate Details
- auth_guard: PASS (0.12s)
  metrics: {"required_checks": 7, "passed_checks": 7, "coverage_ratio": 1.0}
- secret_hygiene: PASS (0.13s)
  metrics: {"findings": 0}
- alert_rules: PASS (0.12s)
  metrics: {"pass_marker_found": true}
- openapi_contract: PASS (20.45s)
  metrics: {"pass_marker_found": true}
- metrics_catalog: PASS (0.13s)
  metrics: {"pass_marker_found": true}
- migration_roundtrip: PASS (4.86s)
  metrics: {"head_count": 1, "head": "20260315_000002"}
- pytest_contract: PASS (41.75s)
  metrics: {"passed": 33, "failed": 0, "skipped": 0}
- pytest_security_consistency: PASS (50.71s)
  metrics: {"passed": 48, "failed": 0, "skipped": 0}
- pytest_integration_smoke: PASS (18.66s)
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
2026-03-26 14:57:19 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:57:19 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:57:20 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:20 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:21 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:21 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:21 - app.access - INFO - [75df717a-4c54-4fbd-8f18-2cc5ac2db200] - Request started
2026-03-26 14:57:22 - app.access - INFO - [75df717a-4c54-4fbd-8f18-2cc5ac2db200] - Request completed
2026-03-26 14:57:22 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
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
====================== 33 passed, 13 warnings in 13.17s =======================
2026-03-26 14:57:45 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:57:45 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:57:47 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:57:47 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:57:48 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:48 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:48 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:48 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:48 - app.access - INFO - [81be9dc2-1b32-49b2-b5f1-939a4aa45a0b] - Request started
2026-03-26 14:57:49 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:57:49 - app.access - INFO - [81be9dc2-1b32-49b2-b5f1-939a4aa45a0b] - Request completed
2026-03-26 14:57:49 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:57:49 - app.access - INFO - [34e77f30-be85-4131-b2e5-fa852c36a031] - Request started
2026-03-26 14:57:49 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 14:57:49 - app.access - INFO - [34e77f30-be85-4131-b2e5-fa852c36a031] - Request completed
2026-03-26 14:57:49 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 14:57:49 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:49 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:49 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:49 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:49 - app.access - INFO - [e1d29973-06dd-4651-8358-6948db4003a5] - Request started
2026-03-26 14:57:50 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:57:50 - app.access - INFO - [e1d29973-06dd-4651-8358-6948db4003a5] - Request completed
2026-03-26 14:57:50 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:57:50 - app.access - INFO - [56de0955-6321-474a-b3c2-da156b33ab6d] - Request started
2026-03-26 14:57:50 - app.access - INFO - [56de0955-6321-474a-b3c2-da156b33ab6d] - Request completed
2026-03-26 14:57:50 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 14:57:50 - app.access - INFO - [9caa3ff8-cc01-4377-add5-b227550ca3f1] - Request started
2026-03-26 14:57:50 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.pg.update resource=/api/v1/sync/config/pg outcome=success actor=admin@medqc.com roles=admin,qc_manager trace_id=9caa3ff8-cc01-4377-add5-b227550ca3f1 details={"changed_fields": ["remote_host", "remote_password", "remote_password_ref", "remote_port"], "connection_ok": true, "remote_host": "10.8.8.8", "remote_port": "5544"}
2026-03-26 14:57:50 - app.access - INFO - [9caa3ff8-cc01-4377-add5-b227550ca3f1] - Request completed
2026-03-26 14:57:50 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 14:57:50 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:50 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:50 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:50 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:50 - app.access - INFO - [5dd12d83-cdcd-4d76-924d-a241146071d2] - Request started
2026-03-26 14:57:51 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 14:57:51 - app.access - INFO - [5dd12d83-cdcd-4d76-924d-a241146071d2] - Request completed
2026-03-26 14:57:51 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:57:51 - app.access - INFO - [d08d0ddf-dd17-4288-be9b-d59f7d9f0095] - Request started
2026-03-26 14:57:51 - app.main - WARNING - [d08d0ddf-dd17-4288-be9b-d59f7d9f0095] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 14:57:51 - app.access - WARNING - [d08d0ddf-dd17-4288-be9b-d59f7d9f0095] - Request completed
2026-03-26 14:57:51 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 14:57:51 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:51 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:51 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:51 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:51 - app.access - INFO - [3bb600b0-d296-4df1-8bae-c3f47361dfa3] - Request started
2026-03-26 14:57:51 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:57:51 - app.access - INFO - [3bb600b0-d296-4df1-8bae-c3f47361dfa3] - Request completed
2026-03-26 14:57:51 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:57:51 - app.access - INFO - [cbda0296-4be6-48b6-8e40-2d696e61934f] - Request started
2026-03-26 14:57:51 - app.routers.qc_sichuan - INFO - [no-trace-id] - Loaded 179 Sichuan rules from JSON file
2026-03-26 14:57:51 - app.access - INFO - [cbda0296-4be6-48b6-8e40-2d696e61934f] - Request completed
2026-03-26 14:57:51 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/rules "HTTP/1.1 200 OK"
2026-03-26 14:57:51 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:51 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:51 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:51 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:51 - app.access - INFO - [2ed506c0-346e-4760-a120-692a865ce2b1] - Request started
2026-03-26 14:57:52 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:57:52 - app.access - INFO - [2ed506c0-346e-4760-a120-692a865ce2b1] - Request completed
2026-03-26 14:57:52 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:57:52 - app.access - INFO - [a265ffcc-6243-475e-b9b6-54d9d17b93fb] - Request started
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251110_041209.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251109_233517.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_234838.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_070941.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065547.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065421.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_062819.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_053504.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_021345.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_015054.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_014934.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_013113.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_005230.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\fe17a51e-5db0-4d37-ab6d-ac41cecca752_sequential_batch_20251112_130619.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f41ab06d-0f77-4f0f-ad27-e9c08fea5756_sequential_batch_20251112_143049.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f158d3cf-7fa9-4059-82e6-01e478d60399_sequential_batch_20251112_142617.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\e6cd1e70-88ac-4df9-a164-1326d35a6874_sequential_batch_20251110_064046.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\daf44f72-0baa-453b-bf32-b9355bd3bd01_sequential_batch_20251112_011112.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\defbcbd9-94e9-4723-b6df-dbf0b21ea4f7_sequential_batch_20251112_233633.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\c79d0012-c564-4d1c-bd4c-cf5aebe1fd92_sequential_batch_20251112_132237.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_083256.json: 'list' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a9c69ec9-9675-40ed-b203-5d830842a11c_sequential_batch_20251112_013953.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_082322.json: 'list' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a2bbfbe5-48de-4da8-bb47-e0cc59424775_sequential_batch_20251112_233854.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\9d5ec2a7-dc69-40dc-86ac-2c1e52f9aafd_sequential_batch_20251112_031338.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\89bb0a9d-14b9-48bc-8f67-f04f89fbb9c5_sequential_batch_20251112_031203.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\81d4a41f-bd3d-457d-aea6-1c32a412312e_sequential_batch_20251111_120900.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\818fe627-f5ad-4101-b06d-8a2addf10a71_sequential_batch_20251111_134659.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6fd14104-4d02-4b52-bc3d-a012cf4ede90_sequential_batch_20251112_232848.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6de19991-4266-4aa4-8bef-ee3001fb3ddc_sequential_batch_20251113_000427.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6154a09c-c692-4cfd-83a7-eb2773a9ad8b_sequential_batch_20251112_141218.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\5a2b1859-a0a8-436b-a4a0-af30eb6db6dc_sequential_batch_20251111_235912.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\57c72978-223b-4e01-b6ff-180e802c1718_sequential_batch_20251112_130944.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4eb1f192-80d8-48fa-8393-0c91b788d0d9_sequential_batch_20251111_235832.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4798fb59-6450-4f11-94c3-848d2702cf6c_sequential_batch_20251112_151503.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4596298c-eca7-4ca2-89ce-30ce5ae2898d_sequential_batch_20251111_012838.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\36f11425-d816-4f8a-b624-dced1ac4c164_sequential_batch_20251112_060145.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\2c59b9ef-9b2f-4ef8-b671-d0840df86da8_sequential_batch_20251112_231936.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1e2886a3-253f-4008-b4c7-da32548e5826_sequential_batch_20251111_121107.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1ca2602c-56e6-4310-b686-19a73531a8a9_sequential_batch_20251112_232958.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\13c4efdd-6bff-4ff7-aa51-2bc906aad435_sequential_batch_20251112_232048.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:57:52 - app.access - INFO - [a265ffcc-6243-475e-b9b6-54d9d17b93fb] - Request completed
2026-03-26 14:57:52 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/results/history?page=1&page_size=10 "HTTP/1.1 200 OK"
2026-03-26 14:57:52 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:52 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:52 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:52 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:52 - app.access - INFO - [83d658dd-066b-4c2b-a156-648ea091d8d9] - Request started
2026-03-26 14:57:53 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:57:53 - app.access - INFO - [83d658dd-066b-4c2b-a156-648ea091d8d9] - Request completed
2026-03-26 14:57:53 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:57:53 - app.access - INFO - [797cab23-aefa-468a-831d-5854839bfe91] - Request started
2026-03-26 14:57:53 - app.access - INFO - [797cab23-aefa-468a-831d-5854839bfe91] - Request completed
2026-03-26 14:57:53 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 200 OK"
2026-03-26 14:57:53 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:53 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:53 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:53 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:53 - app.access - INFO - [957a0340-4268-49f0-9f30-5894c609f3b9] - Request started
2026-03-26 14:57:54 - app.access - INFO - [957a0340-4268-49f0-9f30-5894c609f3b9] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:54 - app.access - INFO - [ded204df-409f-4922-8b09-ba83a3954779] - Request started
2026-03-26 14:57:54 - app.access - INFO - [ded204df-409f-4922-8b09-ba83a3954779] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK"
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:54 - app.access - INFO - [8e1d6909-aab3-4123-aa24-e1eaf3272e51] - Request started
2026-03-26 14:57:54 - app.access - INFO - [8e1d6909-aab3-4123-aa24-e1eaf3272e51] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 14:57:54 - app.access - INFO - [825b5c5c-f6e0-46a4-8913-1278207baf3c] - Request started
2026-03-26 14:57:54 - app.access - INFO - [825b5c5c-f6e0-46a4-8913-1278207baf3c] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 14:57:54 - app.access - INFO - [a03099b1-9e20-41f1-bdd6-75bda27d453c] - Request started
2026-03-26 14:57:54 - app.main - WARNING - [a03099b1-9e20-41f1-bdd6-75bda27d453c] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 14:57:54 - app.access - WARNING - [a03099b1-9e20-41f1-bdd6-75bda27d453c] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 403 Forbidden"
2026-03-26 14:57:54 - app.access - INFO - [596de0a8-f253-4544-a21b-d846e275188e] - Request started
2026-03-26 14:57:54 - app.main - WARNING - [596de0a8-f253-4544-a21b-d846e275188e] - HTTP Exception: 401 - Authentication required
2026-03-26 14:57:54 - app.access - WARNING - [596de0a8-f253-4544-a21b-d846e275188e] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 401 Unauthorized"
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:54 - app.access - INFO - [7939c5c3-3ca5-4fc5-8683-560af7d9eff8] - Request started
2026-03-26 14:57:54 - app.main - WARNING - [7939c5c3-3ca5-4fc5-8683-560af7d9eff8] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 14:57:54 - app.access - WARNING - [7939c5c3-3ca5-4fc5-8683-560af7d9eff8] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:54 - app.access - INFO - [db0fe16d-e356-4246-832c-b53e87c01638] - Request started
2026-03-26 14:57:54 - app.main - WARNING - [db0fe16d-e356-4246-832c-b53e87c01638] - Validation Error: [{'type': 'greater_than_equal', 'loc': ('body', 'lookback_minutes'), 'msg': 'Input should be greater than or equal to 0', 'input': -1, 'ctx': {'ge': 0}, 'url': 'https://errors.pydantic.dev/2.5/v/greater_than_equal'}]
2026-03-26 14:57:54 - app.access - WARNING - [db0fe16d-e356-4246-832c-b53e87c01638] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:57:54 - app.access - INFO - [34b1a8f2-48c2-4d31-ad76-44af86b1f6cd] - Request started
2026-03-26 14:57:54 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.mongo.update resource=/api/v1/sync/config/mongo outcome=success actor=sync@test.local roles=admin trace_id=34b1a8f2-48c2-4d31-ad76-44af86b1f6cd details={"changed_fields": ["connect_timeout_ms", "enabled", "inter_request_delay_ms", "lookback_minutes", "max_batch_size", "night_window_end", "night_window_start", "rescan_recent_days", "tier1_interval_minutes", "tier2_interval_minutes", "tier3_cron"], "enabled": true}
2026-03-26 14:57:54 - app.access - INFO - [34b1a8f2-48c2-4d31-ad76-44af86b1f6cd] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 200 OK"
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:54 - app.access - INFO - [81cce0fd-99ce-4a96-bcd0-716f80d4fdeb] - Request started
2026-03-26 14:57:54 - app.access - INFO - [81cce0fd-99ce-4a96-bcd0-716f80d4fdeb] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:54 - app.access - INFO - [82527298-fea8-4db6-9194-924011c1a245] - Request started
2026-03-26 14:57:54 - app.access - INFO - [82527298-fea8-4db6-9194-924011c1a245] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/test-connection/all "HTTP/1.1 200 OK"
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:54 - app.access - INFO - [381baded-2afb-46f1-bef6-4f0bfef5a3a3] - Request started
2026-03-26 14:57:54 - app.access - INFO - [381baded-2afb-46f1-bef6-4f0bfef5a3a3] - Request completed
2026-03-26 14:57:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 14:57:54 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:54 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:55 - app.access - INFO - [baf18e0f-6825-4184-8eed-6b129035654a] - Request started
2026-03-26 14:57:55 - app.access - INFO - [baf18e0f-6825-4184-8eed-6b129035654a] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:55 - app.access - INFO - [95c84fc6-23e9-497a-af06-ae2dd9967877] - Request started
2026-03-26 14:57:55 - app.audit - INFO - [no-trace-id] - audit.event action=sync.trigger resource=/api/v1/sync/trigger outcome=rejected_running actor=sync@test.local roles=admin trace_id=95c84fc6-23e9-497a-af06-ae2dd9967877 details={"idempotency_key": "mongo:all:2026-03-26:sync@test.local", "run_id": "syncrun-d5a703235a0b", "source": "mongo", "sync_date": "2026-03-26", "tier": "all"}
2026-03-26 14:57:55 - app.access - INFO - [95c84fc6-23e9-497a-af06-ae2dd9967877] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:55 - app.access - INFO - [029cb11c-11a8-4b56-be1f-75d7f0712245] - Request started
2026-03-26 14:57:55 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 14:57:55 - app.audit - INFO - [no-trace-id] - audit.event action=sync.trigger resource=/api/v1/sync/trigger outcome=success actor=sync@test.local roles=admin trace_id=029cb11c-11a8-4b56-be1f-75d7f0712245 details={"idempotency_key": "mongo:tier1:2026-03-26:sync@test.local", "run_id": "syncrun-cffac6edd112", "source": "mongo", "status": "success", "sync_date": "2026-03-26", "tier": "tier1", "total_records": 2}
2026-03-26 14:57:55 - app.access - INFO - [029cb11c-11a8-4b56-be1f-75d7f0712245] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:55 - app.access - INFO - [0ee04359-68a7-4201-8e23-132c68a078b5] - Request started
2026-03-26 14:57:55 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 14:57:55 - app.access - INFO - [0ee04359-68a7-4201-8e23-132c68a078b5] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:57:55 - app.access - INFO - [4750a751-0bcd-4983-b08c-3b025935e4a8] - Request started
2026-03-26 14:57:55 - app.access - INFO - [4750a751-0bcd-4983-b08c-3b025935e4a8] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:55 - app.access - INFO - [2599b3a5-3408-48b0-9c0a-5c8a34c50d8c] - Request started
2026-03-26 14:57:55 - app.access - INFO - [2599b3a5-3408-48b0-9c0a-5c8a34c50d8c] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/runs?source=mongo&tier=tier2&limit=20 "HTTP/1.1 200 OK"
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:55 - app.access - INFO - [993fc7aa-cb66-4ad5-88ae-580e7b56fe0a] - Request started
2026-03-26 14:57:55 - app.access - INFO - [993fc7aa-cb66-4ad5-88ae-580e7b56fe0a] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 200 OK"
2026-03-26 14:57:55 - app.access - INFO - [934e7571-b435-42ca-86f9-a8e13b8c55ce] - Request started
2026-03-26 14:57:55 - app.main - WARNING - [934e7571-b435-42ca-86f9-a8e13b8c55ce] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 14:57:55 - app.access - WARNING - [934e7571-b435-42ca-86f9-a8e13b8c55ce] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 403 Forbidden"
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:55 - app.access - INFO - [6a30ef28-271a-416e-81e6-71f21b5f7658] - Request started
2026-03-26 14:57:55 - app.audit - INFO - [no-trace-id] - audit.event action=sync.template.apply resource=/api/v1/sync/templates/apply outcome=success actor=sync@test.local roles=admin trace_id=6a30ef28-271a-416e-81e6-71f21b5f7658 details={"departments_count": 1, "enabled": false, "template_id": "single_department_focus"}
2026-03-26 14:57:55 - app.access - INFO - [6a30ef28-271a-416e-81e6-71f21b5f7658] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 200 OK"
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:55 - app.access - INFO - [3b747f6b-63c6-4b6a-9914-13b72e3c5f29] - Request started
2026-03-26 14:57:55 - app.main - WARNING - [3b747f6b-63c6-4b6a-9914-13b72e3c5f29] - HTTP Exception: 422 - 该模板必须选择科室
2026-03-26 14:57:55 - app.access - WARNING - [3b747f6b-63c6-4b6a-9914-13b72e3c5f29] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:57:55 - app.access - INFO - [a02797d0-edaa-4db0-b96a-1795ad2f7084] - Request started
2026-03-26 14:57:55 - app.main - WARNING - [a02797d0-edaa-4db0-b96a-1795ad2f7084] - HTTP Exception: 422 - 科室列表不允许同时包含 * 和具体科室
2026-03-26 14:57:55 - app.access - WARNING - [a02797d0-edaa-4db0-b96a-1795ad2f7084] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:55 - app.access - INFO - [4377865d-9a00-49bc-a114-8722ade26d41] - Request started
2026-03-26 14:57:55 - app.access - INFO - [4377865d-9a00-49bc-a114-8722ade26d41] - Request completed
2026-03-26 14:57:55 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 200 OK"
2026-03-26 14:57:55 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:55 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:56 - app.access - INFO - [9b1943d2-fdd2-45e9-b040-94c61056be38] - Request started
2026-03-26 14:57:56 - app.main - WARNING - [9b1943d2-fdd2-45e9-b040-94c61056be38] - HTTP Exception: 422 - mongo_uri 未配置
2026-03-26 14:57:56 - app.access - WARNING - [9b1943d2-fdd2-45e9-b040-94c61056be38] - Request completed
2026-03-26 14:57:56 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:56 - app.access - INFO - [a1d42973-9053-415c-9641-fddb02321476] - Request started
2026-03-26 14:57:56 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 14:57:56 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 14:57:56 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:57:56 - app.access - INFO - [a1d42973-9053-415c-9641-fddb02321476] - Request completed
2026-03-26 14:57:56 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:56 - app.access - INFO - [64d0e450-b843-41d1-b421-7ee9beb519e6] - Request started
2026-03-26 14:57:56 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:57:56 - app.access - INFO - [64d0e450-b843-41d1-b421-7ee9beb519e6] - Request completed
2026-03-26 14:57:56 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics/prometheus "HTTP/1.1 200 OK"
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:56 - app.access - INFO - [trace-client-123] - Request started
2026-03-26 14:57:56 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:57:56 - app.access - INFO - [trace-client-123] - Request completed
2026-03-26 14:57:56 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:56 - app.access - INFO - [req-client-456] - Request started
2026-03-26 14:57:56 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:57:56 - app.access - INFO - [req-client-456] - Request completed
2026-03-26 14:57:56 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:56 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request started
2026-03-26 14:57:56 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:57:56 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request completed
2026-03-26 14:57:56 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:57:56 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:56 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:57 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:57 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:57 - app.access - INFO - [ae218960-c7ac-4c50-a79e-9e25cd61a183] - Request started
2026-03-26 14:57:57 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:57:57 - app.access - INFO - [ae218960-c7ac-4c50-a79e-9e25cd61a183] - Request completed
2026-03-26 14:57:57 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:57:57 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:57 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:57 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:57 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:57 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request started
2026-03-26 14:57:57 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:57:57 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request completed
2026-03-26 14:57:57 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:57:57 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:57 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:57 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:57 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:57 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:57:57 - app.core.otel - WARNING - [no-trace-id] - OpenTelemetry dependencies unavailable, skip instrumentation: No module named 'opentelemetry'
2026-03-26 14:57:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:57:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:57:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:57:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:57:59 - app.access - INFO - [8077d8da-3fae-489f-8304-e36ba74c6435] - Request started
2026-03-26 14:57:59 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:57:59 - app.access - ERROR - [8077d8da-3fae-489f-8304-e36ba74c6435] - Request failed: boom
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
2026-03-26 14:58:00 - app.core.middleware_errors - ERROR - [8077d8da-3fae-489f-8304-e36ba74c6435] - Internal Server Error: boom
2026-03-26 14:58:00 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 500 Internal Server Error"
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
====================== 48 passed, 13 warnings in 29.04s =======================
2026-03-26 14:58:28 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:58:28 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:58:30 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.pg.update resource=/api/v1/sync/config/pg outcome=success actor=admin@medqc.com roles=admin trace_id=trace-unit-audit details={"nested": {"token": "***"}, "remote_host": "127.0.0.1", "remote_password": "***"}
2026-03-26 14:58:30 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:58:30 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:58:33 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:33 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:33 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:33 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:33 - app.access - INFO - [01fa6bba-f5ed-4f95-8142-900c89031831] - Request started
2026-03-26 14:58:33 - app.main - WARNING - [01fa6bba-f5ed-4f95-8142-900c89031831] - HTTP Exception: 401 - Authentication required
2026-03-26 14:58:33 - app.access - WARNING - [01fa6bba-f5ed-4f95-8142-900c89031831] - Request completed
2026-03-26 14:58:33 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 14:58:33 - app.access - INFO - [52ab418a-fcc4-4f7e-8b05-b8dbdb8eed46] - Request started
2026-03-26 14:58:33 - app.main - WARNING - [52ab418a-fcc4-4f7e-8b05-b8dbdb8eed46] - HTTP Exception: 401 - Authentication required
2026-03-26 14:58:33 - app.access - WARNING - [52ab418a-fcc4-4f7e-8b05-b8dbdb8eed46] - Request completed
2026-03-26 14:58:33 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/drg/config/current "HTTP/1.1 401 Unauthorized"
2026-03-26 14:58:33 - app.access - INFO - [87801588-06e0-4ef7-8dbf-3e349691118f] - Request started
2026-03-26 14:58:33 - app.main - WARNING - [87801588-06e0-4ef7-8dbf-3e349691118f] - HTTP Exception: 401 - Authentication required
2026-03-26 14:58:33 - app.access - WARNING - [87801588-06e0-4ef7-8dbf-3e349691118f] - Request completed
2026-03-26 14:58:33 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/settlement/list "HTTP/1.1 401 Unauthorized"
2026-03-26 14:58:33 - app.access - INFO - [45276868-5243-403b-80a7-008cb25726c7] - Request started
2026-03-26 14:58:33 - app.main - WARNING - [45276868-5243-403b-80a7-008cb25726c7] - HTTP Exception: 401 - Authentication required
2026-03-26 14:58:33 - app.access - WARNING - [45276868-5243-403b-80a7-008cb25726c7] - Request completed
2026-03-26 14:58:33 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 401 Unauthorized"
2026-03-26 14:58:33 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:33 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:34 - app.access - INFO - [80ece932-2e35-44ee-9f22-26c146d0ed31] - Request started
2026-03-26 14:58:34 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 14:58:34 - app.access - INFO - [80ece932-2e35-44ee-9f22-26c146d0ed31] - Request completed
2026-03-26 14:58:34 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:34 - app.access - INFO - [29bc5c87-73f8-4222-8207-a809ad3e9d10] - Request started
2026-03-26 14:58:34 - app.main - WARNING - [29bc5c87-73f8-4222-8207-a809ad3e9d10] - HTTP Exception: 403 - 此操作需要系统管理员权限
2026-03-26 14:58:34 - app.access - WARNING - [29bc5c87-73f8-4222-8207-a809ad3e9d10] - Request completed
2026-03-26 14:58:34 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 403 Forbidden"
2026-03-26 14:58:34 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:34 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:34 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:34 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:34 - app.access - INFO - [48fd1eb4-1b1f-42b9-867c-512deb5b4503] - Request started
2026-03-26 14:58:35 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:35 - app.access - INFO - [48fd1eb4-1b1f-42b9-867c-512deb5b4503] - Request completed
2026-03-26 14:58:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:35 - app.access - INFO - [9e493148-2036-44e7-8ca1-60f8f8a15a38] - Request started
2026-03-26 14:58:35 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 14:58:35 - app.access - INFO - [9e493148-2036-44e7-8ca1-60f8f8a15a38] - Request completed
2026-03-26 14:58:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 14:58:35 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:35 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:35 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:35 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:35 - app.access - INFO - [540edece-6a3f-47a6-a3d2-92212d1445f6] - Request started
2026-03-26 14:58:35 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=reset-c37d5634@medqc.com roles=doctor trace_id=540edece-6a3f-47a6-a3d2-92212d1445f6 details={"assigned_roles": ["doctor"], "department": "测试科室", "target_email": "reset-c37d5634@medqc.com"}
2026-03-26 14:58:35 - app.access - INFO - [540edece-6a3f-47a6-a3d2-92212d1445f6] - Request completed
2026-03-26 14:58:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 14:58:35 - app.access - INFO - [5bc7dbb4-92db-49d6-964e-58c66ab9caa8] - Request started
2026-03-26 14:58:35 - app.routers.auth - INFO - [no-trace-id] - auth.forgot_password.issued email=reset-c37d5634@medqc.com
2026-03-26 14:58:35 - app.access - INFO - [5bc7dbb4-92db-49d6-964e-58c66ab9caa8] - Request completed
2026-03-26 14:58:35 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/forgot-password "HTTP/1.1 200 OK"
2026-03-26 14:58:35 - app.access - INFO - [a9efdd4a-baff-49e7-b9f0-c2c9fae978e7] - Request started
2026-03-26 14:58:36 - app.routers.auth - INFO - [no-trace-id] - auth.reset_password.success email=reset-c37d5634@medqc.com
2026-03-26 14:58:36 - app.access - INFO - [a9efdd4a-baff-49e7-b9f0-c2c9fae978e7] - Request completed
2026-03-26 14:58:36 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 200 OK"
2026-03-26 14:58:36 - app.access - INFO - [5168f70e-46ff-4e28-af3b-2906e008653b] - Request started
2026-03-26 14:58:36 - app.main - WARNING - [5168f70e-46ff-4e28-af3b-2906e008653b] - HTTP Exception: 401 - 重置令牌已使用或失效
2026-03-26 14:58:36 - app.access - WARNING - [5168f70e-46ff-4e28-af3b-2906e008653b] - Request completed
2026-03-26 14:58:36 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 401 Unauthorized"
2026-03-26 14:58:36 - app.access - INFO - [e502d928-b21b-4180-8521-b628e95985c2] - Request started
2026-03-26 14:58:37 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=reset-c37d5634@medqc.com
2026-03-26 14:58:37 - app.access - INFO - [e502d928-b21b-4180-8521-b628e95985c2] - Request completed
2026-03-26 14:58:37 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:37 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:37 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:37 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:37 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:37 - app.access - INFO - [e7c53c9c-e0f5-41e3-9cdb-09c155916bf4] - Request started
2026-03-26 14:58:37 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:37 - app.access - INFO - [e7c53c9c-e0f5-41e3-9cdb-09c155916bf4] - Request completed
2026-03-26 14:58:37 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:37 - app.access - INFO - [905296d1-e7d3-403b-b433-e4c9082a16a0] - Request started
2026-03-26 14:58:37 - app.main - WARNING - [905296d1-e7d3-403b-b433-e4c9082a16a0] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/db/config. Please use /api/v1/sync/*
2026-03-26 14:58:37 - app.access - WARNING - [905296d1-e7d3-403b-b433-e4c9082a16a0] - Request completed
2026-03-26 14:58:37 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/system/db/config "HTTP/1.1 410 Gone"
2026-03-26 14:58:37 - app.access - INFO - [4347ef77-63ad-4d6f-890d-4a0756005bb4] - Request started
2026-03-26 14:58:37 - app.main - WARNING - [4347ef77-63ad-4d6f-890d-4a0756005bb4] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/sync/trigger. Please use /api/v1/sync/*
2026-03-26 14:58:37 - app.access - WARNING - [4347ef77-63ad-4d6f-890d-4a0756005bb4] - Request completed
2026-03-26 14:58:37 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/system/sync/trigger "HTTP/1.1 410 Gone"
2026-03-26 14:58:37 - app.services.etl_sync - INFO - [no-trace-id] - 同步 病案首页 (web.mr)...
2026-03-26 14:58:37 - app.services.etl_sync - INFO - [no-trace-id] -   \u2705 病案首页: 1 条
2026-03-26 14:58:37 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:37 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:37 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:37 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:37 - app.access - INFO - [83645744-6d13-43db-9550-953da8c8253c] - Request started
2026-03-26 14:58:37 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 14:58:37 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 14:58:38 - app.access - INFO - [83645744-6d13-43db-9550-953da8c8253c] - Request completed
2026-03-26 14:58:38 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:38 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:38 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:38 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:38 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:38 - app.access - INFO - [f5b11aed-dc4d-4b24-b896-6bf4a33fa5f9] - Request started
2026-03-26 14:58:38 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:58:38 - app.access - INFO - [f5b11aed-dc4d-4b24-b896-6bf4a33fa5f9] - Request completed
2026-03-26 14:58:38 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:58:38 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:38 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:38 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:38 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:38 - app.access - INFO - [05036122-fab0-4855-af60-37cf46f827c7] - Request started
2026-03-26 14:58:38 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:58:38 - app.access - INFO - [05036122-fab0-4855-af60-37cf46f827c7] - Request completed
2026-03-26 14:58:38 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics/prometheus "HTTP/1.1 200 OK"
2026-03-26 14:58:38 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:38 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:38 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:38 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:38 - app.access - INFO - [23a91b96-50fe-455d-aea4-3de1fe10624c] - Request started
2026-03-26 14:58:38 - app.access - INFO - [23a91b96-50fe-455d-aea4-3de1fe10624c] - Request completed
2026-03-26 14:58:38 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 14:58:38 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:38 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:38 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:38 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:38 - app.access - INFO - [82636f0a-14ac-40b1-b8d7-e02d88e8ff69] - Request started
2026-03-26 14:58:38 - app.access - WARNING - [82636f0a-14ac-40b1-b8d7-e02d88e8ff69] - Request completed
2026-03-26 14:58:38 - httpx - INFO - [no-trace-id] - HTTP Request: OPTIONS http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 14:58:38 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:38 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:38 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:38 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:38 - app.access - INFO - [4f883e52-01c1-4854-986b-43076b85df99] - Request started
2026-03-26 14:58:39 - app.access - INFO - [4f883e52-01c1-4854-986b-43076b85df99] - Request completed
2026-03-26 14:58:39 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:39 - app.access - INFO - [34b24e86-f8bd-4bb9-acc5-cf6b851c0a09] - Request started
2026-03-26 14:58:39 - app.access - INFO - [34b24e86-f8bd-4bb9-acc5-cf6b851c0a09] - Request completed
2026-03-26 14:58:39 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:39 - app.access - INFO - [8517f002-1148-4040-b2d1-fde1619fe6f1] - Request started
2026-03-26 14:58:39 - app.access - INFO - [8517f002-1148-4040-b2d1-fde1619fe6f1] - Request completed
2026-03-26 14:58:39 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:39 - app.access - INFO - [3ee2e5ad-1c82-4b4b-9bdd-e04ad319acd6] - Request started
2026-03-26 14:58:39 - app.access - INFO - [3ee2e5ad-1c82-4b4b-9bdd-e04ad319acd6] - Request completed
2026-03-26 14:58:39 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:39 - app.access - INFO - [c172671b-a07f-434b-a220-89ee5841bc96] - Request started
2026-03-26 14:58:39 - app.access - INFO - [c172671b-a07f-434b-a220-89ee5841bc96] - Request completed
2026-03-26 14:58:39 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:39 - app.access - INFO - [b5080178-db22-44fb-b5c5-525ab7ddc1fb] - Request started
2026-03-26 14:58:39 - app.access - INFO - [b5080178-db22-44fb-b5c5-525ab7ddc1fb] - Request completed
2026-03-26 14:58:39 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:39 - app.access - INFO - [9981feb8-2fc2-4b5b-9100-ec3b9d1c7718] - Request started
2026-03-26 14:58:39 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:58:39 - app.access - INFO - [9981feb8-2fc2-4b5b-9100-ec3b9d1c7718] - Request completed
2026-03-26 14:58:39 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:39 - app.access - INFO - [92313727-1795-4a10-9a54-15295b077e79] - Request started
2026-03-26 14:58:39 - app.access - WARNING - [92313727-1795-4a10-9a54-15295b077e79] - Request completed
2026-03-26 14:58:39 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/nonexistent "HTTP/1.1 404 Not Found"
2026-03-26 14:58:39 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:39 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:40 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:40 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:40 - app.access - INFO - [bed9a1ea-35f4-4a2c-94ad-4e1df9fc48c6] - Request started
2026-03-26 14:58:40 - app.access - WARNING - [bed9a1ea-35f4-4a2c-94ad-4e1df9fc48c6] - Request completed
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 14:58:40 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:40 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:40 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:40 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:40 - app.access - INFO - [69128391-ca3c-4ace-a687-062a9dbf3748] - Request started
2026-03-26 14:58:40 - app.access - INFO - [63934b76-ed8b-4ed7-a3aa-d965512b1b9b] - Request started
2026-03-26 14:58:40 - app.access - INFO - [b37ef43f-2f93-4602-bab0-6db595f6f13e] - Request started
2026-03-26 14:58:40 - app.access - INFO - [69128391-ca3c-4ace-a687-062a9dbf3748] - Request completed
2026-03-26 14:58:40 - app.access - INFO - [45a37fe0-3c6d-4f3f-a6b3-4a5d68bf060f] - Request started
2026-03-26 14:58:40 - app.access - INFO - [dee2d073-961c-46f1-bc53-b1bf3dcb8170] - Request started
2026-03-26 14:58:40 - app.access - INFO - [30acba2e-f1ef-4582-861b-99008fc35817] - Request started
2026-03-26 14:58:40 - app.access - INFO - [83aa1906-2b9b-484a-bca5-3c80b4f88603] - Request started
2026-03-26 14:58:40 - app.access - INFO - [99fa3968-c114-43ef-9979-b0d9f266b6ae] - Request started
2026-03-26 14:58:40 - app.access - INFO - [50ba276d-aaa0-42ac-9e2d-3eb517d9291f] - Request started
2026-03-26 14:58:40 - app.access - INFO - [d39aaec7-0cfb-4f8b-b9cc-849b3fed3ee8] - Request started
2026-03-26 14:58:40 - app.access - INFO - [63934b76-ed8b-4ed7-a3aa-d965512b1b9b] - Request completed
2026-03-26 14:58:40 - app.access - INFO - [b37ef43f-2f93-4602-bab0-6db595f6f13e] - Request completed
2026-03-26 14:58:40 - app.access - INFO - [45a37fe0-3c6d-4f3f-a6b3-4a5d68bf060f] - Request completed
2026-03-26 14:58:40 - app.access - INFO - [dee2d073-961c-46f1-bc53-b1bf3dcb8170] - Request completed
2026-03-26 14:58:40 - app.access - INFO - [30acba2e-f1ef-4582-861b-99008fc35817] - Request completed
2026-03-26 14:58:40 - app.access - INFO - [83aa1906-2b9b-484a-bca5-3c80b4f88603] - Request completed
2026-03-26 14:58:40 - app.access - INFO - [99fa3968-c114-43ef-9979-b0d9f266b6ae] - Request completed
2026-03-26 14:58:40 - app.access - INFO - [50ba276d-aaa0-42ac-9e2d-3eb517d9291f] - Request completed
2026-03-26 14:58:40 - app.access - INFO - [d39aaec7-0cfb-4f8b-b9cc-849b3fed3ee8] - Request completed
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:40 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:40 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:40 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:40 - app.access - INFO - [c00968db-5baf-4d7e-b7d9-075df076f9ec] - Request started
2026-03-26 14:58:40 - app.access - INFO - [c00968db-5baf-4d7e-b7d9-075df076f9ec] - Request completed
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:40 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:40 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:40 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:40 - app.access - INFO - [33cbe820-2dea-486c-a4e0-30376a974aad] - Request started
2026-03-26 14:58:40 - app.access - INFO - [33cbe820-2dea-486c-a4e0-30376a974aad] - Request completed
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:40 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:40 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:40 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:40 - app.access - INFO - [2793571a-23db-463b-a002-9b35176850b7] - Request started
2026-03-26 14:58:40 - app.access - INFO - [2793571a-23db-463b-a002-9b35176850b7] - Request completed
2026-03-26 14:58:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:40 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:40 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:41 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:41 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:41 - app.access - INFO - [2dfd1c88-5202-46a8-ac15-d64795b2b152] - Request started
2026-03-26 14:58:41 - app.access - INFO - [2dfd1c88-5202-46a8-ac15-d64795b2b152] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health?test=1&test=2 "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:41 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:41 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:41 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:41 - app.access - INFO - [9338dbe6-31da-494a-873b-22fce9b1d145] - Request started
2026-03-26 14:58:41 - app.access - INFO - [9338dbe6-31da-494a-873b-22fce9b1d145] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [07223dac-2fbf-44e8-ad1a-689a12badd31] - Request started
2026-03-26 14:58:41 - app.access - INFO - [07223dac-2fbf-44e8-ad1a-689a12badd31] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [a984f522-341b-40f0-8f14-313511411c37] - Request started
2026-03-26 14:58:41 - app.access - INFO - [a984f522-341b-40f0-8f14-313511411c37] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [47479f8f-6a2f-4213-8522-a38a24dcdb54] - Request started
2026-03-26 14:58:41 - app.access - INFO - [47479f8f-6a2f-4213-8522-a38a24dcdb54] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [1dbb0814-3f75-4223-ac14-5c959a87dad0] - Request started
2026-03-26 14:58:41 - app.access - INFO - [1dbb0814-3f75-4223-ac14-5c959a87dad0] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [9c4b9465-9eb9-43e1-a851-7af5316824dc] - Request started
2026-03-26 14:58:41 - app.access - INFO - [9c4b9465-9eb9-43e1-a851-7af5316824dc] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [99ac0773-39ed-4fc0-a496-89a4def81051] - Request started
2026-03-26 14:58:41 - app.access - INFO - [99ac0773-39ed-4fc0-a496-89a4def81051] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [ddbd3bfb-f2cd-4848-bed2-4064c79af0dd] - Request started
2026-03-26 14:58:41 - app.access - INFO - [ddbd3bfb-f2cd-4848-bed2-4064c79af0dd] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [1024f9e3-84aa-484b-874a-14fdc1bb3407] - Request started
2026-03-26 14:58:41 - app.access - INFO - [1024f9e3-84aa-484b-874a-14fdc1bb3407] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [4b3a5851-c03e-4529-be2b-c9d4a1f1257f] - Request started
2026-03-26 14:58:41 - app.access - INFO - [4b3a5851-c03e-4529-be2b-c9d4a1f1257f] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [214a6d0c-2d5d-4f19-aad6-a51af8a5902c] - Request started
2026-03-26 14:58:41 - app.access - INFO - [214a6d0c-2d5d-4f19-aad6-a51af8a5902c] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [cda22786-75c5-45ee-82ba-1d54eb91d689] - Request started
2026-03-26 14:58:41 - app.access - INFO - [cda22786-75c5-45ee-82ba-1d54eb91d689] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [8629117e-d638-4d01-bc97-645cf04f2070] - Request started
2026-03-26 14:58:41 - app.access - INFO - [8629117e-d638-4d01-bc97-645cf04f2070] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [992d77df-dc63-4d69-8373-c02ab39b7f08] - Request started
2026-03-26 14:58:41 - app.access - INFO - [992d77df-dc63-4d69-8373-c02ab39b7f08] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [7b7686ee-f826-4190-a62e-73520dc0be81] - Request started
2026-03-26 14:58:41 - app.access - INFO - [7b7686ee-f826-4190-a62e-73520dc0be81] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [7ca3e3c3-ad00-44a7-bc4b-23c0561326d3] - Request started
2026-03-26 14:58:41 - app.access - INFO - [7ca3e3c3-ad00-44a7-bc4b-23c0561326d3] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [ee6d03d1-072f-432d-a193-b117fe070c66] - Request started
2026-03-26 14:58:41 - app.access - INFO - [ee6d03d1-072f-432d-a193-b117fe070c66] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [c12b8603-8d1e-440e-b3b2-4963a3b254d9] - Request started
2026-03-26 14:58:41 - app.access - INFO - [c12b8603-8d1e-440e-b3b2-4963a3b254d9] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [a7a65e5e-9dbe-4646-80c3-b2e2de1330a9] - Request started
2026-03-26 14:58:41 - app.access - INFO - [a7a65e5e-9dbe-4646-80c3-b2e2de1330a9] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [92f428ec-c6e4-49ef-8ea5-b96865fc65f3] - Request started
2026-03-26 14:58:41 - app.access - INFO - [92f428ec-c6e4-49ef-8ea5-b96865fc65f3] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [3e130514-9ebb-4094-b8f6-37c0388c4e34] - Request started
2026-03-26 14:58:41 - app.access - INFO - [3e130514-9ebb-4094-b8f6-37c0388c4e34] - Request completed
2026-03-26 14:58:41 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:41 - app.access - INFO - [5d2dd62d-db79-489b-b5d0-b3eab4a5d563] - Request started
2026-03-26 14:58:42 - app.access - INFO - [5d2dd62d-db79-489b-b5d0-b3eab4a5d563] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [d97a1437-dccf-4582-9a68-1590724fc5ff] - Request started
2026-03-26 14:58:42 - app.access - INFO - [d97a1437-dccf-4582-9a68-1590724fc5ff] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [4b42b7a1-992b-476a-bcc0-6a6580d3acb3] - Request started
2026-03-26 14:58:42 - app.access - INFO - [4b42b7a1-992b-476a-bcc0-6a6580d3acb3] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [42a575c3-d4e9-4f77-a6a9-edbbc1ac03e1] - Request started
2026-03-26 14:58:42 - app.access - INFO - [42a575c3-d4e9-4f77-a6a9-edbbc1ac03e1] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [a8d3eaca-b92c-4859-a064-41e29d45e2b7] - Request started
2026-03-26 14:58:42 - app.access - INFO - [a8d3eaca-b92c-4859-a064-41e29d45e2b7] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [3fc73b17-4599-4500-aa8f-020feb2cbebd] - Request started
2026-03-26 14:58:42 - app.access - INFO - [3fc73b17-4599-4500-aa8f-020feb2cbebd] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [6d3710d0-ab80-439e-b5ac-34e231d74f9d] - Request started
2026-03-26 14:58:42 - app.access - INFO - [6d3710d0-ab80-439e-b5ac-34e231d74f9d] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [e5787518-a630-4c62-b689-83d1c145980c] - Request started
2026-03-26 14:58:42 - app.access - INFO - [e5787518-a630-4c62-b689-83d1c145980c] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [8867ba0b-e220-4c3b-ab84-f45fc92b7a8e] - Request started
2026-03-26 14:58:42 - app.access - INFO - [8867ba0b-e220-4c3b-ab84-f45fc92b7a8e] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [4a89d43b-27c4-40ea-a014-32c8e1f806c1] - Request started
2026-03-26 14:58:42 - app.access - INFO - [4a89d43b-27c4-40ea-a014-32c8e1f806c1] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [3c22d961-9d17-43ed-81c2-add6b9980f6a] - Request started
2026-03-26 14:58:42 - app.access - INFO - [3c22d961-9d17-43ed-81c2-add6b9980f6a] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [9fb22a3b-5820-4aa0-b5da-4e90ca4a631d] - Request started
2026-03-26 14:58:42 - app.access - INFO - [9fb22a3b-5820-4aa0-b5da-4e90ca4a631d] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [29737305-04b7-412a-9313-e8660a93e288] - Request started
2026-03-26 14:58:42 - app.access - INFO - [29737305-04b7-412a-9313-e8660a93e288] - Request completed
2026-03-26 14:58:42 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:42 - app.access - INFO - [aa4654f0-9045-45ba-9f04-8a8228225877] - Request started
2026-03-26 14:58:42 - app.access - INFO - [aa4654f0-9045-45ba-9f04-8a8228225877] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [3345e20d-96a9-4c92-918b-db39b1d3b91e] - Request started
2026-03-26 14:58:43 - app.access - INFO - [3345e20d-96a9-4c92-918b-db39b1d3b91e] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [4774a0f1-0446-4487-98b9-97f7cb591b64] - Request started
2026-03-26 14:58:43 - app.access - INFO - [4774a0f1-0446-4487-98b9-97f7cb591b64] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [0a5f5dae-15cf-4a93-9930-de7b2d12a115] - Request started
2026-03-26 14:58:43 - app.access - INFO - [0a5f5dae-15cf-4a93-9930-de7b2d12a115] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [b3b59ece-aa40-473d-a3f9-e77842fe4983] - Request started
2026-03-26 14:58:43 - app.access - INFO - [b3b59ece-aa40-473d-a3f9-e77842fe4983] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [75250747-d1cb-424f-966d-8513d7c1e97f] - Request started
2026-03-26 14:58:43 - app.access - INFO - [75250747-d1cb-424f-966d-8513d7c1e97f] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [3d14dd76-1197-4f53-bb7d-11576e61b35d] - Request started
2026-03-26 14:58:43 - app.access - INFO - [3d14dd76-1197-4f53-bb7d-11576e61b35d] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [ca67bf1f-5f0c-4998-92a0-b2211bf47b1f] - Request started
2026-03-26 14:58:43 - app.access - INFO - [ca67bf1f-5f0c-4998-92a0-b2211bf47b1f] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [70be1c70-eff0-4ddd-bf04-cbedbc762a2e] - Request started
2026-03-26 14:58:43 - app.access - INFO - [70be1c70-eff0-4ddd-bf04-cbedbc762a2e] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [490b9bf0-4457-4b37-95b5-0d6f9086b553] - Request started
2026-03-26 14:58:43 - app.access - INFO - [490b9bf0-4457-4b37-95b5-0d6f9086b553] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [d0e038a1-fc66-4b5f-b61e-028e3eac2e16] - Request started
2026-03-26 14:58:43 - app.access - INFO - [d0e038a1-fc66-4b5f-b61e-028e3eac2e16] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [5767aeb0-8dd2-431c-b18d-6e89487de3cd] - Request started
2026-03-26 14:58:43 - app.access - INFO - [5767aeb0-8dd2-431c-b18d-6e89487de3cd] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [1c218313-f281-4560-abd7-f23835fada43] - Request started
2026-03-26 14:58:43 - app.access - INFO - [1c218313-f281-4560-abd7-f23835fada43] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [65cc247d-5dc7-42c6-956d-b450da37c791] - Request started
2026-03-26 14:58:43 - app.access - INFO - [65cc247d-5dc7-42c6-956d-b450da37c791] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [f3e2ddad-896f-46b1-89c3-69fe519d8d55] - Request started
2026-03-26 14:58:43 - app.access - INFO - [f3e2ddad-896f-46b1-89c3-69fe519d8d55] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [3e8dfe69-310c-41f8-8b6f-f55f8b3af846] - Request started
2026-03-26 14:58:43 - app.access - INFO - [3e8dfe69-310c-41f8-8b6f-f55f8b3af846] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [8c2efead-f237-4d29-a2da-5fa86ebfa152] - Request started
2026-03-26 14:58:43 - app.access - INFO - [8c2efead-f237-4d29-a2da-5fa86ebfa152] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [dc7dee01-e051-486a-9135-fc0b4066eafd] - Request started
2026-03-26 14:58:43 - app.access - INFO - [dc7dee01-e051-486a-9135-fc0b4066eafd] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [8f46e508-8fc4-4dfd-88a0-d0667acfcad8] - Request started
2026-03-26 14:58:43 - app.access - INFO - [8f46e508-8fc4-4dfd-88a0-d0667acfcad8] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [cd9ab4dd-ab9c-4c63-b90e-570fb16d6f4c] - Request started
2026-03-26 14:58:43 - app.access - INFO - [cd9ab4dd-ab9c-4c63-b90e-570fb16d6f4c] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [947ef307-9a5b-4d80-a595-2481e8d64335] - Request started
2026-03-26 14:58:43 - app.access - INFO - [947ef307-9a5b-4d80-a595-2481e8d64335] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [5f03ac07-72bf-4504-8244-fb679b4a6229] - Request started
2026-03-26 14:58:43 - app.access - INFO - [5f03ac07-72bf-4504-8244-fb679b4a6229] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [69897ead-e49a-46f8-9956-bdabacc0e4fd] - Request started
2026-03-26 14:58:43 - app.access - INFO - [69897ead-e49a-46f8-9956-bdabacc0e4fd] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [625e75fb-76a0-4c56-b1c1-46d6eb291b2e] - Request started
2026-03-26 14:58:43 - app.access - INFO - [625e75fb-76a0-4c56-b1c1-46d6eb291b2e] - Request completed
2026-03-26 14:58:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:43 - app.access - INFO - [b003e4dc-cef4-420d-8d9a-efdfbb6a3629] - Request started
2026-03-26 14:58:44 - app.access - INFO - [b003e4dc-cef4-420d-8d9a-efdfbb6a3629] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [0a701e44-2dd3-4096-9012-fb471009cbb7] - Request started
2026-03-26 14:58:44 - app.access - INFO - [0a701e44-2dd3-4096-9012-fb471009cbb7] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [081730b3-69b8-4f8a-a103-c5e91d3337c8] - Request started
2026-03-26 14:58:44 - app.access - INFO - [081730b3-69b8-4f8a-a103-c5e91d3337c8] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [7d796a47-3ea5-44f3-8ac8-2e44d8603c0e] - Request started
2026-03-26 14:58:44 - app.access - INFO - [7d796a47-3ea5-44f3-8ac8-2e44d8603c0e] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [b4dadee5-ecc7-4879-b919-e38a7159a8d2] - Request started
2026-03-26 14:58:44 - app.access - INFO - [b4dadee5-ecc7-4879-b919-e38a7159a8d2] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [598d2960-f422-499c-9905-e73b971af949] - Request started
2026-03-26 14:58:44 - app.access - INFO - [598d2960-f422-499c-9905-e73b971af949] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [ac79ca66-c4f8-4ab7-983a-44650490f6fc] - Request started
2026-03-26 14:58:44 - app.access - INFO - [ac79ca66-c4f8-4ab7-983a-44650490f6fc] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [e77a250d-a0d9-44c8-a5a0-92eb27562c81] - Request started
2026-03-26 14:58:44 - app.access - INFO - [e77a250d-a0d9-44c8-a5a0-92eb27562c81] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [2001623c-e326-4266-9fc2-fa2a7096893e] - Request started
2026-03-26 14:58:44 - app.access - INFO - [2001623c-e326-4266-9fc2-fa2a7096893e] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [9c5ddd8a-7f20-424d-80f1-72b03415c5c3] - Request started
2026-03-26 14:58:44 - app.access - INFO - [9c5ddd8a-7f20-424d-80f1-72b03415c5c3] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [39e8b95d-ef3b-4635-877c-39464439b1bb] - Request started
2026-03-26 14:58:44 - app.access - INFO - [39e8b95d-ef3b-4635-877c-39464439b1bb] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [af4415b0-235c-48dd-88e6-a7e5e8b79dc7] - Request started
2026-03-26 14:58:44 - app.access - INFO - [af4415b0-235c-48dd-88e6-a7e5e8b79dc7] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [2ea6a03e-73cd-44d2-8210-473c65dddb5e] - Request started
2026-03-26 14:58:44 - app.access - INFO - [2ea6a03e-73cd-44d2-8210-473c65dddb5e] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [5c2f801a-bede-4e29-8dea-87dcb56b785c] - Request started
2026-03-26 14:58:44 - app.access - INFO - [5c2f801a-bede-4e29-8dea-87dcb56b785c] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [1b99ba12-e6eb-4e1b-8b5a-96a5db0c60f6] - Request started
2026-03-26 14:58:44 - app.access - INFO - [1b99ba12-e6eb-4e1b-8b5a-96a5db0c60f6] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [985e5c3a-30e1-4169-9307-67232f14ebc9] - Request started
2026-03-26 14:58:44 - app.access - INFO - [985e5c3a-30e1-4169-9307-67232f14ebc9] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [28dcbbe8-f4dd-4402-bd1f-cb1a7f8aabbf] - Request started
2026-03-26 14:58:44 - app.access - INFO - [28dcbbe8-f4dd-4402-bd1f-cb1a7f8aabbf] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [5e49fe3b-4dd3-4b3d-b2de-3bc8d78883bc] - Request started
2026-03-26 14:58:44 - app.access - INFO - [5e49fe3b-4dd3-4b3d-b2de-3bc8d78883bc] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [0f20e968-6335-4464-906c-b8bfc67ab5aa] - Request started
2026-03-26 14:58:44 - app.access - INFO - [0f20e968-6335-4464-906c-b8bfc67ab5aa] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [ff80192e-8e36-4c02-a796-88e299f681e5] - Request started
2026-03-26 14:58:44 - app.access - INFO - [ff80192e-8e36-4c02-a796-88e299f681e5] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [fade2311-3213-4b10-ad1c-e0c9bdd7d713] - Request started
2026-03-26 14:58:44 - app.access - INFO - [fade2311-3213-4b10-ad1c-e0c9bdd7d713] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [8ea303a4-7b7e-47ea-bca3-cae8692fdc72] - Request started
2026-03-26 14:58:44 - app.access - INFO - [8ea303a4-7b7e-47ea-bca3-cae8692fdc72] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [c12a6a0a-bbd2-49c6-9f50-85f5ad6b7995] - Request started
2026-03-26 14:58:44 - app.access - INFO - [c12a6a0a-bbd2-49c6-9f50-85f5ad6b7995] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [e2529829-b51e-448c-a704-4c5047a43c0b] - Request started
2026-03-26 14:58:44 - app.access - INFO - [e2529829-b51e-448c-a704-4c5047a43c0b] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [8a0ecc29-c074-4626-9843-0c5db9acb8ee] - Request started
2026-03-26 14:58:44 - app.access - INFO - [8a0ecc29-c074-4626-9843-0c5db9acb8ee] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [7366fbee-fc53-4bee-a6f6-2721358b13ce] - Request started
2026-03-26 14:58:44 - app.access - INFO - [7366fbee-fc53-4bee-a6f6-2721358b13ce] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [8b4829e0-bd00-45c5-ab0a-4d33bfeb3c7e] - Request started
2026-03-26 14:58:44 - app.access - INFO - [8b4829e0-bd00-45c5-ab0a-4d33bfeb3c7e] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [64d676c1-c131-4aad-b962-68149d799f56] - Request started
2026-03-26 14:58:44 - app.access - INFO - [64d676c1-c131-4aad-b962-68149d799f56] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [a6d50455-4326-4778-8a75-6d154f58851b] - Request started
2026-03-26 14:58:44 - app.access - INFO - [a6d50455-4326-4778-8a75-6d154f58851b] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:44 - app.access - INFO - [bd017a7e-6626-4e81-9599-4361b537c4d0] - Request started
2026-03-26 14:58:44 - app.access - INFO - [bd017a7e-6626-4e81-9599-4361b537c4d0] - Request completed
2026-03-26 14:58:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [c7e5cfe3-f973-42b8-83fd-0e4202777c5e] - Request started
2026-03-26 14:58:45 - app.access - INFO - [c7e5cfe3-f973-42b8-83fd-0e4202777c5e] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [1727c91e-5383-42bb-96c5-7ff595d5a6d9] - Request started
2026-03-26 14:58:45 - app.access - INFO - [1727c91e-5383-42bb-96c5-7ff595d5a6d9] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [2326ab2e-e237-42a0-9f0a-730b780df4da] - Request started
2026-03-26 14:58:45 - app.access - INFO - [2326ab2e-e237-42a0-9f0a-730b780df4da] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [6155b078-6da0-43bc-85e7-c13d9b64dc50] - Request started
2026-03-26 14:58:45 - app.access - INFO - [6155b078-6da0-43bc-85e7-c13d9b64dc50] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [ac9b0570-d823-438b-ba6b-caa4a6d9503c] - Request started
2026-03-26 14:58:45 - app.access - INFO - [ac9b0570-d823-438b-ba6b-caa4a6d9503c] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [9a222eaa-18b9-4903-a730-9ae0369ca9e0] - Request started
2026-03-26 14:58:45 - app.access - INFO - [9a222eaa-18b9-4903-a730-9ae0369ca9e0] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [a86d468a-97bc-4fa2-8f1a-8b5055b69613] - Request started
2026-03-26 14:58:45 - app.access - INFO - [a86d468a-97bc-4fa2-8f1a-8b5055b69613] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [dafb129c-fa3d-421d-9ad0-74e22ffc9d18] - Request started
2026-03-26 14:58:45 - app.access - INFO - [dafb129c-fa3d-421d-9ad0-74e22ffc9d18] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [62dab2a2-a142-4b10-b21c-5d6eb7c5e3aa] - Request started
2026-03-26 14:58:45 - app.access - INFO - [62dab2a2-a142-4b10-b21c-5d6eb7c5e3aa] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [cde5647e-ae25-4015-a3d3-07e37fe8460f] - Request started
2026-03-26 14:58:45 - app.access - INFO - [cde5647e-ae25-4015-a3d3-07e37fe8460f] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [54991f84-2ba9-4528-9868-2244784c710a] - Request started
2026-03-26 14:58:45 - app.access - INFO - [54991f84-2ba9-4528-9868-2244784c710a] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.access - INFO - [27f26d0c-fe21-4be4-852e-7b5d14b15f2f] - Request started
2026-03-26 14:58:45 - app.access - INFO - [27f26d0c-fe21-4be4-852e-7b5d14b15f2f] - Request completed
2026-03-26 14:58:45 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:58:45 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:45 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:45 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:45 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:45 - app.access - INFO - [ca168b7d-19cf-47d9-a89c-b865afc32f1c] - Request started
2026-03-26 14:58:46 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:46 - app.access - INFO - [ca168b7d-19cf-47d9-a89c-b865afc32f1c] - Request completed
2026-03-26 14:58:46 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:46 - app.access - INFO - [f745f700-bf74-405f-970b-662ad8790aa2] - Request started
2026-03-26 14:58:46 - app.core.permissions - INFO - [no-trace-id] - 权限允许: 用户 admin@medqc.com 执行 update 操作在 medical_records 资源上
2026-03-26 14:58:46 - app.access - INFO - [f745f700-bf74-405f-970b-662ad8790aa2] - Request completed
2026-03-26 14:58:46 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/tasks/task-1/assign "HTTP/1.1 200 OK"
2026-03-26 14:58:46 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:46 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:46 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:46 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:46 - app.access - INFO - [ebc3a495-0414-4180-88cd-c66e6ef628be] - Request started
2026-03-26 14:58:47 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:47 - app.access - INFO - [ebc3a495-0414-4180-88cd-c66e6ef628be] - Request completed
2026-03-26 14:58:47 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:47 - app.access - INFO - [cb36b650-968e-42e2-93f2-d7426a4b58f0] - Request started
2026-03-26 14:58:47 - app.access - INFO - [cb36b650-968e-42e2-93f2-d7426a4b58f0] - Request completed
2026-03-26 14:58:47 - httpx - INFO - [no-trace-id] - HTTP Request: DELETE http://testserver/api/v1/tasks/task-del-1 "HTTP/1.1 200 OK"
2026-03-26 14:58:47 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:47 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:47 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:47 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:47 - app.access - INFO - [8f6db789-c8a4-4892-9ce3-fd1793d222c2] - Request started
2026-03-26 14:58:48 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:48 - app.access - INFO - [8f6db789-c8a4-4892-9ce3-fd1793d222c2] - Request completed
2026-03-26 14:58:48 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:51 - app.access - INFO - [3f074701-2483-43ba-a34a-8352e2e9cf90] - Request started
2026-03-26 14:58:51 - app.main - WARNING - [3f074701-2483-43ba-a34a-8352e2e9cf90] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:58:51 - app.access - WARNING - [3f074701-2483-43ba-a34a-8352e2e9cf90] - Request completed
2026-03-26 14:58:51 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/parse-medical-file-public "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:58:51 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:51 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:51 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:51 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:51 - app.access - INFO - [5e7fcbe5-2cd1-408d-b34c-1912799394e4] - Request started
2026-03-26 14:58:52 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:52 - app.access - INFO - [5e7fcbe5-2cd1-408d-b34c-1912799394e4] - Request completed
2026-03-26 14:58:52 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:52 - app.access - INFO - [c6ed4261-ce5f-4678-a0ca-ea9f89236a7d] - Request started
2026-03-26 14:58:52 - app.main - WARNING - [c6ed4261-ce5f-4678-a0ca-ea9f89236a7d] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:58:52 - app.access - WARNING - [c6ed4261-ce5f-4678-a0ca-ea9f89236a7d] - Request completed
2026-03-26 14:58:52 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/batch-upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:58:52 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:52 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:52 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:52 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:52 - app.access - INFO - [04843f5a-b377-4d18-88d6-95cfd57ac41a] - Request started
2026-03-26 14:58:53 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:53 - app.access - INFO - [04843f5a-b377-4d18-88d6-95cfd57ac41a] - Request completed
2026-03-26 14:58:53 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:53 - app.access - INFO - [1db809eb-6098-475c-bf65-37496565d5b6] - Request started
2026-03-26 14:58:53 - app.main - WARNING - [1db809eb-6098-475c-bf65-37496565d5b6] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:58:53 - app.access - WARNING - [1db809eb-6098-475c-bf65-37496565d5b6] - Request completed
2026-03-26 14:58:53 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/records/upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:58:53 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:53 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:53 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:53 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:53 - app.access - INFO - [2b432a28-6801-45c5-a020-467063709c4f] - Request started
2026-03-26 14:58:54 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:54 - app.access - INFO - [2b432a28-6801-45c5-a020-467063709c4f] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:54 - app.access - INFO - [bbb15e57-f5e7-4d48-9411-d96e737eed3f] - Request started
2026-03-26 14:58:54 - app.main - WARNING - [bbb15e57-f5e7-4d48-9411-d96e737eed3f] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:58:54 - app.access - WARNING - [bbb15e57-f5e7-4d48-9411-d96e737eed3f] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:54 - app.access - INFO - [d774fd62-27c3-48bc-a977-62db3e885715] - Request started
2026-03-26 14:58:54 - app.main - WARNING - [d774fd62-27c3-48bc-a977-62db3e885715] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:58:54 - app.access - WARNING - [d774fd62-27c3-48bc-a977-62db3e885715] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:54 - app.access - INFO - [4dc0767b-1cf2-4ade-bad2-67a5a7f43893] - Request started
2026-03-26 14:58:54 - app.main - WARNING - [4dc0767b-1cf2-4ade-bad2-67a5a7f43893] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:58:54 - app.access - WARNING - [4dc0767b-1cf2-4ade-bad2-67a5a7f43893] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:54 - app.access - INFO - [14b93f19-9a81-4276-8216-d0a4c5438d68] - Request started
2026-03-26 14:58:54 - app.main - WARNING - [14b93f19-9a81-4276-8216-d0a4c5438d68] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:58:54 - app.access - WARNING - [14b93f19-9a81-4276-8216-d0a4c5438d68] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:54 - app.access - INFO - [57bd29ae-c756-4a4a-8997-555fecd4f365] - Request started
2026-03-26 14:58:54 - app.main - WARNING - [57bd29ae-c756-4a4a-8997-555fecd4f365] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:58:54 - app.access - WARNING - [57bd29ae-c756-4a4a-8997-555fecd4f365] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:54 - app.access - INFO - [2fd9ff60-332a-4296-b428-076e9e81a2f7] - Request started
2026-03-26 14:58:54 - app.main - WARNING - [2fd9ff60-332a-4296-b428-076e9e81a2f7] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:58:54 - app.access - WARNING - [2fd9ff60-332a-4296-b428-076e9e81a2f7] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:54 - app.access - INFO - [d8b010dc-f578-44b0-bc10-9ac6032dc9c3] - Request started
2026-03-26 14:58:54 - app.main - WARNING - [d8b010dc-f578-44b0-bc10-9ac6032dc9c3] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:58:54 - app.access - WARNING - [d8b010dc-f578-44b0-bc10-9ac6032dc9c3] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:54 - app.access - INFO - [da3fc6c6-f322-4f11-8fcf-eb5185e3bea6] - Request started
2026-03-26 14:58:54 - app.main - WARNING - [da3fc6c6-f322-4f11-8fcf-eb5185e3bea6] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:58:54 - app.access - WARNING - [da3fc6c6-f322-4f11-8fcf-eb5185e3bea6] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:54 - app.access - INFO - [8dcc8f9b-8112-43a6-9ca1-83adf9ad79ea] - Request started
2026-03-26 14:58:54 - app.main - WARNING - [8dcc8f9b-8112-43a6-9ca1-83adf9ad79ea] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:58:54 - app.access - WARNING - [8dcc8f9b-8112-43a6-9ca1-83adf9ad79ea] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:54 - app.access - INFO - [cca93dc7-a63a-4fd5-9e60-258f02cbb7d4] - Request started
2026-03-26 14:58:54 - app.main - WARNING - [cca93dc7-a63a-4fd5-9e60-258f02cbb7d4] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:58:54 - app.access - WARNING - [cca93dc7-a63a-4fd5-9e60-258f02cbb7d4] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:54 - app.access - INFO - [9df9378b-04e7-4845-94b5-0bfb088ad8e7] - Request started
2026-03-26 14:58:54 - app.core.rate_limit - WARNING - [9df9378b-04e7-4845-94b5-0bfb088ad8e7] - audit.rate_limit.exceeded bucket=drg_smart_upload key=drg_smart_upload:testclient method=POST path=/api/v1/drg/smart-upload
2026-03-26 14:58:54 - app.main - WARNING - [9df9378b-04e7-4845-94b5-0bfb088ad8e7] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:58:54 - app.access - WARNING - [9df9378b-04e7-4845-94b5-0bfb088ad8e7] - Request completed
2026-03-26 14:58:54 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:58:54 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:54 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:54 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:54 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:55 - app.access - INFO - [f8938b5a-0915-4b49-9800-84b2cb4d9b0b] - Request started
2026-03-26 14:58:55 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:55 - app.access - INFO - [f8938b5a-0915-4b49-9800-84b2cb4d9b0b] - Request completed
2026-03-26 14:58:55 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:55 - app.access - INFO - [fda12ba3-bcef-46d7-b25a-912d23c530f7] - Request started
2026-03-26 14:58:55 - app.core.upload_security - WARNING - [fda12ba3-bcef-46d7-b25a-912d23c530f7] - audit.upload.rejected reason=extension_not_allowed filename=malicious.exe content_type=application/octet-stream size_bytes=4
2026-03-26 14:58:55 - app.main - WARNING - [fda12ba3-bcef-46d7-b25a-912d23c530f7] - HTTP Exception: 400 - 不支持的文件扩展名: .exe
2026-03-26 14:58:55 - app.access - WARNING - [fda12ba3-bcef-46d7-b25a-912d23c530f7] - Request completed
2026-03-26 14:58:55 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/parse-medical-file-public "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:55 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:55 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:55 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:55 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:55 - app.access - INFO - [e2cd8d8f-15f4-4ef5-a5f4-b75157bc2819] - Request started
2026-03-26 14:58:56 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:56 - app.access - INFO - [e2cd8d8f-15f4-4ef5-a5f4-b75157bc2819] - Request completed
2026-03-26 14:58:56 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:56 - app.access - INFO - [c2413726-f4b2-4140-8d5e-0d417e8cea25] - Request started
2026-03-26 14:58:56 - app.core.upload_security - WARNING - [c2413726-f4b2-4140-8d5e-0d417e8cea25] - audit.upload.rejected reason=virus_scan_blocked filename=record.txt content_type=text/plain size_bytes=68
2026-03-26 14:58:56 - app.main - WARNING - [c2413726-f4b2-4140-8d5e-0d417e8cea25] - HTTP Exception: 400 - 检测到潜在恶意文件签名
2026-03-26 14:58:56 - app.access - WARNING - [c2413726-f4b2-4140-8d5e-0d417e8cea25] - Request completed
2026-03-26 14:58:56 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/records/upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:56 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:56 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:56 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:56 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:56 - app.access - INFO - [57f0b3e6-c617-4a26-a885-b4c90f530229] - Request started
2026-03-26 14:58:57 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:57 - app.access - INFO - [57f0b3e6-c617-4a26-a885-b4c90f530229] - Request completed
2026-03-26 14:58:57 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:57 - app.access - INFO - [317bcd1c-3281-451b-b02b-bff32d199a85] - Request started
2026-03-26 14:58:57 - app.core.upload_security - WARNING - [317bcd1c-3281-451b-b02b-bff32d199a85] - audit.upload.rejected reason=mime_not_allowed filename=sample.csv content_type=image/png size_bytes=81
2026-03-26 14:58:57 - app.main - WARNING - [317bcd1c-3281-451b-b02b-bff32d199a85] - HTTP Exception: 400 - 不支持的文件类型: image/png
2026-03-26 14:58:57 - app.access - WARNING - [317bcd1c-3281-451b-b02b-bff32d199a85] - Request completed
2026-03-26 14:58:57 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/batch-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:57 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:58:57 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:58:57 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:58:57 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:58:57 - app.access - INFO - [d5ad4ccb-93b3-489f-ae6d-89ba86ae2408] - Request started
2026-03-26 14:58:57 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:58:57 - app.access - INFO - [d5ad4ccb-93b3-489f-ae6d-89ba86ae2408] - Request completed
2026-03-26 14:58:57 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:58:57 - app.access - INFO - [c09340fd-ba9c-44ba-9014-ca08362c4312] - Request started
2026-03-26 14:58:57 - app.core.upload_security - WARNING - [c09340fd-ba9c-44ba-9014-ca08362c4312] - audit.upload.rejected reason=file_too_large filename=sample.csv content_type=text/csv size_bytes=10
2026-03-26 14:58:57 - app.main - WARNING - [c09340fd-ba9c-44ba-9014-ca08362c4312] - HTTP Exception: 400 - 文件大小不能超过 8B
2026-03-26 14:58:57 - app.access - WARNING - [c09340fd-ba9c-44ba-9014-ca08362c4312] - Request completed
2026-03-26 14:58:57 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:58:58 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:58:58 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:58:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
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
======================= 5 passed, 19 warnings in 5.90s ========================
2026-03-26 14:59:11 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:59:11 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:59:13 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:59:13 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:59:13 - app.access - INFO - [aee7aacf-f80a-4492-9463-d510a961a656] - Request started
2026-03-26 14:59:14 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=release-gate-a6590265dd49@example.com roles=doctor trace_id=aee7aacf-f80a-4492-9463-d510a961a656 details={"assigned_roles": ["doctor"], "department": "质控科", "target_email": "release-gate-a6590265dd49@example.com"}
2026-03-26 14:59:14 - app.access - INFO - [aee7aacf-f80a-4492-9463-d510a961a656] - Request completed
2026-03-26 14:59:14 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 14:59:14 - app.access - INFO - [e0df3453-b582-4ccb-bb32-321c5c9bf859] - Request started
2026-03-26 14:59:14 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-a6590265dd49@example.com
2026-03-26 14:59:14 - app.access - INFO - [e0df3453-b582-4ccb-bb32-321c5c9bf859] - Request completed
2026-03-26 14:59:14 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:59:14 - app.access - INFO - [baeba90d-86fe-4792-815f-6ad90b4d400f] - Request started
2026-03-26 14:59:14 - app.access - INFO - [baeba90d-86fe-4792-815f-6ad90b4d400f] - Request completed
2026-03-26 14:59:14 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/auth/me "HTTP/1.1 200 OK"
2026-03-26 14:59:14 - app.access - INFO - [4b5b386a-af52-4e00-8d93-f9e6dc8b570e] - Request started
2026-03-26 14:59:14 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=release-gate-a6590265dd49@example.com
2026-03-26 14:59:14 - app.access - INFO - [4b5b386a-af52-4e00-8d93-f9e6dc8b570e] - Request completed
2026-03-26 14:59:14 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 14:59:14 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:59:14 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:59:15 - app.access - INFO - [172c8249-507d-4620-9f40-0a1f172277b4] - Request started
2026-03-26 14:59:15 - app.main - WARNING - [172c8249-507d-4620-9f40-0a1f172277b4] - HTTP Exception: 401 - Authentication required
2026-03-26 14:59:15 - app.access - WARNING - [172c8249-507d-4620-9f40-0a1f172277b4] - Request completed
2026-03-26 14:59:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 14:59:15 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:59:15 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:59:16 - app.access - INFO - [2e75c29e-b873-4eb2-a794-61ad59a0992b] - Request started
2026-03-26 14:59:16 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=release-gate-43fb94356a09@example.com roles=doctor trace_id=2e75c29e-b873-4eb2-a794-61ad59a0992b details={"assigned_roles": ["doctor"], "department": "质控科", "target_email": "release-gate-43fb94356a09@example.com"}
2026-03-26 14:59:16 - app.access - INFO - [2e75c29e-b873-4eb2-a794-61ad59a0992b] - Request completed
2026-03-26 14:59:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 14:59:16 - app.access - INFO - [54443167-9cec-442d-bf00-2242f5bb8bae] - Request started
2026-03-26 14:59:16 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-43fb94356a09@example.com
2026-03-26 14:59:16 - app.access - INFO - [54443167-9cec-442d-bf00-2242f5bb8bae] - Request completed
2026-03-26 14:59:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:59:16 - app.access - INFO - [a7cdd4fe-ebd5-41cf-8a36-ee986bbad459] - Request started
2026-03-26 14:59:16 - app.main - WARNING - [a7cdd4fe-ebd5-41cf-8a36-ee986bbad459] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 14:59:16 - app.access - WARNING - [a7cdd4fe-ebd5-41cf-8a36-ee986bbad459] - Request completed
2026-03-26 14:59:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 14:59:16 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:59:16 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:59:17 - app.access - INFO - [ef625e98-d71f-4694-8a90-a138a4d32c1f] - Request started
2026-03-26 14:59:17 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:59:17 - app.access - INFO - [ef625e98-d71f-4694-8a90-a138a4d32c1f] - Request completed
2026-03-26 14:59:17 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:59:17 - app.access - INFO - [815bc86d-10ac-45db-94d5-055d3407319e] - Request started
2026-03-26 14:59:17 - app.core.permissions - INFO - [no-trace-id] - 权限允许: 用户 admin@medqc.com 执行 read 操作在 medical_records 资源上
2026-03-26 14:59:17 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 14:59:17 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 14:59:17 - app.access - INFO - [815bc86d-10ac-45db-94d5-055d3407319e] - Request completed
2026-03-26 14:59:17 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/records?page=1&page_size=5 "HTTP/1.1 200 OK"
2026-03-26 14:59:17 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:59:17 - app.core.otel - INFO - [no-trace-id] - OpenTelemetry disabled by OTEL_ENABLED
2026-03-26 14:59:18 - app.access - INFO - [1f2532cd-ac0a-45af-aeb2-e17f7dcf4eae] - Request started
2026-03-26 14:59:18 - app.access - INFO - [1f2532cd-ac0a-45af-aeb2-e17f7dcf4eae] - Request completed
2026-03-26 14:59:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:59:18 - app.access - INFO - [6d6ed18f-f7a1-4cd7-a900-8f545eb64529] - Request started
2026-03-26 14:59:18 - app.access - INFO - [6d6ed18f-f7a1-4cd7-a900-8f545eb64529] - Request completed
2026-03-26 14:59:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
```