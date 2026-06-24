# Backend Release Gate Report

- total gates: 7
- passed gates: 7
- failed gates: 0
- all passed: True

## Gate Details
- auth_guard: PASS (0.17s)
  metrics: {"required_checks": 7, "passed_checks": 7, "coverage_ratio": 1.0}
- secret_hygiene: PASS (0.18s)
  metrics: {"findings": 0}
- alert_rules: PASS (0.14s)
  metrics: {"pass_marker_found": true}
- migration_roundtrip: PASS (7.24s)
  metrics: {"head_count": 1, "head": "20260315_000002"}
- pytest_contract: PASS (20.72s)
  metrics: {"passed": 28, "failed": 0, "skipped": 0}
- pytest_security_consistency: PASS (23.83s)
  metrics: {"passed": 48, "failed": 0, "skipped": 0}
- pytest_integration_smoke: PASS (18.29s)
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
[alert-rules] PASS file=D:\LLM\lx0222\health-qc-monorepo\scripts\medqc_prometheus_alert_rules.yml alerts=5
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
collected 28 items

tests\unit\test_auth_sync_contract.py   views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
.  views OK: qc.v_qc_task_progress, qc.qc_appeals_statistics, qc.qc_remediation_statistics, qc.qc_assignee_workload, qc.qc_statistics_view, qc.v_qc_coder_ranking
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

app\main.py:304
tests/unit/test_auth_sync_contract.py::test_refresh_contract_accepts_json_and_returns_stable_shape
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\main.py:304: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    @app.on_event("startup")

C:\Python310\lib\site-packages\fastapi\applications.py:4547
tests/unit/test_auth_sync_contract.py::test_refresh_contract_accepts_json_and_returns_stable_shape
  C:\Python310\lib\site-packages\fastapi\applications.py:4547: DeprecationWarning: 
          on_event is deprecated, use lifespan event handlers instead.
  
          Read more about it in the
          [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
          
    return self.router.on_event(event_type)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 28 passed, 11 warnings in 5.86s =======================
2026-03-26 14:40:56 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:40:56 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:40:57 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:40:57 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:40:57 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:40:57 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:40:57 - app.access - INFO - [83ae5840-3443-4c82-9993-c020dfc2167a] - Request started
2026-03-26 14:40:58 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:40:58 - app.access - INFO - [83ae5840-3443-4c82-9993-c020dfc2167a] - Request completed
2026-03-26 14:40:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:40:58 - app.access - INFO - [0f22803a-df4f-4589-96cd-d874cc8b90ee] - Request started
2026-03-26 14:40:58 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 14:40:58 - app.access - INFO - [0f22803a-df4f-4589-96cd-d874cc8b90ee] - Request completed
2026-03-26 14:40:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 14:40:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:40:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:40:58 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:40:58 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:40:58 - app.access - INFO - [6561f6bd-de6a-4f5a-aa15-10696055d8b2] - Request started
2026-03-26 14:40:58 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:40:58 - app.access - INFO - [6561f6bd-de6a-4f5a-aa15-10696055d8b2] - Request completed
2026-03-26 14:40:58 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:40:58 - app.access - INFO - [241fde35-1153-430b-bc67-b2c40c5c8f37] - Request started
2026-03-26 14:40:58 - app.access - INFO - [241fde35-1153-430b-bc67-b2c40c5c8f37] - Request completed
2026-03-26 14:40:58 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 14:40:58 - app.access - INFO - [4e62e876-57ec-413c-ad7e-d3622e4010b0] - Request started
2026-03-26 14:40:58 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.pg.update resource=/api/v1/sync/config/pg outcome=success actor=admin@medqc.com roles=admin,qc_manager trace_id=4e62e876-57ec-413c-ad7e-d3622e4010b0 details={"changed_fields": ["remote_host", "remote_password", "remote_password_ref", "remote_port"], "connection_ok": true, "remote_host": "10.8.8.8", "remote_port": "5544"}
2026-03-26 14:40:58 - app.access - INFO - [4e62e876-57ec-413c-ad7e-d3622e4010b0] - Request completed
2026-03-26 14:40:58 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 14:40:58 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:40:58 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:40:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:40:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:40:59 - app.access - INFO - [fc981cdc-42db-4601-b708-7e1d039b1996] - Request started
2026-03-26 14:40:59 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 14:40:59 - app.access - INFO - [fc981cdc-42db-4601-b708-7e1d039b1996] - Request completed
2026-03-26 14:40:59 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:40:59 - app.access - INFO - [7061e203-b2f0-4244-8b7c-7090f3a1b53b] - Request started
2026-03-26 14:40:59 - app.main - WARNING - [7061e203-b2f0-4244-8b7c-7090f3a1b53b] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 14:40:59 - app.access - WARNING - [7061e203-b2f0-4244-8b7c-7090f3a1b53b] - Request completed
2026-03-26 14:40:59 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 14:40:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:40:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:40:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:40:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:40:59 - app.access - INFO - [a1f616d9-12ae-4622-b1dc-fba2040911f5] - Request started
2026-03-26 14:40:59 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:40:59 - app.access - INFO - [a1f616d9-12ae-4622-b1dc-fba2040911f5] - Request completed
2026-03-26 14:40:59 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:40:59 - app.access - INFO - [9bfdec61-27ec-4bfa-98cd-01069e0cf7db] - Request started
2026-03-26 14:40:59 - app.routers.qc_sichuan - INFO - [no-trace-id] - Loaded 179 Sichuan rules from JSON file
2026-03-26 14:40:59 - app.access - INFO - [9bfdec61-27ec-4bfa-98cd-01069e0cf7db] - Request completed
2026-03-26 14:40:59 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/rules "HTTP/1.1 200 OK"
2026-03-26 14:40:59 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:40:59 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:40:59 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:40:59 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:00 - app.access - INFO - [f1838437-eaae-4c03-8b37-425432e602bd] - Request started
2026-03-26 14:41:00 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:00 - app.access - INFO - [f1838437-eaae-4c03-8b37-425432e602bd] - Request completed
2026-03-26 14:41:00 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:00 - app.access - INFO - [c287bb93-50d1-4c25-b5cb-9056681c2603] - Request started
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251110_041209.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251109_233517.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_234838.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_070941.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065547.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_065421.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_062819.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_053504.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_021345.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_015054.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_014934.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_013113.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\sequential_batch_20251108_005230.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\fe17a51e-5db0-4d37-ab6d-ac41cecca752_sequential_batch_20251112_130619.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f41ab06d-0f77-4f0f-ad27-e9c08fea5756_sequential_batch_20251112_143049.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\f158d3cf-7fa9-4059-82e6-01e478d60399_sequential_batch_20251112_142617.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\e6cd1e70-88ac-4df9-a164-1326d35a6874_sequential_batch_20251110_064046.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\daf44f72-0baa-453b-bf32-b9355bd3bd01_sequential_batch_20251112_011112.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\defbcbd9-94e9-4723-b6df-dbf0b21ea4f7_sequential_batch_20251112_233633.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\c79d0012-c564-4d1c-bd4c-cf5aebe1fd92_sequential_batch_20251112_132237.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_083256.json: 'list' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a9c69ec9-9675-40ed-b203-5d830842a11c_sequential_batch_20251112_013953.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\aliyun_lx030_model_report_20251113_082322.json: 'list' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\a2bbfbe5-48de-4da8-bb47-e0cc59424775_sequential_batch_20251112_233854.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\9d5ec2a7-dc69-40dc-86ac-2c1e52f9aafd_sequential_batch_20251112_031338.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\89bb0a9d-14b9-48bc-8f67-f04f89fbb9c5_sequential_batch_20251112_031203.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\81d4a41f-bd3d-457d-aea6-1c32a412312e_sequential_batch_20251111_120900.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\818fe627-f5ad-4101-b06d-8a2addf10a71_sequential_batch_20251111_134659.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6fd14104-4d02-4b52-bc3d-a012cf4ede90_sequential_batch_20251112_232848.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6de19991-4266-4aa4-8bef-ee3001fb3ddc_sequential_batch_20251113_000427.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\6154a09c-c692-4cfd-83a7-eb2773a9ad8b_sequential_batch_20251112_141218.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\5a2b1859-a0a8-436b-a4a0-af30eb6db6dc_sequential_batch_20251111_235912.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\57c72978-223b-4e01-b6ff-180e802c1718_sequential_batch_20251112_130944.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4eb1f192-80d8-48fa-8393-0c91b788d0d9_sequential_batch_20251111_235832.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4798fb59-6450-4f11-94c3-848d2702cf6c_sequential_batch_20251112_151503.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\4596298c-eca7-4ca2-89ce-30ce5ae2898d_sequential_batch_20251111_012838.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\36f11425-d816-4f8a-b624-dced1ac4c164_sequential_batch_20251112_060145.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\2c59b9ef-9b2f-4ef8-b671-d0840df86da8_sequential_batch_20251112_231936.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1e2886a3-253f-4008-b4c7-da32548e5826_sequential_batch_20251111_121107.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\1ca2602c-56e6-4310-b686-19a73531a8a9_sequential_batch_20251112_232958.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.routers.qc_sichuan - WARNING - [no-trace-id] - 读取质控结果文件失败 D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\storage\qc_results\13c4efdd-6bff-4ff7-aa51-2bc906aad435_sequential_batch_20251112_232048.json: 'NoneType' object has no attribute 'get'
2026-03-26 14:41:00 - app.access - INFO - [c287bb93-50d1-4c25-b5cb-9056681c2603] - Request completed
2026-03-26 14:41:00 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/qc/sichuan/results/history?page=1&page_size=10 "HTTP/1.1 200 OK"
2026-03-26 14:41:00 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:00 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:00 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:00 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:00 - app.access - INFO - [631d1be4-c1d8-4d95-b7ed-534106dcb361] - Request started
2026-03-26 14:41:00 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:00 - app.access - INFO - [631d1be4-c1d8-4d95-b7ed-534106dcb361] - Request completed
2026-03-26 14:41:00 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:00 - app.access - INFO - [8752e7a9-a05c-4ab8-a586-fa725c6ea47f] - Request started
2026-03-26 14:41:00 - app.access - INFO - [8752e7a9-a05c-4ab8-a586-fa725c6ea47f] - Request completed
2026-03-26 14:41:00 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 200 OK"
2026-03-26 14:41:00 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:00 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [88ee8d68-accd-4c5f-a218-c7f029dccbd8] - Request started
2026-03-26 14:41:01 - app.access - INFO - [88ee8d68-accd-4c5f-a218-c7f029dccbd8] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.access - INFO - [51262830-eb17-4564-947e-8e59483f2270] - Request started
2026-03-26 14:41:01 - app.access - INFO - [51262830-eb17-4564-947e-8e59483f2270] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.access - INFO - [60fe7fc7-405d-4af5-96bb-7cd1ba6bb952] - Request started
2026-03-26 14:41:01 - app.main - WARNING - [60fe7fc7-405d-4af5-96bb-7cd1ba6bb952] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 14:41:01 - app.access - WARNING - [60fe7fc7-405d-4af5-96bb-7cd1ba6bb952] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 403 Forbidden"
2026-03-26 14:41:01 - app.access - INFO - [7ca9f611-04ec-4bde-8c5f-392f811a2c64] - Request started
2026-03-26 14:41:01 - app.main - WARNING - [7ca9f611-04ec-4bde-8c5f-392f811a2c64] - HTTP Exception: 401 - Authentication required
2026-03-26 14:41:01 - app.access - WARNING - [7ca9f611-04ec-4bde-8c5f-392f811a2c64] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/status "HTTP/1.1 401 Unauthorized"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [72855412-8ea2-41c2-b84d-a76fc03b798c] - Request started
2026-03-26 14:41:01 - app.main - WARNING - [72855412-8ea2-41c2-b84d-a76fc03b798c] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 14:41:01 - app.access - WARNING - [72855412-8ea2-41c2-b84d-a76fc03b798c] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [7f637c08-0892-4d74-8969-9778cd6b7147] - Request started
2026-03-26 14:41:01 - app.main - WARNING - [7f637c08-0892-4d74-8969-9778cd6b7147] - Validation Error: [{'type': 'greater_than_equal', 'loc': ('body', 'lookback_minutes'), 'msg': 'Input should be greater than or equal to 0', 'input': -1, 'ctx': {'ge': 0}, 'url': 'https://errors.pydantic.dev/2.5/v/greater_than_equal'}]
2026-03-26 14:41:01 - app.access - WARNING - [7f637c08-0892-4d74-8969-9778cd6b7147] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:41:01 - app.access - INFO - [24740781-811b-41cf-b37f-7637a7d244cb] - Request started
2026-03-26 14:41:01 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.mongo.update resource=/api/v1/sync/config/mongo outcome=success actor=sync@test.local roles=admin trace_id=24740781-811b-41cf-b37f-7637a7d244cb details={"changed_fields": ["connect_timeout_ms", "enabled", "inter_request_delay_ms", "lookback_minutes", "max_batch_size", "night_window_end", "night_window_start", "rescan_recent_days", "tier1_interval_minutes", "tier2_interval_minutes", "tier3_cron"], "enabled": true}
2026-03-26 14:41:01 - app.access - INFO - [24740781-811b-41cf-b37f-7637a7d244cb] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/mongo "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [9d2e81bc-a86d-43a3-8594-73e8eb118bbf] - Request started
2026-03-26 14:41:01 - app.access - INFO - [9d2e81bc-a86d-43a3-8594-73e8eb118bbf] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/v1/sync/config/pg "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [d0e4e1da-c5f5-43d4-b9db-8f62fb93c55c] - Request started
2026-03-26 14:41:01 - app.access - INFO - [d0e4e1da-c5f5-43d4-b9db-8f62fb93c55c] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/test-connection/all "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [c83b9c3f-2a76-4925-bc4f-2020ffdfcbcd] - Request started
2026-03-26 14:41:01 - app.access - INFO - [c83b9c3f-2a76-4925-bc4f-2020ffdfcbcd] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [0d84b5f5-6b20-4c29-be6a-0d74daf43acf] - Request started
2026-03-26 14:41:01 - app.access - INFO - [0d84b5f5-6b20-4c29-be6a-0d74daf43acf] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/preflight "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [0c828154-97d0-40b1-b6fd-d7b77a1b4675] - Request started
2026-03-26 14:41:01 - app.audit - INFO - [no-trace-id] - audit.event action=sync.trigger resource=/api/v1/sync/trigger outcome=rejected_running actor=sync@test.local roles=admin trace_id=0c828154-97d0-40b1-b6fd-d7b77a1b4675 details={"idempotency_key": "mongo:all:2026-03-26:sync@test.local", "run_id": "syncrun-5bb9c8505b4a", "source": "mongo", "sync_date": "2026-03-26", "tier": "all"}
2026-03-26 14:41:01 - app.access - INFO - [0c828154-97d0-40b1-b6fd-d7b77a1b4675] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [711b5faa-aaa9-4718-a607-d5ff44b5cda1] - Request started
2026-03-26 14:41:01 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 14:41:01 - app.audit - INFO - [no-trace-id] - audit.event action=sync.trigger resource=/api/v1/sync/trigger outcome=success actor=sync@test.local roles=admin trace_id=711b5faa-aaa9-4718-a607-d5ff44b5cda1 details={"idempotency_key": "mongo:tier1:2026-03-26:sync@test.local", "run_id": "syncrun-7178609172b6", "source": "mongo", "status": "success", "sync_date": "2026-03-26", "tier": "tier1", "total_records": 2}
2026-03-26 14:41:01 - app.access - INFO - [711b5faa-aaa9-4718-a607-d5ff44b5cda1] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [110ca6cd-ea49-402f-a359-15f1779014a2] - Request started
2026-03-26 14:41:01 - app.routers.sync - INFO - [no-trace-id] - sync.trigger operator=sync@test.local source=mongo tier=tier1 status=success total_records=2
2026-03-26 14:41:01 - app.access - INFO - [110ca6cd-ea49-402f-a359-15f1779014a2] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.access - INFO - [231e3503-7665-4ea9-a55d-cf9136a7a4c5] - Request started
2026-03-26 14:41:01 - app.access - INFO - [231e3503-7665-4ea9-a55d-cf9136a7a4c5] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [17b9b744-378f-4a24-954a-3878b98db79d] - Request started
2026-03-26 14:41:01 - app.access - INFO - [17b9b744-378f-4a24-954a-3878b98db79d] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/runs?source=mongo&tier=tier2&limit=20 "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [a4359fce-b764-494b-a847-2244827acada] - Request started
2026-03-26 14:41:01 - app.access - INFO - [a4359fce-b764-494b-a847-2244827acada] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.access - INFO - [0664c7a4-af79-437b-9dad-2ccb25b4c15a] - Request started
2026-03-26 14:41:01 - app.main - WARNING - [0664c7a4-af79-437b-9dad-2ccb25b4c15a] - HTTP Exception: 403 - 数据同步读取权限不足（仅 admin / qc_manager 可访问）
2026-03-26 14:41:01 - app.access - WARNING - [0664c7a4-af79-437b-9dad-2ccb25b4c15a] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/templates "HTTP/1.1 403 Forbidden"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:01 - app.access - INFO - [19c524e7-1ba4-4fd5-9e64-299059593d12] - Request started
2026-03-26 14:41:01 - app.audit - INFO - [no-trace-id] - audit.event action=sync.template.apply resource=/api/v1/sync/templates/apply outcome=success actor=sync@test.local roles=admin trace_id=19c524e7-1ba4-4fd5-9e64-299059593d12 details={"departments_count": 1, "enabled": false, "template_id": "single_department_focus"}
2026-03-26 14:41:01 - app.access - INFO - [19c524e7-1ba4-4fd5-9e64-299059593d12] - Request completed
2026-03-26 14:41:01 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 200 OK"
2026-03-26 14:41:01 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:01 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:02 - app.access - INFO - [0d6c683d-a117-4c97-bcda-e1d6e2e7dd38] - Request started
2026-03-26 14:41:02 - app.main - WARNING - [0d6c683d-a117-4c97-bcda-e1d6e2e7dd38] - HTTP Exception: 422 - 该模板必须选择科室
2026-03-26 14:41:02 - app.access - WARNING - [0d6c683d-a117-4c97-bcda-e1d6e2e7dd38] - Request completed
2026-03-26 14:41:02 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:41:02 - app.access - INFO - [d78cec3f-3757-4e4d-b7fd-5e404fc7ab7d] - Request started
2026-03-26 14:41:02 - app.main - WARNING - [d78cec3f-3757-4e4d-b7fd-5e404fc7ab7d] - HTTP Exception: 422 - 科室列表不允许同时包含 * 和具体科室
2026-03-26 14:41:02 - app.access - WARNING - [d78cec3f-3757-4e4d-b7fd-5e404fc7ab7d] - Request completed
2026-03-26 14:41:02 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/templates/apply "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:02 - app.access - INFO - [59e64166-1854-49e6-b006-905e04624c1d] - Request started
2026-03-26 14:41:02 - app.access - INFO - [59e64166-1854-49e6-b006-905e04624c1d] - Request completed
2026-03-26 14:41:02 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 200 OK"
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:02 - app.access - INFO - [6bdac7df-8eee-49ae-8721-d0fcea63c95e] - Request started
2026-03-26 14:41:02 - app.main - WARNING - [6bdac7df-8eee-49ae-8721-d0fcea63c95e] - HTTP Exception: 422 - mongo_uri 未配置
2026-03-26 14:41:02 - app.access - WARNING - [6bdac7df-8eee-49ae-8721-d0fcea63c95e] - Request completed
2026-03-26 14:41:02 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/sync/departments "HTTP/1.1 422 Unprocessable Entity"
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:02 - app.access - INFO - [44dba596-f9b1-4bbd-b579-46a9cf8ca176] - Request started
2026-03-26 14:41:02 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 14:41:02 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 14:41:02 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:41:02 - app.access - INFO - [44dba596-f9b1-4bbd-b579-46a9cf8ca176] - Request completed
2026-03-26 14:41:02 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:02 - app.access - INFO - [cd45cc51-cf6a-4133-8e51-38650420a370] - Request started
2026-03-26 14:41:02 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:41:02 - app.access - INFO - [cd45cc51-cf6a-4133-8e51-38650420a370] - Request completed
2026-03-26 14:41:02 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics/prometheus "HTTP/1.1 200 OK"
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:02 - app.access - INFO - [trace-client-123] - Request started
2026-03-26 14:41:02 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:41:02 - app.access - INFO - [trace-client-123] - Request completed
2026-03-26 14:41:02 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:02 - app.access - INFO - [req-client-456] - Request started
2026-03-26 14:41:02 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:41:02 - app.access - INFO - [req-client-456] - Request completed
2026-03-26 14:41:02 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:02 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request started
2026-03-26 14:41:02 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:41:02 - app.access - INFO - [4bf92f3577b34da6a3ce929d0e0e4736] - Request completed
2026-03-26 14:41:02 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:02 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:02 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:02 - app.access - INFO - [1f476827-adfb-4582-9a14-cee80e1ae38c] - Request started
2026-03-26 14:41:02 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:41:02 - app.access - INFO - [1f476827-adfb-4582-9a14-cee80e1ae38c] - Request completed
2026-03-26 14:41:02 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
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

app\main.py:304
tests/unit/test_security_hardening.py::test_high_risk_endpoints_require_auth
tests/unit/test_production_guard.py::test_startup_fails_fast_in_production_with_default_demo_users
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\main.py:304: DeprecationWarning: 
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
====================== 48 passed, 13 warnings in 12.40s =======================
2026-03-26 14:41:13 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:41:14 - app.audit - INFO - [no-trace-id] - audit.event action=sync.config.pg.update resource=/api/v1/sync/config/pg outcome=success actor=admin@medqc.com roles=admin trace_id=trace-unit-audit details={"nested": {"token": "***"}, "remote_host": "127.0.0.1", "remote_password": "***"}
2026-03-26 14:41:14 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:41:14 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:14 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:15 - app.access - INFO - [0d7b15ce-a2cc-47f8-b4f4-d64adf95c511] - Request started
2026-03-26 14:41:15 - app.main - WARNING - [0d7b15ce-a2cc-47f8-b4f4-d64adf95c511] - HTTP Exception: 401 - Authentication required
2026-03-26 14:41:15 - app.access - WARNING - [0d7b15ce-a2cc-47f8-b4f4-d64adf95c511] - Request completed
2026-03-26 14:41:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 14:41:15 - app.access - INFO - [05ca5b52-21e8-4dea-bc4f-84e8bec6adf8] - Request started
2026-03-26 14:41:15 - app.main - WARNING - [05ca5b52-21e8-4dea-bc4f-84e8bec6adf8] - HTTP Exception: 401 - Authentication required
2026-03-26 14:41:15 - app.access - WARNING - [05ca5b52-21e8-4dea-bc4f-84e8bec6adf8] - Request completed
2026-03-26 14:41:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/drg/config/current "HTTP/1.1 401 Unauthorized"
2026-03-26 14:41:15 - app.access - INFO - [4e60562a-0c60-482e-b298-eb5bb3153dfa] - Request started
2026-03-26 14:41:15 - app.main - WARNING - [4e60562a-0c60-482e-b298-eb5bb3153dfa] - HTTP Exception: 401 - Authentication required
2026-03-26 14:41:15 - app.access - WARNING - [4e60562a-0c60-482e-b298-eb5bb3153dfa] - Request completed
2026-03-26 14:41:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/settlement/list "HTTP/1.1 401 Unauthorized"
2026-03-26 14:41:15 - app.access - INFO - [b6650aff-5624-4efb-93b5-1acc374c9b3e] - Request started
2026-03-26 14:41:15 - app.main - WARNING - [b6650aff-5624-4efb-93b5-1acc374c9b3e] - HTTP Exception: 401 - Authentication required
2026-03-26 14:41:15 - app.access - WARNING - [b6650aff-5624-4efb-93b5-1acc374c9b3e] - Request completed
2026-03-26 14:41:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 401 Unauthorized"
2026-03-26 14:41:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:15 - app.access - INFO - [caac3090-ce02-45bc-a699-a6a92caa7855] - Request started
2026-03-26 14:41:15 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=doctor@medqc.com
2026-03-26 14:41:15 - app.access - INFO - [caac3090-ce02-45bc-a699-a6a92caa7855] - Request completed
2026-03-26 14:41:15 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:15 - app.access - INFO - [fc9c7402-6ef5-40d6-be84-7601679fa956] - Request started
2026-03-26 14:41:15 - app.main - WARNING - [fc9c7402-6ef5-40d6-be84-7601679fa956] - HTTP Exception: 403 - 此操作需要系统管理员权限
2026-03-26 14:41:15 - app.access - WARNING - [fc9c7402-6ef5-40d6-be84-7601679fa956] - Request completed
2026-03-26 14:41:15 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/system/db/status "HTTP/1.1 403 Forbidden"
2026-03-26 14:41:15 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:15 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:15 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:15 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:15 - app.access - INFO - [d8a85b28-b12e-47e9-a01e-3df1fa27f558] - Request started
2026-03-26 14:41:15 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:16 - app.access - INFO - [d8a85b28-b12e-47e9-a01e-3df1fa27f558] - Request completed
2026-03-26 14:41:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:16 - app.access - INFO - [b3c7fa1b-1dc9-4507-b788-c2722cab4654] - Request started
2026-03-26 14:41:16 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=admin@medqc.com
2026-03-26 14:41:16 - app.access - INFO - [b3c7fa1b-1dc9-4507-b788-c2722cab4654] - Request completed
2026-03-26 14:41:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 14:41:16 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:16 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:16 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:16 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:16 - app.access - INFO - [bd84db42-f9e5-4666-af0c-a1af66ed7203] - Request started
2026-03-26 14:41:16 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=reset-5d00bc04@medqc.com roles=doctor trace_id=bd84db42-f9e5-4666-af0c-a1af66ed7203 details={"assigned_roles": ["doctor"], "department": "测试科室", "target_email": "reset-5d00bc04@medqc.com"}
2026-03-26 14:41:16 - app.access - INFO - [bd84db42-f9e5-4666-af0c-a1af66ed7203] - Request completed
2026-03-26 14:41:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 14:41:16 - app.access - INFO - [9deeb7e1-92fe-4c0e-bc96-fda93652d47b] - Request started
2026-03-26 14:41:16 - app.routers.auth - INFO - [no-trace-id] - auth.forgot_password.issued email=reset-5d00bc04@medqc.com
2026-03-26 14:41:16 - app.access - INFO - [9deeb7e1-92fe-4c0e-bc96-fda93652d47b] - Request completed
2026-03-26 14:41:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/forgot-password "HTTP/1.1 200 OK"
2026-03-26 14:41:16 - app.access - INFO - [589d2f6f-1708-46e0-bb9f-5742f2fac665] - Request started
2026-03-26 14:41:16 - app.routers.auth - INFO - [no-trace-id] - auth.reset_password.success email=reset-5d00bc04@medqc.com
2026-03-26 14:41:16 - app.access - INFO - [589d2f6f-1708-46e0-bb9f-5742f2fac665] - Request completed
2026-03-26 14:41:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 200 OK"
2026-03-26 14:41:16 - app.access - INFO - [5c281a38-db9e-497b-9b6e-3eba036770d7] - Request started
2026-03-26 14:41:16 - app.main - WARNING - [5c281a38-db9e-497b-9b6e-3eba036770d7] - HTTP Exception: 401 - 重置令牌已使用或失效
2026-03-26 14:41:16 - app.access - WARNING - [5c281a38-db9e-497b-9b6e-3eba036770d7] - Request completed
2026-03-26 14:41:16 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/reset-password "HTTP/1.1 401 Unauthorized"
2026-03-26 14:41:16 - app.access - INFO - [61f6161f-c31e-4af0-82e0-20331a2160ba] - Request started
2026-03-26 14:41:17 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=reset-5d00bc04@medqc.com
2026-03-26 14:41:17 - app.access - INFO - [61f6161f-c31e-4af0-82e0-20331a2160ba] - Request completed
2026-03-26 14:41:17 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:17 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:17 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:17 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:17 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:17 - app.access - INFO - [a923c979-05df-46b8-8506-2f65f31cf672] - Request started
2026-03-26 14:41:17 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:17 - app.access - INFO - [a923c979-05df-46b8-8506-2f65f31cf672] - Request completed
2026-03-26 14:41:17 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:17 - app.access - INFO - [b157660a-25a1-4ff2-b208-dce302aa606d] - Request started
2026-03-26 14:41:17 - app.main - WARNING - [b157660a-25a1-4ff2-b208-dce302aa606d] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/db/config. Please use /api/v1/sync/*
2026-03-26 14:41:17 - app.access - WARNING - [b157660a-25a1-4ff2-b208-dce302aa606d] - Request completed
2026-03-26 14:41:17 - httpx - INFO - [no-trace-id] - HTTP Request: PUT http://testserver/api/system/db/config "HTTP/1.1 410 Gone"
2026-03-26 14:41:17 - app.access - INFO - [95e10ddd-df39-4234-ab21-7e4f92bcd502] - Request started
2026-03-26 14:41:17 - app.main - WARNING - [95e10ddd-df39-4234-ab21-7e4f92bcd502] - HTTP Exception: 410 - Legacy write endpoint retired: /api/system/sync/trigger. Please use /api/v1/sync/*
2026-03-26 14:41:17 - app.access - WARNING - [95e10ddd-df39-4234-ab21-7e4f92bcd502] - Request completed
2026-03-26 14:41:17 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/system/sync/trigger "HTTP/1.1 410 Gone"
2026-03-26 14:41:17 - app.services.etl_sync - INFO - [no-trace-id] - 同步 病案首页 (web.mr)...
2026-03-26 14:41:17 - app.services.etl_sync - INFO - [no-trace-id] -   \u2705 病案首页: 1 条
2026-03-26 14:41:17 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:17 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:17 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:17 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:17 - app.access - INFO - [f6b35798-5fd1-447d-9bdd-11555327b6ab] - Request started
2026-03-26 14:41:17 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 14:41:17 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 14:41:18 - app.access - INFO - [f6b35798-5fd1-447d-9bdd-11555327b6ab] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [d8c9f584-2f1f-4565-9ffc-fbc377f34d36] - Request started
2026-03-26 14:41:18 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:41:18 - app.access - INFO - [d8c9f584-2f1f-4565-9ffc-fbc377f34d36] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [0a5dc995-1fe7-4ae8-a596-d1378baeb623] - Request started
2026-03-26 14:41:18 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:41:18 - app.access - INFO - [0a5dc995-1fe7-4ae8-a596-d1378baeb623] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics/prometheus "HTTP/1.1 200 OK"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [0aab114f-5bd4-4ce9-ad45-ca950c44f207] - Request started
2026-03-26 14:41:18 - app.access - INFO - [0aab114f-5bd4-4ce9-ad45-ca950c44f207] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [4930ac33-e629-49d9-b061-6db960fc41e0] - Request started
2026-03-26 14:41:18 - app.access - WARNING - [4930ac33-e629-49d9-b061-6db960fc41e0] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: OPTIONS http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [ec6d1d14-f78c-4ba7-bdc1-5a2c63aa142a] - Request started
2026-03-26 14:41:18 - app.access - INFO - [ec6d1d14-f78c-4ba7-bdc1-5a2c63aa142a] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [6f6ec522-c62e-48d0-9a15-dc18cfd5adc0] - Request started
2026-03-26 14:41:18 - app.access - INFO - [6f6ec522-c62e-48d0-9a15-dc18cfd5adc0] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [92051895-a567-4c97-be95-d162c8187566] - Request started
2026-03-26 14:41:18 - app.access - INFO - [92051895-a567-4c97-be95-d162c8187566] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [361a67e5-3eed-49cf-a0e1-9e476e640ce4] - Request started
2026-03-26 14:41:18 - app.access - INFO - [361a67e5-3eed-49cf-a0e1-9e476e640ce4] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [6f6e55f3-c6f8-481d-9647-64d3c34c9c75] - Request started
2026-03-26 14:41:18 - app.access - INFO - [6f6e55f3-c6f8-481d-9647-64d3c34c9c75] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [c5d3a1f3-603a-44a6-b2f0-9e1b7a65a5c9] - Request started
2026-03-26 14:41:18 - app.access - INFO - [c5d3a1f3-603a-44a6-b2f0-9e1b7a65a5c9] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [dc0d77ac-237d-4623-9952-5bc09a6cf33f] - Request started
2026-03-26 14:41:18 - app.services.qc_llm_client - INFO - [no-trace-id] - SichuanQCLLMClient env init: source=LLM_* endpoint_set=True api_key_set=True model=qwen3.5-35b-a3b allow_mock=False
2026-03-26 14:41:18 - app.access - INFO - [dc0d77ac-237d-4623-9952-5bc09a6cf33f] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/metrics "HTTP/1.1 200 OK"
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:18 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:18 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:18 - app.access - INFO - [2fef91f4-e60b-4af5-ade0-50ecefff1e86] - Request started
2026-03-26 14:41:18 - app.access - WARNING - [2fef91f4-e60b-4af5-ade0-50ecefff1e86] - Request completed
2026-03-26 14:41:18 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/nonexistent "HTTP/1.1 404 Not Found"
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:19 - app.access - INFO - [26c826a2-198d-4f36-88fe-40f2e6e6e37c] - Request started
2026-03-26 14:41:19 - app.access - WARNING - [26c826a2-198d-4f36-88fe-40f2e6e6e37c] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/health "HTTP/1.1 405 Method Not Allowed"
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:19 - app.access - INFO - [c0d2d439-ad9b-4065-8aaf-448310c41bbb] - Request started
2026-03-26 14:41:19 - app.access - INFO - [4f73ae61-af55-4fa2-9c8b-a87afdca2eff] - Request started
2026-03-26 14:41:19 - app.access - INFO - [c0d2d439-ad9b-4065-8aaf-448310c41bbb] - Request completed
2026-03-26 14:41:19 - app.access - INFO - [100b0fed-9d98-4c41-9247-9197b564b906] - Request started
2026-03-26 14:41:19 - app.access - INFO - [474e289c-14f4-4f14-881b-661d029b223c] - Request started
2026-03-26 14:41:19 - app.access - INFO - [4f73ae61-af55-4fa2-9c8b-a87afdca2eff] - Request completed
2026-03-26 14:41:19 - app.access - INFO - [cc3c3839-fde6-4ef8-874e-c390b6778ee2] - Request started
2026-03-26 14:41:19 - app.access - INFO - [c813eb7e-b9b9-4c80-93c4-3cb8e3e33c43] - Request started
2026-03-26 14:41:19 - app.access - INFO - [d4b7d64d-7066-4f04-8f15-a5f762474afd] - Request started
2026-03-26 14:41:19 - app.access - INFO - [6aa6d7ff-6391-4a70-8abb-6d3515f77fca] - Request started
2026-03-26 14:41:19 - app.access - INFO - [100b0fed-9d98-4c41-9247-9197b564b906] - Request completed
2026-03-26 14:41:19 - app.access - INFO - [474e289c-14f4-4f14-881b-661d029b223c] - Request completed
2026-03-26 14:41:19 - app.access - INFO - [cd4ac833-9682-4f74-86ef-5e0e6d91f11d] - Request started
2026-03-26 14:41:19 - app.access - INFO - [e4d16823-e1d6-4c22-b29f-01cbafa304bd] - Request started
2026-03-26 14:41:19 - app.access - INFO - [cc3c3839-fde6-4ef8-874e-c390b6778ee2] - Request completed
2026-03-26 14:41:19 - app.access - INFO - [c813eb7e-b9b9-4c80-93c4-3cb8e3e33c43] - Request completed
2026-03-26 14:41:19 - app.access - INFO - [d4b7d64d-7066-4f04-8f15-a5f762474afd] - Request completed
2026-03-26 14:41:19 - app.access - INFO - [6aa6d7ff-6391-4a70-8abb-6d3515f77fca] - Request completed
2026-03-26 14:41:19 - app.access - INFO - [cd4ac833-9682-4f74-86ef-5e0e6d91f11d] - Request completed
2026-03-26 14:41:19 - app.access - INFO - [e4d16823-e1d6-4c22-b29f-01cbafa304bd] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:19 - app.access - INFO - [953d69d4-2d0e-498a-9978-45601ca5a052] - Request started
2026-03-26 14:41:19 - app.access - INFO - [953d69d4-2d0e-498a-9978-45601ca5a052] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:19 - app.access - INFO - [363ed99f-2d60-46c1-8071-aac048dbc14f] - Request started
2026-03-26 14:41:19 - app.access - INFO - [363ed99f-2d60-46c1-8071-aac048dbc14f] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:19 - app.access - INFO - [13906ebd-004b-486b-9af4-af6cfbc83c4d] - Request started
2026-03-26 14:41:19 - app.access - INFO - [13906ebd-004b-486b-9af4-af6cfbc83c4d] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:19 - app.access - INFO - [0c6466d6-928b-4724-8e2b-3d51ef5e7745] - Request started
2026-03-26 14:41:19 - app.access - INFO - [0c6466d6-928b-4724-8e2b-3d51ef5e7745] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health?test=1&test=2 "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:19 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:19 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:19 - app.access - INFO - [5167db65-0179-42b5-96d4-7af2a8937b34] - Request started
2026-03-26 14:41:19 - app.access - INFO - [5167db65-0179-42b5-96d4-7af2a8937b34] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [7fcd18ae-546f-4c73-8034-f0da3d82fd8a] - Request started
2026-03-26 14:41:19 - app.access - INFO - [7fcd18ae-546f-4c73-8034-f0da3d82fd8a] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [94ee5454-b4cd-46fb-9ca0-cf7cd9c211fa] - Request started
2026-03-26 14:41:19 - app.access - INFO - [94ee5454-b4cd-46fb-9ca0-cf7cd9c211fa] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [87f7f069-f39a-4b01-8803-95643431c9a6] - Request started
2026-03-26 14:41:19 - app.access - INFO - [87f7f069-f39a-4b01-8803-95643431c9a6] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [28a5544d-1ef1-4e43-a774-4cf66a7139a3] - Request started
2026-03-26 14:41:19 - app.access - INFO - [28a5544d-1ef1-4e43-a774-4cf66a7139a3] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [2912890b-2f39-45eb-b8e0-376ad09ac990] - Request started
2026-03-26 14:41:19 - app.access - INFO - [2912890b-2f39-45eb-b8e0-376ad09ac990] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [0686561a-17b0-480d-b18c-8dde2fba2b9f] - Request started
2026-03-26 14:41:19 - app.access - INFO - [0686561a-17b0-480d-b18c-8dde2fba2b9f] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [6cd1b746-eef3-493d-971e-a04c8b1c9481] - Request started
2026-03-26 14:41:19 - app.access - INFO - [6cd1b746-eef3-493d-971e-a04c8b1c9481] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [c53195ec-0621-42c0-8208-0dbad8af8860] - Request started
2026-03-26 14:41:19 - app.access - INFO - [c53195ec-0621-42c0-8208-0dbad8af8860] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [ff794b76-fde8-445c-b089-17e2e9222de5] - Request started
2026-03-26 14:41:19 - app.access - INFO - [ff794b76-fde8-445c-b089-17e2e9222de5] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [b2cd433c-3f5d-46a0-953e-f228f9a034a2] - Request started
2026-03-26 14:41:19 - app.access - INFO - [b2cd433c-3f5d-46a0-953e-f228f9a034a2] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [60a784a6-ceef-4faf-9e84-ffdf79be491c] - Request started
2026-03-26 14:41:19 - app.access - INFO - [60a784a6-ceef-4faf-9e84-ffdf79be491c] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [848a0b00-a61a-4b27-931a-16628003f42c] - Request started
2026-03-26 14:41:19 - app.access - INFO - [848a0b00-a61a-4b27-931a-16628003f42c] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [ab3bb103-9aee-45e8-a603-069c1297ccdc] - Request started
2026-03-26 14:41:19 - app.access - INFO - [ab3bb103-9aee-45e8-a603-069c1297ccdc] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [ad784452-89c4-4222-a35b-e88ab48a7379] - Request started
2026-03-26 14:41:19 - app.access - INFO - [ad784452-89c4-4222-a35b-e88ab48a7379] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [f03658ee-793d-4f48-9dae-663d4cb5a70c] - Request started
2026-03-26 14:41:19 - app.access - INFO - [f03658ee-793d-4f48-9dae-663d4cb5a70c] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [903792ba-1abe-4341-bb48-2a360b0801aa] - Request started
2026-03-26 14:41:19 - app.access - INFO - [903792ba-1abe-4341-bb48-2a360b0801aa] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [12ca04b8-c40f-4c98-acfe-56791eba76aa] - Request started
2026-03-26 14:41:19 - app.access - INFO - [12ca04b8-c40f-4c98-acfe-56791eba76aa] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [dca150ed-4361-44c2-adbc-4d211f759e4c] - Request started
2026-03-26 14:41:19 - app.access - INFO - [dca150ed-4361-44c2-adbc-4d211f759e4c] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [408c5893-a8b8-4baf-a789-fb3f6e0f7e19] - Request started
2026-03-26 14:41:19 - app.access - INFO - [408c5893-a8b8-4baf-a789-fb3f6e0f7e19] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [a91e19ad-06a9-4cff-96de-5a783e314caf] - Request started
2026-03-26 14:41:19 - app.access - INFO - [a91e19ad-06a9-4cff-96de-5a783e314caf] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [ce3dca83-daff-4fc0-8873-a02bf0ec47a8] - Request started
2026-03-26 14:41:19 - app.access - INFO - [ce3dca83-daff-4fc0-8873-a02bf0ec47a8] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [0795cfe1-03ed-42a8-8a13-f2c947254888] - Request started
2026-03-26 14:41:19 - app.access - INFO - [0795cfe1-03ed-42a8-8a13-f2c947254888] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [f1571efb-8d4a-4e5e-b42d-91e4e8618128] - Request started
2026-03-26 14:41:19 - app.access - INFO - [f1571efb-8d4a-4e5e-b42d-91e4e8618128] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [aceb20ce-1d4c-4aef-965c-23a6ee59f9ac] - Request started
2026-03-26 14:41:19 - app.access - INFO - [aceb20ce-1d4c-4aef-965c-23a6ee59f9ac] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [027fe9ad-97a9-4b3e-b3f7-aa81dcd84f32] - Request started
2026-03-26 14:41:19 - app.access - INFO - [027fe9ad-97a9-4b3e-b3f7-aa81dcd84f32] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [ffc9dd3d-a70a-464e-a16a-0e25107dff81] - Request started
2026-03-26 14:41:19 - app.access - INFO - [ffc9dd3d-a70a-464e-a16a-0e25107dff81] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [1d23d399-08d6-4e8f-8e62-47042aa63914] - Request started
2026-03-26 14:41:19 - app.access - INFO - [1d23d399-08d6-4e8f-8e62-47042aa63914] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [60217cfd-aa1d-4f18-8c9f-e26fc6b7845b] - Request started
2026-03-26 14:41:19 - app.access - INFO - [60217cfd-aa1d-4f18-8c9f-e26fc6b7845b] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [72eaaad2-dafb-4fd4-af11-a61393d02b2b] - Request started
2026-03-26 14:41:19 - app.access - INFO - [72eaaad2-dafb-4fd4-af11-a61393d02b2b] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [f30b9fd6-ba08-4d7d-b245-0039c9fa0848] - Request started
2026-03-26 14:41:19 - app.access - INFO - [f30b9fd6-ba08-4d7d-b245-0039c9fa0848] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [9367c684-d935-4659-a013-4e28108a4477] - Request started
2026-03-26 14:41:19 - app.access - INFO - [9367c684-d935-4659-a013-4e28108a4477] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [bf2c0bb2-18c9-4244-862b-2a9cf594f219] - Request started
2026-03-26 14:41:19 - app.access - INFO - [bf2c0bb2-18c9-4244-862b-2a9cf594f219] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [b79e65eb-d9b1-48b1-b815-b65689f60acd] - Request started
2026-03-26 14:41:19 - app.access - INFO - [b79e65eb-d9b1-48b1-b815-b65689f60acd] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [e2061598-c716-445b-90ae-71e67ca7c967] - Request started
2026-03-26 14:41:19 - app.access - INFO - [e2061598-c716-445b-90ae-71e67ca7c967] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [ebb65110-eef4-424c-b11e-c44dbdc87a5e] - Request started
2026-03-26 14:41:19 - app.access - INFO - [ebb65110-eef4-424c-b11e-c44dbdc87a5e] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [2095c0f8-f15d-4cd8-a0e7-2efc18c25bd5] - Request started
2026-03-26 14:41:19 - app.access - INFO - [2095c0f8-f15d-4cd8-a0e7-2efc18c25bd5] - Request completed
2026-03-26 14:41:19 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:19 - app.access - INFO - [65ad90d7-e9b3-4e5f-a145-b8b782e07b93] - Request started
2026-03-26 14:41:19 - app.access - INFO - [65ad90d7-e9b3-4e5f-a145-b8b782e07b93] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [cf77ef59-c2b6-46f3-8587-107295d70aae] - Request started
2026-03-26 14:41:20 - app.access - INFO - [cf77ef59-c2b6-46f3-8587-107295d70aae] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [51febe7e-6b10-4c66-84b1-11bee0ca1064] - Request started
2026-03-26 14:41:20 - app.access - INFO - [51febe7e-6b10-4c66-84b1-11bee0ca1064] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [0a3bef70-1ffd-4059-aefd-6be67aede415] - Request started
2026-03-26 14:41:20 - app.access - INFO - [0a3bef70-1ffd-4059-aefd-6be67aede415] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [4d968820-b1fe-4fa3-8257-2b2c62bc3eb0] - Request started
2026-03-26 14:41:20 - app.access - INFO - [4d968820-b1fe-4fa3-8257-2b2c62bc3eb0] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [97cc07c8-b293-4dc8-9e3f-1d76469b29a6] - Request started
2026-03-26 14:41:20 - app.access - INFO - [97cc07c8-b293-4dc8-9e3f-1d76469b29a6] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [cf3b4287-c0b5-4c5d-99cc-a62e9bd40475] - Request started
2026-03-26 14:41:20 - app.access - INFO - [cf3b4287-c0b5-4c5d-99cc-a62e9bd40475] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [af66144a-8408-431b-9eb1-898805e9dc69] - Request started
2026-03-26 14:41:20 - app.access - INFO - [af66144a-8408-431b-9eb1-898805e9dc69] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [a43c2d33-b076-4b9f-97f5-79beafb06a9f] - Request started
2026-03-26 14:41:20 - app.access - INFO - [a43c2d33-b076-4b9f-97f5-79beafb06a9f] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [eca4fd38-bff2-4f23-86fe-e450f92c9b24] - Request started
2026-03-26 14:41:20 - app.access - INFO - [eca4fd38-bff2-4f23-86fe-e450f92c9b24] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [6633f1ce-155f-4997-bfda-fd4adcc7faa4] - Request started
2026-03-26 14:41:20 - app.access - INFO - [6633f1ce-155f-4997-bfda-fd4adcc7faa4] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [4be41e6e-ed50-4ad1-8ac6-a7c755c99f75] - Request started
2026-03-26 14:41:20 - app.access - INFO - [4be41e6e-ed50-4ad1-8ac6-a7c755c99f75] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [e74aa6df-751c-42e6-bb5e-7ef0b7fa932d] - Request started
2026-03-26 14:41:20 - app.access - INFO - [e74aa6df-751c-42e6-bb5e-7ef0b7fa932d] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [51ad1113-be27-4ce4-9828-b82bd9675fb3] - Request started
2026-03-26 14:41:20 - app.access - INFO - [51ad1113-be27-4ce4-9828-b82bd9675fb3] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [fc35744c-41d4-478f-aaf1-49536cc0e2b7] - Request started
2026-03-26 14:41:20 - app.access - INFO - [fc35744c-41d4-478f-aaf1-49536cc0e2b7] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [5bfdd800-783b-4576-bb9d-091625af0c3d] - Request started
2026-03-26 14:41:20 - app.access - INFO - [5bfdd800-783b-4576-bb9d-091625af0c3d] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [57634ab4-fc2e-4171-88a8-9a788e533e8c] - Request started
2026-03-26 14:41:20 - app.access - INFO - [57634ab4-fc2e-4171-88a8-9a788e533e8c] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [521a13c8-9801-49d8-a309-7a07722dceae] - Request started
2026-03-26 14:41:20 - app.access - INFO - [521a13c8-9801-49d8-a309-7a07722dceae] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [fb8134ab-bb93-43c1-98ac-d8cc0c848ce5] - Request started
2026-03-26 14:41:20 - app.access - INFO - [fb8134ab-bb93-43c1-98ac-d8cc0c848ce5] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [025fc020-09b8-4a2f-bae0-6c7940d02b02] - Request started
2026-03-26 14:41:20 - app.access - INFO - [025fc020-09b8-4a2f-bae0-6c7940d02b02] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [9cc368fe-6568-4ea8-b8c2-a30d90a5aa4a] - Request started
2026-03-26 14:41:20 - app.access - INFO - [9cc368fe-6568-4ea8-b8c2-a30d90a5aa4a] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [bfc51a46-e52f-442b-8490-53993c5ef53c] - Request started
2026-03-26 14:41:20 - app.access - INFO - [bfc51a46-e52f-442b-8490-53993c5ef53c] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [bff47e03-2de4-4f99-bd9e-137f5b7daa10] - Request started
2026-03-26 14:41:20 - app.access - INFO - [bff47e03-2de4-4f99-bd9e-137f5b7daa10] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [08f74d5c-5745-4df7-af4e-1fa1551a4a5a] - Request started
2026-03-26 14:41:20 - app.access - INFO - [08f74d5c-5745-4df7-af4e-1fa1551a4a5a] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [352de849-6bca-43e8-b86b-d6264828cc4d] - Request started
2026-03-26 14:41:20 - app.access - INFO - [352de849-6bca-43e8-b86b-d6264828cc4d] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [d633140d-caf1-403a-8a64-0f01e3b7574b] - Request started
2026-03-26 14:41:20 - app.access - INFO - [d633140d-caf1-403a-8a64-0f01e3b7574b] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [ff84da79-6d66-4fb3-b1c7-85d82506bd77] - Request started
2026-03-26 14:41:20 - app.access - INFO - [ff84da79-6d66-4fb3-b1c7-85d82506bd77] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [40a8a8ea-cce2-4a45-bc0d-8187edbd5359] - Request started
2026-03-26 14:41:20 - app.access - INFO - [40a8a8ea-cce2-4a45-bc0d-8187edbd5359] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [ab9c54c0-9d7f-46af-8c0f-d6b4b5a3ac34] - Request started
2026-03-26 14:41:20 - app.access - INFO - [ab9c54c0-9d7f-46af-8c0f-d6b4b5a3ac34] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [4b71f914-2933-4f58-ac54-c8604baaa856] - Request started
2026-03-26 14:41:20 - app.access - INFO - [4b71f914-2933-4f58-ac54-c8604baaa856] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [4c72de7c-0fe5-4f85-b1b2-fe1fd971ee06] - Request started
2026-03-26 14:41:20 - app.access - INFO - [4c72de7c-0fe5-4f85-b1b2-fe1fd971ee06] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [0ee952cd-a0fa-4012-ba8d-7b8a6db52d29] - Request started
2026-03-26 14:41:20 - app.access - INFO - [0ee952cd-a0fa-4012-ba8d-7b8a6db52d29] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [7bd2658f-842c-4500-a2bc-3d3e53a1c096] - Request started
2026-03-26 14:41:20 - app.access - INFO - [7bd2658f-842c-4500-a2bc-3d3e53a1c096] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [f7ecc3fd-c6fb-42db-975b-bbfc9c67a36c] - Request started
2026-03-26 14:41:20 - app.access - INFO - [f7ecc3fd-c6fb-42db-975b-bbfc9c67a36c] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [7bd36abb-1d22-4f51-9ca2-fa78ecb1bc2a] - Request started
2026-03-26 14:41:20 - app.access - INFO - [7bd36abb-1d22-4f51-9ca2-fa78ecb1bc2a] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [089a39e4-0a14-496f-8258-61600cf1633b] - Request started
2026-03-26 14:41:20 - app.access - INFO - [089a39e4-0a14-496f-8258-61600cf1633b] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [f597aa7b-6540-48d4-a7e1-9336c2d45bbc] - Request started
2026-03-26 14:41:20 - app.access - INFO - [f597aa7b-6540-48d4-a7e1-9336c2d45bbc] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [cf1d9171-1a69-4c90-ad1e-07b10d06cf0d] - Request started
2026-03-26 14:41:20 - app.access - INFO - [cf1d9171-1a69-4c90-ad1e-07b10d06cf0d] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [7026c7d6-b546-475e-812e-333cbaee58cd] - Request started
2026-03-26 14:41:20 - app.access - INFO - [7026c7d6-b546-475e-812e-333cbaee58cd] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [87070522-6483-45df-9d72-806fa3be86c8] - Request started
2026-03-26 14:41:20 - app.access - INFO - [87070522-6483-45df-9d72-806fa3be86c8] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [4c8360fb-1607-47d1-8443-42ae91464324] - Request started
2026-03-26 14:41:20 - app.access - INFO - [4c8360fb-1607-47d1-8443-42ae91464324] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [3708e901-f206-45f2-b640-fd619586baf0] - Request started
2026-03-26 14:41:20 - app.access - INFO - [3708e901-f206-45f2-b640-fd619586baf0] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [28f6f1b6-4dc5-474a-af7c-1e5b8302020b] - Request started
2026-03-26 14:41:20 - app.access - INFO - [28f6f1b6-4dc5-474a-af7c-1e5b8302020b] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [93fabf15-7e24-4392-bacf-d0e801dccf21] - Request started
2026-03-26 14:41:20 - app.access - INFO - [93fabf15-7e24-4392-bacf-d0e801dccf21] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [f8d1a065-f1b6-41c9-9327-9a11076fa7d8] - Request started
2026-03-26 14:41:20 - app.access - INFO - [f8d1a065-f1b6-41c9-9327-9a11076fa7d8] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [e0b3af4e-3e47-44be-86af-4a9fc8dfc161] - Request started
2026-03-26 14:41:20 - app.access - INFO - [e0b3af4e-3e47-44be-86af-4a9fc8dfc161] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [b19ce8b8-3fe3-4a21-8064-46e4bf296ba0] - Request started
2026-03-26 14:41:20 - app.access - INFO - [b19ce8b8-3fe3-4a21-8064-46e4bf296ba0] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [8406fc03-128d-435b-9ba4-878e578793bf] - Request started
2026-03-26 14:41:20 - app.access - INFO - [8406fc03-128d-435b-9ba4-878e578793bf] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [ef50c640-3d99-44eb-b2f2-90b9831a57cf] - Request started
2026-03-26 14:41:20 - app.access - INFO - [ef50c640-3d99-44eb-b2f2-90b9831a57cf] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [295b7341-f943-4bf5-a0b2-e02ffbdef6e6] - Request started
2026-03-26 14:41:20 - app.access - INFO - [295b7341-f943-4bf5-a0b2-e02ffbdef6e6] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [547b730f-ed3d-4428-8b0a-444d9a15d1b0] - Request started
2026-03-26 14:41:20 - app.access - INFO - [547b730f-ed3d-4428-8b0a-444d9a15d1b0] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [64148eea-a3ed-411b-abac-96feadcb2255] - Request started
2026-03-26 14:41:20 - app.access - INFO - [64148eea-a3ed-411b-abac-96feadcb2255] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [9a79db63-2515-4c8a-ba09-3fd44c0f3260] - Request started
2026-03-26 14:41:20 - app.access - INFO - [9a79db63-2515-4c8a-ba09-3fd44c0f3260] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [7ed4051d-4e2d-4018-9f53-35f1684a66e0] - Request started
2026-03-26 14:41:20 - app.access - INFO - [7ed4051d-4e2d-4018-9f53-35f1684a66e0] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [13223f83-3bd4-4e76-9023-e1d1f697f642] - Request started
2026-03-26 14:41:20 - app.access - INFO - [13223f83-3bd4-4e76-9023-e1d1f697f642] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [5b245258-94f8-4b32-a54c-654752aa4caa] - Request started
2026-03-26 14:41:20 - app.access - INFO - [5b245258-94f8-4b32-a54c-654752aa4caa] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [d260225c-b48f-49eb-9864-6d130eda4d0c] - Request started
2026-03-26 14:41:20 - app.access - INFO - [d260225c-b48f-49eb-9864-6d130eda4d0c] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [66b5ae9d-76d9-440d-8ec2-ac4c809f9abb] - Request started
2026-03-26 14:41:20 - app.access - INFO - [66b5ae9d-76d9-440d-8ec2-ac4c809f9abb] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [7a54b4ed-bc1a-4c2b-a7d5-90d1092d3f68] - Request started
2026-03-26 14:41:20 - app.access - INFO - [7a54b4ed-bc1a-4c2b-a7d5-90d1092d3f68] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [512c6b66-35a8-4fa3-93c4-5d03c6b71200] - Request started
2026-03-26 14:41:20 - app.access - INFO - [512c6b66-35a8-4fa3-93c4-5d03c6b71200] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [bc36262f-8939-4484-af47-ad54093c779a] - Request started
2026-03-26 14:41:20 - app.access - INFO - [bc36262f-8939-4484-af47-ad54093c779a] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [cbdb8edd-6ea1-4d5b-b134-d910c099a0a9] - Request started
2026-03-26 14:41:20 - app.access - INFO - [cbdb8edd-6ea1-4d5b-b134-d910c099a0a9] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.access - INFO - [4c336cde-82d6-480e-ad85-8489ad3ea84b] - Request started
2026-03-26 14:41:20 - app.access - INFO - [4c336cde-82d6-480e-ad85-8489ad3ea84b] - Request completed
2026-03-26 14:41:20 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:20 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:20 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:20 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:20 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:20 - app.access - INFO - [00bb7265-9ade-4e28-8fcc-4af924251fad] - Request started
2026-03-26 14:41:21 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:21 - app.access - INFO - [00bb7265-9ade-4e28-8fcc-4af924251fad] - Request completed
2026-03-26 14:41:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:21 - app.access - INFO - [4b8dd47d-6d42-4a13-a7aa-cb6b0ccb3dce] - Request started
2026-03-26 14:41:21 - app.core.permissions - INFO - [no-trace-id] - 权限允许: 用户 admin@medqc.com 执行 update 操作在 medical_records 资源上
2026-03-26 14:41:21 - app.access - INFO - [4b8dd47d-6d42-4a13-a7aa-cb6b0ccb3dce] - Request completed
2026-03-26 14:41:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/tasks/task-1/assign "HTTP/1.1 200 OK"
2026-03-26 14:41:21 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:21 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:21 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:21 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:21 - app.access - INFO - [29770b2c-ab2e-48a9-bf44-bca55c8a2075] - Request started
2026-03-26 14:41:21 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:21 - app.access - INFO - [29770b2c-ab2e-48a9-bf44-bca55c8a2075] - Request completed
2026-03-26 14:41:21 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:21 - app.access - INFO - [781d18a9-8270-455a-ae68-0b8283e8e202] - Request started
2026-03-26 14:41:21 - app.access - INFO - [781d18a9-8270-455a-ae68-0b8283e8e202] - Request completed
2026-03-26 14:41:21 - httpx - INFO - [no-trace-id] - HTTP Request: DELETE http://testserver/api/v1/tasks/task-del-1 "HTTP/1.1 200 OK"
2026-03-26 14:41:21 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:21 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:21 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:21 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:21 - app.access - INFO - [cda95662-ab74-481d-a4b8-2b68f9b3c976] - Request started
2026-03-26 14:41:22 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:22 - app.access - INFO - [cda95662-ab74-481d-a4b8-2b68f9b3c976] - Request completed
2026-03-26 14:41:22 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:22 - app.access - INFO - [2efe8ff9-789b-4dcd-8fe5-fc3e32d54c9e] - Request started
2026-03-26 14:41:22 - app.main - WARNING - [2efe8ff9-789b-4dcd-8fe5-fc3e32d54c9e] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:41:22 - app.access - WARNING - [2efe8ff9-789b-4dcd-8fe5-fc3e32d54c9e] - Request completed
2026-03-26 14:41:22 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/parse-medical-file-public "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:41:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:22 - app.access - INFO - [7fb6f7d5-0716-4795-af4e-05b4c94a23cd] - Request started
2026-03-26 14:41:22 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:22 - app.access - INFO - [7fb6f7d5-0716-4795-af4e-05b4c94a23cd] - Request completed
2026-03-26 14:41:22 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:22 - app.access - INFO - [c0e62801-808d-47db-a621-eb1908ae0c16] - Request started
2026-03-26 14:41:22 - app.main - WARNING - [c0e62801-808d-47db-a621-eb1908ae0c16] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:41:22 - app.access - WARNING - [c0e62801-808d-47db-a621-eb1908ae0c16] - Request completed
2026-03-26 14:41:22 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/batch-upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:41:22 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:22 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:22 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:22 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:22 - app.access - INFO - [b3276cff-25b4-46fb-b2a1-d934a9948440] - Request started
2026-03-26 14:41:23 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:23 - app.access - INFO - [b3276cff-25b4-46fb-b2a1-d934a9948440] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:23 - app.access - INFO - [1f151d98-0ba0-49cf-a294-f6584ee532fc] - Request started
2026-03-26 14:41:23 - app.main - WARNING - [1f151d98-0ba0-49cf-a294-f6584ee532fc] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:41:23 - app.access - WARNING - [1f151d98-0ba0-49cf-a294-f6584ee532fc] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/records/upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:41:23 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:23 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:23 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:23 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:23 - app.access - INFO - [12f77892-4de8-4601-bae2-0079c71d1737] - Request started
2026-03-26 14:41:23 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:23 - app.access - INFO - [12f77892-4de8-4601-bae2-0079c71d1737] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:23 - app.access - INFO - [3e7bae8f-9644-424b-856b-6cfc8a9ae582] - Request started
2026-03-26 14:41:23 - app.main - WARNING - [3e7bae8f-9644-424b-856b-6cfc8a9ae582] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:41:23 - app.access - WARNING - [3e7bae8f-9644-424b-856b-6cfc8a9ae582] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:23 - app.access - INFO - [fd1ff723-daef-4a91-9540-7de198565107] - Request started
2026-03-26 14:41:23 - app.main - WARNING - [fd1ff723-daef-4a91-9540-7de198565107] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:41:23 - app.access - WARNING - [fd1ff723-daef-4a91-9540-7de198565107] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:23 - app.access - INFO - [36980030-feea-48d7-82b5-ae10bb09cca9] - Request started
2026-03-26 14:41:23 - app.main - WARNING - [36980030-feea-48d7-82b5-ae10bb09cca9] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:41:23 - app.access - WARNING - [36980030-feea-48d7-82b5-ae10bb09cca9] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:23 - app.access - INFO - [cd0e1829-f2c7-42ea-8e07-e05a9dfc7f1e] - Request started
2026-03-26 14:41:23 - app.main - WARNING - [cd0e1829-f2c7-42ea-8e07-e05a9dfc7f1e] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:41:23 - app.access - WARNING - [cd0e1829-f2c7-42ea-8e07-e05a9dfc7f1e] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:23 - app.access - INFO - [5bf60f2a-a543-4b6b-92d3-a40349f05776] - Request started
2026-03-26 14:41:23 - app.main - WARNING - [5bf60f2a-a543-4b6b-92d3-a40349f05776] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:41:23 - app.access - WARNING - [5bf60f2a-a543-4b6b-92d3-a40349f05776] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:23 - app.access - INFO - [8ef618bb-ee3a-4b1b-a55a-17a06c18199e] - Request started
2026-03-26 14:41:23 - app.main - WARNING - [8ef618bb-ee3a-4b1b-a55a-17a06c18199e] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:41:23 - app.access - WARNING - [8ef618bb-ee3a-4b1b-a55a-17a06c18199e] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:23 - app.access - INFO - [efdb15cf-849d-4f12-8463-c82e387234f6] - Request started
2026-03-26 14:41:23 - app.main - WARNING - [efdb15cf-849d-4f12-8463-c82e387234f6] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:41:23 - app.access - WARNING - [efdb15cf-849d-4f12-8463-c82e387234f6] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:23 - app.access - INFO - [801c2745-d972-4d15-bf4c-42232d41d242] - Request started
2026-03-26 14:41:23 - app.main - WARNING - [801c2745-d972-4d15-bf4c-42232d41d242] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:41:23 - app.access - WARNING - [801c2745-d972-4d15-bf4c-42232d41d242] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:23 - app.access - INFO - [95cd63cf-b7de-4aa1-8810-12a2504376b9] - Request started
2026-03-26 14:41:23 - app.main - WARNING - [95cd63cf-b7de-4aa1-8810-12a2504376b9] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:41:23 - app.access - WARNING - [95cd63cf-b7de-4aa1-8810-12a2504376b9] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:23 - app.access - INFO - [0568aec1-018a-4f71-b3a7-d8ad5a7ff57d] - Request started
2026-03-26 14:41:23 - app.main - WARNING - [0568aec1-018a-4f71-b3a7-d8ad5a7ff57d] - HTTP Exception: 400 - 不支持的文件格式: .txt，仅支持 .xlsx/.xls/.csv/.zip
2026-03-26 14:41:23 - app.access - WARNING - [0568aec1-018a-4f71-b3a7-d8ad5a7ff57d] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:23 - app.access - INFO - [da9d17f1-0aa6-4c4c-8e91-789f1c3ee4df] - Request started
2026-03-26 14:41:23 - app.core.rate_limit - WARNING - [da9d17f1-0aa6-4c4c-8e91-789f1c3ee4df] - audit.rate_limit.exceeded bucket=drg_smart_upload key=drg_smart_upload:testclient method=POST path=/api/v1/drg/smart-upload
2026-03-26 14:41:23 - app.main - WARNING - [da9d17f1-0aa6-4c4c-8e91-789f1c3ee4df] - HTTP Exception: 429 - Too many requests, please retry later.
2026-03-26 14:41:23 - app.access - WARNING - [da9d17f1-0aa6-4c4c-8e91-789f1c3ee4df] - Request completed
2026-03-26 14:41:23 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 429 Too Many Requests"
2026-03-26 14:41:23 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:23 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:23 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:23 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:23 - app.access - INFO - [b842b482-c366-4e3f-9e50-eb44894c8e0f] - Request started
2026-03-26 14:41:24 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:24 - app.access - INFO - [b842b482-c366-4e3f-9e50-eb44894c8e0f] - Request completed
2026-03-26 14:41:24 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:24 - app.access - INFO - [2d6a12b2-292e-4865-8f07-94ec49740e69] - Request started
2026-03-26 14:41:24 - app.core.upload_security - WARNING - [2d6a12b2-292e-4865-8f07-94ec49740e69] - audit.upload.rejected reason=extension_not_allowed filename=malicious.exe content_type=application/octet-stream size_bytes=4
2026-03-26 14:41:24 - app.main - WARNING - [2d6a12b2-292e-4865-8f07-94ec49740e69] - HTTP Exception: 400 - 不支持的文件扩展名: .exe
2026-03-26 14:41:24 - app.access - WARNING - [2d6a12b2-292e-4865-8f07-94ec49740e69] - Request completed
2026-03-26 14:41:24 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/parse-medical-file-public "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:24 - app.access - INFO - [d8fe8920-f16e-4751-84c5-1c35979421ec] - Request started
2026-03-26 14:41:24 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:24 - app.access - INFO - [d8fe8920-f16e-4751-84c5-1c35979421ec] - Request completed
2026-03-26 14:41:24 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:24 - app.access - INFO - [861c66e2-1355-491a-b28c-30e791eb31e7] - Request started
2026-03-26 14:41:24 - app.core.upload_security - WARNING - [861c66e2-1355-491a-b28c-30e791eb31e7] - audit.upload.rejected reason=virus_scan_blocked filename=record.txt content_type=text/plain size_bytes=68
2026-03-26 14:41:24 - app.main - WARNING - [861c66e2-1355-491a-b28c-30e791eb31e7] - HTTP Exception: 400 - 检测到潜在恶意文件签名
2026-03-26 14:41:24 - app.access - WARNING - [861c66e2-1355-491a-b28c-30e791eb31e7] - Request completed
2026-03-26 14:41:24 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/records/upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:24 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:24 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:24 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:24 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:24 - app.access - INFO - [093b7a03-83ac-48f2-b412-5dd585ffd133] - Request started
2026-03-26 14:41:25 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:25 - app.access - INFO - [093b7a03-83ac-48f2-b412-5dd585ffd133] - Request completed
2026-03-26 14:41:25 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:25 - app.access - INFO - [85e75a38-2c0c-4ced-a9c0-46f4bc528cc4] - Request started
2026-03-26 14:41:25 - app.core.upload_security - WARNING - [85e75a38-2c0c-4ced-a9c0-46f4bc528cc4] - audit.upload.rejected reason=mime_not_allowed filename=sample.csv content_type=image/png size_bytes=81
2026-03-26 14:41:25 - app.main - WARNING - [85e75a38-2c0c-4ced-a9c0-46f4bc528cc4] - HTTP Exception: 400 - 不支持的文件类型: image/png
2026-03-26 14:41:25 - app.access - WARNING - [85e75a38-2c0c-4ced-a9c0-46f4bc528cc4] - Request completed
2026-03-26 14:41:25 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/batch-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:25 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
2026-03-26 14:41:25 - app.database.connection - INFO - [no-trace-id] - [init_db] DB_SCHEMA_MODE=split, skip create_all/schema-sync; managed by Alembic.
2026-03-26 14:41:25 - app.database.connection - INFO - [no-trace-id] - [OK] CDM database initialized (PostgreSQL): postgresql://postgres:***@localhost:5432/medqc
2026-03-26 14:41:25 - app.main - INFO - [no-trace-id] - \u2139\ufe0f 跳过启动阶段的四川质控服务初始化（将按需懒加载）
2026-03-26 14:41:25 - app.access - INFO - [f1ac515a-43a7-48de-9847-bc99872e6b34] - Request started
2026-03-26 14:41:25 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:25 - app.access - INFO - [f1ac515a-43a7-48de-9847-bc99872e6b34] - Request completed
2026-03-26 14:41:25 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:25 - app.access - INFO - [cdf6b99a-ffbe-4236-9fc7-4fed443d771f] - Request started
2026-03-26 14:41:25 - app.core.upload_security - WARNING - [cdf6b99a-ffbe-4236-9fc7-4fed443d771f] - audit.upload.rejected reason=file_too_large filename=sample.csv content_type=text/csv size_bytes=10
2026-03-26 14:41:25 - app.main - WARNING - [cdf6b99a-ffbe-4236-9fc7-4fed443d771f] - HTTP Exception: 400 - 文件大小不能超过 8B
2026-03-26 14:41:25 - app.access - WARNING - [cdf6b99a-ffbe-4236-9fc7-4fed443d771f] - Request completed
2026-03-26 14:41:25 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/drg/smart-upload "HTTP/1.1 400 Bad Request"
2026-03-26 14:41:25 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:41:26 - app.main - INFO - [no-trace-id] - \U0001f680 应用启动中...
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

app\main.py:304
tests/integration/test_release_gate_smoke.py::test_release_gate_auth_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_authz_reject_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_sync_trigger_permission_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_records_query_smoke
tests/integration/test_release_gate_smoke.py::test_release_gate_system_probe_smoke
  D:\LLM\lx0222\health-qc-monorepo\apps\medqc-web\backend\app\main.py:304: DeprecationWarning: 
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
======================= 5 passed, 19 warnings in 6.53s ========================
2026-03-26 14:41:37 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:41:37 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:41:38 - app.access - INFO - [bedfec74-84d3-40c8-8b30-d4525af2c78a] - Request started
2026-03-26 14:41:39 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=release-gate-8c9b5b28c60d@example.com roles=doctor trace_id=bedfec74-84d3-40c8-8b30-d4525af2c78a details={"assigned_roles": ["doctor"], "department": "质控科", "target_email": "release-gate-8c9b5b28c60d@example.com"}
2026-03-26 14:41:39 - app.access - INFO - [bedfec74-84d3-40c8-8b30-d4525af2c78a] - Request completed
2026-03-26 14:41:39 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 14:41:39 - app.access - INFO - [c9537bf9-73a9-4b7e-82b3-208f192bade9] - Request started
2026-03-26 14:41:39 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-8c9b5b28c60d@example.com
2026-03-26 14:41:39 - app.access - INFO - [c9537bf9-73a9-4b7e-82b3-208f192bade9] - Request completed
2026-03-26 14:41:39 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:39 - app.access - INFO - [5b561518-2c12-4430-aee0-d2a4239eabad] - Request started
2026-03-26 14:41:39 - app.access - INFO - [5b561518-2c12-4430-aee0-d2a4239eabad] - Request completed
2026-03-26 14:41:39 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/auth/me "HTTP/1.1 200 OK"
2026-03-26 14:41:39 - app.access - INFO - [e62a5af3-5d23-45e8-9504-77c40d27237b] - Request started
2026-03-26 14:41:39 - app.routers.auth - INFO - [no-trace-id] - auth.refresh.success email=release-gate-8c9b5b28c60d@example.com
2026-03-26 14:41:39 - app.access - INFO - [e62a5af3-5d23-45e8-9504-77c40d27237b] - Request completed
2026-03-26 14:41:39 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/refresh "HTTP/1.1 200 OK"
2026-03-26 14:41:39 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:41:40 - app.access - INFO - [8fe63bcd-1a57-4557-afb3-545636d82da1] - Request started
2026-03-26 14:41:40 - app.main - WARNING - [8fe63bcd-1a57-4557-afb3-545636d82da1] - HTTP Exception: 401 - Authentication required
2026-03-26 14:41:40 - app.access - WARNING - [8fe63bcd-1a57-4557-afb3-545636d82da1] - Request completed
2026-03-26 14:41:40 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/medical-records/list "HTTP/1.1 401 Unauthorized"
2026-03-26 14:41:40 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:41:41 - app.access - INFO - [7aaec38c-f96e-43b9-92bc-1d7fe9980e01] - Request started
2026-03-26 14:41:41 - app.audit - INFO - [no-trace-id] - audit.event action=auth.user.register resource=/api/v1/auth/register outcome=success actor=release-gate-6965aa2c3c74@example.com roles=doctor trace_id=7aaec38c-f96e-43b9-92bc-1d7fe9980e01 details={"assigned_roles": ["doctor"], "department": "质控科", "target_email": "release-gate-6965aa2c3c74@example.com"}
2026-03-26 14:41:41 - app.access - INFO - [7aaec38c-f96e-43b9-92bc-1d7fe9980e01] - Request completed
2026-03-26 14:41:41 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/register "HTTP/1.1 200 OK"
2026-03-26 14:41:41 - app.access - INFO - [abdf6e7a-f300-4085-a137-1a5284dd9dbd] - Request started
2026-03-26 14:41:41 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=release-gate-6965aa2c3c74@example.com
2026-03-26 14:41:41 - app.access - INFO - [abdf6e7a-f300-4085-a137-1a5284dd9dbd] - Request completed
2026-03-26 14:41:41 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:41 - app.access - INFO - [4eea1ea8-bf70-4e55-bebe-a075c617aaad] - Request started
2026-03-26 14:41:41 - app.main - WARNING - [4eea1ea8-bf70-4e55-bebe-a075c617aaad] - HTTP Exception: 403 - 数据同步写入权限不足（仅 admin 可操作）
2026-03-26 14:41:41 - app.access - WARNING - [4eea1ea8-bf70-4e55-bebe-a075c617aaad] - Request completed
2026-03-26 14:41:41 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/sync/trigger "HTTP/1.1 403 Forbidden"
2026-03-26 14:41:41 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:41:42 - app.access - INFO - [dca402cf-b2a0-45db-b94e-7dca8cb50d03] - Request started
2026-03-26 14:41:42 - app.routers.auth - INFO - [no-trace-id] - auth.login.success email=admin@medqc.com
2026-03-26 14:41:42 - app.access - INFO - [dca402cf-b2a0-45db-b94e-7dca8cb50d03] - Request completed
2026-03-26 14:41:43 - httpx - INFO - [no-trace-id] - HTTP Request: POST http://testserver/api/v1/auth/login "HTTP/1.1 200 OK"
2026-03-26 14:41:43 - app.access - INFO - [242acb10-6211-4838-8479-4d7f260cbc92] - Request started
2026-03-26 14:41:43 - app.core.permissions - INFO - [no-trace-id] - 权限允许: 用户 admin@medqc.com 执行 read 操作在 medical_records 资源上
2026-03-26 14:41:43 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端连接池就绪: localhost:5432/medqc (schema_mode=split, search_path=qc,sys,cdm,public,legacy)
2026-03-26 14:41:43 - app.core.supabase_client - INFO - [no-trace-id] - SQLAlchemy 适配客户端已就绪（替代 Supabase）
2026-03-26 14:41:43 - app.access - INFO - [242acb10-6211-4838-8479-4d7f260cbc92] - Request completed
2026-03-26 14:41:43 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/records?page=1&page_size=5 "HTTP/1.1 200 OK"
2026-03-26 14:41:43 - app.main - INFO - [no-trace-id] - LLM diagnostics at startup: {'source': 'LLM_*', 'endpoint_set': True, 'api_key_set': True, 'model': 'qwen3.5-35b-a3b', 'timeout_seconds': 120, 'allow_mock_when_unconfigured': False}
2026-03-26 14:41:44 - app.access - INFO - [d765cdc5-4536-401b-90eb-75bfebdbd0f4] - Request started
2026-03-26 14:41:44 - app.access - INFO - [d765cdc5-4536-401b-90eb-75bfebdbd0f4] - Request completed
2026-03-26 14:41:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/health "HTTP/1.1 200 OK"
2026-03-26 14:41:44 - app.access - INFO - [0027cffd-00b0-483c-9b12-c3692a2f92f7] - Request started
2026-03-26 14:41:44 - app.access - INFO - [0027cffd-00b0-483c-9b12-c3692a2f92f7] - Request completed
2026-03-26 14:41:44 - httpx - INFO - [no-trace-id] - HTTP Request: GET http://testserver/api/v1/ready "HTTP/1.1 200 OK"
```